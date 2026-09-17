"""Produced: EVALUATION.md 2026-09-08, "What perception now sees that it could
not" — element counts before and after typing `LAH`. **Live site**: loads
it once and types three letters into a search field. Nothing is submitted.

Moved from `.scratch/probe_railways.py` on 2026-09-17, unchanged but for paths.

Run from the repo root: `python -m tools.evaluation.railways_inference_probe`.
"""

import sys, time
from pathlib import Path
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from playwright.sync_api import sync_playwright
from backend.perception.serializer import read
from backend.perception.overlays import analyse
from backend.perception.snapshot import COMPUTED_STYLES
from tools.evaluation.conditions import banner  # noqa: E402

URL = "https://www.pakrailways.gov.pk/train"
UA = ("SIMBA-screener/0.1 (final-year university project; read-only; "
      "+https://github.com/ikan-simba26/Simba)")

print(banner(), flush=True)
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(user_agent=UA, viewport={"width":1280,"height":800})
    pg = ctx.new_page()
    pg.goto(URL, wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(3000)

    view = read(pg)
    print(f"BEFORE typing: {len(view.elements)} elements, {sum(1 for e in view.elements if e.inferred)} inferred")
    for e in view.elements:
        print(f"  [{e.id}] {e.role:9} {e.label[:44]!r:48} inf={e.inferred} {e.inferred_from or ''} tag={e.tag}")

    box = pg.get_by_role("textbox", name="From", exact=True)
    box.click()
    box.type("LAH", delay=120)
    pg.wait_for_timeout(1800)

    view2 = read(pg)
    inf = [e for e in view2.elements if e.inferred]
    print(f"\nAFTER typing LAH: {len(view2.elements)} elements, {len(inf)} inferred")
    for e in inf:
        print(f"  [{e.id}] {e.role:9} {e.label[:44]!r:48} via={e.inferred_from} tag={e.tag} rect={tuple(round(v) for v in e.rect)}")
        print(f"        path={e.locator_hint}")

    # target-scoped blocker check against the To field
    to = next((e for e in view2.elements if e.label == "To" and e.role == "textbox"), None)
    if to:
        cdp = ctx.new_cdp_session(pg)
        cdp.send("DOMSnapshot.enable")
        snap = cdp.send("DOMSnapshot.captureSnapshot", {"computedStyles": COMPUTED_STYLES})
        cdp.detach()
        plain = analyse(snap, (1280,800))
        scoped = analyse(snap, (1280,800), target=to.backend_node_id)
        print(f"\nTo field rect={tuple(round(v) for v in to.rect)} occluded={to.occluded}")
        print(f"  page-level blockers: {len(plain.blockers)}")
        print(f"  target-scoped blockers: {len(scoped.blockers)}")
        for bl in scoped.blockers:
            print(f"    {bl.reason} rect={tuple(round(v) for v in bl.rect)} scoped={bl.scoped_to_target}")

    c = view2.content
    print(f"\ncontent: {len(c.headings)} headings, {len(c.tables)} tables, {len(c.pairs)} pairs, {len(c.values)} values")
    print(f"  headings: {[(h.level,h.text[:50]) for h in c.headings][:8]}")
    print(f"  values: {[(v.text[:40],v.font_size) for v in c.values][:8]}")
    b.close()
