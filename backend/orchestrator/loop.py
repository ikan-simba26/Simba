"""The runtime loop: perceive, act, verify, retry.

    goal -> perceive -> decide action -> render step
         -> user confirms -> act -> verify -> loop

Verification is not optional (see CLAUDE.md). Every step snapshots the page
before and after, and a step only counts as done if the page actually changed
in the way the plan expected. On a mismatch the step is retried once with a
different strategy; if that also fails, control goes back to the user via
`help.requested`. Nothing here assumes a click worked.

The detail level adapts when the caller passes `rules`: a starting level
from the first page, a fold on one clear signal while a step waits, a return
after two calm steps, each sent as `load.updated`. Those rules are provisional
and stand in for the estimator (`backend/estimator/rules.py`); a caller that
passes none — most tests — never sends `load.updated` at all.
"""

import asyncio
import base64
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from typing import Callable, Protocol

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page

from backend.estimator.page_features import PageFeatures
from backend.estimator.page_features import features as page_features
from backend.estimator.pairing import Recorder
from backend.estimator.rules import Decision, LevelRules
from backend.orchestrator import voice
from backend.orchestrator.plan import About, Expectation, FieldValue, Operation, Target
from backend.orchestrator.vault import Credentials, Vault
from backend.perception.content import Content
from backend.perception.serializer import (
    Element,
    PageView,
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
    Finding,
    StepAction,
    StepFailed,
    StepField,
    ErrorPayload,
    StepPresented,
    TaskCompleted,
    TaskFailed,
    TaskStarted,
    LevelOverride,
)

VERIFY_TIMEOUT_S = 5.0

# How long a step that waits on a list the site fetches may take to show it
# (`Expectation.list_opens`). A station list is a network round trip after a
# name is typed, not a repaint after a click, and on 2026-09-30 one took longer
# than five seconds on the live site: the run said the site offered no
# stations for Lahore, which has two (EVALUATION.md). Polled like any other
# verification, so a list that opens in half a second costs half a second; the
# price is paid only when no list ever comes, which with two strategies is
# twice this before the run says so.
LIST_TIMEOUT_S = 15.0

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


def features_of(view: PageView) -> PageFeatures | None:
    """The page's raw features, or None when this read brought no snapshot.

    The ablation switches turn the snapshot off, and a page read without one
    has no layout to count. A row with no page on it is not written.
    """
    return page_features(view, view.document) if view.document is not None else None


async def perceive(page: Page) -> tuple[list[Element], Snapshot, PageView]:
    """Read the page once: the elements, the comparable snapshot, and the view.

    The view comes back as well because the estimator counts its features off
    the same read — the parsed snapshot is in it — and a second read would be
    a second CDP round trip describing a page that has had time to move. It is
    deliberately *not* folded into `Snapshot`, which is compared for equality
    to decide whether an action changed anything: a field that is a fresh
    object every read would make every page look different from itself.
    """
    view = await read_async(page)
    snapshot = Snapshot(
        url=page.url,
        title=await page.title(),
        labels=tuple(element.label for element in view.elements),
        content=view.content,
        values=tuple(element.value for element in view.elements),
    )
    return view.elements, snapshot, view


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
    if expect.label_like:
        wanted = expect.label_like.casefold()
        if not any(wanted in label.casefold() for label in after.labels):
            return f"expected something called {expect.label_like!r} to appear on the page"
    if expect.content_says and not after.content.says(expect.content_says):
        return f"expected the page to say {expect.content_says!r}"
    if expect.rows_at_least is not None:
        rows = sum(len(table.rows) for table in after.content.tables)
        if rows < expect.rows_at_least:
            return (
                f"expected at least {expect.rows_at_least} row(s) of results, "
                f"the page has {rows}"
            )
    return None


def held_mismatch(after: Snapshot, held: FieldValue) -> str | None:
    """None if the field holds the value, else why not.

    Exact, deliberately: a date that is nearly right is a wrong answer. And an
    empty field is an answer, not an absence — `value_of` tells the two apart.
    The one loosening is a value declared with `names`, which the person gave
    in their words and the page holds in its own (`FieldValue`).
    """
    actual = after.value_of(held.label)
    if actual is None:
        return f"expected a field called {held.label!r} on the page"
    if not held.accepts(actual):
        return f"expected {held.label!r} to hold {held.equals!r}, it holds {actual!r}"
    return None


