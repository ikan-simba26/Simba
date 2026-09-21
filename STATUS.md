# Status

Per module: what is done, what is in progress, what is open, and what is
actually blocked and on whom. **Update at the end of every task.**

Owners are from `CLAUDE.md`. **"Blocked" means work cannot proceed until a
named person or external thing acts.** Something nobody has done yet is
*open*, not blocked. Until 2026-09-17 this file mixed the two, and several
items sat under "blocked on quota" for eight days after the quota had reset.

**Last updated:** 2026-09-20 · **399 passing, 3 skipped** · suite wall clock 720s. Only 3 skipped because a host happened to be running, so the five Electron tests ran rather than skipping; without one it is 8 skipped (5 host, 2 `SIMBA_LIVE_TESTS=1`, 1 `SIMBA_HOST_TESTS=1`). Earlier runs of smaller suites took 329s, 367s, 438s, 459s and 711s on the same machine. Steps, counts and pass rates are the figures to read here; a wall clock from this machine carries about ±2x (EVALUATION.md, 2026-09-17h)

---

## Where the project actually is

The walking skeleton runs end to end on three flows — two replicas we wrote,
and one live public site.

**An LLM run has finished a live task correctly, for the first time**
(EVALUATION.md, 2026-09-17f). Railways, through the real Electron window, 8
model calls, $0.000847: both stations committed, the calendar navigated to
October, the 15th picked, and the search sent for `2026-10-15`. The run
before it, earlier the same day, did the same and was stopped by durable
verification on a date the page had only reformatted (2026-09-17b); a value
matching the task's declared `About.holds` is now accepted, and that is the
difference between the two runs.

**A closing screen now shows the answer, and it shows all of it.** The live
results' heading strip was extracted as a table of its own, so nothing paired
`Train No.` with a train; joining them fixed it (2026-09-17i), and on
2026-09-18 a finding carries *every* value for a label rather than the first,
so a two-train search reads `2DN, 14DN` (2026-09-18b).

**The perception figures are confirmed in the environment that runs them.**
Every figure in EVALUATION.md before today was measured headless; the
scrollbar-spacer defect existed only in the Electron host. All three sites
were re-read both ways on 2026-09-18 and **no serialized figure differs** —
though the host's raw markup does still carry the spacer, so it was a standing
difference and not a bad day on the live site (2026-09-18c).

**A published benchmark figure does not reproduce, by 2x, and the cause is
the machine.** The hardcoded plan's 5.9s from 2026-09-06 re-runs at 3.0s on
that very commit — and at 3.93s and 6.85s the same day on the same tree
(2026-09-17h). Code and venv were ruled out; what is left is the environment.
Steps and model calls are now the primary metrics, wall clock secondary with
its range (DECISIONS.md). Every conclusion in EVALUATION.md that rested on a
time difference has been audited: none is withdrawn, one now stands on its
mechanism rather than its seconds.

**Both channels exist now, and nothing reads either.** Channel A is the
page: nine raw features per step. Channel B is the person: hesitation, cursor
path ratio, backtracks, re-reads and help presses, sent by the overlay on
every step response and on a 3s timer while a step waits — `telemetry` had
been in CONTRACT.md since 2026-09-04 with no sender. Every sample is written
beside the page features of the step it belongs to, in `data/steps.jsonl`,
which is **not committed** because it carries the goals a person typed
(2026-09-20c). No score, no weights, no user data collected yet.

**Bounds are CSS pixels everywhere.** `snapshot.parse` converts on the way in,
so overlays, interactivity, content and the estimator all read the same units
as the frozen viewport. Every recorded perception figure was re-measured in
both environments afterwards and **not one moved** — but `MIN_COVERAGE = 0.30`
has been behaving as **0.133 in the host** since the rule existed, because a
box 1.5x too large covers 2.25x the area. The registration modal read a
coverage of **2.220** before the fix and 0.986 after (2026-09-20).

**The estimator measures nothing about a person yet.**
`backend/estimator/page_features.py` reads nine raw features off one page
read — counts, a density, a depth, a dead-link ratio and a Flesch-Kincaid
grade — with **no score, no weights and no normalisation**, because those need
a corpus to calibrate against. `data/corpus.json` is the first one: 20 public
pages, read in both environments, 0 failures. **Three of the nine features
cannot tell those pages apart** and are flagged as such (2026-09-19b).

