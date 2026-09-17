# SIMBA frontend

The Electron window and the overlay the person actually sees. Electron +
React + TypeScript + Vite, Tailwind, Zustand, and Framer Motion for the
transitions.

Until 2026-09-17 this file described the frontend as "a functional harness,
not the interface", with no detail levels, no trust panel and Framer Motion
unused. That stopped being true around 2026-09-06; all three exist.

## The window

A `BaseWindow` (`electron/main.ts`) holding two `WebContentsView`s at
identical 1280x800 bounds:

1. **the site view** — the real website, driven by the backend over CDP
2. **the overlay** — this React app, added second so it covers the site view

The site view stays visible to Chromium and is *covered*, never hidden with
`setVisible(false)`. See DECISIONS.md for the measurements behind that.

## The overlay

One column, one thing at a time (`src/App.tsx`):

- **Home** — a greeting, up to three goals asked for before (from
  `history.offered`), and a text box behind "Ask for something new".
- **Working** — "Let me open that for you." then "Give me a moment.", with the
  four states (thinking, acting, waiting, stuck) also shown without words
  (`components/StateSignal.tsx`).
- **A step** — at one of three detail levels, folding between them
  (`levels.ts`, `components/StepShell.tsx`), with anything found so far,
  the person's own level control, and "What are you doing?", which opens a
  screenshot of the real page with the target ringed
  (`components/TrustPanel.tsx`).
- **Five endings** — found an answer, done, failed, stuck, and stopped because
  the person pressed stop. Every one offers "Do something else".
- **Notices** — a level change the person did not make, and a step that
  failed and was carried past.

Every word the overlay writes is in `src/copy.ts`. The development view — the
raw message log — is behind Ctrl+Shift+D.

How it fits with the backend: `../ARCHITECTURE.md`. What is open:
`../STATUS.md`, Interface.

## Run

The usual way is the launcher from the repo root — `.\run.ps1` or `./run.sh`
— which starts a replica, this window and the backend in order. See
`../RUNNING.md`. On its own:

```bash
cd frontend
npm install
SIMBA_START_URL=http://127.0.0.1:5100/ npm start
```

| Command | What it does |
|---|---|
| `npm start` | Type-checks, builds, and opens the Electron window |
| `npm run build` | Type-checks and builds into `dist/` without opening anything |
| `npm run start:built` | Opens the window on the existing build |
| `npm run dev` | Serves the overlay alone on a Vite dev server, in an ordinary browser, with no site view and no CDP |

Environment for the window:

| Variable | Meaning |
|---|---|
| `SIMBA_CDP_PORT` | Remote debugging port the backend attaches to (9222) |
| `SIMBA_START_URL` | What the site view loads. Also how the backend tells the two views apart — **set it** |
| `SIMBA_DEV_SERVER` | Load the overlay from a Vite dev server instead of the build, for HMR |

The overlay connects to `ws://127.0.0.1:8000/ws`; `?ws=` on its URL
overrides that, which is how the rendered tests point it at a fake backend.

## Without a backend

```bash
python -m uvicorn tools.mock_backend:app --port 8000
```

Then Start in the window, or `.\run.ps1 mock`. The mock plays a full scripted
task including a level change and a skipped step. It does not send
`page.preview`, `help.requested`, `task.failed` or `error`.

## Tests

Run from the repo root with `python -m pytest`; they are Python, driving a
real browser.

| File | What it checks |
|---|---|
| `test_copy.py` | `copy.ts` compiled and read; no component writes its own words; the backend's words obey the same rules |
| `test_terminal_states.py` | Builds the overlay from source and renders every ending, including after a step, pressing every button |
| `test_levels.py` | Rendered heights per level. Measures `dist/`, so run `npm run build` first |

## Notes

- The log is cleared per *connection*, not per task, because `seq` is a
  per-connection counter and keeping entries across a reconnect shows two
  runs interleaved with duplicate numbers.
- The backend closes the socket when a task ends, so `Start` reconnects when
  the socket is dead rather than failing.
