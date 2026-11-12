"""The AI provider set up in the app (2026-11-13, the advisor's direction, K):
entered once, kept encrypted on this computer, checked with one small
question, and never shown, logged or sent back — only its last four
characters. No network: the check's provider is faked."""

import asyncio
import json
import logging

import httpx2 as httpx
import openai
import pytest
from fastapi.testclient import TestClient

from backend.orchestrator import ai_settings, llm
from backend.orchestrator import app as app_module
from backend.orchestrator.ai_settings import AiStore, SettingsError, check, settings_from
from backend.orchestrator.llm import LLMError
from backend.orchestrator.vault import Vault

KEY = "AIzaTESTkey-not-a-real-one-9f3c"

needs_vault = pytest.mark.skipif(not Vault().available, reason="Windows DPAPI only")


def test_a_key_is_never_printed():
    settings = settings_from("gemini", KEY)
    assert KEY not in repr(settings) and KEY not in str(settings)
    assert settings.ends_with == "9f3c"
    from shared.schema import AiSetup
    assert KEY not in repr(AiSetup(provider="gemini", key=KEY))


@pytest.mark.parametrize("provider, key, url, model, reason", [
    ("bard", KEY, None, None, "provider"),
    ("gemini", "short", None, None, "key"),
    ("gemini", "has a space in it", None, None, "key"),
    ("openai", KEY, "http://example.com/v1", "m", "address"),
    ("openai", KEY, "https://example.com/v1", "", "model"),
])
def test_setup_that_cannot_work_says_why(provider, key, url, model, reason):
    with pytest.raises(SettingsError) as raised:
        settings_from(provider, key, url, model)
    assert raised.value.reason == reason


def test_each_provider_has_its_address_and_a_model():
    gemini = settings_from("gemini", KEY)
    assert "generativelanguage.googleapis.com" in gemini.base_url
    assert settings_from("groq", KEY).model == "openai/gpt-oss-120b"
    other = settings_from("openai", KEY, "https://llm.example.edu/v1", "my-model")
    assert (other.base_url, other.model) == ("https://llm.example.edu/v1", "my-model")


@needs_vault
def test_the_key_is_kept_encrypted(tmp_path):
    store = AiStore(tmp_path / "ai.json")
    store.save(settings_from("gemini", KEY))
    assert KEY not in (tmp_path / "ai.json").read_text(encoding="utf-8")
    assert store.load().key == KEY
    store.clear()
    assert store.load() is None


@needs_vault
def test_a_key_set_up_in_the_app_wins_over_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SIMBA_AI_SETTINGS", str(tmp_path / "ai.json"))
    monkeypatch.setattr(llm, "_load_dotenv", lambda: None)
    monkeypatch.setenv("SIMBA_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "env-key-123456")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    AiStore().save(settings_from("groq", KEY))
    provider = llm.provider_from_env()
    assert provider.label == "Groq"


def api_error(kind, status):
    request = httpx.Request("POST", "https://example.invalid/v1/chat/completions")
    if kind in (openai.APIConnectionError, openai.APITimeoutError):
        return kind(request=request)
    return kind("failed", response=httpx.Response(status, request=request), body=None)


class Failing:
    def __init__(self, error):
        self.error = error

    async def choose_route(self, system_prompt, goal):
        if self.error is None:
            return object()
        raise LLMError("call failed") from self.error


@pytest.mark.parametrize("error, verdict", [
    (None, "ok"),
    (api_error(openai.AuthenticationError, 401), "key"),
    (api_error(openai.RateLimitError, 429), "limit"),
    (api_error(openai.APIConnectionError, 0), "network"),
    (api_error(openai.InternalServerError, 500), "other"),
])
def test_the_check_says_how_it_went_in_a_word(error, verdict):
    assert asyncio.run(check(Failing(error))) == verdict


@needs_vault
def test_setting_up_from_the_window_answers_without_the_key(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("SIMBA_AI_SETTINGS", str(tmp_path / "ai.json"))
    monkeypatch.setenv("SIMBA_ROUTER", "keywords")
    monkeypatch.setenv("SIMBA_RECORD_STEPS", "0")

    async def fine(provider):
        return "ok"
    monkeypatch.setattr(app_module, "check_ai", fine)
    caplog.set_level(logging.DEBUG)
    from starlette.websockets import WebSocketDisconnect

    sent: list[dict] = []
    try:
        with TestClient(app_module.app) as client, client.websocket_connect("/ws") as ws:
            sent.append(ws.receive_json())
            ws.send_json({"v": 1, "type": "ai.setup", "task_id": "t", "seq": 1, "ts": 0,
                          "payload": {"provider": "gemini", "key": KEY}})
            sent.append(ws.receive_json())
    except WebSocketDisconnect:
        pass
    status = sent[-1]
    assert status["type"] == "ai.status"
    assert status["payload"] == {"configured": True, "provider": "Gemini",
                                 "ends_with": "9f3c", "check": "ok"}
    assert KEY not in json.dumps(sent)
    assert KEY not in caplog.text
    assert AiStore().load().key == KEY
