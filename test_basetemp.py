"""No test writes to the system temp directory (CLAUDE.md, tooling boundaries)."""

from pathlib import Path

REPO = Path(__file__).resolve().parent


def test_tmp_path_is_inside_the_repository(tmp_path: Path) -> None:
    assert tmp_path.resolve().is_relative_to((REPO / ".scratch" / "pytest").resolve())


def test_the_session_factory_is_too(tmp_path_factory) -> None:
    base = tmp_path_factory.getbasetemp().resolve()
    assert base == (REPO / ".scratch" / "pytest").resolve()
