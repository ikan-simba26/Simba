# Showing SIMBA in eight minutes

A script for showing the system to someone: what to run, what to type, what to
point at, and what to do when a part of it fails in front of them.

The shape of it: **show them the real website first.** The clutter is the
problem SIMBA exists for, and nobody feels it from a description. Then the same
task, in SIMBA, in one window. Then a helper teaching it a task of their own.
**With only five minutes, leave out "Teach a task"** (4:40 to 7:40) and close
straight after the bill.

Everything below has been run end to end, last on 2026-11-11 on our copies,
every step walked in the overlay against the real backend. The recordings in
`demo/` were all made again that day and show the overlay as it is now: the
picture tiles, named stages, the safe moves as a journey line, the trains as
tickets, the answer on the real page ("See it on the real page"), a booking
through its final screen, and a helper teaching the bill and running it from
its new tile. At a watchable pace: railways 50 seconds, a booking 59, billing
33, a greeting 6, teaching 79. **The live railways run is slower** — about 55
seconds of task time against 26 on the copy (EVALUATION.md, 2026-10-16),
before any pauses for narration.

---

## What changed for the advisor's review (2026-11-13)

The eight minutes below still run as written. Since 13 November SIMBA also works
on any website, and the advisor asked to see that, so there is a second part,
**"Any website" (about six minutes)**, after the close. Run it after the eight
minutes, or in their place from 2:40 if time is short. It needs:

- **An AI key**, set up in the first-time setup or in `.env` (Gemini; Groq as its
  fallback). For the review use a **paid** key: the free tier's terms let Google
  read what is sent (DECISIONS.md, 2026-11-13). Without one, every goal on a
  website with no plan is answered "I don't know how to do that on … yet", and
  the part still shows "Ask a helper to show me once" — say so and go on.
- **The card gateway on**: start with `$env:SIMBA_CARD_GATEWAY = "1"` before
  `run.ps1`, so "Pay this bill" goes through the test card gateway.
- **Internet**, for the live websites. Nothing is booked, ordered or paid on
  them; the bank holiday and Wikipedia pages are read only.

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

**The recordings show the flow as it is** (all re-recorded 2026-11-11): the
questions, the read-back, the journey line, the answer and the real page;
in `demo/booking.webm`, a booking on our copy through its final screen,
ending "Booked on the practice site." with the booking number and that no
real ticket was booked and no money taken; and in `demo/teach.webm`, the bill
taught once on the billing copy and run from its new tile.
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
  registration start at the simplest level**, the third dot lit on the first
  screen, because the model scores their first pages heavy. So they have no
  further to fold: to show a fold live, use the trains, or start with
  `$env:SIMBA_PAGE_MODEL = "0"`; `demo/adapt.webm` shows one, made that way.
- **At 100% and 150% the sign-in drops to the first dot to fit**, without a
  word, and the next screen goes back to the third (since 2026-11-01). That is
  the screen making room for two boxes, not the level changing its mind.
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
.\run.ps1 railways-local                                        # in one terminal
python -m tools.record_demo railways booking billing hello fold teach   # in another
```

**`teach` needs room on the home screen** — fewer than three tiles under
"Yours", and none called "My bill" — or it stops and says so. It teaches the
bill, keeps it as "My bill", and runs it from that tile, so take the tile off
afterwards ("Change my tiles", "Take it off") before rehearsing the teaching
yourself.

**`adapt` needs a stack of its own.** The trained estimator starts billing at
the simplest level, so with the model on nothing can fold and the clip shows no
fold. Stop that stack, then:

```powershell
$env:SIMBA_PAGE_MODEL = "0"; .\run.ps1 railways-local     # in one terminal
python -m tools.record_demo adapt                          # in another
```

Clear it afterwards (`Remove-Item Env:SIMBA_PAGE_MODEL`), or the rules go on
judging pages in that terminal. `adapt` prints `folded after` a few seconds; the
health check at `http://127.0.0.1:8000/` should say `provisional rules` for this
clip and `trained model` for the others.

It prints what each clip did. Every task clip should end on "found an answer"
(the booking and the scripted `fold` on "done"); one that ends on "I'm stuck"
is not a fallback for a run that worked.

