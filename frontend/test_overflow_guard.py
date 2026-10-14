"""The overflow guard says what it did, and never becomes the lock.

When a step will not fit the window, the overlay drops a level towards level 1,
the compact one (`useOverflowGuard.ts`). Until 2026-09-25 it did that
silently: the backend's level rules thought the screen was at one level while
it showed another, and under a lock the guard's level became the locked level
and was carried into the next task as if the person had chosen it.

Driven in a real browser against the overlay built from source, in a window
606px tall — a 1080p laptop at 150% — with a scripted backend that records
everything the overlay says:

  * a guard move goes out as `level.override {by: "overflow"}`;
  * under a lock it goes out with the lock still on, and the next step is
    shown at the person's level again;
  * a lock carried into a new task is the person's level, not the guard's.
"""

import asyncio
import functools
import http.server
import json
import shutil
import socketserver
import subprocess
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
import websockets
from playwright.sync_api import Page, Playwright

FRONTEND = Path(__file__).resolve().parent
BUILD = FRONTEND.parent / ".scratch" / "overlay-guard"
#: A 1920x1080 laptop at 150%, taskbar excluded: what the window gets.
SHORT = {"width": 1266, "height": 606}
LEVEL_LABELS = {1: "Show more", 2: "Show the usual amount", 3: "Show less"}


def step(index: int, *, tall: bool) -> dict:
    """A step. A tall one has three fields and cannot fit 606px at level 2."""
    fields = [
        {"id": f"f{n}", "label": label, "type": "text", "value": ""}
        for n, label in enumerate(["Student ID or Username", "Password", "Course code"])
    ] if tall else []
    return {
        "step_index": index, "step_total": 3,
        "instruction": ("Let me sign you in, then find the course and hold a place "
                        "for you while you decide." if tall else f"Step {index}, short."),
        "detail": "Fictional State University student portal.",
        "fields": fields, "requires_confirmation": True, "findings": [],
        "actions": [
            {"id": "confirm", "label": f"Go ahead {index}", "kind": "primary"},
            {"id": "cancel", "label": "Stop this", "kind": "secondary"},
        ],
    }


@pytest.fixture(scope="module")
def overlay() -> Iterator[str]:
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if npx is None:
        pytest.skip("npx not on PATH")
    if not (FRONTEND / "node_modules").exists():
        pytest.skip("frontend dependencies not installed; run npm install in frontend/")
    if BUILD.exists():
        shutil.rmtree(BUILD)
    built = subprocess.run(
        [npx, "vite", "build", "--outDir", str(BUILD), "--emptyOutDir", "--logLevel", "error"],
        cwd=FRONTEND, capture_output=True, text=True, timeout=300,
    )
    assert built.returncode == 0 and (BUILD / "index.html").exists(), built.stderr

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(BUILD))
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/index.html"
    finally:
        server.shutdown()
        server.server_close()


class Backend:
    """Plays `steps` in order, one per answer, then completes; records all."""

    def __init__(self, steps: list[dict]) -> None:
        self.steps = steps
        self.received: list[dict] = []
        self.port = 0
        started = threading.Event()

        def run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def handler(ws):
                seq = 0

                async def send(message_type: str, payload: dict) -> None:
                    nonlocal seq
                    seq += 1
                    await ws.send(json.dumps({"v": 1, "type": message_type, "task_id": "t",
                                              "seq": seq, "ts": 0, "payload": payload}))

                await send("history.offered", {"goals": []})
                try:
                    # Everything up to and including the task.start.
                    while True:
                        message = json.loads(await ws.recv())
                        self.received.append(message)
                        if message.get("type") == "task.start":
                            break
                    await send("task.started", {"goal": "g", "estimated_steps": 3})
                    await send("state.changed", {"state": "waiting"})
                    for payload in self.steps:
                        await send("step.presented", payload)
                        while True:
                            message = json.loads(await ws.recv())
                            self.received.append(message)
                            if message.get("type") == "step.response":
                                break
                    await send("task.completed", {
                        "summary": "done", "duration_ms": 1, "steps_taken": len(self.steps),
                        "llm_calls": 0, "replayed": False, "findings": []})
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

    def overrides(self) -> list[dict]:
        return [m["payload"] for m in self.received if m.get("type") == "level.override"]


