"""Show me once (2026-11-04): watching a helper do a task once, and keeping it.

The helper's presses here are real ones — Playwright's mouse and keyboard on
the billing copy in Chromium — and the backend reads them through the same
script in the page and the same perception the real window uses. What is kept
is checked to be perception's role and label, never an id or a selector; a
typed value is asked about; a password is never read; and the answer is what
the helper pointed at.
"""

import asyncio
import json
from pathlib import Path

import pytest
from playwright.async_api import Page, async_playwright

from backend.orchestrator import teach as teaching
from backend.orchestrator import voice
from backend.orchestrator.routines import RoutineStore, Step
from backend.orchestrator.teach import (
    Draft,
    Taught,
    element_at,
    element_over,
    labels_for,
    teach,
    twin_index,
)
from backend.orchestrator.test_billing import billing_replica  # noqa: F401
from backend.orchestrator.test_checklist import run
from backend.perception.content import Content, Pair
from backend.perception.serializer import Element

REFERENCE = "04141234567890"

pytestmark = pytest.mark.skipif(not RoutineStore(Path("unused")).available,
                                reason="routines need the operating system's encryption")


class Overlay:
    """The overlay's side of a teaching conversation: what the backend sent,
    and what the test has the overlay say."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []
        self.incoming: asyncio.Queue = asyncio.Queue()

    async def send(self, message_type: str, payload) -> None:
        self.sent.append((message_type, json.loads(payload.model_dump_json())))

    async def next_message(self) -> dict:
        return await self.incoming.get()

    def say(self, message_type: str, payload: dict) -> None:
        self.incoming.put_nowait({"type": message_type, "payload": payload})

    def of(self, message_type: str) -> list[dict]:
        return [payload for kind, payload in self.sent if kind == message_type]

    def types(self) -> list[str]:
        return [kind for kind, _ in self.sent]

    def bar(self) -> dict:
        return self.of("teach.watching")[-1]

    async def until(self, ready, timeout: float = 20.0) -> None:
        deadline = asyncio.get_running_loop().time() + timeout
        while not ready(self):
            if asyncio.get_running_loop().time() > deadline:
                raise AssertionError(f"waited {timeout}s; sent so far: {self.types()}")
            await asyncio.sleep(0.05)


async def _on_page(url: str, helper, store: RoutineStore, *, live: bool = False):
    """Teach on `url` with `helper(page, overlay)` doing what a helper does."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        overlay = Overlay()
        try:
            job = asyncio.create_task(teach(page, overlay, url, store))
            await overlay.until(lambda o: o.of("teach.watching") or o.of("help.requested"))
            await helper(page, overlay)
            kept = await asyncio.wait_for(job, 30)
            return kept, overlay, page.url
        finally:
            await browser.close()


async def _show_the_bill(page: Page, overlay: Overlay, *, same: bool = False,
                         point: str = "14,382", name: str = "My bill") -> None:
    await page.get_by_role("button", name="Accept all cookies").click()
    await overlay.until(lambda o: len(o.bar()["lines"]) == 1)
    await page.get_by_role("textbox", name="Reference No.").fill(REFERENCE)
    await page.get_by_role("button", name="Check Bill").click()
    await page.wait_for_url("**/bill")
    await overlay.until(lambda o: o.bar()["question"] is not None and len(o.bar()["lines"]) == 3)
    question = overlay.bar()["question"]
    overlay.say("teach.answer", {"action": "same" if same else "ask",
                                 "step": question["step"]})
    await overlay.until(lambda o: o.bar()["question"] is None)
    overlay.say("teach.answer", {"action": "finish"})
    await overlay.until(lambda o: o.bar()["pointing"])
    await page.get_by_text(point, exact=True).first.click()
    await overlay.until(lambda o: o.of("step.presented"))
    overlay.say("step.response", {"step_index": 1, "action_id": "confirm",
                                  "input_values": {"name": name, "answer": "Amount due"}})


def test_a_helper_shows_the_bill_once_and_it_is_kept_by_role_and_label(
        billing_replica: str, tmp_path: Path) -> None:  # noqa: F811
    store = RoutineStore(tmp_path / "routines.json")
    kept, overlay, _ = run(_on_page(billing_replica, _show_the_bill, store))

    assert kept is not None and store.all() == [kept]
    assert kept.label == "My bill" and kept.start.startswith(billing_replica)
    assert [(s.kind, s.role, s.label) for s in kept.steps] == [
        ("click", "button", "Accept all cookies"),
        ("fill", "textbox", "Reference No."),
        ("click", "button", "Check Bill"),
    ]
    # Asked each time, so the number is not kept; and the search is checked
    # by where it went.
    fill = kept.steps[1]
    assert fill.ask and fill.value is None
    assert kept.steps[2].expect_url == "/bill"
    # The answer is the page's own label for what was pointed at.
    assert (kept.answer.reads, kept.answer.name) == ("P/WITHIN", "Amount due")
    # Nothing the page would call an id or a selector, anywhere in it.
    written = [value for step in kept.steps for value in (*step.__dict__.values(), *step.shows)
               if isinstance(value, str)]
    assert not [text for text in written if "#" in text or "[" in text]
    # Kept encrypted: no label of the site is readable in the file.
    assert "Reference No." not in store.path.read_text(encoding="utf-8")


