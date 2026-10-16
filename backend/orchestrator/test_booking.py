"""Booking the train the person picked, on our railways replica (2026-10-16).

After the trains are found, on a replica only: "Would you like to book one
of these trains?" — the trains, and "No, just the times". A train picked
opens its booking form, SIMBA asks only what the form needs (a name, and a
class from the form's own choices), fills it in, and shows the final screen
with every detail read from the page. "Book it" books; the closing screen
quotes the site's confirmation and its booking number, train, date and seat,
with the proof. Real loop, real Chromium, the real replica.
"""

from datetime import date, timedelta

from backend.orchestrator import voice
from backend.orchestrator.details import TripBrief, Understood
from backend.orchestrator.test_checklist import Answers, go
from backend.orchestrator.test_trip_answers import railways  # noqa: F401

TOMORROW = date.today() + timedelta(days=1)
NAME = "Ayesha Khan"


def journey() -> TripBrief:
    return TripBrief("trains to Karachi tomorrow",
                     Understood(origin="Lahore Cantt", destination="Karachi Cantt", day=TOMORROW))


#: Yes to the read-back; the first train; a name; the second class.
BOOK_FIRST = [("choice:0", {}), ("choice:0", {}), ("confirm", {"passenger": NAME}),
              ("choice:1", {})]


def shown(done, instruction: str) -> dict:
    return next(p for p in done.of("step.presented") if p["instruction"] == instruction)


def test_once_the_trains_are_found_it_offers_to_book_one(railways: str) -> None:  # noqa: F811
    done = go(railways, journey(), [("choice:0", {})])

    offer = shown(done, voice.ASK_BOOK)
    labels = [a["label"] for a in offer["actions"]]
    assert labels == ["7UP, leaves 07:25", "8DN, leaves 16:35", voice.JUST_TIMES, voice.STOP]
    # The task's stages say there is a booking to come.
    assert done.of("task.started")[0]["stages"][-1] == voice.BOOK_STAGE
    # Unanswered here, so "No, just the times": the trains, as before.
    assert done.of("task.completed")[0]["findings"][0]["values"] == ["7UP", "8DN"]


def test_a_picked_train_is_booked_after_its_final_screen(railways: str) -> None:  # noqa: F811
    done = go(railways, journey(), BOOK_FIRST)

    # Only what the form needs was asked, the class from its own choices.
    classes = shown(done, voice.ASK_CLASS)
    assert [a["label"] for a in classes["actions"]] == [
        "Economy", "AC Standard", "AC Business", voice.STOP]
    assert shown(done, voice.ASK_PASSENGER)["fields"][0]["id"] == "passenger"
    # Opening the form and filling it in ran by themselves.
    assert done.rows()[-2:] == [voice.DOING_BOOKING_FORM, voice.doing_booking("AC Standard")]

    final = shown(done, voice.final_book("7UP"))
    assert final["final"] == [
        {"label": "Train", "value": "7UP"},
        {"label": "From", "value": "Lahore Cantt"},
        {"label": "To", "value": "Karachi Cantt"},
        {"label": "Date", "value": voice.page_date(TOMORROW.strftime("%d-%m-%Y"))},
        {"label": "Leaves", "value": "07:25"},
        {"label": "Passenger", "value": NAME},
        {"label": "Class", "value": "AC Standard"},
        {"label": "Fare", "value": "Rs 3,250"},
    ]
    assert [(a["id"], a["label"]) for a in final["actions"]] == [
        ("confirm", voice.BOOK_IT), (voice.DECLINE_ID, voice.DONT_BOOK)]

    end = done.of("task.completed")[0]
    found = {f["label"]: f["values"][0] for f in end["findings"]}
    assert found["Booking number"].startswith("PR-") and len(found["Booking number"]) == 9
    assert found["Train"] == "7UP"
    assert found["Date"] == voice.page_date(TOMORROW.strftime("%d-%m-%Y"))
    assert found["Seat"].startswith("Coach 3, seat ")
    assert end["confirmation"] == (f"The site says “Booking Confirmed”, with booking "
                                   f"number {found['Booking number']}.")
    assert end["caveat"] == ("The site also says “No real ticket was booked and no money "
                             "was taken”.")
    assert end["scope"] == voice.booked_scope("7UP")
    assert end["proof"] and len(end["proof"]["rings"]) >= 3


def test_dont_book_it_books_nothing(railways: str) -> None:  # noqa: F811
    class SaysDont(Answers):
        async def receive(self, message_type, step_index=None, on_other=None):
            step = self.of("step.presented")[-1]
            if step.get("final"):
                self.shown += 1
                return {"type": "step.response", "payload": {
                    "step_index": step_index, "action_id": voice.DECLINE_ID,
                    "input_values": {}}}
            return await super().receive(message_type, step_index, on_other)

    import backend.orchestrator.test_checklist as checklist

    original, checklist.Answers = checklist.Answers, SaysDont
    try:
        done = go(railways, journey(), list(BOOK_FIRST))
    finally:
        checklist.Answers = original

    assert done.of("task.failed")[0]["reason"] == voice.NOTHING_CHANGED
    assert "task.completed" not in done.types()


def test_a_name_that_is_not_a_name_is_asked_again(railways: str) -> None:  # noqa: F811
    answers = [*BOOK_FIRST[:2], ("confirm", {"passenger": "  "}), ("confirm", {"passenger": NAME}),
               ("choice:0", {})]
    done = go(railways, journey(), answers)

    asked = [p for p in done.of("step.presented") if p["instruction"] == voice.ASK_PASSENGER]
    assert len(asked) == 2 and asked[1]["note"] == voice.NAME_NOT_CAUGHT
    assert "task.completed" in done.types()


def test_a_booking_the_site_does_not_confirm_is_not_done(
    railways: str, monkeypatch,  # noqa: F811
) -> None:
    """The press lands and the page moves on, but its confirmation is not
    the one the task waits for: never "done", and said plainly (2026-10-16)."""
    from dataclasses import replace

    import backend.orchestrator.finish_plan as finish_plan

    real = finish_plan.booking_task

    def unconfirmed(train: str):
        task = real(train)
        return replace(task, confirms=replace(task.confirms, heading="Ticket Issued"))

    monkeypatch.setattr(finish_plan, "booking_task", unconfirmed)
    done = go(railways, journey(), list(BOOK_FIRST))

    assert "task.completed" not in done.types()
    help = done.of("help.requested")[0]
    assert help["unconfirmed"] is True
    assert help["reason"] == voice.not_confirmed("Confirm Booking", "site")


def test_nothing_is_shown_as_found_on_the_way_to_a_booking(railways: str) -> None:  # noqa: F811
    """The booking's steps carry no findings: what it reads is its receipt,
    shown at the end. "Here's what I found: 7UP" on the name question ran it
    past a 1280x800 window in the real window (2026-10-16)."""
    done = go(railways, journey(), list(BOOK_FIRST))

    for instruction in (voice.ASK_PASSENGER, voice.ASK_CLASS, voice.final_book("7UP")):
        assert shown(done, instruction)["findings"] == [], instruction
    # The offer itself still shows the trains it is about.
    assert shown(done, voice.ASK_BOOK)["findings"][0]["values"] == ["7UP", "8DN"]
