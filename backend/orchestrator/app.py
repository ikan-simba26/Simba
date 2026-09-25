"""FastAPI entry point for the orchestrator.

Run from the repo root:

    python -m uvicorn backend.orchestrator.app:app --port 8000

The frontend connects to /ws, sends `task.start`, and answers each
`step.presented` with a `step.response`.

**The typed goal decides what happens** (2026-09-21). Every `task.start` is
routed first (`router.py`): a request for one of the flows runs that flow
with the goal as typed; small talk, a request SIMBA cannot do, or one that
could be two flows gets a `goal.answered` instead, and the socket stays open
for whatever the person picks next. Nothing runs that was not asked for —
until that day `SIMBA_FLOW` chose the task, and "hello" ran the bill.

The switches, all environment variables:

- `SIMBA_ROUTER` is `model` (default: one classification call to the
  configured provider, keywords if there is no key, no quota or no answer in
  time) or `keywords` (never call the model; what the tests use).
- `SIMBA_FLOW` no longer chooses anything a person gets. It keeps two narrow
  jobs: `stubborn` runs the registration request on the rigged page that
  measures recovery, and `SIMBA_FLOW` + `SIMBA_REPLICA_URL` together point
  that one flow at another URL, as the websocket tests do. Each flow's URL can
  also be set directly: `SIMBA_REGISTRATION_URL`, `SIMBA_BILLING_URL`,
  `SIMBA_RAILWAYS_URL`.
- `SIMBA_USE_HARDCODED_PLAN=1` runs that flow's hardcoded plan instead of the
  LLM — the A/B comparison, and the deterministic fallback for demo day.
- `SIMBA_TRACE_MEMORY=1` wraps whichever planner was chosen in `TracePlanner`,
  so a goal already done on this site replays from SQLite instead of being
  planned again.
- `SIMBA_BROWSER` is `chromium` (default, launches its own headless browser)
  or `electron` (attaches over CDP to a running host and drives its hidden
  site view). See `browser.py`.
- `SIMBA_ADAPT` is on by default: the provisional level rules
  (`backend/estimator/rules.py`) choose the detail level as the run goes and
  send `load.updated`. `SIMBA_ADAPT=0` sends none, so the level stays where
  the overlay put it — the fixed-level condition, and a way out on demo day.
"""

import logging
import os
import sqlite3
from dataclasses import replace
from pathlib import Path

from fastapi import FastAPI, WebSocket

from backend.orchestrator.billing_plan import BILLING_PLAN, BILLING_TASK
from backend.orchestrator.browser import browser_source, open_page
from backend.orchestrator.llm import provider_from_env
from backend.orchestrator.llm_loop import REGISTRATION_TASK, LLMPlanner
from backend.estimator.pairing import Recorder, recording_enabled
from backend.estimator.rules import Decision, LevelRules
from backend.orchestrator.loop import Connection, follow_override, run_task
from backend.orchestrator.plan import REGISTRATION_PLAN, HardcodedPlanner
from backend.orchestrator.railways_plan import RAILWAYS_PLAN, RAILWAYS_TASK, RAILWAYS_URL
from backend.orchestrator.replay import TracePlanner
from backend.orchestrator.router import (
    ROUTABLE,
    Route,
    configured_classifier,
    route,
    use_model,
)
from backend.orchestrator.stubborn_plan import STUBBORN_PLAN, STUBBORN_TASK, STUBBORN_URL
from backend.orchestrator.traces import TraceStore, site_of
from shared.schema import GoalAnswered, HistoryOffered, PastGoal

DEFAULT_DB = str(Path(__file__).resolve().parents[2] / "traces.db")
# How many past goals the home screen offers. Three large cards is a choice;
# a list of them is the cluttered interface this project exists to remove.
HOME_GOALS = 3

FLOWS = {
    "registration": (REGISTRATION_TASK, REGISTRATION_PLAN, "http://127.0.0.1:5000"),
    "billing": (BILLING_TASK, BILLING_PLAN, "http://127.0.0.1:5100"),
    # The only flow that is not a replica we wrote. Read-only.
    "railways": (RAILWAYS_TASK, RAILWAYS_PLAN, RAILWAYS_URL),
    # A replica page whose first control does nothing, so the loop's recovery
    # and a planner's use of a setback can be measured. See stubborn_plan.py.
    "stubborn": (STUBBORN_TASK, STUBBORN_PLAN, STUBBORN_URL),
}

app = FastAPI()


def _flag(name: str) -> bool:
    return os.environ.get(name, "0").strip().lower() in {"1", "true", "yes"}


def use_hardcoded_plan() -> bool:
    return _flag("SIMBA_USE_HARDCODED_PLAN")


def use_trace_memory() -> bool:
    return _flag("SIMBA_TRACE_MEMORY")


def adapt_level() -> bool:
    """On unless `SIMBA_ADAPT` says otherwise."""
    return os.environ.get("SIMBA_ADAPT", "1").strip().lower() not in {"0", "false", "no"}


log = logging.getLogger("simba.app")


def pinned_flow() -> str | None:
    """`SIMBA_FLOW`, if set. It no longer chooses the task; see the docstring."""
    name = os.environ.get("SIMBA_FLOW", "").strip().lower()
    if name and name not in FLOWS:
        raise RuntimeError(f"unknown SIMBA_FLOW {name!r}; expected one of {sorted(FLOWS)}")
    return name or None


