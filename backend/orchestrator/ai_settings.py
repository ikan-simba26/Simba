"""The AI provider set up in SIMBA's first-time setup (2026-11-13, the
advisor's direction, K): which provider, and its key, entered once in the app.

**Kept like the vault** (`vault.py`): encrypted with this Windows account's own
key (DPAPI), in `data/ai.json`, never committed. The key is never logged,
never sent back to the window — only its last four characters, so the person
can tell which key it is — and never put in a prompt. Set up here, it is used
in place of `.env`'s; with nothing set up, `.env` is used as before.

The check after saving is one small question to the provider (routing
"hello"), so the person learns at once whether the key works; what it says is
reduced to a reason code, never the provider's own message, which can echo
part of a key.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from backend.orchestrator.vault import REPO, Vault, VaultUnavailable, decrypt, encrypt

log = logging.getLogger("simba.ai")

DEFAULT_PATH = REPO / "data" / "ai.json"

#: The providers the setup offers, and where each is served.
PROVIDERS = {
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/",
               "gemini-3.1-flash-lite"),
    "groq": ("https://api.groq.com/openai/v1", "openai/gpt-oss-120b"),
    "openai": (None, None),  # any OpenAI-compatible: its own address and model
}
#: How long the check waits for the provider.
CHECK_TIMEOUT_S = 12.0


class SettingsError(ValueError):
    """Setup that cannot be kept. `reason` is a code the overlay says in words."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class AiSettings:
    provider: str
    key: str
    base_url: str | None
    model: str

    def __repr__(self) -> str:  # never the key, whatever prints this
        return f"AiSettings(provider={self.provider!r}, model={self.model!r}, key=...)"

    __str__ = __repr__

    @property
    def ends_with(self) -> str:
        return self.key[-4:] if len(self.key) >= 8 else ""


def settings_from(provider: str, key: str, base_url: str | None = None,
                  model: str | None = None) -> AiSettings:
    """What the person entered, checked for its shape. Raises `SettingsError`
    with `provider`, `key`, `address` or `model`."""
    provider = (provider or "").strip().lower()
    if provider not in PROVIDERS:
        raise SettingsError("provider")
    key = (key or "").strip()
    if len(key) < 8 or any(ch.isspace() for ch in key):
        raise SettingsError("key")
    default_url, default_model = PROVIDERS[provider]
    if provider == "openai":
        from urllib.parse import urlsplit

        parts = urlsplit((base_url or "").strip())
        if parts.scheme != "https" and parts.hostname not in ("127.0.0.1", "localhost"):
            raise SettingsError("address")
        if not (model or "").strip():
            raise SettingsError("model")
        return AiSettings(provider, key, (base_url or "").strip(), model.strip())
    return AiSettings(provider, key, default_url, (model or "").strip() or default_model)


class AiStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or os.environ.get("SIMBA_AI_SETTINGS") or DEFAULT_PATH)

    def load(self) -> AiSettings | None:
        if not self.path.exists():
            return None
        try:
            blob = json.loads(self.path.read_text(encoding="utf-8"))["ai"]
            row = json.loads(decrypt(bytes.fromhex(blob)).decode("utf-8"))
            return AiSettings(row["provider"], row["key"], row.get("base_url"), row["model"])
        except (OSError, ValueError, KeyError, VaultUnavailable):
            log.warning("ai: the saved setup could not be read")
            return None

    def save(self, settings: AiSettings) -> None:
        if not Vault().available:
            raise SettingsError("vault")
        row = {"provider": settings.provider, "key": settings.key,
               "base_url": settings.base_url, "model": settings.model}
        blob = encrypt(json.dumps(row).encode("utf-8")).hex()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"ai": blob}), encoding="utf-8")
        temporary.replace(self.path)
        log.info("ai: setup saved for %s", settings.provider)

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


def provider_for(settings: AiSettings, transcript=None):
    """The provider the saved setup names (`llm.OpenAICompatibleProvider`)."""
    from backend.orchestrator.llm import OpenAICompatibleProvider

    return OpenAICompatibleProvider(api_key=settings.key, base_url=settings.base_url,
                                    model=settings.model, transcript=transcript)


async def check(provider) -> str:
    """One small question to the provider: `ok`, or why not — `key`,
    `limit`, `network` or `other`. Never the provider's own words."""
    from backend.orchestrator.llm import LLMError
    from backend.orchestrator.router import SYSTEM_PROMPT

    try:
        await asyncio.wait_for(provider.choose_route(SYSTEM_PROMPT, "hello"), CHECK_TIMEOUT_S)
        return "ok"
    except asyncio.TimeoutError:
        return "network"
    except LLMError as error:
        try:
            import openai
        except ImportError:  # pragma: no cover
            return "other"
        cause = error.__cause__
        if isinstance(cause, (openai.AuthenticationError, openai.PermissionDeniedError)):
            return "key"
        if isinstance(cause, openai.RateLimitError):
            return "limit"
        if isinstance(cause, (openai.APIConnectionError, openai.APITimeoutError)):
            return "network"
        return "other"
