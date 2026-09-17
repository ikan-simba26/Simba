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

#: `task.failed.reason` when the person pressed `STOP`. It is shown on the
#: screen, under "I couldn't finish this.", and it used to read "The user
#: chose not to continue." — about the person, in the third person, to them.
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
