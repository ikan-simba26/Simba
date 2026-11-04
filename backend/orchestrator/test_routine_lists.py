"""Show me once, stage 2 (2026-11-04): values that change list choices and days.

A helper shows the train search once on our copy of it — station boxes that
are read-only until clicked, lists that open on a typed name, a calendar of
bare day cells — and says the stations and the day change. The person then
runs it for another journey: asked where from and where to against the site's
own station list (`details.match_station`), and which day as a journey's day
is asked, and SIMBA types, chooses, moves the calendar to the month and picks
the day. Real presses on the real copy in Chromium, with the real loop.
"""

import asyncio
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from backend.orchestrator import voice
from backend.orchestrator.loop import FilledValue, Move, Operation, recommitted, run_brief
from backend.orchestrator.plan import Expectation, Target
from backend.orchestrator.routine_plan import RoutineBrief
from backend.orchestrator.routines import RoutineStore, export, parse
from backend.orchestrator.teach import shown_month, teach
from backend.orchestrator.test_checklist import run
from backend.orchestrator.test_routine_run import Scripted
from backend.orchestrator.test_teach import Overlay
from backend.orchestrator.test_trip_answers import railways  # noqa: F401

pytestmark = pytest.mark.skipif(not RoutineStore(Path("unused")).available,
                                reason="routines need the operating system's encryption")

TOMORROW = date.today() + timedelta(days=1)


async def _choose(page, box: str, typed: str, station: str) -> None:
    await page.locator(f"#{box}").click()
    await page.locator(f"#{box}").press_sequentially(typed, delay=30)
    await page.locator("li:visible", has_text=station).first.click()


async def _show_the_trains(page, overlay: Overlay) -> None:
    """A helper finds trains Lahore Cantt to Karachi Cantt on the 15th of next
    month, and says the stations and the day change."""
    await _choose(page, "from", "LAH", "LAHORE CANTT")
    await overlay.until(lambda o: o.bar()["question"] is not None)
    overlay.say("teach.answer", {"action": "ask", "step": overlay.bar()["question"]["step"]})
    await overlay.until(lambda o: o.bar()["question"] is None)
    await _choose(page, "to", "KARACHI", "KARACHI CANTT")
    await overlay.until(lambda o: o.bar()["question"] is not None)
    overlay.say("teach.answer", {"action": "ask", "step": overlay.bar()["question"]["step"]})
    await overlay.until(lambda o: o.bar()["question"] is None)
    await page.locator("#date").click()
    # As a person does: the next month is seen before a day in it is pressed.
    showing = await page.locator("#showing").inner_text()
    await page.get_by_role("button", name="Next Month").click()
    await page.wait_for_function(
        f"document.getElementById('showing').textContent !== {json.dumps(showing)}")
    await page.locator("#days td.available", has_text="15").first.click()
    await overlay.until(lambda o: o.bar()["question"] is not None)
    assert overlay.bar()["question"]["kind"] == "day"
    overlay.say("teach.answer", {"action": "ask", "step": overlay.bar()["question"]["step"]})
    await overlay.until(lambda o: o.bar()["question"] is None)
    await page.locator("#search").click()
    await page.locator("#results td").first.wait_for()
    overlay.say("teach.answer", {"action": "finish"})
    await overlay.until(lambda o: o.bar()["pointing"])
    await page.locator("#results tbody td").first.click()
    await overlay.until(lambda o: o.of("step.presented"))
    overlay.say("step.response", {"step_index": 1, "action_id": "confirm",
                                  "input_values": {"name": "My trains", "answer": "Trains"}})


async def _teach(url: str, store: RoutineStore):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        overlay = Overlay()
        job = asyncio.create_task(teach(page, overlay, url, store))
        await overlay.until(lambda o: o.of("teach.watching"))
        await _show_the_trains(page, overlay)
        kept = await asyncio.wait_for(job, 30)
        await browser.close()
        return kept, overlay


@pytest.fixture(scope="module")
def trains(railways: str, tmp_path_factory):  # noqa: F811
    store = RoutineStore(tmp_path_factory.mktemp("lists") / "routines.json")
    kept, overlay = run(_teach(railways, store))
    return {"routine": kept, "overlay": overlay, "url": railways}


