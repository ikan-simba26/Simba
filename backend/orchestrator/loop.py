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
after two calm steps, each sent as `load.updated`. The trained estimator judges
the page when there is a model, and the rules' signs when there is not; what
the person does is still read by the provisional rules
(`backend/estimator/rules.py`). A caller that passes none — most tests — never
sends `load.updated` at all.
"""

import asyncio
import base64
import json
import logging
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Callable, Protocol
from urllib.parse import urlsplit

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page

from backend.estimator.page_features import PageFeatures
from backend.estimator.page_features import features as page_features
from backend.estimator.pairing import Recorder
from backend.estimator.rules import Decision, LevelRules
from backend.orchestrator import voice
from backend.orchestrator.browser import capture_site
from backend.orchestrator.plan import (
    About,
    Confirmation,
    Expectation,
    FieldValue,
    FinalRead,
    Operation,
    Target,
    part_of,
)
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
    Detail,
    HandOver,
    HelpRequested,
    Highlight,
    PagePreview,
    Proof,
    StateChanged,
    Finding,
    StepAction,
    StepFailed,
    StepField,
    ErrorPayload,
    StepPresented,
    TaskCompleted,
    TaskOffer,
    KeepOffer,
    TaskFailed,
    TaskStarted,
    LevelOverride,
)

if TYPE_CHECKING:
    from backend.orchestrator.tiles import TileStore

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
        message_type: str | tuple[str, ...],
        step_index: int | None = None,
        on_other: Callable[[dict], Awaitable[None]] | None = None,
    ) -> dict:
        # One type, or any of several: the first message of a connection is
        # a task to start or, since 2026-11-04, a helper to watch.
        wanted = (message_type,) if isinstance(message_type, str) else message_type
        while True:
            message = json.loads(await self._websocket.receive_text())
            if message.get("type") not in wanted:
                # Not what we are waiting for, but not necessarily noise: the
                # user can ask what is happening while a step is on screen.
                if on_other is not None:
                    await on_other(message)
                continue
            if step_index is not None:
                if message.get("payload", {}).get("step_index") != step_index:
                    continue
            return message

    async def next_message(self) -> dict:
        """The next message, whatever its type (2026-11-04): teaching listens
        to the overlay and the page at once (`teach.py`)."""
        return json.loads(await self._websocket.receive_text())

    async def poll(self, seconds: float = 0.02) -> list[dict]:
        """Whatever the overlay has sent, without waiting for more than a
        moment — for the checklist's Pause, between moves nobody pressed for
        (2026-10-14). Waiting on the socket's queue is safe to cut short:
        nothing is taken off it until it is returned."""
        got: list[dict] = []
        while True:
            try:
                text = await asyncio.wait_for(self._websocket.receive_text(), seconds)
            except asyncio.TimeoutError:
                return got
            got.append(json.loads(text))


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

    if operation.kind == "select":
        # A list the page draws itself (`<select>`), chosen by what it says
        # (2026-11-04: a routine keeps the option's words). The other way is
        # by its value or its words, whichever the page has.
        if strategy == 0:
            await locator.select_option(label=value, timeout=ACTION_TIMEOUT_MS)
        else:
            await locator.select_option(value, timeout=ACTION_TIMEOUT_MS)
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
    if expect.has_value and not after.content.values_for(expect.has_value):
        return f"expected the page to show something under {expect.has_value!r}"
    for label, accepted in expect.field_has:
        held = after.value_of(label)
        if held is None or not any(a.casefold() in held.casefold() for a in accepted):
            return f"expected {label!r} to hold {accepted[0]!r}, it holds {held!r}"
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
    snapshot: Snapshot, task: "Task", known: dict[str, list[str]],
    rows: list[dict[str, str]] | None = None,
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

    `rows`, when given, is the run's memory of the results whole — one dict
    per table row, by the names the task shows them under, repeats kept
    (`Content.rows_for`) — and is mutated the same way. `values` drops a
    repeated value, so two findings' lists cannot be paired by position: two
    trains with one journey time give two trains and one time. The first
    finding carries the rows (`Finding.rows`), one cell per finding returned.
    """
    for answer in task.about.finds:
        values = [v for v in (part_of(value, answer.part)
                              for value in snapshot.content.values_for(answer.reads)) if v]
        if values:
            known[answer.name] = values
    if rows is not None and task.about.finds:
        read = snapshot.content.rows_for([answer.reads for answer in task.about.finds])
        if read:
            rows[:] = [{answer.name: part_of(cell, answer.part)
                        for answer, cell in zip(task.about.finds, row)}
                       for row in read]
            if task.about.per_row is not None:
                rows[:] = [task.about.per_row(row) for row in rows]
    # Said in plain words where the task says how (`Answer.plain`,
    # 2026-10-16); `known` keeps the page's own text, which is what is
    # compared and ringed.
    def shown(answer, values: list[str]) -> list[str]:
        return [answer.plain(v) for v in values] if answer.plain else list(values)

    findings = [Finding(label=answer.name, value=voice.found(shown(answer, known[answer.name])),
                        values=shown(answer, known[answer.name]))
                for answer in task.about.finds if answer.name in known]
    if rows and findings and findings[0].label == task.about.finds[0].name:
        plain = {answer.name: answer.plain for answer in task.about.finds}
        findings[0].rows = [[(plain[f.label] or str)(row[f.label]) if row.get(f.label) else ""
                             for f in findings]
                            for row in rows]
    return findings


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
    # What the step is about, for the icon beside it: date, place, choose,
    # type, read or confirm (`shared/schema.py`, `StepKind`). None means work
    # it out from the operations (`kind_of`).
    kind: str | None = None
    # Which of the task's stages the step is in (`TaskStarted.stages`).
    stage: int | None = None
    # Safe to run without a press, and its line on the checklist
    # (`PlanStep.safe`, 2026-10-14). Only a planner that knows sets it.
    safe: bool = False
    doing: str | None = None
    # What was wrong with the last answer, beside a question asked again.
    note: str | None = None
    # Changes a record (`PlanStep.changes`, 2026-10-16): tried once, only on a
    # replica, and only after its final screen (`final`, the details it shows
    # as the page states them; `final_answers`, its two answers' words).
    changes: bool = False
    #: Which AI provider chose this move, for the person to see (2026-11-13):
    #: "Gemini", "Groq". None for a written plan, a routine, replay.
    worked_out_by: str | None = None
    final: tuple[FinalRead, ...] = ()
    final_answers: tuple[str, str] | None = None
    # Its words say it books, and the planner says it only opens a page to
    # read: "Book train 7UP" opens the booking form, and "Confirm Booking"
    # books (2026-11-04, fix). Believed only as `only_opens` checks it.
    opens: bool = False


# --- the final step (2026-10-16) ---------------------------------------------
#
# CLAUDE.md, the final-step rule: an action that pays, books, registers or
# changes a record happens only on a replica, and only after a final screen
# that says what will happen, shows what, how much and when as the page
# states them, and has two answers, neither the default. Enforced here, for
# every planner, rather than trusted to each one.

#: Where our replicas are served from: this machine, and nowhere else.
REPLICA_HOSTS = ("127.0.0.1", "localhost")

