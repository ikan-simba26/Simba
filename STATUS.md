# Status

Per module: what is done, what is in progress, what is blocked and on whom.
**Update at the end of every task.**

Owners are from `CLAUDE.md`. "Blocked on" names a person or an external
thing, not a task.

**Last updated:** 2026-09-17 · 258 passing, 7 skipped (5 need an Electron host, 2 need `SIMBA_LIVE_TESTS=1`) · full suite 288s

---

## Where the project actually is

The walking skeleton runs end to end: Electron window up, backend attached to
its hidden site view over CDP, a task driven from the overlay through the
contract to a real page and back. It does that on **three** flows — two
replicas we wrote, and one live public site.

It *completes* on the live one with the hardcoded plan: five steps, no model,
choosing two stations from a dropdown and a date from a calendar the
accessibility tree does not know exist. Two recorded timings: 46.1s on
2026-09-08 (EVALUATION.md), and 54s on 2026-09-09 re-verifying against the
stricter success condition — `Departure Date` holding `15-10-2026`,
`travelDate: "2026-10-15"` on the wire, one train back. The 54s run is
recorded only here, not in EVALUATION.md. **Neither has been repeated since
2026-09-09**, so whether the live flow still completes today is not known.
The live search page itself still serializes the same way: re-read once on
2026-09-17, 18 elements, 4 unnamed, 3 dead links — identical to 2026-09-07.

**With the LLM it produced a wrong answer once, and that has been closed
off** — a real timetable for `2026-09-15` against a goal naming `2026-10-15`,
reported as `task.completed` (EVALUATION.md, case 6). The success condition
can now check the date, a floating panel states which month it shows, and a
durability lapse ends the run.

**The confirming LLM run has still not been made.** STATUS.md has said it was
blocked on quota since 2026-09-09. That was true on the day — 17 of 20
requests spent — but the quota is per day, and eight days have passed with no
LLM transcript in `logs/` since 2026-09-09. **It is not blocked on quota now;
it is simply not done.** See *The run that is owed* below.

What the system cannot do is trust its own result. A field can read back
correctly at every check while the application submits something else, and no
DOM-level observation catches it — EVALUATION.md, *"The DOM is not the
application's state"*.

### Changed on 2026-09-17

- **The stuck screen has a way onward.** It had nothing to press. Now every
  ending — found an answer, done without one, failed, stuck — is rendered in a
  real browser by `frontend/test_terminal_states.py`, which fails if one has
  nothing to press or a button that goes nowhere.
- **The backend's half of the voice is under test.** `backend/orchestrator/voice.py`
  holds the backend's fixed strings, and `frontend/test_copy.py` now checks
  every plan's instructions, details and labels, and the mock's, against the
  same rules as `copy.ts`.
- **Wording** — "I'm done", "Ask for something new", "Stop this", one name
  ("Do something else") for the way back home, no colons on lead-ins, one
  presence sentence ("Give me a moment."), "Can you do this part? I'll carry
  on after.", "You asked me for these".
- **`Task.about`** replaces `Task.answers` and `Expectation.value_is`, and is
  required.
- **`history.offered`** is recorded in `CONTRACT.md` as pending ratification.

---

## The run that is owed

Three changes are verified everywhere they can be without a model and have
never been through a whole task with one.

| Question | Known | Unknown |
|---|---|---|
| Does the **promoted setback** change a run, not just one decision? | One call, same page state, same words moved above the element list: the model went from clicking search to addressing the date | Whether it holds across a run, and whether the model then does something that *works* rather than re-typing |
| Does **stating the visible month** change what the model picks? | The banner reads `IT IS SHOWING: 2026 September`, and `2026 October` after `Next Month`. Live-tested | Nothing. No model has seen it |
| Does a **held date** (`About.holds`, formerly `value_is`) make a real run fail rather than complete? | The exact failing snapshot fails in `test_success_conditions.py`; a correct hardcoded run completed with the equivalent check on 2026-09-09 | Whether a live LLM run on a wrong date ends in `help.requested` |

**The run to make.** Railways, LLM planner, one run, when 8+ requests are
free. `.scratch/rail_llm.py` drives it — **and `.scratch/` is gitignored**, so
that script exists only on the machine it was written on. Anyone else has to
recreate it.

**What each outcome means.**

- `help.requested` naming the departure date — the intended result. The held
  date did its job on a real run.
- `task.completed` **on the goal's date** — also a pass, and a better one: the
  model navigated the calendar, which it has never done.
- `task.completed` on any other date — the check is not wired the way the
  tests believe. That would be the most important thing to find.

