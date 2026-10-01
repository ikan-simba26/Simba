"""Train the estimator on people's ratings of the corpus pages.

    python -m backend.estimator.train

Reads the page features (`data/corpus.json`) and the ratings people gave the
pictures of those pages (`data/ratings.jsonl`, written by `tools/rating`),
and does four things in order, stopping with a reason at the first one that
cannot be done honestly:

1. **Says how far the raters agree** before anything is fitted, because a
   model can only be as consistent as the people it learns from. Between
   raters: Krippendorff's alpha (interval) over every first showing, and each
   rater's Spearman correlation with the mean of the others, which picks out
   one rater who read the question differently. Within a rater: the two pages
   every session shows twice (`tools/rating/session.py`) — how far apart the
   two answers were.
2. **Averages the ratings per page.** A rater who saw a page twice has their
   two answers averaged first, so every rater counts once per page.
3. **Fits a ridge regression** from the page features to those averages, and
   reports what it is worth by 5-fold cross-validated R², next to the same
   number for predicting the training mean — the score a model has to beat to
   have learned anything. Permutation importance is measured on the held-out
   fold of each split, not on the pages the model was fitted to.
4. **Saves the model** (`data/estimator.joblib`) and **appends a results
   section to EVALUATION.md**.

**It refuses to train with fewer than ten raters.** Ten is a floor chosen for
this study on 2026-10-01, not a statistical cliff: the fewer the raters, the
more one person moves a page's average — an answer of 6 instead of 1 moves it
by 5/n points, a whole point with five raters and half with ten — and the less
their agreement can be told from chance. It also refuses with too few pages to fold, and
refuses ratings that mix synthetic rows with real ones.

**Synthetic ratings are never reported as a result.** Rows carrying
`"synthetic": true` — the tests make them — can be trained on, so the pipeline
is proven before real ratings exist, but everything built from them is marked
synthetic, and this refuses to write a synthetic model or report to the
project's own `data/estimator.joblib` or `EVALUATION.md`.

**Which features.** The nine raw features `page_features` measures, from the
**headless** rows of the corpus, because the pictures raters see are headless
captures (`tools/rating/capture.py`). Standardised before the fit, so the
ridge coefficients are comparable with each other.

**What it does not do.** It does not replace the provisional level rules; that
is a separate step, to be checked against the rules' logged decisions
(CLAUDE.md, current phase).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from scipy.stats import pearsonr, spearmanr
from sklearn.inspection import permutation_importance
from sklearn.linear_model import RidgeCV
from sklearn.metrics import r2_score
from sklearn.model_selection import KFold
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler

REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "data" / "corpus.json"
RATINGS = REPO / "data" / "ratings.jsonl"
MODEL = REPO / "data" / "estimator.joblib"
EVALUATION = REPO / "EVALUATION.md"

#: The nine raw features `page_features` measures, in its own order.
FEATURES: tuple[str, ...] = (
    "interactive", "links", "inferred", "text_density", "max_depth",
    "overlays", "form_fields", "dead_link_ratio", "reading_grade",
)
#: The pictures are headless captures, so the features are the headless rows.
ENVIRONMENT = "headless"
SCALE = (1, 7)
MIN_RATERS = 10
FOLDS = 5
#: Two pages per fold at the least, or a fold's R² is not a number.
MIN_PAGES = 2 * FOLDS
#: Searched inside each training fold by `RidgeCV`, never on the held-out one.
ALPHAS = tuple(float(a) for a in np.logspace(-2, 3, 26))
PERMUTATION_REPEATS = 50
SEED = 0


class RefusedToTrain(Exception):
    """The data cannot support a model, and the message says why."""


# --- reading --------------------------------------------------------------------


@dataclass(frozen=True)
class Rating:
    rater: int
    url: str
    state: str
    page: str
    repeat: bool
    rating: int
    synthetic: bool = False

    @property
    def key(self) -> tuple[str, str]:
        return (self.url, self.state)


def read_ratings(path: Path) -> list[Rating]:
    """Every answer in a `tools/rating` file. A malformed row stops the read:
    a model trained on rows this could not understand is not one to trust."""
    if not path.exists():
        raise RefusedToTrain(
            f"no ratings at {path}. Ratings come from `python -m tools.rating.serve`.")
    rows: list[Rating] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            rating = Rating(
                rater=int(row["rater"]), url=str(row["url"]), state=str(row["state"]),
                page=str(row.get("page", "")), repeat=bool(row.get("repeat", False)),
                rating=int(row["rating"]), synthetic=bool(row.get("synthetic", False)),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RefusedToTrain(f"{path}, line {number}, is not a rating: {error}") from error
        if not SCALE[0] <= rating.rating <= SCALE[1]:
            raise RefusedToTrain(
                f"{path}, line {number}: rating {rating.rating} is outside {SCALE[0]}-{SCALE[1]}")
        rows.append(rating)
    if not rows:
        raise RefusedToTrain(f"{path} has no ratings in it.")
    return rows


def read_corpus(path: Path, environment: str = ENVIRONMENT) -> tuple[dict, dict]:
    """The corpus rows for one environment, keyed by `(url, state)`, without
    the pages that failed to load; and the corpus's own conditions."""
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["results"][environment]
    usable = {(r["url"], r["state"]): r for r in rows if "error" not in r}
    return usable, data.get("conditions", {})


