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
    ask next (`loop.run_brief` does the asking). Since 2026-10-06 every answer
    is also checked before anything on the site is done, and a journey is read
    back once before it starts (`TripBrief`).
  * **The task.** Once nothing is missing, the brief builds the task from the
    person's details — including what the run must find true at the end, so a
    search for another route or another day fails rather than completes.

**The model is not trusted with anything it could invent.** A reference
number or a course code it reports is kept only if those characters are in
what the person typed. A day has to be a real date, today or later, and
a day the words show cannot exist is not mended by it. A place is kept as it
came, because the site's own station list is what decides whether it is a
station, and the person is shown the journey in one sentence before anything
is done.

No words live here. Every sentence a question shows is in `voice.py`.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, replace
from datetime import date, timedelta
from difflib import SequenceMatcher
from typing import Protocol

from pydantic import BaseModel

from backend.orchestrator import voice
from backend.orchestrator.loop import Move, Planner, Task
from backend.orchestrator.plan import (
    About,
    CoursePlanner,
    Expectation,
    HardcodedPlanner,
    Shown,
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
    #: A day the goal named that cannot be travelled on, and why — so the
    #: question that asks for the day can say what was wrong with that one.
    day_problem: "DayReading | None" = None


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
    ("yesterday", re.compile(r"\byesterday\b")),
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
        elif kind == "yesterday":
            found = today - timedelta(days=1)
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


# What can be wrong with a day someone named, beyond not naming one.
GONE = "gone"
TOO_FAR = "too far"
NO_SUCH_DAY = "no such day"


@dataclass(frozen=True)
class DayReading:
    """A day as read from what someone typed, and what is wrong with it if
    anything is. `day` is set only for a day that can be travelled on;
    `problem` only for a day that was named and cannot. Neither means no day
    was named at all."""

    day: date | None = None
    problem: str | None = None
    #: The day as it was understood, for saying what was wrong with it.
    said: str = ""


_MONTH_NAMES = {number: name for name, number in MONTHS.items() if len(name) > 3}
_MONTH_NAMES[5] = "may"


def no_such_day(text: str) -> tuple[str, tuple[int, int]] | None:
    """A date that is written like one and is not in the calendar — 31
    February, 2026-02-30, 31/4 — as words, and where it is said.

    `find_day` passes over these, because there is nothing to find; this is
    what tells "I didn't catch that" apart from "there is no such day". Only
    a real month counts: "45/13" is not a date at all.
    """
    lowered = text.lower()
    for kind, pattern in _DAY_PATTERNS:
        match = pattern.search(lowered)
        if match is None:
            continue
        if kind == "iso":
            year, month, day = match[1], int(match[2]), int(match[3])
        elif kind == "day month":
            day, month, year = int(match[1]), MONTHS[match[2]], match[3]
        elif kind == "month day":
            month, day, year = MONTHS[match[1]], int(match[2]), match[3]
        elif kind == "numeric":
            day, month, year = int(match[1]), int(match[2]), match[3]
        else:
            continue
        if not 1 <= month <= 12 or day < 1:
            continue
        words = f"{day} {_MONTH_NAMES[month].title()}"
        return (f"{words} {year}" if year and len(year) == 4 else words), match.span()
    return None


def read_day(text: str, today: date) -> DayReading:
    """The day someone typed, checked: in the calendar, not gone, not too far."""
    found, _ = find_day(text, today)
    if found is None:
        impossible = no_such_day(text)
        if impossible is not None:
            return DayReading(problem=NO_SUCH_DAY, said=impossible[0])
        return DayReading()
    return judge_day(found, today)


def judge_day(found: date, today: date) -> DayReading:
    """A real date, checked against today and against how far ahead is allowed."""
    if found < today:
        return DayReading(problem=GONE, said=voice.day_words(found, today))
    if (found - today).days > HORIZON_DAYS:
        return DayReading(problem=TOO_FAR, said=voice.day_words(found, today))
    return DayReading(day=found)


def last_day(today: date) -> date:
    """The furthest day a journey can be looked up for."""
    return today + timedelta(days=HORIZON_DAYS)


def day_trouble(reading: DayReading, today: date) -> str | None:
    """The sentence that says what was wrong with a day, and asks again."""
    if reading.problem == GONE:
        return voice.day_gone(reading.said)
    if reading.problem == TOO_FAR:
        return voice.day_too_far(voice.day_words(last_day(today), today))
    if reading.problem == NO_SUCH_DAY:
        return voice.no_such_day(reading.said)
    return None


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
        impossible = no_such_day(goal) if found is None else None
        if impossible is not None:
            span = impossible[1]
        rest = goal if span is None else goal[:span[0]] + " " + goal[span[1]:]
        origin, destination = find_places(rest)
        reading = (DayReading(problem=NO_SUCH_DAY, said=impossible[0]) if impossible
                   else judge_day(found, today) if found else DayReading())
        return Understood(origin=clean_place(origin), destination=clean_place(destination),
                          day=reading.day, day_problem=reading if reading.problem else None)
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
        # A day the words show cannot be travelled on stays that way: asked
        # "31 February", a model will happily answer 3 March.
        day=None if known.day_problem else (read.day or known.day),
        reference=read.reference or known.reference,
        course=read.course or known.course,
        day_problem=known.day_problem,
    )


