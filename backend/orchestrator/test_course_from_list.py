"""Which course, asked from the courses the portal offers (2026-10-16).

Until then the course was asked first, in the person's own words, before the
site was touched; a course the portal does not offer was found out only at
the register step, when its button was not there. Now the run signs in, reads
the courses the portal lists, and asks from those — on the registration
replica, twenty "Register for ..." buttons.
"""

from playwright.async_api import async_playwright

from backend.orchestrator import voice
from backend.orchestrator.details import CourseBrief, Understood
from backend.orchestrator.loop import run_brief
from backend.orchestrator.test_checklist import Answers, run
from backend.orchestrator.test_orchestrator import replica  # noqa: F401


class SignsIn(Answers):
    """Signs in as a person would, and answers each question in turn."""

    async def receive(self, message_type, step_index=None, on_other=None):
        step = self.of("step.presented")[-1]
        if any(f["id"] == "password" for f in step["fields"]):
            self.shown += 1
            return {"type": "step.response", "payload": {
                "step_index": step_index, "action_id": "confirm",
                "input_values": {"username": "student", "password": "anything"}}}
        return await super().receive(message_type, step_index, on_other)


def go(start_url: str, brief, answers) -> SignsIn:
    async def inner() -> SignsIn:
        connection = SignsIn(answers)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await run_brief(page, connection, brief, start_url, auto=True)
            finally:
                await browser.close()
        return connection

    return run(inner())


OFFERED = ["CS-401", "CS-220", "MATH-210", "MATH-301", "ENGL-101", "ENGL-215", "HIST-150",
           "BIOL-101", "BIOL-101L", "CHEM-111", "PHYS-201", "ECON-101", "PSYC-101",
           "ART-101", "PHIL-205", "CS-350", "CS-460", "STAT-200", "MUSC-110", "SOC-101"]


def course_questions(done) -> list[dict]:
    return [p for p in done.of("step.presented") if p["instruction"] == voice.ASK_COURSE]


def test_no_course_named_is_asked_after_signing_in_from_the_portals_list(
    replica: str,  # noqa: F811
) -> None:
    brief = CourseBrief("register me for a course", Understood())

    done = go(replica, brief, [("confirm", {"course": "math 210"})])

    shown = [p["instruction"] for p in done.of("step.presented")]
    assert shown.index("Let me sign you in first.") < shown.index(voice.ASK_COURSE)
    [question] = course_questions(done)
    [field] = question["fields"]
    assert (field["type"], field["options"]) == ("choice", OFFERED)
    assert question["detail"] == voice.COURSES_OFFERED
    assert question["stage"] == 1
    # Whatever the spelling, the course registered is the portal's own.
    assert "task.completed" in done.types(), done.types()
    assert done.of("task.completed")[0]["scope"].startswith(
        "You are registered for MATH-210")


def test_a_course_named_and_offered_is_not_asked_about(replica: str) -> None:  # noqa: F811
    brief = CourseBrief("register me for MATH-210", Understood(course="MATH-210"))

    done = go(replica, brief, [])

    assert course_questions(done) == []
    assert "task.completed" in done.types()


def test_a_course_named_but_not_offered_is_caught_at_the_question(
    replica: str,  # noqa: F811
) -> None:
    """Not at the register step, where its button would not be there."""
    brief = CourseBrief("register me for CS-999", Understood(course="CS-999"))

    done = go(replica, brief, [("confirm", {"course": "CS-401"})])

    [question] = course_questions(done)
    assert question["note"] == "The portal doesn't offer CS-999."
    assert "task.completed" in done.types()
    assert "CS-401" in done.of("task.completed")[0]["scope"]


def test_a_typed_course_not_on_the_list_is_asked_again(replica: str) -> None:  # noqa: F811
    brief = CourseBrief("register me for a course", Understood())

    done = go(replica, brief, [("confirm", {"course": "BIO-999"}),
                               ("confirm", {"course": "CS-460"})])

    first, second = course_questions(done)
    assert first.get("note") is None
    assert second["note"] == "The portal doesn't offer BIO-999."
    assert "task.completed" in done.types()


def test_registering_still_asks(replica: str) -> None:  # noqa: F811
    """Choosing the course is not agreeing to register: that step asks."""
    brief = CourseBrief("register me for MATH-210", Understood(course="MATH-210"))

    done = go(replica, brief, [])

    assert "Ready to book your place on MATH-210." in done.asked()
