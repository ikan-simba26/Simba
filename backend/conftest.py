"""The replica servers, shared by every backend test that needs one.

They live in a conftest rather than in one test module so that two modules
asking for a replica get the *same* one. A second copy would be two servers on
one port: whichever started first would hold 5001 and the other would fail, in
a way that reads as a broken test rather than as a duplicated fixture.

**Only the servers live here.** The sync-API browser stays in
`perception/conftest.py`, one directory down, and this is not tidiness. A live
`sync_playwright` session breaks `asyncio.run` in the same thread — "asyncio.run()
cannot be called from a running event loop" — so a session-scoped sync browser
visible to `orchestrator/`, whose tests are all `asyncio.run`, fails 54 of them
the moment a module that sorts earlier opens it. Measured on 2026-09-19, by
moving it up here and running the suite.
"""

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

# Every app a test starts routes goals by keywords unless the test says
# otherwise. The default is one call to the configured model, and the key in
# `.env` is real: without this, every websocket test would spend quota on
# classifying a goal it already knows the answer to (2026-09-21).
os.environ.setdefault("SIMBA_ROUTER", "keywords")

# And every app a test starts writes nothing to `data/steps.jsonl`, which is
# the person's real rows. Before 2026-09-25 a test run wrote nothing there
# anyway — tests send no telemetry — but every run now writes a decision per
# step, and the suite would have filled the file with its own.
os.environ.setdefault("SIMBA_RECORD_STEPS", "0")

# And no test reads or writes the person's saved passwords. A password saved
# for the registration replica would change what its sign-in step shows, and a
# test that pressed "save" would write to `data/vault.json`. Tests that need a
# vault make one of their own.
os.environ.setdefault(
    "SIMBA_VAULT", str(Path(__file__).resolve().parents[1] / ".scratch" / "vault-tests.json"))

REPLICAS = Path(__file__).resolve().parents[1] / "replicas"
BASE_URL = "http://127.0.0.1:5001"
BILLING_URL = "http://127.0.0.1:5002"


def _serve(name: str, port: int, url: str) -> Iterator[str]:
    proc = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=REPLICAS / name,
        env={**os.environ, "PORT": str(port)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for(url)
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture(scope="session")
def replica() -> Iterator[str]:
    yield from _serve("registration", 5001, BASE_URL)


@pytest.fixture(scope="session")
def billing() -> Iterator[str]:
    """The second replica. Its own port, so both can be up at once."""
    yield from _serve("billing", 5002, BILLING_URL)


def _wait_for(url: str, timeout_s: float = 20.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.2)
    raise RuntimeError(f"replica did not start at {url}")