**A closing screen shows every result now, checked on the live site.** A
finding carries both the one line the step screen shows and the list the
ending shows; a two-train search put both trains and both journey times on the
screen, and the site view confirmed nothing was missing (2026-09-19).

**The project's headline perception finding is smaller than it read.**
"What perception emits decides what a planner can use" is split in two: emitting
what the input does not contain (occlusion, date qualifiers — 10/10 runs, and
a distinction no prompt could supply) holds; moving words the prompt already
carries above the element list is **falsified as stated** at 0 of 8 runs
(EVALUATION.md, 2026-09-18).

**Every ending reached from a step was unpressable** — found and fixed on
2026-09-17, present since at least `cc4704f`. After any step, an invisible
leftover of the step screen covered the ending's buttons (EVALUATION.md,
2026-09-17c).

The hardcoded plan last completed the live flow on 2026-09-09 (54s). Not
re-run since; the live page's structure was unchanged when re-read on
2026-09-17.

What the system cannot do is trust its own result: the DOM is not the
application's state (EVALUATION.md).

### Changed on 2026-09-21

- **The typed goal decides what happens.** Routed before anything runs: one
  call to the configured model, keywords without a key, quota or answer in
  8s. "hello" is greeted with what SIMBA can do, "book a flight" is declined
  with the same, an ambiguous goal is asked about, and a request for a flow
  runs it. `SIMBA_FLOW` no longer chooses the task. Verified through the real
  stack on billing and railways (EVALUATION.md, 2026-09-21).
- **`goal.answered`** added to the contract, pending ratification; `task.start`
  gains an optional `flow`; an empty goal is now greeted, not run.
- **The mock routes as the backend does**, and plays each flow from its real
  plan.
- **The overlay has a design system**: tokens, a light and a dark theme, one
  focal size per screen, the step as a card, a wordless presence mark, the
  answer as the hero. Every screen captured before and after in both themes
  (`tools/screenshots.py`).
- **Launchers start both replicas** for every real flow.

### Changed on 2026-09-20

- **CSS pixels at the source** (`snapshot.parse`), with every recorded
  perception figure re-measured in both environments: none changed
  (2026-09-20).
- **What `MIN_COVERAGE` has actually been measuring**, per environment, stated
  in EVALUATION.md — 0.30 headless, 0.133 in the host.
- **The corpus is 34 pages**, including both replicas, `/stubborn`, the live
  site with its dropdown and calendar open, and seven application-like public
  pages. `dead_link_ratio` and `form_fields` are no longer flat; `overlays`
  and `inferred` still are (2026-09-20b).
- **`controls` is one feature** where `interactive` and `links` were two, with
  both counts and `link_share` kept.
- **Channel B is sent and recorded** (2026-09-20c): `frontend/src/telemetry.ts`,
  `backend/estimator/pairing.py`, `data/steps.jsonl`.
- **`feat/estimator-features-and-every-result` merged**; `main` at `d239126`.

### Changed on 2026-09-19

- **Every result on the closing screen**: `Finding.values`, additive and
  optional in the contract; verified live through the host (2026-09-19).
- **`backend/estimator/page_features.py`**, nine raw features, 27 tests.
- **`tools/evaluation/collect_corpus`** and the first corpus: 20 pages, both
  environments, `data/corpus.json` (2026-09-19b).
- **Bounds are device pixels**, found by the two-environment rule. The
  estimator converts; perception still does not (below).
- **`PageView` carries the parsed snapshot**, so a caller that needs the page
  itself works from the same read.
- **`feat/evaluation-limits-and-all-results` merged**; `main` at `d455ad2`.

### Changed on 2026-09-18

- **A finding carries every result**, not the first: `values_for`, and
  `voice.found` showing four values and a count (2026-09-18b).
- **Every site read twice**, headless and in the host: no serialized figure
  differs, the raw markup does (2026-09-18c). New script,
  `tools/evaluation/viewport_perception_probe`.
