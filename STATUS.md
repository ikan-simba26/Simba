# Status

Per module: what is done, what is in progress, what is blocked and on whom.
**Update at the end of every task.**

Owners are from `CLAUDE.md`. "Blocked on" names a person or an external
thing, not a task.

**Last updated:** 2026-09-15 · 224 passing, 7 skipped (5 need an Electron host, 2 need `SIMBA_LIVE_TESTS=1`)

---

## Where the project actually is

The walking skeleton runs end to end: Electron window up, backend attached to
its hidden site view over CDP, a task driven from the overlay through the
contract to a real page and back. It does that on **three** flows — two
replicas we wrote, and one live public site.

It now *completes* on the live one with the hardcoded plan: five steps,
fifty-four seconds, no model, choosing two stations from a dropdown and a date
from a calendar that the accessibility tree does not know exist. Re-verified
2026-09-09 against the stricter success condition — `Departure Date` holding
`15-10-2026`, `travelDate: "2026-10-15"` on the wire, one train back.

**With the LLM it produced a wrong answer, and that has been closed off.** It
commits both stations from the inferred options unprompted, then set the date
to the 15th of the month the picker opened on and searched anyway — returning
a real timetable for `2026-09-15` against a goal naming `2026-10-15`, and
reporting `task.completed`. The first plausible-but-wrong answer the system
has produced, and the failure mode that matters most (EVALUATION.md, case 6).

Three things had to line up. Two are now fixed: the success condition can
test a field's value, so that run would fail today; and a floating panel
states which month it is showing instead of leaving it in an unremarkable
button. The third — continuing past a durability lapse — was a change made
that morning and reverted the same evening. **A lapse ends the run again.**

What remains unmeasured is whether any of it changes what the model does.
**The confirming LLM run has not been made**: 17 of the day's 20 requests were
already spent on the runs that found the problem, and a run needs 6–7. Not
started rather than started and abandoned — a partial run would burn the quota
without answering anything. See *Waiting on quota* below for the three
questions it settles and what to look for.

What the system cannot do is trust its own result. A field can read back
correctly at every check while the application submits something else, and no
DOM-level observation catches it. That is a boundary of the approach rather
than a bug in it, and it is now stated as one — EVALUATION.md, *"The DOM is
not the application's state"*.

---

## Waiting on quota

Three changes are verified everywhere they can be without a model and have
never been through a whole task with one. This is the single outstanding
piece of evidence in the project right now, and it is one run.

| Question | Known | Unknown |
|---|---|---|
| Does the **promoted setback** change a run, not just one decision? | One call, same page state, same words moved above the element list: the model went from clicking search to addressing the date | Whether it holds across a run, and whether the model then does something that *works* rather than re-typing |
| Does **stating the visible month** change what the model picks? | The banner reads `IT IS SHOWING: 2026 September`, and `2026 October` after `Next Month`. Live-tested | Nothing. No model has seen it |
| Does **`value_is`** make a real run fail rather than complete? | The exact failing snapshot fails in `test_success_conditions.py`; a correct hardcoded run still completes with it | Whether a live LLM run on a wrong date ends in `help.requested` |

**The run to make.** Railways, LLM planner, one run, when 8+ requests are
free. `.scratch/rail_llm.py` drives it.

**What each outcome means.**

- `help.requested` naming the departure date — the intended result. `value_is`
  did its job on a real run.
- `task.completed` **on the goal's date** — also a pass, and a better one: the
  model navigated the calendar, which it has never done.
- `task.completed` on any other date — **`value_is` is not wired the way the
  tests believe**, and the unit tests are testing a snapshot the loop does not
  actually build. That would be the most important thing to find.

Quota is 20 requests a day for `gemini-3.1-flash-lite`, which is 2–3 runs.
Counting what has been spent: `python -c "..."` over `logs/llm-<date>-*.jsonl`,
one request per record carrying a `user` key.

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
- **Qualifiers** on inferred elements, from the class tokens the class
  attribute was already being parsed for and throwing away: `previous month`,
  `next month`, `disabled`, `today`. Live-tested on the railways calendar —
  the two cells labelled `30` are told apart, and `Target("option", "15",
  qualifier="")` names the 15th of the month on screen.
