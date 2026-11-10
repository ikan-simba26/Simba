"""Does the SIMBA window fit the screen it opens on, at 100%, 125% and 150%?

Launches the Electron host on its own — no backend, no replica — once per
display scale, and measures from outside it, over CDP:

- **the window**, outer bounds, against the display's work area — both from
  the line the host prints when it fits itself, since Electron's CDP has no
  `Browser.getWindowForTarget` — with the page's `screenX`/`outerHeight` kept
  beside them as a cross-check;
- **the overlay**: its CSS viewport, which is the window's content size at
  zoom 1, the smallest text on the home screen, and where the text box sits —
  it must end inside the viewport with nothing to scroll. **Twice**: once as
  the host opens, with no backend and so no history, and once pointed at a
  scripted backend that offers three remembered goals as long as a card will
  hold (`HISTORY`). Until 2026-09-30 only the first was measured, so the
  home screen this checked always had three cards, while a person with
  history saw six and, at 150%, no text box;
- **every ending**: the overlay pointed at a scripted backend that plays each
  of `frontend/test_terminal_states.ENDINGS` in turn — answers of one, five
  and nine results, no answer, failed, stuck, stopped — and, for each, every
  button on it must be wholly inside the window with nothing to scroll. Until
  2026-10-05 only the home screen was measured, and the closing screen had put
  its way onward below the window with three results or more, at every scale;
- **the sign-in screen** (2026-10-16), the registration's first: its
  buttons and boxes inside the window, nothing to scroll, and the level it
  settled at;
- **the site view**: its CSS viewport, which must be exactly 1280x800, and 20
  screenshots of it in a row, the capture `page.preview` depends on;
- **the brand** (2026-11-02): the window's title, and in each theme the logo
  while opening, the small logo on the fullest home screen, and a step with
  neither, with a picture of each in `.scratch/brand/`; and under reduced
  motion, that there is no logo while opening.

Then it saves a picture of the overlay page, which is the window's whole
content area (CLAUDE.md: the application's own view, never the desktop).

    python -m tools.evaluation.display_fit_run                 # 1, 1.25, 1.5
    python -m tools.evaluation.display_fit_run native          # the real scaling
    python -m tools.evaluation.display_fit_run 1.25            # one forced scale

**The scales are forced, not real.** Chromium's `--force-device-scale-factor`
makes the host see the physical screen at that scale; Windows' own setting is
not changed, because that is the machine's configuration and not this repo's.
The taskbar keeps its real height in physical pixels, so on a machine set to
150% a forced 100% or 125% has a slightly smaller work area than a real one —
the stricter case. `native` measures whatever the machine is set to.

Needs `npm run build` in frontend/ first. Uses CDP port 9232 so it cannot
collide with a running stack on 9222.
"""

import asyncio
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from urllib.parse import quote
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from tools.evaluation.conditions import banner, record

REPO = Path(__file__).resolve().parents[2]
FRONTEND = REPO / "frontend"
OUT = REPO / ".scratch" / "screenshots" / "fit"
BRAND_OUT = REPO / ".scratch" / "brand"
THEMES = ("light", "dark")
PORT = "9232"
CDP = f"http://127.0.0.1:{PORT}"
SCALES = ["1", "1.25", "1.5"]
TEXTBOX = "What would you like me to do?"
CAPTURES = 20

# Three remembered goals at the limit of what a card holds: two lines even at
# the compact layout's 23px, so every card is as tall as a card can be.
#: The person's own tiles (2026-10-18), three — as many as there can be — so
#: the home screen with history is the fullest it gets.
OWN_TILES = [{"id": "a1", "label": "My bill", "flow": "billing"},
             {"id": "b2", "label": "Trains to Karachi", "flow": "railways"},
             {"id": "c3", "label": "Trains home", "flow": "railways"}]

#: Whether one question of the welcome fits: nothing scrolls, and every button
#: on it is wholly in the window.
WELCOME_FITS = """() => {
  const scrolls = document.scrollingElement.scrollHeight > innerHeight;
  const off = [...document.querySelectorAll('[data-testid=welcome] button')]
    .filter(b => b.offsetParent && !b.closest('[aria-hidden=true]'))
    .filter(b => { const r = b.getBoundingClientRect();
                   return r.top < 0 || r.bottom > innerHeight || r.right > innerWidth; })
    .map(b => b.innerText.trim());
  return {question: document.querySelector('[data-testid=welcome]').dataset.question,
          scrolls, off};
}"""

