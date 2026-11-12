"""Finishing the task, on our own replicas (2026-10-16).

Until today every flow stopped before anything that books, pays or changes a
record. On a replica — a site we wrote, never a live one — the person can
now have it done: the train they pick booked, the bill they looked up paid
(a pretend payment, with no card details), the course registered. Each
change happens only after a final screen that says in plain words what will
happen, shows what, how much and when as the page states them, and offers
two answers, do it or don't, neither the default (CLAUDE.md, the final-step
rule). Everything the final screen shows is read from the page at that
moment (`plan.FinalRead`); nothing on it is SIMBA's own.

`loop.carry_out` enforces the rule whichever planner asks: a move that
changes something is acted on only on a replica, and only after its final
screen was answered "do it".
"""

from backend.orchestrator import voice
from backend.orchestrator.plan import (
    About,
    Answer,
    Confirmation,
    Expectation,
    FinalRead,
    Operation,
    Target,
)
from shared.schema import StepField

# --- the train the person picked -------------------------------------------

#: How the replica's results name each train's booking link.
BOOK_TRAIN = "Book train "


def booking_task(train: str | None = None):
    """Booking one seat: done only with the site's confirmation on the page,
    and its booking number, train, date and seat quoted from it. Which train
    is settled by the planner once the person has said (`settled`)."""
    from backend.orchestrator.loop import Task

    return Task(
        goal=f"Book a seat on {train}." if train else "Book a seat.",
        estimated_steps=4,
        success=Expectation(title_contains="Booking Confirmed"),
        about=About(finds=(
            Answer("Booking number", reads="Booking number"),
            Answer("Train", reads="Train"),
            Answer("Date", reads="Date", plain=voice.page_date),
            Answer("Seat", reads="Seat"),
        )),
        confirms=Confirmation(heading="Booking Confirmed", reads="Booking number",
                              caveat="No real ticket", who="site",
                              done=voice.BOOKED_PRACTICE, practice=voice.NO_REAL_TICKET),
        scope=voice.booked_scope(train) if train else None,
    )


