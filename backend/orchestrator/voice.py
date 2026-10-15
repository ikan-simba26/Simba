"""The backend's half of what the interface says.

`frontend/src/copy.ts` holds every sentence the overlay writes itself. It
cannot hold these, because the contract has the backend author them: the
instruction on each step, its detail line, the labels on its buttons, the
suggestion on the stuck screen, the reason on the failed screen, and the
caption in the trust panel all arrive as strings in a message.

Until this file existed those strings were scattered across three plans, the
LLM planner, replay, the loop and the mock backend, with nothing checking any
of them — so the voice was set in two places and only one was enforceable.
Now everything that is not specific to one task is here, and everything that
*is* specific to one task (a plan's own instructions) is checked against the
same rules by `frontend/test_copy.py`:

  * a sentence ends with a full stop or a question mark, and a button label
    ends with nothing;
  * no word the reader would have to be taught — "step", "session",
    "verify", "retry", "overlay" — and never "the user", because the person
    reading it *is* the user;
  * straight apostrophes only, the same as `copy.ts`;
  * no web address in anything a person reads;
  * every step offers the same way to stop, in the same words;
  * where the backend and `copy.ts` voice the same situation, the same
    sentence.

Imports nothing but the schema, so a plan, the mock backend and a test can
all use it without pulling in a browser.
"""

import re

from shared.schema import StepAction

# --- the two buttons on every step ------------------------------------------

#: Agrees to a move the planner described in its own words. Used by every
#: planner that does not write a label per step — the LLM, and replay.
GO_AHEAD = "Yes, do that"

#: The way out of any step. The same words on every step of every plan,
#: because the person should never have to read the second button to find out
#: whether it is still the one that stops.
STOP = "Stop this"

CONFIRM_ID = "confirm"
CANCEL_ID = "cancel"


def actions(label: str) -> list[StepAction]:
    """The primary action, named for this step, and the one way to stop."""
    return [
        StepAction(id=CONFIRM_ID, label=label, kind="primary"),
        StepAction(id=CANCEL_ID, label=STOP, kind="secondary"),
    ]


# --- a question, and its answers ---------------------------------------------
#
# When something the task needs was not said, the person is asked — one thing
# at a time, as an ordinary `step.presented`. Where the answers are few they
# are buttons; otherwise there is one box to type in and one button to say
# that is it. Either way the same way to stop is underneath.

#: What every button that answers a question has at the front of its id. The
#: one id that stops is `CANCEL_ID`; anything else a question offers is an
#: answer, and the overlay carries on rather than showing its stop screen.
CHOICE_PREFIX = "choice:"

#: Said when a picture of the page could not be had in time (2026-10-16).
#: `copy.ts` has the same words, `TRUST.noPicture`, for when nothing came.
NO_PICTURE = "I couldn't get a picture just now."

#: Each finishes a typed answer, and says what it does with it (2026-10-15).
#: Until then all four were "That's it", which says nothing about what
#: happens next.
USE_STATION = "Use this station"
USE_DAY = "Use this day"
USE_NUMBER = "Use this number"
USE_COURSE = "Use this course"
#: All four: what tells a typed question's answer from a go-ahead.
TYPED_ANSWERS = (USE_STATION, USE_DAY, USE_NUMBER, USE_COURSE)

#: The most answers a question shows as buttons. More than this is a list to
#: read, which is the thing this interface exists to spare someone.
MAX_CHOICES = 4


def choices(labels: list[str]) -> list[StepAction]:
    """One button per answer, and the one way to stop."""
    return [
        *(StepAction(id=f"{CHOICE_PREFIX}{index}", label=label, kind="primary")
          for index, label in enumerate(labels)),
        StepAction(id=CANCEL_ID, label=STOP, kind="secondary"),
    ]


# --- the checklist: what SIMBA is doing by itself (2026-10-14) -------------
#
# Once the person has decided, the safe mechanical moves run without a press
# each, and each is one line of a checklist that ticks off. Labels: no full
# stop, said as what is happening.