HISTORY = [
    f"Find the amount due for reference number {n}. Then tell me which of them "
    "is due first and how much it is."
    for n in ("04141234567890", "04149999999999", "04145555555555")
]


class ScriptedHistory:
    """A backend that says hello with `HISTORY` and nothing more."""

    def __init__(self) -> None:
        import asyncio
        import threading

        import websockets

        self.port = 0
        started = threading.Event()

        def run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def handler(ws):
                await ws.send(json.dumps({
                    "v": 1, "type": "history.offered", "task_id": "t_fit", "seq": 1,
                    "ts": 0, "payload": {"goals": [{"goal": g, "site": "fit"} for g in HISTORY],
                                         "tiles": OWN_TILES},
                }))
                try:
                    async for _ in ws:
                        pass
                except websockets.ConnectionClosed:
                    return

            async def main() -> None:
                server = await websockets.serve(handler, "127.0.0.1", 0)
                self.port = server.sockets[0].getsockname()[1]
                started.set()
                await asyncio.Future()

            loop.run_until_complete(main())

        threading.Thread(target=run, daemon=True).start()
        started.wait(timeout=10)


# A page that scrolls, with an inner scroll box, for the site view's layout
# width. Hidden scrollbars (2026-09-30) must leave both at the full 1280px and
# the page still scrollable, on the first page and on the next.
LAYOUT_PAGE = "data:text/html," + quote(
    "<!doctype html><html><body style='margin:0'>"
    "<div id=wide style='width:100%;height:40px'></div>"
    "<div id=box style='height:120px;overflow-y:scroll'>" + "line<br>" * 40 + "</div>"
    + "<p>text</p>" * 200 + "</body></html>")

LAYOUT_JS = """() => {
    window.scrollTo(0, 600);
    return {
        client: document.documentElement.clientWidth,
        wide: Math.round(document.getElementById('wide').getBoundingClientRect().width),
        inner_box: document.getElementById('box').clientWidth,
        scrolled_to: Math.round(window.scrollY),
    };
}"""


def site_layout(site: Page) -> dict:
    """The site view's layout width on a page that scrolls, twice over."""
    first = None
    for _ in range(2):
        site.goto(LAYOUT_PAGE)
        site.wait_for_timeout(500)
        first = first or site.evaluate(LAYOUT_JS)
    return {"first_page": first, "next_page": site.evaluate(LAYOUT_JS)}


HOME_JS = """(label) => {
    const box = document.querySelector(`[aria-label="${label}"]`)
        || [...document.querySelectorAll('textarea,input')][0];
    const r = box.getBoundingClientRect();
    const entry = document.querySelector('[data-testid=teach-entry]');
    const teach = entry ? entry.getBoundingClientRect() : null;
    const greeting = document.querySelector('[data-testid=greeting]').getBoundingClientRect();
    // The smallest text a person can see: every element that
    // holds text of its own, is rendered, and is inside the
    // window.
    const sizes = [...document.querySelectorAll('body *')]
        .filter(el => [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())
                      || (el.tagName === 'INPUT' && el.placeholder))
        .filter(el => { const b = el.getBoundingClientRect();
                        return b.width > 0 && b.height > 0 && b.top < innerHeight
                               && getComputedStyle(el).opacity !== '0'; })
        .map(el => parseFloat(getComputedStyle(el).fontSize));
    return {
        inner: [innerWidth, innerHeight],
        dpr: devicePixelRatio,
        scroll_height: document.documentElement.scrollHeight,
        box_top: Math.round(r.top), box_bottom: Math.round(r.bottom),
        smallest_text_px: Math.min(...sizes),
        input_text_px: parseFloat(getComputedStyle(box).fontSize),
        cards: document.querySelectorAll('[data-testid=tile]').length,
        remembered: document.querySelectorAll('[data-testid=remembered]').length,
        // The way in for a helper (2026-11-10), in the top right corner:
        // wholly in the window, and above the person's column.
        teach_in_viewport: teach !== null && teach.top >= 0 && teach.bottom <= innerHeight
                           && teach.right <= innerWidth,
        teach_clear: teach !== null && teach.bottom <= greeting.top,
    };
}"""


def read_home(overlay: Page) -> dict:
    """Where the home screen's text box is, and whether the page scrolls."""
    view = overlay.evaluate(HOME_JS, TEXTBOX)
    box = overlay.get_by_role("textbox", name=TEXTBOX)
    view["box_in_viewport"] = box.is_visible() and view["box_bottom"] <= view["inner"][1]
    view["scrolls"] = view["scroll_height"] > view["inner"][1]
    return view