#: A button or link whose words say it would make a change: for a planner
#: that does not mark its own changes (the model, replay). Matched on whole
#: words, ignoring case.
CHANGE_WORDS = re.compile(
    r"\b(register|enrol|enroll|book|reserve|pay|purchase|buy|checkout|check out|"
    r"place order|submit|confirm|"
    # 2026-11-13: the AI planner works on live sites now, so more of the words
    # a form's last button uses are read as a change (DECISIONS.md, default
    # deny). A press wrongly read as one costs one more question; one missed
    # would be a change nobody agreed to.
    r"apply|send|sign up|signup|create account|order|order now|proceed to|subscribe|"
    r"donate|save changes|delete|remove account|transfer)\b", re.IGNORECASE)


#: What a box for card or bank details is called, by its label or its name.
PAYMENT_WORDS = re.compile(
    r"\b(card|cvv|cvc|csc|security code|expiry|expiration|iban|swift|bank account)\b",
    re.IGNORECASE)


async def asks_for_payment(page: Page, elements: list[Element], move: "Move") -> bool:
    """Whether a move would type into a box for card or bank details: by its
    label, its name, or what the page says it autocompletes (`cc-number`,
    `cc-csc`, …). SIMBA never types payment details, anywhere (CLAUDE.md, the
    final-step rule; 2026-10-16)."""
    for operation in move.operations:
        if operation.kind != "fill":
            continue
        element_id = (operation.element_id if operation.element_id is not None
                      else pick(elements, operation.target))
        element = next((e for e in elements if e.id == element_id), None)
        words = " ".join(filter(None, [operation.target.label,
                                       element.label if element else "",
                                       element.name if element else ""]))
        if PAYMENT_WORDS.search(words):
            return True
        if element is not None:
            try:
                filled = await resolve(page, elements, element.id).get_attribute(
                    "autocomplete", timeout=2000)
            except PlaywrightError:
                filled = None
            if (filled or "").strip().lower().startswith("cc-"):
                return True
    return False


#: What a page says when it is a check that a person is there, or a refusal,
#: rather than the website (2026-11-13). Found live: timeanddate answered a
#: headless run with Cloudflare's "Just a moment…", and the model quoted it
#: as the answer. Matched on the title, the headings and the larger text,
#: never on the body, where "captcha" can be a word in an article.
BLOCKED_WORDS = re.compile(
    r"(just a moment|checking your browser|verify(ing)? you are (a )?human|"
    r"are you a robot|i'?m not a robot|captcha|attention required|access denied|"
    r"request blocked|you have been blocked|unusual traffic|"
    r"\b403 forbidden\b|security check|one[- ]time (password|code)|\botp\b|"
    r"verification code)", re.IGNORECASE)


#: A press that pays: on a live site always the person's, after its final
#: screen (2026-11-13, the advisor's direction, F). An order paid in cash on
#: delivery is not a payment here: SIMBA may place it after the final screen.
PAY_WORDS = re.compile(r"\b(pay|pay now|payment|make payment|purchase|buy now|complete purchase)\b",
                       re.IGNORECASE)

#: What a page says once a payment or an order went through.
DONE_WORDS = re.compile(
    r"(thank you|payment (was )?(successful|received|complete)|order (is )?(placed|confirmed)|"
    r"booking (is )?confirmed|transaction (successful|complete)|receipt|paid)",
    re.IGNORECASE)

#: How long a page is the person's before SIMBA stops waiting: long enough to
#: find a card and wait for a bank's code.
HANDOVER_WAIT_S = 20 * 60
#: How many times one run hands over for a check before it stops.
MOST_CHECKS = 2

#: An amount as a page writes it.
MONEY = re.compile(r"(rs\.?|pkr|usd|us\$|\$|£|€)\s?[\d,]+(\.\d+)?|[\d,]+(\.\d+)?\s?(rs|pkr)\b",
                   re.IGNORECASE)


async def page_asks_for_payment(page: Page, elements: "list[Element]") -> bool:
    """Whether the page has a box for card or bank details, by its label or
    name, or by what the page says it autocompletes (`cc-number`, …)."""
    for element in elements:
        if element.type == "fill" or element.role in ("textbox", "spinbutton", "combobox"):
            words = " ".join(filter(None, [element.label, element.name]))
            if PAYMENT_WORDS.search(words):
                return True
    try:
        return bool(await page.evaluate(
            "() => !!document.querySelector('input[autocomplete^=\"cc-\"]')"))
    except PlaywrightError:
        return False


async def amounts_on_page(page: Page, most: int = 3) -> list[Detail]:
    """The page's own amounts, as it states them, for a final screen no plan
    wrote: "Total: Rs 450" is Total, Rs 450. Read from the page's text, never
    from a box anyone typed in."""
    try:
        text = await page.evaluate("() => document.body ? document.body.innerText : ''")
    except PlaywrightError:
        return []
    details: list[Detail] = []
    for line in (text or "").splitlines():
        line = line.strip()
        found = MONEY.search(line)
        if not found or len(line) > 80:
            continue
        label = line[:found.start()].strip(" :-") or voice.ON_THE_PAGE
        details.append(Detail(label=label[:40], value=found.group(0).strip()))
        if len(details) >= most:
            break
    return details


def done_words(snapshot: "Snapshot") -> str | None:
    """The page's own words saying a payment or an order went through, or None."""
    for text in [snapshot.title] + [h.text for h in snapshot.content.headings] \
            + [v.text for v in snapshot.content.values]:
        if text and DONE_WORDS.search(text):
            return text.strip()
    return None


def blocked(snapshot: "Snapshot", elements: "list[Element] | None" = None) -> bool:
    """Whether the page is a bot check, a CAPTCHA, a one-time code or a
    refusal: something only the person may do (CLAUDE.md; the advisor's hard
    rules). SIMBA never tries to get past one."""
    said = [snapshot.title] + [h.text for h in snapshot.content.headings] \
        + [v.text for v in snapshot.content.values]
    if any(BLOCKED_WORDS.search(text or "") for text in said):
        return True
    for element in elements or []:
        words = " ".join(filter(None, [element.label, element.name]))
        if re.search(r"captcha|one[- ]time|\botp\b|verification code", words, re.IGNORECASE):
            return True
    return False


def on_replica(url: str) -> bool:
    """Whether a page is one of our replicas: served from this machine."""
    from urllib.parse import urlparse

    return (urlparse(url).hostname or "") in REPLICA_HOSTS


def would_change(move: "Move", planner: object) -> bool:
    """Whether a move books, pays, registers or changes a record: marked so
    by a planner that marks its own, or, for one that does not, a press whose
    words say so."""
    if move.changes:
        return True
    if getattr(planner, "marks_changes", False) or move.question:
        return False
    return any(operation.kind == "click" and CHANGE_WORDS.search(operation.target.label or "")
               for operation in move.operations)


async def only_opens(page: Page, elements: list[Element], move: "Move") -> bool:
    """Whether a move whose words say it books only opens a page, as its
    planner says (`Move.opens`): then it gets no final screen of its own, and
    the press that does book gets the only one (2026-11-04, fix).

    Believed only on one of our replicas, and only when every press is on a
    link, as the page has it now, to another page of the same replica:
    following a link asks the site for a page and sends it nothing. A button,
    a link that runs a script, or anything on a live site keeps its final
    screen, whatever the planner said."""
    if not move.opens or move.changes or not on_replica(page.url) or not move.operations:
        return False
    here = urlsplit(page.url)
    for operation in move.operations:
        if operation.kind != "click":
            return False
        element_id = (operation.element_id if operation.element_id is not None
                      else pick(elements, operation.target))
        if element_id is None:
            return False
        try:
            href = await resolve(page, elements, element_id).evaluate(
                "e => e.tagName === 'A' && e.getAttribute('href') ? e.href : ''",
                timeout=2000)
        except PlaywrightError:
            return False
        goes = urlsplit(href or "")
        if goes.scheme not in ("http", "https") or goes.netloc != here.netloc \
                or (goes.path, goes.query) == (here.path, here.query):
            return False
    return True


