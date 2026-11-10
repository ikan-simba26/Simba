"""Picture tiles (2026-11-10): every tile on the home screen wears a picture on
its own calm colour, in a real browser.

The three things SIMBA can do wear theirs by what they are; a tile the person
kept, and one a helper taught, wear the one their name asks for
(`frontend/src/pictures.ts`), and the globe when the name asks for none. The
colour always goes with the picture, a taught tile still has its own mark,
the words stay readable in both themes, and the fullest home screen still
fits at every scale it is tested at.
"""

import pytest
from playwright.sync_api import Page

from frontend.test_home import SIZES, TALLEST, box_fits, browser  # noqa: F401 - fixture
from frontend.test_show_me_once import Teacher, opened, pages  # noqa: F401 - fixture
from frontend.test_terminal_states import overlay  # noqa: F401 - fixture

#: A name, and the picture the rule gives it.
NAMES = [
    ("Trains to Karachi", "train"),
    ("Railway tickets home", "train"),
    ("Electricity at home", "bill"),
    ("My water bill", "bill"),
    ("Register for CS-401", "course"),
    ("Evening course", "course"),
    ("Mum's pension", "other"),
    ("Trains, then my bill", "train"),  # the first word on a list decides
    ("Billboard", "other"),             # a whole word, not part of one
]

#: The contrast of one colour on another, from computed colours, in the page.
CONTRAST_JS = """([fg, bg]) => {
  const rgb = (s) => s.match(/[\\d.]+/g).slice(0, 3).map(Number);
  const lum = (c) => { const [r, g, b] = c.map(v => { v /= 255;
    return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const [a, b] = [lum(rgb(fg)), lum(rgb(bg))].sort((x, y) => y - x);
  return (a + 0.05) / (b + 0.05);
}"""


def kinds(page: Page, testid: str) -> list[str]:
    return page.eval_on_selector_all(
        f"[data-testid={testid}] [data-picture]", "els => els.map(e => e.dataset.picture)")


def contrast(page: Page, fg: str, bg: str) -> float:
    return page.evaluate(CONTRAST_JS, [fg, bg])


def test_the_three_things_simba_can_do_wear_their_own_pictures(
        browser, overlay: str, pages: list) -> None:  # noqa: F811
    backend = Teacher()
    page, _ = opened(browser, overlay, backend, pages)
    # A new person's large pictures: the course, the bill, the train, each on
    # its own pale square.
    assert kinds(page, "tile") == ["course", "bill", "train"]
    squares = page.eval_on_selector_all(
        "[data-testid=tile] [data-picture]", "els => els.map(e => e.style.background)")
    assert squares == ["var(--pic-course-tint)", "var(--pic-bill-tint)", "var(--pic-train-tint)"]


@pytest.mark.parametrize("name, kind", NAMES)
def test_a_kept_tile_wears_the_picture_its_name_asks_for(
        browser, overlay: str, pages: list, name: str, kind: str) -> None:  # noqa: F811
    backend = Teacher()
    # The flow says railways every time: the name decides, so the picture and
    # the words always say the same thing.
    backend.tiles = [{"id": "a1", "label": name, "flow": "railways"}]
    page, _ = opened(browser, overlay, backend, pages)
    page.get_by_test_id("own-tile").wait_for(timeout=10000)
    assert kinds(page, "own-tile") == [kind]
    chip = page.locator("[data-testid=own-tile] [data-picture]")
    assert chip.evaluate("e => [e.style.background, e.style.color]") == [
        f"var(--pic-{kind}-tint)", f"var(--pic-{kind})"]
    # A kept tile is not marked as taught.
    assert page.locator("[data-testid=own-tile] [data-testid=taught-mark]").count() == 0
    # Once the person has tiles, the three things SIMBA can do are small, and
    # still each wear theirs.
    assert kinds(page, "tile") == ["course", "bill", "train"]


def test_a_taught_tile_wears_its_name_s_picture_and_its_own_mark(
        browser, overlay: str, pages: list) -> None:  # noqa: F811
    backend = Teacher()
    backend.tiles = [{"id": "a1", "label": "My water bill", "flow": "billing"}]
    backend.routines = [{"id": "r1", "label": "My water bill", "site": "127.0.0.1:5100"},
                        {"id": "r2", "label": "Mum's pension", "site": "example.gov.pk"}]
    page, _ = opened(browser, overlay, backend, pages)
    page.get_by_test_id("own-routine").first.wait_for(timeout=10000)
    assert kinds(page, "own-routine") == ["bill", "other"]
    # Told apart from a kept tile of the same name by a shape on the picture's
    # corner, never by colour: the same picture, the same colour, one mark.
    assert page.locator("[data-testid=own-routine] [data-testid=taught-mark]").count() == 2
    assert page.locator("[data-testid=own-tile] [data-testid=taught-mark]").count() == 0
    kept = page.locator("[data-testid=own-tile] [data-picture]").evaluate("e => e.style.color")
    taught = page.locator("[data-testid=own-routine] [data-picture]").first.evaluate(
        "e => e.style.color")
    assert kept == taught == "var(--pic-bill)"


