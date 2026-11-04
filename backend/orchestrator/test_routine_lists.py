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
    # Book on a train opens its form, and its words say book; Confirm Booking
    # books. Both wait for a final screen when it runs.
    assert changes[-1] == ("button", "Confirm Booking")
    assert booking.changes and booking.answer.reads == "Booking number"
    name = next(s for s in booking.steps if s.label == "Passenger Name")
    assert name.ask and name.value is None


def test_the_booking_runs_behind_its_final_screens_and_says_it_was_practice(booking) -> None:
    done = _run(booking, [("confirm", {"value0": "Lahore Cantt"}),
                          ("confirm", {"value2": "Karachi Cantt"}),
                          (f"{voice.CHOICE_PREFIX}1", {}),
                          ("confirm", {next(f"value{i}" for i, s in enumerate(booking.steps)
                                            if s.label == "Passenger Name"): "Bilal Ahmed"})])
    finals = [p for p in done.of("step.presented") if p.get("final")]
    # Two: Book on the train, whose words say book though it only opens the
    # form, and Confirm Booking. Each names what it presses (flagged: the
    # final-step rule asks for what, how much and when as well).
    assert [f["final"] for f in finals] == [
        [{"label": voice.WHAT_I_PRESS, "value": next(
            s.label for s in booking.steps if s.role == "link" and s.changes)}],
        [{"label": voice.WHAT_I_PRESS, "value": "Confirm Booking"}]]
    ending = done.of("task.completed")[0]
    assert ending["findings"][0]["values"][0].startswith("PR-")
    assert ending["scope"] == voice.ROUTINE_PRACTICE_SCOPE and ending["llm_calls"] == 0


def test_the_person_can_say_don_t_and_nothing_is_booked(booking) -> None:
    class Declines(Scripted):
        async def receive(self, message_type, step_index=None, on_other=None):
            steps = self.of("step.presented")
            if steps and steps[-1].get("final") and steps[-1]["final"][0]["value"] \
                    == "Confirm Booking":
                return {"type": "step.response", "payload": {
                    "step_index": step_index, "action_id": voice.DECLINE_ID,
                    "input_values": {}}}
            return await super().receive(message_type, step_index, on_other)

    async def inner():
        connection = Declines([("confirm", {"value0": "Lahore Cantt"}),
                               ("confirm", {"value2": "Karachi Cantt"}),
                               (f"{voice.CHOICE_PREFIX}1", {}),
                               ("confirm", {f"value{i}": "Bilal Ahmed"
                                            for i in range(len(booking.steps))})])
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
