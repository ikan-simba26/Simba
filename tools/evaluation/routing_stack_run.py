"""Typed goals through the real stack: Electron host, real backend, real sites.

Start the stack first, from the repo root:

    .\\run.ps1 billing          # both replicas, the host, the backend

then:

    python -m tools.evaluation.routing_stack_run

For each goal this reloads the overlay page inside the host, types the goal
into the home screen as a person would, and then does what a person would do
next: on a reply, press the choice it offers; on a step, press the go-ahead;
until the task ends or the reply is recorded. Every screen reached is captured
from the overlay page itself (CLAUDE.md: never the desktop).

The railways goal runs the live site once. That is the whole of its use here
(CLAUDE.md: repeated runs go against replicas).

Whether the model or the keywords routed each goal is read from the
provider's transcript in `logs/`, where every route call is recorded with
`purpose: route`. A goal with no such entry was routed by keywords.
"""

import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from tools.evaluation.conditions import banner, record

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / ".scratch" / "screenshots" / "stack"
CDP = "http://127.0.0.1:9222"

#: (name, what is typed, what to press if a reply comes back)
GOALS = [
    ("hello", "hello", "Check my electricity bill"),
    ("bill-in-own-words", "What do I owe on my electricity bill?", None),
    ("flight", "book a flight to Dubai", None),
    ("ambiguous", "I need to pay for my course", "The electricity bill"),
    ("trains", "Show me trains from Lahore to Karachi", None),
]

#: What only an ending says. Not "Here's what I found": a step that has found
#: something says that too, and the first version of this script stopped on
#: step 3 of the bill and called it the end.
ENDED = ("I'm done", "I'm stuck, so I've stopped.", "I couldn't finish this.")
REPLIES = {"Hello. Here's what I can help with.": "greeting",
           "I can't do that yet.": "unsupported",
           "Which of these did you mean?": "clarify"}


def route_calls_since(started: float) -> list[dict]:
    """Every `purpose: route` entry any transcript has written since then."""
    calls = []
    for path in sorted((REPO / "logs").glob("*.jsonl")):
        if path.stat().st_mtime < started:
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if entry.get("purpose") == "route" and "response" in entry:
                calls.append(entry["response"])
    return calls


def screen_text(page) -> str:
    return page.evaluate("() => document.body.innerText")


def run_one(page, name: str, goal: str, press: str | None, overlay_url: str) -> dict:
    started = time.time()
    shots: list[str] = []
    seen: list[str] = []

    def shot(label: str) -> None:
        path = OUT / f"{name}-{len(shots) + 1:02d}-{label}.png"
        page.wait_for_timeout(900)
        page.screenshot(path=str(path))
        shots.append(path.name)

    page.goto(overlay_url)
    page.wait_for_timeout(1500)
    reveal = page.get_by_role("button", name="Ask for something new")
    if reveal.count() and reveal.is_visible():
        reveal.click()
    box = page.get_by_role("textbox", name="What would you like me to do?")
    box.fill(goal)
    page.keyboard.press("Enter")
    # What the person sees while the backend decides: the reading state.
    page.wait_for_timeout(400)
    if "Let me see what you need." in screen_text(page):
        seen.append("reading")
        path = OUT / f"{name}-00-reading.png"
        page.screenshot(path=str(path))
        shots.append(path.name)

    reply = None
    deadline = time.time() + 400
    pressed_reply = False
    while time.time() < deadline:
        page.wait_for_timeout(700)
        text = screen_text(page)
        found = next((kind for sentence, kind in REPLIES.items() if sentence in text), None)
        if found and not pressed_reply:
            reply = found
            seen.append(f"reply:{found}")
            shot(f"reply-{found}")
            # Press the offered choice only if this reply offers it: the model
            # may answer differently from the keywords (it called "pay for my
            # course" unsupported, not ambiguous), and that is a result, not
            # a failure of the run.
            choice = page.get_by_role("button", name=press) if press else None
            if choice is None or not choice.count():
                break
            choice.click()
            pressed_reply = True
            continue
        if any(ending in text for ending in ENDED):
            seen.append("ended")
            shot("ended")
            break
        shell = page.locator("[data-testid=step-shell]")
        if shell.count() and shell.first.is_visible():
            go = shell.first.locator("button:not([disabled])").first
            if go.count():
                label = go.inner_text().strip()
                if not seen or seen[-1] != f"step:{label}":
                    seen.append(f"step:{label}")
                    shot("step")
                    go.click()
    return {
        "name": name,
        "typed": goal,
        "reply": reply,
        "pressed": press if pressed_reply else None,
        "path": seen,
        "ended_with": next((e for e in ENDED if e in screen_text(page)), None),
        "routed_by_model": route_calls_since(started),
        "seconds": round(time.time() - started, 1),
        "screenshots": shots,
    }


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    OUT.mkdir(parents=True, exist_ok=True)
    print(banner(), flush=True)
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(CDP)
        pages = [p for c in browser.contexts for p in c.pages]
        overlay = next(p for p in pages if p.url.startswith("file:"))
        overlay_url = overlay.url.split("?")[0]
        only = set(filter(None, os.environ.get("SIMBA_ONLY", "").split(",")))
        for name, goal, press in GOALS:
            if only and name not in only:
                continue
            result = run_one(overlay, name, goal, press, overlay_url)
            results.append(result)
            print(f"  {name:<18} typed {goal!r:<44} -> {result['path']} "
                  f"| model said {result['routed_by_model']} | {result['seconds']}s",
                  flush=True)
        overlay.goto(overlay_url)
        browser.close()
    out = REPO / "logs" / "routing_stack_run.json"
    record(out, results)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
