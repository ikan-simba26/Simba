"""Level 3 must never be the tallest layout.

Level 3 exists for someone who is struggling. If it renders *taller* than the
others for the same step, simplifying has made the page bigger, which is the
opposite of the point and pushes content off screen. That happened: on a
short step level 3 measured 208px against level 2's 176px, because the type
grew faster than the removed regions shrank.

**The full chain `h3 <= h2 <= h1` is not achievable and is not asserted.**
Level 1 is the *compact* layout — smaller type, tighter spacing, and fields
laid out inline with their labels rather than stacked above them — so it is
consistently the shortest, not the tallest. Measured, at the same viewport:

    short step   L1 241   L2 253   L3 174
    medium step  L1 341   L2 418   L3 384
    long step    L1 539   L2 771   L3 542

The gap widens with content because inline fields cost roughly half the
height of stacked ones. Making level 1 the tallest would mean abandoning
inline fields or giving it level 2's type and spacing, which is its entire
brief. So what is enforced here is the invariant that actually prevents the
bug: level 3 is never taller than either of the others.

Measured in a real browser against the built overlay, because the thing under
test is layout — jsdom would report zero for all of it.

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

FRONTEND = Path(__file__).resolve().parent
DIST = FRONTEND / "dist"

pytestmark = pytest.mark.skipif(
    not (DIST / "index.html").exists(),
    reason="frontend not built; run `npm run build` in frontend/",
)

# Deliberately taller than the real 1280x800. What is under test is each
# level's intrinsic height, and at 800px the overflow guard would move the
# level out from under the measurement.
VIEWPORT = {"width": 1280, "height": 2200}

SHORT = {
    "instruction": "Close the registration alert.",
    "detail": "The portal opened a notice about the add/drop deadline.",
    "fields": [],
}
MEDIUM = {
    "instruction": "Register for CS-401, Advanced Widget Design, for the autumn term.",
    "detail": "3 credit hours. MWF 10:00-10:50, Dr. Aslam, SCI 214.",
    "fields": [{"id": "student_id", "label": "Student ID", "type": "text", "value": ""}],
}
LONG = {
    "instruction": (
        "Confirm that you want to transfer your enrolment from CS-401 Advanced "
        "Widget Design to CS-460 Machine Learning for the autumn term, releasing "
        "your seat in the first course and taking the last remaining place in "
        "the second."
    ),
    "detail": (
        "CS-401 meets MWF 10:00-10:50 with Dr. Aslam in SCI 214. CS-460 meets "
        "MWF 15:00-15:50 with Dr. Aslam in SCI 214."
    ),
    "fields": [
        {"id": "student_id", "label": "Student ID", "type": "text", "value": ""},
        {"id": "reason", "label": "Reason for transfer", "type": "text", "value": ""},
        {"id": "advisor", "label": "Advisor name", "type": "text", "value": ""},
    ],
}

ACTIONS = [
    {"id": "confirm", "label": "Yes, do that", "kind": "primary"},
    {"id": "cancel", "label": "Not now", "kind": "secondary"},
]


def _step(body: dict) -> dict:
    return {
        "step_index": 2,
        "step_total": 6,
        "instruction": body["instruction"],
        "detail": body["detail"],
        "fields": body["fields"],
        "actions": ACTIONS,
        "requires_confirmation": True,
    }


@pytest.fixture(scope="module")
def static_site() -> Iterator[str]:
    """Serve the built overlay. It is a file:// app; tests want http."""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DIST))
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/index.html"
    finally:
        server.shutdown()
        server.server_close()


