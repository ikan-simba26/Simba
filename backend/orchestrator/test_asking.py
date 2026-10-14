"""Asking the person for what their goal left out.

A goal rarely names everything a task needs. "Trains to Rawalpindi tomorrow"
does not say where from; "check my bill" does not say which bill. Until
2026-09-30 the run used the plan's values anyway, so what came back was a real
answer to somebody else's question.

Two things ask now, and this file is about both of them as the loop sees them,
with a stub in place of the real briefs and planners so that what is tested is
the loop's behaviour and not theirs (`test_details.py` covers the reading, and
`test_trip.py` the station questions):

  * **Before the run** — a `Brief` (`loop.run_brief`). One question at a time,
    as an ordinary `step.presented`, with the site open behind them and
    nothing on it touched until every answer is in.
  * **During the run** — a planner's `Move(question=True)`, for something only
    the page can raise: which of two stations in one city was meant.

And the two things a question is not. It is not a step: `steps_taken` counts
what the person agreed to have done, and answering a question is not that. And
its answer is not a stop — `is_answer` is the one place that decides, and
`frontend/test_questions.py` holds the overlay to the same line.

A real browser and the real registration replica, because `run_brief` reads
the page to have something to show for "What are you doing?" before it asks
anything. Nothing here registers for anything: the stub planners stop.
"""

import asyncio
from dataclasses import dataclass, field

import pytest
from playwright.async_api import async_playwright

from backend.orchestrator.loop import (
    Connection,
    Move,
    Task,
    is_answer,
    run_brief,
    run_task,
)
from backend.orchestrator.plan import About, Expectation, Operation, Target
from backend.orchestrator.test_orchestrator import REPLICA_URL, replica  # noqa: F401
from backend.orchestrator.voice import CANCEL_ID, CHOICE_PREFIX, USE_STATION, actions, choices
from shared.schema import StepAction, StepField

# The answers a run is driven with, in the order the questions come. `None`
# means press stop.
Answers = list[tuple[str, dict[str, str]] | None]

NOTHING_HELD = Task(goal="g", estimated_steps=4, about=About())


class ScriptedConnection(Connection):
    """Records what the loop emits, and answers each thing it shows in turn.

    An answer the script has run out of is go-ahead, so a run that shows more
    than was scripted still finishes rather than hanging.
    """

    def __init__(self, answers: Answers | None = None) -> None:
        self.sent: list[tuple[str, dict]] = []
        self.answers: Answers = list(answers or [])
        self.shown = 0
        #: The checklist's Pause (2026-10-14): pressed on this call to `poll`.
        self.pause_on_poll: int | None = None
        self.polls = 0

    async def poll(self, seconds: float = 0.0) -> list[dict]:  # noqa: ARG002
        self.polls += 1
        if self.pause_on_poll == self.polls:
            return [{"type": "step.response",
                     "payload": {"step_index": 0, "action_id": "pause", "input_values": {}}}]
        return []

    async def send(self, message_type: str, payload) -> None:
        self.sent.append((message_type, payload.model_dump()))

    async def receive(self, message_type: str, step_index: int | None = None,
                      on_other=None) -> dict:  # noqa: ARG002
        self.shown += 1
        answer = self.answers.pop(0) if self.answers else ("confirm", {})
        if answer is None:
            answer = (CANCEL_ID, {})
        return {
            "type": "step.response",
            "payload": {"step_index": step_index, "action_id": answer[0],
                        "input_values": answer[1]},
        }

    def types(self) -> list[str]:
        return [message_type for message_type, _ in self.sent]

    def of(self, message_type: str) -> list[dict]:
        return [payload for name, payload in self.sent if name == message_type]

    def instructions(self) -> list[str]:
        return [payload["instruction"] for payload in self.of("step.presented")]

    def labels(self, index: int) -> list[str]:
        return [a["label"] for a in self.of("step.presented")[index]["actions"]]

    def ids(self, index: int) -> list[str]:
        return [a["id"] for a in self.of("step.presented")[index]["actions"]]


# --- the stubs --------------------------------------------------------------


def a_question(instruction: str, labels: list[str]) -> Move:
    return Move(instruction=instruction, detail="", operations=[], expect=Expectation(),
                fields=[], actions=choices(labels), question=True)


