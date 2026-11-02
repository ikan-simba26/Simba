"""How overwhelming are Pakistan's public websites, and why?

The trained page model (`backend/estimator/page_model.py`) put to a question it
was not built for: not "how should this step be shown" but "what is this
country's public web like for someone who finds cluttered pages hard". About 40
main pages, across seven kinds of service.

    python -m tools.evaluation.overwhelm_index

**Read-only, and one visit each.** robots.txt first, for the same user agent the
page is then fetched with, and a page it forbids is never opened. Nothing is
clicked, filled or submitted, nothing is retried, and there is a pause between
sites. It touches live sites, so it is not a benchmark and is not for repeating
(CLAUDE.md).

**The same pipeline as the pictures people rated.** `tools/rating/capture.photograph`
loads the page, waits as it did, hides scrollbars, reads the nine features and
takes the picture of the first 1280x800 from one load. A score for a page taken
some other way would not be a score from this model.

**Two levels, and they are not the same.** `page_band` is the model's own: 1
calm, 2 middle, 3 heavy. `simba_level` is what SIMBA would do, from the real
`rules.LevelRules` for a person who has chosen nothing: the page can start them
simpler and never fuller, so a calm page still opens at level 2.

**A score is only reported for a page that is one.** A firewall's refusal or a
"Just a moment..." challenge is a short, plain page, which this model calls calm;
one of those at the bottom of the table would be a false finding about a site
nobody read. So a page with an error status, a refusal in its words, a sign-in
page, or next to nothing on it is listed as failed, with why, and never ranked.

**A score is not a verdict on a picture the model cannot see.** It reads text,
counts and structure, and knows nothing of images, so words baked into a banner
are no words at all, and its weight on something covering the page is +0.004.
On the first pass 35 of 36 pages came out below the average rated page, while
the pictures were plainly busy (EVALUATION.md, 2026-11-02b). So a reason is
always shown with its direction: what pushes a page up, and what holds it down.
The model's own `reasons` follow the way its score went, and on a page below the
average they say why it scored low, not why it is overwhelming.

**A first screen still empty is not a calm page.** K-Electric ranked last at 1.13
with 9,566 characters on the page and only a menu showing, its content not yet
animated in. Text counts cannot see that, so the picture itself is measured:
`FLAT_LIMIT`, set from that run's 36 pictures.

**robots.txt that cannot be read is not permission.** `screen_site.robots_for`
treats an unreadable file as no rules, and raises on a refusal. Here a refused or
unreachable file means the site is skipped (RFC 9309, for an unreachable one).
Python's TLS is stricter than Chromium's about an incomplete certificate chain,
so a file `urllib` could not reach gets one more try in the browser first.

Writes to `.scratch/overwhelm-index/`, none of it committed: `overwhelm_index.csv`,
`report.md`, `results.json` with the conditions, and `screenshots/`, which are
pictures of other people's sites.

    python -m tools.evaluation.overwhelm_index --report

works the table and the report out again from what was saved. It visits nothing:
the only browser it opens is on this machine, to read the saved pictures.
"""

from __future__ import annotations

import asyncio
import base64
import csv
import dataclasses
import hashlib
import json
import re
import statistics
import sys
import urllib.error
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Awaitable, Callable
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, async_playwright

from backend.estimator import page_model
from backend.estimator.page_features import PageFeatures
from backend.estimator.page_model import FEATURES, SMALLEST_REASON, TOP, PageModel
from backend.estimator.rules import LevelRules
from tools.evaluation.collect_corpus import UA, reset
from tools.evaluation.conditions import banner, conditions, record
from tools.rating.capture import VIEWPORT, new_run, page_id, photograph
from tools.screen_site import DELAY_BETWEEN_PAGES_S, USER_AGENT, robots_for

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / ".scratch" / "overwhelm-index"
CORPUS = REPO / "data" / "corpus.json"

