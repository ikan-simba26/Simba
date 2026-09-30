"""The home screen: one list of at most three cards, and the box always on screen.

Until 2026-09-30 the home screen showed the three things SIMBA can do and then,
under a second heading, up to three goals the person had asked for before: six
cards. At 150% the window's content is 1266x606, and six cards put the text box
below the bottom of it. `test_window_fit.py` never saw this, because the fit
measurement launches the host with no backend, and with no backend there is no
history — so what it measured was always the three-card screen.

Now there is one list: remembered goals first, most recent first, then the
things SIMBA can do, nothing twice, three at most (`App.homeCards`). This builds
the overlay from source and renders it at the three sizes the window actually
gets — measured in EVALUATION.md, 2026-09-25c — against a scripted backend that
offers the history, and checks the box from outside.

The viewports are the window's content in CSS pixels, with the scale factor to
match, which is how the overlay lays out since the zoom was withdrawn: at
zoom 1, a CSS viewport of 1266x606 is the same layout whatever the device
pixels behind it.
"""

import asyncio
import json
import threading
from collections.abc import Iterator

import pytest
import websockets
from playwright.sync_api import Page, Playwright

from frontend.test_terminal_states import overlay  # noqa: F401 - the built overlay

# The window's content at each display scale (EVALUATION.md, 2026-09-25c).
SIZES = {
    "100%": (1280, 800, 1.0),
    "125%": (1280, 734, 1.25),
    "150%": (1266, 606, 1.5),
}

BOX = "What would you like me to do?"
CARDS = {"registration": "Register for CS-401", "billing": "Check my electricity bill",
         "railways": "Find trains from Lahore to Karachi"}

# What the trace store offers since goals are spelled out (details.py): whole
# sentences, and long enough to wrap onto a second line on a card.
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


def home(browser, overlay: str, history: History, goals: list[str], size: str,  # noqa: F811
         pages: dict) -> Page:
    width, height, scale = SIZES[size]
    history.goals = [{"goal": goal, "site": "127.0.0.1"} for goal in goals]
    page = browser.new_page(viewport={"width": width, "height": height},
                            device_scale_factor=scale)
    pages[size] = page
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{history.port}")
    page.get_by_role("textbox", name=BOX).wait_for(timeout=15000)
    # History arrives after the socket opens, and the first card then stops
    # being the first thing SIMBA can do — however the remembered goal is shown.
    # (No test here remembers "Register for CS-401" first.)
    if goals:
        page.wait_for_function(
            """() => { const b = document.querySelector('section button');
                       return b && !b.innerText.startsWith('Register for CS-401'); }""",
            timeout=10000)
    page.wait_for_timeout(1200)
    return page


def cards_on(page: Page) -> list[str]:
    """The cards' own words, top to bottom."""
    lead = page.get_by_text("I can help with these", exact=True)
    section = lead.locator("xpath=ancestor::section[1]")
    return [b.inner_text().strip() for b in section.get_by_role("button").all()]


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
# Three bills looked up: every card a whole sentence, two lines at 26px.
BILLS = [f"Find the amount due for reference number {n}."
         for n in ("04141234567890", "04149999999999", "04145555555555")]
# Longer than any goal the system writes: two lines even at 23px, and more than
# two at 26px, so every card is held at its two-line limit.
TALLEST = [f"{bill} Then tell me which of them is due first and how much it is." for bill in BILLS]


@pytest.mark.parametrize("size", list(SIZES))
@pytest.mark.parametrize("goals", [[], WORST, BILLS, TALLEST],
                         ids=["no history", "three long goals", "three bills", "three at the limit"])
def test_the_box_is_on_screen_without_scrolling(
    size: str, goals: list[str], browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    """The requirement, at 100%, 125% and 150%, with no history and with the
    longest history the store would offer."""
    page = home(browser, overlay, history, goals, size, at)

    fits, measured = box_fits(page)

    assert fits, (size, measured)


@pytest.mark.parametrize("size", list(SIZES))
def test_never_more_than_three_cards(
    size: str, browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    page = home(browser, overlay, history, ["Pay my water bill", LONG, LONGER], size, at)

    assert len(cards_on(page)) == 3


# --- the one list ----------------------------------------------------------


def test_with_no_history_the_three_things_it_can_do(
    browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    page = home(browser, overlay, history, [], "150%", at)

    assert cards_on(page) == list(CARDS.values())


def test_remembered_goals_come_first(
    browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    page = home(browser, overlay, history, [LONG], "150%", at)

    assert cards_on(page) == [LONG, CARDS["registration"], CARDS["billing"]]


def test_three_remembered_goals_fill_the_list(
    browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    """Most recent first, in the order the backend sent them."""
    page = home(browser, overlay, history, ["Pay my water bill", LONG, LONGER], "150%", at)

    assert cards_on(page) == ["Pay my water bill", LONG, LONGER]


def test_a_remembered_goal_that_is_one_of_the_cards_is_shown_once(
    browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    """First, where remembered goals go, and not again further down — whatever
    its case, spacing or full stop."""
    page = home(browser, overlay, history, ["check my  electricity bill."], "150%", at)

    assert cards_on(page) == [CARDS["billing"], CARDS["registration"], CARDS["railways"]]


def test_the_same_goal_remembered_twice_is_one_card(
    browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    """Two sites can remember the same words; the person sees them once."""
    page = home(browser, overlay, history, [LONG, LONG.upper()], "150%", at)

    assert cards_on(page) == [LONG, CARDS["registration"], CARDS["billing"]]


def test_a_card_is_never_taller_than_two_lines(
    browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    """A goal can be as long as someone typed it. The card holds two lines and
    no more, and the words are all still there for a screen reader."""
    page = home(browser, overlay, history, TALLEST, "100%", at)
    card = page.locator("section button").first

    lines = page.evaluate(
        """el => { const t = el.querySelector('span.line-clamp-2');
                   return Math.round(t.getBoundingClientRect().height /
                                     parseFloat(getComputedStyle(t).lineHeight)); }""",
        card.element_handle())

    assert lines <= 2
    # Clamped, not cut: every word is still in the card.
    assert TALLEST[0] in page.evaluate("el => el.textContent", card.element_handle())


def test_pressing_a_remembered_card_that_is_a_flow_runs_that_flow(
    browser, overlay: str, history: History, at: dict,  # noqa: F811
) -> None:
    """Shown once and in its remembered place, it still sends the flow the card
    always sent, so the backend runs exactly that rather than guessing."""
    page = home(browser, overlay, history, ["check my electricity bill."], "150%", at)
    history.received.clear()

    page.locator("section button").first.click()
    page.wait_for_timeout(800)

    starts = [m["payload"] for m in history.received if m.get("type") == "task.start"]
    assert starts and starts[0]["goal"] == CARDS["billing"]
    assert starts[0].get("flow") == "billing"
