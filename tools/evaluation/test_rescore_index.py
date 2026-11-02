"""The overwhelm index again, from what was saved: both models on one read of each
page, written beside the first index, with no visit to anything. The study is the
synthetic one `backend/estimator/test_train_visual.py` makes.
"""

import json
from pathlib import Path

import pytest

from backend.estimator import page_model, train_visual
from backend.estimator.page_model import FEATURES
from backend.estimator.test_train_visual import compared, quick, world  # noqa: F401
from backend.estimator.train_visual import ALL_FEATURES, Paths
from tools.evaluation import overwhelm_index, rescore_index


def models(paths: Paths) -> tuple[page_model.PageModel, page_model.PageModel]:
    found = compared(paths)
    train_visual.save_candidate(found, paths.candidate)
    data = json.loads(paths.candidate.read_text(encoding="utf-8"))
    data["synthetic"] = False
    paths.candidate.write_text(json.dumps(data), encoding="utf-8")
    live = page_model.load()
    new = page_model.load(paths.candidate, names=ALL_FEATURES)
    assert live is not None and new is not None
    return live, new


def saved_rows(paths: Paths) -> list[dict]:
    return json.loads(paths.visual.read_text(encoding="utf-8"))["sites"]["rows"]


def test_every_scored_site_is_ranked_by_both_models(tmp_path: Path) -> None:
    paths = world(tmp_path)
    live, new = models(paths)
    table = rescore_index.rescored(saved_rows(paths), live, new)
    assert len(table) == 15
    assert [row["rating"] for row in table] == sorted((r["rating"] for r in table), reverse=True)
    assert all({"old_rating", "rating", "band", "simba_level"} <= set(row) for row in table)


def test_a_skipped_site_stays_out_of_the_table(tmp_path: Path) -> None:
    paths = world(tmp_path)
    live, new = models(paths)
    assert "Skipped" not in {row["site"] for row in rescore_index.rescored(saved_rows(paths), live, new)}


def test_the_two_columns_are_of_the_same_read(tmp_path: Path) -> None:
    paths = world(tmp_path)
    live, new = models(paths)
    rows = saved_rows(paths)
    table = {row["site"]: row for row in rescore_index.rescored(rows, live, new)}
    from types import SimpleNamespace
    first = rows[0]
    expected = live.judge(SimpleNamespace(**{n: first[n] for n in FEATURES}))
    assert table[first["site"]]["old_rating"] == expected.rating


def test_a_page_is_never_given_more_detail_than_the_rules_allow(tmp_path: Path) -> None:
    paths = world(tmp_path)
    live, new = models(paths)
    table = rescore_index.rescored(saved_rows(paths), live, new)
    assert all(row["simba_level"] >= 2 for row in table)


def test_the_new_reasons_are_said_in_words(tmp_path: Path) -> None:
    paths = world(tmp_path)
    live, new = models(paths)
    words = {w for pair in page_model.WORDS.values() for w in pair}
    for row in rescore_index.rescored(saved_rows(paths), live, new):
        for reason in row["pushed_up_by"]:
            assert any(reason.startswith(word) for word in words), reason


def test_it_is_written_beside_the_first_index_and_not_over_it(tmp_path: Path) -> None:
    paths = world(tmp_path)
    models(paths)
    out = tmp_path / "again"
    table = rescore_index.write_rescored(paths.candidate, paths.visual, out, preview=True)
    assert len(table) == 15
    text = (out / "report.md").read_text(encoding="utf-8")
    assert "A preview" in text and "Nothing was visited" in text
    assert (out / "overwhelm_index.csv").exists()
    assert rescore_index.OUT.parent == overwhelm_index.OUT


def test_a_missing_model_is_said_rather_than_guessed_round(tmp_path: Path) -> None:
    paths = world(tmp_path)
    with pytest.raises(rescore_index.Unscored, match="candidate"):
        rescore_index.write_rescored(paths.candidate, paths.visual, tmp_path / "again")
