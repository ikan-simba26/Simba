"""Every task screen has one fixed layout, and the card that builds fills as SIMBA learns.

The frontend redesign (2026-11-17, "Concept 2 · It builds as you go"): left
"So far", middle "Now", right the card; the same three every screen. This file
holds what that promises, in a real browser against the built overlay, with a
scripted backend:

  * the card starts empty and fills from the goal, then from each choice;
  * what is waiting for the person says so, in amber;
  * the final screen is the card, complete;
  * a password, a card number and a code never reach the card;
  * the three panels do not move between screens;
  * the colours say whose turn it is;
  * at the simplest level the sides fold away, and "Show more" brings them back;
  * every screen fits the window at 100%, 125% and 150%.

Requires `npm run build` in frontend/ first; skipped otherwise.
"""

import asyncio
import functools
import http.server
import json
import socketserver
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
import websockets
from playwright.sync_api import Page, Playwright

FRONTEND = Path(__file__).resolve().parent
DIST = FRONTEND / "dist"

pytestmark = pytest.mark.skipif(
    not (DIST / "index.html").exists(),
    reason="frontend not built; run `npm run build` in frontend/",
)

# 100%, 125% and 150% of a 1080p laptop, as the window is fitted to them.
SIZES = {"100": {"width": 1280, "height": 800}, "125": {"width": 1280, "height": 734},
         "150": {"width": 1266, "height": 632}}

GOAL = "Book a bus from Lahore to Karachi on Friday"
STOP = {"id": "cancel", "label": "Stop this", "kind": "secondary"}


def card(label: str, sub: str, index: int) -> dict:
    return {"id": f"choice:{index}", "label": label, "kind": "primary", "sub": sub}


def step(index: int, instruction: str, **more) -> dict:
    body = {"step_index": index, "step_total": 8, "instruction": instruction, "detail": "",
            "fields": [], "actions": [], "requires_confirmation": True}
    body.update(more)
    return body


def row(index: int, label: str) -> tuple[str, dict]:
    """A move SIMBA makes by itself: a line of the checklist."""
    return "step.presented", step(index, label, requires_confirmation=False, coming=[])


BUSES = [card("8:30 am", "Rs 6,200 Business", 0), card("2:00 pm", "Rs 5,400 Standard", 1),
         card("9:00 pm", "Rs 6,200 Overnight", 2)]
CHOOSE = step(3, "Which bus would you like?", actions=[*BUSES, STOP])
SEATS = step(5, "Which seat would you like?", actions=[
    card("Seat 9 · Window", "free", 0), card("Seat 10 · Aisle", "free", 1), STOP])
PASSWORD = step(6, "Choose a password for your account.", fields=[
    {"id": "name", "label": "Full name", "type": "text", "value": ""},
    {"id": "pw", "label": "Password", "type": "password", "value": ""}],
    actions=[{"id": "confirm", "label": "Next", "kind": "primary"}, STOP])
FINAL = step(7, "I'll press Book on daewoo.com.pk for Rs 6,200.", final=[
    {"label": "Trip", "value": "Lahore to Karachi"}, {"label": "Date", "value": "Fri 20 Nov"},
    {"label": "Bus", "value": "8:30 am"}, {"label": "Seat", "value": "9 · Window"},
    {"label": "Passenger", "value": "Muhammad Raham"}, {"label": "Amount", "value": "Rs 6,200"},
    {"label": "Website", "value": "daewoo.com.pk"}],
    actions=[{"id": "confirm", "label": "Book it", "kind": "primary"},
             {"id": "decline", "label": "Don't book", "kind": "primary"}])


@pytest.fixture(scope="module")
def static_site() -> Iterator[str]:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DIST))
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/index.html"
    finally:
        server.shutdown()
        server.server_close()


