"""The final-step rule (2026-10-16, CLAUDE.md).

An action that pays, books, registers or changes a record happens only on a
replica, and only after a final screen that says what will happen, shows the
key details as the page states them, and has two answers, do it and don't,
neither the default. "Don't" ends the task with nothing changed. Enforced by
the loop, whichever planner asks — so these drive the real loop in real
Chromium, on the registration replica and on pages that are not ours.
"""

from types import SimpleNamespace
from urllib.parse import quote

from playwright.async_api import async_playwright

from backend.orchestrator import voice
from backend.orchestrator.loop import (
    Move,
    Task,
    final_screen,
    on_replica,
    read_final,
    run_task,
    would_change,
)
from backend.orchestrator.plan import (
    REGISTRATION_PLAN,
    About,
    Expectation,
    FinalRead,
    HardcodedPlanner,
    Operation,
    PlanStep,
    Target,
)
from backend.orchestrator.test_asking import ScriptedConnection
from backend.orchestrator.test_checklist import run
from backend.orchestrator.test_orchestrator import replica  # noqa: F401
from backend.perception.content import Content, Pair, Row, Table
from shared.schema import Detail


def press(label: str, **extra) -> Move:
    return Move(instruction="i", detail="", operations=[Operation("click", Target("button", label))],
                expect=Expectation(), fields=[], actions=voice.actions("Go"), **extra)


class Unmarked:
    """A planner that does not mark its own changes: the model, replay."""


class Marked:
    marks_changes = True


# --- the parts ---------------------------------------------------------------


def test_only_this_machine_is_a_replica() -> None:
    assert on_replica("http://127.0.0.1:5000/courses")
    assert on_replica("http://localhost:5200/")
    assert not on_replica("https://pakrail.gov.pk/train-timings")
    assert not on_replica("data:text/html,<p>hi</p>")
    assert not on_replica("http://127.0.0.1.example.com/")


def test_what_counts_as_a_change() -> None:
    # Marked by the planner: whatever its words.
    assert would_change(press("Next", changes=True), Marked())
    # A planner that marks its own: only what it marks.
    assert not would_change(press("Book train 13UP"), Marked())
    # One that does not: a press whose words say so.
    for label in ("Register for CS-401", "Confirm Booking", "Pay now", "Submit", "Book it"):
        assert would_change(press(label), Unmarked()), label
    for label in ("Search", "Check Bill", "Accept all cookies", "Sign In", "Close"):
        assert not would_change(press(label), Unmarked()), label
    # A question changes nothing.
    assert not would_change(press("Book", question=True), Unmarked())


def test_a_detail_is_read_as_the_page_states_it_or_not_at_all() -> None:
    content = Content(
        pairs=[Pair("Fare", "Rs 3,250")],
        tables=[Table(headers=("Subj", "Crse", "Title"), rows=(
            Row(cells=(("Subj", "CS"), ("Crse", "220"), ("Title", "Data Structures"))),
            Row(cells=(("Subj", "CS"), ("Crse", "401"), ("Title", "Advanced Widget Design"))),
        ))])
    assert read_final(content, FinalRead("Fare", "Fare")) == "Rs 3,250"
    assert read_final(content, FinalRead("Course", "Title",
                                         row=(("Subj", "CS"), ("Crse", "401")))) == \
        "Advanced Widget Design"
    assert read_final(content, FinalRead("Due", "Due date")) is None
    assert read_final(content, FinalRead("What", fixed="Pay")) == "Pay"
    assert read_final(content, FinalRead("Fare", "Fare", plain=str.upper)) == "RS 3,250"


def test_a_final_screen_with_nothing_read_names_the_button() -> None:
    shown, details = final_screen(press("Register for CS-401", changes=True), Content())
    assert shown.instruction == voice.final_press("Register for CS-401")
    assert shown.detail == voice.FINAL_WAITS
    assert details == [Detail(label=voice.WHAT_I_PRESS, value="Register for CS-401")]
    assert [(a.id, a.label) for a in shown.actions] == [
        ("confirm", voice.DO_IT), (voice.DECLINE_ID, voice.DONT_DO_IT)]
    assert final_screen(press("Pay", changes=True, final=(FinalRead("Fare", "Fare"),)),
                        Content()) is None


# --- the rule, in the real loop -------------------------------------------------------


