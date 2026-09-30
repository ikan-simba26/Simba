# Showing SIMBA in five minutes

A script for showing the system to someone: what to run, what to type, what to
point at, and what to do when a part of it fails in front of them.

The shape of it: **show them the real website first.** The clutter is the
problem SIMBA exists for, and nobody feels it from a description. Then the same
task, in SIMBA, in one window.

Everything below has been run end to end. The timings are from the recordings
in `demo/` (2026-09-23): railways takes 80 seconds at a watchable pace, billing
24, a greeting 8.

---

## Rehearsing

**Rehearse from the recordings. Run the live railways flow only for the real
demo.** Every railways run is a search on somebody's public service, and
CLAUDE.md keeps repeated runs off live sites. Practise the narration against
`demo/railways.webm` — same screens, same pace — and rehearse the parts that
run locally (billing, "hello", "book a flight") live as often as you like. On
the day, the live railways run is the one you do in front of the audience.

If the recordings are missing, make them once, the day before (below); that
is the one other time the live site is used.

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
- `level: provisional rules` means **the screen adapts to you while you
  present** (since 2026-09-25). Talking over a step for 15 seconds, or
  pressing "What are you doing?" — which the script below does — folds that
  step to the simplest level, with "I'm showing less for a moment". That is
  the feature working; say so if it happens. To keep the level still, press
  the middle level dot once at the first step (it locks until "let it
  choose"), or start with `$env:SIMBA_ADAPT = "0"`.

Open a second, ordinary browser window at
`https://www.pakrailways.gov.pk/train` and leave it on screen one. Leave the
SIMBA window on screen two, or alt-tab between them.

**Have `demo/` open in a file manager too.** Those recordings are the fallback
for every failure below. They are not committed — record them the day before:

```powershell
python -m tools.record_demo          # with the stack up: all five clips
```

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

Press Start, then narrate as it goes. **The first two screens are questions,
not steps** (since 2026-09-30): that sentence does not say where the journey
starts, and "Lahore" does not say which of the two Lahore stations. Type
`Lahore` into the box, then press `Lahore Cantt`.

| What is on screen | What to say |
|---|---|
| "Let me see what you need." | It is working out what you asked for. Nothing has started yet. |
| "Where are you travelling from?", one box | It read the rest out of the sentence — the destination, and that "tomorrow" is a date. This is the one thing it could not know, so it asks for that and nothing else. |
| "Which Lahore station do you mean?", two buttons | The station list is the site's own. Two of them are in Lahore, so it asks rather than picking. Before today it would have searched whichever the plan named. |
| Step 1 of 5, one sentence, one big button | One step at a time. It never acts until you press. |
| The dot above the column | That is the assistant: it breathes while it thinks, circles while it acts, and fills when it is your turn. |
| **Press "What are you doing?"** | It shows the real page, zoomed to the control it is about to press, ringed. "Show the whole page" if they want to see where that is. Then "Hide the page". |
| Steps 3 and 4 — the calendar | This is the field that could not be typed. It is picking the date the way the page insists on. |
| "Trains from Lahore Cantt to Rawalpindi on ... Shall I search?" | The last thing it asks for is the search, and it says the whole journey back first. If any of it were wrong, this is where they would stop it. |
| The ending | The answer, as the biggest thing on the screen: the train and how long it takes. |

If someone asks what a goal that says everything looks like, type
`trains from Rawalpindi to Multan tomorrow` — nothing is asked, and it goes
straight to the five steps.

### 2:40 — it only does what you ask (1 minute)

Press **"Do something else"**, then type:

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

### 3:40 — a second task, chosen by pressing (1 minute)

Press the card **"Check my electricity bill"**. The card sends exactly those
words, and they do not say *which* bill — so the first screen asks for the
reference number. Type `04141234567890`. Then three steps, on our own replica
of a utility site: it accepts the cookie banner, types the number you gave it,
opens the bill. The ending shows **14,382** and the due date **15-09-2026** —
the page's own figures, in the page's own format.

### 4:40 — the close

One sentence, then stop: *the site is unchanged and still does what it always
did; what changed is what the person has to deal with.*

---

## If something fails

Say what happened, in one short sentence, and move. A demo that admits a
failure and continues is stronger than one that pretends.

| What failed | What you see | What to do |
|---|---|---|
| **The live railways site is down or very slow** | The run sits on step 1, or the stuck screen appears | *"The site is down; here is the same run from yesterday."* Play `demo/railways.webm`. Then do the billing task live — it is local and unaffected. |
| **No internet at all** | The railways site will not load | Skip railways entirely. Open the billing replica page (`http://127.0.0.1:5100`) as the cluttered "before", then run the billing task. Both replicas are local. Routing falls back to keywords with no network, so typing still works. |
| **The Electron window never appears** | `run.ps1` stops at "starting the Electron host" | Almost always `ELECTRON_RUN_AS_NODE`, set by some editors' terminals. `run.ps1` clears it, so start from a plain PowerShell window, not the editor's. Otherwise play the recordings. |
| **A port is already in use** | `port 8000 is already in use - another SIMBA run is probably up` | An earlier run is still alive. Close it, or `Get-Process electron, python \| Stop-Process`, then start again. |
| **The model has no quota** | The reading screen waits ~8 seconds, then works normally | Nothing to do. It fell back to keywords. If you want to avoid the wait entirely, set `$env:SIMBA_ROUTER = "keywords"` before `run.ps1`. |
| **A step genuinely fails** | "I couldn't do that. I'm carrying on." or the stuck screen | Show it deliberately: *it tells you, it does not pretend, and it stops rather than guess.* Then move to the billing task or the recordings. |
| **Everything is broken** | — | `python -m tools.record_demo mock` needs no stack at all, or play the clips in `demo/`. |

---

## If they ask

- **"Does it work on any website?"** No. Three flows today: a course
  registration, an electricity bill, and train times. Anything else is
  declined rather than attempted.
- **"Does it pay the bill?"** No. It stops at the confirmation screen and
  never submits anything irreversible. That is a design constraint, not a gap.
- **"Does the model see my password?"** No. Credentials go straight into the
  page; they never enter a prompt or a log.
- **"What if it clicks the wrong thing?"** After every action it checks the
  page changed the way the plan expected. If it did not, it retries once
  differently, then hands over and says so.
- **"Is it always this slow?"** The pace is deliberate — it waits for you.
  The recordings are at the same speed as the live runs.
