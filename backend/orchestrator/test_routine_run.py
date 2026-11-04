"""Running a routine a helper showed (2026-11-04): from a tile, with no model.

The person presses the tile. SIMBA asks only what the helper said changes,
before the site is touched; runs the rest as the checklist, each move found
again by role and label on the page as it is now and checked like any other;
and shows the answer with the picture of the real page. When the site has
changed and a move cannot be found, it stops and says so — and offers a model
only when one is set up, and only if the person agrees.

On the billing copy in Chromium, with the real loop.
"""

import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from backend.orchestrator import voice
from backend.orchestrator.loop import Move, Snapshot, mismatch, run_brief
from backend.orchestrator.plan import Expectation
from backend.orchestrator.routine_plan import RoutineBrief, RoutinePlanner, routine_task
from backend.orchestrator.routines import Answer, Routine, Step
from backend.orchestrator.test_billing import REPO_ROOT, _wait_for
from backend.orchestrator.test_billing import billing_replica  # noqa: F401
from backend.orchestrator.test_checklist import Answers, run
from backend.perception.content import Content, Pair
from backend.perception.serializer import Element

REFERENCE = "04141234567890"
CHANGED_PORT = 5132


def the_bill(start: str, ask: bool = True) -> Routine:
    """The bill, as a helper shows it on the billing copy (`test_teach.py`)."""
    return Routine(
        id="r1", label="My bill", start=start,
        steps=(Step("click", "button", "Accept all cookies"),
               Step("fill", "textbox", "Reference No.", ask=ask,
                    value=None if ask else REFERENCE),
               Step("click", "button", "Check Bill", expect_url="/bill")),
        answer=Answer("Amount due", "P/WITHIN"))


class Scripted(Answers):
    """`Answers`, and the offer of a model answered from the script too: it
    is not one of the questions `Answers` knows by its buttons."""

    async def receive(self, message_type, step_index=None, on_other=None):
        steps = self.of("step.presented")
        if steps and steps[-1]["instruction"] == voice.ROUTINE_TRY and self.answers:
            self.shown += 1
            answer = self.answers.pop(0)
            return {"type": "step.response",
                    "payload": {"step_index": step_index, "action_id": answer[0],
                                "input_values": answer[1]}}
        return await super().receive(message_type, step_index, on_other)


def go(routine: Routine, answers, *, auto: bool = True, fallback=None) -> Answers:
    async def inner() -> Answers:
        connection = Scripted(answers)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await run_brief(page, connection, RoutineBrief(routine, fallback=fallback),
                                routine.start, auto=auto)
                connection.url = page.url
            finally:
                await browser.close()
        return connection

    return run(inner())


# --- the loop, for a routine ----------------------------------------------------------


def test_a_label_with_no_value_is_not_the_answer() -> None:
    expect = Expectation(has_value="P/WITHIN")
    said = Snapshot(url="u", title="t", labels=(), content=Content(pairs=[Pair("P/WITHIN", "1")]))
    blank = Snapshot(url="u", title="t", labels=(), content=Content(pairs=[Pair("Other", "1")]))
    assert mismatch(said, expect) is None
    assert "P/WITHIN" in mismatch(blank, expect)


def test_a_routine_is_never_cut_short_by_an_answer_already_there() -> None:
    planner = RoutinePlanner(the_bill("http://x/"), {1: REFERENCE})
    assert planner.must_finish and not planner.marks_changes
    assert planner.ran_out == voice.ROUTINE_NO_ANSWER


def test_the_task_reads_what_the_helper_pointed_at() -> None:
    task = routine_task(the_bill("http://x/"))
    assert task.success == Expectation(has_value="P/WITHIN")
    assert [(a.name, a.reads) for a in task.about.finds] == [("Amount due", "P/WITHIN")]
    assert task.scope == voice.ROUTINE_SCOPE and task.heading == "My bill"


# --- the billing copy -------------------------------------------------------------------


def test_the_bill_runs_from_its_tile_asking_only_the_number(billing_replica: str) -> None:
    done = go(the_bill(billing_replica), [("confirm", {"value1": REFERENCE})])

    # One question for the number, the cookie question, then the checklist.
    assert done.asked() == [voice.routine_ask("Reference No."), voice.ASK_COOKIES]
    assert done.rows() == [voice.doing_type("Reference No."), voice.doing_press("Check Bill")]
    ending = done.of("task.completed")[0]
    assert ending["llm_calls"] == 0
    assert ending["findings"][0]["label"] == "Amount due"
    assert ending["findings"][0]["values"] == ["14,382"]
    assert ending["heading"] == "My bill" and ending["scope"] == voice.ROUTINE_SCOPE
    # With the picture of the real page, the amount ringed.
    assert ending["proof"] is not None and len(ending["proof"]["rings"]) == 1


