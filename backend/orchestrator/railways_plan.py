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

import os
from datetime import date

from backend.orchestrator.loop import Task
from backend.orchestrator.plan import (
    About,
    Answer,
    Expectation,
    FieldValue,
    Operation,
    PlanStep,
    Target,
)
from backend.orchestrator import voice
from backend.orchestrator.voice import actions
from shared.schema import StepField

RAILWAYS_URL = "https://www.pakrailways.gov.pk/train"

# The route, overridable so a verification run can pick one with several
# trains on it without editing the plan. The defaults are what every recorded
# railways number was measured on and do not change; an override is for a run
# that needs a particular shape of result — LAHORE CANTT to KARACHI CANTT
# returned two trains on 2026-09-09 and one on 2026-09-18, and "does the
# closing screen show every result" cannot be answered by a route that
# happens to have one.
ORIGIN = os.environ.get("SIMBA_RAILWAYS_FROM", "LAHORE CANTT")
DESTINATION = os.environ.get("SIMBA_RAILWAYS_TO", "KARACHI CANTT")


def _query(station: str, recorded: str) -> str:
    """Enough of a station's name to narrow the list without matching one.

    The recorded queries are kept exactly for the recorded route — "LAH"
    brings back six stations, which is the case worth exercising, and a
    different prefix would quietly measure a different thing. An overridden
    station gets six characters of its name, which is a prefix and not a whole
    station for every name on the list.
    """
    return recorded if station in ("LAHORE CANTT", "KARACHI CANTT") else station[:6]


ORIGIN_QUERY = os.environ.get("SIMBA_RAILWAYS_FROM_QUERY") or _query(ORIGIN, "LAH")
DESTINATION_QUERY = os.environ.get("SIMBA_RAILWAYS_TO_QUERY") or _query(DESTINATION, "KARACHI")

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
# What the site puts in the field once a date is actually committed. Not the
# same string that gets typed: the picker accepts `2026-10-15` and writes back
# `15-10-2026`, and the difference is the whole point — the typed value proves
# nothing, the committed one is the application agreeing.
DEPARTURE_AS_SHOWN = departure_date().strftime("%d-%m-%Y")

GOAL = f"Find trains from {ORIGIN} to {DESTINATION} on {DEPARTURE}."


RAILWAYS_TASK = Task(
    goal=GOAL,
    estimated_steps=5,
    # Results appeared...
    success=Expectation(rows_at_least=1),
    about=About(
        # ...*and* they are results for the date that was asked for.
        #
        # `rows_at_least` alone was the whole condition until 2026-09-09, and
        # it let a run finish wrongly: the LLM set the date to the month the
        # picker opened on, searched, got two real trains, and reported
        # `task.completed` against a goal naming a different month. "Results
        # appeared" is satisfied by a search for any date at all.
        #
        # The date cannot be checked in the results — the table has `Train
        # No.`, `From/To`, `Time` and `Duration`, and no date column — so the
        # only place it can be checked is the field the user watched being
        # filled.
        #
        # Both halves are needed. The held date alone would pass on a filled
        # form nobody had searched with; `rows_at_least` alone passed on the
        # wrong search. The loop never ends a run early on `holds` alone.
        holds=(FieldValue("Departure Date", DEPARTURE_AS_SHOWN),),
        # The goal asks which trains run, so the answer is the train and how
        # long it takes. Read from the results table once the search returns.
        finds=(
            Answer("Train", reads="Train No."),
            Answer("Journey", reads="Duration"),
        ),
    ),
)

