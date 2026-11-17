"""My bookings (2026-11-17): every booking or order SIMBA completed, as a card.

Kept on this computer only, in `data/bookings.json` (never committed), and
shown on the home screen as clean cards: what, from, to, date, time, seat, the
number, the amount. Nothing in it goes anywhere. What is kept is what the
person chose and the website confirmed — never a card number, a code or a
password, and never the details that identify them (a CNIC, a phone number, an
email, an address), which stay in the encrypted profile (`profile.py`).
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from backend.orchestrator import profile
from backend.orchestrator.vault import REPO
from shared.schema import Booking, Detail

DEFAULT_PATH = REPO / "data" / "bookings.json"
#: The most kept: the screen shows a few cards, not a ledger.
MOST_KEPT = 50

#: A booking or order number as a page words it.
NUMBER = re.compile(
    r"(?:order|booking|reservation|ticket|reference|confirmation|invoice|receipt|pnr)"
    r"\s*(?:no\.?|number|#|id|ref\.?|code)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9-]{3,})", re.IGNORECASE)
MONEY = re.compile(r"(?:\brs\.?|\bpkr)\s?\d[\d,]*(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s?(?:\brs\.?|\bpkr)\b",
                   re.IGNORECASE)


def number_in(text: str) -> str | None:
    """A booking or order number the page's own words give, or None."""
    for found in NUMBER.finditer(text or ""):
        value = found.group(1).strip("-")
        if any(ch.isdigit() for ch in value):
            return value
    return None


class BookingStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or os.environ.get("SIMBA_BOOKINGS") or DEFAULT_PATH)

    def all(self) -> list[Booking]:
        try:
            rows = json.loads(self.path.read_text(encoding="utf-8")).get("bookings", [])
            return [Booking.model_validate(row) for row in rows]
        except (OSError, ValueError):
            return []

    def add(self, goal: str, url: str, facts: list[Detail], confirmation: str | None) -> Booking:
        """Keep one completed booking or order. Personal details are left out."""
        keep = [Detail(label=f.label, value=f.value) for f in facts
                if profile.kind_of(f.label) is None]
        amount = next((f.value for f in keep if MONEY.search(f.value)
                       and re.search(r"amount|total|fare|price|cost|paying", f.label, re.I)), None)
        title = " ".join((goal or "").split())[:90] or "Booking"
        entry = Booking(
            id=uuid.uuid4().hex[:10], title=title, site=urlsplit(url).netloc.removeprefix("www."),
            when=time.strftime("%Y-%m-%d %H:%M"), lines=keep,
            number=number_in(confirmation or ""), amount=amount)
        rows = [entry, *self.all()][:MOST_KEPT]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({
            "about": "Bookings and orders SIMBA completed, on this computer only. Never commit.",
            "bookings": [row.model_dump() for row in rows],
        }, indent=2), encoding="utf-8")
        return entry

    def forget(self) -> bool:
        try:
            self.path.unlink()
            return True
        except FileNotFoundError:
            return False
