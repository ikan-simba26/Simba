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
    configured, and a value set after that is never seen.

    `.scratch/` itself is made here if it is not there (2026-10-17): it is
    ignored, so a fresh clone has none, and pytest makes only the last folder
    of the path — on a fresh clone every test that used `tmp_path` errored."""
    if not config.option.basetemp:
        BASETEMP.parent.mkdir(parents=True, exist_ok=True)
        config.option.basetemp = str(BASETEMP)


def pytest_report_header(config: pytest.Config) -> str:
    """The machine's power source, processor speed and free memory, at the
    top of every run (2026-10-17). The backend half took 805s on one commit
    on 2026-10-16 and 1435s on the same commit a day later, and nothing said
    what the machine was doing either time."""
    from tools.evaluation.conditions import power, power_line

    return power_line(power()).replace("power       ", "power: ", 1)


@pytest.fixture(scope="session")
def playwright_instance() -> Playwright:
    with sync_playwright() as playwright:
        yield playwright
