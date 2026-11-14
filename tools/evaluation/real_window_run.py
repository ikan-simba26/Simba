"""One goal, typed into the real SIMBA window, on the real website (2026-11-14).

"Nothing counts as done until it has been tried in the real SIMBA window on
the real website" (Raham, 2026-11-14): the headless runs passed on the night
the window did not. This drives the window itself — the Electron host and the
backend `run.ps1` started — the way `routing_stack_run` does: it attaches to
the host over CDP, types into the overlay as a person would, and presses what
a person would press. Pictures are of the SIMBA window's own view, never the
desktop (CLAUDE.md).

    .\\run.ps1 billing
    backend/venv/Scripts/python -m tools.evaluation.real_window_run \\
        --site https://www.readings.com.pk "Find the price of Atomic Habits" --name price

What it presses, playing the person:

  * the read-back and every ordinary step: the first button (go ahead);
  * **a final screen: "Don't do it"**, and **a handover: stop**. A real order,
    booking, payment or account is a person's own press, never a script's
    (CLAUDE.md, the final-step rule). One exception, asked for with
    `--open-form`: a final screen met *before anything has been typed in this
    run* is answered "Do it". Raham kept the final screen for a press that
    only opens a form (DECISIONS.md, 2026-11-15) — "Register" at the top of
    Readings — and with nothing typed there is nothing such a press could
    send. Once a box has been filled, or a password made, every final screen
    is "Don't do it" again, whatever is asked for;
  * "Make a strong password for me", when it is offered and `--make-password`
    is given: SIMBA makes it and types it; this script never sees it;
  * a box only the person can fill: `--type label=value` gives the value for a
    box whose label contains `label`; with none, the run stops there and says
    which box it was. Nothing personal is ever made up here.

Writes what happened to `.scratch/real-window/<name>.json` and prints one
line. One run per call: a live site gets a handful, not a loop.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from tools.evaluation.conditions import banner, record

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / ".scratch" / "real-window"
CDP = "http://127.0.0.1:9222"



def capture_view(page, path: Path) -> None:
    """The SIMBA window's own view, as it is shown, and nothing else: through
    `browser.capture_site` on a connection of its own, as `display_fit_run`
    does (that module's helper is tied to its own host's port)."""
    import asyncio
    import concurrent.futures

    url = page.url

    async def shoot() -> bytes:
        from playwright.async_api import async_playwright

        from backend.orchestrator.browser import capture_site

        async with async_playwright() as playwright:
            browser = await playwright.chromium.connect_over_cdp(CDP)
            try:
                view = next(p for c in browser.contexts for p in c.pages if p.url == url)
                return await capture_site(view)
            finally:
                await browser.close()  # detaches; the host is the caller's to stop

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        path.write_bytes(pool.submit(lambda: asyncio.run(shoot())).result(timeout=40))


def restore_window() -> str:
    """Put the SIMBA window back if it has been minimised, without taking the
    keyboard: the host this stack started, found by the port it listens on,
    and no other window. SIMBA waits rather than act on a minimised window
    (`loop._Run.ready`), so a run cannot go on while it is put away. Returns
    "minimised" if it was, "shown" if not."""
    import subprocess

    script = (
        "$o = (Get-NetTCPConnection -State Listen -LocalPort 9222 -ErrorAction SilentlyContinue"
        " | Select-Object -First 1).OwningProcess; if (-not $o) { 'no host'; exit }; "
        "$p = Get-Process -Id $o; "
        "Add-Type -Namespace SimbaWin -Name U -MemberDefinition "
        "'[DllImport(\"user32.dll\")] public static extern bool ShowWindow(IntPtr h, int n); "
        "[DllImport(\"user32.dll\")] public static extern bool IsIconic(IntPtr h);'; "
        "if ([SimbaWin.U]::IsIconic($p.MainWindowHandle)) "
        "{ [void][SimbaWin.U]::ShowWindow($p.MainWindowHandle, 4); 'minimised' } else { 'shown' }")
    out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                         capture_output=True, text=True, timeout=30, check=False).stdout.strip()
    return out or "unknown"


#: How often one run puts the window back before it gives up: someone is
#: putting it away on purpose, and the run is theirs to allow.
MOST_RESTORES = 3

ENDED = ("Back to start", "I'm stuck, so I've stopped.", "I couldn't finish this.")
REPLIES = ("Hello. Here's what I can help with.", "I can't do that yet.",
           "Which of these did you mean?")


def screen_text(page) -> str:
    return page.evaluate("() => document.body.innerText")


def backend_log_since(started: float) -> list[str]:
    """The run's own lines in logs/backend.log: times, never what was typed."""
    lines = []
    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(started))
    path = REPO / "logs" / "backend.log"
    if not path.exists():
        return lines
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line[:19] >= stamp and ("simba.run" in line or "simba.app" in line):
            lines.append(line)
    return lines


