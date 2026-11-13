"""One row per step: what the page was like, and what the person did on it.

The estimator's whole premise is that two channels say something neither says
alone — what the *page* is (`page_features`) and what the *person* does with
it (`telemetry`, CONTRACT.md). Neither is worth much unpaired: a dense page
that someone sails through is not a problem, and a simple page someone stalls
on is.

Nothing here scores anything. It writes the pairs down, in the order they
happen, so that a training set exists when there is something to train. That
is the same order the features were built in and for the same reason
(DECISIONS.md, 2026-09-19).

**What a row is.** One telemetry sample, with the page as it was when the step
it belongs to was presented:

    {"ts": ..., "task_id": "...", "step_index": 2, "goal": "...",
     "url": "...", "instruction": "...", "when": "answered" | "waiting",
     "page": {"controls": 66, "overlays": 1, ...},
     "telemetry": {"hesitation_ms": 4200, "cursor_path_ratio": 3.8, ...}}

`when` matters: the frontend sends on every step response *and* on a timer
while the step is still on screen, so a step that took a person thirty seconds
leaves a trail of `waiting` rows and one `answered` row, and the trail is the
interesting part — hesitation that grows is the signal, not its final value.

Since 2026-09-25 the file holds a second kind of row: every decision the
provisional level rules make (`rules.py`), with the inputs it was made from.
`kind` tells them apart — `telemetry` or `decision`; a row written before
that day has no `kind` and is a telemetry row.

Since 2026-10-18, a third: `start_level`, once per task — the level the
person chose as comfortable in the overlay's welcome, or `null` if they did
not choose — and the same value on every telemetry row after it, as
`start_level`, so each row says what the person said about themselves beside
what they did. It is the person's own report, not a measurement: see
DECISIONS.md, *The starting level is a signal of its own*.

**Appended, never rewritten**, as JSON lines, so a crashed run keeps whatever
it had written and a reader can `tail` it while a run is happening.

No personal data: no keystrokes, no field values, no screenshots. Cursor
geometry, counts, and milliseconds. The goal is written down because it is
the person's own sentence and the row is meaningless without it — which is
also why this file is in `data/` and not in a log anyone ships.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from backend.estimator.page_features import PageFeatures
from backend.estimator.rules import Decision

REPO_ROOT = Path(__file__).resolve().parents[2]
#: `SIMBA_STEPS` moves it: the installed app keeps it in the person's profile
#: folder, not in the install folder (`frontend/electron/backend.ts`, 2026-11-13).
DEFAULT_PATH = Path(os.environ.get("SIMBA_STEPS") or REPO_ROOT / "data" / "steps.jsonl")

#: Set to "0" to run without writing anything. The app turns recording on;
#: tests pass their own recorder or none at all.
ENV_SWITCH = "SIMBA_RECORD_STEPS"


def recording_enabled() -> bool:
    return os.environ.get(ENV_SWITCH, "1").strip().lower() not in {"0", "false", "no"}


@dataclass
class Step:
    """What was on screen when a step was presented."""

    step_index: int
    goal: str
    url: str
    instruction: str
    features: PageFeatures | None


@dataclass
class Recorder:
    """Holds the current step's page, and writes a row per telemetry sample.

    One per run. `note_step` is called when a step is presented — before the
    person has done anything — and `note_telemetry` every time a sample
    arrives for it.
    """

    path: Path = DEFAULT_PATH
    task_id: str = "t_unknown"
    #: Rows written, for a caller that wants to say so without reading the file.
    written: int = 0
    #: The level the person chose in the welcome, for this task; None if they
    #: did not choose (2026-10-18).
    start_level: int | None = None
    _steps: dict[int, Step] = field(default_factory=dict)

    def note_step(
        self,
        step_index: int,
        *,
        goal: str,
        url: str,
        instruction: str,
        features: PageFeatures | None,
    ) -> None:
        self._steps[step_index] = Step(
            step_index=step_index, goal=goal, url=url,
            instruction=instruction, features=features,
        )

    def note_telemetry(self, payload: dict) -> dict | None:
        """Pair one telemetry sample with its step and write the row.

        Returns the row, or None when the sample names a step this run never
        presented — which is not an error worth stopping a run for, and is
        worth not writing: a row with no page on it teaches nothing.
        """
        index = payload.get("step_index")
        step = self._steps.get(index) if isinstance(index, int) else None
        if step is None:
            return None

        row = {
            "kind": "telemetry",
            "ts": int(time.time() * 1000),
            "task_id": self.task_id,
            "step_index": step.step_index,
            "goal": step.goal,
            "url": step.url,
            "instruction": step.instruction,
            # A sample that arrives with a step response is the step being
            # answered; anything else is the timer while it sat there.
            "when": "answered" if payload.get("answered") else "waiting",
            "page": step.features.as_dict() if step.features else None,
            "telemetry": {key: value for key, value in payload.items()
                          if key not in {"answered"}},
            "start_level": self.start_level,
        }
        self._write(row)
        return row

    def note_start_level(self, level: object) -> dict:
        """The level the person chose as comfortable, as the task starts
        (`task.start.start_level`, 2026-10-18): its own row, and on every
        telemetry row after it. Anything but 1, 2 or 3 is written as null —
        not chosen — and never as 2, which would claim a choice not made."""
        chosen = isinstance(level, int) and not isinstance(level, bool) and level in (1, 2, 3)
        self.start_level = level if chosen else None
        row = {
            "kind": "start_level",
            "ts": int(time.time() * 1000),
            "task_id": self.task_id,
            "start_level": self.start_level,
            "chosen": self.start_level is not None,
        }
        self._write(row)
        return row

    def note_decision(self, decision: Decision) -> dict:
        """Write down one decision of the level rules, with what it was made from.

        Every decision, not only the ones that moved the level: a trained
        model is checked against what the rules would have done at each
        sample, and "held" is an answer as much as "folded" is.
        """
        row = {
            "kind": "decision",
            "ts": int(time.time() * 1000),
            "task_id": self.task_id,
            **decision.as_row(),
        }
        self._write(row)
        return row

    def _write(self, row: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as lines:
            lines.write(json.dumps(row, ensure_ascii=False) + "\n")
        self.written += 1


def read_rows(path: Path = DEFAULT_PATH) -> list[dict]:
    """Every row written so far. For a reader, a test, or a training set."""
    if not path.exists():
        return []
    return [json.loads(line) for line in
            path.read_text(encoding="utf-8").splitlines() if line.strip()]
