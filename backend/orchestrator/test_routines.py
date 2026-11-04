"""Routines a helper showed SIMBA (2026-11-04): kept, named, shared.

The store is the tiles' kind of file — encrypted with this Windows account's
own key — and a routine shares the home screen's row of three with them. A
routine saved to a file for someone else asks for every value the helper
typed, and a file read in is checked as data before anything is kept. Over
the real websocket where it matters, the store alone where it does not.
"""

import asyncio
import json
import os
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
import websockets

from backend.orchestrator.routines import (
    Answer,
    NotARoutine,
    Routine,
    RoutineStore,
    Step,
    export,
    file_name,
    parse,
)
from backend.orchestrator.test_billing import REPO_ROOT, _wait_for
from backend.orchestrator.test_checklist import run
from backend.orchestrator.tiles import TileStore

REFERENCE = "04141234567890"
PORT = 8043
WS_URL = f"ws://127.0.0.1:{PORT}/ws"

pytestmark = pytest.mark.skipif(not RoutineStore(Path("unused")).available,
                                reason="routines need the operating system's encryption")


def a_bill(ask: bool = True) -> Routine:
    return Routine(
        id="", label="My bill", start="http://127.0.0.1:5100/",
        steps=(Step("click", "button", "Accept all cookies"),
               Step("fill", "textbox", "Reference No.", ask=ask,
                    value=None if ask else REFERENCE),
               Step("click", "button", "Check Bill", expect_url="/bill")),
        answer=Answer("Amount due", "P/WITHIN"))


@pytest.fixture
def store(tmp_path: Path) -> RoutineStore:
    return RoutineStore(tmp_path / "routines.json")


# --- the store -------------------------------------------------------------------------


def test_a_routine_is_kept_encrypted_and_nothing_prints_what_it_types(
        store: RoutineStore) -> None:
    kept = store.add(a_bill(ask=False))
    assert kept is not None and kept.id and store.all() == [kept]
    written = store.path.read_text(encoding="utf-8")
    for secret in (REFERENCE, "Reference No.", "My bill", "P/WITHIN", "127.0.0.1"):
        assert secret not in written
    assert REFERENCE not in repr(kept) and REFERENCE not in str([kept])


def test_routines_can_be_renamed_and_removed(store: RoutineStore) -> None:
    one = store.add(a_bill())
    two = store.add(replace(a_bill(), label="Second"))
    assert store.rename(one.id, "  Electricity   bill ") and not store.rename(one.id, "  ")
    assert [r.label for r in store.all()] == ["Electricity bill", "Second"]
    assert store.remove(two.id) and not store.remove("nope")
    store.clear()
    assert store.all() == [] and not store.path.exists()


def test_routines_and_tiles_share_one_row_of_three(store: RoutineStore, tmp_path: Path) -> None:
    tiles = TileStore(tmp_path / "tiles.json")
    tiles.add("Home", "railways", {"origin": "Lahore Cantt", "destination": "Karachi Cantt"})
    tiles.add("Bill", "billing", {"reference": REFERENCE})
    assert store.add(a_bill(), tiles=len(tiles.all())) is not None
    assert not store.room(len(tiles.all()))
    assert store.add(a_bill(), tiles=len(tiles.all())) is None


def test_a_damaged_row_is_that_routine_gone_not_all_of_them(store: RoutineStore) -> None:
    from backend.orchestrator.routines import as_row
    from backend.orchestrator.vault import encrypt

    good = as_row(replace(a_bill(), id="abc"))
    bad = {**good, "id": "def", "steps": [{"kind": "run-this-script"}]}
    blob = encrypt(json.dumps([bad, good]).encode()).hex()
    store.path.write_text(json.dumps({"routines": blob}), encoding="utf-8")
    assert [r.id for r in store.all()] == ["abc"]


# --- sharing ---------------------------------------------------------------------------


def test_a_shared_routine_asks_for_every_value_the_helper_typed() -> None:
    text = export(replace(a_bill(ask=False), id="kept-here"))
    assert REFERENCE not in text and "kept-here" not in text
    shared = parse(text)
    assert shared.steps[1].ask and shared.steps[1].value is None
    assert [s.label for s in shared.steps] == ["Accept all cookies", "Reference No.",
                                               "Check Bill"]
    assert shared.answer == Answer("Amount due", "P/WITHIN")
    assert file_name("My bill") == "my-bill.simba-routine.json"


