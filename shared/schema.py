"""SIMBA message contract, mirrored from CONTRACT.md.

Keep field names identical to shared/schema.ts and to CONTRACT.md. Additive
optional fields are fine; renames and removals require all three owners and
a version bump (see CLAUDE.md).
"""

from __future__ import annotations

from typing import Dict, Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel

# --- Shared vocab -----------------------------------------------------------

State = Literal["thinking", "acting", "waiting", "stuck"]
Level = Literal[1, 2, 3]
ActionKind = Literal["primary", "secondary", "destructive"]
InputMode = Literal["text", "voice"]
# What a step is about, for the icon beside it (2026-10-07).
StepKind = Literal["date", "place", "choose", "type", "read", "confirm"]

MessageType = Literal[
    # backend -> frontend
    "task.started",
    "state.changed",
    "history.offered",
    "goal.answered",
    "step.presented",
    "step.failed",
    "load.updated",
    "page.preview",
    "help.requested",
    "task.completed",
    "task.failed",
    "error",
    # frontend -> backend
    "task.start",
    "step.response",
    "level.override",
    "trust.requested",
    "task.cancel",
    "telemetry",
    # Pending agreement with the rest (2026-10-18): the person renaming,
    # moving or removing one of their own tiles, or clearing them all.
    "tile.change",
    # Pending agreement with the rest (2026-11-04, "Show me once"): a helper
    # showing SIMBA a task once, and a routine saved to a file or read back
    # from one. backend -> frontend: "teach.watching", "routine.file".
    # frontend -> backend: "teach.start", "teach.answer", "routine.export",
    # "routine.import".
    "teach.watching",
    "routine.file",
    "teach.start",
    "teach.answer",
    "routine.export",
    "routine.import",
    # Pending agreement (2026-11-13, the advisor's direction): a website added
    # to the list on the home screen.
    "site.add",
    # Pending agreement (2026-11-13): the real page handed to the person — to
    # pay, or to pass a check for a person — and their word that they are done.
    "handover",
    "handover.done",
]

# --- Backend to frontend -----------------------------------------------------


class TaskStarted(BaseModel):
    goal: str
    estimated_steps: int
    # Additive and optional (2026-10-14). The task's stages by name — trains:
    # From, To, Day, Search, Trains — shown in place of a count. Fixed for the
    # task: a question asked again stays in its stage. Empty: no stages shown.
    stages: List[str] = []


class StateChanged(BaseModel):
    state: State


class PastGoal(BaseModel):
    """Something this person asked for before, and where they asked it."""

    goal: str
    site: str
    # Additive and optional (2026-10-16). The goal in a few words, for the home
    # screen's one line — "Bill ending 7890", "Trains Lahore Cantt to
    # Rawalpindi" — built by the backend from what the goal spells out
    # (`voice.short_label`). Absent: the goal's own words are shown.
    label: Optional[str] = None


class PersonalTile(BaseModel):
    """One of the person's own tiles (2026-10-18): a task they kept, by the
    name they gave it. Its details stay in the backend, encrypted; the overlay
    runs it by `id` (`task.start.tile`)."""

    id: str
    label: str
    flow: "FlowName"


class TaughtTile(BaseModel):
    """A routine a helper showed SIMBA once (2026-11-04), as a tile on the home
    screen: its name, and the site it runs on, by its address's host. Its
    moves stay in the backend, encrypted; the overlay runs it by `id`
    (`task.start.routine`)."""

    id: str
    label: str
    site: str


How = Literal["built-in", "ai", "taught"]


class CatalogueTask(BaseModel):
    """Something SIMBA can do on a listed website (2026-11-13), and how:
    `built-in` runs a written plan (`flow`), `ai` asks the AI planner to work
    it out on the live page, `taught` runs a routine a helper showed
    (`routine`, its id). Pressing it sends `goal` with `site`."""

    label: str
    goal: str
    how: How
    flow: Optional["FlowName"] = None
    routine: Optional[str] = None
    # Additive and optional (2026-11-13). A routine taught on another website
    # of the same genre: that website's name. Pressed here, the routine runs on
    # this website (`task.start.routine` with `site`).
    taught_on: Optional[str] = None


class CatalogueSite(BaseModel):
    """A website SIMBA can work with, listed on the home screen's left by
    genre (2026-11-13). `added`: added in the app, not shipped."""

    id: str
    name: str
    address: str
    genre: str
    tasks: List[CatalogueTask]
    added: bool = False