**The prompt has not changed since 2026-09-09.** `voice.describe` was kept
word-for-word for that reason, so the run still measures what the three fixes
were tested against. The *code path* to the check has changed
(`Expectation.value_is` → `About.holds` + `loop.unmet`), which is one more
reason the run matters.

**Quota — uncertain.** STATUS.md has said 20 requests a day for
`gemini-3.1-flash-lite`, 2–3 runs. EVALUATION.md's configuration section says
the lite model was chosen for having a *workable* allowance, where
`gemini-3.6-flash` had 20 a day — and the 2026-09-05 ten-run benchmarks on the
lite model used well over 20 requests in a day. Both cannot be current. Check
the provider console before planning around either.

---

## Perception — Nahail · `backend/perception/`

**Done**
- `serialize` / `read`: page to numbered `Element` list, from the
  accessibility tree plus a DOM join for tag, `type` and `name`.
- Password inputs distinguishable from text inputs.
- Structural overlay detection (`overlays.py`), no ARIA dependency, with a
  **target-scoped rule**: anything overlapping the element a move is about to
  touch counts, at any size. `MIN_COVERAGE` still answers the page-level
  question.
- **Non-semantic interactivity** (`interactivity.py`): controls a framework
  renders as plain `li`/`div`/`span` with no role, found from `cursor:
  pointer` and from repeated sibling groups in floating panels. Flagged
  `inferred`, never confused with a declared role. Verified against the live
  railways dropdown, unmodified.
- **Qualifiers** on inferred elements: `previous month`, `next month`,
  `disabled`, `today`. Live-tested on the railways calendar.
- **Panel headings**: an inferred element carries what its floating panel says
  it shows, and `render_page` promotes it above the element list —
  `IT IS SHOWING: 2026 September.` Live-tested.
- **Content extraction** (`content.py`): headings with level, table rows
  paired to their column headers, label/value pairs, prominent values.
- Form values (`Element.value`), so a filled form is a different page from an
  empty one.
- One shared `DOMSnapshot` parse (`snapshot.py`) behind all three readers.
- Dead-link flagging (`href="#"`, `javascript:void(0)`).
- `SIMBA_OVERLAY_DETECTION` and `SIMBA_INFERRED_ROLES` ablation switches.
- Verified against two replicas and one live site. Re-read on 2026-09-17: the
  registration course page with its modal up gives 66 elements, 1 `OVERLAY`,
  65 `OCCLUDED`, 44 dead links; the billing results page 39 elements with
  `P/WITHIN → 14,382` paired; the live search page 18 elements. All three
  element counts match the ones recorded when each was first measured.

**In progress**
- Nothing.

**Blocked / open — needs Nahail's call**

1. **The DOM is not the application's state, and perception only reads the
   DOM.** The live date input read back `2026-10-15` correctly at every check
   while the application's own model held `""`. No defence found except
   driving the widget the way a person must. **The most important open item
   on this page.**
2. **A modal's content is skipped along with a dropdown's.** Nothing yet tells
   a dialog apart from a popup.
3. **Elements with no accessible name are unaddressable.** The railways search
   button has none; `Target("button", "")` works only because that page has
   exactly one unnamed button.
4. **A panel heading is found by class-name fragment** (`header`, `heading`,
   `title`, `caption`). A picker that names its header otherwise gets none,
   silently.
5. **Inference is confined to the first document.** Iframes are not read.
6. **Accordion expanded state is discarded.**
7. **`css_path` is positional**, recomputed every perceive; staleness is
   bounded, not zero.
8. **`value_for` returns the first pair with a label.** The railways results
   have two trains and the finding "Train" is only ever the first. For a goal
   that asks *which trains*, one train is a partial answer shown as a whole
   one. New on 2026-09-17; not fixed.
9. Page-side load features for the estimator: not started, correctly so.

---

## Orchestrator — Raham · `backend/orchestrator/`

**Done**
- Shared loop (`loop.py`): perceive, decide, present, act, verify, retry with
  a different strategy, setback re-plan, `help.requested`.
- Verification proven to have teeth — unit tests per failure mode plus
  end-to-end cases that cannot succeed.
- `HardcodedPlanner`, `LLMPlanner` and `TracePlanner` behind one execution
  path, asserted identical under injected failure.
- LLM provider interface: Anthropic and any OpenAI-compatible endpoint, key
  from `.env`, response validated, retry-once with the error fed back,
  rate-limit backoff, token and cost accounting.
- Trace memory in SQLite, keyed on role and label, replaying at zero model
  calls and correcting itself when a trace no longer fits.
