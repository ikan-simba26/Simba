"""Channel B, measured off the rendered overlay rather than off the code.

`telemetry` has been in CONTRACT.md since 2026-09-04 with nothing sending it.
These drive the built overlay in a browser, with a socket on the other end
recording what arrives, and assert that the five numbers turn up, that they
move with what the person does, and that they arrive both on the answer and on
the timer while a step waits.

Built from source, like `test_terminal_states.py`, so a stale `dist/` cannot
pass it.
"""

import asyncio
import functools
import http.server
import json
import os
import shutil
import socketserver
import subprocess
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import websockets
from playwright.sync_api import Page, Playwright

FRONTEND = Path(__file__).resolve().parent
BUILD = FRONTEND.parent / ".scratch" / "overlay-telemetry"

GOAL = "Find out what I owe"
GO_AHEAD = "Check the bill"
#: `SAMPLE_EVERY_MS` in `src/telemetry.ts`. Kept here as a number so the test
#: fails loudly if the two drift apart rather than hanging.
SAMPLE_EVERY_MS = 3000

A_STEP = {
    "step_index": 1, "step_total": 3,
    "instruction": "Let me look up your bill.", "detail": "On the billing site.",
    "fields": [], "requires_confirmation": True, "findings": [],
    "actions": [
        {"id": "confirm", "label": GO_AHEAD, "kind": "primary"},
        {"id": "cancel", "label": "Stop this", "kind": "secondary"},
    ],
}

#: A 1x1 transparent PNG. The panel wants a picture, not a good one.
PIXEL = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
         "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")

SCRIPT = [
    ("task.started", {"goal": GOAL, "estimated_steps": 3}),
    ("state.changed", {"state": "waiting"}),
    ("step.presented", A_STEP),
]


# --- the overlay, built from the source as it is now -------------------------


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
        # Presses count at once in these tests: the guard that ignores a press
        # on a button that has just arrived (2026-10-16) is tested on its own
        # (`test_press_guard.py`), which turns it back on.
        env={**os.environ, "VITE_SIMBA_SETTLE_MS": "0",
             # Straight to the home screen: the welcome (2026-10-18) has its
             # own tests, which turn it back on.
             "VITE_SIMBA_WELCOME": "0"},
    )
    assert built.returncode == 0 and (BUILD / "index.html").exists(), built.stderr

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(BUILD))
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/index.html"
    finally:
        server.shutdown()
        server.server_close()


class Backend:
    """Presents one step and records everything the overlay says back."""

    def __init__(self) -> None:
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
                    await ws.send(json.dumps({
                        "v": 1, "type": message_type, "task_id": "t_telemetry",
                        "seq": seq, "ts": 0, "payload": payload,
                    }))

                await send("history.offered", {"goals": []})
                try:
                    await ws.recv()  # task.start
                except websockets.ConnectionClosed:
                    return
                for message_type, payload in SCRIPT:
                    await send(message_type, payload)
                # Then listen: telemetry, the response, whatever comes — and
                # answer `trust.requested` the way the backend does, because
                # the panel shows nothing to press until its picture lands.
                try:
                    while True:
                        message = json.loads(await ws.recv())
                        self.received.append(message)
                        if message.get("type") == "trust.requested":
                            await send("page.preview", {
                                "screenshot": PIXEL,
                                "highlight": {"x": 0, "y": 0, "w": 0, "h": 0},
                                "caption": "Looking at the bill.",
                            })
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

    def of(self, message_type: str) -> list[dict]:
        return [m["payload"] for m in self.received if m.get("type") == message_type]

    def types(self) -> list[str]:
        return [m.get("type") for m in self.received]


@pytest.fixture(scope="module")
def backend() -> Backend:
    return Backend()


@pytest.fixture(scope="module")
def page(playwright_instance: Playwright) -> Iterator[Page]:
    browser = playwright_instance.chromium.launch()
    # The frozen viewport (CLAUDE.md).
    yield browser.new_page(viewport={"width": 1280, "height": 800})
    browser.close()


def open_step(page: Page, overlay: str, backend: Backend) -> None:
    """Start a task and wait for the step to be on screen, and settled.

    The settle is not padding: the home screen and the step share a grid cell
    and cross-fade, so for the length of that fade the outgoing screen is
    still over the incoming one's controls and a click lands on nothing.
    """
    backend.received.clear()
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    page.fill("input[aria-label='What would you like me to do?']", GOAL)
    page.get_by_role("button", name="Start").click()
    page.wait_for_selector("[data-testid=step-shell]", timeout=15000)
    page.wait_for_timeout(700)


def wander(page: Page, points: list[tuple[int, int]]) -> None:
    """Move the pointer through these, in small steps, like a hand would."""
    for x, y in points:
        page.mouse.move(x, y, steps=12)
        page.wait_for_timeout(60)


