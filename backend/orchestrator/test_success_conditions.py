"""The check that would have caught the wrong answer.

On 2026-09-09 an LLM run set the railways date to the 15th of September,
searched, got two real trains back, and reported `task.completed` against a
goal naming the 15th of October. Every check the loop had agreed: results
existed, the page had changed, nothing had lapsed since the last look.

`rows_at_least=1` is satisfied by a search for any date at all, and the date
is not in the results table to be checked. These tests rebuild that exact
snapshot and assert the run would now fail instead.

Since 2026-09-17 the date is declared in `About.holds` rather than in the
success expectation, alongside what the task asks to find out, and `unmet` is
the check the loop runs. The second half of this file is about that: that a
value declared once is checked without being declared again, and that a task
cannot be written without saying what it is about.

No browser and no network: the failure is entirely a question of what a
`Snapshot` says and what a `Task` asks of it.
"""

from dataclasses import replace

import pytest

from backend.orchestrator.loop import Snapshot, Task, findings_in, satisfies, unmet
from backend.orchestrator.plan import About, Answer, Expectation, FieldValue
from backend.orchestrator.railways_plan import (
    DEPARTURE_AS_SHOWN,
    RAILWAYS_TASK,
)
from backend.perception.content import Content, Pair, Row, Table

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
    reason = unmet(WRONG_MONTH, RAILWAYS_TASK)
    assert reason is not None
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
    assert unmet(RIGHT_MONTH, RAILWAYS_TASK) is None


def test_both_halves_are_load_bearing() -> None:
    """A filled form nobody searched with is not success either."""
    filled_but_unsearched = Snapshot(
        url="https://www.pakrailways.gov.pk/train",
        title="RABTA",
        labels=LABELS,
        values=("", "", "LAHORE CANTT", "KARACHI CANTT", DEPARTURE_AS_SHOWN, ""),
        content=Content(),
    )

    dates_only = replace(RAILWAYS_TASK, success=None)
    assert unmet(filled_but_unsearched, dates_only) is None
    assert unmet(filled_but_unsearched, RAILWAYS_TASK) is not None


# --- a held value on its own ------------------------------------------------


def test_an_empty_field_is_an_answer_not_an_absence() -> None:
    """A field the page has emptied is exactly what this is for."""
    emptied = railways_page("")

    reason = unmet(emptied, RAILWAYS_TASK)
    assert "it holds ''" in reason


def test_a_missing_field_says_so_rather_than_passing() -> None:
    """Absent and empty are different, and neither is success."""
    gone = Snapshot(url="u", title="t", labels=("Something else",), values=("x",))

    task = Task(goal="g", estimated_steps=1,
                about=About(holds=(FieldValue("Departure Date", "x"),)))
    reason = unmet(gone, task)
    assert "expected a field called 'Departure Date'" in reason


def test_the_expected_value_is_what_the_page_shows_not_what_was_typed() -> None:
    """The distinction the widget forces.

    The picker accepts `2026-10-15` and writes back `15-10-2026`. A condition
    written against the typed string would fail at the moment the value became
    real, which is the opposite of what it is for.
    """
    assert RAILWAYS_TASK.about.holds[0].equals == DEPARTURE_AS_SHOWN
    assert unmet(railways_page("2026-10-15"), RAILWAYS_TASK) is not None


@pytest.mark.parametrize("held", ["15-10-2026 ", " 15-10-2026", "15-10-26", "15/10/2026"])
def test_a_near_miss_is_still_a_miss(held: str) -> None:
    """Exact, deliberately. A date that is nearly right is a wrong answer."""
    assert unmet(railways_page(held), RAILWAYS_TASK) is not None


def test_value_of_reads_the_field_by_its_label() -> None:
    assert WRONG_MONTH.value_of("Departure Date") == "15-09-2026"
    assert WRONG_MONTH.value_of("From") == "LAHORE CANTT"
    assert WRONG_MONTH.value_of("Nothing called this") is None


def test_an_expectation_with_no_value_check_ignores_values() -> None:
    """Every existing task is unaffected."""
    assert satisfies(WRONG_MONTH, Expectation(rows_at_least=1))
    assert satisfies(WRONG_MONTH, Expectation())


# --- one declaration of what a task is about --------------------------------


def test_a_task_cannot_be_written_without_saying_what_it_is_about() -> None:
    """Forgetting is loud now.

    `Task.answers` and `Expectation.value_is` both defaulted to nothing, so a
    task that left either out checked nothing and showed nothing, and said so
    nowhere. `about` has no default.
    """
    with pytest.raises(TypeError):
        Task(goal="Find something.", estimated_steps=1)  # type: ignore[call-arg]


def test_a_named_value_is_checked_without_being_repeated_in_success() -> None:
    """The date is declared once, in `about`, and the success expectation
    does not mention it — and the wrong date still fails."""
    assert RAILWAYS_TASK.success == Expectation(rows_at_least=1)
    assert satisfies(WRONG_MONTH, RAILWAYS_TASK.success)
    assert unmet(WRONG_MONTH, RAILWAYS_TASK) is not None


def test_a_task_with_nothing_named_is_judged_by_success_alone() -> None:
    task = Task(goal="g", estimated_steps=1, success=Expectation(rows_at_least=1),
                about=About())
    assert unmet(WRONG_MONTH, task) is None


def test_what_a_task_finds_comes_from_the_same_declaration() -> None:
    """`finds` is read by name from the content channel, in declared order."""
    page = Snapshot(
        url="u", title="t", labels=(), values=(),
        content=Content(pairs=[Pair("Duration", "22 h 16 min"), Pair("Train No.", "2DN")]),
    )
    found = findings_in(page, RAILWAYS_TASK, {})
    assert [(f.label, f.value) for f in found] == [("Train", "2DN"), ("Journey", "22 h 16 min")]


def test_a_finding_is_remembered_after_the_page_stops_showing_it() -> None:
    """The billing amount is on the results page; the run ends on another."""
    task = Task(goal="g", estimated_steps=1,
                about=About(finds=(Answer("Your bill", reads="P/WITHIN"),)))
    known: dict[str, str] = {}
    results = Snapshot(url="u", title="t", labels=(),
                       content=Content(pairs=[Pair("P/WITHIN", "14,382")]))
    detail = Snapshot(url="u2", title="t", labels=(), content=Content())

    findings_in(results, task, known)
    found = findings_in(detail, task, known)

    assert [(f.label, f.value) for f in found] == [("Your bill", "14,382")]
