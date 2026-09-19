"""One run through the whole stack, driven the way a person drives it.

Every other script here drives a page directly and reads what came back. This
one presses the overlay's own buttons: the goal goes into the box, "Start" is
clicked, each step is confirmed, and the closing screen is read off the screen
a person would have been looking at. That is the only way to check something
the *interface* does — the closing screen showed one train when the search
returned two, and no backend assertion could have seen it (2026-09-18b).

It drives what is already running, so start the stack first:

    .\\run.ps1 railways          # host + backend, hardcoded plan, no quota

and then, from the repo root:

    python -m tools.evaluation.host_overlay_run

`SIMBA_RAILWAYS_TO=RAWALPINDI .\\run.ps1 railways` picks a route with several
trains on it, which is the case worth watching.

Prints the closing screen's text, what the site itself is showing, and writes a
screenshot of the overlay — the overlay view only, never the desktop
(CLAUDE.md) — to `logs/host-overlay-<time>.png`.

**Live site** when the flow is railways, one read-only search. No model unless
the stack was started with `SIMBA_USE_HARDCODED_PLAN=0`.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from backend.perception.serializer import read_async
from tools.evaluation.conditions import banner, record

REPO_ROOT = Path(__file__).resolve().parents[2]
CDP = "http://127.0.0.1:9222"
GOAL_BOX = "input[aria-label='What would you like me to do?']"
START = "Start"
#: How long a live step may take before the run is called stuck.
STEP_TIMEOUT_MS = 90000
#: Endings, as the overlay writes them. Any of these means the run is over.
ENDINGS = ("Here's what I found", "That's done.", "I'm stuck", "I've stopped",
           "That didn't work")


async def overlay_page(browser):
    """The overlay view, which is the one served from the built files."""
    pages = [page for context in browser.contexts for page in context.pages]
    for page in pages:
        if page.url.startswith("file:"):
            return page
    raise SystemExit(f"no overlay view among {[p.url for p in pages]} — is the host up?")


async def press_through(page, goal: str) -> list[str]:
    """Answer every step until the run ends. Returns what was pressed."""
    pressed: list[str] = []
    if await page.locator(GOAL_BOX).count():
        await page.fill(GOAL_BOX, goal)
        await page.get_by_role("button", name=START, exact=True).click()
        pressed.append(START)
        # The home screen fades out while the first step fades in, so both
        # sets of buttons are on screen for a moment. Wait the crossfade out
        # rather than pressing whatever is on top of it.
        await page.wait_for_selector("[data-testid=step-shell]", timeout=STEP_TIMEOUT_MS)
    else:
        # A run is already under way — a previous drive that stopped part of
        # the way through. Carry on from wherever it got to.
        print("no goal box: a run is already under way, carrying on", flush=True)

    deadline = time.monotonic() + STEP_TIMEOUT_MS / 1000 * 8
    while time.monotonic() < deadline:
        # Let a crossfade finish before reading the screen, so a step on its
        # way out is not mistaken for the one to answer.
        await page.wait_for_timeout(700)
        text = await page.inner_text("body")
        if any(ending in text for ending in ENDINGS):
            return pressed
        # The step's own primary action, which is the first enabled button
        # inside the step shell. Scoped to the shell because the screen also
        # carries the trust panel's opener: an unscoped "first button on
        # screen" drive opened the panel and pressed "Hide the page" three
        # times on the way through a run, which is not what a person answering
        # a step does.
        scope = ("[data-testid=step-shell] button:not([disabled])"
                 if await page.locator("[data-testid=step-shell]").count()
                 else "button:not([disabled])")
        labels = await page.eval_on_selector_all(
            scope,
            "buttons => buttons.filter(b => b.offsetParent !== null)"
            ".map(b => b.innerText.trim()).filter(Boolean)",
        )
        # `Start` belongs to the home screen; if it is still on screen it is a
        # screen on its way out, and pressing it presses nothing.
        labels = [label for label in labels if label != START]
        if labels:
            try:
                # `.last`, because a step leaving and the step arriving both
                # hold their buttons for the length of the crossfade, and the
                # arriving one is what a person would press. Without it a
                # strict locator finds two "Open the calendar" and refuses.
                await page.get_by_role("button", name=labels[0], exact=True).last.click(
                    timeout=8000)
            except PlaywrightError as refused:
                # Mid-crossfade the element detaches under the click. Let the
                # screen settle and read it again rather than forcing it.
                print(f"  (retrying {labels[0]!r}: {type(refused).__name__})", flush=True)
                continue
            pressed.append(labels[0])
            await page.wait_for_timeout(1500)
            continue
        # Waiting on the backend: nothing to press, so let it work.
        await page.wait_for_timeout(1000)
    raise SystemExit(f"the run did not end; pressed {pressed}")


async def main() -> None:
    goal = sys.argv[1] if sys.argv[1:] else "Find the trains"
    print(banner(), flush=True)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.connect_over_cdp(CDP)
        page = await overlay_page(browser)
        started = time.monotonic()
        pressed = await press_through(page, goal)
        seconds = time.monotonic() - started

        # Let the closing crossfade finish before reading the screen.
        await page.wait_for_timeout(1200)
        screen = await page.inner_text("body")
        # What the site itself is showing, read through the host's site view
        # with the same serializer the backend used. The overlay's store is
        # not on `window` and should not be put there for a test, and this is
        # the stronger comparison anyway: every result the site returned has
        # to be on the closing screen.
        site = next(candidate for candidate in
                    [pg for context in browser.contexts for pg in context.pages]
                    if not candidate.url.startswith(("file:", "devtools:", "chrome:")))
        content = (await read_async(site)).content
        results = {label: content.values_for(label)
                   for label in ("Train No.", "Duration")}
        missing = [value for values in results.values() for value in values
                   if value not in screen]

        stamp = time.strftime("%Y%m%d-%H%M%S")
        shot = REPO_ROOT / "logs" / f"host-overlay-{stamp}.png"
        shot.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(shot))
        await browser.close()

    print("\n--- the closing screen, as read off it ---")
    print(screen)
    print("\n--- what the site is showing, read through the site view ---")
    print(json.dumps(results, indent=2, ensure_ascii=False))
    print("MISSING FROM THE SCREEN:", missing or "nothing")
    print(f"\npressed: {pressed}")
    print(f"wall clock: {seconds:.1f}s (one run, this machine — EVALUATION.md, 2026-09-17h)")
    print(f"screenshot: {shot}")

    record(REPO_ROOT / "logs" / "host_overlay_run.json",
           {"goal": goal, "pressed": pressed, "seconds": round(seconds, 1),
            "screen": screen, "on_the_site": results, "missing": missing,
            "screenshot": shot.name})


asyncio.run(main())
