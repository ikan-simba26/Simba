"""B3 (2026-11-18): each finished answer in "So far" has a Change button.

Pressed, the task starts again on the same website with every other answer kept
(`task.start.keep_answers`) and that one question asked again. Never after
something was done on the website (Do it, Pay now), and never for a secret.

Requires `npm run build` in frontend/ first; skipped otherwise.
"""

import asyncio
import functools
import http.server
import json
import socketserver
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
import websockets
from playwright.sync_api import Page, Playwright

DIST = Path(__file__).resolve().parent / "dist"

pytestmark = pytest.mark.skipif(
    not (DIST / "index.html").exists(),
    reason="frontend not built; run `npm run build` in frontend/",
)

GOAL = "Book a bus from Lahore to Karachi on Friday"
STOP = {"id": "cancel", "label": "Stop this", "kind": "secondary"}


def choice(label: str, index: int, sub: str = "") -> dict:
    return {"id": f"choice:{index}", "label": label, "kind": "primary", "sub": sub}


def step(index: int, instruction: str, **more) -> dict:
    body = {"step_index": index, "step_total": 8, "instruction": instruction, "detail": "",
            "fields": [], "actions": [], "requires_confirmation": True}
    body.update(more)
    return body


WHICH_BUS = step(1, "Which bus would you like?", actions=[
    choice("8:30 am", 0, "Rs 6,200"), choice("2:00 pm", 1, "Rs 5,400"), STOP])
WHICH_SEAT = step(2, "Which seat would you like?", actions=[
    choice("Seat 9 · Window", 0), choice("Seat 10 · Aisle", 1), STOP])
PASSWORD = step(3, "Choose a password.", fields=[
    {"id": "pw", "label": "Password", "type": "password", "value": ""}],
    actions=[{"id": "confirm", "label": "Next", "kind": "primary"}, STOP])
FINAL = step(4, "I will press Book for Rs 6,200.", final=[{"label": "Amount", "value": "Rs 6,200"}],
             actions=[{"id": "confirm", "label": "Book it", "kind": "primary"},
                      {"id": "decline", "label": "Don't book", "kind": "primary"}])

BUS_CHANGE = "Change: 8:30 am · Rs 6,200"


@pytest.fixture(scope="module")
def static_site() -> Iterator[str]:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DIST))
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/index.html"
    finally:
        server.shutdown()
        server.server_close()


class Backend:
    """Plays the script on every `task.start`, one question at a time, records
    each start and each answer, and closes the socket on a Stop answer (as the
    real backend does)."""

    def __init__(self) -> None:
        self.script: list[dict] = []
        self.starts: list[dict] = []
        self.answers: list[dict] = []
        self.port = 0
        ready = threading.Event()

        def run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def handler(ws):
                try:
                    start = json.loads(await ws.recv())
                    self.starts.append(start["payload"])
                    for seq, payload in enumerate(list(self.script), 1):
                        await ws.send(json.dumps({"v": 1, "type": "step.presented", "task_id": "t",
                                                  "seq": seq, "ts": 0, "payload": payload}))
                        # Telemetry arrives beside the answer: wait for the answer itself.
                        reply = json.loads(await ws.recv())
                        while reply.get("type") != "step.response":
                            reply = json.loads(await ws.recv())
                        self.answers.append(reply.get("payload", {}))
                        if reply["payload"].get("action_id") == "cancel":
                            await ws.close()
                            return
                    await asyncio.Future()
                except (websockets.ConnectionClosed, asyncio.CancelledError):
                    return

            async def main() -> None:
                server = await websockets.serve(handler, "127.0.0.1", 0)
                self.port = server.sockets[0].getsockname()[1]
                ready.set()
                await asyncio.Future()

            loop.run_until_complete(main())

        threading.Thread(target=run, daemon=True).start()
        ready.wait(timeout=10)


@pytest.fixture()
def backend() -> Backend:
    return Backend()


