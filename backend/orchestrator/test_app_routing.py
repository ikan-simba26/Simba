"""The typed goal decides what happens — over the real websocket.

`test_router.py` checks the classifier. This checks the thing the person
meets: the running app, a `task.start`, and what comes back. The failure it
exists for was end to end — "hello" typed into a backend started as `billing`
opened the bill site — so it is tested end to end.

Keyword routing (`SIMBA_ROUTER=keywords`) and the hardcoded plan, so no model
is called and no quota is spent; the billing flow runs against a local
replica, and the railways flow is checked without touching the live site.
"""

import asyncio
import concurrent.futures
import json
import os
import subprocess
import sys
from collections.abc import Iterator

import pytest
import websockets

from backend.orchestrator.billing_plan import BILLING_PLAN, REFERENCE
from backend.orchestrator.railways_plan import RAILWAYS_PLAN, RAILWAYS_URL
from backend.orchestrator.test_billing import REPO_ROOT, _wait_for, billing_replica  # noqa: F401

PORT = 8024
WS_URL = f"ws://127.0.0.1:{PORT}/ws"

#: What ends a conversation from the test's side.
ENDINGS = ("task.completed", "task.failed", "help.requested")


@pytest.fixture(scope="module")
def app_url(billing_replica: str) -> Iterator[str]:  # noqa: F811
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.orchestrator.app:app",
         "--port", str(PORT)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "SIMBA_ROUTER": "keywords",
            "SIMBA_USE_HARDCODED_PLAN": "1",
            "SIMBA_BILLING_URL": billing_replica,
            "SIMBA_RECORD_STEPS": "0",
            # Deliberately set to something else: it must not choose the task.
            "SIMBA_FLOW": "",
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for(f"http://127.0.0.1:{PORT}")
        yield WS_URL
    finally:
        proc.terminate()
        proc.wait(timeout=10)


class Talk:
    """One websocket conversation, driven the way the overlay drives it."""

    def __init__(self, ws) -> None:
        self.ws = ws
        self.seq = 0
        self.received: list[dict] = []

    async def send(self, message_type: str, payload: dict) -> None:
        self.seq += 1
        await self.ws.send(json.dumps({
            "v": 1, "type": message_type, "task_id": "t_test",
            "seq": self.seq, "ts": 0, "payload": payload,
        }))

    async def until(self, *types: str, timeout: float = 90) -> dict:
        while True:
            message = json.loads(await asyncio.wait_for(self.ws.recv(), timeout=timeout))
            self.received.append(message)
            if message["type"] == "step.presented":
                await self.send("step.response", {
                    "step_index": message["payload"]["step_index"],
                    "action_id": "confirm",
                    "input_values": {"reference": REFERENCE},
                })
            if message["type"] in types:
                return message

    def types(self) -> list[str]:
        return [m["type"] for m in self.received]


def converse(url: str, *starts: dict) -> Talk:
    """Send each `task.start` in turn on ONE connection, until it is answered."""

    async def run() -> Talk:
        async with websockets.connect(url, max_size=None) as ws:
            talk = Talk(ws)
            await talk.until("history.offered")
            for payload in starts:
                await talk.send("task.start", {"input_mode": "text", **payload})
                await talk.until("goal.answered", *ENDINGS)
            return talk

    # On its own thread, for the reason in `backend/conftest.py`: a sync
    # Playwright session from another module holds a loop on this one.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, run()).result()


def answer_of(talk: Talk) -> dict:
    return [m for m in talk.received if m["type"] == "goal.answered"][-1]["payload"]


# --- the five the task named ---------------------------------------------------


def test_hello_is_answered_and_starts_nothing(app_url: str) -> None:
    talk = converse(app_url, {"goal": "hello"})

    answer = answer_of(talk)
    assert answer["kind"] == "greeting"
    assert set(answer["flows"]) == {"registration", "billing", "railways"}
    # The failure this exists for: no task, no step, no site opened.
    assert "task.started" not in talk.types()
    assert "step.presented" not in talk.types()


def test_pay_my_bill_runs_billing_with_the_goal_as_typed(app_url: str) -> None:
    talk = converse(app_url, {"goal": "pay my bill"})

    started = [m for m in talk.received if m["type"] == "task.started"][0]["payload"]
    assert started["goal"] == "pay my bill"
    assert started["estimated_steps"] == len(BILLING_PLAN)
    assert "task.completed" in talk.types(), talk.types()
    assert "goal.answered" not in talk.types()


def test_book_a_flight_is_declined(app_url: str) -> None:
    talk = converse(app_url, {"goal": "book a flight"})

    assert answer_of(talk)["kind"] == "unsupported"
    assert "task.started" not in talk.types()


def test_something_ambiguous_is_asked_about(app_url: str) -> None:
    talk = converse(app_url, {"goal": "I need to pay for my course"})

    answer = answer_of(talk)
    assert answer["kind"] == "clarify"
    assert set(answer["flows"]) == {"billing", "registration"}
    assert answer["goal"] == "I need to pay for my course"
    assert "task.started" not in talk.types()


def test_trains_to_karachi_routes_to_railways() -> None:
    """Checked at the dispatch, not by running it: the live site is not ours
    to hit from a test suite (CLAUDE.md)."""
    import asyncio as aio

    from backend.orchestrator.app import flow_setup
    from backend.orchestrator.router import by_keywords, route

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        decided = pool.submit(aio.run, route("trains to Karachi", None)).result()
    assert (decided.kind, decided.flow) == ("flow", "railways")
    name, _, plan, url = flow_setup(decided.flow)
    assert (name, plan, url) == ("railways", RAILWAYS_PLAN, RAILWAYS_URL)
    assert by_keywords("trains to Karachi").flow == "railways"


# --- the conversation around them ----------------------------------------------


def test_the_socket_stays_open_after_an_answer_and_a_card_runs(app_url: str) -> None:
    """Hello, then the billing card: one connection, and the card is obeyed."""
    talk = converse(
        app_url,
        {"goal": "hello"},
        {"goal": "Check my electricity bill", "flow": "billing"},
    )

    assert talk.types().count("history.offered") == 1
    assert "goal.answered" in talk.types()
    assert "task.completed" in talk.types(), talk.types()


def test_a_clarifying_choice_runs_the_goal_as_typed(app_url: str) -> None:
    """The person answers "which did you mean"; their sentence is still the goal."""
    talk = converse(
        app_url,
        {"goal": "I need to pay for my course"},
        {"goal": "I need to pay for my course", "flow": "billing"},
    )

    started = [m for m in talk.received if m["type"] == "task.started"][0]["payload"]
    assert started["goal"] == "I need to pay for my course"
    assert "task.completed" in talk.types(), talk.types()


def test_a_flow_that_does_not_exist_is_not_obeyed(app_url: str) -> None:
    talk = converse(app_url, {"goal": "hello", "flow": "stubborn"})

    assert answer_of(talk)["kind"] == "greeting"
    assert "task.started" not in talk.types()


def test_an_empty_goal_starts_nothing(app_url: str) -> None:
    """The contract used to fall back to the configured flow here."""
    talk = converse(app_url, {"goal": "   "})

    assert answer_of(talk)["kind"] == "greeting"
    assert "task.started" not in talk.types()