DOING_FROM = "Filling in where you're starting from"
DOING_TO = "Filling in where you're going"
DOING_CALENDAR = "Opening the calendar"
DOING_SEARCH = "Searching"
DOING_LOOKUP = "Looking up your bill"
DOING_FULL_BILL = "Opening the full bill"
DOING_NOTICE = "Closing the portal's notice"


def doing_day(words: str) -> str:
    """`Choosing 15 October`."""
    return f"Choosing {words}"


#: When the person pressed Pause on the checklist. Nothing more is done until
#: they say so.
PAUSED = "I've paused. Carry on when you're ready."
#: The `step.response` action id the checklist's Pause sends.
PAUSE_ID = "pause"

# The stages of each task, by name, shown in place of a count (2026-10-14).
# Labels: no full stop, and never the word the rules forbid.
TRIP_STAGES = ["From", "To", "Day", "Search", "Trains"]
BILL_STAGES = ["Reference", "Look up", "Your bill"]
# Signing in first since 2026-10-16: which course is asked from the
# portal's own list, which is only there once signed in.
COURSE_STAGES = ["Sign in", "Course", "Register", "Done"]

ASK_FROM = "Where are you travelling from?"
ASK_TO = "Where are you travelling to?"
ASK_DAY = "What day are you travelling?"
DAY_TODAY = "Today"
DAY_TOMORROW = "Tomorrow"
DAY_PICK = "Pick another day"
ASK_WHICH_DAY = "Which day? You can type it like 3 October."
#: The question for a day after one could not be used.
ASK_TRAVEL_DAY = "Which day would you like to travel?"
#: The question when a few stations are offered for a name the list lacks.
ASK_CLOSEST = "Did you mean one of these?"

# What was wrong with an answer: one kind sentence, sent as the step's `note`
# beside the question asked again, never inside it (2026-10-14). The overlay
# clears it once a valid answer is chosen; until then the question still
# reads on its own.
NOT_CAUGHT = "I didn't catch that."
DAY_NOT_CAUGHT = "I didn't catch that day."

#: Answers to a question about a station, past the stations themselves: the
#: way back to the whole list when none of the few offered is the one.
NONE_OF_THESE = "None of these"

# --- reading the journey back, once, before anything is done (2026-10-06) --

READ_BACK_YES = "Yes, that's right"
READ_BACK_NO = "No, change something"
ASK_CHANGE = "What would you like to change?"
CHANGE_FROM = "Where from"
CHANGE_TO = "Where to"
CHANGE_DAY = "The day"
#: The search step, once the journey has been read back and agreed. Saying
#: the whole journey a second time is reading it back twice.
READY_TO_SEARCH = "Everything is filled in. Shall I search for your trains?"


def station_name(name: str) -> str:
    """A station as a person reads it. The site writes `LAHORE CANTT`; a name
    in capitals is harder to read, so it is shown as `Lahore Cantt`. A name
    already in mixed case is left as the site wrote it."""
    return name.title() if name.isupper() else name


_TRIP_GOAL = re.compile(r"Find trains from (.+?) to (.+?) on \d{4}-\d{2}-\d{2}\.?")
_BILL_GOAL = re.compile(r"Find the amount due for reference number (\d{4,})\.?")
_COURSE_GOAL = re.compile(r"Register for the course (\S+?)\.?")


def short_label(goal: str) -> str | None:
    """A remembered goal in a few words, for the home screen's one line
    (2026-10-16): "Trains Lahore Cantt to Rawalpindi", "Bill ending 7890",
    "Course CS-401". Built from the sentences the briefs write
    (`details.*Brief.sentence`), which are what is remembered; anything else
    has no label and is shown in its own words."""
    if (trip := _TRIP_GOAL.fullmatch(goal.strip())) is not None:
        return f"Trains {station_name(trip[1])} to {station_name(trip[2])}"
    if (bill := _BILL_GOAL.fullmatch(goal.strip())) is not None:
        return f"Bill ending {bill[1][-4:]}"
    if (course := _COURSE_GOAL.fullmatch(goal.strip())) is not None:
        return f"Course {course[1]}"
    return None