def test_the_stations_and_the_day_are_kept_as_the_person_s_to_give(trains: dict) -> None:
    steps = trains["routine"].steps
    shape = [(s.kind, s.role, s.label, s.ask, s.pick, s.day, s.click_first) for s in steps]
    assert shape == [
        ("fill", "textbox", "From", True, False, False, True),
        ("click", "option", "LAHORE CANTT", False, True, False, False),
        ("fill", "textbox", "To", True, False, False, True),
        ("click", "option", "KARACHI CANTT", False, True, False, False),
        ("click", "textbox", "Departure Date", False, False, False, False),
        ("click", "option", "15", True, False, True, False),
        ("click", "button", "", False, False, False, False),
    ]
    # The typed letters never kept; the calendar's press folded into the day;
    # the box's check waits for its list, the date box's for the calendar.
    assert steps[0].value is None and steps[0].expect_label == "LAHORE CANTT"
    assert steps[0].list_opens
    assert steps[5].nav == "Next Month" and steps[4].expect_label == "Next Month"
    assert trains["routine"].answer.reads == "Train No."
    # The page's own rewrites of the boxes were never taken for typing.
    assert not any(s.kind == "fill" and s.label == "Departure Date" for s in steps)


def test_the_read_back_says_the_choices_and_the_day(trains: dict) -> None:
    lines = trains["overlay"].of("step.presented")[0]["routine"]
    assert lines[:2] == ["Ask what to type in From, and type it.",
                         "Choose the one they said from the list."]
    assert lines[5] == "Ask which day, and choose it on the calendar."


def _run(routine, answers):
    async def inner():
        connection = Scripted(answers)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await run_brief(page, connection, RoutineBrief(routine), routine.start,
                                auto=True)
                connection.searched = await page.evaluate("window.__searched || null")
                connection.text = await page.locator("body").inner_text()
            finally:
                await browser.close()
        return connection

    return run(inner())


def test_another_journey_runs_from_the_same_routine(trains: dict) -> None:
    # Rawalpindi to Sukkur, tomorrow: nothing the helper chose.
    done = _run(trains["routine"], [("confirm", {"value0": "Rawalpindi"}),
                                    ("confirm", {"value2": "Sukkur"}),
                                    (f"{voice.CHOICE_PREFIX}1", {})])
    assert done.searched == {"from": "RAWALPINDI", "to": "SUKKUR",
                             "date": TOMORROW.isoformat()}, done.types()
    ending = done.of("task.completed")[0]
    assert ending["heading"] == (f"My trains: Rawalpindi, Sukkur, "
                                 f"{voice.when_words(TOMORROW, date.today())}")
    assert ending["llm_calls"] == 0 and ending["findings"][0]["label"] == "Trains"
    assert ending["findings"][0]["values"]
    # Asked from the site's own list, as the train search asks.
    first = [p for p in done.of("step.presented") if p["requires_confirmation"]][0]
    assert first["fields"][0]["type"] == "choice" and "RAWALPINDI" in first["fields"][0]["options"]


def test_a_city_with_two_stations_is_asked_about(trains: dict) -> None:
    later = TOMORROW + timedelta(days=40)
    done = _run(trains["routine"], [("confirm", {"value0": "Lahore"}),
                                    (f"{voice.CHOICE_PREFIX}1", {}),
                                    ("confirm", {"value2": "Karachi Cantt"}),
                                    (f"{voice.CHOICE_PREFIX}2", {}),
                                    ("confirm", {"value5": later.strftime("%d %B %Y")})])
    assert done.searched == {"from": "LAHORE CANTT", "to": "KARACHI CANTT",
                             "date": later.isoformat()}, done.types()
    assert voice.ASK_CLOSEST in done.asked()


def test_a_place_not_in_the_list_is_said_and_asked_again(trains: dict) -> None:
    done = _run(trains["routine"], [("confirm", {"value0": "Narnia"}),
                                    ("confirm", {"value0": "Multan"}),
                                    ("confirm", {"value2": "Quetta"}),
                                    (f"{voice.CHOICE_PREFIX}0", {})])
    asked = [p for p in done.of("step.presented") if p["requires_confirmation"]]
    assert asked[1]["note"] == voice.not_in_list("Narnia")
    assert done.searched["from"] == "MULTAN CANTT"


