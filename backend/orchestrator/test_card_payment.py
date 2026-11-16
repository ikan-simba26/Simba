"""SIMBA pays by card, through the real browser (2026-11-16).

The owner's direction: when a page asks for a card, SIMBA types it in and
presses Pay itself, on any website, once the person has said "pay now" on a
final screen. Nothing here is a simulation: the pages are real Chromium pages,
and the proof that the typing was real is the *server's* — the test gateway on
the billing copy only shows its one-time-code page to a request that carried
the published test card, and declines any other.

No real card, ever. The cards below are the gateway's published test cards
(Visa 4242…, Mastercard 5555…4444), and the card vault is a file in the test's
own folder.
"""

import logging
import pytest

from backend.orchestrator import payment, voice
from backend.orchestrator.test_billing import REPLICA_URL
from backend.orchestrator.test_billing import billing_replica  # noqa: F401
from backend.orchestrator.test_handover import drive, page

REFERENCE = "04141234567890"
CHECKOUT = f"{REPLICA_URL}/gateway/checkout?reference={REFERENCE}"
VISA = "4242 4242 4242 4242"
DECLINED_CARD = "5555 5555 5555 4444"
NAME = "Zubair Q Testcard"


def typed(number: str = VISA, expiry: str = "12/30", cvv: str = "737") -> dict:
    return {"name": NAME, "number": number, "expiry": expiry, "cvv": cvv}


@pytest.fixture(autouse=True)
def card_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("SIMBA_PAY_MODE", "card")
    monkeypatch.setenv("SIMBA_CARD_VAULT", str(tmp_path / "card.json"))


async def enters_the_code(page):
    """The person's part: the bank's one-time code, on the real page."""
    await page.wait_for_selector("#otp")
    await page.fill("#otp", "123456")
    await page.click("text=Confirm")
    await page.wait_for_selector("text=Payment Received")


# --- the card itself ---------------------------------------------------------------------------


def test_a_card_is_checked_before_it_is_ever_typed():
    card = payment.parse_card(NAME, VISA, "12/30", "737")
    assert (card.number, card.month, card.year, card.last4) == ("4242424242424242", "12", "2030", "4242")
    assert card.spoken == "Visa ending 4242"
    assert payment.parse_card(NAME, VISA, "1230", "737").year == "2030"
    assert payment.parse_card(NAME, VISA, "12/2030", "7371").cvv == "7371"
    for wrong, reason in [
        (dict(name=""), "name"),
        (dict(number="4242 4242 4242 4241"), "number"),     # fails the Luhn check
        (dict(number="not a card"), "number"),
        (dict(expiry="13/30"), "expiry"),
        (dict(expiry="01/20"), "expiry"),                     # has passed
        (dict(cvv="12"), "cvv"),
    ]:
        args = dict(name=NAME, number=VISA, expiry="12/30", cvv="737") | wrong
        with pytest.raises(payment.CardError) as error:
            payment.parse_card(**args)
        assert error.value.reason == reason


def test_a_card_never_prints_itself():
    card = payment.parse_card(NAME, VISA, "12/30", "737")
    for shown in (repr(card), str(card), f"{card}", f"{[card]}"):
        assert "4242" not in shown and "737" not in shown and NAME not in shown


def test_the_vault_keeps_one_card_encrypted_and_forgets_it(tmp_path):
    vault = payment.CardVault(tmp_path / "v.json")
    if not vault.available:
        pytest.skip("needs Windows' own key (DPAPI)")
    card = payment.parse_card(NAME, VISA, "12/30", "737")
    assert vault.get() is None
    vault.put(card)
    assert vault.get() == card
    raw = (tmp_path / "v.json").read_text(encoding="utf-8")
    assert "4242" not in raw and NAME not in raw and "737" not in raw
    assert vault.forget() and vault.get() is None


