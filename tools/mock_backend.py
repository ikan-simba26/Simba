"""Mock backend for SIMBA.

Plays scripted backend-to-frontend messages so the frontend can be built with
no real backend running. Also the demo-day fallback (see CONTRACT.md). Keep
this in sync with CONTRACT.md.

**It routes a typed goal exactly as the real backend does** (2026-09-21): the
same `router.route`, with the same configured model and the same keyword
fallback. "hello" gets a greeting and cards, "book a flight" gets told what
can be done, "pay for my course" gets asked which, and a request for one of
the three flows plays that flow's script. Until that day it played the
registration script whatever was typed — and carried the billing flow's
answer on it — so a demo taught the wrong thing about what the product does.

The billing and railways scripts present the real plans' own steps, so the
demo says what the product says. The registration script is its own: it is
where the step-failed notice and the level changes are demonstrated.

Run: uvicorn tools.mock_backend:app --port 8000 --app-dir .
"""

import asyncio
import json
import sys
from pathlib import Path

from fastapi import FastAPI, WebSocket

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.orchestrator.billing_plan import BILLING_PLAN  # noqa: E402
from backend.orchestrator.railways_plan import RAILWAYS_PLAN  # noqa: E402
from backend.orchestrator.router import (  # noqa: E402
    ROUTABLE,
    Route,
    configured_classifier,
    route,
    use_model,
)
from backend.orchestrator.voice import actions  # noqa: E402
from shared.envelope import envelope  # noqa: E402
from backend.orchestrator import voice
from shared.schema import (  # noqa: E402
    BaseModel,
    Finding,
    GoalAnswered,
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

# --- registration: the demo of everything that can happen mid-task ------------

# The step the mock reports as skipped. Third, so there is a step before it
# to have "failed" and a step after it for the notice to sit above.
FAILED_BEFORE_STEP = 3

# The level the frontend should be at when each step is presented. The
# estimator does not exist yet, so this is scripted: two steps at the default,
# one at level 3, then back. It is here so the level change — the fold from
# one level to the next — can be demoed and worked on without one.
LEVEL_BEFORE_STEP = {3: 3, 4: 2}

LOAD_REASONS = {
    3: "long hesitation, two backtracks",
    4: "recovered, acting quickly again",
}

REGISTRATION_STEPS = [
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


def from_plan(plan) -> list[StepPresented]:
    """A real plan's steps, as the real backend would present them."""
    return [
        StepPresented(
            step_index=index,
            step_total=len(plan),
            instruction=step.instruction,
            detail=step.detail,
            fields=list(step.fields),
            actions=list(step.actions),
            requires_confirmation=True,
        )
        for index, step in enumerate(plan, start=1)
    ]


#: The answers, exactly as the sites print them.
#:
#: The bill is the billing replica's own `BILL["payable_within"]` and
#: `BILL["due_date"]`, character for character, and `test_mock_backend`
#: fails if they drift. Until 2026-09-21 this said "15 October 2026": the
#: wrong month, in a format the page never uses, on the screen that exists
#: to give the person the answer — invented while writing the demo, and shown
#: on demo day. The product was never wrong; the demo of it was.
#:
#: Railways has no replica. These are the values the live site returned on
#: 2026-09-21 for Lahore to Karachi, in its own format (EVALUATION.md).
BILL_AMOUNT = "14,382"
BILL_DUE = "15-09-2026"
TRAIN = "2DN"
JOURNEY = "22 h 16 min"

#: One script per flow: (steps, findings, the step the answer turns up on).
#: Registration changes something and finds nothing; the other two are asked
#: a question, and the answer travels with every step from where it is found.
SCRIPTS: dict[str, tuple[list[StepPresented], list[Finding], int]] = {
    "registration": (REGISTRATION_STEPS, [], 0),
    "billing": (
        from_plan(BILLING_PLAN),
        [
            Finding(label="Your bill", value=BILL_AMOUNT, values=[BILL_AMOUNT]),
            Finding(label="Due", value=BILL_DUE, values=[BILL_DUE]),
        ],
        3,
    ),
    "railways": (
        from_plan(RAILWAYS_PLAN),
        [
            Finding(label="Train", value=TRAIN, values=[TRAIN]),
            Finding(label="Journey", value=JOURNEY, values=[JOURNEY]),
        ],
        5,
    ),
}

#: Every step the mock can show, for the copy tests that hold it to the same
#: rules as a real plan (`frontend/test_copy.py`).
STEPS = [step for steps, _, _ in SCRIPTS.values() for step in steps]

app = FastAPI()


def explain(findings: list[Finding]) -> str | None:
    """The closing screen's sentence, by the backend's own rules (`voice.py`)."""
    found = {f.label: list(f.values or [f.value]) for f in findings}
    return voice.explain_trains(found, {}) or voice.explain_bill(found, {})


# The decorator belongs to `health`. From 2026-10-03 to 2026-10-05 `explain`
# sat between them and took the route, so `/` answered 422 and nothing could
# tell the mock was up: the demo recorder refused to start it, and the tests'
# fixture waited its full 30s every run.
@app.get("/")
async def health() -> dict[str, str]:
    """Same shape as the real backend's, so a launcher can poll either.

    Without this, readiness could only be inferred from a 404, which is true
    by accident rather than by statement.
    """
    return {
        "status": "ok",
        "flow": "mock",
        "router": "model" if use_model() else "keywords",
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

    async def receive(msg_type: str, step_index: int | None = None) -> dict:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            matches = msg.get("type") == msg_type and (
                step_index is None or msg.get("payload", {}).get("step_index") == step_index
            )
            if not matches:
                print(f"mock_backend: ignoring unexpected message {msg.get('type')!r}")
                continue
            return msg

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

    # Routed exactly as the real backend routes. Anything that is not a
    # request for a flow is answered, and the socket is kept for the next.
    model = configured_classifier()
    while True:
        start = (await receive("task.start")).get("payload", {})
        goal = (start.get("goal") or "").strip()
        chosen = start.get("flow")
        decided = (Route("flow", chosen, (chosen,), "chosen") if chosen in ROUTABLE
                   else await route(goal, model))
        print(f"mock_backend: routed {goal!r} -> {decided.kind} "
              f"{decided.flow or list(decided.flows)} ({decided.via})")
        if decided.kind == "flow" and decided.flow is not None:
            break
        await send("goal.answered",
                   GoalAnswered(kind=decided.kind, goal=goal, flows=list(decided.flows)))

    await play(decided.flow, goal, send, receive)
    await ws.close()


async def play(flow: str, goal: str, send, receive) -> None:
    """One flow's script, start to finish."""
    steps, findings, found_at = SCRIPTS[flow]

    # The stages by name (2026-10-14), each step in its own; the mock's steps
    # are all past the first question, so they are in the stages after it.
    stages = {"registration": voice.COURSE_STAGES, "billing": voice.BILL_STAGES,
              "railways": voice.TRIP_STAGES}[flow]
    await send("task.started", TaskStarted(goal=goal, estimated_steps=len(steps),
                                           stages=stages))
    await send("state.changed", StateChanged(state="thinking"))

    for step in steps:
        step = step.model_copy(update={"stage": min(step.step_index, len(stages) - 2)})
        # The registration demo only: one step reported as having failed and
        # been carried past, so the quiet notice can be seen without waiting
        # for a real page to break.
        if flow == "registration" and step.step_index == FAILED_BEFORE_STEP:
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
        level = LEVEL_BEFORE_STEP.get(step.step_index) if flow == "registration" else None
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
        await asyncio.sleep(0.5)
        await send("state.changed", StateChanged(state="waiting"))
        # From the step the answer is on, it travels with every step and then
        # with the ending — the same journey a real run makes.
        await send(
            "step.presented",
            step.model_copy(update={"findings": findings})
            if findings and step.step_index >= found_at
            else step,
        )
        await receive("step.response", step.step_index)

        await send("state.changed", StateChanged(state="thinking"))
        await asyncio.sleep(0.3)

    await send(
        "task.completed",
        TaskCompleted(
            summary=goal,
            duration_ms=48200,
            steps_taken=len(steps),
            llm_calls=0,
            replayed=False,
            findings=findings,
            # Built the same way the real backend builds it, from the same
            # findings, so the overlay shows what a real run would.
            explanation=explain(findings),
        ),
    )
