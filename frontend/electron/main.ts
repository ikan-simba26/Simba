/**
 * SIMBA host: the window, and the two views inside it.
 *
 *   siteView  the real website. The backend attaches to this over CDP and
 *             drives it. The user never looks at it directly.
 *   overlay   the React app. Added second, at identical bounds, so it covers
 *             the site view completely.
 *
 * The site view is deliberately left visible to Chromium and *covered*, not
 * hidden with setVisible(false). A view Chromium believes is invisible stops
 * repainting reliably and screenshots fail about half the time — measured in
 * spike/, recorded in DECISIONS.md. Covered: 20/20 captures. Hidden: 2/5.
 *
 * Environment:
 *   SIMBA_CDP_PORT     remote debugging port the backend attaches to (9222)
 *   SIMBA_START_URL    what the site view loads at boot. Also how the backend
 *                      tells the site view apart from the overlay.
 *   SIMBA_DEV_SERVER   load the overlay from a Vite dev server instead of the
 *                      built files, for HMR while working on the UI.
 */

import { fileURLToPath } from "node:url";
import path from "node:path";

import { BaseWindow, WebContentsView, app } from "electron";

const CDP_PORT = process.env.SIMBA_CDP_PORT ?? "9222";
const START_URL = process.env.SIMBA_START_URL ?? "about:blank";
const DEV_SERVER = process.env.SIMBA_DEV_SERVER;

// Must be set before the app is ready.
app.commandLine.appendSwitch("remote-debugging-port", CDP_PORT);

// 1280x800 is frozen — the estimator measures text density per visible area,
// so the viewport has to stay constant across runs.
const VIEWPORT = { x: 0, y: 0, width: 1280, height: 800 };

const here = path.dirname(fileURLToPath(import.meta.url));
const OVERLAY_FILE = path.join(here, "..", "dist", "index.html");

app.whenReady().then(() => {
  const win = new BaseWindow({
    width: VIEWPORT.width,
    height: VIEWPORT.height,
    title: "SIMBA",
  });

  const siteView = new WebContentsView();
  win.contentView.addChildView(siteView);
  siteView.setBounds(VIEWPORT);
  void siteView.webContents.loadURL(START_URL);

  const overlay = new WebContentsView();
  win.contentView.addChildView(overlay);
  overlay.setBounds(VIEWPORT);

  if (DEV_SERVER) {
    void overlay.webContents.loadURL(DEV_SERVER);
  } else {
    void overlay.webContents.loadFile(OVERLAY_FILE);
  }

  // The backend picks the site view out of the host's CDP targets. Say which
  // is which out loud so a mismatch is diagnosable from the host's own log.
  console.log(
    `SIMBA host ready — CDP ${CDP_PORT}; site view ${START_URL}; ` +
      `overlay ${DEV_SERVER ?? OVERLAY_FILE}`,
  );

  win.on("closed", () => app.quit());
});

app.on("window-all-closed", () => app.quit());
