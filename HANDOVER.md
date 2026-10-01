# SIMBA — handover

For someone who has never seen this repository and needs to reason about it
without reading the code. Written 2026-09-17 against commit `cc4704f`, and
updated twice since: that evening after the owed LLM run, and on 2026-09-18
after the fixes that followed it. About twenty minutes end to end.

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

- **It never does anything irreversible.** No payments, no submissions that
  change real records. It stops at the confirmation screen.
- **The language model never sees a credential**, and **never writes a
  selector**. Perception numbers the page's elements; the model answers
  "click 14"; the backend turns 14 back into something clickable.
- **Verification is not optional.** After every action the page is read again
  and checked against what the step expected.

It is a final-year project by three people — Nahail (perception, estimator),
Raham (orchestrator), Aly (interface) — with a hard deadline of December
2026. The current phase is the "walking skeleton": the whole loop working
end to end before any intelligence is added on top.

### The shape of it

Two processes that talk only over one WebSocket:

- **Frontend** — an Electron window with two views stacked at 1280x800. Below
  is the real website. On top, covering it completely, is the React overlay
  the person actually sees. (Covered, not hidden: a hidden view stops being
  repainted and screenshots fail — 20/20 captures covered, 2/5 hidden,
  measured in `spike/`.)
- **Backend** — Python and FastAPI. It attaches to the hidden website view
  over the Chrome DevTools Protocol and drives it with Playwright.

The loop, per step: read the page → decide the next action → show it to the
person → wait for them to agree → do it → read the page again and check →
retry once a different way, or stop and ask for help.

Deciding the next action is done by one of three "planners", and they are
interchangeable because everything else is shared: a **hardcoded plan**
written by hand for a known site; an **LLM planner** that asks a model for
one action at a time; and **trace replay**, which repeats a run that worked
before and hands back to the other planner the moment the page stops
matching. Details: [ARCHITECTURE.md](ARCHITECTURE.md), stages 3–7.

---

## 2. What works today, by module

The full suite was last run on 2026-09-18: **323 passed, 7 skipped, 459s**. The
7 skips are 5 tests that need a running Electron window and 2 that hit the
live website; **none of those 7 were run today.**

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
| Costs little | whole read 0.19s idle, 0.22s with the calendar open, on the live site (EVALUATION.md, 2026-09-08) |

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
| Drives either its own headless Chromium or the Electron window's hidden view | headless: most of the suite. Electron: `test_electron_stack.py`, **skipped today** |

### Interface — `frontend/` (Aly)

| Claim | Evidence |
|---|---|
| One calm column: a home screen, a working state, a step, and five endings (found an answer, done, failed, stuck, stopped by the person) | `test_terminal_states.py` renders all five in a real browser, three of them reached from a step |
| **Every ending offers a way onward, and it can be pressed** | same file. Fixed 2026-09-17 twice: the stuck ending had nothing to press, and every ending reached from a step had an invisible leftover screen over its buttons (EVALUATION.md, 2026-09-17c) |
| Three detail levels that fold into each other; level 3 is never the tallest | `test_levels.py` measures rendered heights (tests whatever is in `frontend/dist/`) |
| Every word the overlay writes is in one file, `copy.ts`, and the backend's words obey the same rules | `test_copy.py`, 25 tests; 8 deliberate breakages tried on 2026-09-17, all now caught |
| "What are you doing?" shows a screenshot of the real page with the target ringed | built and used; its rendering is not covered by a test |
| A level change the person did not make is always announced | `store.ts`, `LevelControl.tsx`; no dedicated test |

### Estimator — `backend/estimator/` (Nahail)

Empty. See §3.

---

## 3. What is not built, and why

| Not built | Why not |
|---|---|
| **The estimator** (cognitive load score that changes the detail level) | Deliberately deferred by CLAUDE.md until the skeleton ran end to end. It now does, so it is unblocked, but it needs perception's page-side load features, which are not started. The frontend already obeys `load.updated`; only the mock backend sends it |
| **Telemetry** (hesitation, cursor path, backtracks) | In the contract, sent by nothing. It is the estimator's other input |
| **The credential vault** | Not started. Today a password travels from the overlay to the backend in the step response. The backend already refuses to type a password a planner made up |
| **Voice input** | In the contract, out of scope for now |
| **Replay tuning** (when to trust a trace over fresh planning) | Not started |
| **Anything irreversible** | By design, permanently |
| **CI** | Nobody has set it up. Tests run when someone runs them |

---

## 4. What the project has found

Six findings, each with the numbers behind it. The full account of each is in
[EVALUATION.md](EVALUATION.md).

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

---

## 5. How to run it

All commands are from the repository root unless a `cd` says otherwise.
Windows PowerShell and bash are both given where they differ.

### Once: set up

```powershell
python -m venv backend\venv
backend\venv\Scripts\python -m pip install -r backend\requirements-dev.txt
backend\venv\Scripts\python -m playwright install chromium
cd frontend; npm install; cd ..
```

