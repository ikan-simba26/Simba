/**
 * SIMBA host: the window, and the two views inside it.
 *
 *   siteView  the real website. The backend attaches to this over CDP and
 *             drives it. The user never looks at it directly.
 *   overlay   the React app. Added second, filling the window's content
 *             area, so it covers the site view everywhere the window shows.
 *
 * The site view is deliberately left visible to Chromium and *covered*, not
 * hidden with setVisible(false). A view Chromium believes is invisible stops
 * repainting reliably and screenshots fail about half the time — measured in
 * spike/, recorded in DECISIONS.md. Covered: 20/20 captures. Hidden: 2/5.
 *
 * **Fitting the screen.** The window never exceeds the work area of the
 * display it opens on (the screen minus the taskbar), and is never larger
 * than 1280x800 of content. On a 1920x1080 laptop at 150% the work area is
 * 1280x672 in Windows' own units, so the content area is about 1266x608.
 *
 * The overlay lays out at the window's real size, at zoom 1, so its text is
 * the size it was designed at on every screen — body 23px — and the layout
 * adapts to the height instead (`short:` in `src/index.css`). It was zoomed to
 * fit for one day (2026-09-25), which drew 23px body text at about 17px on
 * that laptop.
 *
 * The site view is not touched: bounds 1280x800 at the window's origin, zoom
 * 1, so the page perception reads is 1280x800 CSS pixels whatever the screen.
 * Where the window is smaller, the rest of it lies past the window's right
 * and bottom edges — never past its origin (CLAUDE.md).
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

import {
  BaseWindow, WebContentsView, app, powerMonitor, screen, type Display, type Rectangle,
} from "electron";

const CDP_PORT = process.env.SIMBA_CDP_PORT ?? "9222";
const START_URL = process.env.SIMBA_START_URL ?? "about:blank";

/** Every scrollbar in the site view, gone and taking no room. See below. */
const HIDE_SCROLLBARS =
  "* { scrollbar-width: none !important; } ::-webkit-scrollbar { display: none !important; }";
const DEV_SERVER = process.env.SIMBA_DEV_SERVER;

// Must be set before the app is ready.
app.commandLine.appendSwitch("remote-debugging-port", CDP_PORT);

// Where this host keeps its storage — the person's profile among it — when a
// test or a walk says (2026-10-18). Unset, Electron's own place for the
// person's app data, as always. A test that needs a first open points it at
// an empty folder inside the repository, so it never clears the real
// person's profile, and never writes outside the checkout (CLAUDE.md).
if (process.env.SIMBA_USER_DATA) app.setPath("userData", process.env.SIMBA_USER_DATA);

// 1280x800 is frozen — the estimator measures text density per visible area,
// so the site view's viewport has to stay constant across runs. It is also
// the largest the window's content gets.
const VIEWPORT = { x: 0, y: 0, width: 1280, height: 800 };

const here = path.dirname(fileURLToPath(import.meta.url));
const OVERLAY_FILE = path.join(here, "..", "dist", "index.html");

// The app icon (2026-11-02): the .ico on Windows, which holds every size from
// 16 to 256 for the title bar and the taskbar; a PNG everywhere else, since
// Linux takes no .ico and macOS's dock wants a picture.
const BRAND = path.join(here, "..", "..", "assets", "brand");
const ICON_PNG = path.join(BRAND, "png", "simba-app-icon-512.png");
const ICON = process.platform === "win32" ? path.join(BRAND, "simba-app-icon.ico") : ICON_PNG;

// Windows groups a taskbar button by this id. Without one this is any other
// Electron app, under Electron's own id. Before the window, or it does not count.
if (process.platform === "win32") app.setAppUserModelId("simba");

/**
 * The largest content size, up to 1280x800, whose window — frame included —
 * fits inside `work`. Width and height are fitted separately: the overlay is
 * a column, and a window as wide as the screen allows is better than one
 * narrowed to keep a ratio nothing depends on.
 */
function fitted(work: Rectangle, frame: { width: number; height: number }) {
  return {
    width: Math.min(VIEWPORT.width, Math.floor(work.width - frame.width)),
    height: Math.min(VIEWPORT.height, Math.floor(work.height - frame.height)),
  };
}

