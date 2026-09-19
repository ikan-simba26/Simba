"""Raw page features for a list of pages, read in both environments.

The estimator has no corpus, so it has no calibration, so it has no business
having weights (DECISIONS.md, 2026-09-19). This is the collection half:
`backend/estimator/page_features` run over a spread of real pages, from one
that is almost nothing to ones that are a wall of links, writing the raw
numbers to `data/corpus.json` for whoever builds the score later.

**Both environments**, per the rule from 2026-09-18c: each page is read in a
headless Chromium *and* through the Electron host's site view, and both rows
are kept. One defect has already existed only in the host, and a corpus
collected in the environment the product does not run in is a corpus of
something else. The two are not identical by construction — the host sends
Electron's user agent and this script sends the project's screening one — and
where a page treats them differently, the rows say so.

Run the host first if you want that half:

    .\\run.ps1 registration       # or any flow; only the site view is used

then, from the repo root:

    python -m tools.evaluation.collect_corpus                  # the starter list
    python -m tools.evaluation.collect_corpus urls.txt         # one URL per line
    python -m tools.evaluation.collect_corpus --headless-only  # no host needed

**What it costs.** One page load per page per environment, read-only, no
model. It is the same thing `tools/screen_site.py` does to look at a site
before building for it, at twenty pages instead of one. Public pages only,
nothing behind a login, nothing submitted. Some sites refuse automated
browsers outright; a page that fails is recorded as a failure with its reason
rather than dropped, because "this kind of page could not be read" is itself
something the estimator's authors need to know.
"""

import asyncio
import statistics
import sys
from collections import Counter
from pathlib import Path

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from backend.estimator.page_features import PageFeatures, features
from backend.perception.serializer import VIEWPORT, read_async
from tools.evaluation.conditions import banner, record

REPO_ROOT = Path(__file__).resolve().parents[2]
CDP = "http://127.0.0.1:9222"
UA = ("SIMBA-screener/0.1 (final-year university project; read-only; "
      "+https://github.com/ikan-simba26/Simba)")
SETTLE_MS = 2500
LOAD_TIMEOUT_MS = 45000

#: Twenty public pages, ordered by how much they put in front of you — from a
#: page with one paragraph on it to a front page that is mostly links. The
#: order is a guess and the point of collecting is to find out whether the
#: numbers agree with it; nothing downstream may assume this ranking.
#:
#: Chosen to vary the things the features measure rather than the subject
#: matter: text-only pages against link walls, forms against articles, plain
#: HTML against framework-rendered apps, and one page — the railways search —
#: that this project already drives, so the corpus contains at least one page
#: whose behaviour is documented elsewhere in EVALUATION.md.
STARTER_LIST = [
    "https://example.com/",
    "http://info.cern.ch/hypertext/WWW/TheProject.html",
    "https://httpbin.org/html",
    "https://text.npr.org/",
    "https://lite.cnn.com/",
    "https://danluu.com/",
    "https://www.pakrailways.gov.pk/train",
    "https://quotes.toscrape.com/",
    "https://books.toscrape.com/",
    "https://www.python.org/",
    "https://pypi.org/",
    "https://developer.mozilla.org/en-US/docs/Web/HTML",
    "https://en.wikipedia.org/wiki/Cognitive_load",
    "https://en.wikipedia.org/wiki/Main_Page",
    "https://www.gov.uk/",
    "https://www.gov.uk/browse/benefits",
    "https://www.nhs.uk/",
    "https://news.ycombinator.com/",
    "https://arxiv.org/list/cs.HC/recent",
    "https://www.bbc.co.uk/news",
]

#: The features to summarise, in the order the report prints them. The last
#: five are the raw counts the derived two are built from, kept so a later
#: definition of density or grade can be computed without reading the pages
#: again.
FEATURES = ["interactive", "inferred", "text_density", "max_depth", "overlays",
            "form_fields", "links", "dead_link_ratio", "reading_grade",
            "characters", "viewport_characters", "words", "sentences", "syllables"]

#: A feature whose values barely move cannot tell two pages apart. Flagged at
#: a coefficient of variation below this, and flagged outright when every page
#: gives the same answer. Not a rule about what to drop — a prompt to look.
FLAT_CV = 0.15

#: And flagged when one value covers this share of the corpus. A feature that
#: reads 0 on seventeen pages out of twenty has a large coefficient of
#: variation — the few non-zero pages see to that — and still cannot tell most
#: pages apart, which is the thing being looked for.
SAME_SHARE = 0.75


