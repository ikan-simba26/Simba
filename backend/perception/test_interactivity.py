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


# --- qualifiers: what the label cannot carry --------------------------------


def calendar_with_header(month: str = "2026 September") -> dict:
    """A picker panel with a header, the way a real one is built.

    The header sits beside the arrow buttons and says which month the grid
    below belongs to. Every month's grid looks the same without it.
    """
    b = Builder()
    root = b.node(-1, "html")
    body = b.node(root, "body")
    panel = b.node(body, "div", attrs={"class": "el-picker-panel el-date-picker"},
                   style=FLOATING, rect=(790, 218, 324, 343))
    header = b.node(panel, "div", attrs={"class": "el-date-picker__header"},
                    rect=(790, 218, 324, 40))
    b.node(header, "span", attrs={"class": "el-date-picker__header-label"},
           rect=(830, 222, 60, 30), text=month)
    table = b.node(panel, "table", attrs={"class": "el-date-table"})
    for index, (day, classes) in enumerate((("14", "available"), ("15", "available"),
                                            ("16", "available"))):
        cell = b.node(table, "td", attrs={"class": classes}, style=POINTER,
                      rect=(800 + index * 30, 300, 28, 28))
        b.node(cell, "span", style=POINTER, rect=(802 + index * 30, 302, 24, 24),
               text=day)
    return b.build()


def calendar(today_index: int = 4) -> dict:
    """A month grid the way a picker builds one.

    Three rows: trailing days of the previous month, the month itself, then
    leading days of the next. The numbers repeat across the boundaries, which
    is the whole problem.
    """
    b = Builder()
    root = b.node(-1, "html")
    body = b.node(root, "body")
    panel = b.node(body, "div", attrs={"class": "el-picker-panel"}, style=FLOATING,
                   rect=(300, 200, 320, 300))
    table = b.node(panel, "table", attrs={"class": "el-date-table"})
    cells = [
        ("30", "prev-month"), ("31", "prev-month"),
        ("1", "available"), ("2", "available"), ("3", "available"),
        ("4", "available today"), ("5", "disabled"),
        ("29", "available"), ("30", "available"),
        ("1", "next-month"), ("2", "next-month"),
    ]
    for index, (day, classes) in enumerate(cells):
        cell = b.node(table, "td", attrs={"class": classes}, style=POINTER,
                      rect=(300 + index * 30, 220, 28, 28))
        # Text in a span inside the cell, as every picker does it.
        b.node(cell, "span", style=POINTER, rect=(302 + index * 30, 222, 24, 24),
               text=day)
    return b.build()


def test_the_two_cells_labelled_thirty_are_told_apart() -> None:
    """The finding this exists for, in miniature.

    A month grid has two cells called `30`. Emitted identically, "the 30th of
    this month" is not expressible and a planner picks whichever comes first.
    """
    found = infer(calendar())

    thirtieths = [f for f in found if f.label == "30"]
    assert len(thirtieths) == 2
    assert {f.qualifier for f in thirtieths} == {"previous month", ""}


def test_a_day_in_the_month_on_screen_has_no_qualifier() -> None:
    """Emptiness is the signal. It is what "this month" looks like."""
    found = infer(calendar())

    ordinary = [f for f in found if f.qualifier == ""]
    assert {f.label for f in ordinary} == {"1", "2", "3", "29", "30"}


def test_leading_and_trailing_days_name_the_month_they_belong_to() -> None:
    found = infer(calendar())

    by_label = {(f.label, f.qualifier) for f in found}
    assert ("31", "previous month") in by_label
    assert ("1", "next month") in by_label
    # And `1` exists twice, once each way.
    assert ("1", "") in by_label


def test_state_tokens_are_carried_too() -> None:
    found = infer(calendar())

    qualifiers = {f.label: f.qualifier for f in found if f.label in {"4", "5"}}
    assert qualifiers["4"] == "today"
    assert qualifiers["5"] == "disabled"


