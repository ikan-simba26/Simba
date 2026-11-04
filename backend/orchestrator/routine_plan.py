"""Running a routine a helper showed SIMBA (2026-11-04, "Show me once").

`RoutineBrief` asks the person only what the helper said changes, one
question at a time, before the site is touched (the question flow every brief
uses, `loop.run_brief`). `RoutinePlanner` then gives the loop the helper's
moves one at a time, each found again by role, label and which of several
alike on the page as it is now (`find`), never by an id kept from before:
ids are per reading (DECISIONS.md, *Traces keyed on role and label*).

Everything after that is the loop's, the same as for every planner: the
checklist for moves that are safe, the cookie question, the final screen for
a change and only on our replicas, never a card's details, every move
checked, the answer read and shown with the picture of the real page.

**When the site has changed.** A move that cannot be found, or that does not
do what it did when it was shown, stops the run and says so plainly: the
helper may need to show it again. It is not tried a different way by guessing.
Only when a model is set up does the person get one more choice — "Shall I
try to work out the rest?" — and only a yes hands the rest to it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import date, timedelta

from backend.orchestrator import voice
from backend.orchestrator.loop import Move, Planner, Task
from backend.orchestrator.plan import About, Expectation, Operation, Target
from backend.orchestrator.plan import Answer as Finds
from backend.orchestrator.routines import Routine, Step, asks_consent
from backend.perception.content import Content
from backend.perception.serializer import Element
from shared.schema import StepField

#: How many unusable answers to one question before the run gives up, as for
#: every other question (`details.MAX_TRIES`).
MAX_TRIES = 3

#: Builds the planner that takes over when the person agrees: the task in
#: hand, and a planner back. None when no model is set up.
Fallback = Callable[[Task], Planner]


def calendar_days(elements: list[Element]) -> list[Element]:
    """The day cells of a calendar that is open: numbers in a panel that
    says which month it shows."""
    from backend.orchestrator.teach import is_day

    return [e for e in elements if is_day(e)]


def find(elements: list[Element], step: Step) -> Element | None:
    """The element a move was made on, on the page as it is now: same role,
    same label, the same qualifier when one was kept, and the same one of
    several alike. None when the page has no such element."""
    if step.day and step.ask:
        # The person's day: any day of an open calendar will do to start from.
        days = calendar_days(elements)
        return days[0] if days else None
    if step.row:
        # Any row's press will do to start from: which is the person's.
        return next((e for e in elements if e.role == step.role
                     and in_row(step, e.label) is not None), None)
    alike = [e for e in elements if e.role == step.role and e.label == step.label
             and (step.qualifier is None or e.qualifier == step.qualifier)]
    return alike[step.nth] if step.nth < len(alike) else None


def in_row(step: Step, label: str) -> str | None:
    """The row's name in a row press's label, or None when the label is not
    one of the column: "Book train 13UP" is 13UP's, for "Book train {}"."""
    before, _, after = step.label.partition("{}")
    if len(label) <= len(before) + len(after) or not (
            label.startswith(before) and label.endswith(after)):
        return None
    return label[len(before):len(label) - len(after)] or None


#: The most cells of a row said on its button, after its name: the ones that
#: tell the rows apart (the time it leaves, how long it takes).
ROW_CELLS = 2


def rows_of(content: Content, elements: list[Element],
            step: Step) -> list[tuple[str, str]]:
    """The rows the person can choose from, as the page shows them now: each
    row's name, and how it is said as an answer — its name, then the cells
    that differ from row to row ("13UP, 13:05 16:20, 3 h 15 min"). Only rows
    whose own press is on the page, in the page's order."""
    presses = {e.label for e in elements if e.role == step.role}
    for table in content.tables:
        if step.row not in table.headers:
            continue
        rows = []
        for row in table.rows:
            name = row.get(step.row)
            if name and step.label.replace("{}", name, 1) in presses \
                    and name not in (r.get(step.row) for r in rows):
                rows.append(row)
        if not rows:
            continue
        differ = [header for header in table.headers if header != step.row
                  and len({row.get(header) or "" for row in rows}) > 1][:ROW_CELLS]
        return [(row.get(step.row) or "",
                 ", ".join([row.get(step.row) or "",
                            *(row.get(h) or "" for h in differ if row.get(h))]))
                for row in rows]
    return []


