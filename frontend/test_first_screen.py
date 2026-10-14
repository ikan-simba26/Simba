"""A task's first screen: it fits at level 2 without folding, and no notice is
ever shown on it (2026-10-14).

In the real window at 150% the station question did not fit at level 2: the
overflow guard folded it and said so — "I've made this smaller so it fits."
— on the first screen of every task. Each flow's first question is checked
here at 100%, 125% and 150% (both the 606px window with Electron's menu bar
and the 632px one without it).
"""

import pytest
from playwright.sync_api import Page, Playwright

from frontend.test_terminal_states import AWAIT_RESPONSE, Backend, overlay  # noqa: F401

GOAL = "train"
TRIP = ["From", "To", "Day", "Search", "Trains"]
STATIONS = ["LAHORE JN", "LAHORE CANTT", "KARACHI CANTT", "KARACHI CITY", "RAWALPINDI",
            "MULTAN CANTT", "SUKKUR", "QUETTA"]
LEVEL_LABELS = {1: "Show more", 2: "Show the usual amount", 3: "Show less"}


def acts(*labels):
    if len(labels) == 1:
        out = [{"id": "confirm", "label": labels[0], "kind": "primary"}]
    else:
        out = [{"id": f"choice:{i}", "label": l, "kind": "primary"} for i, l in enumerate(labels)]
    return out + [{"id": "cancel", "label": "Stop this", "kind": "secondary"}]


def question(instruction, actions, fields=(), detail="", kind=None, stage=0):
    return {"step_index": 1, "step_total": 9, "instruction": instruction, "detail": detail,
            "fields": list(fields), "actions": actions, "requires_confirmation": True,
            "findings": [], "step_kind": kind, "stage": stage}


FIRST = {
    "where from": (TRIP, question("Where are you travelling from?", acts("That's it"),
        [{"id": "origin", "label": "From", "type": "choice", "value": "", "options": STATIONS}],
        kind="place")),
    "which station": (TRIP, question("Which Lahore station do you mean?",
        acts("Lahore Jn", "Lahore Cantt", "None of these"), kind="place")),
    "read back": (TRIP, question("Lahore Cantt to Karachi Cantt, tomorrow, 15 October. "
        "Is that right?", acts("Yes, that's right", "No, change something"), kind="confirm",
        stage=3)),
    "which day": (TRIP, question("What day are you travelling?",
        acts("Today", "Tomorrow", "Pick another day"), kind="date", stage=2)),
    "reference": (["Reference", "Look up", "Your bill"], question(
        "What is the reference number on your bill?", acts("That's it"),
        [{"id": "reference", "label": "Reference number", "type": "text", "value": ""}],
        detail="It is the 14-digit number at the top left of your bill.", kind="type")),
    "course": (["Course", "Sign in", "Register", "Done"], question(
        "Which course would you like to register for?", acts("That's it"),
        [{"id": "course", "label": "Course", "type": "text", "value": ""}],
        detail="A course code looks like CS-401.", kind="type")),
}
SIZES = {"100%": (1280, 800, 1.0), "125%": (1280, 734, 1.25),
         "150%, 632": (1266, 632, 1.5), "150%, 606": (1266, 606, 1.5)}


@pytest.fixture(scope="module")
def backend() -> Backend:
    return Backend()


@pytest.fixture(scope="module")
def browser(playwright_instance: Playwright):
    browser = playwright_instance.chromium.launch()
    yield browser
    browser.close()


def show(browser, overlay: str, backend: Backend, script, size) -> Page:  # noqa: F811
    width, height, scale = size
    page = browser.new_page(viewport={"width": width, "height": height},
                            device_scale_factor=scale)
    backend.script = script
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    page.fill("input[aria-label='What would you like me to do?']", GOAL)
    page.get_by_role("button", name="Start").click()
    page.wait_for_selector("[data-testid=step-shell]", timeout=15000)
    page.wait_for_timeout(1500)  # past the guard's measure, and any notice
    return page


def level_on_screen(page: Page) -> int:
    label = page.locator('button[aria-pressed="true"]').first.get_attribute("aria-label")
    return next(level for level, name in LEVEL_LABELS.items() if name == label)


@pytest.mark.parametrize("size", list(SIZES), ids=list(SIZES))
@pytest.mark.parametrize("name", list(FIRST), ids=list(FIRST))
def test_the_first_question_fits_at_level_2_without_a_notice(
    browser, overlay: str, backend: Backend, name: str, size: str  # noqa: F811
) -> None:
    stages, step = FIRST[name]
    page = show(browser, overlay, backend, [
        ("task.started", {"goal": GOAL, "estimated_steps": 9, "stages": stages}),
        ("state.changed", {"state": "waiting"}),
        ("step.presented", step),
        (AWAIT_RESPONSE, {}),
    ], SIZES[size])
    try:
        assert level_on_screen(page) == 2
        assert page.get_by_test_id("notice-line").count() == 0
        assert not page.evaluate("document.scrollingElement.scrollHeight > innerHeight")
    finally:
        page.close()


