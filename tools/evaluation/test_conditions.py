"""The conditions a measurement was taken under are recorded, and no secret is.

Why this is tested at all: the 2026-09-06 benchmark figure could not be
explained because its result file held numbers and nothing else
(EVALUATION.md, 2026-09-17e). The November benchmark is the one the report is
built on, so the recording has to be right, and the one thing it must never
record is a credential — it reads `.env` for the model string.
"""

import json
import subprocess

import pytest

from tools.evaluation import conditions as module


@pytest.fixture
def recorded() -> dict:
    return module.conditions()


def test_it_records_the_commit_that_is_checked_out(recorded: dict) -> None:
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                          cwd=module.REPO_ROOT, check=True).stdout.strip()
    assert recorded["git"]["commit"] == head[:12]
    assert recorded["git"]["branch"]
    assert recorded["git"]["dirty"] in (True, False)


def test_it_records_the_interpreter_and_whether_it_is_the_project_venv(recorded: dict) -> None:
    assert recorded["python"]["version"].count(".") == 2
    assert recorded["python"]["executable"]
    assert isinstance(recorded["python"]["project_venv"], bool)


def test_it_records_playwright_and_the_machine(recorded: dict) -> None:
    assert recorded["playwright"], "playwright version not found"
    assert recorded["machine"]["cpus"] >= 1
    assert recorded["machine"]["platform"]
    load = recorded["machine"]["load_percent"]
    assert load is None or 0 <= load <= 100


def test_every_switch_is_recorded_even_when_it_is_not_set(recorded: dict) -> None:
    """"Not set" has to be stated. An ablation arm nobody wrote down is the
    same problem as a timing nobody wrote down."""
    assert set(recorded["switches"]) == set(module.SWITCHES)
    assert "SIMBA_OVERLAY_DETECTION" in recorded["switches"]


def test_the_model_comes_from_the_environment_first(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIMBA_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_MODEL", "some-pinned-model")
    assert module.model() == {"provider": "openai", "model": "some-pinned-model",
                              "model_from": "environment"}


def test_the_model_is_read_from_dotenv_when_the_environment_is_silent(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    (tmp_path / ".env").write_text(
        "SIMBA_LLM_PROVIDER=openai\nOPENAI_MODEL=gemini-3.1-flash-lite\n", encoding="utf-8")
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.delenv("SIMBA_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    assert module.model() == {"provider": "openai", "model": "gemini-3.1-flash-lite",
                              "model_from": ".env"}


def test_no_key_in_dotenv_is_ever_read(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """The rule with no exceptions: secrets never enter a log (CLAUDE.md)."""
    (tmp_path / ".env").write_text(
        "OPENAI_API_KEY=sk-should-never-be-recorded\n"
        "ANTHROPIC_API_KEY=also-not-this\n"
        "SIMBA_LLM_PROVIDER=openai\nOPENAI_MODEL=a-model\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    assert module._dotenv() == {"SIMBA_LLM_PROVIDER": "openai", "OPENAI_MODEL": "a-model"}
    written = json.dumps(module.conditions()) + module.banner()
    assert "should-never-be-recorded" not in written
    assert "also-not-this" not in written
    assert "API_KEY" not in written


def test_the_banner_says_what_it_could_not_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unknown load reads as unknown, never as zero."""
    monkeypatch.setattr(module, "load_percent", lambda: None)
    assert "load unknown" in module.banner()


def test_the_banner_says_what_the_machine_was_doing() -> None:
    """2026-10-17: the same commit's suite took 805s one day and 1435s the
    next, and nothing recorded the machine's state either time."""
    line = module.power_line({"on_battery": True, "charge_percent": 40,
                              "cpu_performance_percent": 48, "free_memory_mb": 1200})
    assert line == ("power       ON BATTERY (40%), processor at 48% of rated speed, "
                    "1200 MB memory free")
    assert module.power_line({"on_battery": False}) == "power       on mains"
    assert module.power_line({}) == "power       unknown power source"


def test_the_banner_warns_about_a_dirty_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "git_state", lambda: {"commit": "abc123", "branch": "x", "dirty": True})
    assert "DIRTY TREE" in module.banner()


def test_results_are_written_with_their_conditions(tmp_path) -> None:
    out = tmp_path / "nested" / "result.json"
    module.record(out, [{"run": 1, "seconds": 3.0}], runs=1)

    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["results"] == [{"run": 1, "seconds": 3.0}]
    assert written["conditions"]["runs"] == 1
    assert written["conditions"]["git"]["commit"]
    assert written["conditions"]["machine"]["cpus"] >= 1
