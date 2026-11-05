"""Does seeing visual clutter help? The old features and the new, on the same pages.

    python -m backend.estimator.train_visual "<Set 1>.csv" "<Set 2>.csv" "<Set 3>.csv"
    python -m backend.estimator.train_visual --min-ratings 5 --charts   # under the floor, named

Reads the forms' CSVs as `tools.rating.retrain` does, then trains on Sets 1 to 3
four times over the same pages and the same folds, so that a difference between
two lines is a difference between their features and nothing else:

| Arm | Features |
|---|---|
| `old` | the nine, refitted on these pages |
| `new` | the nine and the five first-screen features |
| `visual` | the five alone: the ablation |
| `no_motion` | `new` without `motion`, which no still picture can show |

**It refuses until every page has eight ratings**, as `train.py` does, and says how
many more of which set. There are two ways round that. `--min-ratings 5` runs the
real comparison with fewer, as `train.py --min-ratings` does: the report names every
page below eight before any number, and the gate's first condition still fails, so it
can say how far apart the arms are and cannot switch a model. `--preview` runs on the
pages of Sets 1 and 2 alone and writes only to `.scratch/`: it can show the sums work,
and it cannot pass the gate, because the pages the question is about are not in it.

Each arm is reported overall and on the Pakistani pages alone, from the same held-out
predictions; with its gain over `old`, pages resampled; and the old, new and five-alone
arms with their features' importance. `--charts` draws the importance and the predicted
ratings against people's, as SVG (`tools/evaluation/visual_charts.py`).

**Whether the new model is better is decided by `GATE`, set before any Set 3 rating
existed** (2026-11-02), so that the bar could not be fitted to the result. All must
hold, on held-out pages:

1. real ratings, the floor met, Set 3 in it;
2. held-out error lower, with a 95% interval that stays above zero when pages are
   resampled, because 40 shuffles of the same 65 pages are not 40 samples of the web;
3. R² higher;
4. levels no worse: nested kappa, cut points chosen without the page scored;
5. heavy pages caught no fewer;
6. on the Pakistani pages, with both models fitted on Sets 1 and 2 alone and tested
   on Set 3, lower error. That is the failure this work began from.

**Nothing here changes what SIMBA runs.** It writes the new model to
`data/estimator_visual.json` and never to `data/estimator.json`. Even a new model
that passes every check is not live: the running app measures only the nine, and
`page_model.load` refuses a model of anything else. Measuring the five during a task
is a change to the loop, `motion` costs three seconds of a person's time, and that
is a decision for all three owners (DECISIONS.md, *What the visual features can and
cannot be*). So a pass says what is left to do, and a fail says why not.

**Pages rated in October carry features read in November** (`visual_features`,
`drift`). The comparison is run on all of them, and again without the pages that have
drifted past `DRIFT_LIMIT`, where the features no longer describe what was rated.

Then `tools/evaluation/rescore_index` works the overwhelm index out again.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold

from backend.estimator import train
from backend.estimator.page_model import FEATURES, VISUAL_FEATURES
from backend.estimator.train import RefusedToTrain
from tools.evaluation.conditions import banner, conditions

REPO = Path(__file__).resolve().parents[2]
VISUAL = REPO / "data" / "visual_features.json"
SET3 = REPO / "data" / "rating" / "set3.json"
#: Never `train.COEFFICIENTS`: that is what the running app reads.
CANDIDATE = REPO / "data" / "estimator_visual.json"
PREVIEW = REPO / ".scratch" / "visual-features" / "preview"
#: Where `--charts` draws, by default: gitignored, beside the scratch of this work.
CHARTS = REPO / ".scratch" / "retrain-visual"
ALL_FEATURES = (*FEATURES, *VISUAL_FEATURES)
ARMS: dict[str, tuple[str, ...]] = {
    "old": FEATURES,
    "new": ALL_FEATURES,
    "visual": VISUAL_FEATURES,
    "no_motion": tuple(name for name in ALL_FEATURES if name != "motion"),
}
LABELS = {"old": "Old: the nine", "new": "New: the nine and the five",
          "visual": "The five alone", "no_motion": "New, without motion",
          "mean": "Predicting the training mean"}
#: The arms whose features' importance is measured: the three the question names.
IMPORTANCE_ARMS = ("old", "new", "visual")
SET_OF_SITES = 3
#: Ratings the preview makes do with, as the live model did (2026-10-30).
PREVIEW_MIN_RATINGS = 5
#: Past this share of the screen differing from the picture people rated, a page's
#: new features are of a different page. Set from the pixel differences alone, on
#: 2026-11-02, before any comparison was run (EVALUATION.md, 2026-11-02c).
DRIFT_LIMIT = 0.25
#: How hard to look: `train`'s own 40 shuffles and five nested repeats.
EFFORT = {"repeats": train.REPEATS, "nested": 5}
BOOTSTRAPS = 10000
CONFIDENCE = (2.5, 97.5)
#: The conditions a new model must meet: see the module's docstring.
GATE = ("real ratings, the floor met, and Set 3 in them",
        "held-out error lower, its 95% interval above zero",
        "held-out R² higher",
        "levels no worse (nested kappa)",
        "heavy pages caught no fewer",
        "Pakistani pages: lower error, fitted on Sets 1 and 2 alone")


@dataclass
class Paths:
    """Where everything is, so a test can move all of it."""

    ratings: Path = train.RATINGS
    corpus: Path = train.CORPUS
    pictures: Path = train.PICTURES
    design: Path = train.DESIGN
    visual: Path = VISUAL
    set3: Path = SET3
    evaluation: Path = train.EVALUATION
    candidate: Path = CANDIDATE
    preview: Path = PREVIEW


# --- the pages ----------------------------------------------------------------------


@dataclass
class Pages:
    """Everything known about the pages, keyed by `(url, state)`."""

    corpus: dict[tuple[str, str], dict]
    pictures: dict[tuple[str, str], dict]
    #: A page's fourteen, for the pages that have them all.
    features: dict[tuple[str, str], dict[str, float]]
    sites: set[tuple[str, str]]
    drift: dict[tuple[str, str], float | None]
    design: dict[tuple[str, str], set[int]]
    #: Rated pages the first-screen read could not reach, and why.
    unread: dict[tuple[str, str], str] = field(default_factory=dict)


def read_pages(paths: Paths) -> Pages:
    """Sets 1 and 2's pages with their first-screen read beside them, and Set 3's
    from one load each, which are all the features a site has."""
    corpus, _ = train.read_corpus(paths.corpus)
    pictures = train.read_pictures(paths.pictures)
    visual = json.loads(paths.visual.read_text(encoding="utf-8"))
    features: dict[tuple[str, str], dict[str, float]] = {}
    drift: dict[tuple[str, str], float | None] = {}
    unread: dict[tuple[str, str], str] = {}
    for row in visual["rated"]["rows"]:
        key = (row["url"], row["state"])
        if "error" in row:
            unread[key] = row["error"]
        elif key in corpus:
            features[key] = {**{n: float(corpus[key][n]) for n in FEATURES},
                             **{n: float(row[n]) for n in VISUAL_FEATURES}}
            drift[key] = row.get("drift")
    sites: set[tuple[str, str]] = set()
    if paths.set3.exists():
        chosen = train.read_pictures(paths.set3)
        run = visual["sites"]["run"]["id"]
        rows = {(row["url"], "as it loads"): row for row in visual["sites"]["rows"]
                if row["status"] == "scored"}
        for key in chosen:
            if key in rows:
                corpus[key] = {**rows[key], "run": run}
                features[key] = {n: float(rows[key][n]) for n in ALL_FEATURES}
                sites.add(key)
        pictures = {**pictures, **chosen}
    return Pages(corpus=corpus, pictures=pictures, features=features, sites=sites, drift=drift,
                 design=train.read_design(paths.design), unread=unread)


# --- the comparison -----------------------------------------------------------------


@dataclass
class Arm:
    name: str
    features: tuple[str, ...]
    predicted: np.ndarray
    repeated: train.Repeated
    levels: train.Levels
    #: Of the pages raters put at "Very" or more, the share found heavy, held out.
    heavy_caught: float
    #: Pages -> their mean error on them, for the arm against `old`.
    errors: np.ndarray


@dataclass
class Check:
    says: str
    passed: bool
    detail: str


@dataclass
class Verdict:
    checks: list[Check]

    @property
    def better(self) -> bool:
        return all(check.passed for check in self.checks)


@dataclass
class Comparison:
    synthetic: bool
    preview: bool
    agreement: train.Agreement
    coverage: train.Shortfall
    pages: list[tuple[str, str]]
    y: np.ndarray
    x: dict[str, np.ndarray]
    arms: dict[str, Arm]
    #: Old minus new error, mean and 95% interval, pages resampled. Above zero is better.
    gain: tuple[float, float, float]
    #: Arm -> (error, R²) on Set 3, fitted on Sets 1 and 2 alone; None without Set 3.
    across: dict[str, tuple[float, float]] | None
    #: Arm -> (R², error) on the pages that have not drifted, and how many.
    steady: dict[str, tuple[float, float]]
    steady_pages: int
    #: Anchor -> (Sets 1 and 2's mean, raters, Set 3's mean, raters).
    anchors: dict[tuple[str, str], tuple[float, int, float, int]]
    #: Arm -> feature -> (R² lost when shuffled, its sd, standardised coefficient),
    #: for `IMPORTANCE_ARMS`.
    importances: dict[str, dict[str, tuple[float, float, float]]]
    baseline: train.Repeated
    verdict: Verdict
    ceiling: float | None = None
    left_out: list[tuple[tuple[str, str], str]] = field(default_factory=list)
    #: The floor this ran on, and the pages compared that have fewer than eight.
    min_ratings: int = train.MIN_RATINGS
    below_floor: list[tuple[tuple[str, str], int]] = field(default_factory=list)
    #: Arm, and "mean" -> ((R², sd), (error, sd)) on the Pakistani pages alone, from
    #: the same held-out predictions as the whole. Empty without them.
    on_sites: dict[str, tuple[tuple[float, float], tuple[float, float]]] = \
        field(default_factory=dict)
    #: Arm -> its error lower than old's, mean and 95% interval, pages resampled.
    gains: dict[str, tuple[float, float, float]] = field(default_factory=dict)
    #: Which of `pages` are Set 3's.
    sites: np.ndarray | None = None

    @property
    def importance(self) -> dict[str, tuple[float, float, float]]:
        """The new model's, as reported since 2026-11-02."""
        return self.importances["new"]


