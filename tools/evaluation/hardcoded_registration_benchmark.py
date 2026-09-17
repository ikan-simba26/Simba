"""Ten hardcoded-planner runs on the registration replica, for the A/B.

Produced: EVALUATION.md 2026-09-06, "hardcoded plan vs LLM", the Hardcoded
row. No model, no quota.

Moved from `.scratch/hardcoded_ab.py` on 2026-09-17. One fix: its fake
connection's `receive` lacked the `on_other` argument the loop has passed
since the trust panel was added, so as found it could not run against the
current loop. Re-run on 2026-09-17 to confirm it reproduces (EVALUATION.md).

Run from the repo root: `python -m tools.evaluation.hardcoded_registration_benchmark`.
"""
import asyncio, json, os, subprocess, sys, time, urllib.error, urllib.request
from pathlib import Path
from playwright.async_api import async_playwright

from backend.orchestrator.loop import Connection, run_task
from backend.orchestrator.llm_loop import REGISTRATION_TASK
from backend.orchestrator.plan import REGISTRATION_PLAN, HardcodedPlanner
from dataclasses import replace

ROOT = Path(__file__).resolve().parents[2]
PORT, RUNS = 5030, 10
REPLICA = f"http://127.0.0.1:{PORT}"
CREDS = {"username": "raham", "password": "hunter2"}
TASK = replace(REGISTRATION_TASK, estimated_steps=len(REGISTRATION_PLAN))

class Rec(Connection):
    def __init__(self): self.sent = []
    async def send(self, t, p): self.sent.append((t, p.model_dump()))
    async def receive(self, t, step_index=None, on_other=None):
        return {"type": "step.response", "payload": {"step_index": step_index,
                "action_id": "confirm", "input_values": CREDS}}
    def of(self, t): return [p for n, p in self.sent if n == t]

def wait_for(url, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        try: urllib.request.urlopen(url, timeout=1); return
        except Exception: time.sleep(0.2)
    raise RuntimeError(url)

async def one(i):
    c = Rec(); started = time.monotonic()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width":1280,"height":800})
        await run_task(pg, c, HardcodedPlanner(REGISTRATION_PLAN), TASK, REPLICA)
        url = pg.url
        await b.close()
    done = c.of("task.completed")
    return {"run": i, "completed": bool(done),
            "steps": done[0]["steps_taken"] if done else len(c.of("step.presented")),
            "llm_calls": done[0]["llm_calls"] if done else None,
            "seconds": round(time.monotonic()-started, 1),
            "actions": [p["instruction"] for p in c.of("step.presented")],
            "final_url": url,
            "failure": (c.of("help.requested") or [{}])[0].get("reason")}

async def main():
    proc = subprocess.Popen([sys.executable, "app.py"],
        cwd=ROOT/"replicas"/"registration", env={**os.environ, "PORT": str(PORT)},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_for(REPLICA)
        out = []
        for i in range(1, RUNS+1):
            r = await one(i); out.append(r)
            print(f"[{'OK ' if r['completed'] else 'FAIL'}] {i:2} steps={r['steps']} "
                  f"calls={r['llm_calls']} {r['seconds']}s", flush=True)
    finally:
        proc.terminate(); proc.wait(timeout=10)
    (ROOT/"logs"/"hardcoded_ab.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("wrote logs/hardcoded_ab.json")

asyncio.run(main())