- **The prominence rule narrowed** to what the evidence supports, with the
  position sub-claim withdrawn rather than caveated; `llm.py`, HANDOVER.md and
  DECISIONS.md brought into line.
- **Two limitation sections added** to EVALUATION.md — measurement
  environment, and wall-clock reliability with the audit of what rested on it.
- **`feat/evaluation-conditions-and-recovery` merged** and `main` pushed at
  `c33f106`.

### Changed on 2026-09-17 (third pass)

- **The benchmark discrepancy investigated** and the published figure
  corrected (EVALUATION.md 2026-09-17e).
- **Durable verification accepts a value the task declared** — and is
  unchanged, false stops included, on every field the task did not declare
  (DECISIONS.md).
- **Every ending is also tested through a step**, including the stuck ending
  in the one message order that exposed it (EVALUATION.md 2026-09-17g).
- **The railways LLM run through the Electron host** (2026-09-17f).
- **The day's work committed**, one commit per item.

### Changed on 2026-09-17 (second pass)

- **Evaluation scripts are in the repository**, `tools/evaluation/`, committed
  as `7d7bc5d` on `feat/orchestrator-evaluation-scripts`, with a table in
  EVALUATION.md mapping each result to its script. Two re-run to check: the
  billing perception probe reproduces exactly; the hardcoded benchmark
  reproduces its outcome at half its recorded time.
- **The owed LLM run**, above.
- **The stuck screen says what happens**: "I'm stuck, so I've stopped." /
  "I won't do any more on this. You can ask me for something else."
- **Pressing "Stop this" is its own ending**, "I've stopped, as you asked.",
  not a failure.
- **Endings after a step can be pressed.**
- **Stale documents**: `README.md` (test count, start command),
  `frontend/README.md` (no longer calls the overlay a harness), and
  `CLAUDE.md` / `README.md` no longer claim `ruff` + `black`, which were never
  installed.

---

## Perception — Nahail · `backend/perception/`

**Done**
- Page to numbered `Element` list from the accessibility tree plus a DOM
  join; password inputs distinguishable.
- Structural overlay detection, page-level and target-scoped.
- Non-semantic interactivity: controls with no role, found from layout,
  flagged `inferred`. Qualifiers (`previous month`, `next month`, `disabled`,
  `today`) and panel headings (`IT IS SHOWING: 2026 September`).
- **The panel heading changed a model's decision** in the 2026-09-17 run: it
  pressed Next Month where both 2026-09-09 runs, without the banner, did not.
  One run.
- Content extraction: headings, table rows paired to headers, label/value
  pairs, prominent values.
- Form values, dead-link flagging, one shared snapshot parse, ablation
  switches.
- Re-read on 2026-09-17: 66 / 39 / 18 elements on the registration replica,
  billing replica and live site — each matching its first measurement. The
  billing probe reproduces its 2026-09-06 table exactly.
- **Re-read again on 2026-09-18, in the Electron host as well as headless**,
  with every figure identical in both and matching its first measurement:
  66/1/65/44, 39 with `P/WITHIN → 14,382`, 18/4/3, and the live results
  joining 4-wide in both (2026-09-18c).
- A label's every value, not its first: `values_for`, with `voice.found`
  showing four and a count.
- `PageView` carries the parsed snapshot the read was built from.

**In progress**
- Nothing.

**Open — Nahail's call**
1. **The DOM is not the application's state.** No defence except driving
   widgets the way a person must.
1b. ~~A snapshot's bounds are in device pixels, and every caller has to know
   it.~~ **Fixed 2026-09-20**: `snapshot.parse` converts, `Document` records
   the ratio, and every recorded figure was re-measured in both environments
   without moving. What it leaves behind is a threshold question, below.
2b. **`MIN_COVERAGE` has been two different numbers, and is now one.** As
   written it is 0.30 of the viewport; in the host it behaved as **0.133**,
   because a box 1.5x too large in each direction covers 2.25x the area. So
   the host has been *more* sensitive to mid-sized blockers than the code
   said, and since the fix it is less sensitive than it was yesterday:
   anything covering between 13% and 30% is no longer flagged there. Nothing
   in the three flows sits in that band — the only page-level blocker we have
   is the registration modal at 98.6% — but **0.30 has never been calibrated
   against real pages**, and the corpus is the instrument for that.