app.whenReady().then(() => {
  if (process.platform === "darwin") app.dock.setIcon(ICON_PNG);
  const win = new BaseWindow({
    width: VIEWPORT.width,
    height: VIEWPORT.height,
    // The numbers above are the content area, not the frame round it: the
    // frame is measured once the window exists, and budgeted for below.
    useContentSize: true,
    // Resizing by hand would need the overlay to follow, and a window larger
    // than 1280x800 has nothing more to show. It is sized for the screen.
    resizable: false,
    maximizable: false,
    fullscreenable: false,
    // Electron's own File / Edit / View / Window / Help bar is not for the
    // person using SIMBA: it is clutter above the one thing on screen, and a
    // way into reloading the window and its developer tools. Hidden, not
    // removed, so Alt still shows it to a developer (2026-10-14).
    autoHideMenuBar: true,
    show: false,
    title: "simba",
    icon: ICON,
  });

  const siteView = new WebContentsView();
  win.contentView.addChildView(siteView);
  siteView.setBounds(VIEWPORT);
  // No scrollbars in the site view, so a page lays out at the full 1280px.
  // Headless Chromium hides them, and the host did not: a page that scrolled
  // laid out at 1263px here and 1280px there, and every inner scroll box lost
  // another 17px — so perception read a different page in each environment,
  // and a scrolling table's heading strip grew the spacer column
  // `content.py` has to discount (EVALUATION.md, 2026-09-17i, 2026-09-30e).
  // Nobody sees this view, so nothing is lost; it still scrolls. Put back on
  // every page, since a stylesheet lasts only as long as its document; the
  // user origin, so no page's own stylesheet can bring them back.
  siteView.webContents.on("dom-ready", () => {
    void siteView.webContents.insertCSS(HIDE_SCROLLBARS, { cssOrigin: "user" });
  });
  void siteView.webContents.loadURL(START_URL);

  const overlay = new WebContentsView();
  win.contentView.addChildView(overlay);

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
    fittedTo = display.id;

    // The window's whole content area, at zoom 1: the overlay's CSS size is
    // the window's size.
    overlay.setBounds({ x: 0, y: 0, width: size.width, height: size.height });

    // One line the evaluation reads (tools/evaluation/display_fit_run.py).
    console.log(`SIMBA fit ${JSON.stringify({
      display: { id: display.id, scale_factor: display.scaleFactor, bounds: display.bounds },
      work_area: work,
      frame,
      content: size,
      window: win.getBounds(),
    })}`);
  };

  // Zoom 1 on every load, for both views. Chromium remembers a zoom level per
  // origin in the profile, and the day the overlay was zoomed to fit
  // (2026-09-25) left `file://` at 0.757 on every machine that ran it: the
  // next build, which set no zoom at all, came up zoomed anyway. For the site
  // view a remembered zoom would be worse — it would change the CSS viewport
  // perception measures without anything saying so.
  for (const view of [siteView, overlay]) {
    view.webContents.on("did-finish-load", () => view.webContents.setZoomFactor(1));
  }

  fit(screen.getDisplayMatching(win.getBounds()));

  // Moved to another screen, or this one's scaling or resolution changed:
  // fit again. A move within one screen changes nothing.
  win.on("moved", () => {
    const display = screen.getDisplayMatching(win.getBounds());
    if (display.id !== fittedTo) fit(display);
  });
  screen.on("display-metrics-changed", () => fit(screen.getDisplayMatching(win.getBounds())));

  // Whether the window is there to be acted in, written into the overlay
  // page, where the backend reads it over CDP before every action
  // (`backend/orchestrator/browser.window_watch`). A minimised window paints
  // the site view about once a second and a click there waits for a page that
  // never settles; on 2026-10-05 that ended two demo clips "I'm stuck". The
  // pages themselves cannot be asked: both reported `visibilityState`
  // "visible" while the window was minimised. Only this process knows.
  const windowState = (): string =>
    win.isMinimized() ? "minimised" : win.isVisible() ? "shown" : "hidden";
  const tellOverlay = (): void => {
    overlay.webContents
      .executeJavaScript(`window.__simbaWindow = ${JSON.stringify(windowState())};`)
      .catch(() => undefined);
  };
  win.on("minimize", tellOverlay);
  win.on("restore", tellOverlay);
  win.on("hide", tellOverlay);
  win.on("show", tellOverlay);
  overlay.webContents.on("did-finish-load", tellOverlay);

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

  // Why the host went away, in its own log (2026-10-17). Once, the host fit
  // test found the host's pages closed after 22 minutes, and nothing said
  // whether a renderer died, the window was closed, or the app quit; each of
  // those, and the machine sleeping or locking, is now a line.
  const said = (what: string, detail: object = {}): void => {
    console.log(`SIMBA host ${what} ${JSON.stringify({ at: new Date().toISOString(), ...detail })}`);
  };
  for (const [name, view] of [["site", siteView], ["overlay", overlay]] as const) {
    view.webContents.on("render-process-gone", (_event, details) =>
      said("render-process-gone", { view: name, ...details }));
    view.webContents.on("unresponsive", () => said("unresponsive", { view: name }));
    view.webContents.on("responsive", () => said("responsive", { view: name }));
    view.webContents.on("destroyed", () => said("view destroyed", { view: name }));
  }
  app.on("child-process-gone", (_event, details) => said("child-process-gone", details));
  // Every press the overlay's guard logged, ignored or not
  // (`frontend/src/pressGuard.ts`), into this log too: a tile press that did
  // not register, seen once at 150%, said nothing anywhere the overlay's own
  // memory did not outlive (2026-10-17).
  overlay.webContents.on("console-message", (_event, _level, message) => {
    if (message.startsWith("[simba] press ")) console.log(`SIMBA overlay ${message.slice(8)}`);
  });
  for (const event of ["suspend", "resume", "lock-screen", "unlock-screen"] as const) {
    powerMonitor.on(event as "suspend", () => said(`power ${event}`));
  }
  win.on("close", () => said("window closing"));
  app.on("before-quit", () => said("quitting"));

  win.on("closed", () => {
    said("window closed");
    app.quit();
  });
});

app.on("window-all-closed", () => app.quit());
