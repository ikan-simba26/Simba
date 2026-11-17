"""Payment handover and live changes behind the final screen (2026-11-13, the
advisor's direction, items F and G). Written before the code, as CLAUDE.md asks
for anything in the verification path.

The rule as it now stands:

- On a live site, a move that orders, books, registers or submits happens only
  after the final screen and the person's "do it" — and then SIMBA presses it.
- Payment itself is always the person's. A press that pays, a page that asks
  for card or bank details, a one-time code, a CAPTCHA or a bot check: SIMBA
  stops, hands the real page to the person ("handover"), and never types,
  reads, logs or keeps what they enter. When they say they have finished,
  SIMBA reads the page and says what it shows — or that it cannot tell.
- "Stop" during a handover ends the task, and SIMBA says it changed nothing.

Pages here are `data:` URLs, which are not this machine and so count as live
sites, in real Chromium through the real loop.
"""

from types import SimpleNamespace
from urllib.parse import quote

from playwright.async_api import async_playwright

from backend.orchestrator import voice
from backend.orchestrator.loop import Task, run_task
from backend.orchestrator.plan import (
    About, Expectation, HardcodedPlanner, Operation, PlanStep, Target,
)
from backend.orchestrator.test_asking import ScriptedConnection
from backend.orchestrator.test_checklist import run


class Handing(ScriptedConnection):
    """Answers steps from a script; answers a handover by doing, on the real
    page, what the person would (`person`), then `handover.done` with
    `action` — or `task.cancel`."""

    def __init__(self, answers=None, person=None, action: str = "done") -> None:
        super().__init__(answers)
        self.page = None
        self.person = person
        self.action = action
        self.handovers: list[dict] = []

    async def receive(self, message_type, step_index=None, on_other=None):
        wanted = (message_type,) if isinstance(message_type, str) else message_type
        if "handover.done" in wanted:
            self.handovers.append(self.of("handover")[-1])
            if self.person is not None:
                await self.person(self.page)
            if self.action == "cancel":
                return {"type": "task.cancel", "payload": {}}
            return {"type": "handover.done", "payload": {"action": self.action}}
        return await super().receive(message_type, step_index, on_other)


def drive(start_url: str, steps: list[PlanStep], answers=None, person=None,
          action: str = "done", planner=None) -> tuple[Handing, SimpleNamespace]:
    async def inner():
        connection = Handing(answers, person, action)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            connection.page = page
            try:
                await run_task(page, connection, planner or HardcodedPlanner(steps),
                               Task(goal="g", estimated_steps=max(1, len(steps)),
                                    about=About()),
                               start_url)
                after = SimpleNamespace(
                    title=await page.title(),
                    clicked=await page.evaluate("window.__clicked || 0"),
                    typed=await page.evaluate(
                        "[...document.querySelectorAll('input')].map(i => i.value)"))
            finally:
                await browser.close()
        return connection, after

    return run(inner())


def page(body: str, title: str = "Checkout") -> str:
    return "data:text/html," + quote(f"<title>{title}</title>{body}")


def press(label: str, **extra) -> PlanStep:
    return PlanStep(instruction=f"Press {label}.", detail="", actions=voice.actions("Go"),
                    operations=[Operation("click", Target("button", label))],
                    expect=Expectation(), **extra)


ORDER = page("<h1>Your order</h1><p>Total: <b>Rs 450</b></p>"
             "<p>Pay on delivery</p>"
             "<button onclick=\"window.__clicked=1;document.title='Order placed';"
             "document.body.innerHTML='<h1>Thank you, your order is placed</h1>'\">"
             "Place order</button>")


# --- a change on a live site: the final screen, then SIMBA presses ---------------------


def test_an_order_on_a_live_site_waits_for_the_final_screen_then_is_placed():
    done, after = drive(ORDER, [press("Place order", changes=True)], [("confirm", {})])
    final = done.of("step.presented")[-1]
    assert final["final"] is not None
    assert [a["id"] for a in final["actions"]] == ["confirm", voice.DECLINE_ID]
    assert after.clicked == 1
    assert "handover" not in done.types()
    assert "task.completed" in done.types()


def test_an_order_the_person_does_not_want_is_not_placed():
    done, after = drive(ORDER, [press("Place order", changes=True)], [(voice.DECLINE_ID, {})])
    assert done.of("task.failed")[0]["reason"] == voice.NOTHING_CHANGED
    assert after.clicked == 0


