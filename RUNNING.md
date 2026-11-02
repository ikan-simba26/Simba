# Running SIMBA

One command. `run.ps1` on Windows PowerShell, `run.sh` anywhere with bash —
they do the same thing and print the same lines.

**The argument is the page the window opens on, not the task.** What you type
into SIMBA chooses the task (since 2026-09-21), and every real start page
brings up both replicas, so you can ask for the bill from the registration
page. `run.ps1` called it `-Flow` until 2026-09-25 and still accepts that name.

```powershell
.\run.ps1                # opens on the registration replica
.\run.ps1 billing        # opens on the billing replica
.\run.ps1 railways       # opens on the live railways site
.\run.ps1 railways-local # opens on our own copy of the train search — rehearse here
.\run.ps1 mock           # the overlay against the scripted backend
```

```bash
./run.sh                 # opens on the registration replica
./run.sh billing
./run.sh railways
./run.sh railways-local
./run.sh mock
```

Ctrl+C stops everything it started. Nothing is left listening.

**Everything defaults to the hardcoded plan**, which spends no API quota and
does the same thing every time — so a run that misbehaves is the system's
fault rather than the model's. For the LLM planner, set
`SIMBA_USE_HARDCODED_PLAN=0` first, and read `STATUS.md` on quota before you
do: it is about 20 requests a day and one run costs 6–7.

---

## Installing the exact versions

Every dependency is pinned to the version the full suite passes with
(2026-10-17): `backend/requirements.txt` and `backend/requirements-dev.txt`
name every Python package, the ones they pull in included, with `==`, and
`frontend/package.json` names exact versions that `frontend/package-lock.json`
holds to, down to every package beneath them. Install them like this, and
nothing newer slips in:

```powershell
cd backend
.\venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt     # exactly the pinned set
cd ..\frontend
npm ci                                  # exactly package-lock.json; never rewrites it
cd ..
```

`npm ci` rather than `npm install`: it installs what the lock says and fails
rather than change it. `pip check` afterwards should say "No broken
requirements found." To move a version on purpose, change it in the file,
install, and run the whole suite before committing (README.md, step 5).

---

## What you see

Starting `./run.sh registration` prints, in order:

```
==> starting the registration replica on :5000
==> the registration replica is up
==> starting the Electron host (builds first, ~10s)
==> the host (CDP 9222) is up
==> starting the backend on :8000 — the typed goal picks the task, planner=hardcoded (no API quota spent)
==> the backend is up

==> ready — type a goal in the SIMBA window and press Start
==> Ctrl+Shift+D in the window shows the message log
==> Ctrl+C here stops everything
```

Vite's build output and each server's own logging appear in between. The
`==>` lines are the launcher; everything else belongs to the thing starting.

A SIMBA window opens, showing the logo until the backend has spoken: under 10s
here, 15s at most, and then the home screen with or without one. Type a goal,
press Start, and answer each step. On Ctrl+C:

```
==> stopping
==> stopped
```

The order is not arbitrary. The backend attaches to the host over CDP, so the
host has to exist first; the host loads the replica into its hidden view, so
the replica has to exist before that.

---

## The start pages

**What you type decides what runs** (since 2026-09-21). Every real start page
starts both replicas, the host and the backend; the name only picks the page
the host opens on. The launcher no longer sets `SIMBA_FLOW`, so the backend's
health check says `"flow": "routed by goal"` whichever page you started on,
and a `SIMBA_FLOW=stubborn` set in your own shell now reaches the backend
instead of being overwritten. Type "check my electricity bill" and the billing
flow runs; type "trains from Lahore to Karachi" and the railways one does;
type "hello", "book a flight" or something that could be two of them, and
SIMBA answers and offers what it can do instead of starting anything. The
backend asks the configured model once and falls back to keywords with no
key or no quota (`SIMBA_ROUTER=keywords` skips the model entirely).

| | What it starts | Opens on |
|---|---|---|
| `registration` | replicas :5000 and :5100, host, backend | The registration replica — a page we wrote, a modal to dismiss, ends on a confirmation screen. The thing to run first. |
| `billing` | replicas :5000 and :5100, host, backend | The billing replica — a cookie bar, breadcrumbs, an accordion, and an amount that only `content.py` can read. |
| `railways` | replicas :5000 and :5100, host, backend | **A live public website.** Read-only: fills a search and reads the timetable. Please treat it as somebody's public service — a handful of runs, not a benchmark. |
| `railways-local` | replicas :5000, :5100 and **:5200**, host, backend with `SIMBA_RAILWAYS_URL` set | **Our own copy of the train search.** A train goal runs here instead of on the live site, as often as you like. Two stations in Lahore, two in Karachi, one with no trains. **Use this to rehearse and to try things out.** |
| `mock` | mock backend :8000, host | The overlay alone, driven by a script. No replica, no browser driving, nothing real. |

