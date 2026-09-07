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

### The pattern

Every one of these passed a check that was true but not sufficient: the click
did land, the task did complete, the string was on the page. What each check
missed was the *cost* — a wasted step, thirty seconds, an entire run's worth
of context. The defence is not better assertions but a second, unrelated
number next to the first: step counts beside completion, wall clock beside
success, the actual sequence beside the outcome. Two numbers disagreeing is
how all three of these were found.

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
- **One replica, one task.** Everything here is `replicas/registration` and
  the CS-401 goal. Nothing has been measured against a second site, a second
  task, or a page whose overlay is not a full-viewport backdrop.
- **No cost measurement.** Tokens per run and cost per completed task are not
  recorded yet.
- **The hardcoded planner has no benchmark.** The A/B it exists for has not
  been run, so there is no baseline to compare the LLM against.
