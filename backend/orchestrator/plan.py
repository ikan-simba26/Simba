"""The hardcoded registration plan.

September's walking skeleton has no LLM (see CLAUDE.md). This module stands
in for one: it decides, ahead of time, which element to act on at each step
and what the page should look like afterwards. When the LLM arrives it
replaces `Target` matching with a model call — everything downstream, the
integer ids and the verification, stays the same.
"""

from dataclasses import dataclass, field
from typing import Literal

from shared.schema import StepAction, StepField

GOAL = "Register for CS-401"


@dataclass(frozen=True)
class Target:
    """What the planner is looking for, in accessibility-tree terms."""

    role: str
    label: str


@dataclass(frozen=True)
class Operation:
    """One thing to do to one element.

    `press` sends a key — "ArrowDown", "Enter", "Escape", "Control+a". It is
    here because several real widgets have no other way through: a combobox
    whose options are `li`s with no role can be driven by the keyboard even
    when clicking is awkward, and a value the mouse cannot commit sometimes
    commits on Enter. `value` carries the key name.

    Additive: nothing crosses the frontend boundary that changed, so
    `CONTRACT.md` and both schema files are untouched.
    """

    kind: Literal["fill", "click", "select", "press"]
    target: Target
    value_key: str | None = None  # which step.response input_value to type
    # A planner that already knows the id (the LLM does) sets it here; one
    # that matches by role and label (the hardcoded plan) leaves it None.
    element_id: int | None = None
    value: str | None = None


@dataclass(frozen=True)
class Expectation:
    """What must be true of the page after a step, for it to count as done.

    The first four ask about the page's *chrome* — where you are and what you
    can press. They are all a single-page app leaves you, and for a task whose
    goal is to read something they are not enough: the railways search finishes
    without the URL, the title or a single interactive label changing, so
    nothing in this class could describe its success and `success` was left
    `None` outright.

    The last two ask about what the page *says*, which is what such a task was
    always actually about.
    """

    url_contains: str | None = None
    title_contains: str | None = None
    label_gone: str | None = None
    label_present: str | None = None
    # Readable content, from perception's second channel.
    content_says: str | None = None
    rows_at_least: int | None = None


@dataclass(frozen=True)
class PlanStep:
    instruction: str
    detail: str
    operations: list[Operation]
    expect: Expectation
    fields: list[StepField] = field(default_factory=list)
    actions: list[StepAction] = field(default_factory=list)


def _confirm(label: str) -> list[StepAction]:
    return [
        StepAction(id="confirm", label=label, kind="primary"),
        StepAction(id="cancel", label="Not now", kind="secondary"),
    ]


REGISTRATION_PLAN: list[PlanStep] = [
    PlanStep(
        instruction="Sign in to the course portal.",
        detail="Fictional State University student portal.",
        fields=[
            StepField(id="username", label="Student ID or Username", type="text", value=""),
            StepField(id="password", label="Password", type="password", value=""),
        ],
        actions=_confirm("Sign in"),
        operations=[
            Operation("fill", Target("textbox", "Student ID or Username"), "username"),
            Operation("fill", Target("textbox", "Password"), "password"),
            Operation("click", Target("button", "Sign In")),
        ],
        expect=Expectation(url_contains="/courses"),
    ),
    PlanStep(
        instruction="Close the registration alert.",
        detail="The portal opened a notice about the add/drop deadline.",
        actions=_confirm("Close it"),
        operations=[Operation("click", Target("button", "Close"))],
        expect=Expectation(label_gone="Close"),
    ),
    PlanStep(
        instruction="Register for CS-401, Advanced Widget Design.",
        detail="3 credit hours. MWF 10:00-10:50, Dr. Aslam, SCI 214.",
        actions=_confirm("Register for CS-401"),
        operations=[Operation("click", Target("button", "Register for CS-401"))],
        expect=Expectation(url_contains="/register", title_contains="Registration Confirmed"),
    ),
]


class HardcodedPlanner:
    """Walks REGISTRATION_PLAN. The deterministic A/B arm and demo fallback."""

    calls_made = 0
    stuck_reason: str | None = None

    def __init__(self, steps: list[PlanStep]) -> None:
        self._steps = list(steps)
        self._index = 0

    async def next_move(self, elements, history, setback):
        from backend.orchestrator.loop import Move

        if self._index >= len(self._steps):
            return None

        step = self._steps[self._index]
        self._index += 1
        return Move(
            instruction=step.instruction,
            detail=step.detail,
            operations=step.operations,
            expect=step.expect,
            fields=step.fields,
            actions=step.actions,
        )
