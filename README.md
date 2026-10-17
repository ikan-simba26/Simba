# SIMBA

Desktop app that performs web tasks on behalf of users who find cluttered
interfaces overwhelming. The real website loads in a hidden browser view; the
user sees only a clean, one-step-at-a-time overlay that simplifies itself when
the user appears to be struggling.

New here? Read this file top to bottom and you will have it running. It
assumes nothing is installed yet. `DEMO.md` is for showing it to someone,
`RUNNING.md` for the day-to-day commands once it works.

## Architecture

Two processes, talking only over WebSocket.

- **Frontend** — Electron + React + TypeScript. Renders the overlay. Owns a
  hidden `WebContentsView` holding the target site.
- **Backend** — Python + FastAPI. Perception, orchestration, cognitive load
  estimation. Drives the hidden view via Playwright over CDP.

Every message between them is defined in `CONTRACT.md` and mirrored in
`shared/schema.py` and `shared/schema.ts`. Nothing crosses the boundary that
isn't in the contract.

## Repository layout

| Path | Responsibility |
|---|---|
| `backend/perception/` | Page reading, element serialization, page-side load features |
| `backend/orchestrator/` | Plan, act, verify, retry, trace replay, LLM interface |
| `backend/estimator/` | Fuses page features + user behaviour into a load score |
| `frontend/` | Overlay, three detail levels, trust panel, credential vault |
| `shared/` | Message contract mirrored as `schema.py` / `schema.ts` |
| `replicas/` | Local site replicas — `registration` (:5000), `billing` (:5100), `railways` (:5200, our copy of the train search) |
| `tools/` | Dev tooling: the mock backend, screenshots, demo recordings |
| `data/` | The page corpus and its labels |
| `spike/` | The Electron + CDP experiment the architecture rests on |

---

# Installing from scratch

## 1. What must already be on the machine

| | Version used here | Check it |
|---|---|---|
| **Python** | 3.12.3 (3.12 or newer) | `python --version` |
| **Node.js** | 24.12.0 (18 or newer) | `node --version` |
| **npm** | 11.6.2 (ships with Node) | `npm --version` |
| **git** | any | `git --version` |

On Windows, use **Windows PowerShell or PowerShell 7**, not the editor's
integrated terminal — see the `ELECTRON_RUN_AS_NODE` note at the bottom, which
costs people an hour if they meet it without warning.

```powershell
git clone <this repo> simba
cd simba
```

## 2. The backend

A virtual environment inside `backend/`, then two installs and a browser.

```powershell
# Windows PowerShell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
playwright install chromium
cd ..
```

```bash
# macOS / Linux / git bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
playwright install chromium
cd ..
```

`requirements.txt` is what the backend needs to *run*: FastAPI, uvicorn,
pydantic, Playwright, and the two LLM clients. `requirements-dev.txt` includes
it and adds pytest, flask and websockets — flask because the tests start the
local replicas themselves, so the replicas' dependency is a test dependency
too. Installing the dev file gets both; there is no reason to install only the
first unless you are deploying.

`playwright install chromium` downloads a browser (~150 MB) into Playwright's
own cache. Without it the backend starts and then fails on the first task.

**Check it:**

```powershell
python -c "import fastapi, playwright, pytest; print('backend ok')"
```

## 3. The frontend

```powershell
cd frontend
npm ci
cd ..
```

This pulls Electron (~100 MB) as well as React, Tailwind and Vite. It takes a
few minutes on a first run and nothing after that. `npm ci` installs exactly
the versions in `package-lock.json` — every Python and Node dependency is
pinned to the versions the suite passes with (RUNNING.md, *Installing the
exact versions*).

**Check it:**

```powershell
cd frontend
npm run build          # type-checks both tsconfigs, then builds
cd ..
```

A clean build prints the Vite summary and writes `frontend/dist/` and
`frontend/dist-electron/`. A type error here is a real error: the project is
TypeScript strict with no `any`.

## 4. The model key — optional

SIMBA runs without one. The hardcoded planner does the same thing every time
and spends no quota, and goal routing falls back to keyword matching when no
key is configured. **Everything in `DEMO.md` works with no key at all.**

For the LLM planner, copy the example and fill it in:

```powershell
copy .env.example .env      # bash: cp .env.example .env
```

`.env` is never committed. `SIMBA_LLM_PROVIDER` picks `anthropic` or
`openai` (any OpenAI-compatible endpoint); pin an exact model string, never an
alias like `*-latest`, or two benchmark runs stop being comparable.

## 5. Prove the install

From the repo root, with the venv active, **in two halves** — one
`python -m pytest` over everything stops at collection, because
`backend/orchestrator/` and `frontend/` each have a `test_checklist.py`
(checked on a fresh clone, 2026-10-17):

