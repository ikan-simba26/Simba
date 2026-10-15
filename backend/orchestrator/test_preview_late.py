"""The person's answer is never blocked by a picture of the page (2026-10-15).

On 2026-10-14, in the real window, a screenshot for `trust.requested` took
30s to fail, and because it was awaited in the loop that reads the person's
answer, "Register for CS-401" — pressed meanwhile — waited 31s. A picture is
now taken in a task of its own, dropped past `PREVIEW_DEADLINE_S`, and
cancelled as soon as the step is answered.
"""

import asyncio
import time
from types import SimpleNamespace

import pytest

from backend.orchestrator import loop
from backend.orchestrator.loop import Move, _Run
from backend.orchestrator.plan import Expectation
from backend.orchestrator.test_asking import ScriptedConnection
from backend.orchestrator.voice import actions

STEP = Move(instruction="Ready to book your place on CS-401.", detail="", operations=[],
            expect=Expectation(), fields=[], actions=actions("Register for CS-401"))
NO_PAGE = SimpleNamespace(document=None)


class AsksForAPictureThenAnswers(ScriptedConnection):
    """Asks for a picture, waits `then` seconds, then answers the step."""

    def __init__(self, then: float = 0.0) -> None:
        super().__init__()
        self.then = then

    async def receive(self, message_type, step_index=None, on_other=None):  # noqa: ARG002
        await on_other({"type": "trust.requested", "payload": {}})
        await asyncio.sleep(self.then)
        return {"type": "step.response",
                "payload": {"step_index": step_index, "action_id": "confirm",
                            "input_values": {}}}


def present(connection, preview) -> tuple[float, _Run]:
    async def go() -> tuple[float, _Run]:
        run = _Run(None, connection, None, None)
        started = time.monotonic()
        await run.present(STEP, goal="g", findings=[], view=NO_PAGE)
        took = time.monotonic() - started
        await asyncio.sleep(0.3)  # let anything cancelled or dropped finish
        return took, run

    original = loop.send_preview
    loop.send_preview = preview
    try:
        return asyncio.run(go())
    finally:
        loop.send_preview = original


def test_a_slow_picture_does_not_hold_the_answer() -> None:
    seen = {"cancelled": False}

    async def slow(page, connection, move) -> None:  # noqa: ARG001
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            seen["cancelled"] = True
            raise

    took, run = present(AsksForAPictureThenAnswers(), slow)

    assert took < 1.0, took
    # Answered: the picture of a step that has gone is dropped, not left to
    # race the next move on the page.
    assert seen["cancelled"]
    assert not run.previews


def test_a_quick_picture_is_still_sent() -> None:
    async def quick(page, connection, move) -> None:  # noqa: ARG001
        await connection.send("error", SimpleNamespace(model_dump=lambda: {"code": "PICTURE"}))

    connection = AsksForAPictureThenAnswers(then=0.2)
    took, _ = present(connection, quick)

    assert connection.of("error") == [{"code": "PICTURE"}]
    assert took < 1.0


def test_a_late_picture_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(loop, "PREVIEW_DEADLINE_S", 0.1)
    sent = {"done": False}

    async def late(page, connection, move) -> None:  # noqa: ARG001
        await asyncio.sleep(5)
        sent["done"] = True

    connection = AsksForAPictureThenAnswers(then=0.5)
    took, run = present(connection, late)

    assert not sent["done"]
    assert took < 1.0
    assert not run.previews
    assert connection.of("page.preview") == []
    # Said, so "What are you doing?" can say so too (2026-10-16).
    assert connection.of("error") == [{"code": loop.PREVIEW_LATE,
                                       "message": "I couldn't get a picture just now."}]


def test_a_failed_picture_does_not_stop_the_step() -> None:
    async def broken(page, connection, move) -> None:  # noqa: ARG001
        raise RuntimeError("the page went away")

    connection = AsksForAPictureThenAnswers(then=0.2)
    took, _ = present(connection, broken)

    assert took < 1.0
    assert [e["code"] for e in connection.of("error")] == [loop.PREVIEW_LATE]