class Backend:
    """Plays `script` after `task.start`, one message per turn, and after each
    step that asks something waits for the answer before playing on."""

    def __init__(self) -> None:
        self.script: list[tuple[str, dict]] = []
        self.answers: list[dict] = []
        self.port = 0
        started = threading.Event()

        def run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def handler(ws):
                await ws.recv()  # task.start
                seq = 0
                for kind, payload in list(self.script):
                    seq += 1
                    await ws.send(json.dumps({"v": 1, "type": kind, "task_id": "t_card", "seq": seq,
                                              "ts": 0, "payload": payload}))
                    if kind == "step.presented" and payload.get("requires_confirmation", True):
                        try:
                            reply = json.loads(await ws.recv())
                        except websockets.ConnectionClosed:
                            return
                        self.answers.append(reply.get("payload", {}))
                    else:
                        await asyncio.sleep(0.05)
                try:
                    await asyncio.Future()
                except asyncio.CancelledError:
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
def backend() -> Backend:
    return Backend()


@pytest.fixture()
def page(playwright_instance: Playwright) -> Iterator[Page]:
    browser = playwright_instance.chromium.launch()
    page = browser.new_page(viewport=SIZES["100"])
    page.add_init_script("window.__simbaSettleMs = 0")
    page.add_init_script("window.__simbaWelcome = false")
    page.add_init_script("window.__simbaSplash = false")
    yield page
    browser.close()


def start(page: Page, site: str, backend: Backend, script: list[tuple[str, dict]],
          goal: str = GOAL) -> None:
    backend.script = script
    backend.answers = []
    page.goto(f"{site}?ws=ws://127.0.0.1:{backend.port}")
    page.fill("input[aria-label='What would you like me to do?']", goal)
    page.get_by_role("button", name="Start").click()


def started(goal: str = GOAL) -> list[tuple[str, dict]]:
    return [("task.started", {"goal": goal, "estimated_steps": 6}),
            ("state.changed", {"state": "waiting"})]


def rows(page: Page) -> dict[str, str]:
    """The card's lines by key: the value, or 'waiting', or '' when empty."""
    out = {}
    for line in page.locator("[data-testid=card-row]").all():
        state = line.get_attribute("data-state")
        key = line.get_attribute("data-key")
        out[key] = "waiting" if state == "waiting" else (
            line.locator("dd").inner_text() if state == "filled" else "")
    return out


# --- the card ---------------------------------------------------------------


def test_the_card_starts_empty_and_fills_from_the_goal(page, static_site, backend) -> None:
    start(page, static_site, backend, [*started(), ("step.presented", CHOOSE)])
    page.wait_for_selector("[data-testid=the-card]")
    found = rows(page)
    assert found["from"] == "Lahore" and found["to"] == "Karachi" and found["date"] == "Friday"
    assert found["seat"] == "" and found["passenger"] == "" and found["price"] == ""
    assert page.locator("[data-testid=card-count]").inner_text() == "3 of 7 filled in"
    assert "Your ticket" in page.locator("[data-testid=the-card]").inner_text()


def test_the_field_waiting_for_the_person_is_amber(page, static_site, backend) -> None:
    start(page, static_site, backend, [*started(), ("step.presented", CHOOSE)])
    page.wait_for_selector("[data-testid=card-row][data-state=waiting]")
    assert rows(page)["ride"] == "waiting"
    assert "Waiting for you" in page.locator("[data-state=waiting]").inner_text()


def test_a_choice_fills_the_card_and_the_left_panel(page, static_site, backend) -> None:
    start(page, static_site, backend, [*started(), ("step.presented", CHOOSE),
                                       ("step.presented", SEATS)])
    page.wait_for_selector("[data-testid=card]")
    page.locator("[data-testid=card]").first.click()
    page.wait_for_selector("text=Which seat would you like?")
    found = rows(page)
    assert found["ride"] == "8:30 am" and found["price"] == "Rs 6,200"
    assert found["seat"] == "waiting"
    chips = page.locator("[data-testid=so-far] [data-testid=chip]").all_inner_texts()
    assert any("8:30 am" in chip for chip in chips)
    assert "5 of 7" in page.locator("[data-testid=card-count]").inner_text()
    assert page.locator("[data-testid=chip-now]").inner_text().startswith("Now:")


