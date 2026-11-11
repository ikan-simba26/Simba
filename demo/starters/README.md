# Starter tasks

Two taught tasks, ready-made, saved as files. Each is a routine a helper
taught SIMBA once on our own copies, saved with the overlay's own "Save to a
file" — **made, not written by hand** (`python -m tools.starter_tasks make`,
2026-11-11).

| File | Tile | On | Asks the person | Reads |
|---|---|---|---|---|
| `my-bill.simba-routine.json` | My bill | the billing copy, `127.0.0.1:5100` | the reference number; cookies Yes or No | the amount due |
| `train-times.simba-routine.json` | Train times | the railways copy, `127.0.0.1:5200` | From and To, from the site's own lists; the day | the trains |

**Nothing loads them by itself.** A file becomes a tile only when someone adds
it: "Teach a task", "Add one from a file", choose the file. The screen does
not change when a file is added (it only says so when one cannot be used);
"Not now" goes back to the home screen, where the tile is. The home screen
needs room for it: a row holds three.

Every value the helper typed is asked for each time and kept nowhere in the
file: that is what "Save to a file" does with any routine. Both run on this
machine's copies only, so they need the stack up (`.\run.ps1 billing` or
`.\run.ps1 railways-local`).

**In the demo** `my-bill.simba-routine.json` is the fallback when teaching the
bill live goes wrong (`DEMO.md`, 4:40).

Checked by `python -m tools.starter_tasks check`: each file added and run from
its tile five times, 5 of 5 each on 2026-11-11 (EVALUATION.md, 2026-11-11c).
Made again the same way if the copies change.