def when_words(day, today) -> str:
    """The day of a journey the way a person would check it: `tomorrow,
    7 October`, `today, 6 October`, or `Friday 16 October`."""
    delta = (day - today).days
    if delta == 0:
        return f"today, {day_words(day, today)}"
    if delta == 1:
        return f"tomorrow, {day_words(day, today)}"
    return f"{day.strftime('%A')} {day_words(day, today)}"


def route_heading(origin: str, destination: str, day, today) -> str:
    """Above the trains found: `Lahore Cantt to Karachi Cantt, Thursday 15
    October` — the journey the person agreed, not anything the page said."""
    return f"{origin} to {destination}, {day.strftime('%A')} {day_words(day, today)}"


def read_back(origin: str, destination: str, when: str) -> str:
    """The journey, once, before anything on the site is touched."""
    return f"{origin} to {destination}, {when}. Is that right?"


# --- an answer that cannot be used, said kindly, and asked again ------------
#
# Each one says what was understood and what to do instead, and never that
# the person was wrong. Every answer is checked before anything is done.


def day_gone(said: str) -> str:
    return f"{said} has already passed."


def day_too_far(last: str) -> str:
    return f"I can only look up trains up to {last}."


def no_such_day(said: str) -> str:
    return f"There is no {said} in the calendar."


def not_a_station(typed: str) -> str:
    """A name the site's list does not have."""
    return f"I couldn't find a station called {typed}."


def many_stations(typed: str) -> str:
    return f"Lots of stations have {typed} in their name."


def same_station(name: str) -> str:
    """Where to, when it is where from."""
    return f"{name} is where you're starting from."
ASK_REFERENCE = "What is the reference number on your bill?"
REFERENCE_DETAIL = "It is the 14-digit number at the top left of your bill."
REFERENCE_NOT_RIGHT = "That doesn't look like a 14-digit reference number."
ASK_COURSE = "Which course would you like to register for?"
COURSE_DETAIL = "A course code looks like CS-401."
COURSE_NOT_CAUGHT = "I didn't catch that course."
#: Above the portal's own list of courses, once signed in (2026-10-16).
COURSES_OFFERED = "These are the courses the portal offers. Type the first few letters."
#: `help.requested.reason` when the portal lists no course to register for.
NO_COURSES = "The portal didn't show any courses to register for."


def course_not_offered(course: str) -> str:
    """The note beside the course question, when the one named is not on the
    portal's list (2026-10-16): caught at the question, not at the button."""
    return f"The portal doesn't offer {course}."

#: The label beside the box a typed answer goes in.
FIELD_FROM = "From"
FIELD_TO = "To"
FIELD_DAY = "Day"
FIELD_REFERENCE = "Reference number"
FIELD_COURSE = "Course"
FIELD_STATION = "Station"

#: `help.requested.reason` when the same question has been asked three times.
NOT_UNDERSTOOD = "I asked a few times and still couldn't work out what you meant."


def day_words(day, today) -> str:
    """A date the way a person says it: `3 October`, with the year only when
    it is not this one."""
    words = f"{day.day} {day.strftime('%B')}"
    return words if day.year == today.year else f"{words} {day.year}"


def which_station(place: str) -> str:
    return f"Which {place} station do you mean?"


def narrow_station(place: str) -> str:
    return f"There are several {place} stations. Can you type more of the name?"


def confirm_search(origin: str, destination: str, day: str) -> str:
    """The one sentence before a search, so the person can see what is about
    to be looked up and stop it if it is not what they meant."""
    return f"Trains from {origin} to {destination} on {day}. Shall I search?"


