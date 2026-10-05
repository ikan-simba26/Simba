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
    # And for someone with history: three remembered goals, as long as a card
    # holds. Not measured until 2026-09-30, when six cards had put the box
    # below the bottom of the window at every scale.
    history = result["overlay_with_history"]
    assert history["cards"] == 3, history
    assert history["box_in_viewport"], history
    assert not history["scrolls"], history
    assert history["smallest_text_px"] >= 20, history
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
    # Perception's page is exactly what it was.
    assert result["site_view"]["inner"] == [1280, 800], result["site_view"]
    # And a page that scrolls lays out at the full 1280px, inner scroll boxes
    # too, as it does headless — on the first page and the next — and still
    # scrolls. Until 2026-09-30 the host laid it out at 1263px.
    for page in ("first_page", "next_page"):
        layout = result["site_view"]["layout"][page]
        assert layout["client"] == layout["wide"] == layout["inner_box"] == 1280, layout
        assert layout["scrolled_to"] == 600, layout
