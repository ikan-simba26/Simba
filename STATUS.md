# Status

Per module: what is done, what is in progress, what is blocked and on whom.
**Update at the end of every task.**

Owners are from `CLAUDE.md`. "Blocked on" names a person or an external
thing, not a task.

**Last updated:** 2026-09-08 · 169 passing, 6 skipped (5 need an Electron host, 1 needs `SIMBA_LIVE_TESTS=1`)

---

## Where the project actually is

The walking skeleton runs end to end: Electron window up, backend attached to
its hidden site view over CDP, a task driven from the overlay through the
contract to a real page and back. It does that on **three** flows — two
replicas we wrote, and one live public site.

It now *completes* on the live one: five steps, forty-six seconds, no model,
choosing two stations from a dropdown and a date from a calendar that the
accessibility tree does not know exist.

What it cannot do is trust the result. The one live case examined closely had
a field reading back correctly while the application's own state was empty,
and perception has no way to see that. See **Perception**, item 1, and
EVALUATION.md 2026-09-08.

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
4. **Inference is confined to the first document.** Iframes arrive as further
   entries in the snapshot's `documents` and are not read.
5. **Accordion expanded state is discarded.** The AX tree reports
   `expanded: False` and `build_elements` drops it.
6. **`css_path` is positional.** An inferred element is addressed by an
   `nth-of-type` chain recomputed on every perceive, so staleness is bounded
   by the gap between perceiving and acting — but it is not zero.
7. Page-side load features for the estimator: not started, correctly so.

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
  perceive, not only the instant after typing.
- **`press`** as a fourth operation — arrow keys, Enter, Escape. Additive;
  `CONTRACT.md` and both schema files untouched.
- **Content-based success conditions**: `Expectation.content_says` and
  `rows_at_least`, so a task whose goal is to read something can say when it
  is done.
- Refuses to act on an element something is sitting on top of.
- `ACTION_TIMEOUT_MS = 10s` rather than Playwright's 30s.
- Drives its own headless Chromium or a real Electron hidden view.

**In progress**
- Nothing.

**Blocked / open**
- **A single failed step is invisible to the user.** The first setback
  increments a counter, records a note for the planner and continues, with no
  message to the frontend at all. `HardcodedPlanner` ignores setbacks, so the
  step is silently skipped and the trace is indistinguishable from success.
  This is how the first railways run was misdiagnosed for a day. **Needs a
  contract decision** — probably an `error` or a step-level outcome — so it is
  Raham's to propose and all three owners' to agree.
- **A durability lapse gives up rather than letting a planner recover.**
  Correct for the hardcoded path; an LLM told "commit the choice this time"
  might genuinely fix it. Revisit when the LLM path runs against a live site.
- **Trace memory has never run against a live model.** Replay needs none and
  is covered; the record-then-replay cycle on a real run is not. Blocked on
  API quota.
- **The JS-click fallback can click through a modal.** With overlay detection
  off it does so in 10/10 runs and the run still passes — open question,
  flagged rather than decided.
- **The railways plan is anchored to one date.** `MONTHS_AHEAD = 1` is only
  true while today is in September 2026. That is what a hardcoded plan is, but
  it means the flow expires.
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
  day against 4–5 per run. **Blocked on a paid API key.** Still the largest
  gap in the evaluation.
- No LLM run against the billing or railways flows, same quota block.
- No baseline for the LLM against a goal it has not seen.

---

## Infrastructure

**Done**
- Two replicas, structurally different by design, plus one live read-only
  flow.
- `tools/screen_site.py` — screen a site before pointing anything at it.
- `spike/` proves the Electron + CDP + Playwright arrangement.
- 175 tests from the repo root with `python -m pytest`; 5 Electron integration
  tests skip unless a host is running, and the live-site test needs
  `SIMBA_LIVE_TESTS=1`.

**Blocked / open**
- No CI. Tests run when someone runs them, and the Electron tests skip
  silently without a host, so a regression there would go unnoticed.
- Nothing supervises the Electron host. Start order matters — replica, host,
  backend — and a host that dies mid-task surfaces as a connection error.
- `frontend/test_levels.py` needs `npm run build` first and skips otherwise,
  so a stale `dist/` is measured rather than the current source.
