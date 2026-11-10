# Status

Per module: what is done, what is in progress, what is open, and what is
actually blocked and on whom. **Update at the end of every task.**

Owners are from `CLAUDE.md`. **"Blocked" means work cannot proceed until a
named person or external thing acts.** Something nobody has done yet is
*open*, not blocked. Until 2026-09-17 this file mixed the two, and several
items sat under "blocked on quota" for eight days after the quota had reset.

**Last updated:** 2026-11-11 · **2100 passing, 12 skipped, 1 failed** · backend 1386 in 1930s, frontend 714 in 1648s, as two halves, on mains, on `fix/host-fit-flake` at `35d4e34`: the one failure is `test_calm.py::test_the_shape_does_not_slow_the_window`, 154ms over a 150ms limit, which passed 5 of 5 on its own (42 to 115ms). The host fit test (`SIMBA_HOST_TESTS=1`) 3 of 3 (584s), after `npm run build`, on mains; and 15 of 15 in five runs in a row before that. **Not merged** pending a decision (EVALUATION.md, 2026-11-11, 2026-11-11b)

---

## Where the project actually is

*Rewritten on 2026-11-02. What it said until then is in the first log entry below.*

**What SIMBA does.** It does web tasks for people who find cluttered websites
overwhelming. The real site loads in a view nobody looks at; the person sees one
plain step at a time, and the screen simplifies itself if they seem to be
struggling. The person decides and SIMBA clicks: once they have chosen, safe moves
run as a checklist with one Pause, and a real choice, anything to type, anything
that went wrong and anything that changes a record still waits for them. Every
action is checked on the page afterwards, tried once more another way, then handed
back. Features froze on 1 November; this month is evaluation and writing.

**The estimator is trained on the page side, and judges a task's first page.** A
ridge regression on nine page features, from 15 raters' answers on 50 pages
(`page_model.py`). 5-fold R² 0.49 against −0.11 for predicting the mean, off by
0.48 of a point against 0.77, and of the 8 pages raters put at "Very" or more it
caught 6 held out where the old rules caught 2. Read that with its limits: raters
agree weakly (alpha 0.318), judged a picture rather than used a page, and none is
from the audience; and it is under the study's floor, with 22 pages on 5 ratings
rather than 8. Three more Set 2 raters and one command fix the floor. What a person
does during a step still goes through hand-written rules with no person's behaviour
behind them, and nothing fuses the two (EVALUATION.md, 2026-10-30 to 2026-10-30c).

**Three flows, one of them on a live site.** Registering for a course and looking
up a bill run on replicas we wrote. Train times run on the live Pakistan Railways
site, read-only, or on our copy (`run.ps1 railways-local`). Each runs on the person's
own details: the goal is read, what is missing is asked one question at a time, and a
search for the wrong route or day fails rather than completes. The hand-written plan
is the default, with a language-model planner and trace replay behind the same loop;
the replica benchmarks are 50/50 with no model (EVALUATION.md, 2026-10-16d).

**Booking and paying happen only on our replicas.** Under the final-step rule
(2026-10-16) a change happens only on a page served from this machine, after a
final screen saying what will happen, with what, how much and when as the page
states them, and do it / don't, no default and no timer. `loop.carry_out` holds this
for every planner. So a train can be booked, a bill paid with no card, and a course
registered, each ending in practice words. On the live site SIMBA reads, and card or
bank details are never typed anywhere.

**Proof.** A closing screen with an answer offers "See it on the real page": a still
of the page as the task closed, with what was read ringed. The page is read again
before closing, and if it now says something else no answer is shown. Every closing
screen says what was and was not done, and "done" needs the site's own confirmation,
quoted. "What are you doing?" shows the page during a task.

**The person's own.** A welcome of four skippable questions on first open; the name
never leaves the overlay, and the level they choose is where the rules start. Up to
three tiles of their own, encrypted with the vault's key and run by id, which ask
only what changes. One saved password per site, Windows only. "Forget me and start
again" clears the profile and the tiles, and hides the goals from before it.

**Show me once** (2026-11-04, after the freeze, by Raham's decision). A helper does a task
once on the real site while SIMBA watches, with the overlay stepped aside to a bar; it is kept
as a routine of perception's roles and labels and the answer the helper pointed at, and the
person runs it from a tile — asked only what the helper said changes, the rest as the
checklist, every move checked, no model. A site that changed stops it honestly. Stage 1, the
bill on our copy, and stage 2, list choices and calendar days, a booking on the railways copy and
a read-only lookup on the live train search, are done. Since the fixes, a train pressed in the
results is the person's to choose, the booking has one final screen, and it shows what, how
much and when as the page states them. Since 2026-11-10 a helper finds it from the home screen
("Teach a task", in the top right corner), the bar lists what it has kept, and the last thing can
be taken back, the website with it, or started again when it cannot.

**The brand** (2026-11-02). The logo kit is in `assets/brand/`: the app icon, the title
`simba`, the logo while the backend comes up, and a small one on the home screen alone.

**What it cannot claim yet.** Nobody from the audience has used it. What the page
shows is not what the application believes, and every check reads the page. The
model-behaviour figures predate current perception, the stronger-model ablation has
not run, the LLM has no honest baseline, and the contract is an unratified draft.

### Changed on 2026-11-11: the host fit test's random failure, found — `fix/host-fit-flake`

- **The cause**: the host's window was **minimised from outside the test** while it ran. A
  minimised window gets 0 to 1 animation frames a second, and Playwright's "stable" check waits
  on frames, so a press on Start waited its 30s. Caught in a real run (the window said
  `minimised` at both failures), reproduced (21 and 18 of 40 presses failed with the window
  minimised, 0 of 180 with it covered but shown), and gone with the fix (0 of 40 with 34
  restores). Not an entrance animation, a layout shift, the press guard or the fitting.
- **Fixed in the test, not the app** (`tools/evaluation/display_fit_run.py`): it shows its own
  window again without taking focus whenever it is minimised, and says so in its result. No
  retry, no longer timeout. A person is not affected: nobody presses a minimised window, and
  the backend's window watch already handles one.
- **Proof**: five runs in a row after `npm run build`, on mains: **15 of 15**, with the window
  minimised from outside 7 times (EVALUATION.md, 2026-11-11).
- **Suite**: backend 1386 passed; frontend 714 passed and **1 failed**, a timing assertion
  (`test_calm.py`, 154ms over 150ms) that passed 5 of 5 on its own; host fit test 3 of 3
  (EVALUATION.md, 2026-11-11b). **Not merged yet**: the task says a failure means no merge.
- **Open**: what minimises the window; the site view's captures at 10 to 13 of 20 at 100% and
  125%, against 20 of 20 in CLAUDE.md.

### Changed on 2026-11-10 (later): picture tiles and a journey line — `feat/interface-look`

- **A follow-on to Teach a task, after the freeze, by Raham's decision** (DECISIONS.md, *Picture
  tiles and a journey line go in after the feature freeze*). How the overlay looks; nothing it
  does, and nothing in the backend or the contract.
- **Every home screen tile wears a picture on its own calm colour**: a train, a bill, a book, or
  a globe for anything else. Built-in tiles by what they are; kept and taught tiles by their
  name (`frontend/src/pictures.ts`). Each picture at least 6.25:1 on its pale square in all
  four themes; the words unchanged. A taught tile's mark is a badge on its picture's corner.
- **The checklist is a journey line**: done dots filled, the one being done larger with "Doing
  this now", those to come empty. Still a list with the current step marked. At the simplest
  level only the move being done and "Then N more things."; levels 1 and 2 as before. The dot
  grows in once; not under reduced motion.
- **Found on the way**: the fullest home screen with names long enough to wrap already scrolled
  on `main`, by 19px at 100% and 14px at 150%. It fits at every size now (EVALUATION.md,
  2026-11-10c).
- **Suite**: backend 1386 and frontend 715 passed, 0 failed; **the host fit test failed at 125%**
  on the known intermittent press on Start, and passed on its own re-run (EVALUATION.md,
  2026-11-10d). Held back at first, as the task said; **merged into `main` on Raham's decision**,
  the only failure being that known intermittent one, as on 2026-11-10b.
- **Flagged**: the level-3 count; the replies' pictures changing too; "What are you doing?" not
  on the checklist; kept tiles pictured by name, not by flow. See DECISIONS.md.

### Changed on 2026-11-10: Teach a task, and undo on the bar — `feat/interface-teach-entry`

- **A follow-on to Show me once, after the freeze, by Raham's decision** (DECISIONS.md, *"Teach a
  task" and undo go in after the feature freeze*). A way in for helpers on the home screen, and a
  bar that shows what it has learned and can take the last thing back.
- **"Teach a task"** opens "Show me a task once", with "For a helper, like a carer or a teacher."
  under it. It is in the window's top right corner across from the logo, **not at the bottom as
  the task said**: measured, a row under the settings put the box off the bottom by 73px at 150%,
  and a row fixed at the window's bottom sat on the settings row by 29px (EVALUATION.md,
  2026-11-10). The settings entry stays. The fit tests, headless and in the host, hold it above
  the greeting at every size. **Aly to say whether the corner is right.**