def said_so_far(
    snapshot: Snapshot, task: "Task", seen: dict[str, list[str]]
) -> dict[str, list[str]]:
    """Add what this page says under the labels the task must be shown.

    `seen` is the run's memory, mutated and returned, for the same reason
    `findings_in` keeps one: the page that states the reference number is not
    the page the billing run ends on.
    """
    for shown in task.about.shows:
        values = seen.setdefault(shown.reads, [])
        values += [v for v in snapshot.content.values_for(shown.reads) if v not in values]
    return seen


def unmet(
    after: Snapshot, task: "Task", seen: dict[str, list[str]] | None = None
) -> str | None:
    """Why this page does not finish the task, or None if it does.

    The values the goal names come first, then the task's own success
    expectation. First because they are the more specific failure: on the
    railways page that searched the wrong date, "results appeared" is true and
    the date is what is wrong, and the reason given should say so.

    `seen` is what the run has been shown so far (`said_so_far`). Without it,
    only this page is asked.
    """
    for held in task.about.holds:
        failure = held_mismatch(after, held)
        if failure is not None:
            return failure
    said = said_so_far(after, task, {} if seen is None else seen)
    for shown in task.about.shows:
        if not shown.met_by(said.get(shown.reads, [])):
            got = ", ".join(repr(v) for v in said.get(shown.reads, [])) or "nothing"
            return (f"expected the page to show {shown.says!r} as {shown.reads!r}, "
                    f"it showed {got}")
    if task.success is not None:
        return mismatch(after, task.success)
    return None


def findings_in(
    snapshot: Snapshot, task: "Task", known: dict[str, list[str]]
) -> list[Finding]:
    """Update what has been found, and return it in the task's own order.

    Accumulated across the run rather than read from the final page, because
    the answer is often not on the page the task ends on. The billing amount
    is on the results page; the run then opens the detail page, where that
    column does not exist. Reading only at the end would find nothing and
    report nothing, having walked past the answer two steps earlier.

    `known` is mutated, which is the point: it is the run's memory of what it
    has seen.

    Every value the page gives a label, not the first: a results table has a
    row per result, and "which trains run?" is answered by all of them.

    `known` holds the values themselves, and each `Finding` carries both forms
    of them: `value`, the one line `voice.found` builds, which stops at four
    and counts the rest, and `values`, all of them. The step screen shows one
    finding in large type while the run is still going; the closing screen is
    the answer and shows every result. Keeping only the line here was the
    display-side half of the same defect the content channel had
    (EVALUATION.md, 2026-09-18b).
    """
    for answer in task.about.finds:
        values = snapshot.content.values_for(answer.reads)
        if values:
            known[answer.name] = values
    return [Finding(label=answer.name, value=voice.found(known[answer.name]),
                    values=known[answer.name])
            for answer in task.about.finds if answer.name in known]


def satisfies(after: Snapshot, expect: Expectation) -> bool:
    """Whether a page is already in the expected state, change or no change."""
    return mismatch(after, expect) is None


def check(before: Snapshot, after: Snapshot, expect: Expectation) -> str | None:
    """Return None if the page changed as expected, else why it did not."""
    if after == before:
        return "the page did not change at all"
    return mismatch(after, expect)


async def verify(page: Page, before: Snapshot, expect: Expectation) -> str | None:
    """Poll until the page settles into the expected state, or give up.

    A step waiting on a list the site fetches gets longer to see it than an
    ordinary step (`LIST_TIMEOUT_S`); nothing else about the check changes.
    """
    window = LIST_TIMEOUT_S if expect.list_opens else VERIFY_TIMEOUT_S
    deadline = time.monotonic() + window
    failure = "the page did not change at all"
    while time.monotonic() < deadline:
        _, after, _ = await perceive(page)
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
    # A question for the person rather than something to do. Nothing is acted
    # on: it is shown, and whatever they answer goes back to whoever asked
    # (`answered`). Any of its actions but the one that stops is an answer.
    question: bool = False
    # More of a step the person has already agreed to. It is acted on and
    # verified like any move, and not shown again: "set the departure station"
    # is one thing to agree to, though it takes typing a name, looking at what
    # the page offers, and then choosing — and what to choose cannot be known
    # until the page has been looked at.
    quiet: bool = False


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
    # When the page says the task is done. Checked before every move, so a run
    # stops as soon as it holds, and once more at the end.
    success: Expectation | None = None
    # What the task is about: the values its goal names, which must hold for
    # the run to finish, and the values it asks for, which are read and shown.
    #
    # Required, and keyword-only. `About()` is a legitimate answer — a task
    # that changes something rather than finding something out, which is most
    # of them — but it has to be written, so that leaving it out is a
    # TypeError rather than a task that silently checks and shows nothing.
    about: About = field(kw_only=True)
    # The closing screen's one plain sentence, built from what the run found
    # (`found`, by the names the task shows them under) and what the site said
    # back (`seen`, by the page's own labels). None means no sentence. Only
    # ever from those values: `voice.explain_*`.
    explain: "Callable[[dict[str, list[str]], dict[str, list[str]]], str | None] | None" = field(
        default=None, kw_only=True)


