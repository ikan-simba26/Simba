"""The person decides, SIMBA clicks (2026-10-14).

Once the person has decided — the journey read back and agreed, the bill's
number given, the course chosen — the safe mechanical moves run without a press
each: each is one line of a checklist (`step.presented` with
`requires_confirmation: false`), acted on and verified like any other move.
What still asks: every question, a choice on someone else's site (cookies),
anything the person must type (signing in), anything that registers, pays,
books or changes a record, and the next move after anything goes wrong. The
person can pause between moves, and can choose to be asked every time.

On the real replicas in real Chromium, with the real loop.
"""

import asyncio
import concurrent.futures
from datetime import date, timedelta

from playwright.async_api import async_playwright

from backend.orchestrator import voice
from backend.orchestrator.details import BillBrief, CourseBrief, TripBrief, Understood, understand
from backend.orchestrator.loop import Move, Task, run_brief, run_task
from backend.orchestrator.plan import About, Expectation, Operation, Target
from backend.orchestrator.test_asking import OFFER_IDS, ScriptedConnection
from backend.orchestrator.test_billing import billing_replica  # noqa: F401
from backend.orchestrator.test_orchestrator import replica  # noqa: F401
from backend.orchestrator.test_trip_answers import railways  # noqa: F401
from backend.orchestrator.voice import CHOICE_PREFIX, TYPED_ANSWERS

TOMORROW = date.today() + timedelta(days=1)


class Answers(ScriptedConnection):
    """Answers each question in turn and agrees to every step that asks."""

    async def receive(self, message_type, step_index=None, on_other=None):  # noqa: ARG002
        self.shown += 1
        if self.offered():
            # The closing screen's offer: taken only when scripted.
            answer = (self.answers.pop(0) if self.answers and self.answers[0]
                      and self.answers[0][0] in OFFER_IDS else ("leave", {}))
            return {"type": "step.response",
                    "payload": {"step_index": 0, "action_id": answer[0], "input_values": {}}}
        step = self.of("step.presented")[-1]
        ids = [a["id"] for a in step["actions"]]
        question = any(i.startswith(CHOICE_PREFIX) for i in ids) or any(
            a["label"] in TYPED_ANSWERS for a in step["actions"])
        answer = ("confirm", {})
        if question or step["instruction"] == voice.PAUSED:
            answer = (self.answers.pop(0) if self.answers else None) or ("cancel", {})
        return {"type": "step.response",
                "payload": {"step_index": step_index, "action_id": answer[0],
                            "input_values": answer[1]}}

    def rows(self) -> list[str]:
        """The checklist: what SIMBA did without asking."""
        return [p["instruction"] for p in self.of("step.presented")
                if not p["requires_confirmation"]]

    def asked(self) -> list[str]:
        return [p["instruction"] for p in self.of("step.presented")
                if p["requires_confirmation"]]


class Counting:
    """A recorder that only counts what it is given."""

    def __init__(self) -> None:
        self.steps: list[str] = []

    def note_step(self, index, *, goal, url, instruction, features) -> None:  # noqa: ARG002
        self.steps.append(instruction)

    def note_telemetry(self, sample) -> None:  # noqa: ARG002
        pass

    def note_decision(self, decision) -> None:  # noqa: ARG002
        pass


def run(coroutine):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coroutine).result()


def go(start_url: str, brief, answers, *, auto=True, pause_on_poll=None, recorder=None,
       planner_task=None) -> Answers:
    async def inner() -> Answers:
        connection = Answers(answers)
        connection.pause_on_poll = pause_on_poll
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                if planner_task is not None:
                    planner, task = planner_task
                    await run_task(page, connection, planner, task, start_url, recorder,
                                   auto=auto)
                else:
                    await run_brief(page, connection, brief, start_url, recorder, auto=auto)
                connection.searched = await page.evaluate("window.__searched || null")
            finally:
                await browser.close()
        return connection

    return run(inner())


def a_journey() -> TripBrief:
    known = run(understand("railways", "trains from Rawalpindi to Sukkur tomorrow"))
    return TripBrief("trains from Rawalpindi to Sukkur tomorrow", known)


# --- the train search ----------------------------------------------------------------


