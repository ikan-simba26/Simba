"""Inferred interactivity: the controls the accessibility tree calls text.

The live case these exist for is at the bottom of the file. Everything above
it is the shape of the problem, pinned down without a network.
"""

import os

import pytest
from playwright.sync_api import Page

from backend.perception.interactivity import MIN_GROUP, find_inferred
from backend.perception.serializer import read, serialize
from backend.perception.snapshot import COMPUTED_STYLES, parse

VIEWPORT = (1280, 800)


# --- a snapshot builder, so the unit tests speak CDP's dialect ---------------


class Builder:
    """Build a `DOMSnapshot.captureSnapshot` payload by hand.

    Column arrays and interned strings, the way CDP sends them. A friendlier
    fixture would test a shape the real input never takes.
    """

    def __init__(self) -> None:
        self.strings: list[str] = [""]
        self.parents: list[int] = []
        self.names: list[int] = []
        self.values: list[int] = []
        self.types: list[int] = []
        self.backend: list[int] = []
        self.attributes: list[list[int]] = []
        self.bounds: dict[int, list[float]] = {}
        self.styles: dict[int, list[int]] = {}

    def _s(self, text: str) -> int:
        if text not in self.strings:
            self.strings.append(text)
        return self.strings.index(text)

    def node(
        self,
        parent: int,
        tag: str,
        *,
        attrs: dict[str, str] | None = None,
        style: dict[str, str] | None = None,
        rect: tuple[float, float, float, float] = (0, 0, 100, 20),
        text: str = "",
    ) -> int:
        index = len(self.parents)
        self.parents.append(parent)
        self.names.append(self._s(tag.upper()))
        self.values.append(0)
        self.types.append(1)
        self.backend.append(1000 + index)
        flat: list[int] = []
        for name, value in (attrs or {}).items():
            flat += [self._s(name), self._s(value)]
        self.attributes.append(flat)

        full = {"position": "static", "display": "block", "opacity": "1"}
        full.update(style or {})
        self.bounds[index] = list(rect)
        self.styles[index] = [self._s(full.get(key, "")) for key in COMPUTED_STYLES]

        if text:
            child = len(self.parents)
            self.parents.append(index)
            self.names.append(self._s("#text"))
            self.values.append(self._s(text))
            self.types.append(3)
            self.backend.append(1000 + child)
            self.attributes.append([])
        return index

    def build(self) -> dict:
        laid_out = sorted(self.styles)
        return {
            "strings": self.strings,
            "documents": [
                {
                    "nodes": {
                        "parentIndex": self.parents,
                        "nodeName": self.names,
                        "nodeValue": self.values,
                        "nodeType": self.types,
                        "backendNodeId": self.backend,
                        "attributes": self.attributes,
                    },
                    "layout": {
                        "nodeIndex": laid_out,
                        "bounds": [self.bounds[i] for i in laid_out],
                        "styles": [self.styles[i] for i in laid_out],
                    },
                }
            ],
        }


POINTER = {"cursor": "pointer"}
FLOATING = {"position": "absolute", "z-index": "2000"}


def dropdown(pointer_on_items: bool = True, floating: bool = True) -> dict:
    """The shape the live railways station list actually has."""
    b = Builder()
    root = b.node(-1, "html")
    body = b.node(root, "body")
    panel = b.node(body, "div", attrs={"class": "el-select-dropdown"},
                   style=FLOATING if floating else {}, rect=(312, 220, 215, 204))
    listing = b.node(panel, "ul", attrs={"class": "el-scrollbar__view"})
    for offset, station in enumerate(("LAHORE JN.", "LAHORE CANTT", "KOT NAJIBULLAH")):
        item = b.node(
            listing, "li",
            attrs={"class": "el-select-dropdown__item"},
            style=POINTER if pointer_on_items else {},
            rect=(312, 224 + offset * 34, 215, 34),
        )
        # The text is in a span, inheriting the pointer cursor from the li.
        b.node(item, "span", style=POINTER if pointer_on_items else {},
               rect=(316, 228 + offset * 34, 200, 26), text=station)
    return b.build()