@pytest.mark.parametrize("box, role", [
    ({"autocomplete": "cc-number", "type": "text"}, "number"),
    ({"autocomplete": "cc-csc", "type": "text"}, "cvv"),
    ({"autocomplete": "cc-exp", "type": "text"}, "expiry"),
    ({"autocomplete": "cc-exp-month", "type": "select-one"}, "exp_month"),
    ({"autocomplete": "cc-exp-year", "type": "select-one"}, "exp_year"),
    ({"label": "Card number", "type": "tel"}, "number"),
    ({"name": "card_no", "placeholder": "Card number", "type": ""}, "number"),
    ({"placeholder": "CVC", "type": "text"}, "cvv"),
    ({"label": "Security code", "type": "text"}, "cvv"),
    ({"label": "Name on card", "type": "text"}, "name"),
    ({"aria": "Cardholder name", "type": "text"}, "name"),
    ({"placeholder": "MM / YY", "type": "text"}, "expiry"),
    ({"label": "Expiration date", "type": "text"}, "expiry"),
    ({"label": "Expiry month", "type": "select-one"}, "exp_month"),
    ({"label": "Year", "type": "select-one"}, "exp_year"),
])
def test_a_box_is_known_by_what_the_page_says_about_it(box, role):
    assert payment.classify(box) == role


@pytest.mark.parametrize("box", [
    {"label": "One-time code", "type": "text"},          # the bank's code is the person's
    {"label": "Email", "type": "email"},
    {"label": "Search", "type": "text"},
    {"label": "Card number", "type": "hidden"},
    {"label": "Remember my card", "type": "checkbox"},
])
def test_a_box_that_is_not_part_of_a_card_is_left_alone(box):
    assert payment.classify(box) is None


# --- through the real gateway page, in a real browser -----------------------------------------


def test_asked_for_a_card_it_types_it_and_pays_through_the_gateway(billing_replica, caplog):  # noqa: F811
    caplog.set_level(logging.DEBUG)
    done, after = drive(CHECKOUT, [], [(voice.USE_CARD_ID, typed()), ("confirm", {})],
                        person=enters_the_code)

    shown = done.of("step.presented")
    # 1. The card was asked for, in protected boxes.
    ask = shown[0]
    assert ask["instruction"] == voice.CARD_ASK
    assert {f["label"]: f["type"] for f in ask["fields"]} == {
        voice.CARD_NAME_LABEL: "text", voice.CARD_NUMBER_LABEL: "password",
        voice.CARD_EXPIRY_LABEL: "text", voice.CARD_CVV_LABEL: "password"}
    # 2. The final screen: the page's amount, the website, the card by its last four.
    final = next(s for s in shown if s["final"])
    assert final["instruction"] == voice.pay_card_final("127.0.0.1:5101", "Visa ending 4242")
    details = {d["label"]: d["value"] for d in final["final"]}
    assert details[voice.FINAL_CARD_LABEL] == "Visa ending 4242"
    assert details[voice.FINAL_WEBSITE_LABEL] == "127.0.0.1:5101"
    assert any("Rs" in v for v in details.values())
    assert [a["label"] for a in final["actions"]] == [voice.PAY_NOW, voice.DONT_PAY_NOW]
    # 3. The overlay saw each box being filled, in the order a card is read, then Pay.
    lines = [s["instruction"] for s in shown if not s["requires_confirmation"]]
    assert lines == [voice.TYPING_PART["number"], voice.TYPING_PART["name"],
                     voice.TYPING_PART["expiry"], voice.TYPING_PART["cvv"], voice.PRESSING_PAY]
    # 4. The server accepted the card — so it was really typed — and the code was the person's.
    assert [h["reason"] for h in done.of("handover")] == ["check"]
    end = done.of("task.completed")[0]
    assert end["heading"] == voice.PAID and end["caveat"] == voice.PAID_CAVEAT_CARD
    assert "Payment Received" in end["confirmation"]
    # 5. The card is in no message and no log line.
    everything = repr(done.sent) + caplog.text
    for secret in ("4242424242424242", "4242 4242", NAME, "12/30", "737"):
        assert secret not in everything, secret


def test_a_card_the_gateway_declines_is_reported_not_called_paid(billing_replica):  # noqa: F811
    done, _ = drive(CHECKOUT, [], [(voice.USE_CARD_ID, typed(DECLINED_CARD)), ("confirm", {})])
    help_ = done.of("help.requested")[0]
    assert "Card declined" in help_["reason"] and voice.NOT_RETRIED in help_["reason"]
    assert "task.completed" not in done.types()


