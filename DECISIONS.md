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

**Correction, 2026-09-17.** The 5.9s this entry quotes does not reproduce: the
same commit runs at 3.0s today, and the cause is not established
(EVALUATION.md, 2026-09-17e). The "3.2x" and "about 13 seconds" above were
computed from it and are withdrawn. The decision does not rest on the ratio
and stands.

---

## The backend detaches from the Electron host, never closes it

**Date:** 2026-09-06 (`c053367`)

**Decision.** With `SIMBA_BROWSER=electron`, `browser.open_page` connects over
CDP, and on exit calls `browser.close()` — which for a `connect_over_cdp`
connection detaches the client without touching the browser. The host owns
its own lifetime.

**Alternatives.** Have the backend launch and own Electron, so one process
supervises the whole stack. Or leave the connection open for the app's
lifetime instead of per task.

**Why this.** The window is the user's; a backend crash or a finished task
must not close it. Verified rather than assumed — the host was checked still
answering on CDP after a completed run, and there is a test for exactly that
(`test_the_host_survives_the_backend_detaching`), because the failure mode is
invisible until it happens in front of someone.

**Cost.** Two processes to start in the right order, and nothing supervises
the host. If it dies mid-task the backend reports a connection error rather
than restarting anything.

---

## The site view is identified by origin, and ambiguity is refused

**Date:** 2026-09-06 (`c053367`)

**Decision.** `find_site_page` picks the site view by matching the start
URL's origin, excludes the overlay by its `data:` URL, and raises when two
plausible candidates remain rather than choosing one.

**Alternatives.** Take the first non-overlay page. Have the host tag the site
view somehow — a title, a window name, an injected global. Have the host
report the target id over a side channel.

**Why this.** Driving the overlay instead of the site is the worst available
failure: every action would appear to succeed and nothing would happen to the
real page. Taking the first non-overlay page is one devtools window away from
doing exactly that. Origin matching is precise and needs nothing from the
host but the URL it was already given.

**Cost.** It depends on the host being told `SIMBA_START_URL`. Without it,
both views are `about:blank`-ish and detection falls back to the ambiguity
guard — which fails loudly, but fails. A host-side tag would be more robust
and is worth revisiting if the arrangement grows a third view.

**Update, 2026-09-06 (`7bb8ebf`).** The guard earned its cost one task later.
Building the React overlay moved it from a `data:` URL to `file:`, so the
scheme exclusion stopped matching and both views became plausible
candidates. Because the rule is *refuse when ambiguous*, every Electron run
failed immediately with "could not tell which of 2 pages is the site view"
and the cause was in the error text.

Had it taken the first non-overlay page instead, there was a real chance of
attaching to the overlay: the backend would have driven the React app,
`page.goto` would have loaded the replica *into the overlay*, every action
would have appeared to succeed, and the site view would never have moved.
That failure is silent, passes its own verification, and would have been
found by a person noticing the window looked wrong. The loud version cost
about ten minutes.

Exclusion is now by scheme (`data:`, `file:`, `devtools:`, `chrome:`) with
`SIMBA_OVERLAY_URL` for a dev-server overlay, which no scheme can rule out.

---

## The message log is cleared per connection, not per task

**Date:** 2026-09-06 (`fa4a508`)

**Decision.** The frontend harness clears its message log when it reconnects,
and keeps it across tasks that share a connection.

**Alternatives.** Clear on every task start. Never clear, and let it grow.

**Why this.** `seq` is a per-connection counter (CONTRACT.md), so it restarts
at 1 on every reconnect. Keeping entries across a reconnect renders two runs
interleaved with duplicate numbers, which is actively misleading — it made a
verification check pass falsely during this work before it was caught.
Clearing per task would instead throw away the history of a multi-task
session that never dropped its connection.

**Cost.** A session that reconnects loses the earlier log. Fine for a
harness; the real interface will want the log persisted somewhere if it keeps
one at all.

---

## `task.start.goal` is honoured, not discarded

**Date:** 2026-09-06 (`CONTRACT.md`, `app.py`)

**Decision.** The goal in `task.start` is the task. `SIMBA_FLOW` still selects
the site, the replica URL and the hardcoded plan, but the goal text comes
from the message, falling back to the flow's own goal only when the message
carries none.

**Alternatives.** Leave it: the backend picks the goal from its configured
flow and the field is decoration. Remove `goal` from `task.start` and select
tasks some other way. Add a separate task-selection message.

**Why this.** The field was in `CONTRACT.md`, the frontend sent it, the
schema typed it, and the backend threw it away — the frontend could start a
task but not choose one. That is worse than not having the field, because
every reader of the contract, on both sides, reasonably concluded it worked.
It was found by typing a goal into the harness and watching a different one
come back in `task.started`; nothing in the code, the types or the contract
would have revealed it.

A documented field that silently does nothing is a lie the codebase tells
its own authors. Either honour it or delete it — leaving it is the one
option that is not defensible.

**Cost.** The LLM planner now receives a goal the operator did not write, on
a site chosen by configuration. A goal that does not match the flow's site
will fail in ways the hardcoded plan never could, which is correct but new.

---

## An answered step stays on screen; the overlay crossfades in a shared grid cell

**Date:** 2026-09-06 (`c2efe13`)

**Decision.** Answering a step marks it answered and disables its buttons
rather than clearing it, and the screens crossfade as two children of one CSS
grid cell rather than with `AnimatePresence mode="wait"`.

**Alternatives.** Clear the step on answer, which is the obvious way to stop
it being answered twice. Use `mode="wait"`, which is the documented way to
avoid two screens overlapping mid-transition.

**Why this.** Both obvious choices were wrong here, and together they broke
the app. Clearing the step dropped the screen back to the goal for the few
milliseconds before the next message, which flashed. `mode="wait"` then
stranded the transition outright: the exiting screen stayed mounted at
opacity 0 and the next never arrived, so the column went blank and stayed
blank — no error, no warning, nothing in the console.

Overlapping both screens in one grid cell gives a true crossfade with no
reflow jump and no serialised exit to get stuck in. Keeping the answered step
up is better behaviour anyway: the thing you just agreed to stays visible
while it happens.

**Cost.** The column is as tall as the taller of the two screens during a
300ms crossfade. Unnoticeable at these sizes; would matter if a step were
very long.

---

## The three levels are one tree described by data, not three components

**Date:** 2026-09-06 (`b177bf2`)

