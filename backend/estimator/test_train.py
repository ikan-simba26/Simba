"""The training pipeline, proven on synthetic ratings before real ones exist.

Nothing here is a result. Every rating is generated with `"synthetic": true`,
from a rule the test chose, so what these tests check is that the pipeline
finds a rule that is there, finds nothing when there is nothing, measures
agreement the way it says it does, refuses what it should refuse — and never
lets a synthetic run into the project's own model file or EVALUATION.md.

Files go in `tmp_path`, which is inside the repository (`.scratch/pytest`,
set in the root `conftest.py`), as CLAUDE.md requires.
"""

import json
import random
from pathlib import Path

import joblib
import numpy as np
import pytest

from backend.estimator import train as pipeline
from backend.estimator.train import (
    EVALUATION,
    FEATURES,
    MIN_RATERS,
    MODEL,
    Rating,
    RefusedToTrain,
    agreement,
    krippendorff_alpha_interval,
    page_means,
    read_corpus,
    read_ratings,
    report,
    run,
    save_model,
    train,
    write_evaluation,
)

@pytest.fixture
def here(tmp_path: Path) -> Path:
    return tmp_path


# --- synthetic data ---------------------------------------------------------


def synthetic_corpus(pages: int = 50, seed: int = 1) -> dict:
    """Headless corpus rows with plausible, independent feature values."""
    rng = np.random.default_rng(seed)
    rows = {}
    for i in range(pages):
        rows[(f"https://synthetic.example/{i}", "as it loads")] = {
            "url": f"https://synthetic.example/{i}", "state": "as it loads",
            "interactive": int(rng.integers(0, 200)), "links": int(rng.integers(0, 500)),
            "inferred": int(rng.integers(0, 50)), "text_density": float(rng.uniform(0, 4)),
            "max_depth": int(rng.integers(4, 40)), "overlays": int(rng.integers(0, 3)),
            "form_fields": int(rng.integers(0, 20)),
            "dead_link_ratio": float(rng.uniform(0, 1)),
            "reading_grade": float(rng.uniform(3, 14)),
        }
    return rows


def truth(row: dict) -> float:
    """The rule synthetic raters follow: dense text and many links overwhelm.
    On a 1-7 scale; nothing else matters."""
    return 1.0 + 1.2 * row["text_density"] + 0.006 * row["links"]


def synthetic_ratings(corpus: dict, raters: int = 12, noise: float = 0.6,
                      signal: bool = True, repeats: int = 2, seed: int = 2) -> list[dict]:
    """Rows in `tools/rating` shape, every one marked synthetic.

    Each rater has a bias of their own and answers with noise, rounded and
    clipped to 1-7; each repeats two pages, as a real session does. With
    `signal=False` the answers ignore the page entirely."""
    rng = random.Random(seed)
    rows = []
    keys = list(corpus)
    for rater in range(1, raters + 1):
        bias = rng.gauss(0, 0.4)

        def answer(key) -> int:
            base = truth(corpus[key]) if signal else 4.0
            return int(min(7, max(1, round(base + bias + rng.gauss(0, noise)))))

        for key in keys:
            rows.append({"rater": rater, "url": key[0], "state": key[1], "page": key[0],
                         "repeat": False, "rating": answer(key), "synthetic": True})
        for key in rng.sample(keys, repeats):
            rows.append({"rater": rater, "url": key[0], "state": key[1], "page": key[0],
                         "repeat": True, "rating": answer(key), "synthetic": True})
    return rows


def as_ratings(rows: list[dict]) -> list[Rating]:
    return [Rating(rater=r["rater"], url=r["url"], state=r["state"], page=r["page"],
                   repeat=r["repeat"], rating=r["rating"],
                   synthetic=r.get("synthetic", False)) for r in rows]


def write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def write_corpus(path: Path, rows: dict) -> Path:
    path.write_text(json.dumps({
        "conditions": {"taken_at": "synthetic"},
        "results": {"headless": list(rows.values()), "host": []},
    }), encoding="utf-8")
    return path


# --- it finds a rule that is there, and nothing where there is none ---------


def test_a_rule_the_raters_follow_is_found() -> None:
    corpus = synthetic_corpus()

    trained = train(as_ratings(synthetic_ratings(corpus)), corpus)

    r2, _ = trained.r2
    assert r2 > 0.6, trained.fold_r2
    assert r2 > trained.baseline[0] + 0.5
    # The two features the rule uses are the two the importance ranks first.
    ranked = sorted(FEATURES, key=lambda f: trained.importance[f][0], reverse=True)
    assert set(ranked[:2]) == {"text_density", "links"}, trained.importance
    # And both push the same way the rule does.
    assert trained.coefficients["text_density"] > 0
    assert trained.coefficients["links"] > 0
    assert trained.synthetic is True


def test_raters_who_ignore_the_page_teach_it_nothing() -> None:
    """The control: no rule, no fit. A pipeline that found something here
    would be finding its own noise."""
    corpus = synthetic_corpus()

    trained = train(as_ratings(synthetic_ratings(corpus, signal=False)), corpus)

    assert trained.r2[0] < 0.1, trained.fold_r2
    assert max(m for m, _ in trained.importance.values()) < 0.1