def test_pay_nothing_if_the_person_says_dont(billing_replica):  # noqa: F811
    done, after = drive(CHECKOUT, [], [(voice.USE_CARD_ID, typed()), (voice.DECLINE_ID, {})])
    assert done.of("task.failed")[0]["reason"] == voice.NOTHING_CHANGED
    assert not any(not s["requires_confirmation"] for s in done.of("step.presented"))
    # Nothing was typed into the page.
    assert "4242" not in str(after.typed) and NAME not in str(after.typed)
    assert after.title.startswith("Card payment")


def test_a_wrong_card_is_asked_again_with_the_box_named(billing_replica):  # noqa: F811
    done, _ = drive(CHECKOUT, [], [(voice.USE_CARD_ID, typed(number="4242 4242 4242 4241")),
                                   (voice.DECLINE_ID, {})])
    asks = [s for s in done.of("step.presented") if s["instruction"] == voice.CARD_ASK]
    assert len(asks) == 2
    assert asks[1]["note"] == voice.CARD_NOTES["number"]


def test_the_person_can_type_it_themselves_instead(billing_replica):  # noqa: F811
    async def by_hand(page):
        await page.fill("#cc-name", "A Person")
        await page.fill("#cc-number", "4242424242424242")
        await page.fill("#cc-exp", "12/30")
        await page.fill("#cc-csc", "123")
        await page.click("text=Pay Rs")
        await enters_the_code(page)

    done, _ = drive(CHECKOUT, [], [(voice.MYSELF_ID, {})], person=by_hand)
    assert done.of("handover")[0]["reason"] == "payment"
    assert done.of("task.completed")[0]["caveat"] == voice.PAID_CAVEAT


def test_a_kept_card_is_used_without_asking_again(billing_replica):  # noqa: F811
    vault = payment.CardVault()
    if not vault.available:
        pytest.skip("needs Windows' own key (DPAPI)")
    # First run: typed once and kept.
    drive(CHECKOUT, [], [(voice.KEEP_CARD_ID, typed()), ("confirm", {})], person=enters_the_code)
    kept = vault.get()
    assert kept is not None and kept.last4 == "4242"
    # Second run: no card question at all, straight to the final screen.
    done, _ = drive(CHECKOUT, [], [("confirm", {})], person=enters_the_code)
    shown = done.of("step.presented")
    assert all(s["instruction"] != voice.CARD_ASK for s in shown)
    assert shown[0]["final"] and done.of("task.completed")


def test_in_handover_mode_nothing_is_typed(billing_replica, monkeypatch):  # noqa: F811
    monkeypatch.setenv("SIMBA_PAY_MODE", "handover")

    async def by_hand(page):
        assert await page.input_value("#cc-number") == ""
        await page.fill("#cc-name", "A Person")
        await page.fill("#cc-number", "4242424242424242")
        await page.fill("#cc-exp", "12/30")
        await page.fill("#cc-csc", "123")
        await page.click("text=Pay Rs")
        await enters_the_code(page)

    done, _ = drive(CHECKOUT, [], [], person=by_hand)
    assert not any(s["instruction"] == voice.CARD_ASK for s in done.of("step.presented"))
    assert done.of("handover")[0]["reason"] == "payment"


# --- any website: forms the gateway does not look like ---------------------------------------


OTHER_SHOP = page(
    "<h1>Checkout</h1><p>Total: <b>Rs 1,200</b></p>"
    "<form onsubmit=\"event.preventDefault();"
    "document.title=[...document.querySelectorAll('input,select')].map(e=>e.value).join('|');"
    "document.body.innerHTML='<h1>Thank you for your payment</h1>'\">"
    "<label>Card holder <input name=h></label>"
    "<label>Card number <input name=n inputmode=numeric></label>"
    "<label>Month <select name=m><option value=''>--</option>"
    + "".join(f"<option value='{m:02d}'>{m:02d}</option>" for m in range(1, 13)) +
    "</select></label>"
    "<label>Year <select name=y><option value=''>--</option>"
    + "".join(f"<option>{y}</option>" for y in range(2026, 2036)) +
    "</select></label>"
    "<label>Security code <input name=c></label>"
    "<button type=button onclick='history.back()'>Back</button>"
    "<button>Pay Rs 1,200</button></form>")