def a_typed_question(instruction: str, field_id: str) -> Move:
    return Move(instruction=instruction, detail="", operations=[], expect=Expectation(),
                fields=[StepField(id=field_id, label=field_id.title(), type="text", value="")],
                actions=actions(USE_STATION), question=True)


class StoppedPlanner:
    """Settles the argument about what a task is by not doing anything."""

    calls_made = 0

    async def next_move(self, elements, history, setback):  # noqa: ARG002
        return None


@dataclass
class StubBrief:
    """Two things missing: which day, and where from. Asked in that order."""

    goal: str = "trains to Rawalpindi tomorrow"
    #: Two questions, then the plan's three steps.
    estimated_steps: int = 5
    gave_up: str | None = None
    day: str | None = None
    origin: str | None = None
    #: Every answer handed back, for the tests that care that it arrived.
    heard: list[tuple[str, dict]] = field(default_factory=list)
    #: Set when a brief cannot make sense of what it is told.
    give_up_after: int | None = None
    asked: int = 0

    def question(self) -> Move | None:
        if self.gave_up is not None:
            return None
        if self.day is None:
            self.asked += 1
            return a_question("What day are you travelling?",
                              ["Today", "Tomorrow", "Pick a day"])
        if self.origin is None:
            self.asked += 1
            return a_typed_question("Where are you travelling from?", "origin")
        return None

    def answered(self, action_id: str, input_values: dict[str, str]) -> None:
        self.heard.append((action_id, input_values))
        if self.give_up_after is not None and len(self.heard) >= self.give_up_after:
            self.gave_up = "I asked a few times and still couldn't work out what you meant."
            return
        if self.day is None:
            self.day = action_id
            return
        self.origin = input_values.get("origin") or None
        if self.origin is None:
            self.gave_up = "I asked a few times and still couldn't work out what you meant."

    def settle(self) -> tuple[StoppedPlanner, Task]:
        return StoppedPlanner(), Task(
            goal=f"Find trains from {self.origin} on {self.day}.",
            estimated_steps=self.estimated_steps, about=About())


class AsksMidRun:
    """A planner that has to ask before it can go on, the way `TripPlanner`
    does when a place names more than one station."""

    calls_made = 0

    def __init__(self, moves: list[Move]) -> None:
        self.moves = list(moves)
        self.heard: list[tuple[str, dict]] = []

    async def next_move(self, elements, history, setback):  # noqa: ARG002
        return self.moves.pop(0) if self.moves else None

    def answered(self, action_id: str, input_values: dict[str, str]) -> None:
        self.heard.append((action_id, input_values))


# --- driving it -------------------------------------------------------------


def ask(brief: StubBrief, answers: Answers, start_url: str) -> ScriptedConnection:
    async def go() -> ScriptedConnection:
        connection = ScriptedConnection(answers)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await run_brief(page, connection, brief, start_url)
                connection.final_url = page.url  # type: ignore[attr-defined]
            finally:
                await browser.close()
        return connection

    return asyncio.run(go())


def plan_with(planner, answers: Answers, start_url: str) -> ScriptedConnection:
    async def go() -> ScriptedConnection:
        connection = ScriptedConnection(answers)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await run_task(page, connection, planner, NOTHING_HELD, start_url)
                connection.final_url = page.url  # type: ignore[attr-defined]
                # What the page ended up holding, for the tests that care that
                # something really was done to it rather than merely reported.
                connection.typed = await page.input_value("#username")  # type: ignore[attr-defined]
            finally:
                await browser.close()
        return connection

    return asyncio.run(go())


ANSWER_BOTH: Answers = [(f"{CHOICE_PREFIX}1", {}), ("confirm", {"origin": "Lahore"})]


# --- one question at a time, before anything is touched ---------------------


def test_the_questions_come_one_at_a_time_and_in_order(replica: str) -> None:  # noqa: F811
    brief = StubBrief()

    connection = ask(brief, ANSWER_BOTH, replica)

    assert connection.instructions()[:2] == [
        "What day are you travelling?",
        "Where are you travelling from?",
    ]
    # Each one was answered before the next was asked.
    assert brief.asked == 2
    assert [action_id for action_id, _ in brief.heard] == [f"{CHOICE_PREFIX}1", "confirm"]


