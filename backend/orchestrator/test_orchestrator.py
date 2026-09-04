"""End-to-end: the skeleton drives the replica from login to confirmation.

Runs the real orchestrator under uvicorn against the real replica, and talks
to it over a real WebSocket as the frontend would.
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

REPO_ROOT = Path(__file__).resolve().parents[2]
REPLICA_URL = "http://127.0.0.1:5011"
ORCHESTRATOR_URL = "http://127.0.0.1:8011"
WS_URL = "ws://127.0.0.1:8011/ws"

CREDENTIALS = {"username": "raham", "password": "hunter2"}


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
def replica() -> Iterator[str]:
    proc = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=REPO_ROOT / "replicas" / "registration",
        env={**os.environ, "PORT": "5011"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for(REPLICA_URL)
        yield REPLICA_URL
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture(scope="module")
def orchestrator(replica: str) -> Iterator[str]:
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.orchestrator.app:app", "--port", "8011"],
        cwd=REPO_ROOT,
        env={**os.environ, "SIMBA_REPLICA_URL": replica},
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
    """Play the frontend: start the task, confirm every step, collect messages."""
    received: list[dict] = []
    seq = 0

    async with websockets.connect(ws_url, max_size=None) as ws:

        async def send(message_type: str, payload: dict) -> None:
            nonlocal seq
            seq += 1
            await ws.send(
                json.dumps(
                    {
                        "v": 1,
                        "type": message_type,
                        "task_id": "t_test",
                        "seq": seq,
                        "ts": 0,
                        "payload": payload,
                    }
                )
            )

        await send("task.start", {"goal": "Register for CS-401", "input_mode": "text"})

        while True:
            message = json.loads(await asyncio.wait_for(ws.recv(), timeout=90))
            received.append(message)

            if message["type"] == "step.presented":
                await send(
                    "step.response",
                    {
                        "step_index": message["payload"]["step_index"],
                        "action_id": "confirm",
                        "input_values": CREDENTIALS,
                    },
                )
            elif message["type"] in ("task.completed", "task.failed", "help.requested"):
                return received


@pytest.fixture(scope="module")
def messages(orchestrator: str) -> list[dict]:
    return asyncio.run(_run_flow(orchestrator))


def of_type(messages: list[dict], message_type: str) -> list[dict]:
    return [m for m in messages if m["type"] == message_type]


def test_reaches_confirmation(messages: list[dict]) -> None:
    assert not of_type(messages, "help.requested"), "the skeleton got stuck"
    assert not of_type(messages, "task.failed")

    completed = of_type(messages, "task.completed")
    assert len(completed) == 1
    assert "/register" in completed[0]["payload"]["summary"]
    assert completed[0]["payload"]["steps_taken"] == 3


def test_every_step_was_presented_and_confirmed(messages: list[dict]) -> None:
    presented = of_type(messages, "step.presented")
    assert [m["payload"]["step_index"] for m in presented] == [1, 2, 3]
    assert all(m["payload"]["step_total"] == 3 for m in presented)
    assert all(m["payload"]["requires_confirmation"] for m in presented)


def test_login_step_asks_for_a_password_field(messages: list[dict]) -> None:
    login = of_type(messages, "step.presented")[0]
    field_types = {f["id"]: f["type"] for f in login["payload"]["fields"]}
    assert field_types == {"username": "text", "password": "password"}


def test_no_llm_calls(messages: list[dict]) -> None:
    """The skeleton is hardcoded: no model in the loop yet."""
    assert of_type(messages, "task.completed")[0]["payload"]["llm_calls"] == 0


def test_states_follow_the_contract(messages: list[dict]) -> None:
    states = [m["payload"]["state"] for m in of_type(messages, "state.changed")]
    assert set(states) <= {"thinking", "acting", "waiting", "stuck"}
    assert "waiting" in states and "acting" in states


def test_envelopes_are_well_formed(messages: list[dict]) -> None:
    assert [m["seq"] for m in messages] == list(range(1, len(messages) + 1))
    assert all(m["v"] == 1 for m in messages)
    assert all(m["task_id"] == "t_skeleton" for m in messages)
