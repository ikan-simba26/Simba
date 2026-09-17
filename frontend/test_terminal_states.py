"""Every way a task can end leaves the person something to press.

A task ends in one of four screens: finished with an answer, finished without
one, failed, or stuck. Until 2026-09-17 the stuck screen had nothing on it to
press. `STOPPED.again` was in `copy.ts` and no component rendered it, so the
one moment the system said it needed the person was the one moment it gave
them nowhere to go — and the backend closes the socket after
`help.requested`, so there was nothing to wait for either.

That defect lived in the gap between a declaration and a rendered screen,
which is exactly where a test of the declaration cannot look (DECISIONS.md,
"measure the rendered result, not the declared intent"). So this renders each
ending in a real browser, from the current source, and asserts:

  * there is at least one enabled button on it;
  * every one of them leads somewhere — pressing it leaves the ending for the
    home screen, rather than being a button that does nothing;
  * nothing on it is a web address.

**Built from source, not from `dist/`.** `test_levels.py` measures whatever
`dist/` holds and skips without it, which means a stale build is tested
rather than the code (STATUS.md, Infrastructure). This builds the overlay
into `.scratch/overlay-terminal/` first, the same way `test_copy.py` compiles
`copy.ts` into `.scratch/`, so it always tests what is checked out.
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
BUILD = FRONTEND.parent / ".scratch" / "overlay-terminal"

GOAL = "Find out what I owe"
GREETING = "Hello. What can I do for you?"


def ending(*messages: tuple[str, dict]) -> list[tuple[str, dict]]:
    """A task that starts, and then ends with these messages."""
    return [
        ("task.started", {"goal": GOAL, "estimated_steps": 3}),
        ("state.changed", {"state": "thinking"}),
        *messages,
    ]


ENDINGS: dict[str, list[tuple[str, dict]]] = {
    "completed with an answer": ending(
        ("task.completed", {
            "summary": f"{GOAL} http://127.0.0.1:5100/bill/detail", "duration_ms": 1,
            "steps_taken": 3, "llm_calls": 0, "replayed": False,
            "findings": [{"label": "Your bill", "value": "14,382"},
                         {"label": "Due", "value": "15-09-2026"}],
        }),
    ),
    # The backend's summary really is the goal and then the final URL. It was
    # rendered here in 26px type until 2026-09-17.
    "completed without an answer": ending(
        ("task.completed", {
            "summary": f"{GOAL} http://127.0.0.1:5000/register", "duration_ms": 1,
            "steps_taken": 3, "llm_calls": 0, "replayed": False, "findings": [],
        }),
    ),
    "failed": ending(
        ("task.failed", {"reason": "You asked me to stop.", "recoverable": True}),
    ),
    "stuck": ending(
        ("state.changed", {"state": "stuck"}),
        ("help.requested", {
            "reason": "could not find 'Close' on the page",
            "suggestion": "I won't do any more on this. You can ask me for something else.",
        }),
    ),
}


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
    """Plays whichever ending is current, then closes the socket like the real
    backend does once a task is over."""

    def __init__(self) -> None:
        self.script: list[tuple[str, dict]] = []
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
                        "v": 1, "type": message_type, "task_id": "t_terminal",
                        "seq": seq, "ts": 0, "payload": payload,
                    }))

                await send("history.offered", {"goals": []})
                try:
                    await ws.recv()  # task.start
                except websockets.ConnectionClosed:
                    return
                for message_type, payload in self.script:
                    await send(message_type, payload)
                await ws.close()

            async def main() -> None:
                server = await websockets.serve(handler, "127.0.0.1", 0)
                self.port = server.sockets[0].getsockname()[1]
                started.set()
                await asyncio.Future()

            loop.run_until_complete(main())

        threading.Thread(target=run, daemon=True).start()
        started.wait(timeout=10)


@pytest.fixture(scope="module")
def backend() -> Backend:
    return Backend()


@pytest.fixture(scope="module")
def page(playwright_instance: Playwright) -> Iterator[Page]:
    browser = playwright_instance.chromium.launch()
    # The frozen viewport (CLAUDE.md).
    yield browser.new_page(viewport={"width": 1280, "height": 800})
    browser.close()


def reach(page: Page, overlay: str, backend: Backend, name: str) -> list[str]:
    """Drive the overlay to this ending. Returns the labels of its buttons."""
    backend.script = ENDINGS[name]
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    page.fill("input[aria-label='What would you like me to do?']", GOAL)
    page.get_by_role("button", name="Start").click()
    # Let the last message land and the crossfade finish.
    page.wait_for_function(
        "() => !document.body.innerText.includes('Give me a moment.')", timeout=15000
    )
    page.wait_for_timeout(600)
    return page.eval_on_selector_all(
        "button:not([disabled])",
        "buttons => buttons.filter(b => b.offsetParent !== null).map(b => b.innerText.trim())",
    )


@pytest.mark.parametrize("name", list(ENDINGS))
def test_every_ending_has_something_to_press(
    name: str, page: Page, overlay: str, backend: Backend
) -> None:
    labels = reach(page, overlay, backend, name)
    assert [label for label in labels if label], f"{name}: nothing to press"


@pytest.mark.parametrize("name", list(ENDINGS))
def test_everything_on_an_ending_leads_somewhere(
    name: str, page: Page, overlay: str, backend: Backend
) -> None:
    """A button that does nothing is not a way onward."""
    for label in [label for label in reach(page, overlay, backend, name) if label]:
        reach(page, overlay, backend, name)
        page.get_by_role("button", name=label, exact=True).click()
        page.wait_for_function(
            f"() => document.body.innerText.includes({json.dumps(GREETING)})", timeout=5000
        )


@pytest.mark.parametrize("name", list(ENDINGS))
def test_no_ending_shows_a_web_address(
    name: str, page: Page, overlay: str, backend: Backend
) -> None:
    reach(page, overlay, backend, name)
    text = page.inner_text("body")
    assert "http" not in text, text


def test_the_stuck_screen_says_what_happens_and_offers_a_way_on(
    page: Page, overlay: str, backend: Backend
) -> None:
    """The screen the defect was on, stated directly.

    And it no longer promises what nothing does: the run is over and the page
    is covered, so there is nothing for the person to do on it and nothing
    that will carry on afterwards.
    """
    labels = reach(page, overlay, backend, "stuck")
    text = page.inner_text("body")
    assert "I'm stuck, so I've stopped." in text
    assert "I won't do any more on this. You can ask me for something else." in text
    for promise in ("carry on", "Can you", "help with"):
        assert promise not in text, promise
    assert "Do something else" in labels