class Brief(Protocol):
    """What a person asked for, and whatever it still needs them to say.

    A goal rarely names everything a task needs: "trains to Rawalpindi
    tomorrow" does not say where from. A brief holds what was understood,
    asks for the rest one question at a time, and when nothing is missing
    says what the task is and who plans it (`details.py`).
    """

    goal: str
    estimated_steps: int
    #: Why the asking was abandoned, once it has been.
    gave_up: str | None

    def question(self) -> "Move | None":
        """The next thing to ask, or None when nothing is missing."""
        ...

    def answered(self, action_id: str, input_values: dict[str, str]) -> None: ...

    def settle(self) -> "tuple[Planner, Task]":
        """The planner and the task, now that every detail is known."""
        ...


MAX_STEPS = 12


def is_answer(move: "Move", action_id: object) -> bool:
    """Whether a response to a question answers it, rather than stopping."""
    return action_id != voice.CANCEL_ID and any(a.id == action_id for a in move.actions)


def caption_for(move: "Move") -> str:
    """Plain words for what is about to happen. Never the value being typed."""
    operation = move.operations[0] if move.operations else None
    if operation is None:
        return move.instruction
    return voice.caption(
        operation.kind, operation.target.label or "this", operation.value or ""
    )


async def send_preview(page: Page, connection: Connection, move: "Move | None") -> None:
    """Answer trust.requested: a picture of the real page, and what is next.

    The site view is covered rather than hidden precisely so this works — a
    view Chromium believes is invisible stops repainting and the capture
    times out about half the time (CLAUDE.md, architecture constraints).
    """
    highlight = Highlight(x=0, y=0, w=0, h=0)
    caption = voice.PREVIEW_CAPTION

    if move is not None and move.operations:
        caption = caption_for(move)
        elements, _, _ = await perceive(page)
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


# --- saved sign-in details ---------------------------------------------------


def sign_in_fields(move: "Move") -> tuple[StepField | None, StepField | None]:
    """The step's username and password fields, if it asks for a password.

    The password is the field of type password. The username is the one other
    text field beside it, when there is exactly one; a step that asks for more
    than that is not a plain sign-in, and only its password is saved."""
    password = next((f for f in move.fields if f.type == "password"), None)
    if password is None:
        return None, None
    others = [f for f in move.fields if f is not password and f.type == "text"]
    return (others[0] if len(others) == 1 else None), password


def with_saved_details(move: "Move", saved: Credentials | None, can_save: bool) -> "Move":
    """The step as the person sees it, given what is saved for this site.

    Saved: the sign-in fields are gone — the backend types them — the detail
    line says so, and there is a way to forget them. Not saved: the step asks
    as it always did, with a second button that keeps the password. A step
    that asks for no password is returned unchanged."""
    username, password = sign_in_fields(move)
    if password is None:
        return move
    primary, *rest = move.actions
    stop = [a for a in rest if a.id == voice.CANCEL_ID]
    if saved is not None:
        return replace(
            move,
            detail=voice.USING_SAVED,
            fields=[f for f in move.fields if f is not password and f is not username],
            actions=[primary, StepAction(id=voice.FORGET_ID, label=voice.FORGET,
                                         kind="primary"), *stop],
        )
    if not can_save:
        return move
    return replace(move, actions=[
        primary, StepAction(id=voice.REMEMBER_ID, label=voice.remember(primary.label),
                            kind="primary"), *stop])


