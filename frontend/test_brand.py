"""The brand: the kit in the repository, the icon and the title, the logo while
SIMBA opens, and the small logo on the home screen and nowhere else (2026-11-02).

The logo shown while opening is the part with a failure to it. `run.ps1` and
`run.sh` start the window first, since the backend attaches to it, so in every
real start the overlay's first attempt fails while the backend is still
importing, and nothing tried again. A logo waiting on that attempt would stay up
for good; one leaving when it failed would leave with nothing connected. These
start the backend after the page, as a launcher does, and also never.

The tests' builds turn the logo off (`VITE_SIMBA_SPLASH=0`), as they do the
welcome, and these turn it back on per page. The host's own windows are measured
by `tools/evaluation/display_fit_run.py`.
"""

import asyncio
import json
import re
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import websockets
from playwright.sync_api import Browser, Page, Playwright

from frontend.test_home import BOX, SIZES, History
from frontend.test_terminal_states import (  # noqa: F401 - `backend`, `overlay`: fixtures
    AWAIT_RESPONSE, ENDINGS, GOAL, Backend, backend, overlay, reach,
)

REPO = Path(__file__).resolve().parents[1]
KIT = REPO / "assets" / "brand"
DERIVED = KIT / "derived"

#: The two themes, as the operating system says them.
THEMES = ("light", "dark")

SPLASH_ON = "window.__simbaSplash = true"

LONG_GOALS = ["Find trains from Lahore Cantt to Rawalpindi on 2026-10-01.",
              "Find the amount due for reference number 04141234567890."]


@pytest.fixture(scope="module")
def browser(playwright_instance: Playwright) -> Iterator[Browser]:
    browser = playwright_instance.chromium.launch()
    yield browser
    browser.close()


@pytest.fixture(scope="module")
def offers() -> History:
    return History()


def free_port() -> int:
    with socket.socket() as held:
        held.bind(("127.0.0.1", 0))
        return held.getsockname()[1]


def kept_page(browser: Browser, theme: str = "light", size: str = "100%", **options) -> Page:
    width, height, scale = SIZES[size]
    context = browser.new_context(viewport={"width": width, "height": height},
                                  device_scale_factor=scale, color_scheme=theme, **options)
    return context.new_page()


def serve_late(port: int, after: float, goals: list[str], first_word: float = 0) -> None:
    """A backend that comes up `after` seconds from now, and says hello
    `first_word` seconds after a connection opens."""
    def run() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def handler(ws):
            await asyncio.sleep(first_word)
            await ws.send(json.dumps({
                "v": 1, "type": "history.offered", "task_id": "t_brand", "seq": 1, "ts": 0,
                "payload": {"goals": [{"goal": g, "site": "127.0.0.1"} for g in goals]},
            }))
            try:
                async for _ in ws:
                    pass
            except websockets.ConnectionClosed:
                return

        async def main() -> None:
            await asyncio.sleep(after)
            await websockets.serve(handler, "127.0.0.1", port)
            await asyncio.Future()

        loop.run_until_complete(main())

    threading.Thread(target=run, daemon=True).start()


def splash_shown(page: Page) -> bool:
    return page.get_by_test_id("splash").count() > 0


def served(page: Page, address: str) -> str:
    """The file the build really serves: its name alone cannot tell a derived
    logo from the kit's, since they share one."""
    return page.evaluate("(address) => fetch(address).then((answer) => answer.text())", address)


# --- the kit ----------------------------------------------------------------


def test_the_kit_is_all_here_with_its_readme() -> None:
    names = {path.relative_to(KIT).as_posix() for path in KIT.rglob("*")
             if path.is_file() and "derived" not in path.parts}

    assert len(names) == 28
    assert "README.txt" in names
    for variant in ("horizontal", "horizontal-dark", "stacked", "stacked-dark"):
        assert f"simba-logo-{variant}.svg" in names