# The ending whose picture is saved: the tallest closing screen there is.
TALLEST_ENDING = "completed with nine results and a sentence"


def said(scale: str, what: str) -> None:
    """One line per stage, with the time since the host was started
    (2026-10-17). A run once took 22 minutes and ended with the host's pages
    closed, and nothing said which stage the time went on; pytest shows these
    lines with a failure."""
    print(f"fit {scale} {time.monotonic() - STARTED.get(scale, time.monotonic()):7.1f}s "
          f"{what}", flush=True)


#: When each scale's host was started, for `said`.
STARTED: dict[str, float] = {}


def read_welcome(overlay: Page, scale: str) -> list[dict]:
    """Each question of the welcome as a new person meets it (2026-10-18):
    whether it fits, and its picture. Empty if the host opened on the home
    screen instead. With no backend here, it comes after the logo's 15s."""
    try:
        overlay.get_by_test_id("welcome").wait_for(timeout=30000)
    except Exception:  # noqa: BLE001 - no welcome is a finding, not a failure here
        return []
    measured = []
    for _ in range(4):
        overlay.wait_for_timeout(900)  # past the arrival and the press guard
        fit = overlay.evaluate(WELCOME_FITS)
        capture_view(overlay, OUT / f"welcome-{scale}-{fit['question']}.png")
        measured.append(fit)
        overlay.get_by_test_id("welcome-skip").click()
    return measured


def read_endings(overlay: Page, scale: str) -> dict[str, dict]:
    """Every ending, played into the real window, and where its buttons are.

    The same endings and the same measurement `test_terminal_states.py` runs
    in a headless browser at each scale's size, here inside the host itself.
    """
    # Here, not at the top: the tests import this module.
    from frontend.test_terminal_states import ENDINGS, Backend, onward, reach

    backend = Backend()
    base = overlay.url.split("?")[0]
    measured = {}
    for name in ENDINGS:
        said(scale, f"ending: {name}")
        reach(overlay, base, backend, name)
        measured[name] = onward(overlay)
        if name == TALLEST_ENDING:
            capture_view(overlay, OUT / f"ending-{scale}.png")
    return measured


#: Where a logo is, and what it is drawn from. `file` is the source's name,
#: without the build's hash: Vite's eight characters, which can hold a `-`
#: themselves (`...-small-dark-D3-JexYj.svg`, 2026-11-03).
LOGO_JS = """(selector) => {
    const holder = document.querySelector(selector);
    if (!holder) return null;
    const img = holder.querySelector('img');
    const b = img.getBoundingClientRect();
    const touches = [...document.querySelectorAll(
        '[data-presence], h1, section, input, [data-testid=own-tile], [data-testid=tile]')]
        .filter(el => { const o = el.getBoundingClientRect();
                        return o.width > 0 && b.left < o.right && b.right > o.left
                               && b.top < o.bottom && b.bottom > o.top; }).length;
    return {file: img.currentSrc.split('/').pop().replace(/-[\\w-]{8}\\.svg$/, ''),
            loaded: img.naturalWidth > 0, touches,
            box: [b.left, b.top, b.right, b.bottom].map(Math.round),
            whole: b.left >= 0 && b.top >= 0 && b.right <= innerWidth && b.bottom <= innerHeight,
            centred: Math.abs((b.left + b.right) / 2 - innerWidth / 2) <= 1
                     && Math.abs((b.top + b.bottom) / 2 - innerHeight / 2) <= 1,
            scrolls: document.scrollingElement.scrollHeight > innerHeight};
}"""


