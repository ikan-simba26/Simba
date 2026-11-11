"""The starter tasks in `demo/starters/` (2026-11-11) and the teach clip.

The files are made by `python -m tools.starter_tasks make` through the
overlay's own "Save to a file"; these check what they must be, whoever made
them: routines SIMBA reads, on this machine's copies only, asking the person
for everything the helper typed, with nothing typed kept. Running them from a
tile needs the stack (`python -m tools.starter_tasks check`, EVALUATION.md
2026-11-11c).
"""

from urllib.parse import urlsplit

import pytest

from backend.orchestrator.routines import parse
from tools import record_demo, starter_tasks


@pytest.mark.parametrize("which", sorted(starter_tasks.TASKS))
def test_each_starter_is_a_routine_on_our_copy(which: str) -> None:
    task = starter_tasks.TASKS[which]
    text = (starter_tasks.STARTERS / task["file"]).read_text(encoding="utf-8")
    routine = parse(text)
    assert routine.label == task["label"]
    assert routine.answer.name == task["answer"]
    # Our own copies, served from this machine: never a live site.
    assert urlsplit(routine.start).hostname == "127.0.0.1"
    assert routine.start.startswith(task["origin"])


@pytest.mark.parametrize("which", sorted(starter_tasks.TASKS))
def test_a_starter_asks_for_what_was_typed_and_keeps_none_of_it(which: str) -> None:
    task = starter_tasks.TASKS[which]
    text = (starter_tasks.STARTERS / task["file"]).read_text(encoding="utf-8")
    routine = parse(text)
    typed = [step for step in routine.steps if step.kind == "fill"]
    assert typed and all(step.ask and step.value is None for step in typed)
    assert starter_tasks.REFERENCE not in text


def test_the_trains_starter_asks_the_day() -> None:
    routine = parse((starter_tasks.STARTERS / "train-times.simba-routine.json")
                    .read_text(encoding="utf-8"))
    assert [step for step in routine.steps if step.day and step.ask]


def test_the_teach_clip_has_the_reference_to_give_and_shows_the_proof() -> None:
    assert any(c[0] == "teach" for c in record_demo.CLIPS)
    assert record_demo.ANSWERS["teach"]["type"] == [starter_tasks.REFERENCE]
    assert "teach" in record_demo.SHOWS_PROOF
