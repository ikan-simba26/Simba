"""The real page behind the step, in a real browser (2026-10-07).

When a task starts the page shows clearly for a moment, then softens behind
the card; "Show the real page" clears it while held, or until "Hide the real
page" after a tap; and none of this counts as asking for help. Against a
scripted backend that answers every `trust.requested` with a picture, as the
real one does (`loop.send_preview`).
"""

import asyncio
import base64
import json
import threading
from collections.abc import Iterator

import pytest
import websockets
from playwright.sync_api import Page, Playwright

from frontend.test_terminal_states import overlay  # noqa: F401 - fixture

GOAL = "trains to Rawalpindi tomorrow"

A_STEP = {
    "step_index": 1, "step_total": 3,
    "instruction": "Let me set where you're starting from.", "detail": "",
    "fields": [], "requires_confirmation": True, "findings": [],
    "actions": [
        {"id": "confirm", "label": "Set the departure station", "kind": "primary"},
        {"id": "cancel", "label": "Stop this", "kind": "secondary"},
    ],
}
DONE = {"summary": GOAL, "duration_ms": 1000, "steps_taken": 1, "llm_calls": 0,
        "replayed": False, "findings": []}


class PictureBackend:
    """Plays a task with one step, answering every picture request.

    `trust.requested` gets a `page.preview` back whenever it arrives, the way
    the real backend answers it while a step is on screen. Every message the
    overlay sends is kept."""

    def __init__(self, picture: str) -> None:
        self.picture = picture
        self.heard: list[dict] = []
        self.finish = threading.Event()
        self.port = 0
        started = threading.Event()

        def run() -> None:
            loop = asyncio.new_event_loop()

            async def handler(ws):
                seq = 0

                async def send(kind: str, payload: dict) -> None:
                    nonlocal seq
                    seq += 1
                    await ws.send(json.dumps({"v": 1, "type": kind, "task_id": "t", "seq": seq,
                                              "ts": 0, "payload": payload}))

                await send("history.offered", {"goals": []})
                await ws.recv()  # task.start
                await send("task.started", {"goal": GOAL, "estimated_steps": 3})
                await send("state.changed", {"state": "waiting"})
                await send("step.presented", A_STEP)
                async for raw in ws:
                    said = json.loads(raw)
                    self.heard.append(said)
                    if said["type"] == "trust.requested":
                        await send("page.preview", {
                            "screenshot": self.picture,
                            "highlight": {"x": 0, "y": 0, "w": 0, "h": 0},
                            "caption": "This is the page I'm working on."})
                    if said["type"] == "step.response":
                        await send("task.completed", DONE)
                        await ws.close()
                        return

            async def main() -> None:
                server = await websockets.serve(handler, "127.0.0.1", 0)
                self.port = server.sockets[0].getsockname()[1]
                started.set()
                await asyncio.Future()

            loop.run_until_complete(main())

        threading.Thread(target=run, daemon=True).start()
        started.wait(timeout=10)


@pytest.fixture(scope="module")
def browser(playwright_instance: Playwright):
    browser = playwright_instance.chromium.launch()
    yield browser
    browser.close()


@pytest.fixture(scope="module")
def picture(browser) -> str:
    """A stand-in for the real page: busy, and unmistakably not the overlay."""
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.set_content("<body style='margin:0;background:#2a6;font:64px sans-serif'>"
                     + "TRAIN TIMINGS " * 40 + "</body>")
    shot = base64.b64encode(page.screenshot()).decode("ascii")
    page.close()
    return shot


@pytest.fixture
def page(browser) -> Iterator[Page]:
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    yield page
    page.close()


def start(page: Page, overlay: str, picture: str) -> PictureBackend:  # noqa: F811
    backend = PictureBackend(picture)
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    page.fill("input[aria-label='What would you like me to do?']", GOAL)
    page.get_by_role("button", name="Start").click()
    page.wait_for_selector("[data-testid=step-shell]", timeout=15000)
    page.wait_for_selector("[data-testid=backdrop]", timeout=10000)
    return backend


def clear(page: Page) -> str:
    return page.get_attribute("[data-testid=backdrop]", "data-clear")


def card_opacity(page: Page) -> float:
    return float(page.evaluate(
        "getComputedStyle(document.querySelector('[data-testid=step-shell]')"
        ".closest('[style*=pointer-events]')).opacity"))


