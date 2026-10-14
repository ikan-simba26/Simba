"""One person's own journey, searched on the train page.

The fixed plan searches one route on one day — the route every recorded
railways number was measured on. `TripPlanner` searches the journey the person
asked for, which is a different job: what to press depends on what the site
offers. Typing "Lahore" brings back however many stations the site has in
Lahore, and only then is it known whether there is one to choose or a question
to ask.

Against the local replica, not the live site: CLAUDE.md keeps repeated runs
off it, and the replica was built to behave the way that site was measured to
behave — readonly boxes, bare `<li>` options, a calendar of bare `<td>`s, a
date written back as `dd-mm-yyyy`, an unnamed search button, and no URL or
title change when a search happens. It also has what the live site's list has
and a fixed plan never needed: two stations in Lahore, two in Karachi, and a
station with no trains.

`window.__searched` in the replica records what was actually searched, from the
application's own state rather than from the boxes — so "it searched the right
thing" is asserted against what the page believed, not against what it showed.
"""

import asyncio
import os
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import replace
from datetime import date, timedelta

import pytest
from playwright.async_api import async_playwright

from backend.orchestrator.loop import run_task
from backend.orchestrator.railways_plan import (
    RAILWAYS_TASK,
    TripPlanner,
    as_shown,
    months_between,
    trip_task,
)
from backend.orchestrator.test_asking import Answers, ScriptedConnection
from backend.orchestrator.test_orchestrator import _wait_for
from backend.orchestrator.voice import (
    CANCEL_ID,
    CHOICE_PREFIX,
    FORM_CHANGED,
    NO_TRAINS,
    confirm_search,
    day_words,
    no_station,
)
from backend.perception.serializer import Element

REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
PORT = 5211
REPLICA_URL = f"http://127.0.0.1:{PORT}"

TODAY = date.today()
TOMORROW = TODAY + timedelta(days=1)
# Far enough ahead to need the calendar moved on more than once.
LATER = TODAY + timedelta(days=75)


@pytest.fixture(scope="module")
def railways() -> Iterator[str]:
    proc = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=REPO_ROOT / "replicas" / "railways",
        env={**os.environ, "PORT": str(PORT)},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for(REPLICA_URL)
        yield REPLICA_URL
    finally:
        proc.terminate()
        proc.wait(timeout=10)




class AnswersQuestions(ScriptedConnection):
    """Agrees to every step, and answers a question from the script.

    A question here is the step that offers ids of its own — `choice:0` and the
    rest — so a test's script names only the answers it cares about and not the
    go-aheads around them. Out of answers, it stops rather than hanging.
    """

    async def receive(self, message_type: str, step_index: int | None = None,
                      on_other=None) -> dict:  # noqa: ARG002
        self.shown += 1
        offered = self.of("step.presented")[-1]["actions"]
        asking = any(action["id"].startswith(CHOICE_PREFIX) for action in offered)
        answer = ("confirm", {})
        if asking:
            answer = (self.answers.pop(0) if self.answers else None) or (CANCEL_ID, {})
        return {
            "type": "step.response",
            "payload": {"step_index": step_index, "action_id": answer[0],
                        "input_values": answer[1]},
        }


def search(origin: str, destination: str, day: date, answers: Answers,
           start_url: str, task=None) -> ScriptedConnection:
    """Run the real loop with a real browser, and report what was searched."""

    async def go() -> ScriptedConnection:
        connection = AnswersQuestions(answers)
        planner = TripPlanner(origin, destination, day, TODAY)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await run_task(
                    page, connection, planner,
                    task or trip_task(origin, destination, day), start_url,
                )
                connection.searched = await page.evaluate("window.__searched")
                connection.held = await page.evaluate("window.__model")
                connection.stations = dict(planner.stations)
            finally:
                await browser.close()
        return connection

    return asyncio.run(go())


# --- a journey where nothing has to be asked --------------------------------


