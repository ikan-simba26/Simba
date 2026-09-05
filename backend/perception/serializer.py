"""Serialize a page's interactive elements from the accessibility tree.

Perception assigns every interactive element an integer id. The orchestrator
and the LLM refer to elements only by that id (`click(14)`), never by
selector (see CLAUDE.md).

Structure comes from Chromium's accessibility tree over CDP rather than raw
HTML. The AX tree already computes each element's accessible name — a
`<label for=...>`, an `aria-label`, or the element's own text all collapse
into one `name` — and it drops elements that are hidden from users, neither
of which comes free from parsing markup.

The AX tree alone is not enough to act safely, though: a password input and a
text input are both role `textbox` with identical AX properties. So each
element is also matched back to its DOM node (one `DOM.getDocument` call) for
its tag name and `type` attribute. The credential vault needs that to know
where it may inject a secret.
"""

from dataclasses import dataclass
from typing import Any

from playwright.async_api import Page as AsyncPage
from playwright.sync_api import Page

from backend.perception.overlays import COMPUTED_STYLES, OverlayReport, analyse

# AX role -> the action the orchestrator can take on the element.
# Frozen viewport, per CLAUDE.md — coverage is measured against it.
VIEWPORT = (1280, 800)

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

    @property
    def is_password(self) -> bool:
        return self.input_type == "password"


def serialize(page: Page, viewport: tuple[int, int] = VIEWPORT) -> list[Element]:
    """Return the page's interactive elements, numbered in document order."""
    cdp = page.context.new_cdp_session(page)
    try:
        cdp.send("Accessibility.enable")
        ax_nodes = cdp.send("Accessibility.getFullAXTree")["nodes"]
        document = cdp.send("DOM.getDocument", {"depth": -1})["root"]
        cdp.send("DOMSnapshot.enable")
        snapshot = cdp.send(
            "DOMSnapshot.captureSnapshot", {"computedStyles": COMPUTED_STYLES}
        )
    finally:
        cdp.detach()

    return build_elements(ax_nodes, index_dom(document), analyse(snapshot, viewport))


async def serialize_async(
    page: AsyncPage, viewport: tuple[int, int] = VIEWPORT
) -> list[Element]:
    """Async twin of `serialize`, for callers running under an event loop."""
    cdp = await page.context.new_cdp_session(page)
    try:
        await cdp.send("Accessibility.enable")
        ax_nodes = (await cdp.send("Accessibility.getFullAXTree"))["nodes"]
        document = (await cdp.send("DOM.getDocument", {"depth": -1}))["root"]
        await cdp.send("DOMSnapshot.enable")
        snapshot = await cdp.send(
            "DOMSnapshot.captureSnapshot", {"computedStyles": COMPUTED_STYLES}
        )
    finally:
        await cdp.detach()

    return build_elements(ax_nodes, index_dom(document), analyse(snapshot, viewport))


def build_elements(
    ax_nodes: list[dict[str, Any]],
    dom: dict[int, tuple[str, dict[str, str]]],
    overlays: OverlayReport | None = None,
) -> list[Element]:
    """Turn AX nodes plus a DOM index into numbered elements. Pure."""
    elements: list[Element] = []
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
        report = overlays or OverlayReport()
        elements.append(
            Element(
                id=len(elements) + 1,
                role=role,
                label=node.get("name", {}).get("value", "").strip(),
                type=action,
                tag=tag,
                input_type=attributes.get("type"),
                name=attributes.get("name"),
                overlay=backend_id in report.overlay_ids,
                occluded=backend_id in report.occluded_ids,
                dead_link=is_dead_link(tag, attributes),
            )
        )
    return elements


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