def pressed(move: "Move") -> str:
    """The site's own words on what a move presses: "Confirm Booking"."""
    return next((o.target.label for o in move.operations if o.kind == "click"
                 and o.target.label), move.instruction)


def read_final(content: Content, read: FinalRead) -> str | None:
    """One final-screen detail, as the page states it now, or None."""
    if read.fixed is not None:
        return read.fixed
    if read.row:
        value = None
        for table in content.tables:
            for row in table.rows:
                if all(row.get(header) == wanted for header, wanted in read.row):
                    value = row.get(read.reads)
                    break
            if value:
                break
    else:
        value = content.value_for(read.reads)
    if not value or not value.strip():
        return None
    return read.plain(value.strip()) if read.plain else value.strip()


def final_screen(move: "Move", content: Content) -> "tuple[Move, list[Detail]] | None":
    """The final screen for a move that changes something: its sentence, its
    details read from the page, and its two answers. None when the page does
    not state a detail the screen has to show: then nothing is done."""
    label = pressed(move)
    reads = move.final or (FinalRead(voice.WHAT_I_PRESS, fixed=label),)
    details: list[Detail] = []
    for read in reads:
        value = read_final(content, read)
        if value is None:
            return None
        details.append(Detail(label=read.name, value=value))
    instruction = move.instruction if move.final else voice.final_press(label)
    answers = voice.final_actions(*(move.final_answers or ()))
    shown = replace(move, instruction=instruction, detail=voice.FINAL_WAITS, fields=[],
                    actions=answers, changes=True, safe=False, kind="confirm")
    return shown, details


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
    # (`found`, by the names the task shows them under), what the site said
    # back (`seen`, by the page's own labels), and the results whole (`rows`,
    # a dict per table row by the same names as `found`, repeats kept). None
    # means no sentence. Only ever from those values: `voice.explain_*`.
    explain: ("Callable[[dict[str, list[str]], dict[str, list[str]], "
              "list[dict[str, str]]], str | None] | None") = field(default=None, kw_only=True)
    # Above the results on the closing screen: what they are for, from what
    # the person asked and agreed (2026-10-14). None: no heading.
    heading: str | None = field(default=None, kw_only=True)
    # The closing screen's last line: what was done and what was not
    # (2026-10-16). A sentence, or built like `explain` from what the site
    # said back — "You are registered for CS-401 section 001." None: no line.
    scope: ("str | Callable[[dict[str, list[str]], dict[str, list[str]], "
            "list[dict[str, str]]], str | None] | None") = field(default=None, kw_only=True)
    # For a task that changes something: what the site shows once it has
    # (2026-10-16). The task is completed only with it on the page, and it is
    # quoted on the closing screen. None: a task that only reads.
    confirms: "Confirmation | None" = field(default=None, kw_only=True)


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

    # Optional: `async def prepare(self, page) -> None`, called once the site
    # is open and before the first question, for a brief that checks answers
    # against what the site offers. It reads; it never acts.

    def settle(self) -> "tuple[Planner, Task]":
        """The planner and the task, now that every detail is known."""
        ...


MAX_STEPS = 12


def is_answer(move: "Move", action_id: object) -> bool:
    """Whether a response to a question answers it, rather than stopping."""
    return action_id != voice.CANCEL_ID and any(a.id == action_id for a in move.actions)


def kind_of(move: "Move") -> str:
    """What a step is about, for the icon beside it (2026-10-07).

    A planner that knows says so (`Move.kind`): the trip planner knows a
    station from a date. Otherwise it is read off what the step does, which
    every planner's moves have — the hardcoded plans, the LLM's and replay's:
    typing is "type", picking from a list is "choose", following a link is
    "read" (it opens something to look at), and pressing anything else is
    "confirm". A question is "type" when it has a box and "choose" when it
    has only buttons.
    """
    if move.kind is not None:
        return move.kind
    if move.question:
        return "type" if any(not f.value for f in move.fields) else "choose"
    operation = move.operations[0] if move.operations else None
    if operation is None:
        return "confirm"
    if operation.kind in ("fill", "type"):
        return "type"
    if operation.kind == "select" or operation.target.role == "option":
        return "choose"
    if operation.target.role == "link":
        return "read"
    return "confirm"


def caption_for(move: "Move") -> str:
    """Plain words for what is about to happen. Never the value being typed."""
    operation = move.operations[0] if move.operations else None
    if operation is None:
        return move.instruction
    return voice.caption(
        operation.kind, operation.target.label or "this", operation.value or ""
    )


#: What counts as a password box in a picture of the page.
PASSWORD_BOXES = ("input[type=password], input[autocomplete=current-password], "
                  "input[autocomplete=new-password]")
#: What a password box is painted over with. Solid, and the same in both themes.
MASK_COLOUR = "#8c7a66"


#: The longest the closing picture may take before it is given up on.
PROOF_DEADLINE_S = 8.0

#: Where on the page each thing read is: the smallest element whose whole
#: text is the value, or its table row, in the page's own coordinates. A
#: sentence quoted from a paragraph (`within`) is the smallest element that
#: holds it.
RINGS_JS = """(targets) => {
  const shown = [...document.querySelectorAll('body *')].filter(e => {
    const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden';
  });
  const text = (e) => (e.innerText || '').trim().replace(/\\s+/g, ' ');
  return targets.map(([want, row, within]) => {
    const has = (e) => within ? text(e).includes(want) : text(e) === want;
    const exact = shown.filter(e => has(e) && ![...e.children].some(has));
    const el = exact[0];
    if (!el) return null;
    const box = (row && el.closest('tr')) || el;
    const r = box.getBoundingClientRect();
    return {x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height};
  });
}"""


#: Every sentence of the page's visible text, as the page writes it.
SENTENCES_JS = """() => (document.body.innerText || '')
  .split(/\\n+/).flatMap(line => line.split(/(?<=[.!?])\\s+/))
  .map(s => s.trim().replace(/\\s+/g, ' ')).filter(Boolean)"""


async def site_sentence(page: Page, words: str) -> str | None:
    """The page's own sentence holding these words, exactly as it wrote it,
    or None when the page does not say them (2026-10-16)."""
    try:
        sentences = await page.evaluate(SENTENCES_JS)
    except PlaywrightError:
        return None
    wanted = words.casefold()
    return next((s for s in sentences if wanted in s.casefold()), None)


#: The longest a picture of the page may take before it is dropped
#: (2026-10-15). The picture is optional; the person's answer is not.
PREVIEW_DEADLINE_S = 5.0
#: The `error` code for a picture that was dropped, late or failed.
PREVIEW_LATE = "PREVIEW_LATE"


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
        # Every password box is painted over before the picture leaves the
        # backend (2026-10-07). The overlay shows this picture when the
        # person asks "What are you doing?", and a password is never on it —
        # not as dots, whose count says its length, and not as text if a site
        # has a "show password" switch that turns the box into an ordinary
        # one: those are matched by what they autocomplete.
        shot = await capture_site(page, mask=PASSWORD_BOXES, mask_colour=MASK_COLOUR)
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


#: How often a run waiting on a put-away window looks again, in seconds.
WINDOW_POLL_S = 0.5

