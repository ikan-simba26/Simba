"""The runtime loop: perceive, act, verify, retry.

    goal -> perceive -> decide action -> render step
         -> user confirms -> act -> verify -> loop

Verification is not optional (see CLAUDE.md). Every step snapshots the page
before and after, and a step only counts as done if the page actually changed
in the way the plan expected. On a mismatch the step is retried once with a
different strategy; if that also fails, control goes back to the user via
`help.requested`. Nothing here assumes a click worked.

Load estimation is deliberately absent — no `load.updated` is emitted, since
the estimator is not built until the skeleton runs end to end.
"""

import asyncio
import json
import time
from dataclasses import dataclass

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page

from backend.orchestrator.plan import GOAL, Expectation, Operation, PlanStep, Target
from backend.perception.serializer import Element, serialize_async
from shared.schema import (
    BaseModel,
    HelpRequested,
    StateChanged,
    StepPresented,
    TaskCompleted,
    TaskFailed,
    TaskStarted,
)

VERIFY_TIMEOUT_S = 5.0


@dataclass(frozen=True)
class Snapshot:
    """Enough of the page's state to tell whether an action changed it."""

    url: str
    title: str
    labels: tuple[str, ...]


class Connection:
    """One frontend WebSocket, framed as contract envelopes."""

    def __init__(self, websocket, task_id: str) -> None:
        self._websocket = websocket
        self._task_id = task_id
        self._seq = 0

    async def send(self, message_type: str, payload: BaseModel) -> None:
        self._seq += 1
        await self._websocket.send_text(
            json.dumps(
                {
                    "v": 1,
                    "type": message_type,
                    "task_id": self._task_id,
                    "seq": self._seq,
                    "ts": int(time.time() * 1000),
                    "payload": payload.model_dump(),
                }
            )
        )

    async def receive(self, message_type: str, step_index: int | None = None) -> dict:
        while True:
            message = json.loads(await self._websocket.receive_text())
            if message.get("type") != message_type:
                continue  # unknown types are ignored, never fatal
            if step_index is not None:
                if message.get("payload", {}).get("step_index") != step_index:
                    continue
            return message


async def perceive(page: Page) -> tuple[list[Element], Snapshot]:
    elements = await serialize_async(page)
    snapshot = Snapshot(
        url=page.url,
        title=await page.title(),
        labels=tuple(element.label for element in elements),
    )
    return elements, snapshot


def pick(elements: list[Element], target: Target) -> int | None:
    """Choose an element id. This is the seat the LLM will take."""
    for element in elements:
        if element.role == target.role and element.label == target.label:
            return element.id
    return None


def resolve(page: Page, elements: list[Element], element_id: int):
    """Resolve an integer id back to something clickable."""
    element = next(e for e in elements if e.id == element_id)
    twins = [e for e in elements if e.role == element.role and e.label == element.label]
    return page.get_by_role(element.role, name=element.label, exact=True).nth(
        twins.index(element)
    )


async def act(page: Page, elements: list[Element], element_id: int, operation: Operation,
              value: str, strategy: int) -> None:
    """Perform one operation. `strategy` 1 is a different route to the same end."""
    locator = resolve(page, elements, element_id)

    if operation.kind == "fill":
        if strategy == 0:
            await locator.fill(value)
        else:
            await locator.clear()
            await locator.press_sequentially(value)
        return

    if strategy == 0:
        await locator.click()
    else:
        # Bypasses hit-testing and actionability, which is the usual reason
        # a click silently does nothing.
        await locator.evaluate("element => element.click()")


def check(before: Snapshot, after: Snapshot, expect: Expectation) -> str | None:
    """Return None if the page changed as expected, else why it did not."""
    if after == before:
        return "the page did not change at all"
    if expect.url_contains and expect.url_contains not in after.url:
        return f"expected the URL to contain {expect.url_contains!r}, got {after.url!r}"
    if expect.title_contains and expect.title_contains not in after.title:
        return f"expected the title to contain {expect.title_contains!r}, got {after.title!r}"
    if expect.label_gone and expect.label_gone in after.labels:
        return f"expected {expect.label_gone!r} to be gone from the page"
    if expect.label_present and expect.label_present not in after.labels:
        return f"expected {expect.label_present!r} to appear on the page"
    return None


async def verify(page: Page, before: Snapshot, expect: Expectation) -> str | None:
    """Poll until the page settles into the expected state, or give up."""
    deadline = time.monotonic() + VERIFY_TIMEOUT_S
    failure = "the page did not change at all"
    while time.monotonic() < deadline:
        _, after = await perceive(page)
        failure = check(before, after, expect)
        if failure is None:
            return None
        await asyncio.sleep(0.25)
    return failure


async def attempt(page: Page, step: PlanStep, input_values: dict[str, str], strategy: int,
                  before: Snapshot) -> str | None:
    """Run one step's operations, then verify. Returns None on success."""
    for operation in step.operations:
        # Perceive fresh each time: the previous operation may have navigated.
        elements, _ = await perceive(page)

        element_id = pick(elements, operation.target)
        if element_id is None:
            return f"could not find {operation.target.label!r} on the page"

        value = input_values.get(operation.value_key, "") if operation.value_key else ""
        try:
            await act(page, elements, element_id, operation, value, strategy)
        except PlaywrightError as error:
            first_line = str(error).split("\n")[0]
            return f"{operation.kind} on {operation.target.label!r} failed: {first_line}"

    return await verify(page, before, step.expect)


async def run_task(page: Page, connection: Connection, plan: list[PlanStep],
                   start_url: str) -> None:
    started = time.monotonic()
    await connection.send("task.started", TaskStarted(goal=GOAL, estimated_steps=len(plan)))

    current_state: str | None = None

    async def set_state(state: str) -> None:
        # Exactly one state is active at a time, so don't re-announce it.
        nonlocal current_state
        if state != current_state:
            current_state = state
            await connection.send("state.changed", StateChanged(state=state))

    await set_state("thinking")
    await page.goto(start_url)

    for index, step in enumerate(plan, start=1):
        await set_state("thinking")
        _, before = await perceive(page)

        await set_state("waiting")
        await connection.send(
            "step.presented",
            StepPresented(
                step_index=index,
                step_total=len(plan),
                instruction=step.instruction,
                detail=step.detail,
                fields=step.fields,
                actions=step.actions,
                requires_confirmation=True,
            ),
        )
        response = await connection.receive("step.response", step_index=index)
        payload = response.get("payload", {})

        if payload.get("action_id") != "confirm":
            await connection.send(
                "task.failed",
                TaskFailed(reason="The user chose not to continue.", recoverable=True),
            )
            return

        await set_state("acting")
        input_values = payload.get("input_values", {})

        failure = await attempt(page, step, input_values, strategy=0, before=before)
        if failure is not None:
            # Re-perceive: the failed attempt may have changed the page anyway.
            _, before = await perceive(page)
            failure = await attempt(page, step, input_values, strategy=1, before=before)

        if failure is not None:
            await set_state("stuck")
            await connection.send(
                "help.requested",
                HelpRequested(
                    reason=f"Step {index} did not work: {failure}",
                    suggestion="Can you do this step for me? I'll carry on from there.",
                ),
            )
            return

    await connection.send(
        "task.completed",
        TaskCompleted(
            summary=f"Registered for CS-401. {page.url}",
            duration_ms=int((time.monotonic() - started) * 1000),
            steps_taken=len(plan),
            llm_calls=0,
            replayed=False,
        ),
    )
