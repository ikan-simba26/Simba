"""Verification must have teeth: prove it catches a step that didn't work.

The end-to-end test only walks the happy path, where every step succeeds. If
`check` were broken and always passed, that test would still be green. These
drive the loop directly with plans that cannot succeed, and assert the
skeleton notices, retries, and hands control back.
"""

import asyncio
import time

from playwright.async_api import async_playwright

from backend.orchestrator.loop import (
    VERIFY_TIMEOUT_S,
    Connection,
    Snapshot,
    check,
    run_task,
)
from backend.orchestrator.plan import (
    REGISTRATION_PLAN,
    Expectation,
    Operation,
    PlanStep,
    Target,
)
from backend.orchestrator.test_orchestrator import REPLICA_URL, replica  # noqa: F401
from shared.schema import StepAction

CREDENTIALS = {"username": "raham", "password": "hunter2"}
CONFIRM = [StepAction(id="confirm", label="Go", kind="primary")]

BEFORE = Snapshot(url="http://x/a", title="A", labels=("one", "two"))


class FakeConnection(Connection):
    """Records what the loop emits and confirms every step it presents."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []

    async def send(self, message_type: str, payload) -> None:
        self.sent.append((message_type, payload.model_dump()))

    async def receive(self, message_type: str, step_index: int | None = None) -> dict:
        return {
            "type": "step.response",
            "payload": {
                "step_index": step_index,
                "action_id": "confirm",
                "input_values": CREDENTIALS,
            },
        }

    def types(self) -> list[str]:
        return [message_type for message_type, _ in self.sent]

    def payload_of(self, message_type: str) -> dict:
        return next(payload for name, payload in self.sent if name == message_type)


def drive(plan: list[PlanStep], start_url: str) -> FakeConnection:
    """Run the real loop against a real browser and replica."""

    async def go() -> FakeConnection:
        connection = FakeConnection()
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await run_task(page, connection, plan, start_url)
            finally:
                await browser.close()
        return connection

    return asyncio.run(go())


# --- check() is the thing under suspicion -----------------------------------


def test_check_rejects_an_unchanged_page() -> None:
    assert check(BEFORE, BEFORE, Expectation(url_contains="/a")) == (
        "the page did not change at all"
    )


def test_check_rejects_a_wrong_url() -> None:
    after = Snapshot(url="http://x/b", title="A", labels=("one",))
    assert "expected the URL to contain" in check(BEFORE, after, Expectation(url_contains="/z"))


def test_check_rejects_a_label_that_should_have_gone() -> None:
    after = Snapshot(url="http://x/b", title="A", labels=("one",))
    assert "to be gone" in check(BEFORE, after, Expectation(label_gone="one"))


def test_check_rejects_a_label_that_never_appeared() -> None:
    after = Snapshot(url="http://x/b", title="A", labels=("one",))
    assert "to appear" in check(BEFORE, after, Expectation(label_present="three"))


def test_check_accepts_a_page_that_changed_as_expected() -> None:
    after = Snapshot(url="http://x/courses", title="Courses", labels=("three",))
    expect = Expectation(url_contains="/courses", label_gone="one", label_present="three")
    assert check(BEFORE, after, expect) is None


# --- and end to end, against the replica ------------------------------------


def test_a_click_that_changes_nothing_asks_for_help(replica: str) -> None:  # noqa: F811
    """The click lands, the element is still there, but the page never moves.

    "Home" is an href="#" link, so clicking it is a no-op. This is the case
    the skeleton must never wave through: the action appeared to succeed.
    """
    plan = [
        PlanStep(
            instruction="Go home.",
            detail="",
            actions=CONFIRM,
            operations=[Operation("click", Target("link", "Home"))],
            expect=Expectation(url_contains="/somewhere-that-does-not-exist"),
        )
    ]

    started = time.monotonic()
    connection = drive(plan, replica)
    elapsed = time.monotonic() - started

    assert "task.completed" not in connection.types()
    assert "help.requested" in connection.types()

    states = [state for name, state in connection.sent if name == "state.changed"]
    assert states[-1] == {"state": "stuck"}

    reason = connection.payload_of("help.requested")["reason"]
    assert "the page did not change at all" in reason

    # Two verification windows must have elapsed, not one: the step was tried
    # again with the fallback strategy before giving up.
    assert elapsed > 2 * VERIFY_TIMEOUT_S - 1, f"only one attempt was made ({elapsed:.1f}s)"


def test_missing_element_asks_for_help(replica: str) -> None:  # noqa: F811
    """The plan names an element that is not on the page at all."""
    plan = [
        PlanStep(
            instruction="Click something that isn't there.",
            detail="",
            actions=CONFIRM,
            operations=[Operation("click", Target("button", "No Such Button"))],
            expect=Expectation(url_contains="/courses"),
        )
    ]

    connection = drive(plan, replica)

    reason = connection.payload_of("help.requested")["reason"]
    assert "could not find 'No Such Button'" in reason
    assert "task.completed" not in connection.types()


def test_the_same_harness_completes_the_real_plan(replica: str) -> None:  # noqa: F811
    """Control: the failures above are the plans' fault, not the harness's."""
    connection = drive(REGISTRATION_PLAN, replica)

    assert "help.requested" not in connection.types()
    assert connection.payload_of("task.completed")["steps_taken"] == 3
