"""Four-condition ablation: overlay detection on/off x two models.

Records every run, including runs cut short by quota, so a partial condition
is reported as partial rather than silently dropped.

Produced: EVALUATION.md 2026-09-05, "ablation: does overlay detection still
help on a stronger model?" Spends model quota heavily.

Moved from `.scratch/ablation.py` on 2026-09-17. **Not exactly the version
that produced the table.** As found, `CONDITIONS` had three entries and no
`current-overlay-on`, which the table's first row needs; it was edited
between sessions and no earlier copy survives. That condition is restored
below so the script can reproduce all four rows. The demo-model rows are
capped at 3 runs here; the table reports 1 each, because quota ended them.
Pass condition labels as arguments to run only those.

Run from the repo root: `python -m tools.evaluation.overlay_ablation`.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright

from tools.evaluation.conditions import banner, conditions

REPO_ROOT = Path(__file__).resolve().parents[2]
PORT = 5030
REPLICA = f"http://127.0.0.1:{PORT}"
CREDENTIALS = {"username": "raham", "password": "hunter2"}
RUNS = 10
PAUSE_S = float(os.environ.get('ABL_PAUSE', '8'))

CURRENT_MODEL = "gemini-3.1-flash-lite"
DEMO_MODEL = "gemini-3.8-flash"

# Scarcest quota first, so a cap costs the cheapest condition, not the one
# the question is actually about.
ONLY = set(sys.argv[1:])
CHROMIUM: dict[str, str] = {}

# (label, model, overlay flag, runs). The demo model is capped at 5 requests
# per minute on this key, so a run of it costs ~5 minutes of waiting; five
# runs is what fits, and the count is reported rather than papered over.
CONDITIONS = [
    # Restored 2026-09-17: the table's first row. See the docstring.
    ("current-overlay-on", CURRENT_MODEL, "1", 10),
    ("current-overlay-off", CURRENT_MODEL, "0", 10),
    ("demo-overlay-off", DEMO_MODEL, "0", 3),
    ("demo-overlay-on", DEMO_MODEL, "1", 3),
]


def wait_for(url: str, timeout_s: float = 30.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.2)
    raise RuntimeError(f"nothing at {url}")


async def one_run(label: str, index: int) -> dict:
    # Imported here so each run picks up the current environment.
    from backend.orchestrator.llm import Transcript, provider_from_env
    from backend.orchestrator.llm_loop import REGISTRATION_TASK, LLMPlanner
    from backend.orchestrator.loop import Connection, run_task

    class Recording(Connection):
        def __init__(self) -> None:
            self.sent: list[tuple[str, dict]] = []

        async def send(self, message_type, payload):
            self.sent.append((message_type, payload.model_dump()))

        async def receive(self, message_type, step_index=None, on_other=None):
            return {
                "type": "step.response",
                "payload": {
                    "step_index": step_index,
                    "action_id": "confirm",
                    "input_values": CREDENTIALS,
                },
            }

        def of(self, message_type):
            return [p for n, p in self.sent if n == message_type]

    transcript = Transcript(REPO_ROOT / "logs" / f"abl-{label}-{index:02d}.jsonl")
    provider = provider_from_env(transcript=transcript)
    planner = LLMPlanner(provider, REGISTRATION_TASK)
    connection = Recording()

    started = time.monotonic()
    crash = None
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        CHROMIUM.setdefault("version", browser.version)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            await run_task(page, connection, planner, REGISTRATION_TASK, REPLICA)
        except Exception as error:
            crash = f"{type(error).__name__}: {error}"
        final_url = page.url
        await browser.close()
    elapsed = time.monotonic() - started
    throttled = getattr(provider, "throttled_seconds", 0.0)

    completed = connection.of("task.completed")
    helped = connection.of("help.requested")
    failure = helped[0]["reason"] if helped else None
    return {
        "run": index,
        "completed": bool(completed),
        "steps": completed[0]["steps_taken"] if completed else len(connection.of("step.presented")),
        "llm_calls": planner.calls_made,
        "seconds": round(elapsed - throttled, 1),
        "wall_seconds": round(elapsed, 1),
        "throttled_seconds": round(throttled, 1),
        "actions": [p["instruction"] for p in connection.of("step.presented")],
        "final_url": final_url,
        "failure": failure,
        "crash": crash,
        "quota_blocked": bool(failure and "429" in failure) or bool(crash and "429" in crash),
    }


async def main() -> None:
    print(banner(), flush=True)
    replica = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=REPO_ROOT / "replicas" / "registration",
        env={**os.environ, "PORT": str(PORT)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    out_path = REPO_ROOT / "logs" / "ablation.json"
    everything: dict[str, list[dict]] = (
        json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    )
    try:
        wait_for(REPLICA)
        for label, model, overlay, runs in CONDITIONS:
            if ONLY and label not in ONLY:
                continue
            os.environ["OPENAI_MODEL"] = model
            os.environ["SIMBA_OVERLAY_DETECTION"] = overlay
            print(f"\n=== {label}  model={model}  overlay={overlay} ===", flush=True)

            results = []
            for i in range(1, runs + 1):
                result = await one_run(label, i)
                results.append(result)
                mark = "OK " if result["completed"] else "FAIL"
                print(f"[{mark}] {i:2} steps={result['steps']} calls={result['llm_calls']} "
                      f"{result['seconds']}s  {' | '.join(a.rstrip('.') for a in result['actions'])}",
                      flush=True)
                if result["quota_blocked"]:
                    print(f"  ! quota exhausted after {i} run(s) of {label}", flush=True)
                    break
                if i < runs:
                    await asyncio.sleep(PAUSE_S)

            everything[label] = results
            # Per condition, because each arm sets its own model and switches
            # and may run minutes or days apart from the others.
            everything[f"{label}.conditions"] = conditions(
                model=model, overlay_detection=overlay, runs=len(results),
                chromium=CHROMIUM.get("version"))
            out_path.write_text(
                json.dumps(everything, indent=2), encoding="utf-8"
            )
    finally:
        replica.terminate()
        replica.wait(timeout=10)

    print("\nwrote logs/ablation.json", flush=True)


asyncio.run(main())
