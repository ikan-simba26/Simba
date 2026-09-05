"""FastAPI entry point for the orchestrator.

Run from the repo root:

    python -m uvicorn backend.orchestrator.app:app --port 8000

The frontend connects to /ws, sends `task.start`, and answers each
`step.presented` with a `step.response`.

Planning comes from the LLM by default. Set `SIMBA_USE_HARDCODED_PLAN=1` to
run the hardcoded plan in `plan.py` instead — the A/B comparison, and the
deterministic fallback for demo day.
"""

import os
from dataclasses import replace

from fastapi import FastAPI, WebSocket
from playwright.async_api import async_playwright

from backend.orchestrator.llm import provider_from_env
from backend.orchestrator.llm_loop import REGISTRATION_TASK, LLMPlanner
from backend.orchestrator.loop import Connection, run_task
from backend.orchestrator.plan import REGISTRATION_PLAN, HardcodedPlanner

# 1280x800 is frozen — see CLAUDE.md's architecture constraints.
VIEWPORT = {"width": 1280, "height": 800}
REPLICA_URL = os.environ.get("SIMBA_REPLICA_URL", "http://127.0.0.1:5000")

app = FastAPI()


def use_hardcoded_plan() -> bool:
    return os.environ.get("SIMBA_USE_HARDCODED_PLAN", "0").strip().lower() in {"1", "true", "yes"}


@app.get("/")
async def health() -> dict[str, str]:
    return {"status": "ok", "planner": "hardcoded" if use_hardcoded_plan() else "llm"}


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    connection = Connection(websocket, task_id="t_skeleton")
    await connection.receive("task.start")

    # The only thing the flag changes is which planner picks the next move —
    # and how many steps it can promise up front, which the hardcoded plan
    # knows exactly and the LLM can only estimate.
    if use_hardcoded_plan():
        task = replace(REGISTRATION_TASK, estimated_steps=len(REGISTRATION_PLAN))
        planner = HardcodedPlanner(REGISTRATION_PLAN)
    else:
        task = REGISTRATION_TASK
        planner = LLMPlanner(provider_from_env(), task)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport=VIEWPORT)
        try:
            await run_task(page, connection, planner, task, REPLICA_URL)
        finally:
            await browser.close()

    await websocket.close()
