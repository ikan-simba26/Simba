"""A step's page and what the person did on it, written down as one row.

Two levels, because the pairing can fail at either:

  * the recorder on its own — does a sample land on the right step, is a timer
    tick told from an answer, and is a sample for a step nobody presented
    quietly dropped;
  * the loop, driving the real replica in a real browser, with telemetry
    arriving the way the overlay sends it: one while the step waits, and one
    with the answer.

Nothing here asserts a number is good. There is no score and there are no
weights (DECISIONS.md, 2026-09-19).
"""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from playwright.async_api import async_playwright

from backend.estimator.page_features import PageFeatures
from backend.estimator.pairing import Recorder, read_rows, recording_enabled
from backend.orchestrator.loop import Connection, Task, run_task
from backend.orchestrator.plan import (
    REGISTRATION_PLAN,
    About,
    Expectation,
    HardcodedPlanner,
)

CREDENTIALS = {"username": "raham", "password": "hunter2"}

TASK = Task(
    goal="Register for the course CS-401.",
    estimated_steps=3,
    success=Expectation(url_contains="/register",
                        title_contains="Registration Confirmed"),
    about=About(),
)

SAMPLE = {
    "step_index": 1,
    "hesitation_ms": 4200,
    "cursor_path_ratio": 3.8,
    "backtracks": 1,
    "rereads": 2,
    "help_presses": 0,
}

FEATURES = PageFeatures(
    interactive=21, links=45, inferred=0, text_density=4.81, max_depth=11,
    overlays=1, form_fields=0, dead_link_ratio=0.978, reading_grade=6.41,
    controls=66, dead_links=44, characters=5299,
    viewport_characters=4929, words=680, sentences=202, syllables=1192,
)


@pytest.fixture
def recorder(tmp_path) -> Recorder:
    return Recorder(path=tmp_path / "steps.jsonl", task_id="t_test")


# --- the recorder on its own ------------------------------------------------


def test_a_sample_is_written_beside_the_page_its_step_was_showing(
    recorder: Recorder,
) -> None:
    recorder.note_step(1, goal="Register for CS-401", url="http://x/courses",
                       instruction="Let me open the list.", features=FEATURES)

    row = recorder.note_telemetry(SAMPLE)

    assert row is not None
    assert row["step_index"] == 1
    assert row["goal"] == "Register for CS-401"
    assert row["instruction"] == "Let me open the list."
    assert row["page"]["controls"] == 66 and row["page"]["overlays"] == 1
    assert row["telemetry"]["hesitation_ms"] == 4200
    assert read_rows(recorder.path) == [row]


def test_a_timer_tick_and_an_answer_are_told_apart(recorder: Recorder) -> None:
    """A step that took thirty seconds leaves a trail, and the trail is the
    interesting part — hesitation that grows, not its final value."""
    recorder.note_step(2, goal="g", url="u", instruction="i", features=FEATURES)

    recorder.note_telemetry({**SAMPLE, "step_index": 2, "hesitation_ms": 3000})
    recorder.note_telemetry({**SAMPLE, "step_index": 2, "hesitation_ms": 6000})
    recorder.note_telemetry({**SAMPLE, "step_index": 2, "hesitation_ms": 8100,
                             "answered": True})

    rows = read_rows(recorder.path)
    assert [row["when"] for row in rows] == ["waiting", "waiting", "answered"]
    assert [row["telemetry"]["hesitation_ms"] for row in rows] == [3000, 6000, 8100]
    # `answered` is how the two are told apart, and is not itself a signal.
    assert "answered" not in rows[0]["telemetry"]


def test_a_sample_for_a_step_nobody_presented_is_dropped(recorder: Recorder) -> None:
    """A row with no page on it teaches nothing, and a stale sample from a
    previous run is not worth stopping a task for."""
    assert recorder.note_telemetry(SAMPLE) is None
    assert recorder.written == 0
    assert read_rows(recorder.path) == []


