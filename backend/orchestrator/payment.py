"""Paying by card, for real, when the person says so (2026-11-16).

Until today SIMBA never typed a card: it handed the payment page to the person.
The project's owner asked for the other half — SIMBA fills a payment form and
presses Pay itself, on any website, once the person has said "do it" on a
final screen that names the amount, the website and the card. This module is
that half. It has four parts, none of them specific to a website:

* `Card` and `parse_card` — a card, checked before it is ever typed anywhere
  (Luhn, a date that has not passed, a security code of three or four digits).
* `CardVault` — the card, encrypted with Windows' own key for this user (the
  same DPAPI as `vault.py`), in its own file, never committed. One card.
* `classify` and `find_card_fields` — which box on a page is the card number,
  the expiry, the security code, the name: by what the page says it
  autocompletes, then by its name, id, label, placeholder and aria-label.
  Looked for in the page and in every frame on it, because payment forms are
  often a gateway's iframe.
* `fill_card` and `find_pay_button` — the typing and the press, through
  Playwright: real keystrokes into the real boxes of the real page, each one
  read back to check it took. Nothing here animates anything.

**The model never sees a card.** Nothing here is imported by a planner, no
function here returns a value from the card in a message, and nothing logs one:
a failure names the *role* of the box ("the card number"), never its value.
`Card` has no readable `repr`. The page picture masks card boxes
(`loop.PASSWORD_BOXES`).
"""

from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Frame, Locator, Page

from backend.orchestrator.vault import REPO, VaultUnavailable, decrypt, encrypt

DEFAULT_PATH = REPO / "data" / "card.json"

#: How SIMBA treats a payment page. `card`: it may fill the card in itself, once
#: the person has agreed on a final screen. `handover`: the page is the
#: person's, as it was before 2026-11-16 (and as the older tests expect).
MODES = ("card", "handover")


def pay_mode() -> str:
    # `handover` since 2026-11-17: the person types the card themselves, in the
    # help-me step on the real page (`helpme.py`); SIMBA presses Pay after the
    # pay screen. `card` — SIMBA types the card from its own vault — stays
    # behind `SIMBA_PAY_MODE=card`, off.
    mode = os.environ.get("SIMBA_PAY_MODE", "handover").strip().lower()
    return mode if mode in MODES else "handover"


# --- the card ---------------------------------------------------------------


