"""FastAPI entry point for the orchestrator.

Run from the repo root:

    python -m uvicorn backend.orchestrator.app:app --port 8000

The frontend connects to /ws, sends `task.start`, and answers each
`step.presented` with a `step.response`.

Two switches, both environment variables:

- `SIMBA_FLOW` picks the site and task: `registration` (default) or `billing`.
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
from dataclasses import replace
from pathlib import Path

from fastapi import FastAPI, WebSocket

from backend.orchestrator.billing_plan import BILLING_PLAN, BILLING_TASK
from backend.orchestrator.browser import browser_source, open_page
from backend.orchestrator.llm import provider_from_env
from backend.orchestrator.llm_loop import REGISTRATION_TASK, LLMPlanner
from backend.orchestrator.loop import Connection, run_task
from backend.orchestrator.plan import REGISTRATION_PLAN, HardcodedPlanner
from backend.orchestrator.replay import TracePlanner
from backend.orchestrator.traces import TraceStore, site_of

DEFAULT_DB = str(Path(__file__).resolve().parents[2] / "traces.db")

FLOWS = {
    "registration": (REGISTRATION_TASK, REGISTRATION_PLAN, "http://127.0.0.1:5000"),
    "billing": (BILLING_TASK, BILLING_PLAN, "http://127.0.0.1:5100"),
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


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    connection = Connection(websocket, task_id="t_skeleton")
    await connection.receive("task.start")

    _, task, plan, replica_url = selected_flow()

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

    async with open_page(replica_url) as page:
        await run_task(page, connection, planner, task, replica_url)

    await websocket.close()