- **Panel headings**: an inferred element carries what the floating panel it
  sits in says it is showing, and `render_page` promotes it above the element
  list — `IT IS SHOWING: 2026 September.` Live-tested, and it follows the
  month when `Next Month` is pressed.
- **Content extraction** (`content.py`): headings with level, table rows
  paired to their column headers, label/value pairs, prominent values. The
  second output channel.
- Form values (`Element.value`), so a filled form is a different page from an
  empty one.
- One shared `DOMSnapshot` parse (`snapshot.py`) behind all three readers.
- Dead-link flagging (`href="#"`, `javascript:void(0)`).
- `SIMBA_OVERLAY_DETECTION` and `SIMBA_INFERRED_ROLES` ablation switches.
- Verified against two replicas and one live site.

**In progress**
- Nothing.

**Blocked / open — needs Nahail's call.** Reordered after the live run; the
top three items from the previous entry are now done.

1. **The DOM is not the application's state, and perception only reads the
   DOM.** The live date input read back `2026-10-15` correctly at every
   check while the application's own model held `""` — the outgoing request
   proves it. A framework keeps its truth in JavaScript, and every signal
   available here agrees with the DOM and is wrong together. No defence
   found except driving the widget the way a person must. **The most
   important open item on this page**, and there is no reason to think the
   date field is the only instance.
2. **A modal's content is skipped along with a dropdown's.** Content
   extraction excludes floating panels because a date picker is not content;
   nothing yet tells a dialog apart from a popup. The first task that needs
   to read a modal has to fix this.
3. **Elements with no accessible name are unaddressable.** The railways
   search button has none; `Target("button", "")` is disambiguated only by
   ordinal, and worked only because that page has exactly one unnamed button.
   Inference deliberately drops unlabelled candidates for the same reason, so
   an icon-only control found by cursor is still not reportable.
4. **A panel heading is found by class-name fragment.** `header`, `heading`,
   `title`, `caption`. A picker that names its header something else gets no
   heading, silently, and the calendar is ambiguous again. The list will need
   extending and the only way to find out is a page where it fails.
5. **Inference is confined to the first document.** Iframes arrive as further
   entries in the snapshot's `documents` and are not read.
6. **Accordion expanded state is discarded.** The AX tree reports
   `expanded: False` and `build_elements` drops it.
7. **`css_path` is positional.** An inferred element is addressed by an
   `nth-of-type` chain recomputed on every perceive, so staleness is bounded
   by the gap between perceiving and acting — but it is not zero.
8. Page-side load features for the estimator: not started, correctly so.

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
- `page.preview` on demand: capture of the covered site view plus the bounds
  of the element the current move targets.
- Three flows via `SIMBA_FLOW`: `registration`, `billing`, `railways`. The
  railways flow **completes on the live site**, 5/5 steps, 46s, no model.
- **Durable verification**: a typed value must still be there at the next
  perceive, not only the instant after typing. Has fired twice on the live
  site, both times correctly. A lapse **ends the run** — the other way was
  tried on 2026-09-09 and reverted the same day.
- **`Expectation.value_is`**: a success condition can require a named field to
  hold a given value, read from the values `Snapshot` already carries. The
  railways task uses it, so the run that searched the wrong date would now
  fail instead of completing. Confirmed not to reject a *correct* run: the
  hardcoded flow still completes with it (2026-09-09, 5/5, 54s).
- **`press`** as a fourth operation — arrow keys, Enter, Escape. Additive;
  `CONTRACT.md` and both schema files untouched.
- **Content-based success conditions**: `Expectation.content_says` and
  `rows_at_least`, so a task whose goal is to read something can say when it
  is done.
