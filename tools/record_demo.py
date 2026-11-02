"""Screen recordings of SIMBA running, as fallbacks for a demo.

A demo can fail for reasons that have nothing to do with the work: the live
railways site is down, the room has no internet, the host will not start. These
are the same runs, recorded, so the talk can go on.

    .\\run.ps1 railways-local                # in one terminal, for the real ones
    python -m tools.record_demo              # in another

    python -m tools.record_demo mock         # only the clips needing no stack
    python -m tools.record_demo hello fold   # or name the clips

**What is recorded.** The real overlay, built from source, talking to the real
backend over the websocket — the same conversation the Electron window has.
The backend drives the hidden site view exactly as it does in the product; the
overlay is simply rendered in a browser that can record, which the Electron
window cannot. The picture is the overlay's own 1280x800, never the desktop
(CLAUDE.md, "Tooling boundaries").

**No clip touches the live site.** The railways clip runs on our own copy of
the train search: start the stack with `railways-local`, and this asks the
backend where a train goal would run before recording one, and refuses if the
answer is the live site (since 2026-10-01; until then the railways clip was the
one time a recording used the live site).

**Clips answer questions.** Since 2026-09-30 a goal that leaves something out
is asked about, and a clip that only pressed the first button on every screen
would press "That's it" on an empty box until the run gave up. Each clip says
what to type when it is asked and which answer to press (`ANSWERS`), the way
DEMO.md tells a presenter to.
"""

import functools
import http.server
import json
import shutil
import socketserver
import subprocess
import sys
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from tools.evaluation.adaptation_stack_run import SIMPLER, hesitate

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

ENDED = ("Back to start", "I'm stuck, so I've stopped.", "I couldn't finish this.")

#: (name, which backend, what to type, what it shows)
CLIPS: list[tuple[str, str, str, str]] = [
    ("railways", "real", "trains to Rawalpindi tomorrow",
     "our copy of the train search: where from, which Lahore station, the day, the "
     "journey said back, the search as a checklist, the trains as tickets, and the "
     "answer on the real page"),
    # A booking with its final screen (2026-10-16): "book" in the goal goes
    # straight on from the trains to "Which train?".
    ("booking", "real", "book a train from Lahore to Karachi tomorrow",
     "which station at each end, the read-back, the checklist, which train, a name, "
     "a class, the final screen held, Book it, the site's confirmation and the page"),
    ("billing", "real", "What do I owe on my electricity bill?",
     "the billing replica: the reference number, cookies asked Yes or No, the "
     "lookup as a checklist, the bill in plain words, and the answer on the real page"),
    ("hello", "real", "hello",
     "a greeting and the three things SIMBA can do — no task started"),
    ("fold", "mock", "Register for CS-401",
     "the scripted run, including the fold from one detail level to the next"),
    # No notice is shown on a task's first screen (2026-10-14), so the clip
    # answers the first — the reference number — and hesitates on the second,
    # the cookie question, until it folds. Needs a stack with
    # SIMBA_PAGE_MODEL=0: the trained estimator starts billing at level 3, and
    # nothing folds from there (DEMO.md).
    ("adapt", "real", "What do I owe on my electricity bill?",
     "billing, hesitating on the cookie question until it folds, then calm, and back"),
]

#: What each clip types when it is asked something, in order, and which answer
#: it presses when a question offers several — what DEMO.md tells a presenter
#: to do. A clip with nothing here presses each screen's first button.
ANSWERS: dict[str, dict[str, list[str]]] = {
    "railways": {"type": ["Lahore"], "pick": ["Lahore Cantt"]},
    "booking": {"type": ["Ayesha Khan"],
                "pick": ["Lahore Cantt", "Karachi Cantt", "AC Standard"]},
    "billing": {"type": ["04141234567890"]},
    "adapt": {"type": ["04141234567890"]},
    # The mock's third step has a box to fill (2026-10-15: its button waits
    # for it).
    "fold": {"type": ["S-2026-0142"]},
}

