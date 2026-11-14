"""The AI planner carrying a task out, with the real model, on pages served here (2026-11-14).

    python -m tools.evaluation.live_doing_replica_run [--runs 3]

The shop and top-up pages of `backend/orchestrator/test_live_doing.py`, served
from this machine, driven by the real loop and `OpenGoalPlanner` with the model
configured in `.env` (Gemini first, then the fallbacks). The person is played
by this script: it types a made-up name when SIMBA asks for one, answers
"Do it" on the final screen (these pages are ours; nothing real happens) and
"done" to the payment handover; the test page shows a receipt by itself a
moment after its card page appears, standing in for the person paying.

Recorded per run: the moves shown, whether a final screen came before the
order, the outcome and the answer, which provider worked each move out, and
whether the made-up name appears anywhere in what the model was sent (the
transcript).
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import http.server
import json
import socketserver
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from playwright.async_api import async_playwright  # noqa: E402

from backend.orchestrator import voice  # noqa: E402
from backend.orchestrator.llm import Transcript, provider_from_env  # noqa: E402
from backend.orchestrator.llm_loop import OpenGoalPlanner  # noqa: E402
from backend.orchestrator.loop import Connection, Task, _Run, carry_out  # noqa: E402
from backend.orchestrator.plan import About  # noqa: E402
from backend.orchestrator.test_live_doing import PAY, SHOP  # noqa: E402
from backend.orchestrator.test_sign_up import EMAIL, SIGN_UP  # noqa: E402
from backend.orchestrator.vault import Vault  # noqa: E402
from tools.evaluation.conditions import banner, record  # noqa: E402

NAME = "Test Personname"
OUT = REPO / ".scratch" / "live-doing-replica"


class Person(Connection):
    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []

    async def send(self, message_type: str, payload) -> None:
        self.sent.append((message_type, payload.model_dump()))

    async def receive(self, message_type, step_index=None, on_other=None) -> dict:
        if isinstance(message_type, tuple):  # the payment handover: the person
            await asyncio.sleep(1.0)          # pays, then presses "I've finished"
            return {"type": "handover.done", "payload": {"action": "done"}}
        step = next((p for k, p in reversed(self.sent) if k == "step.presented"), {})
        ids = [a["id"] for a in step.get("actions") or []]
        if voice.MAKE_PASSWORD_ID in ids:      # a new password: SIMBA makes it
            return {"type": "step.response",
                    "payload": {"step_index": step_index,
                                "action_id": voice.MAKE_PASSWORD_ID, "input_values": {}}}
        values = {field["id"]: (EMAIL if field["type"] == "email" else NAME)
                  for field in step.get("fields") or []}
        # The terms question is answered "I agree" (its id is CONFIRM_ID).
        return {"type": "step.response",
                "payload": {"step_index": step_index, "action_id": voice.CONFIRM_ID,
                            "input_values": values}}


async def one(url: str, goal: str) -> dict:
    transcript = Transcript(OUT / f"llm-{time.strftime('%H%M%S')}-{id(goal)}.jsonl")
    provider = provider_from_env(transcript)
    task = Task(goal=goal, estimated_steps=8, success=None, about=About())
    planner = OpenGoalPlanner(provider, task)
    person = Person()
    started = time.monotonic()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            vault = Vault(OUT / "vault.json")
            run = _Run(page, person, None, None, vault=vault if vault.available else None)
            await run.open(goal, task.estimated_steps, url)
            await carry_out(run, planner, task)
        finally:
            await browser.close()
    steps = [p for k, p in person.sent if k == "step.presented"]
    ended = next(((k, p) for k, p in reversed(person.sent)
                  if k in ("task.completed", "help.requested", "task.failed")), None)
    sent_to_model = transcript.path.read_text(encoding="utf-8") if transcript.path.exists() else ""
    return {
        "goal": goal,
        "outcome": ended[0] if ended else "no ending",
        "answer": ((ended[1].get("findings") or [{}])[0].get("value")
                   if ended and ended[0] == "task.completed" else None),
        "reason": ended[1].get("reason") if ended and ended[0] != "task.completed" else None,
        "moves": [p["instruction"] for p in steps],
        "final_screens": sum(1 for p in steps if p.get("final")),
        "handed_over": any(k == "handover" for k, _ in person.sent),
        "confirmation": (ended[1].get("confirmation")
                         if ended and ended[0] == "task.completed" else None),
        "worked_out_by": [p.get("worked_out_by") for p in steps if p.get("worked_out_by")],
        "model_calls": planner.calls_made,
        "name_sent_to_model": NAME.lower() in sent_to_model.lower(),
        "email_sent_to_model": EMAIL.lower() in sent_to_model.lower(),
        "terms_asked": sum(1 for p in steps if p["instruction"] == voice.AGREE_TERMS),
        "password_made": any(voice.MADE_PASSWORD in json.dumps(p) for k, p in person.sent)
        or any(voice.MAKE_PASSWORD_ID in [a["id"] for a in p.get("actions") or []]
               for p in steps),
        "email_explained": any(p["instruction"] == voice.CHECK_EMAIL for p in steps),
        "name_typed_on_page": any(NAME in json.dumps(p) for k, p in person.sent),
        "seconds": round(time.monotonic() - started, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=3)
    options = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(banner(), flush=True)
    folder = OUT / "site"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "index.html").write_text(SHOP, encoding="utf-8")
    (folder / "pay.html").write_text(PAY, encoding="utf-8")
    (folder / "join.html").write_text(SIGN_UP, encoding="utf-8")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(folder))
    server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    rows = []
    try:
        for _ in range(options.runs):
            rows.append(asyncio.run(one(f"{base}/index.html",
                                        "Order this book for me, cash on delivery")))
            print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
        for _ in range(max(1, options.runs - 1)):
            rows.append(asyncio.run(one(f"{base}/pay.html", "Top up my phone with Rs. 200")))
            print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
        for _ in range(options.runs):
            (OUT / "vault.json").unlink(missing_ok=True)   # a new account each time
            rows.append(asyncio.run(one(f"{base}/join.html",
                                        "Make me an account on this website")))
            print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    finally:
        server.shutdown()
    record(OUT / f"runs-{time.strftime('%Y%m%d-%H%M%S')}.json", {"rows": rows})


if __name__ == "__main__":
    main()
