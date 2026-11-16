"""On a site that is not ours, SIMBA reads and never books or pays
(2026-10-16), and it never types card or bank details anywhere.

The live train site cannot be searched over and over (CLAUDE.md), so "a site
that is not ours" is our own replica with the replica hosts emptied: exactly
the code path a live page takes, on a page that behaves the same every run.
"""

from datetime import date, timedelta
from urllib.parse import quote

import pytest

from backend.orchestrator import loop, voice
from backend.orchestrator.details import BillBrief, TripBrief, Understood
from backend.orchestrator.plan import Expectation, Operation, PlanStep, Target
from backend.orchestrator.test_checklist import go
from backend.orchestrator.test_final_step import drive
from backend.orchestrator.test_trip_answers import railways  # noqa: F401

TOMORROW = date.today() + timedelta(days=1)


def journey() -> TripBrief:
    return TripBrief("trains to Karachi tomorrow",
                     Understood(origin="Lahore Cantt", destination="Karachi Cantt", day=TOMORROW))


def test_on_a_real_site_it_reads_says_so_and_offers_nothing(
    railways: str, monkeypatch: pytest.MonkeyPatch,  # noqa: F811
) -> None:
    monkeypatch.setattr(loop, "REPLICA_HOSTS", ())

    done = go(railways, journey(), [("choice:0", {})])  # yes to the read-back

    assert done.of("task.completed")[0]["offer"] is None
    assert voice.BOOK_STAGE not in done.of("task.started")[0]["stages"]
    end = done.of("task.completed")[0]
    assert end["scope"] == "I only looked up times. I did not book a ticket or pay for anything."
    # One way to see the real page, at the right place: the trains ringed.
    assert end["proof"] and len(end["proof"]["rings"]) == 2


def test_a_bill_on_a_site_that_is_not_ours_says_the_same() -> None:
    brief = BillBrief("b", Understood(reference="04141234567890"))
    assert brief.task().scope == voice.NOT_ON_REAL_SITE_BILL
    brief.finishes = True
    assert brief.task().scope == voice.ONLY_LOOKED_AT_BILL


def page(box: str) -> str:
    return "data:text/html," + quote(
        f"<title>Checkout</title>{box}<button onclick='window.__clicked=1'>Next</button>")


def fill(label: str) -> PlanStep:
    return PlanStep(instruction="Let me fill this in.", detail="", actions=voice.actions("Go"),
                    operations=[Operation("fill", Target("textbox", label), value="4111111111111111")],
                    expect=Expectation())


@pytest.mark.parametrize("box, label", [
    ("<label>Card number <input name=n></label>", "Card number"),
    ("<label>CVV <input name=v></label>", "CVV"),
    ("<label>Number <input autocomplete=cc-number></label>", "Number"),
    ("<label>IBAN <input></label>", "IBAN"),
], ids=["card", "cvv", "autocomplete", "iban"])
def test_card_and_bank_details_are_never_typed(box: str, label: str) -> None:
    """Never typed, on any site. Since 2026-11-13 the page is handed to the
    person to type them there (`test_handover.py`) rather than the run ending;
    here the script's person does nothing, so the page cannot say it was paid."""
    from backend.orchestrator.test_handover import drive as drive_handing

    done, _ = drive_handing(page(box), [fill(label)])

    assert done.of("handover")[0]["reason"] == "payment"
    assert done.of("step.presented") == []  # not even asked
    assert "4111111111111111" not in repr(done.sent)
    assert done.of("help.requested")[0]["reason"] == voice.PAYMENT_NOT_SEEN


def test_an_ordinary_box_is_still_typed_into() -> None:
    done, _ = drive(page("<label>Reference No. <input></label>"), [fill("Reference No.")])

    assert "help.requested" not in done.types()
