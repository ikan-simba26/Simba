"""The level adapts in a real run: through the loop, and over the websocket.

`backend/estimator/test_rules.py` checks the rules on scripted samples alone.
This checks that the loop hands them the right samples at the right moments,
sends what they decide as `load.updated` in the right place among the other
messages, and writes every decision down — on the billing replica, with the
hardcoded plan, in a real browser. Then the same over the running app, where
a lock set before the task starts has to hold.
"""

import asyncio
import concurrent.futures
import json
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
import websockets
from playwright.async_api import async_playwright

from backend.estimator.pairing import Recorder, read_rows
from backend.estimator.rules import THRESHOLDS, LevelRules
from backend.orchestrator.billing_plan import BILLING_PLAN, BILLING_TASK, REFERENCE
from backend.orchestrator.loop import Connection, run_task
from backend.orchestrator.plan import HardcodedPlanner
from backend.orchestrator.test_billing import _wait_for

REPO_ROOT = Path(__file__).resolve().parents[2]
PORT = 8026
WS_URL = f"ws://127.0.0.1:{PORT}/ws"


def sample(step: int, ms: int, *, answered: bool = False, help_presses: int = 0) -> dict:
    return {"step_index": step, "hesitation_ms": ms, "cursor_path_ratio": 1.0,
            "backtracks": 0, "rereads": 0, "help_presses": help_presses,
            "answered": answered}


#: Per step, what the overlay sends while it waits and with the answer.
HESITANT_THEN_CALM = {
    1: [sample(1, 3000), sample(1, 9000), sample(1, THRESHOLDS.hesitation_ms),
        sample(1, 18000), sample(1, 19000, answered=True)],
    2: [sample(2, 2000, answered=True)],
    3: [sample(3, 2000, answered=True)],
}


class ScriptedFrontend(Connection):
    """Answers every step, sending the scripted samples for it first."""

    def __init__(self, script: dict[int, list[dict]],
                 before: list[dict] | None = None) -> None:
        self.script = script
        self.before = before or []
        self.sent: list[tuple[str, dict]] = []

    async def send(self, message_type: str, payload) -> None:
        self.sent.append((message_type, payload.model_dump()))

    async def receive(self, message_type: str, step_index=None, on_other=None) -> dict:
        if on_other is not None:
            for message in self.before:
                await on_other(message)
            self.before = []
            for payload in self.script.get(step_index, []):
                await on_other({"type": "telemetry", "payload": payload})
        # "No" to the offer to pay, which has no go-ahead (2026-10-16).
        shown = [p for kind, p in self.sent if kind == "step.presented"]
        ids = [a["id"] for a in shown[-1]["actions"]] if shown else ["confirm"]
        return {"type": "step.response",
                "payload": {"step_index": step_index,
                            "action_id": "confirm" if "confirm" in ids else "decline",
                            "input_values": {"reference": REFERENCE}}}

    def types(self) -> list[str]:
        return [kind for kind, _ in self.sent]

    def levels(self) -> list[int]:
        return [payload["level"] for kind, payload in self.sent if kind == "load.updated"]


def drive(frontend: ScriptedFrontend, start_url: str, recorder: Recorder | None,
          rules: LevelRules | None) -> None:
    async def go() -> None:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await run_task(page, frontend, HardcodedPlanner(BILLING_PLAN),
                               BILLING_TASK, start_url, recorder, rules)
            finally:
                await browser.close()

    # Its own thread: see `backend/conftest.py` on sync and async Playwright.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(lambda: asyncio.run(go())).result()


# --- through the loop --------------------------------------------------------------


def test_the_level_folds_mid_step_and_returns_before_the_ending(
    billing: str, tmp_path
) -> None:
    recorder = Recorder(path=tmp_path / "steps.jsonl", task_id="t_adapt")
    frontend = ScriptedFrontend(HESITANT_THEN_CALM)
    drive(frontend, billing, recorder, LevelRules())

    types = frontend.types()
    assert "task.completed" in types, types
    # Start at 2, fold to 3 on step 1, back to 2 after two calm steps.
    assert frontend.levels() == [2, 3, 2]

    loads = [i for i, kind in enumerate(types) if kind == "load.updated"]
    steps = [i for i, kind in enumerate(types) if kind == "step.presented"]
    # The start arrives before the first step, so it is shown at its level.
    assert loads[0] < steps[0]
    # The fold arrives while step 1 is on screen, not after it.
    assert steps[0] < loads[1] < steps[1]
    # Billing has three steps, so the return goes out before the ending.
    assert steps[2] < loads[2] < types.index("task.completed")


