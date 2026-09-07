# How a task flows through SIMBA

Plain language, naming the real files. Read `CLAUDE.md` first for the rules
this has to obey, `CONTRACT.md` for the message shapes, and `DECISIONS.md`
for why any of it is shaped this way.

## The short version

    overlay (React)         backend (Python)                 the site
    ---------------         ----------------                 --------
    task.start      ──▶     perceive the page        ──▶     read via CDP
                            decide the next action
    step.presented  ◀──     describe it in plain words
    step.response   ──▶     do it                    ──▶     click / type
                            verify it worked         ──▶     read again
                            (retry, or ask for help)
    trust.requested ──▶     screenshot + locate target ──▶   capture
    page.preview    ◀──
    task.completed  ◀──

Two processes, one WebSocket, and nothing crosses between them that is not
in `CONTRACT.md`.

Both live inside one Electron window holding two `WebContentsView`s at
identical 1280x800 bounds: the **site view** with the real website, and the
**overlay** — the React app — added after it so it covers the site view
completely. The user only ever sees the overlay. The backend attaches to the
site view over CDP on port 9222 and drives it.

---

## Stage by stage

### 1. The overlay opens a task

The overlay asks "What would you like me to do?", and sends `task.start`
carrying whatever was typed. That text *is* the task: the backend runs the
goal as sent (`CONTRACT.md`), and only falls back to its configured goal if
the message carries none.
`backend/orchestrator/app.py:ws_endpoint` accepts the socket, wraps it in a
`Connection` (`loop.py`), and waits for that message.

Environment variables decide what runs:

| Variable | Effect |
|---|---|
| `SIMBA_FLOW` | Which site, replica URL and hardcoded plan, from the `FLOWS` table in `app.py` |
| `SIMBA_USE_HARDCODED_PLAN` | `1` runs `HardcodedPlanner`, otherwise `LLMPlanner` |
| `SIMBA_TRACE_MEMORY` | `1` wraps the planner in `TracePlanner` and replays a remembered run |
| `SIMBA_BROWSER` | `chromium` launches a headless browser; `electron` attaches to the running host |
| `SIMBA_LLM_PROVIDER` | `anthropic`, or any OpenAI-compatible endpoint |

`browser.open_page` yields the page to drive — either a fresh headless
Chromium at the frozen viewport, or the Electron host's site view picked out
of its CDP targets by origin (`browser.find_site_page`, which refuses rather
than guessing when two candidates remain). It is handed to `loop.run_task`
with the chosen planner. Everything after this point is planner-agnostic.

### 2. Perceive

`loop.perceive` calls `perception/serializer.py:serialize_async`, which makes
three CDP calls in one session:

| Call | What it gives |
|---|---|
| `Accessibility.getFullAXTree` | roles, accessible names, what is hidden from users |
| `DOM.getDocument` | tag names and attributes, per backend node id |
| `DOMSnapshot.captureSnapshot` | bounds and computed styles for the whole document |

`serializer.build_elements` joins them into a numbered list of `Element`s —
`id`, `role`, `label`, `type`, `tag`, `input_type`, `name`, plus the flags
`overlay`, `occluded` and `dead_link`. Structure comes from the accessibility
tree because it already resolves an accessible name from a `<label for>`, an
`aria-label` or the element's own text, and already drops what a user cannot
see.

`perception/overlays.py:analyse` supplies the two overlay flags. It ignores
ARIA entirely and works from layout: an element that is positioned, stacked
above the page, and covering enough of the viewport is a blocker, and
anything whose centre falls inside it is occluded.

`perceive` also builds a `Snapshot` — url, title, and the tuple of element
labels. That is the "before" picture the verification step compares against.

### 3. Decide

The planner is asked for one `Move`:

```python
await planner.next_move(elements, history, setback)
```

A `Move` (defined in `loop.py`) is what to show the user, what to do, and
what must be true afterwards: `instruction`, `detail`, `operations`,
`expect`, `fields`, `actions`.

Three planners produce them, and that is the *only* thing that differs
between them:

| Planner | File | How it chooses |
|---|---|---|
| `HardcodedPlanner` | `plan.py` | Walks a fixed list of `PlanStep`s |
| `LLMPlanner` | `llm_loop.py` | Asks a model for one action |
| `TracePlanner` | `replay.py` | Replays a remembered run, wrapping one of the above |