def read_brand(overlay: Page, scale: str) -> dict:
    """The logo while opening, and the small logo on the fullest home screen,
    in each theme, in the real window, with a picture of each; then that
    reduced motion shows no logo (2026-11-02). A theme is the system's, so it
    is emulated here rather than changed on the machine."""
    base = overlay.url.split("?")[0]
    history = ScriptedHistory()
    measured: dict = {}
    BRAND_OUT.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        overlay.emulate_media(color_scheme=theme)
        said(scale, f"the logo while opening, {theme}")
        # A port nothing answers on, so the logo stays up to be measured.
        overlay.goto(f"{base}?ws=ws://127.0.0.1:1/ws")
        overlay.get_by_test_id("splash").wait_for(timeout=15000)
        overlay.wait_for_timeout(900)  # the fade in
        splash = overlay.evaluate(LOGO_JS, "[data-testid=splash]")
        capture_view(overlay, BRAND_OUT / f"splash-{scale}-{theme}.png", theme)

        said(scale, f"the small logo, {theme}")
        overlay.emulate_media(color_scheme=theme)  # undone by that capture
        overlay.goto(f"{base}?ws=ws://127.0.0.1:{history.port}")
        overlay.get_by_test_id("own-tile").first.wait_for(timeout=30000)
        overlay.wait_for_timeout(1400)
        home = overlay.evaluate(LOGO_JS, "[data-testid=home-logo]")
        capture_view(overlay, BRAND_OUT / f"home-{scale}-{theme}.png", theme)
        measured[theme] = {"splash": splash, "home": home}

    overlay.emulate_media(color_scheme="no-override", reduced_motion="reduce")
    overlay.goto(f"{base}?ws=ws://127.0.0.1:1/ws")
    overlay.get_by_role("textbox", name=TEXTBOX).wait_for(timeout=5000)
    measured["reduced_motion_logos"] = overlay.get_by_test_id("splash").count()
    overlay.emulate_media(reduced_motion="no-override")
    return measured


def read_brand_steps(overlay: Page, scale: str) -> dict:
    """A step in each theme: the shape is there, the small logo is not."""
    measured = {}
    for theme in THEMES:
        overlay.emulate_media(color_scheme=theme)
        step = read_sign_in(overlay, f"{scale}-{theme}", out=BRAND_OUT, name="step", theme=theme)
        measured[theme] = {"home_logos": step["home_logos"], "shapes": step["shapes"],
                           "off_screen": step["off_screen"], "scrolls": step["scrolls"]}
    overlay.emulate_media(color_scheme="no-override")
    return measured


def window_title() -> str | None:
    """The title Windows has for the host listening on `PORT`; None elsewhere."""
    if os.name != "nt":
        return None
    script = (f"(Get-Process -Id (Get-NetTCPConnection -LocalPort {PORT} -State Listen)"
              ".OwningProcess).MainWindowTitle")
    done = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                          capture_output=True, text=True, timeout=30)
    return done.stdout.strip()


def read_sign_in(overlay: Page, scale: str, out: Path = OUT, name: str = "sign-in",
                 theme: str | None = None) -> dict:
    """The registration's first screen, signing in (2026-10-16), played into
    the real window as the backend sends it: where its buttons are, whether
    anything scrolls, and the level it settled at once the overflow guard had
    had its one move. Measured headless only until 2026-10-16, where Electron
    lays text out wider (EVALUATION.md, 2026-10-16)."""
    from frontend.test_first_screen import level_on_screen
    from frontend.test_sign_in import SIGN_IN, STAGES
    from frontend.test_terminal_states import AWAIT_RESPONSE, Backend, onward

    backend = Backend()
    backend.script = [
        ("task.started", {"goal": "course", "estimated_steps": 4, "stages": STAGES}),
        ("state.changed", {"state": "waiting"}), ("step.presented", SIGN_IN),
        (AWAIT_RESPONSE, {}),
    ]
    overlay.goto(overlay.url.split("?")[0] + f"?ws=ws://127.0.0.1:{backend.port}")
    overlay.wait_for_timeout(800)  # a press on a button just arrived is ignored
    overlay.fill("input[aria-label='What would you like me to do?']", "course")
    overlay.get_by_role("button", name="Start").click()
    overlay.get_by_text("Let me sign you in first.").first.wait_for(timeout=15000)
    overlay.wait_for_timeout(1800)  # past the guard
    measured = onward(overlay)
    measured["level"] = level_on_screen(overlay)
    measured["fields_on_screen"] = overlay.evaluate("""() => [...document.querySelectorAll(
        '[data-testid=step-shell] input')].filter(i => i.offsetParent).every(
        i => i.getBoundingClientRect().bottom <= innerHeight)""")
    measured["home_logos"] = overlay.get_by_test_id("home-logo").count()
    measured["shapes"] = overlay.get_by_test_id("shape").count()
    capture_view(overlay, out / f"{name}-{scale}.png", theme)
    return measured


