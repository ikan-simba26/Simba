# The recordings

Seven clips of SIMBA running, kept so a demo survives a dead website, a room
with no internet, or a host that will not start. `DEMO.md` says where each one
goes in the talk.

**The `.webm` files are not committed** — about 27 MB of video that would be
re-recorded rather than read. Record them the day before showing anything.

| Clip | Backend | Typed goal | What it shows | Size |
|---|---|---|---|---|
| `railways.webm` | real | `trains to Rawalpindi tomorrow` | **Our copy** of the train search. Asked where from (typed "Lahore", chose "Lahore Cantt" under the box), the journey read back, the search as a journey line, the trains as tickets with the offer to keep it and "Book one of these" beside "Back to start", then "See it on the real page". | 4.4 MB, 50s |
| `booking.webm` | real | `book a train from Lahore to Karachi tomorrow` | **A booking on our copy.** Which station at each end, the read-back, the checklist, which train, a name, a class, the **final screen** held, "Book it", then the ending in plain words — "Booked on the practice site." over the booking number and "This was a practice copy, so no real ticket was booked and no money was taken." — the site's own words, the booking number, train, date and seat, and the real page. | 5.9 MB, 59s |
| `billing.webm` | real | `What do I owe on my electricity bill?` | The billing replica, **opening at the simplest level, which the trained estimator chose from the page**. The reference asked for, cookies asked Yes or No, the lookup as a journey line, "Rs 14,382, due 15 September 2026", "Pay this bill" offered, and the real page. | 3.1 MB, 33s |
| `hello.webm` | real | `hello` | A greeting and the three things SIMBA can do. **No task starts.** | 0.7 MB, 6s |
| `fold.webm` | mock | `Register for CS-401` | The scripted run, including the fold from one detail level to the next. | 3.1 MB, 42s |
| `adapt.webm` | real | `What do I owe on my electricity bill?` | The same fold, **not scripted**: the reference is given, then the pointer drifts over the cookie question without pressing, and the provisional rules fold it to level 3 (5.3s in). No notice is shown on a task's first screen, so the drift is on the second. **Recorded with `SIMBA_PAGE_MODEL=0`, the rules judging the page**: the trained estimator starts billing at level 3, and nothing folds from there. Folded 5.4s in on 2026-11-11. | 3.1 MB, 46s |
| `teach.webm` | real | — ("Teach a task") | **A helper teaching the bill once** on the billing copy: the address typed, the bar across the top with the website under it, cookies accepted, the reference typed, "Ask each time", "Finish", the amount pointed at (an orange ring marks each press), the four moves read back, named "My bill" with the answer "Amount due", kept; then the person presses the new picture tile, gives the reference, says Yes to cookies, gets **14,382, Amount due**, and the real page with the amount ringed. | 6.9 MB, 79s |

All seven recorded 2026-11-11 at the machine's own 150%, on mains, on
`docs/demo-show-me-once`, with the picture tiles and the journey line as
they are now. `adapt` on a stack of its own (below), the rest on one
`railways-local` stack whose home screen started with no tiles of the
person's own.
No clip touches the live site.

## Recording them again

The real clips need the stack up; the mock one does not.

```powershell
.\run.ps1 railways-local                # terminal 1 — replicas, host, backend
python -m tools.record_demo railways booking billing hello fold teach   # terminal 2

python -m tools.record_demo mock        # only what needs no stack
python -m tools.record_demo hello fold  # or name the clips
```

**`adapt` needs its own stack**, started with `$env:SIMBA_PAGE_MODEL = "0"`, then
`python -m tools.record_demo adapt`. With the model on, billing starts at level
3, the clip has nothing to fold, and it is not the clip it says it is. A run
with no names records all seven, so `adapt` among them, whichever stack is up.

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

**`teach` shows the SIMBA window as a helper sees it.** While SIMBA watches,
the window is the overlay as a bar across the top and the site view below it
(`frontend/electron/main.ts`). The recording browser has only the overlay, so
the clip puts the site view's own picture under the bar, taken from the SIMBA
window's site view over CDP between the helper's presses, with a ring where
each press lands (`tools/starter_tasks.py`, `Mirror`). Nothing else on the
screen is captured. The helper's presses go to that site view, where the
backend watches them. It needs room for one tile on the home screen and no
"My bill" there already, and leaves "My bill" kept.

No clip touches the live site, since 2026-10-01: the railways clip is recorded
on our copy. After recording, the demo needs no site at all.

**Keep the SIMBA window un-minimised while recording.** The backend drives the
page inside it, and a minimised window is painted about once a second, so a
click waits for a page that never settles (2026-10-05: billing and adapt ended
"I'm stuck" that way, and were recorded again).