def _matrix(pages: list[tuple[str, str]], features: dict, names: tuple[str, ...]) -> np.ndarray:
    return np.array([[features[key][name] for name in names] for key in pages])


def gain(y: np.ndarray, old: np.ndarray, new: np.ndarray, seed: int = train.SEED
         ) -> tuple[float, float, float]:
    """How much lower the new error is, with an interval from resampling pages:
    each page's mean error over the shuffles, old minus new."""
    difference = np.abs(old - y).mean(axis=0) - np.abs(new - y).mean(axis=0)
    rng = np.random.default_rng(seed)
    means = difference[rng.integers(0, len(difference), (BOOTSTRAPS, len(difference)))].mean(axis=1)
    low, high = np.percentile(means, CONFIDENCE)
    return float(difference.mean()), float(low), float(high)


def caught(y: np.ndarray, bands: list[list[int]]) -> float:
    """The share of the pages raters called heavy that held-out bands call heavy."""
    heavy = train.band(y, train.BANDS) == 2
    if not heavy.any():
        return 0.0
    return float(np.mean([(np.array(row)[heavy] == 2).mean() for row in bands]))


def across_sets(pages: list[tuple[str, str]], y: np.ndarray, x: dict[str, np.ndarray],
                sites: set[tuple[str, str]]) -> dict[str, tuple[float, float]] | None:
    """Fitted on Sets 1 and 2 alone, tested on the Pakistani pages: the one test
    here with no page of that kind among those it learned from."""
    test = np.array([key in sites for key in pages])
    if not test.any() or test.all():
        return None
    found = {}
    for name, rows in x.items():
        scores = np.clip(train._model().fit(rows[~test], y[~test]).predict(rows[test]), *train.SCALE)
        r2 = float(r2_score(y[test], scores)) if test.sum() > 1 else float("nan")
        found[name] = (float(mean_absolute_error(y[test], scores)), r2)
    return found


