# Status

Per module: what is done, what is in progress, what is open, and what is
actually blocked and on whom. **Update at the end of every task.**

Owners are from `CLAUDE.md`. **"Blocked" means work cannot proceed until a
named person or external thing acts.** Something nobody has done yet is
*open*, not blocked. Until 2026-09-17 this file mixed the two, and several
items sat under "blocked on quota" for eight days after the quota had reset.

**Last updated:** 2026-10-01 · **776 passing, 12 skipped** · suite wall clock 1222s, on `feat/multi-october-pipeline-and-demo`. 34 tests added today. The 12 skips are unchanged: 5 needing a running Electron host, 2 needing a host **and** `SIMBA_HOST_TESTS=1`, 3 that open the host themselves and need `SIMBA_HOST_TESTS=1` (`frontend/test_window_fit.py`), and 2 needing `SIMBA_LIVE_TESTS=1`. Earlier runs of smaller suites took 329s, 367s, 438s, 459s, 656s, 711s, 729s, 762s, 827s, 1001s and 1081s on the same machine. Steps, counts and pass rates are the figures to read here; a wall clock from this machine carries about ±2x (EVALUATION.md, 2026-09-17h)

---

## Where the project actually is

The walking skeleton runs end to end on three flows — three replicas we wrote,
and one live public site.

**Every flow runs on the person's own details now, and asks for what they did
not say** (2026-09-30). Until today a goal was a label: "trains to Rawalpindi
tomorrow" searched Lahore Cantt to Karachi Cantt on the 15th of next month,
because that is what the plan said, and the closing screen showed real trains
for a journey nobody had asked about. The goal is read for what it states, the
rest is asked for one question at a time, and the run is judged against what
the person said — so a search for another route or another day fails rather
than completes. Checked live six times through the Electron host: "trains to
Rawalpindi tomorrow" asked **where from** and nothing else, `Lahore` brought
back the site's own `Lahore Jn.` and `Lahore Cantt`, and the station pressed is
the one the live site searched — three trains back for Lahore Cantt to
Rawalpindi on the 1st of October, all three on the closing screen
(EVALUATION.md, 2026-09-30).

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

**The level adapts in a real run now, by provisional rules** (2026-09-25).
A heavy first page starts at level 3; a long pause, a wandering pointer or a
help press folds the step on screen one level simpler; two calm steps bring
it back; a lock holds. Checked live on billing through the Electron host:
folded at 8.0s (pointer) and 18.3s (still), came back on the ending, lock
held across two tasks (EVALUATION.md, 2026-09-25). The rules are hand-written
guesses standing in for the estimator, not the estimator.

**Both channels exist now, and until 2026-09-25 nothing read either.** Channel A is the
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

### Changed on 2026-10-01: the training pipeline, one attempt, the recordings

- **Merged and pushed.** `feat/multi-october-readiness` is in `main`
  (`85bbf69`). The rest below is on `feat/multi-october-pipeline-and-demo`,
  **not merged**.
- **A mistyped place is reported in 16.7s**, not 31.5s: a step that waits on a
  list gets one attempt. An exception to CLAUDE.md's retry rule, and CLAUDE.md
  does not yet say so (2026-10-01).
- **The estimator's training pipeline exists and has trained nothing.**
  `python -m backend.estimator.train` measures agreement, averages per page,
  fits a ridge regression, cross-validates, and refuses fewer than ten raters.
  No person has rated a page, so today it says where ratings come from and
  stops. Checked on synthetic ratings only, and those can never be written as
  the model or into EVALUATION.md (2026-10-01b).
- **scikit-learn is a dependency** (with numpy, scipy, joblib), installed in
  `backend/venv` and named in `backend/requirements.txt`.
- **The demo clips are re-recorded on our copy of the train search**, answering
  the questions; the recorder refuses to record railways on the live site. All
  three task clips ended on an answer found (2026-10-01c).

### Changed on 2026-09-30 (later): six items, one branch