#: Fewer characters than this, with fewer things to press than `THIN_CONTROLS`,
#: is not a page that has been read: a splash, or a script that never ran.
THIN_CHARACTERS = 200
THIN_CONTROLS = 5
#: Reasons in the report.
TOP_REASONS = 3
#: A first screen with this share of its pixels one colour has nothing on it to
#: judge. Set from the 36 pictures of 2026-11-02 (EVALUATION.md, 2026-11-02b).
FLAT_LIMIT = 0.97
#: The model's error on pages it had not seen, in points of the 1-5 scale
#: (EVALUATION.md, 2026-10-30). Ranks closer than this are not a difference.
HELD_OUT_ERROR = 0.48


@dataclass(frozen=True)
class Site:
    name: str
    category: str
    url: str
    why: str


GOVERNMENT = "Government services"
UTILITY = "Utilities"
UNIVERSITY = "Universities"
BANK = "Banks"
TELECOM = "Telecoms"
TRANSPORT = "Transport"
HEALTH = "Health"

SITES: tuple[Site, ...] = (
    Site("Pakistan national portal", GOVERNMENT, "https://www.pakistan.gov.pk/",
         "The federal government's front door"),
    Site("NADRA", GOVERNMENT, "https://www.nadra.gov.pk/",
         "National identity cards, which everything else asks for"),
    Site("FBR", GOVERNMENT, "https://www.fbr.gov.pk/", "Tax, for every filer"),
    Site("Directorate of Passports", GOVERNMENT, "https://www.dgip.gov.pk/",
         "Passports and their appointments"),
    Site("Government of Punjab", GOVERNMENT, "https://punjab.gov.pk/",
         "The largest province's portal"),
    Site("Government of Sindh", GOVERNMENT, "https://www.sindh.gov.pk/",
         "Provincial services for Karachi and Sindh"),
    Site("Government of Khyber Pakhtunkhwa", GOVERNMENT, "https://kp.gov.pk/",
         "Provincial services"),
    Site("Election Commission", GOVERNMENT, "https://www.ecp.gov.pk/",
         "Voter registration and polling information"),
    Site("Benazir Income Support", GOVERNMENT, "https://www.bisp.gov.pk/",
         "Cash support, used by people with the least help to hand"),
    Site("LESCO", UTILITY, "https://www.lesco.gov.pk/", "Electricity for Lahore"),
    Site("IESCO", UTILITY, "https://www.iesco.com.pk/", "Electricity for Islamabad"),
    Site("K-Electric", UTILITY, "https://www.ke.com.pk/", "Electricity for Karachi"),
    Site("MEPCO", UTILITY, "https://www.mepco.com.pk/", "Electricity for southern Punjab"),
    Site("SNGPL", UTILITY, "https://www.sngpl.com.pk/", "Gas for the north"),
    Site("SSGC", UTILITY, "https://www.ssgc.com.pk/", "Gas for the south"),
    Site("Karachi Water", UTILITY, "https://www.kwsc.gos.pk/", "Water for Karachi"),
    Site("WASA Lahore", UTILITY, "https://wasa.punjab.gov.pk/", "Water for Lahore"),
    Site("University of the Punjab", UNIVERSITY, "https://pu.edu.pk/",
         "One of the largest public universities"),
    Site("University of Karachi", UNIVERSITY, "https://www.uok.edu.pk/",
         "Karachi's large public university"),
    Site("Quaid-i-Azam University", UNIVERSITY, "https://qau.edu.pk/",
         "A federal public university"),
    Site("NUST", UNIVERSITY, "https://nust.edu.pk/", "A public engineering university"),
    Site("LUMS", UNIVERSITY, "https://lums.edu.pk/", "A private university, for contrast"),
    Site("Higher Education Commission", UNIVERSITY, "https://www.hec.gov.pk/",
         "Degrees and scholarships, for every student"),
    Site("HBL", BANK, "https://www.hbl.com/", "The largest bank"),
    Site("National Bank of Pakistan", BANK, "https://www.nbp.com.pk/",
         "The state bank, which pays many pensions"),
    Site("MCB", BANK, "https://www.mcb.com.pk/", "A large private bank"),
    Site("Bank Alfalah", BANK, "https://www.bankalfalah.com/", "A large private bank"),
    Site("Meezan Bank", BANK, "https://www.meezanbank.com/", "The largest Islamic bank"),
    Site("Jazz", TELECOM, "https://jazz.com.pk/", "The largest mobile network"),
    Site("Zong", TELECOM, "https://www.zong.com.pk/", "A large mobile network"),
    Site("Telenor Pakistan", TELECOM, "https://www.telenor.com.pk/", "A large mobile network"),
    Site("Ufone", TELECOM, "https://www.ufone.com/", "A large mobile network"),
    Site("PTCL", TELECOM, "https://ptcl.com.pk/", "Landlines and home internet"),
    Site("Pakistan Railways", TRANSPORT, "https://www.pakrailways.gov.pk/",
         "Trains, and the live site SIMBA already reads"),
    Site("PIA", TRANSPORT, "https://www.piac.com.pk/", "The national airline"),
    Site("National Highway Authority", TRANSPORT, "https://nha.gov.pk/",
         "Roads, tolls and motorway information"),
    Site("Daewoo Express", TRANSPORT, "https://daewoo.com.pk/", "The main intercity coaches"),
    Site("National Institute of Health", HEALTH, "https://www.nih.org.pk/",
         "Public health advisories"),
    Site("PIMS Hospital", HEALTH, "https://pims.gov.pk/", "A large public hospital, Islamabad"),
    Site("Shaukat Khanum", HEALTH, "https://shaukatkhanum.org.pk/",
         "A charitable cancer hospital, widely used"),
    Site("Aga Khan University Hospital", HEALTH, "https://hospitals.aku.edu/",
         "A large private hospital, Karachi"),
    Site("Drug Regulatory Authority", HEALTH, "https://www.dra.gov.pk/",
         "Medicine prices and recalls"),
)