def test_a_shared_routine_keeps_the_choices_and_the_day_asked(trains: dict) -> None:
    shared = parse(export(trains["routine"]))
    assert [s.pick for s in shared.steps] == [s.pick for s in trains["routine"].steps]
    assert shared.steps[5].day and shared.steps[5].ask


# --- the loop: a choice from a list commits the box ----------------------------------


def test_a_choice_from_a_list_is_what_the_box_holds_after_it(railways: str) -> None:  # noqa: F811
    async def inner():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page()
            await page.goto(railways)
            await page.locator("#from").click()
            await page.locator("#from").press_sequentially("LAH")
            typed = [FilledValue("textbox", "From", "LAH", page.url)]
            await page.locator("li", has_text="LAHORE CANTT").first.click()
            move = Move(instruction="", detail="", operations=[Operation(
                "click", Target("option", "LAHORE CANTT"))], expect=Expectation(), fields=[],
                actions=[])
            after = await recommitted(page, typed, move)
            await browser.close()
            return after

    after = run(inner())
    assert [f.value for f in after] == ["LAHORE CANTT"]


def test_a_choice_never_takes_the_place_of_a_value_the_task_declares(
        railways: str) -> None:  # noqa: F811
    from backend.orchestrator.plan import FieldValue

    async def inner():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page()
            await page.goto(railways)
            await page.locator("#to").click()
            await page.locator("#to").press_sequentially("MULTAN")
            typed = [FilledValue("textbox", "To", "MULTAN", page.url)]
            await page.locator("li:visible", has_text="MULTAN CANTT").first.click()
            move = Move(instruction="", detail="", operations=[Operation(
                "click", Target("option", "MULTAN CANTT"))], expect=Expectation(), fields=[],
                actions=[])
            after = await recommitted(page, typed, move,
                                      (FieldValue("To", "Peshawar", names=True),))
            await browser.close()
            return after

    # Still "MULTAN": the next look finds the box changed, and stops the run.
    assert [f.value for f in run(inner())] == ["MULTAN"]


def test_a_calendar_banner_is_read_as_a_month() -> None:
    assert shown_month("2026 December") == (2026, 12)
    assert shown_month("December 2026") == (2026, 12)
    assert shown_month("Choose a station") is None
    assert json.dumps(shown_month("2027 january")) == "[2027, 1]"


# --- booking on our copy: a change, behind the final screen ----------------------------


async def _show_a_booking(page, overlay: Overlay) -> None:
    """The same search, then Book on the first train, a name asked each time,
    a class the same every time, Confirm Booking, and the booking number."""

    async def ask_or_keep(same: bool) -> None:
        await overlay.until(lambda o: o.bar()["question"] is not None)
        overlay.say("teach.answer", {"action": "same" if same else "ask",
                                     "step": overlay.bar()["question"]["step"]})
        await overlay.until(lambda o: o.bar()["question"] is None)

    await _choose(page, "from", "LAH", "LAHORE CANTT")
    await ask_or_keep(False)
    await _choose(page, "to", "KARACHI", "KARACHI CANTT")
    await ask_or_keep(False)
    await page.locator("#date").click()
    await page.locator("#days td.available.today, #days td.available").first.wait_for()
    await page.locator("#days td.available").last.click()
    await ask_or_keep(False)
    await page.locator("#search").click()
    await page.locator("#results a").first.click()
    await page.wait_for_url("**/book**")
    await page.locator("#passenger").fill("Ayesha Khan")
    # Held for a moment while it is read, then let through: clicked, not
    # checked, and seen checked before going on.
    await page.get_by_label("AC Standard").click()
    await page.wait_for_function(
        "document.querySelector('input[value=\"AC Standard\"]').checked")
    await ask_or_keep(False)
    await page.get_by_role("button", name="Confirm Booking").click()
    await page.wait_for_url("**/book")
    await page.get_by_role("heading", name="Booking Confirmed").wait_for()
    overlay.say("teach.answer", {"action": "finish"})
    await overlay.until(lambda o: o.bar()["pointing"])
    await page.locator("td", has_text="PR-").first.click()
    await overlay.until(lambda o: o.of("step.presented"))
    overlay.say("step.response", {"step_index": 1, "action_id": "confirm",
                                  "input_values": {"name": "Book my train",
                                                   "answer": "Booking number"}})