def test_a_journey_the_site_has_one_station_for_each_end(railways: str) -> None:
    """Rawalpindi and Multan name one station each, so the run goes straight
    through: type a name, choose what the site offers, find the month, pick the
    day, and search."""
    run = search("Rawalpindi", "Multan", TOMORROW, [], railways)

    assert run.searched == {"from": "RAWALPINDI", "to": "MULTAN CANTT",
                            "date": TOMORROW.isoformat()}
    assert run.of("task.completed")[0]["steps_taken"] == 5
    assert "help.requested" not in run.types()


def test_what_the_closing_screen_says_is_the_trains_that_came_back(
    railways: str,
) -> None:
    found = search("Rawalpindi", "Multan", TOMORROW, [], railways).of("task.completed")[0]

    labels = {finding["label"] for finding in found["findings"]}
    # Since 2026-10-14 both times too: the page's `Time` reads leaves, then
    # arrives.
    assert labels == {"Train", "Leaves", "Arrives", "Journey"}
    assert all(finding["value"] for finding in found["findings"])


def test_a_day_months_away_is_reached_by_moving_the_calendar(railways: str) -> None:
    run = search("Rawalpindi", "Multan", LATER, [], railways)

    assert run.searched["date"] == LATER.isoformat()
    assert run.held["date"] == LATER.isoformat()


def test_the_date_is_read_back_in_the_sites_own_order(railways: str) -> None:
    """The box shows `dd-mm-yyyy` and the application holds `yyyy-mm-dd`. What
    is checked is the box, because that is what a person and a snapshot see."""
    run = search("Rawalpindi", "Multan", TOMORROW, [], railways)

    assert as_shown(TOMORROW) == TOMORROW.strftime("%d-%m-%Y")
    assert run.held["date"] == TOMORROW.isoformat()


# --- a place that names more than one station -------------------------------


def test_a_place_with_two_stations_is_asked_about(railways: str) -> None:
    """The case the fixed plan never had to face. Which Lahore station was
    meant is not a guess the system gets to make."""
    run = search("Lahore", "Rawalpindi", TOMORROW, [(f"{CHOICE_PREFIX}1", {})], railways)

    asked = [p for p in run.of("step.presented")
             if p["instruction"] == "Which Lahore station do you mean?"]
    assert len(asked) == 1
    assert [a["label"] for a in asked[0]["actions"]] == [
        "Lahore Jn", "Lahore Cantt", "Stop this"]
    # The one they picked is the one that was searched.
    assert run.stations["origin"] == "LAHORE CANTT"
    assert run.searched == {"from": "LAHORE CANTT", "to": "RAWALPINDI",
                            "date": TOMORROW.isoformat()}


def test_the_other_answer_searches_the_other_station(railways: str) -> None:
    """The control: the answer is read, not ignored in favour of the first."""
    run = search("Lahore", "Rawalpindi", TOMORROW, [(f"{CHOICE_PREFIX}0", {})], railways)

    assert run.searched["from"] == "LAHORE JN"


def test_both_ends_can_need_asking_about(railways: str) -> None:
    run = search("Lahore", "Karachi", TOMORROW,
                 [(f"{CHOICE_PREFIX}1", {}), (f"{CHOICE_PREFIX}0", {})], railways)

    asked = [p["instruction"] for p in run.of("step.presented")
             if p["instruction"].startswith("Which")]
    assert asked == ["Which Lahore station do you mean?",
                     "Which Karachi station do you mean?"]
    assert run.searched["from"] == "LAHORE CANTT"
    assert run.searched["to"] == "KARACHI CANTT"


def test_a_place_that_already_names_one_station_is_not_asked_about(
    railways: str,
) -> None:
    run = search("Lahore Cantt", "Rawalpindi", TOMORROW, [], railways)

    assert not [p for p in run.of("step.presented") if p["instruction"].startswith("Which")]
    assert run.searched["from"] == "LAHORE CANTT"


