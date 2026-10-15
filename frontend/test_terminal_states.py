"""Every way a task can end leaves the person something to press.

A task ends in one of five screens: finished with an answer, finished
without one, failed, stuck, or stopped because the person pressed stop. Until 2026-09-17 the stuck screen had nothing on it to
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
  * nothing on it is a web address;
  * at the window's size at 100%, 125% and 150%, every button on it is wholly
    on screen and nothing scrolls. Until 2026-10-05 the fit was measured for
    the home screen and for steps only, and the closing screen had put its way
    onward below the window, with three results or more, at every scale.

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
GREETING = "What can I do for you?"

# In a script, wait here for the overlay's `step.response` before going on.
AWAIT_RESPONSE = "(await step.response)"

# Which button the person presses on the step, for an ending that has one.
PRESSES = {"stopped by the person": "Stop this"}
GO_AHEAD = "Check the bill"

A_STEP = {
    "step_index": 1, "step_total": 3,
    "instruction": "Let me look up your bill.", "detail": "",
    "fields": [], "requires_confirmation": True, "findings": [],
    "actions": [
        {"id": "confirm", "label": "Check the bill", "kind": "primary"},
        {"id": "cancel", "label": "Stop this", "kind": "secondary"},
    ],
}


def ending(*messages: tuple[str, dict]) -> list[tuple[str, dict]]:
    """A task that starts, and then ends with these messages."""
    return [
        ("task.started", {"goal": GOAL, "estimated_steps": 3}),
        ("state.changed", {"state": "thinking"}),
        *messages,
    ]


# A picture of the real page with what was read ringed (2026-10-16): the
# smallest real PNG, which the panel scales to the page's shape.
PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
PROOF = {"screenshot": PNG, "caption": "What I read is ringed.",
         "rings": [{"x": 728, "y": 143, "w": 118, "h": 17}]}

HELP = ("help.requested", {
    "reason": "could not find 'Check Bill' on the page",
    "suggestion": "I won't do any more on this. You can ask me for something else.",
})

# How each ending ends: the messages after the task is under way.
TAILS: dict[str, list[tuple[str, dict]]] = {
    "completed with an answer": [
        ("task.completed", {
            "summary": f"{GOAL} http://127.0.0.1:5100/bill/detail", "duration_ms": 1,
            "steps_taken": 3, "llm_calls": 0, "replayed": False,
            "findings": [{"label": "Your bill", "value": "14,382"},
                         {"label": "Due", "value": "15-09-2026"}],
            # What was not done, the last line, and the answer on the real
            # page (2026-10-16).
            "scope": "I only looked at your bill. I did not pay it.",
            "proof": PROOF,
        }),
    ],
    # A search that returned several results. The closing screen is the
    # answer, so it shows all of them; `value` is the one-line form the step
    # screen shows while the run is still going, and it stops at four.
    "completed with several results": [
        ("task.completed", {
            "summary": f"{GOAL} http://127.0.0.1:5100/results", "duration_ms": 1,
            "steps_taken": 3, "llm_calls": 0, "replayed": False,
            "findings": [
                {"label": "Train", "value": "39UP, 1UP, 7UP, 27UP and 1 more",
                 "values": ["39UP", "1UP", "7UP", "27UP", "101UP"]},
                {"label": "Journey", "value": "6 h 38 min, 6 h 3 min",
                 "values": ["6 h 38 min", "6 h 3 min"]},
            ],
        }),
    ],
    # The tallest closing screen a real search has produced: nine trains, each
    # with a journey time, and the sentence above them (EVALUATION.md,
    # 2026-09-30 and 2026-10-03c). Here so the fit is checked on it too.
    "completed with nine results and a sentence": [
        ("task.completed", {
            "summary": f"{GOAL} http://127.0.0.1:5200/results", "duration_ms": 1,
            "steps_taken": 3, "llm_calls": 0, "replayed": False,
            "explanation": "There are 9 trains. The fastest takes 4 hours 15 minutes.",
            "scope": "I only looked up times. I did not book a ticket or pay for anything.",
            "proof": PROOF,
            "findings": [
                {"label": "Train", "value": "105UP, 101UP, 13UP, 39UP and 5 more",
                 "values": ["105UP", "101UP", "13UP", "39UP", "7UP", "5UP", "103UP",
                            "107UP", "1UP"]},
                {"label": "Journey",
                 "value": "4 h 30 min, 4 h 45 min, 5 h 20 min, 5 h 45 min and 5 more",
                 "values": ["4 h 30 min", "4 h 45 min", "5 h 20 min", "5 h 45 min",
                            "5 h 30 min", "4 h 25 min", "5 h 10 min", "4 h 15 min",
                            "5 h 15 min"]},
            ],
        }),
    ],
    # The same nine trains, two with the same journey time: perception keeps a
    # repeated value once, so eight times for nine trains, which cannot be put
    # beside them. Found by the fit check below on the day it was written:
    # both buttons were below a 606px window.
    "completed with nine results and a detail that does not line up": [
        ("task.completed", {
            "summary": f"{GOAL} http://127.0.0.1:5200/results", "duration_ms": 1,
            "steps_taken": 3, "llm_calls": 0, "replayed": False,
            "explanation": "There are 9 trains. The fastest takes 4 hours 15 minutes.",
            "scope": "I only looked up times. I did not book a ticket or pay for anything.",
            "proof": PROOF,
            "findings": [
                {"label": "Train", "value": "105UP, 101UP, 13UP, 39UP and 5 more",
                 "values": ["105UP", "101UP", "13UP", "39UP", "7UP", "5UP", "103UP",
                            "107UP", "1UP"]},
                {"label": "Journey",
                 "value": "4 h 30 min, 4 h 45 min, 5 h 20 min, 5 h 45 min and 4 more",
                 "values": ["4 h 30 min", "4 h 45 min", "5 h 20 min", "5 h 45 min",
                            "5 h 30 min", "4 h 25 min", "5 h 10 min", "4 h 15 min"]},
            ],
        }),
    ],
    # The backend's summary really is the goal and then the final URL. It was
    # rendered here in 26px type until 2026-09-17.
    "completed without an answer": [
        ("task.completed", {
            "summary": f"{GOAL} http://127.0.0.1:5000/register", "duration_ms": 1,
            "steps_taken": 3, "llm_calls": 0, "replayed": False, "findings": [],
            # What changed, the last line, and the portal's own word for it
            # (2026-10-16).
            "scope": "You are registered for CS-401 section 001.",
            "confirmation": ("The portal says “Registration Confirmed”, with "
                             "confirmation number REG-10234-2026."),
            "proof": PROOF,
        }),
    ],
    # A change tried and not confirmed (2026-10-16): never "done".
    "not confirmed": [
        ("state.changed", {"state": "stuck"}),
        ("help.requested", {
            "reason": ("I tried to press “Register for CS-401”, but the portal has "
                       "not confirmed it, so I can't tell you it worked. Please check the "
                       "portal before you rely on it."),
            "suggestion": "I won't do any more on this. You can ask me for something else.",
            "unconfirmed": True,
        }),
    ],
    # The backend ending a task on its own account. `loop.py` has no such path
    # today — its only `task.failed` is a stop — but the contract allows it.
    "failed": [
        ("task.failed", {"reason": "The portal timed out.", "recoverable": True}),
    ],
    # The order `loop.give_up` sends: the state first, then the request.
    "stuck": [("state.changed", {"state": "stuck"}), HELP],
    # The same ending with the request arriving alone. The contract does not
    # require the state change to come first, and this is the order that
    # matters: when `help.requested` is the message that switches the screen,
    # a step on its way out strands itself over the buttons unless
    # `App.Step` keeps rendering it. With the stuck state first the screen has
    # already switched while the step was still set, and nothing strands — which
    # is why the stuck ending looked protected when it was not. Measured
    # 2026-09-17 with the fix reverted: 3 of 3 blocked this way, 0 of 3 the
    # other.
    "stuck, asked for with no state change first": [HELP],
}

# Through a step: the way every real run reaches its ending. The person
# presses go-ahead on a step, the backend acts, then the ending arrives.
THROUGH_A_STEP = [
    ("state.changed", {"state": "waiting"}),
    ("step.presented", A_STEP),
    (AWAIT_RESPONSE, {}),
    ("state.changed", {"state": "acting"}),
]

ENDINGS: dict[str, list[tuple[str, dict]]] = {
    # From the working screen, before any step. Not how a real run ends, and
    # on their own these passed while every ending after a step was
    # unpressable (EVALUATION.md, 2026-09-17c). Kept because they are the
    # simplest case of each screen.
    **{name: ending(*tail) for name, tail in TAILS.items()},
    # Every ending again, reached through a step.
    **{f"{name}, after a step": ending(*THROUGH_A_STEP, *tail) for name, tail in TAILS.items()},
    # What the real backend does when the person presses stop: `task.failed`,
    # straight away, then the socket closes. Only exists after a step.
    "stopped by the person": ending(
        ("state.changed", {"state": "waiting"}),
        ("step.presented", A_STEP),
        (AWAIT_RESPONSE, {}),
        ("task.failed", {"reason": "You asked me to stop.", "recoverable": True}),
    ),
}


def test_every_ending_is_also_reached_through_a_step() -> None:
    """The structure itself: no ending is tested only from the working screen."""
    through = {name for name, script in ENDINGS.items()
               if any(message == AWAIT_RESPONSE for message, _ in script)}
    for name in TAILS:
        assert f"{name}, after a step" in through, name
    assert "stopped by the person" in through


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
        self.responses: list[dict] = []
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
                    if message_type == AWAIT_RESPONSE:
                        # Everything the overlay says, until the answer
                        # itself: since 2026-09-20 a telemetry sample goes out
                        # first, and reading exactly one message here read
                        # that instead of the response and then waited for a
                        # step that had already been answered.
                        try:
                            while True:
                                said = json.loads(await ws.recv())
                                self.responses.append(said)
                                if said.get("type") == "step.response":
                                    break
                        except websockets.ConnectionClosed:
                            return
                        continue
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
    backend.responses.clear()
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    page.fill("input[aria-label='What would you like me to do?']", GOAL)
    page.get_by_role("button", name="Start").click()
    if any(message_type == AWAIT_RESPONSE for message_type, _ in backend.script):
        # A step comes first, and the person answers it.
        page.wait_for_selector("[data-testid=step-shell]", timeout=15000)
        page.get_by_role("button", name=PRESSES.get(name, GO_AHEAD), exact=True).click()
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
    """A button that does nothing is not a way onward. "See it on the real
    page" (2026-10-16) leads to the picture, and back from it."""
    for label in [label for label in reach(page, overlay, backend, name) if label]:
        reach(page, overlay, backend, name)
        page.get_by_role("button", name=label, exact=True).click()
        if label == "See it on the real page":
            page.get_by_test_id("proof-panel").wait_for(timeout=5000)
            page.get_by_role("button", name="Back to the answer").click()
            page.get_by_role("button", name="I'm done").wait_for(timeout=5000)
            continue
        page.wait_for_function(
            f"() => document.body.innerText.includes({json.dumps(GREETING)})", timeout=5000
        )


