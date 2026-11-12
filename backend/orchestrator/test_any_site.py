"""Any website (2026-11-13), through the real `/ws` endpoint, in-process: the
list of websites on the socket's first message, "Add a website", and a goal
on a website with no written plan answered `not_yet` — never started on the
wrong flow, and never on a site nobody named."""

import json
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.orchestrator import app as app_module
from backend.orchestrator.catalogue import CatalogueStore


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SIMBA_ROUTER", "keywords")
    monkeypatch.setenv("SIMBA_RECORD_STEPS", "0")
    monkeypatch.setenv("SIMBA_CATALOGUE_LOCAL", str(tmp_path / "catalogue.local.json"))
    monkeypatch.setenv("SIMBA_TILES", str(tmp_path / "tiles.json"))
    monkeypatch.setenv("SIMBA_ROUTINES", str(tmp_path / "routines.json"))
    monkeypatch.setenv("SIMBA_TRACE_DB", str(tmp_path / "traces.db"))

    # No task may open a page here: a test that reaches one has failed.
    def no_page(name):
        raise AssertionError(f"a flow was started: {name}")
    monkeypatch.setattr(app_module, "flow_setup_for_run", no_page, raising=False)
    with TestClient(app_module.app) as test_client:
        yield test_client


@contextmanager
def socket(client):
    """The overlay's connection. Leaving it is the overlay closing the window:
    the endpoint, waiting for the next goal, sees the disconnect, as it does
    under uvicorn, and only that is let through. Any other server error fails
    the test."""
    try:
        with client.websocket_connect("/ws") as ws:
            yield ws
    except WebSocketDisconnect:
        pass


def send(ws, kind: str, payload: dict, seq: int = 1) -> None:
    ws.send_json({"v": 1, "type": kind, "task_id": "t", "seq": seq, "ts": 0,
                  "payload": payload})


def test_the_first_message_lists_the_websites_by_genre(client):
    with socket(client) as ws:
        first = ws.receive_json()
    assert first["type"] == "history.offered"
    sites = first["payload"]["sites"]
    genres = first["payload"]["genres"]
    assert {site["genre"] for site in sites} <= set(genres)
    railways = next(site for site in sites if site["id"] == "pakrailways")
    assert railways["tasks"][0] == {"label": "Find train times", "goal": "Find train times",
                                    "how": "built-in", "flow": "railways", "routine": None}


def test_a_website_added_comes_back_in_the_list(client, tmp_path):
    with socket(client) as ws:
        ws.receive_json()
        send(ws, "site.add", {"name": "My clinic", "address": "clinic.example.pk",
                              "genre": "Health"})
        answer = ws.receive_json()
    assert answer["type"] == "history.offered"
    added = answer["payload"]["sites"][-1]
    assert (added["name"], added["address"], added["genre"], added["added"]) == (
        "My clinic", "https://clinic.example.pk/", "Health", True)
    # Kept in the person's own file, not the shipped one.
    kept = json.loads((tmp_path / "catalogue.local.json").read_text(encoding="utf-8"))
    assert kept["sites"][0]["name"] == "My clinic"


@pytest.mark.parametrize("payload, reason", [
    ({"name": "", "address": "example.com", "genre": "Health"}, "name"),
    ({"name": "Mine", "address": "javascript:alert(1)", "genre": "Health"}, "address"),
    ({"name": "Again", "address": "https://www.gov.uk/bank-holidays", "genre": "Health"},
     "listed"),
    ({"address": "example.com"}, "name"),
])
def test_a_website_that_cannot_be_added_is_answered_with_why(client, payload, reason):
    with socket(client) as ws:
        ws.receive_json()
        send(ws, "site.add", payload)
        answer = ws.receive_json()
    assert answer["type"] == "error"
    assert answer["payload"] == {"code": "SITE_NOT_ADDED", "message": reason}


@pytest.mark.parametrize("goal, site, expected_site", [
    # Picked from the list: its address.
    ("When is the next bank holiday?", "https://www.gov.uk/bank-holidays",
     "https://www.gov.uk/bank-holidays"),
    # Typed as the person typed it.
    ("Track my passport application", "dgip.gov.pk", "https://dgip.gov.pk/"),
    # Written in the goal itself.
    ("when is the next bank holiday on gov.uk", None, "https://gov.uk/"),
    # A train goal on a site that is not Pakistan Railways is not a train
    # search there.
    ("trains to Karachi tomorrow", "https://www.gov.uk/", "https://www.gov.uk/"),
    # A bill goal on a real electricity company's site is not our billing copy.
    ("check my electricity bill", "https://bill.pitc.com.pk/iescobill",
     "https://bill.pitc.com.pk/iescobill"),
])
def test_a_goal_on_a_website_with_no_plan_is_not_yet(client, goal, site, expected_site):
    with socket(client) as ws:
        ws.receive_json()
        payload = {"goal": goal, "input_mode": "text"}
        if site:
            payload["site"] = site
        send(ws, "task.start", payload)
        answer = ws.receive_json()
        # The socket stays open: the next goal arrives on it.
        send(ws, "task.start", {"goal": "hello", "input_mode": "text"}, seq=2)
        after = ws.receive_json()
    assert answer["type"] == "goal.answered"
    assert answer["payload"] == {"kind": "not_yet", "goal": goal, "flows": [],
                                 "site": expected_site}
    assert after["payload"]["kind"] == "greeting"


def test_hello_on_a_website_is_still_a_greeting(client):
    with socket(client) as ws:
        ws.receive_json()
        send(ws, "task.start", {"goal": "hello", "input_mode": "text",
                                "site": "https://www.gov.uk/"})
        answer = ws.receive_json()
    assert answer["payload"]["kind"] == "greeting"


def test_a_site_that_is_not_an_address_is_ignored(client):
    with socket(client) as ws:
        ws.receive_json()
        send(ws, "task.start", {"goal": "book a flight to Dubai", "input_mode": "text",
                                "site": "javascript:alert(1)"})
        answer = ws.receive_json()
    # Routed as it always was: a request SIMBA cannot do, with no site.
    assert answer["payload"]["kind"] == "unsupported"
    assert answer["payload"].get("site") is None


def test_a_built_in_flow_runs_only_on_its_own_site(tmp_path):
    catalogue = CatalogueStore(local=tmp_path / "local.json")
    assert app_module.is_flows_site("billing", "http://127.0.0.1:5100/", catalogue)
    assert app_module.is_flows_site("railways", "https://pakrailways.gov.pk/train", catalogue)
    assert not app_module.is_flows_site("billing", "https://bill.pitc.com.pk/", catalogue)
    assert not app_module.is_flows_site("registration", "http://127.0.0.1:5100/", catalogue)
