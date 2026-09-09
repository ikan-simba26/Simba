"""The check that would have caught the wrong answer.

On 2026-09-09 an LLM run set the railways date to the 15th of September,
searched, got two real trains back, and reported `task.completed` against a
goal naming the 15th of October. Every check the loop had agreed: results
existed, the page had changed, nothing had lapsed since the last look.

`rows_at_least=1` is satisfied by a search for any date at all, and the date
is not in the results table to be checked. These tests rebuild that exact
snapshot and assert the run would now fail instead.

No browser and no network: the failure is entirely a question of what a
`Snapshot` says and what an `Expectation` asks of it.
"""

import pytest

from backend.orchestrator.loop import Snapshot, mismatch, satisfies
from backend.orchestrator.plan import Expectation, FieldValue
from backend.orchestrator.railways_plan import (
    DEPARTURE_AS_SHOWN,
    RAILWAYS_TASK,
)
from backend.perception.content import Content, Row, Table

# The results the wrong search actually returned, headers and all.
RESULTS = Content(
    tables=[
        Table(
            headers=("Train No.", "From/To", "Time", "Duration"),
            rows=(
                Row(cells=(("Train No.", "2DN"),
                           ("From/To", "LAHORE CANTT KARACHI CANTT"),
                           ("Time", "08:04 06:20"),
                           ("Duration", "22 h 16 min"))),
                Row(cells=(("Train No.", "14DN"),
                           ("From/To", "LAHORE CANTT KARACHI CANTT"),
                           ("Time", "19:09 19:25"),
                           ("Duration", "24 h 16 min"))),
            ),
        )
    ]
)

LABELS = ("Home", "Train Timings", "From", "To", "Departure Date", "")


def railways_page(date_shown: str) -> Snapshot:
    """The live search page as it stood at the end of that run.

    The URL and title never change on this site — it is a single-page app —
    which is why neither can be part of a success condition here.
    """
    return Snapshot(
        url="https://www.pakrailways.gov.pk/train",
        title="RABTA",
        labels=LABELS,
        values=("", "", "LAHORE CANTT", "KARACHI CANTT", date_shown, ""),
        content=RESULTS,
    )


WRONG_MONTH = railways_page("15-09-2026")
RIGHT_MONTH = railways_page(DEPARTURE_AS_SHOWN)


# --- the exact failing case -------------------------------------------------


def test_a_search_on_the_wrong_date_no_longer_counts_as_success() -> None:
    """The regression this exists for, stated as an assertion."""
    assert not satisfies(WRONG_MONTH, RAILWAYS_TASK.success)

    reason = mismatch(WRONG_MONTH, RAILWAYS_TASK.success)
    assert "Departure Date" in reason
    assert "15-09-2026" in reason
    assert DEPARTURE_AS_SHOWN in reason


def test_the_old_condition_would_have_let_it_through() -> None:
    """Which check was too weak, pinned down rather than asserted in prose.

    Same page, same results. `rows_at_least=1` passes on it. That is not a
    bug in `rows_at_least` — it answers the question it was asked. It is the
    wrong question for a goal that names a date.
    """
    assert satisfies(WRONG_MONTH, Expectation(rows_at_least=1))


def test_the_right_date_with_results_does_succeed() -> None:
    """The control: the condition is not simply unsatisfiable."""
    assert satisfies(RIGHT_MONTH, RAILWAYS_TASK.success)


def test_both_halves_are_load_bearing() -> None:
    """A filled form nobody searched with is not success either."""
    filled_but_unsearched = Snapshot(
        url="https://www.pakrailways.gov.pk/train",
        title="RABTA",
        labels=LABELS,
        values=("", "", "LAHORE CANTT", "KARACHI CANTT", DEPARTURE_AS_SHOWN, ""),
        content=Content(),
    )

    assert satisfies(filled_but_unsearched, Expectation(value_is=RAILWAYS_TASK.success.value_is))
    assert not satisfies(filled_but_unsearched, RAILWAYS_TASK.success)


# --- value_is on its own ----------------------------------------------------


def test_an_empty_field_is_an_answer_not_an_absence() -> None:
    """A field the page has emptied is exactly what this is for."""
    emptied = railways_page("")

    reason = mismatch(emptied, RAILWAYS_TASK.success)
    assert "it holds ''" in reason


def test_a_missing_field_says_so_rather_than_passing() -> None:
    """Absent and empty are different, and neither is success."""
    gone = Snapshot(url="u", title="t", labels=("Something else",), values=("x",))

    reason = mismatch(gone, Expectation(value_is=FieldValue("Departure Date", "x")))
    assert "expected a field called 'Departure Date'" in reason


def test_the_expected_value_is_what_the_page_shows_not_what_was_typed() -> None:
    """The distinction the widget forces.

    The picker accepts `2026-10-15` and writes back `15-10-2026`. A condition
    written against the typed string would fail at the moment the value became
    real, which is the opposite of what it is for.
    """
    assert RAILWAYS_TASK.success.value_is.equals == DEPARTURE_AS_SHOWN
    assert not satisfies(railways_page("2026-10-15"), RAILWAYS_TASK.success)


@pytest.mark.parametrize("held", ["15-10-2026 ", " 15-10-2026", "15-10-26", "15/10/2026"])
def test_a_near_miss_is_still_a_miss(held: str) -> None:
    """Exact, deliberately. A date that is nearly right is a wrong answer."""
    assert not satisfies(railways_page(held), RAILWAYS_TASK.success)


def test_value_of_reads_the_field_by_its_label() -> None:
    assert WRONG_MONTH.value_of("Departure Date") == "15-09-2026"
    assert WRONG_MONTH.value_of("From") == "LAHORE CANTT"
    assert WRONG_MONTH.value_of("Nothing called this") is None


def test_an_expectation_with_no_value_check_ignores_values() -> None:
    """Every existing task is unaffected."""
    assert satisfies(WRONG_MONTH, Expectation(rows_at_least=1))
    assert satisfies(WRONG_MONTH, Expectation())
