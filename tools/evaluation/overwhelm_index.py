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

**robots.txt that cannot be read is not permission.** `screen_site.robots_for`
treats an unreadable file as no rules, and raises on a refusal. Here a refused or
unreachable file means the site is skipped (RFC 9309, for an unreachable one).
Python's TLS is stricter than Chromium's about an incomplete certificate chain,
so a file `urllib` could not reach gets one more try in the browser first.

Writes to `.scratch/overwhelm-index/`, none of it committed: `overwhelm_index.csv`,
`report.md`, `results.json` with the conditions, and `screenshots/`, which are
pictures of other people's sites.
"""

from __future__ import annotations

import asyncio
import csv
import dataclasses
import hashlib
import json
import re
import sys
import urllib.error
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, async_playwright

from backend.estimator import page_model
from backend.estimator.page_features import PageFeatures
from backend.estimator.page_model import FEATURES, PageModel
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


def judged(row: dict[str, Any], model: PageModel) -> dict[str, Any]:
    """The model's score and reasons for one page, and the level the real rules
    choose from it for a person who has set none."""
    found = PageFeatures(**{field.name: row[field.name] for field in dataclasses.fields(PageFeatures)})
    judgement = model.judge(found)
    decision = LevelRules(page_model=model).start_step(0, found)
    return {"rating": judgement.rating, "score": judgement.score,
            "page_band": judgement.level, "simba_level": decision.level,
            "reasons": list(judgement.reasons)}


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
        return {
            **blank(site, "scored", answer.note), **judged(row, model),
            "final_url": final_url, "title": shot["title"], "http_status": status,
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


COLUMNS = ("rank", "site", "category", "rating", "score", "page_band", "simba_level",
           "reason_1", "reason_2", "reason_3", *FEATURES, "urdu_share", "outside_corpus",
           "url", "final_url", "title", "http_status", "screenshot", "sha256")


def write_csv(rows: list[dict], path: Path) -> None:
    """The ranked pages. UTF-8 with a mark, so a spreadsheet reads a title in Urdu."""
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for rank, row in enumerate(ranked(rows), 1):
            reasons = (row["reasons"] + ["", "", ""])[:3]
            writer.writerow({**row, "rank": rank, "reason_1": reasons[0], "reason_2": reasons[1],
                             "reason_3": reasons[2],
                             "outside_corpus": "; ".join(row["outside_corpus"])})


def report(rows: list[dict], model: PageModel, recorded: dict[str, Any]) -> str:
    """The short report."""
    order = ranked(rows)
    urdu = [row["site"] for row in order if row["urdu_share"] > 0.5]
    past = [row for row in order if row["outside_corpus"]]
    heavy_only = [row for row in order if row["page_band"] == 3]
    lines = [
        "# How overwhelming are Pakistan's public websites, and why?", "",
        f"{len(rows)} public sites, {len(order)} scored, one visit each, on "
        f"{recorded['taken_at'][:10]}. Each score is a **prediction** of the answer to \"How "
        "overwhelming does this page feel?\", 1 (Not at all) to 5 (Extremely), by the "
        f"model `{model.version}`. It is not a measurement of anyone using these sites.", "",
        f"Differences under about {HELD_OUT_ERROR} of a point are not differences: that is the "
        "model's typical error on pages it had not seen. Read the table as bands, not places.",
        "", "## Ranked, most overwhelming first", "",
        "| # | Site | Category | Rating | Band | SIMBA's level | Why |", "|---|---|---|---|---|---|---|",
    ]
    for rank, row in enumerate(order, 1):
        why = ", ".join(row["reasons"]) or "much like the average page"
        lines.append(f"| {rank} | {row['site']} | {row['category']} | {row['rating']:.2f} | "
                     f"{row['page_band']} | {row['simba_level']} | {why} |")
    lines += ["", "Band is the model's: 1 calm, 2 middle, 3 heavy. SIMBA's level is what the real "
              "rules choose for someone who has set none, which is never below 2.", "",
              "## By category", "", "| Category | Listed | Scored | Mean rating | Heavy |",
              "|---|---|---|---|---|"]
    for group in by_category(rows):
        mean = "not scored" if group["mean"] is None else f"{group['mean']:.2f}"
        lines.append(f"| {group['category']} | {group['listed']} | {group['scored']} | {mean} | "
                     f"{group['heavy']} |")
    lines += ["", "With five to nine sites in a category, one site moves its mean a lot.", "",
              "## The three most common reasons", ""]
    lines += [f"- **{reason}**: {count} of {len(order)} pages"
              for reason, count in common_reasons(rows)]
    lines += ["", f"Among the {len(heavy_only)} heavy pages alone: "
              + "; ".join(f"{reason} ({count})" for reason, count in common_reasons(heavy_only))
              + ".", "", "A reason is what moved this model's sum for this page, in the direction "
              "of its score. It is what the model leans on, not a cause anyone has tested.", "",
              "## Failed or skipped", ""]
    missing = [row for row in rows if row["status"] != "scored"]
    lines += [f"- **{row['site']}** ({row['status']}): {row['note']}" for row in missing] or ["None."]
    lines += ["", "## What this can and cannot say", "",
              "- These are predictions from a model trained on 15 raters, 13 of them aged 18 to 24 "
              "and 10 in computing, none from SIMBA's audience, who agreed weakly with each other "
              "(alpha 0.318). It is under the study's own floor of ratings on 22 of its 50 pages.",
              "- The raters judged a picture of the first screen. They did not use a page. How hard "
              "a site is to get something done on is a different question, and this does not ask it.",
              "- No rated page was Pakistani, and most rated pages were in English.",
              f"- Pages mostly in Urdu ({len(urdu)}: {', '.join(urdu) or 'none'}): reading grade is a "
              "formula for English and says nothing there.",
              f"- Pages past anything the model saw on at least one feature: {len(past)} of "
              f"{len(order)}. Their scores carry a straight line beyond its data, and a score past 5 "
              "is held at 5.",
              "- `links` and `interactive` count the whole page while raters saw one screen, and a "
              "banner image counts as no text, so a page of pictures can read calmer than it looks.",
              "- One visit, one moment, one machine, from Pakistan. Pages change, and a carousel "
              "shows whatever it was showing.", "",
              f"Run: commit {recorded['git']['commit']} on {recorded['git']['branch']}, chromium "
              f"{recorded.get('chromium')}, viewport {VIEWPORT['width']}x{VIEWPORT['height']}.", ""]
    return "\n".join(lines)


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    model = page_model.load()
    if model is None:
        raise SystemExit("no usable model in data/estimator.json")
    print(banner(), flush=True)
    rows, chromium = asyncio.run(survey(SITES, model, OUT / "screenshots"))
    write_csv(rows, OUT / "overwhelm_index.csv")
    recorded = record(OUT / "results.json", rows, chromium=chromium, sites=len(rows))["conditions"]
    (OUT / "report.md").write_text(report(rows, model, recorded), encoding="utf-8")
    print(f"wrote {OUT}: {sum(r['status'] == 'scored' for r in rows)} of {len(rows)} scored")


if __name__ == "__main__":
    main()