**For "Teach a task", check the home screen and the starter file.** The
home screen needs room for one more tile and no tile already called "My bill":
if there is one, "Change my tiles", then "Take it off" beside it. Know where
the starter file is — `D:\simba\demo\starters\my-bill.simba-routine.json` —
because the fallback for teaching is to add it from the file dialog
(`demo/starters/README.md`).

**Do not minimise the SIMBA window while recording.** The clips are drawn in a
separate browser, but the backend still drives the page inside the SIMBA
window, and a minimised window is painted about once a second: on 2026-10-05
the billing and adapt clips ended "I'm stuck" because a click on the reference
box never saw the page settle. Covered by other windows is fine; minimised is
not.

---

## The eight minutes

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
no menu, no address bar, no advertisement. One question, in large type, and
under it three tiles, each with its own picture: a book, a bill, a train.
"Teach a task" in the top right corner is for later.

Type, exactly:

```
trains to Rawalpindi tomorrow
```

Press Start. It asks only what the sentence did not say — where from, with
the site's own two Lahore stations to choose between — then reads the
journey back once. Type `Lahore` into the box when asked, press
`Lahore Cantt` under it, then `Use this station`.

| What is on screen | What to say |
|---|---|
| "Let me see what you need." | It is working out what you asked for. Nothing has started yet. |
| "Where are you travelling from?", one box | It read the rest out of the sentence: the destination, and that "tomorrow" is a date. This is the one thing it could not know. The row at the top is where you are: From, To, Day, Search, Trains, Book. |
| **Press "What are you doing?"** now, on this first question | It shows the real page as it is, under "This is the page I'm working on."; "Hide the page" goes back. This is the one way to see the page while it works. It also folds the step to the simplest level, the third dot — say so (see "Ten minutes before"). |
| `Lahore` typed: "Lahore Jn" and "Lahore Cantt" under the box | The site's own list has two Lahore stations, so it shows both rather than picking. Press "Lahore Cantt", then "Use this station". |
| "Lahore Cantt to Rawalpindi, tomorrow, 12 November.", "Yes, that's right" | Said back once, before anything on the site is touched. If any of it were wrong, this is where they would stop it ("No, change something"). |
| "I'm doing what you asked.", a journey line | The person decided; SIMBA clicks. Filling in, the calendar, the search run by themselves: the one being done is the large dot, "Doing this now", and at the simplest level only that one and "Then 3 more things." One Pause. Anything that is a real choice, or that would book or pay, still asks. |
| The ending | The answer, as the biggest thing on the screen: each train as a ticket, leaves, arrives, how long, the fastest marked, and what was not done ("I only looked up times…"). Under it, "Shall I keep this on your home screen as Trains to Rawalpindi?" — **press "Not now"**; the home screen stays as rehearsed. |
| **Press "See it on the real page"** | "What I read is ringed.": the page as the search ended, the trains ringed where they are. It was read again before closing; if it had changed, no answer would be shown. "Back to the answer" returns. |

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
*which* bill, so the first screen asks for the reference number. It opens at the
simplest level, the third dot lit: people rated this page as busy, and SIMBA has
read that from the page before you touch anything. Type
`04141234567890` and press "Use this number". It asks about cookies — "This
site asks about cookies." — press Yes; then it looks the bill up by itself,
on a journey line under the stages Reference, Look up, Your bill, Pay. The
ending says it plainly: **"Your bill is Rs 14,382, due 15 September 2026."**
It offers to keep the bill on the home screen as "My bill": **press "Not
now"** — the next part teaches a tile of that name, and two would be
confusing.

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

### 4:40 — Teach a task (3 minutes)

The three tiles were built in. This is how a helper — a carer, a family
member, a teacher — gives the person one of their own, by doing it once.
Press **"Back to start"**.

