"""The first screen's numbers, on pages whose answers are known.

Every page here is served from this machine to a real browser, because what is
being tested is what Chromium says is on screen: a box is not a thing anyone can
see. Each page is laid out in round numbers so that the right answer can be
worked out by hand, and the tests that matter most are the ones where a box-based
reading would give the wrong one: a carousel's hidden slides, a picture behind a
solid panel, text below the fold.
"""

import asyncio
import base64
import concurrent.futures
import http.server
import json
import threading
from collections.abc import Awaitable, Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from playwright.async_api import Page

from backend.estimator import page_model
from backend.perception.overlays import MIN_STACK_LEVEL
from tools.evaluation import overwhelm_index as index
from tools.evaluation import visual_features as visual
from tools.rating.capture import new_run

WIDTH, HEIGHT = 1280, 800
AREA = WIDTH * HEIGHT
#: One pixel of red, stretched to whatever box it is given.
RED = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
       "z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
#: Two pixels wide, so that `naturalWidth` says it really loaded.
WIDE = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4"
        "nGP8z8DAwMDAxAAAAOwAA5+UZ6sAAAAASUVORK5CYII=")
PLAIN = "<!doctype html><style>html,body{margin:0;padding:0;background:#fff}</style>"


class Pages(http.server.BaseHTTPRequestHandler):
    """Pages by path."""

    pages: dict[str, tuple[int, str]] = {}

    def do_GET(self) -> None:  # noqa: N802 - the name http.server calls
        status, body = Pages.pages.get(self.path, (404, "not here"))
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain" if self.path == "/robots.txt"
                         else "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_: object) -> None:
        pass


@pytest.fixture
def host() -> Iterator[str]:
    Pages.pages = {"/robots.txt": (200, "User-agent: *\nAllow: /\n")}
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Pages)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def in_browser(step: Callable[[Page], Awaitable[Any]]) -> Any:
    """On a thread of its own: a sync Playwright session may hold this one."""
    found: list[Any] = []

    async def noted(page: Page) -> None:
        found.append(await step(page))

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(asyncio.run, visual.browse(noted)).result()
    return found[0]


def read_page(host: str, html: str, path: str = "/page") -> dict[str, Any]:
    """The first-screen read of one page."""
    Pages.pages[path] = (200, html)

    async def step(page: Page) -> dict[str, Any]:
        await page.goto(host + path, wait_until="load")
        await page.wait_for_timeout(150)
        return visual.on_screen(await page.evaluate(
            visual.VISUAL_JS, [visual.STEP, MIN_STACK_LEVEL, visual.NAMED]))

    return in_browser(step)


def box(left: int, top: int, width: int, height: int, more: str = "") -> str:
    return (f"position:absolute;left:{left}px;top:{top}px;width:{width}px;height:{height}px;"
            f"{more}")


# --- image_area ------------------------------------------------------------------


def test_a_picture_counts_for_the_share_of_the_screen_it_fills(host: str) -> None:
    html = f"{PLAIN}<img src='{WIDE}' style='{box(0, 0, 640, 400)}'>"
    assert read_page(host, html)["image_area"] == pytest.approx(0.25, abs=0.01)


def test_a_page_of_words_has_no_image_area(host: str) -> None:
    assert read_page(host, f"{PLAIN}<p>Only words here.</p>")["image_area"] == 0


@pytest.mark.parametrize("element", [
    f"<div style='{box(0, 0, 640, 800, f'background-image:url({WIDE})')}'></div>",
    f"<canvas style='{box(0, 0, 640, 800)}'></canvas>",
    f"<video style='{box(0, 0, 640, 800)}'></video>",
    f"<svg style='{box(0, 0, 640, 800)}'><rect width='100%' height='100%'/></svg>",
], ids=["background", "canvas", "video", "svg"])
def test_every_kind_of_picture_counts(host: str, element: str) -> None:
    assert read_page(host, PLAIN + element)["image_area"] == pytest.approx(0.5, abs=0.01)


