"""One parse of a `DOMSnapshot.captureSnapshot` payload, shared by its readers.

Three things now read the same snapshot — overlay detection, non-semantic
interactivity, and content extraction — and each of them needs the same
awkward reassembly first. The CDP payload is column-oriented and
string-interned: `nodes.nodeName` is a list of indexes into `strings`,
`layout` covers only the nodes that actually generate a box, and the tree
exists only as a `parentIndex` array. Every reader wanting its own copy of
that unpacking is how the three of them drift apart.

`parse` does it once and hands back something with names on it. It is pure:
give it the dict CDP returned and it touches nothing else.

Only the first document is read. Iframes arrive as further entries in
`documents` and are not handled — see STATUS.md.
"""

from dataclasses import dataclass, field
from typing import Any

# The styles requested from CDP. Index-matched to `layout.styles`, so the
# order here is the order values come back in, and appending is safe.
#
#   position/z-index/display/visibility/opacity  overlays.py
#   cursor                                       interactivity.py
#   font-size/font-weight                        content.py
COMPUTED_STYLES = [
    "position",
    "z-index",
    "display",
    "visibility",
    "opacity",
    "cursor",
    "font-size",
    "font-weight",
]

ELEMENT_NODE = 1
TEXT_NODE = 3

Rect = tuple[float, float, float, float]


