"""What a page looks like on its first screen, which the nine features cannot see.

The overwhelm index (EVALUATION.md, 2026-11-02b) found the page model blind to
visual clutter: text inside images, carousels, things laid over the page. So five
more numbers, each measured on the first 1280x800 and on nothing below it:

| Feature | Unit | What it is |
|---|---|---|
| `image_area` | 0-1 | share of the screen showing an image, background image, video, canvas or SVG |
| `motion` | 0-1 | share of the screen's pixels that differ between two captures `GAP_S` apart |
| `covered` | 0-1 | share of the screen under something fixed, sticky or stacked above the page |
| `first_screen_links` | count | links a person can actually see |
| `first_screen_text` | characters per 1000pxÂ² | text a person can actually see, in `text_density`'s unit |

    python -m tools.evaluation.visual_features                  # both lists
    python -m tools.evaluation.visual_features --only rated     # the 50 rated pages
    python -m tools.evaluation.visual_features --only sites     # the index's 35 sites

**Read from what the browser would paint.** A box says where an element would be,
not whether anyone can see it: a carousel's other slides sit inside the screen,
clipped or faded out, and text behind a modal has a box like any other. So the
screen is asked, on a grid every `STEP` pixels: `elementsFromPoint` gives what is
stacked at a point, from the top down, and clipping and stacking are already done.
Going down that stack, something opaque ends the search, so a picture behind a
solid panel is not on screen. A partly see-through backdrop does not end it.

**The screen is asked twice, and both were found the hard way** (2026-11-02). Hit
testing skips anything marked `pointer-events: none`, which is how slider plugins
lay out their slides, so `image_area` read 0.01 on Quaid-i-Azam's page, nearly all
photograph. So pictures are asked for with that switched off for the length of the
pass, by a style that is then removed. `covered` keeps the ordinary hit test, or
every decorative layer nobody can touch would count as covering the page.

**`covered` is fixed, sticky, or absolute at a z-index of `MIN_STACK_LEVEL` or more
and attached to the body**, whatever the size. `overlays.candidates` has no such last
condition, and it matters here: a slider's own layers are absolute and stacked high,
and they put 0.79 on Quaid-i-Azam and 0.72 on Ufone with no pop-up on either. A pop-up
is attached to the page; a slide's layer is inside the page. A fixed site header
counts, as the brief asks, and so does a hero built as a fixed layer, as NUST's is:
position cannot tell that from a modal.

**`motion` compares two pictures, so it is only as good as its gap.** A slider that
changes every five seconds is caught by a 3s gap about three times in five, and a
page that changes and changes back reads as still. `motion_late` is the same
comparison at twice the gap, not a feature: it says how much the gap missed. Raters
are shown stills, so a rating can only ever reach motion through what a still shows
(DECISIONS.md, *What the visual features can and cannot be*).

**Not in any of this**: what is inside an iframe (the frame itself is `covered` if
it floats, but a video in one is not `image_area`), and text in a shadow root.

**The rated pictures are frozen; these reads are not.** People rated pictures taken
on 2026-10-03, and these pages are read again now, so for a live page the numbers
describe a later page than the one rated. That breaks what `train.paired` holds to,
and cannot be mended without the pages as they were. So each rated page's new
capture is compared with the picture people saw, and `drift` says how much of the
screen differs. The pictures in `data/rating/pages/` are read and never written.

**The sites are read as the index read them**, through `overwhelm_index.measure`:
robots.txt first, the same checks, no retry. Only the sites it scored are visited.
The nine features come back too, so a site's picture, nine features and five new
ones are all from one load, which is what a page in a rating set must have.

Writes `data/visual_features.json` (committed, numbers only), after every page so
that a failure part-way costs no second visit, and the pictures to
`.scratch/visual-features/`, which are pictures of other people's sites.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
import time
from pathlib import Path
from typing import Any

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, async_playwright

from backend.estimator import page_model
from backend.estimator.page_features import AREA_UNIT
from backend.estimator.page_model import FEATURES, VISUAL_FEATURES
from backend.perception.overlays import MIN_STACK_LEVEL
from tools.evaluation import overwhelm_index as index
from tools.evaluation.collect_corpus import STARTER_LIST, UA, name_of, replicas_running, reset
from tools.evaluation.conditions import banner, conditions
from tools.rating.capture import MANIFEST, PAGES, VIEWPORT, new_run, page_id, photograph
from tools.screen_site import DELAY_BETWEEN_PAGES_S, robots_for

REPO = Path(__file__).resolve().parents[2]
RECORD = REPO / "data" / "visual_features.json"
OUT = REPO / ".scratch" / "visual-features"
#: Seconds between the two captures `motion` compares.
GAP_S = 3.0
#: Pixels between the points the screen is asked about: 5,000 points a pass. Ten
#: was slow enough on a heavy page, at two passes, to stretch `motion`'s gap.
STEP = 16
#: A pixel has changed when a channel moved by more than this of 255: enough to
#: leave out the re-encoding of a video frame, and nothing a person would see.
TOLERANCE = 16
#: Elements named in a row, biggest first, so a `covered` can be checked by eye.
NAMED = 5

#: One read of the first screen. Everything here is in the page's own terms: the
#: viewport as it stands, so a page a drive left scrolled is read where it is.
VISUAL_JS = """([step, stackLevel, named]) => {
    const width = innerWidth, height = innerHeight;
    const styles = new Map(), painted = new Map(), lifters = new Map();
    const style = e => {
        if (!styles.has(e)) styles.set(e, getComputedStyle(e));
        return styles.get(e);
    };
    // Faded right out, or hidden by an ancestor: hit testing still finds an
    // element at opacity 0, which is how carousels hide their other slides.
    const seen = e => {
        if (!painted.has(e)) painted.set(e, e.checkVisibility({
            opacityProperty: true, visibilityProperty: true, contentVisibilityAuto: true}));
        return painted.get(e);
    };
    const opaque = e => {
        const found = style(e).backgroundColor.match(/^rgba?\\(([^)]+)\\)$/);
        if (!found || parseFloat(style(e).opacity) < 1) return false;
        const parts = found[1].split(/[\\s,\\/]+/).filter(Boolean);
        return parts.length < 4 || parseFloat(parts[3]) === 1;
    };
    const picture = e => {
        const tag = e.tagName.toLowerCase();
        if (tag === 'img') return e.complete && e.naturalWidth > 1;
        if (tag === 'video' || tag === 'canvas' || e instanceof SVGElement) return true;
        return style(e).backgroundImage.includes('url(');
    };
    // The nearest element, this one or above, that sits above the page.
    const lifter = e => {
        if (lifters.has(e)) return lifters.get(e);
        const tag = e.tagName.toLowerCase();
        let found = null;
        if (tag !== 'html' && tag !== 'body') {
            const s = style(e);
            const z = parseInt(s.zIndex, 10);
            if (s.position === 'fixed' || s.position === 'sticky'
                || (s.position === 'absolute' && z >= stackLevel
                    && e.parentElement === document.body)) found = e;
            else if (e.parentElement) found = lifter(e.parentElement);
        }
        lifters.set(e, found);
        return found;
    };
    const everyPoint = visit => {
        for (let y = step / 2; y < height; y += step)
            for (let x = step / 2; x < width; x += step)
                visit(document.elementsFromPoint(x, y).filter(seen));
    };
    let points = 0, images = 0, covered = 0;
    const covering = new Map();
    everyPoint(stack => {
        points += 1;
        const above = stack.length ? lifter(stack[0]) : null;
        if (above) {
            covered += 1;
            covering.set(above, (covering.get(above) || 0) + 1);
        }
    });
    // What is painted, whether or not anyone could press it.
    const reachable = document.createElement('style');
    reachable.textContent = '* { pointer-events: auto !important; }';
    document.documentElement.appendChild(reachable);
    try {
        everyPoint(stack => {
            for (const e of stack) {
                if (picture(e)) { images += 1; break; }
                if (opaque(e)) break;
            }
        });
    } finally {
        reachable.remove();
    }
    // Whether a person can see this element at this point of the screen.
    const reaches = (e, x, y) => {
        if (style(e).pointerEvents === 'none') return true;
        for (const top of document.elementsFromPoint(x, y)) {
            if (!seen(top)) continue;
            if (top === e || e.contains(top)) return true;
            if (picture(top) || opaque(top)) return false;
        }
        return false;
    };
    const clip = r => {
        const left = Math.max(r.left, 0), top = Math.max(r.top, 0);
        const right = Math.min(r.right, width), bottom = Math.min(r.bottom, height);
        return right > left && bottom > top ? {left, top, right, bottom} : null;
    };
    const middle = c => [(c.left + c.right) / 2, (c.top + c.bottom) / 2];
    let links = 0;
    for (const link of document.querySelectorAll('a, [role="link"]')) {
        if (!seen(link)) continue;
        for (const r of link.getClientRects()) {
            const c = clip(r);
            if (c && reaches(link, ...middle(c))) { links += 1; break; }
        }
    }
    // A text node's characters count in the share of its lines on the screen.
    const unread = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'HEAD', 'TITLE']);
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const range = document.createRange();
    let characters = 0;
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const text = node.nodeValue.replace(/\\s+/g, ' ').trim();
        const owner = node.parentElement;
        if (!text || !owner || unread.has(owner.tagName) || !seen(owner)) continue;
        range.selectNodeContents(node);
        let whole = 0, shown = 0;
        for (const r of range.getClientRects()) {
            whole += r.width * r.height;
            const c = clip(r);
            if (c && reaches(owner, ...middle(c)))
                shown += (c.right - c.left) * (c.bottom - c.top);
        }
        if (whole > 0) characters += text.length * shown / whole;
    }
    const name = e => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '')
        + ' ' + style(e).position;
    return {
        viewport: [width, height], points,
        image_area: images / points, covered: covered / points,
        first_screen_links: links, first_screen_characters: characters,
        covering: [...covering].sort((a, b) => b[1] - a[1]).slice(0, named)
            .map(([e, n]) => ({element: name(e), share: n / points})),
    };
}"""

#: The share of two pictures' pixels that differ, or null if they are not the
#: same size. Decoded here because nothing in the project can decode a PNG.
PIXELS_JS = """async ([one, two, tolerance]) => {
    const read = async address => {
        const picture = new Image();
        picture.src = address;
        await picture.decode();
        const canvas = document.createElement('canvas');
        canvas.width = picture.width;
        canvas.height = picture.height;
        const paint = canvas.getContext('2d', {willReadFrequently: true});
        paint.drawImage(picture, 0, 0);
        return paint.getImageData(0, 0, canvas.width, canvas.height);
    };
    const [a, b] = [await read(one), await read(two)];
    if (a.width !== b.width || a.height !== b.height) return null;
    let changed = 0;
    for (let at = 0; at < a.data.length; at += 4) {
        if (Math.abs(a.data[at] - b.data[at]) > tolerance
            || Math.abs(a.data[at + 1] - b.data[at + 1]) > tolerance
            || Math.abs(a.data[at + 2] - b.data[at + 2]) > tolerance) changed += 1;
    }
    return changed / (a.data.length / 4);
}"""


class Unmeasured(Exception):
    """The numbers from this read would not mean what they say."""


def address(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


async def changed(page: Page, one: bytes, two: bytes) -> float | None:
    """How much of two pictures differs, on a blank tab of the same browser, so
    a page's own policy has no say and nothing is fetched."""
    blank = await page.context.new_page()
    try:
        share = await blank.evaluate(PIXELS_JS, [address(one), address(two), TOLERANCE])
    finally:
        await blank.close()
    return None if share is None else round(float(share), 4)


