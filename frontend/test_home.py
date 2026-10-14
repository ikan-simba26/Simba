"""The home screen: a greeting, three tiles, at most two goals asked for before,
and the box always on screen.

Until 2026-09-30 the home screen showed the three things SIMBA can do and then,
under a second heading, up to three goals the person had asked for before: six
cards. At 150% the window's content is 1266x606, and six cards put the text box
below the bottom of it. `test_window_fit.py` never saw this, because the fit
measurement launches the host with no backend, and with no backend there is no
history — so what it measured was always the three-card screen.

Since 2026-10-14 the three things SIMBA can do are three large tiles side by
side, always, and goals asked for before are a short list under them: two at
most, one line each, never one a tile already offers (`App.rememberedGoals`).
The greeting says the time of day; the screen uses the whole height of the
window, the box at the bottom. This builds the overlay from source and renders
it at the sizes the window actually gets — measured in EVALUATION.md,
2026-09-25c, and the 632px window without Electron's menu bar — against a
scripted backend that offers the history, and checks it from outside.

The viewports are the window's content in CSS pixels, with the scale factor to
match, which is how the overlay lays out since the zoom was withdrawn: at
zoom 1, a CSS viewport of 1266x606 is the same layout whatever the device
pixels behind it.
"""

import asyncio
import json
import threading
from collections.abc import Iterator
from datetime import datetime

import pytest
import websockets
from playwright.sync_api import Page, Playwright

from frontend.test_terminal_states import overlay  # noqa: F401 - the built overlay

# The window's content at each display scale (EVALUATION.md, 2026-09-25c).
SIZES = {
    "100%": (1280, 800, 1.0),
    "125%": (1280, 734, 1.25),
    "150%": (1266, 606, 1.5),
    "150%, 632": (1266, 632, 1.5),
}

BOX = "What would you like me to do?"
TILES = {"registration": "Register for a course", "billing": "Check my electricity bill",
         "railways": "Find train times"}

# What the trace store offers since goals are spelled out (details.py): whole
# sentences.
LONG = "Find trains from Lahore Cantt to Rawalpindi on 2026-10-01."
LONGER = "Find the amount due for reference number 04141234567890."


class History:
    """A backend that says hello with these remembered goals, and nothing else."""

    def __init__(self) -> None:
        self.goals: list[dict] = []
        #: Everything the overlay said back.
        self.received: list[dict] = []
        self.port = 0
        started = threading.Event()

        def run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def handler(ws):
                await ws.send(json.dumps({
                    "v": 1, "type": "history.offered", "task_id": "t_home", "seq": 1,
                    "ts": 0, "payload": {"goals": self.goals},
                }))
                try:
                    async for said in ws:
                        self.received.append(json.loads(said))
                except websockets.ConnectionClosed:
                    return

            async def main() -> None:
                server = await websockets.serve(handler, "127.0.0.1", 0)
                self.port = server.sockets[0].getsockname()[1]
                started.set()
                await asyncio.Future()

            loop.run_until_complete(main())

        threading.Thread(target=run, daemon=True).start()
        started.wait(timeout=10)


@pytest.fixture(scope="module")
def history() -> History:
    return History()


@pytest.fixture(scope="module")
def browser(playwright_instance: Playwright):
    browser = playwright_instance.chromium.launch()
    yield browser
    browser.close()


@pytest.fixture
def at() -> Iterator[dict]:
    """Pages opened by a test, closed after it."""
    pages: dict = {}
    yield pages
    for page in pages.values():
        page.close()


def tile_goal(goal: str) -> bool:
    """Whether a remembered goal is one a tile already offers."""
    plain = " ".join(goal.split()).rstrip(".!?").lower()
    return plain in {words.lower() for words in TILES.values()}


def home(browser, overlay: str, history: History, goals: list[str], size: str,  # noqa: F811
         pages: dict, before=None) -> Page:
    width, height, scale = SIZES[size]
    history.goals = [{"goal": goal, "site": "127.0.0.1"} for goal in goals]
    page = browser.new_page(viewport={"width": width, "height": height},
                            device_scale_factor=scale)
    pages[size] = page
    if before:
        before(page)
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{history.port}")
    page.get_by_role("textbox", name=BOX).wait_for(timeout=15000)
    # History arrives after the socket opens. A goal a tile already offers
    # changes nothing on screen, so for that there is nothing to wait for.
    if any(not tile_goal(goal) for goal in goals):
        page.get_by_test_id("remembered").first.wait_for(timeout=10000)
    page.wait_for_timeout(1600)  # past the entrance
    return page


