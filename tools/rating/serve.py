"""The rating session: one screenshot at a time, one question, five labelled answers.

    python -m tools.rating.serve                 # then open http://127.0.0.1:8765

Asks for the rater's number, shows the two worked examples (`examples.py`),
then the 30 pictures of the rater's set — the same two sets, anchors and
question as the online forms (`export_form.py`, DECISIONS.md, *Two sets of
30*): the set's 25 pages and the other set's three anchors in a random order,
plus two of its own pages again later (`session.py`). Odd rater numbers rate
Set 1 and even numbers Set 2 (`session.set_of`). Each picture comes with the
question "How overwhelming does this page feel?" and five buttons, Not at
all / A little / Somewhat / Very / Extremely — or the keys 1 to 5. Every
answer is appended to `data/ratings.jsonl` as it is given, so a session
abandoned halfway keeps what it had.

The sets are read from `data/rating/form.json`, the mapping the online forms
were made from, so a rater in person and a rater online of the same set see
the same pages.

**One row per answer:**

    {"ts": ..., "rater": 3, "set": 1, "session": "a1b2c3d4e5f6", "seed": 12345,
     "position": 7, "of": 30, "page": "www-bbc-co-uk-news", "url": "...",
     "state": "as it loads", "kind": "public", "image_sha256": "...",
     "repeat": false, "anchor": false, "rating": 4, "ms": 4210, "question": "...",
     "shown": [556, 348], "window": [1266, 606]}

`anchor` is true for the six pages both sets show.

`ms` is the time from the picture being on screen to the answer, measured in
the browser. `shown` is how large the picture was drawn and `window` the
browser's size, both in CSS pixels: the picture is fitted to the window, so a
rater on a small laptop sees it smaller than one on a monitor, and a rating
may depend on that. `position` and `page` are the server's, not the browser's: the
browser says which position it is answering and the server looks up what was
shown there, so a row cannot name a page the rater never saw. `image_sha256`
is the exact picture that was rated (`capture.py`).

The rater's number is the only thing recorded about them. The file is not
committed (`.gitignore`): whether ratings leave the machine is a decision for
whoever collects them, with the raters' consent.

Standard library only. Binds 127.0.0.1 unless told otherwise.
"""

from __future__ import annotations

import argparse
import json
import secrets
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from tools.rating.session import plan, set_of

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
MANIFEST = REPO / "data" / "rating" / "pages.json"
DESIGN = REPO / "data" / "rating" / "form.json"
RATINGS = REPO / "data" / "ratings.jsonl"
QUESTION = "How overwhelming does this page feel?"
#: Every point of the scale has its words, in order from 1.
LABELS = ("Not at all", "A little", "Somewhat", "Very", "Extremely")
SCALE = (1, 5)
#: In-person raters are numbered below the online ones (`from_form.FORMS`).
MAX_RATER = 4999