RAILWAYS_PLAN: list[PlanStep] = [
    PlanStep(
        instruction="Let me set where you're starting from.",
        detail=f"Starting at {ORIGIN}.",
        fields=[StepField(id="from", label="From", type="text", value=ORIGIN)],
        actions=actions("Set the departure station"),
        operations=[
            Operation("fill", Target("textbox", "From"), value=ORIGIN_QUERY),
            # An `option` that the accessibility tree does not know exists.
            Operation("click", Target("option", ORIGIN)),
        ],
        # Committing the choice closes the list, which changes the page.
        expect=Expectation(label_gone=ORIGIN),
    ),
    PlanStep(
        instruction="Now where you're going.",
        detail=f"Arriving at {DESTINATION}.",
        fields=[StepField(id="to", label="To", type="text", value=DESTINATION)],
        actions=actions("Set the destination"),
        operations=[
            Operation("fill", Target("textbox", "To"), value=DESTINATION_QUERY),
            Operation("click", Target("option", DESTINATION)),
        ],
        expect=Expectation(label_gone=DESTINATION),
    ),
    PlanStep(
        instruction="Let me find the right month.",
        detail=f"Departing {DEPARTURE}.",
        actions=actions("Open the calendar"),
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
        instruction="Now the day you're travelling.",
        detail=f"{DEPARTURE}. Typing the date does not take — it has to be picked.",
        actions=actions("Set the date"),
        # A `td` in the calendar grid, with no role and no aria. Perception
        # infers it the same way it infers a dropdown option, and gives it the
        # same role: anything inside a floating panel is one of a set of
        # choices.
        #
        # `qualifier=""` means the day belonging to the month on screen. The
        # grid also carries trailing days of the previous month and leading
        # days of the next, and those are labelled with bare numbers too — so
        # without this, "15" could be matched against a cell from a month
        # nobody asked for. It does not bite on the 15th, which no grid shows
        # twice, and it is the difference between a plan that is correct and
        # one that happens to work.
        operations=[Operation("click", Target("option", DEPARTURE_DAY, qualifier=""))],
        expect=Expectation(label_gone=DEPARTURE_DAY),
    ),
    PlanStep(
        instruction="Ready to look up your trains.",
        detail="This only looks up the timetable. Nothing is booked.",
        actions=actions("Search"),
        # The search control is a button with no accessible name at all — no
        # text, no aria-label, a base64 icon only. `Target("button", "")` is
        # the honest description of what perception offers. It is unambiguous
        # here only because there happens to be exactly one unnamed button on
        # the page; `resolve` would otherwise pick by ordinal.
        operations=[Operation("click", Target("button", ""))],
        expect=Expectation(rows_at_least=1),
    ),
]


# --- a person's own journey ------------------------------------------------------
#
# Everything above is one fixed journey: the route and the day every recorded
# railways number was measured on. A person's request does not run it. It runs
# `TripPlanner`, with where they said they were going and when.


def as_shown(day: date) -> str:
    """A date the way the site writes it back once it is really set."""
    return day.strftime("%d-%m-%Y")


def trip_task(origin: str, destination: str, day: date) -> Task:
    """The task for one person's journey, and what has to be true at its end.

    Three things the person named, and all three are held: the day exactly,
    as the site writes it, and each station box naming the place they asked
    for. A search that came back with trains for another route or another day
    ends in `help.requested`, not `task.completed` — the failure this project
    has already produced once with a date (EVALUATION.md, case 6), and until
    2026-09-30 produced with the route every time, because the route was the
    plan's and not the person's.

    The places are matched loosely and the day is not. "Lahore" is the
    person's word and `LAHORE JN` is the site's; which Lahore station they
    meant is settled by asking them, and the planner checks the box holds the
    one they chose before it searches.
    """
    return Task(
        goal=f"Find trains from {origin} to {destination} on {day.isoformat()}.",
        estimated_steps=5,
        success=Expectation(rows_at_least=1),
        about=About(
            holds=(
                FieldValue("Departure Date", as_shown(day)),
                FieldValue("From", origin, names=True),
                FieldValue("To", destination, names=True),
            ),
            finds=(
                Answer("Train", reads="Train No."),
                Answer("Journey", reads="Duration"),
            ),
        ),
    )


def months_between(start: date, end: date) -> int:
    """How many times "Next Month" is pressed to get from one to the other."""
    return (end.year - start.year) * 12 + end.month - start.month