def tiles_on(page: Page) -> list[str]:
    """The tiles' own words, left to right."""
    return [t.inner_text().strip() for t in page.get_by_test_id("tile").all()]


def remembered_on(page: Page) -> list[str]:
    """The goals asked for before, top to bottom."""
    return [r.inner_text().strip() for r in page.get_by_test_id("remembered").all()]


def box_fits(page: Page) -> tuple[bool, dict]:
    box = page.get_by_role("textbox", name=BOX)
    rect = box.bounding_box()
    viewport = page.viewport_size
    button = page.get_by_role("button", name="Start", exact=True).bounding_box()
    scrolls = page.evaluate(
        "() => document.scrollingElement.scrollHeight > window.innerHeight")
    measured = {"box_bottom": round(rect["y"] + rect["height"]),
                "start_bottom": round(button["y"] + button["height"]),
                "height": viewport["height"], "scrolls": scrolls}
    fits = (rect["y"] >= 0 and measured["box_bottom"] <= viewport["height"]
            and measured["start_bottom"] <= viewport["height"] and not scrolls)
    return fits, measured


# --- the box, at every scaling ----------------------------------------------


WORST = [LONGER, LONG, "Register for CS-401"]
# Three bills looked up: every goal a whole sentence.
BILLS = [f"Find the amount due for reference number {n}."
         for n in ("04141234567890", "04149999999999", "04145555555555")]
# Longer than any goal the system writes: more than a line at every size, so
# every remembered goal is held at its one-line limit.
TALLEST = [f"{bill} Then tell me which of them is due first and how much it is." for bill in BILLS]


@pytest.mark.parametrize("size", list(SIZES))
@pytest.mark.parametrize("goals", [[], WORST, BILLS, TALLEST],
                         ids=["no history", "three long goals", "three bills", "three at the limit"])
