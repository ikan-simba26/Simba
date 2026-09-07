"""The railways flow: a read-only train search on a live public site.

This is the first flow that does not run against a replica we wrote. It
exists to find out what breaks, and it does break — see EVALUATION.md,
2026-09-07.

**Scope, deliberately narrow.** Fill origin, destination and date, submit the
search, read the results. No booking, no seat selection, no registration, no
login, and nothing that alters a record anywhere. That is both CLAUDE.md's
irreversible-action rule and simple manners on someone else's public service.

The target is `pakrailways.gov.pk/train`, not `pakrail.gov.pk`. The latter is
Pakistan Railways' informational site — ASP.NET, ~100 links, no search form
anywhere on it. The public train search lives on the other domain and is a
Vue single-page app. Neither domain serves a robots.txt.
"""

from backend.orchestrator.loop import Task
from backend.orchestrator.plan import Expectation, Operation, PlanStep, Target
from shared.schema import StepAction, StepField

RAILWAYS_URL = "https://www.pakrailways.gov.pk/train"

ORIGIN = "LAHORE CANTT"
DESTINATION = "KARACHI CANTT"
# Far enough ahead to be a real timetable query rather than a same-day edge.
DEPARTURE = "2026-10-15"

GOAL = f"Find trains from {ORIGIN} to {DESTINATION} on {DEPARTURE}."


def _confirm(label: str) -> list[StepAction]:
    return [
        StepAction(id="confirm", label=label, kind="primary"),
        StepAction(id="cancel", label="Not now", kind="secondary"),
    ]


RAILWAYS_TASK = Task(
    goal=GOAL,
    estimated_steps=4,
    # There is no success condition this loop can express.
    #
    # A `Snapshot` is url, title and the labels of *interactive* elements. The
    # results of this search are a table of static text in a single-page app:
    # the URL does not change, the title does not change, and the rows are not
    # interactive, so none of them reach perception. There is nothing to
    # assert against. Left as None, which means the run ends when the plan
    # runs out rather than when the goal is met.
    success=None,
)

RAILWAYS_PLAN: list[PlanStep] = [
    PlanStep(
        instruction="Choose where you are travelling from.",
        detail=f"Starting at {ORIGIN}.",
        fields=[StepField(id="from", label="From", type="text", value=ORIGIN)],
        actions=_confirm("Set the departure station"),
        operations=[Operation("fill", Target("textbox", "From"), value=ORIGIN)],
        # A fill is verified by reading the field back, not by the page moving.
        expect=Expectation(),
    ),
    PlanStep(
        instruction="Choose where you are travelling to.",
        detail=f"Arriving at {DESTINATION}.",
        fields=[StepField(id="to", label="To", type="text", value=DESTINATION)],
        actions=_confirm("Set the destination"),
        operations=[Operation("fill", Target("textbox", "To"), value=DESTINATION)],
        expect=Expectation(),
    ),
    PlanStep(
        instruction="Choose the date you want to travel.",
        detail=f"Departing {DEPARTURE}.",
        fields=[
            StepField(id="date", label="Departure Date", type="text", value=DEPARTURE)
        ],
        actions=_confirm("Set the date"),
        operations=[
            Operation("fill", Target("textbox", "Departure Date"), value=DEPARTURE)
        ],
        expect=Expectation(),
    ),
    PlanStep(
        instruction="Search for trains.",
        detail="This only looks up the timetable. Nothing is booked.",
        actions=_confirm("Search"),
        # The search control is a button with no accessible name at all — no
        # text, no aria-label, an icon glyph only. `Target("button", "")` is
        # the honest description of what perception offers, and it is also
        # ambiguous: it matches every unnamed button on the page.
        operations=[Operation("click", Target("button", ""))],
        expect=Expectation(),
    ),
]