def test_the_field_just_filled_is_washed(page, static_site, backend) -> None:
    start(page, static_site, backend, [*started(), ("step.presented", CHOOSE),
                                       ("step.presented", SEATS)])
    page.wait_for_selector("[data-testid=card]")
    page.locator("[data-testid=card]").first.click()
    page.wait_for_selector("[data-key=ride][data-fresh=true]", timeout=3000)


def test_the_final_screen_is_the_card_complete(page, static_site, backend) -> None:
    start(page, static_site, backend, [*started(), ("step.presented", FINAL)])
    page.wait_for_selector("[data-testid=final-check]")
    the_card = page.locator("[data-testid=the-card]")
    assert the_card.get_attribute("data-complete") == "true"
    text = the_card.inner_text()
    assert "Complete" in text and "Muhammad Raham" in text and "Rs 6,200" in text
    assert "9 · Window" in text
    # Two buttons, the same size, and neither a default: the rule is unchanged.
    answers = page.locator("[data-testid=final-answers] button")
    assert answers.count() == 2
    first, second = (answers.nth(i).bounding_box() for i in (0, 1))
    assert abs(first["height"] - second["height"]) < 1 and abs(first["width"] - second["width"]) < 2
    # And the state is the person's decision, in amber.
    assert page.locator("[data-testid=state-pill]").inner_text().strip() == "Your decision"


def test_a_password_and_what_is_typed_in_it_never_reach_the_card(page, static_site, backend) -> None:
    start(page, static_site, backend, [*started("Register for CS-401"),
                                        ("step.presented", PASSWORD)], goal="Register for CS-401")
    page.wait_for_selector("[data-testid=step-shell]")
    page.get_by_label("Full name").fill("Muhammad Raham")
    page.get_by_label("Password").fill("Hunter2-secret")
    text = page.locator("[data-testid=the-card]").inner_text()
    assert "Hunter2-secret" not in text
    page.get_by_role("button", name="Next").click()
    page.wait_for_timeout(500)
    # Answered: the name is on the card, the password is only "kept safely".
    card_text = page.locator("[data-testid=the-card]").inner_text()
    assert "Hunter2-secret" not in page.inner_text("body")
    assert "Muhammad Raham" in card_text
    assert card_text.count("Kept safely") == 1


# --- the frame --------------------------------------------------------------


def panel_boxes(page: Page) -> tuple:
    return tuple(page.locator(f"[data-testid={name}]").bounding_box() for name in
                 ("so-far", "frame-centre", "the-card"))


def test_the_three_panels_do_not_move_between_screens(page, static_site, backend) -> None:
    start(page, static_site, backend, [*started(), row(1, "Opening daewoo.com.pk"),
                                       ("step.presented", CHOOSE), ("step.presented", FINAL)])
    page.wait_for_selector("[data-testid=checklist], [data-testid=step-shell]")
    seen = []
    for _ in range(3):
        page.wait_for_timeout(700)
        seen.append(panel_boxes(page))
        if page.locator("[data-testid=final-check]").count():
            break
        cards = page.locator("[data-testid=card]")
        if cards.count():
            cards.first.click()
    assert len(seen) >= 2
    for boxes in seen[1:]:
        for before, after in zip(seen[0], boxes):
            assert before["x"] == after["x"] and before["y"] == after["y"]
            assert before["width"] == after["width"] and before["height"] == after["height"]


