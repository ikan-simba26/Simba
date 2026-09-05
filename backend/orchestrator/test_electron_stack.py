"""The Electron path, end to end. Skipped unless a host is already running.

The default suite must stay headless and must not need Electron installed,
so this only runs when something is already answering on the CDP port. Start
one with `npm start` in frontend/ (with SIMBA_START_URL set) and run pytest
again to exercise it.
"""

import asyncio
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from backend.orchestrator.billing_plan import BILLING_PLAN, BILLING_TASK
from backend.orchestrator.browser import cdp_url, open_page
from backend.orchestrator.loop import run_task
from backend.orchestrator.plan import HardcodedPlanner
from backend.orchestrator.test_verification import FakeConnection
from backend.perception.serializer import serialize_async

REPO_ROOT = Path(__file__).resolve().parents[2]
REPLICA_URL = "http://127.0.0.1:5102"


def _host_is_up() -> bool:
    try:
        urllib.request.urlopen(cdp_url() + "/json/version", timeout=1)
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _host_is_up(),
    reason=f"no SIMBA host on {cdp_url()}; start one with npm start in frontend/",
)


@pytest.fixture(scope="module")
def replica() -> Iterator[str]:
    proc = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=REPO_ROOT / "replicas" / "billing",
        env={**os.environ, "PORT": "5102"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                urllib.request.urlopen(REPLICA_URL, timeout=1)
                break
            except (urllib.error.URLError, ConnectionError):
                time.sleep(0.2)
        yield REPLICA_URL
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture(autouse=True)
def electron(monkeypatch) -> None:
    monkeypatch.setenv("SIMBA_BROWSER", "electron")


def test_the_backend_attaches_to_the_site_view_not_the_overlay(replica: str) -> None:
    async def go():
        async with open_page(replica) as page:
            return page.url, await page.evaluate("[window.innerWidth, window.innerHeight]")

    url, viewport = asyncio.run(go())

    assert not url.startswith("data:"), "attached to the overlay, not the site"
    assert viewport == [1280, 800], "the hidden view is not at the frozen viewport"


def test_the_covered_view_screenshots_reliably(replica: str) -> None:
    """The whole reason the site view is covered rather than hidden."""

    async def go():
        async with open_page(replica) as page:
            await page.goto(replica)
            return [await page.screenshot(timeout=8000) for _ in range(5)]

    shots = asyncio.run(go())

    assert len(shots) == 5
    assert all(len(s) > 1000 for s in shots)


def test_perception_works_on_the_hidden_view(replica: str) -> None:
    async def go():
        async with open_page(replica) as page:
            await page.goto(replica)
            return await serialize_async(page)

    elements = asyncio.run(go())

    assert len(elements) > 20
    assert any(e.role == "textbox" for e in elements)
    assert sum(e.dead_link for e in elements) > 10


def test_a_hardcoded_task_completes_against_the_hidden_view(replica: str) -> None:
    task = replace(BILLING_TASK, estimated_steps=len(BILLING_PLAN))

    async def go():
        connection = FakeConnection()
        async with open_page(replica) as page:
            await run_task(page, connection, HardcodedPlanner(BILLING_PLAN), task, replica)
        return connection

    connection = asyncio.run(go())

    assert "help.requested" not in connection.types(), connection.sent[-1]
    completed = connection.payload_of("task.completed")
    assert completed["steps_taken"] == 3
    assert completed["llm_calls"] == 0
    assert "/bill/detail" in completed["summary"]


def test_the_host_survives_the_backend_detaching(replica: str) -> None:
    """Closing a CDP connection must not take the user's window down."""

    async def go():
        async with open_page(replica) as page:
            await page.goto(replica)

    asyncio.run(go())

    assert _host_is_up(), "the host died when the backend disconnected"
