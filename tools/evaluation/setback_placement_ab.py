"""Does it matter where a setback sits in the prompt? Two runs, one each way.

The loop hands a failed step back to the planner as a setback. On 2026-09-09 a
live run was told, in plain words at the *end* of its prompt, that its date was
the wrong month — and clicked search anyway; re-asked with the same words moved
above the element list, the same model addressed the date. One decision, not a
run (EVALUATION.md, "Where information sits is a perception decision").

Twice since then a run was supposed to settle it and could not: nothing failed,
so no setback was ever sent. A live site will not fail on demand.

So this runs the `stubborn` flow, whose "Continue" button is a `<button>` with
no handler, on a page with two dozen dead links to give the element list some
length.

**The first move is forced, and the model makes every one after it.** Left to
itself the model simply takes the working route first — measured twice — and a
run where nothing fails cannot say anything about recovery. Forcing the dead
click is the point: it puts every arm in the state the question is about, with
a setback in hand and the page unchanged, and leaves the decision under test
to the model.

What it reports per arm: what the model chose after being told the first move
did nothing, whether that was the route that works, and whether the run
completed. Two runs per arm, because one answer from a model is an anecdote.

    python -m tools.evaluation.setback_placement_ab

**Spends model quota**: 2-4 requests per arm, 4-8 in total. No live site — the
page is the local registration replica's `/stubborn`. Writes
`logs/setback_ab.json`.
"""

import asyncio
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright

from backend.orchestrator.llm import SETBACK_ABOVE, SETBACK_AFTER, Transcript, provider_from_env
from backend.orchestrator.llm_loop import LLMPlanner
from backend.orchestrator.loop import Connection, Move, run_task
from backend.orchestrator.plan import Expectation, Operation, Target
from backend.orchestrator.stubborn_plan import STUBBORN_TASK
from backend.orchestrator.voice import GO_AHEAD, actions
from tools.evaluation.conditions import banner, record

REPO_ROOT = Path(__file__).resolve().parents[2]
PORT = 5032
STUBBORN = f"http://127.0.0.1:{PORT}/stubborn"
# The one that works, in the words the planner's instruction uses.
THE_WAY_OUT = "Take the long way round"
RUNS_PER_ARM = 2

# The move every arm starts with: the dead button, pressed on purpose.
DEAD_CLICK = Move(
    instruction="Click Continue.",
    detail="Forced, so that this run has a failure to recover from.",
    operations=[Operation("click", Target("button", "Continue"))],
    expect=Expectation(),
    fields=[],
    actions=actions(GO_AHEAD),
)


class ForcedFirstMove:
    """The dead click first, then the model for everything after it.

    Wrapping rather than prompting: the model is never asked to choose the
    failure, so nothing about its judgement is being tested here except what
    it does once it has been told.
    """

    def __init__(self, planner: LLMPlanner) -> None:
        self.planner = planner
        self.moves = 0
        self.setbacks: list[str] = []

    @property
    def calls_made(self) -> int:
        return self.planner.calls_made

    @property
    def stuck_reason(self) -> str | None:
        return self.planner.stuck_reason

    async def next_move(self, elements, history, setback):
        if setback is not None:
            self.setbacks.append(setback)
        self.moves += 1
        if self.moves == 1:
            return DEAD_CLICK
        return await self.planner.next_move(elements, history, setback)


