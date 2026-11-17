"""The first screen: a greeting that asks where, one box, and — with no list of
websites offered — the three tasks SIMBA knows by heart in the websites' place.

**Redesigned 2026-11-14** (Raham: "the home screen must not look like three
tasks"). With a list of websites, the first screen is their cards, and
`test_sites.py` checks it. This file keeps what is true whatever is offered:
the box and its button are on screen at every scaling, what is typed is asked
for in its own words, the greeting says the time of day, and the example is
something SIMBA does. Goals asked for before are no longer a row here: one is
a suggestion on its own website's screen.

Until then this file checked three large tiles, two remembered goals under
them, what told two remembered goals apart, and the tiles' entrance — all of
which went with that screen.

The viewports are the window's content in CSS pixels, with the scale factor to
match (EVALUATION.md, 2026-09-25c), and the 632px window without Electron's
menu bar.
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
    # A goal, or a goal with the backend's short label (2026-10-16).
    history.goals = [goal if isinstance(goal, dict) else {"goal": goal, "site": "127.0.0.1"}
                     for goal in goals]
    page = browser.new_page(viewport={"width": width, "height": height},
                            device_scale_factor=scale)
    pages[size] = page
    if before:
        before(page)
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{history.port}")
    page.get_by_role("textbox", name=BOX).wait_for(timeout=15000)
    page.wait_for_timeout(1600)  # past the entrance, and the history's arrival
    return page


def tiles_on(page: Page) -> list[str]:
    """The tiles' own words, left to right."""
    return [t.inner_text().strip() for t in page.get_by_test_id("tile").all()]


def remembered_on(page: Page) -> list[str]:
    """The goals asked for before, top to bottom."""
    return [r.inner_text().strip() for r in page.get_by_test_id("remembered").all()]


def rect(page: Page, test_id: str) -> dict:
    box = page.get_by_test_id(test_id).first.bounding_box()
    assert box, test_id
    return box


def overlap(a: dict, b: dict) -> bool:
    """Whether two boxes share any area (touching edges do not count)."""
    return (a["x"] < b["x"] + b["width"] - 1 and b["x"] < a["x"] + a["width"] - 1
            and a["y"] < b["y"] + b["height"] - 1 and b["y"] < a["y"] + a["height"] - 1)


#: What the first screen is made of (2026-11-17, the home redesign), none of it over any other.
PARTS = ["home-logo", "status-line", "teach-a-task", "change-settings", "ask-goal", "home-go",
         "chips", "site-grid", "bookings-panel", "own-tiles"]


def box_fits(page: Page) -> tuple[bool, dict]:
    box = page.get_by_role("textbox", name=BOX)
    rect_ = box.bounding_box()
    viewport = page.viewport_size
    button = page.get_by_role("button", name="Start", exact=True).bounding_box()
    scrolls = page.evaluate(
        "() => document.scrollingElement.scrollHeight > window.innerHeight")
    # Every part of the screen wholly in the window (the grid and the aside scroll inside
    # themselves when there is more of them than room, so only their tops are held to it),
    # and none over another: the way in for a helper and "My bookings" used to be drawn
    # over the greeting at 150%.
    boxes = {name: rect(page, name) for name in PARTS if page.get_by_test_id(name).count()}
    crossings = [(a, b) for i, a in enumerate(boxes) for b in list(boxes)[i + 1:]
                 if overlap(boxes[a], boxes[b])]
    inside = all(0 <= r["x"] and r["x"] + r["width"] <= viewport["width"] + 1 and r["y"] >= 0
                 for r in boxes.values())
    measured = {"box_bottom": round(rect_["y"] + rect_["height"]),
                "start_bottom": round(button["y"] + button["height"]),
                "height": viewport["height"], "scrolls": scrolls, "crossings": crossings,
                "inside": inside}
    fits = (rect_["y"] >= 0 and measured["box_bottom"] <= viewport["height"]
            and measured["start_bottom"] <= viewport["height"] and not scrolls
            and not crossings and inside)
    return fits, measured


# --- the box, at every scaling ----------------------------------------------


WORST = [LONGER, LONG, "Register for CS-401"]
# Three bills looked up: every goal a whole sentence.
BILLS = [f"Find the amount due for reference number {n}."
         for n in ("04141234567890", "04149999999999", "04145555555555")]
