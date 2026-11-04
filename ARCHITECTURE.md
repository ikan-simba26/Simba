# How a task flows through SIMBA

Plain language, naming the real files. Read `CLAUDE.md` first for the rules
this has to obey, `CONTRACT.md` for the message shapes, and `DECISIONS.md`
for why any of it is shaped this way.

**Refreshed 2026-09-17** against the code as checked out that day, and corrected
on 2026-11-02. What had drifted is listed at the end, under *Drift found*, rather
than corrected silently.

## The short version

    overlay (React)         backend (Python)                 the site
    ---------------         ----------------                 --------
                    ◀──     history.offered (on connect)
    task.start      ──▶     perceive the page        ──▶     read via CDP
                            decide the next action
    step.presented  ◀──     describe it in plain words
    step.response   ──▶     do it                    ──▶     click / type
                            verify it worked         ──▶     read again
                            (retry, or ask for help)
    step.failed     ◀──     (if a step was carried past)
    trust.requested ──▶     screenshot + locate target ──▶   capture
    page.preview    ◀──
    task.completed  ◀──     or task.failed, or help.requested

Two processes, one WebSocket, and nothing crosses between them that is not
in `CONTRACT.md`.

Both live inside one Electron window holding two `WebContentsView`s: the **site
view** with the real website, always 1280x800 at the window's origin, and the
**overlay** — the React app — added after it and filling the window's content
area, which is smaller than the site view on a small screen. So it covers
everything of the site view the window shows, and the user only ever sees the
overlay. The backend attaches to the site view over CDP on port 9222 and drives
it.

---

## Stage by stage

### 1. The overlay opens a task

When the socket opens, the backend sends `history.offered` — up to three goals
from the trace store, and the person's own tiles by name — before anything is
asked (`app.py:past_goals`). On opening, the overlay shows the logo until that
message arrives, trying again meanwhile, because the launchers start the window
first, and for 15s at most (`Brand.tsx`). The home screen greets the person, and
shows their own tiles, the three things SIMBA can do, at most two of those goals,
and the text box, which is always there.

Choosing a tile or typing a goal sends `task.start`. That text *is* the task:
the backend runs the goal as sent (`CONTRACT.md`), and only falls back to its
configured goal if the message carries none.
`backend/orchestrator/app.py:ws_endpoint` accepts the socket, wraps it in a
`Connection` (`loop.py`), and waits for that message. **One socket carries
one task**: the backend closes it when the task ends, or after `loop.OFFER_IDLE_S`
if a closing screen's offer is keeping it open, and the overlay reconnects for
the home screen.

Environment variables decide what runs:

| Variable | Effect |
|---|---|
| `SIMBA_ROUTER` | `model` (default) routes each typed goal with one call to the configured provider, falling back to keywords; `keywords` never calls a model. See `router.py` |
| `SIMBA_FLOW` | Since 2026-09-21 it does **not** choose the task; the typed goal does. `stubborn` runs a registration request on the rigged page that measures recovery |
| `SIMBA_REPLICA_URL` | Legacy override: the site of the flow in `SIMBA_FLOW`, or of registration when none is set. `SIMBA_<FLOW>_URL` overrides one flow directly |
| `SIMBA_USE_HARDCODED_PLAN` | `1` runs `HardcodedPlanner`, otherwise `LLMPlanner` |
| `SIMBA_TRACE_MEMORY` | `1` wraps the planner in `TracePlanner`, which replays a remembered run and records new ones |
| `SIMBA_TRACE_DB` | Where the trace store is (default `traces.db` at the repo root) |
| `SIMBA_BROWSER` | `chromium` launches a headless browser; `electron` attaches to the running host |
| `SIMBA_CDP_URL` | Where the Electron host's CDP endpoint is |
| `SIMBA_OVERLAY_URL` | Excludes a dev-server overlay when picking the site view |
| `SIMBA_LLM_PROVIDER` | `anthropic`, or `openai` for any OpenAI-compatible endpoint |
| `SIMBA_LLM_EFFORT` | Thinking effort for the Anthropic provider |
| `SIMBA_OVERLAY_DETECTION`, `SIMBA_INFERRED_ROLES` | Ablation switches in perception |
| `SIMBA_SETBACK_PLACEMENT` | `above` (the design) or `after`, for comparing where a setback sits in the prompt |
| `SIMBA_ADAPT` | On by default: the rules choose the level. `0` sends no `load.updated` |
| `SIMBA_PAGE_MODEL` | On by default: the trained model judges the first page. `0`, or no model file, leaves that to the rules |
| `SIMBA_RECORD_STEPS` | On by default: rows go to `data/steps.jsonl`. `0` turns it off |
| `SIMBA_LOG_FILE` | Where the backend's run log goes (default `logs/backend.log`); empty keeps it to the console |

