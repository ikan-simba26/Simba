"""A train that arrives after midnight says so (2026-10-15).

The site's Time cell is the two clock times, `08:04 06:20`; nothing in it
says the 06:20 is the next morning. The journey time does: 08:04 and 22 h 16
min is 06:20 a day later. The two rows recorded from the live site
(EVALUATION.md, 2026-09-18) are both next-day arrivals, one of them with an
arrival clock time later than its departure.
"""

import pytest

from backend.orchestrator.test_trip import TOMORROW, railways, search  # noqa: F401
from backend.orchestrator.voice import arrival, days_later


@pytest.mark.parametrize("leaves, arrives, journey, days", [
    # Recorded from the live site.
    ("08:04", "06:20", "22 h 16 min", 1),
    ("19:09", "19:25", "24 h 16 min", 1),  # a later clock time, still next day
    # The railways replica's 8DN.
    ("16:35", "00:50", "8 h 15 min", 1),
    ("07:25", "14:40", "7 h 15 min", 0),
    ("22:00", "23:59", "49 h 59 min", 2),
    ("23:50", "00:01", "0 h 9 min", 1),   # a minute either side of midnight
    ("23:50", "23:58", "0 h 9 min", 0),
    # No journey time, or one that does not agree: only what the clocks say.
    ("23:00", "01:00", "", 1),
    ("10:00", "11:00", "", 0),
    ("10:00", "09:00", "5 h 0 min", 1),
])
def test_days_later(leaves: str, arrives: str, journey: str, days: int) -> None:
    assert days_later(leaves, arrives, journey) == days


def test_the_arrival_says_the_day() -> None:
    row = {"Train": "8DN", "Leaves": "16:35", "Arrives": "00:50", "Journey": "8 h 15 min"}
    assert arrival(row)["Arrives"] == "00:50, next day"
    assert arrival({**row, "Arrives": "23:59", "Leaves": "22:00",
                    "Journey": "49 h 59 min"})["Arrives"] == "23:59, 2 days later"


def test_a_same_day_row_or_a_row_without_times_is_as_it_was() -> None:
    same = {"Train": "7UP", "Leaves": "07:25", "Arrives": "14:40", "Journey": "7 h 15 min"}
    assert arrival(same) == same
    bare = {"Train": "7UP", "Journey": "7 h 15 min"}
    assert arrival(bare) == bare
    unreadable = {"Train": "7UP", "Leaves": "early", "Arrives": "late"}
    assert arrival(unreadable) == unreadable


def test_the_results_say_it_on_the_replica(railways: str) -> None:  # noqa: F811
    """Lahore Cantt to Karachi Cantt on our copy: 8DN leaves 16:35 and arrives
    at 00:50, 8 h 15 min later."""
    run = search("Lahore Cantt", "Karachi Cantt", TOMORROW, [], railways)

    completed = run.of("task.completed")[0]
    labels = [finding["label"] for finding in completed["findings"]]
    rows = {row[0]: dict(zip(labels, row)) for row in completed["findings"][0]["rows"]}
    assert rows["8DN"]["Arrives"] == "00:50, next day"
    assert rows["7UP"]["Arrives"] == "14:40"
