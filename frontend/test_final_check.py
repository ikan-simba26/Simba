"""The final screen, in a real browser (2026-10-16).

The one step before SIMBA books, pays, registers or changes a record
(CLAUDE.md, the final-step rule): what will happen in plain words, the
details as the page states them, and two answers — do it, don't — with no
default and nothing moving on by itself. These check that the two answers
look exactly alike, that nothing has focus when it arrives, that every
detail shows at every level, that it fits at every size, and that "don't"
sends what the backend ends the task on.
"""

import pytest
from playwright.sync_api import Page

from frontend.test_first_screen import SIZES, browser  # noqa: F401
from frontend.test_terminal_states import AWAIT_RESPONSE, Backend, overlay  # noqa: F401

GOAL = "trains to Karachi tomorrow"
STAGES = ["From", "To", "Day", "Search", "Trains", "Book"]

#: The booking's final screen, the fullest: eight details from the page.
BOOKING = {
    "step_index": 9, "step_total": 9, "stage": 5, "step_kind": "confirm",
    "instruction": "I'll book one seat on 13UP for you, with these details.",
    "detail": "Nothing happens until you choose.",
    "fields": [], "requires_confirmation": True, "findings": [],
    "actions": [{"id": "confirm", "label": "Book it", "kind": "primary"},
                {"id": "decline", "label": "Don't book it", "kind": "primary"}],
    "final": [{"label": "Train", "value": "13UP"},
              {"label": "From", "value": "Lahore Cantt"},
              {"label": "To", "value": "Karachi Cantt"},
              {"label": "Date", "value": "17 October 2026"},
              {"label": "Leaves", "value": "07:25"},
              {"label": "Passenger", "value": "Ayesha Siddiqa Rahman"},
              {"label": "Class", "value": "AC Standard"},
              {"label": "Fare", "value": "Rs 3,250"}],
}


@pytest.fixture(scope="module")
def backend() -> Backend:
    return Backend()


def final(browser, overlay: str, backend: Backend, size: str,  # noqa: F811
          level: int | None = None) -> Page:
    width, height, scale = SIZES[size]
    page = browser.new_page(viewport={"width": width, "height": height},
                            device_scale_factor=scale)
    script = [("task.started", {"goal": GOAL, "estimated_steps": 9, "stages": STAGES})]
    if level is not None:
        script.append(("load.updated", {"score": 0.5, "level": level, "reason": "test"}))
    backend.script = [*script, ("state.changed", {"state": "waiting"}),
                      ("step.presented", BOOKING), (AWAIT_RESPONSE, {})]
    backend.responses.clear()
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    page.fill("input[aria-label='What would you like me to do?']", GOAL)
    page.get_by_role("button", name="Start").click()
    page.get_by_test_id("final-check").wait_for(timeout=15000)
    page.wait_for_timeout(1500)
    return page


def test_the_two_answers_look_exactly_alike(browser, overlay: str,  # noqa: F811
                                            backend: Backend) -> None:
    page = final(browser, overlay, backend, "100%")
    try:
        page.mouse.move(5, 5)  # off both: a hover is not a default
        page.wait_for_timeout(400)
        answers = page.get_by_test_id("final-answers").get_by_role("button")
        assert answers.all_inner_texts() == ["Book it", "Don't book it"]
        looks = page.evaluate("""() => [...document.querySelectorAll(
            '[data-testid=final-answers] button')].map(b => {
              const s = getComputedStyle(b), r = b.getBoundingClientRect();
              return [b.className, s.backgroundColor, s.color, s.fontWeight,
                      Math.round(r.width), Math.round(r.height)]; })""")
        assert looks[0] == looks[1], looks
        # Nothing chosen for them: no focus on arrival, and no way to stop
        # but "don't".
        assert page.evaluate("document.activeElement === document.body")
        assert page.get_by_role("button", name="Stop this").count() == 0
    finally:
        page.close()


def test_nothing_moves_on_by_itself(browser, overlay: str, backend: Backend) -> None:  # noqa: F811
    page = final(browser, overlay, backend, "100%")
    try:
        page.wait_for_timeout(6000)
        assert [m for m in backend.responses if m.get("type") == "step.response"] == []
        assert page.get_by_test_id("final-check").is_visible()
    finally:
        page.close()


@pytest.mark.parametrize("level", [1, 3])
def test_every_detail_shows_at_every_level(browser, overlay: str, backend: Backend,  # noqa: F811
                                           level: int) -> None:
    page = final(browser, overlay, backend, "100%", level)
    try:
        shown = page.get_by_test_id("final-details").inner_text()
        for detail in BOOKING["final"]:
            assert detail["label"] in shown and detail["value"] in shown, (level, detail)
        assert page.get_by_text(BOOKING["instruction"]).is_visible()
    finally:
        page.close()


@pytest.mark.parametrize("size", list(SIZES), ids=list(SIZES))
def test_the_final_screen_fits(browser, overlay: str, backend: Backend,  # noqa: F811
                               size: str) -> None:
    page = final(browser, overlay, backend, size)
    try:
        height = SIZES[size][1]
        for name in ("Book it", "Don't book it", "What are you doing?"):
            box = page.get_by_role("button", name=name, exact=True).bounding_box()
            assert box and box["y"] + box["height"] <= height, (size, name, box)
        over = page.evaluate("document.scrollingElement.scrollHeight - innerHeight")
        assert over <= 0, (size, over)
    finally:
        page.close()


@pytest.mark.parametrize("label, action", [("Book it", "confirm"),
                                           ("Don't book it", "decline")])
def test_each_answer_says_which(browser, overlay: str, backend: Backend,  # noqa: F811
                                label: str, action: str) -> None:
    page = final(browser, overlay, backend, "100%")
    try:
        page.get_by_role("button", name=label, exact=True).click()
        page.wait_for_timeout(600)
        sent = [m["payload"] for m in backend.responses if m.get("type") == "step.response"]
        assert sent and sent[-1]["action_id"] == action and sent[-1]["step_index"] == 9
    finally:
        page.close()
