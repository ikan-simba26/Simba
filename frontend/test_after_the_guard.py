"""The level a screen goes back to after the overflow guard moved the one before.

The guard moves a screen that does not fit straight to the compact level 1, and
that move is for that screen. CONTRACT.md has said since 2026-09-25 that the
next step is shown at the person's own level again; only a locked level ever
did (`store.ts`). Unlocked, a heavy task's sign-in at 100% and 150% pulled the
level from 3 to 1, and every screen after it stayed at the densest level, on
the very page the trained estimator had said to keep simple (2026-11-01).

Two ways. Scripted, against the overlay alone, for what the screen does around
it. And the real thing: the built overlay, the real backend and the registration
replica, at 100% and at both 150% windows, past the real sign-in.
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Page, Playwright

from frontend.test_first_screen import (  # noqa: F401
    SIZES, browser, level_on_screen, question, show)
from frontend.test_sign_in import SIGN_IN, STAGES
from frontend.test_terminal_states import AWAIT_RESPONSE, Backend, overlay  # noqa: F401

REPO = Path(__file__).resolve().parents[1]
REPLICA_PORT = 5011
APP_PORT = 8041
#: The two screens the measured windows force the guard on, and the one that
#: fits at the level the estimator chose (`test_sign_in.py`).
TOO_SHORT = ["100%", "150%, 632", "150%, 606"]
FITTED_NOTICE = "I've made this smaller so it fits."

NEXT = {**question("Which course would you like to register for?", [
    {"id": "confirm", "label": "Use this course", "kind": "primary"},
    {"id": "cancel", "label": "Stop this", "kind": "secondary"}],
    [{"id": "course", "label": "Course", "type": "text", "value": ""}], kind="type", stage=1),
    "step_index": 2}
THIRD = {**question("Shall I carry on?", [
    {"id": "confirm", "label": "Carry on", "kind": "primary"},
    {"id": "cancel", "label": "Stop this", "kind": "secondary"}], kind="confirm", stage=2),
    "step_index": 3}


@pytest.fixture(scope="module")
def backend() -> Backend:
    return Backend()


def tall(step_index: int) -> dict:
    """A step that does not fit at level 3 at any of the sizes: the sign-in's
    two boxes and three buttons, on a later screen, where a notice can show."""
    return {**SIGN_IN, "step_index": step_index}


def scripted(browser, overlay: str, backend: Backend, size: str,  # noqa: F811
             script: list[tuple[str, dict]]) -> Page:
    return show(browser, overlay, backend, [
        ("task.started", {"goal": "train", "estimated_steps": 4, "stages": STAGES}),
        *script], SIZES[size])


def answer(page: Page, label: str) -> None:
    page.get_by_role("button", name=label, exact=True).first.click()


def with_boxes_filled(page: Page) -> None:
    page.get_by_label("Student ID or Username").fill("student")
    page.locator("input[type='password']").fill("anything")


@pytest.mark.parametrize("size", TOO_SHORT, ids=TOO_SHORT)
def test_the_next_screen_goes_back_to_the_level_before_the_guard(
        browser, overlay: str, backend: Backend, size: str) -> None:  # noqa: F811
    page = scripted(browser, overlay, backend, size, [
        ("load.updated", {"score": 0.6, "level": 3, "reason": "heavy page"}),
        ("state.changed", {"state": "waiting"}), ("step.presented", SIGN_IN),
        (AWAIT_RESPONSE, {}),
        ("state.changed", {"state": "waiting"}), ("step.presented", NEXT),
        (AWAIT_RESPONSE, {}),
    ])
    try:
        assert level_on_screen(page) == 1  # the guard, for this screen
        with_boxes_filled(page)
        answer(page, "Sign in")
        page.get_by_text("Which course would you like").first.wait_for(timeout=10000)
        page.wait_for_timeout(1500)  # past the guard's measure of the new screen
        assert level_on_screen(page) == 3, size
        assert page.get_by_text(FITTED_NOTICE).count() == 0
    finally:
        page.close()


def test_a_screen_that_does_not_fit_either_gets_its_own_hop_and_the_next_comes_back(
        browser, overlay: str, backend: Backend) -> None:  # noqa: F811
    page = scripted(browser, overlay, backend, "150%, 606", [
        ("load.updated", {"score": 0.6, "level": 3, "reason": "heavy page"}),
        ("state.changed", {"state": "waiting"}), ("step.presented", SIGN_IN),
        (AWAIT_RESPONSE, {}),
        ("state.changed", {"state": "waiting"}), ("step.presented", tall(2)),
        (AWAIT_RESPONSE, {}),
        ("state.changed", {"state": "waiting"}), ("step.presented", NEXT),
        (AWAIT_RESPONSE, {}),
    ])
    try:
        with_boxes_filled(page)
        answer(page, "Sign in")
        page.wait_for_timeout(1500)
        assert level_on_screen(page) == 1  # its own hop, from 3 again
        assert page.get_by_text(FITTED_NOTICE).count() == 1
        with_boxes_filled(page)
        answer(page, "Sign in")
        page.get_by_text("Which course would you like").first.wait_for(timeout=10000)
        page.wait_for_timeout(1500)
        assert level_on_screen(page) == 3
        # Said of the screen before: not true of this one.
        assert page.get_by_text(FITTED_NOTICE).count() == 0
    finally:
        page.close()


def test_a_move_from_the_rules_after_the_hop_wins_and_is_said_from_where_it_was(
        browser, overlay: str, backend: Backend) -> None:  # noqa: F811
    """Two calm steps bring a heavy start back a level as the next step
    arrives: the rules speak first, and the step that follows must not undo it."""
    page = scripted(browser, overlay, backend, "150%, 606", [
        ("load.updated", {"score": 0.6, "level": 3, "reason": "heavy page"}),
        ("state.changed", {"state": "waiting"}), ("step.presented", SIGN_IN),
        (AWAIT_RESPONSE, {}),
        ("load.updated", {"score": 0.3, "level": 2, "reason": "2 calm steps in a row"}),
        ("state.changed", {"state": "waiting"}), ("step.presented", NEXT),
        (AWAIT_RESPONSE, {}),
    ])
    try:
        with_boxes_filled(page)
        answer(page, "Sign in")
        page.get_by_text("Which course would you like").first.wait_for(timeout=10000)
        page.wait_for_timeout(1500)
        assert level_on_screen(page) == 2
    finally:
        page.close()


def test_a_lock_still_holds_the_persons_own_level_after_the_hop(
        browser, overlay: str, backend: Backend) -> None:  # noqa: F811
    page = scripted(browser, overlay, backend, "150%, 606", [
        ("state.changed", {"state": "waiting"}), ("step.presented", SIGN_IN),
        (AWAIT_RESPONSE, {}),
        ("state.changed", {"state": "waiting"}), ("step.presented", NEXT),
        (AWAIT_RESPONSE, {}),
    ])
    try:
        page.get_by_role("button", name="Show less").click()  # locks at 3
        page.wait_for_timeout(600)
        with_boxes_filled(page)
        answer(page, "Sign in")
        page.get_by_text("Which course would you like").first.wait_for(timeout=10000)
        page.wait_for_timeout(1500)
        assert level_on_screen(page) == 3
    finally:
        page.close()


def test_a_level_the_person_picks_after_the_hop_is_kept(
        browser, overlay: str, backend: Backend) -> None:  # noqa: F811
    """Their choice replaces what the guard was going to hand back."""
    page = scripted(browser, overlay, backend, "150%, 606", [
        ("load.updated", {"score": 0.6, "level": 3, "reason": "heavy page"}),
        ("state.changed", {"state": "waiting"}), ("step.presented", SIGN_IN),
        (AWAIT_RESPONSE, {}),
        ("state.changed", {"state": "waiting"}), ("step.presented", NEXT),
        (AWAIT_RESPONSE, {}),
    ])
    try:
        page.get_by_role("button", name="Show the usual amount").click()
        page.wait_for_timeout(600)
        page.get_by_role("button", name="Show more").click()
        page.wait_for_timeout(600)
        with_boxes_filled(page)
        answer(page, "Sign in")
        page.get_by_text("Which course would you like").first.wait_for(timeout=10000)
        page.wait_for_timeout(1500)
        assert level_on_screen(page) == 1
    finally:
        page.close()


# --- the real thing ------------------------------------------------------------------


def wait_for(url: str) -> None:
    deadline = time.time() + 40
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except OSError:
            time.sleep(0.2)
    raise TimeoutError(url)


@pytest.fixture(scope="module")
def registration() -> Iterator[str]:
    """The registration replica and the real backend with the trained model."""
    replica = subprocess.Popen(
        [sys.executable, "app.py"], cwd=REPO / "replicas" / "registration",
        env={**os.environ, "PORT": str(REPLICA_PORT)},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    app = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.orchestrator.app:app",
         "--port", str(APP_PORT)], cwd=REPO,
        env={**os.environ, "SIMBA_ROUTER": "keywords", "SIMBA_USE_HARDCODED_PLAN": "1",
             "SIMBA_REGISTRATION_URL": f"http://127.0.0.1:{REPLICA_PORT}",
             "SIMBA_RECORD_STEPS": "0", "SIMBA_FLOW": "", "SIMBA_LOG_FILE": ""},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_for(f"http://127.0.0.1:{REPLICA_PORT}/")
        wait_for(f"http://127.0.0.1:{APP_PORT}/")
        yield f"ws://127.0.0.1:{APP_PORT}/ws"
    finally:
        for process in (app, replica):
            process.terminate()
            process.wait(timeout=10)


@pytest.mark.parametrize("size", TOO_SHORT, ids=TOO_SHORT)
def test_registration_after_sign_in_comes_back_to_the_models_level(
        playwright_instance: Playwright, overlay: str, registration: str,  # noqa: F811
        size: str) -> None:
    """Through the real flow, with nobody having said a level: the model starts
    the portal's page at 3, the guard moves the sign-in to 1 to fit, and the
    next question goes back to 3, with nothing past the window."""
    width, height, scale = SIZES[size]
    browser = playwright_instance.chromium.launch()
    page = browser.new_page(viewport={"width": width, "height": height},
                            device_scale_factor=scale)
    moves: list[dict] = []

    def heard(frame: str | bytes) -> None:
        message = json.loads(frame)
        if message.get("type") == "level.override":
            moves.append(message["payload"])

    page.on("websocket", lambda socket: socket.on("framesent", heard))
    try:
        page.goto(f"{overlay}?ws={registration}")
        box = page.get_by_role("textbox", name="What would you like me to do?")
        box.fill("Register for a course", timeout=10000)
        page.keyboard.press("Enter")
        page.get_by_text("Let me sign you in first.").first.wait_for(timeout=30000)
        page.wait_for_timeout(1800)  # past the guard
        assert level_on_screen(page) == 1, size
        assert page.evaluate("document.scrollingElement.scrollHeight - innerHeight") <= 0

        with_boxes_filled(page)
        answer(page, "Sign in")
        page.get_by_text("Which course").first.wait_for(timeout=60000)
        page.wait_for_timeout(1800)
        print(f"after sign-in {size}: level {level_on_screen(page)}, "
              f"over {page.evaluate('document.scrollingElement.scrollHeight - innerHeight')}, "
              f"moves {moves}, notice {page.get_by_text(FITTED_NOTICE).count()}")
        assert page.evaluate("document.scrollingElement.scrollHeight - innerHeight") <= 0
        if size == "150%, 606":
            # The shortest window: the question went back to 3, did not fit
            # there, and took its own hop. The second move is the proof that
            # it went back: from 1 there would have been nothing to hop from.
            assert [move["by"] for move in moves] == ["overflow", "overflow"]
            assert level_on_screen(page) == 1
            assert page.get_by_text(FITTED_NOTICE).count() == 1
        else:
            assert [move["by"] for move in moves] == ["overflow"], moves
            assert level_on_screen(page) == 3, size
            assert page.get_by_text(FITTED_NOTICE).count() == 0
    finally:
        browser.close()
