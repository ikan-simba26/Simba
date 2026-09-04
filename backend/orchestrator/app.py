"""FastAPI entry point for the walking skeleton.

Run from the repo root:

    python -m uvicorn backend.orchestrator.app:app --port 8000

The frontend connects to /ws, sends `task.start`, and answers each
`step.presented` with a `step.response`.
"""

import os

from fastapi import FastAPI, WebSocket
from playwright.async_api import async_playwright

from backend.orchestrator.loop import Connection, run_task
from backend.orchestrator.plan import REGISTRATION_PLAN

# 1280x800 is frozen — see CLAUDE.md's architecture constraints.
VIEWPORT = {"width": 1280, "height": 800}
REPLICA_URL = os.environ.get("SIMBA_REPLICA_URL", "http://127.0.0.1:5000")

app = FastAPI()


@app.get("/")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    connection = Connection(websocket, task_id="t_skeleton")
    await connection.receive("task.start")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport=VIEWPORT)
        try:
            await run_task(page, connection, REGISTRATION_PLAN, REPLICA_URL)
        finally:
            await browser.close()

    await websocket.close()
