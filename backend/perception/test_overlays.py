"""Overlay detection against the replica's deliberately non-semantic modal.

The replica's modal is a plain `div` with no role="dialog" and no aria-modal,
on purpose — that is what real portals ship, and it is exactly the case the
accessibility tree cannot see. Detection has to be structural or it is
useless here.
"""

from collections.abc import Iterator

import pytest
from playwright.sync_api import Page

from backend.perception.overlays import (
    COMPUTED_STYLES,
    MIN_COVERAGE,
    MIN_STACK_LEVEL,
    analyse,
)
from backend.perception.serializer import is_dead_link, serialize
from backend.perception.test_serializer import find, labels

VIEWPORT = (1280, 800)


@pytest.fixture(autouse=True)
def detection_on(monkeypatch) -> None:
    """These assert what detection does, so don't inherit the ablation flag."""
    monkeypatch.setenv("SIMBA_OVERLAY_DETECTION", "1")


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


# --- dead links -------------------------------------------------------------


@pytest.mark.parametrize(
    "href,expected",
    [
        ("#", True),
        ("", True),
        ("javascript:void(0)", True),
        ("javascript:void(0);", True),
        ("javascript:;", True),
        ("/courses", False),
        ("#section-2", False),
        ("https://example.com", False),
    ],
)
def test_dead_link_rule(href: str, expected: bool) -> None:
    assert is_dead_link("a", {"href": href}) is expected


def test_a_button_is_never_a_dead_link() -> None:
    assert is_dead_link("button", {}) is False


def test_the_replicas_placeholder_nav_is_flagged(replica: str, page: Page) -> None:
    page.goto(replica + "/")
    elements = serialize(page)

    # The nav is href="#" throughout; the Registrar link is a real target.
    assert find(elements, "Home").dead_link
    assert find(elements, "Academic Calendar").dead_link
    assert not find(elements, "Registrar").dead_link
    assert not find(elements, "Sign In").dead_link  # a button, not a link


def test_the_ablation_switch_turns_detection_off(courses: Page, monkeypatch) -> None:
    """The A/B arm: same page, same modal, no flags raised."""
    monkeypatch.setenv("SIMBA_OVERLAY_DETECTION", "0")

    elements = serialize(courses)

    assert not [e for e in elements if e.overlay or e.occluded]
    # Dead-link flagging is a separate feature and stays on, so the ablation
    # isolates overlay detection rather than perception as a whole.
    assert find(elements, "Home").dead_link


# --- the target-scoped rule -------------------------------------------------
#
# `MIN_COVERAGE` asks "is the page unusable". That is the right question for a
# modal and the wrong one for a strip along the bottom of the screen, which is
# why the billing replica's cookie bar went undetected for a fortnight while
# sitting on top of six live links. The second rule asks the question that
# actually decides whether a step can work: is anything on top of *this*
# element.


def snapshot_of(page: Page) -> dict:
    cdp = page.context.new_cdp_session(page)
    cdp.send("DOMSnapshot.enable")
    snapshot = cdp.send("DOMSnapshot.captureSnapshot", {"computedStyles": COMPUTED_STYLES})
    cdp.detach()
    return snapshot


@pytest.fixture
def bill(billing: str, page: Page) -> Page:
    """The enquiry result, scrolled to the footer, cookie bar still up.

    Scrolled deliberately. The page is 896px in an 800px viewport, so at the
    top the footer links sit below the fold and the bar covers nothing — the
    conflict only exists once someone has scrolled down to reach the links,
    which is the moment they would try to use them. Testing at scroll zero
    would assert against a page where the problem is not yet happening.
    """
    page.goto(f"{billing}/bill?reference=04141234567890")
    page.mouse.wheel(0, 2000)
    page.wait_for_timeout(300)
    return page


def test_the_cookie_bar_is_invisible_to_the_page_level_rule(bill: Page) -> None:
    """Not a bug in the page-level rule — the page genuinely is usable."""
    report = analyse(snapshot_of(bill), VIEWPORT)

    assert not report.blocked


def test_the_cookie_bar_blocks_the_footer_link_it_is_sitting_on(bill: Page) -> None:
    elements = serialize(bill)
    disclaimer = find(elements, "Disclaimer")

    report = analyse(snapshot_of(bill), VIEWPORT, target=disclaimer.backend_node_id)

    assert report.blocked, "a link under the cookie bar was reported as clickable"
    blocker = report.target_blockers[0]
    assert blocker.scoped_to_target
    assert blocker.coverage < MIN_COVERAGE, "this is the case coverage cannot see"
    assert "overlapping the element this step needs" in blocker.reason
    # And the link is behind it, not merely near it.
    assert disclaimer.backend_node_id in report.occluded_ids


def test_an_element_nowhere_near_the_bar_is_not_blocked(bill: Page) -> None:
    elements = serialize(bill)
    enquiry = [e for e in elements if e.label == "Bill Enquiry"][0]

    report = analyse(snapshot_of(bill), VIEWPORT, target=enquiry.backend_node_id)

    assert not report.blocked


def test_the_bars_own_button_is_not_blocked_by_the_bar(bill: Page) -> None:
    """Otherwise the one control that dismisses it would be unreachable."""
    elements = serialize(bill)
    accept = find(elements, "Accept all cookies")

    report = analyse(snapshot_of(bill), VIEWPORT, target=accept.backend_node_id)

    assert accept.backend_node_id not in report.occluded_ids


def test_naming_a_target_does_not_lose_the_page_level_blocker(courses: Page) -> None:
    """Both rules at once: the modal is still found when a target is named."""
    elements = serialize(courses)
    register = find(elements, "Register for CS-401")

    report = analyse(snapshot_of(courses), VIEWPORT, target=register.backend_node_id)

    assert report.blocked
    assert any(not b.scoped_to_target for b in report.blockers), "lost the modal"
    assert register.backend_node_id in report.occluded_ids


def test_no_target_behaves_exactly_as_before(bill: Page) -> None:
    """The default path is untouched, so nothing already passing changed."""
    snapshot = snapshot_of(bill)

    assert analyse(snapshot, VIEWPORT).blockers == []
    assert analyse(snapshot, VIEWPORT, target=None).blockers == []
