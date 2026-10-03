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

#: Finishes a typed answer.
THATS_IT = "That's it"

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


ASK_FROM = "Where are you travelling from?"
ASK_TO = "Where are you travelling to?"
ASK_DAY = "What day are you travelling?"
DAY_TODAY = "Today"
DAY_TOMORROW = "Tomorrow"
DAY_PICK = "Pick a day"
ASK_WHICH_DAY = "Which day? You can type it like 3 October."
ASK_DAY_AGAIN = "I didn't catch that day. Try typing it like 3 October."
ASK_DAY_GONE = "That day has already gone. Which day would you like?"
ASK_REFERENCE = "What is the reference number on your bill?"
REFERENCE_DETAIL = "It is the 14-digit number at the top left of your bill."
ASK_REFERENCE_AGAIN = "That doesn't look right. The reference number has 14 digits."
ASK_COURSE = "Which course would you like to register for?"
COURSE_DETAIL = "A course code looks like CS-401."
ASK_COURSE_AGAIN = "I didn't catch that course. A course code looks like CS-401."

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
