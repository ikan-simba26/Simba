"""Photographing the site view when a capture request stalls.

At a display scale of 100% the host's site view answers a capture only when a
second one is asked for (EVALUATION.md, 2026-10-17): the end-of-task picture
then failed about every other time. `browser.capture_site` asks again while it
waits. These tests stand a scripted CDP session in for Chromium, so they run
without the host; the real one was measured with the host at forced scales.
"""

import asyncio
import base64

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from backend.orchestrator import browser

PNG = b"\x89PNG picture"


class StallingSession:
    """Chromium at 100%: a request is answered only when the next one arrives,
    and then every request waiting is answered together. `answers=False`: none
    ever is."""

    def __init__(self, answers: bool = True) -> None:
        self.answers = answers
        self.waiting: list[asyncio.Future] = []
        self.asked = 0
        self.detached = False

    async def send(self, method: str, params: dict) -> dict:
        assert method == "Page.captureScreenshot" and params == {"format": "png"}
        self.asked += 1
        reply = asyncio.get_running_loop().create_future()
        if self.answers and self.waiting:
            for earlier in self.waiting:
                if not earlier.done():
                    earlier.set_result({"data": base64.b64encode(PNG).decode()})
            reply.set_result({"data": base64.b64encode(PNG).decode()})
        self.waiting.append(reply)
        return await reply

    async def detach(self) -> None:
        self.detached = True


class Page:
    def __init__(self, session: StallingSession) -> None:
        self.session = session
        self.scripts: list[str] = []
        self.context = self

    async def new_cdp_session(self, page: "Page") -> StallingSession:
        return self.session

    async def evaluate(self, script: str, arg=None) -> None:
        self.scripts.append(script)


def test_a_stalled_capture_is_asked_for_again_and_arrives() -> None:
    session = StallingSession()
    page = Page(session)

    async def go():
        started = asyncio.get_running_loop().time()
        shot = await browser.capture_site(page, mask="input[type=password]")
        return shot, asyncio.get_running_loop().time() - started

    shot, took = asyncio.run(go())

    assert shot == PNG
    assert session.asked == 2
    assert took < browser.NUDGE_S + 0.5  # not a timeout's worth
    # The page is put back as it was, and the session let go.
    assert page.scripts == [browser.PREPARE_JS, browser.CLEAN_JS]
    assert session.detached


def test_a_capture_nobody_answers_gives_up_in_time(monkeypatch) -> None:
    monkeypatch.setattr(browser, "CAPTURE_TIMEOUT_S", 0.5)
    session = StallingSession(answers=False)
    page = Page(session)

    with pytest.raises(PlaywrightTimeoutError):
        asyncio.run(browser.capture_site(page))

    assert session.asked >= 2
    assert page.scripts[-1] == browser.CLEAN_JS
    assert session.detached
