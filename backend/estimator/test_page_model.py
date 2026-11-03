"""The trained estimator as the running app reads it.

Two kinds of test. Synthetic models pin the arithmetic, the words and every way
a model file can be unusable, each of which must leave the rules judging the
page. And the committed model itself: the JSON the app reads has to give what
the scikit-learn pipeline gives on every corpus page, or the plain numbers are
not the model that was evaluated.
"""

import json
from dataclasses import replace
from pathlib import Path

import joblib
import numpy as np
import pytest

from backend.estimator import page_model, train
from backend.estimator.page_features import PageFeatures
from backend.estimator.page_model import FEATURES, Judgement, PageModel, load
from backend.estimator.test_rules import HEAVY, LIGHT
from tools.evaluation.estimator_compare import features_of

#: The rating is 1 plus the text density: one feature, nothing else moves it.
SIMPLE = PageModel(
    version="trained test", means=(0.0,) * 9, spreads=(1.0,) * 9,
    coefficients=(0, 0, 0, 1.0, 0, 0, 0, 0, 0), intercept=1.0, calm=2.45, heavy=2.9)


def page(**changes) -> PageFeatures:
    return replace(LIGHT, **changes)


def file_with(path: Path, **changes) -> Path:
    data = {
        "version": "trained test", "synthetic": False, "scale": [1, 5],
        "features": list(FEATURES), "means": [0.0] * 9, "spreads": [1.0] * 9,
        "coefficients": [0.0, 0, 0, 1.0, 0, 0, 0, 0, 0], "intercept": 1.0,
        "cuts": {"calm": 2.45, "heavy": 2.9},
    }
    data.update(changes)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# --- the sum ---------------------------------------------------------------------


def test_the_rating_is_the_intercept_plus_each_scaled_feature() -> None:
    model = replace(SIMPLE, means=(0, 0, 0, 1.0, 0, 0, 0, 0, 0), spreads=(1, 1, 1, 2.0, 1, 1, 1, 1, 1))
    assert model.rating(page(text_density=3.0)) == pytest.approx(1.0 + (3.0 - 1.0) / 2.0)


def test_the_rating_never_leaves_the_scale() -> None:
    assert SIMPLE.rating(page(text_density=400.0)) == 5.0
    assert replace(SIMPLE, intercept=-9.0).rating(page(text_density=0.0)) == 1.0


def test_the_score_is_the_rating_on_the_contracts_zero_to_one() -> None:
    assert SIMPLE.judge(page(text_density=0.0)).score == 0.0
    assert SIMPLE.judge(page(text_density=2.0)).score == 0.5
    assert SIMPLE.judge(page(text_density=40.0)).score == 1.0


@pytest.mark.parametrize("density, level", [(1.0, 1), (1.44, 1), (1.45, 2), (1.89, 2), (1.9, 3)])
def test_the_level_follows_the_cut_points_and_a_rating_on_a_cut_goes_up(
        density: float, level: int) -> None:
    assert SIMPLE.judge(page(text_density=density)).level == level


# --- the reasons -----------------------------------------------------------------


def test_a_heavy_page_is_explained_by_what_pushed_it_up() -> None:
    model = replace(SIMPLE, coefficients=(0, 0.5, 0, 1.0, 0, 0, 0, 0, 0),
                    means=(0, 100, 0, 1, 0, 0, 0, 0, 0), spreads=(1, 100, 1, 1, 1, 1, 1, 1, 1))
    judged = model.judge(page(text_density=3.0, links=300))
    assert judged.reasons == ("a lot of text on screen", "many links (300)")


def test_a_calm_page_is_explained_by_what_held_it_down() -> None:
    model = replace(SIMPLE, coefficients=(0, 0.5, 0, 1.0, 0, 0, 0, 0, 0),
                    means=(0, 100, 0, 1, 0, 0, 0, 0, 0), spreads=(1, 100, 1, 1, 1, 1, 1, 1, 1),
                    intercept=3.0)
    judged = model.judge(page(text_density=0.5, links=2))
    assert judged.reasons == ("little text on screen", "few links (2)")


def test_a_feature_pulling_the_other_way_is_not_a_reason() -> None:
    model = replace(SIMPLE, coefficients=(0, 0.5, 0, 1.0, 0, 0, 0, 0, 0),
                    means=(0, 100, 0, 1, 0, 0, 0, 0, 0), spreads=(1, 100, 1, 1, 1, 1, 1, 1, 1))
    judged = model.judge(page(text_density=4.0, links=20))
    assert judged.reasons == ("a lot of text on screen",)