async def still(page: Page) -> bytes:
    """One capture, with the second try `capture.photograph` gives a heavy page."""
    try:
        return await page.screenshot(full_page=False)
    except PlaywrightError:
        await page.wait_for_timeout(1500)
        return await page.screenshot(full_page=False)


def on_screen(read: dict[str, Any]) -> dict[str, Any]:
    """The page's own read as features. A read at any other size would be
    numbers about a different screen (CLAUDE.md), so it is refused."""
    if read["viewport"] != [VIEWPORT["width"], VIEWPORT["height"]]:
        raise Unmeasured(f"read at {read['viewport']}, not the frozen viewport")
    area = VIEWPORT["width"] * VIEWPORT["height"] / AREA_UNIT
    return {"image_area": round(read["image_area"], 4), "covered": round(read["covered"], 4),
            "first_screen_links": read["first_screen_links"],
            "first_screen_text": round(read["first_screen_characters"] / area, 3),
            "covering": [{"element": c["element"], "share": round(c["share"], 4)}
                         for c in read["covering"]]}


async def observed(page: Page, first: bytes, gap_s: float = GAP_S) -> dict[str, Any]:
    """The five features of the page in front of `page`, just photographed as
    `first`. The page is only looked at, and the style `VISUAL_JS` adds to do
    that is gone when it returns."""
    started = time.monotonic()

    async def after(seconds: float) -> tuple[bytes, float]:
        await asyncio.sleep(max(0.0, started + seconds - time.monotonic()))
        return await still(page), time.monotonic() - started

    # The clock first: the read below took 12s on one bank's page, on battery,
    # and a gap of 12s is not the gap `motion` is defined by.
    second, gap = await after(gap_s)
    seen = on_screen(await page.evaluate(VISUAL_JS, [STEP, MIN_STACK_LEVEL, NAMED]))
    third, late = await after(2 * gap_s)
    return {**seen, "motion": await changed(page, first, second),
            "motion_late": await changed(page, first, third),
            "gap_s": round(gap, 2), "late_gap_s": round(late, 2)}


