"""The hardcoded registration plan.

September's walking skeleton has no LLM (see CLAUDE.md). This module stands
in for one: it decides, ahead of time, which element to act on at each step
and what the page should look like afterwards. When the LLM arrives it
replaces `Target` matching with a model call — everything downstream, the
integer ids and the verification, stays the same.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from backend.orchestrator import voice
from backend.orchestrator.voice import actions
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
    # `names` loosens the match to "the field's value contains this", ignoring
    # case. It is for a value the person gave in their own words and the page
    # holds in its: they ask for "Lahore", the site's station is `LAHORE JN`,
    # and which station it is was settled by asking them. The date stays exact.
    names: bool = False

    def accepts(self, actual: str) -> bool:
        if self.names:
            return self.equals.casefold() in actual.casefold()
        return actual == self.equals


@dataclass(frozen=True)
class Shown:
    """Something the page has to have said, under one of its own labels.

    For a value the person named that is in no field by the time the run
    ends: the bill's reference number is typed on the first page and the run
    finishes two pages later, and a course is chosen by pressing a button.
    What is left to check is what the site says back — `REF NO` on the bill,
    `Course` on the confirmation — so that is what is checked.

    Seen at any point in the run, not only on the last page, for the same
    reason findings are remembered: the page that says it is often not the
    page the run ends on. `says` is matched inside the value, ignoring case,
    because a site adds its own words ("CS-401 section 001").
    """

    reads: str
    says: str

    def met_by(self, values: list[str]) -> bool:
        return any(self.says.casefold() in value.casefold() for value in values)


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
    # Which value of the cell, when the page prints two in one: the live
    # train table's `Time` is `08:04 06:20` — leaves, then arrives
    # (EVALUATION.md, 2026-09-07). None: the whole cell. A cell without that
    # many values gives nothing, never a value worked out from the others.
    part: int | None = None
    # How a value is said on screen, in plain words (2026-10-16): the bill's
    # `14,382` as "Rs 14,382", its `15-09-2026` as "15 September 2026". Only
    # what is shown: what is checked, compared and ringed is the page's own
    # text. None: as the page wrote it.
    plain: Callable[[str], str] | None = None


def part_of(cell: str, part: int | None) -> str:
    """One value of a cell that holds several, or the cell; "" if it has not
    got that many."""
    if part is None:
        return cell
    values = cell.split()
    return values[part] if part < len(values) else ""


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
    number — cannot be a `holds` entry. `shows` is for that case: what the
    site said back about the value, on whichever page it said it (`Shown`).
    """

    holds: tuple[FieldValue, ...] = ()
    finds: tuple[Answer, ...] = ()
    shows: tuple[Shown, ...] = ()
    # What a whole row of `finds` says that no one cell does, said in it:
    # a train arriving the day after it leaves (`voice.arrival`, 2026-10-15).
    # Applied to the rows only, after they are read; never to what is checked.
    per_row: Callable[[dict[str, str]], dict[str, str]] | None = None


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
    # Some element's label contains this, ignoring case. For a step that types
    # part of a name and needs the page to have offered something for it —
    # a station list answering "LAHORE" — before anything can be chosen.
    label_like: str | None = None
    # The step waits on a list the site fetches — a station list answering a
    # typed name — so it is given `loop.LIST_TIMEOUT_S` to appear instead of
    # the ordinary window. Not a condition on the page: it says how long to
    # look, and the conditions above say what for. Until 2026-09-30 such a
    # step had the same five seconds as a click, and on the live site a list
    # that took longer was reported as a place with no stations.
    list_opens: bool = False
    # Readable content, from perception's second channel.
    content_says: str | None = None
    rows_at_least: int | None = None


@dataclass(frozen=True)
class FinalRead:
    """One detail on a final screen (2026-10-16): its name for the person,
    and where the page states it — the value beside the page's own label
    `reads`, or, in a table of many rows, the cell under `reads` in the row
    whose cells match `row` ((header, value) pairs). Read at the moment the
    final screen goes up; a detail the page does not state means no final
    screen and nothing done. `plain` says it in plain words, as `Answer.plain`
    does. `fixed` is a detail known without reading — the label of the button
    a model-planned move would press — and is shown as it is."""

    name: str
    reads: str = ""
    plain: Callable[[str], str] | None = None
    row: tuple[tuple[str, str], ...] = ()
    fixed: str | None = None


