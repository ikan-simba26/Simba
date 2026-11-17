"""What the AI planner is shown on the page the SIMBA window's site view is on
now (2026-11-17): the numbered elements and the page's text, as `llm_loop`
renders them. Read-only; nothing is clicked. For working out why a run chose
what it did.

    python -m tools.evaluation.see_page [--text] [--cards]
"""

from __future__ import annotations

import asyncio
import sys

from playwright.async_api import async_playwright

CDP = "http://127.0.0.1:9222"


async def main() -> None:
    from backend.orchestrator import loop
    from backend.orchestrator.llm_loop import render_content, render_page

    async with async_playwright() as playwright:
        browser = await playwright.chromium.connect_over_cdp(CDP)
        pages = [p for c in browser.contexts for p in c.pages if not p.url.startswith("file:")]
        page = pages[0]
        print("URL:", page.url)
        elements, snapshot, _view = await loop.perceive(page)
        print(render_page(elements))
        if "--text" in sys.argv:
            print("\n--- page says ---\n" + render_content(snapshot.content, 3000))
        if "--cards" in sys.argv:
            from backend.orchestrator import cards

            found = await cards.find_cards(page)
            for card in found:
                print(card)
        await browser.close()


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    asyncio.run(main())
