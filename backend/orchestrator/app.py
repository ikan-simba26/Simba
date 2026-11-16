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
from urllib.parse import urlsplit

from fastapi import FastAPI, WebSocket

from backend.orchestrator.billing_plan import BILLING_PLAN, BILLING_TASK
from backend.orchestrator.catalogue import (
    CatalogueError, CatalogueStore, address_in, clean_address, host_of, offered,
)
from backend.orchestrator.browser import browser_source, open_page, window_watch
from backend.orchestrator.details import BRIEFS, brief_for, known_from_tile, understand
from backend.orchestrator import host_watch
from backend.orchestrator.llm import (LLMError, label_for, planner_provider_from_env,
                                      provider_from_env)
from backend.orchestrator.ai_settings import (
    AiStore, SettingsError, check as check_ai, provider_for, settings_from,
)
from backend.orchestrator.llm_loop import REGISTRATION_TASK, LLMPlanner, OpenGoalBrief
from backend.orchestrator import robots
from backend.estimator import page_model
from backend.estimator.pairing import Recorder, recording_enabled
from backend.estimator.rules import Decision, LevelRules
from backend.orchestrator.loop import Connection, Task, follow_override, run_brief, run_task
from backend.orchestrator.plan import About
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
from backend.orchestrator.teach import teach
from backend.orchestrator.routine_plan import RoutineBrief, routine_sentence
from backend.orchestrator.routines import (
    NotARoutine, RoutineStore, export, file_name, moved_to, parse,
)
from backend.orchestrator.tiles import TileStore
from backend.orchestrator.traces import TraceStore, site_of
from shared.schema import (
    AiSetup,
    AiStatus,
    CatalogueSite,
    CatalogueTask,
    ErrorPayload,
    GoalAnswered,
    HelpRequested,
    HistoryOffered,
    PastGoal,
    PersonalTile,
    RoutineExport,
    RoutineFile,
    RoutineImport,
    SiteAdd,
    TaughtTile,
    TeachStart,
    TileChange,
)

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

# The installed app's host passes its own PID; if the host goes — even by a
# crash, which stops nothing — the backend goes with it (2026-11-13). Unset in
# development and in tests: nothing is watched.
host_watch.start_from_environment()


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


def past_goals(tiles: TileStore | None = None,
               routines: RoutineStore | None = None,
               catalogue: CatalogueStore | None = None) -> HistoryOffered:
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
    # And the routines helpers have shown (2026-11-04), by name and the
    # site's host only: their moves stay in the encrypted store.
    kept = routines.all() if routines is not None else []
    taught = [TaughtTile(id=r.id, label=r.label, site=urlsplit(r.start).netloc)
              for r in kept]
    # And the websites SIMBA can work with, by genre (2026-11-13), with each
    # taught routine on the site it was taught on.
    listed = (catalogue or CatalogueStore()).load()
    sites = [CatalogueSite(id=site.id, name=site.name, address=site.address, genre=site.genre,
                           added=site.added,
                           tasks=[CatalogueTask(label=t.label, goal=t.goal, how=t.how,
                                                flow=t.flow, routine=t.routine,
                                                taught_on=t.taught_on)
                                  for t in site.tasks])
             for site in offered(listed, kept)]
    return HistoryOffered(goals=[PastGoal(goal=goal, site=site, label=voice.short_label(goal))
                                 for goal, site in goals],
                          tiles=own, routines=taught, sites=sites, genres=listed.genres,
                          ai=ai_status())


def ai_status(check: str = "not_checked") -> AiStatus:
    """Whether an AI provider is set up, from the app's setup or `.env`
    (2026-11-13). Its name and, set up in the app, the key's last four."""
    saved = AiStore().load()
    if saved is not None:
        return AiStatus(configured=True, provider=label_for(saved.base_url),
                        ends_with=saved.ends_with or None, check=check)
    provider = open_goal_provider()
    if provider is None:
        return AiStatus(configured=False, check=check)
    return AiStatus(configured=True, provider=getattr(provider, "label", None), check=check)


async def set_up_ai(connection: Connection, message: dict) -> bool:
    """`ai.setup` from the first-time setup (2026-11-13). Whether it was one.
    Kept, encrypted, then checked with one small question; answered with
    `ai.status`. The key is never logged or sent back."""
    if message.get("type") != "ai.setup":
        return False
    try:
        wanted = AiSetup.model_validate(message.get("payload") or {})
        settings = settings_from(wanted.provider, wanted.key, wanted.base_url, wanted.model)
        AiStore().save(settings)
    except SettingsError as error:
        await connection.send("ai.status", ai_status(error.reason))
        return True
    except ValueError:
        await connection.send("ai.status", ai_status("key"))
        return True
    verdict = await check_ai(provider_for(settings))
    log.info("ai: setup checked: %s", verdict)
    await connection.send("ai.status", ai_status(verdict))
    return True


