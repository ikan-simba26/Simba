"""The person's own details: read from what they typed, and asked for if missing.

Until 2026-09-30 every flow ran on values written into its plan. "Trains to
Rawalpindi tomorrow" searched Lahore Cantt to Karachi Cantt on the 15th of
next month, because that is what the plan said, and the closing screen then
showed real trains for a journey nobody had asked about. The goal was only a
label on somebody else's task.

Three things live here.

  * **Understanding.** What the goal says about the task it was routed to:
    where from, where to and which day; a reference number; a course code.
    The configured model reads it when there is one, with the same short
    timeout as routing, and a keyword-and-date reader does when there is not
    — so it works offline, in the tests and on demo day.
  * **Asking.** Whatever is still missing is asked for, one question at a
    time, as an ordinary step. A `Brief` holds what is known and says what to
    ask next (`loop.run_brief` does the asking).
  * **The task.** Once nothing is missing, the brief builds the task from the
    person's details — including what the run must find true at the end, so a
    search for another route or another day fails rather than completes.

**The model is not trusted with anything it could invent.** A reference
number or a course code it reports is kept only if those characters are in
what the person typed. A day has to be a real date, today or later. A place
is kept as it came, because the page is what decides whether it is a station,
and the person is shown the journey in one sentence before anything is
searched.

No words live here. Every sentence a question shows is in `voice.py`.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Protocol

from pydantic import BaseModel

from backend.orchestrator import voice
from backend.orchestrator.loop import Move, Planner, Task
from backend.orchestrator.plan import (
    About,
    Expectation,
    HardcodedPlanner,
    Shown,
    registration_plan,
)
from shared.schema import StepField

#: Seconds the model gets to read the details before the keywords do. The same
#: bound routing has, for the same reason: this is a person waiting.
MODEL_TIMEOUT_S = 8.0

#: How many times one question is asked before the run says it is stuck.
MAX_TRIES = 3

#: How far ahead a day may be. A year covers any journey someone plans by
#: typing a sentence, and rules out a mistyped year.
HORIZON_DAYS = 366

# --- what was understood -------------------------------------------------------


@dataclass(frozen=True)
class Understood:
    """What a goal says, as far as anyone could tell. None means it did not say."""

    origin: str | None = None
    destination: str | None = None
    day: date | None = None
    reference: str | None = None
    course: str | None = None


class DetailsChoice(BaseModel):
    """What the model is allowed to answer. Validated like every other reply."""

    origin: str | None = None
    destination: str | None = None
    date: str | None = None
    reference: str | None = None
    course: str | None = None


#: The JSON schema a provider pins the answer to, where it can.
DETAILS_SCHEMA = {
    "type": "object",
    "properties": {
        name: {"type": ["string", "null"]}
        for name in ("origin", "destination", "date", "reference", "course")
    },
    "required": ["origin", "destination", "date", "reference", "course"],
    "additionalProperties": False,
}


def system_prompt(today: date) -> str:
    return f"""\
You read one request typed by a person and pick out the details it states.
Today is {today.strftime('%A')} {today.isoformat()}.

Answer with JSON:
{{"origin": ..., "destination": ..., "date": ..., "reference": ..., "course": ...}}

- origin: the place a journey starts, as the person wrote it, or null.
- destination: the place a journey ends, as the person wrote it, or null.
- date: the day of travel as YYYY-MM-DD, worked out from today, or null.
  A day and month with no year means the next time that day comes.
- reference: a bill's reference number, digits only, or null.
- course: a course code such as CS-401, or null.