#: What a run did, and how long each part took, in `logs/backend.log`
#: (`app.log_runs`). Never a value the person typed.
log = logging.getLogger("simba.run")


class StoppedWhileAway(Exception):
    """The person pressed stop on the step that said the window was back."""


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
        window: Callable[[], Awaitable[str]] | None = None,
        auto: bool = False,
    ) -> None:
        self.page = page
        self.connection = connection
        #: Run the safe moves as a checklist rather than asking for each
        #: (2026-10-14). The app turns it on unless the person asked to be
        #: asked every time; a caller that does not say gets the old way.
        self.auto = auto
        #: Messages `poll` read that were not a pause: kept for the next wait.
        self.held: list[dict] = []
        #: Pictures of the page being taken, each in its own task, so that
        #: none stands between the person and their answer (2026-10-15).
        self.previews: set[asyncio.Task] = set()
        self.recorder = recorder
        self.rules = rules
        #: Saved sign-in details, or None to ask every time (`vault.py`).
        self.vault = vault
        #: Whether the SIMBA window is "shown", "minimised" or "hidden"
        #: (`browser.window_watch`), or None where there is no window — the
        #: headless browser, and every test that does not give one.
        self.window = window
        self._can_save: bool | None = None
        #: A website where a helper could show SIMBA the task, offered on the
        #: stuck screen when the AI planner could not do it (2026-11-13, "AI
        #: first, then teach"). None: nothing is offered.
        self.teach_site: str | None = None
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

    async def ready(self, *, goal: str, findings: list[Finding], view: PageView) -> None:
        """Wait, rather than act, while the window is put away.

        A minimised window paints about once a second, and an action there
        waits for a page that never settles: on 2026-10-05 that ended two
        demo clips "I'm stuck" (EVALUATION.md, 2026-10-05d). So nothing is
        done while the window is minimised or hidden — no failure, no retry,
        no stuck screen. When it comes back the person is told, in one line,
        that the run waited, and it goes on only when they say so. Raises
        `StoppedWhileAway` if they press stop instead.
        """
        if self.window is None:
            return
        away = await self.window()
        if away == "shown":
            return
        log.info("window %s: waiting before acting", away)
        went = time.monotonic()
        was = self.state
        while await self.window() != "shown":
            await asyncio.sleep(WINDOW_POLL_S)
        log.info("window shown again after %.1fs: asking to carry on", time.monotonic() - went)
        back = Move(instruction=voice.WINDOW_BACK, detail="", operations=[],
                    expect=Expectation(), fields=[], actions=voice.actions(voice.CARRY_ON),
                    question=True, kind="confirm")
        payload = await self.present(back, goal=goal, findings=findings, view=view)
        if payload.get("action_id") != voice.CONFIRM_ID:
            raise StoppedWhileAway
        await self.set_state(was or "acting")

    async def tick(self, move: "Move", *, findings: list[Finding],
                   coming: list[str] | None = None) -> int:
        """One line of the checklist: a move SIMBA does by itself. Shown, not
        asked; nothing waits for an answer, and nothing about the person is
        measured on it — no row for the estimator, nothing for the level
        rules, because there was no decision to measure."""
        self.shown += 1
        await self.connection.send(
            "step.presented",
            StepPresented(
                step_index=self.shown,
                step_total=max(self.total, self.shown),
                instruction=move.doing or move.instruction,
                detail="",
                fields=[],
                actions=[],
                requires_confirmation=False,
                findings=findings,
                step_kind=kind_of(move),
                stage=move.stage,
                coming=coming or [],
                worked_out_by=move.worked_out_by,
            ),
        )
        log.info("checklist line %d: %s", self.shown, kind_of(move))
        return self.shown

    async def pause_pressed(self) -> bool:
        """Whether the checklist's Pause has been pressed since last asked."""
        poll = getattr(self.connection, "poll", None)
        if poll is None:
            return False
        paused = False
        for message in await poll():
            if (message.get("type") == "step.response"
                    and message.get("payload", {}).get("action_id") == voice.PAUSE_ID):
                paused = True
            else:
                self.held.append(message)
        return paused

    async def give_up(self, reason: str, unconfirmed: bool = False) -> None:
        log.info("task ended stuck after %.1fs%s", time.monotonic() - self.started,
                 ", not confirmed" if unconfirmed else "")
        await self.set_state("stuck")
        await self.connection.send(
            "help.requested",
            HelpRequested(
                reason=reason,
                suggestion=voice.AI_THEN_TEACH if self.teach_site else voice.HELP_SUGGESTION,
                unconfirmed=unconfirmed,
                teach_site=self.teach_site,
            ),
        )

    async def hand_over(self, reason: str) -> str:
        """The real page, the person's (2026-11-13): the bar says why, and the
        website shows below it. "done", "cancel", or "timeout". Nothing on the
        page is read while it is theirs."""
        sentence = voice.HANDOVER_PAYMENT if reason == "payment" else voice.HANDOVER_CHECK
        log.info("handed over: %s, on %s", reason, urlsplit(self.page.url).netloc or "a page")
        await self.set_state("waiting")
        await self.connection.send("handover", HandOver(
            reason=reason, sentence=sentence, site=urlsplit(self.page.url).netloc))
        try:
            message = await asyncio.wait_for(
                self.connection.receive(("handover.done", "task.cancel")), HANDOVER_WAIT_S)
        except asyncio.TimeoutError:
            return "timeout"
        if message.get("type") == "task.cancel":
            return "cancel"
        action = (message.get("payload") or {}).get("action")
        if action != "done":
            return "cancel"
        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=10_000)
        except PlaywrightError:
            pass
        log.info("handed back: %s", reason)
        return "done"

    async def after_payment(self) -> None:
        """The person has paid, or says so: what the page now says, in its own
        words — or that it does not say."""
        _, after, _ = await perceive(self.page)
        said = done_words(after)
        if said is None:
            await self.give_up(voice.PAYMENT_NOT_SEEN, unconfirmed=True)
            return
        await self.connection.send("task.completed", TaskCompleted(
            summary=f"paid {self.page.url}",
            duration_ms=int((time.monotonic() - self.started) * 1000),
            steps_taken=self.shown, llm_calls=0, replayed=False, findings=[],
            heading=voice.PAID, caveat=voice.PAID_CAVEAT,
            confirmation=voice.site_says(said)))

    async def stopped(self) -> None:
        log.info("task stopped by the person after %.1fs", time.monotonic() - self.started)
        await self.connection.send(
            "task.failed",
            TaskFailed(reason=voice.YOU_STOPPED, recoverable=True),
        )

    async def open(self, goal: str, estimated_steps: int, start_url: str,
                   stages: list[str] | None = None) -> None:
        self.total = estimated_steps
        await self.connection.send(
            "task.started",
            TaskStarted(goal=goal, estimated_steps=estimated_steps, stages=stages or []),
        )
        await self.set_state("thinking")
        opening = time.monotonic()
        await self.page.goto(start_url)
        log.info("task started on %s, %d steps estimated; page open in %.1fs",
                 urlsplit(start_url).netloc, estimated_steps, time.monotonic() - opening)

    async def present(
        self, move: "Move", *, goal: str, findings: list[Finding], view: PageView,
        final: list[Detail] | None = None,
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
                step_kind=kind_of(move),
                stage=move.stage,
                note=move.note,
                final=final,
                worked_out_by=move.worked_out_by,
            ),
        )
        log.info("step %d on screen: %s%s", index, kind_of(move), ", final" if final else "")
        shown_at = time.monotonic()

        async def answer_questions(message: dict) -> None:
            if message.get("type") == "trust.requested":
                # Taken beside the wait, never in it (2026-10-15). It was
                # awaited here: on 2026-10-14 one screenshot took 30s to fail,
                # and "Register for CS-401", pressed meanwhile, waited 31s.
                self.picture(move)
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

        # Anything that arrived while the checklist ran — a picture asked
        # for, a telemetry sample — is answered first.
        held, self.held = self.held, []
        for message in held:
            await answer_questions(message)
        try:
            response = await self.connection.receive(
                "step.response", step_index=index, on_other=answer_questions
            )
        finally:
            # Answered: a picture still being taken is of a step that has
            # gone, and must not race the next move on the page.
            self.drop_pictures()
        payload = response.get("payload", {})
        log.info("step %d answered %r after %.1fs", index, payload.get("action_id"),
                 time.monotonic() - shown_at)
        return payload

    def picture(self, move: "Move") -> None:
        """Take a picture of the page for the overlay, in a task of its own,
        and drop it if it is late (`PREVIEW_DEADLINE_S`) or fails: the
        picture is optional."""

        async def take() -> None:
            asked = time.monotonic()
            try:
                await asyncio.wait_for(send_preview(self.page, self.connection, move),
                                       PREVIEW_DEADLINE_S)
                log.info("picture of the page sent in %.1fs", time.monotonic() - asked)
            except asyncio.CancelledError:
                raise
            except Exception as error:  # noqa: BLE001 - late, failed or closed: dropped
                log.info("picture of the page not sent after %.1fs: %s",
                         time.monotonic() - asked, type(error).__name__)
                # Said, so "What are you doing?" can say it too, rather than
                # doing nothing (2026-10-16). Nothing more is tried.
                try:
                    await self.connection.send("error", ErrorPayload(
                        code=PREVIEW_LATE, message=voice.NO_PICTURE))
                except Exception:  # noqa: BLE001 - the socket may be gone
                    return

        task = asyncio.create_task(take())
        self.previews.add(task)
        task.add_done_callback(self.previews.discard)

    def drop_pictures(self) -> None:
        """Every picture still being taken, dropped."""
        for task in list(self.previews):
            task.cancel()