def test_a_picture_a_slider_has_made_untouchable_is_still_a_picture(host: str) -> None:
    """Hit testing skips `pointer-events: none`, which is how slider plugins lay
    out their slides: Quaid-i-Azam's page, nearly all photograph, read 0.01."""
    style = box(0, 0, 1280, 400, f"pointer-events:none;background-image:url({WIDE})")
    above = box(0, 0, 1280, 400, "z-index:3")
    html = f"{PLAIN}<div style='{style}'></div><a href='/x' style='{above}'></a>"
    assert read_page(host, html)["image_area"] == pytest.approx(0.5, abs=0.01)


def test_the_read_leaves_the_page_as_it_found_it(host: str) -> None:
    Pages.pages["/left"] = (200, f"{PLAIN}<p style='pointer-events:none'>x</p>")

    async def step(page: Page) -> list[Any]:
        await page.goto(host + "/left", wait_until="load")
        before = await page.evaluate("document.documentElement.outerHTML")
        await page.evaluate(visual.VISUAL_JS, [visual.STEP, MIN_STACK_LEVEL, visual.NAMED])
        return [before, await page.evaluate("document.documentElement.outerHTML"),
                await page.evaluate("getComputedStyle(document.querySelector('p')).pointerEvents")]

    before, after, events = in_browser(step)
    assert before == after and events == "none"


def test_a_gradient_is_not_a_picture(host: str) -> None:
    style = box(0, 0, 1280, 800, "background-image:linear-gradient(#fff,#eee)")
    assert read_page(host, f"{PLAIN}<div style='{style}'></div>")["image_area"] == 0


def test_two_overlapping_pictures_count_once(host: str) -> None:
    html = (f"{PLAIN}<img src='{WIDE}' style='{box(0, 0, 640, 800)}'>"
            f"<img src='{WIDE}' style='{box(0, 0, 640, 800)}'>")
    assert read_page(host, html)["image_area"] == pytest.approx(0.5, abs=0.01)


def test_a_picture_below_the_first_screen_does_not_count(host: str) -> None:
    html = f"{PLAIN}<img src='{WIDE}' style='{box(0, 900, 1280, 800)}'>"
    assert read_page(host, html)["image_area"] == 0


def test_a_picture_half_on_screen_counts_for_that_half(host: str) -> None:
    html = f"{PLAIN}<img src='{WIDE}' style='{box(0, 400, 1280, 800)}'>"
    assert read_page(host, html)["image_area"] == pytest.approx(0.5, abs=0.01)


def test_the_slides_a_carousel_is_not_showing_do_not_count(host: str) -> None:
    """Its other slides have boxes on the screen; a box-based reading says full."""
    html = (f"{PLAIN}<div style='{box(0, 0, 640, 400, 'overflow:hidden')}'>"
            f"<img src='{WIDE}' style='{box(0, 0, 640, 400)}'>"
            f"<img src='{WIDE}' style='{box(640, 0, 640, 400)}'></div>"
            f"<img src='{WIDE}' style='{box(640, 0, 640, 800, 'opacity:0')}'>")
    assert read_page(host, html)["image_area"] == pytest.approx(0.25, abs=0.01)


def test_a_picture_behind_a_solid_panel_is_not_on_screen(host: str) -> None:
    html = (f"{PLAIN}<img src='{WIDE}' style='{box(0, 0, 1280, 800)}'>"
            f"<div style='{box(0, 0, 640, 800, 'background:#fff')}'></div>")
    assert read_page(host, html)["image_area"] == pytest.approx(0.5, abs=0.01)


def test_a_picture_behind_a_see_through_backdrop_still_shows(host: str) -> None:
    html = (f"{PLAIN}<img src='{WIDE}' style='{box(0, 0, 1280, 800)}'>"
            f"<div style='{box(0, 0, 1280, 800, 'background:rgba(0,0,0,.5)')}'></div>")
    assert read_page(host, html)["image_area"] == pytest.approx(1, abs=0.01)