def icon_sizes(path: Path) -> list[int]:
    data = path.read_bytes()
    assert data[:4] == b"\x00\x00\x01\x00", "not an icon file"
    count = int.from_bytes(data[4:6], "little")
    return [data[6 + 16 * index] or 256 for index in range(count)]


def test_the_windows_icon_holds_every_size_the_taskbar_asks_for() -> None:
    assert {16, 24, 32, 48, 256} <= set(icon_sizes(KIT / "simba-app-icon.ico"))


def text(path: Path) -> str:
    """As written: a clone on Windows may have turned its line endings round."""
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def without(svg: str, pattern: str) -> str:
    kept, removed = re.subn(pattern, "", svg, count=1)
    assert removed == 1, pattern
    return kept


BACKGROUND = r'<rect [^>]*fill="#0F1A19"[^>]*/>\s*'
TAGLINE_LIGHT = r'<path [^>]*fill="#55645F"[^>]*/>\s*'
TAGLINE_DARK = r'<path [^>]*fill="#9FB2AC"[^>]*/>\s*'


@pytest.mark.parametrize("name, source, parts", [
    ("simba-logo-stacked-dark.svg", "simba-logo-stacked-dark.svg", [BACKGROUND]),
    ("simba-logo-horizontal-dark.svg", "simba-logo-horizontal-dark.svg", [BACKGROUND]),
    ("simba-logo-horizontal-small.svg", "simba-logo-horizontal.svg", [TAGLINE_LIGHT]),
    ("simba-logo-horizontal-small-dark.svg", "simba-logo-horizontal-dark.svg",
     [BACKGROUND, TAGLINE_DARK]),
])
def test_a_derived_logo_is_the_kits_with_one_thing_taken_out(
    name: str, source: str, parts: list[str],
) -> None:
    """The drawings stay the kit's: a new kit must not leave these behind unseen."""
    expected = text(KIT / source)
    for part in parts:
        expected = without(expected, part)

    assert text(DERIVED / name) == expected


