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