def test_back_home_after_a_task_there_is_no_entrance(
    page: Page, overlay: str, backend: Backend
) -> None:
    """The tiles rise in once, when SIMBA opens (2026-10-14). Coming back to
    them after a task, they are simply there."""
    name = next(iter(ENDINGS))
    reach(page, overlay, backend, name)
    page.get_by_role("button", name="I'm done", exact=True).click()
    page.get_by_test_id("tile").first.wait_for(state="attached", timeout=5000)
    assert page.evaluate(
        "() => +getComputedStyle(document.querySelector('[data-testid=tiles] li')).opacity"
    ) == 1


MULTIPLE = ["39UP", "1UP", "7UP", "27UP", "101UP"]


@pytest.mark.parametrize("name", ["completed with several results",
                                  "completed with several results, after a step"])
def test_a_closing_screen_shows_every_result(
    name: str, page: Page, overlay: str, backend: Backend
) -> None:
    """Five trains came back, so five trains are on the screen.

    The run that prompted this found two and showed one, because the value
    was the first pair on the page (EVALUATION.md, 2026-09-18b). Reading the
    list out of the message rather than the summary line is what makes the
    fifth train visible: the line itself stops at four.
    """
    reach(page, overlay, backend, name)
    text = page.inner_text("body")

    for train in MULTIPLE:
        assert train in text, f"{train} missing from the closing screen: {text}"
    assert "and 1 more" not in text, "the closing screen showed the summary line"


