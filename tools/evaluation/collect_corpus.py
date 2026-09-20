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
before building for it, at thirty-odd pages instead of one. Public pages and
our own replicas — which this starts itself if their ports are free — nothing
behind a real login, nothing submitted. The driven states below open a modal,
a dropdown or a date picker and read the page; none of them sends anything.

A page that fails is recorded as a failure with its reason rather than
dropped, because "this kind of page could not be read" is itself something
the estimator's authors need to know.
"""

import asyncio
import os
import socket
import statistics
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
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

# --- getting a page into the state worth measuring --------------------------
#
# An idle front page is not what this project is for. The features that were
# flat on the first corpus — overlays, inferred controls, dead links — are
# exactly what a run *meets*: a modal it has to dismiss, a dropdown the page
# never declared, a nav of `href="#"`. Several of these pages are therefore
# driven into that state before they are read, which is what the `drive` field
# is for (EVALUATION.md, 2026-09-20b).


async def sign_in(page) -> None:
    """The registration replica's course list, with its modal up."""
    await page.get_by_role("textbox", name="Student ID or Username").fill("student")
    await page.get_by_role("textbox", name="Password").fill("x")
    await page.get_by_role("button", name="Sign In").click()
    await page.wait_for_url("**/courses")


async def open_the_station_list(page) -> None:
    """The live railways search with its options showing: 6 inferred `li`s."""
    box = page.get_by_role("textbox", name="From", exact=True)
    await box.click()
    await box.press_sequentially("LAH")
    await page.wait_for_timeout(1800)


async def open_the_calendar(page) -> None:
    """The same page with the date picker open: 42 inferred day cells."""
    await page.get_by_role("textbox", name="Departure Date", exact=True).click()
    await page.wait_for_timeout(1200)


async def open_a_bootstrap_modal(page) -> None:
    await page.get_by_role("button", name="Launch demo modal").first.click()
    await page.wait_for_timeout(1200)


async def open_an_element_plus_dialog(page) -> None:
    await page.get_by_role("button", name="Click to open the Dialog").first.click()
    await page.wait_for_timeout(1200)


async def open_a_mui_dialog(page) -> None:
    await page.get_by_role("button", name="Open simple dialog").first.click()
    await page.wait_for_timeout(1200)


async def open_an_antd_modal(page) -> None:
    await page.get_by_role("button", name="Open Modal").first.click()
    await page.wait_for_timeout(1200)


async def open_a_sweetalert(page) -> None:
    """A library whose entire product is the overlay."""
    await page.get_by_role("button", name="Try me!").first.click()
    await page.wait_for_timeout(1200)


async def open_a_demoqa_modal(page) -> None:
    await page.get_by_role("button", name="Small modal").click()
    await page.wait_for_timeout(1200)


async def add_a_todo(page) -> None:
    """An app with state in it, rather than an empty one."""
    box = page.get_by_placeholder("What needs to be done?")
    await box.fill("buy tickets")
    await box.press("Enter")
    await page.wait_for_timeout(500)


#: The corpus: `(url, drive, kind)`, ordered roughly by how much each page
#: puts in front of you. The order is a guess — the point of collecting is to
#: find out whether the numbers agree with it — and nothing downstream may
#: assume it.
#:
#: **`kind` is a label on the row, not a judgement of it.** Anything
#: calibrated on this corpus has to be able to ask "how much of this is our
#: own HTML" and "how much of this is a demo site built to be automated", and
#: it can only ask that if every row says which it is:
#:
#:   * `ours` — the two replicas. Pages we wrote, so a feature that separates
#:     them from the world may be measuring our own habits.
#:   * `target` — the live site this project drives, idle and in the two
#:     states its run passes through. The only rows that are the real thing.
#:   * `public` — real pages serving real users, from one paragraph to a wall
#:     of links. Nobody built these to be read by a program.
#:   * `demo` — **sandboxes and component galleries.** Freely readable
#:     application-like pages: demo banks, practice login forms, and
#:     documentation whose dialogs can be opened. These are where a corpus of
#:     public pages gets its modals and its non-semantic controls from, and
#:     they are labelled because they are *not* evidence about the web at
#:     large. A component library's docs page is a page *about* dialogs,
#:     which is not the same thing as a page with a dialog on it, and a
#:     practice form is a form built to be easy to drive.
#:
#: The application-like pages exist because three features were flat on a
#: corpus of front pages (EVALUATION.md, 2026-09-19b). A front page has no
#: modal, no inferred control and no form; a SIMBA run meets all three within
#: two steps.
#:
#: The replicas have to be up: `python replicas/registration/app.py` (:5000)
#: and `python replicas/billing/app.py` (:5100). The collector starts them
#: itself if the ports are free.
REGISTRATION = "http://127.0.0.1:5000"
BILLING = "http://127.0.0.1:5100"
REFERENCE = "04141234567890"

