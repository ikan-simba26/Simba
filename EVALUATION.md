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
  would change what the perception work is worth.
- **One replica, one task.** Everything here is `replicas/registration` and
  the CS-401 goal. Nothing has been measured against a second site, a second
  task, or a page whose overlay is not a full-viewport backdrop.
- **No cost measurement.** Tokens per run and cost per completed task are not
  recorded yet.
- **The hardcoded planner has no benchmark.** The A/B it exists for has not
  been run, so there is no baseline to compare the LLM against.
