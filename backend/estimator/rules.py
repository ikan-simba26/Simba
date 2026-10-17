"""PROVISIONAL. Which detail level to show, by hand-written rules.

**This is not the estimator.** It is a stand-in so that the level adapts in a
real run at all — until it existed only the mock sent `load.updated`, so the
fold between levels never happened outside a script. The trained model
replaces it. Every threshold below is a guess, recorded as one in
DECISIONS.md, and every decision is written down with what it was made from
(`pairing.Recorder.note_decision`) so the model can later be checked against
these rules rather than against nothing.

What it does:

- **A starting level from the page.** Before the first step, a page with at
  least two of the three signs of a heavy page — many controls, dense text,
  something covering it — starts at level 3. Anything else starts at 2.
- **Simpler, during a step, on one clear signal.** A long pause, a pointer
  wandering or doubling back, or a press of "What are you doing?" moves one
  level simpler, straight away, while the step is still on screen.
- **Back, slowly.** Only after two calm steps in a row, one level, and only
  as the next step arrives — a screen does not reshape as it leaves. Never
  past level 2: more detail is something a person chooses, not something
  inferred.
- **Never more than one change per step,** whatever the signals do.
- **A locked level never moves.** The decision is still made and written
  down, with what it would have done; it is just not sent.
- **The overflow guard is followed, not fought.** When the overlay drops a
  level because a step does not fit, it says so (`level.override` with
  `by: "overflow"`). That is the step's one change, it does not count against
  a calm run, and it never becomes the lock: a lock is only ever the person's
  own choice, and each new step is shown at it again.

The score is the strongest signal's distance to its threshold, 0–1, so 1.0
means "a rule fired". It is a readout of these rules, not a measure of load,
and the contract's `reason` is never shown to the person.

Pure: no I/O, no clock. The loop calls it and does the sending and writing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from backend.estimator.page_features import PageFeatures
from shared.schema import LoadUpdated

#: Written into every decision row, so a row from these rules can never be
#: mistaken for one from the model that replaces them.
RULES_VERSION = "provisional"

SIMPLEST = 3
#: Where the rules restore to, and never go past.
BASELINE = 2


@dataclass(frozen=True)
class Thresholds:
    """Every number the rules use. **All guesses** (DECISIONS.md, 2026-09-25).

    Where a number came from is noted beside it. None of them is calibrated:
    the telemetry behind them is the 36 answered steps in this machine's
    `data/steps.jsonl` on 2026-09-25, every one of them a script driving a
    browser (STATUS.md). No person's behaviour is behind any number here.
    """

    # --- the page, before the first step --------------------------------------
    #: Controls (links and non-links). Between the corpus median (56) and its
    #: 75th percentile (241); python.org is 153, the registration page 66.
    heavy_controls: int = 150
    #: Characters per 1000px² in the viewport. The corpus 90th percentile.
    heavy_text_density: float = 2.5
    #: Anything covering the page at all.
    heavy_overlays: int = 1
    #: How many of the three it takes. One is not enough: registration's
    #: sign-in page is dense (2.57) and otherwise ordinary.
    heavy_signs: int = 2

    # --- the person, during a step ----------------------------------------------
    #: The recorded answered steps take 1.0–7.8s, median about 2s.
    hesitation_ms: int = 15_000
    #: Pointer path over straight-line distance.
    wander_ratio: float = 6.0
    #: Turns of more than ~120°. Recorded steps answered in under 8s reach 6.
    wander_backtracks: int = 8
    #: Before this, pointer signals are ignored. A short hop divides by a
    #: short distance: one recorded step answered in 3s has a ratio of 24.8.
    wander_after_ms: int = 6_000
    #: "What are you doing?" pressed at all.
    help_presses: int = 1

    # --- calm ----------------------------------------------------------------------
    #: A step answered faster than this, with no signal, is calm. Between it and
    #: `hesitation_ms` a step is neither, and breaks a calm run.
    calm_hesitation_ms: int = 8_000
    #: Calm steps in a row before one level back.
    calm_steps: int = 2


THRESHOLDS = Thresholds()

When = Literal["start", "step", "waiting", "answered", "override", "end"]


@dataclass(frozen=True)
class Decision:
    """One evaluation of the rules, and whether it goes to the frontend."""

    at: When
    step_index: int
    score: float
    level_before: int
    level: int
    #: Which rule decided: start, simplify, restore, hold, locked,
    #: once-per-step, simplest, override, overflow, stale.
    rule: str
    reason: str
    send: bool
    inputs: dict[str, Any] = field(default_factory=dict)

    @property
    def changed(self) -> bool:
        return self.level != self.level_before

    def load(self) -> LoadUpdated:
        return LoadUpdated(score=self.score, level=self.level, reason=self.reason)

    def as_row(self) -> dict[str, Any]:
        return {
            "rules": RULES_VERSION,
            "at": self.at,
            "step_index": self.step_index,
            "score": self.score,
            "level_before": self.level_before,
            "level": self.level,
            "changed": self.changed,
            "sent": self.send,
            "rule": self.rule,
            "reason": self.reason,
            "inputs": self.inputs,
        }


def page_signs(features: PageFeatures | None, t: Thresholds = THRESHOLDS) -> list[str]:
    """Which signs of a heavy page this page shows, in words for the log."""
    if features is None:
        return []
    signs = []
    if features.controls >= t.heavy_controls:
        signs.append(f"{features.controls} controls")
    if features.text_density >= t.heavy_text_density:
        signs.append(f"text density {features.text_density:g}")
    if features.overlays >= t.heavy_overlays:
        signs.append(f"{features.overlays} covering")
    return signs


def person_signals(payload: dict, t: Thresholds = THRESHOLDS) -> tuple[float, list[str]]:
    """How close each signal is to its threshold, and which ones reached it."""
    ms = int(payload.get("hesitation_ms") or 0)
    ratio = float(payload.get("cursor_path_ratio") or 1.0)
    backtracks = int(payload.get("backtracks") or 0)
    helps = int(payload.get("help_presses") or 0)

    pressures = {
        f"paused {ms / 1000:.1f}s": ms / t.hesitation_ms,
        f"pressed help {helps}x": helps / t.help_presses,
    }
    # Pointer signals only count once the step has been up long enough for
    # movement to mean something (see `wander_after_ms`).
    if ms >= t.wander_after_ms:
        pressures[f"pointer wandering {ratio:g}"] = ratio / t.wander_ratio
        pressures[f"doubled back {backtracks}x"] = backtracks / t.wander_backtracks

    fired = [name for name, pressure in pressures.items() if pressure >= 1.0]
    return min(1.0, max(pressures.values())), fired


class LevelRules:
    """The level one run is at, and every decision about it.

    One per connection. The loop calls `start_step` before each step goes on
    screen, `telemetry` for every sample, `override` for every
    `level.override`, and `end` before the task completes.
    """

    def __init__(self, thresholds: Thresholds = THRESHOLDS) -> None:
        self.t = thresholds
        #: Where a task starts and where calm steps bring it back: 2, or the
        #: level the person chose as comfortable in the welcome (2026-10-18,
        #: `start_from`).
        self.baseline: int = BASELINE
        self.level: int = BASELINE
        self.locked = False
        #: The level the person chose and locked. `level` can differ from it
        #: for one step, when the overflow guard moves the screen under a lock.
        self.locked_level: int | None = None
        self.started = False
        self.step_index = 0
        #: The step the level last changed on. The start counts as step 0.
        self.changed_on: int | None = None
        self.calm_streak = 0
        #: A signal reached its threshold on the current step, whether or not
        #: the level could move for it. Such a step is not calm.
        self.signalled = False
        self.page_score = 0.0

    def start_from(self, level: int | None) -> None:
        """The person's own level, from `task.start.start_level` (2026-10-18):
        the task starts there, unless the page is heavy, and calm steps come
        back to it. None, or anything but 1 to 3, leaves 2."""
        if level in (1, 2, 3) and not self.started:
            self.baseline = level
            self.level = level

    # --- the three moments ---------------------------------------------------------

    def start_step(self, step_index: int, features: PageFeatures | None) -> Decision:
        """Before step `step_index` goes on screen: the start, or a return."""
        self.step_index = step_index
        self.signalled = False
        # A guard move under a lock lasts one step; the next is shown at the
        # person's own level again, as the overlay does.
        if self.locked and self.locked_level is not None:
            self.level = self.locked_level
        signs = page_signs(features, self.t)
        self.page_score = min(1.0, len(signs) / self.t.heavy_signs)
        inputs = {"page": features.as_dict() if features else None,
                  "heavy_signs": signs}

        if not self.started:
            self.started = True
            heavy = len(signs) >= self.t.heavy_signs
            wanted = SIMPLEST if heavy else self.baseline
            why = (f"heavy page: {', '.join(signs)}" if heavy
                   else f"ordinary page{': ' + ', '.join(signs) if signs else ''}")
            if not heavy and self.baseline != BASELINE:
                why += f"; the person's own level, {self.baseline}"
            if self.locked:
                return self._hold("start", "locked",
                                  f"locked at {self.locked_level}; would start at {wanted}: {why}",
                                  self.page_score, inputs)
            return self._move("start", wanted, "start", why, self.page_score, inputs,
                              always_send=True)

        return self._between_steps("step", inputs)

    def telemetry(self, payload: dict) -> Decision:
        """One sample, on the timer or with the answer."""
        at: When = "answered" if payload.get("answered") else "waiting"
        pressure, fired = person_signals(payload, self.t)
        score = max(self.page_score, pressure)
        inputs = {"telemetry": dict(payload)}

        if payload.get("step_index") != self.step_index:
            return self._hold(at, "stale", "sample for a step not on screen", score, inputs)

        if fired:
            self.signalled = True
        # A calm step is judged on the whole step, so it is settled on the
        # answer — before the decision below, which may still record a move.
        if at == "answered":
            calm = (not self.signalled
                    and int(payload.get("hesitation_ms") or 0) < self.t.calm_hesitation_ms)
            self.calm_streak = self.calm_streak + 1 if calm else 0

        if not fired:
            return self._hold(at, "hold", "calm" if pressure < 1 else "no signal", score,
                              inputs)
        why = ", ".join(fired)
        if self.locked:
            return self._hold(at, "locked",
                              f"locked at {self.locked_level}; would simplify: {why}", score,
                              inputs)
        if self.changed_on == self.step_index:
            return self._hold(at, "once-per-step", f"already changed this step: {why}",
                              score, inputs)
        if self.level >= SIMPLEST:
            return self._hold(at, "simplest", f"already simplest: {why}", score, inputs)
        return self._move(at, self.level + 1, "simplify", why, score, inputs)

    def override(self, level: int, locked: bool, by: str = "person") -> Decision:
        """A level the overlay set. Never sent back: the screen already shows it.

        `by` is `person` — they chose a level, or handed it back — or
        `overflow`, the overlay's guard dropping a level because the step did
        not fit. The guard's move is followed, is this step's one change, and
        leaves the lock and the calm run exactly as they were.
        """
        before = self.level
        self.level = level
        inputs = {"override": {"level": level, "locked": locked, "by": by}}
        if by == "overflow":
            if not self.locked:
                self.changed_on = self.step_index
            lock = f"; lock stays at {self.locked_level}" if self.locked else ""
            return Decision(
                at="override", step_index=self.step_index, score=self.page_score,
                level_before=before, level=level, rule="overflow",
                reason=f"step did not fit; overlay moved to {level}{lock}", send=False,
                inputs=self._state(inputs),
            )
        self.locked = locked
        self.locked_level = level if locked else None
        self.calm_streak = 0
        return Decision(
            at="override", step_index=self.step_index, score=self.page_score,
            level_before=before, level=level, rule="override",
            reason=f"{'locked' if locked else 'handed back'} at {level}", send=False,
            inputs=self._state(inputs),
        )

    def end(self) -> Decision:
        """Before the ending: a return that was due has no next step to wait for."""
        return self._between_steps("end", {})

    # --- helpers ---------------------------------------------------------------------------

    def _between_steps(self, at: When, inputs: dict[str, Any]) -> Decision:
        """The only place the level goes back: two calm steps, then one level."""
        if self.calm_streak >= self.t.calm_steps and self.level > self.baseline:
            why = f"{self.calm_streak} calm steps in a row"
            if self.locked:
                return self._hold(at, "locked",
                                  f"locked at {self.locked_level}; would restore: {why}",
                                  self.page_score, inputs)
            return self._move(at, self.level - 1, "restore", why, self.page_score, inputs)
        return self._hold(at, "hold", "no change between steps", self.page_score, inputs)

    def _state(self, extra: dict[str, Any]) -> dict[str, Any]:
        return {
            **extra,
            "level": self.level,
            "locked": self.locked,
            "locked_level": self.locked_level,
            "calm_streak": self.calm_streak,
            "changed_on_step": self.changed_on,
            "thresholds": asdict(self.t),
        }

    def _hold(self, at: When, rule: str, reason: str, score: float,
              inputs: dict[str, Any]) -> Decision:
        return Decision(at=at, step_index=self.step_index, score=round(score, 3),
                        level_before=self.level, level=self.level, rule=rule,
                        reason=reason, send=False, inputs=self._state(inputs))

    def _move(self, at: When, level: int, rule: str, reason: str, score: float,
              inputs: dict[str, Any], always_send: bool = False) -> Decision:
        state = self._state(inputs)
        before = self.level
        self.level = level
        self.calm_streak = 0
        self.changed_on = 0 if at == "start" else self.step_index
        return Decision(at=at, step_index=self.step_index, score=round(score, 3),
                        level_before=before, level=level, rule=rule, reason=reason,
                        send=always_send or level != before, inputs=state)
