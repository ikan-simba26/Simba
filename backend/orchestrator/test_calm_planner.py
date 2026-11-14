"""The AI planner asks once, and does not wander (2026-11-14).

Raham tried SIMBA in the real window on 2026-11-14: on Readings the AI asked
him to confirm about ten moves, went round Login and Close without making an
account, proposed opening the help chat, and took 95 to 113 seconds over some
choices. What has to hold now, through the real loop and a real browser, with
only the model scripted:

  * one read-back, one yes; then the moves that only look run by themselves,
    each a line of the checklist in plain words — never "Click element 13",
    never the site's own run of labels;
  * the person is stopped only for what is theirs: something only they can
    type, a press that changes something (the final screen), a consent;
  * the answer ends the run in one sentence, without one more question —
    unless the person asked to confirm every move;
  * three moves that get nowhere, or the same press a third time, and it
    stops and offers a helper's "Show me once";
  * a help-chat button is never offered, a dialog the goal needs is not
    "dismissed first", and a link that opens a dialog is not a dead link;
  * a provider that does not answer in time is moved on from, and rested.
"""

import asyncio
import functools
import http.server
import socketserver
import threading
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from backend.orchestrator import llm, voice
from backend.orchestrator.llm import Action, FallbackProvider, LLMError
from backend.orchestrator.llm_loop import (
    ON_TOP_BANNER,
    OpenGoalBrief,
    answer_sentence,
    render_page,
    restate,
    usable,
    without_widgets,
)
from backend.orchestrator.loop import run_brief, settled
from backend.orchestrator.test_verification import FakeConnection
from backend.perception.serializer import Element, is_dead_link

SHOP = """<!doctype html><html><head><title>Books</title></head><body>
<a href="#" role="button" data-toggle="modal" data-target="#login" id="open-login">Login</a>
<a href="#">Nowhere</a>
<form action="results.html"><input type="search" name="q" aria-label="Keyword | Title | Author">
</form>
<button id="noop" onclick="void 0">Offers</button>
<a href="index.html">Home</a>
<div id="login" hidden style="position:fixed;inset:0;z-index:50;background:#fff">
  <button onclick="document.getElementById('login').hidden=true">Close</button>
  <label>Email <input type="email" name="email"></label>
  <a href="#" data-toggle="modal" data-target="#register">Register.</a>
</div>
<script>document.getElementById('open-login').onclick =
  () => { document.getElementById('login').hidden = false; };</script>
</body></html>"""

RESULTS = """<!doctype html><html><head><title>Results</title></head><body>
<h1>Results</h1>
<p>Atomic Habits by James Clear. Our Price: Rs. 3,221 In Stock</p>
<label>Your name <input name="fullname"></label>
<button>Place order</button>
</body></html>"""

LATE = """<!doctype html><html><head><title>Late</title></head><body><h1>Shop</h1>
<script>setTimeout(() => { for (let i = 0; i < 30; i++) {
  const a = document.createElement('a'); a.href = 'p' + i; a.textContent = 'Book ' + i;
  document.body.appendChild(a); } }, 600);</script></body></html>"""


@pytest.fixture(scope="module")
def shop(tmp_path_factory) -> str:
    folder: Path = tmp_path_factory.mktemp("shop")
    (folder / "index.html").write_text(SHOP, encoding="utf-8")
    (folder / "results.html").write_text(RESULTS, encoding="utf-8")
    (folder / "late.html").write_text(LATE, encoding="utf-8")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(folder))
    server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/index.html"
    server.shutdown()


class Model:
    """The model: chooses by the words of an element, as the page lists it."""

    label = "Gemini"

    def __init__(self, script: list) -> None:
        self.script = list(script)
        self.pages: list[str] = []
        self.systems: list[str] = []
        self.feedback: list[str | None] = []

    async def decide(self, system_prompt, page, goal, feedback=None, history=None):
        self.systems.append(system_prompt)
        self.pages.append(page)
        self.feedback.append(feedback)
        if not self.script:
            raise AssertionError("the model was asked more often than the script allows")
        step = self.script.pop(0)
        if isinstance(step, Action):
            return step
        kind, words, value = step
        line = next(line for line in page.splitlines() if f"'{words}" in line)
        return Action(action=kind, element_id=int(line.split(".", 1)[0]), value=value,
                      reasoning="It is the next thing to do.")