#: The `error` code for a website that could not be added (2026-11-13).
SITE_NOT_ADDED = "SITE_NOT_ADDED"


async def add_site(connection: Connection, message: dict, tiles: TileStore,
                   routines: RoutineStore, catalogue: CatalogueStore) -> bool:
    """`site.add` from "Add a website" (2026-11-13). Whether it was one.
    Answered with the home screen's offer as it now stands, or an `error`
    whose message is the reason, for the overlay to say in words."""
    if message.get("type") != "site.add":
        return False
    try:
        wanted = SiteAdd.model_validate(message.get("payload") or {})
        catalogue.add(wanted.name, wanted.address, wanted.genre)
    except CatalogueError as error:
        log.info("catalogue: a site not added: %s", error.reason)
        await connection.send("error", ErrorPayload(code=SITE_NOT_ADDED, message=error.reason))
        return True
    except ValueError:
        await connection.send("error", ErrorPayload(code=SITE_NOT_ADDED, message="name"))
        return True
    await connection.send("history.offered", past_goals(tiles, routines, catalogue))
    return True


def site_for(payload: dict, goal: str, catalogue: CatalogueStore | None = None) -> str | None:
    """The website a `task.start` is for (2026-11-13): `site` as sent, or an
    address written in the goal, or (2026-11-16) a listed site the goal names
    in words ("on readings"). None when there is none, or when what was sent
    is not a web address — then the goal is routed as it always was."""
    named = catalogue.named_in(goal) if catalogue is not None else None
    for candidate in (payload.get("site"), address_in(goal), named.address if named else None):
        if not candidate:
            continue
        try:
            return clean_address(str(candidate))
        except CatalogueError:
            continue
    return None


def open_goal_provider():
    """The AI provider for a goal with no plan (2026-11-13), or None when none
    is set up: then SIMBA says it cannot do it yet and offers a helper. Asked
    whatever `SIMBA_USE_HARDCODED_PLAN` says: that flag is about the three
    built-in tasks, which keep their written plans."""
    try:
        # Gemini's Flash for the planner, not Flash-Lite (2026-11-14).
        return planner_provider_from_env()
    except LLMError:
        return None


def quick_provider():
    """The provider that routes goals, for saying a goal back in a sentence
    (2026-11-14): quick, and enough for that. None when none is set up."""
    try:
        return provider_from_env()
    except LLMError:
        return None


def site_name(site: str, catalogue: CatalogueStore) -> str:
    """A website by the name the person knows it: the catalogue's, or its
    address without the `www.`."""
    listed = catalogue.for_address(site)
    if listed is not None and listed.name:
        return listed.name
    host = host_of(site)
    return host[4:] if host.startswith("www.") else host


#: How many moves a goal with no plan is told to expect. A guess the person
#: never sees as a count: the stages are not named for an open goal.
OPEN_GOAL_STEPS = 6


def _place(address: str) -> tuple[str, str]:
    """Where an address is, for telling two websites apart: host and path. Two
    electricity companies' bill pages share a host (2026-11-13)."""
    return host_of(address), urlsplit(address).path.rstrip("/")


def is_flows_site(flow: str, site: str, catalogue: CatalogueStore) -> bool:
    """Whether a built-in flow may run for a goal on `site`: the site is the one
    the flow runs on now, or one the catalogue lists that flow on. A train goal
    on gov.uk is not a train search on Pakistan Railways."""
    if host_of(flow_setup(flow)[3]) == host_of(site):
        return True
    listed = catalogue.for_address(site)
    return listed is not None and any(task.flow == flow for task in listed.tasks)


def change_tile(tiles: TileStore, message: dict, routines: RoutineStore | None = None) -> bool:
    """A `tile.change` from the home screen (2026-10-18). Whether it was one.

    A routine a helper showed (2026-11-04) is one of the person's tiles too:
    renamed or removed by its id, and gone with the rest in a reset. It is not
    moved: routines stand after the tiles, in the order they were kept."""
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
        if routines is not None:
            routines.clear()
        # And the websites the person added (2026-11-13).
        CatalogueStore().clear()
        Vault().clear()
        try:
            TraceStore(os.environ.get("SIMBA_TRACE_DB", DEFAULT_DB)).forget_the_person()
        except sqlite3.Error:
            log.warning("tiles: the reset could not be written to the trace store")
    elif change.action == "remove" and change.id:
        if not tiles.remove(change.id) and routines is not None:
            routines.remove(change.id)
    elif change.action == "rename" and change.id and change.label:
        if not tiles.rename(change.id, change.label) and routines is not None:
            routines.rename(change.id, change.label)
    elif change.action == "move" and change.id and change.to is not None:
        tiles.move(change.id, change.to)
    log.info("tiles: %s", change.action)
    return True