# --- agreement ------------------------------------------------------------------


def krippendorff_alpha_interval(units: list[list[float]]) -> float | None:
    """Krippendorff's alpha with the interval metric.

    `units` is one list of values per page — whatever raters gave it, any
    number of them. Pages with fewer than two values say nothing about
    agreement and are left out, which is what the measure is for: it does not
    need every rater to have rated every page. None when there is nothing to
    compare or every value is the same.
    """
    pairable = [np.asarray(u, dtype=float) for u in units if len(u) >= 2]
    if not pairable:
        return None
    n = sum(len(u) for u in pairable)
    observed = sum(
        float(((u[:, None] - u[None, :]) ** 2).sum()) / (len(u) - 1) for u in pairable
    ) / n
    values = np.concatenate(pairable)
    expected = float(((values[:, None] - values[None, :]) ** 2).sum()) / (n * (n - 1))
    if expected == 0:
        return None
    return 1.0 - observed / expected


@dataclass
class Agreement:
    raters: int
    pages: int
    #: Between raters, over first showings.
    alpha: float | None
    #: Each rater against the mean of everyone else, on the pages both rated.
    rater_vs_rest: dict[int, float | None]
    #: Within a rater: one `(first, repeat)` pair per repeated page.
    repeat_pairs: list[tuple[int, int]]

    @property
    def repeat_mean_difference(self) -> float | None:
        if not self.repeat_pairs:
            return None
        return float(np.mean([abs(a - b) for a, b in self.repeat_pairs]))

    @property
    def repeat_identical(self) -> float | None:
        if not self.repeat_pairs:
            return None
        return float(np.mean([a == b for a, b in self.repeat_pairs]))

    @property
    def repeat_within_one(self) -> float | None:
        if not self.repeat_pairs:
            return None
        return float(np.mean([abs(a - b) <= 1 for a, b in self.repeat_pairs]))

    @property
    def repeat_correlation(self) -> float | None:
        if len(self.repeat_pairs) < 3:
            return None
        first, second = zip(*self.repeat_pairs)
        if len(set(first)) < 2 or len(set(second)) < 2:
            return None
        return float(pearsonr(first, second)[0])


def agreement(ratings: list[Rating]) -> Agreement:
    first = [r for r in ratings if not r.repeat]
    by_page: dict[tuple[str, str], dict[int, int]] = {}
    for r in first:
        by_page.setdefault(r.key, {})[r.rater] = r.rating

    alpha = krippendorff_alpha_interval([list(v.values()) for v in by_page.values()])

    rater_vs_rest: dict[int, float | None] = {}
    for rater in sorted({r.rater for r in first}):
        mine, theirs = [], []
        for given in by_page.values():
            others = [v for k, v in given.items() if k != rater]
            if rater in given and others:
                mine.append(given[rater])
                theirs.append(float(np.mean(others)))
        ok = len(mine) >= 3 and len(set(mine)) > 1 and len(set(theirs)) > 1
        rater_vs_rest[rater] = float(spearmanr(mine, theirs)[0]) if ok else None

    first_of = {(r.rater, r.key): r.rating for r in first}
    pairs = [(first_of[(r.rater, r.key)], r.rating)
             for r in ratings if r.repeat and (r.rater, r.key) in first_of]

    return Agreement(raters=len({r.rater for r in ratings}), pages=len(by_page),
                     alpha=alpha, rater_vs_rest=rater_vs_rest, repeat_pairs=pairs)