# Longer than any goal the system writes: more than a line at every size.
TALLEST = [f"{bill} Then tell me which of them is due first and how much it is." for bill in BILLS]


@pytest.mark.parametrize("size", list(SIZES))
@pytest.mark.parametrize("goals", [[], TALLEST], ids=["no history", "three at the limit"])
def test_the_box_is_on_screen_without_scrolling(
    size: str, goals: list[str], browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    """The requirement, at every scaling, whatever was asked for before: goals
    asked before are no longer on the first screen (2026-11-14), so the longest
    history the store would offer changes nothing here."""
    page = home(browser, overlay, history, goals, size, at)

    fits, measured = box_fits(page)

    assert fits, (size, measured)
    assert page.get_by_test_id("remembered").count() == 0


# --- with no list of websites offered ------------------------------------------


def test_with_no_websites_offered_the_three_known_tasks_stand_in(
    browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    """This backend offers no websites, as an older one would, or one whose
    list could not be read. The first screen is not left empty: the three
    tasks SIMBA knows by heart are cards where the websites would be. With a
    list, they are suggestions on their own websites (`test_sites.py`)."""
    page = home(browser, overlay, history, [], "100%", at)

    assert tiles_on(page) == list(TILES.values())
    assert page.get_by_test_id("site").count() == 0


def test_pressing_a_known_task_runs_that_flow(
    browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    page = home(browser, overlay, history, [], "100%", at)
    history.received.clear()

    page.get_by_test_id("tile").filter(has_text="Find train times").click()
    page.wait_for_timeout(600)

    starts = [m["payload"] for m in history.received if m["type"] == "task.start"]
    assert starts and starts[-1]["flow"] == "railways"
    assert starts[-1]["goal"] == "Find train times"


def test_what_is_typed_in_the_box_is_asked_for_in_its_own_words(
    browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    """The first screen's box still takes something to do, as it always has:
    what is typed goes to the backend as typed, with no flow and no website."""
    page = home(browser, overlay, history, [], "125%", at)
    history.received.clear()
    start = page.get_by_role("button", name="Start", exact=True)
    assert start.is_disabled()

    page.get_by_role("textbox", name=BOX).fill("Trains from Lahore to Karachi tomorrow")
    start.click()
    page.wait_for_timeout(600)

    sent = [m["payload"] for m in history.received if m["type"] == "task.start"][-1]
    assert sent["goal"] == "Trains from Lahore to Karachi tomorrow"
    assert "flow" not in sent and "site" not in sent


# --- the greeting -----------------------------------------------------------


@pytest.mark.parametrize("hour, greeting", [
    (9, "Good morning"), (14, "Good afternoon"), (20, "Good evening"), (2, "Good evening"),
], ids=["morning", "afternoon", "evening", "small hours"])
def test_the_greeting_says_the_time_of_day_and_asks_where(
    hour: int, greeting: str, browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    """The first question is where, not what (2026-11-14)."""
    def set_clock(page: Page) -> None:
        page.clock.set_fixed_time(datetime(2026, 10, 14, hour, 30))

    page = home(browser, overlay, history, [], "100%", at, before=set_clock)

    # A small greeting over the one question (2026-11-17).
    assert page.get_by_test_id("greeting").inner_text().strip().startswith(greeting)
    assert page.get_by_role("heading").count() >= 0
    assert page.get_by_text("What would you like to do?", exact=True).is_visible()


def test_the_example_is_something_simba_does(
    browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    """The box's example names a website to go to and something to ask for,
    and nothing SIMBA does not do: it never pays for anything by itself."""
    page = home(browser, overlay, history, [], "100%", at)

    example = page.get_by_role("textbox", name=BOX).get_attribute("placeholder")

    assert example == "For example: book a bus from Lahore to Karachi on Friday"
    assert "pay" not in example.lower()


def test_the_presence_mark_is_small_and_the_lion_is_in_the_corner(
    browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    """Small on the first screen too since 2026-11-14: the websites need the
    height. The lion and the name stay in the corner, which is the brand."""
    page = home(browser, overlay, history, [], "150%", at)

    mark = page.get_by_role("status").first.bounding_box()
    assert mark["height"] <= 64
    assert page.get_by_test_id("home-logo").is_visible()
