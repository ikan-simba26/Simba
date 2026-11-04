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

from backend.orchestrator import voice
from backend.orchestrator.loop import Move, Planner, Task
from backend.orchestrator.plan import About, Expectation, Operation, Target
from backend.orchestrator.plan import Answer as Finds
from backend.orchestrator.routines import Routine, Step, asks_consent
from backend.perception.serializer import Element
from shared.schema import StepField

#: How many unusable answers to one question before the run gives up, as for
#: every other question (`details.MAX_TRIES`).
MAX_TRIES = 3

#: Builds the planner that takes over when the person agrees: the task in
#: hand, and a planner back. None when no model is set up.
Fallback = Callable[[Task], Planner]


def find(elements: list[Element], step: Step) -> Element | None:
    """The element a move was made on, on the page as it is now: same role,
    same label, the same qualifier when one was kept, and the same one of
    several alike. None when the page has no such element."""
    alike = [e for e in elements if e.role == step.role and e.label == step.label
             and (step.qualifier is None or e.qualifier == step.qualifier)]
    return alike[step.nth] if step.nth < len(alike) else None


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
        scope=None if routine.changes else voice.ROUTINE_SCOPE,
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
            if not _safe(step):
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
            # It was found, and it did not do what it did when it was shown.
            done = self.routine.steps[self._index - 1]
            return self._stopped(voice.routine_did_not_work(done.label or done.role))
        if self._index >= len(self.routine.steps):
            return None
        step = self.routine.steps[self._index]
        if find(elements, step) is None:
            return self._stopped(voice.routine_changed(step.label or f"the {step.role}"))
        move = self.move_for(self._index, elements)
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

    def answered(self, action_id: str, input_values: dict[str, str]) -> None:  # noqa: ARG002
        """The person's answer to "Shall I try to work out the rest?"."""
        if action_id == voice.CONFIRM_ID and self._fallback is not None:
            self._model = self._fallback(self._task)
            self._stop = None

    def move_for(self, index: int, elements: list[Element] | None = None) -> Move:
        """One kept move as the loop runs it."""
        step = self.routine.steps[index]
        element = find(elements, step) if elements is not None else None
        target = Target(role=step.role, label=step.label, qualifier=step.qualifier)
        # The first of several alike is what matching by role and label finds
        # anyway; any other is named by the id it has on this reading.
        element_id = element.id if element is not None and step.nth > 0 else None
        expect = Expectation(url_contains=step.expect_url, label_present=step.expect_label,
                             list_opens=step.list_opens)
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
        if asks_consent(step):
            return Move(instruction=voice.ASK_COOKIES, detail="", operations=[operation],
                        expect=expect, fields=[], actions=voice.yes_or_no(), kind="choose")
        return Move(instruction=voice.routine_do(step), detail="", operations=[operation],
                    expect=expect, fields=fields,
                    actions=voice.actions(voice.GO_AHEAD), safe=_safe(step),
                    doing=_doing(step), changes=step.changes)


class RoutineBrief:
    """What the person is asked before a routine runs: only what the helper
    said changes, one question at a time. The routine's name is the goal, and
    nothing typed is read by the router or a model."""

    #: Not offered as a tile again: it is one (`loop.keep_offer`).
    keepable = None

    def __init__(self, routine: Routine, fallback: Fallback | None = None) -> None:
        self.routine = routine
        self.goal = routine.label
        self.gave_up: str | None = None
        self.from_tile = routine.id
        self._asking = list(routine.asks)
        self._answers: dict[int, str] = {}
        self._tries: dict[int, int] = {}
        self._fallback = fallback
        self.estimated_steps = len(self._asking) + len(routine.steps)

    def question(self) -> Move | None:
        if self.gave_up is not None or not self._asking:
            return None
        index = self._asking[0]
        step = self.routine.steps[index]
        where = step.label or step.role
        ask = voice.routine_choose(where) if step.kind == "select" else voice.routine_ask(where)
        return Move(instruction=ask, detail=voice.ASKED_EACH_TIME, operations=[],
                    expect=Expectation(),
                    fields=[StepField(id=f"value{index}", label=where, type="text", value="")],
                    actions=voice.actions(voice.USE_THIS), question=True, kind="type",
                    note=voice.NOT_CAUGHT if self._tries.get(index) else None)

    def answered(self, action_id: str, input_values: dict[str, str]) -> None:  # noqa: ARG002
        index = self._asking[0]
        typed = " ".join((input_values.get(f"value{index}") or "").split())
        if not typed:
            self._tries[index] = self._tries.get(index, 0) + 1
            if self._tries[index] >= MAX_TRIES:
                self.gave_up = voice.NOT_UNDERSTOOD
            return
        self._answers[index] = typed
        self._asking.pop(0)

    def settle(self) -> tuple[RoutinePlanner, Task]:
        task = routine_task(self.routine)
        return RoutinePlanner(self.routine, self._answers, self._fallback, task), task
