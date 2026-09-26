"""How reliably the site view can be photographed, and why it sometimes cannot.

"What are you doing?" answers with a picture of the site view
(`page.preview`), taken with Playwright's screenshot. At a real 100% display
scale on 2026-09-27 that capture succeeded 10 of 20 times, alternating, while
a page that repaints every frame succeeded 20 of 20 (EVALUATION.md,
2026-09-27). This launches the Electron host on its own — no backend, no
replica — and repeats that measurement:

    python -m tools.evaluation.site_capture_run            # the machine's real scaling
    python -m tools.evaluation.site_capture_run 1          # forced 100%
    python -m tools.evaluation.site_capture_run 1.5        # forced 150%

Passes, 20 captures each, 5s timeout per capture:

- `static`, and `static again` on a fresh page: a page that has finished
  drawing and is doing nothing, which is what most site pages are when the
  person asks.
- `repainting`: a page with a `requestAnimationFrame` animation, so the
  compositor always has a new frame to give.

The pattern of each pass is printed as `+` (captured) and `.` (timed out).
Results go to `logs/site_capture_run.json` with the conditions they were taken
under. Uses CDP port 9232, so a running stack on 9222 is left alone.

Needs `npm run build` in frontend/ first.
"""

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

from tools.evaluation.conditions import banner, record

REPO = Path(__file__).resolve().parents[2]
FRONTEND = REPO / "frontend"
PORT = "9232"
CDP = f"http://127.0.0.1:{PORT}"
CAPTURES = 20
TIMEOUT_MS = 5000

STATIC = "<h1>{title}</h1><p>" + "text " * 400 + "</p>"
REPAINTING = """<h1>repainting</h1><div id=d style='width:20px;height:20px;background:red'></div>
<script>let n=0;(function f(){d.style.marginLeft=(n++%200)+'px';requestAnimationFrame(f)})()</script>"""


def launch(scale: str) -> subprocess.Popen:
    electron = FRONTEND / "node_modules" / ".bin" / ("electron.cmd" if os.name == "nt" else "electron")
    args = [str(electron), "."]
    if scale != "native":
        args.append(f"--force-device-scale-factor={scale}")
    env = {**os.environ, "SIMBA_CDP_PORT": PORT, "SIMBA_START_URL": "about:blank"}
    env.pop("ELECTRON_RUN_AS_NODE", None)
    proc = subprocess.Popen(args, cwd=FRONTEND, env=env, shell=os.name == "nt",
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{CDP}/json/version", timeout=1)
            return proc
        except OSError:
            time.sleep(0.5)
    stop(proc)
    raise SystemExit(f"the host did not open CDP on {PORT}")


def stop(proc: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    else:
        proc.terminate()
    proc.wait(timeout=20)


def capture_pass(site, label: str, shoot) -> dict:
    marks, seconds = "", []
    for _ in range(CAPTURES):
        started = time.time()
        try:
            shoot(site)
            marks += "+"
        except Exception:  # noqa: BLE001 — a failed capture is the measurement
            marks += "."
        seconds.append(round(time.time() - started, 2))
    result = {"pass": label, "captured": marks.count("+"), "of": CAPTURES,
              "pattern": marks, "slowest_s": max(seconds)}
    print(f"  {label:<24} {result['captured']:2}/{CAPTURES}  {marks}  "
          f"slowest {result['slowest_s']}s", flush=True)
    return result


def plain(site) -> None:
    site.screenshot(timeout=TIMEOUT_MS)


def measure(scale: str, extra_passes: list[tuple[str, object]] | None = None) -> dict:
    """The passes above, plus any `(label, shoot)` a caller adds."""
    proc = launch(scale)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(CDP)
            site = next(p for c in browser.contexts for p in c.pages
                        if not p.url.startswith("file:"))
            view = site.evaluate("() => ({inner: [innerWidth, innerHeight], dpr: devicePixelRatio})")
            passes = []
            for label, html, shoot in (
                ("static", STATIC.format(title="static"), plain),
                ("static again", STATIC.format(title="static again"), plain),
                ("repainting", REPAINTING, plain),
                *[(lab, STATIC.format(title=lab), fn) for lab, fn in (extra_passes or [])],
            ):
                site.set_content(html)
                site.wait_for_timeout(500)
                passes.append(capture_pass(site, label, shoot))
            browser.close()
    finally:
        stop(proc)
    return {"scale": scale, "site_view": view, "passes": passes}


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    if not (FRONTEND / "dist" / "index.html").exists():
        raise SystemExit("frontend not built; run `npm run build` in frontend/")
    scale = sys.argv[1] if len(sys.argv) > 1 else "native"
    print(banner(), flush=True)
    result = measure(scale)
    out = REPO / "logs" / "site_capture_run.json"
    record(out, [result])
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
