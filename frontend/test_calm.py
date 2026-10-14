"""Calm, measured: nothing moves for someone who has asked for less motion.

`index.css` stops CSS transitions and animations under
`prefers-reduced-motion: reduce`, but most of the overlay's motion is Framer
Motion, which animates from JavaScript and never reads that rule. So it is
measured here in a real browser with reduced motion emulated: whatever is on
screen is sampled over a few seconds and must not change.
"""

from collections.abc import Iterator

import pytest
from playwright.sync_api import Page, Playwright

from frontend.test_terminal_states import AWAIT_RESPONSE, Backend, overlay  # noqa: F401

GOAL = "trains to Rawalpindi tomorrow"

THINKING = [
    ("task.started", {"goal": GOAL, "estimated_steps": 4}),
    ("state.changed", {"state": "thinking"}),
    # Held open: the run is thinking for as long as the test looks.
    (AWAIT_RESPONSE, {}),
]

#: How the presence mark looks, as numbers that change if it moves.
LOOKS = """() => [...document.querySelectorAll('[data-presence] *')].map(e => {
  const s = getComputedStyle(e);
  return s.transform + '|' + s.opacity;
}).join(';')"""


@pytest.fixture(scope="module")
def backend() -> Backend:
    return Backend()


@pytest.fixture
def still_page(playwright_instance: Playwright) -> Iterator[Page]:
    browser = playwright_instance.chromium.launch()
    context = browser.new_context(viewport={"width": 1280, "height": 800},
                                  reduced_motion="reduce")
    yield context.new_page()
    browser.close()


def start(page: Page, overlay: str, backend: Backend, script) -> None:  # noqa: F811
    backend.script = script
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    page.fill("input[aria-label='What would you like me to do?']", GOAL)
    page.get_by_role("button", name="Start").click()


def samples(page: Page, script: str, count: int = 12, every_ms: int = 250) -> list[str]:
    seen = []
    for _ in range(count):
        seen.append(page.evaluate(script))
        page.wait_for_timeout(every_ms)
    return seen


