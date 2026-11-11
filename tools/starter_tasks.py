"""Starter tasks (2026-11-11): two taught tasks, ready-made, saved as files.

A helper teaches SIMBA a task once ("Teach a task"); the overlay can then save
it to a file ("Save to a file", in "Change these tiles") and add one back from
a file ("Add one from a file", under "Teach a task"). The two files in
`demo/starters/` are made that way, by teaching each task through the real
overlay on our own copies and pressing "Save to a file" — never written by
hand:

- **My bill** (`my-bill.simba-routine.json`), on the billing copy: cookies
  accepted, the reference number typed and **asked each time**, Check Bill,
  the amount pointed at.
- **Train times** (`train-times.simba-routine.json`), on the railways copy:
  From and To chosen from the site's lists and the day from its calendar, each
  **asked each time**, the search, the trains pointed at.

They are for a demo whose live teaching goes wrong, and for anyone who wants
a taught task without teaching one. **Nothing loads them by itself**: a file
becomes a tile only when someone adds it with "Add one from a file". How
routines are stored is unchanged.

    .\\run.ps1 railways-local                       # terminal 1: the stack
    python -m tools.starter_tasks make              # teach both, save both
    python -m tools.starter_tasks check [runs]      # add each, run it from its tile

`make` and `check` each need room for one tile on the home screen (a row
holds three), and each leaves the home screen as it found it: the taught or
added tile is taken off again with "Take it off". `check` runs each file
`runs` times (5): added in a fresh overlay, its tile pressed, the person's
questions answered, and the answer checked — the bill's amount, or trains
for the route asked, a different route on alternate runs. Written to
`logs/starter_tasks.json`.

**What it drives.** The overlay is the real one, built from source, in a
browser of its own talking to the real backend at 8000 (`tools.record_demo`).
The helper's presses go to the website in the SIMBA window's site view, over
CDP on `SIMBA_CDP_PORT` (9222), exactly where the backend watches them — the
same page a helper uses. Replicas only: both addresses are this machine's.

The teach clip (`python -m tools.record_demo teach`) uses `teach_then_press`
with `shown=True`: while the bar is up, the recording shows the site view's
own picture under the bar, as the SIMBA window does (`Mirror`).
"""

import base64
import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from tools.record_demo import BEAT_MS, REAL_WS, build, drive, press, serve

REPO = Path(__file__).resolve().parents[1]
STARTERS = REPO / "demo" / "starters"
LOG = REPO / "logs" / "starter_tasks.json"
CDP = f"http://127.0.0.1:{os.environ.get('SIMBA_CDP_PORT', '9222')}"
REFERENCE = "04141234567890"
#: The overlay's height while it is a bar (`frontend/src/store.ts`, TEACH_BAR):
#: the site view shows below it, at its own coordinates.
BAR = 160

TASKS: dict[str, dict[str, str]] = {
    "bill": {"label": "My bill", "answer": "Amount due",
             "address": "127.0.0.1:5100", "origin": "http://127.0.0.1:5100",
             "file": "my-bill.simba-routine.json"},
    "trains": {"label": "Train times", "answer": "Trains",
               "address": "127.0.0.1:5200", "origin": "http://127.0.0.1:5200",
               "file": "train-times.simba-routine.json"},
}

#: The person's answers when each runs from its tile. The trains alternate
#: between two routes, so a run that kept the helper's route would show.
RUNS_SAY: dict[str, list[dict[str, list[str]]]] = {
    "bill": [{"type": [REFERENCE]}],
    "trains": [{"type": ["Lahore", "Karachi"], "pick": ["Lahore Cantt", "Karachi Cantt"]},
               {"type": ["Hyderabad", "Sukkur"], "pick": ["Hyderabad Jn", "Sukkur"]}],
}


