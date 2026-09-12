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
from dataclasses import dataclass, field
from typing import Protocol

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page

from backend.orchestrator.plan import Expectation, Operation, Target
from backend.perception.content import Content
from backend.perception.serializer import (
    Element,
    blockers_for_target_async,
    read_async,
)
from shared.envelope import envelope
from shared.schema import (
    BaseModel,
    HelpRequested,
    Highlight,
    PagePreview,
    StateChanged,
    StepAction,
    StepFailed,
    StepField,
    ErrorPayload,
    StepPresented,
    TaskCompleted,
    TaskFailed,
    TaskStarted,
)

VERIFY_TIMEOUT_S = 5.0

# How long one action may take before it counts as not having worked.
#
# Playwright's own default is 30 seconds, which is the right default for a
# test suite and the wrong one here twice over. A person is watching this
# step happen, and half a minute of nothing is not a wait, it is a hang. And
# the loop's whole design is to fail and try something else — at 30s a step
# that retries once costs a minute before anyone is told, and the live
# railways run spent most of an hour that way. A click that has not landed in
# ten seconds is not going to.
ACTION_TIMEOUT_MS = 10_000


@dataclass(frozen=True)
class Snapshot:
    """Enough of the page's state to tell whether an action changed it.

    `content` is what the page says, and it is part of the comparison as much
    as the URL is: a search that fills a results table changes nothing else
    about the page, and a snapshot blind to it would report that nothing
    happened.
    """

    url: str
    title: str
    labels: tuple[str, ...]
    content: Content = field(default_factory=Content)
    # What the form holds. A page whose fields have been filled is not the
    # same page as one whose fields are empty, and until this was here the
    # loop could not tell: a step that typed a station name into a combobox
    # changed no URL, no title and no label, so `check` reported that the
    # page "did not change at all" about a step that had just worked.
    values: tuple[str, ...] = ()

    def value_of(self, label: str) -> str | None:
        """What the field with this label holds, or None if there is no such
        field. An empty string is an answer, not an absence — a field the page
        has emptied is exactly what this is for."""
        for element_label, value in zip(self.labels, self.values):
            if element_label == label:
                return value
        return None


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
    view = await read_async(page)
    snapshot = Snapshot(
        url=page.url,
        title=await page.title(),
        labels=tuple(element.label for element in view.elements),
        content=view.content,
        values=tuple(element.value for element in view.elements),
    )
    return view.elements, snapshot


def pick(elements: list[Element], target: Target) -> int | None:
    """Choose an element id. This is the seat the LLM will take."""
    for element in elements:
        if element.role != target.role or element.label != target.label:
            continue
        if target.qualifier is not None and element.qualifier != target.qualifier:
            continue
        return element.id
    return None


def resolve(page: Page, elements: list[Element], element_id: int):
    """Resolve an integer id back to something clickable.

    Two routes, because there are two kinds of element. One the accessibility
    tree named, and `get_by_role` finds it by that name. One perception
    inferred from layout, which by definition has no role to look up — for
    those, perception computed a structural path at the same moment it read
    the page, and that path is what turns the id back into a handle. Either
    way the resolution happens here, inside the backend, from an integer: no
    planner ever sees or emits a selector (CLAUDE.md).
    """
    element = next(e for e in elements if e.id == element_id)
    if element.locator_hint:
        return page.locator(element.locator_hint)
    twins = [e for e in elements if e.role == element.role and e.label == element.label]
    return page.get_by_role(element.role, name=element.label, exact=True).nth(
        twins.index(element)
    )


