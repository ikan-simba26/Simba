"""A link that opens "in a new tab" is followed in the site view (2026-11-15).

Step E (EVALUATION.md, 2026-11-15) had SIMBA stop as "stuck" on Readings'
"order a book", 3 runs of 3: the search result is a `target=_blank` link, and
Electron opened it as a second window while the site view stayed on the results
page, so after the press SIMBA saw nothing change. `frontend/electron/main.ts`
now follows such a link, and `window.open`, in the site view itself. This
launches the real host on a page served from this machine and checks that no
second page appears and the site view ends on the link's address.

It opens a real window, so it runs only with `SIMBA_HOST_TESTS=1`, like the
other tests that need the host. It needs `npm run build` first.
"""

import http.server
import os
import shutil
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parent
REPO = FRONTEND.parent
CDP_PORT = "9341"

pytestmark = [
    pytest.mark.skipif(not os.environ.get("SIMBA_HOST_TESTS"),
                       reason="opens the Electron host (SIMBA_HOST_TESTS=1)"),
    pytest.mark.skipif(not (FRONTEND / "dist" / "index.html").exists(),
                       reason="frontend not built; run `npm run build` in frontend/"),
]

PAGES = {
    "/start": b"""<html><body>
      <a id="blank" href="/arrived" target="_blank">a link for a new tab</a>
      <button id="opens" onclick="window.open('/arrived', '_blank')">opens</button>
    </body></html>""",
    "/arrived": b"<html><body><h1 id='here'>arrived</h1></body></html>",
}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = PAGES.get(self.path.split("?")[0])
        self.send_response(200 if body else 404)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body or b"")

    def log_message(self, *args: object) -> None:  # silence
        pass


@pytest.fixture()
def host():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    user_data = REPO / ".scratch" / "user-data-new-tab"
    shutil.rmtree(user_data, ignore_errors=True)
    electron = FRONTEND / "node_modules" / ".bin" / ("electron.cmd" if os.name == "nt" else "electron")
    env = {**os.environ, "SIMBA_CDP_PORT": CDP_PORT, "SIMBA_START_URL": base + "/start",
           "SIMBA_USER_DATA": str(user_data)}
    env.pop("ELECTRON_RUN_AS_NODE", None)
    proc = subprocess.Popen([str(electron), "."], cwd=FRONTEND, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
                            shell=os.name == "nt")
    try:
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=1)
                break
            except OSError:
                time.sleep(0.5)
        else:
            pytest.fail("the host did not open CDP")
        yield base
    finally:
        # By the PID started here, with its own children, never by name.
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        else:
            proc.terminate()
        proc.wait(timeout=20)
        server.shutdown()


def web_pages(browser) -> list:
    return [p for c in browser.contexts for p in c.pages if p.url.startswith("http")]


@pytest.mark.parametrize("opener", ["#blank", "#opens"])
def test_a_new_tab_link_is_followed_in_the_site_view(host: str, opener: str) -> None:
    import concurrent.futures

    from playwright.sync_api import sync_playwright

    def run() -> tuple[int, str]:
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
            try:
                deadline = time.time() + 20
                while time.time() < deadline and not web_pages(browser):
                    time.sleep(0.3)
                site = web_pages(browser)[0]
                site.wait_for_selector(opener)
                site.click(opener)
                deadline = time.time() + 15
                while time.time() < deadline and not site.url.endswith("/arrived"):
                    time.sleep(0.3)
                time.sleep(1.0)  # a second window, if one were coming, is here by now
                return len(web_pages(browser)), site.url
            finally:
                browser.close()

    # Its own thread: a sync Playwright session elsewhere in the suite holds this one.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        count, url = pool.submit(run).result()

    assert url == host + "/arrived", url
    assert count == 1, f"a second page opened: {count} pages"