@pytest.fixture(scope="module")
def booking(railways: str, tmp_path_factory):  # noqa: F811
    store = RoutineStore(tmp_path_factory.mktemp("booking") / "routines.json")

    async def inner():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            overlay = Overlay()
            job = asyncio.create_task(teach(page, overlay, railways, store))
            await overlay.until(lambda o: o.of("teach.watching"))
            await _show_a_booking(page, overlay)
            kept = await asyncio.wait_for(job, 30)
            await browser.close()
            return kept

    return run(inner())


def test_a_booking_on_our_copy_is_kept_with_its_changes_marked(booking) -> None:
    changes = [(s.role, s.label) for s in booking.steps if s.changes]
    # Book on a train opens its form, though its words say book; Confirm
    # Booking books, and is the only change (2026-11-04, fix).
    assert changes == [("button", "Confirm Booking")]
    opens = [s for s in booking.steps if s.opens]
    assert [(s.role, s.label) for s in opens] == [("link", "Book train {}")]
    assert booking.changes and booking.answer.reads == "Booking number"
    name = next(s for s in booking.steps if s.label == "Passenger Name")
    assert name.ask and name.value is None


def _name(booking) -> str:
    return next(f"value{i}" for i, s in enumerate(booking.steps) if s.label == "Passenger Name")


def test_the_booking_runs_behind_its_final_screens_and_says_it_was_practice(booking) -> None:
    done = _run(booking, [("confirm", {"value0": "Lahore Cantt"}),
                          ("confirm", {"value2": "Karachi Cantt"}),
                          (f"{voice.CHOICE_PREFIX}1", {}),
                          ("confirm", {_name(booking): "Bilal Ahmed"}),
                          (f"{voice.CHOICE_PREFIX}0", {})])
    finals = [p for p in done.of("step.presented") if p.get("final")]
    # One, for Confirm Booking: Book on the train only opens the form, and
    # runs as a checklist line once the person has chosen the train. It shows
    # what, how much and when as the page states them, as the built-in
    # booking's does (2026-11-04, fix).
    assert [f["final"] for f in finals] == [[
        {"label": "Train", "value": "7UP"}, {"label": "From", "value": "LAHORE CANTT"},
        {"label": "To", "value": "KARACHI CANTT"},
        {"label": "Date", "value": voice.page_date(f"{TOMORROW:%d-%m-%Y}")},
        {"label": "Departs", "value": "07:25"}, {"label": "Passenger", "value": "Bilal Ahmed"},
        {"label": "Class", "value": "AC Standard"}, {"label": "Fare", "value": "Rs 3,250"}]]
    assert finals[0]["instruction"] == voice.final_routine("Confirm Booking")
    assert "Opening Book train 7UP" in [p["instruction"] for p in done.of("step.presented")
                                        if not p["requires_confirmation"]]
    ending = done.of("task.completed")[0]
    assert ending["findings"][0]["values"][0].startswith("PR-")
    assert ending["scope"] == voice.ROUTINE_PRACTICE_SCOPE and ending["llm_calls"] == 0


def test_the_person_can_say_don_t_and_nothing_is_booked(booking) -> None:
    class Declines(Scripted):
        async def receive(self, message_type, step_index=None, on_other=None):
            steps = self.of("step.presented")
            if steps and steps[-1].get("final"):
                return {"type": "step.response", "payload": {
                    "step_index": step_index, "action_id": voice.DECLINE_ID,
                    "input_values": {}}}
            return await super().receive(message_type, step_index, on_other)

    async def inner():
        connection = Declines([("confirm", {"value0": "Lahore Cantt"}),
                               ("confirm", {"value2": "Karachi Cantt"}),
                               (f"{voice.CHOICE_PREFIX}1", {}),
                               ("confirm", {f"value{i}": "Bilal Ahmed"
                                            for i in range(len(booking.steps))}),
                               (f"{voice.CHOICE_PREFIX}0", {})])
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page()
            await run_brief(page, connection, RoutineBrief(booking), booking.start, auto=True)
            connection.url = page.url
            await browser.close()
        return connection

    done = run(inner())
    assert done.of("task.failed")[0]["reason"] == voice.NOTHING_CHANGED
    assert "task.completed" not in done.types() and "/book" in done.url


