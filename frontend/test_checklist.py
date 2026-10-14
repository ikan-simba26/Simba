"""The checklist: what SIMBA does by itself once the person has decided (2026-10-14).

Against a scripted backend that sends checklist lines — `step.presented` with
`requires_confirmation: false` — the way the real one does
(`backend/orchestrator/test_checklist.py` covers the backend's side).
"""

import json
from collections.abc import Iterator

import pytest
from playwright.sync_api import Page, Playwright

from frontend.test_terminal_states import AWAIT_RESPONSE, Backend, overlay  # noqa: F401

GOAL = "trains from Rawalpindi to Sukkur tomorrow"
TRIP = ["From", "To", "Day", "Search", "Trains"]


def line(index: int, label: str) -> dict:
    return {"step_index": index, "step_total": 9, "instruction": label, "detail": "",
            "fields": [], "actions": [], "requires_confirmation": False, "findings": [],
            "stage": 3}


PAUSED = {"step_index": 4, "step_total": 9,
          "instruction": "I've paused. Carry on when you're ready.", "detail": "",
          "fields": [], "requires_confirmation": True, "findings": [], "stage": 3,
          "actions": [{"id": "confirm", "label": "Carry on", "kind": "primary"},
                      {"id": "cancel", "label": "Stop this", "kind": "secondary"}]}

RUNNING = [
    ("task.started", {"goal": GOAL, "estimated_steps": 6, "stages": TRIP}),
    ("state.changed", {"state": "acting"}),
    ("step.presented", line(1, "Filling in where you're starting from")),
    ("step.presented", line(2, "Filling in where you're going")),
    ("step.presented", line(3, "Opening the calendar")),
    # Held here: the next thing the backend waits for is the Pause.
    (AWAIT_RESPONSE, {}),
    ("state.changed", {"state": "waiting"}),
    ("step.presented", PAUSED),
    (AWAIT_RESPONSE, {}),
]


@pytest.fixture(scope="module")
def backend() -> Backend:
    return Backend()


@pytest.fixture(scope="module")
def browser(playwright_instance: Playwright):
    browser = playwright_instance.chromium.launch()
    yield browser
    browser.close()


@pytest.fixture
def page(browser) -> Iterator[Page]:
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()
    yield page
    context.close()


def begin(page: Page, overlay: str, backend: Backend, script=RUNNING) -> None:  # noqa: F811
    backend.script = script
    backend.responses.clear()
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    page.fill("input[aria-label='What would you like me to do?']", GOAL)
    page.get_by_role("button", name="Start").click()
    page.wait_for_selector("[data-testid=checklist]", timeout=15000)
    page.wait_for_timeout(900)


def lines(page: Page) -> list[tuple[str, str]]:
    return [tuple(x) for x in page.eval_on_selector_all(
        "[data-testid=checklist-lines] li",
        "items => items.map(i => [i.lastElementChild.innerText, i.dataset.state])")]


def test_the_lines_tick_off_and_the_last_is_being_done(page: Page, overlay: str,  # noqa: F811
                                                        backend: Backend) -> None:
    begin(page, overlay, backend)

    assert lines(page) == [("Filling in where you're starting from", "done"),
                           ("Filling in where you're going", "done"),
                           ("Opening the calendar", "now")]
    assert page.get_by_text("I'm doing what you asked.").is_visible()
    # One thing to press, and it is Pause.
    buttons = page.eval_on_selector_all(
        "[data-testid=checklist] button", "bs => bs.map(b => b.innerText.trim())")
    assert buttons == ["Pause"]


def test_pause_asks_the_backend_to_stop_before_its_next_move(page: Page, overlay: str,  # noqa: F811
                                                             backend: Backend) -> None:
    begin(page, overlay, backend)

    page.get_by_role("button", name="Pause").click()
    page.wait_for_selector("text=I've paused. Carry on when you're ready.", timeout=10000)

    pauses = [m["payload"] for m in backend.responses if m.get("type") == "step.response"]
    assert pauses[0] == {"step_index": 3, "action_id": "pause", "input_values": {}}
    assert page.get_by_role("button", name="Carry on").is_visible()


def test_no_telemetry_is_about_a_checklist_line(page: Page, overlay: str,  # noqa: F811
                                               backend: Backend) -> None:
    """There was no decision to measure."""
    begin(page, overlay, backend)
    page.wait_for_timeout(3500)  # past a timer sample, if one were sent

    samples = [m["payload"] for m in backend.responses if m.get("type") == "telemetry"]
    assert all(s["step_index"] not in (1, 2, 3) for s in samples), samples


def test_the_setting_to_be_asked_every_time_is_sent_and_kept(page: Page, overlay: str,  # noqa: F811
                                                            backend: Backend) -> None:
    backend.script = []
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    box = page.get_by_role("checkbox", name="Ask me before each thing I do")
    assert not box.is_checked()

    box.check()
    page.reload()
    assert page.get_by_role("checkbox", name="Ask me before each thing I do").is_checked()


def test_the_setting_reaches_the_backend(browser, overlay: str) -> None:  # noqa: F811
    """Read off the socket as the task starts."""
    import asyncio
    import threading

    import websockets

    started: list[dict] = []
    ready = threading.Event()
    port_holder: list[int] = []

    def serve() -> None:
        async def handler(ws):
            await ws.send(json.dumps({"v": 1, "type": "history.offered", "task_id": "t",
                                      "seq": 1, "ts": 0, "payload": {"goals": []}}))
            started.append(json.loads(await ws.recv()))
            await asyncio.Future()

        async def main() -> None:
            server = await websockets.serve(handler, "127.0.0.1", 0)
            port_holder.append(server.sockets[0].getsockname()[1])
            ready.set()
            await asyncio.Future()

        asyncio.new_event_loop().run_until_complete(main())

    threading.Thread(target=serve, daemon=True).start()
    ready.wait(10)
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()
    try:
        page.goto(f"{overlay}?ws=ws://127.0.0.1:{port_holder[0]}")
        page.get_by_role("checkbox", name="Ask me before each thing I do").check()
        page.fill("input[aria-label='What would you like me to do?']", GOAL)
        page.get_by_role("button", name="Start").click()
        page.wait_for_timeout(1500)
        assert started and started[0]["payload"]["confirm_each"] is True
    finally:
        context.close()


def test_the_checklist_fits_at_150_percent(browser, overlay: str,  # noqa: F811
                                          backend: Backend) -> None:
    context = browser.new_context(viewport={"width": 1266, "height": 632},
                                  device_scale_factor=1.5)
    page = context.new_page()
    try:
        five = RUNNING[:2] + [("step.presented", line(i, label)) for i, label in enumerate(
            ["Filling in where you're starting from", "Filling in where you're going",
             "Opening the calendar", "Choosing 15 October", "Searching"], start=1)] + [
            (AWAIT_RESPONSE, {})]
        begin(page, overlay, backend, five)
        assert not page.evaluate("document.scrollingElement.scrollHeight > innerHeight")
        box = page.get_by_role("button", name="Pause").bounding_box()
        assert box and box["y"] + box["height"] <= 632
    finally:
        context.close()
