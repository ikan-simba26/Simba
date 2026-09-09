"""The LLM planner.

This module decides *which* action comes next and nothing else. Presenting,
acting, verifying, retrying and giving up all live in `loop.py` and are the
same code the hardcoded planner runs, so an A/B between the two compares
planning and only planning.

The model never sees a selector — it answers with an integer element id from
the list it was shown — and it never sees a credential: the page it is given
carries labels, never values, and vault values are substituted at execution
time by `loop.resolve_value`.

Its schema has no "done" verb, by design, so completion is decided by the
task's success condition rather than by the model claiming to be finished.
"""

from dataclasses import dataclass

from backend.orchestrator.llm import Action, LLMError, Provider
from backend.orchestrator.loop import Move, Task
from backend.orchestrator.plan import Expectation, Operation, Target
from backend.perception.serializer import Element
from shared.schema import StepAction, StepField

SYSTEM_PROMPT = """You operate a web page on behalf of someone who finds \
cluttered interfaces overwhelming.

You are given a goal and a numbered list of the page's interactive elements. \
Choose the single next action that makes progress toward the goal.

Rules:
- Answer with an element_id taken from the list. Never write a CSS selector, \
an XPath, or element text as the id.
- One action at a time. Do not plan ahead in the answer.
- Use "type" for text fields, "click" for buttons and links, "select" for \
dropdowns.
- For a password or username field, set value to null. Those are filled from \
the user's vault, not by you.
- If any element is marked OVERLAY, something is covering the page. Dismiss \
it first, using one of the OVERLAY elements, before anything else. Nothing \
marked OCCLUDED can be clicked until you do.
- Never choose an element marked OCCLUDED.
- Never choose an element marked "dead link" — it goes nowhere and wastes a \
step.
- When the goal needs the user signed in, fill the sign-in fields on this page \
rather than navigating. Prefer form fields and buttons over navigation links.
- Keep reasoning to one short sentence, phrased for the person you are helping.
"""

REGISTRATION_TASK = Task(
    goal="Register for the course CS-401.",
    estimated_steps=4,
    success=Expectation(url_contains="/register", title_contains="Registration Confirmed"),
)


@dataclass(frozen=True)
class _Choice:
    action: Action
    element: Element


def render_page(elements: list[Element]) -> str:
    """The page as the model sees it: ids, roles, labels. Never values.

    Perception's structural flags are spelled out rather than left implicit.
    A model cannot infer from a list of sixty buttons that one of them belongs
    to a modal covering the rest — nor that six of them appeared a moment ago
    because someone started typing, and are the only way to commit a choice.
    """
    blocked = any(element.overlay for element in elements)
    choices = [e for e in elements if e.inferred and e.role == "option"]

    lines = []
    if blocked:
        lines += [
            "AN OVERLAY IS COVERING THE PAGE. Everything marked OCCLUDED is "
            "unreachable until it is dismissed, using an OVERLAY element.",
            "",
        ]
    if choices:
        # A banner, not a rule in the list. The same move the OVERLAY case
        # makes, for the same reason and on the same evidence: told as one
        # rule among nine, a model reads it and proceeds anyway. The first
        # live LLM run was shown `option 'LAHORE CANTT'` and the rule saying
        # to click it, and typed into the next field instead — because from
        # where it sits, having typed the station name, the field is done.
        # The page disagrees, and says so only by silently emptying it.
        lines += [
            f"A LIST OF CHOICES IS OPEN, with {len(choices)} option(s) marked "
            "INFERRED below. Nothing is chosen yet. Typing the text is not "
            "choosing: click the option you want NOW, before touching any "
            "other field, or what you typed will be discarded.",
            "",
        ]

    for element in elements:
        line = f"{element.id}. {element.role} {element.label!r}"
        if element.qualifier:
            # Without this a month grid offers two elements called '30' and
            # nothing to choose between them.
            line += f" ({element.qualifier})"
        if element.input_type:
            line += f" [input type={element.input_type}]"
        if element.overlay:
            line += "  <- OVERLAY"
        if element.occluded:
            line += "  <- OCCLUDED, cannot be clicked"
        if element.dead_link:
            line += "  <- dead link, goes nowhere"
        if element.inferred:
            # Say that the role is a guess. The model is choosing partly on
            # the strength of the role word, and "option" read from the page
            # and "option" worked out from a mouse cursor are not the same
            # claim. Collapsing them would hide the uncertainty in exactly
            # the place it matters.
            line += "  <- INFERRED (role worked out from layout, not declared)"
        lines.append(line)
    return "\n".join(lines)


def describe(action: Action, element: Element) -> str:
    """The action as a sentence for the person being helped."""
    label = element.label or f"element {element.id}"
    if action.action == "type":
        return f"Fill in {label}."
    if action.action == "select":
        return f"Choose an option in {label}."
    return f"Click {label}."


class LLMPlanner:
    """Asks the model for one action and shapes it into a Move."""

    def __init__(self, provider: Provider, task: Task) -> None:
        self._provider = provider
        self._task = task
        self.calls_made = 0
        self.stuck_reason: str | None = None

    async def next_move(
        self, elements: list[Element], history: list[str], setback: str | None
    ) -> Move | None:
        choice = await self._choose(elements, history, setback)
        if choice is None:
            return None

        action, element = choice.action, choice.element
        operation = Operation(
            kind="fill" if action.action == "type" else action.action,
            target=Target(role=element.role, label=element.label),
            element_id=element.id,
            value=action.value,
        )

        # Only offer a field when the user could reasonably fill it. A password
        # is never round-tripped through the step, it comes from the vault.
        fields = (
            [
                StepField(
                    id=element.name or str(element.id),
                    label=element.label,
                    type=element.input_type or "text",
                    value="",
                )
            ]
            if action.action == "type" and not element.is_password
            else []
        )

        return Move(
            instruction=describe(action, element),
            detail=action.reasoning,
            operations=[operation],
            # The model declares no expectation, so the bar is the general one:
            # the page must actually have changed. A typed value is checked by
            # reading the field back, in loop.attempt_move.
            expect=Expectation(),
            fields=fields,
            actions=[
                StepAction(id="confirm", label="Yes, do that", kind="primary"),
                StepAction(id="cancel", label="Not now", kind="secondary"),
            ],
        )

    async def _choose(
        self, elements: list[Element], history: list[str], setback: str | None
    ) -> _Choice | None:
        """One action, retried once with the specific error fed back."""
        feedback = setback
        valid = {element.id: element for element in elements}

        for _ in range(2):
            self.calls_made += 1
            try:
                action = await self._provider.decide(
                    SYSTEM_PROMPT, render_page(elements), self._task.goal, feedback, history
                )
            except LLMError as error:
                feedback = str(error)
                continue

            if action.element_id not in valid:
                feedback = (
                    f"element_id {action.element_id} is not on the page. "
                    f"Valid ids are 1 to {len(elements)}."
                )
                continue

            return _Choice(action=action, element=valid[action.element_id])

        self.stuck_reason = f"I could not work out the next step: {feedback}"
        return None