@dataclass(frozen=True)
class PlanStep:
    instruction: str
    detail: str
    operations: list[Operation]
    expect: Expectation
    fields: list[StepField] = field(default_factory=list)
    actions: list[StepAction] = field(default_factory=list)
    # Which of the task's stages this step is in (`voice.*_STAGES`).
    stage: int | None = None
    # Safe to do without a press: it only fills in or looks something up, and
    # the person has already decided what (2026-10-14). Never a step that
    # pays, books, registers or changes a record, and never one that needs
    # the person to type or choose. `doing` is its line on the checklist.
    safe: bool = False
    doing: str | None = None
    # Changes a record (2026-10-16): registers, books, submits. Tried once and
    # never retried a second way — a second press could make the change twice
    # — and "done" only once the site's confirmation is on the page.
    changes: bool = False
    # What its final screen shows (2026-10-16): only for a step that
    # `changes`, which is never acted on without one (CLAUDE.md, the final-step
    # rule). Empty: the final screen names the button it would press.
    final: tuple[FinalRead, ...] = ()
    # The final screen's two answers, when the step names them: do it, don't.
    final_answers: tuple[str, str] | None = None


@dataclass(frozen=True)
class Confirmation:
    """What the site shows when a change it was asked to make has been made:
    a heading, and the reference it gives, by the page's own label. Read from
    the final page and quoted on the closing screen (2026-10-16)."""

    heading: str
    reads: str | None = None
    # A few words of the site's own warning about what was done — "not final
    # until" — whose whole sentence is quoted beside the confirmation
    # (2026-10-16): the portal confirms a registration and, in the same
    # breath, says it is not final until fees are paid. Never said unless the
    # page says it.
    caveat: str | None = None
    # Who is quoted: "The portal says…", "The site says…" (2026-10-16).
    who: str = "portal"


def course_final(course: str) -> tuple[FinalRead, ...]:
    """What registering for `course` shows on its final screen (2026-10-16):
    the course's own row on the portal's list — its title, when it meets,
    who teaches it, where, and its credit hours — found by its subject and
    number (`CS-401` is subject `CS`, number `401`)."""
    subject, _, number = course.partition("-")
    row = (("Subj", subject), ("Crse", number))
    return (
        FinalRead("Course", fixed=course),
        FinalRead("Title", "Title", row=row),
        FinalRead("Days", "Days", row=row),
        FinalRead("Time", "Time", row=row),
        FinalRead("Teacher", "Instructor", row=row),
        FinalRead("Room", "Room", row=row),
        FinalRead("Credit hours", "Cr", row=row),
    )


def register_step(course: str, stage: int | None = 2) -> PlanStep:
    """The step that registers: a change, behind its final screen."""
    return PlanStep(
        instruction=voice.final_register(course),
        detail="This registers you for the course.",
        actions=actions(f"Register for {course}"),
        operations=[Operation("click", Target("button", f"Register for {course}"))],
        expect=Expectation(url_contains="/register", title_contains="Registration Confirmed"),
        stage=stage,
        changes=True,
        final=course_final(course),
        final_answers=(voice.REGISTER_IT, voice.DONT_REGISTER),
    )


def registration_plan(course: str) -> list[PlanStep]:
    """The registration plan for one course, by its code as the portal prints
    it (`CS-401`). The person says which; nothing here picks one for them."""
    return [*SIGN_IN_AND_CLEAR, register_step(course)]


SIGN_IN_AND_CLEAR: list[PlanStep] = [
    PlanStep(
        instruction="Let me sign you in first.",
        detail="Fictional State University student portal.",
        fields=[
            StepField(id="username", label="Student ID or Username", type="text", value=""),
            StepField(id="password", label="Password", type="password", value=""),
        ],
        actions=actions("Sign in"),
        operations=[
            Operation("fill", Target("textbox", "Student ID or Username"), "username"),
            Operation("fill", Target("textbox", "Password"), "password"),
            Operation("click", Target("button", "Sign In")),
        ],
        expect=Expectation(url_contains="/courses"),
        stage=0,
    ),
    PlanStep(
        instruction="The portal opened a notice. I'll close it.",
        detail="The portal opened a notice about the add/drop deadline.",
        actions=actions("Close it"),
        operations=[Operation("click", Target("button", "Close"))],
        expect=Expectation(label_gone="Close"),
        stage=0,
        safe=True,
        doing=voice.DOING_NOTICE,
    ),
]

# The plan every recorded registration number was measured on. Its last step
# carries CS-401's own timetable line, which only a plan written for one
# course can know; `registration_plan` is what a person's request runs.
REGISTRATION_PLAN: list[PlanStep] = [
    *SIGN_IN_AND_CLEAR,
    # Registers (2026-10-16): behind its final screen, like every change. Its
    # timetable line is the final screen's details now, read from the page.
    register_step("CS-401", stage=None),
]


#: How a course's button names it, on the portal's list: "Register for CS-401".
REGISTER_FOR = "Register for "