class Mirror:
    """The SIMBA window while a helper teaches: the overlay is a bar across
    the top and the site view shows below it, unmoved (`frontend/electron/
    main.ts`). The recording's overlay is the bar; under it goes the site
    view's own picture from y=160 down, refreshed between the helper's
    presses, and a ring where each press lands. Nothing else of the screen.

    With `shown=False` it draws nothing and only waits.
    """

    def __init__(self, page, site, shown: bool) -> None:
        self.page, self.site, self.shown = page, site, shown
        self.frames = self.missed = 0

    def on(self) -> None:
        if not self.shown:
            return
        self.page.evaluate("""(bar) => {
            const img = document.createElement('img');
            img.id = '__simba_site';
            Object.assign(img.style, {position: 'fixed', left: '0', top: bar + 'px',
                width: '1280px', height: (800 - bar) + 'px', zIndex: 2147483646,
                pointerEvents: 'none', background: '#fff'});
            const ring = document.createElement('div');
            ring.id = '__simba_ring';
            Object.assign(ring.style, {position: 'fixed', width: '44px', height: '44px',
                marginLeft: '-22px', marginTop: '-22px', borderRadius: '50%',
                border: '4px solid #e8590c', zIndex: 2147483647, pointerEvents: 'none',
                display: 'none'});
            document.body.append(img, ring);
        }""", BAR)
        self.refresh()

    def refresh(self) -> None:
        if not self.shown:
            return
        try:
            shot = self.site.screenshot(type="jpeg", quality=80, timeout=3000,
                                        clip={"x": 0, "y": BAR, "width": 1280, "height": 800 - BAR})
        except Exception:  # noqa: BLE001 - a missed picture keeps the last one
            self.missed += 1
            return
        self.frames += 1
        self.page.evaluate("s => { const i = document.getElementById('__simba_site');"
                           " if (i) i.src = 'data:image/jpeg;base64,' + s; }",
                           base64.b64encode(shot).decode())

    def beat(self, ms: int) -> None:
        if not self.shown:
            self.page.wait_for_timeout(ms)
            return
        end = time.monotonic() + ms / 1000
        self.refresh()
        while time.monotonic() < end:
            self.page.wait_for_timeout(120)
            self.refresh()

    def ring(self, target) -> None:
        """Where the helper is about to press, for a moment."""
        if not self.shown:
            return
        box = target.bounding_box()
        if not box:
            return
        self.page.evaluate("""([x, y]) => { const r = document.getElementById('__simba_ring');
            if (r) Object.assign(r.style, {left: x + 'px', top: y + 'px', display: 'block'}); }""",
                           [box["x"] + box["width"] / 2, box["y"] + box["height"] / 2])
        self.beat(600)

    def unring(self) -> None:
        if self.shown:
            self.page.evaluate("() => { const r = document.getElementById('__simba_ring');"
                               " if (r) r.style.display = 'none'; }")

    def off(self) -> None:
        if self.shown:
            self.page.evaluate("() => ['__simba_site', '__simba_ring'].forEach(id =>"
                               " document.getElementById(id)?.remove())")


def helper_press(mirror: Mirror, target) -> None:
    """A helper's press on the website, seen landing."""
    if hasattr(target, "wait_for"):
        target.wait_for(state="visible", timeout=20000)
    mirror.ring(target)
    target.click()
    mirror.unring()
    mirror.beat(900)


def helper_type(mirror: Mirror, target, text: str) -> None:
    """Typed a key at a time, the picture following."""
    helper_press(mirror, target)
    for key in text:
        target.press_sequentially(key)
        mirror.refresh()
    mirror.beat(600)


def on_bar(page, mirror: Mirror, testid: str) -> None:
    """Press one of the bar's buttons, once it is there."""
    button = page.get_by_test_id(testid)
    button.wait_for(state="visible", timeout=30000)
    mirror.beat(BEAT_MS)
    press(page, button)
    mirror.beat(900)


def pointing(page, mirror: Mirror) -> None:
    deadline = time.monotonic() + 30
    while page.locator("[data-testid=teach-bar][data-pointing=true]").count() == 0:
        if time.monotonic() > deadline:
            raise SystemExit("the bar never asked to be shown the answer")
        mirror.beat(300)
    mirror.beat(BEAT_MS)