# --- the train is the person's choice (2026-11-04, fix) -------------------------------


def test_the_train_pressed_is_kept_as_the_person_s_to_choose(booking) -> None:
    row = next(s for s in booking.steps if s.row)
    assert (row.role, row.label, row.row) == ("link", "Book train {}", "Train No.")
    assert "7UP" not in json.dumps([s.label for s in booking.steps])
    assert voice.routine_line(row).startswith("Ask which train they want, from the page's own")
    # A shared file keeps it, and is read back the same.
    assert next(s for s in parse(export(booking)).steps if s.row) == row


def test_the_person_chooses_a_train_that_is_not_the_helper_s(booking) -> None:
    # Hyderabad Jn to Sukkur has four trains, none of them 7UP: the person
    # is asked which, from the page's own rows, and the third is booked.
    done = _run(booking, [("confirm", {"value0": "Hyderabad"}),
                          ("confirm", {"value2": "Sukkur"}),
                          (f"{voice.CHOICE_PREFIX}1", {}),
                          ("confirm", {_name(booking): "Bilal Ahmed"}),
                          (f"{voice.CHOICE_PREFIX}2", {})])
    which = next(p for p in done.of("step.presented") if p["instruction"] == "Which train?")
    assert [a["label"] for a in which["actions"]][:4] == [
        "11UP, 06:40 09:55, 3 h 15 min", "12DN, 09:30 13:45, 4 h 15 min",
        "13UP, 13:05 16:20, 3 h 15 min", "14DN, 18:45 23:00, 4 h 15 min"]
    assert which["detail"] == voice.ROWS_DETAIL
    assert done.of("task.completed"), done.of("help.requested")
    assert "13UP" in done.text and "Booking Confirmed" in done.text
    assert done.of("task.completed")[0]["llm_calls"] == 0


def test_a_column_of_presses_is_found_and_a_lone_press_is_not() -> None:
    from backend.orchestrator.teach import row_of
    from backend.perception.content import Content, Row, Table
    from backend.perception.serializer import Element

    def link(i, label):
        return Element(id=i, role="link", label=label, type="", tag="a", input_type=None)

    table = Table(headers=("Train No.", "Time", "Book"), rows=(
        Row((("Train No.", "7UP"), ("Time", "07:25"), ("Book", "Book"))),
        Row((("Train No.", "8DN"), ("Time", "16:35"), ("Book", "Book")))))
    links = [link(1, "Book train 7UP"), link(2, "Book train 8DN"), link(3, "Home")]
    assert row_of(Content(tables=[table]), links, links[0]) == ("Train No.", "Book train {}")
    assert row_of(Content(tables=[table]), links, links[2]) is None
    # Only one row's press on the page: not a column of them.
    assert row_of(Content(tables=[table]), links[:1], links[0]) is None
    assert row_of(Content(), links, links[0]) is None


def test_the_rows_offered_are_the_page_s_own_and_say_what_tells_them_apart() -> None:
    from backend.orchestrator.routine_plan import in_row, rows_of
    from backend.orchestrator.routines import Step
    from backend.perception.content import Content, Row, Table
    from backend.perception.serializer import Element

    step = Step(kind="click", role="link", label="Book train {}", row="Train No.")
    table = Table(headers=("Train No.", "From/To", "Time", "Book"), rows=(
        Row((("Train No.", "7UP"), ("From/To", "A B"), ("Time", "07:25"), ("Book", "Book"))),
        Row((("Train No.", "8DN"), ("From/To", "A B"), ("Time", "16:35"), ("Book", "Book")))))
    links = [Element(id=i, role="link", label=f"Book train {t}", type="", tag="a",
                     input_type=None) for i, t in enumerate(("7UP", "8DN"))]
    assert rows_of(Content(tables=[table]), links, step) == [("7UP", "7UP, 07:25"),
                                                             ("8DN", "8DN, 16:35")]
    # A row whose press is not on the page is not offered.
    assert rows_of(Content(tables=[table]), links[:1], step) == [("7UP", "7UP")]
    assert in_row(step, "Book train 13UP") == "13UP"
    assert in_row(step, "Book train ") is None and in_row(step, "Home") is None
    assert voice.which_row("Train No.") == "Which train?"
    assert voice.which_row("No.") == "Which one?"


