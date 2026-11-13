"""Gemini first, Groq when Gemini cannot answer (2026-11-13, the advisor's
direction, item E): which errors move to the next provider, which do not, and
that the app can say which one answered. No network: the providers are fakes
or real clients whose calls are replaced."""

import asyncio

import httpx2 as httpx
import openai
import pytest

from backend.orchestrator import llm
from backend.orchestrator.llm import (
    Action, FallbackProvider, LLMError, OpenAICompatibleProvider, label_for, provider_from_env,
)

ACTION = Action(action="click", element_id=3, value=None, reasoning="Open the search.")


def api_error(kind: type, status: int, headers: dict | None = None) -> Exception:
    request = httpx.Request("POST", "https://example.invalid/v1/chat/completions")
    if kind is openai.APIConnectionError:
        return kind(request=request)
    if kind is openai.APITimeoutError:
        return kind(request=request)
    response = httpx.Response(status, request=request, headers=headers or {})
    return kind("failed", response=response, body=None)


class Fake:
    """A provider whose `decide` raises what it is told, or answers."""

    def __init__(self, label: str, fails_with: Exception | None = None) -> None:
        self.label = label
        self.fails_with = fails_with
        self.calls = 0

    async def decide(self, system_prompt, page, goal, feedback=None, history=None):
        self.calls += 1
        if self.fails_with is not None:
            raise LLMError(f"{self.label} failed: {self.fails_with}") from self.fails_with
        return ACTION

    async def choose_route(self, system_prompt, goal):
        return await self.decide(system_prompt, "", goal)

    async def read_details(self, system_prompt, goal):
        return await self.decide(system_prompt, "", goal)


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize("error", [
    api_error(openai.RateLimitError, 429, {"retry-after": "30"}),
    api_error(openai.APIConnectionError, 0),
    api_error(openai.APITimeoutError, 0),
    api_error(openai.InternalServerError, 503),
    api_error(openai.AuthenticationError, 401),
    api_error(openai.PermissionDeniedError, 403),
], ids=["rate limit", "no connection", "timeout", "server error", "bad key", "not allowed"])
def test_the_fallback_answers_when_the_first_cannot(error):
    first, second = Fake("Gemini", error), Fake("Groq")
    chain = FallbackProvider([first, second])
    assert run(chain.decide("s", "p", "g")) == ACTION
    assert (first.calls, second.calls) == (1, 1)
    assert chain.answered_by == "Groq"
    assert chain.fell_back == 1


def test_the_first_answers_and_the_fallback_is_never_asked():
    first, second = Fake("Gemini"), Fake("Groq")
    chain = FallbackProvider([first, second])
    assert run(chain.decide("s", "p", "g")) == ACTION
    assert second.calls == 0
    assert chain.answered_by == "Gemini"


def test_a_bad_answer_is_not_a_reason_to_ask_another():
    # A response that did not match the schema is the planner's to retry with
    # the error fed back (`LLMPlanner._choose`): another provider would only
    # hide that the first one is misbehaving.
    shape = LLMError("response did not match the action schema — action: invalid")
    first, second = Fake("Gemini"), Fake("Groq")
    first.fails_with = None

    async def bad(*args, **kwargs):
        first.calls += 1
        raise shape
    first.decide = bad
    chain = FallbackProvider([first, second])
    with pytest.raises(LLMError):
        run(chain.decide("s", "p", "g"))
    assert second.calls == 0


def test_when_both_cannot_the_last_error_is_raised():
    first = Fake("Gemini", api_error(openai.RateLimitError, 429))
    second = Fake("Groq", api_error(openai.APIConnectionError, 0))
    chain = FallbackProvider([first, second])
    with pytest.raises(LLMError, match="Groq"):
        run(chain.decide("s", "p", "g"))
    assert chain.answered_by is None


def test_routing_and_details_fall_back_too():
    first, second = Fake("Gemini", api_error(openai.RateLimitError, 429)), Fake("Groq")
    chain = FallbackProvider([first, second])
    run(chain.choose_route("s", "g"))
    assert chain.answered_by == "Groq"
    run(chain.read_details("s", "g"))
    assert second.calls == 2


@pytest.mark.parametrize("base_url, label", [
    ("https://generativelanguage.googleapis.com/v1beta/openai/", "Gemini"),
    ("https://api.groq.com/openai/v1", "Groq"),
    ("https://openrouter.ai/api/v1", "OpenRouter"),
    (None, "OpenAI"),
    ("https://llm.example.edu/v1", "llm.example.edu"),
])
def test_a_provider_is_named_as_people_know_it(base_url, label):
    assert label_for(base_url) == label


def test_a_rate_limit_moves_on_at_once_when_there_is_a_fallback(monkeypatch):
    """The first provider in a chain does not wait out a rate limit — that is
    up to a minute of the person looking at "Give me a moment" — when another
    provider can answer now."""
    provider = OpenAICompatibleProvider(api_key="k", base_url="https://api.groq.com/openai/v1",
                                        model="m", wait_out_rate_limits=False)
    calls = []

    async def limited(messages, response_format):
        calls.append(1)
        raise api_error(openai.RateLimitError, 429, {"retry-after": "40"})
    monkeypatch.setattr(provider, "_call", limited)
    with pytest.raises(LLMError):
        run(provider.decide("s", "p", "g"))
    assert len(calls) == 1
    assert provider.throttled_seconds == 0


