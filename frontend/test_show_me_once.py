"""Show me once, in the overlay (2026-11-04), in a real browser.

From "Change my settings", behind a screen that says it is for a helper; the
overlay then steps aside to a bar at the top and asks the host to show the
website below it; the bar asks about each typed value and waits for the
answer to be pointed at; the read-back lists what was learned and waits for a
name; the routine is a tile, run by its id; and it can be saved to a file and
one read in. A scripted backend here plays the real one's part
(`backend/orchestrator/test_teach.py` holds that one to the same messages).
"""

import asyncio
import json
import threading
from collections.abc import Iterator

import pytest
from playwright.sync_api import Page
import websockets

from frontend.test_home import SIZES, box_fits, browser  # noqa: F401 - fixture
from frontend.test_terminal_states import overlay  # noqa: F401 - fixture

BOX = "What would you like me to do?"
WELCOMED = ("window.localStorage.setItem('simba.profile', "
            "JSON.stringify({welcomed: true, askEach: false, readAloud: false}))")
LINES = ["Ask about cookies, and press Accept all cookies if the answer is yes.",
         "Ask what to type in Reference No., and type it.",
         "Press Check Bill.",
         "Read the answer from P/WITHIN on the page. It says 14,382 now."]
READ_BACK = {
    "step_index": 1, "step_total": 1, "instruction": "Here's what I learned. Is it right?",
    "detail": "Give it a name for the home screen. Then it runs with one press.",
    "fields": [{"id": "name", "label": "Name on the home screen", "type": "text", "value": ""},
               {"id": "answer", "label": "What the answer is", "type": "text",
                "value": "P/WITHIN"}],
    "actions": [{"id": "confirm", "label": "Keep it", "kind": "primary"},
                {"id": "cancel", "label": "Stop this", "kind": "secondary"}],
    "requires_confirmation": True, "findings": [], "step_kind": "confirm", "routine": LINES,
}
ROUTINE = {"id": "r1", "label": "My bill", "site": "127.0.0.1:5100"}


class Teacher:
    """Says hello with these tiles and routines, answers `teach.start` with a
    bar, and sends whatever the test pushes."""

    def __init__(self) -> None:
        self.tiles: list[dict] = []
        self.routines: list[dict] = []
        self.received: list[dict] = []
        self.port = 0
        self.ws = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.seq = 0
        started = threading.Event()

        def run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.loop = loop

            async def handler(ws):
                self.ws = ws
                await self._send("history.offered", {"goals": [], "tiles": self.tiles,
                                                     "routines": self.routines})
                try:
                    async for raw in ws:
                        said = json.loads(raw)
                        self.received.append(said)
                        if said["type"] == "teach.start":
                            await self._send("teach.watching", {"lines": [], "pointing": False})
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

    async def _send(self, kind: str, payload: dict) -> None:
        self.seq += 1
        await self.ws.send(json.dumps({"v": 1, "type": kind, "task_id": "t", "seq": self.seq,
                                       "ts": 0, "payload": payload}))

    def push(self, kind: str, payload: dict) -> None:
        asyncio.run_coroutine_threadsafe(self._send(kind, payload), self.loop).result(5)

    def sent(self, kind: str) -> list[dict]:
        return [m["payload"] for m in self.received if m["type"] == kind]


@pytest.fixture
def backend() -> Teacher:
    return Teacher()


@pytest.fixture
def pages(browser) -> Iterator[list]:  # noqa: F811
    opened: list = []
    yield opened
    for page in opened:
        page.close()


def opened(browser, overlay: str, backend: Teacher, pages: list,  # noqa: F811
           size: str = "100%") -> tuple[Page, list[str]]:
    """The home screen, a welcomed person's, and every line the overlay logs."""
    width, height, scale = SIZES[size]
    page = browser.new_page(viewport={"width": width, "height": height},
                            device_scale_factor=scale)
    pages.append(page)
    said: list[str] = []
    page.on("console", lambda message: said.append(message.text))
    page.add_init_script(WELCOMED)
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    page.get_by_role("textbox", name=BOX).wait_for(timeout=15000)
    page.wait_for_timeout(1600)  # past the entrance
    return page, said


