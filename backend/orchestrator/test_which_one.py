"""B4 and B5 (2026-11-18): "Which one?" reads the whole page and is about what
was asked for, never the website's own name, and never only the first few tiles."""

import asyncio

from playwright.async_api import async_playwright

from backend.orchestrator import cards as cardlib
from backend.orchestrator.llm_loop import cards_about, goal_words


def card(i: int, name: str) -> cardlib.Card:
    return cardlib.Card(index=i, name=name, price="Rs.500", link_text=name,
                        has_picture=False, link_rect=None)


HOME = [card(0, "Laws (Readings Classics)"), card(1, "From The Margin: And Other Short Stories"),
        card(2, "The Dialogues Of Plato (Readings Classics)")]


def test_the_websites_own_name_is_not_a_topic_the_live_readings_case() -> None:
    # Readings' front page, goal "Order me an alchemist book on Readings":
    # nothing there is about an alchemist, so no card is offered (B5).
    assert cards_about(HOME, "Order me an alchemist book on Readings", {"readings"}) == []


def test_the_matches_further_down_a_long_list_reach_the_person() -> None:
    tiles = [card(i, f"Atlas of the sky {i}") for i in range(20)]
    tiles += [card(20 + i, f"The Alchemist, edition {i}") for i in range(8)]
    found = cards_about(tiles, "Order The Alchemist on Readings", {"readings"})
    assert len(found) == 8 and all("Alchemist" in c.name for c in found)


def test_the_card_saying_most_of_the_goal_comes_first() -> None:
    tiles = [card(0, "Paulo Coelho notebook"), card(1, "The Alchemist by Paulo Coelho")]
    found = cards_about(tiles, "buy The Alchemist by Paulo Coelho", set())
    assert [c.index for c in found] == [1, 0]


def test_a_goal_with_only_filler_and_the_site_has_no_topic() -> None:
    assert goal_words("Order me a book on Readings") == ["readings"]
    assert cards_about(HOME, "Order me a book on Readings", {"readings"}) == []


PAGE = """<html><body><div id=list></div><script>
  const list = document.getElementById('list');
  function add(n0, n1) { for (let i = n0; i < n1; i++) {
    const d = document.createElement('div'); d.className = 'tile';
    d.innerHTML = `<h3>Book number ${i}</h3><span>Rs.${100 + i}</span><a href="/b/${i}">Open book ${i}</a>`;
    list.appendChild(d); } }
  add(0, 10);
  // Lazy: more tiles arrive only once the page has been scrolled near its end.
  let more = false;
  window.addEventListener('scroll', () => { if (!more && window.scrollY + innerHeight > document.body.scrollHeight - 300) { more = true; add(10, 30); } });
  document.body.style.margin = 0;
  list.style.cssText = 'display:block';
  document.querySelectorAll('.tile').forEach(t => t.style.cssText = 'height:200px');
</script></body></html>"""


def test_lazy_tiles_are_loaded_and_all_of_them_are_read() -> None:
    async def run() -> tuple[int, int]:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": 1000, "height": 700})
            await page.set_content(PAGE)
            before = len(await cardlib.find_cards(page))
            await cardlib.read_whole_page(page)
            after = len(await cardlib.find_cards(page))
            await browser.close()
            return before, after

    before, after = asyncio.run(run())
    assert before == 10          # only what the first screen loaded
    assert after > 10            # the scroll loaded the rest, and none was cut at 6


def test_book_the_noun_is_not_book_the_verb() -> None:
    from backend.orchestrator.llm_loop import DOING_GOAL

    # A look-up about a book is not a booking (Readings, 2026-11-18).
    assert not DOING_GOAL.search("Find the price of the book The Alchemist on Readings")
    assert not DOING_GOAL.search("Is the book Atomic Habits in stock")
    for doing in ("Order me an alchemist book on Readings", "Book a bus from Lahore to Karachi",
                  "I want to book a train to Multan", "please book me a seat", "Buy a book",
                  "Register for CS-401", "Add Atomic Habits to my cart"):
        assert DOING_GOAL.search(doing), doing


def test_a_search_box_that_says_mobile_phones_is_searched_not_asked_for_a_phone_number() -> None:
    """OLX, 2026-11-18: "Find Cars, Mobile Phones and more..." was taken for the
    person's phone number, so the planner asked instead of searching, and never
    pressed Enter."""
    from backend.orchestrator.llm import Action
    from backend.orchestrator.llm_loop import OpenGoalPlanner, _Choice
    from backend.orchestrator.loop import Task
    from backend.orchestrator.plan import About
    from backend.perception.serializer import Element

    task = Task(goal="Find the price of a used laptop on OLX", estimated_steps=6, success=None,
                about=About())
    planner = OpenGoalPlanner(None, task)  # type: ignore[arg-type]
    box = Element(id=8, role="textbox", label="Find Cars, Mobile Phones and more...",
                  type="textbox", tag="input", input_type="search")
    choice = _Choice(action=Action(action="type", element_id=8, value="used laptop",
                                   reasoning="search"), element=box)

    move = asyncio.run(planner._shape(choice))

    assert [op.kind for op in move.operations] == ["fill", "press"]
    assert move.operations[0].value == "used laptop" and move.operations[1].value == "Enter"
    assert move.fields == []          # nothing is asked of the person


