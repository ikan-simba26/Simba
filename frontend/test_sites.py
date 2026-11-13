"""The websites SIMBA can work with, on the home screen (2026-11-13, the
advisor's direction): the list on the left by genre, a website chosen and what
SIMBA can do there, the box for any website beside the box to ask in, "Add a
website", and the reply when SIMBA cannot do a goal on a website yet.

Rendered from source at the window's real sizes against a scripted backend
whose first message is the backend's own offer — the shipped catalogue, made by
`app.past_goals` itself — so the list here is the list the person gets.
"""

import asyncio
import json
import threading
from collections.abc import Iterator

import pytest
import websockets
from playwright.sync_api import Page, Playwright

from frontend.test_home import SIZES
from frontend.test_terminal_states import overlay  # noqa: F401 - the built overlay

BOX = "What would you like me to do?"


def shipped_offer(tmp_path_factory) -> dict:
    """The backend's own first message, with the shipped catalogue and nothing
    of anyone's: no goals, tiles, routines or added sites."""
    import os

    from backend.orchestrator import app as app_module
    from backend.orchestrator.catalogue import CatalogueStore
    from backend.orchestrator.routines import RoutineStore
    from backend.orchestrator.tiles import TileStore

    folder = tmp_path_factory.mktemp("offer")
    os.environ["SIMBA_TRACE_DB"] = str(folder / "traces.db")
    try:
        offer = app_module.past_goals(TileStore(folder / "tiles.json"),
                                      RoutineStore(folder / "routines.json"),
                                      CatalogueStore(local=folder / "local.json"))
    finally:
        del os.environ["SIMBA_TRACE_DB"]
    return offer.model_dump(exclude_none=True)


def _stuck(payload):
    return [("task.started", {"goal": payload["goal"], "estimated_steps": 3}),
            ("state.changed", {"state": "stuck"}),
            ("help.requested", {"reason": "I couldn't work out how to do this on this website.",
                                "suggestion": "A helper can show me once. Then I can do it on my own.",
                                "teach_site": payload["site"]})]


def _not_allowed(payload):
    return [("goal.answered", {"kind": "not_allowed", "goal": payload["goal"], "flows": [],
                               "site": payload["site"]})]


def _a_step(payload):
    return [("task.started", {"goal": payload["goal"], "estimated_steps": 3}),
            ("state.changed", {"state": "waiting"}),
            ("step.presented", {
                "step_index": 1, "step_total": 3, "instruction": "Click Show more.",
                "detail": "The rest of the list is behind it.", "fields": [],
                "actions": [{"id": "confirm", "label": "Yes, do that", "kind": "primary"},
                            {"id": "cancel", "label": "Stop this", "kind": "secondary"}],
                "requires_confirmation": True, "worked_out_by": "Groq"})]


def _pay(payload):
    return [("task.started", {"goal": payload["goal"], "estimated_steps": 3}),
            ("handover", {"reason": "payment", "site": "shop.example.pk",
                          "sentence": "Your turn: pay on the page below. Type your card details "
                                      "or code there yourself. I don't see or keep them. Press "
                                      "I've finished when it's done."})]


#: Goals the scripted backend answers with a whole scene.
SCRIPTS = {"stuck please": _stuck, "not allowed please": _not_allowed, "a step please": _a_step,
           "pay please": _pay}


