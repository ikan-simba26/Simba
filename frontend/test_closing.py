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
        scale: float = 1.0, until: str = "I'm done") -> Page:
    backend.script = script
    backend.responses.clear()
    page = browser.new_page(viewport={"width": size[0], "height": size[1]},
                            device_scale_factor=scale)
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    page.fill("input[aria-label='What would you like me to do?']", GOAL)
    page.get_by_role("button", name="Start").click()
    page.get_by_role("button", name=until).wait_for(timeout=15000)
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


# --- whole rows (2026-10-05) ---------------------------------------------------
#
# Since 2026-10-07 each row is a ticket: the result, then its other cells after
# a torn-paper rule, and "Fastest" on the one that takes least time.

#: Each ticket's parts, " | " between them.
# Each ticket's parts, " | " between them; a named cell as "Name value".
TICKETS = """[...document.querySelectorAll('[data-testid=ticket]')]
  .map(t => [...t.children].map(c => c.dataset.testid === 'ticket-cell'
    ? [...c.children].map(x => x.textContent.trim()).join(' ')
    : c.textContent.trim()).join(' | '))"""


def tickets(page: Page) -> list[str]:
    return page.evaluate(TICKETS)
#
# `Finding.rows` carries each result's cells together, repeats kept, on the
# first finding. The screen reads its lines from them, so no time can sit
# beside the wrong train.


def test_two_trains_that_share_a_journey_time_each_show_it(
    browser, overlay: str, backend: Backend  # noqa: F811
) -> None:
    page = end(browser, overlay, backend, completed(
        "There are 2 trains. The fastest takes 5 hours 15 minutes.", [
            {"label": "Train", "value": "3UP, 4DN", "values": ["3UP", "4DN"],
             "rows": [["3UP", "5 h 15 min"], ["4DN", "5 h 15 min"]]},
            {"label": "Journey", "value": "5 h 15 min", "values": ["5 h 15 min"]},
        ]))

    # Both take the same, so neither is the fastest.
    assert tickets(page) == ["3UP | Journey 5 h 15 min", "4DN | Journey 5 h 15 min"]
    assert page.get_by_text("Train, Journey", exact=True).count() == 0
    assert "Journey:" not in page.inner_text("body")


