"""Repo-root fixtures, and the reason this file exists at all.

Putting the repo root on `sys.path` so tests can import `backend.*` and
`shared.*` — run the suite from here with `python -m pytest`.

It also owns the one Playwright instance the whole session shares. Two
`sync_playwright()` context managers alive at once in the same process fail
with "Sync API inside the asyncio loop", which is a confusing way to be told
that only one may exist. Every module that needs a browser takes this fixture
rather than opening its own.
"""

import pytest
from playwright.sync_api import Playwright, sync_playwright


@pytest.fixture(scope="session")
def playwright_instance() -> Playwright:
    with sync_playwright() as playwright:
        yield playwright
