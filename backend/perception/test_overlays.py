"""Overlay detection against the replica's deliberately non-semantic modal.

The replica's modal is a plain `div` with no role="dialog" and no aria-modal,
on purpose — that is what real portals ship, and it is exactly the case the
accessibility tree cannot see. Detection has to be structural or it is
useless here.
"""

from collections.abc import Iterator

import pytest
from playwright.sync_api import Page

from backend.perception.overlays import MIN_STACK_LEVEL, analyse
from backend.perception.serializer import serialize
from backend.perception.test_serializer import find, labels

VIEWPORT = (1280, 800)


@pytest.fixture
def courses(replica: str, page: Page) -> Iterator[Page]:
    """The course list, with the modal up as it is on load."""
    page.goto(replica + "/")
    page.fill("#username", "raham")
    page.fill("#password", "hunter2")
    page.click("button[type=submit]")
    page.wait_for_url(replica + "/courses")
    yield page


def test_the_modal_is_detected_without_any_aria(courses: Page) -> None:
    elements = serialize(courses)

    close = find(elements, "Close")
    assert close.overlay, "the modal's own button was not flagged as an overlay"
    assert not close.occluded, "the dismiss button must stay reachable"


def test_the_register_button_is_occluded_while_the_modal_is_open(courses: Page) -> None:
    elements = serialize(courses)

    register = find(elements, "Register for CS-401")
    assert register.occluded, "a click here cannot land, and nothing said so"
    assert not register.overlay


def test_the_page_behind_is_occluded_wholesale(courses: Page) -> None:
    elements = serialize(courses)

    occluded = [e for e in elements if e.occluded]
    overlay = [e for e in elements if e.overlay]

    assert len(overlay) == 1, [e.label for e in overlay]
    assert len(occluded) > 40, len(occluded)
    # Nothing is both.
    assert not [e for e in elements if e.overlay and e.occluded]


def test_dismissing_the_modal_clears_every_flag(courses: Page) -> None:
    courses.click("#modal-close")

    elements = serialize(courses)

    assert not [e for e in elements if e.occluded]
    assert not [e for e in elements if e.overlay]
    assert "Close" not in labels(elements)


def test_a_page_with_no_overlay_flags_nothing(replica: str, page: Page) -> None:
    page.goto(replica + "/")

    elements = serialize(page)

    assert not [e for e in elements if e.overlay or e.occluded]
    assert find(elements, "Sign In").occluded is False


def test_report_explains_why_it_flagged_the_blocker(courses: Page) -> None:
    cdp = courses.context.new_cdp_session(courses)
    cdp.send("DOMSnapshot.enable")
    from backend.perception.overlays import COMPUTED_STYLES

    snapshot = cdp.send("DOMSnapshot.captureSnapshot", {"computedStyles": COMPUTED_STYLES})
    cdp.detach()

    report = analyse(snapshot, VIEWPORT)

    assert report.blocked
    blocker = report.blockers[0]
    assert blocker.z_index >= MIN_STACK_LEVEL
    assert blocker.coverage > 0.9  # the replica's backdrop covers everything
    assert "z-index" in blocker.reason


def test_analyse_survives_an_empty_snapshot() -> None:
    report = analyse({}, VIEWPORT)

    assert not report.blocked
    assert report.overlay_ids == set() and report.occluded_ids == set()