def teach_bill(page, site, mirror: Mirror) -> list[str]:
    """As `tools/evaluation/show_me_once.py` teaches it, on the billing copy
    the stack serves."""
    seen = []
    cookies = site.get_by_role("button", name="Accept all cookies")
    try:
        cookies.wait_for(state="visible", timeout=5000)
        helper_press(mirror, cookies)
    except Exception:  # noqa: BLE001 - the site remembered an earlier answer
        seen.append("no cookie banner to accept")
    helper_type(mirror, site.get_by_role("textbox", name="Reference No."), REFERENCE)
    helper_press(mirror, site.get_by_role("button", name="Check Bill"))
    site.wait_for_url("**/bill", timeout=20000)
    on_bar(page, mirror, "teach-ask")       # the reference: Ask each time
    on_bar(page, mirror, "teach-finish")
    pointing(page, mirror)
    helper_press(mirror, site.get_by_text("14,382", exact=True).first)
    return seen


def station(mirror: Mirror, site, box: str, typed: str, choice: str) -> None:
    field = site.locator(f"input[placeholder='{box}'], #{box.lower()}").first
    helper_type(mirror, field, typed)
    option = site.locator("li:visible", has_text=choice).first
    option.wait_for(timeout=20000)
    helper_press(mirror, option)


def teach_trains(page, site, mirror: Mirror) -> list[str]:
    """From, To, a day, the search, and the trains pointed at, on the
    railways copy; each choice asked each time."""
    station(mirror, site, "From", "LAH", "LAHORE CANTT")
    on_bar(page, mirror, "teach-ask")
    station(mirror, site, "To", "KARACHI", "KARACHI CANTT")
    on_bar(page, mirror, "teach-ask")
    helper_press(mirror, site.locator("input[placeholder='Departure Date'], #date").first)
    banner = site.locator("#showing").first
    banner.wait_for()
    before = banner.inner_text()
    helper_press(mirror, site.get_by_role("button", name="Next Month").first)
    site.wait_for_function(f"document.querySelector('#showing').innerText !== {before!r}")
    helper_press(mirror, site.locator("td.available:visible", has_text="15").first)
    on_bar(page, mirror, "teach-ask")
    # The search button has no name (`show_me_once._search_trains`).
    search = site.evaluate_handle("""() => [...document.querySelectorAll('button')]
        .find(b => b.offsetParent && !(b.innerText || '').trim()
              && !b.getAttribute('aria-label') && !b.closest('.el-picker-panel'))""")
    helper_press(mirror, search.as_element())
    site.locator("#results tbody td").first.wait_for(timeout=60000)
    on_bar(page, mirror, "teach-finish")
    pointing(page, mirror)
    helper_press(mirror, site.locator("#results tbody td").first)
    return []


TEACHERS = {"bill": teach_bill, "trains": teach_trains}


def site_page(host, origin: str, page):
    """The SIMBA window's site view, once the backend has opened the website
    in it. Waited on through `page`, not `time.sleep`: the sync API only
    hears that a page moved during its own calls."""
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        for context in host.contexts:
            for candidate in context.pages:
                if candidate.url.startswith(origin):
                    return candidate
        page.wait_for_timeout(300)
    raise SystemExit(f"the SIMBA window never opened {origin}; is `.\\run.ps1` up?")


def routine_tile(page, label: str):
    return page.locator(f"[data-testid=own-routine][title='{label}']")