def test_a_page_read_without_a_snapshot_is_recorded_as_having_none(
    recorder: Recorder,
) -> None:
    """The ablation switches turn the snapshot off. The row says so rather
    than inventing zeroes."""
    recorder.note_step(1, goal="g", url="u", instruction="i", features=None)

    row = recorder.note_telemetry(SAMPLE)

    assert row["page"] is None
    assert row["telemetry"]["hesitation_ms"] == 4200


def test_rows_are_appended_so_a_crashed_run_keeps_what_it_had(
    recorder: Recorder,
) -> None:
    recorder.note_step(1, goal="g", url="u", instruction="i", features=FEATURES)
    recorder.note_telemetry(SAMPLE)
    again = Recorder(path=recorder.path, task_id="t_second")
    again.note_step(1, goal="g2", url="u2", instruction="i2", features=None)
    again.note_telemetry(SAMPLE)

    lines = recorder.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert [json.loads(line)["task_id"] for line in lines] == ["t_test", "t_second"]


def test_recording_is_on_unless_it_is_turned_off(monkeypatch) -> None:
    # The suite turns it off for every app it starts (`backend/conftest.py`).
    monkeypatch.delenv("SIMBA_RECORD_STEPS", raising=False)
    assert recording_enabled()
    monkeypatch.setenv("SIMBA_RECORD_STEPS", "0")
    assert not recording_enabled()


# --- and through the loop, on a real page -----------------------------------


class TelemetryConnection(Connection):
    """A frontend that sends a timer sample, then answers the step.

    Which is what the overlay does: `telemetry.ts` samples while a step waits
    and sends one more with the response.
    """

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []

    async def send(self, message_type: str, payload) -> None:
        self.sent.append((message_type, payload.model_dump()))

    async def receive(self, message_type: str, step_index=None, on_other=None) -> dict:
        if on_other is not None:
            # While the step is on screen: one tick, as the timer would.
            await on_other({
                "type": "telemetry",
                "payload": {**SAMPLE, "step_index": step_index,
                            "hesitation_ms": 3000},
            })
            # And the one that goes with the press.
            await on_other({
                "type": "telemetry",
                "payload": {**SAMPLE, "step_index": step_index,
                            "hesitation_ms": 5200, "answered": True},
            })
        return {
            "type": "step.response",
            "payload": {"step_index": step_index, "action_id": "confirm",
                        "input_values": CREDENTIALS},
        }


def test_the_loop_pairs_what_it_showed_with_what_came_back(
    replica: str, tmp_path
) -> None:
    """End to end on the registration replica: three steps, two samples each,
    each row carrying the features of the page that step was showing."""
    recorder = Recorder(path=tmp_path / "steps.jsonl", task_id="t_loop")

    async def go() -> None:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await run_task(
                    page, TelemetryConnection(), HardcodedPlanner(REGISTRATION_PLAN),
                    TASK, replica, recorder,
                )
            finally:
                await browser.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(lambda: asyncio.run(go())).result()

    rows = read_rows(recorder.path)
    assert len(rows) >= 4, rows
    assert {row["when"] for row in rows} == {"waiting", "answered"}

    for row in rows:
        assert row["task_id"] == "t_loop"
        assert row["goal"] == TASK.goal
        assert row["instruction"], "a row should say which step it belongs to"
        # The page as it was when that step went on screen.
        assert row["page"]["controls"] > 0
        assert row["page"]["reading_grade"] != 0
        assert row["telemetry"]["cursor_path_ratio"] == 3.8

    # The page changes under the run, and the rows follow it: signing in opens
    # a modal, and the course list is a different page from the login form.
    pages = [row["page"]["controls"] for row in rows]
    assert len(set(pages)) > 1, pages
    assert any(row["page"]["overlays"] == 1 for row in rows), "the modal was never seen"


def test_a_run_without_a_recorder_writes_nothing(replica: str, tmp_path) -> None:
    """Every other test in this repository drives `run_task` without one."""
    out = tmp_path / "steps.jsonl"

    async def go() -> None:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await run_task(page, TelemetryConnection(),
                               HardcodedPlanner(REGISTRATION_PLAN), TASK, replica)
            finally:
                await browser.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(lambda: asyncio.run(go())).result()

    assert not out.exists()
