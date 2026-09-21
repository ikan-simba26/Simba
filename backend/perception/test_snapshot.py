"""Boxes arrive in device pixels and leave in CSS pixels.

CDP reports a snapshot's layout in device pixels. Everything else in this
project is CSS pixels: the frozen 1280x800 viewport, `MIN_COVERAGE` as a
fraction of it, the estimator's text density. While the device pixel ratio is
1 the two are the same and nothing notices; the Electron host on this
machine's display runs at 1.5, and there the same `<h1>` measured
`(384, 180, 1152, 48)` where headless measured `(256, 120, 768, 32)`
(EVALUATION.md, 2026-09-19b).

`parse` converts, so no caller has to know, and these tests are about that.

They also record something that cost an afternoon: **a headless browser cannot
reproduce the host's condition.** Playwright's `device_scale_factor` is an
emulation — the page reports `devicePixelRatio` 1.5 and CDP still reports every
box in CSS pixels — so dividing by what the page says would have been wrong in
exactly the environment the tests run in. The ratio comes from the two
viewports CDP reports instead, which reads 1 under emulation and 1.5 in the
host. The one test that needs the real thing is skipped unless
`SIMBA_HOST_TESTS=1` and a host is up.
"""

import os
from collections.abc import Iterator

import pytest
from playwright.sync_api import Playwright

from backend.perception.serializer import VIEWPORT, read, pixel_ratio
from backend.perception.snapshot import parse

# One element at a known place, so the numbers below can be read off it.
PAGE = """
<html><body style="margin:0">
  <div id="box" style="position:absolute; left:100px; top:200px;
                       width:300px; height:40px; background:#eee">box</div>
</body></html>
"""

BOX = "() => { const r = document.getElementById('box').getBoundingClientRect();" \
      " return [r.x, r.y, r.width, r.height]; }"


def snapshot_of(width: float, height: float) -> dict:
    """The smallest captureSnapshot payload `parse` will accept."""
    return {
        "strings": ["#document", "DIV"],
        "documents": [{
            "nodes": {
                "parentIndex": [-1, 0],
                "nodeType": [9, 1],
                "nodeName": [0, 1],
                "nodeValue": [-1, -1],
                "backendNodeId": [1, 2],
                "attributes": [[], []],
            },
            "layout": {"nodeIndex": [1], "bounds": [[10.0, 20.0, width, height]]},
        }],
    }


# --- the conversion ---------------------------------------------------------


def test_a_ratio_of_one_leaves_the_numbers_alone() -> None:
    document = parse(snapshot_of(300.0, 40.0))
    assert document.bounds[1] == (10.0, 20.0, 300.0, 40.0)
    assert document.device_pixel_ratio == 1.0


def test_a_ratio_of_one_and_a_half_divides_every_box() -> None:
    document = parse(snapshot_of(450.0, 60.0), 1.5)
    assert document.bounds[1] == pytest.approx((6.667, 13.333, 300.0, 40.0), abs=0.01)
    assert document.device_pixel_ratio == 1.5


def test_the_ratio_is_recorded_so_a_reader_can_tell_what_happened() -> None:
    """A row in a corpus should be able to say what the display was doing."""
    assert parse(snapshot_of(1.0, 1.0), 2.0).device_pixel_ratio == 2.0


def test_a_missing_ratio_does_not_erase_the_layout() -> None:
    """Dividing by zero would lose every box. Nonsense reads as 1."""
    document = parse(snapshot_of(300.0, 40.0), 0)
    assert document.bounds[1] == (10.0, 20.0, 300.0, 40.0)
    assert document.device_pixel_ratio == 1.0


# --- where the ratio comes from ---------------------------------------------


def test_the_ratio_is_read_from_the_two_viewports_cdp_reports() -> None:
    """`Page.getLayoutMetrics` gives the same viewport in both units, so no
    JavaScript runs on the page being read."""
    assert pixel_ratio({"layoutViewport": {"clientWidth": 1920},
                        "cssLayoutViewport": {"clientWidth": 1280}}) == 1.5
    assert pixel_ratio({"layoutViewport": {"clientWidth": 1280},
                        "cssLayoutViewport": {"clientWidth": 1280}}) == 1.0


@pytest.mark.parametrize("metrics", [{}, {"layoutViewport": {}},
                                     {"layoutViewport": {"clientWidth": 0},
                                      "cssLayoutViewport": {"clientWidth": 1280}}])
def test_metrics_that_say_nothing_mean_a_ratio_of_one(metrics: dict) -> None:
    assert pixel_ratio(metrics) == 1.0


