const { app, BaseWindow, WebContentsView } = require('electron');

// Must be set before the app is ready.
app.commandLine.appendSwitch('remote-debugging-port', '9222');

// 1280x800 is frozen: the estimator measures text density per visible area,
// so the viewport must stay constant across runs.
const VIEWPORT = { x: 0, y: 0, width: 1280, height: 800 };

app.whenReady().then(() => {
  const win = new BaseWindow({ width: VIEWPORT.width, height: VIEWPORT.height });

  // The site view is visible to Chromium — it has a real viewport and keeps
  // compositing, so screenshots stay reliable — but the user never sees it,
  // because the overlay is added afterwards and covers it completely.
  const siteView = new WebContentsView();
  win.contentView.addChildView(siteView);
  siteView.setBounds(VIEWPORT);
  siteView.webContents.loadURL('https://example.com');

  const overlay = new WebContentsView();
  win.contentView.addChildView(overlay);
  overlay.setBounds(VIEWPORT);
  overlay.webContents.loadURL(
    'data:text/html,<html><body style="background:%23fff"><h1>SIMBA spike</h1></body></html>'
  );

  win.on('closed', () => app.quit());
});

app.on('window-all-closed', () => app.quit());
