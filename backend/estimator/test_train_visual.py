"""Old features against new: fair, gated, and unable to touch what SIMBA runs.

Every rating here is generated and marked synthetic, in a study under a temporary
folder. The tests that matter most are the ones that fail a model: the gate has
six conditions and each one is shown stopping a switch alone. Nothing here can
write to `data/`; a test checks that the app's own model file does not change.
"""

import hashlib
import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from backend.estimator import page_model, train, train_visual
from backend.estimator.page_model import FEATURES, VISUAL_FEATURES
from backend.estimator.train import RefusedToTrain, Repeated
from backend.estimator.train_visual import (ALL_FEATURES, ARMS, GATE, Arm, Paths, gain, judge_gate,
                                            says)

RUN, SITES_RUN = "r1", "r3"
REPEATS, NESTED = 3, 1


@pytest.fixture(autouse=True)
def quick(monkeypatch: pytest.MonkeyPatch) -> None:
    """A coarse grid of cut points: the search is not what is under test."""
    monkeypatch.setattr(train, "CUT_GRID", (2.0, 2.5, 3.0, 3.5, 4.0))


def world(root: Path, rated: int = 40, sites: int = 15, raters: int = 8, *,
          clutter_matters: bool = True, set3: bool = True, seed: int = 7,
          synthetic: bool = True) -> Paths:
    """A study of `rated` pages in two sets and `sites` in a third. The rating of
    a page follows `links`, and with `clutter_matters` its `image_area` as well."""
    rng = np.random.default_rng(seed)
    root.mkdir(parents=True, exist_ok=True)
    corpus, pictures, visual_rows, site_rows, set3_pages = [], [], [], [], []
    truth: dict[tuple[str, str], float] = {}

    def numbers() -> tuple[dict, dict]:
        nine = {name: float(rng.uniform(0, 10)) for name in FEATURES}
        five = {name: float(rng.uniform(0, 1)) for name in VISUAL_FEATURES}
        return nine, five

    def felt(nine: dict, five: dict) -> float:
        base = 1.5 + 0.2 * nine["links"]
        return base + (3.0 * five["image_area"] if clutter_matters else 0.0)

    for n in range(rated):
        url = f"https://rated-{n:02d}.example/"
        nine, five = numbers()
        corpus.append({"url": url, "state": "as it loads", "run": RUN, **nine})
        pictures.append({"id": f"rated-{n:02d}", "url": url, "state": "as it loads",
                         "run": RUN, "file": f"rated-{n:02d}.png", "sha256": f"sha-{n}"})
        visual_rows.append({"url": url, "state": "as it loads", "drift": 0.5 if n < 3 else 0.01,
                            **five})
        truth[(url, "as it loads")] = felt(nine, five)
    for n in range(sites):
        url = f"https://site-{n:02d}.example.pk/"
        nine, five = numbers()
        site_rows.append({"site": f"Site {n}", "category": "Banks", "status": "scored", "url": url,
                          "screenshot": f"site-{n:02d}.png", "sha256": f"site-sha-{n}",
                          "note": "", **nine, **five})
        set3_pages.append({"id": f"site-{n:02d}", "url": url, "state": "as it loads",
                           "run": SITES_RUN, "file": f"site-{n:02d}.png",
                           "sha256": f"site-sha-{n}"})
        truth[(url, "as it loads")] = felt(nine, five)
    site_rows.append({"site": "Skipped", "category": "Banks", "status": "skipped", "url": "x",
                      "note": "robots"})

    keys = sorted(truth)
    picture_of = {(p["url"], p["state"]): p["sha256"] for p in pictures + set3_pages}
    of_set: dict[int, list[tuple[str, str]]] = {1: [], 2: [], 3: []}
    for key in keys:
        of_set[3 if "site-" in key[0] else (1 if hash(key[0]) % 2 else 2)].append(key)
    rows = []
    for number, chosen in of_set.items():
        for rater in range(raters if (number != 3 or set3) else 0):
            for key in chosen:
                score = int(np.clip(round(truth[key] + rng.normal(0, 0.3)), 1, 5))
                rows.append({"rater": 1000 * number + rater, "url": key[0], "state": key[1],
                             "page": key[0], "repeat": False, "rating": score, "set": number,
                             "synthetic": synthetic, "image_sha256": picture_of[key]})
    paths = Paths(ratings=root / "ratings.jsonl", corpus=root / "corpus.json",
                  pictures=root / "pages.json", design=root / "form.json",
                  visual=root / "visual.json", set3=root / "set3.json",
                  evaluation=root / "EVALUATION.md", candidate=root / "candidate.json",
                  preview=root / "preview")
    paths.ratings.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    paths.corpus.write_text(json.dumps({"results": {"headless": corpus}}), encoding="utf-8")
    paths.pictures.write_text(json.dumps({"pages": pictures}), encoding="utf-8")
    paths.set3.write_text(json.dumps({"pages": set3_pages}), encoding="utf-8")
    paths.visual.write_text(json.dumps({
        "rated": {"rows": visual_rows}, "sites": {"run": {"id": SITES_RUN}, "rows": site_rows}}),
        encoding="utf-8")
    names = {key: f"P{i:02d}" for i, key in enumerate(keys)}
    paths.design.write_text(json.dumps({
        "pictures": {names[k]: {"url": k[0], "state": k[1]} for k in keys},
        "sets": {str(s): {"own": [names[k] for k in chosen], "anchors": []}
                 for s, chosen in of_set.items()}}), encoding="utf-8")
    return paths


