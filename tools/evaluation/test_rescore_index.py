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


# --- ranked by the model the gate keeps, beside what people said -------------------------


def test_with_the_live_model_kept_the_table_is_ranked_by_it(tmp_path: Path) -> None:
    paths = world(tmp_path)
    live, new = models(paths)
    table = rescore_index.rescored(saved_rows(paths), live, new, by="live")
    assert [r["old_rating"] for r in table] == sorted((r["old_rating"] for r in table), reverse=True)
    assert all(row["ranked_by"] == "live" for row in table)


def test_the_reasons_are_the_ranking_models_own(tmp_path: Path) -> None:
    from types import SimpleNamespace
    paths = world(tmp_path)
    live, new = models(paths)
    rows = saved_rows(paths)
    table = {row["site"]: row for row in rescore_index.rescored(rows, live, new, by="live")}
    first = rows[0]
    page = SimpleNamespace(**{n: first[n] for n in ALL_FEATURES})
    assert table[first["site"]]["reasons"] == list(live.judge(page).reasons)
    visual_words = {w for n in page_model.VISUAL_FEATURES for w in page_model.WORDS[n]}
    for row in table.values():
        for reason in row["pushed_up_by"] + row["held_down_by"]:
            assert not any(reason.startswith(word) for word in visual_words), reason


def test_what_held_a_page_down_is_said_beside_what_pushed_it_up(tmp_path: Path) -> None:
    paths = world(tmp_path)
    live, new = models(paths)
    for row in rescore_index.rescored(saved_rows(paths), live, new):
        assert not set(row["pushed_up_by"]) & set(row["held_down_by"])
    assert any(row["held_down_by"] for row in rescore_index.rescored(saved_rows(paths), live, new))


def test_people_are_put_beside_the_sites_they_rated(tmp_path: Path) -> None:
    paths = world(tmp_path)
    live, new = models(paths)
    said = rescore_index.people(paths.ratings, paths.set3)
    assert len(said) == 15 and {n for _, n in said.values()} == {8}
    table = rescore_index.rescored(saved_rows(paths), live, new, by="live", people=said)
    assert all(row["people"] == said[row["url"]][0] for row in table)
    text = rescore_index.rescored_report(table, live, new, preview=False, by="live")
    assert "As people rated them" in text and "the live model" in text


def test_an_answer_to_another_picture_of_a_site_is_not_counted(tmp_path: Path) -> None:
    paths = world(tmp_path)
    lines = paths.ratings.read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines]
    site = next(r["url"] for r in rows if "site-" in r["url"])
    for row in rows:
        if row["url"] == site and row["rater"] % 2:
            row["image_sha256"] = "another picture"
    paths.ratings.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    assert rescore_index.people(paths.ratings, paths.set3)[site][1] == 4


def test_with_no_ratings_nobody_is_said_to_have_rated_anything(tmp_path: Path) -> None:
    paths = world(tmp_path)
    assert rescore_index.people(tmp_path / "none.jsonl", paths.set3) == {}


def test_a_reason_is_counted_once_whatever_number_it_carries() -> None:
    rows = [{"pushed_up_by": [f"many links ({n})"], "held_down_by": []} for n in (90, 217, 326)]
    assert rescore_index.common(rows, "pushed_up_by") == [("many links", 3)]


def test_against_people_the_new_models_row_says_it_was_fitted_on_them(tmp_path: Path) -> None:
    paths = world(tmp_path)
    live, new = models(paths)
    said = rescore_index.people(paths.ratings, paths.set3)
    table = rescore_index.rescored(saved_rows(paths), live, new, by="live", people=said)
    real = rescore_index.rescored_report(table, live, new, preview=False, by="live")
    assert "not held out" in real.split("As people rated them")[1]
    preview = rescore_index.rescored_report(table, live, new, preview=True, by="live")
    assert "not held out" not in preview.split("As people rated them")[1]
