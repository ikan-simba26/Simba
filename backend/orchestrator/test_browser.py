"""Sourcing the page: launching Chromium, or attaching to the Electron host.

The page-picking logic is the part that can silently do the wrong thing —
drive the overlay instead of the site — so it is tested directly rather than
only through a live host.
"""

from dataclasses import dataclass

import pytest

from backend.orchestrator.browser import (
    NoSiteView,
    browser_source,
    cdp_url,
    find_site_page,
)

OVERLAY = "data:text/html,<html><body>SIMBA</body></html>"
SITE = "http://127.0.0.1:5100/"


@dataclass
class FakePage:
    url: str


def test_the_site_view_is_found_by_origin() -> None:
    pages = [FakePage(OVERLAY), FakePage(SITE + "bill/detail")]

    assert find_site_page(pages, SITE).url == SITE + "bill/detail"


def test_order_does_not_matter() -> None:
    pages = [FakePage(SITE), FakePage(OVERLAY)]

    assert find_site_page(pages, SITE).url == SITE


def test_the_overlay_is_never_chosen() -> None:
    """Driving the overlay would look like it worked and change nothing."""
    pages = [FakePage(OVERLAY), FakePage("about:blank")]

    assert find_site_page(pages, SITE).url == "about:blank"


def test_a_site_view_that_has_not_navigated_yet_still_resolves() -> None:
    pages = [FakePage(OVERLAY), FakePage("about:blank")]

    assert find_site_page(pages, "http://127.0.0.1:5100").url == "about:blank"


def test_no_pages_at_all_is_reported_clearly() -> None:
    with pytest.raises(NoSiteView, match="no pages"):
        find_site_page([], SITE)


def test_only_the_overlay_names_the_likely_cause() -> None:
    with pytest.raises(NoSiteView, match="SIMBA_START_URL"):
        find_site_page([FakePage(OVERLAY)], SITE)


def test_an_ambiguous_host_refuses_rather_than_guessing() -> None:
    """Two candidate pages and no origin match: better to stop than pick one."""
    pages = [FakePage("about:blank"), FakePage("chrome://version")]

    with pytest.raises(NoSiteView, match="could not tell which"):
        find_site_page(pages, "http://elsewhere.invalid")


def test_defaults_keep_the_suite_headless(monkeypatch) -> None:
    monkeypatch.delenv("SIMBA_BROWSER", raising=False)
    monkeypatch.delenv("SIMBA_CDP_URL", raising=False)

    assert browser_source() == "chromium"
    assert cdp_url() == "http://127.0.0.1:9222"


def test_the_browser_source_is_case_and_space_tolerant(monkeypatch) -> None:
    monkeypatch.setenv("SIMBA_BROWSER", "  Electron ")

    assert browser_source() == "electron"