**Decision.** `levels.ts` describes each level as a set of regions and
densities; `StepShell` renders that description. The dispatch table of one
component per level, added a task earlier, is gone.

**Alternatives.** Keep three components and crossfade between them. Keep
three components and morph the shared elements with Framer's `layoutId`.

**Why this.** The level change has to read as the interface folding down, and
a swap between two trees cannot do that: both trees exist only for the
duration of the crossfade, so nothing collapses, it just dissolves. A
collapse needs the surviving elements to stay mounted while the departing
ones animate their height to zero. `layoutId` morphing was the other option
and would have kept three files, but it puts two mounted copies of every
shared element on screen mid-transition and is markedly harder to reason
about when it goes wrong — which, on this codebase's record with Framer, it
would have.

**Cost.** The differences between levels are now adjacent in one file rather
than isolated per level, so a change to level 1 is a change to the file that
also draws levels 2 and 3. Worth it for an animation this central, and the
seam at `StepView` is still there if the levels ever diverge beyond what a
spec can express.

---

## Overflow moves towards level 1, not away from it

**Date:** 2026-09-06 (`55823b3`)

**Decision.** When a step will not fit, the level goes *down* the numbers —
3 to 2 to 1 — and level 1 is the floor. It overrides a locked level.

**Alternatives.** Move towards level 3, on the reading that "drop a level"
means show less. Respect the lock and allow a scrollbar. Shrink the type
instead.

**Why this.** The first version did move towards level 3 and made things
worse: measured on a step with three fields and three actions, level 1 is
449px and level 3 is 851px. Level 3 is the *roomiest* — 40px type, generous
gaps — while level 1 packs the same content into a compact card with inline
fields. Fitting and simplifying pull in opposite directions, and only one of
them is about height.

Overriding the lock is the uncomfortable half. The alternative is a scrollbar
on an interface whose whole premise is one visible decision at a time, and a
decision the user cannot see is worse than a level they did not pick. The
notice says why it happened.

**Cost.** A user who deliberately locks level 3 on a long step will watch it
pulled back to level 1 twice in a second. That is abrupt, and if it turns out
to matter more than the scrollbar does, this is the decision to revisit.

**Drift, noted 2026-09-17.** "Twice in a second" is no longer true. The guard
was limited to one hop per step later the same day (`c846be6`), so a locked
level 3 is pulled back to level 2 once, and the step then scrolls.

---

## Practice: measure the rendered result, not the declared intent

**Date:** 2026-09-06

**Decision.** Anything visual is verified by measuring what the browser
actually produced — computed styles, bounding boxes, per-frame samples — not
by reading the code that was supposed to produce it. Where the result is a
number, it goes in a test.

**Alternatives.** Read the diff and trust it. Look at a screenshot and judge
by eye. Trust the library to do what its API says.

**Why this.** Building the three levels turned up four defects in one
sitting, and not one of them would have been caught by reading the code,
because in every case the code said the right thing:

1. **`layout` fought `fontSize`.** Framer projects a laid-out element's box
   with a transform, which distorts any animation that changes layout. The
   heading was declared at 40px and rendered at roughly 16. Found by reading
   `getComputedStyle`, not the JSX.
2. **Framer silently dropped a unitless `fontSize`.** It appends `px` to
   numbers for `height` and `padding` but not for `fontSize`, so
   `fontSize: 40` did nothing at all — no error, no warning. The inline style
   showed the other two properties applied and this one simply absent. It
   needs `"40px"`.
3. **The easing read as a snap.** `[0.32, 0.72, 0, 1]` is a legitimate curve
   over a legitimate 350ms, and the code declaring it looks correct.
   Sampling per animation frame showed 72% of the movement landing in the
   first third, which is not a fold. Only the frame timeline showed it.
4. **The overflow guard moved the wrong way.** It dropped towards level 3 to
   make content fit, which is sound if you assume simpler means shorter.
   Measured, level 3 was 851px against level 1's 449px on the same step. The
   code was self-consistent and the assumption underneath it was false.

The common shape: the declaration was right and the rendered result was not,
so anything that only inspected the declaration agreed with itself. Two of
the four were silent — no error, no warning, no console output — and would
have shipped.

**Cost.** Measuring needs a real browser, which means the visual tests are
slower than unit tests and need the frontend built first. That is why
`test_levels.py` skips rather than fails when `dist/` is missing.

---

## The trust panel shows an annotated still, not the live site view

**Date:** 2026-09-07 (`1833a65`)

**Decision.** "What are you doing?" answers with a screenshot of the covered
site view, dimmed, with the element about to be touched ringed and named in
plain words. It does not reveal the live `WebContentsView` underneath.

**Alternatives.** Slide the overlay view aside in the Electron main process
so the real page is genuinely visible. Show the live view in an embedded
frame. Show nothing but a sentence describing the action.

**Why this.** The panel exists to answer a fair question — *how do I know
what you are about to do to my account?* — and a still with the target ringed
answers it completely: this page, that button, now. Revealing the live view
answers it too, and in the same movement hands the user the cluttered
interface the entire system exists to remove. Someone who finds a
sixty-element government portal overwhelming does not stop finding it
overwhelming because they asked a question.

It also matches the contract, which was written this way: `page.preview`
carries `screenshot`, `highlight` and `caption`, and is "sent only in
response to `trust.requested`". The image is the mechanism the protocol
already provides.

A still is additionally *safer to look at*: it cannot change under the user
mid-read, cannot start an animation, and cannot be clicked by accident.

**Cost.** It is a picture, so it is a moment old, and someone who wants to
verify with their own eyes on the live page cannot. If that turns out to
matter, the honest escalation is an explicit "open the real page" that hands
over control entirely, not a peek.

---

## Levels vary by density, not by height

**Date:** 2026-09-07

**Decision.** The levels are ordered by **how much is on screen and how many
decisions it asks for**, not by how tall they are. Both of those are
monotonic: level 1 shows the progress counter, the detail line, every field
and both actions as buttons; level 2 drops the detail line and quietens the
counter; level 3 drops the counter entirely, trims the instruction to its
first sentence, keeps only fields it cannot proceed without, and leaves one
button with the second choice demoted to text.

Total height is **not** monotonic and is not claimed to be. The only height
guarantee is that **level 3 is never the tallest**.

**Alternatives.** Order by height and force `h3 <= h2 <= h1`. Leave the
ordering undefined.