class CardError(ValueError):
    """A card that cannot be used. `reason` is `name`, `number`, `expiry` or
    `cvv`: which box to ask again. Never the value."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Card:
    name: str
    number: str  # digits only
    month: str  # "01".."12"
    year: str  # four digits
    cvv: str

    def __repr__(self) -> str:  # never the values, whatever prints this
        return "Card(...)"

    __str__ = __repr__

    @property
    def last4(self) -> str:
        return self.number[-4:]

    @property
    def brand(self) -> str:
        n = self.number
        if n.startswith("4"):
            return "Visa"
        if re.match(r"^(5[1-5]|2[2-7])", n):
            return "Mastercard"
        if re.match(r"^3[47]", n):
            return "American Express"
        return "Card"

    @property
    def spoken(self) -> str:
        """How the card is named on screen: the last four digits and nothing else."""
        return f"{self.brand} ending {self.last4}"


def luhn_ok(digits: str) -> bool:
    total = 0
    for position, char in enumerate(reversed(digits)):
        value = int(char)
        if position % 2:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def parse_card(name: str, number: str, expiry: str, cvv: str,
               today: date | None = None) -> Card:
    """A card as a person types it, or `CardError` for the first box that is
    wrong. "4242 4242 4242 4242", "12/30", "12/2030" and "1230" are all fine."""
    today = today or date.today()
    holder = " ".join((name or "").split())
    if not holder:
        raise CardError("name")
    digits = re.sub(r"[\s-]", "", number or "")
    if not digits.isdigit() or not 12 <= len(digits) <= 19 or not luhn_ok(digits):
        raise CardError("number")
    match = re.fullmatch(r"\s*(\d{1,2})\s*[/\-]?\s*(\d{2}|\d{4})\s*", expiry or "")
    if match is None:
        raise CardError("expiry")
    month, year = int(match.group(1)), int(match.group(2))
    if year < 100:
        year += 2000
    if not 1 <= month <= 12 or (year, month) < (today.year, today.month):
        raise CardError("expiry")
    code = (cvv or "").strip()
    if not code.isdigit() or len(code) not in (3, 4):
        raise CardError("cvv")
    return Card(holder, digits, f"{month:02d}", f"{year:04d}", code)


class CardVault:
    """The person's card, sealed with this Windows account's own key, in its own
    file. One card, replaced when another is kept. `SIMBA_CARD_VAULT` points
    elsewhere; the tests use that."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or os.environ.get("SIMBA_CARD_VAULT") or DEFAULT_PATH)

    @property
    def available(self) -> bool:
        try:
            return decrypt(encrypt(b"check")) == b"check"
        except VaultUnavailable:
            return False

    def get(self) -> Card | None:
        try:
            sealed = json.loads(self.path.read_text(encoding="utf-8")).get("card")
            opened = json.loads(decrypt(base64.b64decode(sealed)))
            return Card(opened["name"], opened["number"], opened["month"],
                        opened["year"], opened["cvv"])
        except (OSError, ValueError, KeyError, TypeError, VaultUnavailable):
            return None

    def put(self, card: Card) -> None:
        """Raises `VaultUnavailable` where this machine cannot encrypt."""
        sealed = encrypt(json.dumps({
            "name": card.name, "number": card.number, "month": card.month,
            "year": card.year, "cvv": card.cvv}).encode())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({
            "about": "A saved card, encrypted with this Windows account's own key "
                     "(DPAPI). Not readable on another machine. Never commit.",
            "card": base64.b64encode(sealed).decode(),
        }, indent=2), encoding="utf-8")

    def forget(self) -> bool:
        try:
            self.path.unlink()
            return True
        except FileNotFoundError:
            return False


# --- which box is which -------------------------------------------------------

#: What a box for each part of a card is called, tried in this order.
_NAME = re.compile(r"(name\s*on\s*(the\s*)?card|card\s*holder|cardholder|holder'?s?\s*name|"
                   r"cc[-_ ]?name|name\s*as\s*(shown|printed))", re.I)
_CVV = re.compile(r"(\bcvv2?\b|\bcvc2?\b|\bcsc\b|\bcid\b|security\s*(code|number)|"
                  r"card\s*(security|verification)|verification\s*value)", re.I)
_NUMBER = re.compile(r"(card\s*(number|no\b|num\b|#)|cc[-_ ]?(num|number)|\bpan\b|"
                     r"(credit|debit)\s*card)", re.I)
_EXP_MONTH = re.compile(r"(exp\w*[-_ ]*month|month|\bmm\b)", re.I)
_EXP_YEAR = re.compile(r"(exp\w*[-_ ]*year|year|\byy(yy)?\b)", re.I)
_EXPIRY = re.compile(r"(exp(iry|iration|ire|\b)|valid\s*(thru|till|until)|mm\s*/\s*yy)", re.I)

#: `autocomplete` tokens a page uses for a card, and what they are.
_TOKENS = {"cc-number": "number", "cc-csc": "cvv", "cc-exp": "expiry",
           "cc-exp-month": "exp_month", "cc-exp-year": "exp_year", "cc-name": "name"}

ROLE_WORDS = {
    "name": "the name on the card", "number": "the card number",
    "expiry": "the expiry date", "exp_month": "the expiry month",
    "exp_year": "the expiry year", "cvv": "the security code",
}
#: The order they are typed in: the way a person reads a card.
ORDER = ("number", "name", "expiry", "exp_month", "exp_year", "cvv")

_TYPEABLE = {"", "text", "tel", "number", "password", "select-one"}


