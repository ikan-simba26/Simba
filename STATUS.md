# Status

Per module: what is done, what is in progress, what is open, and what is
actually blocked and on whom. **Update at the end of every task.**

Owners are from `CLAUDE.md`. **"Blocked" means work cannot proceed until a
named person or external thing acts.** Something nobody has done yet is
*open*, not blocked. Until 2026-09-17 this file mixed the two, and several
items sat under "blocked on quota" for eight days after the quota had reset.

**Last updated:** 2026-09-17 (third pass) · 292 passing, 7 skipped (5 need an Electron host, 2 need `SIMBA_LIVE_TESTS=1`) · full suite 329s and 367s on two runs of the same tree, which is the spread to expect from a wall clock here (EVALUATION.md, 2026-09-17e)

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

**The run found the train and did not show it.** The live results' header row
is extracted as a table of its own, so nothing pairs `Train No.` with `2DN`,
and the closing screen said "That's done." instead of the answer. Now the most
important open item in perception.

**A published benchmark figure does not reproduce, by 2x.** The hardcoded plan's 5.9s
from 2026-09-06 re-runs at 3.0s with that very commit. The code and the venv
are ruled out; the cause is not established. Corrected in EVALUATION.md, with
the ratios derived from it withdrawn (2026-09-17e).

**Every ending reached from a step was unpressable** — found and fixed on
2026-09-17, present since at least `cc4704f`. After any step, an invisible
leftover of the step screen covered the ending's buttons (EVALUATION.md,
2026-09-17c).

The hardcoded plan last completed the live flow on 2026-09-09 (54s). Not
re-run since; the live page's structure was unchanged when re-read on
2026-09-17.

What the system cannot do is trust its own result: the DOM is not the
application's state (EVALUATION.md).

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

**In progress**
- Nothing.

**Open — Nahail's call**
1. **The DOM is not the application's state.** No defence except driving
   widgets the way a person must.
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
   and this failed only in the 1280x800 host, so other readings may be
   viewport-dependent in ways nothing has checked.
9. `value_for` returns the first matching pair, so even when pairing works
   "which trains?" shows one train.
10. Page-side load features for the estimator: not started.

**Blocked**
- Nothing.

---

## Orchestrator — Raham · `backend/orchestrator/`

**Done**
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
- **Durable verification still stops correct runs on undeclared fields.**
  Since 2026-09-17 a field that now holds its task-declared value is accepted;
  every other field is compared with what was typed, character for character,
  so a page that reformats a value there still ends the run. An LLM planner
  types into whatever it chooses, so this is where it will meet it. Options
  and costs in DECISIONS.md.
- **Setback placement is still unmeasured.** Two runs today, neither with a
  failed step. A live site will not fail on demand; answering it needs a run
  on a page made to fail one step.
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

**In progress**
- Nothing.

**Open — Aly's call**
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
- Nothing, deliberately deferred until the skeleton ran end to end, which it
  does.

**Open**
- Not started. It needs page-side load features from perception (also
  Nahail's, also not started) and `telemetry` from the frontend (specified,
  unsent). The frontend already honours `load.updated` and the level lock.

**Blocked**
- Nothing. Previously listed as blocked on the load features, which are
  simply the first piece of the same unstarted work.

---

## Shared contract — all three owners · `shared/`, `CONTRACT.md`

**Done**
- Both schema files mirror every message. `step.failed`, `findings` and
  `history.offered` added; `history.offered` recorded as pending
  ratification with its reasoning and costs.
- No schema file changed on 2026-09-17.

**Open**
- `telemetry` is specified and nothing sends it.
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
- **The 5.9s hardcoded figure does not reproduce** and is corrected; its cause is not
  established (2026-09-17e). The LLM timings from 2026-09-05 were taken the
  same way and have not been re-run.
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
- The day's work is committed on `feat/orchestrator-evaluation-scripts`, not
  merged, and not pushed.

**Blocked**
- Nothing.
