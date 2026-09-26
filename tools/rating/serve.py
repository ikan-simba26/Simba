"""The rating session: one screenshot at a time, one question, a 1–7 answer.

    python -m tools.rating.serve                 # then open http://127.0.0.1:8765

Asks for the rater's number, then shows every captured page once in a random
order, plus two pages again later (`session.py`), each with the question
"How overwhelming would this page be to use?" and seven buttons — or the keys
1 to 7. Every answer is appended to `data/ratings.jsonl` as it is given, so a
session abandoned halfway keeps what it had.

**One row per answer:**

    {"ts": ..., "rater": 3, "session": "a1b2c3d4e5f6", "seed": 12345,
     "position": 7, "of": 52, "page": "www-bbc-co-uk-news", "url": "...",
     "state": "as it loads", "kind": "public", "image_sha256": "...",
     "repeat": false, "rating": 5, "ms": 4210, "question": "...",
     "shown": [556, 348], "window": [1266, 606]}

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

from tools.rating.session import plan

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
MANIFEST = REPO / "data" / "rating" / "pages.json"
RATINGS = REPO / "data" / "ratings.jsonl"
QUESTION = "How overwhelming would this page be to use?"
SCALE = (1, 7)


class Study:
    """The pages, the sessions in progress, and the file answers go to."""

    def __init__(self, manifest: Path = MANIFEST, ratings: Path = RATINGS) -> None:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        self.images = manifest.parent / "pages"
        self.pages = {row["id"]: row for row in data["pages"]
                      if "error" not in row and (self.images / row["file"]).exists()}
        self.ratings = ratings
        self.sessions: dict[str, dict] = {}
        self.lock = threading.Lock()

    def start(self, rater: object) -> dict:
        if not isinstance(rater, int) or isinstance(rater, bool) or not 1 <= rater <= 9999:
            raise ValueError("rater must be a whole number from 1 to 9999")
        if not self.pages:
            raise ValueError("no captured pages; run python -m tools.rating.capture")
        seed = secrets.randbits(32)
        session = secrets.token_hex(6)
        items = plan(sorted(self.pages), seed)
        with self.lock:
            self.sessions[session] = {"rater": rater, "seed": seed, "items": items,
                                      "answered": set()}
        return {
            "session": session, "question": QUESTION, "scale": SCALE,
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
                raise ValueError("rating must be a whole number from 1 to 7")
            if not isinstance(ms, int) or ms < 0:
                raise ValueError("ms must be a whole number of milliseconds")
            item = items[position - 1]
            page = self.pages[item["page"]]
            row = {
                "ts": int(time.time() * 1000),
                "rater": state["rater"], "session": session, "seed": state["seed"],
                "position": position, "of": len(items),
                "page": page["id"], "url": page["url"], "state": page["state"],
                "kind": page["kind"], "image_sha256": page["sha256"],
                "repeat": item["repeat"], "rating": rating, "ms": ms,
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
            if self.path.startswith("/pages/"):
                name = Path(self.path.split("?")[0]).name
                file = study.images / name
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
    print(f"{len(study.pages)} pages; answers go to {RATINGS}")
    print(f"open http://{args.host}:{args.port}/  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
