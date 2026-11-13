"""The backend ends when its host has gone (`host_watch.py`, 2026-11-13)."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from backend.orchestrator import host_watch

REPO = Path(__file__).resolve().parents[2]

#: Stands in for the backend: watches the PID it is given, then idles.
WATCHER = """
import sys, time
from backend.orchestrator import host_watch
host_watch.start_from_environment()
print("watching", flush=True)
time.sleep(120)
"""


def _sleeper() -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])


def test_the_backend_ends_when_its_host_is_killed() -> None:
    host = _sleeper()
    backend = subprocess.Popen(
        [sys.executable, "-c", WATCHER], cwd=REPO, stdout=subprocess.PIPE, text=True,
        env={**os.environ, host_watch.ENV: str(host.pid)},
    )
    try:
        assert backend.stdout is not None
        assert backend.stdout.readline().strip() == "watching"
        time.sleep(0.5)
        assert backend.poll() is None, "ended before its host did"
        started = time.monotonic()
        host.kill()  # as a crash would: no clean quit, nothing told
        backend.wait(timeout=10)
        assert time.monotonic() - started < 5
        assert backend.returncode == 0
    finally:
        for process in (host, backend):
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)


def test_a_host_that_was_never_there_ends_it_at_once() -> None:
    gone = _sleeper()
    gone.kill()
    gone.wait(timeout=10)
    ended = threading.Event()
    host_watch.watch(gone.pid, on_gone=ended.set)
    assert ended.wait(timeout=5)


def test_unset_nothing_is_watched(monkeypatch) -> None:
    monkeypatch.delenv(host_watch.ENV, raising=False)
    assert host_watch.start_from_environment() is None
    monkeypatch.setenv(host_watch.ENV, "not-a-pid")
    assert host_watch.start_from_environment() is None