Use null for anything the request does not state. Never guess a value.
"""


class Reader(Protocol):
    async def read_details(self, system_prompt: str, goal: str) -> DetailsChoice: ...


# --- reading without a model -----------------------------------------------------

MONTHS = {
    name: number
    for number, names in enumerate(
        [
            ("january", "jan"), ("february", "feb"), ("march", "mar"), ("april", "apr"),
            ("may",), ("june", "jun"), ("july", "jul"), ("august", "aug"),
            ("september", "sep", "sept"), ("october", "oct"), ("november", "nov"),
            ("december", "dec"),
        ],
        start=1,
    )
    for name in names
}
WEEKDAYS = {
    name: number
    for number, names in enumerate(
        [("monday", "mon"), ("tuesday", "tue", "tues"), ("wednesday", "wed"),
         ("thursday", "thu", "thur", "thurs"), ("friday", "fri"), ("saturday", "sat"),
         ("sunday", "sun")]
    )
    for name in names
}

_MONTH = "|".join(sorted(MONTHS, key=len, reverse=True))
_WEEKDAY = "|".join(sorted(WEEKDAYS, key=len, reverse=True))
_ORDINAL = r"(?:st|nd|rd|th)?"

#: Each way of writing a day, most specific first. The first that matches wins.
_DAY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("iso", re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")),
    ("overmorrow", re.compile(r"\b(?:the\s+)?day\s+after\s+tomorrow\b")),
    ("tomorrow", re.compile(r"\b(?:tomorrow|tomorow|tommorow|tmrw)\b")),
    ("today", re.compile(r"\b(?:today|tonight)\b")),
    ("day month", re.compile(
        rf"\b(?:on\s+)?(?:the\s+)?(\d{{1,2}}){_ORDINAL}\s+(?:of\s+)?({_MONTH})\b\.?"
        r"(?:,?\s+(\d{4}))?")),
    ("month day", re.compile(
        rf"\b(?:on\s+)?({_MONTH})\b\.?\s+(?:the\s+)?(\d{{1,2}}){_ORDINAL}\b(?:,?\s+(\d{{4}}))?")),
    ("numeric", re.compile(r"\b(?:on\s+)?(\d{1,2})[/.](\d{1,2})(?:[/.](\d{2,4}))?\b")),
    ("weekday", re.compile(rf"\b(?:on\s+)?(?:(this|next)\s+)?({_WEEKDAY})\b")),
)


def _dated(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _coming(month: int, day: int, year: str | None, today: date) -> date | None:
    """A day and a month, in the year given or the next time it comes."""
    if year:
        number = int(year)
        return _dated(number + 2000 if number < 100 else number, month, day)
    this_year = _dated(today.year, month, day)
    if this_year is not None and this_year >= today:
        return this_year
    return _dated(today.year + 1, month, day)


def find_day(text: str, today: date) -> tuple[date | None, tuple[int, int] | None]:
    """The day a sentence names, and where in the sentence it is said.

    The span comes back so the words of the date can be taken out before the
    places are looked for: "to Multan on 3 October" is a destination and a
    day, not a destination called "Multan on 3 October".
    """
    lowered = text.lower()
    for kind, pattern in _DAY_PATTERNS:
        match = pattern.search(lowered)
        if match is None:
            continue
        found: date | None = None
        if kind == "iso":
            found = _dated(int(match[1]), int(match[2]), int(match[3]))
        elif kind == "today":
            found = today
        elif kind == "tomorrow":
            found = today + timedelta(days=1)
        elif kind == "overmorrow":
            found = today + timedelta(days=2)
        elif kind == "day month":
            found = _coming(MONTHS[match[2]], int(match[1]), match[3], today)
        elif kind == "month day":
            found = _coming(MONTHS[match[1]], int(match[2]), match[3], today)
        elif kind == "numeric":
            # Day first, as it is written in Pakistan.
            found = _coming(int(match[2]), int(match[1]), match[3], today) \
                if 1 <= int(match[2]) <= 12 else None
        elif kind == "weekday":
            ahead = (WEEKDAYS[match[2]] - today.weekday()) % 7
            # A weekday named on that same weekday means the next one, unless
            # they said "this".
            if ahead == 0 and match[1] != "this":
                ahead = 7
            found = today + timedelta(days=ahead)
        if found is not None:
            return found, match.span()
    return None, None


def usable_day(found: date | None, today: date) -> date | None:
    """A day that can be travelled on: today or later, and not years away."""
    if found is None or found < today:
        return None
    if (found - today).days > HORIZON_DAYS:
        return None
    return found


#: Words that are never a place. Whatever is left around "from" and "to" is.
NOT_A_PLACE = frozenset("""
    a an the i me my we us our you your it is are was be been am do does did can could
    would should will shall may might must please kindly thanks thank hello hi
    want wants wanted need needs like love wish hoping hope trying try looking look
    go going goes get getting travel travelling traveling travels leave leaving
    find finding show showing see check checking search searching book booking tell
    give know take taking catch catching ride riding
    train trains railway railways rail ticket tickets timing timings time times
    timetable schedule schedules seat seats journey journeys trip trips station stations
    to from on for at by in of and or with into via till until between then
    there here any some all what which when where who how
    this next morning evening afternoon night day date leaves runs run running
    available early late soon now