def test_the_bar_and_the_pill_say_whose_turn_it_is(page, static_site, backend) -> None:
    start(page, static_site, backend, [*started(), row(1, "Opening daewoo.com.pk"),
                                       ("step.presented", CHOOSE)])
    page.wait_for_selector("[data-testid=step-shell], [data-testid=choice-cards]")
    bar = page.locator("[data-testid=state-bar]")
    assert bar.get_attribute("data-phase") == "turn"
    assert bar.bounding_box()["height"] == 6
    assert page.locator("[data-testid=state-pill]").inner_text().strip() == "Your turn"


def test_while_simba_works_it_is_teal_and_the_lion_has_a_halo(page, static_site, backend) -> None:
    start(page, static_site, backend, [*started(), row(1, "Opening daewoo.com.pk")])
    page.wait_for_selector("[data-testid=checklist]")
    assert page.locator("[data-testid=state-bar]").get_attribute("data-phase") == "working"
    assert page.locator("[data-testid=state-pill]").inner_text().strip() == "SIMBA is working"
    assert "simba-halo" in page.locator("[data-testid=frame-lion]").get_attribute("class")


def test_stop_is_in_the_header_with_the_steps_own_words(page, static_site, backend) -> None:
    start(page, static_site, backend, [*started(), ("step.presented", CHOOSE)])
    page.wait_for_selector("[data-testid=choice-cards]")
    stop = page.locator("[data-testid=frame-stop]")
    assert stop.inner_text().strip() == "Stop this"
    # And only there: the step does not offer a second one.
    assert page.get_by_role("button", name="Stop this").count() == 1
    stop.click()
    page.wait_for_selector("text=I've stopped, as you asked.")


# --- the fold ---------------------------------------------------------------


def test_the_simplest_level_folds_the_sides_away(page, static_site, backend) -> None:
    start(page, static_site, backend, [*started(), ("load.updated", {"score": 0.8, "level": 3,
                                                                    "reason": "busy"}),
                                       ("step.presented", CHOOSE)])
    page.wait_for_selector("[data-testid=busy-line]")
    page.wait_for_timeout(900)
    assert page.locator("[data-testid=busy-line]").inner_text().startswith(
        "This website is busy, so I'm showing you less.")
    centre = page.locator("[data-testid=frame-centre]").bounding_box()
    assert centre["width"] > 1100
    tiles = page.locator("[data-testid=card]")
    assert tiles.count() == 3 and tiles.first.bounding_box()["height"] >= 190
    page.locator("[data-testid=show-more]").click()
    page.wait_for_timeout(900)
    assert page.locator("[data-testid=frame-centre]").bounding_box()["width"] < 700
    assert page.locator("[data-testid=the-card]").bounding_box()["x"] > 800


def test_a_final_screen_is_never_folded(page, static_site, backend) -> None:
    start(page, static_site, backend, [*started(), ("load.updated", {"score": 0.9, "level": 3,
                                                                    "reason": "busy"}),
                                       ("step.presented", FINAL)])
    page.wait_for_selector("[data-testid=final-check]")
    page.wait_for_timeout(900)
    assert page.locator("[data-testid=the-card]").bounding_box()["width"] > 300


# --- fit --------------------------------------------------------------------


@pytest.mark.parametrize("scale", ["100", "125", "150"])
def test_every_task_screen_fits_the_window(page, static_site, backend, scale) -> None:
    page.set_viewport_size(SIZES[scale])
    for script in ([*started(), row(1, "Opening daewoo.com.pk")],
                   [*started(), ("step.presented", CHOOSE)],
                   [*started(), ("step.presented", SEATS)],
                   [*started(), ("step.presented", FINAL)]):
        start(page, static_site, backend, script)
        page.wait_for_selector("[data-testid=task-frame]")
        page.wait_for_timeout(1000)
        size = page.evaluate("[document.documentElement.scrollHeight, innerHeight, "
                             "document.documentElement.scrollWidth, innerWidth]")
        assert size[0] <= size[1] + 1, f"{scale}%: page scrolls {size}"
        assert size[2] <= size[3] + 1, f"{scale}%: page is wider than the window {size}"
        centre = page.locator("[data-frame-scroll]")
        assert centre.evaluate("e => e.scrollHeight <= e.clientHeight + 2"), \
            f"{scale}%: the middle panel scrolls"


