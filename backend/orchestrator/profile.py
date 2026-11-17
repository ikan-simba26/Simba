"""The details a form asks for, kept on this computer (2026-11-17).

A name, a CNIC, a phone number, an email, an address, a city: the boxes nearly
every booking and order form puts in front of a person. SIMBA asks for each
once, in its own screen with big boxes, offers to keep it, and the next time
types it itself. **They never go to the AI model**: the planner is told only
that a box wants "your phone number", never the number, and the loop redacts
any value it has typed from every prompt it sends (`llm_loop.keep_private`).

Kept encrypted with Windows' own key for this user (the same DPAPI as
`vault.py`), in `data/profile.json`, never committed. Another machine or
another Windows account cannot read it. `SIMBA_PROFILE` points elsewhere, which
the tests use.
"""

from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path

from backend.orchestrator.vault import REPO, VaultUnavailable, decrypt, encrypt

DEFAULT_PATH = REPO / "data" / "profile.json"

#: What a box is for, by what the page and the model call it. Tried in order.
KINDS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("cnic", re.compile(r"\b(cnic|nic|national\s*id|identity\s*(card)?\s*(no|number)?|id\s*card)\b", re.I)),
    ("email", re.compile(r"e-?mail", re.I)),
    ("phone", re.compile(r"\b(phone|mobile|cell|contact\s*(no|number)|whatsapp|tel)\b", re.I)),
    ("dob", re.compile(r"(birth|\bdob\b)", re.I)),
    ("city", re.compile(r"\b(city|town)\b", re.I)),
    ("address", re.compile(r"\b(address|street)\b", re.I)),
    ("name", re.compile(r"\b(full\s*name|first\s*name|last\s*name|surname|passenger\s*name|"
                        r"your\s*name|name)\b", re.I)),
)

#: Said to the person, for the box that asks.
WORDS = {"name": "your name", "email": "your email", "phone": "your phone number",
         "cnic": "your CNIC number", "address": "your address", "city": "your city",
         "dob": "your date of birth"}


def kind_of(label: str, name: str | None = None, input_type: str | None = None) -> str | None:
    """Which kept detail a box wants, or None. A user name or a password is a
    sign-in, not a detail kept here."""
    said = " ".join(filter(None, [label, name]))
    if re.search(r"\b(user\s*name|username|login|password|passcode|pin|card|cvv|otp|code)\b",
                 said, re.I):
        return None
    if input_type == "email":
        return "email"
    if input_type == "tel":
        return "phone"
    for kind, pattern in KINDS:
        if pattern.search(said):
            return kind
    return None


class ProfileVault:
    """The person's details, sealed with this Windows account's own key."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or os.environ.get("SIMBA_PROFILE") or DEFAULT_PATH)

    @property
    def available(self) -> bool:
        try:
            return decrypt(encrypt(b"check")) == b"check"
        except VaultUnavailable:
            return False

    def all(self) -> dict[str, str]:
        try:
            sealed = json.loads(self.path.read_text(encoding="utf-8")).get("profile")
            opened = json.loads(decrypt(base64.b64decode(sealed)))
            return {k: str(v) for k, v in opened.items() if isinstance(v, str) and v}
        except (OSError, ValueError, TypeError, VaultUnavailable):
            return {}

    def get(self, kind: str) -> str | None:
        return self.all().get(kind)

    def put(self, kind: str, value: str) -> None:
        """Raises `VaultUnavailable` where this machine cannot encrypt."""
        value = " ".join((value or "").split())
        if not value:
            return
        details = self.all()
        details[kind] = value
        sealed = encrypt(json.dumps(details).encode())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({
            "about": "The person's details, encrypted with this Windows account's own "
                     "key (DPAPI). Not readable on another machine. Never commit.",
            "profile": base64.b64encode(sealed).decode(),
        }, indent=2), encoding="utf-8")

    def forget(self) -> bool:
        try:
            self.path.unlink()
            return True
        except FileNotFoundError:
            return False
