"""Provider-layer tests. None of these call a real API."""

import json

import pytest

from backend.orchestrator.llm import (
    Action,
    LLMError,
    Transcript,
    build_user_prompt,
    provider_from_env,
    validate_action,
)


def test_action_rejects_an_unknown_verb() -> None:
    with pytest.raises(Exception):
        Action.model_validate({"action": "teleport", "element_id": 1, "reasoning": "x"})


def test_action_requires_an_integer_element_id() -> None:
    with pytest.raises(Exception):
        Action.model_validate(
            {"action": "click", "element_id": "#submit", "reasoning": "x"}
        )


def test_action_accepts_a_null_value_for_click() -> None:
    action = Action.model_validate(
        {"action": "click", "element_id": 14, "value": None, "reasoning": "the button"}
    )
    assert action.element_id == 14
    assert action.value is None


def test_prompt_carries_the_goal_and_page() -> None:
    prompt = build_user_prompt("1. button 'Sign In'", "Register for CS-401", None)
    assert "Register for CS-401" in prompt
    assert "button 'Sign In'" in prompt
    assert "rejected" not in prompt


def test_feedback_is_fed_back_into_the_prompt() -> None:
    prompt = build_user_prompt("1. button 'Sign In'", "goal", "element_id 99 does not exist")
    assert "element_id 99 does not exist" in prompt
    assert "Do not repeat it" in prompt


def test_validate_rejects_the_shape_a_real_model_actually_returned() -> None:
    """A live run produced exactly this: the action nested under a wrapper."""
    raw = '{"thought": "fill the username", "action": {"element_id": 21, "type": "type"}}'

    with pytest.raises(LLMError) as caught:
        validate_action(raw)

    message = str(caught.value)
    assert "did not match the action schema" in message
    assert "element_id" in message  # names the missing field
    assert "action" in message


def test_validate_rejects_the_other_shape_a_real_model_returned() -> None:
    """Also seen live: 'reason' instead of 'reasoning'."""
    raw = '{"element_id": 21, "action": "type", "value": null, "reason": "because"}'

    with pytest.raises(LLMError, match="reasoning"):
        validate_action(raw)


def test_validate_rejects_a_string_element_id() -> None:
    raw = '{"action": "click", "element_id": "#submit", "value": null, "reasoning": "x"}'

    with pytest.raises(LLMError, match="element_id"):
        validate_action(raw)


def test_validate_rejects_an_unknown_verb() -> None:
    raw = '{"action": "teleport", "element_id": 1, "value": null, "reasoning": "x"}'

    with pytest.raises(LLMError, match="action"):
        validate_action(raw)


def test_validate_rejects_text_that_is_not_json() -> None:
    with pytest.raises(LLMError, match="not valid JSON|did not match"):
        validate_action("I think you should click the Sign In button.")


def test_validate_accepts_a_dict_as_well_as_json() -> None:
    """The Anthropic path hands over a dict; the OpenAI path hands over text."""
    payload = {"action": "click", "element_id": 7, "value": None, "reasoning": "ok"}

    from_dict = validate_action(payload)
    from_json = validate_action(json.dumps(payload))

    assert from_dict == from_json
    assert from_dict.element_id == 7


def test_transcript_writes_one_json_line_per_entry(tmp_path) -> None:
    transcript = Transcript(tmp_path / "run.jsonl")
    transcript.record(provider="anthropic", user="pick an element")
    transcript.record(provider="anthropic", response={"action": "click"})

    lines = transcript.path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["user"] == "pick an element"
    assert json.loads(lines[1])["response"] == {"action": "click"}
    assert "ts" in json.loads(lines[0])


def test_unknown_provider_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("SIMBA_LLM_PROVIDER", "definitely-not-a-provider")
    with pytest.raises(LLMError, match="unknown SIMBA_LLM_PROVIDER"):
        provider_from_env()


def test_missing_key_names_the_variable(monkeypatch) -> None:
    monkeypatch.setenv("SIMBA_LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("backend.orchestrator.llm._load_dotenv", lambda: None)

    with pytest.raises(LLMError, match="ANTHROPIC_API_KEY is not set"):
        provider_from_env()
