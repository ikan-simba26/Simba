"""Every list of choices a page holds, whether it is open or not.

Perception reads what is on screen, and a closed dropdown is not on screen.
That is right for acting — nothing can be clicked inside a closed list — and
wrong for asking. Before SIMBA touches the train search it has to ask the
person where they are going, and the answer has to be one of the site's own
stations, so it needs the site's list without opening it (2026-10-06).

The live train search makes this possible. Measured on 2026-10-06 with one
read-only visit: before anything is clicked, the page already holds 684
`li.el-select-dropdown__item`s — the From list and the To list, 342 each, 340
distinct names. Element UI renders a select's options at mount and only shows
them when the box is opened. Most component libraries do the same, and a
native `<select>` or `<datalist>` always holds its options.

What counts as a list, deliberately narrow:

  * a `<select>` or `<datalist>`, by its `<option>`s;
  * an ARIA `listbox`, by its `option`s;
  * a `<ul>` inside something whose class names it a dropdown, select,
    autocomplete, listbox or options panel, by its `<li>`s — and only when no
    item holds a link, a button or an input, which is what keeps a site's
    navigation menu (a `ul` of links in a `dropdown`) out of it.

Reads the DOM and nothing else: no click, no focus, no scroll. Text is taken
from `textContent`, which a hidden element still has.
"""

from __future__ import annotations

from playwright.async_api import Page

LISTS_SCRIPT = r"""() => {
  const said = (el) => (el.textContent || "").replace(/\s+/g, " ").trim();
  const lists = [];
  for (const el of document.querySelectorAll("select, datalist")) {
    // What the option shows; its value only when it shows nothing, as a
    // datalist's often does. A select's value is often an internal code.
    lists.push([...el.querySelectorAll("option")].map((o) => (o.label || said(o) || o.value).trim()));
  }
  for (const el of document.querySelectorAll("[role=listbox]")) {
    lists.push([...el.querySelectorAll("[role=option]")].map(said));
  }
  const PANEL = "[class*=dropdown], [class*=select], [class*=autocomplete], " +
                "[class*=listbox], [class*=options]";
  for (const ul of document.querySelectorAll("ul")) {
    if (!ul.closest(PANEL) || ul.closest("[role=listbox]")) continue;
    const items = [...ul.children].filter((li) => li.tagName === "LI");
    if (items.some((li) => li.querySelector("a, button, input"))) continue;
    lists.push(items.map(said));
  }
  return lists;
}"""


def tidy(items: list[str]) -> list[str]:
    """The names in page order, each once, blanks dropped.

    The live list carries two names twice (DINA, OKARA CANTT): the same
    station listed twice is one choice, not two.
    """
    seen: set[str] = set()
    kept: list[str] = []
    for item in items:
        name = " ".join(item.split())
        if name and name not in seen:
            seen.add(name)
            kept.append(name)
    return kept


def lists_from(found: list[list[str]]) -> list[list[str]]:
    """What `LISTS_SCRIPT` returned, each list tidied, empty ones dropped."""
    return [names for names in (tidy(items) for items in found) if names]


async def option_lists(page: Page) -> list[list[str]]:
    """Every list of choices on the page."""
    return lists_from(await page.evaluate(LISTS_SCRIPT))


async def longest_list(page: Page) -> list[str]:
    """The page's longest list of choices, or an empty list if it has none.

    The train search has two lists and they are the same list. On a page with
    several, the longest is the one a long text answer is most likely to be
    an item of; a caller that needs more than that should not use this.
    """
    lists = await option_lists(page)
    return max(lists, key=len) if lists else []
