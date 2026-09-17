"""One LLM-planned railways run through the real Electron host, watchable.

Unlike `railways_llm_run`, nothing here stands in for the interface: the task
is typed into the real overlay, every step is shown in the real window, and
"Yes, do that" is pressed in that window — by this script, over CDP, after a
pause long enough for someone watching to read the step. The backend drives
the covered site view exactly as it does for a person.

Needs the stack up first, with the LLM planner:

    $env:SIMBA_USE_HARDCODED_PLAN = "0"; .\\run.ps1 railways

then, from the repo root:

    python -m tools.evaluation.railways_llm_stack_run

**Live site and model quota**: one run is 6-8 requests and one read-only
search. What the overlay received is taken from its own WebSocket; what the
site sent is taken from the site view's network. The model transcript is the
backend's, in `logs/llm-<timestamp>.jsonl`.

Written 2026-09-17 for EVALUATION.md 2026-09-17f.
"""

import asyncio
import json
import sys
import time

from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.orchestrator.railways_plan import RAILWAYS_TASK  # noqa: E402

CDP = "http://127.0.0.1:9222"
READ_PAUSE_S = 2.5  # long enough to read a step before it is answered
ENDINGS = (
    "That's done.",
    "Here's what I found",
    "I couldn't finish this.",
    "I'm stuck, so I've stopped.",
    "I've stopped, as you asked.",
)


async def main() -> None:
    received: list[dict] = []
    searches: list[str] = []
    started = time.monotonic()

    async with async_playwright() as playwright:
        browser = await playwright.chromium.connect_over_cdp(CDP)
        pages = [page for context in browser.contexts for page in context.pages]
        overlay = next(p for p in pages if p.url.startswith("file:") and "index.html" in p.url)
        site = next(p for p in pages if "pakrailways" in p.url)

        def on_socket(ws):
            ws.on("framereceived", lambda frame: received.append(json.loads(frame)))

        overlay.on("websocket", on_socket)
        site.on("request", lambda r: searches.append(r.post_data or "")
                if "trainInfoList" in r.url else None)

        await overlay.reload()
        await overlay.wait_for_timeout(1500)
        box = overlay.locator("input[aria-label='What would you like me to do?']")
        await box.fill(RAILWAYS_TASK.goal)
        await overlay.wait_for_timeout(1200)
        await overlay.get_by_role("button", name="Start").click()
        print("goal:", RAILWAYS_TASK.goal, flush=True)

        answered = 0
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            text = await overlay.inner_text("body")
            ending = next((e for e in ENDINGS if e in text), None)
            if ending:
                print("ending on screen:", ending, flush=True)
                break
            steps = [m for m in received if m["type"] == "step.presented"]
            if len(steps) > answered:
                go = overlay.get_by_role("button", name="Yes, do that", exact=True)
                try:
                    await go.wait_for(state="visible", timeout=5000)
                except Exception:  # noqa: BLE001
                    await overlay.wait_for_timeout(300)
                    continue
                step = steps[-1]["payload"]
                print(f"step {step['step_index']}: {step['instruction']}  "
                      f"| {step['detail']}", flush=True)
                await overlay.wait_for_timeout(READ_PAUSE_S * 1000)
                await go.click()
                answered = len(steps)
            await overlay.wait_for_timeout(400)

        await overlay.wait_for_timeout(1500)
        final = {}
        for name in ("From", "To", "Departure Date"):
            try:
                final[name] = await site.get_by_role("textbox", name=name, exact=True).input_value()
            except Exception as error:  # noqa: BLE001
                final[name] = f"<{type(error).__name__}>"
        screen = await overlay.inner_text("body")
        await browser.close()  # detaches; the host keeps running

    print("\nmessages the overlay received:")
    for message in received:
        payload = message["payload"]
        if message["type"] == "state.changed":
            continue
        if message["type"] == "step.presented":
            payload = {k: payload[k] for k in ("step_index", "instruction", "findings")}
        print(f"  {message['seq']:3} {message['type']}: {json.dumps(payload)[:400]}")
    print("\nfinal form:", final)
    print("search requests:", searches)
    print("screen:", " / ".join(line for line in screen.splitlines() if line.strip())[:400])
    print(f"wall clock (Start to ending): {time.monotonic() - started:.1f}s")


asyncio.run(main())