async def run_task(
    page: Page,
    connection: Connection,
    planner: Planner,
    task: Task,
    start_url: str,
    recorder: Recorder | None = None,
    rules: LevelRules | None = None,
    vault: Vault | None = None,
    window: Callable[[], Awaitable[str]] | None = None,
    auto: bool = False,
    teach_site: str | None = None,
) -> None:
    """Perceive, decide, present, act, verify, recover. Planner-agnostic.

    `teach_site` (2026-11-13): where the stuck screen offers a helper's "Show
    me once" if this run cannot be done — a goal the AI planner was given.

    `recorder` pairs what the page was like with what the person did on it,
    for the estimator's training set. `app.py` supplies one; a caller that
    passes none — every test here — runs exactly as before and writes nothing
    (`backend/estimator/pairing.py`).

    `rules` chooses the detail level as the run goes (`_Run.adapt`). With
    none, the level is whatever the overlay shows and nothing here moves it.
    """
    run = _Run(page, connection, recorder, rules, vault, window, auto)
    run.teach_site = teach_site
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
    window: Callable[[], Awaitable[str]] | None = None,
    auto: bool = False,
    tiles: "TileStore | None" = None,
) -> None:
    """Ask for whatever the goal left out, then run the task it describes.

    The questions come first and one at a time, as ordinary steps, with the
    site already open behind them — so "What are you doing?" has a page to
    show, and the level rules have a page to weigh. Nothing on the site is
    touched until every one is answered. A person who stops at a question has
    stopped the task; a brief that cannot make sense of the answers ends the
    run the way being stuck does, and says why.
    """
    run = _Run(page, connection, recorder, rules, vault, window, auto)
    # On a replica a brief may offer to finish the task once its answer is in
    # (2026-10-16): book the train, pay the bill. Its stages say so.
    if hasattr(brief, "finishes"):
        brief.finishes = on_replica(start_url)
    await run.open(brief.goal, brief.estimated_steps, start_url,
                   getattr(brief, "stages", None))

    # A brief that holds its answers to what the site offers reads that first,
    # without touching anything: the train search's own station list
    # (`details.TripBrief.prepare`, 2026-10-06).
    prepare = getattr(brief, "prepare", None)
    if prepare is not None:
        await prepare(page)

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
    follow_for = getattr(brief, "follow_on", None)
    keep = keep_offer(brief, tiles)
    completed = await carry_out(run, planner, task, send=follow_for is None and keep is None)
    if completed is None or (follow_for is None and keep is None):
        return
    follow = follow_for(completed) if follow_for and on_replica(page.url) else None
    await finish(run, completed, follow, keep)


@dataclass(frozen=True)
class Keep:
    """Keeping this task as one of the person's tiles (2026-10-18): offered
    once on the closing screen under `label`; `save` keeps it under the name
    the person gives, or returns None if it cannot."""

    label: str
    save: Callable[[str], object]


def keep_offer(brief: "Brief", tiles: "TileStore | None") -> Keep | None:
    """The offer to keep this task, when it has details worth keeping, is not
    already a tile, and there is room. Never for a run started from a tile."""
    keepable = getattr(brief, "keepable", None)
    if tiles is None or keepable is None or getattr(brief, "from_tile", None):
        return None
    kept = keepable()
    if kept is None:
        return None
    flow, details, label = kept
    if not tiles.can_keep(flow, details):
        return None
    return Keep(label=label, save=lambda name: tiles.add(name, flow, details))


@dataclass(frozen=True)
class FollowOn:
    """What can follow the answer, on a replica (2026-10-16): booking one of
    the trains found, paying the bill. Offered as a quiet second button on
    the closing screen (`id`, `label`), or taken straight away when the goal
    asked for it (`straight`). `take` gives the planner and the task that
    finish the job."""

    id: str
    label: str
    straight: bool
    take: Callable[[], "tuple[Planner, Task]"]


class LeftTheAnswer(Exception):
    """The person went on from the closing screen without the follow-on."""


#: How long a run waits on its closing screen's offer before it closes itself
#: (2026-10-17). Until then it waited for as long as the connection lasted.
#: Ten minutes is long enough to read an answer and decide; the overlay takes
#: the offer away when the run has gone (`App.tsx`), and "Back to start" works
#: as before.
OFFER_IDLE_S = 600.0