# --- robots.txt --------------------------------------------------------------


@dataclass(frozen=True)
class Robots:
    allowed: bool
    note: str


def permitted(parser: RobotFileParser, url: str, note: str = "") -> Robots:
    allowed = parser.can_fetch(USER_AGENT, url)
    return Robots(allowed, note if allowed else "disallowed by robots.txt")


def from_python(url: str, fetch=robots_for) -> Robots | None:
    """What robots.txt says, by the screener's own fetch; None when that could
    not read it, so that the browser can try."""
    try:
        parser, said = fetch(url)
    except urllib.error.HTTPError as error:
        return refused(error.code)
    if said.startswith("(could not fetch"):
        return None
    return permitted(parser, url, said if said.startswith("(no robots.txt") else "")


def refused(status: int) -> Robots | None:
    """A refused file is a no; a server in trouble says nothing, so the caller
    is left to treat it as unreachable."""
    if status in (401, 403):
        return Robots(False, f"robots.txt refused: HTTP {status}")
    return None


def from_browser(status: int, body: str, url: str) -> Robots:
    """The same reading, of an answer the browser got."""
    if status in (404, 410):
        return Robots(True, f"(no robots.txt: HTTP {status})")
    if status >= 400:
        return refused(status) or Robots(False, f"robots.txt unreachable: HTTP {status}")
    parser = RobotFileParser()
    if body.lstrip()[:1] == "<" or "<html" in body[:400].lower():
        parser.parse([])
        return permitted(parser, url, "(no robots.txt: the server returned HTML, not rules)")
    parser.parse(body.splitlines())
    return permitted(parser, url)


async def robots(page: Page, url: str, fetch=robots_for) -> Robots:
    """Whether this page may be opened. Never True by default: a file nobody
    could read is a site skipped."""
    answer = await asyncio.to_thread(from_python, url, fetch)
    if answer is not None:
        return answer
    parts = urlsplit(url)
    address = urljoin(f"{parts.scheme}://{parts.netloc}", "/robots.txt")
    try:
        response = await page.goto(address, wait_until="domcontentloaded", timeout=20000)
        if response is None:
            return Robots(False, "robots.txt unreachable: no response")
        return from_browser(response.status, await response.text(), url)
    except PlaywrightError as error:
        return Robots(False, f"robots.txt unreachable: {first_line(error)}")
    finally:
        await reset(page)


def first_line(error: BaseException) -> str:
    return (str(error).splitlines() or [type(error).__name__])[0][:120]


# --- whether what came back is a page ----------------------------------------


