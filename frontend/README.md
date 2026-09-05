# SIMBA frontend

Electron + React + TypeScript + Vite, Tailwind, Zustand. Framer Motion is
installed but deliberately unused — the animation work comes with the design.

**This is a functional harness, not the interface.** It exists to prove the
contract round-trips and to show every message type the backend actually
sends. No styling beyond default Tailwind, no detail levels, no trust panel.

## The window

A `BaseWindow` holding two `WebContentsView`s at identical 1280x800 bounds:

1. **the site view** — the real website, driven by the backend over CDP
2. **the overlay** — this React app, added second so it covers the site view

The site view stays visible to Chromium and is *covered*, never hidden with
`setVisible(false)`. See DECISIONS.md for the measurements behind that.

## Run

```bash
cd frontend
npm install
SIMBA_START_URL=http://127.0.0.1:5100/ npm start
```

`npm start` builds and launches. Environment:

| Variable | Meaning |
|---|---|
| `SIMBA_CDP_PORT` | Remote debugging port the backend attaches to (9222) |
| `SIMBA_START_URL` | What the site view loads. Also how the backend tells the two views apart — **set it** |
| `SIMBA_DEV_SERVER` | Load the overlay from a Vite dev server instead of the build, for HMR |

## Verifying it without a backend

```bash
python -m uvicorn tools.mock_backend:app --port 8000
```

Then Start in the UI. The mock plays a full scripted task. It does not send
`page.preview`, `help.requested`, `task.failed` or `error` — those were
verified separately.

## Notes

- The log is cleared per *connection*, not per task, because `seq` is a
  per-connection counter and keeping entries across a reconnect shows two
  runs interleaved with duplicate numbers.
- The backend closes the socket after `task.completed`, so `Start` reconnects
  when the socket is dead rather than failing.