class HistoryOffered(BaseModel):
    """What the home screen offers instead of an empty box.

    Sent once, when the socket opens, before any task. A frontend that ignores
    it sees exactly what it saw before.
    """

    goals: List[PastGoal]
    # Additive and optional (2026-10-18). The person's own tiles, in their
    # order. Also sent again after each `tile.change`. Absent: none.
    tiles: Optional[List[PersonalTile]] = None
    # Additive and optional (2026-11-04). The routines helpers have shown,
    # as tiles, in the order they were kept. They share the home screen's row
    # of three with `tiles`. Absent: none.
    routines: Optional[List[TaughtTile]] = None
    # Additive and optional (2026-11-13). The websites SIMBA can work with, in
    # the list's order, and the genres in theirs. Also sent again after each
    # `site.add`. Absent: no list, and the home screen is as it was.
    sites: Optional[List[CatalogueSite]] = None
    genres: Optional[List[str]] = None


FlowName = Literal["registration", "billing", "railways"]
# "not_yet" (2026-11-13, additive): a goal on a website SIMBA has no way to do
# yet. The overlay offers a helper's "Show me once" on that website (`site`).
# "not_allowed" (2026-11-13, additive): the website's robots.txt asks programs
# not to use that page, so SIMBA does not.
AnswerKind = Literal["greeting", "unsupported", "clarify", "not_yet", "not_allowed"]


class GoalAnswered(BaseModel):
    """A typed goal that did not start a task, and what to offer instead.

    Added 2026-09-21, pending ratification (CONTRACT.md). Carries no words:
    the overlay writes every sentence from `copy.ts`, so the mock and the
    backend cannot disagree about what the person reads.
    """

    kind: AnswerKind
    goal: str
    flows: List[FlowName]
    # Additive and optional (2026-11-13). The website the goal was for, when
    # there was one: where "Show me once" opens for `not_yet`.
    site: Optional[str] = None


class Finding(BaseModel):
    """A value the task was looking for, and the name to show it under.

    `label` is for a person to read, not the page's own column heading: the
    billing replica calls the amount `P/WITHIN`, and nobody outside a billing
    department knows what that means. The plan supplies the readable name.

    Two forms of the same answer, because two screens want different things:

      * `value` is one line. A results table has a row per result, so it is
        the values joined, and past four it counts the rest — the step screen
        shows a finding while the run is still going, in large type, beside
        the instruction, and twenty values there is clutter.
      * `values` is every one of them, in the order the page listed them. The
        closing screen is the answer and shows them all.

    `values` is optional and additive: a sender that does not set it is read
    as `[value]`, which is what every finding was before 2026-09-19.

    `values` drops a repeated value, so two findings' lists cannot be paired by
    position. `rows`, on the first finding of a message only, is every result
    whole: one cell per finding in that message, in their order, repeats kept,
    "" where the page's row had nothing. Optional and additive (2026-10-05);
    empty when the values did not come from a table.
    """

    label: str
    value: str
    values: List[str] = []
    rows: List[List[str]] = []


class StepField(BaseModel):
    id: str
    label: str
    type: str
    value: str
    # Additive and optional (2026-10-06). The answers a field accepts, when
    # they are a known list — the site's own stations, read before anything
    # on it is touched. The overlay shows the ones that match what has been
    # typed so far. Empty means any text.
    options: List[str] = []


class StepAction(BaseModel):
    id: str
    label: str
    kind: ActionKind


class Detail(BaseModel):
    """One thing a final screen shows, by name, as the page states it
    (2026-10-16): `{"label": "Fare", "value": "Rs 3,250"}`."""

    label: str
    value: str


