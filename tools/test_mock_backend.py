"""The mock routes a typed goal the way the real backend does.

It is the demo-day fallback. Until 2026-09-21 it played the registration
script whatever was typed, so a demo taught the wrong thing about the product
— "hello" appeared to start a task. These are the same five cases
`backend/orchestrator/test_app_routing.py` puts to the real backend, put to
the mock.
"""

import asyncio
import concurrent.futures
import json
import os
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest
import websockets

REPO = Path(__file__).resolve().parents[1]
PORT = 8031
WS_URL = f"ws://127.0.0.1:{PORT}/ws"


@pytest.fixture(scope="module")
def mock() -> Iterator[str]:
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "tools.mock_backend:app", "--port", str(PORT)],
        cwd=REPO, env={**os.environ, "SIMBA_ROUTER": "keywords"},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=1)
            break
        except OSError:
            time.sleep(0.2)
    try:
        yield WS_URL
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def converse(url: str, *starts: dict) -> list[dict]:
    """Each `task.start` in turn on one connection, answering every step."""

    async def run() -> list[dict]:
        received: list[dict] = []
        seq = 0
        async with websockets.connect(url) as ws:

            async def send(kind: str, payload: dict) -> None:
                nonlocal seq
                seq += 1
                await ws.send(json.dumps({"v": 1, "type": kind, "task_id": "t",
                                          "seq": seq, "ts": 0, "payload": payload}))

            async def until(*kinds: str) -> None:
                while True:
                    message = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
                    received.append(message)
                    if message["type"] == "step.presented":
                        await send("step.response", {
                            "step_index": message["payload"]["step_index"],
                            "action_id": "confirm", "input_values": {}})
                    if message["type"] in kinds:
                        return

            await until("history.offered")
            for payload in starts:
                await send("task.start", {"input_mode": "text", **payload})
                await until("goal.answered", "task.completed")
        return received

    # On a thread of its own. A sync Playwright session from another module in
    # the same pytest run holds an event loop on this thread, and `asyncio.run`
    # refuses to start beside it (`backend/conftest.py` has the long story).
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, run()).result()


def types(received: list[dict]) -> list[str]:
    return [m["type"] for m in received]


def answer(received: list[dict]) -> dict:
    return [m for m in received if m["type"] == "goal.answered"][-1]["payload"]


def started(received: list[dict]) -> dict:
    return [m for m in received if m["type"] == "task.started"][0]["payload"]


def completed(received: list[dict]) -> dict:
    return [m for m in received if m["type"] == "task.completed"][0]["payload"]


def test_the_mock_says_it_is_up(mock: str) -> None:
    """The launcher, the demo recorder and this file's fixture all wait for
    `/`. From 2026-10-03 to 2026-10-05 it answered 422, because a helper had
    been put between the route's decorator and `health`."""
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=5) as response:
        said = json.loads(response.read())
    assert said["status"] == "ok" and said["flow"] == "mock"


def test_hello_is_greeted_and_nothing_plays(mock: str) -> None:
    received = converse(mock, {"goal": "hello"})

    assert answer(received)["kind"] == "greeting"
    assert "task.started" not in types(received)


def test_pay_my_bill_plays_billing_and_finds_the_bill(mock: str) -> None:
    received = converse(mock, {"goal": "pay my bill"})

    assert started(received)["goal"] == "pay my bill"
    labels = [f["label"] for f in completed(received)["findings"]]
    assert labels == ["Your bill", "Due"]


def test_trains_to_karachi_plays_railways_and_finds_trains(mock: str) -> None:
    received = converse(mock, {"goal": "trains to Karachi"})

    assert started(received)["goal"] == "trains to Karachi"
    assert completed(received)["findings"][0]["label"] == "Train"


def test_book_a_flight_is_declined(mock: str) -> None:
    received = converse(mock, {"goal": "book a flight"})

    assert answer(received)["kind"] == "unsupported"
    assert "task.started" not in types(received)


def test_something_ambiguous_is_asked_about(mock: str) -> None:
    received = converse(mock, {"goal": "I need to pay for my course"})

    assert answer(received)["kind"] == "clarify"
    assert set(answer(received)["flows"]) == {"billing", "registration"}


def test_the_bill_is_what_the_replica_says_character_for_character(mock: str) -> None:
    """The demo cannot show an answer the page does not.

    It did: "15 October 2026" for a bill the replica says is due
    "15-09-2026". A wrong date on the answer screen is the failure this
    project exists to prevent, and the demo is where most people first see it.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "billing_replica", REPO / "replicas" / "billing" / "app.py")
    replica = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(replica)

    received = converse(mock, {"goal": "pay my bill"})
    found = {f["label"]: f["values"] for f in completed(received)["findings"]}

    assert found["Your bill"] == [replica.BILL["payable_within"]]
    assert found["Due"] == [replica.BILL["due_date"]]


def test_registration_changes_something_and_finds_nothing(mock: str) -> None:
    """It used to carry the billing flow's answer."""
    received = converse(mock, {"goal": "Register for CS-401"})

    assert completed(received)["findings"] == []


def test_a_greeting_then_a_card_on_one_connection(mock: str) -> None:
    received = converse(mock, {"goal": "hi"},
                        {"goal": "Check my electricity bill", "flow": "billing"})

    assert types(received).count("history.offered") == 1
    assert completed(received)["findings"][0]["label"] == "Your bill"
