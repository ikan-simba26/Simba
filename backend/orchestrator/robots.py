"""Whether a website's robots.txt lets SIMBA use a page (2026-11-13).

The advisor's direction keeps every rule, and one of them is to respect each
site's robots.txt. Asked once, before the AI planner opens a page nobody
wrote a plan for; a page the site asks programs not to use is never opened
(`goal.answered` `not_allowed`). Our own copies, on this machine, are not
asked.

Read as the standard says: no robots.txt (404) allows everything; a robots.txt
the server refuses to show (401, 403) is read as "no", as `tools/screen_site`
reads it; a site that does not answer in time is read as "no" too — SIMBA
would rather not start than start where it was not allowed.
"""

from __future__ import annotations

import asyncio
import logging
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

log = logging.getLogger("simba.robots")

#: Who SIMBA says it is, to robots.txt. The browser it drives sends its own.
USER_AGENT = "SIMBA"
TIMEOUT_S = 6.0
LOCAL = ("127.0.0.1", "localhost")


def _read(address: str) -> bool:
    parts = urlsplit(address)
    robots = urljoin(f"{parts.scheme}://{parts.netloc}", "/robots.txt")
    parser = RobotFileParser()
    request = urllib.request.Request(robots, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:  # noqa: S310
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            return False
        return True  # no robots.txt: nothing is disallowed
    except (urllib.error.URLError, TimeoutError, OSError):
        return False
    if body.lstrip().lower().startswith(("<!doctype", "<html")):
        return True  # a page, not rules: the site has none
    parser.parse(body.splitlines())
    return parser.can_fetch(USER_AGENT, address)


async def allowed(address: str) -> bool:
    """Whether SIMBA may open `address`. Never raises."""
    if (urlsplit(address).hostname or "") in LOCAL:
        return True
    try:
        verdict = await asyncio.to_thread(_read, address)
    except Exception:  # noqa: BLE001 - an unreadable answer is not permission
        verdict = False
    log.info("robots.txt %s %s", "allows" if verdict else "does not allow",
             urlsplit(address).netloc)
    return verdict