class Person(FakeConnection):
    """Answers each thing that waits with the next id in `answers` (then
    "confirm"), typing `typed` into any box."""

    def __init__(self, answers: list[str] | None = None, typed: dict | None = None) -> None:
        super().__init__()
        self.answers = list(answers or [])
        self.typed = typed or {}

    async def receive(self, message_type, step_index=None, on_other=None):
        action = self.answers.pop(0) if self.answers else "confirm"
        return {"type": "step.response",
                "payload": {"step_index": step_index, "action_id": action,
                            "input_values": dict(self.typed)}}

    async def poll(self, seconds: float = 0.02) -> list[dict]:  # noqa: ARG002
        return []  # Pause is never pressed

    def asked(self) -> list[dict]:
        return [step for step in self.of("step.presented") if step["requires_confirmation"]]

    def lines(self) -> list[str]:
        return [step["instruction"] for step in self.of("step.presented")
                if not step["requires_confirmation"]]


def go(url: str, model: Model, person: Person | None = None, *, auto: bool = True,
       goal: str = "Find the price of Atomic Habits", reader=None) -> Person:
    person = person or Person()
    brief = OpenGoalBrief(model, goal, "Books", steps=6, auto=auto, reader=reader)

    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await run_brief(page, person, brief, url, auto=auto, teach_site=url)
            finally:
                await browser.close()
    asyncio.run(run())
    return person


PRICE = Action(action="answer", element_id=0, value="Rs. 3,221",
               reasoning="Atomic Habits costs Rs. 3,221 at Books.")


# --- asked once, then by itself ------------------------------------------------


def test_one_read_back_then_the_search_runs_by_itself_and_ends_with_the_answer(shop):
    model = Model([("type", "Keyword", "Atomic Habits"), PRICE])
    person = go(shop, model)
    asked = person.asked()
    # One thing waited for the person: the read-back. Not the search, and not
    # "Is this what you wanted?".
    assert [step["instruction"] for step in asked] == [
        "On Books, I'll do this: “Find the price of Atomic Habits”. Shall I?"]
    assert [a["label"] for a in asked[0]["actions"]] == [voice.READ_BACK_GO, voice.READ_BACK_STOP]
    # The search is a line of the checklist, in plain words.
    assert person.lines() == ["Searching for Atomic Habits"]
    done = person.payload_of("task.completed")
    assert done["findings"][0]["value"] == "Rs. 3,221"
    assert done["explanation"] == "Atomic Habits costs Rs. 3,221 at Books."
    assert done["scope"] == voice.AI_ONLY_LOOKED


def test_no_to_the_read_back_touches_nothing(shop):
    model = Model([])
    person = go(shop, model, Person(["cancel"]))
    assert person.payload_of("task.failed")["reason"] == voice.YOU_STOPPED
    assert model.pages == []


def test_asked_to_confirm_every_move_every_move_is_asked_and_so_is_the_answer(shop):
    model = Model([("type", "Keyword", "Atomic Habits"), PRICE])
    person = go(shop, model, auto=False)
    said = [step["instruction"] for step in person.asked()]
    assert said[1] == "Search for Atomic Habits."
    assert said[2] == "The page says: Rs. 3,221. Is this what you wanted?"
    assert person.lines() == []


def test_the_read_back_is_the_models_sentence_when_it_is_a_usable_one(shop):
    reader = Model([Action(action="answer", element_id=0, reasoning="",
                           value="I'll search Books for Atomic Habits and tell you the price.")])
    person = go(shop, Model([PRICE.model_copy(update={"value": "Login"})]), reader=reader)
    assert person.asked()[0]["instruction"] == (
        "I'll search Books for Atomic Habits and tell you the price. Shall I?")


@pytest.mark.parametrize("said", [
    "Sure! Searching now.",                       # not said as what it will do
    "I'll go to https://example.com and look.",   # an address
    "I'll " + "search " * 40,                     # too long
])
def test_a_read_back_that_is_not_one_plain_sentence_is_not_used(said):
    reader = Model([Action(action="answer", element_id=0, value=said, reasoning="")])
    assert asyncio.run(restate(reader, "Find a book", "Books")) is None


# --- only what is the person's stops for them -----------------------------------