2c. **A full-screen modal with no z-index is invisible to the detector.**
   `the-internet.herokuapp.com/entry_ad` covers 100% of the viewport with a
   `position: fixed` overlay and `z-index: auto`; `MIN_STACK_LEVEL` requires
   5, so neither the page-level nor the target-scoped rule sees it. Found by
   the corpus (2026-09-20b). A fixed element covering the page arguably needs
   no z-index to be on top, and the rule could say so — Nahail's call.
2. A modal's content is skipped along with a dropdown's.
3. Elements with no accessible name are addressable only by ordinal.
4. Panel headings are found by class-name fragment; a picker that names its
   header otherwise gets none, silently.
5. Iframes are not read.
6. Accordion expanded state is discarded.
7. An inferred element's `css_path` is positional.
8. ~~The live railways results have no header pairs.~~ **Fixed 2026-09-17.**
   The site had not changed: a scrolling table's heading strip carries an
   empty spacer cell, so it was one column wider than its rows and the join
   refused. Verified on the live site — a completed run now shows
   `2DN / Train` on the closing screen (EVALUATION.md, 2026-09-17i). What it
   leaves behind: **content extraction had only ever been measured headless**,
   and this failed only in the 1280x800 host.
   ~~So other readings may be viewport-dependent in ways nothing has
   checked.~~ **Checked 2026-09-18**: all three sites read both ways, no
   serialized figure differs (2026-09-18c). The host's heading strip still
   carries the spacer the fix absorbs, so the difference is standing, not
   incidental — and the comparison is shallow, being the serializer's output
   plus the strips' cell counts rather than the DOM. A perception figure now
   says which environment produced it.
9. ~~`value_for` returns the first matching pair, so even when pairing works
   "which trains?" shows one train.~~ **Fixed 2026-09-18** (2026-09-18b).
10. Page-side load features for the estimator: not started.

**Blocked**
- Nothing.

---

## Orchestrator — Raham · `backend/orchestrator/`

**Done**
- **Goal routing** (`router.py`, 2026-09-21): model first with an 8s bound,
  keywords as the fallback, and a small-talk floor under both. 42 unit tests,
  9 over the real app's websocket, 7 over the mock's.
- Shared loop: perceive, decide, present, act, verify, retry differently,
  setback re-plan, `help.requested`. Three planners behind it, asserted
  identical under injected failure.
- LLM providers with validation, retry, backoff, token and cost accounting.
- Trace memory in SQLite, replaying at zero model calls.
- Durable verification; a lapse ends the run.
- `Task.about`: `holds` (values the goal names, checked at the end) and
  `finds` (values it asks for, shown). Required.
- `voice.py`: every fixed string the backend puts on screen, under test.
- **The LLM planner on the live site, 2026-09-17**: stations committed,
  calendar navigated, right day picked, 7 calls, no malformed answers.
- Content-based success, `press`, covered-element refusal, `step.failed`,
  10s action timeout, a railways date that does not expire.

**In progress**
- Nothing.

**Open — Raham's call**
- **The keyword fallback runs one half of a two-part request.** "I have a
  payment due and a class to sign up for" went to billing when the model
  timed out: two bill words beat one class word. Nothing wrong was started,
  but only one of two things asked for was. Options: treat any second flow
  with a strong word as `clarify`; or leave it. Recommended: clarify — it
  costs one extra question on requests that name two things.
- **Routing waits up to 8s on a slow model**, and it did twice in twelve
  calls. The overlay now says so. Lowering the bound sends more requests to
  the keywords; raising it makes the wait longer. Left at 8.
- **`goal.answered` and the empty-goal change need ratifying** by all three
  owners (CONTRACT.md).
- **Durable verification still stops correct runs on undeclared fields.**
  Since 2026-09-17 a field that now holds its task-declared value is accepted;
  every other field is compared with what was typed, character for character,
  so a page that reformats a value there still ends the run. An LLM planner
  types into whatever it chooses, so this is where it will meet it. Options
  and costs in DECISIONS.md.