# --- averaging ------------------------------------------------------------------


def page_means(ratings: list[Rating]) -> dict[tuple[str, str], tuple[float, int]]:
    """Each page's mean rating and how many raters it rests on.

    A rater's answers to one page are averaged first — the repeat is the same
    person asked again, not a second person — so every rater counts once.
    """
    per_rater: dict[tuple[str, str], dict[int, list[int]]] = {}
    for r in ratings:
        per_rater.setdefault(r.key, {}).setdefault(r.rater, []).append(r.rating)
    return {
        key: (float(np.mean([np.mean(v) for v in raters.values()])), len(raters))
        for key, raters in per_rater.items()
    }


# --- training -------------------------------------------------------------------


@dataclass
class Trained:
    synthetic: bool
    agreement: Agreement
    pages: list[tuple[str, str]]
    #: Rated pages the corpus could not supply features for.
    unmatched: list[tuple[str, str]]
    fold_r2: list[float]
    baseline_r2: list[float]
    #: Feature -> (mean, standard deviation) of the R² lost when it is shuffled,
    #: over every held-out fold and repeat.
    importance: dict[str, tuple[float, float]]
    #: Feature -> standardised coefficient of the model fitted on every page.
    coefficients: dict[str, float]
    alpha: float
    model: Pipeline
    sources: dict[str, Any] = field(default_factory=dict)

    @property
    def r2(self) -> tuple[float, float]:
        return float(np.mean(self.fold_r2)), float(np.std(self.fold_r2))

    @property
    def baseline(self) -> tuple[float, float]:
        return float(np.mean(self.baseline_r2)), float(np.std(self.baseline_r2))


def _model() -> Pipeline:
    return make_pipeline(StandardScaler(), RidgeCV(alphas=ALPHAS))


def train(ratings: list[Rating], corpus: dict, min_raters: int = MIN_RATERS) -> Trained:
    """Everything above, in order. Raises `RefusedToTrain` with the reason."""
    synthetic = {r.synthetic for r in ratings}
    if synthetic == {True, False}:
        raise RefusedToTrain(
            "the ratings mix synthetic rows with real ones. A model built from both "
            "is neither a test of the pipeline nor a result; separate them.")
    is_synthetic = synthetic == {True}

    raters = {r.rater for r in ratings}
    if len(raters) < min_raters:
        raise RefusedToTrain(
            f"only {len(raters)} rater{'s' if len(raters) != 1 else ''} "
            f"({', '.join(str(r) for r in sorted(raters))}); training needs at least "
            f"{min_raters}, the floor set for this study. With few raters one person "
            f"carries a page's average — an answer of 6 instead of 1 moves it by "
            f"{5 / len(raters):.2f} points here — and agreement between them cannot "
            f"be told from chance. Collect more ratings with `python -m "
            f"tools.rating.serve`.")

    found = agreement(ratings)
    means = page_means(ratings)
    pages = sorted(k for k in means if k in corpus)
    unmatched = sorted(k for k in means if k not in corpus)
    if len(pages) < MIN_PAGES:
        raise RefusedToTrain(
            f"only {len(pages)} rated pages have features in the corpus; {FOLDS}-fold "
            f"cross-validation needs at least {MIN_PAGES}.")

    x = np.array([[float(corpus[k][f]) for f in FEATURES] for k in pages])
    y = np.array([means[k][0] for k in pages])

    folds = KFold(n_splits=FOLDS, shuffle=True, random_state=SEED)
    fold_r2, baseline_r2 = [], []
    lost: dict[str, list[float]] = {f: [] for f in FEATURES}
    for train_index, test_index in folds.split(x):
        model = _model().fit(x[train_index], y[train_index])
        fold_r2.append(float(r2_score(y[test_index], model.predict(x[test_index]))))
        baseline = np.full(len(test_index), y[train_index].mean())
        baseline_r2.append(float(r2_score(y[test_index], baseline)))
        # On the held-out fold: how much worse the model does there when one
        # feature's values are shuffled. Measured on pages it was fitted to,
        # this would reward whatever it had memorised.
        result = permutation_importance(
            model, x[test_index], y[test_index], scoring="r2",
            n_repeats=PERMUTATION_REPEATS, random_state=SEED)
        for index, name in enumerate(FEATURES):
            lost[name].extend(float(v) for v in result.importances[index])

    final = _model().fit(x, y)
    ridge: RidgeCV = final[-1]
    return Trained(
        synthetic=is_synthetic, agreement=found, pages=pages, unmatched=unmatched,
        fold_r2=fold_r2, baseline_r2=baseline_r2,
        importance={f: (float(np.mean(v)), float(np.std(v))) for f, v in lost.items()},
        coefficients={f: float(c) for f, c in zip(FEATURES, ridge.coef_)},
        alpha=float(ridge.alpha_), model=final,
    )