class Study:
    """The pages, the two sets, the sessions in progress, and the file answers go to."""

    def __init__(self, manifest: Path = MANIFEST, ratings: Path = RATINGS,
                 design: Path = DESIGN) -> None:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        self.images = manifest.parent / "pages"
        self.examples_folder = manifest.parent / "examples"
        self.pages = {row["id"]: row for row in data["pages"]
                      if "error" not in row and (self.images / row["file"]).exists()}
        self.ratings = ratings
        self.sessions: dict[str, dict] = {}
        self.lock = threading.Lock()
        made = json.loads(design.read_text(encoding="utf-8")) if design.exists() else None
        if made is None or "sets" not in made:
            raise ValueError(f"no sets in {design}; run python -m tools.rating.export_form")
        page_of = {name: p["page"] for name, p in made["pictures"].items()}
        #: Set -> (the pages it shows, the pages it may repeat).
        self.sets: dict[int, tuple[list[str], set[str]]] = {}
        for key, chosen in made["sets"].items():
            shown = sorted(page_of[n] for n in chosen["own"] + chosen["anchors"])
            missing = [p for p in shown if p not in self.pages]
            if missing:
                raise ValueError(f"set {key} names pages with no picture here: {missing[:3]}; "
                                 f"recapture or re-export")
            self.sets[int(key)] = (shown, {page_of[n] for n in chosen["own"]}
                                   - {page_of[n] for n in chosen["lends"]})
        self.anchors = {page_of[n] for chosen in made["sets"].values()
                        for n in chosen["anchors"]}
        self.examples = [{"image": f"/examples/{e['file']}", "says": e["says"],
                          "answer": e["answer"], "label": e["label"]}
                         for e in made.get("examples", [])
                         if (self.examples_folder / e["file"]).exists()]

    def start(self, rater: object) -> dict:
        if not isinstance(rater, int) or isinstance(rater, bool) \
                or not 1 <= rater <= MAX_RATER:
            raise ValueError(f"rater must be a whole number from 1 to {MAX_RATER}")
        if not self.pages:
            raise ValueError("no captured pages; run python -m tools.rating.capture")
        chosen = set_of(rater)
        shown, repeatable = self.sets[chosen]
        seed = secrets.randbits(32)
        session = secrets.token_hex(6)
        items = plan(shown, seed, repeatable=repeatable)
        with self.lock:
            self.sessions[session] = {"rater": rater, "set": chosen, "seed": seed,
                                      "items": items, "answered": set()}
        return {
            "session": session, "set": chosen, "question": QUESTION, "scale": SCALE,
            "labels": LABELS, "examples": self.examples,
            "items": [{"position": i + 1, "image": f"/pages/{self.pages[it['page']]['file']}"}
                      for i, it in enumerate(items)],
        }

    def answer(self, session: object, position: object, rating: object, ms: object,
               shown: object = None, window: object = None) -> dict:
        with self.lock:
            state = self.sessions.get(session) if isinstance(session, str) else None
            if state is None:
                raise ValueError("unknown session")
            items = state["items"]
            if not isinstance(position, int) or not 1 <= position <= len(items):
                raise ValueError("no such position in this session")
            if position in state["answered"]:
                raise ValueError("that position has already been answered")
            if not isinstance(rating, int) or isinstance(rating, bool) \
                    or not SCALE[0] <= rating <= SCALE[1]:
                raise ValueError(f"rating must be a whole number from {SCALE[0]} to {SCALE[1]}")
            if not isinstance(ms, int) or ms < 0:
                raise ValueError("ms must be a whole number of milliseconds")
            item = items[position - 1]
            page = self.pages[item["page"]]
            row = {
                "ts": int(time.time() * 1000),
                "rater": state["rater"], "set": state["set"], "session": session,
                "seed": state["seed"],
                "position": position, "of": len(items),
                "page": page["id"], "url": page["url"], "state": page["state"],
                "kind": page["kind"], "image_sha256": page["sha256"],
                "repeat": item["repeat"], "anchor": item["page"] in self.anchors,
                "rating": rating, "ms": ms,
                "question": QUESTION,
                "shown": _pair(shown), "window": _pair(window),
            }
            self.ratings.parent.mkdir(parents=True, exist_ok=True)
            with self.ratings.open("a", encoding="utf-8") as lines:
                lines.write(json.dumps(row, ensure_ascii=False) + "\n")
            state["answered"].add(position)
            return {"ok": True, "left": len(items) - len(state["answered"])}


def _pair(value: object) -> list[int] | None:
    """A width and height from the browser, or None if it sent something else."""
    if (isinstance(value, list) and len(value) == 2
            and all(isinstance(n, int) and not isinstance(n, bool) and 0 <= n <= 20000
                    for n in value)):
        return value
    return None


def handler_for(study: Study) -> type[BaseHTTPRequestHandler]:
    index = (HERE / "index.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:  # the answers are the log
            pass

        def _send(self, status: int, body: bytes, kind: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, payload: dict) -> None:
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json")

        def do_GET(self) -> None:
            if self.path in ("/", "/index.html"):
                self._send(HTTPStatus.OK, index, "text/html; charset=utf-8")
                return
            for prefix, folder in (("/pages/", study.images),
                                   ("/examples/", study.examples_folder)):
                if self.path.startswith(prefix):
                    name = Path(self.path.split("?")[0]).name
                    file = folder / name
                    if file.suffix == ".png" and file.exists():
                        self._send(HTTPStatus.OK, file.read_bytes(), "image/png")
                        return
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
                if self.path == "/api/session":
                    self._json(HTTPStatus.OK, study.start(body.get("rater")))
                elif self.path == "/api/rating":
                    self._json(HTTPStatus.OK, study.answer(
                        body.get("session"), body.get("position"),
                        body.get("rating"), body.get("ms"),
                        body.get("shown"), body.get("window")))
                else:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            except (ValueError, json.JSONDecodeError) as refused:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(refused)})

    return Handler


def serve(study: Study, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), handler_for(study))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    study = Study()
    server = serve(study, args.host, args.port)
    print(f"{len(study.pages)} pages in two sets of {len(study.sets[1][0])} and "
          f"{len(study.sets[2][0])}; odd rater numbers Set 1, even Set 2; "
          f"answers go to {RATINGS}")
    print(f"open http://{args.host}:{args.port}/  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