`LLMPlanner._choose` renders the page with `render_page`, calls the provider,
and checks the answer. A malformed response or an `element_id` that is not on
the page is retried **once** with the specific error fed back; a second
failure sets `stuck_reason` and returns `None`.

`TracePlanner` looks up `(goal, site)` in SQLite (`traces.py`). With a hit it
replays the recorded steps, each resolved against the *current* page by role
and label. The first step that will not resolve or will not verify ends
replay for good and the wrapped planner takes over from there.

### 4. Present, and wait

`run_task` sends `state.changed: waiting` then `step.presented` with the
move's instruction, the planner's reasoning as `detail`, any input fields,
and the confirm/cancel actions. It then blocks on `connection.receive` until
a `step.response` for that step index arrives.

Nothing acts on the page before the user confirms. A response whose
`action_id` is not `confirm` ends the task with `task.failed`.

### 5. Act

`loop.attempt_move` runs the move's operations. For each one:

1. Perceive again — the previous operation may have navigated.
2. Resolve the target to an id: `loop.pick` matches by role and label, or the
   planner supplied `element_id` directly.
3. Decide the value: `loop.resolve_value` takes the vault's value over
   anything a planner supplied, and **refuses outright** to fill a password
   from a planner-invented string.
4. `loop.act` performs it. `loop.resolve` turns the integer id back into a
   Playwright locator via `get_by_role(role, name=label).nth(...)`.

### 6. Verify

Never assumed, always checked.

- A **fill** is verified by reading the field back (`loop.verify_typed`).
  Typing changes no URL, title or label, so a fill-only move is not also
  required to change the page.
- Anything else must change the page. `loop.verify` polls `perceive` for up
  to `VERIFY_TIMEOUT_S` and compares before against after with `loop.check`,
  which requires both that the snapshot changed at all and that the move's
  `Expectation` holds.

### 7. Recover

Identical code for every planner:

1. The move is retried once with **a different strategy** — a real click
   becomes a JS click, a `fill` becomes clear-then-type. This is the
   `strategy` argument threaded through `attempt_move` and `act`.
2. Still failing, the failure is handed back to the planner as a `setback` on
   the next iteration, and it may choose differently.
3. Two consecutive setbacks and the run stops: `state.changed: stuck`, then
   `help.requested` naming what went wrong.

### 8. Finish

When the task's success `Expectation` is satisfied, `run_task` hands the
moves that actually worked to `planner.finished` if it has one — that is how
`TracePlanner` records a trace — and sends `task.completed` with the step
count, the model calls made, and whether any step was replayed.

---

## What the overlay does with all this

`step.presented` is rendered by `StepShell`, at one of three detail levels
described as data in `frontend/src/levels.ts`. The levels are ordered by
**density** — how much is on screen and how many decisions it asks for — not
by height (`DECISIONS.md`):

| | progress | detail line | fields | second choice | instruction |
|---|---|---|---|---|---|
| Level 1 | stated | shown | all, inline | button | full |
| Level 2 | murmured | hidden | all, stacked | button | full |
| Level 3 | none | hidden | only what it needs | plain text | first sentence |

They are one persistent tree rather than three components, because the change
between them has to *fold*: regions collapse their own height to nothing over
350ms while what remains slides up. Three trees could only crossfade.

`load.updated` moves the level; the user can override and lock it with the
three dots at the foot of the column, which sends `level.override`. While
locked, `load.updated` changes the score and leaves the level alone. Any
change the user did not make raises a dismissible notice — the interface
never reshapes silently. If a step would not fit, the level drops one step
towards level 1 (the compact layout) rather than growing a scrollbar; one hop
only, then it scrolls and says so.

### The trust panel

"What are you doing?" sends `trust.requested`. The loop answers it *while
waiting for `step.response`* — `Connection.receive` takes an `on_other` hook
so a message arriving mid-wait is answered rather than dropped.

`loop.send_preview` screenshots the site view, resolves the element the
current move targets to its bounding box, and sends `page.preview`. The
overlay then slides up and out, showing the capture dimmed with that element
ringed and the caption beneath it.

This is the reason the site view is covered rather than hidden: Chromium
stops reliably repainting a view it believes is invisible, and the capture
times out about half the time (`CLAUDE.md`).