def _plain_code(code: str) -> str:
    """A course code for comparing: "cs 401", "CS401" and "CS-401" alike."""
    return "".join(ch for ch in code.upper() if ch.isalnum())


class CoursePlanner:
    """Registers for a course the portal offers (2026-10-16).

    Signs in and clears the portal's notice, as the fixed plan does. Then it
    reads the courses the portal lists — the "Register for CS-401" buttons —
    and asks which one, from those: a course that is not offered is caught at
    the question, not at the button. A course the person named that is on the
    list is not asked about again; one that is not is asked about, with a
    note saying so. Registering always asks: it is the step that changes a
    record.
    """

    calls_made = 0
    stuck_reason: str | None = None
    marks_changes = True

    def __init__(self, course: str | None) -> None:
        #: What the person named, if anything, as they wrote it.
        self.named = course
        #: The course chosen from the portal's list, as the portal writes it.
        self.chosen: str | None = None
        #: The portal's own list, read once signed in.
        self.offered: list[str] = []
        self._signing_in = HardcodedPlanner(list(SIGN_IN_AND_CLEAR))
        self._asked = False
        self._note: str | None = None
        self._registered = False

    async def next_move(self, elements, history, setback):
        from backend.orchestrator.loop import Move

        if self._signing_in._index < len(self._signing_in._steps):
            return await self._signing_in.next_move(elements, history, setback)
        if self.chosen is None:
            self.offered = [e.label[len(REGISTER_FOR):] for e in elements
                            if e.role == "button" and e.label.startswith(REGISTER_FOR)]
            if not self.offered:
                self.stuck_reason = voice.NO_COURSES
                return None
            if self.named and not self._asked:
                self.chosen = self._find(self.named)
                if self.chosen is None:
                    self._note = voice.course_not_offered(self.named)
            if self.chosen is None:
                self._asked = True
                return self._question(Move)
        if not self._registered:
            self._registered = True
            [step] = registration_plan(self.chosen)[len(SIGN_IN_AND_CLEAR):]
            return Move(instruction=step.instruction, detail=step.detail,
                        operations=step.operations, expect=step.expect, fields=step.fields,
                        actions=step.actions, stage=step.stage, changes=step.changes,
                        final=step.final, final_answers=step.final_answers)
        return None

    def _question(self, Move):
        if len(self.offered) <= voice.MAX_CHOICES:
            fields, answers = [], voice.choices(self.offered)
        else:
            fields = [StepField(id="course", label=voice.FIELD_COURSE, type="choice",
                                value="", options=list(self.offered))]
            answers = voice.actions(voice.USE_COURSE)
        note, self._note = self._note, None
        return Move(instruction=voice.ASK_COURSE, detail=voice.COURSES_OFFERED,
                    operations=[], expect=Expectation(), fields=fields, actions=answers,
                    question=True, kind="type", stage=1, note=note)

    def _find(self, words: str) -> str | None:
        wanted = _plain_code(words)
        return next((code for code in self.offered if _plain_code(code) == wanted), None)

    def answered(self, action_id: str, input_values: dict[str, str]) -> None:
        """The person's answer to which course: a button, or the list."""
        index = action_id.removeprefix(voice.CHOICE_PREFIX)
        if index.isdigit() and int(index) < len(self.offered):
            self.chosen = self.offered[int(index)]
            return
        typed = (input_values.get("course") or "").strip()
        self.chosen = self._find(typed)
        if self.chosen is None:
            self._note = (voice.course_not_offered(typed) if typed
                          else voice.COURSE_NOT_CAUGHT)

    def settled(self, task):
        """The task, with the course the person chose in it: what the
        confirmation has to name, and the sentence that says so."""
        from dataclasses import replace

        if self.chosen is None:
            return task
        return replace(task, about=About(shows=(Shown(reads="Course", says=self.chosen),)),
                       scope=voice.explain_course(self.chosen))


class HardcodedPlanner:
    """Walks REGISTRATION_PLAN. The deterministic A/B arm and demo fallback."""

    calls_made = 0
    stuck_reason: str | None = None
    #: Its plans say which steps change something (`PlanStep.changes`), so
    #: the loop does not guess from a button's words (2026-10-16).
    marks_changes = True

    def __init__(self, steps: list[PlanStep]) -> None:
        self._steps = list(steps)
        self._index = 0

    def coming(self) -> list[str]:
        """The checklist lines after the move just given: the safe steps that
        follow it, up to the first that will ask (2026-10-15)."""
        lines: list[str] = []
        for step in self._steps[self._index:]:
            if not step.safe:
                break
            lines.append(step.doing or step.instruction)
        return lines

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
            stage=step.stage,
            safe=step.safe,
            doing=step.doing,
            changes=step.changes,
            final=step.final,
            final_answers=step.final_answers,
        )
