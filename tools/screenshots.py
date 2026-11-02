"""Every screen of the overlay, captured in both themes, for comparing designs.

The overlay is built from the source as it is checked out, served locally, and
driven by a scripted fake backend into each screen in turn. Each screen is
captured from the overlay page itself at the frozen 1280x800 — the
application's own renderer, never the desktop (CLAUDE.md, "Tooling
boundaries").

    python -m tools.screenshots before     # writes .scratch/screenshots/before/
    python -m tools.screenshots after      # writes .scratch/screenshots/after/

Themes are the operating system's preference, emulated: `light` and `dark`.
An overlay with one theme renders the same picture twice, which is itself the
thing a before/after comparison should show.
"""

import asyncio
import base64
import functools
import http.server
import json
import os
import shutil
import socketserver
import subprocess
import sys
import threading
from pathlib import Path

import websockets
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[1]
FRONTEND = REPO / "frontend"
GOAL = "Find out what I owe"

HOLD = ("hold", {})               # stop here and keep the socket open
STEP_RESPONSE = ("await", {"type": "step.response"})
TRUST = ("await", {"type": "trust.requested"})


def step(index: int, total: int, instruction: str, detail: str = "", fields=(),
         go: str = "Check the bill", findings=()) -> dict:
    return {
        "step_index": index, "step_total": total, "instruction": instruction,
        "detail": detail, "fields": list(fields), "requires_confirmation": True,
        "findings": list(findings),
        "actions": [
            {"id": "confirm", "label": go, "kind": "primary"},
            {"id": "cancel", "label": "Stop this", "kind": "secondary"},
        ],
    }


REFERENCE_FIELD = {"id": "reference", "label": "Reference No.", "type": "text",
                   "value": "04141234567890"}
# The answers as the sites print them, taken from the mock, which takes them
# from the replica. Retyped here once, as "15 October 2026", and the design
# comparison then showed a due date the page has never said.
from tools.mock_backend import BILL_AMOUNT, BILL_DUE, JOURNEY, TRAIN  # noqa: E402

BILL = [{"label": "Your bill", "value": BILL_AMOUNT, "values": [BILL_AMOUNT]},
        {"label": "Due", "value": BILL_DUE, "values": [BILL_DUE]}]
# Several results, to show how the closing screen lists them: the live
# answer and a second train in the same format.
TRAINS = [{"label": "Train", "value": f"{TRAIN}, 14DN", "values": [TRAIN, "14DN"]},
          {"label": "Journey", "value": f"{JOURNEY}, 20 h 5 min",
           "values": [JOURNEY, "20 h 5 min"]}]

STARTED = [("task.started", {"goal": GOAL, "estimated_steps": 3}),
           ("state.changed", {"state": "thinking"})]
LOOKUP = step(2, 3, "Let me look up your bill.",
              "Using the 14-digit reference number from your bill.", [REFERENCE_FIELD])


def level(n: int) -> tuple:
    return ("load.updated", {"score": 0.5, "level": n, "reason": "scripted"})


def at(*messages) -> list:
    return [*STARTED, *messages, ("state.changed", {"state": "waiting"})]


def completed(findings) -> tuple:
    return ("task.completed", {"summary": GOAL, "duration_ms": 1, "steps_taken": 3,
                               "llm_calls": 0, "replayed": False, "findings": findings})