def test_choosing_a_station_is_not_a_step_of_its_own(railways: str) -> None:
    """"Set the departure station" is one thing to agree to, though it takes
    typing a name, reading what came back, and then choosing (`Move.quiet`)."""
    run = search("Lahore", "Rawalpindi", TOMORROW, [(f"{CHOICE_PREFIX}0", {})], railways)

    instructions = [p["instruction"] for p in run.of("step.presented")]
    assert instructions.count("Let me set where you're starting from.") == 1
    assert run.of("task.completed")[0]["steps_taken"] == 5


# --- the sentence before the search ----------------------------------------


def test_the_journey_is_said_back_in_one_sentence_before_anything_is_searched(
    railways: str,
) -> None:
    """The last thing agreed to is the search, and what it says is the journey
    — so a person who is about to have the wrong thing looked up can see it."""
    run = search("Rawalpindi", "Multan", TOMORROW, [], railways)

    last = run.of("step.presented")[-1]
    assert last["instruction"] == confirm_search(
        "Rawalpindi", "Multan Cantt", day_words(TOMORROW, TODAY))
    assert last["instruction"].endswith("Shall I search?")
    assert "Nothing is booked." in last["detail"]


def test_the_sentence_names_the_station_that_was_chosen(railways: str) -> None:
    """Having asked which Lahore, it says which Lahore. The alternative is to
    repeat their own word back and leave the answer invisible."""
    run = search("Lahore", "Rawalpindi", TOMORROW, [(f"{CHOICE_PREFIX}1", {})], railways)

    last = run.of("step.presented")[-1]
    assert last["instruction"] == confirm_search(
        "Lahore Cantt", "Rawalpindi", day_words(TOMORROW, TODAY))


def test_the_day_is_written_the_way_a_person_says_it() -> None:
    assert day_words(date(2026, 10, 3), date(2026, 9, 30)) == "3 October"
    # The year only when it is not this one.
    assert day_words(date(2027, 1, 3), date(2026, 9, 30)) == "3 January 2027"


# --- when it cannot be done ------------------------------------------------


def test_a_place_the_site_has_no_station_for_stops_and_says_so(railways: str) -> None:
    run = search("Narnia", "Multan", TOMORROW, [], railways)

    assert run.of("help.requested")[0]["reason"] == no_station("Narnia")
    assert "task.completed" not in run.types()
    assert run.searched is None


def test_a_search_that_comes_back_with_nothing_says_that_rather_than_finishing(
    railways: str,
) -> None:
    """Quetta is in the list and has no trains. The search really happened and
    really returned nothing, which is not a failure of the run — but it is not
    an answer either, and `rows_at_least=1` is what notices."""
    run = search("Quetta", "Multan", TOMORROW, [], railways)

    assert run.searched == {"from": "QUETTA", "to": "MULTAN CANTT",
                            "date": TOMORROW.isoformat()}
    assert run.of("help.requested")[0]["reason"] == NO_TRAINS
    assert "task.completed" not in run.types()


# --- the check that makes a wrong search a failure -------------------------


def test_a_search_for_another_route_never_gets_sent(railways: str) -> None:
    """A run pointed at one journey and judged against another stops, and it
    stops *early* — the page is holding a station the task does not name, and
    that is noticed while the form is being filled rather than after a search.
    So the wrong search is never sent at all.

    The route is checked again on the page the run ends on, which is what
    catches a site that changes the answer underneath a filled form;
    `test_success_conditions.py` asserts that against the real snapshot,
    because no replica will search one route and report another.
    """
    asked_for = trip_task("Rawalpindi", "Peshawar", TOMORROW)

    run = search("Rawalpindi", "Multan", TOMORROW, [], railways, task=asked_for)

    assert run.searched is None
    assert "task.completed" not in run.types()
    assert "'To'" in run.of("help.requested")[0]["reason"]


def test_a_search_on_another_day_fails_rather_than_completing(railways: str) -> None:
    """The day is the case that reaches the end. Nothing types a date — it is
    picked out of the calendar — so nothing notices early, the search really is
    sent, real trains really come back, and the run still fails on the value
    the goal named. This is the 2026-09-09 failure, on a page, with the
    person's own day instead of the plan's (EVALUATION.md, case 6)."""
    asked_for = trip_task("Rawalpindi", "Multan", LATER)

    run = search("Rawalpindi", "Multan", TOMORROW, [], railways, task=asked_for)

    assert run.searched["date"] == TOMORROW.isoformat()
    reason = run.of("help.requested")[0]["reason"]
    assert "Departure Date" in reason and as_shown(LATER) in reason
    assert "task.completed" not in run.types()