#: Clips whose closing screen then opens "See it on the real page" for a beat.
SHOWS_PROOF = {"railways", "booking", "billing"}

#: The live site. No clip may run there.
LIVE_RAILWAYS = "pakrailways.gov.pk"

#: Clips that hesitate on their first step instead of pressing it: the pointer
#: drifts over the step until the overlay says it is showing less, the way
#: `tools/evaluation/adaptation_stack_run.py` does it through the host. The
#: fold is the backend's provisional rules answering the overlay's own
#: telemetry; nothing here sends a sample.
HESITATES = {"adapt"}


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


def railways_site(health_url: str = "http://127.0.0.1:8000/") -> str:
    """Where the running backend would run a train goal."""
    import urllib.request

    with urllib.request.urlopen(health_url, timeout=5) as answer:
        return json.loads(answer.read()).get("railways_site", "")


def refuse_the_live_site(site: str) -> None:
    """Stop before a railways clip that would search the live site."""
    if not site or LIVE_RAILWAYS in site:
        raise SystemExit(
            f"the backend would run the railways clip on {site or 'an unknown site'}. "
            "Start the stack with `.\\run.ps1 railways-local` (or `./run.sh "
            "railways-local`) so it runs on our own copy, then record again.")


#: Buttons in a step that are not answers to it.
NOT_ANSWERS = {"Read this aloud", "Stop reading", "Stop this"}


def answers_in(shell) -> list:
    """The screen's answers, in order: no "Read this aloud", no way to stop."""
    return [b for b in shell.locator("button:not([disabled])").all()
            if b.is_visible() and b.inner_text().strip() not in NOT_ANSWERS]


def press(page, button) -> str:
    """Press like a person: the overlay ignores a press on a button that has
    only just arrived (2026-10-16), so give it a moment first, and if the
    overlay's own log says the press was ignored, press again."""
    label = button.inner_text().strip()
    for _ in range(4):
        page.wait_for_timeout(700)
        button.click()
        last = page.evaluate("(window.__simbaPresses || []).slice(-1)[0] || null")
        if not last or not last.get("ignored"):
            break
    return label


def answer_screen(page, shell, typed: list[str], picks: list[str]) -> str | None:
    """Answer whatever the screen in `shell` asks. Returns what was done, or
    None when there is nothing to press yet.

    A box: type the next answer into it, choose it from the site's own names
    when one of `picks` is offered, then press the screen's own button for a
    typed answer ("Use this station", "Use this name"). Several answers
    offered: press the next one named in `picks`, if it is there. Anything
    else: the first answer, which is the screen's go-ahead.
    """
    from backend.orchestrator.voice import TYPED_ANSWERS

    if not answers_in(shell) and not shell.locator("input:not([disabled])").count():
        return None
    box = shell.locator("input[type=text]:not([disabled]), input:not([type]):not([disabled])")
    if box.count() and typed:
        value = typed.pop(0)
        box.first.click()
        box.first.type(value, delay=60)
        page.wait_for_timeout(900)
        if picks:
            wanted = shell.get_by_role("button", name=picks[0], exact=True)
            if wanted.count():
                picks.pop(0)
                press(page, wanted.first)
        finish = ([b for b in answers_in(shell) if b.inner_text().strip() in TYPED_ANSWERS]
                  or answers_in(shell)[:1])
        if finish:
            press(page, finish[0])
        return f"typed {value!r}"
    if picks:
        wanted = shell.get_by_role("button", name=picks[0], exact=True)
        if wanted.count():
            picks.pop(0)
            return f"chose {press(page, wanted.first)!r}"
    offered = answers_in(shell)
    if not offered:
        return None
    return press(page, offered[0])


