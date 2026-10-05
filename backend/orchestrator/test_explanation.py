"""The closing screen's one sentence: what the result means, from the page alone.

"There are 3 trains. The fastest takes 6 hours 3 minutes." Built by
`voice.explain_*` from the values the run found and the values the site said
back, and never from anything else. The rule this file holds above all is that
last one: every number in a sentence is a number the page printed, or a count
of the values it returned — and where a value is not in a shape these can read
safely, the sentence says less rather than guess.

The end-to-end half runs the real flows on the replicas and reads the sentence
off `task.completed`.
"""

import re

import pytest

from backend.orchestrator.test_billing import billing_replica  # noqa: F401 - fixture
from backend.orchestrator.test_orchestrator import replica  # noqa: F401 - fixture
from backend.orchestrator.test_trip import railways  # noqa: F401 - fixture
from backend.orchestrator.voice import (
    duration,
    explain_bill,
    explain_course,
    explain_trains,
)

#: The live search of 2026-09-30, run 6: three trains, as the page wrote them.
LIVE = {"Train": ["13UP", "39UP", "1UP"],
        "Journey": ["6 h 6 min", "6 h 38 min", "6 h 3 min"]}


def numbers_in(text: str) -> list[str]:
    return re.findall(r"\d[\d,-]*\d|\d", text)


# --- trains -----------------------------------------------------------------


def test_the_example_asked_for() -> None:
    assert explain_trains(LIVE, {}) == "There are 3 trains. The fastest takes 6 hours 3 minutes."


def test_one_train_is_not_the_fastest_of_one() -> None:
    assert explain_trains({"Train": ["9UP"], "Journey": ["8 h 15 min"]}, {}) == (
        "There is 1 train. It takes 8 hours 15 minutes.")


def test_the_fastest_is_the_shortest_journey_wherever_it_is_listed() -> None:
    found = {"Train": ["A", "B", "C"], "Journey": ["9 h 0 min", "4 h 59 min", "5 h 0 min"]}
    assert explain_trains(found, {}).endswith("The fastest takes 4 hours 59 minutes.")


def test_a_journey_it_cannot_read_leaves_the_fastest_unsaid() -> None:
    """Rather than guess which is fastest from words it does not understand."""
    found = {"Train": ["9UP", "10DN"], "Journey": ["8 h 15 min", "overnight"]}
    assert explain_trains(found, {}) == "There are 2 trains."


def test_no_trains_no_sentence() -> None:
    assert explain_trains({}, {}) is None
    assert explain_trains({"Train": [], "Journey": ["6 h 3 min"]}, {}) is None


@pytest.mark.parametrize("page, said", [
    ("6 h 3 min", "6 hours 3 minutes"),
    ("1 h 0 min", "1 hour"),
    ("0 h 45 min", "45 minutes"),
    ("2 h 1 min", "2 hours 1 minute"),
    ("0 h 0 min", "0 minutes"),
    ("about six hours", "about six hours"),  # not read, so not reworded
])
def test_a_journey_in_words(page: str, said: str) -> None:
    assert duration(page) == said


# --- a bill and a course ------------------------------------------------------


def test_a_bill_in_the_pages_own_figures() -> None:
    """No currency is added: the page did not print one."""
    assert explain_bill({"Your bill": ["14,382"], "Due": ["15-09-2026"]}, {}) == (
        "Your bill is 14,382, and it is due on 15-09-2026.")
    assert explain_bill({"Your bill": ["14,382"]}, {}) == "Your bill is 14,382."


def test_two_amounts_is_not_a_bill_it_can_explain() -> None:
    assert explain_bill({"Your bill": ["14,382", "9,001"], "Due": ["15-09-2026"]}, {}) is None


def test_a_course_as_the_confirmation_named_it() -> None:
    explain = explain_course("MATH-210")
    assert explain({}, {"Course": ["MATH-210 section 001"]}) == (
        "You are registered for MATH-210 section 001.")
    # Named another course: nothing said, rather than the wrong one.
    assert explain({}, {"Course": ["CS-401 section 001"]}) is None
    assert explain({}, {}) is None


# --- only the page's values ---------------------------------------------------


@pytest.mark.parametrize("found, seen, explain", [
    (LIVE, {}, explain_trains),
    ({"Train": ["9UP"], "Journey": ["8 h 15 min"]}, {}, explain_trains),
    ({"Your bill": ["14,382"], "Due": ["15-09-2026"]}, {}, explain_bill),
    ({}, {"Course": ["MATH-210 section 001"]}, explain_course("MATH-210")),
])
def test_every_number_said_is_one_the_page_printed_or_a_count(found, seen, explain) -> None:
    sentence = explain(found, seen)
    printed = " ".join(v for values in (*found.values(), *seen.values()) for v in values)
    counts = {str(len(values)) for values in found.values()}
    for number in numbers_in(sentence):
        assert number in printed or number in counts, (number, sentence)


def test_a_value_that_is_a_web_address_is_never_said() -> None:
    """The rule every on-screen string keeps: no address reaches the screen."""
    assert explain_bill({"Your bill": ["https://example.com/pay"]}, {}) is None
    assert explain_trains({"Train": ["1UP"], "Journey": ["www.example.com"]}, {}) == (
        "There is 1 train.")


# --- end to end, on the replicas --------------------------------------------------


def test_the_train_search_ends_with_its_sentence(railways: str) -> None:  # noqa: F811
    from backend.orchestrator.test_trip import TOMORROW, search

    run = search("Rawalpindi", "Multan", TOMORROW, [], railways)

    completed = run.of("task.completed")[0]
    trains = next(f["values"] for f in completed["findings"] if f["label"] == "Train")
    journeys = next(f["values"] for f in completed["findings"] if f["label"] == "Journey")
    assert completed["explanation"] == explain_trains(
        {"Train": trains, "Journey": journeys}, {})
    assert completed["explanation"].startswith(f"There are {len(trains)} trains.")


def test_the_bill_ends_with_its_sentence(billing_replica: str) -> None:  # noqa: F811
    from backend.orchestrator.billing_plan import BILLING_PLAN, BILLING_TASK
    from backend.orchestrator.plan import HardcodedPlanner
    from backend.orchestrator.test_billing import drive

    completed = drive(HardcodedPlanner(BILLING_PLAN), BILLING_TASK, billing_replica)\
        .payload_of("task.completed")

    assert completed["explanation"] == "Your bill is 14,382, and it is due on 15-09-2026."


def test_a_registration_ends_with_its_sentence(replica: str) -> None:  # noqa: F811
    from backend.orchestrator.test_course import register

    completed = register("MATH-210", replica).payload_of("task.completed")

    assert completed["explanation"] == "You are registered for MATH-210 section 001."


def test_a_task_with_nothing_to_explain_sends_none(replica: str) -> None:  # noqa: F811
    """The fixed registration plan declares no sentence; the field is absent
    (None), and the closing screen is what it was."""
    from backend.orchestrator.plan import REGISTRATION_PLAN
    from backend.orchestrator.test_verification import TASK, drive

    connection = drive(REGISTRATION_PLAN, replica)

    assert connection.payload_of("task.completed")["explanation"] is None
    assert TASK.explain is None

