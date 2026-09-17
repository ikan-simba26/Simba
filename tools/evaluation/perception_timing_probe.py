"""Produced: EVALUATION.md 2026-09-08, the profiling table (`read()` 0.19s
idle, 0.22s calendar open). **Live site**: loads it once and opens the
calendar. Nothing is submitted.

Moved from `.scratch/probe_timing.py` on 2026-09-17, unchanged but for paths.

Run from the repo root: `python -m tools.evaluation.perception_timing_probe`.
"""

import sys, io, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright
from backend.perception.serializer import read, COMPUTED_STYLES
from backend.perception.snapshot import parse
from backend.perception.content import extract
from backend.perception.interactivity import find_inferred
from backend.perception.overlays import analyse

URL = "https://www.pakrailways.gov.pk/train"
UA = ("SIMBA-screener/0.1 (final-year university project; read-only; "
      "+https://github.com/ikan-simba26/Simba)")
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(user_agent=UA, viewport={"width":1280,"height":800})
    pg = ctx.new_page()
    pg.goto(URL, wait_until="domcontentloaded", timeout=60000); pg.wait_for_timeout(3000)

    for label in ("closed", "calendar open"):
        if label == "calendar open":
            pg.get_by_role("textbox", name="Departure Date", exact=True).click()
            pg.wait_for_timeout(800)
        t0=time.monotonic(); view = read(pg); t1=time.monotonic()
        cdp = ctx.new_cdp_session(pg); cdp.send("DOMSnapshot.enable")
        t2=time.monotonic()
        snap = cdp.send("DOMSnapshot.captureSnapshot",{"computedStyles":COMPUTED_STYLES})
        t3=time.monotonic(); cdp.detach()
        doc = parse(snap); t4=time.monotonic()
        analyse(doc,(1280,800)); t5=time.monotonic()
        find_inferred(doc,(1280,800),set()); t6=time.monotonic()
        extract(doc); t7=time.monotonic()
        print(f"\n=== {label}: {len(view.elements)} elements, {len(doc)} DOM nodes")
        print(f"  read()          {t1-t0:6.2f}s")
        print(f"  captureSnapshot {t3-t2:6.2f}s")
        print(f"  parse           {t4-t3:6.2f}s")
        print(f"  analyse         {t5-t4:6.2f}s")
        print(f"  find_inferred   {t6-t5:6.2f}s")
        print(f"  extract         {t7-t6:6.2f}s")
    b.close()
