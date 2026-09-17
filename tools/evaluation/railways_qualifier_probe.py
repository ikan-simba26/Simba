"""Produced: EVALUATION.md 2026-09-09b, "Qualifiers work, and nothing used
them" — the duplicate-label table. **Live site**: opens the calendar,
presses Next Month, picks the 15th. Nothing is submitted.

Moved from `.scratch/probe_qualifier.py` on 2026-09-17, unchanged but for paths.

Run from the repo root: `python -m tools.evaluation.railways_qualifier_probe`.
"""

import sys, io
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from collections import Counter
from playwright.sync_api import sync_playwright
from backend.perception.serializer import read

URL = "https://www.pakrailways.gov.pk/train"
UA = ("SIMBA-screener/0.1 (final-year university project; read-only; "
      "+https://github.com/ikan-simba26/Simba)")
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(user_agent=UA, viewport={"width":1280,"height":800})
    pg = ctx.new_page(); pg.set_default_timeout(10000)
    pg.goto(URL, wait_until="domcontentloaded", timeout=60000); pg.wait_for_timeout(3000)
    d = pg.get_by_role("textbox", name="Departure Date", exact=True)
    d.click(); pg.wait_for_timeout(800)

    for view_name in ("September (as opened)", "October (after Next Month)"):
        els = read(pg).elements
        days = [e for e in els if e.inferred and e.role == "option"]
        counts = Counter(e.label for e in days)
        dupes = {k: v for k, v in counts.items() if v > 1}
        print(f"\n=== {view_name}: {len(days)} day cells, {len(dupes)} duplicate labels")
        print("   month button:", [e.label for e in els if e.role=='button' and e.label in
              ('September','October','November')])
        for label in sorted(dupes, key=lambda x: int(x)):
            same = [e for e in days if e.label == label]
            print(f"   '{label}' x{len(same)}: " +
                  " | ".join(f"qualifier={e.qualifier!r}" for e in same))
        plain15 = [e for e in days if e.label == "15" and e.qualifier == ""]
        print(f"   day 15 with no qualifier: {len(plain15)}")
        if view_name.startswith("October"):
            from backend.orchestrator.loop import pick
            from backend.orchestrator.plan import Target
            chosen = pick(els, Target("option", "15", qualifier=""))
            el = next(e for e in els if e.id == chosen)
            print(f"   pick(Target('option','15',qualifier='')) -> id {chosen} "
                  f"qualifier={el.qualifier!r}")
            pg.locator(el.locator_hint).click(); pg.wait_for_timeout(900)
            print("   date field now:", repr(d.input_value()))
            break
        pg.get_by_role("button", name="Next Month", exact=True).click()
        pg.wait_for_timeout(800)
    b.close()