def test_a_backdrop_faded_as_a_whole_is_still_see_through(host: str) -> None:
    """Bootstrap's: solid black, at opacity .5. MCB's hero read 0.01 behind one."""
    html = (f"{PLAIN}<img src='{WIDE}' style='{box(0, 0, 1280, 800)}'>"
            f"<div style='{box(0, 0, 1280, 800, 'background:#000;opacity:.5')}'></div>")
    assert read_page(host, html)["image_area"] == pytest.approx(1, abs=0.01)


def test_words_over_a_picture_leave_it_a_picture(host: str) -> None:
    html = (f"{PLAIN}<div style='{box(0, 0, 1280, 800, f'background-image:url({WIDE})')}'>"
            "<h1>Words across the top of it</h1></div>")
    assert read_page(host, html)["image_area"] == pytest.approx(1, abs=0.01)


def test_a_picture_that_did_not_load_is_not_one(host: str) -> None:
    html = f"{PLAIN}<img src='/nothing-here.png' style='{box(0, 0, 1280, 800)}'>"
    assert read_page(host, html)["image_area"] == 0


# --- covered ---------------------------------------------------------------------


def test_a_chat_bubble_covers_exactly_its_own_share(host: str) -> None:
    style = "position:fixed;right:0;bottom:0;width:320px;height:200px;background:#eee"
    found = read_page(host, f"{PLAIN}<div id='chat' style='{style}'>Ask us</div>")
    assert found["covered"] == pytest.approx(320 * 200 / AREA, abs=0.005)
    assert found["covering"][0]["element"] == "div#chat fixed"


def test_a_sticky_banner_counts(host: str) -> None:
    style = "position:sticky;top:0;height:80px;background:#ffd"
    html = f"{PLAIN}<div style='{style}'>Notice</div><div style='height:3000px'></div>"
    assert read_page(host, html)["covered"] == pytest.approx(0.1, abs=0.005)


def test_a_modal_and_its_backdrop_cover_the_page(host: str) -> None:
    html = (f"{PLAIN}<p>The page.</p><div style='position:fixed;inset:0;"
            "background:rgba(0,0,0,.5)'><div style='margin:200px auto;width:400px;"
            "background:#fff'>A dialog</div></div>")
    assert read_page(host, html)["covered"] == pytest.approx(1, abs=0.005)


def test_a_small_thing_still_counts_where_overlay_detection_would_not(host: str) -> None:
    """`overlays.analyse` has a floor of 27% of the screen; this has none."""
    style = "position:fixed;left:0;top:0;width:640px;height:80px;background:#eee"
    assert read_page(host, f"{PLAIN}<div style='{style}'>x</div>")["covered"] == pytest.approx(
        0.05, abs=0.005)


def test_stacked_counts_by_the_rule_overlay_detection_uses(host: str) -> None:
    high = box(0, 0, 640, 800, f"z-index:{MIN_STACK_LEVEL};background:#eee")
    low = box(640, 0, 640, 800, f"z-index:{MIN_STACK_LEVEL - 1};background:#eee")
    html = f"{PLAIN}<div style='{high}'>on top</div><div style='{low}'>in the page</div>"
    assert read_page(host, html)["covered"] == pytest.approx(0.5, abs=0.01)


def test_a_sliders_own_layers_are_not_covering_the_page(host: str) -> None:
    """Stacked inside the page, over its own slide: a slide is not a pop-up. This
    put 0.79 on Quaid-i-Azam's page and 0.72 on Ufone's with nothing on top of them."""
    layer = box(0, 0, 1280, 500, "z-index:20")
    html = (f"{PLAIN}<section style='position:relative;height:500px'><img src='{WIDE}' "
            f"style='{box(0, 0, 1280, 500)}'><a href='/x' style='{layer}'></a></section>")
    assert read_page(host, html)["covered"] == 0


def test_a_decorative_layer_nobody_can_touch_is_not_a_cover(host: str) -> None:
    style = "position:fixed;inset:0;pointer-events:none"
    assert read_page(host, f"{PLAIN}<div style='{style}'></div><p>x</p>")["covered"] == 0