def to_the_intro(page: Page) -> None:
    page.get_by_test_id("change-settings").click()
    page.get_by_test_id("show-me-once").click()
    page.get_by_test_id("teach-intro").wait_for(timeout=5000)


def watching(page: Page, backend: Teacher, address: str = "127.0.0.1:5100") -> None:
    to_the_intro(page)
    page.get_by_test_id("teach-address").fill(address)
    page.get_by_test_id("teach-start").click()
    page.get_by_test_id("teach-bar").wait_for(timeout=5000)


def until(check, timeout_s: float = 5.0) -> None:
    import time

    deadline = time.monotonic() + timeout_s
    while not check():
        if time.monotonic() > deadline:
            raise AssertionError("waited and it did not happen")
        time.sleep(0.05)


# --- behind the settings, for a helper ---------------------------------------------------


def test_show_me_once_is_in_the_settings_behind_a_screen_for_a_helper(
        browser, overlay: str, backend: Teacher, pages: list) -> None:  # noqa: F811
    page, _ = opened(browser, overlay, backend, pages)
    # Not on the home screen itself.
    assert page.get_by_test_id("show-me-once").count() == 0
    to_the_intro(page)
    intro = page.get_by_test_id("teach-intro").inner_text()
    assert "helper" in intro and "I never keep a password" in intro
    # Nothing is watched until the helper says where.
    assert page.get_by_test_id("teach-start").is_disabled()
    # "Not now" goes home, calmly: nothing was started.
    page.get_by_test_id("teach-back").click()
    page.get_by_role("textbox", name=BOX).wait_for(timeout=5000)
    assert backend.sent("teach.start") == []


def test_starting_shows_the_bar_and_asks_the_host_for_the_website(
        browser, overlay: str, backend: Teacher, pages: list) -> None:  # noqa: F811
    page, said = opened(browser, overlay, backend, pages)
    watching(page, backend)

    until(lambda: backend.sent("teach.start"))
    assert backend.sent("teach.start") == [{"url": "http://127.0.0.1:5100/"}]
    assert "[simba] host bar 96" in said
    # The bar and nothing else: no home screen, no presence, no column.
    assert page.get_by_role("textbox", name=BOX).count() == 0
    assert page.get_by_test_id("teach-bar").bounding_box()["height"] == 96
    assert "I'm watching." in page.get_by_test_id("teach-bar").inner_text()


def test_an_address_without_its_beginning_is_made_whole(
        browser, overlay: str, backend: Teacher, pages: list) -> None:  # noqa: F811
    page, _ = opened(browser, overlay, backend, pages)
    watching(page, backend, "www.example.gov.pk/bills")
    until(lambda: backend.sent("teach.start"))
    assert backend.sent("teach.start")[0]["url"] == "https://www.example.gov.pk/bills"


def test_the_bar_asks_about_a_typed_value_and_then_for_the_answer(
        browser, overlay: str, backend: Teacher, pages: list) -> None:  # noqa: F811
    page, _ = opened(browser, overlay, backend, pages)
    watching(page, backend)

    backend.push("teach.watching", {"lines": LINES[:2], "pointing": False, "question": {
        "step": 1, "label": "Reference No.", "value": "04141234567890"}})
    page.get_by_test_id("teach-question").wait_for(timeout=5000)
    assert page.get_by_test_id("teach-finish").count() == 0
    page.get_by_test_id("teach-ask").click()
    until(lambda: backend.sent("teach.answer"))
    assert backend.sent("teach.answer") == [{"action": "ask", "step": 1}]

    backend.push("teach.watching", {"lines": LINES[:3], "pointing": False})
    page.get_by_test_id("teach-finish").wait_for(timeout=5000)
    assert "3 things so far." in page.get_by_test_id("teach-bar").inner_text()
    assert page.get_by_test_id("teach-last").inner_text() == LINES[2]
    page.get_by_test_id("teach-finish").click()
    until(lambda: len(backend.sent("teach.answer")) == 2)
    assert backend.sent("teach.answer")[1] == {"action": "finish"}

    backend.push("teach.watching", {"lines": LINES[:3], "pointing": True})
    page.locator("[data-testid=teach-bar][data-pointing=true]").wait_for(timeout=5000)
    assert "click the answer" in page.get_by_test_id("teach-bar").inner_text()
    assert page.get_by_test_id("teach-finish").count() == 0