`browser.open_page` yields the page to drive — either a fresh headless
Chromium at the frozen viewport, or the Electron host's site view picked out
of its CDP targets by origin (`browser.find_site_page`, which refuses rather
than guessing when two candidates remain). It is handed to `loop.run_task`
with the chosen planner. Everything after this point is planner-agnostic.

### 1b. Read the goal, and ask for what it left out

Since 2026-09-30 a routed goal is read for the details the flow needs before
anything runs (`details.py:understand`): where from, where to and which day;
a reference number; a course code. The configured model reads it, bounded at
eight seconds, and a keyword and date reader supplies whatever the model did
not say — or all of it, when there is no model. Nothing the model reports is
kept unless it can be held to what the person typed.

Whatever is still missing goes to a `Brief`, which `loop.run_brief` asks for
one question at a time, as ordinary `step.presented` messages with the site
already open behind them and nothing on it touched. A question has a few
buttons where the answers are few (`choice:0`, `choice:1`, ...) and one box to
type in otherwise; every other id the step offers is an answer and only
`cancel` stops (`loop.is_answer`). Three unusable answers to one question end
the run the way being stuck does.

When nothing is missing, `Brief.settle()` returns the planner and the task,
both built from the person's own details — including what has to be true at
the end, so a search for another route or another day fails rather than
completes. Trace memory wraps whatever planner it settled on, keyed on the
details spelled out rather than on the words typed.

A planner may also ask mid-run (`Move.question`), for what only the page can
raise: `TripPlanner` asks which Lahore station was meant, because the site's
own list is what says there are two.

### 2. Perceive

`loop.perceive` calls `perception/serializer.py:read_async`, which makes
three CDP calls in one session:

| Call | What it gives |
|---|---|
| `Accessibility.getFullAXTree` | roles, accessible names, what is hidden from users |
| `DOM.getDocument` | tag names and attributes, per backend node id |
| `DOMSnapshot.captureSnapshot` | bounds and computed styles for the whole document |

`serializer.build_elements` joins them into a numbered list of `Element`s —
`id`, `role`, `label`, `type`, `tag`, `input_type`, `name`, `value`, `rect`,
plus the flags `overlay`, `occluded`, `dead_link` and `inferred`, and for an
inferred element `qualifier` and `panel`. Structure comes from the
accessibility tree because it already resolves an accessible name from a
`<label for>`, an `aria-label` or the element's own text, and already drops
what a user cannot see.

The snapshot is parsed once by `perception/snapshot.py:parse` and read by
three modules, so all three agree on what the page looks like:

| Module | Reads | For |
|---|---|---|
| `overlays.py` | position, z-index, bounds | what is covering the page, or covering one element |
| `interactivity.py` | `cursor`, sibling structure, class tokens | controls the accessibility tree calls text |
| `content.py` | text, tables, `font-size` | what the page *says* |

**`interactivity.py` is why a real site works at all.** A component framework
renders a dropdown option as `<li class="...__item"><span>LAHORE CANTT</span>`
— no role, no tabindex, no aria — and the accessibility tree carries it as
`StaticText`, indistinguishable from a paragraph. So this ignores semantics
and reads layout: an element with a computed `cursor: pointer` is something a
person is being told they can click, and three or more same-class siblings
inside a floating panel are a list of choices. What it finds is flagged
`inferred`. Inside a floating panel everything is an `option`; elsewhere a
list item is a `menuitem` and anything else a `button` (DECISIONS.md). Four
class tokens become a `qualifier` (`previous month`, `next month`,
`disabled`, `today`), and the panel's own heading becomes `panel`.

