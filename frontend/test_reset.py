"""Forgetting the person, for the next one (2026-10-18).

In "Change my settings" — never on a first open, where there is nothing to
forget — "Forget me and start again" asks once, plainly, and then clears the
person's profile on this computer and has the backend clear their own tiles,
and opens the welcome as on a first open. For a study between sessions, and
for handing the laptop to someone new.
"""

import json
from collections.abc import Iterator

import pytest
from playwright.sync_api import Page

from frontend.test_home import browser  # noqa: F401 - fixture
from frontend.test_own_tiles import MINE, Tiles
from frontend.test_terminal_states import overlay  # noqa: F401 - fixture

PROFILE = {"name": "Ayesha", "level": 3, "readAloud": False, "askEach": True,
           "welcomed": True}


@pytest.fixture
def backend() -> Tiles:
    return Tiles()


@pytest.fixture
def pages(browser) -> Iterator[list]:  # noqa: F811
    opened: list = []
    yield opened
    for page in opened:
        page.context.close()


def a_known_person(browser, overlay: str, backend: Tiles, pages: list) -> Page:  # noqa: F811
    backend.tiles = [dict(t) for t in MINE]
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    context.add_init_script(
        "window.__simbaWelcome = true; window.__simbaSettleMs = 0;"
        f"if (!sessionStorage.getItem('seeded')) {{"
        f" localStorage.setItem('simba.profile', {json.dumps(json.dumps(PROFILE))});"
        f" sessionStorage.setItem('seeded', '1'); }}")
    page = context.new_page()
    pages.append(page)
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    page.get_by_test_id("own-tile").first.wait_for(timeout=15000)
    return page


def saved(page: Page) -> dict | None:
    raw = page.evaluate("() => localStorage.getItem('simba.profile')")
    return json.loads(raw) if raw else None


def test_saying_no_changes_nothing(
    browser, overlay: str, backend: Tiles, pages: list  # noqa: F811
) -> None:
    page = a_known_person(browser, overlay, backend, pages)
    page.get_by_test_id("change-settings").click()
    page.get_by_test_id("forget").click()
    assert page.get_by_role("heading", level=1).inner_text() == (
        "Shall I forget everything about you?")
    page.get_by_test_id("forget-no").click()

    assert page.get_by_role("textbox").input_value() == "Ayesha"
    assert saved(page) == PROFILE
    assert backend.sent("tile.change") == []


def test_forgetting_clears_the_profile_and_the_tiles_and_starts_again(
    browser, overlay: str, backend: Tiles, pages: list  # noqa: F811
) -> None:
    page = a_known_person(browser, overlay, backend, pages)
    assert "Ayesha" in page.get_by_test_id("greeting").inner_text()

    page.get_by_test_id("change-settings").click()
    page.get_by_test_id("forget").click()
    page.get_by_test_id("forget-yes").click()
    page.wait_for_timeout(500)

    assert backend.sent("tile.change") == [{"action": "clear"}]
    assert saved(page) is None
    # The welcome, as on a first open: the name asked for again, empty, and
    # nothing to forget any more.
    welcome = page.get_by_test_id("welcome")
    assert welcome.get_attribute("data-question") == "name"
    assert page.get_by_role("textbox").input_value() == ""
    assert page.get_by_test_id("forget").count() == 0

    for _ in range(4):
        page.get_by_test_id("welcome-skip").click()
        page.wait_for_timeout(250)
    greeting = page.get_by_test_id("greeting").inner_text()
    assert "Ayesha" not in greeting and greeting.endswith("Where do you want to go?")
    assert page.get_by_test_id("own-tiles").count() == 0
    assert page.get_by_test_id("can-help").is_visible()
    # And the read-aloud button is back for the next person, as by default.
    assert saved(page) == {"readAloud": True, "askEach": False, "welcomed": True}


def test_a_first_open_has_nothing_to_forget(
    browser, overlay: str, backend: Tiles, pages: list  # noqa: F811
) -> None:
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    context.add_init_script("window.__simbaWelcome = true; window.__simbaSettleMs = 0")
    page = context.new_page()
    pages.append(page)
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    page.get_by_test_id("welcome").wait_for(timeout=15000)

    assert page.get_by_test_id("forget").count() == 0