def test_after_the_readback_the_search_runs_as_a_checklist(railways: str) -> None:  # noqa: F811
    done = go(railways, a_journey(), [(f"{CHOICE_PREFIX}0", {})])

    assert done.asked() == [voice.read_back("Rawalpindi", "Sukkur",
                                            voice.when_words(TOMORROW, date.today()))]
    assert done.rows() == [voice.DOING_FROM, voice.DOING_TO, voice.DOING_CALENDAR,
                           voice.doing_day(voice.day_words(TOMORROW, date.today())),
                           voice.DOING_SEARCH]
    assert done.searched == {"from": "RAWALPINDI", "to": "SUKKUR",
                             "date": TOMORROW.isoformat()}
    assert "task.completed" in done.types()
    # The results say what they are for, and each train when it leaves and
    # arrives, read from the page's one `Time` cell (2026-10-14).
    ending = done.of("task.completed")[0]
    assert ending["heading"] == voice.route_heading("Rawalpindi", "Sukkur", TOMORROW,
                                                    date.today())
    # The last line: nothing was booked or paid (2026-10-16).
    assert ending["scope"] == voice.ONLY_LOOKED_UP_TIMES
    rows = ending["findings"][0]["rows"]
    labels = [f["label"] for f in ending["findings"]]
    assert labels == ["Train", "Leaves", "Arrives", "Journey"]
    assert all(len(row) == 4 and all(row) for row in rows), rows
    # Every line was in the Search stage.
    assert {p["stage"] for p in done.of("step.presented")
            if not p["requires_confirmation"]} == {3}
    # Each line says what is still to come, so the list shrinks to nothing
    # (`coming`, 2026-10-15).
    lines = [p for p in done.of("step.presented") if not p["requires_confirmation"]]
    assert [p["coming"] for p in lines] == [done.rows()[i + 1:] for i in range(5)]


def test_asked_every_time_it_asks_every_time(railways: str) -> None:  # noqa: F811
    """The person's setting: the way SIMBA always worked."""
    done = go(railways, a_journey(), [(f"{CHOICE_PREFIX}0", {})], auto=False)

    assert done.rows() == []
    assert len(done.asked()) == 1 + 5
    assert "task.completed" in done.types()


def test_pause_stops_before_the_next_move_and_carry_on_finishes(railways: str) -> None:  # noqa: F811
    done = go(railways, a_journey(), [(f"{CHOICE_PREFIX}0", {}), ("confirm", {})],
              pause_on_poll=3)

    assert voice.PAUSED in done.asked()
    # Two lines before the pause, the rest after it.
    assert len(done.rows()) == 5
    assert done.asked().index(voice.PAUSED) == 1
    assert "task.completed" in done.types()


def test_stopping_at_the_pause_searches_nothing(railways: str) -> None:  # noqa: F811
    done = go(railways, a_journey(), [(f"{CHOICE_PREFIX}0", {}), None], pause_on_poll=3)

    assert done.rows() == [voice.DOING_FROM, voice.DOING_TO]
    assert done.searched is None
    assert "task.failed" in done.types()


def test_nothing_about_the_person_is_recorded_for_a_checklist_line(railways: str) -> None:  # noqa: F811
    """There was no decision to measure. Hesitation is measured on questions,
    and on the moves that still ask."""
    recorder = Counting()
    done = go(railways, a_journey(), [(f"{CHOICE_PREFIX}0", {})], recorder=recorder)

    assert recorder.steps == done.asked()


# --- the bill and the course ------------------------------------------------------------


def test_the_bill_asks_about_cookies_then_looks_itself_up(
    billing_replica: str,  # noqa: F811
) -> None:
    """Accepting cookies is consent on someone else's site: it asks. Looking
    up the number the person gave does not. (Opening the full bill afterwards
    was a second line until 2026-10-16; the run now ends on the results.)"""
    brief = BillBrief("check my bill 04141234567890", Understood(reference="04141234567890"))

    done = go(billing_replica, brief, [])

    assert done.asked() == [voice.ASK_COOKIES]
    assert done.rows() == [voice.DOING_LOOKUP]
    assert "task.completed" in done.types()
    lines = [p for p in done.of("step.presented") if not p["requires_confirmation"]]
    assert [p["coming"] for p in lines] == [[]]