def as_written(day: date) -> tuple[str, ...]:
    """A day as a date box may write it: the first is said if it does not."""
    month = day.strftime("%B")
    return (f"{day:%d-%m-%Y}", f"{day:%Y-%m-%d}", f"{day:%d/%m/%Y}", f"{day:%m/%d/%Y}",
            f"{day:%d.%m.%Y}", f"{day.day} {month}", f"{month} {day.day}",
            f"{day.day} {month[:3]}", f"{month[:3]} {day.day}")


def months_apart(shown: tuple[int, int], wanted: date) -> int:
    return (wanted.year - shown[0]) * 12 + wanted.month - shown[1]


def routine_task(routine: Routine) -> Task:
    """What running a routine has to end with: the answer the helper pointed
    at, on the page, read and shown under the name they gave it."""
    return Task(
        goal=routine.label,
        estimated_steps=len(routine.steps),
        success=Expectation(has_value=routine.answer.reads),
        about=About(finds=(Finds(routine.answer.name or routine.answer.reads,
                                 reads=routine.answer.reads),)),
        heading=routine.label,
        # A change is only ever made on our copies (`loop.carry_out`), so a
        # routine that makes one says it was the practice site (stage 2).
        scope=voice.ROUTINE_PRACTICE_SCOPE if routine.changes else voice.ROUTINE_SCOPE,
    )


def routine_sentence(routine: Routine) -> str:
    """The goal a model is given if the person lets it try the rest: what the
    routine is for, by the page's own label. Never shown to the person."""
    return (f"{routine.label}: get to the page that shows {routine.answer.reads!r} and stop "
            f"there.")


def _safe(step: Step) -> bool:
    """Runs without a press, as a checklist line: filling in what the person
    has already said or the helper fixed, and pressing what only looks
    something up. Never a change, never consent, never a password."""
    if step.changes or step.secret:
        return False
    return not asks_consent(step)


def _doing(step: Step) -> str:
    where = step.label or step.role
    if step.day:
        return voice.DOING_CHOOSE_DAY
    if step.pick:
        return voice.DOING_PICK
    if step.kind == "fill":
        return voice.doing_type(where)
    if step.kind == "select":
        return voice.doing_choose(where)
    if step.kind == "press":
        return voice.doing_key(step.value or "Enter", where)
    if step.role == "link":
        return voice.doing_open(where)
    return voice.doing_press(where)


