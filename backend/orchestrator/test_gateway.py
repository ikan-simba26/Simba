"""The test card gateway on the billing copy, and a whole payment through it
(2026-11-13, the advisor's direction, H and F): SIMBA opens the card page after
the final screen, hands the page to the person, never types or keeps what they
enter, and reads the receipt when they say they have finished.

The person is played on the real page by the test; the card and code are the
gateway's published test ones. No real money is involved anywhere.
"""

import sys
from pathlib import Path

import pytest

from backend.orchestrator import voice
from backend.orchestrator.finish_plan import PaymentPlanner
from backend.orchestrator.test_billing import REPLICA_URL
from backend.orchestrator.test_billing import billing_replica  # noqa: F401
from backend.orchestrator.test_handover import drive

REPLICA = Path(__file__).resolve().parents[2] / "replicas" / "billing"
REFERENCE = "04141234567890"
CARD = "4242424242424242"


@pytest.fixture
def gateway():
    sys.path.insert(0, str(REPLICA))
    try:
        import app as billing  # noqa: PLC0415 - the replica's own module
    finally:
        sys.path.remove(str(REPLICA))
    billing.app.config["TESTING"] = True
    return billing.app.test_client()


def test_the_test_card_and_code_go_through(gateway):
    card = gateway.post("/gateway/card", data={"reference": REFERENCE, "cc-number": CARD})
    assert b"One-time code" in card.data
    code = gateway.post("/gateway/otp", data={"reference": REFERENCE, "otp": "123456"})
    assert code.status_code == 302
    receipt = gateway.get(code.headers["Location"])
    assert b"Payment successful" in receipt.data
    assert b"No money was taken" in receipt.data


def test_any_other_card_is_declined_and_never_shown_back(gateway):
    declined = gateway.post("/gateway/card", data={"reference": REFERENCE,
                                                   "cc-number": "5555555555554444"})
    assert b"Card declined" in declined.data
    assert b"5555555555554444" not in declined.data


def test_a_wrong_code_is_asked_again(gateway):
    wrong = gateway.post("/gateway/otp", data={"reference": REFERENCE, "otp": "000000"})
    assert wrong.status_code == 200 and b"not right" in wrong.data


def test_every_gateway_page_says_it_is_a_test(gateway):
    page = gateway.get(f"/gateway/checkout?reference={REFERENCE}")
    assert b"TEST GATEWAY" in page.data and b"No real money" in page.data


async def pays_by_card(page):
    """The person, on the real gateway page: their card, the bank's code."""
    await page.fill("#cc-name", "M R Wasim")
    await page.fill("#cc-number", CARD)
    await page.fill("#cc-exp", "12/30")
    await page.fill("#cc-csc", "123")
    await page.click("text=Pay Rs")
    await page.wait_for_selector("#otp")
    await page.fill("#otp", "123456")
    await page.click("text=Confirm")
    await page.wait_for_selector("text=Payment Received")


def test_a_bill_paid_by_card_through_the_gateway_end_to_end(billing_replica, monkeypatch):  # noqa: F811
    monkeypatch.setenv("SIMBA_CARD_GATEWAY", "1")
    planner = PaymentPlanner(stage=1)
    start = f"{REPLICA_URL}/bill/pay?reference={REFERENCE}"
    # The payment page is already open: the planner's first move, the link to
    # it, is taken as done.
    planner._done.add("open")
    done, after = drive(start, [], [("confirm", {})], person=pays_by_card, planner=planner)

    final = done.of("step.presented")[-1]
    assert final["instruction"] == voice.FINAL_PAY_CARD
    assert {d["label"]: d["value"] for d in final["final"]}["Reference number"] == REFERENCE
    assert done.of("handover")[0]["reason"] == "payment"
    end = done.of("task.completed")[0]
    assert end["heading"] == voice.PAID
    assert "Payment Received" in end["confirmation"]
    # Nothing the person typed went anywhere SIMBA sends.
    # (The code is looked for as a whole value: the reference number itself
    # has the digits 123456 in it.)
    sent = repr(done.sent)
    assert CARD not in sent
    assert "'123456'" not in sent and '"123456"' not in sent
    assert "12/30" not in sent


def test_stop_on_the_card_page_changes_nothing(billing_replica, monkeypatch):  # noqa: F811
    monkeypatch.setenv("SIMBA_CARD_GATEWAY", "1")
    planner = PaymentPlanner(stage=1)
    planner._done.add("open")
    done, after = drive(f"{REPLICA_URL}/bill/pay?reference={REFERENCE}", [], [("confirm", {})],
                        action="cancel", planner=planner)
    assert done.of("task.failed")[0]["reason"] == voice.HANDED_BACK_STOPPED
    assert after.title.startswith("Card payment")
