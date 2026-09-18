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

import asyncio
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = REPO_ROOT / "logs"

ANTHROPIC_DEFAULT_MODEL = "claude-opus-5"
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
MAX_TOKENS = 16000
HISTORY_LIMIT = 10  # actions kept in the prompt; see build_user_prompt
# Where a setback goes in the prompt: "above" the element list, or "after" it.
#
# An ablation switch, not a setting. Above is the design (see
# `build_user_prompt`); after is where it used to be, kept only so the two can
# be compared on a run rather than argued about. Read per call so a benchmark
# can flip arms between processes.
SETBACK_ABOVE = "above"
SETBACK_AFTER = "after"
RATE_LIMIT_RETRIES = 4  # a free tier meters per minute; wait it out

# US dollars per million tokens, (prompt, completion). Rates move and vary by
# region, so this is a lookup to keep current rather than a source of truth —
# an unknown model costs nothing rather than guessing, and a run says so.
RATES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "gpt-4o-mini": (0.15, 0.60),
    # Free tier at time of writing; priced here at the published paid rates so
    # a run reports what it would cost rather than zero.
    "gemini-3.1-flash-lite": (0.10, 0.40),
    "gemini-3.8-flash": (0.30, 2.50),
    "gemini-3.6-flash": (0.30, 2.50),
}


@dataclass
class Usage:
    """What one call, or a whole run, consumed."""

    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""
    priced: bool = True

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def add(self, prompt: int, completion: int, model: str) -> "Usage":
        rate = RATES_PER_MTOK.get(model)
        self.calls += 1
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.model = model
        if rate is None:
            self.priced = False
        else:
            self.cost_usd += (prompt * rate[0] + completion * rate[1]) / 1_000_000
        return self

    def as_dict(self) -> dict:
        return {
            "model": self.model,
            "calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "priced": self.priced,
        }

    def summary_row(self, label: str) -> str:
        """One line in EVALUATION.md's table format."""
        # Per-run costs here are fractions of a cent; four places round
        # them all to $0.0000, which reads as free rather than small.
        cost = f"${self.cost_usd:.6f}" if self.priced else "unpriced"
        return (
            f"| {label} | {self.model} | {self.calls} | {self.prompt_tokens} | "
            f"{self.completion_tokens} | {self.total_tokens} | {cost} |"
        )


def estimate_cost(prompt_tokens: int, completion_tokens: int, model: str) -> float | None:
    """Dollars for one call, or None if the model has no rate on file."""
    rate = RATES_PER_MTOK.get(model)
    if rate is None:
        return None
    return (prompt_tokens * rate[0] + completion_tokens * rate[1]) / 1_000_000


class Action(BaseModel):
    """What the model wants done next."""

    action: Literal["click", "type", "select"]
    element_id: int
    value: str | None = None
    reasoning: str


class LLMError(RuntimeError):
    """The provider could not produce a usable action."""


ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["click", "type", "select"]},
        "element_id": {"type": "integer"},
        "value": {"type": ["string", "null"]},
        "reasoning": {"type": "string"},
    },
    "required": ["action", "element_id", "value", "reasoning"],
    "additionalProperties": False,
}


def validate_action(raw: object) -> Action:
    """The one gate every provider's output passes through.

    Structured outputs make a bad shape unlikely on some providers and
    impossible on none, so nothing is trusted: both paths validate here, and
    both produce the same error text for the retry to feed back.
    """
    try:
        if isinstance(raw, (str, bytes)):
            return Action.model_validate_json(raw)
        return Action.model_validate(raw)
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or 'response'}: {e['msg']}"
            for e in error.errors()
        )
        raise LLMError(f"response did not match the action schema — {problems}") from error
    except ValueError as error:
        raise LLMError(f"response was not valid JSON: {error}") from error


class Provider(Protocol):
    async def decide(
        self,
        system_prompt: str,
        page: str,
        goal: str,
        feedback: str | None = None,
        history: list[str] | None = None,
    ) -> Action: ...