def test_the_presence_mark_is_still_while_thinking_under_reduced_motion(
    still_page: Page, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """It breathes, slowly and forever, for everyone else."""
    start(still_page, overlay, backend, THINKING)
    still_page.wait_for_selector("[data-presence=thinking]", timeout=15000)
    still_page.wait_for_timeout(800)  # anything arriving has arrived

    seen = samples(still_page, LOOKS)

    assert len(set(seen)) == 1, f"{len(set(seen))} different looks in 3s"


# --- SIMBA's shape (2026-10-07) -----------------------------------------------

SHAPE_POSE = "getComputedStyle(document.querySelector('.simba-shape')).transform"

A_STEP = {
    "step_index": 1, "step_total": 3, "instruction": "Let me find the right month.",
    "detail": "", "fields": [], "requires_confirmation": True, "findings": [],
    "actions": [{"id": "confirm", "label": "Open the calendar", "kind": "primary"},
                {"id": "cancel", "label": "Stop this", "kind": "secondary"}],
}


@pytest.fixture
def moving_page(playwright_instance: Playwright) -> Iterator[Page]:
    browser = playwright_instance.chromium.launch()
    context = browser.new_context(viewport={"width": 1280, "height": 800},
                                  reduced_motion="no-preference")
    yield context.new_page()
    browser.close()


def home(page: Page, overlay: str, backend: Backend) -> None:  # noqa: F811
    backend.script = []
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    page.get_by_role("textbox", name="What would you like me to do?").wait_for()
    page.wait_for_timeout(600)


def thinking(page: Page, overlay: str, backend: Backend) -> None:  # noqa: F811
    start(page, overlay, backend, THINKING)
    page.wait_for_selector("[data-presence=thinking]", timeout=15000)
    page.wait_for_timeout(800)


def test_one_presence_mark_large_and_still_on_the_home_screen(
    moving_page: Page, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """The shape is the presence mark (2026-10-14): one of it, and no dot."""
    home(moving_page, overlay, backend)

    assert moving_page.locator("[data-testid=shape]").count() == 1
    assert moving_page.get_attribute("[data-presence]", "data-size") == "large"
    assert len(set(samples(moving_page, SHAPE_POSE, count=6, every_ms=500))) == 1


def test_it_turns_only_while_simba_is_working(moving_page: Page, overlay: str,  # noqa: F811
                                              backend: Backend) -> None:
    thinking(moving_page, overlay, backend)

    assert moving_page.locator("[data-testid=shape]").count() == 1
    assert moving_page.get_attribute("[data-presence]", "data-size") == "small"
    assert len(set(samples(moving_page, SHAPE_POSE, count=6, every_ms=500))) > 1


def test_it_is_still_while_working_under_reduced_motion(still_page: Page, overlay: str,  # noqa: F811
                                                        backend: Backend) -> None:
    thinking(still_page, overlay, backend)
    seen = samples(still_page, SHAPE_POSE, count=6, every_ms=500)
    assert len(set(seen)) == 1
    assert seen[0] != "none", "still, and still a 3D pose"


def test_on_a_step_it_is_small_and_still(moving_page: Page, overlay: str,  # noqa: F811
                                         backend: Backend) -> None:
    start(moving_page, overlay, backend, [
        ("task.started", {"goal": GOAL, "estimated_steps": 3}),
        ("state.changed", {"state": "waiting"}),
        ("step.presented", A_STEP),
        (AWAIT_RESPONSE, {}),
    ])
    moving_page.wait_for_selector("[data-testid=step-shell]", timeout=15000)
    moving_page.wait_for_timeout(1200)  # the home screen's crossfade is over

    assert moving_page.locator("[data-testid=shape]").count() == 1
    assert moving_page.get_attribute("[data-presence]", "data-presence") == "waiting"
    assert moving_page.get_attribute("[data-presence]", "data-size") == "small"
    assert len(set(samples(moving_page, SHAPE_POSE, count=6, every_ms=500))) == 1


def test_nothing_moves_while_the_window_is_not_focused(moving_page: Page, overlay: str,  # noqa: F811
                                                       backend: Backend) -> None:
    thinking(moving_page, overlay, backend)
    moving_page.evaluate("window.dispatchEvent(new Event('blur'))")
    moving_page.evaluate("document.documentElement.dataset.motion = 'paused'")
    # The pause takes hold on the next frame. Sampled at once, the first pose
    # could be one step (50ms of turn) before it: 2 runs in 5 failed so.
    moving_page.wait_for_timeout(150)

    play = moving_page.evaluate(
        "getComputedStyle(document.querySelector('.simba-shape')).animationPlayState")
    assert play == "paused"
    assert len(set(samples(moving_page, SHAPE_POSE, count=6, every_ms=500))) == 1

    moving_page.evaluate("window.dispatchEvent(new Event('focus'))")
    assert moving_page.evaluate("document.documentElement.dataset.motion") == "on"


#: Five seconds of frames: how long each one took to come.
FRAMES = """() => new Promise(done => {
  const times = []; const start = performance.now();
  const tick = (now) => { times.push(now);
    if (now - start < 5000) requestAnimationFrame(tick); else done(times); };
  requestAnimationFrame(tick);
})"""


def cost(page: Page) -> tuple[float, float]:
    """(main-thread task seconds, slowest-frame milliseconds at the 95th
    percentile) over five seconds on the screen as it is."""
    session = page.context.new_cdp_session(page)
    session.send("Performance.enable")
    before = {m["name"]: m["value"] for m in session.send("Performance.getMetrics")["metrics"]}
    times = page.evaluate(FRAMES)
    after = {m["name"]: m["value"] for m in session.send("Performance.getMetrics")["metrics"]}
    gaps = sorted(b - a for a, b in zip(times, times[1:]))
    return after["TaskDuration"] - before["TaskDuration"], gaps[int(len(gaps) * 0.95)]


def test_the_shape_does_not_slow_the_window(moving_page: Page, still_page: Page,  # noqa: F811
                                            overlay: str, backend: Backend) -> None:
    """While SIMBA is working, the one time it turns, measured against the same
    screen with it held still. The frame loop that measures costs the same on
    both, so the difference is the turn."""
    thinking(moving_page, overlay, backend)
    thinking(still_page, overlay, backend)
    moving = cost(moving_page)
    still = cost(still_page)
    print(f"\nshape turning: {moving[0] * 1000:.0f}ms of main-thread work in 5s, "
          f"p95 frame {moving[1]:.1f}ms; held still: {still[0] * 1000:.0f}ms, "
          f"p95 frame {still[1]:.1f}ms")
    # Measured at about 70ms more in five seconds (EVALUATION.md, 2026-10-07).
    # Held to under 3% of one core, and to every frame on time: a 95th
    # percentile frame no slower than one at 50fps.
    assert moving[0] - still[0] < 0.15
    assert moving[1] < 20