async def read_rated(page: Page, url: str, drive: Any, kind: str, run: dict, into: Path,
                     pictures: Path, fetch=robots_for, gap_s: float = GAP_S) -> dict[str, Any]:
    """One rated page, as it is now, beside the picture people saw. Never raises:
    a page that cannot be read is a row saying so."""
    state = name_of(drive)
    row: dict[str, Any] = {"id": page_id(url, state), "url": url, "state": state, "kind": kind,
                           "run": run["id"]}
    try:
        if kind != "ours":
            answer = await index.robots(page, url, fetch)
            if not answer.allowed:
                return {**row, "error": answer.note}
        shot, read = await photograph(page, url, drive, kind, run, into)
        if "error" in shot:
            return {**row, "error": shot["error"]}
        png = (into / shot["file"]).read_bytes()
        rated = pictures / shot["file"]
        return {**row, **await observed(page, png, gap_s), "sha256": shot["sha256"],
                "title": shot["title"], "layout_width": shot["layout_width"],
                "drift": await changed(page, rated.read_bytes(), png) if rated.exists() else None,
                "nine_now": {name: read[name] for name in FEATURES}}
    except Exception as error:  # noqa: BLE001 - one page must not stop the rest
        return {**row, "error": f"{type(error).__name__}: {index.first_line(error)}"}
    finally:
        await reset(page)