def compared(paths: Paths, **options) -> train_visual.Comparison:
    return train_visual.compare(train.read_ratings(paths.ratings), train_visual.read_pages(paths),
                                repeats=REPEATS, nested=NESTED, **options)


def summary(mae: float, r2: float) -> Repeated:
    pair = (0.0, 0.0)
    return Repeated(r2=(r2, 0.0), mae=(mae, 0.0), rmse=pair, baseline_r2=pair, baseline_mae=pair,
                    baseline_rmse=pair)


def arm(mae: float = 0.4, r2: float = 0.5, kappa: float = 0.5, heavy: float = 0.7) -> Arm:
    levels = train.Levels(cuts=(2.4, 2.9), kappa=kappa, plain_kappa=kappa, nested_kappa=kappa,
                          nested_exact=0.5, nested_cuts=((2.4, 0.1), (2.9, 0.1)),
                          breaks=(2.0, 3.0), rated=(1, 1, 1), confusion=[[0] * 3] * 3)
    return Arm(name="x", features=(), predicted=np.zeros((1, 1)), repeated=summary(mae, r2),
               levels=levels, heavy_caught=heavy, errors=np.zeros(1))


def gate(floor: bool = True, set3: bool = True, synthetic: bool = False,
         won: tuple[float, float, float] = (0.1, 0.05, 0.15),
         across: dict | None = None, **new: float) -> train_visual.Verdict:
    arms = {"old": arm(), "new": arm(**{"mae": 0.3, "r2": 0.6, **new})}
    return judge_gate(floor, set3, synthetic, arms, won,
                      {"old": (0.6, 0.1), "new": (0.4, 0.3)} if across is None else across)


# --- the gate, one condition at a time ------------------------------------------------


def test_a_model_that_meets_every_condition_is_better() -> None:
    verdict = gate()
    assert verdict.better and len(verdict.checks) == len(GATE)


@pytest.mark.parametrize("changed, says_failed", [
    ({"floor": False}, GATE[0]), ({"set3": False}, GATE[0]), ({"synthetic": True}, GATE[0]),
    ({"won": (0.1, -0.01, 0.2)}, GATE[1]), ({"r2": 0.5}, GATE[2]), ({"kappa": 0.49}, GATE[3]),
    ({"heavy": 0.69}, GATE[4]), ({"across": {"old": (0.4, 0.3), "new": (0.4, 0.3)}}, GATE[5]),
], ids=["floor", "no-set-3", "synthetic", "interval", "r2", "kappa", "heavy", "pakistani"])
def test_each_condition_alone_keeps_the_old_model(changed: dict, says_failed: str) -> None:
    verdict = gate(**changed)
    assert not verdict.better
    assert [c.says for c in verdict.checks if not c.passed] == [says_failed]
    assert says_failed in says(verdict) and "stays" in says(verdict)


def test_a_lower_error_the_interval_cannot_tell_from_nothing_is_not_better() -> None:
    assert not gate(won=(0.2, 0.0, 0.4)).better


