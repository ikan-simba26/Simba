"""The course the person asked for, registered on the student portal.

The portal lists twenty-one courses and the plan knew one of them. "Register me
for MATH-210" signed in and booked a place on CS-401, because CS-401 is what
`REGISTRATION_PLAN` says — and the confirmation screen then showed a real
registration for a course nobody had asked about.

`registration_plan(course)` takes the code, and `CourseBrief` says what has to
be true at the end. That last part is the harder half here: a course is chosen
by pressing its own button, so by the time the run ends there is no field
holding the code to check. What the confirmation does carry is a line naming
the course, and that is what is checked (`About.shows`).

The real replica and a real browser. Nothing irreversible: the replica's
registration is a page, and CLAUDE.md's rule is about real records.
"""

import asyncio
from datetime import date

import pytest
from playwright.async_api import async_playwright

from backend.orchestrator.details import CourseBrief, Understood
from backend.orchestrator.loop import run_task
from backend.orchestrator.plan import (
    REGISTRATION_PLAN,
    HardcodedPlanner,
    registration_plan,
)
from backend.orchestrator.test_orchestrator import replica  # noqa: F401
from backend.orchestrator.test_verification import FakeConnection

# Room in it, unlike CS-220, so what is tested is the plan and not a full class.
COURSE = "MATH-210"


def register(course: str, start_url: str, task=None) -> FakeConnection:
    async def go() -> FakeConnection:
        connection = FakeConnection()
        brief = CourseBrief(f"register me for {course}", Understood(course=course))
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await run_task(page, connection, HardcodedPlanner(registration_plan(course)),
                               task or brief.task(), start_url)
                connection.final_url = page.url  # type: ignore[attr-defined]
            finally:
                await browser.close()
        return connection

    return asyncio.run(go())


def test_the_course_the_person_named_is_the_one_registered(replica: str) -> None:  # noqa: F811
    connection = register(COURSE, replica)

    assert "help.requested" not in connection.types(), connection.sent[-1]
    assert "task.completed" in connection.types()
    assert "/register" in connection.final_url  # type: ignore[attr-defined]


def test_the_step_says_which_course_it_is_about_to_book(replica: str) -> None:  # noqa: F811
    """The person reads the step, so the step names their course."""
    connection = register(COURSE, replica)

    last = connection.of("step.presented")[-1]
    assert COURSE in last["instruction"]
    # Its final screen (2026-10-16): the course among what will happen.
    assert any(COURSE in detail["value"] for detail in last["final"])


def test_registering_for_another_course_fails_rather_than_completes(
    replica: str,  # noqa: F811
) -> None:
    """The check that makes the goal mean something. The run books MATH-210 and
    is judged against a task for CS-401: the confirmation is real, the URL and
    the title are exactly what success looks like, and it still fails."""
    asked_for = CourseBrief("register me for CS-401", Understood(course="CS-401")).task()

    connection = register(COURSE, replica, task=asked_for)

    assert "/register" in connection.final_url  # type: ignore[attr-defined]
    reason = connection.payload_of("help.requested")["reason"]
    assert "Course" in reason and "CS-401" in reason and COURSE in reason
    assert "task.completed" not in connection.types()


def test_the_confirmation_is_what_carries_the_check(replica: str) -> None:  # noqa: F811
    """There is no field to check by then, so `shows` is the only thing that
    can catch a wrong course — and the site puts its own words round the code
    (`MATH-210 section 001`), which is why the match is inside the value."""
    task = CourseBrief("g", Understood(course=COURSE)).task()

    assert task.about.holds == ()
    assert [(s.reads, s.says) for s in task.about.shows] == [("Course", COURSE)]

    connection = register(COURSE, replica)
    shown = connection.payload_of("task.completed")
    assert "task.failed" not in connection.types()
    assert shown["steps_taken"] == 3


def test_the_plan_for_a_course_is_the_shared_sign_in_and_that_course() -> None:
    """One plan per course, and only its last step differs."""
    theirs = registration_plan(COURSE)
    ours = registration_plan("CS-401")

    assert [step.instruction for step in theirs[:-1]] == [
        step.instruction for step in ours[:-1]]
    assert theirs[-1].operations[0].target.label == f"Register for {COURSE}"
    assert ours[-1].operations[0].target.label == "Register for CS-401"


def test_the_worked_example_is_still_the_worked_example() -> None:
    """`REGISTRATION_PLAN` is what every recorded registration number was
    measured on. Its last step carried CS-401's own timetable line, written
    into the plan; since 2026-10-16 that line is the final screen's details,
    read off the portal's own row, the same as for any course. The steps, and
    what each presses, are as they were."""
    assert REGISTRATION_PLAN[-1].final == registration_plan("CS-401")[-1].final
    assert REGISTRATION_PLAN[-1].operations == registration_plan("CS-401")[-1].operations
    assert REGISTRATION_PLAN[-1].changes
    assert len(REGISTRATION_PLAN) == len(registration_plan("CS-401"))


@pytest.mark.parametrize("said, code", [
    ("register me for math 210", "MATH-210"),
    ("MATH210", "MATH-210"),
    ("i want MATH-210 please", "MATH-210"),
])
def test_a_course_is_read_out_of_the_goal_however_it_was_written(
    said: str, code: str
) -> None:
    from backend.orchestrator.details import by_keywords

    assert by_keywords("registration", said, date(2026, 9, 30)).course == code