```powershell
python -m pytest backend tools test_basetemp.py     # about 900 tests
python -m pytest frontend                           # about 530 tests
```

About 1,430 tests in all; every one passes, and 12 skip. On the machine this
was written on, each half takes 20–25 minutes. The tests start the replicas
they need, so nothing has to be running first. The skips are deliberate: 5
want a running Electron host, 2 more want a host **and** `SIMBA_HOST_TESTS=1`,
3 open the host themselves and also want `SIMBA_HOST_TESTS=1`, and 2 want
`SIMBA_LIVE_TESTS=1`, which points at a real public website. The first lines
of each run say whether the machine was on battery and how much memory was
free: the same suite has taken nearly twice as long on one day as the day
before.

Do step 3 (`npm run build`) before this: the overlay layout tests read
`frontend/dist`, and skip themselves rather than fail when it is not there.

If that passes, most of the system is proven and what remains to check is the
*wiring*.

---

# Running it

## The short way

```powershell
.\run.ps1                # opens on the registration replica — or ./run.sh anywhere with bash
.\run.ps1 billing        # opens on the billing replica
.\run.ps1 railways       # opens on the live site
.\run.ps1 railways-local # opens on our own copy of the train search — rehearse here
.\run.ps1 mock           # the overlay against the scripted backend, no browser driving
```

The argument is only **the page the window opens on**. What you type chooses
the task, from any start page, because the registration and billing replicas
are always up. A train goal runs on the live site unless you started with
`railways-local`, which also brings up our copy of the train search (:5200)
and sends train goals there.

One command starts both replicas, the Electron host and the backend, in the
order they need, and prints `==> ready - type a goal in the SIMBA window and
press Start`. Ctrl+C stops everything it started and leaves nothing listening.

Type a goal in the window — `What do I owe on my electricity bill?` — and
press Start. `RUNNING.md` covers every start page and what each failure looks
like.

## The long way, in three pieces

Worth doing once, because it shows what `run.ps1` is doing.

### 1. One flow, headless — no frontend, no Electron

The backend drives its own Chromium. The fastest way to watch the loop work.

```bash
# terminal 1 — the target site (not needed for railways, which is live)
python replicas/billing/app.py                           # port 5100

# terminal 2 — the backend
SIMBA_USE_HARDCODED_PLAN=1 python -m uvicorn backend.orchestrator.app:app --port 8000
```

```powershell
# PowerShell sets variables separately
$env:SIMBA_USE_HARDCODED_PLAN = "1"
python -m uvicorn backend.orchestrator.app:app --port 8000
```

`curl http://127.0.0.1:8000/` reports what it is configured to do. Nothing
happens until something connects to `/ws` and sends `task.start` — either the
overlay, or a script.

### 2. The whole stack — Electron host, overlay, hidden site view

Three terminals, in this order. Order matters: the backend attaches to the
host, so the host has to exist first.

```bash
# 1. the target site
python replicas/billing/app.py

# 2. the Electron host: the window, the overlay, and the hidden site view
cd frontend && SIMBA_START_URL=http://127.0.0.1:5100 npm start

# 3. the backend, attached to the host over CDP
SIMBA_BROWSER=electron SIMBA_USE_HARDCODED_PLAN=1 \
  python -m uvicorn backend.orchestrator.app:app --port 8000
```

The overlay talks to `ws://127.0.0.1:8000/ws`; the backend drives the site view
the window is hiding. `http://127.0.0.1:9222/json/list` should show two
targets — the overlay (`dist/index.html`) and the site.

With the host up, the 5 stack tests run, and 2 more with the switch:

```bash
python -m pytest backend/orchestrator/test_electron_stack.py
SIMBA_HOST_TESTS=1 python -m pytest backend/perception/test_snapshot.py
```

### 3. The overlay on its own

The overlay is a plain web page, so it can be worked on without Electron, a
browser view or a real backend. `tools/mock_backend.py` plays the backend's
side of the whole conversation, routing typed goals the same way the real one
does.

```bash
python -m uvicorn tools.mock_backend:app --port 8000
cd frontend && npm run dev
```

See `frontend/README.md`. This is for working on the overlay, not for running
SIMBA: nothing is driving a website.

---

## Switches

All environment variables, all read at the backend.