class BookingPlanner:
    """Books a train the search found, on the railways replica.

    Asks which train — from the trains found, unless there is only one —
    then opens its booking form (a page to read: runs by itself), asks the
    two things the form needs — the passenger's name, and the class from the
    form's own choices — fills them in, and shows the final screen. Only
    "Book it" there presses "Confirm Booking".
    """

    calls_made = 0
    stuck_reason: str | None = None
    #: Marks its own change: only "Confirm Booking" books.
    marks_changes = True

    def __init__(self, trains: list[tuple[str, str]], stage: int) -> None:
        #: The trains found, each with when it leaves, as the results showed them.
        self.trains = trains
        self.train: str | None = trains[0][0] if len(trains) == 1 else None
        self.stage = stage
        self.name: str | None = None
        self.klass: str | None = None
        self.classes: list[str] = []
        self._done: set[str] = set()
        self._note: str | None = None

    def coming(self) -> list[str]:
        return []

    def _which(self, Move):
        """Which of the trains found, as buttons, or a list when there are many."""
        names = [train for train, _ in self.trains]
        if len(self.trains) <= voice.MAX_CHOICES:
            fields = []
            actions = voice.choices([voice.train_choice(t, leaves) for t, leaves in self.trains])
        else:
            fields = [StepField(id="train", label=voice.FIELD_TRAIN, type="choice", value="",
                                options=names)]
            actions = voice.actions(voice.USE_TRAIN)
        return Move(instruction=voice.ASK_WHICH_TRAIN, detail="", operations=[],
                    expect=Expectation(), fields=fields, actions=actions, question=True,
                    kind="choose", stage=self.stage)

    def settled(self, task):
        """The task, with the train the person chose in it."""
        from dataclasses import replace

        if self.train is None:
            return task
        return replace(task, scope=voice.booked_scope(self.train))

    async def next_move(self, elements, history, setback):
        from backend.orchestrator.loop import Move

        if self.train is None:
            return self._which(Move)
        if "open" not in self._done:
            self._done.add("open")
            return Move(instruction=voice.DOING_BOOKING_FORM + ".", detail="",
                        operations=[Operation("click", Target("link", BOOK_TRAIN + self.train))],
                        expect=Expectation(title_contains="Book a Seat"), fields=[],
                        actions=voice.actions(voice.OPEN_IT), safe=True,
                        doing=voice.DOING_BOOKING_FORM, stage=self.stage, kind="read")
        if not self.classes:
            self.classes = [e.label for e in elements if e.role == "radio" and e.label]
            if not self.classes:
                self.stuck_reason = voice.NO_CLASSES
                return None
        if self.name is None:
            note, self._note = self._note, None
            return Move(instruction=voice.ASK_PASSENGER, detail=voice.PASSENGER_DETAIL,
                        operations=[],
                        expect=Expectation(),
                        fields=[StepField(id="passenger", label=voice.FIELD_NAME, type="text",
                                          value="")],
                        actions=voice.actions(voice.USE_NAME), question=True, kind="type",
                        stage=self.stage, note=note)
        if self.klass is None:
            return Move(instruction=voice.ASK_CLASS, detail=voice.CLASS_DETAIL, operations=[],
                        expect=Expectation(), fields=[], actions=voice.choices(self.classes),
                        question=True, kind="choose", stage=self.stage)
        if "fill" not in self._done:
            self._done.add("fill")
            return Move(instruction=voice.doing_booking(self.klass) + ".", detail="",
                        operations=[
                            Operation("fill", Target("textbox", "Passenger Name"),
                                      value=self.name),
                            Operation("click", Target("radio", self.klass)),
                        ],
                        expect=Expectation(content_says=self.klass), fields=[],
                        actions=voice.actions(voice.FILL_IN), safe=True,
                        doing=voice.doing_booking(self.klass), stage=self.stage, kind="type")
        if "final" not in self._done:
            self._done.add("final")
            return Move(
                instruction=voice.final_book(self.train), detail=voice.FINAL_WAITS,
                operations=[Operation("click", Target("button", "Confirm Booking"))],
                expect=Expectation(title_contains="Booking Confirmed"), fields=[],
                actions=voice.final_actions(voice.BOOK_IT, voice.DONT_BOOK),
                final_answers=(voice.BOOK_IT, voice.DONT_BOOK),
                changes=True, stage=self.stage, kind="confirm",
                final=(
                    FinalRead("Train", "Train"),
                    FinalRead("From", "From", plain=voice.station_name),
                    FinalRead("To", "To", plain=voice.station_name),
                    FinalRead("Date", "Date", plain=voice.page_date),
                    FinalRead("Leaves", "Departs"),
                    FinalRead("Passenger", "Passenger"),
                    FinalRead("Class", "Class"),
                    FinalRead("Fare", "Fare"),
                ))
        return None

    def answered(self, action_id: str, input_values: dict[str, str]) -> None:
        if self.train is None:
            names = [train for train, _ in self.trains]
            index = action_id.removeprefix(voice.CHOICE_PREFIX)
            if index.isdigit() and int(index) < len(names):
                self.train = names[int(index)]
            elif input_values.get("train") in names:
                self.train = input_values["train"]
            return
        if self.name is None:
            name = " ".join((input_values.get("passenger") or "").split())
            if name and len(name) <= 60 and any(ch.isalpha() for ch in name):
                self.name = name
            else:
                self._note = voice.NAME_NOT_CAUGHT
            return
        index = action_id.removeprefix(voice.CHOICE_PREFIX)
        if index.isdigit() and int(index) < len(self.classes):
            self.klass = self.classes[int(index)]


# --- the bill the person looked up --------------------------------------------


