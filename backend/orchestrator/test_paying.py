"""Paying the bill the person looked up, on our billing replica (2026-10-16).

A pretend payment, with no card details: once the bill is shown, on a
replica only, "Would you like to pay this bill?" — "Yes, pay it" or "No,
just the bill". Yes opens the payment page, then the final screen with the
amount, the bill and the due date read from the page; "Pay it" pays, and the
closing screen quotes the receipt. Real loop, real Chromium, real replica.
"""

from datetime import date

from backend.orchestrator import voice
from backend.orchestrator.details import BillBrief, Understood
from backend.orchestrator.test_billing import billing_replica  # noqa: F401
from backend.orchestrator.test_checklist import Answers, go

REFERENCE = "04141234567890"


def a_bill() -> BillBrief:
    return BillBrief("pay my bill", Understood(reference=REFERENCE))


def shown(done, instruction: str) -> dict:
    return next(p for p in done.of("step.presented") if p["instruction"] == instruction)


def test_the_bill_comes_with_a_quiet_offer_and_no_question(billing_replica: str) -> None:  # noqa: F811
    done = go(billing_replica, a_bill(), [])

    assert done.asked() == [voice.ASK_COOKIES]
    assert done.of("task.started")[0]["stages"][-1] == voice.PAY_STAGE
    end = done.of("task.completed")
    assert len(end) == 1 and end[0]["findings"][0]["values"] == ["Rs 14,382"]
    assert end[0]["scope"] == voice.ONLY_LOOKED_AT_BILL
    assert end[0]["offer"] == {"id": voice.PAY_ID, "label": voice.PAY_THIS_BILL}


def test_a_goal_that_says_pay_goes_straight_to_paying(billing_replica: str) -> None:  # noqa: F811
    brief = BillBrief("pay my bill", Understood(reference=REFERENCE, wants="pay"))
    done = go(billing_replica, brief, [])

    end = done.of("task.completed")
    assert len(end) == 1 and end[0]["confirmation"].startswith("The site says")
    assert shown(done, voice.FINAL_PAY)["final"][0] == {"label": "Amount", "value": "Rs 14,382"}


def test_yes_pays_after_its_final_screen_with_no_card(billing_replica: str) -> None:  # noqa: F811
    done = go(billing_replica, a_bill(), [(voice.PAY_ID, {})])

    assert voice.DOING_PAYMENT_PAGE in done.rows()
    final = shown(done, voice.FINAL_PAY)
    assert final["final"] == [
        {"label": "Amount", "value": "Rs 14,382"},
        {"label": "Bill", "value": "AUG 2026"},
        {"label": "Due", "value": "15 September 2026"},
        {"label": "Reference number", "value": REFERENCE},
    ]
    assert [(a["id"], a["label"]) for a in final["actions"]] == [
        ("confirm", voice.PAY_IT), (voice.DECLINE_ID, voice.DONT_PAY)]
    # Nothing on any step asked for, or typed, a card.
    for step in done.of("step.presented"):
        assert not any("card" in f["label"].lower() for f in step["fields"]), step

    end = done.of("task.completed")[-1]
    found = {f["label"]: f["values"][0] for f in end["findings"]}
    assert found["Receipt number"].startswith("RCPT-")
    assert found["Amount paid"] == "Rs 14,382"
    assert found["Paid on"] == voice.page_date(date.today().strftime("%d-%m-%Y"))
    # Said plainly, not "That's done." (2026-10-17).
    assert end["heading"] == "Paid on the practice site."
    assert end["caveat"] == (f"Receipt number {found['Receipt number']}. This was a practice "
                             f"copy, so no money was taken.")
    assert end["confirmation"] == "The site says “Payment Received”."
    assert end["scope"] == voice.PAID_SCOPE
    assert end["proof"] and end["proof"]["rings"]


def test_dont_pay_pays_nothing(billing_replica: str) -> None:  # noqa: F811
    class SaysDont(Answers):
        async def receive(self, message_type, step_index=None, on_other=None):
            step = self.of("step.presented")[-1]
            if step.get("final"):
                self.shown += 1
                return {"type": "step.response", "payload": {
                    "step_index": step_index, "action_id": voice.DECLINE_ID,
                    "input_values": {}}}
            return await super().receive(message_type, step_index, on_other)

    import backend.orchestrator.test_checklist as checklist

    original, checklist.Answers = checklist.Answers, SaysDont
    try:
        done = go(billing_replica, a_bill(), [(voice.PAY_ID, {})])
    finally:
        checklist.Answers = original

    assert done.of("task.failed")[0]["reason"] == voice.NOTHING_CHANGED
    # Only the answer itself completed: nothing was booked or paid.
    assert len(done.of("task.completed")) == 1


def test_a_payment_the_site_does_not_confirm_is_not_done(
    billing_replica: str, monkeypatch,  # noqa: F811
) -> None:
    from dataclasses import replace

    import backend.orchestrator.finish_plan as finish_plan

    real = finish_plan.payment_task

    def unconfirmed(reference: str):
        task = real(reference)
        return replace(task, confirms=replace(task.confirms, heading="Payment Settled"))

    monkeypatch.setattr(finish_plan, "payment_task", unconfirmed)
    done = go(billing_replica, a_bill(), [(voice.PAY_ID, {})])

    # Only the answer itself completed: nothing was booked or paid.
    assert len(done.of("task.completed")) == 1
    help = done.of("help.requested")[0]
    assert help["unconfirmed"] is True
    assert help["reason"] == voice.not_confirmed("Confirm Payment", "site")