""".split())

_TOKEN = re.compile(r"[A-Za-z][A-Za-z'.-]*")


def _place_after(tokens: list[str], index: int) -> str | None:
    """The run of place words that starts at `index`, if one does."""
    words: list[str] = []
    for token in tokens[index:index + 3]:
        if token.lower().strip(".'-") in NOT_A_PLACE:
            break
        words.append(token.strip(".,"))
    return " ".join(words) or None


def _place_before(tokens: list[str], index: int) -> str | None:
    """The run of place words that ends just before `index`, if one does."""
    words: list[str] = []
    for token in reversed(tokens[max(0, index - 3):index]):
        if token.lower().strip(".'-") in NOT_A_PLACE:
            break
        words.insert(0, token.strip(".,"))
    return " ".join(words) or None


def find_places(text: str) -> tuple[str | None, str | None]:
    """Where from and where to, read off the words "from" and "to".

    "from X" is an origin and "to Y" a destination wherever they sit. With no
    "from", whatever stands directly before "to Y" is the origin — "Lahore to
    Karachi" — unless it is an ordinary word, as in "trains to Karachi".
    A "to" followed by an ordinary word is grammar, not a journey: the "to"
    in "I want to go".
    """
    tokens = _TOKEN.findall(text)
    lowered = [token.lower() for token in tokens]
    origin: str | None = None
    destination: str | None = None
    before_to: str | None = None

    for index, word in enumerate(lowered):
        if word == "from" and origin is None:
            origin = _place_after(tokens, index + 1)
        elif word == "to":
            place = _place_after(tokens, index + 1)
            if place is not None:
                destination = place
                before_to = _place_before(tokens, index)
    return origin or before_to, destination


_REFERENCE = re.compile(r"(?<!\d)\d(?:[\s-]?\d){13}(?!\d)")
_COURSE = re.compile(r"\b([A-Za-z]{2,4})[\s-]?(\d{3}[A-Za-z]?)\b")


def clean_reference(text: str | None) -> str | None:
    """Fourteen digits, however they were spaced, or nothing."""
    match = _REFERENCE.search(text or "")
    return re.sub(r"\D", "", match[0]) if match else None


def clean_course(text: str | None) -> str | None:
    """A course code the way the portal prints it: `CS-401`."""
    match = _COURSE.search(text or "")
    return f"{match[1].upper()}-{match[2].upper()}" if match else None


def clean_place(text: str | None) -> str | None:
    """A place name, tidied and nothing more: the page decides if it is one."""
    words = " ".join(_TOKEN.findall(text or ""))
    return words.title() if 0 < len(words) <= 40 else None


def by_keywords(flow: str, goal: str, today: date) -> Understood:
    """The offline reader. Only what the flow in hand could use is looked for,
    so a number in a train request is never mistaken for a course."""
    if flow == "railways":
        found, span = find_day(goal, today)
        rest = goal if span is None else goal[:span[0]] + " " + goal[span[1]:]
        origin, destination = find_places(rest)
        return Understood(origin=clean_place(origin), destination=clean_place(destination),
                          day=usable_day(found, today))
    if flow == "billing":
        return Understood(reference=clean_reference(goal))
    if flow == "registration":
        return Understood(course=clean_course(goal))
    return Understood()


def _said(goal: str, value: str) -> bool:
    """Whether the letters and digits of `value` are in what was typed."""
    squeeze = lambda text: re.sub(r"[^a-z0-9]", "", text.lower())  # noqa: E731
    return squeeze(value) in squeeze(goal)


def from_model(flow: str, goal: str, choice: DetailsChoice, today: date) -> Understood:
    """The model's answer, kept only where it can be held to what was typed."""
    if flow == "railways":
        found: date | None = None
        try:
            found = date.fromisoformat(choice.date) if choice.date else None
        except ValueError:
            found = None
        return Understood(origin=clean_place(choice.origin),
                          destination=clean_place(choice.destination),
                          day=usable_day(found, today))
    if flow == "billing":
        reference = clean_reference(choice.reference)
        return Understood(reference=reference if reference and _said(goal, reference) else None)
    if flow == "registration":
        course = clean_course(choice.course)
        return Understood(course=course if course and _said(goal, course) else None)
    return Understood()


