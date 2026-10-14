"""Reading a page's lists of choices without opening them.

The train search asks the person for a station before it touches the site, so
the station has to come from the site's own list — read while the list is
closed (`options.py`). The shapes here are the ones that matter: the live
site's Element UI dropdown, measured on 2026-10-06 to hold every station
before anything is clicked, and the native and ARIA lists a page could use
instead; and the navigation menu that must not be mistaken for one.
"""

from playwright.sync_api import Page

from backend.perception.options import LISTS_SCRIPT, lists_from, tidy

# The live site's shape: two closed panels holding the same names, one of them
# listed twice, as the page holds them before anything is clicked.
ELEMENT_UI = """
<div class="el-select-dropdown el-popper" style="display: none">
  <div class="el-scrollbar"><ul class="el-scrollbar__view el-select-dropdown__list">
    <li class="el-select-dropdown__item"><span>LAHORE JN.</span></li>
    <li class="el-select-dropdown__item"><span>LAHORE CANTT</span></li>
    <li class="el-select-dropdown__item"><span>DINA</span></li>
    <li class="el-select-dropdown__item"><span>DINA</span></li>
  </ul></div>
</div>
"""


def lists(page: Page, html: str) -> list[list[str]]:
    page.set_content(html)
    return lists_from(page.evaluate(LISTS_SCRIPT))


def test_a_closed_component_dropdown_is_read_whole(page: Page) -> None:
    """The case this exists for: nothing on screen, every name read."""
    assert lists(page, ELEMENT_UI) == [["LAHORE JN.", "LAHORE CANTT", "DINA"]]


def test_reading_opens_nothing(page: Page) -> None:
    page.set_content(ELEMENT_UI)
    page.evaluate(LISTS_SCRIPT)
    assert page.evaluate("getComputedStyle(document.querySelector('.el-select-dropdown'))"
                         ".display") == "none"


def test_a_native_select_and_a_datalist(page: Page) -> None:
    found = lists(page, """
        <select><option>Economy</option><option>Business</option></select>
        <datalist id="d"><option value="Quetta"></option><option value="Sibi Jn."></option>
        </datalist>""")
    # A datalist option with no text is read by its label, which is its value.
    assert found == [["Economy", "Business"], ["Quetta", "Sibi Jn."]]


def test_an_aria_listbox(page: Page) -> None:
    found = lists(page, """
        <div role="listbox" hidden>
          <div role="option">Multan Cantt</div><div role="option">Sukkur</div>
        </div>""")
    assert found == [["Multan Cantt", "Sukkur"]]


def test_a_navigation_menu_is_not_a_list_of_choices(page: Page) -> None:
    """A `ul` of links in a `dropdown` is how a site's menu is built."""
    found = lists(page, """
        <nav><div class="dropdown"><ul>
          <li><a href="#">Tickets</a></li><li><a href="#">Timings</a></li>
        </ul></div></nav>""")
    assert found == []


def test_a_plain_list_on_the_page_is_not_a_list_of_choices(page: Page) -> None:
    assert lists(page, "<ul><li>Bring your ticket</li><li>Arrive early</li></ul>") == []


def test_names_are_kept_once_in_page_order() -> None:
    assert tidy(["  KOT  ADDU ", "SUKKUR", "", "KOT ADDU", "QUETTA"]) == [
        "KOT ADDU", "SUKKUR", "QUETTA"]
