"""Where the page the backend drives comes from.

Two sources, one interface:

- **chromium** launches a headless browser of its own. This is what the test
  suite uses and the default, so nothing needs Electron installed to run.
- **electron** attaches over CDP to a running SIMBA host and drives the site
  view inside it — the real architecture, where the page is the hidden
  `WebContentsView` the user never sees directly.

Picking the site view out of the Electron host needs care: the host has two
`WebContentsView`s and both appear as ordinary CDP page targets, and driving
the overlay by mistake would look like every action succeeded while the real
page never moved.

The site view is matched on the URL the host was told to load. Failing that,
pages that cannot be a website are excluded — the overlay is served from
`file:` in a build and `data:` in the old placeholder host, and devtools
targets show up as `devtools:`. `about:blank` is deliberately *not* excluded,
since that is what the site view looks like before it navigates.
"""

import os
from contextlib import asynccontextmanager

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, async_playwright

# 1280x800 is frozen — see CLAUDE.md's architecture constraints.
VIEWPORT = {"width": 1280, "height": 800}
DEFAULT_CDP_URL = "http://127.0.0.1:9222"

# Schemes the site view is never served from. The overlay is one of these.
NOT_A_WEBSITE = ("data:", "file:", "devtools:", "chrome:", "chrome-extension:")


def browser_source() -> str:
    return os.environ.get("SIMBA_BROWSER", "chromium").strip().lower()


def cdp_url() -> str:
    return os.environ.get("SIMBA_CDP_URL", DEFAULT_CDP_URL)


def overlay_url() -> str:
    """Where the overlay is served from, when it cannot be ruled out by scheme.

    Only needed when the overlay runs from a dev server, which looks exactly
    like a website.
    """
    return os.environ.get("SIMBA_OVERLAY_URL", "").strip()


class HostNotRunning(RuntimeError):
    """SIMBA_BROWSER=electron, but nothing is listening on the CDP port."""


class NoSiteView(RuntimeError):
    """Attached to the host, but could not tell which page is the site."""


def find_site_page(pages: list[Page], start_url: str) -> Page:
    """Pick the site view out of the host's pages.

    Tried in order: a page already on the target origin, then any page that
    is not the overlay. The overlay is always a data: URL, so it is the one
    thing that can be ruled out with certainty.
    """
    if not pages:
        raise NoSiteView("the host exposed no pages over CDP")

    origin = _origin(start_url)
    if origin:
        for page in pages:
            if page.url.startswith(origin):
                return page

    overlay = overlay_url()
    candidates = [
        p
        for p in pages
        if not p.url.startswith(NOT_A_WEBSITE)
        and not (overlay and p.url.startswith(overlay))
    ]
    if not candidates:
        raise NoSiteView(
            "every page the host exposed is the overlay or a devtools target, "
            "so none of them is the site view. Is SIMBA_START_URL set on the "
            "host?"
        )
    if len(candidates) > 1:
        urls = ", ".join(p.url[:60] for p in candidates)
        raise NoSiteView(
            f"could not tell which of {len(candidates)} pages is the site "
            f"view: {urls}"
        )
    return candidates[0]


def _origin(url: str) -> str:
    from urllib.parse import urlsplit

    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else ""


@asynccontextmanager
async def open_page(start_url: str):
    """Yield the page to drive, however it is sourced. Cleans up after."""
    source = browser_source()

    async with async_playwright() as playwright:
        if source == "electron":
            url = cdp_url()
            try:
                browser = await playwright.chromium.connect_over_cdp(url)
            except PlaywrightError as error:
                # Playwright reports a bare ECONNREFUSED here, which says
                # nothing about what was expected to be listening.
                raise HostNotRunning(
                    f"no SIMBA host answering on {url}. Start it with "
                    f"`npm start` in frontend/, or set SIMBA_BROWSER=chromium "
                    f"to run without Electron. ({error})"
                ) from error
            try:
                pages = [page for context in browser.contexts for page in context.pages]
                yield find_site_page(pages, start_url)
            finally:
                # Detach only. The host owns its own lifetime and closing the
                # connection must not take the user's window down with it.
                await browser.close()
            return

        if source != "chromium":
            raise RuntimeError(
                f"unknown SIMBA_BROWSER {source!r}; expected 'chromium' or 'electron'"
            )

        browser = await playwright.chromium.launch()
        try:
            yield await browser.new_page(viewport=VIEWPORT)
        finally:
            await browser.close()
