"""Show me once (2026-11-04): a routine taught once, then run from its tile.

Produced: EVALUATION.md 2026-11-04, "Show me once". For each routine: the
helper's side once — how long teaching took and how many presses it needed,
and how many moves were kept — then ten runs as the person, each counted for
success, presses, checklist lines, moves, model calls and time; and on our
copies, one run against the same copy changed after teaching, which has to
stop and say so rather than press something else.

The helper here is Playwright's real mouse and keyboard on the page, through
the same recorder and perception the real window uses (`teach.py`); the
person is a script answering each screen. Headless Chromium at 1280x800, no
model, no quota. Teaching time is a script's, not a person's: it measures
SIMBA's own work while watching, which a helper adds their own time to.

Run from the repo root: `python -m tools.evaluation.show_me_once [runs]`.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.request
from dataclasses import replace
from pathlib import Path

from playwright.async_api import async_playwright

from backend.orchestrator import voice
from backend.orchestrator.loop import Connection, run_brief
from backend.orchestrator.routine_plan import RoutineBrief
from backend.orchestrator.routines import RoutineStore
from backend.orchestrator.teach import teach
from tools.evaluation.conditions import banner, record

ROOT = Path(__file__).resolve().parents[2]
RUNS = int(sys.argv[1]) if len(sys.argv) > 1 else 10
REFERENCE = "04141234567890"
#: The billing copy as it is, and as it is after its search button was renamed.
BILLING, CHANGED = 5141, 5142


class Helper(Connection):
    """The overlay's side while a helper teaches: what the backend sent, and
    what the script has the bar say."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []
        self.incoming: asyncio.Queue = asyncio.Queue()
        self.presses = 0

    async def send(self, message_type, payload) -> None:
        self.sent.append((message_type, json.loads(payload.model_dump_json())))

    async def next_message(self) -> dict:
        return await self.incoming.get()

    def say(self, message_type: str, payload: dict) -> None:
        self.presses += 1
        self.incoming.put_nowait({"type": message_type, "payload": payload})

    def bar(self) -> dict:
        return [p for n, p in self.sent if n == "teach.watching"][-1]

    async def until(self, ready, timeout: float = 30.0) -> None:
        deadline = time.monotonic() + timeout
        while not ready():
            if time.monotonic() > deadline:
                raise TimeoutError([n for n, _ in self.sent])
            await asyncio.sleep(0.05)


async def teach_the_bill(store: RoutineStore) -> dict:
    """The bill, shown once on the billing copy, as `test_teach.py` shows it."""
    helper = Helper()
    page_presses = 0
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        started = time.monotonic()
        job = asyncio.create_task(teach(page, helper, f"http://127.0.0.1:{BILLING}", store))
        await helper.until(lambda: any(n == "teach.watching" for n, _ in helper.sent))
        await page.get_by_role("button", name="Accept all cookies").click()
        await page.get_by_role("textbox", name="Reference No.").fill(REFERENCE)
        await page.get_by_role("button", name="Check Bill").click()
        page_presses += 3
        await page.wait_for_url("**/bill")
        await helper.until(lambda: helper.bar()["question"] is not None)
        helper.say("teach.answer", {"action": "ask", "step": helper.bar()["question"]["step"]})
        await helper.until(lambda: helper.bar()["question"] is None)
        helper.say("teach.answer", {"action": "finish"})
        await helper.until(lambda: helper.bar()["pointing"])
        await page.get_by_text("14,382", exact=True).first.click()
        page_presses += 1
        await helper.until(lambda: any(n == "step.presented" for n, _ in helper.sent))
        readback = [p for n, p in helper.sent if n == "step.presented"][0]["routine"]
        helper.say("step.response", {"step_index": 1, "action_id": "confirm",
                                     "input_values": {"name": "My bill", "answer": "Amount due"}})
        kept = await asyncio.wait_for(job, 30)
        seconds = time.monotonic() - started
        await browser.close()
    return {"routine": kept, "seconds": round(seconds, 1), "moves": len(kept.steps),
            "asked_each_time": len(kept.asks), "helper_presses_on_page": page_presses,
            "helper_presses_on_bar": helper.presses, "read_back": readback}