- **The bar lists what it has kept**, newest last, in a few words each ("Typed in Reference
  No.", "Pressed Check Bill."), never a typed value, a password as "Typed a password." and
  nothing more; the last few and "N more before these." when there are more than fit. The bar is
  160px tall, from 96.
- **Undo last thing.** A typed value comes off the list and out of its box. A press that moved
  the website to another page takes the website back and comes off only once the page is really
  the one it was pressed on, with what the list says was typed there in its boxes again. When it
  cannot be (the page cannot be reached by going back; a list choice, a day or a password was
  made there) the bar says so, nothing is let through, and **Start again** is offered in place of
  Undo and Finish. Tests first: the bill taught, the search undone and made again, kept, and run
  from its tile: **5 of 5**, 2 presses, 0 model calls, the routine step for step stage 1's
  (EVALUATION.md, 2026-11-10).
- **Contract**: `teach.watching.kept` and `start_again`, and `teach.answer` `undo` and
  `restart`; additive, pending Nahail and Aly (CONTRACT.md).
- **Flagged for review**: the corner; the bar's height; a page with a list choice, a day or a
  password can only be started again; a press that stayed on its page is taken off the list
  and the page left as it is. See DECISIONS.md, *Teach a task and undo: what was settled along
  the way*.

### Changed on 2026-11-05: the visual retrain — `eval/retrain-visual`

- **Set 3 is in, and the visual features are not better.** 37 responses, 23 usable raters (10, 5
  and 8; 14 on a phone dropped). Old, new and the five alone on the same 63 pages and folds: error
  0.528, 0.524 and 0.513, no gain told from nothing; on the 15 Pakistani pages no arm beats knowing
  their average (held-out R² −0.02 to 0.06). The gate fails five of six, **so the old model stays
  live, `data/estimator.json` unchanged, and the loop was not touched** (EVALUATION.md, 2026-11-05).
- **Still under the floor, on Set 2 alone**: 21 compared pages have 5 ratings. The one new Set 2
  response was on a phone. Three more usable Set 2 raters is still what fixes it.
- **People have now rated 15 of the index's sites**, and the live model reads them a third of a
  point calmer than people do (error 0.61, order kept 0.28). Mostly calm, as it said; not in its
  order. Its top ten on a second read are 2026-11-02b's, in the same order.
- **New**: `train_visual --min-ratings`, `--charts` (`visual_charts.py`, SVG), and the index ranked
  by the model the gate keeps (`rescore_index --by`). Charts in `.scratch/retrain-visual/`.
- **Flagged**: refitting the live nine on Sets 1 to 3; the conditions block naming a language
  model on runs that call none. See the task report and DECISIONS.md.

### Changed on 2026-11-04 (evening): Show me once, fixes — `fix/show-me-once`

- **The train is the person's choice.** A press that is one of a column, one per row of the
  results, is kept without the row's name; when it runs the person is asked "Which train?" from
  the page's own rows, and that train is booked. Ten runs on two routes, half of them a route
  with no 7UP: 10 of 10 booked the train chosen on the route asked for (EVALUATION.md,
  2026-11-04c).
- **One final screen per booking**: the link that only opens the form runs as a checklist line;
  `loop.only_opens` believes that only for a real link to another page of our copy.
- **The final screen shows what, how much and when** as the page states them: Train, From, To,
  Date, Departs, Passenger, Class, Fare, as the built-in booking's. 6 presses, 0 model calls.
- Stage 2's three flagged items are settled by these; a routine file gains three optional keys
  (CONTRACT.md, `routine.import`).
- **Merged into `main` on 2026-11-05**, after the host fit test passed 3 of 3 (580s) on a re-run.
  It had failed at 100% twice, at a different point each time, with nothing it uses changed. The
  re-run had about as little memory available (959 MB) as the second failure, so memory alone does
  not explain those failures. **Open:** the host fit test may be intermittent at 100%. Seen again
  on 2026-11-10 at 150%, the same press on Start at the sign-in screen, gone on re-run
  (EVALUATION.md, 2026-11-10b): **intermittent, at any scale.** And again that evening at 125%,
  on the way to an ending (2026-11-10d): four failures in a week, each a press on Start that
  waits for the button to be stable, each gone on re-run. It now decides whether a branch merges.
  **Found on 2026-11-11**: the window minimised from outside mid-run; the test now shows it
  again (see 2026-11-11 above).

### Changed on 2026-11-04 (later): Show me once, stage 2 — `feat/show-me-once`

- **List choices and calendar days** a helper says change are the person's to give: asked from
  the site's own list and as a journey's day is asked, then typed, chosen, and the calendar
  moved to the month. The page must hold the person's station and day the moment each is chosen.
- **Booking on the railways copy**: 10 of 10, 6 presses (four questions, two final screens), 0
  model calls. **Trains on the live site, read only**: taught once, 2 of 2, 3 presses, 0 model
  calls; robots.txt checked first (EVALUATION.md, 2026-11-04b).
- **Walked in the real window** on the railways copy: the day asked about on the bar, and another
  journey run on a typed day, searched exactly as asked.
- **Flagged**: a routine's final screen names the button only; a booking meets two final screens;
  a press whose label holds data (a train's number) ties the routine to it.

### Changed on 2026-11-04: Show me once, stage 1 — `feat/show-me-once`

- **One feature after the freeze, by Raham's decision** (DECISIONS.md, with its reason and
  cost): a helper does a task once on the real site while SIMBA watches, and the person runs it
  from a tile, with no model.
- **Stage 1, the bill on the billing copy, end to end**: teaching mode in the settings, the bar,
  recording by perception's role and label, the same-or-ask question, the answer pointed at, the
  read-back, the name, a tile, export and import, and running it with the checklist, every move
  checked and the proof. 10 of 10 runs right, 2 presses, 0 model calls; on the copy changed after
  teaching, an honest stop that names what is missing (EVALUATION.md, 2026-11-04).
- **Walked in the real window** at 100% and 150%: taught in 7 presses, run in 3, captures in
  `.scratch/show-me-once/`.
- **Safety**: teaching only reads on a live site (a press that would book, pay, register or
  submit is held and never made), a card box stops it, a password is never read; on our copies a
  changing press is kept and runs behind the final screen.
- **Contract**: six new message types and three optional fields, additive, pending Nahail and
  Aly (CONTRACT.md, *Show me once*).
- **Flagged for review**: see the end of this entry in the task report, and DECISIONS.md, *Show
  me once, stage 1: what was settled along the way*.

### Changed on 2026-11-03: `eval/visual-features` checked and merged into `main`

- **The suite**: 1907 passed, 12 skipped, 0 failed (backend 1268 in 1421s, frontend 639 in
  1421s), on mains, with 0.7 GB free at the start.
- **The host fit test failed 0 of 3, on its own check**: `display_fit_run` read a logo's name
  up to its last `-`, and the rebuild's hash for the dark small logo, `D3-JexYj`, held one. It
  now cuts Vite's eight characters; re-run 3 of 3 (561s). **Aly to review** (DECISIONS.md).

### Changed on 2026-11-02 (visual features) — `eval/visual-features`

- **The blindness is measured.** Five first-screen features (`visual_features.py`) on 48 of the
  50 rated pages and all 35 sites. Median `image_area` 0.70 on the sites against 0.006 on public
  rated pages, and 33 of 35 past any public page rated. The two left out now disallow us in
  robots.txt (EVALUATION.md, 2026-11-02c).
- **Set 3 is ready to send, and has no answers.** 20 pictures, about 3-4 minutes: `makeFormSet3`,
  and every step in `tools/rating/form/README.md`, section 7.
- **The comparison is built and cannot run yet.** `python -m backend.estimator.train_visual`
  refuses today: 186 more ratings, at least 3 more Set 2 raters and 8 more Set 3 raters.
- **So there is no new model, and the old one stays live.** `data/estimator.json` is unchanged.
  A preview on Sets 1 and 2 got worse with the new features (R² 0.58 to 0.42), as pages with
  almost no pictures would make it: that is no verdict either way.
- **Blocked on people**: raters for Set 3, and three more for Set 2.
- **Open, for all three owners**: a pass at the gate does not go live, because the app measures
  only the nine. See DECISIONS.md, *What the visual features can and cannot be*.
- **Flagged, for Nahail**: `first_screen_text` is nearly `text_density` (r = 0.98); no still can
  show `motion`; and `capture.py` and `collect_corpus.py` do not ask robots.txt.

### Changed on 2026-11-02 (last): the overwhelm index — `eval/overwhelm-index`

- **The trained model on 42 Pakistani public sites**, read once each, read-only:
  `tools/evaluation/overwhelm_index.py`, 55 tests. 35 scored, 6 skipped (5 of them 403s on
  robots.txt), 1 failed.
- **It calls them calm, and that should not be believed yet.** 34 of 35 are below the
  average rated page, and none is heavy, against 7 of the 21 public pages people rated. The
  pictures are busy. The model counts text and these pages put theirs in images: median
  density 0.38 against 0.91. A limit of the model, found by using it on pages unlike those it
  learned from (EVALUATION.md, 2026-11-02b).
- **Open, for Nahail: nothing tests that reading.** People rating ten or so of these pictures
  would. Pictures of text may need a feature of their own, which is past the freeze.
- **Not re-run**: the whole suite, since this branch only adds a script and its tests.

### Changed on 2026-11-02 (later): the opening rewritten — `docs/tidy`

Documents only, so the suite was not re-run. HANDOVER.md's opening is a dated list,
README.md opens with five lines for a stranger, and ARCHITECTURE.md's stages are
corrected, with what had drifted listed at its end. Fifteen stale items in this
file's module sections are corrected, most struck through beside what replaced them,
and three superseded decisions now say so. Flagged, not fixed, because they are not these
documents: `data/tiles.json` is not in `.gitignore`; CLAUDE.md's *Current phase* is
October's; and CLAUDE.md and README.md say the estimator "fuses", and put the
credential vault in `frontend/`.

The section above was rewritten to say what is true today. Everything it said until now
is here, in its own words and its old order, each paragraph under a line saying what
became of it. Nothing below that line was edited.

*Superseded: long past a skeleton. See the opening.*

The walking skeleton runs end to end on three flows — three replicas we wrote,
and one live public site.

*Still true on 2026-11-02; said more shortly in the opening.*

**The first page of a task is judged from people's ratings now** (2026-10-30).
A ridge regression on nine page features, trained on 15 raters' answers to "How
overwhelming does this page feel?", replaces the rules' guess at a heavy page.
It beats predicting the mean (R² 0.49 against −0.11, off by 0.48 of a point
against 0.77) and it beats the rules, which caught 2 of the 8 pages raters put at
"Very" or more, against 6 of 8 held out. **Raters agree weakly** (alpha 0.318),
and the model was trained **under the study's floor**: 22 pages have 5 ratings,
not 8, because Set 2 has 5 usable raters. Three more fix that, and retraining
is one command (EVALUATION.md, 2026-10-30 to 2026-10-30c).

*Still true on 2026-11-02; said more shortly in the opening.*

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

*Still true as a record of that run. Not re-run since.*

**An LLM run has finished a live task correctly, for the first time**
(EVALUATION.md, 2026-09-17f). Railways, through the real Electron window, 8
model calls, $0.000847: both stations committed, the calendar navigated to
October, the 15th picked, and the search sent for `2026-10-15`. The run
before it, earlier the same day, did the same and was stopped by durable
verification on a date the page had only reformatted (2026-09-17b); a value
matching the task's declared `About.holds` is now accepted, and that is the
difference between the two runs.

*Superseded in part: since 2026-10-14 results are tickets, five at 100% and three in a short window, and past that a count.*

**A closing screen now shows the answer, and it shows all of it.** The live
results' heading strip was extracted as a table of its own, so nothing paired
`Train No.` with a train; joining them fixed it (2026-09-17i), and on
2026-09-18 a finding carries *every* value for a label rather than the first,
so a two-train search reads `2DN, 14DN` (2026-09-18b). Since 2026-10-05 it
shows the first six and counts the rest, so that the screen fits.

*Still true as of its date. The host has laid pages out at 1280px since 2026-09-30.*

**The perception figures are confirmed in the environment that runs them.**
Every figure in EVALUATION.md before today was measured headless; the
scrollbar-spacer defect existed only in the Electron host. All three sites
were re-read both ways on 2026-09-18 and **no serialized figure differs** —
though the host's raw markup does still carry the spacer, so it was a standing
difference and not a bad day on the live site (2026-09-18c).

*Still true. Its finding stands in HANDOVER.md, section 4.*

**A published benchmark figure does not reproduce, by 2x, and the cause is
the machine.** The hardcoded plan's 5.9s from 2026-09-06 re-runs at 3.0s on
that very commit — and at 3.93s and 6.85s the same day on the same tree
(2026-09-17h). Code and venv were ruled out; what is left is the environment.
Steps and model calls are now the primary metrics, wall clock secondary with
its range (DECISIONS.md). Every conclusion in EVALUATION.md that rested on a
time difference has been audited: none is withdrawn, one now stands on its
mechanism rather than its seconds.

*Superseded in part: since 2026-10-30 the trained model judges the first page. What a person does in a step is still read by these rules.*

**The level adapts in a real run now, by provisional rules** (2026-09-25).
A heavy first page starts at level 3; a long pause, a wandering pointer or a
help press folds the step on screen one level simpler; two calm steps bring
it back; a lock holds. Checked live on billing through the Electron host:
folded at 8.0s (pointer) and 18.3s (still), came back on the ending, lock
held across two tasks (EVALUATION.md, 2026-09-25). The rules are hand-written
guesses standing in for the estimator, not the estimator.

*Superseded: "No score, no weights" ended on 2026-10-30 for the page side, and the rules have read both channels since 2026-09-25.*

**Both channels exist now, and until 2026-09-25 nothing read either.** Channel A is the
page: nine raw features per step. Channel B is the person: hesitation, cursor
path ratio, backtracks, re-reads and help presses, sent by the overlay on
every step response and on a 3s timer while a step waits — `telemetry` had
been in CONTRACT.md since 2026-09-04 with no sender. Every sample is written
beside the page features of the step it belongs to, in `data/steps.jsonl`,
which is **not committed** because it carries the goals a person typed
(2026-09-20c). No score, no weights, no user data collected yet.

*Still true. `MIN_COVERAGE` has been 0.27 since 2026-09-30.*

**Bounds are CSS pixels everywhere.** `snapshot.parse` converts on the way in,
so overlays, interactivity, content and the estimator all read the same units
as the frozen viewport. Every recorded perception figure was re-measured in
both environments afterwards and **not one moved** — but `MIN_COVERAGE = 0.30`
has been behaving as **0.133 in the host** since the rule existed, because a
box 1.5x too large covers 2.25x the area. The registration modal read a
coverage of **2.220** before the fix and 0.986 after (2026-09-20).

*Superseded: on 2026-10-30 for the page, which has a score and weights from people's ratings. Nothing about a person is measured by a model yet. The corpus has been 50 pages since 2026-09-21.*

**The estimator measures nothing about a person yet.**
`backend/estimator/page_features.py` reads nine raw features off one page
read — counts, a density, a depth, a dead-link ratio and a Flesch-Kincaid
grade — with **no score, no weights and no normalisation**, because those need
a corpus to calibrate against. `data/corpus.json` is the first one: 20 public
pages, read in both environments, 0 failures. **Three of the nine features
cannot tell those pages apart** and are flagged as such (2026-09-19b).

*Superseded in part: past five tickets, or three in a short window, the rest are counted.*

**A closing screen shows every result now, checked on the live site.** A
finding carries both the one line the step screen shows and the list the
ending shows; a two-train search put both trains and both journey times on the
screen, and the site view confirmed nothing was missing (2026-09-19).

*Still true. Its finding stands in HANDOVER.md, section 4.*

**The project's headline perception finding is smaller than it read.**
"What perception emits decides what a planner can use" is split in two: emitting
what the input does not contain (occlusion, date qualifiers — 10/10 runs, and
a distinction no prompt could supply) holds; moving words the prompt already
carries above the element list is **falsified as stated** at 0 of 8 runs
(EVALUATION.md, 2026-09-18).

*Still true as history: fixed on 2026-09-17, and tested since.*

**Every ending reached from a step was unpressable** — found and fixed on
2026-09-17, present since at least `cc4704f`. After any step, an invisible
leftover of the step screen covered the ending's buttons (EVALUATION.md,
2026-09-17c).

