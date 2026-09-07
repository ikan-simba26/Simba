"""Find the controls the accessibility tree does not know are controls.

The accessibility tree is the right primary source and it has one blind spot
that matters enormously in practice: a component framework can render a
perfectly ordinary control as a plain `li`, `div` or `span` with no role, no
tabindex and no aria, and the tree then carries it as `StaticText` — the same
thing it carries a paragraph as. Nothing downstream can tell a choice from a
sentence.

This is not a corner case. The live railways search opens a station list of
six `<li class="el-select-dropdown__item"><span>LAHORE CANTT</span></li>`
with no ARIA anywhere on them. Perception reported eighteen elements before
the list opened and eighteen after, on a page showing six new choices, and
that alone made the flow impossible (EVALUATION.md, 2026-09-07). Element UI
and its successors sit behind a very large number of enterprise and
government single-page apps.

So: read layout instead of semantics, the same move overlay detection makes.

  **Primary signal — `cursor: pointer`.** The one thing a framework cannot
  skip, because it is what tells the *user* the thing is clickable. If it
  looks clickable to a person it carries this, and if it does not carry it,
  a sighted user could not find it either.

  **Secondary signal — a repeated sibling group in a floating panel.** Three
  or more siblings sharing a tag and a class, inside an absolutely or fixed
  positioned ancestor. That is the shape of a dropdown, a menu or a popover
  list, and it catches members that inherit no pointer cursor of their own.

Everything found here is flagged `inferred`. A planner and a log can always
tell a role the page declared from a role we guessed at, because those two
things deserve different amounts of trust and collapsing them would hide
exactly the uncertainty worth surfacing.
"""

import os
from dataclasses import dataclass

from backend.perception.snapshot import Document, Rect, visible

# Tags that are already controls. If one of these turns up under the pointer
# rule it is either in the accessibility tree already (and gets dropped as a
# duplicate) or it is broken in a way this module should not paper over.
NATIVE_CONTROLS = {"a", "button", "input", "select", "textarea", "option", "label"}

# Containers that make their contents a *list of choices* rather than a set of
# unrelated buttons. Drives the inferred role, which is the only thing a plan
# has to aim at.
CHOICE_CONTAINERS = {"ul", "ol", "select", "datalist", "menu"}

# How many same-tag, same-class siblings before a group reads as a list rather
# than a coincidence. Two is common by accident; three is a pattern.
MIN_GROUP = 3
# A control's label. Longer than this and it is prose inside a clickable
# wrapper, not the name of a thing to click.
MAX_LABEL = 120
# A pointer region larger than this fraction of the viewport is a layout
# artifact — a clickable backdrop, an overlay catcher — not a control.
MAX_AREA_SHARE = 0.5

# What a planner may do with each inferred role. Deliberately separate from
# the serializer's INTERACTIVE_ROLES: adding "option" there would make every
# native <select>'s options into top-level elements on every page.
INFERRED_ACTIONS = {"option": "click", "menuitem": "click", "button": "click"}


@dataclass(frozen=True)
class Inferred:
    """A control found by layout rather than by role."""

    backend_node_id: int
    node_index: int
    tag: str
    label: str
    role: str
    rect: Rect
    signal: str  # "cursor" or "group" — which rule fired
    css_path: str

    @property
    def action(self) -> str:
        return INFERRED_ACTIONS.get(self.role, "click")


def inference_enabled() -> bool:
    """Ablation switch, matching `overlay_detection_enabled`.

    Read per call rather than at import so a benchmark can flip conditions
    between processes without reaching into module state.
    """
    return os.environ.get("SIMBA_INFERRED_ROLES", "1").strip().lower() not in {
        "0",
        "false",
        "no",
    }