class StepPresented(BaseModel):
    step_index: int
    step_total: int
    instruction: str
    detail: str
    fields: List[StepField]
    actions: List[StepAction]
    requires_confirmation: bool
    # What has been found so far, if the task was looking for anything.
    # Additive and optional: a task that reads nothing sends an empty list.
    findings: List[Finding] = []
    # Additive and optional (2026-10-07). What kind of thing the step is
    # about, so the overlay can put one plain icon beside it. Absent: no icon.
    step_kind: Optional[StepKind] = None
    # Additive and optional (2026-10-14). Which of `task.started.stages` this
    # step is in, by position. Absent: the stage before it.
    stage: Optional[int] = None
    # Additive and optional (2026-10-14). What was wrong with the last answer,
    # in one kind sentence, beside the question asked again — "I couldn't find
    # a station called Narnia." The overlay clears it once a valid answer is
    # chosen. Absent: nothing was wrong.
    note: Optional[str] = None
    # Additive and optional (2026-10-15). On a checklist line
    # (`requires_confirmation: false`): the lines SIMBA expects to do by itself
    # after this one, in order, so the person can see what is next. Empty:
    # nothing more it knows of, or not a checklist line.
    coming: List[str] = []
    # Additive and optional (2026-10-16). Set on the final screen before a
    # move that books, pays, registers or changes a record: the key details
    # of what will happen, read from the page at that moment. The instruction
    # says it in plain words; the actions are exactly two, do it
    # (`"confirm"`) and don't (`"decline"`), neither the default. Absent: an
    # ordinary step.
    final: Optional[List[Detail]] = None
    # Additive and optional (2026-11-04). What a helper has just shown SIMBA,
    # read back in plain words, one line each, in order, before it is kept:
    # "Type 04141234567890 in Reference No.", "Press Check Bill.". Absent: an
    # ordinary step.
    routine: Optional[List[str]] = None
    # Additive and optional (2026-11-13). Which AI provider worked this move
    # out, said small under the step: "Gemini", "Groq". Absent: a written
    # plan, a routine a helper showed, or a replayed run.
    worked_out_by: Optional[str] = None


class StepFailed(BaseModel):
    """A step did not work, and the run is carrying on past it.

    Emitted where the loop previously said nothing at all. A first failure is
    absorbed — the planner is told and may choose differently — and until this
    existed the frontend saw step N, then step N+1, with no way to tell a
    skipped step from a completed one. That is not a hypothetical: it is how
    the first live railways run was misdiagnosed for a day.

    Not the same thing as `error`, which is the harness failing. This is the
    task failing at something and continuing, which the user should see
    quietly rather than be alarmed by.
    """

    step_index: int
    instruction: str  # what was attempted, in the words the user was shown
    reason: str  # why it did not work
    strategies_tried: int


class LoadUpdated(BaseModel):
    score: float
    level: Level
    reason: str


class Highlight(BaseModel):
    x: int
    y: int
    w: int
    h: int


class PagePreview(BaseModel):
    screenshot: str
    highlight: Highlight
    caption: str


class Proof(BaseModel):
    """A still of the real page at the end of a task, with what was read
    ringed (2026-10-16): the closing screen's "See it on the real page"."""

    screenshot: str
    rings: List[Highlight]
    caption: str


class HelpRequested(BaseModel):
    reason: str
    suggestion: str
    # Additive and optional (2026-10-16). Set when a step that changes
    # something was tried and the site did not confirm it: not "stuck", and
    # the reason is the one thing the person must read.
    unconfirmed: bool = False
    # Additive and optional (2026-11-13). The AI planner could not do a goal
    # on this website: the overlay offers a helper's "Show me once" there.
    teach_site: Optional[str] = None


class HandOver(BaseModel):
    """The real page, handed to the person (2026-11-13, pending agreement).

    `reason` is `payment` — card or bank details, a one-time code, or the
    press that pays — or `check`: a CAPTCHA or a check that a person is there.
    SIMBA never does either. The overlay steps aside to a bar with `sentence`
    and shows the website below it, as for "Show me once", until the person
    says they have finished (`handover.done`) or stops. Nothing they type is
    read, logged or kept. `site` is the page's host, for the bar."""

    reason: Literal["payment", "check"]
    sentence: str
    site: str


class TaskOffer(BaseModel):
    """What can follow an answer, on our replicas (2026-10-16): a quiet
    second button on the closing screen. Pressed, the overlay sends a
    `step.response` whose `action_id` is `id`."""

    id: str
    label: str


class KeepOffer(BaseModel):
    """Offered once on a closing screen (2026-10-18): keep this task as a tile
    on the home screen, under `label`. Pressed, the overlay sends a
    `step.response` whose `action_id` is "keep" and whose `input_values` has
    the name as `label`."""

    label: str