class Backend:
    """Says hello with the offer, keeps what the overlay sends, and answers
    `site.add` and a goal as the real backend would for these tests."""

    def __init__(self, offer: dict) -> None:
        self.offer = offer
        self.received: list[dict] = []
        self.port = 0
        started = threading.Event()

        def run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def handler(ws):
                seq = 0

                async def send(kind: str, payload: dict) -> None:
                    nonlocal seq
                    seq += 1
                    await ws.send(json.dumps({"v": 1, "type": kind, "task_id": "t", "seq": seq,
                                              "ts": 0, "payload": payload}))

                offer = json.loads(json.dumps(self.offer))
                await send("history.offered", offer)
                try:
                    async for said in ws:
                        message = json.loads(said)
                        self.received.append(message)
                        payload = message.get("payload", {})
                        if message["type"] == "site.add":
                            if payload.get("address") == "not an address":
                                await send("error", {"code": "SITE_NOT_ADDED",
                                                     "message": "address"})
                                continue
                            offer["sites"].append({
                                "id": "added-1", "name": payload["name"],
                                "address": "https://clinic.example.pk/",
                                "genre": payload["genre"], "tasks": [], "added": True})
                            await send("history.offered", offer)
                        elif message["type"] == "ai.setup":
                            key = payload.get("key", "")
                            await send("ai.status", {
                                "configured": True, "provider": "Gemini",
                                "ends_with": key[-4:],
                                "check": getattr(self, "verdict", "ok")})
                        elif message["type"] == "handover.done":
                            if payload.get("action") == "done":
                                await send("task.completed", {
                                    "summary": "paid", "duration_ms": 1, "steps_taken": 1,
                                    "llm_calls": 0, "replayed": False, "findings": [],
                                    "heading": "The website says it went through.",
                                    "caveat": "You paid on the website yourself. I didn't see "
                                              "or keep your card details or code.",
                                    "confirmation": "The website says: “Thank you”."})
                            else:
                                await send("task.failed", {
                                    "reason": "I've stopped, as you asked. I didn't change "
                                              "anything.", "recoverable": True})
                        elif message["type"] == "task.start" and payload.get("goal") in SCRIPTS:
                            for kind, body in SCRIPTS[payload["goal"]](payload):
                                await send(kind, body)
                        elif message["type"] == "task.start" and payload.get("site"):
                            await send("goal.answered", {
                                "kind": "not_yet", "goal": payload["goal"], "flows": [],
                                "site": payload["site"]})
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

    def sent(self, kind: str) -> list[dict]:
        return [m["payload"] for m in self.received if m["type"] == kind]


@pytest.fixture(scope="module")
def offer(tmp_path_factory) -> dict:
    return shipped_offer(tmp_path_factory)


@pytest.fixture
def backend(offer) -> Backend:
    return Backend(offer)


@pytest.fixture(scope="module")
def browser(playwright_instance: Playwright):
    browser = playwright_instance.chromium.launch()
    yield browser
    browser.close()


@pytest.fixture
def pages() -> Iterator[list]:
    opened: list = []
    yield opened
    for page in opened:
        page.close()


def home(browser, overlay: str, backend: Backend, size: str, pages: list) -> Page:  # noqa: F811
    width, height, scale = SIZES[size]
    page = browser.new_page(viewport={"width": width, "height": height},
                            device_scale_factor=scale)
    pages.append(page)
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    page.get_by_test_id("site-list").wait_for(timeout=15000)
    page.wait_for_timeout(1600)  # past the entrance
    return page


def edges(page: Page, testid: str) -> dict:
    box = page.get_by_test_id(testid).bounding_box()
    return {"left": box["x"], "right": box["x"] + box["width"],
            "top": box["y"], "bottom": box["y"] + box["height"]}


# --- the list ----------------------------------------------------------------


@pytest.mark.parametrize("size", list(SIZES))
def test_the_list_is_on_the_left_and_the_home_screen_still_fits(
        size, browser, overlay, backend, offer, pages):  # noqa: F811
    page = home(browser, overlay, backend, size, pages)
    width, height, _ = SIZES[size]
    listed = edges(page, "site-list")
    box = page.get_by_role("textbox", name=BOX).bounding_box()
    greeting = edges(page, "greeting")

    # Every website and every genre with one is there, in the backend's order.
    names = [b.inner_text().strip() for b in page.get_by_test_id("site").all()]
    assert names == [site["name"] for site in offer["sites"]]
    genres = [g.get_attribute("aria-label") for g in page.get_by_test_id("site-genre").all()]
    assert genres == [g for g in offer["genres"]
                      if any(site["genre"] == g for site in offer["sites"])]

    # On the left, wholly in the window, beside the column and not under it.
    assert listed["left"] >= 0 and listed["bottom"] <= height
    assert listed["right"] <= greeting["left"], (listed, greeting)
    assert listed["right"] <= box["x"]
    # The page never scrolls, sideways or down; the list scrolls by itself.
    assert not page.evaluate("() => document.scrollingElement.scrollHeight > innerHeight")
    assert not page.evaluate("() => document.scrollingElement.scrollWidth > innerWidth")
    assert box["y"] + box["height"] <= height
    # "Add a website" is at its foot, on screen.
    add = edges(page, "add-site")
    assert add["bottom"] <= listed["bottom"] and add["top"] >= listed["top"]
    # And the three that are ready to go say so: not all SIMBA can do.
    assert page.get_by_test_id("can-help").inner_text().strip() == "Ready to go"