def on_pages(y: np.ndarray, predicted: np.ndarray, chosen: np.ndarray
             ) -> tuple[tuple[float, float], tuple[float, float]]:
    """R² and error on the `chosen` pages alone, each shuffle scored on its own and
    then averaged, as `train.repeated` does for all of them."""
    r2s = [float(r2_score(y[chosen], row[chosen])) for row in predicted]
    maes = [float(mean_absolute_error(y[chosen], row[chosen])) for row in predicted]
    return (float(np.mean(r2s)), float(np.std(r2s))), (float(np.mean(maes)), float(np.std(maes)))


def steady_pages(pages: list[tuple[str, str]], drift: dict) -> np.ndarray:
    """The pages whose picture is still much what was rated. Set 3's are from
    one load, so they have no drift, and a page with none recorded stays."""
    return np.array([(drift.get(key) or 0.0) <= DRIFT_LIMIT for key in pages])


def against_set3(ratings: list[train.Rating]) -> dict[tuple[str, str], tuple[float, int, float, int]]:
    """Set 3's raters against Sets 1 and 2's on the pages both rated, first showings."""
    first = [r for r in ratings if not r.repeat and r.set is not None]
    given: dict[tuple[str, str], dict[bool, list[int]]] = {}
    for r in first:
        given.setdefault(r.key, {}).setdefault(r.set == SET_OF_SITES, []).append(r.rating)
    return {key: (float(np.mean(found[False])), len(found[False]),
                  float(np.mean(found[True])), len(found[True]))
            for key, found in sorted(given.items()) if len(found) == 2}