def no_station(place: str) -> str:
    """When the site offered nothing for a place the person named.

    It says what happened and not what it means, because the two cases cannot
    be told apart from here. On 2026-09-30 this read "I couldn't find a
    station called Lahore." and was shown for Lahore, which has two stations
    on that site: the name had gone into the box but the list had not opened
    yet, and a list that has not arrived looks exactly like a place that has
    no stations (EVALUATION.md).
    """
    return f"The site didn't offer me any stations for {place}."


NO_TRAINS = "I searched, and no trains came back for that day."
WRONG_MONTH = "The calendar on the page isn't showing the month you asked for."
FORM_CHANGED = "The page no longer holds what I put in it, so I haven't searched."


# --- the sentence on the closing screen ------------------------------------
#
# One plain sentence above the result, saying what it means: "There are 3
# trains. The fastest takes 6 hours 3 minutes." (2026-10-03). Built only from
# values the page returned — every number in it is one the page printed, or a
# count of them — and when a value is not in a shape these can read safely, the
# sentence says less rather than guess: no sentence at all, or the page's own
# words where a rewording would have been.

_JOURNEY = re.compile(r"\s*(\d+)\s*h\s*(\d+)\s*min\s*")


def _minutes(journey: str) -> int | None:
    """`6 h 3 min` as 363, or None for anything else."""
    match = _JOURNEY.fullmatch(journey)
    return int(match[1]) * 60 + int(match[2]) if match else None


_CLOCK = re.compile(r"\s*(\d{1,2}):(\d{2})\s*")


def _clock(time: str) -> int | None:
    """`06:20` as minutes past midnight, or None for anything else."""
    match = _CLOCK.fullmatch(time)
    return int(match[1]) * 60 + int(match[2]) if match else None


#: How far a journey's end may be from leaving time plus journey time and
#: still be that journey's end: the site rounds neither, but says so nowhere.
_CLOCK_SLACK = 5


def days_later(leaves: str, arrives: str, journey: str = "") -> int:
    """How many days after it leaves a train arrives (2026-10-15).

    From the journey time when the page gives one that agrees with the two
    clock times: the live site's 14DN leaves 19:09, takes 24 h 16 min and
    arrives at 19:25 — a later clock time, and still the next day. Without a
    journey time that agrees, only what the clocks say: arriving at an
    earlier time than it left is the next day. Never a guess past that.
    """
    left, came = _clock(leaves), _clock(arrives)
    if left is None or came is None:
        return 0
    taken = _minutes(journey)
    if taken is not None:
        total = left + taken
        gap = abs(total % 1440 - came)
        if min(gap, 1440 - gap) <= _CLOCK_SLACK:
            return round((total - came) / 1440)
    return 1 if came < left else 0


def arrival(row: dict[str, str]) -> dict[str, str]:
    """A results row with its arrival said as the day it is: "00:50, next
    day", "19:25, 2 days later". A row that arrives the day it leaves, or
    has no arrival, is as it was."""
    arrives = row.get("Arrives", "")
    days = days_later(row.get("Leaves", ""), arrives, row.get("Journey", ""))
    if not arrives or days == 0:
        return row
    return {**row, "Arrives": f"{arrives}, {NEXT_DAY if days == 1 else f'{days} days later'}"}


#: After an arrival time on the day after the train leaves.
NEXT_DAY = "next day"


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def duration(journey: str) -> str:
    """`6 h 3 min` as `6 hours 3 minutes`; anything else exactly as the page
    wrote it."""
    minutes = _minutes(journey)
    if minutes is None:
        return journey.strip()
    hours, rest = divmod(minutes, 60)
    parts = [_plural(hours, "hour")] if hours else []
    if rest or not hours:
        parts.append(_plural(rest, "minute"))
    return " ".join(parts)


def _readable(*values: str) -> bool:
    """Nothing in a sentence a person reads may be a web address (the same
    rule as every other string here)."""
    return all(v and "://" not in v and "www." not in v.lower() for v in values)