# --- writing --------------------------------------------------------------------


def _is_the_projects(path: Path, own: Path) -> bool:
    return path.resolve() == own.resolve()


def save_model(trained: Trained, path: Path = MODEL) -> None:
    """The fitted pipeline and what it was fitted on. A synthetic model is
    never written to the project's own model path."""
    if trained.synthetic and _is_the_projects(path, MODEL):
        raise RefusedToTrain(
            f"refusing to save a model trained on synthetic ratings to {MODEL}: "
            f"that is where the real estimator lives.")
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "model": trained.model,
        "features": FEATURES,
        "environment": ENVIRONMENT,
        "synthetic": trained.synthetic,
        "raters": trained.agreement.raters,
        "pages": trained.pages,
        "cv_r2": trained.r2,
        "trained_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "sources": trained.sources,
    }, path)


def _number(value: float | None, places: int = 3) -> str:
    return "—" if value is None or (isinstance(value, float) and math.isnan(value)) \
        else f"{value:.{places}f}"


def _commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], cwd=REPO,
                             capture_output=True, text=True, timeout=10)
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=REPO,
                               capture_output=True, text=True, timeout=10).stdout.strip()
        return out.stdout.strip() + (" (dirty tree)" if dirty else "")
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def report(trained: Trained, when: datetime | None = None) -> str:
    """The EVALUATION.md section for one training run."""
    when = when or datetime.now().astimezone()
    a = trained.agreement
    r2, r2_sd = trained.r2
    base, base_sd = trained.baseline
    title = (f"## {when:%Y-%m-%d} — the estimator, trained on {a.raters} raters' ratings")
    lines = [title, ""]
    if trained.synthetic:
        lines += [
            "**SYNTHETIC — a test of the pipeline, not a result.** Every rating below "
            "was generated, not given by a person. Nothing here says anything about "
            "how overwhelming a page is.", ""]
    s = trained.sources
    lines += [
        f"`python -m backend.estimator.train` at `{s.get('commit', 'unknown')}`. "
        f"Ratings: `{s.get('ratings', '?')}`, {s.get('rows', '?')} rows, sha256 "
        f"`{str(s.get('ratings_sha256', ''))[:12]}`. Features: the {ENVIRONMENT} rows of "
        f"`{s.get('corpus', '?')}`, collected {s.get('corpus_taken_at', '?')}. "
        f"Model: `{s.get('model', '?')}`.", "",
        "### How far the raters agree", "",
        "| | |", "|---|---|",
        f"| Raters | {a.raters} |",
        f"| Pages rated | {a.pages} |",
        f"| Krippendorff's alpha (interval), first showings | {_number(a.alpha)} |",
        f"| Repeated pages: pairs | {len(a.repeat_pairs)} |",
        f"| Repeated pages: mean difference | {_number(a.repeat_mean_difference, 2)} |",
        f"| Repeated pages: identical / within one | "
        f"{_number(a.repeat_identical, 2)} / {_number(a.repeat_within_one, 2)} |",
        f"| Repeated pages: correlation | {_number(a.repeat_correlation)} |", "",
        "Each rater against the mean of the others (Spearman):", "",
        "| Rater | ρ |", "|---|---|",
        *[f"| {rater} | {_number(rho)} |" for rater, rho in a.rater_vs_rest.items()], "",
        "### The model", "",
        f"Ridge regression on the nine features, standardised; alpha chosen inside "
        f"each training fold from {len(ALPHAS)} values, {ALPHAS[0]:g}–{ALPHAS[-1]:g}; "
        f"{trained.alpha:g} on all {len(trained.pages)} pages.", "",
        "| | R², 5-fold, mean ± sd | Folds |", "|---|---|---|",
        f"| Ridge | **{r2:.3f} ± {r2_sd:.3f}** | "
        f"{', '.join(f'{v:.2f}' for v in trained.fold_r2)} |",
        f"| Predicting the training mean | {base:.3f} ± {base_sd:.3f} | "
        f"{', '.join(f'{v:.2f}' for v in trained.baseline_r2)} |", "",
        f"Permutation importance on the held-out fold of each split, "
        f"{PERMUTATION_REPEATS} shuffles each: the R² lost when one feature is shuffled.", "",
        "| Feature | R² lost, mean ± sd | Coefficient (standardised) |", "|---|---|---|",
    ]
    ranked = sorted(FEATURES, key=lambda f: trained.importance[f][0], reverse=True)
    lines += [f"| `{f}` | {trained.importance[f][0]:.3f} ± {trained.importance[f][1]:.3f} | "
              f"{trained.coefficients[f]:+.3f} |" for f in ranked]
    if trained.unmatched:
        lines += ["", f"**{len(trained.unmatched)} rated pages had no {ENVIRONMENT} features** "
                  "and were left out: " + ", ".join(f"{u} [{s}]" for u, s in trained.unmatched)]
    return "\n".join(lines) + "\n"