Those elements have no role to look up, so `serialize` also computes a
structural path for each one (`locator_hint`) and the backend uses it in
`loop.resolve`. A planner still only ever says `click(14)`.

**`content.py` is the second output channel.** Interactive elements are what
the page offers; content is what it says — headings with their level, table
rows paired to their column headers, label/value pairs, and text set
noticeably larger than the page's own baseline. `14,382` alone is a number;
`("P/WITHIN", "14,382")` is an answer. Content stops at a floating panel — a
date picker is a control, not something the page says.

`perceive` also builds a `Snapshot` — url, title, the tuple of element labels,
the tuple of field **values**, and the content. That is the "before" picture
verification compares against.

### 3. Decide

The planner is asked for one `Move`:

```python
await planner.next_move(elements, history, setback)
```

A `Move` (defined in `loop.py`) is what to show the user, what to do, and
what must be true afterwards: `instruction`, `detail`, `operations`,
`expect`, `fields`, `actions`. Three more say how it is treated: `question`,
`safe` (it may run without a press) and `changes` (it books, pays, registers or
changes a record).

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
failure sets `stuck_reason` and returns `None`. The model can `click`, `type`
or `select`; it cannot `press` a key, which only hand-written plans use.

`render_page` puts three kinds of banner above the element list when they
apply — an overlay is covering the page; a list of choices is open; what the
open panel says it is showing — because a fact a planner must act on *at this
step* is ignored when it is one line among many (EVALUATION.md, *"Where
information sits is a perception decision"*). `llm.build_user_prompt` puts a
setback above the list for the same reason.

`TracePlanner` looks up `(goal, site)` in SQLite (`traces.py`). With a hit it
replays the recorded steps, each resolved against the *current* page by role
and label. The first step that will not resolve or will not verify ends
replay for good and the wrapped planner takes over from there.

### 4. Present, and wait

The loop (`loop.carry_out`) sends `state.changed: waiting` then `step.presented`
with the move's instruction, detail, any input fields, its actions, and whatever
the task has found so far. It then blocks on `connection.receive` until a
`step.response` for that step index arrives.

The words come from two places. A hand-written plan writes its own
instruction, detail and primary label. Everything else — the stop button
("Stop this"), the LLM and replay confirm button ("Yes, do that"), the
sentence describing a move a planner chose — comes from
`backend/orchestrator/voice.py`. `frontend/test_copy.py` holds both to the
same rules as the overlay's own `copy.ts`.

**The person decides, SIMBA clicks** (2026-10-14). Not every move waits. Once the
person has decided, a `safe` move runs by itself as a checklist line:
`step.presented` with `requires_confirmation: false`, with Pause as its one answer.
A real choice, anything to type, the next move after anything that went wrong, and
any move that `changes` something still asks, and a person can ask to confirm every
move (`task.start.confirm_each`).

What an answer does depends on the step. On a **question**, every id it offers is an
answer and only `cancel` stops (`loop.is_answer`). On an **ordinary step**, `confirm`
goes on, `remember` goes on and keeps the password, `decline` on a yes-or-no question
leaves that one move undone, and anything else stops. On a **final screen**, see
stage 8. A stop reaches the overlay as `task.failed`.

### 5. Act

`loop.attempt_move` runs the move's operations. For each one:

1. Perceive again — the previous operation may have navigated.
2. Resolve the target to an id: `loop.pick` matches by role, label and (if
   given) qualifier, or the planner supplied `element_id` directly.
3. Decide the value: `loop.resolve_value` takes the step response's value over
   anything a planner supplied, and **refuses outright** to fill a password
   from a planner-invented string.
4. Refuse if something is covering the point a click would land on
   (`loop.covering`, a fresh target-scoped overlay check).
5. `loop.act` performs it. `loop.resolve` turns the integer id back into a
   Playwright locator — `locator_hint` for an inferred element, otherwise
   `get_by_role(role, name=label).nth(...)`.

Every action is capped at `ACTION_TIMEOUT_MS` (10s) rather than Playwright's
30s default.

### 6. Verify

Never assumed, always checked.

- A **fill** is verified by reading the field back (`loop.verify_typed`).
  Typing changes no URL, title or label, so a move of fills and key presses
  is not also required to change the page. A move of presses alone is.
- Anything else must change the page. `loop.verify` polls `perceive` for up
  to `VERIFY_TIMEOUT_S` and compares before against after with `loop.check`,
  which requires both that the snapshot changed at all and that the move's
  `Expectation` holds.
- And **durably**: `loop.durability_failure` re-checks, at every later
  perceive, that each value this run typed is still there. A lapse ends the
  run rather than being retried or handed to the planner — tried the other
  way on 2026-09-09 and reverted the same day (DECISIONS.md).

An `Expectation` can be about the URL, the title, a label appearing or
going, or **content**: `content_says` and `rows_at_least`.

What none of this catches: **the DOM is not the application's state.** A live
date input read back `2026-10-15` at every check while the framework's own
model held `""`, and the search went out empty. See `EVALUATION.md`.

### 7. Recover

Identical code for every planner:

1. The move is retried once with **a different strategy** — a real click
   becomes a JS click, and a `fill` becomes click-then-select-all-then-type.
   The fill fallback clicks first because a framework combobox ships its
   input `readonly` until clicked, and `fill` waits for editable forever.
2. Still failing, the loop sends `step.failed` — the person sees a quiet
   notice — and hands the failure to the planner as a `setback` on the next
   iteration, where it may choose differently. The hardcoded planner ignores
   setbacks and simply serves its next step.
3. Two consecutive setbacks and the run stops: `state.changed: stuck`, then
   `help.requested` naming what went wrong, with the suggestion from
   `voice.HELP_SUGGESTION`.

### 8. Finish

A task declares what it is about in `Task.about` (`plan.About`): `holds`, the
values its goal names as the page must show them, and `finds`, the values it
asks for and the names to show them under. It is required — `About()` is
allowed but has to be written.

At every perceive, `loop.findings_in` reads each `finds` value from the
content channel and remembers it, because the answer is often on a page the
run leaves before it ends. Those findings go out on every `step.presented`
and on `task.completed`.

Before each move, if the task has a `success` expectation, `loop.unmet`
checks the page against `holds` and then `success`; if nothing is unmet, the
run stops early. `holds` alone never ends a run early — a filled form nobody
has searched with holds every value.

When the planner has nothing more, the same check runs on the final page
whenever the task has a `success` expectation *or* any `holds`. Unmet, the
run ends in `help.requested` with the reason. Met, the loop hands the moves
that worked to `planner.finished` if it has one — that is how `TracePlanner`
records a trace — and sends `task.completed` with the step count, model calls,
whether any step was replayed, and the findings.

**The final-step rule** (2026-10-16, CLAUDE.md), held in `loop.carry_out` for every
planner. A move that books, pays, registers or changes a record (`loop.would_change`)
ends the run on a page not served from this machine (`loop.on_replica`), and
otherwise goes through a final screen, which says what will happen, with the page's
own details, and has two answers and no default. `confirm` does it, once: a second
press could make the change twice. `decline` ends the task with "Nothing was changed."
A page that asks for card or bank details ends the run on any site.

**`task.completed` says what was and was not done.** `scope` is what was done;
`confirmation` and `caveat` quote the site; `proof` is a still of the page as the task
closed, with what was read ringed, or `proof_note` says why there is none. `offer`
keeps the run open for a quiet "Book one of these" or "Pay this bill", on a replica
only, and `keep` offers to keep the task as a tile.

---

## What the overlay does with all this

The overlay is one column showing one screen at a time (`App.tsx`): the welcome on a
first open, home, working ("Let me open that for you." then "Give me a moment."), a
step, the checklist, or one of six endings — found an answer, done, failed, stuck,
stopped by the person, and "I didn't do it. Nothing was changed." **Every ending
offers "Back to start"**, which returns to the home screen;
`frontend/test_terminal_states.py` renders each, including after a step, and fails if
one has nothing to press or a button that goes nowhere.

The person's own stop is decided in the overlay, not read from the backend. `cancel`
stops the task, which the loop reports as `task.failed`, so the overlay shows its stop
ending the moment the answer is sent (`store.respond`) and ignores the `task.failed`
that follows. "Don't" on a final screen is handled the same way. Every word it writes
itself is in `frontend/src/copy.ts`.

`step.presented` is rendered by `StepShell`, at one of three detail levels
described as data in `frontend/src/levels.ts`. The levels are ordered by
**density**, not height (`DECISIONS.md`):

| | progress | detail line | fields | second choice | instruction | findings |
|---|---|---|---|---|---|---|
| Level 1 | stated | shown | all, inline | button | full | shown |
| Level 2 | murmured | hidden | all, stacked | button | full | shown |
| Level 3 | none | hidden | only what it needs | plain text | first sentence | hidden until the end |

They are one persistent tree rather than three components, because the change
between them has to *fold*: regions collapse their own height over 350ms
while what remains slides up.

`load.updated` moves the level; the user can override and lock it with the
three dots at the foot of the column, which sends `level.override`. Any
change the user did not make raises a dismissible notice — one of two
sentences, chosen by direction alone. If a step would not fit, the level
drops to level 1 (the compact layout) rather than growing a scrollbar; one hop
per step, then it scrolls. That move is for that screen: the next step goes
back to the level it came from, on both sides, with nothing sent.

`step.failed` raises a quiet notice — "I couldn't do that. I'm carrying on."
— that outlives the step it belongs to, since the next step arrives
milliseconds later.

### The trust panel

"What are you doing?" sends `trust.requested`. The loop answers it *while
waiting for `step.response`* — `Connection.receive` takes an `on_other` hook
so a message arriving mid-wait is answered rather than dropped.

`loop.send_preview` screenshots the site view, resolves the element the
current move targets to its bounding box, and sends `page.preview` with a
caption from `voice.caption`. The overlay slides up and out, showing the
capture dimmed with that element ringed and the caption beneath it.

This is the reason the site view is covered rather than hidden: Chromium
stops reliably repainting a view it believes is invisible (`CLAUDE.md`).

**The capture may come back larger than the viewport.** On the machine this
was measured on, the Electron site view captured at **1920x1200 for a
1280x800 viewport** — a device pixel ratio of 1.5. The `highlight` bounds are
in **CSS pixels**, so the overlay positions the ring in *percentages* of the
1280x800 viewport, which is correct at any ratio. Anything that does pixel
arithmetic on that image has to scale by the ratio first. Not re-measured on
2026-09-17.

---

## Where things live

| Path | What it is |
|---|---|
| `backend/perception/serializer.py` | Page to numbered `Element` list, and the content channel |
| `backend/perception/snapshot.py` | One parse of the CDP snapshot, shared by the three readers |
| `backend/perception/overlays.py` | Structural blocker and occlusion detection, page-level and target-scoped |
| `backend/perception/interactivity.py` | Controls the accessibility tree calls text |
| `backend/perception/content.py` | What the page says: headings, tables, pairs, values |
| `backend/orchestrator/loop.py` | The shared loop: perceive, present, act, verify, recover, finish |
| `backend/orchestrator/plan.py` | `PlanStep`, `Operation`, `Target`, `Expectation`, `About`, `FieldValue`, `Shown`; the registration plan, fixed and per course; `HardcodedPlanner` |
| `backend/orchestrator/voice.py` | Every fixed string the backend puts on screen |
| `backend/orchestrator/billing_plan.py` | The billing flow's plan and task |
| `backend/orchestrator/railways_plan.py` | The live read-only train search: the worked example's plan, and `TripPlanner` for a person's own journey |
| `backend/orchestrator/details.py` | What a goal says, what is still missing, and the briefs that ask for it |
| `backend/orchestrator/browser.py` | Headless Chromium, or attach to the Electron host |
| `backend/orchestrator/llm_loop.py` | `LLMPlanner`, the system prompt, `render_page`, the registration task |
| `backend/orchestrator/llm.py` | Provider interface, validation, token and cost accounting, transcripts |
| `backend/orchestrator/traces.py` | SQLite trace storage |
| `backend/orchestrator/replay.py` | `TracePlanner` |
| `backend/orchestrator/app.py` | FastAPI `/ws` endpoint, `history.offered`, the flow switches |
| `backend/orchestrator/vault.py` | One saved password per site, encrypted with this Windows account's key |
| `backend/orchestrator/tiles.py` | The person's own tiles, encrypted with the same key |
| `backend/orchestrator/teach.py` | Show me once (2026-11-04): the recorder in the page, each press held until perception has read it, the same-or-ask question, the answer pointed at, the read-back and the name |
| `backend/orchestrator/routines.py` | A routine a helper showed: moves by role and label, kept encrypted like the tiles, saved to and read from a file |
| `backend/orchestrator/routine_plan.py` | `RoutineBrief` (asks only what changes) and `RoutinePlanner` (each move found again, the person's row asked from the page's own rows, a change's final details read from the page, the honest stop, the model only if agreed) |
| `backend/estimator/` | Page features (`page_features.py`), step/telemetry/decision rows (`pairing.py`), training (`train.py`), the trained model as the app reads it (`page_model.py`), and the level rules (`rules.py`), which take the model's judgement of the page and fall back on their own signs |
| `shared/schema.py` / `.ts` | Every contract message, both sides |
| `shared/envelope.py` / `.ts` | Envelope construction, one place |
| `frontend/electron/main.ts` | The window: site view, then overlay on top of it |
| `frontend/src/App.tsx` | The overlay: home, working, step, the checklist and the six endings |
| `frontend/src/copy.ts` | Every word the overlay writes itself |
| `frontend/src/store.ts` | Every message applied, in one place |
| `frontend/src/connection.ts` | The WebSocket, framed as envelopes; `?ws=` overrides the address |
| `frontend/src/levels.ts` | What each detail level shows, as data |
| `frontend/src/components/StepShell.tsx` | One step at any level, and the fold between them |
| `frontend/src/components/StateSignal.tsx` | The four states shown without words; the stuck note |
| `frontend/src/components/LevelControl.tsx` | The three dots, the lock, the level notice |
| `frontend/src/components/Notices.tsx` | The skipped-step and level notices, and how long they stay |
| `frontend/src/components/TrustPanel.tsx` | "What are you doing?" and the annotated capture |
| `frontend/src/components/TeachBar.tsx`, `TeachIntro.tsx`, `ReadBack.tsx` | Show me once (2026-11-04): the bar while a helper is watched, the screen behind it in the settings, and the read-back |
| `frontend/src/components/Debug.tsx` | The development view, Ctrl+Shift+D |
| `frontend/src/components/Brand.tsx` | The logo while SIMBA opens, which waits for the backend's first message, and the small one on the home screen |
| `assets/brand/` | The logo kit as supplied; `derived/` holds the same drawings without a background or a tagline, for the overlay and the README |
| `frontend/src/useOverflowGuard.ts` | Drops a level when a step will not fit |
| `frontend/test_copy.py` | The voice rules, for `copy.ts`, the components and the backend |
| `frontend/test_levels.py`, `frontend/test_terminal_states.py` | Rendered tests in a real browser |
| `replicas/registration/`, `replicas/billing/`, `replicas/railways/` | Local sites to run against, and the only places anything is booked, paid or registered |
| `tools/mock_backend.py` | Scripted backend so the overlay can be built alone |
| `tools/screen_site.py` | Screen a site before pointing anything at it |
| `tools/evaluation/` | The scripts behind EVALUATION.md's tables |
| `run.ps1`, `run.sh` | One command; the argument is the page the window opens on, the typed goal picks the task |
| `spike/` | The Electron + CDP + Playwright proof the constraints in `CLAUDE.md` came from |

## What is not built yet

**Half of the estimator.** Since 2026-10-30 a model trained on people's ratings
judges the first page of a task (`backend/estimator/page_model.py`, reading
`data/estimator.json`), and with no model the rules' three signs do. What the
person does in a step — one level simpler on a clear telemetry signal, back
after two calm steps — is still read by **provisional hand-written rules**
(`backend/estimator/rules.py`), and no person's behaviour is behind their
thresholds. Pages after the first are scored and logged, and do not move the
level. Every decision is logged to `data/steps.jsonl`, with who judged the page
and what the rules would have said. **A credential store past the minimum**: one
saved password per site, Windows only, typed by the backend and never in a prompt
(`vault.py`), and forgettable only from a sign-in step. **Voice input**, and
**replay tuning**.

See `STATUS.md` for where each module actually stands.

---

## The planner system prompt

Verbatim from `backend/orchestrator/llm_loop.py:SYSTEM_PROMPT`, checked
against the code on 2026-09-17.

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

The page it is given alongside this, captured from the registration replica's
course page with its modal up on 2026-09-17 (first lines of 66):

```text
AN OVERLAY IS COVERING THE PAGE. Everything marked OCCLUDED is unreachable until it is dismissed, using an OVERLAY element.

1. button 'Close' [input type=button]  <- OVERLAY
2. link 'Home'  <- OCCLUDED, cannot be clicked  <- dead link, goes nowhere
...
11. link 'Registrar'  <- OCCLUDED, cannot be clicked
...
36. button 'Register for CS-401' [input type=submit]  <- OCCLUDED, cannot be clicked
```

`HANDOVER.md` has fuller samples, including the live site.

---

## Drift found on 2026-09-17

What this file said that was no longer true, and was changed:

- **Stage 7's numbered list was broken.** A paragraph about the action
  timeout had been inserted between items 1 and 2.
- **The render sample was not real output.** It showed `3. textbox 'Student
  ID or Username'` on the page with the modal — a page that has no textbox —
  and omitted `[input type=button]` on `Close`. Replaced with a capture.
- **Stage 1** described the overlay asking "What would you like me to do?"
  first. There has been a home screen with remembered goals, and
  `history.offered`, since 2026-09-15.
- **Stage 5** described `loop.resolve` as `get_by_role` only, and did not
  mention the covering check. Inferred elements resolve by `locator_hint`.
- **Stage 8** said nothing about findings or about the final check ending in
  `help.requested`, and described success as "the task's success
  `Expectation`" only.
- **Stage 7** did not mention `step.failed`, which has existed since
  2026-09-09.
- **The overlay section** did not mention the home screen, findings, the four
  endings, `copy.ts`, or the skipped-step notice. It also said overflow, once
  it has hopped, "scrolls and says so"; it says so in the developer's console,
  not to the person.
- **The environment table** listed five of the twelve `SIMBA_*` variables the
  backend reads. (The Electron host reads three more — `SIMBA_START_URL`,
  `SIMBA_CDP_PORT`, `SIMBA_DEV_SERVER` — and the launchers two.)
- **The file table** was missing `voice.py` (new), `copy.ts`, `connection.ts`,
  four components, the overflow guard, the tests, the launchers and `spike/`.

Changed by this task, so not drift: `Expectation.value_is` and
`Task.answers` are now `Task.about`.

## Drift found on 2026-11-02

What this file said that was no longer true, and was changed:

- **The two views** were described at identical 1280x800 bounds. The overlay has
  been the window's own size since 2026-09-25.
- **Stage 1** kept the text box behind "Ask for something new", which went on
  2026-10-14, and did not mention tiles or the logo. One socket does not always
  end with its task since closing-screen offers.
- **Stage 4 and the overlay section** said any answer but `confirm` stops a task, and
  that nothing runs before the person confirms. Both stopped being true on 2026-09-30
  and 2026-10-14; what each kind of step does is now spelled out.
- **Stage 8** said nothing of the final-step rule, proof or offers, all from 2026-10-16.
- **The overlay section** counted five endings, with no welcome and no checklist.
- **"What is not built"** said no credential vault, which has existed since
  2026-10-03.
- **`run_task`** was named for the loop's own work, which is in `carry_out`.
- **The file table** named `StepNotice.tsx`, which is gone, and left out `vault.py`,
  `tiles.py` and the railways replica. **The environment table** left out four
  switches that decide what runs.

Checked and left alone: the system prompt above, which matches the code word for
word. The level table was compared with `levels.ts` on what it shows, not on its
findings column.