*Superseded: it completed the live flow again on 2026-09-18, 5 of 5 steps (EVALUATION.md, 2026-09-17i).*

The hardcoded plan last completed the live flow on 2026-09-09 (54s). Not
re-run since; the live page's structure was unchanged when re-read on
2026-09-17.

*Still true.*

What the system cannot do is trust its own result: the DOM is not the
application's state (EVALUATION.md).

### Changed on 2026-11-02: the brand — `feat/brand`, under the freeze

- **The logo kit is in `assets/brand/`, as supplied.** The window has the app icon and
  the title `simba`; README.md opens with the horizontal logo. The taskbar itself was
  not seen, since that takes a desktop capture: Windows was given the icon, read back
  at 24px and 48px, and the title bar shows it.
- **The stacked logo shows while SIMBA opens**, then fades to the home screen; nothing
  under reduced motion. It waits for the backend's first message, 15s at most, and was
  up 7.8s and 9.8s on two real starts. **A connection change came with it**: the
  launchers start the window first, so the first attempt failed and nothing tried again.
  While the logo is up it does, so a person's own tiles are now on the home screen on a
  real start, which they were not until a first task had ended.
- **A small horizontal logo on the home screen and no other**, in the corner, touching
  nothing on the fullest home screen at any scale, in either theme. The shape stays the
  presence mark.
- **Two logos are not the kit's files**: the dark ones sat in a visible box, and the
  tagline was 4px in the corner. `assets/brand/derived/` has the same drawings without
  them, held to that by a test (DECISIONS.md, *The brand*; EVALUATION.md, 2026-11-02).
- **The suite**: 1712 passed, 12 skipped, 0 failed (backend 1073 in 981s, frontend 639
  in 1420s); the host fit test 3/3 (579s), on mains.
- **Open, for Raham: the backend's first message comes 3.8s to 5.8s after the socket
  opens**, on a real start. The logo now covers it, so nobody sees it. The cause is not
  known; `past_goals` and the health check are not it.
- **Open: one host fit run stopped on a press at 125% and 150%**, with no frames as the
  likeliest reading and nothing to show it, and the next run passed. The fit run now
  says whether frames are arriving when that happens.
- **Open: under reduced motion a real start still offers no tiles** until a first task
  has ended, because there is no logo to wait behind. Retrying on the home screen would
  need the attempt to stand aside for a press.
- **Aly to review** `Brand.tsx` and its place in `App.tsx`.

### Changed on 2026-11-01: after the training — `fix/after-training`, under the freeze

- **The guard's move lasts one screen.** After the overflow guard dropped a step to
  fit, every later step stayed at the guard's level unless a lock was on, so a heavy
  task ran at the densest level from the sign-in on. The next step now goes back to
  the level it came from, on both sides, with nothing sent. In the real window at
  150% and forced 100%, registration went 3, 1 for the sign-in, 3 for the next
  question, nothing past the window, and the backend's row agreed. At 1266x606 the
  next question goes back to 3, does not fit, and takes its own hop with the notice
  (EVALUATION.md, 2026-11-01b; **Aly and Nahail to review**, DECISIONS.md).
- **`billing.webm` and `adapt.webm` re-recorded**, stills checked. Billing opens at
  level 3; adapt needs `SIMBA_PAGE_MODEL=0` and folds at 5.3s. The other four clips
  were not. DEMO.md says how to make both.
- **The figures with and without raters 5007 and 5013, side by side**
  (EVALUATION.md, 2026-11-01). Alpha 0.318 to 0.447, R² 0.572 to 0.621, and the heavy
  call differs on at most 1 of 50 pages. Both raters stay.
- **The suite**: 1665 passed, 12 skipped, 0 failed (backend 1073 in 1013s, frontend
  592 in 1327s); the host fit test 3/3 (515s). **Not all on mains**: mains was lost
  about 07:59, so the end of the frontend half and all of the host test ran on
  battery, which Raham accepted for this bug fix. Merged into `main` and pushed.

### Changed on 2026-10-30: the estimator, trained on people's ratings — `feat/estimator-trained`

- **Ratings are in.** 24 responses, 9 dropped for being on a phone: **15 usable
  raters**, 10 in Set 1 and 5 in Set 2. 450 rows. 22 pages have 5 ratings, 22
  have 10, the six anchors 15.
- **Under the floor, and saying so.** `train.py` refused, as it should. Trained
  on all 50 pages with a new `--min-ratings 5`, which is written into the model
  and names the 22 pages. The default still refuses. Measured: fitted to the 28
  pages at the floor alone, the error on those pages is 0.477; with the 22 added
  it is 0.412, so the thinner pages help (DECISIONS.md, *The estimator is trained
  under the floor*).