**Why this.** Forcing the height chain is not achievable without destroying
level 1. Level 1 is the *compact* layout — smaller type, tighter spacing,
fields laid out inline beside their labels rather than stacked above them —
so it is consistently the **shortest**, measured at the same viewport:

| step | level 1 | level 2 | level 3 |
|---|---|---|---|
| short | 241 | 253 | 174 |
| medium | 341 | 418 | 384 |
| long | 539 | 771 | 542 |

Inline fields cost roughly half the height of stacked ones, so the gap widens
as content grows. Making level 1 the tallest would mean abandoning inline
fields or giving it level 2's type and spacing — which is its whole brief.

Height was never the property that mattered. What a struggling user needs is
fewer things to read and fewer choices to make, and that is exactly what the
ordering delivers. The one height claim worth enforcing is the one that
prevents the original bug: simplifying must never push content off the
screen, so level 3 must never be the tallest.

**Cost.** "Drop a level" is ambiguous in a way the team has to keep straight:
towards level 3 is *simpler*, towards level 1 is *shorter*. The overflow
guard moves towards level 1 for exactly that reason, and got it backwards on
the first attempt.

---

## An inferred role is reported as inferred, and is never silently a declared one

**Decision.** Elements found from layout carry `inferred=True` and
`inferred_from` naming the rule that fired. They are numbered in the same
sequence as everything else and a plan targets them the same way, but the
distinction is never erased.

**Alternatives.** Merge them in indistinguishably, so nothing downstream has
to care. Keep them in a separate list a planner has to ask for.

**Why this.** A declared `option` is what the page's author said it is. An
inferred one is what it looks like from a mouse cursor. Those deserve
different amounts of trust, and the moment a run goes wrong the first
question is which kind was clicked. Merging them would erase exactly the
uncertainty worth surfacing; separating them entirely would mean every
planner needs a second code path for what is, at the point of use, the same
thing — an element with an id you can click.

**Cost.** One more field on `Element` and one more thing a planner may ignore.
Nothing currently reads it except logs and tests, which is the point: it costs
nothing until something goes wrong.

---

## An inferred element's role is decided by position, never by its neighbours

**Decision.** Inside a floating panel, everything is an `option`. Elsewhere a
list item is a `menuitem` and anything else is a `button`. The sibling-group
signal decides *whether* an element is a control, never *what kind*.

**Alternatives.** Use group membership as evidence for `option` (what the
first version did). Give everything the same role and let the label
disambiguate.

**Why this.** The first version was unstable in a way that took an hour-long
failing run to find. Element UI gives calendar cells classes like
`available`, `prev-month available` and `today available`, so how many
siblings share a cell's class depends on where in the month the day falls.
The 15th of October came out `option` and the 15th of another month
`button` — from identical markup. A plan has to name the role it aims at, so
a role that moves with the calendar is not usable at all.

Predictable beats nuanced when the value is part of an addressing scheme.

**Cost.** A `li` inside an absolutely-positioned container that really is a
menu item is called an `option`. Nothing can currently tell those apart from
layout, and pretending otherwise is what caused the problem.

---

## Content extraction stops at a floating panel

**Decision.** Anything inside an absolutely or fixed positioned container
stacked above the page is excluded from readable content. It stays fully
available through the interactive channel.

**Alternatives.** Read everything and let callers filter. Exclude only
elements that are also flagged as an overlay.

**Why this.** A date picker is a control, not something the page says. The
live railways picker is a properly built `<table>` with `Sun`..`Sat` headers
and six rows of days, and with it included the run **reported success after
three steps** — "the page has at least one row of results" was satisfied by
opening a calendar. A success condition a date picker can satisfy is not a
success condition.

The same test the other two snapshot readers already use, so all three agree
on what a floating panel is.

**Cost.** Real content inside a modal is skipped too, and nothing yet
distinguishes a dialog from a dropdown. This is a live limitation, recorded in
STATUS.md. It is tolerable for now because a modal's content is also blocking
content, and the loop's job with one of those is to dismiss it — but the first
task that needs to read a modal will have to make the distinction properly.

---

## The retry strategy for a fill clicks before it types

**Decision.** Strategy 1 for a fill is now click, select-all, type — not
`clear()` then type.

**Alternatives.** Leave it. Add a separate "unlock" operation to the plan
vocabulary.

**Why this.** `fill` and `clear` both require an element to be *editable*, and
a component-framework combobox ships its input `readonly` until you click it,
removing the attribute in its own handler. Playwright never gets that far: it
waits for editable, the attribute never clears, and the step fails after a
long timeout on a field nothing was blocking. Both station inputs on the live
railways search are like this, and it is what actually defeated the first run.

A click is not subject to the editable check, so this route works where the
direct one cannot — and the retry slot is exactly where "a different way of
achieving the same thing" belongs. Putting it in the plan instead would make
every plan carry a workaround for a widget library.

**Cost.** The retry is slightly more invasive: it focuses the element, which
can trigger handlers a bare `fill` would not.

---

## A value that stops being there ends the run rather than being retried

**Decision.** Durable verification hands control back immediately. It does not
retry, and it does not count towards the two-setback budget.

**Alternatives.** Treat it as an ordinary setback. Re-run the step that filled
the field.

**Why this.** Every other failure here is an action that did not take effect,
and a different strategy is a real chance at a different outcome. A value the
page took back is not that: the typing worked, and something undid it
afterwards. Repeating the same keystrokes invites the same undoing, while
every further step would be acting on a form that does not contain what the
user was shown being entered.

Tolerating it is not neutral. Before this, a lapsed value was absorbed as a
first setback and the run continued to `task.completed` on an empty form —
which is the exact class of silent wrongness verification exists to prevent.

**Cost.** A planner that *could* recover — an LLM told "type it again, but
commit the choice this time" — never gets the chance. Worth revisiting when
the LLM path is exercised against a live site; flagged rather than settled.

**Revisited 2026-09-09, and this decision stands.** The LLM path was
exercised against a live site, the other way was tried, and it was reverted
the same day. See "A durability lapse ends the run — tried the other way,
reverted the same day" below for what it cost.

---

## An action gets ten seconds, not thirty

**Decision.** `ACTION_TIMEOUT_MS = 10_000` on every Playwright action the loop
performs.

**Alternatives.** Keep Playwright's 30s default. Make it configurable per
step.

**Why this.** Thirty seconds is the right default for a test suite and the
wrong one twice over here. A person is watching the step happen, and half a
minute of nothing is not a wait, it is a hang. And the loop retries: at 30s, a
step that fails both strategies costs over a minute before anyone is told
anything. A live run that could not find its target spent **sixty-two
minutes** failing.