def test_the_task_holds_all_three_things_the_person_said() -> None:
    task = trip_task("Lahore", "Rawalpindi", date(2026, 10, 3))

    held = {value.label: (value.equals, value.names) for value in task.about.holds}
    assert held == {
        "Departure Date": ("03-10-2026", False),
        "From": ("Lahore", True),
        "To": ("Rawalpindi", True),
    }
    assert [(answer.reads, answer.part) for answer in task.about.finds] == [
        ("Train No.", None), ("Time", 0), ("Time", 1), ("Duration", None)]


def test_the_fixed_plans_task_is_not_a_persons_task() -> None:
    """The worked example is still there, unchanged, and it is not what a
    typed goal runs."""
    assert RAILWAYS_TASK.goal != trip_task("Lahore", "Rawalpindi", TOMORROW).goal
    assert RAILWAYS_TASK.about.holds[0].names is False


# --- the parts, without a browser ------------------------------------------


def option(label: str, qualifier: str = "", panel: str = "") -> Element:
    return Element(id=1, role="option", label=label, type="option", tag="li",
                   input_type=None, qualifier=qualifier, panel=panel)


def textbox(label: str, value: str) -> Element:
    return Element(id=1, role="textbox", label=label, type="textbox", tag="input",
                   input_type="text", value=value)


def move_for(planner: TripPlanner, elements: list[Element]):
    return asyncio.run(planner.next_move(elements, [], None))


def test_more_stations_than_can_be_buttons_asks_for_more_of_the_name() -> None:
    """Five answers is a list to read, which is the thing this interface exists
    to spare someone. It asks them to narrow it instead, and then matches
    against both words."""
    offered = [option(f"{place} CANTT") for place in
               ("LAHORE", "KARACHI", "MULTAN", "PESHAWAR", "QUETTA")]
    planner = TripPlanner("Cantt", "Multan", TOMORROW, TODAY)

    question = move_for(planner, offered)

    assert question is not None and question.question is True
    assert "several Cantt stations" in question.instruction
    assert [f.id for f in question.fields] == ["station"]

    planner.answered("confirm", {"station": "Multan"})
    narrowed = move_for(planner, offered)
    assert narrowed is not None and narrowed.question is False


def test_a_station_the_person_narrowed_to_is_the_one_chosen() -> None:
    offered = [option("LAHORE JN"), option("LAHORE CANTT")]
    planner = TripPlanner("Lahore", "Multan", TOMORROW, TODAY)

    move_for(planner, offered)  # the question
    planner.answered(f"{CHOICE_PREFIX}1", {})
    chosen = move_for(planner, offered)

    assert chosen is not None
    assert chosen.operations[0].target.label == "LAHORE CANTT"
    assert chosen.quiet is True


def test_a_disabled_option_is_not_offered_as_an_answer() -> None:
    offered = [option("LAHORE JN"), option("LAHORE CANTT", qualifier="disabled")]
    planner = TripPlanner("Lahore", "Multan", TOMORROW, TODAY)

    chosen = move_for(planner, offered)

    assert chosen is not None and chosen.question is False
    assert chosen.operations[0].target.label == "LAHORE JN"


def test_a_calendar_showing_another_month_is_not_trusted() -> None:
    """A day cell says "3"; which 3 it is comes from the panel's own heading.
    Without that check the run would pick the third of whatever is on screen."""
    planner = TripPlanner("Rawalpindi", "Multan", date(2026, 10, 3), TODAY)
    planner.stations = {"origin": "RAWALPINDI", "destination": "MULTAN CANTT"}
    planner._done = {"choose origin", "choose destination", "open month"}

    wrong = move_for(planner, [option("3", panel="2026 September")])

    assert wrong is None
    assert planner.stuck_reason is not None


