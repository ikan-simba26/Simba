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

from backend.orchestrator.billing_plan import BILLING_PLAN, BILLING_TASK, REFERENCE
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
    assert completed[0]["payload"]["steps_taken"] == 3
    assert "/bill/detail" in completed[0]["payload"]["summary"]


def test_the_flow_switch_selects_billing(messages: list[dict]) -> None:
    started = [m for m in messages if m["type"] == "task.started"][0]
    assert "amount due" in started["payload"]["goal"]
    assert started["payload"]["estimated_steps"] == 3


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
    assert "/bill/detail" in _completed(first)["summary"]
    assert "/bill/detail" in _completed(second)["summary"]


def test_replay_is_one_step_per_operation(two_runs) -> None:
    """A plan step can carry several operations; a trace step carries one.

    The billing plan's lookup step fills the reference and clicks Check Bill
    as one unit, so replaying it takes two steps where planning took one.
    """
    first, second = two_runs
    assert _completed(first)["steps_taken"] == 3
    assert _completed(second)["steps_taken"] == 4
