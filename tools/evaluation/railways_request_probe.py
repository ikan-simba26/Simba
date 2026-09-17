"""Produced: the evidence in EVALUATION.md "The DOM is not the application's
state" — the field reading `2026-10-15` while the request said
`"travelDate":""`. **Live site, and it submits two searches.** Read-only
searches, but searches: run it rarely.

Moved from `.scratch/probe_api.py` on 2026-09-17, unchanged but for paths.

Run from the repo root: `python -m tools.evaluation.railways_request_probe`.
"""

import sys, io, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright
from backend.perception.serializer import read

URL = "https://www.pakrailways.gov.pk/train"
UA = ("SIMBA-screener/0.1 (final-year university project; read-only; "
      "+https://github.com/ikan-simba26/Simba)")
seen = []

def station(pg, field, typed, want):
    loc = pg.get_by_role("textbox", name=field, exact=True)
    loc.click(); pg.wait_for_timeout(400)
    loc.press_sequentially(typed, delay=110); pg.wait_for_timeout(1500)
    opts = [e for e in read(pg).elements if e.inferred and e.role=="option"]
    hit = next((o for o in opts if o.label == want), None)
    if hit: pg.locator(hit.locator_hint).click(); pg.wait_for_timeout(700)
    return bool(hit)

def grab(resp):
    if "trainInfoList" in resp.url:
        try: seen.append(json.dumps(resp.json())[:900])
        except Exception as e: seen.append(f"<unparseable {e}>")

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(user_agent=UA, viewport={"width":1280,"height":800})
    pg = ctx.new_page(); pg.on("response", grab)
    pg.goto(URL, wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(3000)
    station(pg, "From", "LAH", "LAHORE CANTT")
    station(pg, "To", "KARACHI", "KARACHI CANTT")

    for date in ("2026-10-15", "2026-09-21"):
        d = pg.get_by_role("textbox", name="Departure Date", exact=True)
        d.click(); pg.wait_for_timeout(400)
        d.press("Control+a"); d.press_sequentially(date, delay=60); d.press("Enter")
        pg.wait_for_timeout(800)
        seen.clear()
        pg.get_by_role("button", name="", exact=True).nth(0).click()
        pg.wait_for_timeout(7000)
        v = read(pg)
        print(f"\n=== {date}: values={ {n: pg.get_by_role('textbox', name=n, exact=True).input_value() for n in ('From','To','Departure Date')} }")
        print(f"    elements={len(v.elements)} tables={len(v.content.tables)} pairs={len(v.content.pairs)}")
        print(f"    api response: {seen[0] if seen else '(none)'}")
        body = " / ".join(t for t in pg.inner_text("body").split("\n") if t.strip())
        print(f"    body: {body[:260]}")
    b.close()