def test_the_answers_reach_the_brief(replica: str) -> None:  # noqa: F811
    brief = StubBrief()

    ask(brief, ANSWER_BOTH, replica)

    assert brief.day == f"{CHOICE_PREFIX}1"
    assert brief.origin == "Lahore"


def test_the_site_is_open_behind_the_questions_and_untouched(replica: str) -> None:  # noqa: F811
    """Open, so "What are you doing?" has a page to show and the level rules
    have one to weigh. Untouched, because nothing has been agreed to yet."""
    connection = ask(StubBrief(), ANSWER_BOTH, replica)

    assert connection.final_url.rstrip("/") == replica.rstrip("/")  # type: ignore[attr-defined]
    assert "step.failed" not in connection.types()


def test_a_question_offers_its_answers_as_buttons_and_one_way_to_stop(
    replica: str,  # noqa: F811
) -> None:
    connection = ask(StubBrief(), ANSWER_BOTH, replica)

    assert connection.labels(0) == ["Today", "Tomorrow", "Pick a day", "Stop this"]
    assert connection.ids(0) == [f"{CHOICE_PREFIX}0", f"{CHOICE_PREFIX}1",
                                 f"{CHOICE_PREFIX}2", CANCEL_ID]
    # The typed one has a box and the button that finishes it.
    typed = connection.of("step.presented")[1]
    assert [f["id"] for f in typed["fields"]] == ["origin"]
    assert connection.labels(1) == [USE_STATION, "Stop this"]


def test_the_count_does_not_grow_as_the_questions_are_answered(
    replica: str,  # noqa: F811
) -> None:
    """What is on screen is question 1 of 5, not 1 of 1 and then 2 of 2: the
    total is everything still to come, read before the first question."""
    connection = ask(StubBrief(), ANSWER_BOTH, replica)

    shown = connection.of("step.presented")
    assert [s["step_index"] for s in shown] == [1, 2]
    assert {s["step_total"] for s in shown} == {5}
    assert connection.of("task.started")[0]["estimated_steps"] == 5


# --- a question is not a step ----------------------------------------------


def test_answering_questions_is_not_counted_as_doing_steps(
    replica: str,  # noqa: F811
) -> None:
    """`steps_taken` is what the person agreed to have done to the site. They
    agreed to nothing here; they answered two questions."""
    connection = ask(StubBrief(), ANSWER_BOTH, replica)

    completed = connection.of("task.completed")[0]
    assert completed["steps_taken"] == 0
    assert connection.shown == 2


def test_a_question_a_planner_asks_mid_run_goes_back_to_the_planner(
    replica: str,  # noqa: F811
) -> None:
    planner = AsksMidRun([a_question("Which Lahore station do you mean?",
                                     ["Lahore Jn", "Lahore Cantt"])])

    connection = plan_with(planner, [(f"{CHOICE_PREFIX}1", {})], replica)

    # Asked, answered, and nothing done to the page on the strength of it.
    assert planner.heard == [(f"{CHOICE_PREFIX}1", {})]
    assert connection.typed == ""  # type: ignore[attr-defined]
    assert connection.instructions() == ["Which Lahore station do you mean?"]
    assert connection.of("task.completed")[0]["steps_taken"] == 0


def test_a_quiet_move_is_done_without_being_shown_again(replica: str) -> None:  # noqa: F811
    """The rest of a step already agreed to. Typing a station name and then
    choosing from the list the site offers is one thing to agree to, and the
    choice cannot be known until the page has been looked at."""
    quiet = Move(
        instruction="Let me sign you in first.", detail="",
        operations=[Operation("fill", Target("textbox", "Student ID or Username"),
                              value="raham")],
        expect=Expectation(), fields=[], actions=actions("Sign in"), quiet=True,
    )

    connection = plan_with(AsksMidRun([quiet]), [], replica)

    # Nothing was shown, and the page was really filled in all the same.
    assert connection.instructions() == []
    assert connection.typed == "raham"  # type: ignore[attr-defined]
    assert connection.of("task.completed")[0]["steps_taken"] == 0
    assert "step.failed" not in connection.types()