def judge_gate(comparison_floor: bool, has_set3: bool, synthetic: bool, arms: dict[str, Arm],
               won: tuple[float, float, float],
               across: dict[str, tuple[float, float]] | None) -> Verdict:
    """`GATE`, in order. Any one failing keeps the old model."""
    old, new = arms["old"], arms["new"]
    checks = [
        Check(GATE[0], comparison_floor and has_set3 and not synthetic,
              ("synthetic ratings" if synthetic else "under the floor" if not comparison_floor
               else "no Set 3 pages" if not has_set3 else "met")),
        Check(GATE[1], won[1] > 0,
              f"{new.repeated.mae[0]:.3f} against {old.repeated.mae[0]:.3f}; lower by "
              f"{won[0]:.3f}, 95% interval {won[1]:.3f} to {won[2]:.3f}"),
        Check(GATE[2], new.repeated.r2[0] > old.repeated.r2[0],
              f"{new.repeated.r2[0]:.3f} against {old.repeated.r2[0]:.3f}"),
        Check(GATE[3], new.levels.nested_kappa >= old.levels.nested_kappa,
              f"{new.levels.nested_kappa:.3f} against {old.levels.nested_kappa:.3f}"),
        Check(GATE[4], new.heavy_caught >= old.heavy_caught,
              f"{new.heavy_caught:.0%} against {old.heavy_caught:.0%}"),
    ]
    if across is None:
        checks.append(Check(GATE[5], False, "no Set 3 pages to test on"))
    else:
        checks.append(Check(GATE[5], across["new"][0] < across["old"][0],
                            f"{across['new'][0]:.3f} against {across['old'][0]:.3f}"))
    return Verdict(checks)


