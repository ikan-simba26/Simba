"""The LLM-planned loop, driven by a scripted provider instead of a real model.

These run the whole real loop — real browser, real replica, real verification
— with only the model replaced, so they cover the parts a live run cannot be
relied on to exercise: a malformed answer, an id that does not exist, and the
refusal to let a model invent a password.
"""

import asyncio
import re

from playwright.async_api import async_playwright

from backend.orchestrator.llm import Action, LLMError
from backend.orchestrator.llm_loop import REGISTRATION_TASK, LLMPlanner, render_page
from backend.orchestrator.loop import Task, resolve_value, run_task
from backend.orchestrator.plan import Expectation, Operation, Target
from backend.orchestrator.test_orchestrator import replica  # noqa: F401
from backend.orchestrator.test_verification import FakeConnection
from backend.perception.serializer import Element

CREDENTIALS = {"username": "raham", "password": "hunter2"}


def element(**kwargs) -> Element:
    base = dict(id=1, role="button", label="Sign In", type="click", tag="button",
                input_type=None, name=None)
    return Element(**{**base, **kwargs})


class ScriptedProvider:
    """Replays a list of Actions or exceptions, recording the prompts it saw."""

    def __init__(self, script: list) -> None:
        self.script = list(script)
        self.prompts: list[tuple[str, str | None]] = []
        self.histories: list[list[str]] = []

    async def decide(self, system_prompt, page, goal, feedback=None, history=None):
        self.prompts.append((page, feedback))
        self.histories.append(list(history or []))
        result = self.script.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class LabelDrivenProvider:
    """Reads the rendered page and picks the id whose label was scripted.

    Closer to a real model than fixed ids: it only ever answers with an id it
    actually saw in the list it was given.
    """

    LINE = re.compile(r"^(\d+)\. (\S+) '(.*?)'")

    def __init__(self, script: list[tuple[str, str]]) -> None:
        self.script = list(script)
        self.prompts: list[tuple[str, str | None]] = []
        self.histories: list[list[str]] = []

    async def decide(self, system_prompt, page, goal, feedback=None, history=None):
        self.prompts.append((page, feedback))
        self.histories.append(list(history or []))
        kind, label = self.script.pop(0)

        for line in page.splitlines():
            match = self.LINE.match(line)
            if match and match.group(3) == label:
                return Action(
                    action=kind,
                    element_id=int(match.group(1)),
                    value=None,
                    reasoning=f"{kind} {label}",
                )

        raise LLMError(f"{label!r} is not on this page")


def drive(provider, task: Task, start_url: str) -> FakeConnection:
    async def go() -> FakeConnection:
        connection = FakeConnection()
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await run_task(page, connection, LLMPlanner(provider, task), task, start_url)
            finally:
                await browser.close()
        return connection

    return asyncio.run(go())


# --- the page the model sees ------------------------------------------------


def test_rendered_page_has_ids_roles_and_labels_but_no_values() -> None:
    rendered = render_page(
        [
            element(id=1, role="textbox", label="Password", tag="input", input_type="password"),
            element(id=2, role="button", label="Sign In"),
        ]
    )
    assert "1. textbox 'Password' [input type=password]" in rendered
    assert "2. button 'Sign In'" in rendered
    assert "hunter2" not in rendered


# --- retry with the error fed back ------------------------------------------


def test_nonexistent_id_is_retried_with_the_error_fed_back() -> None:
    provider = ScriptedProvider(
        [
            Action(action="click", element_id=99, reasoning="guessing"),
            Action(action="click", element_id=2, reasoning="the sign in button"),
        ]
    )
    elements = [element(id=1), element(id=2)]

    planner = LLMPlanner(provider, REGISTRATION_TASK)
    move = asyncio.run(planner.next_move(elements, [], None))

    assert move is not None
    assert move.operations[0].element_id == 2
    _, feedback = provider.prompts[1]
    assert "element_id 99 is not on the page" in feedback
    assert "Valid ids are 1 to 2" in feedback


def test_malformed_response_is_retried_with_the_error_fed_back() -> None:
    provider = ScriptedProvider(
        [
            LLMError("response did not match the action schema"),
            Action(action="click", element_id=1, reasoning="recovered"),
        ]
    )

    planner = LLMPlanner(provider, REGISTRATION_TASK)
    move = asyncio.run(planner.next_move([element(id=1)], [], None))

    assert move is not None and move.operations[0].element_id == 1
    assert "did not match the action schema" in provider.prompts[1][1]


