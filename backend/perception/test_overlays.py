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
    positioned,
)
from backend.perception.snapshot import parse
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


# --- a full-screen fixed element, with no z-index at all --------------------
#
# Both rules above start by asking for a declared `z-index` of at least
# `MIN_STACK_LEVEL`, and that turned out to be an assumption rather than a
# requirement. `the-internet.herokuapp.com/entry_ad` puts up a
# `position: fixed` modal covering the whole viewport with `z-index: auto` —
# it does not need one, being fixed and last in the DOM — and the corpus read
# zero overlays on it (EVALUATION.md, 2026-09-20b).
#
# So a *fixed or sticky* element that covers enough of the viewport is a
# blocker whatever its z-index. Those two positions are lifted out of the
# normal flow and painted against the viewport; `absolute` is not, which is
# why it is deliberately left out below.

ENTRY_AD = """
<style>
  body { margin: 0; }
  #page { height: 2000px; }
  #modal { position: fixed; top: 0; left: 0; width: 100%; height: 100%;
           background: rgba(0,0,0,0.5); }
  #dialog { position: absolute; top: 200px; left: 340px;
            width: 600px; height: 400px; background: #fff; }
</style>
<div id="page"><button id="buried">Buy now</button></div>
<div id="modal"><div id="dialog"><button id="shut">Close</button></div></div>
"""

STICKY_SHEET = """
<style>
  body { margin: 0; }
  #sticky { position: sticky; top: 0; width: 1280px; height: 600px;
            background: #eee; }
</style>
<div id="sticky"><button id="shut">Close</button></div>
<div style="height: 2000px"><button id="buried">Buy now</button></div>
"""

#: A fixed strip along the bottom, no z-index — the shape the page-level rule
#: is *supposed* to ignore, because the page around it is still usable.
FIXED_STRIP = """
<style>
  body { margin: 0; }
  #bar { position: fixed; bottom: 0; left: 0; width: 100%; height: 60px;
         background: #333; }
</style>
<div style="height: 2000px"><button id="buried">Buy now</button></div>
<div id="bar"><button id="accept">Accept</button></div>
"""

#: The same full-viewport box, `absolute` instead of `fixed`. This is every
#: hero image and every stretched background on the web, and it is also
#: entry_ad's own `.underlay`, which is a child of the fixed modal and gets
#: picked up as part of it rather than on its own.
ABSOLUTE_SHEET = """
<style>
  body { margin: 0; }
  #sheet { position: absolute; top: 0; left: 0; width: 1280px; height: 800px;
           background: #eee; }
</style>
<div id="sheet"></div>
<div style="height: 2000px"><button id="buried">Buy now</button></div>
"""


def built(page: Page, markup: str) -> Page:
    """A page from a string, so these cases need no network and no replica."""
    page.goto("about:blank")
    page.set_content(markup)
    page.wait_for_timeout(100)
    return page


def test_a_fixed_full_screen_element_blocks_without_any_z_index(page: Page) -> None:
    """The entry_ad shape: fixed, 100% of the viewport, `z-index: auto`."""
    report = analyse(snapshot_of(built(page, ENTRY_AD)), VIEWPORT)

    assert report.blocked, "a full-screen fixed modal was reported as nothing"
    blocker = report.blockers[0]
    assert blocker.coverage >= MIN_COVERAGE
    assert not blocker.scoped_to_target, "this is the page-level rule, not the target one"


def test_the_reason_says_there_was_no_z_index_rather_than_inventing_one(
    page: Page,
) -> None:
    """A reader of the log has to be able to tell which rule fired."""
    report = analyse(snapshot_of(built(page, ENTRY_AD)), VIEWPORT)

    assert "z-index auto" in report.blockers[0].reason
    assert "covering 100% of the viewport" in report.blockers[0].reason


def test_what_is_behind_a_z_less_modal_is_occluded_and_its_own_button_is_not(
    page: Page,
) -> None:
    elements = serialize(built(page, ENTRY_AD))

    assert find(elements, "Close").overlay
    assert not find(elements, "Close").occluded, "the dismiss button must stay reachable"
    assert find(elements, "Buy now").occluded, "a click here cannot land"


def test_a_sticky_element_over_the_threshold_blocks_too(page: Page) -> None:
    """`sticky` is not in `STACKED_POSITIONS` and is lifted all the same."""
    report = analyse(snapshot_of(built(page, STICKY_SHEET)), VIEWPORT)

    assert report.blocked
    assert report.blockers[0].coverage >= MIN_COVERAGE


def test_a_fixed_strip_under_the_threshold_is_still_not_a_page_blocker(
    page: Page,
) -> None:
    """The page-level rule keeps its meaning: is the page as a whole unusable.

    Without this the new rule would flag every cookie bar and every sticky
    header on the web as a modal. The bar is still caught by the
    target-scoped rule when a step reaches under it — that is what the
    billing replica's cookie bar tests above are.
    """
    report = analyse(snapshot_of(built(page, FIXED_STRIP)), VIEWPORT)

    assert not report.blocked


