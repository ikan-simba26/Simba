"""Serialize a page into the two things a planner can use.

**Interactive elements.** Perception assigns every one an integer id. The
orchestrator and the LLM refer to elements only by that id (`click(14)`),
never by selector (see CLAUDE.md).

Structure comes from Chromium's accessibility tree over CDP rather than raw
HTML. The AX tree already computes each element's accessible name — a
`<label for=...>`, an `aria-label`, or the element's own text all collapse
into one `name` — and it drops elements that are hidden from users, neither
of which comes free from parsing markup.

The AX tree alone is not enough to act safely, though, in two separate ways.

  A password input and a text input are both role `textbox` with identical AX
  properties, so each element is also matched back to its DOM node (one
  `DOM.getDocument` call) for its tag name and `type` attribute. The
  credential vault needs that to know where it may inject a secret.

  And the AX tree does not know a control is a control when a framework
  renders it as a plain `li` or `div` with no role — it carries those as
  `StaticText`, indistinguishable from a paragraph. `interactivity.py` finds
  them from layout instead, and they arrive flagged `inferred` so nothing
  downstream mistakes a guess for a declaration.

**Readable content.** Headings, table rows paired with their column headers,
label/value pairs and prominent values, from `content.py`. Interactive
elements are what the page *offers*; content is what it *says*, and a task
whose goal is to read a number needs the second one. It travels as a separate
channel so a planner can never confuse the two.

All three readers work from one `DOMSnapshot.captureSnapshot`, parsed once.
"""

import os
from dataclasses import dataclass, field
from typing import Any

from playwright.async_api import Page as AsyncPage
from playwright.sync_api import Page

from backend.perception.content import Content, extract
from backend.perception.interactivity import (
    Inferred,
    find_inferred,
    inference_enabled,
)
from backend.perception.overlays import OverlayReport, analyse
from backend.perception.snapshot import COMPUTED_STYLES, Document, Rect, parse

# Frozen viewport, per CLAUDE.md — coverage is measured against it.
VIEWPORT = (1280, 800)

__all__ = [
    "COMPUTED_STYLES",
    "VIEWPORT",
    "Element",
    "PageView",
    "serialize",
    "serialize_async",
    "read_async",
    "read_content_async",
    "blockers_for_target_async",
    "build_elements",
    "index_dom",
    "is_dead_link",
    "overlay_detection_enabled",
]


def overlay_detection_enabled() -> bool:
    """Ablation switch. On unless SIMBA_OVERLAY_DETECTION says otherwise.

    Read per call rather than at import so a benchmark can flip conditions
    between processes without reaching into module state.
    """
    return os.environ.get("SIMBA_OVERLAY_DETECTION", "1").strip().lower() not in {
        "0",
        "false",
        "no",
    }


INTERACTIVE_ROLES: dict[str, str] = {
    "button": "click",
    "link": "click",
    "menuitem": "click",
    "tab": "click",
    "textbox": "type",
    "searchbox": "type",
    "spinbutton": "type",
    "checkbox": "check",
    "radio": "check",
    "switch": "check",
    "menuitemcheckbox": "check",
    "menuitemradio": "check",
    "combobox": "select",
    "listbox": "select",
}


@dataclass
class Element:
    id: int
    role: str
    label: str
    type: str
    tag: str
    input_type: str | None
    name: str | None = None  # the DOM name attribute, for routing vault values
    # Part of something covering the page — use these to dismiss it.
    overlay: bool = False
    # Sitting behind something covering the page. A click here cannot land.
    occluded: bool = False
    # A link that goes nowhere: href="#", javascript:void(0), or no target.
    dead_link: bool = False
    # The role was guessed from layout, not read from the page. A planner and
    # a log can tell the difference, which matters: a declared `option` is
    # what the author said it is, an inferred one is what it looks like.
    inferred: bool = False
    # Which rule fired — "cursor" or "group". Only set when inferred.
    inferred_from: str | None = None
    # A few words the label cannot carry: "previous month", "disabled". Empty
    # for an ordinary element, and the emptiness is meaningful — in a calendar
    # grid it is what marks a day as belonging to the month on screen.
    qualifier: str = ""
    # What the floating panel this element sits in says it is showing —
    # "2026 September" for a date picker, empty for a dropdown that needs no
    # heading because its options name themselves.
    panel: str = ""
    # What the field currently holds, for an input. Empty for everything else.
    # A form with values in it is not the same page as an empty one, and
    # without this perception cannot tell them apart.
    value: str = ""
    # Where the element is, in CSS pixels. Needed to ask whether something is
    # covering this particular element.
    rect: Rect | None = None
    backend_node_id: int = -1
    # How the backend gets from this id back to something it can act on, for
    # elements `get_by_role` cannot reach. Internal: never crosses to a
    # planner, never leaves the process.
    locator_hint: str | None = None

    @property
    def is_password(self) -> bool:
        return self.input_type == "password"