def teach_then_press(playwright, page, which: str, shown: bool, then_press: bool = True
                     ) -> list[str]:
    """From the home screen: "Teach a task", the task shown once on our copy,
    read back, named and kept — then its new tile pressed, unless
    `then_press` is False. Returns what happened."""
    task = TASKS[which]
    label = task["label"]
    page.get_by_test_id("teach-a-task").wait_for(timeout=20000)
    page.wait_for_timeout(BEAT_MS)  # the tiles, offered on connecting
    if routine_tile(page, label).count():
        raise SystemExit(f"'{label}' is already on the home screen. Take it off first "
                         "(Change these tiles, Take it off), then teach it again.")
    host = playwright.chromium.connect_over_cdp(CDP)
    try:
        started = time.monotonic()
        press(page, page.get_by_test_id("teach-a-task"))
        page.get_by_test_id("teach-intro").wait_for()
        if page.get_by_test_id("teach-full").count():
            raise SystemExit("the home screen's row of three is full; take a tile off first")
        page.wait_for_timeout(BEAT_MS)
        address = page.get_by_test_id("teach-address")
        address.click()
        address.type(task["address"], delay=60)
        page.wait_for_timeout(700)
        press(page, page.get_by_test_id("teach-start"))
        page.get_by_test_id("teach-bar").wait_for(timeout=30000)
        site = site_page(host, task["origin"], page)
        site.wait_for_load_state()
        mirror = Mirror(page, site, shown)
        mirror.on()
        mirror.beat(BEAT_MS)
        seen = TEACHERS[which](page, site, mirror)
        page.get_by_test_id("read-back").wait_for(timeout=60000)
        mirror.off()
        moves = page.get_by_test_id("read-back-lines").locator("li").count()
        page.wait_for_timeout(BEAT_MS * 2)  # the moves, read
        for field, value in (("name", label), ("answer", task["answer"])):
            box = page.get_by_test_id(f"read-back-{field}")
            box.click()
            box.fill("")
            box.type(value, delay=60)
            page.wait_for_timeout(500)
        press(page, page.get_by_test_id("read-back-keep"))
        # "Kept." and what the tile will do, then "Back to start", as a
        # helper sees it (`teach.py`, task.completed).
        back = page.get_by_role("button", name="Back to start")
        back.wait_for(timeout=30000)
        explanation = page.get_by_test_id("explanation").first.inner_text().strip()
        page.wait_for_timeout(BEAT_MS * 2)
        press(page, back)
        seen.append(f"kept: {explanation[:80]!r}")
        tile = routine_tile(page, label)
        tile.wait_for(timeout=30000)
        seen.append(f"taught {label!r}: {moves} moves read back, {time.monotonic() - started:.0f}s,"
                    f" site pictures {mirror.frames} shown, {mirror.missed} missed")
        if then_press:
            page.wait_for_timeout(BEAT_MS * 2)  # the new picture tile, seen
            press(page, tile)
            seen.append(f"pressed the {label!r} tile")
        return seen
    finally:
        host.close()  # detaches; the host keeps running


def take_off(page, label: str) -> None:
    """"Change these tiles", then "Take it off" on the tile's row, then back."""
    press(page, page.get_by_test_id("change-tiles"))
    row = page.get_by_test_id("tile-row").filter(has=page.get_by_label(f"Name of {label}"))
    row.first.wait_for(timeout=10000)
    press(page, row.first.get_by_role("button", name="Take it off"))
    row.first.wait_for(state="detached", timeout=10000)
    press(page, page.get_by_test_id("tiles-back"))


def overlay(browser, page_url: str):
    context = browser.new_context(viewport={"width": 1280, "height": 800}, accept_downloads=True)
    context.add_init_script("window.__simbaWelcome = false; window.__simbaSplash = false")
    page = context.new_page()
    page.goto(f"{page_url}?ws={REAL_WS}")
    return context, page


def make(page_url: str) -> None:
    STARTERS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for which, task in TASKS.items():
            context, page = overlay(browser, page_url)
            seen = teach_then_press(playwright, page, which, shown=False, then_press=False)
            press(page, page.get_by_test_id("change-tiles"))
            row = page.get_by_test_id("tile-row").filter(
                has=page.get_by_label(f"Name of {task['label']}"))
            with page.expect_download(timeout=20000) as saving:
                press(page, row.first.get_by_test_id("routine-save"))
            download = saving.value
            kept = STARTERS / download.suggested_filename
            download.save_as(kept)
            press(page, page.get_by_test_id("tiles-back"))
            take_off(page, task["label"])
            text = kept.read_text(encoding="utf-8")
            print(f"{which}: {' | '.join(seen)}\n  saved {kept.relative_to(REPO)} "
                  f"({len(text)} bytes); the typed reference in it: {REFERENCE in text}",
                  flush=True)
            context.close()
        browser.close()