class Unmarked(HardcodedPlanner):
    """A planner that does not mark its own changes, as the model does not."""

    marks_changes = False


def test_the_final_screen_on_a_live_site_shows_what_the_page_says_it_costs():
    """A move the model chose has no plan to say which details matter: the
    final screen shows the page's own amounts, as it states them."""
    steps = [press("Place order")]
    done, _ = drive(ORDER, steps, [(voice.DECLINE_ID, {})], planner=Unmarked(steps))
    details = {d["label"]: d["value"] for d in done.of("step.presented")[-1]["final"]}
    assert details[voice.WHAT_I_PRESS] == "Place order"
    assert details.get("Total") == "Rs 450"


# --- paying is the person's ---------------------------------------------------------------


PAY = page("<h1>Pay for your ticket</h1><p>Fare: <b>Rs 1,200</b></p>"
           "<button onclick=\"window.__clicked=1\">Pay now</button>")


async def pays(page):
    """The person, on the real page: presses Pay themselves."""
    await page.evaluate("document.body.innerHTML = '<h1>Payment successful</h1>"
                        "<p>Receipt no. <b>PX-2201</b></p>'")


def test_a_press_that_pays_is_pressed_by_simba_after_its_final_screen():
    # Changed 2026-11-17: the person types the card in the help-me step; a press
    # that pays is SIMBA's after "do it", like any change. The page is no longer
    # handed over wholesale for it.
    done, after = drive(PAY, [press("Pay now", changes=True)], [("confirm", {})], person=pays)
    assert done.of("step.presented")[-1]["final"] is not None
    assert done.of("handover") == []
    assert after.clicked == 1


CARD = page("<h1>Card details</h1><label>Card number <input name=n></label>"
            "<label>CVV <input name=c></label><button>Pay Rs 1,200</button>")


def fill(label: str) -> PlanStep:
    return PlanStep(instruction="Fill in.", detail="", actions=voice.actions("Go"),
                    operations=[Operation("fill", Target("textbox", label),
                                          value="4111111111111111")],
                    expect=Expectation())


async def types_card(page):
    await page.fill("input[name=n]", "4242424242424242")
    await page.fill("input[name=c]", "123")


def test_a_page_asking_for_card_details_is_handed_over_and_never_typed_into():
    # Since 2026-11-17 the person types the card in the help-me step; SIMBA then
    # shows the pay screen, and "don't pay" changes nothing.
    done, after = drive(CARD, [fill("Card number")], [("decline", {})], person=types_card)
    assert done.of("handover")[0]["reason"] == "payment"
    assert done.of("handover")[0]["kind"] == "card"
    # Not a single step about the card was put to the person or done by SIMBA.
    assert all("Card" not in s["instruction"] for s in done.of("step.presented")
               if not s.get("final"))
    assert done.of("step.presented")[-1]["final"] is not None
    assert done.of("task.failed")[0]["reason"] == voice.NOTHING_CHANGED


def test_what_the_person_types_is_never_sent_anywhere():
    done, _ = drive(CARD, [fill("Card number")], [("decline", {})], person=types_card)
    sent = repr(done.sent)
    assert "4242424242424242" not in sent and "123\"" not in sent


def test_stop_during_a_handover_ends_the_task_and_changes_nothing():
    done, after = drive(CARD, [fill("Card number")], action="cancel")
    assert done.of("task.failed")[0]["reason"] == voice.HANDED_BACK_STOPPED
    assert "task.completed" not in done.types()
    assert after.typed == ["", ""]


# --- a check for a person ----------------------------------------------------------------


CHECK = page("<h1>Security check</h1><label>Enter the captcha <input name=cap></label>"
             "<button>Go on</button>", title="Just a moment...")


async def solves(page):
    await page.evaluate("document.title = 'Results';"
                        "document.body.innerHTML = '<h1>Your results</h1><p>Done</p>'")


def test_a_captcha_is_handed_to_the_person_and_the_run_goes_on_after():
    done, _ = drive(CHECK, [], person=solves)
    assert done.of("handover")[0]["reason"] == "check"
    assert "help.requested" not in done.types()


def test_a_check_that_is_still_there_after_twice_stops():
    done, _ = drive(CHECK, [], person=None)
    assert len(done.of("handover")) == 2
    assert done.of("help.requested")[0]["reason"] == voice.BLOCKED