def test_a_form_that_no_longer_holds_the_journey_is_not_searched() -> None:
    """Checked again just before searching, where it stops a wrong search being
    sent at all rather than reporting one afterwards."""
    planner = TripPlanner("Rawalpindi", "Multan", TOMORROW, TODAY)
    planner.stations = {"origin": "RAWALPINDI", "destination": "MULTAN CANTT"}
    planner._done = {"choose origin", "choose destination", "pick day"}

    emptied = move_for(planner, [textbox("From", ""), textbox("To", "MULTAN CANTT"),
                                 textbox("Departure Date", as_shown(TOMORROW))])

    assert emptied is None
    assert planner.stuck_reason == FORM_CHANGED


def test_the_form_holding_the_journey_is_searched() -> None:
    planner = TripPlanner("Rawalpindi", "Multan", TOMORROW, TODAY)
    planner.stations = {"origin": "RAWALPINDI", "destination": "MULTAN CANTT"}
    planner._done = {"choose origin", "choose destination", "pick day"}

    move = move_for(planner, [textbox("From", "RAWALPINDI"),
                              textbox("To", "MULTAN CANTT"),
                              textbox("Departure Date", as_shown(TOMORROW))])

    assert move is not None and move.instruction.endswith("Shall I search?")


@pytest.mark.parametrize("start, end, presses", [
    (date(2026, 9, 30), date(2026, 9, 30), 0),
    (date(2026, 9, 30), date(2026, 10, 1), 1),
    (date(2026, 9, 30), date(2026, 12, 25), 3),
    (date(2026, 12, 1), date(2027, 1, 3), 1),
])
def test_how_many_times_next_month_is_pressed(start: date, end: date, presses: int) -> None:
    assert months_between(start, end) == presses


def test_a_task_built_for_a_journey_is_the_journey_it_says_it_is() -> None:
    task = trip_task("Lahore", "Rawalpindi", date(2026, 10, 3))
    assert "Lahore" in task.goal and "Rawalpindi" in task.goal
    assert "2026-10-03" in task.goal
    # And changing the goal's words does not change what is checked.
    assert replace(task, goal="trains to Pindi").about == task.about


# --- a station list that opens late -----------------------------------------
#
# On 2026-09-30 the live site's list for "Lahore" did not open within the five
# seconds every step was given, on either strategy, and the run said the site
# offered no stations for Lahore — a city with two on that list. A step that
# waits on a list the site fetches is given `LIST_TIMEOUT_S` now. The replica's
# `?list_delay_ms=` makes its list arrive late, the way the live one did.

LATE_MS = 8000  # past the ordinary window, well inside the list window


def late(railways: str) -> str:
    return f"{railways}/?list_delay_ms={LATE_MS}"


async def _type_then_verify(start_url: str, expect) -> tuple[str | None, float]:
    """Type a station name on a real page and time the verification."""
    import time

    from backend.orchestrator.loop import perceive, verify

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            await page.goto(start_url)
            _, before, _ = await perceive(page)
            await page.click("#from")
            await page.fill("#from", "LAHORE")
            started = time.monotonic()
            failure = await verify(page, before, expect)
            return failure, time.monotonic() - started
        finally:
            await browser.close()


def test_the_ordinary_window_misses_a_late_list(railways: str) -> None:
    """The defect, reproduced: an ordinary step's five seconds end before the
    list arrives, and what the check sees is a page with nothing on offer."""
    from backend.orchestrator.loop import LIST_TIMEOUT_S, VERIFY_TIMEOUT_S
    from backend.orchestrator.plan import Expectation

    failure, took = asyncio.run(
        _type_then_verify(late(railways), Expectation(label_like="Lahore")))

    assert failure is not None
    assert VERIFY_TIMEOUT_S - 0.5 < took < LIST_TIMEOUT_S


