"""Exit when the host that started this backend has gone (2026-11-13).

The installed app's host starts the backend itself and stops it by PID when it
quits (`frontend/electron/backend.ts`). A host that crashes, or is ended from
Task Manager, never gets to: the backend would keep running, holding its port
and a Python process nobody can see, until the person signed out.

So the host passes its own PID as `SIMBA_HOST_PID`, and this waits on that
process and ends the backend when it ends. On Windows the process is opened
once, at start, and waited on — a handle, not a PID looked up again later, so a
new process that happens to be given the same PID cannot keep the backend
alive. Elsewhere it is polled every two seconds.

Unset (development, `run.ps1`, every test), nothing happens.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from collections.abc import Callable

log = logging.getLogger("simba.host_watch")

ENV = "SIMBA_HOST_PID"

_SYNCHRONIZE = 0x00100000
_INFINITE = 0xFFFFFFFF


def _wait_windows(pid: int) -> bool:
    """Block until `pid` ends. False if it could not be opened at all."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel32.OpenProcess(_SYNCHRONIZE, False, pid)
    if not handle:
        return False
    try:
        kernel32.WaitForSingleObject(handle, _INFINITE)
    finally:
        kernel32.CloseHandle(handle)
    return True


def _wait_posix(pid: int) -> bool:
    while True:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            pass  # there, but someone else's
        time.sleep(2.0)


def wait_for(pid: int) -> bool:
    """Block until process `pid` ends. False if it was never there to wait on."""
    return _wait_windows(pid) if sys.platform == "win32" else _wait_posix(pid)


def watch(pid: int, on_gone: Callable[[], None] | None = None) -> threading.Thread:
    """End this process (or call `on_gone`) once `pid` has ended."""

    def run() -> None:
        found = wait_for(pid)
        log.info("host %d %s; the backend ends with it", pid,
                 "has gone" if found else "was not running")
        if on_gone is not None:
            on_gone()
        else:
            # Not sys.exit: this is a thread, and the server's own shutdown
            # waits on connections that no longer have anyone at the other end.
            os._exit(0)

    thread = threading.Thread(target=run, name="host-watch", daemon=True)
    thread.start()
    return thread


def start_from_environment() -> threading.Thread | None:
    """Watch `SIMBA_HOST_PID` if it is set to a PID; otherwise do nothing."""
    raw = os.environ.get(ENV, "").strip()
    if not raw:
        return None
    try:
        pid = int(raw)
    except ValueError:
        log.warning("%s=%r is not a PID; not watching", ENV, raw)
        return None
    log.info("watching host %d", pid)
    return watch(pid)