- ~~Setback placement is unmeasured.~~ **Answered 2026-09-18**, with a
  replica page rigged to fail (`SIMBA_FLOW=stubborn`): across eight runs and
  two page shapes, **where the setback sits changed nothing**. What decided
  recovery was the options the page left — with a plausible wrong button
  present the model took it 4/4 and the run ended in `help.requested`
  (EVALUATION.md, 2026-09-18). That leg of "What perception emits decides
  what a planner can use" (renamed from "Where information sits is a
  perception decision") is now **withdrawn** rather than weakened, and the
  comment beside `build_user_prompt` says the position stays because it costs
  nothing, not because it works. What would settle it is the same rig against
  a stronger model.
- **The held date has never failed a wrong-date run live.** It passed the
  correct date in 2026-09-17f. The wrong-date case is covered only by
  `test_success_conditions.py`.
- **The loop says nothing when it accepts a declared value.** The only
  evidence it happened in 2026-09-17f is that the run did not stop.
- `About` checks only what was declared, only on the final page; `finds` is
  not part of success.
- A move the LLM or replay chose reads as an order ("Click LAHORE CANTT.");
  the same string is the model's history.
- `task.completed.summary` is the goal plus a URL, read by tests, not shown.
- The JS-click fallback clicks through a modal with overlay detection off.
- Trace memory has never recorded and replayed a live model run. Not blocked.
- `requires_confirmation` is always `true`.
- Replay tuning: not started.

**Blocked**
- Nothing.

---

## Interface — Aly · `frontend/`

**Done**
- **Design system** (2026-09-21): `index.css` and `design.ts` tokens for
  colour, type, spacing, radii, shadows and motion; light and dark themes
  from the system; every text pairing measured at AA or better. Home is a
  greeting, three task cards and an ask box; replies (greeting, can't do,
  which one) reuse the same cards; the step is a card at every level; the
  closing screen puts the answer in a card as the hero; a presence mark shows
  the assistant's state without words.
- **The answer no longer pulses on the closing screen**, and **the home
  screen's box no longer hides itself after typing has started**
  (EVALUATION.md, 2026-09-21).
- The window: site view covered by the overlay; CDP on 9222.
- Contract client; every backend-to-frontend type handled.
- One column: home with remembered goals, working, a step at three levels
  folding between them, notices, the trust panel.
- **Five endings, all with a way onward, all pressable after a step**:
  found an answer, done, failed, stuck, stopped by the person.
  `test_terminal_states.py` renders each, including three reached from a
  step, and presses every button.
- **The stuck screen is true** (2026-09-17): the run has stopped, nothing
  more will happen, ask for something else. `test_copy.py` fails if it
  promises to carry on or asks the person to do part of the task.
- **Stopping is not failing** (2026-09-17): the stop ending shows the moment
  stop is pressed.
- All copy in `copy.ts`; the component scan catches any words.
- **Telemetry**, five numbers per step, on the answer and on a timer
  (`src/telemetry.ts`). No keystrokes, no field values, no coordinates leave
  the renderer.
- **The closing screen shows every result**, one per line, shrinking the type
  as the list grows. Verified live: two trains, two journey times, nothing the
  site returned missing from the screen (2026-09-19).

**In progress**
- Nothing.

**Open — Aly's call**
- **The typeface is the system's.** A face designed for low-vision and
  dyslexic readers (Atkinson Hyperlegible) would likely read better for this
  audience; it is a font file, so a dependency, and was not added.
- **The theme follows the operating system** with no choice in the overlay.
- **Three contrast fixes soften deliberate behaviours**: the waiting recede
  0.55 → 0.8, the level-2 step count 0.4 → 0.75, the resting level dots
  0.4 → 0.7. Each was under a contrast rule before.
- **Nobody from the audience has seen the redesign.**
- **"I'm done" and "Do something else" go to the same place.**
- **The stuck screen still shows the technical reason** in small type. In the
  2026-09-17 run that reason would have told the person the date had been
  lost, when it had been set correctly.
- **An LLM "Fill in" step still shows an empty field.** Since 2026-09-17 an
  empty answer no longer overrides the model's value (DECISIONS.md), so the
  defect is closed, but the step still asks the person to approve a field that
  does not show what is about to be typed. Pre-filling it belongs with the
  credential vault.
