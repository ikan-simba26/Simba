"""The runtime loop, planned one action at a time by the LLM.

Same shape as the hardcoded loop — perceive, decide, present, act, verify —
but the decision comes from a model instead of `plan.py`. The model sees the
serialized page and the goal, and answers with an integer element id. It
never sees a selector, and it never sees a credential: values for named
fields come from the vault after the model has chosen, and a password field
is never filled from anything the model wrote.

The model has no "done" verb, by design — its schema is only click/type/
select — so completion is decided here, by checking the goal's success
condition against the page after every step.
"""

import time
from dataclasses import dataclass

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page

from backend.orchestrator.llm import Action, LLMError, Provider
from backend.orchestrator.loop import (
    Connection,
    mismatch,
    perceive,
    resolve,
    satisfies,
    verify,
)
from backend.orchestrator.plan import Expectation
from backend.perception.serializer import Element
from shared.schema import (
    HelpRequested,
    StateChanged,
    StepAction,
    StepField,
    StepPresented,
    TaskCompleted,
    TaskFailed,
    TaskStarted,
)

MAX_STEPS = 10

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
- If a dialog or overlay is covering the page, dismiss it before anything else.
- Keep reasoning to one short sentence, phrased for the person you are helping.
"""


@dataclass(frozen=True)
class Goal:
    text: str
    success: Expectation
    estimated_steps: int


REGISTRATION_GOAL = Goal(
    text="Register for the course CS-401.",
    success=Expectation(url_contains="/register", title_contains="Registration Confirmed"),
    estimated_steps=4,
)


def render_page(elements: list[Element]) -> str:
    """The page as the model sees it: ids, roles, labels. Never values."""
    lines = []
    for element in elements:
        line = f"{element.id}. {element.role} {element.label!r}"
        if element.input_type:
            line += f" [input type={element.input_type}]"
        lines.append(line)
    return "\n".join(lines)


async def plan_next(
    provider: Provider, goal: Goal, elements: list[Element]
) -> tuple[Action | None, str | None]:
    """Ask for one action, retrying once with the error fed back."""
    feedback: str | None = None
    valid_ids = {element.id for element in elements}

    for _ in range(2):
        try:
            action = await provider.decide(
                SYSTEM_PROMPT, render_page(elements), goal.text, feedback
            )
        except LLMError as error:
            feedback = str(error)
            continue

        if action.element_id not in valid_ids:
            feedback = (
                f"element_id {action.element_id} is not on the page. "
                f"Valid ids are 1 to {len(elements)}."
            )
            continue

        return action, None

    return None, feedback


def value_for(
    element: Element, action: Action, vault: dict[str, str]
) -> tuple[str | None, str | None]:
    """Decide what to type. Returns (value, refusal). Vault beats the model."""
    if element.name and element.name in vault:
        return vault[element.name], None
    if element.is_password:
        return None, "no vault value for this password field, and the model may not invent one"
    return action.value or "", None


def describe(action: Action, element: Element) -> str:
    """The action as a sentence for the person being helped."""
    label = element.label or f"element {element.id}"
    if action.action == "type":
        return f"Fill in {label}."
    if action.action == "select":
        return f"Choose an option in {label}."
    return f"Click {label}."


async def apply(
    page: Page, elements: list[Element], element: Element, action: Action, value: str
) -> None:
    locator = resolve(page, elements, element.id)
    if action.action == "type":
        await locator.fill(value)
    elif action.action == "select":
        await locator.select_option(value)
    else:
        await locator.click()


async def verify_typed(
    page: Page, elements: list[Element], element: Element, expected: str
) -> str | None:
    """A typed value is verified by reading it back, not by assuming."""
    actual = await resolve(page, elements, element.id).input_value()
    if actual == expected:
        return None
    if element.is_password:
        # Never put a secret, or a near-miss of one, into a message or log.
        return "the password field did not take the value"
    return f"expected the field to hold {expected!r}, it holds {actual!r}"


async def run_task_llm(
    page: Page,
    connection: Connection,
    provider: Provider,
    goal: Goal,
    start_url: str,
) -> None:
    started = time.monotonic()
    llm_calls = 0
    steps_taken = 0
    current_state: str | None = None

    async def set_state(state: str) -> None:
        nonlocal current_state
        if state != current_state:
            current_state = state
            await connection.send("state.changed", StateChanged(state=state))

    async def give_up(reason: str) -> None:
        await set_state("stuck")
        await connection.send(
            "help.requested",
            HelpRequested(
                reason=reason,
                suggestion="Can you take it from here? I'll carry on afterwards.",
            ),
        )

    await connection.send(
        "task.started", TaskStarted(goal=goal.text, estimated_steps=goal.estimated_steps)
    )

    await set_state("thinking")
    await page.goto(start_url)

    for _ in range(MAX_STEPS):
        elements, before = await perceive(page)

        if satisfies(before, goal.success):
            break

        await set_state("thinking")
        action, failure = await plan_next(provider, goal, elements)
        llm_calls += 1 if failure is None else 2

        if action is None:
            await give_up(f"I could not work out the next step: {failure}")
            return

        element = next(e for e in elements if e.id == action.element_id)

        fields = (
            [StepField(id=element.name or str(element.id), label=element.label,
                       type=element.input_type or "text", value="")]
            if action.action == "type" and not element.is_password
            else []
        )

        steps_taken += 1
        await set_state("waiting")
        await connection.send(
            "step.presented",
            StepPresented(
                step_index=steps_taken,
                step_total=max(goal.estimated_steps, steps_taken),
                instruction=describe(action, element),
                detail=action.reasoning,
                fields=fields,
                actions=[
                    StepAction(id="confirm", label="Yes, do that", kind="primary"),
                    StepAction(id="cancel", label="Not now", kind="secondary"),
                ],
                requires_confirmation=True,
            ),
        )
        response = await connection.receive("step.response", step_index=steps_taken)
        payload = response.get("payload", {})

        if payload.get("action_id") != "confirm":
            await connection.send(
                "task.failed",
                TaskFailed(reason="The user chose not to continue.", recoverable=True),
            )
            return

        # The user's values win over anything the model wrote.
        value, refusal = value_for(element, action, payload.get("input_values", {}))
        if refusal is not None:
            await give_up(f"I stopped before filling {element.label!r}: {refusal}")
            return

        await set_state("acting")
        try:
            await apply(page, elements, element, action, value or "")
        except PlaywrightError as error:
            await give_up(f"{action.action} on {element.label!r} failed: "
                          f"{str(error).splitlines()[0]}")
            return

        if action.action == "type":
            failure = await verify_typed(page, elements, element, value or "")
        else:
            failure = await verify(page, before, Expectation())

        if failure is not None:
            await give_up(f"{describe(action, element)} did not work: {failure}")
            return

    _, final = await perceive(page)
    if not satisfies(final, goal.success):
        await give_up(f"I ran out of steps before finishing. {mismatch(final, goal.success)}")
        return

    await connection.send(
        "task.completed",
        TaskCompleted(
            summary=f"Registered for CS-401. {page.url}",
            duration_ms=int((time.monotonic() - started) * 1000),
            steps_taken=steps_taken,
            llm_calls=llm_calls,
            replayed=False,
        ),
    )