def compare(ratings: list[train.Rating], pages: Pages, min_ratings: int = train.MIN_RATINGS,
            preview: bool = False, repeats: int = EFFORT["repeats"],
            nested: int = EFFORT["nested"]) -> Comparison:
    """Everything above, in order. Raises `RefusedToTrain` with the reason."""
    kept, unpaired = train.paired(ratings, pages.corpus, pages.pictures)
    if not kept:
        raise RefusedToTrain("no rating pairs with a current picture and features from its run.")
    synthetic = {r.synthetic for r in kept}
    if synthetic == {True, False}:
        raise RefusedToTrain("the ratings mix synthetic rows with real ones.")
    wanted = train.trainable(pages.corpus, pages.pictures)
    if preview:
        wanted = [key for key in wanted if key not in pages.sites]
        kept = [r for r in kept if r.key not in pages.sites]
    coverage = train.shortfall(kept, wanted, pages.design, min_ratings)
    if coverage.short:
        raise RefusedToTrain(
            f"{coverage.says()} Training needs at least {min_ratings} ratings on every page, "
            f"the floor set for this study. Set 3's form is in "
            f"`tools/rating/form/README.md`, section 7.")
    means = train.page_means(kept)
    order = sorted(key for key in means if key in pages.features)
    left_out = list(unpaired) + [(key, pages.unread.get(key, "no first-screen read"))
                                 for key in sorted(set(means) - set(order))]
    if len(order) < train.MIN_PAGES:
        raise RefusedToTrain(f"only {len(order)} rated pages have all fourteen features.")
    y = np.array([means[key][0] for key in order])
    x = {name: _matrix(order, pages.features, names) for name, names in ARMS.items()}

    arms: dict[str, Arm] = {}
    baseline: train.Repeated | None = None
    base = np.zeros((repeats, len(y)))
    for name, names in ARMS.items():
        predicted, base = train.held_out_predictions(x[name], y, repeats)
        baseline = train.repeated(y, predicted, base)
        levels = train.choose_levels(x[name], y, predicted, nested)
        arms[name] = Arm(name=name, features=names, predicted=predicted, repeated=baseline,
                         levels=levels, heavy_caught=caught(y, levels.nested_bands),
                         errors=np.abs(predicted - y).mean(axis=0))
    assert baseline is not None
    gains = {name: gain(y, arms["old"].predicted, arm.predicted)
             for name, arm in arms.items() if name != "old"}
    won = gains["new"]
    across = across_sets(order, y, x, pages.sites)
    sites = np.array([key in pages.sites for key in order])
    on_sites = {}
    if sites.sum() > 1:
        on_sites = {name: on_pages(y, arm.predicted, sites) for name, arm in arms.items()}
        on_sites["mean"] = on_pages(y, base, sites)
    below = [(key, coverage.counts.get(key, 0)) for key in order
             if coverage.counts.get(key, 0) < train.MIN_RATINGS]

    steady = steady_pages(order, pages.drift)
    held = {}
    if steady.sum() >= train.MIN_PAGES:
        for name in ARMS:
            predicted, base = train.held_out_predictions(x[name][steady], y[steady], repeats)
            found = train.repeated(y[steady], predicted, base)
            held[name] = (found.r2[0], found.mae[0])

    importances = {name: _importance(x[name], y, ARMS[name],
                                     train._model().fit(x[name], y)[-1].coef_)
                   for name in IMPORTANCE_ARMS}
    floor_met = min_ratings >= train.MIN_RATINGS and not coverage.short
    verdict = judge_gate(floor_met and not preview, bool(pages.sites) and not preview,
                         synthetic == {True}, arms, won, across)
    return Comparison(
        synthetic=synthetic == {True}, preview=preview, agreement=train.agreement(kept),
        coverage=coverage, pages=order, y=y, x=x, arms=arms, gain=won, across=across,
        steady=held, steady_pages=int(steady.sum()), anchors=against_set3(kept),
        importances=importances, baseline=baseline, verdict=verdict,
        ceiling=train.reliability(kept), left_out=left_out, min_ratings=min_ratings,
        below_floor=below, on_sites=on_sites, gains=gains, sites=sites)