- Refuses to act on an element something is sitting on top of.
- **`step.failed`**: a step that failed and was carried past says so. The loop
  no longer absorbs a setback in silence.
- `ACTION_TIMEOUT_MS = 10s` rather than Playwright's 30s.
- The railways date is computed from today, so the flow does not expire.
- Drives its own headless Chromium or a real Electron hidden view.

**In progress**
- Nothing.

**Blocked / open**
- **A success condition still has to be remembered.** `value_is` closes the
  railways case, and it is per-field and per-plan: a task whose author does
  not write one is exactly as blind as `RAILWAYS_TASK` was for four days. The
  version this eventually needs is a task that states what it was asking for
  and is checked against it without anyone having to remember. Raham's to
  propose.
- **The model cannot navigate a calendar.** It clicked the 15th of the month
  the picker opened on in both runs, with `button 'Next Month'` in its list
  and October in its goal, and did so again after being told the date was
  wrong. The panel heading now states the month; **whether that changes what
  it picks is unmeasured.**
- **Three changes are unverified end to end.** The promoted setback, the
  panel heading, and `value_is` in a live run. All three are tested at the
  unit and page level; none has been through a whole task with a model.
  **Blocked on quota** — see *Waiting on quota* at the top for the run to
  make and what each outcome would mean.
- **Trace memory has never run against a live model.** Replay needs none and
  is covered; the record-then-replay cycle on a real run is not. Blocked on
  API quota.
- **The JS-click fallback can click through a modal.** With overlay detection
  off it does so in 10/10 runs and the run still passes — open question,
  flagged rather than decided.
- Replay tuning (when to prefer a trace over fresh planning): not started.

---

## Interface — Aly · `frontend/`

**Done**
- Electron + React + TypeScript + Vite, Tailwind, Zustand, Framer Motion.
- The window: site view covered by the React overlay at identical bounds,
  CDP on 9222 for the backend.
- Contract client over `shared/schema.ts` and `shared/envelope.ts`. Every
  backend-to-frontend type handled; `task.start`, `step.response`,
  `level.override` and `trust.requested` sent; per-connection `seq` tracked
  with a warning on a gap.
- The overlay: one centred column, the four states shown rather than
  described, nothing else on screen. Development view behind Ctrl+Shift+D.
- All three detail levels, described as data in `levels.ts`, with the change
  between them animated as a fold. Ordered by density, not height.
- Manual level control with a lock that `load.updated` respects, and a notice
  on any change the user did not make.
- Overflow drops one level rather than growing a scrollbar.
- The trust panel: an annotated still of the real page with the target ringed.
- A quiet notice when a step failed and the run carried on past it
  (`step.failed`). The muted card the level notice uses, not the stuck screen:
  the run is still going, and dressing a recovered setback up as a failure
  would teach people to distrust a system that is working.
- **A home screen**: a greeting, and the goals this person has asked for
  before as large cards, with the text box behind "Something else". No
  history means the box directly.
- **Findings on screen**: the value the goal was about, larger than the
  instruction beside it, on the step card and again on the closing screen.
- **A closing screen that answers the question** rather than saying "Done.",
  with one action to finish and one to start something else.
- **Presence between steps** in the same plain voice as everything else,
  instead of an unlabelled pulse.
- **All interface copy in `copy.ts`**, with `test_copy.py` failing if a
  component writes its own sentence or if one situation can produce two.

**In progress**
- Nothing.

**Blocked / open — needs Aly**
- **The voice is set in two places.** `copy.ts` holds the interface's words
  and is enforced by a test. The instruction on each step and the label on
  each button come from the backend's plans, where nothing checks them — a new
  plan brings its own wording and can be as inconsistent as its author. The
  wording review in the 2026-09-15 report lists what that has already cost.
- **A found value is shown exactly as the page wrote it.** The billing due
  date reads `15-09-2026` on screen because that is what the table says.
  Formatting it would mean inventing, so nothing does — but `15-09-2026` is
  not plain language and this audience is the one least able to parse it.
