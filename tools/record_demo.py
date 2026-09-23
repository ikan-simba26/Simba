"""Screen recordings of SIMBA running, as fallbacks for a demo.

A demo can fail for reasons that have nothing to do with the work: the live
railways site is down, the room has no internet, the host will not start. These
are the same runs, recorded, so the talk can go on.

    .\\run.ps1 billing                       # in one terminal, for the real ones
    python -m tools.record_demo              # in another

    python -m tools.record_demo mock         # only the clips needing no stack
    python -m tools.record_demo hello fold   # or name the clips

**What is recorded.** The real overlay, built from source, talking to the real
backend over the websocket — the same conversation the Electron window has.
The backend drives the hidden site view exactly as it does in the product; the
overlay is simply rendered in a browser that can record, which the Electron
window cannot. The picture is the overlay's own 1280x800, never the desktop
(CLAUDE.md, "Tooling boundaries").

The railways clip uses the live site once. One recording, kept, is the point:
it is what saves the demo from needing the site at all.
"""

import functools
import http.server
import shutil
import socketserver
import subprocess
import sys
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[1]
FRONTEND = REPO / "frontend"
BUILD = FRONTEND / "dist"
OUT = REPO / "demo"

#: Where the real stack and the mock listen. `run.ps1` uses 8000; the mock is
#: started here on a port of its own so both can be up at once.
REAL_WS = "ws://127.0.0.1:8000/ws"
MOCK_PORT = 8010
MOCK_WS = f"ws://127.0.0.1:{MOCK_PORT}/ws"

#: Long enough that a watcher can read the screen before the next press. A
#: recording is for an audience, not a benchmark.
BEAT_MS = 1800

ENDED = ("I'm done", "I'm stuck, so I've stopped.", "I couldn't finish this.")

#: (name, which backend, what to type, what it shows)
CLIPS: list[tuple[str, str, str, str]] = [
    ("railways", "real", "Show me trains from Lahore to Karachi",
     "the live site, five steps, ending on the train and the journey time"),
    ("billing", "real", "What do I owe on my electricity bill?",
     "the billing replica, three steps, ending on the amount and the due date"),
    ("hello", "real", "hello",
     "a greeting and the three things SIMBA can do — no task started"),
    ("fold", "mock", "Register for CS-401",
     "the scripted run, including the fold from one detail level to the next"),
]


class Quiet(http.server.SimpleHTTPRequestHandler):
    """Serving a file is not news; the clip's own line is the output."""

    def log_message(self, *args) -> None:
        pass


def serve(directory: Path) -> str:
    handler = functools.partial(Quiet, directory=str(directory))
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_address[1]}/index.html"


def build() -> None:
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if npx is None:
        raise SystemExit("npx is not on PATH; install Node and run npm install in frontend/")
    done = subprocess.run([npx, "vite", "build", "--logLevel", "error"],
                          cwd=FRONTEND, capture_output=True, text=True, timeout=300)
    if done.returncode != 0:
        raise SystemExit(done.stderr)


def record(playwright, name: str, ws: str, goal: str, page_url: str) -> tuple[Path, list[str]]:
    """One clip: type the goal, press through whatever comes back, keep it.

    Returns the file and what was on screen along the way. A recording nobody
    has watched is not evidence of anything, so the caller prints the path: a
    clip that stopped early or never started is visible without opening it.
    """
    browser = playwright.chromium.launch()
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        record_video_dir=str(OUT / "_raw"),
        record_video_size={"width": 1280, "height": 800},
    )
    page = context.new_page()
    page.goto(f"{page_url}?ws={ws}")
    page.wait_for_timeout(BEAT_MS)

    # Typed rather than filled, so the recording shows it being written.
    box = page.get_by_role("textbox", name="What would you like me to do?")
    box.click()
    box.type(goal, delay=45)
    page.wait_for_timeout(700)
    page.keyboard.press("Enter")

    seen: list[str] = []
    deadline = time.time() + 300
    while time.time() < deadline:
        page.wait_for_timeout(600)
        text = page.evaluate("() => document.body.innerText")
        if any(ending in text for ending in ENDED):
            seen.append("ended")
            break
        # A reply: nothing starts, and that is the clip.
        if "Here's what I can help with" in text:
            seen.append("greeted")
            break
        if "I can't do that yet." in text:
            seen.append("declined")
            break
        shell = page.locator("[data-testid=step-shell]")
        if shell.count() and shell.first.is_visible():
            go = shell.first.locator("button:not([disabled])").first
            if go.count():
                label = go.inner_text().strip()
                if not seen or seen[-1] != label:
                    seen.append(label)
                    page.wait_for_timeout(BEAT_MS)
                    go.click()
    page.wait_for_timeout(2500)  # let the last screen be read

    video = page.video
    context.close()          # the file is only written when the context closes
    browser.close()
    kept = OUT / f"{name}.webm"
    if kept.exists():
        kept.unlink()
    Path(video.path()).rename(kept)
    return kept, seen


def start_mock() -> subprocess.Popen:
    import urllib.request

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "tools.mock_backend:app", "--port", str(MOCK_PORT)],
        cwd=REPO, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{MOCK_PORT}/", timeout=1)
            return proc
        except OSError:
            time.sleep(0.3)
    proc.terminate()
    raise SystemExit("the mock backend did not start")


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    wanted = [a for a in sys.argv[1:] if a != "mock"]
    only_mock = "mock" in sys.argv[1:]
    clips = [c for c in CLIPS
             if (not wanted or c[0] in wanted) and (not only_mock or c[1] == "mock")]
    if not clips:
        raise SystemExit(f"nothing to record; clips are {[c[0] for c in CLIPS]}")

    OUT.mkdir(exist_ok=True)
    (OUT / "_raw").mkdir(exist_ok=True)
    print("building the overlay", flush=True)
    build()
    page_url = serve(BUILD)

    mock = start_mock() if any(c[1] == "mock" for c in clips) else None
    try:
        with sync_playwright() as playwright:
            for name, backend, goal, shows in clips:
                ws = MOCK_WS if backend == "mock" else REAL_WS
                started = time.time()
                kept, seen = record(playwright, name, ws, goal, page_url)
                size = kept.stat().st_size / 1_000_000
                print(f"  {name:<9} {shows}\n            {kept.name} "
                      f"({size:.1f} MB, {time.time() - started:.0f}s) "
                      f"-> {' | '.join(seen)}", flush=True)
    finally:
        if mock is not None:
            mock.terminate()
            mock.wait(timeout=10)
        shutil.rmtree(OUT / "_raw", ignore_errors=True)


if __name__ == "__main__":
    main()