- **Merged and pushed.** `feat/orchestrator-person-details` is in `main`
  (`ec6adca`). The rest below is on `feat/multi-october-readiness`, **not
  merged**.
- **A station list gets fifteen seconds, not five** (`Expectation.list_opens`,
  `LIST_TIMEOUT_S`). On the replica with its list 8s late, the old window
  reproduced the live failure word for word; the new one searched. The cost: a
  place with no station takes 31.5s to report, not about 11.6s
  (EVALUATION.md, 2026-09-30b).
- **`railways-local`** opens the window on our own copy of the train search and
  runs train goals there. Checked through the window: the same seven screens as
  live, nothing sent to the live site. Rehearsals use it (DEMO.md).
- **Two corrections to yesterday's record**: six live runs, not five; and every
  one made two model calls, routing and reading the goal, where the record said
  none (2026-09-30c).
- **CLAUDE.md's phase is October's**, as approved, and Python is 3.12.
- **The home screen fits with history.** Six cards had put the text box off the
  window at every scale once three goals were remembered; the fit test never had
  history, so never saw it. One list of three now; worst case, the box ends at
  576 of 606 at 150% and nothing scrolls (2026-09-30d).
- **The site view lays out at 1280px.** Its scrollbars are hidden; before, a
  page that scrolled laid out at 1263 in the host (2026-09-30e).
- **`MIN_COVERAGE` is 0.27**, the middle of the empty band; no result on the
  corpus changes (2026-09-30f).
- **`text_density` reads where the page is scrolled to**, and the corpus is
  re-collected: headless and host now differ on 9 of 48 pages, not 14 of 49;
  both Wikipedia pages read the same; the first page in the 0.27–0.30 band is
  measured, a drawer at 0.295 (2026-09-30g).

### Changed on 2026-09-30: every flow runs on the person's own details

- **A goal is read for what it says, and what it does not say is asked for.**
  Where from, where to and which day; a reference number; a course code
  (`details.py`). The configured model reads it with the same 8s bound routing
  has, and a keyword and date reader does when there is no model — so it works
  offline, in the tests and on demo day. Nothing the model reports is kept
  unless it can be held to what the person typed: an invented reference number
  looks exactly like a real one and opens somebody else's bill.
- **Whatever is missing is asked, one question at a time**, as an ordinary
  `step.presented`, with the site open behind the questions and nothing on it
  touched until every answer is in (`loop.run_brief`). Buttons where the
  answers are few, one box otherwise, and the same way to stop underneath.
  Three unusable answers end the run the way being stuck does. **No contract
  change**: an answer's id is an id the step offered, which is all
  `CONTRACT.md` requires.
- **The train search runs the person's journey** (`TripPlanner`). Places are
  matched against the site's own station list: one match is taken, up to four
  are asked about as buttons, more are asked to be narrowed, none stops the
  run. Checked live: `Lahore` brought back `Lahore Jn.` and `Lahore Cantt`,
  and the one pressed is the one the site searched — `LHR` for Jn., `LRC` for
  Cantt, different trains each time (EVALUATION.md).
- **The journey is said back in one sentence before anything is searched** —
  "Trains from Lahore Cantt to Rawalpindi on 1 October. Shall I search?" — so
  a wrong search can be stopped by the person rather than reported afterwards.
- **A search for the wrong route or the wrong day now fails.** `holds` matches
  a place the person's way and the date exactly; `shows` covers a value that is
  in no field by the end — the bill's reference number, the course code — by
  checking what the site said back about it. Four rigged runs on real pages all
  ended in `help.requested` with real results on screen (EVALUATION.md).
- **A step can be answered, not only agreed to.** The overlay showed its stop
  screen for any answer but go-ahead, so pressing "Tomorrow" ended the run; and
  `StepShell` rendered exactly two buttons, so a three-answer question dropped
  the third answer *and* the way to stop. Both fixed, both rendered in a real
  browser by `frontend/test_questions.py`.