- **Agreement is weak, and it is a result.** Alpha 0.318 (Set 1 0.284, Set 2
  0.357). People are far more consistent with themselves (repeats correlate
  0.803, 93% within one answer) than with each other. Rater 5007 runs against
  everyone (−0.58), 5013 alongside no one (0.10); both kept, since no exclusion
  rule was set beforehand. The two sets rate the anchors alike (0.02 apart, p =
  1.000, on five raters a side at best).
- **The model is worth something and has a ceiling.** 5-fold R² 0.491 ± 0.240
  (folds 0.06 to 0.72), error 0.480; over 40 shuffles of the folds 0.572, error
  0.498. The page means' own reliability is 0.779, about the most any model could
  reach. `text_density` carries most of it, then `links`, then a negative
  `max_depth`; `overlays`, `reading_grade` and `inferred` carry nothing.
- **Against the rules**: agree on 36 of 50 pages; of the 14 they differ on, raters
  side with the model on 11. Rank correlation with the ratings 0.778 against
  0.492. On heavy pages, held out: precision 0.49 and recall 0.75 against 0.20
  and 0.25. The rules' count of covering pop-ups carried no weight with raters.
- **In SIMBA**: `backend/estimator/page_model.py` reads `data/estimator.json`,
  features in, a score and level out, cut points **2.45 and 2.90**, chosen on
  held-out scores (held-out kappa 0.691). A task starts at the simpler of the
  page's level and the person's own; a page never brings more detail than they
  chose. Live behaviour and a lock work as before. No model, an unreadable one
  or `SIMBA_PAGE_MODEL=0`: the rules judge the page. The health check says
  which. Every decision row says who judged the page and what the rules would
  have said. `load.updated` is unchanged: no contract change.
- **Retraining is one command**: `python -m tools.rating.retrain` (RUNNING.md).
  116s.
- **Each page's score and reasons in plain words**: `data/estimator_pages.json`,
  and EVALUATION.md, 2026-10-30b. Rated means are not committed.
- **Found and fixed**: from level 3 the sign-in screen ran 60px to 86px past the
  window at 100% and 150%, because the guard's one hop went to level 2. It now
  goes to level 1 (`levels.ts`; **Aly to review**).
- **Behaviour that changed**: billing and registration now start at level 3, and
  so have nowhere to fold. DEMO.md and `demo/README.md` say what to do. The
  `adapt` clip needs `SIMBA_PAGE_MODEL=0` to re-record.
- **Needs the other owners**: DECISIONS.md, 2026-10-30, six entries; HANDOVER.md,
  *For Nahail (2026-10-30)*.
- **The suite, on mains**: 1644 passed, 12 skipped, 0 failed (backend 1062 in 964s,
  frontend 582 in 1261s); the host fit test 3/3 (453s). Merged into `main` and
  pushed.

### Changed on 2026-10-23 (later): two sets of 30 — `feat/rating-sets`

- **The rating forms are 30 pictures, not 55**, online and in person: the 50
  pages split into Set 1 and Set 2, 25 each, balanced on the nine features
  (worst feature's mean rank 0.023 apart; random halvings have a median of
  0.133), each set showing three anchor pages of the other and two repeats.
  The A/B reverse-order forms are gone. In person, odd rater numbers rate Set
  1 and even Set 2 (DECISIONS.md, *Two sets of 30*).
- **One fully labelled question**: "How overwhelming does this page feel?" —
  Not at all / A little / Somewhat / Very / Extremely, 1–5. Two worked
  examples first (GOV.UK's bank holidays, Not at all; Newegg under a pop-up,
  Very), neither among the 50 (`python -m tools.rating.examples`). "About 5-7
  minutes" at the top and a progress bar, on both. The 5-7 minutes is an
  estimate; nobody has filled in a form yet.
- **Training needs 8 ratings on every page**, not 10 raters overall, and when
  it refuses it says how many more ratings, and raters of each set, are
  needed; the converter says the same after every run. That is at least 16
  usable raters, 8 per set. Agreement works on the incomplete table (alpha
  overall and per set; each rater against the others on their own pages), and
  the six anchors check the two groups rate alike (EVALUATION.md, 2026-10-23b).
- **Tests**: rating and training 101 passed (was 75); `make_form.gs` run
  against stand-ins for Google's services, not in Google: 98 items per form,
  was 171.
- **Still no ratings.** Neither form has been made in Google.

### Changed on 2026-10-23: `feat/personal` merged into `main`

- **Brought up to date with `main`** (the two rating-form branches); only
  STATUS, DECISIONS and EVALUATION conflicted, every side kept.
- **The suite found a real defect on the branch**: the trace store's times
  tied on Windows (1996 of 1999 consecutive clock readings identical), so two
  goals saved in one tick came back from `recent` in either order, and the
  reset test failed in 60 runs of 200. Fixed — a tie moves on a microsecond —
  with a test that stops the clock outright; 0 of 200 after (EVALUATION.md,
  2026-10-23).
- **The suite, rerun on mains after the fix**: 1531 passed, 12 skipped, 0
  failed (backend 953 in 941s, frontend 578 in 1245s); the host fit test 3/3.
  Merged into `main` and pushed.
- **Still needs the other owners**: the contract additions from
  `feat/personal`, listed in HANDOVER.md, are now on `main`.

### Changed on 2026-10-22 (later): two rating forms — `feat/rating-two-orders`

- **Two forms, A and B**, B showing the pictures in reverse order, each repeat
  as far from its first showing in both (7 to 18 pictures). `make_form.gs` has
  `makeFormA` and `makeFormB`. `from_form.py` takes both CSVs, tells them
  apart by column order (or `A=`/`B=`), and records each rater's form. The
  repeat is the later showing in the rater's own form (DECISIONS.md, *Two
  forms*). The script was run against stand-ins for Google's services, not
  in Google (EVALUATION.md, 2026-10-22b).

### Changed on 2026-10-22: ratings collected online — `feat/rating-online`

- **Ratings can now be collected remotely, with a Google Form.**
  `python -m tools.rating.export_form` writes the 50 pictures and five repeats
  (P01–P55) and a mapping to `.scratch/rating-form/`, with `make_form.gs` to
  build the form and a README for the steps. `python -m tools.rating.from_form`
  turns the form's CSV into `data/ratings.jsonl` rows marked online. It drops
  phone, declined and incomplete answers, and counts the usable raters
  against `train.py`'s ten. One fixed order for every online rater;
  pictures seen at about half size; unsupervised (DECISIONS.md, EVALUATION.md
  2026-10-22).
- **Still no ratings.** The form has not been made in Google yet, so
  `make_form.gs` is untested.

### Changed on 2026-10-18: SIMBA made for the person — `feat/personal`, merged 2026-10-23

- **Getting to know you**: on first open, four short questions, each
  skippable — a name, which of three ways of showing a question feels
  comfortable (the real step at levels 1, 2 and 3), whether to show "Read
  this aloud", and ask-each or just-do-it. Kept in the overlay as the
  person's profile; the name greets them and never leaves it. The level goes
  with every task (`task.start.start_level`), and the rules start from it and
  come back to it instead of 2. "Change my settings" reopens it
  (EVALUATION.md, 2026-10-18).
- **Your own tiles**: a bill or a journey's closing screen offers once to keep
  it; kept, it is encrypted with the vault's key, names and all, and the
  overlay is told only its id, name and flow. Run by id, it asks only what
  changes. Up to three, first on the home screen above "Things I can help
  with"; renamed, moved and removed through `tile.change`, a new message
  (2026-10-18b).
- **The starting level is written down as its own signal** for the
  estimator, with a note for Nahail (2026-10-18c).
- **"Forget me and start again"** clears the profile and the tiles. The last
  goals asked are not cleared — flagged, with a recommendation (2026-10-18d).
- **Walked in the real window** as a brand-new person at 100%: welcome,
  the bill, kept as "My bill", run again from the tile without being asked
  the number (2026-10-18e).
- **Found on the way**: the backend's log lines had held the typed goal and
  its reference number since 2026-10-17; they now hold neither.
- **Needs the other owners**: `start_level`, `history.offered.tiles`,
  `task.completed.keep`, `task.start.tile` (additive, optional) and the new
  `tile.change` message — listed in HANDOVER.md.
- **The suite on this branch, on mains**: 1500 passed, 12 skipped, 0 failed
  (backend 928 in 859s, frontend 572 in 1190s); the host fit test 3/3, now
  with a new person's welcome and three tiles of their own in it.

### Changed on 2026-10-17 (last): final touches — `fix/final-touches`

- **A registration on our copy ends in practice words**, as a booking and a
  payment do: "Registered for CS-401 on the practice site." over the
  confirmation number, "This was a practice copy, so no real registration
  was made.", and the portal's caveat, kept (EVALUATION.md, 2026-10-17j).
- **Every dependency is pinned** to the versions the suite passes with: all
  48 Python packages in the two requirement files, exact versions in
  `package.json`, the lock for the rest; install with `pip install -r` and
  `npm ci` (RUNNING.md, *Installing the exact versions*). The first lock
  written was not in step, and `npm ci` on a fresh clone refused it: fixed.
- **A fresh clone runs the whole suite**: the first run there found 66 errors
  (no `.scratch/` folder — the conftest now makes it), a proof test this
  branch had left behind, and **a real press-guard bug**: a button that eased
  to rest could have its first press ignored, the gap the guard kept plus the
  press's own 1px nudge reading as a fresh move. Fixed; very likely the tile
  press seen once at 150%. Rerun: 901 + 528 passed, one failure in a new test,
  since fixed (2026-10-17k).
- **`demo/booking.webm` re-recorded** with the new ending, checked on its last
  frame; no other clip shows changed wording (2026-10-17l).
- **`feat/orchestrator-preview-capture` deleted** — superseded; it was never on
  GitHub. Three evaluation scripts only it held went with it (DECISIONS.md).
- **The suite before merging, on mains**: 1430 passed, 12 skipped, 0 failed
  (backend 902 in 952s, frontend 528 in 1036s); the host fit test 3/3 (415s).

### Changed on 2026-10-17 (later): stability — `fix/stability`, no new features