| What to do | What is on screen | What to say |
|---|---|---|
| Point at **"Teach a task"**, top right | "For a helper, like a carer or a teacher." under it | It is apart from the person's tiles on purpose: this is the helper's way in, not the person's. |
| Press **"Teach a task"** | "Show me a task once", what will happen, a box for "Which website" | It says who it is for, and that on a real website it only reads. |
| Type `127.0.0.1:5100`, press **"Start watching"** | The window becomes **a bar across the top** — "I'm watching." — and **the billing copy below it** | SIMBA steps aside. The helper uses the real site; SIMBA watches. |
| On the website: **"Accept all cookies"** at the bottom, then click **Reference No.**, type `04141234567890`, press **"Check Bill"** | Each thing appears on the bar as it is done: "Pressed Accept all cookies.", "Clicked in Reference No.", and so on | It keeps each move in plain words. "Undo last thing" takes the last one back. |
| The bar asks **"Is what you typed in Reference No. the same every time?"** — press **"Ask each time"** | Then "Finish" | A reference number is the person's, not the helper's. It will be asked for each time, and it is never kept, not even in a saved file. |
| Press **"Finish"** | "Last thing: click the answer on the website." | What the task is *for*: SIMBA cannot guess it, so the helper points. |
| **Click the amount, 14,382**, in the P/WITHIN column | "Here's what I learned. Is it right?", four numbered lines | Read the lines out: ask about cookies; ask what to type in Reference No.; press Check Bill; read the answer from P/WITHIN — "It says 14,382 now." |
| Type `My bill` in **"Name on the home screen"**; in **"What the answer is"**, replace P/WITHIN with `Amount due`. Press **"Keep it"** | "It's on the home screen now, as My bill." | The name is what the person will see. The page's own column name means nothing to them. |
| Press **"Back to start"** | **"Yours: My bill"**, a new tile with the bill's picture and a small mark on its corner | The mark says a helper taught it. One press now does the whole task. |
| Press the **"My bill"** tile. Type `04141234567890`, press **"Use this"**; press **Yes** to cookies | "What should I type in Reference No.?", then the cookie question | The reference asked, as the helper chose. Everything else runs by itself. |
| The ending | **"My bill: 04141234567890"**, **14,382**, "Amount due", "I only did what your helper showed me. I didn't book, pay or change anything." | Same answer as the built-in bill, from one helper's single demonstration. |
| Press **"See it on the real page"** | "What I read is ringed.": the bill, 14,382 ringed | **The proof**: it read the number the helper pointed at, from the page itself. |

**If teaching goes wrong live** — a press not listed on the bar, the wrong
thing kept, the website not loading under the bar — do not fix it in front of
them. Press **"Stop watching"** (on the read-back, "Stop this"), then:

1. Press **"Teach a task"**, then **"Add one from a file"**.
2. In the file dialog, open `D:\simba\demo\starters\my-bill.simba-routine.json`.
3. **Nothing on the screen changes** — it only speaks up when a file cannot be
   used. Press **"Not now"**: "My bill" is on the home screen.
4. Carry on from pressing the "My bill" tile.

Say: *this is the same task, taught once yesterday and saved to a file — a
helper can share one with someone else this way.* The file was made with
"Save to a file" from a real teaching, and asks for the reference number like
the one you just taught (`demo/starters/README.md`). If even that fails, play
`demo/teach.webm`.

### 7:40 — the close

One sentence, then stop: *the site is unchanged and still does what it always
did; what changed is what the person has to deal with.*

---

## Any website (about six minutes, 2026-11-13)

The advisor's question: *what if I need this done on website XYZ?* The answer,
shown: pick it or type it; if the AI can't do it, a helper shows SIMBA once, and
from then on it is a tile.

| What to do | What is on screen | What to say |
|---|---|---|
| **"Back to start"** and point at the left | "Websites I can use": Travel, Bills, Education, Government, Health, Shopping, Look things up, Practice sites | Not three tasks: a list of websites, by kind. It is a file anyone can add to. |
| Point at **"Add a website"** at the foot of the list | | Where a new website goes: name, address, what kind. It is in the list at once. |
| Press **"UK bank holidays"**, then **"The next bank holiday"** | "I'll work it out" under it | No written plan for this site. The AI works it out on the live page. |
| Wait | "The page says: 25 December Christmas Day. Is this what you wanted?" and "Worked out with Gemini." | It answers only with words the page itself says, word for word, and it is your answer only when you say so. The small line says which AI chose. |
| **"Yes, that's it"** | The answer, and "See it on the real page" | The answer ringed on the real page. |
| Back to start. Type `When was the Royal Gloucestershire Hussars formed?` and, in **"Which website"**, `en.wikipedia.org` | | Any website, typed. **Not yet run live** (a goal that needs a search): rehearse it once; if it stops, that is the next row. |
| If the AI says it can't | "I couldn't work out how to do this on this website." and **"Ask a helper to show me once"** | AI first, then teach: the helper is offered on that same website. |
| Press it | "Show me a task once", the address filled in | A helper does it once; from then on it is a tile, and it is offered on websites of the same kind too. |
| **"Not now"**, back to start. Press **"Check my electricity bill"**, the number, cookies, then **"Pay this bill"** | The final screen: amount, month, due date, reference | Paying, booking, ordering: always a final screen first, on any website. |
| **"Go to card payment"** | The window becomes a bar: "Your turn: pay on the page below…", and the card page below it | Payment is always the person's. SIMBA never types, reads or keeps card details. |
| On the page: `4242 4242 4242 4242`, `12/30`, `123`, **Pay**; then the code `123456`, **Confirm**; then **"I've finished"** on the bar | "The website says it went through." and the receipt's own words | It reads the page after, and quotes it. This is a test gateway: no money. |
| Point at the bottom left | "Connected · Finished" | Always says whether it is connected and what it is doing. |