def test_the_list_scrolls_inside_itself_when_it_is_long(browser, overlay, offer, pages):  # noqa: F811
    long_offer = json.loads(json.dumps(offer))
    long_offer["sites"] += [{"id": f"x{n}", "name": f"Example site {n}",
                             "address": f"https://x{n}.example.com/", "genre": "Other",
                             "tasks": [], "added": True} for n in range(30)]
    long_offer["genres"].append("Other")
    page = home(browser, overlay, Backend(long_offer), "150%", pages)
    scroll = page.get_by_test_id("site-scroll")
    assert scroll.evaluate("el => el.scrollHeight > el.clientHeight")
    assert not page.evaluate("() => document.scrollingElement.scrollHeight > innerHeight")
    # The last one can be reached.
    page.get_by_test_id("site").last.scroll_into_view_if_needed()
    assert page.get_by_test_id("site").last.is_visible()


# --- a website chosen ---------------------------------------------------------


@pytest.mark.parametrize("size", list(SIZES))
def test_a_website_chosen_shows_what_simba_can_do_there(
        size, browser, overlay, backend, pages):  # noqa: F811
    page = home(browser, overlay, backend, size, pages)
    page.get_by_test_id("site").filter(has_text="UK bank holidays").click()
    panel = page.get_by_test_id("site-panel")
    panel.wait_for()
    task = page.get_by_test_id("site-task")
    assert task.count() == 1
    assert "The next bank holiday" in task.inner_text()
    assert "I'll work it out" in task.inner_text()
    # The box asks about it — in a short window its lead-in goes, as the home
    # screen's always has, and the panel above names the website — and the
    # whole screen still fits.
    page.get_by_role("textbox", name=BOX).wait_for()
    assert page.get_by_text("What would you like me to do on UK bank holidays?").count() == 1
    assert "UK bank holidays" in panel.inner_text()
    height = SIZES[size][1]
    assert not page.evaluate("() => document.scrollingElement.scrollHeight > innerHeight")
    assert edges(page, "site-show-here")["bottom"] <= height


def test_an_ai_task_is_sent_with_its_website(browser, overlay, backend, pages):  # noqa: F811
    page = home(browser, overlay, backend, "100%", pages)
    page.get_by_test_id("site").filter(has_text="UK bank holidays").click()
    page.get_by_test_id("site-task").click()
    page.wait_for_timeout(500)
    start = backend.sent("task.start")[-1]
    assert start["goal"] == "When is the next bank holiday?"
    assert start["site"] == "https://www.gov.uk/bank-holidays"
    assert "flow" not in start


def test_a_built_in_task_is_sent_as_its_flow_and_no_website(
        browser, overlay, backend, pages):  # noqa: F811
    page = home(browser, overlay, backend, "100%", pages)
    page.get_by_test_id("site").filter(has_text="Pakistan Railways").click()
    task = page.get_by_test_id("site-task")
    assert "I know this one" in task.inner_text()
    task.click()
    page.wait_for_timeout(500)
    start = backend.sent("task.start")[-1]
    assert (start["goal"], start["flow"]) == ("Find train times", "railways")
    assert "site" not in start


def test_the_box_asks_about_the_chosen_website(browser, overlay, backend, pages):  # noqa: F811
    page = home(browser, overlay, backend, "125%", pages)
    page.get_by_test_id("site").filter(has_text="Wikipedia").click()
    page.get_by_role("textbox", name=BOX).fill("Who wrote Bano Qudsia's books?")
    page.get_by_role("button", name="Start", exact=True).click()
    page.wait_for_timeout(500)
    start = backend.sent("task.start")[-1]
    assert start["site"] == "https://en.wikipedia.org/wiki/Main_Page"