def test_a_box_for_the_persons_own_details_is_theirs_to_type(shop):
    # The model makes a name up; it is dropped, and the person is asked.
    model = Model([("type", "Your name", "John Doe"), PRICE])
    person = go(shop.replace("index.html", "results.html"), model,
                Person(typed={"fullname": "Amna"}))
    box = person.asked()[1]
    assert box["instruction"] == "Type your name."
    assert box["fields"][0]["value"] == ""
    assert "John Doe" not in str(person.sent)


def test_a_press_that_changes_something_still_gets_its_final_screen(shop):
    model = Model([("click", "Place order", None)])
    person = go(shop.replace("index.html", "results.html"), model, Person(["confirm", "decline"]))
    final = person.asked()[1]
    assert final["final"], "the press that orders was not put on a final screen"
    assert person.payload_of("task.failed")["reason"] == voice.NOTHING_CHANGED


# --- never wandering ---------------------------------------------------------------


def test_three_moves_that_get_nowhere_and_it_stops_and_offers_a_helper(shop):
    # Login opens the dialog (somewhere new); Close, Login, Close go round.
    model = Model([("click", "Login", None), ("click", "Close", None),
                   ("click", "Login", None), ("click", "Close", None)])
    person = go(shop, model, goal="Make me an account")
    stuck = person.payload_of("help.requested")
    assert stuck["reason"] == voice.AI_NO_PROGRESS
    assert stuck["teach_site"] == shop
    assert stuck["suggestion"] == voice.AI_THEN_TEACH
    # Stopped before a fifth choice was asked for, and the model was told,
    # the first time it came back to a page it had seen.
    assert model.script == []
    assert "already seen" in (model.feedback[2] or "")
    assert len(person.lines()) <= 4


def test_a_press_that_changes_nothing_is_fed_back_and_then_stops(shop):
    model = Model([("click", "Offers", None), ("click", "Home", None)])
    person = go(shop, model)
    stuck = person.payload_of("help.requested")
    # Said in SIMBA's words, not the move's and the browser's.
    assert stuck["reason"] == voice.AI_NO_PROGRESS
    assert stuck["teach_site"] == shop
    assert "did not work" in (model.feedback[1] or "")


# --- what the model is shown ---------------------------------------------------------


def element(id, role, label, **flags) -> Element:
    return Element(id=id, role=role, label=label, type="click", tag="a", input_type=None, **flags)


def test_a_dialog_the_goal_needs_is_not_dismissed_first(shop):
    model = Model([("click", "Login", None), ("click", "Register.", None), PRICE])
    go(shop, model, goal="Make me an account")
    with_dialog = model.pages[1]
    assert ON_TOP_BANNER in with_dialog
    assert "Dismiss it first" not in with_dialog
    assert "Dismiss it first" not in model.systems[0]


def test_a_help_chat_button_is_never_offered_and_covers_nothing():
    page = [element(1, "link", "Register"),
            element(2, "button", "Search", occluded=True),
            element(3, "button", "Open help chat", overlay=True)]
    shown = without_widgets(page)
    assert [e.label for e in shown] == ["Register", "Search"]
    assert not any(e.occluded for e in shown)
    assert "help chat" not in render_page(shown)
    # With a real dialog on top as well, what is behind it stays behind it.
    page.append(element(4, "button", "Close", overlay=True))
    assert [e.label for e in usable(without_widgets(page))] == ["Register", "Close"]


def test_only_what_was_listed_can_be_chosen(shop):
    # 'Nowhere' is a link that goes nowhere: counted, not listed, not chosen.
    model = Model([Action(action="click", element_id=2, value=None, reasoning="x"),
                   Action(action="answer", element_id=0, value="Offers", reasoning="x")])
    go(shop, model)
    assert "\n2. " not in model.pages[0] and "1 links that go nowhere" in model.pages[0]
    assert "not in the list" in (model.feedback[1] or "")


def test_a_link_that_opens_a_dialog_is_not_a_dead_link():
    assert is_dead_link("a", {"href": "#"})
    assert is_dead_link("a", {"href": ""})
    assert not is_dead_link("a", {"href": "#", "role": "button", "data-toggle": "modal",
                                  "data-target": "#register"})
    assert not is_dead_link("a", {"href": "#", "data-bs-toggle": "modal"})
    assert not is_dead_link("a", {"href": "#", "aria-haspopup": "dialog"})


# --- in plain words ------------------------------------------------------------------