def model_fallback(routine):
    """What a routine may hand the rest of its run to, once the person agrees,
    when it stops because the site changed (2026-11-04): the model planner,
    only when a model is set up and the hardcoded plan was not asked for — the
    launchers ask for it, so on demo day a routine never offers a model. None
    otherwise, and then nothing is offered."""
    if use_hardcoded_plan():
        return None
    try:
        provider = provider_from_env()
    except Exception:  # noqa: BLE001 - no key, no provider: nothing to offer
        return None
    return lambda task: LLMPlanner(provider, replace(task, goal=routine_sentence(routine)))


async def watch_a_helper(connection: Connection, payload: dict, tiles: TileStore,
                         routines: RoutineStore) -> None:
    """`teach.start`: open the website the helper named in the site view and
    watch (`teach.teach`). Only a web address is opened."""
    try:
        url = TeachStart.model_validate(payload).url.strip()
    except ValueError:
        url = ""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        await connection.send("help.requested", HelpRequested(
            reason=voice.TEACH_NOT_AN_ADDRESS, suggestion=voice.TEACH_SUGGESTION))
        return
    log.info("teaching on %s", parts.netloc)
    async with open_page(url) as page:
        await teach(page, connection, url, routines, tiles=len(tiles.all()))


#: The `error` code for a routine's file that could not be kept (2026-11-04).
ROUTINE_NOT_READ = "ROUTINE_NOT_READ"