def chosen_times(lines: list[str]) -> list[float]:
    """Seconds each move took to choose, from the backend's log."""
    out = []
    for line in lines:
        if "next move chosen in " in line:
            out.append(float(line.rsplit("next move chosen in ", 1)[1].rstrip("s")))
    return out


def run_one(page, overlay_url: str, goal: str, site: str | None, name: str,
            typed: dict[str, str], until_final: bool, limit_s: float,
            press_text: str | None, press_through: bool = False,
            open_form: bool = False, make_password: bool = False) -> dict:
    started = time.time()
    shots: list[str] = []
    path_seen: list[str] = []
    asked = 0          # screens that waited for the person
    lines_seen: list[str] = []   # checklist lines, moves SIMBA did by itself
    outcome = "timeout"
    stopped_at = None
    typed_any: list[str] = []   # boxes this run filled: after one, never "Do it"
    saw_live: list[bool] = []

    def shot(label: str) -> None:
        file = OUT / f"{name}-{len(shots) + 1:02d}-{label}.png"
        page.wait_for_timeout(700)
        try:
            capture_view(page, file)
            shots.append(file.name)
        except Exception as error:  # noqa: BLE001 - a picture is optional
            shots.append(f"(no picture: {type(error).__name__})")

    restores = 0
    if restore_window() == "minimised":
        restores += 1
    page.goto(overlay_url)
    page.wait_for_timeout(2000)
    for skip in ("Skip this", "No, thank you"):
        button = page.get_by_role("button", name=skip)
        if button.count() and button.first.is_visible():
            button.first.click()
            page.wait_for_timeout(600)
    shot("home")
    # The first screen: "Where do you want to go?" (2026-11-14). The website's
    # card when it is listed, "Another website" and its address when not.
    if site:
        from urllib.parse import urlsplit

        host = (urlsplit(site).netloc or site).removeprefix("www.")
        card = page.locator(f'[data-testid=site][title="{host}"]')
        if card.count():
            card.first.click()
        else:
            page.locator("[data-testid=another-site]").click()
            page.locator("[data-testid=ask-where]").fill(site)
        page.wait_for_timeout(800)
        shot("there")
    # The second: "What do you want to do there?" — a suggestion, or the box.
    if press_text:
        page.get_by_text(press_text, exact=False).first.click()
        page.wait_for_timeout(400)
    if goal:
        box = page.locator("[data-testid=ask-there]" if site else "[data-testid=ask-goal]")
        if press_text and "…" in box.first.input_value():
            # A suggestion with a gap: the gap is selected; type over it.
            page.keyboard.type(goal)
        else:
            box.first.fill(goal)
        page.keyboard.press("Enter")

    last_step = None
    deadline = time.time() + limit_s
    idle_since = time.time()
    while time.time() < deadline:
        page.wait_for_timeout(500)
        text = screen_text(page)
        # Nothing new for a while: the window may have been put away, and
        # SIMBA is waiting to act. Looked at every 20 seconds, not every turn.
        if time.time() - idle_since > 20:
            idle_since = time.time()
            if restore_window() == "minimised":
                restores += 1
                path_seen.append("window put away; restored")
                if restores > MOST_RESTORES:
                    outcome = "window kept being put away"
                    break
        if any(reply in text for reply in REPLIES) and not path_seen:
            outcome = "reply"
            shot("reply")
            break
        # Lines of the checklist: what SIMBA is doing by itself.
        for row in page.locator("[data-testid=checklist-lines] li").all():
            label = row.inner_text().strip().split("\n")[-1]
            if label and label not in lines_seen:
                lines_seen.append(label)
                path_seen.append(f"did:{label}")
        live = page.locator("[data-testid=live-page] img")
        if live.count() and not saw_live:
            saw_live.append(True)
            shot("working")
        if any(ending in text for ending in ENDED):
            outcome = ("stopped" if "stopped, as you asked" in text or "Nothing was changed" in text
                       else "completed" if "Back to start" in text and "stuck" not in text.lower()
                       and "couldn't" not in text.lower() and "stopped" not in text.lower()
                       else "stuck")
            if outcome == "stopped" and any(p.startswith("final:") for p in path_seen):
                outcome = "final screen, declined"
            shot("ended")
            break
        if page.locator("[data-testid=handover-bar]").count():
            path_seen.append("handover")
            outcome = "handover"
            shot("handover")
            stop = page.locator("[data-testid=handover-stop]")
            if stop.count():
                stop.first.click()
            break
        shell = page.locator("[data-testid=step-shell], [data-testid=final-check]")
        if not (shell.count() and shell.first.is_visible()):
            last_step = None  # between steps: the next may say the same words
            continue
        heading = shell.first.locator("h1, h2").first
        said = heading.inner_text().strip() if heading.count() else ""
        if said == last_step:
            continue
        if "I waited while the window was" in said:
            # Put away while SIMBA worked: back, without the keyboard, and on.
            restores += 1
            path_seen.append("window put away; restored")
            if restores > MOST_RESTORES:
                outcome = "window kept being put away"
                break
            restore_window()
        final = page.locator("[data-testid=final-check]").count() > 0
        buttons = shell.first.locator("button:not([disabled]):not([data-testid=speak])")
        if not buttons.count():
            continue
        last_step = said
        asked += 1
        path_seen.append(("final:" if final else "asked:") + said)
        shot("final" if final else "step")
        if final and open_form and not typed_any:
            # Nothing typed yet: this press can only open a form.
            path_seen[-1] = "final, opened:" + said
            shell.first.get_by_role("button", name="Do it").first.click()
            page.wait_for_timeout(600)
            continue
        if final:
            # Never "Do it" otherwise: a real change is a person's own press.
            outcome = "final screen"
            dont = shell.first.get_by_role("button", name="Don't")
            (dont.first if dont.count() else buttons.nth(1)).click()
            page.wait_for_timeout(1500)
            shot("declined")
            break
        made = shell.first.get_by_role("button", name="Make a strong password for me")
        if make_password and made.count():
            typed_any.append("password")
            path_seen[-1] += " [made a password]"
            made.first.click()
            page.wait_for_timeout(600)
            continue
        # A box only the person can fill.
        boxes = shell.first.locator("input:visible:not([type=checkbox])")
        blocked = None
        for index in range(boxes.count()):
            box = boxes.nth(index)
            if box.input_value():
                continue
            label = (box.get_attribute("aria-label") or box.get_attribute("placeholder")
                     or box.get_attribute("name") or "").strip()
            asked_for = f"{label} {said}".lower()
            value = next((v for k, v in typed.items() if k.lower() in asked_for), None)
            if value is None and press_through:
                continue
            if value is None:
                blocked = label or said or "a box with no name"
                break
            box.fill(value)
            typed_any.append(label or said)
        if blocked is not None:
            outcome = "needs the person"
            stopped_at = blocked
            stop = shell.first.get_by_role("button", name="Stop this")
            if stop.count():
                stop.first.click()
            break
        buttons.first.click()

    log_lines = backend_log_since(started)
    times = chosen_times(log_lines)
    return {
        "name": name, "site": site, "goal": goal,
        "outcome": outcome,
        "stopped_at": stopped_at,
        "asked": asked,
        "boxes_filled": len(typed_any),
        "window_restored": restores,
        "did_by_itself": len(lines_seen),
        "live_page_shown": bool(saw_live),
        "path": path_seen,
        "ending_text": screen_text(page)[:600],
        "seconds": round(time.time() - started, 1),
        "choose_seconds": times,
        "slowest_choice": max(times) if times else None,
        "screenshots": shots,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("goal", nargs="?", default="")
    parser.add_argument("--site")
    parser.add_argument("--name", default="run")
    parser.add_argument("--type", action="append", default=[],
                        help="label=value for a box only the person can fill")
    parser.add_argument("--press", help="start by pressing this text on the home screen")
    parser.add_argument("--until-final", action="store_true")
    parser.add_argument("--open-form", action="store_true",
                        help='"Do it" on a final screen met before anything is typed')
    parser.add_argument("--make-password", action="store_true")
    parser.add_argument("--press-through", action="store_true",
                        help="press go-ahead past an empty box (how the planner asked "
                             "before 2026-11-14: its own value was never shown in the box)")
    parser.add_argument("--limit", type=float, default=420)
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    OUT.mkdir(parents=True, exist_ok=True)
    typed = dict(item.split("=", 1) for item in args.type)
    print(banner(), flush=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(CDP)
        pages = [p for c in browser.contexts for p in c.pages]
        overlay = next(p for p in pages if p.url.startswith("file:"))
        overlay_url = overlay.url.split("?")[0]
        result = run_one(overlay, overlay_url, args.goal, args.site, args.name, typed,
                         args.until_final, args.limit, args.press, args.press_through,
                         args.open_form, args.make_password)
        browser.close()
    record(OUT / f"{args.name}.json", result)
    print(json.dumps({k: v for k, v in result.items() if k not in ("ending_text",)},
                     indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
