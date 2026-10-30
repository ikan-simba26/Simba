"""The comparison with the rules, and the one command that retrains.

The numbers these print are in EVALUATION.md; what is pinned here is the
arithmetic, that a page's rated mean never reaches a committed file, and that
retraining runs the three steps in order and stops at the first refusal.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

from backend.estimator import train
from backend.estimator.page_features import PageFeatures
from backend.estimator.page_model import PageModel
from tools.evaluation import estimator_compare as compare
from tools.evaluation.estimator_compare import Page
from tools.rating import from_form, retrain

MODEL = PageModel(
    version="trained test", means=(0.0,) * 9, spreads=(1.0,) * 9,
    coefficients=(0, 0, 0, 1.0, 0, 0, 0, 0, 0), intercept=1.0, calm=2.45, heavy=2.9)


def page(rated: float, rating: float = 2.0, level: int = 2, rules_level: int = 2,
         ratings: int = 10, name: str = "https://example.test/") -> Page:
    return Page(key=(name, "as it loads"), kind="public", ratings=ratings, rated=rated,
                held_out=rating, rating=rating, level=level, rules_level=rules_level,
                signs=[], reasons=("little text on screen",))


def test_heavy_calls_count_against_a_rating_of_3_5_or_more() -> None:
    called = np.array([True, True, False, False])
    rated = np.array([4.0, 2.0, 3.5, 1.0])
    found = compare.heavy_calls(called, rated)
    assert (found["hits"], found["false"], found["missed"]) == (1, 1, 1)
    assert found["precision"] == 0.5 and found["recall"] == 0.5 and found["accuracy"] == 0.5


def test_nobody_called_heavy_is_no_precision_rather_than_a_crash() -> None:
    found = compare.heavy_calls(np.array([False, False]), np.array([1.0, 2.0]))
    assert found["precision"] == 0.0 and found["recall"] == 0.0


def test_a_person_who_has_not_said_starts_at_2_or_3() -> None:
    assert [page(1, level=n).start_level for n in (1, 2, 3)] == [2, 2, 3]


def test_a_corpus_row_or_a_logged_page_becomes_features_whatever_else_it_holds() -> None:
    row = {name: 1 for name in PageFeatures.__dataclass_fields__}
    assert compare.features_of({**row, "url": "x", "run": "y", "link_share": 0.5}).links == 1


def test_logged_decisions_are_grouped_by_page_and_replayed(tmp_path: Path) -> None:
    page_row = {name: 1 for name in PageFeatures.__dataclass_fields__}
    rows = [{"kind": "decision", "at": "start", "level": 2, "inputs": {"page": page_row}},
            {"kind": "decision", "at": "start", "level": 3, "inputs": {"page": page_row}},
            {"kind": "decision", "at": "step", "level": 3, "inputs": {"page": page_row}},
            {"kind": "decision", "at": "start", "level": 2, "inputs": {"page": None}},
            {"kind": "telemetry"}]
    path = tmp_path / "steps.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    found = compare.replay_logged(MODEL, path)
    assert len(found) == 1
    assert found[0]["rows"] == 2 and found[0]["levels"] == {2: 1, 3: 1}
    assert found[0]["rating"] == 2.0 and found[0]["level"] == 1


def test_what_is_committed_about_a_page_holds_no_rating(tmp_path: Path) -> None:
    """DECISIONS.md, *The trained model is committed; the ratings are not*: the
    aggregate model only, not the per-page means."""
    path = tmp_path / "pages.json"
    compare.save_pages([page(4.37, rating=3.0, level=3)], MODEL, path)
    text = path.read_text(encoding="utf-8")
    assert "4.37" not in text and "rated" not in text
    saved = json.loads(text)
    assert saved["pages"][0]["score"] == 3.0
    assert saved["pages"][0]["sentence"] == "3.0 of 5, level 3: little text on screen."


def test_the_table_with_ratings_in_it_goes_to_scratch_only() -> None:
    assert compare.SCRATCH.relative_to(compare.REPO).parts[0] == ".scratch"
    assert ".scratch/" in (compare.REPO / ".gitignore").read_text(encoding="utf-8")


def test_the_charts_are_svg_and_name_every_page() -> None:
    pages = [page(4.0, 3.0, ratings=5, name="https://a.test/"),
             page(1.0, 2.0, name="https://b.test/")]
    svg = compare.scatter_chart(pages, (2.45, 2.9))
    assert svg.startswith("<svg") and "a.test" in svg and "b.test" in svg
    assert "Under 8 ratings" in svg


def test_phone_raters_can_be_put_back_for_the_check_only(tmp_path: Path) -> None:
    mapping = json.loads(from_form.MAPPING.read_text(encoding="utf-8"))
    questions = mapping["questions"]
    order = mapping["orders"]["1"]
    header = ["Timestamp", questions["consent"]["title"], questions["device"]["title"],
              questions["age"]["title"], questions["computing"]["title"],
              *[f"{questions['rating']['title']} [{name}]" for name in order]]
    yes = questions["consent"]["yes"]
    word = questions["rating"]["labels"][0]
    answers = [["t", yes, questions["device"]["choices"][device], "18-24", "Yes",
                *[word] * len(order)] for device in ("phone", "laptop")]
    path = tmp_path / "set1.csv"
    import csv
    with path.open("w", encoding="utf-8", newline="") as out:
        csv.writer(out).writerows([header, *answers])

    everyone, phones = compare.with_phones([path], mapping)
    assert phones == {from_form.FORMS["1"] + 1}
    assert {r.rater for r in everyone} == {5001, 5002}
    # The converter itself still drops them.
    assert len(from_form.convert([header, *answers], mapping, "1").raters) == 1


# --- the one command -------------------------------------------------------------


@pytest.fixture
def steps(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    done: list[str] = []
    monkeypatch.setattr(from_form, "run", lambda csvs: done.append(f"convert {csvs}") or None)
    monkeypatch.setattr(from_form, "summary", lambda converted: "converted")
    monkeypatch.setattr(train, "report", lambda trained: "report")

    def trained(min_ratings: int) -> str:
        done.append(f"train {min_ratings}")
        return "trained"

    monkeypatch.setattr(train, "run", trained)
    monkeypatch.setattr(compare, "run", lambda csvs: done.append(f"compare {csvs}") or "compared")
    return done


def run_with(monkeypatch: pytest.MonkeyPatch, *arguments: str) -> None:
    monkeypatch.setattr(sys, "argv", ["retrain", *arguments])
    retrain.main()


def test_one_command_converts_trains_and_compares_in_that_order(
        steps: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    run_with(monkeypatch, "a.csv", "2=b.csv")
    assert steps == [f"convert {[(None, Path('a.csv')), ('2', Path('b.csv'))]}",
                     f"train {train.MIN_RATINGS}",
                     f"compare {[Path('a.csv'), Path('b.csv')]}"]


def test_with_no_csv_it_trains_on_the_ratings_already_there(
        steps: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    run_with(monkeypatch)
    assert steps == [f"train {train.MIN_RATINGS}", "compare []"]


def test_the_floor_is_only_lowered_when_asked(
        steps: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    run_with(monkeypatch, "--min-ratings", "5")
    assert steps[0] == "train 5"


def test_a_refusal_stops_before_the_comparison(
        steps: list[str], monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    def refused(min_ratings: int) -> None:
        raise train.RefusedToTrain("22 of 50 pages have fewer than 8 ratings")

    monkeypatch.setattr(train, "run", refused)
    with pytest.raises(SystemExit) as stopped:
        run_with(monkeypatch)
    assert stopped.value.code == 2
    assert not any(step.startswith("compare") for step in steps)
    assert "22 of 50 pages" in capsys.readouterr().out
