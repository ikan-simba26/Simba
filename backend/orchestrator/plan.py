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
    kind: Literal["fill", "click"]
    target: Target
    value_key: str | None = None  # which step.response input_value to type


@dataclass(frozen=True)
class Expectation:
    """What must be true of the page after a step, for it to count as done."""

    url_contains: str | None = None
    title_contains: str | None = None
    label_gone: str | None = None
    label_present: str | None = None


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
