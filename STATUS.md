# Status

Per module: what is done, what is in progress, what is blocked and on whom.
**Update at the end of every task.**

Owners are from `CLAUDE.md`. "Blocked on" names a person or an external
thing, not a task.

**Last updated:** 2026-09-06 · 101 tests passing · `12dcc82`

---

## Perception — Nahail · `backend/perception/`

**Done**
- `serialize` / `serialize_async`: page to numbered `Element` list, from the
  accessibility tree plus a DOM join for tag, `type` and `name`.
- Password inputs distinguishable from text inputs.
- Structural overlay detection (`overlays.py`) — no ARIA dependency. Modal
  detected on the registration replica; elements behind it flagged
  `occluded`.
- Dead-link flagging (`href="#"`, `javascript:void(0)`).
- `SIMBA_OVERLAY_DETECTION` ablation switch.
- Verified against a second, structurally different replica (billing).

**In progress**
- Nothing.

**Blocked / open — needs Nahail's call**
- **Cookie-banner-shaped blockers are missed.** `MIN_COVERAGE = 0.30`
  assumes a modal. The billing banner covers 6.6% and blocks six real footer
  links, reported as not occluded. Fix is in the gate, not the occlusion
  test.
- **Accordion expanded state is discarded.** The AX tree reports
  `expanded: False`; `build_elements` drops it. A planner cannot tell a
  collapsed section from an expanded one.
- **Read-only values are not perceivable.** Only interactive elements are
  serialized, so the amount due on the billing replica — the thing that flow
  exists to find — never reaches a planner. Blocks any lookup-shaped task.
- Page-side load features for the estimator: not started, and correctly so
  (see Current phase in `CLAUDE.md`).

---

## Orchestrator — Raham · `backend/orchestrator/`

**Done**
- Shared loop (`loop.py`): perceive, decide, present, act, verify, retry with
  a different strategy, setback re-plan, `help.requested`.
- Verification proven to have teeth — unit tests per failure mode plus
  end-to-end cases that cannot succeed.
- `HardcodedPlanner` and `LLMPlanner` behind one execution path, asserted
  identical under injected failure.
- LLM provider interface: Anthropic and any OpenAI-compatible endpoint,
  chosen by env var, key from `.env`.
- Response validation on both provider paths, retry-once with the error fed
  back, then `help.requested`.
- Rate-limit backoff honouring the server's stated delay.
- Token and cost instrumentation per call and per run.
- Trace memory: SQLite, keyed on role and label, replay at zero model calls,
  self-correcting when a trace no longer fits.
- Runs on two sites (`SIMBA_FLOW`), hardcoded plans for both.

**In progress**
- Nothing.

**Blocked / open**
- **Trace memory has never run against a live model.** Replay itself needs no
  model and is covered, but the record-then-replay cycle on a real run is
  unproven. Blocked on API quota.
- **The JS-click fallback can click through a modal.** With overlay detection
  off it does so in 10/10 runs and the run still passes. Whether strategy 1
  should refuse an element perception knows is occluded is an open design
  question — **flagged, not decided**.
- Trace replay is not wired into `app.py`; `TracePlanner` exists and is
  tested but nothing constructs it in the running server.
- Replay, LLM interface hardening beyond one provider pair, and the retry
  policy for real sites: not started.

---

## Interface — Aly · `frontend/`

**Done**
- Nothing. Directory is a placeholder.

**In progress**
- Nothing.

**Blocked / open — needs Aly**
- Not started. `tools/mock_backend.py` plays a full scripted task over a real
  WebSocket, so the overlay can be built now with no backend running.
- `shared/schema.ts` and `shared/envelope.ts` are current and type-check
  under `--strict`.
- The three detail levels, trust panel and credential vault are explicitly
  deferred until the skeleton runs end to end (`CLAUDE.md`).

---

## Estimator — Nahail · `backend/estimator/`

**Done**
- Nothing, deliberately. `CLAUDE.md` defers it until the skeleton runs end to
  end.

**Blocked / open**
- Waiting on the walking skeleton being accepted as complete. The loop does
  not emit `load.updated` and should not yet.
- Depends on perception's page-side load features, also not started.

---

## Shared contract — all three owners · `shared/`, `CONTRACT.md`

**Done**
- `schema.py` and `schema.ts` mirror every message in `CONTRACT.md`.
- `envelope.py` / `.ts` build the envelope in one place, used by the
  orchestrator and the mock backend.

**Blocked / open**
- `CONTRACT.md` is still marked **DRAFT**. It has never been ratified in a
  session with all three owners, which `CONTRACT.md` itself requires before
  it is treated as frozen. **Blocked on Nahail, Raham and Aly together.**

---

## Evaluation · `EVALUATION.md`

**Done**
- Ten-run benchmarks before and after overlay detection.
- Hardcoded vs LLM A/B on the registration replica.
- Token and cost figures.

**Blocked / open**
- **The demo-model ablation could not run.** Free tier allows 20 requests a
  day against 4–5 per run. One run attempted per demo condition, neither
  completed. Whether a stronger model absorbs the overlay-detection gain is
  unknown. **Blocked on a paid API key.** This is the largest gap in the
  evaluation.
- No baseline for the LLM against an unseen goal.
- No second-site LLM run (billing), same quota block.

---

## Infrastructure

**Done**
- Two replicas, structurally different by design.
- `spike/` proves the Electron + CDP + Playwright architecture.
- 101 tests, run from the repo root with `python -m pytest`.

**Blocked / open**
- Electron and the backend have never been connected. The spike drives a
  hidden view over CDP and the orchestrator drives its own Chromium; nothing
  yet points the orchestrator at the Electron view. That is the next
  integration and nobody is on it.
- No CI. Tests only run when someone runs them.