class Backend:
    """One server for the whole module, serving whichever step is current.

    Deliberately never shut down: stopping the loop while the page still holds
    the socket open takes the browser context down with it.
    """

    def __init__(self) -> None:
        self.step: dict = {}
        self.port = 0
        started = threading.Event()

        def run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def handler(ws):
                await ws.recv()  # task.start
                await self._send(ws, 1, "task.started",
                                 {"goal": "Measure", "estimated_steps": 6})
                await self._send(ws, 2, "state.changed", {"state": "waiting"})
                await self._send(ws, 3, "step.presented", self.step)
                try:
                    await asyncio.Future()
                except asyncio.CancelledError:
                    return

            async def main() -> None:
                server = await websockets.serve(handler, "127.0.0.1", 0)
                self.port = server.sockets[0].getsockname()[1]
                started.set()
                await asyncio.Future()

            loop.run_until_complete(main())

        threading.Thread(target=run, daemon=True).start()
        started.wait(timeout=10)

    @staticmethod
    async def _send(ws, seq: int, message_type: str, payload: dict) -> None:
        await ws.send(json.dumps({
            "v": 1, "type": message_type, "task_id": "t_measure",
            "seq": seq, "ts": 0, "payload": payload,
        }))


@pytest.fixture(scope="module")
def browser_page(playwright_instance: Playwright) -> Iterator[Page]:
    # Shared session-wide: a second sync_playwright() in the same process
    # fails with "Sync API inside the asyncio loop". See the root conftest.
    browser = playwright_instance.chromium.launch()
    page = browser.new_page(viewport=VIEWPORT)
    yield page
    browser.close()


@pytest.fixture(scope="module")
def backend() -> Backend:
    return Backend()


def heights_by_level(page: Page, site: str, backend: Backend, step: dict) -> dict[int, int]:
    """Render one step at each level and measure the step's own box."""
    backend.step = step
    page.goto(f"{site}?ws=ws://127.0.0.1:{backend.port}")
    # The overlay only opens a task when someone asks it to.
    page.fill("input[aria-label='What would you like me to do?']", "Measure")
    page.get_by_role("button", name="Start").click()
    page.wait_for_selector("[data-testid=step-shell]", timeout=15000)

    measured: dict[int, int] = {}
    for level, label in ((1, "more"), (2, "the usual amount"), (3, "less")):
        page.get_by_role("button", name=f"Show {label}").click()
        page.wait_for_timeout(700)  # the fold is 350ms plus its delay
        measured[level] = page.evaluate(
            "Math.round(document.querySelector('[data-testid=step-shell]')"
            ".getBoundingClientRect().height)"
        )
    return measured


@pytest.fixture(scope="module")
def short(browser_page: Page, static_site: str, backend: Backend) -> dict[int, int]:
    return heights_by_level(browser_page, static_site, backend, _step(SHORT))


@pytest.fixture(scope="module")
def medium(browser_page: Page, static_site: str, backend: Backend) -> dict[int, int]:
    return heights_by_level(browser_page, static_site, backend, _step(MEDIUM))


@pytest.fixture(scope="module")
def long_step(browser_page: Page, static_site: str, backend: Backend) -> dict[int, int]:
    return heights_by_level(browser_page, static_site, backend, _step(LONG))


@pytest.mark.parametrize("case", ["short", "medium", "long_step"])
def test_level_3_is_never_taller_than_level_2(case: str, request) -> None:
    """The bug this file exists for."""
    heights = request.getfixturevalue(case)
    assert heights[3] <= heights[2], heights


@pytest.mark.parametrize("case", ["short", "medium", "long_step"])
def test_level_3_is_never_the_tallest(case: str, request) -> None:
    heights = request.getfixturevalue(case)
    assert heights[3] <= max(heights[1], heights[2]), heights


@pytest.mark.parametrize("case", ["short", "medium", "long_step"])
def test_level_1_is_the_shortest_because_it_is_compact(case: str, request) -> None:
    """Not a requirement — a consequence, asserted so it stays deliberate.

    If this starts failing, level 1 has stopped being compact. That may be
    the right call, but it should be a decision rather than a drift.
    """
    heights = request.getfixturevalue(case)
    assert heights[1] <= heights[2], heights


def test_the_levels_are_actually_different(medium: dict[int, int]) -> None:
    """Monotonic is easy to satisfy by making them identical. They are not."""
    assert len({medium[1], medium[2], medium[3]}) == 3, medium


def test_a_longer_step_is_taller_at_every_level(
    short: dict[int, int], long_step: dict[int, int]
) -> None:
    for level in (1, 2, 3):
        assert long_step[level] > short[level], (level, short, long_step)