async def understand(
    flow: str, goal: str, model: Reader | None = None, today: date | None = None
) -> Understood:
    """What the goal says about this flow. The model if it answers, and the
    keyword reader for whatever it did not say, or for all of it otherwise."""
    today = today or date.today()
    known = by_keywords(flow, goal, today)
    if model is None or not goal.strip():
        return known
    try:
        choice = await asyncio.wait_for(
            model.read_details(system_prompt(today), goal.strip()), MODEL_TIMEOUT_S
        )
        read = from_model(flow, goal, choice, today)
    except Exception:  # noqa: BLE001 - no key, no quota, slow, or malformed
        return known
    return Understood(
        origin=read.origin or known.origin,
        destination=read.destination or known.destination,
        day=read.day or known.day,
        reference=read.reference or known.reference,
        course=read.course or known.course,
    )


# --- asking for what is missing ---------------------------------------------------


def _typed(instruction: str, detail: str, field_id: str, label: str) -> Move:
    """A question answered by typing: one box, one button, and the way to stop."""
    return Move(
        instruction=instruction,
        detail=detail,
        operations=[],
        expect=Expectation(),
        fields=[StepField(id=field_id, label=label, type="text", value="")],
        actions=voice.actions(voice.THATS_IT),
        question=True,
    )


def _picked(instruction: str, labels: list[str]) -> Move:
    """A question answered by pressing one of a few buttons."""
    return Move(
        instruction=instruction,
        detail="",
        operations=[],
        expect=Expectation(),
        fields=[],
        actions=voice.choices(labels),
        question=True,
    )


def choice_index(action_id: str) -> int | None:
    """Which button a `choice:N` id means, or None if it is not one."""
    if not action_id.startswith(voice.CHOICE_PREFIX):
        return None
    try:
        return int(action_id[len(voice.CHOICE_PREFIX):])
    except ValueError:
        return None


class _Asking:
    """What every brief shares: one question at a time, and a limit on it."""

    #: How many steps the flow's own plan takes, after the questions.
    plan_steps = 0

    def __init__(self, goal: str) -> None:
        self.goal = goal
        self.gave_up: str | None = None
        #: Set by the app to put trace memory round the planner. It is given
        #: the task with its details spelled out, which is what a remembered
        #: run is filed under.
        self.wrap = None
        self._tries: dict[str, int] = {}
        #: The count once it has been read. See `estimated_steps`.
        self._total: int | None = None

    def _missing(self) -> list[str]:
        raise NotImplementedError

    @property
    def estimated_steps(self) -> int:
        """Everything to be shown: the questions still to ask, and the plan.

        Read once and kept, so the count the person sees does not move while
        they are answering. Two things can still make a run end higher than
        this: a question asked a second time because the answer could not be
        used, and a question only the page can raise (which of two stations in
        one city). Neither can be counted in advance, and `step_total` never
        goes below what is on screen (`loop._Run.present`).
        """
        if self._total is None:
            self._total = len(self._missing()) + self.plan_steps
        return self._total

    def _again(self, what: str) -> bool:
        """Count one more unusable answer. False once that is too many."""
        self._tries[what] = self._tries.get(what, 0) + 1
        if self._tries[what] >= MAX_TRIES:
            self.gave_up = voice.NOT_UNDERSTOOD
            return False
        return True

    def _tried(self, what: str) -> bool:
        return self._tries.get(what, 0) > 0

    def _ask(self, move: Move) -> Move:
        # The count is read before the first question goes out; asking does
        # not change it.
        self.estimated_steps  # noqa: B018 - freeze it before anything is asked
        return move

    def sentence(self) -> str:
        raise NotImplementedError

    def _plan(self) -> tuple[Planner, Task]:
        raise NotImplementedError

    def settle(self) -> tuple[Planner, Task]:
        """The planner and the task, now that nothing is missing."""
        planner, task = self._plan()
        if self.wrap is not None:
            planner = self.wrap(planner, replace(task, goal=self.sentence()))
        return planner, task


