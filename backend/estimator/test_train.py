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
    MIN_RATINGS,
    MODEL,
    Rating,
    RefusedToTrain,
    agreement,
    krippendorff_alpha_interval,
    page_means,
    read_corpus,
    read_design,
    read_ratings,
    report,
    run,
    save_model,
    shortfall,
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
            "run": "run-1",
        }
    return rows


def truth(row: dict) -> float:
    """The rule synthetic raters follow: dense text and many links overwhelm.
    On the 1-5 scale; nothing else matters."""
    return 1.0 + 0.7 * row["text_density"] + 0.004 * row["links"]


def two_sets(corpus: dict, anchors: int = 3) -> dict:
    """The forms' design on the synthetic corpus: every other page in each
    set, and the first `anchors` of each set shown in the other too."""
    keys = list(corpus)
    own = {1: keys[0::2], 2: keys[1::2]}
    design = {k: {s} for s, pages in own.items() for k in pages}
    for s in (1, 2):
        for k in own[s][:anchors]:
            design[k] = {1, 2}
    return design


def synthetic_ratings(corpus: dict, raters: int = 12, noise: float = 0.4,
                      signal: bool = True, repeats: int = 2, seed: int = 2,
                      design: dict | None = None, first_rater: int = 1,
                      shift: dict[int, float] | None = None) -> list[dict]:
    """Rows in `tools/rating` shape, every one marked synthetic.

    Each rater has a bias of their own and answers with noise, rounded and
    clipped to 1-5 (noise 0.4 and bias 0.3: the 0.6 and 0.4 of the 1-7 scale,
    scaled by 4/6); each repeats two pages, as a real session does. With
    `signal=False` the answers ignore the page entirely. With `design`, a
    rater rates only the pages of one set — odd raters Set 1, even Set 2,
    as in person — and `shift` adds to every answer of a set's raters."""
    rng = random.Random(seed)
    rows = []
    for rater in range(first_rater, first_rater + raters):
        bias = rng.gauss(0, 0.3)
        chosen = (1 if rater % 2 else 2) if design else None
        keys = [k for k in corpus if design is None or chosen in design[k]]
        lean = (shift or {}).get(chosen, 0.0)

        def answer(key) -> int:
            base = truth(corpus[key]) if signal else 3.0
            return int(min(5, max(1, round(base + bias + lean + rng.gauss(0, noise)))))

        for key in keys:
            rows.append({"rater": rater, "url": key[0], "state": key[1], "page": key[0],
                         "repeat": False, "rating": answer(key), "synthetic": True,
                         "set": chosen})
        for key in rng.sample(keys, repeats):
            rows.append({"rater": rater, "url": key[0], "state": key[1], "page": key[0],
                         "repeat": True, "rating": answer(key), "synthetic": True,
                         "set": chosen})
    return rows


def as_ratings(rows: list[dict]) -> list[Rating]:
    return [Rating(rater=r["rater"], url=r["url"], state=r["state"], page=r["page"],
                   repeat=r["repeat"], rating=r["rating"],
                   synthetic=r.get("synthetic", False), set=r.get("set")) for r in rows]


def write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def write_pictures(path: Path, rows: dict, run: str = "run-1") -> Path:
    """A picture manifest for the synthetic corpus, every picture from `run`."""
    path.write_text(json.dumps({"run": {"id": run}, "pages": [
        {"url": k[0], "state": k[1], "run": run, "sha256": f"sha-{i}"}
        for i, k in enumerate(rows)]}), encoding="utf-8")
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

    # 0.7 on the 1-7 scale. Rounding to five points adds error of its own
    # (2026-10-23: 0.70 at the same noise relative to the scale), so 0.6.
    assert following.alpha > 0.6
    assert ignoring.alpha < 0.2


def test_a_rater_who_reads_the_question_backwards_is_picked_out() -> None:
    corpus = synthetic_corpus()
    rows = synthetic_ratings(corpus)
    for row in rows:
        if row["rater"] == 7:
            row["rating"] = 6 - row["rating"]

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


# --- each rater rates only some pages -------------------------------------------


