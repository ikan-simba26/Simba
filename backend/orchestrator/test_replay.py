"""Trace memory: record a run, replay it, and cope when the page has moved on."""

import asyncio

from playwright.async_api import async_playwright

from backend.orchestrator.llm import Action, LLMError
from backend.orchestrator.llm_loop import REGISTRATION_TASK, LLMPlanner
from backend.orchestrator.loop import Move, Task, run_task
from backend.orchestrator.plan import Expectation, Operation, Target
from backend.orchestrator.replay import TracePlanner, steps_from
from backend.orchestrator.test_llm_loop import LabelDrivenProvider
from backend.orchestrator.test_orchestrator import replica  # noqa: F401
from backend.orchestrator.test_verification import FakeConnection
from backend.orchestrator.traces import TraceStep, TraceStore, site_of

CREDENTIALS = {"username": "raham", "password": "hunter2"}

THE_WAY = [
    ("type", "Student ID or Username"),
    ("type", "Password"),
    ("click", "Sign In"),
    ("click", "Close"),
    ("click", "Register for CS-401"),
]


def drive(planner, task: Task, start_url: str) -> FakeConnection:
    async def go() -> FakeConnection:
        connection = FakeConnection()
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await run_task(page, connection, planner, task, start_url)
            finally:
                await browser.close()
        return connection

    return asyncio.run(go())


def planner_for(store: TraceStore, site: str, script=None):
    provider = LabelDrivenProvider(list(script if script is not None else THE_WAY))
    fallback = LLMPlanner(provider, REGISTRATION_TASK)
    planner = TracePlanner(store, REGISTRATION_TASK, site, fallback)
    planner.provider = provider  # for assertions
    return planner


# --- the store --------------------------------------------------------------


def test_a_trace_round_trips(tmp_path) -> None:
    store = TraceStore(tmp_path / "t.db")
    steps = [TraceStep("fill", "textbox", "User"), TraceStep("click", "button", "Go")]

    store.save("goal", "http://x", steps)

    trace = store.find("goal", "http://x")
    assert trace is not None
    assert trace.steps == steps
    assert trace.created_at


def test_an_unknown_goal_has_no_trace(tmp_path) -> None:
    store = TraceStore(tmp_path / "t.db")
    assert store.find("never done", "http://x") is None


def test_re_recording_replaces_rather_than_duplicates(tmp_path) -> None:
    store = TraceStore(tmp_path / "t.db")
    store.save("goal", "http://x", [TraceStep("click", "button", "Old")])

    store.save("goal", "http://x", [TraceStep("click", "button", "New")])

    assert store.find("goal", "http://x").steps == [TraceStep("click", "button", "New")]
    assert store.goals() == [("goal", "http://x")]


def test_a_different_site_is_a_different_trace(tmp_path) -> None:
    store = TraceStore(tmp_path / "t.db")
    store.save("goal", "http://a", [TraceStep("click", "button", "A")])

    assert store.find("goal", "http://b") is None


def test_site_is_the_origin() -> None:
    assert site_of("http://127.0.0.1:5001/courses?x=1") == "http://127.0.0.1:5001"


def test_a_vault_routed_value_is_never_written_to_a_trace() -> None:
    """The key is remembered; the secret is not."""
    move = Move(
        instruction="Fill in Password.",
        detail="",
        operations=[
            Operation("fill", Target("textbox", "Password"), value_key="password",
                      value="hunter2")
        ],
        expect=Expectation(),
        fields=[],
        actions=[],
    )

    assert steps_from(move)[0].value is None


# --- record then replay -----------------------------------------------------


def test_a_successful_run_is_recorded(replica: str, tmp_path) -> None:  # noqa: F811
    store = TraceStore(tmp_path / "t.db")
    planner = planner_for(store, site_of(replica))

    connection = drive(planner, REGISTRATION_TASK, replica)

    assert "task.completed" in connection.types()
    trace = store.find(REGISTRATION_TASK.goal, site_of(replica))
    assert trace is not None
    assert [(s.kind, s.label) for s in trace.steps] == [
        ("fill", "Student ID or Username"),
        ("fill", "Password"),
        ("click", "Sign In"),
        ("click", "Close"),
        ("click", "Register for CS-401"),
    ]
    # No credential reached the database.
    assert all(step.value is None for step in trace.steps)