REFUSAL = re.compile(
    r"just a moment|attention required|checking your browser|access denied|forbidden"
    r"|not acceptable|request (was )?rejected|requested url was rejected|web page blocked"
    r"|service unavailable|bad gateway|gateway time-?out|under maintenance|site maintenance"
    r"|page not found|\b40[134]\b|\b50[0234]\b", re.IGNORECASE)
SIGN_IN = re.compile(r"(^|[/_.-])(log-?in|sign-?in|auth(enticate)?|sso)([/_.?-]|$)", re.IGNORECASE)


def not_a_page(status: int | None, title: str, text: str, final_url: str,
               row: dict[str, Any]) -> str | None:
    """Why what came back should not be scored; None if it should."""
    if status is not None and status >= 400:
        return f"HTTP {status}"
    if REFUSAL.search(title) or REFUSAL.search(text[:300]):
        return f"a refusal or error page: {title[:60] or text[:60]!r}"
    if SIGN_IN.search(urlsplit(final_url).path):
        return f"landed on a sign-in page: {urlsplit(final_url).path}"
    controls = int(row.get("interactive", 0)) + int(row.get("links", 0))
    if int(row.get("characters", 0)) < THIN_CHARACTERS and controls < THIN_CONTROLS:
        return "next to nothing on the page to read"
    return None


#: The largest share of a picture's pixels that are one colour, to 4 bits a channel.
FLAT_JS = """async (address) => {
    const picture = new Image();
    picture.src = address;
    await picture.decode();
    const canvas = document.createElement('canvas');
    canvas.width = picture.width;
    canvas.height = picture.height;
    const paint = canvas.getContext('2d', {willReadFrequently: true});
    paint.drawImage(picture, 0, 0);
    const {data} = paint.getImageData(0, 0, canvas.width, canvas.height);
    const counts = new Map();
    for (let at = 0; at < data.length; at += 4) {
        const key = (data[at] >> 4) << 8 | (data[at + 1] >> 4) << 4 | data[at + 2] >> 4;
        counts.set(key, (counts.get(key) || 0) + 1);
    }
    return Math.max(...counts.values()) / (data.length / 4);
}"""


async def flat_share(page: Page, png: bytes) -> float:
    """How much of a picture is one colour, read in the browser, since nothing
    here can decode a PNG. The picture is passed in, so nothing is fetched."""
    address = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    return round(float(await page.evaluate(FLAT_JS, address)), 4)


def empty_screen(flat: float) -> str | None:
    """Why a first screen is not worth scoring, or None."""
    if flat >= FLAT_LIMIT:
        return f"first screen still empty when read ({flat:.0%} one colour)"
    return None


