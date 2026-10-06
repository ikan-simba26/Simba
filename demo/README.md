# The recordings

Five clips of SIMBA running, kept so a demo survives a dead website, a room
with no internet, or a host that will not start. `DEMO.md` says where each one
goes in the talk.

**The `.webm` files are not committed** — about 12 MB of video that would be
re-recorded rather than read. Record them the day before showing anything.

| Clip | Backend | Typed goal | What it shows | Size |
|---|---|---|---|---|
| `railways.webm` | real | `trains to Rawalpindi tomorrow` | **Our copy** of the train search. Asked where from, typed "Lahore", chose "Lahore Cantt", five steps. Ends on the closing screen: the sentence, one line per train with its journey time, the two buttons side by side. | 4.9 MB, 61s |
| `billing.webm` | real | `What do I owe on my electricity bill?` | The billing replica. Asked for the reference, three steps: accept cookies, check the bill, show the breakdown. Ends on 14,382 and 15-09-2026 under "Your bill is 14,382, and it is due on 15-09-2026." | 3.1 MB, 43s |
| `hello.webm` | real | `hello` | A greeting and the three things SIMBA can do. **No task starts** — this is the clip for "it only does what you ask". | 0.6 MB, 8s |
| `fold.webm` | mock | `Register for CS-401` | The scripted run, including the fold from one detail level to the next. | 3.1 MB, 34s |
| `adapt.webm` | real | `What do I owe on my electricity bill 04141234567890?` | The same fold, **not scripted**: the pointer drifts over step 1 without pressing anything, and the backend's provisional rules fold the step to level 3 while it is on screen (7.2s in). Steps 2 and 3 are answered promptly, and the ending returns. | 3.5 MB, 41s |

Recorded 2026-10-05 with the stack started by `.\run.ps1 railways-local`: no
clip touches the live site. The recorder asks the backend where a train goal
runs and refuses to record railways anywhere but our copy.

## Recording them again

The four real clips need the stack up; the mock one does not.

```powershell
.\run.ps1 railways-local                # terminal 1 — replicas, host, backend
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

No clip touches the live site, since 2026-10-01: the railways clip is recorded
on our copy. After recording, the demo needs no site at all.

**Keep the SIMBA window un-minimised while recording.** The backend drives the
page inside it, and a minimised window is painted about once a second, so a
click waits for a page that never settles (2026-10-05: billing and adapt ended
"I'm stuck" that way, and were recorded again).
