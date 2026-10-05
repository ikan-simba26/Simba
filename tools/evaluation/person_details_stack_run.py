"""One run on the person's own details, through the real Electron host.

Like `railways_llm_stack_run`, nothing here stands in for the interface: the
goal is typed into the real overlay, every step and every question is shown in
the real window, and the answers are pressed in that window over CDP after a
pause long enough for someone watching to read them.

Unlike it, this one can answer a *question*. Since 2026-09-30 a step is not
always something to agree to: where a goal left out something the task needs,
the backend asks, with a box to type in or a few buttons to press. So this
presses the primary button on an ordinary step, fills the box on a typed
question, and picks a named answer on a question that offers several.

Needs the stack up first. The hardcoded planner spends no quota:

    .\\run.ps1 railways-local    # our own copy of the train search: rehearse here
    .\\run.ps1 railways          # the live site: a handful of runs, not a benchmark

then, from the repo root:

    python -m tools.evaluation.person_details_stack_run "trains to Rawalpindi tomorrow" \\
        --type Lahore --pick "Lahore Cantt"

`--type` answers each typed question in turn; `--pick` names the answer to
press on each question that offers several, matched loosely and falling back to
the first one offered. `--goal` may also be given positionally, as above.

**Live site**: the search is read-only, and one run sends one search. On the
local copy nothing leaves the machine, and what it searched is read from its
own record (`window.__searched`) rather than from the network. What the
overlay received is taken from its own WebSocket; what the site was asked is
taken from the site view's own network; what came back is read off the site
view afterwards, so "trains came back for that route" is asserted against the
real page and not against the overlay's summary.

Written 2026-09-30 for EVALUATION.md.
"""

import argparse
import asyncio
import json
import sys
import time

from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tools.evaluation.conditions import banner  # noqa: E402

CDP = "http://127.0.0.1:9222"
READ_PAUSE_S = 2.5
ENDINGS = (
    "That's done.",
    "Here's what I found",
    "I couldn't finish this.",
    "I'm stuck, so I've stopped.",
    "I've stopped, as you asked.",
    # The closing screen with a sentence has no lead-in (2026-10-05).
    "I'm done",
)
STOP_ID = "cancel"
CHOICE_PREFIX = "choice:"


