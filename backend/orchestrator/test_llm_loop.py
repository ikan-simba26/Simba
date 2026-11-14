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
from backend.orchestrator.plan import About, Expectation, Operation, Target
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


# --- searching, and icons with no words (2026-11-14) ------------------------


def _shaped(element_kwargs: dict, action: Action):
    planner = LLMPlanner(ScriptedProvider([]), REGISTRATION_TASK)
    from backend.orchestrator.llm_loop import _Choice

    return asyncio.run(planner._shape(_Choice(action=action, element=element(**element_kwargs))))


def test_typing_into_a_search_box_also_presses_enter() -> None:
    """Readings, run E (EVALUATION.md, 2026-11-13j): the search was typed seven
    times and never sent, because its button is an icon with no words."""
    for kwargs in ({"role": "searchbox", "label": "Search"},
                   {"role": "combobox", "label": "Keyword | Title | Author | ISBN | Publisher"}):
        move = _shaped({"id": 6, "tag": "input", "input_type": "text", **kwargs},
                       Action(action="type", element_id=6, value="Atomic Habits", reasoning="r"))
        kinds = [(op.kind, op.value) for op in move.operations]
        assert kinds == [("fill", "Atomic Habits"), ("press", "Enter")], kwargs


def test_typing_into_any_other_field_does_not() -> None:
    move = _shaped({"id": 3, "role": "textbox", "label": "Full name", "tag": "input",
                    "input_type": "text"},
                   Action(action="type", element_id=3, value=None, reasoning="r"))
    assert [op.kind for op in move.operations] == ["fill"]


def test_an_icon_font_character_is_not_a_name() -> None:
    rendered = render_page([element(id=7, role="button", label=""),
                            element(id=8, role="button", label=" Add to Wishlist")])
    assert "" not in rendered and "" not in rendered
    assert "7. button (no name)" in rendered.splitlines()
    assert "8. button 'Add to Wishlist'" in rendered.splitlines()
    move = _shaped({"id": 7, "role": "button", "label": ""},
                   Action(action="click", element_id=7, reasoning="r"))
    assert "" not in move.instruction
    assert move.instruction != "Click ."


# --- the trimmed list (2026-11-13) ------------------------------------------


def test_what_can_never_be_chosen_is_counted_not_listed() -> None:
    rendered = render_page([
        element(id=1, role="button", label="Close", overlay=True, dead_link=True),
        element(id=2, role="link", label="CS-401", occluded=True),
        element(id=3, role="link", label="Fees", occluded=True, dead_link=True),
        element(id=4, role="link", label="Tickets", dead_link=True),
        element(id=5, role="button", label="Search"),
    ])
    lines = rendered.splitlines()
    assert lines[0].startswith("AN OVERLAY IS COVERING THE PAGE")
    # The overlay's own close is kept even when its link goes nowhere:
    # it is how the overlay is dismissed.
    assert "1. button 'Close' [overlay]" in lines
    assert "5. button 'Search'" in lines
    for gone in ("CS-401", "Fees", "Tickets"):
        assert gone not in rendered
    assert "Not listed, since none can be used: 2 behind the overlay, 1 links that go nowhere." \
        in lines


def test_an_input_type_is_shown_only_where_the_role_does_not_say_it() -> None:
    rendered = render_page([
        element(id=1, role="textbox", label="Name", input_type="text"),
        element(id=2, role="searchbox", label="Search", input_type="search"),
        element(id=3, role="radio", label="Small", input_type="radio"),
        element(id=4, role="textbox", label="Email", input_type="email"),
        element(id=5, role="button", label="Main menu", input_type="checkbox"),
    ]).splitlines()
    assert "1. textbox 'Name'" in rendered
    assert "2. searchbox 'Search'" in rendered
    assert "3. radio 'Small'" in rendered
    assert "4. textbox 'Email' [input type=email]" in rendered
    assert "5. button 'Main menu' [input type=checkbox]" in rendered


def test_a_label_is_one_line_and_cut_when_long() -> None:
    long = "Apply for admission to the undergraduate programmes " * 3
    rendered = render_page([
        element(id=1, role="link", label="Full\xa0article\n  here"),
        element(id=2, role="link", label=long),
    ]).splitlines()
    assert "1. link 'Full article here'" in rendered
    second = next(line for line in rendered if line.startswith("2. "))
    assert second.endswith("…'") and len(second) < 100


def test_inferred_is_marked_short_and_explained_once() -> None:
    rendered = render_page([
        element(id=1, role="option", label=str(day), inferred=True, panel="2026 November")
        for day in range(1, 4)
    ])
    assert rendered.count("[inferred] means") == 1
    assert "1. option '1' [inferred]" in rendered.splitlines()
    assert "INFERRED (role worked out" not in rendered


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


def test_an_empty_answer_does_not_override_what_the_model_chose() -> None:
    """The overlay sends the step's fields as they stand, and an LLM step shows
    them empty: the model's value is not put into the box for the person to
    confirm. So pressing "Yes, do that" without typing sent an empty string,
    and on any input with a `name` it replaced the model's value — the field
    was then "filled" with nothing, and read back as nothing, successfully.

    Not observed live: the railways inputs have no `name`, so the key never
    matched. Any named input would have hit it.
    """
    field = element(id=1, role="textbox", label="Search", tag="input",
                    input_type="text", name="q")
    operation = Operation("fill", Target("textbox", "Search"), element_id=1, value="CS-401")

    assert resolve_value(field, operation, {"q": ""}) == ("CS-401", None)


def test_an_answer_that_says_something_still_wins() -> None:
    """The person's own answer is still the authority when they gave one."""
    field = element(id=1, role="textbox", label="Search", tag="input",
                    input_type="text", name="q")
    operation = Operation("fill", Target("textbox", "Search"), element_id=1, value="CS-401")

    assert resolve_value(field, operation, {"q": "MATH-210"}) == ("MATH-210", None)


def test_an_empty_answer_with_nothing_to_fall_back_on_is_still_empty() -> None:
    field = element(id=1, role="textbox", label="Search", tag="input",
                    input_type="text", name="q")
    operation = Operation("fill", Target("textbox", "Search"), element_id=1)

    assert resolve_value(field, operation, {"q": ""}) == ("", None)


def test_an_empty_password_is_refused_rather_than_typed_as_nothing() -> None:
    """A password has no planner fallback, so an empty answer is the refusal
    path, not a field quietly filled with nothing."""
    field = element(id=1, role="textbox", label="Password", tag="input",
                    input_type="password", name="password")
    operation = Operation("fill", Target("textbox", "Password"), element_id=1)

    value, refusal = resolve_value(field, operation, {"password": ""})

    assert value == ""
    assert "never filled from anything a planner supplied" in refusal


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
                estimated_steps=1,
                about=About())

    connection = drive(provider, goal, replica)

    assert connection.payload_of("task.completed")["llm_calls"] == 0
    assert provider.prompts == []
