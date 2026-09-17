# SIMBA evaluation

Every benchmark number lives here. Each entry records what was measured, on
what, and against which commit, so a later number is comparable to an earlier
one. Add entries; don't edit old ones.

## Configuration under test

| | |
|---|---|
| Model | `gemini-3.1-flash-lite` |
| Provider | OpenAI-compatible endpoint (`SIMBA_LLM_PROVIDER=openai`) |
| Base URL | `https://generativelanguage.googleapis.com/v1beta/openai/` |
| Pinned in | `.env` (`OPENAI_MODEL`), never committed |
| Replica | `replicas/registration`, three pages, 66 interactive elements on the course list |
| Viewport | 1280x800 (frozen — see CLAUDE.md) |

The model string is pinned exactly, not aliased. `gemini-flash-latest` and
friends move under you and would make two runs a week apart incomparable.

**Why this model and not a stronger one:** the free tier allows 20 requests
per day for `gemini-3.6-flash`, and one run costs 6–10. Ten runs is not
possible on that quota. The lite model has a workable allowance. Numbers
below are therefore a floor, not a ceiling — a stronger model should do
better, particularly on the wasted-navigation problem.

---

## Which script produced which table

Added 2026-09-17. Until then every script below lived in `.scratch/`, which
is gitignored, so no number in this file could be reproduced by anyone but
the person who ran it. They are now in `tools/evaluation/`. Run each from the
repo root as `python -m tools.evaluation.<name>`; each script's docstring
says what it spends (model quota, the live site) and anything that differs
from the version that produced its table.

| Entry | Table or claim | Script |
|---|---|---|
| 2026-09-05 | LLM planner, ten consecutive runs | `llm_registration_benchmark` |
| 2026-09-05 | After overlay detection: ten runs, and "Before and after" | `llm_registration_benchmark` |
| 2026-09-05 | Ablation, four conditions | `overlay_ablation` — **not the exact version**: the first row's condition had been deleted from it and is restored |
| 2026-09-06 | Perception against a second replica | `billing_perception_probe` (needs the billing replica on :5100) |
| 2026-09-06 | Hardcoded plan vs LLM, Hardcoded row | `hardcoded_registration_benchmark`; the LLM rows are the two above |
| 2026-09-06 | Token and cost, one planning call (61 + 62 tokens) | **unknown** — no surviving script matches it |
| 2026-09-07 | Screening table | `tools/screen_site.py` (already committed) |
| 2026-09-07 | The first live run, stuck after 2 of 4 steps | **not preserved** — an earlier form of `railways_hardcoded_run`, from before the plan had five steps |
| 2026-09-08 | The live flow completes, 5/5, 46.1s | `railways_hardcoded_run` |
| 2026-09-08 | What perception now sees (18 → 24 after typing) | `railways_inference_probe`; the calendar-open count is from `perception_timing_probe` |
| 2026-09-08 | Profiling `read()` | `perception_timing_probe` |
| 2026-09-09 | Run 1 and run 2 with the LLM | `railways_llm_run` |
| 2026-09-09 | The fix: a banner, not a rule; "Where information sits" | `railways_banner_probe` |
| 2026-09-09b | The run that completed on the wrong date | `railways_llm_run` |
| 2026-09-09b | Setback promoted, one call | `railways_setback_probe` |
| 2026-09-09b | Qualifiers, duplicate-label table | `railways_qualifier_probe` |
| "The DOM is not the application's state" | `"travelDate":""` while the field read `2026-10-15` | `railways_request_probe` (submits two live searches) |
| "Durable verification, justified" | The two live lapses | `railways_llm_run` (the 2026-09-09 runs) |
| 2026-09-17 | What perception reads today | `serializer_samples` |
| 2026-09-17 | The suite, and the terminal test's control | `pytest`; the control swapped `App.tsx` by hand |
| 2026-09-17 | Copy-test mutations | **not preserved** — applied by hand, listed in the entry |

Transcripts and raw results go to `logs/`, which is also gitignored. The
scripts are reproducible; the outputs they wrote on the day are not in the
repository, and the tables in this file are the record of them.

**Since 2026-09-17 every script records what it ran under.** Each prints a
conditions block when it starts — time, commit and whether the tree was dirty,
interpreter and whether it is the project venv, Playwright and Chromium
versions, provider and model, every `SIMBA_*` switch, platform, CPU count and
CPU load — and the three that write result files write it into the file beside
the results (`tools/evaluation/conditions.py`). Files written before that date
hold bare results; anything reading them must handle both shapes. Result files
from 2026-09-17 onward are `{"conditions": ..., "results": ...}`.

**Re-run on 2026-09-17 to check the move worked**, the two that need no model
and no live site:

- `billing_perception_probe`: identical to the 2026-09-06 table — 37, 39 and
  37 elements, the same role and dead-link counts, the cookie bar at 6.6%
  coverage and undetected, 37 → 38 elements on expanding the accordion.
- `hardcoded_registration_benchmark`: 10/10 completed, 3 steps, 0 model calls,
  as before. **Mean wall clock 3.01s against 5.93s** in the 2026-09-06 result
  file (median 2.8s against 5.9s). The shape reproduces and the time does not.
  *Investigated in 2026-09-17e: not the code — the original commit also runs
  at 3.0s today. The published 5.9s is corrected in its entry.*

---

## 2026-09-05 — LLM planner, ten consecutive runs

Commit `e1ed61c`. Goal: "Register for the course CS-401." No changes between
runs; a fresh browser and session each time.

| Run | Completed | Steps | LLM calls | Seconds | Wasted nav clicks |
|---|---|---|---|---|---|
| 1 | yes | 10 | 10 | 72.8 | 4 |
| 2 | yes | 7 | 7 | 55.1 | 1 |
| 3 | yes | 10 | 10 | 56.7 | 4 |
| 4 | yes | 7 | 7 | 59.3 | 1 |
| 5 | yes | 10 | 10 | 77.1 | 4 |
| 6 | yes | 10 | 10 | 63.1 | 4 |
| 7 | yes | 6 | 6 | 50.2 | 0 |
| 8 | yes | 10 | 10 | 72.2 | 4 |
| 9 | yes | 7 | 7 | 54.1 | 1 |
| 10 | yes | 6 | 6 | 52.0 | 0 |

**Success rate: 10/10.** Steps 6–10 (median 10). Wall clock 50.2–77.1s, mean
61.3s. LLM calls equalled steps in every run, so no answer was ever malformed
or named an id that wasn't on the page — the JSON schema and the id validation
both held.

### How much the path varies

Three distinct paths, all ending identically:

| Runs | Steps | Path |
|---|---|---|
| 5 | 10 | Registrar → Academics → Registrar → Add/Drop Form → *login* → Register → **Close** → Register |
| 3 | 7 | Registrar → *login* → Register → **Close** → Register |
| 2 | 6 | *login* → Register → **Close** → Register |

The variance is entirely in the **prefix**: 0, 1, or 4 wasted navigation
clicks before the model settles on the login form. Every one of those clicks
is on an `href="#"` nav link that goes nowhere, so verification catches it and
the planner moves on. Cost, not correctness.

The middle — fill username, fill password, click Sign In — was identical in
all ten runs. It is the stable part.

### The unstable steps

**1. Choosing where to start (varies, costs steps).** In 8 of 10 runs the
model clicked at least one dead nav link before looking at the login form
directly in front of it. This is what makes a run 6 steps or 10.

**2. The modal (fails every single time).** In 10 of 10 runs the model tried
to click "Register for CS-401" while the modal was still covering the page,
the click timed out, and only then did it click "Close" and retry. The
recovery works, so the run completes — but it is a guaranteed wasted step and
~30s of timeout in every run, and the success rate flatters it.

The system prompt already says to dismiss overlays first, and the model
ignores it. The likely cause is a perception gap rather than a reasoning one:
the serialized page lists `1. button 'Close'` among 66 elements with nothing
marking it as belonging to a blocking overlay. The replica's modal is a plain
`div` with no `role="dialog"` or `aria-modal`, so the accessibility tree does
not flag it either, and neither does perception.

Worth trying next, cheapest first: surface modality in the serializer, so a
covering overlay is visible to the planner as such rather than as one more
button in a list.

### Method

`.scratch/benchmark.py`, 5s between runs to stay under the rate limit. Full
prompt-and-response transcripts in `logs/bench-run*.jsonl` (gitignored).
Credentials checked absent from every transcript.

### Not measured yet

- The hardcoded planner over the same ten runs, as an A/B baseline.
- Any model other than the one above.
- Cost per run.

---

## 2026-09-05 — after overlay detection and dead-link flagging

Commit `25324d3`. Same model, same replica, same goal, same harness. The only
changes are in perception and the prompt: overlays are detected structurally
and marked, elements behind them are marked occluded, links that go nowhere
are marked dead, and the prompt tells the model to act on all three.

| Run | Completed | Steps | LLM calls | Seconds |
|---|---|---|---|---|
| 1 | yes | 5 | 5 | 11.8 |
| 2 | yes | 5 | 5 | 25.7 |
| 3 | yes | 5 | 5 | 18.8 |
| 4 | yes | 5 | 5 | 25.3 |
| 5 | yes | 5 | 5 | 19.4 |
| 6 | yes | 5 | 5 | 13.4 |
| 7 | yes | 5 | 5 | 14.3 |
| 8 | yes | 5 | 5 | 13.5 |
| 9 | yes | 5 | 5 | 14.2 |
| 10 | yes | 5 | 5 | 15.0 |

**Every run took the same five steps:**

    fill username → fill password → Sign In → Close → Register for CS-401

### Before and after

| | Before (`e1ed61c`) | After (`25324d3`) |
|---|---|---|
| Success rate | 10/10 | 10/10 |
| Steps | 6–10 (median 10) | **5, every run** |
| Distinct paths | 3 | **1** |
| Wasted nav clicks | 0–4, in 8 of 10 runs | **0** |
| Runs that clicked Register before dismissing the modal | **10 of 10** | **0** |
| Wall clock | 50.2–77.1s, mean 61.3 | **11.8–25.7s, mean 17.1** |
| LLM calls | 6–10 | **5** |

**The modal timeout is gone.** No run attempted Register while the modal was
up, so no run ate the ~30s click timeout and no run needed the recovery path.
That single change accounts for most of the 3.6x speedup; removing the dead
nav clicks accounts for the rest and for the step count collapsing to a
constant.

Five steps is the floor for this task — two fields, three clicks — so the
planner is now optimal on this replica, and the run-to-run variance in the
path is zero. The remaining spread in wall clock (11.8–25.7s) is API latency,
not planning.

Worth being clear about what this does and does not show: the model did not
get better at reasoning. Perception started telling it something true that it
previously had no way to know, and the prompt told it what to do with that.
The earlier 10/10 success rate was hiding a wasted step in every single run.

---

## 2026-09-05 — ablation: does overlay detection still help on a stronger model?

Commit `9b19206`. Four conditions on the registration replica, same goal.
The ablated variable is **overlay detection only** — `SIMBA_OVERLAY_DETECTION`
turns off the DOMSnapshot pass and the `overlay`/`occluded` flags. Dead-link
flagging stays on in both arms, so this measures overlay detection rather
than perception as a whole.

| Condition | Model | Runs | Completed | Steps | LLM calls | Seconds (mean) | Paths |
|---|---|---|---|---|---|---|---|
| overlay ON | `gemini-3.1-flash-lite` | 10 | 10/10 | 5 | 5 | 19.1 | 1 |
| overlay OFF | `gemini-3.1-flash-lite` | 10 | 10/10 | 4 | 4 | 44.5 | 1 |
| overlay ON | `gemini-3.8-flash` | **1** | **0/1** | — | — | — | — |
| overlay OFF | `gemini-3.8-flash` | **1** | **0/1** | — | — | — | — |

