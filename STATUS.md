# Status

Per module: what is done, what is in progress, what is blocked and on whom.
**Update at the end of every task.**

Owners are from `CLAUDE.md`. "Blocked on" names a person or an external
thing, not a task.

**Last updated:** 2026-09-09 · 197 passing, 7 skipped (5 need an Electron host, 2 need `SIMBA_LIVE_TESTS=1`)

---

## Where the project actually is

The walking skeleton runs end to end: Electron window up, backend attached to
its hidden site view over CDP, a task driven from the overlay through the
contract to a real page and back. It does that on **three** flows — two
replicas we wrote, and one live public site.

It now *completes* on the live one with the hardcoded plan: five steps,
forty-six seconds, no model, choosing two stations from a dropdown and a date
from a calendar that the accessibility tree does not know exist.

**With the LLM it now runs to the end and gets the wrong answer.** It commits
both stations from the inferred options unprompted, then sets the date to the
15th of the month the picker opened on, is told so, re-plans, and searches
anyway — returning a real timetable for `2026-09-15` against a goal naming
`2026-10-15`, and reporting `task.completed`.

That is a **regression in outcome**, and it comes from a change made
deliberately: a durability lapse now hands the failure to the planner once
instead of ending the run. The mechanism works; the model does not use it.
Before the change the run stopped and said it was stuck, which was wrong
about the cause and right about the outcome. See EVALUATION.md 2026-09-09b —
this is the first plausible-but-wrong answer the system has produced, and it
is the failure mode that matters most.

What the system cannot do is trust its own result. A field can read back
correctly at every check while the application submits something else, and no
DOM-level observation catches it. That is a boundary of the approach rather
than a bug in it, and it is now stated as one — EVALUATION.md, *"The DOM is
not the application's state"*.

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
- **Qualifiers** on inferred elements, from the class tokens the class
  attribute was already being parsed for and throwing away: `previous month`,
  `next month`, `disabled`, `today`. Live-tested on the railways calendar —
  the two cells labelled `30` are told apart, and `Target("option", "15",
  qualifier="")` names the 15th of the month on screen.
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
4. **Nothing says which month a calendar is showing.** Qualifiers fixed the
   ambiguity *within* a grid — every duplicate day is now separated, and the
   15th of October is expressible. What no element carries is the grid's own
   month: `button 'September'` and `button 'October'` are just two more
   buttons, and both LLM runs clicked the 15th without comparing either to
   the goal. A panel-level qualifier, or a heading promoted the way an
   overlay banner is, would be the next thing to try.
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
  site, both times correctly. A lapse is handed to the planner once as a
  setback before the run ends.
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
- **A run can now report success on a wrong answer.** The single most
  important open item on this page. The LLM run searched `2026-09-15` against
  a goal naming `2026-10-15`, got two real trains, and reported
  `task.completed`. Three things had to line up and all three are open:
  the model ignored a well-formed setback; nothing tells it which month a
  calendar is showing; and the success condition cannot see a date at all.
- **`Expectation` has no vocabulary for a form value.** `Snapshot` has
  carried `values` since 2026-09-08 and no expectation can test them. A task
  whose goal names a value should be able to require the form still holds it
  at the end — the cheapest of the three fixes above, and the one that would
  have caught this. **Blocked on quota** to test against the case that
  motivated it.
- **The model cannot navigate a calendar.** It clicked the 15th of the month
  the picker opened on in both runs, with `button 'Next Month'` in its list
  and October in its goal, and did so again after being told the date was
  wrong. Needs re-testing on the demo model before anything is concluded.
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

**In progress**
- Nothing.

**Blocked / open — needs Aly**
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
  schema files and CONTRACT.md carry it. `strategies_tried` is `0` when the
  step's own actions succeeded and the failure was found afterwards.

**Blocked / open**
- `CONTRACT.md` is still marked **DRAFT** and has never been ratified in a
  session with all three owners, which it requires before being treated as
  frozen. **Blocked on Nahail, Raham and Aly together.**
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
- **The setback-prominence fix is unverified end to end.** Moving the setback
  above the element list changed the model's answer at the decision that
  failed, measured with one call. Whether it changes the *run* needs a full
  run and the day's quota is spent.

---

## Infrastructure

**Done**
- Two replicas, structurally different by design, plus one live read-only
  flow.
- `tools/screen_site.py` — screen a site before pointing anything at it.
- `spike/` proves the Electron + CDP + Playwright arrangement.
- 204 tests from the repo root with `python -m pytest`; 5 Electron integration
  tests skip unless a host is running, and the two live-site tests need
  `SIMBA_LIVE_TESTS=1`.

**Blocked / open**
- No CI. Tests run when someone runs them, and the Electron tests skip
  silently without a host, so a regression there would go unnoticed.
- Nothing supervises the Electron host. Start order matters — replica, host,
  backend — and a host that dies mid-task surfaces as a connection error.
- `frontend/test_levels.py` needs `npm run build` first and skips otherwise,
  so a stale `dist/` is measured rather than the current source.