def test_every_decision_is_written_beside_the_telemetry(billing: str, tmp_path) -> None:
    recorder = Recorder(path=tmp_path / "steps.jsonl", task_id="t_adapt")
    drive(ScriptedFrontend(HESITANT_THEN_CALM), billing, recorder, LevelRules())

    rows = read_rows(recorder.path)
    telemetry = [row for row in rows if row["kind"] == "telemetry"]
    decisions = [row for row in rows if row["kind"] == "decision"]
    samples = sum(len(v) for v in HESITANT_THEN_CALM.values())

    assert len(telemetry) == samples
    # One per sample, one per step as it arrives, one before the ending.
    assert len(decisions) == samples + len(BILLING_PLAN) + 1
    assert all(row["rules"] == "provisional" for row in decisions)
    fold = [row for row in decisions if row["rule"] == "simplify"]
    assert len(fold) == 1
    assert fold[0]["inputs"]["telemetry"]["hesitation_ms"] == THRESHOLDS.hesitation_ms
    # The start was made from the page the first step was showing.
    start = decisions[0]
    assert start["at"] == "start"
    assert start["inputs"]["page"]["controls"] > 0


def test_a_lock_sent_while_a_step_waits_holds_from_then_on(billing: str) -> None:
    frontend = ScriptedFrontend(
        HESITANT_THEN_CALM,
        before=[{"type": "level.override", "payload": {"level": 1, "locked": True}}],
    )
    drive(frontend, billing, None, LevelRules())

    # The start went out before the lock; nothing after it.
    assert frontend.levels() == [2]
    assert "task.completed" in frontend.types()


def test_without_rules_nothing_is_sent(billing: str) -> None:
    """Every other test in the repository drives `run_task` this way."""
    frontend = ScriptedFrontend(HESITANT_THEN_CALM)
    drive(frontend, billing, None, None)

    assert "load.updated" not in frontend.types()
    assert "task.completed" in frontend.types()


# --- over the running app ----------------------------------------------------------


@pytest.fixture(scope="module")
def app_url(billing: str) -> Iterator[str]:
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.orchestrator.app:app",
         "--port", str(PORT)],
        cwd=REPO_ROOT,
        env={**os.environ, "SIMBA_ROUTER": "keywords", "SIMBA_USE_HARDCODED_PLAN": "1",
             "SIMBA_BILLING_URL": billing, "SIMBA_RECORD_STEPS": "0", "SIMBA_FLOW": ""},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for(f"http://127.0.0.1:{PORT}")
        yield WS_URL
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def converse(url: str, before: list[tuple[str, dict]], start: dict | None = None) -> list[dict]:
    """Play the overlay: anything in `before`, then the bill, hesitating on
    step 1 and answering the rest at once."""

    async def run() -> list[dict]:
        received: list[dict] = []
        seq = 0
        async with websockets.connect(url, max_size=None) as ws:

            async def send(kind: str, payload: dict) -> None:
                nonlocal seq
                seq += 1
                await ws.send(json.dumps({"v": 1, "type": kind, "task_id": "t_test",
                                          "seq": seq, "ts": 0, "payload": payload}))

            for kind, payload in before:
                await send(kind, payload)
            # Three screens, the ones these telemetry samples are written for:
            # the question for the number (left out of the goal since
            # 2026-10-16, when the bill became two steps), the cookies and the
            # lookup. Asked before each move (`confirm_each`): since 2026-10-14
            # the lookup otherwise runs as a checklist line, which is no
            # decision and is never weighed, so there would be no calm steps to
            # return on.
            await send("task.start", {"goal": "Check my electricity bill",
                                      "input_mode": "text", "flow": "billing",
                                      "confirm_each": True, **(start or {})})
            while True:
                message = json.loads(await asyncio.wait_for(ws.recv(), timeout=90))
                received.append(message)
                if message["type"] == "step.presented":
                    index = message["payload"]["step_index"]
                    for payload in HESITANT_THEN_CALM.get(index, []):  # the offer to pay: calm
                        await send("telemetry", payload)
                    ids = [a["id"] for a in message["payload"]["actions"]]
                    await send("step.response", {
                        "step_index": index,
                        "action_id": "confirm" if "confirm" in ids else "decline",
                        "input_values": {"reference": REFERENCE}})
                if message["type"] in ("task.completed", "task.failed", "help.requested"):
                    return received

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, run()).result()


def levels_of(received: list[dict]) -> list[int]:
    return [m["payload"]["level"] for m in received if m["type"] == "load.updated"]


def test_the_app_folds_and_returns(app_url: str) -> None:
    received = converse(app_url, [])

    assert received[-1]["type"] == "task.completed", [m["type"] for m in received]
    assert levels_of(received) == [2, 3, 2]
    for message in received:
        if message["type"] == "load.updated":
            assert 0.0 <= message["payload"]["score"] <= 1.0
            assert message["payload"]["reason"]


def test_a_lock_set_on_the_home_screen_holds_from_the_first_step(app_url: str) -> None:
    """Sent before `task.start`, which is where the overlay sends it."""
    received = converse(app_url, [("level.override", {"level": 2, "locked": True})])

    assert received[-1]["type"] == "task.completed"
    assert levels_of(received) == []


def test_the_level_the_person_chose_is_where_the_task_starts_and_returns(
    app_url: str,
) -> None:
    """`task.start.start_level` (2026-10-18), from the overlay's welcome: the
    rules start at the person's own level, fold one from there, and come back
    to it — not to 2."""
    received = converse(app_url, [], {"start_level": 1})

    assert received[-1]["type"] == "task.completed", [m["type"] for m in received]
    assert levels_of(received) == [1, 2, 1]
