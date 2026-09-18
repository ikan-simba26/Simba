"""A step that fails on purpose, and what the planner is told about it.

The loop absorbs a first failure: `step.failed` to the frontend, the reason
to the planner as a setback, and on with the run. Every test of that until now
injected the failure by naming an element that does not exist. Nothing
exercised the case the mechanism is actually for — a control that is really
there, really enabled, and does nothing — because the replicas always worked.

`/stubborn` on the registration replica is that control: a `<button>` with no
form and no handler. These tests are about what happens around it.

No model here. Whether a *model* uses the setback is a live question and needs
runs; see `tools/evaluation/setback_placement_ab.py` and EVALUATION.md.
"""

import asyncio
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from backend.orchestrator.loop import Move, Task, run_task
from backend.orchestrator.plan import About, Expectation, HardcodedPlanner, Operation, Target
from backend.orchestrator.stubborn_plan import STUBBORN_PLAN, STUBBORN_TASK
from backend.orchestrator.test_verification import FakeConnection
from backend.orchestrator.voice import actions

REPO_ROOT = Path(__file__).resolve().parents[2]
REPLICA_URL = "http://127.0.0.1:5013"
STUBBORN = f"{REPLICA_URL}/stubborn"

DEAD_BUTTON = Operation("click", Target("button", "Continue"))
THE_LONG_WAY = Operation("click", Target("link", "Take the long way round"))
REACHED_THE_LIST = Expectation(url_contains="/courses")


@pytest.fixture(scope="module")
def replica() -> Iterator[str]:
    proc = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=REPO_ROOT / "replicas" / "registration",
        env={**os.environ, "PORT": "5013"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                urllib.request.urlopen(STUBBORN, timeout=1)
                break
            except (urllib.error.URLError, ConnectionError):
                time.sleep(0.2)
        else:
            raise RuntimeError("replica did not start")
        yield REPLICA_URL
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def drive(planner, task: Task = STUBBORN_TASK) -> FakeConnection:
    async def go() -> FakeConnection:
        connection = FakeConnection()
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await run_task(page, connection, planner, task, STUBBORN)
            finally:
                await browser.close()
        return connection

    return asyncio.run(go())


def move(instruction: str, operation: Operation) -> Move:
    return Move(instruction=instruction, detail="", operations=[operation],
                expect=REACHED_THE_LIST, fields=[], actions=actions("Go"))


class Listening:
    """A planner that records what it was told and chooses accordingly.

    Stands in for an LLM without being one: first the dead button, then —
    only if a setback arrived — the route that works.
    """

    calls_made = 0
    stuck_reason: str | None = None

    def __init__(self, *, recover: bool) -> None:
        self.recover = recover
        self.setbacks: list[str] = []
        self.moves = 0

    async def next_move(self, elements, history, setback):
        if setback is not None:
            self.setbacks.append(setback)
        self.moves += 1
        if self.moves == 1:
            return move("Let me try the quick way in.", DEAD_BUTTON)
        if self.recover and self.setbacks:
            return move("Let me go round the other way.", THE_LONG_WAY)
        # Told, and not listening: the same dead button again.
        return move("Let me try that again.", DEAD_BUTTON)


# --- the rig itself ---------------------------------------------------------


def test_the_dead_button_really_does_fail(replica: str) -> None:
    """Both strategies, including the JS click, land on it and change nothing.

    If this ever passes, the page is no longer rigged and everything below is
    measuring something else.
    """
    connection = drive(Listening(recover=False))

    failures = connection.of("step.failed")
    assert failures, connection.types()
    assert failures[0]["instruction"] == "Let me try the quick way in."
    assert failures[0]["strategies_tried"] == 2
    assert "did not change" in failures[0]["reason"] or "expected the URL" in failures[0]["reason"]


def test_everything_perception_reports_about_it_is_true(replica: str) -> None:
    """The button is not a trick played on perception: it is named, enabled,
    visible and uncovered. The failure is in what it does, not in what it
    looks like."""
    from backend.perception.serializer import read_async

    async def look():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            await page.goto(STUBBORN)
            view = await read_async(page)
            await browser.close()
            return view.elements

    elements = asyncio.run(look())
    button = next(e for e in elements if e.role == "button" and e.label == "Continue")
    assert not button.overlay and not button.occluded and not button.dead_link
    assert not button.inferred
    assert any(e.role == "link" and e.label == "Take the long way round" for e in elements)


# --- what the planner is told ------------------------------------------------


def test_the_setback_says_what_happened_in_words_a_planner_can_act_on(
    replica: str,
) -> None:
    planner = Listening(recover=True)
    drive(planner)

    assert planner.setbacks, "the planner was never told"
    setback = planner.setbacks[0]
    assert "Let me try the quick way in." in setback
    assert "did not work" in setback
    # And it says what to do about it, not only that something went wrong.
    assert "Choose a different action" in setback


def test_a_planner_that_acts_on_the_setback_finishes(replica: str) -> None:
    """The recovery path, end to end, on a control that really fails."""
    connection = drive(Listening(recover=True))

    completed = connection.of("task.completed")
    assert completed, connection.types()
    assert "/courses" in completed[0]["summary"]
    assert len(connection.of("step.failed")) == 1


def test_a_planner_that_ignores_it_is_stopped_after_two(replica: str) -> None:
    """Two consecutive failures end the run. The setback is a chance, not a
    licence to keep pressing the same dead button."""
    connection = drive(Listening(recover=False))

    assert not connection.of("task.completed"), connection.types()
    assert connection.of("help.requested")
    # One notice, then the run ends: the second failure is carried by
    # help.requested, not by a second step.failed.
    assert len(connection.of("step.failed")) == 1


# --- the deterministic arm ---------------------------------------------------


def test_the_hardcoded_plan_walks_it_the_same_way(replica: str) -> None:
    """`HardcodedPlanner` ignores setbacks by construction, and its second
    step is the long way round regardless. A run still survives the failure."""
    connection = drive(HardcodedPlanner(STUBBORN_PLAN))

    completed = connection.of("task.completed")
    assert completed, connection.types()
    assert completed[0]["steps_taken"] == 2
    assert len(connection.of("step.failed")) == 1


def test_the_flow_is_reachable_by_name() -> None:
    """`SIMBA_FLOW=stubborn`, so the launcher and the evaluation script agree
    on what this is called."""
    from backend.orchestrator.app import FLOWS

    task, plan, url = FLOWS["stubborn"]
    assert task is STUBBORN_TASK and plan is STUBBORN_PLAN
    assert url.endswith("/stubborn")


def test_nothing_else_in_the_replica_links_to_it() -> None:
    """The other pages' recorded element counts stay comparable."""
    templates = (REPO_ROOT / "replicas" / "registration" / "templates")
    for name in ("login.html", "courses.html", "confirm.html", "_nav.html", "_footer.html"):
        assert "stubborn" not in (templates / name).read_text(encoding="utf-8")
        assert "the_long_way" not in (templates / name).read_text(encoding="utf-8")


def test_the_task_asks_for_the_course_list(replica: str) -> None:
    assert STUBBORN_TASK.success == REACHED_THE_LIST
    assert STUBBORN_TASK.about == About()
