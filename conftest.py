"""Repo-root fixtures, and the reason this file exists at all.

Putting the repo root on `sys.path` so tests can import `backend.*` and
`shared.*` — run the suite from here with `python -m pytest`.

It also owns the one Playwright instance the whole session shares. Two
`sync_playwright()` context managers alive at once in the same process fail
with "Sync API inside the asyncio loop", which is a confusing way to be told
that only one may exist. Every module that needs a browser takes this fixture
rather than opening its own.
"""

from pathlib import Path

import pytest
from playwright.sync_api import Playwright, sync_playwright

#: Where every test's `tmp_path` lives. CLAUDE.md keeps temporary files inside
#: the repository, in its ignored paths; pytest's default is the system temp
#: directory, and until 2026-10-03 seven test files wrote there. Absolute, so
#: it holds whichever directory pytest is run from. pytest empties it at the
#: start of every run, so nothing else may keep files in it.
BASETEMP = Path(__file__).resolve().parent / ".scratch" / "pytest"


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    """`--basetemp` is `.scratch/pytest` unless the command line says otherwise.

    First, because pytest's own temp-path factory reads the option when it is
    configured, and a value set after that is never seen."""
    if not config.option.basetemp:
        config.option.basetemp = str(BASETEMP)


@pytest.fixture(scope="session")
def playwright_instance() -> Playwright:
    with sync_playwright() as playwright:
        yield playwright