def test_the_cookie_question_is_yes_or_no(billing_replica: str) -> None:  # noqa: F811
    """Asked, never told (2026-10-16): Yes, No, and the way to stop."""
    brief = BillBrief("check my bill 04141234567890", Understood(reference="04141234567890"))

    done = go(billing_replica, brief, [])

    cookies = done.of("step.presented")[0]
    assert cookies["instruction"] == "This site asks about cookies. Shall I say yes?"
    assert [(a["id"], a["label"]) for a in cookies["actions"]] == [
        ("confirm", "Yes"), (voice.DECLINE_ID, "No"), ("cancel", "Stop this")]


def test_no_to_cookies_leaves_them_and_still_finds_the_bill(
    billing_replica: str,  # noqa: F811
) -> None:
    """No is an answer, not a stop: the banner is left as it is, and the
    bill is still looked up."""

    class SaysNo(Answers):
        async def receive(self, message_type, step_index=None, on_other=None):
            step = self.of("step.presented")[-1]
            if step["instruction"] == voice.ASK_COOKIES:
                self.shown += 1
                return {"type": "step.response", "payload": {
                    "step_index": step_index, "action_id": voice.DECLINE_ID,
                    "input_values": {}}}
            return await super().receive(message_type, step_index, on_other)

    async def inner() -> SaysNo:
        connection = SaysNo([])
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                brief = BillBrief("b", Understood(reference="04141234567890"))
                await run_brief(page, connection, brief, billing_replica, auto=True)
                connection.searched = await page.locator("#cookie-bar").is_visible()
            finally:
                await browser.close()
        return connection

    done = run(inner())

    assert "task.failed" not in done.types()
    assert done.of("task.completed")[0]["findings"][0]["values"] == ["Rs 14,382"]
    assert done.searched is True  # the banner was never accepted


def test_registering_always_asks(replica: str) -> None:  # noqa: F811
    """Signing in needs the person to type; registering registers. Only
    closing the portal's notice runs by itself."""

    class SignsIn(Answers):
        async def receive(self, message_type, step_index=None, on_other=None):
            step = self.of("step.presented")[-1]
            if any(f["id"] == "password" for f in step["fields"]):
                self.shown += 1
                return {"type": "step.response", "payload": {
                    "step_index": step_index, "action_id": "confirm",
                    "input_values": {"username": "student", "password": "anything"}}}
            return await super().receive(message_type, step_index, on_other)

    brief = CourseBrief("register for CS-401", Understood(course="CS-401"))

    async def inner():
        connection = SignsIn([])
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await run_brief(page, connection, brief, replica, auto=True)
            finally:
                await browser.close()
        return connection

    done = run(inner())

    assert done.rows() == [voice.DOING_NOTICE]
    assert done.asked() == ["Let me sign you in first.",
                            voice.final_register("CS-401")]
    assert "task.completed" in done.types()


# --- when something goes wrong ------------------------------------------------------------


class GoesWrong:
    """A safe move that cannot work, then a safe move that can."""

    calls_made = 0

    def __init__(self) -> None:
        self.made = 0

    async def next_move(self, elements, history, setback):  # noqa: ARG002
        self.made += 1
        if self.made == 1:
            return Move(instruction="Press a button that is not there.", detail="",
                        operations=[Operation("click", Target("button", "Not on this page"))],
                        expect=Expectation(), fields=[], actions=voice.actions("Press it"),
                        safe=True, doing="Pressing a button that is not there")
        if self.made == 2:
            return Move(instruction="Fill in the username.", detail="",
                        operations=[Operation("fill", Target("textbox",
                                                             "Student ID or Username"),
                                              value="student")],
                        expect=Expectation(), fields=[], actions=voice.actions("Fill it in"),
                        safe=True, doing="Filling in the username")
        return None


def test_after_a_move_goes_wrong_the_next_one_asks(replica: str) -> None:  # noqa: F811
    task = Task(goal="g", estimated_steps=2, about=About())

    done = go(replica, None, [], planner_task=(GoesWrong(), task))

    assert done.rows() == ["Pressing a button that is not there"]
    assert "step.failed" in done.types()
    assert done.asked() == ["Fill in the username."]
