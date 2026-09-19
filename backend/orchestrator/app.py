"""FastAPI entry point for the orchestrator.

Run from the repo root:

    python -m uvicorn backend.orchestrator.app:app --port 8000

The frontend connects to /ws, sends `task.start`, and answers each
`step.presented` with a `step.response`.

Two switches, both environment variables:

- `SIMBA_FLOW` picks the site, the replica URL and the hardcoded plan:
  `registration` (default), `billing`, `railways`, or `stubborn` — a
  registration-replica page whose first control does nothing, for measuring
  recovery. The *goal* comes from the frontend's `task.start`; the flow's own
  goal is only the fallback when the message carries none.
- `SIMBA_USE_HARDCODED_PLAN=1` runs that flow's hardcoded plan instead of the
  LLM — the A/B comparison, and the deterministic fallback for demo day.
- `SIMBA_TRACE_MEMORY=1` wraps whichever planner was chosen in `TracePlanner`,
  so a goal already done on this site replays from SQLite instead of being
  planned again.
- `SIMBA_BROWSER` is `chromium` (default, launches its own headless browser)
  or `electron` (attaches over CDP to a running host and drives its hidden
  site view). See `browser.py`.
"""

import os
import sqlite3
from dataclasses import replace
from pathlib import Path

from fastapi import FastAPI, WebSocket

from backend.orchestrator.billing_plan import BILLING_PLAN, BILLING_TASK
from backend.orchestrator.browser import browser_source, open_page
from backend.orchestrator.llm import provider_from_env
from backend.orchestrator.llm_loop import REGISTRATION_TASK, LLMPlanner
from backend.estimator.pairing import Recorder, recording_enabled
from backend.orchestrator.loop import Connection, run_task
from backend.orchestrator.plan import REGISTRATION_PLAN, HardcodedPlanner
from backend.orchestrator.railways_plan import RAILWAYS_PLAN, RAILWAYS_TASK, RAILWAYS_URL
from backend.orchestrator.replay import TracePlanner
from backend.orchestrator.stubborn_plan import STUBBORN_PLAN, STUBBORN_TASK, STUBBORN_URL
from backend.orchestrator.traces import TraceStore, site_of
from shared.schema import HistoryOffered, PastGoal

DEFAULT_DB = str(Path(__file__).resolve().parents[2] / "traces.db")
# How many past goals the home screen offers. Three large cards is a choice;
# a list of them is the cluttered interface this project exists to remove.
HOME_GOALS = 3

FLOWS = {
    "registration": (REGISTRATION_TASK, REGISTRATION_PLAN, "http://127.0.0.1:5000"),
    "billing": (BILLING_TASK, BILLING_PLAN, "http://127.0.0.1:5100"),
    # The only flow that is not a replica we wrote. Read-only.
    "railways": (RAILWAYS_TASK, RAILWAYS_PLAN, RAILWAYS_URL),
    # A replica page whose first control does nothing, so the loop's recovery
    # and a planner's use of a setback can be measured. See stubborn_plan.py.
    "stubborn": (STUBBORN_TASK, STUBBORN_PLAN, STUBBORN_URL),
}

app = FastAPI()


def _flag(name: str) -> bool:
    return os.environ.get(name, "0").strip().lower() in {"1", "true", "yes"}


def use_hardcoded_plan() -> bool:
    return _flag("SIMBA_USE_HARDCODED_PLAN")


def use_trace_memory() -> bool:
    return _flag("SIMBA_TRACE_MEMORY")


def selected_flow() -> tuple:
    name = os.environ.get("SIMBA_FLOW", "registration").strip().lower()
    if name not in FLOWS:
        raise RuntimeError(f"unknown SIMBA_FLOW {name!r}; expected one of {sorted(FLOWS)}")
    task, plan, default_url = FLOWS[name]
    return name, task, plan, os.environ.get("SIMBA_REPLICA_URL", default_url)


@app.get("/")
async def health() -> dict[str, str]:
    name, _, _, url = selected_flow()
    return {
        "status": "ok",
        "flow": name,
        "planner": "hardcoded" if use_hardcoded_plan() else "llm",
        "trace_memory": "on" if use_trace_memory() else "off",
        "browser": browser_source(),
        "replica": url,
    }


def past_goals() -> HistoryOffered:
    """What this person has asked for before, most recent first.

    Read from the same SQLite store trace replay uses, so the home screen
    offers exactly the goals that would replay rather than a separate list
    that could disagree with it. Capped: the home screen shows a few large
    cards, and a long list of them is the cluttered interface this project
    exists to remove.
    """
    try:
        store = TraceStore(os.environ.get("SIMBA_TRACE_DB", DEFAULT_DB))
        goals = store.recent(limit=HOME_GOALS)
    except sqlite3.Error:
        # A missing or unreadable store is an empty home screen, not a dead
        # socket. The text box is always there underneath.
        return HistoryOffered(goals=[])
    return HistoryOffered(goals=[PastGoal(goal=goal, site=site) for goal, site in goals])


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    connection = Connection(websocket, task_id="t_skeleton")

    # Offered before anything is asked for, so the home screen has something
    # to show the moment it connects.
    await connection.send("history.offered", past_goals())

    start = await connection.receive("task.start")

    _, task, plan, replica_url = selected_flow()

    # The goal comes from the frontend. SIMBA_FLOW still decides which site
    # to open and which hardcoded plan is available, but what the user typed
    # is what the task is — a documented field that was quietly discarded is
    # worse than no field at all (DECISIONS.md).
    goal = (start.get("payload", {}).get("goal") or "").strip()
    if goal:
        task = replace(task, goal=goal)

    # The only thing the flag changes is which planner picks the next move —
    # and how many steps it can promise up front, which the hardcoded plan
    # knows exactly and the LLM can only estimate.
    if use_hardcoded_plan():
        task = replace(task, estimated_steps=len(plan))
        planner = HardcodedPlanner(plan)
    else:
        planner = LLMPlanner(provider_from_env(), task)

    # Trace memory wraps whatever was chosen: replay the remembered run if
    # there is one, and hand back to that planner the moment it stops fitting.
    if use_trace_memory():
        store = TraceStore(os.environ.get("SIMBA_TRACE_DB", DEFAULT_DB))
        planner = TracePlanner(store, task, site_of(replica_url), planner)

    # Channel B's other half: every step's page features, paired with whatever
    # telemetry the overlay sends about it, appended to `data/steps.jsonl`.
    # `SIMBA_RECORD_STEPS=0` turns it off (`backend/estimator/pairing.py`).
    recorder = Recorder(task_id="t_skeleton") if recording_enabled() else None

    async with open_page(replica_url) as page:
        await run_task(page, connection, planner, task, replica_url, recorder)

    await websocket.close()
