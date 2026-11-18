"""The person's own tiles on the home screen (2026-10-18).

A task kept from its closing screen becomes a tile — "My bill", "Trains to
Karachi" — offered first on the home screen, above the three things SIMBA can
do, which then read "Things I can help with". Pressed, it is started by its id;
its details never reach the overlay. "Change my tiles" renames, moves and
removes them, each change answered by the backend with the tiles as they now
stand. A scripted backend here plays that part; `backend/orchestrator/
test_tiles.py` holds the real one to the same messages.
"""

import asyncio
import json
import threading
from collections.abc import Iterator

import pytest
import websockets
from playwright.sync_api import Page

from frontend.test_home import SIZES, box_fits, browser  # noqa: F401 - fixture
from frontend.test_terminal_states import TAILS, AWAIT_RESPONSE, Backend, overlay  # noqa: F401

BOX = "What would you like me to do?"
MINE = [{"id": "a1", "label": "My bill", "flow": "billing"},
        {"id": "b2", "label": "Trains to Karachi", "flow": "railways"},
        {"id": "c3", "label": "Trains home", "flow": "railways"}]


class Tiles:
    """Says hello with these tiles and goals; answers `tile.change` as the
    backend does, with the tiles as they then stand."""

    def __init__(self) -> None:
        self.tiles: list[dict] = []
        self.goals: list[dict] = []
        self.received: list[dict] = []
        self.port = 0
        started = threading.Event()

        def run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def offer(ws) -> None:
                await ws.send(json.dumps({
                    "v": 1, "type": "history.offered", "task_id": "t", "seq": 1, "ts": 0,
                    "payload": {"goals": self.goals, "tiles": self.tiles}}))

            async def handler(ws):
                await offer(ws)
                try:
                    async for raw in ws:
                        said = json.loads(raw)
                        self.received.append(said)
                        if said["type"] == "tile.change":
                            self.change(said["payload"])
                            await offer(ws)
                except websockets.ConnectionClosed:
                    return

            async def main() -> None:
                server = await websockets.serve(handler, "127.0.0.1", 0)
                self.port = server.sockets[0].getsockname()[1]
                started.set()
                await asyncio.Future()

            loop.run_until_complete(main())

        threading.Thread(target=run, daemon=True).start()
        started.wait(timeout=10)

    def change(self, change: dict) -> None:
        index = next((i for i, t in enumerate(self.tiles) if t["id"] == change.get("id")), None)
        if change["action"] == "clear":
            self.tiles = []
        elif index is None:
            return
        elif change["action"] == "rename":
            self.tiles[index] = {**self.tiles[index], "label": change["label"]}
        elif change["action"] == "remove":
            self.tiles.pop(index)
        elif change["action"] == "move":
            self.tiles.insert(change["to"], self.tiles.pop(index))

    def sent(self, kind: str) -> list[dict]:
        return [m["payload"] for m in self.received if m["type"] == kind]


@pytest.fixture
def backend() -> Tiles:
    return Tiles()


@pytest.fixture
def pages(browser) -> Iterator[list]:  # noqa: F811
    opened: list = []
    yield opened
    for page in opened:
        page.close()


def home(browser, overlay: str, backend: Tiles, pages: list, size: str = "100%",  # noqa: F811
         tiles: list[dict] | None = None, goals: list[str] | None = None) -> Page:
    backend.tiles = [dict(t) for t in (MINE if tiles is None else tiles)]
    backend.goals = [{"goal": g, "site": "127.0.0.1"} for g in goals or []]
    width, height, scale = SIZES[size]
    page = browser.new_page(viewport={"width": width, "height": height},
                            device_scale_factor=scale)
    pages.append(page)
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    page.get_by_role("textbox", name=BOX).wait_for(timeout=15000)
    if backend.tiles:
        page.get_by_test_id("own-tile").first.wait_for(timeout=10000)
    page.wait_for_timeout(1600)  # past the entrance
    return page


def own_on(page: Page) -> list[str]:
    return [t.inner_text().strip() for t in page.get_by_test_id("own-tile").all()]


def test_with_no_tiles_of_their_own_the_three_say_what_they_are(
    browser, overlay: str, backend: Tiles, pages: list  # noqa: F811
) -> None:
    page = home(browser, overlay, backend, pages, tiles=[])

    assert page.get_by_test_id("own-tiles").count() == 0
    assert page.get_by_test_id("can-help").inner_text() == "Things I can help with"
    # The three at their full size, each with its picture.
    assert page.locator("[data-testid=tile] svg").count() >= 3


