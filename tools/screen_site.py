"""Screen a site before pointing SIMBA at it.

Run this first, read the table, and only then decide whether to build a flow.
It answers the questions that decide whether a site is a legitimate target
and whether perception stands a chance:

  * does robots.txt allow the paths we would touch, for our user agent
  * does the page load at all, and how long does it take
  * how many interactive elements are there, and how many of them have a
    usable accessible name rather than an id ASP.NET generated
  * is anything covering the page
  * how many links go nowhere

It is read-only by construction: it fetches robots.txt, opens pages, and
serializes them. It never fills a field, never clicks, never submits.

    python -m tools.screen_site https://example.gov/ /search /help

Respecting robots.txt is not optional and not advisory here — a `DISALLOWED`
row means do not build the flow.
"""

import asyncio
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.perception.overlays import COMPUTED_STYLES, analyse  # noqa: E402
from backend.perception.serializer import serialize_async  # noqa: E402

# Identify honestly. A site owner reading their logs should be able to tell
# what this was and stop it if they want to.
USER_AGENT = (
    "SIMBA-screener/0.1 (final-year university project; read-only; "
    "+https://github.com/ikan-simba26/Simba)"
)
VIEWPORT = {"width": 1280, "height": 800}
# Deliberately slow. This is someone's public service, not a load target.
DELAY_BETWEEN_PAGES_S = 3.0


@dataclass
class PageReport:
    url: str
    allowed: bool
    status: str = ""
    load_ms: int = 0
    title: str = ""
    elements: int = 0
    named: int = 0
    unnamed: int = 0
    generated_names: int = 0
    dead_links: int = 0
    overlay: int = 0
    occluded: int = 0
    roles: dict[str, int] = field(default_factory=dict)
    samples: list[str] = field(default_factory=list)


def robots_for(base: str) -> tuple[RobotFileParser, str]:
    """Fetch robots.txt. A site that cannot be read is not one to guess about."""
    root = f"{urlsplit(base).scheme}://{urlsplit(base).netloc}"
    parser = RobotFileParser()
    url = urljoin(root, "/robots.txt")
    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8", "replace")

        # A single-page app answers every path with its index.html, including
        # this one. HTTP 200 is not enough: HTML parsed as robots rules yields
        # no rules at all, which reads as "everything is allowed" when what
        # actually happened is that nothing was stated.
        if body.lstrip()[:1] == "<" or "<html" in body[:400].lower():
            parser.parse([])
            return parser, "(no robots.txt: the server returned HTML, not rules)"

        parser.parse(body.splitlines())
        return parser, body
    except urllib.error.HTTPError as error:
        if error.code in (404, 410):
            # No robots.txt means no restrictions stated.
            parser.parse([])
            return parser, f"(no robots.txt: HTTP {error.code})"
        raise
    except Exception as error:  # noqa: BLE001
        parser.parse([])
        return parser, f"(could not fetch robots.txt: {error})"


def looks_generated(label: str) -> bool:
    """ASP.NET and friends name controls after their server-side control tree.

    `ctl00$ContentPlaceHolder1$txtFrom` tells a planner nothing a person would
    recognise, and is exactly what a WebForms page offers when no label is
    associated with the input.
    """
    if not label:
        return False
    lowered = label.lower()
    markers = ("ctl00", "contentplaceholder", "$", "__", "gridview", "dnn_")
    if any(marker in lowered for marker in markers):
        return True
    # A bare token with no spaces that reads like an identifier.
    return " " not in label and len(label) > 12 and any(c.isdigit() for c in label)


async def screen(base: str, paths: list[str]) -> list[PageReport]:
    from playwright.async_api import async_playwright

    parser, robots_body = robots_for(base)
    print(f"robots.txt for {urlsplit(base).netloc}:")
    for line in robots_body.strip().splitlines()[:20]:
        print(f"    {line}")
    print()

    reports: list[PageReport] = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        context = await browser.new_context(user_agent=USER_AGENT, viewport=VIEWPORT)
        page = await context.new_page()

        for index, path in enumerate(paths):
            url = urljoin(base, path)
            allowed = parser.can_fetch(USER_AGENT, url)
            report = PageReport(url=url, allowed=allowed)

            if not allowed:
                report.status = "DISALLOWED by robots.txt — not fetched"
                reports.append(report)
                continue

            if index:
                await asyncio.sleep(DELAY_BETWEEN_PAGES_S)

            try:
                import time

                started = time.monotonic()
                response = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(1500)  # let scripts settle
                report.load_ms = int((time.monotonic() - started) * 1000)
                report.status = str(response.status if response else "no response")
                report.title = await page.title()
            except Exception as error:  # noqa: BLE001
                report.status = f"failed: {type(error).__name__}"
                reports.append(report)
                continue

            elements = await serialize_async(page)
            report.elements = len(elements)
            report.unnamed = sum(1 for e in elements if not e.label)
            report.generated_names = sum(1 for e in elements if looks_generated(e.label))
            report.named = report.elements - report.unnamed - report.generated_names
            report.dead_links = sum(1 for e in elements if e.dead_link)
            report.overlay = sum(1 for e in elements if e.overlay)
            report.occluded = sum(1 for e in elements if e.occluded)
            for element in elements:
                report.roles[element.role] = report.roles.get(element.role, 0) + 1
            report.samples = [
                f"{e.role} {e.label!r}"
                for e in elements
                if e.type in ("type", "select") or e.role == "button"
            ][:12]

            cdp = await context.new_cdp_session(page)
            await cdp.send("DOMSnapshot.enable")
            snapshot = await cdp.send(
                "DOMSnapshot.captureSnapshot", {"computedStyles": COMPUTED_STYLES}
            )
            await cdp.detach()
            blockers = analyse(snapshot, (VIEWPORT["width"], VIEWPORT["height"])).blockers
            if blockers:
                report.samples.append(f"blocker: {blockers[0].reason}")

            reports.append(report)

        await browser.close()
    return reports


def render(reports: list[PageReport]) -> None:
    print("| page | robots | status | load | elements | named | unnamed | generated | dead links | overlay/occluded |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for r in reports:
        path = urlsplit(r.url).path or "/"
        robots = "allowed" if r.allowed else "**DISALLOWED**"
        print(
            f"| `{path}` | {robots} | {r.status} | {r.load_ms}ms | {r.elements} | "
            f"{r.named} | {r.unnamed} | {r.generated_names} | {r.dead_links} | "
            f"{r.overlay}/{r.occluded} |"
        )

    for r in reports:
        if not r.samples:
            continue
        print(f"\n{urlsplit(r.url).path or '/'} — {r.title!r}")
        print(f"  roles: {r.roles}")
        for sample in r.samples:
            print(f"    {sample}")


def main() -> None:
    # Labels on a real site are not all Latin-1, and a Windows console is.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    if len(sys.argv) < 2:
        raise SystemExit("usage: python -m tools.screen_site BASE_URL [PATH ...]")
    base = sys.argv[1]
    paths = sys.argv[2:] or ["/"]
    render(asyncio.run(screen(base, paths)))


if __name__ == "__main__":
    main()
