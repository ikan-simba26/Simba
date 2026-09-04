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

## Architecture constraints

Findings from the `spike/` Electron + CDP + Playwright test.

- **The hidden view needs real laid-out bounds plus `setVisible(false)`.**
  Sizing the `WebContentsView` to `0x0` to hide it breaks Playwright's click
  actionability check — elements permanently report as "outside of the
  viewport" and clicks time out, even though reads (title, link text) still
  work. Giving the view a real size and hiding it with `setVisible(false)`
  instead fixes this; reads and clicks both work.
- **Viewport is frozen at 1280x800.** The estimator measures text density per
  visible area, so the viewport must stay constant across runs — changing it
  changes the density numbers independently of anything the page actually
  did. Confirmed read-and-click still work at 1280x800.
- **Screenshotting the hidden view is possible but unreliable.** Playwright
  can screenshot a `setVisible(false)` `WebContentsView`, and the screenshot
  does reflect the page's current content after navigation (confirmed:
  content and byte size change to match the new page). But repeated capture
  calls on the same hidden view are flaky — in testing, roughly every other
  `page.screenshot()` call timed out waiting for a compositor frame that
  never arrived, with no navigation or scrolling in between. Chromium appears
  not to reliably keep repainting a surface that's marked invisible. Anything
  built on `page.preview` / `trust.requested` needs a retry-with-timeout
  strategy, or should briefly flip the view visible for the capture and back,
  rather than assuming a single screenshot call will return promptly.
- **Lazy-loaded content still fires in a hidden view.** An
  `IntersectionObserver`-backed lazy load target updated correctly after a
  programmatic `window.scrollTo(...)` on a `setVisible(false)` view — DOM,
  layout, and JS execution keep running normally in the hidden view; only
  the compositor/paint step (screenshotting) is what's flaky.

## Current phase

September: walking skeleton. One task, one local replica, full loop, fixed
detail level, **plan hardcoded — no LLM yet**. Get the pipes working before
adding intelligence.

Do not build the estimator, replay, or the three-level UI until the skeleton
runs end to end.