# The window's content at each display scale, in CSS pixels, with the scale
# factor to match (EVALUATION.md, 2026-09-25c; `test_home.SIZES`).
WINDOWS = {
    "100%": (1280, 800, 1.0),
    "125%": (1280, 734, 1.25),
    "150%": (1266, 606, 1.5),
}

# Every button a person could press, and whether each is wholly inside the
# window; and whether the page is taller than the window. Also run inside the
# real host by `tools/evaluation/display_fit_run.py`.
ONWARD_JS = """() => {
    const shown = [...document.querySelectorAll('button')]
        .filter(b => b.offsetParent !== null && !b.disabled
                     && getComputedStyle(b).visibility !== 'hidden');
    const off = shown.filter(b => {
        const r = b.getBoundingClientRect();
        return r.top < 0 || r.left < 0 || r.bottom > innerHeight || r.right > innerWidth;
    });
    const name = b => b.innerText.trim() || b.getAttribute('aria-label') || '?';
    return {
        inner: [innerWidth, innerHeight],
        buttons: shown.map(name),
        off_screen: off.map(name),
        lowest: Math.round(Math.max(0, ...shown.map(b => b.getBoundingClientRect().bottom))),
        scroll_height: document.scrollingElement.scrollHeight,
        scrolls: document.scrollingElement.scrollHeight > innerHeight,
    };
}"""