def classify(box: dict) -> str | None:
    """Which part of a card a box on a page is, or None. `box` has what the
    page says about it: `autocomplete`, `name`, `id`, `label`, `placeholder`,
    `aria`, `type`."""
    if box.get("type", "") not in _TYPEABLE:
        return None
    for token in (box.get("autocomplete") or "").lower().split():
        if token in _TOKENS:
            return _TOKENS[token]
    said = " ".join(str(box.get(key) or "") for key in
                    ("name", "id", "label", "placeholder", "aria"))
    if _NAME.search(said):
        return "name"
    if _CVV.search(said):
        return "cvv"
    if _NUMBER.search(said):
        return "number"
    if re.search(r"\bmm\s*[/\-]\s*yy", said, re.I):  # one box for both: "MM / YY"
        return "expiry"
    if _EXP_MONTH.search(said) and (_EXPIRY.search(said) or box.get("type") == "select-one"):
        return "exp_month"
    if _EXP_YEAR.search(said) and (_EXPIRY.search(said) or box.get("type") == "select-one"):
        return "exp_year"
    if _EXPIRY.search(said):
        return "expiry"
    return None


@dataclass(frozen=True)
class CardField:
    role: str
    frame: Frame
    index: int  # among `input, select` in its frame
    box: dict

    def locator(self) -> Locator:
        return self.frame.locator("input, select").nth(self.index)


_BOXES_JS = """() => [...document.querySelectorAll('input, select')].map((e, i) => {
  const r = e.getBoundingClientRect(), s = getComputedStyle(e);
  return {
    i, type: e.tagName === 'SELECT' ? 'select-one' : (e.type || '').toLowerCase(),
    name: e.name || '', id: e.id || '', autocomplete: e.autocomplete || '',
    placeholder: e.placeholder || '', aria: e.getAttribute('aria-label') || '',
    label: e.labels ? [...e.labels].map(l => l.innerText).join(' ') : '',
    maxlength: e.maxLength > 0 ? e.maxLength : 0,
    visible: r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'
  };
})"""


async def find_card_fields(page: Page) -> list[CardField]:
    """The card boxes on the page and in its frames, one per part, in the order
    a card is read. Empty unless a card number box is among them: a page with
    only an expiry box is not a payment form."""
    found: dict[str, CardField] = {}
    for frame in page.frames:
        try:
            boxes = await frame.evaluate(_BOXES_JS)
        except PlaywrightError:
            continue
        # A card form is one frame's: take the first frame that has a number.
        here: dict[str, CardField] = {}
        for box in boxes:
            if not box["visible"]:
                continue
            role = classify(box)
            if role is not None and role not in here:
                here[role] = CardField(role, frame, box["i"], box)
        if "number" in here:
            found = here
            break
    if "number" not in found:
        return []
    return [found[role] for role in ORDER if role in found]


# --- typing it in -------------------------------------------------------------


class FillError(Exception):
    """A box that did not take what was typed. `role` is which one."""

    def __init__(self, role: str) -> None:
        super().__init__(role)
        self.role = role


def expiry_text(card: Card, box: dict) -> str:
    """The expiry as this box wants it, from what it says about itself."""
    hint = f"{box.get('placeholder', '')} {box.get('label', '')}".upper()
    limit = box.get("maxlength") or 0
    if "YYYY" in hint:
        return f"{card.month}/{card.year}"
    if limit == 4:
        return f"{card.month}{card.year[2:]}"
    if limit == 6:
        return f"{card.month}{card.year}"
    return f"{card.month}/{card.year[2:]}"


def text_for(card: Card, field: CardField) -> str:
    role = field.role
    if role == "number":
        return card.number
    if role == "name":
        return card.name
    if role == "cvv":
        return card.cvv
    if role == "expiry":
        return expiry_text(card, field.box)
    year_short = (field.box.get("maxlength") == 2
                  or "YY" in f"{field.box.get('placeholder', '')}".upper()
                  and "YYYY" not in f"{field.box.get('placeholder', '')}".upper())
    if role == "exp_month":
        return card.month
    return card.year[2:] if year_short else card.year


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text or "")


