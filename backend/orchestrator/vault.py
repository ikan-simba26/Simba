"""The person's saved sign-in details: encrypted on this machine, typed by the backend.

A password is entered once, in a protected field on a sign-in step, and the
person chooses whether to keep it. Kept, it is encrypted and written here; the
next time a step needs it, the backend types it into the page itself and the
step only says that it will. It never goes into a prompt, a log, a trace, or a
message to the overlay — `test_vault.py` runs whole tasks and searches all of
them for it.

**Encrypted with the operating system's own key for this user** (Windows
DPAPI, `CryptProtectData`), through `ctypes`: no dependency, and no key of ours
to store, lose or leak. The file is useless on another machine or to another
Windows account. On any other operating system the vault reports itself
unavailable and nothing is saved — the step asks every time, as it did before.

**One entry per site**, by origin (`http://127.0.0.1:5000`): the username and
the password together, encrypted as one. The file is `data/vault.json`, not
committed (`.gitignore`), and inside the repository (CLAUDE.md); `SIMBA_VAULT`
points somewhere else, which the tests use.

Nothing here prints a secret. `Credentials` has no readable `repr`, so an
accidental log line, assertion message or traceback shows `Credentials(...)`.
"""

from __future__ import annotations

import base64
import ctypes
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[2]
DEFAULT_PATH = REPO / "data" / "vault.json"
#: Mixed into the encryption, so another program using DPAPI for the same
#: account cannot decrypt this file by accident.
ENTROPY = b"SIMBA sign-in vault, 2026-10-03"


class VaultUnavailable(Exception):
    """This machine cannot encrypt with the operating system's key."""


@dataclass(frozen=True)
class Credentials:
    username: str
    password: str

    def __repr__(self) -> str:  # never the values, whatever prints this
        return "Credentials(...)"

    __str__ = __repr__


def site_of(url: str) -> str:
    """The origin a page belongs to, which is what a saved entry is for."""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}".lower()


# --- DPAPI, through ctypes --------------------------------------------------------


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]


#: No dialog, ever: a background process has no one to show one to.
_CRYPTPROTECT_UI_FORBIDDEN = 0x01


def _blob(data: bytes) -> _Blob:
    buffer = ctypes.create_string_buffer(data, len(data))
    return _Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))


def _dpapi(name: str, data: bytes) -> bytes:
    """`CryptProtectData` or `CryptUnprotectData`: no description, our
    entropy, no UI. Raises `VaultUnavailable` off Windows or on failure."""
    if sys.platform != "win32":
        raise VaultUnavailable(
            "saved passwords are encrypted with Windows' own key for this user, "
            f"and this is {sys.platform}")
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    source, entropy, out = _blob(data), _blob(ENTROPY), _Blob()
    ok = getattr(crypt32, name)(
        ctypes.byref(source), None, ctypes.byref(entropy), None, None,
        _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out))
    if not ok:
        raise VaultUnavailable(f"{name} failed (Windows error {kernel32.GetLastError()})")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)


def encrypt(data: bytes) -> bytes:
    return _dpapi("CryptProtectData", data)


def decrypt(data: bytes) -> bytes:
    """Fails on another machine or account, which is the point."""
    return _dpapi("CryptUnprotectData", data)


# --- the vault ----------------------------------------------------------------------


class Vault:
    """Saved sign-in details, one entry per site."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or os.environ.get("SIMBA_VAULT") or DEFAULT_PATH)

    @property
    def available(self) -> bool:
        """Whether anything can be saved here at all."""
        try:
            return decrypt(encrypt(b"check")) == b"check"
        except VaultUnavailable:
            return False

    def _entries(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8")).get("sites", {})

    def _write(self, entries: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({
            "about": "Saved sign-in details, encrypted with this Windows account's own "
                     "key (DPAPI). Not readable on another machine. Never commit.",
            "sites": entries,
        }, indent=2), encoding="utf-8")

    def get(self, url: str) -> Credentials | None:
        """The saved details for the site this page is on, or None."""
        sealed = self._entries().get(site_of(url))
        if sealed is None:
            return None
        try:
            opened = json.loads(decrypt(base64.b64decode(sealed)))
        except (VaultUnavailable, ValueError):
            return None
        return Credentials(opened["username"], opened["password"])

    def put(self, url: str, credentials: Credentials) -> None:
        """Save, replacing anything saved for that site. Raises
        `VaultUnavailable` when this machine cannot encrypt."""
        sealed = encrypt(json.dumps({"username": credentials.username,
                                     "password": credentials.password}).encode())
        entries = self._entries()
        entries[site_of(url)] = base64.b64encode(sealed).decode()
        self._write(entries)

    def forget(self, url: str) -> bool:
        """Delete what was saved for that site. True if there was something."""
        entries = self._entries()
        if entries.pop(site_of(url), None) is None:
            return False
        self._write(entries)
        return True

    def sites(self) -> list[str]:
        """Which sites have something saved. Origins only: nothing secret."""
        return sorted(self._entries())