class TripBrief(_Asking):
    """A train journey: where from, where to, and which day."""

    plan_steps = 5

    def __init__(self, goal: str, known: Understood, today: date | None = None,
                 hardcoded: bool = True, provider=None) -> None:
        super().__init__(goal)
        self.today = today or date.today()
        self.origin = known.origin
        self.destination = known.destination
        self.day = known.day
        self._hardcoded = hardcoded
        self._provider = provider
        self._waiting: str | None = None
        self._typing_day = False
        self._day_gone = False

    def _missing(self) -> list[str]:
        return [name for name, value in (("origin", self.origin),
                                         ("destination", self.destination),
                                         ("day", self.day)) if value is None]

    def question(self) -> Move | None:
        if self.gave_up is not None:
            return None
        missing = self._missing()
        if not missing:
            return None
        self._waiting = missing[0]
        if self._waiting == "origin":
            return self._ask(_typed(voice.ASK_FROM, "", "origin", voice.FIELD_FROM))
        if self._waiting == "destination":
            return self._ask(_typed(voice.ASK_TO, "", "destination", voice.FIELD_TO))
        if not self._typing_day:
            return self._ask(_picked(
                voice.ASK_DAY, [voice.DAY_TODAY, voice.DAY_TOMORROW, voice.DAY_PICK]))
        instruction = (voice.ASK_DAY_GONE if self._day_gone
                       else voice.ASK_DAY_AGAIN if self._tried("day")
                       else voice.ASK_WHICH_DAY)
        return self._ask(_typed(instruction, "", "day", voice.FIELD_DAY))

    def answered(self, action_id: str, input_values: dict[str, str]) -> None:
        waiting = self._waiting
        if waiting in ("origin", "destination"):
            place = clean_place(input_values.get(waiting))
            if place is None:
                self._again(waiting)
            elif waiting == "origin":
                self.origin = place
            else:
                self.destination = place
            return

        if not self._typing_day:
            picked = choice_index(action_id)
            if picked == 0:
                self.day = self.today
            elif picked == 1:
                self.day = self.today + timedelta(days=1)
            else:
                self._typing_day = True
            return

        typed = input_values.get("day") or ""
        found, _ = find_day(typed, self.today)
        if found is None and typed.strip().isdigit():
            # A bare number is a day of this month, or of the next if it has gone.
            found = _coming_day_of_month(int(typed.strip()), self.today)
        self._day_gone = found is not None and found < self.today
        self.day = usable_day(found, self.today)
        if self.day is None:
            self._again("day")

    def sentence(self) -> str:
        """The journey as one plain sentence, with the date written out."""
        return (f"Find trains from {self.origin} to {self.destination} "
                f"on {self.day.isoformat()}.")

    def task(self) -> Task:
        from backend.orchestrator.railways_plan import trip_task

        return replace(trip_task(self.origin, self.destination, self.day),
                       goal=self.goal)

    def _plan(self) -> tuple[Planner, Task]:
        from backend.orchestrator.railways_plan import TripPlanner

        task = self.task()
        if self._hardcoded:
            return TripPlanner(self.origin, self.destination, self.day, self.today), task
        from backend.orchestrator.llm_loop import LLMPlanner

        # The model plans from the journey spelled out, not from "tomorrow".
        return LLMPlanner(self._provider, replace(task, goal=self.sentence())), task