- **The 100% picture is fixed.** At a display scale of 100% (and 110%) a
  capture of an idle site view stalls until a second one is asked for.
  `browser.capture_site` asks again every 0.15s while it waits: 20/20 at
  100%, 110%, 125% and 150%, median ~0.35s; the proof and every preview use
  it. Why the scale matters inside Chromium is still not known
  (EVALUATION.md, 2026-10-17).
- **The false "I waited while the window was closed"** came from the demo
  recorder's run of 16 October: its overlay is a browser of its own, while
  the backend read the host's window, minimised and unwatched. The host's
  window now counts only when the task was started in it
  (`window.__simbaStarted`). A hidden window is still read as shown
  (2026-10-17b).
- **The registration's caveat** is the portal's whole meaning: "…until
  tuition and fees are paid, or a payment plan is in place." (2026-10-17c).
- **A booking or a payment on our copy** ends "Booked on the practice site."
  / "Paid on the practice site." over the number and "This was a practice
  copy, so no real ticket was booked and no money was taken." (2026-10-17d).
- **The slower backend suite is not the code, it is the battery**: the
  commit before the offer took 805s on 2026-10-16 and 1435s on battery on
  2026-10-17; this branch's backend half took 1537s on battery and 879s on
  mains the same day, with the same free memory. Every run now prints the
  power source, processor speed and free memory. A run kept open for an offer closes itself
  after 10 minutes, and the overlay takes the offer away (2026-10-17e).
- **Tile presses and a slow checklist at 150%: not reproduced** in 20 runs;
  the backend now logs every step, move and picture with times to
  `logs/backend.log`, and the host logs every press the guard saw (2026-10-17f).
- **The host fit test's 22-minute hang: found** — its overlay picture had no
  time limit and stalled at 100%, one run in twelve; now 20/20 (2026-10-17h).
- **A fresh clone**, set up from README and RUNNING alone, ran all three
  flows; README's way of proving the install was wrong and is fixed
  (2026-10-17g).
- **The suite before merging**: 1428 passed, 12 skipped, 0 failed (backend
  901 in 879s on mains, frontend 527 in 1059s); the host fit test 3/3. Three
  overlay tests that assumed Playwright acts within a fixed time were made
  independent of it; the press-guard pair failed the same way on `main`
  (EVALUATION.md, 2026-10-17i).

### Changed on 2026-10-17: offers as a button, the stop found, honest wording

On `feat/finish`, one commit per item, then **`feat/finish` merged into `main`**
with everything of 2026-10-16 (last).

- **No question after every answer.** On our replicas the closing screen
  has a quieter "Book one of these" / "Pay this bill" beside "Back to start";
  the run stays open for it (`task.completed.offer`). A goal that says book
  or pay goes straight on. "Which train?" is the booking's first question.
- **The unexplained stop, found.** Every press is logged (`pressGuard.ts`).
  40 walks before the fix: 22 ended "I've stopped" — a press aimed at the
  fading screen's "Tomorrow" landing on the arriving screen's "Stop this",
  which sat where "Tomorrow" had been. Fixed (a leaving screen takes no
  presses and keeps its own step) and guarded (a press on a button that
  moved or appeared in the last 500ms, or where another was, is ignored).
  40 walks after: 40 reached the trains (EVALUATION.md, 2026-10-16e).
- **"You're registered for CS-401. The portal says it isn't final until
  fees are paid."** in place of "That's done." beside the portal's caveat.
- **Replica benchmarks re-run** on the current flows: 50/50, no model
  (EVALUATION.md, 2026-10-16d), replacing the old registration numbers.
- **Demo clips re-recorded**, with a booking through its final screen;
  DEMO.md walks the new screens and paying a bill.
- **HANDOVER.md lists what Nahail and Aly must agree.**
- **Open, flagged:** see the report — chiefly the caveat's plain words
  dropping "tuition" and "payment plan"; "That's done." beside "no real
  ticket was booked"; at forced 100% the end-of-task still of the page
  sometimes fails, which cost the railways clip its proof until recorded at
  150%; a minimised-window wait seen once while recording.

### Changed on 2026-10-16 (last): SIMBA finishes the task, on our replicas

On `feat/finish`, from `main`; merged on 2026-10-17. One commit per item, and one
for what the real window found (EVALUATION.md, 2026-10-16c).

- **The final-step rule replaces "never execute an irreversible action"**
  (CLAUDE.md; Raham's request; **Nahail and Aly to be told**): a change
  happens only on a replica and only after a final screen — what will
  happen in plain words, what, how much and when as the page states them,
  do it / don't, no default, no timer. Held in the loop for every planner.
- **Trains**: after the results, on our replica, "Would you like to book
  one of these trains?"; then the name and class the form needs, the final
  screen, and "Booking Confirmed" quoted with booking number, train, date
  and seat.
- **Bill**: "Would you like to pay this bill?"; a pretend payment with no
  card; the receipt quoted.
- **Registration**: its register step is the same final screen, with the
  course's own row.
- **Live sites**: "I only looked up times. I don't book tickets or pay on
  the real site." and the one way to see the page; payment details are
  never typed anywhere.
- **Honest endings**: "That's done." only with the site's confirmation;
  "Don't" ends "I didn't do it. Nothing was changed."
- **Open, flagged:** the offer is made after every replica search and bill
  (one more press for someone who wanted only the answer); the first walk's
  unexplained stop; the recorded registration benchmarks predate the final
  screen; CONTRACT.md's `final` and the rule need the other two owners.

### Changed on 2026-10-16 (later): finishing proof, and merged

On `feat/proof`, one commit per item, then **merged into `main`** after a
clean full suite and host fit test (EVALUATION.md, 2026-10-16b).

- **The portal's caveat is quoted** under its confirmation, its sentence
  whole: "Registration is not final until tuition and fees are paid or a
  payment plan is in place" (`task.completed.caveat`, additive).
- **Cookies are a question**: "This site asks about cookies. Shall I say
  yes?" — Yes, No, and the way to stop. No leaves the banner and carries on.
- **A bill in plain words**: "Rs 14,382, due 15 September 2026". Checked and
  ringed by the page's own text.
- **One way to see the page**: "What are you doing?" during a task (close-up,
  whole page inside); "See it on the real page" at the end. "Show the real
  page" and the picture asked for with every step are gone.
- **"Back to start"**, one button, on every ending.
- **The host fit test** covers 25 endings and the sign-in screen at three
  scales. It found nine ticketed trains 179px below a 1280x800 window; the
  closing screen now gives up results until it fits.
- **Open, flagged:** "That's done." beside "not final until fees are paid";
  the sign-in screen still needs level 1 at 100% and 150%; Yes is the filled
  button on the cookie question.

### Changed on 2026-10-16: proof — the answer on the real page, and never more than was done

On `feat/proof`, from `main`, **not merged**. One commit per item.

- **"See it on the real page"** on every closing screen with an answer: a
  still of the page as the task closed, what was read ringed, close up. The
  page is read again before closing; if it now says something else, no answer
  is shown. No picture is said in plain words, never shown stale or empty.
- **Every closing screen ends with what was and was not done**: "I only
  looked up times. I did not book a ticket or pay for anything."
- **A change is "done" only with the site's own confirmation on the page**,
  quoted; otherwise "It isn't confirmed." The step that changes something is
  tried once.
- **Registration asks which course from the portal's own list**, after
  signing in; a course not offered is caught at the question.
- **"I couldn't get a picture just now"** instead of nothing.
- **Remembered goals in a few words**: "Bill ending 7890".
- **A person's bill ends on its results page** (it used to open the full
  bill, where its answer is not shown).
- **Fixed from walking the real window:** a list question's button waited for
  nothing; course codes title-cased; rings covering headings; a confirmation
  number broken at its hyphen; a live ticket widening the column in Electron.
- **Open, flagged:** see the report — chiefly the portal's "not final until
  fees are paid" next to "That's done"; the sign-in first screen needing level
  1 at 100% and 150%; headless fit checks missing Electron's wider text.

### Changed on 2026-10-15: review fixes, and merged

On `feat/interface-reveal`, one commit per item, then **merged into `main`**
with `feat/railways-ask` (already inside it).

- **Direction B, the deep teal, is the default**; A with `?palette=a`.
- **Trains arriving after midnight say so**: "00:50, next day", from the
  journey time; checked on the live site's rows.
- **Times** in tabular figures; **empty boxes** look ready (a light fill, a
  2px edge, a 3px ring with the cursor in them).
- **A question's main button** says what it does ("Use this station", "Use
  this day", "Use this number", "Use this course") and waits for an answer.
- **Pause** has a pause sign; **the checklist shows the lines still to come**
  (`StepPresented.coming`, additive and optional).
- **Home**: the box sits under the tiles, one group, centred.
- **No softened page behind a step**, and the light themes' glow lightens
  the top of the window rather than shading it.
- **Question headings** at full strength.
- **Sign-in**: keeping the password is a box to tick (Raham's choice; **Aly to
  be told**, DECISIONS.md); the screen now fits at every size.
- **Remembered goals that would look the same** say what tells them apart
  ("ending 7890").
- **A picture of the page never holds the person's answer**: taken beside
  the wait, dropped after 5s, cancelled on the answer.
- **For Nahail** (also in HANDOVER.md): fewer training rows per task, and
  `read_aloud` is a new telemetry signal.
- **Open, flagged:** "What are you doing?" pressed while a picture is late
  shows nothing for that press; a remembered goal at 150% reads "Find the…"
  before its tag; the stage row is 16px at level 2.

### Changed on 2026-10-14 (later): the person decides, SIMBA clicks; the opening; colour

On `feat/interface-reveal`, **not merged**. One commit per item.

- **Safe moves run as a checklist** once the person has decided: filling in,
  the calendar, searching, opening a page to read. Questions, cookies,
  signing in, registering, model-planned moves and the move after a failure
  still ask. "Ask me before each thing I do" keeps the old way. Trains: 9
  presses to 4. Nothing about the person is recorded on a checklist line
  (DECISIONS.md: **fewer training rows per task; Nahail to note**).
- **Named stages** replace "Step X of Y" (trains: From, To, Day, Search,
  Trains), fixed for the task.