def test_a_day_is_asked_about_as_a_day(
        browser, overlay: str, backend: Teacher, pages: list) -> None:  # noqa: F811
    page, _ = opened(browser, overlay, backend, pages)
    watching(page, backend)
    backend.push("teach.watching", {"lines": ["Choose 15 on the calendar."], "pointing": False,
                                    "question": {"step": 0, "label": "15", "value": "",
                                                 "kind": "day"}})
    page.get_by_test_id("teach-question").wait_for(timeout=5000)
    assert page.get_by_test_id("teach-question").inner_text() ==         "Is this day the same every time?"


def test_a_note_from_the_backend_is_said_on_the_bar(
        browser, overlay: str, backend: Teacher, pages: list) -> None:  # noqa: F811
    page, _ = opened(browser, overlay, backend, pages)
    watching(page, backend)
    note = "You haven't shown me anything yet. Do the task on the page first."
    backend.push("teach.watching", {"lines": [], "pointing": False, "note": note})
    page.get_by_test_id("teach-note").wait_for(timeout=5000)
    assert page.get_by_test_id("teach-note").inner_text().strip() == note


@pytest.mark.parametrize("size", ["100%", "125%", "150%"])
def test_the_bar_is_one_row_that_fits_at_every_size(
        browser, overlay: str, backend: Teacher, pages: list, size: str) -> None:  # noqa: F811
    page, _ = opened(browser, overlay, backend, pages, size)
    watching(page, backend)
    backend.push("teach.watching", {"lines": LINES[:2], "pointing": False, "question": {
        "step": 1, "label": "Reference No.", "value": "04141234567890"}})
    page.get_by_test_id("teach-question").wait_for(timeout=5000)
    # The bar is only as tall as the host makes the window's top: the rest of
    # the window is the website.
    page.set_viewport_size({"width": SIZES[size][0], "height": 96})
    bar = page.get_by_test_id("teach-bar")
    measured = bar.evaluate("e => ({w: e.scrollWidth, cw: e.clientWidth, h: e.scrollHeight})")
    assert measured["w"] <= measured["cw"] and measured["h"] <= 96, measured
    for button in bar.get_by_role("button").all():
        box = button.bounding_box()
        assert box["x"] + box["width"] <= SIZES[size][0] and box["y"] + box["height"] <= 96


def test_stop_watching_gives_the_window_back(
        browser, overlay: str, backend: Teacher, pages: list) -> None:  # noqa: F811
    page, said = opened(browser, overlay, backend, pages)
    watching(page, backend)
    page.get_by_test_id("teach-stop").click()
    until(lambda: backend.sent("teach.answer"))
    assert backend.sent("teach.answer") == [{"action": "cancel"}]
    assert said[-1] == "[simba] host full" or "[simba] host full" in said
    page.get_by_role("button", name="Back to start").wait_for(timeout=5000)


# --- the read-back -------------------------------------------------------------------------


def test_the_read_back_lists_what_was_learned_and_waits_for_a_name(
        browser, overlay: str, backend: Teacher, pages: list) -> None:  # noqa: F811
    page, said = opened(browser, overlay, backend, pages)
    watching(page, backend)
    backend.push("task.started", {"goal": "Show me once", "estimated_steps": 1})
    backend.push("step.presented", READ_BACK)
    page.get_by_test_id("read-back").wait_for(timeout=5000)
    # The website is covered again the moment the read-back arrives.
    assert "[simba] host full" in said
    lines = page.get_by_test_id("read-back-lines").locator("li").all_inner_texts()
    assert [line.split("\n")[-1].strip() for line in lines] == LINES
    assert lines[0].startswith("1.")
    keep = page.get_by_test_id("read-back-keep")
    assert keep.is_disabled()
    page.get_by_test_id("read-back-name").fill("My bill")
    page.get_by_test_id("read-back-answer").fill("Amount due")
    keep.click()
    until(lambda: backend.sent("step.response"))
    assert backend.sent("step.response") == [{"step_index": 1, "action_id": "confirm",
                                              "input_values": {"name": "My bill",
                                                               "answer": "Amount due"}}]