async def read_features(page, url: str) -> dict:
    """One page, loaded and measured. Failures come back as rows too."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=LOAD_TIMEOUT_MS)
        # Let a framework paint and a lazy image or two arrive. Not
        # `networkidle`: an ad-heavy front page never reaches it.
        await page.wait_for_timeout(SETTLE_MS)
        view = await read_async(page, VIEWPORT)
        if view.document is None:
            return {"url": url, "error": "no snapshot; are the switches off?"}
        found: PageFeatures = features(view, view.document, VIEWPORT)
        # The ratio the read was taken at, recorded rather than applied: since
        # 2026-09-20 `snapshot.parse` converts the boxes and every length here
        # is CSS pixels. Kept in the row because a corpus should say what the
        # display was doing.
        return {"url": url, "title": (await page.title())[:80],
                "device_pixel_ratio": view.document.device_pixel_ratio,
                **found.as_dict()}
    except PlaywrightError as refused:
        return {"url": url, "error": f"{type(refused).__name__}: {str(refused)[:120]}"}


async def in_headless(urls: list[str]) -> list[dict]:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        context = await browser.new_context(
            user_agent=UA, viewport={"width": VIEWPORT[0], "height": VIEWPORT[1]})
        page = await context.new_page()
        rows = []
        for url in urls:
            rows.append(await read_features(page, url))
            print(f"  headless {url} -> {_say(rows[-1])}", flush=True)
        await browser.close()
        return rows


async def in_host(urls: list[str]) -> list[dict]:
    """Through the host's site view — the environment a run actually reads."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.connect_over_cdp(CDP)
        pages = [page for context in browser.contexts for page in context.pages]
        site = next((p for p in pages
                     if not p.url.startswith(("file:", "devtools:", "chrome:"))), None)
        if site is None:
            raise SystemExit("no site view in the host — is it up? (.\\run.ps1)")
        rows = []
        for url in urls:
            rows.append(await read_features(site, url))
            print(f"  host     {url} -> {_say(rows[-1])}", flush=True)
        await browser.close()
        return rows


def _say(row: dict) -> str:
    if "error" in row:
        return f"FAILED {row['error']}"
    return (f"{row['interactive']} interactive, {row['links']} links, "
            f"density {row['text_density']}, grade {row['reading_grade']}")


# --- what came back ---------------------------------------------------------


def spread(rows: list[dict], name: str) -> dict | None:
    """Min, median, max and coefficient of variation for one feature."""
    values = [row[name] for row in rows if "error" not in row]
    if not values:
        return None
    mean = statistics.fmean(values)
    deviation = statistics.pstdev(values)
    commonest, appearances = Counter(values).most_common(1)[0]
    return {
        "min": min(values), "median": round(statistics.median(values), 3),
        "max": max(values), "mean": round(mean, 3),
        "cv": round(deviation / mean, 3) if mean else 0.0,
        "distinct": len(set(values)),
        "pages": len(values),
        "commonest": commonest,
        "commonest_pages": appearances,
        "commonest_share": round(appearances / len(values), 3),
    }


def report(name: str, rows: list[dict]) -> list[str]:
    """Print the spread of every feature. Returns the ones worth a second look."""
    good = [row for row in rows if "error" not in row]
    print(f"\n=== {name}: {len(good)} pages read, {len(rows) - len(good)} failed ===")
    print(f"{'feature':<22}{'min':>12}{'median':>12}{'max':>12}{'cv':>8}{'distinct':>10}")
    flat = []
    for feature in FEATURES:
        found = spread(rows, feature)
        if found is None:
            continue
        mark = ""
        if found["distinct"] <= 1:
            mark = " <- ONE VALUE ONLY"
            flat.append(feature)
        elif found["commonest_share"] >= SAME_SHARE:
            mark = (f" <- {found['commonest']} on {found['commonest_pages']}"
                    f" of {found['pages']} pages")
            flat.append(feature)
        elif found["cv"] < FLAT_CV:
            mark = f" <- barely varies (cv {found['cv']})"
            flat.append(feature)
        print(f"{feature:<22}{found['min']:>12}{found['median']:>12}"
              f"{found['max']:>12}{found['cv']:>8}{found['distinct']:>10}{mark}")
    return flat


def differences(headless: list[dict], host: list[dict]) -> list[dict]:
    """Where the same page read differently in the two environments."""
    by_url = {row["url"]: row for row in host}
    found = []
    for row in headless:
        other = by_url.get(row["url"])
        if other is None:
            continue
        if "error" in row or "error" in other:
            if ("error" in row) != ("error" in other):
                found.append({"url": row["url"], "headless": row.get("error", "read"),
                              "host": other.get("error", "read")})
            continue
        gaps = {feature: [row[feature], other[feature]] for feature in FEATURES
                if row[feature] != other[feature]}
        if gaps:
            found.append({"url": row["url"], "differs": gaps})
    return found


async def main() -> None:
    arguments = [argument for argument in sys.argv[1:] if argument != "--headless-only"]
    headless_only = "--headless-only" in sys.argv[1:]
    urls = (Path(arguments[0]).read_text(encoding="utf-8").split()
            if arguments else STARTER_LIST)

    print(banner(), flush=True)
    print(f"{len(urls)} pages, "
          f"{'headless only' if headless_only else 'headless and in the host'}\n",
          flush=True)

    headless = await in_headless(urls)
    host = [] if headless_only else await in_host(urls)

    flat = report("headless", headless)
    if host:
        report("in the host", host)
        gaps = differences(headless, host)
        print(f"\n=== the two environments: {len(gaps)} of {len(urls)} pages differ ===")
        for gap in gaps:
            print(f"  {gap['url']}: "
                  f"{gap.get('differs') or (gap['headless'], gap['host'])}")

    print("\nBarely varies, so of no use to an estimator as it stands:",
          ", ".join(flat) or "nothing")

    out = REPO_ROOT / "data" / "corpus.json"
    record(out, {"headless": headless, "host": host},
           pages=len(urls), viewport=list(VIEWPORT), settle_ms=SETTLE_MS,
           flat_features=flat)
    print(f"wrote {out}")


if __name__ == "__main__":
    asyncio.run(main())
