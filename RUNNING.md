# Running SIMBA

One command per flow. `run.ps1` on Windows PowerShell, `run.sh` anywhere with
bash — they do the same thing and print the same lines.

```powershell
.\run.ps1                # registration replica
.\run.ps1 billing
.\run.ps1 railways
.\run.ps1 mock
```

```bash
./run.sh                 # registration replica
./run.sh billing
./run.sh railways
./run.sh mock
```

Ctrl+C stops everything it started. Nothing is left listening.

**Everything defaults to the hardcoded plan**, which spends no API quota and
does the same thing every time — so a run that misbehaves is the system's
fault rather than the model's. For the LLM planner, set
`SIMBA_USE_HARDCODED_PLAN=0` first, and read `STATUS.md` on quota before you
do: it is about 20 requests a day and one run costs 6–7.

---

## What you see

Starting `./run.sh registration` prints, in order:

```
==> starting the registration replica on :5000
==> the registration replica is up
==> starting the Electron host (builds first, ~10s)
==> the host (CDP 9222) is up
==> starting the backend on :8000 — flow=registration, planner=hardcoded (no API quota spent)
==> the backend is up

==> ready — type a goal in the SIMBA window and press Start
==> Ctrl+Shift+D in the window shows the message log
==> Ctrl+C here stops everything
```

Vite's build output and each server's own logging appear in between. The
`==>` lines are the launcher; everything else belongs to the thing starting.

A SIMBA window opens. Type a goal, press Start, and answer each step. On
Ctrl+C:

```
==> stopping
==> stopped
```

The order is not arbitrary. The backend attaches to the host over CDP, so the
host has to exist first; the host loads the replica into its hidden view, so
the replica has to exist before that.

---

## The flows

| | What it starts | What it shows |
|---|---|---|
| `registration` | replica :5000, host, backend | The whole stack on a page we wrote. Three steps, a modal to dismiss, ends on a confirmation screen. The thing to run first. |
| `billing` | replica :5100, host, backend | A second site with different chrome — a cookie bar, breadcrumbs, an accordion, and an amount that only `content.py` can read. |
| `railways` | host, backend | **A live public website.** Read-only: fills a search and reads the timetable. Please treat it as somebody's public service — a handful of runs, not a benchmark. |
| `mock` | mock backend :8000, host | The overlay alone, driven by a script. No replica, no browser driving, nothing real. |

### mock is for the interface

`tools/mock_backend.py` plays the backend's whole side of the conversation
from a script, so the overlay can be worked on without a site, a model or a
browser to drive. It deliberately includes the two things that are otherwise
awkward to see on demand:

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
