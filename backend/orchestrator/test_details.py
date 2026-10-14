"""Reading a person's own details out of what they typed.

Until 2026-09-30 a goal was a label. "Trains to Rawalpindi tomorrow" ran
Lahore Cantt to Karachi Cantt on the 15th of next month, because that is what
the plan said, and the closing screen then showed real trains for a journey
nobody had asked about. `details.py` reads the goal instead; `test_asking.py`
covers what the loop does with a question, and this covers what is asked and
why.

Two readers, and both are tested: the configured model, and the keyword and
date reader that runs when there is no model — offline, in the tests, and on
demo day. The model is never trusted with a value it could have invented: a
reference number or a course code is kept only if those characters are in what
the person typed, and a day has to be a real date, today or later.

Today is fixed at Wednesday 2026-09-30 throughout, so "tomorrow" and "Friday"
mean something an assertion can name.
"""

import asyncio
import concurrent.futures
from datetime import date

import pytest

from backend.orchestrator import voice
from backend.orchestrator.details import (
    MAX_TRIES,
    BillBrief,
    CourseBrief,
    DetailsChoice,
    TripBrief,
    Understood,
    brief_for,
    clean_course,
    clean_reference,
    find_day,
    find_places,
    understand,
    usable_day,
)
from backend.orchestrator.llm import LLMError

TODAY = date(2026, 9, 30)
TOMORROW = date(2026, 10, 1)


def read(flow: str, goal: str, model=None) -> Understood:
    # On its own thread, for the reason `test_router.routed` has one: a sync
    # Playwright session from a frontend test in the same run holds a loop on
    # this one (`backend/conftest.py`).
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(
            asyncio.run, understand(flow, goal, model=model, today=TODAY)
        ).result()


# --- a goal that says everything -------------------------------------------


def test_a_goal_with_every_detail_is_only_read_back() -> None:
    """Nothing to ask for, so the one thing asked is whether it is right
    (2026-10-06): the journey is read back before anything is done."""
    known = read("railways", "trains from Lahore to Rawalpindi on 3 October")

    assert known.origin == "Lahore"
    assert known.destination == "Rawalpindi"
    assert known.day == date(2026, 10, 3)
    brief = brief_for("railways", "g", known, today=TODAY)
    question = brief.question()
    assert question is not None
    assert question.instruction == "Lahore to Rawalpindi, Saturday 3 October. Is that right?"
    brief.answered(f"{voice.CHOICE_PREFIX}0", {})
    assert brief.question() is None


def test_a_goal_with_some_details_asks_only_for_the_rest() -> None:
    """The task's own example: where from is the one thing missing."""
    known = read("railways", "trains to Rawalpindi tomorrow")

    assert known.origin is None
    assert known.destination == "Rawalpindi"
    assert known.day == TOMORROW

    question = brief_for("railways", "trains to Rawalpindi tomorrow", known,
                         today=TODAY).question()
    assert question is not None and question.instruction == voice.ASK_FROM


def test_a_goal_with_no_details_asks_for_all_three_in_turn() -> None:
    known = read("railways", "I need a train")
    brief = brief_for("railways", "I need a train", known, today=TODAY)

    assert (known.origin, known.destination, known.day) == (None, None, None)
    asked = []
    for answer in (("confirm", {"origin": "Lahore"}),
                   ("confirm", {"destination": "Rawalpindi"}),
                   (f"{voice.CHOICE_PREFIX}1", {})):
        question = brief.question()
        assert question is not None
        asked.append(question.instruction)
        brief.answered(*answer)

    assert asked == [voice.ASK_FROM, voice.ASK_TO, voice.ASK_DAY]
    assert brief.question() is not None  # the journey, read back
    brief.answered(f"{voice.CHOICE_PREFIX}0", {})
    assert brief.question() is None
    assert (brief.origin, brief.destination, brief.day) == ("Lahore", "Rawalpindi", TOMORROW)


# --- the day ----------------------------------------------------------------


