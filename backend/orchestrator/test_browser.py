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
BUILT_OVERLAY = "file:///D:/simba/frontend/dist/index.html"
DEV_OVERLAY = "http://127.0.0.1:5173/"
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
    """Two pages that could each be a website, and no origin match.

    Picking one would mean a chance of driving the wrong page, where every
    action appears to succeed and nothing happens. Better to stop.
    """
    pages = [FakePage("http://127.0.0.1:5100/"), FakePage("http://127.0.0.1:5173/")]

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


# --- the overlay is a real app now, not a data: URL --------------------------


def test_the_built_overlay_is_excluded_by_scheme() -> None:
    """Regression: the overlay moved from data: to file: and stopped being
    excluded, so the site view became ambiguous and every Electron run failed."""
    pages = [FakePage(BUILT_OVERLAY), FakePage("http://127.0.0.1:5100/bill/detail")]

    assert find_site_page(pages, "http://127.0.0.1:5102").url.startswith("http://127.0.0.1:5100")


def test_devtools_targets_are_excluded() -> None:
    pages = [FakePage(BUILT_OVERLAY), FakePage("devtools://devtools/bundled/x.html"),
             FakePage("about:blank")]

    assert find_site_page(pages, "http://elsewhere.invalid").url == "about:blank"


def test_a_dev_server_overlay_needs_to_be_named(monkeypatch) -> None:
    """A Vite dev server looks exactly like a website, so scheme cannot rule
    it out. Without SIMBA_OVERLAY_URL it is ambiguous, which is loud."""
    pages = [FakePage(DEV_OVERLAY), FakePage("about:blank")]

    with pytest.raises(NoSiteView, match="could not tell which"):
        find_site_page(pages, "http://elsewhere.invalid")

    monkeypatch.setenv("SIMBA_OVERLAY_URL", DEV_OVERLAY)
    assert find_site_page(pages, "http://elsewhere.invalid").url == "about:blank"