- **Nothing chooses a level automatically** except `load.updated`, which only
  the mock sends. Every real run sits at level 2 unless the user moves it.
- **The credential vault is not built.** Values arrive in `step.response`
  rather than from a store the model cannot see, though `resolve_value`
  already refuses to fill a password from anything a planner supplied.
- Voice input (`input_mode: "voice"`) is in the contract and unimplemented.
- `frontend/electron/main.ts` and the window layout are Aly's to review.

---

## Estimator — Nahail · `backend/estimator/`

**Done**
- Nothing, deliberately. `CLAUDE.md` defers it until the skeleton runs end to
  end. It now does, so this is unblocked as of this entry.

**Blocked / open**
- Depends on perception's page-side load features, not started.
- The frontend already honours `load.updated` and the level lock, so the
  estimator has a working consumer waiting for it.

---

## Shared contract — all three owners · `shared/`, `CONTRACT.md`

**Done**
- `schema.py` and `schema.ts` mirror every message; `envelope.py` / `.ts`
  build the envelope in one place.
- `task.start.goal` is honoured rather than discarded, and `CONTRACT.md` says
  so explicitly.
- **`step.failed`** added 2026-09-09 — additive, no rename, no removal. Both
  schema files and CONTRACT.md carry it.
- **`findings`** on `step.presented` and `task.completed`, added 2026-09-15.
  Additive optional fields, which `CONTRACT.md` permits without ceremony.
- **`history.offered`** added 2026-09-15 — a **new message type**, which is
  more than an additive field. Sent unprompted when the socket opens, so the
  home screen has something to show. Additive in effect, and still a change to
  the contract's shape: **needs ratifying with the other two owners.**

**Blocked / open**
- `CONTRACT.md` is still marked **DRAFT** and has never been ratified in a
  session with all three owners, which it requires before being treated as
  frozen. **Blocked on Nahail, Raham and Aly together**, and now overdue:
  three message types have been added since it was written.
- `telemetry` is specified and nothing sends it. It is the estimator's other
  input channel.

---

## Evaluation · `EVALUATION.md`

**Done**
- Ten-run benchmarks before and after overlay detection; the overlay ablation;
  hardcoded vs LLM A/B; token and cost figures; four recorded cases of
  verification passing wrongly; the live-site screening, the failed run and
  the completing run; perception profiled on a live page.
- The 2026-09-07 entry carries a **correction**: its account of why the first
  live run failed was wrong in both of its parts, and the corrected version is
  kept beside the original rather than replacing it.

**Blocked / open**
- **The demo-model ablation could not run.** Free tier allows 20 requests a
  day against 4–6 per run. **Blocked on a paid API key.** Still the largest
  gap in the evaluation, and now larger: the calendar failure is exactly the
  kind of thing a stronger model may simply not have.
- No LLM run against the billing flow, same quota block.
- No baseline for the LLM against a goal it has not seen.
- **Three fixes are unverified against a model.** The promoted setback (one
  call says it changes that decision), the panel heading, and
  `Expectation.value_is`. Each is tested where it can be — unit tests, and
  live page tests that need no model — and none has been through a whole run.
  **Blocked on quota.**

---

## Infrastructure

**Done**
- Two replicas, structurally different by design, plus one live read-only
  flow.
- `tools/screen_site.py` — screen a site before pointing anything at it.
- `spike/` proves the Electron + CDP + Playwright arrangement.
- 231 tests from the repo root with `python -m pytest`; 5 Electron integration
  tests skip unless a host is running, and the two live-site tests need
  `SIMBA_LIVE_TESTS=1`.

**Blocked / open**
- No CI. Tests run when someone runs them, and the Electron tests skip
  silently without a host, so a regression there would go unnoticed.
- Nothing supervises the Electron host. Start order matters — replica, host,
  backend — and a host that dies mid-task surfaces as a connection error.
- `frontend/test_levels.py` needs `npm run build` first and skips otherwise,
  so a stale `dist/` is measured rather than the current source.
