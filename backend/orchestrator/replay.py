"""Replay a remembered trace, and fall back to the LLM when it no longer fits.

Wraps another planner rather than replacing it. On a goal that has been done
before on this site, the recorded steps are replayed one at a time, each
resolved against the *current* page by role and label — never by the id it
had last time, since ids shift between loads.

Verification is unchanged: every replayed action is checked the same way a
planned one is, by the shared path in `loop.py`. The moment a step cannot be
resolved or does not verify, replay stops for good and the wrapped planner
takes over from that point. Whatever the run ends up doing is then recorded,
so the trace corrects itself instead of failing the same way twice.
"""

from backend.orchestrator import voice
from backend.orchestrator.loop import Move, Task
from backend.orchestrator.plan import Expectation, Operation, Target
from backend.orchestrator.traces import TraceStep, TraceStore
from backend.perception.serializer import Element
from shared.schema import StepField


def describe(step: TraceStep) -> str:
    return voice.describe(step.kind, step.label or "the element")


def steps_from(move: Move) -> list[TraceStep]:
    """Flatten a Move into what needs remembering. One step per operation."""
    return [
        TraceStep(
            kind=operation.kind,
            role=operation.target.role,
            label=operation.target.label,
            # A vault-routed field's value is a secret by construction, so the
            # key is remembered and the value never is.
            value=None if operation.value_key else operation.value,
        )
        for operation in move.operations
    ]


class TracePlanner:
    """Replays a trace if there is one, otherwise defers to the wrapped planner."""

    def __init__(self, store: TraceStore, task: Task, site: str, fallback) -> None:
        self._store = store
        self._task = task
        self._site = site
        self._fallback = fallback

        trace = store.find(task.goal, site)
        self._steps = list(trace.steps) if trace else []
        self._index = 0
        self._replaying = bool(self._steps)

        self.had_trace = bool(self._steps)
        self.replayed_steps = 0
        self.fell_back_after: int | None = None
        self.fallback_reason: str | None = None

    # The loop reads these off any planner.
    @property
    def calls_made(self) -> int:
        return getattr(self._fallback, "calls_made", 0)

    @property
    def stuck_reason(self) -> str | None:
        return getattr(self._fallback, "stuck_reason", None)

    async def next_move(
        self, elements: list[Element], history: list[str], setback: str | None
    ) -> Move | None:
        if self._replaying and setback is not None:
            # A recorded step did not resolve or did not verify. The page has
            # moved on from what was remembered; stop trusting the rest of it.
            self._stop_replaying(setback)

        if self._replaying:
            if self._index < len(self._steps):
                step = self._steps[self._index]
                self._index += 1
                self.replayed_steps += 1
                return self._move_for(step, elements)
            # The trace ran out without reaching the goal, or the goal check
            # would already have ended the run. Let the planner finish it.
            self._stop_replaying("the remembered trace ran out before the goal")

        return await self._fallback.next_move(elements, history, setback)

    def finished(self, completed: list[Move]) -> None:
        """Record what actually worked, replacing any trace that did not."""
        steps: list[TraceStep] = []
        for move in completed:
            steps.extend(steps_from(move))
        self._store.save(self._task.goal, self._site, steps)

    def _stop_replaying(self, reason: str) -> None:
        self._replaying = False
        self.fell_back_after = self._index
        self.fallback_reason = reason

    def _move_for(self, step: TraceStep, elements: list[Element]) -> Move:
        # Offer a field for a fill so the frontend can supply the value, the
        # same way the LLM planner does. A password is filled from the vault
        # and never round-tripped through the step.
        match = next(
            (e for e in elements if e.role == step.role and e.label == step.label), None
        )
        fields: list[StepField] = []
        if step.kind == "fill" and match is not None and not match.is_password:
            fields = [
                StepField(
                    id=match.name or str(match.id),
                    label=match.label,
                    type=match.input_type or "text",
                    value="",
                )
            ]

        return Move(
            instruction=describe(step),
            detail="Remembered from a previous run.",
            operations=[
                Operation(
                    kind=step.kind,
                    target=Target(role=step.role, label=step.label),
                    value=step.value,
                )
            ],
            expect=Expectation(),
            fields=fields,
            actions=voice.actions(voice.GO_AHEAD),
        )
