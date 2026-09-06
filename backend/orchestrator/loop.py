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
import base64
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page

from backend.orchestrator.plan import Expectation, Operation, Target
from backend.perception.serializer import Element, serialize_async
from shared.envelope import envelope
from shared.schema import (
    BaseModel,
    HelpRequested,
    Highlight,
    PagePreview,
    StateChanged,
    StepAction,
    StepField,
    ErrorPayload,
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
            json.dumps(envelope(message_type, self._task_id, self._seq, payload))
        )

    async def receive(
        self,
        message_type: str,
        step_index: int | None = None,
        on_other: Callable[[dict], Awaitable[None]] | None = None,
    ) -> dict:
        while True:
            message = json.loads(await self._websocket.receive_text())
            if message.get("type") != message_type:
                # Not what we are waiting for, but not necessarily noise: the
                # user can ask what is happening while a step is on screen.
                if on_other is not None:
                    await on_other(message)
                continue
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


def mismatch(after: Snapshot, expect: Expectation) -> str | None:
    """Return None if this page satisfies the expectation, else why it doesn't."""
    if expect.url_contains and expect.url_contains not in after.url:
        return f"expected the URL to contain {expect.url_contains!r}, got {after.url!r}"
    if expect.title_contains and expect.title_contains not in after.title:
        return f"expected the title to contain {expect.title_contains!r}, got {after.title!r}"
    if expect.label_gone and expect.label_gone in after.labels:
        return f"expected {expect.label_gone!r} to be gone from the page"
    if expect.label_present and expect.label_present not in after.labels:
        return f"expected {expect.label_present!r} to appear on the page"
    return None


def satisfies(after: Snapshot, expect: Expectation) -> bool:
    """Whether a page is already in the expected state, change or no change."""
    return mismatch(after, expect) is None


def check(before: Snapshot, after: Snapshot, expect: Expectation) -> str | None:
    """Return None if the page changed as expected, else why it did not."""
    if after == before:
        return "the page did not change at all"
    return mismatch(after, expect)


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


# --- one execution and recovery path, shared by every planner ----------------


@dataclass(frozen=True)
class Move:
    """One unit of work: what to show the user, what to do, what must follow.

    Both planners produce these. Everything downstream — presenting, acting,
    verifying, retrying, giving up — is the same code for both, so the only
    thing that differs between a hardcoded plan and an LLM is which Move comes
    next.
    """

    instruction: str
    detail: str
    operations: list[Operation]
    expect: Expectation
    fields: list[StepField]
    actions: list[StepAction]


class Planner(Protocol):
    calls_made: int

    async def next_move(
        self, elements: list[Element], history: list[str], setback: str | None
    ) -> Move | None:
        """The next Move, or None when there is nothing left to do."""
        ...


@dataclass(frozen=True)
class Task:
    goal: str
    estimated_steps: int
    success: Expectation | None = None


MAX_STEPS = 12


def caption_for(move: "Move") -> str:
    """Plain words for what is about to happen. Never the value being typed."""
    operation = move.operations[0] if move.operations else None
    if operation is None:
        return move.instruction
    where = operation.target.label or "this"
    if operation.kind == "fill":
        return f"I'm about to type your {where} in here."
    if operation.kind == "select":
        return f"I'm about to choose an option in {where}."
    return f"I'm about to click {where}."


async def send_preview(page: Page, connection: Connection, move: "Move | None") -> None:
    """Answer trust.requested: a picture of the real page, and what is next.

    The site view is covered rather than hidden precisely so this works — a
    view Chromium believes is invisible stops repainting and the capture
    times out about half the time (CLAUDE.md, architecture constraints).
    """
    highlight = Highlight(x=0, y=0, w=0, h=0)
    caption = "This is the page I'm working on."

    if move is not None and move.operations:
        caption = caption_for(move)
        elements, _ = await perceive(page)
        operation = move.operations[0]
        element_id = (
            operation.element_id
            if operation.element_id is not None
            else pick(elements, operation.target)
        )
        if element_id is not None and any(e.id == element_id for e in elements):
            try:
                box = await resolve(page, elements, element_id).bounding_box()
            except PlaywrightError:
                box = None
            if box:
                highlight = Highlight(
                    x=int(box["x"]), y=int(box["y"]),
                    w=int(box["width"]), h=int(box["height"]),
                )

    try:
        shot = await page.screenshot()
    except PlaywrightError as error:
        await connection.send(
            "error",
            ErrorPayload(code="PREVIEW_FAILED", message=str(error).splitlines()[0]),
        )
        return

    await connection.send(
        "page.preview",
        PagePreview(
            screenshot=base64.b64encode(shot).decode("ascii"),
            highlight=highlight,
            caption=caption,
        ),
    )


