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

The person decides; SIMBA clicks (2026-10-14). Once the person has made their
choices — a journey read back and agreed, a bill's number, a course — the
moves a plan marks safe (filling in, opening a calendar, searching, opening a
page to read) run without a press each, as a checklist with one Pause. A real
choice, anything the person must type, anything that went wrong, and anything
that pays, books, registers or changes a record still waits for "user
confirms". A person can ask to confirm every move.

Verification is not optional. After every action, snapshot the page and check
it changed the way the plan expected. If it didn't: retry once with a different
strategy, then hand control to the user. Never assume a click worked.
Two exceptions get one attempt, not two: a step that waits for a list to open,
and a step that changes something (a second press could make the change twice).

## Rules

- **The final-step rule** (2026-10-16, replacing "never execute an
  irreversible action"). An action that pays, books, registers or changes a
  record happens only **(a) on a replica** — a site we wrote, served from this
  machine — and **(b) after a dedicated final screen** that says in plain
  words exactly what will happen, shows the key details (what, how much,
  when) as the page states them, and has two buttons: do it / don't. No
  default, no timer. "Don't" ends the task and says nothing was changed. On a
  live site SIMBA reads and never books, pays or changes anything, and it
  never types payment details anywhere. `loop.carry_out` enforces (a) and (b)
  whichever planner asks.
- **The LLM never sees a credential.** The vault injects values directly into
  the DOM. Secrets never enter a prompt or a log.
- **The LLM never emits a selector.** Perception assigns integer IDs to
  elements; the model says `click(14)`. The backend resolves 14 to a handle.
- **Repeated benchmark runs go against local replicas**, never a live site.
- Do not change `CONTRACT.md` or the schema files without all three owners
  agreeing. Additive optional fields are fine; renames and removals are not.
- Do not add dependencies without asking.
- Do not use OpenCV or local LLMs. Out of scope.
- Text-to-speech is in scope only as reading a step aloud in the system's own
  speech voice, in English, when the person presses the button for it — off
  by default, stopped when the step changes, and never a bundled or cloud
  voice. Approved by Raham on 2026-10-14; Nahail and Aly still to be told
  (DECISIONS.md).
- `.env` is never committed.

## Tooling boundaries

Applies to any agent or script working in this repo, not just to people.

- **Never take a full-screen or full-desktop screenshot.** When a visual check
  is genuinely needed, capture the specific application window and nothing
  else. A desktop capture sweeps up whatever else the machine is showing.
- **Never read or write files outside the project directory.** Temporary files
  belong in the repo's ignored paths, not in the home directory or system
  temp.
- **Never run a broad kill command.** No `taskkill /F` with a filter
  (`/FI`, `/IM`), no `pkill` or `killall` by name, nothing that matches
  processes by pattern. Stop only processes you started, by PID — the PID you
  got when you started it, or the one listening on a port you started it on.
  On 2026-10-05 a `taskkill /F /FI "WINDOWTITLE eq none"` was run while
  stopping a mock backend; it matched nothing, which was luck.
- **Ask before any action that touches the system rather than the repo** —
  installing software, changing global configuration, killing processes that
  aren't ones this work started, or anything that outlives the checkout.

## Reporting

Every task ends with a report covering all five of these. A task is not
finished until it has one.

1. **Files changed.** What was touched, and what each change was for.
2. **What was measured, with numbers.** Not "it works" — the step count, the
   wall clock, the token count, the pass rate. If nothing was measured, say
   that outright rather than implying it was.
3. **What failed and why.** Including failures that were fixed along the way.
   A defect found and corrected is the most useful thing in the report; a
   report with no failures in it is usually an incomplete one.
4. **Decisions made that weren't asked for.** Anything settled that the task
   did not specify. Each one also goes in `DECISIONS.md`.
5. **Flagged for human review.** See below.

Numbers go in `EVALUATION.md`, decisions in `DECISIONS.md`, module state in
`STATUS.md`. Update `STATUS.md` at the end of every task.

## Flag design questions, don't settle them quietly

When a design question comes up that the task did not ask about, it does not
get decided in passing and buried in a diff. Raise it under **flagged for
review** with:

- the question, in one line;
- the options actually available;
- a recommendation, and what it costs.

Then either wait, or proceed with the recommendation and say clearly that you
did. What is not acceptable is a choice that only shows up later as a
surprise in the code.

This applies hardest where the code already works. A silent decision inside
something passing its tests is the one nobody reviews.

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
- **Stage with explicit file paths.** `git add path/to/file.py`, never
  `git add -A` or `git add .`. A broad add sweeps up unrelated edits and
  quietly bundles two changes into one commit, which is how a reviewable
  history stops being reviewable.
- Every contributor sets `git config user.name` and `user.email` locally so
  commits are attributed correctly even though pushes share one account.

## Architecture constraints

Findings from the `spike/` Electron + CDP + Playwright test.

- **Hide the site view by covering it, never by hiding it.** The site view
  stays `setVisible(true)` at full 1280x800 bounds, positioned at the window's
  origin, and the overlay view is added to the window *after* it, filling the
  window's content area, so it covers every part of the site view the window
  shows. Chromium keeps compositing a covered view, so screenshots stay
  reliable; the user still never sees it. This is the standard approach —
  `spike/main.js` is the reference; `frontend/electron/main.ts` adds the
  fitting to the screen.

  The two alternatives both fail, and neither is a free choice:

  | Approach | Viewport | Screenshots | Click |
  |---|---|---|---|
  | Covered by overlay, `setVisible(true)` | 1280x800 | **20/20** | works |
  | `setVisible(false)` | 1280x800 | 2/5 | works |
  | Positioned outside the parent, `setVisible(true)` | collapses to 0x0 | 0/5 | fails |

- **The site view may extend past the window, but is never positioned
  outside it.** On a screen smaller than 1280x800 (a 1080p laptop at 150% has
  a 1280x672 work area) the window is smaller than the site view, and the rest
  of the site view lies past its right and bottom edges. That is measured safe
  at 125% and 150%: viewport 1280x800, 20/20 captures, clicks work
  (EVALUATION.md, 2026-09-25b). What fails is *position*: `0x0` bounds, or an
  origin past the parent's edge, collapses the renderer's viewport to 0x0.
  Reads (title, link text) still work, but every click times out with
  "element is outside of the viewport", because nothing can ever be inside a
  zero-size viewport.
- **Viewport is frozen at 1280x800.** The estimator measures text density per
  visible area, so the viewport must stay constant across runs — changing it
  changes the density numbers independently of anything the page actually
  did.
- **A view hidden with `setVisible(false)` cannot be screenshotted
  reliably.** Captures alternated pass/fail at 40% (2/5), timing out waiting
  for a compositor frame that never arrived, with no navigation or scrolling
  in between — Chromium does not reliably repaint a surface marked invisible.
  Content itself was correct when a capture did return, including after
  navigation. Covering the view instead of hiding it takes this to 100%
  (20/20), which is what `page.preview` / `trust.requested` depends on.
- **Lazy-loaded content fires normally.** An `IntersectionObserver`-backed
  target updated correctly after a programmatic `window.scrollTo(...)` even
  on a `setVisible(false)` view. DOM, layout, and JS execution always keep
  running; compositing was the only thing at risk.

## Current phase

**Changed 2026-11-13 by the advisor's direction (Ma'am Samia, 12 November),
approved by Raham; pending Nahail and Aly** (DECISIONS.md, *The advisor's
direction of 12 November*). The deadline is **19 November 2026**; building
stops on 17 November. The feature freeze and "Do not add new sites or flows"
are lifted for the advisor's list: SIMBA works on any website (a catalogue of
sites by genre, any address typed, the AI planner first, then a helper's
"Show me once"), live tasks behind the final screen with payment always handed
to the person, an installer and a first-time setup. The text below is the
October phase, kept for the record.


October 2026: from skeleton to evidence. Feature freeze is 1 November;
November is evaluation and writing; December is the report and demo.

Priorities, in order: (1) the estimator trained on human ratings with
tools/rating, a small interpretable scikit-learn model, cross-validated, with
feature importance, replacing the provisional rules and checked against their
logged decisions; (2) the product for its audience: the home screen fits at
every scaling, a minimal credential store, and the answer explained in one
plain sentence; (3) early sessions with two or three people, including someone
who works with people with cognitive disabilities; (4) evaluation readiness:
benchmarks re-run on current perception, the stronger-model ablation, and an
LLM baseline on an unseen goal.

Do not add new sites or flows, or any feature not listed here, without asking.