@pytest.mark.parametrize("said, expected", [
    ("today", date(2026, 9, 30)),
    ("tonight", date(2026, 9, 30)),
    ("tomorrow", date(2026, 10, 1)),
    ("tommorow", date(2026, 10, 1)),
    ("tmrw", date(2026, 10, 1)),
    ("the day after tomorrow", date(2026, 10, 2)),
    ("on 3 October", date(2026, 10, 3)),
    ("3rd october", date(2026, 10, 3)),
    ("October 3", date(2026, 10, 3)),
    ("oct 3rd", date(2026, 10, 3)),
    ("on the 3rd of October", date(2026, 10, 3)),
    ("2026-10-03", date(2026, 10, 3)),
    ("3/10", date(2026, 10, 3)),
    ("3/10/2026", date(2026, 10, 3)),
    ("3.10.26", date(2026, 10, 3)),
    ("on Friday", date(2026, 10, 2)),
    ("next monday", date(2026, 10, 5)),
    # A day named in a month that has gone is next year's.
    ("on 3 January", date(2027, 1, 3)),
    # The same weekday as today means the next one, unless they say "this".
    ("on Wednesday", date(2026, 10, 7)),
    ("this Wednesday", date(2026, 9, 30)),
])
def test_the_day_a_sentence_names(said: str, expected: date) -> None:
    found, _ = find_day(f"trains to Rawalpindi {said}", TODAY)
    assert found == expected


def test_a_sentence_with_no_day_says_so() -> None:
    assert find_day("trains to Rawalpindi", TODAY) == (None, None)


@pytest.mark.parametrize("gone", ["2026-09-29", "29/9/2026", "on 29 September 2026"])
def test_a_day_that_has_already_gone_is_not_usable(gone: str) -> None:
    """Asked about rather than searched for. A date in the past is either a
    typing slip or a misunderstanding, and neither is a journey. It takes a
    year to say one: a day and month on their own roll forward instead."""
    found, _ = find_day(gone, TODAY)
    assert found is not None and found < TODAY
    assert usable_day(found, TODAY) is None


@pytest.mark.parametrize("said, expected", [
    ("on 3 September", date(2027, 9, 3)),
    ("on 3 October", date(2026, 10, 3)),
    ("sept 29", date(2027, 9, 29)),
])
def test_a_day_and_month_with_no_year_mean_the_next_time_that_day_comes(
    said: str, expected: date
) -> None:
    """Someone typing "3 September" on the 30th of September means next year's,
    because this year's cannot be travelled on. The alternative is to read it
    as a date in the past and then tell them so, which is answering a question
    they did not ask. A year, written out, is still taken literally."""
    found, _ = find_day(said, TODAY)
    assert found == expected


def test_a_day_years_away_is_not_usable() -> None:
    """A mistyped year, not a plan. Anything within a year is kept."""
    assert usable_day(date(2028, 1, 3), TODAY) is None
    assert usable_day(date(2027, 9, 30), TODAY) == date(2027, 9, 30)


def test_the_day_is_read_out_of_the_sentence_before_the_places_are() -> None:
    """Otherwise "to Multan on 3 October" is a place called that."""
    known = read("railways", "trains from Lahore to Multan on 3 October")

    assert known.destination == "Multan"
    assert known.day == date(2026, 10, 3)


# --- where from and where to ------------------------------------------------


@pytest.mark.parametrize("goal, places", [
    ("trains from Lahore to Rawalpindi", ("Lahore", "Rawalpindi")),
    ("Lahore to Karachi", ("Lahore", "Karachi")),
    ("I want to go from Lahore to Karachi", ("Lahore", "Karachi")),
    ("book me a seat to Multan from Faisalabad", ("Faisalabad", "Multan")),
    ("trains to Rawalpindi", (None, "Rawalpindi")),
    ("Rawalpindi to Lahore Cantt", ("Rawalpindi", "Lahore Cantt")),
])
def test_where_a_sentence_says_it_is_going(goal: str, places: tuple) -> None:
    assert find_places(goal) == places


def test_an_ordinary_to_is_grammar_and_not_a_journey() -> None:
    """"I want to go" has a "to" in it and names nowhere."""
    assert find_places("I want to go") == (None, None)
    assert find_places("I need to check something") == (None, None)


def test_the_words_around_a_journey_are_not_taken_for_places() -> None:
    known = read("railways", "please show me the train timings to Rawalpindi tomorrow")
    assert known.origin is None
    assert known.destination == "Rawalpindi"