def test_a_page_with_nothing_on_top_of_it_is_not_covered(host: str) -> None:
    assert read_page(host, f"{PLAIN}<h1>Plain</h1>")["covered"] == 0


def test_a_fixed_body_is_a_page_holding_still_not_a_cover(host: str) -> None:
    html = f"{PLAIN}<body style='position:fixed;width:100%'><h1>Scroll-locked</h1></body>"
    assert read_page(host, html)["covered"] == 0


# --- the links and text a person can see ------------------------------------------


def lines(count: int, top: int = 0) -> str:
    return "".join(f"<div style='{box(0, top + 40 * n, 400, 40)}'><a href='/{n}'>Go {n}</a></div>"
                   for n in range(count))


def test_links_below_the_first_screen_do_not_count(host: str) -> None:
    html = PLAIN + lines(30)  # 40px each: twenty on an 800px screen, ten below it
    assert read_page(host, html)["first_screen_links"] == 20


def test_links_behind_a_solid_panel_cannot_be_seen(host: str) -> None:
    html = (PLAIN + lines(10)
            + f"<div style='{box(0, 0, 1280, 800, 'background:#fff;z-index:9')}'>Wait</div>")
    assert read_page(host, html)["first_screen_links"] == 0


def test_links_in_a_closed_menu_do_not_count(host: str) -> None:
    hidden = "".join(f"<a href='/{n}'>Hidden {n}</a>" for n in range(5))
    html = (f"{PLAIN}<ul style='display:none'>{hidden}</ul>"
            f"<div style='height:0;overflow:hidden'>{hidden}</div>"
            f"<div style='{box(0, 0, 200, 40, 'overflow:hidden')}'>"
            f"<a href='/seen'>Seen</a><div style='height:400px'></div>"
            f"<a href='/clipped'>Clipped</a></div>")
    assert read_page(host, html)["first_screen_links"] == 1


def test_a_picture_that_is_a_link_is_a_link(host: str) -> None:
    html = f"{PLAIN}<a href='/x'><img src='{WIDE}' width='200' height='200'></a>"
    assert read_page(host, html)["first_screen_links"] == 1


def test_a_page_of_text_reads_as_its_characters_per_area(host: str) -> None:
    """In `text_density`'s own unit, so the two can be set side by side."""
    html = f"{PLAIN}<p style='margin:0;word-break:break-all'>{'x' * 1024}</p>"
    assert read_page(host, html)["first_screen_text"] == pytest.approx(1.0, abs=0.01)


def test_a_line_running_off_the_side_counts_for_what_is_on_screen(host: str) -> None:
    html = f"{PLAIN}<p style='margin:0;font:20px monospace;white-space:nowrap'>{'x' * 1280}</p>"
    assert read_page(host, html)["first_screen_text"] < 0.3


def test_only_the_lines_on_screen_count(host: str) -> None:
    """Half a long paragraph is on screen. `text_density` counts all of it."""
    style = "margin:0;font:20px/40px monospace;width:600px;word-break:break-all"
    text = "x" * 2000  # 50 characters a line, so 40 lines, twenty of them on screen
    found = read_page(host, f"{PLAIN}<p style='{style}'>{text}</p>")
    assert found["first_screen_text"] == pytest.approx(1000 / (AREA / 1000), rel=0.1)


def test_text_behind_a_solid_panel_cannot_be_read(host: str) -> None:
    html = (f"{PLAIN}<p>{'words ' * 100}</p>"
            f"<div style='{box(0, 0, 1280, 800, 'background:#fff')}'></div>")
    assert read_page(host, html)["first_screen_text"] == 0


def test_text_in_a_script_is_not_on_screen(host: str) -> None:
    html = f"{PLAIN}<script>const a = '{'x' * 500}';</script><noscript>{'y' * 500}</noscript>"
    assert read_page(host, html)["first_screen_text"] == 0


def test_text_a_page_has_made_untouchable_is_still_seen(host: str) -> None:
    style = "pointer-events:none;margin:0;word-break:break-all"
    html = f"{PLAIN}<p style='{style}'>{'x' * 1024}</p>"
    assert read_page(host, html)["first_screen_text"] == pytest.approx(1.0, abs=0.01)