def test_raters_of_two_sets_agree_as_well_as_raters_of_every_page() -> None:
    """The same raters' rule, once with everyone rating all 50 and once with
    each rating one set of 28: alpha copes with the missing ratings, and
    lands near the full table's."""
    corpus = synthetic_corpus()
    full = agreement(as_ratings(synthetic_ratings(corpus, raters=16)))
    halves = agreement(as_ratings(synthetic_ratings(corpus, raters=16,
                                                    design=two_sets(corpus))))

    assert halves.pages == 50 and halves.raters_by_set == {1: 8, 2: 8}
    assert halves.alpha == pytest.approx(full.alpha, abs=0.1)
    assert all(v > 0.6 for v in halves.alpha_by_set.values())
    # Every rater is compared with the others on the pages they rated.
    assert all(rho is not None and rho > 0.5 for rho in halves.rater_vs_rest.values())


def test_sixteen_raters_in_two_sets_is_enough_to_train() -> None:
    corpus = synthetic_corpus()
    design = two_sets(corpus)
    trained = train(as_ratings(synthetic_ratings(corpus, raters=16, design=design)), corpus,
                    design=design)

    assert trained.r2[0] > 0.5, trained.fold_r2
    assert min(trained.coverage.counts.values()) == MIN_RATINGS
    assert max(trained.coverage.counts.values()) == 16  # the anchors
    section = report(trained)
    assert "Set 1: 8, Set 2: 8" in section and "8 / 8 / 16" in section


def test_the_anchors_say_the_two_groups_rate_alike() -> None:
    corpus = synthetic_corpus()
    design = two_sets(corpus)
    found = agreement(as_ratings(synthetic_ratings(corpus, raters=16, design=design)))

    assert found.groups is not None and len(found.groups.anchors) == 6
    assert abs(found.groups.difference) < 0.5
    assert found.groups.alike is True


def test_the_anchors_catch_a_group_that_rates_everything_higher() -> None:
    corpus = synthetic_corpus()
    design = two_sets(corpus)
    rows = synthetic_ratings(corpus, raters=16, design=design, shift={2: 1.2})

    found = agreement(as_ratings(rows))

    assert found.groups.difference > 0.8
    assert found.groups.p_value is not None and found.groups.p_value < 0.05
    assert found.groups.alike is False
    section = report(train(as_ratings(rows), corpus, design=design))
    assert "**not alike**" in section and "depends on which set" in section


def test_without_sets_there_is_no_group_check() -> None:
    corpus = synthetic_corpus()
    assert agreement(as_ratings(synthetic_ratings(corpus))).groups is None


# --- what it refuses ----------------------------------------------------------


def test_it_refuses_pages_with_fewer_than_eight_ratings_and_says_how_many_more() -> None:
    corpus = synthetic_corpus()
    seven = as_ratings(synthetic_ratings(corpus, raters=MIN_RATINGS - 1))

    with pytest.raises(RefusedToTrain) as refused:
        train(seven, corpus)

    message = str(refused.value)
    assert "50 of 50 pages have fewer than 8 ratings" in message
    assert "50 more ratings are needed in all" in message
    assert "average" in message


def test_with_the_sets_it_says_how_many_more_raters_of_each() -> None:
    """Ten raters, five per set: every page of a set's own has five ratings,
    the anchors ten. Three more of each set bring every page to eight."""
    corpus = synthetic_corpus()
    design = two_sets(corpus)
    rows = as_ratings(synthetic_ratings(corpus, raters=10, design=design))

    with pytest.raises(RefusedToTrain) as refused:
        train(rows, corpus, design=design)

    assert "44 of 50 pages have fewer than 8 ratings; 132 more ratings" in str(refused.value)
    assert "at least 3 more Set 1 raters and 3 more Set 2 raters" in str(refused.value)


def test_the_shortfall_counts_a_rater_once_per_page_and_pages_nobody_rated() -> None:
    ratings = as_ratings([
        {"rater": 1, "url": "a", "state": "s", "page": "a", "repeat": False, "rating": 2},
        {"rater": 1, "url": "a", "state": "s", "page": "a", "repeat": True, "rating": 3},
        {"rater": 2, "url": "a", "state": "s", "page": "a", "repeat": False, "rating": 4},
    ])
    found = shortfall(ratings, [("a", "s"), ("b", "s")], minimum=3)

    assert found.counts == {("a", "s"): 2, ("b", "s"): 0}
    assert found.short == {("a", "s"): 1, ("b", "s"): 3} and found.needed == 4


