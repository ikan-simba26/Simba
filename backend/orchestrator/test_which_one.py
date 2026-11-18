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
