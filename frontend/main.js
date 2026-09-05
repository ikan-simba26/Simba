/**
 * SIMBA host shell.
 *
 * Owns the two views the architecture is built on:
 *
 *   siteView  the real website, driven by the backend over CDP
 *   overlay   what the user actually sees, drawn on top of it
 *
 * The site view is deliberately left visible to Chromium and covered by the
 * overlay rather than hidden with setVisible(false). Chromium stops reliably
 * repainting a view it thinks is invisible, which makes screenshots fail
 * about half the time — measured in spike/, recorded in CLAUDE.md and
 * DECISIONS.md. Covered gets 20/20 captures; hidden gets 2/5.
 *
 * This is a host shell, not the overlay UI. It exists to prove the pipe
 * between Electron and the backend. The real interface is frontend/ work.
 *
 * Environment:
 *   SIMBA_CDP_PORT   remote debugging port the backend attaches to (9222)
 *   SIMBA_START_URL  what the site view loads at boot, so the backend can
 *                    recognise which of the two views is the site
 */

const { app, BaseWindow, WebContentsView } = require('electron');

const CDP_PORT = process.env.SIMBA_CDP_PORT || '9222';
const START_URL = process.env.SIMBA_START_URL || 'about:blank';

// Must be set before the app is ready.
app.commandLine.appendSwitch('remote-debugging-port', CDP_PORT);

// 1280x800 is frozen — the estimator measures text density per visible area,
// so the viewport must stay constant across runs.
const VIEWPORT = { x: 0, y: 0, width: 1280, height: 800 };

const OVERLAY_HTML = `data:text/html,
<html><body style="margin:0;background:%23f7f7f8;font-family:system-ui,sans-serif">
<div style="padding:40px">
  <div style="font-size:13px;letter-spacing:2px;color:%238a8a94">SIMBA</div>
  <h1 style="font-size:26px;margin:8px 0 4px">Working on it</h1>
  <p style="color:%2355555f;font-size:15px;margin:0">
    The site is loaded behind this panel. The backend is driving it.
  </p>
</div>
</body></html>`.replace(/\n/g, '');

app.whenReady().then(() => {
  const win = new BaseWindow({ width: VIEWPORT.width, height: VIEWPORT.height });

  const siteView = new WebContentsView();
  win.contentView.addChildView(siteView);
  siteView.setBounds(VIEWPORT);
  siteView.webContents.loadURL(START_URL);

  // Added second, so it renders on top and covers the site view completely.
  const overlay = new WebContentsView();
  win.contentView.addChildView(overlay);
  overlay.setBounds(VIEWPORT);
  overlay.webContents.loadURL(OVERLAY_HTML);

  console.log(`SIMBA host ready: CDP on ${CDP_PORT}, site view at ${START_URL}`);

  win.on('closed', () => app.quit());
});

app.on('window-all-closed', () => app.quit());