def test_the_bar_says_what_was_kept_and_asks_about_the_typed_value(
        billing_replica: str, tmp_path: Path) -> None:  # noqa: F811
    store = RoutineStore(tmp_path / "routines.json")
    _, overlay, _ = run(_on_page(billing_replica, _show_the_bill, store))

    bars = overlay.of("teach.watching")
    asked = next(bar["question"] for bar in bars if bar["question"])
    assert asked == {"step": 1, "label": "Reference No.", "value": REFERENCE, "kind": "typed"}
    # The bar's lines are the read-back's words, as each move came in.
    assert bars[-1]["lines"][0] == voice.routine_line(
        Step("click", "button", "Accept all cookies"), consent=True)
    # The read-back: each move in plain words, then the answer.
    readback = overlay.of("step.presented")[0]
    assert readback["routine"] == [
        "Ask about cookies, and press Accept all cookies if the answer is yes.",
        "Ask what to type in Reference No., and type it.",
        "Press Check Bill.",
        "Read the answer from P/WITHIN on the page. It says 14,382 now.",
    ]
    assert [f["id"] for f in readback["fields"]] == ["name", "answer"]
    assert overlay.of("task.completed")[0]["explanation"] == voice.taught_kept("My bill")


def test_a_value_the_same_every_time_is_kept(billing_replica: str,
                                             tmp_path: Path) -> None:  # noqa: F811
    async def helper(page, overlay):
        await _show_the_bill(page, overlay, same=True)

    kept, overlay, _ = run(_on_page(billing_replica, helper, RoutineStore(tmp_path / "r.json")))
    assert kept.steps[1].value == REFERENCE and not kept.steps[1].ask
    assert overlay.of("step.presented")[0]["routine"][1] == f"Type {REFERENCE} in Reference No."


def test_finish_waits_for_the_question_and_for_something_shown(
        billing_replica: str, tmp_path: Path) -> None:  # noqa: F811
    async def helper(page, overlay):
        overlay.say("teach.answer", {"action": "finish"})
        await overlay.until(lambda o: o.bar()["note"] == voice.TEACH_NOTHING_YET)
        await page.get_by_role("textbox", name="Reference No.").fill(REFERENCE)
        await page.get_by_role("textbox", name="Reference No.").press("Tab")
        await overlay.until(lambda o: o.bar()["question"] is not None)
        overlay.say("teach.answer", {"action": "finish"})
        await overlay.until(lambda o: o.bar()["note"] == voice.TEACH_ANSWER_FIRST)
        assert not overlay.bar()["pointing"]
        overlay.say("teach.answer", {"action": "cancel"})

    kept, overlay, _ = run(_on_page(billing_replica, helper, RoutineStore(tmp_path / "r.json")))
    assert kept is None
    assert overlay.of("task.failed")[0]["reason"] == voice.YOU_STOPPED


def test_typing_into_one_box_twice_is_one_value(billing_replica: str,
                                                tmp_path: Path) -> None:  # noqa: F811
    async def helper(page, overlay):
        box = page.get_by_role("textbox", name="Reference No.")
        await box.fill("0414")
        await box.press("Tab")
        await overlay.until(lambda o: o.bar()["question"] is not None)
        await box.fill(REFERENCE)
        await box.press("Tab")
        await overlay.until(lambda o: o.bar()["question"]["value"] == REFERENCE)
        assert len(overlay.bar()["lines"]) == 1
        overlay.say("teach.answer", {"action": "cancel"})

    run(_on_page(billing_replica, helper, RoutineStore(tmp_path / "r.json")))


def test_enter_in_a_box_is_kept_as_a_press_and_still_searches(
        billing_replica: str, tmp_path: Path) -> None:  # noqa: F811
    async def helper(page, overlay):
        box = page.get_by_role("textbox", name="Reference No.")
        await box.fill(REFERENCE)
        await box.press("Enter")
        await page.wait_for_url("**/bill")
        await overlay.until(lambda o: len(o.bar()["lines"]) == 2)
        assert overlay.bar()["lines"][1] == "Press Enter in Reference No."
        overlay.say("teach.answer", {"action": "cancel"})

    _, _, url = run(_on_page(billing_replica, helper, RoutineStore(tmp_path / "r.json")))
    assert url.endswith("/bill")