- **The count on screen no longer moves while the person answers.** It read
  "1 of 7" then "2 of 5" in one run. Found by running it, not by a test; there
  is a test now.
- **Found on the live site, not fixed: a station list that does not arrive
  looks like a place with no stations.** 1 of 5 live runs. The sentence now says
  what was observed rather than guessing a cause.
- **The billing replica made its own new check meaningless** — its results page
  printed the worked example's reference number whatever had been looked up.
  It echoes the number that was searched.
- A local train-search replica (`replicas/railways/`), because this planner
  needs many runs and CLAUDE.md keeps those off the live site.

### Changed on 2026-09-27: the 100% capture problem is real

- **Site-view captures at a real 100% succeed 10/20**, alternating, exactly
  as at forced 100%. A page that repaints every frame captures 20/20, so the
  capture waits for a frame an idle page never produces. `page.preview` will
  fail about half the time on 100% machines. **Open, not fixed**
  (EVALUATION.md, 2026-09-27).

### Changed on 2026-09-25 (last): text at full size, the guard, the notice, ratings

- **The overlay is no longer zoomed.** It lays out at the window's real size
  (1266x606 on a 1080p laptop at 150%), and below 760px tall the layout is
  compact. Nothing on the home screen is under 20px at any scale, and no
  screen of billing or registration overflows at 100%, 125% or 150%
  (EVALUATION.md, 2026-09-25c). Zoom is reset to 1 on every load: Chromium had
  remembered 0.757.
- **The overflow guard reports its moves** (`level.override`, `by:
  "overflow"`, additive in CONTRACT.md), and a guard move under a lock lasts
  one step. A lock is only ever the person's own level.
- **The level notice floats** over the card's top edge instead of pushing
  the screen down.
- **CLAUDE.md** now says the site view may extend past the window but is
  never positioned outside it (approved).
- **`tools/rating/`**: 50 corpus pages photographed at 1280x800, and a rating
  session (1–7, two repeats) writing `data/ratings.jsonl`. No ratings
  collected yet.
- **main** carries the level rules (`21f5691`) and the window fit
  (`2950e10`), pushed. This task's work is not committed.

### Changed on 2026-09-25 (later): the window fits the screen

- **The window never exceeds the screen's work area.** On a 1080p laptop at
  150% it is 984x672 inside 1280x672, and the home screen's text box is on
  screen. The overlay is zoomed to fit and still lays out at 1280x800 CSS; the
  site view is untouched, 1280x800 CSS at every scale (EVALUATION.md,
  2026-09-25b). The window is no longer resizable.
- **`tools/evaluation/display_fit_run.py`** measures it at forced 100/125/150%
  and at the real scaling. **`frontend/test_window_fit.py`** asserts it,
  behind `SIMBA_HOST_TESTS=1`.
- **Open, flagged:** CLAUDE.md's "never size the view outside its parent" and
  "identical bounds" no longer describe the host below 1:1. Site-view captures
  at forced 100% are 10–11/20, and were before the change as well. A real
  100% machine has not been tried.

### Changed on 2026-09-25

- **The level adapts live.** `backend/estimator/rules.py`, provisional, on
  by default (`SIMBA_ADAPT=0` turns it off). The backend sends `load.updated`
  at the start, on a fold, and on a return. Every decision is logged with its
  inputs to `data/steps.jsonl` as a `"kind": "decision"` row. All thresholds
  are in one dataclass and recorded in DECISIONS.md as guesses.
- **A lock survives a new task.** The overlay re-sends it before `task.start`,
  and the backend now reads `level.override` before a task starts.
- **The launchers' argument is the start page.** `run.ps1 -StartPage` (the old
  `-Flow` still works) and `run.sh`'s first argument; they no longer set
  `SIMBA_FLOW`. README, RUNNING, DEMO and ARCHITECTURE say so.
- **DEMO.md: rehearse from the recordings**, and run live railways only for
  the real demo. It also warns that the screen now folds if the presenter
  lingers or presses "What are you doing?".