FORM = """<html><body><form onsubmit="return false">
  <label for=n>Full name</label><input id=n name=n required>
  <label for=e>Email</label><input id=e name=e type=email required>
  <input id=opt name=opt placeholder="Nickname">
  <select id=c required><option value="">Choose</option><option>Lahore</option></select>
  <label><input type=checkbox id=t required> I agree</label>
  <input type=hidden required value="">
  <button id=send type=submit>Register</button></form>
  <button id=loose>Send</button></body></html>"""


def test_required_boxes_still_empty_are_named_before_a_form_is_sent_on() -> None:
    from backend.orchestrator.llm_loop import SENDS_FORM, empty_required_boxes

    async def run() -> tuple[list[str], list[str], list[str]]:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content(FORM)
            empty = await empty_required_boxes(page.locator("#send"))
            await page.fill("#n", "Amna")
            await page.fill("#e", "a@b.pk")
            await page.select_option("#c", "Lahore")
            await page.check("#t")
            filled = await empty_required_boxes(page.locator("#send"))
            outside = await empty_required_boxes(page.locator("#loose"))
            await browser.close()
            return empty, filled, outside

    empty, filled, outside = asyncio.run(run())
    assert empty == ["Full name", "Email", "c", "I agree"] or set(empty) >= {"Full name", "Email"}
    assert "Nickname" not in empty            # not required: left alone
    assert filled == []                       # everything required is filled
    assert outside == []                      # a button in no form has none to check
    assert SENDS_FORM.search("Register") and SENDS_FORM.search("Place order")
    assert not SENDS_FORM.search("Open details")


IESCO_LIKE = """<html><body><img alt="IESCO Logo" src="logo.png">
<form><input name=ref placeholder="Enter 14-digit valid reference no">
<div id=box><img id=captchaImage alt="CAPTCHA Image" src="c.png" width=80 height=30>
<input id=captchaInput placeholder="Enter CAPTCHA code"></div>
<input type=submit id=btnSearch></form></body></html>"""


def test_a_picture_captcha_is_a_captcha_not_a_code_from_the_phone() -> None:
    """IESCO's bill page, 2026-11-18: "Enter CAPTCHA code" was read as a code
    the website sent to the phone."""
    from backend.orchestrator import helpme

    async def run() -> tuple[str, str]:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content(IESCO_LIKE)
            kind = await helpme.kind_of_page(page)
            target = await helpme.find(page, "captcha")
            box_id = await target.locator.get_attribute("id") if target.locator else ""
            await browser.close()
            return kind, box_id

    kind, box_id = asyncio.run(run())
    assert kind == "captcha"
    assert box_id == "box"       # the block holding the picture and its box


PAYMENT = """<html><body>
<label id=chosen><input type=radio name=pay value=cod checked> Cash On Delivery Rs.465</label>
<label id=other><input type=radio name=pay value=card> Card</label>
<div id=card1><input type=radio name=ship value=a checked> Standard</div>
<div id=group><input type=radio name=g value=1 checked><input type=radio name=g value=2></div>
<button id=btn>Pay</button></body></html>"""


def test_a_press_on_a_choice_already_made_is_not_a_failure() -> None:
    """Readings' checkout, 2026-11-18: a second press on the chosen Cash On
    Delivery changed nothing, was called a failed move, and the run went round."""
    from backend.orchestrator.loop import already_chosen
    from backend.perception.serializer import Element

    async def run() -> list[bool]:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content(PAYMENT)
            # `resolve` needs a real reading of the page; the element ids come from it.
            from backend.orchestrator.loop import perceive
            elements, _, _ = await perceive(page)
            found = {e.label: e.id for e in elements}
            out = []
            for label in ("Cash On Delivery Rs.465", "Card", "Pay"):
                key = next((k for k in found if label in k), None)
                out.append(bool(key) and await already_chosen(page, elements, found[key]))
            await browser.close()
            return out

    chosen, other, button = asyncio.run(run())
    assert chosen is True        # already selected: nothing to press
    assert other is False        # a different choice still gets pressed
    assert button is False       # a plain button is never "already chosen"