Wall clock excludes time spent waiting out rate limits, which is tracked
separately.

### The demo-model arm did not run

**One run was attempted per demo condition, and neither completed.** Both
were stopped by the free tier, in two stages: first
`GenerateRequestsPerMinutePerProjectPerModel-FreeTier` at **5 requests per
minute**, which the provider's backoff absorbed at a cost of 400–450 seconds
of waiting per run, and then
`GenerateRequestsPerDayPerProjectPerModel-FreeTier` at **20 requests per
day**, which nothing can absorb. A single run needs 4–5 requests, so the
daily allowance is roughly four runs, and the earlier per-minute waiting had
already consumed it.

**So the question this ablation was built to answer is unanswered.** Whether
a stronger model absorbs the gain is not known, and nothing below should be
read as evidence either way. It needs a key without a free-tier cap; the
comparison is cheap to run once one exists.

### What the two complete conditions show

The surprise is that turning detection **off makes the step count go down and
the time go up**, and that the run still passes:

- **Overlay OFF never dismisses the modal at all.** All ten runs went
  straight from Sign In to Register, with no Close. They still completed —
  because the shared retry's second strategy is a JS click, which bypasses
  hit-testing and punches *through* the overlay.
- **That costs ~25s per run.** Mean wall clock is 44.5s against 19.1s, and
  the gap is about one Playwright click timeout: strategy 0 waits out the
  full timeout on an intercepted click before strategy 1 succeeds.
- **Fewer steps is worse here, not better.** Four steps beats five only if
  you count steps. The four-step path works by interacting with a page the
  user cannot see, past a dialog they were meant to read — which for this
  project is the wrong behaviour regardless of the timing, and something
  SIMBA should never do on a real site.

Both conditions were perfectly consistent: one path each, zero variance
across ten runs, identical step and call counts.

### Read this carefully

The JS-click fallback is doing something here that it was not designed for.
It exists to recover from a click that silently fails; it turns out to also
paper over a missing perception signal, and it does so *successfully enough
to look like a pass*. Without overlay detection the system would ship a
100% success rate on this task while routinely clicking through modals.

Worth revisiting: whether strategy 1 should refuse to click an element that
perception knows is occluded, so that clicking through a modal becomes a
failure rather than a silent recovery.

---

## 2026-09-06 — perception against a second replica

Commit `66b61e9`. The billing replica exists to test whether perception
generalises or has been fitted to the registration page. Serializer run
against all three pages, no changes made to the replica to suit it.

| Page | Interactive elements | link | button | textbox | dead links | overlay | occluded |
|---|---|---|---|---|---|---|---|
| Bill enquiry | 37 | 31 | 5 | 1 | 29 | 0 | 0 |
| Enquiry result | 39 | 36 | 3 | 0 | 32 | 0 | 0 |
| Bill detail | 37 | 34 | 3 | 0 | 31 | 0 | 0 |

**What worked.** Accessible names resolve correctly throughout, including the
reference-number input, whose name comes from its `<label for>`. Dead-link
detection generalises unchanged — 29 to 32 of ~37 elements per page are
placeholder `href="#"` nav, correctly flagged. Every element has a usable
accessible name; none came back nameless.

**Accordion content is correctly absent before expansion.** Collapsed panels
are `display:none`, the accessibility tree ignores them, and the serializer
reports 37 elements on the enquiry page. Expanding the first accordion takes
it to 38 and the previously hidden "Read the full enquiry guide" link
appears. This is right — it matches what a user can actually reach — but see
the second gap below.

### Three gaps, none of them fixed

**1. The cookie banner is not detected, and it really does block things.**
The banner is `position: fixed`, `z-index: 9999`, 1280x53 at the bottom of
the viewport — **6.6% coverage**, against `MIN_COVERAGE = 0.30`. So the
structural rule ignores it.

That is not a harmless miss. Scrolled to the bottom of the enquiry result,
six real footer links — Disclaimer, Privacy, Sitemap, Accessibility,
Feedback, Archive — sit underneath the banner and are reported with
`occluded: false`. A click on any of them would be intercepted exactly the
way the registration modal intercepted Register, and nothing would warn the
planner first.

The coverage threshold encodes an assumption that a blocker is modal-shaped.
A strip that covers a tenth of the screen blocks a tenth of the screen, and
the right test is whether it covers *the element in question*, not whether it
covers most of the page. The occlusion test already works per element; only
the gate deciding what counts as a blocker at all is wrong.

**2. Perception discards the accordion's expanded state, which the
accessibility tree already knows.** The AX node for the accordion control
carries `('expanded', False)` — the tree reports it, and `build_elements`
drops it on the floor. A planner therefore sees `button 'Tariff and
adjustment details for this bill'` with nothing to say it is collapsed, no
way to know content is behind it, and no way to tell an expanded accordion
from a collapsed one after acting. This is information already in hand,
being thrown away.

**3. The value the task is about is invisible to perception.** The goal of
this flow is to find the amount due. That amount — `14,382` — is text in a
table cell. The serializer emits only *interactive* elements, so it does not
appear in the output at all: `'14,382' in element labels → False`, while
`'14,382' in page body → True`.

This is the deepest of the three. Every read-only value a user might be
looking for is currently outside what SIMBA can perceive, which means the
overlay's `step.presented` can describe what to click but cannot state what
the answer is. The registration flow hid this because its goal was
*completing an action*; a lookup flow's goal is *reading a value*, and that
is a different shape of task the perception layer does not yet serve.

**Also noted:** two distinct links share the label "Bill Enquiry" (the ribbon
nav and the breadcrumb). `resolve` disambiguates them by ordinal, so
execution is correct, but a planner choosing between them by label alone
cannot tell which is which.

---

## 2026-09-06 — hardcoded plan vs LLM, registration replica

Commit `3968838`. Ten runs of the hardcoded planner, against the LLM numbers
already recorded above. Same replica, same goal, same shared loop — the only
difference is which planner picks the next move.

| Planner | Runs | Completed | Steps | LLM calls | Seconds (mean) | Paths |
|---|---|---|---|---|---|---|
| Hardcoded | 10 | 10/10 | 3 | 0 | **5.9** | 1 |
| LLM, overlay ON | 10 | 10/10 | 5 | 5 | 19.1 | 1 |
| LLM, overlay OFF | 10 | 10/10 | 4 | 4 | 44.5 | 1 |

> **Corrected 2026-09-17: the Hardcoded row's 5.9s does not reproduce.**
> Re-run on 2026-09-17 it is **3.0s** — with today's code (3.01s mean), and
> with this entry's own commit `3968838` checked out and run the same way
> (3.0s, 10/10). So no code change since explains it. Nor does a package
> change: Playwright, greenlet and Flask in `backend/venv` were installed on
> 2026-09-04 and not touched since. What made the original runs twice as
> slow is **not established** — see 2026-09-17e for what was ruled out and
> what was not.
>
> What this changes below: "3.2x faster" and "about 13 seconds" for five
> model round trips were both computed from 5.9s. From 3.0s they would read
> 6.4x and about 16s. **Neither pair should be quoted**: the LLM's 19.1s is
> itself a 2026-09-05 measurement under conditions nobody recorded, has not
> been re-run, and the planning-cost estimate is only sound when both arms run
> in one session on one machine. The argument of the entry — the hardcoded
> plan is a ceiling, not a baseline — does not depend on the ratio.

The hardcoded plan is **3.2x faster** than the best LLM configuration, uses
no model at all, and is perfectly deterministic. It takes 3 steps to the
LLM's 5 because a plan step can carry several operations — its login step
fills both fields and clicks Sign In as one unit — where the LLM emits one
action at a time.

### Token and cost, per run

Measured with the instrumentation added in the same commit.

| Condition | Model | Calls | Prompt tokens | Completion tokens | Total | Cost |
|---|---|---|---|---|---|---|
| Hardcoded | — | 0 | 0 | 0 | 0 | $0.000000 |
| LLM, one planning call (measured) | `gemini-3.1-flash-lite` | 1 | 61 | 62 | 123 | $0.000031 |

A five-call run on this replica costs a small fraction of a cent at
flash-lite rates. Cost is not currently a reason to prefer either planner;
latency is.

### So what does the LLM buy?

On this task, measured: **nothing.** It is slower, costs money, and reaches
the same place. Anyone comparing the two columns above and concluding the
LLM is not worth it would be reading the table correctly.

What the table cannot show is the thing the LLM is actually for. The
hardcoded plan names `Register for CS-401` because a person wrote that
string. It reaches the confirmation page on this replica, for this course,
and would need a person to write it again for a different course, a
different portal, or a page whose Close button is labelled Dismiss. Every
number in its column is a measurement of a plan that already knows the
answer.

The honest framing for the report: the hardcoded planner is the **ceiling**,
not the baseline. It is what perfect planning would score, and it exists to
show how much of the LLM's cost is planning overhead rather than execution.
The LLM's 19.1s against 5.9s says five model round trips cost about 13
seconds; it does not say the LLM is 3.2x worse at the task.

The comparison that would actually settle it — both planners against a goal
neither has seen, on the billing replica or a third site — has not been run.
The billing hardcoded plan exists now, so the LLM half of that is one
quota-permitting run away.

---

## 2026-09-07 - a live site: Pakistan Railways train search

Flow in `backend/orchestrator/railways_plan.py`. Read-only throughout: fill
origin, destination and date, submit the search, read the results. Nothing
booked, no login, no registration. One full loop run and about five page
loads in total, spaced out - this is someone's public service.

### Screening, before building anything

`tools/screen_site.py`, which fetches robots.txt, loads each page and
serializes it without ever filling or clicking.

| page | robots | status | load | elements | named | unnamed | generated | dead links | overlay/occluded |
|---|---|---|---|---|---|---|---|---|---|
| `pakrail.gov.pk/` | no robots.txt (404) | 200 | 5421ms | 100 | 76 | 24 | 0 | 20 | 0/0 |
| `pakrailways.gov.pk/train` | no robots.txt (HTML returned) | 200 | 2625ms | 18 | 14 | 4 | 0 | 3 | 0/0 |

**The requested site does not have the requested feature.**
`pakrail.gov.pk` is Pakistan Railways' informational site: ASP.NET `.aspx`
pages, 100 interactive elements on the homepage, 98 of them links, and **no
train search form anywhere on it**. Its own "Train Timings" link points at a
different domain. The public search lives at `pakrailways.gov.pk/train` and
is a **Vue single-page app** called RABTA - so the ASP.NET page the brief
expected to test perception against is not the page the search is on.

Neither domain serves a robots.txt: one 404s, the other returns its SPA's
`index.html` for every path including that one. Nothing is disallowed, so a
read-only search is fair game - but HTTP 200 was not enough to conclude that,
and the screener now says so rather than parsing HTML as rules.

### What perception sees on the real search page

18 elements: 12 links, 3 buttons, 3 textboxes.

| | count | note |
|---|---|---|
| Usefully named | 14 | From, To, Departure Date, Log in, Train Timings ... |
| Empty accessible name | 4 | three links and **the search button** |
| ASP.NET-style generated names | 0 | none - it is a SPA, not WebForms |
| Overlays detected | 0 | correct; there is no modal or cookie banner |

**No `ctl00$...` names at all.** The generated-name problem the brief
anticipated did not appear, because the search is not a WebForms page. What
appeared instead is worse.

### The blocking finding: the dropdown does not exist

Typing `LAH` into **From** opens a list of six stations - DERA ALLAHYAR,
LAHORE JN., LAHORE CANTT, TANDO ALLAH YAR, KILLAABDULLAH, KOT NAJIBULLAH.
They are plainly on screen.

**The serializer sees none of them.** Element count before typing: 18. After
typing: 18.

