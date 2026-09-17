"""Both planners must recover identically, because it is the same code.

The planners differ only in how the next Move is chosen. Presenting, acting,
verifying, retrying and giving up live in loop.py and are shared. These tests
inject the same failure into each and assert the observable behaviour matches
message for message.
"""

import asyncio

import pytest
from playwright.async_api import async_playwright

from backend.orchestrator import loop as loop_module
from backend.orchestrator.llm import Action
from backend.orchestrator.llm_loop import LLMPlanner
from backend.orchestrator.loop import Move, Task, run_task
from backend.orchestrator.plan import (
    About,
    Expectation,
    HardcodedPlanner,
    Operation,
    PlanStep,
    Target,
)
from backend.orchestrator.test_orchestrator import replica  # noqa: F401
from backend.orchestrator.test_verification import FakeConnection

TASK = Task(
    goal="Register for the course CS-401.",
    estimated_steps=4,
    success=Expectation(url_contains="/register", title_contains="Registration Confirmed"),
    about=About(),
)

# Both planners are pointed at the same element: a nav link with href="#",
# which is clickable but changes nothing. Verification must catch it.
DEAD_LINK = ("link", "Home")


class OneNoteProvider:
    """A model that always answers with the same element."""

    def __init__(self, role: str, label: str, kind: str = "click") -> None:
        self.role, self.label, self.kind = role, label, kind
        self.calls = 0

    async def decide(self, system_prompt, page, goal, feedback=None, history=None):
        self.calls += 1
        for line in page.splitlines():
            number, _, rest = line.partition(". ")
            if rest.startswith(f"{self.role} '{self.label}'"):
                return Action(
                    action=self.kind,
                    element_id=int(number),
                    value=None,
                    reasoning="always this one",
                )
        raise AssertionError(f"{self.label!r} not on the page")


def hardcoded_planner_for(role: str, label: str) -> HardcodedPlanner:
    step = PlanStep(
        instruction=f"Click {label}.",
        detail="",
        operations=[Operation("click", Target(role, label))],
        expect=Expectation(),
        actions=[],
    )
    # Enough repeats that the planner never runs out before the shared
    # give-up rule fires. Clicking an href="#" link changes the URL once (it
    # gains the fragment), so the first click passes and later ones do not.
    return HardcodedPlanner([step] * 6)


def drive(planner, start_url: str) -> FakeConnection:
    async def go() -> FakeConnection:
        connection = FakeConnection()
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await run_task(page, connection, planner, TASK, start_url)
            finally:
                await browser.close()
        return connection

    return asyncio.run(go())


@pytest.fixture(scope="module")
def both(replica: str):  # noqa: F811
    """Run the identical dead-link failure through each planner."""
    role, label = DEAD_LINK
    return {
        "hardcoded": drive(hardcoded_planner_for(role, label), replica),
        "llm": drive(LLMPlanner(OneNoteProvider(role, label), TASK), replica),
    }


def test_both_planners_give_up_the_same_way(both) -> None:
    for name, connection in both.items():
        assert "help.requested" in connection.types(), name
        assert "task.completed" not in connection.types(), name


def test_both_reach_the_same_terminal_state(both) -> None:
    for name, connection in both.items():
        states = [s for n, s in connection.sent if n == "state.changed"]
        assert states[-1] == {"state": "stuck"}, name


def test_both_emit_the_same_message_sequence(both) -> None:
    hardcoded = both["hardcoded"].types()
    llm = both["llm"].types()
    assert hardcoded == llm, f"\nhardcoded: {hardcoded}\nllm:       {llm}"


def test_both_report_the_same_verification_failure(both) -> None:
    reasons = {
        name: connection.payload_of("help.requested")["reason"]
        for name, connection in both.items()
    }
    for name, reason in reasons.items():
        assert "did not change at all" in reason, (name, reason)


def test_both_take_the_same_number_of_steps_before_giving_up(both) -> None:
    counts = {name: len(c.of("step.presented")) for name, c in both.items()}
    assert len(set(counts.values())) == 1, counts


def test_the_retry_is_the_shared_code_path(monkeypatch, replica: str) -> None:  # noqa: F811
    """Both planners must drive attempt_move with strategy 0 then strategy 1."""
    seen: dict[str, list[int]] = {"hardcoded": [], "llm": []}
    real = loop_module.attempt_move

    role, label = DEAD_LINK
    for name, planner in (
        ("hardcoded", hardcoded_planner_for(role, label)),
        ("llm", LLMPlanner(OneNoteProvider(role, label), TASK)),
    ):
        async def spy(page, move, input_values, strategy, before, _name=name):
            seen[_name].append(strategy)
            return await real(page, move, input_values, strategy, before)

        monkeypatch.setattr(loop_module, "attempt_move", spy)
        drive(planner, replica)

    # The same strategies, in the same order, for both planners.
    assert seen["hardcoded"] == seen["llm"], seen

    strategies = seen["hardcoded"]
    assert 1 in strategies, f"the fallback strategy never ran: {strategies}"
    # A retry only ever follows a first attempt, never starts one.
    for index, strategy in enumerate(strategies):
        if strategy == 1:
            assert strategies[index - 1] == 0, strategies


def test_planners_differ_only_in_what_they_choose(both) -> None:
    """Sanity: the shared path is shared, but the planners are distinct objects."""
    hardcoded_steps = both["hardcoded"].of("step.presented")
    llm_steps = both["llm"].of("step.presented")

    assert hardcoded_steps[0]["instruction"] == "Click Home."
    assert llm_steps[0]["instruction"] == "Click Home."
    # The LLM planner carries its reasoning through; the hardcoded one has none.
    assert llm_steps[0]["detail"] == "always this one"
    assert hardcoded_steps[0]["detail"] == ""