def test_choosing_it_again_lets_it_go(browser, overlay, backend, pages):  # noqa: F811
    page = home(browser, overlay, backend, "100%", pages)
    site = page.get_by_test_id("site").filter(has_text="Wikipedia")
    site.click()
    page.get_by_test_id("site-panel").wait_for()
    assert site.get_attribute("aria-pressed") == "true"
    page.get_by_test_id("site-not-this").click()
    page.get_by_test_id("tiles").wait_for()
    assert site.get_attribute("aria-pressed") == "false"


# --- any website, typed -----------------------------------------------------------


def test_any_website_typed_beside_the_box_is_sent_as_typed(
        browser, overlay, backend, pages):  # noqa: F811
    page = home(browser, overlay, backend, "150%", pages)
    page.get_by_role("textbox", name=BOX).fill("Opening hours")
    page.get_by_test_id("ask-where").fill("lums.edu.pk")
    page.get_by_role("button", name="Start", exact=True).click()
    page.wait_for_timeout(500)
    assert backend.sent("task.start")[-1]["site"] == "lums.edu.pk"


def test_with_no_website_nothing_extra_is_sent(browser, overlay, backend, pages):  # noqa: F811
    page = home(browser, overlay, backend, "100%", pages)
    page.get_by_role("textbox", name=BOX).fill("hello")
    page.get_by_role("button", name="Start", exact=True).click()
    page.wait_for_timeout(500)
    assert "site" not in backend.sent("task.start")[-1]


# --- not yet ----------------------------------------------------------------------


def test_not_yet_offers_a_helper_on_that_website(browser, overlay, backend, pages):  # noqa: F811
    page = home(browser, overlay, backend, "150%", pages)
    page.get_by_role("textbox", name=BOX).fill("Track my passport application")
    page.get_by_test_id("ask-where").fill("https://dgip.gov.pk/")
    page.get_by_role("button", name="Start", exact=True).click()
    page.get_by_test_id("not-yet").wait_for(timeout=10000)
    assert page.get_by_text("I don't know how to do that on dgip.gov.pk yet.").is_visible()
    assert not page.evaluate("() => document.scrollingElement.scrollHeight > innerHeight")
    page.get_by_test_id("show-me-once").click()
    page.get_by_test_id("teach-intro").wait_for()
    assert page.get_by_test_id("teach-address").input_value() == "https://dgip.gov.pk/"


# --- add a website ------------------------------------------------------------------


@pytest.mark.parametrize("size", list(SIZES))
def test_add_a_website_fits_and_adds_it(size, browser, overlay, backend, pages):  # noqa: F811
    page = home(browser, overlay, backend, size, pages)
    page.get_by_test_id("add-site").click()
    page.get_by_test_id("add-site-screen").wait_for()
    # Past the crossfade: while the home screen leaves, both share the column.
    page.wait_for_timeout(800)
    height = SIZES[size][1]
    assert edges(page, "add-site-go")["bottom"] <= height
    assert not page.evaluate("() => document.scrollingElement.scrollHeight > innerHeight")
    # The list is the home screen's alone.
    assert page.get_by_test_id("site-list").count() == 0

    page.get_by_test_id("add-site-name").fill("My clinic")
    page.get_by_test_id("add-site-address").fill("clinic.example.pk")
    page.get_by_test_id("add-site-genre").select_option("Health")
    page.get_by_test_id("add-site-go").click()

    # Back home, with the new website chosen and in the list under Health.
    page.get_by_test_id("site-panel").wait_for(timeout=10000)
    assert backend.sent("site.add")[-1] == {"name": "My clinic", "address": "clinic.example.pk",
                                            "genre": "Health"}
    chosen = page.locator("[data-testid=site][aria-pressed=true]")
    assert chosen.inner_text().strip() == "My clinic"


