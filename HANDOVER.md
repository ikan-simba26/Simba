# SIMBA — handover

For someone who has never seen this repository and needs to reason about it
without reading the code. About twenty minutes end to end. Written on 2026-09-17
against commit `cc4704f`, and brought up to date since:

- **2026-09-18**: updated.
- **2026-10-05**: refreshed against `main` at `9fd09bc` plus
  `feat/multi-october-fifth`; sections 1 to 4, 6 to 8 and 10 rewritten.
- **2026-10-06**: whole rows, the window waited for, the fastest train named.
- **2026-10-15**: the interface work of 14 and 15 October: the checklist, named
  stages, the new home screen and colours, the review fixes.
- **2026-10-17**: the final-step rule: booking, paying and registering on our
  replicas behind a final screen, the offer as a quiet button, the press guard, and
  what Nahail and Aly must agree (below).
- **2026-10-17, `fix/stability`**: the 100% picture fixed (`browser.capture_site`),
  the false window pause, practice-copy endings, the full registration caveat, an
  offer that closes after ten minutes, the backend's run log, the host fit test's
  hang, and README checked on a fresh clone.
- **2026-10-17, `fix/final-touches`**: a registration said as a practice copy, every
  dependency pinned, the whole suite run on a fresh clone (which found a press-guard
  bug, now fixed), the booking clip re-recorded, the preview-capture branch deleted.
- **2026-10-18, `feat/personal`, merged 2026-10-23**: the welcome and the person's
  profile, their own tiles, the starting level as an estimator signal, and a reset.
- **2026-10-23**: ratings collected online, and the trace store's times, which tied
  on Windows and are now strictly increasing.
- **2026-10-23, `feat/rating-sets`**: two sets of 30 pictures with a five-point
  labelled question, replacing the forms before any rating was collected, and
  training's floor set at 8 ratings per page.
- **2026-10-30, `feat/estimator-trained`**: the estimator trained on people's ratings
  and judging the first page of a task.
- **2026-11-01, `fix/after-training`**: the overflow guard's move lasts one screen.
- **2026-11-02, `feat/brand`**: the logo, the icon and the title.
- **2026-11-02, `docs/tidy`**: this list, and what had gone stale in section 8.
- **2026-11-02, `eval/overwhelm-index`**: the model on 42 Pakistani public sites, which
  found a limit of the model more than anything about the sites (EVALUATION.md,
  2026-11-02b).
- **2026-11-02, `eval/visual-features`**: five first-screen features measured, Set 3's form,
  and the comparison, built and waiting for ratings (EVALUATION.md, 2026-11-02c). The live
  model is unchanged.

- **2026-11-04, `feat/show-me-once`, stage 1**: one feature after the freeze, by Raham's
  decision: a helper shows SIMBA a task once, and the person runs it from a tile. The bill on
  the billing copy, end to end (below, and EVALUATION.md, 2026-11-04).
- **2026-11-04, stage 2**: list choices and calendar days, a booking on the railways copy and a
  read-only lookup on the live train search (EVALUATION.md, 2026-11-04b).
- **2026-11-04, `fix/show-me-once`, merged 2026-11-05**: in a taught booking the person chooses the train from the
  page's own rows, only the press that books gets a final screen, and that screen shows what,
  how much and when as the page states them (EVALUATION.md, 2026-11-04c).

Section 9 is still the 2026-09-17 capture, and says so.

This file summarises and points. It does not repeat the four living
documents, and where they go deeper it links to them:

- [STATUS.md](STATUS.md) — per module, what is done and what is blocked, updated every task.
- [ARCHITECTURE.md](ARCHITECTURE.md) — how a task flows through the code, stage by stage, file by file.
- [DECISIONS.md](DECISIONS.md) — every decision that would be expensive to reverse, with what it cost.
- [EVALUATION.md](EVALUATION.md) — every number, dated, with method.

Also read [CLAUDE.md](CLAUDE.md) (the project's rules, which bind people and
tools alike), [CONTRACT.md](CONTRACT.md) (every message between the two
processes) and [RUNNING.md](RUNNING.md) (the launcher, and what to do when it
fails).

**For Nahail and Aly (2026-11-04): Show me once, after the freeze.** Raham decided to add one
feature after 1 November (DECISIONS.md, *"Show me once" goes in after the feature freeze*,
with its reason and cost). A helper — a carer, a family member, a teacher — does a task once on
the real site while SIMBA watches; SIMBA keeps it as a routine of perception's roles and labels
and the answer the helper pointed at; the person runs it from a tile, with no model. Both
stages are on `main`: the bill on the billing copy, then list choices and calendar days, a
booking on the railways copy and one read-only lookup on the live train search.

- **For both: the contract.** Six new message types and three optional fields, every one
  additive, listed in one table in CONTRACT.md, *Show me once*. A side that ignores them works as
  it did on 2026-11-03.
- **For Aly: the overlay and the host.** While a helper is watched the overlay is a 96px bar at
  the top and the host shows the website below it (`TeachBar.tsx`, `store.hostBar`,
  `main.ts`): the host shrinks only the overlay view, told by a line in the overlay's console, and
  the site view keeps its bounds at the origin and is never hidden. Also: "Show me once" on the
  name question of "Change my settings", the screen behind it (`TeachIntro.tsx`), the read-back
  as its own screen (`ReadBack.tsx`, no level row under it), a routine as a fourth kind of tile
  in the row of three, and saving to a file through the host's own save dialog. Every choice is
  in DECISIONS.md, *Show me once, stage 1: what was settled along the way*.
- **For Nahail: perception reads the helper's presses.** Each press is held in the page until
  `read_async` has read it, and is kept as the role, label, qualifier and which of several alike
  of the smallest element under the pointer by perception's boxes (`teach.element_at`). The
  answer is found by perception's pairs (`Content.pairs`), by the page's own label. Nothing in
  perception changed. Stage 2 leans on two of yours: a calendar day is a number whose `panel`
  names a month, and the site's own list is `options.longest_list`, as the train search reads it.
- **For Aly: one more contract field**, `TeachQuestion.kind` (`"day"`), so the bar asks "Is this
  day the same every time?".

**For Nahail (2026-11-02): the visual features, yours to review.** The page model cannot see
pictures, and now we know how far that goes: 33 of the 35 Pakistani sites have more of their
screen in pictures than any public page raters saw. `visual_features.py` measures five new
numbers, and Set 3's form is ready to send (`tools/rating/form/README.md`, section 7). With
ratings, `python -m backend.estimator.train_visual` compares old against new and applies a
gate written before any of those ratings existed. Three things want your eye: whether adding
`first_screen_text` is worth it at r = 0.98 with `text_density`; whether `motion` belongs in
a model of stills; and what a pass should lead to, since the app measures only the nine
(DECISIONS.md, *What the visual features can and cannot be*).

**For Aly (2026-11-02): the brand, yours to review.** Raham approved it as visual
polish under the freeze. `frontend/src/components/Brand.tsx` has the logo while SIMBA
opens and the small one on the home screen. Two things go past a picture: the overlay
now tries the backend again while that logo is up, because the launchers start the
window first, and the logos in `assets/brand/derived/` are the kit's with a background
or a tagline deleted. DECISIONS.md, *The brand*, has both.

