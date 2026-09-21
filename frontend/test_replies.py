"""What the person sees when a goal starts nothing — and that it is never a dead end.

The overlay built from source, against the real mock backend, routing by
keywords. The five goals the routing was built for, typed into the real home
screen; and for the three that start nothing, the choice offered is pressed
and has to run the right flow.
"""

import os
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator

import pytest
from playwright.sync_api import Page, Playwright

from frontend.test_terminal_states import overlay  # noqa: F401 - the built overlay

REPO = __import__("pathlib").Path(__file__).resolve().parents[1]
PORT = 8032

GREETING = "Hello. Here's what I can help with."
CANNOT = "I can't do that yet."
WHICH = "Which of these did you mean?"


@pytest.fixture(scope="module")
def mock() -> Iterator[str]:
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "tools.mock_backend:app", "--port", str(PORT)],
        cwd=REPO, env={**os.environ, "SIMBA_ROUTER": "keywords"},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=1)
            break
        except OSError:
            time.sleep(0.2)
    try:
        yield f"ws://127.0.0.1:{PORT}/ws"
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture
def page(playwright_instance: Playwright) -> Iterator[Page]:
    browser = playwright_instance.chromium.launch()
    yield browser.new_page(viewport={"width": 1280, "height": 800})
    browser.close()


def ask(page: Page, overlay: str, mock: str, goal: str) -> None:  # noqa: F811
    """Type a goal into the home screen, the way a person would.

    The box is always on the home screen since 2026-09-21. It used to hide
    behind "Ask for something new" whenever there was history, and this
    helper had to wait for that button to be deterministic.
    """
    page.goto(f"{overlay}?ws={mock}")
    box = page.get_by_role("textbox", name="What would you like me to do?")
    box.fill(goal, timeout=10000)
    page.keyboard.press("Enter")


def arrived(page: Page, text: str) -> None:
    """The reply is on screen and the screen before it has finished leaving.

    The crossfade holds both for 0.3s, and the home screen can offer the same
    goals as history — so a check inside that window sees two of each card.
    """
    page.get_by_text(text).wait_for(timeout=8000)
    page.wait_for_timeout(700)


def test_hello_is_greeted_with_what_i_can_do(page: Page, overlay: str, mock: str) -> None:  # noqa: F811
    ask(page, overlay, mock, "hello")

    arrived(page, GREETING)
    for card in ("Register for CS-401", "Check my electricity bill",
                 "Find trains from Lahore to Karachi"):
        assert page.get_by_role("button", name=card).is_visible(), card
    # And nothing is running.
    assert not page.get_by_text("Give me a moment.").is_visible()


def test_a_card_after_hello_runs_that_flow(page: Page, overlay: str, mock: str) -> None:  # noqa: F811
    ask(page, overlay, mock, "hello")
    arrived(page, GREETING)
    page.get_by_role("button", name="Check my electricity bill").click()

    page.wait_for_selector("[data-testid=step-shell]", timeout=10000)
    assert page.get_by_role("button", name="Accept cookies").is_visible()


def test_pay_my_bill_goes_straight_to_the_bill(page: Page, overlay: str, mock: str) -> None:  # noqa: F811
    ask(page, overlay, mock, "pay my bill")

    page.wait_for_selector("[data-testid=step-shell]", timeout=10000)
    assert page.get_by_role("button", name="Accept cookies").is_visible()


def test_trains_to_karachi_goes_straight_to_the_trains(
    page: Page, overlay: str, mock: str  # noqa: F811
) -> None:
    ask(page, overlay, mock, "trains to Karachi")

    page.wait_for_selector("[data-testid=step-shell]", timeout=10000)
    assert page.get_by_role("button", name="Set the departure station").is_visible()


def test_book_a_flight_says_so_and_shows_what_i_can_do(
    page: Page, overlay: str, mock: str  # noqa: F811
) -> None:
    ask(page, overlay, mock, "book a flight")

    arrived(page, CANNOT)
    assert page.get_by_text("book a flight").is_visible(), "their words are echoed back"
    assert page.get_by_role("button", name="Register for CS-401").is_visible()


def test_something_ambiguous_asks_and_the_answer_runs(
    page: Page, overlay: str, mock: str  # noqa: F811
) -> None:
    ask(page, overlay, mock, "I need to pay for my course")

    arrived(page, WHICH)
    assert page.get_by_role("button", name="The course registration").is_visible()
    page.get_by_role("button", name="The electricity bill").click()

    page.wait_for_selector("[data-testid=step-shell]", timeout=10000)
    assert page.get_by_role("button", name="Accept cookies").is_visible()