def test_a_value_the_same_every_time_is_not_asked(billing_replica: str) -> None:
    done = go(the_bill(billing_replica, ask=False), [("confirm", {})])
    assert done.asked() == [voice.ASK_COOKIES]
    assert done.of("task.completed")[0]["findings"][0]["values"] == ["14,382"]


def test_an_answer_left_empty_is_asked_again(billing_replica: str) -> None:
    done = go(the_bill(billing_replica), [("confirm", {"value1": "  "}),
                                          ("confirm", {"value1": REFERENCE})])
    asked = [p for p in done.of("step.presented") if p["requires_confirmation"]]
    assert asked[1]["note"] == voice.NOT_CAUGHT
    assert "task.completed" in done.types()


def test_asked_before_each_thing_every_move_asks(billing_replica: str) -> None:
    done = go(the_bill(billing_replica, ask=False), [("confirm", {})], auto=False)
    assert done.rows() == []
    assert done.asked() == [voice.ASK_COOKIES, voice.routine_do(Step(
        "fill", "textbox", "Reference No.")), voice.routine_do(Step("click", "button",
                                                                    "Check Bill"))]
    assert "task.completed" in done.types()


def test_an_answer_not_on_the_page_at_the_end_is_said_plainly(billing_replica: str) -> None:
    routine = replace(the_bill(billing_replica), answer=Answer("Amount due", "NO SUCH LABEL"))
    done = go(routine, [("confirm", {"value1": REFERENCE})])
    assert done.of("help.requested")[0]["reason"] == voice.ROUTINE_NO_ANSWER
    assert "task.completed" not in done.types()


# --- the honest stop -----------------------------------------------------------------------