class RoutinePlanner:
    """The helper's moves, one at a time, found again on the page as it is."""

    #: The loop also stops on a press whose words say it books, pays or
    #: changes something, whatever was kept (`loop.would_change`): a routine
    #: read from someone else's file is data, not a promise.
    marks_changes = False
    #: Every move the helper showed is done before the answer is looked for:
    #: a page that already shows the label is not the answer to this run.
    must_finish = True

    def __init__(self, routine: Routine, answers: dict[int, str],
                 fallback: Fallback | None = None, task: Task | None = None) -> None:
        self.routine = routine
        self.answers = dict(answers)
        self._index = 0
        self._fallback = fallback
        self._task = task or routine_task(routine)
        self._model: Planner | None = None
        self._offered = False
        self._stop: str | None = None
        self._stuck: str | None = None
        #: Said when every move is done and the answer is not on the page.
        self.ran_out = voice.ROUTINE_NO_ANSWER
        self.replayed_steps = 0
        #: The page's readable content, as the loop last read it (`look`).
        self._content = Content()
        #: The row the person chose, by the step it is for (2026-11-04, fix).
        self._rows: dict[int, str] = {}
        #: The rows offered, while "Which train?" waits for its answer.
        self._offering: list[tuple[str, str]] = []

    def look(self, content: Content) -> None:
        """What the page says, read by the loop before each move: the rows a
        press in a row is chosen from."""
        self._content = content

    @property
    def calls_made(self) -> int:
        return getattr(self._model, "calls_made", 0)

    @property
    def stuck_reason(self) -> str | None:
        """Why the run stopped: the honest stop, or, once the person let a
        model try the rest, the model's own reason."""
        if self._model is not None:
            return getattr(self._model, "stuck_reason", None)
        return self._stuck

    def coming(self) -> list[str]:
        """The checklist lines after the move just given, up to the first
        that will ask."""
        lines: list[str] = []
        for step in self.routine.steps[self._index:]:
            if not _safe(step) or step.row:
                break
            lines.append(_doing(step))
        return lines

    async def next_move(self, elements: list[Element], history: list[str],
                        setback: str | None) -> Move | None:
        if self._model is not None:
            return await self._model.next_move(elements, history, setback)
        if self._stop is not None:
            self._stuck = self._stop
            return None
        if setback is not None and self._index > 0:
            coming = (self.routine.steps[self._index]
                      if self._index < len(self.routine.steps) else None)
            if coming is not None and coming.row and find(elements, coming) is None:
                # The search was sent and found nothing to choose from: no
                # trains that day, which is not the site having changed.
                self._stop = voice.no_rows(coming.row)
                self._stuck = self._stop
                return None
            if self._index == len(self.routine.steps):
                # The last move, which waits for the answer: done, and the
                # answer is not there (stage 2).
                return self._stopped(voice.ROUTINE_NO_ANSWER)
            # It was found, and it did not do what it did when it was shown.
            done = self.routine.steps[self._index - 1]
            return self._stopped(voice.routine_did_not_work(done.label or done.role))
        if self._index >= len(self.routine.steps):
            return None
        step = self.routine.steps[self._index]
        if step.pick:
            chosen = self._chosen(self._index)
            if self._option(elements, chosen) is None:
                # The person's answer is not in the list the page opened.
                self._stop = voice.not_in_list(chosen)
                self._stuck = self._stop
                return None
        elif step.row and self._index not in self._rows:
            rows = rows_of(self._content, elements, step)
            if not rows:
                if find(elements, step) is None and not self._content.values_for(step.row):
                    # Nothing found to choose from: no trains on that day.
                    self._stop = voice.no_rows(step.row)
                    self._stuck = self._stop
                    return None
                return self._stopped(voice.routine_changed(voice.pressed_in_row(step)))
            if len(rows) > 1:
                return self._which(step, rows)
            self._rows[self._index] = rows[0][0]
        elif find(elements, step) is None:
            where = "the calendar" if step.day else (step.label or f"the {step.role}")
            return self._stopped(voice.routine_changed(where))
        move = self.move_for(self._index, elements)
        if move is None:
            return None
        self._index += 1
        self.replayed_steps += 1
        return move

    def _stopped(self, reason: str) -> Move | None:
        """The honest stop. With a model set up, the person is asked once
        whether it may try the rest; otherwise, or after a no, it stops."""
        self._stop = reason
        if self._fallback is None or self._offered:
            self._stuck = reason
            return None
        self._offered = True
        return Move(instruction=voice.ROUTINE_TRY, detail=reason, operations=[],
                    expect=Expectation(), fields=[],
                    actions=voice.try_or_not(),
                    question=True, kind="confirm")

    def _which(self, step: Step, rows: list[tuple[str, str]]) -> Move:
        """"Which train?", from the page's own rows, as the built-in booking
        asks (`finish_plan.BookingPlanner`): buttons, or a list when there
        are many."""
        from backend.orchestrator.details import _picked

        self._offering = rows
        said = [label for _, label in rows]
        if len(rows) <= voice.MAX_CHOICES:
            return replace(_picked(voice.which_row(step.row or ""), said, kind="choose"),
                           detail=voice.ROWS_DETAIL)
        return Move(instruction=voice.which_row(step.row or ""), detail=voice.ROWS_DETAIL,
                    operations=[], expect=Expectation(),
                    fields=[StepField(id="row", label=voice.row_noun(step.row or "").capitalize(),
                                      type="choice", value="", options=said)],
                    actions=voice.actions(voice.USE_ROW), question=True, kind="choose")

    def answered(self, action_id: str, input_values: dict[str, str]) -> None:
        """The person's answer to "Which train?", or to "Shall I try to work
        out the rest?"."""
        if self._offering:
            from backend.orchestrator.details import choice_index

            offered, self._offering = self._offering, []
            picked = choice_index(action_id)
            said = [label for _, label in offered]
            if picked is None and input_values.get("row") in said:
                picked = said.index(input_values["row"])
            if picked is not None and picked < len(offered):
                self._rows[self._index] = offered[picked][0]
            return  # not caught: asked again, from the page as it is then
        if action_id == voice.CONFIRM_ID and self._fallback is not None:
            self._model = self._fallback(self._task)
            self._stop = None

    def _chosen(self, index: int) -> str:
        """What a list choice is to choose: the answer to the box before it,
        or what the helper typed there when it is the same every time."""
        box = self.routine.steps[index - 1]
        return self.answers.get(index - 1) or box.value or ""

    @staticmethod
    def _option(elements: list[Element], chosen: str) -> Element | None:
        """The option the answer names: the one whose words are the answer,
        else the first that holds them."""
        options = [e for e in elements if e.role == "option" and e.qualifier != "disabled"]
        want = chosen.casefold().strip()
        return (next((e for e in options if e.label.casefold() == want), None)
                or next((e for e in options if want and want in e.label.casefold()), None))

    def _day_move(self, index: int, elements: list[Element]) -> Move | None:
        """The person's day on the calendar: moved on to its month with the
        press the helper used, then the day itself — the one in the month
        shown, never a greyed day either side (as `railways_plan.TripPlanner`)."""
        from backend.orchestrator.teach import shown_month

        step = self.routine.steps[index]
        wanted = date.fromisoformat(self.answers[index])
        cells = calendar_days(elements)
        shown = shown_month(cells[0].panel) if cells else None
        apart = months_apart(shown, wanted) if shown else -1
        if apart < 0 or (apart > 0 and not step.nav):
            self._stuck = voice.WRONG_MONTH
            return None
        qualifier = "today" if wanted == date.today() else ""
        operations = [Operation("click", Target("button", step.nav or "")) for _ in range(apart)]
        operations.append(Operation("click", Target("option", str(wanted.day),
                                                    qualifier=qualifier)))
        # The box the calendar was opened from has to hold the person's day:
        # the page took the day, not merely closed its calendar.
        opened = self.routine.steps[index - 1] if index else None
        expect = Expectation()
        if opened is not None and opened.kind == "click" and opened.role in (
                "textbox", "combobox") and opened.label:
            expect = Expectation(field_has=((opened.label, as_written(wanted)),))
        return Move(instruction=voice.routine_do(step), detail="", operations=operations,
                    expect=self._last(index, expect), fields=[],
                    actions=voice.actions(voice.GO_AHEAD), safe=True, doing=_doing(step),
                    kind="date")

    def _last(self, index: int, expect: Expectation) -> Expectation:
        """The last move waits for the answer to be on the page (stage 2): a
        search that fills a table in place has nothing else to wait for, and
        the end check reads the page once."""
        if index == len(self.routine.steps) - 1:
            return replace(expect, has_value=self.routine.answer.reads)
        return expect

    def move_for(self, index: int, elements: list[Element] | None = None) -> Move | None:
        """One kept move as the loop runs it."""
        step = self.routine.steps[index]
        if step.day and step.ask:
            return self._day_move(index, elements or [])
        if step.row:
            # The person's row: its own press, named as the page names it.
            step = replace(step, label=step.label.replace("{}", self._rows.get(index, ""), 1),
                           row=None)
        element = find(elements, step) if elements is not None and not step.pick else None
        label = step.label
        if step.pick:
            chosen = self._option(elements or [], self._chosen(index))
            label = chosen.label if chosen is not None else self._chosen(index)
        target = Target(role=step.role, label=label, qualifier=step.qualifier)
        # The person's choice is what the box holds once it is made.
        holds: tuple[tuple[str, tuple[str, ...]], ...] = ()
        if step.pick and index and self.routine.steps[index - 1].label:
            holds = ((self.routine.steps[index - 1].label, (label,)),)
        # The first of several alike is what matching by role and label finds
        # anyway; any other is named by the id it has on this reading.
        element_id = element.id if element is not None and step.nth > 0 else None
        expect = self._last(index, Expectation(
            url_contains=step.expect_url, label_present=step.expect_label,
            list_opens=step.list_opens, field_has=holds))
        # A box whose list choice comes next is typed with what will be
        # chosen, so the list shows it (stage 2).
        following = (self.routine.steps[index + 1]
                     if index + 1 < len(self.routine.steps) else None)
        if following is not None and following.pick and step.kind == "fill":
            expect = replace(expect, label_present=None, label_like=self._chosen(index + 1),
                             list_opens=True)
        # Before a choice of row: the rows are on the page, named in their
        # column (a search that fills a table in place changes nothing else).
        if following is not None and following.row and not (
                expect.url_contains or expect.label_present or expect.has_value):
            expect = replace(expect, has_value=following.row)
        fields: list[StepField] = []
        value = step.value
        key = None
        if step.kind in ("fill", "select") and step.ask:
            value = self.answers.get(index, "")
        if step.secret:
            # The saved one, or the person types it: never anything kept.
            key = (element.name if element is not None and element.name else "password")
            fields = [StepField(id=key, label=step.label or "Password", type="password",
                                value="")]
            value = None
        operation = Operation(kind=step.kind, target=target, value=value, value_key=key,
                              element_id=element_id)
        operations = [operation]
        if step.click_first:
            # Read-only until clicked: the click first, as the train search's
            # station boxes need (`railways_plan.TripPlanner`).
            operations = [Operation("click", target, element_id=element_id), operation]
        if asks_consent(step):
            return Move(instruction=voice.ASK_COOKIES, detail="", operations=operations,
                        expect=expect, fields=[], actions=voice.yes_or_no(), kind="choose")
        return Move(instruction=voice.routine_do(step), detail="", operations=operations,
                    expect=expect, fields=fields,
                    actions=voice.actions(voice.GO_AHEAD), safe=_safe(step),
                    doing=_doing(step), changes=step.changes)


