# Status

Per module: what is done, what is in progress, what is blocked and on whom.
**Update at the end of every task.**

Owners are from `CLAUDE.md`. "Blocked on" names a person or an external
thing, not a task.

**Last updated:** 2026-09-07 · 127 passing, 5 skipped without an Electron host · `97f2891`

---

## Where the project actually is

The walking skeleton runs end to end: Electron window up, backend attached to
its hidden site view over CDP, a task driven from the overlay through the
contract to a real page and back. It does that on **three** flows — two
replicas we wrote, and one live public site.

The live site is where it stops working, and that is now the most important
thing on this page. See **Perception**, and EVALUATION.md 2026-09-07.

---

## Perception — Nahail · `backend/perception/`

**Done**
- `serialize` / `serialize_async`: page to numbered `Element` list, from the
  accessibility tree plus a DOM join for tag, `type` and `name`.
- Password inputs distinguishable from text inputs.
- Structural overlay detection (`overlays.py`), no ARIA dependency.
- Dead-link flagging (`href="#"`, `javascript:void(0)`).
- `SIMBA_OVERLAY_DETECTION` ablation switch.
- Verified against two structurally different replicas.

**In progress**
- Nothing.

**Blocked / open — needs Nahail's call.** In rough order of how much they
matter, which changed after the live-site run:

1. **Choices that are not controls are invisible.** On the live railways
   search, six station options are on screen and perception reports zero: they
   are Element UI `li`/`span` with no role, no tabindex and no aria, reaching
   the accessibility tree only as `StaticText`. `INTERACTIVE_ROLES` cannot
   match them. **This alone makes the flow impossible** and the pattern is
   common across enterprise SPAs.
2. **Read-only values are not perceivable.** Only interactive elements are
   serialized, so the amount due on the billing replica — and every train in a
   results table — never reaches a planner. Blocks lookup-shaped tasks and
   makes success conditions inexpressible.
3. **Small blockers are missed.** `MIN_COVERAGE = 0.30` assumes a modal. It
   misses the billing replica's cookie banner (6.6% of the viewport, blocking
   six real links) and the railways dropdown (~220x180) that intercepted a
   fill and timed the loop out.
4. **Elements with no accessible name are unaddressable.** The railways search
   button has none; `Target("button", "")` matches every unnamed button on the
   page and is disambiguated only by ordinal.
5. **Accordion expanded state is discarded.** The AX tree reports
   `expanded: False` and `build_elements` drops it.
6. Page-side load features for the estimator: not started, correctly so.

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
- Three flows via `SIMBA_FLOW`: `registration`, `billing`, `railways`.
- Drives its own headless Chromium or a real Electron hidden view.

**In progress**
- Nothing.

**Blocked / open**
- **Verification checks the moment, not the outcome.** On the live site a
  fill was read straight back, verified, and had evaporated one step later,
  because the widget clears itself on blur. The loop has no notion of a value
  that must still be there when it is used. Fourth recorded case of
  verification passing wrongly.
- **No way to express "press a key".** `Operation` is fill, click or select.
  Keyboard selection is the only route through several real widgets.
- **Trace memory has never run against a live model.** Replay needs none and
  is covered; the record-then-replay cycle on a real run is not. Blocked on
  API quota.
- **The JS-click fallback can click through a modal.** With overlay detection
  off it does so in 10/10 runs and the run still passes — open question,
  flagged rather than decided.
- Replay tuning (when to prefer a trace over fresh planning) and the retry
  policy for real sites: not started.

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
  verification passing wrongly; the live-site screening and run.

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
- 132 tests from the repo root with `python -m pytest`; 5 Electron
  integration tests skip unless a host is running.

**Blocked / open**
- No CI. Tests run when someone runs them, and the Electron tests skip
  silently without a host, so a regression there would go unnoticed.
- Nothing supervises the Electron host. Start order matters — replica, host,
  backend — and a host that dies mid-task surfaces as a connection error.
- `frontend/test_levels.py` needs `npm run build` first and skips otherwise,
  so a stale `dist/` is measured rather than the current source.