def test_eight_ratings_per_page_is_enough() -> None:
    corpus = synthetic_corpus()
    assert train(as_ratings(synthetic_ratings(corpus, raters=MIN_RATINGS)), corpus)


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

    with pytest.raises(RefusedToTrain, match="outside 1-5"):
        read_ratings(path)
    path.write_text('{"rater": 1, "url": "u", "state": "s", "rating": 6}\n', encoding="utf-8")
    with pytest.raises(RefusedToTrain, match="outside 1-5"):
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

    pictures = write_pictures(here / "pages.json", corpus)

    trained = run(ratings, corpus_file, model, evaluation, pictures_path=pictures,
                  design_path=None)

    saved = joblib.load(model)
    assert saved["synthetic"] is True
    assert saved["features"] == FEATURES
    assert saved["raters"] == 12 and saved["scale"] == (1, 5)
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


# --- a rating is paired with the features of the picture it was given for ---


def pictures_of(corpus: dict, run: str = "run-1") -> dict:
    return {k: {"url": k[0], "state": k[1], "run": run, "sha256": f"sha-{i}"}
            for i, k in enumerate(corpus)}


def test_ratings_of_pictures_and_features_from_one_run_are_used() -> None:
    corpus = synthetic_corpus()
    pictures = pictures_of(corpus)
    rows = synthetic_ratings(corpus)
    for row in rows:
        row["image_sha256"] = pictures[(row["url"], row["state"])]["sha256"]

    trained = train(as_rated(rows), corpus, pictures=pictures)

    assert trained.unpaired == []
    assert len(trained.pages) == len(corpus)


def test_features_from_another_run_than_the_picture_are_left_out() -> None:
    """The 2026-09-25 pictures and the 2026-09-30 features, as a test: a page
    whose features were read in a different run than its picture was taken in
    is not trained on."""
    corpus = synthetic_corpus()
    stale = next(iter(corpus))
    corpus[stale] = {**corpus[stale], "run": "run-0"}

    trained = train(as_rated(synthetic_ratings(corpus)), corpus, pictures=pictures_of(corpus))

    assert [k for k, _ in trained.unpaired] == [stale]
    assert "different capture runs" in trained.unpaired[0][1]
    assert stale not in trained.pages
    assert "did not pair" in report(trained)


def test_a_rating_of_an_earlier_picture_is_left_out() -> None:
    """Three of twelve raters rated an earlier picture of one page: their
    answers to it are left out, and the nine left are still enough."""
    corpus = synthetic_corpus()
    pictures = pictures_of(corpus)
    rows = synthetic_ratings(corpus)
    for row in rows:
        row["image_sha256"] = pictures[(row["url"], row["state"])]["sha256"]
    first = next(iter(corpus))
    for row in rows:
        if (row["url"], row["state"]) == first and row["rater"] <= 3:
            row["image_sha256"] = "an-older-picture"

    trained = train(as_rated(rows), corpus, pictures=pictures)

    assert trained.unpaired == [(first, "rated an earlier picture than the one captured now")]
    assert trained.coverage.counts[first] == 9


def test_a_page_whose_ratings_are_all_of_an_earlier_picture_needs_new_ones() -> None:
    corpus = synthetic_corpus()
    pictures = pictures_of(corpus)
    rows = synthetic_ratings(corpus)
    first = next(iter(corpus))
    for row in rows:
        same = (row["url"], row["state"]) == first
        row["image_sha256"] = "an-older-picture" if same else \
            pictures[(row["url"], row["state"])]["sha256"]

    with pytest.raises(RefusedToTrain, match="1 of 50 pages have fewer than 8 ratings; "
                                             "8 more ratings"):
        train(as_rated(rows), corpus, pictures=pictures)


def test_nothing_that_pairs_is_refused_with_the_reason() -> None:
    corpus = synthetic_corpus()

    with pytest.raises(RefusedToTrain, match="different capture runs"):
        train(as_rated(synthetic_ratings(corpus)), corpus, pictures=pictures_of(corpus, "run-9"))


def as_rated(rows: list[dict]) -> list[Rating]:
    """`as_ratings`, keeping which picture each answer was given for."""
    return [Rating(rater=r["rater"], url=r["url"], state=r["state"], page=r["page"],
                   repeat=r["repeat"], rating=r["rating"], synthetic=r.get("synthetic", False),
                   image=r.get("image_sha256", ""), set=r.get("set")) for r in rows]


def test_it_reads_the_sets_of_the_committed_forms() -> None:
    """`data/rating/form.json`: 50 pages, 44 in one set and the 6 anchors in both."""
    design = read_design(pipeline.DESIGN)

    assert len(design) == 50
    assert sorted(len(s) for s in design.values()).count(2) == 6
    assert sum(s == {1} for s in design.values()) == sum(s == {2} for s in design.values()) == 22
