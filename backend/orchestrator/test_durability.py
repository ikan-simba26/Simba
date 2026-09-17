"""Durable verification, and the keyboard.

Reading a field back the instant after typing proves the keystrokes arrived.
It does not prove the value is still there when the step that depends on it
runs, and on a real page those are different questions: a component-framework
combobox clears its own input on blur unless a choice was committed. A field
can verify correctly and be empty two seconds later.

A lapse ends the run. Handing it back to the planner as a setback instead was
tried on 2026-09-09 and reverted the same day: the live LLM run was told its
date was the wrong month, re-planned, searched anyway, and reported
`task.completed` on a timetable for a date nobody asked for. A run that
stopped honestly became one that finished wrongly.

The replicas do not behave that way, so the blur handler is attached here, in
the test, to a page that is otherwise untouched. The replicas stay as they
are — they are evidence, and editing them to suit the loop would spend the
evidence (CLAUDE.md, and the standing instruction not to fix a replica to
suit perception).
"""

import asyncio

from playwright.async_api import async_playwright

from backend.orchestrator.loop import (
    Connection,
    Move,
    Task,
    durability_failure,
    record_fills,
    run_task,
)
from backend.orchestrator.plan import (
    About,
    Expectation,
    FieldValue,
    HardcodedPlanner,
    Operation,
    PlanStep,
    Target,
)
from backend.orchestrator.test_orchestrator import REPLICA_URL, replica  # noqa: F401
from backend.orchestrator.test_verification import FakeConnection
from shared.schema import StepAction, StepField

CONFIRM = [StepAction(id="confirm", label="Go", kind="primary")]
USERNAME = Target("textbox", "Student ID or Username")

FILL_USERNAME = Move(
    instruction="Type the username.",
    detail="",
    operations=[Operation("fill", USERNAME, "username")],
    expect=Expectation(),
    fields=[],
    actions=[],
)

# Element UI's own behaviour, in one line: the input clears itself when it
# loses focus unless a choice was committed from the dropdown. Attached on
# DOMContentLoaded because an init script runs before the document exists.
CLEAR_ON_BLUR = """
    document.addEventListener('DOMContentLoaded', function () {
        var field = document.getElementById('username');
        if (field) {
            field.addEventListener('blur', function () { this.value = ''; });
        }
    });
"""


def on_login(body, *, script: str | None = None):
    """Run `body(page)` against the replica's login page. Returns its result."""

    async def go():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await page.goto(REPLICA_URL + "/")
                if script:
                    await page.evaluate(script)
                return await body(page)
            finally:
                await browser.close()

    return asyncio.run(go())


# --- what was typed is remembered from the page, not from the plan ----------


def test_a_fill_is_recorded_as_what_the_field_actually_holds(replica: str) -> None:  # noqa: F811
    async def body(page):
        await page.fill("#username", "raham")
        return await record_fills(page, FILL_USERNAME)

    recorded = on_login(body)

    assert len(recorded) == 1
    assert recorded[0].label == "Student ID or Username"
    assert recorded[0].value == "raham"


def test_a_password_is_never_held_in_run_state(replica: str) -> None:  # noqa: F811
    """Not even to check it later. The vault rule has no verification exemption."""
    move = Move(
        instruction="Type the password.",
        detail="",
        operations=[Operation("fill", Target("textbox", "Password"), "password")],
        expect=Expectation(),
        fields=[],
        actions=[],
    )

    async def body(page):
        await page.fill("#password", "hunter2")
        return await record_fills(page, move)

    assert on_login(body, script=None) == []


# --- the check itself -------------------------------------------------------


def test_a_value_that_is_still_there_is_not_a_failure(replica: str) -> None:  # noqa: F811
    async def body(page):
        await page.fill("#username", "raham")
        recorded = await record_fills(page, FILL_USERNAME)
        return await durability_failure(page, recorded)

    assert on_login(body) is None


def test_a_value_that_vanished_is_caught_at_the_next_look(replica: str) -> None:  # noqa: F811
    """The case read-back cannot see, because read-back already passed."""

    async def body(page):
        await page.fill("#username", "raham")
        recorded = await record_fills(page, FILL_USERNAME)
        # The page takes it back, the way the live railways select does.
        await page.evaluate("document.getElementById('username').value = ''")
        return await durability_failure(page, recorded)

    failure = on_login(body)

    assert failure is not None
    assert "no longer holds" in failure
    assert "'raham'" in failure and "''" in failure


