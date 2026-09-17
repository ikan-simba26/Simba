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
    # Narrows a match when the label alone is ambiguous.
    #
    # `None` means the qualifier is not part of the match, which is what
    # almost every target wants. A string means it must match exactly — and
    # `""` is a real value, not a synonym for None: it means "the one with no
    # qualifier at all". That is the distinction a calendar needs. A month
    # grid has two cells labelled `30`, one of them the previous month's;
    # `Target("option", "30", qualifier="")` is the way to say the one in the
    # month on screen.
    qualifier: str | None = None


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
class FieldValue:
    """A field on the page, and what it has to hold.

    `equals` is what the **page shows**, not what was typed. Those come apart
    on exactly the widgets this matters for: the live railways picker accepts
    `2026-10-15` and commits it as `15-10-2026`, and a plan that asserted the
    typed string would fail the moment the value became real.
    """

    label: str
    equals: str


@dataclass(frozen=True)
class Answer:
    """Something the goal asks to find out, and what to call it on screen.

    `name` is for a person to read. `reads` is the label the page's own
    content uses for the value — the billing replica heads its amount column
    `P/WITHIN`, which means nothing outside a billing department, so the name
    and the place it is read from are necessarily two different strings.
    """

    name: str
    reads: str


@dataclass(frozen=True)
class About:
    """What a task is about, declared once.

    Two halves, because a goal does two things with values. It *names* some
    ("on 2026-10-15") and it *asks for* some ("which trains?").

    `holds` is the first: each named value, as the page shows it once it is
    really set. Every one is checked whenever the run decides it has finished,
    in addition to the task's `success` expectation, and a run that ends with
    one of them wrong ends in `help.requested` rather than `task.completed`.
    Nobody has to also remember to write it into `success`.

    It exists because of a specific failure. The railways task's success was
    `rows_at_least=1`, the run searched for the wrong date, two real trains
    came back, and it reported `task.completed` — a well-formed answer to a
    question nobody asked. The results table has no date column, so the only
    place the date appears is the field the user watched being filled
    (EVALUATION.md, case 6).

    `finds` is the second: read from the content channel along the way,
    remembered, and sent to the screen as `findings`.

    These used to be two unrelated declarations — `Task.answers`, and
    `Expectation.value_is` inside a task's success condition — and a plan
    author had to remember both, separately, with nothing to say either had
    been forgotten. One declaration makes "what is this task about?" a single
    question, and `Task` requires it to be answered: `About()` is allowed, but
    it has to be written down.

    A limit worth knowing: a held value is checked on the *final* page. A
    field the run has navigated away from is not there to be checked, so a
    value typed on one page of a multi-page flow — the billing reference
    number — cannot be a `holds` entry. That case still has no check.
    """

    holds: tuple[FieldValue, ...] = ()
    finds: tuple[Answer, ...] = ()


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

    What a *field* must hold is not here. It was, as `value_is`, from
    2026-09-09 to 2026-09-17; it is now `About.holds`, so the values a goal
    names are declared in the same place as the values it asks for.
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
        instruction="Let me sign you in first.",
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
        instruction="The portal opened a notice. I’ll close it.",
        detail="The portal opened a notice about the add/drop deadline.",
        actions=_confirm("Close it"),
        operations=[Operation("click", Target("button", "Close"))],
        expect=Expectation(label_gone="Close"),
    ),
    PlanStep(
        instruction="Ready to book your place on CS-401.",
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