@dataclass
class PageView:
    """One read of a page: what it offers, and what it says."""

    elements: list[Element] = field(default_factory=list)
    content: Content = field(default_factory=Content)
    # The parsed snapshot this read was built from, when there was one. Kept
    # so a caller that needs the page itself — the estimator's features are
    # counted off the DOM, not off the element list — works from the same
    # moment as the elements above, rather than capturing a second snapshot
    # of a page that has moved on. None when the switches turned it off.
    document: Document | None = None


def _wants_snapshot() -> bool:
    return overlay_detection_enabled() or inference_enabled()


def serialize(page: Page, viewport: tuple[int, int] = VIEWPORT) -> list[Element]:
    """Return the page's interactive elements, numbered in document order."""
    return read(page, viewport).elements


def read(page: Page, viewport: tuple[int, int] = VIEWPORT) -> PageView:
    """Elements and content in one pass. The sync twin of `read_async`."""
    cdp = page.context.new_cdp_session(page)
    try:
        cdp.send("Accessibility.enable")
        ax_nodes = cdp.send("Accessibility.getFullAXTree")["nodes"]
        document = cdp.send("DOM.getDocument", {"depth": -1})["root"]
        snapshot = None
        ratio = 1.0
        if _wants_snapshot():
            cdp.send("DOMSnapshot.enable")
            snapshot = cdp.send(
                "DOMSnapshot.captureSnapshot", {"computedStyles": COMPUTED_STYLES}
            )
            ratio = pixel_ratio(cdp.send("Page.getLayoutMetrics"))
    finally:
        cdp.detach()

    return _assemble(ax_nodes, document, snapshot, viewport, ratio)


async def serialize_async(
    page: AsyncPage, viewport: tuple[int, int] = VIEWPORT
) -> list[Element]:
    """Async twin of `serialize`, for callers running under an event loop."""
    return (await read_async(page, viewport)).elements


async def read_async(
    page: AsyncPage, viewport: tuple[int, int] = VIEWPORT
) -> PageView:
    """Elements and content from one set of CDP calls."""
    cdp = await page.context.new_cdp_session(page)
    try:
        await cdp.send("Accessibility.enable")
        ax_nodes = (await cdp.send("Accessibility.getFullAXTree"))["nodes"]
        document = (await cdp.send("DOM.getDocument", {"depth": -1}))["root"]
        snapshot = None
        ratio = 1.0
        if _wants_snapshot():
            await cdp.send("DOMSnapshot.enable")
            snapshot = await cdp.send(
                "DOMSnapshot.captureSnapshot", {"computedStyles": COMPUTED_STYLES}
            )
            ratio = pixel_ratio(await cdp.send("Page.getLayoutMetrics"))
    finally:
        await cdp.detach()

    return _assemble(ax_nodes, document, snapshot, viewport, ratio)


async def read_content_async(
    page: AsyncPage, viewport: tuple[int, int] = VIEWPORT
) -> Content:
    """Just the readable content, for a caller that does not need elements."""
    return (await read_async(page, viewport)).content


async def blockers_for_target_async(
    page: AsyncPage, element: Element, viewport: tuple[int, int] = VIEWPORT
) -> OverlayReport:
    """What, if anything, is covering this specific element right now.

    Deliberately a fresh capture rather than a reuse of the last one. The
    thing this catches — a dropdown the previous step opened — appears
    *between* perceiving and acting, so a cached snapshot would be a snapshot
    from before the problem existed.
    """
    if not overlay_detection_enabled() or element.backend_node_id < 0:
        return OverlayReport()
    cdp = await page.context.new_cdp_session(page)
    try:
        await cdp.send("DOMSnapshot.enable")
        snapshot = await cdp.send(
            "DOMSnapshot.captureSnapshot", {"computedStyles": COMPUTED_STYLES}
        )
    finally:
        await cdp.detach()
    return analyse(snapshot, viewport, target=element.backend_node_id)


def pixel_ratio(metrics: dict[str, Any]) -> float:
    """How many device pixels the page is drawing per CSS pixel.

    From `Page.getLayoutMetrics`, which reports the same viewport twice — once
    in device pixels and once in CSS pixels — rather than from
    `window.devicePixelRatio`, so no JavaScript is run on the page being read.
    A snapshot's boxes are in the first of those units and everything else in
    this project is in the second.

    Returns 1.0 when the metrics are missing or nonsensical, which is what a
    headless browser reports anyway.
    """
    css = (metrics.get("cssLayoutViewport") or {}).get("clientWidth")
    device = (metrics.get("layoutViewport") or {}).get("clientWidth")
    if not css or not device:
        return 1.0
    ratio = float(device) / float(css)
    return ratio if ratio > 0 else 1.0