def saved_answers(move: "Move", saved: Credentials) -> dict[str, str]:
    """What the saved details answer, keyed the way the step's fields are."""
    username, password = sign_in_fields(move)
    answers = {password.id: saved.password} if password is not None else {}
    if username is not None and saved.username:
        answers[username.id] = saved.username
    return answers


def answers_to_save(move: "Move", input_values: dict[str, str]) -> Credentials | None:
    """The details the person just typed, to keep — or None if no password."""
    username, password = sign_in_fields(move)
    if password is None or not input_values.get(password.id):
        return None
    return Credentials(input_values.get(username.id, "") if username else "",
                       input_values[password.id])


class _Run:
    """One task's conversation with the person: what is on screen, and the
    few things every part of a run says the same way."""

    def __init__(
        self,
        page: Page,
        connection: Connection,
        recorder: Recorder | None,
        rules: LevelRules | None,
        vault: Vault | None = None,
    ) -> None:
        self.page = page
        self.connection = connection
        self.recorder = recorder
        self.rules = rules
        #: Saved sign-in details, or None to ask every time (`vault.py`).
        self.vault = vault
        self._can_save: bool | None = None
        self.started = time.monotonic()
        self.state: str | None = None
        #: How many things have been put on screen: steps and questions both.
        self.shown = 0
        #: How many were said there would be, in `task.started`. Read once and
        #: kept: a count that moves while the person is answering is worse
        #: than one that is approximate, and on 2026-09-30 it moved twice in
        #: one run — 1 of 7, then 2 of 5, because the questions counted the
        #: one on screen and the steps then counted none of them.
        self.total = 0

    @property
    def can_save(self) -> bool:
        """Whether a password can be kept on this machine. Asked once."""
        if self._can_save is None:
            self._can_save = self.vault is not None and self.vault.available
        return self._can_save

    def saved(self) -> Credentials | None:
        return self.vault.get(self.page.url) if self.can_save else None

    async def set_state(self, state: str) -> None:
        # Exactly one state is active at a time, so don't re-announce it.
        if state != self.state:
            self.state = state
            await self.connection.send("state.changed", StateChanged(state=state))

    async def adapt(self, decision: Decision | None) -> None:
        """Every decision is written down; only a change is sent."""
        if decision is None:
            return
        if self.recorder is not None:
            self.recorder.note_decision(decision)
        if decision.send:
            await self.connection.send("load.updated", decision.load())

    async def give_up(self, reason: str) -> None:
        await self.set_state("stuck")
        await self.connection.send(
            "help.requested",
            HelpRequested(
                reason=reason,
                suggestion=voice.HELP_SUGGESTION,
            ),
        )

    async def stopped(self) -> None:
        await self.connection.send(
            "task.failed",
            TaskFailed(reason=voice.YOU_STOPPED, recoverable=True),
        )

    async def open(self, goal: str, estimated_steps: int, start_url: str) -> None:
        self.total = estimated_steps
        await self.connection.send(
            "task.started", TaskStarted(goal=goal, estimated_steps=estimated_steps)
        )
        await self.set_state("thinking")
        await self.page.goto(start_url)

    async def present(
        self, move: "Move", *, goal: str, findings: list[Finding], view: PageView,
    ) -> dict:
        """Put a step or a question on screen and wait for the person.

        Returns the response's payload. While it waits it answers what the
        overlay may ask in the meantime: a picture of the page, a telemetry
        sample, a change of level.
        """
        self.shown += 1
        index = self.shown
        await self.set_state("waiting")
        features = features_of(view)
        # What the page was like at the moment this step went on screen, kept
        # for whatever the person then does with it. Written down only if the
        # caller asked for a recorder: the app does, tests do not
        # (`backend/estimator/pairing.py`).
        if self.recorder is not None:
            self.recorder.note_step(
                index,
                goal=goal,
                url=self.page.url,
                instruction=move.instruction,
                features=features,
            )
        # Before the step, so it arrives already at its level: the starting
        # level on the first step, a return after two calm ones.
        if self.rules is not None:
            await self.adapt(self.rules.start_step(index, features))
        await self.connection.send(
            "step.presented",
            StepPresented(
                step_index=index,
                # Never less than what is on screen, and never less than what
                # was promised. It can still end higher than promised: a
                # question only the page can raise — which of two stations in
                # one city — cannot be counted before the page has answered.
                step_total=max(self.total, index),
                instruction=move.instruction,
                detail=move.detail,
                fields=move.fields,
                actions=move.actions,
                requires_confirmation=True,
                findings=findings,
            ),
        )

        async def answer_questions(message: dict) -> None:
            if message.get("type") == "trust.requested":
                await send_preview(self.page, self.connection, move)
                return
            # Channel B, arriving while the step is on screen: one sample on
            # a timer, and one more with the response itself. Paired with the
            # page above and written down, and — with rules — the one input
            # that can fold the step while it is still showing.
            if message.get("type") == "telemetry":
                sample = message.get("payload") or {}
                if self.recorder is not None:
                    self.recorder.note_telemetry(sample)
                if self.rules is not None:
                    await self.adapt(self.rules.telemetry(sample))
                return
            await follow_override(message, self.rules, self.adapt)

        response = await self.connection.receive(
            "step.response", step_index=index, on_other=answer_questions
        )
        return response.get("payload", {})


