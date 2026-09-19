"""Fixtures shared by the tests that need a browser and a replica.

They live in a conftest rather than in one test module so every module gets
the same session-scoped browser. Importing a fixture across modules registers
it twice and enters `sync_playwright()` twice, which fails.

Moved up from `perception/` on 2026-09-19, when the estimator's tests needed
the same two replicas. A second copy would have been two servers on one port:
whichever started first would hold 5001 and the other would fail, in a way
that reads as a broken test rather than as a duplicated fixture.
"""

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Page, Playwright

REPLICAS = Path(__file__).resolve().parents[1] / "replicas"
BASE_URL = "http://127.0.0.1:5001"
BILLING_URL = "http://127.0.0.1:5002"


def _serve(name: str, port: int, url: str) -> Iterator[str]:
    proc = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=REPLICAS / name,
        env={**os.environ, "PORT": str(port)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for(url)
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture(scope="session")
def replica() -> Iterator[str]:
    yield from _serve("registration", 5001, BASE_URL)


@pytest.fixture(scope="session")
def billing() -> Iterator[str]:
    """The second replica. Its own port, so both can be up at once."""
    yield from _serve("billing", 5002, BILLING_URL)


def _wait_for(url: str, timeout_s: float = 20.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.2)
    raise RuntimeError(f"replica did not start at {url}")


@pytest.fixture(scope="session")
def page(playwright_instance: Playwright) -> Iterator[Page]:
    # The Playwright instance is shared session-wide; see the root conftest.
    browser = playwright_instance.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    yield page
    browser.close()
