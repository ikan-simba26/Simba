"""SIMBA message contract, mirrored from CONTRACT.md.

Keep field names identical to shared/schema.ts and to CONTRACT.md. Additive
optional fields are fine; renames and removals require all three owners and
a version bump (see CLAUDE.md).
"""

from __future__ import annotations

from typing import Dict, Generic, List, Literal, TypeVar

from pydantic import BaseModel

# --- Shared vocab -----------------------------------------------------------

State = Literal["thinking", "acting", "waiting", "stuck"]
Level = Literal[1, 2, 3]
ActionKind = Literal["primary", "secondary", "destructive"]
InputMode = Literal["text", "voice"]

MessageType = Literal[
    # backend -> frontend
    "task.started",
    "state.changed",
    "step.presented",
    "step.failed",
    "load.updated",
    "page.preview",
    "help.requested",
    "task.completed",
    "task.failed",
    "error",
    # frontend -> backend
    "task.start",
    "step.response",
    "level.override",
    "trust.requested",
    "task.cancel",
    "telemetry",
]

# --- Backend to frontend -----------------------------------------------------


class TaskStarted(BaseModel):
    goal: str
    estimated_steps: int


class StateChanged(BaseModel):
    state: State


class StepField(BaseModel):
    id: str
    label: str
    type: str
    value: str


class StepAction(BaseModel):
    id: str
    label: str
    kind: ActionKind


class StepPresented(BaseModel):
    step_index: int
    step_total: int
    instruction: str
    detail: str
    fields: List[StepField]
    actions: List[StepAction]
    requires_confirmation: bool


class StepFailed(BaseModel):
    """A step did not work, and the run is carrying on past it.

    Emitted where the loop previously said nothing at all. A first failure is
    absorbed — the planner is told and may choose differently — and until this
    existed the frontend saw step N, then step N+1, with no way to tell a
    skipped step from a completed one. That is not a hypothetical: it is how
    the first live railways run was misdiagnosed for a day.

    Not the same thing as `error`, which is the harness failing. This is the
    task failing at something and continuing, which the user should see
    quietly rather than be alarmed by.
    """

    step_index: int
    instruction: str  # what was attempted, in the words the user was shown
    reason: str  # why it did not work
    strategies_tried: int


class LoadUpdated(BaseModel):
    score: float
    level: Level
    reason: str


class Highlight(BaseModel):
    x: int
    y: int
    w: int
    h: int


class PagePreview(BaseModel):
    screenshot: str
    highlight: Highlight
    caption: str


class HelpRequested(BaseModel):
    reason: str
    suggestion: str


class TaskCompleted(BaseModel):
    summary: str
    duration_ms: int
    steps_taken: int
    llm_calls: int
    replayed: bool


class TaskFailed(BaseModel):
    reason: str
    recoverable: bool


class ErrorPayload(BaseModel):
    code: str
    message: str


# --- Frontend to backend -----------------------------------------------------


class TaskStart(BaseModel):
    goal: str
    input_mode: InputMode


class StepResponse(BaseModel):
    step_index: int
    action_id: str
    input_values: Dict[str, str]


class LevelOverride(BaseModel):
    level: Level
    locked: bool


class TrustRequested(BaseModel):
    pass


class TaskCancel(BaseModel):
    pass


class Telemetry(BaseModel):
    step_index: int
    hesitation_ms: int
    cursor_path_ratio: float
    backtracks: int
    rereads: int
    help_presses: int


# --- Envelope ----------------------------------------------------------------

PayloadT = TypeVar("PayloadT", bound=BaseModel)


class Envelope(BaseModel, Generic[PayloadT]):
    v: Literal[1] = 1
    type: MessageType
    task_id: str
    seq: int
    ts: int
    payload: PayloadT
