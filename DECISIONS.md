# Decisions

One entry per decision that would be expensive to reverse or surprising to
inherit. Each records what was decided, what else was considered, why this
one won, and when.

**Append here whenever a decision of that kind is made.** If a design question
comes up that the task did not ask about, it goes in the task report under
"flagged for review" *and*, once settled, here.

Newest last.

---

## Element ids, not selectors, across the boundary

**Date:** 2026-09-04 (`4a5bb27`, the rule predates it in CLAUDE.md)

**Decision.** Perception numbers every interactive element and the planner
answers with an integer. `loop.resolve` turns that integer back into a
Playwright locator. No selector, XPath, or element text ever crosses from a
planner into execution.

**Alternatives.** Let the planner emit a CSS selector, which is what most
browser agents do and what a model is most fluent at. Or let it emit the
element's visible text and match on that.

**Why this.** A selector is an assertion about the DOM that the planner cannot
verify and the backend cannot safely check — a wrong one silently matches the
wrong thing, and a model-authored one is an injection surface. An integer is
meaningless outside the list perception just produced, so an out-of-range
answer is caught immediately (`LLMPlanner._choose`) instead of acting on the
wrong element. It also means the planner can be swapped without touching
execution.

**Cost.** Ids are per-perception and shift between page loads, which is why
traces cannot store them (see below).

---

## The site view is covered, not hidden

**Date:** 2026-09-05 (`0fb5275`)

**Decision.** The `WebContentsView` holding the real site stays
`setVisible(true)` at full 1280x800 bounds, and the overlay view is added
after it at identical bounds so it covers it completely.

**Alternatives.** `setVisible(false)`, the obvious way to hide a view.
Positioning it outside the parent's bounds. Sizing it `0x0`.

**Why this.** Measured, 20 captures per condition:

| Approach | Viewport | Screenshots | Click |
|---|---|---|---|
| Covered by overlay | 1280x800 | 20/20 | works |
| `setVisible(false)` | 1280x800 | 2/5 | works |
| Outside the parent | collapses to 0x0 | 0/5 | fails |

Chromium keeps compositing a covered view but does not reliably repaint an
invisible one, so screenshots — which `page.preview` and `trust.requested`
depend on — time out about half the time. Anything sized or positioned
outside its parent collapses the renderer viewport to 0x0, which breaks
clicking entirely.

**Cost.** Occlusion depends on Electron's documented z-order rather than an
explicit visibility API, so a future layout change could expose the site view
without any error being raised.

---

## Structural overlay detection, not ARIA roles

**Date:** 2026-09-05 (`3d1bad1`)

**Decision.** `perception/overlays.py` decides what is covering the page from
layout — position, stacking, and how much of the viewport it covers — and
ignores `role="dialog"` and `aria-modal` completely.

**Alternatives.** Trust ARIA. Or hit-test every element with
`elementFromPoint`.

**Why this.** Real portals ship modals as plain positioned `div`s with no
dialog semantics; the registration replica is deliberately one of them, and
the accessibility tree says nothing about it. Trusting ARIA would mean
detecting overlays on exactly the sites that do not need help. Hit-testing
per element would be correct but costs a round trip each, against one
`DOMSnapshot` for the whole document.

**Cost.** The blocker gate is a coverage threshold (`MIN_COVERAGE = 0.30`),
which assumes a blocker is modal-shaped. Measured against the billing
replica on 2026-09-06, the cookie banner covers 6.6% and is missed, while
genuinely blocking six footer links. **Open** — see EVALUATION.md.

---

## Planning history capped at the last 10 actions

**Date:** 2026-09-05 (`4d0bcaf`)

**Decision.** The goal is always sent in full; the list of completed actions
is trimmed to the last 10, and the trim is stated in the prompt rather than
silent.

**Alternatives.** Unbounded history. Summarising older actions.

**Why this.** Unbounded is exact but grows cost and latency every step and
eventually meets the context window. Summarising costs an extra model call
per summary and can quietly rewrite what happened, which is a bad trade in a
verification path — the whole point is knowing what actually occurred. A flat
window is predictable and cheap.

**Cost.** A task needing to recall something from more than 10 actions ago
will fail in a way that looks like bad planning. Revisit if that shows up.