def test_a_row_press_that_does_not_say_where_the_name_goes_is_refused() -> None:
    from backend.orchestrator.routines import NotARoutine, step_from

    with pytest.raises(NotARoutine):
        step_from({"kind": "click", "role": "link", "label": "Book train 7UP",
                   "row": "Train No."})
    assert step_from({"kind": "click", "role": "link", "label": "Book train {}",
                      "row": "Train No."}).row == "Train No."


def test_a_route_with_no_trains_stops_and_says_so(booking) -> None:
    done = _run(booking, [("confirm", {"value0": "Quetta"}),
                          ("confirm", {"value2": "Sukkur"}),
                          (f"{voice.CHOICE_PREFIX}1", {}),
                          ("confirm", {_name(booking): "Bilal Ahmed"})])
    assert "task.completed" not in done.types()
    assert not [p for p in done.of("step.presented") if p.get("final")]
    assert done.of("help.requested")[-1]["reason"] == voice.no_rows("Train No.")


# --- one final screen per booking (2026-11-04, fix) ----------------------------------


def test_only_a_link_to_another_page_of_our_copy_is_believed_to_only_open(
        railways: str) -> None:  # noqa: F811
    from backend.orchestrator.loop import only_opens
    from backend.perception.serializer import read_async

    async def inner():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            await page.goto(railways)
            await page.evaluate("""() => document.body.insertAdjacentHTML('afterbegin',
                '<a href="/book?train=7UP">Book train 7UP</a>' +
                '<a href="#" onclick="return false">Book now</a>' +
                '<button>Book this</button>' +
                '<a href="https://example.com/book">Book elsewhere</a>')""")
            elements = (await read_async(page)).elements

            async def opens(role: str, label: str, said: bool = True) -> bool:
                move = Move(instruction="", detail="",
                            operations=[Operation("click", Target(role, label))],
                            expect=Expectation(), fields=[], actions=[], opens=said)
                return await only_opens(page, elements, move)

            found = [await opens("link", "Book train 7UP"),
                     await opens("link", "Book train 7UP", said=False),
                     await opens("link", "Book now"),
                     await opens("button", "Book this"),
                     await opens("link", "Book elsewhere")]
            await browser.close()
            return found

    # Only the real link to another page of our copy, and only when the
    # planner says so: a script's link, a button and another site keep
    # their final screens.
    assert run(inner()) == [True, False, False, False, False]


def test_a_routine_file_cannot_take_the_final_screen_off_a_button(booking) -> None:
    from dataclasses import replace

    from backend.orchestrator.routines import Routine

    # A file that says Confirm Booking only opens a page: the loop still
    # shows its final screen, since it is a button that sends the form.
    told = Routine(id="x", label=booking.label, start=booking.start, answer=booking.answer,
                   steps=tuple(replace(s, changes=False, opens=True) if s.changes else s
                               for s in booking.steps))
    done = _run(told, [("confirm", {"value0": "Lahore Cantt"}),
                       ("confirm", {"value2": "Karachi Cantt"}),
                       (f"{voice.CHOICE_PREFIX}1", {}),
                       ("confirm", {_name(booking): "Bilal Ahmed"}),
                       (f"{voice.CHOICE_PREFIX}0", {})])
    assert [f["final"][0]["value"] for f in done.of("step.presented") if f.get("final")] == [
        "Confirm Booking"]


# --- what, how much and when on a routine's final screen (2026-11-04, fix) ------------


def test_the_details_the_page_stated_are_kept_with_the_press_that_books(booking) -> None:
    confirm = next(s for s in booking.steps if s.changes)
    assert confirm.shows == ("Train", "From", "To", "Date", "Departs", "Passenger", "Class",
                             "Fare")
    # Labels only: nothing the helper's booking said is kept.
    assert "Ayesha" not in json.dumps([s.shows for s in booking.steps])
    assert next(s for s in parse(export(booking)).steps if s.changes).shows == confirm.shows