def test_a_verdict_that_passes_still_says_it_is_not_live() -> None:
    assert "not live" in says(gate())


def test_the_interval_is_above_zero_only_when_pages_agree() -> None:
    y = np.zeros(40)
    old = np.full((3, 40), 1.0)
    always = gain(y, old, np.full((3, 40), 0.5))
    assert always[1] > 0

    mixed = np.full((3, 40), 0.5)
    mixed[:, ::2] = 1.5  # half the pages better, half worse, by the same amount
    assert gain(y, old, mixed)[1] < 0


# --- the comparison -------------------------------------------------------------------


def test_every_arm_is_scored_on_the_same_pages(tmp_path: Path) -> None:
    found = compared(world(tmp_path))
    assert set(found.arms) == {"old", "new", "visual", "no_motion"}
    assert {rows.shape[0] for rows in found.x.values()} == {len(found.pages)} == {55}


def test_every_arm_has_the_features_it_says(tmp_path: Path) -> None:
    found = compared(world(tmp_path))
    assert found.x["old"].shape[1] == 9 and found.x["new"].shape[1] == 14
    assert found.x["visual"].shape[1] == 5 and found.x["no_motion"].shape[1] == 13
    assert ARMS["new"] == ALL_FEATURES and "motion" not in ARMS["no_motion"]


def test_the_folds_are_the_same_for_every_arm() -> None:
    """A difference between two lines must be a difference between their features."""
    rng = np.random.default_rng(0)
    y = rng.uniform(1, 5, 30)
    x = rng.normal(size=(30, 4))
    one, _ = train.held_out_predictions(x, y, 2)
    # The same rows with a useless column change the numbers and not which page
    # is held out when, which a constant-free check on the seed cannot show: a
    # model given `y` itself is perfect only if it was fitted on other pages.
    again, base = train.held_out_predictions(x[:, :2], y, 2)
    assert one.shape == again.shape
    other, base_again = train.held_out_predictions(x, y, 2)
    assert np.array_equal(base, base_again) and np.array_equal(one, other)


def test_when_clutter_drives_the_ratings_the_new_model_finds_it(tmp_path: Path) -> None:
    found = compared(world(tmp_path, rated=60, sites=15))
    assert found.arms["new"].repeated.mae[0] < found.arms["old"].repeated.mae[0]
    assert found.gain[1] > 0
    assert found.across["new"][0] < found.across["old"][0]


def test_when_clutter_does_not_the_gate_stays_shut(tmp_path: Path) -> None:
    found = compared(world(tmp_path, clutter_matters=False))
    assert not found.verdict.better


def test_a_synthetic_run_cannot_pass_however_good_it_looks(tmp_path: Path) -> None:
    found = compared(world(tmp_path, rated=60))
    assert found.synthetic
    assert not found.verdict.better
    assert not found.verdict.checks[0].passed


def test_the_pages_that_have_drifted_are_compared_without_them_as_well(tmp_path: Path) -> None:
    found = compared(world(tmp_path))
    assert found.steady_pages == 52
    assert set(found.steady) == set(ARMS)