def test_an_absolute_sheet_with_no_z_index_is_not_a_blocker(page: Page) -> None:
    """`absolute` sits in normal paint order, so covering is not stacking.

    A stretched background `div` covers the whole viewport and is underneath
    everything. Requiring a declared `z-index` of it is the only thing that
    separates it from a modal.
    """
    report = analyse(snapshot_of(built(page, ABSOLUTE_SHEET)), VIEWPORT)

    assert not report.blocked


def test_the_declared_modal_is_still_found_exactly_once(courses: Page) -> None:
    """No regression: the replica's modal has a z-index and is one blocker.

    Its backdrop and dialog must not now arrive as two, which is what a
    second rule matching the same subtree would do.
    """
    report = analyse(snapshot_of(courses), VIEWPORT)

    assert len([b for b in report.blockers if not b.scoped_to_target]) == 1
    assert report.blockers[0].coverage > 0.9


def test_a_page_with_nothing_on_it_is_still_clear(replica: str, page: Page) -> None:
    """The other half of no-regression: the login page gains no blocker."""
    page.goto(replica + "/")

    assert not analyse(snapshot_of(page), VIEWPORT).blocked


# --- the page is not covering itself ----------------------------------------
#
# Found on 2026-09-20e by extending the corpus. The Guardian and Spiegel both
# put `position: fixed` on `<body>` while their consent wall is up — it is the
# standard way to stop the page behind a modal from scrolling — and a fixed
# `<body>` is a fixed element covering the whole viewport, so the rule added
# earlier the same day flagged it.
#
# It is not a near miss. `body`'s box is the *document*, not the viewport, so
# it came back at coverage **27.17** on the Guardian and **43.61** on Spiegel:
# 2717% of the screen. And because `_overlay_indexes` takes a blocker's whole
# subtree, flagging `body` marks every element on the page as belonging to an
# overlay, which is the worst possible answer — a planner is told the entire
# page is a dialog.

SCROLL_LOCKED = """
<style>
  html { height: 100%; }
  body { position: fixed; top: 0; left: 0; width: 100%; margin: 0; }
  #wall { position: fixed; top: 100px; left: 240px; width: 800px; height: 600px;
          background: #fff; z-index: 50; }
</style>
<div style="height: 3000px"><button id="buried">Buy now</button></div>
<div id="wall"><button id="agree">I agree</button></div>
"""


def test_a_scroll_locked_body_is_not_a_blocker(page: Page) -> None:
    """`position: fixed` on `<body>` is a scroll lock, not an overlay."""
    report = analyse(snapshot_of(built(page, SCROLL_LOCKED)), VIEWPORT)

    tags = {b.backend_node_id for b in report.blockers}
    assert tags, "the consent wall itself should still be found"
    for blocker in report.blockers:
        assert "fixed at z-index auto" not in blocker.reason or blocker.coverage < 5, (
            f"something enormous was flagged: {blocker.reason}"
        )
    # The wall is the blocker, and it is the only one.
    assert len(report.blockers) == 1
    assert report.blockers[0].coverage == pytest.approx(0.469, abs=0.01)


def test_the_page_behind_a_wall_is_still_occluded_when_body_is_locked(
    page: Page,
) -> None:
    """The real bite: flagging `body` marks the whole page as overlay.

    `_overlay_indexes` takes a blocker's entire subtree, so a blocked `body`
    puts every element on the page in `overlay_ids` and leaves `occluded_ids`
    empty — exactly inverting what perception is supposed to say.
    """
    elements = serialize(built(page, SCROLL_LOCKED))

    assert find(elements, "I agree").overlay, "the wall's own button"
    assert not find(elements, "I agree").occluded
    assert not find(elements, "Buy now").overlay, "the page is not the overlay"


def test_the_root_element_is_never_a_candidate(page: Page) -> None:
    """`html` too, for the same reason and by the same route."""
    page.goto("about:blank")
    page.set_content(
        "<style>html { position: fixed; width: 100%; height: 100%; }</style>"
        "<div style='height: 2000px'><button>Buy now</button></div>"
    )
    page.wait_for_timeout(100)

    assert not analyse(snapshot_of(page), VIEWPORT).blocked


# --- coverage is of the screen, not of the element --------------------------
#
# Found on 2026-09-20e by putting pages with partial-coverage overlays in the
# corpus. `coverage` was `(width * height) / viewport_area` with nothing
# asking where the box actually was, so a big element far down a long page
# scored as though it were covering the screen:
#
#   Guardian   div.dcr-1lss6kd   rect (490, 19167, 700, 570)   coverage 0.389
#   Spiegel    div.WSwWMedB      rect (136, 14308, 1008, 456)  coverage 0.449
#
# Nineteen thousand pixels down the page is not "covering 39% of the
# viewport". Five of the twelve candidates that first appeared in the
# 0.30-0.90 band were this, which would have made a threshold measured on
# them meaningless.
#
# Every overlay the project had measured before was a full-screen modal at
# (0, 0), where the element's own area and its share of the screen are the
# same number, which is why this survived.