def test_a_password_is_never_read_off_the_page(tmp_path: Path) -> None:
    page_html = ("data:text/html,<form><label>Name <input name=user></label>"
                 "<label>Password <input type=password name=pw></label>"
                 "<button type=button onclick=\"document.title='in'\">Sign in</button></form>")

    async def helper(page, overlay):
        await page.get_by_label("Password").fill("hunter2-secret")
        await page.get_by_role("button", name="Sign in").click()
        await overlay.until(lambda o: len(o.bar()["lines"]) == 2)
        overlay.say("teach.answer", {"action": "cancel"})

    _, overlay, _ = run(_on_page(page_html, helper, RoutineStore(tmp_path / "r.json")))
    assert "hunter2" not in json.dumps(overlay.sent)
    # No question about it, and the bar says a password goes there.
    assert overlay.bar()["question"] is None
    assert overlay.bar()["lines"][0].startswith("Type the password in Password.")


# --- finding what was pressed, on perception's reading -------------------------------


def _element(id: int, role: str, label: str, rect, qualifier: str = "") -> Element:
    return Element(id=id, role=role, label=label, type="", tag="", input_type=None,
                   rect=rect, qualifier=qualifier)


def test_a_press_is_the_smallest_element_under_the_pointer() -> None:
    row = _element(1, "row", "", (0, 100, 800, 40))
    link = _element(2, "link", "Open", (20, 105, 60, 20))
    other = _element(3, "button", "Go", (600, 105, 60, 20))
    assert element_at([row, link, other], 30, 110) is link
    assert element_at([row, link, other], 300, 110) is row
    assert element_at([row, link, other], 900, 900) is None


def test_a_box_is_the_element_perception_read_at_the_same_place() -> None:
    field = _element(1, "textbox", "From", (100, 100, 200, 30))
    near = _element(2, "textbox", "To", (100, 140, 200, 30))
    assert element_over([field, near], {"x": 101, "y": 100, "w": 200, "h": 30}) is field
    # Half a box away is not the same box.
    assert element_over([field], {"x": 250, "y": 100, "w": 200, "h": 30}) is None


def test_which_of_several_alike_is_kept() -> None:
    first = _element(1, "link", "", (0, 0, 10, 10))
    second = _element(2, "link", "", (0, 20, 10, 10))
    day = _element(3, "option", "30", (0, 40, 10, 10), "previous month")
    month = _element(4, "option", "30", (0, 60, 10, 10))
    elements = [first, second, day, month]
    assert twin_index(elements, second) == 1
    # A day of last month is not a twin of this month's day.
    assert twin_index(elements, month) == 0


def test_the_answer_is_found_by_the_page_s_own_label() -> None:
    content = Content(pairs=[Pair("P/WITHIN", "14,382"), Pair("P/AFTER", "14,957"),
                             Pair("Note", "Pay 14,382 by the due date")])
    assert labels_for(content, " 14,382 ") == ["P/WITHIN"]
    assert labels_for(content, "14,957") == ["P/AFTER"]
    assert labels_for(content, "nothing like it") == []


def test_what_the_next_move_waits_for_is_worked_out_from_what_appeared() -> None:
    before = frozenset({("textbox", "From")})
    after = frozenset({("textbox", "From"), ("option", "LAHORE JN")})
    draft = Draft(start="https://x/")
    draft.taught = [
        Taught(Step("fill", "textbox", "From"), "https://x/train", before, typed="Lahore",
               same=True),
        Taught(Step("click", "option", "LAHORE JN"), "https://x/train", after),
    ]
    from backend.orchestrator.routines import Answer
    draft.answer = Answer("Trains", "Train No.")
    routine = draft.routine("https://x/train")
    assert routine.steps[0].expect_label == "LAHORE JN" and routine.steps[0].list_opens
    assert routine.steps[0].value == "Lahore"
    assert routine.steps[1].expect_url is None


def test_the_recorder_script_is_the_one_installed() -> None:
    # One script, guarded so a page that has it twice holds a press once.
    assert "window.__simbaRecorder" in teaching.RECORDER_JS
    assert teaching.BINDING in teaching.RECORDER_JS


# --- the answer, pointed at ------------------------------------------------------------


