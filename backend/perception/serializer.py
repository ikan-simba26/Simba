"""Serialize a page's interactive elements from the accessibility tree.

Perception assigns every interactive element an integer id. The orchestrator
and the LLM refer to elements only by that id (`click(14)`), never by
selector (see CLAUDE.md).

This reads Chromium's accessibility tree over CDP rather than raw HTML. The
AX tree already computes each element's accessible name — a `<label for=...>`,
an `aria-label`, or the element's own text all collapse into one `name` — and
it drops elements that are hidden from users, neither of which comes free
from parsing markup.

Known gap: the AX tree does not distinguish a password input from a text
input; both are role `textbox` with identical properties. The credential
vault will need another way to spot password fields.
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


def serialize(page: Page) -> list[Element]:
    """Return the page's interactive elements, numbered in document order."""
    cdp = page.context.new_cdp_session(page)
    try:
        cdp.send("Accessibility.enable")
        nodes = cdp.send("Accessibility.getFullAXTree")["nodes"]
    finally:
        cdp.detach()

    elements: list[Element] = []
    for node in nodes:
        if node.get("ignored"):
            continue

        role = node.get("role", {}).get("value", "")
        action = INTERACTIVE_ROLES.get(role)
        if action is None:
            continue

        if _property(node, "disabled") is True:
            continue

        elements.append(
            Element(
                id=len(elements) + 1,
                role=role,
                label=node.get("name", {}).get("value", "").strip(),
                type=action,
            )
        )
    return elements


def _property(node: dict[str, Any], name: str) -> Any:
    for prop in node.get("properties", []):
        if prop.get("name") == name:
            return prop.get("value", {}).get("value")
    return None
