"""Play the person in the real SIMBA window, one move per call (2026-11-17).

The stack is started by `.\\run.ps1`. This attaches to its window over CDP,
does one thing a person would do, waits for the screen to settle and prints
what the person would now see: the screen's words, its buttons, and its boxes
(by label, never by what is in them). Pictures are of the SIMBA overlay view
only, saved under `.scratch/real-window/`, never the desktop (CLAUDE.md).

    python -m tools.evaluation.drive look
    python -m tools.evaluation.drive goal "Book a bus ticket ..." --site daewoo.com.pk
    python -m tools.evaluation.drive press "Yes"
    python -m tools.evaluation.drive type "Name=Some Person"
    python -m tools.evaluation.drive shot name

It never presses a final button for the person's real change: that is the
person's own press (the task's rule). `press` refuses a button whose words
are "Do it" or "Pay now" unless `--allow-final` is given, which only the
person asks for.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / ".scratch" / "real-window"
CDP = "http://127.0.0.1:9222"
FINAL_WORDS = ("do it", "pay now", "book it", "yes, order", "yes, book")


def overlay_page(browser):
    pages = [p for c in browser.contexts for p in c.pages]
    return next(p for p in pages if p.url.startswith("file:") or ":5173" in p.url)


def look(page, wait_ms: int = 800) -> str:
    page.wait_for_timeout(wait_ms)
    text = page.evaluate("() => document.body.innerText")
    buttons = page.evaluate(
        "() => [...document.querySelectorAll('button')].filter(b => b.offsetParent !== null)"
        ".map(b => (b.disabled ? '(off) ' : '') + b.innerText.trim().replace(/\\s+/g, ' '))"
        ".filter(Boolean)")
    boxes = page.evaluate(
        "() => [...document.querySelectorAll('input,textarea,select')]"
        ".filter(i => i.offsetParent !== null).map(i => (i.getAttribute('aria-label') || "
        "i.placeholder || i.name || i.type) + ' [' + i.type + (i.value ? ', filled' : ', empty') + ']')")
    return (f"--- screen ---\n{text.strip()[:1800]}\n--- buttons ---\n"
            + "\n".join(f"  [{n}] {b}" for n, b in enumerate(buttons))
            + "\n--- boxes ---\n" + "\n".join(f"  {b}" for b in boxes))


def settle(page, seconds: float) -> None:
    """Wait until the screen's text stops changing for 3 seconds, or `seconds`."""
    end = time.time() + seconds
    last, since = None, time.time()
    while time.time() < end:
        page.wait_for_timeout(500)
        now = page.evaluate("() => document.body.innerText")
        if now != last:
            last, since = now, time.time()
        elif time.time() - since > 3:
            return


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["look", "goal", "press", "type", "shot", "home", "key"])
    parser.add_argument("arg", nargs="?", default="")
    parser.add_argument("--site", help="the website's address, to choose its card first")
    parser.add_argument("--wait", type=float, default=25)
    parser.add_argument("--allow-final", action="store_true")
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(CDP)
        page = overlay_page(browser)
        if args.action == "home":
            page.goto(page.url.split("?")[0] + ("?" + page.url.split("?")[1] if "?" in page.url else ""))
            page.wait_for_timeout(2500)
            for skip in ("Skip this", "No, thank you"):
                b = page.get_by_role("button", name=skip)
                if b.count() and b.first.is_visible():
                    b.first.click()
                    page.wait_for_timeout(600)
        elif args.action == "goal":
            if args.site:
                from urllib.parse import urlsplit
                host = (urlsplit(args.site).netloc or args.site).removeprefix("www.")
                card = page.locator(f'[data-testid=site][title="{host}"]')
                if card.count():
                    page.wait_for_timeout(1200)
                    card.first.scroll_into_view_if_needed()
                    page.wait_for_timeout(900)
                    card.first.click()
                    page.wait_for_timeout(800)
                    if not page.locator("[data-testid=home-there]").count():
                        card.first.click()
                else:
                    page.locator("[data-testid=ask-goal]").fill(args.site)
                    page.locator("[data-testid=home-go]").click()
                page.wait_for_timeout(800)
            box = page.locator("[data-testid=ask-there]" if args.site else "[data-testid=ask-goal]")
            box.first.fill(args.arg)
            page.keyboard.press("Enter")
        elif args.action == "press":
            if args.arg.lower().startswith(FINAL_WORDS) and not args.allow_final:
                print("REFUSED: that is the person's own press.")
                browser.close()
                return
            if args.arg.isdigit():
                visible = page.locator("button:visible")
                visible.nth(int(args.arg)).click()
            else:
                page.get_by_role("button", name=args.arg).first.click()
        elif args.action == "type":
            label, value = args.arg.split("=", 1)
            box = page.locator(f'input:visible[aria-label*="{label}" i], input:visible[placeholder*="{label}" i], '
                               f'input:visible[name*="{label}" i]')
            if not box.count():
                box = page.locator("input:visible:not([type=checkbox])")
            box.first.fill(value)
        elif args.action == "key":
            page.keyboard.press(args.arg)
        if args.action == "shot":
            file = OUT / f"{args.arg or 'view'}.png"
            page.screenshot(path=str(file))
            print(f"picture: {file}")
        if args.action in ("goal", "press", "key"):
            settle(page, args.wait)
        print(look(page))
        browser.close()


if __name__ == "__main__":
    main()
