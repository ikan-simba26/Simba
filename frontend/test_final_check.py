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


#: The registration's and the payment's, as the backend sends them.
REGISTERING = {**BOOKING, "stage": 2,
               "instruction": "I'll register you for CS-401, with these details.",
               "actions": [{"id": "confirm", "label": "Register", "kind": "primary"},
                           {"id": "decline", "label": "Don't register", "kind": "primary"}],
               "final": [{"label": "Course", "value": "CS-401"},
                         {"label": "Title", "value": "Advanced Widget Design"},
                         {"label": "Days", "value": "MWF"},
                         {"label": "Time", "value": "10:00-10:50"},
                         {"label": "Teacher", "value": "Dr. Aslam"},
                         {"label": "Room", "value": "SCI 214"},
                         {"label": "Credit hours", "value": "3"}]}
PAYING = {**BOOKING, "stage": 3,
          "instruction": ("I'll pay this bill for you. It is a practice payment, and no card "
                          "is used."),
          "actions": [{"id": "confirm", "label": "Pay it", "kind": "primary"},
                      {"id": "decline", "label": "Don't pay", "kind": "primary"}],
          "final": [{"label": "Amount", "value": "Rs 14,382"},
                    {"label": "Bill", "value": "AUG 2026"},
                    {"label": "Due", "value": "15 September 2026"},
                    {"label": "Reference number", "value": "04141234567890"}]}
SCREENS = {"booking": BOOKING, "registration": REGISTERING, "payment": PAYING}


@pytest.fixture(scope="module")
def backend() -> Backend:
    return Backend()


def final(browser, overlay: str, backend: Backend, size: str,  # noqa: F811
          level: int | None = None, step: dict = BOOKING) -> Page:
    width, height, scale = SIZES[size]
    page = browser.new_page(viewport={"width": width, "height": height},
                            device_scale_factor=scale)
    script = [("task.started", {"goal": GOAL, "estimated_steps": 9, "stages": STAGES})]
    if level is not None:
        script.append(("load.updated", {"score": 0.5, "level": level, "reason": "test"}))
    backend.script = [*script, ("state.changed", {"state": "waiting"}),
                      ("step.presented", step), (AWAIT_RESPONSE, {})]
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


@pytest.mark.parametrize("screen", list(SCREENS))
@pytest.mark.parametrize("size", list(SIZES), ids=list(SIZES))
def test_the_final_screen_fits(browser, overlay: str, backend: Backend,  # noqa: F811
                               size: str, screen: str) -> None:
    step = SCREENS[screen]
    page = final(browser, overlay, backend, size, step=step)
    try:
        height = SIZES[size][1]
        names = [a["label"] for a in step["actions"]] + ["What are you doing?"]
        for name in names:
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


#: Once the trains are found, on a replica: which to book, or none.
OFFER = {
    "step_index": 7, "step_total": 9, "stage": 5, "step_kind": "choose",
    "instruction": "Would you like to book one of these trains?", "detail": "",
    "fields": [], "requires_confirmation": True,
    "findings": [{"label": "Train", "value": "7UP, 8DN", "values": ["7UP", "8DN"]}],
    "actions": [{"id": "choice:0", "label": "7UP, leaves 07:25", "kind": "primary"},
                {"id": "choice:1", "label": "8DN, leaves 16:35", "kind": "primary"},
                {"id": "decline", "label": "No, just the times", "kind": "primary"},
                {"id": "cancel", "label": "Stop this", "kind": "secondary"}],
}


#: The booking's two questions, as the backend sends them: no findings on
#: the way to a change (2026-10-16).
NAME = {**OFFER, "step_index": 8, "step_kind": "type", "findings": [],
        "instruction": "What name should the ticket be in?",
        "detail": "Type it as it is on your ID card.",
        "fields": [{"id": "passenger", "label": "Name", "type": "text", "value": ""}],
        "actions": [{"id": "confirm", "label": "Use this name", "kind": "primary"},
                    {"id": "cancel", "label": "Stop this", "kind": "secondary"}]}
CLASS = {**OFFER, "step_index": 9, "findings": [],
         "instruction": "Which class would you like?",
         "detail": "These are the classes the booking form offers.",
         "actions": [{"id": "choice:0", "label": "Economy", "kind": "primary"},
                     {"id": "choice:1", "label": "AC Standard", "kind": "primary"},
                     {"id": "choice:2", "label": "AC Business", "kind": "primary"},
                     {"id": "cancel", "label": "Stop this", "kind": "secondary"}]}
QUESTIONS = {"offer": OFFER, "name": NAME, "class": CLASS}


@pytest.mark.parametrize("question", list(QUESTIONS))
@pytest.mark.parametrize("size", list(SIZES), ids=list(SIZES))
def test_the_booking_questions_fit(browser, overlay: str, backend: Backend,  # noqa: F811
                                   size: str, question: str) -> None:
    width, height, scale = SIZES[size]
    page = browser.new_page(viewport={"width": width, "height": height},
                            device_scale_factor=scale)
    step = QUESTIONS[question]
    backend.script = [("task.started", {"goal": GOAL, "estimated_steps": 9, "stages": STAGES}),
                      ("state.changed", {"state": "waiting"}), ("step.presented", step),
                      (AWAIT_RESPONSE, {})]
    try:
        page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
        page.fill("input[aria-label='What would you like me to do?']", GOAL)
        page.get_by_role("button", name="Start").click()
        page.wait_for_selector("[data-testid=step-shell]", timeout=15000)
        page.wait_for_timeout(1800)  # past the guard
        for action in step["actions"]:
            box = page.get_by_role("button", name=action["label"], exact=True).bounding_box()
            assert box and box["y"] + box["height"] <= height, (size, action["label"], box)
        assert page.evaluate("document.scrollingElement.scrollHeight <= innerHeight"), size
    finally:
        page.close()


FIRST = {"step_index": 8, "step_total": 9, "stage": 5, "instruction": "Which class would you like?",
         "detail": "", "fields": [], "requires_confirmation": True, "findings": [],
         "actions": [{"id": "choice:0", "label": "Economy", "kind": "primary"},
                     {"id": "choice:1", "label": "AC Standard", "kind": "primary"},
                     {"id": "cancel", "label": "Stop this", "kind": "secondary"}]}


def test_no_level_notice_is_carried_onto_the_final_screen(browser, overlay: str,  # noqa: F811
                                                          backend: Backend) -> None:
    """A level change just before it — the rules folding the screen before,
    as the guard's "I've made this smaller so it fits." did in the real
    window — is not shown on the final screen, which keeps its own layout
    whatever the level (2026-10-16)."""
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    backend.script = [("task.started", {"goal": GOAL, "estimated_steps": 9, "stages": STAGES}),
                      ("state.changed", {"state": "waiting"}), ("step.presented", FIRST),
                      (AWAIT_RESPONSE, {}),
                      ("load.updated", {"score": 0.8, "level": 3, "reason": "test"}),
                      ("step.presented", BOOKING), (AWAIT_RESPONSE, {})]
    try:
        page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
        page.fill("input[aria-label='What would you like me to do?']", GOAL)
        page.get_by_role("button", name="Start").click()
        page.get_by_role("button", name="AC Standard").click()
        # The screen before fades out beside it: wait until it has gone.
        page.wait_for_function(
            "document.querySelectorAll('[data-testid=final-check]').length === 1",
            timeout=15000)
        page.wait_for_timeout(1200)
        shown = page.get_by_test_id("final-check").inner_text()
        assert "showing less" not in shown and "smaller" not in shown, shown
        # Where the person is shows instead.
        assert "Book" in shown
    finally:
        page.close()
