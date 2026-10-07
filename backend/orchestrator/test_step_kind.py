"""What each step is about, for the icon beside it (2026-10-07).

`loop.kind_of` reads it off what a step does, unless the planner said; the
trip planner says, because it knows a station from a day. Checked over every
step of the three hardcoded plans, the trip planner's moves, and questions.
"""

from datetime import date

from backend.orchestrator.billing_plan import BILLING_PLAN
from backend.orchestrator.loop import Move, kind_of
from backend.orchestrator.plan import REGISTRATION_PLAN, Expectation
from backend.orchestrator.railways_plan import RAILWAYS_PLAN, TripPlanner, as_shown
from backend.orchestrator.voice import THATS_IT, actions, choices
from backend.orchestrator.test_trip import option, textbox
from shared.schema import StepField, StepPresented


def plan_kinds(plan) -> list[str]:
    return [kind_of(Move(instruction=s.instruction, detail=s.detail, operations=s.operations,
                         expect=s.expect, fields=s.fields, actions=s.actions))
            for s in plan]


def test_the_bill_is_agree_type_read() -> None:
    """Accept cookies, type the reference and look it up, open the full bill."""
    assert plan_kinds(BILLING_PLAN) == ["confirm", "type", "read"]


def test_registering_is_type_agree_agree() -> None:
    """Sign in, close the notice, register."""
    assert plan_kinds(REGISTRATION_PLAN) == ["type", "confirm", "confirm"]


def test_the_fixed_train_search_types_chooses_and_agrees() -> None:
    """Without a planner to say, a station typed in is "type"."""
    assert plan_kinds(RAILWAYS_PLAN) == ["type", "type", "confirm", "choose", "confirm"]


def test_the_trip_planner_says_place_date_and_agree() -> None:
    import asyncio

    day = date(2026, 10, 8)
    planner = TripPlanner("RAWALPINDI", "SUKKUR", day, date(2026, 10, 7),
                          stations={"origin": "RAWALPINDI", "destination": "SUKKUR"},
                          said_back=True)
    seen = []

    def next_move(elements):
        return asyncio.run(planner.next_move(elements, [], None))

    seen.append(kind_of(next_move([])))                                  # type Rawalpindi
    seen.append(kind_of(next_move([option("RAWALPINDI")])))              # choose it
    seen.append(kind_of(next_move([])))                                  # type Sukkur
    seen.append(kind_of(next_move([option("SUKKUR")])))                  # choose it
    seen.append(kind_of(next_move([])))                                  # open the month
    seen.append(kind_of(next_move([option("8", panel="2026 October")])))  # pick the day
    seen.append(kind_of(next_move([textbox("From", "RAWALPINDI"), textbox("To", "SUKKUR"),
                                   textbox("Departure Date", as_shown(day))])))  # search

    assert seen == ["place", "place", "place", "place", "date", "date", "confirm"]


def test_a_question_with_a_box_is_typing_and_one_with_buttons_is_choosing() -> None:
    typed = Move(instruction="q", detail="", operations=[], expect=Expectation(),
                 fields=[StepField(id="x", label="X", type="text", value="")],
                 actions=actions(THATS_IT), question=True)
    picked = Move(instruction="q", detail="", operations=[], expect=Expectation(),
                  fields=[], actions=choices(["A", "B"]), question=True)

    assert (kind_of(typed), kind_of(picked)) == ("type", "choose")


def test_a_kind_the_planner_gave_wins() -> None:
    move = Move(instruction="q", detail="", operations=[], expect=Expectation(), fields=[],
                actions=choices(["A"]), question=True, kind="date")
    assert kind_of(move) == "date"


def test_it_goes_out_with_the_step_and_an_old_step_has_none() -> None:
    sent = StepPresented(step_index=1, step_total=1, instruction="i", detail="", fields=[],
                         actions=[], requires_confirmation=True, step_kind="place")
    assert sent.model_dump()["step_kind"] == "place"
    old = StepPresented.model_validate({"step_index": 1, "step_total": 1, "instruction": "i",
                                        "detail": "", "fields": [], "actions": [],
                                        "requires_confirmation": True})
    assert old.step_kind is None


# --- the questions a journey asks (2026-10-07) ---------------------------------


def test_every_question_a_journey_asks_has_the_shape_of_what_it_asks() -> None:
    """Where from and where to are places, the day is a date — as buttons and
    typed — and the journey read back is the go-ahead. Asked of a brief that
    has read a station list, as the app's has."""
    from backend.orchestrator.test_trip_answers import STATIONS, brief, choice

    made = brief(origin="Lahore")
    asked = []
    for answer in (choice(1),                                 # which Lahore
                   ("confirm", {"destination": "Rawalpindi"}),
                   choice(2),                                 # pick another day
                   ("confirm", {"day": "tomorrow"}),
                   choice(1)):                                # no, change something
        asked.append(kind_of(made.question()))
        made.answered(*answer)
    asked.append(kind_of(made.question()))                    # what to change

    assert STATIONS
    assert asked == ["place", "place", "date", "date", "confirm", "choose"]


def test_the_bill_and_the_course_questions_are_typed() -> None:
    from backend.orchestrator.details import BillBrief, CourseBrief, Understood

    assert kind_of(BillBrief("g", Understood()).question()) == "type"
    assert kind_of(CourseBrief("g", Understood()).question()) == "type"
