"""No test writes to the system temp directory (CLAUDE.md, tooling boundaries)."""

from pathlib import Path

REPO = Path(__file__).resolve().parent


def test_tmp_path_is_inside_the_repository(tmp_path: Path) -> None:
    assert tmp_path.resolve().is_relative_to((REPO / ".scratch" / "pytest").resolve())


def test_the_session_factory_is_too(tmp_path_factory) -> None:
    base = tmp_path_factory.getbasetemp().resolve()
    assert base == (REPO / ".scratch" / "pytest").resolve()


def test_a_fresh_clone_with_no_scratch_folder_gets_one(tmp_path: Path, monkeypatch) -> None:
    """`.scratch/` is ignored, so a fresh clone has none, and pytest makes only
    the last folder of `--basetemp`: until 2026-10-17 every test that used
    `tmp_path` errored on a fresh clone (EVALUATION.md, 2026-10-17k)."""
    from types import SimpleNamespace

    import conftest

    target = tmp_path / "fresh-clone" / ".scratch" / "pytest"
    monkeypatch.setattr(conftest, "BASETEMP", target)
    config = SimpleNamespace(option=SimpleNamespace(basetemp=None))

    conftest.pytest_configure(config)

    assert target.parent.is_dir()
    assert config.option.basetemp == str(target)
