"""The full loop on a second site, hardcoded plan, no model in the loop.

The point is not that billing works — it is that the loop, verification and
recovery were written against the registration replica and have to hold on a
page with different chrome, different blocking, and a different shape of goal.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest
import websockets
from playwright.async_api import async_playwright

from backend.orchestrator.billing_plan import (
    BILLING_PLAN,
    BILLING_TASK,
    REFERENCE,
    bill_task,
    billing_plan,
    person_billing_plan,
)
from backend.orchestrator.details import BillBrief, Understood
from backend.orchestrator.loop import run_task
from backend.orchestrator.plan import (
    Expectation,
    HardcodedPlanner,
    Operation,
    PlanStep,
    Target,
)
from backend.orchestrator.test_verification import FakeConnection

REPO_ROOT = Path(__file__).resolve().parents[2]
REPLICA_URL = "http://127.0.0.1:5101"
ORCHESTRATOR_URL = "http://127.0.0.1:8021"
WS_URL = "ws://127.0.0.1:8021/ws"


def _wait_for(url: str, timeout_s: float = 30.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.2)
    raise RuntimeError(f"nothing came up at {url}")


@pytest.fixture(scope="module")
def billing_replica() -> Iterator[str]:
    proc = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=REPO_ROOT / "replicas" / "billing",
        env={**os.environ, "PORT": "5101"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for(REPLICA_URL)
        yield REPLICA_URL
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def drive(planner, task, start_url: str) -> FakeConnection:
    async def go() -> FakeConnection:
        connection = FakeConnection()
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await run_task(page, connection, planner, task, start_url)
            finally:
                await browser.close()
        return connection

    return asyncio.run(go())


# --- in process --------------------------------------------------------------


def test_the_hardcoded_plan_reaches_the_bill_detail(billing_replica: str) -> None:
    connection = drive(HardcodedPlanner(BILLING_PLAN), BILLING_TASK, billing_replica)

    assert "help.requested" not in connection.types(), connection.sent[-1]
    completed = connection.payload_of("task.completed")
    assert completed["steps_taken"] == 3
    assert completed["llm_calls"] == 0


def test_the_answer_reaches_the_end_from_a_page_the_run_has_left(billing_replica: str) -> None:
    """What `About.finds` is for, end to end, on the real replica.

    The amount and the due date are only in the results table. The run then
    opens the detail page, where neither column exists — so these values in
    `task.completed` can only have come from remembering them. Until
    2026-09-17 nothing tested that the answer reached the end at all.

    The due date is exactly as the page wrote it. Nothing reformats a found
    value (STATUS.md).
    """
    connection = drive(HardcodedPlanner(BILLING_PLAN), BILLING_TASK, billing_replica)

    completed = connection.payload_of("task.completed")
    assert completed["findings"] == [
        # Both forms of each answer: the line the step screen shows, and the
        # list the closing screen shows. One value, so they say the same thing.
        # And the bill's one table row whole, on the first finding: the amount
        # and the date due, from the same row (2026-10-05).
        {"label": "Your bill", "value": "14,382", "values": ["14,382"],
         "rows": [["14,382", "15-09-2026"]]},
        {"label": "Due", "value": "15-09-2026", "values": ["15-09-2026"], "rows": []},
    ]
    # And it was shown while the run was still going, from the step it turned up on.
    assert connection.of("step.presented")[-1]["findings"] == completed["findings"]


def test_the_reference_number_is_actually_typed(billing_replica: str) -> None:
    """A fill is verified by reading the field back, on this site too."""
    connection = drive(HardcodedPlanner(BILLING_PLAN), BILLING_TASK, billing_replica)

    lookup = connection.of("step.presented")[1]
    assert lookup["fields"][0]["id"] == "reference"
    assert "task.completed" in connection.types()


def test_verification_catches_a_wrong_expectation_here_too(billing_replica: str) -> None:
    """Same failure shape as on registration, on a different site."""
    plan = [
        PlanStep(
            instruction="Dismiss the cookie notice.",
            detail="",
            actions=[],
            operations=[Operation("click", Target("button", "Accept all cookies"))],
            expect=Expectation(url_contains="/nowhere-at-all"),
        )
    ] * 3

    connection = drive(HardcodedPlanner(plan), BILLING_TASK, billing_replica)

    assert "task.completed" not in connection.types()
    assert "help.requested" in connection.types()
    assert [s for n, s in connection.sent if n == "state.changed"][-1] == {"state": "stuck"}


def test_a_missing_element_is_reported_by_name(billing_replica: str) -> None:
    plan = [
        PlanStep(
            instruction="Click something absent.",
            detail="",
            actions=[],
            operations=[Operation("click", Target("button", "Pay Now With Card"))],
            expect=Expectation(url_contains="/bill"),
        )
    ]

    connection = drive(HardcodedPlanner(plan), BILLING_TASK, billing_replica)

    assert "could not find 'Pay Now With Card'" in (
        connection.payload_of("help.requested")["reason"]
    )


# --- over a real WebSocket ---------------------------------------------------


@pytest.fixture(scope="module")
def orchestrator(billing_replica: str) -> Iterator[str]:
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.orchestrator.app:app", "--port", "8021"],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "SIMBA_FLOW": "billing",
            "SIMBA_USE_HARDCODED_PLAN": "1",
            "SIMBA_REPLICA_URL": billing_replica,
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for(ORCHESTRATOR_URL)
        yield WS_URL
    finally:
        proc.terminate()
        proc.wait(timeout=10)


async def _run_flow(ws_url: str) -> list[dict]:
    received: list[dict] = []
    seq = 0
    async with websockets.connect(ws_url, max_size=None) as ws:

        async def send(message_type: str, payload: dict) -> None:
            nonlocal seq
            seq += 1
            await ws.send(json.dumps({
                "v": 1, "type": message_type, "task_id": "t_test",
                "seq": seq, "ts": 0, "payload": payload,
            }))

        await send("task.start", {"goal": BILLING_TASK.goal, "input_mode": "text"})
        while True:
            message = json.loads(await asyncio.wait_for(ws.recv(), timeout=90))
            received.append(message)
            if message["type"] == "step.presented":
                await send("step.response", {
                    "step_index": message["payload"]["step_index"],
                    "action_id": "confirm",
                    "input_values": {"reference": REFERENCE},
                })
            elif message["type"] in ("task.completed", "task.failed", "help.requested"):
                return received


@pytest.fixture(scope="module")
def messages(orchestrator: str) -> list[dict]:
    return asyncio.run(_run_flow(orchestrator))


def test_the_billing_flow_completes_over_the_websocket(messages: list[dict]) -> None:
    completed = [m for m in messages if m["type"] == "task.completed"]
    assert completed, [m["type"] for m in messages]
    assert completed[0]["payload"]["llm_calls"] == 0
    # The person's bill ends on its results page since 2026-10-16, where
    # the amount and the due date are (`billing_plan.person_billing_plan`).
    assert completed[0]["payload"]["steps_taken"] == 2
    assert completed[0]["payload"]["summary"].endswith("/bill")


def test_the_flow_switch_selects_billing(messages: list[dict]) -> None:
    started = [m for m in messages if m["type"] == "task.started"][0]
    assert "amount due" in started["payload"]["goal"]
    assert started["payload"]["estimated_steps"] == 2


# --- trace memory, through the running server --------------------------------


@pytest.fixture(scope="module")
def replaying_orchestrator(billing_replica: str, tmp_path_factory) -> Iterator[str]:
    """The same server, with trace memory on and a database of its own."""
    db = tmp_path_factory.mktemp("traces") / "server.db"
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.orchestrator.app:app", "--port", "8022"],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "SIMBA_FLOW": "billing",
            "SIMBA_USE_HARDCODED_PLAN": "1",
            "SIMBA_TRACE_MEMORY": "1",
            "SIMBA_TRACE_DB": str(db),
            "SIMBA_REPLICA_URL": billing_replica,
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for("http://127.0.0.1:8022")
        yield "ws://127.0.0.1:8022/ws"
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture(scope="module")
def two_runs(replaying_orchestrator: str) -> tuple[list[dict], list[dict]]:
    first = asyncio.run(_run_flow(replaying_orchestrator))
    second = asyncio.run(_run_flow(replaying_orchestrator))
    return first, second


def _completed(messages: list[dict]) -> dict:
    done = [m for m in messages if m["type"] == "task.completed"]
    assert done, [m["type"] for m in messages]
    return done[0]["payload"]


def test_the_first_run_is_not_a_replay(two_runs) -> None:
    first, _ = two_runs
    assert _completed(first)["replayed"] is False


def test_the_second_run_replays_the_first(two_runs) -> None:
    _, second = two_runs
    payload = _completed(second)

    assert payload["replayed"] is True
    assert payload["llm_calls"] == 0


def test_both_runs_reach_the_same_page(two_runs) -> None:
    first, second = two_runs
    # The person's bill ends on its results page since 2026-10-16, where
    # the amount and the due date are (`billing_plan.person_billing_plan`).
    assert _completed(first)["summary"].endswith("/bill")
    assert _completed(second)["summary"].endswith("/bill")


def test_replay_is_one_step_per_operation(two_runs) -> None:
    """A plan step can carry several operations; a trace step carries one.

    The billing plan's lookup step fills the reference and clicks Check Bill
    as one unit, so replaying it takes two steps where planning took one.
    """
    first, second = two_runs
    # The person's bill ends on its results page since 2026-10-16, where
    # the amount and the due date are (`billing_plan.person_billing_plan`).
    assert _completed(first)["steps_taken"] == 2
    assert _completed(second)["steps_taken"] == 3


# --- the goal comes from the frontend ----------------------------------------


async def _start_with_goal(ws_url: str, goal: str) -> dict:
    """Send task.start with this goal, return the task.started payload."""
    async with websockets.connect(ws_url, max_size=None) as ws:
        await ws.send(json.dumps({
            "v": 1, "type": "task.start", "task_id": "t_test", "seq": 1, "ts": 0,
            "payload": {"goal": goal, "input_mode": "text"},
        }))
        while True:
            message = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
            if message["type"] == "task.started":
                return message["payload"]


def test_the_typed_goal_becomes_the_task(orchestrator: str) -> None:
    goal = "Check what I owe on reference 04141234567890"

    started = asyncio.run(_start_with_goal(orchestrator, goal))

    assert started["goal"] == goal


async def _first_reply(ws_url: str, goal: str) -> dict:
    """Send task.start with this goal, return whichever reply comes first."""
    async with websockets.connect(ws_url, max_size=None) as ws:
        await ws.send(json.dumps({
            "v": 1, "type": "task.start", "task_id": "t_test", "seq": 1, "ts": 0,
            "payload": {"goal": goal, "input_mode": "text"},
        }))
        while True:
            message = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
            if message["type"] in ("task.started", "goal.answered"):
                return message


def test_an_empty_goal_starts_nothing(orchestrator: str) -> None:
    """Reversed on 2026-09-21. This used to assert the opposite — an empty goal
    ran the configured flow, "so a frontend that sends nothing still gets a
    working task". With the backend pinned to billing, that was a bill looked
    up that nobody asked for. An empty box is nobody asking; it is greeted."""
    reply = asyncio.run(_first_reply(orchestrator, "   "))

    assert reply["type"] == "goal.answered"
    assert reply["payload"]["kind"] == "greeting"


# --- the person's own reference number --------------------------------------
#
# Until 2026-09-30 the plan's number was the only number. "Check the bill for
# 0414 9999 999999" looked up 04141234567890, because that is what
# `BILLING_PLAN` holds, and the closing screen then showed a real amount due on
# somebody else's bill. Checking it needs `About.shows`: the number is typed on
# the first page and the run ends two pages later, with no field left to read
# it back from.

OTHER_REFERENCE = "04149999999999"


def look_up(reference: str, start_url: str, task=None) -> FakeConnection:
    brief = BillBrief(f"bill for {reference}", Understood(reference=reference))
    return drive(HardcodedPlanner(person_billing_plan(reference)), task or brief.task(),
                 start_url)


def test_the_bill_looked_up_is_the_one_the_person_named(billing_replica: str) -> None:
    connection = look_up(OTHER_REFERENCE, billing_replica)

    assert "help.requested" not in connection.types(), connection.sent[-1]
    assert connection.payload_of("task.completed")["steps_taken"] == 2
    # Their number, in the step they agreed to and in the field that was typed.
    lookup = connection.of("step.presented")[1]
    assert lookup["fields"][0]["value"] == OTHER_REFERENCE


def test_looking_up_another_bill_fails_rather_than_completes(billing_replica: str) -> None:
    """The check that makes the goal mean something, on the page it has to work
    on. The run looks up one number and is judged against another: the detail
    page arrives, the URL and the title are exactly what success looks like,
    and it still fails."""
    asked_about = BillBrief("g", Understood(reference=REFERENCE)).task()

    connection = look_up(OTHER_REFERENCE, billing_replica, task=asked_about)

    reason = connection.payload_of("help.requested")["reason"]
    assert "REF NO" in reason and REFERENCE in reason and OTHER_REFERENCE in reason
    assert "task.completed" not in connection.types()


def test_the_results_page_echoes_the_number_that_was_searched(
    billing_replica: str,
) -> None:
    """What makes the check possible, and it was not true until today: the
    results page printed the worked example's number whatever had been looked
    up, so every bill said it was the one asked about."""
    connection = look_up(OTHER_REFERENCE, billing_replica)

    # The run ends on the results page (2026-10-16), so what was read there is
    # in the ending rather than on a step after it.
    said = connection.payload_of("task.completed")["findings"]
    assert said, "nothing was read off the results page"
    assert "task.completed" in connection.types()


def test_the_amount_still_reaches_the_end_for_any_number(billing_replica: str) -> None:
    """`About.finds` is unchanged by whose bill it is."""
    completed = look_up(OTHER_REFERENCE, billing_replica).payload_of("task.completed")

    assert [finding["label"] for finding in completed["findings"]] == ["Your bill", "Due"]
    assert all(finding["value"] for finding in completed["findings"])


def test_the_task_names_the_number_and_what_must_say_it() -> None:
    task = BillBrief("check my bill", Understood(reference=OTHER_REFERENCE)).task()

    # The goal stays the person's own words, because that is what the screen
    # shows them; the number reached the checks, which is where it is needed.
    assert task.goal == "check my bill"
    assert OTHER_REFERENCE in bill_task(OTHER_REFERENCE).goal
    # Nothing held: there is no field on the final page to hold it.
    assert task.about.holds == ()
    assert [(s.reads, s.says) for s in task.about.shows] == [("REF NO", OTHER_REFERENCE)]


def test_the_worked_example_is_still_the_worked_example() -> None:
    """`BILLING_PLAN` and `BILLING_TASK` are what every recorded billing number
    was measured on, and they are no longer what a typed goal runs."""
    assert BILLING_PLAN == billing_plan(REFERENCE)
    assert BILLING_TASK == bill_task(REFERENCE)
    assert billing_plan(OTHER_REFERENCE) != BILLING_PLAN