| Variable | Default | What it does |
|---|---|---|
| `SIMBA_ROUTER` | `model` | How a typed goal is routed: `model` asks the configured provider once and falls back to keywords with no key, no quota or no answer in 8s; `keywords` never calls a model (the tests' default) |
| `SIMBA_FLOW` | unset | **No longer chooses the task** — the typed goal does (2026-09-21), and the launchers no longer set it (2026-09-25). `stubborn` runs a registration request on the rigged page that measures recovery; with `SIMBA_REPLICA_URL`, points that one flow at another URL |
| `SIMBA_REGISTRATION_URL`, `SIMBA_BILLING_URL`, `SIMBA_RAILWAYS_URL` | per flow | Override one flow's site |
| `SIMBA_USE_HARDCODED_PLAN` | off | Run the flow's written plan instead of the LLM |
| `SIMBA_BROWSER` | `chromium` | `electron` attaches to a running host over CDP |
| `SIMBA_TRACE_MEMORY` | off | Replay a goal already done on this site from SQLite |
| `SIMBA_ADAPT` | on | The provisional level rules choose the detail level as a run goes and send `load.updated`; `0` keeps the level where the overlay puts it |
| `SIMBA_RECORD_STEPS` | on | Write each step's page features, telemetry and level decisions to `data/steps.jsonl`; the test suite turns it off |
| `SIMBA_REPLICA_URL` | per flow | Legacy: the site of the flow named in `SIMBA_FLOW`, or of registration when none is |
| `SIMBA_OVERLAY_DETECTION` | on | Ablation switch for structural blocker detection |
| `SIMBA_INFERRED_ROLES` | on | Ablation switch for non-semantic control detection |
| `SIMBA_SETBACK_PLACEMENT` | `above` | Where a setback sits in the prompt: `above` the element list or `after` it. Ablation arm; see EVALUATION.md, 2026-09-18 |
| `SIMBA_LIVE_TESTS` | off | Let the two tests that hit a real website run |
| `SIMBA_HOST_TESTS` | off | Let the tests that open real Electron windows run |
| `SIMBA_LOG_FILE` | `logs/backend.log` | Where the backend writes what each run did and how long each part took; empty keeps it to the terminal |

---

## When it does not work

**The Electron window never appears, and the error names your entry point.**
Check `ELECTRON_RUN_AS_NODE`:

```powershell
$env:ELECTRON_RUN_AS_NODE          # bash: echo $ELECTRON_RUN_AS_NODE
```

If it is set, the Electron binary runs as plain Node — no window, no CDP, and
an error about your file rather than the real cause. Some editors set it in
their integrated terminal. `run.ps1` and `run.sh` clear it; starting the host
by hand, use a terminal where it is unset.

**`port 8000 is already in use`.** An earlier run is still alive. `run.ps1`
refuses to start rather than half-attach to it. Close the old terminal, or stop
the stray `python` / `electron` process, then start again.

**A task sits on step 1 and then says it is stuck.** For railways, the live
site is probably down or slow; the billing and registration flows are local and
unaffected. The stuck screen is the system working: it stops rather than guess.

**The reading screen waits about eight seconds every time.** The model router
is timing out on its one classification call — no key, or no quota. It falls
back to keywords and the answer is the same; set `SIMBA_ROUTER=keywords` to
skip the wait.

**`ModuleNotFoundError: No module named 'backend'`.** Run pytest from the repo
root (`python -m pytest`), not from inside a package directory. The root
`conftest.py` is what puts the repo on `sys.path`.

---

## Conventions

- Python 3.12, type hints everywhere. Tests in `pytest`.
- **No formatter or linter is in use.** `ruff` and `black` were named here
  until 2026-09-17, but neither was ever installed or run. Measured that day
  over the repository's 57 Python files: `black` would reformat 46 of them
  (about 2,000 changed lines at its default width), and `ruff` with its
  defaults reports 69 findings, 30 of them not auto-fixable. Adopting either
  means one reformat across every module, so it is a decision for all three
  owners, not a convention to assume.
- TypeScript strict mode. No `any`.
- Tests before implementation for anything in the verification path.
- Small commits. Branch per feature: `feat/<module>-<thing>`.
- **Stage with explicit file paths.** Never `git add -A` or `git add .`.
- Every contributor sets `git config user.name` and `user.email` locally so
  commits are attributed correctly even though pushes share one account.

## The other documents

| File | What it is for |
|---|---|
| `CLAUDE.md` | The project's rules, in full. Read before changing anything. |
| `CONTRACT.md` | Every message between frontend and backend. |
| `RUNNING.md` | Every flow, every switch, every failure, day to day. |
| `DEMO.md` | Showing SIMBA to someone in under five minutes. |
| `ARCHITECTURE.md` | Why it is two processes and a covered view. |
| `DECISIONS.md` | What was settled, when, and on what evidence. |
| `EVALUATION.md` | Every measurement, with its conditions. |
| `STATUS.md` | Where each module actually is. |
| `HANDOVER.md` | Picking the project up cold. |