FAR_DOWN_THE_PAGE = """
<style>
  body { margin: 0; }
  #big { position: absolute; top: 9000px; left: 0; width: 1000px; height: 700px;
         background: #ccc; z-index: 40; }
</style>
<div style="height: 12000px"><button id="buried">Buy now</button></div>
<div id="big">A promo panel nine thousand pixels down</div>
"""

#: Half on screen, half below it: 1280x800 starting at y=400, so exactly half
#: of its area is visible and the other half is not.
HALF_OFF_THE_BOTTOM = """
<style>
  body { margin: 0; }
  #sheet { position: fixed; top: 400px; left: 0; width: 1280px; height: 800px;
           background: #eee; z-index: 40; }
</style>
<div style="height: 3000px"><button id="buried">Buy now</button></div>
<div id="sheet">A sheet hanging off the bottom</div>
"""


def test_a_big_element_far_below_the_fold_covers_nothing(page: Page) -> None:
    """700x570 at y=9000 is 0% of the screen, not 39% of it."""
    report = analyse(snapshot_of(built(page, FAR_DOWN_THE_PAGE)), VIEWPORT)

    assert not report.blocked, (
        "an element nine thousand pixels down was called a page-level blocker"
    )


def test_coverage_is_the_part_on_screen(page: Page) -> None:
    """Half off the bottom is half the coverage its area would suggest."""
    document = parse(snapshot_of(built(page, HALF_OFF_THE_BOTTOM)))
    sheet = [c for c in positioned(document, VIEWPORT) if c.tag == "div"
             and c.rect[3] > 700]

    assert sheet, "the sheet itself was not found"
    # Its own area is 1280x800 = one whole viewport; only 1280x400 is visible.
    assert sheet[0].coverage == pytest.approx(0.5, abs=0.01)


def test_a_full_screen_modal_still_reads_one(courses: Page) -> None:
    """The clip must not move the number for anything already measured."""
    report = analyse(snapshot_of(courses), VIEWPORT)

    assert report.blockers[0].coverage == pytest.approx(1.0, abs=0.02)


def test_the_blockers_rect_is_still_the_whole_element(page: Page) -> None:
    """Only `coverage` is clipped. Occlusion needs the real box.

    Whether a click can land is decided by `centre_inside` against the
    blocker's rect, and clipping that would stop a sheet hanging off the
    bottom of the screen from occluding what is under its visible half.
    """
    report = analyse(snapshot_of(built(page, HALF_OFF_THE_BOTTOM)), VIEWPORT)

    assert report.blocked
    assert report.blockers[0].rect[3] == pytest.approx(800, abs=1), (
        "the rect was clipped; it should be the element's real box"
    )


# --- the viewport is wherever the page is scrolled to ------------------------
#
# The clip above was written as though every read happens at the top of the
# page. Idle reads do; driven ones do not. When a corpus drive clicks a button
# half-way down a docs page, Playwright scrolls it into view first, and CDP
# reports every box in *document* coordinates — so Bootstrap's full-screen
# backdrop, read at scroll 900, has the rect (0, 900, 1280, 800). Clipped
# against (0, 0, 1280, 800) it covered 0.000 of the screen. Five full-screen
# overlays in the corpus went from 1.000 to near nothing in one commit
# (EVALUATION.md, 2026-09-20e).

SCROLLED_MODAL = """
<style>
  body { margin: 0; }
  #modal { position: fixed; top: 0; left: 0; width: 100%; height: 100%;
           background: rgba(0,0,0,.5); z-index: 50; }
</style>
<div style="height: 5000px"><button>Buy now</button></div>
<div id="modal"><button>Close</button></div>
"""


def test_a_full_screen_modal_on_a_scrolled_page_covers_the_screen(page: Page) -> None:
    built(page, SCROLLED_MODAL)
    page.evaluate("window.scrollTo(0, 1234)")
    page.wait_for_timeout(100)

    report = analyse(snapshot_of(page), VIEWPORT)

    assert report.blocked, "a full-screen modal was missed because the page was scrolled"
    assert report.blockers[0].coverage == pytest.approx(1.0, abs=0.01)


def test_a_box_in_view_after_scrolling_counts_and_one_above_it_does_not(
    page: Page,
) -> None:
    """Scrolled to 9000, the promo panel at 9000 is on screen; at 0 it is not."""
    built(page, FAR_DOWN_THE_PAGE)
    page.evaluate("window.scrollTo(0, 9000)")
    page.wait_for_timeout(100)

    assert analyse(snapshot_of(page), VIEWPORT).blocked

    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(100)

    assert not analyse(snapshot_of(page), VIEWPORT).blocked


def test_the_document_records_where_it_was_scrolled(page: Page) -> None:
    built(page, SCROLLED_MODAL)
    page.evaluate("window.scrollTo(0, 1234)")
    page.wait_for_timeout(100)

    document = parse(snapshot_of(page))

    assert document.scroll == (0.0, 1234.0)