async def finish(run: _Run, completed: TaskCompleted, follow: FollowOn | None,
                 keep: Keep | None = None) -> None:
    """The answer, and the job finished if the person asks for it.

    Asked for in the goal: straight on, no closing screen between. Otherwise
    the closing screen as always, with one more, quieter button; the run
    waits for it until the person presses it, goes back to start (which
    closes the connection), cancels, or leaves it for `OFFER_IDLE_S`.
    Someone who wanted only the answer presses nothing extra (2026-10-16; it
    was a question after every answer).

    And, once, the offer to keep the task as one of the person's own tiles
    (`keep`, 2026-10-18). Kept, the run goes on waiting for the other offer,
    if there is one.
    """
    if follow is None and keep is None:
        await run.connection.send("task.completed", completed)
        return
    if follow is None or not follow.straight:
        update: dict = {}
        if follow is not None:
            update["offer"] = TaskOffer(id=follow.id, label=follow.label)
        if keep is not None:
            update["keep"] = KeepOffer(label=keep.label)
        await run.connection.send("task.completed", completed.model_copy(update=update))

        async def left(message: dict) -> None:
            if message.get("type") == "task.cancel":
                raise LeftTheAnswer

        while True:
            try:
                response = await asyncio.wait_for(
                    run.connection.receive("step.response", on_other=left), OFFER_IDLE_S)
            except asyncio.TimeoutError:
                log.info("closing screen left for %.0fs: closing the run", OFFER_IDLE_S)
                return
            except Exception:  # noqa: BLE001 - left, cancelled, or the connection closed
                return
            payload = response.get("payload", {})
            action = payload.get("action_id")
            if keep is not None and action == voice.KEEP_ID:
                name = (payload.get("input_values") or {}).get("label") or keep.label
                log.info("kept as a tile" if keep.save(name) else "could not keep the tile")
                keep = None
                if follow is None:
                    return
                continue
            if follow is not None and action == follow.id:
                break
            return  # any other answer: the closing screen was the end
        await run.set_state("thinking")
    assert follow is not None
    planner, task = follow.take()
    await carry_out(run, planner, task)