def test_their_own_tiles_come_first(
    browser, overlay: str, backend: Tiles, pages: list  # noqa: F811
) -> None:
    page = home(browser, overlay, backend, pages)

    assert own_on(page) == ["My bill", "Trains to Karachi", "Trains home"]
    mine = page.get_by_test_id("own-tiles").bounding_box()
    theirs = page.get_by_test_id("tiles").bounding_box()
    # Beside them, in the column on the right (the home redesign, 2026-11-17), not over them.
    assert mine["x"] >= theirs["x"] + theirs["width"] - 1
    assert page.get_by_test_id("can-help").is_visible()
    assert len(page.get_by_test_id("tile").all()) == 3


def test_a_tile_is_started_by_its_id_and_nothing_else(
    browser, overlay: str, backend: Tiles, pages: list  # noqa: F811
) -> None:
    page = home(browser, overlay, backend, pages)
    page.get_by_test_id("own-tile").nth(1).click()
    page.wait_for_timeout(600)

    [start] = backend.sent("task.start")
    assert start["tile"] == "b2" and start["flow"] == "railways"
    assert start["goal"] == "Trains to Karachi"


def test_tiles_can_be_renamed_moved_and_taken_off(
    browser, overlay: str, backend: Tiles, pages: list  # noqa: F811
) -> None:
    page = home(browser, overlay, backend, pages)
    page.get_by_test_id("change-tiles").click()
    page.get_by_test_id("tiles-editor").wait_for()

    name = page.get_by_role("textbox", name="Name of My bill")
    name.fill("Electricity")
    name.press("Enter")
    page.get_by_test_id("tile-row").nth(2).get_by_role("button", name="Move left").click()
    page.wait_for_timeout(300)
    page.get_by_test_id("tile-row").nth(0).get_by_role("button", name="Take it off").click()
    page.wait_for_timeout(300)
    page.get_by_test_id("tiles-back").click()
    page.get_by_test_id("own-tile").first.wait_for()

    assert backend.sent("tile.change") == [
        {"action": "rename", "id": "a1", "label": "Electricity"},
        {"action": "move", "id": "c3", "to": 1},
        {"action": "remove", "id": "a1"},
    ]
    assert own_on(page) == ["Trains home", "Trains to Karachi"]
    # The first cannot move left, the last cannot move right.
    page.get_by_test_id("change-tiles").click()
    rows = page.get_by_test_id("tile-row")
    assert rows.first.get_by_role("button", name="Move left").is_disabled()
    assert rows.last.get_by_role("button", name="Move right").is_disabled()


@pytest.mark.parametrize("size", list(SIZES))
def test_three_tiles_and_two_goals_asked_before_still_fit(
    size: str, browser, overlay: str, backend: Tiles, pages: list  # noqa: F811
) -> None:
    page = home(browser, overlay, backend, pages, size,
                goals=["Find trains from Lahore Cantt to Rawalpindi on 2026-10-01.",
                       "Register for CS-401"])

    fits, measured = box_fits(page)
    assert fits, (size, measured)
    for tile in page.get_by_test_id("own-tile").all():
        box = tile.bounding_box()
        assert box["y"] >= 0 and box["y"] + box["height"] <= page.viewport_size["height"]


def test_keep_it_sends_the_answer_with_the_name_offered(
    browser, overlay: str, pages: list  # noqa: F811
) -> None:
    ending = Backend()
    ending.script = [("task.started", {"goal": "g", "estimated_steps": 3}),
                     *TAILS["completed with trains, an offer to book, and an offer to keep"]]
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    pages.append(page)
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{ending.port}")
    page.get_by_role("textbox", name=BOX).fill("trains to Karachi")
    page.get_by_role("button", name="Start", exact=True).click()
    page.get_by_test_id("keep-it").click()
    page.get_by_test_id("kept").wait_for(timeout=5000)
    page.wait_for_timeout(300)

    keeps = [m["payload"] for m in ending.responses if m.get("type") == "step.response"]
    assert keeps == [{"step_index": 0, "action_id": "keep",
                      "input_values": {"label": "Trains to Karachi"}}]
    assert page.get_by_test_id("kept").inner_text() == (
        "Kept on your home screen as Trains to Karachi.")
    # The offer to book is still there.
    assert page.get_by_test_id("offer").is_visible()