def _importance(x: np.ndarray, y: np.ndarray, names: tuple[str, ...], coefficients: np.ndarray
                ) -> dict[str, tuple[float, float, float]]:
    """R² lost on held-out folds when one feature is shuffled, as `train` measures it."""
    lost: dict[str, list[float]] = {name: [] for name in names}
    for train_index, test_index in KFold(n_splits=train.FOLDS, shuffle=True,
                                         random_state=train.SEED).split(x):
        model = train._model().fit(x[train_index], y[train_index])
        found = permutation_importance(model, x[test_index], y[test_index], scoring="r2",
                                       n_repeats=train.PERMUTATION_REPEATS,
                                       random_state=train.SEED)
        for at, name in enumerate(names):
            lost[name].extend(float(v) for v in found.importances[at])
    return {name: (float(np.mean(lost[name])), float(np.std(lost[name])),
                   float(coefficients[at])) for at, name in enumerate(names)}


# --- writing ------------------------------------------------------------------------


def save_candidate(found: Comparison, path: Path, projects_live: Path = train.COEFFICIENTS) -> None:
    """The new model as plain numbers, in the shape `page_model` reads. Never the
    file the app runs on, and never synthetic at the project's own path."""
    if path.resolve() == projects_live.resolve():
        raise RefusedToTrain(f"refusing to write the new model over {projects_live}: "
                             "the running app reads that, and measures only the nine.")
    if found.synthetic and path.resolve() == CANDIDATE.resolve():
        raise RefusedToTrain(f"refusing to save a synthetic model to {CANDIDATE}.")
    model = train._model().fit(found.x["new"], found.y)
    cuts = found.arms["new"].levels.cuts
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "version": "candidate " + datetime.now().astimezone().isoformat(timespec="seconds"),
        "synthetic": found.synthetic,
        "preview": found.preview,
        "better_than_live": found.verdict.better,
        "scale": list(train.SCALE),
        "features": list(ALL_FEATURES),
        "means": [float(v) for v in model[0].mean_],
        "spreads": [float(v) for v in model[0].scale_],
        "coefficients": [float(v) for v in model[-1].coef_],
        "intercept": float(model[-1].intercept_),
        "ridge_alpha": float(model[-1].alpha_),
        "cuts": {"calm": cuts[0], "heavy": cuts[1]},
        "raters": found.agreement.raters,
        "pages": len(found.pages),
        "min_ratings": found.coverage.minimum,
    }, indent=2) + "\n", encoding="utf-8")


