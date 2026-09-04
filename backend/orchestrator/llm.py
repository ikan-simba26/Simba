"""The planning LLM, behind one thin interface.

One method, `decide`, takes a system prompt, a serialized page, and the goal,
and returns a structured action. Two providers implement it — Anthropic and
any OpenAI-compatible endpoint — chosen by `SIMBA_LLM_PROVIDER`.

Two rules from CLAUDE.md shape this module:

- **The model never emits a selector.** It returns an integer `element_id`
  taken from the serialized page; the orchestrator resolves it to a handle.
- **The model never sees a credential.** The serialized page carries element
  labels, never values, and the vault's values are injected by the
  orchestrator after the model has chosen. Nothing secret reaches a prompt,
  and so nothing secret reaches the transcript either.

Every prompt and response is written to `logs/` (gitignored) so a run's
reasoning can be read back afterwards.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = REPO_ROOT / "logs"

ANTHROPIC_DEFAULT_MODEL = "claude-opus-5"
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
MAX_TOKENS = 16000


class Action(BaseModel):
    """What the model wants done next."""

    action: Literal["click", "type", "select"]
    element_id: int
    value: str | None = None
    reasoning: str


class LLMError(RuntimeError):
    """The provider could not produce a usable action."""


class Provider(Protocol):
    async def decide(
        self, system_prompt: str, page: str, goal: str, feedback: str | None = None
    ) -> Action: ...


def build_user_prompt(page: str, goal: str, feedback: str | None) -> str:
    parts = [f"Goal: {goal}", "", "Interactive elements on the page:", page]
    if feedback:
        parts += [
            "",
            "Your previous answer was rejected. Do not repeat it.",
            f"Problem: {feedback}",
        ]
    return "\n".join(parts)


class Transcript:
    """Appends every prompt and response to logs/, as JSON lines."""

    def __init__(self, path: Path | None = None) -> None:
        if path is None:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            path = LOG_DIR / f"llm-{stamp}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path

    def record(self, **entry: object) -> None:
        entry["ts"] = datetime.now(timezone.utc).isoformat()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


class AnthropicProvider:
    """Anthropic, using structured outputs so the shape is guaranteed."""

    name = "anthropic"

    def __init__(
        self,
        api_key: str,
        model: str = ANTHROPIC_DEFAULT_MODEL,
        effort: str = "low",
        transcript: Transcript | None = None,
    ) -> None:
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model
        self._effort = effort
        self._transcript = transcript or Transcript()

    async def decide(
        self, system_prompt: str, page: str, goal: str, feedback: str | None = None
    ) -> Action:
        import anthropic

        user_prompt = build_user_prompt(page, goal, feedback)
        self._transcript.record(
            provider=self.name, model=self._model, system=system_prompt, user=user_prompt
        )

        try:
            message = await self._client.messages.parse(
                model=self._model,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                output_config={"effort": self._effort},
                output_format=Action,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except anthropic.APIError as error:
            self._transcript.record(provider=self.name, error=str(error))
            raise LLMError(f"Anthropic call failed: {error}") from error

        if message.stop_reason == "refusal":
            self._transcript.record(provider=self.name, refusal=str(message.stop_details))
            raise LLMError("the model declined to answer")

        for block in message.content:
            parsed = getattr(block, "parsed_output", None)
            if isinstance(parsed, Action):
                self._transcript.record(
                    provider=self.name, response=parsed.model_dump(), usage=str(message.usage)
                )
                return parsed

        self._transcript.record(provider=self.name, malformed=str(message.content))
        raise LLMError("no structured action in the response")


class OpenAICompatibleProvider:
    """Any OpenAI-compatible chat completions endpoint."""

    name = "openai"

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model: str = OPENAI_DEFAULT_MODEL,
        transcript: Transcript | None = None,
    ) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._transcript = transcript or Transcript()

    async def decide(
        self, system_prompt: str, page: str, goal: str, feedback: str | None = None
    ) -> Action:
        import openai

        user_prompt = build_user_prompt(page, goal, feedback)
        self._transcript.record(
            provider=self.name, model=self._model, system=system_prompt, user=user_prompt
        )

        try:
            completion = await self._client.chat.completions.create(
                model=self._model,
                max_tokens=MAX_TOKENS,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except openai.OpenAIError as error:
            self._transcript.record(provider=self.name, error=str(error))
            raise LLMError(f"OpenAI-compatible call failed: {error}") from error

        raw = completion.choices[0].message.content or ""
        self._transcript.record(provider=self.name, raw_response=raw)

        try:
            action = Action.model_validate_json(raw)
        except ValidationError as error:
            raise LLMError(f"response did not match the action schema: {error}") from error

        self._transcript.record(provider=self.name, response=action.model_dump())
        return action


def provider_from_env(transcript: Transcript | None = None) -> Provider:
    """Build the configured provider. Keys come from the environment or .env."""
    _load_dotenv()
    choice = os.environ.get("SIMBA_LLM_PROVIDER", "anthropic").strip().lower()

    if choice == "anthropic":
        return AnthropicProvider(
            api_key=_require_key("ANTHROPIC_API_KEY"),
            model=os.environ.get("ANTHROPIC_MODEL", ANTHROPIC_DEFAULT_MODEL),
            effort=os.environ.get("SIMBA_LLM_EFFORT", "low"),
            transcript=transcript,
        )

    if choice == "openai":
        return OpenAICompatibleProvider(
            api_key=_require_key("OPENAI_API_KEY"),
            base_url=os.environ.get("OPENAI_BASE_URL"),
            model=os.environ.get("OPENAI_MODEL", OPENAI_DEFAULT_MODEL),
            transcript=transcript,
        )

    raise LLMError(f"unknown SIMBA_LLM_PROVIDER {choice!r}; expected 'anthropic' or 'openai'")


def _require_key(name: str) -> str:
    key = os.environ.get(name)
    if not key:
        raise LLMError(f"{name} is not set. Put it in .env, which is never committed.")
    return key


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(REPO_ROOT / ".env")