def payment_task(reference: str):
    """Paying the bill for `reference`, a pretend payment with no card details:
    done only with the site's receipt on the page, its number quoted."""
    from backend.orchestrator.loop import Task

    return Task(
        goal=f"Pay the bill for reference number {reference}.",
        estimated_steps=2,
        success=Expectation(title_contains="Payment Received"),
        about=About(finds=(
            Answer("Receipt number", reads="Receipt number"),
            Answer("Amount paid", reads="Amount paid", plain=voice.rupees),
            Answer("Paid on", reads="Paid on", plain=voice.page_date),
        )),
        confirms=Confirmation(heading="Payment Received", reads="Receipt number",
                              caveat="No money was taken", who="site",
                              done=voice.PAID_PRACTICE, practice=voice.NO_REAL_MONEY),
        scope=voice.PAID_SCOPE,
    )


def card_gateway() -> bool:
    """Whether the bill is paid by card through the billing copy's test
    gateway (2026-11-13): `SIMBA_CARD_GATEWAY=1`. Off, it is the pretend
    payment with no card, as since 2026-10-16."""
    import os

    return os.environ.get("SIMBA_CARD_GATEWAY", "").strip() == "1"


class PaymentPlanner:
    """Pays the bill the person looked up, on the billing replica: opens its
    payment page (a page to read), then the final screen. Nothing to ask: the
    page needs no card and no choice. Only "Pay it" presses "Confirm Payment".
    """

    calls_made = 0
    stuck_reason: str | None = None
    #: Marks its own change: only "Confirm Payment" pays.
    marks_changes = True

    def __init__(self, stage: int) -> None:
        self.stage = stage
        self._done: set[str] = set()

    def coming(self) -> list[str]:
        return []

    async def next_move(self, elements, history, setback):
        from backend.orchestrator.loop import Move

        if "open" not in self._done:
            self._done.add("open")
            return Move(instruction=voice.DOING_PAYMENT_PAGE + ".", detail="",
                        operations=[Operation("click", Target("link", "Pay this bill"))],
                        expect=Expectation(title_contains="Pay Your Bill"), fields=[],
                        actions=voice.actions(voice.OPEN_PAYMENT), safe=True,
                        doing=voice.DOING_PAYMENT_PAGE, stage=self.stage, kind="read")
        if "final" not in self._done and card_gateway():
            # By card, through the test gateway (2026-11-13): the final screen
            # opens the card page; the loop hands that page to the person, who
            # pays there, and reads the receipt once they have.
            self._done.add("final")
            return Move(
                instruction=voice.FINAL_PAY_CARD, detail=voice.FINAL_WAITS,
                operations=[Operation("click", Target("button", "Pay by card (test gateway)"))],
                expect=Expectation(title_contains="Card payment"), fields=[],
                actions=voice.final_actions(voice.PAY_BY_CARD, voice.DONT_PAY),
                final_answers=(voice.PAY_BY_CARD, voice.DONT_PAY),
                changes=True, stage=self.stage, kind="confirm",
                final=(
                    FinalRead("Amount", "Amount payable", plain=voice.rupees),
                    FinalRead("Bill", "Billing month"),
                    FinalRead("Due", "Due date", plain=voice.page_date),
                    FinalRead("Reference number", "Reference No."),
                ))
        if "final" not in self._done:
            self._done.add("final")
            return Move(
                instruction=voice.FINAL_PAY, detail=voice.FINAL_WAITS,
                operations=[Operation("click", Target("button", "Confirm Payment"))],
                expect=Expectation(title_contains="Payment Received"), fields=[],
                actions=voice.final_actions(voice.PAY_IT, voice.DONT_PAY),
                final_answers=(voice.PAY_IT, voice.DONT_PAY),
                changes=True, stage=self.stage, kind="confirm",
                final=(
                    FinalRead("Amount", "Amount payable", plain=voice.rupees),
                    FinalRead("Bill", "Billing month"),
                    FinalRead("Due", "Due date", plain=voice.page_date),
                    FinalRead("Reference number", "Reference No."),
                ))
        return None

    def answered(self, action_id: str, input_values: dict[str, str]) -> None:
        pass
