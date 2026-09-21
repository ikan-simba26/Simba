"""How much of the viewport the things covering it actually cover.

`MIN_COVERAGE` has been 0.30 since overlay detection was written, and 0.30
was a guess. It was never measured against a page, and for most of its life
it was quietly behaving as two different guesses depending on the display
(EVALUATION.md, 2026-09-20). A threshold nobody has measured is a threshold
nobody can defend in a report, so this measures it.

**What this does.** Every page in the corpus, loaded and driven into the same
state `collect_corpus` reads it in, then `overlays.candidates` — the
detector's own candidate set, not a reimplementation of it — enumerated with
**no coverage threshold applied at all**. Each candidate comes back with its
coverage, its position, its z-index, what element it is and what it says, so
that a human can look down the list and say which ones are really in the way.

That last part is the point and cannot be automated here. "Is this element a
blocker" has no programmatic ground truth — if it did, the threshold would
not be needed. So this produces the distribution and the identifying detail,
and a person reads it. The reading is written up in EVALUATION.md, 2026-09-20d.

**`MIN_STACK_LEVEL` too**, since it is the same kind of guess. It cannot be
measured from `candidates()`, because `candidates()` has already applied it —
an `absolute` element at z-index 3 is not in that set. So the probe walks
`positioned()`, every positioned element with no rule applied, and reports
the z-index of the things that are blockers against the things that are not.

**The sweep** answers the two questions a coverage threshold has to answer:
what a higher value misses, and what a lower one falsely flags. For each
candidate threshold it reports how many pages would be called blocked and
which pages join or leave, so the cost of moving the number is visible rather
than argued about.

Run it:

    python -m tools.evaluation.overlay_coverage_probe

Headless, read-only, one page load per page, no model. Coverage is a fraction
of the frozen 1280x800 viewport in CSS pixels, which since 2026-09-20 is
environment-independent — `snapshot.parse` converts on the way in, so this
number no longer depends on the display the probe ran on.
"""

import asyncio
import json
import statistics
import sys
from pathlib import Path

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from backend.perception.overlays import (
    LIFTED_POSITIONS,
    MIN_COVERAGE,
    MIN_STACK_LEVEL,
    STACKED_POSITIONS,
    Candidate,
    positioned,
)
from backend.perception.serializer import VIEWPORT, read_async
from tools.evaluation.collect_corpus import (
    LOAD_TIMEOUT_MS,
    SETTLE_MS,
    STARTER_LIST,
    UA,
    name_of,
    replicas_running,
    reset,
)
from tools.evaluation.conditions import banner, record

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Candidates smaller than this are not printed. Nothing is dropped from the
#: recorded file — this is only about a readable console report, and a
#: 12x12px positioned spinner is not a design question.
WORTH_PRINTING = 0.01

#: The thresholds swept. 0.30 is the one in the code; the rest bracket it
#: closely enough to show where pages enter and leave.
SWEEP = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.75, 0.90]

#: What counts as a real blocker when splitting the z-index distribution.
#: Not `MIN_COVERAGE`: using the threshold under test to define the thing
#: being tested would make the answer circular. This is set where the corpus
#: has a genuine gap, and every element above it has been eyeballed and is a
#: modal, a drawer or a consent wall.
BLOCKER_COVERAGE = 0.30


def describe(document, candidate: Candidate) -> dict:
    """One candidate, with enough about it to judge it by eye.

    The identity matters as much as the number. `0.34` says nothing; `0.34,
    a fixed div with class "sidebar"` says it is furniture and `0.34, a fixed
    div whose text begins "We use cookies"` says it is a consent wall.
    """
    index = candidate.node_index
    attributes = document.attributes[index] if index < len(document.attributes) else {}
    return {
        "coverage": round(candidate.coverage, 4),
        "position": candidate.position,
        "z_index": candidate.z_index,
        # Which of the two ways in it took. `declared` alone was the whole
        # candidate set before 2026-09-20d.
        "found_by": "z-index" if candidate.declared else "position",
        # Whether either rule admits it as things stand. False on a row means
        # the detector cannot see this element at all today.
        "a_candidate": candidate.declared or candidate.lifted,
        "tag": candidate.tag,
        "id": attributes.get("id", ""),
        "class": attributes.get("class", "")[:60],
        "rect": [round(v) for v in candidate.rect],
        "text": document.text_of(index, limit=70),
        "css_path": document.css_path(index)[-90:],
    }