def urdu_share(text: str) -> float:
    """How much of a page's letters are Arabic script. Reading grade is a
    formula for English, so on a page mostly in Urdu that feature says nothing."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return round(sum("؀" <= c <= "ۿ" or "ﭐ" <= c <= "ﻼ" for c in letters)
                 / len(letters), 3)


def corpus_ranges(path: Path = CORPUS) -> dict[str, tuple[float, float]]:
    """The smallest and largest of each feature among the pages people rated."""
    rows = json.loads(path.read_text(encoding="utf-8"))["results"]["headless"]
    rows = [row for row in rows if "error" not in row]
    return {name: (min(float(row[name]) for row in rows), max(float(row[name]) for row in rows))
            for name in FEATURES}


def outside(row: dict[str, Any], ranges: dict[str, tuple[float, float]]) -> list[str]:
    """Features past anything the model was trained on: a score there is the
    line carried on past its data."""
    return [name for name in FEATURES
            if not ranges[name][0] <= float(row[name]) <= ranges[name][1]]


# --- the score ---------------------------------------------------------------


def moved(row: dict[str, Any], model: PageModel) -> dict[str, list[str]]:
    """What pushes this page's score up and what holds it down, each in the
    model's own words, biggest first. The model's own `reasons` give only the
    way the score went; a question about why needs both."""
    found = SimpleNamespace(**{name: row[name] for name in FEATURES})
    by_feature = model.contributions(found)  # type: ignore[arg-type]

    def words(sign: int) -> list[str]:
        chosen = sorted(((name, by) for name, by in by_feature.items()
                         if by * sign >= SMALLEST_REASON),
                        key=lambda item: abs(item[1]), reverse=True)[:TOP]
        return [model._word(name, found) for name, _ in chosen]  # type: ignore[arg-type]

    return {"pushed_up_by": words(1), "held_down_by": words(-1)}


def judged(row: dict[str, Any], model: PageModel) -> dict[str, Any]:
    """The model's score and reasons for one page, and the level the real rules
    choose from it for a person who has set none."""
    found = PageFeatures(**{field.name: row[field.name] for field in dataclasses.fields(PageFeatures)})
    judgement = model.judge(found)
    decision = LevelRules(page_model=model).start_step(0, found)
    return {"rating": judgement.rating, "score": judgement.score,
            "page_band": judgement.level, "simba_level": decision.level,
            "reasons": list(judgement.reasons), **moved(row, model)}


# --- one site ----------------------------------------------------------------


def blank(site: Site, status: str, why: str = "") -> dict[str, Any]:
    return {"site": site.name, "category": site.category, "url": site.url, "why": site.why,
            "status": status, "note": why}


async def measure(page: Page, site: Site, run: dict, model: PageModel,
                  ranges: dict[str, tuple[float, float]], into: Path,
                  fetch=robots_for) -> dict[str, Any]:
    """One site, one visit: "scored", "failed" or "skipped", and never raises."""
    answer = await robots(page, site.url, fetch)
    if not answer.allowed:
        return blank(site, "skipped", answer.note)

    statuses: list[int] = []

    def seen(response: Any) -> None:
        try:
            if response.request.is_navigation_request() and response.frame == page.main_frame:
                statuses.append(response.status)
        except PlaywrightError:
            pass

    page.on("response", seen)
    try:
        shot, row = await photograph(page, site.url, None, site.category, run, into)
        if "error" in shot:
            return blank(site, "failed", shot["error"])
        final_url = page.url
        text = await page.evaluate("document.body ? document.body.innerText : ''")
        status = statuses[-1] if statuses else None
        refusal = not_a_page(status, shot.get("title", ""), text, final_url, row)
        if refusal:
            (into / shot["file"]).unlink(missing_ok=True)
            return blank(site, "failed", refusal)
        flat = await flat_share(page, (into / shot["file"]).read_bytes())
        empty = empty_screen(flat)
        if empty:
            return {**blank(site, "failed", empty), "screenshot": shot["file"]}
        return {
            **blank(site, "scored", answer.note), **judged(row, model),
            "final_url": final_url, "title": shot["title"], "http_status": status,
            "flat_share": flat,
            "layout_width": shot["layout_width"], "urdu_share": urdu_share(text),
            "outside_corpus": outside(row, ranges), "screenshot": shot["file"],
            "sha256": shot["sha256"], "characters": row["characters"],
            **{name: row[name] for name in FEATURES},
        }
    except Exception as error:  # noqa: BLE001 - one site must not stop the rest
        return blank(site, "failed", f"{type(error).__name__}: {first_line(error)}")
    finally:
        page.remove_listener("response", seen)
        await reset(page)


async def survey(sites: tuple[Site, ...], model: PageModel, into: Path, fetch=robots_for,
                 pause_s: float = DELAY_BETWEEN_PAGES_S) -> tuple[list[dict], str]:
    """Every site in turn, and the browser's version for the conditions."""
    into.mkdir(parents=True, exist_ok=True)
    ranges = corpus_ranges()
    run = new_run()
    rows: list[dict] = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(args=["--hide-scrollbars"])
        # As `tools/rating/capture.py` has it, so a page here is read as a rated
        # page was. `bypass_csp` is for the scrollbar style and changes nothing else.
        context = await browser.new_context(user_agent=UA, viewport=VIEWPORT,
                                             device_scale_factor=1, bypass_csp=True)
        page = await context.new_page()
        for index, site in enumerate(sites):
            if index:
                await asyncio.sleep(pause_s)
            row = await measure(page, site, run, model, ranges, into, fetch)
            rows.append(row)
            said = f"{row['rating']:.2f}" if row["status"] == "scored" else row["note"]
            print(f"  {site.name[:34]:<34} {row['status']:<8} {said}", flush=True)
        version = browser.version
        await browser.close()
    return rows, version