def test_a_negative_coefficient_still_describes_the_page_as_it_is() -> None:
    """Shallow pages scored heavier on the real ratings: the sentence says the
    page is shallow, not that a deep page is light."""
    model = replace(SIMPLE, coefficients=(0, 0, 0, 0, -0.5, 0, 0, 0, 0),
                    means=(0, 0, 0, 0, 15, 0, 0, 0, 0))
    assert model.judge(page(max_depth=5)).reasons == ("a shallow, plain layout",)


def test_a_page_near_the_average_has_nothing_to_say_and_says_so() -> None:
    model = replace(SIMPLE, coefficients=(0.0,) * 9, intercept=2.5)
    judged = model.judge(LIGHT)
    assert judged.reasons == ()
    assert judged.says() == "2.5 of 5: much like the average page"


def test_never_more_than_three_reasons() -> None:
    model = replace(SIMPLE, coefficients=(1.0,) * 9)
    assert len(model.judge(HEAVY).reasons) == 3


def test_every_feature_has_words_for_both_directions() -> None:
    assert set(page_model.WORDS) == set(FEATURES) | set(page_model.VISUAL_FEATURES)
    assert all(high != low for high, low in page_model.WORDS.values())


def test_a_judgement_says_its_rating_and_its_reasons_and_goes_in_a_row() -> None:
    judged = Judgement(rating=4.76, score=0.94, level=3, reasons=("a lot of text on screen",))
    assert judged.says() == "4.8 of 5: a lot of text on screen"
    assert judged.as_row() == {"rating": 4.76, "score": 0.94, "level": 3,
                               "reasons": ["a lot of text on screen"]}


# --- a model that cannot be used ---------------------------------------------------


def test_a_good_file_loads(tmp_path: Path) -> None:
    model = load(file_with(tmp_path / "estimator.json"))
    assert model is not None and model.heavy == 2.9 and model.version == "trained test"


def test_no_file_means_no_model(tmp_path: Path) -> None:
    assert load(tmp_path / "nothing.json") is None


@pytest.mark.parametrize("changes", [
    {"synthetic": True},
    {"features": list(reversed(FEATURES))},
    {"features": ["links"]},
    {"means": [0.0] * 8},
    {"coefficients": [0.0]},
    {"spreads": [1.0] * 8},
    {"spreads": [0.0] * 9},
    {"cuts": {"calm": 3.0, "heavy": 2.0}},
    {"cuts": {"calm": 2.0}},
    {"cuts": None},
    {"intercept": "high"},
    {"scale": []},
], ids=str)
def test_a_file_that_cannot_be_trusted_means_no_model(tmp_path: Path, changes: dict) -> None:
    assert load(file_with(tmp_path / "estimator.json", **changes)) is None


def test_a_file_that_is_not_json_means_no_model(tmp_path: Path) -> None:
    path = tmp_path / "estimator.json"
    path.write_text("{ not json", encoding="utf-8")
    assert load(path) is None


def test_a_file_saying_nothing_of_how_it_was_trained_is_not_used(tmp_path: Path) -> None:
    path = file_with(tmp_path / "estimator.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["synthetic"]
    path.write_text(json.dumps(data), encoding="utf-8")
    assert load(path) is None


def test_the_switch_turns_the_model_off(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = file_with(tmp_path / "estimator.json")
    assert page_model.active(path) is not None
    for off in ("0", "false", "no"):
        monkeypatch.setenv(page_model.ENV_SWITCH, off)
        assert page_model.active(path) is None


def test_features_are_the_ones_training_fits() -> None:
    assert FEATURES == train.FEATURES


# --- the committed model -----------------------------------------------------------


@pytest.mark.skipif(not train.COEFFICIENTS.exists(), reason="no trained model in this checkout")
def test_the_committed_json_gives_what_the_committed_pipeline_gives() -> None:
    """The app reads one file and the evaluation was of the other."""
    model = load(train.COEFFICIENTS)
    assert model is not None
    pipeline = joblib.load(train.MODEL)["model"]
    corpus, _ = train.read_corpus(train.CORPUS)
    assert len(corpus) == 50
    for row in corpus.values():
        features = features_of(row)
        x = np.array([[float(row[f]) for f in FEATURES]])
        assert model.rating(features) == pytest.approx(
            float(np.clip(pipeline.predict(x)[0], 1, 5)), abs=1e-9)


@pytest.mark.skipif(not train.COEFFICIENTS.exists(), reason="no trained model in this checkout")
def test_the_committed_model_says_how_it_was_trained() -> None:
    saved = json.loads(train.COEFFICIENTS.read_text(encoding="utf-8"))
    assert saved["synthetic"] is False
    assert saved["raters"] >= 15 and saved["pages"] == 50
    # Under the floor only if it says so, with the count.
    assert (saved["min_ratings"] < train.MIN_RATINGS) == (saved["pages_below_floor"] > 0)