def infer(snapshot: dict, known: set[int] | None = None):
    return find_inferred(parse(snapshot), VIEWPORT, known or set())


# --- the primary signal -----------------------------------------------------


def test_a_pointer_cursor_makes_a_plain_li_a_control() -> None:
    found = infer(dropdown())

    assert [f.label for f in found] == [
        "LAHORE JN.", "LAHORE CANTT", "KOT NAJIBULLAH",
    ]
    assert all(f.role == "option" for f in found)
    assert all(f.signal == "cursor" for f in found)
    assert all(f.tag == "li" for f in found)


def test_the_span_inside_a_clickable_li_is_not_a_second_control() -> None:
    """`cursor` inherits, so the span looks identical to its parent.

    Reporting both would offer a planner two ids for one choice, and the
    inner one is never the thing a person clicks.
    """
    found = infer(dropdown())

    assert len(found) == 3, [(f.tag, f.label) for f in found]


def test_an_inferred_control_carries_a_path_back_to_itself() -> None:
    found = infer(dropdown())

    path = found[1].css_path
    assert path.startswith("html > ")
    assert path.endswith("li:nth-of-type(2)")


def test_an_unlabelled_pointer_region_is_left_out() -> None:
    """A control a plan cannot name is a control a plan cannot use."""
    b = Builder()
    root = b.node(-1, "html")
    body = b.node(root, "body")
    b.node(body, "div", style=POINTER, rect=(0, 0, 40, 40))

    assert infer(b.build()) == []


def test_a_full_screen_pointer_region_is_a_backdrop_not_a_control() -> None:
    b = Builder()
    root = b.node(-1, "html")
    body = b.node(root, "body")
    b.node(body, "div", style=POINTER, rect=(0, 0, 1280, 800), text="dismiss")

    assert infer(b.build()) == []


def test_a_wrapper_around_a_known_control_is_not_reported_twice() -> None:
    b = Builder()
    root = b.node(-1, "html")
    body = b.node(root, "body")
    wrapper = b.node(body, "div", style=POINTER, rect=(0, 0, 120, 40))
    inner = b.node(wrapper, "button", style=POINTER, rect=(4, 4, 112, 32), text="Search")

    known = {b.backend[inner]}
    assert infer(b.build(), known) == []


# --- the secondary signal ---------------------------------------------------


def test_a_repeated_sibling_group_in_a_floating_panel_is_a_list_of_choices() -> None:
    """Members that carry no pointer cursor of their own still get found."""
    found = infer(dropdown(pointer_on_items=False))

    assert [f.label for f in found] == [
        "LAHORE JN.", "LAHORE CANTT", "KOT NAJIBULLAH",
    ]
    assert all(f.signal == "group" for f in found)


def test_the_same_group_in_normal_flow_is_just_a_list() -> None:
    """Otherwise every nav and every table body becomes a set of controls."""
    assert infer(dropdown(pointer_on_items=False, floating=False)) == []


def test_a_group_smaller_than_the_threshold_is_a_coincidence() -> None:
    b = Builder()
    root = b.node(-1, "html")
    body = b.node(root, "body")
    panel = b.node(body, "div", style=FLOATING)
    for index in range(MIN_GROUP - 1):
        b.node(panel, "li", attrs={"class": "item"}, text=f"item {index}")

    assert infer(b.build()) == []


def test_a_row_of_cells_yields_the_cells_not_the_row() -> None:
    """The live date picker matches both, and only the cells are clickable.

    Without this a planner is offered a "30 31 1 2 3 4" element sitting on
    top of the seven real day cells, and picking a date means picking the row.
    """
    b = Builder()
    root = b.node(-1, "html")
    body = b.node(root, "body")
    table = b.node(body, "div", style=FLOATING)
    for week in range(MIN_GROUP):
        row = b.node(table, "tr", attrs={"class": "el-date-table__row"})
        for day in range(3):
            b.node(row, "td", attrs={"class": "available"},
                   rect=(day * 32, week * 32, 30, 30), text=str(week * 3 + day + 1))

    found = infer(b.build())

    assert [f.label for f in found] == [str(n) for n in range(1, 10)]
    assert all(f.tag == "td" for f in found)