@pytest.mark.parametrize("size", ["100%", "125%", "150%"])
def test_the_read_back_fits_the_window_at_every_size(
        browser, overlay: str, backend: Teacher, pages: list, size: str) -> None:  # noqa: F811
    page, _ = opened(browser, overlay, backend, pages, size)
    watching(page, backend)
    backend.push("task.started", {"goal": "Show me once", "estimated_steps": 1})
    backend.push("step.presented", {**READ_BACK, "note": "Give it a name first."})
    page.get_by_test_id("read-back").wait_for(timeout=5000)
    page.wait_for_timeout(600)
    keep = page.get_by_test_id("read-back-keep").bounding_box()
    height = SIZES[size][1]
    scrolls = page.evaluate("() => document.scrollingElement.scrollHeight > window.innerHeight")
    assert keep["y"] + keep["height"] <= height and not scrolls, (keep, height)


# --- a routine on the home screen ------------------------------------------------------------


def test_a_routine_is_a_tile_and_starts_by_its_id(
        browser, overlay: str, backend: Teacher, pages: list) -> None:  # noqa: F811
    backend.routines = [ROUTINE]
    page, _ = opened(browser, overlay, backend, pages)
    tile = page.get_by_test_id("own-routine")
    assert tile.inner_text().strip() == "My bill"
    tile.click()
    until(lambda: backend.sent("task.start"))
    start = backend.sent("task.start")[0]
    assert start["routine"] == "r1" and start["goal"] == "My bill" and "tile" not in start


@pytest.mark.parametrize("size", ["100%", "150%"])
def test_two_tiles_and_a_routine_still_fit(
        browser, overlay: str, backend: Teacher, pages: list, size: str) -> None:  # noqa: F811
    backend.tiles = [{"id": "a1", "label": "Electricity", "flow": "billing"},
                     {"id": "b2", "label": "Trains to Karachi", "flow": "railways"}]
    backend.routines = [ROUTINE]
    page, _ = opened(browser, overlay, backend, pages, size)
    assert page.get_by_test_id("own-routine").count() == 1
    fits, measured = box_fits(page)
    assert fits, measured


def test_with_the_row_full_nothing_can_be_started(
        browser, overlay: str, backend: Teacher, pages: list) -> None:  # noqa: F811
    backend.tiles = [{"id": "a1", "label": "One", "flow": "billing"},
                     {"id": "b2", "label": "Two", "flow": "railways"}]
    backend.routines = [ROUTINE]
    page, _ = opened(browser, overlay, backend, pages)
    to_the_intro(page)
    assert page.get_by_test_id("teach-full").is_visible()
    assert page.get_by_test_id("teach-start").count() == 0
    assert page.get_by_test_id("teach-from-file").count() == 0


def test_a_routine_is_saved_to_a_file_and_one_is_read_in(
        browser, overlay: str, backend: Teacher, pages: list, tmp_path) -> None:  # noqa: F811
    backend.routines = [ROUTINE]
    page, _ = opened(browser, overlay, backend, pages)
    page.get_by_test_id("change-tiles").click()
    page.get_by_test_id("routine-save").click()
    until(lambda: backend.sent("routine.export"))
    assert backend.sent("routine.export") == [{"id": "r1"}]
    with page.expect_download() as download:
        backend.push("routine.file", {"label": "My bill", "name": "my-bill.simba-routine.json",
                                      "file": "{\"format\": \"simba-routine\"}"})
    assert download.value.suggested_filename == "my-bill.simba-routine.json"

    page.get_by_test_id("tiles-back").click()
    to_the_intro(page)
    shared = tmp_path / "shared.simba-routine.json"
    shared.write_text("{\"format\": \"simba-routine\", \"version\": 1}", encoding="utf-8")
    page.get_by_test_id("teach-file").set_input_files(str(shared))
    until(lambda: backend.sent("routine.import"))
    assert backend.sent("routine.import")[0]["file"].startswith("{\"format\"")
    backend.push("error", {"code": "ROUTINE_NOT_READ", "message": "not a routine"})
    page.get_by_test_id("file-note").wait_for(timeout=5000)
    assert page.get_by_test_id("file-note").inner_text() == "I couldn't use that file."