OURS, TARGET, PUBLIC, DEMO = "ours", "target", "public", "demo"

STARTER_LIST: list[tuple[str, object, str]] = [
    # --- ours ---------------------------------------------------------------
    (f"{REGISTRATION}/", None, OURS),
    (f"{REGISTRATION}/", sign_in, OURS),               # the course list, modal up
    (f"{REGISTRATION}/stubborn", None, OURS),          # the rig: 24 dead links
    (f"{BILLING}/", None, OURS),                       # a form as the main event
    (f"{BILLING}/bill?reference={REFERENCE}", None, OURS),   # its result
    # --- the live site, in the states a run passes through -------------------
    ("https://www.pakrailways.gov.pk/train", None, TARGET),
    ("https://www.pakrailways.gov.pk/train", open_the_station_list, TARGET),
    ("https://www.pakrailways.gov.pk/train", open_the_calendar, TARGET),
    # --- public pages, simple to cluttered -----------------------------------
    ("https://example.com/", None, PUBLIC),
    ("http://info.cern.ch/hypertext/WWW/TheProject.html", None, PUBLIC),
    ("https://httpbin.org/html", None, PUBLIC),
    ("https://text.npr.org/", None, PUBLIC),
    ("https://lite.cnn.com/", None, PUBLIC),
    ("https://danluu.com/", None, PUBLIC),
    ("https://quotes.toscrape.com/", None, PUBLIC),
    ("https://books.toscrape.com/", None, PUBLIC),
    ("https://www.python.org/", None, PUBLIC),
    ("https://pypi.org/", None, PUBLIC),
    ("https://developer.mozilla.org/en-US/docs/Web/HTML", None, PUBLIC),
    ("https://en.wikipedia.org/wiki/Cognitive_load", None, PUBLIC),
    ("https://en.wikipedia.org/wiki/Main_Page", None, PUBLIC),
    ("https://www.gov.uk/", None, PUBLIC),
    ("https://www.gov.uk/browse/benefits", None, PUBLIC),
    ("https://www.nhs.uk/", None, PUBLIC),
    ("https://news.ycombinator.com/", None, PUBLIC),
    ("https://arxiv.org/list/cs.HC/recent", None, PUBLIC),
    ("https://www.bbc.co.uk/news", None, PUBLIC),
    # --- demo sites and component galleries ----------------------------------
    #
    # Labelled `demo` rather than `public` deliberately; see `kind` above.
    # These are the rows that carry the corpus's modals, its fields and most
    # of its non-semantic controls.
    ("https://the-internet.herokuapp.com/entry_ad", None, DEMO),  # modal on load
    ("https://the-internet.herokuapp.com/", None, DEMO),          # its index
    ("https://the-internet.herokuapp.com/login", None, DEMO),     # a two-field form
    # http, not https: its certificate expired years ago, and a cert error
    # leaves the tab on chrome-error:// where even about:blank is refused.
    ("http://demo.testfire.net/", None, DEMO),                    # a demo bank
    ("https://parabank.parasoft.com/parabank/index.htm", None, DEMO),  # another
    ("https://demo.applitools.com/", None, DEMO),                 # a demo login
    ("https://opensource-demo.orangehrmlive.com/web/index.php/auth/login",
     None, DEMO),                                                 # an HR app's login
    ("https://www.saucedemo.com/", None, DEMO),                   # a login
    ("https://demo.opencart.com/", None, DEMO),                   # a shop
    ("https://practice.expandtesting.com/", None, DEMO),          # a practice index
    ("https://demoqa.com/automation-practice-form", None, DEMO),  # 15 fields
    ("https://demoqa.com/modal-dialogs", open_a_demoqa_modal, DEMO),
    ("https://todomvc.com/examples/react/dist/", add_a_todo, DEMO),  # an app, with state
    ("https://getbootstrap.com/docs/5.3/components/modal/",
     open_a_bootstrap_modal, DEMO),
    ("https://element-plus.org/en-US/component/dialog.html",
     open_an_element_plus_dialog, DEMO),
    ("https://mui.com/material-ui/react-dialog/", open_a_mui_dialog, DEMO),
    ("https://ant.design/components/modal", open_an_antd_modal, DEMO),
    ("https://sweetalert2.github.io/", open_a_sweetalert, DEMO),
]

