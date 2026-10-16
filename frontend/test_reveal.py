"""One way to see the real page on any screen (2026-10-16), in a real browser.

During a step: "What are you doing?", which opens the close-up on what is
about to be touched, with the whole page a press away inside it. At the end:
"See it on the real page", and nothing else. Until 2026-10-16 a step also had
"Show the real page" beside it — a second button to a second picture of the
same page, drawn behind the step (2026-10-07) — and a picture was asked for
with every step to be ready for it. Against a scripted backend that answers
every `trust.requested` with a picture, as the real one does
(`loop.send_preview`).
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
        "replayed": False, "findings": [],
        "proof": {"screenshot": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQ"
                            "DwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
                  "caption": "What I read is ringed.",
                  "rings": [{"x": 728, "y": 143, "w": 118, "h": 17}]}}


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
                            "highlight": {"x": 300, "y": 120, "w": 140, "h": 36},
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
    page.wait_for_timeout(600)
    return backend


#: Every way the overlay has had of showing the real page.
PAGE_BUTTONS = ("What are you doing?", "Show the real page", "See it on the real page")


def page_buttons(page: Page) -> list[str]:
    return [name for name in PAGE_BUTTONS
            if page.get_by_role("button", name=name, exact=True).count()]


def test_a_step_has_one_way_to_see_the_page(page: Page, overlay: str,  # noqa: F811
                                            picture: str) -> None:
    start(page, overlay, picture)

    assert page_buttons(page) == ["What are you doing?"]
    # And nothing of the page is drawn behind the step.
    assert page.locator("[data-testid=backdrop]").count() == 0


def test_it_opens_close_up_with_the_whole_page_inside(page: Page, overlay: str,  # noqa: F811
                                                      picture: str) -> None:
    start(page, overlay, picture)

    page.get_by_role("button", name="What are you doing?").click()
    page.get_by_test_id("trust-panel").wait_for(timeout=10000)
    page.get_by_test_id("trust-highlight").wait_for(timeout=5000)
    assert page.get_by_role("button", name="Show the whole page").is_visible()

    page.get_by_role("button", name="Show the whole page").click()
    assert page.get_by_role("button", name="Show it close up").is_visible()
    page.get_by_role("button", name="Hide the page").click()
    page.wait_for_timeout(900)
    assert page.get_by_test_id("trust-panel").count() == 0


def test_no_picture_is_asked_for_unless_the_person_asks(
    page: Page, overlay: str, picture: str  # noqa: F811
) -> None:
    """A picture was asked for with every step, for the page behind it. That
    page is gone, and so is the asking."""
    backend = start(page, overlay, picture)
    page.wait_for_timeout(1500)
    assert [m for m in backend.heard if m["type"] == "trust.requested"] == []

    page.get_by_role("button", name="What are you doing?").click()
    page.get_by_test_id("trust-panel").wait_for(timeout=10000)
    assert len([m for m in backend.heard if m["type"] == "trust.requested"]) == 1


def test_the_end_has_one_way_to_see_the_page(page: Page, overlay: str,  # noqa: F811
                                             picture: str) -> None:
    start(page, overlay, picture)

    page.get_by_role("button", name="Set the departure station").click()
    page.get_by_role("button", name="I'm done").wait_for(timeout=10000)
    page.wait_for_timeout(600)

    assert page_buttons(page) == ["See it on the real page"]


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
        for name in ("What are you doing?", "Stop this"):
            box = page.get_by_role("button", name=name, exact=True).bounding_box()
            assert box and box["y"] + box["height"] <= height, (size, name, box)
        assert not page.evaluate(
            "document.scrollingElement.scrollHeight > window.innerHeight"), size
    finally:
        page.close()


def test_asking_with_no_picture_coming_says_so(browser, overlay: str) -> None:  # noqa: F811
    """"What are you doing?" pressed while no picture comes: until 2026-10-16
    the press did nothing at all. Now, once the wait is over, it says so and
    offers the way back."""
    from frontend.test_terminal_states import AWAIT_RESPONSE, Backend

    backend = Backend()  # answers no request for a picture
    backend.script = [("task.started", {"goal": GOAL, "estimated_steps": 3}),
                      ("state.changed", {"state": "waiting"}),
                      ("step.presented", A_STEP), (AWAIT_RESPONSE, {})]
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    try:
        page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
        page.fill("input[aria-label='What would you like me to do?']", GOAL)
        page.get_by_role("button", name="Start").click()
        page.wait_for_selector("[data-testid=step-shell]", timeout=15000)
        page.get_by_role("button", name="What are you doing?").click()
        page.get_by_test_id("no-picture").wait_for(timeout=9000)
        assert "I couldn't get a picture just now." in page.inner_text("[data-testid=no-picture]")
        page.get_by_role("button", name="Close").click()
        page.wait_for_timeout(800)
        assert page.get_by_test_id("no-picture").count() == 0
        assert page.get_by_role("button", name="What are you doing?").is_visible()
    finally:
        page.close()
