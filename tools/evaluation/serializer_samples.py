"""Capture real serializer output for HANDOVER.md. 

1. The registration replica's course page, straight after signing in — the
   modal is up, so the OVERLAY banner and OCCLUDED marks appear.
2. The billing replica's results page — the content channel.
3. The live railways search page, loaded once, never touched.

Produced: the samples in HANDOVER.md section 9 and the "What perception reads
today" table in EVALUATION.md 2026-09-17. Starts both replicas itself on
:5198 and :5199. **Live site**: loads it once, touches nothing. No model.

Moved from `.scratch/sample_serializer.py` on 2026-09-17, unchanged but for paths.

Run from the repo root: `python -m tools.evaluation.serializer_samples`.
"""

import asyncio
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from backend.orchestrator.llm_loop import render_page  # noqa: E402
from backend.perception.serializer import read_async  # noqa: E402
from tools.screen_site import USER_AGENT  # noqa: E402
from tools.evaluation.conditions import banner  # noqa: E402


def wait(url: str) -> None:
    for _ in range(100):
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError(url)


def show_content(content) -> None:
    for h in content.headings[:6]:
        print(f"  heading h{h.level}: {h.text!r}")
    for t in content.tables[:2]:
        print(f"  table headers: {t.headers}")
        for r in t.rows[:2]:
            print(f"    row: {r.cells}")
    for p in content.pairs[:8]:
        print(f"  pair: {p.label!r} -> {p.value!r}")
    for v in content.values[:4]:
        print(f"  prominent: {v.text!r} ({v.font_size}px)")


async def main() -> None:
    print(banner(), flush=True)
    from playwright.async_api import async_playwright

    py = sys.executable
    reg = subprocess.Popen([py, "app.py"], cwd=REPO / "replicas" / "registration",
                           env={**os.environ, "PORT": "5198"},
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    bill = subprocess.Popen([py, "app.py"], cwd=REPO / "replicas" / "billing",
                            env={**os.environ, "PORT": "5199"},
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait("http://127.0.0.1:5198/")
        wait("http://127.0.0.1:5199/")
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})

            await page.goto("http://127.0.0.1:5198/")
            await page.get_by_role("textbox", name="Student ID or Username").fill("student")
            await page.get_by_role("textbox", name="Password").fill("x")
            await page.get_by_role("button", name="Sign In").click()
            await page.wait_for_url("**/courses")
            view = await read_async(page)
            print("=== 1. registration /courses, modal up ===")
            print(f"elements: {len(view.elements)}")
            print(render_page(view.elements))

            await page.goto("http://127.0.0.1:5199/")
            await page.get_by_role("button", name="Accept all cookies").click()
            await page.get_by_role("textbox", name="Reference No.").fill("04141234567890")
            await page.get_by_role("button", name="Check Bill").click()
            await page.wait_for_url("**/bill**")
            view = await read_async(page)
            print("\n=== 2. billing results, content channel ===")
            print(f"elements: {len(view.elements)}")
            show_content(view.content)

            context = await browser.new_context(user_agent=USER_AGENT,
                                                viewport={"width": 1280, "height": 800})
            live = await context.new_page()
            started = time.monotonic()
            await live.goto("https://www.pakrailways.gov.pk/train",
                            wait_until="domcontentloaded", timeout=45000)
            await live.wait_for_timeout(2500)
            load_ms = int((time.monotonic() - started) * 1000)
            view = await read_async(live)
            print("\n=== 3. live pakrailways.gov.pk/train, loaded once, untouched ===")
            print(f"title: {await live.title()!r}; load {load_ms}ms; elements: {len(view.elements)}")
            print(render_page(view.elements))
            show_content(view.content)
            await browser.close()
    finally:
        reg.terminate()
        bill.terminate()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    asyncio.run(main())