# --- the other shapes, and what happens after "do it" -----------------------

RECEIPT_FINAL = step(5, "I'll place this order on readings.com.pk for Rs 1,445.", final=[
    {"label": "You chose", "value": "The Alchemist, paperback"},
    {"label": "Items in cart", "value": "1"},
    {"label": "Delivery", "value": "Rs 150"}, {"label": "Paying", "value": "Cash on delivery"},
    {"label": "Amount", "value": "Rs 1,445"}, {"label": "Website", "value": "readings.com.pk"}],
    actions=[{"id": "confirm", "label": "Place the order", "kind": "primary"},
             {"id": "decline", "label": "Don't order", "kind": "primary"}])
ADDRESS = step(4, "Where should the book go?", fields=[
    {"id": "address", "label": "Your address", "type": "text", "value": ""},
    {"id": "city", "label": "City", "type": "text", "value": "Lahore"}],
    actions=[{"id": "confirm", "label": "Next", "kind": "primary"}, STOP])


def test_a_receipt_says_only_one_and_never_mistakes_how_many_for_what(
        page, static_site, backend) -> None:
    start(page, static_site, backend, [*started("Order the Alchemist"),
                                        ("step.presented", RECEIPT_FINAL)], goal="Order the Alchemist")
    page.wait_for_selector("[data-testid=final-check]")
    the_card = page.locator("[data-testid=the-card]")
    assert the_card.get_attribute("data-shape") == "receipt"
    item = page.locator("[data-testid=card-item]").inner_text()
    assert "The Alchemist, paperback" in item and "Only 1, as you asked" in item
    found = rows(page)
    assert found["delivery"] == "Rs 150" and found["payment"] == "Cash on delivery"
    assert page.locator("[data-testid=card-total]").inner_text().endswith("Rs 1,445")
    assert "Your order" in the_card.inner_text()


def test_the_address_and_the_city_are_both_on_the_card(page, static_site, backend) -> None:
    start(page, static_site, backend, [*started("Order the Alchemist"), ("step.presented", ADDRESS),
                                       ("step.presented", RECEIPT_FINAL)], goal="Order the Alchemist")
    page.wait_for_selector("[data-testid=step-shell]")
    assert rows(page)["deliverTo"] == "waiting"
    page.get_by_label("Your address").fill("House 12, Garden Town")
    page.get_by_role("button", name="Next").click()
    page.wait_for_selector("[data-testid=final-check]")
    # The final screen has no address of its own, so what was typed is still there.
    assert rows(page)["deliverTo"] == "House 12, Garden Town, Lahore"


def test_a_bill_and_an_answer_have_their_own_cards(page, static_site, backend) -> None:
    start(page, static_site, backend, [*started("Check my electricity bill, reference 1234567890"),
                                       row(1, "Opening the billing site")],
          goal="Check my electricity bill, reference 1234567890")
    page.wait_for_selector("[data-testid=the-card]")
    assert page.locator("[data-testid=the-card]").get_attribute("data-shape") == "bill"
    assert rows(page)["reference"] == "ending 7890"
    start(page, static_site, backend, [*started("When is the next train to Karachi"),
                                       row(1, "Opening the timetable")],
          goal="When is the next train to Karachi")
    page.wait_for_selector("[data-testid=the-card]")
    # A look-up that says "train" still asks about a journey: a ticket.
    assert page.locator("[data-testid=the-card]").get_attribute("data-shape") == "ticket"
    start(page, static_site, backend, [*started("What is the weather in Lahore"),
                                       row(1, "Opening the weather page")],
          goal="What is the weather in Lahore")
    page.wait_for_selector("[data-testid=the-card]")
    assert page.locator("[data-testid=the-card]").get_attribute("data-shape") == "answer"
    assert "Your answer" in page.locator("[data-testid=the-card]").inner_text()