class TaskCompleted(BaseModel):
    summary: str
    duration_ms: int
    steps_taken: int
    llm_calls: int
    replayed: bool
    # The answer, when the task had one. A run that ends without saying what
    # it found has not finished from the user's side of the screen.
    findings: List[Finding] = []
    # One plain sentence above the result, saying what it means — "There are
    # 3 trains. The fastest takes 6 hours 3 minutes." Built by the backend
    # only from values the page returned (`voice.explain_*`). Optional and
    # additive (2026-10-03): absent when there is nothing it can say safely.
    explanation: Optional[str] = None
    # Additive and optional (2026-10-14). What the results are for, above them:
    # "Lahore Cantt to Karachi Cantt, Thursday 15 October". From what the
    # person asked and agreed, never from the page. Absent: no heading.
    heading: Optional[str] = None
    # Additive and optional (2026-10-16). The closing screen's last line: what
    # was done, and what was not — "I only looked up times. I did not book a
    # ticket or pay for anything." From `voice.py`, never from a model.
    scope: Optional[str] = None
    # Additive and optional (2026-10-16). For a task that changed something:
    # the site's own confirmation, quoted — 'The portal says "Registration
    # Confirmed", with confirmation number REG-10234-2026.' Sent only when the
    # confirmation is on the page; without it the task is not completed.
    confirmation: Optional[str] = None
    # Additive and optional (2026-10-16). What the site says against that
    # confirmation, its own sentence quoted whole — 'The portal also says
    # "Registration is not final until tuition and fees are paid or a payment
    # plan is in place".' Only when the final page says it.
    caveat: Optional[str] = None
    # Additive and optional (2026-10-16). The real page as it was when the
    # task closed, with every row or value the closing screen shows ringed —
    # taken after the page was read again and found to agree.
    proof: Optional[Proof] = None
    # Additive and optional (2026-10-16). Why there is no `proof`, in plain
    # words, when there is none: never an empty or stale picture instead.
    proof_note: Optional[str] = None
    # Additive and optional (2026-10-16). On our replicas, what can follow
    # the answer — booking one of the trains, paying the bill — as a quiet
    # second button beside "Back to start". The backend keeps the run open
    # for it; going back to start closes the connection.
    offer: Optional[TaskOffer] = None
    # Additive and optional (2026-10-18). Keep this task as one of the
    # person's own tiles: offered once, when it has details worth keeping and
    # is not already a tile. The run stays open for the answer.
    keep: Optional[KeepOffer] = None


class TaskFailed(BaseModel):
    reason: str
    recoverable: bool


class TeachQuestion(BaseModel):
    """The question the bar asks about one typed value (2026-11-04): is it the
    same every time, or should the person be asked each time? `step` is its
    place in what has been kept so far; `label` the box's name as perception
    read it; `value` what the helper typed, never a password's."""

    step: int
    label: str
    value: str
    # Additive and optional (2026-11-04, stage 2): what the question is about,
    # so the bar can say it: something typed, or a day on a calendar.
    kind: Literal["typed", "day"] = "typed"


class TeachWatching(BaseModel):
    """What the bar at the top says while a helper shows SIMBA a task
    (2026-11-04, pending agreement): what has been kept so far, in plain words,
    one line each; the one question open about a typed value; whether the
    helper is now to point at the answer on the page; and a note, when
    something needs saying. Sent whenever any of it changes."""

    lines: List[str]
    question: Optional[TeachQuestion] = None
    pointing: bool = False
    note: Optional[str] = None
    # Additive and optional (2026-11-10). Each thing kept so far in a few
    # words, newest last, for the bar's list ("Typed in Reference No.",
    # "Pressed Check Bill."); a password is "Typed a password." and nothing
    # more. Absent: the bar shows the count and the last of `lines`.
    kept: Optional[List[str]] = None
    # Additive and optional (2026-11-10). True when the last thing could not
    # be taken back: the website is not on the page it was, nothing on it is
    # let through, and the bar offers Start again in place of Undo and Finish.
    start_again: bool = False


class RoutineFile(BaseModel):
    """A routine saved to a file (2026-11-04, pending agreement), in answer to
    `routine.export`: the file's suggested `name` and its whole text, for the
    overlay to save where the helper chooses. Every value the helper typed is
    asked for in it, never kept."""

    label: str
    name: str
    file: str


class ErrorPayload(BaseModel):
    code: str
    message: str


# --- Frontend to backend -----------------------------------------------------


