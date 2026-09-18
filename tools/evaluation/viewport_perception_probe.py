"""The same pages read headless and inside the Electron host, side by side.

Every perception figure in EVALUATION.md before 2026-09-18 was taken from a
headless browser. On 2026-09-17 a bug turned up that exists only in the host:
the live results' heading strip carries a scrollbar spacer there and not
headless, so nothing paired `Train No.` with `2DN` and a completed run showed
no answer (2026-09-17i). One environment-only defect is one too many to leave
the rest unchecked.

So this reads each page twice — once in its own headless Chromium, once
through the host's covered site view over CDP — and prints the two sets of
numbers next to each other with the differences called out.

Needs the host up, and the replicas it will visit:

    python replicas/registration/app.py          # :5000
    python replicas/billing/app.py               # :5100
    cd frontend; $env:SIMBA_START_URL = "http://127.0.0.1:5000"; npm start

then, from the repo root:

    python -m tools.evaluation.viewport_perception_probe

**Live site**: the railways pages are read, and the results page needs one
read-only search per environment — two in a full run. No model, no quota.
Writes `logs/viewport_perception.json`.
"""

import asyncio
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright

from backend.perception.serializer import read_async
from tools.evaluation.conditions import banner, record

REPO_ROOT = Path(__file__).resolve().parents[2]
CDP = "http://127.0.0.1:9222"
VIEWPORT = {"width": 1280, "height": 800}
UA = ("SIMBA-screener/0.1 (final-year university project; read-only; "
      "+https://github.com/ikan-simba26/Simba)")

REGISTRATION = "http://127.0.0.1:5000"
BILLING = "http://127.0.0.1:5100"
RAILWAYS = "https://www.pakrailways.gov.pk/train"
REFERENCE = "04141234567890"

# The route the results page is read for. Overridable, because the scrollbar
# spacer that broke the header join only exists while the results body
# overflows: a route with one train on it cannot show the bug either way.
FROM_STATION = os.environ.get("SIMBA_PROBE_FROM", "LAHORE CANTT")
TO_STATION = os.environ.get("SIMBA_PROBE_TO", "KARACHI CANTT")


#: Whether a heading strip carries a scrollbar spacer, straight from the DOM.
#:
#: `table_widths` above is measured after `_adopt_headers` has already
#: discounted an empty trailing cell, so it reads 4 whether the strip had four
#: cells or five. This counts cells before anything touches them, and says
#: whether the results body is scrolling — the state that adds the spacer.
HEADING_STRIPS = """() => ({
  tables: [...document.querySelectorAll('table')].map(table => {
    const cells = table.rows[0] ? [...table.rows[0].cells] : [];
    return {
      cells: cells.length,
      empty: cells.filter(cell => !cell.textContent.trim()).length,
      named_gutter: cells.filter(cell => cell.classList.contains('gutter')).length,
    };
  }),
  scrolling: [...document.querySelectorAll('div')].filter(box =>
    box.scrollHeight - box.clientHeight > 4 &&
    ['auto', 'scroll'].includes(getComputedStyle(box).overflowY)).length,
})"""


async def measure(page) -> dict:
    """The figures EVALUATION.md records for a page, all from one read."""
    view = await read_async(page)
    elements, content = view.elements, view.content
    return {
        "elements": len(elements),
        "unnamed": sum(1 for e in elements if not e.label),
        "dead_links": sum(1 for e in elements if e.dead_link),
        "overlay": sum(1 for e in elements if e.overlay),
        "occluded": sum(1 for e in elements if e.occluded),
        "inferred": sum(1 for e in elements if e.inferred),
        "headings": len(content.headings),
        "tables": len(content.tables),
        "rows": sum(len(table.rows) for table in content.tables),
        "table_widths": [len(table.headers) for table in content.tables],
        "pairs": len(content.pairs),
        "values": len(content.values),
    }


# --- the pages, each as "get there, then measure" ----------------------------


async def registration_courses(page) -> dict:
    """The course list with its modal up: 66 elements when first measured."""
    await page.goto(f"{REGISTRATION}/")
    await page.get_by_role("textbox", name="Student ID or Username").fill("student")
    await page.get_by_role("textbox", name="Password").fill("x")
    await page.get_by_role("button", name="Sign In").click()
    await page.wait_for_url("**/courses")
    return await measure(page)


async def billing_results(page) -> dict:
    """The enquiry result, where the amount is: 39 elements when first measured."""
    await page.goto(f"{BILLING}/bill?reference={REFERENCE}")
    found = await measure(page)
    view = await read_async(page)
    found["P/WITHIN"] = view.content.value_for("P/WITHIN")
    return found


