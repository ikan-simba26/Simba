"""Find things that are visually covering the page, structurally.

Real sites put modals up as plain positioned `div`s with no `role="dialog"`
and no `aria-modal`, so the accessibility tree says nothing about them and a
planner sees the dialog's buttons as just more buttons in a long list. That
is how a run ends up clicking something underneath a modal and waiting for a
click that can never land.

So this ignores ARIA entirely and works from layout: an element that is
positioned, stacked above the page, and big enough to matter is treated as
blocking, and anything whose centre falls inside it is occluded.

Input is one `DOMSnapshot.captureSnapshot` — bounds, computed styles and
backend node ids for the whole document in a single CDP round trip.
"""

from dataclasses import dataclass, field

# The styles requested from CDP, in this order. Index-matched to layout.styles.
COMPUTED_STYLES = ["position", "z-index", "display", "visibility", "opacity"]

STACKED_POSITIONS = {"fixed", "absolute"}
# A z-index this far above the page is a deliberate "put me on top".
MIN_STACK_LEVEL = 5
# Fraction of the viewport an element must cover before it counts as blocking.
# A cookie banner or a toast covers little and blocks little; a modal backdrop
# covers most of the screen.
MIN_COVERAGE = 0.30


@dataclass
class Blocker:
    """One element that is covering the page."""

    backend_node_id: int
    rect: tuple[float, float, float, float]
    z_index: int
    coverage: float
    reason: str


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


def analyse(snapshot: dict, viewport: tuple[int, int]) -> OverlayReport:
    """Work out what is covering the page, and what is stuck behind it."""
    documents = snapshot.get("documents") or []
    if not documents:
        return OverlayReport()

    strings = snapshot.get("strings", [])
    document = documents[0]
    nodes = document.get("nodes", {})
    layout = document.get("layout", {})

    parents = nodes.get("parentIndex", [])
    backend_ids = nodes.get("backendNodeId", [])
    node_indexes = layout.get("nodeIndex", [])
    all_bounds = layout.get("bounds", [])
    all_styles = layout.get("styles", [])

    viewport_area = float(viewport[0] * viewport[1]) or 1.0

    boxes: dict[int, tuple[tuple[float, float, float, float], list[str]]] = {}
    for position, node_index in enumerate(node_indexes):
        bounds = tuple(all_bounds[position])
        styles = [_text(strings, s) for s in all_styles[position]]
        boxes[node_index] = (bounds, styles)

    blockers: list[Blocker] = []
    blocker_indexes: list[int] = []

    for node_index, (bounds, styles) in boxes.items():
        style = dict(zip(COMPUTED_STYLES, styles))
        if not _visible(style):
            continue
        if style.get("position") not in STACKED_POSITIONS:
            continue

        z_index = _int_or_none(style.get("z-index"))
        if z_index is None or z_index < MIN_STACK_LEVEL:
            continue

        _, _, width, height = bounds
        coverage = (width * height) / viewport_area
        if coverage < MIN_COVERAGE:
            continue

        blocker_indexes.append(node_index)
        blockers.append(
            Blocker(
                backend_node_id=_backend_id(backend_ids, node_index),
                rect=bounds,
                z_index=z_index,
                coverage=round(coverage, 3),
                reason=(
                    f"{style['position']} at z-index {z_index}, "
                    f"covering {round(coverage * 100)}% of the viewport"
                ),
            )
        )

    if not blockers:
        return OverlayReport()

    # Anything inside a blocker belongs to the overlay. So does a sibling that
    # is stacked at least as high — the common backdrop-plus-dialog pair, where
    # the dialog is not a child of the backdrop.
    children = _children_of(parents)
    overlay_indexes: set[int] = set()
    for blocker_index in blocker_indexes:
        overlay_indexes |= _subtree(children, blocker_index)
        for sibling in _siblings(parents, children, blocker_index):
            sibling_box = boxes.get(sibling)
            if sibling_box is None:
                continue
            style = dict(zip(COMPUTED_STYLES, sibling_box[1]))
            sibling_z = _int_or_none(style.get("z-index"))
            if (
                _visible(style)
                and style.get("position") in STACKED_POSITIONS
                and sibling_z is not None
                and sibling_z >= MIN_STACK_LEVEL
            ):
                overlay_indexes |= _subtree(children, sibling)

    occluded_indexes: set[int] = set()
    for node_index, (bounds, _styles) in boxes.items():
        if node_index in overlay_indexes:
            continue
        if any(_centre_inside(bounds, blocker.rect) for blocker in blockers):
            occluded_indexes.add(node_index)

    return OverlayReport(
        blockers=blockers,
        overlay_ids={_backend_id(backend_ids, i) for i in overlay_indexes},
        occluded_ids={_backend_id(backend_ids, i) for i in occluded_indexes},
    )


def _visible(style: dict[str, str]) -> bool:
    if style.get("display") == "none" or style.get("visibility") == "hidden":
        return False
    opacity = style.get("opacity")
    if opacity is not None:
        try:
            if float(opacity) == 0.0:
                return False
        except ValueError:
            pass
    return True


def _centre_inside(
    inner: tuple[float, float, float, float], outer: tuple[float, float, float, float]
) -> bool:
    """Occlusion by the standard a click cares about: is the middle covered."""
    x, y, width, height = inner
    if width <= 0 or height <= 0:
        return False
    cx, cy = x + width / 2, y + height / 2
    ox, oy, ow, oh = outer
    return ox <= cx <= ox + ow and oy <= cy <= oy + oh


def _children_of(parents: list[int]) -> dict[int, list[int]]:
    children: dict[int, list[int]] = {}
    for index, parent in enumerate(parents):
        children.setdefault(parent, []).append(index)
    return children


def _subtree(children: dict[int, list[int]], root: int) -> set[int]:
    """The node plus everything under it."""
    found = {root}
    queue = [root]
    while queue:
        for child in children.get(queue.pop(), ()):
            if child not in found:
                found.add(child)
                queue.append(child)
    return found


def _siblings(parents: list[int], children: dict[int, list[int]], node_index: int) -> list[int]:
    if node_index >= len(parents):
        return []
    return [i for i in children.get(parents[node_index], ()) if i != node_index]


def _int_or_none(value: str | None) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _text(strings: list[str], index: int) -> str:
    return strings[index] if 0 <= index < len(strings) else ""


def _backend_id(backend_ids: list[int], node_index: int) -> int:
    return backend_ids[node_index] if 0 <= node_index < len(backend_ids) else -1