- **A fifth clip**, `demo/adapt.webm`: billing, hesitating until it folds,
  then back. Not committed, like the others.
- **The suite no longer writes to `data/steps.jsonl`** (`backend/conftest.py`).
- **Open, flagged:** the overflow guard moves the other way (to level 1),
  overrides the lock, and is invisible to the backend. The return notice
  overflows billing's ending. The contract still says nothing reads telemetry.

### Changed on 2026-09-23

- **`main` has the scale-and-trust branch**, fast-forwarded and pushed.
- **There is a script for showing SIMBA to someone**: `DEMO.md`, five minutes,
  with the exact commands, the exact goals to type, what to point at on each
  screen, and what to do when the live site, the internet or the host fails.
  It opens on the real railways page, so the audience meets the clutter before
  the alternative.
- **Four recordings back it up**: `tools/record_demo.py` drives the real stack
  and the mock and keeps `demo/*.webm` — a clean railways run, a billing run,
  "hello" being greeted, and the mock's level fold. The clips are gitignored;
  the recorder and `demo/README.md` are committed (DECISIONS.md, 2026-09-23).
- **`README.md` installs the project from nothing**: prerequisites with the
  versions actually used, a check after each install, both shells, the optional
  key, and the failures that cost a newcomer an hour — `ELECTRON_RUN_AS_NODE`,
  a busy port, pytest run from the wrong directory.
- **The skip count here was one test out of date.** It is 5 needing a running
  Electron host, 2 needing a host and `SIMBA_HOST_TESTS=1`, 2 needing
  `SIMBA_LIVE_TESTS=1` — 9, not 8.

### Changed on 2026-09-21

- **Later the same day:** `main` has the design branch and the perception
  branch (479 passed, 9 skipped on the merged tree). The mock showed the bill
  due "15 October 2026" — invented demo data; the replica and the product say
  15-09-2026 — and is now pinned to the replica by a test. The overlay is
  scaled about 27% for its audience in Atkinson Hyperlegible Next, with the
  text box always on the home screen, "What are you doing?" as a button, and a
  close-up in the trust panel. The keyword fallback asks when two flows are
  named (EVALUATION.md, 2026-09-21b).
- **Three overlay-detector defects fixed**, all found by adding partial-coverage
  pages: a scroll-locked `body` read as a blocker (coverage 27.17); coverage
  counted area below the fold; and the first fix for that clipped to the top
  of the page and zeroed every driven full-screen modal. Coverage is now
  on-screen area at the page's scroll position (EVALUATION.md, 2026-09-20e).
- **The corpus is 50 pages and read in both environments.** `overlays` agrees
  on all 49 comparable pages; 16 differ elsewhere, most from live content and
  five from the host's **1263px** layout width (a classic scrollbar).
- **The 0.30–0.50 coverage band is occupied** — bottom sheet 0.461, sticky
  banner 0.369, side drawer 0.3125 — and 0.30 still separates everything,
  now by 0.013.
- **`MIN_STACK_LEVEL` measured**: the data bounds it to 3–2001; kept at 5.
- **First labels**: `data/labels.json`, **4 of 50 pages**, all passes.
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

- **`MIN_COVERAGE` is measured**, not guessed: 45 pages, 96 candidates, every
  real blocker at 1.000 and the largest non-blocker at 0.234, with nothing
  between. Kept at 0.30 (2026-09-20d, `tools/evaluation/overlay_coverage_probe`,
  `data/overlay_coverage.json`).
- **A fixed or sticky element covering the page is a blocker without a
  z-index.** `the-internet/entry_ad` is detected at last; it is the only page
  in the corpus whose detection depended on the change.
- **`interactive` and `links` are two features again**, disjoint this time,
  with `controls` kept as their total. The merge made this morning is recorded
  as instructed, implemented and reversed (DECISIONS.md).