# --- what it adds up to ------------------------------------------------------


def ranked(rows: list[dict]) -> list[dict]:
    """The scored pages, most overwhelming first; a tie goes by name."""
    return sorted((row for row in rows if row["status"] == "scored"),
                  key=lambda row: (-row["rating"], row["site"]))


def by_category(rows: list[dict]) -> list[dict]:
    """Each category's mean, highest first. Only pages that were scored count."""
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(row["category"], []).append(row)
    out = []
    for category, members in groups.items():
        scored = [row for row in members if row["status"] == "scored"]
        if not scored:
            out.append({"category": category, "listed": len(members), "scored": 0,
                        "mean": None, "heavy": 0})
            continue
        out.append({"category": category, "listed": len(members), "scored": len(scored),
                    "mean": round(sum(row["rating"] for row in scored) / len(scored), 2),
                    "heavy": sum(row["page_band"] == 3 for row in scored)})
    return sorted(out, key=lambda group: (group["mean"] is None, -(group["mean"] or 0)))


def plain_reason(reason: str) -> str:
    """A reason without its count: "many links (240)" is "many links"."""
    return re.sub(r"\s*\(\d+\)$", "", reason)


def common_reasons(rows: list[dict], top: int = TOP_REASONS) -> list[tuple[str, int]]:
    return Counter(plain_reason(reason) for row in rows if row["status"] == "scored"
                   for reason in row["reasons"]).most_common(top)


def rederive(rows: list[dict], model: PageModel, flat_of: Callable[[str], float]) -> list[dict]:
    """The rows again from what was saved, with today's checks and words, and
    no visit to anything: `flat_of` reads a saved picture."""
    out = []
    for row in rows:
        if row["status"] != "scored":
            out.append(row)
            continue
        flat = flat_of(row["screenshot"])
        empty = empty_screen(flat)
        if empty:
            out.append({**blank(Site(row["site"], row["category"], row["url"], row["why"]),
                                "failed", empty),
                        "screenshot": row["screenshot"], "was_scored": row["rating"]})
        else:
            out.append({**row, **moved(row, model), "flat_share": flat})
    return out


def compared(rows: list[dict], model: PageModel, path: Path = CORPUS) -> dict[str, Any]:
    """These pages beside the public pages people rated, by the same model."""
    corpus = json.loads(path.read_text(encoding="utf-8"))["results"]["headless"]
    public = [row for row in corpus if row.get("kind") == "public" and "error" not in row]
    fields = PageFeatures.__dataclass_fields__
    judgements = [model.judge(PageFeatures(**{name: row[name] for name in fields}))
                  for row in public]
    order = ranked(rows)
    return {
        "average_page": round(model.intercept, 2),
        "below_average": sum(row["rating"] < model.intercept for row in order),
        "public_median": round(statistics.median(j.rating for j in judgements), 2),
        "public_heavy": sum(j.level == 3 for j in judgements),
        "public_pages": len(public),
        "median": round(statistics.median(row["rating"] for row in order), 2),
        "heavy": sum(row["page_band"] == 3 for row in order),
        "public_density": round(statistics.median(float(r["text_density"]) for r in public), 2),
        "density": round(statistics.median(float(r["text_density"]) for r in order), 2),
        "covered": sum(int(row["overlays"]) > 0 for row in order),
    }


COLUMNS = ("rank", "site", "category", "rating", "score", "page_band", "simba_level",
           "reason_1", "reason_2", "reason_3", "pushed_up_by", "held_down_by", *FEATURES,
           "urdu_share", "flat_share", "outside_corpus", "url", "final_url", "title",
           "http_status", "screenshot", "sha256")


