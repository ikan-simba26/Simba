"""The closing screen's sentence, rendered: above the result, and what it costs.

`task.completed.explanation` (2026-10-03) is one plain sentence the backend
builds from the page's own values. The overlay writes none of its own; it
shows the sentence above the findings, or, on an ending with no findings, in
place of restating the goal. These render it in a real browser.

**What they found besides.** The closing screen did not fit before the
sentence: with three results the way onward was already partly below the
window at every scale, and with nine — the longest answer a real search has
given (EVALUATION.md, 2026-09-30) — entirely. The fit was only ever measured
for the home screen and for steps. Both cases are pinned below as strict known
failures, with the sentence's own 51-61px on top, so the day the closing
screen is made to fit they fail and are turned into ordinary tests.
"""

from collections.abc import Iterator

import pytest
from playwright.sync_api import Page, Playwright

from frontend.test_terminal_states import (  # noqa: F401 - fixtures
    Backend,
    overlay,
)

GOAL = "trains to Rawalpindi tomorrow"
NINE = ["105UP", "101UP", "13UP", "39UP", "7UP", "5UP", "103UP", "107UP", "1UP"]
JOURNEYS = ["4 h 30 min", "4 h 45 min", "5 h 20 min", "5 h 45 min", "5 h 30 min",
            "4 h 25 min", "5 h 10 min", "4 h 15 min", "5 h 15 min"]
SENTENCE = "There are 9 trains. The fastest takes 4 hours 15 minutes."


def completed(explanation: str | None, findings: list[dict]) -> list[tuple[str, dict]]:
    return [
        ("task.started", {"goal": GOAL, "estimated_steps": 6}),
        ("state.changed", {"state": "thinking"}),
        ("task.completed", {
            "summary": f"{GOAL} http://127.0.0.1:5200/", "duration_ms": 1,
            "steps_taken": 5, "llm_calls": 0, "replayed": False,
            "findings": findings, "explanation": explanation,
        }),
    ]


TRAINS = [
    {"label": "Train", "value": "105UP, 101UP, 13UP, 39UP and 5 more", "values": NINE},
    {"label": "Journey", "value": "4 h 30 min, 4 h 45 min, 5 h 20 min, 5 h 45 min and 5 more",
     "values": JOURNEYS},
]


@pytest.fixture(scope="module")
def backend() -> Backend:
    return Backend()


@pytest.fixture
def browser(playwright_instance: Playwright) -> Iterator:
    browser = playwright_instance.chromium.launch()
    yield browser
    browser.close()


def end(browser, overlay: str, backend: Backend, script, size=(1280, 800),  # noqa: F811
        scale: float = 1.0) -> Page:
    backend.script = script
    backend.responses.clear()
    page = browser.new_page(viewport={"width": size[0], "height": size[1]},
                            device_scale_factor=scale)
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    page.fill("input[aria-label='What would you like me to do?']", GOAL)
    page.get_by_role("button", name="Start").click()
    page.get_by_role("button", name="I'm done").wait_for(timeout=15000)
    page.wait_for_timeout(900)
    return page


def test_the_sentence_is_above_the_result(browser, overlay: str, backend: Backend) -> None:  # noqa: F811
    page = end(browser, overlay, backend, completed(SENTENCE, TRAINS))

    said = page.get_by_test_id("explanation")
    assert said.inner_text() == SENTENCE
    first_train = page.get_by_text("105UP", exact=True).first
    assert said.bounding_box()["y"] < first_train.bounding_box()["y"]


def test_no_sentence_and_the_screen_is_as_it_was(browser, overlay: str, backend: Backend) -> None:  # noqa: F811
    page = end(browser, overlay, backend, completed(None, TRAINS))

    assert page.get_by_test_id("explanation").count() == 0
    assert page.get_by_text("105UP", exact=True).count()


def test_with_no_findings_it_says_what_happened_instead_of_the_goal(
    browser, overlay: str, backend: Backend  # noqa: F811
) -> None:
    page = end(browser, overlay, backend,
               completed("You are registered for MATH-210 section 001.", []))

    assert page.get_by_test_id("explanation").inner_text() == (
        "You are registered for MATH-210 section 001.")
    assert GOAL not in page.inner_text("body")


THREE = [
    {"label": "Train", "value": "13UP, 39UP, 1UP", "values": ["13UP", "39UP", "1UP"]},
    {"label": "Journey", "value": "6 h 6 min, 6 h 38 min, 6 h 3 min",
     "values": ["6 h 6 min", "6 h 38 min", "6 h 3 min"]},
]
SIZES = [((1280, 800), 1.0), ((1280, 734), 1.25), ((1266, 606), 1.5)]


def onward_on_screen(page: Page, height: int) -> list[str]:
    """The buttons of the way onward that are not wholly on screen."""
    off = []
    for name in ("I'm done", "Do something else"):
        box = page.get_by_role("button", name=name, exact=True).bounding_box()
        if box is None or box["y"] + box["height"] > height:
            off.append(name)
    return off


@pytest.mark.xfail(strict=True, reason=(
    "Known, and older than the sentence: the closing screen does not fit with "
    "three results at any scale. With no sentence, 'Do something else' ended at "
    "851 of 800 at 100%, and 'I'm done' began at 595 of 606 at 150%. The "
    "sentence adds 51-61px. Measured 2026-10-03; STATUS.md, Interface. Strict, "
    "so this fails the day it is fixed."))
@pytest.mark.parametrize("size, scale", SIZES)
def test_the_example_and_its_sentence_leave_the_way_onward_on_screen(
    size, scale, browser, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """The live search's three trains (2026-09-30, run 6) with the sentence
    asked for: everything on screen at every scale."""
    page = end(browser, overlay, backend, completed(
        "There are 3 trains. The fastest takes 6 hours 3 minutes.", THREE), size, scale)

    assert onward_on_screen(page, size[1]) == []
    said = page.get_by_test_id("explanation").bounding_box()
    assert said is not None and said["y"] >= 0


@pytest.mark.xfail(strict=True, reason=(
    "Known, and older than the sentence: nine results put 'I'm done' below the "
    "window at every scale (y=1057 of 800 at 100%, 973 of 606 at 150%, with no "
    "sentence). The sentence adds 51-61px. A layout question for the closing "
    "screen; STATUS.md, Interface. Strict, so this fails the day it is fixed."))
@pytest.mark.parametrize("size, scale", SIZES)
def test_nine_trains_leave_the_way_onward_on_screen(
    size, scale, browser, overlay: str, backend: Backend  # noqa: F811
) -> None:
    page = end(browser, overlay, backend, completed(SENTENCE, TRAINS), size, scale)

    assert onward_on_screen(page, size[1]) == []
