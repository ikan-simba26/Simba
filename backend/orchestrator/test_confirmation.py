"""A change is "done" only when the site confirms it (2026-10-16).

Registering for a course changes a record. The closing screen now quotes the
portal's own confirmation, and says "done" only when that confirmation is on
the page; without it, the run says plainly that it is not confirmed. The step
that makes the change is tried once: a second press, a different way, could
register twice.
"""

from playwright.async_api import async_playwright

from backend.orchestrator import voice
from backend.orchestrator.details import CourseBrief, Understood
from backend.orchestrator.loop import Task, run_task
from backend.orchestrator.plan import (
    SIGN_IN_AND_CLEAR,
    About,
    Confirmation,
    Expectation,
    HardcodedPlanner,
    Operation,
    PlanStep,
    Target,
)
from backend.orchestrator.test_checklist import run
from backend.orchestrator.test_course_from_list import SignsIn, go
from backend.orchestrator.test_orchestrator import replica  # noqa: F401
from backend.orchestrator.voice import actions

CONFIRMS = Confirmation(heading="Registration Confirmed", reads="Confirmation number")


def register_step(expect: Expectation) -> PlanStep:
    return PlanStep(instruction="Ready to book your place on MATH-210.", detail="",
                    actions=actions("Register for MATH-210"),
                    operations=[Operation("click", Target("button", "Register for MATH-210"))],
                    expect=expect, stage=2, changes=True)


def drive(start_url: str, steps: list[PlanStep], task: Task) -> SignsIn:
    async def inner() -> SignsIn:
        connection = SignsIn([])
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await run_task(page, connection, HardcodedPlanner(steps), task, start_url)
            finally:
                await browser.close()
        return connection

    return run(inner())


def test_the_portals_confirmation_is_quoted(replica: str) -> None:  # noqa: F811
    brief = CourseBrief("register me for MATH-210", Understood(course="MATH-210"))

    done = go(replica, brief, [])

    ending = done.of("task.completed")[0]
    # Said as a booking and a payment are (2026-10-17): where, then the
    # number, what the practice copy did not do, and what the portal says
    # against it — kept, plainly. The portal's own words, without the number.
    assert ending["heading"] == "Registered for MATH-210 on the practice site."
    assert ending["caveat"] == (
        "Confirmation number REG-10301-2026. This was a practice copy, so no real "
        "registration was made. The portal says it isn't final until tuition and fees "
        "are paid, or a payment plan is in place.")
    assert ending["confirmation"] == "The portal says “Registration Confirmed”."
    assert ending["scope"] == "You are registered for MATH-210 section 001."
    # Ringed where it was read, with the heading and the number's row.
    assert len(ending["proof"]["rings"]) == 3


def test_a_caveat_the_page_does_not_say_is_not_said(replica: str) -> None:  # noqa: F811
    """Never more than the site: words it does not use give no caveat."""
    steps = [*SIGN_IN_AND_CLEAR, register_step(Expectation(url_contains="/register"))]
    task = Task(goal="g", estimated_steps=3, about=About(),
                confirms=Confirmation(heading="Registration Confirmed",
                                      reads="Confirmation number",
                                      caveat="subject to a refund"))

    done = drive(replica, steps, task)

    assert done.of("task.completed")[0]["caveat"] is None


def test_a_change_the_site_does_not_confirm_is_not_done(replica: str) -> None:  # noqa: F811
    """The click lands, but the page never shows what the step waits for."""
    steps = [*SIGN_IN_AND_CLEAR,
             register_step(Expectation(title_contains="A heading the portal never shows"))]
    task = Task(goal="g", estimated_steps=3, about=About(), confirms=CONFIRMS)

    done = drive(replica, steps, task)

    assert "task.completed" not in done.types()
    assert done.of("help.requested")[0]["reason"] == voice.not_confirmed("Register for MATH-210")
    assert done.of("help.requested")[0]["unconfirmed"] is True
    # Tried once: not a second time, a second way.
    assert done.of("step.failed") == []


def test_a_confirmation_missing_from_the_final_page_is_not_done(replica: str) -> None:  # noqa: F811
    """The step's own check passes; the confirmation the task names is not
    there."""
    steps = [*SIGN_IN_AND_CLEAR,
             register_step(Expectation(url_contains="/register"))]
    task = Task(goal="g", estimated_steps=3, about=About(),
                confirms=Confirmation(heading="Enrolment Finalised"))

    done = drive(replica, steps, task)

    assert "task.completed" not in done.types()
    assert done.of("help.requested")[0]["reason"] == voice.not_confirmed("Register for MATH-210")


def test_a_task_that_only_reads_has_no_confirmation(replica: str) -> None:  # noqa: F811
    steps = [*SIGN_IN_AND_CLEAR]
    task = Task(goal="g", estimated_steps=2, about=About())

    done = drive(replica, steps, task)

    assert done.of("task.completed")[0]["confirmation"] is None


def test_a_qualified_registration_says_what_was_confirmed_not_done(
    replica: str,  # noqa: F811
) -> None:
    """The portal's own sentence must be on the page for the plain words to
    be said (2026-10-16): with a phrase it does not use, neither is."""
    steps = [*SIGN_IN_AND_CLEAR, register_step(Expectation(url_contains="/register"))]
    task = Task(goal="g", estimated_steps=3, about=About(),
                heading="You're registered for MATH-210.",
                confirms=Confirmation(heading="Registration Confirmed",
                                      reads="Confirmation number", caveat="not final until",
                                      caveat_plain="it isn't final until fees are paid"))

    done = drive(replica, steps, task)

    assert done.of("task.completed")[0]["caveat"] == (
        "The portal says it isn't final until fees are paid.")