def test_a_place_is_kept_as_the_person_wrote_it() -> None:
    """The page decides whether it is a station; nothing here corrects them."""
    assert read("railways", "trains from lahore to RAWALPINDI").origin == "Lahore"
    assert read("railways", "trains from lahore to RAWALPINDI").destination == "Rawalpindi"


# --- a reference number and a course code -----------------------------------


@pytest.mark.parametrize("said", [
    "04141234567890",
    "0414 1234 567890",
    "0414-1234-567890",
    "my bill, reference 04141234567890, is it due",
])
def test_a_reference_number_however_it_was_spaced(said: str) -> None:
    assert clean_reference(said) == "04141234567890"


@pytest.mark.parametrize("said", ["0414123456789", "check my bill", "041412345678901234"])
def test_something_that_is_not_a_reference_number_is_not_read_as_one(said: str) -> None:
    """Fourteen digits or nothing: a number that is nearly one would look up
    somebody else's bill, or none."""
    assert clean_reference(said) is None


@pytest.mark.parametrize("said, code", [
    ("register for CS-401", "CS-401"),
    ("CS401", "CS-401"),
    ("cs 401", "CS-401"),
    ("I want to take MT-201 this term", "MT-201"),
    ("sign me up for phys 101a", "PHYS-101A"),
])
def test_a_course_code_the_way_the_portal_prints_it(said: str, code: str) -> None:
    assert clean_course(said) == code


def test_a_goal_with_no_course_code_asks_for_one() -> None:
    known = read("registration", "I want to register for a course")

    assert known.course is None
    question = brief_for("registration", "g", known).question()
    assert question is not None and question.instruction == voice.ASK_COURSE


def test_a_goal_with_no_reference_number_asks_for_one() -> None:
    known = read("billing", "check my electricity bill")

    assert known.reference is None
    question = brief_for("billing", "g", known).question()
    assert question is not None and question.instruction == voice.ASK_REFERENCE


def test_only_what_the_flow_could_use_is_looked_for() -> None:
    """A number in a train request is not a course code, and a station name in
    a bill request is not a station."""
    assert read("railways", "trains to Multan 401").course is None
    assert read("billing", "bill for 04141234567890").destination is None
    assert read("registration", "register for CS-401").reference is None


# --- the model, and what happens when it is not there -----------------------


class FakeReader:
    """Stands in for a provider's `read_details`. Records what it was asked."""

    def __init__(self, answer: object = None, error: Exception | None = None,
                 slow: bool = False) -> None:
        self.answer = answer
        self.error = error
        self.slow = slow
        self.asked: list[str] = []

    async def read_details(self, system_prompt: str, goal: str) -> DetailsChoice:
        self.asked.append(goal)
        if self.error is not None:
            raise self.error
        if self.slow:
            await asyncio.sleep(30)
        return DetailsChoice.model_validate(self.answer)


def test_the_model_is_asked_once_and_believed() -> None:
    model = FakeReader({"origin": "Lahore", "destination": "Rawalpindi",
                        "date": "2026-10-03", "reference": None, "course": None})

    known = read("railways", "I'd like to be in Pindi by Saturday, leaving Lahore", model)

    assert model.asked == ["I'd like to be in Pindi by Saturday, leaving Lahore"]
    assert (known.origin, known.destination) == ("Lahore", "Rawalpindi")
    assert known.day == date(2026, 10, 3)


def test_the_model_reads_what_the_keywords_cannot() -> None:
    """The reason there is a model at all: a sentence with no "from" or "to"."""
    plain = read("railways", "I'd like to be in Pindi by Saturday, leaving Lahore")
    assert plain.destination is None

    model = FakeReader({"origin": "Lahore", "destination": "Rawalpindi",
                        "date": "2026-10-03", "reference": None, "course": None})
    assert read("railways", "I'd like to be in Pindi by Saturday, leaving Lahore",
                model).destination == "Rawalpindi"


def test_what_the_model_did_not_say_the_keywords_still_supply() -> None:
    model = FakeReader({"origin": "Lahore", "destination": None,
                        "date": None, "reference": None, "course": None})

    known = read("railways", "trains from Lahore to Rawalpindi tomorrow", model)

    assert known.destination == "Rawalpindi"
    assert known.day == TOMORROW


