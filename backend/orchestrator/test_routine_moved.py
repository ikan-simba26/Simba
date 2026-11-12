"""One taught routine, run on another website (2026-11-13, the advisor's
direction: "one taught routine may move from one website to another").

A sister site is one laid out the same way at another address — one
electricity company's bill page and another's. Here, a second copy of our
billing site on its own port: the bill taught on one runs on the other, every
move found again by role and label and checked, and the answer read there.
And the list offers it on the sister site, marked with where it was taught.
"""

import os
import subprocess
import sys
from dataclasses import dataclass

import pytest

from backend.orchestrator import voice
from backend.orchestrator.catalogue import Catalogue, Site, Task, offered
from backend.orchestrator.routines import Answer, Routine, Step, moved_to
from backend.orchestrator.test_billing import REPO_ROOT, _wait_for
from backend.orchestrator.test_billing import billing_replica  # noqa: F401
from backend.orchestrator.test_routine_run import REFERENCE, go, the_bill

SISTER_PORT = 5134


@pytest.fixture(scope="module")
def sister_billing():
    """Another billing site, laid out the same, at another address."""
    proc = subprocess.Popen(
        [sys.executable, "app.py"], cwd=REPO_ROOT / "replicas" / "billing",
        env={**os.environ, "PORT": str(SISTER_PORT)},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{SISTER_PORT}"
    try:
        _wait_for(url)
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


# --- moved_to --------------------------------------------------------------------


def taught(start: str, *paths: str | None) -> Routine:
    return Routine(id="r", label="My bill", start=start,
                   steps=tuple(Step("click", "button", f"B{n}", expect_url=path)
                               for n, path in enumerate(paths)),
                   answer=Answer("Amount due", "P/WITHIN"))


def test_the_start_and_paths_under_it_move_and_nothing_else():
    routine = taught("https://bill.pitc.com.pk/iescobill", "/iescobill/general",
                     "/iescobill", "/other", None)
    moved = moved_to(routine, "https://bill.pitc.com.pk/lescobill")
    assert moved.start == "https://bill.pitc.com.pk/lescobill"
    assert [s.expect_url for s in moved.steps] == ["/lescobill/general", "/lescobill",
                                                     "/other", None]
    # Everything else about each move is as the helper showed it.
    assert [(s.kind, s.role, s.label) for s in moved.steps] == \
        [(s.kind, s.role, s.label) for s in routine.steps]
    assert (moved.id, moved.label, moved.answer) == (routine.id, routine.label, routine.answer)


def test_a_routine_from_the_root_keeps_its_paths():
    routine = taught("http://127.0.0.1:5100/", "/bill")
    assert moved_to(routine, "http://127.0.0.1:5134/").steps[0].expect_url == "/bill"


def test_a_path_that_only_begins_alike_is_not_moved():
    routine = taught("https://x.example/bill", "/billing/help")
    assert moved_to(routine, "https://y.example/pay").steps[0].expect_url == "/billing/help"


# --- run on the sister site ---------------------------------------------------------


def test_the_bill_taught_on_one_site_runs_on_its_sister(billing_replica, sister_billing):  # noqa: F811
    routine = moved_to(the_bill(billing_replica), sister_billing)
    done = go(routine, [("confirm", {"value1": REFERENCE})])
    ending = done.of("task.completed")[0]
    assert ending["findings"][0]["values"] == ["14,382"]
    assert ending["llm_calls"] == 0
    # Done there, not on the site it was taught on.
    assert done.url.startswith(sister_billing)
    assert done.asked() == [voice.routine_ask("Reference No."), voice.ASK_COOKIES]


# --- the list offers it -------------------------------------------------------------


@dataclass
class R:
    id: str
    label: str
    start: str


def test_the_list_offers_a_routine_on_sister_sites_of_its_genre():
    catalogue = Catalogue(genres=["Bills", "Travel"], sites=[
        Site("iesco", "IESCO bill", "https://bill.pitc.com.pk/iescobill", "Bills"),
        Site("ssgc", "Gas bill", "https://www.ssgc.com.pk/", "Bills"),
        Site("rail", "Railways", "https://www.pakrailways.gov.pk/train", "Travel"),
    ])
    sites = {s.id: s for s in offered(catalogue, [R("r1", "My bill", "https://bill.pitc.com.pk/iescobill")])}
    assert sites["iesco"].tasks == (Task("My bill", "My bill", "taught", routine="r1"),)
    assert sites["ssgc"].tasks == (Task("My bill", "My bill", "taught", routine="r1",
                                        taught_on="IESCO bill"),)
    # Not on a website of another genre.
    assert sites["rail"].tasks == ()


def test_a_routine_on_an_unlisted_site_is_offered_nowhere():
    catalogue = Catalogue(genres=["Bills"], sites=[
        Site("ssgc", "Gas bill", "https://www.ssgc.com.pk/", "Bills")])
    sites = offered(catalogue, [R("r1", "Mine", "https://nowhere.example/")])
    assert sites[0].tasks == ()