def test_pointing_lets_nothing_through_and_a_miss_is_said(billing_replica: str,
                                                          tmp_path: Path) -> None:  # noqa: F811
    async def helper(page, overlay):
        await page.get_by_role("textbox", name="Reference No.").fill(REFERENCE)
        await page.get_by_role("button", name="Check Bill").click()
        await page.wait_for_url("**/bill")
        await overlay.until(lambda o: o.bar()["question"] is not None)
        overlay.say("teach.answer", {"action": "ask", "step": 0})
        overlay.say("teach.answer", {"action": "finish"})
        await overlay.until(lambda o: o.bar()["pointing"])
        # A link pressed while pointing is not followed.
        await page.get_by_role("link", name="View full bill detail").click()
        await overlay.until(lambda o: o.bar()["note"] == voice.POINT_AGAIN)
        assert page.url.endswith("/bill") and overlay.bar()["pointing"]
        # Then the amount itself.
        await page.get_by_text("15-09-2026", exact=True).first.click()
        await overlay.until(lambda o: o.of("step.presented"))
        overlay.say("step.response", {"step_index": 1, "action_id": "confirm",
                                      "input_values": {"name": "Due date", "answer": ""}})

    kept, overlay, url = run(_on_page(billing_replica, helper,
                                      RoutineStore(tmp_path / "r.json")))
    assert url.endswith("/bill")
    # The page's own label, and its name when the helper gave none.
    assert kept.answer == type(kept.answer)(name="DUE DT", reads="DUE DT")
    # Nothing pressed while pointing became part of the routine.
    assert [s.label for s in kept.steps] == ["Reference No.", "Check Bill"]


def test_finish_pressed_while_the_page_loads_still_points(
        billing_replica: str, tmp_path: Path) -> None:  # noqa: F811
    async def helper(page, overlay):
        # Searching with no number sends the page back to itself, with a
        # message; Finish is pressed while that page is still on its way.
        await page.get_by_role("button", name="Check Bill").click()
        await overlay.until(lambda o: len(o.bar()["lines"]) == 1)
        overlay.say("teach.answer", {"action": "finish"})
        await overlay.until(lambda o: o.bar()["pointing"])
        await page.wait_for_load_state()
        # An empty box is nothing to read, and is said to be: the new page
        # knew it was for pointing.
        await page.get_by_role("textbox", name="Reference No.").click()
        await overlay.until(lambda o: o.bar()["note"] == voice.POINT_AGAIN)
        overlay.say("teach.answer", {"action": "cancel"})

    kept, overlay, _ = run(_on_page(billing_replica, helper, RoutineStore(tmp_path / "r.json")))
    assert kept is None and not overlay.of("step.presented")


def test_a_routine_with_no_name_is_asked_for_one(billing_replica: str,
                                                tmp_path: Path) -> None:  # noqa: F811
    async def helper(page, overlay):
        await page.get_by_role("textbox", name="Reference No.").fill(REFERENCE)
        await page.get_by_role("button", name="Check Bill").click()
        await page.wait_for_url("**/bill")
        await overlay.until(lambda o: o.bar()["question"] is not None)
        overlay.say("teach.answer", {"action": "same", "step": 0})
        overlay.say("teach.answer", {"action": "finish"})
        await overlay.until(lambda o: o.bar()["pointing"])
        await page.get_by_text("14,382", exact=True).first.click()
        await overlay.until(lambda o: o.of("step.presented"))
        overlay.say("step.response", {"step_index": 1, "action_id": "confirm",
                                      "input_values": {"name": "   ", "answer": "Amount"}})
        await overlay.until(lambda o: len(o.of("step.presented")) == 2)
        assert overlay.of("step.presented")[1]["note"] == voice.NAME_IT_FIRST
        overlay.say("step.response", {"step_index": 2, "action_id": "confirm",
                                      "input_values": {"name": "Bill", "answer": "Amount"}})

    kept, _, _ = run(_on_page(billing_replica, helper, RoutineStore(tmp_path / "r.json")))
    assert kept.label == "Bill" and kept.answer.name == "Amount"


# --- safety, while teaching -----------------------------------------------------------


async def _to_the_results(page, overlay) -> None:
    await page.get_by_role("textbox", name="Reference No.").fill(REFERENCE)
    await page.get_by_role("button", name="Check Bill").click()
    await page.wait_for_url("**/bill")
    await overlay.until(lambda o: len(o.bar()["lines"]) == 2)


