"""The level adapting live: billing, through the Electron host, hesitating once.

Start the stack first, from the repo root:

    .\\run.ps1 billing          # both replicas, the host, the backend

then:

    python -m tools.evaluation.adaptation_stack_run          # pointer wandering
    python -m tools.evaluation.adaptation_stack_run still    # pointer at rest

This drives the overlay page inside the host, as a person would: types the
bill goal, and on the first step **does nothing useful** — the pointer drifts
back and forth over the step without pressing anything — until the screen
folds, or 30 seconds pass. Then it answers that step and the next two
promptly, the way someone who has got their bearings would.

What it checks, from the screen: the level each step is shown at (the pressed
level dot), whether "I'm showing less for a moment" appeared while the first
step was still up, and whether the fuller notice appeared after
the two calm answers (since 2026-10-14 "I'm showing a bit more now") — on billing, whose three steps leave no step after the
second calm one, that is on the ending. Then, from `data/steps.jsonl`, every
decision the rules made in this run, and which rule fired.

The telemetry is real: the overlay's own `telemetry.ts` measures the pointer
moves this script makes and sends them, and nothing here writes a sample.
Screenshots are of the overlay page only (CLAUDE.md: never the desktop).
"""

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from tools.evaluation.conditions import banner, record
from tools.evaluation.display_fit_run import capture_view

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / ".scratch" / "screenshots" / "adapt"
STEPS = REPO / "data" / "steps.jsonl"
CDP = "http://127.0.0.1:9222"
GOAL = "What do I owe on my electricity bill?"

SIMPLER = "I'm showing less for a moment."
FULLER = "I'm showing a bit more now."
ENDED = ("I'm done", "I'm stuck, so I've stopped.", "I couldn't finish this.")
LEVELS = {"Show more": 1, "Show the usual amount": 2, "Show less": 3}

#: Give up waiting for the fold after this long. The rules' own threshold for
#: a pause is 15s, and the sample that carries it can be up to 3s late.
HESITATE_LIMIT_MS = 30_000
#: How long a calm answer takes: long enough to read, well under the 8s
#: the rules call calm.
CALM_MS = 1_800


def text_of(page: Page) -> str:
    return page.evaluate("() => document.body.innerText")


def level_on_screen(page: Page) -> int | None:
    dot = page.locator('button[aria-pressed="true"]')
    if not dot.count():
        return None
    return LEVELS.get(dot.first.get_attribute("aria-label") or "")


def go_button(page: Page):
    shell = page.locator("[data-testid=step-shell]")
    if not (shell.count() and shell.first.is_visible()):
        return None
    button = shell.first.locator("button:not([disabled])").first
    return button if button.count() else None


def hesitate(page: Page, until: str, limit_ms: int = HESITATE_LIMIT_MS,
             moving: bool = True) -> float | None:
    """Drift the pointer over the step, pressing nothing, until `until` is on
    screen. Returns how long that took in seconds, or None if it never came.

    Slow, uneven sweeps across the middle of the column: what someone reading
    and re-reading does with a mouse, and enough turning back for the overlay
    to count it. With `moving` false the pointer rests on the step and only
    the pause itself can fold it.
    """
    started = time.time()
    x, y = 420, 330
    page.mouse.move(x, y)
    sweep = 0
    while (time.time() - started) * 1000 < limit_ms:
        if moving:
            target_x = 860 if sweep % 2 == 0 else 420
            target_y = 300 + (sweep % 3) * 40
            page.mouse.move(target_x, target_y, steps=25)
            sweep += 1
        page.wait_for_timeout(900)
        if until in text_of(page):
            return round(time.time() - started, 1)
    return None


def decisions_since(ts_ms: int) -> list[dict]:
    if not STEPS.exists():
        return []
    rows = []
    for line in STEPS.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("kind") == "decision" and row.get("ts", 0) >= ts_ms:
            rows.append(row)
    return rows


def run(page: Page, overlay_url: str, moving: bool = True) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    started_ms = int(time.time() * 1000)
    started = time.time()
    shots: list[str] = []
    steps: list[dict] = []

    def shot(label: str) -> None:
        path = OUT / f"{len(shots) + 1:02d}-{label}.png"
        capture_view(page, path)
        shots.append(path.name)

    page.goto(overlay_url)
    page.wait_for_timeout(1500)
    box = page.get_by_role("textbox", name="What would you like me to do?")
    box.fill(GOAL)
    page.keyboard.press("Enter")

    fold_after_s = None
    return_seen = False
    deadline = time.time() + 180
    while time.time() < deadline:
        page.wait_for_timeout(500)
        text = text_of(page)
        if any(ending in text for ending in ENDED):
            page.wait_for_timeout(600)
            return_seen = FULLER in text_of(page)
            shot("ending")
            break
        button = go_button(page)
        if button is None:
            continue
        label = button.inner_text().strip()
        index = len(steps) + 1
        entry = {"step": index, "button": label, "level_shown": level_on_screen(page)}
        shot(f"step{index}-shown")
        if index == 1:
            fold_after_s = hesitate(page, SIMPLER, moving=moving)
            entry["folded_after_s"] = fold_after_s
            entry["level_after_hesitating"] = level_on_screen(page)
            shot("step1-folded")
        else:
            page.wait_for_timeout(CALM_MS)
        steps.append(entry)
        button = go_button(page)
        if button is not None:
            button.click()
        # An answered step keeps its screen, with its buttons disabled, until
        # the next one replaces it. Wait for that, so it is not answered twice.
        for _ in range(20):
            if go_button(page) is None:
                break
            page.wait_for_timeout(250)

    decisions = decisions_since(started_ms)
    return {
        "goal": GOAL,
        "pointer": "wandering" if moving else "still",
        "steps": steps,
        "fold_seen_mid_step": fold_after_s is not None,
        "fold_after_s": fold_after_s,
        "return_seen_on_ending": return_seen,
        "ended_with": next((e for e in ENDED if e in text_of(page)), None),
        "seconds": round(time.time() - started, 1),
        "decisions": len(decisions),
        "sent": [
            {"at": d["at"], "step": d["step_index"], "from": d["level_before"],
             "to": d["level"], "rule": d["rule"], "score": d["score"],
             "reason": d["reason"]}
            for d in decisions if d["sent"]
        ],
        "screenshots": shots,
    }


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    print(banner(), flush=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(CDP)
        pages = [p for c in browser.contexts for p in c.pages]
        overlay = next(p for p in pages if p.url.startswith("file:"))
        overlay_url = overlay.url.split("?")[0]
        # `still`: rest the pointer, so only the pause can fold the step.
        result = run(overlay, overlay_url, moving="still" not in sys.argv[1:])
        overlay.goto(overlay_url)
        browser.close()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    out = REPO / "logs" / f"adaptation_stack_run_{result['pointer']}.json"
    record(out, [result])
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