def _assemble(
    ax_nodes: list[dict[str, Any]],
    document: dict[str, Any],
    snapshot: dict[str, Any] | None,
    viewport: tuple[int, int],
    device_pixel_ratio: float = 1.0,
) -> PageView:
    parsed = parse(snapshot, device_pixel_ratio) if snapshot else None
    overlays = analyse(parsed, viewport) if parsed and overlay_detection_enabled() else None

    elements = build_elements(ax_nodes, index_dom(document), overlays, parsed)
    content = extract(parsed) if parsed else Content()
    return PageView(elements=elements, content=content, document=parsed)


def build_elements(
    ax_nodes: list[dict[str, Any]],
    dom: dict[int, tuple[str, dict[str, str]]],
    overlays: OverlayReport | None = None,
    parsed: Document | None = None,
) -> list[Element]:
    """Turn AX nodes, a DOM index and a parsed snapshot into numbered elements.

    Pure. Ids are assigned last, over the merged and ordered list, so an
    inferred element is numbered in the same sequence as a declared one and
    nothing downstream has to know which kind it got.
    """
    report = overlays or OverlayReport()
    declared: list[tuple[int, Element]] = []
    known: set[int] = set()

    for node in ax_nodes:
        if node.get("ignored"):
            continue

        role = node.get("role", {}).get("value", "")
        action = INTERACTIVE_ROLES.get(role)
        if action is None:
            continue

        if _property(node, "disabled") is True:
            continue

        backend_id = node.get("backendDOMNodeId", -1)
        tag, attributes = dom.get(backend_id, ("", {}))
        known.add(backend_id)
        node_index = (
            parsed.index_of_backend_id.get(backend_id, len(declared))
            if parsed
            else len(declared)
        )
        declared.append(
            (
                node_index,
                Element(
                    id=0,
                    role=role,
                    label=node.get("name", {}).get("value", "").strip(),
                    type=action,
                    tag=tag,
                    input_type=attributes.get("type"),
                    name=attributes.get("name"),
                    overlay=backend_id in report.overlay_ids,
                    occluded=backend_id in report.occluded_ids,
                    dead_link=is_dead_link(tag, attributes),
                    value=parsed.input_values.get(node_index, "") if parsed else "",
                    rect=parsed.bounds.get(node_index) if parsed else None,
                    backend_node_id=backend_id,
                ),
            )
        )

    merged = declared
    if parsed is not None and inference_enabled():
        viewport_size = (VIEWPORT[0], VIEWPORT[1])
        for found in find_inferred(parsed, viewport_size, known):
            merged.append((found.node_index, _from_inferred(found, report)))

    # Document order, so an inferred option lands among the elements it sits
    # between rather than in a block at the end. Stable, so declared elements
    # keep accessibility-tree order wherever the snapshot cannot place them.
    merged.sort(key=lambda pair: pair[0])

    elements: list[Element] = []
    for _, element in merged:
        element.id = len(elements) + 1
        elements.append(element)
    return elements


def _from_inferred(found: Inferred, report: OverlayReport) -> Element:
    return Element(
        id=0,
        role=found.role,
        label=found.label,
        type=found.action,
        tag=found.tag,
        input_type=None,
        name=None,
        overlay=found.backend_node_id in report.overlay_ids,
        occluded=found.backend_node_id in report.occluded_ids,
        dead_link=False,
        inferred=True,
        inferred_from=found.signal,
        qualifier=found.qualifier,
        panel=found.panel,
        rect=found.rect,
        backend_node_id=found.backend_node_id,
        locator_hint=found.css_path,
    )


def is_dead_link(tag: str, attributes: dict[str, str]) -> bool:
    """Whether an anchor goes nowhere.

    A cluttered portal's nav is mostly these: placeholder links that look like
    navigation and do nothing. A planner that cannot tell them apart from real
    ones spends steps discovering it the slow way, one dead click at a time.
    """
    if tag != "a":
        return False

    href = (attributes.get("href") or "").strip()
    if not href or href == "#":
        return True

    lowered = href.lower().replace(" ", "")
    if lowered.startswith("javascript:"):
        # javascript:void(0) and friends. A real handler may still be attached,
        # so this only says the href itself navigates nowhere.
        return lowered in {"javascript:void(0)", "javascript:void(0);", "javascript:;"}

    # "#section" is a real in-page jump; bare "#" is not.
    return False


def index_dom(root: dict[str, Any]) -> dict[int, tuple[str, dict[str, str]]]:
    """Map every DOM node's backend id to its (tag name, attributes)."""
    index: dict[int, tuple[str, dict[str, str]]] = {}
    stack = [root]
    while stack:
        node = stack.pop()
        backend_id = node.get("backendNodeId")
        if backend_id is not None:
            flat = node.get("attributes") or []
            index[backend_id] = (
                node.get("nodeName", "").lower(),
                dict(zip(flat[::2], flat[1::2])),
            )
        stack.extend(node.get("children", []))
    return index


def _property(node: dict[str, Any], name: str) -> Any:
    for prop in node.get("properties", []):
        if prop.get("name") == name:
            return prop.get("value", {}).get("value")
    return None