def test_after_do_it_the_card_gets_its_number_and_moves_into_my_bookings(
        page, static_site, backend) -> None:
    done = ("task.completed", {"summary": GOAL, "duration_ms": 1, "steps_taken": 3, "llm_calls": 0,
                               "replayed": False,
                               "confirmation": "Booking number DW-48213. Your seat is confirmed."})
    start(page, static_site, backend, [*started(), ("step.presented", FINAL), done])
    page.wait_for_selector("[data-testid=final-check]")
    page.get_by_role("button", name="Book it").click()
    flight = page.wait_for_selector("[data-testid=booked-flight]", timeout=5000)
    text = flight.inner_text()
    assert "DW-48213" in text and "Saved in My bookings" in text and "Complete" in text
    # It takes no presses, and it is gone within four seconds.
    assert flight.evaluate("e => getComputedStyle(e).pointerEvents") == "none"
    page.wait_for_selector("[data-testid=booked-flight]", state="detached", timeout=6000)


def test_the_card_does_not_fly_under_reduced_motion(playwright_instance, static_site, backend) -> None:
    browser = playwright_instance.chromium.launch()
    context = browser.new_context(viewport=SIZES["100"], reduced_motion="reduce")
    for flag in ("__simbaSettleMs = 0", "__simbaWelcome = false", "__simbaSplash = false"):
        context.add_init_script(f"window.{flag}")
    page = context.new_page()
    done = ("task.completed", {"summary": GOAL, "duration_ms": 1, "steps_taken": 3, "llm_calls": 0,
                               "replayed": False, "confirmation": "Booking number DW-48213."})
    start(page, static_site, backend, [*started(), ("step.presented", FINAL), done])
    page.wait_for_selector("[data-testid=final-check]")
    page.get_by_role("button", name="Book it").click()
    page.wait_for_selector("text=Booking number DW-48213")
    assert page.locator("[data-testid=booked-flight]").count() == 0
    browser.close()


def test_a_final_screen_with_no_details_does_not_claim_the_card_is_complete(
        page, static_site, backend) -> None:
    bare = {**FINAL, "final": []}
    start(page, static_site, backend, [*started(), ("step.presented", bare)])
    page.wait_for_selector("[data-testid=final-check]")
    assert page.locator("[data-testid=the-card]").get_attribute("data-complete") is None
    assert "Complete" not in page.locator("[data-testid=the-card]").inner_text()


PICTURE = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJg"
           "gg==")


def test_the_real_page_opens_in_the_middle_and_what_was_typed_is_kept(page, static_site, backend) -> None:
    preview = ("page.preview", {"screenshot": PICTURE, "highlight": {"x": 0, "y": 0, "w": 0, "h": 0},
                                 "caption": ""})
    typed = step(3, "What is your name?", fields=[
        {"id": "name", "label": "Full name", "type": "text", "value": ""}],
        actions=[{"id": "confirm", "label": "Next", "kind": "primary"}, STOP])
    start(page, static_site, backend, [*started(), preview, ("step.presented", typed)])
    page.wait_for_selector("[data-testid=step-shell]")
    page.get_by_label("Full name").fill("Muhammad Raham")
    page.get_by_role("button", name="See the real page").click()
    page.wait_for_selector("[data-testid=live-page-centre]")
    assert page.locator("[data-testid=live-page-centre] img").is_visible()
    # Only the middle panel is given to it: the other two stay where they are.
    assert page.locator("[data-testid=so-far]").is_visible() and page.locator("[data-testid=the-card]").is_visible()
    assert page.get_by_role("button", name="Hide the real page").is_visible()
    page.get_by_role("button", name="Hide the real page").click()
    page.wait_for_selector("[data-testid=step-shell]")
    assert page.get_by_label("Full name").input_value() == "Muhammad Raham"