**For Nahail (2026-10-30): the estimator is trained, and it is yours to review.**
Raham asked for it to go in before the freeze, so it went in without you. Nothing
below is settled against your judgement; each has an entry in DECISIONS.md, with
what it costs to change.

- **What is on `main`.** A ridge regression on your nine features, 15 raters, 50
  pages (`train.py`, unchanged in method). `backend/estimator/page_model.py`
  turns features into a score and a level; `rules.py` uses that for the first
  page and falls back on its three signs. Telemetry still goes through the
  provisional rules. Nothing fuses the two channels yet.
- **It is under your floor.** Set 2 has 5 usable raters, so 22 pages have 5
  ratings. `--min-ratings 5` is new and is written into the model. Three more
  usable Set 2 raters, then `python -m tools.rating.retrain "<Set 1>.csv"
  "<Set 2>.csv"` with no flag replaces everything (RUNNING.md).
- **Six things to confirm or change**: training under the floor on all 50 pages;
  keeping raters 5007 (−0.58 with everyone) and 5013 (0.10), since no exclusion
  rule existed; keeping the nine phone raters out, though they would meet the floor
  at once and move R² by only 0.007; the start level as `max(person, page)`;
  the cut points' method; and judging only the first page.
- **What surprised me, and you may read differently.** `text_density` does most of
  the work, and it is the only feature measured on what raters could see; `links`
  and `interactive` count the whole page, which may be why they do less. `overlays`
  carries nothing (coefficient +0.004), though the rules count it as a sign.
  Deeper pages score lower, and pages with more form fields score lower: raters
  judged how a picture looked, not how hard it was to fill in. Your call whether
  `form_fields` should stay in a model for a product that fills in forms.
- **`read_aloud` and `start_level` are not features**, as your decisions left
  them: the ratings have no person attached. `start_level` is used as the rules
  used it, as the person's own floor.
- **Every decision row now has `judged_by` and `inputs.judged`**, beside what the
  rules would have said, so the two can be compared on real sessions.
- **Since 2026-11-01 the rules undo a guard move on the next step** (`before_guard`,
  `inputs.after_guard`), as the overlay does. The figures with and without raters
  5007 and 5013 are side by side in EVALUATION.md, 2026-11-01, for your call on
  keeping them.

**For Nahail (2026-10-15): two changes that reach the estimator.**