@dataclass
class Document:
    """A snapshot's first document, unpacked and indexed.

    Everything is keyed by *node index* — the node's position in the flat
    `nodes` arrays — because that is the only key the snapshot uses
    internally. `backend_id` converts to the id the rest of perception and
    the accessibility tree speak in.

    **`bounds` are CSS pixels**, converted on the way in by `parse`. CDP sends
    them in device pixels, which is the same thing only while the device pixel
    ratio is 1 — true headless, false in the Electron host on a display at
    150%, where the same `<h1>` measured `(384, 180, 1152, 48)` against
    `(256, 120, 768, 32)` (EVALUATION.md, 2026-09-19b). Every other length in
    this project is CSS pixels: the frozen 1280x800 viewport, a coverage
    fraction, a text density. One of them had to convert and this is the one,
    because it is the only place the numbers enter.
    """

    strings: list[str]
    parents: list[int]
    node_types: list[int]
    node_names: list[str]
    node_values: list[str]
    backend_ids: list[int]
    attributes: list[dict[str, str]]
    bounds: dict[int, Rect] = field(default_factory=dict)
    styles: dict[int, dict[str, str]] = field(default_factory=dict)
    children: dict[int, list[int]] = field(default_factory=dict)
    index_of_backend_id: dict[int, int] = field(default_factory=dict)
    # What each input currently holds. CDP sends it with the snapshot, so
    # knowing it costs nothing extra, and without it perception cannot see
    # the one thing a filled form has that an empty one does not.
    input_values: dict[int, str] = field(default_factory=dict)
    #: What `bounds` were divided by to get CSS pixels. Recorded so a reader
    #: can tell a page that was read at 1 from one read at 1.5, and so a test
    #: can assert the conversion happened rather than assuming it.
    device_pixel_ratio: float = 1.0
    #: Where the page was scrolled to when the snapshot was taken, in CSS
    #: pixels. Every box in `bounds` is in *document* coordinates, so the
    #: visible viewport is `(scroll[0], scroll[1], width, height)`, not
    #: `(0, 0, width, height)`. A driven read is almost never at the top: a
    #: click on a button half-way down scrolls it into view first. CDP sends
    #: this in device pixels, like the boxes — measured in the host at 1.5,
    #: scrolled to 1234 CSS pixels, it reported 1851 (EVALUATION.md,
    #: 2026-09-20e) — so it is converted here with them.
    scroll: tuple[float, float] = (0.0, 0.0)

    def __len__(self) -> int:
        return len(self.parents)

    def backend_id(self, node_index: int) -> int:
        if 0 <= node_index < len(self.backend_ids):
            return self.backend_ids[node_index]
        return -1

    def tag(self, node_index: int) -> str:
        if 0 <= node_index < len(self.node_names):
            return self.node_names[node_index].lower()
        return ""

    def is_element(self, node_index: int) -> bool:
        return (
            0 <= node_index < len(self.node_types)
            and self.node_types[node_index] == ELEMENT_NODE
        )

    def attribute(self, node_index: int, name: str) -> str:
        if 0 <= node_index < len(self.attributes):
            return self.attributes[node_index].get(name, "")
        return ""

    def ancestors(self, node_index: int) -> list[int]:
        """From the node's parent up to the root. Guards against a cycle."""
        chain: list[int] = []
        seen = {node_index}
        current = self.parents[node_index] if node_index < len(self.parents) else -1
        while current >= 0 and current not in seen:
            chain.append(current)
            seen.add(current)
            current = self.parents[current] if current < len(self.parents) else -1
        return chain

    def subtree(self, root: int) -> set[int]:
        """The node plus every descendant."""
        found = {root}
        queue = [root]
        while queue:
            for child in self.children.get(queue.pop(), ()):
                if child not in found:
                    found.add(child)
                    queue.append(child)
        return found

    def text_of(self, node_index: int, limit: int = 400) -> str:
        """Visible text under a node, whitespace-collapsed.

        Text from a `display: none` subtree is skipped: it is in the DOM and
        not on the screen, and a label nobody can read is worse than no label
        because it looks addressable.
        """
        pieces: list[str] = []
        stack = [node_index]
        while stack and sum(len(p) for p in pieces) < limit:
            current = stack.pop()
            style = self.styles.get(current)
            if current != node_index and style and not visible(style):
                continue
            if self.node_types[current] == TEXT_NODE:
                pieces.append(self.node_values[current])
                continue
            stack.extend(reversed(self.children.get(current, [])))
        return " ".join(" ".join(pieces).split())[:limit]

    def css_path(self, node_index: int) -> str:
        """A structural path back to this node, for the backend's own use.

        Elements the accessibility tree never named cannot be reached with
        `get_by_role`, and inventing a selector for a *planner* to emit is
        exactly what CLAUDE.md forbids. This is the other half of that rule:
        the planner says `click(14)`, and the backend turns 14 into something
        it can act on. The path is recomputed on every perceive, so it is only
        ever as stale as the perceive that produced it.
        """
        steps: list[str] = []
        current = node_index
        while current >= 0 and self.is_element(current):
            tag = self.tag(current)
            if tag == "html":
                steps.append("html")
                break
            parent = self.parents[current] if current < len(self.parents) else -1
            position = 1
            for sibling in self.children.get(parent, ()):
                if sibling == current:
                    break
                if self.is_element(sibling) and self.tag(sibling) == tag:
                    position += 1
            steps.append(f"{tag}:nth-of-type({position})")
            current = parent
        return " > ".join(reversed(steps))


#: What a password field holds, as far as anything reading the page knows: that
#: it holds something, never what. Fixed length, so not even how long it is.
SECRET_MASK = "********"


def _readable(value: str, attributes: dict) -> str:
    """A field's value as everything downstream of the snapshot sees it.

    CDP reads every input's live value, a password field's included, so after
    a password was typed the secret was in `Document.input_values`, in every
    `Element.value` and in every `Snapshot` built from them (found 2026-10-03).
    Nothing sent it on — the model's page shows no values, and the loop's own
    checks skip passwords — but every new reader of a value was one line from
    leaking it. A password field reads as the mask when it holds anything and
    empty when it does not, so "filled or not" stays visible and the secret
    never enters perception at all.
    """
    if str(attributes.get("type", "")).lower() == "password":
        return SECRET_MASK if value else ""
    return value