def answered(which: str, page, say: dict[str, list[str]]) -> bool:
    """Whether the ending is the right answer: the bill's amount, or trains
    between the stations asked for."""
    text = page.evaluate("() => document.body.innerText")
    if page.locator("[data-testid=findings]").count() == 0:
        return False
    if which == "bill":
        return "14,382" in text
    return all(place.lower() in text.lower() for place in say["pick"])


def check(page_url: str, runs: int) -> None:
    rows = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for which, task in TASKS.items():
            path = STARTERS / task["file"]
            for run in range(runs):
                say = RUNS_SAY[which][run % len(RUNS_SAY[which])]
                context, page = overlay(browser, page_url)
                started = time.monotonic()
                row = {"task": which, "run": run + 1, "say": say}
                try:
                    page.get_by_test_id("teach-a-task").wait_for(timeout=20000)
                    page.wait_for_timeout(BEAT_MS)  # the tiles, offered on connecting
                    if routine_tile(page, task["label"]).count():
                        raise SystemExit(f"'{task['label']}' is already on the home screen")
                    press(page, page.get_by_test_id("teach-a-task"))
                    page.get_by_test_id("teach-intro").wait_for()
                    page.get_by_test_id("teach-file").set_input_files(str(path))
                    # Nothing on this screen says it was added (only a file
                    # that could not be used is said): "Not now" goes home,
                    # where the tile is.
                    page.wait_for_timeout(BEAT_MS)
                    if page.get_by_test_id("file-note").count():
                        raise RuntimeError(page.get_by_test_id("file-note").inner_text())
                    press(page, page.get_by_test_id("teach-back"))
                    tile = routine_tile(page, task["label"])
                    tile.wait_for(timeout=20000)
                    row["added_s"] = round(time.monotonic() - started, 1)
                    press(page, tile)
                    row["seen"] = drive(page, "teach" if which == "bill" else "trains-tile", say)
                    row["right"] = answered(which, page, say)
                    press(page, page.get_by_role("button", name="Back to start"))
                except SystemExit:
                    raise
                except Exception as error:  # noqa: BLE001 - one run failing is a result
                    row["right"] = False
                    row["error"] = repr(error)[:300]
                    try:
                        row["screen"] = " / ".join(
                            line for line in page.evaluate("document.body.innerText").splitlines()
                            if line.strip())[:400]
                    except Exception:  # noqa: BLE001
                        pass
                finally:
                    row["seconds"] = round(time.monotonic() - started, 1)
                    try:
                        page.get_by_test_id("teach-a-task").wait_for(timeout=10000)
                        if routine_tile(page, task["label"]).count():
                            take_off(page, task["label"])
                    except Exception as error:  # noqa: BLE001
                        row["left_behind"] = repr(error)[:200]
                    context.close()
                rows.append(row)
                print(f"{which} {run + 1}: {'right' if row['right'] else 'WRONG'} "
                      f"{row['seconds']}s -> {' | '.join(row.get('seen', []))}"
                      f"{' ' + row['error'] if 'error' in row else ''}"
                      f"{' SCREEN: ' + row['screen'] if 'screen' in row else ''}", flush=True)
        browser.close()
    summary = {which: f"{sum(r['right'] for r in rows if r['task'] == which)} of "
                      f"{sum(1 for r in rows if r['task'] == which)}" for which in TASKS}
    LOG.parent.mkdir(exist_ok=True)
    LOG.write_text(json.dumps({"summary": summary, "runs": rows}, indent=2), encoding="utf-8")
    print(f"summary {summary}; written to {LOG.relative_to(REPO)}", flush=True)


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    if what not in ("make", "check"):
        raise SystemExit("python -m tools.starter_tasks make | check [runs]")
    print("building the overlay", flush=True)
    build()
    page_url = serve(REPO / "frontend" / "dist")
    if what == "make":
        make(page_url)
    else:
        check(page_url, int(sys.argv[2]) if len(sys.argv) > 2 else 5)


if __name__ == "__main__":
    main()
