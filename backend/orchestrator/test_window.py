"""A run waits while the SIMBA window is put away, and goes on only when told.

On 2026-10-05 the SIMBA window was minimised during two demo recordings, and
both ended "I'm stuck, so I've stopped.": a minimised window paints the site
view about once a second, a click waits for a page that settles, and none
does (EVALUATION.md, 2026-10-05d). Now nothing is done while the window is
minimised or hidden. When it comes back the person is told, in one line, that
the run waited (`voice.WINDOW_BACK`), and it goes on only once they say so.

These run the real loop on the billing replica in a headless browser, with a
stand-in for the host's window (`browser.window_watch` in the product). Its
second step types the reference number and then presses "Check Bill", so a
window put away at the third check goes away in the middle of a step.
`test_window_state_*` read the value the host writes into the overlay page.
"""

import asyncio
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from backend.orchestrator import loop, voice
from backend.orchestrator.billing_plan import BILLING_PLAN, BILLING_TASK
from backend.orchestrator.browser import window_state
from backend.orchestrator.loop import run_task
from backend.orchestrator.plan import HardcodedPlanner
from backend.orchestrator.test_billing import billing_replica  # noqa: F401 - fixture
from backend.orchestrator.test_verification import FakeConnection

#: The checks, one before each operation: accept cookies; type the reference;
#: press "Check Bill"; open the full bill.
MID_STEP = 3


class Window:
    """A window put away at one check, and back after so many more looks."""

    def __init__(self, away_at: int | None, looks_away: int = 4, state: str = "minimised"):
        self.away_at = away_at
        self.looks_away = looks_away
        self.away_state = state
        self.looks = 0
        self.now = "shown"

    async def __call__(self) -> str:
        self.looks += 1
        away = (self.away_at is not None
                and self.away_at <= self.looks < self.away_at + self.looks_away)
        self.now = self.away_state if away else "shown"
        return self.now


class StopsWhenBack(FakeConnection):
    """Confirms every step, and presses stop on the one that says the window
    is back."""

    def __init__(self) -> None:
        super().__init__()
        self.last_instruction = ""

    async def send(self, message_type: str, payload) -> None:
        await super().send(message_type, payload)
        if message_type == "step.presented":
            self.last_instruction = payload.instruction

    async def receive(self, message_type: str, step_index: int | None = None,
                      on_other=None) -> dict:
        response = await super().receive(message_type, step_index, on_other)
        if self.last_instruction == voice.WINDOW_BACK:
            response["payload"]["action_id"] = voice.CANCEL_ID
        return response