def test_repeats_on_different_rows_each_train_shows_its_own_time(
    browser, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """The departure repeats on rows 1 and 2, the journey on rows 2 and 3.
    Each list is two values for three trains — the case the lists alone could
    not pair. From rows, every line is one train's own."""
    page = end(browser, overlay, backend, completed(None, [
        {"label": "Train", "value": "1UP, 2UP, 3UP", "values": ["1UP", "2UP", "3UP"],
         "rows": [["1UP", "07:10", "5 h 15 min"], ["2UP", "07:10", "6 h 15 min"],
                  ["3UP", "09:00", "6 h 15 min"]]},
        {"label": "Departs", "value": "07:10, 09:00", "values": ["07:10", "09:00"]},
        {"label": "Journey", "value": "5 h 15 min, 6 h 15 min",
         "values": ["5 h 15 min", "6 h 15 min"]},
    ]))

    assert tickets(page) == ["1UP | Departs 07:10 | Journey 5 h 15 min | Fastest",
                             "2UP | Departs 07:10 | Journey 6 h 15 min",
                             "3UP | Departs 09:00 | Journey 6 h 15 min"]
    assert page.get_by_text("Train, Departs, Journey", exact=True).count() == 0


# The longest sentences the closing screen can now be given (2026-10-06): the
# fastest named, and a tie of three named.
NAMED = "There are 9 trains. The fastest is 107UP, at 4 hours 15 minutes."
TIED = "There are 9 trains. 105UP, 101UP and 107UP are the fastest, all at 4 hours 15 minutes."


@pytest.mark.parametrize("sentence", [NAMED, TIED], ids=["named", "a tie of three"])
@pytest.mark.parametrize("size, scale", SIZES)
def test_the_sentence_that_names_the_fastest_leaves_the_way_onward_on_screen(
    size, scale, sentence: str, browser, overlay: str, backend: Backend  # noqa: F811
) -> None:
    page = end(browser, overlay, backend, completed(sentence, TRAINS), size, scale)

    assert onward_on_screen(page, size[1]) == []
    assert page.get_by_test_id("explanation").inner_text() == sentence
    scrolls = page.evaluate("() => document.scrollingElement.scrollHeight > innerHeight")
    assert not scrolls


NINE_ROWS = [[train, journey] for train, journey in zip(
    NINE, JOURNEYS[:8] + [JOURNEYS[0]])]


@pytest.mark.parametrize("size, scale", SIZES)
def test_nine_trains_as_rows_leave_the_way_onward_on_screen(
    size, scale, browser, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """Nine trains, two sharing a time: from rows, six whole lines and a
    count, as tall as nine trains with nine times."""
    page = end(browser, overlay, backend, completed(SENTENCE, [
        {**TRAINS[0], "rows": NINE_ROWS},
        {"label": "Journey", "value": "4 h 30 min, 4 h 45 min, 5 h 20 min, 5 h 45 min and 4 more",
         "values": JOURNEYS[:8]},
    ]), size, scale)

    assert onward_on_screen(page, size[1]) == []
    # In the page's order, then the fastest, which is eighth: the one marked
    # is never among those counted. Five at full height, three in a short
    # window, where each ticket is one line of its own (2026-10-14).
    shown = 5 if size[1] > 760 else 3
    assert tickets(page) == [f"{train} | Journey {journey}"
                             for train, journey in NINE_ROWS[:shown - 1]] + [
        "107UP | Journey 4 h 15 min | Fastest"]
    assert page.get_by_text(f"and {9 - shown} more", exact=True).count() == 1


def test_a_tie_marks_every_train_in_it(browser, overlay: str, backend: Backend) -> None:  # noqa: F811
    page = end(browser, overlay, backend, completed(None, [
        {"label": "Train", "value": "11UP, 12DN, 13UP", "values": ["11UP", "12DN", "13UP"],
         "rows": [["11UP", "3 h 15 min"], ["12DN", "4 h 15 min"], ["13UP", "3 h 15 min"]]},
        {"label": "Journey", "value": "3 h 15 min, 4 h 15 min",
         "values": ["3 h 15 min", "4 h 15 min"]},
    ]))

    assert tickets(page) == ["11UP | Journey 3 h 15 min | Fastest",
                             "12DN | Journey 4 h 15 min",
                             "13UP | Journey 3 h 15 min | Fastest"]


def test_times_that_cannot_be_read_mark_nothing(browser, overlay: str,  # noqa: F811
                                               backend: Backend) -> None:
    page = end(browser, overlay, backend, completed(None, [
        {"label": "Train", "value": "9UP, 10DN", "values": ["9UP", "10DN"],
         "rows": [["9UP", "overnight"], ["10DN", "6 h 0 min"]]},
        {"label": "Journey", "value": "overnight, 6 h 0 min",
         "values": ["overnight", "6 h 0 min"]},
    ]))

    assert tickets(page) == ["9UP | Journey overnight", "10DN | Journey 6 h 0 min"]


def test_a_bill_is_a_slip_with_its_amount_and_what_supports_it(
    browser, overlay: str, backend: Backend  # noqa: F811
) -> None:
    page = end(browser, overlay, backend, completed(
        "Your bill is 14,382, and it is due on 15-10-2026.", [
            {"label": "Your bill", "value": "14,382", "values": ["14,382"]},
            {"label": "Due", "value": "15-10-2026", "values": ["15-10-2026"]},
        ]))

    found = page.get_by_test_id("findings")
    assert found.get_attribute("data-shape") == "slip"
    assert page.locator("[data-testid=findings] p").inner_text().split() == ["Due",
                                                                            "15-10-2026"]
    assert page.get_by_text("14,382", exact=True).count() == 1



def test_each_train_shows_when_it_leaves_and_arrives_and_how_long(
    browser, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """The live site prints both times in one cell, "08:04 06:20"; the
    backend reads them apart. Under a heading that says what the trains are
    for, and with no line naming the columns (2026-10-14)."""
    script = completed("There are 2 trains. The fastest is 2DN, at 22 hours 16 minutes.", [
        {"label": "Train", "value": "2DN, 14DN", "values": ["2DN", "14DN"],
         "rows": [["2DN", "08:04", "06:20, next day", "22 h 16 min"],
                  ["14DN", "19:09", "19:25, next day", "24 h 16 min"]]},
        {"label": "Leaves", "value": "08:04, 19:09", "values": ["08:04", "19:09"]},
        {"label": "Arrives", "value": "06:20, 19:25", "values": ["06:20", "19:25"]},
        {"label": "Journey", "value": "22 h 16 min, 24 h 16 min",
         "values": ["22 h 16 min", "24 h 16 min"]},
    ])
    script[-1][1]["heading"] = "Lahore Cantt to Karachi Cantt, Thursday 15 October"
    page = end(browser, overlay, backend, script)

    assert page.get_by_test_id("heading").inner_text() == (
        "Lahore Cantt to Karachi Cantt, Thursday 15 October")
    # A next-day arrival says so (the backend's `voice.arrival`, 2026-10-15).
    assert tickets(page) == [
        "2DN | Leaves 08:04 | Arrives 06:20, next day | Journey 22 h 16 min | Fastest",
        "14DN | Leaves 19:09 | Arrives 19:25, next day | Journey 24 h 16 min"]
    assert "Train, Journey" not in page.inner_text("body")
    assert "Train, Leaves" not in page.inner_text("body")
    # Each ticket still one line, nothing to scroll.
    heights = page.eval_on_selector_all("[data-testid=ticket]",
                                        "ts => ts.map(t => t.getBoundingClientRect().height)")
    assert max(heights) < 80, heights
    assert not page.evaluate("document.scrollingElement.scrollHeight > innerHeight")
    # Times in the interface's own face, every figure one width (2026-10-15).
    styles = page.eval_on_selector_all(
        "[data-testid=ticket-cell] > span:last-child",
        "cells => cells.map(c => [getComputedStyle(c).fontFamily, "
        "getComputedStyle(c).fontVariantNumeric])")
    body = page.evaluate("getComputedStyle(document.body).fontFamily")
    assert all(family == body and "tabular-nums" in numeric for family, numeric in styles), styles


def test_a_page_that_prints_one_time_shows_no_arrival(
    browser, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """Nothing is worked out: an empty "Arrives" is left out."""
    page = end(browser, overlay, backend, completed(None, [
        {"label": "Train", "value": "7UP, 8DN", "values": ["7UP", "8DN"],
         "rows": [["7UP", "07:20", "7 h 15 min"], ["8DN", "16:30", "8 h 15 min"]]},
        {"label": "Leaves", "value": "07:20, 16:30", "values": ["07:20", "16:30"]},
        {"label": "Journey", "value": "7 h 15 min, 8 h 15 min",
         "values": ["7 h 15 min", "8 h 15 min"]},
    ]))

    assert tickets(page)[0] == "7UP | Leaves 07:20 | Journey 7 h 15 min | Fastest"


def test_the_last_line_says_what_was_not_done(
    browser, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """Every closing screen ends with what was and was not done (2026-10-16)."""
    script = completed("There are 2 trains. The fastest is 7UP, at 7 hours 15 minutes.", [
        {"label": "Train", "value": "7UP, 8DN", "values": ["7UP", "8DN"],
         "rows": [["7UP", "07:25", "14:40", "7 h 15 min"],
                  ["8DN", "16:35", "00:50, next day", "8 h 15 min"]]},
        {"label": "Leaves", "value": "07:25, 16:35", "values": ["07:25", "16:35"]},
        {"label": "Arrives", "value": "14:40, 00:50", "values": ["14:40", "00:50"]},
        {"label": "Journey", "value": "7 h 15 min, 8 h 15 min",
         "values": ["7 h 15 min", "8 h 15 min"]},
    ])
    script[-1][1]["scope"] = ("I only looked up times. I did not book a ticket or pay "
                              "for anything.")
    page = end(browser, overlay, backend, script)

    scope = page.get_by_test_id("scope")
    assert scope.inner_text() == script[-1][1]["scope"]
    # The last thing in the answer, under the tickets.
    tickets = page.get_by_test_id("ticket").last.bounding_box()
    assert scope.bounding_box()["y"] > tickets["y"] + tickets["height"]


def test_a_registration_quotes_the_portals_confirmation(
    browser, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """What changed, and the site's own word for it (2026-10-16)."""
    script = completed(None, [])
    script[-1][1]["scope"] = "You are registered for CS-401 section 001."
    script[-1][1]["confirmation"] = ("The portal says “Registration Confirmed”, "
                                     "with confirmation number REG-10234-2026.")
    page = end(browser, overlay, backend, script)

    assert page.get_by_test_id("scope").inner_text() == script[-1][1]["scope"]
    assert page.get_by_test_id("confirmation").inner_text() == script[-1][1]["confirmation"]
    # The goal is not repeated where the line says what changed.
    assert GOAL not in page.inner_text("body")


def test_a_change_not_confirmed_says_so_first(
    browser, overlay: str, backend: Backend  # noqa: F811
) -> None:
    from frontend.test_terminal_states import ENDINGS

    page = end(browser, overlay, backend, ENDINGS["not confirmed"], until="Do something else")

    assert page.get_by_role("heading", level=1).inner_text() == "It isn't confirmed."
    assert "I'm stuck" not in page.inner_text("body")
    assert page.get_by_test_id("unconfirmed").inner_text().startswith(
        "I tried to press “Register for CS-401”")


def test_the_answer_can_be_seen_on_the_real_page(
    browser, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """The still the backend took as it finished, with what it read ringed,
    where it read it (2026-10-16)."""
    from frontend.test_terminal_states import PROOF

    proof = {**PROOF, "rings": [{"x": 640, "y": 400, "w": 128, "h": 80},
                                {"x": 0, "y": 0, "w": 64, "h": 40}]}
    script = completed("Your bill is 14,382, and it is due on 15-09-2026.", [
        {"label": "Your bill", "value": "14,382"}, {"label": "Due", "value": "15-09-2026"}])
    script[-1][1]["proof"] = proof
    page = end(browser, overlay, backend, script)

    page.get_by_role("button", name="See it on the real page").click()
    panel = page.get_by_test_id("proof-panel")
    panel.wait_for(timeout=5000)
    page.wait_for_timeout(600)
    assert "What I read is ringed." in panel.inner_text()
    picture = panel.locator("img").bounding_box()
    rings = [r.bounding_box() for r in panel.get_by_test_id("proof-ring").all()]
    assert len(rings) == 2
    # Where the backend found it, in the picture's own proportions: the
    # middle of the page is the middle of the picture (each ring 6px wider
    # all round than what it rings).
    middle = rings[0]
    assert abs((middle["x"] + 6 - picture["x"]) / picture["width"] - 0.5) < 0.01
    assert abs((middle["y"] + 6 - picture["y"]) / picture["height"] - 0.5) < 0.01
    page.get_by_role("button", name="Back to the answer").click()
    page.wait_for_timeout(800)
    assert page.get_by_test_id("proof-panel").count() == 0
    assert page.get_by_role("button", name="I'm done").is_visible()


def test_no_picture_is_said_and_no_button_shown(
    browser, overlay: str, backend: Backend  # noqa: F811
) -> None:
    script = completed(None, [{"label": "Your bill", "value": "14,382"}])
    script[-1][1]["proof_note"] = "I couldn't get a picture of the page to show you."
    page = end(browser, overlay, backend, script)

    assert page.get_by_test_id("proof-note").inner_text() == script[-1][1]["proof_note"]
    assert page.get_by_role("button", name="See it on the real page").count() == 0