The reason, from the DOM and the accessibility tree:

    <li class="el-select-dropdown__item"><span>LAHORE CANTT</span></li>
        role: none   tabindex: none   aria-label: none
    AX: role StaticText (not ignored), plus InlineTextBox.
        No option. No menuitem.

Element UI renders its options as plain `li`/`span` with no ARIA and nothing
focusable. They reach the accessibility tree only as text. `INTERACTIVE_ROLES`
has no entry that can match them, so perception reports an empty dropdown on
a page showing six choices.

This is not exotic. Element UI and its successors sit behind a very large
number of enterprise and government single-page apps.

### What the loop did

    step 1/4  Choose where you are travelling from.   verified, moved on
    step 2/4  Choose where you are travelling to.     failed
    help.requested - fill on 'To' failed: Locator.clear: Timeout 30000ms

Final state: **both fields empty**, page showing "Please enter search
criteria". 124s.

> **Corrected 2026-09-08.** The account first written here was wrong in
> both of its parts, and the correction is more interesting than the error.
> It is kept visible rather than quietly rewritten, because how the wrong
> reading survived is itself the finding: the run's output was consistent
> with it, and nothing was measured that would have contradicted it.

**What was written here first.** That step 1 filled the From field, verified
it by reading it back, and had the value evaporate on blur; and that step 2
timed out because the dropdown step 1 opened was covering the To input.

**What actually happened**, established by reproducing it directly:

1. **Step 1 never filled anything.** Both station inputs are `readonly` on
   load - Element UI removes the attribute in its own click handler.
   Playwright's `fill` waits for an element to be *editable*, which never
   becomes true, so it timed out on a field nothing was blocking. No value
   was ever typed, so `verify_typed` never ran and nothing was verified. The
   step failed.
2. **Nothing was covering the To input.** Measured: the From dropdown opens
   at x 312-527, the To field sits at x 548-765. They do not overlap. Step 2
   failed for the same reason step 1 did - `readonly` - and `Locator.clear`
   is simply where the retry strategy happened to hit it.

**Why step 1 looked like it had succeeded.** It did not; the loop did not
say so. A first failed step increments `consecutive_setbacks`, records a
setback for the planner, and `continue`s - with no message to the frontend
at all. `HardcodedPlanner` ignores setbacks, so it served step 2, and the
user saw `step 1` then `step 2` exactly as if the first had worked. The
observable trace of a silently skipped step is identical to a successful
one. **That is a defect in its own right and it is still open** - see
STATUS.md.

The original reading was reached by inference from a plausible mechanism
(Element UI really does clear on blur) rather than from evidence. The
evidence needed was two lines: the `readonly` attribute, and two rectangles.

### Two things the flow could not even express

- **The search button has no name.** `Target("button", "")` is the honest
  description of what perception offers, and it matches every unnamed button
  on the page. `resolve` would disambiguate by ordinal, which is
  order-dependent and would break silently on a layout change.
- **There is no success condition.** Results are a table of static text in a
  SPA: the URL does not change, the title does not change, and no row is
  interactive. A `Snapshot` is url, title and interactive labels, so there is
  nothing to assert against. `RAILWAYS_TASK.success` is `None`, and the run
  ends when the plan runs out rather than when the goal is met.
  *(Fixed 2026-09-08: content extraction, and `Expectation.rows_at_least`.)*

### The gap between the replicas and a real site

The replicas were built to be cluttered, and they are - 66 elements, a modal,
a cookie banner, twenty dead nav links. What they were not built to be is
*semantically poor*, and that turns out to be the difference that matters.

| | replicas | live site |
|---|---|---|
| Every control has an accessible name | yes | 4 of 18 do not, including the submit |
| Choices are real controls | button, a, input | li/span with no role |
| A filled field stays filled | yes | only if a dropdown item was selected |
| Blocking chrome is detectable | full-viewport modal | 220x180 dropdown, under threshold |
| Success is observable | URL and title change | neither changes; results are static text |

Every replica was written by someone who knew what perception reads. A real
page is written by someone who has never heard of it, and the assumptions
that went unexamined for three weeks - that a choice is a control, that a
filled field stays filled, that finishing changes the URL - are all false
here at once.

The honest summary: **the walking skeleton works on pages built the way we
build them, and does not yet work on a page we did not write.** Nothing in
the loop is wrong. The gap is entirely in what perception can see.

---

## 2026-09-08 - the live flow completes

Second pass at the railways flow, after five changes to perception and the
loop. Same site, same read-only scope, same hardcoded plan, no LLM.

### The run

    step 1/5  Choose where you are travelling from.        ok
    step 2/5  Choose where you are travelling to.          ok
    step 3/5  Open the calendar and go to the right month. ok
    step 4/5  Pick the day you want to travel.             ok
    step 5/5  Search for trains.                           ok
    task.completed - 5 steps, 46.1s, 0 model calls

Final form state, read from the page: `From = 'LAHORE CANTT'`,
`To = 'KARACHI CANTT'`, `Departure Date = '15-10-2026'`. One search request,
fully populated:

    {"boardStationCode":"LRC","arrivalStationCode":"KCT","travelDate":"2026-10-15"}

And the results, read back through the content channel:

| Train No. | From/To | Time | Duration |
|---|---|---|---|
| 2DN | LAHORE CANTT KARACHI CANTT | 08:04 06:20 | 22 h 16 min |

| | first run (2026-09-07) | this run |
|---|---|---|
| Steps reached | 2 of 4 | **5 of 5** |
| Outcome | `help.requested` | `task.completed` |
| Wall clock | 124s | **46s** |
| Fields set at the end | none | all three |
| Search request | never sent | sent, fully populated |
| Results read | none possible | 1 row, headed |
| Model calls | 0 | 0 |

### What perception now sees that it could not

Measured on the live page, same viewport, same user agent:

| | before | after |
|---|---|---|
| Elements, search page idle | 18 | 18 |
| Elements, after typing `LAH` | 18 | **24** |
| Station options | 0 | **6** |
| Elements, calendar open | 18 | **66** |
| Day cells addressable | 0 | **42** |
| Content: tables / rows after a search | - | 2 / 2 |
| Form values visible to the loop | no | yes |

The six stations are `li.el-select-dropdown__item` with no role, no
tabindex and no aria, reaching the accessibility tree as `StaticText`. The
day cells are `td`s with the same nothing. Both are found by computed
`cursor: pointer` and nothing else. **The page was not modified.**

Cost of looking: one `DOMSnapshot.captureSnapshot` that was already being
fetched. Profiled on the live page - 2,374 DOM nodes idle, 2,690 with the
calendar open:

| | idle | calendar open |
|---|---|---|
| Whole `read()` | 0.19s | 0.22s |
| of which captureSnapshot | 0.03s | 0.05s |
| of which inference | 0.02s | 0.02s |
| of which content extraction | 0.02s | 0.02s |

### The wrong turn on the way, and what it cost

The plan reached all five steps two runs before it completed, and took
**3,704 seconds** - sixty-two minutes - to fail. Two causes, both worth
recording:

1. **A role that moved.** Inferred roles were partly decided by how many
   same-class siblings an element had. Element UI gives calendar cells
   classes like `available`, `prev-month available`, `today available`, so
   the size of a cell's class-group depends on where in the month it falls:
   the 15th came out `option` in one month and `button` in another, from
   identical markup. The plan named `button`, found nothing, and every step
   after it thrashed. Roles are now decided by position alone - inside a
   floating panel, everything is an `option`.
2. **Thirty-second timeouts.** Playwright's default. With two strategies per
   step and several operations per strategy, a plan that cannot find its
   target spends minutes doing nothing before anyone is told. `act` now caps
   an action at 10s. The same failing plan would now cost roughly a fifth as
   long, and a step a person is watching cannot hang for half a minute.

A third, smaller one: with `rows_at_least=1` as the success condition, the
run **reported success after three steps**. The open date picker is a
well-formed `<table>` with `Sun`..`Sat` headers and six rows of days, so
"the page has at least one row of results" was satisfied by opening a
calendar. Content extraction now skips floating panels - a date picker is a
control, not something the page says.

### Still open after this

- **The DOM is not the application's state.** Case 4 below, in full. The date
  is the instance we found; there is no reason to think it is the only one.
- **An unnamed submit button is addressed by ordinal.** It worked here only
  because the page happens to have exactly one unnamed button.
- **A single failed step is invisible to the user.** Unchanged, and it is how
  the first run's diagnosis went wrong.
- **A modal's content is skipped along with the date picker's**, because both
  are floating panels and nothing yet tells them apart.

---

## 2026-09-09 - the model meets an element the page never declared

First LLM run on a live site, and the first time a model has been shown
elements whose role perception guessed at. `gemini-3.1-flash-lite`, same
railways flow, same read-only scope. Two runs and one single-call probe: nine
requests against a 20-a-day quota.

### Run 1 - the model was told, and did it anyway

    step 1/5  Fill in From.    "entering the departure station into the 'From' field"
    step 2/5  Fill in To.      "enter the destination station to proceed"
    help.requested - 'From' no longer holds what I put in it, it held
                     'LAHORE CANTT' and now holds ''

Two model calls, 48.9s. What makes this worth recording is that the model
**was shown the option and the rule, and chose neither.** Its second prompt
ended:

    19. option 'LAHORE CANTT'  <- INFERRED (role worked out from layout, not declared)

and the system prompt carried, among nine rules:

    - A dropdown option only counts as chosen when you click it. Typing text
      into the field above it is not choosing; many pages will discard what
      you typed. If you have typed into a field and INFERRED options have
      appeared, click the one you want before doing anything else.

