"""The help-me step (2026-11-17): the person does one small thing on the real page.

A CAPTCHA, a code the website sent to a phone, a card number: SIMBA never does
these and never reads what is typed into them. The overlay shows only that part
of the real page, zoomed and scrollable, with one plain sentence, and the
person clicks or types straight into it. This module finds that part, scrolls
it into view, and notices — without reading anything typed — when it is done.

What it may learn from the page is a yes or no and a count: whether the part is
still there, whether a box holds *any* characters (its length, never its text),
whether a "solved" token field is non-empty. Nothing typed ever comes back
here, so nothing typed can be logged, kept or sent to a model.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Locator, Page

from backend.orchestrator import payment

log = logging.getLogger("simba.helpme")

CAPTCHA_SELECTOR = ", ".join([
    "iframe[src*='recaptcha' i]", "iframe[src*='hcaptcha' i]", "iframe[src*='turnstile' i]",
    "iframe[src*='captcha' i]", "iframe[title*='captcha' i]", ".g-recaptcha", ".h-captcha",
    ".cf-turnstile",
])
#: The "it was solved" token a CAPTCHA widget writes into the page.
#: The nearest block that holds a CAPTCHA picture and the box its letters go in.
_LOW = "translate(%s, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')"
IMAGE_CAPTCHA_BLOCK = (
    "xpath=(//input[contains(" + _LOW % "@name" + ", 'captcha') or contains(" + _LOW % "@id"
    + ", 'captcha')]/ancestor::*[.//img[contains(" + _LOW % "@id" + ", 'captcha') or contains("
    + _LOW % "@alt" + ", 'captcha') or contains(" + _LOW % "@src" + ", 'captcha')]][1])[1]")
SOLVED_SELECTOR = ("textarea[name='g-recaptcha-response'], textarea[name='h-captcha-response'], "
                   "input[name='cf-turnstile-response']")
CODE_SELECTOR = ", ".join([
    "input[autocomplete='one-time-code']", "input[name*='otp' i]", "input[id*='otp' i]",
    "input[placeholder*='otp' i]", "input[placeholder*='code' i]", "input[name*='code' i]",
    "input[aria-label*='code' i]", "input[aria-label*='otp' i]", "input[id*='verif' i]",
])


@dataclass
class Target:
    """The part of the page the person is asked to use."""

    kind: str
    locator: Locator | None = None
    card: list[payment.CardField] | None = None

    @property
    def has_part(self) -> bool:
        """Whether a part of the page was found: only then can SIMBA tell
        when it is done. Without one, the person says so."""
        return bool(self.card) or self.locator is not None

    async def present(self) -> bool:
        """Whether the part is still on the page, visible."""
        try:
            if self.card:
                return await self.card[0].locator().is_visible(timeout=1000)
            if self.locator is None:
                return False
            return await self.locator.is_visible(timeout=1000)
        except PlaywrightError:
            return False

    async def scroll(self) -> None:
        """Bring the part to the middle of what is shown."""
        try:
            handle = self.card[0].locator() if self.card else self.locator
            if handle is None:
                return
            await handle.evaluate(
                "e => e.scrollIntoView({block: 'center', inline: 'center'})", timeout=2000)
        except PlaywrightError:
            return

    async def finished(self, page: Page) -> bool:
        """Whether the person has done it: by what the page shows of its own
        state, never by what was typed. A count of characters is the most this
        reads."""
        if self.kind == "captcha":
            try:
                if await page.evaluate(
                        "(s) => [...document.querySelectorAll(s)].some(e => (e.value || '').length > 10)",
                        SOLVED_SELECTOR):
                    return True
            except PlaywrightError:
                pass
            return not await self.present()
        if self.kind == "card" and self.card:
            for field in self.card:
                if field.role == "name":
                    continue
                try:
                    length = await field.locator().evaluate("e => (e.value || '').length", timeout=1000)
                except PlaywrightError:
                    return not await self.present()
                need = {"number": 12, "cvv": 3, "expiry": 4, "exp_month": 1, "exp_year": 2}.get(
                    field.role, 1)
                if length < need:
                    return False
            return True
        return not await self.present()


async def find(page: Page, kind: str) -> Target:
    """The part of the page for `kind` (`captcha`, `code`, `card`), or a
    `Target` with nothing in it when none can be told: the whole page is then
    the person's, as before."""
    if kind == "card":
        fields = await payment.find_card_fields(page)
        return Target("card", card=fields or None)
    if kind == "captcha":
        # A picture of letters with a box to type them in (IESCO's bill page,
        # 2026-11-18): the part is the nearest block holding both, so the person
        # sees the picture and the box. Not a widget's iframe: that is below.
        picture = page.locator(IMAGE_CAPTCHA_BLOCK).first
        try:
            if await picture.count() and await picture.is_visible(timeout=500):
                return Target("captcha", locator=picture)
        except PlaywrightError:
            pass
        found = page.locator(CAPTCHA_SELECTOR)
        try:
            for index in range(await found.count()):
                if await found.nth(index).is_visible(timeout=500):
                    return Target("captcha", locator=found.nth(index))
        except PlaywrightError:
            pass
        return Target("captcha")
    if kind == "code":
        for frame in page.frames:
            boxes = frame.locator(CODE_SELECTOR)
            try:
                for index in range(await boxes.count()):
                    box = boxes.nth(index)
                    kind_of = (await box.get_attribute("type", timeout=500) or "text").lower()
                    if kind_of in ("hidden", "checkbox", "radio", "submit", "button"):
                        continue
                    if not await box.is_visible(timeout=500):
                        continue
                    # A promo, coupon or gift-card box says "code" too.
                    said = await box.evaluate(
                        "e => [e.name, e.id, e.placeholder, e.getAttribute('aria-label'),"
                        " e.labels && [...e.labels].map(l => l.innerText).join(' ')]"
                        ".filter(Boolean).join(' ')", timeout=500)
                    if payment.DISCOUNT_WORDS.search(said or ""):
                        continue
                    return Target("code", locator=box)
            except PlaywrightError:
                continue
        return Target("code")
    return Target(kind)


async def kind_of_page(page: Page) -> str:
    """What a check that stopped a run is, from the page: a card form, a
    CAPTCHA, a box for a code — else `other`."""
    if await payment.find_card_fields(page):
        return "card"
    if (await find(page, "captcha")).locator is not None:
        return "captcha"
    if (await find(page, "code")).locator is not None:
        return "code"
    return "other"