def report(found: Comparison, when: datetime | None = None) -> str:
    """What the comparison found, for EVALUATION.md."""
    when = when or datetime.now().astimezone()
    title = "a preview on Sets 1 and 2" if found.preview else "Sets 1 to 3"
    lines = [f"## {when:%Y-%m-%d} — the old features and the new, {title}", ""]
    if found.synthetic:
        lines += ["**SYNTHETIC — a test of the pipeline, not a result.**", ""]
    if found.preview:
        lines += [f"**A preview, not a result.** Under the floor, at {found.coverage.minimum} "
                  "ratings a page, and without the Pakistani pages the question is about. It "
                  "cannot pass the gate.", ""]
    if found.below_floor and not found.preview:
        lines += [f"**Below the study's floor.** {len(found.below_floor)} of {len(found.pages)} "
                  f"pages have fewer than {train.MIN_RATINGS} ratings, so this ran with "
                  f"`--min-ratings {found.min_ratings}`, which only a person asks for, and "
                  f"the gate's first condition fails whatever else holds: " + "; ".join(
                      f"{u} [{st}] ({n})" for (u, st), n in found.below_floor) + ".", ""]
    a = found.agreement
    by_set = ", ".join(f"Set {s} {train._number(alpha)} ({a.raters_by_set.get(s, 0)} raters)"
                       for s, alpha in sorted(a.alpha_by_set.items()))
    lines += [
        f"{a.raters} raters, {len(found.pages)} pages, alpha {train._number(a.alpha)}, "
        f"reliability {train._number(found.ceiling)}. Every arm on the same pages and folds, "
        f"{train.REPEATS} shuffles of {train.FOLDS} folds.", "",
        *([f"Agreement within each set (alpha): {by_set}.", ""] if by_set else []),
        "| Arm | R² | Error | Nested kappa | Heavy pages caught |", "|---|---|---|---|---|"]
    for name, arm in found.arms.items():
        lines.append(f"| {LABELS[name]} | {arm.repeated.r2[0]:.3f} ± {arm.repeated.r2[1]:.3f} | "
                     f"{arm.repeated.mae[0]:.3f} ± {arm.repeated.mae[1]:.3f} | "
                     f"{arm.levels.nested_kappa:.3f} | {arm.heavy_caught:.0%} |")
    lines.append(f"| Predicting the training mean | {found.baseline.baseline_r2[0]:.3f} | "
                 f"{found.baseline.baseline_mae[0]:.3f} | | |")
    lines += ["", f"Lower error, new against old: {found.gain[0]:.3f}, 95% interval "
              f"{found.gain[1]:.3f} to {found.gain[2]:.3f}, pages resampled {BOOTSTRAPS} times.", ""]
    others = [(name, won) for name, won in found.gains.items() if name != "new"]
    if others:
        lines += ["Each other arm the same way, its error lower than old's: " + "; ".join(
            f"{LABELS[name].lower()} {won[0]:.3f} ({won[1]:.3f} to {won[2]:.3f})"
            for name, won in others) + ".", ""]
    if found.on_sites and found.sites is not None:
        lines += [f"On the {int(found.sites.sum())} Pakistani pages alone, held out in the same "
                  "folds as the whole:", "", "| Arm | R² | Error |", "|---|---|---|",
                  *[f"| {LABELS[name]} | {r2[0]:.3f} ± {r2[1]:.3f} | {mae[0]:.3f} ± {mae[1]:.3f} |"
                    for name, (r2, mae) in found.on_sites.items()], ""]
    if found.across:
        lines += ["Fitted on Sets 1 and 2 alone, tested on the Pakistani pages:", "",
                  "| Arm | Error | R² |", "|---|---|---|",
                  *[f"| {LABELS[name]} | {mae:.3f} | {r2:.3f} |"
                    for name, (mae, r2) in found.across.items()], ""]
    if found.steady:
        lines += [f"Without the pages drifted past {DRIFT_LIMIT:.0%} of the screen "
                  f"({found.steady_pages} of {len(found.pages)} left):", "",
                  "| Arm | R² | Error |", "|---|---|---|",
                  *[f"| {LABELS[name]} | {r2:.3f} | {mae:.3f} |"
                    for name, (r2, mae) in found.steady.items()], ""]
    if found.anchors:
        lines += ["Set 3's raters against those of Sets 1 and 2, on the same pictures:", "",
                  "| Anchor | Sets 1 and 2 (raters) | Set 3 (raters) |", "|---|---|---|",
                  *[f"| {u} [{st}] | {one:.2f} ({n}) | {three:.2f} ({m}) |"
                    for (u, st), (one, n, three, m) in found.anchors.items()], ""]
    shown = [name for name in IMPORTANCE_ARMS if name in found.importances]
    lines += ["Each feature's importance, held out: R² lost when it is shuffled, and its "
              "standardised coefficient, in each arm that has it. Sorted by the new model.", "",
              "| Feature | " + " | ".join(LABELS[name] for name in shown) + " |",
              "|---|" + "---|" * len(shown)]
    for feature, _ in sorted(found.importance.items(), key=lambda item: -item[1][0]):
        cells = []
        for name in shown:
            if feature in found.importances[name]:
                lost, sd, coefficient = found.importances[name][feature]
                cells.append(f"{lost:.3f} ± {sd:.3f}, {coefficient:+.3f}")
            else:
                cells.append("")
        lines.append(f"| `{feature}` | " + " | ".join(cells) + " |")
    lines += ["", "### The gate", "", "| Condition | Met | |", "|---|---|---|",
              *[f"| {check.says} | {'yes' if check.passed else '**no**'} | {check.detail} |"
                for check in found.verdict.checks], ""]
    lines.append(says(found.verdict))
    if found.left_out:
        lines += ["", f"Left out, {len(found.left_out)} pages: " + "; ".join(
            f"{u} [{st}]: {why}" for (u, st), why in found.left_out)]
    return "\n".join(lines) + "\n"