def test_a_page_scrolled_by_a_drive_is_read_where_it_is(host: str) -> None:
    """The picture is of wherever the drive left it, and so are these numbers."""
    Pages.pages["/long"] = (200, f"{PLAIN}<img src='{WIDE}' style='{box(0, 1000, 1280, 800)}'>"
                                 "<div style='height:3000px'></div>")

    async def step(page: Page) -> dict[str, Any]:
        await page.goto(host + "/long", wait_until="load")
        await page.evaluate("window.scrollTo(0, 1000)")
        return visual.on_screen(await page.evaluate(
            visual.VISUAL_JS, [visual.STEP, MIN_STACK_LEVEL, visual.NAMED]))

    assert in_browser(step)["image_area"] == pytest.approx(1, abs=0.01)


def test_a_read_at_any_other_size_is_refused() -> None:
    read = {"viewport": [1263, 800], "image_area": 0, "covered": 0, "first_screen_links": 0,
            "first_screen_characters": 0, "covering": []}
    with pytest.raises(visual.Unmeasured, match="1263"):
        visual.on_screen(read)


# --- motion ----------------------------------------------------------------------


STILL = f"{PLAIN}<h1>Nothing moves here</h1>"
#: The left half of the screen swaps colour, once, after 300ms.
SWAPS = (f"{PLAIN}<div id='a' style='{box(0, 0, 640, 800, 'background:#000')}'></div>"
         "<script>setTimeout(() => document.getElementById('a').style.background = '#fff', 300)"
         "</script>")
#: A fifth of the screen changes every 100ms, for as long as anyone looks.
RUNS = (f"{PLAIN}<div id='a' style='{box(0, 0, 256, 800, 'background:#000')}'></div><script>"
        "let on = 0; setInterval(() => { on = (on + 1) % 2;"
        " document.getElementById('a').style.background = on ? '#fff' : '#000'; }, 100)</script>")
#: Changes only after a second, so a short gap misses it and a longer one does not.
LATE = (f"{PLAIN}<div id='a' style='{box(0, 0, 640, 800, 'background:#000')}'></div>"
        "<script>setTimeout(() => document.getElementById('a').style.background = '#fff', 900)"
        "</script>")


def watched(host: str, html: str, gap_s: float = 0.6) -> dict[str, Any]:
    Pages.pages["/moves"] = (200, html)

    async def step(page: Page) -> dict[str, Any]:
        await page.goto(host + "/moves", wait_until="load")
        return await visual.observed(page, await page.screenshot(), gap_s)

    return in_browser(step)


def test_a_page_that_holds_still_has_no_motion(host: str) -> None:
    found = watched(host, STILL)
    assert found["motion"] == 0 and found["motion_late"] == 0


def test_motion_is_the_share_of_the_screen_that_changed(host: str) -> None:
    assert watched(host, SWAPS)["motion"] == pytest.approx(0.5, abs=0.01)


def test_the_later_capture_says_what_the_gap_missed(host: str) -> None:
    found = watched(host, LATE)
    assert found["motion"] == 0
    assert found["motion_late"] == pytest.approx(0.5, abs=0.01)


def test_the_gap_is_recorded_as_it_was_not_as_it_was_meant(host: str) -> None:
    found = watched(host, STILL)
    assert found["gap_s"] >= 0.6 and found["late_gap_s"] >= 1.2


def test_the_gap_between_captures_is_three_seconds() -> None:
    assert visual.GAP_S == 3.0


def pixels(host: str, one: str, two: str) -> float | None:
    """How much two pages' pictures differ, each taken at `size`."""
    Pages.pages["/one"], Pages.pages["/two"] = (200, one), (200, two)

    async def step(page: Page) -> float | None:
        await page.goto(host + "/one", wait_until="load")
        first = await page.screenshot()
        await page.goto(host + "/two", wait_until="load")
        return await visual.changed(page, first, await page.screenshot())

    return in_browser(step)


