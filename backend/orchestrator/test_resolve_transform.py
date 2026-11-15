"""An element is found again whatever case the page's styling gives its name.

Step E (EVALUATION.md, 2026-11-15): on Readings every result link is styled
`text-transform: capitalize`. Chromium's accessibility tree names the link as
it is drawn ("Atomic Habits: An Easy And Proven Way"), Playwright's name match
reads the page's own text ("Atomic Habits: an Easy and Proven Way") and, being
exact and case-sensitive, found nothing: the press timed out, was tried again,
timed out again, and the run stopped as "stuck" — 3 runs of 3. `loop.resolve`
now matches the name without regard to case.
"""

import asyncio

from playwright.async_api import async_playwright

from backend.orchestrator import loop

PAGE = """<html><body>
<style>.t { text-transform: capitalize }</style>
<p id="result">nothing pressed</p>
<a href="#one" class="t" onclick="document.getElementById('result').textContent='one'">atomic habits: an easy and proven way</a>
<a href="#two" class="t" onclick="document.getElementById('result').textContent='two'">another book: and its second part</a>
<a href="#up" onclick="document.getElementById('result').textContent='upper'">SAME WORDS</a>
<a href="#low" onclick="document.getElementById('result').textContent='lower'">same words</a>
</body></html>"""


async def pressed(label_part: str, nth: int = 0) -> str:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            page = await browser.new_page()
            await page.set_content(PAGE)
            elements, _, _ = await loop.perceive(page)
            chosen = [e for e in elements if e.role == "link"
                      and label_part in (e.label or "").lower()][nth]
            await loop.resolve(page, elements, chosen.id).click(timeout=3000)
            return await page.inner_text("#result")
        finally:
            await browser.close()


def test_a_link_whose_name_the_page_capitalises_is_found_and_pressed() -> None:
    assert asyncio.run(pressed("atomic habits")) == "one"
    assert asyncio.run(pressed("another book")) == "two"


def test_two_links_whose_names_differ_only_by_case_are_still_told_apart() -> None:
    assert asyncio.run(pressed("same words", 0)) == "upper"
    assert asyncio.run(pressed("same words", 1)) == "lower"