def setback_placement() -> str:
    """Where a setback is put. `SIMBA_SETBACK_PLACEMENT=after` restores the
    old position, for the comparison recorded in EVALUATION.md."""
    choice = os.environ.get("SIMBA_SETBACK_PLACEMENT", SETBACK_ABOVE).strip().lower()
    return SETBACK_AFTER if choice == SETBACK_AFTER else SETBACK_ABOVE


SETBACK_HEADING = (
    "SOMETHING WENT WRONG WITH YOUR LAST ANSWER. Put it right before "
    "anything else — do not move on to another part of the task."
)


def build_user_prompt(
    page: str, goal: str, feedback: str | None, history: list[str] | None = None
) -> str:
    parts = [f"Goal: {goal}", ""]
    above = setback_placement() == SETBACK_ABOVE

    # Feedback goes first, in the imperative, above the history and above the
    # element list.
    #
    # It used to be appended after the page, and a live run showed what that
    # costs. The model was told in plain words that the date it had set was
    # the wrong one and that the choice needed committing — and it clicked
    # search anyway, because the setback was sitting eighteen element lines
    # below the thing it was about. Same lesson as the overlay banner and the
    # open-choices banner, in a third place: anything a planner must act on
    # *at this step* sits above the list, or it competes with the list and
    # loses. See EVALUATION.md, "Where information sits is a perception
    # decision".
    if feedback and above:
        parts += [SETBACK_HEADING, f"Problem: {feedback}", ""]

    # Without this the model has no memory of its own actions and will keep
    # choosing the step it already completed.
    #
    # The goal is always carried in full; the action list is capped at the
    # last HISTORY_LIMIT. This is a deliberate choice, not an oversight. The
    # two alternatives:
    #   - Unbounded history. Exact, but the prompt grows without limit, so
    #     cost and latency climb with every step and a long task eventually
    #     runs into the context window.
    #   - Summarise older actions. Keeps some of the dropped context, but
    #     costs an extra model call per summary and can quietly rewrite what
    #     actually happened, which is a bad trade in a verification path.
    # A flat window is predictable and cheap. Revisit if tasks start needing
    # to recall something from more than HISTORY_LIMIT actions ago.
    if history:
        recent = history[-HISTORY_LIMIT:]
        dropped = len(history) - len(recent)
        parts += ["Already done, in order:"]
        if dropped:
            parts += [f"  (…{dropped} earlier action{'s' if dropped > 1 else ''} omitted)"]
        parts += [f"  {i}. {done}" for i, done in enumerate(recent, start=dropped + 1)]
        parts += ["", "Choose what comes next. Do not repeat any of the above.", ""]
    else:
        parts += ["Nothing has been done yet. This is the first action.", ""]

    parts += ["Interactive elements on the page:", page]

    # The arm this exists to compare against: the same words, after the list,
    # which is where they were until 2026-09-09 and where a live run showed
    # the model reading past them.
    if feedback and not above:
        parts += ["", SETBACK_HEADING, f"Problem: {feedback}"]
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
        self.usage = Usage()

    async def decide(
        self,
        system_prompt: str,
        page: str,
        goal: str,
        feedback: str | None = None,
        history: list[str] | None = None,
    ) -> Action:
        import anthropic

        user_prompt = build_user_prompt(page, goal, feedback, history)
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
            if parsed is None:
                continue
            raw = parsed.model_dump() if isinstance(parsed, BaseModel) else parsed
            self._transcript.record(provider=self.name, raw_response=raw)
            # Validated even though structured outputs should guarantee it.
            action = validate_action(raw)
            self._record_usage(
                getattr(message.usage, "input_tokens", 0),
                getattr(message.usage, "output_tokens", 0),
            )
            self._transcript.record(provider=self.name, response=action.model_dump())
            return action

        self._transcript.record(provider=self.name, malformed=str(message.content))
        raise LLMError("no structured action in the response")

    def _record_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        before = self.usage.cost_usd
        self.usage.add(prompt_tokens, completion_tokens, self._model)
        self._transcript.record(
            provider=self.name,
            model=self._model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            call_cost_usd=round(self.usage.cost_usd - before, 6),
            run_cost_usd=round(self.usage.cost_usd, 6),
            run_total_tokens=self.usage.total_tokens,
        )


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
        # Seconds spent waiting out rate limits, excluded from real latency.
        self.throttled_seconds = 0.0
        self.usage = Usage()

    async def decide(
        self,
        system_prompt: str,
        page: str,
        goal: str,
        feedback: str | None = None,
        history: list[str] | None = None,
    ) -> Action:
        import openai

        user_prompt = build_user_prompt(page, goal, feedback, history)
        self._transcript.record(
            provider=self.name, model=self._model, system=system_prompt, user=user_prompt
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # A JSON schema pins the shape. Plain json_object only guarantees
        # valid JSON, and models drift between key names and nest the action
        # under a wrapper. Not every compatible endpoint accepts a schema, so
        # fall back rather than fail.
        try:
            completion = await self._call_with_backoff(messages, self._schema_format())
        except openai.BadRequestError:
            self._transcript.record(provider=self.name, note="schema rejected, using json_object")
            try:
                completion = await self._call_with_backoff(messages, {"type": "json_object"})
            except openai.OpenAIError as error:
                self._transcript.record(provider=self.name, error=str(error))
                raise LLMError(f"OpenAI-compatible call failed: {error}") from error
        except openai.OpenAIError as error:
            self._transcript.record(provider=self.name, error=str(error))
            raise LLMError(f"OpenAI-compatible call failed: {error}") from error

        raw = completion.choices[0].message.content or ""
        self._transcript.record(provider=self.name, raw_response=raw)

        counts = getattr(completion, "usage", None)
        self._record_usage(
            getattr(counts, "prompt_tokens", 0) or 0,
            getattr(counts, "completion_tokens", 0) or 0,
        )

        action = validate_action(raw)

        self._transcript.record(provider=self.name, response=action.model_dump())
        return action

    def _record_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        before = self.usage.cost_usd
        self.usage.add(prompt_tokens, completion_tokens, self._model)
        self._transcript.record(
            provider=self.name,
            model=self._model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            call_cost_usd=round(self.usage.cost_usd - before, 6),
            run_cost_usd=round(self.usage.cost_usd, 6),
            run_total_tokens=self.usage.total_tokens,
        )

    async def _call_with_backoff(self, messages: list[dict], response_format: dict):
        """Wait out rate limits rather than failing the run.

        Free tiers meter per minute, so a burst of planning calls trips the
        limit even when the daily allowance is untouched. The server says how
        long to wait; honour it. Time spent waiting is accumulated separately
        so a benchmark can report it apart from real latency.
        """
        import openai

        delay = 1.0
        for attempt in range(RATE_LIMIT_RETRIES + 1):
            try:
                return await self._call(messages, response_format)
            except openai.RateLimitError as error:
                if attempt == RATE_LIMIT_RETRIES:
                    raise
                wait = _retry_after(error) or delay
                self.throttled_seconds += wait
                self._transcript.record(
                    provider=self.name, rate_limited=True, waited_seconds=round(wait, 1)
                )
                await asyncio.sleep(wait)
                delay = min(delay * 2, 60.0)
        raise AssertionError("unreachable")

    def _schema_format(self) -> dict:
        return {
            "type": "json_schema",
            "json_schema": {"name": "action", "strict": True, "schema": ACTION_SCHEMA},
        }

    async def _call(self, messages: list[dict], response_format: dict):
        return await self._client.chat.completions.create(
            model=self._model,
            max_tokens=MAX_TOKENS,
            response_format=response_format,
            messages=messages,
        )


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


def _retry_after(error: Exception) -> float | None:
    """Seconds the server asked us to wait, if it said."""
    headers = getattr(getattr(error, "response", None), "headers", None)
    if headers:
        raw = headers.get("retry-after")
        if raw:
            try:
                return float(raw)
            except ValueError:
                pass
    match = re.search(r"retry in ([0-9.]+)s", str(error))
    if match:
        return float(match.group(1)) + 1.0
    return None


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