class Recording(Connection):
    """Answers every step with go-ahead, and keeps what it was shown."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []

    async def send(self, message_type: str, payload) -> None:
        self.sent.append((message_type, payload.model_dump()))

    async def receive(self, message_type, step_index=None, on_other=None):
        return {"type": "step.response",
                "payload": {"step_index": step_index, "action_id": "confirm",
                            "input_values": {}}}

    def of(self, message_type: str) -> list[dict]:
        return [payload for name, payload in self.sent if name == message_type]


def wait_for(url: str, timeout_s: float = 30.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.2)
    raise RuntimeError(f"nothing at {url}")


async def one_arm(placement: str, run: int) -> dict:
    os.environ["SIMBA_SETBACK_PLACEMENT"] = placement
    transcript = Transcript(REPO_ROOT / "logs" / f"setback-{placement}-{run}.jsonl")
    provider = provider_from_env(transcript=transcript)
    planner = ForcedFirstMove(LLMPlanner(provider, STUBBORN_TASK))
    connection = Recording()

    started = time.monotonic()
    crash = None
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            await run_task(page, connection, planner, STUBBORN_TASK, STUBBORN)
        except Exception as error:  # noqa: BLE001 — a crash is a result too
            crash = f"{type(error).__name__}: {error}"
        final_url = page.url
        await browser.close()
    elapsed = time.monotonic() - started

    steps = [payload["instruction"] for payload in connection.of("step.presented")]
    failed = connection.of("step.failed")
    helped = connection.of("help.requested")
    # The move made *after* being told the first one did nothing.
    after_setback = steps[len(steps) - 1] if len(steps) > 1 else None
    reason = (helped[0]["reason"] if helped else None) or crash or ""
    return {
        "placement": placement,
        "run": run,
        "setbacks_delivered": len(planner.setbacks),
        "completed": bool(connection.of("task.completed")),
        "steps": steps,
        "step_count": len(steps),
        "llm_calls": planner.calls_made,
        "failed_steps": [f["instruction"] for f in failed],
        "after_the_setback": after_setback,
        # The question, as a boolean: did it change course to the route that
        # works, rather than pressing the dead button again?
        "recovered": bool(after_setback and THE_WAY_OUT in after_setback),
        "final_url": final_url,
        "seconds": round(elapsed - getattr(provider, "throttled_seconds", 0.0), 1),
        "throttled_seconds": round(getattr(provider, "throttled_seconds", 0.0), 1),
        "help_reason": helped[0]["reason"] if helped else None,
        "crash": crash,
        "quota_blocked": "429" in reason or "quota" in reason.lower(),
        "transcript": str(transcript.path),
    }


async def main() -> None:
    print(banner(), flush=True)
    replica = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=REPO_ROOT / "replicas" / "registration",
        env={**os.environ, "PORT": str(PORT)},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    results = []
    try:
        wait_for(STUBBORN)
        # Above first: if quota ends the session, the arm that matters is done.
        for placement in (SETBACK_ABOVE, SETBACK_AFTER):
            for run in range(1, RUNS_PER_ARM + 1):
                print(f"\n=== setback {placement} the element list, run {run} ===", flush=True)
                arm = await one_arm(placement, run)
                results.append(arm)
                print(f"  completed={arm['completed']} steps={arm['step_count']} "
                      f"calls={arm['llm_calls']} setbacks={arm['setbacks_delivered']} "
                      f"recovered={arm['recovered']} {arm['seconds']}s", flush=True)
                for i, step in enumerate(arm["steps"], start=1):
                    mark = " <- failed" if step in arm["failed_steps"] else ""
                    print(f"    {i}. {step}{mark}", flush=True)
                if arm["help_reason"]:
                    print(f"    help.requested: {arm['help_reason'][:150]}", flush=True)
                if arm["quota_blocked"]:
                    print("  ! quota exhausted; the rest was not run", flush=True)
                    break
            else:
                continue
            break
    finally:
        replica.terminate()
        replica.wait(timeout=10)

    record(REPO_ROOT / "logs" / "setback_ab.json", results, runs=len(results))
    print("\nwrote logs/setback_ab.json", flush=True)
    for placement in (SETBACK_ABOVE, SETBACK_AFTER):
        arms = [a for a in results if a["placement"] == placement]
        if not arms:
            continue
        recovered = sum(a["recovered"] for a in arms)
        completed = sum(a["completed"] for a in arms)
        print(f"  {placement:>5}: recovered {recovered}/{len(arms)}, "
              f"completed {completed}/{len(arms)}, "
              f"after the setback: {[a['after_the_setback'] for a in arms]}")


asyncio.run(main())