def test_the_pakistani_test_is_fitted_without_a_pakistani_page(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = world(tmp_path)
    seen: list[int] = []
    real = train._model

    def counting():
        model = real()
        fit = model.fit

        def noted(x, y):
            seen.append(len(y))
            return fit(x, y)

        model.fit = noted
        return model

    pages = train_visual.read_pages(paths)
    monkeypatch.setattr(train, "_model", counting)
    keys = sorted(pages.features)
    rows = {"old": np.array([[pages.features[k][n] for n in FEATURES] for k in keys])}
    y = np.linspace(1, 5, len(keys))
    train_visual.across_sets(keys, y, rows, pages.sites)
    assert seen == [len(keys) - len(pages.sites)]


def test_a_rated_page_with_no_first_screen_read_is_left_out_of_every_arm(tmp_path: Path) -> None:
    paths = world(tmp_path)
    data = json.loads(paths.visual.read_text(encoding="utf-8"))
    data["rated"]["rows"][5] = {"url": data["rated"]["rows"][5]["url"], "state": "as it loads",
                                "error": "timed out"}
    paths.visual.write_text(json.dumps(data), encoding="utf-8")
    found = compared(paths)
    assert len(found.pages) == 54
    assert any("timed out" in why for _, why in found.left_out)


def test_set_3_raters_are_held_against_the_others_on_the_same_pictures() -> None:
    def rating(rater: int, url: str, value: int, form: int) -> train.Rating:
        return train.Rating(rater=rater, url=url, state="s", page=url, repeat=False,
                            rating=value, set=form)

    rows = [rating(1, "a", 2, 1), rating(2, "a", 4, 2), rating(3, "a", 5, 3),
            rating(1, "b", 3, 1)]
    assert train_visual.against_set3(rows) == {("a", "s"): (3.0, 2, 5.0, 1)}


def test_the_first_two_sets_are_still_compared_with_a_third_in_the_ratings() -> None:
    def rating(rater: int, url: str, value: int, form: int) -> train.Rating:
        return train.Rating(rater=rater, url=url, state="s", page=url, repeat=False,
                            rating=value, set=form)

    rows = [rating(r, "a", 2, 1) for r in range(1, 4)] + [rating(r, "a", 3, 2) for r in range(4, 7)]
    rows += [rating(7, "a", 5, 3)]
    found = train.groups(rows)
    assert found is not None and found.anchors[("a", "s")] == (2.0, 3, 3.0, 3)


# --- refusing, and saying what is needed ------------------------------------------------


def test_it_refuses_under_eight_ratings_and_says_how_many_more(tmp_path: Path) -> None:
    paths = world(tmp_path, raters=5)
    with pytest.raises(RefusedToTrain) as refused:
        compared(paths)
    said = str(refused.value)
    assert "3 more Set 1 raters" in said and "3 more Set 2 raters" in said
    assert "3 more Set 3 raters" in said


def test_with_no_set_3_ratings_it_says_all_eight_are_needed(tmp_path: Path) -> None:
    paths = world(tmp_path, set3=False)
    with pytest.raises(RefusedToTrain, match="8 more Set 3 raters"):
        compared(paths)


def test_the_floor_is_the_same_as_trains() -> None:
    assert train.MIN_RATINGS == 8


def test_ratings_that_mix_synthetic_and_real_are_refused(tmp_path: Path) -> None:
    paths = world(tmp_path)
    lines = paths.ratings.read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[0])
    row["synthetic"] = False
    paths.ratings.write_text("\n".join([json.dumps(row), *lines[1:]]), encoding="utf-8")
    with pytest.raises(RefusedToTrain, match="mix"):
        compared(paths)


# --- under the floor, when a person asks -------------------------------------------------


def thinned(paths: Paths, form: int = 2, keep: int = 5) -> Paths:
    """The same study with only `keep` raters left in `form`: under the floor there."""
    rows = [json.loads(line) for line in paths.ratings.read_text(encoding="utf-8").splitlines()]
    rows = [r for r in rows if r["set"] != form or r["rater"] - 1000 * form < keep]
    paths.ratings.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return paths


def test_a_real_run_still_refuses_under_the_floor_unless_asked(tmp_path: Path) -> None:
    with pytest.raises(RefusedToTrain, match="3 more Set 2 raters"):
        compared(thinned(world(tmp_path)))


def test_asked_for_it_runs_under_the_floor_and_names_every_page_below_it(tmp_path: Path) -> None:
    paths = thinned(world(tmp_path))
    found = compared(paths, min_ratings=5)
    design = train.read_design(paths.design)
    set2 = {key for key in found.pages if design.get(key) == {2}}
    assert set2 and {key for key, _ in found.below_floor} == set2
    assert {n for _, n in found.below_floor} == {5}
    assert found.min_ratings == 5


def test_under_the_floor_the_gate_stays_shut_however_good_the_model(tmp_path: Path) -> None:
    """The gate was set before any Set 3 rating: a person asking for fewer ratings
    lowers what training refuses, not what a switch needs."""
    found = compared(thinned(world(tmp_path, rated=60, synthetic=False)), min_ratings=5)
    assert not found.verdict.better
    first = found.verdict.checks[0]
    assert not first.passed and first.detail == "under the floor"


def test_the_report_says_it_is_under_the_floor_before_any_number(tmp_path: Path) -> None:
    found = compared(thinned(world(tmp_path)), min_ratings=5)
    text = train_visual.report(found)
    floor = text.index("Below the study's floor")
    assert floor < text.index("| Arm |")
    named = text[floor:text.index("\n\n", floor)]
    assert all(key[0] in named for key, _ in found.below_floor)
    assert "--min-ratings 5" in named