def test_a_step_that_waits_on_a_list_sees_it_arrive(railways: str) -> None:
    """The fix: the same page, the same typing, and the list is waited for.
    It took longer than the ordinary window, so the ordinary window could not
    have seen it."""
    from backend.orchestrator.loop import LIST_TIMEOUT_S, VERIFY_TIMEOUT_S
    from backend.orchestrator.plan import Expectation

    failure, took = asyncio.run(_type_then_verify(
        late(railways), Expectation(label_like="Lahore", list_opens=True)))

    assert failure is None
    assert VERIFY_TIMEOUT_S < took < LIST_TIMEOUT_S


def test_a_list_that_opens_quickly_costs_no_more_than_it_did(railways: str) -> None:
    """Polled, not slept: the longer window is only spent when it is needed."""
    from backend.orchestrator.loop import VERIFY_TIMEOUT_S
    from backend.orchestrator.plan import Expectation

    failure, took = asyncio.run(_type_then_verify(
        railways, Expectation(label_like="Lahore", list_opens=True)))

    assert failure is None
    assert took < VERIFY_TIMEOUT_S


def test_a_whole_journey_with_late_lists_is_searched(railways: str) -> None:
    """End to end, with both station lists arriving late: the station is asked
    about, chosen, and searched, and nothing fails along the way."""
    run = search("Lahore", "Rawalpindi", TOMORROW, [(f"{CHOICE_PREFIX}1", {})],
                 late(railways))

    assert "step.failed" not in run.types()
    assert "help.requested" not in run.types()
    assert run.searched == {"from": "LAHORE CANTT", "to": "RAWALPINDI",
                            "date": TOMORROW.isoformat()}


def test_typing_a_station_name_is_a_step_that_waits_on_a_list() -> None:
    planner = TripPlanner("Lahore", "Rawalpindi", TOMORROW, TODAY)

    typing = move_for(planner, [])

    assert typing is not None
    assert typing.expect.list_opens is True
    assert typing.expect.label_like == "Lahore"


def test_no_other_step_on_the_trip_waits_longer() -> None:
    """The longer window is for the one thing that is fetched. Choosing, the
    calendar and the search keep the ordinary one."""
    planner = TripPlanner("Rawalpindi", "Multan", TOMORROW, TODAY)
    planner.stations = {"origin": "RAWALPINDI", "destination": "MULTAN CANTT"}
    planner._done = {"choose origin", "choose destination", "pick day"}

    searching = move_for(planner, [textbox("From", "RAWALPINDI"),
                                   textbox("To", "MULTAN CANTT"),
                                   textbox("Departure Date", as_shown(TOMORROW))])
    choosing = move_for(TripPlanner("Rawalpindi", "Multan", TOMORROW, TODAY),
                        [option("RAWALPINDI")])

    assert searching is not None and searching.expect.list_opens is False
    assert choosing is not None and choosing.expect.list_opens is False


# --- one attempt for a step that waits on a list ----------------------------
#
# With two attempts, each waiting the full list window, a place with no station
# took 31.5s to be reported (EVALUATION.md, 2026-09-30b). Since 2026-10-01 a
# step that waits on a list gets one attempt: its longer wait is its second
# chance. Every other step keeps two, which `test_setback.py` and
# `test_durability.py` hold.


def test_a_place_with_no_station_is_reported_after_one_window(railways: str) -> None:
    import time

    from backend.orchestrator.loop import LIST_TIMEOUT_S

    started = time.monotonic()
    run = search("Narnia", "Multan", TOMORROW, [], railways)
    took = time.monotonic() - started

    assert run.of("help.requested")[0]["reason"] == no_station("Narnia")
    assert [f["strategies_tried"] for f in run.of("step.failed")] == [1]
    # One window and the page around it, not two windows.
    assert LIST_TIMEOUT_S < took < 2 * LIST_TIMEOUT_S


def test_a_late_list_is_still_found_with_one_attempt(railways: str) -> None:
    """What the second attempt was for, before the window was lengthened: a
    list that is late but does come. One attempt still sees it."""
    run = search("Rawalpindi", "Multan", TOMORROW, [], late(railways))

    assert "step.failed" not in run.types()
    assert run.searched["to"] == "MULTAN CANTT"
