"""The closing screen: the sentence, the results, and room for the way onward.

`task.completed.explanation` (2026-10-03) is one plain sentence the backend
builds from the page's own values. The overlay writes none of its own; it
shows the sentence above the findings, in the place of the "Here's what I
found" lead-in, or, on an ending with no findings, in place of restating the
goal. These render it in a real browser.

**The fit.** Until 2026-10-05 the closing screen did not fit: with three
results the way onward was partly below the window at every scale, and with
nine — the longest answer a real search has given (EVALUATION.md,
2026-09-30) — entirely. Six strict known failures here recorded that. Now
each result is one line with its detail beside it, past six the rest are
counted, the sentence takes the lead-in's place, and the two buttons sit side
by side; with 1, 3 and 9 results, at 100%, 125% and 150%,
both buttons are wholly on screen. `test_terminal_states.py` checks the same
for every ending.
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
    first_train = page.get_by_text("105UP, 4 h 30 min", exact=True)
    assert said.bounding_box()["y"] < first_train.bounding_box()["y"]
    # In the lead-in's place: the two said one thing twice.
    assert "Here's what I found" not in page.inner_text("body")


def test_no_sentence_and_the_lead_in_is_there_instead(
    browser, overlay: str, backend: Backend  # noqa: F811
) -> None:
    page = end(browser, overlay, backend, completed(None, TRAINS))

    assert page.get_by_test_id("explanation").count() == 0
    assert "Here's what I found" in page.inner_text("body")
    assert page.get_by_text("105UP, 4 h 30 min", exact=True).count() == 1


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
ONE = [
    {"label": "Train", "value": "13UP", "values": ["13UP"]},
    {"label": "Journey", "value": "6 h 6 min", "values": ["6 h 6 min"]},
]
# The window's content at each display scale (EVALUATION.md, 2026-09-25c).
SIZES = [((1280, 800), 1.0), ((1280, 734), 1.25), ((1266, 606), 1.5)]


def onward_on_screen(page: Page, height: int) -> list[str]:
    """The buttons of the way onward that are not wholly on screen."""
    off = []
    for name in ("I'm done", "Do something else"):
        box = page.get_by_role("button", name=name, exact=True).bounding_box()
        if box is None or box["y"] + box["height"] > height:
            off.append(name)
    return off


@pytest.mark.parametrize("size, scale", SIZES)
def test_the_example_and_its_sentence_leave_the_way_onward_on_screen(
    size, scale, browser, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """The live search's three trains (2026-09-30, run 6) with the sentence
    asked for: everything on screen at every scale.

    Measured 2026-10-03, before the fix and with no sentence: 'Do something
    else' ended at 851 of 800 at 100%, and 'I'm done' began at 595 of 606 at
    150%."""
    page = end(browser, overlay, backend, completed(
        "There are 3 trains. The fastest takes 6 hours 3 minutes.", THREE), size, scale)

    assert onward_on_screen(page, size[1]) == []
    said = page.get_by_test_id("explanation").bounding_box()
    assert said is not None and said["y"] >= 0
    # Each train with its journey, one line each.
    for row in ("13UP, 6 h 6 min", "39UP, 6 h 38 min", "1UP, 6 h 3 min"):
        assert page.get_by_text(row, exact=True).count() == 1, row


@pytest.mark.parametrize("size, scale", SIZES)
def test_nine_trains_leave_the_way_onward_on_screen(
    size, scale, browser, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """Measured 2026-10-03, before the fix and with no sentence: 'I'm done'
    began at y=1057 of 800 at 100%, and 973 of 606 at 150%."""
    page = end(browser, overlay, backend, completed(SENTENCE, TRAINS), size, scale)

    assert onward_on_screen(page, size[1]) == []


@pytest.mark.parametrize("size, scale", SIZES)
def test_one_train_and_its_sentence_leave_the_way_onward_on_screen(
    size, scale, browser, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """One result keeps the large type the billing answer has always had."""
    page = end(browser, overlay, backend, completed(
        "There is 1 train. It takes 6 hours 6 minutes.", ONE), size, scale)

    assert onward_on_screen(page, size[1]) == []
    assert page.get_by_text("13UP", exact=True).count() == 1


def test_past_six_the_rest_are_counted(browser, overlay: str, backend: Backend) -> None:  # noqa: F811
    page = end(browser, overlay, backend, completed(SENTENCE, TRAINS))
    text = page.inner_text("body")

    for train, journey in list(zip(NINE, JOURNEYS))[:6]:
        assert f"{train}, {journey}" in text
    for train, journey in list(zip(NINE, JOURNEYS))[6:]:
        assert f"{train}, {journey}" not in text
    assert "and 3 more" in text
    # The labels, once, under the list they name.
    assert page.get_by_text("Train, Journey", exact=True).count() == 1


def test_six_are_all_shown_and_nothing_is_counted(
    browser, overlay: str, backend: Backend  # noqa: F811
) -> None:
    six = [{"label": f["label"], "value": "", "values": f["values"][:6]} for f in TRAINS]
    page = end(browser, overlay, backend, completed(SENTENCE, six))
    text = page.inner_text("body")

    assert all(train in text for train in NINE[:6])
    assert "more" not in text


def test_a_detail_that_does_not_line_up_is_not_put_beside_a_result(
    browser, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """Three trains and two journey times: perception keeps a repeated value
    once (`values_for`), so the two lists no longer line up row for row, and
    pairing them by position would put a time beside the wrong train."""
    page = end(browser, overlay, backend, completed(None, [
        {"label": "Train", "value": "13UP, 39UP, 1UP", "values": ["13UP", "39UP", "1UP"]},
        {"label": "Journey", "value": "6 h 6 min, 6 h 38 min",
         "values": ["6 h 6 min", "6 h 38 min"]},
    ]))
    text = page.inner_text("body")

    assert "13UP, 6 h 6 min" not in text
    for train in ("13UP", "39UP", "1UP"):
        assert page.get_by_text(train, exact=True).count() == 1, train
    assert "Journey: 6 h 6 min, 6 h 38 min" in text


@pytest.mark.parametrize("size, scale", SIZES)
def test_nine_trains_and_eight_journeys_leave_the_way_onward_on_screen(
    size, scale, browser, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """Two of nine trains with the same journey time, so eight times. Each
    detail that cannot go beside a result takes one result's place: five
    trains, "and 4 more", and the times on a line of their own. As a block of
    its own it put both buttons 87px below a 606px window."""
    eight = [TRAINS[0], {"label": "Journey",
                         "value": "4 h 30 min, 4 h 45 min, 5 h 20 min, 5 h 45 min and 4 more",
                         "values": JOURNEYS[:8]}]
    page = end(browser, overlay, backend, completed(SENTENCE, eight), size, scale)
    text = page.inner_text("body")

    assert onward_on_screen(page, size[1]) == []
    assert all(page.get_by_text(train, exact=True).count() == 1 for train in NINE[:5])
    assert page.get_by_text("and 4 more", exact=True).count() == 1
    assert "Journey: 4 h 30 min" in text
