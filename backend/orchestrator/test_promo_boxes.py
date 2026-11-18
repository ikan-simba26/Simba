"""A promo, coupon or gift-card box is not a card or a one-time code (2026-11-17).

Found live on Readings' checkout: "Promo Code" and "Gift Card Code" boxes made
the page read as asking for card details, then as asking for a one-time code,
and the run was handed to the person at a page that only wanted an address.
"""

from urllib.parse import quote

import pytest
from playwright.async_api import async_playwright

from backend.orchestrator import helpme
from backend.orchestrator.loop import page_asks_for_payment, perceive
from backend.orchestrator.test_checklist import run


def on_page(body: str):
    async def inner():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await page.goto("data:text/html," + quote(f"<title>t</title>{body}"))
                elements, _, _ = await perceive(page)
                return (await page_asks_for_payment(page, elements),
                        (await helpme.find(page, "code")).locator is not None,
                        await helpme.kind_of_page(page))
            finally:
                await browser.close()

    return run(inner())


CHECKOUT = ("<h1>Checkout</h1><input type='email' placeholder='Email'>"
            "<textarea placeholder='Special Instructions'></textarea>"
            "<input type='text' placeholder='Promo Code'><button>Apply</button>"
            "<input type='text' placeholder='Gift Card Code'><button>Apply</button>"
            "<button>Place Order</button>")


def test_promo_and_gift_card_boxes_are_not_payment_or_a_code() -> None:
    pays, code, kind = on_page(CHECKOUT)
    assert (pays, code, kind) == (False, False, "other")


@pytest.mark.parametrize("body", [
    "<label>Coupon code <input name='coupon'></label>",
    "<input name='voucher_code' placeholder='Voucher'>",
    "<input aria-label='Discount code'>",
])
def test_other_discount_boxes_are_not_a_code_either(body: str) -> None:
    _, code, kind = on_page(body)
    assert not code and kind == "other"


def test_a_card_number_box_still_is_payment() -> None:
    pays, _, kind = on_page("<label>Card number <input name='cardnumber'></label>")
    assert pays


def test_a_one_time_code_box_still_is_a_code() -> None:
    _, code, kind = on_page("<input placeholder='Enter the one-time code (OTP)'>")
    assert code and kind == "code"
    _, code, _ = on_page("<input name='code' placeholder='Verification code'>")
    assert code


# --- the amount a final screen shows is the total (2026-11-17) --------------------------

READINGS_CHECKOUT = (
    "<div>Orders Cart</div><p>Our Price: Rs.4495 Rs.4045</p><p>You Save: Rs.450</p>"
    "<p>List Price: £20</p><div>Payment</div><div>Cash On Delivery</div><div>Rs.4195</div>"
    "<button>Place Order</button><div>Subtotal</div><div>Rs.4045</div>"
    "<div>Standard Shipping</div><div>Rs.150</div><div>Total</div><div>Rs.4195</div>")


def amounts(body: str):
    from backend.orchestrator.loop import amounts_on_page

    async def inner():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await page.goto("data:text/html," + quote(f"<title>t</title>{body}"))
                return [(d.label, d.value) for d in await amounts_on_page(page)]
            finally:
                await browser.close()

    return run(inner())


def test_the_total_comes_first_and_the_label_may_be_on_the_line_before() -> None:
    got = amounts(READINGS_CHECKOUT)
    assert got[0] == ("Total", "Rs.4195")
    assert ("Standard Shipping", "Rs.150") in got
    assert len(got) <= 3


def test_without_a_total_the_first_amounts_are_shown_as_before() -> None:
    assert amounts("<p>Fare: Rs 3,250</p><p>Tax Rs 10</p>") == [("Fare", "Rs 3,250"),
                                                                ("Tax", "Rs 10")]
