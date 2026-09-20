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

**What counts as "stacked above the page"** is the other half, and it was an
assumption until the corpus caught it. A declared `z-index` of at least
`MIN_STACK_LEVEL` is one way an element says it is on top. It is not the only
one: `position: fixed` and `position: sticky` lift an element out of the flow
and paint it against the viewport, so a fixed box the size of the screen is
on top of the page whether or not anyone wrote a `z-index` for it. It does
not need one, being fixed and last in the DOM, and plenty of real modals do
not bother — `the-internet.herokuapp.com/entry_ad` covers 100% of the
viewport at `z-index: auto`, and this module reported nothing on it for as
long as it existed (EVALUATION.md, 2026-09-20b).

So a fixed or sticky element over `MIN_COVERAGE` is a page-level blocker
whatever its z-index. `absolute` is deliberately *not* in that set: an
absolutely positioned box sits in normal paint order, so covering the
viewport says nothing about being on top of it — that is every stretched
background and every hero image on the web, and entry_ad's own `.underlay`.
An `absolute` element still has to declare itself with a z-index, as before.
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

__all__ = ["COMPUTED_STYLES", "Blocker", "Candidate", "OverlayReport",
           "MIN_COVERAGE", "MIN_STACK_LEVEL", "STACKED_POSITIONS",
           "LIFTED_POSITIONS", "analyse", "candidates"]

STACKED_POSITIONS = {"fixed", "absolute"}
#: Positions that are painted against the viewport rather than laid out in
#: the flow. One of these plus enough coverage is a blocker on its own: the
#: element is on top of the page whether or not it declared a z-index.
#:
#: Not a subset of `STACKED_POSITIONS`, and the two are not interchangeable.
#: They overlap at `fixed` and differ at both ends — `absolute` takes part in
#: the declared-stacking rule but not this one, because being absolutely
#: positioned says nothing about paint order, and `sticky` takes part in this
#: one but not that one.
LIFTED_POSITIONS = {"fixed", "sticky"}
# A z-index this far above the page is a deliberate "put me on top".
MIN_STACK_LEVEL = 5
# Fraction of the viewport an element must cover before it counts as blocking
# the page as a whole. Not used at all when a target is named.
#
# Measured on 2026-09-20 against the 45-page corpus rather than left as the
# guess it had been since the rule was written, and kept at 0.30 on the
# result. 96 candidates: every real blocker covers **1.000**, the largest
# thing that is not one covers **0.234** (a documentation sidebar), and the
# band between them is **empty**.
#
# So the evidence bounds this number rather than picking it — anything in
# (0.234, 0.90] behaves identically on everything we have seen, and 0.30 is
# already inside that. What the corpus does rule out is going lower: 0.15
# calls Wikipedia and MDN blocked. EVALUATION.md, 2026-09-20d, has the
# distribution, the sweep, and what this calibration cannot tell you.
MIN_COVERAGE = 0.30


@dataclass
class Blocker:
    """One element that is covering the page, or covering the target."""

    backend_node_id: int
    rect: Rect
    #: None when the element never declared one. A blocker found by its
    #: position alone has no z-index to report, and reporting 0 for that
    #: would be a number nobody wrote.
    z_index: int | None
    coverage: float
    reason: str
    # True when this was found by overlapping the named target rather than by
    # covering enough of the viewport. Kept apart so a log can say which rule
    # fired, and so the page-level meaning of `blocked` does not quietly
    # change into something broader.
    scoped_to_target: bool = False


@dataclass(frozen=True)
class Candidate:
    """One element painted above the page, before any rule has judged it.

    `analyse` narrows these down to blockers. It is a named type rather than a
    local tuple so that a calibration probe can see exactly what the detector
    saw — a threshold measured against a reimplementation of the candidate set
    is measuring the reimplementation (`tools/evaluation/overlay_coverage_probe`).
    """

    node_index: int
    backend_node_id: int
    rect: Rect
    coverage: float
    position: str
    #: None when the element never declared one, which is `z-index: auto`.
    z_index: int | None
    #: True when a declared z-index is what put it above the page. False when
    #: its position alone did, which is the `fixed`/`sticky` case.
    declared: bool
    tag: str

    @property
    def lifted(self) -> bool:
        """Painted against the viewport rather than in the flow."""
        return self.position in LIFTED_POSITIONS


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


def candidates(document: Document, viewport: tuple[int, int]) -> list[Candidate]:
    """Everything painted above the page, with how much of it each covers.

    Two ways in, and an element only needs one:

      * a declared `z-index` of at least `MIN_STACK_LEVEL` while positioned
        `fixed` or `absolute` — the element saying "put me on top";
      * `position: fixed` or `position: sticky` at any z-index — the layout
        saying it, because both are painted against the viewport rather than
        in the flow.

    No coverage threshold is applied here. That is the caller's question, and
    keeping it out is what lets the probe report the distribution the
    threshold is chosen from.
    """
    viewport_area = float(viewport[0] * viewport[1]) or 1.0
    found: list[Candidate] = []
    for node_index, style in document.styles.items():
        if not visible(style):
            continue
        position = style.get("position") or ""
        z_index = _int_or_none(style.get("z-index"))
        declared = (
            position in STACKED_POSITIONS
            and z_index is not None
            and z_index >= MIN_STACK_LEVEL
        )
        if not declared and position not in LIFTED_POSITIONS:
            continue
        bounds = document.bounds.get(node_index)
        if bounds is None:
            continue
        _, _, width, height = bounds
        found.append(
            Candidate(
                node_index=node_index,
                backend_node_id=document.backend_id(node_index),
                rect=bounds,
                coverage=(width * height) / viewport_area,
                position=position,
                z_index=z_index,
                declared=declared,
                tag=document.tag(node_index),
            )
        )
    return found


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

    **The target-scoped rule still asks for a declared z-index.** A fixed
    element with no z-index reaches the page-level rule only, so the two rules
    do not have the same candidate set. That is deliberate and narrow: a
    fixed header overlapping the target is genuinely in the way, but so is
    every decorative full-screen layer with `pointer-events: none`, and the
    page-level rule at least requires such a thing to be huge before it says
    anything. Widening the target rule is flagged, not taken
    (EVALUATION.md, 2026-09-20d).
    """
    document = snapshot if isinstance(snapshot, Document) else parse(snapshot)
    if document is None:
        return OverlayReport()

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

    for candidate in candidates(document, viewport):
        covers_page = candidate.coverage >= MIN_COVERAGE
        covers_target = (
            candidate.declared
            and target_rect is not None
            and candidate.node_index not in target_lineage
            and overlaps(candidate.rect, target_rect)
        )
        if not covers_page and not covers_target:
            continue

        blocker_indexes.append(candidate.node_index)
        percent = round(candidate.coverage * 100)
        where = f"{candidate.position} at z-index {_z_label(candidate.z_index)}"
        if covers_page:
            reason = f"{where}, covering {percent}% of the viewport"
        else:
            reason = (
                f"{where}, overlapping the element this step needs "
                f"(only {percent}% of the viewport, so the page-level rule "
                f"does not see it)"
            )
        blockers.append(
            Blocker(
                backend_node_id=candidate.backend_node_id,
                rect=candidate.rect,
                z_index=candidate.z_index,
                coverage=round(candidate.coverage, 3),
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


def _z_label(z_index: int | None) -> str:
    """What to call a z-index in a reason, including not having one."""
    return "auto" if z_index is None else str(z_index)


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