#: (name, how to start, what the backend plays, what to do before capturing).
#: `start` is "home" (capture as it opens), "goal" (type the goal and press
#: Start), or ("goal", text).
SCREENS: list[tuple[str, object, list, list[str]]] = [
    ("01-home-first-visit", "home", [], []),
    ("02-home-with-history", "home-history", [], []),
    ("03-home-asking", "home-history", [], ["reveal"]),
    ("04-working", "goal", [*STARTED, HOLD], []),
    ("05-step-level-1", "goal", [*at(level(1), ("step.presented", LOOKUP)), HOLD], []),
    ("06-step-level-2", "goal", [*at(("step.presented", LOOKUP)), HOLD], []),
    ("07-step-level-3", "goal", [*at(level(3), ("step.presented", LOOKUP)), HOLD], []),
    ("08-step-with-answer", "goal",
     [*at(("step.presented", step(3, 3, "Now I'll open the full bill.",
                                  "This shows what makes up the amount due.",
                                  go="Show me the breakdown", findings=BILL))), HOLD], []),
    ("09-step-after-a-setback", "goal",
     [*STARTED, ("step.failed", {"step_index": 1, "instruction": "Accept cookies",
                                 "reason": "click failed", "strategies_tried": 2}),
      ("state.changed", {"state": "waiting"}), ("step.presented", LOOKUP), HOLD], []),
    ("10-acting", "goal",
     [*at(("step.presented", LOOKUP)), STEP_RESPONSE,
      ("state.changed", {"state": "acting"}), HOLD], ["go"]),
    ("11-trust-panel", "goal",
     [*at(("step.presented", LOOKUP)), TRUST, ("page.preview", "PREVIEW"), HOLD],
     ["trust"]),
    ("12-done-with-answer", "goal", [*STARTED, completed(BILL)], []),
    ("13-done-with-several-results", "goal", [*STARTED, completed(TRAINS)], []),
    ("14-done-without-answer", "goal", [*STARTED, completed([])], []),
    ("15-failed", "goal",
     [*STARTED, ("task.failed", {"reason": "The portal timed out.", "recoverable": True})], []),
    ("16-stuck", "goal",
     [*STARTED, ("state.changed", {"state": "stuck"}),
      ("help.requested", {"reason": "I could not find the Check Bill button.",
                          "suggestion": "I won't do any more on this. "
                                        "You can ask me for something else."})], []),
    ("17-stopped-by-you", "goal",
     [*at(("step.presented", LOOKUP)), STEP_RESPONSE,
      ("task.failed", {"reason": "You asked me to stop.", "recoverable": True})], ["stop"]),
    ("18-reply-greeting", ("goal", "hello"),
     [("goal.answered", {"kind": "greeting", "goal": "hello",
                         "flows": ["registration", "billing", "railways"]}), HOLD], []),
    ("19-reply-cannot-do", ("goal", "book a flight"),
     [("goal.answered", {"kind": "unsupported", "goal": "book a flight",
                         "flows": ["registration", "billing", "railways"]}), HOLD], []),
    ("20-reply-which-one", ("goal", "I need to pay for my course"),
     [("goal.answered", {"kind": "clarify", "goal": "I need to pay for my course",
                         "flows": ["registration", "billing"]}), HOLD], []),
    # Pressed Start; the backend has not decided yet. Numbered last so 1-20
    # line up with a capture taken before this screen existed.
    ("21-reading-the-request", "goal", [HOLD], []),
    ("22-trust-panel-whole-page", "goal",
     [*at(("step.presented", LOOKUP)), TRUST, ("page.preview", "PREVIEW"), HOLD],
     ["trust", "whole"]),
]


def preview_image(playwright) -> str:
    """A plain stand-in for the real site, as the trust panel would show it."""
    browser = playwright.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.set_content("""<body style="margin:0;font:16px sans-serif;background:#fff">
      <div style="background:#1f4e79;color:#fff;padding:18px 32px;font-size:22px">
        Electricity Company — Bill Enquiry</div>
      <div style="padding:40px 32px"><p>Reference No.</p>
      <div style="border:1px solid #999;width:360px;height:36px"></div>
      <button style="margin-top:16px;padding:10px 24px;background:#1f4e79;color:#fff;
        border:0">Check Bill</button></div></body>""")
    shot = base64.b64encode(page.screenshot(type="png")).decode()
    browser.close()
    return shot