def test_a_change_too_small_to_see_is_not_a_change(host: str) -> None:
    one = f"{PLAIN}<div style='{box(0, 0, 1280, 800, 'background:#808080')}'></div>"
    two = f"{PLAIN}<div style='{box(0, 0, 1280, 800, 'background:#858585')}'></div>"
    assert pixels(host, one, two) == 0


def test_pictures_of_different_sizes_are_not_compared(host: str) -> None:
    async def step(page: Page) -> float | None:
        await page.goto("about:blank")
        small = base64.b64decode(RED.split(",")[1])
        wide = base64.b64decode(WIDE.split(",")[1])
        return await visual.changed(page, small, wide)

    assert in_browser(step) is None


# --- the rated pages: read, never rewritten -----------------------------------------


def test_a_rated_page_is_read_beside_the_picture_people_saw(host: str, tmp_path: Path) -> None:
    rated, into = tmp_path / "rated", tmp_path / "into"
    rated.mkdir()
    into.mkdir()
    Pages.pages["/same"] = (200, f"{PLAIN}<h1>The same page</h1>")
    url = f"{host}/same"
    name = f"{visual.page_id(url, 'as it loads')}.png"

    async def take(page: Page) -> None:
        await page.goto(url, wait_until="load")
        await page.add_style_tag(content="html{scrollbar-width:none}")
        (rated / name).write_bytes(await page.screenshot())

    in_browser(take)
    before = (rated / name).read_bytes()

    async def step(page: Page) -> dict[str, Any]:
        return await visual.read_rated(page, url, None, "public", new_run(), into, rated,
                                       gap_s=0.2)

    row = in_browser(step)

    assert "error" not in row
    assert row["drift"] == 0
    assert (rated / name).read_bytes() == before
    assert set(row["nine_now"]) == set(page_model.FEATURES)
    assert (into / name).exists()


def test_a_page_that_has_changed_since_it_was_rated_says_how_much(host: str, tmp_path: Path) -> None:
    rated, into = tmp_path / "rated", tmp_path / "into"
    rated.mkdir()
    into.mkdir()
    Pages.pages["/moved"] = (200, f"{PLAIN}<div style='{box(0, 0, 640, 800, 'background:#000')}'>")
    url = f"{host}/moved"
    name = f"{visual.page_id(url, 'as it loads')}.png"

    async def take(page: Page) -> None:
        await page.goto(url, wait_until="load")
        (rated / name).write_bytes(await page.screenshot())

    in_browser(take)
    Pages.pages["/moved"] = (200, f"{PLAIN}<h1>Something else</h1>")

    async def step(page: Page) -> dict[str, Any]:
        return await visual.read_rated(page, url, None, "public", new_run(), into, rated,
                                       gap_s=0.2)

    assert in_browser(step)["drift"] >= 0.45


def test_a_rated_page_robots_forbids_is_never_opened(host: str, tmp_path: Path) -> None:
    Pages.pages["/robots.txt"] = (200, "User-agent: *\nDisallow: /\n")
    Pages.pages["/page"] = (200, "<p>never read</p>")

    async def step(page: Page) -> dict[str, Any]:
        return await visual.read_rated(page, f"{host}/page", None, "public", new_run(), tmp_path,
                                       tmp_path)

    row = in_browser(step)
    assert "disallowed" in row["error"] and "image_area" not in row


def test_our_own_replicas_are_not_asked_for_robots_rules(host: str, tmp_path: Path) -> None:
    Pages.pages["/robots.txt"] = (200, "User-agent: *\nDisallow: /\n")
    Pages.pages["/page"] = (200, f"{PLAIN}<p>ours</p>")

    async def step(page: Page) -> dict[str, Any]:
        return await visual.read_rated(page, f"{host}/page", None, "ours", new_run(), tmp_path,
                                       tmp_path, gap_s=0.1)

    assert "error" not in in_browser(step)