def test_a_field_that_left_with_the_page_is_not_a_failure(replica: str) -> None:  # noqa: F811
    """Navigation is the page-level check's business, not this one's."""

    async def body(page):
        await page.fill("#username", "raham")
        recorded = await record_fills(page, FILL_USERNAME)
        await page.goto(REPLICA_URL + "/help")
        return await durability_failure(page, recorded)

    assert on_login(body) is None


def test_nothing_recorded_means_nothing_to_check(replica: str) -> None:  # noqa: F811
    assert on_login(lambda page: durability_failure(page, [])) is None


# --- a value the page reformatted into the one the task declared ------------
#
# The 2026-09-17 live LLM run typed `2026-10-15` into the departure date,
# picked the 15th of October from the calendar, and the picker wrote the field
# back as `15-10-2026` — the right date, in the page's own format. The check
# compared that with what was typed, saw a different string, and ended a run
# whose form was entirely correct (EVALUATION.md, 2026-09-17b).
#
# The fix accepts a changed value only when it is exactly the value the task
# declared for that field in `Task.about.holds`. Anywhere else the check is as
# strict as it was, false stops included. The replica's username field stands
# in for the date: the page upper-cases it, the way the picker reformats.

UPPER_CASE_IT = "document.getElementById('username').value = 'RAHAM'"
DECLARED = (FieldValue("Student ID or Username", "RAHAM"),)


def typed_then(page_change: str, holds=()):
    async def body(page):
        await page.fill("#username", "raham")
        recorded = await record_fills(page, FILL_USERNAME)
        await page.evaluate(page_change)
        return await durability_failure(page, recorded, holds)

    return body


def test_a_reformat_into_the_declared_value_is_not_a_lapse(replica: str) -> None:  # noqa: F811
    assert on_login(typed_then(UPPER_CASE_IT, DECLARED)) is None


def test_a_change_into_anything_else_is_still_a_lapse(replica: str) -> None:  # noqa: F811
    """Declared, but not what the field now holds: the check is not loosened."""
    failure = on_login(
        typed_then("document.getElementById('username').value = 'someone'", DECLARED)
    )
    assert failure is not None and "'someone'" in failure


def test_a_field_emptied_is_still_a_lapse_even_when_declared(replica: str) -> None:  # noqa: F811
    failure = on_login(typed_then("document.getElementById('username').value = ''", DECLARED))
    assert failure is not None and "no longer holds" in failure


def test_an_undeclared_field_is_as_strict_as_before(replica: str) -> None:  # noqa: F811
    """The limit of the fix, pinned down.

    With nothing declared, a reformat reads as a lapse exactly as it did on
    2026-09-17. This is the situation the LLM planner is in on any field its
    task did not name — see DECISIONS.md.
    """
    failure = on_login(typed_then(UPPER_CASE_IT))
    assert failure is not None and "'RAHAM'" in failure


def test_a_value_declared_for_another_field_does_not_count(replica: str) -> None:  # noqa: F811
    failure = on_login(typed_then(UPPER_CASE_IT, (FieldValue("Password", "RAHAM"),)))
    assert failure is not None


def test_the_check_keeps_watching_after_accepting_a_reformat(replica: str) -> None:  # noqa: F811
    """Accepting `RAHAM` once must not stop the field being watched."""

    async def body(page):
        await page.fill("#username", "raham")
        recorded = await record_fills(page, FILL_USERNAME)
        await page.evaluate(UPPER_CASE_IT)
        first = await durability_failure(page, recorded, DECLARED)
        await page.evaluate("document.getElementById('username').value = ''")
        second = await durability_failure(page, recorded, DECLARED)
        return first, second

    first, second = on_login(body)
    assert first is None
    assert second is not None


# --- and in the loop --------------------------------------------------------


def drive(plan: list[PlanStep], task: Task, script: str | None = None) -> FakeConnection:
    async def go() -> FakeConnection:
        connection = FakeConnection()
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            if script:
                await page.add_init_script(script)
            try:
                await run_task(
                    page, connection, HardcodedPlanner(plan), task, REPLICA_URL + "/"
                )
            finally:
                await browser.close()
        return connection

    return asyncio.run(go())


TWO_FILLS = [
    PlanStep(
        instruction="Type your username.",
        detail="",
        fields=[StepField(id="username", label="Username", type="text", value="")],
        actions=CONFIRM,
        operations=[Operation("fill", USERNAME, "username")],
        expect=Expectation(),
    ),
    PlanStep(
        instruction="Type your password.",
        detail="",
        fields=[StepField(id="password", label="Password", type="password", value="")],
        actions=CONFIRM,
        operations=[Operation("fill", Target("textbox", "Password"), "password")],
        expect=Expectation(),
    ),
    PlanStep(
        instruction="Sign in.",
        detail="",
        actions=CONFIRM,
        operations=[Operation("click", Target("button", "Sign In"))],
        expect=Expectation(url_contains="/courses"),
    ),
]