def test_two_bad_answers_give_up_rather_than_looping() -> None:
    provider = ScriptedProvider([LLMError("bad"), LLMError("still bad")])

    planner = LLMPlanner(provider, REGISTRATION_TASK)
    move = asyncio.run(planner.next_move([element(id=1)], [], None))

    assert move is None
    assert "still bad" in planner.stuck_reason
    assert len(provider.prompts) == 2


def test_completed_actions_are_fed_back_so_the_model_cannot_repeat_itself(
    replica: str,  # noqa: F811
) -> None:
    """A live run failed by refilling the username every step: it had no memory.

    Each call must be told what is already done, in order.
    """
    provider = LabelDrivenProvider(
        [
            ("type", "Student ID or Username"),
            ("type", "Password"),
            ("click", "Sign In"),
            ("click", "Close"),
            ("click", "Register for CS-401"),
        ]
    )

    drive(provider, REGISTRATION_TASK, replica)

    assert provider.histories[0] == []
    assert len(provider.histories[1]) == 1
    assert "Student ID or Username" in provider.histories[1][0]
    assert len(provider.histories[4]) == 4
    assert "Sign In" in provider.histories[4][2]


def test_history_reaches_the_prompt_text() -> None:
    from backend.orchestrator.llm import build_user_prompt

    prompt = build_user_prompt("1. button 'Go'", "goal", None, ["type on textbox 'User' (id 3)"])

    assert "Already done, in order:" in prompt
    assert "1. type on textbox 'User' (id 3)" in prompt
    assert "Do not repeat any of the above" in prompt


def test_first_call_says_nothing_has_been_done() -> None:
    from backend.orchestrator.llm import build_user_prompt

    assert "Nothing has been done yet" in build_user_prompt("1. button 'Go'", "goal", None, [])


# --- credentials ------------------------------------------------------------


def test_vault_value_beats_whatever_the_model_wrote() -> None:
    field = element(id=1, role="textbox", label="Password", tag="input",
                    input_type="password", name="password")
    operation = Operation("fill", Target("textbox", "Password"), element_id=1,
                          value="guessed-password")

    value, refusal = resolve_value(field, operation, CREDENTIALS)

    assert value == "hunter2"
    assert refusal is None


def test_model_may_not_invent_a_password() -> None:
    field = element(id=1, role="textbox", label="Password", tag="input",
                    input_type="password", name="password")
    operation = Operation("fill", Target("textbox", "Password"), element_id=1,
                          value="invented")

    value, refusal = resolve_value(field, operation, {})

    assert value == ""
    assert "never filled from anything a planner supplied" in refusal


def test_model_value_is_used_for_an_ordinary_field() -> None:
    field = element(id=1, role="textbox", label="Search", tag="input",
                    input_type="text", name="q")
    operation = Operation("fill", Target("textbox", "Search"), element_id=1, value="CS-401")

    assert resolve_value(field, operation, {}) == ("CS-401", None)


# --- end to end against the replica -----------------------------------------


def test_a_scripted_model_completes_the_registration(replica: str) -> None:  # noqa: F811
    """A stand-in model that reads the page and picks by label, as a real one would."""
    provider = LabelDrivenProvider(
        [
            ("type", "Student ID or Username"),
            ("type", "Password"),
            ("click", "Sign In"),
            ("click", "Close"),
            ("click", "Register for CS-401"),
        ]
    )

    connection = drive(provider, REGISTRATION_TASK, replica)

    assert "help.requested" not in connection.types(), connection.sent[-1]
    completed = connection.payload_of("task.completed")
    assert "/register" in completed["summary"]
    assert completed["llm_calls"] == 5


def test_giving_up_when_the_model_cannot_answer(replica: str) -> None:  # noqa: F811
    provider = ScriptedProvider([LLMError("upstream is down"), LLMError("still down")])

    connection = drive(provider, REGISTRATION_TASK, replica)

    assert "task.completed" not in connection.types()
    assert "upstream" in connection.payload_of("help.requested")["reason"] or "still down" in (
        connection.payload_of("help.requested")["reason"]
    )
    assert [s for n, s in connection.sent if n == "state.changed"][-1] == {"state": "stuck"}


def test_goal_already_satisfied_completes_without_calling_the_model(replica: str) -> None:  # noqa: F811
    """If the page already meets the goal, no model call is made at all."""
    provider = ScriptedProvider([])
    goal = Task(goal="Be on the login page.",
                success=Expectation(title_contains="Sign In"),
                estimated_steps=1)

    connection = drive(provider, goal, replica)

    assert connection.payload_of("task.completed")["llm_calls"] == 0
    assert provider.prompts == []