async def share_routine(connection: Connection, message: dict, tiles: TileStore,
                        routines: RoutineStore) -> bool:
    """A routine saved to a file, or read from one (2026-11-04). Whether the
    message was one of those. Every value the helper typed is asked for in the
    file (`routines.export`); a file read in is checked as data, and kept only
    if there is room on the home screen."""
    kind = message.get("type")
    if kind == "routine.export":
        try:
            wanted = RoutineExport.model_validate(message.get("payload") or {})
        except ValueError:
            return True
        routine = routines.get(wanted.id)
        if routine is not None:
            await connection.send("routine.file", RoutineFile(
                label=routine.label, name=file_name(routine.label), file=export(routine)))
            log.info("routines: one saved to a file")
        return True
    if kind != "routine.import":
        return False
    try:
        text = RoutineImport.model_validate(message.get("payload") or {}).file
        routine = parse(text)
        if routines.add(routine, tiles=len(tiles.all())) is None:
            raise NotARoutine("there is no room for it on the home screen")
        log.info("routines: one read from a file")
    except (ValueError, NotARoutine) as error:
        log.info("routines: a file not kept: %s", error)
        await connection.send("error", ErrorPayload(code=ROUTINE_NOT_READ, message=str(error)))
    await connection.send("history.offered", past_goals(tiles, routines))
    return True


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    connection = Connection(websocket, task_id="t_skeleton")
    tiles = TileStore()
    routines = RoutineStore()
    catalogue = CatalogueStore()

    # Offered before anything is asked for, so the home screen has something
    # to show the moment it connects.
    await connection.send("history.offered", past_goals(tiles, routines, catalogue))

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
        if change_tile(tiles, message, routines):
            await connection.send("history.offered", past_goals(tiles, routines, catalogue))
            return
        # A website added to the list (2026-11-13).
        if await add_site(connection, message, tiles, routines, catalogue):
            return
        # The AI provider, set up in the first-time setup (2026-11-13).
        if await set_up_ai(connection, message):
            return
        # A routine saved to a file, or read from one (2026-11-04).
        if await share_routine(connection, message, tiles, routines):
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
        start = await connection.receive(("task.start", "teach.start"),
                                         on_other=before_the_task)
        payload = start.get("payload", {})
        if start.get("type") == "teach.start":
            # "Show me once" (2026-11-04): a helper does a task while SIMBA
            # watches, and it is kept as a routine. Nothing is routed.
            await watch_a_helper(connection, payload, tiles, routines)
            try:
                await websocket.close()
            except RuntimeError:
                pass
            return
        goal = (payload.get("goal") or "").strip()
        chosen = payload.get("flow")
        # The checklist unless the person asked to be asked every time.
        auto = not bool(payload.get("confirm_each"))
        # The level the person chose as comfortable, kept by the overlay
        # (2026-10-18): the rules start there and come back to it.
        if rules is not None:
            rules.start_from(payload.get("start_level"))

        # The website the goal is for (2026-11-13), set below when there is one.
        site = None
        open_provider = None
        # A routine a helper showed (2026-11-04): run as shown, by its id.
        # Its name is the goal; nothing is read or classified.
        routine = routines.get(payload.get("routine")) if payload.get("routine") else None
        if routine is not None:
            goal = routine.label
            # On another website (2026-11-13): moved there, if the site lets
            # programs use it. Every move is still found and checked there.
            elsewhere = site_for(payload, "")
            if elsewhere is not None and _place(elsewhere) != _place(routine.start):
                if not await robots.allowed(elsewhere):
                    await connection.send("goal.answered", GoalAnswered(
                        kind="not_allowed", goal=goal, flows=[], site=elsewhere))
                    continue
                log.info("routine moved from %s to %s", host_of(routine.start),
                         host_of(elsewhere))
                routine = moved_to(routine, elsewhere)
            break

        # One of the person's own tiles (2026-10-18): its flow and its kept
        # details, and its name as the goal. Nothing is read or classified.
        tile = tiles.get(payload.get("tile")) if payload.get("tile") else None
        # The website the goal is for, if one was picked, typed or written in
        # the goal (2026-11-13). Never for a tile or a flow the person pressed.
        if tile is not None:
            goal = tile.label
            decided = Route("flow", tile.flow, (tile.flow,), "tile")
        elif chosen in ROUTABLE:
            # Picked by the person from something we offered. Not classified
            # again: they have already answered the question.
            decided = Route("flow", chosen, (chosen,), "chosen")
        else:
            site = site_for(payload, goal, catalogue)
            decided = await route(goal, model)
        # The flow only, never the words typed (2026-10-18): this line goes to
        # logs/backend.log, and a goal can hold a reference number. The site by
        # its host only.
        log.info("routed -> %s %s (%s)%s", decided.kind,
                 decided.flow or list(decided.flows), decided.via,
                 f" on {host_of(site)}" if site else "")

        if decided.kind == "flow" and decided.flow is not None and (
                site is None or is_flows_site(decided.flow, site, catalogue)):
            break
        if site is not None and decided.kind != "greeting":
            # A goal on a website with no written plan for it (2026-11-13):
            # the AI planner, if one is set up and the site allows it; else
            # SIMBA says it cannot do it yet and offers a helper there.
            if not await robots.allowed(site):
                await connection.send("goal.answered", GoalAnswered(
                    kind="not_allowed", goal=goal, flows=[], site=site))
                continue
            open_provider = open_goal_provider()
            if open_provider is not None:
                break
            await connection.send("goal.answered", GoalAnswered(
                kind="not_yet", goal=goal, flows=[], site=site))
            continue
        await connection.send(
            "goal.answered",
            GoalAnswered(kind=decided.kind, goal=goal, flows=list(decided.flows)),
        )

    # The person's own starting level, written down beside what they then do
    # (2026-10-18): a signal for the estimator of its own.
    if recorder is not None:
        recorder.note_start_level(payload.get("start_level"))

    if open_provider is not None and site is not None:
        # The AI planner on a goal nobody wrote a plan for (2026-11-13). Since
        # 2026-11-14 it works like the built-in tasks: read back once and
        # agreed once, then the moves that only look run by themselves as the
        # checklist; every move checked; a helper offered if it cannot be
        # done. Asked to confirm every move, every move is asked, as before.
        brief = OpenGoalBrief(open_provider, goal, site_name(site, catalogue),
                              steps=OPEN_GOAL_STEPS, auto=auto, reader=quick_provider())
        log.info("open goal on %s, with %s%s", host_of(site),
                 getattr(open_provider, "label", "the model"),
                 "" if auto else ", every move asked")
        async with open_page(site) as page:
            await run_brief(page, connection, brief, site, recorder, rules,
                            vault=Vault(), window=window_watch(page), auto=auto,
                            teach_site=site)
        log.info("open goal: %d model calls",
                 brief.planner.calls_made if brief.planner else 0)
        try:
            await websocket.close()
        except RuntimeError:
            pass
        return

    if routine is not None:
        # Asks only what the helper said changes, then runs as the checklist,
        # each move found again by role and label and checked (2026-11-04).
        brief = RoutineBrief(routine, fallback=model_fallback(routine))
        log.info("routine: %d moves, %d asked", len(routine.steps), len(routine.asks))
        async with open_page(routine.start) as page:
            await run_brief(page, connection, brief, routine.start, recorder, rules,
                            vault=Vault(), window=window_watch(page), auto=auto)
        try:
            await websocket.close()
        except RuntimeError:
            pass
        return

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