class TripPlanner:
    """Plans one journey on the train search, looking at the page as it goes.

    A list of steps written ahead of time cannot do this, because what to
    press depends on what the site offers. Typing "Lahore" brings back
    however many stations the site has in Lahore, and only then is it known
    whether there is one to choose or a question to ask. So each turn reads
    the page and decides: type the place, ask which station, choose it, find
    the month, pick the day, and — once the page holds all three — say the
    journey back in one sentence and search.

    The stations come from the site's own list and from nowhere else. A place
    is matched against whatever the list offers for it; one match is chosen,
    a few are asked about as buttons, and none ends the run saying so.

    Choosing a station after typing its name is the rest of a step the person
    already agreed to, so it is not shown again (`Move.quiet`).
    """

    calls_made = 0

    # The box each end of the journey goes in, and how its steps are worded.
    _BOX = {"origin": "From", "destination": "To"}
    _SAYS = {
        "origin": ("Let me set where you're starting from.", "Starting at {}.",
                   "Set the departure station"),
        "destination": ("Now where you're going.", "Arriving at {}.",
                        "Set the destination"),
    }

    def __init__(self, origin: str, destination: str, day: date,
                 today: date | None = None) -> None:
        self.places = {"origin": origin, "destination": destination}
        self.day = day
        self.today = today or date.today()
        self.stations: dict[str, str] = {}
        self.stuck_reason: str | None = None
        self._typed: dict[str, int] = {"origin": 0, "destination": 0}
        self._narrowed: dict[str, str] = {}
        self._done: set[str] = set()
        self._pending: str | None = None
        self._asking: tuple[str, list[str]] | None = None

    async def next_move(self, elements, history, setback):
        pending, self._pending = self._pending, None
        if pending is not None:
            if setback is None:
                self._done.add(pending)
            elif self._gives_up_on(pending):
                return None

        for end in ("origin", "destination"):
            if f"choose {end}" not in self._done:
                return self._station(end, elements)
        if "pick day" not in self._done:
            return self._day(elements)
        if "search" not in self._done:
            return self._search(elements)
        return None

    def answered(self, action_id: str, input_values: dict[str, str]) -> None:
        """The person's answer to the station question just asked."""
        if self._asking is None:
            return
        end, offered = self._asking
        self._asking = None
        if offered:
            index = action_id.removeprefix(voice.CHOICE_PREFIX)
            if index.isdigit() and int(index) < len(offered):
                self.stations[end] = offered[int(index)]
            return
        # Too many to show as buttons: they typed more of the name instead.
        more = " ".join((input_values.get("station") or "").split())
        if more:
            self._narrowed[end] = more

    # --- each part of the form ---------------------------------------------------

    def _gives_up_on(self, pending: str) -> bool:
        """A step that did not work. True if that ends the run, with a reason
        a person can read; otherwise the step is simply tried again, and the
        loop stops the run itself if it fails twice running."""
        if pending.startswith("type "):
            self.stuck_reason = voice.no_station(self.places[pending.split()[1]])
            return True
        if pending == "search":
            self.stuck_reason = voice.NO_TRAINS
            return True
        return False

    def _offered(self, end: str, elements) -> list[str]:
        """The stations the site is offering for this place, in its order."""
        place = self.places[end].casefold()
        more = self._narrowed.get(end, "").casefold()
        found: list[str] = []
        for element in elements:
            if element.role != "option" or element.qualifier == "disabled":
                continue
            label = element.label.casefold()
            if place in label and more in label and element.label not in found:
                found.append(element.label)
        return found

    def _station(self, end: str, elements):
        place = self.places[end]
        box = self._BOX[end]
        instruction, detail, button = self._SAYS[end]
        offered = self._offered(end, elements)

        if not offered:
            # Nothing on offer: the name has not been typed yet, or the list
            # closed while a question was on screen. Typed twice with nothing
            # to show for it, there is no such station.
            if self._typed[end] >= 2:
                self.stuck_reason = voice.no_station(place)
                return None
            self._typed[end] += 1
            self._pending = f"type {end}"
            query = (self._narrowed.get(end) or place).upper()
            return self._move(
                instruction, detail.format(place), button,
                operations=[
                    # The box is read-only until it is clicked.
                    Operation("click", Target("textbox", box)),
                    Operation("fill", Target("textbox", box), value=query),
                ],
                # The site has to offer something for the name before there
                # is anything to choose, and the list is fetched, so it is
                # given the longer window a fetched list needs.
                expect=Expectation(label_like=place, list_opens=True),
                quiet=self._typed[end] > 1,
            )

        station = self.stations.get(end)
        if station not in offered:
            if len(offered) == 1:
                station = offered[0]
            elif len(offered) <= voice.MAX_CHOICES:
                self._asking = (end, offered)
                return self._question(voice.which_station(place),
                                      answers=voice.choices([s.title() for s in offered]))
            else:
                self._asking = (end, [])
                # Typing more of the name means typing it into the box again.
                self._typed[end] = 0
                return self._question(
                    voice.narrow_station(place),
                    fields=[StepField(id="station", label=voice.FIELD_STATION,
                                      type="text", value="")],
                    answers=actions(voice.THATS_IT),
                )
            self.stations[end] = station

        self._pending = f"choose {end}"
        return self._move(
            instruction, detail.format(station.title()), button,
            operations=[Operation("click", Target("option", station))],
            # Committing the choice closes the list, which changes the page.
            expect=Expectation(label_gone=station),
            quiet=True,
        )

    def _day(self, elements):
        day = str(self.day.day)
        words = voice.day_words(self.day, self.today)
        # The cell for this day in the month on screen. "today" is the one
        # qualifier such a cell can carry; the greyed days either side of the
        # month carry "previous month" or "next month" and are never these.
        cells = [e for e in elements
                 if e.role == "option" and e.label == day and e.qualifier in ("", "today")]

        if "open month" in self._done and cells:
            cell = cells[0]
            # The calendar says which month it is showing, once, at the top.
            # If it says another month, the day on it is another day.
            if cell.panel and not (self.day.strftime("%B") in cell.panel
                                   and str(self.day.year) in cell.panel):
                self.stuck_reason = voice.WRONG_MONTH
                return None
            self._pending = "pick day"
            return self._move(
                "Now the day you're travelling.", f"{words}.", "Set the date",
                operations=[Operation("click", Target("option", day, qualifier=cell.qualifier))],
                expect=Expectation(label_gone=day),
            )

        self._done.discard("open month")
        self._pending = "open month"
        return self._move(
            "Let me find the right month.", f"Travelling on {words}.", "Open the calendar",
            operations=[
                Operation("click", Target("textbox", "Departure Date")),
                # The calendar opens on this month; the day may be in a later one.
                *[Operation("click", Target("button", "Next Month"))
                  for _ in range(months_between(self.today, self.day))],
            ],
            expect=Expectation(label_present=day),
        )

    def _search(self, elements):
        """The last look before searching: the page has to hold the journey.

        Checked here as well as at the end, because here it stops a wrong
        search from being sent at all — and the sentence on screen is then a
        description of the form, not a hope about it.
        """
        held = {e.label: e.value for e in elements if e.role == "textbox"}
        wanted = {
            "From": self.stations["origin"],
            "To": self.stations["destination"],
        }
        if held.get("Departure Date") != as_shown(self.day) or any(
            station.casefold() not in (held.get(box) or "").casefold()
            for box, station in wanted.items()
        ):
            self.stuck_reason = voice.FORM_CHANGED
            return None

        self._pending = "search"
        return self._move(
            voice.confirm_search(
                self.stations["origin"].title(), self.stations["destination"].title(),
                voice.day_words(self.day, self.today),
            ),
            "This only looks up the timetable. Nothing is booked.", "Search",
            # The search control is a button with no accessible name at all.
            operations=[Operation("click", Target("button", ""))],
            expect=Expectation(rows_at_least=1),
        )

    # --- shaping -----------------------------------------------------------------

    def _move(self, instruction, detail, button, *, operations, expect, quiet=False):
        from backend.orchestrator.loop import Move

        return Move(instruction=instruction, detail=detail, operations=operations,
                    expect=expect, fields=[], actions=actions(button), quiet=quiet)

    def _question(self, instruction, *, answers, fields=()):
        from backend.orchestrator.loop import Move

        return Move(instruction=instruction, detail="", operations=[],
                    expect=Expectation(), fields=list(fields), actions=answers,
                    question=True)
