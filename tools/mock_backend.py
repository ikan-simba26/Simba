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

from backend.orchestrator.voice import actions  # noqa: E402
from shared.envelope import envelope  # noqa: E402
from shared.schema import (  # noqa: E402
    BaseModel,
    Finding,
    HistoryOffered,
    LoadUpdated,
    PastGoal,
    StateChanged,
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

# The answer the scripted task is looking for, and the step it turns up on.
# Two values, because a real answer usually has a qualifier attached: the
# amount is the thing asked for and the date is what makes it actionable.
FOUND_AT_STEP = 3
FINDINGS = [
    Finding(label="Your bill", value="14,382 rupees"),
    Finding(label="Due", value="15 September"),
]

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
        instruction="Let me sign you in first.",
        detail="Using your saved university credentials.",
        fields=[],
        actions=actions("Log in"),
        requires_confirmation=True,
    ),
    StepPresented(
        step_index=2,
        step_total=3,
        instruction="Now I'll add CS-401 for you.",
        detail="3 credit hours. Seats available: 12.",
        fields=[],
        actions=actions("Add course"),
        requires_confirmation=True,
    ),
    StepPresented(
        step_index=3,
        step_total=4,
        # Two sentences, so level 3 trimming to the first one is visible.
        instruction=(
            "Ready to confirm your place. This uses one of your four "
            "elective slots for the year."
        ),
        detail="Advanced Widget Design, 3 credit hours, Dr. Aslam.",
        fields=[
            StepField(id="student_id", label="Student ID", type="text", value=""),
        ],
        actions=actions("Confirm my place"),
        requires_confirmation=True,
    ),
    StepPresented(
        step_index=4,
        step_total=4,
        instruction="Last one — I'll send it now.",
        detail="This finalizes your schedule for the term.",
        fields=[],
        actions=actions("Submit"),
        requires_confirmation=True,
    ),
]

app = FastAPI()


@app.get("/")
async def health() -> dict[str, str]:
    """Same shape as the real backend's, so a launcher can poll either.

    Without this, readiness could only be inferred from a 404, which is true
    by accident rather than by statement.
    """
    return {
        "status": "ok",
        "flow": "mock",
        "planner": "scripted",
        "trace_memory": "off",
        "browser": "none",
        "replica": "none",
    }


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

    # The home screen's cards. Two, so the screen shows a choice rather than
    # a single button that looks like the only option.
    await send(
        "history.offered",
        HistoryOffered(
            goals=[
                PastGoal(goal="Register for CS-401", site="http://127.0.0.1:5000"),
                PastGoal(goal="Check my electricity bill", site="http://127.0.0.1:5100"),
            ]
        ),
    )

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
                    instruction="The portal opened a notice. I'll close it.",
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
        # From the step the amount is on, the answer travels with every step
        # and then with the ending — the same journey a real run makes.
        await send(
            "step.presented",
            step.model_copy(update={"findings": FINDINGS})
            if step.step_index >= FOUND_AT_STEP
            else step,
        )
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
            findings=FINDINGS,
        ),
    )
    await ws.close()