async def browse(step: Any) -> str:
    """`step(page)` in a browser set up as the rating pictures' was."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(args=["--hide-scrollbars"])
        context = await browser.new_context(user_agent=UA, viewport=VIEWPORT,
                                             device_scale_factor=1, bypass_csp=True)
        await step(await context.new_page())
        version = browser.version
        await browser.close()
    return version


def sites_to_visit(results: Path = index.OUT / "results.json") -> tuple[index.Site, ...]:
    """The sites the index scored. A site it skipped refused, one it failed on
    gave nothing to compare with, and neither gets a second visit."""
    rows = json.loads(results.read_text(encoding="utf-8"))["results"]
    scored = {row["site"] for row in rows if row["status"] == "scored"}
    return tuple(site for site in index.SITES if site.name in scored)


async def extra(page: Page, shot: dict, into: Path) -> dict[str, Any]:
    """What `overwhelm_index.measure` adds to a site it has found to be a page."""
    return await observed(page, (into / shot["file"]).read_bytes())


def read_record(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save(path: Path, part: str, rows: list[dict], run: dict, recorded: dict[str, Any]) -> None:
    """This list's rows so far, beside the other list's as they were."""
    whole = read_record(path)
    whole["definitions"] = {"step_px": STEP, "gap_s": GAP_S, "tolerance": TOLERANCE,
                            "viewport": VIEWPORT, "features": list(VISUAL_FEATURES)}
    whole[part] = {"conditions": recorded, "run": run, "rows": rows}
    path.write_text(json.dumps(whole, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


async def rated_pages(path: Path, into: Path) -> None:
    run = new_run()
    rows: list[dict] = []
    recorded = conditions()

    async def step(page: Page) -> None:
        for number, (url, drive, kind) in enumerate(STARTER_LIST):
            if number and kind != "ours":
                await asyncio.sleep(DELAY_BETWEEN_PAGES_S)
            rows.append(await read_rated(page, url, drive, kind, run, into, PAGES))
            save(path, "rated", rows, run, recorded)
            said = rows[-1].get("error") or (
                f"image {rows[-1]['image_area']:.2f}  motion {rows[-1]['motion']:.2f}  "
                f"covered {rows[-1]['covered']:.2f}  drift {rows[-1]['drift']}")
            print(f"  {rows[-1]['id'][:52]:<52} {said}", flush=True)

    with replicas_running():
        version = await browse(step)
    save(path, "rated", rows, run, {**recorded, "chromium": version})


async def the_sites(path: Path, into: Path) -> None:
    model = page_model.load()
    if model is None:
        raise SystemExit("no usable model in data/estimator.json")
    run = new_run()
    rows: list[dict] = []
    recorded = conditions()
    ranges = index.corpus_ranges()

    async def step(page: Page) -> None:
        for number, site in enumerate(sites_to_visit()):
            if number:
                await asyncio.sleep(DELAY_BETWEEN_PAGES_S)
            rows.append(await index.measure(page, site, run, model, ranges, into, robots_for,
                                            extra=extra))
            save(path, "sites", rows, run, recorded)
            row = rows[-1]
            said = row["note"] if row["status"] != "scored" else (
                f"image {row['image_area']:.2f}  motion {row['motion']:.2f}  "
                f"covered {row['covered']:.2f}")
            print(f"  {site.name[:34]:<34} {row['status']:<8} {said}", flush=True)

    version = await browse(step)
    save(path, "sites", rows, run, {**recorded, "chromium": version})


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", choices=("rated", "sites"))
    args = parser.parse_args()
    print(banner(), flush=True)
    for part, read in (("rated", rated_pages), ("sites", the_sites)):
        if args.only in (None, part):
            into = OUT / part
            into.mkdir(parents=True, exist_ok=True)
            print(part, flush=True)
            asyncio.run(read(RECORD, into))


if __name__ == "__main__":
    main()