def flow_setup(name: str) -> tuple:
    """The task, plan and URL a routed flow runs with.

    `stubborn` stands in for `registration` when pinned, so the recovery rig
    is still reachable through the real endpoint by asking for a course.
    """
    pinned = pinned_flow()
    actual = "stubborn" if (name == "registration" and pinned == "stubborn") else name
    task, plan, url = FLOWS[actual]
    url = os.environ.get(f"SIMBA_{name.upper()}_URL", url)
    # `SIMBA_REPLICA_URL` meant "the selected flow's URL", and with nothing
    # selected the selected flow was registration. Both meanings are kept, so
    # nothing that already sets it moves to a different site.
    legacy = os.environ.get("SIMBA_REPLICA_URL")
    if legacy and (pinned == actual or (pinned is None and name == "registration")):
        url = legacy
    return actual, task, plan, url


@app.get("/")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "flow": pinned_flow() or "routed by goal",
        "router": "model" if use_model() else "keywords",
        "planner": "hardcoded" if use_hardcoded_plan() else "llm",
        "trace_memory": "on" if use_trace_memory() else "off",
        "level": "provisional rules" if adapt_level() else "fixed",
        "browser": browser_source(),
        "replica": "per flow",
    }


def past_goals() -> HistoryOffered:
    """What this person has asked for before, most recent first.

    Read from the same SQLite store trace replay uses, so the home screen
    offers exactly the goals that would replay rather than a separate list
    that could disagree with it. Capped: the home screen shows a few large
    cards, and a long list of them is the cluttered interface this project
    exists to remove.
    """
    try:
        store = TraceStore(os.environ.get("SIMBA_TRACE_DB", DEFAULT_DB))
        goals = store.recent(limit=HOME_GOALS)
    except sqlite3.Error:
        # A missing or unreadable store is an empty home screen, not a dead
        # socket. The text box is always there underneath.
        return HistoryOffered(goals=[])
    return HistoryOffered(goals=[PastGoal(goal=goal, site=site) for goal, site in goals])


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    connection = Connection(websocket, task_id="t_skeleton")

    # Offered before anything is asked for, so the home screen has something
    # to show the moment it connects.
    await connection.send("history.offered", past_goals())

    # Channel B's other half: every step's page features, paired with whatever
    # telemetry the overlay sends about it, appended to `data/steps.jsonl`,
    # with every decision the level rules make beside them.
    # `SIMBA_RECORD_STEPS=0` turns it off (`backend/estimator/pairing.py`).
    recorder = Recorder(task_id="t_skeleton") if recording_enabled() else None

    # One set of rules per connection, made before anything is asked for: a
    # level the person locked on the home screen arrives ahead of the
    # `task.start`, and has to hold from the first step.
    rules = LevelRules() if adapt_level() else None

    async def before_the_task(message: dict) -> None:
        # Nothing is sent back: an override is the person's own doing, and
        # there is no step on screen yet for a level to reshape.
        async def write_down(decision: Decision | None) -> None:
            if recorder is not None and decision is not None:
                recorder.note_decision(decision)
        await follow_override(message, rules, write_down)

    # Routed first, every time. Anything that is not a request for a flow is
    # answered and the socket is kept, so the person's next choice — a card, a
    # clarifying button, a new sentence — arrives on the same connection.
    model = configured_classifier()
    while True:
        start = await connection.receive("task.start", on_other=before_the_task)
        payload = start.get("payload", {})
        goal = (payload.get("goal") or "").strip()
        chosen = payload.get("flow")

        if chosen in ROUTABLE:
            # Picked by the person from something we offered. Not classified
            # again: they have already answered the question.
            decided = Route("flow", chosen, (chosen,), "chosen")
        else:
            decided = await route(goal, model)
        log.info("routed %r -> %s %s (%s)", goal, decided.kind,
                 decided.flow or list(decided.flows), decided.via)

        if decided.kind == "flow" and decided.flow is not None:
            break
        await connection.send(
            "goal.answered",
            GoalAnswered(kind=decided.kind, goal=goal, flows=list(decided.flows)),
        )

    _, task, plan, replica_url = flow_setup(decided.flow)
    # What the person typed is what the task is. A card's goal is its own
    # sentence; an empty goal cannot reach here, because it routes to a
    # greeting.
    if goal:
        task = replace(task, goal=goal)

    # The only thing the flag changes is which planner picks the next move —
    # and how many steps it can promise up front, which the hardcoded plan
    # knows exactly and the LLM can only estimate.
    if use_hardcoded_plan():
        task = replace(task, estimated_steps=len(plan))
        planner = HardcodedPlanner(plan)
    else:
        planner = LLMPlanner(provider_from_env(), task)

    # Trace memory wraps whatever was chosen: replay the remembered run if
    # there is one, and hand back to that planner the moment it stops fitting.
    if use_trace_memory():
        store = TraceStore(os.environ.get("SIMBA_TRACE_DB", DEFAULT_DB))
        planner = TracePlanner(store, task, site_of(replica_url), planner)

    async with open_page(replica_url) as page:
        await run_task(page, connection, planner, task, replica_url, recorder, rules)

    await websocket.close()
