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

**And the person's own details are what it runs on** (2026-09-30). Once a
goal is routed, what it says is read (`details.py`): where from, where to and
which day; a reference number; a course. Anything missing is asked for, one
question at a time, before the site is touched. Until that day every flow ran
on the values written into its plan, whatever had been typed.

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
- `SIMBA_ADAPT` is on by default: `backend/estimator/rules.py` chooses the
  detail level as the run goes and sends `load.updated`. `SIMBA_ADAPT=0` sends
  none, so the level stays where the overlay put it — the fixed-level
  condition, and a way out on demo day.
- `SIMBA_PAGE_MODEL` is on by default: the trained estimator
  (`backend/estimator/page_model.py`) judges the page, if `data/estimator.json`
  is there and readable. `SIMBA_PAGE_MODEL=0`, or no such file, leaves that to
  the provisional rules' three signs.
"""

import logging
import os
import sqlite3
from dataclasses import replace
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI, WebSocket

from backend.orchestrator.billing_plan import BILLING_PLAN, BILLING_TASK
from backend.orchestrator.browser import browser_source, open_page, window_watch
from backend.orchestrator.details import BRIEFS, brief_for, known_from_tile, understand
from backend.orchestrator.llm import provider_from_env
from backend.orchestrator.llm_loop import REGISTRATION_TASK, LLMPlanner
from backend.estimator import page_model
from backend.estimator.pairing import Recorder, recording_enabled
from backend.estimator.rules import Decision, LevelRules
from backend.orchestrator.loop import Connection, follow_override, run_brief, run_task
from backend.orchestrator.plan import REGISTRATION_PLAN, HardcodedPlanner
from backend.orchestrator.railways_plan import RAILWAYS_PLAN, RAILWAYS_TASK, RAILWAYS_URL
from backend.orchestrator.replay import TracePlanner
from backend.orchestrator.vault import Vault
from backend.orchestrator import voice
from backend.orchestrator.router import (
    ROUTABLE,
    Route,
    configured_classifier,
    route,
    use_model,
)
from backend.orchestrator.stubborn_plan import STUBBORN_PLAN, STUBBORN_TASK, STUBBORN_URL
from backend.orchestrator.tiles import TileStore
from backend.orchestrator.traces import TraceStore, site_of
from shared.schema import GoalAnswered, HistoryOffered, PastGoal, PersonalTile, TileChange

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

#: What each run did and how long each part took, beside the other run logs
#: and never committed (2026-10-17). Once, a checklist sat for over a minute
#: and nothing anywhere said where; until then the backend's own lines were
#: not shown at all, because nothing set up the `simba` loggers. No value a
#: person typed is ever logged. `SIMBA_LOG_FILE=` (empty) keeps it to the
#: terminal.
LOG_FILE = Path(__file__).resolve().parents[2] / "logs" / "backend.log"


def log_runs() -> None:
    """The `simba.*` loggers at INFO, to the terminal and to `LOG_FILE`."""
    simba = logging.getLogger("simba")
    if simba.handlers:
        return
    simba.setLevel(logging.INFO)
    form = logging.Formatter("%(asctime)s.%(msecs)03d %(name)s %(message)s", "%Y-%m-%d %H:%M:%S")
    terminal = logging.StreamHandler()
    terminal.setFormatter(form)
    simba.addHandler(terminal)
    path = os.environ.get("SIMBA_LOG_FILE", str(LOG_FILE)).strip()
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        written = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=3,
                                      encoding="utf-8")
        written.setFormatter(form)
        simba.addHandler(written)


log_runs()


def _flag(name: str) -> bool:
    return os.environ.get(name, "0").strip().lower() in {"1", "true", "yes"}


def use_hardcoded_plan() -> bool:
    return _flag("SIMBA_USE_HARDCODED_PLAN")


def use_trace_memory() -> bool:
    return _flag("SIMBA_TRACE_MEMORY")


def adapt_level() -> bool:
    """On unless `SIMBA_ADAPT` says otherwise."""
    return os.environ.get("SIMBA_ADAPT", "1").strip().lower() not in {"0", "false", "no"}


def level_source() -> str:
    """What is choosing the detail level, for the health check."""
    if not adapt_level():
        return "fixed"
    return "trained model" if page_model.active() is not None else "provisional rules"


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
        "level": level_source(),
        "browser": browser_source(),
        "replica": "per flow",
        # Where a train goal would run: the live site, or our own copy when
        # started with `railways-local`. Said here so a script can check before
        # it runs one (`tools/record_demo.py` refuses the live site).
        "railways_site": flow_setup("railways")[3],
    }


def past_goals(tiles: TileStore | None = None) -> HistoryOffered:
    """What this person has asked for before, most recent first — since the
    last "Forget me and start again", never before it (2026-10-21).

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
        goals = []
    # And the person's own tiles, by name only (2026-10-18): their details
    # stay in the encrypted store.
    own = [PersonalTile(id=tile.id, label=tile.label, flow=tile.flow)
           for tile in (tiles.all() if tiles is not None else [])]
    return HistoryOffered(goals=[PastGoal(goal=goal, site=site, label=voice.short_label(goal))
                                 for goal, site in goals],
                          tiles=own)


