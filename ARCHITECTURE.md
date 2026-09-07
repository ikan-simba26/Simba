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
`id`, `role`, `label`, `type`, `tag`, `input_type`, `name`, `value`, `rect`,
plus the flags `overlay`, `occluded`, `dead_link` and `inferred`. Structure
comes from the accessibility tree because it already resolves an accessible
name from a `<label for>`, an `aria-label` or the element's own text, and
already drops what a user cannot see.

The snapshot is parsed once by `perception/snapshot.py:parse` and read by
three modules, so all three agree on what the page looks like:

| Module | Reads | For |
|---|---|---|
| `overlays.py` | position, z-index, bounds | what is covering the page, or covering one element |
| `interactivity.py` | `cursor`, sibling structure | controls the accessibility tree calls text |
| `content.py` | text, tables, `font-size` | what the page *says* |

**`interactivity.py` is why a real site works at all.** A component framework
renders a dropdown option as `<li class="...__item"><span>LAHORE CANTT</span>`
— no role, no tabindex, no aria — and the accessibility tree carries it as
`StaticText`, indistinguishable from a paragraph. So this ignores semantics
and reads layout: an element with a computed `cursor: pointer` is something a
person is being told they can click, and three or more same-class siblings
inside a floating panel are a list of choices. What it finds is flagged
`inferred`, because a role the page declared and a role we guessed at deserve
different amounts of trust.

Those elements have no role to look up, so `serialize` also computes a
structural path for each one and the backend uses it in `loop.resolve`. A
planner still only ever says `click(14)`.

**`content.py` is the second output channel.** Interactive elements are what
the page offers; content is what it says — headings with their level, table
rows paired to their column headers, label/value pairs, and text set
noticeably larger than the page's own baseline. A task whose goal is to read
a number needs it: `14,382` alone is a number, and `("P/WITHIN", "14,382")`
is an answer. It travels separately so nothing can confuse "the page says
14,382" with "there is a button called 14,382". Content stops at a floating
panel — a date picker is a control, not something the page says.

`perceive` also builds a `Snapshot` — url, title, the tuple of element labels,
the tuple of field **values**, and the content. That is the "before" picture
verification compares against. Values are in it because a form that has been
filled is not the same page as an empty one, and without them a step that
typed a station name into a combobox changed nothing the loop could see.

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
  Typing changes no URL, title or label, so a move of fills and key presses
  is not also required to change the page. A move of presses alone is, since
  it has no read-back to stand on.
- Anything else must change the page. `loop.verify` polls `perceive` for up
  to `VERIFY_TIMEOUT_S` and compares before against after with `loop.check`,
  which requires both that the snapshot changed at all and that the move's
  `Expectation` holds.
- And **durably**: `loop.durability_failure` re-checks, at every later
  perceive, that each value this run typed is still there. Read-back proves
  the keystrokes arrived; it does not prove the value stays, and a
  component-framework combobox clears its own input on blur unless a choice
  was committed. A lapse ends the run rather than being retried — the typing
  worked, something undid it, and repeating the keystrokes invites the same
  undoing while every later step acts on a form that is not filled.

An `Expectation` can be about the URL, the title, a label appearing or
going — or about **content**: `content_says` and `rows_at_least`. Those exist
because a single-page app finishes a search without changing its URL, its
title or one interactive label, and until content was readable such a task
had no expressible success condition at all.

What none of this catches: **the DOM is not the application's state.** A live
date input read back `2026-10-15` at every check while the framework's own
model held `""`, and the search went out empty. Every signal available here
agrees with the DOM and is wrong together. See `EVALUATION.md`.

### 7. Recover

Identical code for every planner:

1. The move is retried once with **a different strategy** — a real click
   becomes a JS click, and a `fill` becomes click-then-select-all-then-type.
   This is the `strategy` argument threaded through `attempt_move` and `act`.

   The fill fallback clicks first because `fill` and `clear` both wait for an
   element to be *editable*, and a framework combobox ships its input
   `readonly` until clicked, removing the attribute in its own handler. The
   direct route times out on a field nothing is blocking; a click is not
   subject to that check.

Every action is capped at `ACTION_TIMEOUT_MS` (10s) rather than Playwright's
30s default. A person is watching the step, and the loop retries — at 30s a
step that fails both strategies costs over a minute before anyone is told.
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
| `backend/perception/serializer.py` | Page to numbered `Element` list, and the content channel |
| `backend/perception/snapshot.py` | One parse of the CDP snapshot, shared by the three readers |
| `backend/perception/overlays.py` | Structural blocker and occlusion detection, page-level and target-scoped |
| `backend/perception/interactivity.py` | Controls the accessibility tree calls text |
| `backend/perception/content.py` | What the page says: headings, tables, pairs, values |
| `backend/orchestrator/loop.py` | The shared loop: perceive, present, act, verify, recover |
| `backend/orchestrator/plan.py` | `PlanStep`/`Operation` types, registration plan, `HardcodedPlanner` |
| `backend/orchestrator/billing_plan.py` | The billing flow's plan and task |
| `backend/orchestrator/railways_plan.py` | The live read-only train search |
| `tools/screen_site.py` | Screen a site before pointing anything at it |
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