def test_the_page_shows_clearly_then_softens_behind_the_step(
    page: Page, overlay: str, picture: str  # noqa: F811
) -> None:
    start(page, overlay, picture)

    assert clear(page) == "true"
    page.wait_for_function(
        "document.querySelector('[data-testid=backdrop]').dataset.clear === 'false'",
        timeout=4000)
    page.wait_for_timeout(1200)  # the fade
    blurred = page.evaluate(
        "[...document.querySelectorAll('[data-testid=backdrop] img')]"
        ".map(i => getComputedStyle(i).filter + '|' + getComputedStyle(i).opacity)")
    assert any("blur(18px)|1" == b for b in blurred), blurred


def test_holding_the_button_shows_the_page_and_letting_go_hides_it(
    page: Page, overlay: str, picture: str  # noqa: F811
) -> None:
    start(page, overlay, picture)
    page.wait_for_function(
        "document.querySelector('[data-testid=backdrop]').dataset.clear === 'false'",
        timeout=4000)

    button = page.get_by_test_id("peek")
    box = button.bounding_box()
    page.mouse.move(box["x"] + 20, box["y"] + 20)
    page.mouse.down()
    page.wait_for_timeout(900)
    assert clear(page) == "true"
    assert card_opacity(page) < 0.1
    page.mouse.up()
    page.wait_for_timeout(900)

    assert clear(page) == "false"
    assert card_opacity(page) > 0.9


def test_a_tap_keeps_the_page_until_hide_is_pressed(
    page: Page, overlay: str, picture: str  # noqa: F811
) -> None:
    start(page, overlay, picture)

    page.get_by_test_id("peek").click()
    page.wait_for_timeout(2500)  # past the first clear moment
    assert clear(page) == "true"

    page.get_by_role("button", name="Hide the real page").click()
    page.wait_for_timeout(900)
    assert clear(page) == "false"
    assert card_opacity(page) > 0.9


def test_the_keyboard_can_show_it_too(page: Page, overlay: str, picture: str) -> None:  # noqa: F811
    start(page, overlay, picture)
    page.get_by_test_id("peek").focus()

    page.keyboard.press("Enter")
    page.wait_for_timeout(2500)

    assert clear(page) == "true"


def test_none_of_it_counts_as_asking_for_help(
    page: Page, overlay: str, picture: str  # noqa: F811
) -> None:
    """Only "What are you doing?" is the person asking. The picture asked for
    with every step, and looking at the page, are not."""
    backend = start(page, overlay, picture)
    page.get_by_test_id("peek").click()
    page.get_by_role("button", name="Hide the real page").click()
    page.wait_for_timeout(600)

    page.get_by_role("button", name="Set the departure station").click()
    page.wait_for_timeout(800)

    asked = [m for m in backend.heard if m["type"] == "trust.requested"]
    assert len(asked) >= 1
    samples = [m["payload"] for m in backend.heard if m["type"] == "telemetry"]
    assert samples and all(s.get("help_presses", 0) == 0 for s in samples), samples


def test_the_page_is_gone_when_the_task_ends(
    page: Page, overlay: str, picture: str  # noqa: F811
) -> None:
    start(page, overlay, picture)

    page.get_by_role("button", name="Set the departure station").click()
    page.wait_for_timeout(1500)

    assert page.locator("[data-testid=backdrop]").count() == 0


@pytest.mark.parametrize("size, viewport", [
    ("125%", (1280, 734, 1.25)), ("150%", (1266, 606, 1.5))])
def test_the_row_under_the_step_fits(browser, overlay: str, picture: str,  # noqa: F811
                                     size: str, viewport) -> None:
    width, height, scale = viewport
    page = browser.new_page(viewport={"width": width, "height": height},
                            device_scale_factor=scale)
    try:
        start(page, overlay, picture)
        page.wait_for_timeout(1500)
        for name in ("What are you doing?", "Show the real page", "Stop this"):
            box = page.get_by_role("button", name=name, exact=True).bounding_box()
            assert box and box["y"] + box["height"] <= height, (size, name, box)
        assert not page.evaluate(
            "document.scrollingElement.scrollHeight > window.innerHeight"), size
    finally:
        page.close()