# --- and in a browser -------------------------------------------------------
#
# A headless browser cannot reproduce the host's condition, which is worth
# stating because it is why this went unnoticed. Playwright's
# `device_scale_factor` is an *emulation*: the page reports
# `devicePixelRatio` 1.5 and CDP still reports every box, and both viewports,
# in CSS pixels. The Electron host's 1.5 comes from the display itself, and
# there `layoutViewport` reads 1920x1200 against `cssLayoutViewport`
# 1280x800 — and the boxes are scaled to match. Measured both ways on
# 2026-09-20.
#
# So `pixel_ratio` asks the two viewports rather than the page: emulation
# reads 1.0 and nothing is converted, which is right, and the host reads 1.5
# and everything is.


@pytest.fixture(scope="module")
def scaled(playwright_instance: Playwright) -> Iterator[tuple]:
    """The same page in a plain context and in one emulating a 1.5x display."""
    browser = playwright_instance.chromium.launch()
    made = []
    for ratio in (1.0, 1.5):
        context = browser.new_context(
            viewport={"width": VIEWPORT[0], "height": VIEWPORT[1]},
            device_scale_factor=ratio,
        )
        page = context.new_page()
        page.set_content(PAGE)
        made.append(page)
    yield tuple(made)
    browser.close()


def box_in(document) -> tuple:
    index = next(i for i, name in enumerate(document.node_names)
                 if name.upper() == "DIV")
    return document.bounds[index]


def test_the_box_reads_as_css_pixels_whatever_the_page_says_its_ratio_is(
    scaled: tuple,
) -> None:
    """One page, two displays, one answer — which is the point of the change."""
    plain, emulated = scaled
    assert plain.evaluate(BOX) == emulated.evaluate(BOX) == [100, 200, 300, 40]
    assert emulated.evaluate("() => window.devicePixelRatio") == 1.5

    for page in (plain, emulated):
        assert box_in(read(page, VIEWPORT).document) == pytest.approx(
            (100, 200, 300, 40), abs=0.6)


def test_an_emulated_ratio_is_not_a_scaled_snapshot(scaled: tuple) -> None:
    """The reason `devicePixelRatio` is the wrong thing to divide by.

    Under emulation the page says 1.5 and CDP reports CSS pixels anyway;
    dividing by what the page says would have shrunk every box by a third.
    """
    _, emulated = scaled
    assert read(emulated, VIEWPORT).document.device_pixel_ratio == 1.0


@pytest.mark.skipif(not os.environ.get("SIMBA_HOST_TESTS"),
                    reason="needs the Electron host on :9222 (SIMBA_HOST_TESTS=1)")
def test_the_host_reports_a_real_ratio_and_the_boxes_come_back_css(
    playwright_instance: Playwright,
) -> None:
    """The environment the defect lived in, checked rather than described.

    `run.ps1 registration` (or any flow), then `SIMBA_HOST_TESTS=1 pytest`.
    """
    browser = playwright_instance.chromium.connect_over_cdp("http://127.0.0.1:9222")
    site = next(page for context in browser.contexts for page in context.pages
                if not page.url.startswith(("file:", "devtools:", "chrome:")))
    site.set_content(PAGE)

    document = read(site, VIEWPORT).document

    assert document.device_pixel_ratio > 1.0, "this host is not on a scaled display"
    assert box_in(document) == pytest.approx((100, 200, 300, 40), abs=1.0)
    browser.close()



# --- the scroll offset, which arrives in the same units as the boxes --------


def test_the_scroll_offset_is_divided_by_the_ratio_like_every_box() -> None:
    """Measured in the host: scrolled to 1234 CSS px, CDP said 1851 (x1.5)."""
    snapshot = snapshot_of(300.0, 60.0)
    snapshot["documents"][0]["scrollOffsetX"] = 0
    snapshot["documents"][0]["scrollOffsetY"] = 1851

    document = parse(snapshot, device_pixel_ratio=1.5)

    assert document.scroll == pytest.approx((0.0, 1234.0), abs=0.5)


def test_a_snapshot_with_no_scroll_offset_is_at_the_top() -> None:
    assert parse(snapshot_of(300.0, 60.0)).scroll == (0.0, 0.0)


@pytest.mark.skipif(not os.environ.get("SIMBA_HOST_TESTS"),
                    reason="needs the Electron host on :9222 (SIMBA_HOST_TESTS=1)")
def test_the_host_scroll_offset_comes_back_css(playwright_instance: Playwright) -> None:
    """The measurement the unit test above is copied from, kept runnable."""
    browser = playwright_instance.chromium.connect_over_cdp("http://127.0.0.1:9222")
    site = next(page for context in browser.contexts for page in context.pages
                if not page.url.startswith(("file:", "devtools:", "chrome:")))
    site.set_content('<div style="height: 5000px"></div>')
    site.evaluate("window.scrollTo(0, 1234)")
    site.wait_for_timeout(200)

    document = read(site, VIEWPORT).document

    assert document.device_pixel_ratio > 1.0, "this host is not on a scaled display"
    assert document.scroll == pytest.approx((0.0, 1234.0), abs=1.0)
    site.evaluate("window.scrollTo(0, 0)")
    browser.close()
