"""The window fits the screen, and the site view stays 1280x800.

A 1920x1080 laptop at 150% has a work area of 1280x672 in Windows' units, and
a fixed 1280x800 window put the home screen's text box below the bottom of
it. `frontend/electron/main.ts` now fits the window to the work area, and the
overlay lays out at the window's real size — no zoom, so text keeps its size —
with a compact layout in short windows; the site view is left alone. This
launches the real host at forced display scales and checks every promise from
outside it (`tools/evaluation/display_fit_run.py` does the measuring).

It opens real windows, so it runs only with `SIMBA_HOST_TESTS=1`, like the
other tests that need the host. It needs `npm run build` first.
"""

import concurrent.futures
import os
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parent

pytestmark = [
    pytest.mark.skipif(not os.environ.get("SIMBA_HOST_TESTS"),
                       reason="opens the Electron host (SIMBA_HOST_TESTS=1)"),
    pytest.mark.skipif(not (FRONTEND / "dist" / "index.html").exists(),
                       reason="frontend not built; run `npm run build` in frontend/"),
]


def measured(scale: str) -> dict:
    from tools.evaluation.display_fit_run import measure

    # Its own thread: a sync Playwright session elsewhere in the suite holds
    # this one (backend/conftest.py).
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(measure, scale).result()


@pytest.mark.parametrize("scale", ["1", "1.25", "1.5"])
def test_the_window_fits_and_the_site_view_does_not_change(scale: str) -> None:
    result = measured(scale)

    assert result["window_fits_work_area"], result["host_says"]
    # The overlay is the window's size, not zoomed to a design size.
    assert result["overlay_matches_window"], (result["overlay"], result["host_says"])
    # Nothing on the home screen is below 20px, at any scale.
    assert result["overlay"]["smallest_text_px"] >= 20, result["overlay"]
    # The text box is on screen with nothing to scroll.
    assert result["overlay"]["box_in_viewport"], result["overlay"]
    assert not result["overlay"]["scrolls"], result["overlay"]
    # And for someone with history: the three tiles and two remembered goals
    # under them, as long as a line holds. Not measured until 2026-09-30, when
    # six cards had put the box below the bottom of the window at every scale.
    # Since 2026-10-18 with the person's own three tiles above them too: the
    # fullest the home screen gets.
    history = result["overlay_with_history"]
    assert history["cards"] == 3, history
    assert history["own_tiles"] == 3, history
    assert history["remembered"] == 2, history
    assert history["box_in_viewport"], history
    assert not history["scrolls"], history
    assert history["smallest_text_px"] >= 20, history
    # And a new person's first open (2026-10-18): the welcome, its four
    # questions each fitting, nothing to scroll and every button in the window.
    welcome = result["welcome"]
    assert [q["question"] for q in welcome] == ["name", "level", "read", "ask"], welcome
    for question in welcome:
        assert not question["scrolls"] and question["off"] == [], question
    # And every way a task can end: each button wholly in the window, nothing
    # to scroll. Not measured until 2026-10-05, when the closing screen had put
    # its way onward below the window, with three results or more, at every
    # scale.
    from frontend.test_terminal_states import ENDINGS

    assert set(result["endings"]) == set(ENDINGS), sorted(result["endings"])
    for name, ending in result["endings"].items():
        assert ending["buttons"], (name, ending)
        assert ending["off_screen"] == [], (name, ending)
        assert not ending["scrolls"], (name, ending)
    # And the sign-in screen, the registration's first (2026-10-16): measured
    # headless only until then, where Electron lays text out wider.
    sign_in = result["sign_in"]
    assert sign_in["buttons"], sign_in
    assert sign_in["off_screen"] == [], sign_in
    assert sign_in["fields_on_screen"], sign_in
    assert not sign_in["scrolls"], sign_in
    # The brand (2026-11-02): the window's name, the logo while opening whole
    # and centred, the small logo touching nothing on the fullest home screen,
    # in each theme and from the theme's own file; a step with the shape and
    # no logo; and no logo at all under reduced motion.
    assert result["window_title"] in ("simba", None), result["window_title"]
    brand = result["brand"]
    assert brand["reduced_motion_logos"] == 0, brand
    for theme, ending in (("light", ""), ("dark", "-dark")):
        splash, home = brand[theme]["splash"], brand[theme]["home"]
        assert splash["file"] == f"simba-logo-stacked{ending}" and splash["loaded"], splash
        assert splash["whole"] and splash["centred"] and not splash["scrolls"], splash
        assert home["file"] == f"simba-logo-horizontal-small{ending}" and home["loaded"], home
        assert home["whole"] and home["touches"] == 0 and not home["scrolls"], home
        step = brand["steps"][theme]
        assert step["home_logos"] == 0 and step["shapes"] >= 1, step
        assert step["off_screen"] == [] and not step["scrolls"], step
    # Perception's page is exactly what it was.
    assert result["site_view"]["inner"] == [1280, 800], result["site_view"]
    # And a page that scrolls lays out at the full 1280px, inner scroll boxes
    # too, as it does headless — on the first page and the next — and still
    # scrolls. Until 2026-09-30 the host laid it out at 1263px.
    for page in ("first_page", "next_page"):
        layout = result["site_view"]["layout"][page]
        assert layout["client"] == layout["wide"] == layout["inner_box"] == 1280, layout
        assert layout["scrolled_to"] == 600, layout