**SIMBA asks for what your goal left out** (since 2026-09-30). "Trains to
Rawalpindi tomorrow" does not say where from, so it asks — one question at a
time, with buttons where the answers are few. "Check my electricity bill" asks
for the reference number, and the home screen's card sends exactly those
words, so pressing the card asks too. Since 2026-10-06 the train card ("Find
train times") and the course card ("Register for a course") name nothing
either, so they ask for everything. A goal that names everything is asked
nothing but whether the journey is right: type "trains from Rawalpindi to
Multan tomorrow" and the first screen reads it back. Station questions offer
the site's own stations — type a few letters and press one — and every answer
is checked before the site is touched: a day gone, too far ahead or not in the
calendar, the same station both ways, or a name the site does not have.

### The local train search

`replicas/railways/` is a page we wrote that stands in for the live train
search, for the things repeated runs need and the live site cannot give:
several stations in one city, a station with no trains, and a search that can
be run again and again. **`railways-local` opens the window on it** and tells
the backend that the railways flow lives there, so "trains to Rawalpindi
tomorrow" runs end to end without touching the live site. `railways` still
means the live site. Nothing else changes: the other two replicas are up as
usual, and the backend's health check reads the same.

What the copy is not: a timing rehearsal. The same run takes about 25s of task
time here and about 54s on the live site (EVALUATION.md, 2026-09-30c), because
the live site's lists and search are network round trips. Add
`?list_delay_ms=8000` to the page's address to make its station list arrive
late, the way the live one sometimes does.

The tests start the copy themselves. By hand, without the rest of the stack:

```bash
PORT=5200 python replicas/railways/app.py    # then open http://127.0.0.1:5200
```

### The window fits your screen

The window is sized to the screen's work area, taskbar excluded, and never
past 1280x800. On a 1080p laptop at 150% its content is 1266x606. The
interface lays out at that real size — text stays the size it was designed
at, body 23px, nothing below 20px — and below 760px tall it switches to a
compact layout: tighter spacing, smaller cards and buttons, the greeting a
step down (`short:` in `frontend/src/index.css`). A step that still does not
fit drops a level towards the compact level 1, once, and tells the backend.
The site view behind it stays exactly 1280x800 CSS pixels, so perception's
numbers do not change with the screen. The window cannot be resized; change
the display scaling instead, and it re-fits. To check a machine:
`python -m tools.evaluation.display_fit_run native`.

### Rating pages (the estimator's labels)

`tools/rating/` collects people's judgements of the corpus pages, one
screenshot at a time: "How overwhelming does this page feel?", answered Not
at all / A little / Somewhat / Very / Extremely (1 to 5).

```powershell
python -m tools.rating.capture        # once: every corpus page, 1280x800, no scrollbar
python -m tools.rating.examples       # once: the two worked examples, outside the 50
python -m tools.rating.export_form    # the two sets, written to data/rating/form.json
python -m tools.rating.serve          # then open http://127.0.0.1:8765
```

The 50 pages are split into two sets of 25 alike in their features, and each
set also shows three anchor pages from the other (DECISIONS.md, *Two sets of
30*). Each rater enters their number — odd numbers rate Set 1, even Set 2 —
sees two worked examples, then their set's 25 pages and 3 anchors in a random
order plus two of them again later: 30 pictures, about 5-7 minutes. Every
answer is appended to `data/ratings.jsonl` with the page, the set, the time
taken and the size the picture was shown at. The same sets as Google Forms,
for raters who cannot come in: `tools/rating/form/README.md`. The pictures
are in `data/rating/pages/` and are not committed; their hashes are in
`data/rating/pages.json`, which is. Capture once and rate that set: a
re-capture of live pages is a different set of pictures.

### Retraining the estimator

When more ratings come in, download both forms' responses again and run one
command from the repository root:

```powershell
backend\venv\Scripts\python -m tools.rating.retrain "SIMBA rating form, Set 1.csv" "SIMBA rating form, Set 2.csv"
```

```bash
backend/venv/bin/python -m tools.rating.retrain "SIMBA rating form, Set 1.csv" "SIMBA rating form, Set 2.csv"
```

It reads the CSVs into `data/ratings.jsonl` (keeping any in-person rows), trains,
chooses the cut points, holds the new model against the rules, and writes
`data/estimator.joblib`, `data/estimator.json`, `data/estimator_pages.json`, two
new sections of EVALUATION.md and the charts in `.scratch/estimator/`. The next
connection to the backend uses the new model; nothing needs restarting. About
two minutes (116s on battery, 2026-10-30). With no CSVs it trains on the
ratings already there.

**It refuses while any page has fewer than 8 ratings**, and says how many more
raters of each set it takes. The model on `main` was trained under that floor,
so as it stands the command needs `--min-ratings 5`, which is written into the
model and into EVALUATION.md, naming every page under 8. Once Set 2 has three
more usable raters, drop the flag. Add the three new model files by name, and
the two sections; the CSVs and `data/ratings.jsonl` are never committed.

### The level adapts in a real run

Since 2026-09-25 the real backend moves the detail level itself. Since
2026-10-30 **the first page is judged by the trained estimator**
(`backend/estimator/page_model.py`): a page scoring from the heavy cut point
upward starts at level 3, and a calm or middle page leaves the person at their
own level, or at 2 if they have not said. The page can start someone simpler
than the level they chose, never with more detail.
`curl http://127.0.0.1:8000/` says `"level": "trained model"`.

**With no model, the rules judge the page**, by their three signs, and the
health check says `"provisional rules"`. That happens if `data/estimator.json`
is missing, unreadable, synthetic or for other features (the backend logs why),
or with `SIMBA_PAGE_MODEL=0`. Only that file matters to the running app:
`data/estimator.joblib` is the same model for scikit-learn, and the app does
not read it.

**Everything after the first page is still the provisional rules**
(`backend/estimator/rules.py`; every threshold is a guess, listed in
DECISIONS.md). To see them, on the trains, whose first page is calm; billing and
registration start at level 3 and have no further to fold, unless started with
`SIMBA_PAGE_MODEL=0`:

- **Fold.** On any step, do nothing for 15 seconds — or press "What are you
  doing?", or wander the pointer after 6 seconds. The step on screen folds to
  level 3 while you look at it, with "I'm showing less for a moment".
- **Return.** Answer the next two steps promptly (under 8 seconds each). The
  step after that arrives at level 2, with "I'm showing a bit more again". On
  billing, which has three steps, that is the ending.
- **Lock.** Pick a level with the dots and nothing moves it until you press
  "let it choose".

`SIMBA_ADAPT=0` turns all of it off and the level stays where the overlay
puts it. Every decision, with its inputs, who judged the page and what the
rules would have said, is written to `data/steps.jsonl` beside the telemetry
(`"kind": "decision"`); the file is not committed.

### mock is for the interface

`tools/mock_backend.py` plays the backend's whole side of the conversation
from a script, so the overlay can be worked on without a site, a model or a
browser to drive. It deliberately includes two things that are otherwise
awkward to see on demand (a real run folds too now, but only if you hesitate):

- **A mid-task level change.** Before step 3 it sends `load.updated` with
  level 3, and before the last step it sends level 2 again. The interface
  folds from one level to the other — the single most important animation in
  the project — and says so in a notice. Watch the middle of the run.
- **A skipped step.** It reports `step.failed` once, so the quiet notice for
  "I couldn't do that step, I'm carrying on" is visible without breaking a
  real page.

Measured, driving it: the level goes `2 → 3` at step 3, stays there, and
returns to `2` at the last step, with `I'm showing less for a moment` and
`I'm showing a bit more again` in between.

---

## Smoke test

Start everything, hold it, shut it down — no keypress, nothing left running.
Useful before a demo, and the only automated check that the launcher itself
works.

```powershell
.\run.ps1 mock -Seconds 20
```

```bash
SIMBA_RUN_SECONDS=20 ./run.sh mock
```

It passes if you see `stopped` and no port is still listening.

`DEMO.md` is the script for actually showing the thing to someone: five
minutes, the exact goals to type, and what to say when a part of it fails.

---

## When it does not work

### The window never appears, and the error names `main.ts`

Check `ELECTRON_RUN_AS_NODE`:

```powershell
$env:ELECTRON_RUN_AS_NODE
```
```bash
echo "$ELECTRON_RUN_AS_NODE"
```

If it is set, the Electron binary runs as **plain Node**: no window, no CDP,
and a `TypeError` pointing at our entry point rather than at the real cause.
Some editors set it in their integrated terminal, which is exactly where
someone is most likely to run this. Both launchers unset it for the processes
they start; if you are running the pieces by hand, unset it yourself.

The tell is `npx electron --version` printing a **Node** version (`v20.x`)
rather than an Electron one (`v32.x`).

### `port 8000 is already in use`

Another run is still up — often one whose terminal was closed rather than
Ctrl+C'd. The launcher refuses to start rather than silently attaching to
somebody else's host and then killing it on the way out.

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object OwningProcess
```
```bash
netstat -ano | grep LISTENING | grep :8000      # Windows
lsof -ti tcp:8000                               # macOS, Linux
```

### `the host (CDP 9222) did not come up`

Almost always the build failing. Scroll up: `tsc` and `vite` print above the
launcher's line. `cd frontend && npm run build` on its own shows it clearly.

### The backend starts but every step fails

Check what it thinks it is doing:

```bash
curl http://127.0.0.1:8000/
```

`browser` should read `electron` and `replica` should be the site you expect.
`browser: chromium` means it is driving its own headless browser and ignoring
the window entirely.

### `no backend/venv found`

The launcher falls back to `python` from PATH. Follow the setup in
`README.md`; the tests and Playwright both want that virtualenv.

### Nothing happens when you press Start

The overlay talks to `ws://127.0.0.1:8000/ws`. If the backend was started
after the window, the socket was refused once — press Start again, which
reconnects. Ctrl+Shift+D shows every message, and an empty log means nothing
ever arrived.

---

## Running the pieces by hand

The launcher is a convenience, not a requirement. `README.md` has the
individual commands, and you want them when you are changing one piece and
restarting it on its own.
