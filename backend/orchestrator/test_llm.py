"""Provider-layer tests. None of these call a real API."""

import json

import pytest

from backend.orchestrator.llm import (
    Action,
    LLMError,
    Transcript,
    build_user_prompt,
    Usage,
    estimate_cost,
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
    assert "SOMETHING WENT WRONG" not in prompt


def test_feedback_is_fed_back_into_the_prompt() -> None:
    prompt = build_user_prompt("1. button 'Sign In'", "goal", "element_id 99 does not exist")
    assert "element_id 99 does not exist" in prompt
    assert "SOMETHING WENT WRONG" in prompt


def test_feedback_sits_above_the_element_list() -> None:
    """Position, not presence. A live run proved presence is not enough.

    The model was told at the end of its prompt that the date it had set was
    the wrong month, with the setback eighteen element lines below the thing
    it was about, and clicked search anyway. Same lesson as the overlay
    banner: anything a planner must act on at this step goes above the list.
    """
    prompt = build_user_prompt(
        "1. button 'Search'", "goal", "the date is wrong", ["Fill in Departure Date."]
    )

    assert prompt.index("the date is wrong") < prompt.index("Already done")
    assert prompt.index("the date is wrong") < prompt.index("Interactive elements")


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


def test_history_is_capped_at_the_limit_but_keeps_the_goal() -> None:
    history = [f"action {i}" for i in range(1, 26)]

    prompt = build_user_prompt("1. button 'Go'", "Register for CS-401", None, history)

    assert "Register for CS-401" in prompt          # the goal always survives
    assert "action 25" in prompt and "action 16" in prompt   # the last 10
    assert "action 15" not in prompt                # and nothing older
    assert "15 earlier actions omitted" in prompt   # said out loud, not silent


def test_history_under_the_limit_is_not_truncated() -> None:
    prompt = build_user_prompt("1. button 'Go'", "goal", None, ["a", "b", "c"])

    assert "omitted" not in prompt
    assert "1. a" in prompt and "3. c" in prompt


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


# --- token and cost accounting ----------------------------------------------


def test_usage_accumulates_across_calls() -> None:
    usage = Usage()
    usage.add(1000, 200, "claude-opus-5")
    usage.add(500, 100, "claude-opus-5")

    assert usage.calls == 2
    assert usage.prompt_tokens == 1500
    assert usage.completion_tokens == 300
    assert usage.total_tokens == 1800


def test_cost_uses_the_rate_table() -> None:
    # 1M prompt at $5 plus 1M completion at $25.
    assert estimate_cost(1_000_000, 1_000_000, "claude-opus-5") == 30.0
    assert estimate_cost(1000, 0, "claude-opus-5") == 0.005


def test_an_unknown_model_is_unpriced_rather_than_free() -> None:
    assert estimate_cost(1000, 1000, "some-model-we-have-no-rate-for") is None

    usage = Usage()
    usage.add(1000, 1000, "some-model-we-have-no-rate-for")

    assert usage.priced is False
    assert usage.cost_usd == 0.0
    assert "unpriced" in usage.summary_row("run")


def test_a_mixed_run_is_marked_unpriced() -> None:
    """One unrated call makes the whole total untrustworthy, and says so."""
    usage = Usage()
    usage.add(1000, 100, "claude-opus-5")
    usage.add(1000, 100, "mystery-model")

    assert usage.priced is False


def test_the_summary_row_is_evaluation_table_format() -> None:
    usage = Usage()
    usage.add(2000, 400, "gemini-3.1-flash-lite")

    row = usage.summary_row("registration, LLM")

    assert row == (
        "| registration, LLM | gemini-3.1-flash-lite | 1 | 2000 | 400 | 2400 | $0.000360 |"
    )


def test_usage_serialises_for_the_run_log() -> None:
    usage = Usage()
    usage.add(100, 10, "gpt-4o-mini")

    payload = usage.as_dict()

    assert payload["calls"] == 1
    assert payload["total_tokens"] == 110
    assert payload["model"] == "gpt-4o-mini"
    assert payload["cost_usd"] > 0


def test_the_setback_can_be_put_back_after_the_list_for_comparison(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ablation arm. `SIMBA_SETBACK_PLACEMENT=after` is where the setback
    sat until 2026-09-09, and the only way to compare the two on a real run
    rather than on one re-asked decision (EVALUATION.md, 2026-09-17j)."""
    monkeypatch.setenv("SIMBA_SETBACK_PLACEMENT", "after")

    prompt = build_user_prompt("1. button 'Continue'", "goal", "that did nothing")

    assert prompt.index("SOMETHING WENT WRONG") > prompt.index("button 'Continue'")
    assert "that did nothing" in prompt


def test_above_is_what_an_unset_switch_means(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SIMBA_SETBACK_PLACEMENT", raising=False)
    prompt = build_user_prompt("1. button 'Continue'", "goal", "that did nothing")
    assert prompt.index("SOMETHING WENT WRONG") < prompt.index("button 'Continue'")


def test_an_unknown_placement_is_the_design_not_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A typo in an ablation switch must not quietly select the worse arm."""
    monkeypatch.setenv("SIMBA_SETBACK_PLACEMENT", "sideways")
    prompt = build_user_prompt("1. button 'Continue'", "goal", "that did nothing")
    assert prompt.index("SOMETHING WENT WRONG") < prompt.index("button 'Continue'")