def says(verdict: Verdict) -> str:
    """The decision, in a sentence or two."""
    if verdict.better:
        return ("**The new model is better on held-out pages.** It is not live: the running "
                "app measures only the nine. `data/estimator.json` is unchanged, and going "
                "live needs the loop to measure the five, which all three owners decide.")
    failed = [check.says for check in verdict.checks if not check.passed]
    return ("**The old model stays.** `data/estimator.json` is unchanged. Not met: "
            + "; ".join(failed) + ".")


def run(paths: Paths, preview: bool = False, min_ratings: int = train.MIN_RATINGS
        ) -> Comparison:
    """The comparison, then the model and the report, each where it belongs. A
    preview stays in `.scratch/`, and a synthetic run is kept out of EVALUATION.md.
    `min_ratings` below eight is a person's choice, and the report says so."""
    pages = read_pages(paths)
    found = compare(train.read_ratings(paths.ratings), pages,
                    PREVIEW_MIN_RATINGS if preview else min_ratings, preview,
                    EFFORT["repeats"], EFFORT["nested"])
    candidate = paths.preview / "estimator_visual.json" if preview else paths.candidate
    save_candidate(found, candidate)
    section = report(found)
    if preview:
        paths.preview.mkdir(parents=True, exist_ok=True)
        (paths.preview / "report.md").write_text(section, encoding="utf-8")
        return found
    if found.synthetic and paths.evaluation.resolve() == train.EVALUATION.resolve():
        raise RefusedToTrain("refusing to write a synthetic result into EVALUATION.md.")
    with paths.evaluation.open("a", encoding="utf-8") as out:
        out.write("\n---\n\n" + section + f"\n```text\n{banner(conditions())}\n```\n")
    return found


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("csv", nargs="*", help="a form's responses, downloaded as CSV")
    parser.add_argument("--preview", action="store_true",
                        help="Sets 1 and 2 only, under the floor; writes only to .scratch/")
    parser.add_argument("--min-ratings", type=int, default=train.MIN_RATINGS,
                        help=f"compare with fewer than {train.MIN_RATINGS} ratings on a page; "
                             "named in the report, and the gate stays shut")
    parser.add_argument("--charts", type=Path, default=None, nargs="?", const=CHARTS,
                        help=f"draw the charts as SVG, by default into {CHARTS}")
    args = parser.parse_args()
    paths = Paths()
    if args.csv:
        from tools.rating import from_form
        try:
            print(from_form.summary(from_form.run([from_form.named(a) for a in args.csv])))
        except from_form.ConversionRefused as reason:
            print(f"Not converted: {reason}")
            raise SystemExit(2) from None
    try:
        found = run(paths, args.preview, args.min_ratings)
    except RefusedToTrain as reason:
        print(f"Not training: {reason}")
        raise SystemExit(2) from None
    print(report(found))
    if args.charts is not None:
        from tools.evaluation import visual_charts
        for drawn in visual_charts.write(found, args.charts):
            print(f"Drawn: {drawn}")
    # Here rather than at the top: it reads this module's paths.
    from tools.evaluation import rescore_index
    try:
        candidate = paths.preview / "estimator_visual.json" if args.preview else paths.candidate
        out = paths.preview / "overwhelm-index" if args.preview else rescore_index.OUT
        table = rescore_index.write_rescored(
            candidate, paths.visual, out, args.preview,
            by="new" if found.verdict.better else "live",
            people=rescore_index.people(paths.ratings, paths.set3))
    except rescore_index.Unscored as reason:
        print(f"The overwhelm index was not worked out again: {reason}")
        raise SystemExit(2) from None
    print(f"The overwhelm index again: {len(table)} sites, {out}.")


if __name__ == "__main__":
    main()
