"""A remembered goal in a few words (2026-10-16).

The home screen gives a remembered goal one line, which shows about twenty
characters: two bills both read "Find the amount due for…". The backend now
says what each is, from the sentence it remembered.
"""

from datetime import date

import pytest

from backend.orchestrator import app, voice
from backend.orchestrator.details import BillBrief, CourseBrief, TripBrief, Understood
from backend.orchestrator.traces import TraceStep, TraceStore


@pytest.mark.parametrize("goal, label", [
    ("Find trains from Lahore Cantt to Rawalpindi on 2026-10-01.",
     "Trains Lahore Cantt to Rawalpindi"),
    ("Find trains from LAHORE CANTT to KARACHI CANTT on 2026-10-15.",
     "Trains Lahore Cantt to Karachi Cantt"),
    ("Find the amount due for reference number 04141234567890.", "Bill ending 7890"),
    ("Register for the course CS-401.", "Course CS-401"),
    # Anything else has no label, and is shown in its own words.
    ("Pay my water bill", None),
    ("Find trains somewhere", None),
])
def test_short_label(goal: str, label: str | None) -> None:
    assert voice.short_label(goal) == label


def test_every_sentence_a_brief_remembers_has_a_label() -> None:
    """What is remembered is each brief's own sentence (`replay.finished`)."""
    trip = TripBrief("trains", Understood(origin="Lahore Cantt", destination="Karachi Cantt",
                                          day=date(2026, 10, 15)), today=date(2026, 10, 14))
    bill = BillBrief("bill", Understood(reference="04141234567890"))
    course = CourseBrief("course", Understood(course="CS-401"))
    assert [voice.short_label(b.sentence()) for b in (trip, bill, course)] == [
        "Trains Lahore Cantt to Karachi Cantt", "Bill ending 7890", "Course CS-401"]


def test_the_home_screen_is_offered_the_labels(tmp_path, monkeypatch) -> None:
    store = TraceStore(tmp_path / "traces.db")
    step = [TraceStep(kind="click", role="button", label="Search", value=None)]
    store.save("Find the amount due for reference number 04149999999999.", "s", step)
    store.save("Pay my water bill", "s", step)
    monkeypatch.setenv("SIMBA_TRACE_DB", str(tmp_path / "traces.db"))

    offered = app.past_goals()

    assert {g.goal: g.label for g in offered.goals} == {
        "Find the amount due for reference number 04149999999999.": "Bill ending 9999",
        "Pay my water bill": None,
    }
