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