class RoutineBrief:
    """What the person is asked before a routine runs: only what the helper
    said changes, one question at a time. The routine's name is the goal, and
    nothing typed is read by the router or a model.

    Stage 2: a box whose list choice follows is asked from the site's own list
    when the page has one (read before anything is touched, as the train
    search does: `details.read_stations`), and matched to it the same way
    (`details.match_station`): one is that one, a few are asked about, none
    is said. A day is asked as a journey's day is: Today, Tomorrow, or a day
    typed in, read by `details.read_day`."""

    #: Not offered as a tile again: it is one (`loop.keep_offer`).
    keepable = None

    def __init__(self, routine: Routine, fallback: Fallback | None = None,
                 today: date | None = None) -> None:
        self.routine = routine
        self.goal = routine.label
        self.gave_up: str | None = None
        self.from_tile = routine.id
        self.today = today or date.today()
        steps = routine.steps
        self._asking = [index for index in routine.asks
                        if not steps[index].pick]
        self._answers: dict[int, str] = {}
        self._tries: dict[int, int] = {}
        self._notes: dict[int, str] = {}
        #: A few from the list, offered as buttons for the box at the front.
        self._offered: list[str] = []
        #: The day question has gone on to "Pick another day".
        self._typing_day = False
        #: The site's own list, for a box whose choice follows.
        self.stations: list[str] | None = None
        self._fallback = fallback
        self.estimated_steps = len(self._asking) + len(routine.steps)

    def _picks(self, index: int) -> bool:
        steps = self.routine.steps
        return index + 1 < len(steps) and steps[index + 1].pick

    async def prepare(self, page) -> None:
        """The site's own list, read without touching anything, when a box
        asked about has its choice made from one."""
        if not any(self._picks(index) for index in self._asking):
            return
        from backend.orchestrator.details import read_stations

        names = await read_stations(page)
        if len(names) >= 2:
            self.stations = names

    def question(self) -> Move | None:
        from backend.orchestrator.details import _picked, _typed

        if self.gave_up is not None or not self._asking:
            return None
        index = self._asking[0]
        step = self.routine.steps[index]
        where = step.label or step.role
        note = self._notes.get(index)
        if step.day:
            if not self._typing_day:
                return replace(_picked(voice.ASK_ROUTINE_DAY, [
                    voice.DAY_TODAY, voice.DAY_TOMORROW, voice.DAY_PICK], kind="date"),
                    detail=voice.ASKED_EACH_TIME, note=note)
            return replace(_typed(voice.ASK_WHICH_DAY, voice.ASKED_EACH_TIME, f"value{index}",
                                  voice.FIELD_DAY, voice.USE_DAY, kind="date"), note=note)
        if self._offered:
            return replace(_picked(voice.ASK_CLOSEST, [*self._offered, voice.NONE_OF_THESE],
                                   kind="choose"), note=note)
        listed = self.stations if self._picks(index) and self.stations else []
        ask = (voice.routine_choose(where) if step.kind == "select" or self._picks(index)
               else voice.routine_ask(where))
        return Move(instruction=ask, detail=voice.ASKED_EACH_TIME, operations=[],
                    expect=Expectation(),
                    fields=[StepField(id=f"value{index}", label=where,
                                      type="choice" if listed else "text", value="",
                                      options=list(listed))],
                    actions=voice.actions(voice.USE_THIS), question=True,
                    kind="choose" if listed else "type",
                    note=note or (voice.NOT_CAUGHT if self._tries.get(index) else None))

    def answered(self, action_id: str, input_values: dict[str, str]) -> None:
        from backend.orchestrator.details import choice_index

        index = self._asking[0]
        step = self.routine.steps[index]
        self._notes.pop(index, None)
        if step.day:
            self._answer_day(index, action_id, input_values)
            return
        if self._offered:
            offered, self._offered = self._offered, []
            picked = choice_index(action_id)
            if picked is not None and picked < len(offered):
                self._take(index, offered[picked])
            return  # None of these: asked again, from the whole list
        typed = " ".join((input_values.get(f"value{index}") or "").split())
        if not typed:
            self._again(index)
            return
        if not (self._picks(index) and self.stations):
            self._take(index, typed)
            return
        from backend.orchestrator.details import match_station

        found = match_station(typed, self.stations)
        if found.station is not None:
            self._take(index, found.station)
        elif found.several:
            self._offered = list(found.several)
        else:
            self._again(index)
            self._offered = list(found.close)
            self._notes[index] = voice.not_in_list(typed)

    def _answer_day(self, index: int, action_id: str, input_values: dict[str, str]) -> None:
        from backend.orchestrator.details import (
            _coming_day_of_month,
            choice_index,
            day_trouble,
            judge_day,
            read_day,
        )

        if not self._typing_day:
            picked = choice_index(action_id)
            if picked in (0, 1):
                self._take(index, (self.today + timedelta(days=picked)).isoformat())
            else:
                self._typing_day = True
            return
        typed = (input_values.get(f"value{index}") or "").strip()
        reading = read_day(typed, self.today)
        if reading.day is None and reading.problem is None and typed.isdigit():
            found = _coming_day_of_month(int(typed), self.today)
            reading = judge_day(found, self.today) if found else reading
        if reading.day is None:
            self._again(index)
            self._notes[index] = day_trouble(reading, self.today) or voice.DAY_NOT_CAUGHT
            return
        self._typing_day = False
        self._take(index, reading.day.isoformat())

    def _take(self, index: int, answer: str) -> None:
        self._answers[index] = answer
        self._asking.pop(0)

    def _again(self, index: int) -> None:
        self._tries[index] = self._tries.get(index, 0) + 1
        if self._tries[index] >= MAX_TRIES:
            self.gave_up = voice.NOT_UNDERSTOOD

    def heading(self) -> str:
        """The routine's name, and what the person said for it, above the
        answer (stage 2): "Trains: Rawalpindi, Sukkur, Tuesday 24 November".
        Only their own answers, never the page's words."""
        said = []
        for index in sorted(self._answers):
            answer = self._answers[index]
            if self.routine.steps[index].day:
                said.append(voice.when_words(date.fromisoformat(answer), self.today))
            else:
                said.append(voice.station_name(answer) if self._picks(index) else answer)
        return f"{self.routine.label}: {', '.join(said)}" if said else self.routine.label

    def settle(self) -> tuple[RoutinePlanner, Task]:
        task = replace(routine_task(self.routine), heading=self.heading())
        return RoutinePlanner(self.routine, self._answers, self._fallback, task), task