def test_a_disabled_choice_is_surfaced_rather_than_dropped() -> None:
    """A date you cannot pick is information, not noise.

    Dropping it would make the page look as though the option does not exist,
    which is a different and worse claim than "it exists and is unavailable".
    """
    found = infer(calendar())

    assert any(f.label == "5" and f.qualifier == "disabled" for f in found)


def test_the_qualifier_comes_from_the_cell_when_the_text_is_in_a_span() -> None:
    """The node that survives the containment filter is the `td`.

    Its class carries the state; the `span` inside carries the text. Looking
    only at the element that won would find nothing on some libraries and
    nothing on the parent for others, so both are checked.
    """
    b = Builder()
    root = b.node(-1, "html")
    body = b.node(root, "body")
    panel = b.node(body, "div", style=FLOATING)
    cell = b.node(panel, "td", attrs={"class": "prev-month"}, style=POINTER,
                  rect=(0, 0, 28, 28))
    b.node(cell, "span", style=POINTER, rect=(1, 1, 26, 26), text="30")

    found = infer(b.build())

    assert len(found) == 1
    assert (found[0].label, found[0].qualifier) == ("30", "previous month")


def test_an_ordinary_dropdown_option_carries_no_qualifier() -> None:
    """Station names are unambiguous, so nothing is added to them."""
    found = infer(dropdown())

    assert all(f.qualifier == "" for f in found)


def test_styling_classes_are_not_treated_as_qualifiers() -> None:
    """A curated list, not a class dump. Most of a class attribute is noise."""
    b = Builder()
    root = b.node(-1, "html")
    body = b.node(root, "body")
    panel = b.node(body, "div", style=FLOATING)
    b.node(panel, "li", attrs={"class": "el-select-dropdown__item hover selected--x"},
           style=POINTER, rect=(0, 0, 100, 30), text="LAHORE CANTT")

    found = infer(b.build())

    assert found[0].qualifier == ""


# --- panel headings: which month is this ------------------------------------


def test_a_picker_says_which_month_it_is_showing() -> None:
    """The fact that decides whether a day cell is the right one.

    Forty-two cells look the same in every month. Which month is on screen is
    stated once, at the top, in text a planner had no reason to single out —
    and both live LLM runs clicked the 15th without ever comparing it to the
    goal.
    """
    found = infer(calendar_with_header())

    assert [f.label for f in found] == ["14", "15", "16"]
    assert all(f.panel == "2026 September" for f in found)


def test_the_heading_follows_the_month_on_screen() -> None:
    found = infer(calendar_with_header("2026 October"))

    assert all(f.panel == "2026 October" for f in found)


def test_a_dropdown_with_no_heading_carries_none() -> None:
    """Station names describe themselves. Nothing is invented for them."""
    found = infer(dropdown())

    assert all(f.panel == "" for f in found)


def test_the_panels_own_header_wins_over_a_nested_one() -> None:
    """Breadth-first, so a sub-header inside the grid cannot shadow it."""
    b = Builder()
    root = b.node(-1, "html")
    body = b.node(root, "body")
    panel = b.node(body, "div", attrs={"class": "picker"}, style=FLOATING,
                   rect=(0, 0, 300, 300))
    header = b.node(panel, "div", attrs={"class": "picker__header"}, rect=(0, 0, 300, 40))
    b.node(header, "span", rect=(0, 0, 100, 30), text="2026 October")
    grid = b.node(panel, "div", attrs={"class": "grid"})
    inner = b.node(grid, "div", attrs={"class": "column-title"}, rect=(0, 40, 300, 20))
    b.node(inner, "span", rect=(0, 40, 40, 20), text="Sun Mon Tue")
    for index in range(MIN_GROUP):
        cell = b.node(grid, "td", attrs={"class": "day"}, style=POINTER,
                      rect=(index * 30, 60, 28, 28))
        b.node(cell, "span", style=POINTER, rect=(index * 30, 60, 24, 24),
               text=str(index + 1))

    found = infer(b.build())

    assert found and all(f.panel == "2026 October" for f in found)


