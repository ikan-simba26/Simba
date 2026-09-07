"""Find things that are visually covering the page, structurally.

Real sites put modals up as plain positioned `div`s with no `role="dialog"`
and no `aria-modal`, so the accessibility tree says nothing about them and a
planner sees the dialog's buttons as just more buttons in a long list. That
is how a run ends up clicking something underneath a modal and waiting for a
click that can never land.

So this ignores ARIA entirely and works from layout: an element that is
positioned and stacked above the page is a candidate, and anything whose
centre falls inside it is occluded.

There are two rules for *how big a candidate has to be*, because there are
two different questions being asked.

  **Page-level.** `MIN_COVERAGE` — is the page as a whole unusable? A modal
  backdrop covers most of the viewport; a toast covers a sliver. This is the
  rule that answers "is there a dialog in the way", and it stays as it was.

  **Target-scoped.** Pass a `target` and size stops mattering: anything
  stacked above the page that *overlaps the element the next move is about
  to touch* is blocking that move, at any size. A 220x180 dropdown is 2% of
  the viewport and 100% of the reason the click fails.

The second rule exists because the first one missed both real cases we have:
the billing replica's cookie bar (6.6% of the viewport, sitting on six live
links) and the live railways dropdown (~2%, sitting on the field the next
step needed). Coverage was never the right question for those — it was
whether the thing in the way is in the way *of what we are doing*.
"""

from dataclasses import dataclass, field

from backend.perception.snapshot import (
    COMPUTED_STYLES,
    Document,
    Rect,
    centre_inside,
    overlaps,
    parse,
    visible,
)

__all__ = ["COMPUTED_STYLES", "Blocker", "OverlayReport", "MIN_COVERAGE",
           "MIN_STACK_LEVEL", "STACKED_POSITIONS", "analyse"]

STACKED_POSITIONS = {"fixed", "absolute"}
# A z-index this far above the page is a deliberate "put me on top".
MIN_STACK_LEVEL = 5
# Fraction of the viewport an element must cover before it counts as blocking
# the page as a whole. Not used at all when a target is named.
MIN_COVERAGE = 0.30


@dataclass
class Blocker:
    """One element that is covering the page, or covering the target."""

    backend_node_id: int
    rect: Rect
    z_index: int
    coverage: float
    reason: str
    # True when this was found by overlapping the named target rather than by
    # covering enough of the viewport. Kept apart so a log can say which rule
    # fired, and so the page-level meaning of `blocked` does not quietly
    # change into something broader.
    scoped_to_target: bool = False


@dataclass
class OverlayReport:
    blockers: list[Blocker] = field(default_factory=list)
    # Backend node ids belonging to an overlay — the things you can use to
    # dismiss it.
    overlay_ids: set[int] = field(default_factory=set)
    # Backend node ids sitting behind one.
    occluded_ids: set[int] = field(default_factory=set)

    @property
    def blocked(self) -> bool:
        return bool(self.blockers)

    @property
    def target_blockers(self) -> list[Blocker]:
        return [b for b in self.blockers if b.scoped_to_target]


def analyse(
    snapshot: dict | Document | None,
    viewport: tuple[int, int],
    target: int | None = None,
) -> OverlayReport:
    """Work out what is covering the page, and what is stuck behind it.

    `target` is the backend node id of the element a move is about to act on.
    Give it one and the target-scoped rule applies as well: anything stacked
    above the page and overlapping that element is reported, however small.
    Leave it None and this behaves exactly as it always did.
    """
    document = snapshot if isinstance(snapshot, Document) else parse(snapshot)
    if document is None:
        return OverlayReport()

    viewport_area = float(viewport[0] * viewport[1]) or 1.0

    target_index = (
        document.index_of_backend_id.get(target) if target is not None else None
    )
    target_rect = document.bounds.get(target_index) if target_index is not None else None
    # A container the target lives inside is not covering it. Without this the
    # positioned dropdown panel would be reported as blocking its own options.
    target_lineage: set[int] = set()
    if target_index is not None:
        target_lineage = {target_index, *document.ancestors(target_index)}

    blockers: list[Blocker] = []
    blocker_indexes: list[int] = []

    for node_index, style in document.styles.items():
        if not visible(style):
            continue
        if style.get("position") not in STACKED_POSITIONS:
            continue

        z_index = _int_or_none(style.get("z-index"))
        if z_index is None or z_index < MIN_STACK_LEVEL:
            continue

        bounds = document.bounds.get(node_index)
        if bounds is None:
            continue
        _, _, width, height = bounds
        coverage = (width * height) / viewport_area

        covers_page = coverage >= MIN_COVERAGE
        covers_target = (
            target_rect is not None
            and node_index not in target_lineage
            and overlaps(bounds, target_rect)
        )
        if not covers_page and not covers_target:
            continue

        blocker_indexes.append(node_index)
        if covers_page:
            reason = (
                f"{style['position']} at z-index {z_index}, "
                f"covering {round(coverage * 100)}% of the viewport"
            )
        else:
            reason = (
                f"{style['position']} at z-index {z_index}, overlapping the "
                f"element this step needs (only {round(coverage * 100)}% of "
                f"the viewport, so the page-level rule does not see it)"
            )
        blockers.append(
            Blocker(
                backend_node_id=document.backend_id(node_index),
                rect=bounds,
                z_index=z_index,
                coverage=round(coverage, 3),
                reason=reason,
                scoped_to_target=not covers_page,
            )
        )

    if not blockers:
        return OverlayReport()

    return OverlayReport(
        blockers=blockers,
        overlay_ids={
            document.backend_id(i) for i in _overlay_indexes(document, blocker_indexes)
        },
        occluded_ids={
            document.backend_id(i)
            for i in _occluded_indexes(document, blockers, blocker_indexes)
        },
    )


def _overlay_indexes(document: Document, blocker_indexes: list[int]) -> set[int]:
    """Everything belonging to a blocker — its subtree, and stacked siblings.

    The sibling case is the common backdrop-plus-dialog pair, where the dialog
    is not a child of the backdrop but of the same parent.
    """
    overlay: set[int] = set()
    for blocker_index in blocker_indexes:
        overlay |= document.subtree(blocker_index)
        parent = document.parents[blocker_index]
        for sibling in document.children.get(parent, ()):
            if sibling == blocker_index:
                continue
            style = document.styles.get(sibling)
            if style is None:
                continue
            sibling_z = _int_or_none(style.get("z-index"))
            if (
                visible(style)
                and style.get("position") in STACKED_POSITIONS
                and sibling_z is not None
                and sibling_z >= MIN_STACK_LEVEL
            ):
                overlay |= document.subtree(sibling)
    return overlay


def _occluded_indexes(
    document: Document, blockers: list[Blocker], blocker_indexes: list[int]
) -> set[int]:
    overlay = _overlay_indexes(document, blocker_indexes)
    occluded: set[int] = set()
    for node_index, bounds in document.bounds.items():
        if node_index in overlay:
            continue
        if any(centre_inside(bounds, blocker.rect) for blocker in blockers):
            occluded.add(node_index)
    return occluded


def _int_or_none(value: str | None) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
