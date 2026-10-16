"""Every flow as it runs today, ten times each, on its own replica.

Produced: EVALUATION.md 2026-10-16d, "the replica benchmarks, re-run on the
current flows", which replaces the registration numbers of 2026-09-06 and
2026-09-17 (`hardcoded_registration_benchmark`), measured before the person's
own details were asked for, before the checklist, and before the final
screen.

The real loop (`run_brief`), the briefs and hardcoded planners the app uses,
the checklist on (as the app runs it unless the person asked to be asked
each time), headless Chromium at 1280x800, each replica on its own port. No
model, no quota. Each screen is answered as a person would: signing in, Yes
to cookies, yes to the read-back, the first train, a name, the second class,
"do it" on a final screen, and "Back to start" on a closing screen's offer.

Run from the repo root: `python -m tools.evaluation.replica_flows_benchmark [runs]`.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from playwright.async_api import async_playwright

from backend.orchestrator import voice
from backend.orchestrator.details import BillBrief, CourseBrief, TripBrief, Understood
from backend.orchestrator.loop import Connection, run_brief
from tools.evaluation.conditions import banner, record

ROOT = Path(__file__).resolve().parents[2]
RUNS = int(sys.argv[1]) if len(sys.argv) > 1 else 10
PORTS = {"registration": 5031, "billing": 5131, "railways": 5231}
TOMORROW = date.today() + timedelta(days=1)


def flows() -> dict:
    """Each flow: its replica, and a fresh brief per run."""
    journey = dict(origin="Lahore Cantt", destination="Karachi Cantt", day=TOMORROW)
    return {
        "register for a course": ("registration",
                                  lambda: CourseBrief("register me for MATH-210",
                                                      Understood(course="MATH-210"))),
        "look up a bill": ("billing", lambda: BillBrief(
            "check my bill 04141234567890", Understood(reference="04141234567890"))),
        "pay a bill": ("billing", lambda: BillBrief(
            "pay my bill 04141234567890",
            Understood(reference="04141234567890", wants="pay"))),
        "find trains": ("railways", lambda: TripBrief(
            "trains from Lahore to Karachi tomorrow", Understood(**journey))),
        "book a train": ("railways", lambda: TripBrief(
            "book a train from Lahore to Karachi tomorrow",
            Understood(**journey, wants="book"))),
    }


class Person(Connection):
    """Answers each screen as a first-time person would, and counts."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []

    async def send(self, message_type, payload) -> None:
        self.sent.append((message_type, payload.model_dump()))

    async def poll(self, seconds: float = 0.0) -> list[dict]:  # noqa: ARG002
        return []

    async def receive(self, message_type, step_index=None, on_other=None) -> dict:  # noqa: ARG002
        last = self.sent[-1] if self.sent else ("", {})
        if last[0] == "task.completed":
            return self._say(0, "leave")  # "Back to start" beside the offer
        step = [p for n, p in self.sent if n == "step.presented"][-1]
        ids = [a["id"] for a in step["actions"]]
        fields = {f["id"] for f in step["fields"]}
        if "password" in fields:
            return self._say(step_index, "confirm",
                             {"username": "student", "password": "benchmark"})
        if "passenger" in fields:
            return self._say(step_index, "confirm", {"passenger": "Ayesha Khan"})
        if step["instruction"] == voice.ASK_CLASS:
            return self._say(step_index, "choice:1")
        if any(i.startswith(voice.CHOICE_PREFIX) for i in ids):
            return self._say(step_index, "choice:0")  # read-back yes; first train
        return self._say(step_index, "confirm")  # cookies Yes; a final screen's "do it"

    @staticmethod
    def _say(step_index, action_id, values=None) -> dict:
        return {"type": "step.response", "payload": {
            "step_index": step_index, "action_id": action_id, "input_values": values or {}}}

    def of(self, kind: str) -> list[dict]:
        return [p for n, p in self.sent if n == kind]


async def one(flow: str, site: str, brief) -> dict:
    person = Person()
    started = time.monotonic()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            await run_brief(page, person, brief, f"http://127.0.0.1:{PORTS[site]}", auto=True)
        finally:
            await browser.close()
    shown = person.of("step.presented")
    ends = person.of("task.completed")
    end = ends[-1] if ends else None
    return {
        "flow": flow,
        "completed": end is not None,
        "confirmed": bool(end and end.get("confirmation")),
        "presses": sum(1 for s in shown if s["requires_confirmation"]),
        "checklist_lines": sum(1 for s in shown if not s["requires_confirmation"]),
        "final_screens": sum(1 for s in shown if s.get("final")),
        "steps_taken": end["steps_taken"] if end else None,
        "llm_calls": end["llm_calls"] if end else None,
        "seconds": round(time.monotonic() - started, 1),
        "ended": next((n for n, _ in reversed(person.sent)
                       if n in ("task.completed", "task.failed", "help.requested")), None),
    }


def serve() -> list[subprocess.Popen]:
    procs = []
    for site, port in PORTS.items():
        procs.append(subprocess.Popen([sys.executable, "app.py"], cwd=ROOT / "replicas" / site,
                                      env={**os.environ, "PORT": str(port)},
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    for port in PORTS.values():
        deadline = time.time() + 30
        while True:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=1)
                break
            except OSError:
                if time.time() > deadline:
                    raise
                time.sleep(0.2)
    return procs


def main() -> None:
    print(banner(), flush=True)
    procs = serve()
    results = []
    try:
        for flow, (site, brief) in flows().items():
            for run in range(1, RUNS + 1):
                result = asyncio.run(one(flow, site, brief()))
                result["run"] = run
                results.append(result)
                print(json.dumps(result), flush=True)
    finally:
        for proc in procs:
            proc.terminate()
            proc.wait(timeout=10)
    summary = {}
    for flow in flows():
        rows = [r for r in results if r["flow"] == flow]
        seconds = sorted(r["seconds"] for r in rows)
        summary[flow] = {
            "runs": len(rows), "completed": sum(r["completed"] for r in rows),
            "confirmed": sum(r["confirmed"] for r in rows),
            "presses": sorted({r["presses"] for r in rows}),
            "checklist_lines": sorted({r["checklist_lines"] for r in rows}),
            "final_screens": sorted({r["final_screens"] for r in rows}),
            "steps_taken": sorted({r["steps_taken"] for r in rows}),
            "llm_calls": sorted({r["llm_calls"] for r in rows}),
            "seconds_mean": round(sum(seconds) / len(seconds), 2),
            "seconds_range": [seconds[0], seconds[-1]],
        }
    print(json.dumps(summary, indent=1))
    record(ROOT / "logs" / "replica_flows_benchmark.json", {"runs": results, "summary": summary})


if __name__ == "__main__":
    main()