# --- what arrives ------------------------------------------------------------


def test_the_answer_carries_a_sample_with_it(
    page: Page, overlay: str, backend: Backend
) -> None:
    """Every step response, per CONTRACT.md. And before the response, so the
    backend has it in hand when it pairs the step with its page."""
    open_step(page, overlay, backend)
    page.wait_for_timeout(800)
    page.get_by_role("button", name=GO_AHEAD, exact=True).click()
    page.wait_for_timeout(600)

    assert "telemetry" in backend.types(), backend.types()
    assert backend.types().index("telemetry") < backend.types().index("step.response")

    sample = backend.of("telemetry")[-1]
    assert sample["step_index"] == 1
    assert sample["answered"] is True
    assert sample["hesitation_ms"] >= 800
    assert sample["cursor_path_ratio"] >= 1.0
    assert set(sample) >= {"step_index", "hesitation_ms", "cursor_path_ratio",
                           "backtracks", "rereads", "help_presses"}


def test_a_wandering_pointer_reads_as_wandering(
    page: Page, overlay: str, backend: Backend
) -> None:
    """The ratio is path length over straight-line distance: 1.0 is a direct
    move. A zigzag that ends where it started is a long path over a short
    line, and reads as one."""
    open_step(page, overlay, backend)
    wander(page, [(200, 200), (1000, 600), (200, 600), (1000, 200), (240, 220)])
    page.get_by_role("button", name=GO_AHEAD, exact=True).click()
    page.wait_for_timeout(600)

    sample = backend.of("telemetry")[-1]
    assert sample["cursor_path_ratio"] > 2.0, sample
    assert sample["backtracks"] >= 1, sample


def test_a_straight_move_does_not(page: Page, overlay: str, backend: Backend) -> None:
    """The control for the test above: one straight line to the button.

    Straight *to the thing being pressed*, which is what the ratio measures —
    an L-shaped path that ends at the button is not a direct move and should
    not read as one. Measured: the same journey in two legs reads 28.5.
    """
    open_step(page, overlay, backend)
    button = page.get_by_role("button", name=GO_AHEAD, exact=True)
    box = button.bounding_box()
    assert box is not None
    page.mouse.move(200, 180)
    page.wait_for_timeout(80)
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=20)
    page.wait_for_timeout(80)
    button.click()
    page.wait_for_timeout(600)

    sample = backend.of("telemetry")[-1]
    assert 1.0 <= sample["cursor_path_ratio"] < 1.3, sample
    assert sample["backtracks"] == 0, sample


def test_asking_what_is_happening_is_counted(
    page: Page, overlay: str, backend: Backend
) -> None:
    """The loudest signal channel B has: they stopped and asked."""
    open_step(page, overlay, backend)
    page.get_by_role("button", name="What are you doing?", exact=True).click()
    page.wait_for_timeout(500)
    # Out the way the panel offers, not with Escape: the panel is a fixed
    # sheet over the whole screen and nothing dismisses it from outside —
    # deliberately, because the way out lives inside it (`TrustPanel.tsx`).
    page.get_by_role("button", name="Hide the page", exact=True).click()
    page.wait_for_timeout(500)
    page.get_by_role("button", name=GO_AHEAD, exact=True).click()
    page.wait_for_timeout(600)

    assert backend.of("telemetry")[-1]["help_presses"] == 1


def test_a_step_left_alone_still_reports(
    page: Page, overlay: str, backend: Backend
) -> None:
    """On a timer while waiting, per CONTRACT.md — and the samples grow, which
    is the point: hesitation that keeps climbing is the signal, not its final
    value."""
    open_step(page, overlay, backend)
    started = time.monotonic()
    page.wait_for_timeout(int(SAMPLE_EVERY_MS * 2.4))

    samples = backend.of("telemetry")
    assert len(samples) >= 2, f"{len(samples)} samples in {time.monotonic() - started:.1f}s"
    assert all(not sample.get("answered") for sample in samples), samples
    assert samples[-1]["hesitation_ms"] > samples[0]["hesitation_ms"]
    assert all(sample["step_index"] == 1 for sample in samples)


def test_nothing_is_sent_when_no_step_is_waiting(
    page: Page, overlay: str, backend: Backend
) -> None:
    """A screen with no decision on it has nothing to measure, and an answered
    step is reported once by the answer rather than repeatedly by the timer."""
    open_step(page, overlay, backend)
    page.get_by_role("button", name=GO_AHEAD, exact=True).click()
    page.wait_for_timeout(int(SAMPLE_EVERY_MS * 1.6))

    assert len(backend.of("telemetry")) == 1, backend.of("telemetry")