async def run_task(
    page: Page,
    connection: Connection,
    planner: Planner,
    task: Task,
    start_url: str,
    recorder: Recorder | None = None,
    rules: LevelRules | None = None,
    vault: Vault | None = None,
) -> None:
    """Perceive, decide, present, act, verify, recover. Planner-agnostic.

    `recorder` pairs what the page was like with what the person did on it,
    for the estimator's training set. `app.py` supplies one; a caller that
    passes none — every test here — runs exactly as before and writes nothing
    (`backend/estimator/pairing.py`).

    `rules` chooses the detail level as the run goes (`_Run.adapt`). With
    none, the level is whatever the overlay shows and nothing here moves it.
    """
    run = _Run(page, connection, recorder, rules, vault)
    await run.open(task.goal, task.estimated_steps, start_url)
    await carry_out(run, planner, task)


async def run_brief(
    page: Page,
    connection: Connection,
    brief: Brief,
    start_url: str,
    recorder: Recorder | None = None,
    rules: LevelRules | None = None,
    vault: Vault | None = None,
) -> None:
    """Ask for whatever the goal left out, then run the task it describes.

    The questions come first and one at a time, as ordinary steps, with the
    site already open behind them — so "What are you doing?" has a page to
    show, and the level rules have a page to weigh. Nothing on the site is
    touched until every one is answered. A person who stops at a question has
    stopped the task; a brief that cannot make sense of the answers ends the
    run the way being stuck does, and says why.
    """
    run = _Run(page, connection, recorder, rules, vault)
    await run.open(brief.goal, brief.estimated_steps, start_url)

    view: PageView | None = None
    while (question := brief.question()) is not None:
        if view is None:
            _, _, view = await perceive(page)
        payload = await run.present(
            question, goal=brief.goal, findings=[], view=view
        )
        if not is_answer(question, payload.get("action_id")):
            await run.stopped()
            return
        await run.set_state("thinking")
        brief.answered(payload["action_id"], payload.get("input_values") or {})

    if brief.gave_up is not None:
        await run.give_up(brief.gave_up)
        return

    planner, task = brief.settle()
    await carry_out(run, planner, task)


