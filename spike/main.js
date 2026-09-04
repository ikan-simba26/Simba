const { app, BrowserWindow, WebContentsView } = require('electron');

// Must be set before the app is ready.
app.commandLine.appendSwitch('remote-debugging-port', '9222');

app.whenReady().then(() => {
  const win = new BrowserWindow({ width: 1280, height: 800 });
  win.loadURL('data:text/html,<html><body><h1>SIMBA spike</h1></body></html>');

  // Hidden view: same bounds as the window (so it has a real viewport and
  // is click-able), but setVisible(false) keeps it off screen. 1280x800 is
  // frozen — the estimator measures text density per visible area, so the
  // viewport must stay constant across runs.
  const hiddenView = new WebContentsView();
  win.contentView.addChildView(hiddenView);
  hiddenView.setBounds({ x: 0, y: 0, width: 1280, height: 800 });
  hiddenView.setVisible(false);
  hiddenView.webContents.loadURL('https://example.com');

  win.on('closed', () => app.quit());
});

app.on('window-all-closed', () => app.quit());
