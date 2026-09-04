# SIMBA spike: Electron + CDP + Playwright

Architecture test only. Proves that a Python process can drive a hidden
`WebContentsView` inside an Electron app over the Chrome DevTools Protocol.

- **Part A** (`main.js`) — Electron app. Shows a visible window with "SIMBA
  spike", and loads `https://example.com` into a hidden `WebContentsView`.
  Launched with remote debugging on port 9222.
- **Part B** (`cdp_client.py`) — standalone Python script. Connects to
  `localhost:9222` via Playwright, finds the `example.com` page, prints its
  title and link text, clicks the first link, and prints the resulting URL.

## Run order (two terminals)

### Terminal 1 — Electron app (Part A)

```bash
cd spike
npm install
npm start
```

Leave this running. A window titled with "SIMBA spike" should appear.

### Terminal 2 — Python CDP client (Part B)

```bash
cd spike
python -m venv venv
venv\Scripts\activate        # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python cdp_client.py
```

Expected output: the page title, one line per link's text, and the URL
after clicking the first link.

## Notes

- The site view is a full-size `WebContentsView` left **visible**, with the
  overlay view added after it at the same bounds so it covers the site view
  completely. Hiding the site view with `setVisible(false)` instead makes
  screenshots flaky (40% of captures time out); sizing it `0x0` or moving it
  outside the parent collapses its viewport to 0x0 and breaks clicking. See
  CLAUDE.md's Architecture constraints for the numbers.
- If `npm start` exits immediately with `Cannot read properties of undefined
  (reading 'commandLine')`, the `ELECTRON_RUN_AS_NODE` environment variable is
  set and is forcing Electron to run as plain Node. Unset it first:
  `env -u ELECTRON_RUN_AS_NODE npm start` (bash) or `Remove-Item Env:ELECTRON_RUN_AS_NODE`
  (PowerShell) before running.