def test_the_box_is_on_screen_without_scrolling(
    size: str, goals: list[str], browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    """The requirement, at every scaling, with no history and with the longest
    history the store would offer."""
    page = home(browser, overlay, history, goals, size, at)

    fits, measured = box_fits(page)

    assert fits, (size, measured)


@pytest.mark.parametrize("size", list(SIZES))
def test_the_screen_uses_the_whole_height(
    size: str, browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    """The box sits near the bottom of the window, not under the tiles in the
    top half (2026-10-14)."""
    page = home(browser, overlay, history, [], size, at)

    _, measured = box_fits(page)

    assert measured["start_bottom"] >= 0.8 * measured["height"], measured


# --- the tiles ----------------------------------------------------------------


@pytest.mark.parametrize("size", list(SIZES))
def test_three_tiles_side_by_side(
    size: str, browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    page = home(browser, overlay, history, TALLEST, size, at)

    assert tiles_on(page) == list(TILES.values())
    tops = {round(t.bounding_box()["y"]) for t in page.get_by_test_id("tile").all()}
    assert len(tops) == 1, tops
    # Each with its picture.
    assert page.locator("[data-testid=tile] svg").count() == 3


def test_pressing_a_tile_runs_that_flow(
    browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    """The tile's words are the goal, sent with the flow's name so the backend
    runs exactly that rather than guessing."""
    page = home(browser, overlay, history, [], "150%", at)
    history.received.clear()

    page.get_by_test_id("tile").nth(1).click()
    page.wait_for_timeout(800)

    starts = [m["payload"] for m in history.received if m.get("type") == "task.start"]
    assert starts and starts[0]["goal"] == TILES["billing"]
    assert starts[0].get("flow") == "billing"


# --- goals asked for before -------------------------------------------------


def test_with_no_history_nothing_under_the_tiles(
    browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    page = home(browser, overlay, history, [], "150%", at)

    assert remembered_on(page) == []
    assert page.get_by_text("You asked before", exact=True).count() == 0


def test_two_remembered_goals_at_most_most_recent_first(
    browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    page = home(browser, overlay, history, ["Pay my water bill", LONG, LONGER], "150%", at)

    assert remembered_on(page) == ["Pay my water bill", LONG]


def test_a_remembered_goal_a_tile_offers_is_not_shown_again(
    browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    """Whatever its case, spacing or full stop."""
    page = home(browser, overlay, history, ["check my  electricity bill.", LONG], "150%", at)

    assert remembered_on(page) == [LONG]
    assert tiles_on(page) == list(TILES.values())


def test_the_same_goal_remembered_twice_is_shown_once(
    browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    """Two sites can remember the same words; the person sees them once."""
    page = home(browser, overlay, history, [LONG, LONG.upper(), LONGER], "150%", at)

    assert remembered_on(page) == [LONG, LONGER]


def test_a_remembered_goal_is_one_line(
    browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    """A goal can be as long as someone typed it. The line holds one line and
    no more, and the words are all still there for a screen reader."""
    page = home(browser, overlay, history, TALLEST, "100%", at)
    line = page.get_by_test_id("remembered").first

    lines = page.evaluate(
        """el => { const t = el.querySelector('span.line-clamp-1');
                   return Math.round(t.getBoundingClientRect().height /
                                     parseFloat(getComputedStyle(t).lineHeight)); }""",
        line.element_handle())

    assert lines == 1
    # Clamped, not cut: every word is still there.
    assert TALLEST[0] in page.evaluate("el => el.textContent", line.element_handle())


def test_pressing_a_remembered_goal_asks_for_it_in_its_own_words(
    browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    page = home(browser, overlay, history, [LONG], "150%", at)
    history.received.clear()

    page.get_by_test_id("remembered").first.click()
    page.wait_for_timeout(800)

    starts = [m["payload"] for m in history.received if m.get("type") == "task.start"]
    assert starts and starts[0]["goal"] == LONG
    assert not starts[0].get("flow")


# --- the greeting, the example, the entrance --------------------------------


@pytest.mark.parametrize("hour, words", [
    (9, "Good morning. What can I do for you?"),
    (14, "Good afternoon. What can I do for you?"),
    (20, "Good evening. What can I do for you?"),
    (2, "Good evening. What can I do for you?"),
], ids=["morning", "afternoon", "evening", "small hours"])
def test_the_greeting_says_the_time_of_day(
    hour: int, words: str, browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    def clock(page: Page) -> None:
        page.clock.set_fixed_time(datetime(2026, 10, 14, hour, 30))

    page = home(browser, overlay, history, [], "100%", at, before=clock)

    assert page.get_by_test_id("greeting").inner_text().strip() == words


def test_the_example_is_something_simba_does(
    browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    """It said "Pay my electricity bill" until 2026-10-14, and SIMBA never pays."""
    page = home(browser, overlay, history, [], "100%", at)

    example = page.get_by_role("textbox", name=BOX).get_attribute("placeholder") or ""

    assert example == "Trains from Lahore to Karachi tomorrow"
    assert not any(word in example.lower() for word in ("pay", "book", "buy"))


FIRST_TILE = "() => +getComputedStyle(document.querySelector('[data-testid=tiles] li')).opacity"


def opened(page: Page, overlay: str, history: History) -> float:  # noqa: F811
    """The first tile's opacity as soon as it is on the page."""
    history.goals = []
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{history.port}")
    page.get_by_test_id("tile").first.wait_for(state="attached", timeout=15000)
    return page.evaluate(FIRST_TILE)


def test_the_tiles_rise_in_when_simba_opens(
    browser, overlay: str, history: History,  # noqa: F811
) -> None:
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    try:
        assert opened(page, overlay, history) < 0.5
        page.wait_for_timeout(2000)
        assert page.evaluate(FIRST_TILE) == 1
    finally:
        page.close()


def test_under_reduced_motion_there_is_no_entrance(
    browser, overlay: str, history: History,  # noqa: F811
) -> None:
    page = browser.new_page(viewport={"width": 1280, "height": 800}, reduced_motion="reduce")
    try:
        assert opened(page, overlay, history) == 1
    finally:
        page.close()