def test_a_run_passes_on_the_floor_it_was_given(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = thinned(world(tmp_path))
    monkeypatch.setattr(train_visual, "EFFORT", {"repeats": REPEATS, "nested": NESTED})
    with pytest.raises(RefusedToTrain):
        train_visual.run(paths)
    found = train_visual.run(paths, min_ratings=5)
    assert found.min_ratings == 5
    assert "Below the study's floor" in paths.evaluation.read_text(encoding="utf-8")
    assert json.loads(paths.candidate.read_text(encoding="utf-8"))["min_ratings"] == 5


# --- what each arm is asked, overall and on the Pakistani pages ---------------------------


def test_the_pakistani_pages_are_scored_from_the_same_held_out_predictions(tmp_path: Path) -> None:
    from sklearn.metrics import mean_absolute_error, r2_score
    found = compared(world(tmp_path))
    sites = np.array([key[0].startswith("https://site-") for key in found.pages])
    assert sites.sum() == 15 and set(found.on_sites) == set(ARMS) | {"mean"}
    for name, arm_found in found.arms.items():
        rows = arm_found.predicted[:, sites]
        r2, mae = found.on_sites[name]
        assert r2[0] == pytest.approx(np.mean([r2_score(found.y[sites], r) for r in rows]))
        assert mae[0] == pytest.approx(np.mean([mean_absolute_error(found.y[sites], r)
                                                for r in rows]))


def test_a_preview_has_no_pakistani_pages_to_score(tmp_path: Path) -> None:
    found = compared(world(tmp_path, raters=5, set3=False), min_ratings=5, preview=True)
    assert found.on_sites == {}


def test_importance_is_given_for_the_old_the_new_and_the_five_alone(tmp_path: Path) -> None:
    found = compared(world(tmp_path))
    assert set(found.importances) == {"old", "new", "visual"}
    for name, measured in found.importances.items():
        assert tuple(measured) == ARMS[name]
    assert found.importance == found.importances["new"]


def test_every_arm_is_held_against_the_old_with_its_own_interval(tmp_path: Path) -> None:
    found = compared(world(tmp_path))
    assert set(found.gains) == {"new", "visual", "no_motion"}
    assert found.gains["new"] == found.gain
    assert found.gains["visual"] == gain(found.y, found.arms["old"].predicted,
                                         found.arms["visual"].predicted)


def test_the_report_gives_agreement_for_each_set(tmp_path: Path) -> None:
    text = train_visual.report(compared(world(tmp_path)))
    assert all(f"Set {n}" in text.split("| Arm |")[0] for n in (1, 2, 3))


# --- the preview --------------------------------------------------------------------


def test_a_preview_runs_under_the_floor_on_the_first_two_sets(tmp_path: Path) -> None:
    paths = world(tmp_path, raters=5, set3=False)
    found = compared(paths, min_ratings=5, preview=True)
    assert found.preview and len(found.pages) == 40
    assert found.across is None


def test_a_preview_cannot_pass_the_gate(tmp_path: Path) -> None:
    found = compared(world(tmp_path, rated=60, raters=5, set3=False), min_ratings=5, preview=True)
    assert not found.verdict.better


def test_a_preview_cannot_pass_even_on_real_ratings_that_look_better(tmp_path: Path) -> None:
    found = compared(world(tmp_path, rated=60, raters=8, set3=True, synthetic=False),
                     min_ratings=8, preview=True)
    first = found.verdict.checks[0]
    assert not first.passed and first.detail == "under the floor"
    assert not found.verdict.better


def test_a_preview_says_what_it_is_before_any_number() -> None:
    assert train_visual.PREVIEW_MIN_RATINGS == 5


def test_a_preview_writes_to_neither_evaluation_nor_the_candidate(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = world(tmp_path, raters=5, set3=False)
    monkeypatch.setattr(train_visual, "EFFORT", {"repeats": REPEATS, "nested": NESTED})
    train_visual.run(paths, preview=True)
    assert not paths.evaluation.exists() and not paths.candidate.exists()
    assert "A preview, not a result" in (paths.preview / "report.md").read_text(encoding="utf-8")
    assert (paths.preview / "estimator_visual.json").exists()


# --- it cannot touch what SIMBA runs ------------------------------------------------------


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_a_full_run_leaves_the_live_model_as_it_was(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    before = digest(train.COEFFICIENTS), digest(train.MODEL)
    paths = world(tmp_path, rated=60)
    monkeypatch.setattr(train_visual, "EFFORT", {"repeats": REPEATS, "nested": NESTED})
    train_visual.run(paths)
    assert (digest(train.COEFFICIENTS), digest(train.MODEL)) == before
    assert paths.candidate.exists()


def test_even_a_model_that_passes_every_condition_changes_nothing_live(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The case the whole design is for: not synthetic, the floor met, better."""
    before = digest(train.COEFFICIENTS), digest(train.MODEL)
    paths = world(tmp_path, rated=60, synthetic=False)
    monkeypatch.setattr(train_visual, "EFFORT", {"repeats": REPEATS, "nested": NESTED})

    found = train_visual.run(paths)

    assert found.verdict.better, [c.detail for c in found.verdict.checks if not c.passed]
    assert (digest(train.COEFFICIENTS), digest(train.MODEL)) == before
    saved = json.loads(paths.candidate.read_text(encoding="utf-8"))
    assert saved["better_than_live"] is True
    assert page_model.load(paths.candidate) is None  # the app would not read it
    text = paths.evaluation.read_text(encoding="utf-8")
    assert "It is not live" in text and "taken at" in text


def test_the_new_model_can_never_be_written_over_the_live_one(tmp_path: Path) -> None:
    """Against a stand-in. On 2026-11-02 this test was run with the guard broken on
    purpose, against the real file, and overwrote the live model with a synthetic
    one; `git status` showed it. A test of a guard must not depend on the guard."""
    found = compared(world(tmp_path))
    stand_in = tmp_path / "estimator.json"
    with pytest.raises(RefusedToTrain, match="running app"):
        train_visual.save_candidate(found, stand_in, projects_live=stand_in)
    assert not stand_in.exists()


def test_the_guard_is_set_on_the_file_the_app_really_reads() -> None:
    default = inspect.signature(train_visual.save_candidate).parameters["projects_live"].default
    assert default == train.COEFFICIENTS == page_model.PATH


def test_the_candidate_is_a_different_file_from_the_live_one() -> None:
    assert train_visual.CANDIDATE != train.COEFFICIENTS


def test_the_running_app_refuses_a_model_of_fourteen_features(tmp_path: Path) -> None:
    paths = world(tmp_path)
    found = compared(paths)
    train_visual.save_candidate(found, paths.candidate)
    data = json.loads(paths.candidate.read_text(encoding="utf-8"))
    data["synthetic"] = False
    paths.candidate.write_text(json.dumps(data), encoding="utf-8")
    assert page_model.load(paths.candidate) is None
    model = page_model.load(paths.candidate, names=ALL_FEATURES)
    assert model is not None and model.names == ALL_FEATURES


def test_a_synthetic_result_is_kept_out_of_the_projects_evaluation(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = world(tmp_path, rated=60)
    size = train.EVALUATION.stat().st_size
    monkeypatch.setattr(train_visual, "EFFORT", {"repeats": REPEATS, "nested": NESTED})
    paths.evaluation = train.EVALUATION
    with pytest.raises(RefusedToTrain, match="synthetic"):
        train_visual.run(paths)
    assert train.EVALUATION.stat().st_size == size


def test_the_candidate_gives_the_same_score_the_sum_should(tmp_path: Path) -> None:
    paths = world(tmp_path)
    found = compared(paths)
    train_visual.save_candidate(found, paths.candidate)
    data = json.loads(paths.candidate.read_text(encoding="utf-8"))
    data["synthetic"] = False
    paths.candidate.write_text(json.dumps(data), encoding="utf-8")
    model = page_model.load(paths.candidate, names=ALL_FEATURES)
    assert model is not None
    fitted = train._model().fit(found.x["new"], found.y)
    row = found.x["new"][4]
    by_hand = model.intercept + sum(
        c * (v - m) / s for c, v, m, s
        in zip(model.coefficients, row, model.means, model.spreads))
    assert by_hand == pytest.approx(float(fitted.predict(row[None])[0]))
