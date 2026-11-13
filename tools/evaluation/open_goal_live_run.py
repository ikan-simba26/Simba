"""One goal with no plan, done by the AI planner on a live website (2026-11-13).

The advisor's direction, phase 2: "AI first, then teach". This runs the real
loop and the real `OpenGoalPlanner` against a real website, in a headless
browser at the frozen 1280x800, with the configured provider (Gemini, Groq as
its fallback). **One run per call, read-only**: every move is the loop's to
allow, and on a live site a press whose words would book, pay or submit ends
the run (`loop.would_change`). robots.txt is asked first.

Every step is answered "go ahead", and the first answer the page says word
for word is answered "Yes, that's it": the person's check is played by this
script, so whether the answer is *right* is judged afterwards, by a person
reading the result against the page. Never against a live site in a loop, and
never more than a handful (CLAUDE.md).

    python -m tools.evaluation.open_goal_live_run https://www.gov.uk/bank-holidays \\
        "When is the next bank holiday in England and Wales?"

Prints the conditions, then what happened; writes the same, with the
transcript's path, to `.scratch/open-goal-live/`. Prints no page content but
the answer.
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from playwright.async_api import async_playwright  # noqa: E402

from backend.orchestrator import robots, voice  # noqa: E402
from backend.orchestrator.llm import Transcript, provider_from_env  # noqa: E402
from backend.orchestrator.llm_loop import OpenGoalPlanner  # noqa: E402
from backend.orchestrator.loop import Connection, Task, _Run, carry_out  # noqa: E402
from backend.orchestrator.plan import About  # noqa: E402
from tools.evaluation.conditions import banner, record  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / ".scratch" / "open-goal-live"


class Recording(Connection):
    """Says yes to every step, and keeps what it said — **but never "Do it"**.

    Since 2026-11-13 a live site may be changed after the final screen
    (CLAUDE.md, the final-step rule), so "yes to everything" would press "Do it"
    on a real booking, order or form. This script plays the person only up to
    there: a final screen is always answered "Don't do it", and a handover (a
    payment, a bot check, a one-time code) is always cancelled. A real change
    is the person's own press, never a script's.
    """

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []
        #: Final screens declined and handovers cancelled, for the record.
        self.declined: list[str] = []

    async def send(self, message_type: str, payload) -> None:
        self.sent.append((message_type, payload.model_dump()))

    def _last_step(self) -> dict:
        return next((p for kind, p in reversed(self.sent) if kind == "step.presented"), {})

    async def receive(self, message_type, step_index=None, on_other=None) -> dict:
        wanted = message_type if isinstance(message_type, tuple) else (message_type,)
        if "step.response" not in wanted:
            # A handover waits for the person's "done" or a cancel: cancel.
            self.declined.append(f"handover: {wanted}")
            return {"type": "task.cancel", "payload": {}}
        step = self._last_step()
        ids = {action.get("id") for action in step.get("actions") or []}
        # A final screen is the step with its details listed (`final`). Not
        # "any step that offers decline": "Is this what you wanted?" offers
        # "No, keep looking" under that same id, and answering it so turned
        # down the right trains nine times in a row (EVALUATION.md, 2026-11-13j).
        if step.get("final"):
            self.declined.append(f"final screen: {step.get('instruction', '')[:120]}")
            answer = voice.DECLINE_ID if voice.DECLINE_ID in ids else voice.CANCEL_ID
        else:
            answer = voice.CONFIRM_ID
        return {"type": "step.response",
                "payload": {"step_index": step_index, "action_id": answer,
                            "input_values": {}}}


async def one_run(site: str, goal: str, steps: int = 6) -> dict:
    if not await robots.allowed(site):
        return {"outcome": "not allowed by robots.txt"}
    transcript = Transcript()
    provider = provider_from_env(transcript)
    task = Task(goal=goal, estimated_steps=steps, success=None, about=About())
    planner = OpenGoalPlanner(provider, task)
    connection = Recording()
    started = time.monotonic()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            run = _Run(page, connection, None, None)
            run.teach_site = site
            await run.open(goal, task.estimated_steps, site)
            await carry_out(run, planner, task)
        finally:
            await browser.close()
    seconds = time.monotonic() - started
    types = [kind for kind, _ in connection.sent]
    steps = [p for kind, p in connection.sent if kind == "step.presented"]
    ended = next(((kind, p) for kind, p in reversed(connection.sent)
                  if kind in ("task.completed", "help.requested", "task.failed")), None)
    result = {
        "site": site, "goal": goal,
        "outcome": ended[0] if ended else "no ending",
        "answer": (ended[1].get("findings") or [{}])[0].get("value")
        if ended and ended[0] == "task.completed" else None,
        "reason": ended[1].get("reason") if ended and ended[0] != "task.completed" else None,
        "steps_shown": len(steps),
        "moves": [p["instruction"] for p in steps],
        "worked_out_by": sorted({p.get("worked_out_by") for p in steps if p.get("worked_out_by")}),
        "model_calls": planner.calls_made,
        "fell_back": getattr(provider, "fell_back", 0),
        "seconds": round(seconds, 1),
        "transcript": str(getattr(transcript, "path", "")),
        "messages": types.count("step.presented"),
        "declined": connection.declined,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("site")
    parser.add_argument("goal")
    parser.add_argument("--steps", type=int, default=6)
    args = parser.parse_args()
    # Here, not at import: a test imports `Recording` (2026-11-13).
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(banner())
    result = asyncio.run(one_run(args.site, args.goal, args.steps))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    record(OUT / f"run-{stamp}.json", result)


if __name__ == "__main__":
    main()
