/**
 * SIMBA host: the window, and the two views inside it.
 *
 *   siteView  the real website. The backend attaches to this over CDP and
 *             drives it. The user never looks at it directly.
 *   overlay   the React app. Added second, so it covers the site view
 *             everywhere the window shows.
 *
 * The site view is deliberately left visible to Chromium and *covered*, not
 * hidden with setVisible(false). A view Chromium believes is invisible stops
 * repainting reliably and screenshots fail about half the time — measured in
 * spike/, recorded in DECISIONS.md. Covered: 20/20 captures. Hidden: 2/5.
 *
 * **Fitting the screen.** The window never exceeds the work area of the
 * display it opens on (the screen minus the taskbar). On a 1920x1080 laptop at
 * 150% that area is 1280x672 in Windows' own units, and a 1280x800 window cut
 * the home screen's text box off. So the window's content shrinks by one
 * factor, `scale`, and the overlay is zoomed by the same factor: it still lays
 * out at 1280x800 CSS pixels, exactly as designed, and is drawn smaller. The
 * site view is not touched — its bounds stay 1280x800 at zoom 1, so the page
 * perception reads is 1280x800 CSS pixels whatever the screen. Where the
 * window is smaller than that, the rest of the site view lies past the
 * window's edge, covered by nothing because nothing can see it.
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

import { BaseWindow, WebContentsView, app, screen, type Display, type Rectangle } from "electron";

const CDP_PORT = process.env.SIMBA_CDP_PORT ?? "9222";
const START_URL = process.env.SIMBA_START_URL ?? "about:blank";
const DEV_SERVER = process.env.SIMBA_DEV_SERVER;

// Must be set before the app is ready.
app.commandLine.appendSwitch("remote-debugging-port", CDP_PORT);

// 1280x800 is frozen — the estimator measures text density per visible area,
// so the site view's viewport has to stay constant across runs. It is also
// the size the overlay is designed at, and the size it lays out at on every
// screen: only how large it is drawn changes.
const VIEWPORT = { x: 0, y: 0, width: 1280, height: 800 };

const here = path.dirname(fileURLToPath(import.meta.url));
const OVERLAY_FILE = path.join(here, "..", "dist", "index.html");

/**
 * The largest content size, in the design's 1280x800 proportions, whose
 * window — frame included — fits inside `work`. Never larger than 1:1.
 */
function fitted(work: Rectangle, frame: { width: number; height: number }) {
  const scale = Math.min(
    1,
    (work.width - frame.width) / VIEWPORT.width,
    (work.height - frame.height) / VIEWPORT.height,
  );
  // Whole pixels, and the zoom taken from them, so the overlay's CSS size
  // comes back to 1280x800 rather than a pixel either side.
  const width = Math.floor(VIEWPORT.width * scale);
  const height = Math.floor(VIEWPORT.height * scale);
  return { width, height, scale: Math.min(width / VIEWPORT.width, height / VIEWPORT.height) };
}

app.whenReady().then(() => {
  const win = new BaseWindow({
    width: VIEWPORT.width,
    height: VIEWPORT.height,
    // The numbers above are the content area, not the frame round it: the
    // frame is measured once the window exists, and budgeted for below.
    useContentSize: true,
    // Resizing by hand would need the views to follow, and a larger window
    // than 1:1 has nothing to show. The window is sized for the screen.
    resizable: false,
    maximizable: false,
    fullscreenable: false,
    show: false,
    title: "SIMBA",
  });

  const siteView = new WebContentsView();
  win.contentView.addChildView(siteView);
  siteView.setBounds(VIEWPORT);
  void siteView.webContents.loadURL(START_URL);

  const overlay = new WebContentsView();
  win.contentView.addChildView(overlay);

  let scale = 1;
  let fittedTo: number | null = null;

  const fit = (display: Display) => {
    const work = display.workArea;
    // The frame is measured, not assumed, and the result is checked where the
    // window finally stands: at 125% and 150% the first fit came out one
    // pixel taller than the work area, from rounding, and any overshoot is
    // taken off and the fit done again. Three passes is more than it has
    // ever needed.
    const outer = win.getBounds();
    const inner = win.getContentBounds();
    const frame = { width: outer.width - inner.width, height: outer.height - inner.height };
    let size = fitted(work, frame);
    for (let pass = 0; pass < 3; pass += 1) {
      win.setContentSize(size.width, size.height);
      // Centred in the work area, so no edge sits under the taskbar or off
      // the screen, whichever side the taskbar is on.
      const sized = win.getBounds();
      win.setPosition(
        Math.round(work.x + (work.width - sized.width) / 2),
        Math.max(work.y, Math.round(work.y + (work.height - sized.height) / 2)),
      );
      // Checked after the move, not before: at a fractional scale the same
      // physical window rounds to a different size in DIPs once it has moved,
      // and at 150% that was the pixel that put it one past the work area.
      const now = win.getBounds();
      const over = {
        width: now.x + now.width - (work.x + work.width),
        height: now.y + now.height - (work.y + work.height),
      };
      if (over.width <= 0 && over.height <= 0) break;
      // Still over: add the overshoot to the frame's budget and fit again.
      frame.width += Math.max(0, over.width);
      frame.height += Math.max(0, over.height);
      size = fitted(work, frame);
    }
    scale = size.scale;
    fittedTo = display.id;

    overlay.setBounds({ x: 0, y: 0, width: size.width, height: size.height });
    overlay.webContents.setZoomFactor(scale);

    // One line the evaluation reads (tools/evaluation/display_fit_run.py).
    console.log(`SIMBA fit ${JSON.stringify({
      display: { id: display.id, scale_factor: display.scaleFactor, bounds: display.bounds },
      work_area: work,
      frame,
      content: size,
      window: win.getBounds(),
    })}`);
  };

  // Zoom is kept per page load, so it is set again whenever the overlay
  // loads — a reload from the development view included.
  overlay.webContents.on("did-finish-load", () => overlay.webContents.setZoomFactor(scale));

  fit(screen.getDisplayMatching(win.getBounds()));

  // Moved to another screen, or this one's scaling or resolution changed:
  // fit again. A move within one screen changes nothing.
  win.on("moved", () => {
    const display = screen.getDisplayMatching(win.getBounds());
    if (display.id !== fittedTo) fit(display);
  });
  screen.on("display-metrics-changed", () => fit(screen.getDisplayMatching(win.getBounds())));

  if (DEV_SERVER) {
    void overlay.webContents.loadURL(DEV_SERVER);
  } else {
    void overlay.webContents.loadFile(OVERLAY_FILE);
  }
  win.show();

  // The backend picks the site view out of the host's CDP targets. Say which
  // is which out loud so a mismatch is diagnosable from the host's own log.
  console.log(
    `SIMBA host ready — CDP ${CDP_PORT}; site view ${START_URL}; ` +
      `overlay ${DEV_SERVER ?? OVERLAY_FILE}`,
  );

  win.on("closed", () => app.quit());
});

app.on("window-all-closed", () => app.quit());