- `page.preview` on demand.
- Three flows via `SIMBA_FLOW`: `registration`, `billing`, `railways`.
- **Durable verification**: a typed value must still be there at the next
  perceive. A lapse **ends the run** — the other way was tried on 2026-09-09
  and reverted the same day.
- **`Task.about`** (2026-09-17): one required declaration of the values a goal
  names (`holds`, checked whenever the run decides it has finished) and the
  values it asks for (`finds`, read along the way and shown). Replaces
  `Task.answers` and `Expectation.value_is`. A held value is checked even when
  a task has no `success` expectation, and never ends a run early on its own.
- **Findings end to end**: the billing run's `task.completed` carries `Your
  bill 14,382` and `Due 15-09-2026`, read on the results page and remembered
  onto the detail page. Tested for the first time on 2026-09-17.
- **`voice.py`** (2026-09-17): the stop button, the LLM/replay confirm button,
  the stuck suggestion, the stop reason, the trust captions and the move
  descriptions, in one place, checked by `frontend/test_copy.py`.
- **`press`** as a fourth operation. **Content-based success conditions**
  (`content_says`, `rows_at_least`). Refuses to act on a covered element.
  **`step.failed`** when a step is carried past. `ACTION_TIMEOUT_MS = 10s`.
  The railways date is computed from today.
- Drives its own headless Chromium or a real Electron hidden view.

**In progress**
- Nothing.

**Blocked / open**
- **The LLM run that is owed** — see the top. Not blocked on quota any more.
  Raham's to make.
- **A success condition still only checks what was declared.** `About` makes
  the question unavoidable; it does not make the answer right. `holds` is
  checked only on the final page, so a value typed on one page of a
  multi-page flow (the billing reference number) cannot be declared. And
  `finds` is not part of success: a billing run that never read the amount
  would complete with no findings rather than stop. Flagged, not decided.
- **The model cannot navigate a calendar**, as of the last run it made. The
  panel heading now states the month; whether that changes what it picks is
  unmeasured.
- **A move the LLM or replay chose reads as an order to the person** ("Click
  LAHORE CANTT.") and an unnamed element as "element 13". The same sentence is
  the model's history, so rewording it changes the prompt. Kept as is until
  the owed run is made. Flagged.
- **`task.completed.summary` is the goal plus the final URL.** Six tests read
  the URL out of it; the frontend no longer displays it. The contract's
  example shows a human sentence. Flagged.
- **Trace memory has never run against a live model.**
- **The JS-click fallback can click through a modal** with overlay detection
  off (10/10 runs, still passing). Flagged rather than decided.
- **`requires_confirmation` is always `true`.** Every step is confirmed, and
  nothing is ever sent that asks a person to confirm something irreversible,
  because nothing irreversible is ever attempted. Correct today; worth knowing
  it carries no information.
- Replay tuning: not started.

---

## Interface — Aly · `frontend/`

**Done**
- Electron + React + TypeScript + Vite, Tailwind, Zustand, Framer Motion.
- The window: site view covered by the React overlay at identical bounds,
  CDP on 9222 for the backend.
- Contract client over `shared/schema.ts` and `shared/envelope.ts`. Every
  backend-to-frontend type handled; `task.start`, `step.response`,
  `level.override` and `trust.requested` sent.
- The overlay: one centred column, the four states shown rather than
  described. Development view behind Ctrl+Shift+D.
- All three detail levels, described as data in `levels.ts`, animated as a
  fold. Ordered by density, not height.
- Manual level control with a lock that `load.updated` respects, and a notice
  on any change the user did not make — now always one of the two sentences
  in `copy.ts`, by direction.
- Overflow drops one level rather than growing a scrollbar.
- The trust panel.
- A quiet notice when a step failed and the run carried on.
- **A home screen**: a greeting, past goals as large cards, and the text box
  behind "Ask for something new".
- **Findings on screen**, on the step card and on the closing screen.
- **Every ending has a way onward** (2026-09-17). The stuck screen had none.
  All four endings rendered and pressed in `test_terminal_states.py`.
- **All interface copy in `copy.ts`**, and the component scan now catches any
  words, not only punctuated sentences. It had been passing `let it choose`,
  `Hide the page` and an image description.

**In progress**
- Nothing.

**Blocked / open — needs Aly**
- **The stuck screen promises something nothing does.** "Can you do this
  part? I'll carry on after." — but the backend has closed the socket, nothing
  resumes, and the person cannot see or reach the page they are being asked to
  act on: the site view is covered by the overlay by design. The wording was
  asked for; the behaviour behind it does not exist. **The most important open
  item on this page.**
- **"I'm done" and "Do something else" go to the same place.** Both call
  `startOver`. One destination under two names is the thing the rename fixed
  elsewhere.
- **The failed screen after pressing "Stop this"** reads "I couldn't finish
  this. / You asked me to stop." A choice the person made is presented as the
  assistant failing.
- **The stuck screen shows the technical reason** under the suggestion, e.g.
  `could not find 'Close' on the page`, in muted type. The skipped-step notice
  removed exactly this kind of text; the stuck screen kept it.
- **"I'm showing a bit more again."** is now also what an overflow drop says,
  and "again" is untrue when the level was never fuller before.
- **"Step 2 of 6"** uses a word `copy.ts`'s own rules forbid.
- **A found value is shown exactly as the page wrote it** — `15-09-2026`.
  Deliberately left as is.
- **Home screen history is stale after a task.** The home screen reached from
  a finished task shows the goals from before it; see `CONTRACT.md`.
- **A backend that dies mid-task leaves "Give me a moment." on screen
  forever**, with nothing to press. Not a contract ending, so the terminal
  test does not cover it.
- **Nothing chooses a level automatically** except `load.updated`, which only
  the mock sends.
- **The credential vault is not built.** Values arrive in `step.response`.
- Voice input is in the contract and unimplemented.

---

## Estimator — Nahail · `backend/estimator/`

**Done**
- Nothing, deliberately. Unblocked since the skeleton ran end to end.

**Blocked / open**
- Depends on perception's page-side load features, not started.
- The frontend already honours `load.updated` and the lock.

---

## Shared contract — all three owners · `shared/`, `CONTRACT.md`

**Done**
- `schema.py` and `schema.ts` mirror every message.
- `task.start.goal` is honoured.
- `step.failed` (2026-09-09) and `findings` (2026-09-15), additive.
- `history.offered` (2026-09-15), **recorded as pending ratification** on
  2026-09-17 with the WebSocket-over-HTTP reasoning and its two known costs.
- **No schema file changed on 2026-09-17.** `voice.py` and `About` are
  backend-internal.

**Blocked / open**
- `CONTRACT.md` is still **DRAFT** and has never been ratified. **Blocked on
  Nahail, Raham and Aly together.** Previous versions of this file said three
  message types had been added since it was written; it is two
  (`step.failed`, `history.offered`) plus the optional `findings` fields.
- `telemetry` is specified and nothing sends it.
- The `step.presented` example still labels its cancel button "Not now".
  Left alone: it is an example, and this task did not ask for the contract to
  change beyond `history.offered`.

---

## Evaluation · `EVALUATION.md`

**Done**
- Ten-run benchmarks before and after overlay detection; the overlay ablation;
  hardcoded vs LLM A/B; token and cost figures; **six** recorded cases of
  verification passing wrongly (previous versions of this file said four);
  the live-site screening, failed run and completing run; perception profiled
  on a live page.
- 2026-09-17: test counts, the copy test's mutation checks, the terminal
  test's control run against the previous `App.tsx`, and a re-read of all
  three sites' serializer output.

**Blocked / open**
- **The demo-model ablation could not run.** Blocked on a paid API key.
- No LLM run against the billing flow.
- No baseline for the LLM against a goal it has not seen.
- **The benchmark harness is not in the repository.** `.scratch/benchmark.py`,
  `.scratch/ablation.py` and `.scratch/rail_llm.py` produced every model
  number in EVALUATION.md, and `.scratch/` is gitignored.
- EVALUATION.md contains statements its own later entries contradict. Listed
  in its 2026-09-17 entry rather than edited out.

---

## Infrastructure

**Done**
- Two replicas plus one live read-only flow.
- `run.ps1` / `run.sh`: one command per flow, cleaned up on Ctrl+C.
- `tools/screen_site.py`, `tools/mock_backend.py`, `spike/`.
- 265 tests from the repo root with `python -m pytest`: 258 pass, 5 skip
  without an Electron host, 2 skip without `SIMBA_LIVE_TESTS=1`.
- `test_terminal_states.py` builds the overlay from source into `.scratch/`
  rather than testing `dist/`.

**Blocked / open**
- No CI.
- Nothing supervises the Electron host.
- `frontend/test_levels.py` still measures `dist/` and skips without it.
- **`ruff` and `black` are the stated conventions and are not installed** —
  not in `requirements-dev.txt`, not in the venv. Nothing in this repo has
  been checked by either.
- **The venv is Python 3.12.3**; `CLAUDE.md` says 3.11.
- `README.md` says 214 tests pass and gives `npm run dev` as the frontend
  command; `RUNNING.md` and the launchers use `npm start`. Not refreshed in
  this task.