@pytest.mark.parametrize("args, kwargs, said, doing", [
    (("fill", "combobox", "Keyword | Title | Author | ISBN | Publisher", "Atomic Habits"),
     {"search": True}, "Search for Atomic Habits.", "Searching for Atomic Habits"),
    (("click", "link", "Atomic Habits: An Easy & Proven Way To Build Good Habits"), {},
     "Open Atomic Habits: An Easy & Proven Way To Build Good Habits.",
     "Opening Atomic Habits: An Easy & Proven Way To Build Good Habits"),
    (("click", "button", "Add to Cart"), {}, "Press Add to Cart.", "Pressing Add to Cart"),
    (("click", "button", "Close"), {"overlay": True}, "Close the pop-up.", "Closing a pop-up"),
    (("fill", "textbox", "Enter Email *", None), {}, "Type your email.", "Typing your email"),
    (("fill", "textbox", "Enter Password", None), {"password": True},
     "Type your password.", "Typing your password"),
    (("fill", "spinbutton", "Quantity", "2"), {}, "Type 2 in the quantity box.",
     "Typing 2 in the quantity box"),
    (("select", "combobox", "City", "Lahore"), {}, "Choose Lahore.", "Choosing Lahore"),
    (("click", "option", "LAHORE CANTT"), {}, "Choose LAHORE CANTT.", "Choosing LAHORE CANTT"),
    (("click", "button", ""), {}, "Press a button that has no words on it.", "Pressing a button"),
])
def test_a_move_is_said_in_plain_words(args, kwargs, said, doing):
    assert voice.plain_move(*args, **kwargs) == (said, doing)
    assert "element" not in said.lower() and "click" not in said.lower()


def test_a_long_label_is_cut_at_a_word():
    name = voice.short_name("The Assassins Of Rome (The Roman Mysteries Book 4) by Caroline "
                            "Lawrence, paperback, second edition")
    assert len(name) <= voice.PLAIN_LABEL_CHARS + 1 and name.endswith("…")


@pytest.mark.parametrize("sentence, kept", [
    ("Atomic Habits costs Rs. 3,221 at Books.", True),
    ("Atomic Habits costs Rs. 3,221, down from Rs. 4,999.", False),   # a figure not shown
    ("It is cheap.", False),                                          # without the value
    ("Atomic Habits costs Rs. 3,221. You should buy it now.", False),  # two sentences
])
def test_the_answers_sentence_is_used_only_if_it_holds(sentence, kept):
    result = answer_sentence("Rs. 3,221", sentence, "Find the price of Atomic Habits")
    assert (result is not None) is kept


# --- a page still arriving, and a provider that is slow ---------------------------------


def test_a_page_is_read_once_it_has_stopped_arriving(shop):
    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page()
            await page.goto(shop.replace("index.html", "late.html"))
            waited = await settled(page)
            links = await page.locator("a").count()
            await browser.close()
            return waited, links
    waited, links = asyncio.run(run())
    assert links == 30, "the page was read before its books arrived"
    assert 0.6 <= waited < 6.0


class Slow:
    label = "Gemini"
    wait_out_rate_limits = False

    def __init__(self) -> None:
        self.asked = 0

    async def decide(self, *args, **kwargs):
        import openai

        self.asked += 1
        try:
            raise openai.APITimeoutError(request=None)  # type: ignore[arg-type]
        except openai.APITimeoutError as error:
            raise LLMError("OpenAI-compatible call failed: timed out") from error


class Quick:
    label = "Groq"

    async def decide(self, *args, **kwargs):
        return PRICE


def test_a_provider_that_does_not_answer_is_moved_on_from_and_then_rested():
    slow, chain = Slow(), None
    chain = FallbackProvider([slow, Quick()])

    async def ask():
        return [await chain.decide("s", "p", "g") for _ in range(4)]
    answers = asyncio.run(ask())
    assert answers == [PRICE] * 4 and chain.answered_by == "Groq"
    # Asked twice, then rested: the third and fourth calls went straight on.
    assert slow.asked == llm.REST_AFTER


def test_the_sdk_does_not_wait_or_retry_by_itself():
    provider = llm.OpenAICompatibleProvider(api_key="k" * 12, base_url="https://x.invalid/v1",
                                            transcript=llm.Transcript(Path("NUL")))
    assert provider._client.max_retries == 0
    assert provider._client.timeout == llm.CALL_TIMEOUT_S <= 30