@pytest.fixture(autouse=True)
def quick(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(loop, "WINDOW_POLL_S", 0.01)


def drive(start_url: str, window, connection: FakeConnection | None = None,
          monkeypatch: pytest.MonkeyPatch | None = None) -> tuple[FakeConnection, list[str]]:
    """The billing run with this window. Returns what was sent, and the
    window's state at every action actually taken on the page."""
    acted_while: list[str] = []
    real_act = loop.act

    async def act(*args, **kwargs):
        acted_while.append(window.now if window is not None else "shown")
        return await real_act(*args, **kwargs)

    assert monkeypatch is not None
    monkeypatch.setattr(loop, "act", act)

    async def go() -> FakeConnection:
        sent = connection or FakeConnection()
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await run_task(page, sent, HardcodedPlanner(BILLING_PLAN), BILLING_TASK,
                               start_url, window=window)
            finally:
                await browser.close()
        return sent

    return asyncio.run(go()), acted_while


def instructions(connection: FakeConnection) -> list[str]:
    return [step["instruction"] for step in connection.of("step.presented")]


def test_a_window_minimised_mid_step_is_waited_for_and_the_run_finishes(
    billing_replica: str, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    window = Window(away_at=MID_STEP)

    sent, acted_while = drive(billing_replica, window, monkeypatch=monkeypatch)

    # Nothing was done on the page while the window was away.
    assert acted_while == ["shown"] * 4
    # No failure, no retry, no stuck screen.
    assert "help.requested" not in sent.types()
    assert "step.failed" not in sent.types()
    # When it came back: the one calm line, between the step that was under
    # way and the next one, and then the run carried on to the bill.
    assert instructions(sent) == [
        voice.ASK_COOKIES,
        "Let me look up your bill.",
        voice.WINDOW_BACK,
        "Now I'll open the full bill.",
    ]
    back = sent.of("step.presented")[2]
    assert [(a["id"], a["label"]) for a in back["actions"]] == [
        (voice.CONFIRM_ID, voice.CARRY_ON), (voice.CANCEL_ID, voice.STOP)]
    completed = sent.payload_of("task.completed")
    # The line is not a step the person agreed to.
    assert completed["steps_taken"] == 3
    assert completed["findings"][0]["value"] == "14,382"


def test_it_waits_as_long_as_the_window_is_away(
    billing_replica: str, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """Away for forty looks, and still nothing done and nothing failed."""
    window = Window(away_at=MID_STEP, looks_away=40)

    sent, acted_while = drive(billing_replica, window, monkeypatch=monkeypatch)

    assert window.looks >= MID_STEP + 40
    assert "minimised" not in acted_while
    assert instructions(sent).count(voice.WINDOW_BACK) == 1
    assert "task.completed" in sent.types()


def test_a_hidden_window_is_waited_for_like_a_minimised_one(
    billing_replica: str, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    window = Window(away_at=1, state="hidden")

    sent, acted_while = drive(billing_replica, window, monkeypatch=monkeypatch)

    assert "hidden" not in acted_while
    assert instructions(sent)[:2] == [voice.ASK_COOKIES,
                                      voice.WINDOW_BACK]
    assert "task.completed" in sent.types()


def test_stop_when_the_window_comes_back_stops_the_run(
    billing_replica: str, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    window = Window(away_at=MID_STEP)

    sent, acted_while = drive(billing_replica, window, StopsWhenBack(), monkeypatch)

    # Two actions, before the window went: accept, type. Nothing after.
    assert acted_while == ["shown", "shown"]
    assert sent.payload_of("task.failed")["reason"] == voice.YOU_STOPPED
    assert "help.requested" not in sent.types()
    assert "task.completed" not in sent.types()


def test_a_window_that_stays_shown_changes_nothing(
    billing_replica: str, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    watched, _ = drive(billing_replica, Window(away_at=None), monkeypatch=monkeypatch)
    unwatched, _ = drive(billing_replica, None, monkeypatch=monkeypatch)

    assert watched.types() == unwatched.types()
    assert voice.WINDOW_BACK not in instructions(watched)


# --- what the host writes, read the way the backend reads it ------------------


def test_window_state_reads_what_the_host_wrote_into_the_overlay(tmp_path: Path) -> None:
    overlay_file = tmp_path / "index.html"
    overlay_file.write_text("<!doctype html><title>overlay</title>", encoding="utf-8")

    async def go() -> list[str]:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                site = await browser.new_page()
                await site.set_content("<p>the site</p>")
                overlay = await browser.new_page()
                await overlay.goto(overlay_file.as_uri())
                pages = [site, overlay]
                seen = [await window_state(pages)]
                for state in ("minimised", "hidden", "shown"):
                    await overlay.evaluate(f"() => {{ window.__simbaWindow = '{state}'; }}")
                    seen.append(await window_state(pages))
                # A value on the site view is not the host's, and is ignored.
                await overlay.evaluate("() => { delete window.__simbaWindow; }")
                await site.evaluate("() => { window.__simbaWindow = 'minimised'; }")
                seen.append(await window_state(pages))
                return seen
            finally:
                await browser.close()

    # Before the host has said anything, the window reads as shown.
    assert asyncio.run(go()) == ["shown", "minimised", "hidden", "shown", "shown"]


def test_window_state_with_no_overlay_page_is_shown() -> None:
    assert asyncio.run(window_state([])) == "shown"