async def read_candidates(page, url: str, drive=None, kind: str = "") -> dict:
    """One page, driven into its corpus state, with everything above it."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=LOAD_TIMEOUT_MS)
        await page.wait_for_timeout(SETTLE_MS)
        if drive is not None:
            await drive(page)
            await page.wait_for_timeout(600)
        view = await read_async(page, VIEWPORT)
        if view.document is None:
            return {"url": url, "state": name_of(drive), "kind": kind,
                    "error": "no snapshot; are the switches off?"}
        # `positioned`, not `candidates`: the rules are what is being
        # measured, so the population has to be the one they select from.
        found = positioned(view.document, VIEWPORT)
        return {
            "url": url,
            "state": name_of(drive),
            "kind": kind,
            "device_pixel_ratio": view.document.device_pixel_ratio,
            "candidates": sorted(
                (describe(view.document, c) for c in found),
                key=lambda row: -row["coverage"],
            ),
        }
    except PlaywrightError as refused:
        await reset(page)
        return {"url": url, "state": name_of(drive), "kind": kind,
                "error": f"{type(refused).__name__}: {str(refused)[:120]}"}


async def collect(pages) -> list[dict]:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        context = await browser.new_context(
            user_agent=UA, viewport={"width": VIEWPORT[0], "height": VIEWPORT[1]})
        page = await context.new_page()
        rows = []
        for url, drive, kind in pages:
            row = await read_candidates(page, url, drive, kind)
            rows.append(row)
            print(f"  {_where(row)} -> {_say(row)}", flush=True)
        await browser.close()
        return rows


def _where(row: dict) -> str:
    where = row["url"].replace("https://", "").replace("http://", "")[:44]
    if row.get("state") and row["state"] != "as it loads":
        where = f"{where} [{row['state']}]"
    return f"{where:<62}"


def _say(row: dict) -> str:
    if "error" in row:
        return f"FAILED {row['error']}"
    above = row["candidates"]
    over = [c for c in above if c["coverage"] >= MIN_COVERAGE]
    biggest = f"{above[0]['coverage']:.3f}" if above else "-"
    return (f"{len(above):3d} above the page, {len(over)} over {MIN_COVERAGE}, "
            f"largest {biggest}")


# --- what came back ---------------------------------------------------------


def print_candidates(rows: list[dict]) -> None:
    """Every candidate worth looking at, page by page, biggest first."""
    print("\n=== what is painted above each page ===")
    print("coverage is a fraction of the 1280x800 viewport; `found_by` says "
          f"whether a z-index >= {MIN_STACK_LEVEL} or a position in "
          f"{sorted(LIFTED_POSITIONS)} put it in the candidate set\n")
    for row in rows:
        if "error" in row:
            continue
        shown = [c for c in row["candidates"] if c["coverage"] >= WORTH_PRINTING]
        if not shown:
            continue
        print(_where(row).strip())
        for c in shown:
            name = c["id"] or c["class"] or c["tag"]
            print(f"    {c['coverage']:>6.3f}  {c['position']:<8}"
                  f"z={str(c['z_index'] or 'auto'):<6}{c['found_by']:<9}"
                  f"{c['tag']:<7}{name[:26]:<28}{c['text'][:44]!r}")
        print()


def only_candidates(rows: list[dict]) -> list[dict]:
    """The elements a rule actually admits, out of every positioned one.

    The file records `positioned()` — everything — because that is what the
    z-index question needs. The coverage threshold governs `candidates()`
    only, and mixing the two makes a distribution that cannot be compared
    with the run before it: on 2026-09-20e the same corpus read as 3019
    elements or 270 candidates depending on which was meant.
    """
    return [c for row in rows if "error" not in row
            for c in row["candidates"] if c["a_candidate"]]


def distribution(rows: list[dict]) -> None:
    """The spread of coverage over every candidate in the corpus."""
    values = [c["coverage"] for c in only_candidates(rows)]
    if not values:
        print("no candidates at all — that is itself the finding")
        return
    positioned_total = sum(len(r["candidates"]) for r in rows if "error" not in r)
    print(f"=== {len(values)} candidates over "
          f"{sum(1 for r in rows if 'error' not in r)} pages "
          f"(out of {positioned_total} positioned elements) ===")
    print(f"  min {min(values):.4f}   median {statistics.median(values):.4f}   "
          f"mean {statistics.fmean(values):.4f}   max {max(values):.4f}")
    admitted = only_candidates(rows)
    bands = [(0.0, 0.01), (0.01, 0.05), (0.05, 0.10), (0.10, 0.20),
             (0.20, 0.30), (0.30, 0.40), (0.40, 0.50), (0.50, 0.90), (0.90, 1e9)]
    print("\n  coverage band      candidates   of which fixed/sticky with no z-index")
    for low, high in bands:
        inside = [c for c in admitted if low <= c["coverage"] < high]
        lifted = [c for c in inside if c["found_by"] == "position"]
        label = f"{low:.2f}-{high:.2f}" if high < 1e9 else f"{low:.2f}+    "
        note = "   <- the band that was empty" if 0.30 <= low < 0.90 else ""
        print(f"  {label:<18}{len(inside):>11}{len(lifted):>40}{note}")

    # And every one of them, since this is the band under examination.
    inband = sorted((c for c in admitted if 0.30 <= c["coverage"] < 0.90),
                    key=lambda c: -c["coverage"])
    print(f"\n  {len(inband)} candidates between 0.30 and 0.90:")
    for c in inband:
        name = c["id"] or c["class"] or c["tag"]
        print(f"    {c['coverage']:.4f}  {c['position']:<8}"
              f"z={str(c['z_index'] if c['z_index'] is not None else 'auto'):<12}"
              f"{name[:40]:<42}{c['text'][:28]!r}")


def sweep_of(rows: list[dict]) -> list[dict]:
    """What each threshold would call blocked, and who joins as it falls.

    The two questions in one table: raising the number misses the pages that
    drop out, lowering it falsely flags the pages that come in. `joined` is
    read downwards — these are the pages this threshold admits that the next
    one up did not.
    """
    good = [row for row in rows if "error" not in row]
    summary = []
    previous: set[str] = set()
    for threshold in sorted(SWEEP, reverse=True):
        blocked = {
            _where(row).strip() for row in good
            if any(c["a_candidate"] and c["coverage"] >= threshold
                   for c in row["candidates"])
        }
        blockers = sum(
            1 for row in good for c in row["candidates"]
            if c["a_candidate"] and c["coverage"] >= threshold
        )
        summary.append({"threshold": threshold, "pages_blocked": len(blocked),
                        "blockers": blockers, "joined": sorted(blocked - previous)})
        previous = blocked
    return list(reversed(summary))


def print_sweep(summary: list[dict]) -> None:
    print("\n=== every threshold, and which pages it calls blocked ===")
    print(f"{'threshold':<12}{'pages blocked':>15}{'blockers':>11}   joins as the "
          f"threshold falls to this value")
    for line in reversed(summary):
        mark = "  <- the value in the code" if line["threshold"] == MIN_COVERAGE else ""
        joined = ", ".join(j[:34] for j in line["joined"][:3]) or "-"
        print(f"{line['threshold']:<12.2f}{line['pages_blocked']:>15}"
              f"{line['blockers']:>11}   {joined}{mark}")


def z_indexes(rows: list[dict]) -> None:
    """What `MIN_STACK_LEVEL` is separating, and what it is not.

    A "real blocker" here is an element over `MIN_COVERAGE` that a person
    would have to deal with — which on this corpus is the same set as
    "coverage >= 0.9", because the corpus has no mid-sized ones. Said out
    loud because it makes the comparison below narrower than it looks.
    """
    everything = [c for row in rows if "error" not in row for c in row["candidates"]]
    if not everything:
        print("no positioned elements at all")
        return

    blockers = [c for c in everything if c["coverage"] >= BLOCKER_COVERAGE]
    others = [c for c in everything if c["coverage"] < BLOCKER_COVERAGE]

    print(f"\n=== z-index, over {len(everything)} positioned elements ===")
    print("`absolute` is the position the rule actually gates: `fixed` and "
          f"`sticky` get in\nwithout a z-index, so only an `absolute` element "
          f"is ever excluded by MIN_STACK_LEVEL={MIN_STACK_LEVEL}.\n")

    def spread(name: str, rows_: list[dict]) -> None:
        declared = [c["z_index"] for c in rows_ if c["z_index"] is not None]
        auto = len(rows_) - len(declared)
        if declared:
            print(f"  {name:<28} {len(rows_):>4} elements, {auto:>4} with no "
                  f"z-index, declared min {min(declared)} / max {max(declared)}")
        else:
            print(f"  {name:<28} {len(rows_):>4} elements, {auto:>4} with no "
                  f"z-index, none declared")

    spread(f"blockers (>= {BLOCKER_COVERAGE})", blockers)
    spread("everything else", others)

    print("\n  z-index band        blockers   not blockers")
    bands = [(None, None), (-(10**9), 0), (0, 1), (1, 5), (5, 50), (50, 1000),
             (1000, 10**9)]
    for low, high in bands:
        if low is None:
            label = "auto (none declared)"
            inb = [c for c in blockers if c["z_index"] is None]
            oth = [c for c in others if c["z_index"] is None]
        else:
            label = f"{low} to {high - 1}" if high < 10**9 else f"{low}+"
            inb = [c for c in blockers
                   if c["z_index"] is not None and low <= c["z_index"] < high]
            oth = [c for c in others
                   if c["z_index"] is not None and low <= c["z_index"] < high]
        print(f"  {label:<20}{len(inb):>9}{len(oth):>15}")

    # The only rows MIN_STACK_LEVEL decides: absolute, with a declared
    # z-index. Everything else gets in or stays out for other reasons.
    gated = [c for c in everything
             if c["position"] in STACKED_POSITIONS
             and c["position"] not in LIFTED_POSITIONS
             and c["z_index"] is not None]
    print(f"\n  Rows MIN_STACK_LEVEL actually decides "
          f"(`absolute` with a declared z-index): {len(gated)}")
    for c in sorted(gated, key=lambda c: -c["coverage"])[:12]:
        verdict = "IN " if c["z_index"] >= MIN_STACK_LEVEL else "OUT"
        big = " <- over MIN_COVERAGE" if c["coverage"] >= MIN_COVERAGE else ""
        print(f"    {verdict} z={c['z_index']:<8} coverage {c['coverage']:.4f}  "
              f"{c['tag']} {(c['id'] or c['class'])[:34]}{big}")

    # What would change if the level moved.
    print("\n  threshold   absolute elements admitted   of those, over "
          f"{MIN_COVERAGE}")
    for level in (0, 1, 2, 3, 5, 10, 50, 100):
        admitted = [c for c in gated if c["z_index"] >= level]
        over = [c for c in admitted if c["coverage"] >= MIN_COVERAGE]
        mark = "  <- the value in the code" if level == MIN_STACK_LEVEL else ""
        print(f"  {level:<12}{len(admitted):>22}{len(over):>29}{mark}")


async def main() -> None:
    # This console is cp1252 and the pages are not. Printing a page's own
    # text is the point of the report, so the console has to be able to take
    # it; without this, one character on one page ends the run.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    pages = STARTER_LIST
    print(banner(), flush=True)
    print(f"{len(pages)} pages, headless, candidates enumerated with no "
          f"coverage threshold\n", flush=True)

    with replicas_running():
        rows = await collect(pages)

    # Written before anything is printed, and deliberately. The first run of
    # this script did 45 network reads, then died formatting them, and the
    # measurement was gone. A report can be regenerated from the file; the
    # file cannot be regenerated from a traceback.
    out = REPO_ROOT / "data" / "overlay_coverage.json"
    summary = sweep_of(rows)
    record(out, {"pages": rows, "sweep": summary},
           viewport=list(VIEWPORT), min_coverage=MIN_COVERAGE,
           min_stack_level=MIN_STACK_LEVEL, settle_ms=SETTLE_MS)
    print(f"\nwrote {out}", flush=True)

    print_candidates(rows)
    distribution(rows)
    print_sweep(summary)
    z_indexes(rows)


if __name__ == "__main__":
    asyncio.run(main())
