"""Fixtures shared by the perception tests.

They live here rather than in one test module so both modules get the same
session-scoped browser. Importing a fixture across modules registers it twice
and enters `sync_playwright()` twice, which fails.
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

REPLICA_DIR = Path(__file__).resolve().parents[2] / "replicas" / "registration"
BASE_URL = "http://127.0.0.1:5001"


@pytest.fixture(scope="session")
def replica() -> Iterator[str]:
    proc = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=REPLICA_DIR,
        env={**os.environ, "PORT": "5001"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for(BASE_URL)
        yield BASE_URL
    finally:
        proc.terminate()
        proc.wait(timeout=10)


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