- **The corpus is 45 pages**, eleven of them new application-like ones, and
  every row carries a `kind`: 19 public, 18 demo, 5 ours, 3 target. `inferred`
  is no longer flat; `overlays` still is, on 37 of 45.
- **CSS pixels at the source** (`snapshot.parse`), with every recorded
  perception figure re-measured in both environments: none changed
  (2026-09-20).
- **What `MIN_COVERAGE` has actually been measuring**, per environment, stated
  in EVALUATION.md — 0.30 headless, 0.133 in the host.
- ~~**The corpus is 34 pages**~~ superseded the same day; see above.
  `dead_link_ratio` and `form_fields` stopped being flat here (2026-09-20b).
- ~~**`controls` is one feature** where `interactive` and `links` were two.~~
  **Reversed the same day** on the corpus's own evidence.
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
- **Overlay detection measured against a corpus** rather than against the
  replicas alone: `overlays.candidates` is the candidate set as a named thing,
  and `tools/evaluation/overlay_coverage_probe` enumerates it with no
  threshold so the distribution can be read (2026-09-20d).
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
2b. ~~**`MIN_COVERAGE` has been two different numbers**, and 0.30 has never
   been calibrated against real pages.~~ **Measured 2026-09-20d** over 45
   pages and 96 candidates. The corpus is bimodal with an empty middle: every
   real blocker covers **1.000**, the largest thing that is not one covers
   **0.234** (a docs sidebar), and nothing lies between. Kept at 0.30.
   What it leaves behind, and it is deliberately not written as settled: the
   measurement **bounds** the value rather than choosing it — anything in
   (0.234, 0.90] behaves identically — and the reason the middle is empty is
   that **every modal in the corpus is full-screen**. No drawer, bottom sheet
   or 40% consent wall has ever been measured by this project. The first one
   is the first real test.
2c. ~~**A full-screen modal with no z-index is invisible to the detector.**~~
   **Fixed 2026-09-20d.** `fixed` and `sticky` now reach the page-level rule
   on their position alone; `absolute` still has to declare a z-index,
   because it sits in normal paint order. `entry_ad` is detected, and is the
   only page in the corpus that needed the change. What it leaves behind:
   **the two rules no longer share a candidate set** — the target-scoped rule
   still wants a declared z-index, so a small fixed element with no z-index
   sitting on the element a step needs is still invisible to it. Widening it
   would admit every decorative full-screen layer with `pointer-events:
   none`, which perception cannot see at all (`pointer-events` is not in
   `COMPUTED_STYLES`). Flagged, not taken — Nahail's call.
2d. ~~**`MIN_STACK_LEVEL = 5` is as unmeasured as 0.30 was.**~~ **Measured
   2026-09-21.** It decides no page-level verdict in the corpus — every
   page-level blocker is `fixed` or `sticky` — so its only job is the
   target-scoped rule. The data bounds it to **3–2001**: below 3 the
   Guardian's z=2 link cards are admitted; above 2001 the railways date
   picker is lost. Kept at 5. The upper bound is two elements from one site.
2e. ~~**`MIN_COVERAGE` now has 0.013 of margin.**~~ **0.27 since 2026-09-30**,
   the middle of the gap: 0.036 over the largest non-blocker, 0.0425 under the
   nearest blocker. No page's result changed. The one measured page inside the
   band is Ant Design's drawer panel at 0.295, now a blocker; a docs sidebar
   wider than 345px would now be one too. Still argued from a gap.
2f. **Coverage on scrolled pages** is correct as of 2026-09-21
   (`Document.scroll`), and `text_density` is too since 2026-09-30.
2g. **The host now lays pages out at 1280px** (scrollbars hidden in the site
   view, 2026-09-30). Every host-side perception figure before that date was
   taken at 1263px on a page that scrolled.
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
- **The person's own details** (2026-09-30): `details.py` reads a routed goal
  for what it says — model first with an 8s bound, keywords and dates as the
  fallback — and a `Brief` asks for the rest one question at a time through
  `loop.run_brief`. 83 unit tests on the reading, 19 on the loop's side of
  asking, 2 over the real app's websocket.