- **"Click element 13."** reached the screen in the watched run.
- **A long list of results scrolls the ending.** The overflow guard drops a
  detail level when a *step* will not fit; the closing screen has no such
  guard, so past roughly eight values the answer runs off the bottom. Nothing
  has measured where the line is.
- **The step screen shows one finding**, as one line that stops at four
  values. That is the design, not an oversight — but it means a run in
  progress can show "and 2 more" for a while before the ending shows them.
- "I'm showing a bit more again." is also what an overflow drop says.
- "Step 2 of 6" uses a word `copy.ts` forbids.
- A found value is shown as the page wrote it (`15-09-2026`).
- Home-screen history is stale after a task (`CONTRACT.md`).
- A backend that dies mid-task leaves "Give me a moment." on screen with
  nothing to press.
- Nothing chooses a level automatically; only the mock sends `load.updated`.
- The credential vault is not built. Voice input is not built.

**Blocked**
- Nothing.

---

## Estimator — Nahail · `backend/estimator/`

**Done**
- **The page-side features**, raw: `controls`, `inferred`, `text_density`
  (characters per 1000px² of the viewport), `max_depth`, `overlays`,
  `form_fields`, `dead_link_ratio`, `reading_grade`, plus the raw counts they
  are built from — `links`, `non_link_controls`, `dead_links`, `link_share`,
  characters, words, sentences, syllables. 28 tests, arithmetic and browser.
- **The corpus**: 34 pages — both replicas, `/stubborn`, the live site in
  three states, twenty public pages and seven application-like ones — read in
  both environments, 0 failures (`tools/evaluation/collect_corpus`,
  `data/corpus.json`).
- **Channel B**: the overlay sends telemetry on every step response and on a
  3s timer; the loop pairs each sample with the page features of that step and
  appends a row to `data/steps.jsonl` (`backend/estimator/pairing.py`). 14
  tests: 8 on the pairing, 6 driving the built overlay in a browser.

**Open — Nahail's call**
1. **No score, and deliberately so.** Weights need a calibration and there is
   no user data at all. What exists is measurement (DECISIONS.md).
2. **Three features carry no signal on the corpus**: `overlays` is 0 on all
   20 pages, `inferred` on 18, `dead_link_ratio` on 16. The overlay result is
   the detector being right — public sites put cookie banners *in* the page
   flow, not over it — so what it needs is a corpus with real modals in it,
   which means our own replicas and applications rather than front pages.
3. **`links` and `interactive` are nearly the same signal** on these pages.
   Two features carrying one signal is a weighting problem waiting to happen.
4. **Reading grade is the narrowest real spread** (3.91–13.68, CV 0.27) and
   the most heuristic number here: block-counted sentences and a vowel-group
   syllable counter (DECISIONS.md).
5. **Nothing consumes either channel.** The rows accumulate; no score reads
   them, and `load.updated` still only ever comes from the mock.
6. **No user data exists.** Every telemetry number so far came from a test
   driving a browser. Whether any of the five separates a page someone coped
   with from one they did not is the whole question and is unmeasured.
7. **The definitions are starting guesses**: 8px of movement, ~120° of turn, a
   3s timer, "re-read" as the pointer re-entering the text. All in
   `frontend/src/telemetry.ts` so they can be moved together.
8. **`data/steps.jsonl` grows without bound** and has no rotation.

**Blocked**
- Nothing.

---

## Shared contract — all three owners · `shared/`, `CONTRACT.md`

**Done**
- Both schema files mirror every message. `step.failed`, `findings` and
  `history.offered` added; `history.offered` recorded as pending
  ratification with its reasoning and costs.
- **`Finding.values`** added 2026-09-19: every value for a label, beside the
  one-line `value`. Additive and optional, which CLAUDE.md allows without a
  ratification session — a sender that omits it means `[value]`.
- **`Telemetry.answered`** added 2026-09-20, same rule: true on the sample
  that goes with the response, absent on a timer sample. CONTRACT.md now also
  says how each of the five numbers is measured.

**Open**
- ~~`telemetry` is specified and nothing sends it.~~ **Sent since
  2026-09-20**, and recorded. Nothing reads it back yet, which is the
  estimator's item and not the contract's.