@pytest.fixture()
def page(playwright_instance: Playwright) -> Iterator[Page]:
    browser = playwright_instance.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    for flag in ("__simbaSettleMs = 0", "__simbaWelcome = false", "__simbaSplash = false"):
        page.add_init_script(f"window.{flag}")
    yield page
    browser.close()


def begin(page: Page, site: str, backend: Backend, script: list[dict]) -> None:
    backend.script = script
    page.goto(f"{site}?ws=ws://127.0.0.1:{backend.port}")
    page.fill("input[aria-label='What would you like me to do?']", GOAL)
    page.get_by_role("button", name="Start").click()


def answer(page: Page, label: str) -> None:
    page.wait_for_timeout(800)
    page.get_by_role("button", name=label, exact=False).first.click()
    page.wait_for_timeout(900)


def test_each_answered_question_has_a_change_button(page, static_site, backend) -> None:
    begin(page, static_site, backend, [WHICH_BUS, WHICH_SEAT])
    page.wait_for_selector("text=Which bus would you like?")
    answer(page, "8:30 am")
    page.wait_for_selector("text=Which seat would you like?")
    chips = page.locator("[data-testid=so-far] [data-testid=chip]")
    assert chips.count() == 1
    assert chips.first.locator("[data-testid=chip-change]").count() == 1
    assert page.get_by_role("button", name=BUS_CHANGE).count() == 1


def test_change_starts_again_keeping_the_other_answers_and_asks_that_one_again(
        page, static_site, backend) -> None:
    begin(page, static_site, backend, [WHICH_BUS, WHICH_SEAT, PASSWORD])
    page.wait_for_selector("text=Which bus would you like?")
    answer(page, "8:30 am")
    page.wait_for_selector("text=Which seat would you like?")
    answer(page, "Seat 10")
    page.wait_for_selector("text=Choose a password.")

    # Change the bus: the seat answer is kept, the bus is asked again.
    page.get_by_role("button", name=BUS_CHANGE).click()
    page.wait_for_function("document.body.innerText.includes('Which bus would you like?')",
                           timeout=8000)
    assert len(backend.starts) == 2
    again = backend.starts[1]
    assert again["goal"] == GOAL
    assert again["keep_answers"] == [
        {"question": "Which seat would you like?", "action_label": "Seat 10 · Aisle",
         "input_values": {}}]
    # The kept answer is still on the left, the changed one is not.
    chips = page.locator("[data-testid=so-far] [data-testid=chip]").all_inner_texts()
    assert any("Seat 10" in chip for chip in chips)
    assert not any("8:30" in chip for chip in chips)


def test_a_secret_is_never_kept(page, static_site, backend) -> None:
    begin(page, static_site, backend, [WHICH_BUS, PASSWORD, WHICH_SEAT])
    page.wait_for_selector("text=Which bus would you like?")
    answer(page, "8:30 am")
    page.wait_for_selector("text=Choose a password.")
    page.wait_for_timeout(800)
    page.get_by_label("Password").fill("Hunter2-secret")
    page.get_by_role("button", name="Next").click()
    page.wait_for_selector("text=Which seat would you like?")
    page.wait_for_timeout(800)
    page.get_by_role("button", name=BUS_CHANGE).click()
    page.wait_for_function("document.body.innerText.includes('Which bus would you like?')",
                           timeout=8000)
    sent = json.dumps(backend.starts)
    assert "Hunter2-secret" not in sent
    assert "Choose a password" not in sent


def test_no_change_after_do_it(page, static_site, backend) -> None:
    begin(page, static_site, backend, [WHICH_BUS, FINAL, WHICH_SEAT])
    page.wait_for_selector("text=Which bus would you like?")
    answer(page, "8:30 am")
    page.wait_for_selector("[data-testid=final-check]")
    page.wait_for_timeout(800)
    # Before Do it, nothing has been done on the website: Change is there.
    assert page.locator("[data-testid=chip-change]").count() == 1
    page.get_by_role("button", name="Book it").click()
    page.wait_for_timeout(1200)
    assert page.locator("[data-testid=chip-change]").count() == 0