def luminance(colour: str) -> float:
    parts = [int(colour[at:at + 2], 16) / 255 for at in (1, 3, 5)]
    r, g, b = (v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in parts)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(one: str, two: str) -> float:
    light, dark = sorted((luminance(one), luminance(two)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


@pytest.mark.parametrize("file, canvases", [
    ("simba-logo-horizontal-small.svg", ("#f5efe3", "#f4ede2")),
    ("simba-logo-horizontal-small-dark.svg", ("#0b1817", "#14100c")),
    ("simba-logo-stacked-dark.svg", ("#0b1817", "#14100c")),
])
def test_every_colour_in_a_logo_stands_off_its_canvas(file: str, canvases: tuple[str, ...]) -> None:
    """3:1, what a control's edge is held to (`test_contrast.py`), on both
    palettes' canvases. Nothing here is the same as a canvas: nothing depends
    on it being filled behind."""
    fills = set(re.findall(r'fill="(#[0-9A-Fa-f]{6})"', text(DERIVED / file)))

    assert fills
    for fill in fills:
        for canvas in canvases:
            assert contrast(fill, canvas) >= 3, (fill, canvas)


# --- the window -------------------------------------------------------------


def test_the_window_is_called_simba_and_wears_the_icon() -> None:
    host = text(REPO / "frontend" / "electron" / "main.ts")

    assert 'title: "simba"' in host
    assert "icon: ICON" in host
    assert '"simba-app-icon.ico"' in host and '"simba-app-icon-512.png"' in host
    assert "<title>simba</title>" in text(REPO / "frontend" / "index.html")
    # Named from `dist-electron`, where the host runs.
    assert 'path.join(here, "..", "..", "assets", "brand")' in host


# --- the logo while opening -------------------------------------------------


@pytest.mark.parametrize("theme, file", [("light", "simba-logo-stacked"),
                                         ("dark", "simba-logo-stacked-dark")])
@pytest.mark.parametrize("size", SIZES)
def test_the_logo_is_centred_whole_and_the_themes_own(
    browser: Browser, overlay: str, theme: str, file: str, size: str,  # noqa: F811
) -> None:
    page = kept_page(browser, theme, size)
    page.add_init_script(SPLASH_ON)
    try:
        # A port nothing is on: it stays up for as long as this needs.
        page.goto(f"{overlay}?ws=ws://127.0.0.1:{free_port()}")
        page.get_by_test_id("splash").wait_for(timeout=15000)
        logo = page.get_by_test_id("splash").get_by_role("img", name="simba")
        logo.wait_for(timeout=5000)
        page.wait_for_timeout(800)  # the fade in

        shown = page.evaluate("""() => {
            const img = document.querySelector('[data-testid=splash] img');
            const box = img.getBoundingClientRect();
            return {src: img.currentSrc, left: box.left, right: innerWidth - box.right,
                    top: box.top, bottom: innerHeight - box.bottom, loaded: img.naturalWidth,
                    scrolls: document.scrollingElement.scrollHeight > innerHeight};
        }""")

        assert shown["loaded"] > 0, shown
        assert re.search(rf"/{file}-[^/]*\.svg$", shown["src"]), shown
        assert "<rect" not in served(page, shown["src"]), "stands in a box"
        assert abs(shown["left"] - shown["right"]) <= 1, shown
        assert abs(shown["top"] - shown["bottom"]) <= 1, shown
        assert shown["top"] > 0 and shown["left"] > 0, shown
        assert not shown["scrolls"], shown
    finally:
        page.context.close()


def test_nothing_of_the_home_screen_is_behind_it(browser: Browser, overlay: str) -> None:  # noqa: F811
    """So its entrance is not spent where nobody can see it."""
    page = kept_page(browser)
    page.add_init_script(SPLASH_ON)
    try:
        page.goto(f"{overlay}?ws=ws://127.0.0.1:{free_port()}")
        page.get_by_test_id("splash").wait_for(timeout=15000)

        assert page.get_by_test_id("tile").count() == 0
        assert page.get_by_test_id("home-logo").count() == 0
    finally:
        page.context.close()


def test_it_waits_for_a_backend_that_starts_after_the_window(
    browser: Browser, overlay: str,  # noqa: F811
) -> None:
    """The order every real start has. The first attempt fails; tried again, the
    person's goals are on the home screen when it arrives. Until now a window
    opened first offered nothing until something was pressed."""
    page = kept_page(browser)
    page.add_init_script(SPLASH_ON)
    port = free_port()
    serve_late(port, after=2.5, goals=LONG_GOALS)
    try:
        page.goto(f"{overlay}?ws=ws://127.0.0.1:{port}")
        page.get_by_test_id("splash").wait_for(timeout=15000)
        page.wait_for_timeout(1500)
        assert splash_shown(page), "left before the backend came"

        page.get_by_role("textbox", name=BOX).wait_for(timeout=12000)

        # The first screen has no remembered goals since 2026-11-14: what it
        # offers is there whole, the three tasks, and is not changed by goals.
        assert page.get_by_test_id("remembered").count() == 0
        assert page.get_by_test_id("tile").count() == 3
    finally:
        page.context.close()


def test_the_home_screen_arrives_whole_after_a_slow_first_word(
    browser: Browser, overlay: str,  # noqa: F811
) -> None:
    """On a real start the socket opened seconds before the first message. A
    logo leaving on the socket showed a home screen that rearranged itself
    when the goals came."""
    page = kept_page(browser)
    page.add_init_script(SPLASH_ON)
    port = free_port()
    serve_late(port, after=0, goals=LONG_GOALS, first_word=3)
    try:
        page.goto(f"{overlay}?ws=ws://127.0.0.1:{port}")

        page.get_by_role("textbox", name=BOX).wait_for(timeout=12000)

        # Whole when the box is there, and not rearranged when the first word
        # comes (2026-11-14: nothing on the first screen depends on the goals).
        before = page.get_by_test_id("tile").count()
        page.wait_for_timeout(3500)
        assert before == page.get_by_test_id("tile").count() == 3
        assert page.get_by_test_id("remembered").count() == 0
    finally:
        page.context.close()


def test_it_stays_long_enough_not_to_flash(
    browser: Browser, overlay: str, offers: History,  # noqa: F811
) -> None:
    page = kept_page(browser)
    page.add_init_script(SPLASH_ON)
    offers.goals = []
    try:
        started = time.monotonic()
        page.goto(f"{overlay}?ws=ws://127.0.0.1:{offers.port}")
        page.get_by_test_id("splash").wait_for(timeout=15000)
        page.get_by_role("textbox", name=BOX).wait_for(timeout=15000)

        assert time.monotonic() - started >= 1.2
    finally:
        page.context.close()


def test_with_no_backend_at_all_the_home_screen_still_comes(
    browser: Browser, overlay: str,  # noqa: F811
) -> None:
    """What a person can press is never held behind a logo for good."""
    page = kept_page(browser)
    page.add_init_script(SPLASH_ON)
    try:
        started = time.monotonic()
        page.goto(f"{overlay}?ws=ws://127.0.0.1:{free_port()}")
        page.get_by_test_id("splash").wait_for(timeout=15000)

        page.get_by_role("textbox", name=BOX).wait_for(timeout=20000)
        arrived = time.monotonic() - started
        page.get_by_test_id("splash").wait_for(state="detached", timeout=5000)

        assert 14 <= arrived <= 18
    finally:
        page.context.close()


def test_it_keeps_trying_at_home_but_never_over_a_press(browser: Browser, overlay: str) -> None:  # noqa: F811
    """Until 2026-11-13 the window tried again only while the logo was up: a
    late attempt on the home screen would replace the connection a press had
    just opened, since `connect` closes whatever there is. By the advisor's
    direction (L) it now keeps trying on the home screen, and says so; what
    stops it replacing a press's connection is that it never tries while one
    is connecting or a goal has been asked (`store.keepConnected`), which the
    second half checks."""
    page = kept_page(browser)
    page.add_init_script(SPLASH_ON)
    attempts: list[float] = []
    page.on("websocket", lambda _: attempts.append(time.monotonic()))
    try:
        page.goto(f"{overlay}?ws=ws://127.0.0.1:{free_port()}")
        page.get_by_role("textbox", name=BOX).wait_for(timeout=20000)
        page.get_by_test_id("splash").wait_for(state="detached", timeout=5000)
        at_home = len(attempts)
        # Until it tries again, and for no longer than the backoff allows: a
        # refused attempt takes about 2.5s on Windows and the gap between
        # attempts grew to 10s in a whole-suite run, where a fixed 6s saw none
        # (2026-11-15).
        deadline = time.monotonic() + 25
        while len(attempts) <= at_home and time.monotonic() < deadline:
            page.wait_for_timeout(250)
        page.wait_for_timeout(1500)

        assert at_home >= 2, attempts
        assert len(attempts) > at_home, attempts  # it keeps trying
        gaps = [later - earlier for earlier, later in zip(attempts, attempts[1:])]
        assert min(gaps) > 0.9, gaps  # no more than about once a second

        # A press: its connection is the only one from then on.
        page.get_by_role("textbox", name=BOX).fill("hello")
        before = len(attempts)
        page.get_by_role("button", name="Start", exact=True).click()
        page.wait_for_timeout(1500)
        assert len(attempts) - before <= 1, attempts
    finally:
        page.context.close()


def test_under_reduced_motion_there_is_nothing(browser: Browser, overlay: str) -> None:  # noqa: F811
    """No logo, not for a frame: a watcher is in place before the page's first
    script. And the home screen is there at once, with no wait for a backend."""
    page = kept_page(browser, reduced_motion="reduce")
    page.add_init_script(SPLASH_ON)
    page.add_init_script("""
        window.__seen = 0;
        new MutationObserver(() => {
            if (document.querySelector('[data-testid=splash]')) window.__seen += 1;
        }).observe(document, {subtree: true, childList: true});
    """)
    try:
        started = time.monotonic()
        page.goto(f"{overlay}?ws=ws://127.0.0.1:{free_port()}")
        page.get_by_role("textbox", name=BOX).wait_for(timeout=5000)
        arrived = time.monotonic() - started
        page.wait_for_timeout(400)

        assert page.evaluate("window.__seen") == 0
        assert arrived < 3
    finally:
        page.context.close()


def test_the_home_screen_is_there_whole_as_the_logo_leaves(
    browser: Browser, overlay: str, offers: History,  # noqa: F811
) -> None:
    """The tiles no longer rise in (2026-11-14: the first screen is the cards
    and the box, there at once). What stays: the logo leaves and the screen
    behind it is whole, not half-faded."""
    page = kept_page(browser)
    page.add_init_script(SPLASH_ON)
    offers.goals = []
    try:
        page.goto(f"{overlay}?ws=ws://127.0.0.1:{offers.port}")
        page.get_by_test_id("tile").first.wait_for(state="attached", timeout=15000)
        first = "+getComputedStyle(document.querySelector('[data-testid=tiles] li')).opacity"

        page.wait_for_timeout(2000)
        assert page.evaluate(first) == 1
        assert page.get_by_test_id("tile").count() == 3
        assert not splash_shown(page)
    finally:
        page.context.close()


def test_what_it_covered_can_be_pressed_once_it_has_gone(
    browser: Browser, overlay: str, offers: History,  # noqa: F811
) -> None:
    page = kept_page(browser)
    page.add_init_script(SPLASH_ON)
    offers.goals = []
    offers.received.clear()
    try:
        page.goto(f"{overlay}?ws=ws://127.0.0.1:{offers.port}")
        page.get_by_test_id("splash").wait_for(timeout=15000)
        page.get_by_test_id("splash").wait_for(state="detached", timeout=15000)
        page.fill(f"input[aria-label='{BOX}']", GOAL)
        page.get_by_role("button", name="Start").click()
        page.wait_for_timeout(600)

        assert any(said.get("type") == "task.start" for said in offers.received)
    finally:
        page.context.close()


# --- the small logo ---------------------------------------------------------


def logo_on(page: Page) -> dict:
    return page.evaluate("""() => {
        const holder = document.querySelector('[data-testid=home-logo]');
        if (!holder) return {there: false};
        const img = holder.querySelector('img');
        const box = img.getBoundingClientRect();
        const overlaps = (selector) => [...document.querySelectorAll(selector)].some((other) => {
            const b = other.getBoundingClientRect();
            return b.width > 0 && box.left < b.right && box.right > b.left
                   && box.top < b.bottom && box.bottom > b.top;
        });
        return {there: true, src: img.currentSrc, loaded: img.naturalWidth, alt: img.alt,
                left: box.left, top: box.top, right: box.right, bottom: box.bottom,
                width: innerWidth, height: innerHeight,
                presses: getComputedStyle(holder).pointerEvents,
                on_the_shape: overlaps('[data-presence]'),
                on_the_screen: overlaps('h1, section, input, [data-testid=tile], button'),
                scrolls: document.scrollingElement.scrollHeight > innerHeight};
    }""")


@pytest.mark.parametrize("theme, file", [("light", "simba-logo-horizontal-small"),
                                         ("dark", "simba-logo-horizontal-small-dark")])
@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("goals", [[], LONG_GOALS], ids=["new", "with history"])
def test_it_sits_top_left_and_touches_nothing(
    browser: Browser, overlay: str, offers: History, theme: str, file: str,  # noqa: F811
    size: str, goals: list[str],
) -> None:
    page = kept_page(browser, theme, size)
    offers.goals = [{"goal": goal, "site": "127.0.0.1"} for goal in goals]
    try:
        page.goto(f"{overlay}?ws=ws://127.0.0.1:{offers.port}")
        page.get_by_role("textbox", name=BOX).wait_for(timeout=15000)
        if goals:
            # Goals asked before are not on the first screen since 2026-11-14.
            page.wait_for_timeout(600)
            assert page.get_by_test_id("remembered").count() == 0
        page.wait_for_timeout(1400)  # past the entrance

        logo = logo_on(page)

        assert logo["there"] and logo["loaded"] > 0, logo
        assert logo["alt"] == "simba", logo
        assert re.search(rf"/{file}-[^/]*\.svg$", logo["src"]), logo
        drawn = served(page, logo["src"])
        assert "<rect" not in drawn, "stands in a box"
        assert "#55645F" not in drawn and "#9FB2AC" not in drawn, "a tagline nobody can read"
        assert logo["left"] >= 8 and logo["top"] >= 8, logo
        assert logo["right"] < logo["width"] / 2 and logo["bottom"] < logo["height"] / 2, logo
        assert not logo["on_the_shape"], logo
        assert not logo["on_the_screen"], logo
        assert not logo["scrolls"], logo
        assert logo["presses"] == "none", logo
        # The presence mark is still SIMBA's sign on the same screen.
        assert page.get_by_test_id("shape").count() == 1
    finally:
        page.context.close()


def goes_to_a_step(page: Page, overlay: str, backend: Backend) -> None:  # noqa: F811
    backend.script = next(script for script in ENDINGS.values()
                          if any(kind == AWAIT_RESPONSE for kind, _ in script))
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    page.fill(f"input[aria-label='{BOX}']", GOAL)
    page.get_by_role("button", name="Start").click()
    page.wait_for_selector("[data-testid=step-shell], [data-testid=final-check]", timeout=15000)
    page.wait_for_timeout(700)  # past the crossfade


def test_not_on_a_step_and_the_presence_mark_stays(
    browser: Browser, overlay: str, backend: Backend,  # noqa: F811
) -> None:
    page = kept_page(browser)
    try:
        goes_to_a_step(page, overlay, backend)

        assert page.get_by_test_id("home-logo").count() == 0
        # The presence mark stays: since the task frame (2026-11-17) it is the lion
        # in the header, with the same states and the same words.
        assert page.get_by_test_id("frame-lion").count() >= 1
    finally:
        page.context.close()


def test_not_on_an_ending_and_back_on_the_home_screen(
    browser: Browser, overlay: str, backend: Backend,  # noqa: F811
) -> None:
    page = kept_page(browser)
    try:
        reach(page, overlay, backend, "failed")
        page.wait_for_timeout(700)
        assert page.get_by_test_id("home-logo").count() == 0

        page.get_by_role("button", name="Back to start").click()
        page.get_by_test_id("home-logo").wait_for(timeout=5000)
        assert logo_on(page)["there"]
    finally:
        page.context.close()


def test_not_on_the_welcome(browser: Browser, overlay: str, offers: History) -> None:  # noqa: F811
    """"The home screen only": the welcome stands in its place and is not it."""
    page = kept_page(browser)
    page.add_init_script("window.__simbaWelcome = true")
    offers.goals = []
    try:
        page.goto(f"{overlay}?ws=ws://127.0.0.1:{offers.port}")
        page.get_by_test_id("welcome").wait_for(timeout=15000)
        page.wait_for_timeout(700)

        assert page.get_by_test_id("home-logo").count() == 0
    finally:
        page.context.close()


def test_the_readme_opens_with_the_logo_in_both_themes() -> None:
    readme = text(REPO / "README.md")

    head = readme[:readme.index("# SIMBA")]
    assert "assets/brand/simba-logo-horizontal.svg" in head
    assert "assets/brand/derived/simba-logo-horizontal-dark.svg" in head
    assert 'alt="simba"' in head