async def carry_out(run: _Run, planner: Planner, task: Task) -> None:
    """The loop itself, from a page that is already open."""
    page, connection = run.page, run.connection
    rules = run.rules
    set_state, give_up = run.set_state, run.give_up
    history: list[str] = []
    setback: str | None = None
    consecutive_setbacks = 0
    # Steps the person agreed to and the run then did. Questions are not
    # steps, and neither is the quiet remainder of a step already agreed to.
    steps_taken = 0
    last_failure: str | None = None
    completed: list[Move] = []
    filled: list[FilledValue] = []
    # What the task was asked to find out, as it turns up. See `findings_in`.
    found: dict[str, list[str]] = {}
    # What the site has said back about the values the goal named. See
    # `said_so_far`.
    seen: dict[str, list[str]] = {}

    # A planner that asks, or that finishes a step quietly, takes more turns
    # than it shows steps. The second bound is what stops one that never
    # gets to the point.
    for _ in range(MAX_STEPS * 2):
        if steps_taken >= MAX_STEPS:
            break
        await set_state("thinking")
        elements, before, view = await perceive(page)
        findings = findings_in(before, task, found)
        said_so_far(before, task, seen)

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
        # `About.holds` is the beginning of that and is not yet enough on its
        # own: it checks only the values a plan author declared, on the final
        # page. See DECISIONS.md and EVALUATION.md, case 6.
        lapsed = await durability_failure(page, filled, task.about.holds)
        if lapsed is not None:
            await give_up(lapsed)
            return

        # Only a task with a success expectation can finish early. `holds`
        # alone is not a finish line: a filled form nobody has searched with
        # holds every value the goal named.
        if task.success is not None and unmet(before, task, seen) is None:
            break

        move = await planner.next_move(elements, history, setback)
        setback = None

        if move is None:
            reason = getattr(planner, "stuck_reason", None)
            if reason:
                await give_up(reason)
                return
            break

        if move.question:
            # The planner needs the person to say something before it can go
            # on — which of two stations they meant. Shown like a step and
            # acted on by nobody: the answer goes back to the planner.
            payload = await run.present(
                move, goal=task.goal, findings=findings, view=view,
            )
            if not is_answer(move, payload.get("action_id")):
                await run.stopped()
                return
            planner.answered(payload["action_id"], payload.get("input_values") or {})
            continue

        input_values: dict[str, str] = {}
        keep: Credentials | None = None
        if not move.quiet:
            steps_taken += 1
            # A step that asks for a password uses the saved one if there is
            # one, and offers to keep it if there is not. Either way the
            # password is never in what is shown: a saved one is typed by the
            # backend, and the field for a new one is always empty.
            saved = run.saved() if sign_in_fields(move)[1] is not None else None
            shown = with_saved_details(move, saved, run.can_save)
            payload = await run.present(shown, goal=task.goal, findings=findings, view=view)
            if payload.get("action_id") == voice.FORGET_ID and saved is not None:
                # Deleted, then the same step again, asking.
                run.vault.forget(page.url)
                saved = None
                shown = replace(with_saved_details(move, None, run.can_save),
                                detail=voice.FORGOTTEN)
                payload = await run.present(shown, goal=task.goal, findings=findings,
                                            view=view)
            action = payload.get("action_id")
            if action not in (voice.CONFIRM_ID, voice.REMEMBER_ID):
                await run.stopped()
                return
            input_values = payload.get("input_values", {})
            if saved is not None:
                input_values = {**input_values, **saved_answers(move, saved)}
            if action == voice.REMEMBER_ID:
                keep = answers_to_save(move, input_values)

        await set_state("acting")

        # The retry: same move, different strategy. Identical for every planner.
        #
        # Except a step that waits on a list the site fetches, which gets one
        # attempt (2026-10-01). Its verification already waits three times as
        # long as an ordinary step's (`LIST_TIMEOUT_S`), so a second attempt
        # doubled that for the case where no list ever comes — a mistyped
        # place took 31.5s to be reported. The longer wait is that step's
        # second chance. An exception to CLAUDE.md's "retry once with a
        # different strategy"; DECISIONS.md.
        strategies = 1 if move.expect.list_opens else 2
        failure = await attempt_move(page, move, input_values, strategy=0, before=before)
        if failure is not None and strategies > 1:
            _, before_retry, _ = await perceive(page)
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
                    step_index=run.shown,
                    instruction=move.instruction,
                    reason=failure,
                    strategies_tried=strategies,
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
        if keep is not None:
            # Only now: a password that did not sign anyone in is not kept.
            run.vault.put(page.url, keep)
        completed.append(move)
        history.append(move.instruction)
        # Anything typed on a page we have since left is not ours to police.
        filled = [f for f in filled if f.url == page.url]
        filled += await record_fills(page, move)

    _, final, _ = await perceive(page)
    findings = findings_in(final, task, found)
    # A task with named values is checked here even without a success
    # expectation, so a declared value can never go unchecked.
    unfinished = (
        unmet(final, task, seen)
        if task.success is not None or task.about.holds or task.about.shows
        else None
    )
    if unfinished is not None:
        # Prefer the concrete reason the last move failed over the generic
        # "ran out of steps", which says nothing a user could act on.
        await give_up(last_failure or f"I ran out of steps before finishing. {unfinished}")
        return

    # A return that was due when the last step was answered has no next step
    # to arrive with, so it goes out before the ending.
    if rules is not None:
        await run.adapt(rules.end())

    # A planner that remembers runs gets told what actually worked.
    remember = getattr(planner, "finished", None)
    if remember is not None:
        remember(completed)

    await connection.send(
        "task.completed",
        TaskCompleted(
            summary=f"{task.goal} {page.url}",
            duration_ms=int((time.monotonic() - run.started) * 1000),
            steps_taken=steps_taken,
            llm_calls=getattr(planner, "calls_made", 0),
            replayed=getattr(planner, "replayed_steps", 0) > 0,
            findings=findings,
            explanation=task.explain(found, seen) if task.explain else None,
        ),
    )