def onward(page: Page) -> dict:
    """Where an ending's buttons are, from outside it."""
    return page.evaluate(ONWARD_JS)


@pytest.fixture(scope="module")
def windows(playwright_instance: Playwright) -> Iterator[dict[str, Page]]:
    """One page per window size, reused across endings."""
    browser = playwright_instance.chromium.launch()
    pages = {
        size: browser.new_page(viewport={"width": width, "height": height},
                               device_scale_factor=scale)
        for size, (width, height, scale) in WINDOWS.items()
    }
    yield pages
    browser.close()


@pytest.mark.parametrize("size", list(WINDOWS))
@pytest.mark.parametrize("name", list(ENDINGS))
def test_every_ending_fits_the_window(
    name: str, size: str, windows: dict[str, Page], overlay: str, backend: Backend
) -> None:
    """Every way onward is on screen without scrolling, at every scale."""
    page = windows[size]
    reach(page, overlay, backend, name)

    measured = onward(page)

    assert measured["buttons"], (name, size, measured)
    assert measured["off_screen"] == [], (name, size, measured)
    assert not measured["scrolls"], (name, size, measured)


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


def test_stopping_is_not_reported_as_a_failure(
    page: Page, overlay: str, backend: Backend
) -> None:
    """Pressing stop is the person's decision, and reads as one.

    The backend reports it as `task.failed` — the contract's only way to say a
    task ended without completing — and the screen used to show exactly that:
    "I couldn't finish this."
    """
    labels = reach(page, overlay, backend, "stopped by the person")
    text = page.inner_text("body")

    # The step response, not simply the first thing the overlay said: since
    # 2026-09-20 a telemetry sample goes out just before it (CONTRACT.md).
    answers = [message for message in backend.responses
               if message.get("type") == "step.response"]
    assert answers and answers[0]["payload"]["action_id"] == "cancel"
    assert "I've stopped, as you asked." in text
    assert "I couldn't finish this." not in text
    assert "You asked me to stop." not in text
    assert "Do something else" in labels


def test_a_failure_the_person_did_not_choose_still_says_so(
    page: Page, overlay: str, backend: Backend
) -> None:
    """The control: the fix did not turn every failure into a polite stop."""
    reach(page, overlay, backend, "failed")
    text = page.inner_text("body")
    assert "I couldn't finish this." in text
    assert "I've stopped, as you asked." not in text