- **`TripPlanner`** (2026-09-30): plans one person's journey off the page as it
  goes, matching places against the site's own station list and asking which
  when a place names several. 29 tests against a local replica.
- **`About.shows`** (2026-09-30): a value that is in no field by the end — the
  bill's reference number, the course code — checked against what the site said
  back about it, on whichever page it said it.
- **`FieldValue.names`** (2026-09-30): a place the person named is matched
  inside the site's own station name; the date stays exact.
- **A step can be a question** (`Move.question`) and a step already agreed to
  can finish quietly (`Move.quiet`). Neither counts as a step taken.

**In progress**
- Nothing.

**Open — Raham's call**
- ~~**The keyword fallback runs one half of a two-part request.**~~
  **Fixed 2026-09-21b**: two flows named is a question. "I have a
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
- ~~**A station list that does not arrive looks like a place with no
  stations**~~ **Fixed 2026-09-30 (later)**: a step that waits on a fetched list
  has 15s (`LIST_TIMEOUT_S`). Reproduced and fixed on the replica with a late
  list; **not re-checked on the live site**, where it happened once in six runs.
- ~~**A mistyped place now takes 31.5s to be reported**~~ **16.7s since
  2026-10-01**: one attempt for a step that waits on a list. CLAUDE.md's loop
  rule names the exception since 2026-10-03.
- **Replayed runs do not get the longer window.** Replay builds every move with
  an empty expectation. Trace memory is off by default, so nothing uses it
  today.
- **A question the page raises is not in the count** (2026-09-30). The number on
  screen can end one or two above what was promised: which of two stations was
  meant cannot be known before the site answers. It only ever grows, and never
  goes below what is on screen. Options: budget for one station question per
  end, which overstates every unambiguous journey; or leave it.
  Recommended: leave it.
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
- **A step can be answered, not only agreed to** (2026-09-30). `store.ts`
  showed the stop screen for any answer but go-ahead, so pressing "Tomorrow" on
  a question ended the run while the backend waited for a response it already
  had; only `cancel` stops now. `StepShell` rendered exactly two buttons, the
  first and one more, so a three-answer question dropped both the third answer
  and the way to stop — every answer is a button at every level now, and the
  way to stop keeps the slot that folds to text at level 3.
  `test_questions.py` renders both shapes of question in a real browser and
  presses them.
- **Telemetry**, five numbers per step, on the answer and on a timer
  (`src/telemetry.ts`). No keystrokes, no field values, no coordinates leave
  the renderer.
- **The closing screen shows every result**, one per line, shrinking the type
  as the list grows. Verified live: two trains, two journey times, nothing the
  site returned missing from the screen (2026-09-19).

**In progress**
- Nothing.

