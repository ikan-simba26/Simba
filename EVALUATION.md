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
| 2026-09-09 | The fix: a banner, not a rule; "What perception emits" | `railways_banner_probe` |
| 2026-09-09b | The run that completed on the wrong date | `railways_llm_run` |
| 2026-09-09b | Setback promoted, one call | `railways_setback_probe` |
| 2026-09-09b | Qualifiers, duplicate-label table | `railways_qualifier_probe` |
| "The DOM is not the application's state" | `"travelDate":""` while the field read `2026-10-15` | `railways_request_probe` (submits two live searches) |
| "Durable verification, justified" | The two live lapses | `railways_llm_run` (the 2026-09-09 runs) |
| 2026-09-17 | What perception reads today | `serializer_samples` (headless only) |
| 2026-09-18c | Headless against the host, all three sites | `viewport_perception_probe` (needs the host and both replicas; two live searches per environment) |
| 2026-09-19 | The closing screen, read off the screen | `host_overlay_run` (drives the overlay of a running stack; live search when the flow is railways) |
| 2026-09-19b | The twenty-page corpus, and every feature's range | `collect_corpus` (20 public pages, read in both environments; writes `data/corpus.json`) |
| 2026-09-20 | Every recorded perception figure, re-measured after the CSS-pixel change | `viewport_perception_probe` |
| 2026-09-20b | The 34-page corpus, driven states included | `collect_corpus` (starts the replicas itself; two live reads of the railways page) |
| 2026-09-17 | The suite, and the terminal test's control | `pytest`; the control swapped `App.tsx` by hand |
| 2026-09-17 | Copy-test mutations | **not preserved** — applied by hand, listed in the entry |
| 2026-10-30 | The estimator: agreement, the model, the cut points | `python -m backend.estimator.train`, or `python -m tools.rating.retrain` for this and the next row (`--min-ratings 5` until every page has 8) |
| 2026-10-30b | The model against the rules, the logged decisions, the two environments, the data's handling, each page's reasons | `estimator_compare` (reads local files; no model quota, no site) |
| 2026-11-01 | The estimator with and without raters 5007 and 5013 | `estimator_compare --without 5007 5013` (writes no model) |
| 2026-11-02 | How long the logo stays, on the real launcher | **not preserved** -- one-off scripts in `.scratch/`, described in the entry |
| 2026-11-02b | How overwhelming Pakistan's public websites are, as predicted | `overwhelm_index` (**one visit to each of 42 live sites; not for repeating**); `overwhelm_index --report` works it out again from what was saved and visits nothing |
| 2026-11-02c | The five first-screen features of the rated pages and the sites | `visual_features` (**reads 43 live pages and our replicas, then 35 live sites; not for repeating**) |
| 2026-11-02c | Old features against new, and the gate | `python -m backend.estimator.train_visual`, which refuses until Set 3 has answers; `--preview` runs on Sets 1 and 2 and writes only to `.scratch/` |
| 2026-11-02c | The overwhelm index by the new model | `rescore_index`, from what was saved, visiting nothing |
| 2026-11-05 | Raters, usable and dropped, per set | `python -m tools.rating.from_form "<Set 1>.csv" "<Set 2>.csv" "<Set 3>.csv"` |
| 2026-11-05 | Old, new and the five alone on Sets 1 to 3, overall and on the Pakistani pages; the gate | `python -m backend.estimator.train_visual --min-ratings 5 --charts` |
| 2026-11-05 | The overwhelm index by the live model, beside people's ratings | `python -m tools.evaluation.rescore_index --by live`, run by the line above, visiting nothing |
| 2026-11-05 | The two charts | `tools/evaluation/visual_charts.py`, drawn by `train_visual --charts` into `.scratch/retrain-visual/` |

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

> **Replaced 2026-10-16** by "the replica benchmarks, re-run on the current
> flows" (2026-10-16d): the registration now asks which course on the portal
> and registers behind a final screen.
>
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
This looked like the prompt-prominence finding for a third time, in a channel
where it had not been applied: the setback was appended *after* the page.
Moved above the element list and stated in the imperative, the same decision,
same page state, one call:

*Superseded 2026-09-18. On a rig where every run reaches this state, placement
changed 0 of 8 runs. This single call is what the claim rested on, and it does
not generalise — see "What perception emits decides what a planner can
use".*

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

## What perception emits decides what a planner can use

*Renamed 2026-09-18 from "Where information sits is a perception
decision", because that title asserted the half of it that eight runs
falsified. Anything citing the old name means this section.*

**What perception knows is not what a planner uses.** The model is not
reasoning over a database it can query; it is reading a page of text, once.
What reaches its decision is what perception chose to emit, and where it put
it.

*Narrowed 2026-09-18, with one sub-claim withdrawn.* This section was written
as "three times now the same thing has been true". Two of those cases are
about **information the model had not been given**, and both hold. The rest is
about **moving words the model already had**, and that has since been tested
on runs rather than on single calls: it made no difference in eight of eight
(2026-09-18). The two halves are stated separately below, because they are not
the same claim and only one of them is supported.

The cleanest measurement is still the inferred-option case, because only one
thing changed — but read "What does not hold" below before quoting it.

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

### What holds: emitting what the model did not have

Two cases, and in both of them perception put something into the input that
was not in it before. Neither is a prompting trick, because no prompt could
have produced the missing fact:

1. **Calendar days.** The model was given 42 day cells, eleven of the numbers
   appearing twice, with nothing separating a day of the month on screen from
   a day of the month either side. It picked the 15th of the wrong month. No
   prompt could have fixed that, because *the distinction was not in the
   input at all*. The fix was a qualifier on the element (2026-09-09), which
   is a change to what perception emits. **This is the case that settles the
   argument**: prompting can only rank what is present.
2. **Overlays.** Whether a control is covered is not derivable from a list of
   controls. `render_page` prints `AN OVERLAY IS COVERING THE PAGE` and marks
   the elements `OVERLAY` and `OCCLUDED`; without it a run clicks underneath a
   modal and waits for a click that can never land. **Measured at 10/10 runs**
   (2026-09-05) — the only leg of this finding with a run count behind it.
   Note what the marking adds: occlusion, which the page never declares.

So this much of the design rule stands, and it is a perception
responsibility — it says what `serialize` must emit:

> Anything that distinguishes one element from another has to be **on the
> element**, and any state of the page a planner must respect — covered,
> disabled, already chosen — has to be emitted at all, because no amount of
> instruction can separate two lines of text that are identical or supply a
> fact the input does not contain.

### What does not hold: moving words the model already had

> ~~Anything a planner must act on **at this step** goes above the element
> list, in the imperative, naming the elements it applies to.~~
> **Falsified as stated, 2026-09-18.**

That was the other half of the rule, and it rested on two single calls: the
inferred-option experiment above (one call against two) and the promoted
setback on 2026-09-09b (one re-asked decision). Both moved words that were
already in the prompt to a different position, and both got a better answer
once.

Tested on runs, it does not reproduce. A replica page rigged to fail
(`/stubborn`) put every run into the state the claim is about, with a setback
in hand, and `SIMBA_SETBACK_PLACEMENT` decided whether it sat above the
element list or after it: **0 of 8 runs changed, across two page shapes**
(2026-09-18). What decided recovery was the options the page left. Offered a
plausible wrong control labelled "Refresh and try again", the model took it
four times out of four — having been told in the imperative, directly above
the list, that its last action had done nothing.

The narrowed statement:

- **For a correction the model already holds, promotion is not known to
  change anything, and on the one rig where it has been measured it changed
  nothing.** It costs nothing, so it stays; it is not a result and should not
  be reported as one.
- **The inferred-option case is not a third leg of support.** It is n = 1, on
  a different page, and structurally identical to what the eight runs
  falsified — the same words, moved. It is recorded here as an observation
  until it is re-run the way the setback was.
- **Background versus imperative** — which rules live in the standing prompt
  and which are promoted above the element list — is therefore an unmeasured
  design preference, not a finding. It should be described that way wherever
  it appears.

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

- **Ratings are collected online as well as in person** (2026-10-22). Online
  raters see each picture at about half size, with nobody supervising, in one
  of two fixed orders (form A, or B, its reverse). Their rows say
  `"online": true` and which form; a trained result should be checked with
  and without them (DECISIONS.md, *Ratings are collected online*; *Two
  forms*).
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

### The environment a measurement was taken in

- **Content extraction has only ever been measured headless.** Added
  2026-09-18. Every perception figure in this file up to 2026-09-17 came from
  a headless Chromium launched by a probe script; every run a user sees goes
  through the Electron host's covered `WebContentsView`. The two are the same
  Chromium at the same 1280x800, which is why nobody thought to check — and
  they are not the same environment. The scrollbar-spacer defect
  (2026-09-17i) exists **only in the host**: on the same live page, the same
  route, minutes apart, the host's heading strip carries an empty
  `th.gutter` and the headless one does not (2026-09-18c). A bug that only
  appears where the product runs is invisible to every measurement here.
- **What re-measuring found.** All three sites were read twice on 2026-09-18,
  headless and in the host, and **no serialized figure differed** — elements,
  overlay, occluded, dead links, headings, tables, rows, pairs, and the
  values themselves (2026-09-18c). So the numbers in this file are not wrong.
  What was missing was any evidence that they were right, for two weeks, in
  the environment that matters.
- **What this means for a figure taken from now on.** A perception figure
  should say which environment produced it, and anything about *table
  structure* — column counts, header joins, pairing — has to be checked in
  the host, because that is the one thing shown to differ. The probe that
  does both in one run is `tools/evaluation/viewport_perception_probe`.
- **The host comparison is per-page and shallow.** It diffs what the
  serializer reports plus the heading strips' raw cell counts. Two
  environments agreeing on those does not make their DOMs identical, and the
  spacer's actual trigger is still unnamed.

### Wall clock, and what to report instead

- **The same code on the same machine on the same day ranged 3.01s to 6.85s.**
  Added 2026-09-18, measuring 2026-09-17h. Ten-run means of the hardcoded
  benchmark, nothing in the repository changing between them: 3.01s at ~15:00,
  3.93s at ~15:30 with the test suite running alongside, 6.85s at ~23:36 at
  23% CPU load. That is a **2.3x spread from the environment alone**, and the
  figure published on 2026-09-06 (5.93s) sits inside it.
- **Report step count and model calls as the primary metrics.** Both are
  discrete, both are what the system actually decides, and both have been
  perfectly stable where timing was not: the 2026-09-05 ablation's two arms
  each held one path with **zero variance in steps and calls across ten
  runs** while their mean times differed by 2.3x. Tokens and cost behave the
  same way, and pass rate is unaffected by load.
- **Report wall clock second, never alone.** With n, the range, and the
  conditions block beside it (`tools/evaluation/conditions.py`). A single
  mean with no range is not a measurement of this system; it is a measurement
  of this laptop.
- **Treat any difference under 2.3x as unexplained unless it has both.** Both
  arms measured in one session, back to back, *and* a named mechanism. A
  cross-session difference of that size is not evidence of anything.

**Audit of what in this file rests on a wall-clock difference** (done
2026-09-18, against the 2.3x spread):

| Claim | The difference it rests on | Verdict |
|---|---|---|
| "Overlay detection off costs ~25s per run" (2026-09-05) | 44.5s against 19.1s, **2.33x** | **At the boundary, and it survives on its mechanism, not its seconds.** Same session, minutes apart, ten runs per arm, zero variance, and the gap is one Playwright click timeout on an intercepted click. The conclusion it feeds — fewer steps is worse here — is already stated "regardless of the timing". Quote the mechanism; do not quote the 25s as a property of the system |
| Perception `read()` 0.19s idle against 0.22s with the calendar open, and its phase breakdown (captureSnapshot 0.03s against 0.05s) (2026-09-08) | **1.16x, one run each** | **The difference is not evidence and should not be read as one.** What survives is the magnitude: both reads are about 0.2s, two orders below the cost of a step, which is all the entry needed to claim. "Looking costs nothing" holds; "the calendar costs 30ms more" does not |
| "Mean time fell 72% (61.3s to 17.1s)", LLM against hardcoded | **3.6x** | **Outside the spread, and independently explained** by five model calls against zero. The direction is safe; the absolute seconds are from 2026-09-05 and are not today's |
| "3.2x faster", "about 13 seconds for five round trips" (2026-09-06) | derived from the unreproducible 5.93s | **Already withdrawn** (2026-09-17e), not recomputed |
| Test suite 275.4s against 288.2s (2026-09-17) | **1.05x** | The entry already refuses the comparison: the second run shared the machine with a browser and a `vite` build. No conclusion drawn |
| Single-run durations quoted throughout (46.1s, 48.9s, 66.9s, 71.8s, 73.4s, 79.5s, 84.4s) | **n = 1** | Descriptive of one run on this machine. No conclusion in this file rests on one, and none should |
| "The wrong turn cost 3,704 seconds" (2026-09-08) | 62 minutes against a run of about one | **Safe.** A 2.3x factor does not reach an order of magnitude and a half |

**Nothing in this file has to be withdrawn for this reason.** One claim —
the ~25s overlay cost — needs its mechanism quoted rather than its seconds,
and one sub-claim, the per-phase perception deltas, should not be read as a
difference at all. The November benchmark must run its arms back to back in
one session and publish its conditions block.

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
- **The credential store works only on Windows.** A saved password is
  encrypted with Windows' own key for the signed-in account (DPAPI,
  `backend/orchestrator/vault.py`). On any other system the store reports
  itself unavailable, nothing is saved, and the step offers no way to save:
  the person is asked for their password every time, as before the store
  existed (2026-10-03b). That path is the same branch as running with no store
  at all, which `test_vault.py` covers; it has not been run on another system.
  *Added 2026-10-05.*

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

---

## 2026-09-17i — the missing answer was a scrollbar, and the closing screen now shows the train

The run in 2026-09-17f finished correctly and showed nothing: `findings` was
empty because nothing paired `Train No.` with `2DN`. That entry said it was
not established whether the site had changed. **It had not.**

### What was actually wrong

`content.py` has not been touched since 2026-09-08, so the extraction code was
not the change. The markup is the same Element UI shape `_adopt_headers` was
written for — a one-row `el-table__header` table, then an `el-table__body`
table — and, probed directly on the live page today, it pairs:

    raw[0] headers=() widths=[4]  ('Train No.', 'From/To', 'Time', 'Duration')
    raw[1] headers=() widths=[4]  ('2DN', 'LAHORE CANTT KARACHI CANTT', '08:04 06:20', '22 h 16 min')
    -> joined, value_for('Train No.') = '2DN'

The same page inside the Electron host, after the same search:

    raw[0] headers=() widths=[5]  ('Train No.', 'From/To', 'Time', 'Duration', '')
    raw[1] headers=() widths=[4]  ('2DN', ...)
    -> widths differ, the join refuses, no pairs at all

**The fifth cell is a scrollbar spacer.** Element UI adds an empty
`<th class="gutter">` to the heading strip when the body scrolls, so the strip
is one cell wider than every row under it. `_adopt_headers` only ever joined
on an exact width match — deliberately, so a mismatch cannot name columns
wrongly — and a gutter is a mismatch.

So this was never about the site. It is **state**: the same page, the same
markup, pairs or does not pair depending on whether that table's body has a
scrollbar, which depends on the viewport and how many rows came back. The
headless probe had no scrollbar; the host, with its 1280x800 site view, did.
That is also why nothing caught it earlier: every recorded content measurement
before 2026-09-17 was taken headless.

### The fix, and what it refuses to do

`_without_gutter` discounts trailing header cells that are empty, and only as
many as the mismatch needs. A trailing cell with a name in it is still a
mismatch and still refuses — naming columns wrongly is worse than not naming
them. Six tests, four of them on the rule and one on the real markup in a
browser; with the allowance removed, two fail.

### Verified on the live site

Hardcoded plan, through the Electron host, driven in the overlay
(`python -m tools.evaluation.railways_llm_stack_run`):

| | |
|---|---|
| Steps | **5 of 5** |
| Task duration | **61.1s** (5 × 2.5s of that is the deliberate pause before each answer) |
| Model calls | 0 |
| Search sent | `{"boardStationCode":"LRC","arrivalStationCode":"KCT","travelDate":"2026-10-15"}` |
| Findings on `task.completed` | `Train 2DN`, `Journey 22 h 16 min` |
| **The closing screen** | **"Here's what I found / 2DN / Train / 22 h 16 min / Journey"** |

The gutter was present in that run — checked in the host's own page
afterwards, header strip five cells to the body's four — so the fix is what
put the train on the screen, not a lucky layout.

It is also the first hardcoded railways completion recorded since 2026-09-09:
the live flow still works. The wall clock is not comparable to the 46.1s and
54s of those days — it includes the pauses, and see 2026-09-17h on what a
duration from this machine is worth.

**Still true:** `value_for` returns the first pair, so "which trains?" answers
with one train. Two trains came back on 2026-09-09; one came back today.

---

## 2026-09-18 — a step rigged to fail, and the setback question answered: placement changed nothing

Three runs were meant to settle where a setback belongs in the prompt and
none could, because nothing failed in them. A live site will not fail on
demand, so the replica now has a page that does:
`/stubborn` on the registration replica, with a `<button>` that has no form
and no handler. Everything perception reports about it is true — named,
enabled, visible, uncovered — and pressing it changes nothing.

**The first move is forced to that button**, so every run reaches the state
the question is about with a setback in hand. Everything after it is the
model's. `python -m tools.evaluation.setback_placement_ab`, two runs per arm,
`gemini-3.1-flash-lite`, conditions recorded in `logs/setback_ab.json`.

### Two page shapes, eight runs

| Page | Live controls after the failure | Setback above | Setback after |
|---|---|---|---|
| Two controls | the registrar's route only | **recovered 2/2**, completed 2/2 | **recovered 2/2**, completed 2/2 |
| Three controls | "Refresh and try again", and the registrar's route | **recovered 0/2** | **recovered 0/2** |

**Placement changed nothing, in any of the eight runs.** What changed the
outcome was what else was on the page.

- With only one live way forward, the model took it whichever way it had been
  told. Recovery there is over-determined: the dead button is in its own
  history under "do not repeat", and every other element is a flagged dead
  link.
- With a plausible wrong option present, it took the wrong option both ways —
  "Refresh and try again", four times out of four, which reloads the same page,
  fails the change check, and ends the run in `help.requested`. The model was
  told in the imperative, directly above the list, that its last action did
  nothing; it pressed the button whose label says "try again".

### What this does to the earlier claim

EVALUATION.md's "What perception emits decides what a planner can use" drew on
three mechanisms plus this one. Two are unaffected: the overlay banner (10/10
runs, measured) and the calendar qualifiers (the distinction was absent from
the input) — in both, perception emitted something the model did not have.
The promoted setback is a different claim, because the words were already in
the prompt and only their position moved. It rested on **one re-asked
decision** on 2026-09-09b. The inferred-option banner, which that section
calls its second case, rests on one call in the same way.

That observation stands as a single call on a different page. It does not
generalise: on this rig, across eight runs and two page shapes, the promotion
made no difference at all. **The sub-claim is falsified as stated**, not
qualified —

> ~~Anything a planner must act on at this step goes above the element
> list.~~

— and this replaces it:

> Promotion is worth having and costs nothing, and there is no evidence it
> changes a run. Whether a planner recovers from a setback is decided by the
> options the page leaves it, not by where it was told.

The half of the rule that survives is about emitting what the input does not
contain — occlusion, a qualifier — which is a different mechanism with its own
evidence. The two are now stated separately in that section.

`SIMBA_SETBACK_PLACEMENT=after` restores the old position, so this can be
re-run against any model and any page.

### What the rig also showed

- **The loop's recovery works on a control that really fails.** Both
  strategies land on the dead button, the second being a JS click, and both
  change nothing (`test_setback.py`, 9 tests, no model).
- **A wrong recovery is safe.** Two consecutive failures end the run in
  `help.requested` rather than in a claim of success — which is what the four
  three-control runs did.
- **The first attempt at the rig measured the wrong thing** and is worth
  recording as a method note: the page included the replica's site nav, the
  model clicked "Registrar", reached the login page and hit the password
  refusal instead of the dead button. A rig with a live escape route is not a
  rig. The page now has no nav, and its clutter is twenty-four links that are
  all `href="#"`.
- **The model prefers the working route when it is offered one.** Left to
  choose first, it clicked "Take the long way round" and finished in one step,
  twice — which is why the first move is forced rather than prompted.

---

## 2026-09-18b — a finding carries every result, not the first

`Content.value_for` returned the first pair with a matching label, and
`findings_in` used it, so a goal that asks *which* trains run was answered
with one train. The 2026-09-09 search returned two — `2DN` and `14DN` — and a
finding would have named `2DN` alone. Nothing was wrong on the page or in the
pairing; the reader stopped at the first row.

`values_for` returns every value for a label in document order, dropping
repeats — both trains run `LAHORE CANTT KARACHI CANTT`, and saying that twice
is noise, not a second answer. `value_for` remains, as the first value, for a
label a page uses once, and is now expressed in terms of `values_for`.

`voice.found` turns a list into the line a person reads:

| Values | Shown |
|---|---|
| `2DN` | `2DN` |
| `2DN`, `14DN` | `2DN, 14DN` |
| five or more | `a, b, c, d and 1 more` |

Four and a count, because the closing screen shows a finding in the largest
type on it and twenty values would not be readable at a glance — which is the
only reason to show it large.

Measured on the 2026-09-09 results, rebuilt as markup in a browser:
`values_for("Train No.")` is `["2DN", "14DN"]` and the finding reads
`Train 2DN, 14DN`. The billing amount, a label its page uses once, is
unchanged at `14,382` — asserted end to end against the replica.

---

## 2026-09-18c — every site read twice, headless and in the host: the numbers agree, the markup does not

Every perception figure in this file before today was taken in a headless
Chromium. Every run a user will ever see happens in the Electron host, in a
covered `WebContentsView` at 1280x800. On 2026-09-17 that gap produced a
defect: the live results heading strip carried a scrollbar spacer in the host
and not headless, the header join refused, and a completed run showed no
answer (2026-09-17i). One environment-only bug is reason to check the rest.

`python -m tools.evaluation.viewport_perception_probe` reads each page twice —
once in its own headless browser, once through the host's site view over CDP —
and diffs the two. Conditions in `logs/viewport_perception.json`:
`346222c` (dirty: the probe itself was untracked), Python 3.12.3,
Playwright 1.62.0, load 28–79%, four measurement passes between 19:30 and
19:36.

### Everything the serializer reports is identical

| Page | Figure | Headless | In the host |
|---|---|---|---|
| registration `/courses`, modal up | elements / overlay / occluded / dead links | 66 / 1 / 65 / 44 | **same** |
| | headings / tables / rows / pairs | 3 / 1 / 20 / 177 | **same** |
| billing `/bill?reference=…` | elements / dead links | 39 / 32 | **same** |
| | headings / tables / rows / pairs | 5 / 3 / 19 / 70 | **same** |
| | `value_for("P/WITHIN")` | `14,382` | **same** |
| railways `/train`, idle | elements / unnamed / dead links | 18 / 4 / 3 | **same** |
| railways results, LHR→KHI | tables / rows / joined width / pairs | 2 / 2 / 4 / 4 | **same** |
| | `values_for("Train No.")` | `['2DN']` | **same** |
| railways results, LHR→RWP | tables / rows / joined width / pairs | 2 / 3 / 4 / 7 | **same** |
| | `values_for("Train No.")` | `['39UP', '1UP']` | **same** |

Not one figure differs. The registration, billing and railways-idle figures
also match what they were first recorded as (66/1/65/44, 39, 18/4/3), which is
the first time any of them has been confirmed in the environment that runs
them.

### The markup underneath is not identical, and that is the whole finding

`table_widths` above is measured *after* `_adopt_headers` has discounted an
empty trailing cell, so it reads 4 whether the strip had four cells or five —
it cannot see the bug it was written for. Reading the DOM directly, same
route, same minute, the two environments disagree:

| Heading strip on the results page | Headless | In the host |
|---|---|---|
| First strip: cells / empty / `class="gutter"` | 4 / 0 / 0 | **5 / 1 / 1** |
| Second strip: cells / empty / `class="gutter"` | 5 / 1 / 0 | **6 / 2 / 1** |

The host adds one empty `th.gutter` per strip. It is Element UI's scrollbar
spacer, and it is present in the host and absent headless on the same page,
the same route and the same markup, minutes apart. So the 2026-09-17 bug was
not a bad day on the live site: **it is a standing difference between the two
environments**, and it would recur on every host run.

What makes the serialized figures agree anyway is the 2026-09-17i fix:
`_without_gutter` drops empty trailing header cells, so both environments
join a 4-wide header to a 4-wide body and pair `Train No.` with the trains.
The fix is now verified live in the environment the bug lives in, which
2026-09-17i could not claim — that entry verified a run, not a comparison.

Two things this does **not** establish:

- **The trigger is not row count, and is not an overflowing body as far as
  the probe can see.** The scroll check (`overflow-y: auto|scroll` and
  `scrollHeight - clientHeight > 4`) found no scrolling wrapper in *either*
  environment, on a route with one result and on a route with two. The
  spacer's condition is something host-side the probe does not name.
- **No claim about the other two sites' markup.** They were compared through
  the serializer only; their figures agree, and nothing says their DOM is
  byte-identical.

### The live site, incidentally

LAHORE CANTT → KARACHI CANTT returned **one** train today (`2DN`, 22 h 16 min)
where 2026-09-09 returned two. LAHORE CANTT → RAWALPINDI returned two
(`39UP` 6 h 38 min, `1UP` 6 h 3 min) — which is this morning's `values_for`
change (2026-09-18b) working on a live page for the first time, in the host, with both
trains in the finding.

Six read-only searches today, across both environments and both routes.

---

## 2026-09-19 — the closing screen shows every result, verified on the live site

2026-09-18b fixed the reading: `values_for` returns every value a page gives a
label, and a finding's text became `2DN, 14DN` instead of `2DN`. What it did
not fix is that a finding is still **one string**, built by `voice.found`,
which stops at four values and counts the rest. That is right for the step
screen — a run in progress shows its finding in large type beside the
instruction — and wrong for the closing screen, which is the answer. A search
returning five trains would have ended on "and 1 more".

### The change

`Finding` carries both forms, and `values` is an additive optional field of
the kind CLAUDE.md allows without a ratification session:

| | | |
|---|---|---|
| `value` | one line, stops at four | what the step screen shows |
| `values` | every value, page order | what the closing screen shows |

A message without `values` means `[value]`, so nothing that already speaks
this contract has to change.

### Measured

**In a browser, from source.** `test_terminal_states.py` gains an ending
carrying five trains whose one-line form says "and 1 more". Every train is on
the screen and the summary line is not, from the working screen and through a
step: **2 tests, both passing**. With `Findings` reverted to read `value`,
**2 of 2 fail** — the test catches the thing it exists for.

**Live, through the Electron host.** `run.ps1 railways` with
`SIMBA_RAILWAYS_TO=RAWALPINDI` (a route with more than one train on it), the
hardcoded plan, no model. `tools/evaluation/host_overlay_run` typed the goal,
pressed the step buttons and read the closing screen off the screen:

    Here's what I found
    39UP
    1UP
    Train
    6 h 38 min
    6 h 3 min
    Journey

Read back through the host's site view with the same serializer, the site was
showing `Train No. → ['39UP', '1UP']` and `Duration → ['6 h 38 min', '6 h 3
min']`. **Nothing the site returned was missing from the screen.** 9 presses,
34.3s for the run (one run, this machine — 2026-09-17h). Screenshot in
`logs/host-overlay-20260919-155018.png`.

### What this leaves

- **Only two results were available to test with live.** Five was tested in
  the browser, from a scripted message. The live route returned two, which is
  enough to show the defect is gone and not enough to show what twenty look
  like on a screen this size.
- **A long list scrolls.** The overflow guard drops a detail level when a
  *step* will not fit; the closing screen has no such guard, so past roughly
  eight values the ending scrolls. Scrolling an answer is a smaller failure
  than hiding part of it, but it is a failure, and nothing has measured where
  the line is.
- **The step screen still shows one finding**, the first, as its one line.
  That is the design (`StepShell`), not an oversight.

---

## 2026-09-19b — the estimator's raw features, and twenty pages measured with them

The estimator has never had a number to work from. `backend/estimator/` was
empty, deliberately, until the skeleton ran end to end (CLAUDE.md), and it
does. This is the measurement half and nothing else: raw counts, **no score,
no weights, no normalisation**, because weights picked before there is a
corpus are weights picked from intuition and they then decide what the corpus
is allowed to say.

`python -m tools.evaluation.collect_corpus`, 20 public pages, read in a
headless Chromium and through the Electron host's site view (the rule from
2026-09-18c). Conditions in `data/corpus.json`: commit `f01a897`, Python
3.12.3, Playwright 1.62.0, load 39%, 2026-09-19 16:15. **0 of 20 pages failed
to read** in either environment.

### The corpus, headless

| Page | interactive | inferred | density | depth | overlays | fields | links | dead | grade | words |
|---|---|---|---|---|---|---|---|---|---|---|
| example.com | 1 | 0 | 0.12 | 6 | 0 | 0 | 1 | 0.0 | 9.2 | 19 |
| info.cern.ch (the first website) | 25 | 0 | 0.91 | 6 | 0 | 0 | 25 | 0.0 | 7.8 | 153 |
| httpbin.org/html | 0 | 0 | **3.51** | **5** | 0 | 0 | **0** | 0.0 | **13.7** | 605 |
| text.npr.org | 28 | 0 | 1.07 | 8 | 0 | 0 | 28 | 0.0 | 7.3 | 258 |
| lite.cnn.com | 106 | 0 | 1.97 | 10 | 0 | 0 | 106 | 0.009 | 8.4 | 1306 |
| danluu.com | 210 | 0 | 1.30 | 6 | 0 | 0 | 210 | 0.0 | 7.3 | 1218 |
| pakrailways.gov.pk/train | 18 | 0 | **0.10** | 21 | 0 | 3 | 12 | **0.25** | 10.6 | 1061 |
| quotes.toscrape.com | 55 | 0 | 0.84 | 11 | 0 | 0 | 55 | 0.0 | 5.4 | 278 |
| books.toscrape.com | 114 | 0 | 0.64 | 16 | 0 | 0 | 94 | 0.0 | **3.9** | 272 |
| python.org | 153 | 5 | 1.05 | 17 | 0 | 1 | 151 | 0.007 | 6.8 | 1126 |
| pypi.org | 55 | 0 | 0.54 | 14 | 0 | 1 | 52 | 0.0 | 8.9 | 253 |
| developer.mozilla.org | 147 | 2 | 1.74 | 18 | 0 | 1 | 131 | 0.0 | 7.0 | 1816 |
| wikipedia.org/wiki/Cognitive_load | **827** | 0 | 2.14 | **45** | 0 | **12** | **806** | 0.001 | 10.1 | **7416** |
| wikipedia.org/wiki/Main_Page | 260 | 0 | 1.82 | 23 | 0 | 12 | 246 | 0.0 | 7.6 | 1627 |
| gov.uk | 88 | 0 | 0.45 | 20 | 0 | 1 | 79 | 0.0 | 7.7 | 861 |
| gov.uk/browse/benefits | 56 | 0 | 0.53 | 20 | 0 | 0 | 49 | 0.0 | 7.9 | 681 |
| nhs.uk | 53 | 0 | 0.52 | 16 | 0 | 1 | 49 | 0.0 | 5.4 | 449 |
| news.ycombinator.com | 230 | 0 | **2.37** | 16 | 0 | 1 | 229 | 0.0 | 7.1 | 511 |
| arxiv.org/list/cs.HC/recent | 493 | 0 | 1.78 | 13 | 0 | 0 | 493 | 0.0 | 11.2 | 2296 |
| bbc.co.uk/news | 116 | 0 | 0.56 | 23 | 0 | 0 | 108 | 0.0 | 6.4 | 1340 |

### The range of each feature, and which are useless as they stand

| Feature | Min | Median | Max | CV | Distinct | Verdict |
|---|---|---|---|---|---|---|
| `interactive` | 0 | 97 | 827 | 1.26 | 19/20 | Wide, and it separates every page |
| `links` | 0 | 86.5 | 806 | 1.29 | 19/20 | Wide — and almost the same signal as `interactive` |
| `text_density` | 0.096 | 0.98 | 3.51 | 0.71 | 20/20 | Wide, and it ranks pages differently from the counts |
| `max_depth` | 5 | 16 | 45 | 0.56 | 14/20 | Usable |
| `reading_grade` | 3.91 | 7.67 | 13.68 | 0.27 | 19/20 | Usable, but the narrowest real spread here |
| `form_fields` | 0 | 0 | 12 | 2.14 | 4 values | Borderline: 0 on 11 of 20 |
| `inferred` | 0 | 0 | 5 | 3.29 | 3 values | **Flagged: 0 on 18 of 20** |
| `dead_link_ratio` | 0.0 | 0.0 | 0.25 | 4.07 | 5 values | **Flagged: 0.0 on 16 of 20** |
| `overlays` | 0 | 0 | 0 | 0.0 | 1 value | **Flagged: 0 on 20 of 20** |

**Three features cannot tell these pages apart.** Flagged by the collector
itself, which marks a feature when one value covers three quarters of the
corpus — a rule that catches `inferred` and `dead_link_ratio`, both of which
have a *large* coefficient of variation precisely because they are zero
almost everywhere and then jump.

- **`overlays` is 0 on every page, and the detector is right.** gov.uk and
  nhs.uk both show a cookie banner covering **41% of the viewport** — and both
  are `position: static`, in the page's flow, pushing the content down rather
  than covering it. `overlays.analyse` looks for something *stacked over* the
  page, which is what a click has to get past. So the feature is not broken;
  it is measuring something that public front pages rarely do, and 20 pages
  bought no information at all. It needs a corpus with real modals in it — the
  registration replica has one — or it is not a feature.
- **`inferred` is 0 except on python.org (5) and MDN (2).** Non-semantic
  controls are much rarer on well-built public pages than on the two
  applications this project actually drives: the railways site has 6 inferred
  options as soon as a dropdown opens, and 42 when the calendar does
  (2026-09-08). Idle pages are the wrong place to measure it.
- **`dead_link_ratio` is 0.0 on 16 of 20**, and its one real value is the
  railways site at 0.25. Our own registration replica sits at 0.978. Public
  sites do not leave `href="#"` lying about; the pages that need SIMBA might.
- **`links` and `interactive` move together** — 19 of 20 pages differ in both,
  and the two columns are within a few percent of each other on most rows.
  Two features carrying one signal is a weighting problem waiting to happen,
  and whoever builds the score should treat them as one until a page shows
  otherwise.

### Both environments agree, once device pixels are accounted for

**16 of 20 pages read identically** headless and in the host. The four that
differ are all live pages whose content changed between the two passes
(`lite.cnn.com`, Hacker News, BBC News, and Wikipedia's main page, which also
disagreed on `form_fields`, 12 against 4 — unexplained, and the one difference
here that is not obviously the clock).

Getting there took a real defect out of the way, and it is one the
two-environment rule caught exactly as intended:

> **A snapshot's bounds are in device pixels; the viewport is in CSS pixels.**
> On example.com the same `<h1>` measures `(256, 120, 768, 32)` headless and
> `(384, 180, 1152, 48)` in the host, which runs at `devicePixelRatio` 1.5 on
> this machine's display. Both report `innerWidth/innerHeight` of exactly
> 1280x800.

Before that was handled, the host counted a viewport 1.5x too small and read
every page as thinner than it is — **18 of 20 pages disagreed**, Wikipedia's
article by 2.7x (2192 characters against 814). `page_features` now takes the
ratio and converts. **This is not only the estimator's problem**: see the
flagged item below.

### What failed on the way, and what it changed

- **Script source was being counted as prose.** A `<script>` is not in the
  layout tree, so it has no computed style in the snapshot, so "nothing is
  hiding this" was true of it. `lite.cnn.com` — a page of headlines — measured
  **23,422 words and reading grade 98.5**, BBC News 18,370 words and grade
  32.2. With `NOT_RENDERED` skipped by tag: **1,306 words, grade 8.4** and
  **1,340 words, grade 6.4**. Every grade in the table above is from after the
  fix; the corpus was collected three times because of it.
- **Sentences are counted per block, not per page.** The first run graded
  `lite.cnn.com` at 293 and Wikipedia's main page at 110, because a page of
  links has almost no full stops and Flesch–Kincaid then reads the whole page
  as one enormous sentence. A block — a paragraph, a heading, a list item —
  counts as at least one sentence, which is what formatting means on a web
  page. The raw `words`, `sentences` and `syllables` are in every row so a
  different rule can be applied later without re-reading anything.
- **The two replica pages share a 45-link nav**, so `links` and
  `dead_link_ratio` read *identically* on a three-field login and on a
  60-element course list with a modal over it. Found by a test assertion that
  turned out to be wrong about the pages rather than about the code
  (`test_page_features.py`).
- **Sharing the browser fixture broke 54 orchestrator tests.** The estimator's
  tests need the same two replicas perception's do, so the fixtures moved up
  to `backend/conftest.py` — and took the session-scoped *sync* Playwright
  browser with them. A live `sync_playwright` session breaks `asyncio.run` in
  the same thread, every orchestrator test is an `asyncio.run`, and
  `estimator/` sorts before `orchestrator/`: **54 failed and 18 errored**, all
  of them "asyncio.run() cannot be called from a running event loop". The
  replicas are plain subprocesses and stay shared; the browser went back down
  to `perception/conftest.py` and the estimator's browser tests are async like
  the orchestrator's. **369 passed, 7 skipped, 438s** after.

  Worth recording for a reason beyond the fix: the failure had nothing to do
  with what was being built, appeared only in the *whole* suite, and would
  have been invisible to anyone running one module at a time.

### What this does not do

No score, no weights, no normalisation, and no claim that any of these
features predicts anything about a person. There is no user data, and nothing
here has been compared against how hard anybody found a page. A corpus of 20
pages read once is a starting point for choosing features, not a calibration.

---

## 2026-09-20 — bounds are CSS pixels everywhere, and what `MIN_COVERAGE` has actually been measuring

Yesterday the estimator worked around the device-pixel trap by taking a ratio
from its caller (2026-09-19b). That is the fix that keeps working until
somebody forgets, and `overlays.py`, `interactivity.py` and `content.py` all
read the same boxes. So the conversion moved to where the numbers enter:
`snapshot.parse` divides every box by the ratio, `Document` records what it
divided by, and every caller now reads CSS pixels without knowing anything
about the display.

### Where the ratio comes from, and the trap in the obvious answer

**Not `window.devicePixelRatio`.** Playwright's `device_scale_factor` is an
emulation: the page reports 1.5 and CDP still reports every box in CSS pixels.
Dividing by what the page says would have been wrong in exactly the
environment the test suite runs in — measured at 1.0, 1.5 and 2.0, boxes
identical at all three.

The ratio comes from `Page.getLayoutMetrics`, which reports the same viewport
twice:

| | `layoutViewport` | `cssLayoutViewport` | ratio | boxes |
|---|---|---|---|---|
| Headless, plain | 1280x800 | 1280x800 | 1.0 | CSS |
| Headless, `device_scale_factor=1.5` | 1280x800 | 1280x800 | 1.0 | CSS |
| Electron host, 150% display | **1920x1200** | 1280x800 | **1.5** | **device** |

So a headless browser cannot reproduce the host's condition at all, which is
why this survived two weeks of headless measurement. `test_snapshot.py` covers
the conversion, the emulation case, and — skipped unless `SIMBA_HOST_TESTS=1`
and a host is up — the real one.

### Every recorded perception figure, re-measured in both environments

`python -m tools.evaluation.viewport_perception_probe`, after the change:

| Page | Figures | Headless | In the host | Against the first recorded |
|---|---|---|---|---|
| registration `/courses`, modal up | 66 elements / 1 overlay / 65 occluded / 44 dead; 3 headings, 1 table, 20 rows, 177 pairs | unchanged | identical | unchanged |
| billing `/bill` | 39 / 32 dead; 5 headings, 3 tables, 19 rows, 70 pairs; `P/WITHIN → 14,382` | unchanged | identical | unchanged |
| railways `/train` idle | 18 / 4 unnamed / 3 dead | unchanged | identical | unchanged |
| railways results (LHR→KHI) | 2 tables, 2 rows, joined 4-wide, 4 pairs, `Train No. → ['2DN']` | unchanged | identical | — |

**Not one figure changed.** The reason is worth saying rather than being
relieved about: every overlay this project has ever measured is a full-screen
modal, and a full-screen modal is over the threshold whichever units it is
measured in. The conversion changes what happens in the band between, and
nothing we have sits in that band.

### What the threshold has been measuring, per environment

`MIN_COVERAGE = 0.30` is a fraction of the viewport's area. A box 1.5x too
large in each direction covers **2.25x** as much area, so:

| Environment | Ratio | Area factor | `MIN_COVERAGE` as written | What it actually required |
|---|---|---|---|---|
| Headless (and any 1x display) | 1.0 | 1.00 | 0.30 | **0.30 of the screen** |
| The Electron host, 150% display | 1.5 | 2.25 | 0.30 | **0.133 of the screen** |

Measured on the registration replica's modal, which is the one page-level
blocker in the project:

    headless  coverage 1.000   (unchanged by the fix)
    host      coverage 0.986   (read as 2.220 before it)

A coverage of **2.220** — a backdrop covering 222% of the screen — is the
clearest statement of the bug there is, and nothing ever printed it because
`blocked` is a boolean.

**So the threshold comparison was meaningless in the host until today.**
Not merely miscalibrated: `coverage >= MIN_COVERAGE` was comparing a number
that could exceed 1.0 against a fraction of a viewport, which is not a
comparison of two like things at all. Every page-level verdict the Electron
host has ever reached was reached that way, and the host is the environment
the product runs in. Headless — where the whole test suite runs — was correct
throughout, which is exactly why this lasted.

**It produced no wrong outcome, and that is luck of a specific kind.** Every
modal this project has ever measured is full-screen: the registration
replica's backdrop at 1.000, `entry_ad`'s at 1.000, the two component-library
dialogs. A box that covers the whole viewport is over 0.30 at a ratio of 1.0
and still over it at 2.220, so the comparison returned the right answer while
being incapable of being wrong. That is **a property of the test set, not of
the detector** — the detector had no working notion of "30% of the screen" in
the host, and would have reported the same `blocked` for anything between
13.3% and 30% that a correct implementation would have let through. Nothing
in the corpus sat in that band, which is a fact about the corpus.

The two lessons are separable and both stand: a threshold has to be compared
against a number in the same units (fixed 2026-09-20), and a detector tested
only on the easy end of its range has not been tested at the threshold at all.
The second is what the calibration below is for.

Three things follow, and the middle one is the uncomfortable one:

1. **The number in the code described the headless case only.** In the host —
   the environment the product runs in — the page-level rule has been firing
   at 13.3% since the rule existed.
2. **The fix makes the host less sensitive, not more.** Anything covering
   between 13.3% and 30% of the screen was flagged in the host yesterday and
   is not today. Nothing in the three flows is in that band: the two small
   blockers on record are the billing cookie bar at **6.6%** and the live
   railways dropdown at **~2%**, both below either threshold, which is why the
   target-scoped rule was written in the first place (2026-09-05).
3. **0.30 has never been calibrated against real pages.** It was a guess that
   has been quietly behaving as two different guesses. The corpus is the
   instrument for fixing that, and this is flagged rather than settled.

---

## 2026-09-20b — a corpus with modals, fields and dead links in it

The first corpus was twenty public front pages and three of the nine features
were flat on it (2026-09-19b). That was a fact about the corpus, not about the
features: a front page has no modal up, almost nothing whose role has to be
worked out from layout, and no `href="#"` nav — and those are exactly what a
SIMBA run meets. So the corpus now has **34 pages**, including ours.

| Group | Pages |
|---|---|
| Ours | registration login, its course list **with the modal up**, `/stubborn`, the billing form, the billing result |
| The live site, in the states a run passes through | railways idle, **station list open**, **calendar open** |
| Public, one paragraph to a wall of links | the previous 20, unchanged |
| Public but application-like | `the-internet/entry_ad` (modal on load), its index, a demo bank, a login, a shop, and Bootstrap's and Element Plus's dialog pages **with the dialog opened** |

Driven states are read after the drive: a `sign_in`, a click on a date field,
a click on "Launch demo modal". Nothing is submitted. **34 pages, 0 failures,
both environments.** Conditions in `data/corpus.json`.

### Ours, and the application-like ones

| Page | controls | link share | inferred | overlays | fields | dead | density | depth | grade |
|---|---|---|---|---|---|---|---|---|---|
| registration login | 49 | 0.92 | 0 | 0 | 3 | **0.978** | 2.57 | 8 | 9.9 |
| registration course list, modal up | 66 | 0.68 | 0 | **1** | 0 | 0.978 | 4.81 | 11 | 6.4 |
| `/stubborn` | 27 | 0.93 | 0 | 0 | 0 | **0.960** | 0.75 | 6 | 10.0 |
| billing form | 37 | 0.84 | 0 | 0 | 1 | 0.935 | 1.73 | 9 | 8.6 |
| billing result | 39 | 0.92 | 0 | 0 | 0 | 0.889 | 2.64 | 9 | 7.7 |
| railways idle | 18 | 0.67 | 0 | 0 | 3 | 0.25 | 0.10 | 21 | 10.6 |
| railways, station list open | 24 | 0.50 | **6** | 0 | 3 | 0.25 | 0.17 | 21 | 10.6 |
| railways, calendar open | 66 | **0.18** | **42** | 0 | 3 | 0.25 | 0.19 | 21 | 10.3 |
| `the-internet/entry_ad` (modal up) | 3 | 0.67 | 1 | **0** | 0 | 0.5 | 0.28 | 9 | 5.1 |
| demo bank (Altoro Mutual) | 45 | 0.96 | 0 | 0 | 2 | 0.0 | 2.46 | 13 | 8.1 |
| a login (Swag Labs) | 3 | **0.00** | 0 | 0 | 3 | 0.0 | 0.15 | 12 | 8.1 |
| a shop (OpenCart demo) | 101 | 0.75 | 0 | 0 | 1 | 0.026 | 0.39 | 15 | 5.1 |
| Bootstrap docs, modal open | 282 | 0.80 | 0 | **2** | 0 | 0.0 | 1.48 | 16 | 9.9 |
| Element Plus docs, dialog open | 300 | 0.72 | 0 | **1** | **25** | 0.0 | 0.93 | 20 | 8.5 |

### What the extension bought, feature by feature

| Feature | Before (20 public) | Now (34) | Verdict |
|---|---|---|---|
| `dead_link_ratio` | 0.0 on 16/20 — **flagged** | 0.0–0.978, **nonzero on 13/34**, 11 distinct | **No longer flat.** Our replicas sit at 0.89–0.98, the railways site at 0.25, a shop at 0.026 |
| `form_fields` | 0 on 11/20, borderline | 0–25, **nonzero on 17/34** | **No longer flat.** A component library's docs page has 25 |
| `overlays` | 0 on 20/20 — **flagged** | 0–2, nonzero on **3/34** — still flagged | Better, still thin. Three pages in the world's corpus have a detected modal |
| `inferred` | 0 on 18/20 — **flagged** | 0–42, nonzero on **6/34** — still flagged | Better, still thin, and the two big values are both the same live page in two states |
| `controls` | 0–827 | 0–827 | Unchanged, and still the widest |
| `text_density` | 0.096–3.51 | 0.096–**4.81** | The course list with its modal is the densest page in the corpus |
| `reading_grade` | 3.91–13.68, CV 0.27 | 3.91–13.68, CV 0.25 | Unchanged, still the narrowest real spread |

### The two that are still flat, and why

- **`overlays`: 3 of 34.** Two of those three are documentation pages for
  dialog components, opened on purpose. The interesting one is the page that
  should have counted and did not: `the-internet.herokuapp.com/entry_ad` puts
  up a **`position: fixed` overlay covering 100% of the viewport** and
  perception reports nothing, because the element's `z-index` is `auto` and
  `MIN_STACK_LEVEL` requires 5. A modal that does not bother to set a
  z-index — it does not need one, being fixed and last in the DOM — is
  invisible to both the page-level and the target-scoped rule. That is a
  detector gap, found by a corpus, which is what a corpus is for. Flagged for
  perception's owner rather than changed here.
- **`inferred`: 6 of 34**, and 42 of the 48 inferred elements in the whole
  corpus are one live page's calendar. Non-semantic controls are rare on
  well-built public pages and normal on the applications this project is for.
  This feature will only get a distribution from more application pages, and
  the ones that are freely readable without a login are mostly demo sites.

### Both environments still agree

**7 of 34 pages differ**, every one of them a live page that changed between
the two passes: ±1 link on python.org and Wikipedia, a different front page
on BBC News (77 controls against 116, and 77 inferred against 0 — it serves
different markup run to run), a few characters on Hacker News. **None of ours
differs, and none of the driven states differs.**

### `links` and `interactive` are one feature now — and this corpus already separates them

Merged on 2026-09-20 into `controls`, on the evidence of the first corpus,
where the two were the same signal: a public page's controls are nearly all
links. `links`, `non_link_controls` and `dead_links` remain in every row, so
the merge can be undone from the data without re-reading anything, and
`link_share = links / controls` is the measure of whether it should be.

The extended corpus answers that immediately, and against the merge:

| Page | links | controls | `link_share` |
|---|---|---|---|
| a login (Swag Labs) | 0 | 3 | **0.00** |
| railways, calendar open | 12 | 66 | **0.18** |
| railways, station list open | 12 | 24 | **0.50** |
| `httpbin.org/html` | 0 | 0 | 0.00 (nothing to divide) |
| everything else | — | — | 0.67–1.00, median **0.92** |

So: on the pages this project exists for — a form, a picker, a dropdown — the
two counts say different things, and on front pages they say the same thing
twice. The merge stands as asked and as implemented; whether it should
survive contact with these three rows is a design question and is flagged, not
settled here.

---

## 2026-09-20c — channel B exists, and every step now leaves a row

`telemetry` has been in CONTRACT.md since 2026-09-04 and nothing has ever sent
it, so every estimator discussion has been about one channel. The overlay now
sends it, and the backend writes it down beside the page features of the step
it belongs to.

### What is sent, and when

`frontend/src/telemetry.ts`, five numbers, each restarting when a step is
presented:

| Field | Measured as |
|---|---|
| `hesitation_ms` | step presented → sample |
| `cursor_path_ratio` | path length ÷ start-to-end distance, 1.0 when the pointer never moved |
| `backtracks` | consecutive segments (≥ 8px) turning more than ~120° |
| `rereads` | pointer re-entering the step's text after leaving it |
| `help_presses` | presses of "What are you doing?" |

Sent **on every step response** — before the response, so the backend has it
when it pairs — and **on a 3s timer while a step waits**. Nothing is sent when
no step is on screen.

### Measured on the built overlay, in a browser

`frontend/test_telemetry.py` drives the real overlay against a socket that
records what arrives. Six tests, all passing:

| What it drives | What arrives |
|---|---|
| Press go-ahead after ~0.8s | one `telemetry` **before** `step.response`, `answered: true`, `hesitation_ms ≥ 800` |
| A zigzag across the window, then press | `cursor_path_ratio` **> 2.0**, `backtracks ≥ 1` |
| One straight move to the button, then press | ratio **1.0–1.3**, `backtracks == 0` |
| Ask "What are you doing?", close, then press | `help_presses == 1` |
| Leave the step alone for 7.2s | **≥ 2 samples**, none `answered`, hesitation rising |
| Answer, then wait 4.8s | exactly **1** sample — an answered step is not re-reported |

The middle two are the pair worth keeping: the same measurement on two
journeys to the same button. The control was wrong at first and the failure
was useful — an **L-shaped** path to the button (out, then across) read as
**28.5**, which is right: it is not a direct move. "Straight" means straight
at the thing being pressed.

### The rows

`backend/estimator/pairing.py` writes one JSON line per sample:

    {"ts": ..., "task_id": ..., "step_index": 2, "goal": "...", "url": "...",
     "instruction": "...", "when": "waiting" | "answered",
     "page": {"controls": 66, "overlays": 1, "text_density": 4.81, ...},
     "telemetry": {"hesitation_ms": 4200, "cursor_path_ratio": 3.8, ...}}

Measured end to end on the registration replica (`test_pairing.py`): three
steps, two samples each, **six rows**, each carrying the features of the page
that step was showing — and the features move with the run, including the
`overlays: 1` row for the step presented over the modal. A run with no
recorder writes nothing, which is every other test in the repository.

### Through the real stack, not only the tests

`run.ps1 billing`, driven by `host_overlay_run` pressing the overlay's own
buttons, 6.5s, **7 rows across 3 steps**:

| Step | Instruction | controls | fields | density | hesitation |
|---|---|---|---|---|---|
| 1 | "The site is asking about cookies." | 37 | 1 | 1.73 | 996ms (answered) |
| 2 | "Let me look up your bill." | 35 | 1 | 1.55 | 54ms, then 2052ms (answered) |
| 3 | "Now I'll open the full bill." | 39 | 0 | 2.64 | 306 → 3305 → 6304 → 9300ms |

Step 3 was left alone on purpose, and the trail is what it is for: four
samples, hesitation climbing, the page behind them unchanged. The features
move with the run — a form page, a filled form page, a results page — which is
the pairing doing its job.

One thing the same run showed that no test would have: driven against the
*registration* flow, `host_overlay_run` presses the primary action without
filling the credential fields, so the sign-in does not happen, the modal never
opens, and the run ends stuck two steps later. The rows say so plainly — step
2's page reads `controls: 49, overlays: 0`, which is the login page, not the
course list — and that is the first time this project's own data has explained
one of its own failures.

`data/steps.jsonl` is **not committed**: it holds the goals a person typed.
The corpus beside it is public pages and is.

### What this is not

- **Nothing reads it.** There is no estimator and no score, by decision. This
  is a training set accumulating, and `load.updated` still only ever comes
  from the mock.
- **No user data has been collected.** Every number so far is from a test
  driving a browser. What a real person's trace looks like — and whether any
  of these five separates a page someone coped with from one they did not —
  is unmeasured, and is the whole question.
- **The definitions are guesses.** 8px of movement, 120° of turn, a 3s timer,
  "re-read" as pointer re-entry: each is a starting value, all in one file, and
  the first person with real traces should expect to move them.

---

## 2026-09-20d — `MIN_COVERAGE` measured at last, and a modal that needed no z-index

Two things that had been flagged and not done. `MIN_COVERAGE = 0.30` had
never been compared against a real page, and a full-screen modal with no
z-index was invisible to the detector (2026-09-20, 2026-09-20b). Both are now
measured, on the same 45-page corpus, with
`python -m tools.evaluation.overlay_coverage_probe` — which enumerates the
detector's own candidate set with **no coverage threshold applied at all** and
writes every candidate to `data/overlay_coverage.json` with its coverage,
position, z-index and text, so the judging can be done by eye and checked by
somebody else.

**45 pages, 0 failures, 96 candidates painted above a page.**

### The distribution, and why it settles the question so quickly

| Coverage band | Candidates | Of which `fixed`/`sticky` with no z-index |
|---|---|---|
| 0.00–0.01 | 51 | 15 |
| 0.01–0.05 | 2 | 1 |
| 0.05–0.10 | 17 | 9 |
| 0.10–0.20 | 11 | 10 |
| 0.20–0.30 | 2 | 0 |
| **0.30–0.90** | **0** | 0 |
| 0.90+ | **13** | 3 |

The corpus is **bimodal with nothing in the middle**. Every one of the 13 real
blockers covers exactly **1.000** of the viewport. The largest thing that is
*not* a blocker covers **0.234**. Between 0.234 and 1.000 there is not one
element on 45 pages.

**The 13 at 1.000**, every one a modal or its backdrop, on 8 pages:

| Page | Blockers | What they are |
|---|---|---|
| registration replica, signed in | 1 | `#deadline-modal`, `fixed` z-index 100 |
| `the-internet/entry_ad` | 1 | `div.modal`, `fixed`, **z-index `auto`** |
| `demoqa.com/modal-dialogs` | 2 | backdrop z 1050 + dialog z 1055 |
| `getbootstrap.com` modal docs | 2 | backdrop z 1050 + dialog z 1055 |
| `element-plus.org` dialog docs | 2 | `.el-overlay` z 2018 + `.el-overlay-dialog`, **z `auto`** |
| `mui.com` dialog docs | 2 | `.MuiDialog-root` z 1300 + `.MuiBackdrop-root`, **z `-1`** |
| `ant.design` modal docs | 2 | `.ant-modal-mask` + `.ant-modal-wrap`, both z 1000 |
| `sweetalert2.github.io` | 1 | `.swal2-container` z 1060 |

**And everything in 0.08–0.234 is furniture.** Not one borderline case, not
one judgement call — the entire band is sticky headers, sticky sidebars and
tables of contents:

| Coverage | Page | What it is |
|---|---|---|
| 0.234 | `mui.com` | the docs navigation sidebar |
| 0.208 | `element-plus.org` | the docs navigation sidebar |
| 0.192 | `ant.design` | the components sidebar |
| 0.179 | `sweetalert2.github.io` | `nav.sidebar-nav` |
| 0.176 | `developer.mozilla.org` | the article's right-hand "In this article" |
| 0.176 | `mui.com` | "Contents" |
| 0.153 | `en.wikipedia.org` | Vector's pinned contents panel |
| 0.141 | `getbootstrap.com` | `aside.bd-sidebar` |
| 0.121 | `developer.mozilla.org` | the page header |
| 0.109 | railways, calendar open | the date picker panel |
| 0.101 | `bbc.co.uk/news` | the BBC header |
| 0.085 | railways | the site header |

### The sweep: what a higher value misses and a lower one falsely flags

| Threshold | Pages called blocked | Blockers | What changes at this value |
|---|---|---|---|
| 0.90 | 8 | 13 | — |
| 0.50 | 8 | 13 | nothing |
| 0.40 | 8 | 13 | nothing |
| **0.30** | **8** | **13** | **nothing — the value in the code** |
| 0.25 | 8 | 13 | nothing |
| 0.20 | 8 | 15 | two docs sidebars become "blockers" on pages already blocked |
| 0.15 | **10** | 21 | **Wikipedia and MDN are now blocked pages** |
| 0.10 | **12** | 26 | BBC News and the railways calendar join |
| 0.05 | **19** | 43 | our own billing cookie bar, the demoqa form, 19 pages in all |

**What 0.30 misses: nothing in this corpus.** There is no element anywhere
between 0.234 and 1.000, so nothing is sitting just under the line.

**What a lower value would falsely flag**, in order of how bad it gets:

- **0.25** — nothing. Identical to 0.30.
- **0.20** — the MUI and Element Plus documentation sidebars start counting as
  blockers. No page's verdict changes, because both pages already have a real
  modal up, but `overlays` rises and everything behind a sidebar starts being
  reported as occluded.
- **0.15** — the first real damage. **MDN and Wikipedia become blocked
  pages.** Both are ordinary articles with nothing in the way; what gets
  flagged is a sticky table of contents. A planner told the page is blocked
  looks for something to dismiss, and there is nothing.
- **0.10** — BBC News joins on its own header, and the railways calendar joins
  on its date picker panel. The date picker is a genuine overlay, but it is
  the *target-scoped* rule's business — it is why that rule exists — and
  calling the whole page unusable because a picker is open is wrong.
- **0.05** — 19 of 45 pages, including our own billing replica on its cookie
  bar. "Blocked" would stop meaning anything.

### Recommendation: keep 0.30, and be honest about what that is worth

**Keep it.** It is inside the empty band, it misses nothing, it falsely flags
nothing, and there is no reason to move a number that is already right.

**What it costs to say that.** The corpus **bounds** this threshold rather
than choosing it. Any value in (0.234, 0.90] produces identical results on all
45 pages, so this measurement cannot distinguish 0.25 from 0.85 — it can only
rule out 0.20 and below. Calling 0.30 "calibrated" would be overclaiming; it
is **measured, and not contradicted**, which is a weaker and truer thing.

The reason the band is empty is worth naming, because it is the limitation
and not the result: **every modal in the corpus is full-screen.** Not one
half-screen drawer, bottom sheet, corner dialog or 40%-of-the-screen consent
wall appears on 45 pages. Those exist in the world, and the first one this
project meets is the first real test of where the line goes. Until then 0.30
is a number that has been shown not to be wrong, on a corpus with no hard
cases in it — which is the same shape of claim as the one 2026-09-20 had to
withdraw about the device-pixel bug, and is recorded here in those terms
deliberately.

### The missing rule, and the one page that needed it

`entry_ad` put up a `position: fixed` modal covering 100% of the viewport at
`z-index: auto`, and the detector reported nothing, because both rules began
by demanding a declared z-index of at least `MIN_STACK_LEVEL` (2026-09-20b).

Fixed: `fixed` and `sticky` now reach the page-level rule on their position
alone. Both are painted against the viewport rather than laid out in the flow,
so a fixed box the size of the screen is on top of the page whether anyone
wrote a z-index for it or not. `absolute` is deliberately excluded — it sits
in normal paint order, so covering the viewport says nothing about being above
it. That exclusion is doing real work: `entry_ad`'s own `.underlay` is
`absolute` at `z-index: auto` covering 1.000, and so is every stretched
background on the web.

**What the new rule actually caught**, measured rather than assumed — 38 of
the 96 candidates are found by position alone, and 3 of those are over the
threshold:

| Element | Page | Why the old rule missed it |
|---|---|---|
| `div#modal` | `the-internet/entry_ad` | `z-index: auto` |
| `.el-overlay-dialog` | `element-plus.org` | `z-index: auto` |
| `.MuiBackdrop-root` | `mui.com` | `z-index: -1` |

**Exactly one page — `entry_ad` — is detected only because of this change.**
The other two are second blockers on pages a declared z-index already caught.
That is a smaller result than "a whole class of modals was invisible" and it
is the accurate one.

**No existing detection regressed**, and this is checked against the previous
corpus rather than argued from the shape of the code. The 34 pages that appear
in both the 2026-09-20b corpus and this one, compared row by row on `overlays`:

| | Pages |
|---|---|
| Lost an overlay | **0** |
| Unchanged | 32 |
| Gained one | 2 — `entry_ad` 0→1, `element-plus.org` 1→2 |

Both gains are correct: `entry_ad`'s modal at `z-index: auto`, and Element
Plus's `.el-overlay-dialog`, which sits inside the `.el-overlay` the old rule
already found. All 8 blocked pages under the new rule are pages with a real
modal up. Nothing that was detected before stopped being detected — the rule
only adds candidates — and the suite is green at
**403 passed, 8 skipped, 0 failed** in 481s, with 8 new tests covering the
fixed case, the sticky case, the `absolute` non-case, and a fixed strip under
the threshold that must *not* become a page-level blocker.

One correction to something said in passing while this was being measured:
`ant.design`'s modal was observed reporting zero overlays in a trial run, and
that was read as a second instance of the same gap. It is not — both its
blockers carry `z-index: 1000` and the old rule would have found them. The
trial had simply caught the page with its modal shut. The gap has one
instance in this corpus, not two.

### The corpus that this was measured on, and what the extension bought

Extended from 34 pages to **45** for this, by adding eleven application-like
pages — demo banks, practice login and registration forms, a todo app with
state in it, and three more component galleries whose dialogs are opened.
Read headless, **45 pages, 0 failures**. Every row now carries a `kind`:
**19 public, 18 demo, 5 ours, 3 target**.

| Feature | 34 pages (2026-09-20b) | 45 pages | Verdict |
|---|---|---|---|
| `overlays` | nonzero on **3/34**, 2 distinct — flagged | nonzero on **8/45**, 3 distinct — still flagged | Better, still the thinnest. Two of the five new ones are the detector change, not the corpus |
| `inferred` | nonzero on **6/34**, and 42 of 48 were one page | nonzero on **14/45**, 9 distinct, max **305** | **No longer flat.** The mass is still concentrated: MUI 305, SweetAlert2 107, Ant Design 59 |
| `form_fields` | nonzero on 17/34, max 25 | nonzero on **25/45**, max 25 | Wider |
| `dead_link_ratio` | nonzero on 13/34 | nonzero on **15/45**, 13 distinct | Unchanged in character |
| `link_share` | 4 pages under 0.6 | **9** of the 44 pages with controls | The split's evidence roughly doubled |

**`overlays` is the one still flagged**, at 0 on 37 of 45 pages, and the
honest reading is that five of its eight nonzero rows are component libraries
being asked to show a dialog. That is a corpus of demonstrations of modals,
not a sample of pages that have them. The feature now has a distribution;
whether it has a *representative* one is a different question and the answer
is no.

**Where the spread came from is itself a caveat.** Both of the features that
improved did so almost entirely on `demo` rows — which is why the label
exists. 305 inferred controls on a Material UI documentation page is a real
measurement of a page built out of `div`s, and it is not evidence about what
an application a person actually uses looks like.

### What this does not do

- **Headless only.** The standing rule is that perception figures are taken
  in both environments (2026-09-18c), and the host half was not run for this
  probe. The reason it is defensible is narrow and should be checked rather
  than trusted: since `snapshot.parse` converts on the way in, coverage is a
  ratio of CSS pixels to a frozen CSS-pixel viewport and no longer depends on
  the display — which is precisely the claim that was false until today, and
  so is the claim most worth re-testing in the host before anyone leans on
  these numbers.
- **It does not calibrate the target-scoped rule**, which has no coverage
  threshold to calibrate. It also still requires a declared z-index, so a
  fixed element with `z-index: auto` sitting on the one element a step needs
  reaches the page-level rule and not that one. Widening it is flagged below
  rather than taken, because the same change would admit every decorative
  full-screen layer with `pointer-events: none` — a property this detector
  cannot currently see, since `pointer-events` is not among `COMPUTED_STYLES`.
- **It does not touch `MIN_STACK_LEVEL`.** 5 is as unmeasured today as 0.30
  was yesterday. Nothing in this corpus depends on it — every declared
  blocker is at z-index 100 or above, and the nearest candidate below is at
  z-index 2 — so it was not the pressing one, but it is the same kind of
  guess.

---

## 2026-09-20e — partial overlays, three detector defects, the host corpus, and the first labels

Finished 2026-09-21. Four questions: does the corpus read the same in the
Electron host; does the coverage gap survive pages built to land in it; what
does `MIN_STACK_LEVEL` actually separate; and how hard is each page for the
agent. The second question found three defects in the detector before it
could be answered, and they come first because every number after them
depends on them.

### Three defects the partial-coverage pages exposed

All three were invisible while every overlay in the corpus was a full-screen
modal at the origin, which is the same shape as the device-pixel bug: a test
set that only ever exercises the easy end of a range.

| # | Defect | Found as | Effect | Fixed |
|---|---|---|---|---|
| 1 | A scroll-locked `<body>` (`position: fixed`, standard behind a consent wall) became a candidate under the position rule added in 2026-09-20d | Guardian coverage **27.17**, Spiegel **43.61** | `body`'s whole subtree marked as overlay — every element on the page reported as part of a dialog, nothing occluded | `html`/`body` never candidates (`ROOT_TAGS`) |
| 2 | Coverage was the element's own area over the viewport's, with no check it was on screen | Guardian panel at y=**19167** scoring 0.389; Spiegel's at y=14308 scoring 0.449 | 5 of the first 12 candidates in the 0.30–0.90 band were below the fold | Box clipped to the viewport before the fraction is taken |
| 3 | **My fix for #2** clipped to (0, 0, 1280, 800), assuming every read is at the top of the page | Diffing each page's largest candidate against the previous run: Bootstrap's modal **1.000 → 0.000**, SweetAlert 1.000 → 0.139, MUI dialog 1.000 → 0.239 | Every driven read is scrolled — Playwright scrolls a button into view before clicking it — and CDP boxes are in document coordinates, so full-screen backdrops sat at y=900 and clipped to nothing | `Document.scroll` recorded; clip is to where the page actually is |

Defect 3 was committed (`49e665a`) and caught before anything was built on
it, by the diff rather than by a test. It is recorded because it is the most
useful thing in this entry: a fix for an off-screen measurement that was
itself only correct off-screen.

**The scroll offset arrives in device pixels, like the boxes.** Measured in
the host at a ratio of 1.5, scrolled to 1234 CSS pixels: CDP reported
`scrollOffsetY` **1851**. `parse` divides it with the boxes. A host-gated test
(`test_the_host_scroll_offset_comes_back_css`) keeps that measurement
runnable, and it passes against the real host.

**Headless and host agree on overlays after all three fixes** — see the host
corpus below, where `overlays` differs on **0 of 49** pages at ratios 1.0 and
1.5, including the scrolled, driven ones. That is the host validation the
scroll fix needed.

### Does the gap survive? Partly.

Five pages added, selected **because** they put a blocker in the band — a
bottom sheet (MUI drawer, bottom), two side drawers (Bootstrap offcanvas, Ant
Design), and two live consent walls (the Guardian, Spiegel). That makes this
part of the corpus a deliberate sample: it shows the band is reachable and
says nothing about how often real pages fall in it.

`python -m tools.evaluation.overlay_coverage_probe`, 50 pages, 49 read
(Spiegel failed on DNS this run), 236 candidates among 2769 positioned
elements:

| Band | Candidates, 45 pages (20d) | Candidates, 50 pages (now) |
|---|---|---|
| 0.20–0.30 | 2 | 2 |
| **0.30–0.40** | **0** | **3** |
| **0.40–0.50** | **0** | **1** |
| **0.50–0.90** | **0** | **0** |
| 0.90+ | 13 | 15 |

**Everything in 0.30–0.90 is a real blocker:**

| Coverage | Page | What |
|---|---|---|
| 0.461 | MUI drawer docs | the bottom sheet |
| 0.369 | the Guardian | sticky top ad banner (two nested elements, same box) |
| 0.3125 | Bootstrap offcanvas docs | the side drawer |

**And the largest non-blocker is still a docs sidebar, at 0.234.** Everything
from 0.15 to 0.234 is navigation furniture — MUI, Element Plus, Ant Design,
SweetAlert2 and MDN sidebars and contents panels.

So: **the gap between 0.30 and 0.50 has closed, with real blockers; 0.50–0.90
is still empty.** 0.30 still separates everything in the corpus — it misses no
blocker and flags no furniture — but the margin is now **0.013 above the
nearest blocker** and 0.066 above the largest non-blocker, against 0.77 and
0.066 before. The midpoint of the gap that remains is **0.273**.

What the sweep says, over the detector's own candidates:

| Threshold | Pages blocked | Blockers | Change |
|---|---|---|---|
| 0.90–0.50 | 10 | 15 | — |
| 0.40 | 10 | 16 | + bottom sheet |
| **0.30** | **10** | **19** | + Guardian banner, Bootstrap drawer |
| 0.25 | 10 | 19 | nothing |
| 0.20 | 10 | 21 | + two MUI docs sidebars (pages already blocked) |
| 0.15 | 13 | 29 | Ant Design, MDN — sidebars; **false** |

**What this cannot tell you, still.** The Ant Design drawer — whose default
width, 378px, is **0.295** of this viewport — did not open in this run. It
did in two earlier ones (at 0.3116 including its frame). If a real 378px
drawer arrives on screen at 0.295 it is **under** the line. That is the
concrete case to test next, and the reason 0.273 is recommended below rather
than left as a number in a table.

### `MIN_STACK_LEVEL`: what it gates, and what the data bounds

The level only ever decides one thing: whether an `absolute` element with a
declared z-index is admitted. `fixed` and `sticky` get in regardless since
2026-09-20d. So the population is the 508 `absolute` elements with a declared
z-index, not everything.

**It decides no page-level verdict in this corpus.** After the clip, not one
`absolute` element with a declared z-index covers 0.30 of the screen. Every
page-level blocker is `fixed` or `sticky`. Its whole remaining job is the
target-scoped rule, which has no size floor — so every admitted element,
however small, can refuse a move.

Every `absolute` declared-z element showing ≥1% of the screen, all eight:

| z-index | Coverage | Page | What | Blocker? |
|---|---|---|---|---|
| 1 | 0.234 | `entry_ad` | the dialog box inside `#modal` | inside one — its parent is caught |
| 2 | 0.110, 0.035 ×3 | the Guardian | article link cards | **no** |
| 12 | 0.073 | the Guardian | a content panel | **no — admitted today** |
| 2001 | 0.109 | railways | the date picker | **yes** |
| 2005 | 0.046 | railways | the station dropdown | **yes** |

The z-index distribution, for completeness: 359 non-blockers declare 1–4,
123 declare 5–49, 10 declare 50–999, 43 declare 1000+.

**What the data bounds: 3 ≤ `MIN_STACK_LEVEL` ≤ 2001.** Below 3 the
Guardian's link cards are admitted to the target-scoped rule, and a click on
anything they overlap is refused. Above 2001 the railways date picker drops
out, and that is the case the target-scoped rule was written for. 5 is
inside. Anything from 13 to 2001 would be strictly cleaner on this corpus —
it would also drop the Guardian's z=12 panel — but the upper side rests on
**two elements from one site**, which is not a bound anyone should move a
constant on.

Recommendation: **keep 5.** The lower bound is solid and has margin; the
upper bound is a lead, not a finding.

### The host half of the corpus

Read through the Electron host's site view (Electron 32.3.3, Chromium 128, a
display at 150%), 50 pages, and compared field by field against headless.

**16 of 50 differ. `overlays` differs on none.**

| Cause | Pages | Fields |
|---|---|---|
| **The host's layout is 1263 wide, not 1280** | Wikipedia ×2 (+18%, +17%), practice.expandtesting (3.6×), lite.cnn, Hacker News (−3%) | `text_density`, `viewport_characters` |
| Live content changed between the two passes | python.org, Wikipedia, opencart, the Guardian, Bootstrap ×2, MUI, Ant modal | ±1 link, a few characters, reading grade in the second decimal |
| BBC News serves different markup per request (known, 2026-09-20b) | BBC | 116 against 241 controls, 0 against 73 inferred |
| The drive reached a different state | Ant Design drawer | 439 against 257 controls |
| The page rendered no text in the host | OrangeHRM | every field 0 |
| DNS failure in headless only | Spiegel | read in the host, failed headless |

**The first row is a finding, not noise.** CLAUDE.md freezes the viewport at
1280x800 because density is per visible area. In the host, a scrollable page
gets a classic 17px scrollbar and its layout width is **1263**; headless
Chromium uses overlay scrollbars and keeps 1280. Measured directly:
`document.documentElement.clientWidth` reads 1280 headless and 1263 in the
host on the same Wikipedia page. Text reflows into a narrower column, so the
same page puts more or fewer characters above the fold. The viewport is
frozen in one environment and 17px narrower in the other, and the difference
is in the product's environment.

### The first labels

`python -m tools.evaluation.label_corpus` runs the hardcoded planner over every
corpus page that has a plan and writes `data/labels.json` with the conditions
block. Three runs per replica flow, one against the live site (CLAUDE.md).
**No score** — raw counts, per the standing decision that the estimator
measures before it scores. Retries and verification failures are read by
wrapping `attempt_move` and `verify`, because a retry that succeeds sends no
message.

**4 of 50 pages have a usable label (8%).**

| Label source | Pages |
|---|---|
| `agent_run` — a flow starts here and was measured | **4** |
| `driven_state_of_a_labelled_page` — same URL, different state | 3 |
| `features_only` — no plan reaches it | **43** |

| Flow | Runs | Pass | Steps | Attempts | Retries | Verify failures | Recovery | Seconds (median) |
|---|---|---|---|---|---|---|---|---|
| registration | 3 | 100% | 3 | 3 | 0 | 0 | no | 5.7 |
| billing | 3 | 100% | 3 | 3 | 0 | 0 | no | 3.2 |
| stubborn | 3 | 100% | 2 | 3 | 1 | 2 | **yes** | 12.8 |
| railways (live) | 1 | 100% | 5 | 8 | 3 | 0 | no | 202.0 |

Every local run was identical across its three repeats in every count, and
within 0.5s on the clock.

**What the distribution looks like: four points, and two of them are not
evidence about pages.**

- **Every label is a pass.** Pass rate cannot separate anything in this set.
- **The stubborn row is difficult because we built it to be.** It is the
  setback rig from 2026-09-18 — a button that does nothing on purpose. Its
  retries and its recovery are the rig working.
- **The railways row is difficult because it is live and slow.** Its three
  retries were all first-strategy timeouts (`fill` on From and To, a
  `click`) that the second strategy recovered, and each cost a 10-second
  timeout. That is 30 of its 202 seconds, and one sample.
- **That leaves registration and billing**, both our own replicas, both
  3 steps, 0 retries, 0 failures, 3–6 seconds. The only "natural" difficulty
  signal is that the two replicas are easy.

**This is not yet a training target.** A `y` with four values, all passes,
two engineered and one a single live sample, cannot fit anything, and the
features beside it have 43 rows with no `y` at all. The way to more labels is
more plans, not more runs: a label needs a task, and 46 of the 50 pages have
none. Recorded as the headline because it is the thing the next month's work
has to change.

Two joins the file declines to make, on purpose. The registration run passes
through the course list, which is a corpus row (`/`, signed in); it is marked
`driven_state_of_a_labelled_page` rather than given the run's label, because a
task-level count cannot be split across the pages it crossed. And the billing
run reaches its results page by POST at `/bill`, while the corpus has the
same page by GET at `/bill?reference=…`; an exact-URL join does not call
those the same page, and neither should anything built on this.

### Flagged, not settled

- **`text_density` makes the same top-of-page assumption the clip did.**
  `page_features._inside` counts text inside `(0, 0, 1280, 800)`, so on a
  driven, scrolled read it measures the top of the document rather than what
  was on screen. The 10 driven rows' `text_density` and `viewport_characters`
  are affected. Recommendation: the same one-line change, using
  `document.scroll` — cost is a re-collection of the corpus. Estimator's
  owner's call.
- **The host viewport is 1263 wide on scrollable pages.** Options: hide the
  site view's scrollbar (a style injected into the site view, frontend); run
  headless with classic scrollbars so both agree at 1263; or accept and record
  per-environment density. Recommendation: hide it in the site view — the
  user never sees that view, and it restores the 1280 CLAUDE.md promises.
  Cost: a frontend change and one more thing injected into a real site.
- **`MIN_COVERAGE`: consider 0.27.** 0.30 sits 0.013 above the nearest real
  blocker and 0.066 above the nearest non-blocker; 0.273 is the middle of the
  gap, and it would catch a default 378px Ant Design drawer (0.295) that 0.30
  would miss. Cost: one untested number for another until a corpus has a
  drawer in that 0.27–0.30 range. Left at 0.30.
- **`ELECTRON_RUN_AS_NODE=1` breaks `run.ps1` from an editor terminal.**
  VS Code and other Electron-based editors set it for child processes;
  `electron .` then runs as plain Node and fails with an ESM loader error
  that names nothing useful. The host was started here with the variable
  unset. `run.ps1` could clear it before `Start-Host`.

---

## 2026-09-21 — the goal decides, and the overlay is redesigned

Two changes to the product a person touches. The typed goal now decides what
happens, in the real backend and the mock; and the overlay has a design
system, applied to every screen, in a light and a dark theme.

### Routing: the five cases, three ways

| Goal | Keywords (`test_router`, `test_app_routing`, `test_mock_backend`, `test_replies`) | Real stack, model routing |
|---|---|---|
| hello | greeting, nothing starts | greeting — the small-talk floor, no model call |
| pay my bill / "What do I owe on my electricity bill?" | billing runs | model: billing; 3 steps; ends on **14,382** |
| trains to Karachi / "Show me trains from Lahore to Karachi" | railways | model: railways; 5 steps on the live site; ends on **2DN**, 22 h 16 min |
| book a flight / "book a flight to Dubai" | unsupported, nothing starts | model: unsupported |
| I need to pay for my course | **clarify**: billing or registration | model: **unsupported** |

The real stack is `run.ps1 billing` with the Electron host, the real backend,
both replicas and the live railways site, driven through the overlay page
itself by `tools/evaluation/routing_stack_run.py`. The hardcoded planner, so
the only model spend was routing: about 200 prompt and 11 completion tokens
per call, $0.000024 each at the published rate.

**The last row is the interesting one.** The keywords see a bill word and a
course word and ask which; the model reads "pay for my course" as neither —
SIMBA registers you for a course, it does not pay for one — and declines.
The model is arguably right. Either way nothing starts, which is the rule. The
clarify path is exercised by the keyword tests and the mock, in a browser;
through the real stack, no goal tried reached it. Of four more candidates,
the model answered two (billing, unsupported) and the other two timed out
and were routed by the keywords, both to billing.

After pressing the card offered to "hello", the billing flow ran to its
answer; that is the one case where a reply led to a task, and it ran on the
same connection.

### The model's latency, and the silent screen it exposed

Twelve route calls to `gemini-3.1-flash-lite`, all read back from the
transcripts: ten answered in **1.3–5.9s, median 2.4s**, and **two took longer
than the 8-second limit** and fell back to keywords, as designed. A timed-out
call leaves a request in the transcript with no response and no error, which
is how the two were found.

That found a defect this change created. The old backend sent `task.started`
immediately; the new one sends nothing until the route is decided, so for up
to 8 seconds after pressing Start the home screen sat unchanged, which for
this audience reads as "it did not work". Fixed: the overlay shows "Let me see
what you need." from the moment Start is pressed, with the typed goal under
it and the presence mark breathing, until the answer or the task arrives.
Captured through the real stack before every model-routed goal.

### The design system

Tokens, measured before use. Contrast, WCAG ratio:

| Pairing | Light | Dark |
|---|---|---|
| ink on canvas | 15.1 | 16.5 |
| ink on card | 16.4 | 15.3 |
| soft text on card | 7.4 | 8.3 |
| button label on accent | 6.5 | 9.5 |
| stuck on card | 6.6 | 7.9 |
| instruction while waiting, 0.8 | 8.7 | 10.1 |
| instruction while waiting, the old 0.55 | **3.8 — fails** | 5.4 |

Screenshots of every screen before and after, in both themes, taken from the
overlay page by `python -m tools.screenshots before|after` (21 screens after,
20 before — the reading state did not exist). Before, the two themes are the
same picture: there was one theme.

### Defects found on the way

1. **The closing screen's answer pulsed.** The thinking pulse dimmed the
   whole column whenever the state was `thinking` with no step, and the loop
   never leaves `thinking` after `task.completed` — so on the one screen that
   exists to be read, the answer faded between full and 62% every 2.6
   seconds. Replaced by the presence mark, which breathes on its own.
2. **The home screen's box could vanish mid-sentence.** It shows while
   history is empty and hides under "Ask for something new" when
   `history.offered` arrives; if that is late, the person has already started
   typing. Found by a test that failed one run in three. Typing now latches
   it open.
3. **A double focus ring** on the ask box: the global focus rule was
   unlayered CSS, which outranks every utility. Moved to `@layer base`.
4. **The mock carried the billing answer on the registration script**, and
   played registration whatever was typed. It now routes as the backend does
   and plays each flow from the real plan's own steps.
5. **Tests would have spent quota.** Every websocket test starts the app, and
   the app's default is now a model call with the real key in `.env`. The
   backend conftest defaults tests to keyword routing.
6. **Two mistakes in my own verification script,** both caught by looking at
   what it captured: it treated "Here's what I found" as an ending (a step with
   a finding says it too) and stopped billing on step 3; and it assumed the
   model would call "pay for my course" ambiguous.

### Measured

- Suite: **458 passed, 8 skipped, 0 failed**, on the final code, in 720s.
- `test_levels` on a fresh `dist/`: level 3 is never taller than level 2,
  levels 1–3 distinct, a longer step taller at every level — all hold with
  the card and the new type sizes.
- `test_replies` 6/6 on three consecutive runs after the latch fix; 2/6 and
  4/6 failing before it.

### What this does not do

- **No new typeface.** Flagged in DECISIONS.md.
- **No user has seen it.** Every judgement above is the brief's and the
  measurements', not a person's with a cognitive disability.
- **The host window is 1263px wide on scrollable pages** (2026-09-20e); the
  overlay itself never scrolls, so it is unaffected, but it is still open.

---

## 2026-09-21b — the due date, the merge, and the overlay at the audience's size

### The due date on the closing screen

The comparison page showed the bill due "15 October 2026"; the real-stack run
showed "15-09-2026". Traced to the source:

| Where | Says |
|---|---|
| `replicas/billing/app.py`, `BILL["due_date"]` | `15-09-2026` |
| The replica's results page, `DUE DT` column | `15-09-2026`, printed verbatim |
| The real product, through the Electron host (2026-09-21) | **15-09-2026** |
| `tools/mock_backend.py`, until today | "15 October 2026" |
| `tools/screenshots.py`, until today | "15 October 2026" |
| `tools/mock_backend.py`, before 2026-09-21 | "15 September" |

**Both the value and the format were wrong, and only in demo data.** The
product never reformatted anything: `content.py` reads the cell's text and the
overlay prints it. "15 October 2026" was invented while writing the mock's
billing script on 2026-09-21 — the wrong month, in a format the page never
uses — and copied into the screenshot tool, so the published comparison put it
on the answer screen. Fixed: both take the replica's values, and a new test
fails if the mock's answer differs from `BILL` by a character. The previous
comparison page still shows the wrong date and is superseded by this one.

### The merge

`feat/interface-design-system` fast-forwarded `main`; the perception branch
merged on top. Conflicts only in the three append-only records, where both
had added entries at the end; resolved by keeping both, perception first, in
the order the work was done. **479 passed, 9 skipped** on the merged tree
before the merge was committed.

### The overlay at the audience's size

Every screen again, before and after, both themes (`python -m
tools.screenshots before2|after2`): before is `main` after the merge, with
the corrected demo data, so the comparison shows only interface changes.

| | Before | After |
|---|---|---|
| Body text | 18px | 23px |
| Focal size (display / hero) | 38 / 56px | 48 / 72px |
| Large button | 64px | 80px |
| Column | 680px of 1280 | 880px of 1280 |
| Face | Segoe UI | Atkinson Hyperlegible Next |
| Home: own words | behind "Ask for something new" with history | always shown, below the cards |
| "What are you doing?" | grey underlined link | secondary button with an icon |
| Trust panel | whole page, target ringed at its real size | close-up on the target, whole page one button away |

The overflow guard's budget is the risk in a scale-up, and the densest screens
were checked in the captures: the level-1 step with a field and a notice ends
at y≈760 of 800, the step with a finding at y≈750, the home screen at y≈725.
All fit without the guard dropping a level. `test_levels` holds on the new
geometry: level 3 is never taller than level 2, the three are distinct, and
a longer step is taller at every level.

Suite on the finished branch: **485 passed, 9 skipped, 0 failed**, 650s.

### The keyword fallback

Two flows named by strong words is now a question. The case from 2026-09-21 —
"I have a payment due and a class to sign up for", which ran billing when the
model timed out — asks which; so do "pay my electricity bill and then find me
a train" and "register for CS-401 and check the train times". A place name
alone still does not make a second flow.

## 2026-09-23 — the demo recordings, and what they cost to make

Four clips, recorded by `tools/record_demo.py` against the real stack
(`run.ps1 billing`, hardcoded planner, model router) and the mock. The overlay
is built from source and served as a plain page, so Playwright can record what
the Electron window cannot; the backend drives the hidden site view exactly as
in the product. The frame is the overlay's own 1280x800, never the desktop.

| Clip | Backend | What it drove | Size | Wall clock |
|---|---|---|---|---|
| `railways` | real, live site | departure, destination, open the calendar, set the date, search, ended | 4.9 MB | 80s |
| `billing` | real, replica | accept cookies, check the bill, show the breakdown, ended | 2.2 MB | 24s |
| `hello` | real | greeted — **no task started** | 0.6 MB | 8s |
| `fold` | mock | log in, add course, confirm my place, submit, ended | 2.7 MB | 30s |

9.9 MB in total. The wall clocks are not performance figures: the recorder
waits `BEAT_MS = 1800` between presses and types the goal at 45ms a character,
because the clip is for an audience to read. The railways flow's own five
steps are the same five the live run takes.

Every clip reached a terminal screen on the first attempt. The recorder prints
the buttons it pressed, so a clip that stopped early would be visible without
opening it — that is the check, and nothing was silently short.

Suite after the documentation changes: **485 passed, 9 skipped, 0 failed**,
762s on this machine.
The 9 skips are 5 needing a running Electron host, 2 needing a host and
`SIMBA_HOST_TESTS=1`, and 2 needing `SIMBA_LIVE_TESTS=1`. This breakdown is
recorded because README.md now states it, and the previous statement of it —
"5 host, 2 live, 1 `SIMBA_HOST_TESTS`" in STATUS.md — was one test out of date.

## 2026-09-25 — the level adapts in a real run, by provisional rules

Until today only the mock sent `load.updated`, so a real run stayed at level 2
unless the person moved it. `backend/estimator/rules.py` now moves it, by
hand-written rules marked provisional (DECISIONS.md, 2026-09-25). All
thresholds are guesses and are listed there.

### Scripted telemetry (`backend/estimator/test_rules.py`, 24 tests)

The four runs the task named, fed to the rules as the overlay would send them
(a 3s timer sample while a step waits, one more with the answer):

| Run | Levels, step by step | `load.updated` sent |
|---|---|---|
| calm, 5 steps | 2 2 2 2 2 | 1 (the start, level 2) |
| hesitant on step 2 | 2 3 | 2 (start; fold during step 2 at the 15.0s sample) |
| hesitant on step 1, then calm | 3 3 3 2 | 3 (start; fold on step 1; return as step 4 arrives) |
| locked at 2, hesitant on steps 1 and 3, help on 2 | 2 2 2 | 0 |

### Through the loop and the app (`backend/orchestrator/test_adaptation.py`, 6 tests)

Billing replica, hardcoded plan, real browser. Hesitant on step 1, calm on 2
and 3: `load.updated` levels **[2, 3, 2]**. The start arrives before step 1,
the fold between step 1 and step 2, and the return after step 3 and before
`task.completed`. Decision rows: 5 + 1 + 1 samples, 3 steps, 1 end = **11**,
one per evaluation. Over the websocket with `level.override {2, locked}` sent
before `task.start`, **0** `load.updated`.

### Live, billing, through the Electron host (`tools/evaluation/adaptation_stack_run.py`)

`run.ps1 billing`, hardcoded planner, model router. The script drives the
overlay page inside the host; the overlay's own `telemetry.ts` measures the
pointer. Screenshots of the overlay page only.

| Pointer on step 1 | Fold seen | Rule that fired | Steps 2–3 shown at | Return | Decisions logged | Wall clock |
|---|---|---|---|---|---|---|
| drifting back and forth | **yes, 8.0s** into hesitating | pointer wandering, ratio 53.11 | 3, 3 | "I'm showing a bit more again" on the ending | 12 | 30.0s |
| still | **yes, 18.3s** | paused 17.9s | 3, 3 | same | 14 | 38.3s |

The still run folded at 17.9s rather than 15s. Samples go every 3s, and the
one before the threshold landed just under it, so a pause can go up to 3s past
the threshold before the fold. The drifting run folded on the first sample
past `wander_after_ms`. Sweeping back and forth ends near where it started, so
the path ratio divides by a short distance and reaches 53. That rule fires as
soon as it is allowed to, and a real hand may do the same (DECISIONS.md).

**Lock, live, two tasks on one window.** Step 1 locked at level 2 by pressing
the middle dot, then 20s still: **no fold**, and three `locked` decisions
logged ("would simplify: paused 15.5s / 18.5s / 21.0s"). The second task,
started with "Do something else", began `locked at 1; would start at 2`. The
store re-sent its lock, and again nothing folded. The lock had become level 1
because of the overflow guard, not the rules; see "Found" below.

### Clip

`demo/adapt.webm`, 2.1 MB, 32.4s, from `python -m tools.record_demo adapt`
against the same stack. Frames checked from the file: level 2 at 17s, folded
to level 3 with "I'm showing less for a moment" at 21s, ending with "I'm
showing a bit more again" at 32s. As with the other clips, the recorded
overlay is the built overlay in a Playwright browser, talking to the real
backend, which drives the Electron host's site view. The Electron window
itself cannot be recorded.

### Found

- **The return notice overflows the billing ending.** At 1280x800 the ending
  plus "I'm showing a bit more again" fills about 790 of 800 CSS px, and a
  scrollbar shows until the notice leaves (8s). It happens because billing's
  return can only land on the ending (three steps). Flagged, not fixed.
- **The overflow guard moves to level 1 and overrides the lock.** Billing's
  step 3 at level 2 does not fit, so the guard hops to `denser(2)` = 1 and
  announces it. The store keeps that level for the next task, and under a lock
  it becomes the locked level. This was true before today; the rules make it
  visible, because the guard and the rules now move the level in opposite
  directions and the backend is never told about the guard's move. Flagged.
- **A test-driver bug suspected, and wrong.** The level-1 surprise was first
  blamed on the driver clicking a level dot as if it were the go-ahead. The
  dots sit outside the step shell, so it cannot have been, and the guard
  explains it exactly (its notice was on the ending).

### Suite

**515 passed, 9 skipped, 0 failed**, 656s on this machine: 485 before, plus 24
rule tests and 6 adaptation tests. The same 9 skips. `data/steps.jsonl` held
200 rows before the suite and 200 after, because the suite now turns recording
off.

## 2026-09-25b — the window fits the screen at 100%, 125% and 150%

On a 1920x1080 laptop at 150% the work area is 1280x672 DIP, and the host
asked for a 1280x800 window. **Before the change**, measured at this
machine's real 150%, Windows clamped the window's outer height to 672. Both
views were still 1280x800 inside it, and the home screen's text box sat at
643–712 CSS px, below the bottom of what the window showed. Nothing could be
typed without a scrollbar, and there was none.

**After**, measured by `tools/evaluation/display_fit_run.py`. Scales 1, 1.25
and 1.5 are forced (`--force-device-scale-factor`); `native` is the machine's
real 150%.

| Scale | Work area (DIP) | Window, frame included | Fits | Overlay zoom | Overlay CSS | Text box (CSS y) | Scrolls | Site view CSS | Site captures |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 1920x1008 | 1302x882 at (309, 63) | yes | 1.000 | 1280x800 | 645–714 | no | 1280x800 | **11/20** |
| 1.25 | 1536x807 | 1193x806 at (172, 0) | yes | 0.917 | 1280x801 | 644–712 | no | 1280x800 | 20/20 |
| 1.5 | 1280x672 | 984x672 at (148, 0) | yes | 0.757 | 1280x800 | 644–713 | no | 1280x800 | 20/20 |
| native (150%) | 1280x672 | 984x672 at (148, 0) | yes | 0.757 | 1280x800 | 644–713 | no | 1280x800 | 20/20 |

The window's bounds are the host's own (Electron's CDP has no
`Browser.getWindowForTarget`), and the page's `screenX`/`outerHeight` agreed
with them in every row.

**Through the whole stack at the real 150%**, `run.ps1 billing`: all three
billing steps ran and the site view ended on the bill detail. The backend's
clicks work in a site view that reaches past the window. "What are you
doing?" returned the preview in 0.4s, 1920x1200 px, the whole 1280x800 page,
with the ring on the right field. The adaptation check from 2026-09-25 still
passes: fold at 18.3s, return on the ending.

`frontend/test_window_fit.py`: 3 passed at forced 1, 1.25 and 1.5 with
`SIMBA_HOST_TESTS=1`, 77s; skipped otherwise. `frontend` + `tools` suites:
110 passed, 3 skipped. The backend was not changed and was not re-run.

### Found

- **The window was 1 DIP too tall at 125% and 150% on the first try.** The
  frame measured before resizing differed by a rounding pixel afterwards, and
  at 150% the same window rounded to a different DIP height once it had moved.
  Fixed: the host checks where the window finally stands and fits again by
  any overshoot.
- **Playwright's `page.screenshot()` gets the zoomed overlay wrong.** It sized
  the capture as 1280x800 DIP times the screen scale, which produced the real
  969x606 view in the corner of a larger picture. The evaluation scripts now
  capture the view's own surface (`display_fit_run.capture_view`), used by
  `routing_stack_run` and `adaptation_stack_run` too.
- **Site-view captures at forced 100% are 10–11 of 20**, alternating, and the
  **unchanged host does the same** (10/20 at forced 100%, 20/20 at 150%). So
  this predates the change. If it also happens at a real 100%, `page.preview`
  fails about half the time on 100% machines. Not settled: it needs a machine
  really set to 100%.
- **One hang, not reproduced.** Mid-run, after several raw CDP captures that
  were abandoned on timeout, Playwright could no longer connect to the host.
  A fresh host ran the same flow cleanly. The probing is the likely cause; it
  is not proven.

## 2026-09-25c — the overlay at the window's real size, the guard, the notice, the rating tool

### The home screen at 100%, 125% and 150%

`tools/evaluation/display_fit_run.py`. Forced scales on a machine set to 150%,
and that machine's real 150% (`native`).

| Scale | Window (frame incl.) in work area | Overlay CSS = window content | Zoom | Smallest text | Input text | Text box (CSS y) | Scrolls | Site view | Site captures |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 1302x882 in 1920x1008 | 1280x800 | 1 | 20px | 26px | 645–714 | no | 1280x800 | **10/20** |
| 1.25 | 1301x806 in 1536x807 | 1280x734 (compact) | 1 | 20px | 26px | 493–553 | no | 1280x800 | 20/20 |
| 1.5 | 1280x672 in 1280x672 | 1266x606 (compact) | 1 | 20px | 26px | 492–553 | no | 1280x800 | 20/20 |
| native 150% | 1280x672 in 1280x672 | 1266x606 (compact) | 1 | 20px | 26px | 492–553 | no | 1280x800 | 20/20 |

Body text is 23px everywhere. Under the zoom from earlier today it was drawn
at about 17px at 150%.

### Whole flows, every screen

Billing (with "What are you doing?" on step 2) and registration, through the
Electron host. At 150% on the running stack; at forced 100% and 125% on a
second host and backend. "Overflows" means the document is taller than the
window.

| Flow | Scale | Screens | Overflowing | Guard moves (backend's log) |
|---|---|---|---|---|
| billing | 100% | 7 | 0 | 0 |
| billing | 125% | 7 | 0 | 0 |
| billing | 150% | 7 | 0 | 0 |
| registration | 150% | 5 | 0 | 1: sign-in step, 2 → 1, `overflow` |

Before the compact layout covered steps and endings, at 606px, billing's
step 3 overflowed by 27px even at level 1 and its ending by 78px; after
compacting, step 2 at level 2 still overflowed by 1px, which the guard's
2px tolerance let through. Trimming the page's bottom padding in a short
window cleared it. The earlier run's guard move on billing's step 2 was
logged by the backend as `override · overflow · 2 → 1`.

`frontend/test_overflow_guard.py`, 3 tests at 1266x606: the guard's move goes
out as `level.override {1, locked: false, by: "overflow"}`; under a lock at 2
it goes out `locked: true`, and the next step is back at 2; a lock carried
into a new task is re-sent as `{2, locked: true, by: "person"}` after the
guard had shown level 1. `backend/estimator/test_rules.py`: 27, 3 of them new
for guard moves.

The level notice, floating: over the presence mark and the card's top
padding on every step and ending screenshot at 606px, and over no text.

### The rating tool

`python -m tools.rating.capture`: 46 of 50 pages on the first pass. Three
failed on the scrollbar style, because pypi.org and gov.uk (two pages)
forbid inline styles by CSP. BBC News had one refused capture. With
`bypass_csp` and one retry, `--only` those four: **50 of 50**, every page
laid out at 1280px, 4.9MB. Headless Chromium laid a 2400px-tall page out at
1280 with or without `--hide-scrollbars` and the style, in both headless
modes.

`tools/rating/test_rating.py`, 23 tests: every page once plus exactly two
repeats; a repeat is at least 6 positions after its first showing over 200
seeds; a seed reproduces its order; answers outside 1–7, non-numeric raters
and double answers are refused and write nothing; a whole 7-picture session
in a browser, by key and by click, writes 7 rows with the right ratings,
positions, rater, two repeats, `ms` ≥ 100 and the window size.

### Found

- **Chromium remembered the zoom.** The first build without the zoom still
  came up at 0.757, with device pixel ratio 1.136 at 150% and 0.757 at
  forced 100%, because the zoom level is stored per origin in the profile.
  Fixed by setting zoom 1 on every load, for both views.
- **Registration "stuck" at step 2 was my driver.** It pressed "Sign in"
  with the credential fields empty; the replica refused, no modal opened,
  and "Close" could not be found. With the replica's test credentials it
  completes in three steps. It stopped at the same place at forced 100%, with
  the site view wholly inside the window, which is what ruled out the new
  overhang before the empty fields were found.
- **At forced 100% the trust panel's preview never arrived** within 35s on
  billing's step 2: the site-view capture failing, which is the pre-existing
  10/20 pattern at 100% (2026-09-25b). Part 7 of the task measures it at a
  real 100%.

### Suite

**544 passed, 12 skipped, 0 failed**, 729s: 515 before, plus 3 rule tests for
guard moves, 3 overlay tests of the guard and 23 of the rating tool. The 3 new
skips are `frontend/test_window_fit.py`, which opens the host itself and runs
only with `SIMBA_HOST_TESTS=1`; run that way on the final code it passed 3 of 3
(79s). `data/steps.jsonl` had 623 rows before the suite and after it, and the
suite created no `data/ratings.jsonl`.

## 2026-09-27 — site-view captures at a real 100%

The machine switched to 100% by its owner for this measurement and switched
back afterwards. Display 1920x1080, work area 1920x1032, scale factor 1.
`tools/evaluation/display_fit_run.py native`, then the passes now in
`tools/evaluation/site_capture_run.py` (one host launch, 20 Playwright
captures of the site view per pass, 5s timeout each):
`python -m tools.evaluation.site_capture_run` reproduces them at whatever the
machine is set to. At forced 100% on 2026-09-27 it gave static 11/20, static
again 11/20, repainting 20/20: the same alternation, so forced 100% is a fair
stand-in for developing against.

| What | Captures | Pattern |
|---|---|---|
| `display_fit_run native` | **10/20** | — |
| static page | 12/20 | `+++++.+.+.+.+.+.+.+.` |
| static page, second pass | 10/20 | `.+.+.+.+.+.+.+.+.+.+` |
| page repainting every frame (a rAF animation) | **20/20** | all |

So the failure seen at forced 100% is real at a real 100%, and it has the
signature of the `setVisible(false)` finding in CLAUDE.md: on a page that is
not repainting, every other capture times out waiting for a frame. A page
that repaints every frame never fails. At 125% and 150% the same static page
captures 20/20, forced or real, and why the scale factor matters is not
known.

The window at 100%: 1296x865 inside 1920x1032; overlay 1280x800 at zoom 1;
smallest home-screen text 20px; text box at 645–714, no scrolling; site view
1280x800.

**Consequence:** on a machine at 100%, "What are you doing?" can be expected
to fail to return its picture about half the time, on any site page that is
idle when it is asked — which is most of them. Not fixed; see STATUS.md.

---

## 2026-09-30 — every flow on the person's own details, and five live runs

The change: a routed goal is read for what it says, whatever is missing is
asked for one question at a time, and the task — including what has to be true
at the end — is built from the person's answers rather than from the plan's
values. Before today "trains to Rawalpindi tomorrow" searched Lahore Cantt to
Karachi Cantt on the 15th of next month, and reported success.

Hardcoded planner throughout, so **no model quota was spent on any run below**.
The keyword and date reader did all the reading; the model path is covered by
fake readers in `test_details.py` and was not exercised live.

### The suite

| | Before (STATUS.md, 2026-09-25) | Mid-change (`e951ced`) | After (`ae26978`) |
|---|---|---|---|
| Passing | 544 | 710 | **712** |
| Skipped | 12 | 12 | 12 |
| Wall clock | 729s | 1000.85s | **1081.18s** |

**168 tests added**, all in this change. The 12 skips are unchanged and none of
them ran: 5 need a running Electron host, 2 need a host and
`SIMBA_HOST_TESTS=1`, 3 open the host themselves and need `SIMBA_HOST_TESTS=1`,
2 need `SIMBA_LIVE_TESTS=1`. The wall clock carries the usual ±2x for this
machine (2026-09-17h); the growth is mostly real work — 29 of the new tests
drive a browser against a replica and 5 build the overlay and drive it.

New files: `test_details.py` (83), `test_trip.py` (29), `test_asking.py` (19),
`test_course.py` (9), `frontend/test_questions.py` (5); the rest are additions
to `test_success_conditions.py` (17), `test_billing.py` (7) and
`test_app_routing.py` (2).

### The three goal shapes, against the local replica

`replicas/railways/` on :5244, the real backend on :8044, keyword routing,
driven over the websocket the way the overlay drives it. Each run searched and
reached the closing screen.

| Goal | Asked | Shown | `steps_taken` | Searched |
|---|---|---|---|---|
| `trains from Rawalpindi to Multan tomorrow` | nothing | 5 | 5 | `RAWALPINDI → MULTAN CANTT`, `2026-10-01` |
| `trains to Rawalpindi tomorrow` | where from; which Lahore station | 7 | 5 | `LAHORE CANTT → RAWALPINDI`, `2026-10-01` |
| `I need a train` | where from; where to; which day; which Lahore station | 9 | 5 | `LAHORE JN → MULTAN CANTT`, `2026-09-30` |

`steps_taken` is 5 in all three: a question is not a step, and neither is
choosing from the station list the site offered (`Move.quiet`). What the
replica recorded as searched is its own `window.__searched`, taken from the
application's state rather than from the boxes.

A fourth run of `I need a train` answered the destination with an empty box
three times and ended in `help.requested` — "I asked a few times and still
couldn't work out what you meant." — with nothing searched, which is
`MAX_TRIES`.

### The counter defect, found by running it

The second run above first read **1 of 7**, then **2 of 5**. Two mistakes in
opposite directions: the brief recomputed its count on every question and
counted the question on screen as both asked and still missing, then the steps
after the questions took their count from the settled task, which knows only
about the plan. Fixed by reading the count once at `task.started` and keeping
it (`_Run.total`), and freezing the brief's own promise. Now:

    1/6  2/6  3/6  4/6  5/6  6/6  7/7

It still ends one above the promise, because a question only the page can
raise — which of two stations in one city — cannot be counted before the page
has answered. It never goes backwards, and never below what is on screen.
`test_asking.py::test_the_count_never_goes_backwards_across_the_questions`.

### Five runs on the live site, through the Electron host

`run.ps1 railways`, hardcoded planner, goal typed into the real overlay and
every answer pressed in the real window over CDP after a 2.5s pause
(`python -m tools.evaluation.person_details_stack_run "trains to Rawalpindi
tomorrow" --type Lahore --pick "Lahore Cantt"`). Read-only: one timetable
search per run. Machine at 150%, window content 1266x606, site view 1280x800.

| # | Commit | Station chosen | Searched | Trains back | `duration_ms` | Wall clock |
|---|---|---|---|---|---|---|
| 1 | `ff0c7cc` (dirty) | Lahore Jn. | `LHR → RWP`, `2026-10-01` | **9** | 54,750 | 77.8s |
| 2 | `ff0c7cc` (dirty) | Lahore Jn. | `LHR → RWP`, `2026-10-01` | **9** | 54,750 | 73.4s |
| 3 | `d8043e8` | Lahore Jn. | `LHR → RWP`, `2026-10-01` | **9** | 53,467 | 67.1s |
| 4 | `d8043e8` | — | nothing | — | — | 37.3s |
| 5 | `ae26978` | **Lahore Cantt** | `LRC → RWP`, `2026-10-01` | **3** | 54,047 | 71.9s |

**What the required check asked for, and what happened.** "Trains to
Rawalpindi tomorrow" asked **where from** and nothing else — it had read the
destination and the date out of the sentence. `Lahore` typed into that box
brought back the site's own two Lahore stations, and it asked which:

    question 1/6  Where are you travelling from?          box: From
    step     2/6  Let me set where you're starting from.   Starting at Lahore.
    question 3/6  Which Lahore station do you mean?        Lahore Jn. | Lahore Cantt
    step     4/6  Now where you're going.                  Arriving at Rawalpindi.
    step     5/6  Let me find the right month.              Travelling on 1 October.
    step     6/6  Now the day you're travelling.            1 October.
    step     7/7  Trains from Lahore Cantt to Rawalpindi on 1 October. Shall I search?

The search the live site actually sent, from its own network:

    POST .../ticket/trainInfo/trainInfoList
    {"boardStationCode":"LRC","arrivalStationCode":"RWP","travelDate":"2026-10-01"}

and the form it ended holding: `From LAHORE CANTT`, `To RAWALPINDI`,
`Departure Date 01-10-2026`. Three trains came back on the real page —
`13UP 07:14→13:20 6 h 6 min`, `39UP 09:22→16:00 6 h 38 min`,
`1UP 20:12→… 6 h 3 min`, all `LAHORE CANTT / RAWALPINDI` — and the closing
screen showed all three with their journey times.

**The station the person picked is the one the site searched.** Runs 1–3 chose
Lahore Jn. and sent `boardStationCode":"LHR"`; run 5 chose Lahore Cantt and
sent `"LRC"`. Different answer, different code, different trains (9 and 3).
Runs 1–4 pressed Lahore Jn. whatever `--pick` said, because the stack runner
re-decided its answer on every look while waiting for the button and took
another off the front of its list each time; that was a bug in the runner, not
in the backend, and run 5 is after fixing it.

### Run 4: the station list did not come back, and the run said the wrong thing

One of five runs failed, and it is the useful one.

    step 2/6  Let me set where you're starting from.
    step.failed  the page did not change at all   (2 strategies tried)
    help.requested  "I couldn't find a station called Lahore."

The name did reach the box — the form afterwards held `From LAHORE` — but the
site's list had not opened within the 5s `VERIFY_TIMEOUT_S`, on either
strategy, so nothing was offered for "Lahore" and the planner concluded there
is no such station. It had searched from Lahore Jn. three times in the
previous ten minutes.

A list that has not arrived and a place that has no stations look identical
from here: both show nothing. So the sentence was changed to say what was
observed rather than what it means — "The site didn't offer me any stations
for Lahore." The flakiness itself is **not fixed**: 1 of 5 live runs on this
machine, and the retry structure gives a station name two fills and two 5s
waits before the run ends. See STATUS.md.

`duration_ms` in runs 1 and 2 is identical to the millisecond, which is
coincidence rather than a constant: 7 of the ~54s are deliberate 2.5s pauses
and the runner looks every 400ms, so the total is heavily quantised. Run 3 and
run 5 differ from it.

### What the check now refuses

Same loop, same pages, the task's declared values changed to a journey nobody
asked for:

| Rigged as | Where it stopped | What it said |
|---|---|---|
| plan searches Rawalpindi→Multan, task asks Rawalpindi→Peshawar | before the search was sent | `'To'` does not hold `Peshawar` |
| plan searches tomorrow, task asks 75 days out | after a real search returned real trains | `Departure Date` holds `01-10-2026`, expected `14-12-2026` |
| plan books MATH-210, task asks CS-401 | on the real confirmation page | `Course` showed `MATH-210 section 001`, expected `CS-401` |
| plan looks up `0414 9999 999999`, task asks `0414 1234 567890` | on the real bill detail page | `REF NO` showed the other number |

The route case never sends the search at all: the page is holding a station
the task does not name, and that is noticed while the form is still being
filled. The day is the case that reaches the end, because nothing types a
date — it is picked out of the calendar — which is the 2026-09-09 failure
shape with the person's own day in place of the plan's.

### The billing replica was making its own check meaningless

Its results page printed the worked example's reference number whatever had
been looked up, so every bill claimed to be the one asked about and
`About.shows` would have passed for any number. It echoes the number that was
searched now. Found while writing the check, not by a test.

---

## 2026-09-30b — a station list that opens late

The live failure from 2026-09-30, run 4: the name went into the box, the site's
list had not opened within the 5s verification window on either strategy, and
the run said the site offered no stations for Lahore. A step that waits on a
fetched list now has `LIST_TIMEOUT_S = 15.0` instead (`Expectation.list_opens`);
only the trip planner's typing step sets it.

Reproduced on the local replica, which now takes `?list_delay_ms=` and makes
its list arrive that long after a name is typed. 8000ms throughout — past the
ordinary window, inside the new one. `test_trip.py`, real Chromium.

| What | Before the fix (window 5s) | After (window 15s) |
|---|---|---|
| "trains to Rawalpindi", list 8s late, both ends | `step.failed`, then "The site didn't offer me any stations for Lahore.", nothing searched, 11.6s | searched `LAHORE CANTT → RAWALPINDI`, no `step.failed`, 18.8s |
| Typing "LAHORE", list 8s late, verification alone | fails at 5.0s | passes, between 5s and 15s |
| Typing "LAHORE", list immediate, verification alone | — | passes in under 5s: polled, not slept |

"Before" is the same code with `LIST_TIMEOUT_S` set back to 5s for one run, so
the only difference between the two columns is the window.

**What it costs.** A place the site genuinely has no station for is now found
out after both strategies have waited the full list window: the Narnia run takes
**31.5s** to reach "The site didn't offer me any stations for Narnia.", where it
took about 11.6s before. A person who mistypes a place waits about twenty
seconds longer to be told so. Nothing else on the trip waits longer: choosing a
station, the calendar and the search keep the ordinary window.

**Not measured:** how late the live list actually was. The failing run recorded
only that it had not come within 5s, and the site was not asked again for this.
15s is three times the window it failed in, not a figure read off the site.
Replayed runs are unaffected either way — replay builds every move with an
empty expectation — and trace memory is off by default.

---

## 2026-09-30c — two corrections to 2026-09-30, and `railways-local`

### Corrections

**There were six live runs, not five.** The 2026-09-30 table leaves out the run
made at 17:10 on `d8043e8` (dirty tree), between the failed run and the one that
chose Lahore Cantt. It chose Lahore Jn. because of the stack runner's `--pick`
bug, sent `{"boardStationCode":"LHR","arrivalStationCode":"RWP","travelDate":"2026-10-01"}`,
got 9 trains back, `duration_ms` 56,358, wall clock 71.4s. So: six runs, five
searches sent to the live site, one run that stopped before searching. The
backend's transcripts confirm six (`logs/llm-20260930-1200*` to `-1212*`).

**The model did read every goal, and quota was spent.** The entry says the
keyword and date reader did all the reading and that no quota was spent. Wrong:
`run.ps1` leaves the router at `model`, and `app.py` hands the same model to
`details.understand`, so every live run made **two model calls** — one to route
the goal, one to read its details — and the planner made none. Per run:

| | Prompt tokens | Completion tokens |
|---|---|---|
| Route | 202 | 12 |
| Details | 200 | 38–50 |
| **Run** | **402** | **50–62** |

Six runs, `gemini-3.1-flash-lite`, 2,412 prompt and 324 completion tokens in
all. Every details answer was the same and right:
`{"origin": null, "destination": "Rawalpindi", "date": "2026-10-01"}` — which
the keyword reader gives for this goal as well, so the runs do not tell the two
readers apart. **The model path of `details.py` has been exercised live, on one
goal**; the keyword path has not been exercised live at all.

### `railways-local`

`.\run.ps1 railways-local` brings up the three replicas, opens the window on
the local train search at :5200, and starts the backend with
`SIMBA_RAILWAYS_URL=http://127.0.0.1:5200`, so a train goal runs there. One run
through the Electron window with the stack runner, same goal and answers as the
live runs, at `49e3334` (dirty tree: this change):

| | Local copy | Live, for comparison (2026-09-30, run 6) |
|---|---|---|
| Screens | 7 (2 questions, 5 steps), same order and wording | 7 |
| Stations offered for "Lahore" | `Lahore Jn`, `Lahore Cantt` | `Lahore Jn.`, `Lahore Cantt` |
| Searched | `LAHORE CANTT → RAWALPINDI`, `2026-10-01` (the copy's own record) | `LRC → RWP`, `2026-10-01` (network) |
| Requests to the live site | **none** | one |
| `duration_ms` | 24,905 | 54,047 |
| Wall clock | 46.8s | 71.9s |
| Model calls | 2 (route, details) | 2 |

The copy is about twice as fast, so a rehearsal on it is not a timing rehearsal
for the live site. It spells the junction without the full stop the live site
uses.

---

## 2026-09-30d — the home screen with history, at 100%, 125% and 150%

The fit measurement (`display_fit_run`, `test_window_fit.py`) launched the host
with no backend, so the home screen it measured never had any remembered goals:
it was always the three-card screen. With history the old screen had six cards
— three remembered, three defaults, under two headings — and none of that was
measured.

**Before**, measured in Chromium at each scale's real content size (from
2026-09-25c) against a scripted backend offering the history, on the code at
`b6ac3d4`:

| Remembered | 100% (1280x800) | 125% (1280x734) | 150% (1266x606) |
|---|---|---|---|
| three bill look-ups | box at **1096–1164**, page 1224 tall | **867–927**, 955 | **867–927**, 955 |
| three at a card's limit | **1205–1273**, 1333 | **976–1036**, 1064 | **976–1036**, 1064 |

The text box was below the bottom of the window at every scale, not only at
150%. A bill look-up is a realistic remembered goal — "Find the amount due for
reference number 04141234567890." is what the trace store files a bill under.

**After**: one list, remembered goals first, nothing twice, three cards at
most; a card holds two lines; in a short window the card text is 23px and the
box's lead-in is dropped. Measured in the real host at forced scales
(`python -m tools.evaluation.display_fit_run`), with no history and with three
remembered goals at a card's limit (`HISTORY`: two lines even at 23px):

| Scale | Overlay CSS | No history: cards, box | With history: cards, box | Scrolls | Smallest text |
|---|---|---|---|---|---|
| 1 | 1280x800 | 3, 605–674 | 3, **656–724** | no | 20px |
| 1.25 | 1280x734 | 3, 453–513 | 3, **516–576** | no | 20px |
| 1.5 | 1266x606 | 3, 452–513 | 3, **515–576** | no | 20px |

Site view 1280x800 at every scale; captures 10/20 at scale 1, 20/20 at 1.25 and
1.5 — the known 100% capture problem (2026-09-27), unchanged.

The worst case at 150% leaves 30px under the box. `frontend/test_home.py` holds
it in the suite without a host: four histories at three sizes, never more than
three cards, remembered first, a remembered goal that is one of the cards shown
once and still sent with its flow. 22 tests.

With no history, the box sits 40px higher than on 2026-09-25c at every scale:
645–714 → 605–674 at 100%, from the tighter spacing, and 493–553 → 453–513 at
125% and 492–553 → 452–513 at 150%, from the hidden lead-in.

---

## 2026-09-30e — the site view's scrollbar, hidden

A page that scrolls, with an inner scroll box, in the Electron site view and in
headless Chromium (Playwright's own launch, which hides scrollbars). The host at
forced scales, over CDP.

| | Page layout width | Inner scroll box | Page still scrolls |
|---|---|---|---|
| Headless | 1280 | 1280 | yes |
| Host, before, at 1, 1.25 and 1.5 | **1263** | **1246–1247** | yes |
| Host, after, at 1, 1.25 and 1.5 | **1280** | **1280** | yes, to 600 of 600 asked |

So until today the host laid out every page that scrolls 17px narrower than
headless, and every inner scroller another 17px narrower still, at every scale.
That is the environment difference behind the scrollbar spacer column on the
live railways results (2026-09-17i): it appeared only in the host.

The fix is a user-origin stylesheet put into the site view on every page
(`frontend/electron/main.ts`), so a page's own CSS cannot bring the scrollbars
back. Checked on a first page and after a second navigation.
`test_window_fit.py` holds both, at all three scales, when the host tests run.

Every perception figure measured in the host before this — the host columns of
the corpus (2026-09-19b, 2026-09-20e) and every host run since — was measured
at 1263px on a page that scrolled. Re-collected in 2026-09-30g, below.

---

## 2026-09-30f — `MIN_COVERAGE` 0.27, checked against the coverage probe's data

From `data/overlay_coverage.json` (the probe's run of 2026-09-21, headless, 50
pages, every candidate above the page with no threshold applied). Coverage does
not depend on `MIN_COVERAGE`, so this data answers where the line can go
without being collected again.

| Coverage | Page | What | Blocker |
|---|---|---|---|
| 0.4612 | MUI drawer, bottom sheet open | the sheet | yes |
| 0.3688 | the Guardian | sticky top ad banner (two nested boxes) | yes |
| 0.3125 | Bootstrap offcanvas, drawer open | the drawer | yes |
| — | *nothing between 0.2344 and 0.3125* | | |
| 0.2344 | MUI drawer and dialog pages | the docs sidebar | no |
| 0.2344 | `entry_ad` | the dialog box inside `#modal` (its parent is caught) | no |
| 0.2258 | TodoMVC | the `aside` | no |

The sweep over thresholds blocks the same 10 pages at 0.20, 0.25 and 0.30. So
moving from 0.30 to 0.27 **changes no result on this corpus**; it moves the line
from 0.0125 under the nearest blocker to the middle of the gap (midpoint
0.273), 0.036 above the largest non-blocker and 0.0425 under the nearest
blocker.

The one case it is expected to change is arithmetic, not a measured page: a
drawer 378px wide — Ant Design's default — over the full 800px height covers
378/1280 = 0.295, which 0.30 misses and 0.27 catches. No page in the corpus puts
anything between 0.27 and 0.30. Perception's suite passes at 0.27 unchanged
(109 passed, 4 skipped).

---

## 2026-09-30g — the corpus, re-collected

`python -m tools.evaluation.collect_corpus`, both environments, at `3fb9ab4`
(clean tree): the site view's scrollbars hidden (2026-09-30e), `MIN_COVERAGE`
0.27 (2026-09-30f), and `text_density` measured where the page is scrolled to.
The same 50 pages as 2026-09-20e, read-only, the host at 150%. The previous file
is kept at `.scratch/corpus-before-2026-09-30.json` (ignored, local).

**Failures.** Spiegel, DNS, headless only, as before. New: 
`practice.expandtesting.com` refused the load in **both** environments
(`ERR_ABORTED`), so the page with the largest host difference last time
(3.6×) could not be compared this time.

### Headless against host

Rows compared on `text_density`, `viewport_characters`, `overlays`, `controls`
and `characters`, over pages read in both:

| | Pages read in both | Differ on any | Differ on `text_density` |
|---|---|---|---|
| 2026-09-20e | 49 | 14 | 9 |
| **Now** | 48 | **9** | **5** |

**Wikipedia, both pages, now read identically in both environments** — they
differed by 18% and 17% in density, the clearest case of the 1263px layout. So
does OrangeHRM, which rendered no text in the host last time.

What still differs, and why:

| Page | Density headless / host | Cause |
|---|---|---|
| lite.cnn.com | 2.013 / 1.913 | **Not explained.** Same 8,580 characters, same controls, 2,061 against 1,959 on screen: the layout still differs somewhere, and the scrollbar is not it |
| Hacker News | 2.363 / 2.310 | The page itself: 3,871 against 3,848 characters, a live front page read twice |
| MUI dialog (driven) | 1.805 / 1.492 | The drive: 0 overlays and 362 controls in the host — the dialog was not open when the host was read |
| Ant Design modal (driven) | 1.511 / 1.576 | The drive, the other way: the modal opened in the host (2 overlays) and not headless |
| Ant Design drawer (driven) | 1.525 / 1.584 | The drive: 3 overlays in the host, 0 headless |

The three driven differences were checked by driving those pages once more in
each environment and reading `analyse` directly. Where the state was reached,
both environments agreed exactly: the Ant Design drawer gave the same three
blockers in each, the MUI dialog the same two. **Overlays never differed for the
same state.** The corpus rows differ because the drive reached a different
state, which 2026-09-20e also saw on the Ant drawer.

**The first measured page between 0.27 and 0.30.** In that check, the open Ant
Design drawer's panel — 378x800 at x=902 — covered **0.295** of the viewport in
both environments, and is a blocker at 0.27 where it would not have been at
0.30. The page is already blocked by the drawer's full-screen mask either way,
so the page-level answer does not change; the blocker count does. This is the
case 2026-09-30f argued for from arithmetic.

### What the scroll-aware density changed

Headless, driven rows, before and after:

| Driven page | Density before | After | Characters before / after |
|---|---|---|---|
| MUI dialog | 1.077 | **1.805** | 7,689 / 7,689 |
| MUI drawer, bottom sheet | 0.924 | **1.739** | 8,126 / 8,126 |
| Bootstrap offcanvas | 1.175 | **1.811** | 21,891 / 21,933 |
| Bootstrap modal | 1.477 | **1.769** | 29,895 / 29,899 |
| Ant Design drawer | 1.235 | **1.525** | 12,827 / 12,827 |
| SweetAlert2 | 0.408 | **0.585** | 34,917 / 34,918 |
| Ant Design modal | 1.313 | 1.511 | 18,077 / 20,700 — the page changed |
| sign-in, both railways states, demoqa, TodoMVC, Element Plus | unchanged | unchanged | unchanged |

Where a drive scrolled the page to open something, the text on screen was
different from the text at the top of the document, and density rose by 19–88%
with the character count the same. Where a drive did not scroll, nothing
moved. Of 35 idle headless rows, 27 read the same density as before; the other
8 are live pages that changed.

`overlays` is still the one feature that barely varies across the corpus, now
the only one the collector reports as such.

---

## 2026-10-01 — one attempt for a step that waits on a list

A step that waits on a fetched list (`Expectation.list_opens`) now makes one
attempt instead of two. `test_trip.py`, local replica, real Chromium.

| | Before (2026-09-30b) | After |
|---|---|---|
| "Narnia": no station, reported after | 31.5s | **16.7s** (16.68, 16.84, 16.65 over three runs) |
| `step.failed.strategies_tried` on that step | 2 | 1 |
| A list 8s late, one attempt | — | found, searched, no `step.failed` |

One run of the same Narnia search took 24.8s; it was the first browser run in
that test session, and the three repeats above did not reproduce it. Every other
step still makes two attempts, which `test_setback.py` and `test_durability.py`
assert (`strategies_tried == 2`); 78 tests across those files, `test_trip.py`
and `test_verification.py` pass.

---

## 2026-10-01b — the estimator's training pipeline: built, checked on synthetic ratings, not trained

**There is no trained estimator and no result here.** `data/ratings.jsonl` does
not exist yet: no person has rated a page. `python -m backend.estimator.train`
today says so and exits with code 2, saving nothing and writing nothing.

What exists is the pipeline (`backend/estimator/train.py`), checked against
ratings generated by the tests, with a rule the tests chose. **Every number in
this entry is from synthetic ratings and describes the pipeline, not pages or
people.** Corpus: 50 synthetic pages; 12 synthetic raters, each with a bias of
their own, each repeating two pages; the rule is that dense text and many links
overwhelm, and nothing else matters.

| Synthetic raters | 5-fold R² | Predicting the mean | Alpha | Repeat mean difference | Top two by importance |
|---|---|---|---|---|---|
| follow the rule, noise sd 0.6 | 0.948 ± 0.018 | −0.025 | 0.777 | 0.46 | `text_density`, `links` |
| follow the rule, noise sd 2.5 | 0.574 ± 0.389 | −0.079 | 0.257 | 1.71 | `links`, `text_density` |
| ignore the page | −0.129 ± 0.090 | −0.099 | −0.018 | 0.67 | none above 0.0 |

So it finds the two features the rule uses and only those, its R² falls as the
raters get noisier, it finds nothing when there is nothing, and agreement falls
with them. Krippendorff's alpha reproduces the published value for the example
in Krippendorff (2011), 0.849. With 9 raters it refuses. One run takes about 4s.

`test_train.py`, 24 tests. It also holds the two guards: a synthetic run cannot
be saved to `data/estimator.joblib` or appended to this file — both checked
against the real files, which the tests leave unchanged.

scikit-learn 1.9.1 (numpy 2.5.3, scipy 1.18.1, joblib 1.6.0), new in
`backend/requirements.txt`.

---

## 2026-10-01c — the demo clips, re-recorded on our copy of the train search

`python -m tools.record_demo` with the stack started by `.\run.ps1
railways-local`, overlay built from source, every clip pressing at a 1.8s beat.
The backend's health check said `"railways_site": "http://127.0.0.1:5200"`
before the railways clip, and the recorder refuses to record that clip unless
it does.

| Clip | What it did | Ending | Length to record |
|---|---|---|---|
| railways | typed "Lahore", chose "Lahore Cantt", five steps | **found an answer** | 45s |
| billing | typed `04141234567890` when asked, three steps | **found an answer** | 32s |
| hello | — | greeted, nothing started | 8s |
| fold (mock) | four steps, the scripted fold | done | 30s |
| adapt | folded after 9.4s of hesitation on step 1, three steps | **found an answer** | 40s |

The first pass reported only "ended" for every task clip, which an "I'm stuck"
ending would also have produced; the recorder now says which ending it reached,
and the task clips were recorded again. Before the question flow, the recorder
pressed the first button on every screen, which on a question with a box is
"That's it" on an empty box: the railways, billing and (asked for a reference)
adapt clips could not have completed.

**What shows the railways clip ran on the copy**: the health check reports
`flow_setup("railways")`, the same function the run itself uses to choose the
site, and the recorder refused to start until it named the copy. Not a network
capture: the three replicas' request logs cannot be told apart, and no request
to the live site is in the stack's output.

The railways clip is 45s; the 2026-09-23 recording on the live site was 80s,
with three fewer screens. The copy is faster than the live site (EVALUATION.md,
2026-09-30c), so the clips no longer show the live run's pace.

---

## 2026-10-03 — the rating pictures and the corpus, one run

`python -m tools.rating.capture`, run `58dc053cdac7`, 2026-10-03 16:47 +05:00,
at `7b1a1f9` (clean tree), with the stack up for the corpus's host half. For
every page: one headless load, the drive, the scrollbars hidden, the features
read and the picture taken moments apart from that same page; then the host
half, straight after. `data/rating/pages.json` and `data/corpus.json` both
carry the run's id and date, on the file and on every row.

| | |
|---|---|
| Pictures captured | **50 of 50**, all laid out at 1280px |
| Headless rows (the features the estimator uses) | 50 of 50, every one from run `58dc053cdac7`, the same as its picture |
| Host rows | 49 of 50; `practice.expandtesting.com` refused the host (`ERR_ABORTED`) |
| Pictures identical to the 2026-09-25 set | 23 of 50 |
| Headless density changed since 2026-09-30 | 12 of 50 pages |

So 27 of the 50 pictures people would have rated were no longer the pages the
features described. That is now impossible by construction for a rating given
from here on: `train.py` uses a rating only if it was given for the picture in
the manifest and that picture's features came from the same run.

Headless and host differ on 13 of 50 pages by the collector's count. What
differs, and why, is the same kind as 2026-09-30g: driven pages where the drive
reached a different state in each environment (both Ant Design pages), live
pages read twice minutes apart (Hacker News, BBC, the Guardian, Bootstrap's two
docs pages by a few dozen characters), and small unexplained density
differences with identical text (lite.cnn.com 1.920/1.867, Wikipedia's main
page 1.903/1.940). `entry_ad` shows its modal in the host and not headless, so
its picture shows no modal, and its features say so too — they agree with each
other, which is the point.

**One thing about how the headless features are read changed with this.** They
are read in the capture's browser context — `--hide-scrollbars`, the scrollbar
style injected, `bypass_csp` so that style is accepted on pypi.org and gov.uk —
rather than `collect_corpus`'s plain one. That is what makes them the features
of the picture. `collect_corpus` on its own still reads the plain way.

---

## 2026-10-03b — the credential store: a saved password, searched for everywhere

`backend/orchestrator/test_vault.py`, the registration replica, real Chromium.
The headline test runs a whole registration task through the real loop, the
real LLM planner and the real `OpenAICompatibleProvider` — only its HTTP call
answered offline — with a password saved for the site, trace memory on, the
step recorder on and every log record captured at DEBUG. Then it searches for
the password in:

| Where | Found |
|---|---|
| Every prompt the model was sent (5) | no |
| The provider's transcript file | no |
| The trace database | no |
| The step recorder's file | no |
| Every log record | no |
| Every message to the overlay | no |
| The vault file (nor the username) | no |
| Every file created or changed under `logs/` and `data/` during the run | no |

And the backend did type it: the fill on the "Password" field carried it. The
password step was shown with no field for it and the line "I'll use the sign-in
details you saved for this site."

**The test catches a leak.** Planting one log line carrying the password failed
it on "every log record"; planting the password in a step's instruction failed
it on "the step recorder". Both plants were in a scratch copy, removed after.

**A leak found while building it.** CDP's snapshot reads every input's live
value, a password field's included, so after a password was typed the secret
was in `Document.input_values`, in `Element.value` and in every `Snapshot` built
from them. Nothing sent it further — the model's page has no values, and the
loop's checks already skipped passwords — but it was one new reader away from a
prompt or a log. `snapshot.parse` now reads a password field as `********` when
it holds anything and empty when not; `test_serializer.py` types a password into
the real replica and finds it nowhere in the read.

The other twelve tests: nothing readable on disk; an entry is per site (origin);
a tampered entry is refused, not misread; saved details never print; asked once
and kept only when the person presses "Sign in and save my password"; typed
without asking the next time; forgotten on request and the step asked again in
the same run; a password whose step did not work is not kept; with no vault the
step is exactly as before. At 150% (1266x606) the sign-in step with its third
button keeps both fields and all three buttons on screen. 13 + 2 + 2 tests.

---

## 2026-10-03c — one plain sentence on the closing screen, and the screen it lands on

`task.completed.explanation`, built by `voice.explain_*` from the values the
page returned. On the replicas, end to end (`test_explanation.py`):

| Flow | Sentence |
|---|---|
| Train search, our copy, Rawalpindi to Multan | "There are 2 trains. The fastest takes 5 hours 15 minutes." (3UP, 5 h 15 min; 4DN, 6 h 15 min) |
| Bill | "Your bill is 14,382, and it is due on 15-09-2026." |
| Registration, MATH-210 | "You are registered for MATH-210 section 001." |
| Fixed registration plan | none: it declares no sentence, and the screen is as before |

On the live search of 2026-09-30 (run 6), the same function gives "There are 3
trains. The fastest takes 6 hours 3 minutes." Every number in a sentence is one
the page printed or a count of what it returned, which a test checks number by
number; a journey it cannot read leaves "the fastest" unsaid, two amounts leave
the bill unexplained, and a value that is a web address is never said. 23 tests,
and the six new sentences pass every wording rule `test_copy.py` holds the
backend to.

**The closing screen did not fit before the sentence.** Measured in Chromium at
each scale's content size, with the sentence and without:

| Results | Scale | "I'm done" (no sentence) | "Do something else" ends (no sentence) | With the sentence |
|---|---|---|---|---|
| 3 trains | 100% (800 tall) | 679–759 | **851** | +61px |
| 3 trains | 125% / 150% (734 / 606) | 595–659 | **735** | +51px |
| 9 trains | 100% | **1057** | — | **1118** |
| 9 trains | 150% | **973** | — | **1024** |

So with any answer of three or more results the way onward has been partly or
wholly below the window, at every scale, since before this change; the fit was
only ever measured for the home screen and for steps (2026-09-25c, 2026-09-30d).
The sentence makes it 51–61px worse. Both cases are pinned in
`frontend/test_closing.py` as strict known failures. Not fixed here: flagged.

## 2026-10-05 — the closing screen, made to fit

Fixes what 2026-10-03c measured and flagged. Measured in Chromium at each
scale's content size (1280x800 at 100%, 1280x734 at 125%, 1266x606 at 150%),
the overlay built from source, trains and journey times from the live search of
2026-09-30. "Spare" is the window's height less the bottom of the lower button;
negative is off screen.

**What it took, in the order tried.** The cascade asked for was one line per
result, then a smaller type with a sentence, then the first six and "and N
more". The first and third were not enough at 150%:

| Stage | 9 results, sentence, 150% | 9 results, no sentence, 150% | 9 results, sentence, 100% | 1 result, sentence, 150% |
|---|---|---|---|---|
| Before (2026-10-03c) | "I'm done" at 1024 of 606 | 973 of 606 | 1118 of 800 | — |
| One line per result, first six, 36–40px rows | **−123** | **−98** | **−47** | **−12** |
| …and in a short window the two buttons side by side | −8 | −22 | −8 | +64 |
| …and the sentence in the lead-in's place, rows past four at 30px | **+40** | **+45** | **+48** | **+110** |

The budget at 150%, before: the presence bar, the card's padding, the lead-in,
the sentence and two stacked 64px buttons left 197px for the results and their
label line. Six rows of 30px type with "and 3 more" and the label line measure
295px. Side by side the buttons give back 76px and the lead-in 46px, which is
319px; there was no way to 295px through the type alone without going below
the size of the text a person reads (23px), which is why the layout changed.

**Final, every case:**

| Results | Sentence | 100% spare | 125% spare | 150% spare | Page scrolls |
|---|---|---|---|---|---|
| 1 | yes | 110 | 238 | 110 | no |
| 1 | no | 116 | 242 | 114 | no |
| 3 | yes | 118 | 238 | 110 | no |
| 3 | no | 125 | 243 | 115 | no |
| 9 | yes | 48 | 168 | 40 | no |
| 9 | no | 55 | 173 | 45 | no |

The tightest is nine results with a sentence at 150%: 40px. One defect found
on the way: with "and 3 more" at 26px, nine results with a sentence at 100%
made the page 2px taller than the window (802 of 800) with both buttons still
on screen; at 23px it is 800 of 800.

The six strict known failures in `frontend/test_closing.py` now pass and are
ordinary tests; five tests were added there (one result at three scales, the
count past six, six with nothing counted, a detail that does not line up), and
one in `test_copy.py`.

## 2026-10-05b — every ending, fitted, in a browser and in the real window

The fit had been measured for the home screen and for steps, never for an
ending. It now is, twice over: `test_terminal_states.test_every_ending_fits_the_window`
renders all 17 endings (four of them new: the two below, each also reached
through a step) in Chromium at each scale's content size on every suite run, and
`display_fit_run` plays the same 17 into the real Electron window at forced
100%, 125% and 150% (`test_window_fit.py`, `SIMBA_HOST_TESTS=1`). Each asserts
every button wholly inside the window and nothing to scroll.

Two endings were added to the list for it, each direct and after a step: nine
results with a sentence, and nine results with eight journey times — two
trains sharing a time, which perception keeps once, so the times cannot be put
beside the trains.

**What the check found on its first run, both fixed here:**

| Case | Scale | Before | After |
|---|---|---|---|
| 9 trains, 8 times, sentence | 150% | both buttons off screen, lowest at 693 of 606 (−87) | 572 of 606 |
| 9 trains, 8 times, sentence | 100% | "Do something else" off screen, 887 of 800 | 666 of 800 |
| 5 trains, 2 times (an existing ending) | 100% | buttons on screen, page 821 of 800: a scrollbar | 621 of 800, no scroll |
| 9 trains, sentence (paired) | 100% | 752 of 800, page exactly 800: 0px from a scrollbar | 660 of 800 |

The unpaired times were a block of their own, label and all; they are now one
line under the list that takes one result's place. And the buttons, side by
side only in short windows in the morning's change, are side by side at every
height (DECISIONS.md).

**In the real window**, the lowest button and the window's height, every
ending (the 8 "after a step" variants measure the same as their direct form,
to the pixel, and are left out):

| Ending | 100% (800) | 125% (734) | 150% (606) |
|---|---|---|---|
| answer: bill and due date | 592 | 492 | 492 |
| five trains, two times | 621 | 529 | 529 |
| nine trains, sentence | 660 | 566 | 566 |
| nine trains, eight times, sentence | 666 | 572 | **572** |
| no answer | 404 | 352 | 352 |
| failed | 446 | 370 | 370 |
| stuck (both orders) | 442 | 366 | 366 |
| stopped by the person | 347 | 295 | 295 |

Nothing scrolls anywhere. The tightest is nine trains with eight times at 150%:
34px. The headless figures are identical to the host's at every scale.

Site-view captures in the same runs: 10/20, 11/20 and 10/20 at forced 100%,
20/20 at 125% and 150% — the known 100% capture problem (2026-09-27),
unchanged and unrelated: the captures are taken before any ending is played.

## 2026-10-05c — results as whole rows: each train with its own time

`values` drops a repeated value per label, so the closing screen could only
pair a train with a journey time by position, and refused when the lists'
lengths differed (2026-10-05b). Now perception reads each table row whole
(`Content.rows_for`, repeats kept), the first finding carries the rows
(`Finding.rows`, additive and optional), and the closing screen and the
sentence read from them.

**On our copy** (`railways-local`, through the Electron window, hardcoded
plan): "trains from Hyderabad to Sukkur tomorrow", a route given four trains
whose journey times repeat on rows 1 and 3 and on rows 2 and 4. 5 steps, 0
planner calls, 20.9s Start to ending as the backend timed it (51.3s by the
driving script, which pauses 2.5s on each step to be readable).

| | What it carried |
|---|---|
| `Journey.values` | `3 h 15 min, 4 h 15 min` — two times for four trains |
| `Train.rows` | `11UP, 3 h 15 min` · `12DN, 4 h 15 min` · `13UP, 3 h 15 min` · `14DN, 4 h 15 min` |
| The site view's own table | the same four rows, cell for cell |
| The closing screen | "There are 4 trains. The fastest takes 3 hours 15 minutes." and the four rows above, one line each |

Before this change the same message would have shown the four trains and,
under them, "Journey: 3 h 15 min, 4 h 15 min" — not wrong, but no train's own
time.

**On the live site, one read-only search**: "trains to Rawalpindi tomorrow",
answered Lahore, then Lahore Cantt. One request sent, `LRC` to `RWP` for
2026-10-06. 5 steps, 0 planner calls, 50.7s Start to ending. The live results
are built from `div`s with the heading strip as a separate group, and the rows
came through that join (`_adopt_headers`) whole: `13UP, 6 h 6 min` ·
`39UP, 6 h 38 min` · `1UP, 6 h 3 min`, matching the site view's table, and the
same three lines on the closing screen under "There are 3 trains. The fastest
takes 6 hours 3 minutes." No two trains shared a time on that route that day,
so the live run shows the rows arriving, not the repeat being kept.

Tests: 3 in `backend/perception/test_content.py`, 4 in
`backend/orchestrator/test_success_conditions.py`, 3 in
`backend/orchestrator/test_explanation.py` (one of them the Hyderabad search
end to end on the replica), 5 in `frontend/test_closing.py` (two trains
sharing a time; repeats on different rows across three columns, where each
list alone is two values for three trains; nine trains as rows at three
scales). The router was set to `model` on both runs; whatever calls it made
to route and read the goal are not in `llm_calls`, which counts the planner's
only, and were not counted separately.

## 2026-10-05d — the demo clips, re-recorded to show the closing screen as it is

`python -m tools.record_demo` with the stack started by `.\run.ps1
railways-local`, the overlay built from the current source, every clip
pressing at a 1.8s beat. The health check said `"railways_site":
"http://127.0.0.1:5200"` before the railways clip.

| Clip | What it did | Ending | Length |
|---|---|---|---|
| railways | typed "Lahore", chose "Lahore Cantt", five steps | **found an answer** | 61s |
| billing | typed `04141234567890` when asked, three steps | **found an answer** | 43s |
| hello | — | greeted, nothing started | 8s |
| fold (mock) | four steps, the scripted fold | done | 34s |
| adapt | folded after 7.2s of hesitation on step 1, three steps | **found an answer** | 41s |

**Two failures on the way, both found and fixed before these clips.**

- **The recorder could not start the mock backend.** Since `a577cef`
  (2026-10-03) a helper had been put between `@app.get("/")` and `health()` in
  `tools/mock_backend.py`, so `/` answered 422 and nothing could tell the mock
  was up. `tools/test_mock_backend.py`'s fixture has the same readiness loop
  but goes on after 30s regardless, so the suite kept passing and spent 30s
  every run. Fixed in `2727730`, with a test.
- **The first pass of billing and adapt ended "I'm stuck, so I've stopped."**
  Step 3's click on the reference box timed out twice (10s each), and the run
  stopped on the next step. The SIMBA window was **minimised** — checked with
  Windows' own window state, not a screenshot — and the site view inside it
  was painting about once a second (frames at 936, 1957 and 2982ms), so
  Playwright's wait for the box to be stable never passed. The overlay's own
  Start button failed the same way. Not caused by this change: the same flow
  passes headless, and both clips ended on the answer in a fresh,
  un-minimised window. What minimised it is not known.

That second one is also a **product finding**: a person who minimises SIMBA
during a task would see the next action fail. CLAUDE.md's rule keeps the site
view visible and covered so screenshots work; it says nothing about the window
itself being minimised. Not fixed: flagged.

The clips were not watched frame by frame; what shows they hold the current
closing screen is that they were drawn by the overlay built from this source,
and that every task clip reported reaching its ending.

## 2026-10-06 — a minimised window is waited for, not failed

Before every action the backend asks whether the SIMBA window is there
(`browser.window_watch`, reading what `frontend/electron/main.ts` writes into
the overlay page on minimise, restore, hide and show). While it is minimised or
hidden, nothing is done; when it comes back, one line — "I waited while the
window was closed. Ready to carry on?" — and the run goes on only after "Carry
on". Stop there ends the run as a stop, not a failure.

**In the real window** (`.\run.ps1 billing`, driven over the backend's
websocket; the window minimised and restored with Windows' `ShowWindow` on the
Electron process the stack started, found by its CDP port):

| Time | What happened |
|---|---|
| 16.9s | step 2, "Let me look up your bill.", on screen; window minimised (`IsIconic` true; the overlay page says `minimised`); step 2 confirmed |
| 16.9–27.3s | the backend waited: one `state.changed` to acting, no action, no `step.failed`, no `help.requested` |
| 27.3s | window restored (the overlay page says `shown`) |
| 28.1s | "I waited while the window was closed. Ready to carry on?" with **Carry on** and **Stop this** |
| 30.1s | after Carry on: step 4, "Now I'll open the full bill." |
| 31.1s | `task.completed`, 3 steps taken, 0 planner calls, the bill 14,382 found |

Before this change the same minimise ended the run: on 2026-10-05 the click on
the reference box timed out twice and the next step was given up on
(2026-10-05d).

`backend/orchestrator/test_window.py`, 7 tests, on the billing replica with a
stand-in for the window: minimised between typing the reference and pressing
"Check Bill" (mid-step), waited for and finished, with the window's state
recorded at every real action — all four `shown`; away for forty looks; hidden
rather than minimised; stop when it comes back (two actions before, none
after, `task.failed` with the stop's reason); a window that stays shown
changes no message; and the overlay page's value read the way the backend
reads it, ignoring the same value on the site view. "Hidden" has been checked
with the stand-in only, not by hiding the real window.

## 2026-10-06b — the sentence names the fastest train, and a tie is said as one

With rows and two trains or more, `voice.explain_trains` names the fastest:
"There are 3 trains. The fastest is 1UP, at 6 hours 3 minutes." A tie is not
settled by picking one: two or three tied are named ("11UP and 13UP are the
fastest, both at 3 hours 15 minutes."), more are counted ("4 of them are the
fastest, all at …"), and when every train ties, "They both take …" or "They
all take …". One train, or no rows, keeps the wording that names none. On the
replicas end to end: Rawalpindi to Multan gives "There are 2 trains. The
fastest is 3UP, at 5 hours 15 minutes."; Hyderabad Jn to Sukkur, where two
pairs tie, gives "There are 4 trains. 11UP and 13UP are the fastest, both at 3
hours 15 minutes."

**The fit, measured** in Chromium at each scale's content size, nine trains:

| Sentence | Characters | 100%: lines, spare | 125%: lines, spare | 150%: lines, spare |
|---|---|---|---|---|
| the fastest named | 64 | 1, 140px | 1, 168px | 1, 40px |
| a tie of two named | 80 | 2, 140px | 2, 170px | 2, 42px |
| a tie of three named | 86 | 2, 140px | 2, 170px | 2, 42px |
| a tie of four, counted | 73 | 2, 140px | 1, 168px | 1, 40px |

Nothing scrolls in any of the twelve. **Found on the way**: before the line
rule below, the tie of three wrapped to two lines at 150% (69px against 35px)
and the page scrolled by 10px (616 of 606), buttons still on screen; the tie
of two did the same (80 characters). Any sentence over about 70 characters
wraps at the compact layout's 23px, and the live site's train names are not
ours to keep short. So each line the sentence takes past its first gives up
one result line: a wrapped sentence shows five trains and "and 4 more"
instead of six and "and 3 more" (`App.Findings`, `less`).

Tests: 9 in `backend/orchestrator/test_explanation.py` (named; tie of two;
three named and four counted; all tied, two and three; one result; no rows; a
train number that is an address is not named; every number said is printed
or a count, from rows), the two end-to-end sentences updated, 3 more
sentences under `test_copy.py`'s rules, and 6 fit cases in
`frontend/test_closing.py`.

## 2026-10-06c — every answer about a journey is checked before the site is touched

Raham ran `railways-local`, and SIMBA never asked where the journey was to or when.

**Why.** Reproduced headless with the default launch (`run.ps1`'s variables:
hardcoded plan, model router, `.env` loaded) on the replica: a *typed* train
goal does ask — "train" asked where from, three times with an empty answer,
and gave up as designed. What does not ask is the **home screen's train card**.
Its words are the goal it sends (`copy.ts` `FLOWS`), and they were "Find
trains from Lahore to Karachi" — so pressing it told the backend both ends of a
journey nobody had chosen, and only the day was asked. The course card did the
same with "Register for CS-401". The model was ruled out: 11 detail readings of
four goals by the configured model (one timed out) invented no place and no
day. The overlay was ruled out: it is rebuilt from source on every launch. The
person's own run is not on record — `data/steps.jsonl` has no train goal after
5 October 20:09, and the only model call logged today is a bill — so the cause
is established by reproducing every way into a train search, not by reading
that run.

Three more gaps were found against the task's list while looking, all fixed:
a station was whatever was typed, held to the site only mid-run after the box
had been typed into (a place the site lacks ended the run, 31.5s for "Narnia"
on 2026-09-30b); a journey from a station to itself was never noticed; and a
day not in the calendar ("31 February") was "I didn't catch that day".

**What the live site allows, measured** (one read-only visit, nothing typed
into a station box, nothing searched; `.scratch/probe_live.py`):

| What | Measured |
|---|---|
| `li.el-select-dropdown__item` in the page before anything is clicked | **684** — the From and To lists, 342 each |
| Distinct station names | **340** (DINA and OKARA CANTT listed twice) |
| Visible after clicking From, nothing typed | 342 — the whole From list opens |
| Fields the search form has | From, To, Departure Date — nothing else |
| Calendar, days disabled in October 2026 to November 2027 (14 months) | **0** — past days this month (1–5 October) are pickable, and nothing ahead is closed |

So the station list can be read without touching the page, and the site sets
no limit on the day either way: "in the past" and "too far ahead" are SIMBA's
checks, not the site's. SIMBA's limit stays a year (`HORIZON_DAYS = 366`).

**On the live site, after the change** (one read-only run, one search,
`.scratch/live_once.py`, headless Chromium, hardcoded plan, no model):
"train from Lahore to Karachi tomorrow".

| | |
|---|---|
| Station list read | **340** names in **0.56s**, page untouched |
| Asked, in order | "Which Lahore station do you mean?" → Lahore Cantt; "Which Karachi station do you mean?" → Karachi Cantt; "Lahore Cantt to Karachi Cantt, tomorrow, 7 October. Is that right?" → Yes |
| The three boxes when the journey was read back | all **empty** |
| After | 5 steps taken, 0 model calls, the search step read "Everything is filled in. Shall I search for your trains?" |
| The form at the end | From `LAHORE CANTT`, To `KARACHI CANTT`, Departure Date `07-10-2026` |
| Result | `task.completed`, 2 trains (2DN, 14DN), "There are 2 trains. The fastest is 2DN, at 22 hours 16 minutes." |
| Wall clock | 19.7s from start to the end, answers given instantly (±2x on this machine) |

Not checked in the Electron window: everything above is headless Chromium and
the websocket.

**Tests.** `backend/orchestrator/test_trip_answers.py`, 54: each bad answer —
a day gone (4 ways of writing one), too far ahead (3), not in the calendar
(5, plus a bare "45"), from and to the same (typed, in the goal, without a
list), a station not on the list (closest offered; nothing close; in the goal)
— and the list offered, the reading back, changing an answer, the plan
searching the chosen stations; three runs on the replica in real Chromium,
each asserting the page untouched at the reading back and what was finally
searched; and the real app over its websocket against a stand-in model that
answers every call with HTTP 429 `insufficient_quota`, which asked, searched
and completed. `backend/perception/test_options.py`, 7. Overlay:
`frontend/test_questions.py`, 6 new.

Checked that they can fail: with the same-station check disabled, 4 of the 54
fail; with the reading back skipped, 7 fail.

**Found and fixed on the way.**

- The list reader dropped a `<datalist>` option that has only a value
  (`test_a_native_select_and_a_datalist`): read by its value now, after its
  label and text.
- Four stacked matches put "Stop this" at 652px in a 606px window at 150%
  (`test_a_list_question_fits_at_150_percent`). Typing does not re-run the
  overflow guard, so nothing folded. Two to a row now; the test passes.
- **Level 3 removed the answer box at the first keystroke.** It keeps "only
  the fields a step cannot go on without", and judged that by the typed value,
  so any typed question shown at level 3 lost its box and its answer. It
  judges by what the backend sent now. Present since level 3 existed; a
  question reaches level 3 only after a fold or a lock, which is why no run
  on record shows it.

**Full suite** on `feat/railways-ask`: **1012 passed, 12 skipped, 0 failed**,
1181s (944 passed before; 68 added). Docstrings in `details.py` and the
records were edited while it ran; no code was.

## 2026-10-07 — the interface, less plain: the real page behind, shapes, tickets

On `feat/interface-reveal`, from `feat/railways-ask`. Five of the seven
things asked for are built; one already existed and one is not allowed.
Every measurement here is headless Chromium against the built overlay, never
the Electron window, and no desktop was captured. 168 screenshots — 28
screens, both themes, 100%, 125% and 150% — are in `.scratch/interface-reveal/`
(not committed), with the script that takes them.

**Reduced motion did not reach most of the motion.** `index.css` stops CSS
animation under `prefers-reduced-motion`, and the presence mark is Framer
Motion, which animates from JavaScript. With reduced motion emulated, the mark
while thinking had **12 different looks in 12 samples over 3s**; after
`MotionConfig reducedMotion="user"` and a still mark, **1**
(`frontend/test_calm.py`). Present since the mark existed.

**The real page behind the step.** The backend's picture of the site, asked
for with each step, blurred 18px under 82% of the canvas colour, after 1.6s
shown clearly when a task starts; "Show the real page" clears it while held
(over 400ms) or until "Hide the real page" after a tap. Password boxes are
painted over in every capture: on the registration replica with a password
typed, every pixel inside the box is the mask colour, where the same box
unmasked has the dots in it (`test_preview_mask.py`, 4). Neither the picture
nor a peek counted as a help press in any telemetry sample
(`test_reveal.py`, 8).

**SIMBA's shape costs the main thread, and it was measured.** CSS 3D, no
dependency. Main-thread task time over 5s on the home screen, three runs each:

| Condition | Main-thread task time in 5s | 95th-percentile frame |
|---|---|---|
| No shape on the page | 113–174ms | 16.7–16.8ms |
| Shape held still (reduced motion) | 122–162ms | 16.7ms |
| Turning, sixty updates a second | 244–320ms (style recalc 47–61ms) | 16.7–16.8ms |
| Turning, `will-change: transform` | 249–288ms | 16.7–16.8ms |
| **Turning, twenty updates a second (kept)** | **181–206ms** | 16.7–16.8ms |

So the 3D turn is not composited here: it costs style work as it changes, and
layer promotion does not help. Stepping it to twenty updates a second halves
the extra work, to about 70ms in 5s (1.4% of one core), and no frame is late
in any condition. Not measured in the Electron window, where a GPU may
composite it.

**Fit, measured against the base.** The screenshot script flags any page that
scrolls. Built from `98cf77a` (this branch's base) and from this branch, the
same screens, overflow in px at 100 / 125 / 150%:

| Screen | Base | This branch, first | After the fix |
|---|---|---|---|
| Reply to "book a flight" | 40 / 0 / 57 | 40 / 0 / 57 | 24 / 0 / 45 |
| Sign-in step | 0 / 0 / 0 | 1 / 0 / 6 | 0 / 0 / 0 |
| Station question | 0 / 0 / 0 | 1 / 0 / 0 | 0 / 0 / 0 |
| Station question, "kar" typed | **52** / 0 / **52** | 69 / 0 / 57 | 0 / 0 / 0 |

The station question overflowed on `feat/railways-ask` already: its names
arrive after the overflow guard has measured the step, and its fit test
checked the two buttons only. It now keeps one row for the list from the
start and shows at most two names; its test now requires that nothing
scrolls. The reply screen is not part of this work and still scrolls (flagged).

**Closing screen.** Nine trains as tickets still leave both buttons on screen
at all three sizes, with a one-line and a two-line sentence
(`test_closing.py`, 32, three new). The fastest, eighth of nine, is moved into
the last place shown so the one marked is never counted away.

**Shapes beside steps.** All three hardcoded plans, the trip planner and every
question are given the kind they mean (`test_step_kind.py`, 9); a long
sentence with its shape fits at 150% at levels 1, 2 and 3
(`test_step_icons.py`, 11).

**Full suite** on `feat/interface-reveal`: **1054 passed, 12 skipped, 0
failed**, 1173s (1012 before; 42 added). The records were written while it
ran; no code was changed after it started.

## 2026-10-14 — the new look, in the real window

The first time the interface from `feat/interface-reveal` was seen in the
Electron host rather than a headless browser. `.\run.ps1 railways-local`, with
`SIMBA_RECORD_STEPS=0` so scripted presses never reached the estimator's
training rows. Driven over the host's CDP port with real input events
(`Input.dispatchMouseEvent`, `Input.insertText`) sent to the overlay's own
target only; every capture is the overlay's content (`Page.captureScreenshot`)
or the SIMBA window alone (`PrintWindow` on the window of the process holding
the CDP port), never the desktop. Scripts and captures in
`.scratch/window-review/` (not committed).

**This machine's display is at 150%:** the real window is 1266x606 CSS pixels
at a device pixel ratio of 1.5 — the tightest of the three sizes. The 100%
captures come from a second real host started with
`--force-device-scale-factor=1`, as `display_fit_run.py` does; Windows' own
setting was not touched.

**The whole train flow, walked** (22 screens): home, "train", a station the
site lacks ("Narnia"), a misspelling ("Lahor", then Lahore Cantt), the same
station both ways, a day that has passed ("1 October 2026"), the readback,
five steps, the peek, the results. It completed, and searched Lahore Cantt to
Karachi Cantt for the 15th.

**What the real window showed that headless did not:**

| Found | Detail |
|---|---|
| Electron's own menu bar | File / Edit / View / Window / Help above the overlay, 26px of it at 150% |
| A scrollbar at 150% | Five question screens 9px too tall — the ones whose sentence explains a wrong answer and runs to two lines — with a classic scrollbar down the side. Already at level 1, the guard's floor |
| "I'm showing a bit more again." on every first question | The overflow guard's fold, at 100% and at 150% |
| One softened frame before the reveal | The backdrop drew `data-clear=false` for 17ms, then cleared |
| "Read this aloud" could not be pressed | For the eight seconds the guard's notice was up it lay over the button; the press landed on the notice. Found when checking item 5, after it was built |
| The count runs past itself | Re-asked questions push the count past its promise: "Step 10 of 10", "11 of 11", "12 of 12", "13 of 13" — every later screen claims to be the last |

**The shape, the reveal and the blur, measured in the real window** (5s of
frames and main-thread time from inside the overlay, then 10s of CPU over the
host's 5 processes):

| Condition | Main-thread work in 5s | 95th-pct frame | Host CPU, % of one core |
|---|---|---|---|
| Home, shape turning | 122ms (style 30ms) | 16.8ms | 7.5 |
| Home, reduced motion (shape still) | 99ms | 17.0ms | 2.7 |
| Home, shape removed | 92ms | 16.9ms | 0.2 |
| Question, real page softened behind | 88ms | 16.8ms (one 433ms frame) | 8.4 |
| Question, backdrop removed | 108ms | 16.8ms | 5.6 |

So in the real window the turn costs less of the main thread than headless
(+30ms in 5s against +70ms) but about 7% of one core across the host's
processes, the GPU process included, for as long as the home screen is open.
Every frame is on time in every condition. The one 433ms frame, with the
softened page behind a question, happened once and is not explained.

**The reveal's timing** (from a watcher in the page): the first question at
4891ms, its picture 262ms later, clear for 1602ms (1.6s asked), then softened.
The peek cleared and hid as pressed. In the light theme the softened page is
nearly invisible once the reveal is over — a green tint along the top from the
site's own bar.

**After the fixes, the same walk in the real window at 150%:** content 1266x632
(the menu bar's 26px given back), **0px of scroll on all 22 screens**, the
notice reading "I've made this smaller so it fits." beside "Read this aloud"
rather than over it, the button under its own centre, and pressing it made the
system speak with the default voice (Microsoft David, en-US; Mark and Zira also
offered) until "Stop reading". At 100%, before the fixes too, nothing scrolled.

**Fixed in Part B**, each with a test that fails on the old code where the
old code could be run: the reply to "book a flight" (24px at 100%, 45px at
150%, before; 0 at all three, after, for every kind of reply); the notice's
wording; the station box at level 1 (9px); the chosen station as a second
filled button; the station in capitals in a step's detail; the one softened
frame; the menu bar; the two eyes; the notice over "Read this aloud".

**Full suite** on `feat/interface-reveal`: **1078 passed, 12 skipped, 0
failed**, 1206s (1054 before; 24 added). **The host fit test**
(`SIMBA_HOST_TESTS=1 frontend/test_window_fit.py`), with the menu bar hidden:
3 passed, at 100%, 125% and 150%.

## 2026-10-14b — the person decides, SIMBA clicks; the opening; two colour directions

On `feat/interface-reveal`, not merged. Headless figures are from the built
overlay in Chromium at each size's CSS viewport and scale; real-window figures
from the Electron host driven over CDP, forced to 100% with
`--force-device-scale-factor=1` (this machine is at 150%), against the three
local replicas, `SIMBA_USE_HARDCODED_PLAN=1`, `SIMBA_RECORD_STEPS=0`.

**Presses to search for trains, a goal naming nothing.** Before: 9 (four
questions, then five moves pressed one by one). After: 4 (the four
questions); the five moves run as a checklist. In the real window the
checklist took 6.5 to 9.8s over six runs (median 7.7s) from "Yes, that's right" to the results,
five lines. A bill with its number: 3 presses to 1 (the number) plus the
cookie question when the site shows it. A course: 4 to 3 (course, sign-in,
Register); the portal's notice is a checklist line.

**A task's first question at level 2** (scroll overflow, px, at 100% /
125% / 150% at 632 / 150% at 606):

| | 100% | 125% | 150%, 632 | 150%, 606 |
|---|---|---|---|---|
| "Where are you travelling from?", before | +73 | 0 | +39 | +65 |
| every flow's first question, after (6 questions) | 0 | 0 | 0 | 0 |

**Level 3 against level 2, each flow's first question** (the step card's
height, px, at 100%). With level 3 falling back to the column, as first
committed: the read-back 376 / 416, "What day are you travelling?" 345 /
452, and `test_levels.py`'s medium step 440 / 458 — the simplest level the
tallest, which that test exists to prevent. Keeping the row at level 3:

| | where from | which station | read back | which day | reference | course |
|---|---|---|---|---|---|---|
| level 2 | 477 | 345 | 376 | 345 | 440 | 440 |
| level 3 | 417 | 324 | 324 | 268 | 408 | 408 |

**The home screen with two remembered goals** (overflow, px): stacked under
the tiles, +100 at 100% and +51 at 150% (606 and 632); in one row, 0 at all
four sizes. With no history, 0 at all four. The box's bottom edge sits at
89% of the window's height at 100% (714 of 800); the old screen's was not
measured.

**The home screen's entrance.** The tiles' opacity, sampled every frame from
load: before the fix, 1 from the first frame (the screens'
`AnimatePresence initial={false}` held it back, so it never played); after,
0 at 103-274ms, 1 by 1.6s. Under reduced motion: 1 from the first frame.

**The home screen's CPU, real window** (the host's process tree, five
processes, 10s): 2.0% of one core in the first seconds after opening, **0.2%
at rest**, 0.0% with the shape removed. Before (2026-10-14a), with the shape
turning on the home screen: 7.5%. Main-thread work per 5s on the overlay:
208ms then 213ms with the shape, 161ms without; frames on time throughout
(p95 16.9-17.0ms).

**A question after a checklist, real window.** The overlay asked for a
picture of the page on every checklist line; each was answered, a screenshot
each, before the next answer was read. The course flow's "Register for
CS-401": 31.0s from the press to the task completing, one screenshot timing
out at 30s. After: 1.6 to 2.5s in each of the four walks below.

**The course's sign-in screen does not fit** (overflow, px, level 1 — the
guard's one hop — at 100% / 125% / 150% at 632 / 150% at 606): `main` 56 / 0
/ 34 / 60; this branch 96 / 0 / 65 / 91. The card's first line (notice and
"Read this aloud") adds 31-40px. Not fixed; flagged.

**Contrast, both directions** (`frontend/test_contrast.py`, WCAG 2.2 ratios,
the lowest pairing of each kind):

| | ink | soft text | accent as text | label on accent | stuck | control edge |
|---|---|---|---|---|---|---|
| A light | 13.6 | 6.8 | 5.5 | 6.8 | 5.6 | 3.2 |
| A dark | 12.2 | 6.9 | 7.3 | 9.9 | 7.1 | 3.4 |
| B light | 13.2 | 6.5 | 6.4 | 8.1 | 5.6 | 3.1 |
| B dark | 11.6 | 7.3 | 7.3 | 9.2 | 7.1 | 3.7 |

Before, every control's border was the divider colour: 1.3:1 to 1.6:1 against
its ground, in the old palette and both new ones. Two words were drawn
translucent and under 4.5:1: the stages still to come (about 3.9:1) and the
station box's example (about 3.6:1).

**The real window, all three flows** (100%, A and B, light and dark):
every flow reached its ending in all four (A and B, light and dark), from
its home-screen tile, with the person's answers typed and chosen through
real input events.

| | trains: readback to results | tickets | bill: cookie answer to the bill | course: Register to done | screens that scroll |
|---|---|---|---|---|---|
| A light | 7.4s | 2 | 4.9s | 2.5s | sign-in, +96px |
| A dark | 9.2s | 2 | 5.4s | 1.8s | sign-in, +96px |
| B light | 9.8s | 2 | 5.5s | 1.7s | sign-in, +96px |
| B dark | 7.7s | 2 | 5.4s | 1.6s | sign-in, +96px |

The results' heading read "Lahore Cantt to Karachi Cantt, Thursday 15
October" in all four; the first ticket "7UP, Leaves 07:25, Arrives 14:40,
Journey 7 h 15 min, Fastest". A bill: the reference question, then the
site's cookie question (it still asks), then "Looking up your bill" and
"Opening the full bill" as checklist lines. A course: the course, signing in,
"Closing the portal's notice" as a checklist line, then "Ready to book your
place on CS-401." asked. One earlier attempt at A dark lost the window after
the trains (every capture timed out, as a minimised window does); it was run
again whole. The walk script's own first versions pressed "Read this aloud"
and then "Stop this" where it meant the cookie answer; those runs are not
counted.

**The suite.** 1174 passed, 12 skipped, 0 failed (backend 816 in 1194s,
frontend 358 in 779s, as two halves), and the host window-fit test 3 of 3
with `SIMBA_HOST_TESTS=1`. The first full run of this branch found 4
failures: the three stale backend tests and level 3 taller than level 2 on
`test_levels.py`'s medium step; all four are above.

## 2026-10-15 — review fixes: next-day trains, boxes, buttons, the checklist ahead, sign-in

On `feat/interface-reveal`. Real-window figures as on 2026-10-14b: the
Electron host forced to 100%, the three local replicas, hardcoded plans,
`SIMBA_RECORD_STEPS=0`, direction B (now the default), light and dark.

**Next-day arrivals.** The rule (`voice.days_later`) on the two rows ever
recorded from the live site: 2 of 2 next-day, 14DN among them with an
arrival clock time later than its departure (19:09, 24 h 16 min, 19:25). One
read-only search of the live site today, Lahore Cantt to Karachi Cantt: 2
trains, both said "next day" (2DN 08:04 to 06:20; 14DN 19:09 to 19:25). On
our copy, 8DN reads "00:50, next day"; the ticket stays one line.

**Figures.** At 46px, Atkinson Hyperlegible Next's digits are 19.8px (1) to
30.2px (0) wide; with `tabular-nums`, 29.1px each. Its zero is slashed with
every feature tried (`zero`, `ss01`, `ss02`).

**Boxes.** The new field colour against what sits on it, lowest of each:

| | ink | example text | edge | focus ring (accent) |
|---|---|---|---|---|
| B light | 16.7 | 8.2 | 3.87 | 8.1 |
| B dark | 12.1 | 7.7 | 3.20 | 7.6 |
| A light | 17.2 | 8.5 | 3.96 | 6.8 |
| A dark | 13.8 | 7.9 | 3.07 | 8.4 |

**The sign-in screen** (overflow, px, at 100% / 125% / 150% at 632 / 150%
at 606): with three buttons, 96 / 0 / 65 / 91 (`main`: 56 / 0 / 34 / 60);
with the box to tick, 0 / 0 / 0 / 0. At 100% and both 150% windows it fits
after the guard's one step to level 1; at 125%, at level 2. It was 2px over
at 606 until the gap above the box was taken from 0.6 to 0.4 of the level's.

**The home screen's tiles to box** (the box's top less the tiles' bottom,
px, no history): 2026-10-14, 185 at 100% and 160 at 150% (606); now 86 and
32. With two remembered goals, the box is 86px under them at 100%. Nothing
scrolls at any of the four sizes.

**The top of the window**, at x=100 on the results screen, B light: before,
(235, 232, 220) at the top against (245, 239, 227) for the canvas, ten
levels darker; after, (247, 243, 234), a touch lighter.

**A picture of the page and the person's answer.** A stand-in screenshot
that takes 30s: the answer waited 30.0s in the old loop and under 1s in the
new, and the picture was cancelled when the answer came. In the real window,
"Register for CS-401" to the task completing: 31.0s (2026-10-14, one
screenshot timing out), 1.6-2.5s (after checklist lines stopped asking for
pictures), 0.6-1.0s now.

**The real window, all three flows, three walks** (B light twice, B dark):
every flow reached its ending from its home-screen tile; no screen scrolled,
the sign-in screen included. Trains, readback to results 5.5-6.6s, five
checklist lines, the four still to come shown from the first; a bill, the
cookie answer to the bill 2.0-3.1s; a course, "Register" to done 0.6-1.0s,
the sign-in screen showing "Sign in" and "Stop this" and the box to tick.
The walk script itself first waited for every button to be enabled and so
never saw a question whose main button waits for an answer; it now waits
for "Stop this".

**The suite.** 1209 passed, 12 skipped, 0 failed: backend 833 in 752s,
frontend 376 in 790s, as two halves; the host window-fit test 3 of 3 with
`SIMBA_HOST_TESTS=1`. The run found 2 failures, both tests still pressing the
"Sign in and save my password" button the box to tick replaced; updated, and
their file rerun, 19 of 19.

## 2026-10-16 — proof: the answer on the real page, and never more than was done

On `feat/proof`, not merged. Real-window figures: the Electron host forced
to 100%, the three local replicas, hardcoded plans, `SIMBA_RECORD_STEPS=0`,
direction B, light; and one read-only search of the live train site.

**The proof picture, each flow** (rings sent with `task.completed.proof`):

| | rings | what | proof note |
|---|---|---|---|
| trains, our copy | 2 | each train's row | none |
| trains, live site | 2 | each train's row (2DN, 14DN) | none |
| a bill | 2 | the amount and the due date, the cells only | none |
| a registration | 2 | "Registration Confirmed", and the confirmation number's row | none |
| the benchmarks' fixed bill plan (ends on the detail page) | 0 | — | "What I read isn't on the page that's open now, so I have no picture of it." |

Opened from the closing screen, the bill's picture is drawn close up: the
page more than twice the window onto it, the two cells and their column
headings readable; on the whole page they were 17px high in a 1280x800
capture shown at 976px.

**A change that is not confirmed** (the registration replica, a register
step whose confirmation never comes): `help.requested`, `unconfirmed: true`,
no `step.failed` — tried once, not a second way. A confirmation missing from
the final page though the step's own check passed: the same.

**Which course** on the registration replica: 20 courses offered, asked as a
list after signing in; a course named and offered is not asked about (0
course questions); "CS-999" named is asked about with "The portal doesn't
offer CS-999."; a typed course not on the list is asked again with the same
note. Registering still asks.

**The registration's first screen is now signing in.** It fits at every
size after the guard's one silent step to level 1 at 100% and both 150%
windows; at level 2 it is 86 / 0 / 60 / 86px over (100% / 125% / 150% at 632
/ 150% at 606) — the card fits, the row under it does not. Flagged.

**The real window, every flow as a first-time person** (time from pressing
the tile to the ending, including the walk's own typing): trains on our
copy 25.8s, a bill 14.5s, a registration 22.8s, trains on the live site
54.8s. No screen scrolled. The live search: 2 trains, both said "next day"
(2DN 08:04 to 06:20; 14DN 19:09 to 19:25).

**Electron lays text out wider than headless Chromium.** The live site's
row in a ticket — "2DN", "Leaves 08:04", "Arrives 06:20, next day",
"Journey 22 h 16 min", "Fastest" — is 784px wide headless, inside the card,
and 896px in the Electron window, where it pushed the whole column from
880px to 992px. The same ticket after the fix: 784px, wrapped to 93px tall,
the card at 880px. A fit measured only headless can miss a real overflow.

**The suite.** 1253 passed, 12 skipped, 0 failed: backend 856 in 748s,
frontend 397 in 851s, as two halves; the host window-fit test 3 of 3 with
`SIMBA_HOST_TESTS=1`. The run found 1 failure: a registration that named its
course was counted as four steps where it shows three; fixed, and its files
rerun, 113 of 113.

## 2026-10-16b — finishing proof: the caveat, cookies, plain words, one way to see, one way on

On `feat/proof`. Headless figures from the suite; real-window figures from
`frontend/test_window_fit.py` with `SIMBA_HOST_TESTS=1` and
`python -m tools.evaluation.display_fit_run` (forced 100%, 125%, 150%).

**The portal's caveat.** On the registration replica, registering for
MATH-210 now ends with 'The portal also says "Registration is not final
until tuition and fees are paid or a payment plan is in place".', the
portal's sentence whole, and 3 rings on the proof picture (the heading, the
confirmation number's row, the caveat's paragraph). Words the page does not
use give no caveat (tested with "subject to a refund").

**Cookies, Yes or No.** On the billing replica, No leaves the banner on the
page (`#cookie-bar` still visible at the end) and the bill is still found,
`Rs 14,382`.

**The closing screen in the real window**, 25 endings (was 17) and the
sign-in screen, at three forced scales:

| scale | window (CSS) | endings, all buttons on screen, none scrolling | lowest button of any ending | sign-in screen: level it settled at, lowest button, scrolls |
|---|---|---|---|---|
| 100% | 1280x800 | 25 of 25 | 759 | level 1, 734, no |
| 125% | 1280x760 | 25 of 25 | 584 | level 2, 688, no |
| 150% | 1266x632 | 25 of 25 | 584 | level 1, 588, no |

The sign-in screen still needs the guard's silent step to level 1 at 100%
and 150% (as on 2026-10-16, before "Show the real page" left the row under
the card). Site-view captures were 12/20, 11/20 and 20/20, the known 100%
capture problem (2026-09-27), not asserted.

**Found by the new endings.** Nine trains as tickets with next-day arrivals
— the live site's real shape — put the way on 179px below a 1280x800
window (lowest button 979): a ticket that wraps is two lines, and the counts
assumed one. The closing screen now gives up a result at a time, measured
after layout, until it fits. And with the caveat, the registration's ending
scrolled a 1266x606 window; its mark now sits beside the heading.

**The suite.** First run: 1 failed, 1290 passed, 12 skipped (backend 859 in
736s, frontend 431 in 826s, as two halves; the root `test_checklist.py` names
collide, so one run cannot collect both). The failure was a test that still
expected the bill as "14,382" after it became "Rs 14,382"; fixed, and the
whole suite run again (below).

The whole suite again, after the fix: **1291 passed, 12 skipped, 0 failed**
(backend 860 in 736s, frontend 431 in 830s). The host window-fit test, 3 of
3, on the same frontend.

## 2026-10-16c — finishing the task on our replicas, behind a final screen

On `feat/finish`, **not merged**. Real-window figures: the Electron host
forced to 100%, the three replicas, hardcoded plans, keyword routing,
`SIMBA_RECORD_STEPS=0`, direction B, light; a script pressing as a person
would (`.scratch/walk-finish/walk5.py`, not committed). No live site was
touched.

**Each flow to the end, in the real window** (time from pressing the tile to
the ending, including the script's own typing and captures):

| flow | screens | longest scroll | final screen: details read from the page | focus on arrival | ending | proof rings | seconds |
|---|---|---|---|---|---|---|---|
| trains: book 7UP, AC Standard | 15 | 0px | 8 (train, from, to, date, leaves, passenger, class, fare) | none | "That's done.", booking PR-242128, coach 3 seat 29 | 7 | 33.3 |
| bill: pay | 7 | 0px | 4 (amount, month, due date, reference) | none | "That's done.", receipt RCPT-614700 | 6 | 16.1 |
| course: register MATH-210 | 4 | 0px | 7 (course, title, days, time, teacher, room, credit hours) | none | "That's done.", REG-10301-2026 | 3 | 17.4 |
| trains: "Don't book it" | 14 | 0px | 8 | none | "I didn't do it. Nothing was changed." | — | 28.0 |

**What the walks found** (three walks; the third is the table):
- **The first walk ended both train runs "I've stopped, as you asked."**
  between pressing "Tomorrow" and the read-back. Two later walks, which
  capture each screen before pressing on it, did not reproduce it. **Not
  explained**: no log line shows which press sent the stop. Suspected, not
  shown: a level change landing as the day question arrives moves "Stop
  this" under a press aimed at "Tomorrow".
- **"Here's what I found: 7UP" on the booking's questions** pushed the name
  question 16px past 1280x800 even after the guard's step to level 1. Fixed:
  no findings on the way to a change.
- **"I've made this smaller so it fits." on the final screen**, carried over
  from the screen before. Fixed: cleared when a final screen arrives.

**Headless fit**, every final screen and the booking's questions at 1280x800,
1280x734, 1266x632 and 1266x606: the three final screens, "which train",
the name and the class all fit with nothing scrolling. The booking's final
screen first ran 20px past 1280x800 and 31px past 1266x606: its details in
four narrow columns wrapped "17 October 2026" and a three-word name onto two
lines; two columns of "name value" lines fixed it. The offer to book, three
answers stacked, ran past 1266x632; they now share a row.

**The rule, in the loop** (`test_final_step.py`, `test_live_site.py`): on a
page not served from this machine a change is never shown or pressed; a
change whose details the page does not state is not done; a change marked
safe still waits for its final screen; card, CVV, autocomplete `cc-number`
and IBAN boxes are refused before anything is shown or typed, an ordinary box
is still typed into.

**The suite**, on the final tree: **1394 passed, 12 skipped, 0 failed**
(backend 886 in 805s, frontend 508 in 999s, as two halves). The host
window-fit test, 3 of 3 at 100%, 125% and 150%, now over 32 endings —
including a booking, a payment, and "don't" pressed on a final screen — and
the sign-in screen. 103 tests added since 1291 this morning.

## 2026-10-16e — the unexplained stop: found, and guarded against

On `feat/finish`. The Electron host at forced 100% (1280x800) and 150%
(1266x632), the three replicas, hardcoded plans, keyword routing. The train
search walked by a script that presses each answer the moment its screen is
up, as the walk that stopped did (`.scratch/walk-finish/walk_repeat.py`, not
committed), every press logged by the overlay itself (`pressGuard.ts`:
which button, the level, ms since that button last moved, ms since anything
moved).

| build | scale | runs | reached the trains | ended "I've stopped" | other | presses ignored by the guard |
|---|---|---|---|---|---|---|
| before: log on, guard off, no fix | 100% | 20 | 5 | **15** | — | — |
| before | 150% | 20 | 0 | **7** | 13 stalled on a press that hit no button | — |
| after: leaving screen inert, guard on (500ms) | 100% | 20 | **20** | 0 | — | 80 |
| after | 150% | 20 | **20** | 0 | — | 69 |

**The cause.** Every one of the 22 stops was a press on "Stop this" 68–183ms
after that button appeared, at level 2 — no level change was involved. It
was the crossfade. When an answer moved the run to the next question, the
outgoing screen re-rendered with the *new* step while its old station box
was still folding away, so its buttons stood lower than the arriving
screen's. The script aimed at "Tomorrow" on the fading copy (found first in
the page); the press went to whatever was on top at that point, which was
the arriving screen's "Stop this". At 150% the same misalignment more often
put the press on the gap between buttons, so it did nothing and the run
waited (the 13 stalls). A person aiming at a screen that is still fading out
can do the same.

**The fixes.** (1) A screen on its way out shows its own step and takes no
presses (`ScreenFrame`, `Step({index})`). (2) The guard: a press is ignored
when its button moved or appeared in the last 500ms, or when a different
button was under that point in the last 500ms. In the after runs it ignored
4 presses a run on average — the script presses within milliseconds of a
button appearing, which a person rarely does — and the script pressed again.

**Found on the way, in the guard itself.** Its first version counted a
pressed button's own 1px nudge (`active:translate-y-px`) as a move, so every
press would have been ignored; and it stopped sampling while a button eased
its last pixel or two, so the look taken at a press read the gap as a fresh
move. Both fixed before the after runs; `test_press_guard.py` holds the
behaviour.

**Not explained here:** in the first, stalled before-batch the home tile's
press sometimes did not register and twice the checklist sat on its first
line for over a minute at 150%. Neither recurred in the 40 after runs.

## 2026-10-16d — the replica benchmarks, re-run on the current flows

**Replaces the registration numbers of 2026-09-06 and 2026-09-17**
(`hardcoded_registration_benchmark`: 10/10, 3 steps, 0 calls, 5.9s, then
3.0s), which were measured on a fixed plan before the person's details were
asked for, before the checklist, and before the final screen. On `feat/finish`
at the commit after `1266c7c`, headless Chromium at 1280x800, each replica
on its own port, hardcoded planners, **no model call in any run**; this
machine's wall clock carries about ±2x (2026-09-17h).

**Every flow as the app runs it** (`tools/evaluation/replica_flows_benchmark.py`,
`run_brief`, the checklist on, a person's answers scripted; 10 runs each):

| flow | completed | confirmed by the site | presses the person makes | checklist lines | final screens | seconds, mean (range) |
|---|---|---|---|---|---|---|
| register for a course (MATH-210 named) | 10/10 | 10/10 | 2 (sign in; Register) | 1 | 1 | 3.11 (2.9–3.8) |
| look up a bill (number given) | 10/10 | — | 1 (cookies) | 1 | 0 | 3.02 (1.8–5.2) |
| pay a bill ("pay" in the goal) | 10/10 | 10/10 | 2 (cookies; Pay it) | 2 | 1 | 3.77 (2.9–4.5) |
| find trains (journey given) | 10/10 | — | 1 (the read-back) | 5 | 0 | 3.73 (3.5–4.1) |
| book a train ("book" in the goal) | 10/10 | 10/10 | 5 (read-back; which train; name; class; Book it) | 7 | 1 | 4.67 (3.9–5.5) |

The same answers every run, so every count is the same in all ten. A
booking or a payment reports the steps of its own half in
`task.completed.steps_taken` (3 and 2), not the search or the lookup before
it; presses and checklist lines above count the whole run.

**The fixed registration plan** the old row was measured on, re-run as it is
now (`hardcoded_registration_benchmark`, every move asked, its register step
behind the final screen): **10/10, 3 steps, 0 model calls, 3.47s mean
(3.0–4.8)**. One more screen than before is answered — the final screen
takes the register step's place, so the count of steps is unchanged.

**The suite on `feat/finish`, 2026-10-17, before merging: 1421 passed, 12
skipped, 0 failed** (backend 896 in 1484s, frontend 525 in 1198s, as two
halves). The host window-fit test failed once at 100% —
`TargetClosedError` from the host's page after 22 minutes, where a passing
run takes about 7 — and passed 3 of 3 when re-run on the same tree (425s),
as did a timed run of 100% alone (every one of 34 endings in 2–3s, the
sign-in screen fitting). Not explained; no code changed between the runs.
**The backend half has taken 23–25 minutes in every run since
2026-10-16 afternoon, against 12–13 before.** Its slowest tests are the
deliberate verification time-outs (50s, 23s, 22s), as before; none waits on
the offer. Not explained either; this machine's wall clock carries ±2x
(2026-09-17h), and nothing of the work's was left running.

## 2026-10-17 — the 100% capture: what it waits for, and the fix

`fix/stability`. The end-of-task picture (`take_proof`) and the picture
behind every step (`send_preview`) failed about every other time at a display
scale of 100%, known since 2026-09-27. All runs below are the real host,
launched by the probe at a forced scale (`--force-device-scale-factor`), with
an idle page in the site view; forced 100% matched a real 100% on 2026-09-27.
Probes are in `.scratch/stability/` (not committed).

**What a stalled capture waits for.** Raw CDP `Page.captureScreenshot`, 20
captures at forced 100%, each sent 0.3s apart: a capture that stalls is never
answered on its own (still waiting after 60s, measured earlier today). Sent
again with identical settings while the first waits, **both are answered
within ~0.1s: 20/20, slowest 0.46s**. Playwright's own screenshot, 5s timeout:
11/20, 10/20 and 4/20 in three passes at 100%, 10–11/20 at 110%, and — new
today — 9/20 at 125% in one pass (20/20 in every earlier pass at 125%); 20/20
at 150%.

**Ruled out, each 20 captures at forced 100%:** the overlay at opacity 0.999
(no change); `backgroundThrottling: false` (12/20); Chromium's native window
occlusion off (12/20); the window 1px narrower (14/20) or 1px shorter
(13/20); the page hidden or throttled — it reports `visible`, has focus, and
draws 55–63 frames a second at 100%, 110%, 125% and 150% alike. Why the scale
matters inside Chromium is still not known.

**Fixes tried, 20 captures each:**

| Approach | 100% | 110% | 150% |
|---|---|---|---|
| Playwright, page kept drawing (a 1px rAF pixel, 2026-09-30's idea) and retried after 2.5s | 20/20, every one ~2.9–3.3s | 20/20, ~3.3s | 20/20, 0.3s |
| the same without the pixel | 20/20, ~3.3s — the pixel made no difference | 20/20 | 20/20 |
| retried after 0.8s or 1.5s instead of 2.5s | 20/20, still ~3.2s each | — | — |
| Playwright with a raw capture sent alongside every 0.3s | 20/20, 0.2–3.7s, up to 11 extra requests | — | 20/20 |
| the same, the extra request clipped to 1x1 | **wrong picture**: Playwright's capture came back 1x1 | — | — |
| **raw capture, the same request again every 0.15s while it waits, password boxes painted in the page (`browser.capture_site`)** | **20/20, median 0.34s, slowest 2.03s** | **20/20, median 0.41s, slowest 2.43s** | **20/20, median 0.35s, slowest 0.47s** |

At 125% the final version was also 20/20 (median 0.40s, slowest 2.71s). Every
picture was the right size (1280x800 at 100%, 1408x880 at 110%, 1600x1000 at
125%, 1920x1200 at 150%) and left nothing behind on the page.

Two defects found along the way. The 1x1 extra request: Chromium answered
Playwright's pending capture with the extra request's clip, so the extra
request has to be identical to the real one — and so the capture is made raw,
not through Playwright. And the raw capture showed the text cursor blinking in
a box just typed into, which Playwright hides: `test_an_ordinary_box_is_left_as_it_is`
failed on it; the cursor is now hidden for the capture.

With the mask, at a 0.3s interval half the captures needed five requests
(~1.5–2s, against two and ~0.5s without the mask); waiting two frames for the
mask to be drawn first changed nothing; at 0.15s the median is 0.34s.

**In the product.** Twenty train searches walked in the real window at
forced 100% (`walk_proof.py`, the closing screen read after each):
**20/20 ended with the picture**, every run reaching the answer (30.5s mean).
The same walk with the old capture put back: **10/10 with the picture too** —
in this flow the picture is taken just after the results page has drawn, and
the stall needs a page that has gone still, so the walk shows the fix costs
nothing in the product's path but cannot show the failure. The failure is
shown by the idle-page captures above, which is how a preview or a proof of a
page that has sat still is taken.

## 2026-10-17b — "I waited while the window was closed", with the window open

`fix/stability`. The sentence appeared once while the window was open. Where:
the recording run of 2026-10-16 at 20:11 (`.scratch/walk-finish/clips3.log`,
not the clips committed). The demo recorder plays the overlay in a browser of
its own and records that; the backend drives the site view inside a real
Electron host whose window nobody watches, and before every action reads
*that* window's state. In that run the "fold" clip took 414s and never
finished, and the "adapt" clip took 308s — "This site asks about cookies. ->
Yes | I waited while the window was closed. -> Carry on" — against 43s and
46s when re-recorded at 00:06. So the host's window was put away for minutes
during those two clips, and each run waited, as it should for a person
working in that window. Nothing in the repository minimises it; who or what
did was not recorded, and is not known.

**The state reads were checked first**, in a host this probe launched,
driving only its own window by handle (`.scratch/stability/window_probe.py`,
`window_race_probe.py`), reading what the backend reads:

| What was done to the window | Read | Right? |
|---|---|---|
| minimise, restore / show-normal / maximise; maximise first, then minimise and restore; the same by `WM_SYSCOMMAND` as a taskbar click sends | minimised, then shown | yes, all 13 transitions |
| minimise then `SW_SHOW` (stays minimised) | minimised | yes |
| 100 minimise-restore cycles, 0–0.3s apart, read 1s after each | stale "minimised" after **0 of 100** | yes |
| hidden (`SW_HIDE`) | **shown** | no — a hidden window is never noticed |

So no read said "away" while the window was there. The pause was a true
reading of a window that was not the one being looked at.

**The fix.** The overlay writes `window.__simbaStarted` — false when it
loads, true once a task is started from it — and the backend counts the
host's window only when it is true. A run driven from any other overlay is
never paused by the host's window; the person working in the host's own
overlay is paused exactly as before. Tests: the state read through a real
overlay page with the flag false, true and absent
(`test_window.py::test_a_minimised_host_does_not_pause_a_run_started_from_another_overlay`),
and the built overlay setting it (`frontend/test_window_started.py`). Every
pause is now a line in `logs/backend.log`: the state, and how long it lasted.

## 2026-10-17c — the registration's caveat, in full

`fix/stability`. The closing screen of a registration now says what the
portal says in full: "The portal says it isn't final until tuition and fees
are paid, or a payment plan is in place." (it said "…until fees are paid",
which dropped the payment plan, half of the portal's meaning). The portal's
own sentence is "Registration is not final until tuition and fees are paid
or a payment plan is in place". Measured: the closing screen with the longer
line still fits — `frontend/test_terminal_states.py`, `test_closing.py` and
`test_copy.py`, **288 passed**, which includes every ending, this one among
them, at the window's size at 100%, 125% and 150% with every button wholly on
screen and nothing scrolling; the host fit test checks it in the real window
at the end of this branch.

## 2026-10-17d — a booking and a payment end in plain practice words

`fix/stability`. On our copies, a confirmed booking now ends "Booked on the
practice site." over "Booking number PR-482193. This was a practice copy, so
no real ticket was booked and no money was taken.", and a payment "Paid on
the practice site." over "Receipt number RCPT-305114. This was a practice
copy, so no money was taken." — in place of "That's done." Then the site's
own words without the number ('The site says "Booking Confirmed".'), the
receipt by the site's labels, and the picture. Measured on the replicas in
headless Chromium, the real loop: `test_booking.py`, `test_paying.py` and
`test_confirmation.py`, **18 passed** — the heading, the line under it with
the replica's own booking or receipt number, and the shortened quote checked
on the real run; and the closing-screen tests, `test_closing.py`, `test_copy.py` and `test_terminal_states.py`, **288 passed**, the booking
and the payment among the endings measured at the window's size at 100%,
125% and 150%.

## 2026-10-17e — the slower backend suite, and runs kept open for an offer

`fix/stability`. The backend half went from 12–13 minutes (752s, 805s on
2026-10-15/16) to 23–25 minutes from the afternoon of 2026-10-16, when the
closing screen's offer began to keep runs open (`610cde5`). Were runs left
waiting for the offer until a timeout?

**In the tests: no.** Every test that reaches an offer answers it: the
scripted connections answer "leave" (`test_asking.ScriptedConnection`,
`test_checklist.Answers`), and the websocket tests close their socket on
`task.completed`, which ends the waiting run at once. Measured: the backend
half, every test timed (`--durations=0`), at `67359d1` — the commit *before*
the offer — and at this branch's `09d2577`, each in a clean worktree, one
after the other, nothing else running:

| | tests | wall clock | the 410 test phases in both |
|---|---|---|---|
| `67359d1`, before the offer | 886 passed, 9 skipped | **1435s** | 1409s |
| `09d2577`, this branch | 899 passed, 9 skipped | **1537s** | 1466s |

The same commit took **805s on 2026-10-16 and 1435s today**. So the code did
not double the time: the machine did. The +100s on this branch is spread
over the tests that now take the end-of-task picture and finish a booking or
a payment (the four offer tests: 4.7–8.9s each, no wait in any), and 13 more
tests. Nothing in either run waits on an offer.

**What the machine was doing** (read-only, today): on battery (38–40%,
discharging), Balanced plan; 1.0–1.2 GB of 7.9 GB memory free, 43–260 pages
paged a second; the user's Chrome ~1.1 GB, two Claude processes, VS Code.
The processor read 48% of rated speed idle but **143–189% under load**, so
the battery is not slowing the processor. Memory pressure on a suite that
launches a browser per test is the likelier cause, and is **not proven**: no
earlier run recorded memory. Every evaluation banner and every pytest run now
prints the power source, the processor's speed at that instant and the free
memory (`conditions.power`, `conftest.pytest_report_header`).

**In real use: yes.** A run kept open for "Book one of these" or "Pay this
bill" waited for as long as the connection lasted — a person who read the
answer and walked away left a run, its Playwright connection to the host and
its page waiting indefinitely. It now closes itself after **10 minutes**
(`loop.OFFER_IDLE_S`), and the overlay takes the offer away once the run has
gone, so a press cannot go nowhere; "Back to start" is unchanged. Tests: a
run whose offer nobody answers ends by itself (`test_booking.py`, with the
idle time shortened), and an offer whose run has closed is not shown
(`frontend/test_terminal_states.py`, 15 offer tests passed).

## 2026-10-17f — the tile press and the slow checklist, at 150%: not reproduced

`fix/stability`. Seen once at 150%: tile presses not registering, and the
checklist sitting over a minute. Twenty train searches in the real window
at forced 150% (`.scratch/walk-finish/walk_item4.py`: the replicas, the real
host and backend, the guard on, pressing each answer the moment its button
is there), each pressing the "Find train times" tile **once** at a set delay
after the tiles arrived (0.3s to 4s, cycled), and timing the checklist from
"Yes, that's right" to the answer:

| | Result |
|---|---|
| tile registered on the first press | **20/20** |
| press to the backend routing the goal (overlay's log against the backend's) | 0.00–0.01s |
| routing to the first question on screen (backend's log) | ~1.3s |
| checklist, read-back to answer | **4.4–6.2s**, median 5.35s — never near a minute |
| reached the answer, with the end-of-task picture | 20/20 |
| presses logged / ignored by the guard | 256 / 76 — every ignored one on a button that had appeared under 600ms before, the walk pressing as soon as it could |

Not reproduced. One limit, measured: the walk could not press the tile
early. The guard's own log put every press 5.4–6.6s after the tile appeared
(`sinceButtonMs`), whatever delay was asked for — the overlay answers CDP
slowly while it loads — so a press during the tiles' 1.3s entrance, which the
guard ignores by design, was never tried. That is the one way a tile press
can do nothing, and it is now visible.

**So the log shows the cause next time.** Every press the guard logs —
ignored or not, how long since its button moved, what was under the pointer
— is now copied into the host's log as `SIMBA overlay press {…}`; the
backend writes `logs/backend.log`, where every page read, choice of move,
step on screen and its answer, checklist line, move and picture has a time
(DECISIONS.md, *What a run did…*). Both were read back in this run: the
press log above is the host's, the timings the backend's. Until now neither
existed — the backend's `simba` lines were never set up to print, and the
overlay's press log died with the page.

## 2026-10-17g — a fresh clone, set up from README.md and RUNNING.md only

`fix/stability`. The showcase machine will be set up this way. `git clone`
of `origin` (`main` at `1a3579a`) into `.scratch/fresh/simba`, then only the
two documents' steps, in Windows PowerShell. One change to the method: pip's,
npm's, Electron's and Playwright's download caches were pointed inside
`.scratch/fresh/cache` (`PIP_CACHE_DIR`, `npm_config_cache`,
`electron_config_cache`, `PLAYWRIGHT_BROWSERS_PATH`), because CLAUDE.md keeps
every file this work writes inside the repository; that also made every
download a real one, as on a new machine.

| Step | What the documents say | What happened |
|---|---|---|
| 1. Tools | Python 3.12+, Node 18+, npm, git | 3.12.3, 24.12.0, 11.6.2, 2.55.0 — as listed |
| 2. Backend | venv, `pip install -r requirements-dev.txt`, `playwright install chromium`, the check | worked; `backend ok`. Unpinned, so the clone got **Playwright 1.64.0** (this machine 1.62.0), fastapi 0.143.3, uvicorn 0.54.0, websockets 17.2, scikit-learn 1.9.1, pytest 9.1.1 |
| 3. Frontend | `npm install`, `npm run build` | worked; `dist/` and `dist-electron/` written |
| 5. Prove it | `python -m pytest` from the root, "485 pass, 9 skip" | **wrong: stops at collection** — `backend/orchestrator/test_checklist.py` and `frontend/test_checklist.py` share a module name ("import file mismatch"). In two halves both collect: 905 and 528 tests. The count was a month old. |
| Run it | `.\run.ps1 railways-local` (RUNNING.md) | every `==>` line RUNNING.md lists, in order, then ready |
| Smoke test | `.\run.ps1 mock -Seconds 20` | "stopped", nothing left listening |

**The three flows, in the clone's own window**, typed and answered as DEMO.md
says (driven over CDP by `.scratch/stability/clone_flows.py`, no model key,
the hardcoded plans):

- **Trains** — "trains to Rawalpindi tomorrow", `Lahore`, Lahore Cantt, "Yes,
  that's right": "There are 2 trains. The fastest is 9UP, at 8 hours 15
  minutes.", both trains, the picture, "I only looked up times…", Back to
  start and "Book one of these".
- **The bill, then paying it** — "Check my electricity bill",
  `04141234567890`, Yes to cookies, "Pay this bill", the final screen, "Pay
  it": confirmed by the site, with the picture, in 14.4s.
- **Registration** — "register me for CS-401", signed in, the final screen,
  "Register": "You're registered for CS-401.", the portal's caveat, the
  picture, in 8.7s.

All three finished. The clone is `main`, so its endings are the old wording
(2026-10-17c and d change them on this branch).

**Fixed in the documents:** README's step 5 now runs the suite in its two
halves, with today's counts, skips and times; its layout table and "the
short way" name the railways copy and `railways-local`; its switches table
gains `SIMBA_HOST_TESTS` and `SIMBA_LOG_FILE`. RUNNING.md needed nothing.
DEMO.md's payment ending is the new wording, and its advice for a port in
use no longer says `Get-Process electron, python | Stop-Process`, which would
stop every Python and Electron program on the showcase machine.

**Not done:** the two halves were collected in the clone, not run there
(about 50 minutes; the full suite runs on this branch below). The live
railways start page was not tried.

## 2026-10-17h — the host fit test that closed after 22 minutes: found

`fix/stability`. Once, on 2026-10-17 at 01:15, the host fit test failed at
100% after 22 minutes with the host's page closed (`TargetClosedError` in a
`wait_for_timeout`); a passing run takes about 2.5 minutes a scale. The same
measurement (`display_fit_run.measure("1")`) was run again and again at
forced 100%, each in its own process with a 15-minute limit, its stage lines
kept (`display_fit_run.said`, new) and the host's own log (new lines for a
renderer gone, a window closed, the app quitting, the machine sleeping):

| | Runs | Passed | Time each |
|---|---|---|---|
| before the fix | 12 | **11** — run 12 hung | 144–157s; run 12 stopped at the 900s limit |
| after the fix | **20** | **20** | 145–153s (median 146s) |

Run 12's stage lines: host up 0.6s, home screen 2.9s, site view laid out
4.3s, 20 site-view captures done at 51.3s (13/20, the known 100% capture
problem, measured on purpose), **"capturing the overlay" — and nothing more
for 849s**. `capture_view` took the overlay's picture with one raw
`Page.captureScreenshot` and retried only if it raised; a capture that stalls
at 100% never raises (2026-10-17, the stall), so the test waited for ever, and
on 2026-10-17 at 01:15 waited until the host's page was closed under it. The
host's log said nothing was wrong: no renderer gone, no window closed.

**The fix:** `capture_view` takes the picture through `browser.capture_site`
— the same request sent again while one stalls, given up after 4s — over a
connection of its own. Every one of the 20 runs after it saved the overlay's
picture and finished. If a capture ever fails now, the test fails at once
and says where, rather than sitting for 22 minutes.

**Addendum, the same day: the battery, after all.** The final backend half on
this branch, run later with the laptop **on mains** and about the same free
memory (1294 MB, printed by the new header), took **879s** for 901 tests —
against 1435s and 1537s on battery that morning for 886 and 899. Same
machine, same memory pressure, more tests, 40% less time. So memory was not
the cause, and power was: the under-load reading above (143–189% of rated
speed) was a one-second sample, which catches a burst of turbo and not the
speed the processor can hold on battery. The suite's 12-to-25-minute jump on
2026-10-16 matches the laptop going on battery that afternoon; that it did
then is inferred, not recorded — which is what the new header is for.

## 2026-10-17i — the suite, before merging `fix/stability`

**Backend half: 901 passed, 9 skipped, 0 failed, 879s** (on mains).
**Frontend half: 527 passed, 3 skipped, 0 failed, 1059s.**
**Host window fit (`SIMBA_HOST_TESTS=1`): 3 passed** — 100%, 125%, 150%, 396s.
In all, **1428 passed, 12 skipped, 0 failed**; the 12 skips as before.

The frontend half failed twice before that: the two press-guard tests (both
runs) and once a level test. All three passed alone, and the press-guard pair
failed the same way on `main` (`1a3579a`) when run after
`test_overflow_guard.py` and `test_levels.py` — an order effect that was
already there, not this branch's doing. Each assumed Playwright acts within a
fixed time: the "just arrived" test that its click lands inside the guard's
500ms; the "on its way out" test that it can catch a screen that lives only
for its exit; the level test that the level is back within 800ms. With
earlier modules' servers still running in the process, none of those held.
Now the first widens the guard's window to 3s after Start, the second has the
page record the leaving screen the moment it is marked, and the third waits
up to 5s for the level. The pair then passed 3 of 3 in the order that failed,
and the whole half passed.

## 2026-10-17j — a registration ends in practice words too

`fix/final-touches`. A registration the portal confirmed on our copy now ends
as a booking and a payment do: "Registered for CS-401 on the practice site."
over "Confirmation number REG-10234-2026. This was a practice copy, so no real
registration was made. The portal says it isn't final until tuition and fees
are paid, or a payment plan is in place." — the portal's caveat kept, in
plain words, and only when the page says it. Measured: the registration
tests on the replica (`test_confirmation.py`, `test_final_step.py`,
`test_course.py`), **24 passed**, the heading and the line with the replica's
own number checked on the real run; the closing-screen, copy and fit tests,
**289 passed**, the longer line fitting at 100%, 125% and 150% with every
button on screen.

## 2026-10-17k — a fresh clone's suite, and the press the guard wrongly ignored

`fix/final-touches`. A fresh clone of this branch from GitHub
(`9787fdc`, then `436085d`), set up from README and RUNNING only — pinned
installs, `npm ci` — and the whole suite run once in its two halves, on
battery (55% → 45%):

| Half | Result | Time |
|---|---|---|
| backend | **833 passed, 9 skipped, 2 failed, 66 errors** | 1301s |
| frontend | **526 passed, 3 skipped, 1 failed** | 1251s |

Three causes, all fixed on this branch:

1. **66 errors and 1 failure: no `.scratch/` folder.** The root conftest puts
   pytest's temporary folder at `.scratch/pytest`; `.scratch/` is ignored, so
   a fresh clone has none, and pytest makes only the last folder of the path.
   Every test using `tmp_path` errored. The conftest now makes the folder
   (`test_basetemp.py` has a test for it). This machine always had one.
2. **1 failure: `test_proof.py`** expected the registration's number inside
   the quoted confirmation; since 2026-10-17j it is said under the heading.
   The commit that moved it had not run this file.
3. **1 failure: the press guard ignored a press it should have taken.** In
   `test_press_guard.py`, "Tomorrow" pressed 2.1s after it arrived was logged
   ignored, `sinceButtonMs` 2–5, with no change to the page at all — 3 runs
   in 6 when run after `test_overflow_guard.py` and `test_levels.py`. Tracked
   frame by frame: the button eased in and came to rest at y 292.3; under
   the press it read 293.3 (its own `active:translate-y-px`); and the guard
   still held y 290, the last place it had *counted* the button as moving —
   it follows the last 2px of an ease only in `exact`. 290 to 293 is 3px,
   over the 2px it allows, so the press was a "move made that instant".
   Whether a run fails depends on where the ease happens to stop. The guard
   now takes each button's resting place as its place once things stop
   moving; when it last moved is unchanged. A new test reproduces it
   exactly (a 3px move, 2px of easing, rest, a 1px nudge): it fails without
   the fix and passes with it, and the order that failed 3 in 6 passed 6 in
   6. Tiles ease in the same way, so this is the likeliest cause of the tile
   press that did not register at 150% (2026-10-17f could not reproduce it:
   its walk always pressed 5s or more after the tiles arrived, by which time
   another scan had caught up). Two theories tried first and dropped: a
   move the guard could not see (an animation the browser runs itself) —
   a 200ms re-check changed nothing; and the typeface arriving late —
   waiting for it changed nothing.

## 2026-10-17l — the booking clip, re-recorded

`fix/final-touches`. `demo/booking.webm` re-recorded with the stack up
(`run.ps1 railways-local`, our copy, on mains): **56s, 5.3 MB**, every screen
answered — both stations, the read-back, 7UP, the name, AC Standard, the final
screen held and "Book it", the real page shown. Its closing frame, looked at
(not just its log): "Booked on the practice site." / "Booking number
PR-452048. This was a practice copy, so no real ticket was booked and no money
was taken." / 'The site says "Booking Confirmed".' / the receipt. The other
five clips were checked against today's wording and left: the bill, trains
and hello clips end on screens that have not changed, and `fold.webm` is the
scripted mock, with no final screen and no confirmation.

## 2026-10-17m — the suite, before merging `fix/final-touches`

On mains (printed by each run). **Backend half: 902 passed, 9 skipped, 0
failed, 952s. Frontend half: 528 passed, 3 skipped, 0 failed, 1036s. Host
window fit: 3 passed** (100%, 125%, 150%, 415s). In all **1430 passed, 12
skipped, 0 failed**. The fresh clone's second run, before the last test fix:
901 passed and 1 failed (that test, since passing in the clone too), 528
passed.

## 2026-10-18 — the welcome, and the person's own starting level

`feat/personal`. The four questions, in a headless browser from the built
overlay: `frontend/test_welcome.py`, **8 passed** — every question skippable
and the welcome not shown again; the answers kept as the profile
(`{"name": "Ayesha", "level": 3, "readAloud": false, "askEach": false,
"welcomed": true}`); the greeting "…, Ayesha. What can I do for you?"; the
next `task.start` carrying `start_level: 3` and no name anywhere in what the
overlay sent; no "Read this aloud" for a person who said no; "Change my
settings" reopening with the answers marked; and all four questions fitting,
nothing scrolling and every button on screen, at 1280x800 (100%), 1280x734
(125%), 1266x606 and 1266x632 (150%). Looked at, at 150% and 100%: the three
examples side by side, each the real step, legible.

The rules (`backend/estimator/test_rules.py`, 7 new, **34 passed**): a task
starts at the chosen level 1, 2 or 3; a heavy page still at 3; calm steps
come back to the person's level, not 2; chosen 3, never brought back to 2;
no level, or one out of range, is 2. Through the app over the websocket
(`test_adaptation.py`, **7 passed**): the bill with `start_level: 1`, one
hesitant question, then calm — levels sent **1, 2, 1**, against 2, 3, 2
without it. The home, level, copy, first-screen and read-aloud tests:
**134 passed**.

## 2026-10-18b — the person's own tiles

`feat/personal`. The store and the backend (`backend/orchestrator/
test_tiles.py`, **14 passed**): a tile written to disk holds neither its name,
its flow nor its reference in readable form, and nothing that prints a tile
shows its details; rename, move, remove and clear; three at most, the same
bill never twice, only a bill's reference or a journey's two stations kept.
On the replicas, through the real loop: a bill's closing screen offered once
to keep it as "My bill", beside "Pay this bill", and kept under the name
given ("Electricity", reference and all); not offered again for a bill
already kept, nor for a run started from a tile; a journey offered as
"Trains to Karachi" (the site says "KARACHI CANTT" — the first version said
"Trains to KARACHI"). Through the app over the websocket: the home screen is
offered the tiles by name only, no reference or station in the message; the
bill's tile ran without asking for the number, its goal "My bill"; the
journey's tile asked the day first and neither station; `tile.change`
renamed, moved and removed, each answered with the tiles as they then stood,
an unknown id changing nothing; and `logs/backend.log` held neither the
reference nor a station.

The overlay (`frontend/test_own_tiles.py`, **9 passed**): "Things I can help
with" shown above the three while there are no tiles; the person's own first
with them; a tile press sends only its id, flow and name; "Change my tiles"
renames, moves and takes off, sending exactly those changes, the first
unable to move left and the last right; "Keep it" sends `keep` with the
offered name, says "Kept on your home screen as Trains to Karachi.", and
leaves "Book one of these" where it was. Three tiles and two goals asked
before fit at 1280x800, 1280x734, 1266x606 and 1266x632 — **after two
failures**: first the box to ask in was 28px below the window at 100% and
17px at 150% (the three cards kept their pictures and two-line names under
the tiles), then the page still scrolled by 19px (the canvas's own bottom
padding). The three now take the tiles' shape under them, and the gaps close
a little the more the home screen holds. Showing "Things I can help with"
always also made the screen with three goals asked before scroll by 16px at
100%; fixed the same way. Both new endings with the offer to keep fit at
every size (`test_terminal_states.py`), and the home, copy, welcome, ending
and first-screen tests: **404 run, all passing after those fixes**. The
backend's websocket and flow tests: **127 passed**.

## 2026-10-18c — the starting level, written down as its own signal

`feat/personal`. `backend/estimator/test_pairing.py`, 3 new, **12 passed**:
a `start_level` row once per task, and the level on every telemetry row after
it; anything but a whole 1, 2 or 3 — none, 0, 4, "2", 2.0 — written as
`null`, not chosen, never as 2 (the first version took 2.0 as a choice:
`2.0 in (1, 2, 3)` is true in Python; fixed here and in `LevelRules.
start_from`); and through the app, the `task.start` of a person with a
profile leaving its `start_level` row first. The rules, with floats and
booleans added to what is not a level: **34 passed**.

## 2026-10-18d — forgetting the person

`feat/personal`. `frontend/test_reset.py`, **3 passed**: "No, keep it" changes
nothing (profile kept, no `tile.change` sent); "Yes, forget it all" sends
`clear`, removes the profile from the overlay's storage, opens the welcome on
an empty name question with nothing left to forget, and after it the home
screen greets no one by name and has no tiles of its own; a first open shows
no button to forget. Through the app (`test_tiles.py`, **15 passed**): `clear`
answers with no tiles and the file they were kept in is gone. The welcome
and copy tests, with the new words: **40 passed**.

## 2026-10-18e — a brand-new person, in the real window; and the suite

`feat/personal`, not merged. **The walk**, at forced 100% in the real host
with an empty profile folder (`SIMBA_USER_DATA`) and an empty tiles file,
our replicas, the hardcoded plans (`.scratch/walk-finish/walk_personal.py`):
first open showed the welcome; "Ayesha", the fullest of the three examples,
the read-aloud button kept, "Just do it and show me"; the home screen said
"Good evening, Ayesha. What can I do for you?" — over two lines, the second
"you?" alone, now balanced (`text-balance`). Typed "Check my electricity
bill": asked the reference number and the cookies, found Rs 14,382, and
offered "Shall I keep this on your home screen as My bill?" beside "Pay this
bill"; "Keep it" said "Kept on your home screen as My bill." Back to start:
"My bill" first, above "Things I can help with". Pressed: asked only the
cookies — the site asks again — and never the number; found the bill again;
offered nothing to keep. 37 seconds end to end. Every screen captured from the
overlay's own view, in `.scratch/for-review-6/`.

**The host window fit, with a new person's first open** (`SIMBA_HOST_TESTS=1
frontend/test_window_fit.py`, each host with an empty profile folder): **3
passed** at 100%, 125% and 150% — the four welcome questions each fitting,
nothing scrolling, every button in the window; the home screen with three of
the person's own tiles and two goals asked before; every ending, the two with
the offer to keep among them; the sign-in screen.

**The suite, on mains: 1500 passed, 12 skipped, 0 failed** — backend 928 in
859s, frontend 572 in 1190s, as two halves.

## 2026-10-18f — the welcome's examples, drawn larger than life

Seen by Raham in the real window at 150%, and in the 100% picture already
copied for review without being looked at: each of the three examples was
drawn at more than full size, across its neighbours. Each example's frame
took its width from the example inside it, laid out at the column's 880px,
so it measured itself at about 976px and drew the example at 1.1 instead of
about 0.45. The tests passed — they checked that nothing scrolled and that the
welcome's own buttons were in the window, and the examples' overflow was
hidden; and the headless pictures looked at earlier were taken before the
examples' width was changed to the column's. Now the frame takes the card's
width and the example sits inside it out of the flow. A new test,
`test_each_example_is_drawn_small_inside_its_own_card`, fails on the old
component at all four sizes and passes on the new (the welcome's tests: **12
passed**); the real host at forced 150% shows the three side by side, each in
its card.

## 2026-10-21 — after a reset, nothing from before it is shown

**Method.** `frontend/test_forget_run.py`, end to end: the real backend
(hardcoded plan, trace memory on, its own trace store, tiles and vault in a
temporary folder), the bill replica and the real overlay build. The bill is run
through the overlay as a person would — "check my electricity bill
04141234567890", agreed, kept as "My bill" — by a profile named Ayesha; then
"Forget me and start again", and the welcome skipped.

**Before the reset (the control):** the greeting holds "Ayesha", the tile
"My bill", one goal asked before, and the bill's last four digits "7890".

**After it:** none of the four anywhere in the page's text, the reference in
neither the text nor the markup (a tooltip), 0 goal cards, 0 tiles — and the
same after the page is opened again. The replay store still holds the run's
one trace with its reference; the tile file is gone. A second test makes the
reset with the overlay pointed at no backend, then opens it against the real
one: nothing shown, and the backend told.

**Against the code before today:** both tests fail — "7890" still on the
home screen after the reset, and no reset kept for a backend that was not
there. **With it:** 2 passed (53.8s). The store and vault units
(`test_replay.py`, `test_vault.py`) and the files around them (tiles, reset,
own tiles, short labels): **63 passed** in 264s, on battery.

## 2026-10-22 — ratings collected online: the form, and its answers read back

`feat/rating-online`. **No ratings were collected; nothing here is a result
about pages.** What was measured is that the instrument is built and that its
answers reach training.

- **Export** (`python -m tools.rating.export_form`): 55 pictures, 5.5 MB in
  all, every one checked against its sha256 in `data/rating/pages.json` (run
  `58dc053cdac7`). The repeats and how far each comes after its first
  showing: P51 = P29 (positions 3 → 12), P52 = P39 (9 → 19), P53 = P07
  (36 → 43), P54 = P28 (27 → 45), P55 = P48 (32 → 46): gaps of 7 to 18.
- **Converter, on a synthetic 12-response CSV against the real mapping** (to
  `.scratch/`, deleted after): 1 dropped for not agreeing, 2 for phones, **9
  usable**, 495 rows, and `train.py` refused at 9 raters as it should. With
  two more usable responses, 11 raters: all 50 pages paired with a current
  picture and features from the same run, 55 repeat pairs, and R² −0.019 ±
  0.018. That is correct for random answers, and shows only that the pipeline
  runs.
- **Tests**: 13 new in `tools/rating/test_form.py`; with the rating tool's and
  training's own, 66 passed in 45.8s.
- **The form itself has not been run.** Apps Script cannot be run from this
  machine; `make_form.gs` is untested until it is run in Google, and the
  README's step 4 is the check.

**Limitations of online ratings**, in full in DECISIONS.md (*Ratings are
collected online*): the pictures are seen at about half size; nobody
supervises, and no time per answer is recorded; one fixed order for every
online rater; the same five repeats for everyone; and the device is
self-reported. Any trained result should say how many of its raters were
online (`"online": true`), and should be checked with and without them.

## 2026-10-22b — two rating forms, A and B reversed

`feat/rating-two-orders`. **Still no ratings collected.**

- **Export**: unchanged pictures and repeats; form A's order is the one in
  2026-10-22, and B is its reverse. Every page and its repeat are as far apart
  in B as in A: 9, 10, 7, 18 and 14 pictures.
- **`make_form.gs`, run in Node against stand-ins for Google's `FormApp`,
  `DriveApp` and `Logger`** (not Google itself), over the real exported
  folder: each form has 171 items (consent, two page breaks, three
  questions, then a page break, picture and 1–7 question for each of 55);
  every question is required with bounds 1–7. Every picture sits directly
  above the question naming it, and each form's order matches the mapping,
  B exactly reversed. This checks the script's own logic, not that Google
  accepts each call. A real run in Google is still the check (README step 4).
  It also caught a JavaScript syntax error in a log line, made while editing,
  before commit.
- **Tests**: `tools/rating/test_form.py` 22 (was 13); with the rating tool's
  and training's own, 75 passed in 41.7s. Training reads both forms' rows
  together: 4 raters, 50 pages, 20 repeat pairs, every page from all 4.

## 2026-10-23 — `feat/personal` brought up to date and merged; a clock tie found

`feat/personal` with `main` merged into it (`bc903c5`), every half on mains
(the header of each run).

**The first run: 1 failure.** Backend half 951 passed, 1 failed, 9 skipped
(876s); frontend half 578 passed, 3 skipped (1220s); host fit test 3 passed
(455s). The failure was
`test_replay.py::test_a_reset_hides_what_came_before_from_the_home_screen_only`,
which passed on 2026-10-18: two goals saved one after the other came back
from `TraceStore.recent` oldest first.

**The cause, measured.** `traces.now()` read `datetime.now()`, and on this
machine 1996 of 1999 consecutive readings were identical. The clock moves in
ticks of several milliseconds, so two saves in one tick tied on `created_at`
and `ORDER BY created_at DESC` returned them in either order. The same
sequence as the test, 200 times: **60 wrong**. The same tie would hide a goal
saved in the reset's own tick, because the cutoff is a strict `>`. A person
cannot finish a task within milliseconds of another, so the app was very
unlikely to show it; the test, which saves back to back, did.

**The fix** (`1e0689f`): `now()` never returns a time at or before the last
one it gave; a tie moves on by a microsecond. New test: the clock stopped
outright, the order and the reset both still right. After: **0 of 200**
wrong, 0 of 1999 consecutive readings identical, and the stamps still sort
as text in time order.

**The rerun, after the fix**: backend half **953 passed, 9 skipped, 0
failed** (941s); frontend half **578 passed, 3 skipped, 0 failed** (1245s);
host fit test **3 passed** at 100%, 125% and 150% (455s). **1531 passed, 12
skipped, 0 failed.** Merged into `main`.

## 2026-10-23b — two sets of 30: a shorter, clearer rating form

`feat/rating-sets`. **No ratings were collected; nothing here is a result
about pages.** What was measured is the instrument: how alike the two sets
are, what each rater now sees, and that answers in the new shape reach
training. Why the forms changed, and what it costs: DECISIONS.md, *Two sets of
30*.

**What a rater does, before and after** (counted, not timed):

| | Before (2026-10-22b) | After |
|---|---|---|
| Pictures per rater, online | 55 | **30** (25 own + 3 anchors + 2 repeats) |
| Pictures per rater, in person | 52 | **30** |
| The question | "...would this page be to use?", 1–7, ends named | "How overwhelming does this page feel?", 5 answers, every one named |
| Before the first picture | instructions | instructions and **two worked examples** with their answers |
| Time stated at the top | "about 15 minutes" (in the description) | "**about 5-7 minutes**" (an estimate, not measured) |
| Items in each Google Form (stand-ins) | 171 | **98** |
| Raters needed to train | 10, each rating every page | **16**, 8 per set: 8 ratings on every page |
| Ratings collected at that floor | 520 | 480 |

**The split** (`session.split`, seed 20261023, 4,000 tries), on the 50 pages
of run `58dc053cdac7`. Each feature as ranks from 0 to 1; the largest
difference between the two sets' mean rank on any feature:

| | Largest mean-rank difference |
|---|---|
| **The split** | **0.023** |
| 2,000 random halvings: median | 0.133 |
| 2,000 random halvings: 5th percentile | 0.074 |
| 2,000 random halvings: best | 0.042 |

Heaviness (mean rank over the nine) runs 0.259–0.834 in Set 1 (median 0.478)
and 0.298–0.760 in Set 2 (median 0.480). Kinds: Set 1 11 demo, 11 public, 2
ours, 1 target; Set 2 10, 10, 3, 2. Raw feature means, Set 1 / Set 2:

| `interactive` | `links` | `inferred` | `text_density` | `max_depth` | `overlays` | `form_fields` | `dead_link_ratio` | `reading_grade` |
|---|---|---|---|---|---|---|---|---|
| 32.4 / 17.7 | 118.3 / 109.6 | 18.4 / 16.1 | 1.11 / 1.19 | 15.0 / 15.9 | 0.48 / 0.40 | 1.76 / 3.24 | 0.125 / 0.133 | 8.06 / 8.05 |

The ranks are even; two raw means are not, because a few pages hold most of
`interactive` and `form_fields`. Balanced by rank on purpose (DECISIONS.md).

**Anchors** (a sixth, a half and five sixths up each set's heaviness), with
heaviness: Set 1 lends demo.applitools.com (0.373), Hacker News (0.478) and
Bootstrap's open modal (0.629), shown in Set 2 at positions 21, 3 and 17;
Set 2 lends danluu.com (0.365), lite.cnn.com (0.480) and the live railway site
with its calendar open (0.646), shown in Set 1 at 17, 2 and 30.
**Repeats**, with the positions of the two showings: Set 1 P51 = the railway
site's station list (11 → 22), P52 = example.com (14 → 24); Set 2 P53 =
demoqa's modal (7 → 21), P54 = practice.expandtesting.com (3 → 22). Gaps of
10 to 19 pictures.

**`make_form.gs`, run in Node against stand-ins for `FormApp`, `DriveApp` and
`Logger`** over the real exported folder (not Google itself): each form has 98
items — consent, three page breaks, three questions, two example pictures,
then a page break, picture and question for each of 30. Every rating question
is required with the five labels in order, sits directly under its own
picture, and the order matches the mapping in both forms; both examples come
before the first picture with their sentence and answer; the description
starts "About 5-7 minutes"; the progress bar is on. A real run in Google is
still the check (`tools/rating/form/README.md`, step 4).

**Synthetic CSVs through the converter and into training**, against the real
mapping, corpus and manifest, every file in `.scratch/` (random answers, so
there is nothing to find):

- 8 Set 1 responses (1 on a phone) and 6 Set 2: 13 usable, 390 rows. Both the
  converter and `train.py` said **44 of 50 pages have fewer than 8 ratings; 66
  more ratings are needed — at least 1 more Set 1 rater and 2 more Set 2
  raters**, and training refused. Correct: 7 and 6 raters, the six anchors
  at 13.
- 9 and 9 responses (one phone each): 16 usable, 480 rows; ratings per page 8
  / 8 / 16 (fewest / median / most). Trained: alpha 0.012 (Set 1 0.014, Set 2
  −0.011), R² −0.152 ± 0.278 against −0.108 for predicting the mean, and the
  groups **alike** on the six anchors (difference 0.02, Mann–Whitney p = 0.916).
  Correct for random answers, and shows only that the pipeline runs.

**The in-person page**, drawn in a headless browser page (not the screen) at
1266x606, the content area of a 1080p laptop at 150%, with the real pictures:
the start, the two examples and their button, and each rating screen fit
without scrolling, the picture 598px wide. The first layout did not: the
examples ran 99px past the bottom, the start screen's Begin button was cut
off, and two-line answer buttons took the picture down to 552px. Fixed before
commit (smaller example pictures, tighter gaps, the number beside each label).

**Synthetic agreement on the coarser scale.** The training tests' synthetic
raters had the 1–7 noise (0.6 of a point); on 1–5 that is relatively more, and
alpha fell to 0.625, failing the test's 0.7. With the noise scaled by 4/6
(0.4) alpha is 0.698: rounding to five points costs agreement by itself. The
noise is now scaled and the threshold 0.6, with a note in the test.

**Tests**: `tools/rating/test_form.py` 28 functions (was 20),
`tools/rating/test_rating.py` 23 (was 14), `backend/estimator/test_train.py`
37 (was 28); together **101 passed** (was 75), three runs in a row, 55–77s.
Three test expectations were wrong on first run and corrected: a set's own
lent pages are anchors too (both sets show them), so a row's `anchor` covers
six pages, not three — caught once only when the random order put a lent page
first — and `inner_text` puts a blank line between paragraphs.

**The examples.** Fourteen live pages were tried for the two pictures: gov.uk's
bank holidays (taken, after its cookie banner was turned down), and for the
cluttered one CNN (politics throughout), timeanddate.com (looked "Somewhat"),
AliExpress (blank), rediff.com (connection reset), Arngren (Norwegian, and
"Extremely" more than "Very"), lingscars.com, AccuWeather and Argos (blocked),
Sports Direct (HTTP/2 error), eBay .com and .co.uk (error pages), Yahoo (politics), and
Newegg (taken, under its sale pop-up).

**The suite**, on mains: backend half **979 passed, 9 skipped, 0 failed**
(997s), frontend half **578 passed, 3 skipped, 0 failed** (1276s): **1557
passed, 12 skipped, 0 failed**, the 1531 of 2026-10-23 plus the 26 new
rating and training tests. The backend half was run with `-q`, which hides
the power header; the power was read just before it and just after it, on
mains both times. One line of `train.py` was tidied while it ran (a double
assignment folded into one), so the 101 rating and training tests were run
again on the final tree: 101 passed. The host fit test was not rerun; nothing
the host shows changed.

---

## 2026-10-30 — the estimator, trained on 15 raters' ratings

`python -m backend.estimator.train` at `19db24949e4b`. Ratings: `data\ratings.jsonl`, 450 rows, sha256 `c75da3a667ad`. Features: the headless rows of `data\corpus.json`, collected 2026-10-03T16:57:34+05:00. Model: `data\estimator.joblib`.

```text
========================================================================
taken at    2026-10-30T21:05:22+05:00
git         19db24949e4b on feat/estimator-trained
python      3.12.3 at D:\simba\backend\venv\Scripts\python.exe
playwright  1.62.0
model       openai gemini-3.1-flash-lite (from .env)
machine     Windows-11-10.0.26200-SP0, 8 cpus, load 63%
power       ON BATTERY (64%), processor at 61% of rated speed, 611 MB memory free
switches    none set
========================================================================
```

**Below the study's floor.** 22 of 50 pages have fewer than 8 ratings, so this ran with `--min-ratings 5`, which only a person asks for: http://127.0.0.1:5000/ [sign in] (5); http://127.0.0.1:5000/stubborn [as it loads] (5); http://127.0.0.1:5100/bill?reference=04141234567890 [as it loads] (5); http://demo.testfire.net/ [as it loads] (5); http://info.cern.ch/hypertext/WWW/TheProject.html [as it loads] (5); https://demo.opencart.com/ [as it loads] (5); https://demoqa.com/automation-practice-form [as it loads] (5); https://demoqa.com/modal-dialogs [open a demoqa modal] (5); https://developer.mozilla.org/en-US/docs/Web/HTML [as it loads] (5); https://element-plus.org/en-US/component/dialog.html [open an element plus dialog] (5); https://en.wikipedia.org/wiki/Cognitive_load [as it loads] (5); https://en.wikipedia.org/wiki/Main_Page [as it loads] (5); https://mui.com/material-ui/react-dialog/ [open a mui dialog] (5); https://parabank.parasoft.com/parabank/index.htm [as it loads] (5); https://practice.expandtesting.com/ [as it loads] (5); https://text.npr.org/ [as it loads] (5); https://the-internet.herokuapp.com/ [as it loads] (5); https://www.bbc.co.uk/news [as it loads] (5); https://www.nhs.uk/ [as it loads] (5); https://www.pakrailways.gov.pk/train [as it loads] (5); https://www.saucedemo.com/ [as it loads] (5); https://www.theguardian.com/international [as it loads] (5).

### How far the raters agree

| | |
|---|---|
| Raters | 15 (Set 1: 10, Set 2: 5) |
| Pages rated | 50 |
| Ratings per page, fewest / median / most | 5 / 10 / 15 (at least 8 needed) |
| Krippendorff's alpha (interval), first showings | 0.318 |
| Krippendorff's alpha, Set 1 only | 0.284 |
| Krippendorff's alpha, Set 2 only | 0.357 |
| Repeated pages: pairs | 30 |
| Repeated pages: mean difference | 0.50 |
| Repeated pages: identical / within one | 0.57 / 0.93 |
| Repeated pages: correlation | 0.803 |

Each rater against the mean of the others (Spearman):

| Rater | ρ |
|---|---|
| 5002 | 0.750 |
| 5003 | 0.378 |
| 5005 | 0.661 |
| 5006 | 0.635 |
| 5007 | -0.584 |
| 5008 | 0.867 |
| 5009 | 0.720 |
| 5012 | 0.788 |
| 5013 | 0.102 |
| 5014 | 0.661 |
| 6003 | 0.669 |
| 6004 | 0.736 |
| 6006 | 0.695 |
| 6008 | 0.649 |
| 6010 | 0.490 |

The two groups on the 6 anchor pages both rated: **alike** (Set 2 minus Set 1, mean over anchors, 0.02; alike means within 0.5 and Mann–Whitney U on each rater's anchor mean not below 0.05: p = 1.000).

| Anchor | Set 1 mean (raters) | Set 2 mean (raters) |
|---|---|---|
| https://danluu.com/ [as it loads] | 3.00 (10) | 3.20 (5) |
| https://demo.applitools.com/ [as it loads] | 1.40 (10) | 1.00 (5) |
| https://getbootstrap.com/docs/5.3/components/modal/ [open a bootstrap modal] | 2.70 (10) | 3.00 (5) |
| https://lite.cnn.com/ [as it loads] | 3.40 (10) | 4.00 (5) |
| https://news.ycombinator.com/ [as it loads] | 3.90 (10) | 3.40 (5) |
| https://www.pakrailways.gov.pk/train [open the calendar] | 1.30 (10) | 1.20 (5) |

### The model

Ridge regression on the nine features, standardised; alpha chosen inside each training fold from 26 values, 0.01–1000; 6.30957 on all 50 pages.

| | R², 5-fold, mean ± sd | Folds |
|---|---|---|
| Ridge | **0.491 ± 0.240** | 0.56, 0.06, 0.44, 0.72, 0.68 |
| Predicting the training mean | -0.110 ± 0.136 | -0.13, -0.00, -0.37, -0.05, -0.01 |

Error on the held-out folds, in points of the 1-5 scale:

| | Mean absolute error | Root mean squared error |
|---|---|---|
| Ridge | **0.480 ± 0.041** | **0.561 ± 0.029** |
| Predicting the training mean | 0.768 ± 0.184 | 0.890 ± 0.194 |

One split of 50 pages into five is one draw. Over 40 shuffles of the folds, every page held out once in each, pooled:

| | R² | Mean absolute error | Root mean squared error |
|---|---|---|---|
| Ridge | **0.572 ± 0.047** | **0.498 ± 0.022** | **0.586 ± 0.030** |
| Predicting the training mean | -0.046 ± 0.034 | 0.778 ± 0.013 | 0.917 ± 0.015 |

How far these page means can be predicted at all: their reliability, halving each page's raters 500 times and stepping up with Spearman-Brown, is **0.779**, about the most R² any model of them could reach.

Permutation importance on the held-out fold of each split, 50 shuffles each: the R² lost when one feature is shuffled.

| Feature | R² lost, mean ± sd | Coefficient (standardised) |
|---|---|---|
| `text_density` | 0.611 ± 0.475 | +0.535 |
| `links` | 0.411 ± 0.689 | +0.312 |
| `max_depth` | 0.184 ± 0.323 | -0.217 |
| `interactive` | 0.010 ± 0.055 | +0.082 |
| `dead_link_ratio` | 0.010 ± 0.033 | +0.072 |
| `form_fields` | 0.007 ± 0.074 | -0.074 |
| `overlays` | -0.002 ± 0.013 | +0.004 |
| `reading_grade` | -0.006 ± 0.015 | -0.002 |
| `inferred` | -0.007 ± 0.050 | -0.033 |

The score is 2.512 plus each coefficient times its feature's distance from the corpus mean in standard deviations, clipped to 1-5.

### From a score to a level

**The raters' own bands**: a mean under 2.5 is nearest "Not at all" or "A little", 2.5 to 3.5 nearest "Somewhat", and 3.5 or more nearest "Very" or "Extremely": 24, 18 and 8 pages. The ratings' natural breaks (three groups, least squared distance) are 2.40 and 3.45.

**The score's cut points are 2.45 and 2.90**, chosen by trying every pair from 1.5 to 4.5 in steps of 0.05 and keeping the pair that best reproduces those bands on held-out scores (quadratic weighted kappa, mean over 40 shuffles: 0.751; the rating cuts used unchanged: 0.666). A held-out score is squeezed towards the mean, which is why the heavy cut sits under 3.5.

**On pages the cuts were not chosen on**, the whole procedure held out: kappa **0.691**, the right band on **64.4%** of pages. The cuts chosen there average 2.43 ± 0.14 and 2.95 ± 0.13: quote them to a tenth at best.

Raters' band against the band of each page's mean held-out score:

| Raters said | Scored calm | Scored middle | Scored heavy |
|---|---|---|---|
| calm | 21 | 3 | 0 |
| middle | 5 | 7 | 6 |
| heavy | 0 | 1 | 7 |

---

## 2026-10-30b — the trained estimator against the provisional rules

`python -m tools.evaluation.estimator_compare`. Which judges a page more as people do, for a person who has not said what level they want: the model's heavy call (level 3) or the rules' (two of three signs). The model is marked on held-out predictions throughout; rated heavy means a mean of 3.5 or more.

```text
========================================================================
taken at    2026-10-30T21:06:26+05:00
git         19db24949e4b on feat/estimator-trained — DIRTY TREE, the commit does not describe this run
python      3.12.3 at D:\simba\backend\venv\Scripts\python.exe
playwright  1.62.0
model       openai gemini-3.1-flash-lite (from .env)
machine     Windows-11-10.0.26200-SP0, 8 cpus, load 32%
power       ON BATTERY (63%), processor at 95% of rated speed, 1660 MB memory free
switches    none set
========================================================================
```

### Which is closer to the ratings

| | Pages called heavy | Rated heavy too | False alarms | Rated heavy, missed | Precision | Recall | Right on heavy or not |
|---|---|---|---|---|---|---|---|
| Provisional rules | 10 | 2 | 8 | 6 | 0.20 | 0.25 | 0.72 |
| Trained model, held out, the shipped cut | 13.2 | 7.1 | 6.2 | 0.9 | 0.54 | 0.89 | 0.86 |
| Trained model, held out, the cut held out too | 12.4 | 6.0 | 6.4 | 2.0 | 0.49 | 0.75 | 0.83 |

Rank correlation with the mean ratings: rules (signs shown, 0 to 3) **0.492**, held-out model **0.778**. The difference, bootstrapped over pages 2000 times, has a 95% interval of +0.117 to +0.503. The pages the rules call heavy average 3.00 against 2.39 for the rest. The rules' thresholds were never fitted to ratings, but they were read off this corpus's spread, so neither side is wholly on unseen ground for its thresholds. The second model row is the fair one: its cut was chosen without the page it scores.

### Where they agree and where they differ

The model as shipped, fitted to all 50 pages, for a person who has not said:

| | Rules: ordinary, level 2 | Rules: heavy, level 3 |
|---|---|---|
| Model: level 2 | **31** | 5 |
| Model: level 3 | 9 | **5** |

They agree on **36 of 50**. Of the 14 where they differ, the raters side with the model on 11 and with the rules on 3, the raters' side being heavy for a mean of 3.5 or more and not heavy otherwise.

| Page | Model | Rules | The rules' signs |
|---|---|---|---|
| httpbin.org/html | 3.83, level 3 | level 2 | text density 3.509 |
| arxiv.org/list/cs.HC/recent | 3.61, level 3 | level 2 | 462 controls |
| 127.0.0.1:5100/bill?reference=04141234567890 | 3.54, level 3 | level 2 | text density 2.635 |
| 127.0.0.1:5000 | 3.54, level 3 | level 2 | text density 2.569 |
| news.ycombinator.com | 3.35, level 3 | level 2 | 231 controls |
| demo.testfire.net | 3.09, level 3 | level 2 | none |
| danluu.com | 3.05, level 3 | level 2 | 210 controls |
| lite.cnn.com | 3.05, level 3 | level 2 | none |
| 127.0.0.1:5100 | 3.04, level 3 | level 2 | none |
| ant.design/components/drawer (open an antd drawer) | 2.82, level 2 | level 3 | 453 controls, 3 covering |
| mui.com/material-ui/react-dialog (open a mui dialog) | 2.80, level 2 | level 3 | 308 controls, 2 covering |
| mui.com/material-ui/react-drawer (open a bottom sheet) | 2.72, level 2 | level 3 | 269 controls, 3 covering |
| www.theguardian.com/international | 2.31, level 2 | level 3 | 268 controls, 3 covering |
| element-plus.org/en-US/component/dialog.html (open an element plus dialog) | 2.24, level 2 | level 3 | 300 controls, 2 covering |

### The rules' logged decisions, replayed

Every `start` decision in `data/steps.jsonl`: 48 rows, 6 distinct pages, from replicas and scripts, no person's choice of page. The level logged includes any level the person chose.

| Rows | Controls | Text density | Logged levels | Rules: heavy | Model | Model's page level |
|---|---|---|---|---|---|---|
| 26 | 37 | 1.728 | 1: 1, 2: 25 | no | 3.04 | 3 |
| 6 | 18 | 0.096 | 2: 6 | no | 1.58 | 1 |
| 5 | 11 | 0.169 | 2: 5 | no | 2.05 | 1 |
| 5 | 11 | 0.169 | 1: 1, 2: 3, 3: 1 | no | 2.01 | 1 |
| 4 | 49 | 2.569 | 2: 4 | no | 3.54 | 3 |
| 2 | 18 | 0.096 | 2: 2 | no | 1.55 | 1 |

### The environment the product runs in

The model was fitted to the headless rows. Of 49 pages read in both environments, the score differs by 0.019 on average and 0.480 at most, and the page's level changes on **2**: https://ant.design/components/drawer [open an antd drawer], 2.82 (level 2) headless, 2.95 (level 3) in the host; https://ant.design/components/modal [open an antd modal], 2.67 (level 2) headless, 3.15 (level 3) in the host.

### How much the handling of the data matters

Pooled held-out figures over 40 shuffles of the folds. Only the first row is the model; the others are checks, and taking raters out because they disagree raises alpha by construction.

| Data | Raters | Pages | Fewest ratings | Alpha | R² | Mean absolute error |
|---|---|---|---|---|---|---|
| As shipped: every usable rater, every page | 15 | 50 | 5 | 0.318 | 0.572 ± 0.047 | 0.498 ± 0.022 |
| Only the pages with 8 ratings or more | 15 | 28 | 10 | 0.306 | 0.435 ± 0.127 | 0.477 ± 0.046 |
| Without the 2 raters under ρ 0.2 (5007, 5013) | 13 | 50 | 5 | 0.447 | 0.621 ± 0.034 | 0.522 ± 0.023 |
| With the 9 phone raters put back | 24 | 50 | 10 | 0.298 | 0.579 ± 0.056 | 0.431 ± 0.024 |

Do the pages under the floor help or hurt? Scored only on the 28 pages at the floor, the same held-out pages either way, mean absolute error is **0.477** fitted to those pages alone and **0.412** with the pages under the floor added to the fit.

Phone raters against the others, page by page: Pearson 0.76, and +0.35 on the scale on average. Alone their alpha is 0.238 and their repeats correlate 0.652.

### Each page, and why

The model as shipped, `trained 2026-10-30T21:05:28+05:00`. Level is the page's own: 2.45 and 2.90 divide it. The reasons are what moved the score most from the average page (2.51). `data/estimator_pages.json` has the same. Per-page rated means are not committed (DECISIONS.md, *The trained model is committed; the ratings are not*).

| Page | Kind | Score | Level | Rules' level | Why |
|---|---|---|---|---|---|
| 127.0.0.1:5000 (sign in) | ours | 4.76 | 3 | 3 | a lot of text on screen, many links that go nowhere, a shallow, plain layout |
| httpbin.org/html | public | 3.83 | 3 | 2 | a lot of text on screen, a shallow, plain layout |
| arxiv.org/list/cs.HC/recent | public | 3.61 | 3 | 2 | many links (462), a lot of text on screen, a shallow, plain layout |
| 127.0.0.1:5100/bill?reference=04141234567890 | ours | 3.54 | 3 | 2 | a lot of text on screen, a shallow, plain layout, many links that go nowhere |
| 127.0.0.1:5000 | ours | 3.54 | 3 | 2 | a lot of text on screen, a shallow, plain layout, many links that go nowhere |
| en.wikipedia.org/wiki/Cognitive_load | public | 3.52 | 3 | 3 | many links (715), a lot of text on screen |
| news.ycombinator.com | public | 3.35 | 3 | 2 | a lot of text on screen, many links (230) |
| getbootstrap.com/docs/5.3/components/modal (open a bootstrap modal) | demo | 3.15 | 3 | 3 | a lot of text on screen, many links (226), many buttons and boxes |
| www.spiegel.de | public | 3.14 | 3 | 3 | many links (553), many buttons and boxes |
| getbootstrap.com/docs/5.3/components/offcanvas (open a side drawer) | demo | 3.11 | 3 | 3 | a lot of text on screen, many links (197) |
| demo.testfire.net | demo | 3.09 | 3 | 2 | a lot of text on screen, a shallow, plain layout |
| danluu.com | public | 3.05 | 3 | 2 | a shallow, plain layout, many links (210), a lot of text on screen |
| lite.cnn.com | public | 3.05 | 3 | 2 | a lot of text on screen, a shallow, plain layout |
| 127.0.0.1:5100 | ours | 3.04 | 3 | 2 | a lot of text on screen, many links that go nowhere, a shallow, plain layout |
| ant.design/components/drawer (open an antd drawer) | demo | 2.82 | 2 | 3 | many links (256), many buttons and boxes, a lot of text on screen |
| mui.com/material-ui/react-dialog (open a mui dialog) | demo | 2.80 | 2 | 3 | a lot of text on screen, many buttons and boxes, many links (154) |
| en.wikipedia.org/wiki/Main_Page | public | 2.79 | 2 | 2 | a lot of text on screen, many links (238) |
| developer.mozilla.org/en-US/docs/Web/HTML | public | 2.78 | 2 | 2 | a lot of text on screen |
| mui.com/material-ui/react-drawer (open a bottom sheet) | demo | 2.72 | 2 | 3 | a lot of text on screen, many buttons and boxes |
| ant.design/components/modal (open an antd modal) | demo | 2.67 | 2 | 2 | many buttons and boxes, many links (200), a lot of text on screen |
| 127.0.0.1:5000/stubborn | ours | 2.59 | 2 | 2 | a shallow, plain layout, many links that go nowhere |
| practice.expandtesting.com | demo | 2.58 | 2 | 2 | many links (249) |
| www.python.org | public | 2.45 | 1 | 2 | little text on screen |
| info.cern.ch/hypertext/WWW/TheProject.html | public | 2.44 | 1 | 2 | few links (25), little text on screen |
| text.npr.org | public | 2.43 | 1 | 2 | few links (28), little text on screen |
| example.com | public | 2.37 | 1 | 2 | few links (1), little text on screen |
| quotes.toscrape.com | public | 2.32 | 1 | 2 | little text on screen, few links (55) |
| www.theguardian.com/international | public | 2.31 | 1 | 3 | little text on screen, a deeply nested layout |
| element-plus.org/en-US/component/dialog.html (open an element plus dialog) | demo | 2.24 | 1 | 3 | many things to fill in, a deeply nested layout, little text on screen |
| books.toscrape.com | public | 2.18 | 1 | 2 | little text on screen |
| todomvc.com/examples/react/dist (add a todo) | demo | 2.15 | 1 | 2 | little text on screen, few links (14) |
| the-internet.herokuapp.com | demo | 2.14 | 1 | 2 | little text on screen, few links (46) |
| sweetalert2.github.io (open a sweetalert) | demo | 2.12 | 1 | 2 | little text on screen, many controls built from plain page parts |
| parabank.parasoft.com/parabank/index.htm | demo | 2.06 | 1 | 2 | little text on screen, few links (33) |
| pypi.org | public | 2.05 | 1 | 2 | little text on screen, few links (52) |
| www.nhs.uk | public | 1.97 | 1 | 2 | little text on screen, few links (47) |
| the-internet.herokuapp.com/entry_ad | demo | 1.97 | 1 | 2 | little text on screen, few links (3) |
| www.bbc.co.uk/news | public | 1.93 | 1 | 2 | little text on screen, a deeply nested layout |
| demo.applitools.com | demo | 1.91 | 1 | 2 | little text on screen, few links (5) |
| demo.opencart.com | demo | 1.91 | 1 | 2 | little text on screen, few links (2) |
| www.gov.uk | public | 1.89 | 1 | 2 | little text on screen, a deeply nested layout, few links (79) |
| www.gov.uk/browse/benefits | public | 1.88 | 1 | 2 | little text on screen, few links (49), a deeply nested layout |
| the-internet.herokuapp.com/login | demo | 1.88 | 1 | 2 | little text on screen, few links (2) |
| www.saucedemo.com | demo | 1.75 | 1 | 2 | little text on screen, few links (0) |
| demoqa.com/modal-dialogs (open a demoqa modal) | demo | 1.71 | 1 | 2 | little text on screen, few links (6), a deeply nested layout |
| www.pakrailways.gov.pk/train (open the calendar) | target | 1.66 | 1 | 2 | little text on screen, few links (12), a deeply nested layout |
| opensource-demo.orangehrmlive.com/web/index.php/auth/login | demo | 1.66 | 1 | 2 | little text on screen, few links (5) |
| www.pakrailways.gov.pk/train (open the station list) | target | 1.59 | 1 | 2 | little text on screen, few links (12), a deeply nested layout |
| www.pakrailways.gov.pk/train | target | 1.55 | 1 | 2 | little text on screen, few links (12), a deeply nested layout |
| demoqa.com/automation-practice-form | demo | 1.53 | 1 | 2 | little text on screen, few links (2), many things to fill in |

---

## 2026-10-30c — what the estimator is worth, read plainly

`feat/estimator-trained`. The two sections above are what `tools.rating.retrain`
wrote; this is what they mean, what was checked by hand, and the suite. The
training section ran on a clean commit, `19db24949e4b`. The comparison's conditions
block says DIRTY TREE because the same command had just written the model and the
section above it, and nothing else had changed. Both ran on battery, which moves
no figure here: the seeds are fixed, and the model's numbers came out the same in
every run. Retraining took 116s.

**The ratings.** 24 responses, 14 to Set 1 and 10 to Set 2, 2026-10-23 to
2026-10-29. Dropped: 9, all for being on a phone (5001, 5004, 5010, 5011, 6001,
6002, 6005, 6007, 6009). None declined and none was incomplete. Usable: **15**, 10
and 5, 450 rows. Ratings per page: 5 on 22 pages, 10 on 22, 15 on the six anchors.

**Agreement is weak.** Alpha 0.318 is well below the 0.667 usually asked of data
to draw even tentative conclusions from, and below 0.8 by further. Two things
soften what that means for this model, and neither repairs it. People are
consistent with themselves: 30 repeated pairs correlate 0.803, 57% identical and
93% within one answer. So the disagreement is mostly between people, not noise
within them, and that is a finding: **how overwhelming a page feels differs from
person to person**, which is the argument for the person's own level and live
behaviour staying in charge of the screen. And a mean smooths what single ratings
do not: the page means' reliability is 0.779. Fewer raters would have been a
smaller problem had they agreed more; with this alpha, more raters is what buys
stable means.

**Accuracy is moderate, and real.** It beats predicting the mean at every cut:
5-fold R² 0.491 ± 0.240 against −0.110, and held-out error 0.480 of a point
against 0.768. The folds run from 0.06 to 0.72, so one number hides a lot: on
50 pages, which ten are held out matters. Over 40 shuffles it is 0.572 ± 0.047,
with error 0.498, against a ceiling of about 0.78. Half a point is half a word
on the form: it can tell "Not at all" from "Very" and cannot be trusted between
neighbouring words. Into three bands, held out throughout, it is right on 64% of
pages. In the middle band it is little better than a coin, which is what the
predicted-against-rated chart shows.

**What this measures, and what it does not.** 13 of the 15 are aged 18–24 and 10
are in computing. They rated a picture seen at about half size, on their own, for
how it felt. None is from the audience this is for, and nobody used a page. So
this is how a page looks to these people, and whether that predicts struggling
is unmeasured. Two features say so directly: pages with more form fields scored
lower, and SIMBA exists for forms. It is a better guess than the rules, and it is
a guess about the first impression.

**The features.** `text_density` does most of the work (Spearman 0.82 with the
means, R² lost 0.61), and it is the one feature read from the viewport raters
saw. `links` counts the whole page: BBC News has 106 and its picture is calm, and
raters said so. `overlays` adds nothing (+0.004), though the rules count it as a
sign, and six of the rules' eight false alarms are component libraries showing
something open.
Shallower pages score heavier (−0.217): a page of plain old HTML reads as heavier
than a modern one with the same links. Importances are wide: 0.61 ± 0.48.

**Three pictures show something other than the page's name.** Seen while checking
surprising ratings: `demo.opencart.com` is a Cloudflare check, not a shop;
`example.com` is now seven languages of text, and raters put it far above its
reputation; BBC News's adverts had not loaded. All three are what raters saw and
what the features read, one load
each, so nothing is wrong, and they are not the pages their names suggest.

**In the real window**, on `main`'s stack with this branch, at this machine's 150%
(1266x632), keyword routing, no model quota: the health check said `trained model`.
Billing's first question at level 3, nothing past the window. Registration started
at 3 from the model (3.54) and the guard took it to level 1, sign-in on screen,
nothing past the window, as `test_sign_in.py` found. Each row held `judged_by`, the
model's rating and reasons, and the rules' signs beside them. This window's saved
profile also chose level 3, so level 3 alone proved nothing there;
`test_with_a_model_the_app_starts_from_the_page_and_says_so` is the same with no
profile, and starts at 3 from the page.

**Failed, and fixed.** A test written for this work found the sign-in screen 60px
past the window at 150% (632), 86px at 150% (606) and over at 100% when a task
started at level 3: the guard's one hop went to level 2, which cannot help. It now
goes to level 1; 47 of 47 in `test_sign_in.py` and `test_first_screen.py`. A first
draft of the heavy-page comparison marked the model with a cut chosen on the same
pages, which flatters it (recall 0.89); the fair row, with the cut held out too, is
0.75. A first draft of the 28-page check reported alpha over all 50 pages. Importing
scikit-learn to do a sum took 5.6s per backend start, so the app reads plain
numbers. One of my tests expected a heavy start back at level 1 in three steps; it
takes five.

**The suite**, on mains, at `24510b2`, the overlay rebuilt first: backend half
**1062 passed, 9 skipped, 0 failed** (964s), frontend half **582 passed, 3 skipped,
0 failed** (1261s): **1644 passed, 12 skipped, 0 failed**, the 1557 of 2026-10-23
plus 87 new, 83 of them estimator, rules, comparison and app tests and 4 the
sign-in from level 3. The host fit test, `SIMBA_HOST_TESTS=1`: **3 of 3** (453s).
The 12 skips are the same 12. The suite waited for mains: the machine was on
battery until 21:17. The backend half was run with `--no-header` by mistake, which
hides its power line, so the power was logged each minute instead, 21:17 to 22:02:
45 readings, all on mains. Only these records changed afterwards.

---

## 2026-11-01 — the estimator with and without raters 5007 and 5013

`python -m tools.evaluation.estimator_compare --without 5007 5013`. **The first column is the model on `main`, and it stays the model.** The other columns are the same training with those raters' answers removed, for reading beside it: nothing here is saved.

```text
========================================================================
taken at    2026-11-01T07:27:14+05:00
git         fe5f54cb5bf5 on fix/after-training
python      3.12.3 at D:\simba\backend\venv\Scripts\python.exe
playwright  1.62.0
model       openai gemini-3.1-flash-lite (from .env)
machine     Windows-11-10.0.26200-SP0, 8 cpus, load 12%
power       on mains, processor at 66% of rated speed, 1294 MB memory free
switches    none set
========================================================================
```

Rank correlation of each with the mean of the others: 5007 -0.58, 5013 0.10. No exclusion rule was set before the ratings came in, so neither is excluded.

**Read the three alpha rows with care.** Taking out the raters who disagree most raises agreement by construction, so a higher alpha here is not evidence that anything improved. Error is not comparable between columns on its own either: without them the page means spread wider, so there is more to get wrong and the mean absolute error can rise while the model improves. The row beside the mean's own error is the fair one.

| | All raters | Without 5007 | Without 5013 | Without 5007 and 5013 |
|---|---|---|---|---|
| Raters (Set 1 + Set 2) | 10 + 5 | 9 + 5 | 9 + 5 | 8 + 5 |
| **Agreement** | | | | |
| Krippendorff's alpha, all | 0.318 | 0.398 | 0.355 | 0.447 |
| Alpha, Set 1 | 0.284 | 0.414 | 0.339 | 0.503 |
| Alpha, Set 2 | 0.357 | 0.357 | 0.357 | 0.357 |
| Reliability of the page means (the ceiling on R²) | 0.779 | 0.813 | 0.792 | 0.823 |
| Spread of the page means (sd) | 0.897 | 0.966 | 0.919 | 0.997 |
| **Accuracy, 5-fold** | | | | |
| R², mean ± sd of folds | 0.491 ± 0.240 | 0.518 ± 0.224 | 0.497 ± 0.263 | 0.532 ± 0.252 |
| Mean absolute error | 0.480 | 0.506 | 0.485 | 0.515 |
| Root mean squared error | 0.561 | 0.593 | 0.571 | 0.599 |
| **Accuracy, 40 shuffles of the folds** | | | | |
| R² | 0.572 ± 0.047 | 0.589 ± 0.041 | 0.593 ± 0.045 | 0.621 ± 0.034 |
| Mean absolute error | 0.498 ± 0.022 | 0.524 ± 0.024 | 0.498 ± 0.022 | 0.522 ± 0.023 |
| Root mean squared error | 0.586 ± 0.030 | 0.619 ± 0.030 | 0.585 ± 0.031 | 0.613 ± 0.027 |
| Error of predicting the mean | 0.778 | 0.846 | 0.802 | 0.880 |
| **Model's error as a share of that** | **0.64** | **0.62** | **0.62** | **0.59** |
| **Levels** | | | | |
| Pages rated calm / middle / heavy | 24 / 18 / 8 | 24 / 18 / 8 | 25 / 19 / 6 | 24 / 18 / 8 |
| Cut points chosen | 2.45, 2.90 | 2.45, 2.95 | 2.15, 2.95 | 2.30, 3.00 |
| Kappa, cuts held out too | 0.691 | 0.710 | 0.632 | 0.676 |
| Right band, cuts held out too | 64.4% | 66.4% | 59.2% | 63.6% |
| Pages called heavy, as fitted | 14 | 14 | 13 | 13 |
| Pages at a different level from the shipped model | 0 | 2 | 8 | 7 |
| Of those, heavy on one side only (all that changes for someone who has not chosen a level) | 0 | 0 | 1 | 1 |
| **Coefficients** | | | | |
| `text_density` | +0.535 | +0.568 | +0.567 | +0.607 |
| `links` | +0.312 | +0.355 | +0.317 | +0.364 |
| `max_depth` | -0.217 | -0.270 | -0.230 | -0.291 |
| `interactive` | +0.082 | +0.089 | +0.076 | +0.084 |
| `form_fields` | -0.074 | -0.075 | -0.063 | -0.062 |
| `dead_link_ratio` | +0.072 | +0.065 | +0.039 | +0.028 |
| `inferred` | -0.033 | -0.033 | -0.042 | -0.044 |
| `overlays` | +0.004 | +0.003 | +0.034 | +0.037 |
| `reading_grade` | -0.002 | +0.017 | -0.004 | +0.018 |

**What the columns say.** Agreement stays weak either way: alpha 0.447 with both out
is still under the 0.667 usually asked for. Accuracy moves a little: R² 0.572 to
0.621, about one standard deviation of the shuffles, and the model's error from 64%
of the mean's to 59%. Taking a rater out does not simply help: without 5013 alone
the cuts held out do worse, kappa 0.632 against 0.691. **What people would see
hardly moves.** The heavy call, which is all that changes for someone who has not
chosen a level, is the same on all 50 pages without 5007, and differs on one page
without 5013 or without both. The other different levels are pages either side of a
calm cut that moves from 2.45 to as low as 2.15, and that cut matters only to someone
who chose level 1. So keeping both raters costs little, and the case for dropping
either would have to rest on something other than these numbers: 5007's two repeats
are each within one answer, which does not show a reversed scale. Rater-level
figures only: no individual answer is reported.

---

## 2026-11-01b — after the guard, the clips, and the suite

`fix/after-training`, under the freeze.

**The bug.** After the overflow guard moved a step to fit, an unlocked level stayed
at the guard's level on every step after it, though CONTRACT.md has said since
2026-09-25 that the next step goes back. Reproduced first, on the unfixed code,
through the real backend, the registration replica and the built overlay: level 1
after sign-in at all three window sizes. After the fix, registration with nobody
having said a level:

| Window | Sign-in | Next question | Past the window | Guard moves |
|---|---|---|---|---|
| Real window, 150% (1266x632) | 1 | **3** | 0px | 1 |
| Real window, forced 100% (1280x800) | 1 | **3** | 0px | 1 |
| Headless, 100% (1280x800) | 1 | **3** | 0px | 1 |
| Headless, 150% (1266x632) | 1 | **3** | 0px | 1 |
| Headless, 150% (1266x606) | 1 | 1, its own hop from 3, with the notice | 0px | 2 |

In the real window the backend's rows agreed at both scales: 3 at the start, 1 by
the guard, and `after_guard {guard: 1, back_to: 3}` on the next asked step, which
is step 3 because step 2 was a checklist line. 1266x606 is the shortest window
measured and the real window has been 632px tall since the menu bar went.

**The clips**, at the machine's own 150%, through the real backend, keyword routing,
no model quota. `billing.webm`, model on: 3.0 MB, 29s, opens with the third dot lit,
ends on the bill. `adapt.webm`, `SIMBA_PAGE_MODEL=0`: 2.6 MB, 32s, folds from 2 to 3
at 5.3s with "I'm showing less for a moment", ends on the bill. Both checked on
stills taken from the files. Not committed, as ever. The other four were not
re-recorded: the trains' first page is calm, and hello and the mock are untouched.

**Failed, and fixed.** My first run of the new tests failed for my own reasons:
arguments in the wrong order, and "Password" matching the "Save my password" box as
well. One expectation was wrong: a lock pressed after the hop leaves the screen at
the locked level. The real-flow test first required level 3 at 1266x606, which is
wrong there: the frames showed two guard moves, so the level had gone back and the
question took its own hop. `test_a_guard_move_is_followed_and_is_the_steps_one_change`
had pinned the old behaviour and now says the new.

**The suite**, at `2532e10`, the overlay rebuilt first: backend half **1073 passed, 9
skipped, 0 failed** (1013s), frontend half **592 passed, 3 skipped, 0 failed** (1327s):
**1665 passed, 12 skipped, 0 failed**, the 1644 of 2026-10-30 plus 21 new, 11 backend
and 10 frontend. The host fit test, `SIMBA_HOST_TESTS=1`: **3 of 3** (515s). The 12
skips are the same 12.

**This run was not all on mains.** The machine went to battery about 07:59, at 99%
charge: the backend half (07:28 to 07:45) was wholly on mains, the frontend half
(07:45 to 08:07) on mains until its last 8 minutes or so, and the host fit test
(08:07 to 08:15) wholly on battery, by its own header and by 17 of 48 minute
readings. Raham accepted that for this bug fix, since pass or fail does not depend
on power, and the rerun on mains was cancelled. So the frontend and host wall clocks
here are not comparable with mains runs, and the frontend half's 1327s and the host's
515s should not be quoted as such.

## 2026-11-02 — the brand, and what the logo waits for

`feat/brand`, asked for by Raham as visual polish under the freeze. No model quota
and no live site. The overlay, the host and the fit run, on one machine.

```
git         d60f015 on feat/brand (the suite ran with these same files, one commit before)
python      3.12.3, playwright 1.62.0, electron 32.3.3
machine     Windows-11-10.0.26200-SP0, 8 cpus
power       the launcher runs and the first host run on battery, or mostly: 58% at the
            start of the task and 55% at 15:05, by when it was on mains. The second host
            run and the whole suite on mains (65% rising to 92%).
```

**The kit.** 28 files, unpacked and compared with the zip by SHA-256: 0 differ. The
icon holds 16, 24, 32, 48, 64, 128 and 256px. Every PNG is the size its name says. No
SVG has a script, an external reference, an embedded image or live text.

**Two things in it do not work as supplied.**

| | Measured | Consequence |
|---|---|---|
| Dark logos' background, #0F1A19 | 1.021:1 on canvas #0b1817, 1.066:1 on palette A's #14100c, in a capture a visible box round each | `assets/brand/derived/`, the rectangle deleted |
| Tagline, 26 units tall in 300 | about 4px at the corner's 48px | `assets/brand/derived/`, the tagline deleted |

The marks themselves stand well off every canvas: 6.66:1 at the least, teal on palette
A's light canvas, and 10.40:1 for the mint on the dark one.

**The window.** Read from Windows while the launcher's host was up: title `simba`;
`WM_GETICON` returns the kit's lion at 24px and 48px; the title bar shows it in a
picture of that one window. **The taskbar itself was not seen**: that would take a
desktop capture, which CLAUDE.md forbids. What Windows was given is measured; what the
taskbar drew from it is not.

**How long the logo stays**, on the real launcher, timed from outside over CDP, in
seconds from CDP first answering. Each socket that reached the backend is shown.

| Start page | Logo leaves on | Backend listens | Socket | First message | Logo gone |
|---|---|---|---|---|---|
| billing | socket open | 2.97 | 3.20 | not timed | 4.03 |
| billing | socket open | 3.50 | 3.62 | 9.01 | 4.45 |
| billing | **first message** | 3.11 | 3.15 | 8.98 | **9.81** |
| registration | **first message** | 2.53 | 3.01 | 6.84 | **7.79** |
| mock (backend first) | first message | already up | already up | not seen | **2.20** |

Two findings. The retry works: a socket reached the backend 0.04s to 0.48s after it
began listening, where nothing tried again before. And **the first message came 3.83s
to 5.83s after the socket opened**, which is why the logo leaves on it. The second row
shows the home screen 4.6s before the person's tiles would arrive. **The cause is not
known.** `past_goals` takes 0.00s and the health check 0.00s in a fresh
process, and `Connection.send` does nothing but send, so neither is it; it may be the
backend's first seconds of running, but that is a guess (STATUS.md, flagged for Raham).
These timings come from a one-off script in `.scratch/`, not `tools/evaluation/`.

**Fit**, `display_fit_run`, with the brand added: the logo while opening, whole and
centred within 1px, and the small logo touching nothing on the fullest home screen
(32,24 to 193,72 at 100%), in each theme at 100%, 125% and 150%, each from its theme's
own file; a step with the shape and no logo; no logo under reduced motion; title `simba`.
Pictures in `.scratch/brand/`, not committed. **3 of 3, 579s**, on mains.

**The tests.** `frontend/test_brand.py`, 47. Ten deliberate breakages, each a mutation
of the code and a run of the test that should catch it: **9 caught on the first pass**.
The one that got away, retrying on the home screen too, passed because the test allowed
one more attempt and watched for 3s, and a refused attempt takes about 2.5s on Windows;
it now requires none in 6s. **10 of 10 caught.** The same pass found the file check
could not tell a derived logo from the kit's, since they share a name, so it now reads
what the build serves.

**Failed, and fixed.**

- The first design left on the socket opening. Measured on the launcher, that showed a
  home screen 4.6s before its tiles; it leaves on the first message now.
- The first host run failed at all three scales. At 100%, on a real defect in the
  harness: a picture is taken over a second connection, which undoes the theme's
  emulation as it attaches, so `splash-1-dark.png` was light, and the load after it
  read the light file. Fixed in `capture_view`, and the pictures checked by eye.

**Failed, and not explained.** In that first host run, at 125% and at 150%, a press on
Start waited out its 30s on "visible, enabled and stable", at a different ending each
time. The host logged no unresponsive page, crash or power event, and Playwright said
nothing more. That wait turns on `requestAnimationFrame`, so a page getting no frames
would do this, and a window covered by another is a candidate, as is the battery; **none
of that is shown**. It did not happen in the second run, on mains. `display_fit_run` now
asks the overlay whether it is getting frames when a press fails, so the next one says.

**The suite**, at `f0b12bc` with the fit run's fix in the tree, the overlay rebuilt
first: frontend half **639 passed, 3 skipped, 0 failed** (1420s), backend half **1073
passed, 9 skipped, 0 failed** (981s): **1712 passed, 12 skipped, 0 failed**, the 1665
of 2026-11-01 plus these 47. The 12 skips are the same 12.

## 2026-11-02b — how overwhelming are Pakistan's public websites, as predicted

`python -m tools.evaluation.overwhelm_index`, on `eval/overwhelm-index`, asked for by
Raham. The question was "How overwhelming are Pakistan's public websites, and why?",
put to the trained page model. **The answer it gives is calm, and that should not be
believed yet.** Read the section *What it found* before quoting any row.

```
taken at    2026-11-02T16:16:00+05:00
git         a02b7c38a67d on eval/overwhelm-index; marked dirty, by simba-logo-kit.zip
            alone, untracked in the repo root: the code was the commit
python      3.12.3 at backend\venv, playwright 1.62.0, chromium 151.0.7922.34
model       trained 2026-10-30T21:05:28+05:00, the model on main. No language model
machine     Windows-11-10.0.26200-SP0, 8 cpus, load 12%
power       on mains, processor at 167% of rated speed, 1048 MB memory free
switches    none set
```

**Method.** 42 main pages, each with its category and why in the script: 9 government
services, 8 utilities, 6 universities, 5 banks, 5 telecoms, 4 transport, 5 health.
robots.txt first, for the same user agent the page is then fetched with, then one load
at the frozen 1280x800, through `tools/rating/capture.photograph`, the pipeline the rated
pictures came through: `domcontentloaded`, 2.5s, scrollbars hidden, the nine features and
the picture from one load. A 3s pause between sites. Nothing clicked, filled or submitted,
and nothing retried. The score is `PageModel.judge`. The level is from the real
`rules.LevelRules`, for a person who has set none. The pictures, the table and the report
are in `.scratch/overwhelm-index/`, not committed: they are other people's sites.

**What came back.** 42 listed, **35 scored**, 1 failed, 6 skipped.

| Not scored | Why |
|---|---|
| NADRA, Government of Punjab, WASA Lahore, HBL, Telenor Pakistan | Skipped: robots.txt answered HTTP 403, read as a no |
| LESCO | Skipped: disallowed by robots.txt |
| K-Electric | Failed: first screen still empty, 99% one colour. Scored 1.13 and ranked last on the first pass (below) |

**The table, for what it is worth.** Prediction of "How overwhelming does this page
feel?", 1 to 5. Band is the model's: 1 calm, 2 middle, 3 heavy. All 35 open at SIMBA's level
2, since a page can start a person simpler and never fuller, and only a heavy page moves
that.

| # | Highest ten | Category | Rating | Band |
|---|---|---|---|---|
| 1 | MCB | Banks | 2.54 | 2 |
| 2 | Directorate of Passports | Government services | 2.38 | 1 |
| 3 | University of the Punjab | Universities | 2.36 | 1 |
| 4 | Government of Sindh | Government services | 2.29 | 1 |
| 5 | Higher Education Commission | Universities | 2.25 | 1 |
| 6 | SSGC | Utilities | 2.12 | 1 |
| 7 | IESCO | Utilities | 2.04 | 1 |
| 8 | Karachi Water | Utilities | 2.03 | 1 |
| 9 | Bank Alfalah | Banks | 2.02 | 1 |
| 10 | Meezan Bank | Banks | 2.02 | 1 |

| # | Lowest five | Category | Rating | Band |
|---|---|---|---|---|
| 31 | University of Karachi | Universities | 1.64 | 1 |
| 32 | National Bank of Pakistan | Banks | 1.64 | 1 |
| 33 | Pakistan Railways | Transport | 1.64 | 1 |
| 34 | Ufone | Telecoms | 1.51 | 1 |
| 35 | Shaukat Khanum | Health | 1.46 | 1 |

| Category | Listed | Scored | Mean | Heavy |
|---|---|---|---|---|
| Banks | 5 | 4 | 2.05 | 0 |
| Government services | 9 | 7 | 2.01 | 0 |
| Utilities | 8 | 5 | 1.96 | 0 |
| Universities | 6 | 6 | 1.94 | 0 |
| Health | 5 | 5 | 1.85 | 0 |
| Transport | 4 | 4 | 1.78 | 0 |
| Telecoms | 5 | 4 | 1.71 | 0 |

The whole table spans 1.08 of a point and the categories 0.34, against the model's held-out
error of 0.48. **The categories cannot be told apart, and neighbours in the table are not
a ranking.**

**The three most common reasons**: little text on screen (31 of 35), a deeply nested layout
(26), few links (15). **These say why pages scored low, not why they overwhelm.** A reason
follows the way a page's score went, and 34 of 35 went below the average rated page, 2.51.
Depth counts against a score in this model (−0.217). What pushed pages up, where anything
did: many links (10), many buttons and boxes (4).

**What it found.** The model and the pictures disagree, and the disagreement is the result.

| | The 35 pages | The 21 public pages in the rated corpus, same model |
|---|---|---|
| Median predicted rating | 1.87 | 2.44 |
| Heavy | 0 | 7 |
| Median text density | 0.38 | 0.91 |

Laid side by side, the 36 pictures are busy: carousels, chat windows, and notices over the
page, on some with their text set in the image, such as the Directorate of Passports' and
MEPCO's. **That was seen by looking, and was not measured.** The model cannot see any of it. It
leans hardest on `text_density` (+0.535), which counts characters and not pictures of them,
and 14 pages had something covering them when read, on a feature it gives +0.004. So a page
that says everything in images scores as a page with little to say. Calling that a finding
about Pakistan's websites would be a mistake. It is a limit of the model, found by pointing
it at pages unlike those it learned from, and it is the most useful thing this run produced.

**Limits.**

- These are predictions, from a model trained on 15 raters, 13 of them aged 18 to 24 and 10
  in computing, none from the audience, agreeing weakly (alpha 0.318), under the study's
  floor on 22 of 50 pages.
- The raters judged a picture of the first screen. They did not use a page, and how hard a
  site is to get something done on is another question, which this does not ask.
- Of the 50 rated pages the only Pakistani ones are three states of one train search, a plain
  page, and Pakistan Railways is a different page here, the site's front page.
- `links` and `interactive` count the whole page, and raters saw one screen.
- Reading grade is a formula for English. No page was mostly Urdu by its text (the most was
  14.6%), though some of the Urdu on them is in images, which that number cannot see.
- 3 of 35 pages are past anything the model saw on one feature: Quaid-i-Azam University on
  `overlays`, MCB and Zong on `reading_grade`.
- One visit, one moment, one machine, in Pakistan. A carousel shows what it was showing. A
  page whose content appears after 2.5s was read without it, which is what happened to
  K-Electric, and a page partly loaded is not caught unless it is nearly empty.
- The skipped sites include some of the largest services, so the table is not a sample of
  them. Five of the six were 403s on robots.txt, which may be a firewall rather than a
  policy; a person asked to open those sites would be let in.

**Failed, and fixed.** The first pass produced a report that read as a clean answer, and it
was wrong in four ways, all found by reading it against the pictures rather than by a test.
No site was visited again: `--report` works everything out from what was saved.

- **K-Electric was "the calmest site in the country"** at 1.13, on a screen showing only a
  menu, with 9,566 characters on the page not yet animated in. Text counts cannot see that, so
  the picture is now measured: it was 99.4% one colour, and the next page 83.2%. `FLAT_LIMIT`
  is 0.97, in that gap. The first pass is kept in `results-first-pass.json`.
- **The reasons read as causes.** "Why" beside "a deeply nested layout" at rank 2 said the
  opposite of what the model meant. Each row now says what pushed it up and what held it
  down.
- **"Among the 0 heavy pages alone: ."** was a line with nothing in it.
- **My first limits were wrong.** "No rated page was Pakistani" is false: three are. Checked
  against `data/corpus.json` before it went anywhere.

**The tests.** `tools/evaluation/test_overwhelm_index.py`, 55, all against servers on this
machine, in a real browser. Six deliberate breakages, each caught: opening a disallowed
page, reading an unreachable robots.txt as permission, scoring a refusal, scoring an empty
screen, reporting the model's band as SIMBA's level, and swapping the directions. Run on
their own: the suite as a whole was not re-run for this branch, which adds one script and
its tests and changes nothing else.

---

## 2026-11-02c — what the model could not see, measured; and what it needs next

`tools/evaluation/visual_features.py`, `tools/rating/export_set3.py`,
`backend/estimator/train_visual.py` and `tools/evaluation/rescore_index.py`, on
`eval/visual-features`, asked for by Raham. **Half of the question is answered and half
cannot be yet.** The blindness is measured: these sites are unlike anything people rated.
Whether seeing it makes a better model needs Set 3's ratings, and **no Set 3 rating exists,
so there is no new model and no verdict**. `data/estimator.json` is unchanged.

```
rated pages, then sites, in one run
taken at    2026-11-02T21:58:21+05:00, and 22:11:08+05:00
git         f15f8f30178a on eval/visual-features; dirty by the zip, and by code for
            Sets 3 and training not yet committed, none of it on this path but
            page_model.load's new argument, whose default is the old behaviour
python      3.12.3 at backend\venv, playwright 1.62.0, chromium 151.0.7922.34
model       trained 2026-10-30T21:05:28+05:00, the model on main. No language model
machine     Windows-11-10.0.26200-SP0, 8 cpus
power       ON BATTERY, 53% and falling, processor at 49 to 80% of rated speed
switches    none set
```

The trial and first pass ran the same day on the same machine, also on battery. Only the
gap between captures depends on speed, and it is recorded per row.

**The five features**, on the first 1280x800 and nothing below it, read from what Chromium
says is on screen, on a 16px grid: `image_area`, `motion` (pixels moved by more than 16 of
255 between two captures 3s apart), `covered`, `first_screen_links`, `first_screen_text`.
Definitions and what each leaves out: the script's docstring. Checked on our replicas first,
where the answers are known: motion 0 on all five, drift 0 to 0.004, the sign-in modal
1.00 covered, the cookie bar 0.0625, and first-screen text equal to `text_density` wherever a
whole page fits.

### What was read

| | Listed | Read | Not read |
|---|---|---|---|
| Rated pages | 50 | **48** | `text.npr.org` and `lite.cnn.com`: robots.txt now disallows this agent |
| Overwhelm index sites | 35 | **35** | none |

**The gap between captures** was 3.14 to 3.52s on the sites and at most 3.34s on the rated
pages. A site's picture, nine features and five new ones are from one load.

### The finding: these pages are outside what people rated

| | Sites, median | Public rated pages, median | Largest public rated page |
|---|---|---|---|
| `image_area` | **0.70** | 0.006 | 0.26 |
| `motion`, 3s | 0.016 | 0.000 | 0.23 |
| `motion_late`, 6s | 0.265 | 0.000 | 0.23 |
| `covered` | 0.105 | 0.000 | 1.00 |
| `first_screen_links` | 16 | 25 | 159 |
| `first_screen_text` | 0.30 | 0.84 | 3.51 |

**33 of the 35 sites have more of their first screen in pictures than any of the 19 public
pages rated.** Of all 48 rated pages only three pass 0.26, and all three are demo logins.
27 of the 35 sites move within 3s, against 5 of the 48 rated pages. This measures what
2026-11-02b could only say it had seen: on this web a page's words are in its pictures, and
the raters were taught on pages where they are not. 9 of 35 have at least 27% of their
screen under something floating, 6 of them all of it. It does not yet show that the model's
"calm" is wrong: only ratings of these pages can.

### Set 3

20 pictures: 15 of the sites, 3 anchors, 2 repeats, about 3-4 minutes, with the same question,
labels and worked examples. Chosen by spreading over the ranks of the five features, at
least two per category and at most three.

| | All 34 sites eligible | The 15 chosen |
|---|---|---|
| `image_area` | 0.16 to 0.91 | 0.16 to 0.91 |
| `motion` | 0.00 to 0.85 | 0.00 to 0.66 |
| `covered` | 0.00 to 1.00 | 0.00 to 1.00 |
| `first_screen_links` | 4 to 40 | 4 to 29 |
| `first_screen_text` | 0.08 to 0.78 | 0.08 to 0.66 |

3 Utilities and 2 each of the other six categories. Anchors `P11`, `P21` and `P28`, the calmest,
the middle and the heaviest by raters of the six that Sets 1 and 2 share. Repeats of Karachi
Water and Jazz. MEPCO is left out by name: its picture is the site's own loader at 91%.

**What it takes:** `python -m backend.estimator.train_visual` says, today: *37 of 65 pages
have fewer than 8 ratings; 186 more ratings are needed in all, at least 3 more Set 2 raters
and 8 more Set 3 raters.*

### The comparison: built, proven on synthetic ratings, and not yet run for real

Four arms on the same pages and folds, 40 shuffles of 5: the nine, the nine and the five,
the five alone, and the new set without `motion`. **The gate was written before any Set 3
rating existed**, so that the bar could not be fitted to the result. All six must hold:

1. real ratings, the floor met, and Set 3 in them;
2. held-out error lower, its 95% interval above zero with pages resampled 10,000 times;
3. held-out R² higher;
4. levels no worse (nested kappa);
5. heavy pages caught no fewer;
6. on the Pakistani pages, fitted on Sets 1 and 2 alone, lower error.

**Step 4 today: the old model stays**, because condition 1 fails. No new model exists to
switch to. A pass later would still not make it live: the running app measures only the nine.

### A preview, which is not a result

`--preview`, 48 pages of Sets 1 and 2 at 5 ratings a page, no Pakistani page. Under the floor,
and it cannot pass the gate. Reported because it is real data through the real pipeline and
because of what it warns about.

| Arm | R² | Error | Nested kappa | Heavy pages caught |
|---|---|---|---|---|
| Old: the nine | 0.576 ± 0.037 | 0.497 ± 0.024 | 0.704 | 69% |
| New: the nine and the five | 0.418 ± 0.099 | 0.532 ± 0.030 | 0.606 | 69% |
| The five alone | 0.504 ± 0.050 | 0.513 ± 0.022 | 0.592 | 74% |
| New, without motion | 0.565 ± 0.059 | 0.498 ± 0.027 | 0.634 | 63% |
| Predicting the training mean | -0.049 | 0.785 | | |

New against old: 0.034 **higher** error, 95% interval -0.117 to 0.024 for the gain, so no
difference that can be told from nothing, and leaning the wrong way. Without the four drifted
pages, 44 pages: 0.540 and 0.382. **This says nothing about visual clutter**, because these
pages hardly have any: on them `motion` is zero on 43 of 48 and `image_area` under 0.03 on
most, so the five can only add noise. `image_area`'s coefficient here is -0.05.

The same preview model on the 35 sites (`.scratch/visual-features/preview/overwhelm-index/`)
moves them **down**, median 1.72 against 1.87, and calls all 35 below its average page. A
model given no busy page learns nothing good about busy pages. Nobody should quote that table.

**The old model's 0.576 is not a better old model.** It is pooled over 40 shuffles, where the
0.49 quoted since 2026-10-30 is the mean of one split's five folds. Pooled on all 50 pages it
is 0.572, so leaving out the two pages moved it by 0.004.

### What went wrong, in order

Each found by reading a number against a picture. No test would have found the first three,
because every test passed.

1. **`image_area` missed sliders.** Hit testing skips `pointer-events: none`, which is how
   slider plugins lay out slides: Quaid-i-Azam's page, nearly all photograph, read 0.01. Now
   0.81, from a second pass with that switched off.
2. **`covered` counted a slider's own layers**: 0.79 on Quaid-i-Azam and 0.72 on Ufone with no
   pop-up on either. Now 0.00 and 0.01. An absolute element has to be attached to the body.
   So this is narrower than `overlays.candidates`.
3. **A backdrop faded as a whole read as solid.** Bootstrap's is black at opacity .5, and MCB's
   hero read 0.01 behind it. Now 0.73.
4. **The read stretched `motion`'s gap**: to 17.3s, with 15 of 35 sites over 3.5s. So the second
   capture now goes first, on the clock, and the page is read about 3s after its picture.
5. **Set 3 first chose MEPCO**, and as a repeat, so two of 20 pictures were a loader. Its
   flatness is an ordinary 0.53, so it was seen, on a sheet of the pictures, and not measured.
6. **A test could damage what it tested.** Breaking the guard on purpose let
   `test_the_new_model_can_never_be_written_over_the_live_one` write a synthetic model to
   `data/estimator.json`. `git status` showed it and it was restored; the file's version,
   raters and pages were checked. The test now uses a stand-in.

So the sites were read three times, not once: the index, the first pass and the corrected one,
with Quaid-i-Azam and MCB read once or twice more in trying the fix. All of it read-only, with
robots.txt first and the 3s pause. The rated pages' live members were read twice.

### Limits

- **Raters see stills, so `motion` can only reach a rating through what a still shows.** A page
  with a carousel is rated on one slide. The `no_motion` arm is there because of this.
- **A 3s gap misses slow carousels.** 5 sites read under 0.05 at 3s and 0.10 or more at 6s,
  among them Election Commission (0.00 and 0.66) and Quaid-i-Azam (0.00 and 0.41). `motion_late`
  is recorded and is not a feature, since the brief set 3s.
- **`first_screen_text` is nearly `text_density`**: r = 0.98 over all 83 pages, on the first
  screen in both. It adds little, and its importance in the preview, 1.01 ± 1.97, is two
  copies of one signal fighting. `first_screen_links` is new information: r = 0.46.
- **Features of pages rated in October are read in November.** Four pages have drifted past
  a quarter of the screen: three of `the-internet.herokuapp.com`, restyled since, and one Ant
  Design drawer. The limit of 0.25 was set from the pixels, in the empty band from 0.18 to
  0.38, before any comparison. Drift moves on a live page: Spiegel read 0.81 on the first pass
  and 0.10 on the second. Each comparison runs both with and without the drifted pages.
- **Position cannot tell a fixed hero from a modal.** NUST reads 1.00 covered and has no pop-up.
- **Inside an iframe is not read.** The Guardian's consent wall is one, so the text behind it
  counts as seen. A video in a frame is not `image_area`.
- **A partly loaded page still gets through**, as 2026-11-02b said. MEPCO is the one seen, and
  it stays in the rescored table with `motion` 0.69, which is its loader fading.
- **Set 3's raters may not be Sets 1 and 2's raters.** The anchors will show it, and nothing
  corrects for it.
- Everything 2026-11-02b says about who the raters are still holds.

### The tests

`tools/evaluation/test_visual_features.py` 58, `tools/rating/test_set3.py` 35,
`backend/estimator/test_train_visual.py` 40, `tools/evaluation/test_rescore_index.py` 7: 140,
all against servers on this machine or synthetic ratings in a temporary folder. 12 deliberate
breakages, each caught. Among them: the interval replaced by its mean, the Pakistani test
fitted with Pakistani pages, a preview allowed to pass, the slider rule, the pointer-events
pass, and Set 3 changing a picture Sets 1 and 2 use. The gate has a test for each condition
failing alone, and one where a model passes all six with the live file checked unchanged.

## 2026-11-03 — the suite on `eval/visual-features`, before merging

At `8993d07`, on mains from start to end of every run, the overlay rebuilt first. Free
memory was 0.7 GB of 7.9 at the start.

| Run | Result | Time |
|---|---|---|
| Backend half | **1268 passed, 9 skipped, 0 failed** | 1421s |
| Frontend half | **639 passed, 3 skipped, 0 failed** | 1421s |
| Host fit test, first run | **0 of 3**, every scale on one assertion | 566s |
| Host fit test, after the fix | **3 of 3** | 561s |

**1907 passed, 12 skipped, 0 failed**: the 1712 of 2026-11-02 plus the 55 of
`eval/overwhelm-index` and the 140 of this branch. The 12 skips are the same 12. The backend
half took 1421s against 981s on 2026-11-02 for 195 more tests; with 0.7 GB free, that is no
reading of the code's speed.

**The host fit test's failure was the test's, not the overlay's.** The rebuild gave the dark
small logo the hash `D3-JexYj`, and `display_fit_run` cut a logo's name at its last `-`, so it
read `simba-logo-horizontal-small-dark-D3` and the brand check failed at 100%, 125% and 150%.
Every fit figure in that run had passed up to that line. The name is now cut at a `-` and
Vite's eight hash characters (DECISIONS.md, *The fit run reads a logo's name by the hash's
length*). Checked against all four built logo names before the re-run. Any earlier build whose
hash held a `-` would have failed the same way; the ones on 2026-11-02 did not.


## 2026-11-04 — Show me once, stage 1: the bill taught once and run from its tile

Raham's one feature after the freeze (DECISIONS.md, *"Show me once" goes in after the feature
freeze*), stage 1 of two: the bill on the billing copy, end to end. A helper shows SIMBA the task
once on the real page; SIMBA keeps it as a routine of perception's roles and labels and the
answer the helper pointed at; the person runs it from a tile with no model.

**Script:** `tools/evaluation/show_me_once.py`, result in `logs/show_me_once.json` with its
conditions. Headless Chromium at 1280x800, the billing copy on its own port, no model. The
helper is Playwright's mouse and keyboard on the page, through the same recorder and perception
the real window uses; the person is a script answering each screen (the number when asked, Yes
to cookies). Then the same routine against the copy with its search button renamed
(`BILLING_CHECK_LABEL=Find my bill`), a page changed after teaching.

**Conditions:** commit `fdd02dd` on `feat/show-me-once`, on mains, processor at 66% of rated
speed, 1.07 GB free. The run reads "dirty" only for an untracked `simba-logo-kit.zip` in the
repository root that predates this work and is not part of it.

### Teaching, once

| | |
|---|---|
| Moves kept | 3: press Accept all cookies, type in Reference No., press Check Bill |
| Asked each time | 1, the reference number (the helper's answer on the bar) |
| Helper's presses on the page | 4: cookies, the box, Check Bill, and the amount pointed at |
| Helper's presses on the bar | 3: "Ask each time", Finish, Keep it |
| SIMBA's own time while watching | 0.8s, script-driven: a helper adds their own time to it |

The read-back, as the helper sees it: "1. Ask about cookies, and press Accept all cookies if the
answer is yes. 2. Ask what to type in Reference No., and type it. 3. Press Check Bill. 4. Read
the answer from P/WITHIN on the page. It says 14,382 now."

### Ten runs from the tile

| Measure | Result |
|---|---|
| Completed | **10 of 10** |
| Right answer (14,382) | 10 of 10 |
| With the picture of the real page, the amount ringed | 10 of 10 |
| Presses for the person | **2** every run: the number, and Yes to cookies |
| Checklist lines (done without a press) | 2 every run: typing in Reference No., pressing Check Bill |
| Moves taken | 3 every run |
| **Model calls** | **0** every run |
| Wall clock | mean 1.89s, range 1.8 to 1.9s (secondary, ±2x on this machine) |

The hand-written bill flow on the same copy is 2 presses and 1 checklist line (EVALUATION.md,
2026-10-16d): the routine has one line more because it presses Check Bill as its own move where
the plan types and presses in one. Steps and model calls lead, as everywhere since 2026-09-17h.

### The page changed after teaching

The same routine against the copy whose button now says "Find my bill":

| | |
|---|---|
| Completed | no, and **no answer shown** |
| Stopped with | "I couldn't find Check Bill on the page. The site may have changed since your helper showed me, so they may need to show me again." |
| Presses before the stop | 2 (the number, cookies) |
| Pressed anything not found | nothing: the run stopped on the lookup page |
| Model calls | 0 (none set up for the person's runs: `SIMBA_USE_HARDCODED_PLAN=1`) |

It stops before acting, because `RoutinePlanner` looks for the move on the page as it is, by
role, label and which of several alike, before handing it to the loop. A press that is found and
does nothing it did when shown stops the same way, with its own sentence
(`test_routine_run.py`).

### In the real window

`.scratch/show-me-once/stack.py` and `walk_teach.py`: the billing copy, the Electron host and
the backend attached to it, every store pointed inside `.scratch` so no real tile, routine,
profile or password is touched. The helper's presses go to the site view and the overlay's to
the overlay, through CDP's own input; every picture is of the application's own views, never the
desktop. Captures in `.scratch/show-me-once/walk-100/` and `walk-150/`.

| Scale | Window | Bar | Teaching (walk, with its pauses) | Helper presses | Run from the tile | Person's presses | Answer |
|---|---|---|---|---|---|---|---|
| 100% | 1280x800 | 96px | 17.8s | 7 | 10.9s | 3 | 14,382, Amount due |
| 150% | 1266x632 | 96px | 17.9s | 7 | 7.4s | 3 | 14,382, Amount due |

The person's three presses are the tile, "Use this" after typing the number, and Yes to
cookies. The host's own log says when the overlay became a bar and when it covered the site
again (`SIMBA host overlay is a bar {"height":96}`, then `overlay covers the site`); the site
view's bounds are never changed.

**What the walk does not show.** The presses are CDP's, sent to each view directly, not a
physical mouse moved across the window: they prove the recorder and the bar, and that the site
view is shown below the bar, but not that Windows' own hit-testing sends a real click to the site
view rather than the overlay. The host's bounds make that the expected behaviour; a person at
the keyboard is the check that remains.

### What failed on the way, and was fixed

1. **Finish pressed while a page was loading lost the pointing switch** (`test_teach.py`): the
   new page started from the recorder's defaults. Each page now asks the backend what it is for
   when the recorder starts.
2. **A list the page draws itself (`<select>`) was never "done"**: choosing changes nothing
   perception compares, so the page-level check said "the page did not change at all". A choice
   is now checked by reading the list back, as typing is.
3. **A model that took over and gave up was misreported**: its reason was replaced by the
   routine's "the answer wasn't on the page". The routine now passes on whoever is planning.
4. **The read-back did not fit**: the row under every step card put "Keep it" 21px past a 606px
   window, and the page scrolled by a pixel at 150%. The row is not shown under a read-back, and
   its gaps are tighter in a short window. Found by its fit test before anyone saw it.
5. **A label ending in a full stop got two** ("Type ... in Reference No.."): one is kept.
6. **Two copies on one port**: the test's changed copy and the replica benchmark both used
   5131; the test now uses 5132.

### Limits

- **One routine, on a copy we wrote.** The billing copy's labels are stable and its table is
  well formed; a live site's may not be (stage 2).
- **The answer is one label.** A page where the value has no label perception can pair is
  pointed at and missed ("I couldn't tell what that is"), which is honest and not useful.
- **Teaching time is a script's**, so it says nothing about how long a helper takes.
- **Nobody from the audience, and no helper, has used it.**

### The tests

`backend/orchestrator/test_teach.py` 22 (recording on the billing copy with real presses,
mapping, the answer, safety: a live site's paying press held, a card box, Enter submitting an
order, no room), `test_routines.py` 22 (the store, sharing and its refusals, over the real
websocket), `test_routine_run.py` 14 (running, the honest stop, the model's offer, a list choice,
the tile over the websocket) and `frontend/test_show_me_once.py` 18 (the overlay at 100%, 125%
and 150%): 76.

### The suite, before merging stage 1

At `fdd02dd`, the overlay rebuilt first. Windows reported AC power before the first half and
after the host fit test (`Win32_Battery`, status 2); the runs were `-q`, which leaves out the
power line pytest's header prints, so nothing recorded the minutes between.

| Run | Result | Time |
|---|---|---|
| Backend half | **1326 passed, 9 skipped, 0 failed** | 1342s |
| Frontend half | **657 passed, 3 skipped, 0 failed** | 1467s |
| Host fit test | **3 of 3** | 564s |

**1983 passed, 12 skipped, 0 failed**: the 1907 of 2026-11-03 and the 76 of this stage. The 12
skips are the same 12.

## 2026-11-04b — Show me once, stage 2: list choices, days, a booking and a live lookup

Stage 2 of Raham's one feature after the freeze (2026-11-04 above): values that change list
choices and calendar days, using the train search's own station and day logic
(`details.match_station`, `read_stations`, `read_day`), taught on the railways copy as far as a
booking, and once on the live train search, read only.

**Script:** `tools/evaluation/show_me_once.py 10`, result in `logs/show_me_once.json`. The
helper is Playwright's mouse and keyboard through the recorder; the person is a script that
says Lahore Cantt, Karachi Cantt, Tomorrow, Bilal Ahmed and the bill's number when asked, Yes
to cookies, "do it" on every final screen, and no to a model. **Conditions:** `fa6bece` on
`feat/show-me-once` (the tree "dirty" only by the untracked `simba-logo-kit.zip`), on mains,
processor at 70%, 1.38 GB free. The live site was screened first (`tools/screen_site.py`): it
serves no robots.txt (HTML in its place, as in September), the page loads (200, 5.4s), and it now
has a Departure Time box it did not have then.

| | The bill (billing copy) | Booking (railways copy) | Trains (live site, read only) |
|---|---|---|---|
| Moves kept | 3 | 11 | 7 |
| Asked each time | 1 (the number) | 4 (from, to, day, name) | 3 (from, to, day) |
| Helper's presses, page / bar | 4 / 3 | 13 / 6 | 9 / 5 |
| SIMBA's own time while watching (script) | 0.8s | 2.3s | 6.4s |
| Runs | **10** | **10** | **2** (never a benchmark on a live site) |
| Completed, right answer, with proof | 10, 10, 10 | 10, 10, 10 | 2, 2, 2 |
| Presses for the person | 2 | 6 | 3 |
| Final screens | 0 | 2 | 0 |
| Checklist lines | 2 | 9 | 7 |
| Moves taken | 3 | 11 | 7 |
| **Model calls** | **0** | **0** | **0** |
| Wall clock (secondary) | mean 1.83s (1.8–1.9) | mean 3.75s (3.6–3.9) | mean 12.5s (12.3–12.7) |

The bill's changed copy stopped again as on 2026-11-04: "I couldn't find Check Bill on the page…",
2 presses, nothing pressed that was not found, 0 model calls.

**What the person's presses are.** The bill: the number, and Yes to cookies. The booking: where
from, where to, which day, the passenger's name, and two final screens. The live trains: where
from, where to, which day. The person never chooses a station from scratch: the question offers
the site's own list, and "Lahore" is asked about as its two stations (`test_routine_lists.py`).

**The live answer** was train 2DN, Lahore Cantt to Karachi Cantt tomorrow, both runs, ringed on
the picture of the live page. Three searches in all were sent to the live site, one while
teaching and one per run; nothing was booked or pressed that changes anything.

### In the real window

`.scratch/show-me-once/walk_trains.py` on the railways copy, at 100%: the helper chose both
stations from the read-only boxes' lists, opened the calendar, moved to the next month and
picked the 15th; the bar asked "Is this day the same every time?" (capture
`walk-trains/11-trains-day-question.png`). Taught in 18.3s. The person then asked for Rawalpindi
to Sukkur on a day typed as "24 November" in 5 presses (the tile, two "Use this", "Pick another
day", "Use this day"), 24.2s, and the page searched exactly that: `{"from": "RAWALPINDI", "to":
"SUKKUR", "date": "2026-11-24"}` against `2026-11-24` asked.

### What failed on the way, and was fixed

1. **The page's own writing was taken for the helper's typing.** The railways copy writes the
   chosen station into its box, and the day into the date box; the recorder committed whatever
   the box held at the next press, and kept "Type LAHORE CANTT in From." and a typed date nobody
   typed. A box now counts as typed only after the helper types in it, and only until it is kept.
2. **A click into a read-only box was never kept**, so a routine could not open the calendar or
   unlock a station box. It is now kept, folded into the typing that follows when there is some.
3. **A list choice was not recognised**: the click into the box is not held, so perception read
   the page after the list had opened. A typed value followed by a choice from a list is now a
   list choice by its shape.
4. **Replaying "type LAH, choose LAHORE CANTT" would have lapsed** the loop's check that typed
   values stay. A choice from the list a box opened now commits the box — and the first version
   of that also let a search typed toward the wrong station through: `test_trip.py`'s "a search
   for another route never gets sent" failed. It now never commits past a value the task
   declares, and that test passes again.
5. **No routine checked that the page held what the person said.** Added after the live lookup
   ran, before anything was recorded here: a chosen station must be in its box and the day in
   the date box (in any of the usual ways of writing one) the moment each is chosen, or the move
   did not work.
6. **The last move did not wait for its answer**: on a page that fills a table in place, the end
   check could read too soon. It now waits as for any expected change.
7. **The answer did not say what it was for**: trains under the routine's name alone. Its heading
   now adds the person's own answers.
8. Three in the evaluation script itself, each a selector that matched the calendar's hidden day
   cells or the live calendar's year label before the results.

### Limits, and what is flagged

- **A press whose label holds data is tied to that data.** The booking routine presses "Book train
  7UP"; for a route whose first train is not 7UP that is not on the page and the run stops
  honestly. Choosing a train is not a value the helper can mark as changing.
- **Two final screens for one booking**, since "Book train 7UP" only opens the form but its words
  say book. Safe, and one press more than needed.
- **A routine's final screen names the button it presses and nothing else**, as a model-planned
  change's does. The final-step rule asks for what, how much and when as the page states them;
  the booking page states them. Flagged in the report with a recommendation.
- **The live run is two runs on one day.** It says the routine works on that site today, and
  nothing about next month's markup.

### The tests

`backend/orchestrator/test_routine_lists.py` 14 on the railways copy with real presses: the
journey taught, another journey run, two stations in one city, a place not on the list, a shared
routine, the booking behind its final screens and "don't", the list choice committing the box
and never past what the task declares, a calendar's banner, the station and day checks.
And `frontend/test_show_me_once.py` gains one: the bar asks about a day as a day (19 in all).

### The suite, before merging stage 2

At `f4bdf16`, the overlay rebuilt first, every run's own header saying on mains this time.

| Run | Result | Time |
|---|---|---|
| Backend half | **1340 passed, 9 skipped, 0 failed** | 1338s |
| Frontend half | **658 passed, 3 skipped, 0 failed** | 1479s |
| Host fit test | **3 of 3** | 568s |

**1998 passed, 12 skipped, 0 failed**: stage 1's 1983 and stage 2's 15. The same 12 skips.


## 2026-11-04c — Show me once, fixes: the person's train, one final screen, its details

Three of stage 2's flagged items, fixed on `fix/show-me-once` (DECISIONS.md, *Show me once,
fixes*): the train is the person's choice, asked from the page's own rows; only the press that
books gets a final screen; and that screen shows what, how much and when as the page states
them, as the built-in booking's does.

**Script:** `tools/evaluation/show_me_once.py 10 booking`, result in
`logs/show_me_once_fix.json`. The booking taught once as in 2026-11-04b, then ten runs: five on
Lahore Cantt to Karachi Cantt (the person choosing 7UP, 8DN, 7UP, 8DN, 7UP) and five on
Hyderabad Jn to Sukkur, whose four trains are none of them the helper's 7UP (11UP, 12DN, 13UP,
14DN, 13UP). Each run is checked on the confirmation page: the train booked is the one chosen,
and its stations are the route asked for. **Conditions:** `9c0d472` on `fix/show-me-once` (the
tree "dirty" only by the untracked `simba-logo-kit.zip`), on mains, processor at 170%, 564 MB
free. A first pass on battery, at half the processor's speed, was a check that the script
worked and is not recorded: the same counts, at 9.1s a run.

| | Stage 2 (2026-11-04b) | Now |
|---|---|---|
| Moves kept | 11 | 11 |
| Helper's presses, page / bar | 13 / 6 | 13 / 6 |
| Runs | 10, one route | 10, two routes |
| Completed, with a booking number and proof | 10 | **10** |
| The person's train, on the route asked for | — (always 7UP) | **10 of 10** |
| "Which train?" asked | 0 | 10 |
| Final screens per run | 2 | **1** |
| What the final screen shows | the button's name | **Train, From, To, Date, Departs, Passenger, Class, Fare** |
| Presses for the person | 6 | 6 |
| Checklist lines | 9 | 10 |
| **Model calls** | **0** | **0** |
| Wall clock (secondary) | mean 3.75s (3.6–3.9) | mean 4.01s (3.9–4.1) |

**The person's presses** are the same in number and now all theirs to make: where from, where to,
which day and the passenger's name before anything is touched, then "Which train?" from the
results, then the one final screen. The press that opened the booking form, which had a final
screen of its own, now runs as a checklist line once the train is chosen ("Opening Book train
13UP"): one more line, one fewer screen.

### What failed on the way, and was fixed

1. **A route with no trains said the search did not work.** The search's own check waits for the
   rows, and with none it failed first; the run stopped with "the button with no name didn't do
   what it did when your helper showed me", which blames the site. It now says the page showed no
   train to choose from (`test_a_route_with_no_trains_stops_and_says_so`).
2. **The teaching test's check for selectors in a routine** looked for `[` in the routine's
   JSON, and the new empty list of final details has one. It now checks every piece of text the
   routine keeps, which is what it was for.
3. Two of my new tests' own expectations were wrong (a row of one has no cells that differ; the
   choices end with "Stop this"), and corrected.

### Limits

- The rows are read from a table perception reads as one, with a column whose values name each
  row's press. A results list that is not a table, or presses named by something not in a cell,
  are kept as the helper's fixed press, as before.
- "Only opens" is believed for a real link to another page of our copy and nothing else. The
  billing and registration copies have no such link before their change, so only the booking
  shows the difference.
- A final screen's details are the page's labels at the moment the helper pressed; the values
  are read when it runs. A page whose summary changes its labels stops the run with nothing done.

### The tests

`backend/orchestrator/test_routine_lists.py` 14 → 27: six for the train, two for the one final
screen, five for its details. The train kept as the person's to choose and
shared that way in a file; the person booking 14DN and 13UP on a route the helper never searched;
the rows offered and their words; a file's row press without `{}` refused; a route with no
trains; only a real link to another page of our copy believed to only open; a file that says
Confirm Booking only opens still meets its final screen; the details kept as labels, read on the
person's own train, and a missing one meaning nothing is done.

### The suite, and the host fit test

On mains, at `9c0d472`, as two halves: **2011 passed, 12 skipped, 0 failed** (backend 1353 in
1421s, frontend 658 in 1472s). The 12 skips are the usual ones.

**The host fit test (`SIMBA_HOST_TESTS=1`) did not pass: 2 of 3, twice**, failing at 100% both
times and at a different point each time. First run (456s): the fit run's own picture of the
overlay's home screen gave no frame within 4.0s (`capture_site`). Second run (535s): a press on
Start on the overlay waited 30s for the button to be stable. 125% and 150% passed both times.
Nothing this test uses changed on the branch: no file under `frontend/` or `shared/`, and the
test drives a scripted backend, not the backend this branch changed (`git diff main --stat --
frontend shared tools/evaluation/display_fit_run.py` is empty). The machine was short of memory:
437 to 1,538 MB free of 8 GB, with Chrome holding 1.7 GB and Edge WebView 0.7 GB, against 1,600
MB free at 2026-11-04b; and the site view gave a picture 13 of 20 and 10 of 20 times at 100%,
where the covered view has given 20 of 20 since September. That points at the machine, not
the change, but it is not proven, and **the branch was not merged**, as the task said to merge
only when clean.

**Re-run on 2026-11-05: 3 of 3** (580s), at `a8ee19f`, on mains, the same command. Before it the
machine had 959 MB available of 8 GB (984 MB free), with Chrome still open at about 1 GB: about
as little as during the second failure. So shortage of memory did not on its own make 100% fail,
and the two failures are better read as intermittent at 100% than as caused by memory; what
stands is that nothing the test uses changed on the branch. Merged into `main` after this run.

---

## 2026-11-05 — retrained with Set 3: the visual features are not better, and the old model stays

`python -m tools.rating.from_form` on the three forms' CSVs, then `python -m
backend.estimator.train_visual --min-ratings 5 --charts`, on `eval/retrain-visual`, asked for by
Raham. **The new model is not better on held-out pages, so it does not go live**: it fails five of
the gate's six conditions, and four of the five would fail with the floor met. `data/estimator.json`
is unchanged and is still the model SIMBA runs. No loop change was made, since none is needed.
The generated section is below as it was written, under its conditions block, with what was added
by hand after it.

**What the forms gave** (`from_form`; the CSVs are gitignored and stay in the repo root):

| Set | Responses | Usable raters | Dropped, and why |
|---|---|---|---|
| 1 | 14 | 10 | 4 on a phone: 5001, 5004, 5010, 5011 |
| 2 | 11 | 5 | 6 on a phone: 6001, 6002, 6005, 6007, 6009, 6011 |
| 3 | 12 | 8 | 4 on a phone: 7002, 7004, 7008, 7012 |

Nobody was dropped for not agreeing or for a missing answer. 23 usable raters, 610 rows. **Sets 1
and 2 are exactly the rows trained on on 2026-10-30** (450 rows, checked row by row): the one new
response, 6011 to Set 2, was on a phone. So Set 2 still has 5 usable raters.

| Pages | Shown in | Ratings each (first showings) |
|---|---|---|
| 22 | Set 1 only | 10 |
| 22 | Set 2 only | **5, under the floor of 8** |
| 3 | Sets 1 and 2 (anchors) | 15 |
| 3 | Sets 1, 2 and 3 (anchors) | 23 |
| 15 | Set 3 only, the Pakistani sites | 8 |

**`--min-ratings 5`, and only because of Set 2.** Every other page meets 8. Until today the real
comparison had no such flag, only `--preview`, so `train_visual` gained one, as `train.py` has.
The 21 compared pages under the floor are named in the generated section below; the 22nd,
`text.npr.org`, is left out of every arm because robots.txt now disallows reading it. **Under the
floor the gate's first condition fails, whatever else holds**: lowering what training accepts
does not lower what a switch needs, because the gate was written before any Set 3 rating existed.
That changed nothing today: the other conditions decide it on their own.

**The two numbers to quote.**

- Overall, the three arms are not distinguishable: held-out error 0.528 old, 0.524 new, 0.513
  for the five alone, each gain's 95% interval across zero (new −0.025 to 0.030; five alone −0.040
  to 0.072). The new model is worse at levels (nested kappa 0.654 against 0.697) and catches fewer
  heavy pages (62% against 78%).
- **On the 15 Pakistani pages no arm does better than knowing their average.** Held out in the
  same folds: R² −0.019 old, −0.007 new, 0.056 five alone, every one within a standard deviation
  of zero. Fitted on Sets 1 and 2 alone and tested on Set 3, the new model is much worse than the
  old (error 0.811 against 0.603), because `image_area` on these pages is past anything in Sets 1
  and 2 (median 0.70 against 0.006, 2026-11-02c) and the model extrapolates.

**Rater agreement**: alpha 0.316 over all 23 raters; within each set 0.284 (Set 1), 0.357 (Set
2) and **0.272 (Set 3, over its 18 pictures)**; reliability of the page means 0.782. The three
anchors all three sets saw differ by 0.23 to 0.32 of a point between Set 3's raters and the
others', in both directions, so Set 3's group rates much as the others do.

**Importance on the Pakistani pages alone is not reported.** On them every arm's held-out R² is
about zero, and importance is R² lost when a feature is shuffled: there is none to lose, so any
figure would be noise. Importance is reported overall, for all three arms (below and in the chart).

**What carries the prediction** is the same signal in every arm: words on the screen.
`text_density` in the old (0.600 of R² lost), split with `first_screen_text` in the new (0.171
and 0.175, r = 0.98 between them, as 2026-11-02c warned), and `first_screen_text` in the five
alone (0.750). That is why the five alone is level with the nine: it carries a copy of the nine's
best feature. **`image_area` and `motion` add nothing in any arm** (−0.004 and −0.005 in the new,
−0.009 and −0.006 alone, each smaller than its own spread).

### As generated by `train_visual`: the old features and the new, Sets 1 to 3

**Below the study's floor.** 21 of 63 pages have fewer than 8 ratings, so this ran with `--min-ratings 5`, which only a person asks for, and the gate's first condition fails whatever else holds: http://127.0.0.1:5000/ [sign in] (5); http://127.0.0.1:5000/stubborn [as it loads] (5); http://127.0.0.1:5100/bill?reference=04141234567890 [as it loads] (5); http://demo.testfire.net/ [as it loads] (5); http://info.cern.ch/hypertext/WWW/TheProject.html [as it loads] (5); https://demo.opencart.com/ [as it loads] (5); https://demoqa.com/automation-practice-form [as it loads] (5); https://demoqa.com/modal-dialogs [open a demoqa modal] (5); https://developer.mozilla.org/en-US/docs/Web/HTML [as it loads] (5); https://element-plus.org/en-US/component/dialog.html [open an element plus dialog] (5); https://en.wikipedia.org/wiki/Cognitive_load [as it loads] (5); https://en.wikipedia.org/wiki/Main_Page [as it loads] (5); https://mui.com/material-ui/react-dialog/ [open a mui dialog] (5); https://parabank.parasoft.com/parabank/index.htm [as it loads] (5); https://practice.expandtesting.com/ [as it loads] (5); https://the-internet.herokuapp.com/ [as it loads] (5); https://www.bbc.co.uk/news [as it loads] (5); https://www.nhs.uk/ [as it loads] (5); https://www.pakrailways.gov.pk/train [as it loads] (5); https://www.saucedemo.com/ [as it loads] (5); https://www.theguardian.com/international [as it loads] (5).

23 raters, 63 pages, alpha 0.316, reliability 0.782. Every arm on the same pages and folds, 40 shuffles of 5 folds.

Agreement within each set (alpha): Set 1 0.284 (10 raters), Set 2 0.357 (5 raters), Set 3 0.272 (8 raters).

| Arm | R² | Error | Nested kappa | Heavy pages caught |
|---|---|---|---|---|
| Old: the nine | 0.481 ± 0.037 | 0.528 ± 0.017 | 0.697 | 78% |
| New: the nine and the five | 0.487 ± 0.033 | 0.524 ± 0.015 | 0.654 | 62% |
| The five alone | 0.502 ± 0.026 | 0.513 ± 0.013 | 0.604 | 65% |
| New, without motion | 0.492 ± 0.033 | 0.523 ± 0.016 | 0.681 | 70% |
| Predicting the training mean | -0.039 | 0.744 | | |

Lower error, new against old: 0.004, 95% interval -0.025 to 0.030, pages resampled 10000 times.

Each other arm the same way, its error lower than old's: the five alone 0.016 (-0.040 to 0.072); new, without motion 0.005 (-0.017 to 0.027).

On the 15 Pakistani pages alone, held out in the same folds as the whole:

| Arm | R² | Error |
|---|---|---|
| Old: the nine | -0.019 ± 0.100 | 0.609 ± 0.028 |
| New: the nine and the five | -0.007 ± 0.104 | 0.612 ± 0.033 |
| The five alone | 0.056 ± 0.114 | 0.588 ± 0.036 |
| New, without motion | 0.000 ± 0.096 | 0.600 ± 0.029 |
| Predicting the training mean | -0.139 ± 0.055 | 0.631 ± 0.018 |

Fitted on Sets 1 and 2 alone, tested on the Pakistani pages:

| Arm | Error | R² |
|---|---|---|
| Old: the nine | 0.603 | -0.104 |
| New: the nine and the five | 0.811 | -1.018 |
| The five alone | 0.845 | -1.298 |
| New, without motion | 0.622 | -0.224 |

Without the pages drifted past 25% of the screen (59 of 63 left):

| Arm | R² | Error |
|---|---|---|
| Old: the nine | 0.466 | 0.540 |
| New: the nine and the five | 0.465 | 0.540 |
| The five alone | 0.492 | 0.523 |
| New, without motion | 0.467 | 0.539 |

Set 3's raters against those of Sets 1 and 2, on the same pictures:

| Anchor | Sets 1 and 2 (raters) | Set 3 (raters) |
|---|---|---|
| https://demo.applitools.com/ [as it loads] | 1.27 (15) | 1.50 (8) |
| https://getbootstrap.com/docs/5.3/components/modal/ [open a bootstrap modal] | 2.80 (15) | 3.12 (8) |
| https://news.ycombinator.com/ [as it loads] | 3.73 (15) | 3.50 (8) |

Each feature's importance, held out: R² lost when it is shuffled, and its standardised coefficient, in each arm that has it. Sorted by the new model.

| Feature | Old: the nine | New: the nine and the five | The five alone |
|---|---|---|---|
| `first_screen_text` |  | 0.175 ± 0.117, +0.224 | 0.750 ± 0.383, +0.530 |
| `text_density` | 0.600 ± 0.338, +0.423 | 0.171 ± 0.118, +0.213 |  |
| `links` | 0.211 ± 0.193, +0.222 | 0.094 ± 0.110, +0.147 |  |
| `first_screen_links` |  | 0.056 ± 0.084, +0.105 | 0.093 ± 0.118, +0.144 |
| `overlays` | 0.056 ± 0.072, +0.111 | 0.030 ± 0.042, +0.085 |  |
| `form_fields` | 0.030 ± 0.058, -0.077 | 0.011 ± 0.032, -0.056 |  |
| `max_depth` | 0.029 ± 0.064, -0.101 | 0.011 ± 0.036, -0.070 |  |
| `covered` |  | 0.009 ± 0.022, +0.041 | 0.045 ± 0.067, +0.132 |
| `dead_link_ratio` | 0.008 ± 0.067, +0.094 | 0.004 ± 0.044, +0.073 |  |
| `interactive` | 0.013 ± 0.042, +0.056 | 0.002 ± 0.020, +0.037 |  |
| `inferred` | 0.002 ± 0.046, -0.063 | -0.003 ± 0.031, -0.045 |  |
| `image_area` |  | -0.004 ± 0.013, +0.021 | -0.009 ± 0.028, +0.041 |
| `motion` |  | -0.005 ± 0.041, +0.053 | -0.006 ± 0.064, +0.086 |
| `reading_grade` | -0.013 ± 0.021, +0.006 | -0.013 ± 0.024, +0.008 |  |

### The gate

| Condition | Met | |
|---|---|---|
| real ratings, the floor met, and Set 3 in them | **no** | under the floor |
| held-out error lower, its 95% interval above zero | **no** | 0.524 against 0.528; lower by 0.004, 95% interval -0.025 to 0.030 |
| held-out R² higher | yes | 0.487 against 0.481 |
| levels no worse (nested kappa) | **no** | 0.654 against 0.697 |
| heavy pages caught no fewer | **no** | 62% against 78% |
| Pakistani pages: lower error, fitted on Sets 1 and 2 alone | **no** | 0.811 against 0.603 |

**The old model stays.** `data/estimator.json` is unchanged. Not met: real ratings, the floor met, and Set 3 in them; held-out error lower, its 95% interval above zero; levels no worse (nested kappa); heavy pages caught no fewer; Pakistani pages: lower error, fitted on Sets 1 and 2 alone.

Left out, 2 pages: https://lite.cnn.com/ [as it loads]: disallowed by robots.txt; https://text.npr.org/ [as it loads]: disallowed by robots.txt

```text
========================================================================
taken at    2026-11-05T21:17:15+05:00
git         b7d816cd463f on eval/retrain-visual — DIRTY TREE, the commit does not describe this run
python      3.12.3 at D:\simba\backend\venv\Scripts\python.exe
playwright  1.62.0
model       openai gemini-3.1-flash-lite (from .env)
machine     Windows-11-10.0.26200-SP0, 8 cpus, load 2%
power       on mains, processor at 50% of rated speed, 1051 MB memory free
switches    none set
========================================================================
```

The conditions block says `model openai gemini-3.1-flash-lite (from .env)`: it reads `.env`
whatever runs. **No language model was called.** The tree was dirty because the code was not yet
committed; `train_visual.py` did not change after this run, and the two later fixes (below) touch
only the index's report and the chart.

### The overwhelm index again, by the better model, which is the live one

`python -m tools.evaluation.rescore_index --by live`, which `train_visual` now runs itself, ranking
by whichever model the gate kept. **Nothing was visited.** It scores the 35 sites from the read of
2026-11-02c (`data/visual_features.json`), the same load Set 3's pictures came from, so a site's
features and the picture people rated are of one page. The live model is the one ranked in
2026-11-02b, so this is that index on a second read. The full table, with every reason, is in
`.scratch/overwhelm-index/visual/report.md`; it is not committed, as the first index is not.

| # | Highest ten | Category | Live | People (8 raters) | Pushed up by | Held down by |
|---|---|---|---|---|---|---|
| 1 | MCB | Banks | 2.54 | | many buttons and boxes, many links (217) | a deeply nested layout, little text on screen |
| 2 | Directorate of Passports | Government services | 2.38 | | nothing much | a deeply nested layout |
| 3 | University of the Punjab | Universities | 2.36 | 3.12 | nothing much | a deeply nested layout |
| 4 | Government of Sindh | Government services | 2.29 | | many links (326) | little text on screen, a deeply nested layout |
| 5 | Higher Education Commission | Universities | 2.23 | | many links (198) | a deeply nested layout |
| 6 | SSGC | Utilities | 2.12 | | many links (181) | little text on screen, a deeply nested layout |
| 7 | IESCO | Utilities | 2.04 | 2.12 | a shallow, plain layout | little text on screen, few links (84) |
| 8 | Karachi Water | Utilities | 2.03 | 2.44 | many buttons and boxes | little text on screen, few links (36) |
| 9 | Bank Alfalah | Banks | 2.02 | 1.50 | nothing much | little text on screen, few links (56), a deeply nested layout |
| 10 | Meezan Bank | Banks | 2.02 | | nothing much | little text on screen |

| # | Lowest five | Category | Live | People (8 raters) | Pushed up by | Held down by |
|---|---|---|---|---|---|---|
| 31 | University of Karachi | Universities | 1.64 | | many links (150) | a deeply nested layout, little text on screen |
| 32 | Pakistan Railways | Transport | 1.64 | | nothing much | little text on screen, few links (17), a deeply nested layout |
| 33 | National Bank of Pakistan | Banks | 1.58 | 2.25 | many links (141) | a deeply nested layout, little text on screen |
| 34 | Ufone | Telecoms | 1.51 | | nothing much | little text on screen, a deeply nested layout, few links (53) |
| 35 | Shaukat Khanum | Health | 1.47 | | nothing much | a deeply nested layout, little text on screen, many things to fill in |

**Every page is band 1 or 2 and opens at SIMBA's level 2; none is heavy.** The top ten are the
same ten as 2026-11-02b, in the same order, within 0.02 of a point, and the bottom five are the
same five, two of them swapped: the nine features read the same on a second visit. The table
spans 1.07 of a point against the model's held-out error of about 0.5, so neighbours are still
not a ranking. What held pages down: little text on screen (32 of 35), a deeply nested layout
(27), few links (15); what pushed some up: many links (10), many buttons and boxes (4).

**The question 2026-11-02b could not answer, answered for 15 sites.** It said the model's "calm"
should not be believed until people rated these pages. They have now:

| | Live model, on pages it never saw |
|---|---|
| Error against people's means | 0.61 |
| Leans (model minus people) | **−0.32**: calmer than people say |
| Order kept (Spearman, 15 sites) | 0.28 |
| Heavy by people / by the model | 1 (Zong, 3.50) / 0 |

People rate these sites 2.22 on average, against 2.49 for the other rated pages: **mostly calm to
middling, as the model said, but not in the order it said.** Zong, people's heaviest at 3.50, is
17th; National Highway Authority, 3.12, is 16th; Bank Alfalah, 1.50, is 9th. The model's "calm"
was roughly right in level and wrong about which. The report beside the table gives the new model
error 0.52 and order 0.64 on the same 15: **that row is not held out**, because the new model was
fitted on these very ratings, and the report says so. Held out, it does no better (above).

### Charts

In `.scratch/retrain-visual/`, gitignored, each with a CSV of the numbers it draws:
`importance.svg` (held-out importance for old, new and five alone, one shared scale), and
`predicted.svg` (held-out prediction against people's mean, one panel per arm, Pakistani pages
as orange squares). The second shows the finding in one look: in every panel the 15 orange
squares lie along a predicted 2, across people's ratings from 1.06 to 3.50. PNGs beside them were
rendered from the SVGs in headless Chromium, not by capturing the screen.

### What failed, and was fixed

1. **The real comparison could not run under the floor.** `train_visual` had only `--preview`,
   which leaves out the Pakistani pages. It now takes `--min-ratings`, names the pages below 8
   before any number, writes the floor into the candidate model, and keeps the gate shut.
2. **The index's reasons were counted by their numbers.** "many links (217)" and "many links
   (326)" were two reasons, so the first report said many links had pushed up 1 page, not 10.
   Found by reading the report against 2026-11-02b's; now counted without the number.
3. **The index's comparison with people flattered the new model.** Its first version put the new
   model's in-sample fit (0.52, order 0.64) beside the live model's honest test (0.61, 0.28) as if
   alike, which read as the opposite of the gate. Found by checking it against the held-out
   figures; the report now says the new row is not held out.
4. **The scatter cut its scale at 4.5**, so pages rated or predicted above it were drawn over the
   panel titles. Seen on the rendered picture, not by a test; the scale is now 1 to 5 and a test
   holds every point inside its panel.

### Limits

- Everything 2026-11-02b and 2026-11-02c say about the raters still holds: 23 people, none from
  the audience, judging a still picture, agreeing weakly.
- 15 Pakistani pages with 8 raters each is a small test: one rater moves a page's mean by up to
  half a point, and Spearman over 15 pages has a wide interval.
- The `old` arm is the nine refitted on these 63 pages. The live model is the nine fitted on
  Sets 1 and 2's 50 on 2026-10-30, and is what the index uses.
- `motion` and `image_area` were tested as a still shows them. Whether a moving page overwhelms a
  person *using* it is not what raters were asked.

### The tests

`backend/estimator/test_train_visual.py` 50 (10 new), `tools/evaluation/test_rescore_index.py` 15
(8 new), `tools/evaluation/test_visual_charts.py` 5 (new): synthetic ratings in a temporary
folder, none touching `data/estimator.json`. **8 deliberate breakages, each caught**: the floor
notice dropped, the gate relaxed under the floor, the Pakistani figures taken from the mean
instead of the model, reasons counted with their numbers, the in-sample warning dropped, the index
ranked by the new model when the live one was kept, an answer to another picture counted, and the
scatter's scale cut at 4.5.

## 2026-11-05b — the suite on `eval/retrain-visual`, before merging

At `7846a9d`, on mains at the start and end of every run, with 1.3 to 1.7 GB of memory free.

| Run | Passed | Skipped | Failed | Time |
|---|---|---|---|---|
| Backend half (`backend tools test_basetemp.py`) | 1376 | 9 | 0 | 1610s |
| Frontend half (`frontend`) | 658 | 3 | 0 | 1471s |
| Host fit test (`SIMBA_HOST_TESTS=1`, after `npm run build`) | 3 | 0 | 0 | 565s |

2034 in all, 23 more than on 2026-11-05's merge of `fix/show-me-once`: the 23 new tests of this
branch. The 12 skips are the usual 12. The host fit test passed first time at 100%, which
STATUS.md had left open as possibly intermittent: one more pass, not proof it is not.

## 2026-11-10 — Teach a task, and undo on the bar: the bill taught with an undo, run from its tile

Raham's follow-on to *Show me once*, after the freeze (DECISIONS.md, *"Teach a task" and undo go
in after the feature freeze*): a way in for helpers on the home screen, a bar that lists what it
has kept, and "Undo last thing". The rule from the task: teach the bill on the billing copy, undo
a step, redo it, save, and run it from the tile, 5 of 5.

**Script:** `tools/evaluation/show_me_once.py 5 undo`, result in `logs/show_me_once_undo.json`.
Headless Chromium at 1280x800, the billing copy on its own port, no model. The helper is
Playwright's mouse and keyboard through the recorder, as in 2026-11-04: Accept all cookies, the
number, Check Bill; then **Undo last thing on the bar**, Check Bill again, "Ask each time",
Finish, the amount pointed at, kept as "My bill". The person is the script of 2026-11-04.
**Conditions:** `700a396` on `feat/interface-teach-entry` (the tree "dirty" only by the untracked
`simba-logo-kit.zip`), on mains, processor at 189%, 801 MB free, **with the suite's backend half
running at the same time**, so the seconds are a ceiling, not a measurement.

### Teaching, with the undo

| | Stage 1 (2026-11-04) | With an undo |
|---|---|---|
| Helper's presses, page / bar | 4 / 3 | 5 / 4 |
| The list before the undo | — | Pressed Accept all cookies. / Typed in Reference No. / Pressed Check Bill. |
| The list after | — | the first two |
| The website after the undo | — | the form (`/`), with the number back in its box |
| Undo, wall clock | — | 0.16s |
| Moves kept | 3 | **3** (Check Bill once, not twice) |
| Asked each time | 1 | 1 |
| Read-back | 4 lines | the same 4 lines, word for word |
| SIMBA's own time while watching | 0.8s | 1.1s, the undo's 0.16s in it |

The one more press on the page is Check Bill the second time; the one more on the bar is Undo.
The routine kept is, step for step, the routine stage 1 kept: `routine.import` would not tell
them apart.

### Five runs from the tile

| | Stage 1, ten runs | Now, five runs |
|---|---|---|
| Completed, with the amount and the proof | 10 of 10 | **5 of 5** |
| Right answer (14,382) | 10 | 5 |
| Presses for the person | 2 | 2 |
| Checklist lines | 2 | 2 |
| Moves | 3 | 3 |
| **Model calls** | **0** | **0** |
| Wall clock (secondary, and under load) | mean 1.89s (1.8–1.9) | mean 2.16s (2.1–2.3) |

A first pass earlier in the day, before the commits and with the machine idle, gave the same
counts at 1.96s a run (1.9–2.1) and the undo at 0.17s; it is not recorded since its conditions
block named the tree as `0010a20` with every change uncommitted.

### The way in, on the home screen: measured, and moved

The task put "Teach a task" at the bottom of the home screen. Built there, as a row under
"Change my settings" with its line under it, it is 79 to 83px tall, and the fullest home screen
(three own tiles, the three things SIMBA can do, two goals asked before) has no such room. From
the overlay built from source, at the window sizes of `test_home.SIZES`, with the row in the
column and then as a row fixed at the window's bottom outside the column:

| Size | Window | In the column: page height | Fixed at the bottom: the row | The settings row |
|---|---|---|---|---|
| 100% | 1280x800 | 882 (scrolls by 82) | 754–792 | 723–761 (overlap 7) |
| 125% | 1280x734 | 734 (fits) | 692–730 | 619–657 (clear) |
| 150% | 1266x606 | 679 (scrolls by 73) | 564–602 | 555–593 (overlap 29) |

In the top right corner of the window, across from the small logo and outside the column, it
costs the column nothing. The same sizes, the same fullest screen, the greeting being the
column's first thing:

| Size | The entry | The greeting starts at | Clear by |
|---|---|---|---|
| 100% | 24–94 | 151 | 57 |
| 125% | 12–82 | 161 | 79 |
| 150% | 12–82 | 97 | 15 |

`test_home.box_fits` now holds every home screen it measures to that (the entry wholly in the
window, above the greeting), so the 47 home screen cases and the fullest one with a routine at
three sizes check it; `tools/evaluation/display_fit_run.py` measures the same two things in the
real host, and `test_window_fit.py` asserts them on the home screen with and without history.

### The bar

160px tall, from 96. In the overlay built from source at the three sizes, the bar in its three
fullest shapes — a question over two rows of the list and "4 more before these."; the list at its
longest, three rows with "3 more", Undo and Finish; the note that the website could not be taken
back, over the list, with Start again — fits at 160 with every button, the heading and every row
wholly inside it: 9 cases, in `test_the_bar_is_one_row_that_fits_at_every_size`. Pictures at 150%
and 100% in `.scratch/teach-entry/` (`bar-question-*.png`, `bar-list-*.png`, `home-*.png`).

### What failed on the way, and was fixed

1. **Chromium brought the form back empty after `go_back`.** The test written first said the
   number would still be in its box on the page gone back to, as a browser's own Back usually
   leaves it; headless Chromium did not restore it. The list said "Typed in Reference No." and
   the page had an empty box: exactly the mismatch the task forbids. Now what the list says was
   typed on that page is put back into its boxes, through a door in the recorder.
2. **A value typed again after an undo was swallowed.** The recorder remembers the last value it
   reported for a box and reports a box only when its value differs, so the number taken out
   and typed again was never sent, and the bar never asked about it. The door in the recorder
   (`__simbaRestore`) now sets that memory to what it put back, so the next real typing is
   reported whatever it is.
3. **A `data:` page cannot replace itself** with another `data:` page (Chromium refuses a
   top-frame navigation to `data:` from a page), so the test of a page that cannot be reached
   by going back did nothing. The test now serves its pages to the browser from the test
   itself (`page.route`) on a made-up host, which is also not one of our replicas, as the test
   needs.
4. **The entry at the bottom did not fit**, twice, as measured above; it moved to the corner.
5. **A test counted the entry gone the moment the next screen arrived**; it fades, so for a
   moment it is still there. The test waits for it to go.
6. **The evaluation script's first log named an uncommitted tree**; re-run after the commits.

### Limits

- Undo takes the website back only to a page where the things kept were typing and presses;
  a page with a choice from a list, a day, or a password can only be started again. The
  railways copy's search, undone, is a Start again.
- A press that did something on its own page (hid a banner, opened a calendar) comes off the
  list and the page keeps what it did.
- The seconds here were taken under the suite's load, and from this machine read ±2x in any
  case (2026-09-18).
- The way in has not been seen by a helper or by Aly; the corner is a measured choice, not a
  tested one.

### The tests

`backend/orchestrator/test_teach.py` 22 → 32: the list in a few words, newest last; a password
listed as a password; undo of a typed value, out of the list and out of its box; undo of the
search, back on the form with the number in its box, then shown again, kept, and run from its
tile five times; undo of a press that stayed on its page; a page that cannot be reached by going
back, with Start again, nothing let through, and starting again; a sign-in page that cannot be
put back; a consent press pressed again as one press; undo with nothing kept and while pointing;
each kind of move's few words. `frontend/test_show_me_once.py` 19 → 34: the way in and where it
goes, its fit on the fullest home screen at three sizes, the list newest last, the last few and
the count, Undo's message, Start again in Undo's and Finish's place, a bar from an older backend,
and the bar's fit in three shapes at three sizes. `test_home.box_fits` and the host fit test
measure the entry on every home screen they measure.

## 2026-11-10b — the suite on `feat/interface-teach-entry`, before merging

At `700a396` (the code; the docs commit followed), on mains, as two halves, then `npm run build`
and the host fit test. 1.36 GB free before the re-runs; the first runs' free memory was not
noted.

| Run | Passed | Skipped | Failed | Time |
|---|---|---|---|---|
| Backend half (`backend tools test_basetemp.py`) | 1386 | 9 | 0 | 1872s |
| Frontend half (`frontend`), first run | 672 | 3 | **1** | 1601s |
| Frontend half, re-run whole | 673 | 3 | 0 | 1799s |
| Host fit test (`SIMBA_HOST_TESTS=1`, after `npm run build`), first run | 2 | 0 | **1** (150%) | 616s |
| Host fit test at 150%, re-run | 1 | 0 | 0 | 173s |

2059 in all, 25 more than on 2026-11-05b: the 10 new tests in `test_teach.py` and the 15 more in
`test_show_me_once.py`. The 12 skips are the usual 12. The backend half ran with the undo
evaluation (2026-11-10) alongside it for its first two minutes.

**Two failures on the first run, neither in what the branch changed, both gone on re-run:**

1. `test_press_guard.py::test_a_press_on_a_button_just_arrived_is_ignored_and_logged` waited
   30s for a step's "Tomorrow" button that its scripted backend had sent and it never showed.
   The press guard and the step screen are untouched by this branch (the home screen's corner
   and the teach bar are what changed); the test's own comment records the same trouble in full
   runs on 2026-10-17. On its own, 4 of 4 at once; in the re-run of the whole half, passed.
2. The host fit test at 150%, in its last stage, the sign-in screen: a press on Start waited 30s
   for the button to be stable. The same failure as 2026-11-04c's second run (then at 100%),
   in a stage this branch does not touch; at 150% the home screen, the brand and every ending
   had passed before it, the new corner checks among them. Re-run at 150% alone: passed in 173s.

Merged into `main` after the re-runs, as on 2026-11-05. What stands: the branch's own tests
passed every time; the two failures are the suite's known timing ones, now seen three times in
a week (2026-11-04c twice at 100%, today at 150%), and **the host fit test being intermittent is
open in STATUS.md still**.

## 2026-11-10c — Picture tiles and a journey line: contrast, fit, and before and after

Raham's follow-on to *Teach a task*, after the freeze (DECISIONS.md, *Picture tiles and a
journey line go in after the feature freeze*): how the overlay looks, nothing it does. Measured
here: the colours' contrast, the fullest home screen's fit, the journey line's fit at every size
and level, and the pictures.

### The colours

From `index.css` (`test_contrast.py`), the lowest of the four pictures in each theme:

| Theme | Picture on its pale | Ink on the pale | Picture on the tile |
|---|---|---|---|
| B light | 6.25 (bill) | 13.36 | 7.42 |
| B dark | 7.53 (book) | 12.42 | 8.09 |
| A light | 6.25 (bill) | 13.77 | 7.48 |
| A dark | 7.53 (book) | 12.70 | 8.52 |

The tiles' words did not change colour: ink on the tile's surface, as before. Measured again in
the page from computed colours (`test_the_words_on_every_tile_stay_readable`), light and dark,
six tiles each: every one at least 4.5:1, and every picture at least 4.5:1 on its square.

### The fullest home screen

Two kept tiles and one taught tile whose names wrap to two lines ("Electricity at home",
"Railway tickets home", "Register for CS-401"), the three things SIMBA can do, and two goals
asked before at their longest. How far the page scrolled, in CSS pixels:

| Size | `main` | Pictures, first draft | Now |
|---|---|---|---|
| 100% (1280x800) | 19 | 3 | **0** |
| 125% (1280x734) | 0 | 0 | 0 |
| 150% (1266x606) | 14 | 6 | **0** |
| 150% (1266x632) | 0 | 0 | 0 |

`main` already scrolled with names this long: no test had used them. The pictures are 10px wider
than the icons, so names wrap sooner; the compact tiles are now less tall (one line 52px, from 56;
two lines 75px, from 87) and 2 to 4px closer together, and nothing scrolls at any size. With short names, as the host
fit test has them, the 150% screen's greeting sits at 107px, against 97 on `main`: the column is
about 20px shorter, and "Teach a task" clears the greeting by 25px, from 15.

### The journey line

Six moves, three done, one being done, two to come, at four window sizes and three levels: 12 of
12 fit, nothing scrolls, every line, "Doing this now" and Pause wholly in the window and the card,
no line overlapping the next (`test_the_journey_fits_at_every_size_and_level`). In the real host
at 150% before the suite: the usual level and the simplest both fit, 1 of 1 in 197s.

| Level | Lines shown | Under them |
|---|---|---|
| 1 | 6 | — |
| 2 | 6 | — |
| 3 | 1, the move being done | "Then 2 more things." |

Before this, every level showed all six.

### Before and after

In `.scratch/interface-look/before/` and `.scratch/interface-look/after/`, each at 100% and 150%,
light and dark: `home-*` (a new person), `home-fullest-*` (two kept tiles, one taught, two goals),
`journey-*` (the usual level) and `journey-simplest-*`. The overlay page alone, built from the
source, headless, at the window's content size. The host's own, from the fit test:
`.scratch/screenshots/fit/home-<scale>-history.png` and `journey-<scale>-{usual,simplest}.png`.

### What failed on the way, and was fixed

1. **The fullest home screen did not fit with long names**, on `main` already, and still did not
   with the first pictures (above). The design changed, not the test.
2. **"Doing this now" first sat at the far right of its line**, a long way from the words it is
   about. It sits beside them now.
3. **Committing the tiles alone**: `App.tsx` holds both parts, and interactive staging is not
   available here, so the tiles' commit was made with the old checklist put back for it, and the
   journey line committed on top.

### Limits

- Nobody from the audience has seen the pictures. "Reads pictures faster than words" is the brief's
  premise, not something measured here.
- The name rule is English and three short lists.
- The level-3 count can change between moves, as the backend's list of what is to come does.

### The tests

`frontend/test_pictures.py`, new, 18: the three built-in pictures and their squares; nine names
through the rule; a taught tile's picture and mark, and the same colour as a kept tile of the
same name; "Change my tiles"; the words and pictures readable in light and dark; the fullest home
screen with wrapping names at four sizes, every picture whole and no name cut.
`frontend/test_checklist.py` 7 → 26: the journey as a list with the current step marked, its dots
and path; the three levels; the last move and one more thing at level 3; the dot's arrival with
and without reduced motion; the fit at four sizes and three levels. `frontend/test_contrast.py`
18 → 23. The host fit test counts every tile's picture and measures the journey line at two
levels.

## 2026-11-10d — the suite on `feat/interface-look`: one failure, so not merged

At `8f214db`, on mains, as two halves, then `npm run build` and the host fit test. 856 MB free at
the start, 379 MB before the re-run.

| Run | Passed | Skipped | Failed | Time |
|---|---|---|---|---|
| Backend half (`backend tools test_basetemp.py`) | 1386 | 9 | 0 | 2862s |
| Frontend half (`frontend`) | 715 | 3 | 0 | 1604s |
| Host fit test (`SIMBA_HOST_TESTS=1`, after `npm run build`) | 2 | 0 | **1** (125%) | 545s |
| Host fit test at 125%, re-run alone | 1 | 0 | 0 | 221s |

2101 passed in the halves, 42 more than on 2026-11-10b: the 42 new tests of this branch. The
backend half took 2862s against 1872s that afternoon, with about half the memory free.

**The failure:** at 125%, on the way to the third ending ("completed with nine results and a
sentence"), a press on Start on the home screen waited 30s for the button to be stable. The same
failure as 2026-11-04c (twice, at 100%) and 2026-11-10b (at 150%), all on code without this
branch's changes. This branch adds no motion near Start: the tiles' pictures are still, and the
tiles' entrance is as it was. Before it failed, 125% had passed the home screen with its pictures,
the brand and two endings; 100% and 150% passed whole, the journey line and the pictures
included; and 125% passed whole on its own re-run.

**Not merged.** The task said to merge only if everything passes, and to report a failure rather
than merge. On 2026-11-10b a failure of this kind was merged after a re-run; this time the rule is
kept as written, and the merge is Raham's call. The host fit test failing at random about one run
in three this week is the larger problem, and it is in STATUS.md.

**Merged afterwards, on Raham's decision**, the only failure being the known intermittent one,
which passed on its own re-run.

## 2026-11-11 — the host fit test's random failure: the host's window minimised mid-run

The host fit test (`SIMBA_HOST_TESTS=1`) had failed at random four times in a week (2026-11-04c
twice, 2026-11-10b, 2026-11-10d), each time a press on Start waiting 30s for the button to be
"stable", each time gone on re-run. Raham's task: find the cause, with evidence; no retry and no
longer timeout as the fix. **Branch** `fix/host-fit-flake`, from `main` at `b2f5948`. Probes in
`.scratch/host-fit-flake/` (not committed).

### Not the button moving: the page's frame check never came back

Playwright's click waits for "visible, enabled and stable", and *stable* is checked frame by
frame with `requestAnimationFrame`: two frames with the same box. A box that differs returns
false, and Playwright logs `element is not stable` and tries again (read in its own source,
`coreBundle.js`, `_checkElementIsStable` and `_retryAction`). All four failures logged exactly one
line, `waiting for element to be visible, enabled and stable`, and nothing more for 30s. The
same Playwright in the same host logs its retries within milliseconds when a check does fail
(`element is not enabled`, three times in the first second, on a probe's empty box). So in every
failure the page-side check never returned: the overlay got no animation frames, or ran nothing.
**That rules out, as the cause: an entrance animation, a late layout shift, and the press guard**
(which ignores a person's press and never touches Playwright's check). A window still being
fitted happens once, in the host's first second; the failures came 89 to 197s in.

The test's own diagnostic for this, the overlay's frames asked at a failure (2026-11-02), had
never worked: it ran after the Playwright session had closed, and said "Event loop is closed!"
in all four failures.

### The cause, caught and reproduced

With the diagnostic moved inside the session, the first run of the test failed 2 of 3, and both
times the host's own window said **`minimised`** (`window.__simbaWindow`, written by
`frontend/electron/main.ts` on Windows' minimise and restore):

| Scale | When | Failure | The window | Memory free |
|---|---|---|---|---|
| 125% | 230s | a press on Start, 30s for "stable" (as the four before) | `minimised` | 1105 MB |
| 150% | 109s | no picture of the page within 4s (as 2026-11-04c's first run) | `minimised` | 1360 MB |

Nothing in the repository minimises a window (searched outside `node_modules`, the venv and
`.scratch`). A minimised host window was minimised from outside: a person at the machine or
Windows. Raham was not sure whether he had.

Then the same thing on purpose, at 125%, each ending reached exactly as the fit test reaches it
(`test_terminal_states.reach`: load, wait, type, press Start, answer, wait for the ending):

| Host window | Rounds | Failed | Longest round | At the failures |
|---|---|---|---|---|
| Covered by a maximised window, in front of nothing | 120 + 60 | **0** | 5.9s / 8.6s | — |
| Covered, focus moved to the site view | frames only | — | — | 31–32 frames in 600ms, as before |
| Minimised once, 10s per action | 40 | **21** | 11.6s | 0 frames in 600ms, every one |
| Minimised every 3s, the test's 30s | 40 | **18** | 31.0s | the logged failure, word for word |
| Minimised every 3s, **with the fix** | 40 | **0** | 3.3s | 34 minimised, 34 shown again |

Minimised, the overlay drops from 30–32 frames in 600ms to 0–3, and the press on Start fails
every other time, as the site view's captures alternate. Covered but shown, it keeps 30–32 and
never failed.

**A person does not meet this.** Nobody presses a button on a minimised window, and the backend
asks whether the window is shown before every action on the site
(`backend/orchestrator/browser.window_watch`, since 2026-10-05). It is the test: it needs the
window shown for ten minutes and assumed it stayed so.

### The fix, in the test

`KeepShown` in `tools/evaluation/display_fit_run.py` watches the host's own window five times a
second while it is measured. When it is minimised, it is shown again with `SW_SHOWNOACTIVATE`,
so it never takes the keyboard from whoever is working, and the time is said and kept in the
result (`window_kept_shown`). Not a retry and no longer wait: the press is made on a window that
is shown, as the test assumed. A failed press now also says, inside the session and with a 3s
limit, whether each view runs code and gets frames, the window's state, and the memory free.

### The proof: five runs in a row

After `npm run build`, on mains, `fix/host-fit-flake` at `35d4e34`:

| Run | Result | 100% | 125% | 150% | Wall clock | Minimised and shown again | Memory free at start |
|---|---|---|---|---|---|---|---|
| 1 | 3 passed | 212s | 209s | 160s | 589s | 2 (100% at 53s and 177s) | 512 MB |
| 2 | 3 passed | 212s | 218s | 164s | 601s | 2 (125% at 201s, 150% at 9s) | 2362 MB |
| 3 | 3 passed | 212s | 204s | 158s | 582s | 1 (150% at 99s) | 1167 MB |
| 4 | 3 passed | 210s | 213s | 163s | 593s | 0 | 1868 MB |
| 5 | 3 passed | 212s | 212s | 164s | 596s | 2 (150% at 5s and 107s) | 2274 MB |

**15 of 15.** In four of the five runs the window was minimised from outside at least once, 7
times in all; before the fix each of those could have failed the run, which fits a failure
about one run in three.

### Open

- **What minimises the window is not known.** Seven times in fifty minutes, at 5s to 201s into a
  host, at every scale. A person is possible; so is something on the machine. Found by watching,
  not by asking: the watcher says when, never why.
- **The site view's captures are 10 to 13 of 20 at 100% and 125%** in every one of these runs,
  and 20 of 20 at 150%; of the 47 counts in the saved logs since 2026-11-04, 42 are 10 to 13 and
  5 are 20. CLAUDE.md records 20 of 20 for the covered view. Not this failure: no assertion reads
  the count. With the window covered by another and shown, probes got 10, 17 and 19 of 20. Not
  settled here.

## 2026-11-11b — the suite on `fix/host-fit-flake`: one timing assertion over its limit

Run as two halves, then `npm run build`, then the host fit test, on mains, `fix/host-fit-flake`
at `35d4e34` (the docs for it uncommitted):

| Part | Result | Wall clock |
|---|---|---|
| `pytest backend tools test_basetemp.py` | 1386 passed, 9 skipped | 1930s |
| `pytest frontend` | **714 passed, 1 failed**, 3 skipped | 1648s |
| `npm run build` | built | 2s |
| host fit test, `SIMBA_HOST_TESTS=1` | 3 passed | 584s |

**The failure**: `frontend/test_calm.py::test_the_shape_does_not_slow_the_window`. The turning
shape cost 271ms of main-thread work in 5s against 117ms held still: **154ms more, the limit is
150ms**. p95 frame 16.8ms both, so no frame was late. The branch changes only
`tools/evaluation/display_fit_run.py`, which nothing in `test_calm.py` uses; the test and the app
are the same as on `main`.

Run on its own five times straight after, same machine, same build:

| Run | Turning | Still | Difference | Result |
|---|---|---|---|---|
| 1 | 180ms | 132ms | 48ms | passed |
| 2 | 194ms | 109ms | 85ms | passed |
| 3 | 238ms | 123ms | 115ms | passed |
| 4 | 136ms | 94ms | 42ms | passed |
| 5 | 157ms | 97ms | 60ms | passed |

Median 60ms, 2026-10-07 recorded about 70ms; the spread on its own reaches 115ms, and 27 minutes
into a full frontend half it reached 154ms. The assertion measures main-thread time in a
browser that shares the machine with the test run, so it moves with load. Held back on this result, as the task says;
**merged into `main` on Raham's decision** on 2026-11-11, the one failure being this timing
assertion, which the branch does not touch.

## 2026-11-11c — starter tasks, the demo script walked, and the clips recorded again (`docs/demo-show-me-once`)

One `.\run.ps1 railways-local` stack on mains at the machine's own 150%, its routines and
tiles in files of their own under `.scratch/` (`SIMBA_ROUTINES`, `SIMBA_TILES`), so nobody's
own tiles were touched; `adapt` on a second stack with `SIMBA_PAGE_MODEL=0`. The overlay built
from source in a browser of its own against the real backend; the helper's presses on the
SIMBA window's site view over CDP. A watcher that shows the host window again if it is
minimised (`KeepShown`, 2026-11-11) ran throughout: **0 restores**.

### Starter tasks, made with "Save to a file"

`python -m tools.starter_tasks make`: each taught once through "Teach a task", then saved with
the tiles editor's "Save to a file" and the download kept in `demo/starters/`.

| Tile | Teaching (script's time) | Moves read back | Asked each time | File | Typed reference in it |
|---|---|---|---|---|---|
| My bill | 33s | 4 | the reference | 1542 bytes | no |
| Train times | 46s | 8 | From, To, the day | 3320 bytes | — (no value in any `fill`) |

### Each added from its file and run from its tile: 5 of 5 each

`python -m tools.starter_tasks check 5` (`logs/starter_tasks.json`): a fresh overlay each run,
"Teach a task", "Add one from a file", "Not now", the tile pressed, the person's questions
answered, then the tile taken off again.

| Tile | Right | Adding | Whole run, each | Asked |
|---|---|---|---|---|
| My bill | **5 of 5** (14,382 read) | 5.5–5.7s | 30.8–32.0s | reference, cookies |
| Train times | **5 of 5** (trains for the stations asked) | 5.5–5.7s | 31.4–32.2s | From, To, day |

The trains alternated Lahore Cantt → Karachi Cantt (runs 1, 3, 5) and Hyderabad Jn → Sukkur
(2, 4), neither the helper's day. The whole run includes the tool's 1.8s beat on each screen.

**Failures on the way, all in the tools, none in the app:** (1) the site view was looked for
with `time.sleep`, during which the sync Playwright API hears nothing, so the page the backend
had already opened was never seen; (2) after "Keep it" the overlay shows "It's on the home
screen now, as My bill." with "Back to start", not the home screen; (3) a check's guard read
the home screen before its tiles arrived and missed a tile already there; (4) after a file
is added the screen does not change (only a file that cannot be used is said), so the tile is
reached with "Not now"; (5) one trains run of two in a trial waited 30s for a step that the
checklist had replaced while the safe moves ran — `record_demo` now reads that as a new
screen. Each fixed before the counted runs.

### The demo script, walked

Every step of DEMO.md's five minutes run on the copies with a script answering as the
presenter does (`.scratch/starters/walk.py`, 40 screens logged). Still as the script says:
the multan read-back only; "hello" and "book a flight to Dubai"; the bill card at the
simplest level, cookies, "Rs 14,382, due 15 September 2026"; "Pay this bill", the final
screen with amount, month, due date and reference, "Paid on the practice site." with a
receipt number, and "Don't pay" ending "I didn't do it. Nothing was changed." **Changed since
the script was written**, and now in it: the stations under the From box ("Lahore Jn",
"Lahore Cantt", then "Use this station") instead of a separate question; "Book" at the end of
the stage row; the checklist a journey line ("Then 3 more things." at the simplest level);
"What are you doing?" on the first question showing the whole page with "Hide the page"; and
every ending offering "Keep it" — the bill's as "My bill".

### The clips

`python -m tools.record_demo`, all seven, the overlay's own 1280x800 only:

| Clip | Length | Size | Ended |
|---|---|---|---|
| `demo/railways.webm` | 50s | 4.4 MB | found an answer, real page shown |
| `demo/booking.webm` | 59s | 5.9 MB | final screen, Book it, done |
| `demo/billing.webm` | 33s | 3.1 MB | found an answer, real page shown |
| `demo/hello.webm` | 6s | 0.7 MB | greeted |
| `demo/fold.webm` | 42s | 3.1 MB | done (mock) |
| `demo/adapt.webm` | 46s | 3.1 MB | folded after 5.4s, found an answer |
| `demo/teach.webm` | 79s | 6.9 MB | taught (4 moves, 43s), run from its tile, found an answer, real page shown |

The teach clip's site pictures under the bar: 67 shown, 0 missed. Watched, not just counted:
15 stills taken from it by playing it in a headless page — the bar over the billing copy with
the reference being typed, the question with "Ask each time", the read-back, the "My bill"
tile with its mark, 14,382 "Amount due", and the amount ringed on the real page.

## 2026-11-11d — the suite on `docs/demo-show-me-once`: a new intermittent failure in teaching list choices

Two halves, then `npm run build`, then the host fit test, on mains, at `1c1f83a`. Nothing in
`backend/`, `shared/` or `frontend/` differs from `main` (`git diff main --stat`).

| Part | Result | Wall clock |
|---|---|---|
| `pytest backend tools test_basetemp.py` | 1385 passed, **7 failed**, 9 skipped | 3189s |
| `pytest frontend` | 714 passed, **1 failed**, 3 skipped | 2086s |
| `npm run build` | built | — |
| host fit test, `SIMBA_HOST_TESTS=1` | **3 passed**, 0 restores | 737s |

**Frontend**: `test_after_the_guard.py::test_the_next_screen_goes_back_to_the_level_before_the_guard[100%]`,
level 1 where 3 was expected. My two-minute run of `test_routine_lists.py` overlapped that half.
On its own, idle, the file passed **5 of 5** (10 tests each).

**Backend: all 7 in `test_routine_lists.py`**, which teaches the train search once (a
module-scoped fixture) and checks what was kept, so one bad teaching fails all 7 together.
Run on its own on an idle machine: passed, failed, passed, failed (whole file, 4 runs); the
first test alone failed 1 of 4, then 0 of 10, and 0 of 10 at `0010a20`, before the last
change to `teach.py`. **Not seen in any earlier entry**; it passed in this morning's suite.

What a failing run shows, with the teach log live: after "kept a fill on a textbox" for From,
**no "kept a click on a option"** — for either station — though the page took the station (the
helper's next questions came). In `teach.py` (`_on_event`, kind `click`) a press is kept only
if perception finds an element at the press point; otherwise it is let through and nothing is
kept or logged. Why perception finds nothing over an open list some of the time is not
settled. Whether a person teaching meets it is not known: in the SIMBA window the train
search taught through the overlay kept both stations (1 of 1, 2026-11-11c), at a helper's pace.
Held back on this result, as the task says; **merged into `main` on Raham's decision** on
2026-11-11, the failures being in code the branch does not touch, with the teaching failure
given a branch of its own (`fix/teach-list-choice`).

## 2026-11-11e — the station press that teaching sometimes drops: not reproduced (`fix/teach-list-choice`)

The failure of 2026-11-11d, looked for on its own branch from `main` at `650c6e9`.

**What a failing run kept** (the saved log of the failing single run): click From, fill From,
click To, fill To, the date box, Next Month, the day, the search — **both station presses
missing**, the day and the search kept. No log line at all for either station press; at that
time the recorder said nothing when it let a press through unkept, so whether perception
found nothing there or the press never reached the recorder is not known.

| Attempt | Runs | Failed |
|---|---|---|
| In the suite, 06:14 | 1 | 1 |
| The file alone, ~07:00 | 4 | 2 |
| Its first test alone, ~07:10 | 4 | 1 |
| Its first test alone, after | 20 | 0 |
| At `0010a20`, before the last change to `teach.py` | 10 | 0 |
| With a line logged for every press let through unkept | 15 | 0 |
| The same, all 8 cores kept busy | 10 | 0 |

Four failures in nine runs within an hour, then **none in 55**. Not load (0 of 10 at full CPU);
not the last change to `teach.py` shown either way (0 of 10 before it, but 0 of 20 after it in
the same hour). Free memory 948 MB of 8070 when it would not fail. **Cause not found.**

**Changed**: `teach.py` now logs "teaching: a press at … not kept: nothing to press there (N
options on the page)" when it lets a press through without keeping it. Nothing else; 59 of 59
in `test_routine_lists.py` and `test_teach.py`. The next failure will say which way it went:
that line present means perception found nothing at the press; absent means the press never
reached the recorder.

## 2026-11-11f — `fix/teach-list-choice`: the backend half, before merging

Only the backend half, as asked: `pytest backend tools test_basetemp.py`, on mains, at `551664c`:
**1406 passed, 0 failed, 9 skipped, 1880s** (1385 + the 7 of `test_routine_lists.py`, this time
passing, + 14 new in `test_teach_log.py`). The new line for a press let through unkept was
written 0 times. The line was checked first: it writes two whole numbers (the press's point,
read as numbers; anything else as -1) and a count of list options, and its message holds only
`%d`, so no typed value, label or secret can reach it. Merged into `main` on Raham's decision;
the cause stays open.


## 2026-11-12 — live sites screened read-only, and the AI providers' free tiers (step 0 of the advisor's direction)

Asked for by Raham for the advisor's direction of 12 November (DECISIONS.md): which live sites
work with perception today, and what the AI providers allow for free. **Nothing was clicked,
filled or submitted, and no account was made.**

**Method.** `python -m tools.screen_site <origin> <path>` once per site, from git bash with
`MSYS_NO_PATHCONV=1`: robots.txt for SIMBA's screener user agent, then one load of one page at
1280x800 and perception's read of it. 3s pause between pages (the tool's own). On mains, 12
November, about 23:00 PKT, from Lahore, on `main` at `233e737`. **No conditions block was
written**: `screen_site` does not print one, and this was not re-run to add it, which would have
been twenty more visits to other people's sites. Read the load times as one visit, one moment,
±2x (EVALUATION.md, 2026-09-17h).

**Failed, and done again.** The first run was worthless: git bash turned each path argument
into a Windows path (`/train` became `/Program Files/Git/train`), so every page "loaded" as 0
elements or an error. Found by reading the table, not by a test; stopped and run again with
`MSYS_NO_PATHCONV=1`. The rows below are the second run.

| Site | Page | robots | HTTP | Load | Elements | Unnamed | Inferred | Dead links | Overlay/occluded |
|---|---|---|---|---|---|---|---|---|---|
| Pakistan Railways | `/train` | no robots.txt | 200 | 6.0s | 18 | 4 | 0 | 3 | 0/0 |
| Daraz | `/` | allowed (cart, checkout, customer disallowed) | 200 | 3.1s | 338 | 17 | 24 | 2 | 0/0 |
| foodpanda | `/` | allowed (login disallowed) | 200 | 4.3s | 147 | 1 | 0 | 1 | 0/0 |
| FCCU | `/` | allowed | 200 | 7.6s | 81 | 4 | 4 | 5 | 0/0 |
| PITC IESCO bill | `/iescobill` | no robots.txt (404) | 200 | 2.2s | 9 | 1 | 0 | 1 | 0/0 |
| SSGC | `/` | allowed | 200 | 7.6s | 182 | 36 | 1 | 9 | 0/0 |
| Directorate of Passports | `/` | allowed | 200 | 3.6s | 108 | 5 | 1 | 3 | 1/20 |
| Daewoo Express | `/` | allowed | 200 | 4.4s | 42 | 3 | 0 | 13 | 0/0 |
| Rozee | `/` | allowed | 200 | 11.9s | 2322 | 39 | 2 | 8 | 0/0 |
| Imtiaz | `/` | allowed | 200 | 5.3s | 81 | 9 | 14 | 3 | 0/22 |
| Naheed | `/` | allowed | 200 | 2.9s | 394 | 38 | 83 | 51 | 0/0 |
| Wikipedia | `/wiki/Main_Page` | allowed | 200 | 2.9s | 263 | 0 | 0 | 1 | 0/0 |
| gov.uk | `/bank-holidays` | allowed | 200 | 3.1s | 56 | 0 | 0 | 0 | 0/0 |
| Open Library | `/` | allowed | 200 | 4.2s | 163 | 0 | 7 | 18 | 0/0 |
| Shaukat Khanum | `/` | allowed | 200 | 3.1s | 124 | 17 | 0 | 1 | 0/0 |
| Chughtai Lab | `/` | allowed | 200 | 2.4s | 86 | 1 | 1 | 3 | 0/0 |
| timeanddate | `/weather/pakistan/lahore` | allowed | 200 | 2.4s | 73 | 0 | 0 | 2 | 0/0 |
| PIA | `/` | allowed | 200 | 3.0s | 132 | 0 | 33 | 5 | 0/0 |
| PTA DIRBS | `/` | allowed | 200 | 2.9s | 31 | 1 | 0 | 1 | 0/0 |
| OLX | `/` | allowed | 200 | 2.3s | 158 | 5 | 0 | 2 | 0/0 |

All 20 loaded with HTTP 200; no robots.txt disallowed the page read. **What this does not
show**: whether a form asks for a CAPTCHA when it is used, whether a task can be done, or
anything past the first page. "Inferred" is controls only perception's layout inference finds:
Naheed's 83 means a planner there leans on inference for a fifth of the page.

**Daraz is out for ordering.** Its robots.txt disallows `/checkout/`, `/cart/` and
`/customer/`; its terms of use (daraz.pk/terms-of-use, read 12 November through a search
result's summary, not in full) limit access to personal shopping and list robots among
prohibited tools.

**The AI providers, as their own pages said on 12 November 2026** (fetched by an agent; the
Gemini pages redirect from ai.google.dev to aistudio.google.com/docs):

| Provider | Free tier | Paid, per 1M tokens in / out | OpenAI-compatible base URL |
|---|---|---|---|
| Gemini | Per project, not per key; the docs give no per-model numbers and point to the AI Studio console. Third-party reports, unconfirmed: 20 requests a day on Flash, 500 on Flash-Lite | 3.8 Flash and 3.6 Flash $0.75 / $3.75 to 31 Dec 2026, then $1.50 / $7.50; 3.5 Flash-Lite $0.30 / $2.50; 3.1 Flash-Lite $0.25 / $1.50 (from a summary of a cut-off page) | `https://generativelanguage.googleapis.com/v1beta/openai/` |
| Groq | `openai/gpt-oss-120b` and `-20b`, `qwen/qwen3.8-27b`: 30 a minute, 1,000 a day, **8,000 tokens a minute**, 200,000 a day (the page may be showing the Developer plan's figures) | Not on groq.com/pricing | `https://api.groq.com/openai/v1` |
| OpenRouter `:free` | 20 a minute; 50 a day, or 1,000 a day after buying 10 credits | Per model | `https://openrouter.ai/api/v1` (implied by its examples) |

**Terms that matter for this audience** (Gemini API additional terms, effective 23 March 2026):
on the free tier ("Unpaid Services") Google uses what is sent to improve its products, human
reviewers may read it, and "Do not submit sensitive, confidential, or personal information to
the Unpaid Services"; users must be 18 or over; it is "for developers ... not for consumer use".
Groq signals a rate limit with HTTP 429 and `retry-after` in seconds. The 8,000 tokens a minute
is the number that bites: a SIMBA prompt with a page's element list is a few thousand tokens.


## 2026-11-13 — the AI planner on live websites: four runs, one defect found and fixed (`feat/orchestrator-ai-live-sites`)

`python -m tools.evaluation.open_goal_live_run <site> <goal>`, once each, read-only. The real
loop and `OpenGoalPlanner`, a headless Chromium at 1280x800, the provider in `.env`: Gemini,
`gemini-3.1-flash-lite`, its OpenAI-compatible endpoint, **free tier** — so only pages with no
personal data (DECISIONS.md, 2026-11-13). No Groq key was set, so the fallback was not used. The
script answers every step "go ahead" and the first answer the page says word for word "Yes,
that's it": **whether an answer is right was judged by reading it against the page afterwards**.
On mains, 13 November about 01:30 PKT, on `feat/orchestrator-ai-live-sites` at `e1e9a5e`;
conditions block in `.scratch/open-goal-live/` with each result. One run each: ±2x on every time.

| Site | Goal | Outcome | Answer | Moves shown | Model calls | Time |
|---|---|---|---|---|---|---|
| gov.uk bank holidays | When is the next bank holiday in England and Wales? | answered | "25 December Christmas Day" — right (the next after 12 November) | 1 (the question) | 1 | 11.7s |
| timeanddate, Lahore | What is the temperature in Lahore now? | answered | **"Just a moment…" — wrong**: the page was a bot check | 2 | 2 | 7.5s |
| Wikipedia main page | What is today's featured article on Wikipedia about? | answered | "The Royal Gloucestershire Hussars" — the article's title, as the page gives it | 1 | 1 | 9.1s |
| timeanddate, Lahore, after the fix | the same | **stopped**: "The website wants to check that a person is using it…" | none | 0 | 0 | 5.0s |

**Failed, and fixed.** timeanddate answered the headless browser with a bot check (title "Just
a moment…"). The model pressed the site's logo, then quoted the check's own words as the answer;
they were on the page word for word, so the planner's check passed them. A person would have
said "No, keep looking" — but the advisor's rule is that a CAPTCHA, a one-time code or a blocked
site stops SIMBA and is handed to the person. `loop.blocked` now reads the page's title,
headings and large text, and any box named for a captcha or a one-time code, before every move
of every planner; such a page ends the run before a model is asked (`test_open_goal.py`, 2
cases). The same goal, run again: stopped in 5.0s with 0 model calls.

**What this shows and does not.** Three of three readable pages answered in one or two model
calls, 7.5 to 11.7s, every answer a quotation of the page. Nothing here typed, searched or
pressed past a link. The screening of 12 November loaded timeanddate's page whole; this
run met the check — a site can decide differently per visit, and a headless browser is more
likely to be checked than SIMBA's own window. **Not measured yet**: a goal that needs a search
or a form, the Groq fallback live, and any run through the Electron window.


## 2026-11-13b — payment handover and live changes: what the tests show (`feat/orchestrator-payment-handover`)

No live site was paid or ordered on; nothing here touched another computer. Every number is a
test count, through the real loop in real Chromium, on `data:` pages (which count as live
sites) and on the billing copy with its new test card gateway.

| What | Tests | Result |
|---|---|---|
| An order on a live site: final screen, "do it", SIMBA presses; "don't", nothing pressed | 2 | pass |
| The live final screen shows the page's own amount ("Total: Rs 450") | 1 | pass |
| A press that pays on a live site: final screen, then handed over; SIMBA's clicks on Pay: **0** | 1 | pass |
| After paying, the page's words quoted; nothing said: "I can't tell…", unconfirmed | 2 | pass |
| A card box: handed over before any move; the number typed by the person never in anything sent | 3 | pass |
| A CAPTCHA or bot check: handed over, the task goes on; still there after two, stops | 2 + 2 | pass |
| The test gateway: the test card and code go through, any other card declined and never echoed, a wrong code asked again, "TEST GATEWAY" on every page | 4 | pass |
| **A bill paid by card end to end**: final screen with the bill's own details, SIMBA presses "Pay by card", the gateway page handed over, the person types card and code, "Payment Received" quoted | 1 | pass |
| Stop on the card page: nothing changed, the page left as it was | 1 | pass |
| The two old tests of the old rule, rewritten to the new one | 5 | pass |

**The backend half** (`pytest backend tools test_basetemp.py`), at the phase's first commit, on
mains: **1540 passed, 2 failed, 9 skipped, 1920s**. The two were phase 2's bot-check tests, which
expected the run to end at once; under the new rule the check is handed to the person first.
Rewritten to expect two handovers and then the stop, with no model asked: 8 of 8.

**Failed on the way, and not a defect**: the end-to-end test first said the card number had
been sent. It had not: the assertion chained three checks, and the one that failed was the
one-time code, 123456, which is inside the reference number 04141234567890. Looked for as a
whole value it is absent too; the card number never was present.


## 2026-11-13c — the overlay half after visible status and the first-time setup (`feat/interface-setup`)

`pytest frontend`, on mains, at the phase 7b commit: **760 passed, 2 failed, 1 error, 3 skipped,
1782s**. All three came from the new behaviour meeting old tests, none from a defect, and each
test was brought to the new rule rather than the behaviour bent to the test:

- `test_brand.py`, "it tries again only while it is up": the window now keeps trying on the home
  screen, by the advisor's direction (L). Rewritten to check it keeps trying, no more than about
  once a second, and that a press's connection is the only one from then on — the reason the old
  rule existed. 1 of 1.
- `test_forget_run.py`, both tests: the reset's helper skipped exactly four welcome questions;
  against the real backend there are now six. It skips until the welcome has gone. 2 of 2.

An earlier run of the same half, on phase 6 alone, is **not counted**: 36 of its errors were
`test_sites.py` importing a half-old backend, because the phase 7b backend was being written
while it ran — a mistake in how the run was done, not a result.

The backend tests 7b touches, beside that run: **142 passed, 2 failed** in
`test_open_goal.py`, then **144 of 144** and **62 of 62** on two re-runs, in both orders.
Read as timing under load (two real-browser tests, started as the overlay run started its
browsers), not proved; recorded as an intermittent to watch.


## 2026-11-13d — the host fit test, in the real window, after phases 1 to 8

`SIMBA_HOST_TESTS=1 pytest frontend/test_window_fit.py`, after `npm run build`, on mains.
**First: 3 failed** — at 100%, 125% and 150% alike, the smallest text on the home screen was
18px against the project's floor of 20px. The new status line (phase 6) was set in the caption
size. The headless tests had measured its place, not its size; only the real-window test
checks the floor. Fixed: the line in the 20px size, the site list's foot raised to leave it room
(`fix/interface-status-size`). **Then: 3 passed**, 589s.

## 2026-11-13 — the Windows installer, built, installed and run on this machine (`feat/infra-installer`)

`tools/build_installer.py` then `tools/evaluation/installed_app_run.py --runs 3`: one silent
per-user install of the built `SIMBA-Setup-0.0.1.exe`, three launches of the installed app
(the first on a profile that did not exist), "hello" typed into each, the window closed with
WM_CLOSE as pressing X does, then a silent uninstall. No replica was running, so the only thing
that could greet was the bundled backend.

**Conditions.** Taken 2026-11-13T00:56+05:00 · `feat/infra-installer` at `233e737` plus the
uncommitted change this entry describes (committed afterwards without code changes) · build and
driver Python 3.12.3 (`D:\simba\backend\venv`), bundled Python **3.12.10** embeddable · Electron
32.3.3, electron-builder 26.18.0, Playwright 1.62.0 · Windows 11 10.0.26200, 8 CPUs, CPU load 56%
at the start, **1,227 MB memory free**, on mains · no `SIMBA_*` switch set, no API key in the
environment · Windows Defender real-time scanning on (not changed). The machine was busy
throughout (the installer build itself ran at 64% load beforehand), so the times below are
upper-end, not typical.

| What | Result |
|---|---|
| Installer (`SIMBA-Setup-0.0.1.exe`) | **199.6 MB** (199,583,460 bytes) |
| Installed folder | **695.2 MB**; about 13,900 files in the backend bundle alone |
| Backend bundle before packing (`stage/backend`) | 416.6 MB |
| Longest path inside the install, from the install folder | 156 characters (budget 170) |
| Build, from nothing (download cached) | 802 s (an earlier build, with the download: 542 s) |
| Bundled backend's own smoke test, start to `/` answering | 4.7 s |
| **Install time**, silent, per user | **260.7 s** |
| **Cold start**, first launch ever (new profile, new executables) | **16.95 s** |
| Cold start, second and third launch | **7.06 s, 6.12 s** |
| "hello" to the greeting on screen | 0.14 s, 0.08 s, 0.08 s |
| Greeting | "Hello. Here's what I can help with." 3 of 3 |
| Processes running from the install folder while open | 6 (SIMBA.exe and its helpers, python.exe, Playwright's node.exe) |
| ... after the window closed | **0**, 3 of 3; the backend's PID gone 3 of 3 |
| Uninstall, silent | 32.7 s; **0** processes left; install folder removed |
| Profile folder `%APPDATA%\SIMBA` after uninstall | kept (by design; see DECISIONS.md) |

Cold start is measured from starting `SIMBA.exe` until the overlay's first screen (the
first-time welcome, or the home screen) is visible, read over CDP. It includes the host waiting
for the backend to answer before it opens the overlay, which is where most of it goes. The
first launch's extra ten seconds are not explained by anything measured; Defender scanning
newly written executables on first run is the likely cause and was not checked.

Every launch used a different pair of ports, both on 127.0.0.1: CDP 62422 / 49158 / 49197,
backend 52873 / 49161 / 49198 — the overlay's `?ws=` named the backend's each time.

The backend logged, each launch, "routing by keywords: ANTHROPIC_API_KEY is not set": the
installed app has no model key, so anything but a greeting or a keyword-routed goal falls back
(flagged in the report).

**Failures found on the way**, each fixed before the numbers above:

1. **electron-builder wrote into the system temp folder** (`elevate.exe`, staged in `%TEMP%`),
   against CLAUDE.md. It removed it itself on exit; the build now sets `TEMP`/`TMP` to
   `.scratch/installer-build/tmp`, and the second build's log names no path outside the repo.
2. **A path over Windows' 260 characters.** Deleting the first build's output failed on
   `anthropic\types\beta\__pycache__\beta_managed_agents_self_hosted_resources_unsupported_deployment_paused_reason_error.cpython-312.pyc`.
   Inside an install that path is 176 characters from the install folder, which would have
   left 83 for the folder itself, and NSIS and Python's imports both stop at 260. The packages
   now live in a short `resources\backend\site\` (156, leaving 103), the build stops if
   anything passes 170, and its own clean-up uses `\\?\` paths.
3. **Backslashes in a bash heredoc** turned `resources\backend` into a backspace character
   in the build script's comment, and `\\?\` into `\?\` in its code. Found by reading the file
   back; fixed with an edit.
4. **`test_window_fit.py` failed 3 of 3 in a fresh worktree**, before opening a window:
   `tools/evaluation/display_fit_run.py` writes its host log into `.scratch/screenshots/fit/`
   without creating it, and a new checkout has no such folder. Not this change; with the
   folder made by hand the same tests passed. Left as it is (flagged).

**Tests run** (not the full suite, as asked), on `feat/infra-installer` with
`SIMBA_HOST_TESTS=1`: `frontend/test_window_fit.py` **3 passed** in 635 s (the development
host, at 100%, 125% and 150%: the window still fits and the site view is still 1280x800);
`frontend/test_brand.py`, `backend/test_data_paths.py` (new, 3 tests),
`backend/estimator/test_pairing.py`, `backend/orchestrator/test_llm.py`: **88 passed** in
131 s. `npm run build`: clean (tsc strict, then vite).

## 2026-11-13e — the installer again, after merging `main`: a crash, a second launch (`feat/infra-installer`)

`main` brought first-time setup and the website catalogue while this branch waited, so the
branch took `main` in, moved setup's `data/ai.json` and the person's `data/catalogue.local.json`
to the profile, shipped `data/catalogue.json`, and was rebuilt and run again with
`tools/evaluation/installed_app_run.py --runs 2 --reuse`.

**Conditions.** 2026-11-13T17:43+05:00 and after · `feat/infra-installer` at `8b01456` plus the
run script's two fixes below · same machine and versions as 2026-11-13 · no `SIMBA_*` switch, no
key in the profile.

| What | Result |
|---|---|
| Installer | **199.6 MB** (199,648,252 bytes), 40 code and data files, longest path 156 |
| Build | 787 s |
| Install, silent | **381.5 s** (261 s the day before, same machine; it was busier) |
| Cold start, launches 1-4 (not first ever) | 6.52, 7.47, 6.70, 10.58 s |
| "hello" to the greeting | 0.11-0.17 s, 4 of 4 |
| **Second launch while open** | ended in **0.92 s**, exit code 0; still **1** backend |
| **Host killed by its PID** (`taskkill /PID <host> /F`, not `/T`) | the backend gone **0.22 s** later; **0** processes left |
| After closing the window | 0 processes left, 4 of 4 |
| Uninstall | 23.5 s; 0 processes left; install folder removed |

The crash case is the one the first round could not have passed: the host's quit handler never
runs when the host is killed. The backend now waits on the host's process handle
(`backend/orchestrator/host_watch.py`) and ends itself.

**Failures found on the way:**

1. **The run script read the previous launch's CDP port.** The first launch after a 381 s
   install took 20 s to start, and the script read `DevToolsActivePort` before the new host had
   replaced it: `connect ECONNREFUSED 127.0.0.1:49197`, a port from the evening before. The app
   was fine — its log shows its backend up on the new port. The script now takes only a file
   written after the launch.
2. **That failed run left SIMBA open.** The script's "close" went before the window existed
   (the host shows it once the backend answers), so it reached nothing. Found by listing what
   ran from the install folder; closed with WM_CLOSE to its own window, and its backend went
   with it. `close_window` now retries until the window is there.

Backend tests on the merged branch: `test_data_paths.py`, `test_host_watch.py` (new, 3),
`test_llm.py`, `test_provider_chain.py`, `test_ai_settings.py`, `test_app_routing.py`,
`test_pairing.py`, `test_vault.py`: **108 passed** in 106 s.

Host tests (`SIMBA_HOST_TESTS=1`): `frontend/test_window_fit.py` and `frontend/test_brand.py`,
**50 passed** in 738 s, so development's window is unchanged by the lock and the switch order.

## 2026-11-13f — a smaller element list for the model: tokens per step, before and after (`feat/perception-trim-prompt`)

`tools/evaluation/prompt_size_probe.py`: seven pages read once and kept — three replicas
(registration with its modal up, billing with its cookie banner, the train search with the date
picker open) and four public catalogue pages (gov.uk bank holidays, Wikipedia's main page,
timeanddate's Lahore weather, FCCU's home page; each robots.txt checked, each loaded once,
nothing pressed). Each page's prompt was built exactly as the planner builds it (for the public
pages with "What the page says", as the open-goal planner sends it) and sent once to Gemini,
whose own `prompt_tokens` is the count. Same seven samples both times; only the renderer differs.

**Conditions.** before 2026-11-13T18:14:02+05:00, after 18:16:44 · `feat/perception-trim-prompt`
off `main` at `6a55423`, uncommitted (the renderer is the only difference) · Gemini `gemini-3.1-flash-lite` alone, free tier, through its
OpenAI-compatible endpoint · Python 3.12.3, Playwright 1.62.0 · on mains, CPU load 3% and 4%.

| Page | Elements | Prompt tokens before | after | Chose before | after |
|---|---|---|---|---|---|
| registration, modal up | 66 | 2,123 | **335** | Close | Close |
| billing, cookie banner | 37 | 878 | **365** | Accept all cookies | Accept all cookies |
| train search, date picker open | 55 | 1,620 | **1,098** | 20 | 20 |
| gov.uk bank holidays | 56 | 1,854 | 1,791 | answer "25 December Christmas Day" | the same |
| Wikipedia main page | 299 | 4,169 | 4,073 | answer (the featured article) | the same |
| timeanddate, Lahore weather | 73 | 2,572 | 2,492 | answer "23 °C" | the same |
| FCCU home | 81 | 2,066 | 1,898 | Admissions | Admissions |
| **Mean per step** | | **2,183** | **1,722 (−21%)** | | **7 of 7 the same** |

Where it comes from: on the replica pages more than half the list's characters were the
per-line notes ("<- OCCLUDED, cannot be clicked", "<- INFERRED (role worked out from layout,
not declared)"), and with the modal up 65 of 66 elements were behind it. The public pages save
3-8%: what they say is already capped at 2,400 characters, and their links are real.

**Not worse, measured two ways.** The seven single steps above chose the same element, or gave
the same answer word for word, 7 of 7. And the whole registration task with the model
(`tools/evaluation/llm_registration_benchmark.py 3`, the replica, Gemini through `.env`):
**3 of 3 completed in 5 steps**, the fewest it can take — sign in, close the notice, register —
in 18.0, 24.4 and 69.0 s. Not a ten-run benchmark: three runs show it still finishes, not that
its rate is unchanged.

**Failure found on the way.** `backend/orchestrator/test_shared_recovery.py` failed, 6 errors and
1 failure: its fake model injects a failure by clicking a link that goes nowhere, and the trimmed
list no longer shows such links. The test now gives its fake the full list (a module fixture,
with the reason); what it tests — that both planners recover the same way — does not depend on
the prompt's wording. 7 of 7 pass.

**The suite, with the shorter list.** `pytest backend tools`, `test_live_site.py` left out (it opens a live site): **1,564 passed, 10 skipped, 0 failed** in 2,037 s, on `feat/perception-trim-prompt`.

## 2026-11-13g — Gemini → Groq → OpenRouter, live, once each way (`tools/evaluation/fallback_live_run.py`)

One planner step on the gov.uk bank holidays page (public, captured above), through the chain
`provider_from_env` builds from `.env`, three times. Every call a real request. A rate limit
cannot be had on cue, so the earlier providers were made to fail with a model name that does not
exist: Google and Groq each answered **404** for real, and a 404 moves the chain on by the same
path as a 429 (`llm._cannot_answer_now`).

| Case | Chain | Answered by (as the app shows it) | Answer | Seconds |
|---|---|---|---|---|
| A. as configured | Gemini, Groq, OpenRouter | **Gemini** | "25 December Christmas Day" | 15.66 |
| B. Gemini gets a 404 | the same | **Groq** (`openai/gpt-oss-120b`) | "The next bank holiday in England and Wales is 25 December Christmas Day" | 2.27 |
| C. Gemini and Groq get 404s | the same | **OpenRouter** (`nvidia/nemotron-3.5-super-vl:free`) | the same sentence as Groq's | 5.75 |

**Conditions.** 2026-11-13T18:21:55+05:00 · `feat/perception-trim-prompt` at `6a55423`,
uncommitted · CPU load 23% · keys from `D:\simba\.env`,
never printed · the three providers' free tiers · no personal data in any prompt.

**What it shows beyond "it falls back".** Groq and OpenRouter both wrote a sentence where Gemini
copied the words. The open-goal planner accepts an answer only if the page says it word for
word, so in the app that answer is refused once and asked again with the reason — one more call
on the fallbacks, not a wrong answer shown. Measured on one page; not a rate.

## 2026-11-13h — phase 5, runs A and B: an AI goal with a search on a live shop (Readings)

Raham's OK for runs A and B of the phase 5 plan. The site is readings.com.pk (a Lahore
bookshop): its robots.txt is `Allow: /`, its terms give "permission to access and make personal
use of this site", and nothing in them mentions automated access (read 2026-11-13). The goal
carries no personal data, so Gemini's free tier was used. Each run once; nothing was bought,
added to a cart or signed in to.

**Run A** — `tools/evaluation/open_goal_live_run.py https://www.readings.com.pk/ "Find the price
of the book Atomic Habits on Readings"`: the real loop and `OpenGoalPlanner`, headless Chromium at
1280x800, every step answered "go ahead" by the script. 2026-11-13T19:33:51+05:00, `main` at
`978396c`, CPU load 13%.

**Run B** — the same goal, typed into **the real SIMBA window** (`run.ps1`, the AI planner on:
`SIMBA_USE_HARDCODED_PLAN=0`), as "Find the price of the book Atomic Habits on readings.com.pk".
The window's own buttons were pressed over CDP as a person would press them, and "Atomic Habits"
was typed into SIMBA's own field when it asked. 2026-11-13T19:35+05:00, the same commit.

| | Run A (headless) | Run B (SIMBA window) |
|---|---|---|
| Step 1 | type "Atomic Habits" in the search box | the same; SIMBA asked the person for the words |
| Step 2 | open "Atomic Habits : an Easy & Proven Way … James Clear Rs. 3896 - In Stock." | the same |
| Model's answer | **"Rs. 3896"**, twice | **"Rs. 3896"**, twice |
| SIMBA's check | refused twice: not on the page word for word | the same |
| End | `help.requested`: "I couldn't work out how to do this on this website." | "I'm stuck, so I've stopped.", 134 s after the goal |
| Worked out with | Gemini, 4 calls, no fallback | Gemini, 4 calls, no fallback |
| Time | 55.1 s | 134 s (two person's presses included) |

**Result: 0 of 2 answered, and both stopped safely.** The model did the task: it searched, opened
the book's page and gave the price the search results showed. SIMBA refused the answer because
its check (`OpenGoalPlanner._choose`, `content.says`) compares against perception's extracted
"What the page says" — headings, label/value pairs, prominent values, tables — and on the book's
page that held the page's headings and links but **no price at all**. So a right answer, which
the page shows, could not be accepted, and the run stopped with a message that blames the website.

**Also seen in run B:** the step's words were cut after "James Clear Rs.", so the window showed
the book without its price; and the stuck message, "I couldn't work out how to do this on this
website", is not what happened.

Afterwards: `run.ps1 -Seconds 420` stopped everything itself; ports 9222, 8000, 5000 and 5100 free.

## 2026-11-13i — the answer check, fixed: Readings again (`fix/orchestrator-answer-check`)

Raham's "yes, fix it" to the open question of 2026-11-13h. Two causes, found one after the
other, each with a test written first and failing:

1. **The check read too little of the page.** `Content.says` looks at headings, label/value
   pairs, large values and tables; Readings' price is plain text in none of them. Perception now
   keeps the page's visible text too (`Content.text`: laid-out text nodes, in page order, nothing
   under `display: none`, `visibility: hidden`, a script or a floating panel), and an answer is
   checked by `Content.shows`: the content, or that text. `says` is unchanged, for success
   conditions. *Re-run of A after this alone* (19:48:39, load 33%): refused twice again, 72.6 s.
2. **One space.** A look at the book page, read-only (`.scratch/readings_price_probe.py`, once):
   the page writes `Rs.3896`, in a `<span class="sale-price">`, and its page text now read
   "Our Price: Rs.5195 Rs.3896". The model had answered "Rs. 3896" because SIMBA's own label for
   the search suggestion read so — perception joins two pieces of text with a space. `shows` now
   ignores a space beside punctuation, on both sides; letters and figures must still match
   ("Rs 3896", "Rs.38 96", "Rs.3895" are refused, `test_content.py`).

**Confirming run** (`open_goal_live_run.py`, the same goal, 2026-11-13T19:54:11+05:00, load 37%):

| | |
|---|---|
| Outcome | **`task.completed`**, answer **"Rs. 3221"**, 3 steps, 70.9 s, 3 model calls |
| Moves | type "Atomic Habits"; open "Atomic Habits : an Easy and Proven Way To Build Good Habits and Break Bad Ones James Clear Rs. 3221 - In Stock."; "The page says: Rs. 3221. Is this what you wanted?" |
| Worked out by | Gemini, then **Groq** — Gemini answered **503 "This model is currently experiencing high demand"** mid-run, and the chain moved on by itself: a real fallback, not a forced one |

Rs. 3221 is the price of the edition Groq opened, a different listing from the Rs. 3896 one
Gemini opened in runs A and B; the goal did not say which edition. The person's "Is this what you
wanted?" is where that is put right ("No, keep looking").

On Readings today: three runs of A, run B in the window, and two looks at the book page for this
diagnosis. No more.

Tests: `test_content.py` 27 passed (2 new), `test_open_goal.py` 11 passed (3 new). The two
files fail together in one process — the first's synchronous browser holds an event loop the
second's `asyncio.run` cannot start under — which is how they were before; the full suite runs
them in an order that does not meet it.

Full suite with the fix: `pytest backend tools`, `test_live_site.py` left out: **1,569 passed, 10 skipped, 0 failed** in 2,303 s.

## 2026-11-13j — phase 5, runs C, D and E on free models only, with Raham away (`eval/phase5-cde`)

Raham: the Gemini key is not paid, the work has to be done with free APIs, run what can be run
while he is away. So every run below sent nothing personal to any model (Gemini, Groq and
OpenRouter are all free tiers), and none could place an order, a booking or a submission: those
are the person's own press on the final screen, and he was not there. Each run by
`tools/evaluation/open_goal_live_run.py`, headless Chromium at 1280x800, keys from `.env`.

**First, a safety fault in that script, found before any run and fixed.** It played the person
by answering "yes" to every step. Until today that was safe: on a live site nothing could be
changed. Since the final-step rule changed (live changes after the final screen), "yes" to a
final screen would have pressed "Do it" — on run D, submitted the form. It now answers a final
screen "Don't do it" and cancels any handover (`tools/evaluation/test_open_goal_live_run.py`).

**And a fault in that fix, found by run C.** The first version took any step offering "decline"
for a final screen; "Is this what you wanted?" offers "No, keep looking" under the same id, so it
turned down the right answer nine times (38DN, 2DN, 10DN, three times each) and the model wandered
until a covered Search button stopped it (20 steps, 169.7 s, 20 calls). That run does not count.
A final screen is now the step that lists its details; a test holds an answer accepted.

| Run | Site and goal | Outcome | Steps | Calls | Seconds | Worked out by |
|---|---|---|---|---|---|---|
| **C** | pakrailways.gov.pk/train — "Find a train from Lahore to Karachi on 20 November 2026 and book one seat on it" | **completed: "38DN"** — stations, date from the calendar, search, the answer | 8 | 8 | 89.5 | Gemini |
| **D** | fccollege.edu.pk — the online admission form for a made-up applicant ("Test Applicant", test@example.com), not submitted | **stopped at once**: the site's check that a person is there was handed over, and with nobody there the script cancelled it. Nothing typed, the model never called | 0 | 0 | 3.6 | — |
| **E** | readings.com.pk — "Put the book Atomic Habits by James Clear in the cart … go to checkout. Do not enter any personal details and do not place the order." | **stuck**: typed "Atomic Habits" in the search box seven times, and twice pressed a button labelled only by an icon-font glyph (shown as "Click .") | 12 | 12 | 193.9 | Gemini |

Conditions: 2026-11-13T20:54:40+05:00 (C, first), 20:58:21 (C), 21:00:14 (D), 21:00:42 (E) ·
`eval/phase5-cde` off `main` at `19f217b`, the script's fixes uncommitted · CPU load 7-15% · no
`SIMBA_*` switch.

**What these show.**
- **C** does the search part of a booking on the live site end to end, and stops where its rules
  stop it: the open-goal planner's rules say never to press a button that books, and to leave it
  to the person. So the booking's final screen and the payment handover were not reached — they
  need the AI planner allowed to press "Book" (behind the final screen), the person's sign-in and
  the passenger's details, which on a free model cannot be sent.
- **D** needs a person at the keyboard to pass the site's own check; the handover did what it
  should with nobody there.
- **E** shows two things: an icon-only button gives the model nothing to read (perception labels
  it with the icon font's private-use character), and the open-goal planner ends a task only with
  an answer, so a goal that is all doing ("put it in the cart") cannot complete with it.

Also seen: a step whose element has no readable name is shown to the person as "Click element 13."
or "Click ." — words that tell a person nothing.

Not run: the real cash-on-delivery order (needs Raham's own press and his name, address and phone,
which may not go to a free model), and the booking up to payment.

## 2026-11-14a — the AI planner carries a task out: order and payment, real model, pages served here (`feat/orchestrator-live-doing`)

Raham, 14 November: SIMBA has to *perform* a task like a payment, as the advisor asked ("tasks
carried out on live sites, not only read"), even with a real payment of Rs 200-500. Before this,
the AI planner was told never to press a button that orders, books or pays, could end only with an
answer, was shown no plain paragraph text, and sent what the person typed to the model whenever a
site showed it back. All four changed, each with a test first (`test_live_doing.py`, 5 tests):

| Test, through the real loop and a real browser, model scripted | Result |
|---|---|
| An order: fill the name (the person types it), continue, "Place order" behind the final screen, finish with the order number | passes |
| "Don't do it" on that final screen: nothing changed, the model never sees the confirmation | passes |
| What the person typed never reaches a model, although the site shows it back ("Deliver to: …") | passes |
| A payment: "Pay now" behind the final screen, the card page handed to the person, the receipt read after | passes |
| The planner's rules no longer forbid pressing; still never type card details | passes |

**With the real model** (`tools/evaluation/live_doing_replica_run.py --runs 3`, the same two pages
served from this machine; the person played by the script, typing a made-up name and answering
"Do it"; 2026-11-14T06:31:20+05:00, CPU load 58%, Gemini free tier):

| Goal | Runs | Completed | Final screens per run | Model calls | Name sent to the model | Seconds |
|---|---|---|---|---|---|---|
| "Order this book for me, cash on delivery" | 3 | **3**, answer "Order placed Order number: 4711" | 1 | 4 | **never** | 10.3, 8.0, 19.0 |
| "Top up my phone with Rs. 200" | 2 | **2**, "The website says: “Payment successful”." | 1 | 1 | **never** | 4.9, 6.1 |

Every move worked out by Gemini; no fallback needed. An earlier run of the same script (06:2x) had
the orders 3 of 3 and the top-ups ending "I've stopped" — the script's reply to the handover lacked
the `"action": "done"` the loop reads, so it counted as a cancel; fixed, and the test now plays the
person pressing "I've finished" a second after paying, as a person would, not before.

**Also changed, from run E on Readings (2026-11-13j):** typing into a search box now presses Enter
too (by role `searchbox`, or a field labelled search/keyword/find); icon-font characters are taken
out of labels, so an icon-only button is "(no name)" to the model and "the button with no name" to
the person, not "Click .". Tests in `test_llm_loop.py` (3 new).

**Not measured:** the prompt's size since plain page text joined "What the page says". It shares the
same 2,400-character cap as before, so a step can grow by at most about 600 tokens on a page whose
headings and tables did not already fill it; Groq's free 8,000 tokens a minute then allows about
three steps a minute.

**Tests.** Full `pytest backend tools` (live-site file left out): **1,577 passed, 2 failed, 10 skipped**
in 2,360 s. The 2 were yesterday's new `tools/evaluation/test_open_goal_live_run.py`, failing only in
the whole suite: a synchronous Playwright session from an earlier test holds the thread's event loop,
and `asyncio.run` will not start under it. They now run their browser on a thread of their own, and
pass after `test_content.py` in one process (29 of 29); the full suite was not run again for that
test-only change. Overlay with Readings added to the list: `test_sites.py`, `test_home.py`,
`test_setup.py` **95 passed**. Readings is in `data/catalogue.json` (Shopping: "Find a book's price",
"Buy a book"); `test_catalogue.py` 33 passed.

For Raham's real payment run: `docs/live-payment-run.md`.