- **Fixed from the last report:** the first question fits at level 2 at every
  size, and no notice shows on a task's first screen; a wrong answer's
  sentence goes once a good one is chosen; no automatic reveal; one thing at a
  time at the top of a step; results headed with the journey, each ticket
  with leaves, arrives and how long.
- **Read aloud is its own telemetry signal** (`read_aloud`); **Nahail to
  confirm** how the estimator uses it.
- **One presence mark**, the shape: still unless SIMBA is working, nothing
  moving when the window is away. Home screen at rest: 0.2% of one core in
  the real window (was 7.5%).
- **The home screen**: greeting by the time of day, three tiles with
  pictures, the whole window's height, an entrance once.
- **Two colour directions**, A (default) and B (`?palette=b`), both passing a
  contrast test, light and dark; controls now have a 3:1 edge. **Raham to
  choose**; captures in `.scratch/directions/` and `.scratch/for-review-2/`.
- **Fixed from walking the real window and the suite:** a checklist line
  asked for a picture of the page, which held the course's "Register" for
  31s; the home tiles' entrance never played; level 3 was taller than level 2
  on choice questions (up to 107px); three backend tests still expected the
  old findings and the old number of weighed steps.
- **Open, flagged:** the course's sign-in screen runs 96px past the window at
  100% and 91px at 150% even at level 1 (56 and 60 on `main`); the stage row
  is 16px at level 2, as "Step X of Y" was; a preview that times out blocks
  the person's answer for 30s; the two remembered bill goals read the same
  once clamped to one line.

### Changed on 2026-10-14: the new look in the real window, and fixes

On `feat/interface-reveal`, **not merged**. One commit per item.

- **Checked in the real Electron window for the first time** (EVALUATION.md,
  2026-10-14): the whole train flow on `railways-local`, every bad answer, at
  this machine's own 150% and at a forced 100%. It found seven things headless
  had not, listed there; the small ones are fixed.
- **Read aloud is built.** Raham approved changing CLAUDE.md's rule; **Nahail
  and Aly still need to be told** (DECISIONS.md). "Read this aloud" above each
  step: the system's English voice, off until pressed, stopped when the step
  changes. Checked with the real Windows voices.
- **The "book a flight" reply fits** at all three sizes.
- **The level notice says what happened**: "I've made this smaller so it
  fits." for the overflow guard; "I'm showing a bit more now." for the rules.
- **Fixed from the real window:** Electron's menu bar hidden; the 9px
  scrollbar at 150% on two-line station questions; a chosen station no longer
  a second filled button; stations written to be read in step details; the
  reveal's one softened frame; two buttons with the same eye; the notice over
  "Read this aloud".
- **Left for Raham, not fixed:** see the report's list — chiefly the step
  count running past itself ("Step 13 of 13"), the guard folding and
  announcing on the first question of every task, a wrong answer's sentence
  staying after a good one is chosen, the softened page all but invisible in
  the light theme, and the shape's 7% of one core while the home screen is up.

### Changed on 2026-10-07: the interface, less plain

On `feat/interface-reveal`, from `feat/railways-ask`, **not merged**. One
commit per item. Screenshots of every screen, both themes, three sizes, in
`.scratch/interface-reveal/` (not committed). Most of it is **for Aly to
review**.

- **The real page behind the step.** Shown clearly for a moment when a task
  starts, then blurred and dimmed behind the card; "Show the real page" while
  held, or until hidden. A picture, asked for with each step; the site view
  is still covered. Password boxes are painted over in every capture.
- **A shape beside each step** for what it is about — date, place, choose,
  type, read, confirm — named by the backend (`step_kind`, additive).
- **Results as tickets**, the fastest marked and always on screen; a bill as
  a slip. Nine trains still fit at 150%.
- **SIMBA's shape**, CSS 3D, on the home screen and while thinking; still
  under reduced motion; about 70ms of main-thread work in 5s while turning.
- **The question screens** have their shapes too.
- **Skipped:** the home cards already existed. **Not built:** read aloud —
  CLAUDE.md rules text-to-speech out; it needs all three owners.
- **Found and fixed:** reduced motion never reached the Framer animations;
  the station question from `feat/railways-ask` scrolled by 52px at 100% and
  150% once names appeared. **Found, not fixed:** the reply to "book a flight"
  scrolls by 24px at 100% and 45px at 150%, as it did before this branch.

### Changed on 2026-10-06 (later): every journey answer checked before the site is touched

On `feat/railways-ask`, **not merged**.

- **Why SIMBA never asked where or when on `railways-local`.** The home
  screen's train card sends its own words as the goal, and they were "Find
  trains from Lahore to Karachi", so both ends were named before anything was
  asked. The course card did the same with CS-401. Typed goals did ask. The
  cards now read "Find train times" and "Register for a course" (for Aly to
  review). The person's own run is not on record; established by reproducing
  every way in (EVALUATION.md, 2026-10-06c).
- **Stations come from the site.** Its own list, 340 names on the live site,
  is read from the closed dropdowns before anything is touched
  (`backend/perception/options.py`, for Nahail to review). The station
  question is a box that offers the matching names as buttons; the replica
  now holds its list the same way.
- **Every answer is checked first**, each said kindly and asked again: a day
  gone, too far ahead, or not in the calendar; from and to the same; a
  station not on the list (the closest offered); a city with two stations.
- **Read back once** before starting — "Lahore Cantt to Karachi Cantt,
  tomorrow, 7 October. Is that right?" — and the search step no longer says
  it again. The plan searches the chosen stations.
- **Checked live once** (read-only, one search): asked and read back with the
  page untouched, searched Lahore Cantt to Karachi Cantt for 7 October,
  2 trains, 5 steps, 0 model calls. With a model that has no quota, the app
  asks and completes on keywords.
- **Found and fixed:** level 3 removed a typed answer's box at the first
  keystroke (for Aly to review); four matches did not fit at 150%; the list
  reader dropped a value-only `datalist` option.
- **Billing and registration.** Billing asks for the one thing its site
  needs, the reference, and the plan runs on it. Registration ran a fixed
  course from its card; fixed with the card. **Open:** a course code is not
  checked against what the portal offers, because the list is only visible
  after signing in. Read from the code, not run: a course that is not offered
  is only found out at the register step, after signing in, when its button
  cannot be found.

### Changed on 2026-10-06: the window waited for, the fastest named

- **Merged and pushed.** `feat/multi-october-fifth-rows` is in `main`, after a
  clean full suite (944 passed, 12 skipped).
- **A minimised or hidden window is waited for, not failed.** The host writes
  the window's state into the overlay page; the backend reads it before every
  action and does nothing while the window is away. When it comes back: "I
  waited while the window was closed. Ready to carry on?", and the run goes on
  only after Carry on. In the real window, minimised for 10.4s mid-step: no
  action, no failure, the bill found after (EVALUATION.md, 2026-10-06).
- **The sentence names the fastest train** when there are rows and two or
  more: "The fastest is 1UP, at 6 hours 3 minutes." A tie is said as a tie.
  Any sentence that wraps gives up one result line, so nine trains fit at
  every scale with every wording (2026-10-06b).
- **CLAUDE.md forbids broad kill commands**: only processes you started, by
  PID.
- **Results not from a table still pair by list length**, recorded in
  DECISIONS.md as a known limitation with no work planned before the freeze.

### Changed on 2026-10-05 (later): whole rows, the clips, the approval

- **Merged and pushed.** `feat/multi-october-fifth` is in `main` (`45125dc`).
  The rest below is on `feat/multi-october-fifth-rows`, **not merged**.
- **Results travel as whole rows.** Perception reads each table row with its
  cells together, repeats kept (`Content.rows_for`); the first finding carries
  them as `Finding.rows`, additive and optional; the closing screen and the
  sentence read them. On our copy, four trains whose times repeat on rows 1 and
  3 and 2 and 4 each showed their own time; on the live site, one read-only
  search, three trains arrived as whole rows through the div-built table
  (EVALUATION.md, 2026-10-05c). The railways replica has one new route for it,
  Hyderabad Jn to Sukkur.
- **The demo clips are re-recorded** on our copy and show the closing screen as
  it is; all three task clips end on their answers (2026-10-05d).
- **The mock backend had no health check** since 2026-10-03: a helper sat
  between `@app.get("/")` and `health`. Fixed, with a test; its tests' fixture
  had waited 30s every run.
- **Found, not fixed: a minimised SIMBA window fails the next action.** The site
  view inside it paints about once a second, and a click waits for a page that
  never settles. It ended two clips "I'm stuck" before they were recorded again.
- **The side-by-side buttons are approved by Raham** (DECISIONS.md).

### Changed on 2026-10-05: the closing screen fits, and every ending is checked

- **Merged and pushed.** `feat/multi-october-third` is in `main` (`9fd09bc`).
  The rest below is on `feat/multi-october-fifth`, **not merged**.
- **The closing screen fits** with 1, 3 and 9 results at 100%, 125% and 150%:
  both buttons on screen, nothing scrolls, tightest 34px. Each result is one
  line with its detail ("13UP, 6 h 6 min"); past six the rest are counted;
  past four the type is 30px; the sentence takes the lead-in's place; the two
  buttons sit side by side. The six strict known failures pass. One line per
  result and the first six were not enough at 150% (−123px), which is why the
  layout changed too (EVALUATION.md, 2026-10-05). The side-by-side buttons
  are approved by Raham (later the same day); the rest is **for Aly to review**.
- **A detail goes beside a result only when the lists line up.** Perception
  keeps a repeated value once, so nine trains can come with eight journey
  times, and pairing by position would put a time beside the wrong train.
- **Every ending is checked for fit**, all 17, at three window sizes in a
  browser on every run and in the real host with `SIMBA_HOST_TESTS=1`. Its
  first run found the morning's fix still wrong: nine trains with eight times
  put both buttons 87px below a 606px window, and five trains with two times
  scrolled at 100%. Both fixed (EVALUATION.md, 2026-10-05b).
- **Four evaluation scripts recognised the closing screen by "Here's what I
  found"**, which a closing screen with a sentence no longer says. They now
  also know "I'm done", and the demo recorder looks for the results.