class Backend:
    """A fake backend playing whichever screen's script is current."""

    def __init__(self, preview: str) -> None:
        self.script: list = []
        self.history: list = []
        self.preview = preview
        self.port = 0
        ready = threading.Event()

        def run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def handler(ws):
                seq = 0

                async def send(kind: str, payload) -> None:
                    nonlocal seq
                    seq += 1
                    if payload == "PREVIEW":
                        payload = {"screenshot": self.preview,
                                   "highlight": {"x": 32, "y": 196, "w": 110, "h": 40},
                                   "caption": "I'm about to press this."}
                    await ws.send(json.dumps({"v": 1, "type": kind, "task_id": "t_shots",
                                              "seq": seq, "ts": 0, "payload": payload}))

                async def until(kind: str) -> None:
                    while json.loads(await ws.recv()).get("type") != kind:
                        pass

                try:
                    await send("history.offered", {"goals": self.history})
                    if not self.script:
                        await asyncio.Future()
                    await until("task.start")
                    for kind, payload in self.script:
                        if kind == "hold":
                            await asyncio.Future()
                        elif kind == "await":
                            await until(payload["type"])
                        else:
                            await send(kind, payload)
                            await asyncio.sleep(0.15)
                    await ws.close()
                except websockets.ConnectionClosed:
                    return

            async def main() -> None:
                server = await websockets.serve(handler, "127.0.0.1", 0, max_size=None)
                self.port = server.sockets[0].getsockname()[1]
                ready.set()
                await asyncio.Future()

            loop.run_until_complete(main())

        threading.Thread(target=run, daemon=True).start()
        ready.wait(timeout=10)


def build(out: Path) -> None:
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if out.exists():
        shutil.rmtree(out)
    done = subprocess.run(
        [npx, "vite", "build", "--outDir", str(out), "--emptyOutDir", "--logLevel", "error"],
        cwd=FRONTEND, capture_output=True, text=True, timeout=300,
        # Each screen is reached a moment after the page opens.
        env={**os.environ, "VITE_SIMBA_SPLASH": "0"},
    )
    if done.returncode != 0:
        raise SystemExit(done.stderr)


def serve(directory: Path) -> str:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_address[1]}/index.html"


def capture(label: str) -> Path:
    out = REPO / ".scratch" / "screenshots" / label
    built = REPO / ".scratch" / f"overlay-shots-{label}"
    build(built)
    url = serve(built)

    with sync_playwright() as playwright:
        backend = Backend(preview_image(playwright))
        browser = playwright.chromium.launch()
        for theme in ("light", "dark"):
            (out / theme).mkdir(parents=True, exist_ok=True)
            for name, start, script, before in SCREENS:
                context = browser.new_context(viewport={"width": 1280, "height": 800},
                                              color_scheme=theme)
                page = context.new_page()
                backend.script = script
                backend.history = ([
                    {"goal": "Register for CS-401", "site": "http://127.0.0.1:5000"},
                    {"goal": "Check my electricity bill", "site": "http://127.0.0.1:5100"},
                ] if start == "home-history" else [])
                page.goto(f"{url}?ws=ws://127.0.0.1:{backend.port}")
                page.wait_for_timeout(700)
                ok = True
                try:
                    reveal = page.get_by_role("button", name="Ask for something new")
                    if "reveal" in before and reveal.count():
                        reveal.click()
                    if start == "goal" or isinstance(start, tuple):
                        text = start[1] if isinstance(start, tuple) else GOAL
                        box = page.get_by_role("textbox").first
                        if not box.is_visible() and reveal.count():
                            reveal.click()
                        box.fill(text)
                        page.keyboard.press("Enter")
                    if "go" in before or "stop" in before or "trust" in before:
                        page.wait_for_selector("[data-testid=step-shell]", timeout=8000)
                        page.wait_for_timeout(500)
                    if "go" in before:
                        page.get_by_role("button", name="Check the bill").click()
                    if "stop" in before:
                        page.get_by_role("button", name="Stop this").click()
                    if "trust" in before:
                        page.get_by_role("button", name="What are you doing?").click()
                    if "whole" in before:
                        page.wait_for_timeout(1200)
                        page.get_by_role("button", name="Show the whole page").click()
                except Exception as error:  # noqa: BLE001 - a screen that cannot be reached is reported
                    ok = False
                    print(f"  {theme:<5} {name}: could not reach ({type(error).__name__})")
                # Let arrivals and slow motion finish before the picture.
                page.wait_for_timeout(1600)
                page.screenshot(path=str(out / theme / f"{name}.png"))
                if ok:
                    print(f"  {theme:<5} {name}")
                context.close()
        browser.close()
    return out


if __name__ == "__main__":
    label = sys.argv[1] if len(sys.argv) > 1 else "current"
    print(f"wrote {capture(label)}")
