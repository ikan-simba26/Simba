# How a task flows through SIMBA

Plain language, naming the real files. Read `CLAUDE.md` first for the rules
this has to obey, `CONTRACT.md` for the message shapes, and `DECISIONS.md`
for why any of it is shaped this way.

## The short version

    frontend                backend                          the site
    --------                -------                          --------
    task.start      ──▶     perceive the page        ──▶     read via CDP
                            decide the next action
    step.presented  ◀──     describe it in plain words
    step.response   ──▶     do it                    ──▶     click / type
                            verify it worked         ──▶     read again
                            (retry, or ask for help)
    task.completed  ◀──

Two processes, one WebSocket, and nothing crosses between them that is not
in `CONTRACT.md`.

---

## Stage by stage

### 1. The frontend opens a task

The frontend connects to `/ws` and sends `task.start`.
`backend/orchestrator/app.py:ws_endpoint` accepts the socket, wraps it in a
`Connection` (`loop.py`), and waits for that message.

Two environment variables decide what runs:

- `SIMBA_FLOW` — `registration` or `billing`. Picks the `Task` (goal,
  estimated steps, success condition), the hardcoded plan, and the replica
  URL, from the `FLOWS` table in `app.py`.
- `SIMBA_USE_HARDCODED_PLAN` — `1` runs `HardcodedPlanner`, otherwise
  `LLMPlanner`.

A Chromium page is launched at the frozen 1280x800 viewport and handed to
`loop.run_task` along with the chosen planner. Everything after this point is
planner-agnostic.

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

## Where things live

| Path | What it is |
|---|---|
| `backend/perception/serializer.py` | Page to numbered `Element` list |
| `backend/perception/overlays.py` | Structural blocker and occlusion detection |
| `backend/orchestrator/loop.py` | The shared loop: perceive, present, act, verify, recover |
| `backend/orchestrator/plan.py` | `PlanStep`/`Operation` types, registration plan, `HardcodedPlanner` |
| `backend/orchestrator/billing_plan.py` | The billing flow's plan and task |
| `backend/orchestrator/llm_loop.py` | `LLMPlanner`, the system prompt, `render_page` |
| `backend/orchestrator/llm.py` | Provider interface, validation, token and cost accounting |
| `backend/orchestrator/traces.py` | SQLite trace storage |
| `backend/orchestrator/replay.py` | `TracePlanner` |
| `backend/orchestrator/app.py` | FastAPI `/ws` endpoint and the flow switches |
| `shared/schema.py` / `.ts` | Every contract message, both sides |
| `shared/envelope.py` / `.ts` | Envelope construction, one place |
| `replicas/registration/`, `replicas/billing/` | Local sites to run against |
| `tools/mock_backend.py` | Scripted backend so the frontend can be built alone |

## What is not built yet

The estimator, the credential vault, the three detail levels, `page.preview`
and `load.updated`. `CLAUDE.md` says the skeleton runs end to end before any
of those start. See `STATUS.md` for where each module actually stands.

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