def change_tile(tiles: TileStore, message: dict) -> bool:
    """A `tile.change` from the home screen (2026-10-18). Whether it was one."""
    if message.get("type") != "tile.change":
        return False
    try:
        change = TileChange.model_validate(message.get("payload") or {})
    except ValueError:
        return True  # one, but not one that parses: answered as it stands
    if change.action == "clear":
        # "Forget me and start again" (2026-10-18), its only sender: the
        # person's tiles and saved sign-ins go, and the goals asked before now
        # are never offered again — kept for replay and the evaluation, never
        # shown to the next person (2026-10-21).
        tiles.clear()
        Vault().clear()
        try:
            TraceStore(os.environ.get("SIMBA_TRACE_DB", DEFAULT_DB)).forget_the_person()
        except sqlite3.Error:
            log.warning("tiles: the reset could not be written to the trace store")
    elif change.action == "remove" and change.id:
        tiles.remove(change.id)
    elif change.action == "rename" and change.id and change.label:
        tiles.rename(change.id, change.label)
    elif change.action == "move" and change.id and change.to is not None:
        tiles.move(change.id, change.to)
    log.info("tiles: %s", change.action)
    return True


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    connection = Connection(websocket, task_id="t_skeleton")
    tiles = TileStore()

    # Offered before anything is asked for, so the home screen has something
    # to show the moment it connects.
    await connection.send("history.offered", past_goals(tiles))

    # Channel B's other half: every step's page features, paired with whatever
    # telemetry the overlay sends about it, appended to `data/steps.jsonl`,
    # with every decision the level rules make beside them.
    # `SIMBA_RECORD_STEPS=0` turns it off (`backend/estimator/pairing.py`).
    recorder = Recorder(task_id="t_skeleton") if recording_enabled() else None

    # One set of rules per connection, made before anything is asked for: a
    # level the person locked on the home screen arrives ahead of the
    # `task.start`, and has to hold from the first step.
    rules = LevelRules(page_model=page_model.active()) if adapt_level() else None

    async def before_the_task(message: dict) -> None:
        # The person's tiles changed on the home screen: answered with the
        # home screen's offer as it now stands (2026-10-18).
        if change_tile(tiles, message):
            await connection.send("history.offered", past_goals(tiles))
            return
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
        # The checklist unless the person asked to be asked every time.
        auto = not bool(payload.get("confirm_each"))
        # The level the person chose as comfortable, kept by the overlay
        # (2026-10-18): the rules start there and come back to it.
        if rules is not None:
            rules.start_from(payload.get("start_level"))

        # One of the person's own tiles (2026-10-18): its flow and its kept
        # details, and its name as the goal. Nothing is read or classified.
        tile = tiles.get(payload.get("tile")) if payload.get("tile") else None
        if tile is not None:
            goal = tile.label
            decided = Route("flow", tile.flow, (tile.flow,), "tile")
        elif chosen in ROUTABLE:
            # Picked by the person from something we offered. Not classified
            # again: they have already answered the question.
            decided = Route("flow", chosen, (chosen,), "chosen")
        else:
            decided = await route(goal, model)
        # The flow only, never the words typed (2026-10-18): this line goes to
        # logs/backend.log, and a goal can hold a reference number.
        log.info("routed -> %s %s (%s)", decided.kind,
                 decided.flow or list(decided.flows), decided.via)

        if decided.kind == "flow" and decided.flow is not None:
            break
        await connection.send(
            "goal.answered",
            GoalAnswered(kind=decided.kind, goal=goal, flows=list(decided.flows)),
        )

    # The person's own starting level, written down beside what they then do
    # (2026-10-18): a signal for the estimator of its own.
    if recorder is not None:
        recorder.note_start_level(payload.get("start_level"))

    name, task, plan, replica_url = flow_setup(decided.flow)

    if name in BRIEFS:
        # The person's own details, read from what they typed. Whatever is
        # missing is asked for inside `run_brief`, and the task is built from
        # the answers — so nothing here knows yet what the task will be.
        known = (known_from_tile(tile.details) if tile is not None
                 else await understand(name, goal, model))
        # Which details were found, never their values (2026-10-18).
        log.info("understood: %s", ", ".join(
            field for field in ("origin", "destination", "day", "reference", "course")
            if getattr(known, field)) or "nothing")
        brief = brief_for(
            name, goal, known,
            hardcoded=use_hardcoded_plan(),
            provider=None if use_hardcoded_plan() else provider_from_env(),
        )
        # Run from a tile: it is not offered as a tile again.
        brief.from_tile = tile.id if tile is not None else None
        # Trace memory wraps whatever planner the brief settles on. It is
        # keyed on the details spelled out, not on the words typed: "trains
        # to Rawalpindi tomorrow" is a different journey every day.
        if use_trace_memory():
            store = TraceStore(os.environ.get("SIMBA_TRACE_DB", DEFAULT_DB))
            brief.wrap = lambda planner, spelled_out: TracePlanner(
                store, spelled_out, site_of(replica_url), planner)

        async with open_page(replica_url) as page:
            await run_brief(page, connection, brief, replica_url, recorder, rules,
                            vault=Vault(), window=window_watch(page), auto=auto,
                            tiles=tiles)
        # The overlay may have closed it already: going back to start from a
        # closing screen that offered more closes the connection (2026-10-16).
        try:
            await websocket.close()
        except RuntimeError:
            pass
        return

    # Only the recovery rig comes this way: a page built to fail, with a plan
    # and a task of its own, and nothing about it for a person to say.
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
        # The recovery rig: every move asked, as its measurements assume.
        await run_task(page, connection, planner, task, replica_url, recorder, rules,
                       vault=Vault(), window=window_watch(page))

    await websocket.close()