SIGN_IN = Task(goal="Sign in.", estimated_steps=3,
               success=Expectation(url_contains="/courses"), about=About())


def test_the_loop_notices_a_field_that_emptied_itself(replica: str) -> None:  # noqa: F811
    """The live-site failure, reproduced where it can be asserted on.

    Step one types the username and verifies it by reading it back — which
    passes, because at that instant the value is genuinely there. Step two
    moves to the password field, the username blurs, and the page takes the
    value back. Nothing before durable verification was capable of noticing.

    The run ends here. Handing it to the planner as a setback instead was
    tried on 2026-09-09 and reverted the same day — see the module docstring
    and EVALUATION.md case 6.
    """
    connection = drive(TWO_FILLS, SIGN_IN, script=CLEAR_ON_BLUR)

    help_requested = connection.of("help.requested")
    assert help_requested, connection.types()
    reason = help_requested[0]["reason"]
    assert "Student ID or Username" in reason
    assert "no longer holds" in reason
    assert not connection.of("task.completed"), (
        "the run finished on a form the page had emptied"
    )


UPPER_CASE_ON_BLUR = """
    document.addEventListener('DOMContentLoaded', function () {
        var field = document.getElementById('username');
        if (field) {
            field.addEventListener('blur', function () {
                this.value = this.value.toUpperCase();
            });
        }
    });
"""

# Two fills and no navigation, so the username field is still on the final
# page for the declared value to be checked there.
TYPE_BOTH = TWO_FILLS[:2]


def test_the_loop_finishes_when_the_page_reformats_into_the_declared_value(
    replica: str,  # noqa: F811
) -> None:
    """The 2026-09-17 false stop, through the whole loop, now completing."""
    task = Task(goal="Type both.", estimated_steps=2,
                about=About(holds=(FieldValue("Student ID or Username", "RAHAM"),)))

    connection = drive(TYPE_BOTH, task, script=UPPER_CASE_ON_BLUR)

    assert not connection.of("help.requested"), connection.of("help.requested")
    assert connection.of("task.completed")


def test_the_same_reformat_still_stops_a_task_that_declared_nothing(
    replica: str,  # noqa: F811
) -> None:
    """The control, and the limit: undeclared, the reformat is a lapse."""
    task = Task(goal="Type both.", estimated_steps=2, about=About())

    connection = drive(TYPE_BOTH, task, script=UPPER_CASE_ON_BLUR)

    help_requested = connection.of("help.requested")
    assert help_requested and "no longer holds" in help_requested[0]["reason"]


def test_a_lapse_is_never_absorbed_in_silence(replica: str) -> None:  # noqa: F811
    """Whatever else happens, the person is told what went wrong.

    The reason travels on `help.requested` rather than `step.failed`, because
    the run is over — two messages about one moment would be one too many,
    which is the same rule a second consecutive setback follows.
    """
    connection = drive(TWO_FILLS, SIGN_IN, script=CLEAR_ON_BLUR)

    assert not connection.of("step.failed"), connection.types()
    assert len(connection.of("help.requested")) == 1


def test_the_same_plan_finishes_when_the_page_behaves(replica: str) -> None:  # noqa: F811
    """The control: without the blur handler the run completes as before."""
    connection = drive(TWO_FILLS, SIGN_IN)

    assert not connection.of("help.requested"), connection.types()
    assert connection.of("task.completed")


# --- the keyboard -----------------------------------------------------------


PRESS_TO_SUBMIT = [
    PlanStep(
        instruction="Type your username.",
        detail="",
        actions=CONFIRM,
        operations=[Operation("fill", USERNAME, "username")],
        expect=Expectation(),
    ),
    PlanStep(
        instruction="Type your password and send the form.",
        detail="",
        actions=CONFIRM,
        operations=[
            Operation("fill", Target("textbox", "Password"), "password"),
            Operation("press", Target("textbox", "Password"), value="Enter"),
        ],
        expect=Expectation(url_contains="/courses"),
    ),
]


