"""The AI planner carries a task out, not only reads (2026-11-14).

Raham, 14 November: SIMBA has to *perform* a task on a live site — an order, a
booking, a payment — as the advisor asked on 12 November ("tasks carried out
on live sites, not only read"). What has to hold, through the real loop, a real
browser and a shop page served from this machine, with only the model scripted:

  * the model may press a button that orders, and the loop puts the final
    screen in front of it — nothing is pressed without the person's "Do it";
  * "Don't do it" ends the task with nothing changed;
  * after the page confirms the order, the task finishes with the
    confirmation the page shows, word for word, as its answer;
  * whatever the person typed (their name, here) is never in anything a model
    is sent, even after the site shows it back — free providers may keep
    what they are sent (DECISIONS.md, 2026-11-13);
  * a payment page is still handed to the person, and the model never sees it.
"""

import asyncio
import functools
import http.server
import socketserver
import threading
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from backend.orchestrator import voice
from backend.orchestrator.llm import Action
from backend.orchestrator.llm_loop import OPEN_GOAL_RULES, OpenGoalPlanner
from backend.orchestrator.loop import Task, _Run, carry_out
from backend.orchestrator.plan import About
from backend.orchestrator.test_verification import FakeConnection

NAME = "Zainab Testwala"

SHOP = """<!doctype html><html><head><title>Book shop</title></head><body>
<h1>Checkout</h1>
<div id="form">
  <label for="fullname">Full name</label> <input id="fullname" name="fullname">
  <button id="go" onclick="
    document.getElementById('review').textContent =
      'Deliver to: ' + document.getElementById('fullname').value;
    document.getElementById('form').hidden = true;
    document.getElementById('place').hidden = false;">Continue</button>
</div>
<p id="review"></p>
<div id="place" hidden>
  <p>Total: Rs. 350, cash on delivery</p>
  <button onclick="
    document.body.innerHTML = '<h2>Order placed</h2><p>Order number: 4711</p>';">Place order</button>
</div>
</body></html>"""

PAY = """<!doctype html><html><head><title>Pay</title></head><body>
<h1>Mobile top-up</h1>
<!-- "Pay now" opens the card page, which a moment later shows the receipt:
     that moment is the person paying, during the handover. -->
<p>Amount: Rs. 200</p>
<button onclick="document.body.innerHTML =
  '<h2>Payment</h2><label for=card>Card number</label> <input id=card name=card>';
  setTimeout(() => { document.body.innerHTML =
    '<h2>Payment successful</h2><p>Receipt number: R-55</p>'; }, 300);">Pay now</button>
</body></html>"""


@pytest.fixture(scope="module")
def site(tmp_path_factory) -> str:
    folder: Path = tmp_path_factory.mktemp("shop")
    (folder / "index.html").write_text(SHOP, encoding="utf-8")
    (folder / "pay.html").write_text(PAY, encoding="utf-8")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(folder))
    server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/index.html"
    server.shutdown()


def element_id(page: str, words: str) -> int:
    return int(next(line.split(".")[0] for line in page.splitlines() if words in line))


class Shopper:
    """The model: fills the name (for the person to type), continues, orders,
    then answers with the confirmation. Keeps every prompt it was sent."""

    label = "Gemini"

    def __init__(self) -> None:
        self.sent: list[str] = []
        self.typed = False

    async def decide(self, system_prompt, page, goal, feedback=None, history=None):
        self.sent.append("\n".join([system_prompt, page, goal, feedback or "",
                                    *(history or [])]))
        if "Order number: 4711" in page:
            return Action(action="answer", element_id=0, value="Order number: 4711",
                          reasoning="The page confirms the order.")
        if "Place order" in page:
            return Action(action="click", element_id=element_id(page, "Place order"),
                          reasoning="Place the order, as asked.")
        if not self.typed:
            self.typed = True
            return Action(action="type", element_id=element_id(page, "Full name"),
                          value=None, reasoning="The person types their own name.")
        return Action(action="click", element_id=element_id(page, "Continue"),
                      reasoning="Go on to the order.")