- **EVALUATION.md's known limitations** say the credential store works only on
  Windows, and that elsewhere the person is asked each time.

### Changed on 2026-10-03: pictures with their features, a vault, a sentence

- **Merged and pushed.** `feat/multi-october-pipeline-and-demo` is in `main`
  (`6ebdb8b`). The rest below is on `feat/multi-october-third`, **not merged**.
- **The rating pictures and the corpus are one run** (`58dc053cdac7`,
  2026-10-03): each page's features read from the same load as its picture,
  both files dated. 27 of 50 pictures had changed since the old set. The
  estimator refuses to pair a rating with features from another run, or a
  rating of an earlier picture. No ratings exist yet.
- **A minimal credential store.** A password typed once into a protected field
  is kept when the person asks, encrypted with Windows' own key, and typed by
  the backend after that; it can be forgotten from the sign-in step. A whole
  LLM-planned task was searched for it everywhere — prompts, transcript,
  traces, recorder, logs, overlay messages, files written — and it is nowhere
  (2026-10-03b). Perception no longer holds any typed password at all.
- **One plain sentence on the closing screen**, from the page's own values, in a
  new optional field `task.completed.explanation` (2026-10-03c).
- **The closing screen does not fit with three or more results, at any scale**,
  and has not since before today; measured for the first time (2026-10-03c).
  See Interface.
- CLAUDE.md names the one-attempt exception; every test's temp files are in
  `.scratch/pytest`; the trained model will be committed and the ratings not
  (DECISIONS.md).

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
  (EVALUATION.md, 2026-09-27). *Fixed 2026-10-17 (above): keeping the page
  drawing turned out not to help; asking again does.*

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
8b. **Rows** (`Content.rows_for`, 2026-10-05): every table row with a value
   under the first header, its cells under each header asked for, repeats
   kept. Label/value pairs have none.
9. ~~`value_for` returns the first matching pair, so even when pairing works
   "which trains?" shows one train.~~ **Fixed 2026-09-18** (2026-09-18b).
10. ~~Page-side load features for the estimator: not started.~~ **Done**:
   `backend/estimator/page_features.py`, nine features (see Estimator).

**Blocked**
- Nothing.

---

## Orchestrator — Raham · `backend/orchestrator/`

**Done**
- **Undo while teaching** (2026-11-10): `Teaching.undo` and `restart`, the recorder's
  `__simbaRestore`, `Draft.kept` and `voice.kept_line`; a page with a list choice, a day or a
  password cannot be put back and is started again. `test_teach.py` 32, ten of them new, the
  undo-redo-save-run one five times over.
- **Show me once, stage 1** (2026-11-04): `teach.py` records a helper by role and label,
  `routines.py` keeps it encrypted and shares it as a file, `routine_plan.py` runs it with no
  model and stops honestly on a changed page. The loop gains `must_finish`, `ran_out`, a list
  choice (`<select>`) checked by reading it back, and `Expectation.has_value`. 58 tests.
  **Stage 2**: list choices and days (`test_routine_lists.py`, 14), the loop's
  `recommitted` and `Expectation.field_has`. **Fixes**: a row's press as the person's choice,
  `Move.opens` with `loop.only_opens`, a routine's final details, and the loop's `look`
  (`test_routine_lists.py`, 27).
- **Saved sign-in details** (`vault.py`, 2026-10-03): DPAPI-encrypted, one entry
  per site, kept only on request and only after the step worked, typed by the
  backend, forgettable from the step. 13 tests, the first of which searches a
  whole LLM-planned task's every output for the password and fails when a leak
  is planted.
- **The closing sentence** (`voice.explain_*`, 2026-10-03), sent as
  `task.completed.explanation`. 23 tests.
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
- ~~**A question the page raises is not in the count** (2026-09-30). The number on
  screen can end one or two above what was promised: which of two stations was
  meant cannot be known before the site answers. It only ever grows, and never
  goes below what is on screen. Options: budget for one station question per
  end, which overstates every unambiguous journey; or leave it.
  Recommended: leave it.~~ **Gone since 2026-10-14**: named stages replaced the
  count, and no frontend code reads `estimated_steps`.
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
- ~~`requires_confirmation` is always `true`.~~ **Not since 2026-10-14**: `false` is
  a line of the checklist.
- Replay tuning: not started.

**Blocked**
- Nothing.

---

## Interface — Aly · `frontend/`