def _listed(names: list[str]) -> str:
    """"A and B", "A, B and C"."""
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def explain_trains(found: dict[str, list[str]], seen: dict[str, list[str]],
                   rows: list[dict[str, str]] | None = None) -> str | None:
    """How many trains came back, and which is fastest or how long it takes.

    From the results whole when there are rows (2026-10-05): a row is a train,
    and its journey is its own. `found` drops a repeated value, so two trains
    with one journey time there are two trains and one time; read from it the
    count is right only because train numbers do not repeat.

    With rows and two trains or more, the fastest is named, because a row says
    which train each time belongs to (2026-10-06): "The fastest is 1UP, at 6
    hours 3 minutes." A tie is said as a tie rather than one train picked:
    two or three are named, more are counted, and when every train ties the
    sentence says they all take the same. One train, or no rows, keeps the
    wording that names no train, since without rows nothing says whose the
    shortest time is.
    """
    if rows:
        listed = [row for row in rows if row.get("Train")]
        trains = [row["Train"] for row in listed]
        journeys = [row.get("Journey", "") for row in listed]
    else:
        trains = found.get("Train") or []
        journeys = found.get("Journey") or []
    if not trains:
        return None
    count = (f"There is {_plural(1, 'train')}." if len(trains) == 1
             else f"There are {len(trains)} trains.")
    minutes = [_minutes(j) for j in journeys]
    if not journeys or None in minutes or not _readable(*journeys):
        return count
    best = min(minutes)
    fastest = duration(journeys[minutes.index(best)])
    if rows and len(trains) > 1 and _readable(*trains):
        named: list[str] = []
        for train, taken in zip(trains, minutes):
            if taken == best and train not in named:
                named.append(train)
        if len(named) == 1:
            return f"{count} The fastest is {named[0]}, at {fastest}."
        if len(named) == len(set(trains)):
            return f"{count} They {'both' if len(named) == 2 else 'all'} take {fastest}."
        if len(named) <= 3:
            return (f"{count} {_listed(named)} are the fastest, "
                    f"{'both' if len(named) == 2 else 'all'} at {fastest}.")
        return f"{count} {len(named)} of them are the fastest, all at {fastest}."
    return f"{count} {'It takes' if len(trains) == 1 else 'The fastest takes'} {fastest}."


def explain_bill(found: dict[str, list[str]], seen: dict[str, list[str]],
                 rows: list[dict[str, str]] | None = None) -> str | None:
    """The amount and the date it is due, in the page's own figures."""
    amount, due = found.get("Your bill") or [], found.get("Due") or []
    if len(amount) != 1 or not _readable(*amount):
        return None
    if len(due) == 1 and _readable(*due):
        return f"Your bill is {amount[0]}, and it is due on {due[0]}."
    return f"Your bill is {amount[0]}."


#: The closing screen's last line, for a search: what was done and what was
#: not (2026-10-16). Nothing in this project books or pays, and the person
#: should not have to wonder.
ONLY_LOOKED_UP_TIMES = "I only looked up times. I did not book a ticket or pay for anything."
#: The same, for a bill.
ONLY_LOOKED_AT_BILL = "I only looked at your bill. I did not pay it."


def explain_course(course: str):
    """For a registration: which course the confirmation named, as it named it."""
    def explain(found: dict[str, list[str]], seen: dict[str, list[str]],
                rows: list[dict[str, str]] | None = None) -> str | None:
        named = [v for v in seen.get("Course") or [] if course.casefold() in v.casefold()]
        if not named or not _readable(named[0]):
            return None
        return f"You are registered for {named[0]}."
    return explain


# --- saved sign-in details -------------------------------------------------
#
# A step that asks for a password offers to remember it; once remembered, the
# step says it will use it and offers to forget it (`vault.py`, 2026-10-03).
# The password itself is never in any of these, or in any message at all.

#: Agrees to the step and keeps the password typed into it.
REMEMBER_ID = "remember"
#: Deletes what was saved for this site, and asks again.
FORGET_ID = "forget"

