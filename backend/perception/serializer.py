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

from playwright.sync_api import Page

# AX role -> the action the orchestrator can take on the element.
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

    @property
    def is_password(self) -> bool:
        return self.input_type == "password"


def serialize(page: Page) -> list[Element]:
    """Return the page's interactive elements, numbered in document order."""
    cdp = page.context.new_cdp_session(page)
    try:
        cdp.send("Accessibility.enable")
        ax_nodes = cdp.send("Accessibility.getFullAXTree")["nodes"]
        document = cdp.send("DOM.getDocument", {"depth": -1})["root"]
    finally:
        cdp.detach()

    return build_elements(ax_nodes, index_dom(document))


def build_elements(
    ax_nodes: list[dict[str, Any]], dom: dict[int, tuple[str, dict[str, str]]]
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

        tag, attributes = dom.get(node.get("backendDOMNodeId", -1), ("", {}))
        elements.append(
            Element(
                id=len(elements) + 1,
                role=role,
                label=node.get("name", {}).get("value", "").strip(),
                type=action,
                tag=tag,
                input_type=attributes.get("type"),
            )
        )
    return elements


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
