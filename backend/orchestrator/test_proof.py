"""The answer, shown on the real page (2026-10-16).

Before a task closes the page is read again and compared with what is about
to be shown; then a still of it is taken with every row or value read
ringed. If the page now says something else, no answer is shown. If no
picture can be had, the closing screen says why. Never an empty or stale
picture.
"""

import asyncio
from datetime import date, timedelta
from types import SimpleNamespace

from playwright.async_api import Error as PlaywrightError

from backend.orchestrator import voice
from backend.orchestrator.billing_plan import BILLING_PLAN, BILLING_TASK
from backend.orchestrator.details import BillBrief, CourseBrief, TripBrief, Understood
from backend.orchestrator.loop import Task, answer_changed, take_proof
from backend.orchestrator.plan import About, Answer, HardcodedPlanner
from backend.orchestrator.test_billing import billing_replica, drive  # noqa: F401
from backend.orchestrator.test_checklist import go
from backend.orchestrator.test_course_from_list import go as go_signed_in
from backend.orchestrator.test_orchestrator import replica  # noqa: F401
from backend.orchestrator.test_trip_answers import railways  # noqa: F401

TOMORROW = date.today() + timedelta(days=1)


def ending(done) -> dict:
    return done.of("task.completed")[0]


def inside(ring: dict) -> bool:
    return (ring["x"] >= 0 and ring["y"] >= 0 and ring["w"] > 0 and ring["h"] > 0
            and ring["x"] < 1280 and ring["y"] < 800)


def test_the_trains_are_ringed_row_by_row(railways: str) -> None:  # noqa: F811
    brief = TripBrief("t", Understood(origin="Lahore Cantt", destination="Karachi Cantt",
                                      day=TOMORROW))

    end = ending(go(railways, brief, [("choice:0", {})]))  # yes to the read-back

    rows = end["findings"][0]["rows"]
    proof = end["proof"]
    assert proof["caption"] == voice.PROOF_CAPTION and end["proof_note"] is None
    assert len(proof["rings"]) == len(rows) == 2
    assert all(inside(ring) for ring in proof["rings"])
    # One ring per row: one above the other, each the row's width.
    first, second = proof["rings"]
    assert second["y"] >= first["y"] + first["h"] - 1
    assert first["w"] > 600


def test_the_bill_rings_the_amount_and_the_due_date(billing_replica: str) -> None:  # noqa: F811
    """One result: its values, not the whole line of the table."""
    brief = BillBrief("b", Understood(reference="04141234567890"))

    end = ending(go(billing_replica, brief, []))

    # Shown in plain words, found on the page by its own.
    assert [f["values"] for f in end["findings"]] == [["Rs 14,382"], ["15 September 2026"]]
    rings = end["proof"]["rings"]
    assert len(rings) == 2 and all(inside(r) and r["w"] < 300 for r in rings)


def test_a_registration_rings_the_portals_confirmation(replica: str) -> None:  # noqa: F811
    brief = CourseBrief("c", Understood(course="MATH-210"))

    end = ending(go_signed_in(replica, brief, []))

    # The number is said under the heading since 2026-10-17, as a booking's
    # is; the portal's words are quoted without it.
    assert end["caveat"].startswith("Confirmation number REG-10301-2026.")
    assert end["confirmation"] == "The portal says “Registration Confirmed”."
    # The heading, the number's row, and the caveat's paragraph.
    assert len(end["proof"]["rings"]) == 3


def test_what_was_read_on_a_page_since_left_has_no_picture(
    billing_replica: str,  # noqa: F811
) -> None:
    """The fixed plan the benchmarks were measured on still opens the full
    bill, where neither value is shown: said, and no picture instead."""
    end = drive(HardcodedPlanner(BILLING_PLAN), BILLING_TASK, billing_replica)\
        .payload_of("task.completed")

    assert end["proof"] is None
    assert end["proof_note"] == voice.NOT_ON_THIS_PAGE


def test_a_page_that_now_says_something_else_is_a_change() -> None:
    task = Task(goal="g", estimated_steps=1,
                about=About(finds=(Answer("Your bill", reads="P/WITHIN"),)))

    def page(*values):
        return SimpleNamespace(content=SimpleNamespace(values_for=lambda label: list(values)))

    assert answer_changed({"Your bill": ["14,382"]}, page("14,957"), task)
    assert not answer_changed({"Your bill": ["14,382"]}, page("14,382"), task)
    # Read on a page since left: not a difference, and said another way.
    assert not answer_changed({"Your bill": ["14,382"]}, page(), task)
    # Read only now: nothing to compare.
    assert not answer_changed({}, page("14,382"), task)


def test_a_picture_that_cannot_be_taken_is_said_and_not_sent() -> None:
    class Broken:
        async def evaluate(self, *args):
            raise PlaywrightError("Target page, context or browser has been closed")

    proof, note = asyncio.run(take_proof(Broken(), [("14,382", False)]))

    assert proof is None and note == voice.NO_PROOF_PICTURE