#: The features to summarise, in the order the report prints them. After the
#: blank the raw counts the features are built from, kept so a later
#: definition — or a re-merging of `interactive` and `links` — can be computed
#: without reading the pages again.
FEATURES = ["interactive", "links", "inferred", "text_density", "max_depth",
            "overlays", "form_fields", "dead_link_ratio", "reading_grade",
            "link_share", "controls", "dead_links",
            "characters", "viewport_characters", "words", "sentences", "syllables"]

#: The features proper — what an estimator would be built on. The rest of
#: `FEATURES` is working out.
SCORED = FEATURES[:9]

#: Below this share of links among a page's controls, the two counts are
#: saying different things. The corpus put four pages under it, which is why
#: `interactive` and `links` are two features again (EVALUATION.md,
#: 2026-09-20d). Still reported: if a later corpus puts nothing under it, the
#: merge becomes arguable again and the number should say so.
SEPARATES_AT = 0.6

#: A feature whose values barely move cannot tell two pages apart. Flagged at
#: a coefficient of variation below this, and flagged outright when every page
#: gives the same answer. Not a rule about what to drop — a prompt to look.
FLAT_CV = 0.15

#: And flagged when one value covers this share of the corpus. A feature that
#: reads 0 on seventeen pages out of twenty has a large coefficient of
#: variation — the few non-zero pages see to that — and still cannot tell most
#: pages apart, which is the thing being looked for.
SAME_SHARE = 0.75


async def reset(page) -> None:
    """Leave the tab somewhere harmless before the next page.

    A failed navigation — an expired certificate, say — leaves Chromium on
    `chrome-error://chromewebdata/`, and a `goto` issued while that is still
    in flight is itself refused: on 2026-09-20 one dead certificate failed the
    five pages after it as well as itself. So: best effort, a few times, and
    never raise.
    """
    for _ in range(3):
        try:
            await page.goto("about:blank", timeout=8000)
            return
        except PlaywrightError:
            await page.wait_for_timeout(800)


async def read_features(page, url: str, drive=None, kind: str = PUBLIC) -> dict:
    """One page, loaded, driven into the state worth reading, and measured.

    Failures come back as rows too: "this kind of page could not be read" is
    something the estimator's authors need to know, and dropping it would make
    the corpus quietly cheerful.
    """
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=LOAD_TIMEOUT_MS)
        # Let a framework paint and a lazy image or two arrive. Not
        # `networkidle`: an ad-heavy front page never reaches it.
        await page.wait_for_timeout(SETTLE_MS)
        if drive is not None:
            await drive(page)
            await page.wait_for_timeout(600)
        view = await read_async(page, VIEWPORT)
        if view.document is None:
            return {"url": url, "state": name_of(drive), "kind": kind,
                    "error": "no snapshot; are the switches off?"}
        found: PageFeatures = features(view, view.document, VIEWPORT)
        # The ratio the read was taken at, recorded rather than applied: since
        # 2026-09-20 `snapshot.parse` converts the boxes and every length here
        # is CSS pixels. Kept in the row because a corpus should say what the
        # display was doing.
        return {"url": url, "state": name_of(drive), "kind": kind,
                "title": (await page.title())[:80],
                "device_pixel_ratio": view.document.device_pixel_ratio,
                **found.as_dict()}
    except PlaywrightError as refused:
        await reset(page)
        return {"url": url, "state": name_of(drive), "kind": kind,
                "error": f"{type(refused).__name__}: {str(refused)[:120]}"}


def name_of(drive) -> str:
    """What state this row was read in, for a reader of the corpus file."""
    return drive.__name__.replace("_", " ") if drive is not None else "as it loads"


async def in_headless(pages: list[tuple]) -> list[dict]:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        context = await browser.new_context(
            user_agent=UA, viewport={"width": VIEWPORT[0], "height": VIEWPORT[1]})
        page = await context.new_page()
        rows = []
        for url, drive, kind in pages:
            rows.append(await read_features(page, url, drive, kind))
            print(f"  headless {_where(rows[-1])} -> {_say(rows[-1])}", flush=True)
        await browser.close()
        return rows


