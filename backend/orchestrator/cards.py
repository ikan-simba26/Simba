"""Products and choices on a page, as cards (2026-11-17).

A shop's search page is forty tiles; the person wants to be asked "Which one?"
with a few plain cards — name, price, picture — and SIMBA then presses the
real one. This finds the tiles on any page, by what a tile is rather than by
any one site's markup: a repeated block that holds a price and a link or a
picture. It also reads the cart (how many things are in it), so a checkout
never starts on a surprise, and takes small pictures of the cards for the
overlay.

Nothing here is typed, clicked or changed on the page, except one attribute on
each card's block (`data-simba-card`) to point at it again.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import re
from dataclasses import dataclass

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page

log = logging.getLogger("simba.cards")

#: The most cards put in front of the person.
MOST_CARDS = 6

_FIND_JS = r"""(most) => {
  const PRICE = /(?:\brs\.?|\bpkr|₨|\busd|\bus\$|\$|£|€)\s?\d[\d,]*(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s?(?:\brs\.?|\bpkr)\b/i;
  const seen = (e) => {
    const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    return r.width > 8 && r.height > 8 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const sig = (e) => e.tagName + '.' + [...e.classList].filter(c => !/\d/.test(c)).slice(0, 1).join('.');
  const prices = [...document.querySelectorAll('body *')].filter(e =>
    e.children.length <= 3 && seen(e) && (e.innerText || '').length < 60 && PRICE.test(e.innerText || ''));
  const groups = new Map();
  const taken = new Set();
  for (const price of prices) {
    let up = price;
    for (let depth = 0; depth < 8 && up.parentElement && up.parentElement !== document.body; depth++) {
      up = up.parentElement;
      const parent = up.parentElement;
      if (!parent) break;
      const like = [...parent.children].filter(c => sig(c) === sig(up));
      const hasLink = up.querySelector('a[href]:not([href="#"]), button, input[type=button], input[type=submit], [role=button]') || up.tagName === 'A';
      const withPrice = like.filter(c => PRICE.test(c.innerText || ''));
      if (hasLink && withPrice.length >= 2 && (up.innerText || '').length < 600) {
        if (!taken.has(up)) {
          taken.add(up);
          const key = sig(up) + '>' + sig(parent);
          if (!groups.has(key)) groups.set(key, []);
          groups.get(key).push(up);
        }
        break;
      }
    }
  }
  let best = [];
  for (const list of groups.values()) if (list.length > best.length) best = list;
  best = best.slice(0, most);
  return best.map((card, i) => {
    card.setAttribute('data-simba-card', String(i));
    const text = (card.innerText || '').replace(/\s+/g, ' ').trim();
    const heading = card.querySelector('h1,h2,h3,h4,h5,h6,[class*=title i],[class*=name i]');
    const links = [...card.querySelectorAll('a[href]:not([href="#"])')]
      .map(a => ({a, t: (a.innerText || a.title || a.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim()}))
      .filter(x => x.t.length > 2 && !PRICE.test(x.t) && !/^(add to|buy|cart|wishlist|quick view|compare)/i.test(x.t));
    let name = heading ? (heading.innerText || '').replace(/\s+/g, ' ').trim() : '';
    let link = null;
    if (links.length) {
      link = links.reduce((a, b) => (b.t.length > a.t.length ? b : a));
      if (!name) name = link.t;
    }
    // The control to press: the name's link, else the card's own button.
    let control = link ? link.a : null;
    let controlText = link ? link.t : '';
    if (!control) {
      const texts = [...card.querySelectorAll('button, input[type=button], input[type=submit], [role=button], a[href]')]
        .map(b => ({b, t: (b.innerText || b.value || b.title || b.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim()}))
        .filter(x => x.t && !/^(close|cancel|more|details?|info)$/i.test(x.t));
      const pick = texts.find(x => x.b.tagName !== 'A') || texts[0];
      if (pick) { control = pick.b; controlText = pick.t; }
    }
    if (!name) { const img = card.querySelector('img[alt]'); name = img ? img.alt.trim() : ''; }
    const rs = text.match(/(?:\brs\.?|\bpkr|₨)\s?\d[\d,]*(?:\.\d+)?/i);
    const match = rs || text.match(PRICE);
    // A row of a table has no heading: its own words, without the price.
    // A row of a table, or a heading with no spaces (cells run together): its own
    // words up to the first price are the name.
    if (!name || !/\s/.test(name) || /\d[A-Za-z]{3,}[A-Z]|[a-z][A-Z]{2,}/.test(name)) {
      const upTo = match ? text.slice(0, text.indexOf(match[0])) : text;
      // The cells read one by one, so they are not run together ("38DNLAHORE").
      const cells = [...card.querySelectorAll('*')].filter(e => e.children.length === 0 && e.offsetWidth > 0)
        .map(e => (e.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean).join(' ');
      const cut = match ? cells.indexOf(match[0]) : -1;
      name = ((cut > 0 ? cells.slice(0, cut) : cells) || upTo || text).slice(0, 90);
    }
    const imgs = [...card.querySelectorAll('img')].filter(seen)
      .sort((a, b) => b.getBoundingClientRect().width * b.getBoundingClientRect().height
                    - a.getBoundingClientRect().width * a.getBoundingClientRect().height);
    const lr = control ? control.getBoundingClientRect() : null;
    return {
      index: i, name: name.slice(0, 120), price: match ? match[0].trim() : '',
      link_text: controlText.slice(0, 120), has_picture: imgs.length > 0,
      link_rect: lr ? [lr.x, lr.y, lr.width, lr.height] : null,
    };
  }).filter(c => c.name);
}"""

#: What the cart says about itself: how many lines and how many things.
_CART_JS = r"""() => {
  const q = [...document.querySelectorAll(
    'input[name*=qty i], input[name*=quant i], input[class*=qty i], input[class*=quant i], input[id*=qty i], input[id*=quant i]')]
    .filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
  let things = 0;
  for (const e of q) { const n = parseInt(e.value, 10); things += Number.isFinite(n) && n > 0 ? n : 1; }
  const rows = [...document.querySelectorAll('tr, li, [class*=cart-item i], [class*=cart_item i], [class*=cartitem i]')]
    .filter(e => /remove|delete|×|✕/i.test(e.innerText || '') && /(\brs\.?|\bpkr|\$)\s?\d/i.test(e.innerText || ''));
  const inner = rows.filter(r => !rows.some(o => o !== r && r.contains(o)));
  return {lines: Math.max(q.length, inner.length), things: Math.max(things, inner.length),
          names: inner.slice(0, 5).map(r => (r.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 90))};
}"""


@dataclass(frozen=True)
class Card:
    index: int
    name: str
    price: str
    link_text: str
    has_picture: bool
    link_rect: tuple[float, float, float, float] | None

    @property
    def sub(self) -> str:
        return self.price

    def __str__(self) -> str:
        return f"[{self.index}] {self.name} | {self.price} | link {self.link_text!r}"


async def find_cards(page: Page, most: int = MOST_CARDS) -> list[Card]:
    """The tiles of the page's main list, in page order. Empty when the page
    is not a list of at least two things with prices."""
    try:
        rows = await page.evaluate(_FIND_JS, most)
    except PlaywrightError:
        return []
    cards = [Card(index=row["index"], name=row["name"], price=row["price"],
                  link_text=row["link_text"], has_picture=row["has_picture"],
                  link_rect=tuple(row["link_rect"]) if row["link_rect"] else None)
             for row in rows]
    return cards if len(cards) >= 2 else []


async def picture_of(page: Page, card: Card) -> str | None:
    """A small picture of the card's own image, as a `data:` address, or None."""
    if not card.has_picture:
        return None
    try:
        image = page.locator(f'[data-simba-card="{card.index}"] img:visible').first
        shot = await image.screenshot(type="jpeg", quality=55, timeout=3000)
    except (PlaywrightError, asyncio.TimeoutError):
        return None
    if len(shot) > 90_000:
        return None
    return "data:image/jpeg;base64," + base64.b64encode(shot).decode("ascii")


async def pictures(page: Page, cards: list[Card]) -> list[str | None]:
    """Pictures for all the cards, one after another (they share the page)."""
    out: list[str | None] = []
    for card in cards:
        out.append(await picture_of(page, card))
    return out


@dataclass(frozen=True)
class Cart:
    lines: int
    things: int
    names: tuple[str, ...]


async def read_cart(page: Page) -> Cart | None:
    """What the page's cart holds, when the page is one, else None."""
    try:
        got = await page.evaluate(_CART_JS)
    except PlaywrightError:
        return None
    if not got or not got.get("lines"):
        return None
    return Cart(lines=int(got["lines"]), things=int(got["things"]), names=tuple(got["names"]))


#: Words of a press that puts one thing in the cart, and of one that starts
#: checking out.
ADD_WORDS = re.compile(r"\b(add to (cart|basket|bag|trolley)|add item|buy now|add)\b", re.IGNORECASE)
CHECKOUT_WORDS = re.compile(r"\b(check ?out|proceed to (checkout|payment|pay)|place order|"
                            r"view cart|go to cart|my cart)\b", re.IGNORECASE)
#: A goal that asks for more than one of something.
MANY = re.compile(
    r"\b(two|three|four|five|both|all|several|multiple|a few|some|\d+)\s+"
    r"(more\s+)?(copies|books|items|tickets|seats|pieces|of them|units|passengers|"
    r"of each|[a-z]+s)\b|\b(x|×)\s?\d+\b|\bquantity\s*(of\s*)?\d+", re.IGNORECASE)


def goal_wants_many(goal: str) -> bool:
    """Whether the goal says more than one of something. Without it, one."""
    found = MANY.search(goal or "")
    if not found:
        return False
    lead = found.group(0).strip().lower()
    return not lead.startswith(("1 ", "one "))