# --- asking for what is missing ---------------------------------------------------


def _typed(instruction: str, detail: str, field_id: str, label: str, button: str,
           kind: str | None = None) -> Move:
    """A question answered by typing: one box, one button that says what it
    does with the answer (`voice.USE_DAY`), and the way to stop.

    `kind` is what the question is about, for the shape beside it
    (`loop.kind_of`); without one it is "type"."""
    return Move(
        instruction=instruction,
        detail=detail,
        operations=[],
        expect=Expectation(),
        fields=[StepField(id=field_id, label=label, type="text", value="")],
        actions=voice.actions(button),
        question=True,
        kind=kind,
    )


def _picked(instruction: str, labels: list[str], kind: str | None = None) -> Move:
    """A question answered by pressing one of a few buttons. Without a `kind`
    its shape is "choose"."""
    return Move(
        instruction=instruction,
        detail="",
        operations=[],
        expect=Expectation(),
        fields=[],
        actions=voice.choices(labels),
        question=True,
        kind=kind,
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

    #: The task's stages by name (`voice.*_STAGES`), and the one each kind of
    #: question is in. Set by each brief.
    stages: list[str] = []

    def _ask(self, move: Move, stage: int | None = 0, note: str | None = None) -> Move:
        # The count is read before the first question goes out; asking does
        # not change it.
        self.estimated_steps  # noqa: B018 - freeze it before anything is asked
        return replace(move, stage=stage, note=note)

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


# --- the site's own stations ------------------------------------------------------

#: Seconds to wait for the station list to be on the page before asking. The
#: live site builds it when its script runs, after the page itself has loaded.
STATION_LIST_WAIT_S = 10.0
#: How often it is read while waiting. It is ready when two reads agree.
STATION_LIST_POLL_S = 0.5

#: How close a name has to be to a station's to be offered as "did you mean".
CLOSE_ENOUGH = 0.75


def _plain(text: str) -> str:
    """A name with case, dots, dashes and spacing taken out: `LAHORE JN.` and
    `lahore jn` are the same station."""
    return " ".join(re.sub(r"[.\-'’]", " ", text.casefold()).split())


@dataclass(frozen=True)
class StationMatch:
    """What one typed name is, on the site's list. At most one field is set."""

    #: Exactly one station.
    station: str | None = None
    #: A few, each a fair reading: "Lahore" is Lahore Jn. and Lahore Cantt.
    several: tuple[str, ...] = ()
    #: More than can be offered as buttons.
    many: bool = False
    #: Nothing has the name in it; these are the nearest by spelling.
    close: tuple[str, ...] = ()


def match_station(typed: str, stations: list[str]) -> StationMatch:
    """A name against the site's list.

    Exactly the name is that station. Otherwise every station whose words
    begin with the typed words (so "Lahore" is both Lahore stations, and
    "Hyd" is Hyderabad Jn.), or failing that, every station with the name
    anywhere in it ("pindi"). One is that station; a few are asked about;
    more than that is too many to offer. None at all is a name the site does
    not have, and the nearest by spelling are offered instead.
    """
    want = _plain(typed)
    if not want:
        return StationMatch()
    plain = {station: _plain(station) for station in stations}
    exact = [s for s, p in plain.items() if p == want]
    if exact:
        return StationMatch(station=exact[0])
    words = want.split()
    pool = [s for s, p in plain.items()
            if all(any(w.startswith(typed_word) for w in p.split()) for typed_word in words)]
    pool = pool or [s for s, p in plain.items() if want in p]
    if len(pool) == 1:
        return StationMatch(station=pool[0])
    if 1 < len(pool) <= voice.MAX_CHOICES:
        return StationMatch(several=tuple(pool))
    if pool:
        return StationMatch(many=True)

    def nearness(station: str) -> float:
        p = plain[station]
        return max(SequenceMatcher(None, want, p).ratio(),
                   SequenceMatcher(None, want, p.split()[0]).ratio() if p else 0.0)

    scored = sorted(((nearness(s), i, s) for i, s in enumerate(stations)), reverse=True)
    close = [s for score, _, s in sorted(
        [t for t in scored if t[0] >= CLOSE_ENOUGH], key=lambda t: (-t[0], t[1]))]
    return StationMatch(close=tuple(close[:voice.MAX_CHOICES]))


async def read_stations(page) -> list[str]:
    """The site's own list of stations, read without opening it, or an empty
    list if the page has none (`backend/perception/options.py`).

    Read until it stops changing: a list still being built is not the list.
    """
    from backend.perception.options import longest_list

    deadline = asyncio.get_running_loop().time() + STATION_LIST_WAIT_S
    last: list[str] | None = None
    while True:
        names = await longest_list(page)
        if names and names == last:
            return names
        if asyncio.get_running_loop().time() >= deadline:
            return names
        last = names
        await asyncio.sleep(STATION_LIST_POLL_S)


class TripBrief(_Asking):
    """A train journey: where from, where to, and which day.

    **Every answer is checked before anything on the site is done**
    (2026-10-06). Until then the stations were whatever the person typed, and
    the site was asked about them one at a time, mid-run: a place it did not
    have was found out after the box had been typed into, and the run ended.
    Now the site's own station list is read first, without touching it
    (`prepare`), and the questions are answered from it: the station boxes
    offer the site's names to choose from, a name it does not have is met
    with the nearest ones it does, a city with two stations is asked about,
    and a journey that starts where it ends is asked about again. A day that
    has gone, that is further ahead than can be looked up, or that is not in
    the calendar at all, is said to be so. Then the journey is read back once,
    and nothing on the site is touched until the person says it is right.

    A page that offers no list leaves the stations to be settled on the page,
    as before (`TripPlanner`), and the same checks of the day still hold.
    """

    plan_steps = 5
    stages = voice.TRIP_STAGES
    _ENDS = ("origin", "destination")

    def __init__(self, goal: str, known: Understood, today: date | None = None,
                 hardcoded: bool = True, provider=None) -> None:
        super().__init__(goal)
        self.today = today or date.today()
        #: Each end as the person said it.
        self.places: dict[str, str | None] = {"origin": known.origin,
                                              "destination": known.destination}
        #: Each end as the site names it, once one of its stations is settled on.
        self.chosen: dict[str, str | None] = {"origin": None, "destination": None}
        self.day = known.day
        #: The site's own list of stations, once read. None until then, and
        #: stays None for a page that has no list.
        self.stations: list[str] | None = None
        #: Whether the person has heard the journey read back and agreed to it.
        self.confirmed = False
        self._hardcoded = hardcoded
        self._provider = provider
        self._waiting: str | None = None
        self._typing_day = False
        self._changing = False
        #: Why something is being asked again: the note beside its question.
        self._why: dict[str, str] = {}
        #: A question asked in other words than the usual one, though nothing
        #: was wrong: which of a city's stations.
        self._asking: dict[str, str] = {}
        #: A few stations offered for one end, as buttons.
        self._offered: dict[str, tuple[str, ...]] = {}
        if known.day_problem is not None:
            self._why["day"] = day_trouble(known.day_problem, self.today) or voice.DAY_NOT_CAUGHT
        self._check_same(counted=False)

    # --- what is known ---------------------------------------------------------

    @property
    def origin(self) -> str | None:
        return self.chosen["origin"] or self.places["origin"]

    @property
    def destination(self) -> str | None:
        return self.chosen["destination"] or self.places["destination"]

    def _known(self, end: str) -> bool:
        if self.stations is None:
            return self.places[end] is not None
        return self.chosen[end] is not None

    def _missing(self) -> list[str]:
        missing = [end for end in self._ENDS if not self._known(end)]
        if self.day is None:
            missing.append("day")
        if not self.confirmed:
            missing.append("read back")
        return missing

    def _shown(self, end: str) -> str:
        """An end the way the person reads it."""
        chosen = self.chosen[end]
        return voice.station_name(chosen) if chosen else (self.places[end] or "")

    # --- reading the site before asking --------------------------------------------

    async def prepare(self, page) -> None:
        """Read the site's station list, and hold the goal's places to it.

        Nothing on the page is touched. A place the goal named is settled
        here if the list has exactly one station for it, and asked about
        otherwise, before anything else is.
        """
        names = await read_stations(page)
        if len(names) < 2:
            return
        self.stations = names
        for end in self._ENDS:
            place = self.places[end]
            if place is not None and self.chosen[end] is None:
                self._take(end, place, counted=False)

    # --- asking ----------------------------------------------------------------------

    def question(self) -> Move | None:
        if self.gave_up is not None:
            return None
        for end in self._ENDS:
            if not self._known(end):
                return self._ask_station(end)
        if self.day is None:
            return self._ask_day()
        if not self.confirmed:
            if self._changing:
                self._waiting = "change"
                return self._ask(_picked(voice.ASK_CHANGE, [
                    voice.CHANGE_FROM, voice.CHANGE_TO, voice.CHANGE_DAY]), stage=3)
            self._waiting = "read back"
            return self._ask(_picked(
                voice.read_back(self._shown("origin"), self._shown("destination"),
                                voice.when_words(self.day, self.today)),
                [voice.READ_BACK_YES, voice.READ_BACK_NO], kind="confirm"), stage=3)
        return None

    def _ask_station(self, end: str) -> Move:
        self._waiting = end
        asking = voice.ASK_FROM if end == "origin" else voice.ASK_TO
        note = self._why.get(end)
        offered = self._offered.get(end)
        if offered:
            # A few to choose from: which of a city's stations, or the
            # nearest names to one the list does not have.
            instruction = self._asking.get(end) or voice.ASK_CLOSEST
            return self._ask(_picked(
                instruction, [voice.station_name(s) for s in offered] + [voice.NONE_OF_THESE],
                kind="place"), stage=self._ENDS.index(end), note=note)
        instruction = asking
        label = voice.FIELD_FROM if end == "origin" else voice.FIELD_TO
        return self._ask(Move(
            instruction=instruction,
            detail="",
            operations=[],
            expect=Expectation(),
            fields=[StepField(id=end, label=label,
                              type="choice" if self.stations else "text", value="",
                              options=self.stations or [])],
            actions=voice.actions(voice.USE_STATION),
            question=True,
            kind="place",
        ), stage=self._ENDS.index(end), note=note)

    def _ask_day(self) -> Move:
        self._waiting = "day"
        if not self._typing_day:
            return self._ask(_picked(
                voice.ASK_DAY,
                [voice.DAY_TODAY, voice.DAY_TOMORROW, voice.DAY_PICK], kind="date"), stage=2,
                note=self._why.get("day"))
        # Asked again after a day that could not be used: plainly, beside why.
        note = self._why.get("day")
        return self._ask(_typed(voice.ASK_TRAVEL_DAY if note else voice.ASK_WHICH_DAY, "",
                                "day", voice.FIELD_DAY, voice.USE_DAY, kind="date"),
                         stage=2, note=note)

    # --- answers -----------------------------------------------------------------------

    def answered(self, action_id: str, input_values: dict[str, str]) -> None:
        waiting = self._waiting
        if waiting in self._ENDS:
            self._answer_station(waiting, action_id, input_values)
        elif waiting == "day":
            self._answer_day(action_id, input_values)
        elif waiting == "read back":
            if choice_index(action_id) == 0:
                self.confirmed = True
            else:
                self._changing = True
        elif waiting == "change":
            self._changing = False
            picked = choice_index(action_id)
            if picked in (0, 1):
                self._forget(self._ENDS[picked])
            else:
                self.day = None
                self._typing_day = False
                self._why.pop("day", None)

    def _answer_station(self, end: str, action_id: str, input_values: dict[str, str]) -> None:
        offered = self._offered.pop(end, None)
        if offered:
            picked = choice_index(action_id)
            if picked is not None and picked < len(offered):
                self._choose(end, offered[picked])
            else:
                # None of these: back to the whole list, which is not a wrong answer.
                self._forget(end)
            return
        self._take(end, " ".join((input_values.get(end) or "").split()), counted=True)

    def _take(self, end: str, typed: str, *, counted: bool) -> None:
        """A name for one end, held to the site's list if there is one."""
        self._why.pop(end, None)
        self._asking.pop(end, None)
        place = clean_place(typed)
        if place is None:
            self.places[end] = None
            if counted:
                self._again(end)
            self._why[end] = voice.NOT_CAUGHT
            return
        if self.stations is None:
            self.places[end] = place
            self._check_same(counted=counted)
            return

        self.places[end] = place
        found = match_station(typed, self.stations)
        if found.station is not None:
            self._choose(end, found.station, counted=counted)
            return
        if found.several:
            # Not a wrong answer: a city with more than one station. Named by
            # the site's word for it when they share one, so "Lahor" is asked
            # about as Lahore.
            self._offered[end] = found.several
            firsts = {_plain(s).split()[0] for s in found.several}
            city = found.several[0].split()[0] if len(firsts) == 1 else place
            self._asking[end] = voice.which_station(voice.station_name(city))
            return
        if counted:
            self._again(end)
        if found.many:
            self._why[end] = voice.many_stations(place)
        elif found.close:
            self._offered[end] = found.close
            self._why[end] = voice.not_a_station(place)
        else:
            self._why[end] = voice.not_a_station(place)
        self.places[end] = None

    def _choose(self, end: str, station: str, *, counted: bool = True) -> None:
        self.chosen[end] = station
        self._why.pop(end, None)
        self._check_same(counted=counted)

    def _forget(self, end: str) -> None:
        self.places[end] = None
        self.chosen[end] = None
        self._offered.pop(end, None)
        self._why.pop(end, None)
        self._asking.pop(end, None)

    def _check_same(self, *, counted: bool) -> None:
        """A journey that starts where it ends is asked about again: where to."""
        ends = [self.chosen[end] if self.stations is not None else self.places[end]
                for end in self._ENDS]
        if None in ends or _plain(ends[0]) != _plain(ends[1]):
            return
        same = self._shown("origin")
        self._forget("destination")
        if counted:
            self._again("destination")
        self._why["destination"] = voice.same_station(same)

    def _answer_day(self, action_id: str, input_values: dict[str, str]) -> None:
        if not self._typing_day:
            picked = choice_index(action_id)
            if picked == 0:
                self.day = self.today
            elif picked == 1:
                self.day = self.today + timedelta(days=1)
            else:
                self._typing_day = True
            self._why.pop("day", None)
            return

        typed = input_values.get("day") or ""
        reading = read_day(typed, self.today)
        if reading.day is None and reading.problem is None and typed.strip().isdigit():
            # A bare number is a day of this month, or of the next if it has gone.
            found = _coming_day_of_month(int(typed.strip()), self.today)
            reading = (judge_day(found, self.today) if found
                       else DayReading(problem=NO_SUCH_DAY, said=f"day {typed.strip()}"))
        self.day = reading.day
        if self.day is None:
            self._why["day"] = day_trouble(reading, self.today) or voice.DAY_NOT_CAUGHT
            self._again("day")
        else:
            self._why.pop("day", None)

    # --- the task ----------------------------------------------------------------------

    def sentence(self) -> str:
        """The journey as one plain sentence, with the date written out."""
        return (f"Find trains from {self.origin} to {self.destination} "
                f"on {self.day.isoformat()}.")

    def task(self) -> Task:
        from backend.orchestrator.railways_plan import trip_task

        return replace(trip_task(self.origin, self.destination, self.day),
                       goal=self.goal,
                       heading=voice.route_heading(self._shown("origin"),
                                                   self._shown("destination"),
                                                   self.day, self.today))

    def _plan(self) -> tuple[Planner, Task]:
        from backend.orchestrator.railways_plan import TripPlanner

        task = self.task()
        if self._hardcoded:
            settled = self.stations is not None
            return TripPlanner(
                self.origin, self.destination, self.day, self.today,
                # Stations already chosen from the site's list are searched as
                # they are, and the journey has been read back: the search
                # step need not say it all again.
                stations={end: self.chosen[end] for end in self._ENDS} if settled else None,
                said_back=settled,
            ), task
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
    stages = voice.BILL_STAGES

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
        return self._ask(_typed(voice.ASK_REFERENCE, voice.REFERENCE_DETAIL, "reference",
                                voice.FIELD_REFERENCE, voice.USE_NUMBER),
                         note=voice.REFERENCE_NOT_RIGHT if self._tried("reference") else None)

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
    """A course to register for: its code.

    Since 2026-10-16 the hardcoded run asks which course on the portal itself,
    once signed in, from the courses it lists (`plan.CoursePlanner`): nothing
    is asked before the site is touched. The model-planned run cannot ask
    from a page, so it still asks first, in the person's own words."""

    plan_steps = 4
    stages = voice.COURSE_STAGES

    def __init__(self, goal: str, known: Understood, hardcoded: bool = True,
                 provider=None) -> None:
        super().__init__(goal)
        self.course = known.course
        self._hardcoded = hardcoded
        self._provider = provider

    def _missing(self) -> list[str]:
        return [] if self.course or self._hardcoded else ["course"]

    def question(self) -> Move | None:
        if self.gave_up is not None or self.course or self._hardcoded:
            return None
        return self._ask(_typed(voice.ASK_COURSE, voice.COURSE_DETAIL, "course",
                                voice.FIELD_COURSE, voice.USE_COURSE), stage=1,
                         note=voice.COURSE_NOT_CAUGHT if self._tried("course") else None)

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
            # was registered, and that is what has to name this one. Not yet
            # known when it is asked on the portal: `CoursePlanner.settled`
            # puts it in once chosen.
            about=About(shows=(Shown(reads="Course", says=self.course),)
                        if self.course else ()),
            # What changed, from what the portal confirmed: the closing
            # screen's last line (2026-10-16), and so not said twice.
            scope=voice.explain_course(self.course) if self.course else None,
        )

    def _plan(self) -> tuple[Planner, Task]:
        task = self.task()
        if self._hardcoded:
            return CoursePlanner(self.course), task
        from backend.orchestrator.llm_loop import LLMPlanner

        return LLMPlanner(self._provider, replace(task, goal=self.sentence())), task


BRIEFS = {"railways": TripBrief, "billing": BillBrief, "registration": CourseBrief}


def brief_for(flow: str, goal: str, known: Understood, *, hardcoded: bool = True,
              provider=None, today: date | None = None):
    """The brief for a routed flow, holding whatever the goal already said."""
    if flow == "railways":
        return TripBrief(goal, known, today, hardcoded, provider)
    return BRIEFS[flow](goal, known, hardcoded, provider)

