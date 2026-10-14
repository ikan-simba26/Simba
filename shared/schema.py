"""SIMBA message contract, mirrored from CONTRACT.md.

Keep field names identical to shared/schema.ts and to CONTRACT.md. Additive
optional fields are fine; renames and removals require all three owners and
a version bump (see CLAUDE.md).
"""

from __future__ import annotations

from typing import Dict, Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel

# --- Shared vocab -----------------------------------------------------------

State = Literal["thinking", "acting", "waiting", "stuck"]
Level = Literal[1, 2, 3]
ActionKind = Literal["primary", "secondary", "destructive"]
InputMode = Literal["text", "voice"]
# What a step is about, for the icon beside it (2026-10-07).
StepKind = Literal["date", "place", "choose", "type", "read", "confirm"]

MessageType = Literal[
    # backend -> frontend
    "task.started",
    "state.changed",
    "history.offered",
    "goal.answered",
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
    # Additive and optional (2026-10-14). The task's stages by name — trains:
    # From, To, Day, Search, Trains — shown in place of a count. Fixed for the
    # task: a question asked again stays in its stage. Empty: no stages shown.
    stages: List[str] = []


class StateChanged(BaseModel):
    state: State


class PastGoal(BaseModel):
    """Something this person asked for before, and where they asked it."""

    goal: str
    site: str


class HistoryOffered(BaseModel):
    """What the home screen offers instead of an empty box.

    Sent once, when the socket opens, before any task. A frontend that ignores
    it sees exactly what it saw before.
    """

    goals: List[PastGoal]


FlowName = Literal["registration", "billing", "railways"]
AnswerKind = Literal["greeting", "unsupported", "clarify"]


class GoalAnswered(BaseModel):
    """A typed goal that did not start a task, and what to offer instead.

    Added 2026-09-21, pending ratification (CONTRACT.md). Carries no words:
    the overlay writes every sentence from `copy.ts`, so the mock and the
    backend cannot disagree about what the person reads.
    """

    kind: AnswerKind
    goal: str
    flows: List[FlowName]


class Finding(BaseModel):
    """A value the task was looking for, and the name to show it under.

    `label` is for a person to read, not the page's own column heading: the
    billing replica calls the amount `P/WITHIN`, and nobody outside a billing
    department knows what that means. The plan supplies the readable name.

    Two forms of the same answer, because two screens want different things:

      * `value` is one line. A results table has a row per result, so it is
        the values joined, and past four it counts the rest — the step screen
        shows a finding while the run is still going, in large type, beside
        the instruction, and twenty values there is clutter.
      * `values` is every one of them, in the order the page listed them. The
        closing screen is the answer and shows them all.

    `values` is optional and additive: a sender that does not set it is read
    as `[value]`, which is what every finding was before 2026-09-19.

    `values` drops a repeated value, so two findings' lists cannot be paired by
    position. `rows`, on the first finding of a message only, is every result
    whole: one cell per finding in that message, in their order, repeats kept,
    "" where the page's row had nothing. Optional and additive (2026-10-05);
    empty when the values did not come from a table.
    """

    label: str
    value: str
    values: List[str] = []
    rows: List[List[str]] = []


class StepField(BaseModel):
    id: str
    label: str
    type: str
    value: str
    # Additive and optional (2026-10-06). The answers a field accepts, when
    # they are a known list — the site's own stations, read before anything
    # on it is touched. The overlay shows the ones that match what has been
    # typed so far. Empty means any text.
    options: List[str] = []


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
    # What has been found so far, if the task was looking for anything.
    # Additive and optional: a task that reads nothing sends an empty list.
    findings: List[Finding] = []
    # Additive and optional (2026-10-07). What kind of thing the step is
    # about, so the overlay can put one plain icon beside it. Absent: no icon.
    step_kind: Optional[StepKind] = None
    # Additive and optional (2026-10-14). Which of `task.started.stages` this
    # step is in, by position. Absent: the stage before it.
    stage: Optional[int] = None
    # Additive and optional (2026-10-14). What was wrong with the last answer,
    # in one kind sentence, beside the question asked again — "I couldn't find
    # a station called Narnia." The overlay clears it once a valid answer is
    # chosen. Absent: nothing was wrong.
    note: Optional[str] = None


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
    # The answer, when the task had one. A run that ends without saying what
    # it found has not finished from the user's side of the screen.
    findings: List[Finding] = []
    # One plain sentence above the result, saying what it means — "There are
    # 3 trains. The fastest takes 6 hours 3 minutes." Built by the backend
    # only from values the page returned (`voice.explain_*`). Optional and
    # additive (2026-10-03): absent when there is nothing it can say safely.
    explanation: Optional[str] = None


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
    # Additive and optional (2026-09-21). Set when the person chose a flow by
    # pressing a card or answering "which did you mean", so the backend runs
    # exactly that rather than classifying the goal again.
    flow: Optional[FlowName] = None
    # Additive and optional (2026-10-14). The person's own setting: ask before
    # every move, as SIMBA always did, rather than running the safe ones as a
    # checklist. Absent: the checklist.
    confirm_each: bool = False


class StepResponse(BaseModel):
    step_index: int
    action_id: str
    input_values: Dict[str, str]


class LevelOverride(BaseModel):
    level: Level
    locked: bool
    # Additive and optional (2026-09-25). Who moved the level: the person, or
    # the overlay's guard because a step did not fit. A guard move never
    # becomes the lock. A sender that omits it means the person.
    by: Literal["person", "overflow"] = "person"


class TrustRequested(BaseModel):
    pass


class TaskCancel(BaseModel):
    pass


class Telemetry(BaseModel):
    """Channel B: how the person is getting on with the step on screen.

    Sent on every step response and on a timer while one waits. `answered`
    tells the two apart — additive and optional (added 2026-09-20), so a
    sender that omits it is read as a timer sample.
    """

    step_index: int
    hesitation_ms: int
    cursor_path_ratio: float
    backtracks: int
    rereads: int
    help_presses: int
    answered: bool = False


# --- Envelope ----------------------------------------------------------------

PayloadT = TypeVar("PayloadT", bound=BaseModel)


class Envelope(BaseModel, Generic[PayloadT]):
    v: Literal[1] = 1
    type: MessageType
    task_id: str
    seq: int
    ts: int
    payload: PayloadT
