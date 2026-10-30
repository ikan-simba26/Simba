# Showing SIMBA in five minutes

A script for showing the system to someone: what to run, what to type, what to
point at, and what to do when a part of it fails in front of them.

The shape of it: **show them the real website first.** The clutter is the
problem SIMBA exists for, and nobody feels it from a description. Then the same
task, in SIMBA, in one window.

Everything below has been run end to end. The recordings in `demo/` were made
on 2026-10-16 on our own copies, and show the overlay as it is now: named
stages in place of a count, the safe moves running as a checklist, the
trains as tickets, the answer on the real page ("See it on the real page"),
and a booking through its final screen to the site's confirmation. At a
watchable pace: railways 35 seconds, a booking 78, billing 39, a greeting
8. **The live railways run is slower** — about 55 seconds of task
time against 26 on the copy (EVALUATION.md, 2026-10-16), before any pauses
for narration.

---

## Rehearsing

**Rehearse on `railways-local`. Run the live railways flow only for the real
demo.** Every railways run on the live site is a search on somebody's public
service, and CLAUDE.md keeps repeated runs off live sites.

```powershell
.\run.ps1 railways-local       # the window opens on our own copy of the train search
```

Then type exactly what the script below says — `trains to Rawalpindi tomorrow`,
`Lahore`, `Lahore Cantt` — as many times as you like. Every screen, question
and sentence is the same as on the live site, in the same order (EVALUATION.md,
2026-09-30c); nothing leaves the machine. Billing, "hello" and "book a flight"
run locally from any start page. On the day, the live railways run is the one
you do in front of the audience, from `.\run.ps1 billing` as below.

Two things the copy does not rehearse. **Pace**: it runs about twice as fast as
the live site, and so do the recordings, which are made on it. Leave room: the
live search steps take longer, and nothing short of the live site shows how
much on the day.
**The live site's own look**: the copy is plain on purpose, so the opening
"show them the real website" is still rehearsed on the real page, by looking at
it, not by searching.

**The recordings show the flow as it is** (re-recorded 2026-10-16; the
booking again on 2026-10-17): the questions, the read-back, the checklist,
the answer and the real page; and, in `demo/booking.webm`, a booking on our
copy through its final screen, ending "Booked on the practice site." with
the booking number and that no real ticket was booked and no money taken.
They are made on our own copies, so **the live site is never used to make
them** — `tools/record_demo.py` asks the
backend where a train goal would run and refuses to record the railways clip
anywhere but the copy. Re-record whenever the flow changes.

---

## Ten minutes before

```powershell
cd D:\simba
.\run.ps1 billing              # opens on the billing replica; both replicas, the window, the backend
```

The word after `run.ps1` is only the page the window opens on. What you type
chooses the task, so railways works from here too.

Wait for `==> ready - type a goal in the SIMBA window and press Start`. Then,
in a second terminal, check the backend agrees with you about what it is:

```powershell
curl http://127.0.0.1:8000/
# {"status":"ok", ... "router":"model","planner":"hardcoded", ...}
```

- `planner: hardcoded` is what you want in a demo: it spends no API quota and
  does the same thing every time. `run.ps1` sets it by default.
- `router: model` means the typed goal is classified by the model, which takes
  1–6 seconds. With no key or no quota it says `keywords`, and the demo works
  exactly the same.
- `level: trained model` means **the first page is judged from people's
  ratings** (since 2026-10-30). It says `provisional rules` if
  `data/estimator.json` is missing, which still works. **Billing and
  registration now start at the simplest level**, because the model scores
  their first pages heavy, so they have no further to fold: to show a fold,
  use the trains, or start with `$env:SIMBA_PAGE_MODEL = "0"`.
- **The screen adapts to you while you present** (since 2026-09-25). Talking
  over a step for 15 seconds, or pressing "What are you doing?" — which the
  script below does — folds a step that is not already at the simplest level,
  with "I'm showing less for a moment". That is the feature working; say so if
  it happens. To keep the level still, press the middle level dot once at the
  first step (it locks until "let it choose"), or start with
  `$env:SIMBA_ADAPT = "0"`.