def launch(scale: str) -> tuple[subprocess.Popen, Path]:
    electron = FRONTEND / "node_modules" / ".bin" / ("electron.cmd" if os.name == "nt" else "electron")
    log = OUT / f"host-{scale}.log"
    args = [str(electron), "."]
    if scale != "native":
        args.append(f"--force-device-scale-factor={scale}")
    # A host of its own storage, empty, so it opens as for a new person — the
    # welcome first (2026-10-18) — and never touches the real person's profile.
    user_data = OUT / f"user-data-{scale}"
    shutil.rmtree(user_data, ignore_errors=True)
    env = {**os.environ, "SIMBA_CDP_PORT": PORT, "SIMBA_START_URL": "about:blank",
           "SIMBA_USER_DATA": str(user_data)}
    env.pop("ELECTRON_RUN_AS_NODE", None)
    proc = subprocess.Popen(args, cwd=FRONTEND, env=env, stdout=log.open("w"),
                            stderr=subprocess.STDOUT, shell=os.name == "nt")
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{CDP}/json/version", timeout=1)
            return proc, log
        except OSError:
            time.sleep(0.5)
    raise SystemExit(f"the host did not open CDP on {PORT}; see {log}")


def stop(proc: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       capture_output=True)
    else:
        proc.terminate()
    proc.wait(timeout=20)
    time.sleep(1.5)


def capture_view(page: Page, path: Path, theme: str | None = None) -> None:
    """Save what the overlay view is showing, at the size it is shown.

    With `theme`, in that theme (2026-11-02). A theme here is an emulation, and
    the connection below undoes the caller's as it attaches, so the first pass
    of the brand's pictures came out light whatever they were named: the page
    had said dark a moment before. The caller has to set it again afterwards.

    Not `page.screenshot()`. Playwright sizes its capture as the CSS viewport
    times the screen's scale and knows nothing of the overlay's zoom, so at
    150% it returned a 1280x800-DIP picture with the real 969x606 view in its
    top-left corner and page background round it. The raw capture with no
    clip returns the view's own surface.

    Through `browser.capture_site` since 2026-10-17, which asks again while a
    capture stalls and gives up after a few seconds. This sent one raw
    request and retried only if it raised, and at 100% a stalled one never
    does: one run of the host fit test sat here for 14 minutes until it was
    stopped, and one on 2026-10-17 at 01:15 for most of 22 before its page
    closed (EVALUATION.md, 2026-10-17h). Taken over a connection of its own,
    on its own thread, because `capture_site` is async and this is not.
    """
    url = page.url

    async def shoot() -> bytes:
        from playwright.async_api import async_playwright

        from backend.orchestrator.browser import capture_site

        async with async_playwright() as playwright:
            browser = await playwright.chromium.connect_over_cdp(CDP)
            try:
                view = next(p for c in browser.contexts for p in c.pages if p.url == url)
                if theme:
                    await view.emulate_media(color_scheme=theme)
                    await view.wait_for_timeout(300)  # the theme's own picture
                return await capture_site(view)
            finally:
                await browser.close()  # detaches; the host is the caller's to stop

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        path.write_bytes(pool.submit(asyncio.run, shoot()).result())


#: Whether the page is getting frames, from inside it. Playwright's click waits
#: on `requestAnimationFrame`, and a page with none times out on "visible,
#: enabled and stable" with nothing to say why (2026-11-02).
FRAMES_JS = """() => new Promise((answer) => {
    const say = (frames) => answer({frames, hidden: document.hidden,
                                    focused: document.hasFocus(),
                                    window: window.__simbaWindow ?? null});
    const none = setTimeout(() => say(false), 2000);
    requestAnimationFrame(() => { clearTimeout(none); say(true); });
})"""


def host_line(log: Path) -> dict:
    """What the host said about the display it fitted itself to, if anything."""
    for _ in range(20):
        text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
        match = re.search(r"SIMBA fit (\{.*\})", text)
        if match:
            return json.loads(match.group(1))
        time.sleep(0.25)
    return {}


