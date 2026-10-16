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
from backend.orchestrator.voice import USE_DAY, actions, choices
from backend.orchestrator.test_trip import option, textbox
from shared.schema import StepField, StepPresented


def plan_kinds(plan) -> list[str]:
    return [kind_of(Move(instruction=s.instruction, detail=s.detail, operations=s.operations,
                         expect=s.expect, fields=s.fields, actions=s.actions))
            for s in plan]


def test_the_bill_is_agree_type_read() -> None:
    """Say yes to cookies, type the reference and look it up, open the full bill."""
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
                 actions=actions(USE_DAY), question=True)
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
    assert kind_of(CourseBrief("g", Understood(), hardcoded=False).question()) == "type"


def test_a_station_in_a_steps_detail_is_written_to_be_read() -> None:
    """The site writes `KARACHI CANTT`; the step said "Arriving at KARACHI
    CANTT." until 2026-10-14. A place the person typed keeps their case."""
    import asyncio

    chosen = TripPlanner("RAWALPINDI", "KARACHI CANTT", date(2026, 10, 8), date(2026, 10, 7),
                         stations={"origin": "RAWALPINDI", "destination": "KARACHI CANTT"})
    typed = TripPlanner("Lahore", "Multan", date(2026, 10, 8), date(2026, 10, 7))

    assert asyncio.run(chosen.next_move([], [], None)).detail == "Starting at Rawalpindi."
    assert asyncio.run(typed.next_move([], [], None)).detail == "Starting at Lahore."



# --- the stage each step is in (2026-10-14) ---------------------------------------


def test_every_question_a_journey_asks_is_in_its_stage() -> None:
    """From, To, Day, then Search for the reading back and what to change. A
    question asked again stays in its stage, so the row never grows."""
    from backend.orchestrator.test_trip_answers import brief, choice

    made = brief()
    assert made.stages == ["From", "To", "Day", "Search", "Trains"]
    stages = []
    for answer in (("confirm", {"origin": "Narnia"}),       # wrong: asked again, same stage
                   ("confirm", {"origin": "Lahore Cantt"}),
                   ("confirm", {"destination": "Rawalpindi"}),
                   choice(2),                               # pick another day
                   ("confirm", {"day": "31 February"}),     # wrong: asked again
                   ("confirm", {"day": "tomorrow"}),
                   choice(1)):                              # no, change something
        stages.append(made.question().stage)
        made.answered(*answer)
    stages.append(made.question().stage)                    # what to change

    assert stages == [0, 0, 1, 2, 2, 2, 3, 3]


def test_the_plans_are_in_their_stages() -> None:
    assert [s.stage for s in BILLING_PLAN] == [1, 1, 1]
    # Signing in is the first stage since 2026-10-16.
    assert [s.stage for s in REGISTRATION_PLAN[:2]] == [0, 0]
    from backend.orchestrator.plan import registration_plan

    assert registration_plan("CS-401")[-1].stage == 2


def test_the_bill_and_course_questions_are_the_first_stage() -> None:
    from backend.orchestrator.details import BillBrief, CourseBrief, Understood

    assert BillBrief("g", Understood()).question().stage == 0
    # The course is asked once signed in (2026-10-16), the second stage.
    assert CourseBrief("g", Understood(), hardcoded=False).question().stage == 1
    assert BillBrief("g", Understood()).stages == ["Reference", "Look up", "Your bill"]
    assert CourseBrief.stages == ["Sign in", "Course", "Register", "Done"]


def test_the_trip_planners_moves_are_the_search_stage() -> None:
    import asyncio

    planner = TripPlanner("RAWALPINDI", "SUKKUR", date(2026, 10, 8), date(2026, 10, 7),
                          stations={"origin": "RAWALPINDI", "destination": "SUKKUR"})
    assert asyncio.run(planner.next_move([], [], None)).stage == 3