def test_on_a_live_site_a_press_that_pays_is_never_made(
        billing_replica: str, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    # The billing copy, taken for a live site: the rule is the host's, and
    # this copy's host is ours.
    monkeypatch.setattr(teaching, "on_replica", lambda url: False)

    async def helper(page, overlay):
        await _to_the_results(page, overlay)
        await page.get_by_role("link", name="Pay this bill").click()
        await overlay.until(lambda o: o.of("help.requested"))

    store = RoutineStore(tmp_path / "r.json")
    kept, overlay, url = run(_on_page(billing_replica, helper, store))
    assert kept is None and store.all() == []
    assert overlay.of("help.requested")[0]["reason"] == voice.TEACH_STOPPED_CHANGE
    # Held in the page and never let through: still on the results.
    assert url.endswith("/bill")
    # And nothing more was kept for it.
    assert len(overlay.bar()["lines"]) == 2


def test_on_our_copy_a_press_that_pays_is_kept_as_a_change(
        billing_replica: str, tmp_path: Path) -> None:  # noqa: F811
    async def helper(page, overlay):
        await _to_the_results(page, overlay)
        await page.get_by_role("link", name="Pay this bill").click()
        await page.wait_for_url("**/bill/pay**")
        await overlay.until(lambda o: len(o.bar()["lines"]) == 3)
        overlay.say("teach.answer", {"action": "cancel"})

    _, overlay, url = run(_on_page(billing_replica, helper, RoutineStore(tmp_path / "r.json")))
    assert "/bill/pay" in url
    assert overlay.bar()["lines"][2] == voice.routine_line(
        Step("click", "link", "Pay this bill", changes=True))
    assert "final screen" in overlay.bar()["lines"][2]


def test_a_card_box_stops_watching_before_anything_is_typed(tmp_path: Path) -> None:
    page_html = ("data:text/html,<form><label>Card number "
                 "<input name=pan autocomplete=cc-number></label></form>")

    async def helper(page, overlay):
        await page.get_by_label("Card number").click()
        await overlay.until(lambda o: o.of("help.requested"))
        await page.get_by_label("Card number").fill("4111111111111111")
        await asyncio.sleep(0.5)

    kept, overlay, _ = run(_on_page(page_html, helper, RoutineStore(tmp_path / "r.json")))
    assert kept is None
    assert overlay.of("help.requested")[0]["reason"] == voice.TEACH_STOPPED_CARD
    assert "4111" not in json.dumps(overlay.sent)


def test_a_card_box_is_known_by_its_name_too(tmp_path: Path) -> None:
    page_html = "data:text/html,<label>CVV <input name=cvv></label>"

    async def helper(page, overlay):
        await page.get_by_label("CVV").click()
        await overlay.until(lambda o: o.of("help.requested"))

    _, overlay, _ = run(_on_page(page_html, helper, RoutineStore(tmp_path / "r.json")))
    assert overlay.of("help.requested")[0]["reason"] == voice.TEACH_STOPPED_CARD


def test_on_a_live_site_enter_that_would_submit_a_change_is_held(tmp_path: Path) -> None:
    # A data: page is not one of ours, so it is a live site to the rule.
    page_html = ("data:text/html,<form action='https://example.invalid/order'>"
                 "<label>Quantity <input name=q></label><button>Place order</button></form>")

    async def helper(page, overlay):
        await page.get_by_label("Quantity").fill("2")
        await page.get_by_label("Quantity").press("Enter")
        await overlay.until(lambda o: o.of("help.requested"))

    _, overlay, url = run(_on_page(page_html, helper, RoutineStore(tmp_path / "r.json")))
    assert overlay.of("help.requested")[0]["reason"] == voice.TEACH_STOPPED_CHANGE
    assert url.startswith("data:")


def test_no_room_on_the_home_screen_and_nothing_is_watched(
        billing_replica: str, tmp_path: Path) -> None:  # noqa: F811
    async def helper(page, overlay):
        await overlay.until(lambda o: o.of("help.requested"))

    async def full():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page()
            overlay = Overlay()
            kept = await teach(page, overlay, billing_replica,
                               RoutineStore(tmp_path / "r.json"), tiles=3)
            await browser.close()
            return kept, overlay

    kept, overlay = run(full())
    assert kept is None and overlay.types() == ["help.requested"]
    assert overlay.of("help.requested")[0]["reason"] == voice.TEACH_NO_ROOM


# --- undoing the last thing (2026-11-10) -------------------------------------------------
#
# A helper who pressed the wrong thing takes it back from the bar. The routine
# that is kept must still match the page: a typed value taken back is cleared
# from its box; a press that moved the website to another page takes the
# website back, and is only taken off the list once the page is really the
# earlier one; when it cannot be, the bar says so and offers Start again, and
# nothing is let through until then.


def _kept(overlay: Overlay) -> list[str]:
    return overlay.bar().get("kept") or []


def test_the_bar_lists_each_thing_kept_in_a_few_words_newest_last(
        billing_replica: str, tmp_path: Path) -> None:  # noqa: F811
    async def helper(page, overlay):
        await page.get_by_role("button", name="Accept all cookies").click()
        await page.get_by_role("textbox", name="Reference No.").fill(REFERENCE)
        await page.get_by_role("button", name="Check Bill").click()
        await page.wait_for_url("**/bill")
        await overlay.until(lambda o: len(_kept(o)) == 3)
        overlay.say("teach.answer", {"action": "cancel"})

    _, overlay, _ = run(_on_page(billing_replica, helper, RoutineStore(tmp_path / "r.json")))
    assert _kept(overlay) == ["Pressed Accept all cookies.", "Typed in Reference No.",
                              "Pressed Check Bill."]
    # Beside the read-back's longer lines, one for one.
    assert len(overlay.bar()["lines"]) == 3
    # What was typed is in the question, where the helper decides about it,
    # never in the list.
    assert REFERENCE not in json.dumps(_kept(overlay))
    assert not overlay.bar().get("start_again")


def test_a_password_is_listed_as_a_password_and_nothing_else(tmp_path: Path) -> None:
    page_html = ("data:text/html,<form><label>Name <input name=user></label>"
                 "<label>Password <input type=password name=pw></label>"
                 "<button type=button onclick=\"document.title='in'\">Sign in</button></form>")

    async def helper(page, overlay):
        await page.get_by_label("Password").fill("hunter2-secret")
        await page.get_by_role("button", name="Sign in").click()
        await overlay.until(lambda o: len(_kept(o)) == 2)
        overlay.say("teach.answer", {"action": "cancel"})

    _, overlay, _ = run(_on_page(page_html, helper, RoutineStore(tmp_path / "r.json")))
    assert _kept(overlay) == ["Typed a password.", "Pressed Sign in."]
    assert "hunter2" not in json.dumps(overlay.sent)


def test_undo_takes_a_typed_value_off_the_list_and_out_of_its_box(
        billing_replica: str, tmp_path: Path) -> None:  # noqa: F811
    async def helper(page, overlay):
        box = page.get_by_role("textbox", name="Reference No.")
        await box.fill(REFERENCE)
        await box.press("Tab")
        await overlay.until(lambda o: o.bar()["question"] is not None)
        overlay.say("teach.answer", {"action": "undo"})
        await overlay.until(lambda o: _kept(o) == [] and o.bar()["question"] is None)
        # The page matches the list: the box is empty again.
        assert await box.input_value() == ""
        assert overlay.bar()["lines"] == []
        # Typed again, it is kept again, and asked about again.
        await box.fill(REFERENCE)
        await box.press("Tab")
        await overlay.until(lambda o: o.bar()["question"] is not None)
        assert _kept(overlay) == ["Typed in Reference No."]
        overlay.say("teach.answer", {"action": "cancel"})

    run(_on_page(billing_replica, helper, RoutineStore(tmp_path / "r.json")))


def test_undo_of_a_press_that_moved_the_page_takes_the_website_back(
        billing_replica: str, tmp_path: Path) -> None:  # noqa: F811
    """The bill shown, the search taken back, shown again, kept, and run
    from its tile five times: the routine after an undo is the routine."""
    from backend.orchestrator.test_routine_run import go as run_routine

    async def helper(page, overlay):
        await page.get_by_role("button", name="Accept all cookies").click()
        await page.get_by_role("textbox", name="Reference No.").fill(REFERENCE)
        await page.get_by_role("button", name="Check Bill").click()
        await page.wait_for_url("**/bill")
        await overlay.until(lambda o: len(_kept(o)) == 3)
        overlay.say("teach.answer", {"action": "undo"})
        await overlay.until(lambda o: len(_kept(o)) == 2)
        # Really the earlier page: the form, with the number still in it.
        assert page.url.rstrip("/") == billing_replica.rstrip("/")
        assert await page.get_by_role("textbox", name="Reference No.").input_value() == REFERENCE
        assert _kept(overlay) == ["Pressed Accept all cookies.", "Typed in Reference No."]
        assert not overlay.bar().get("start_again") and overlay.bar()["note"] is None
        # Done again: kept once, not twice.
        await page.get_by_role("button", name="Check Bill").click()
        await page.wait_for_url("**/bill")
        await overlay.until(lambda o: len(_kept(o)) == 3)
        question = overlay.bar()["question"]
        overlay.say("teach.answer", {"action": "ask", "step": question["step"]})
        await overlay.until(lambda o: o.bar()["question"] is None)
        overlay.say("teach.answer", {"action": "finish"})
        await overlay.until(lambda o: o.bar()["pointing"])
        await page.get_by_text("14,382", exact=True).first.click()
        await overlay.until(lambda o: o.of("step.presented"))
        overlay.say("step.response", {"step_index": 1, "action_id": "confirm",
                                      "input_values": {"name": "My bill", "answer": "Amount due"}})

    store = RoutineStore(tmp_path / "routines.json")
    kept, overlay, _ = run(_on_page(billing_replica, helper, store))
    assert kept is not None and [(s.kind, s.label) for s in kept.steps] == [
        ("click", "Accept all cookies"), ("fill", "Reference No."), ("click", "Check Bill")]
    assert kept.steps[2].expect_url == "/bill"
    # From the tile, five times over: each run finds the amount, with no model.
    for _ in range(5):
        done = run_routine(kept, [("confirm", {"value1": REFERENCE})])
        ending = done.of("task.completed")
        assert ending and ending[0]["findings"][0]["values"] == ["14,382"], done.types()
        assert ending[0]["llm_calls"] == 0


def test_undo_of_a_press_that_stayed_on_the_page_only_takes_it_off_the_list(
        billing_replica: str, tmp_path: Path) -> None:  # noqa: F811
    async def helper(page, overlay):
        await page.get_by_role("button", name="Accept all cookies").click()
        await overlay.until(lambda o: len(_kept(o)) == 1)
        overlay.say("teach.answer", {"action": "undo"})
        await overlay.until(lambda o: _kept(o) == [])
        assert page.url.rstrip("/") == billing_replica.rstrip("/")
        assert overlay.bar()["note"] is None and not overlay.bar().get("start_again")
        overlay.say("teach.answer", {"action": "cancel"})

    run(_on_page(billing_replica, helper, RoutineStore(tmp_path / "r.json")))


#: Pages served to the browser from the test (`_on_routed`), so a site that
#: is not one of ours can be shaped: a press that replaces the page in the
#: history, so going back cannot reach it; a sign-in page.
SITE = "http://undo.test"
SECOND = f"{SITE}/second"
PAGES = {
    f"{SITE}/first": (f"<h1>First</h1><button onclick=\"location.replace('{SECOND}')\">"
                      "Go on</button>"),
    SECOND: "<h1>Second</h1><button>Keep going</button>",
    f"{SITE}/login": ("<h1>Sign in</h1><label>Password <input type=password name=pw></label>"
                      f"<a href='{SITE}/home'>Go on</a>"),
    f"{SITE}/home": "<h1>Home</h1>",
}


async def _on_routed(url: str, helper, store: RoutineStore):
    """`_on_page`, on `PAGES`, which the browser is given from here."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 800})

        async def serve(route):
            html = PAGES.get(route.request.url)
            if html is None:
                await route.abort()
            else:
                await route.fulfill(status=200, content_type="text/html", body=html)

        await page.route(f"{SITE}/**", serve)
        overlay = Overlay()
        try:
            job = asyncio.create_task(teach(page, overlay, url, store))
            await overlay.until(lambda o: o.of("teach.watching") or o.of("help.requested"))
            await helper(page, overlay)
            kept = await asyncio.wait_for(job, 30)
            return kept, overlay, page.url
        finally:
            await browser.close()


def test_when_the_website_cannot_be_taken_back_it_is_said_and_start_again_is_offered(
        tmp_path: Path) -> None:
    async def helper(page, overlay):
        await page.get_by_role("button", name="Go on").click()
        await page.get_by_role("heading", name="Second").wait_for()
        await overlay.until(lambda o: len(_kept(o)) == 1)
        overlay.say("teach.answer", {"action": "undo"})
        await overlay.until(lambda o: o.bar().get("start_again"))
        # Said plainly, and nothing taken off a list the page no longer matches.
        assert overlay.bar()["note"] == voice.TEACH_NOT_BACK
        assert _kept(overlay) == ["Pressed Go on."]
        # Nothing is let through, and nothing kept, until Start again.
        await page.goto(SECOND)
        await page.get_by_role("button", name="Keep going").click()
        await asyncio.sleep(0.5)
        assert _kept(overlay) == ["Pressed Go on."]
        overlay.say("teach.answer", {"action": "finish"})
        await overlay.until(lambda o: o.bar()["note"] == voice.TEACH_START_AGAIN_FIRST)
        assert not overlay.bar()["pointing"]
        # Start again: the first page, with nothing kept, and watching as before.
        overlay.say("teach.answer", {"action": "restart"})
        await overlay.until(lambda o: not o.bar().get("start_again") and _kept(o) == [])
        await page.get_by_role("heading", name="First").wait_for()
        assert overlay.bar()["note"] is None
        await page.get_by_role("button", name="Go on").click()
        await overlay.until(lambda o: _kept(o) == ["Pressed Go on."])
        overlay.say("teach.answer", {"action": "cancel"})

    kept, overlay, _ = run(_on_routed(f"{SITE}/first", helper, RoutineStore(tmp_path / "r.json")))
    assert kept is None


def test_a_page_where_a_password_was_typed_cannot_be_put_back(tmp_path: Path) -> None:
    async def helper(page, overlay):
        await page.get_by_label("Password").fill("hunter2-secret")
        await page.get_by_role("link", name="Go on").click()
        await page.get_by_role("heading", name="Home").wait_for()
        await overlay.until(lambda o: len(_kept(o)) == 2)
        overlay.say("teach.answer", {"action": "undo"})
        await overlay.until(lambda o: o.bar().get("start_again"))
        # The sign-in page again, but not as it was: the password cannot be
        # put back, so the list stays and Start again is the way on.
        assert overlay.bar()["note"] == voice.TEACH_NOT_BACK
        assert _kept(overlay) == ["Typed a password.", "Opened Go on."]
        overlay.say("teach.answer", {"action": "cancel"})

    _, overlay, _ = run(_on_routed(f"{SITE}/login", helper, RoutineStore(tmp_path / "r.json")))
    assert "hunter2" not in json.dumps(overlay.sent)


def test_a_consent_press_pressed_again_after_going_back_is_one_press(
        billing_replica: str, tmp_path: Path) -> None:  # noqa: F811
    async def helper(page, overlay):
        await page.get_by_role("button", name="Accept all cookies").click()
        await page.get_by_role("textbox", name="Reference No.").fill(REFERENCE)
        await page.get_by_role("button", name="Check Bill").click()
        await page.wait_for_url("**/bill")
        await overlay.until(lambda o: len(_kept(o)) == 3)
        overlay.say("teach.answer", {"action": "undo"})
        await overlay.until(lambda o: len(_kept(o)) == 2)
        # The banner is back on the page it was pressed on; pressed again, it
        # is the same press, and the number the list keeps is in its box.
        await page.get_by_role("button", name="Accept all cookies").click()
        await asyncio.sleep(0.5)
        assert _kept(overlay) == ["Pressed Accept all cookies.", "Typed in Reference No."]
        await page.get_by_role("button", name="Check Bill").click()
        await page.wait_for_url("**/bill")
        await overlay.until(lambda o: len(_kept(o)) == 3)
        assert _kept(overlay)[2] == "Pressed Check Bill."
        overlay.say("teach.answer", {"action": "cancel"})

    run(_on_page(billing_replica, helper, RoutineStore(tmp_path / "r.json")))


def test_undo_with_nothing_kept_and_while_pointing_does_nothing(
        billing_replica: str, tmp_path: Path) -> None:  # noqa: F811
    async def helper(page, overlay):
        overlay.say("teach.answer", {"action": "undo"})
        await overlay.until(lambda o: len(o.of("teach.watching")) >= 2)
        assert _kept(overlay) == [] and overlay.bar()["note"] is None
        await _to_the_results(page, overlay)
        overlay.say("teach.answer", {"action": "ask", "step": 0})
        overlay.say("teach.answer", {"action": "finish"})
        await overlay.until(lambda o: o.bar()["pointing"])
        overlay.say("teach.answer", {"action": "undo"})
        await overlay.until(lambda o: len(o.of("teach.watching")) >= 6)
        assert overlay.bar()["pointing"] and len(_kept(overlay)) == 2
        assert page.url.endswith("/bill")
        overlay.say("teach.answer", {"action": "cancel"})

    run(_on_page(billing_replica, helper, RoutineStore(tmp_path / "r.json")))


def test_each_kind_of_move_is_said_in_a_few_words() -> None:
    said = voice.kept_line
    assert said(Step("fill", "textbox", "Reference No.")) == "Typed in Reference No."
    assert said(Step("fill", "textbox", "Password", secret=True)) == "Typed a password."
    assert said(Step("select", "combobox", "Class")) == "Chose from Class."
    assert said(Step("press", "textbox", "Reference No.", value="Enter")) == \
        "Pressed Enter in Reference No."
    assert said(Step("click", "link", "View full bill detail")) == "Opened View full bill detail."
    assert said(Step("click", "button", "Check Bill")) == "Pressed Check Bill."
    assert said(Step("click", "button", "")) == "Pressed the button with no name."
    assert said(Step("click", "textbox", "From")) == "Clicked in From."
    assert said(Step("click", "option", "15", day=True)) == "Chose 15 on the calendar."
    assert said(Step("click", "button", "Book train {}", row="Train No.")) == "Pressed Book train."
    # A sentence each, with one full stop, whatever the name ends in.
    for line in (said(Step("fill", "textbox", "Reference No.")), said(Step("click", "button",
                                                                           "Check Bill"))):
        assert line.endswith(".") and not line.endswith("..")