async def _took(field: CardField, wanted: str) -> bool:
    """Whether the box now holds what was typed. Read back from the page; the
    card's own text is compared here and never leaves this function."""
    try:
        now = await field.locator().input_value(timeout=2000)
    except PlaywrightError:
        return False
    if field.role == "name":
        return now.strip().casefold() == wanted.strip().casefold()
    return _digits(now) == _digits(wanted)


async def _choose(field: CardField, card: Card) -> bool:
    """A drop-down for the month or the year: by its option's value or words."""
    wanted = text_for(card, field)
    month = str(int(card.month))
    options = [wanted, card.year, card.year[2:], month, card.month]
    for option in dict.fromkeys(options):
        for how in ({"value": option}, {"label": option}):
            try:
                await field.locator().select_option(timeout=1500, **how)
                return True
            except PlaywrightError:
                continue
    return False


async def fill_card(page: Page, card: Card, field: CardField, *, delay_ms: int = 30) -> None:
    """One box, typed key by key, then read back. Raises `FillError(role)`.

    Real keystrokes, so a box that formats as it is typed ("4242 4242 …") or
    watches key events (a framework's controlled input) sees what it would see
    from a person. If they do not take, the whole value is set at once and
    checked again; if that fails too, the caller hands the page over."""
    locator = field.locator()
    try:
        await locator.scroll_into_view_if_needed(timeout=3000)
        if field.box.get("type") == "select-one":
            if not await _choose(field, card):
                raise FillError(field.role)
            return
        wanted = text_for(card, field)
        await locator.click(timeout=3000)
        await locator.fill("", timeout=3000)
        await locator.press_sequentially(wanted, delay=delay_ms, timeout=15000)
        if await _took(field, wanted):
            return
        await locator.fill(wanted, timeout=3000)
        if await _took(field, wanted):
            return
    except PlaywrightError:
        pass
    raise FillError(field.role)


# --- pressing Pay ---------------------------------------------------------------

_PAY_BUTTON = re.compile(r"\b(pay|place\s*order|complete|confirm|submit|purchase|buy|checkout|"
                         r"continue)\b", re.I)
_NOT_PAY = re.compile(r"\b(cancel|back|edit|change|close|clear|reset|apply|promo|coupon)\b", re.I)

_BUTTONS_JS = """(index) => {
  const box = document.querySelectorAll('input, select')[index];
  const scope = (box && box.closest('form')) || document;
  const all = [...document.querySelectorAll(
    'button, input[type=submit], input[type=button], [role=button], a.btn, a.button')];
  return all.map((e, i) => {
    const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    return {i, text: (e.innerText || e.value || e.getAttribute('aria-label') || '').trim(),
            inForm: scope.contains(e), disabled: !!e.disabled,
            submit: (e.type || '').toLowerCase() === 'submit' || e.tagName === 'BUTTON' && !e.type,
            visible: r.width > 0 && r.height > 0 && s.visibility !== 'hidden'};
  });
}"""


async def find_pay_button(page: Page, number: CardField) -> tuple[Locator, str] | None:
    """The button that pays, and its words, or None when it cannot be told:
    then the person presses it. The one in the card's own form if the words fit
    a payment (or it is the form's only submit); else a single button elsewhere
    on the page with payment words. Two equally likely buttons is None."""
    try:
        buttons = await number.frame.evaluate(_BUTTONS_JS, number.index)
    except PlaywrightError:
        return None
    live = [b for b in buttons if b["visible"] and not b["disabled"]
            and b["text"] and not _NOT_PAY.search(b["text"])]
    in_form = [b for b in live if b["inForm"]]
    pool = [b for b in in_form if re.search(r"\b(pay|place\s*order|purchase|buy)\b",
                                            b["text"], re.I)]
    if not pool:
        pool = [b for b in in_form if b["submit"]]
    if not pool and not in_form:
        pool = [b for b in live if _PAY_BUTTON.search(b["text"])]
    if len(pool) != 1:
        return None
    chosen = pool[0]
    locator = number.frame.locator(
        "button, input[type=submit], input[type=button], [role=button], a.btn, a.button"
    ).nth(chosen["i"])
    return locator, chosen["text"]