def test_a_press_reaches_the_page(replica: str) -> None:  # noqa: F811
    """Enter submits the form. No button is clicked anywhere in this plan.

    `press` exists because several real widgets have no other route through —
    a combobox whose options carry no role can still be driven by the
    keyboard — and this proves the key actually arrives.
    """
    connection = drive(PRESS_TO_SUBMIT, SIGN_IN)

    assert not connection.of("help.requested"), connection.types()
    completed = connection.of("task.completed")
    assert completed and "/courses" in completed[0]["summary"]


def test_a_move_of_presses_alone_still_has_to_prove_itself(replica: str) -> None:  # noqa: F811
    """A press has no read-back, so it cannot skip the page-level check.

    Escape on the username field changes nothing, and a move that verifies
    nothing must not be allowed to report success.
    """
    plan = [
        PlanStep(
            instruction="Press escape, which does nothing here.",
            detail="",
            actions=CONFIRM,
            operations=[Operation("press", USERNAME, value="Escape")],
            expect=Expectation(),
        )
    ]

    connection = drive(plan, Task(goal="Press escape.", estimated_steps=1,
                                  success=Expectation(url_contains="/courses"),
                                  about=About()))

    assert connection.of("help.requested"), connection.types()


def test_the_caption_says_what_a_key_does_not_what_it_is_called() -> None:
    """The trust panel is where someone decides to allow this."""
    from backend.orchestrator.loop import caption_for

    move = Move(
        instruction="Choose a station.",
        detail="",
        operations=[Operation("press", Target("textbox", "From"), value="ArrowDown")],
        expect=Expectation(),
        fields=[],
        actions=[],
    )

    assert caption_for(move) == "I'm about to move down the list on From."


# --- a skipped step is not a silent one -------------------------------------


SKIPPED_STEP = [
    PlanStep(
        instruction="Click something that isn't there.",
        detail="",
        actions=CONFIRM,
        operations=[Operation("click", Target("button", "No Such Button"))],
        expect=Expectation(),
    ),
    PlanStep(
        instruction="Type your username.",
        detail="",
        actions=CONFIRM,
        operations=[Operation("fill", USERNAME, "username")],
        expect=Expectation(),
    ),
]

TWO_STEPS = Task(goal="Two steps, the first impossible.", estimated_steps=2, about=About())


def test_a_step_that_failed_and_was_skipped_says_so(replica: str) -> None:  # noqa: F811
    """The regression that cost a day.

    The loop absorbs a first failure — it tells the planner and moves on — and
    for a long time it told the frontend nothing. `HardcodedPlanner` ignores
    setbacks, so it served the next step, and the emitted trace was
    `step.presented(1)`, `step.presented(2)`, `task.completed`: byte for byte
    what a run where both steps worked looks like. The first live railways run
    was read that way for a day.
    """
    connection = drive(SKIPPED_STEP, TWO_STEPS)

    failures = connection.of("step.failed")
    assert failures, connection.types()

    failure = failures[0]
    assert failure["step_index"] == 1
    # Named in the words the user was shown, not an internal target.
    assert failure["instruction"] == "Click something that isn't there."
    assert "could not find 'No Such Button'" in failure["reason"]
    assert failure["strategies_tried"] == 2


def test_the_skipped_step_is_reported_before_the_next_one_is_presented(
    replica: str,  # noqa: F811
) -> None:
    """Order matters: the notice is about the step that just went by.

    Arriving after the next `step.presented` would attach it to the wrong step
    in anything reading the stream in order.
    """
    connection = drive(SKIPPED_STEP, TWO_STEPS)

    types = connection.types()
    assert types.count("step.presented") == 2
    first_presented = types.index("step.presented")
    failed_at = types.index("step.failed")
    second_presented = types.index("step.presented", first_presented + 1)

    assert first_presented < failed_at < second_presented, types


def test_a_run_where_nothing_fails_says_nothing(replica: str) -> None:  # noqa: F811
    """Quiet, not chatty. The control for the two tests above."""
    connection = drive(TWO_FILLS, SIGN_IN)

    assert not connection.of("step.failed"), connection.types()
    assert connection.of("task.completed")


def test_giving_up_does_not_also_report_a_skipped_step(replica: str) -> None:  # noqa: F811
    """The second consecutive failure ends the run, and `help.requested`
    already carries the reason. Two messages about one moment would be one
    message too many."""
    plan = SKIPPED_STEP[:1] + [
        PlanStep(
            instruction="Click something else that isn't there.",
            detail="",
            actions=CONFIRM,
            operations=[Operation("click", Target("button", "Nor This One"))],
            expect=Expectation(),
        )
    ]

    connection = drive(plan, TWO_STEPS)

    assert len(connection.of("step.failed")) == 1, connection.types()
    assert connection.of("help.requested")