A click that has not landed in ten seconds is not going to.

**Cost.** A genuinely slow page could have an action fail that would have
succeeded at twenty seconds. The retry absorbs some of that, and no run so far
has an action between 10s and 30s that later succeeded.

---

## An inferred element carries a short qualifier from a curated class list

**Decision.** Four class tokens become a human qualifier on an inferred
element: `prev-month` → "previous month", `next-month` → "next month",
`disabled`, `today`. Everything else in the class attribute is still
discarded. An empty qualifier is a value, not an absence: in a calendar it is
what marks a day as belonging to the month on screen.

**Alternatives.** Emit the whole class attribute. Emit nothing and
disambiguate by position in the group. Encode it into the label
("15 (previous month)").

**Why this.** A month grid has two cells labelled `30` and eleven duplicate
numbers in all, and emitting them identically meant "the 15th of October" was
not expressible in what a planner is given. The live LLM run clicked the 15th
of the wrong month and could not have done better.

The whole class attribute is mostly styling and would drown a planner in
noise — `el-date-table__row`, `hover`, `is-active` — and would make the
matching brittle against a library's next release. Position in the group is
stable but meaningless to a model and unreadable in a log. Folding it into
the label breaks every existing `Target` and makes two different things — the
name of a thing and a fact about it — into one string.

Four tokens, because these four are stable across component libraries and
mean the same thing everywhere.

**Cost.** A library that marks its adjacent-month cells some other way gets
no qualifier and the ambiguity returns silently. The list will need
extending, and the only way to find out is a page where it fails.

---

## A disabled inferred element is surfaced, not dropped

**Decision.** An inferred element carrying `disabled` is emitted with that
qualifier rather than filtered out — unlike an accessibility-tree element,
which `build_elements` drops when the AX tree says `disabled`.

**Alternatives.** Drop it, for consistency with the AX path.

**Why this.** "This date exists and you cannot pick it" and "this date does
not exist" are different claims, and only the first is true. A planner that
sees the option missing will hunt for it; one that sees it disabled can say
so to the user. The inconsistency with the AX path is real and is the lesser
problem — that path drops elements the page itself declared unusable, where
this one is a guess from a class name.

**Cost.** Element counts include things that cannot be clicked, and a planner
that ignores the qualifier will waste a step discovering it.

---

## A durability lapse ends the run — tried the other way, reverted the same day

**Decision.** A value that stops being there ends the run with
`help.requested`. It is not retried and it is not handed back to the planner.

**What was tried instead.** On 2026-09-09 the lapse was changed to hand the
failure to the planner once as a setback, giving up only on a second lapse.
The reasoning was sound and is still sound as far as it goes: both live
lapses are recoverable by *choosing differently* rather than trying harder —
commit the option, press Next Month first — and a planner that can re-plan
should get the chance. Repeating the keystrokes invites the same undoing;
reconsidering the plan does not.

**Why it was reverted.** It converted a run that stopped honestly into one
that finished wrongly. In the live LLM run the model was told in plain words
that its date was the wrong month and that the choice needed committing, it
re-planned, it clicked search anyway, and the run reported `task.completed`
on a timetable for `2026-09-15` against a goal naming `2026-10-15`.

Before the change, no search went out and the user was told the system was
stuck — wrong about the cause, right about the outcome. After it, a person is
handed a plausible, well-formed answer to a question they did not ask, with
nothing on screen suggesting anything went wrong. **That is the worst thing
this system can produce and the only failure a user cannot catch.** A
recoverable stop is worth more than an unrecoverable success.

The mechanism was not at fault and the model was not simply careless: the
setback reached it, and moving that setback above the element list changed
its answer at the same decision. What is missing is a check that can tell a
right answer from a wrong one at the end, and until that exists, continuing
past a lapse is trading a visible failure for an invisible one.

**What would bring it back.** A success condition that can verify the goal's
own values well enough that a wrong answer cannot pass.
`Expectation.value_is` (2026-09-09) is the first half — the railways task now
requires the departure field to hold the goal's date — and it is not enough
on its own, because it only asks about the fields a plan happened to name.
Reconsider when a task can state what it was asking for, and be checked
against it, without the plan author having to remember to.

*Update, 2026-09-17: `Expectation.value_is` is now `About.holds`, and a task
cannot be written without an `About`. That is the "state what it was asking
for" half. It is still only as good as what the author declares, it is only
checked on the final page, and nothing checks what the task finds — so the
condition above for revisiting is not yet met.*

**Cost of the revert.** An LLM that could genuinely recover from a lapse is
stopped anyway, and a run that could have finished ends in `help.requested`.
That is the trade, taken deliberately and with the evidence in hand rather
than predicted: see EVALUATION.md case 6.

**Cost of the revert.** An LLM that could genuinely recover from a lapse is
stopped anyway, and a run that could have finished ends in `help.requested`.
That is the trade, taken deliberately and with the evidence in hand rather
than predicted: see EVALUATION.md case 6.

---

## `Expectation.value_is`: a success condition may ask what a field holds

**Decision.** An `Expectation` can name a field and the value it must hold,
read from the values `Snapshot` already carries. The railways task uses it:
success now needs results *and* the departure field holding the goal's date.

**Alternatives.** Check the date in the results. Check the URL. Leave
`rows_at_least=1` and rely on the planner being right.

**Why this.** The results cannot be checked: the table is `Train No.`,
`From/To`, `Time`, `Duration` — no date column — so `content_says` has
nothing to match. The URL never changes; it is a single-page app. The only
place the requested date appears at all is the field the user watched being
filled, and no expectation could read a field value even though `Snapshot`
has carried them since 2026-09-08.

`rows_at_least=1` is not wrong, it is the wrong question: it is satisfied by a
search for any date at all, which is exactly how a run reported success on
the wrong one.

**The expected value is what the page shows, not what was typed.** The picker
accepts `2026-10-15` and commits it as `15-10-2026`, so `FieldValue.equals`
holds the second. A condition written against the typed string would fail at
the moment the value became real, which is the opposite of its purpose — and
that distinction is the same one durable verification exists for.

**Cost.** It is per-field and per-plan: someone has to remember to write it,
and a task whose author forgets is exactly as blind as before. It also
hard-codes one site's display format into a plan. Both are acceptable for a
hardcoded plan and neither scales to a planner writing its own success
conditions, which is the version this will eventually need.

