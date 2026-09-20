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

  Coverage is the share of the *screen* an element hides, so the box is
  clipped to the viewport before the fraction is taken. That is not the same
  as its own area, and the difference only shows up on a long page: the
  Guardian has a 700x570 panel nine thousand pixels down, which is 39% of a
  viewport's worth of area and 0% of anything anyone can see. Until
  2026-09-20e this module called that a blocker, and could not have known —
  every overlay it had ever measured was a full-screen modal at (0, 0),
  where the two numbers are equal.

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

**`html` and `body` are never candidates.** A page cannot be covering
itself, and both are routinely given `position: fixed` as a scroll lock —
the standard trick for stopping the page behind a modal from scrolling. That
made the page its own blocker: `body`'s box is the *document*, so the
Guardian reported coverage **27.17** and Spiegel **43.61** (EVALUATION.md,
2026-09-20e). Worse than the number, `_overlay_indexes` takes a blocker's
whole subtree, so flagging `body` marks every element on the page as part of
an overlay and leaves nothing occluded — the exact inverse of what
perception is for.
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
           "LIFTED_POSITIONS", "ROOT_TAGS", "analyse", "candidates",
           "positioned"]

STACKED_POSITIONS = {"fixed", "absolute"}
#: Never candidates, whatever they are positioned as. The page is not on top
#: of itself, and a scroll-locked `body` is a page holding still, not a
#: dialog.
ROOT_TAGS = {"html", "body"}
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
# Measured against the corpus twice. On 45 pages (2026-09-20d) every blocker
# covered 1.000 and the largest non-blocker 0.234, with nothing between — a
# gap that flattered the number, because every overlay in that corpus was a
# full-screen modal. Five pages with partial-coverage overlays were added and
# the gap closed: a bottom sheet at 0.461, two side drawers at 0.312, a
# sticky banner at 0.369 (2026-09-20e).
#
# 0.30 still separates them, and now with almost no margin: the nearest real
# blocker is a drawer at **0.312**. That is 4% clear of the line rather than
# 200%, and the next corpus with a 0.28 drawer in it will move this number.
# EVALUATION.md, 2026-09-20e, has both distributions.
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


def positioned(document: Document, viewport: tuple[int, int]) -> list[Candidate]:
    """Every positioned, visible element, before any rule has judged it.

    `html` and `body` are left out — see `ROOT_TAGS` — and nothing else is.
    No z-index requirement and no coverage threshold: this is the population
    the rules select *from*, which is what a probe needs in order to measure
    what the rules exclude. `MIN_STACK_LEVEL` cannot be calibrated against a
    set that has already had `MIN_STACK_LEVEL` applied to it.
    """
    viewport_area = float(viewport[0] * viewport[1]) or 1.0
    found: list[Candidate] = []
    for node_index, style in document.styles.items():
        if not visible(style):
            continue
        position = style.get("position") or ""
        if position not in STACKED_POSITIONS and position not in LIFTED_POSITIONS:
            continue
        if document.tag(node_index) in ROOT_TAGS:
            continue
        bounds = document.bounds.get(node_index)
        if bounds is None:
            continue
        z_index = _int_or_none(style.get("z-index"))
        found.append(
            Candidate(
                node_index=node_index,
                backend_node_id=document.backend_id(node_index),
                # The whole box, unclipped. Occlusion is decided against this
                # and must not be: a sheet hanging off the bottom of the
                # screen still covers what is under its visible half.
                rect=bounds,
                coverage=_on_screen_area(bounds, viewport) / viewport_area,
                position=position,
                z_index=z_index,
                declared=(
                    position in STACKED_POSITIONS
                    and z_index is not None
                    and z_index >= MIN_STACK_LEVEL
                ),
                tag=document.tag(node_index),
            )
        )
    return found


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
    return [c for c in positioned(document, viewport) if c.declared or c.lifted]


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


def _on_screen_area(rect: Rect, viewport: tuple[int, int]) -> float:
    """How much of a box is inside the viewport, in square CSS pixels.

    The page is read at the top of its scroll, which is how every read in
    this project happens, so "inside the viewport" means inside
    `(0, 0, width, height)`. A box entirely below the fold returns 0.
    """
    x, y, width, height = rect
    if width <= 0 or height <= 0:
        return 0.0
    left = max(x, 0.0)
    top = max(y, 0.0)
    right = min(x + width, float(viewport[0]))
    bottom = min(y + height, float(viewport[1]))
    return max(right - left, 0.0) * max(bottom - top, 0.0)


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