Open a second, ordinary browser window at
`https://www.pakrailways.gov.pk/train` and leave it on screen one. Leave the
SIMBA window on screen two, or alt-tab between them.

**Have `demo/` open in a file manager too.** Those recordings are the fallback
for every failure below. They are not committed — record them the day before,
with the stack on our copy of the train search:

```powershell
.\run.ps1 railways-local            # in one terminal
python -m tools.record_demo          # in another: all five clips
```

It prints what each clip did. Every task clip should end on "found an answer";
one that ends on "I'm stuck" is not a fallback for a run that worked.

**Do not minimise the SIMBA window while recording.** The clips are drawn in a
separate browser, but the backend still drives the page inside the SIMBA
window, and a minimised window is painted about once a second: on 2026-10-05
the billing and adapt clips ended "I'm stuck" because a click on the reference
box never saw the page settle. Covered by other windows is fine; minimised is
not.

---

## The five minutes

### 0:00 — the problem, on the real site (40 seconds)

Show the live railways page. Point at, in this order:

1. the menu bar and the language switch — **before** anything to do with trains;
2. the search panel: four fields, two of them dropdowns that only open on click;
3. the date field — it looks typable and is not. It must be picked from a
   calendar, and the calendar opens on today's month.

Say: *this is the page, and this is someone's Tuesday afternoon.* Do not
attempt the search yourself; the point is the clutter, not a race.

### 0:40 — the same task, in SIMBA (2 minutes)

Switch to the SIMBA window. Before typing, point at what is **not** there:
no menu, no address bar, no advertisement. One question, in large type.

Type, exactly:

```
trains to Rawalpindi tomorrow
```

Press Start. It asks only what the sentence did not say — where from, and
which of the site's two Lahore stations — then reads the journey back once.
Type `Lahore` into the box when asked, and press `Lahore Cantt`.

| What is on screen | What to say |
|---|---|
| "Let me see what you need." | It is working out what you asked for. Nothing has started yet. |
| "Where are you travelling from?", one box | It read the rest out of the sentence: the destination, and that "tomorrow" is a date. This is the one thing it could not know. The row at the top is where you are: From, To, Day, Search, Trains. |
| "Which Lahore station do you mean?", two buttons | The site's own list has two Lahore stations, so it asks rather than picking. |
| "Lahore Cantt to Rawalpindi, tomorrow, 17 October. Is that right?" | Said back once, before anything on the site is touched. If any of it were wrong, this is where they would stop it. |
| **Press "What are you doing?"** on any step | It shows the real page, close up on what it is about to press, ringed; "Show the whole page" inside it. This is the one way to see the page while it works. |
| "I'm doing what you asked.", a list that ticks off | The person decided; SIMBA clicks. Filling in, the calendar, the search run by themselves, one line each, with one Pause. Anything that is a real choice, or that would book or pay, still asks. |
| The ending | The answer, as the biggest thing on the screen: each train as a ticket, leaves, arrives, how long, the fastest marked, and what was not done ("I only looked up times…"). |
| **Press "See it on the real page"** | The page as the search ended, the trains ringed where they are. It was read again before closing; if it had changed, no answer would be shown. |

If someone asks what a goal that says everything looks like, type
`trains from Rawalpindi to Multan tomorrow` — only the read-back is asked.

### 2:40 — it only does what you ask (1 minute)

Press **"Back to start"**, then type:

```
hello
```

It greets them and shows the three things it can do. **Nothing starts.** Say:
this matters more than it looks — an assistant that guesses is an assistant
that pays the wrong bill.

If there is time, type:

```
book a flight to Dubai
```

It says it cannot, in one sentence, and offers what it can.

### 3:40 — a second task, finished on our copy (1 minute)