@pytest.fixture(scope="module")
def changed_billing() -> str:
    """The billing copy after its search button was renamed: a site that
    changed after the helper showed it."""
    proc = subprocess.Popen(
        [sys.executable, "app.py"], cwd=REPO_ROOT / "replicas" / "billing",
        env={**os.environ, "PORT": str(CHANGED_PORT), "BILLING_CHECK_LABEL": "Find my bill"},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{CHANGED_PORT}"
    try:
        _wait_for(url)
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_a_changed_site_stops_honestly_and_says_to_show_it_again(changed_billing: str) -> None:
    done = go(the_bill(changed_billing), [("confirm", {"value1": REFERENCE})])
    help_ = done.of("help.requested")[0]
    assert help_["reason"] == voice.routine_changed("Check Bill")
    assert "show me again" in help_["reason"]
    # Nothing pressed that was not found, and no model was asked.
    assert done.url.rstrip("/") == changed_billing
    assert "task.completed" not in done.types()


class Model:
    """Stands in for the language model: counts what it is asked, and gives up."""

    def __init__(self) -> None:
        self.asked = 0
        self.calls_made = 0
        self.stuck_reason = "the model could not see a way on"

    async def next_move(self, elements, history, setback) -> Move | None:
        self.asked += 1
        return None


def test_with_a_model_set_up_the_person_is_asked_before_it_is_used(
        changed_billing: str) -> None:
    model = Model()
    declined = go(the_bill(changed_billing), [("confirm", {"value1": REFERENCE}),
                                              ("decline", {})],
                  fallback=lambda task: model)
    assert voice.ROUTINE_TRY in declined.asked()
    assert declined.of("help.requested")[0]["reason"] == voice.routine_changed("Check Bill")
    assert model.asked == 0

    agreed = go(the_bill(changed_billing), [("confirm", {"value1": REFERENCE}),
                                            ("confirm", {})],
                fallback=lambda task: model)
    assert model.asked == 1
    assert agreed.of("help.requested")[0]["reason"] == model.stuck_reason


# --- finding a move again ----------------------------------------------------------------


def _element(id: int, role: str, label: str, qualifier: str = "") -> Element:
    return Element(id=id, role=role, label=label, type="", tag="", input_type=None,
                   qualifier=qualifier)


def test_a_move_is_found_again_by_role_label_and_which_of_several() -> None:
    from backend.orchestrator.routine_plan import find

    links = [_element(4, "link", ""), _element(9, "link", ""), _element(11, "button", "")]
    assert find(links, Step("click", "link", "", nth=1)).id == 9
    assert find(links, Step("click", "link", "", nth=2)) is None
    days = [_element(1, "option", "30", "previous month"), _element(2, "option", "30")]
    assert find(days, Step("click", "option", "30", qualifier="previous month")).id == 1
    assert find(days, Step("click", "option", "30")).id == 1  # no qualifier kept: the first


def test_what_runs_by_itself_and_what_asks() -> None:
    planner = RoutinePlanner(Routine(
        id="r", label="x", start="http://127.0.0.1:1/",
        steps=(Step("fill", "textbox", "Name", value="A"),
               Step("click", "link", "Open the list"),
               Step("click", "button", "Accept cookies"),
               Step("click", "button", "Book now", changes=True),
               Step("fill", "textbox", "Password", secret=True)),
        answer=Answer("x", "y")), {})
    moves = [planner.move_for(index) for index in range(5)]
    assert [m.safe for m in moves] == [True, True, False, False, False]
    assert moves[2].actions == voice.yes_or_no() and moves[2].instruction == voice.ASK_COOKIES
    assert moves[3].changes
    assert moves[4].fields[0].type == "password" and moves[4].operations[0].value is None
    assert json.dumps([m.instruction for m in moves])


# --- a list the page draws itself ---------------------------------------------------------


def test_a_choice_in_a_list_is_made_by_its_words_and_checked() -> None:
    from backend.orchestrator.loop import attempt_move, perceive
    from backend.orchestrator.plan import Operation, Target

    page_html = ("data:text/html,<label>Class <select name=klass>"
                 "<option value=e>Economy</option><option value=b>Business</option>"
                 "</select></label>")

    async def inner() -> tuple[str | None, str]:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page()
            await page.goto(page_html)
            _, before, _ = await perceive(page)
            move = Move(instruction="", detail="", operations=[Operation(
                "select", Target("combobox", "Class"), value="Business")],
                expect=Expectation(), fields=[], actions=[])
            failure = await attempt_move(page, move, {}, 0, before)
            chosen = await page.eval_on_selector("select", "s => s.value")
            await browser.close()
            return failure, chosen

    failure, chosen = run(inner())
    assert failure is None and chosen == "b"


# --- from the tile, over the real websocket --------------------------------------------------

APP_PORT = 8044


@pytest.fixture(scope="module")
def app(billing_replica: str, tmp_path_factory):  # noqa: F811
    from backend.orchestrator.routines import RoutineStore

    folder = tmp_path_factory.mktemp("routine-run-app")
    routines = RoutineStore(folder / "routines.json")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.orchestrator.app:app",
         "--port", str(APP_PORT)], cwd=REPO_ROOT,
        env={**os.environ, "SIMBA_ROUTER": "keywords", "SIMBA_USE_HARDCODED_PLAN": "1",
             "SIMBA_RECORD_STEPS": "0", "SIMBA_ROUTINES": str(routines.path),
             "SIMBA_TILES": str(folder / "tiles.json"), "SIMBA_LOG_FILE": str(folder / "b.log"),
             "SIMBA_TRACE_DB": str(folder / "traces.db")},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        _wait_for(f"http://127.0.0.1:{APP_PORT}")
        yield {"routines": routines, "billing": billing_replica, "log": folder / "b.log"}
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_the_tile_runs_the_routine_and_no_word_typed_reaches_the_log(app: dict) -> None:
    import asyncio

    import websockets

    kept = app["routines"].add(the_bill(app["billing"]))

    async def talk() -> list[dict]:
        got: list[dict] = []
        async with websockets.connect(f"ws://127.0.0.1:{APP_PORT}/ws", max_size=None) as ws:
            seq = 0

            async def send(kind: str, payload: dict) -> None:
                nonlocal seq
                seq += 1
                await ws.send(json.dumps({"v": 1, "type": kind, "task_id": "t", "seq": seq,
                                          "ts": 0, "payload": payload}))

            got.append(json.loads(await asyncio.wait_for(ws.recv(), 10)))
            await send("task.start", {"goal": kept.label, "input_mode": "text",
                                      "routine": kept.id})
            while True:
                message = json.loads(await asyncio.wait_for(ws.recv(), 60))
                got.append(message)
                kind, payload = message["type"], message["payload"]
                if kind in ("task.completed", "task.failed", "help.requested"):
                    return got
                if kind == "step.presented" and payload["requires_confirmation"]:
                    values = {f["id"]: REFERENCE for f in payload["fields"]}
                    await send("step.response", {"step_index": payload["step_index"],
                                                 "action_id": "confirm",
                                                 "input_values": values})

    got = run(talk())
    ending = got[-1]
    assert ending["type"] == "task.completed", ending
    assert ending["payload"]["findings"][0]["values"] == ["14,382"]
    assert ending["payload"]["llm_calls"] == 0
    assert got[1]["payload"]["goal"] == "My bill"
    assert REFERENCE not in app["log"].read_text(encoding="utf-8")
