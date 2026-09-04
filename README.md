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
pip install -r requirements.txt
```

### Frontend (Electron + React + TypeScript)

```bash
cd frontend
npm install
npm run dev
```

## Conventions

- Python 3.11, type hints everywhere, `ruff` + `black`. Tests in `pytest`.
- TypeScript strict mode. No `any`.
- Small commits. Branch per feature: `feat/<module>-<thing>`.
- Every contributor sets `git config user.name` and `user.email` locally so
  commits are attributed correctly even though pushes share one account.

See `CLAUDE.md` for full project rules and `CONTRACT.md` for the frontend/backend
message contract.