async def in_host(pages: list[tuple]) -> list[dict]:
    """Through the host's site view — the environment a run actually reads."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.connect_over_cdp(CDP)
        open_pages = [page for context in browser.contexts for page in context.pages]
        site = next((p for p in open_pages
                     if not p.url.startswith(("file:", "devtools:", "chrome:"))), None)
        if site is None:
            raise SystemExit("no site view in the host — is it up? (run.ps1)")
        rows = []
        for url, drive, kind in pages:
            rows.append(await read_features(site, url, drive, kind))
            print(f"  host     {_where(rows[-1])} -> {_say(rows[-1])}", flush=True)
        await browser.close()
        return rows


def _where(row: dict) -> str:
    where = row["url"].replace("https://", "").replace("http://", "")[:46]
    return where if row.get("state") == "as it loads" else f"{where} [{row['state']}]"


def _say(row: dict) -> str:
    if "error" in row:
        return f"FAILED {row['error']}"
    return (f"{row['interactive']} interactive + {row['links']} links "
            f"(share {row['link_share']}), "
            f"{row['inferred']} inferred, {row['overlays']} overlays, "
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
    """Where the same page, in the same state, read differently.

    Keyed by url *and* state: the same URL appears more than once now — idle,
    with its dropdown open, with its calendar open — and pairing on the URL
    alone compared a page with its own driven self.
    """
    by_page = {(row["url"], row.get("state")): row for row in host}
    found = []
    for row in headless:
        other = by_page.get((row["url"], row.get("state")))
        if other is None:
            continue
        if "error" in row or "error" in other:
            if ("error" in row) != ("error" in other):
                found.append({"url": _where(row), "headless": row.get("error", "read"),
                              "host": other.get("error", "read")})
            continue
        gaps = {feature: [row[feature], other[feature]] for feature in FEATURES
                if row[feature] != other[feature]}
        if gaps:
            found.append({"url": _where(row), "differs": gaps})
    return found


@contextmanager
def replicas_running() -> Iterator[None]:
    """The two replicas, started here unless something is already serving them.

    A corpus of public front pages cannot exercise a modal, a dead-link nav or
    a form, and those are what this project is for — so ours are on the list,
    and a script that needs a server should start it rather than fail with a
    connection error.
    """
    started = []
    for name, port in (("registration", 5000), ("billing", 5100)):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                print(f"  (:{port} already serving, leaving it alone)", flush=True)
                continue
        started.append(subprocess.Popen(
            [sys.executable, "app.py"],
            cwd=REPO_ROOT / "replicas" / name,
            env={**os.environ, "PORT": str(port)},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ))
        print(f"  (started the {name} replica on :{port})", flush=True)
    if started:
        time.sleep(3)
    try:
        yield
    finally:
        for process in started:
            process.terminate()
            process.wait(timeout=10)


async def main() -> None:
    arguments = [argument for argument in sys.argv[1:] if argument != "--headless-only"]
    headless_only = "--headless-only" in sys.argv[1:]
    # A URL file carries no labels, so its rows are marked `unlabelled`
    # rather than silently counted as `public`.
    pages = ([(url, None, "unlabelled") for url in
              Path(arguments[0]).read_text(encoding="utf-8").split()]
             if arguments else STARTER_LIST)

    print(banner(), flush=True)
    print(f"{len(pages)} pages, "
          f"{'headless only' if headless_only else 'headless and in the host'}\n",
          flush=True)

    with replicas_running():
        headless = await in_headless(pages)
        host = [] if headless_only else await in_host(pages)

    flat = report("headless", headless)
    if host:
        report("in the host", host)
        gaps = differences(headless, host)
        print(f"\n=== the two environments: {len(gaps)} of {len(pages)} pages differ ===")
        for gap in gaps:
            print(f"  {gap['url']}: "
                  f"{gap.get('differs') or (gap['headless'], gap['host'])}")

    print("\nBarely varies, so of no use to an estimator as it stands:",
          ", ".join(flat) or "nothing")
    made_of = Counter(row.get("kind", "unlabelled") for row in headless)
    print("What the corpus is made of: "
          + ", ".join(f"{count} {kind}" for kind, count in made_of.most_common()))
    # `controls > 0` matters: `link_share` is 0.0 on a page of pure buttons
    # and also on a page with nothing on it, and only the first is evidence.
    separating = [row for row in headless
                  if "error" not in row and row["controls"] > 0
                  and row["link_share"] < SEPARATES_AT]
    empty = [row for row in headless
             if "error" not in row and row["controls"] == 0]
    print(f"Pages where links and controls say different things "
          f"(link_share < {SEPARATES_AT}, of the {len(headless) - len(empty)} "
          f"pages that have any controls): {len(separating)}")
    for row in sorted(separating, key=lambda r: r["link_share"])[:8]:
        print(f"  {_where(row)}: {row['links']} links against "
              f"{row['interactive']} interactive"
              f" (share {row['link_share']})")

    out = REPO_ROOT / "data" / "corpus.json"
    record(out, {"headless": headless, "host": host},
           pages=len(pages), viewport=list(VIEWPORT), settle_ms=SETTLE_MS,
           flat_features=flat, separating_pages=len(separating),
           pages_with_no_controls=len(empty), made_of=dict(made_of))
    print(f"wrote {out}")


if __name__ == "__main__":
    asyncio.run(main())