def test_a_form_built_differently_is_filled_by_what_it_says(monkeypatch):
    done, after = drive(OTHER_SHOP, [], [(voice.USE_CARD_ID, typed()), ("confirm", {})])
    # What the page's own submit handler received: every box, month and year chosen.
    assert after.title == f"{NAME}|4242424242424242|12|2030|737" or \
        after.title == f"4242424242424242|{NAME}|12|2030|737"
    assert "Thank you for your payment" in done.of("task.completed")[0]["confirmation"]
    lines = [s["instruction"] for s in done.of("step.presented") if not s["requires_confirmation"]]
    assert voice.TYPING_PART["exp_month"] in lines and voice.TYPING_PART["exp_year"] in lines


IN_A_FRAME = page(
    "<h1>Checkout</h1><p>Total: <b>Rs 700</b></p>"
    "<iframe width=500 height=300 srcdoc=\""
    "&lt;form onsubmit=&quot;event.preventDefault();parent.document.title="
    "[...document.querySelectorAll('input')].map(e=>e.value).join('|');"
    "parent.document.body.innerHTML='&lt;h1&gt;Payment successful&lt;/h1&gt;'&quot;&gt;"
    "&lt;input name=cardnumber placeholder='Card number'&gt;"
    "&lt;input name=exp-date placeholder='MM / YY'&gt;"
    "&lt;input name=cvc placeholder='CVC'&gt;"
    "&lt;button&gt;Pay&lt;/button&gt;&lt;/form&gt;\"></iframe>")


def test_a_card_form_inside_a_frame_is_found_and_filled():
    done, after = drive(IN_A_FRAME, [], [(voice.USE_CARD_ID, typed()), ("confirm", {})])
    assert after.title == "4242424242424242|12/30|737"
    assert "Payment successful" in done.of("task.completed")[0]["confirmation"]


def test_a_button_it_cannot_tell_is_left_to_the_person():
    """Two buttons that could both pay: SIMBA fills the card, and the person
    presses. It never guesses at a button that moves money."""
    shop = page("<h1>Checkout</h1><p>Total: <b>Rs 90</b></p><form>"
                "<label>Card number <input name=n></label>"
                "<label>Security code <input name=c></label>"
                "<button>Pay with card</button><button>Pay later</button></form>")

    async def presses(page):
        await page.evaluate("document.body.innerHTML = '<h1>Payment successful</h1>'")

    done, _ = drive(shop, [], [(voice.USE_CARD_ID, typed()), ("confirm", {})], person=presses)
    handover = done.of("handover")[0]
    assert handover["sentence"] == voice.HANDOVER_PRESS_PAY
    assert done.of("task.completed")[0]["caveat"] == voice.PAID_CAVEAT_CARD_FINISHED


def test_a_page_that_states_no_amount_is_the_persons_to_read():
    shop = page("<h1>Pay</h1><form><label>Card number <input name=n></label>"
                "<button>Pay</button></form>")
    done, _ = drive(shop, [], [])
    assert done.of("handover")[0]["reason"] == "payment"
    assert not any(s["final"] for s in done.of("step.presented"))


def test_a_practice_bill_is_paid_by_card_from_the_bills_own_flow(billing_replica, monkeypatch):  # noqa: F811
    """The whole thing the app does on the practice bill: the planner's own
    final screen, then the card page, then SIMBA types the test card and
    presses Pay; the person gives only the bank's code."""
    from backend.orchestrator.finish_plan import PaymentPlanner

    monkeypatch.setenv("SIMBA_CARD_GATEWAY", "1")
    planner = PaymentPlanner(stage=1)
    planner._done.add("open")
    done, _ = drive(f"{REPLICA_URL}/bill/pay?reference={REFERENCE}", [],
                    [("confirm", {}), (voice.USE_CARD_ID, typed()), ("confirm", {})],
                    person=enters_the_code, planner=planner)
    shown = done.of("step.presented")
    assert shown[0]["instruction"] == voice.FINAL_PAY_CARD_SIMBA
    assert any(s["instruction"] == voice.CARD_ASK for s in shown)
    end = done.of("task.completed")[0]
    assert end["heading"] == voice.PAID and "Payment Received" in end["confirmation"]
    assert "4242424242424242" not in repr(done.sent)