def write_evaluation(trained: Trained, path: Path = EVALUATION) -> str:
    """Append the section. A synthetic run is never appended to the project's
    own EVALUATION.md."""
    if trained.synthetic and _is_the_projects(path, EVALUATION):
        raise RefusedToTrain(
            f"refusing to write a synthetic result into {EVALUATION}: a synthetic run "
            f"proves the pipeline, and is not a result anyone should read as one.")
    section = report(trained)
    with path.open("a", encoding="utf-8") as out:
        out.write("\n---\n\n" + section)
    return section


def run(ratings_path: Path = RATINGS, corpus_path: Path = CORPUS, model_path: Path = MODEL,
        evaluation_path: Path = EVALUATION, environment: str = ENVIRONMENT) -> Trained:
    ratings = read_ratings(ratings_path)
    corpus, corpus_conditions = read_corpus(corpus_path, environment)
    trained = train(ratings, corpus)
    trained.sources = {
        "commit": _commit(),
        "ratings": str(ratings_path.relative_to(REPO)) if ratings_path.is_relative_to(REPO)
        else str(ratings_path),
        "rows": len(ratings),
        "ratings_sha256": hashlib.sha256(ratings_path.read_bytes()).hexdigest(),
        "corpus": str(corpus_path.relative_to(REPO)) if corpus_path.is_relative_to(REPO)
        else str(corpus_path),
        "corpus_taken_at": corpus_conditions.get("taken_at", "?"),
        "model": str(model_path.relative_to(REPO)) if model_path.is_relative_to(REPO)
        else str(model_path),
    }
    save_model(trained, model_path)
    write_evaluation(trained, evaluation_path)
    return trained


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--ratings", type=Path, default=RATINGS)
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument("--model", type=Path, default=MODEL)
    parser.add_argument("--evaluation", type=Path, default=EVALUATION)
    args = parser.parse_args()
    try:
        trained = run(args.ratings, args.corpus, args.model, args.evaluation)
    except RefusedToTrain as reason:
        print(f"Not training: {reason}")
        raise SystemExit(2) from None
    print(report(trained))
    print(f"Saved {args.model}; appended to {args.evaluation}.")


if __name__ == "__main__":
    main()