---

## A floating panel says what it is showing

**Decision.** An inferred element carries `panel`, the heading of the
floating panel it sits in, and `render_page` promotes it to a banner above
the element list: `IT IS SHOWING: 2026 September.`

**Alternatives.** Leave the month in the element list as `button 'September'`
among seventeen others. Put the heading on every option.

**Why this.** A month of day cells is not self-describing. Every month has a
15th; which month is on screen is stated once, at the top, and both live LLM
runs clicked the 15th of the month the picker happened to open on without
ever comparing it to the goal — with `button 'September'` and `button 'Next
Month'` sitting unremarked in the list the whole time.

Qualifiers fixed the ambiguity *within* a grid and could not fix this: they
say which cell is which, not which grid you are looking at. This is the third
mechanism to follow the same rule — a fact that changes which element is
correct belongs above the list, not in it (EVALUATION.md, "Where information
sits is a perception decision").

Once per panel, not once per option: forty-two repetitions of the same
sentence is how a banner stops being read.

**Cost.** The heading is found by class-name fragments — `header`, `title`,
`caption`, `heading` — so a panel that names its header something else gets
none, silently. And a heading is only ever as informative as the page made
it: this one reads `2026 September` because that is the order the site prints
it in, and nothing here reorders or reformats what the page said.

**Unverified.** Whether stating the month actually changes what a model picks
has not been measured. It needs a live run, and the day's quota is spent.

---

## A setback goes above the element list, not after it

**Decision.** `build_user_prompt` puts feedback immediately after the goal,
in the imperative, above both the history and the element list.

**Alternatives.** Leave it appended after the page, where it was.

**Why this.** The third instance of one finding. A live run's model was told
in plain words that the date it had set was the wrong month and that the
choice needed committing, and it clicked search anyway — with the setback
eighteen element lines below the thing it was about. Re-asked with the same
words moved above the list, same page state, one call, it addressed the date
instead of moving on.

This matches what the overlay banner and the open-choices banner already do,
and EVALUATION.md now states the rule the three of them share: anything a
planner must act on at *this* step sits above the list.

**Cost.** It buys attention, not competence — given the correction, the model
re-typed the date, which is exactly what the widget discards. And the
end-to-end effect is unverified: it changed one decision under test and has
not been run through a whole task, because the quota ran out.

---

## The interface's copy lives in one file, and is enforced

**Decision.** Every sentence the interface says is in `frontend/src/copy.ts`.
A component may not write its own, and `frontend/test_copy.py` fails if one
does.

**Alternatives.** Keep strings where they are used. A convention rather than a
test.

**Why this.** The audience is people with cognitive disabilities, and the
governing rule is that identical situations read identically. Someone who has
learned that "Give me a moment." means waiting should never meet "One
moment…" for the same state: a second phrasing asks them to work out whether
something new is happening, which is the work this project exists to remove.

A component that writes its own string cannot be checked for that. A table
can. The test compiles `copy.ts` with the project's own `tsc` and reads the
values out through node, so it cannot pass against a file that would not
build, and cannot drift from what actually renders. It also scans every
`.tsx` for sentences, which is the part that stops the file quietly becoming a
suggestion.

It already caught two things on the first run: `ending.withAnswer` and
`found.heading` were two situations with one sentence, and a level change had
two possible phrasings depending on which pair of levels it was between.

**Cost.** It is only *one* file for the interface. The instructions on each
step and the labels on their buttons come from the backend's plans, and a plan
for a new site brings its own wording with no test behind it. So the voice is
set in two places and only one of them is enforceable. Named in the report and
in `copy.ts` rather than hidden.

**Update, 2026-09-17.** Both places are now enforced — see "The backend's
words live in `voice.py`" below. Also found: the component scan had been
passing three strings that were on screen, and a level-change sentence was
being built in `store.ts` rather than taken from this file. The claim above,
that every sentence the interface says is in `copy.ts`, was not true when it
was written.

---

## A task says what it was asked to find out

**Decision.** `Task.answers` is a tuple of (name to show, content label). The
loop resolves them from the content channel at every perceive, remembers what
it has seen, and sends them on `step.presented` and `task.completed`.

**Alternatives.** Read the answer from the final page. Put the sentence
together in the backend. Let the frontend search the content itself.

**Why this.** A run that ends with "Done." answers nothing. Somebody who asked
what their bill was is owed the number, and the content channel has had it
since 2026-09-08 with nothing carrying it to the screen.

Accumulated rather than read at the end, because the answer is usually not on
the page the task finishes on: the billing amount is on the results page and
the run then opens the detail page, where that column does not exist. Reading
only at the end would find nothing, having walked past the answer two steps
earlier.

The *name* comes from the plan rather than the page because the page's own
heading is `P/WITHIN`, which means nothing outside a billing department. And
the sentence around it is composed in the frontend, not the backend, so all
the wording stays in one reviewable place.

**Cost.** Another thing a plan author has to remember, and the same shape of
gap as `value_is`: a task that does not declare `answers` shows nothing and
nothing warns the author. The two should probably be one declaration — what
this task is about — rather than two.

**Update, 2026-09-17.** Done: `Task.about`, required. See "What a task is
about is declared once, and must be" below. Also found: nothing tested that
an answer reached `task.completed` at all. `test_billing.py` now does, from a
page the run has left.

---

## Past goals reach the home screen over the socket, not over HTTP

**Decision.** A new backend-to-frontend message, `history.offered`, sent once
when the socket opens.

**Alternatives.** A `GET /goals` route with CORS. A request/response pair the
frontend asks for.

**Why this.** The home screen shows what this person has asked for before, so
the data has to cross the boundary, and CLAUDE.md is explicit that the two
processes talk over WebSocket and nothing else. An HTTP route would have been
smaller in one sense and a hole in the architecture in another.

Sent unprompted rather than asked for because there is nothing to ask with
until a task starts, and adding a frontend-to-backend request would have been
two new message types rather than one.

**Cost.** It is a **new message type**, which `CONTRACT.md` says needs all
three owners, where an additive optional field does not. It is additive — a
frontend that ignores it is unaffected — but it is a change to the contract's
shape and it was made to satisfy a screen. Flagged for review rather than
presented as routine.

**Drift, noted 2026-09-17.** The cost above says `CONTRACT.md` requires all
three owners for a new message type. It does not say that: its rule names
additive optional fields (allowed) and renames or removals (all three
owners), and a new type is in neither. The conclusion stands — a new type is
a change to the contract's shape and should be agreed — but it was a
judgement, not a rule being followed. `CONTRACT.md` now records the message
as **pending ratification**, with the reasoning for a WebSocket message over
`GET /history` and two costs found since: the list is only as fresh as the
connection (a goal just finished does not appear on the home screen the run
returns to), and only `SIMBA_TRACE_MEMORY=1` ever writes to the store it is
read from.

---

## What a task is about is declared once, and must be

**Date:** 2026-09-17

**Decision.** `Task.answers` and `Expectation.value_is` are replaced by one
field, `Task.about: About`, with two halves: `holds` (the values the goal
names, as the page must show them) and `finds` (the values the goal asks for,
with the name to show each under). `about` is required and keyword-only;
`About()` is a valid answer but must be written.

The loop checks `holds` through `unmet(snapshot, task)`, which it uses at both
of the points it used to call `satisfies(snapshot, task.success)`:

- **Early finish**, before each move: only when the task has a `success`
  expectation, and then `holds` must also be true. `holds` alone never ends a
  run, because a filled form nobody searched with holds every value.
- **Final check**: whenever the task has a `success` expectation *or* any
  `holds`. So a declared value is checked even if nobody wrote a success
  condition.

**Alternatives.** Keep both fields and add a test that plans use both. Merge
into a single list of "facts" with a flag for check-or-show. Make success
require every `finds` value to have been found.

**Why this.** Asked for: two declarations a plan author must separately
remember is two chances to forget, and forgetting either failed silently.
Two named halves rather than one list with a flag, because a value the goal
names and a value it asks for are used in opposite directions — one is
checked, one is shown — and a flag would put that difference where it is
easy to misread. Required rather than defaulted, because a default is exactly
how both were forgotten before: a task that did not mention either got an
empty tuple and said nothing.

**Cost.** Every `Task` construction had to change, five of them in tests. The
billing reference number still cannot be a `holds` entry: it is typed on the
first page and checked on the last, where there is no field. And `finds` is
still not part of success — a billing run that never read the amount would
complete with no findings rather than stop. Whether it should is flagged, not
decided.

---

## The backend's words live in `voice.py`, and one test holds both halves

**Date:** 2026-09-17

**Decision.** Everything the backend puts on screen that is not specific to
one task — the stop button, the LLM and replay confirm button, the stuck
screen's suggestion, the failed screen's reason when the person stopped, the
trust panel's captions, the sentence templates for a move a planner chose —
is in `backend/orchestrator/voice.py`. The three plans, the LLM planner,
replay, the loop and the mock backend use it. `frontend/test_copy.py` imports
the plans, the mock's script and `voice`, and holds every instruction, detail
line and label to the same rules as `copy.ts`: sentences end, labels do not,
no taught words, never "the user", straight apostrophes, no web address,
every step stops in the same words, and the backend's suggestion is the same
sentence as `STOPPED.suggestion`.

**Alternatives.** Move plan strings into `copy.ts` and have the backend send
keys — which changes the contract, since `step.presented` carries text. A
shared JSON file both sides read — a new cross-language build step for a
problem a test solves. Extend the test to the plans without a shared module —
it would check, but every plan would still write its own stop button.

**Why this.** The contract has the backend author these strings, so they
cannot move to the frontend without renaming fields. A test is the lightest
thing that turns "the voice is set in two places and only one is enforceable"
into two places that are both enforced. The shared module removes the three
copies of `_confirm` and two copies of the LLM/replay confirm buttons, which
is where "Not now" would otherwise have had to be changed seven times.

Writing it turned up four things that were on screen: plans wrote `I’ll`
with a curly apostrophe beside `copy.ts`'s straight `I'm`; the stuck screen's
suggestion from the backend was a different sentence from the one in
`copy.ts`, and the backend's was the one actually shown; the failed screen,
after the person pressed stop, said "The user chose not to continue." to the
user; and the scan of components had been passing `let it choose`, `Hide the
page` and an image description, because it only looked for three-word
punctuated sentences.

**Cost.** The copy test now imports the backend, so a frontend-only checkout
cannot run it. Plan-specific instructions are checked by rule, not by review:
a sentence can pass every check and still be the wrong sentence. And
`voice.describe` is deliberately *not* in the assistant's voice yet ("Fill in
From." rather than "Let me fill in From.") — see the next entry.

---

## The LLM's move descriptions are not reworded yet

**Date:** 2026-09-17

**Decision.** `voice.describe` produces the same text `llm_loop.describe` and
`replay.describe` did.

**Alternatives.** Reword to the assistant's voice now.

**Why this.** The string is used twice: as the instruction on screen, and as
the model's own history in the next prompt ("Already done: 1. Fill in
From."). Rewording it changes the prompt, and the one outstanding LLM run —
the one STATUS.md has been waiting on since 2026-09-09 — should measure the
prompt the three pending fixes were tested against.

**Cost.** Every LLM-planned or replayed step reads as an order to the person
("Click LAHORE CANTT.") where every hand-written plan speaks as the assistant
("Let me set where you're starting from."), and an unnamed element is
described as "element 13" or "the element". Flagged: the screen string and
the prompt string should probably be separated.

---

## A level change is announced from its direction alone

**Date:** 2026-09-17

**Decision.** `LevelNotice` renders `copy.levelNotice(from, to)`. The store's
`because` is no longer rendered; it holds the estimator's reason or the
overflow guard's, for debugging.

**Alternatives.** Keep rendering `because` and fix its wording.

**Why this.** `copy.ts` already said a level change gets one sentence per
direction, and nothing used the function. The store built its own strings
instead, and the overflow guard's — "this step was too long to fit." — was on
screen in lower case, using a word the rules forbid, whenever a long step
dropped a level.

**Cost.** The screen no longer says *why* the level moved, only that it did.
That was already the rule for `load.updated`, whose `reason` the contract
says is never shown.

---

## Thinking and acting share one sentence

**Date:** 2026-09-17

**Decision.** `presence` has two situations, `opening` ("Let me open that for
you.") and `working` ("Give me a moment."). "I'm doing that now." is gone.

**Alternatives.** Keep both. Merge them into a new, longer sentence.

**Why this.** Asked for. It also holds up on its own terms: from the person's
side, working out what to do and doing it are one situation — wait — and the
difference is already shown without words, by the line that crosses the top
of the column while an action runs. The shorter existing sentence was kept
rather than writing a new one, so nothing already learned changes.

**Cost.** The screen no longer says in words that something is being done to
the page right now. Someone who cannot see or does not notice the moving line
gets no signal of it.

---

## A lead-in ends with nothing

**Date:** 2026-09-17

**Decision.** "Here's what I found" and "You asked me for these" have no
colon. `test_copy.py` now has three kinds of string: sentences (end in `.` or
`?`), lead-ins (no punctuation) and labels (no punctuation), in the tables
`SITUATIONS`, `LEADS` and `LABELS`.

**Alternatives.** Keep counting a colon as an ending. Drop the rule.

**Why this.** The colons were removed as asked, and the old test allowed a
colon specifically for "Here's what I found:". Leaving that allowance with
nothing using it would let one come back unnoticed. A lead-in sits directly
above what it introduces, which does the colon's job.

**Cost.** Three categories to keep straight instead of one. A string put in
the wrong table fails for a reason that reads oddly until you know why.

---

## Every ending has a way onward, and one destination has one name

**Date:** 2026-09-17

**Decision.** The stuck screen renders a button, `ONWARD` ("Do something
else"), which returns to the home screen. The closing screen's second button
and the failed screen's button are the same constant. `copy.ts` exports it
once and `STOPPED.again` and `ENDING.again` both refer to it.
`frontend/test_terminal_states.py` renders all four endings and fails if one
has nothing to press or if pressing it goes nowhere.

**Alternatives.** Keep two names ("Do something else" on the closing screen,
"Start again" on the others). Name it "Ask for something new" to match the
home screen's reveal button. Offer a retry on the stuck screen.

**Why this.** `STOPPED.again` existed and nothing rendered it: the stuck
screen was a dead end, for the audience least able to find their own way out
of one. Two names for one place asks the reader to work out whether they are
different places. "Start again" was also inaccurate — it never retried the
task. "Ask for something new" is already the label of a *different* button
(it reveals the text box on the home screen), so reusing it would be two
places with one name, the same problem reversed. There is nothing to retry
into: the backend closes the socket after `help.requested`.

**Cost.** The closing screen now has two buttons, "I'm done" and "Do something
else", and both call `startOver` — the same destination under two names,
which is the problem this entry fixes elsewhere. Not fixed, because deciding
what "I'm done" should do instead is a design question. Flagged in STATUS.md.

---

## The closing screen restates the goal, not `task.completed.summary`

**Date:** 2026-09-17

**Decision.** With no findings, the closing screen shows "That's done." and
the goal from `task.started`. It no longer renders `summary`.

**Alternatives.** Change the backend's summary to drop the URL. Show nothing
under "That's done."

**Why this.** The backend builds `summary` as the goal followed by the final
URL, and it was rendered in 26px type: `Register for the course CS-401.
http://127.0.0.1:5000/register`. Six backend tests read that URL out of
`summary` to see where a run ended, so changing the backend would have taken
evidence away from them. The frontend already has the goal.

**Cost.** `summary` now means two things: a log-and-test channel in practice,
and a human-readable sentence in `CONTRACT.md`'s example (`"Registered for
CS-401."`). Nothing reads it for display any more. Flagged.

---

## The rendered test builds its own overlay

**Date:** 2026-09-17

**Decision.** `test_terminal_states.py` runs `vite build` into
`.scratch/overlay-terminal/` and tests that, rather than `frontend/dist/`.

**Alternatives.** Use `dist/` and skip without it, as `test_levels.py` does.
Run `npm run build` into `dist/`.

**Why this.** The defect this test exists for lived in the gap between
source and screen. Testing a stale `dist/` would reopen that gap. Writing
into `dist/` would change what a running Electron host loads underneath it.
`.scratch/` is ignored and is already where `test_copy.py` compiles to.

**Cost.** A build per run — 5.2s measured on 2026-09-17, with the full suite
running alongside. `vite build` does not type-check,
so a type error does not fail this test; `npm run build` still has to be run
for that.

---

## The stuck screen says what happens, not what it hopes

**Date:** 2026-09-17

**Decision.** "I'm stuck, so I've stopped." / "I won't do any more on this.
You can ask me for something else." The backend's `voice.HELP_SUGGESTION` is
the same sentence, and `test_copy.py` fails if either side promises to carry
on or asks the person to do part of the task.

**Alternatives.** Build what the old words promised: reveal the site view,
let the person act, resume. Keep asking for help but drop the promise.

**Why this.** The words asked for earlier the same day were untrue on every
point. `help.requested` ends the run and the socket closes, so nothing
carries on. The site view is covered by design, so the person cannot do
"this part". A real hand-over is a feature — a contract change and a new
backend state — not a wording fix, and until it exists the screen should say
only what is so.

**Cost.** The stuck screen no longer invites the person into the task at all.
If a hand-over is built, this wording has to change with it. The reason under
it is still technical, and still shown.

---

## The leaving step stays on screen until it has gone

**Date:** 2026-09-17

**Decision.** The step component keeps rendering the last step while its
screen fades out, instead of rendering nothing the moment `step` is cleared.

**Alternatives.** Stop clearing `step` on an ending. Make exiting screens
ignore pointer events. Go back to `AnimatePresence mode="wait"`.

**Why this.** With the step rendering nothing mid-exit, the exit never
completed and an invisible element sat over every ending's buttons. Measured:
0 of 7 attempts could press "Do something else" after a step; 4 of 4 after
this change. Not clearing `step` would spread the fix across every message
handler. Ignoring pointer events would leave the stranded element in the page
and hide the symptom. `mode="wait"` stranded the column outright last time
(see "An answered step stays on screen").

**Cost.** A step is briefly visible, disabled, while it fades, which is the
crossfade working as intended. The cause is inferred from behaviour, not from
Framer's source; if an exit strands for another reason, this does not prevent
it. The terminal test does not catch it for the stuck ending.

---

## Stopping is its own ending, shown the moment stop is pressed

**Date:** 2026-09-17

**Decision.** When the person answers a step with anything but go-ahead, the
overlay shows "I've stopped, as you asked." at once, in ordinary ink, with
"Do something else". It does not wait for the backend's `task.failed`, and
does not show it. The failed screen remains for a `task.failed` the person
did not cause.

**Alternatives.** Go straight to the home screen. Wait for `task.failed` and
choose the screen by its `reason` string. Add a field to `task.failed`
saying who ended it.

**Why this.** The overlay already knows the person pressed stop — it sent the
response — and the backend acts on nothing without one, so there is nothing
to wait for. Matching on the reason string would make wording load-bearing.
A contract field needs all three owners, and the frontend does not need it.
Going straight home would be a change the person did not see announced.
The overlay keys on "not `confirm`" because that is exactly the backend's
rule (`loop.run_task`); `test_copy.py` checks the two ids agree.

**Cost.** The frontend now encodes a backend rule. If a step ever offers two
ways forward, both non-`confirm` answers will read as stopping until this
changes.

---

## No formatter or linter is claimed until one is adopted

**Date:** 2026-09-17

**Decision.** `CLAUDE.md` and `README.md` no longer say the Python code uses
`ruff` and `black`. They say neither is in use, with the measurement.

**Alternatives.** Install both, pin them in `requirements-dev.txt`, and apply
them.

**Why this.** Either option makes the conventions true. Applying them means
`black` rewriting 46 of 57 files — every module, including perception and the
replicas — and 30 `ruff` findings needing hand fixes, some in behaviour
(blind `except`, unchecked subprocesses). That is a change for all three
owners to agree and review, not a side effect of fixing a stale line.

**Cost.** The project has no formatter, and now says so. Style will keep
drifting until someone proposes adopting one.

---

## Evaluation scripts live in `tools/evaluation/`, their outputs do not

**Date:** 2026-09-17 (`7d7bc5d`)

**Decision.** The thirteen scripts behind EVALUATION.md's numbers moved from
`.scratch/` to `tools/evaluation/`, renamed for what they measure, each run
as `python -m tools.evaluation.<name>`. Their outputs stay in `logs/`, which
stays gitignored. `overlay_ablation` had its missing first condition
restored; everything else changed only its paths, plus one signature fix.
The other fifty-odd scratch scripts — document patchers, UI drivers,
throwaway probes — stayed where they were.

**Alternatives.** Flat in `tools/`, beside `screen_site.py` and
`mock_backend.py`. Commit the raw outputs too. Commit the ablation script
exactly as found.

**Why this.** A subdirectory keeps thirteen measurement scripts from burying
the two tools people run day to day. Transcripts hold full prompts and are
large and many; the tables in EVALUATION.md are the record, and the scripts
make them re-runnable. An ablation script that cannot produce the row it is
cited for is not reproduction, so the condition went back, with the change
stated in its docstring.

**Cost.** Three results still have no script: the one-call token count, the
first live run of 2026-09-07, and the copy-test mutations. And a re-run is
reproduction of the method, not of the number — the hardcoded benchmark came
back at half its recorded wall clock.

---

## A changed value is accepted when it is the value the task declared

**Date:** 2026-09-17

**Decision.** Durable verification no longer treats a field as lapsed when it
now holds exactly the value `Task.about.holds` declares for that field's
label. Any other change is still a lapse, the record keeps the typed value so
the field goes on being watched, and a field with no declared value is
checked exactly as before.

**Alternatives.** Compare values through a normaliser — date-aware, or digits
only. Stop watching a field once a choice has been committed into it.

**Why this.** Asked for, and it has the narrowest reach of the three. A
normaliser has to know every format every site writes, and a digits-only one
would equate `15-10-2026` with `2026-10-15` and also with `10-15-2026`, a
different date. Unwatching a field after a commit gives up exactly the case
durable verification was built for: a value the page silently replaces. The
declared value is already the task's statement of what the field must say,
and the loop already requires it at the end.

**Where the check is now weak — and how that differs from what was asked to
be recorded.** The instruction was to record that the check is now *blind*
on fields the plan did not declare. That is not what this change does, and
recording it that way would be wrong in a way that matters:

- **On an undeclared field the check is unchanged, not blind.** It still
  catches a value that disappears or is replaced. It also still stops a run
  whenever the page merely *reformats* a value — the 2026-09-17 false stop,
  intact. `test_an_undeclared_field_is_as_strict_as_before` pins that down.
- **That is where the LLM planner operates.** It types into whatever field
  it chooses, and a task declares only the values its goal names. On any
  other field a reformatting widget will still end an LLM run with a correct
  form. The railways run is helped only because its task happens to declare
  the departure date.
- **On a declared field the check is weaker in one precise way.** A field
  that ends up holding the declared value passes, whatever was typed — so if
  the page itself substituted the declared value for something wrong the
  planner typed, that is not reported. Since the declared value is the right
  answer by definition, this only hides a planner mistake the page corrected.

**Cost.** False stops remain on undeclared fields, which is most fields an
LLM touches. Fixing those needs one of the rejected alternatives, or a
planner that declares what it means a field to hold before it types —
flagged in STATUS.md.

---

## A measurement records the conditions it was taken under

**Date:** 2026-09-17

**Decision.** Every script in `tools/evaluation/` prints a conditions block
when it starts, and the three that write result files write it into the file:
time with offset, commit and dirty flag, interpreter and whether it is the
project venv, Playwright and Chromium versions, provider and model string,
every `SIMBA_*` switch whether set or not, platform, CPU count and CPU load.
`tools/evaluation/conditions.py`, with tests.

**Alternatives.** Record nothing, as before. Record only what changes between
arms of an experiment. Use a library that samples the machine properly
(`psutil`).

**Why this.** The 2026-09-06 hardcoded figure of 5.93s could not be explained
five days later, because its result file held ten numbers and nothing else
(EVALUATION.md, 2026-09-17e). Within hours of adding this, the same benchmark
ran at 6.85s where it had run at 3.01s the same afternoon — a 2.3x spread the
recorder makes visible and an unrecorded number hides (2026-09-17h). The
November benchmark is what the report rests on, so the gap had to close before
it, not after.

`psutil` would sample load better and is a new dependency for one number;
CLAUDE.md says not to add one without asking. `os.getloadavg` where it exists
and a CIM query on Windows cost about three seconds once per run, and report
`None` rather than zero when they fail.

**Only the model string and the provider are read from `.env`**, never a key,
and `test_conditions.py` asserts that no key reaches a banner or a result
file. A recorder that leaked a credential into `logs/` would be a worse
problem than the one it solves.

**Cost.** About four seconds added to the start of every script, most of it
the CPU-load query. A dirty tree is reported but not refused, so a run can
still be taken against uncommitted code — it just says so. And the conditions
describe the start of a run, not the whole of it: a machine that gets busy
half way through still reports the load it began with.
