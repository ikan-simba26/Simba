"""The person's own tiles (2026-10-18): a task kept with its details, run again
with one press.

The store is the vault's kind of file — encrypted with this Windows account's
own key — and nothing about a tile is readable in it. A closing screen offers
once to keep a bill or a journey; kept, the tile runs with what it kept and
asks only what can change, the day; and the details never travel to the
overlay, a model, or the log. Real replicas and a real backend where it
matters; the store alone where it does not.
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

from backend.orchestrator import voice
from backend.orchestrator.details import BillBrief, TripBrief, Understood, known_from_tile
from backend.orchestrator.loop import run_brief
from backend.orchestrator.test_billing import _wait_for, billing_replica  # noqa: F401
from backend.orchestrator.test_checklist import Answers, run
from backend.orchestrator.test_trip_answers import railways  # noqa: F401
from backend.orchestrator.tiles import MAX_TILES, Tile, TileStore

REFERENCE = "04141234567890"
REPO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(not TileStore(Path("unused")).available,
                                reason="tiles need the operating system's encryption")


@pytest.fixture
def store(tmp_path: Path) -> TileStore:
    return TileStore(tmp_path / "tiles.json")


# --- the store ----------------------------------------------------------------------


def test_a_tile_is_kept_encrypted_name_and_all(store: TileStore) -> None:
    tile = store.add("My electricity", "billing", {"reference": REFERENCE})

    assert tile is not None and store.all() == [tile]
    written = store.path.read_text(encoding="utf-8")
    assert REFERENCE not in written and "electricity" not in written
    assert "billing" not in written
    # And nothing that prints one shows its details.
    assert REFERENCE not in repr(tile) and REFERENCE not in str([tile])


def test_tiles_can_be_renamed_moved_and_removed(store: TileStore) -> None:
    bill = store.add("My bill", "billing", {"reference": REFERENCE})
    home = store.add("Home", "railways", {"origin": "Lahore Cantt", "destination": "Karachi Cantt"})
    work = store.add("Work", "railways", {"origin": "Karachi Cantt", "destination": "Hyderabad Jn"})
    assert bill and home and work

    assert store.rename(home.id, "  Trains   home  ")
    assert store.move(work.id, 0)
    assert [t.label for t in store.all()] == ["Work", "My bill", "Trains home"]
    assert store.remove(bill.id)
    assert [t.label for t in store.all()] == ["Work", "Trains home"]
    # Nothing changes for a tile that is not there, or an empty name.
    assert not store.rename("nope", "x") and not store.rename(work.id, "   ")
    assert not store.remove("nope") and not store.move("nope", 1)

    store.clear()
    assert store.all() == [] and not store.path.exists()


def test_no_more_than_three_and_never_the_same_one_twice(store: TileStore) -> None:
    details = {"reference": REFERENCE}
    assert store.add("My bill", "billing", details)
    assert store.add("Again", "billing", details) is None
    assert not store.can_keep("billing", details)
    for n in range(MAX_TILES - 1):
        assert store.add(f"Trip {n}", "railways", {"origin": f"A{n}", "destination": "B"})
    assert store.add("One more", "railways", {"origin": "C", "destination": "D"}) is None
    assert len(store.all()) == MAX_TILES


def test_only_what_a_flow_keeps_is_kept(store: TileStore) -> None:
    assert store.add("Course", "registration", {"course": "CS-401"}) is None
    assert store.add("Half a trip", "railways", {"origin": "Lahore Cantt"}) is None
    tile = store.add("Bill", "billing", {"reference": REFERENCE, "password": "x"})
    assert tile is not None and tile.details == {"reference": REFERENCE}


def test_a_kept_tile_is_known_without_reading_any_words() -> None:
    known = known_from_tile({"origin": "Lahore Cantt", "destination": "Karachi Cantt"})
    assert (known.origin, known.destination, known.day) == ("Lahore Cantt", "Karachi Cantt", None)
    assert known_from_tile({"reference": REFERENCE}).reference == REFERENCE


# --- offered once on the closing screen ----------------------------------------------


class KeepsIt(Answers):
    """Answers the questions; on the closing screen presses "keep" with a name,
    then goes back to start."""

    def __init__(self, answers, name: str | None = "Electricity") -> None:
        super().__init__(answers)
        self.name = name
        self.kept = False

    async def receive(self, message_type, step_index=None, on_other=None):
        last = self.sent[-1] if self.sent else ("", {})
        if last[0] == "task.completed":
            if last[1].get("keep") and not self.kept and self.name:
                self.kept = True
                return {"type": "step.response", "payload": {
                    "step_index": 0, "action_id": voice.KEEP_ID,
                    "input_values": {"label": self.name}}}
            return {"type": "step.response", "payload": {
                "step_index": 0, "action_id": "leave", "input_values": {}}}
        return await super().receive(message_type, step_index, on_other)


def drive(start_url: str, brief, connection: Answers, tiles: TileStore) -> Answers:
    async def inner() -> Answers:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await run_brief(page, connection, brief, start_url, auto=True, tiles=tiles)
            finally:
                await browser.close()
        return connection

    return run(inner())


def test_a_bill_is_offered_once_and_kept_under_the_name_given(
    billing_replica: str, store: TileStore  # noqa: F811
) -> None:
    brief = BillBrief("check my bill", Understood(reference=REFERENCE))
    done = drive(billing_replica, brief, KeepsIt([("confirm", {})]), store)

    end = done.of("task.completed")
    assert len(end) == 1
    assert end[0]["keep"] == {"label": voice.KEEP_BILL}
    # Beside the offer to pay, which is still there.
    assert end[0]["offer"]["id"] == voice.PAY_ID
    [tile] = store.all()
    assert (tile.label, tile.flow, tile.details) == ("Electricity", "billing",
                                                     {"reference": REFERENCE})
    # The details never went to the overlay.
    assert REFERENCE not in json.dumps(end[0]["keep"])


def test_a_bill_already_kept_is_not_offered_again(
    billing_replica: str, store: TileStore  # noqa: F811
) -> None:
    store.add("My bill", "billing", {"reference": REFERENCE})
    brief = BillBrief("check my bill", Understood(reference=REFERENCE))
    done = drive(billing_replica, brief, KeepsIt([("confirm", {})]), store)

    assert done.of("task.completed")[0].get("keep") is None
    assert len(store.all()) == 1


def test_a_run_from_a_tile_is_not_offered_as_a_tile(
    billing_replica: str, store: TileStore  # noqa: F811
) -> None:
    brief = BillBrief("My bill", known_from_tile({"reference": REFERENCE}))
    brief.from_tile = "abc"
    done = drive(billing_replica, brief, KeepsIt([("confirm", {})]), store)

    assert done.of("task.completed")[0].get("keep") is None
    assert store.all() == []


def test_a_journey_is_offered_as_trains_to_its_place(railways: str, store: TileStore) -> None:  # noqa: F811
    from datetime import date, timedelta

    brief = TripBrief("trains to Karachi tomorrow", Understood(
        origin="Lahore Cantt", destination="Karachi Cantt", day=date.today() + timedelta(days=1)))
    done = drive(railways, brief, KeepsIt([("choice:0", {})], name=None), store)

    assert done.of("task.completed")[0]["keep"] == {"label": "Trains to Karachi"}
    assert store.all() == []  # offered, not pressed: nothing kept


# --- through the app, over the websocket ------------------------------------------------

PORT = 8036
WS_URL = f"ws://127.0.0.1:{PORT}/ws"


@pytest.fixture(scope="module")
def app(billing_replica: str, railways: str, tmp_path_factory) -> Iterator[dict]:  # noqa: F811
    folder = tmp_path_factory.mktemp("tiles-app")
    tiles = TileStore(folder / "tiles.json")
    bill = tiles.add("My bill", "billing", {"reference": REFERENCE})
    trip = tiles.add("Trains to Karachi", "railways",
                     {"origin": "Lahore Cantt", "destination": "Karachi Cantt"})
    log = folder / "backend.log"
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.orchestrator.app:app", "--port", str(PORT)],
        cwd=REPO_ROOT,
        env={**os.environ, "SIMBA_ROUTER": "keywords", "SIMBA_USE_HARDCODED_PLAN": "1",
             "SIMBA_BILLING_URL": billing_replica, "SIMBA_RAILWAYS_URL": railways,
             "SIMBA_RECORD_STEPS": "0", "SIMBA_TILES": str(tiles.path),
             "SIMBA_LOG_FILE": str(log)},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        _wait_for(f"http://127.0.0.1:{PORT}")
        yield {"tiles": tiles, "bill": bill, "trip": trip, "log": log}
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def talk(sends: list[tuple[str, dict]], until=("task.completed", "task.failed",
                                               "help.requested")) -> list[dict]:
    """Send each message in turn; answer every question with its first answer,
    the day with "Tomorrow"; stop at the first ending, or at the second
    `history.offered` when nothing else is coming."""

    async def go() -> list[dict]:
        received: list[dict] = []
        async with websockets.connect(WS_URL, max_size=None) as ws:
            seq = 0

            async def send(kind: str, payload: dict) -> None:
                nonlocal seq
                seq += 1
                await ws.send(json.dumps({"v": 1, "type": kind, "task_id": "t", "seq": seq,
                                          "ts": 0, "payload": payload}))

            received.append(json.loads(await asyncio.wait_for(ws.recv(), 30)))
            if received[0]["type"] in until:
                return received
            for kind, payload in sends:
                await send(kind, payload)
            while True:
                message = json.loads(await asyncio.wait_for(ws.recv(), 120))
                received.append(message)
                if message["type"] == "step.presented" and message["payload"]["actions"]:
                    actions = message["payload"]["actions"]
                    labels = {a["label"]: a["id"] for a in actions}
                    answer = labels.get("Tomorrow") or actions[0]["id"]
                    await send("step.response", {"step_index": message["payload"]["step_index"],
                                                 "action_id": answer, "input_values": {}})
                if message["type"] in until:
                    return received

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, go()).result()


def test_the_home_screen_is_offered_the_tiles_by_name_only(app: dict) -> None:
    [offered] = talk([], until=("history.offered",))

    tiles = offered["payload"]["tiles"]
    assert [(t["label"], t["flow"]) for t in tiles] == [("My bill", "billing"),
                                                         ("Trains to Karachi", "railways")]
    assert REFERENCE not in json.dumps(offered) and "Lahore Cantt" not in json.dumps(offered)


def test_a_bill_tile_runs_without_asking_for_the_number(app: dict) -> None:
    received = talk([("task.start", {"goal": "", "input_mode": "text",
                                     "tile": app["bill"].id})])

    asked = [m["payload"]["instruction"] for m in received if m["type"] == "step.presented"
             and m["payload"]["requires_confirmation"]]
    assert voice.ASK_REFERENCE not in asked
    assert received[-1]["type"] == "task.completed", [m["type"] for m in received]
    assert received[-1]["payload"].get("keep") is None
    started = next(m for m in received if m["type"] == "task.started")
    assert started["payload"]["goal"] == "My bill"


def test_a_journey_tile_asks_only_the_day(app: dict) -> None:
    received = talk([("task.start", {"goal": "", "input_mode": "text",
                                     "tile": app["trip"].id})])

    asked = [m["payload"]["instruction"] for m in received if m["type"] == "step.presented"
             and m["payload"]["requires_confirmation"]]
    assert asked[0] == voice.ASK_DAY, asked
    assert voice.ASK_FROM not in asked and voice.ASK_TO not in asked
    assert received[-1]["type"] == "task.completed", [m["type"] for m in received]


def changes(sends: list[dict]) -> list[list[tuple[str, str]]]:
    """Each `tile.change` in turn, and the tiles each was answered with."""

    async def go() -> list[list[tuple[str, str]]]:
        answers = []
        async with websockets.connect(WS_URL, max_size=None) as ws:
            await asyncio.wait_for(ws.recv(), 30)  # the first offer, on connecting
            for seq, payload in enumerate(sends, start=1):
                await ws.send(json.dumps({"v": 1, "type": "tile.change", "task_id": "t",
                                          "seq": seq, "ts": 0, "payload": payload}))
                message = json.loads(await asyncio.wait_for(ws.recv(), 30))
                assert message["type"] == "history.offered"
                answers.append([(t["label"], t["flow"]) for t in message["payload"]["tiles"]])
        return answers

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, go()).result()


def test_a_tile_changed_on_the_home_screen_is_answered_with_the_tiles_as_they_stand(
    app: dict,
) -> None:
    trip, bill = app["trip"], app["bill"]
    answers = changes([{"action": "rename", "id": trip.id, "label": "Karachi"},
                       {"action": "move", "id": trip.id, "to": 0},
                       {"action": "remove", "id": bill.id},
                       {"action": "rename", "id": "not-a-tile", "label": "x"}])

    assert answers == [
        [("My bill", "billing"), ("Karachi", "railways")],
        [("Karachi", "railways"), ("My bill", "billing")],
        [("Karachi", "railways")],
        [("Karachi", "railways")],
    ]
    # Put back for the tests after this one.
    app["tiles"].clear()
    app["bill"] = app["tiles"].add("My bill", "billing", {"reference": REFERENCE})
    app["trip"] = app["tiles"].add("Trains to Karachi", "railways",
                                   {"origin": "Lahore Cantt", "destination": "Karachi Cantt"})


def test_clearing_them_all_leaves_nothing_behind(app: dict) -> None:
    """The reset (2026-10-18): `clear` empties the home screen's tiles and
    deletes the file they were kept in."""
    answers = changes([{"action": "clear"}])

    assert answers == [[]]
    assert not app["tiles"].path.exists()
    app["bill"] = app["tiles"].add("My bill", "billing", {"reference": REFERENCE})
    app["trip"] = app["tiles"].add("Trains to Karachi", "railways",
                                   {"origin": "Lahore Cantt", "destination": "Karachi Cantt"})


def test_the_log_never_holds_what_a_tile_kept(app: dict) -> None:
    talk([("task.start", {"goal": "", "input_mode": "text", "tile": app["bill"].id})])

    written = app["log"].read_text(encoding="utf-8")
    assert "routed" in written
    assert REFERENCE not in written and "Lahore Cantt" not in written
