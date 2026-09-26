"""Does the SIMBA window fit the screen it opens on, at 100%, 125% and 150%?

Launches the Electron host on its own — no backend, no replica — once per
display scale, and measures from outside it, over CDP:

- **the window**, outer bounds, against the display's work area — both from
  the line the host prints when it fits itself, since Electron's CDP has no
  `Browser.getWindowForTarget` — with the page's `screenX`/`outerHeight` kept
  beside them as a cross-check;
- **the overlay**: its CSS viewport, which is the window's content size at
  zoom 1, the smallest text on the home screen, and where the text box sits —
  it must end inside the viewport with nothing to scroll;
- **the site view**: its CSS viewport, which must be exactly 1280x800, and 20
  screenshots of it in a row, the capture `page.preview` depends on.

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

import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from tools.evaluation.conditions import banner, record

REPO = Path(__file__).resolve().parents[2]
FRONTEND = REPO / "frontend"
OUT = REPO / ".scratch" / "screenshots" / "fit"
PORT = "9232"
CDP = f"http://127.0.0.1:{PORT}"
SCALES = ["1", "1.25", "1.5"]
TEXTBOX = "What would you like me to do?"
CAPTURES = 20


def launch(scale: str) -> tuple[subprocess.Popen, Path]:
    electron = FRONTEND / "node_modules" / ".bin" / ("electron.cmd" if os.name == "nt" else "electron")
    log = OUT / f"host-{scale}.log"
    args = [str(electron), "."]
    if scale != "native":
        args.append(f"--force-device-scale-factor={scale}")
    env = {**os.environ, "SIMBA_CDP_PORT": PORT, "SIMBA_START_URL": "about:blank"}
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


def capture_view(page: Page, path: Path) -> None:
    """Save what the overlay view is showing, at the size it is shown.

    Not `page.screenshot()`. Playwright sizes its capture as the CSS viewport
    times the screen's scale and knows nothing of the overlay's zoom, so at
    150% it returned a 1280x800-DIP picture with the real 969x606 view in its
    top-left corner and page background round it. The raw call with no clip
    returns the view's own surface. One retry, because a capture of a page
    that has not changed can wait for a frame that never comes.
    """
    session = page.context.new_cdp_session(page)
    for attempt in range(2):
        try:
            shot = session.send("Page.captureScreenshot", {"format": "png"})
            path.write_bytes(base64.b64decode(shot["data"]))
            return
        except Exception:  # noqa: BLE001 — retried once, then raised
            if attempt:
                raise


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
    proc, log = launch(scale)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(CDP)
            pages = [p for c in browser.contexts for p in c.pages]
            overlay = next(p for p in pages if p.url.startswith("file:"))
            site = next(p for p in pages if not p.url.startswith("file:"))
            overlay.wait_for_load_state()
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

            view = overlay.evaluate("""(label) => {
                const box = document.querySelector(`[aria-label="${label}"]`)
                    || [...document.querySelectorAll('textarea,input')][0];
                const r = box.getBoundingClientRect();
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
                };
            }""", TEXTBOX)
            box = overlay.get_by_role("textbox", name=TEXTBOX)
            view["box_in_viewport"] = box.is_visible() and view["box_bottom"] <= view["inner"][1]
            view["scrolls"] = view["scroll_height"] > view["inner"][1]

            site_view = site.evaluate("() => ({inner: [innerWidth, innerHeight], dpr: devicePixelRatio})")
            site.set_content("<h1 style='font:48px sans-serif'>site view</h1>"
                             "<p>" + "text " * 400 + "</p>")
            ok = 0
            for _ in range(CAPTURES):
                try:
                    site.screenshot(timeout=5000)
                    ok += 1
                except Exception:  # noqa: BLE001 — a failed capture is the measurement
                    pass

            OUT.mkdir(parents=True, exist_ok=True)
            name = f"home-{scale}.png"
            capture_view(overlay, OUT / name)
            browser.close()
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
