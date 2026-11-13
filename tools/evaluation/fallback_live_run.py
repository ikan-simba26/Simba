"""Gemini -> Groq -> OpenRouter, live, once each way (2026-11-13).

    python -m tools.evaluation.fallback_live_run

One planner step on a public page — gov.uk's bank holidays, as read by
`prompt_size_probe capture` (`.scratch/prompt-samples.json`) — through the chain
`provider_from_env` builds from `.env`, three times:

  A. as configured: Gemini should answer;
  B. Gemini asked for a model that does not exist, so Google answers 404 and
     the chain moves on: Groq should answer;
  C. Gemini and Groq both asked for models that do not exist: OpenRouter
     should answer.

Every call is a real request to the real provider. The failures are real
errors from the real services, chosen because a rate limit cannot be had on
cue; a 404 and a 429 take the same path (`llm._cannot_answer_now`). The label
recorded is the one the app shows ("worked out with …"). No key is printed
and nothing personal is in the prompt.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tools.evaluation.conditions import banner, record  # noqa: E402
from tools.evaluation.prompt_size_probe import SAMPLES, prompt_for  # noqa: E402

MISSING_MODEL = "no-such-model-simba-fallback-test"

CASES = [
    ("A. as configured", {}),
    ("B. Gemini unavailable", {"OPENAI_MODEL": MISSING_MODEL}),
    ("C. Gemini and Groq unavailable", {"OPENAI_MODEL": MISSING_MODEL,
                                        "GROQ_MODEL": MISSING_MODEL}),
]


async def one(name: str, overrides: dict[str, str], sample: dict) -> dict:
    from backend.orchestrator import llm

    llm._load_dotenv()
    saved = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)
    try:
        chain = llm.provider_from_env()
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    providers = getattr(chain, "providers", [chain])
    system, page = prompt_for(sample)
    started = time.monotonic()
    row: dict = {"case": name, "chain": [p.label for p in providers],
                 "models": [p.model for p in providers]}
    try:
        action = await chain.decide(system, page, sample["goal"])
        row.update(answered_by=getattr(chain, "answered_by", None) or chain.label,
                   fell_back=getattr(chain, "fell_back", 0), action=action.action,
                   value=(action.value or "")[:80])
    except llm.LLMError as error:
        row.update(answered_by=None, error=type(error.__cause__ or error).__name__)
    row["seconds"] = round(time.monotonic() - started, 2)
    return row


async def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(banner(), flush=True)
    samples = json.loads(SAMPLES.read_text(encoding="utf-8"))
    sample = next(s for s in samples if s["name"] == "gov.uk bank holidays")
    rows = []
    for name, overrides in CASES:
        row = await one(name, overrides, sample)
        print(json.dumps(row), flush=True)
        rows.append(row)
    record(REPO / ".scratch" / "fallback-live-run.json", {"page": sample["url"],
                                                          "goal": sample["goal"], "rows": rows})


if __name__ == "__main__":
    asyncio.run(main())