Press the card **"Check my electricity bill"**. The card's words do not say
*which* bill, so the first screen asks for the reference number. Type
`04141234567890`. It asks about cookies — "This site asks about cookies.
Shall I say yes?" — press Yes; then it looks the bill up by itself. The
ending says it plainly: **Rs 14,382, due 15 September 2026**.

Beside "Back to start" there is a quieter button, **"Pay this bill"**. Press
it. It opens the payment page and shows the **final screen**: what will
happen, in plain words, the amount, the month, the due date and the
reference as the page states them, and two buttons that look alike — "Pay
it" and "Don't pay". Say: *nothing happens until you choose; this is the
only kind of screen where SIMBA changes anything, and only on our own copy
of a site — on a real one it only reads.* Press "Pay it". The ending says it
plainly: "Paid on the practice site." and under it the site's own receipt
number, and that this was a practice copy, so no money was taken.

To show the other way, press "Don't pay" instead: "I didn't do it. Nothing
was changed."

### 4:40 — the close

One sentence, then stop: *the site is unchanged and still does what it always
did; what changed is what the person has to deal with.*

---

## If something fails

Say what happened, in one short sentence, and move. A demo that admits a
failure and continues is stronger than one that pretends.

| What failed | What you see | What to do |
|---|---|---|
| **The live railways site is down or very slow** | The run sits on step 1, or the stuck screen appears | *"The site is down; here is the same run from yesterday."* Play `demo/railways.webm` — and say it was recorded on our own copy of the
train search: the screens are the same, **the trains in it are invented**. Then do the billing task live — it is local and unaffected. |
| **No internet at all** | The railways site will not load | Skip railways entirely. Open the billing replica page (`http://127.0.0.1:5100`) as the cluttered "before", then run the billing task. Both replicas are local. Routing falls back to keywords with no network, so typing still works. |
| **The Electron window never appears** | `run.ps1` stops at "starting the Electron host" | Almost always `ELECTRON_RUN_AS_NODE`, set by some editors' terminals. `run.ps1` clears it, so start from a plain PowerShell window, not the editor's. Otherwise play the recordings. |
| **A port is already in use** | `port 8000 is already in use - another SIMBA run is probably up` | An earlier run is still alive. Close its window and press Ctrl+C in its terminal. If that terminal is gone, find what holds the port — `Get-NetTCPConnection -LocalPort 8000 -State Listen` — and stop that one process (`Stop-Process -Id <its OwningProcess>`), then start again. Never stop every `python` or `electron`: other programs on the machine may be using them. |
| **The model has no quota** | The reading screen waits ~8 seconds, then works normally | Nothing to do. It fell back to keywords. If you want to avoid the wait entirely, set `$env:SIMBA_ROUTER = "keywords"` before `run.ps1`. |
| **A step genuinely fails** | "I couldn't do that. I'm carrying on." or the stuck screen | Show it deliberately: *it tells you, it does not pretend, and it stops rather than guess.* Then move to the billing task or the recordings. |
| **Everything is broken** | — | `python -m tools.record_demo mock` needs no stack at all, or play the clips in `demo/`. |

---

## If they ask

- **"Does it work on any website?"** No. Three flows today: a course
  registration, an electricity bill, and train times. Anything else is
  declined rather than attempted.
- **"Does it pay the bill?"** Only on our own copies of a site, and only
  after a final screen that says exactly what will happen and waits for "Pay
  it" or "Don't pay". On a real site it reads and never books or pays, and it
  never types card details anywhere (CLAUDE.md, the final-step rule). The
  payment on our billing copy is a pretend one: no card, no money.
- **"Does the model see my password?"** No. Credentials go straight into the
  page; they never enter a prompt or a log.
- **"What if it clicks the wrong thing?"** After every action it checks the
  page changed the way the plan expected. If it did not, it retries once
  differently, then hands over and says so.
- **"Is it always this slow?"** The pace is deliberate — it waits for you.
  The recordings run faster than the live railways site, because they are
  made on our own copy of it; billing and the greeting are the same speed.