**Done**
- **Picture tiles and a journey line** (2026-11-10, `feat/interface-look`, merged on Raham's
  decision after the host fit test's known failure at 125% passed on re-run): pictures on calm
  colours on every tile, by name for
  kept and taught tiles; the checklist as a path of dots, with level 3 showing only the move
  being done. `test_pictures.py` 18, `test_checklist.py` 26, `test_contrast.py` 23; the host
  fit test counts the pictures and measures the journey line. **Aly to review all of it.**
- **Teach a task, and the bar's list** (2026-11-10): "Teach a task" in the window's top right
  corner on the home screen, opening the same screen as the settings; the bar 160px tall with the
  things kept listed newest last, Undo last thing, and Start again when the website could not
  be taken back. 34 tests in `test_show_me_once.py` at 100%, 125% and 150%; `box_fits` and the
  host fit test measure the way in. **Aly to review**, the corner above all (DECISIONS.md).
- **Show me once, stage 1** (2026-11-04): "Show me once" in the settings, the screen behind it,
  the bar while watching (the host shows the website below it and covers it again after), the
  read-back, routine tiles, saving to and reading from a file. 18 tests at 100%, 125% and 150%,
  and walked in the real window. **Aly to review.**
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
- **Six endings, all with a way onward, all pressable after a step**:
  found an answer, done, failed, stuck, stopped by the person, and since
  2026-10-16 "I didn't do it. Nothing was changed."
  `test_terminal_states.py` renders each, including from a
  step, presses every button, and since 2026-10-05 checks every button is on
  screen at three window sizes.
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
- **The closing screen shows every result**, verified live: two trains, two
  journey times, nothing the site returned missing from the screen
  (2026-09-19). **Since 2026-10-05, one line per result**, its detail beside
  it ("13UP, 6 h 6 min"), the first six and "and N more" past that, the
  sentence in the lead-in's place, and the two buttons side by side.
- **Every ending fits the window, and is checked to** (2026-10-05): with 1, 3
  and 9 results, at 100%, 125% and 150%, every button is wholly on screen and
  nothing scrolls; tightest 34px. `test_terminal_states.py` checks all 38
  endings (17 on 2026-10-05) at three window sizes on every run, and
  `test_window_fit.py` the same 38 in the real host (EVALUATION.md, 2026-10-05
  and 2026-10-05b).

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
- ~~**"I'm done" and "Do something else" go to the same place.**~~ **One "Back to start" since 2026-10-16.**
- **The stuck screen still shows the technical reason** in small type. In the
  2026-09-17 run that reason would have told the person the date had been
  lost, when it had been set correctly.
- **An LLM "Fill in" step still shows an empty field.** Since 2026-09-17 an
  empty answer no longer overrides the model's value (DECISIONS.md), so the
  defect is closed, but the step still asks the person to approve a field that
  does not show what is about to be typed. Pre-filling it belongs with the
  credential vault.
- **"Click element 13."** reached the screen in the watched run.
- ~~**The closing screen does not fit with three or more results, at any
  scale.**~~ **Fixed 2026-10-05**, by the cascade Raham chose (one line per
  result, smaller type, the first six) and two layout changes it needed and
  did not name: the sentence replaces the "Here's what I found" lead-in, and
  the two buttons sit side by side at every scale — the one screen whose
  buttons are not stacked. A detail that cannot be put beside its result
  (eight journey times for nine trains) is one line under the list and takes
  a result's place. Since later the same day, results arrive as whole rows
  (`Finding.rows`), so a detail is put beside its own result even when times
  repeat; the line under the list is left for values not from a table. The
  side-by-side buttons are **approved by Raham**; the sentence in the
  lead-in's place and the rest are **for Aly to review**: DECISIONS.md, "The
  closing screen fits by changing its layout".
- ~~**A minimised SIMBA window fails the next action** (2026-10-05d).~~
  **Fixed 2026-10-06**: the run waits while the window is minimised or hidden
  and asks before carrying on (EVALUATION.md, 2026-10-06). What it leaves: it
  waits without limit, and "hidden" has been checked with a stand-in only.
- **The step screen shows one finding**, as one line that stops at four
  values. That is the design, not an oversight — but it means a run in
  progress can show "and 2 more" for a while before the ending shows them.
- ~~"I'm showing a bit more again." is also what an overflow drop says.~~
  **Settled 2026-10-14**: an overflow drop says "I've made this smaller so it
  fits.", and the rules' return "I'm showing a bit more now."
- ~~"Step 2 of 6" uses a word `copy.ts` forbids.~~ **Gone since 2026-10-14**:
  named stages.
- ~~A found value is shown as the page wrote it (`15-09-2026`).~~ **A bill's are said in plain words since 2026-10-16**; a train's times are still the page's.
- ~~Home-screen history is stale after a task (`CONTRACT.md`).~~ **Fixed
  2026-10-18**: "Back to start" opens a new connection, and is offered the goals
  and tiles as they now stand (`store.startOver`).
- A backend that dies mid-task leaves "Give me a moment." on screen with
  nothing to press.
- ~~Nothing chooses a level automatically; only the mock sends `load.updated`.~~
  **The rules have since 2026-09-25**, and the trained model judges the first
  page since 2026-10-30.
- ~~The credential vault is not built.~~ **A minimal one, 2026-10-03**
  (`backend/orchestrator/vault.py`). What it is not: saved details can be
  forgotten only from a sign-in step, during a task — deleting them from the
  home screen needs a new contract message; Windows only; one entry per site.
  Voice input is not built.

**Blocked**
- Nothing.

---

## Estimator — Nahail · `backend/estimator/`

**Done**
- **A trained estimator** (2026-10-30): ridge regression on the nine features,
  15 raters, 50 pages, `data/estimator.joblib` and `data/estimator.json`,
  **trained under the floor of 8 ratings**. `page_model.py` is what the app reads;
  `rules.py` takes its judgement of the first page and falls back on its own
  signs; `tools/evaluation/estimator_compare.py` holds it against the rules;
  `tools/rating/retrain.py` is one command for all of it. Page side only: it is
  not yet fused with what the person does (EVALUATION.md, 2026-10-30 to c).
- **The visual features, compared and not adopted** (2026-11-05): five first-screen
  features (`tools/evaluation/visual_features.py`), Set 3's 15 Pakistani pages rated by 8
  people, and `train_visual.py` holding old, new and the five alone against a gate set
  before the ratings. Not better, overall or on the Pakistani pages; the live model is the
  nine. `data/estimator_visual.json` is the candidate, never read by the app
  (EVALUATION.md, 2026-11-05).
- **Two sets of 30** (2026-10-23, replacing the A/B forms of 2026-10-22): the
  50 pages in two balanced sets of 25 (`tools/rating/session.split`), three
  anchors each way and two repeats, a five-point labelled question, two worked
  examples, the same online (`export_form.py`, `form/make_form.gs`,
  `from_form.py`) and in person (`serve.py`). Rows carry `set` and `anchor`.
  28 tests in `test_form.py`, 23 in `test_rating.py`. 24 responses collected,
  15 usable (2026-10-30).
- **Ratings online** (2026-10-22): the pictures exported for Google Forms, and
  their CSVs read back into `data/ratings.jsonl` with `"online": true`.
- **Pictures and features from one load** (2026-10-03): `tools/rating/capture`
  writes the rating pictures and `data/corpus.json` in one run, both dated;
  `train.py` uses a rating only when its picture is current and its features
  came from the same run.
- **The training pipeline** (`train.py`, 2026-10-01): agreement between raters
  (Krippendorff's alpha, interval, checked against the published 0.849) and
  within them (the repeated pages), per-page means with every rater counted
  once, ridge regression on the nine headless features, 5-fold R² beside
  predicting the mean, held-out permutation importance, the model saved with
  what it was trained on, and a section appended to EVALUATION.md. Since
  2026-10-23: 1–5, each rater rating one set, agreement on the incomplete
  table, the two groups compared on the anchors, and a refusal below 8
  ratings on any page that says how many more are needed. Refuses too few
  pages, and synthetic rows mixed with real ones. 37 tests, all on synthetic
  ratings, 2026-10-23; on real ratings since 2026-10-30.
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
1. ~~**No score, and deliberately so.**~~ **A page score exists since
   2026-10-30**, from people's ratings of pictures. There is still no score from
   what a person does, and nothing fuses the two: the rules take the stronger of
   them. CLAUDE.md's table says "fuses"; that is not built.
1b. **Three more usable Set 2 raters** bring every page to the floor (RUNNING.md,
   *Retraining the estimator*). Until then the model on `main` is under it.
1b2. **Pictures of text are still unseen, and now measured as such** (2026-11-05). On
   the 15 rated Pakistani sites the live model is a third of a point calmer than people
   (error 0.61, Spearman 0.28), and no arm, with or without the five visual features,
   orders them better than their average. `image_area` and `motion` carried nothing.
   Seeing words set in pictures would mean reading text out of images: a new dependency,
   past the freeze, so not proposed. Whether to refit the nine on Sets 1 to 3 is flagged.
1c. **Who the raters are.** 13 of 15 aged 18–24, 10 of 15 in computing, judging a
   picture rather than using a page, and none from the audience. Set 2's five
   are the less technical group (four of five, against one of Set 1's ten).
1d. **The features and what raters saw do not line up.** Raters judge the
   viewport; `links` and `interactive` count the whole page. BBC News has 106
   links and looks calm. Counting them per viewport is untested, and would
   mean recapturing the corpus.
2. **One feature still carries almost no signal**: `overlays` is 0 on 39 of the
   50 pages headless (37 of 45 when this was written), and its coefficient in
   the trained model is +0.004. The thinness is honest: it was a corpus of
   demonstrations of modals rather than a sample of pages that have them.
   `inferred` is nonzero on 17 of 50.
3. ~~**`links` and `interactive` are nearly the same signal.**~~ **Settled
   2026-09-20d, twice.** Merged in the morning on the 20-page corpus, split
   again the same day on the 45-page one, where nine of the 44 pages with any
   controls sit under `link_share` 0.6 — a login at 0.00, a 15-field practice
   form at 0.083, the railways calendar at 0.182. Both counts still travel in
   every row either way.
3b. ~~**Nine features, 50 rows, 4 labels.** Nothing can be fitted to this. All
   four labels are passes; one is the rig built to fail and one is a single
   live run. More labels need more *plans*, not more runs.~~ **People's ratings
   replaced labels as the target on 2026-10-30.**
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
   restores it (`rules.py`, DECISIONS.md). Since 2026-10-30 the trained model
   sets the starting level, checked against the rules' 48 logged start decisions
   (EVALUATION.md, 2026-10-30b), and the telemetry half is unchanged: every number
   in it is still a guess. **Nahail has not reviewed either.**
6. **No user data exists.** Every telemetry number so far came from a test
   driving a browser. Whether any of the five separates a page someone coped
   with from one they did not is the whole question and is unmeasured.
7. **The definitions are starting guesses**: 8px of movement, ~120° of turn, a
   3s timer, "re-read" as the pointer re-entering the text. All in
   `frontend/src/telemetry.ts` so they can be moved together.
8. **`data/steps.jsonl` grows without bound** and has no rotation.
9. **The two-sets design is in Nahail's area and Nahail has not reviewed it**
   (2026-10-23): the floor of 8 ratings per page, agreement on an incomplete
   table, and what "the groups rate alike" means — a mean anchor difference
   under 0.5 and Mann–Whitney p not below 0.05, reported but not acted on.
   What to do if they are not alike is open (DECISIONS.md, *Two sets of 30*).

**Blocked**
- Nothing.

---

## Shared contract — all three owners · `shared/`, `CONTRACT.md`

**Done**
- **Teach a task and undo** (2026-11-10): `teach.watching.kept` and `start_again` (optional),
  and `teach.answer.action` `undo` and `restart` (two more values). Additive; pending Nahail and
  Aly.
- **Show me once** (2026-11-04): six new message types (`teach.start`, `teach.answer`,
  `teach.watching`, `routine.export`, `routine.file`, `routine.import`), the optional
  `history.offered.routines`, `task.start.routine` and `step.presented.routine`, the shape
  `TaughtTile` and the error code `ROUTINE_NOT_READ`. All additive; pending Nahail and Aly.
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
- **The corpus is 50 pages.** Enough to choose features, to show which carry no
  signal, and to bound one threshold; thin for a score, which is why the model's
  folds run from 0.06 to 0.72. Five rows are pages we wrote and **21 are demo
  sites**, so a feature that separates them from the world may be measuring
  our HTML habits or a component gallery's. Every row says which it is.
- **Both detector thresholds are measured and the rest are not.**
  `MIN_COVERAGE` (0.27 since 2026-09-30, the middle of the gap) and `MIN_STACK_LEVEL` (5, bounded
  3–2001) against 50 pages (2026-09-20e); the telemetry constants and every
  definition in `page_features` remain as chosen.
- ~~**The first `y` exists and is not usable yet**: 4 of 50 pages.~~ **People's
  ratings are the `y`** since 2026-10-30, on all 50.
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
  that can fail, resting on the six clips `tools/record_demo.py` makes in `demo/`.

**Open**
- No CI. The Electron tests skip silently without a host.
- Nothing supervises the Electron host.
- `test_levels.py` measures `dist/`, which can be stale.
- **No formatter or linter.** `black` would reformat 46 of 57 Python files;
  `ruff` reports 69 findings. Adopting them is for all three owners.
- ~~The venv is Python 3.12.3; `CLAUDE.md` says 3.11.~~ **Settled 2026-09-30**:
  CLAUDE.md says 3.12.
- `main` has `feat/multi-october-fifth-rows`, merged and pushed 2026-10-06
  after a clean full suite: whole rows, the mock's health check, the clips'
  records, the button approval, the window waited for, the fastest named, the
  kill-command rule, and the non-table limitation.
- ~~**The demo recordings show the old closing screen**~~ **Re-recorded
  2026-10-05** on our copy (EVALUATION.md, 2026-10-05d). Still not committed:
  a fresh clone has to record them.
- ~~**The demo recordings predate the questions**~~ **Re-recorded 2026-10-01**
  on our copy, answering the questions. They run at the copy's pace, about
  twice the live site's, and show invented trains; DEMO.md says so. `demo/` is
  not committed, so a fresh clone has to record them again.
- ~~**Most existing tests write to the system temp directory.**~~ **Fixed
  2026-10-03**: the root `conftest.py` sets `--basetemp` to `.scratch/pytest`;
  `test_basetemp.py` holds it.
- ~~**`feat/orchestrator-preview-capture` is committed and deliberately unmerged**:
  it keeps the site view repainting while it is photographed, and it stays out
  of `main` until the 100% capture rate is measured for real (see 2026-09-27
  above).~~ *Superseded 2026-10-17: measured again, the repainting made no
  difference; `browser.capture_site` asks again instead. The branch was deleted
  the same day.*
- **The demo recordings must be made before a demo**, on a machine with the
  stack up: `demo/*.webm` is gitignored, so a fresh clone has no fallbacks
  (DECISIONS.md, 2026-09-23).
- `tools/evaluation/host_overlay_run` drives the overlay of a running stack,
  which is how an interface claim gets checked live. It presses the step's own
  primary action and nothing else.
  `tools/evaluation/person_details_stack_run` is the one that can answer a
  question — it fills a box or presses a named answer — and is what the
  2026-09-30 live runs used.
- ~~**`replicas/railways/` is not started by the launcher**, deliberately:
  `railways` means the live site. The tests start it themselves; by hand it is
  `PORT=5200 python replicas/railways/app.py`. Nothing in `run.ps1` or
  `run.sh` opens the window on it, so watching the trip planner in the real
  overlay means watching it against the live site.~~ **Both launchers do now**:
  `railways-local` starts our copy and sends train goals to it; `railways` still
  means the live site.
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