async def run_task(
    page: Page,
    connection: Connection,
    planner: Planner,
    task: Task,
    start_url: str,
) -> None:
    """Perceive, decide, present, act, verify, recover. Planner-agnostic."""
    started = time.monotonic()
    current_state: str | None = None
    history: list[str] = []
    setback: str | None = None
    consecutive_setbacks = 0
    steps_taken = 0
    last_failure: str | None = None
    completed: list[Move] = []

    async def set_state(state: str) -> None:
        # Exactly one state is active at a time, so don't re-announce it.
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
        "task.started", TaskStarted(goal=task.goal, estimated_steps=task.estimated_steps)
    )
    await set_state("thinking")
    await page.goto(start_url)

    for _ in range(MAX_STEPS):
        await set_state("thinking")
        elements, before = await perceive(page)

        if task.success is not None and satisfies(before, task.success):
            break

        move = await planner.next_move(elements, history, setback)
        setback = None

        if move is None:
            reason = getattr(planner, "stuck_reason", None)
            if reason:
                await give_up(reason)
                return
            break

        steps_taken += 1
        await set_state("waiting")
        await connection.send(
            "step.presented",
            StepPresented(
                step_index=steps_taken,
                step_total=max(task.estimated_steps, steps_taken),
                instruction=move.instruction,
                detail=move.detail,
                fields=move.fields,
                actions=move.actions,
                requires_confirmation=True,
            ),
        )
        async def answer_questions(message: dict) -> None:
            if message.get("type") == "trust.requested":
                await send_preview(page, connection, move)

        response = await connection.receive(
            "step.response", step_index=steps_taken, on_other=answer_questions
        )
        payload = response.get("payload", {})

        if payload.get("action_id") != "confirm":
            await connection.send(
                "task.failed",
                TaskFailed(reason="The user chose not to continue.", recoverable=True),
            )
            return

        await set_state("acting")
        input_values = payload.get("input_values", {})

        # The retry: same move, different strategy. Identical for every planner.
        failure = await attempt_move(page, move, input_values, strategy=0, before=before)
        if failure is not None:
            _, before_retry = await perceive(page)
            failure = await attempt_move(page, move, input_values, 1, before_retry)

        if failure is not None:
            consecutive_setbacks += 1
            if consecutive_setbacks >= 2:
                await give_up(f"{move.instruction} did not work: {failure}")
                return
            # Tell the planner what went wrong; it may choose differently.
            last_failure = f"{move.instruction} did not work: {failure}"
            setback = (
                f"Your last choice — {move.instruction} — did not work: {failure}. "
                f"Something may be covering the page. Choose a different action."
            )
            continue

        consecutive_setbacks = 0
        last_failure = None
        completed.append(move)
        history.append(move.instruction)

    _, final = await perceive(page)
    if task.success is not None and not satisfies(final, task.success):
        # Prefer the concrete reason the last move failed over the generic
        # "ran out of steps", which says nothing a user could act on.
        await give_up(
            last_failure
            or f"I ran out of steps before finishing. {mismatch(final, task.success)}"
        )
        return

    # A planner that remembers runs gets told what actually worked.
    remember = getattr(planner, "finished", None)
    if remember is not None:
        remember(completed)

    await connection.send(
        "task.completed",
        TaskCompleted(
            summary=f"{task.goal} {page.url}",
            duration_ms=int((time.monotonic() - started) * 1000),
            steps_taken=steps_taken,
            llm_calls=getattr(planner, "calls_made", 0),
            replayed=getattr(planner, "replayed_steps", 0) > 0,
        ),
    )


async def attempt_move(
    page: Page, move: Move, input_values: dict[str, str], strategy: int, before: Snapshot
) -> str | None:
    """Run a Move's operations, then verify. None on success."""
    for operation in move.operations:
        # Perceive fresh each time: the previous operation may have navigated.
        elements, _ = await perceive(page)

        element_id = (
            operation.element_id
            if operation.element_id is not None
            else pick(elements, operation.target)
        )
        if element_id is None or not any(e.id == element_id for e in elements):
            return f"could not find {operation.target.label!r} on the page"

        element = next(e for e in elements if e.id == element_id)
        value, refusal = resolve_value(element, operation, input_values)
        if refusal is not None:
            return refusal

        try:
            await act(page, elements, element_id, operation, value, strategy)
        except PlaywrightError as error:
            first_line = str(error).split("\n")[0]
            return f"{operation.kind} on {operation.target.label!r} failed: {first_line}"

        if operation.kind == "fill":
            typed = await verify_typed(page, element_id, element, value)
            if typed is not None:
                return typed

    # Typing changes no URL, title or label, so a fill-only move is verified
    # by the read-back above and nothing else. Demanding a page change here
    # would fail every correctly typed field. A move that clicks, or that
    # states an expectation of its own, still has to prove it on the page.
    only_filled = all(operation.kind == "fill" for operation in move.operations)
    if only_filled and move.expect == Expectation():
        return None

    return await verify(page, before, move.expect)


def resolve_value(
    element: Element, operation: Operation, input_values: dict[str, str]
) -> tuple[str, str | None]:
    """Vault values beat anything a planner supplied. Returns (value, refusal)."""
    if operation.kind != "fill":
        return "", None

    key = operation.value_key or element.name
    if key and key in input_values:
        return input_values[key], None
    if element.is_password:
        return "", (
            f"no vault value for {element.label!r}, and a password is never "
            f"filled from anything a planner supplied"
        )
    return operation.value or "", None


async def verify_typed(
    page: Page, element_id: int, element: Element, expected: str
) -> str | None:
    """A typed value is verified by reading it back, not by assuming."""
    elements, _ = await perceive(page)
    if not any(e.id == element_id for e in elements):
        return None  # the page moved on; the page-level check will judge that
    actual = await resolve(page, elements, element_id).input_value()
    if actual == expected:
        return None
    if element.is_password:
        # Never put a secret, or a near-miss of one, into a message or a log.
        return "the password field did not take the value"
    return f"expected the field to hold {expected!r}, it holds {actual!r}"