def test_noisier_raters_give_a_weaker_model() -> None:
    corpus = synthetic_corpus()
    calm = train(as_ratings(synthetic_ratings(corpus, noise=0.3)), corpus)
    noisy = train(as_ratings(synthetic_ratings(corpus, noise=2.5)), corpus)

    assert calm.r2[0] > noisy.r2[0]


def test_importance_is_measured_on_pages_the_model_did_not_see() -> None:
    """Every fold contributes `PERMUTATION_REPEATS` shuffles of its held-out
    pages — so the numbers are about prediction, not memory."""
    corpus = synthetic_corpus()
    calls: list[int] = []
    original = pipeline.permutation_importance

    def counting(model, x, y, **kwargs):
        calls.append(len(y))
        return original(model, x, y, **kwargs)

    pipeline.permutation_importance = counting
    try:
        train(as_ratings(synthetic_ratings(corpus)), corpus)
    finally:
        pipeline.permutation_importance = original

    assert len(calls) == pipeline.FOLDS
    assert sum(calls) == len(corpus)  # each page held out exactly once


# --- agreement ------------------------------------------------------------------


def test_raters_who_all_agree_have_an_alpha_of_one() -> None:
    assert krippendorff_alpha_interval([[3, 3, 3], [5, 5, 5], [1, 1]]) == pytest.approx(1.0)


def test_alpha_matches_krippendorffs_own_published_example() -> None:
    """The reliability data in Krippendorff, "Computing Krippendorff's
    Alpha-Reliability" (2011): four coders, twelve units, some missing. The
    paper gives interval alpha = 0.849. Checked against the published number,
    not against this module's own arithmetic."""
    units = [
        [1, 1, 1], [2, 2, 3, 2], [3, 3, 3, 3], [3, 3, 3, 3], [2, 2, 2, 2],
        [1, 2, 3, 4], [4, 4, 4, 4], [1, 1, 2, 1], [2, 2, 2, 2], [5, 5, 5],
        [1, 1], [3],
    ]
    assert krippendorff_alpha_interval(units) == pytest.approx(0.849, abs=0.0005)


def test_alpha_needs_two_values_on_a_page_to_say_anything() -> None:
    assert krippendorff_alpha_interval([[4], [2]]) is None
    assert krippendorff_alpha_interval([[4, 4], [4, 4]]) is None  # no variation at all


def test_raters_who_ignore_the_page_do_not_agree() -> None:
    corpus = synthetic_corpus()
    following = agreement(as_ratings(synthetic_ratings(corpus)))
    ignoring = agreement(as_ratings(synthetic_ratings(corpus, signal=False)))

    assert following.alpha > 0.7
    assert ignoring.alpha < 0.2


def test_a_rater_who_reads_the_question_backwards_is_picked_out() -> None:
    corpus = synthetic_corpus()
    rows = synthetic_ratings(corpus)
    for row in rows:
        if row["rater"] == 7:
            row["rating"] = 8 - row["rating"]

    found = agreement(as_ratings(rows))

    assert found.rater_vs_rest[7] < 0
    assert all(rho > 0.5 for rater, rho in found.rater_vs_rest.items() if rater != 7)


def test_the_repeated_pages_say_how_consistent_one_person_is() -> None:
    """Every rater saw two pages twice. Their two answers are paired, and the
    pairs measure test-retest within a session."""
    corpus = synthetic_corpus()
    steady = agreement(as_ratings(synthetic_ratings(corpus, noise=0.0)))
    shaky = agreement(as_ratings(synthetic_ratings(corpus, noise=2.0)))

    assert len(steady.repeat_pairs) == 12 * 2
    assert steady.repeat_mean_difference == 0
    assert steady.repeat_identical == 1.0
    assert shaky.repeat_mean_difference > steady.repeat_mean_difference
    assert shaky.repeat_within_one < 1.0


def test_agreement_is_over_first_showings_only() -> None:
    """A repeat is the same person asked again; counting it as a second rater
    would inflate agreement with themselves."""
    ratings = as_ratings([
        {"rater": 1, "url": "u", "state": "s", "page": "p", "repeat": False, "rating": 2},
        {"rater": 1, "url": "u", "state": "s", "page": "p", "repeat": True, "rating": 2},
    ])

    assert agreement(ratings).alpha is None  # one rater: nothing to agree with


# --- averaging ------------------------------------------------------------------


def test_a_rater_counts_once_per_page_however_often_they_saw_it() -> None:
    ratings = as_ratings([
        {"rater": 1, "url": "u", "state": "s", "page": "p", "repeat": False, "rating": 1},
        {"rater": 1, "url": "u", "state": "s", "page": "p", "repeat": True, "rating": 3},
        {"rater": 2, "url": "u", "state": "s", "page": "p", "repeat": False, "rating": 6},
    ])

    mean, raters = page_means(ratings)[("u", "s")]

    # Rater 1's two answers average to 2; then 2 and 6 average to 4, not
    # (1 + 3 + 6) / 3.
    assert mean == 4.0
    assert raters == 2