@pytest.fixture
def page(playwright_instance: Playwright) -> Iterator[Page]:
    browser = playwright_instance.chromium.launch()
    yield browser.new_page(viewport=SHORT)
    browser.close()


def start(page: Page, overlay: str, backend: Backend) -> None:
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    page.fill("input[aria-label='What would you like me to do?']", "Register me")
    page.get_by_role("button", name="Start").click()
    page.wait_for_selector("[data-testid=step-shell]", timeout=15000)


def level_on_screen(page: Page) -> int:
    label = page.locator('button[aria-pressed="true"]').first.get_attribute("aria-label")
    return next(level for level, name in LEVEL_LABELS.items() if name == label)


def answer(page: Page, index: int) -> None:
    # The guard measures 480ms after a level settles; give it that and more.
    page.wait_for_timeout(1200)
    page.get_by_role("button", name=f"Go ahead {index}", exact=True).click()
    page.wait_for_timeout(900)


def test_a_guard_move_is_told_to_the_backend(page: Page, overlay: str) -> None:
    backend = Backend([step(1, tall=True)])
    start(page, overlay, backend)
    page.wait_for_timeout(1500)

    assert level_on_screen(page) == 1
    assert {"level": 1, "locked": False, "by": "overflow"} in backend.overrides(), \
        backend.overrides()


def test_under_a_lock_a_guard_move_lasts_one_step(page: Page, overlay: str) -> None:
    backend = Backend([step(1, tall=False), step(2, tall=True), step(3, tall=False)])
    start(page, overlay, backend)
    page.wait_for_timeout(800)
    page.get_by_role("button", name=LEVEL_LABELS[2]).click()      # the person locks at 2
    answer(page, 1)

    page.wait_for_selector("text=Go ahead 2")
    page.wait_for_timeout(1500)
    assert level_on_screen(page) == 1                              # the guard, for this step
    guard = [o for o in backend.overrides() if o.get("by") == "overflow"]
    assert guard == [{"level": 1, "locked": True, "by": "overflow"}], backend.overrides()
    answer(page, 2)

    page.wait_for_selector("text=Go ahead 3")
    page.wait_for_timeout(800)
    assert level_on_screen(page) == 2                              # the person's, again


def test_a_lock_carried_into_a_new_task_is_the_persons_level(
    page: Page, overlay: str
) -> None:
    backend = Backend([step(1, tall=False), step(2, tall=True)])
    start(page, overlay, backend)
    page.wait_for_timeout(800)
    page.get_by_role("button", name=LEVEL_LABELS[2]).click()
    answer(page, 1)
    page.wait_for_selector("text=Go ahead 2")
    answer(page, 2)                                                # answered at the guard's 1

    page.get_by_role("button", name="Do something else").click()
    backend.received.clear()
    page.fill("input[aria-label='What would you like me to do?']", "Again")
    page.get_by_role("button", name="Start").click()
    page.wait_for_timeout(1500)

    types = [m.get("type") for m in backend.received]
    before = backend.received[: types.index("task.start")]
    resent = [m["payload"] for m in before if m.get("type") == "level.override"]
    assert resent == [{"level": 2, "locked": True, "by": "person"}], backend.received


def test_a_step_packed_to_fit_says_it_was_made_smaller(page: Page, overlay: str) -> None:
    """Not "I'm showing a bit more again." (until 2026-10-14), which is what
    the level rules say when they give detail back — and which greeted the
    first question of every task in the real window at 150%."""
    backend = Backend([step(1, tall=True)])
    start(page, overlay, backend)
    page.wait_for_timeout(1500)

    assert level_on_screen(page) == 1
    body = page.inner_text("body")
    assert "I've made this a little smaller so it all fits on the screen." in body
    assert "again" not in body