def test_the_person_s_own_train_is_on_the_final_screen(booking) -> None:
    done = _run(booking, [("confirm", {"value0": "Hyderabad"}),
                          ("confirm", {"value2": "Sukkur"}),
                          (f"{voice.CHOICE_PREFIX}1", {}),
                          ("confirm", {_name(booking): "Bilal Ahmed"}),
                          (f"{voice.CHOICE_PREFIX}3", {})])
    final = next(p for p in done.of("step.presented") if p.get("final"))
    said = {d["label"]: d["value"] for d in final["final"]}
    assert (said["Train"], said["From"], said["To"], said["Departs"], said["Fare"]) == (
        "14DN", "HYDERABAD JN", "SUKKUR", "18:45", "Rs 3,250")


def test_a_detail_the_page_no_longer_states_means_nothing_is_done(booking) -> None:
    from dataclasses import replace

    from backend.orchestrator.routines import Routine

    told = Routine(id="x", label=booking.label, start=booking.start, answer=booking.answer,
                   steps=tuple(replace(s, shows=(*s.shows[:7], "Discount")) if s.changes
                               else s for s in booking.steps))
    done = _run(told, [("confirm", {"value0": "Lahore Cantt"}),
                       ("confirm", {"value2": "Karachi Cantt"}),
                       (f"{voice.CHOICE_PREFIX}1", {}),
                       ("confirm", {_name(booking): "Bilal Ahmed"}),
                       (f"{voice.CHOICE_PREFIX}0", {})])
    assert done.of("help.requested")[-1]["reason"] == voice.NO_FINAL_SCREEN
    assert "Booking Confirmed" not in done.text


def test_a_final_screen_s_details_are_said_once_short_and_not_a_column() -> None:
    from backend.orchestrator.teach import shown_details
    from backend.perception.content import Content, Pair

    content = Content(pairs=[Pair("Train", "7UP"), Pair("Train No.", "7UP"),
                             Pair("Train No.", "8DN"), Pair("Terms", "x" * 90),
                             Pair("Fare", "Rs 3,250"), Pair("Fare", "Rs 3,250"),
                             Pair("Confirm Booking", "y"), Pair("Empty", "")])
    assert shown_details(content, "Confirm Booking") == ("Train", "Fare")


def test_a_file_s_final_details_are_a_short_list() -> None:
    from backend.orchestrator.routines import NotARoutine, step_from

    press = {"kind": "click", "role": "button", "label": "Confirm Booking", "changes": True}
    assert step_from({**press, "shows": ["Train", "Fare"]}).shows == ("Train", "Fare")
    assert step_from(press).shows == ()
    for bad in ("Train", [f"d{i}" for i in range(9)], [1], ["x" * 300]):
        with pytest.raises(NotARoutine):
            step_from({**press, "shows": bad})


# --- the person's values, checked the moment they are chosen ---------------------------


def test_a_box_must_hold_what_was_chosen() -> None:
    from backend.orchestrator.loop import Snapshot, mismatch

    expect = Expectation(field_has=(("Departure Date", ("15-12-2026", "2026-12-15")),))
    right = Snapshot(url="u", title="t", labels=("Departure Date",), values=("15-12-2026",))
    wrong = Snapshot(url="u", title="t", labels=("Departure Date",), values=("15-11-2026",))
    empty = Snapshot(url="u", title="t", labels=(), values=())
    assert mismatch(right, expect) is None
    assert "15-12-2026" in mismatch(wrong, expect)
    assert mismatch(empty, expect) is not None


def test_the_choice_and_the_day_carry_their_checks(trains: dict) -> None:
    from backend.orchestrator.routine_plan import RoutinePlanner, as_written
    from backend.perception.serializer import Element

    day = date.today() + timedelta(days=3)
    planner = RoutinePlanner(trains["routine"], {0: "RAWALPINDI", 2: "SUKKUR",
                                                 5: day.isoformat()})
    option = Element(id=9, role="option", label="RAWALPINDI", type="", tag="li",
                     input_type=None)
    chose = planner.move_for(1, [option])
    assert chose.expect.field_has == (("From", ("RAWALPINDI",)),)
    month = day.strftime("%Y %B")
    cell = Element(id=3, role="option", label="1", type="", tag="td", input_type=None,
                   panel=month)
    picked = planner.move_for(5, [cell])
    assert picked.expect.field_has == (("Departure Date", as_written(day)),)
    assert f"{day:%d-%m-%Y}" in as_written(day)