**The capture comes back larger than the viewport.** On this machine the
Electron site view captures at **1920x1200 for a 1280x800 viewport** — a
device pixel ratio of 1.5. The `highlight` bounds in `page.preview` are in
**CSS pixels**, from `locator.bounding_box()`, so they do not match the
image's pixel dimensions. The overlay positions the highlight in
*percentages* of the 1280x800 capture viewport, which is why it lands
correctly regardless of the ratio. Anything that does pixel arithmetic on
that image — cropping, scaling, drawing into it server-side — has to scale by
the ratio first, and must not assume it is 1.

---

## Where things live

| Path | What it is |
|---|---|
| `backend/perception/serializer.py` | Page to numbered `Element` list |
| `backend/perception/overlays.py` | Structural blocker and occlusion detection |
| `backend/orchestrator/loop.py` | The shared loop: perceive, present, act, verify, recover |
| `backend/orchestrator/plan.py` | `PlanStep`/`Operation` types, registration plan, `HardcodedPlanner` |
| `backend/orchestrator/billing_plan.py` | The billing flow's plan and task |
| `backend/orchestrator/browser.py` | Headless Chromium, or attach to the Electron host |
| `backend/orchestrator/llm_loop.py` | `LLMPlanner`, the system prompt, `render_page` |
| `backend/orchestrator/llm.py` | Provider interface, validation, token and cost accounting |
| `backend/orchestrator/traces.py` | SQLite trace storage |
| `backend/orchestrator/replay.py` | `TracePlanner` |
| `backend/orchestrator/app.py` | FastAPI `/ws` endpoint and the flow switches |
| `shared/schema.py` / `.ts` | Every contract message, both sides |
| `shared/envelope.py` / `.ts` | Envelope construction, one place |
| `frontend/electron/main.ts` | The window: site view, then overlay on top of it |
| `frontend/src/App.tsx` | The overlay: one column, one thing at a time |
| `frontend/src/levels.ts` | What each detail level shows, as data |
| `frontend/src/components/StepShell.tsx` | One step at any level, and the fold between them |
| `frontend/src/components/TrustPanel.tsx` | "What are you doing?" and the annotated capture |
| `frontend/src/store.ts` | Every message applied, in one place |
| `replicas/registration/`, `replicas/billing/` | Local sites to run against |
| `tools/mock_backend.py` | Scripted backend so the overlay can be built alone |

## What is not built yet

The **estimator** — nothing computes a load score, so `load.updated` is only
ever sent by the mock, and a real run sits at level 2 unless the user moves
it. The **credential vault** — values still arrive in `step.response` rather
than being injected from a store the model cannot see, though
`loop.resolve_value` already refuses to fill a password from anything a
planner supplied. **Voice input**, and **replay tuning** (when to prefer a
trace over fresh planning).

See `STATUS.md` for where each module actually stands.

---

## The planner system prompt

Verbatim from `backend/orchestrator/llm_loop.py:SYSTEM_PROMPT`. It is the
whole of what the model is told about its job; everything else it sees is the
goal, the action history, and the rendered page.

```text
You operate a web page on behalf of someone who finds cluttered interfaces overwhelming.

You are given a goal and a numbered list of the page's interactive elements. Choose the single next action that makes progress toward the goal.

Rules:
- Answer with an element_id taken from the list. Never write a CSS selector, an XPath, or element text as the id.
- One action at a time. Do not plan ahead in the answer.
- Use "type" for text fields, "click" for buttons and links, "select" for dropdowns.
- For a password or username field, set value to null. Those are filled from the user's vault, not by you.
- If any element is marked OVERLAY, something is covering the page. Dismiss it first, using one of the OVERLAY elements, before anything else. Nothing marked OCCLUDED can be clicked until you do.
- Never choose an element marked OCCLUDED.
- Never choose an element marked "dead link" — it goes nowhere and wastes a step.
- When the goal needs the user signed in, fill the sign-in fields on this page rather than navigating. Prefer form fields and buttons over navigation links.
- Keep reasoning to one short sentence, phrased for the person you are helping.
```

The page it is given alongside this looks like:

```text
AN OVERLAY IS COVERING THE PAGE. Everything marked OCCLUDED is unreachable until it is dismissed, using an OVERLAY element.

1. button 'Close'  <- OVERLAY
2. link 'Home'  <- OCCLUDED, cannot be clicked  <- dead link, goes nowhere
3. textbox 'Student ID or Username' [input type=text]  <- OCCLUDED, cannot be clicked
...
```