def test_a_page_that_cannot_be_read_is_a_row_not_a_crash(host: str, tmp_path: Path) -> None:
    async def step(page: Page) -> dict[str, Any]:
        return await visual.read_rated(page, "http://127.0.0.1:9/", None, "ours", new_run(),
                                       tmp_path, tmp_path)

    assert "error" in in_browser(step)


def test_every_rated_page_on_the_list_has_a_picture_recorded() -> None:
    """The list read is the list rated, so that every rated page gets a row."""
    data = json.loads(visual.MANIFEST.read_text(encoding="utf-8"))
    rated = {(row["url"], row["state"]) for row in data["pages"]}
    listed = {(url, visual.name_of(drive)) for url, drive, _ in visual.STARTER_LIST}
    assert listed == rated


# --- the sites: only those the index scored, by the index's own checks ---------------


def test_only_the_sites_the_index_scored_are_visited(tmp_path: Path) -> None:
    results = tmp_path / "results.json"
    first, second = index.SITES[:2]
    results.write_text(json.dumps({"results": [
        {"site": first.name, "status": "scored"}, {"site": second.name, "status": "skipped"},
        {"site": index.SITES[2].name, "status": "failed"}]}), encoding="utf-8")
    assert visual.sites_to_visit(results) == (first,)


def surveyed(host: str, tmp_path: Path, html: str) -> dict[str, Any]:
    Pages.pages["/"] = (200, html)
    model = page_model.load()
    assert model is not None
    site = index.Site("A site", index.UTILITY, f"{host}/", "To test with")

    async def step(page: Page) -> dict[str, Any]:
        async def quick(page: Page, shot: dict, into: Path) -> dict[str, Any]:
            return await visual.observed(page, (into / shot["file"]).read_bytes(), 0.1)

        return await index.measure(page, site, new_run(), model, index.corpus_ranges(),
                                   tmp_path, extra=quick)

    return in_browser(step)


def test_a_site_gets_all_fourteen_from_one_load(host: str, tmp_path: Path) -> None:
    html = ("<!doctype html><title>A site</title><div style='height:300px;background:#246'>"
            "</div>" + "<p><a href='/x'>A link with some words</a></p>" * 30 + "<p>" + "Plain sentences about the service. " * 40 + "</p>")
    row = surveyed(host, tmp_path, html)
    assert row["status"] == "scored", row["note"]
    for name in (*page_model.FEATURES, *page_model.VISUAL_FEATURES):
        assert name in row, name
    assert (tmp_path / row["screenshot"]).exists()


def test_a_refusal_is_not_measured(host: str, tmp_path: Path) -> None:
    row = surveyed(host, tmp_path, "<title>Access denied</title><p>No.</p>")
    assert row["status"] == "failed" and "image_area" not in row


def test_the_browser_is_set_up_as_the_rating_pictures_were(host: str) -> None:
    async def step(page: Page) -> list[Any]:
        return [page.viewport_size, await page.evaluate("devicePixelRatio"),
                await page.evaluate("navigator.userAgent")]

    size, ratio, agent = in_browser(step)
    assert size == {"width": 1280, "height": 800} and ratio == 1
    assert agent == visual.UA


# --- the record ---------------------------------------------------------------------


def test_each_list_is_saved_without_touching_the_other(tmp_path: Path) -> None:
    path = tmp_path / "visual.json"
    visual.save(path, "rated", [{"id": "a"}], {"id": "r1"}, {"taken_at": "then"})
    visual.save(path, "sites", [{"site": "b"}], {"id": "r2"}, {"taken_at": "now"})
    whole = visual.read_record(path)
    assert whole["rated"]["rows"] == [{"id": "a"}] and whole["sites"]["rows"] == [{"site": "b"}]
    assert whole["definitions"]["gap_s"] == visual.GAP_S
    assert whole["definitions"]["features"] == list(page_model.VISUAL_FEATURES)


def test_nothing_it_writes_to_is_a_rating_picture_or_the_model() -> None:
    assert visual.OUT.is_relative_to(visual.REPO / ".scratch")
    assert visual.RECORD.name == "visual_features.json"
    assert not visual.OUT.is_relative_to(visual.PAGES)