class Person(FakeConnection):
    """Types the name when asked, and answers the final screen as told."""

    def __init__(self, final: str = voice.CONFIRM_ID) -> None:
        super().__init__()
        self.final = final

    async def receive(self, message_type, step_index=None, on_other=None):
        response = await super().receive(message_type, step_index, on_other)
        step = next((p for kind, p in reversed(self.sent) if kind == "step.presented"), {})
        payload = response["payload"]
        payload["input_values"] = {"fullname": NAME} if step.get("fields") else {}
        if step.get("final"):
            payload["action_id"] = self.final
        return response


def run(url: str, provider, connection: FakeConnection, goal: str) -> FakeConnection:
    task = Task(goal=goal, estimated_steps=6, success=None, about=About())

    async def go():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                run_ = _Run(page, connection, None, None)
                await run_.open(task.goal, task.estimated_steps, url)
                await carry_out(run_, OpenGoalPlanner(provider, task), task)
            finally:
                await browser.close()
    asyncio.run(go())
    return connection


ORDER = "Order the book for me, cash on delivery"


def test_the_planner_is_told_it_may_carry_a_task_out():
    assert "never press a button that pays" not in OPEN_GOAL_RULES
    assert "presses it only if they say so" in OPEN_GOAL_RULES
    assert "Never type card numbers" in OPEN_GOAL_RULES


def test_an_order_is_placed_behind_the_final_screen_and_finishes_with_its_number(site):
    provider, person = Shopper(), Person()
    run(site, provider, person, ORDER)
    steps = person.of("step.presented")
    finals = [s for s in steps if s.get("final")]
    assert len(finals) == 1, [s["instruction"] for s in steps]
    assert "Place order" in finals[0]["instruction"]
    assert person.payload_of("task.completed")["findings"][0]["value"] == "Order number: 4711"


def test_dont_do_it_changes_nothing(site):
    provider, person = Shopper(), Person(final=voice.DECLINE_ID)
    run(site, provider, person, ORDER)
    failed = person.payload_of("task.failed")
    assert failed["reason"] == voice.NOTHING_CHANGED
    assert "task.completed" not in person.types()
    assert not any("Order number" in prompt for prompt in provider.sent)


def test_what_the_person_typed_never_reaches_a_model(site):
    provider, person = Shopper(), Person()
    run(site, provider, person, ORDER)
    # The site showed the name back ("Deliver to: …") before the order was
    # placed, so the model was sent that page at least once after typing.
    assert len(provider.sent) >= 3
    for prompt in provider.sent:
        assert NAME not in prompt
        assert "Zainab" not in prompt
    assert any("Deliver to:" in prompt for prompt in provider.sent)


def test_a_payment_is_handed_to_the_person(site):
    class Payer:
        label = "Gemini"

        def __init__(self) -> None:
            self.sent: list[str] = []

        async def decide(self, system_prompt, page, goal, feedback=None, history=None):
            self.sent.append(page)
            return Action(action="click", element_id=element_id(page, "Pay now"),
                          reasoning="Pay, as asked.")

    class Handing(Person):
        async def receive(self, message_type, step_index=None, on_other=None):
            if isinstance(message_type, tuple):   # the handover: the person pays,
                await asyncio.sleep(1.0)            # then presses "I've finished"
                return {"type": "handover.done", "payload": {"action": "done"}}
            return await super().receive(message_type, step_index, on_other)

    provider, person = Payer(), Handing()
    run(site.replace("index.html", "pay.html"), provider, person, "Top up my phone with Rs. 200")
    kinds = person.types()
    assert "handover" in kinds, kinds
    finals = [s for s in person.of("step.presented") if s.get("final")]
    assert finals and "Pay now" in finals[0]["instruction"]
    # The model never saw the card page, and SIMBA read the receipt after.
    assert not any("Card number" in page for page in provider.sent)
    done = person.payload_of("task.completed")
    assert "Payment successful" in (done.get("confirmation") or "") or \
        "Receipt" in (done.get("confirmation") or ""), done