# --- the ways it ends ------------------------------------------------------


def test_stopping_at_a_question_stops_the_task(replica: str) -> None:  # noqa: F811
    brief = StubBrief()

    connection = ask(brief, [None], replica)

    assert connection.of("task.failed")[0]["reason"] == "You asked me to stop."
    assert connection.instructions() == ["What day are you travelling?"]
    assert brief.heard == []
    assert "task.completed" not in connection.types()


def test_stopping_at_a_planners_question_stops_the_task(replica: str) -> None:  # noqa: F811
    planner = AsksMidRun([a_question("Which Lahore station do you mean?", ["Jn", "Cantt"])])

    connection = plan_with(planner, [None], replica)

    assert connection.of("task.failed")[0]["reason"] == "You asked me to stop."
    assert planner.heard == []


def test_a_brief_that_cannot_make_sense_of_the_answers_gives_up_and_says_why(
    replica: str,  # noqa: F811
) -> None:
    """Being stuck, not being silent. Asked too many times, the run ends the
    way any stuck run does, and the site was never touched."""
    brief = StubBrief(give_up_after=1)

    connection = ask(brief, [(f"{CHOICE_PREFIX}0", {})], replica)

    assert connection.of("state.changed")[-1]["state"] == "stuck"
    reason = connection.of("help.requested")[0]["reason"]
    assert reason == "I asked a few times and still couldn't work out what you meant."
    assert "task.completed" not in connection.types()


def test_a_goal_that_says_everything_asks_nothing(replica: str) -> None:  # noqa: F811
    """The control. Nothing missing, no question, straight to the task."""
    brief = StubBrief(day="Tomorrow", origin="Lahore")

    connection = ask(brief, [], replica)

    assert connection.instructions() == []
    assert connection.types()[0] == "task.started"
    assert "task.completed" in connection.types()




# --- the count on screen ----------------------------------------------------


class CountsDifferently(StubBrief):
    """A brief whose settled task carries its own, smaller count.

    Which is every real brief: `TripBrief` promises its questions *and* the
    five steps of the journey, and `trip_task` knows only about the five.
    """

    def settle(self):
        return StoppedPlanner(), Task(goal="spelled out", estimated_steps=2, about=About())


def test_the_count_never_goes_backwards_across_the_questions(
    replica: str,  # noqa: F811
) -> None:
    """Found on 2026-09-30 in a run of "trains to Rawalpindi tomorrow": the
    screen said 1 of 7, then 2 of 5. The questions counted the one on screen
    twice, and the steps after them counted none of the questions at all — so
    the number both overstated and then shrank, in one run, while the person
    was being asked things."""
    brief = CountsDifferently()

    connection = ask(brief, ANSWER_BOTH, replica)

    totals = [(s["step_index"], s["step_total"]) for s in connection.of("step.presented")]
    assert totals, "nothing was shown"
    assert [total for _, total in totals] == sorted(total for _, total in totals)
    for index, total in totals:
        assert total >= index, totals
    # And it is what the person was promised, not what the settled task knows.
    assert connection.of("task.started")[0]["estimated_steps"] == brief.estimated_steps
    assert {total for _, total in totals} == {brief.estimated_steps}


# --- which answer stops --------------------------------------------------


@pytest.mark.parametrize("action_id", [f"{CHOICE_PREFIX}0", f"{CHOICE_PREFIX}2", "confirm"])
def test_every_answer_but_the_one_that_stops_is_an_answer(action_id: str) -> None:
    question = a_question("Which day?", ["Today", "Tomorrow", "Pick a day"])
    question.actions.append(StepAction(id="confirm", label=USE_STATION, kind="primary"))
    assert is_answer(question, action_id)


def test_the_one_that_stops_is_not_an_answer() -> None:
    assert not is_answer(a_question("Which day?", ["Today"]), CANCEL_ID)


def test_an_id_the_question_never_offered_is_not_an_answer() -> None:
    """A response that names nothing on the step is not taken for agreement."""
    assert not is_answer(a_question("Which day?", ["Today"]), f"{CHOICE_PREFIX}9")
    assert not is_answer(a_question("Which day?", ["Today"]), None)