@pytest.mark.parametrize("failure", [
    LLMError("ANTHROPIC_API_KEY is not set"),
    LLMError("details response did not match"),
    RuntimeError("quota"),
])
def test_a_model_that_cannot_answer_falls_back_to_the_keywords(failure: Exception) -> None:
    known = read("railways", "trains to Rawalpindi tomorrow", FakeReader(error=failure))

    assert known.destination == "Rawalpindi"
    assert known.day == TOMORROW


def test_a_slow_model_does_not_keep_the_person_waiting() -> None:
    """The same bound routing has, for the same reason: this is a person
    waiting at a screen that has not been drawn yet."""
    from backend.orchestrator import details

    model = FakeReader({"origin": "X", "destination": "Y", "date": None,
                        "reference": None, "course": None}, slow=True)
    original = details.MODEL_TIMEOUT_S
    details.MODEL_TIMEOUT_S = 0.05
    try:
        known = read("railways", "trains to Rawalpindi tomorrow", model)
    finally:
        details.MODEL_TIMEOUT_S = original

    assert known.destination == "Rawalpindi"


def test_a_reference_number_the_model_invented_is_thrown_away() -> None:
    """Nothing the model reports is kept unless the person typed it. A bill
    that was never asked about is somebody else's bill."""
    model = FakeReader({"origin": None, "destination": None, "date": None,
                        "reference": "04149999999999", "course": None})

    known = read("billing", "check my electricity bill", model)

    assert known.reference is None


def test_a_reference_number_the_person_did_type_is_kept() -> None:
    model = FakeReader({"origin": None, "destination": None, "date": None,
                        "reference": "04141234567890", "course": None})

    known = read("billing", "bill for 0414 1234 567890", model)

    assert known.reference == "04141234567890"


def test_a_course_the_model_invented_is_thrown_away() -> None:
    model = FakeReader({"origin": None, "destination": None, "date": None,
                        "reference": None, "course": "CS-401"})

    assert read("registration", "sign me up for something", model).course is None
    assert read("registration", "sign me up for cs401", model).course == "CS-401"


@pytest.mark.parametrize("said", ["not a date", "2026-13-40", "2026-09-01", ""])
def test_a_day_the_model_gives_that_cannot_be_travelled_on_is_dropped(said: str) -> None:
    """Malformed, impossible, or already gone: all the same answer."""
    model = FakeReader({"origin": "Lahore", "destination": "Rawalpindi",
                        "date": said, "reference": None, "course": None})

    assert read("railways", "trains from Lahore to Rawalpindi", model).day is None


def test_an_empty_goal_is_not_sent_to_the_model() -> None:
    model = FakeReader({"origin": "Lahore", "destination": "Rawalpindi",
                        "date": None, "reference": None, "course": None})

    assert read("railways", "   ", model) == Understood()
    assert model.asked == []


# --- what a question accepts ------------------------------------------------


def trip(goal: str = "I need a train", **known) -> TripBrief:
    return TripBrief(goal, Understood(**known), today=TODAY)


def test_the_day_is_offered_as_buttons_first() -> None:
    brief = trip(origin="Lahore", destination="Rawalpindi")

    question = brief.question()

    assert question is not None and question.fields == []
    assert [a.label for a in question.actions] == [
        voice.DAY_TODAY, voice.DAY_TOMORROW, voice.DAY_PICK, voice.STOP]


@pytest.mark.parametrize("pressed, expected", [(0, TODAY), (1, TOMORROW)])
def test_today_and_tomorrow_need_nothing_typed(pressed: int, expected: date) -> None:
    brief = trip(origin="Lahore", destination="Rawalpindi")
    brief.question()

    brief.answered(f"{voice.CHOICE_PREFIX}{pressed}", {})

    assert brief.day == expected
    # Nothing typed, and nothing more asked but whether the journey is right.
    read_back = brief.question()
    assert read_back is not None and read_back.instruction.endswith("Is that right?")


def test_pick_a_day_asks_for_one_and_takes_it_in_plain_words() -> None:
    brief = trip(origin="Lahore", destination="Rawalpindi")
    brief.question()
    brief.answered(f"{voice.CHOICE_PREFIX}2", {})

    typing = brief.question()
    assert typing is not None
    assert typing.instruction == voice.ASK_WHICH_DAY
    assert [f.id for f in typing.fields] == ["day"]

    brief.answered("confirm", {"day": "3 October"})
    assert brief.day == date(2026, 10, 3)