async def railways_idle(page) -> dict:
    """The live search page, untouched: 18 elements when first measured."""
    await page.goto(RAILWAYS, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(3000)
    return await measure(page)


async def railways_results(page) -> dict:
    """The live results, which is where the host and headless came apart.

    One read-only search: two stations, next month's 15th, submit.
    """
    await page.goto(RAILWAYS, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(3000)
    page.set_default_timeout(20000)

    for field, station in (("From", FROM_STATION), ("To", TO_STATION)):
        box = page.get_by_role("textbox", name=field, exact=True)
        await box.click()
        await box.press("Control+a")
        await box.press_sequentially(station)
        await page.wait_for_timeout(1600)
        option = next(e for e in (await read_async(page)).elements
                      if e.inferred and e.label == station)
        await page.locator(option.locator_hint).click()
        await page.wait_for_timeout(700)

    await page.get_by_role("textbox", name="Departure Date", exact=True).click()
    await page.wait_for_timeout(600)
    await page.get_by_role("button", name="Next Month", exact=True).click()
    await page.wait_for_timeout(600)
    day = next(e for e in (await read_async(page)).elements
               if e.inferred and e.label == "15" and e.qualifier == "")
    await page.locator(day.locator_hint).click()
    await page.wait_for_timeout(600)
    await page.get_by_role("button", name="", exact=True).nth(0).click()
    await page.wait_for_timeout(8000)

    found = await measure(page)
    view = await read_async(page)
    found["route"] = f"{FROM_STATION} -> {TO_STATION}"
    # The serialized widths are post-join, so they cannot say whether a gutter
    # cell was there to discount. This reads the markup itself.
    found["markup"] = await page.evaluate(HEADING_STRIPS)
    found["Train No."] = view.content.values_for("Train No.")
    found["Duration"] = view.content.values_for("Duration")
    return found


PAGES = {
    "registration /courses": registration_courses,
    "billing /bill": billing_results,
    "railways idle": railways_idle,
    "railways results": railways_results,
}

# What each was recorded as, headless, when it was first measured.
FIRST_RECORDED = {
    "registration /courses": {"elements": 66, "overlay": 1, "occluded": 65, "dead_links": 44},
    "billing /bill": {"elements": 39},
    "railways idle": {"elements": 18, "unnamed": 4, "dead_links": 3},
}


async def in_host(measurer) -> dict:
    """Through the host's site view, which is what a real run reads."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.connect_over_cdp(CDP)
        pages = [page for context in browser.contexts for page in context.pages]
        site = next(p for p in pages if not p.url.startswith(("file:", "devtools:", "chrome:")))
        try:
            return await measurer(site)
        finally:
            # Leave the host where it was found, and detach rather than close.
            await browser.close()


async def headless(measurer) -> dict:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        context = await browser.new_context(user_agent=UA, viewport=VIEWPORT)
        page = await context.new_page()
        try:
            return await measurer(page)
        finally:
            await browser.close()


def differences(head: dict, host: dict) -> dict:
    return {key: {"headless": head.get(key), "host": host.get(key)}
            for key in sorted(set(head) | set(host))
            if head.get(key) != host.get(key)}


async def main() -> None:
    print(banner(), flush=True)
    wanted = [name for name in PAGES if not sys.argv[1:] or
              any(argument in name for argument in sys.argv[1:])]
    results = {}
    for name in wanted:
        measurer = PAGES[name]
        print(f"\n=== {name} ===", flush=True)
        head = await headless(measurer)
        host = await in_host(measurer)
        gaps = differences(head, host)
        results[name] = {"headless": head, "host": host, "differences": gaps,
                         "first_recorded": FIRST_RECORDED.get(name)}
        print(f"  headless {head}", flush=True)
        print(f"  host     {host}", flush=True)
        if gaps:
            print(f"  DIFFERENT: {gaps}", flush=True)
        else:
            print("  identical", flush=True)
        recorded = FIRST_RECORDED.get(name)
        if recorded:
            drift = {k: {"then": v, "headless now": head.get(k), "host now": host.get(k)}
                     for k, v in recorded.items()
                     if head.get(k) != v or host.get(k) != v}
            print(f"  against the first recorded figures: {drift or 'unchanged'}", flush=True)

    record(REPO_ROOT / "logs" / "viewport_perception.json", results, pages=len(results))
    print("\nwrote logs/viewport_perception.json", flush=True)
    for name, found in results.items():
        print(f"  {name}: {'differs — ' + ', '.join(found['differences']) if found['differences'] else 'same in both'}")


asyncio.run(main())