---

## One execution and recovery path for every planner

**Date:** 2026-09-05 (`b99a075`)

**Decision.** Every planner produces a `Move`; `loop.run_task` does
presenting, acting, verifying, the strategy-0-then-1 retry, and
`help.requested`. Planners differ only in which `Move` comes next.

**Alternatives.** Let each planner own its loop, which is what the hardcoded
and LLM paths had grown into independently.

**Why this.** With two loops, an A/B between planners compares two
implementations rather than two planners — the thing the experiment is for
is confounded by the thing it is measured with. `test_shared_recovery.py`
asserts both produce identical message sequences under the same injected
failure.

**Cost.** A planner with a genuinely different execution need — one that
batches, or acts without confirmation — will have to widen the shared path
rather than route around it.

---

## Traces keyed on role and label, never element ids

**Date:** 2026-09-05 (`9848ebe`, `e562de7`)

**Decision.** A recorded trace stores each action's accessible role and
label. On replay each step is resolved against the current page. The first
step that will not resolve or will not verify ends replay, the wrapped
planner takes over, and the corrected run is recorded over the old trace.

**Alternatives.** Store element ids, which is what the run actually used.
Store selectors. Never fall back — fail the run when a trace no longer fits.

**Why this.** Ids are assigned per perception pass and shift whenever the
page's element count changes, so an id-keyed trace is stale on the next load.
Selectors are excluded by the ids-not-selectors decision above. Failing
instead of falling back would make trace memory a liability: one page change
and a previously working task breaks, where a human would simply adapt.

**Cost.** A page that renames a button breaks the trace, silently costing a
model call to recover. Two elements sharing a label are disambiguated by
ordinal, which is order-dependent.

---

## Never execute an irreversible action

**Date:** 2026-09-04 (predates the repo; stated in `CLAUDE.md`)

**Decision.** No payments, no form submissions that alter real records, no
account changes. Stop at the confirmation screen. Every step is presented and
waits for `step.response` before anything touches the page, and the vault's
value is used over anything a planner supplied — `loop.resolve_value` refuses
outright to fill a password from a planner-invented string.

**Alternatives.** Allow completion with a confirmation prompt. Allow it
behind a per-site allowlist.

**Why this.** It is a design constraint, not a limitation. The users this is
for are the ones least able to recover from an agent that pays the wrong bill
or drops the wrong course, and a system that cannot do damage does not need
to be trusted not to. It also keeps the failure mode boring: the worst case
is a task that stops early.

**Cost.** Some tasks cannot be finished end to end, and the benchmark's
"success" is therefore always short of the real-world action.

---

## Unpriced, not $0, for a model with no rate on file

**Date:** 2026-09-06 (`3968838`)

**Decision.** `RATES_PER_MTOK` maps model to dollars per million tokens. A
model that is not in it makes the whole run `priced = False`, and the summary
row reads `unpriced` instead of a number.

**Alternatives.** Default an unknown model to $0. Estimate from a similar
model. Refuse to run without a rate.

**Why this.** A silent $0.00 on an unknown model is a wrong number that looks
like a right one, and it would end up in the report. Estimating from a
similar model is the same problem with extra steps. Refusing to run makes
cost accounting a blocker on experiments it is only meant to observe.

**Cost.** Adding a model means remembering to add its rate, or its runs
report unpriced.

---

## The hardcoded planner is the ceiling, not the baseline

**Date:** 2026-09-06 (`12dcc82`)

**Decision.** The hardcoded planner's numbers are recorded as what perfect
planning would score, and used to separate planning overhead from execution
cost — not as the bar the LLM has to beat.

**Alternatives.** Treat it as the baseline and read the LLM's 19.1s against
its 5.9s as the LLM being 3.2x worse.

**Why this.** The hardcoded plan names `Register for CS-401` because a person
wrote that string. It measures a plan that already knows the answer, on the
one replica it was written for. Reading it as a baseline would make "delete
the LLM" look like a 3.2x win, which is true for exactly this task and false
for the project. What the comparison legitimately yields is the cost of
planning: about 13 seconds for five model round trips.

**Cost.** It means there is currently no honest baseline for the LLM at all.
The comparison that would give one — both planners against a goal neither has
seen — has not been run.