def test_a_website_that_cannot_be_added_says_why(browser, overlay, backend, pages):  # noqa: F811
    page = home(browser, overlay, backend, "100%", pages)
    page.get_by_test_id("add-site").click()
    page.get_by_test_id("add-site-name").fill("Mine")
    page.get_by_test_id("add-site-address").fill("not an address")
    page.get_by_test_id("add-site-go").click()
    note = page.get_by_test_id("site-note")
    note.wait_for(timeout=10000)
    assert note.inner_text().strip() == "That doesn't look like a website's address."
    # Still on the screen, to put it right.
    assert page.get_by_test_id("add-site-screen").is_visible()
    page.get_by_test_id("add-site-back").click()
    page.get_by_test_id("site-list").wait_for()


# --- phase 2: AI first, then teach (2026-11-13) --------------------------------------


def ask_on(page: Page, goal: str, site: str) -> None:
    page.get_by_role("textbox", name=BOX).fill(goal)
    page.get_by_test_id("ask-where").fill(site)
    page.get_by_role("button", name="Start", exact=True).click()


@pytest.mark.parametrize("size", ["100%", "150%"])
def test_when_the_ai_cannot_a_helper_is_offered_on_that_website(
        size, browser, overlay, backend, pages):  # noqa: F811
    page = home(browser, overlay, backend, size, pages)
    ask_on(page, "stuck please", "https://dgip.gov.pk/")
    offer = page.get_by_test_id("stuck-show-me-once")
    offer.wait_for(timeout=10000)
    page.wait_for_timeout(600)
    assert not page.evaluate("() => document.scrollingElement.scrollHeight > innerHeight")
    offer.click()
    page.get_by_test_id("teach-intro").wait_for()
    assert page.get_by_test_id("teach-address").input_value() == "https://dgip.gov.pk/"


def test_a_website_that_says_no_is_told_plainly(browser, overlay, backend, pages):  # noqa: F811
    page = home(browser, overlay, backend, "150%", pages)
    ask_on(page, "not allowed please", "https://dgip.gov.pk/")
    page.get_by_test_id("not-allowed").wait_for(timeout=10000)
    assert page.get_by_text("dgip.gov.pk asks programs like me not to use that page.").is_visible()
    # No helper is offered: a taught task would use the page just the same.
    assert page.get_by_test_id("show-me-once").count() == 0


@pytest.mark.parametrize("level", [1, 2, 3])
def test_a_move_the_ai_chose_says_who_worked_it_out(
        level, browser, overlay, backend, pages):  # noqa: F811
    page = home(browser, overlay, backend, "150%", pages)
    ask_on(page, "a step please", "https://www.gov.uk/")
    line = page.get_by_test_id("worked-out-by")
    line.wait_for(timeout=10000)
    # The level's dots, by their names for a screen reader (`copy.LEVEL`).
    name = {1: "Show more", 2: "Show the usual amount", 3: "Show less"}[level]
    page.get_by_role("button", name=name, exact=True).click()
    page.wait_for_timeout(900)  # the fold
    assert line.is_visible()
    assert line.inner_text().strip() == "Worked out with Groq."
    assert not page.evaluate("() => document.scrollingElement.scrollHeight > innerHeight")


# --- phase 3: a task taught on a sister website (2026-11-13) --------------------------


def test_a_task_taught_on_a_sister_site_runs_on_the_one_chosen(
        browser, overlay, offer, pages):  # noqa: F811
    taught = json.loads(json.dumps(offer))
    taught["routines"] = [{"id": "r1", "label": "My bill", "site": "bill.pitc.com.pk"}]
    gas = next(site for site in taught["sites"] if site["id"] == "ssgc")
    gas["tasks"].append({"label": "My bill", "goal": "My bill", "how": "taught",
                         "routine": "r1", "taught_on": "IESCO electricity bill"})
    backend = Backend(taught)
    page = home(browser, overlay, backend, "150%", pages)
    page.get_by_test_id("site").filter(has_text="Sui Southern Gas").click()
    task = page.get_by_test_id("site-task").filter(has_text="My bill")
    assert "A helper showed me on IESCO electricity bill" in task.inner_text()
    assert not page.evaluate("() => document.scrollingElement.scrollHeight > innerHeight")
    task.click()
    page.wait_for_timeout(500)
    start = backend.sent("task.start")[-1]
    assert (start["routine"], start["site"]) == ("r1", "https://www.ssgc.com.pk/")


