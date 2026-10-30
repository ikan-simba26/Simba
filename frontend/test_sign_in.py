"""Signing in: saving the password is a box to tick (2026-10-15).

Until then the backend's offer to keep the password was a second button,
"Sign in and save my password", under "Sign in" and over "Stop this": three
buttons, and at 100% the screen ran 96px past the window even at its most
compact (EVALUATION.md, 2026-10-14b). Raham chose a checkbox. The contract
does not change: "Sign in" sends the offer's own id, `remember`, when the box
is ticked, and `confirm` when it is not.
"""

import pytest
from playwright.sync_api import Page

from frontend.test_first_screen import (  # noqa: F401
    SIZES, browser, level_on_screen, question, show)
from frontend.test_terminal_states import AWAIT_RESPONSE, Backend, overlay  # noqa: F401

STAGES = ["Sign in", "Course", "Register", "Done"]
SIGN_IN = {**question("Let me sign you in first.", [
    {"id": "confirm", "label": "Sign in", "kind": "primary"},
    {"id": "remember", "label": "Sign in and save my password", "kind": "primary"},
    {"id": "cancel", "label": "Stop this", "kind": "secondary"}],
    [{"id": "username", "label": "Student ID or Username", "type": "text", "value": ""},
     {"id": "password", "label": "Password", "type": "password", "value": ""}],
    # As the backend sends it: a step with boxes to type in is "type".
    detail="Fictional State University student portal.", kind="type", stage=0),
    "step_index": 1}
FIRST = question("Which course would you like to register for?", [
    {"id": "confirm", "label": "Use this course", "kind": "primary"},
    {"id": "cancel", "label": "Stop this", "kind": "secondary"}],
    [{"id": "course", "label": "Course", "type": "text", "value": ""}], kind="type")


@pytest.fixture(scope="module")
def backend() -> Backend:
    return Backend()


def signing_in(browser, overlay: str, backend: Backend, size: str) -> Page:  # noqa: F811
    """The sign-in screen, first, as in the flow since 2026-10-16: which course
    is asked after it, from the portal's own list."""
    width, height, scale = SIZES[size]
    page = browser.new_page(viewport={"width": width, "height": height},
                            device_scale_factor=scale)
    backend.script = [
        ("task.started", {"goal": "course", "estimated_steps": 4, "stages": STAGES}),
        ("state.changed", {"state": "waiting"}), ("step.presented", SIGN_IN),
        (AWAIT_RESPONSE, {}),
    ]
    backend.responses.clear()
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    page.fill("input[aria-label='What would you like me to do?']", "course")
    page.get_by_role("button", name="Start").click()
    page.get_by_text("Let me sign you in first.").first.wait_for(timeout=10000)
    page.wait_for_timeout(1800)  # past the guard
    return page


def sent(backend: Backend) -> list[dict]:
    return [m["payload"] for m in backend.responses if m.get("type") == "step.response"]


def test_saving_is_a_box_to_tick_not_a_button(browser, overlay: str,  # noqa: F811
                                               backend: Backend) -> None:
    page = signing_in(browser, overlay, backend, "100%")
    try:
        assert page.get_by_role("checkbox", name="Save my password for next time").count() == 1
        assert page.get_by_role("button", name="Sign in and save my password").count() == 0
        buttons = page.eval_on_selector_all(
            "[data-testid=step-shell] button",
            "bs => bs.filter(b => b.offsetParent && !b.closest('[data-testid=top-line]'))"
            ".map(b => b.innerText.trim())")
        assert buttons == ["Sign in", "Stop this"], buttons
    finally:
        page.close()


@pytest.mark.parametrize("ticked, action", [(False, "confirm"), (True, "remember")],
                         ids=["unticked", "ticked"])
def test_sign_in_says_whether_to_keep_the_password(browser, overlay: str,  # noqa: F811
                                                   backend: Backend, ticked: bool,
                                                   action: str) -> None:
    page = signing_in(browser, overlay, backend, "100%")
    try:
        page.get_by_role("textbox", name="Student ID or Username").fill("student")
        page.get_by_label("Password", exact=True).fill("secret")
        if ticked:
            page.get_by_role("checkbox", name="Save my password for next time").check()
        page.get_by_role("button", name="Sign in", exact=True).click()
        page.wait_for_timeout(600)
        answer = sent(backend)[-1]
        assert answer["step_index"] == 1
        assert answer["action_id"] == action
        assert answer["input_values"] == {"username": "student", "password": "secret"}
    finally:
        page.close()


@pytest.mark.parametrize("size", list(SIZES), ids=list(SIZES))
def test_the_sign_in_screen_fits(browser, overlay: str, backend: Backend,  # noqa: F811
                                 size: str) -> None:
    """It ran 96px past the window at 100% and 91px at 150% with three
    buttons; `main` was 56px and 60px over."""
    page = signing_in(browser, overlay, backend, size)
    try:
        over = page.evaluate("document.scrollingElement.scrollHeight - innerHeight")
        level = level_on_screen(page)
        print(f"sign-in first screen {size}: level {level}, over {over}")
        assert over <= 0, (size, over)
    finally:
        page.close()


@pytest.mark.parametrize("size", list(SIZES), ids=list(SIZES))
def test_the_sign_in_screen_fits_when_the_page_starts_it_at_level_3(
        browser, overlay: str, backend: Backend, size: str) -> None:  # noqa: F811
    """The trained estimator scores the portal's sign-in page heavy, so the
    task starts at level 3 (2026-10-30). The guard moves one level per step
    and then lets a page scroll, so a screen that needed two hops would not
    fit from there."""
    width, height, scale = SIZES[size]
    page = browser.new_page(viewport={"width": width, "height": height},
                            device_scale_factor=scale)
    backend.script = [
        ("task.started", {"goal": "course", "estimated_steps": 4, "stages": STAGES}),
        ("load.updated", {"score": 0.63, "level": 3, "reason": "3.5 of 5"}),
        ("state.changed", {"state": "waiting"}), ("step.presented", SIGN_IN),
        (AWAIT_RESPONSE, {}),
    ]
    backend.responses.clear()
    try:
        page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
        page.fill("input[aria-label='What would you like me to do?']", "course")
        page.get_by_role("button", name="Start").click()
        page.get_by_text("Let me sign you in first.").first.wait_for(timeout=10000)
        page.wait_for_timeout(1800)  # past the guard
        over = page.evaluate("document.scrollingElement.scrollHeight - innerHeight")
        level = level_on_screen(page)
        print(f"sign-in from level 3, {size}: level {level}, over {over}")
        assert over <= 0, (size, level, over)
        assert page.locator("input[type='password']").count() == 1
        assert page.locator("input[type='text']").count() >= 1
    finally:
        page.close()