def test_a_heading_that_is_really_the_contents_is_not_used() -> None:
    """A long "heading" is the panel's body wearing a header class."""
    b = Builder()
    root = b.node(-1, "html")
    body = b.node(root, "body")
    panel = b.node(body, "div", style=FLOATING, rect=(0, 0, 300, 300))
    header = b.node(panel, "div", attrs={"class": "header"}, rect=(0, 0, 300, 40))
    b.node(header, "span", rect=(0, 0, 300, 30), text="x" * 200)
    for index in range(MIN_GROUP):
        cell = b.node(panel, "li", attrs={"class": "item"}, style=POINTER,
                      rect=(0, 60 + index * 30, 200, 28))
        b.node(cell, "span", style=POINTER, rect=(0, 60 + index * 30, 190, 24),
               text=f"choice {index}")

    assert all(f.panel == "" for f in infer(b.build()))


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


@LIVE
def test_the_live_calendar_tells_its_duplicate_days_apart(playwright_instance) -> None:
    """A month grid on the real site, and an October date made expressible.

    Before qualifiers this listing gave a planner 42 day cells of which
    eleven numbers appeared twice, with nothing to choose between them. The
    live LLM run clicked the 15th of the month the picker happened to open
    on, and could not have done better: "the 15th of October" was not
    something the input could express.
    """
    from backend.orchestrator.loop import pick
    from backend.orchestrator.plan import Target

    browser = playwright_instance.chromium.launch()
    try:
        context = browser.new_context(
            user_agent=USER_AGENT, viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        page.set_default_timeout(15000)
        page.goto(RAILWAYS, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        date_field = page.get_by_role("textbox", name="Departure Date", exact=True)
        date_field.click()
        page.wait_for_timeout(800)

        days = [e for e in read(page).elements if e.inferred and e.role == "option"]
        assert len(days) > 28, f"the grid should be a month of days, got {len(days)}"

        # Which month the grid belongs to, stated rather than implied.
        assert days[0].panel, "the picker's heading did not reach the elements"
        assert all(d.panel == days[0].panel for d in days)
        opened_on = days[0].panel

        # The case the brief names: two cells, one number, told apart.
        thirtieths = [d for d in days if d.label == "30"]
        assert len(thirtieths) == 2, [d.label for d in days]
        assert len({d.qualifier for d in thirtieths}) == 2, (
            f"both cells called '30' carry {thirtieths[0].qualifier!r}"
        )
        assert "" in {d.qualifier for d in thirtieths}
        assert "previous month" in {d.qualifier for d in thirtieths}

        # Every duplicate number is separated, not just that one.
        for label in {d.label for d in days}:
            same = [d for d in days if d.label == label]
            assert len({d.qualifier for d in same}) == len(same), (
                f"{len(same)} cells labelled {label!r} share a qualifier"
            )

        # And an October date is expressible: go to next month and name the
        # day belonging to the month on screen.
        page.get_by_role("button", name="Next Month", exact=True).click()
        page.wait_for_timeout(800)

        elements = read(page).elements
        chosen = pick(elements, Target("option", "15", qualifier=""))
        assert chosen is not None, "the 15th of the month on screen was not found"
        element = next(e for e in elements if e.id == chosen)
        assert element.qualifier == ""

        # The heading moved with the month, so a planner can tell it changed.
        moved = [e for e in elements if e.inferred and e.role == "option"]
        assert moved[0].panel != opened_on, (
            f"the heading still reads {opened_on!r} after Next Month"
        )

        # And the model would be told, above the list rather than inside it.
        from backend.orchestrator.llm_loop import render_page

        banner = render_page(elements).splitlines()[1]
        assert banner.startswith("IT IS SHOWING:")
        assert moved[0].panel in banner

        page.locator(element.locator_hint).click()
        page.wait_for_timeout(900)

        # The site writes the committed date back as dd-mm-yyyy.
        assert date_field.input_value().startswith("15-"), date_field.input_value()
        assert date_field.input_value() != "15-09-2026", (
            "picked the month the calendar opened on, not the one asked for"
        )
    finally:
        browser.close()