async def carry_out(run: _Run, planner: Planner, task: Task,
                    send: bool = True) -> TaskCompleted | None:
    """The loop itself, from a page that is already open.

    Returns the ending when the task completed, sent unless `send` is False —
    for a brief that may offer to finish the task once the answer is in
    (`run_brief`, 2026-10-16) — and None when the run ended any other way."""
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
    # The same results whole, a row per result, repeats kept.
    rows: list[dict[str, str]] = []
    # What the site has said back about the values the goal named. See
    # `said_so_far`.
    seen: dict[str, list[str]] = {}
    # After anything goes wrong, the next move asks again, safe or not: a
    # checklist that carried on past a failure would be SIMBA deciding what
    # the person would want (2026-10-14).
    ask_next = False
    # Pages handed to the person for a check (2026-11-13).
    checks = 0

    # A planner that asks, or that finishes a step quietly, takes more turns
    # than it shows steps. The second bound is what stops one that never
    # gets to the point.
    for _ in range(MAX_STEPS * 2):
        if steps_taken >= MAX_STEPS:
            break
        await set_state("thinking")
        reading = time.monotonic()
        elements, before, view = await perceive(page)
        read_s = time.monotonic() - reading
        findings = findings_in(before, task, found, rows)
        # A task that changes something has no answer to show on the way: what
        # it reads is its receipt, from the confirmation, shown at the end.
        # On the booking form "Here's what I found: 7UP" pushed the name
        # question past a 1280x800 window (2026-10-16, in the real window).
        if task.confirms is not None:
            findings = []
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

        # A bot check, a CAPTCHA, a one-time code or a refusal (2026-11-13):
        # never got past, never read as the website. The person's to do, on
        # the real page; twice still there, and SIMBA stops.
        if blocked(before, elements):
            checks += 1
            if checks > MOST_CHECKS:
                await give_up(voice.BLOCKED)
                return
            handed = await run.hand_over("check")
            if handed != "done":
                await connection.send("task.failed", TaskFailed(
                    reason=voice.HANDED_BACK_STOPPED, recoverable=True))
                return
            continue

        # A page that asks for card or bank details (2026-11-13): paying is
        # the person's, on the real page. SIMBA never types into it.
        if await page_asks_for_payment(page, elements):
            handed = await run.hand_over("payment")
            if handed != "done":
                await connection.send("task.failed", TaskFailed(
                    reason=voice.HANDED_BACK_STOPPED, recoverable=True))
                return
            await run.after_payment()
            return

        # Only a task with a success expectation can finish early. `holds`
        # alone is not a finish line: a filled form nobody has searched with
        # holds every value the goal named. Nor a planner that must finish
        # (2026-11-04): a routine a helper showed is done when its last move
        # is, and a page that already shows the answer's label before then is
        # not the answer to this run.
        if (task.success is not None and not getattr(planner, "must_finish", False)
                and unmet(before, task, seen) is None):
            break

        choosing = time.monotonic()
        # A planner that chooses from what the page says, not only from what
        # can be pressed: a routine's rows (2026-11-04, fix).
        look = getattr(planner, "look", None)
        if look is not None:
            look(before.content)
        move = await planner.next_move(elements, history, setback)
        log.info("page read in %.1fs (%d elements); next move chosen in %.1fs", read_s,
                 len(elements), time.monotonic() - choosing)
        by = getattr(planner, "worked_out_by", None)
        if move is not None and by and move.worked_out_by is None:
            move = replace(move, worked_out_by=by)
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

        # Card or bank details are never typed, on any site (2026-10-16): the
        # page is handed to the person instead (2026-11-13).
        if await asks_for_payment(page, elements, move):
            handed = await run.hand_over("payment")
            if handed != "done":
                await connection.send("task.failed", TaskFailed(
                    reason=voice.HANDED_BACK_STOPPED, recoverable=True))
                return
            await run.after_payment()
            return

        # The final step (2026-10-16; changed 2026-11-13 by the advisor's
        # direction, G): a move that books, orders, registers or changes a
        # record is done only after its final screen is answered "do it" — on
        # our replicas, and now on a live site too. A press that pays on a
        # live site is then handed to the person: SIMBA never presses it.
        # Whichever planner asked.
        paying = False
        if would_change(move, planner) and not await only_opens(page, elements, move):
            live = not on_replica(page.url)
            paying = live and bool(PAY_WORDS.search(pressed(move)))
            screen = final_screen(move, before.content)
            if screen is None:
                await give_up(voice.NO_FINAL_SCREEN)
                return
            move, details = screen
            if live and not move.final:
                # Nobody wrote which details matter: the page's own amounts.
                details = details + await amounts_on_page(page)
            steps_taken += 1
            payload = await run.present(move, goal=task.goal, findings=findings, view=view,
                                        final=details)
            action = payload.get("action_id")
            if action == voice.DECLINE_ID:
                # "Don't": the task ends, and nothing was changed.
                await connection.send("task.failed", TaskFailed(
                    reason=voice.NOTHING_CHANGED, recoverable=True))
                return
            if action != voice.CONFIRM_ID:
                await run.stopped()
                return
            if paying:
                # "Do it" to paying: the page is theirs, and they press Pay.
                handed = await run.hand_over("payment")
                if handed != "done":
                    await connection.send("task.failed", TaskFailed(
                        reason=voice.HANDED_BACK_STOPPED, recoverable=True))
                    return
                await run.after_payment()
                return

        # The checklist: a safe move, run without a press (2026-10-14). Pause
        # is looked for first, so a press lands before the next move rather
        # than after it. Never a move that changes something.
        by_itself = (run.auto and move.safe and not move.quiet and not ask_next
                     and not move.changes)
        if by_itself and await run.pause_pressed():
            paused = Move(instruction=voice.PAUSED, detail="", operations=[],
                          expect=Expectation(), fields=[],
                          actions=voice.actions(voice.CARRY_ON), question=True,
                          kind="confirm", stage=move.stage)
            payload = await run.present(paused, goal=task.goal, findings=findings, view=view)
            if payload.get("action_id") != voice.CONFIRM_ID:
                await run.stopped()
                return
        if by_itself:
            steps_taken += 1
            # What the planner expects to do by itself next, if it knows.
            ahead = getattr(planner, "coming", None)
            await run.tick(move, findings=findings, coming=ahead() if ahead else [])
        elif move.changes:
            pass  # asked above, on its final screen
        elif not move.quiet:
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
            if action == voice.DECLINE_ID and any(a.id == voice.DECLINE_ID
                                                  for a in shown.actions):
                # No, to a yes-or-no question about one move (2026-10-16):
                # it is left undone, and the task goes on without it.
                history.append(f"Not done, as asked: {move.instruction}")
                continue
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
        # And a step that changes something gets one attempt, too
        # (2026-10-16): a second press, a different way, could make the change
        # twice. Its check is that the site confirmed it.
        strategies = 1 if move.expect.list_opens or move.changes else 2
        # Before every action, the window has to be there (`_Run.ready`).
        ready = (lambda: run.ready(goal=task.goal, findings=findings, view=view))
        acting = time.monotonic()
        try:
            failure = await attempt_move(page, move, input_values, strategy=0, before=before,
                                         ready=ready)
            if failure is not None and strategies > 1:
                log.info("move %s not done in %.1fs: trying another way",
                         kind_of(move), time.monotonic() - acting)
                _, before_retry, _ = await perceive(page)
                failure = await attempt_move(page, move, input_values, 1, before_retry,
                                             ready=ready)
            log.info("move %s %s in %.1fs", kind_of(move),
                     "done" if failure is None else "not done", time.monotonic() - acting)
        except StoppedWhileAway:
            await run.stopped()
            return

        if failure is not None and move.changes:
            # Not done, and not "stuck": tried, and not confirmed. Said so,
            # naming the site's own button, not the final screen's answer.
            label = pressed(move)
            who = task.confirms.who if task.confirms else "site"
            await give_up(voice.not_confirmed(label, who), unconfirmed=True)
            return

        if failure is not None:
            ask_next = True
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
        ask_next = False
        if keep is not None:
            # Only now: a password that did not sign anyone in is not kept.
            run.vault.put(page.url, keep)
        completed.append(move)
        history.append(move.instruction)
        # Anything typed on a page we have since left is not ours to police.
        filled = [f for f in filled if f.url == page.url]
        # A choice from the list a box opened commits the box: what it holds
        # now is the choice, not the letters typed to find it (2026-11-04).
        filled = await recommitted(page, filled, move, task.about.holds)
        filled += await record_fills(page, move)

    # A planner that settled something the task could not know at the
    # start — which course, chosen on the portal — says so before the end
    # is checked (`plan.CoursePlanner.settled`, 2026-10-16).
    settle = getattr(planner, "settled", None)
    if settle is not None:
        task = settle(task)

    # What was read before this last look, to compare it with (2026-10-16).
    read_before = {name: list(values) for name, values in found.items()}
    _, final, _ = await perceive(page)
    findings = findings_in(final, task, found, rows)
    # A goal with no plan (2026-11-13) ends with the answer the person agreed
    # was it, and only if the page still says it, word for word.
    answer = getattr(planner, "answer", None)
    if getattr(planner, "must_answer", False):
        if answer is None:
            await give_up(last_failure or getattr(planner, "stuck_reason", None)
                          or voice.AI_COULD_NOT)
            return
        if not final.content.shows(answer.value):
            await give_up(voice.ANSWER_CHANGED, unconfirmed=True)
            return
        findings = [answer]
    # A task with named values is checked here even without a success
    # expectation, so a declared value can never go unchecked.
    unfinished = (
        unmet(final, task, seen)
        if task.success is not None or task.about.holds or task.about.shows
        else None
    )
    if unfinished is not None:
        # Prefer the concrete reason the last move failed over the generic
        # "ran out of steps", which says nothing a user could act on; and a
        # planner's own words for it over that, when it has some (2026-11-04).
        await give_up(last_failure or getattr(planner, "ran_out", None)
                      or f"I ran out of steps before finishing. {unfinished}")
        return

    # Read again before closing (2026-10-16): the page has to still say what
    # is about to be shown, or no answer is shown.
    if answer_changed(read_before, final, task):
        await give_up(voice.ANSWER_CHANGED, unconfirmed=True)
        return

    # A change is done only when the site says so, on the page (2026-10-16).
    confirmation: str | None = None
    confirmed: tuple[str, str | None] | None = None
    if task.confirms is not None:
        headings = [h.text for h in final.content.headings]
        if not any(task.confirms.heading in text for text in headings):
            changed = next((m for m in reversed(completed) if m.changes), None)
            label = pressed(changed) if changed else task.confirms.heading
            who = task.confirms.who if task.confirms else "site"
            await give_up(voice.not_confirmed(label, who), unconfirmed=True)
            return
        reference = (final.content.value_for(task.confirms.reads)
                     if task.confirms.reads else None)
        confirmation = voice.portal_says(task.confirms.heading, task.confirms.reads,
                                         reference, task.confirms.who)
        confirmed = (next(text for text in headings if task.confirms.heading in text),
                     reference)
    # And what the site says against it, in its own sentence (2026-10-16):
    # "not final until tuition and fees are paid". Only if it says it.
    caveat_said = (await site_sentence(page, task.confirms.caveat)
                   if task.confirms is not None and task.confirms.caveat else None)
    heading = task.heading
    caveat = (voice.site_qualifies(caveat_said, task.confirms)
              if caveat_said and task.confirms else None)
    # A change made on a practice copy, said plainly in place of "That's
    # done." (2026-10-17): "Booked on the practice site.", then "Booking
    # number PR-482193. This was a practice copy, so no real ticket was booked
    # and no money was taken." Ours to say: a change is only ever made on a
    # replica (above). The number is said there, so the site's own words are
    # quoted without it.
    if task.confirms is not None and task.confirms.done and confirmed is not None:
        heading = task.confirms.done
        caveat = voice.practice_copy(task.confirms.reads, confirmed[1],
                                     task.confirms.practice or "")
        # And what the site says against it, kept (2026-10-17): a
        # registration on our copy is still not final until fees are paid.
        # Only a caveat with plain words of its own; a booking's "No real
        # ticket" is what the practice line has just said.
        if caveat_said and task.confirms.caveat_plain:
            caveat = f"{caveat} {voice.site_qualifies(caveat_said, task.confirms)}"
        confirmation = voice.portal_says(task.confirms.heading, who=task.confirms.who)

    # The proof: a still of the page as it is now, what was read ringed.
    proving = time.monotonic()
    try:
        proof, proof_note = await asyncio.wait_for(
            take_proof(page, proof_targets(task, findings, rows, confirmed, caveat_said,
                                           found) if answer is None
                       else [(answer.value, True)]),
            PROOF_DEADLINE_S)
    except asyncio.TimeoutError:
        proof, proof_note = None, voice.NO_PROOF_PICTURE
    log.info("end-of-task picture %s in %.1fs", "taken" if proof else "not taken",
             time.monotonic() - proving)

    # A return that was due when the last step was answered has no next step
    # to arrive with, so it goes out before the ending.
    if rules is not None:
        await run.adapt(rules.end())

    # A planner that remembers runs gets told what actually worked.
    remember = getattr(planner, "finished", None)
    if remember is not None:
        remember(completed)

    completed = TaskCompleted(
            summary=f"{task.goal} {page.url}",
            duration_ms=int((time.monotonic() - run.started) * 1000),
            steps_taken=steps_taken,
            llm_calls=getattr(planner, "calls_made", 0),
            replayed=getattr(planner, "replayed_steps", 0) > 0,
            findings=findings,
            explanation=task.explain(found, seen, rows) if task.explain else None,
            heading=heading,
            scope=task.scope(found, seen, rows) if callable(task.scope) else task.scope,
            confirmation=confirmation,
            caveat=caveat,
            proof=proof,
            proof_note=proof_note,
    )
    log.info("task completed: %d steps, %.1fs", steps_taken, time.monotonic() - run.started)
    if send:
        await connection.send("task.completed", completed)
    return completed