@pytest.mark.parametrize("change, why", [
    (lambda row: {**row, "format": "something-else"}, "not a routine"),
    (lambda row: {**row, "version": 99}, "different version"),
    (lambda row: {**row, "start": "file:///C:/Windows/"}, "web address"),
    (lambda row: {**row, "start": "javascript:alert(1)"}, "web address"),
    (lambda row: {**row, "steps": []}, "no moves"),
    (lambda row: {**row, "steps": row["steps"] * 11}, "too many"),
    (lambda row: {**row, "steps": [{**row["steps"][0], "kind": "evaluate"}]}, "unknown"),
    (lambda row: {**row, "steps": [{**row["steps"][1], "ask": False, "value": "4111"}]},
     "typed value"),
    (lambda row: {**row, "steps": [{**row["steps"][0], "label": "x" * 500}]}, "short"),
    (lambda row: {**row, "label": ""}, "no name"),
])
def test_a_file_that_is_not_a_routine_is_refused_saying_why(change, why) -> None:
    row = json.loads(export(a_bill()))
    with pytest.raises(NotARoutine, match=why):
        parse(json.dumps(change(row)))


def test_a_file_too_large_or_not_json_is_refused() -> None:
    with pytest.raises(NotARoutine):
        parse("{" * 70_000)
    with pytest.raises(NotARoutine):
        parse("not json")


# --- over the real websocket -------------------------------------------------------------


@pytest.fixture(scope="module")
def app(tmp_path_factory) -> Iterator[dict]:
    folder = tmp_path_factory.mktemp("routines-app")
    routines = RoutineStore(folder / "routines.json")
    tiles = TileStore(folder / "tiles.json")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.orchestrator.app:app", "--port", str(PORT)],
        cwd=REPO_ROOT,
        env={**os.environ, "SIMBA_ROUTER": "keywords", "SIMBA_USE_HARDCODED_PLAN": "1",
             "SIMBA_RECORD_STEPS": "0", "SIMBA_TILES": str(tiles.path),
             "SIMBA_ROUTINES": str(routines.path), "SIMBA_LOG_FILE": str(folder / "b.log"),
             "SIMBA_VAULT": str(folder / "vault.json"),
             "SIMBA_TRACE_DB": str(folder / "traces.db")},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        _wait_for(f"http://127.0.0.1:{PORT}")
        yield {"routines": routines, "tiles": tiles}
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def talk(sends: list[tuple[str, dict]], answers: int) -> list[dict]:
    """Send each message in turn and read `answers` messages after the first
    `history.offered`."""

    async def go() -> list[dict]:
        async with websockets.connect(WS_URL, max_size=None) as ws:
            received = [json.loads(await asyncio.wait_for(ws.recv(), 10))]
            for seq, (kind, payload) in enumerate(sends, 1):
                await ws.send(json.dumps({"v": 1, "type": kind, "task_id": "t", "seq": seq,
                                          "ts": 0, "payload": payload}))
            for _ in range(answers):
                received.append(json.loads(await asyncio.wait_for(ws.recv(), 10)))
            return received

    return run(go())


def test_the_home_screen_is_offered_routines_by_name_and_host_only(app: dict) -> None:
    app["routines"].clear()
    kept = app["routines"].add(a_bill(ask=False))
    [offered] = talk([], 0)
    assert offered["payload"]["routines"] == [
        {"id": kept.id, "label": "My bill", "site": "127.0.0.1:5100"}]
    assert REFERENCE not in json.dumps(offered)


def test_a_routine_is_saved_to_a_file_renamed_and_removed_from_the_home_screen(
        app: dict) -> None:
    app["routines"].clear()
    kept = app["routines"].add(a_bill(ask=False))
    got = talk([("routine.export", {"id": kept.id}),
                ("tile.change", {"action": "rename", "id": kept.id, "label": "Electricity"}),
                ("tile.change", {"action": "remove", "id": kept.id})], 3)
    file = got[1]
    assert file["type"] == "routine.file"
    assert file["payload"]["name"] == "my-bill.simba-routine.json"
    assert REFERENCE not in file["payload"]["file"]
    assert got[2]["payload"]["routines"][0]["label"] == "Electricity"
    assert got[3]["payload"]["routines"] == []


def test_a_file_read_in_becomes_a_routine_and_a_bad_one_is_said(app: dict) -> None:
    app["routines"].clear()
    good = export(a_bill())
    got = talk([("routine.import", {"file": good}),
                ("routine.import", {"file": "not a routine"})], 3)
    assert [r["label"] for r in got[1]["payload"]["routines"]] == ["My bill"]
    assert got[2]["type"] == "error" and got[2]["payload"]["code"] == "ROUTINE_NOT_READ"
    assert len(got[3]["payload"]["routines"]) == 1


def test_forgetting_the_person_takes_the_routines_too(app: dict) -> None:
    app["routines"].add(a_bill())
    got = talk([("tile.change", {"action": "clear"})], 1)
    assert got[1]["payload"]["routines"] == [] and app["routines"].all() == []
