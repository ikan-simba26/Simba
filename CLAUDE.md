# SIMBA

Desktop app that performs web tasks on behalf of users who find cluttered
interfaces overwhelming. The real website loads in a hidden browser view; the
user sees only a clean, one-step-at-a-time overlay that simplifies itself when
the user appears to be struggling.

Final-year project, three people, hard deadline December 2026.

## Architecture

Two processes, talking only over WebSocket.

- **Frontend** — Electron + React + TypeScript. Renders the overlay. Owns a
  hidden `WebContentsView` holding the target site.
- **Backend** — Python + FastAPI. Perception, orchestration, cognitive load
  estimation. Drives the hidden view via Playwright over CDP.

Every message between them is defined in `CONTRACT.md` and mirrored in
`shared/schema.py` and `shared/schema.ts`. Nothing crosses the boundary that
isn't in the contract.

## Modules

| Module | Owner | Path | Responsibility |
|---|---|---|---|
| Perception | Nahail | `backend/perception/` | Page reading, element serialization, page-side load features |
| Orchestrator | Raham | `backend/orchestrator/` | Plan, act, verify, retry, trace replay, LLM interface |
| Interface | Aly | `frontend/` | Overlay, three detail levels, trust panel, credential vault |
| Estimator | Nahail | `backend/estimator/` | Fuses page features + user behaviour into a load score |

Anyone may work anywhere. The owner reviews changes to their area.

## The runtime loop

    goal -> perceive -> score load -> decide action -> render step
         -> user confirms -> act -> verify -> loop

Verification is not optional. After every action, snapshot the page and check
it changed the way the plan expected. If it didn't: retry once with a different
strategy, then hand control to the user. Never assume a click worked.

## Rules

- **Never execute an irreversible action.** No payments, no form submissions
  that alter real records, no account changes. Stop at the confirmation screen.
  This is a design constraint, not a limitation.
- **The LLM never sees a credential.** The vault injects values directly into
  the DOM. Secrets never enter a prompt or a log.
- **The LLM never emits a selector.** Perception assigns integer IDs to
  elements; the model says `click(14)`. The backend resolves 14 to a handle.
- **Repeated benchmark runs go against local replicas**, never a live site.
- Do not change `CONTRACT.md` or the schema files without all three owners
  agreeing. Additive optional fields are fine; renames and removals are not.
- Do not add dependencies without asking.
- Do not use OpenCV, local LLMs, or text-to-speech. Out of scope.
- `.env` is never committed.

## Conventions

- Python 3.11, type hints everywhere, `ruff` + `black`. Tests in `pytest`.
- TypeScript strict mode. No `any`.
- Tests before implementation for anything in the verification path.
- Small commits. Branch per feature: `feat/<module>-<thing>`.
- Every contributor sets `git config user.name` and `user.email` locally so
  commits are attributed correctly even though pushes share one account.

## Current phase

September: walking skeleton. One task, one local replica, full loop, fixed
detail level, **plan hardcoded — no LLM yet**. Get the pipes working before
adding intelligence.

Do not build the estimator, replay, or the three-level UI until the skeleton
runs end to end.