class Person(Connection):
    """Answers each screen as a person would: the number when asked, Yes to
    cookies, and counts what was shown."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []

    async def send(self, message_type, payload) -> None:
        self.sent.append((message_type, json.loads(payload.model_dump_json())))

    async def poll(self, seconds: float = 0.0) -> list[dict]:  # noqa: ARG002
        return []

    async def receive(self, message_type, step_index=None, on_other=None) -> dict:  # noqa: ARG002
        step = [p for n, p in self.sent if n == "step.presented"][-1]
        values = {f["id"]: REFERENCE for f in step["fields"] if f["id"].startswith("value")}
        # The offer of a model, if one is set up: no, as a person who wants
        # only what the helper showed would say.
        action = voice.DECLINE_ID if step["instruction"] == voice.ROUTINE_TRY else "confirm"
        return {"type": "step.response", "payload": {
            "step_index": step_index, "action_id": action, "input_values": values}}

    def of(self, kind: str) -> list[dict]:
        return [p for n, p in self.sent if n == kind]


async def one(routine) -> dict:
    person = Person()
    started = time.monotonic()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            await run_brief(page, person, RoutineBrief(routine), routine.start, auto=True)
        finally:
            await browser.close()
    shown = person.of("step.presented")
    end = (person.of("task.completed") or [None])[-1]
    stuck = (person.of("help.requested") or [None])[-1]
    return {
        "completed": end is not None,
        "answer": end["findings"][0]["values"] if end and end["findings"] else None,
        "proof": bool(end and end.get("proof")),
        "presses": sum(1 for s in shown if s["requires_confirmation"]),
        "checklist_lines": sum(1 for s in shown if not s["requires_confirmation"]),
        "steps_taken": end["steps_taken"] if end else None,
        "llm_calls": end["llm_calls"] if end else 0,
        "seconds": round(time.monotonic() - started, 1),
        "stopped_because": stuck["reason"] if stuck else None,
    }


def serve() -> list[subprocess.Popen]:
    procs = []
    for port, label in ((BILLING, None), (CHANGED, "Find my bill")):
        env = {**os.environ, "PORT": str(port)}
        if label:
            env["BILLING_CHECK_LABEL"] = label
        procs.append(subprocess.Popen([sys.executable, "app.py"], cwd=ROOT / "replicas" / "billing",
                                      env=env, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL))
    for port in (BILLING, CHANGED):
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
    store = RoutineStore(ROOT / ".scratch" / "show-me-once" / "eval-routines.json")
    store.clear()
    procs = serve()
    try:
        taught = asyncio.run(teach_the_bill(store))
        routine = taught.pop("routine")
        print(json.dumps(taught), flush=True)
        runs = []
        for run in range(1, RUNS + 1):
            result = asyncio.run(one(routine))
            result["run"] = run
            runs.append(result)
            print(json.dumps(result), flush=True)
        changed = asyncio.run(one(replace(routine, start=f"http://127.0.0.1:{CHANGED}")))
        print(json.dumps({"changed": changed}), flush=True)
    finally:
        for proc in procs:
            proc.terminate()
            proc.wait(timeout=10)
        store.clear()
    seconds = sorted(r["seconds"] for r in runs)
    summary = {
        "bill on the billing copy": {
            "teaching": taught,
            "runs": len(runs),
            "completed": sum(r["completed"] for r in runs),
            "right_answer": sum(r["answer"] == ["14,382"] for r in runs),
            "with_proof": sum(r["proof"] for r in runs),
            "presses": sorted({r["presses"] for r in runs}),
            "checklist_lines": sorted({r["checklist_lines"] for r in runs}),
            "steps_taken": sorted({r["steps_taken"] for r in runs}),
            "llm_calls": sorted({r["llm_calls"] for r in runs}),
            "seconds_mean": round(sum(seconds) / len(seconds), 2),
            "seconds_range": [seconds[0], seconds[-1]],
            "changed_after_teaching": changed,
        },
    }
    print(json.dumps(summary, indent=1))
    record(ROOT / "logs" / "show_me_once.json", {"runs": runs, "summary": summary})


if __name__ == "__main__":
    main()
