"""Build SIMBA's Windows installer: `SIMBA-Setup-<version>.exe` (2026-11-13).

    backend/venv/Scripts/python tools/build_installer.py

Everything it downloads or writes stays inside the repository, under
`.scratch/installer-build/` (ignored by git), never the home folder or the
system temp (CLAUDE.md):

    .scratch/installer-build/
        downloads/          the embeddable Python zip, pip's and
                            electron-builder's caches
        stage/backend/      what goes into the install as `resources/backend`
            python/         the Windows embeddable Python 3.12
            site/           the packages of backend/requirements.txt
            app/            backend/, shared/ and data/estimator.json
        dist/               the installer, and electron-builder's unpacked app
        build.json          what this build measured

The steps, in order:

  1. Check the build machine: Windows, Python 3.12, npm on PATH.
  2. Download the official embeddable Python (python.org) once, and check it
     against the SHA-256 pinned below. A different file stops the build.
  3. Unpack it fresh into stage/backend/python and widen its `._pth` to the
     site/ and app/ folders beside it. (An embeddable Python reads
     sys.path from that file only; PYTHONPATH is ignored.)
  4. Install backend/requirements.txt into site/ with *this*
     Python's pip (`--target`, wheels only, for CPython 3.12 win_amd64). The
     embeddable Python has no pip of its own, and no PyInstaller is involved.
  5. Copy the backend's code: every .py under backend/ and shared/ except
     tests and conftest, and data/estimator.json, the one data file the
     backend reads at run time.
  6. Byte-compile all of it with the bundled Python itself, so a first launch
     does not spend time on it and an install folder that is not writable
     (an all-users install under Program Files) costs nothing. Then check no
     path inside the bundle is longer than PATH_BUDGET (see there).
  7. Smoke-test the bundle: start uvicorn from it on a free port with
     `SIMBA_BROWSER=electron`, ask `/`, stop exactly that PID.
  8. `npm run build` in frontend/, then electron-builder's NSIS target, with
     its cache under downloads/.

Options:
    --skip-python    reuse stage/backend as it is (steps 2-7), for a quick
                     rebuild after an Electron-only change
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORK = REPO / ".scratch" / "installer-build"
DOWNLOADS = WORK / "downloads"
STAGE = WORK / "stage" / "backend"
PYTHON_DIR = STAGE / "python"
SITE_DIR = STAGE / "site"
APP_DIR = STAGE / "app"
DIST = WORK / "dist"
FRONTEND = REPO / "frontend"

#: The last 3.12 release with Windows binaries; 3.12.11 onwards are
#: source-only security releases. The backend's pins were tested on 3.12.3
#: (backend/requirements.txt); every wheel is for the cp312 ABI, which any
#: 3.12.x shares.
PYTHON_VERSION = "3.12.10"
EMBED_NAME = f"python-{PYTHON_VERSION}-embed-amd64.zip"
EMBED_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/{EMBED_NAME}"
#: Checked on first download (2026-11-13) against the MD5 python.org lists
#: for this file on its release page; see DECISIONS.md.
EMBED_SHA256 = "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3"

#: What goes on the embeddable Python's sys.path, relative to python.exe.
PTH_LINES = [
    "python312.zip",
    ".",
    r"..\site",
    r"..\app",
    "import site",
]


#: The longest path allowed inside the bundle, counted from the install
#: folder (`resources\backend\...`). NSIS and Python's imports both stop at
#: Windows' 260 characters, so this leaves 260 - 1 - PATH_BUDGET for the
#: install folder itself: 89 with this budget, against 42 for the default
#: per-user folder of a 8-letter account name. The anthropic package's longest
#: compiled file came to 176 with site-packages under python\Lib\ (2026-11-13);
#: that is why the packages are in a short `site\` instead.
PATH_BUDGET = 170


def say(message: str) -> None:
    print(f"==> {message}", flush=True)


def die(message: str) -> None:
    print(f"!! {message}", file=sys.stderr, flush=True)
    raise SystemExit(1)


# --- 1. the build machine ---------------------------------------------------


def check_machine() -> str:
    if sys.platform != "win32":
        die("the installer is built on Windows")
    if sys.version_info[:2] != (3, 12):
        die(f"build with Python 3.12 (this is {sys.version.split()[0]}); "
            "pip installs wheels for the bundled 3.12")
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        die("npm is not on PATH")
    return npm


# --- 2. the embeddable Python ----------------------------------------------


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch_python() -> Path:
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    target = DOWNLOADS / EMBED_NAME
    if not target.exists():
        say(f"downloading {EMBED_URL}")
        partial = target.with_suffix(".part")
        with urllib.request.urlopen(EMBED_URL, timeout=120) as response, partial.open("wb") as out:
            shutil.copyfileobj(response, out)
        partial.replace(target)
    found = sha256(target)
    if found != EMBED_SHA256:
        die(f"{target.name} has SHA-256 {found}, expected {EMBED_SHA256}. "
            "Delete it and download again; if it still differs, stop and find out why.")
    say(f"{target.name} matches its pinned SHA-256")
    return target


# --- 3. unpack and widen sys.path -------------------------------------------


def long_path(path: Path) -> str:
    """`path` in the form Windows accepts past 260 characters."""
    return "\\\\?\\" + str(path.resolve())


def remove(path: Path) -> None:
    if path.exists():
        shutil.rmtree(long_path(path))


def unpack_python(archive: Path) -> None:
    remove(STAGE)
    PYTHON_DIR.mkdir(parents=True)
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(PYTHON_DIR)
    pth = PYTHON_DIR / "python312._pth"
    if not pth.exists():
        die(f"{pth.name} is missing from {archive.name}")
    pth.write_text("\n".join(PTH_LINES) + "\n", encoding="ascii")
    say(f"unpacked Python {PYTHON_VERSION} into {PYTHON_DIR.relative_to(REPO)}")


# --- 4. the backend's packages ------------------------------------------------


def install_packages() -> None:
    site = SITE_DIR
    site.mkdir(parents=True, exist_ok=True)
    say("installing backend/requirements.txt into the bundled Python")
    subprocess.run(
        [sys.executable, "-m", "pip", "install",
         "--target", str(site),
         "--requirement", str(REPO / "backend" / "requirements.txt"),
         "--only-binary=:all:", "--platform", "win_amd64",
         "--python-version", "3.12", "--implementation", "cp",
         "--cache-dir", str(DOWNLOADS / "pip-cache"),
         "--no-compile", "--no-warn-script-location", "--disable-pip-version-check"],
        check=True,
    )
    # Console launchers pip wrote for *this* machine's Python; nothing uses them.
    shutil.rmtree(site / "bin", ignore_errors=True)


# --- 5. the backend's code --------------------------------------------------


def wanted(path: Path) -> bool:
    name = path.name
    return (path.suffix == ".py" and not name.startswith("test_")
            and name != "conftest.py" and "__pycache__" not in path.parts
            and "venv" not in path.parts)


def copy_code() -> int:
    copied = 0
    for package in ("backend", "shared"):
        for source in sorted((REPO / package).rglob("*.py")):
            relative = source.relative_to(REPO)
            if not wanted(relative):
                continue
            target = APP_DIR / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied += 1
    for data in ("estimator.json",):
        target = APP_DIR / "data" / data
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / "data" / data, target)
        copied += 1
    say(f"copied {copied} files of backend code and data")
    return copied


# --- 6. byte-compile ----------------------------------------------------------


def compile_all() -> None:
    say("byte-compiling with the bundled Python")
    subprocess.run(
        [str(PYTHON_DIR / "python.exe"), "-m", "compileall", "-q", "-j", "0",
         str(APP_DIR), str(SITE_DIR)],
        check=True, cwd=STAGE,
    )


def check_path_lengths() -> int:
    """The longest path in the bundle, counted as installed. Over budget stops."""
    longest, worst = 0, ""
    for root, _dirs, files in os.walk(long_path(STAGE)):
        for name in files:
            relative = Path(root[len(long_path(STAGE)):].lstrip("\\")) / name
            installed = len(str(Path("resources") / "backend" / relative))
            if installed > longest:
                longest, worst = installed, str(relative)
    if longest > PATH_BUDGET:
        die(f"{worst} is {longest} characters from the install folder, over the "
            f"budget of {PATH_BUDGET}; see PATH_BUDGET")
    say(f"longest path in the bundle: {longest} characters (budget {PATH_BUDGET})")
    return longest


# --- 7. smoke test -------------------------------------------------------------


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def smoke_test() -> float:
    """Start the bundled backend, ask `/`, stop it. Returns seconds to answer."""
    port = free_port()
    scratch = WORK / "smoke"
    shutil.rmtree(scratch, ignore_errors=True)
    scratch.mkdir(parents=True)
    env = {
        **os.environ,
        "SIMBA_BROWSER": "electron",
        "SIMBA_CDP_URL": f"http://127.0.0.1:{free_port()}",
        "SIMBA_TILES": str(scratch / "tiles.json"),
        "SIMBA_VAULT": str(scratch / "vault.json"),
        "SIMBA_ROUTINES": str(scratch / "routines.json"),
        "SIMBA_TRACE_DB": str(scratch / "traces.db"),
        "SIMBA_STEPS": str(scratch / "steps.jsonl"),
        "SIMBA_LOG_FILE": str(scratch / "backend.log"),
        "SIMBA_LLM_LOG_DIR": str(scratch),
    }
    started = time.monotonic()
    process = subprocess.Popen(
        [str(PYTHON_DIR / "python.exe"), "-m", "uvicorn", "backend.orchestrator.app:app",
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=APP_DIR, env=env,
        stdout=(scratch / "console.log").open("wb"), stderr=subprocess.STDOUT,
    )
    try:
        while time.monotonic() - started < 90:
            if process.poll() is not None:
                die(f"the bundled backend exited with {process.returncode}; "
                    f"see {(scratch / 'console.log').relative_to(REPO)}")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as answer:
                    body = answer.read().decode("utf-8", "replace")
                seconds = time.monotonic() - started
                say(f"the bundled backend answered in {seconds:.1f}s: {body[:120]}")
                return seconds
            except OSError:
                time.sleep(0.25)
        die("the bundled backend did not answer within 90s")
    finally:
        # Exactly the process started above, and what it started.
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       capture_output=True, check=False)
        process.wait(timeout=30)
    return 0.0


# --- 8. the installer ------------------------------------------------------


def folder_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def build_installer(npm: str) -> Path:
    env = {
        **os.environ,
        "ELECTRON_BUILDER_CACHE": str(DOWNLOADS / "electron-builder-cache"),
        "npm_config_cache": str(DOWNLOADS / "npm-cache"),
        # electron-builder stages helpers (elevate.exe) in the system temp
        # otherwise; found on the first build, 2026-11-13.
        "TEMP": str(WORK / "tmp"),
        "TMP": str(WORK / "tmp"),
    }
    (WORK / "tmp").mkdir(parents=True, exist_ok=True)
    # Electron reads this and runs as plain Node; electron-builder's own
    # child processes must not inherit it (run.ps1 says the same).
    env.pop("ELECTRON_RUN_AS_NODE", None)
    say("npm run build")
    subprocess.run([npm, "run", "build"], cwd=FRONTEND, env=env, check=True)
    remove(DIST)
    say("electron-builder --win nsis")
    builder = FRONTEND / "node_modules" / ".bin" / "electron-builder.cmd"
    subprocess.run([str(builder), "--win", "nsis", "--x64", "--publish", "never"],
                   cwd=FRONTEND, env=env, check=True)
    setups = sorted(DIST.glob("SIMBA-Setup-*.exe"))
    if not setups:
        die(f"electron-builder wrote no SIMBA-Setup-*.exe into {DIST}")
    return setups[-1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--skip-python", action="store_true",
                        help="reuse stage/backend as it is")
    options = parser.parse_args()

    started = time.monotonic()
    npm = check_machine()
    report: dict[str, object] = {"python": PYTHON_VERSION}
    if options.skip_python:
        if not (PYTHON_DIR / "python.exe").exists():
            die("--skip-python, but there is no staged Python yet")
        say("reusing the staged backend")
    else:
        unpack_python(fetch_python())
        install_packages()
        report["code_files"] = copy_code()
        compile_all()
        report["longest_path"] = check_path_lengths()
        report["smoke_seconds"] = round(smoke_test(), 2)
    report["stage_bytes"] = folder_size(STAGE)

    setup = build_installer(npm)
    report["installer"] = setup.name
    report["installer_bytes"] = setup.stat().st_size
    unpacked = DIST / "win-unpacked"
    if unpacked.exists():
        report["unpacked_bytes"] = folder_size(unpacked)
    report["build_seconds"] = round(time.monotonic() - started, 1)
    (WORK / "build.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    say(f"{setup.relative_to(REPO)}: {setup.stat().st_size / 1e6:.1f} MB")
    say(json.dumps(report))


if __name__ == "__main__":
    main()
