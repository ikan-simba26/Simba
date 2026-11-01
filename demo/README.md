# The recordings

Six clips of SIMBA running, kept so a demo survives a dead website, a room
with no internet, or a host that will not start. `DEMO.md` says where each one
goes in the talk.

**The `.webm` files are not committed** — about 12 MB of video that would be
re-recorded rather than read. Record them the day before showing anything.

| Clip | Backend | Typed goal | What it shows | Size |
|---|---|---|---|---|
| `railways.webm` | real | `trains to Rawalpindi tomorrow` | **Our copy** of the train search. Asked where from (typed "Lahore", chose "Lahore Cantt"), the journey read back, the search as a checklist, the trains as tickets with "Book one of these" beside "Back to start", then "See it on the real page". | 3.4 MB, 35s |
| `booking.webm` | real | `book a train from Lahore to Karachi tomorrow` | **A booking on our copy.** Which station at each end, the read-back, the checklist, which train, a name, a class, the **final screen** held, "Book it", then the ending in plain words — "Booked on the practice site." over the booking number and "This was a practice copy, so no real ticket was booked and no money was taken." — the site's own words, the booking number, train, date and seat, and the real page. Re-recorded 2026-10-17 for that wording. | 5.3 MB, 56s |
| `billing.webm` | real | `What do I owe on my electricity bill?` | The billing replica, **opening at the simplest level, which the trained estimator chose from the page**. The reference asked for, cookies asked Yes or No, the lookup as a checklist, "Rs 14,382, due 15 September 2026", "Pay this bill" offered, and the real page. Re-recorded 2026-11-01. | 3.0 MB, 29s |
| `hello.webm` | real | `hello` | A greeting and the three things SIMBA can do. **No task starts.** | 0.7 MB, 8s |
| `fold.webm` | mock | `Register for CS-401` | The scripted run, including the fold from one detail level to the next. | 3.1 MB, 43s |
| `adapt.webm` | real | `What do I owe on my electricity bill?` | The same fold, **not scripted**: the reference is given, then the pointer drifts over the cookie question without pressing, and the provisional rules fold it to level 3 (5.3s in). No notice is shown on a task's first screen, so the drift is on the second. **Recorded with `SIMBA_PAGE_MODEL=0`, the rules judging the page**: the trained estimator starts billing at level 3, and nothing folds from there. Re-recorded 2026-11-01. | 2.6 MB, 32s |

Billing and adapt recorded 2026-11-01 at the machine's own 150%, on mains. The
rest recorded 2026-10-16/17 with the stack's host forced to 100% (railways at
150%: at 100% the still of the site view used for "See it on the real page"
failed to come, the known 100% capture problem, EVALUATION.md 2026-09-27 —
fixed on 2026-10-17, so a re-recording can be made at 100%). `booking.webm`
re-recorded 2026-10-17 at the machine's own scale, on mains. Which clips
show wording since changed: none now — the bill, trains and hello clips end
on screens that did not change, and `fold.webm` is the scripted mock, whose
run has no final screen and ends "That's done." as a task the site did not
confirm does.
No clip touches the live site.

## Recording them again

The four real clips need the stack up; the mock one does not.

```powershell
.\run.ps1 railways-local                # terminal 1 — replicas, host, backend
python -m tools.record_demo railways booking billing hello fold   # terminal 2

python -m tools.record_demo mock        # only what needs no stack
python -m tools.record_demo hello fold  # or name the clips
```

**`adapt` needs its own stack**, started with `$env:SIMBA_PAGE_MODEL = "0"`, then
`python -m tools.record_demo adapt`. With the model on, billing starts at level
3, the clip has nothing to fold, and it is not the clip it says it is. A run
with no names records all six, so `adapt` among them, whichever stack is up.

Each clip prints its file, its size, its wall clock, and the buttons it
actually pressed — so one that stopped early is visible without opening it.
A line ending in `ended`, `greeted` or `declined` finished; anything else did
not.

## What is in the picture

The overlay, built from source, talking to the real backend over the
websocket — the same conversation the Electron window has, rendered in a
browser that can record, which the Electron window cannot. The frame is the
overlay's own 1280x800 and never the desktop (`CLAUDE.md`, "Tooling
boundaries").

No clip touches the live site, since 2026-10-01: the railways clip is recorded
on our copy. After recording, the demo needs no site at all.

**Keep the SIMBA window un-minimised while recording.** The backend drives the
page inside it, and a minimised window is painted about once a second, so a
click waits for a page that never settles (2026-10-05: billing and adapt ended
"I'm stuck" that way, and were recorded again).
