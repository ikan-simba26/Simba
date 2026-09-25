"""The window fits the screen, and the site view stays 1280x800.

A 1920x1080 laptop at 150% has a work area of 1280x672 in Windows' units, and
a fixed 1280x800 window put the home screen's text box below the bottom of
it. `frontend/electron/main.ts` now fits the window to the work area and
zooms the overlay by the same factor; the site view is left alone. This
launches the real host at forced display scales and checks all four promises
from outside it (`tools/evaluation/display_fit_run.py` does the measuring).

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
    # The overlay lays out at its design size at every scale, a rounding
    # pixel either way.
    width, height = result["overlay"]["inner"]
    assert abs(width - 1280) <= 1 and abs(height - 800) <= 1, result["overlay"]
    # The text box is on screen with nothing to scroll.
    assert result["overlay"]["box_in_viewport"], result["overlay"]
    assert not result["overlay"]["scrolls"], result["overlay"]
    # Perception's page is exactly what it was.
    assert result["site_view"]["inner"] == [1280, 800], result["site_view"]
