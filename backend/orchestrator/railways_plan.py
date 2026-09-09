"""The railways flow: a read-only train search on a live public site.

This is the first flow that does not run against a replica we wrote. It
exists to find out what breaks, and the first time it ran, everything did —
see EVALUATION.md, 2026-09-07.

**Scope, deliberately narrow.** Choose origin, destination and date, submit
the search, read the results. No booking, no seat selection, no registration,
no login, and nothing that alters a record anywhere. That is both CLAUDE.md's
irreversible-action rule and simple manners on someone else's public service.

The target is `pakrailways.gov.pk/train`, not `pakrail.gov.pk`. The latter is
Pakistan Railways' informational site — ASP.NET, ~100 links, no search form
anywhere on it. The public train search lives on the other domain and is a
Vue single-page app. Neither domain serves a robots.txt.

**Why the plan is shaped the way it is.** Every step here is the answer to
something the first run got wrong, and none of it is arbitrary:

  * The station fields are `readonly` until clicked. `fill` waits for an
    element to be editable, so it times out on a field nothing is blocking.
    A fill is therefore always paired with the click that unlocks it, which
    the loop's second strategy now does on its own.
  * Typing a station name is not choosing one. The value has to be committed
    from the dropdown, and the dropdown is six `li`s with no role — invisible
    to perception until `interactivity.py` existed. Steps 1 and 2 aim at
    `option` elements that only exist because of it.
  * Typing a date is not choosing one either, and this one is worse: the
    input accepts `2026-10-15`, reads it straight back, and the application's
    own model stays empty. The outgoing request said `"travelDate":""` while
    the field on screen said `2026-10-15`. The only way to set it is to pick
    the day from the calendar — and the day cells are `td`s with no role,
    inferred exactly like the station options.

The departure date is computed from today rather than written down. A
hardcoded plan is allowed to be specific; it is not allowed to expire. The
first version said `2026-10-15` with `MONTHS_AHEAD = 1`, which was true for
about three weeks and would then have started clicking "Next Month" once to
land in the wrong month — the kind of failure that looks like a perception
bug and is not.
"""

from datetime import date

from backend.orchestrator.loop import Task
from backend.orchestrator.plan import Expectation, Operation, PlanStep, Target
from shared.schema import StepAction, StepField

RAILWAYS_URL = "https://www.pakrailways.gov.pk/train"

ORIGIN = "LAHORE CANTT"
DESTINATION = "KARACHI CANTT"
# Enough of the name to narrow the list without matching only one station —
# "LAH" brings back six, which is the case worth exercising.
ORIGIN_QUERY = "LAH"
DESTINATION_QUERY = "KARACHI"

# Far enough ahead to be a real timetable query rather than a same-day edge,
# and computed so the flow does not expire.
#
# The 15th of next month, always. Two properties the plan depends on, and
# both are why it is the 15th of *next* month rather than "today plus 30
# days":
#
#   * The day number is unambiguous in the calendar grid. Element UI's picker
#     shows trailing days from the previous month and leading days from the
#     next, so a low day number can appear twice — the 1st shows up as both
#     "1 October" and the greyed "1 November". Every month has a 15th, and
#     the 15th only ever appears once in a month's grid.
#   * The number of "Next Month" clicks is exactly one, whatever today is.
#     The picker opens on the current month, and next month is one press
#     away regardless of how near the end of this one we are.
MONTHS_AHEAD = 1
DEPARTURE_DAY_OF_MONTH = 15


def departure_date(today: date | None = None) -> date:
    """The date this plan books for, relative to when it runs.

    Takes `today` so a test can ask what the plan would do on any date
    without waiting for it to be that date.
    """
    anchor = today or date.today()
    # Month arithmetic by hand rather than adding a dependency for one line
    # (CLAUDE.md). Safe for any day-of-month <= 28, which 15 is: no month is
    # short of a 15th, so this never has to clamp.
    month = anchor.month + MONTHS_AHEAD
    year = anchor.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    return date(year, month, DEPARTURE_DAY_OF_MONTH)


DEPARTURE = departure_date().isoformat()
DEPARTURE_DAY = str(DEPARTURE_DAY_OF_MONTH)

GOAL = f"Find trains from {ORIGIN} to {DESTINATION} on {DEPARTURE}."


def _confirm(label: str) -> list[StepAction]:
    return [
        StepAction(id="confirm", label=label, kind="primary"),
        StepAction(id="cancel", label="Not now", kind="secondary"),
    ]


RAILWAYS_TASK = Task(
    goal=GOAL,
    estimated_steps=5,
    # A success condition, at last.
    #
    # This was `None` until perception could read content. The results of this
    # search are static text in a single-page app: the URL does not change,
    # the title does not change, and no row is interactive, so nothing in the
    # url/title/label vocabulary could describe having finished. "At least one
    # row of results exists" is the goal stated in the only terms that were
    # ever true of it.
    success=Expectation(rows_at_least=1),
)

RAILWAYS_PLAN: list[PlanStep] = [
    PlanStep(
        instruction="Choose where you are travelling from.",
        detail=f"Starting at {ORIGIN}.",
        fields=[StepField(id="from", label="From", type="text", value=ORIGIN)],
        actions=_confirm("Set the departure station"),
        operations=[
            Operation("fill", Target("textbox", "From"), value=ORIGIN_QUERY),
            # An `option` that the accessibility tree does not know exists.
            Operation("click", Target("option", ORIGIN)),
        ],
        # Committing the choice closes the list, which changes the page.
        expect=Expectation(label_gone=ORIGIN),
    ),
    PlanStep(
        instruction="Choose where you are travelling to.",
        detail=f"Arriving at {DESTINATION}.",
        fields=[StepField(id="to", label="To", type="text", value=DESTINATION)],
        actions=_confirm("Set the destination"),
        operations=[
            Operation("fill", Target("textbox", "To"), value=DESTINATION_QUERY),
            Operation("click", Target("option", DESTINATION)),
        ],
        expect=Expectation(label_gone=DESTINATION),
    ),
    PlanStep(
        instruction="Open the calendar and go to the right month.",
        detail=f"Departing {DEPARTURE}.",
        actions=_confirm("Open the calendar"),
        operations=[
            Operation("click", Target("textbox", "Departure Date")),
            *[
                Operation("click", Target("button", "Next Month"))
                for _ in range(MONTHS_AHEAD)
            ],
        ],
        expect=Expectation(label_present=DEPARTURE_DAY),
    ),
    PlanStep(
        instruction="Pick the day you want to travel.",
        detail=f"{DEPARTURE}. Typing the date does not take — it has to be picked.",
        actions=_confirm("Set the date"),
        # A `td` in the calendar grid, with no role and no aria. Perception
        # infers it the same way it infers a dropdown option, and gives it the
        # same role: anything inside a floating panel is one of a set of
        # choices.
        operations=[Operation("click", Target("option", DEPARTURE_DAY))],
        expect=Expectation(label_gone=DEPARTURE_DAY),
    ),
    PlanStep(
        instruction="Search for trains.",
        detail="This only looks up the timetable. Nothing is booked.",
        actions=_confirm("Search"),
        # The search control is a button with no accessible name at all — no
        # text, no aria-label, a base64 icon only. `Target("button", "")` is
        # the honest description of what perception offers. It is unambiguous
        # here only because there happens to be exactly one unnamed button on
        # the page; `resolve` would otherwise pick by ordinal.
        operations=[Operation("click", Target("button", ""))],
        expect=Expectation(rows_at_least=1),
    ),
]