def find_inferred(
    document: Document | None,
    viewport: tuple[int, int],
    known_backend_ids: set[int],
) -> list[Inferred]:
    """Controls the accessibility tree missed, in document order.

    `known_backend_ids` are the nodes the AX tree already gave us. They are
    needed for more than deduplication: a `div` wrapping a real `<button>`
    inherits nothing but *contains* something already known, and reporting
    both would offer a planner two ids for one control.
    """
    if document is None:
        return []

    viewport_area = float(viewport[0] * viewport[1]) or 1.0
    pointer = _pointer_nodes(document)
    grouped = _group_nodes(document)

    surviving: list[int] = []
    for node_index in sorted(pointer | grouped):
        if document.backend_id(node_index) in known_backend_ids:
            continue

        # An ancestor already carrying the pointer cursor is the real control;
        # `cursor` inherits, so the <span> inside a clickable <li> looks
        # identical to the <li> and is never the thing to click.
        if any(a in pointer for a in document.ancestors(node_index)):
            continue

        # A wrapper around a control the AX tree already named.
        if any(
            document.backend_id(d) in known_backend_ids
            for d in document.subtree(node_index)
            if d != node_index
        ):
            continue

        surviving.append(node_index)

    # A candidate that still contains another candidate is a container, and
    # the thing inside it is the control. The rule above only removes
    # descendants that inherited a pointer cursor, which leaves the group
    # signal's containers standing: the live date picker matches both a row
    # of day cells and each cell in it, and without this it offers a planner
    # a "30 31 1 2 3 4" element sitting on top of the seven real ones.
    remaining = set(surviving)
    contains_another = {
        node_index
        for node_index in surviving
        if any(d != node_index and d in remaining for d in document.subtree(node_index))
    }

    found: list[Inferred] = []
    for node_index in surviving:
        if node_index in contains_another:
            continue

        bounds = document.bounds.get(node_index)
        if bounds is None:
            continue
        _, _, width, height = bounds
        if width <= 0 or height <= 0:
            continue
        if (width * height) / viewport_area > MAX_AREA_SHARE:
            continue

        label = _label_for(document, node_index)
        # An inferred control with no name is not addressable — a plan can
        # only aim at a role and a label, and "" matches everything. Emitting
        # it would add noise a planner cannot use. This is a real gap for
        # icon-only controls; it is recorded in STATUS.md rather than hidden.
        if not label:
            continue

        found.append(
            Inferred(
                backend_node_id=document.backend_id(node_index),
                node_index=node_index,
                tag=document.tag(node_index),
                label=label,
                role=_role_for(document, node_index, node_index in grouped),
                rect=bounds,
                signal="cursor" if node_index in pointer else "group",
                css_path=document.css_path(node_index),
            )
        )
    return found


def _pointer_nodes(document: Document) -> set[int]:
    """Visible element nodes whose computed cursor says "you can click me"."""
    found: set[int] = set()
    for node_index, style in document.styles.items():
        if style.get("cursor") != "pointer":
            continue
        if not document.is_element(node_index) or not visible(style):
            continue
        found.add(node_index)
    return found


def _group_nodes(document: Document) -> set[int]:
    """Members of a repeated sibling group inside a floating panel.

    Grouped by parent, tag and class, so a dropdown's items are one group and
    the unrelated `div`s around them are not. The floating-ancestor test is
    what keeps this from firing on every nav list and every table body: a
    dropdown, a menu and a popover are positioned out of flow; a nav is not.
    """
    groups: dict[tuple[int, str, str], list[int]] = {}
    for node_index in range(len(document)):
        if not document.is_element(node_index):
            continue
        parent = document.parents[node_index]
        if parent < 0:
            continue
        key = (
            parent,
            document.tag(node_index),
            document.attribute(node_index, "class").strip(),
        )
        if not key[2]:
            continue
        groups.setdefault(key, []).append(node_index)

    found: set[int] = set()
    for members in groups.values():
        if len(members) < MIN_GROUP:
            continue
        if not _floats(document, members[0]):
            continue
        for member in members:
            style = document.styles.get(member)
            if style is not None and visible(style):
                found.add(member)
    return found


def _floats(document: Document, node_index: int) -> bool:
    """Whether the node sits inside an out-of-flow positioned container.

    `relative` deliberately does not count. Half the page is relatively
    positioned on a typical layout, and treating that as a floating panel
    turns this rule into "every list on the page".
    """
    for ancestor in document.ancestors(node_index):
        position = (document.styles.get(ancestor) or {}).get("position")
        if position in {"absolute", "fixed"}:
            return True
    return False


def _label_for(document: Document, node_index: int) -> str:
    """The name this control would go by, in the order a person would read it."""
    text = document.text_of(node_index, limit=MAX_LABEL + 1)
    if text and len(text) <= MAX_LABEL:
        return text
    for attribute in ("aria-label", "title", "alt", "placeholder"):
        value = document.attribute(node_index, attribute).strip()
        if value:
            return value[:MAX_LABEL]
    return ""


def _role_for(document: Document, node_index: int, in_group: bool) -> str:
    """Guess at what kind of control this is. Always reported as a guess.

    Deliberately decided by *where* the element is, never by how many
    same-class siblings it happens to have. An earlier version took the group
    signal into account and the role came out unstable: the live date
    picker's day cells carry classes like `available`, `prev-month available`
    and `today available`, so how many siblings share a cell's class depends
    on where in the month it falls. The 15th of one month was an `option` and
    the 15th of another a `button`, from identical markup. A plan has to name
    the role it is aiming at, so a role that moves with the calendar is not
    usable — predictable beats nuanced here.

    So: inside a floating panel, everything is one of a set of choices —
    a dropdown item, a menu entry, a day in a calendar. Elsewhere, a list
    item is a menu item and anything else is a button.
    """
    tag = document.tag(node_index)
    if tag in NATIVE_CONTROLS:
        return "button"
    if _floats(document, node_index):
        return "option"
    if tag == "li" or document.tag(document.parents[node_index]) in CHOICE_CONTAINERS:
        return "menuitem"
    return "button"