def parse(
    snapshot: dict[str, Any] | None, device_pixel_ratio: float = 1.0
) -> Document | None:
    """Unpack the first document of a captureSnapshot payload, or None.

    `device_pixel_ratio` is what the page reported when the snapshot was
    taken; every box is divided by it, so callers get CSS pixels and none of
    them has to remember a ratio. `serializer.read` supplies it from the page
    itself. The default of 1 is what a headless browser reports, and is also
    what a hand-built document in a test wants.
    """
    if not snapshot:
        return None
    documents = snapshot.get("documents") or []
    if not documents:
        return None

    strings: list[str] = snapshot.get("strings", [])
    document = documents[0]
    nodes = document.get("nodes", {})
    layout = document.get("layout", {})

    parents: list[int] = list(nodes.get("parentIndex", []))
    count = len(parents)

    def text(index: int) -> str:
        return strings[index] if 0 <= index < len(strings) else ""

    node_names = [text(i) for i in nodes.get("nodeName", [])]
    node_values = [text(i) for i in nodes.get("nodeValue", [])]
    node_types = list(nodes.get("nodeType", []))
    backend_ids = list(nodes.get("backendNodeId", []))

    attributes: list[dict[str, str]] = []
    for flat in nodes.get("attributes", []):
        names = [text(i) for i in flat[::2]]
        values = [text(i) for i in flat[1::2]]
        attributes.append(dict(zip(names, values)))

    # The column arrays are meant to be the same length; a short one would
    # otherwise surface as an IndexError somewhere unrelated.
    for column in (node_names, node_values, node_types, backend_ids, attributes):
        while len(column) < count:
            column.append("" if column is not node_types else 0)  # type: ignore[arg-type]

    bounds: dict[int, Rect] = {}
    styles: dict[int, dict[str, str]] = {}
    # A ratio of 0 would mean dividing every box by nothing; treat an absent
    # or nonsensical value as 1 rather than losing the layout entirely.
    scale = float(device_pixel_ratio) if device_pixel_ratio else 1.0
    for position, node_index in enumerate(layout.get("nodeIndex", [])):
        raw_bounds = layout.get("bounds", [])
        raw_styles = layout.get("styles", [])
        if position < len(raw_bounds):
            box = raw_bounds[position]
            bounds[node_index] = (box[0] / scale, box[1] / scale,
                                  box[2] / scale, box[3] / scale)
        if position < len(raw_styles):
            styles[node_index] = dict(
                zip(COMPUTED_STYLES, [text(s) for s in raw_styles[position]])
            )

    children: dict[int, list[int]] = {}
    for index, parent in enumerate(parents):
        children.setdefault(parent, []).append(index)

    # RareStringData: parallel `index` and `value` arrays naming only the
    # nodes that have one, rather than a full-length column of mostly blanks.
    rare = nodes.get("inputValue") or {}
    input_values = {
        node_index: _readable(text(string_index), attributes[node_index]
                              if node_index < len(attributes) else {})
        for node_index, string_index in zip(
            rare.get("index", []), rare.get("value", [])
        )
    }

    return Document(
        strings=strings,
        parents=parents,
        node_types=node_types,
        node_names=node_names,
        node_values=node_values,
        backend_ids=backend_ids,
        attributes=attributes,
        bounds=bounds,
        styles=styles,
        children=children,
        index_of_backend_id={b: i for i, b in enumerate(backend_ids)},
        input_values=input_values,
        device_pixel_ratio=scale,
        scroll=(float(document.get("scrollOffsetX", 0) or 0) / scale,
                float(document.get("scrollOffsetY", 0) or 0) / scale),
    )


def visible(style: dict[str, str]) -> bool:
    """Whether a computed style leaves the element on the screen at all."""
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


def overlaps(a: Rect, b: Rect) -> bool:
    """Whether two rects share any area at all."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    if aw <= 0 or ah <= 0 or bw <= 0 or bh <= 0:
        return False
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def centre_inside(inner: Rect, outer: Rect) -> bool:
    """Occlusion by the standard a click cares about: is the middle covered."""
    x, y, width, height = inner
    if width <= 0 or height <= 0:
        return False
    cx, cy = x + width / 2, y + height / 2
    ox, oy, ow, oh = outer
    return ox <= cx <= ox + ow and oy <= cy <= oy + oh