def answer_changed(before: dict[str, list[str]], after: Snapshot, task: "Task") -> bool:
    """Whether the page, read again before closing, says something other than
    what the run read earlier and is about to show (2026-10-16). A label the
    page no longer has is not a difference — the value was read on a page
    since left — and is said instead by there being no picture of it."""
    for answer in task.about.finds:
        earlier = before.get(answer.name)
        now = [v for v in (part_of(value, answer.part)
                           for value in after.content.values_for(answer.reads)) if v]
        if earlier and now and set(earlier) != set(now):
            return True
    return False


def proof_targets(task: "Task", findings: list[Finding], rows: list[dict[str, str]],
                  confirmation: tuple[str, str | None] | None,
                  caveat: str | None = None, found: dict[str, list[str]] | None = None,
                  ) -> list[tuple[str, bool] | tuple[str, bool, bool]]:
    """What to ring on the closing picture: each result's row, by its first
    value, when there are several; otherwise each value shown, on its own; a
    change's confirmation heading, the row its reference is in, and the
    paragraph its caveat is quoted from."""
    targets: list[tuple[str, bool] | tuple[str, bool, bool]] = []
    # Several results: each one's row. One result — a bill — its values
    # themselves, so the ring is round the amount, not round the whole line.
    # Found by the page's own text, not the plain words they are shown in.
    if len(rows) > 1 and findings:
        targets += [(row[findings[0].label], True) for row in rows
                    if row.get(findings[0].label)]
    else:
        targets += [(value, False) for finding in findings
                    for value in (found or {}).get(finding.label, finding.values)]
    if confirmation is not None:
        heading, reference = confirmation
        targets.append((heading, False))
        if reference:
            targets.append((reference, True))
    if caveat:
        targets.append((caveat, False, True))
    seen: set[tuple] = set()
    return [t for t in targets if not (t in seen or seen.add(t))]


async def take_proof(page: Page, targets: list[tuple[str, bool] | tuple[str, bool, bool]]
                     ) -> tuple[Proof | None, str | None]:
    """A still of the page with every target ringed, or why there is none.

    The page is scrolled so the first ring is in view, captured at the frozen
    viewport, and scrolled back. Password boxes are painted over, as for every
    picture of the page (`send_preview`)."""
    if not targets:
        return None, None
    try:
        found = await page.evaluate(RINGS_JS, [list(t) for t in targets])
    except PlaywrightError:
        return None, voice.NO_PROOF_PICTURE
    boxes = [b for b in found if b]
    if not boxes:
        return None, voice.NOT_ON_THIS_PAGE
    before = await page.evaluate("[scrollX, scrollY]")
    top = min(b["y"] for b in boxes)
    await page.evaluate(f"window.scrollTo(0, {max(0, int(top) - 40)})")
    try:
        at = await page.evaluate("[scrollX, scrollY]")
        shot = await capture_site(page, mask=PASSWORD_BOXES, mask_colour=MASK_COLOUR)
    except PlaywrightError:
        return None, voice.NO_PROOF_PICTURE
    finally:
        try:
            await page.evaluate(f"window.scrollTo({before[0]}, {before[1]})")
        except PlaywrightError:
            pass
    rings = []
    for b in boxes:
        x, y = int(b["x"] - at[0]), int(b["y"] - at[1])
        if y + b["h"] <= 0 or y >= 800:
            continue
        rings.append(Highlight(x=x, y=y, w=int(b["w"]), h=int(b["h"])))
    if not rings:
        return None, voice.NOT_ON_THIS_PAGE
    return Proof(screenshot=base64.b64encode(shot).decode("ascii"), rings=rings,
                 caption=voice.PROOF_CAPTION), None


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
    page: Page, move: Move, input_values: dict[str, str], strategy: int, before: Snapshot,
    ready: Callable[[], Awaitable[None]] | None = None,
) -> str | None:
    """Run a Move's operations, then verify. None on success.

    `ready` is awaited before each operation, so a window put away partway
    through a step stops the next action rather than the step (`_Run.ready`).
    """
    for operation in move.operations:
        if ready is not None:
            await ready()
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
        if operation.kind == "select":
            chosen = await verify_chosen(page, element_id, value)
            if chosen is not None:
                return chosen

    # Typing and key presses change no URL, title or label, so a move made
    # only of those is verified by the read-back above and nothing else.
    # Demanding a page change here would fail every correctly typed field. A
    # move that clicks, or that states an expectation of its own, still has to
    # prove it on the page — and so does a move of presses alone, which has no
    # read-back to stand on.
    kinds = {operation.kind for operation in move.operations}
    only_input = kinds <= {"fill", "press", "select"} and bool(kinds & {"fill", "select"})
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


async def recommitted(page: Page, filled: list[FilledValue], move: Move,
                      holds: tuple[FieldValue, ...] = ()) -> list[FilledValue]:
    """What the boxes hold after a move that chose from a list.

    Typing "LAH" and choosing "LAHORE CANTT" from the list it opens is one
    answer given in two moves, and the box then holds the choice. A box whose
    typed words are in the chosen option's words is read again, and holds
    that from now on; every other box is checked as before. A planner that
    types and chooses in one move never needed this (`TripPlanner` declares
    the station it chose); one that keeps them apart does (`routine_plan`).

    **Never past what the task declares.** A box the task names a value for
    (`About.holds`) is recommitted only to a value that is that value. A
    search typed toward Multan when the person asked for Peshawar still lapses
    at the next look, and the wrong search is never sent (`test_trip.py`).
    """
    chosen = [o.target.label.casefold() for o in move.operations
              if o.kind == "click" and o.target.role == "option" and o.target.label]
    if not chosen or not filled:
        return filled
    elements, _, _ = await perceive(page)
    kept: list[FilledValue] = []
    for record in filled:
        typed = record.value.casefold().strip()
        if not typed or not any(typed in label for label in chosen):
            kept.append(record)
            continue
        element_id = pick(elements, Target(record.role, record.label))
        try:
            now = (await resolve(page, elements, element_id).input_value()
                   if element_id is not None else None)
        except PlaywrightError:
            now = None
        declared = [held for held in holds if held.label == record.label]
        if now and all(held.accepts(now) for held in declared):
            kept.append(replace(record, value=now))
        else:
            kept.append(record)
    return kept


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
    if operation.kind not in ("fill", "select"):
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


#: What a list the page draws itself holds: its value and the chosen option's words.
CHOSEN_JS = "s => [s.value, s.selectedOptions[0] ? s.selectedOptions[0].text.trim() : '']"


async def verify_chosen(page: Page, element_id: int, expected: str) -> str | None:
    """A choice from a list is checked by reading back what the list holds,
    as a typed value is (2026-11-04): choosing changes nothing perception
    compares, so the page-level check would call it no change."""
    elements, _, _ = await perceive(page)
    if not any(e.id == element_id for e in elements):
        return None  # the page moved on; the page-level check will judge that
    try:
        held = await resolve(page, elements, element_id).evaluate(CHOSEN_JS)
    except PlaywrightError as error:
        return f"could not read what the list holds: {str(error).splitlines()[0]}"
    if expected in held:
        return None
    return f"expected the list to hold {expected!r}, it holds {held[1]!r}"


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