def test_a_replay_costs_no_model_calls(replica: str, tmp_path) -> None:  # noqa: F811
    store = TraceStore(tmp_path / "t.db")
    drive(planner_for(store, site_of(replica)), REGISTRATION_TASK, replica)

    # Second time round, with a provider that would raise if it were consulted.
    second = planner_for(store, site_of(replica), script=[])
    connection = drive(second, REGISTRATION_TASK, replica)

    completed = connection.payload_of("task.completed")
    assert completed["llm_calls"] == 0
    assert completed["replayed"] is True
    assert completed["steps_taken"] == 5
    assert second.provider.prompts == []
    assert second.replayed_steps == 5


def test_replay_resolves_by_label_not_by_the_recorded_id(replica: str, tmp_path) -> None:  # noqa: F811
    """Ids shift between loads; the trace must not depend on them."""
    store = TraceStore(tmp_path / "t.db")
    drive(planner_for(store, site_of(replica)), REGISTRATION_TASK, replica)

    trace = store.find(REGISTRATION_TASK.goal, site_of(replica))

    serialised = str([vars(step) for step in trace.steps])
    assert "element_id" not in serialised
    assert all(step.role and step.label for step in trace.steps)


# --- when the page has moved on ---------------------------------------------


def test_a_trace_that_no_longer_fits_falls_back_and_is_corrected(
    replica: str, tmp_path  # noqa: F811
) -> None:
    """A stale trace names something that isn't there any more."""
    store = TraceStore(tmp_path / "t.db")
    site = site_of(replica)
    stale = [
        TraceStep("click", "button", "Accept All Cookies"),  # gone from the page
        TraceStep("click", "button", "Sign In"),
    ]
    store.save(REGISTRATION_TASK.goal, site, stale)

    planner = planner_for(store, site)
    connection = drive(planner, REGISTRATION_TASK, replica)

    # It noticed, stopped trusting the trace, and finished with the planner.
    assert planner.fell_back_after == 1
    assert "task.completed" in connection.types(), connection.sent[-1]
    assert connection.payload_of("task.completed")["llm_calls"] > 0

    # And the trace now describes what actually worked.
    corrected = store.find(REGISTRATION_TASK.goal, site)
    assert [s.label for s in corrected.steps] == [
        "Student ID or Username",
        "Password",
        "Sign In",
        "Close",
        "Register for CS-401",
    ]
    assert "Accept All Cookies" not in [s.label for s in corrected.steps]


def test_the_corrected_trace_replays_cleanly_afterwards(
    replica: str, tmp_path  # noqa: F811
) -> None:
    """The self-correction has to actually stick."""
    store = TraceStore(tmp_path / "t.db")
    site = site_of(replica)
    store.save(REGISTRATION_TASK.goal, site,
               [TraceStep("click", "button", "Accept All Cookies")])

    drive(planner_for(store, site), REGISTRATION_TASK, replica)
    third = planner_for(store, site, script=[])
    connection = drive(third, REGISTRATION_TASK, replica)

    assert connection.payload_of("task.completed")["llm_calls"] == 0
    assert third.replayed_steps == 5


def test_replay_still_verifies_every_action(replica: str, tmp_path) -> None:  # noqa: F811
    """A replayed step is not trusted any more than a planned one."""
    store = TraceStore(tmp_path / "t.db")
    site = site_of(replica)
    # "Home" is href="#". The first click changes the URL (it gains the
    # fragment) and verifies; the second changes nothing at all, and that is
    # the one replay has to catch rather than wave through.
    store.save(
        REGISTRATION_TASK.goal,
        site,
        [TraceStep("click", "link", "Home"), TraceStep("click", "link", "Home")],
    )

    planner = planner_for(store, site)
    drive(planner, REGISTRATION_TASK, replica)

    assert planner.fell_back_after == 2, "the second, inert click was not caught"
    assert "did not change" in (planner.fallback_reason or "")


def test_no_trace_means_ordinary_planning(replica: str, tmp_path) -> None:  # noqa: F811
    store = TraceStore(tmp_path / "t.db")
    planner = planner_for(store, site_of(replica))

    assert planner.had_trace is False

    connection = drive(planner, REGISTRATION_TASK, replica)
    assert connection.payload_of("task.completed")["llm_calls"] == 5
    assert connection.payload_of("task.completed")["replayed"] is False