def _coming_day_of_month(day: int, today: date) -> date | None:
    this_month = _dated(today.year, today.month, day)
    if this_month is not None and this_month >= today:
        return this_month
    year, month = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
    return _dated(year, month, day)


class BillBrief(_Asking):
    """A bill to look up: the reference number printed on it."""

    plan_steps = 3

    def __init__(self, goal: str, known: Understood, hardcoded: bool = True,
                 provider=None) -> None:
        super().__init__(goal)
        self.reference = known.reference
        self._hardcoded = hardcoded
        self._provider = provider

    def _missing(self) -> list[str]:
        return [] if self.reference else ["reference"]

    def question(self) -> Move | None:
        if self.gave_up is not None or self.reference:
            return None
        instruction = (voice.ASK_REFERENCE_AGAIN if self._tried("reference")
                       else voice.ASK_REFERENCE)
        return self._ask(_typed(instruction, voice.REFERENCE_DETAIL, "reference",
                                voice.FIELD_REFERENCE))

    def answered(self, action_id: str, input_values: dict[str, str]) -> None:
        self.reference = clean_reference(input_values.get("reference"))
        if self.reference is None:
            self._again("reference")

    def sentence(self) -> str:
        return f"Find the amount due for reference number {self.reference}."

    def task(self) -> Task:
        from backend.orchestrator.billing_plan import bill_task

        return replace(bill_task(self.reference), goal=self.goal)

    def _plan(self) -> tuple[Planner, Task]:
        from backend.orchestrator.billing_plan import billing_plan

        task = self.task()
        if self._hardcoded:
            return HardcodedPlanner(billing_plan(self.reference)), task
        from backend.orchestrator.llm_loop import LLMPlanner

        return LLMPlanner(self._provider, replace(task, goal=self.sentence())), task


class CourseBrief(_Asking):
    """A course to register for: its code."""

    plan_steps = 3

    def __init__(self, goal: str, known: Understood, hardcoded: bool = True,
                 provider=None) -> None:
        super().__init__(goal)
        self.course = known.course
        self._hardcoded = hardcoded
        self._provider = provider

    def _missing(self) -> list[str]:
        return [] if self.course else ["course"]

    def question(self) -> Move | None:
        if self.gave_up is not None or self.course:
            return None
        instruction = voice.ASK_COURSE_AGAIN if self._tried("course") else voice.ASK_COURSE
        return self._ask(_typed(instruction, voice.COURSE_DETAIL, "course",
                                voice.FIELD_COURSE))

    def answered(self, action_id: str, input_values: dict[str, str]) -> None:
        self.course = clean_course(input_values.get("course"))
        if self.course is None:
            self._again("course")

    def sentence(self) -> str:
        return f"Register for the course {self.course}."

    def task(self) -> Task:
        return Task(
            goal=self.goal,
            estimated_steps=self.plan_steps,
            success=Expectation(url_contains="/register",
                                title_contains="Registration Confirmed"),
            # The course is chosen by pressing its button, so it is in no
            # field to check afterwards. The confirmation says which course
            # was registered, and that is what has to name this one.
            about=About(shows=(Shown(reads="Course", says=self.course),)),
        )

    def _plan(self) -> tuple[Planner, Task]:
        task = self.task()
        if self._hardcoded:
            return HardcodedPlanner(registration_plan(self.course)), task
        from backend.orchestrator.llm_loop import LLMPlanner

        return LLMPlanner(self._provider, replace(task, goal=self.sentence())), task


BRIEFS = {"railways": TripBrief, "billing": BillBrief, "registration": CourseBrief}


def brief_for(flow: str, goal: str, known: Understood, *, hardcoded: bool = True,
              provider=None, today: date | None = None):
    """The brief for a routed flow, holding whatever the goal already said."""
    if flow == "railways":
        return TripBrief(goal, known, today, hardcoded, provider)
    return BRIEFS[flow](goal, known, hardcoded, provider)