def test_the_environment_builds_gemini_then_groq(monkeypatch):
    monkeypatch.setattr(llm, "_load_dotenv", lambda: None)
    monkeypatch.setenv("SIMBA_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "gemini-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    monkeypatch.setenv("OPENAI_MODEL", "gemini-3.1-flash-lite")
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    monkeypatch.delenv("SIMBA_LLM_FALLBACK", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    provider = provider_from_env()
    assert isinstance(provider, FallbackProvider)
    assert [p.label for p in provider.providers] == ["Gemini", "Groq"]
    assert provider.providers[1].model == "openai/gpt-oss-120b"
    assert provider.providers[0].wait_out_rate_limits is False
    assert provider.providers[1].wait_out_rate_limits is True


# --- OpenRouter, the third (2026-11-14) --------------------------------------


def _gemini(monkeypatch):
    monkeypatch.setattr(llm, "_load_dotenv", lambda: None)
    monkeypatch.setenv("SIMBA_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "gemini-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    monkeypatch.setenv("OPENAI_MODEL", "gemini-3.1-flash-lite")
    for name in ("GROQ_MODEL", "GROQ_BASE_URL", "OPENROUTER_MODEL", "OPENROUTER_BASE_URL",
                 "SIMBA_LLM_FALLBACK"):
        monkeypatch.delenv(name, raising=False)


def test_the_environment_builds_gemini_then_groq_then_openrouter(monkeypatch):
    _gemini(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-key")
    provider = provider_from_env()
    assert isinstance(provider, FallbackProvider)
    assert [p.label for p in provider.providers] == ["Gemini", "Groq", "OpenRouter"]
    assert provider.providers[2].model == "nvidia/nemotron-3.5-super-vl:free"
    # Only the last waits out a rate limit: the others move on at once.
    assert [p.wait_out_rate_limits for p in provider.providers] == [False, False, True]


def test_openrouter_follows_gemini_when_there_is_no_groq_key(monkeypatch):
    _gemini(monkeypatch)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-key")
    provider = provider_from_env()
    assert [p.label for p in provider.providers] == ["Gemini", "OpenRouter"]


def test_openrouter_is_where_and_what_env_says(monkeypatch):
    _gemini(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-key")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("OPENROUTER_MODEL", "google/gemma-4-31b-it:free")
    provider = provider_from_env()
    assert provider.providers[2].label == "OpenRouter"
    assert provider.providers[2].model == "google/gemma-4-31b-it:free"


def test_switched_off_there_is_no_openrouter_either(monkeypatch):
    _gemini(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-key")
    monkeypatch.setenv("SIMBA_LLM_FALLBACK", "0")
    assert isinstance(provider_from_env(), OpenAICompatibleProvider)


def test_when_gemini_and_groq_cannot_openrouter_answers_and_is_named():
    first = Fake("Gemini", api_error(openai.RateLimitError, 429))
    second = Fake("Groq", api_error(openai.RateLimitError, 429))
    third = Fake("OpenRouter")
    chain = FallbackProvider([first, second, third])
    assert run(chain.decide("s", "p", "g")) == ACTION
    assert (first.calls, second.calls, third.calls) == (1, 1, 1)
    assert chain.answered_by == "OpenRouter"
    assert chain.label == "OpenRouter"


def test_a_saved_setup_is_followed_by_groq_then_openrouter(monkeypatch, tmp_path):
    from backend.orchestrator import ai_settings

    _gemini(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-key")
    saved = ai_settings.AiSettings(provider="gemini", key="saved-key",
                                   base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                                   model="gemini-3.1-flash-lite")
    monkeypatch.setattr(ai_settings.AiStore, "load", lambda self: saved)
    provider = provider_from_env()
    assert [p.label for p in provider.providers] == ["Gemini", "Groq", "OpenRouter"]


def test_the_openrouter_key_is_never_in_an_error(monkeypatch):
    _gemini(monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-secret-value")
    with pytest.raises(LLMError) as raised:
        provider_from_env()
    assert "openrouter-secret-value" not in str(raised.value)


def test_no_groq_key_is_gemini_alone(monkeypatch):
    monkeypatch.setattr(llm, "_load_dotenv", lambda: None)
    monkeypatch.setenv("SIMBA_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "gemini-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    provider = provider_from_env()
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.label == "Gemini" and provider.wait_out_rate_limits is True


def test_the_fallback_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(llm, "_load_dotenv", lambda: None)
    monkeypatch.setenv("SIMBA_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "gemini-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    monkeypatch.setenv("SIMBA_LLM_FALLBACK", "0")
    assert isinstance(provider_from_env(), OpenAICompatibleProvider)


def test_no_key_is_said_without_the_key(monkeypatch):
    monkeypatch.setattr(llm, "_load_dotenv", lambda: None)
    monkeypatch.setenv("SIMBA_LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "groq-secret-value")
    with pytest.raises(LLMError) as raised:
        provider_from_env()
    assert "groq-secret-value" not in str(raised.value)


def test_answer_is_an_action_the_model_can_give():
    answer = Action(action="answer", element_id=0, value="25 December", reasoning="It says so.")
    assert answer.action == "answer"
    assert "answer" in llm.ACTION_SCHEMA["properties"]["action"]["enum"]
