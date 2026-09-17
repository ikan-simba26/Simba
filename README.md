# SIMBA

Desktop app that performs web tasks on behalf of users who find cluttered
interfaces overwhelming. The real website loads in a hidden browser view; the
user sees only a clean, one-step-at-a-time overlay that simplifies itself when
the user appears to be struggling.

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
| `replicas/` | Local site replicas used for repeated benchmark runs |
| `tools/` | Dev tooling, including the mock backend harness |

## Setup

### Backend (Python + FastAPI)

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt        # runtime
pip install -r requirements-dev.txt    # runtime + test deps
playwright install chromium
```

`requirements.txt` is what the backend needs to run. `requirements-dev.txt`
adds pytest plus the replicas' own dependencies, because the tests start the
local replicas themselves.

### Frontend (Electron + React + TypeScript)

```bash
cd frontend
npm install
npm start          # type-checks, builds, and opens the Electron window
```

`npm run dev` serves only the overlay, in an ordinary browser, with no site
view behind it — useful for working on the overlay against the mock backend,
not for running SIMBA. See `frontend/README.md`.

## The quickest way to run it

```powershell
.\run.ps1            # or ./run.sh — registration replica, window, backend, in order
```

`RUNNING.md` has every flow and what to do when one fails. The sections below
are the pieces by hand.

## Running it

Three ways, in order of how much has to be running. Start at the top: if the
tests pass, most of the system is already proven, and the later steps mainly
prove the *wiring*.

### 1. The tests — nothing has to be running

```bash
python -m pytest        # from the repo root
```

The tests start the replicas they need. On 2026-09-17: 271 pass, in
about five minutes; 7 skip, and the skips are deliberate — 5 want a live
Electron host (see 3 below) and 2 want `SIMBA_LIVE_TESTS=1`, which points at a
real public website. (This said 214 until 2026-09-17, which was out of date
by ten days.)

```bash
SIMBA_LIVE_TESTS=1 python -m pytest -k live     # hits pakrailways.gov.pk
```

### 2. One flow, headless — no frontend, no Electron

The backend can drive its own Chromium. This is the fastest way to watch the
loop work end to end.

```bash
# terminal 1 — the target site (skip for the railways flow, which is live)
python replicas/registration/app.py                      # port 5000
python replicas/billing/app.py                           # port 5100

# terminal 2 — the backend
SIMBA_FLOW=registration SIMBA_USE_HARDCODED_PLAN=1 \
  python -m uvicorn backend.orchestrator.app:app --port 8000
```

`curl http://127.0.0.1:8000/` reports what it is configured to do. Nothing
happens until something connects to `/ws` and sends `task.start` — either the
overlay (3 below) or a script.

### 3. The whole stack — Electron host, overlay, hidden site view

Three terminals, in this order. Order matters: the backend attaches to the
host, so the host has to exist first.

```bash
# 1. the target site
python replicas/registration/app.py

# 2. the Electron host: the window, the overlay, and the hidden site view
cd frontend && npm install
SIMBA_START_URL=http://127.0.0.1:5000 npm start

# 3. the backend, attached to the host over CDP
SIMBA_FLOW=registration SIMBA_USE_HARDCODED_PLAN=1 SIMBA_BROWSER=electron \
  python -m uvicorn backend.orchestrator.app:app --port 8000
```

Type a goal in the window and press Start. The overlay talks to
`ws://127.0.0.1:8000/ws`; the backend drives the site view the window is
hiding. `http://127.0.0.1:9222/json/list` should show two targets — the
overlay (`dist/index.html`) and the site.

With the host up, the 5 skipped tests run:

```bash
python -m pytest backend/orchestrator/test_electron_stack.py
```

**If the Electron window never appears**, check `ELECTRON_RUN_AS_NODE`:

```bash
env | grep ELECTRON_RUN_AS_NODE        # PowerShell: $env:ELECTRON_RUN_AS_NODE
```

If it is set, the Electron binary runs as plain Node — no window, no CDP, and
an error naming your entry point rather than the real cause. Some editors set
it in their integrated terminal. Start the host from a terminal where it is
unset, or clear it for the one command.

### The overlay on its own

The overlay is a plain web page, so it can be driven without Electron at all:
build it, serve `frontend/dist`, and point it at the mock backend, which
plays the backend's side of the whole conversation.

```bash
python -m uvicorn tools.mock_backend:app --port 8000
```

## Switches

All environment variables, all read at the backend.

| Variable | Default | What it does |
|---|---|---|
| `SIMBA_FLOW` | `registration` | `registration`, `billing`, or `railways` (live, read-only) |
| `SIMBA_USE_HARDCODED_PLAN` | off | Run the flow's written plan instead of the LLM |
| `SIMBA_BROWSER` | `chromium` | `electron` attaches to a running host over CDP |
| `SIMBA_TRACE_MEMORY` | off | Replay a goal already done on this site from SQLite |
| `SIMBA_REPLICA_URL` | per flow | Override the site the flow opens |
| `SIMBA_OVERLAY_DETECTION` | on | Ablation switch for structural blocker detection |
| `SIMBA_INFERRED_ROLES` | on | Ablation switch for non-semantic control detection |
| `SIMBA_LIVE_TESTS` | off | Let the two tests that hit a real website run |

The LLM path needs `.env` — see `CLAUDE.md`. It is never committed.

## Conventions

- Python 3.11, type hints everywhere. Tests in `pytest`.
- **No formatter or linter is in use.** `ruff` and `black` were named here
  until 2026-09-17, but neither was ever installed or run. Measured that day
  over the repository's 57 Python files: `black` would reformat 46 of them
  (about 2,000 changed lines at its default width), and `ruff` with its
  defaults reports 69 findings, 30 of them not auto-fixable. Adopting either
  means one reformat across every module, so it is a decision for all three
  owners, not a convention to assume.
- TypeScript strict mode. No `any`.
- Small commits. Branch per feature: `feat/<module>-<thing>`.
- Every contributor sets `git config user.name` and `user.email` locally so
  commits are attributed correctly even though pushes share one account.

See `CLAUDE.md` for full project rules and `CONTRACT.md` for the frontend/backend
message contract.