**If something here fails**: the live site slow or refusing — say so, the
stuck screen is the system working, and go to the card payment, which is local.
No key — the "not yet" screen and its helper offer are the answer. The bar does
not show the page — "Stop, change nothing", and show `backend/orchestrator/test_gateway.py`'s
end-to-end test passing instead.

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
| **"Teach a task" says the home screen is full** | "There are already three tiles on the home screen. Take one off first." | "Not now", then "Change my tiles" and "Take it off" beside one, then "Teach a task" again. Check this ten minutes before. |
| **The website does not appear under the bar** | The bar says "I'm watching." over an empty or old page | "Stop watching", then the starter file (4:40, *If teaching goes wrong live*). |
| **The bar lists a press you did not mean** | An extra line under "I'm watching." | Press "Undo last thing" once; the website goes back too. If the bar offers "Start again" instead, it could not take the page back: press it and teach from the beginning, or use the starter file. |
| **The read-back is wrong** | A line you did not do, or a step missing | "Stop this", then the starter file. Do not keep a routine you would not trust. |
| **"I couldn't use that file."** | Under "Show me a task once", after choosing a file | The wrong file, or no room on the home screen. Choose `my-bill.simba-routine.json` in `D:\simba\demo\starters\`, after taking a tile off if the row is full. |
| **Two tiles called "My bill"** | The bill was kept earlier with "Keep it", then taught | Harmless; the taught one has the mark on its picture's corner. Press that one, and take the other off afterwards. |
| **The taught tile ends "I'm stuck"** | The run stops on a step | Say what happened, then play `demo/teach.webm`. |
| **Everything is broken** | — | `python -m tools.record_demo mock` needs no stack at all, or play the clips in `demo/`. |

---

## If they ask

- **"Does it work on any website?"** Yes (since 2026-11-13). Pick one from the
  list, or type any address. Three tasks have written plans; on any other
  website the AI works it out, one move at a time, each move asked and
  checked, and answers only with the page's own words. If it can't, it says so
  and offers "Ask a helper to show me once", and from then on that task is a
  tile. A website whose robots.txt asks programs not to is not used.
- **"Does it pay the bill?"** It gets you to the payment, and you pay. Anything
  that books, orders, registers or pays waits for a final screen that says
  exactly what will happen, with the page's own amounts, and "do it" or
  "don't". Then the payment page is handed to you — card details, the bank's
  code, the press that pays — and SIMBA never types, reads or keeps them. It
  reads the page afterwards and tells you what it says. A CAPTCHA is handed to
  you the same way. Here the gateway is a test one, with a test card.
- **"Which AI is it?"** Gemini, with Groq taking over when Gemini is busy or
  down; each step says which one worked it out. It is set up once, in the
  first-time setup, and the key stays on this computer, locked.
- **"Does the model see my password?"** No. Credentials go straight into the
  page; they never enter a prompt or a log.
- **"What if it clicks the wrong thing?"** After every action it checks the
  page changed the way the plan expected. If it did not, it retries once
  differently, then hands over and says so.
- **"Is it always this slow?"** The pace is deliberate — it waits for you.
  The recordings run faster than the live railways site, because they are
  made on our own copy of it; billing and the greeting are the same speed.