- **Fewer training rows per task.** Since 2026-10-14, once the person has
  decided (a journey read back and agreed, a bill's number, a course), the
  safe moves — filling in, the calendar, searching, opening a page to read —
  run by themselves as a checklist. A checklist line is not a decision, so
  nothing about the person is recorded on it: no `Recorder.note_step` row, no
  telemetry, nothing for the level rules. A train journey whose goal names
  everything had 6 shown steps and now has 1 (the readback); a bill with its
  number, 3 to 1; a course, 3 to 2. Rows already in `data/steps.jsonl` are
  unchanged, but rows from before and after 2026-10-14 describe different
  kinds of screen, and should not be pooled without saying so. A person who
  ticks "Ask me before each thing I do" gets the old way, and a row per move.
- **`read_aloud` is a new telemetry signal** (`Telemetry.read_aloud`,
  additive and optional): how many times "Read this aloud" was pressed on the
  step. It is never counted as a help press, and the provisional rules do not
  read it. Whether and how the trained estimator uses it is yours to decide —
  someone who wants a step read may be finding it hard, or may simply prefer
  to listen (DECISIONS.md, *Read aloud is its own telemetry signal; Nahail to
  confirm*).

**For Nahail and Aly (2026-10-16): four things to agree.** Each was settled
by Raham for the orchestrator's side and is in use on `main`; none is
ratified. CLAUDE.md puts the contract and its rules with all three owners.
Disagreeing with any of them means a change, not a revert: each is listed
with what it would cost to undo.

1. **The final-step rule** (CLAUDE.md, replacing "never execute an
   irreversible action"; DECISIONS.md, *The final-step rule replaces…*). A
   payment, booking, registration or other change happens only on a replica
   (a page served from this machine), only after a final screen that says
   what will happen and shows what, how much and when as the page states
   them, with two buttons — do it / don't — no default and no timer. On a
   live site SIMBA only reads, and it never types card or bank details
   anywhere. Enforced in `loop.carry_out` for every planner. *To undo:* the
   booking, the pretend payment and registering all stop at their final
   screen.
2. **The contract fields added since 6 October**, every one additive and
   optional, so a side that ignores one still works:
   - `StepField.options` (10-06): the site's own list for a box to choose from.
   - `StepPresented.step_kind` (10-07): the shape beside a step.
   - `StepPresented.stage` and `TaskStarted.stages` (10-14): named stages in
     place of "Step X of Y".
   - `StepPresented.note` (10-14): what was wrong with the last answer.
   - `requires_confirmation: false` read as a checklist line, its one answer
     `"pause"`, and `TaskStart.confirm_each` (10-14).
   - `TaskCompleted.heading` (10-14): what the results are for.
   - `Telemetry.read_aloud` (10-14).
   - `StepPresented.coming` (10-15): the checklist lines still to come.
   - `PastGoal.label` (10-16): a remembered goal in a few words.
   - `TaskCompleted.scope`, `confirmation`, `caveat`, `proof` (with the new
     shape `Proof`) and `proof_note`; `HelpRequested.unconfirmed`; the
     `error` code `PREVIEW_LATE` (10-15 and 10-16): what was and was not
     done, the site's own confirmation and caveat, and the answer on the
     real page.
   - `StepPresented.final` with the new shape `Detail` (10-16): the final
     screen.
   - `TaskCompleted.offer` with the new shape `TaskOffer` (10-16): booking
     or paying as a quiet button; the run stays open for it.
   *To undo any one:* drop it on both sides; nothing else reads it.
3. **Read aloud** (CLAUDE.md, approved by Raham on 2026-10-14): a step read
   in the system's own English voice, only when the button is pressed, off
   by default, stopped when the step changes; its own telemetry signal.
   *To undo:* remove the button; `read_aloud` stays 0.
4. **Saving a password is a box to tick** under the sign-in boxes, not a
   second "Sign in and save my password" button (Raham's choice, 2026-10-15;
   CONTRACT.md, *Keeping a password*; no message changed). *To undo:* the
   overlay draws the backend's `remember` answer as a button again.

**And from `feat/personal` (2026-10-18, merged 2026-10-23): three more to agree.**

5. **The welcome and the person's profile** (Aly's area): four questions on
   first open, kept in the overlay's own storage; the name never leaves it.
   One additive field, `task.start.start_level`, carries the chosen level to
   the rules, which take it as their baseline. Read aloud "on" shows the
   button and "off" hides it — speech is still only on a press. *To undo:*
   drop the welcome; the rules start at 2 again.
6. **The person's own tiles**: additive `history.offered.tiles`,
   `task.completed.keep` and `task.start.tile`, and **a new message type,
   `tile.change`** (rename, move, remove, clear), answered with
   `history.offered`. Tiles are encrypted with the vault's key in
   `data/tiles.json`; the overlay never holds their details. *To undo:* drop
   the four on both sides and delete the file.
7. **For Nahail: the starting level as an estimator signal** — a
   `start_level` row per task and field on every telemetry row in
   `data/steps.jsonl`; how it relates to the estimator is in DECISIONS.md,
   *The starting level is a signal of its own*. It confounds pooled telemetry
   from today on.

**How to read the claims below.** Each "works" claim names its evidence: a
test file, or a dated entry in EVALUATION.md. A test is evidence for today,
because the suite was run today. A dated run is evidence for that date only.
Where something has not been re-checked since, this file says so.

---

## 1. What SIMBA is

A desktop app that does web tasks for people who find cluttered websites
overwhelming — the intended users include people with cognitive
disabilities. You tell it what you want ("Find the amount due on my
electricity bill"). It opens the real website in a browser view you never
see, works out what to click and type, and shows you **one plain step at a
time** in a calm overlay: a sentence saying what it is about to do, and a
button to let it. It checks every action actually worked before moving on.
When it cannot go on, it says so and stops.

It is designed so that the interface simplifies itself when the person
seems to be struggling (three "detail levels"), and so that the person can
always ask "What are you doing?" and see a picture of the real page with the
thing about to be touched ringed.

Three hard rules shape everything ([CLAUDE.md](CLAUDE.md)):

- **It changes something only on our own copies, and only after a final
  screen** (since 2026-10-16, replacing "never anything irreversible"). A
  booking, a payment or a registration happens only on a replica, after a
  screen that says what will happen and shows what, how much and when as the
  page states them, with "do it" and "don't" and no default. On a live site
  it only reads, and it never types card or bank details.
- **The language model never sees a credential**, and **never writes a
  selector**. Perception numbers the page's elements; the model answers
  "click 14"; the backend turns 14 back into something clickable.
- **Verification is not optional.** After every action the page is read again
  and checked against what the step expected.

It is a final-year project by three people — Nahail (perception, estimator),
Raham (orchestrator), Aly (interface) — with a hard deadline of December
2026. The walking skeleton (the whole loop end to end) was done in September.
**October is "from skeleton to evidence"**: feature freeze on 1 November,
November for evaluation and writing, December for the report and demo. The
priorities, in order, are in [CLAUDE.md](CLAUDE.md), *Current phase*: the
estimator trained on human ratings; the product for its audience; early
sessions with two or three people; evaluation readiness.

### The shape of it

Two processes that talk only over one WebSocket:

- **Frontend** — an Electron window with two views. Below is the real website,
  always 1280x800 in CSS pixels. On top, covering it completely, is the React
  overlay the person actually sees, laid out at the window's real size — the
  window fits the screen's work area, so on a 1080p laptop at 150% the overlay
  is 1266x606 and uses a compact layout (EVALUATION.md, 2026-09-25c). (Covered,
  not hidden: a hidden view stops being repainted and screenshots fail — 20/20
  captures covered, 2/5 hidden, measured in `spike/`.)
- **Backend** — Python and FastAPI. It attaches to the hidden website view
  over the Chrome DevTools Protocol and drives it with Playwright.

Before the loop, the typed goal is **routed** — run a flow, greet, decline, or
ask which — and **read for the person's own details** (where from, which day,
a reference number); anything missing is asked for, one question at a time,
before the site is touched. Then the loop, per step: read the page → decide
the next action → show it to the person → wait for them to agree → do it →
read the page again and check → retry once a different way, or stop and ask
for help. It ends on one of six screens; the one with an answer shows it,
with one plain sentence saying what it means.

Deciding the next action is done by one of three "planners", and they are
interchangeable because everything else is shared: a **hardcoded plan**
written by hand for a known site; an **LLM planner** that asks a model for
one action at a time; and **trace replay**, which repeats a run that worked
before and hands back to the other planner the moment the page stops
matching. Details: [ARCHITECTURE.md](ARCHITECTURE.md), stages 3–7.

---

## 2. What works today, by module

The full suite was last run on 2026-11-04, after stage 2: **1998 passed, 12 skipped, 0 failed** (backend 1340 in 1338s, frontend 658 in 1479s, as two halves), and the host fit test 3/3, all on mains (EVALUATION.md, 2026-11-04b). The 12 skips are
5 tests that need a running Electron window, 2 that need one and
`SIMBA_HOST_TESTS=1`, 3 that open the window themselves and need
`SIMBA_HOST_TESTS=1` (`frontend/test_window_fit.py`, run separately on
2026-11-03: 3 passed), and 2 that hit the live website (not run today).

### Perception — `backend/perception/` (Nahail)

Turns a live page into two things a planner can use: a numbered list of
interactive elements, and the readable content.

| Claim | Evidence |
|---|---|
| Reads a page into numbered elements with role, label, input type, value and position | `test_serializer.py`; re-read on three sites 2026-09-17 (samples in §9) |
| Detects something covering the page (a modal) from layout alone, and marks what is behind it | `test_overlays.py`; 1 overlay and 65 occluded elements on the registration replica, 2026-09-17 |
| Finds controls the page never declared — a dropdown option that is a bare `<li>`, a calendar day that is a bare `<td>` | `test_interactivity.py`; on the live site, 6 station options after typing and 42 day cells with the calendar open (EVALUATION.md, 2026-09-08) |
| Tells two calendar cells labelled "30" apart ("previous month") and says which month a calendar shows | `test_interactivity.py`; live-tested 2026-09-09 |
| Reads what a page *says*: headings, table cells paired with their column headers, prominent text | `test_content.py`; `P/WITHIN → 14,382` on the billing replica, 2026-09-17, and `Train No. → 2DN` on the live site, 2026-09-18 |
| Flags links that go nowhere | 44 of 66 elements on the registration replica, 2026-09-17 |
| Every value a label has, not the first — so "which trains?" is answered by all of them | `test_content.py`; fixed 2026-09-18 (EVALUATION.md, 2026-09-18b) |
| Reads the same in the Electron window as headless | all three sites read both ways, no serialized figure differs (EVALUATION.md, 2026-09-18c) |
| Bounds in CSS pixels at the source, so every reader uses the frozen viewport's units | `snapshot.parse`; every recorded figure re-measured both ways, none moved (2026-09-20) |
| The blocker threshold is measured on real pages, not guessed | `MIN_COVERAGE` 0.27, from 50 pages and 96 candidates; `MIN_STACK_LEVEL` 5, bounded 3–2001 (EVALUATION.md, 2026-09-20d, 2026-09-30f) |
| Never holds a typed password | `snapshot.parse` masks a password field (`test_serializer.py`, 2026-10-03) |
| Costs little | whole read 0.19s idle, 0.22s with the calendar open, on the live site (EVALUATION.md, 2026-09-08; a single-session figure, ±2x) |

### Orchestrator — `backend/orchestrator/` (Raham)

| Claim | Evidence |
|---|---|
| The loop presents, acts, verifies, retries once differently, and stops with `help.requested` after two failures | `test_verification.py`, `test_orchestrator.py` |
| All three planners run through identical execution and recovery | `test_shared_recovery.py` asserts identical message sequences under the same injected failure |
| A typed value is checked when typed *and* at every later read, and a value that disappears ends the run | `test_durability.py`; fired correctly twice on the live site, 2026-09-09. It fired **wrongly** once, 2026-09-17, on a date the page had only reformatted; a value matching the task's own declared value is now accepted, and on undeclared fields the false stop remains (STATUS.md, Orchestrator) |
| A task declares what it is about — values its goal names, which must hold at the end, and values it asks for, which are found and shown | `test_success_conditions.py`; `test_billing.py` shows `Your bill 14,382` and `Due 15-09-2026` arriving at the end from a page the run had left |
| The run that searched the wrong date would now fail instead of completing | `test_success_conditions.py` rebuilds that exact page |
| The hardcoded plan completes on both replicas | `test_orchestrator.py`, `test_billing.py` |
| The hardcoded plan completes on the live site | **2026-09-18**, 5/5 steps through the Electron window, search sent for the goal's date, and the train on the closing screen (EVALUATION.md, 2026-09-17i) |
| The LLM planner works through the same loop, with schema validation and one retry | `test_llm_loop.py`, `test_llm.py` with fake providers |
| The LLM planner drives the live site's dropdowns and calendar correctly, and finishes | **2026-09-17, two runs**: the first was stopped short by a false durability check; the second, through the Electron window, committed both stations, reached October, picked the 15th and sent the search for `2026-10-15` (EVALUATION.md, 2026-09-17f) |
| A step that fails is handed back and the run carries on, or stops safely | `test_setback.py`, 9 tests on a replica page rigged to fail; and 8 LLM runs on it, where a wrong recovery ended in `help.requested` rather than a false success (EVALUATION.md, 2026-09-18) |
| Trace replay records a run and replays it with no model calls | `test_replay.py`, `test_billing.py` (second run replays, 0 model calls) |
| Drives either its own headless Chromium or the Electron window's hidden view | headless: most of the suite. Electron: `test_electron_stack.py`, skipped without a running window |
| Routes the typed goal before anything runs: a flow, a greeting, a polite no, or a question when two are named | `router.py`, `test_router.py`; through the real stack on billing and railways (EVALUATION.md, 2026-09-21) |
| Runs on the person's own details and asks for what they did not say, one question at a time | `details.py`, `loop.run_brief`; live six times, "trains to Rawalpindi tomorrow" asked only where from (EVALUATION.md, 2026-09-30) |
| Plans a journey off the live station list, and a search for the wrong route or day fails | `TripPlanner`, `test_trip.py`, `test_success_conditions.py`; four rigged runs on real pages all ended in `help.requested` (2026-09-30) |
| A step that waits on a list gets one attempt, so a mistyped place is reported in 16.7s | `test_verification.py` (EVALUATION.md, 2026-10-01) |
| Keeps a password, encrypted, when the person asks, and types it itself after that | `vault.py`, `test_vault.py`; a whole LLM task searched for it everywhere and it is nowhere (EVALUATION.md, 2026-10-03b). **Windows only**; elsewhere the person is asked each time |
| Says in one plain sentence what the answer means, from the page's own values — and with rows names the fastest train, or says a tie is a tie | `voice.explain_*`, `test_explanation.py` (EVALUATION.md, 2026-10-03c, 2026-10-06b) |
| Carries results as whole rows, so each train keeps its own time even when times repeat | `Content.rows_for`, `Finding.rows`; on our copy and once on the live site (EVALUATION.md, 2026-10-05c) |
| Waits, rather than acts, while the SIMBA window is minimised or hidden, and asks before carrying on | `browser.window_watch`, `test_window.py`; in the real window, minimised mid-step for 10.4s (EVALUATION.md, 2026-10-06) |
| **The person decides, SIMBA clicks**: after the person's choices, the safe moves run as a checklist with one Pause; a real choice, anything typed, anything that went wrong and anything that registers or changes a record still asks | `test_checklist.py`; all three flows in the real window, light and dark (EVALUATION.md, 2026-10-14b, 2026-10-15) |
| Says when a train arrives the next day, from the journey time | `test_arrival.py`; the live site's two recorded rows, and one read-only live search on 2026-10-15 (EVALUATION.md, 2026-10-15) |
| A picture of the page never holds the person's answer: taken beside the wait, dropped after 5s | `test_preview_late.py` (EVALUATION.md, 2026-10-15) |

### Interface — `frontend/` (Aly)

| Claim | Evidence |
|---|---|
| One calm column: a home screen, a working state, a step, and six endings (found an answer, done, failed, stuck, stopped by the person, nothing changed), in a design system with a light and a dark theme | `test_terminal_states.py` renders each in a real browser, also reached from a step; before-and-after captures in both themes (2026-09-21) |
| **Every ending offers a way onward, and it can be pressed** | same file. Fixed 2026-09-17 twice: the stuck ending had nothing to press, and every ending reached from a step had an invisible leftover screen over its buttons (EVALUATION.md, 2026-09-17c) |
| **Every screen fits the window at 100%, 125% and 150%** — the home screen with or without history, every step, and since 2026-10-05 every ending, with nothing below 20px | `test_home.py`, `test_terminal_states.py` (38 endings at three sizes), and `test_window_fit.py` in the real window (EVALUATION.md, 2026-09-30d, 2026-10-05b) |
| The closing screen shows the answer under a heading saying what it is for: a ticket per train with when it leaves, arrives (and on which day) and how long, five at 100% and three in a short window, and a count past that | `test_closing.py` (EVALUATION.md, 2026-10-05, 2026-10-15) |
| Named stages instead of a step count (trains: From, To, Day, Search, Trains), fixed for the task | `test_questions.py`, `test_step_kind.py` (2026-10-14) |
| A task's first question fits at level 2 at every size, and no notice is ever shown on a task's first screen | `test_first_screen.py` (EVALUATION.md, 2026-10-14b) |
| Two colour directions, B (deep teal, the default) and A (`?palette=a`), each light and dark, every text pairing at 4.5:1 or more and every control's edge at 3:1 | `test_contrast.py`, read from `index.css` (EVALUATION.md, 2026-10-14b, 2026-10-15) |
| Signing in fits at every size; keeping the password is a box to tick | `test_sign_in.py` (EVALUATION.md, 2026-10-15) |
| A question can be answered, not only agreed to | `test_questions.py` (2026-09-30) |
| Three detail levels that fold into each other; level 3 is never the tallest | `test_levels.py` measures rendered heights (tests whatever is in `frontend/dist/`) |
| The level adapts in a real run, by provisional rules: a heavy page starts simpler, hesitation folds the step, calm steps bring it back, a lock holds | `backend/estimator/rules.py`; live on billing (EVALUATION.md, 2026-09-25) |
| Every word the overlay writes is in one file, `copy.ts`, and the backend's words obey the same rules | `test_copy.py`; 8 deliberate breakages tried on 2026-09-17, all caught |
| "What are you doing?" shows a screenshot of the real page with the target ringed | built and used; its rendering is not covered by a test. The capture behind it is 20/20 at 100%, 110%, 125% and 150% since 2026-10-17 (`browser.capture_site`; it was about half at 100%) |
| Telemetry — hesitation, pointer path, backtracks, re-reads, help presses — sent on every answer and on a 3s timer | `frontend/src/telemetry.ts`, `test_telemetry.py`; no keystrokes, field values or coordinates leave the window |
| The logo while SIMBA opens, until the backend's first message or 15s, and none under reduced motion; a small logo on the home screen alone; the app icon and the title `simba` | `test_brand.py`, `test_window_fit.py` (EVALUATION.md, 2026-11-02) |

### Estimator — `backend/estimator/` (Nahail)

| Claim | Evidence |
|---|---|
| Nine raw page features per page read — counts, a text density, a depth, a dead-link ratio, a reading grade | `page_features.py`, `test_page_features.py` |
| A corpus of 50 pages, read headless and in the window | `data/corpus.json`, recaptured with the rating pictures in one run (EVALUATION.md, 2026-10-03) |
| Each step's telemetry is paired with that step's page features and logged | `pairing.py`, `data/steps.jsonl` (not committed: it holds what people typed) |
| A training pipeline: agreement between raters, per-page means, ridge regression, 5-fold cross-validation, feature importance, cut points | `train.py`, `test_train.py`; on real ratings 2026-10-30 |
| **A model trained on 15 people's ratings judges a task's first page**, better than the rules and better than the mean: 5-fold R² 0.49, error 0.48 of a point. Raters agree weakly (alpha 0.318), and 22 pages are under the floor of 8 | `page_model.py`, `test_page_model.py`, `test_rules.py`; EVALUATION.md, 2026-10-30 to 2026-10-30c |
| Falls back to the rules with no usable model | `test_page_model.py`, `test_rules.py`, `test_adaptation.py` |
| Each page's score and reasons in plain words | `data/estimator_pages.json`; EVALUATION.md, 2026-10-30b |
| A rating tool: 50 pictures at 1280x800 in two balanced sets of 25, each rater seeing one set, three anchors of the other and two repeats — 30 pictures — answering "How overwhelming does this page feel?" from Not at all to Extremely (1–5), after two worked examples | `tools/rating/`, in person; and the same two sets as two Google Forms for raters who cannot come in, read back by `tools/rating/from_form.py` (`tools/rating/form/README.md`). Training needs 8 ratings on every page: at least 16 raters, 8 per set. 15 usable raters so far: 10 and 5 |

---

## 3. What is not built, and why

| Not built | Why not |
|---|---|
| **An estimator of the person** (a load score from what someone does, fused with the page's) | The page side is trained (2026-10-30). Hand-written provisional rules still read telemetry, with no person's behaviour behind their thresholds, because no person from the audience has used it |
| **A credential store beyond the minimum** | One saved password per site, Windows only, forgettable only from a sign-in step during a task. Deleting it from the home screen would need a new contract message |
| **Voice input** | In the contract, out of scope for now |
| **Replay tuning** (when to trust a trace over fresh planning) | Not started. Trace memory is off by default |
| **Anything that changes a real record** | By design: on our replicas only, behind a final screen; never on a live site |
| **CI** | Nobody has set it up. Tests run when someone runs them, and the tests that need the Electron window skip silently without one |
| **New sites or flows** | Not before asking: CLAUDE.md's October phase forbids them |

---

## 4. What the project has found

Seven findings, each with the numbers behind it. The full account of each is
in [EVALUATION.md](EVALUATION.md). The first six date from September and still
stand; the seventh is from the fit work of late September and October.

**1. What perception emits decides what the model can use — where it sits in
the prompt is unproven.** On the registration replica the model clicked
"Register" underneath an open modal in **10 of 10** runs, although the system
prompt told it to dismiss overlays first. Once perception marked the elements
`OVERLAY`/`OCCLUDED` and printed a banner, **0 of 10** did; steps went from
6–10 to exactly 5, and mean time from **61.3s to 17.1s** (that pair of times
is from one 2026-09-05 session and should be read as ±2x — see finding 6).
The calendar case is the same mechanism with nothing to argue about: the
distinction between the 15th of this month and the 15th of the next was *not
in the input at all*, and no prompt could have supplied it.

The narrower claim about *position* — the same words moved above the element
list — was built on two single calls and does not survive runs: on a rig where
every run needs the correction, placement changed **0 of 8** (2026-09-18).
EVALUATION.md's *"What perception emits decides what a planner can use"* now states
the two halves separately, one supported and one falsified.

**2. Success rate told us nothing.** It was **10/10 in every condition** ever
run on the registration replica — before overlay detection, after it, and
with it switched off. Meanwhile mean time was 61.3s, 17.1s and 44.5s, and in
the switched-off condition the backup JavaScript click was punching *through*
the modal in 10 of 10 runs and still passing. Every result since is reported
with steps, time and path beside it.

**3. A page we wrote is not a page someone else wrote.** The replicas were
built to be cluttered and were handled well. The first live site — a Vue
single-page app — broke nearly everything: dropdown options with no role that
perception could not see (18 elements before typing, 18 after), inputs that
are read-only until clicked, a search button with no name, and a search that
changes no URL or title. First run: **stuck after 2 of 4 steps, 124s**. After
five changes to perception and the loop: **5 of 5 steps, 46.1s, no model**
(2026-09-08).

**4. What the page shows is not what the application believes.** On the live
site the date field read back `2026-10-15` at every check, and the screenshot
showed it, while the application sent `"travelDate":""` and the server
answered with an error. Every check SIMBA has reads the page, so every check
agreed, and all were wrong together. No fix is in scope; watching network
requests is the recommended one. Every claim this project makes about
verification carries this boundary.

**5. The worst outcome is a plausible wrong answer, and we produced one.**
An LLM run (7 steps, 66.9s, 7 model calls, $0.00066) set the date to the 15th
of the month the calendar opened on, searched anyway, got **two real trains
for 2026-09-15** against a goal naming 2026-10-15, and reported the task
complete. It was possible because a change that morning let the run continue
past a disappearing value, and the success check was "results appeared". The
change was reverted the same day, and the task now requires the date field to
hold the goal's date. A stop the person can see is worth more than a finish
they cannot question.

**6. The hardcoded plan is a ceiling, not a baseline — and a wall clock from
this machine is worth ±2x.** On the registration replica it takes **3 steps**
against the LLM's **5 steps**. The times first published — 5.9s against 19.1s
— do not hold up: the same benchmark, same code, same machine, measured
**3.01s, 3.93s and 6.85s in one day** (EVALUATION.md, 2026-09-17h), so no
ratio between the arms should be quoted. **Report step count and model calls
first**; both were perfectly stable — zero variance across ten runs per arm —
where the timing was not. Wall clock goes second, with its range and its
conditions block. The finding itself does not rest on a time: the hardcoded
plan is faster and free because a person already wrote the answer into it, so
it measures perfect planning, not a rival to the LLM. **There is no honest
baseline for the LLM yet**; that needs both planners, in one session, on a
goal neither has seen.

**7. A screen is checked only where someone has rendered it.** The fit test
launched the window with no backend, so it only ever saw a home screen with
no history: six cards then put the text box off the window at every scale for
anyone with three remembered goals (2026-09-30d). The fit was never measured
for an ending at all, and the closing screen had put its buttons below the
window with three results or more, at every scale — "I'm done" at y=1057 in an
800px window with nine trains (2026-10-03c). Both were fixed, and the check now
covers every ending at three sizes, in a browser and in the real window. Its
first run found the fix itself still wrong for nine trains with eight journey
times, 87px off a 606px window (2026-10-05b). Every claim in §2 that something
"fits" now names the cases it was rendered in.

---

## 5. How to run it

All commands are from the repository root unless a `cd` says otherwise.
Windows PowerShell and bash are both given where they differ.

### Once: set up

```powershell
python -m venv backend\venv
backend\venv\Scripts\python -m pip install -r backend\requirements-dev.txt
backend\venv\Scripts\python -m playwright install chromium
cd frontend; npm ci; cd ..
```

```bash
python -m venv backend/venv
backend/venv/bin/python -m pip install -r backend/requirements-dev.txt
backend/venv/bin/python -m playwright install chromium
(cd frontend && npm ci)
```

Every version is pinned (2026-10-17): the requirement files name all 48
Python packages with `==`, and `npm ci` installs exactly `package-lock.json`.
Checked on a fresh clone, where the whole suite then ran (EVALUATION.md,
2026-10-17k).

The launchers look for `backend/venv` and fall back to `python` on the PATH.
The venv on the development machine is Python 3.12.3, and CLAUDE.md has
asked for 3.12 since 2026-09-30; until then it said 3.11, which nothing
depended on.

**For the LLM planner only**, copy `.env.example` to `.env` and fill it in.
The variables are `SIMBA_LLM_PROVIDER` (`anthropic` or `openai`),
`ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`,
`OPENAI_MODEL`, `SIMBA_LLM_EFFORT`. `.env` is never committed.

### Mode 1 — the tests

```powershell
backend\venv\Scripts\python -m pytest backend tools test_basetemp.py   # the backend half
backend\venv\Scripts\python -m pytest frontend                         # the frontend half
backend\venv\Scripts\python -m pytest frontend\test_copy.py            # one file
```

Two halves, never one `python -m pytest` over everything: two test files are
both called `test_checklist.py`, and a single run stops at collection
(checked on a fresh clone, 2026-10-17). Each half takes 20–25 minutes here;
the first lines of a run say whether the machine was on battery and how much
memory was free, because the same commit has taken 805s one day and 1435s
the next.

The tests start the replicas they need. Two groups skip unless asked for:

```powershell
$env:SIMBA_LIVE_TESTS = "1"; backend\venv\Scripts\python -m pytest -k live   # hits the live railways site
```

```powershell
# with an Electron host already running (Mode 2 or 4)
backend\venv\Scripts\python -m pytest backend\orchestrator\test_electron_stack.py
```

```powershell
# opens the window itself at 100%, 125% and 150%; needs npm run build first
$env:SIMBA_HOST_TESTS = "1"; backend\venv\Scripts\python -m pytest frontend\test_window_fit.py
```

`frontend/test_levels.py` measures `frontend/dist/`, so run `npm run build` in
`frontend/` first or it measures an old build. `test_terminal_states.py`
builds its own copy and does not have this problem.

### Mode 2 — the whole app, one command

```powershell
.\run.ps1                 # opens on the registration replica
.\run.ps1 billing         # opens on the billing replica
.\run.ps1 railways        # the LIVE site, read-only — a handful of runs, not a benchmark
.\run.ps1 railways-local  # our own copy of the train search — rehearse here
.\run.ps1 mock            # the overlay driven by a script; nothing real
```

```bash
./run.sh
./run.sh billing
./run.sh railways
./run.sh railways-local
./run.sh mock
```

The argument is only the page the window opens on (since 2026-09-25); what
runs is decided by the goal typed. Each starts the replicas, the Electron
window, and the backend attached to it; a SIMBA window opens; type a goal or
pick one and press Start. Ctrl+C stops everything. Ctrl+Shift+D in the window shows the
raw message log. [RUNNING.md](RUNNING.md) has the expected output and what to
do when a step of it fails.

**Every mode uses the hardcoded plan by default**, which spends no API quota.
To change what the backend does, set variables before launching; the
launcher passes them through:

```powershell
$env:SIMBA_USE_HARDCODED_PLAN = "0"    # use the LLM planner (needs .env)
$env:SIMBA_TRACE_MEMORY = "1"          # replay remembered runs, and record new ones
.\run.ps1 billing
```

```bash
SIMBA_USE_HARDCODED_PLAN=0 SIMBA_TRACE_MEMORY=1 ./run.sh billing
```

Nothing ever appears as a remembered goal on the home screen unless trace
memory was on for an earlier run: only trace memory writes to the store the
home screen reads. On the development machine, `traces.db` was empty on
2026-09-17.

### Mode 3 — smoke test the launcher

```powershell
.\run.ps1 mock -Seconds 20
```

```bash
SIMBA_RUN_SECONDS=20 ./run.sh mock
```

Starts everything, waits, stops. It passes if it prints `stopped` and nothing
is left listening.

### Mode 4 — the pieces by hand

Useful when changing one piece. Three terminals, in this order:

```powershell
# 1. a replica
backend\venv\Scripts\python replicas\registration\app.py        # port 5000
backend\venv\Scripts\python replicas\billing\app.py             # port 5100

# 2. the Electron window
cd frontend; $env:SIMBA_START_URL = "http://127.0.0.1:5000"; npm start

# 3. the backend, attached to the window
$env:SIMBA_USE_HARDCODED_PLAN = "1"; $env:SIMBA_BROWSER = "electron"
backend\venv\Scripts\python -m uvicorn backend.orchestrator.app:app --port 8000
```

`http://127.0.0.1:8000/` reports what the backend is configured to do. If an
editor terminal has `ELECTRON_RUN_AS_NODE` set, the window never appears;
unset it.

### Mode 5 — backend with its own headless browser

Leave out `SIMBA_BROWSER=electron` in step 3 above and skip step 2. The
backend drives its own invisible Chromium. Something still has to connect
to `ws://127.0.0.1:8000/ws` and answer each step: the overlay served as a
plain web page (`cd frontend; npm run dev`, then open the address Vite
prints), or a script. The test suite does this constantly with scripts.
**Using the overlay in an ordinary browser against the real backend has not
been checked recently**; treat it as likely rather than known.

### Mode 6 — the overlay alone, against the mock

```powershell
backend\venv\Scripts\python -m uvicorn tools.mock_backend:app --port 8000
```

Then open the overlay (Mode 2's `mock` does both). The mock plays a scripted
task that includes a level change and a skipped step, so both can be seen on
demand. It is also the demo-day fallback.

### Mode 7 — screen a new site before building anything for it

```powershell
backend\venv\Scripts\python -m tools.screen_site https://example.gov/ /search /help
```

Read-only: checks robots.txt, loads each page, reports what perception sees.
A `DISALLOWED` row means do not build a flow for that site.

### Mode 8 — re-run an evaluation

```powershell
backend\venv\Scripts\python -m tools.evaluation.hardcoded_registration_benchmark
```

Every table in EVALUATION.md has a script in `tools/evaluation/`; the table
*Which script produced which table* says which. Each script's docstring says
whether it spends model quota or touches the live site — several do both.

Each one prints what it is running under before it starts — commit,
interpreter, Playwright and Chromium, model, switches, machine and CPU load —
and the ones that write result files write that into the file. Read it before
trusting a wall clock: on this machine the same benchmark has measured 3.01s,
3.93s and 6.85s on one day (EVALUATION.md, 2026-09-17h). Steps and model calls
are the metrics to lead with.

Most of these scripts drive their own headless browser, which is **not** where
the product runs. One defect has already existed only in the Electron host
(the scrollbar spacer, 2026-09-17i). `viewport_perception_probe` reads each
site both ways in one run and diffs them — on 2026-09-18 every serialized
figure matched, and the raw markup did not (EVALUATION.md, 2026-09-18c). Run
it after anything that changes `content.py` or `serializer.py`:

```powershell
backend\venv\Scripts\python -m tools.evaluation.viewport_perception_probe
```

It needs the host and both replicas up (Mode 4), and it runs two read-only
live searches per environment.

### Mode 9 — the original architecture spike

See [spike/README.md](spike/README.md). It is the experiment the "covered,
not hidden" rule came from, and is not used by the app.

---

## 6. Where things are

Directory level. [ARCHITECTURE.md](ARCHITECTURE.md), *Where things live*,
has every file.

```
CLAUDE.md, CONTRACT.md         rules; the message contract (still a DRAFT)
STATUS.md, ARCHITECTURE.md,    the four living documents
DECISIONS.md, EVALUATION.md
README.md, RUNNING.md          setup; the launcher
run.ps1, run.sh                one command per flow

shared/                        schema.py and schema.ts — every message, mirrored on both sides

backend/perception/            the page → numbered elements + readable content
backend/orchestrator/          the loop, the three planners, the plans for each site,
                               the LLM interface, trace memory, the WebSocket server,
                               router.py and details.py (reading the goal), vault.py,
                               voice.py (every fixed string the backend puts on screen)
backend/estimator/             page features, the provisional level rules, telemetry
                               pairing, the training pipeline, the trained model as the
                               app reads it (page_model.py)

frontend/electron/             the window: website view below, overlay on top
frontend/src/                  the React overlay; copy.ts holds every word it writes
frontend/test_*.py             tests that compile or render the overlay for real

assets/brand/                  the logo kit as supplied; derived/ for what the overlay needs

replicas/registration/         a cluttered student portal with a blocking modal (port 5000)
replicas/billing/              a cluttered electricity bill lookup with a cookie bar (port 5100)
replicas/railways/             our own copy of the live train search, for repeated runs (port 5200)
tools/mock_backend.py          a scripted backend for working on the overlay alone
tools/screen_site.py           read-only site screener
tools/evaluation/              the scripts behind every table in EVALUATION.md
tools/rating/                  the rating pictures, the session that collects ratings, the online forms
tools/record_demo.py           records the demo's fallback clips into demo/
spike/                         the original Electron + CDP experiment

data/                          the corpus, rating pictures and trained model (committed);
                               steps.jsonl, ratings.jsonl, vault.json (never committed)
.scratch/, logs/, traces.db,   gitignored: scratch and test temp files, LLM transcripts,
demo/*.webm                    the trace store, the demo clips
```

The three flows, what each one is for, and what each plan does step by step
are in `backend/orchestrator/plan.py` (registration),
`billing_plan.py` and `railways_plan.py`. The live one is
`https://www.pakrailways.gov.pk/train`, and it is read-only: it fills a search
and reads a timetable.

**The evaluation scripts** are in `tools/evaluation/` (until 2026-09-17 they
were in the gitignored `.scratch/`). EVALUATION.md, *Which script produced
which table*, maps every result to one; three results have none.

---

## 7. What is blocked, and what is only not done

**Blocked** — cannot move until named people act:

| Blocked | On | Notes |
|---|---|---|
| **Ratifying the contract** | Nahail, Raham and Aly in one session | `CONTRACT.md` has been a draft since 2026-09-04. Message types added since — `step.failed`, `history.offered`, `goal.answered` — are recorded as pending; the additive optional fields (`Finding.values`, `Telemetry.answered`, `task.completed.explanation`, `level.override`'s `by`) need no session under CLAUDE.md's rule |

That is the only one. Until 2026-09-17 several items below were recorded as
blocked on quota, days after the quota had reset.

**Not blocked, not done:**

| Item | What it needs | Notes |
|---|---|---|
| **Three more usable Set 2 raters** | Three people on a laptop, in person (`tools/rating/`, even numbers) or on the Set 2 form | 15 usable raters so far, 10 and 5. Then `python -m tools.rating.retrain` with no flag, and the model is no longer under the floor. Priority 1's last step |
| **Early sessions with two or three people** | People, including someone who works with people with cognitive disabilities | Nobody from the audience has seen the interface. Second and third October priorities |
| **The stronger-model ablation** | About 100 model requests | Free-tier limits spread that over days; a paid key does it in one sitting. The biggest gap in the evaluation |
| **An honest baseline for the LLM** | A goal neither planner has seen | |
| **Benchmarks re-run on current perception** | Runs | Every model-behaviour figure predates the perception work it would now measure |
| **A durability check that tells reformatting from undoing, on undeclared fields** | A design choice — Raham's | Declared fields were fixed on 2026-09-17. Undeclared fields still false-stop, and that is where the LLM planner works |
| **Trace memory against a real model** | One run with `SIMBA_TRACE_MEMORY=1` | Replay itself is tested |
| **The demo clips on a fresh clone** | Recording, on a machine with the stack up | Re-recorded 2026-10-05 on our copy and showing the current closing screen, but not committed, so a fresh clone has none. Do not minimise the SIMBA window while recording |

**Uncertain: the quota itself.** The documents disagree on how many requests
a day the free model allows and which model name the stronger one was
(`gemini-3.6-flash` or `gemini-3.8-flash`). Check the provider's console
before planning a run around any number here. EVALUATION.md's 2026-09-17
entry lists the contradiction.

---

## 8. Open design questions

Flagged, not decided. Each has a home in STATUS.md or DECISIONS.md with the
options and a recommendation; this is the list.

**The interface**

1. **Should the stuck screen hand the task over?** It now says only what is
   true — "I'm stuck, so I've stopped." — because nothing resumes and the page
   is covered. Letting the person finish the step themselves would be a
   feature: reveal the page, then carry on. *Settled for now, 2026-09-17; the
   larger question is open.*
2. *(Settled 2026-10-16: "I'm done" and "Do something else", which did the
   same thing, are one "Back to start".)*
3. *(Settled 2026-09-17: pressing "Stop this" now shows "I've stopped, as you
   asked.", not a failure.)*
4. **The stuck screen shows a technical reason** (`could not find 'Close' on
   the page`) in small type. The skipped-step notice deliberately removed this
   kind of text.
5. *(Settled 2026-10-14: no count; each task names its stages once, and the
   row of names never grows.)*
6. **Found values are shown exactly as the page wrote them** — `15-09-2026`.
   Reformatting means inventing; not reformatting is hard for this audience.
7. *(Settled 2026-10-14: an overflow adjustment says "I've made this smaller
   so it fits."; the level rules' return says "I'm showing a bit more now.")*
7b. **The closing screen's layout, for Aly to review** (2026-10-05). To fit
   nine results at 150% the sentence replaced the "Here's what I found"
   lead-in, and the two buttons sit side by side — the one screen whose
   buttons are not stacked. A detail that cannot be put beside its result is
   one line under the list. DECISIONS.md has the alternatives.
7c. **The home screen's cards lead into questions.** "Check my electricity
   bill" names no bill, so pressing it asks for a reference number. Aly's call;
   STATUS.md, Infrastructure.

**The backend**

8. **What the LLM and replay show on screen is also the model's own history.**
   "Fill in From." reads as an order to the person, and "element 13" as
   jargon, but changing the wording changes the prompt. Separate the two
   strings?
9. **Should finding the answer be part of success?** A billing run that never
   read the amount would currently complete with no answer rather than stop.
   On 2026-09-17 a railways run did exactly that — found the train, showed
   nothing — and only a perception fix caught it; nothing in the loop would
   have.
10. **Named values are checked on the final page only**, so a value typed on
    the first page of a multi-page flow cannot be checked.
11. *(Settled 2026-09-18: a finding carries every value for its label, and
    the closing screen shows them.)*
12. *(Settled 2026-10-03: `task.completed.summary` stays the goal plus a URL,
    which tests and logs read, and the human sentence is a new optional field,
    `explanation`.)*
12b. *(Settled 2026-10-05: results travel as whole rows, `Finding.rows`, so
    each train keeps its own time even when times repeat.)*
12c. *(Settled 2026-10-06: a run waits while the window is minimised or
    hidden, and carries on only when the person says so.)*
12d. **Results not from a table still pair by list length**, and can be paired
    wrongly; no current flow hits it. A known limitation, with no work planned
    before the freeze (DECISIONS.md).
13. **The JavaScript click fallback can click through a modal** when overlay
    detection is off, and the run passes. Should the fallback refuse an
    element perception knows is covered?
14. **When to allow continuing past a disappearing value again.** Reverted
    because it produced a wrong answer; the stated condition for revisiting is
    a success check that can catch a wrong answer, and that is not yet met.
14b. **How long a run waits on its closing screen's offer** (2026-10-17):
    ten minutes, then it closes and the offer goes (`loop.OFFER_IDLE_S`).
    Chosen without anyone using it; a person who decides later has to search
    again.
14c. *(Settled 2026-10-17: a registration on our copy ends in practice words
    too, the portal's caveat kept.)*
14e. *(Settled 2026-10-21: the profile and tiles go, and goals from before a
    reset are never offered. DECISIONS.md, *Forgetting the person: nothing from
    before the reset is ever shown*.)*
14d. **The host's window counts only for a task started in it**
    (`window.__simbaStarted`, 2026-10-17), and a window hidden by something
    else is never noticed. Nothing in SIMBA hides it today.

**The contract**

15. **`history.offered`** — a new message type, pending ratification.
    [CONTRACT.md](CONTRACT.md) has the reasoning and the costs. It is no longer
    stale: since 2026-10-18 "Back to start" opens a new connection, and is offered
    the goals as they now stand.

16. **Is prompt prominence worth anything?** "Anything a planner must act on
    goes above the element list" was built on three cases, and the setback one
    turned out to rest on a single re-asked decision. Measured properly on
    2026-09-18 it changed nothing in eight runs. The rule is cheap to keep and
    is no longer evidence; the two other cases still stand. What would settle
    it is the same rig against a stronger model.

---

## 9. What a planner actually receives

Real output of `perception/serializer.py:read_async`, rendered by
`llm_loop.render_page` exactly as the model is given it, captured
2026-09-17 at 1280x800. **Not re-captured since**: perception has changed
underneath (CSS-pixel bounds, measured thresholds), so read this as the shape
of what a planner gets, not today's exact output.

### The live site

`https://www.pakrailways.gov.pk/train`, loaded once with the screener's user
agent and not touched. Title `RABTA`. All 18 elements:

```text
1. link 'Home'
2. link 'Train Timings'
3. link 'Tickets'
4. link 'Order'
5. link 'My'
6. button 'زبان'
7. link 'زبان'  <- dead link, goes nowhere
8. link 'Log in'
9. button 'Log in' [input type=button]
10. textbox 'From' [input type=text]
11. textbox 'To' [input type=text]
12. textbox 'Departure Date' [input type=text]
13. button '' [input type=button]
14. link 'Privacy Policy'  <- dead link, goes nowhere
15. link 'FAQs'  <- dead link, goes nowhere
16. link ''
17. link ''
18. link ''
```

Readable content on this page: one prominent value, `TRAIN TIMINGS` (24px).

What to notice. Element 13 is the search button: it has no name, so the only
honest way to describe it is `button ''`, and it is distinguishable only
because it is the one unnamed button. Elements 16–18 have no names either.
`زبان` is "language". Nothing here says a dropdown or calendar exists — those
appear only once a field is clicked, as `option` elements marked `INFERRED`.

The same page with the date picker open, **as recorded in the 2026-09-09 LLM
run** (EVALUATION.md; not re-captured today, and before qualifiers and the
month banner existed):

```text
A LIST OF CHOICES IS OPEN, with 42 option(s) marked INFERRED below. ...
22. button 'September'
24. button 'Next Month' [input type=button]
25. option '30'   <- INFERRED
...
41. option '15'   <- INFERRED
...
56. option '30'   <- INFERRED
```

Two cells called `30` and nothing to tell them apart — which is why
qualifiers now exist, and a banner reading `IT IS SHOWING: 2026 September`
is now printed above the list.

### A replica with a modal up

The registration replica's course list straight after signing in; 66
elements, of which the first eleven and one course button:

```text
AN OVERLAY IS COVERING THE PAGE. Everything marked OCCLUDED is unreachable until it is dismissed, using an OVERLAY element.

1. button 'Close' [input type=button]  <- OVERLAY
2. link 'Home'  <- OCCLUDED, cannot be clicked  <- dead link, goes nowhere
3. link 'Admissions'  <- OCCLUDED, cannot be clicked  <- dead link, goes nowhere
4. link 'Academics'  <- OCCLUDED, cannot be clicked  <- dead link, goes nowhere
5. link 'Athletics'  <- OCCLUDED, cannot be clicked  <- dead link, goes nowhere
6. link 'Library'  <- OCCLUDED, cannot be clicked  <- dead link, goes nowhere
7. link 'Housing'  <- OCCLUDED, cannot be clicked  <- dead link, goes nowhere
8. link 'Dining'  <- OCCLUDED, cannot be clicked  <- dead link, goes nowhere
9. link 'Parking & Transit'  <- OCCLUDED, cannot be clicked  <- dead link, goes nowhere
10. link 'IT Help Desk'  <- OCCLUDED, cannot be clicked  <- dead link, goes nowhere
11. link 'Registrar'  <- OCCLUDED, cannot be clicked
...
36. button 'Register for CS-401' [input type=submit]  <- OCCLUDED, cannot be clicked
```

### The content channel

The model is not shown content today; success checks and findings use it.
The billing replica's results page, one table row, as pairs:

```text
REF NO    -> 04141234567890
MTR NO    -> K80-4471192
PREV      -> 38714
CURR      -> 39126
UNITS     -> 412
P/WITHIN  -> 14,382
P/AFTER   -> 14,957
DUE DT    -> 15-09-2026
```

The billing plan declares that `P/WITHIN` is "Your bill" and `DUE DT` is
"Due", and those two reach the closing screen.

---

## 10. Where these documents disagree, as of today

Stated so nobody trusts the wrong one:

- EVALUATION.md contains several statements its own later entries contradict.
  Its 2026-09-17 entry lists them, and it is append-only, so the older entry
  is never corrected in place: read the newest entry on a subject.
- `CONTRACT.md`'s examples for `step.presented` and `help.requested` still use
  wording the system no longer says ("Not now", "I'll carry on from there").
- STATUS.md's dated "Changed on" sections are a log: an item marked open on
  one day may be fixed in a later one. The per-module sections below them are
  current.
- This file was not refreshed between 2026-09-18 and 2026-10-05; anything it
  said in that window about the estimator, telemetry, the vault or the closing
  screen was out of date.

Fixed on 2026-09-17, and listed here earlier the same day: README.md's test
count and start command, frontend/README.md calling the overlay a harness,
and CLAUDE.md and README.md naming `ruff` and `black`, which were never
installed. Those two are now described as not in use.