async def act(page: Page, elements: list[Element], element_id: int, operation: Operation,
              value: str, strategy: int) -> None:
    """Perform one operation. `strategy` 1 is a different route to the same end."""
    locator = resolve(page, elements, element_id)

    if operation.kind == "press":
        await locator.press(value, timeout=ACTION_TIMEOUT_MS)
        return

    if operation.kind == "fill":
        if strategy == 0:
            await locator.fill(value, timeout=ACTION_TIMEOUT_MS)
        else:
            # Click first, and edit with the keyboard rather than `clear`.
            #
            # `fill` and `clear` both require the element to be *editable*,
            # and a component-framework combobox ships its input `readonly`
            # until you click it — the framework removes the attribute in its
            # own focus handler. Playwright never gets that far: it waits for
            # editable, the attribute never clears, and thirty seconds later
            # the step fails on a field that was never actually blocked. Both
            # station inputs on the live railways search behave this way.
            # A click is not subject to the editable check, so this route
            # works where the direct one cannot.
            await locator.click(timeout=ACTION_TIMEOUT_MS)
            await locator.press("Control+a", timeout=ACTION_TIMEOUT_MS)
            await locator.press_sequentially(value, timeout=ACTION_TIMEOUT_MS)
        return

    if strategy == 0:
        await locator.click(timeout=ACTION_TIMEOUT_MS)
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
    if expect.content_says and not after.content.says(expect.content_says):
        return f"expected the page to say {expect.content_says!r}"
    if expect.value_is is not None:
        actual = after.value_of(expect.value_is.label)
        if actual is None:
            return f"expected a field called {expect.value_is.label!r} on the page"
        if actual != expect.value_is.equals:
            return (
                f"expected {expect.value_is.label!r} to hold "
                f"{expect.value_is.equals!r}, it holds {actual!r}"
            )
    if expect.rows_at_least is not None:
        rows = sum(len(table.rows) for table in after.content.tables)
        if rows < expect.rows_at_least:
            return (
                f"expected at least {expect.rows_at_least} row(s) of results, "
                f"the page has {rows}"
            )
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


# Keys, said the way a person would say them. "ArrowDown" is a thing the
# keyboard has; "move down the list" is the thing that is about to happen, and
# the trust panel is where someone decides whether to let it.
KEY_CAPTIONS = {
    "ArrowDown": "move down the list",
    "ArrowUp": "move up the list",
    "Enter": "choose what's highlighted",
    "Escape": "close this without choosing",
    "Tab": "move to the next field",
}


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
    if operation.kind == "press":
        key = operation.value or ""
        return f"I'm about to {KEY_CAPTIONS.get(key, f'press {key}')} on {where}."
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
    filled: list[FilledValue] = []

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

        # Durable verification: everything typed so far has to *still* be
        # there, not merely have been there when it was typed.
        #
        # This ends the run. It is not a retry and it is not a setback, and
        # both of those were tried.
        #
        # A retry is wrong because the keystrokes worked — something on the
        # page undid them afterwards, and repeating them invites the same
        # undoing. Handing it to the planner as a setback was tried on
        # 2026-09-09 and reverted the same day: the live LLM run was told in
        # plain words that its date was the wrong month, re-planned, clicked
        # search anyway, and reported `task.completed` on a timetable for a
        # date nobody had asked for. A run that stopped honestly became one
        # that finished wrongly, which is a strictly worse failure — the user
        # cannot catch it.
        #
        # It will be worth revisiting when a success condition can verify the
        # goal's own values well enough that a wrong answer cannot pass.
        # `Expectation.value_is` is the beginning of that and is not yet
        # enough on its own. See DECISIONS.md and EVALUATION.md, case 6.
        lapsed = await durability_failure(page, filled)
        if lapsed is not None:
            await give_up(lapsed)
            return

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
            # Say so. The planner is told and may choose differently, and the
            # *user* is told too — which for a long time it was not. A step
            # that failed and was absorbed produced no message at all, so the
            # trace of a skipped step was identical to the trace of a
            # completed one, in the interface and in the transcript alike.
            # That is how the first live railways run was read wrongly for a
            # day. Quiet, not silent.
            await connection.send(
                "step.failed",
                StepFailed(
                    step_index=steps_taken,
                    instruction=move.instruction,
                    reason=failure,
                    strategies_tried=2,
                ),
            )
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
        # Anything typed on a page we have since left is not ours to police.
        filled = [f for f in filled if f.url == page.url]
        filled += await record_fills(page, move)

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

        covered = await covering(page, element)
        if covered is not None:
            return covered

        try:
            await act(page, elements, element_id, operation, value, strategy)
        except PlaywrightError as error:
            first_line = str(error).split("\n")[0]
            return f"{operation.kind} on {operation.target.label!r} failed: {first_line}"

        if operation.kind == "fill":
            typed = await verify_typed(page, element_id, element, value)
            if typed is not None:
                return typed

    # Typing and key presses change no URL, title or label, so a move made
    # only of those is verified by the read-back above and nothing else.
    # Demanding a page change here would fail every correctly typed field. A
    # move that clicks, or that states an expectation of its own, still has to
    # prove it on the page — and so does a move of presses alone, which has no
    # read-back to stand on.
    kinds = {operation.kind for operation in move.operations}
    only_input = kinds <= {"fill", "press"} and "fill" in kinds
    if only_input and move.expect == Expectation():
        return None

    return await verify(page, before, move.expect)