def test_a_bare_number_typed_for_a_day_is_a_day_of_the_month() -> None:
    brief = trip(origin="Lahore", destination="Rawalpindi")
    brief.question()
    brief.answered(f"{voice.CHOICE_PREFIX}2", {})
    brief.question()

    brief.answered("confirm", {"day": "3"})

    assert brief.day == date(2026, 10, 3)


def test_a_day_that_has_gone_is_asked_about_again_in_different_words() -> None:
    brief = trip(origin="Lahore", destination="Rawalpindi")
    brief.question()
    brief.answered(f"{voice.CHOICE_PREFIX}2", {})
    brief.question()

    brief.answered("confirm", {"day": "29 September 2026"})

    assert brief.day is None
    again = brief.question()
    assert again is not None and again.note == voice.day_gone("29 September")
    assert again.instruction == voice.ASK_TRAVEL_DAY


def test_a_day_nobody_could_read_is_asked_about_again() -> None:
    brief = trip(origin="Lahore", destination="Rawalpindi")
    brief.question()
    brief.answered(f"{voice.CHOICE_PREFIX}2", {})
    brief.question()

    brief.answered("confirm", {"day": "sometime soon"})

    again = brief.question()
    assert again is not None and again.note == voice.DAY_NOT_CAUGHT


def test_asking_the_same_thing_forever_is_not_an_option() -> None:
    """Three tries, then the run says it is stuck rather than asking a fourth
    time. `test_asking.py` covers what the loop does with that."""
    brief = BillBrief("check my bill", Understood())

    for _ in range(MAX_TRIES):
        assert brief.question() is not None
        brief.answered("confirm", {"reference": "not a number"})

    assert brief.question() is None
    assert brief.gave_up == voice.NOT_UNDERSTOOD


def test_the_second_ask_says_what_was_wrong_with_the_first_answer() -> None:
    brief = BillBrief("check my bill", Understood())
    brief.question()

    brief.answered("confirm", {"reference": "1234"})

    again = brief.question()
    assert again is not None and again.note == voice.REFERENCE_NOT_RIGHT
    # The question itself is asked as before; what was wrong is beside it.
    assert again.instruction == voice.ASK_REFERENCE


def test_a_course_question_says_what_a_course_code_looks_like() -> None:
    brief = CourseBrief("register me for a course", Understood())

    question = brief.question()

    assert question is not None
    assert question.detail == voice.COURSE_DETAIL
    brief.answered("confirm", {"course": "mt201"})
    assert brief.course == "MT-201"


def test_a_question_asks_for_one_thing_and_offers_a_way_to_stop() -> None:
    """Every question, whichever brief asked it."""
    for brief in (trip(), BillBrief("g", Understood()), CourseBrief("g", Understood())):
        question = brief.question()
        assert question is not None
        assert len(question.fields) <= 1
        assert question.operations == []
        assert question.question is True
        assert question.actions[-1].id == voice.CANCEL_ID


def test_what_is_still_to_come_is_counted_before_the_first_question() -> None:
    """So the number on screen does not grow as the person answers. A journey
    counts its reading back as one more thing on screen (2026-10-06)."""
    assert trip().estimated_steps == 3 + 1 + TripBrief.plan_steps
    assert trip(origin="Lahore", destination="Rawalpindi").estimated_steps == (
        1 + 1 + TripBrief.plan_steps)
    assert BillBrief("g", Understood()).estimated_steps == 1 + BillBrief.plan_steps
    assert BillBrief("g", Understood(reference="04141234567890")).estimated_steps == (
        BillBrief.plan_steps)


def test_a_count_read_twice_is_the_same_count() -> None:
    """The promise is frozen when it is made. A question asked again, because
    the answer could not be used, does not inflate it — and neither does
    answering one. On 2026-09-30 the number on screen went 1 of 7 then 2 of 5
    in one run, which is the failure `test_asking.py` pins from the loop's
    side."""
    brief = trip()
    first = brief.estimated_steps

    brief.question()
    brief.answered("confirm", {"origin": "Lahore"})
    brief.question()
    brief.answered("confirm", {"destination": ""})

    assert first == 3 + 1 + TripBrief.plan_steps
    assert brief.estimated_steps == first
