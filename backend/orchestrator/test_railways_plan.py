"""The railways plan must not expire.

The first version wrote `2026-10-15` down and set `MONTHS_AHEAD = 1`. That was
true for about three weeks. After it, the plan would have clicked "Next Month"
once and landed in a month that does not contain the date in its own goal
string — a failure that looks like a perception bug and is not one.

No network here. This is arithmetic and a plan structure.
"""

from datetime import date

import pytest

from backend.orchestrator.plan import Operation
from backend.orchestrator.railways_plan import (
    DEPARTURE,
    DEPARTURE_DAY,
    DEPARTURE_DAY_OF_MONTH,
    GOAL,
    MONTHS_AHEAD,
    RAILWAYS_PLAN,
    RAILWAYS_TASK,
    departure_date,
)


@pytest.mark.parametrize(
    "today,expected",
    [
        (date(2026, 1, 1), date(2026, 2, 15)),
        (date(2026, 1, 31), date(2026, 2, 15)),  # from a day February does not have
        (date(2026, 2, 27), date(2026, 3, 15)),
        (date(2026, 11, 30), date(2026, 12, 15)),
        (date(2026, 12, 1), date(2027, 1, 15)),  # the year rolls over
        (date(2026, 12, 31), date(2027, 1, 15)),
        (date(2028, 2, 29), date(2028, 3, 15)),  # from a leap day
    ],
)
def test_the_date_is_always_the_fifteenth_of_next_month(
    today: date, expected: date
) -> None:
    assert departure_date(today) == expected


def test_the_date_is_always_in_the_future(  ) -> None:
    """Whatever day it runs, the query is for a date that has not happened."""
    for month in range(1, 13):
        for day in (1, 15, 28):
            today = date(2026, month, day)
            assert departure_date(today) > today


def test_one_next_month_press_is_always_enough() -> None:
    """The plan presses "Next Month" a fixed number of times.

    That only stays correct because the target is always in the month
    immediately after the one the picker opens on.
    """
    assert MONTHS_AHEAD == 1
    for month in range(1, 13):
        today = date(2026, month, 28)
        target = departure_date(today)
        months_between = (target.year - today.year) * 12 + target.month - today.month
        assert months_between == MONTHS_AHEAD, (today, target)


def test_the_day_number_is_unambiguous_in_a_calendar_grid() -> None:
    """The plan clicks a day by its number, so the number has to be unique.

    Element UI's picker shows trailing days of the previous month and leading
    days of the next, so a low number can appear twice in one grid — the 1st
    shows as both "1 October" and a greyed "1 November". Anything from 13 to
    28 appears exactly once in every month.
    """
    assert 13 <= DEPARTURE_DAY_OF_MONTH <= 28


def test_the_goal_and_the_plan_agree_on_the_date() -> None:
    """The goal string is what the user is shown; the day is what gets clicked."""
    assert DEPARTURE in GOAL
    assert DEPARTURE.endswith(f"-{DEPARTURE_DAY_OF_MONTH}")
    assert DEPARTURE_DAY == str(DEPARTURE_DAY_OF_MONTH)
    assert date.fromisoformat(DEPARTURE) > date.today()


def test_the_plan_clicks_the_day_it_says_it_will() -> None:
    picks_day = [
        operation
        for step in RAILWAYS_PLAN
        for operation in step.operations
        if operation.target.label == DEPARTURE_DAY
    ]
    assert len(picks_day) == 1
    assert picks_day[0] == Operation("click", picks_day[0].target)
    # Inferred from layout — the calendar cell has no role of its own.
    assert picks_day[0].target.role == "option"


def test_the_plan_is_read_only() -> None:
    """No booking, no login, no registration — the standing constraint.

    Cheap to assert and worth asserting: this plan points at somebody's live
    public service, and the day someone adds a sixth step is the day this
    should fail.
    """
    assert RAILWAYS_TASK.estimated_steps == len(RAILWAYS_PLAN) == 5
    labels = {
        operation.target.label.lower()
        for step in RAILWAYS_PLAN
        for operation in step.operations
    }
    assert not {"log in", "sign in", "book", "pay", "register"} & labels