# --- what it refuses ----------------------------------------------------------


def test_it_refuses_fewer_than_ten_raters_and_says_why() -> None:
    corpus = synthetic_corpus()
    nine = as_ratings(synthetic_ratings(corpus, raters=MIN_RATERS - 1))

    with pytest.raises(RefusedToTrain) as refused:
        train(nine, corpus)

    message = str(refused.value)
    assert "only 9 raters" in message and "at least 10" in message
    assert "average" in message


def test_ten_raters_is_enough() -> None:
    corpus = synthetic_corpus()
    assert train(as_ratings(synthetic_ratings(corpus, raters=MIN_RATERS)), corpus)


def test_it_refuses_to_mix_synthetic_and_real_ratings() -> None:
    corpus = synthetic_corpus()
    rows = synthetic_ratings(corpus)
    rows[0] = {**rows[0], "synthetic": False}

    with pytest.raises(RefusedToTrain, match="mix synthetic rows with real ones"):
        train(as_ratings(rows), corpus)


def test_it_refuses_too_few_pages_to_fold() -> None:
    corpus = dict(list(synthetic_corpus().items())[:6])

    with pytest.raises(RefusedToTrain, match="cross-validation needs at least 10"):
        train(as_ratings(synthetic_ratings(corpus)), corpus)


def test_a_rated_page_the_corpus_lacks_is_reported_not_dropped_silently() -> None:
    corpus = synthetic_corpus()
    rows = synthetic_ratings(corpus)
    for rater in range(1, 13):
        rows.append({"rater": rater, "url": "https://gone.example/", "state": "as it loads",
                     "page": "gone", "repeat": False, "rating": 4, "synthetic": True})

    trained = train(as_ratings(rows), corpus)

    assert trained.unmatched == [("https://gone.example/", "as it loads")]
    assert "gone.example" in report(trained)


def test_a_malformed_row_stops_the_read(here: Path) -> None:
    path = here / "ratings.jsonl"
    path.write_text('{"rater": 1, "url": "u", "state": "s", "rating": 9}\n', encoding="utf-8")

    with pytest.raises(RefusedToTrain, match="outside 1-7"):
        read_ratings(path)


def test_no_ratings_file_says_where_ratings_come_from(here: Path) -> None:
    with pytest.raises(RefusedToTrain, match="tools.rating.serve"):
        read_ratings(here / "nothing.jsonl")


# --- synthetic is never reported as real --------------------------------------


def test_a_synthetic_model_is_never_saved_where_the_real_one_lives() -> None:
    corpus = synthetic_corpus()
    trained = train(as_ratings(synthetic_ratings(corpus)), corpus)
    existed = MODEL.exists()

    with pytest.raises(RefusedToTrain, match="synthetic"):
        save_model(trained, MODEL)

    assert MODEL.exists() == existed


def test_a_synthetic_result_is_never_written_into_evaluation_md() -> None:
    corpus = synthetic_corpus()
    trained = train(as_ratings(synthetic_ratings(corpus)), corpus)
    before = EVALUATION.read_text(encoding="utf-8")

    with pytest.raises(RefusedToTrain, match="synthetic"):
        write_evaluation(trained, EVALUATION)

    assert EVALUATION.read_text(encoding="utf-8") == before


def test_a_synthetic_report_says_so_before_anything_else() -> None:
    corpus = synthetic_corpus()
    section = report(train(as_ratings(synthetic_ratings(corpus)), corpus))

    first_paragraph = section.split("\n\n")[1]
    assert first_paragraph.startswith("**SYNTHETIC — a test of the pipeline, not a result.**")


# --- the whole run, end to end, somewhere harmless ---------------------------


def test_the_whole_pipeline_runs_and_writes_where_it_is_told(here: Path) -> None:
    corpus = synthetic_corpus()
    ratings = write_jsonl(here / "ratings.jsonl", synthetic_ratings(corpus))
    corpus_file = write_corpus(here / "corpus.json", corpus)
    model = here / "estimator.joblib"
    evaluation = here / "EVALUATION.md"
    evaluation.write_text("# scratch\n", encoding="utf-8")

    trained = run(ratings, corpus_file, model, evaluation)

    saved = joblib.load(model)
    assert saved["synthetic"] is True
    assert saved["features"] == FEATURES
    assert saved["raters"] == 12
    # The saved model predicts, from features in the declared order.
    row = next(iter(corpus.values()))
    prediction = saved["model"].predict(np.array([[row[f] for f in FEATURES]]))
    assert 0 < prediction[0] < 10
    text = evaluation.read_text(encoding="utf-8")
    assert "the estimator, trained on 12 raters' ratings" in text
    assert "**SYNTHETIC" in text
    assert trained.sources["rows"] == 12 * 52


def test_it_reads_the_real_corpus_file() -> None:
    """The real `data/corpus.json`, so a change to its shape breaks a test
    here rather than the first real training run."""
    rows, conditions = read_corpus(pipeline.CORPUS)

    assert len(rows) >= 40
    assert all(all(f in row for f in FEATURES) for row in rows.values())
    assert conditions.get("taken_at")