def test_change_my_tiles_shows_the_same_pictures(
        browser, overlay: str, pages: list) -> None:  # noqa: F811
    backend = Teacher()
    backend.tiles = [{"id": "a1", "label": "Trains to Karachi", "flow": "railways"}]
    backend.routines = [{"id": "r1", "label": "My water bill", "site": "127.0.0.1:5100"}]
    page, _ = opened(browser, overlay, backend, pages)
    page.get_by_test_id("change-tiles").click()
    page.get_by_test_id("tile-row").first.wait_for(timeout=5000)
    assert kinds(page, "tile-row") == ["train", "bill"]
    assert page.locator("[data-testid=tile-row] [data-testid=taught-mark]").count() == 1


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_the_words_on_every_tile_stay_readable(
        browser, overlay: str, pages: list, theme: str) -> None:  # noqa: F811
    backend = Teacher()
    backend.tiles = [{"id": "a1", "label": "Electricity at home", "flow": "billing"},
                     {"id": "b2", "label": "Trains to Karachi", "flow": "railways"}]
    backend.routines = [{"id": "r1", "label": "Mum's pension", "site": "example.gov.pk"}]
    page = browser.new_page(viewport={"width": 1280, "height": 800}, color_scheme=theme)
    pages.append(page)
    from frontend.test_show_me_once import BOX, WELCOMED
    page.add_init_script(WELCOMED)
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    page.get_by_role("textbox", name=BOX).wait_for(timeout=15000)
    page.get_by_test_id("own-routine").wait_for(timeout=10000)
    page.wait_for_timeout(1600)
    measured = page.eval_on_selector_all(
        "[data-testid=tile], [data-testid=own-tile], [data-testid=own-routine]",
        """tiles => tiles.map(t => {
             const words = [...t.querySelectorAll('span')].find(s => !s.dataset.picture
               && !s.closest('[data-picture]') && s.innerText.trim());
             return {words: words.innerText.trim(), fg: getComputedStyle(words).color,
                     bg: getComputedStyle(t).backgroundColor,
                     pic: (() => { const p = t.querySelector('[data-picture]');
                                   const s = getComputedStyle(p);
                                   return [s.color, s.backgroundColor]; })()};
           })""")
    assert len(measured) == 6, measured
    for tile in measured:
        # The words, at least 4.5:1 on the tile, in light and dark.
        assert contrast(page, tile["fg"], tile["bg"]) >= 4.5, (theme, tile)
        # And the picture plainly on its pale square.
        assert contrast(page, *tile["pic"]) >= 4.5, (theme, tile)


@pytest.mark.parametrize("size", list(SIZES))
def test_the_fullest_home_screen_fits_with_every_picture_whole(
        browser, overlay: str, pages: list, size: str) -> None:  # noqa: F811
    backend = Teacher()
    # Two kept tiles whose names wrap, one taught tile, and two goals asked
    # before at their longest: the fullest the home screen gets.
    backend.tiles = [{"id": "a1", "label": "Electricity at home", "flow": "billing"},
                     {"id": "b2", "label": "Railway tickets home", "flow": "railways"}]
    backend.routines = [{"id": "r1", "label": "Register for CS-401", "site": "127.0.0.1:5300"}]
    backend.goals = [{"goal": goal, "site": "127.0.0.1"} for goal in TALLEST]
    page, _ = opened(browser, overlay, backend, pages, size)
    page.get_by_test_id("remembered").first.wait_for(timeout=10000)
    page.wait_for_timeout(600)
    fits, measured = box_fits(page)
    assert fits, measured
    # Six pictures, each wholly inside its tile, its mark too.
    inside = page.eval_on_selector_all(
        "[data-testid=tile], [data-testid=own-tile], [data-testid=own-routine]",
        """tiles => tiles.map(t => {
             const b = t.getBoundingClientRect();
             return [...t.querySelectorAll('[data-picture], [data-testid=taught-mark]')]
               .every(p => { const r = p.getBoundingClientRect();
                 return r.left >= b.left && r.right <= b.right && r.top >= b.top
                        && r.bottom <= b.bottom && r.width > 0; });
           })""")
    assert inside == [True] * 6, inside
    # No name is cut short at more than its two lines.
    cut = page.eval_on_selector_all(
        "[data-testid=own-tile] .line-clamp-2, [data-testid=own-routine] .line-clamp-2",
        "els => els.filter(e => e.scrollHeight > e.clientHeight + 1).map(e => e.innerText)")
    assert cut == [], cut