def measure(scale: str) -> dict:
    STARTED[scale] = time.monotonic()
    proc, log = launch(scale)
    said(scale, "host answering on CDP")
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(CDP)
            pages = [p for c in browser.contexts for p in c.pages]
            overlay = next(p for p in pages if p.url.startswith("file:"))
            site = next(p for p in pages if not p.url.startswith("file:"))
            overlay.wait_for_load_state()
            # A new person's first open: the welcome, each question measured
            # and kept as a picture, then skipped through to the home screen.
            welcome = read_welcome(overlay, scale)
            overlay.get_by_role("textbox", name=TEXTBOX).wait_for()
            overlay.wait_for_timeout(1200)  # let the entrance animation finish

            # Electron's CDP has no `Browser.getWindowForTarget`, so the window
            # comes from the host's own line; the page's idea of it is kept
            # beside it as a cross-check.
            page_window = overlay.evaluate("""() => ({
                screen_x: screenX, screen_y: screenY,
                outer: [outerWidth, outerHeight],
                avail: [screen.availLeft, screen.availTop, screen.availWidth, screen.availHeight],
            })""")

            said(scale, "home screen up")
            view = read_home(overlay)

            site_view = site.evaluate("() => ({inner: [innerWidth, innerHeight], dpr: devicePixelRatio})")
            site_view["layout"] = site_layout(site)
            site.set_content("<h1 style='font:48px sans-serif'>site view</h1>"
                             "<p>" + "text " * 400 + "</p>")
            said(scale, "site view laid out; capturing it")
            ok = 0
            for _ in range(CAPTURES):
                try:
                    site.screenshot(timeout=5000)
                    ok += 1
                except Exception:  # noqa: BLE001 — a failed capture is the measurement
                    pass

            OUT.mkdir(parents=True, exist_ok=True)
            name = f"home-{scale}.png"
            said(scale, f"site view captured {ok}/{CAPTURES}; capturing the overlay")
            capture_view(overlay, OUT / name)
            said(scale, "overlay captured; the home screen with history")

            # The same screen for someone with history: the overlay pointed
            # at a backend that offers three remembered goals.
            history = ScriptedHistory()
            overlay.goto(overlay.url.split("?")[0] + f"?ws=ws://127.0.0.1:{history.port}")
            overlay.get_by_role("textbox", name=TEXTBOX).wait_for()
            overlay.wait_for_function(
                "g => document.body.textContent.includes(g)", arg=HISTORY[0], timeout=15000)
            overlay.wait_for_timeout(1200)
            overlay.get_by_test_id("own-tile").first.wait_for(timeout=15000)
            with_history = read_home(overlay)
            with_history["own_tiles"] = overlay.get_by_test_id("own-tile").count()
            capture_view(overlay, OUT / f"home-{scale}-history.png")

            title = window_title()
            brand = read_brand(overlay, scale)
            # Every load from here is a screen, not an opening: the logo has
            # been measured, and there are seventeen endings to reach.
            overlay.add_init_script("window.__simbaSplash = false")
            brand["steps"] = read_brand_steps(overlay, scale)

            endings = read_endings(overlay, scale)
            said(scale, "the sign-in screen")
            sign_in = read_sign_in(overlay, scale)
            said(scale, "done")
            browser.close()
    except Exception as error:
        said(scale, f"failed: {error!r}"[:300])
        try:
            said(scale, f"the overlay at that moment: {overlay.evaluate(FRAMES_JS)}")
        except Exception as gone:  # noqa: BLE001 - a dead page is itself the finding
            said(scale, f"the overlay did not answer: {gone!r}"[:200])
        # The host's own account of why it went, if it said (frontend/electron/main.ts).
        text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
        for line in text.splitlines():
            if line.startswith("SIMBA host ") and "ready" not in line:
                print(line, flush=True)
        raise
    finally:
        stop(proc)

    fit = host_line(log)
    work = fit.get("work_area")
    window = fit.get("window")
    result = {
        "scale": scale,
        "host_says": fit,
        "page_says": page_window,
        "overlay": view,
        "overlay_with_history": with_history,
        "endings": endings,
        "welcome": welcome,
        "sign_in": sign_in,
        "window_title": title,
        "brand": brand,
        "site_view": {**site_view, "captures": f"{ok}/{CAPTURES}"},
        "screenshot": name,
    }
    content = fit.get("content")
    if content:
        # Zoom 1 means the overlay's CSS size is the window's content size.
        result["overlay_matches_window"] = (
            abs(view["inner"][0] - content["width"]) <= 1
            and abs(view["inner"][1] - content["height"]) <= 1
        )
    if work and window:
        result["window_fits_work_area"] = (
            window["x"] >= work["x"] and window["y"] >= work["y"]
            and window["x"] + window["width"] <= work["x"] + work["width"]
            and window["y"] + window["height"] <= work["y"] + work["height"]
        )
    return result


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    if not (FRONTEND / "dist" / "index.html").exists():
        raise SystemExit("frontend not built; run `npm run build` in frontend/")
    if shutil.which("taskkill") is None and os.name == "nt":
        raise SystemExit("taskkill not found")
    OUT.mkdir(parents=True, exist_ok=True)
    print(banner(), flush=True)
    scales = sys.argv[1:] or SCALES
    results = [measure(scale) for scale in scales]
    print(json.dumps(results, indent=2))
    out = REPO / "logs" / "display_fit_run.json"
    record(out, results)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