def test_a_level_change_before_the_first_screen_shows_no_notice(
    browser, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """The level rules may start a heavy first page simpler. That is the screen
    arriving as it is, not a change the person saw happen."""
    stages, step = FIRST["which day"]
    page = show(browser, overlay, backend, [
        ("task.started", {"goal": GOAL, "estimated_steps": 9, "stages": stages}),
        ("load.updated", {"score": 0.9, "level": 3, "reason": "heavy page"}),
        ("state.changed", {"state": "waiting"}),
        ("step.presented", step),
        (AWAIT_RESPONSE, {}),
    ], SIZES["100%"])
    try:
        assert level_on_screen(page) == 3
        assert page.get_by_test_id("notice-line").count() == 0
    finally:
        page.close()


def test_a_fold_on_the_first_screen_shows_no_notice_and_the_next_screen_still_can(
    browser, overlay: str, backend: Backend  # noqa: F811
) -> None:
    tall = question(" ".join(["What day are you travelling?"] * 8),
                    acts("Today", "Tomorrow", "Pick another day"), kind="date", stage=2)
    second = {**question("Let me set where you're starting from.", acts("Set it"), stage=3),
              "step_index": 2}
    page = show(browser, overlay, backend, [
        ("task.started", {"goal": GOAL, "estimated_steps": 9, "stages": TRIP}),
        ("state.changed", {"state": "waiting"}),
        ("step.presented", tall),
        (AWAIT_RESPONSE, {}),
        ("load.updated", {"score": 0.9, "level": 3, "reason": "pause"}),
        ("state.changed", {"state": "waiting"}),
        ("step.presented", second),
        (AWAIT_RESPONSE, {}),
    ], SIZES["150%, 606"])
    try:
        assert page.get_by_test_id("notice-line").count() == 0
        page.get_by_role("button", name="Today", exact=True).click()
        page.get_by_text("Let me set where you're starting from.").first.wait_for(timeout=10000)
        page.wait_for_timeout(900)
        # After the first screen, a change of level is said as before.
        assert page.get_by_test_id("notice-line").count() == 1
    finally:
        page.close()


def card_height(browser, overlay: str, backend: Backend, stages, step, level: int) -> int:  # noqa: F811
    """The step card's height with the level set before the first screen."""
    page = show(browser, overlay, backend, [
        ("task.started", {"goal": GOAL, "estimated_steps": 9, "stages": stages}),
        ("load.updated", {"score": 0.9 if level == 3 else 0.5, "level": level, "reason": "set"}),
        ("state.changed", {"state": "waiting"}),
        ("step.presented", step),
        (AWAIT_RESPONSE, {}),
    ], SIZES["100%"])
    try:
        assert level_on_screen(page) == level
        return page.evaluate("Math.round(document.querySelector("
                             "'[data-testid=step-shell]').getBoundingClientRect().height)")
    finally:
        page.close()


@pytest.mark.parametrize("name", list(FIRST), ids=list(FIRST))
def test_level_3_is_never_taller_than_level_2(
    browser, overlay: str, backend: Backend, name: str  # noqa: F811
) -> None:
    """Simplifying must never make a step taller (`test_levels.py`). When the
    answers first shared a row at level 2 (2026-10-14), level 3 kept the
    column: "What day are you travelling?" was 107px taller at level 3."""
    stages, step = FIRST[name]
    two = card_height(browser, overlay, backend, stages, step, 2)
    three = card_height(browser, overlay, backend, stages, step, 3)
    assert three <= two, (name, two, three)


def test_an_empty_box_looks_ready_to_type_in(
    browser, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """On the sunk colour, darker than the card, an empty box read as switched
    off (2026-10-15). Its own light fill, a 2px edge, and a 3px ring once it
    has the cursor."""
    stages, step = FIRST["reference"]
    page = show(browser, overlay, backend, [
        ("task.started", {"goal": GOAL, "estimated_steps": 9, "stages": stages}),
        ("state.changed", {"state": "waiting"}),
        ("step.presented", step),
        (AWAIT_RESPONSE, {}),
    ], SIZES["100%"])
    try:
        box = page.get_by_role("textbox", name="Reference number")
        look = """el => { const s = getComputedStyle(el); return {
            fill: s.backgroundColor, card: getComputedStyle(
              el.closest('[data-testid=step-shell]')).backgroundColor,
            edge: s.borderTopWidth, ring: s.outlineWidth, ringStyle: s.outlineStyle}; }"""
        before = box.evaluate(look)
        assert before["fill"] == "rgb(255, 255, 255)", before
        assert before["edge"] == "2px", before
        box.click()
        after = box.evaluate(look)
        assert after["ring"] == "3px" and after["ringStyle"] == "solid", after
    finally:
        page.close()
