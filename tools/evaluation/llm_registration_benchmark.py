"""Run the LLM-planned registration flow N times and record what happened.

Produced: EVALUATION.md 2026-09-05, both ten-run LLM tables (commits
`e1ed61c` and `25324d3`) — the run-by-run tables and "Before and after".
Spends model quota: one run is 5-10 requests. Takes an optional run count.
Moved from `.scratch/benchmark.py` on 2026-09-17, unchanged but for paths.

Run from the repo root: `python -m tools.evaluation.llm_registration_benchmark`.
"""

import asyncio
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright

from backend.orchestrator.llm import Transcript, provider_from_env
from backend.orchestrator.llm_loop import REGISTRATION_TASK, LLMPlanner
from backend.orchestrator.loop import Connection, run_task
from tools.evaluation.conditions import banner, record

REPO_ROOT = Path(__file__).resolve().parents[2]
PORT = 5030
REPLICA = f"http://127.0.0.1:{PORT}"
CREDENTIALS = {"username": "raham", "password": "hunter2"}
RUNS = int(sys.argv[1]) if len(sys.argv) > 1 else 10
CHROMIUM: dict[str, str] = {}
PAUSE_S = 5.0  # stay under the free-tier rate limit


class RecordingConnection(Connection):
    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []

    async def send(self, message_type: str, payload) -> None:
        self.sent.append((message_type, payload.model_dump()))

    async def receive(self, message_type: str, step_index: int | None = None, on_other=None) -> dict:
        return {
            "type": "step.response",
            "payload": {
                "step_index": step_index,
                "action_id": "confirm",
                "input_values": CREDENTIALS,
            },
        }

    def of(self, message_type: str) -> list[dict]:
        return [p for n, p in self.sent if n == message_type]


def wait_for(url: str, timeout_s: float = 30.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.2)
    raise RuntimeError(f"nothing at {url}")


async def one_run(index: int) -> dict:
    transcript = Transcript(REPO_ROOT / "logs" / f"bench-run{index:02d}.jsonl")
    provider = provider_from_env(transcript=transcript)
    planner = LLMPlanner(provider, REGISTRATION_TASK)
    connection = RecordingConnection()

    started = time.monotonic()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        CHROMIUM.setdefault("version", browser.version)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            await run_task(page, connection, planner, REGISTRATION_TASK, REPLICA)
        except Exception as error:  # a crash is a result too
            connection.sent.append(("crashed", {"error": f"{type(error).__name__}: {error}"}))
        final_url = page.url
        await browser.close()
    elapsed = time.monotonic() - started

    completed = connection.of("task.completed")
    helped = connection.of("help.requested")
    return {
        "run": index,
        "completed": bool(completed),
        "steps": completed[0]["steps_taken"] if completed else len(connection.of("step.presented")),
        "llm_calls": planner.calls_made,
        "seconds": round(elapsed, 1),
        "actions": [p["instruction"] for p in connection.of("step.presented")],
        "final_url": final_url,
        "failure": helped[0]["reason"] if helped else None,
        "crash": (connection.of("crashed") or [{}])[0].get("error"),
    }


async def main() -> None:
    print(banner(), flush=True)
    replica = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=REPO_ROOT / "replicas" / "registration",
        env={**__import__("os").environ, "PORT": str(PORT)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for(REPLICA)
        results = []
        for i in range(1, RUNS + 1):
            result = await one_run(i)
            results.append(result)
            mark = "OK " if result["completed"] else "FAIL"
            print(f"[{mark}] run {i:2}  steps={result['steps']} "
                  f"calls={result['llm_calls']} {result['seconds']}s")
            for action in result["actions"]:
                print(f"          - {action}")
            if result["failure"]:
                print(f"          ! {result['failure'][:160]}")
            if result["crash"]:
                print(f"          ! crash: {result['crash'][:160]}")
            if i < RUNS:
                await asyncio.sleep(PAUSE_S)
    finally:
        replica.terminate()
        replica.wait(timeout=10)

    out = REPO_ROOT / "logs" / "benchmark.json"
    record(out, results, runs=RUNS, chromium=CHROMIUM.get("version"))
    print("\nwrote", out)


asyncio.run(main())