# --- phase 4: the page handed to the person to pay (2026-11-13) ------------------------


@pytest.mark.parametrize("size", ["100%", "150%"])
def test_paying_hands_the_page_over_and_comes_back(size, browser, overlay, backend, pages):  # noqa: F811
    page = home(browser, overlay, backend, size, pages)
    lines: list[str] = []
    page.on("console", lambda message: lines.append(message.text))
    ask_on(page, "pay please", "shop.example.pk")
    bar = page.get_by_test_id("handover-bar")
    bar.wait_for(timeout=10000)
    # The bar, and the host told to show the website below it.
    assert "[simba] host bar 160" in lines
    assert "Type your card details" in page.get_by_test_id("handover-sentence").inner_text()
    assert bar.bounding_box()["height"] == 160
    page.get_by_test_id("handover-done").click()
    page.get_by_text("The website says it went through.").wait_for(timeout=10000)
    assert backend.sent("handover.done")[-1] == {"action": "done"}
    assert "[simba] host full" in lines


def test_stop_on_the_handover_bar_says_nothing_was_changed(
        browser, overlay, backend, pages):  # noqa: F811
    page = home(browser, overlay, backend, "100%", pages)
    ask_on(page, "pay please", "shop.example.pk")
    page.get_by_test_id("handover-bar").wait_for(timeout=10000)
    page.get_by_test_id("handover-stop").click()
    page.wait_for_timeout(800)
    assert backend.sent("handover.done")[-1] == {"action": "cancel"}
    assert page.get_by_test_id("handover-bar").count() == 0


# --- phase 6: always says whether it is connected, and what it is doing (2026-11-13) ----


def overlaps(a: dict, b: dict) -> bool:
    return not (a["right"] <= b["left"] or b["right"] <= a["left"]
                or a["bottom"] <= b["top"] or b["bottom"] <= a["top"])


@pytest.mark.parametrize("size", list(SIZES))
def test_the_status_line_says_connected_and_covers_nothing(
        size, browser, overlay, backend, pages):  # noqa: F811
    page = home(browser, overlay, backend, size, pages)
    line = page.get_by_test_id("status-line")
    assert line.inner_text().replace("\n", " ").split() == ["Connected", "·", "Ready"]
    status = edges(page, "status-line")
    assert status["bottom"] <= SIZES[size][1]
    for testid in ("site-list", "add-site", "change-settings", "greeting"):
        assert not overlaps(status, edges(page, testid)), testid
    start = page.get_by_role("button", name="Start", exact=True).bounding_box()
    assert not overlaps(status, {"left": start["x"], "right": start["x"] + start["width"],
                                 "top": start["y"], "bottom": start["y"] + start["height"]})


def test_the_status_line_says_what_it_is_doing(browser, overlay, backend, pages):  # noqa: F811
    page = home(browser, overlay, backend, "150%", pages)
    ask_on(page, "a step please", "https://www.gov.uk/")
    page.get_by_test_id("worked-out-by").wait_for(timeout=10000)
    assert page.get_by_test_id("status-activity").inner_text() == "Your turn"


def test_a_backend_that_cannot_be_reached_is_said_and_tried_again(
        browser, overlay, pages):  # noqa: F811
    import socket as sockets

    with sockets.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    pages.append(page)
    attempts: list[str] = []
    page.on("websocket", lambda ws: attempts.append(ws.url))
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{port}/ws")
    line = page.get_by_test_id("status-line")
    page.wait_for_function(
        "() => document.querySelector('[data-testid=status-line]')?.dataset.connection === 'error'",
        timeout=15000)
    assert "I can't reach SIMBA's helper. Trying again." in line.inner_text()
    page.wait_for_timeout(4500)
    assert len(attempts) >= 2  # tried again by itself