- The examples for `step.presented` ("Not now") and `help.requested` ("Can
  you click it for me? I'll carry on from there.") no longer match what the
  system says. Left for the ratification session.

**Blocked**
- **Ratifying `CONTRACT.md`**, a draft since 2026-09-04, including
  `history.offered`. **Blocked on Nahail, Raham and Aly meeting together** —
  the one item in this file that genuinely cannot move until specific people
  act.

---

## Evaluation · `EVALUATION.md`

**Done**
- Benchmarks, ablation, A/B, costs, six cases of verification passing wrongly,
  the live-site entries.
- **Every table mapped to a committed script** (`tools/evaluation/`), except
  three recorded as having none.
- **The owed LLM run** (2026-09-17b), the unpressable endings (2026-09-17c),
  and the formatter measurement (2026-09-17d).

**Open**
- **The stronger-model ablation has not been run.** Previously "blocked on a
  paid API key". It is not blocked: it needs roughly 100 model requests, which
  a free tier spreads over several days and a paid key does in one sitting.
  Which free-tier limits apply is uncertain — this file and EVALUATION.md have
  recorded contradictory quotas. The 2026-09-17 run hit no rate limit.
- No LLM run against the billing flow. No LLM baseline on an unseen goal.
  Neither is blocked.
- ~~**The 5.9s hardcoded figure does not reproduce** and is corrected; its
  cause is not established.~~ **Explained 2026-09-18** as far as this machine
  allows: 3.01s, 3.93s and 6.85s in one day on one tree is a 2.3x
  environmental spread, and 5.93s sits inside it (2026-09-17h). Steps and
  model calls lead every result now; wall clock follows with n, range and
  conditions (DECISIONS.md). **The audit is done**: no conclusion is
  withdrawn, the ~25s overlay-detection cost stands on its mechanism rather
  than its seconds, and the per-phase perception deltas (0.19s against 0.22s)
  are withdrawn as a difference. The LLM timings from 2026-09-05 were taken
  the same way and have not been re-run, so their absolute seconds are not
  today's.
- **Two limitations are now stated rather than implied**: what environment a
  perception figure was measured in, and what a wall clock from this machine
  is worth.
- **The corpus is 34 pages read once.** Enough to choose features and to
  show which carry no signal; nowhere near enough to calibrate a score. Five
  of its rows are pages we wrote, so a feature that separates our replicas
  from the world may be measuring our HTML habits.
- ~~Evaluation scripts record a number and nothing about the conditions.~~
  **Fixed 2026-09-17**: every script prints its conditions and the three that
  write result files record them (`tools/evaluation/conditions.py`). It
  immediately showed the same benchmark at 6.85s where it had been 3.01s
  hours earlier, so **the 5.9s is now best explained as the machine, not the
  code** (EVALUATION.md, 2026-09-17h). Any duration from this machine reads
  ±2x without a conditions block beside it.
- EVALUATION.md still contains statements its later entries contradict,
  listed in its 2026-09-17 entry.

**Blocked**
- Nothing.

---

## Infrastructure

**Done**
- Two replicas and one live flow; `run.ps1` / `run.sh`; `tools/screen_site.py`,
  `tools/mock_backend.py`, `tools/evaluation/`, `spike/`.
- The test suite from the repo root; `test_terminal_states.py` builds the
  overlay from source.
- `README.md` and `frontend/README.md` match the project as of 2026-09-17.

**Open**
- No CI. The Electron tests skip silently without a host.
- Nothing supervises the Electron host.
- `test_levels.py` measures `dist/`, which can be stale.
- **No formatter or linter.** `black` would reformat 46 of 57 Python files;
  `ruff` reports 69 findings. Adopting them is for all three owners.
- The venv is Python 3.12.3; `CLAUDE.md` says 3.11.
- `main` is at `d455ad2` (2026-09-18's work, merged and pushed). 2026-09-19's
  work is on `feat/estimator-features-and-every-result`, not merged.
- `tools/evaluation/host_overlay_run` drives the overlay of a running stack,
  which is how an interface claim gets checked live. It presses the step's own
  primary action and nothing else.

**Blocked**
- Nothing.