```bash
python -m venv backend/venv
backend/venv/bin/python -m pip install -r backend/requirements-dev.txt
backend/venv/bin/python -m playwright install chromium
(cd frontend && npm install)
```

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
backend\venv\Scripts\python -m pytest                     # everything; ~5 minutes
backend\venv\Scripts\python -m pytest frontend\test_copy.py   # one file
```

The tests start the replicas they need. Two groups skip unless asked for:

```powershell
$env:SIMBA_LIVE_TESTS = "1"; backend\venv\Scripts\python -m pytest -k live   # hits the live railways site
```

```powershell
# with an Electron host already running (Mode 2 or 4)
backend\venv\Scripts\python -m pytest backend\orchestrator\test_electron_stack.py
```

`frontend/test_levels.py` measures `frontend/dist/`, so run `npm run build` in
`frontend/` first or it measures an old build. `test_terminal_states.py`
builds its own copy and does not have this problem.

### Mode 2 — the whole app, one command

```powershell
.\run.ps1                 # registration replica
.\run.ps1 billing         # billing replica
.\run.ps1 railways        # the LIVE site, read-only — a handful of runs, not a benchmark
.\run.ps1 mock            # the overlay driven by a script; nothing real
```

```bash
./run.sh
./run.sh billing
./run.sh railways
./run.sh mock
```

Each starts, in order, the replica (if any), the Electron window, and the
backend attached to it; a SIMBA window opens; type a goal or pick one and
press Start. Ctrl+C stops everything. Ctrl+Shift+D in the window shows the
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
$env:SIMBA_FLOW = "registration"; $env:SIMBA_USE_HARDCODED_PLAN = "1"; $env:SIMBA_BROWSER = "electron"
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
                               voice.py (every fixed string the backend puts on screen)
backend/estimator/             empty

frontend/electron/             the window: website view below, overlay on top
frontend/src/                  the React overlay; copy.ts holds every word it writes
frontend/test_*.py             tests that compile or render the overlay for real

replicas/registration/         a cluttered student portal with a blocking modal (port 5000)
replicas/billing/              a cluttered electricity bill lookup with a cookie bar (port 5100)
tools/mock_backend.py          a scripted backend for working on the overlay alone
tools/screen_site.py           read-only site screener
tools/evaluation/              the scripts behind every table in EVALUATION.md
spike/                         the original Electron + CDP experiment

.scratch/, logs/, traces.db    gitignored: scratch scripts, LLM transcripts, trace store
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
| **Ratifying the contract** | Nahail, Raham and Aly in one session | `CONTRACT.md` has been a draft since 2026-09-04. Two message types were added since, `step.failed` and `history.offered`; the second is recorded as pending |

That is the only one. Until 2026-09-17 several items below were recorded as
blocked on quota, days after the quota had reset.

**Not blocked, not done:**

| Item | What it needs | Notes |
|---|---|---|
| **A durability check that tells reformatting from undoing, on undeclared fields** | A design choice — Raham's | Declared fields were fixed on 2026-09-17 and the railways LLM run then completed. Undeclared fields still false-stop, and that is where the LLM planner works |
| **Why a model prefers a plausible wrong button to a setback it was just given** | Measurement, not a fix | Answered on 2026-09-18: placement changed nothing across 8 runs; what decided recovery was the options the page left. A stronger model on the same rig is the next thing to try |
| **The stronger-model ablation** | About 100 model requests | Free-tier limits spread that over days; a paid key does it in one sitting. The biggest gap in the evaluation |
| **An honest baseline for the LLM** | A goal neither planner has seen | |
| **The estimator** | Page-side load features, then the estimator — both Nahail's, neither started | |
| **The credential vault** | Aly, not started | |
| **Trace memory against a real model** | One run with `SIMBA_TRACE_MEMORY=1` | Replay itself is tested |
| **A second train from the railways results** | Perception — Nahail's | `value_for` returns the first pair, so "which trains?" answers with one |

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
2. **"I'm done" and "Do something else" do the same thing.** Both go to the
   home screen. What should "I'm done" do?
3. *(Settled 2026-09-17: pressing "Stop this" now shows "I've stopped, as you
   asked.", not a failure.)*
4. **The stuck screen shows a technical reason** (`could not find 'Close' on
   the page`) in small type. The skipped-step notice deliberately removed this
   kind of text.
5. **"Step 2 of 6"** uses a word the copy rules forbid. Should a count be on
   screen at all?
6. **Found values are shown exactly as the page wrote them** — `15-09-2026`.
   Reformatting means inventing; not reformatting is hard for this audience.
7. **"I'm showing a bit more again."** is also what an overflow adjustment
   says, where "again" may be untrue.

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
11. **The results table's first row is the answer.** Two trains came back and
    "Train" shows one of them.
12. **`task.completed.summary`** is the goal plus a URL, read by tests; the
    contract's example shows a human sentence. Which is it for?
13. **The JavaScript click fallback can click through a modal** when overlay
    detection is off, and the run passes. Should the fallback refuse an
    element perception knows is covered?
14. **When to allow continuing past a disappearing value again.** Reverted
    because it produced a wrong answer; the stated condition for revisiting is
    a success check that can catch a wrong answer, and that is not yet met.

**The contract**

15. **`history.offered`** — a new message type, pending ratification. It is
    also stale: the home screen reached after a task shows the goals from
    before that task. [CONTRACT.md](CONTRACT.md) has the reasoning and the
    costs.

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
2026-09-17 at 1280x800.

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
  Its 2026-09-17 entry lists them.
- `CONTRACT.md`'s examples for `step.presented` and `help.requested` still use
  wording the system no longer says ("Not now", "I'll carry on from there").

Fixed on 2026-09-17, and listed here earlier the same day: README.md's test
count and start command, frontend/README.md calling the overlay a harness,
and CLAUDE.md and README.md naming `ruff` and `black`, which were never
installed. Those two are now described as not in use.