#: The detail line on a step that will sign in with saved details.
USING_SAVED = "I'll use the sign-in details you saved for this site."
#: The detail line once they have been forgotten, on the same step asked again.
FORGOTTEN = "I've forgotten them. Type them in to sign in this time."
FORGET = "Forget my saved password"


def remember(label: str) -> str:
    """The button that does the step and keeps the password: the step's own
    words, then what else it does."""
    if label == GO_AHEAD:
        return "Yes, and save my password"
    return f"{label} and save my password"


# --- when a run ends without finishing --------------------------------------

#: `help.requested.suggestion`. `test_copy.py` requires this to be exactly
#: `STOPPED.suggestion` in `copy.ts`, which is the frontend's fallback for the
#: same screen — so the stuck screen reads the same whichever side supplied it.
#:
#: It says what happens, because that is all it can truthfully say. When this
#: is sent the run has ended and the socket is about to close: nothing
#: resumes, and the person cannot reach the page to help. It used to ask them
#: to "do this part" and promise to "carry on after".
HELP_SUGGESTION = "I won't do any more on this. You can ask me for something else."

#: `task.failed.reason` when the person pressed `STOP`. It used to read "The
#: user chose not to continue." — about the person, in the third person, to
#: them. Since 2026-09-17 the overlay does not show it: it knows the person
#: pressed stop, and shows its own sentence rather than a failure screen.
YOU_STOPPED = "You asked me to stop."

# --- the window, put away during a task (2026-10-06) -----------------------

#: Shown when the SIMBA window comes back after being minimised or hidden while
#: the run had something to do. Nothing was done while it was away: a
#: minimised window paints about once a second, and a click there waits for a
#: page that never settles (EVALUATION.md, 2026-10-05d). The run goes on only
#: when the person says so.
WINDOW_BACK = "I waited while the window was closed. Ready to carry on?"
CARRY_ON = "Carry on"

# --- the trust panel --------------------------------------------------------

#: The caption when there is no move to describe.
PREVIEW_CAPTION = "This is the page I'm working on."

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


def caption(kind: str, where: str, key: str = "") -> str:
    """What is about to happen, for the trust panel. Never the value being typed."""
    if kind == "fill":
        return f"I'm about to type your {where} in here."
    if kind == "select":
        return f"I'm about to choose an option in {where}."
    if kind == "press":
        return f"I'm about to {KEY_CAPTIONS.get(key, f'press {key}')} on {where}."
    return f"I'm about to click {where}."


# --- what was found ---------------------------------------------------------

#: How many values a finding shows before it says how many are left.
#:
#: A results table can have twenty rows, and the closing screen shows a
#: finding in the largest type on it — the whole point being that the answer
#: is readable at a glance. Four values and a count keeps that true while
#: still saying, out loud, that there are more.
SHOWN_VALUES = 4


def found(values: list[str]) -> str:
    """Several values for one label, as one line a person can read.

    "2DN, 14DN" rather than "2DN" — a goal that asks which trains run is
    answered by all of them. Past `SHOWN_VALUES` it counts the rest instead of
    filling the screen.
    """
    if len(values) <= SHOWN_VALUES:
        return ", ".join(values)
    shown = ", ".join(values[:SHOWN_VALUES])
    return f"{shown} and {len(values) - SHOWN_VALUES} more"


# --- a move a planner chose, as an instruction ------------------------------


def describe(kind: str, label: str) -> str:
    """The instruction for a single operation a planner chose.

    Used by the LLM planner and by replay, which both produce one operation at
    a time and have no plan author to write the sentence.

    Not yet in the assistant's voice — "Fill in From." reads as an order to the
    person, where every hand-written plan says "Let me…". Left as it is on
    purpose: this sentence is also what the LLM is shown as its own history
    ("Already done: 1. Fill in From."), so rewording it changes the prompt, and
    the one LLM run the project is waiting on should measure the prompt that
    was designed for it. Flagged in STATUS.md.
    """
    if kind in ("fill", "type"):
        return f"Fill in {label}."
    if kind == "select":
        return f"Choose an option in {label}."
    return f"Click {label}."