def record(playwright, name: str, ws: str, goal: str, page_url: str) -> tuple[Path, list[str]]:
    """One clip: type the goal, answer whatever comes back, keep it.

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
    # The clips start on the home screen: the welcome a first open shows
    # (2026-10-18) and the logo before it (2026-11-02) are not what they are
    # about.
    context.add_init_script("window.__simbaWelcome = false; window.__simbaSplash = false")
    page = context.new_page()
    page.goto(f"{page_url}?ws={ws}")
    page.wait_for_timeout(BEAT_MS)

    # Typed rather than filled, so the recording shows it being written.
    box = page.get_by_role("textbox", name="What would you like me to do?")
    box.click()
    box.type(goal, delay=45)
    page.wait_for_timeout(700)
    page.keyboard.press("Enter")

    script = ANSWERS.get(name, {})
    typed, picks = list(script.get("type", [])), list(script.get("pick", []))
    seen: list[str] = []
    #: The screen last acted on, by its words: a new screen is new words.
    last = ""
    acted = time.time()
    deadline = time.time() + 300
    while time.time() < deadline:
        page.wait_for_timeout(600)
        text = page.evaluate("() => document.body.innerText")
        ending = next((e for e in ENDED if e in text), None)
        if ending:
            page.wait_for_timeout(1000)  # the closing screen, settled
            text = page.evaluate("() => document.body.innerText")
        if ending and name in SHOWS_PROOF and "See it on the real page" in text:
            page.wait_for_timeout(BEAT_MS * 2)  # the answer, read first
            press(page, page.get_by_role("button", name="See it on the real page"))
            page.wait_for_timeout(BEAT_MS * 2)
            press(page, page.get_by_role("button", name="Back to the answer"))
            seen.append("showed the real page")
        if ending:
            # Which ending, because "I'm stuck" is an ending too, and a clip
            # that ends on it is not a fallback for a run that worked.
            # The results themselves, not the lead-in above them: since
            # 2026-10-05 a sentence takes the lead-in's place.
            found = page.locator("[data-testid=findings]").count() > 0
            seen.append("found an answer" if found
                        else "done" if ending == "Back to start" else f"ended: {ending}")
            break
        # A reply: nothing starts, and that is the clip.
        if "Here's what I can help with" in text:
            seen.append("greeted")
            break
        if "I can't do that yet." in text:
            seen.append("declined")
            break
        # The final screen (2026-10-16): held long enough to be read, then
        # "do it" — the first of its two answers, which look alike.
        final = page.locator("[data-testid=final-check]")
        if final.count() and final.first.is_visible():
            answer = final.first.locator("[data-testid=final-answers] button").first
            if answer.is_enabled():  # once: answered, its buttons are disabled
                page.wait_for_timeout(BEAT_MS * 2)
                label = press(page, answer)
                seen.append(f"final screen: {label}")
                page.wait_for_timeout(BEAT_MS)
            continue
        shell = page.locator("[data-testid=step-shell]")
        if shell.count() and shell.first.is_visible():
            words = " ".join(shell.first.inner_text().split())
            ready = shell.first.locator("xpath=.//button[not(@disabled)]"
                                        "[not(ancestor::*[@data-testid='top-line'])]").count()
            # The same screen still up long after it was answered: the press
            # did not take (pressed too soon after the screen arrived, say).
            # A person presses again.
            if words == last and time.time() - acted > 10:
                last = ""
            if ready and words != last:
                last = words
                acted = time.time()
                page.wait_for_timeout(BEAT_MS)
                # On the second screen: the first never shows a notice.
                if name in HESITATES and len(seen) == 1:
                    folded = hesitate(page, SIMPLER)
                    seen.append(f"folded after {folded}s" if folded else "never folded")
                    page.wait_for_timeout(BEAT_MS * 2)  # let the fold be seen
                    last = " ".join(shell.first.inner_text().split())
                heading = shell.first.locator("h1").first.inner_text().strip()
                done = answer_screen(page, shell.first, typed, picks)
                if done:
                    seen.append(f"{heading[:40]} -> {done}")
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

    if any(c[0] == "railways" for c in clips):
        site = railways_site()
        refuse_the_live_site(site)
        print(f"railways clip runs on {site}", flush=True)

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