It answered:

    {"action": "type", "element_id": 11, "value": "KARACHI CANTT",
     "reasoning": "I will now enter the destination station to proceed with
                   your train search."}

From where the model sits this is reasonable: it typed `LAHORE CANTT` into
From, the history line says `1. Fill in From.`, and the field is done. The
page disagrees, and says so only by silently emptying the field once focus
moves. That is the same mistake a person makes on this site.

**Durable verification caught it**, and this is the first time it has fired on
something real rather than on a blur handler attached in a test. The withdrawn
case 4 described exactly this behaviour on the wrong evidence; here it is on
the right evidence, from the live page, ending the run instead of submitting
an empty search.

### The fix: a banner, not a rule

The failure is one this module had already solved once. `render_page` does not
list a modal's buttons and hope the model notices — it prints a banner above
the list, because a rule among nine is not read at the moment it matters. The
same move now applies to open choices:

    A LIST OF CHOICES IS OPEN, with N option(s) marked INFERRED below. Nothing
    is chosen yet. Typing the text is not choosing: click the option you want
    NOW, before touching any other field, or what you typed will be discarded.

Re-asking the one decision that failed, same page state, one model call:

    {"action": "click", "element_id": 19, "value": null,
     "reasoning": "Clicking the inferred 'LAHORE CANTT' option confirms your
                   origin selection."}

### Run 2 - with the banner

    step 1/5  Fill in From.
    step 2/5  Click LAHORE CANTT.          <- inferred option
    step 3/5  Fill in To.
    step 4/5  Click KARACHI CANTT.         <- inferred option
    step 5/5  Fill in Departure Date.
    step 6/6  Click 15.                    <- inferred calendar cell
    help.requested - 'Departure Date' no longer holds what I put in it, it
                     held '2026-10-15' and now holds '15-09-2026'

Six model calls, 73.4s, 4,808 tokens, $0.00058. Final state: `From = 'LAHORE
CANTT'`, `To = 'KARACHI CANTT'`, both committed correctly.

**Both questions answered.** The model picks a station from the inferred
options, by exact name, twice. And it understands the marking: asked again at
the decision it had failed, it wrote *"clicking the inferred 'LAHORE CANTT'
option"* - it read the flag, used the word, and treated the element as a real
control rather than as something suspect. Nothing about `inferred` needed
explaining beyond one sentence.

### The step it got wrong

Call 6. The goal says **2026-10-15**. The listing it was given:

    A LIST OF CHOICES IS OPEN, with 42 option(s) marked INFERRED below. ...
    22. button 'September'
    24. button 'Next Month' [input type=button]
    25. option '30'   <- INFERRED
    26. option '31'   <- INFERRED
    27. option '1'    <- INFERRED
    ...
    41. option '15'   <- INFERRED
    ...
    56. option '30'   <- INFERRED
    57. option '1'    <- INFERRED
    ...

Its answer:

    {"action": "click", "element_id": 41, "value": null,
     "reasoning": "I am selecting the 15th of the month from the date picker
                   to finalize the departure date."}

Element 41 is the 15th **of September**. The picker opens on the current
month; the goal is next month; `24. button 'Next Month'` was right there and
the model did not press it. The field became `15-09-2026`, durable
verification saw the value it had typed replaced by a different one, and the
run stopped rather than searching for the wrong date.

Two separate faults, and only one of them is the model's:

1. **The model did not reason about the month.** It had `button 'September'`
   in the list and a goal naming October. This is a planning failure and a
   fair one to attribute to a lite model.
2. **Perception gave it no way to be right even if it had.** Look at the
   list: `option '30'` appears at 25 *and* 56. `option '1'` at 27 *and* 57.
   The calendar's trailing days from August and leading days from October are
   emitted identically to September's own. Element UI marks them
   `prev-month` and `next-month` in the class attribute and
   `interactivity.py` discards it. A day cell's label is a bare number with
   no month attached, so **"the 15th of October" is not expressible in what a
   planner is given**. Here 15 happened to be unique and the model still had
   to infer the month from a separate button. This is perception's fault, not
   the model's, and it is now an open item.

### What this says about inferred elements generally

| Question | Answer |
|---|---|
| Do inferred elements reach the model? | Yes, numbered like any other |
| Can it choose one? | Yes - two stations and a calendar day, unprompted after the banner |
| Does it understand the role is a guess? | Yes, and says so in its reasoning |
| Does the marking make it hesitant? | No. It clicked without hedging |
| Is a rule in the prompt list enough? | **No.** A banner is |
| Are the labels sufficient to choose correctly? | **Not for a calendar.** 42 options, 12 of them duplicate numbers |

The headline is the last two rows. Perception now surfaces the controls, and
a small model can drive them - but only when told at the moment of the
decision rather than in a list of standing rules, and only when the labels
carry enough to tell one option from another. A dropdown of station names
satisfies that. A month of numbered days does not.

---

## 2026-09-09b - a qualifier, one more chance, and a worse outcome

Three changes since the run above: inferred elements carry a qualifier, a
durability lapse is handed to the planner once before the run ends, and the
railways date is computed from today. One LLM run, seven calls. Quota after
it: about three requests left of twenty, which is not enough for another run,
so nothing further was attempted.

### The run

    step 1/5  Fill in From.
    step 2/5  Click LAHORE CANTT.              <- inferred option
    step 3/5  Fill in To.
    step 4/5  Click KARACHI CANTT.             <- inferred option
    step 5/5  Fill in Departure Date.
    step 6/6  Click 15.                        <- inferred, September's
    STEP FAILED 6: 'Departure Date' no longer holds what I put in it — it
                   held '2026-10-15' and now holds '15-09-2026'
    step 7/7  Click element 13.                <- the search button
    task.completed - 7 steps, 66.9s, 7 calls, $0.00066

    {"boardStationCode":"LRC","arrivalStationCode":"KCT","travelDate":"2026-09-15"}

| Train No. | From/To | Time | Duration |
|---|---|---|---|
| 2DN | LAHORE CANTT KARACHI CANTT | 08:04 06:20 | 22 h 16 min |
| 14DN | LAHORE CANTT KARACHI CANTT | 19:09 19:25 | 24 h 16 min |

**It did not reach a correct October date, and it reported success anyway.**
The goal says `2026-10-15`. The search went out for `2026-09-15`, returned two
real trains, satisfied `rows_at_least=1`, and the run ended `task.completed`.

That is worse than the run before it, and the change that made it worse is the
one asked for. Previously a lapse ended the run: no search was sent, and the
user was told the system was stuck. Now the run continues, and a person is
handed a timetable for a date they did not ask for, labelled as done. **A
plausible, well-formed, wrong answer is the worst thing this system can
produce**, and this is the first time it has produced one.

Three separate failures line up to allow it, and they are worth separating
because they have different fixes.

### 1. The setback reached the model and the model ignored it

The mechanism worked. The lapse was caught, `step.failed` was emitted, the
record was dropped, and the setback was passed to the planner. Call 7's prompt
ended:

    Your previous answer was rejected. Do not repeat it.
    Problem: 'Departure Date' no longer holds what I put in it — it held
    '2026-10-15' and now holds '15-09-2026'. Typing a value is not always
    choosing it — a list or a calendar may need the choice committed by
    clicking the option itself. Put it back, and commit it this time.

It answered:

    {"action": "click", "element_id": 13,
     "reasoning": "Click the button to confirm your search selection after
                   setting the route and date."}

Eighteen element lines sat between the instruction and the end of the prompt.
This is the prompt-prominence finding for a third time, in a channel where it
had not been applied: the setback was appended *after* the page. Moved above
the element list and stated in the imperative, the same decision, same page
state, one call:

    {"action": "type", "element_id": 12,
     "reasoning": "I am re-entering the correct date into the field to ensure
                   it is processed accurately this time."}

**Attention, not competence.** It now engages with the date instead of moving
on — and it chooses to *re-type* it, which is exactly what this widget
discards, having just been told so in the sentence it was responding to.
Prominence buys the model's attention; it does not supply the knowledge that
this particular calendar has to be navigated. The end-to-end effect of the
promotion is **unverified**: it needs a full run and the quota is spent.

### 2. Qualifiers work, and nothing used them

The qualifier change did what it was built to do. On the live calendar every
duplicate number is now separated:

| label | cells | qualifiers |
|---|---|---|
| `30` | 2 | `previous month`, `` |
| `1`–`10` | 2 each | ``, `next month` |
| `9` (September) | — | `today` |

`pick(Target("option", "15", qualifier=""))` resolves to exactly one cell and
clicking it sets `15-10-2026`. "The 15th of October" is expressible now, and
the hardcoded plan says it.

The model was shown the qualifiers — `option '15'`, `option '30' (previous
month)` — and still clicked the 15th of September. It never pressed
`Next Month`, which was in the list as a named button. The qualifier tells you
*which* cell is which within a grid; it does not tell you the grid is showing
the wrong month, and `button 'October'` versus `button 'September'` is a
comparison the model did not make either time. **The missing input was
necessary and not sufficient.**

### 3. The success condition cannot see the thing that went wrong

`RAILWAYS_TASK.success` is `rows_at_least=1`. Two trains came back, so the
task was satisfied. It would have been satisfied by a search for any date.

The goal names a date and no available check reads it. The results table has
`Train No.`, `From/To`, `Time` and `Duration` — no date column — so
`content_says` cannot test it either. The only place the requested date
appears is the *input field*, and `Expectation` has no vocabulary for a form
value even though `Snapshot` has carried them since 2026-09-08.

This is the cheapest of the three to fix and the one that would have caught
it: a task whose goal names a value should be able to require that the form
still holds it at the end. **Not implemented** — it is a change to the
`Expectation` vocabulary and there is no quota left to test it against the
case that motivated it.

### What the three changes are actually worth

| Change | Did it do what it was for? | Did it help this run? |
|---|---|---|
| Qualifiers on inferred elements | Yes — every duplicate separated, October expressible, live-tested | No. The model did not use them |
| One chance before giving up | Yes — setback delivered, planner re-planned | **No. It turned a safe stop into an unsafe success** |
| Date computed from today | Yes — no longer expires | Neutral |

The middle row is the one to sit with. Handing a failure back to a planner is
right when the planner can act on it, and the evidence that this one can is
now weaker than it looked: given a clear, well-placed correction it re-tried
the approach that had already failed. Until the LLM path can demonstrably
recover from a lapse, the safety of the old behaviour — stop, and say so — is
worth more than the flexibility that replaced it.

**Settled the same day.** The one-chance change was reverted: a lapse ends the
run again. Two of the three holes it depended on are now closed —
`Expectation.value_is` means the railways task can no longer pass on a wrong
date, and a floating panel now states which month it is showing rather than
leaving it in an unremarkable button. The third, whether the model acts on a
promoted setback across a whole run, is unmeasured and needs quota. See
case 6, and DECISIONS.md.

---

## Durable verification, justified

Added 2026-09-08 on the strength of a mechanism that was real but had not
actually been observed — the withdrawn case 4 described a field clearing
itself on blur, which Element UI genuinely does, in a run where it had not
happened. It was carried for a day as a check with a test behind it and no
incident behind it.

It has now fired twice on the live site, both times with the LLM driving, and
both times stopping was correct.

| | what was typed | what the field held at the next look | why |
|---|---|---|---|
| Run 1, 2026-09-09 | `LAHORE CANTT` in **From** | `''` | Element UI clears a filterable select on blur unless an option was committed. The model typed the name and moved to the next field without clicking the option. |
| Run 2, 2026-09-09 | `2026-10-15` in **Departure Date** | `15-09-2026` | The model clicked the 15th of the month the picker opened on. The date was set, to the wrong month. |

Neither is a case any other check here can see:

- **Read-back** passed both times. The keystrokes arrived; the value was
  genuinely in the field at the moment it was checked.
- **The page-level `Expectation`** passed both times. The URL, the title and
  the labels were all exactly as a working step leaves them.
- **`step.failed`** would not have fired: the steps' own actions succeeded.
- **The trust panel** would have shown a screenshot with the value in place.

What each stopped is worth being concrete about. Run 1 would have gone on to
submit a search with an empty origin. Run 2 would have submitted a search for
**the wrong date** and returned a timetable — a plausible, well-formed,
wrong answer, which is the worst outcome this system can produce and the only
one a user has no way to catch. The search request in run 2 was never sent.

Two further things this establishes:

- **The failure mode is not exotic.** Two instances in two runs on one page,
  from a widget library that sits behind a large number of government and
  enterprise sites. It was not a corner case worth a defensive check; it was
  the normal behaviour of the page.
- **Ending the run was too blunt**, and the evidence for that is in the same
  two rows. Both lapses are recoverable by *choosing differently* rather than
  by trying harder — commit the option; press Next Month first. The check now
  hands the failure back to the planner once before giving up (2026-09-09).
  The keystrokes should not be repeated; the plan should be reconsidered, and
  those are not the same thing.

---

## Where information sits is a perception decision

Three times now the same thing has been true, and it is worth stating as a
finding rather than rediscovering: **what perception knows is not what a
planner uses. Where it puts it decides that.** The model is not reasoning over
a database it can query. It is reading a page of text, once, and the position
of a sentence in that page changes whether the sentence has any effect.

The cleanest measurement is the inferred-option case, because only one thing
changed and it changed nothing about the information.

### The experiment

Same model (`gemini-3.1-flash-lite`), same live page, same page state — the
From field filled with `LAHORE CANTT` and its dropdown open — and the same
instruction, in two positions.

**As a rule in the system prompt**, seventh of nine:

    - A dropdown option only counts as chosen when you click it. Typing text
      into the field above it is not choosing; many pages will discard what
      you typed. If you have typed into a field and INFERRED options have
      appeared, click the one you want before doing anything else.

The element was in the list it was shown:

    19. option 'LAHORE CANTT'  <- INFERRED (role worked out from layout, not declared)

It answered:

    {"action": "type", "element_id": 11, "value": "KARACHI CANTT",
     "reasoning": "I will now enter the destination station to proceed with
                   your train search."}

**As a banner above the element list**, same words in substance:

    A LIST OF CHOICES IS OPEN, with 1 option(s) marked INFERRED below. Nothing
    is chosen yet. Typing the text is not choosing: click the option you want
    NOW, before touching any other field, or what you typed will be discarded.

It answered:

    {"action": "click", "element_id": 19, "value": null,
     "reasoning": "Clicking the inferred 'LAHORE CANTT' option confirms your
                   origin selection."}

| | rule in the prompt | banner above the list |
|---|---|---|
| Information present | yes | yes |
| Element present and marked | yes | yes |
| Model | same | same |
| Page state | same | same |
| Chose the option | **no** | **yes** |
| Calls to establish | 2 (a whole run) | 1 |

One call to fix, and the fix was moving a sentence.

### Why this is a perception finding and not a prompting trick

Because the same result has now happened three times, in three different
mechanisms, and only the first was ever framed as prompting:

1. **Overlays.** A modal's buttons in a list of sixty are just more buttons.
   `render_page` prints `AN OVERLAY IS COVERING THE PAGE` above the list and
   marks the elements `OVERLAY` and `OCCLUDED`. Without it, a run clicks
   underneath a modal and waits for a click that can never land — measured at
   10/10 (2026-09-05).
2. **Inferred options.** This section.
3. **Calendar days.** The model was given 42 day cells, eleven of the numbers
   appearing twice, with nothing separating a day of the month on screen from
   a day of the month either side. It picked the 15th of the wrong month. No
   prompt could have fixed that, because *the distinction was not in the
   input at all*. The fix was a qualifier on the element (2026-09-09), which
   is a change to what perception emits.

Case 3 is the one that settles the argument. Prompting can only rank what is
present. Case 1 and case 2 are the same problem one step earlier: the
information was present but positioned where it did not survive being read.
A rule in a standing list competes with eight other rules and a page of
elements; a banner is read at the moment the decision is made.

So the design rule, stated plainly:

> Anything a planner must act on **at this step** goes above the element
> list, in the imperative, naming the elements it applies to. Anything that
> is background belongs in the standing rules. And anything that
> distinguishes one element from another has to be **on the element**,
> because no amount of instruction can separate two lines of text that are
> identical.

That is a perception responsibility, not a prompt-engineering one. It says
what `serialize` must emit, what `render_page` must promote, and — as the
calendar showed — when neither is enough and the element itself has to carry
more.

### The cost of the alternative

Both banners were added *after* a run failed, and each failure was expensive
to read: the overlay case took a ten-run benchmark to see, the option case
took a full live run plus a transcript, and the calendar case took a live run
plus a hand-driven probe of the DOM. A model that ignores a rule looks
exactly like a model that is not clever enough, and the two have completely
different fixes. **A cheap way to tell them apart would be worth having and
does not exist here**: the only method used so far is to re-ask the identical
decision with the information moved, which costs one call and requires
already suspecting the answer.

---

## When verification passes wrongly

Three times now, something checked whether a thing worked, got "yes", and was
wrong. None was a bug in the check — each was a check measuring something
adjacent to what mattered. Collected because the pattern is the same every
time and the next one will look different again.

### 1. A click that lands and changes nothing

**What matched.** The click was dispatched, Playwright reported success, the
element was there and enabled.

**What actually happened.** The target was an `href="#"` nav link. The click
landed on a real element and did nothing. On the first such click the URL
even changes — it gains the fragment — so a naive "did the page change" test
passes too.

**What distinguishes them now.** Verification requires the snapshot to differ
*and* the step's expectation to hold, and `dead_link` marks `href="#"` and
`javascript:void(0)` in perception so a planner can avoid them. The residual
case — first click on a fragment link — is caught only by the expectation,
not by the change test, and that is worth remembering.

### 2. A 10/10 success rate concealing a guaranteed timeout

**What matched.** Ten runs out of ten reached the confirmation page and
emitted `task.completed`.

**What actually happened.** Every single run first clicked Register while the
modal still covered the page, waited out a ~30 second click timeout, and only
then dismissed the modal and retried. The recovery path worked, so the task
completed, so the headline number was perfect. Mean wall clock was 61.3s
against a floor of 17.1s and nothing in the success rate hinted at it.

**What distinguishes them now.** Wall clock, step count and path variance are
recorded beside the success rate for every run, and whether the recovery path
fired is visible in the step sequence. See "Why success rate alone is
insufficient" below.

### 3. A stale log entry matching `task.completed`

**What matched.** A verification script checked `text=task.completed` on the
frontend after driving one step, found it, and reported the run finished.

**What actually happened.** The run had completed one step of three. The
match came from the *previous* run's entry, still in the message log because
the log was not cleared on reconnect. The check was looking at the right
page for the right string and still got a wrong answer.

**What distinguishes them now.** The log is cleared per connection, so a
stale entry cannot survive into a new run. More usefully: the step count was
also printed, it read `1 steps`, and that is what exposed it. A single
boolean assertion would have passed.

### 4. A field that reads back correctly and is empty to the application

**Withdrawn and replaced, 2026-09-08.** This entry originally described a
field that was filled, verified by read-back, and then emptied itself on
blur. That is a real Element UI behaviour, but it is not what happened in the
run cited: the field was never filled at all, because the input is `readonly`
until clicked. See the correction in the 2026-09-07 entry.

The replacement is the same *class* of failure with evidence behind it, and
it is worse than the withdrawn version.

**What matched.** The Departure Date field was filled with `2026-10-15` and
read straight back as `2026-10-15`. It still read `2026-10-15` at the next
perceive, and the one after. By every check the loop had, and by anything
visible on the screen, the date was set.

**What actually happened.** It was not set. Element UI's date picker updates
its bound model when a day is *picked*, not when text is typed into the
input, and the two are not connected. The outgoing search request said:

    {"boardStationCode":"LRC","arrivalStationCode":"KCT","travelDate":""}

The DOM said `2026-10-15`. The application said `""`. The search returned
`{"msg":"E0117","code":500}` and the page showed its empty state, which reads
as "no trains found" and means "you sent me no date".

**What distinguishes them now.** Nothing does, and nothing in this design
can. Read-back verifies the DOM, and **the DOM is not the application's
state**. A framework keeps its truth in JavaScript that perception cannot
reach and would have no business reaching. Every check available here -
read-back, durable re-check, a screenshot in the trust panel - agrees with
the DOM and is wrong together.

The only defence found is indirect: drive the widget the way a person must,
so the framework's own handlers run. The railways plan now picks the day from
the calendar instead of typing it, and the request goes out populated. That
is not verification, it is avoidance, and it works only because we knew to
look. **Recorded as open.**

**Durable verification was still worth building.** It does not catch this
one, but it catches the blur case the withdrawn entry described - which is
real, just not what happened here - and it is now under test
(`test_durability.py`). What it changed: a value that stops being there ends
the run and says so, instead of the loop carrying on with a form it believes
is filled.

### 5. A step that failed, was skipped, and left no trace of either

**What matched.** A run that reached every step and reported
`task.completed`. Read as a message stream: `step.presented(1)`,
`step.presented(2)`, `task.completed`. Nothing anywhere said otherwise.

**What actually happened.** Step 1 failed both strategies. The loop is built
to absorb a first failure — it increments `consecutive_setbacks`, hands the
reason to the planner as a `setback`, and continues, which is the right
design: a planner that can re-plan should get the chance. But
`HardcodedPlanner` ignores setbacks by construction, so it simply served step
2, and **nothing at all was sent to the frontend**. The emitted trace of a
silently skipped step was byte-for-byte identical to the trace of a completed
one.

**What it cost.** A day. The first live railways run (2026-09-07) was read as
"step 1 filled the From field, verified it, and the value evaporated on blur"
— a coherent story, consistent with every message the run emitted, and wrong.
Step 1 had never filled anything; the input was `readonly`. The whole
published account of that run had to be withdrawn and rewritten, and the
mechanism it blamed was not present on the page. The wrong reading survived
because **nothing that was recorded could have contradicted it**.

**What distinguishes them now.** `step.failed` (CONTRACT.md, 2026-09-09),
carrying the step index, the instruction in the words the user was shown, the
reason, and how many strategies were tried. The overlay shows it briefly and
quietly — the run is still going, and dressing a recovered setback up as a
failure would teach people to distrust a system that is working — but it is
never silent. Four tests pin it down, including that a run where nothing
fails stays quiet, and that giving up does not also report a skip.

**The general lesson, which is not about this bug.** The other four cases here
were all found by putting a second number next to the first. This one could
not be, because the second number did not exist. An agent that recovers from
its own errors must emit the fact that it recovered, or its successes and its
near-misses are the same observation — and the person debugging it, or the
person using it, has no way to tell which one they are looking at.

### 6. A run that completed, returned real results, and answered a different question

The most serious entry on this page, and the only one where the system
produced a wrong answer rather than a wasted step. Everything above cost time.
This cost correctness, silently.

**What matched.** Everything. Every check the loop had agreed the run had
worked:

| Check | Verdict | Why it was satisfied |
|---|---|---|
| Every step's read-back | pass | the values typed were genuinely typed |
| Every step's page-change check | pass | the page changed each time |
| `step.failed` | not raised at the end | the steps' own actions succeeded |
| Durable verification | raised once, then cleared | the lapsed record was dropped after being reported |
| `task.success` = `rows_at_least=1` | **pass** | **two real trains came back** |
| The user's screen | `task.completed` | a finished task, and a timetable |

**What actually happened.** The goal was *Find trains from LAHORE CANTT to
KARACHI CANTT on **2026-10-15***. The search that went out was:

    {"boardStationCode":"LRC","arrivalStationCode":"KCT","travelDate":"2026-09-15"}

The model had typed `2026-10-15` into the date field, then clicked `15` in the
calendar — the 15th of September, the month the picker opens on. It never
pressed `Next Month`. Durable verification caught the change, reported it, and
handed it back to the planner as a setback; the model re-planned and clicked
search anyway. Two trains came back. They are real trains. They run on the
wrong day.

Nothing on the screen said so. A user asked to find trains for the 15th of
October would have been shown a departure board and a completed task.

**Which check was too weak.** `rows_at_least=1`, and it is worth being precise
about *why*, because the check is not buggy — it answers the question it was
asked, and the question was wrong.

    success=Expectation(rows_at_least=1)

"Results appeared" is satisfied by a search for **any** date. The goal names a
date and nothing in the run could test it:

- **Not the results.** The table is `Train No.`, `From/To`, `Time`,
  `Duration`. There is no date column, so `content_says` has nothing to match.
- **Not the URL or title.** Neither changes; it is a single-page app.
- **Not a label.** No interactive element carries the date.

The only place the requested date exists on the finished page is the input
field the user watched being filled — and `Expectation` had no vocabulary for
a field value, though `Snapshot` had carried them since the day before.

**What distinguishes them now.** `Expectation.value_is` (2026-09-09). The
railways task's success is now results **and** the departure field holding the
goal's date, in the format the page writes it back in:

    success=Expectation(
        rows_at_least=1,
        value_is=FieldValue("Departure Date", "15-10-2026"),
    )

The exact failing snapshot is a test (`test_success_conditions.py`): the same
page, the same two trains, `15-09-2026` in the field. It fails now. The same
test asserts that `rows_at_least=1` alone still passes on it, so which check
was too weak is pinned down rather than described.

**And the change that let it happen was reverted.** Continuing past a lapse
was a deliberate change made that morning, on reasoning that still looks
right in isolation: both live lapses were recoverable by choosing differently,
and a planner that can re-plan should get the chance. It was reverted the same
evening. A lapse ends the run again.

The trade is stated plainly in DECISIONS.md: a recoverable stop is worth more
than an unrecoverable success. Stopping is visible, wrong, and fixable by the
person watching. Finishing with the wrong answer is none of those.

**The pattern this one breaks.** The other five cases were all found by
putting a second number beside the first — step count beside completion, wall
clock beside success. This one had a second number. Two trains came back, and
that was the number that lied, because it measured the wrong thing well. The
defence here is not another number but a check that knows what the task was
*for*: not "did something happen" but "did the thing the goal named happen".
Every success condition in this repo should be read with that question, and
`RAILWAYS_TASK` failed it for four days without anyone noticing, because it
passed.

### The pattern

Every one of these six passed a check that was true but not sufficient: the
click did land, the task did complete, the string was on the page, the value
was in the field.

For the first three the missing thing was *cost* — a wasted step, thirty
seconds, an entire run's worth of context — and the defence was a second,
unrelated number beside the first: step counts beside completion, wall clock
beside success, the actual sequence beside the outcome. Two numbers
disagreeing is how those three were found.

Cases 4 to 6 do not fit that shape, and it is worth being clear about why
rather than stretching the original lesson over them.

- **Case 4** had no second number available. The DOM said the field held the
  date at every check, and every signal this design has is downstream of the
  DOM, so there was no second, unrelated observation to take. Only the
  outgoing request disagreed, and nothing was watching it.
- **Case 5** had no first number. A step that failed and was carried past
  emitted nothing at all, so its trace and a successful step's were the same
  bytes. You cannot cross-check an observation that was never made.
- **Case 6** had two numbers that agreed, and both were right. Two trains came
  back; the page really did change. What was wrong was the *question*: "did
  results appear" is satisfied by a search for any date, and the goal named
  one.

So the rule the first three suggest — put a second number next to the first —
is necessary and not sufficient. The other three say: emit the fact that
something went wrong even when you recovered from it (5); know that agreeing
signals may share a single source and be wrong together (4); and ask whether
the check is measuring the thing the task was actually for (6).

---

## Why success rate alone is insufficient

Across every measurement on this replica so far, **success rate has been
10/10 in every condition that ran** — before overlay detection, after it, and
with it explicitly disabled. It has never once distinguished a good run from
a bad one.

Everything that mattered showed up in the other columns:

| | Before overlay detection | After | Detection disabled |
|---|---|---|---|
| Success rate | 10/10 | 10/10 | 10/10 |
| Mean wall clock | 61.3s | 17.1s | 44.5s |
| Steps | 6–10 | 5 | 4 |
| Modal handled correctly | never | always | never |

Mean time fell **72%** (61.3s to 17.1s) between the first two columns while
completion rate did not move at all. What the 10/10 was concealing was a
guaranteed ~30s click timeout in *every single run*, and, in the disabled
condition, a modal being clicked through rather than dismissed.

For this project, completion rate is a floor check — it catches total
breakage and nothing else. Report it alongside steps, wall clock, path
variance, and whether the recovery path had to fire; a run that only
completes because retry rescued it is not the same as a run that went right,
and only the other columns can tell them apart.

---

## The DOM is not the application's state

A boundary of this approach rather than a defect in it, and worth stating
plainly because everything perception does sits inside it.

Perception reads the accessibility tree, the DOM and computed layout. Between
them those describe what a page *is showing*. They do not describe what the
application running the page *believes*, and on a single-page app those are
two different things that can disagree without any visible sign.

**The evidence.** The live railways date field, 2026-09-08:

| Observation | Value |
|---|---|
| `input.value`, read back immediately after typing | `2026-10-15` |
| `input.value`, at the next perceive | `2026-10-15` |
| `input.value`, at every perceive after that | `2026-10-15` |
| What the screenshot in the trust panel showed | `2026-10-15` |
| **What the application submitted** | **`"travelDate":""`** |

The outgoing request was
`{"boardStationCode":"LRC","arrivalStationCode":"KCT","travelDate":""}`. The
server answered `{"msg":"E0117","code":500}` and the page showed its empty
state, which reads as "no trains found" and means "you sent me no date".

Element UI's date picker updates its bound model when a day is *picked*. Text
typed into the input updates the input and nothing else. The two are simply
not connected, and no amount of looking at the input can reveal that.

**Why no DOM-level observation would have caught it.** Every signal available
to this design is downstream of the DOM:

- **Read-back** reads `input.value`. Correct.
- **Durable verification** reads `input.value` again, later. Still correct —
  the value never went anywhere.
- **The `Snapshot` diff** compares URL, title, labels, form values and
  content. All consistent, all describing a filled form.
- **The trust panel** screenshots the rendered page. The user would have seen
  the right date and approved.

All four agree, and all four are wrong together, because they are four views
of one source. Adding a fifth DOM-level check would add a fifth agreeing
wrong answer. This is not a gap that more careful reading closes.

**What would actually close it**, none of it currently in scope:

1. **Watch the network.** The request body is the application's state, stated
   by the application. It is also the only signal here that was *right*. CDP
   gives it for free via `Network.requestWillBeSent`. This is the strongest
   option and the one to try first.
2. **Read the framework's model directly** — Vue's `__vue__`, React's fibre.
   Per-framework, version-fragile, and it would put SIMBA inside the page in
   a way the rest of the design carefully avoids.
3. **Drive every widget the way a person must** and never type into anything
   that looks like a picker. This is what the railways plan does now, and it
   works — but it is avoidance, not verification. It only worked because we
   already knew to look, which is exactly the knowledge a real user does not
   have.

**The honest summary.** SIMBA can verify that a page *looks* the way a step
intended. It cannot currently verify that the application *agrees*, and on
framework-driven sites those come apart quietly. Every claim this project
makes about verification should be read with that boundary attached.

---

## Known limitations

- **These numbers come from a free-tier model.** `gemini-3.1-flash-lite` was
  chosen because it was the strongest model whose free quota allowed ten runs,
  not because it is the right model for the project. Treat every figure here
  as a floor.
- **The free quota is 20 requests per day, per model.** At 5–10 requests per
  run that is two to four runs a day. The first attempt at the ten-run
  benchmark got one run in and then nine consecutive HTTP 429s, which is why
  the model is a lite one. Plan benchmark sessions around this, or use a paid
  key.
- **The final benchmark must be re-run on the demo model.** Whatever model is
  used on demo day is the one these numbers should describe. Re-run both the
  before and after configurations on it before quoting any of this in the
  report — a stronger model may not need the overlay hints at all, which
  would change what the perception work is worth. The 2026-09-05 ablation
  tried and could not: `gemini-3.8-flash` allows 20 requests per day, about
  four runs, and a run needs 4–5. **This is the single biggest gap in the
  evaluation** and the first thing a paid key should be spent on.
- **The strongest models the key lists are not usable at all.**
  `gemini-3.1-pro-preview` and `gemini-pro-latest` return 429 on the first
  request; `gemini-2.5-pro` returns 404. The "demo model" above is the
  strongest that actually answers, not the strongest that exists.

### What perception cannot see

- **The DOM is not the application's state.** The boundary, in full, under its
  own heading above. A field read back correctly at every check while the
  application submitted an empty value, and every signal available here agrees
  with the DOM and is wrong together. Watching the network would close it and
  is not in scope. **Every claim this project makes about verification should
  be read with this attached.**
- **`INTERACTIVE_ROLES` is a fixed list of fourteen roles.** Anything outside
  it is not a control as far as `build_elements` is concerned, whatever the
  page thinks. `slider`, `treeitem`, `option` on a native `<select>`,
  `combobox` variants a library invents — none of them reach a planner. The
  live railways flow only works because `interactivity.py` reaches round the
  outside of this list from layout; the list itself has not moved since it was
  written. Nothing has been measured on a page that needs a role it lacks, so
  the size of this gap is unknown rather than small.
- **A modal's content is skipped along with a dropdown's.** Content extraction
  excludes floating panels because a date picker is not content, and nothing
  yet tells a dialog from a popup.
- **Inference is confined to the first document.** Iframes are not read.

### What the orchestrator cannot promise

- **A success condition has to be written by hand, per plan.** `value_is`
  closes the railways case and it is per-field and per-task: a plan whose
  author does not write one is exactly as blind as `RAILWAYS_TASK` was for
  four days, and case 6 is what that looks like. Nothing warns an author that
  their success condition cannot see the thing their goal names. This is the
  most likely source of the next wrong answer.
- **Trace memory has never run against a live model.** Replay needs no model
  and is covered; the record-then-replay cycle on a real run is not.
- **The JS-click fallback can click through a modal.** With overlay detection
  off it does so in 10/10 runs and the run still passes.

### What is measured, and what that leaves

The three limitations this section used to carry — one replica, no cost
measurement, no hardcoded baseline — were true when written and are now
contradicted by results earlier in this same file. Removed rather than
quietly corrected, because a limitations list that disagrees with its own
evidence is worse than no list: it is the section a reader trusts to be
current.

For the record, since each was cited as a gap:

- **Three flows, not one.** Two replicas plus a live public site
  (2026-09-06, 2026-09-07 onward).
- **Cost is recorded.** Tokens and dollars per run, per model, in the
  2026-09-06 A/B and every live run since.
- **The hardcoded baseline exists.** The A/B ran on 2026-09-06 and the
  hardcoded arm is the deterministic control every flow now defaults to.

What that leaves is narrower and worth stating plainly: **no flow has been
measured more than once with a model since the perception work landed.** The
ten-run benchmarks are all from 2026-09-05, against the registration replica,
before inferred roles, content extraction, qualifiers and panel headings
existed. Every number in this file describing *model* behaviour predates the
thing it would now be measuring.

*Still true on 2026-09-17. The newest LLM transcript in `logs/` is dated
2026-09-09.*

---

## 2026-09-17 — the voice under test, every ending rendered, three sites re-read

No model was called and no flow was run end to end against a site. What was
measured is the test suite, what the new tests catch, and what perception
reads on each site today.

### The suite

| | Before (HEAD `cc4704f`) | After |
|---|---|---|
| Passed | 223 | **258** |
| Failed | 1 | 0 |
| Skipped | 7 | 7 |
| Wall clock (pytest's own figure) | 275.4s | 288.2s |

The one failure before is not a defect in `cc4704f`: `copy.ts` was edited
while that run was in progress and `test_copy.py` read the edited file. The
2026-09-15 STATUS.md figure for that commit is 224 passing. The two wall
clocks are not comparable either — the second run shared the machine with a
browser capturing serializer output and a `vite build`.

The 34 new passes: 15 in `test_copy.py` (10 tests before, 25 after), 13 in the
new `test_terminal_states.py`, 5 in `test_success_conditions.py`, 1 in
`test_billing.py`. The 7 skips are the same 7: five need an Electron host,
two need `SIMBA_LIVE_TESTS=1`. **Nothing that needs the host or the live site
was run.**

### Does the copy test catch what it is for?

A test that passes first time proves nothing on its own. Each mutation below
was applied to the source, the copy test run, and the source restored.

| Mutation | Caught by |
|---|---|
| A curly apostrophe in a plan's instruction | `test_the_backend_apostrophes_are_straight` |
| A plan writing its own stop button labelled "Not now" | `test_every_step_stops_in_the_same_words`, `test_nothing_in_the_backend_writes_its_own_way_to_stop` |
| The old failure reason, "The user chose not to continue." | `test_the_backend_uses_no_word_the_reader_would_have_to_be_taught` |
| The old backend suggestion, "Can you take it from here? I'll carry on afterwards." | `test_the_stuck_screen_reads_the_same_whichever_side_wrote_it` |
| `let it choose` written back into `LevelControl.tsx` | `test_no_component_writes_its_own_words` |
| The colon back on "Here's what I found" | `test_sentences_end`, `test_the_wording_asked_for` |
| `voice.STOP` changed to "Not now" everywhere at once | **nothing, at first** |

**8 mutations, 7 caught.** The miss was real: every rule was about the words
being *consistent*, and changing the stop label everywhere at once is
perfectly consistent. `voice.STOP == "Stop this"` is now pinned in
`test_the_wording_asked_for`, and the mutation fails. One further attempt
broke an import rather than the rule it meant to test; it was redone and is
the "writes its own stop button" row.

The old component scan, run against `cc4704f`'s `TrustPanel.tsx`, passes it.
The new scan finds two strings in it: `Hide the page` and the image
description. With `LevelControl.tsx`'s `let it choose`, three strings were on
screen and outside `copy.ts` while the test said none were.

### Does the terminal test catch the dead end?

`test_terminal_states.py`, 13 tests, **32.5s**, of which the `vite build` it
runs first took **5.2s** measured separately.

Control: the same tests against `cc4704f`'s `App.tsx`, everything else
current.

| Test | Result |
|---|---|
| `test_every_ending_has_something_to_press[stuck]` | **failed** — nothing to press |
| `test_no_ending_shows_a_web_address[completed without an answer]` | **failed** — the backend's `summary`, goal plus URL, was on screen |
| `test_the_stuck_screen_asks_and_offers_a_way_on` | **failed** |
| The other 10 | passed |

3 failed, 10 passed, 19.8s. Both defects it exists for are present in the
previous version and absent from this one.

### Findings, end to end, for the first time

`Task.answers` had no test at all. `test_billing.py` now runs the billing plan
against the replica and asserts `task.completed.findings` is exactly:

| label | value |
|---|---|
| Your bill | `14,382` |
| Due | `15-09-2026` |

Both are read on the results page; the run ends on the detail page, where
neither column exists. The due date is as the page wrote it.

### What perception reads today

Captured 2026-09-17 with `read_async` and `render_page`, at 1280x800. The
two replicas were run locally; the live page was loaded **once**, with the
screener's user agent, and not touched.

| Page | Elements | Overlay | Occluded | Dead links | Unnamed | First recorded |
|---|---|---|---|---|---|---|
| Registration, course list, modal up | 66 | 1 | 65 | 44 | 0 | 66 (2026-09-05) |
| Billing, enquiry result | 39 | 0 | 0 | — | — | 39 (2026-09-06) |
| `pakrailways.gov.pk/train`, idle | 18 | 0 | 0 | 3 | 4 | 18, 3 dead, 4 unnamed (2026-09-07) |

Every element count matches the first measurement. The live page is
structurally unchanged in the respects that were measured, which is not the
same as the flow still completing — that was not run.

The live page took 6,593ms to load *including* a fixed 2,500ms settle wait.
The 2026-09-07 figure of 2,625ms included a 1,500ms wait. Neither excludes
the network, and the two are not a like-for-like comparison.

Content on the billing results page, as a planner's success condition and
`About.finds` see it: `P/WITHIN → 14,382`, `DUE DT → 15-09-2026`, and eight
more pairs from the same row. On the live page the only content is one
prominent value, `TRAIN TIMINGS` at 24px.

### Not measured

- Any LLM call. The run STATUS.md has been waiting on since 2026-09-09 is
  still not made.
- Any flow end to end on a site, including the live one, and anything with
  the Electron host up.
- `ruff` and `black`, which are not installed.
- Whether the new wording is *better* for the people it is for. Everything
  above checks that it is consistent and present, not that it is right.

### Drift in this file, found 2026-09-17

These statements contradict later entries in the same file. They are listed
here rather than edited, because the rule at the top says old entries are not
edited, and because a reader who meets one should find the correction.

- **"Durable verification, justified"**, last bullet: "The check now hands the
  failure back to the planner once before giving up (2026-09-09)." Reverted
  the same day. A lapse ends the run.
- **"When verification passes wrongly"** opens with "Three times now". There
  are six cases.
- **Case 5** says "The other four cases here were all found by putting a
  second number next to the first." The section's own closing, *The pattern*,
  says cases 4 to 6 do not fit that shape.
- **2026-09-07**, and **2026-09-08** under *Still open*: a step that failed
  and was skipped is "still open" and "invisible to the user". Closed on
  2026-09-09 by `step.failed`.
- Not drift, but a reader will meet it: **case 6** and the **2026-09-09b**
  entry describe the fix as `Expectation.value_is`. This task renamed it: it
  is now `About.holds` (DECISIONS.md). The behaviour tested is the same.
- **Configuration under test** says the lite model was chosen because its
  free allowance was workable where `gemini-3.6-flash` allowed 20 requests a
  day. *Known limitations* says 20 a day **per model**, the 2026-09-09 entry
  says 20 a day for the lite model, and the 2026-09-05 ablation names the
  stronger model `gemini-3.8-flash`. **Which quota and which model name were
  true on which day is not established.** The ten lite-model runs of
  2026-09-05 needed more than 20 requests, so the lite quota was higher then
  than it was on 2026-09-09, or the runs spanned days.
- **The 54s hardcoded railways run** that STATUS.md cites as re-verification
  on 2026-09-09 has no entry here.
- **`.scratch/benchmark.py`** is cited as the method for the ten-run
  benchmarks. `.scratch/` is gitignored, so the method is not in the
  repository. *Resolved later the same day: now
  `tools/evaluation/llm_registration_benchmark.py`, and "Which script produced
  which table" near the top of this file maps every table to its script.*

---

## 2026-09-17b — the owed LLM run: the model navigated the calendar, and verification stopped a correct run

The run STATUS.md had been waiting on since 2026-09-09. One run, live site,
read-only. `python -m tools.evaluation.railways_llm_run`.

| | |
|---|---|
| Model | `gemini-3.1-flash-lite`, OpenAI-compatible endpoint — the same as 2026-09-09 |
| Goal | Find trains from LAHORE CANTT to KARACHI CANTT on 2026-10-15 |
| Code | branch `feat/orchestrator-evaluation-scripts` at `7d7bc5d`, plus the uncommitted working tree of 2026-09-17 (`Task.about`, `voice.py`) |
| Model calls | **7**, no retries, no rate limiting, no errors |
| Tokens | 6,334 prompt + 376 completion = **6,710** |
| Cost | **$0.000784** |
| Wall clock | **71.8s** |
| Transcript | `logs/llm-20260917-134121.jsonl` (gitignored) |

### The run

    step 1/5  Fill in From.            "entering the departure station"
    step 2/5  Click LAHORE CANTT.      <- inferred option
    step 3/5  Fill in To.
    step 4/5  Click KARACHI CANTT.     <- inferred option
    step 5/5  Fill in Departure Date.  typed '2026-10-15'
    step 6/6  Click Next Month.        "The current month displayed is September
                                        2026, so I need to click the next month
                                        button to reach October 2026."
    step 7/7  Click 15.                "I am selecting the 15th of October 2026"
    help.requested - 'Departure Date' no longer holds what I put in it - it held
                     '2026-10-15' and now holds '15-10-2026'

Final form, read from the page: `From = 'LAHORE CANTT'`, `To = 'KARACHI
CANTT'`, `Departure Date = '15-10-2026'`. **All three correct.** No search
request was sent.

### The three questions STATUS.md said this run would answer

**1. Does stating the visible month change what the model picks? — Yes, in
this run.** At call 6 the prompt carried `IT IS SHOWING: 2026 September.`
above the list; the model pressed `Next Month`, and its reasoning restates
the banner. At call 7 the banner read `2026 October` and it picked October's
15th (`option '15'`, element 43, no qualifier). On 2026-09-09, with the same
model and the same page state but no banner, it clicked September's 15th in
both runs. That is one run against two, not a rate — but it is the first time
a model has navigated this calendar at all.

**2. Does the promoted setback change a run? — Not tested.** No step failed,
so no setback was ever sent; none of the seven prompts contains `SOMETHING
WENT WRONG`. The question is exactly as open as before.

**3. Does the held date (`About.holds`) make a wrong-date run fail? — Not
tested.** The run ended before the final success check, and no search went
out, so the check never ran. It also could not have been tested this way: the
date on the form was right.

### The outcome STATUS.md did not list

STATUS.md named three outcomes and said `help.requested` naming the departure
date would be the intended result. This run produced `help.requested` naming
the departure date — **for the opposite reason.** Durable verification
recorded what the model typed at step 5, `2026-10-15`. Clicking the day at
step 7 committed the date, and the picker rewrote the field in its own format,
`15-10-2026`. The durability check compares the field to what was typed,
character for character, saw a different string, and ended the run.

The value did not lapse. It was committed — the exact thing durable
verification exists to make the model do — and the check read that as the
value being undone. It cannot tell *reformatted* from *replaced*: on
2026-09-09 the same check saw `2026-10-15` become `15-09-2026` and was right
to stop.

| | 2026-09-09 run 2 | 2026-09-17 |
|---|---|---|
| Typed | `2026-10-15` | `2026-10-15` |
| Field at next check | `15-09-2026` — wrong month | `15-10-2026` — right date, page's format |
| Durability verdict | lapse, stop | lapse, stop |
| Correct verdict | stop | **carry on** |

The hardcoded plan never meets this: it clicks the date field rather than
typing into it, and only typed values are watched. So every recorded
hardcoded completion is silent on it. It is the first false stop recorded for
durable verification, and the first time in this file the system refused a
right answer rather than accepting a wrong one. It is **not fixed** —
flagged in STATUS.md, because the two obvious fixes are both design choices:
compare values through a date-aware normaliser, or stop watching a field once
the page has committed a choice into it.

Also on screen for that stop, had a person been watching: the stuck screen's
old wording, because the run started before this day's wording change — and
under it, in small type, a reason saying the date had been lost when it had
not.

---

## 2026-09-17c — every ending reached from a step was unpressable

Found while testing the new stop screen, not by looking for it.

A task always reaches its ending from a step. The ending's buttons could not
be pressed: the step screen that was leaving stayed in the column's grid cell
at opacity 0, empty, on top of them, and swallowed every click.

| Condition | Attempts | "Do something else" pressable |
|---|---|---|
| Stop pressed on a step, this day's `App.tsx` | 3 | **0** |
| Go-ahead pressed, then `task.completed`, this day's `App.tsx` | 2 | **0** |
| The same, **`cc4704f`'s `App.tsx`** | 2 | **0** |
| The same two cases after the fix | 4 | **4** |

So it predates this day's changes; `cc4704f` has it. How far back is not
established. The four endings `test_terminal_states.py` covered all arrived
from the working screen, which does not strand, so the test passed throughout.

**Cause, as far as it was measured.** Every ending clears `step` in the same
update that changes the screen, and the step component returned nothing once
`step` was null — while it was still mounted as the leaving half of the
crossfade. Keeping the last step rendered while it fades removes the stranded
element in every attempt. That Framer Motion never completes an exit whose
content has emptied is the inference, not something read out of Framer.

**Control.** `test_terminal_states.py` now has three endings reached from a
step. With the one-line fix reverted: 2 failed, 22 passed — `completed after
a step` and `stopped by the person` fail. **`stuck after a step` passes even
without the fix**, so the test does not protect that ending, and whether the
stuck screen was ever affected is not established. With the fix: 24 passed,
50.7s.

Full suite after this entry's and the next's changes: **271 passed, 7
skipped, 323.0s** — 13 more than the morning's 258 (11 terminal-state tests,
2 copy tests). The 7 skips are unchanged and were not run.

---

## 2026-09-17d — the formatter and linter the conventions named

`CLAUDE.md` and `README.md` said the Python code used `ruff` and `black`.
Neither was installed. Both were installed into `backend/venv` to measure,
then removed again with the four packages `black` had pulled in (`pip check`
clean afterwards).

Over the repository's 57 Python files (tracked, plus the day's new ones):

| | Result |
|---|---|
| `black --check`, default 88 columns | 46 files would change, ~1,965 changed lines |
| `black --check -l 100` | 40 files, ~1,499 lines |
| `ruff check`, its defaults (0.16.8) | 69 findings; 39 fixable automatically |

The largest groups: unsorted imports (17), unused `noqa` (9), blind `except`
(7), old-style annotations (6), subprocesses started in async functions (5),
unused imports (5). The claim was removed from both files rather than made
true, because making it true is a reformat of every module.

---

## 2026-09-17e — why the hardcoded benchmark is twice as fast as published

The 2026-09-06 A/B reports the hardcoded plan at **5.93s** mean (median 5.9,
range 4.9–6.4). Re-run on 2026-09-17 it is **3.01s** (median 2.8, range
2.8–4.6). A published figure off by 2x is the most serious problem this file
has had, so this entry is the investigation.

**Is it the same measurement?** Yes. The 2026-09-06 result file survives
(`logs/hardcoded_ab-2026-09-06.json`, gitignored). Its step instructions —
"Sign in to the course portal.", "Close the registration alert.", "Register
for CS-401, Advanced Widget Design." — are the registration plan's wording at
`3968838` and not later, so it was that plan, through that script, timing the
same span: browser launch to browser close.

**What was ruled out**

| Hypothesis | Test | Result |
|---|---|---|
| The code got faster since | `3968838` checked out in a worktree, today's copy of the script run against it | **3.0s** mean, 10/10, range 2.8–3.5. Ruled out |
| A dependency changed | install dates of Playwright 1.62.0, greenlet, pyee, Flask, Werkzeug, FastAPI, uvicorn in `backend/venv` | all 2026-09-04, before the A/B. Ruled out for the venv |
| One slow fixed cost (browser start, driver start) that something external could inflate | each phase of a run timed, current code, 5 runs | Playwright driver 0.40s, browser launch 0.10s, new page 0.10s, **the task 2.19s**, close 0.06s. No single phase is large enough; a 2x total needs the task itself to run at half speed |

**What was not ruled out**

- **Load on the machine.** Run while the full test suite ran alongside, the
  same old code measured **3.93s** mean, range 2.8–4.9. It moves the time in
  the right direction and widens the spread the way the 2026-09-06 runs are
  spread, but it does not reach 5.9s. There is circumstantial evidence the
  machine was busy then: `logs/cost-probe.jsonl` shows a model call at
  00:45:34 on 2026-09-06, and five commits landed between 00:39 and 00:52,
  two of them adding test suites. Nothing records whether tests were running
  during the ten runs.
- **A different interpreter or browser.** The 2026-09-06 script had no import
  path set up, so it cannot have been run the way it is today; how it was run
  is not recorded in the repository. If it ran under a Python outside
  `backend/venv`, the Playwright and Chromium it used could differ. Checking
  means reading outside the project (a Python install, or earlier session
  transcripts under the user's home directory), which the project's rules do
  not allow without asking. **Not checked.**
- Power state, thermal throttling, antivirus. Not recorded, not recoverable.

**Conclusion.** The cause is **not established**. The code and the venv are
exonerated; load reproduces part of the gap; the rest is unrecoverable from
what was recorded. The 5.9s is corrected in its entry, with the claims
derived from it withdrawn rather than recomputed.

**What would have prevented it.** The run recorded a number and nothing about
the conditions it was taken under — interpreter, other processes, whether it
was run alone. Every script in `tools/evaluation/` should record the Python
executable, the Playwright version and the wall-clock start time into its
result file. Not done in this entry; flagged in STATUS.md.

**Also found.** The one-call cost figure in the 2026-09-06 entry (61 + 62
tokens), recorded as having no surviving script, has a surviving transcript:
`logs/cost-probe.jsonl`, 2026-09-06 00:45. The script that wrote it is still
missing.

**What else leans on a timing from those two nights.** The LLM figures in the
2026-09-05 entries (61.3s, 17.1s, 19.1s, 44.5s) were measured in the same
fashion and have not been re-run. Their *differences* between conditions are
large enough that a 2x environmental factor applied to both arms would not
reverse them, but none of the absolute seconds should be quoted as today's.

---

## 2026-09-17f — the railways LLM run through the Electron host: completed, on the right date, with no answer shown

The second LLM run of the day, after durable verification was changed to
accept a value the task declared (DECISIONS.md). Run through the real stack
so it could be watched: `run.ps1 railways` with the LLM planner, the goal
typed into the real overlay, each step left on screen 2.5s and then answered
with "Yes, do that" in the window over CDP
(`python -m tools.evaluation.railways_llm_stack_run`). Live site, read-only.

| | |
|---|---|
| Model | `gemini-3.1-flash-lite`, same as every railways run |
| Model calls | **8**, no retries, no rate limiting, no errors |
| Tokens | **7,305** |
| Cost | **$0.000847** |
| Task duration (`task.completed.duration_ms`) | **84.4s**, of which 8 × 2.5s was the deliberate pause before each answer |
| Transcript | `logs/llm-20260917-142859.jsonl` (gitignored) |

### The run

    step 1  Fill in From.              typed 'LAHORE CANTT'
    step 2  Click LAHORE CANTT.        <- inferred option
    step 3  Fill in To.                typed 'KARACHI CANTT'
    step 4  Click KARACHI CANTT.       <- inferred option
    step 5  Fill in Departure Date.    typed '2026-10-15'
    step 6  Click Next Month.          "The current month is September, so I need
                                        to click the next month button to reach
                                        October."
    step 7  Click 15.                  "the 15th from the currently displayed
                                        calendar for October 2026"
    step 8  Click element 13.          <- the unnamed search button
    task.completed - 8 steps, 8 calls

The search that went out:

    {"boardStationCode":"LRC","arrivalStationCode":"KCT","travelDate":"2026-10-15"}

Final form `From = 'LAHORE CANTT'`, `To = 'KARACHI CANTT'`, `Departure Date =
'15-10-2026'`. One train came back, `2DN`, 22 h 16 min. **The first LLM run
in this project to finish a live task correctly.**

### The three questions, against STATUS.md's outcomes

**Month banner — changed the run, again.** Call 6 was shown `IT IS SHOWING:
2026 September` and pressed Next Month; call 7 was shown `2026 October` and
picked its 15th. With the banner: 2 of 2 runs today navigated the calendar.
Without it, 2026-09-09: 0 of 2. Still four runs, not a rate.

**Setback placement — not exercised, for the second time.** No step failed;
none of the eight prompts carries a setback. Two runs today have now passed
without producing the situation this change is for. It is unanswered, and a
run that goes well cannot answer it: it needs a step that fails on purpose,
which a live site will not supply on demand.

**Held date — changed the run, through durability rather than success.** Up
to step 7 this run matched 2026-09-17b call for call, and so did the page:
the typed `2026-10-15` became `15-10-2026` when the day was picked. That
stopped 17b. Here it matched the declared `About.holds` value and was
accepted, and the run went on to search. At the end the held date was checked
as part of success and passed — correctly, since the date was right. This is
STATUS.md's second outcome: *`task.completed` on the goal's date*. What the
held date was built for, failing a run that searched the **wrong** date, is
still untested on a live run. A correct run cannot test it.

The acceptance is inferred, not logged: the loop emits nothing when it
accepts a declared value. The inference rests on the two runs being identical
up to that point, with the only code difference being that change.

### What went wrong in a run that went right

**No answer on the closing screen.** `task.completed.findings` was empty, so
the overlay said "That's done." and repeated the goal instead of showing the
train. The task declares `Train` ← `Train No.` and `Journey` ← `Duration`,
and neither was found. Read from the live page after the run: content
extraction reports three tables with **no headers** — the results' header row
(`Train No.`, `From/To`, `Time`, `Duration`) is a table of its own, one row of
plain cells, and the body `2DN | LAHORE CANTT KARACHI CANTT | 08:04 06:20 | 22
h 16 min` is another. Nothing pairs them, so there are no label/value pairs
at all. `rows_at_least=1` passed on the body rows regardless.

On 2026-09-09 the same results were recorded paired to their headers. Whether
the site's markup has changed since, or the earlier pairing came through a
path that no longer applies, is **not established**. Flagged for perception.

**"Click element 13."** The unnamed search button reached the screen as that
sentence, in front of the person being asked to approve it. Known and flagged
since 2026-09-15; seen in a watched run for the first time.

**An empty field can override the model.** An LLM "Fill in" step shows an
empty field, and the overlay sends whatever that field holds when "Yes, do
that" is pressed. The loop takes a sent value over the model's whenever the
field has a `name` attribute. It did not bite here — the railways inputs have
no `name`, and the prompts confirm the model's values were typed (the station
lists narrowed to one option, as in the headless run) — but on a form whose
inputs are named, pressing go-ahead without typing would type nothing.
Inferred from `loop.resolve_value`, not observed. Flagged.

---

## 2026-09-17g — the terminal-state test covers every ending through a step

`frontend/test_terminal_states.py` now renders each ending twice — from the
working screen and through a step — plus the person's own stop. 37 tests,
79.5s.

Why the stuck ending was unprotected, measured with the fix in `App.Step`
reverted, three attempts each:

| How the stuck ending arrives after a step | Buttons pressable |
|---|---|
| `state.changed: stuck`, then `help.requested` — the order `loop.give_up` sends | 3 of 3 |
| `help.requested` alone | **0 of 3** |
| `help.requested`, then `state.changed: stuck` | **0 of 3** |
| (control) `task.completed` | **0 of 3** |

The strand happens when the message that clears the step is also the one that
switches the screen. With the stuck state first, the screen switches while the
step is still set, and nothing strands. The old test used exactly that order.
The contract does not require it, so the test now also sends
`help.requested` alone.

Control for the whole file, fix reverted: **5 failed, 32 passed** — the four
after-a-step endings other than stuck-in-the-backend's-order, and the stop.
With the fix: 37 passed.

---

## 2026-09-17h — the same benchmark three times in one day: 3.01s, 3.93s, 6.85s

The 2026-09-06 hardcoded figure of 5.93s could not be explained
(2026-09-17e). Wiring the conditions recorder in produced the explanation, or
as close to one as this machine allows. The same script, the same ten runs,
the same code, the same machine, one day:

| When | Mean | Range | CPU load at start | Conditions recorded |
|---|---|---|---|---|
| ~15:00 | **3.01s** | 2.8–4.6 | not recorded | no |
| ~15:30, full test suite running alongside | **3.93s** | 2.8–4.9 | not recorded | no |
| ~23:36 | **6.85s** | 6.2–7.5 | 23% | **yes** |
| (2026-09-06, published) | 5.93s | 4.9–6.4 | not recorded | no |

**A 2.3x spread with nothing in the repository changing.** Playwright 1.62.0
and Chromium 151.0.7922.34 in every run of the day; the loop untouched
between them; commit `2566938` for the two evening runs and the same working
tree for the afternoon ones. The published 5.93s sits inside that spread.

This does not name the mechanism — thermal state, power profile, what else
the machine was doing, none of which the repository can see. It does settle
what the mechanism is *not*: the code, the dependencies, or anything a reader
of the result file could have inferred. **Any wall clock from this machine
should be read as ±2x unless the conditions beside it say otherwise**, which
is the whole reason for recording them.

What that means for the figures in this file: every per-run *duration* — 5.9s,
19.1s, 44.5s, 61.3s, 17.1s, 46.1s, 54s, 71.8s, 84.4s — is a measurement of a
machine as much as of the system. The *differences within one session* are
still evidence: the overlay-detection ablation ran its two arms minutes apart
(19.1s against 44.5s) and its gap is one Playwright click timeout, which is a
mechanism, not a mood. Differences *between* sessions are not.

The November benchmark should run its arms back to back in one session, and
report the conditions block with them.
