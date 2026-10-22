"""After "Forget me and start again", nothing from before is ever shown
(2026-10-21).

End to end: the real backend and the bill replica, the real overlay. A person
named Ayesha runs a bill through the overlay and keeps it as a tile; the home
screen then greets her, offers the bill as a goal asked before and as her
tile. She forgets herself. The home screen holds nothing from that run — no
name, no tile, no goal, no reference, not even the bill's last four digits —
and still holds nothing on the next open, from a backend that was told once.
The replay store still holds the run: the evaluation reads it.
"""

import os
import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Page

from backend.orchestrator.billing_plan import REFERENCE
from backend.orchestrator.test_billing import REPO_ROOT, _wait_for, billing_replica  # noqa: F401
from backend.orchestrator.tiles import TileStore
from frontend.test_home import browser  # noqa: F401 - fixture
from frontend.test_terminal_states import overlay  # noqa: F401 - fixture

PORT = 8037
NAME = "Ayesha"
GOAL = f"check my electricity bill {REFERENCE}"
BOX = "What would you like me to do?"

pytestmark = pytest.mark.skipif(not TileStore(Path("unused")).available,
                                reason="tiles need the operating system's encryption")


@pytest.fixture
def backend(billing_replica: str, tmp_path: Path) -> Iterator[dict]:  # noqa: F811
    paths = {"traces": tmp_path / "traces.db", "tiles": tmp_path / "tiles.json",
             "vault": tmp_path / "vault.json", "log": tmp_path / "backend.log"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.orchestrator.app:app", "--port", str(PORT)],
        cwd=REPO_ROOT,
        env={**os.environ, "SIMBA_ROUTER": "keywords", "SIMBA_USE_HARDCODED_PLAN": "1",
             "SIMBA_TRACE_MEMORY": "1", "SIMBA_BILLING_URL": billing_replica,
             "SIMBA_RECORD_STEPS": "0", "SIMBA_TRACE_DB": str(paths["traces"]),
             "SIMBA_TILES": str(paths["tiles"]), "SIMBA_VAULT": str(paths["vault"]),
             "SIMBA_LOG_FILE": str(paths["log"])},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        _wait_for(f"http://127.0.0.1:{PORT}")
        yield paths
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def open_home(browser, overlay: str) -> Page:  # noqa: F811
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    # The welcome on, as in the real app; Ayesha already answered it.
    context.add_init_script(
        "window.__simbaWelcome = true; window.__simbaSettleMs = 0;"
        "if (!sessionStorage.getItem('seeded')) {"
        f" localStorage.setItem('simba.profile', JSON.stringify({{name: '{NAME}',"
        " readAloud: true, askEach: false, welcomed: true}));"
        " sessionStorage.setItem('seeded', '1'); }")
    page = context.new_page()
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{PORT}/ws")
    page.get_by_test_id("greeting").wait_for(timeout=15000)
    return page


def run_the_bill(page: Page) -> None:
    """Through the overlay as a person would: ask, agree, keep it, go back."""
    page.get_by_role("textbox", name=BOX).fill(GOAL)
    page.get_by_role("button", name="Start", exact=True).click()
    keep = page.get_by_test_id("keep-it")
    for _ in range(10):
        try:
            keep.wait_for(timeout=4000)
            break
        except Exception:  # noqa: BLE001 - a step is waiting for its answer
            step = page.get_by_test_id("step-shell")
            if step.count():
                step.get_by_role("button").filter(has_not_text="aloud").first.click()
    keep.click()
    page.get_by_test_id("kept").wait_for(timeout=5000)
    page.get_by_test_id("onward").get_by_role("button").first.click()
    page.get_by_test_id("own-tile").first.wait_for(timeout=15000)


def home_text(page: Page) -> str:
    return page.locator("body").inner_text()


def forget(page: Page) -> None:
    page.get_by_test_id("change-settings").click()
    page.get_by_test_id("forget").click()
    page.get_by_test_id("forget-yes").click()
    for _ in range(4):
        page.get_by_test_id("welcome-skip").click()
        page.wait_for_timeout(250)
    page.get_by_test_id("can-help").wait_for(timeout=15000)
    page.wait_for_timeout(500)


def nothing_from_the_run(page: Page) -> None:
    text = home_text(page)
    for left_behind in (NAME, REFERENCE, REFERENCE[-4:], "My bill"):
        assert left_behind not in text, (left_behind, text)
    assert page.get_by_test_id("remembered").count() == 0
    assert page.get_by_test_id("own-tile").count() == 0
    # Not in a tooltip, either.
    assert REFERENCE not in page.content()


def test_after_a_bill_run_and_a_reset_the_home_screen_shows_nothing_from_it(
    browser, overlay: str, backend: dict  # noqa: F811
) -> None:
    page = open_home(browser, overlay)
    run_the_bill(page)
    # The control: before the reset, the run is all over the home screen.
    before = home_text(page)
    assert NAME in before and "My bill" in before, before
    assert page.get_by_test_id("remembered").count() == 1
    assert REFERENCE[-4:] in before

    forget(page)
    nothing_from_the_run(page)

    # Opened again, from the same backend: still nothing.
    page.reload()
    page.get_by_test_id("can-help").wait_for(timeout=15000)
    page.wait_for_timeout(500)
    nothing_from_the_run(page)
    assert page.evaluate("() => localStorage.getItem('simba.forgetting')") is None

    # And the run is still there for replay and the evaluation.
    with sqlite3.connect(backend["traces"]) as db:
        goals = [goal for (goal,) in db.execute("SELECT goal FROM traces")]
    assert len(goals) == 1 and REFERENCE in goals[0]
    assert not backend["tiles"].exists()
    page.context.close()


def test_a_reset_made_with_no_backend_still_holds_when_it_comes_back(
    browser, overlay: str, backend: dict  # noqa: F811
) -> None:
    """Forgotten while the overlay was pointed at nothing: the next open, with
    the backend there, shows nothing from before and tells the backend."""
    page = open_home(browser, overlay)
    run_the_bill(page)
    page.goto(f"{overlay}?ws=ws://127.0.0.1:1/ws")
    page.get_by_test_id("greeting").wait_for(timeout=15000)
    forget(page)
    assert page.evaluate("() => localStorage.getItem('simba.forgetting')") == "1"

    page.goto(f"{overlay}?ws=ws://127.0.0.1:{PORT}/ws")
    page.get_by_test_id("can-help").wait_for(timeout=15000)
    page.wait_for_timeout(800)
    nothing_from_the_run(page)
    assert page.evaluate("() => localStorage.getItem('simba.forgetting')") is None
    assert not backend["tiles"].exists()
    page.context.close()