def write_csv(rows: list[dict], path: Path) -> None:
    """The ranked pages. UTF-8 with a mark, so a spreadsheet reads a title in Urdu."""
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for rank, row in enumerate(ranked(rows), 1):
            reasons = (row["reasons"] + ["", "", ""])[:3]
            writer.writerow({**row, "rank": rank, "reason_1": reasons[0], "reason_2": reasons[1],
                             "reason_3": reasons[2],
                             "pushed_up_by": "; ".join(row.get("pushed_up_by", [])),
                             "held_down_by": "; ".join(row.get("held_down_by", [])),
                             "outside_corpus": "; ".join(row["outside_corpus"])})


def report(rows: list[dict], model: PageModel, recorded: dict[str, Any]) -> str:
    """The short report."""
    order = ranked(rows)
    urdu = [row["site"] for row in order if row["urdu_share"] > 0.5]
    past = [row for row in order if row["outside_corpus"]]
    heavy_only = [row for row in order if row["page_band"] == 3]
    context = compared(rows, model)
    pushes = Counter(plain_reason(reason) for row in order for reason in row["pushed_up_by"])
    lines = [
        "# How overwhelming are Pakistan's public websites, and why?", "",
        f"{len(rows)} public sites, {len(order)} scored, one visit each, on "
        f"{recorded['taken_at'][:10]}. Each score is a **prediction** of the answer to \"How "
        "overwhelming does this page feel?\", 1 (Not at all) to 5 (Extremely), by the "
        f"model `{model.version}`. It is not a measurement of anyone using these sites.", "",
        "## Read this first", "",
        f"**The model calls these pages calm, and that should not be believed yet.** "
        f"{context['below_average']} of {len(order)} score below the average page people rated "
        f"({context['average_page']}), with a median of {context['median']} against "
        f"{context['public_median']} for the {context['public_pages']} public pages in the rated "
        f"corpus, by the same model, and {context['heavy']} heavy against "
        f"{context['public_heavy']} of those. But the pictures are busy: carousels, chat windows, "
        "and notices laid over the page. The model cannot see any of that. It counts text, and on "
        "these pages much of what a person reads is inside images, which was seen in the pictures "
        f"and not measured: median text density {context['density']} against "
        f"{context['public_density']}. "
        f"{context['covered']} pages had something covering them when read, which the model gives "
        "almost no weight (+0.004).", "",
        "So this is better read as a finding about the model than about the sites. The only "
        "Pakistani pages people rated are three states of one train search, a plain page, and "
        "no busier Pakistani page has been rated.", "",
        f"Differences under about {HELD_OUT_ERROR} of a point are not differences: that is the "
        "model's typical error on pages it had not seen. Read the table as bands, not places.",
        "", "## Ranked, highest predicted first", "",
        "| # | Site | Category | Rating | Band | SIMBA's level | Pushed up by | Held down by |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for rank, row in enumerate(order, 1):
        up = ", ".join(row["pushed_up_by"]) or "nothing much"
        down = ", ".join(row["held_down_by"]) or "nothing much"
        lines.append(f"| {rank} | {row['site']} | {row['category']} | {row['rating']:.2f} | "
                     f"{row['page_band']} | {row['simba_level']} | {up} | {down} |")
    lines += ["", "Band is the model's: 1 calm, 2 middle, 3 heavy. SIMBA's level is what the real "
              "rules choose for someone who has set none, which is never below 2.", "",
              "## By category", "", "| Category | Listed | Scored | Mean rating | Heavy |",
              "|---|---|---|---|---|"]
    for group in by_category(rows):
        mean = "not scored" if group["mean"] is None else f"{group['mean']:.2f}"
        lines.append(f"| {group['category']} | {group['listed']} | {group['scored']} | {mean} | "
                     f"{group['heavy']} |")
    lines += ["", "With four to seven sites scored in a category, one site moves its mean a lot, and "
              "the means are closer together than the model's error.", "",
              "## The three most common reasons", "",
              "The model's reasons follow the way a page's score went, and nearly every page went "
              "down. So **these are mostly why pages scored low, not why they overwhelm**:", ""]
    lines += [f"- **{reason}**: {count} of {len(order)} pages"
              for reason, count in common_reasons(rows)]
    lines += ["", "What pushed pages up, where anything did: "
              + "; ".join(f"{reason} ({count})" for reason, count in pushes.most_common(TOP_REASONS))
              + "."]
    if heavy_only:
        lines += ["", f"Among the {len(heavy_only)} heavy pages alone: "
                  + "; ".join(f"{reason} ({count})"
                              for reason, count in common_reasons(heavy_only)) + "."]
    lines += ["", "A deeply nested layout counts against a page's score in this model, which raters "
              "of pictures taught it and nobody has explained. A reason is what moved this model's "
              "sum, not a cause anyone has tested.", "",
              "## Failed or skipped", ""]
    missing = [row for row in rows if row["status"] != "scored"]
    lines += [f"- **{row['site']}** ({row['status']}): {row['note']}" for row in missing] or ["None."]
    lines += ["", "## What this can and cannot say", "",
              "- These are predictions from a model trained on 15 raters, 13 of them aged 18 to 24 "
              "and 10 in computing, none from SIMBA's audience, who agreed weakly with each other "
              "(alpha 0.318). It is under the study's own floor of ratings on 22 of its 50 pages.",
              "- The raters judged a picture of the first screen. They did not use a page. How hard "
              "a site is to get something done on is a different question, and this does not ask it.",
              "- Of the 50 rated pages, the only Pakistani ones are three states of that one "
              "train search.",
              f"- Pages mostly in Urdu ({len(urdu)}: {', '.join(urdu) or 'none'}): reading grade is a "
              "formula for English and says nothing there.",
              f"- Pages past anything the model saw on at least one feature: {len(past)} of "
              f"{len(order)}. Their scores carry a straight line beyond its data, and a score past 5 "
              "is held at 5.",
              "- `links` and `interactive` count the whole page while raters saw one screen, and a "
              "banner image counts as no text, so a page of pictures can read calmer than it looks.",
              "- One visit, one moment, one machine, from Pakistan. Pages change, and a carousel "
              "shows whatever it was showing. A page whose content animates in after 2.5s was read "
              "without it.",
              "- Sites that refused an honest automated visit are not here, which leaves out some "
              "of the largest services.", "",
              f"Run: commit {recorded['git']['commit']} on {recorded['git']['branch']}, chromium "
              f"{recorded.get('chromium')}, viewport {VIEWPORT['width']}x{VIEWPORT['height']}.", ""]
    return "\n".join(lines)


async def saved_flatness(names: list[str], into: Path) -> dict[str, float]:
    """Each saved picture's flatness. The page stays on about:blank."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page()
        found = {name: await flat_share(page, (into / name).read_bytes()) for name in names}
        await browser.close()
    return found


def again(model: PageModel) -> None:
    """The table and the report from what was saved. Visits nothing."""
    path = OUT / "results.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload["results"]
    names = [row["screenshot"] for row in rows if row["status"] == "scored"]
    flats = asyncio.run(saved_flatness(names, OUT / "screenshots"))
    rows = rederive(rows, model, flats.__getitem__)
    payload["results"] = rows
    payload["rederived"] = {"conditions": conditions(), "flat_limit": FLAT_LIMIT}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_csv(rows, OUT / "overwhelm_index.csv")
    (OUT / "report.md").write_text(report(rows, model, payload["conditions"]), encoding="utf-8")
    for name, flat in sorted(flats.items(), key=lambda item: -item[1])[:8]:
        print(f"  {flat:.4f}  {name}")
    print(f"wrote {OUT}: {sum(r['status'] == 'scored' for r in rows)} of {len(rows)} scored")


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    model = page_model.load()
    if model is None:
        raise SystemExit("no usable model in data/estimator.json")
    if "--report" in sys.argv:
        again(model)
        return
    print(banner(), flush=True)
    rows, chromium = asyncio.run(survey(SITES, model, OUT / "screenshots"))
    write_csv(rows, OUT / "overwhelm_index.csv")
    recorded = record(OUT / "results.json", rows, chromium=chromium, sites=len(rows))["conditions"]
    (OUT / "report.md").write_text(report(rows, model, recorded), encoding="utf-8")
    print(f"wrote {OUT}: {sum(r['status'] == 'scored' for r in rows)} of {len(rows)} scored")


if __name__ == "__main__":
    main()
