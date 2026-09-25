# The recordings

Five clips of SIMBA running, kept so a demo survives a dead website, a room
with no internet, or a host that will not start. `DEMO.md` says where each one
goes in the talk.

**The `.webm` files are not committed** — about 12 MB of video that would be
re-recorded rather than read. Record them the day before showing anything.

| Clip | Backend | Typed goal | What it shows | Size |
|---|---|---|---|---|
| `railways.webm` | real | `Show me trains from Lahore to Karachi` | The live site. Five steps: departure, destination, open the calendar, set the date, search. Ends on the train and the journey time. | 4.9 MB, 80s |
| `billing.webm` | real | `What do I owe on my electricity bill?` | The billing replica. Three steps: accept cookies, check the bill, show the breakdown. Ends on 14,382 and 15-09-2026. | 2.2 MB, 24s |
| `hello.webm` | real | `hello` | A greeting and the three things SIMBA can do. **No task starts** — this is the clip for "it only does what you ask". | 0.6 MB, 8s |
| `fold.webm` | mock | `Register for CS-401` | The scripted run, including the fold from one detail level to the next. | 2.7 MB, 30s |
| `adapt.webm` | real | `What do I owe on my electricity bill?` | The same fold, **not scripted**: the pointer drifts over step 1 without pressing anything, the backend's provisional rules read the overlay's telemetry and fold the step to level 3 while it is on screen ("I'm showing less for a moment", about 21s in). Steps 2 and 3 are answered promptly, and the ending says "I'm showing a bit more again". | 2.1 MB, 32s |

Recorded 2026-09-23, at the pace an audience can read, not the pace the system
can go; `adapt.webm` on 2026-09-25.

`python -m tools.record_demo` with no names now records five clips, and one
of them is the live railways run. To remake only the new one:
`python -m tools.record_demo adapt`.

## Recording them again

The four real clips need the stack up; the mock one does not.

```powershell
.\run.ps1 billing                       # terminal 1 — replicas, host, backend
python -m tools.record_demo             # terminal 2 — all five clips

python -m tools.record_demo mock        # only what needs no stack
python -m tools.record_demo hello fold  # or name the clips
```

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

The railways clip touches the live site once, when it is recorded. That single
recording is the point: after it, the demo needs no site at all.
