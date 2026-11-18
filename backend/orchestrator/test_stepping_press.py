"""Only the press that really places the order gets a final screen (2026-11-17).

"Buy Now" and "Proceed to checkout" on a shop only move the purchase on to
its next page; "Place order" is the one that orders. Until today each of them
had a final screen, so a person was asked three times to say yes to one
order. A stepping press now runs as a checklist line, and only when nothing on
the page says it would order at once (a one-click button, a card form, a
"place order" button already there). The rule's default stays deny: anything
not recognised as a stepping press keeps its final screen.
"""

from urllib.parse import quote

import pytest
from playwright.async_api import async_playwright

from backend.orchestrator import voice
from backend.orchestrator.loop import Task, is_stepping, only_moves_on, run_task, would_change
from backend.orchestrator.plan import (
    About,
    Expectation,
    HardcodedPlanner,
    Operation,
    PlanStep,
    Target,
)
from backend.orchestrator.test_asking import ScriptedConnection
from backend.orchestrator.test_checklist import run
from backend.orchestrator.test_final_step import Unmarked, press


@pytest.mark.parametrize("label", [
    "Buy Now", "cart Buy Now", "Proceed to checkout", "Proceed to Checkout", "Checkout",
    "Check out", "Continue to checkout", "Continue to payment", "Go to cart", "View cart",
    "Proceed to shipping",
])
def test_these_only_move_a_purchase_on(label: str) -> None:
    assert is_stepping(label)


@pytest.mark.parametrize("label", [
    "Place order", "Place Order (Cash on Delivery)", "Confirm order", "Complete purchase",
    "Pay now", "Pay Rs 4495", "Submit", "Book now", "Register", "Sign up", "Order now",
    "Confirm and pay", "Buy now and pay", "Search", "Add to cart", "",
])
def test_these_are_never_taken_for_a_stepping_press(label: str) -> None:
    assert not is_stepping(label)


def test_the_words_alone_still_say_it_would_change() -> None:
    # would_change stays blunt; the page guard is what lets a stepping press by.
    assert would_change(press("Proceed to checkout"), Unmarked())
    assert would_change(press("Buy Now"), Unmarked())


def page_with(body: str) -> str:
    return "data:text/html," + quote(f"<title>t</title>{body}")


def moves_on(body: str, label: str) -> bool:
    async def inner() -> bool:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await page.goto(page_with(body))
                return await only_moves_on(page, [], press(label))
            finally:
                await browser.close()

    return run(inner())


def test_a_plain_product_page_lets_buy_now_by() -> None:
    assert moves_on("<h1>The Alchemist</h1><p>Rs 4495</p><button>Buy Now</button>", "Buy Now")


def test_a_one_click_button_keeps_its_final_screen() -> None:
    assert not moves_on("<p>Rs 10</p><button>Buy Now</button><p>1-Click ordering is on</p>",
                        "Buy Now")
    assert not moves_on("<button>Buy Now</button><button>Pay with Apple Pay</button>", "Buy Now")


def test_a_page_with_a_card_form_keeps_its_final_screen() -> None:
    assert not moves_on("<input autocomplete='cc-number'><button>Checkout</button>", "Checkout")


def test_a_page_that_already_has_the_order_button_keeps_its_final_screen() -> None:
    assert not moves_on("<button>Place Order</button><button>Checkout</button>", "Checkout")


def test_a_hidden_order_button_does_not_count() -> None:
    """Readings keeps "Place Order" in a drawer its Buy Now opens."""
    assert moves_on("<button>Buy Now</button><div style='display:none'>"
                    "<button>Place Order</button></div>", "Buy Now")


def test_a_committing_word_is_never_let_by() -> None:
    assert not moves_on("<button>Place order</button>", "Place order")


# --- in the real loop ------------------------------------------------------------------

SHOP = page_with(
    "<p>The Alchemist <b>Rs 4495</b></p>"
    "<button id='go' onclick=\"document.title='cart'; this.remove();"
    "var b=document.createElement('button'); b.textContent='Place order';"
    "b.onclick=function(){document.title='ordered'};"
    "document.body.appendChild(b)\">Proceed to checkout</button>")


class Unmarking(HardcodedPlanner):
    marks_changes = False


def test_only_the_press_that_orders_gets_a_final_screen() -> None:
    steps = [
        PlanStep(instruction="Go to checkout.", detail="", actions=voice.actions("Go"),
                 operations=[Operation("click", Target("button", "Proceed to checkout"))],
                 expect=Expectation(title_contains="cart"), safe=True,
                 doing="Going to checkout"),
        PlanStep(instruction="Place the order.", detail="", actions=voice.actions("Go"),
                 operations=[Operation("click", Target("button", "Place order"))],
                 expect=Expectation(title_contains="ordered")),
    ]

    async def inner():
        connection = ScriptedConnection([("confirm", {})])
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await run_task(page, connection, Unmarking(steps),
                               Task(goal="g", estimated_steps=2, about=About()), SHOP, auto=True)
                return connection, await page.title()
            finally:
                await browser.close()

    connection, title = run(inner())
    finals = [m for m in connection.of("step.presented") if m.get("final") is not None]
    assert len(finals) == 1, [m["instruction"] for m in finals]
    assert finals[0]["actions"][0]["label"] == voice.DO_IT
    assert title == "ordered"


# --- a typed value read back after the page moved on (2026-11-17) -----------------------


def test_reading_back_after_a_search_moved_the_page_does_not_crash() -> None:
    """Found live on Readings: typing a search and pressing Enter loaded the
    results, where the same element number named a "View All" link, and
    reading its value raised an unhandled timeout that ended the session."""
    from backend.orchestrator.loop import perceive, verify_typed

    async def inner():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await page.goto(page_with("<input aria-label='Search books'><a href='#a'>x</a>"))
                elements, _, _ = await perceive(page)
                box = next(e for e in elements if e.label == "Search books")
                await page.evaluate(
                    "document.body.innerHTML = '<a href=\"#a\">View All</a>"
                    "<a href=\"#b\">View All</a><a href=\"#c\">View All</a>'")
                return await verify_typed(page, box.id, box, "alchemist")
            finally:
                await browser.close()

    assert run(inner()) is None
