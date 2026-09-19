"""The browser perception's tests read pages with.

Session-scoped, because launching Chromium per test is most of the runtime.
Sync API, because these tests are synchronous — and for that reason it stays
in this directory: a sync Playwright session alive in the same thread breaks
`asyncio.run`, which is how every orchestrator test runs (`backend/conftest.py`).

The replicas it visits come from `backend/conftest.py`.
"""

from collections.abc import Iterator

import pytest
from playwright.sync_api import Page, Playwright


@pytest.fixture(scope="session")
def page(playwright_instance: Playwright) -> Iterator[Page]:
    # The Playwright instance is shared session-wide; see the root conftest.
    browser = playwright_instance.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    yield page
    browser.close()
