"""Point the serializer at the billing replica and report what it sees.

Produced: EVALUATION.md 2026-09-06, "perception against a second replica" —
the per-page element table and the three gaps. No model.

Expects the billing replica already running on :5100
(`python replicas/billing/app.py`). Moved from `.scratch/probe_billing.py`
on 2026-09-17, unchanged.

Run from the repo root: `python -m tools.evaluation.billing_perception_probe`.
"""

from playwright.sync_api import sync_playwright

from backend.perception.overlays import COMPUTED_STYLES, analyse
from backend.perception.serializer import serialize
from tools.evaluation.conditions import banner  # noqa: E402

BASE = "http://127.0.0.1:5100"
VIEWPORT = (1280, 800)


def show(title, elements):
    print(f"\n=== {title}: {len(elements)} interactive elements ===")
    buckets = {}
    for e in elements:
        buckets.setdefault(e.role, []).append(e)
    for role, group in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
        print(f"  {role:10} x{len(group)}")
    flagged = [e for e in elements if e.overlay or e.occluded]
    print(f"  overlay={sum(e.overlay for e in elements)} "
          f"occluded={sum(e.occluded for e in elements)} "
          f"dead_link={sum(e.dead_link for e in elements)}")
    if flagged:
        for e in flagged:
            print(f"    flagged: {e.role} {e.label!r} overlay={e.overlay} occluded={e.occluded}")
    # Anything with no accessible name at all is unusable to a planner.
    nameless = [e for e in elements if not e.label]
    if nameless:
        print(f"  NAMELESS: {[(e.role, e.tag) for e in nameless]}")
    return elements


def blockers(page):
    cdp = page.context.new_cdp_session(page)
    cdp.send("DOMSnapshot.enable")
    snap = cdp.send("DOMSnapshot.captureSnapshot", {"computedStyles": COMPUTED_STYLES})
    cdp.detach()
    report = analyse(snap, VIEWPORT)
    print(f"  blockers detected: {len(report.blockers)}")
    for b in report.blockers:
        print(f"    {b.reason}")
    # What does the cookie bar actually measure?
    strings = snap["strings"]
    doc = snap["documents"][0]
    layout, nodes = doc["layout"], doc["nodes"]
    for i, ni in enumerate(layout["nodeIndex"]):
        styles = [strings[s] for s in layout["styles"][i]]
        if styles and styles[0] == "fixed":
            x, y, w, h = layout["bounds"][i]
            name = strings[nodes["nodeName"][ni]]
            cov = (w * h) / (VIEWPORT[0] * VIEWPORT[1])
            print(f"    fixed {name} at ({round(x)},{round(y)}) {round(w)}x{round(h)} "
                  f"z={styles[1]} coverage={cov:.1%}")


print(banner(), flush=True)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": VIEWPORT[0], "height": VIEWPORT[1]})

    page.goto(BASE + "/")
    lookup = show("LOOKUP (cookie bar up, accordions collapsed)", serialize(page))
    blockers(page)
    print("  accordion content visible before expansion?",
          any("full enquiry guide" in e.label.lower() for e in lookup))

    page.click(".acc-head")
    page.wait_for_timeout(200)
    after = serialize(page)
    print("  after expanding the first accordion:", len(after), "elements;",
          "guide link present?",
          any("full enquiry guide" in e.label.lower() for e in after))

    page.goto(BASE + "/")
    page.fill("#reference", "04141234567890")
    page.click("button[type=submit]")
    page.wait_for_load_state()
    results = show("RESULTS", serialize(page))
    blockers(page)

    print("\n  is the payable amount reachable at all?")
    print("   '14,382' among element labels:",
          any("14,382" in e.label for e in results))
    print("   text is present in the page body:", "14,382" in page.content())

    page.goto(BASE + "/bill/detail?reference=04141234567890")
    show("DETAIL", serialize(page))

    browser.close()
