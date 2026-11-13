"""The installer, end to end, on this machine (2026-11-13).

    backend/venv/Scripts/python -m tools.evaluation.installed_app_run [--runs 3] [--keep]

What it does, and measures, in order:

  1. Installs `.scratch/installer-build/dist/SIMBA-Setup-*.exe` silently, per
     user (`/S`): **install seconds**.
  2. Launches the installed `SIMBA.exe` from the Start menu's target, then
     reads the CDP port Chromium chose from the profile's `DevToolsActivePort`
     and attaches: **cold start** = launch until the overlay's first screen (the
     welcome or the home screen) is visible.
  3. Gets past the first-time welcome by its own "skip" and "No, thank you"
     buttons, types "hello" and presses Enter: the bundled backend's greeting
     must arrive. No replica is running, so nothing else could answer.
  4. Asks the window to close (WM_CLOSE to the PID this started, the same as
     pressing X) and checks that no process is left running from the install
     folder, and that the backend's PID is gone.
  5. Repeats 2-4 `--runs` times (the first launch is the first-time one).
  6. Uninstalls silently: **uninstall seconds**, and checks again that nothing
     runs from the install folder, and whether the folder is gone.

Nothing is stopped by name or pattern. The check in 4 and 6 only *lists*
processes whose executable is under the install folder.

The person's profile folder (`%APPDATA%\\SIMBA`) is left as the app leaves it;
`--keep` also leaves SIMBA installed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from tools.evaluation.conditions import banner, record

REPO = Path(__file__).resolve().parents[2]
DIST = REPO / ".scratch" / "installer-build" / "dist"
OUT = REPO / ".scratch" / "installer-run.json"
INSTALL_DIR = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "SIMBA"
PROFILE = Path(os.environ["APPDATA"]) / "SIMBA"


def running_from(folder: Path) -> list[dict]:
    """Processes whose executable is under `folder`. Lists only; stops nothing."""
    script = (
        "Get-CimInstance Win32_Process | ? { $_.ExecutablePath -and "
        f"$_.ExecutablePath.StartsWith('{folder}', 'CurrentCultureIgnoreCase') }} | "
        "Select-Object ProcessId, Name | ConvertTo-Json -Compress"
    )
    out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                         capture_output=True, text=True, timeout=60).stdout.strip()
    if not out:
        return []
    found = json.loads(out)
    return found if isinstance(found, list) else [found]


def alive(pid: int) -> bool:
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True, timeout=30).stdout
    return f'"{pid}"' in out


def close_window(pid: int, limit_s: float = 60) -> bool:
    """WM_CLOSE to the main window of exactly this PID, as pressing X does.

    Retried until the window exists: the host shows it only once its backend
    answers, and a close sent before that reaches nothing (found 2026-11-13,
    when a first launch after installing took 20 s and the run left it open).
    """
    until = time.monotonic() + limit_s
    while time.monotonic() < until:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             f"$p = Get-Process -Id {pid} -ErrorAction SilentlyContinue; "
             "if (-not $p) { 'gone' } elseif ($p.CloseMainWindow()) { 'closed' } else { 'no window' }"],
            capture_output=True, text=True, timeout=30, check=False).stdout.strip()
        if out in ("gone", "closed"):
            return True
        time.sleep(0.5)
    return False


def install(setup: Path) -> float:
    started = time.monotonic()
    subprocess.run([str(setup), "/S"], check=True, timeout=600)
    seconds = time.monotonic() - started
    if not (INSTALL_DIR / "SIMBA.exe").exists():
        raise SystemExit(f"installed, but no {INSTALL_DIR / 'SIMBA.exe'}")
    return seconds


def uninstall() -> float:
    uninstaller = INSTALL_DIR / "Uninstall SIMBA.exe"
    started = time.monotonic()
    subprocess.run([str(uninstaller), "/S"], check=True, timeout=600)
    # The NSIS uninstaller copies itself to temp and returns at once; wait for
    # the install folder's executable to go.
    while (INSTALL_DIR / "SIMBA.exe").exists() and time.monotonic() - started < 300:
        time.sleep(0.2)
    return time.monotonic() - started


def one_launch(first: bool, extra: str = "") -> dict:
    port_file = PROFILE / "DevToolsActivePort"
    log = (REPO / ".scratch" / "installed-host.log").open("ab")
    launched_at = time.time()
    started = time.monotonic()
    host = subprocess.Popen([str(INSTALL_DIR / "SIMBA.exe")], stdout=log, stderr=log)
    result: dict = {"first_launch": first, "host_pid": host.pid}
    try:
        # Only a file written by this launch: the host removes the last one,
        # but a slow first start can be read before it has (2026-11-13).
        port = None
        while time.monotonic() - started < 90:
            try:
                if port_file.stat().st_mtime >= launched_at - 1:
                    text = port_file.read_text().split()
                    if text and int(text[0]) > 0:
                        port = int(text[0])
                        break
            except (OSError, ValueError):
                pass
            time.sleep(0.05)
        if port is None:
            raise RuntimeError("no DevToolsActivePort from this launch within 90s")
        result["cdp_port"] = port
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            overlay = None
            while overlay is None and time.monotonic() - started < 90:
                for page in browser.contexts[0].pages:
                    if page.url.startswith("file:") and "index.html" in page.url:
                        overlay = page
                time.sleep(0.05)
            if overlay is None:
                raise RuntimeError("no overlay page within 90s")
            ws = re.search(r"[?&]ws=([^&]+)", overlay.url)
            result["overlay_ws"] = ws.group(1) if ws else None
            first_screen = overlay.locator(
                "[data-testid=welcome], [data-testid=welcome-skip]"
            ).or_(overlay.get_by_role("textbox", name="What would you like me to do?"))
            first_screen.first.wait_for(timeout=90_000)
            result["cold_start_s"] = round(time.monotonic() - started, 2)

            box = overlay.get_by_role("textbox", name="What would you like me to do?")
            for _ in range(12):
                if box.is_visible():
                    break
                skip = overlay.get_by_test_id("welcome-skip")
                no = overlay.get_by_role("button", name="No, thank you")
                if no.is_visible():
                    no.click()
                elif skip.is_visible():
                    skip.click()
                overlay.wait_for_timeout(400)
            result["welcome_shown"] = overlay.get_by_test_id("welcome").count() > 0 or first
            asked = time.monotonic()
            box.fill("hello", timeout=15_000)
            overlay.keyboard.press("Enter")
            overlay.get_by_text("Here's what I can help with").wait_for(timeout=30_000)
            result["greeting_s"] = round(time.monotonic() - asked, 2)
            result["greeting"] = overlay.get_by_text("Here's what I can help with").first.inner_text()
            if extra == "second":
                # A second launch while this one is open: it should end at
                # once and leave one backend, not start a second.
                again = time.monotonic()
                second = subprocess.Popen([str(INSTALL_DIR / "SIMBA.exe")], stdout=log, stderr=log)
                try:
                    second.wait(timeout=30)
                    result["second_launch_exit_s"] = round(time.monotonic() - again, 2)
                    result["second_launch_code"] = second.returncode
                except subprocess.TimeoutExpired:
                    result["second_launch_exit_s"] = None
                result["backends_after_second_launch"] = len(
                    [p for p in running_from(INSTALL_DIR) if p["Name"] == "python.exe"])
            browser.close()
        backend_lines = [line for line in (PROFILE / "logs" / "backend-console.log")
                         .read_text(encoding="utf-8", errors="replace").splitlines()]
        result["backend_console_tail"] = backend_lines[-3:]
    finally:
        under = running_from(INSTALL_DIR)
        result["running_before_close"] = len(under)
        result["backend_pids"] = [p["ProcessId"] for p in under if p["Name"] == "python.exe"]
        if extra == "crash":
            # As a crash would: the host's own process ends with no quit, so
            # it stops nothing. Exactly the PID this started; not /T, which
            # would take the backend with it and prove nothing.
            subprocess.run(["taskkill", "/PID", str(host.pid), "/F"],
                           capture_output=True, timeout=30, check=False)
            host.wait(timeout=30)
            crashed = time.monotonic()
            while (any(alive(pid) for pid in result["backend_pids"])
                   and time.monotonic() - crashed < 20):
                time.sleep(0.2)
            result["backend_gone_after_crash_s"] = round(time.monotonic() - crashed, 2)
        else:
            result["closed_by_window"] = close_window(host.pid)
            try:
                host.wait(timeout=30)
            except subprocess.TimeoutExpired:
                result["host_did_not_exit"] = True
        time.sleep(1.0)
        result["running_after_close"] = running_from(INSTALL_DIR)
        result["backend_alive_after_close"] = [pid for pid in result["backend_pids"] if alive(pid)]
        log.close()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--keep", action="store_true", help="leave SIMBA installed")
    parser.add_argument("--reuse", action="store_true",
                        help="SIMBA is already installed from this installer: skip installing")
    options = parser.parse_args()
    print(banner())

    setups = sorted(DIST.glob("SIMBA-Setup-*.exe"))
    if not setups:
        raise SystemExit("no installer; run tools/build_installer.py first")
    setup = setups[-1]
    if INSTALL_DIR.exists() and not options.reuse:
        raise SystemExit(f"{INSTALL_DIR} already exists; uninstall first, or --reuse")
    profile_existed = PROFILE.exists()
    results: dict = {"installer": setup.name, "installer_bytes": setup.stat().st_size,
                     "profile_existed_before": profile_existed}
    results["install_s"] = None if options.reuse else round(install(setup), 2)
    results["installed_bytes"] = sum(f.stat().st_size for f in INSTALL_DIR.rglob("*")
                                     if f.is_file())
    print(json.dumps({k: results[k] for k in ("install_s", "installed_bytes")}))
    results["launches"] = []
    for run in range(options.runs):
        launch = one_launch(first=(run == 0 and not profile_existed))
        print(json.dumps(launch))
        results["launches"].append(launch)
    # The two cases added on 2026-11-13: a second launch, and a crashed host.
    for extra in ("second", "crash"):
        launch = one_launch(first=False, extra=extra)
        launch["case"] = extra
        print(json.dumps(launch))
        results["launches"].append(launch)
    if not options.keep:
        results["uninstall_s"] = round(uninstall(), 2)
        time.sleep(2)
        results["running_after_uninstall"] = running_from(INSTALL_DIR)
        results["install_dir_left"] = (sorted(str(p.relative_to(INSTALL_DIR))
                                              for p in INSTALL_DIR.rglob("*"))
                                       if INSTALL_DIR.exists() else None)
        results["profile_left"] = PROFILE.exists()
    print(json.dumps({k: v for k, v in results.items() if k != "launches"}))
    record(OUT, results)


if __name__ == "__main__":
    main()