async def follow_override(
    message: dict,
    rules: LevelRules | None,
    adapt: Callable[[Decision | None], Awaitable[None]],
) -> None:
    """A `level.override`: the person chose a level or handed it back, or the
    overlay's guard moved it because a step did not fit (`by: "overflow"`).

    Read wherever the backend is listening — while a step waits, and before a
    task has started — so a lock set on the home screen holds from the first
    step. One that does not parse is ignored, like any unknown message.
    """
    if rules is None or message.get("type") != "level.override":
        return
    try:
        override = LevelOverride.model_validate(message.get("payload") or {})
    except ValueError:
        return
    await adapt(rules.override(override.level, override.locked, override.by))


async def attempt_move(
    page: Page, move: Move, input_values: dict[str, str], strategy: int, before: Snapshot
) -> str | None:
    """Run a Move's operations, then verify. None on success."""
    for operation in move.operations:
        # Perceive fresh each time: the previous operation may have navigated.
        elements, _, _ = await perceive(page)

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
    elements, _, _ = await perceive(page)
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
    page: Page, recorded: list[FilledValue], holds: tuple[FieldValue, ...] = ()
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

    **A field that now holds exactly what the task declared for it is not a
    failure either** (`holds`, from `Task.about.holds`). A page often commits
    a value by rewriting it: the live railways picker takes a typed
    `2026-10-15` and, once the day is picked, writes back `15-10-2026`. That
    is the value being set, not undone, and on 2026-09-17 this check stopped
    an LLM run with a correct form because it compared against the typed
    string alone (EVALUATION.md, 2026-09-17b).

    Nothing else is loosened. The record keeps the typed value, so a field
    accepted this way is still checked at every later look, and anything but
    the declared value is a lapse. A field the task did not declare gets no
    such allowance, and a reformat there still reads as a lapse — which is
    where an LLM planner, typing into whatever it chooses, usually is. See
    DECISIONS.md.
    """
    watching = [record for record in recorded if record.url == page.url]
    if not watching:
        return None

    # One read for every record, not one each. `perceive` is three CDP calls
    # plus a full snapshot parse — cheap once, and paid per watched field when
    # it sat inside the loop. All the records are being checked against the
    # same instant anyway, so re-reading between them was never buying
    # freshness, only latency.
    elements, _, _ = await perceive(page)

    for record in watching:
        element_id = pick(elements, Target(record.role, record.label))
        if element_id is None:
            continue
        try:
            actual = await resolve(page, elements, element_id).input_value()
        except PlaywrightError:
            continue
        if actual == record.value:
            continue
        if any(held.label == record.label and held.accepts(actual) for held in holds):
            continue
        return record, (
            f"{record.label!r} no longer holds what I put in it — it held "
            f"{record.value!r} and now holds {actual!r}"
        )
    return None


async def durability_failure(
    page: Page, recorded: list[FilledValue], holds: tuple[FieldValue, ...] = ()
) -> str | None:
    """`lapsed_value`, as just the message."""
    lapse = await lapsed_value(page, recorded, holds)
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
    # An answer that says nothing is not an answer. The overlay sends every
    # field of the step as it stands, and an LLM-planned step shows its field
    # empty — the model's value is not put in the box for the person to
    # confirm. So pressing "Yes, do that" without typing used to send `""`
    # and, on any input carrying a `name`, replace what the model chose: the
    # field was filled with nothing and read back as nothing, successfully.
    # A password with no answer falls through to the refusal below, which is
    # where it belongs.
    if key and input_values.get(key):
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
    elements, _, _ = await perceive(page)
    if not any(e.id == element_id for e in elements):
        return None  # the page moved on; the page-level check will judge that
    actual = await resolve(page, elements, element_id).input_value()
    if actual == expected:
        return None
    if element.is_password:
        # Never put a secret, or a near-miss of one, into a message or a log.
        return "the password field did not take the value"
    return f"expected the field to hold {expected!r}, it holds {actual!r}"