# --- against the replicas: the cost of being wrong --------------------------


def test_semantic_markup_produces_no_inferred_elements(replica: str, page: Page) -> None:
    """The replicas are written properly, so there is nothing here to infer.

    This is the false-positive test. Inference that fires on a well-built page
    would bury every real control in noise, and the registration replica has
    49 of them to bury.
    """
    page.goto(replica + "/")

    elements = serialize(page)

    assert elements, "sanity: the page has controls"
    assert [e for e in elements if not e.inferred]
    assert not [e for e in elements if e.inferred]


def test_the_ablation_switch_turns_inference_off(monkeypatch, replica: str, page: Page) -> None:
    monkeypatch.setenv("SIMBA_INFERRED_ROLES", "0")
    page.goto(replica + "/")

    assert not [e for e in serialize(page) if e.inferred]


# --- the live site ----------------------------------------------------------
#
# Off by default, and run with SIMBA_LIVE_TESTS=1. Not because it is unsound,
# but because it is somebody's public service and a test that fires on every
# `pytest` invocation would be pointing a loop at it all day.

LIVE = pytest.mark.skipif(
    os.environ.get("SIMBA_LIVE_TESTS", "").strip() not in {"1", "true", "yes"},
    reason="live-site test; set SIMBA_LIVE_TESTS=1 to run it",
)

RAILWAYS = "https://www.pakrailways.gov.pk/train"
USER_AGENT = (
    "SIMBA-screener/0.1 (final-year university project; read-only; "
    "+https://github.com/ikan-simba26/Simba)"
)
STATIONS = {
    "DERA ALLAHYAR",
    "LAHORE JN.",
    "LAHORE CANTT",
    "TANDO ALLAH YAR",
    "KILLAABDULLAH",
    "KOT NAJIBULLAH",
}


@LIVE
def test_the_live_railways_dropdown_reaches_perception(playwright_instance) -> None:
    """The finding that started all of this, as an assertion.

    Typing `LAH` into From puts six stations on the screen. Before inference
    the serialized element count went 18 -> 18: six choices visible to a
    person and none at all to the loop, which made the flow impossible.

    Nothing about the page is modified to make this pass. The page is the
    test — `li.el-select-dropdown__item` with no role, no tabindex and no
    aria, reaching the accessibility tree as `StaticText` and nothing more.
    """
    browser = playwright_instance.chromium.launch()
    try:
        context = browser.new_context(
            user_agent=USER_AGENT, viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        page.goto(RAILWAYS, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        before = read(page).elements
        assert not [e for e in before if e.inferred], "nothing is open yet"

        origin = page.get_by_role("textbox", name="From", exact=True)
        origin.click()
        page.wait_for_timeout(400)
        origin.press_sequentially("LAH", delay=110)
        page.wait_for_timeout(1800)

        after = read(page).elements
        options = [e for e in after if e.inferred and e.role == "option"]

        assert len(after) == len(before) + 6, (
            f"{len(before)} elements before, {len(after)} after; "
            f"six stations are on the screen"
        )
        assert {o.label for o in options} == STATIONS
        # Declared or inferred is never a guess a caller has to make.
        assert all(o.inferred_from == "cursor" for o in options)
        assert all(o.locator_hint for o in options)

        # And the ids resolve to the real things: clicking one drives the app.
        chosen = next(o for o in options if o.label == "LAHORE CANTT")
        page.locator(chosen.locator_hint).click()
        page.wait_for_timeout(800)
        assert origin.input_value() == "LAHORE CANTT"
    finally:
        browser.close()