def answer_for(step: dict, typed: list[str], picks: list[str]) -> tuple[str, dict]:
    """Which button to press on this step, and what to put in its box first.

    Three shapes, in the order they are told apart:

      * a box to fill — a typed question, answered with the next `--type` and
        the step's own primary button ("That's it");
      * several answers of its own — pressed by the next `--pick`, matched
        loosely, or the first one offered;
      * anything else — an ordinary step, agreed to with its primary button.
    """
    actions = step["actions"]
    primary = next((a["label"] for a in actions if a["kind"] == "primary"), "Yes, do that")

    if step["fields"]:
        values = {}
        for field in step["fields"]:
            values[field["label"]] = typed.pop(0) if typed else ""
        return primary, values

    answers = [a for a in actions if a["id"].startswith(CHOICE_PREFIX)]
    if len(answers) > 1:
        wanted = picks.pop(0) if picks else ""
        chosen = next(
            (a["label"] for a in answers if wanted.casefold() in a["label"].casefold()),
            answers[0]["label"],
        )
        return chosen, {}

    return primary, {}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("goal", nargs="?", default="trains to Rawalpindi tomorrow")
    parser.add_argument("--type", dest="typed", action="append", default=[])
    parser.add_argument("--pick", dest="picks", action="append", default=[])
    parser.add_argument("--pause", type=float, default=READ_PAUSE_S)
    args = parser.parse_args()
    typed, picks = list(args.typed), list(args.picks)

    print(banner(), flush=True)
    received: list[dict] = []
    sent: list[dict] = []
    searches: list[str] = []
    started = time.monotonic()

    async with async_playwright() as playwright:
        browser = await playwright.chromium.connect_over_cdp(CDP)
        pages = [page for context in browser.contexts for page in context.pages]
        overlay = next(p for p in pages if p.url.startswith("file:") and "index.html" in p.url)
        # The site view: the live train search, or the local copy that
        # `run.ps1 railways-local` opens on. Anything but the overlay.
        site = next(p for p in pages if p.url.startswith("http"))

        def on_socket(ws):
            ws.on("framereceived", lambda frame: received.append(json.loads(frame)))
            ws.on("framesent", lambda frame: sent.append(json.loads(frame)))

        overlay.on("websocket", on_socket)
        site.on("request", lambda r: searches.append(r.url + " " + (r.post_data or ""))
                if "trainInfoList" in r.url else None)

        await overlay.reload()
        await overlay.wait_for_timeout(1500)
        box = overlay.locator("input[aria-label='What would you like me to do?']")
        await box.fill(args.goal)
        await overlay.wait_for_timeout(1000)
        await overlay.get_by_role("button", name="Start").click()
        print("goal:", args.goal, flush=True)

        answered = 0
        #: The answer worked out for the step now on screen, or None.
        decided: tuple[str, dict] | None = None
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            text = await overlay.inner_text("body")
            ending = next((e for e in ENDINGS if e in text), None)
            if ending:
                print("ending on screen:", ending, flush=True)
                break
            steps = [m for m in received if m["type"] == "step.presented"]
            if len(steps) > answered:
                step = steps[-1]["payload"]
                # Worked out once per step, not once per look. Deciding it
                # again while waiting for the button to appear took another
                # answer off the front of the list each time, so every run
                # before this fix pressed the first station whatever `--pick`
                # said.
                if decided is None:
                    decided = answer_for(step, typed, picks)
                label, values = decided
                press = overlay.get_by_role("button", name=label, exact=True)
                try:
                    await press.wait_for(state="visible", timeout=5000)
                except Exception:  # noqa: BLE001
                    await overlay.wait_for_timeout(300)
                    continue
                kind = "question" if step["fields"] or any(
                    a["id"].startswith(CHOICE_PREFIX) for a in step["actions"]) else "step"
                offered = [a["label"] for a in step["actions"]]
                print(f"{kind} {step['step_index']}/{step['step_total']}: "
                      f"{step['instruction']}  | {step['detail']}", flush=True)
                if kind == "question":
                    print(f"        offered={offered}"
                          f"  boxes={[f['label'] for f in step['fields']]}", flush=True)
                print(f"        -> [{label}] {values or ''}", flush=True)
                # Fill the box, if this is a question with one, in the real
                # window: the person types into the overlay, not into the site.
                for field_label, value in values.items():
                    await overlay.fill(f"input[aria-label='{field_label}']", value)
                await overlay.wait_for_timeout(args.pause * 1000)
                await press.click()
                answered = len(steps)
                decided = None
            await overlay.wait_for_timeout(400)

        await overlay.wait_for_timeout(2000)
        final = {}
        for name in ("From", "To", "Departure Date"):
            try:
                final[name] = await site.get_by_role(
                    "textbox", name=name, exact=True).input_value()
            except Exception as error:  # noqa: BLE001
                final[name] = f"<{type(error).__name__}>"
        # What the live site actually put on the page, read off the site view.
        # The local copy records what it searched in its own state; the live
        # site's search is the network request above.
        searched_locally = await site.evaluate("window.__searched ?? null")
        rows = await site.evaluate(
            """() => Array.from(document.querySelectorAll('table tr'))
                     .map(r => Array.from(r.cells).map(c => c.innerText.trim()).join(' | '))
                     .filter(t => t)""")
        screen = await overlay.inner_text("body")
        site_url = site.url
        await browser.close()  # detaches; the host keeps running

    print("\nmessages the overlay received:")
    for message in received:
        payload = message["payload"]
        if message["type"] == "state.changed":
            continue
        if message["type"] == "step.presented":
            payload = {k: payload[k] for k in ("step_index", "step_total", "instruction",
                                               "findings")}
            payload["actions"] = [a["id"] for a in message["payload"]["actions"]]
        print(f"  {message['seq']:3} {message['type']}: {json.dumps(payload)[:400]}")
    print("\nwhat the overlay sent back:")
    for message in sent:
        if message["type"] == "step.response":
            print(f"  {message['type']}: {json.dumps(message['payload'])}")
    print("\nfinal form:", final)
    print("site view:", site_url)
    print("search requests:", searches or "none")
    if searched_locally is not None:
        print("searched (the local copy's own record):", searched_locally)
    print("rows on the site view:")
    for row in rows[:12]:
        print("   ", row)
    print("screen:", " / ".join(line for line in screen.splitlines() if line.strip())[:500])
    print(f"wall clock (Start to ending): {time.monotonic() - started:.1f}s")


asyncio.run(main())