class TaskStart(BaseModel):
    goal: str
    input_mode: InputMode
    # Additive and optional (2026-09-21). Set when the person chose a flow by
    # pressing a card or answering "which did you mean", so the backend runs
    # exactly that rather than classifying the goal again.
    flow: Optional[FlowName] = None
    # Additive and optional (2026-10-14). The person's own setting: ask before
    # every move, as SIMBA always did, rather than running the safe ones as a
    # checklist. Absent: the checklist.
    confirm_each: bool = False
    # Additive and optional (2026-10-18). The level the person chose as
    # comfortable in the welcome, kept on their computer: the level rules
    # start from it, and come back to it after calm steps, instead of 2.
    # Absent: they did not choose, and 2 it is.
    start_level: Optional[Level] = None
    # Additive and optional (2026-10-18). One of the person's own tiles, by its
    # id: the task runs with the details kept with it, and asks only what can
    # change (the day). The goal is the tile's name and is not classified.
    tile: Optional[str] = None
    # Additive and optional (2026-11-04). A routine a helper showed SIMBA, by
    # its id (`history.offered.routines`): run as shown, asking only what the
    # helper said changes. The goal is its name and is not classified.
    routine: Optional[str] = None
    # Additive and optional (2026-11-13). The website to work on: a listed
    # site's address, or one the person typed. With no `flow`, the goal is done
    # there — by a built-in plan if the goal is one and the site is its site,
    # otherwise by the AI planner. Absent: the goal is routed as before.
    site: Optional[str] = None


class TeachStart(BaseModel):
    """Start watching a helper on this address (2026-11-04, pending
    agreement). The overlay steps aside to a bar while it lasts."""

    url: str


class TeachAnswer(BaseModel):
    """The helper's press on the bar (2026-11-04, pending agreement): "same"
    or "ask" for the question about the value at `step`, "finish" when the
    task has been shown, "cancel" to stop watching. Additive (2026-11-10):
    "undo" takes the last thing off, and the website back when that thing
    moved it; "restart" opens the first page again with nothing kept."""

    action: Literal["same", "ask", "finish", "cancel", "undo", "restart"]
    step: Optional[int] = None


class RoutineExport(BaseModel):
    """Save one routine to a file (2026-11-04, pending agreement). Answered
    with `routine.file`."""

    id: str


class RoutineImport(BaseModel):
    """A routine read from a file someone shared (2026-11-04, pending
    agreement). Answered with `history.offered`, with it there when it was
    kept, and an `error` with code `ROUTINE_NOT_READ` saying why when not."""

    file: str


class HandoverDone(BaseModel):
    """The person's answer on the handover bar (2026-11-13, pending
    agreement): `done` — read the page now — or `cancel`, which stops."""

    action: Literal["done", "cancel"]


class SiteAdd(BaseModel):
    """A website added to the home screen's list (2026-11-13, pending
    agreement): what to call it, its address as typed, and its genre. Answered
    with `history.offered` as it now stands, or `error` `SITE_NOT_ADDED` whose
    message is one of `name`, `address`, `listed`, `full`."""

    name: str
    address: str
    genre: str


class TileChange(BaseModel):
    """The person changing their own tiles (2026-10-18), from the home screen.
    Answered with `history.offered`, as it now stands. Pending agreement: a
    new message type."""

    action: Literal["rename", "move", "remove", "clear"]
    id: Optional[str] = None
    label: Optional[str] = None
    # For "move": where it goes, counting from 0 at the left.
    to: Optional[int] = None


class StepResponse(BaseModel):
    step_index: int
    action_id: str
    input_values: Dict[str, str]


class LevelOverride(BaseModel):
    level: Level
    locked: bool
    # Additive and optional (2026-09-25). Who moved the level: the person, or
    # the overlay's guard because a step did not fit. A guard move never
    # becomes the lock. A sender that omits it means the person.
    by: Literal["person", "overflow"] = "person"


class TrustRequested(BaseModel):
    pass


class TaskCancel(BaseModel):
    pass


class Telemetry(BaseModel):
    """Channel B: how the person is getting on with the step on screen.

    Sent on every step response and on a timer while one waits. `answered`
    tells the two apart — additive and optional (added 2026-09-20), so a
    sender that omits it is read as a timer sample.
    """

    step_index: int
    hesitation_ms: int
    cursor_path_ratio: float
    backtracks: int
    rereads: int
    help_presses: int
    answered: bool = False
    # Additive and optional (2026-10-14). Presses of "Read this aloud" on this
    # step: its own signal, not `help_presses`. Absent: none.
    read_aloud: int = 0


# --- Envelope ----------------------------------------------------------------

PayloadT = TypeVar("PayloadT", bound=BaseModel)


class Envelope(BaseModel, Generic[PayloadT]):
    v: Literal[1] = 1
    type: MessageType
    task_id: str
    seq: int
    ts: int
    payload: PayloadT