**Open — Aly's call**
- ~~**The typeface is the system's.**~~ **Atkinson Hyperlegible Next since
  2026-09-21b**, bundled. A face designed for low-vision and
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
- **The training pipeline** (`train.py`, 2026-10-01): agreement between raters
  (Krippendorff's alpha, interval, checked against the published 0.849) and
  within them (the repeated pages), per-page means with every rater counted
  once, ridge regression on the nine headless features, 5-fold R² beside
  predicting the mean, held-out permutation importance, the model saved with
  what it was trained on, and a section appended to EVALUATION.md. Refuses
  fewer than ten raters, too few pages, and synthetic rows mixed with real
  ones. 24 tests, all on synthetic ratings. **Nothing trained: there are no
  ratings.**
- **The page-side features**, raw: `interactive`, `links`, `inferred`,
  `text_density` (characters per 1000px² of the viewport), `max_depth`,
  `overlays`, `form_fields`, `dead_link_ratio`, `reading_grade` — nine — plus
  the raw counts they are built from: `controls`, `dead_links`, `link_share`,
  characters, words, sentences, syllables. `interactive` and `links` are
  disjoint, so nothing is counted twice. 29 tests, arithmetic and browser.
- **The corpus**: 50 pages — 21 public, 21 demo, 5 ours, 3 target — in
  **both environments** (2026-09-21). Spiegel failed on DNS headless and read
  in the host; 16 pages differ between environments, none on `overlays`
  (`tools/evaluation/collect_corpus`, `data/corpus.json`).
- **Labels**: `data/labels.json`, from `tools/evaluation/label_corpus`. Raw
  counts per flow — steps, retries, verification failures, recovery, seconds —
  on the page each flow starts from. **4 of 50 pages labelled**; 43 have
  features and no label.
- **Provisional level rules** (2026-09-25): `rules.py`, 24 scripted-telemetry
  tests, 6 more through the loop and the app. Every decision is logged beside
  the telemetry. Guesses, marked as such everywhere.
- **Channel B**: the overlay sends telemetry on every step response and on a
  3s timer; the loop pairs each sample with the page features of that step and
  appends a row to `data/steps.jsonl` (`backend/estimator/pairing.py`). 14
  tests: 8 on the pairing, 6 driving the built overlay in a browser.

**Open — Nahail's call**
1. **No score, and deliberately so.** Weights need a calibration and there is
   no user data at all. What exists is measurement (DECISIONS.md).
2. **One feature still carries almost no signal**: `overlays` is 0 on 37 of
   45 pages. Down from 20 of 20, and the remaining thinness is honest — five
   of the eight nonzero rows are component libraries asked to show a dialog,
   which is a corpus of demonstrations of modals rather than a sample of
   pages that have them. `inferred` is no longer flat (14 of 45) but its mass
   is three `demo` rows: MUI 305, SweetAlert2 107, Ant Design 59.
3. ~~**`links` and `interactive` are nearly the same signal.**~~ **Settled
   2026-09-20d, twice.** Merged in the morning on the 20-page corpus, split
   again the same day on the 45-page one, where nine of the 44 pages with any
   controls sit under `link_share` 0.6 — a login at 0.00, a 15-field practice
   form at 0.083, the railways calendar at 0.182. Both counts still travel in
   every row either way.
3b. **Nine features, 50 rows, 4 labels.** Nothing can be fitted to this. All
   four labels are passes; one is the rig built to fail and one is a single
   live run. More labels need more *plans*, not more runs.
3c. ~~**`text_density` assumes the top of the page.**~~ **Fixed 2026-09-30**
   and the corpus re-collected: where a drive scrolled, density rose 20–88%
   with the same characters.
3d. ~~**The host lays pages out at 1263px.**~~ **Fixed 2026-09-30.** Headless
   and host now differ on density on 5 of 48 pages, not 9 of 49. Three are
   drives reaching different states, one is a live page changing, and
   **lite.cnn.com is unexplained**: same characters, 5% more on screen headless.
3e. **The driven rows depend on the drive reaching its state in time**, and
   three did not agree between environments this time. For the same state,
   overlays agree exactly. A drive that checked it had arrived would stop this
   being noise in the estimator's training data.
4. **Reading grade is the narrowest real spread** (3.91–13.68, CV 0.27) and
   the most heuristic number here: block-counted sentences and a vowel-group
   syllable counter (DECISIONS.md).
5. ~~**Nothing consumes either channel.**~~ **Provisional rules consume both
   (2026-09-25)**: page features set the starting level, telemetry folds and
   restores it (`rules.py`, DECISIONS.md). Still **no score**: the rules'
   `score` is distance to a threshold. **Nahail has not reviewed them.** The
   trained model is meant to replace them and be checked against their logged
   decisions.
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
- **The corpus is 45 pages read once.** Enough to choose features, to show
  which carry no signal, and to bound one threshold; nowhere near enough to
  calibrate a score. Five rows are pages we wrote and **eighteen are demo
  sites**, so a feature that separates them from the world may be measuring
  our HTML habits or a component gallery's. Every row says which it is.
- **Both detector thresholds are measured and the rest are not.**
  `MIN_COVERAGE` (0.27 since 2026-09-30, the middle of the gap) and `MIN_STACK_LEVEL` (5, bounded
  3–2001) against 50 pages (2026-09-20e); the telemetry constants and every
  definition in `page_features` remain as chosen.
- **The first `y` exists and is not usable yet**: 4 of 50 pages.
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
- **Three replicas** and one live flow; `run.ps1` / `run.sh`; `tools/screen_site.py`,
  `tools/mock_backend.py`, `tools/screenshots.py`, `tools/record_demo.py`,
  `tools/evaluation/`, `spike/`.
- The test suite from the repo root; `test_terminal_states.py` builds the
  overlay from source.
- **`README.md` installs and runs the project from nothing** (2026-09-23):
  prerequisites with versions, a check after each step, both shells, and the
  four failures a newcomer actually meets. `frontend/README.md` matches the
  project as of 2026-09-17.
- **`DEMO.md`** — the five-minute demo, with a fallback for every part of it
  that can fail, resting on the four recordings in `demo/`.

**Open**
- No CI. The Electron tests skip silently without a host.
- Nothing supervises the Electron host.
- `test_levels.py` measures `dist/`, which can be stale.
- **No formatter or linter.** `black` would reformat 46 of 57 Python files;
  `ruff` reports 69 findings. Adopting them is for all three owners.
- ~~The venv is Python 3.12.3; `CLAUDE.md` says 3.11.~~ **Settled 2026-09-30**:
  CLAUDE.md says 3.12.
- `main` is at `85bbf69` (the October readiness items, merged and pushed
  2026-10-01). **`feat/multi-october-pipeline-and-demo` is not merged**: one
  attempt for list steps, the training pipeline, and the recorder.
- ~~**The demo recordings predate the questions**~~ **Re-recorded 2026-10-01**
  on our copy, answering the questions. They run at the copy's pace, about
  twice the live site's, and show invented trains; DEMO.md says so. `demo/` is
  not committed, so a fresh clone has to record them again.
- ~~**Most existing tests write to the system temp directory.**~~ **Fixed
  2026-10-03**: the root `conftest.py` sets `--basetemp` to `.scratch/pytest`;
  `test_basetemp.py` holds it.
- **`feat/orchestrator-preview-capture` is committed and deliberately unmerged**:
  it keeps the site view repainting while it is photographed, and it stays out
  of `main` until the 100% capture rate is measured for real (see 2026-09-27
  above).
- **The demo recordings must be made before a demo**, on a machine with the
  stack up: `demo/*.webm` is gitignored, so a fresh clone has no fallbacks
  (DECISIONS.md, 2026-09-23).
- `tools/evaluation/host_overlay_run` drives the overlay of a running stack,
  which is how an interface claim gets checked live. It presses the step's own
  primary action and nothing else.
  `tools/evaluation/person_details_stack_run` is the one that can answer a
  question — it fills a box or presses a named answer — and is what the
  2026-09-30 live runs used.
- **`replicas/railways/` is not started by the launcher**, deliberately:
  `railways` means the live site. The tests start it themselves; by hand it is
  `PORT=5200 python replicas/railways/app.py`. Nothing in `run.ps1` or
  `run.sh` opens the window on it, so watching the trip planner in the real
  overlay means watching it against the live site.
- **The home screen's cards now lead into questions.** Each card sends its own
  words as the goal, and "Check my electricity bill" does not name a bill — so
  pressing it asks for the reference number, and a demo has someone type
  fourteen digits. Options: leave it; put the worked example's number in the
  card, which makes the card read like a form; or drop the card's goal and let
  it only open the ask box. Recommended: leave it, because a card that started
  looking up a number nobody gave is the defect this change exists to remove.
  DEMO.md and RUNNING.md now say it happens. **Aly's call.**

**Blocked**
- Nothing.
