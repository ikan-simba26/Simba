"""Mock backend for SIMBA.

Plays a scripted sequence of backend-to-frontend messages for one complete
task, so the frontend can be built with no real backend running. Also the
demo-day fallback (see CONTRACT.md). Keep this in sync with CONTRACT.md.

Run: uvicorn tools.mock_backend:app --port 8000 --app-dir .
"""

import asyncio
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
    StepFailed,
    StepField,
    StepPresented,
    TaskCompleted,
    TaskStarted,
)

TASK_ID = "t_demo01"
GOAL = "Register for CS-401"

# The level the frontend should be at when each step is presented. The
# estimator does not exist yet, so this is scripted: two steps at the default,
# The step the mock reports as skipped. Third, so there is a step before it
# to have "failed" and a step after it for the notice to sit above.
FAILED_BEFORE_STEP = 3

# one at level 3, then back. It is here so the level change — the fold from
# one level to the next — can be demoed and worked on without one.
LEVEL_BEFORE_STEP = {3: 3, 4: 2}

LOAD_REASONS = {
    3: "long hesitation, two backtracks",
    4: "recovered, acting quickly again",
}

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
        step_total=4,
        # Two sentences, so level 3 trimming to the first one is visible.
        instruction=(
            "Confirm your place on CS-401. This uses one of your four "
            "elective slots for the year."
        ),
        detail="Advanced Widget Design, 3 credit hours, Dr. Aslam.",
        fields=[
            StepField(id="student_id", label="Student ID", type="text", value=""),
        ],
        actions=[
            StepAction(id="confirm", label="Confirm my place", kind="primary"),
            StepAction(id="cancel", label="Not now", kind="secondary"),
        ],
        requires_confirmation=True,
    ),
    StepPresented(
        step_index=4,
        step_total=4,
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

    for step in STEPS:
        # One step is reported as having failed and been carried past, so the
        # quiet notice can be seen without waiting for a real page to break.
        if step.step_index == FAILED_BEFORE_STEP:
            await send(
                "step.failed",
                StepFailed(
                    step_index=step.step_index - 1,
                    instruction="Close the registration alert.",
                    reason=(
                        "click on 'Close' failed: Locator.click: Timeout "
                        "10000ms exceeded"
                    ),
                    strategies_tried=2,
                ),
            )
            await asyncio.sleep(0.4)

        # A level change lands before the step it applies to, so the fold and
        # the new step do not arrive in the same frame.
        level = LEVEL_BEFORE_STEP.get(step.step_index)
        if level is not None:
            await send(
                "load.updated",
                LoadUpdated(
                    score=0.72 if level == 3 else 0.31,
                    level=level,
                    reason=LOAD_REASONS[step.step_index],
                ),
            )
            await asyncio.sleep(0.6)

        await send("state.changed", StateChanged(state="acting"))
        await send("state.changed", StateChanged(state="waiting"))
        await send("step.presented", step)
        await receive("step.response", step.step_index)

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