async def covering(page: Page, element: Element) -> str | None:
    """Refuse to act on an element something is sitting on top of.

    Asked per element and per attempt, because the thing this catches appears
    *between* perceiving and acting: a dropdown the previous operation opened
    is not in the perceive that chose this element.

    The refusal is narrower than the detection deliberately. `analyse` reports
    anything overlapping the target at all, however slightly; this only stops
    the move when the blocker covers the point a click would actually land on.
    An overlap at the edge of a bounding box does not stop a click, and
    refusing there would fail moves that would have worked.
    """
    report = await blockers_for_target_async(page, element)
    if not report.blockers:
        return None
    if element.backend_node_id not in report.occluded_ids:
        return None
    blocker = report.target_blockers[0] if report.target_blockers else report.blockers[0]
    return (
        f"{element.label or 'the element'} is covered by something else "
        f"({blocker.reason}), so a click there cannot land"
    )


@dataclass(frozen=True)
class FilledValue:
    """A value this run put into a field, and where it put it."""

    role: str
    label: str
    value: str
    url: str


async def record_fills(page: Page, move: Move) -> list[FilledValue]:
    """What the fields a move filled actually hold, now that it has finished.

    Read from the page rather than taken from the plan: the point is to
    capture what is really there at the end of a successful step, so that the
    next step can be told if it stopped being there.
    """
    fills = [o for o in move.operations if o.kind == "fill"]
    if not fills:
        return []
    elements, _ = await perceive(page)
    recorded: list[FilledValue] = []
    for operation in fills:
        element_id = pick(elements, operation.target)
        if element_id is None:
            continue
        element = next(e for e in elements if e.id == element_id)
        if element.is_password:
            continue  # never hold a secret in run state, not even to check it
        try:
            actual = await resolve(page, elements, element_id).input_value()
        except PlaywrightError:
            continue
        if actual:
            recorded.append(
                FilledValue(
                    role=element.role, label=element.label, value=actual, url=page.url
                )
            )
    return recorded


async def lapsed_value(
    page: Page, recorded: list[FilledValue]
) -> tuple[FilledValue, str] | None:
    """The first value this run typed that has since stopped being there.

    Reading a field back the instant after typing proves the keystrokes
    arrived. It does not prove the value *stays*, and on a real page that is a
    different question: a component-framework combobox clears its own input on
    blur unless a choice was committed, so a field can verify correctly and be
    empty by the time the step that depends on it runs. Verification that only
    ever looks at the moment of typing cannot see that. This looks again at
    the next perceive.

    A field that has gone from the page entirely is not a failure — the page
    navigated, which is the page-level check's business, not this one.
    """
    watching = [record for record in recorded if record.url == page.url]
    if not watching:
        return None

    # One read for every record, not one each. `perceive` is three CDP calls
    # plus a full snapshot parse — cheap once, and paid per watched field when
    # it sat inside the loop. All the records are being checked against the
    # same instant anyway, so re-reading between them was never buying
    # freshness, only latency.
    elements, _ = await perceive(page)

    for record in watching:
        element_id = pick(elements, Target(record.role, record.label))
        if element_id is None:
            continue
        try:
            actual = await resolve(page, elements, element_id).input_value()
        except PlaywrightError:
            continue
        if actual != record.value:
            return record, (
                f"{record.label!r} no longer holds what I put in it — it held "
                f"{record.value!r} and now holds {actual!r}"
            )
    return None


async def durability_failure(
    page: Page, recorded: list[FilledValue]
) -> str | None:
    """`lapsed_value`, as just the message."""
    lapse = await lapsed_value(page, recorded)
    return lapse[1] if lapse is not None else None


def resolve_value(
    element: Element, operation: Operation, input_values: dict[str, str]
) -> tuple[str, str | None]:
    """Vault values beat anything a planner supplied. Returns (value, refusal)."""
    if operation.kind == "press":
        # A key name, not data. It never comes from the vault and never comes
        # from the user's answers — "Enter" is part of the plan, not an input.
        return operation.value or "", None
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
