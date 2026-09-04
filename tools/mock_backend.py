"""Mock backend for SIMBA.

Plays a scripted sequence of backend-to-frontend messages for one complete
task, so the frontend can be built with no real backend running. Also the
demo-day fallback (see CONTRACT.md). Keep this in sync with CONTRACT.md.

Run: uvicorn tools.mock_backend:app --port 8000 --app-dir .
"""

import json
import sys
from pathlib import Path

from fastapi import FastAPI, WebSocket

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.envelope import envelope  # noqa: E402
from shared.schema import (  # noqa: E402
    BaseModel,
    LoadUpdated,
    StateChanged,
    StepAction,
    StepPresented,
    TaskCompleted,
    TaskStarted,
)

TASK_ID = "t_demo01"
GOAL = "Register for CS-401"

STEPS = [
    StepPresented(
        step_index=1,
        step_total=3,
        instruction="Log in to the course portal.",
        detail="Using your saved university credentials.",
        fields=[],
        actions=[
            StepAction(id="confirm", label="Log in", kind="primary"),
            StepAction(id="cancel", label="Not now", kind="secondary"),
        ],
        requires_confirmation=True,
    ),
    StepPresented(
        step_index=2,
        step_total=3,
        instruction="Add CS-401 to your course list.",
        detail="3 credit hours. Seats available: 12.",
        fields=[],
        actions=[
            StepAction(id="confirm", label="Add course", kind="primary"),
            StepAction(id="cancel", label="Not now", kind="secondary"),
        ],
        requires_confirmation=True,
    ),
    StepPresented(
        step_index=3,
        step_total=3,
        instruction="Submit your registration for CS-401.",
        detail="This finalizes your schedule for the term.",
        fields=[],
        actions=[
            StepAction(id="confirm", label="Submit", kind="primary"),
            StepAction(id="cancel", label="Not now", kind="secondary"),
        ],
        requires_confirmation=True,
    ),
]

app = FastAPI()


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    seq = 0

    async def send(msg_type: str, payload: BaseModel) -> None:
        nonlocal seq
        seq += 1
        await ws.send_text(json.dumps(envelope(msg_type, TASK_ID, seq, payload)))

    async def receive(msg_type: str, step_index: int | None = None) -> None:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            matches = msg.get("type") == msg_type and (
                step_index is None or msg.get("payload", {}).get("step_index") == step_index
            )
            if not matches:
                print(f"mock_backend: ignoring unexpected message {msg.get('type')!r}")
                continue
            return

    await receive("task.start")

    await send("task.started", TaskStarted(goal=GOAL, estimated_steps=len(STEPS)))
    await send("state.changed", StateChanged(state="thinking"))

    for i, step in enumerate(STEPS):
        await send("state.changed", StateChanged(state="acting"))
        await send("step.presented", step)
        await receive("step.response", step.step_index)

        if i == 0:
            await send(
                "load.updated",
                LoadUpdated(score=0.35, level=1, reason="first step, low element count"),
            )

        await send("state.changed", StateChanged(state="thinking"))

    await send(
        "task.completed",
        TaskCompleted(
            summary="Registered for CS-401.",
            duration_ms=48200,
            steps_taken=len(STEPS),
            llm_calls=0,
            replayed=False,
        ),
    )
    await ws.close()