def drive(start_url: str, steps: list[PlanStep], answers=None, task=None,
          auto: bool = False) -> tuple[ScriptedConnection, SimpleNamespace]:
    async def inner():
        connection = ScriptedConnection(answers)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await run_task(page, connection, HardcodedPlanner(steps),
                               task or Task(goal="g", estimated_steps=len(steps), about=About()),
                               start_url, auto=auto)
                after = SimpleNamespace(title=await page.title(),
                                        clicked=await page.evaluate("window.__clicked || 0"))
            finally:
                await browser.close()
        return connection, after

    return run(inner())


SIGN_IN = [("confirm", {"username": "student", "password": "pw"})]


def test_registering_waits_for_its_final_screen_and_do_it(replica: str) -> None:  # noqa: F811
    done, page = drive(replica, REGISTRATION_PLAN, SIGN_IN + [("confirm", {}), ("confirm", {})])

    # The course's own row on the portal's list (2026-10-16, item 4).
    final = done.of("step.presented")[-1]
    assert final["instruction"] == voice.final_register("CS-401")
    assert final["final"] == [
        {"label": "Course", "value": "CS-401"},
        {"label": "Title", "value": "Advanced Widget Design"},
        {"label": "Days", "value": "MWF"},
        {"label": "Time", "value": "10:00-10:50"},
        {"label": "Teacher", "value": "Dr. Aslam"},
        {"label": "Room", "value": "SCI 214"},
        {"label": "Credit hours", "value": "3"},
    ]
    assert [(a["id"], a["label"]) for a in final["actions"]] == [
        ("confirm", voice.REGISTER_IT), (voice.DECLINE_ID, voice.DONT_REGISTER)]
    assert page.title.startswith("Registration Confirmed")


def test_dont_ends_the_task_and_changes_nothing(replica: str) -> None:  # noqa: F811
    done, page = drive(replica, REGISTRATION_PLAN,
                       SIGN_IN + [("confirm", {}), (voice.DECLINE_ID, {})])

    assert done.of("task.failed")[0]["reason"] == voice.NOTHING_CHANGED
    assert "task.completed" not in done.types()
    assert not page.title.startswith("Registration Confirmed")


def test_a_change_is_never_on_the_checklist(replica: str) -> None:  # noqa: F811
    """Marked safe by mistake, it still waits for its final screen."""
    *rest, register = REGISTRATION_PLAN
    from dataclasses import replace

    steps = [*rest, replace(register, safe=True, doing="Registering")]
    done, page = drive(replica, steps, SIGN_IN + [(voice.DECLINE_ID, {})], auto=True)

    assert done.of("step.presented")[-1]["final"] is not None
    assert done.of("step.presented")[-1]["requires_confirmation"] is True
    assert not page.title.startswith("Registration Confirmed")


PAGE = ("data:text/html," + quote(
    "<title>Not ours</title><p>Fare <b>Rs 9</b></p>"
    "<button onclick='window.__clicked=(window.__clicked||0)+1'>Pay now</button>"))


def test_on_a_site_that_is_not_ours_paying_is_never_pressed_by_simba() -> None:
    """Until 2026-11-13 no change was made on a live site at all. By the
    advisor's direction (G, F) a change there waits for its final screen, and
    a press that pays is then handed to the person: SIMBA never presses Pay.
    `test_handover.py` has the rest of the new rule."""
    step = PlanStep(instruction="Pay.", detail="", actions=voice.actions("Pay"),
                    operations=[Operation("click", Target("button", "Pay now"))],
                    expect=Expectation(), changes=True)

    done, page = drive(PAGE, [step], [("confirm", {})])

    assert done.of("step.presented")[-1]["final"] is not None  # asked first
    assert page.clicked == 0


def test_a_detail_the_page_does_not_state_means_nothing_is_done(
    replica: str,  # noqa: F811
) -> None:
    *rest, register = REGISTRATION_PLAN
    from dataclasses import replace

    steps = [*rest, replace(register, final=(FinalRead("Fare", "Fare"),))]
    done, page = drive(replica, steps, SIGN_IN + [("confirm", {})])

    assert done.of("help.requested")[0]["reason"] == voice.NO_FINAL_SCREEN
    assert not page.title.startswith("Registration Confirmed")
