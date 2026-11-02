"""Train the estimator on people's ratings of the corpus pages.

    python -m backend.estimator.train

Reads the page features (`data/corpus.json`) and the ratings people gave the
pictures of those pages (`data/ratings.jsonl`, written by `tools/rating`),
and does five things in order, stopping with a reason at the first one that
cannot be done honestly:

1. **Says how far the raters agree** before anything is fitted, because a
   model can only be as consistent as the people it learns from. **Each rater
   rates only some pages** — one of two sets of 30 (`tools/rating/session.py`,
   DECISIONS.md, *Two sets of 30*) — so every measure here works on whatever
   each page has and never needs a full table. Between raters: Krippendorff's
   alpha (interval) over every first showing, which is built for missing
   values, overall and within each set; and each rater's Spearman correlation
   with the mean of the others on the pages that rater rated, which picks out
   one rater who read the question differently. **Between the two groups**:
   the six anchor pages both sets show — each group's mean on each, and each
   rater's own mean over them, Set 1's raters against Set 2's
   (Mann–Whitney U) — so a group that rates everything higher is seen before
   its pages are averaged with the other's. Within a rater: the two pages
   every session shows twice — how far apart the two answers were.
2. **Averages the ratings per page.** A rater who saw a page twice has their
   two answers averaged first, so every rater counts once per page.
3. **Fits a ridge regression** from the page features to those averages, and
   reports what it is worth by 5-fold cross-validated R², next to the same
   number for predicting the training mean — the score a model has to beat to
   have learned anything. Permutation importance is measured on the held-out
   fold of each split, not on the pages the model was fitted to.
4. **Chooses where the score changes the detail level** (`choose_cuts`), on
   held-out scores. A fitted score spreads wider than a score on a page the
   model has not seen, so cut points read off the fitted scores, or off the
   rating scale itself, would rarely fire on a new page.
5. **Saves the model** (`data/estimator.joblib`, and the same numbers as plain
   JSON in `data/estimator.json`, which is the file the running app reads:
   `page_model.py`) and **appends a results section to EVALUATION.md**.

**It refuses to train until every page has at least eight ratings** — eight
raters, each counted once however often they saw the page (2026-10-23; until
then the floor was ten raters overall, when every rater rated every page).
Eight is a floor chosen for this study, not a statistical cliff: the fewer
the ratings, the more one person moves a page's average — an answer of 5
instead of 1 moves it by 4/n points, half a point with eight — and the less
agreement can be told from chance. When it refuses it says how many more
ratings are needed in all, and, from the sets in `data/rating/form.json`, how
many more raters of each set. The pages counted are the ones that can be
trained on: a picture current in the manifest, with features from its run.
It also refuses with too few pages to fold, and refuses ratings that mix
synthetic rows with real ones.

**The floor can be lowered for one run, and it says so** (2026-10-30):
`--min-ratings 5` trains on what there is. The default stays eight; a run
under it names every page below eight in its EVALUATION.md section, and the
saved model carries the count, so a model from fewer ratings can never pass for
one that met the floor. Retrained with enough ratings, the flag goes.

**Synthetic ratings are never reported as a result.** Rows carrying
`"synthetic": true` — the tests make them — can be trained on, so the pipeline
is proven before real ratings exist, but everything built from them is marked
synthetic, and this refuses to write a synthetic model or report to the
project's own `data/estimator.joblib` or `EVALUATION.md`.

**Which features.** The nine raw features `page_features` measures, from the
**headless** rows of the corpus, because the pictures raters see are headless
captures (`tools/rating/capture.py`). Standardised before the fit, so the
ridge coefficients are comparable with each other.

**Each rating is paired with the features of the picture it was given for.**
Since 2026-10-03 the pictures and the corpus are captured in one run, from one
load per page, and both carry the run's id. A rating is used only if the
picture it was given for is the one in the manifest now (`image_sha256`), and
only if that picture and the page's corpus row came from the same run; the
rest are left out and listed, with why.

**What it does not do.** It does not say how the level moves in a run: that is
`rules.py`, which reads `data/estimator.json` through `page_model.py`, and
`tools/evaluation/estimator_compare.py` holds the model against the rules.
`python -m tools.rating.retrain` runs the converter, this and that comparison
as one command (RUNNING.md).
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
from scipy.stats import mannwhitneyu, pearsonr, spearmanr
from sklearn.inspection import permutation_importance
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler

from tools.evaluation.conditions import banner, conditions

REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "data" / "corpus.json"
RATINGS = REPO / "data" / "ratings.jsonl"
MODEL = REPO / "data" / "estimator.joblib"
#: The same model as plain numbers: what the running app reads (`page_model.py`).
COEFFICIENTS = REPO / "data" / "estimator.json"
PICTURES = REPO / "data" / "rating" / "pages.json"
#: The two sets the rating forms show (`tools/rating/export_form.py`).
DESIGN = REPO / "data" / "rating" / "form.json"
EVALUATION = REPO / "EVALUATION.md"

#: The nine raw features `page_features` measures, in its own order.
FEATURES: tuple[str, ...] = (
    "interactive", "links", "inferred", "text_density", "max_depth",
    "overlays", "form_fields", "dead_link_ratio", "reading_grade",
)
#: The pictures are headless captures, so the features are the headless rows.
ENVIRONMENT = "headless"
SCALE = (1, 5)
#: Ratings every page needs, each from a different rater.
MIN_RATINGS = 8
#: Anchor means further apart than this, between the two groups, are reported
#: as the groups not rating alike: an eighth of the 1-5 scale.
GROUPS_DIFFER = 0.5
FOLDS = 5
#: Two pages per fold at the least, or a fold's R² is not a number.
MIN_PAGES = 2 * FOLDS
#: Searched inside each training fold by `RidgeCV`, never on the held-out one.
ALPHAS = tuple(float(a) for a in np.logspace(-2, 3, 26))
PERMUTATION_REPEATS = 50
SEED = 0
#: Where the form's own words divide a page's mean rating: nearest "Not at all"
#: or "A little", nearest "Somewhat", nearest "Very" or "Extremely". Fixed, so
#: one retraining can be compared with the next; `natural_breaks` checks them
#: against where the ratings themselves divide.
BANDS = (2.5, 3.5)
#: Shuffles of the five folds. One split of 50 pages into five is a small
#: sample of the possible splits: each is a different ten held-out pages.
REPEATS = 40
#: The score cut points tried, on the 1-5 scale.
CUT_GRID = tuple(round(float(v), 2) for v in np.arange(1.5, 4.51, 0.05))
#: Random halvings of each page's raters, for the ceiling.
SPLITS = 500


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
    #: The sha256 of the picture this answer was given for (`tools/rating/serve.py`).
    image: str = ""
    #: Which of the two sets the rater rated; None on a row from before sets.
    set: int | None = None

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
                image=str(row.get("image_sha256", "")),
                set=int(row["set"]) if row.get("set") is not None else None,
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


def read_pictures(path: Path) -> dict:
    """The rating manifest's pictures, keyed by `(url, state)`."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return {(r["url"], r["state"]): r for r in data["pages"] if "error" not in r}


def read_design(path: Path) -> dict[tuple[str, str], set[int]]:
    """Each page's sets, keyed by `(url, state)`: one set for most pages, both
    for an anchor. Empty when the file is missing or has no sets."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    pictures = data.get("pictures", {})
    shown: dict[tuple[str, str], set[int]] = {}
    for key, chosen in data.get("sets", {}).items():
        for name in chosen["own"] + chosen["anchors"]:
            picture = pictures[name]
            shown.setdefault((picture["url"], picture["state"]), set()).add(int(key))
    return shown


def paired(ratings: list[Rating], corpus: dict, pictures: dict
           ) -> tuple[list[Rating], list[tuple[tuple[str, str], str]]]:
    """The ratings whose picture is current and whose features were read from
    the same load as it; and every page left out, with why."""
    kept: list[Rating] = []
    left_out: dict[tuple[str, str], str] = {}
    for rating in ratings:
        picture = pictures.get(rating.key)
        features = corpus.get(rating.key)
        if picture is None:
            left_out.setdefault(rating.key, "not in the picture manifest")
        elif rating.image and rating.image != picture.get("sha256"):
            left_out.setdefault(rating.key, "rated an earlier picture than the one captured now")
        elif features is not None and features.get("run") != picture.get("run"):
            left_out.setdefault(rating.key, "the picture and the features are from different "
                                f"capture runs ({picture.get('run')} and {features.get('run')})")
        else:
            kept.append(rating)
    return kept, sorted(left_out.items())


def trainable(corpus: dict, pictures: dict | None) -> list[tuple[str, str]]:
    """The pages a model can be trained on: with `pictures`, those with a
    current picture and features from its run; without, every corpus page."""
    if pictures is None:
        return sorted(corpus)
    return sorted(k for k, picture in pictures.items()
                  if k in corpus and corpus[k].get("run") == picture.get("run"))


# --- how many ratings ------------------------------------------------------------


def ratings_per_page(ratings: list[Rating]) -> dict[tuple[str, str], int]:
    """How many raters rated each page, each counted once."""
    raters: dict[tuple[str, str], set[int]] = {}
    for r in ratings:
        raters.setdefault(r.key, set()).add(r.rater)
    return {key: len(who) for key, who in raters.items()}


@dataclass
class Shortfall:
    """How far the ratings are from `MIN_RATINGS` on every page that needs them."""

    minimum: int
    #: Page -> ratings it has, for every page that needs them, rated or not.
    counts: dict[tuple[str, str], int]
    #: Set -> how many more raters of that set it takes to bring every page
    #: shown only in that set to the minimum. Empty without a design.
    raters_by_set: dict[int, int] = field(default_factory=dict)

    @property
    def short(self) -> dict[tuple[str, str], int]:
        """Page -> how many more ratings it needs, for the pages below the minimum."""
        return {k: self.minimum - n for k, n in self.counts.items() if n < self.minimum}

    @property
    def needed(self) -> int:
        return sum(self.short.values())

    def says(self) -> str:
        """In words: enough, or how many more, where."""
        if not self.short:
            low = min(self.counts.values(), default=0)
            return (f"every one of {len(self.counts)} pages has at least {self.minimum} "
                    f"ratings (the fewest: {low}).")
        text = (f"{len(self.short)} of {len(self.counts)} pages have fewer than "
                f"{self.minimum} ratings; {self.needed} more ratings are needed in all")
        if self.raters_by_set:
            more = [f"{n} more Set {s} rater{'s' if n != 1 else ''}"
                    for s, n in sorted(self.raters_by_set.items()) if n > 0]
            text += (f" — at least {' and '.join(more)}, each rating every page of "
                     f"their set once" if more else "")
        return text + "."


def shortfall(ratings: list[Rating], pages: list[tuple[str, str]],
              design: dict[tuple[str, str], set[int]] | None = None,
              minimum: int = MIN_RATINGS) -> Shortfall:
    """How many more ratings `pages` need, and with `design`, how many more
    raters of each set. A page shown in both sets (an anchor) gets ratings from
    both, so the raters a set needs are counted on its own pages only."""
    counts = ratings_per_page(ratings)
    found = Shortfall(minimum=minimum, counts={k: counts.get(k, 0) for k in pages})
    if design:
        for s in sorted({s for sets in design.values() for s in sets}):
            own = [k for k in pages if design.get(k) == {s}]
            found.raters_by_set[s] = max([0] + [minimum - found.counts[k] for k in own])
    return found


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
class Groups:
    """The two sets' raters, compared on the pages both rated (the anchors)."""

    #: Anchor -> (Set 1's mean, its raters, Set 2's mean, its raters).
    anchors: dict[tuple[str, str], tuple[float, int, float, int]]
    #: Set -> each of its raters' mean over the anchors they rated.
    rater_means: dict[int, list[float]]
    #: Mann–Whitney U, two-sided, on those rater means; None with too few.
    p_value: float | None

    @property
    def difference(self) -> float | None:
        """Set 2's mean minus Set 1's, averaged over the anchors."""
        if not self.anchors:
            return None
        return float(np.mean([b - a for a, _, b, _ in self.anchors.values()]))

    @property
    def alike(self) -> bool | None:
        """Whether the groups rate alike: within `GROUPS_DIFFER` on average,
        and not told apart by the test at 0.05. None with no anchors."""
        if self.difference is None:
            return None
        return abs(self.difference) < GROUPS_DIFFER and (
            self.p_value is None or self.p_value >= 0.05)


def groups(ratings: list[Rating]) -> Groups | None:
    """Set 1 against Set 2 on the pages raters of both rated, first showings
    only. None unless the ratings carry exactly two sets."""
    first = [r for r in ratings if not r.repeat and r.set is not None]
    # Set 3 shares only three pages with them, and `train_visual` compares it.
    sets = sorted({r.set for r in first} - {3})
    if len(sets) != 2:
        return None
    one, two = sets
    first = [r for r in first if r.set in sets]
    by_page: dict[tuple[str, str], dict[int, list[int]]] = {}
    for r in first:
        by_page.setdefault(r.key, {}).setdefault(r.set, []).append(r.rating)
    anchors = {key: (float(np.mean(given[one])), len(given[one]),
                     float(np.mean(given[two])), len(given[two]))
               for key, given in sorted(by_page.items()) if one in given and two in given}
    per_rater: dict[tuple[int, int], list[int]] = {}
    for r in first:
        if r.key in anchors:
            per_rater.setdefault((r.set, r.rater), []).append(r.rating)
    rater_means = {s: [float(np.mean(v)) for (rs, _), v in sorted(per_rater.items()) if rs == s]
                   for s in sets}
    p_value = None
    if all(len(v) >= 3 for v in rater_means.values()) \
            and len(set(rater_means[one] + rater_means[two])) > 1:
        p_value = float(mannwhitneyu(rater_means[one], rater_means[two],
                                     alternative="two-sided").pvalue)
    return Groups(anchors=anchors, rater_means=rater_means, p_value=p_value)


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
    #: Set -> alpha among that set's raters alone.
    alpha_by_set: dict[int, float | None] = field(default_factory=dict)
    #: Set -> its raters.
    raters_by_set: dict[int, int] = field(default_factory=dict)
    #: Set 1's raters against Set 2's on the anchors; None without two sets.
    groups: Groups | None = None

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

    alpha_by_set: dict[int, float | None] = {}
    raters_by_set: dict[int, int] = {}
    for s in sorted({r.set for r in first if r.set is not None}):
        within: dict[tuple[str, str], list[int]] = {}
        for r in first:
            if r.set == s:
                within.setdefault(r.key, []).append(r.rating)
        alpha_by_set[s] = krippendorff_alpha_interval(list(within.values()))
        raters_by_set[s] = len({r.rater for r in first if r.set == s})

    return Agreement(raters=len({r.rater for r in ratings}), pages=len(by_page),
                     alpha=alpha, rater_vs_rest=rater_vs_rest, repeat_pairs=pairs,
                     alpha_by_set=alpha_by_set, raters_by_set=raters_by_set,
                     groups=groups(ratings))


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
    #: Rated pages some of whose ratings were left out because picture,
    #: rating and features did not pair, and why.
    unpaired: list[tuple[tuple[str, str], str]]
    fold_r2: list[float]
    baseline_r2: list[float]
    #: Feature -> (mean, standard deviation) of the R² lost when it is shuffled,
    #: over every held-out fold and repeat.
    importance: dict[str, tuple[float, float]]
    #: Feature -> standardised coefficient of the model fitted on every page.
    coefficients: dict[str, float]
    alpha: float
    model: Pipeline
    #: Ratings per page against the floor this run was given.
    coverage: Shortfall | None = None
    sources: dict[str, Any] = field(default_factory=dict)
    #: The floor this run was given; below `MIN_RATINGS` only when asked for.
    min_ratings: int = MIN_RATINGS
    #: Error on each held-out fold, and the same for predicting the training
    #: mean, in points of the 1-5 scale.
    fold_mae: list[float] = field(default_factory=list)
    fold_rmse: list[float] = field(default_factory=list)
    baseline_mae: list[float] = field(default_factory=list)
    baseline_rmse: list[float] = field(default_factory=list)
    #: The features and the mean ratings, row by row with `pages`.
    x: np.ndarray | None = None
    y: np.ndarray | None = None
    #: Set by `run`: what the luck of the folds is worth, and the cuts.
    repeated: Repeated | None = None
    levels: Levels | None = None
    #: How far the page means can be predicted at all (`reliability`).
    ceiling: float | None = None

    @property
    def r2(self) -> tuple[float, float]:
        return float(np.mean(self.fold_r2)), float(np.std(self.fold_r2))

    @property
    def baseline(self) -> tuple[float, float]:
        return float(np.mean(self.baseline_r2)), float(np.std(self.baseline_r2))

    @property
    def below_floor(self) -> list[tuple[str, str]]:
        """The pages trained on with fewer than `MIN_RATINGS` ratings."""
        counts = self.coverage.counts if self.coverage else {}
        return sorted(k for k, n in counts.items() if n < MIN_RATINGS)


def _model() -> Pipeline:
    return make_pipeline(StandardScaler(), RidgeCV(alphas=ALPHAS))


def train(ratings: list[Rating], corpus: dict, min_ratings: int = MIN_RATINGS,
          pictures: dict | None = None,
          design: dict[tuple[str, str], set[int]] | None = None) -> Trained:
    """Everything above, in order. Raises `RefusedToTrain` with the reason.

    With `pictures`, ratings are first paired with them (`paired`); the
    ratings counted afterwards are the ones that paired. `design` (each
    page's sets, `read_design`) lets a refusal say how many more raters of
    each set it takes."""
    unpaired: list[tuple[tuple[str, str], str]] = []
    if pictures is not None:
        ratings, unpaired = paired(ratings, corpus, pictures)
        if not ratings:
            raise RefusedToTrain(
                "no rating pairs with a current picture and features from its run: "
                + "; ".join(f"{k[0]} [{k[1]}]: {why}" for k, why in unpaired[:5]))
    synthetic = {r.synthetic for r in ratings}
    if synthetic == {True, False}:
        raise RefusedToTrain(
            "the ratings mix synthetic rows with real ones. A model built from both "
            "is neither a test of the pipeline nor a result; separate them.")
    is_synthetic = synthetic == {True}

    coverage = shortfall(ratings, trainable(corpus, pictures), design, min_ratings)
    if coverage.short:
        low = min(coverage.counts.values(), default=0)
        raise RefusedToTrain(
            f"{coverage.says()} Training needs at least {min_ratings} ratings on every "
            f"page, the floor set for this study. With few ratings one person carries "
            f"a page's average — an answer of {SCALE[1]} instead of {SCALE[0]} moves it "
            f"by {(SCALE[1] - SCALE[0]) / max(1, low):.2f} points on the page with the "
            f"fewest here — and agreement cannot be told from chance. Collect more "
            f"ratings with the forms (`tools/rating/form/README.md`) or `python -m "
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
    fold_mae, fold_rmse, baseline_mae, baseline_rmse = [], [], [], []
    lost: dict[str, list[float]] = {f: [] for f in FEATURES}
    for train_index, test_index in folds.split(x):
        model = _model().fit(x[train_index], y[train_index])
        predicted = model.predict(x[test_index])
        fold_r2.append(float(r2_score(y[test_index], predicted)))
        baseline = np.full(len(test_index), y[train_index].mean())
        baseline_r2.append(float(r2_score(y[test_index], baseline)))
        fold_mae.append(float(mean_absolute_error(y[test_index], predicted)))
        fold_rmse.append(float(np.sqrt(mean_squared_error(y[test_index], predicted))))
        baseline_mae.append(float(mean_absolute_error(y[test_index], baseline)))
        baseline_rmse.append(float(np.sqrt(mean_squared_error(y[test_index], baseline))))
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
        unpaired=unpaired,
        fold_r2=fold_r2, baseline_r2=baseline_r2,
        importance={f: (float(np.mean(v)), float(np.std(v))) for f, v in lost.items()},
        coefficients={f: float(c) for f, c in zip(FEATURES, ridge.coef_)},
        alpha=float(ridge.alpha_), model=final, coverage=coverage, min_ratings=min_ratings,
        fold_mae=fold_mae, fold_rmse=fold_rmse, baseline_mae=baseline_mae,
        baseline_rmse=baseline_rmse, x=x, y=y,
    )


# --- held out, and from a score to a level ------------------------------------------


@dataclass
class Repeated:
    """Pooled held-out figures over `REPEATS` shuffles of the five folds: the
    mean and standard deviation of each measure, for the model and for
    predicting the training mean."""

    r2: tuple[float, float]
    mae: tuple[float, float]
    rmse: tuple[float, float]
    baseline_r2: tuple[float, float]
    baseline_mae: tuple[float, float]
    baseline_rmse: tuple[float, float]


def held_out_predictions(x: np.ndarray, y: np.ndarray, repeats: int = REPEATS,
                         seed: int = SEED) -> tuple[np.ndarray, np.ndarray]:
    """One row per shuffle of the folds. Every page is predicted once in each,
    by a model that never saw it; the second array is the same for predicting
    the training mean. Clipped to the scale, as the running app clips."""
    predicted = np.zeros((repeats, len(y)))
    baseline = np.zeros((repeats, len(y)))
    for repeat in range(repeats):
        folds = KFold(n_splits=FOLDS, shuffle=True, random_state=seed + repeat)
        for train_index, test_index in folds.split(x):
            model = _model().fit(x[train_index], y[train_index])
            predicted[repeat, test_index] = model.predict(x[test_index])
            baseline[repeat, test_index] = y[train_index].mean()
    return np.clip(predicted, *SCALE), baseline


def repeated(y: np.ndarray, predicted: np.ndarray, baseline: np.ndarray) -> Repeated:
    def spread(metric: Any, rows: np.ndarray) -> tuple[float, float]:
        values = [float(metric(y, row)) for row in rows]
        return float(np.mean(values)), float(np.std(values))

    def rmse(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.sqrt(mean_squared_error(a, b)))

    return Repeated(r2=spread(r2_score, predicted),
                    mae=spread(mean_absolute_error, predicted), rmse=spread(rmse, predicted),
                    baseline_r2=spread(r2_score, baseline),
                    baseline_mae=spread(mean_absolute_error, baseline),
                    baseline_rmse=spread(rmse, baseline))


def reliability(ratings: list[Rating], splits: int = SPLITS, seed: int = SEED) -> float | None:
    """How far a page's mean is a fact about the page, not about who rated it:
    each page's raters are halved at random, the two halves' means correlated
    over pages, and Spearman-Brown steps that up to all the raters. About the
    most R² any model of these means could reach. A rater's two answers to a
    repeated page count as one."""
    per_page: dict[tuple[str, str], dict[int, list[int]]] = {}
    for r in ratings:
        per_page.setdefault(r.key, {}).setdefault(r.rater, []).append(r.rating)
    means = [[float(np.mean(answers)) for answers in raters.values()]
             for raters in per_page.values() if len(raters) >= 2]
    if len(means) < 3:
        return None
    rng = np.random.default_rng(seed)
    found = []
    for _ in range(splits):
        one, two = [], []
        for page in means:
            order = rng.permutation(len(page))
            half = len(page) // 2
            one.append(np.mean([page[i] for i in order[:half]]))
            two.append(np.mean([page[i] for i in order[half:]]))
        if len(set(one)) > 1 and len(set(two)) > 1:
            found.append(float(pearsonr(one, two)[0]))
    if not found:
        return None
    half = float(np.mean(found))
    return 2 * half / (1 + half) if half > -1 else None


def band(values: np.ndarray, cuts: tuple[float, float]) -> np.ndarray:
    """0 calm, 1 middle, 2 heavy. A value on a cut goes up, as `page_model` does."""
    return np.digitize(values, cuts)


def quadratic_kappa(a: np.ndarray, b: np.ndarray, classes: int = 3) -> float:
    """Agreement between two bandings beyond chance, a miss of two bands
    counting four times a miss of one. 1 is perfect and 0 is chance."""
    a, b = np.asarray(a, dtype=int), np.asarray(b, dtype=int)
    observed = np.bincount(classes * a + b, minlength=classes ** 2).reshape(classes, classes)
    expected = np.outer(observed.sum(axis=1), observed.sum(axis=0)) / len(a)
    weights = (np.arange(classes)[:, None] - np.arange(classes)[None, :]) ** 2
    against = float((weights * expected).sum())
    return 1.0 - float((weights * observed).sum()) / against if against else 0.0


def natural_breaks(values: np.ndarray) -> tuple[float, float]:
    """Where `values` fall most naturally into three groups: the two cuts that
    leave the least squared distance to each group's own mean (Jenks). A check
    on `BANDS`, not the bands: it would move with every retraining."""
    ordered = np.sort(np.asarray(values, dtype=float))
    best: tuple[float, float, float] | None = None
    for i in range(1, len(ordered) - 1):
        for j in range(i + 1, len(ordered)):
            within = sum(float(((g - g.mean()) ** 2).sum())
                         for g in (ordered[:i], ordered[i:j], ordered[j:]))
            if best is None or within < best[0]:
                best = (within, float(ordered[i - 1] + ordered[i]) / 2,
                        float(ordered[j - 1] + ordered[j]) / 2)
    assert best is not None
    return best[1], best[2]


def choose_cuts(predicted: np.ndarray, y: np.ndarray) -> tuple[tuple[float, float], float]:
    """The two score cut points that best reproduce the raters' own bands on
    held-out scores (`predicted`, one row per shuffle), and that agreement: the
    mean quadratic kappa. A tie goes to the lower cuts, so that the miss which
    is rarer is the one on a heavy page."""
    target = band(y, BANDS)
    best: tuple[tuple[float, float], float] = (BANDS, -2.0)
    for i, calm in enumerate(CUT_GRID):
        for heavy in CUT_GRID[i + 1:]:
            kappa = float(np.mean([quadratic_kappa(target, band(row, (calm, heavy)))
                                   for row in predicted]))
            if kappa > best[1]:
                best = ((calm, heavy), kappa)
    return best


@dataclass
class Levels:
    """Where the score changes the level, and what that is worth."""

    cuts: tuple[float, float]
    #: Mean quadratic kappa of `cuts` on held-out scores. Chosen on those same
    #: scores, so it flatters: `nested_kappa` is the number to quote.
    kappa: float
    #: `BANDS` used as the cuts, unchanged: the choice this has to beat.
    plain_kappa: float
    #: The whole procedure held out: cut points chosen without the page scored.
    nested_kappa: float
    nested_exact: float
    #: Mean and standard deviation of each cut over those nested choices.
    nested_cuts: tuple[tuple[float, float], tuple[float, float]]
    #: Where the page means fall into three by themselves.
    breaks: tuple[float, float]
    #: Pages rated calm, middle and heavy.
    rated: tuple[int, int, int]
    #: Rows are the raters' band, columns the band of the mean held-out score.
    confusion: list[list[int]]
    #: Each page's band from the nested choice, one row per shuffle.
    nested_bands: list[list[int]] = field(default_factory=list)


def choose_levels(x: np.ndarray, y: np.ndarray, predicted: np.ndarray,
                  repeats: int = 5, inner: int = 3) -> Levels:
    """`choose_cuts`, and how it does on pages it did not choose on: for each
    of `repeats` shuffles of five folds the cuts are chosen from the other four
    folds alone, then used on the fifth."""
    cuts, kappa = choose_cuts(predicted, y)
    target = band(y, BANDS)
    plain = float(np.mean([quadratic_kappa(target, band(row, BANDS)) for row in predicted]))
    kappas, exact, chosen, nested_bands = [], [], [], []
    for repeat in range(repeats):
        folds = KFold(n_splits=FOLDS, shuffle=True, random_state=SEED + 100 + repeat)
        bands = np.zeros(len(y), dtype=int)
        for train_index, test_index in folds.split(x):
            inside, _ = held_out_predictions(x[train_index], y[train_index], inner, SEED + repeat)
            picked, _ = choose_cuts(inside, y[train_index])
            chosen.append(picked)
            scores = _model().fit(x[train_index], y[train_index]).predict(x[test_index])
            bands[test_index] = band(np.clip(scores, *SCALE), picked)
        kappas.append(quadratic_kappa(target, bands))
        exact.append(float(np.mean(bands == target)))
        nested_bands.append(bands.tolist())
    table = np.zeros((3, 3), dtype=int)
    for rated_band, scored_band in zip(target, band(predicted.mean(axis=0), cuts)):
        table[rated_band, scored_band] += 1
    picks = np.array(chosen)
    return Levels(
        cuts=cuts, kappa=kappa, plain_kappa=plain, nested_kappa=float(np.mean(kappas)),
        nested_exact=float(np.mean(exact)),
        nested_cuts=((float(picks[:, 0].mean()), float(picks[:, 0].std())),
                     (float(picks[:, 1].mean()), float(picks[:, 1].std()))),
        breaks=natural_breaks(y),
        rated=(int((target == 0).sum()), int((target == 1).sum()), int((target == 2).sum())),
        confusion=table.tolist(), nested_bands=nested_bands,
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
        "scale": SCALE,
        "pages": trained.pages,
        "cv_r2": trained.r2,
        "min_ratings": trained.min_ratings,
        "pages_below_floor": len(trained.below_floor),
        "cuts": trained.levels.cuts if trained.levels else None,
        "trained_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "sources": trained.sources,
    }, path)


def save_coefficients(trained: Trained, path: Path = COEFFICIENTS) -> None:
    """The model as plain numbers, for the running app and for reading: a
    linear model is a mean and a spread per feature, a coefficient per feature
    and an intercept. The app reads this rather than the joblib because
    importing scikit-learn took 5.6s here (2026-10-30), on every backend start,
    to do a sum. Never a synthetic model at the project's own path."""
    if trained.synthetic and _is_the_projects(path, COEFFICIENTS):
        raise RefusedToTrain(
            f"refusing to save a model trained on synthetic ratings to {COEFFICIENTS}: "
            f"that is what the running app reads.")
    if trained.levels is None:
        raise RefusedToTrain("no cut points to save: they are chosen by `run`.")
    scaler: StandardScaler = trained.model[0]
    ridge: RidgeCV = trained.model[-1]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "version": "trained " + datetime.now().astimezone().isoformat(timespec="seconds"),
        "synthetic": trained.synthetic,
        "scale": list(SCALE),
        "features": list(FEATURES),
        "means": [float(v) for v in scaler.mean_],
        "spreads": [float(v) for v in scaler.scale_],
        "coefficients": [float(v) for v in ridge.coef_],
        "intercept": float(ridge.intercept_),
        "ridge_alpha": float(ridge.alpha_),
        "cuts": {"calm": trained.levels.cuts[0], "heavy": trained.levels.cuts[1]},
        "raters": trained.agreement.raters,
        "pages": len(trained.pages),
        "min_ratings": trained.min_ratings,
        "pages_below_floor": len(trained.below_floor),
        "cv_r2": trained.r2[0],
    }, indent=2) + "\n", encoding="utf-8")


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
    conditions_block = trained.sources.get("conditions")
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
        *([f"```text\n{conditions_block}\n```", ""] if conditions_block else []),
        *_floor_section(trained),
        "### How far the raters agree", "",
        "| | |", "|---|---|",
        f"| Raters | {a.raters}"
        + (" (" + ", ".join(f"Set {s}: {n}" for s, n in a.raters_by_set.items()) + ")"
           if a.raters_by_set else "") + " |",
        f"| Pages rated | {a.pages} |",
        *([f"| Ratings per page, fewest / median / most | {min(counts)} / "
           f"{float(np.median(counts)):g} / {max(counts)} (at least {MIN_RATINGS} needed) |"]
          if (counts := list(trained.coverage.counts.values()) if trained.coverage else [])
          else []),
        f"| Krippendorff's alpha (interval), first showings | {_number(a.alpha)} |",
        *[f"| Krippendorff's alpha, Set {s} only | {_number(v)} |"
          for s, v in a.alpha_by_set.items()],
        f"| Repeated pages: pairs | {len(a.repeat_pairs)} |",
        f"| Repeated pages: mean difference | {_number(a.repeat_mean_difference, 2)} |",
        f"| Repeated pages: identical / within one | "
        f"{_number(a.repeat_identical, 2)} / {_number(a.repeat_within_one, 2)} |",
        f"| Repeated pages: correlation | {_number(a.repeat_correlation)} |", "",
        "Each rater against the mean of the others (Spearman):", "",
        "| Rater | ρ |", "|---|---|",
        *[f"| {rater} | {_number(rho)} |" for rater, rho in a.rater_vs_rest.items()], "",
        *_groups_section(a.groups),
        "### The model", "",
        f"Ridge regression on the nine features, standardised; alpha chosen inside "
        f"each training fold from {len(ALPHAS)} values, {ALPHAS[0]:g}–{ALPHAS[-1]:g}; "
        f"{trained.alpha:g} on all {len(trained.pages)} pages.", "",
        "| | R², 5-fold, mean ± sd | Folds |", "|---|---|---|",
        f"| Ridge | **{r2:.3f} ± {r2_sd:.3f}** | "
        f"{', '.join(f'{v:.2f}' for v in trained.fold_r2)} |",
        f"| Predicting the training mean | {base:.3f} ± {base_sd:.3f} | "
        f"{', '.join(f'{v:.2f}' for v in trained.baseline_r2)} |", "",
        "Error on the held-out folds, in points of the 1-5 scale:", "",
        "| | Mean absolute error | Root mean squared error |", "|---|---|---|",
        f"| Ridge | **{_spread(trained.fold_mae)}** | **{_spread(trained.fold_rmse)}** |",
        f"| Predicting the training mean | {_spread(trained.baseline_mae)} | "
        f"{_spread(trained.baseline_rmse)} |", "",
        *_repeated_section(trained),
        f"Permutation importance on the held-out fold of each split, "
        f"{PERMUTATION_REPEATS} shuffles each: the R² lost when one feature is shuffled.", "",
        "| Feature | R² lost, mean ± sd | Coefficient (standardised) |", "|---|---|---|",
    ]
    ranked = sorted(FEATURES, key=lambda f: trained.importance[f][0], reverse=True)
    lines += [f"| `{f}` | {trained.importance[f][0]:.3f} ± {trained.importance[f][1]:.3f} | "
              f"{trained.coefficients[f]:+.3f} |" for f in ranked]
    lines += ["", f"The score is {float(trained.model[-1].intercept_):.3f} plus each "
              f"coefficient times its feature's distance from the corpus mean in standard "
              f"deviations, clipped to {SCALE[0]}-{SCALE[1]}."]
    lines += _levels_section(trained.levels)
    if trained.unpaired:
        lines += ["", f"**Ratings of {len(trained.unpaired)} pages did not pair** with a "
                  "current picture and features from its run, and were left out: "
                  + "; ".join(f"{u} [{st}]: {why}" for (u, st), why in trained.unpaired)]
    if trained.unmatched:
        lines += ["", f"**{len(trained.unmatched)} rated pages had no {ENVIRONMENT} features** "
                  "and were left out: " + ", ".join(f"{u} [{s}]" for u, s in trained.unmatched)]
    return "\n".join(lines) + "\n"


def _spread(values: list[float]) -> str:
    return f"{np.mean(values):.3f} ± {np.std(values):.3f}"


def _floor_section(trained: Trained) -> list[str]:
    """A run under the study's floor says so before any number."""
    short = trained.below_floor
    if not short:
        return []
    counts = trained.coverage.counts if trained.coverage else {}
    return [
        f"**Below the study's floor.** {len(short)} of {len(counts)} pages have fewer than "
        f"{MIN_RATINGS} ratings, so this ran with `--min-ratings {trained.min_ratings}`, "
        f"which only a person asks for: " + "; ".join(
            f"{u} [{st}] ({counts[(u, st)]})" for u, st in short) + ".", ""]


def _repeated_section(trained: Trained) -> list[str]:
    found = trained.repeated
    if found is None:
        return []
    lines = [
        f"One split of {len(trained.pages)} pages into five is one draw. Over {REPEATS} "
        f"shuffles of the folds, every page held out once in each, pooled:", "",
        "| | R² | Mean absolute error | Root mean squared error |", "|---|---|---|---|",
        f"| Ridge | **{found.r2[0]:.3f} ± {found.r2[1]:.3f}** | "
        f"**{found.mae[0]:.3f} ± {found.mae[1]:.3f}** | "
        f"**{found.rmse[0]:.3f} ± {found.rmse[1]:.3f}** |",
        f"| Predicting the training mean | {found.baseline_r2[0]:.3f} ± "
        f"{found.baseline_r2[1]:.3f} | {found.baseline_mae[0]:.3f} ± "
        f"{found.baseline_mae[1]:.3f} | {found.baseline_rmse[0]:.3f} ± "
        f"{found.baseline_rmse[1]:.3f} |", ""]
    if trained.ceiling is not None:
        lines += [f"How far these page means can be predicted at all: their reliability, "
                  f"halving each page's raters {SPLITS} times and stepping up with "
                  f"Spearman-Brown, is **{trained.ceiling:.3f}**, about the most R² any "
                  f"model of them could reach.", ""]
    return lines


def _levels_section(found: Levels | None) -> list[str]:
    """How the cut points were chosen, and what that is worth on unseen pages."""
    if found is None:
        return []
    labels = ("calm", "middle", "heavy")
    calm, heavy = found.cuts
    return [
        "", "### From a score to a level", "",
        f"**The raters' own bands**: a mean under {BANDS[0]} is nearest \"Not at all\" or "
        f"\"A little\", {BANDS[0]} to {BANDS[1]} nearest \"Somewhat\", and {BANDS[1]} or more "
        f"nearest \"Very\" or \"Extremely\": {found.rated[0]}, {found.rated[1]} and "
        f"{found.rated[2]} pages. The ratings' natural breaks (three groups, least squared "
        f"distance) are {found.breaks[0]:.2f} and {found.breaks[1]:.2f}.", "",
        f"**The score's cut points are {calm:.2f} and {heavy:.2f}**, chosen by trying every "
        f"pair from {CUT_GRID[0]} to {CUT_GRID[-1]} in steps of 0.05 and keeping the pair "
        f"that best reproduces those bands on held-out scores (quadratic weighted kappa, "
        f"mean over {REPEATS} shuffles: {found.kappa:.3f}; the rating cuts used unchanged: "
        f"{found.plain_kappa:.3f}). A held-out score is squeezed towards the mean, which is "
        f"why the heavy cut sits under {BANDS[1]}.", "",
        f"**On pages the cuts were not chosen on**, the whole procedure held out: kappa "
        f"**{found.nested_kappa:.3f}**, the right band on **{found.nested_exact:.1%}** of "
        f"pages. The cuts chosen there average {found.nested_cuts[0][0]:.2f} ± "
        f"{found.nested_cuts[0][1]:.2f} and {found.nested_cuts[1][0]:.2f} ± "
        f"{found.nested_cuts[1][1]:.2f}: quote them to a tenth at best.", "",
        "Raters' band against the band of each page's mean held-out score:", "",
        "| Raters said | Scored calm | Scored middle | Scored heavy |", "|---|---|---|---|",
        *[f"| {labels[i]} | " + " | ".join(str(n) for n in row) + " |"
          for i, row in enumerate(found.confusion)],
    ]


def _groups_section(found: Groups | None) -> list[str]:
    """The anchors table: whether Set 1's raters and Set 2's rate alike."""
    if found is None:
        return []
    if not found.anchors:
        return ["Two sets of raters, but no page rated by both: the groups cannot be "
                "compared.", ""]
    verdict = {True: "**alike**", False: "**not alike**"}[bool(found.alike)]
    lines = [
        f"The two groups on the {len(found.anchors)} anchor pages both rated: {verdict} "
        f"(Set 2 minus Set 1, mean over anchors, {_number(found.difference, 2)}; "
        f"alike means within {GROUPS_DIFFER} and Mann–Whitney U on each rater's anchor "
        f"mean not below 0.05: p = {_number(found.p_value)}).", "",
        "| Anchor | Set 1 mean (raters) | Set 2 mean (raters) |", "|---|---|---|",
        *[f"| {u} [{st}] | {m1:.2f} ({n1}) | {m2:.2f} ({n2}) |"
          for (u, st), (m1, n1, m2, n2) in found.anchors.items()], ""]
    if found.alike is False:
        lines += ["The groups differ on the same pages, so a page's mean depends on which "
                  "set it was in. Read the model below with that in mind.", ""]
    return lines


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
        evaluation_path: Path = EVALUATION, environment: str = ENVIRONMENT,
        pictures_path: Path | None = PICTURES, design_path: Path | None = DESIGN,
        min_ratings: int = MIN_RATINGS) -> Trained:
    ratings = read_ratings(ratings_path)
    corpus, corpus_conditions = read_corpus(corpus_path, environment)
    pictures = read_pictures(pictures_path) if pictures_path is not None else None
    design = read_design(design_path) if design_path is not None else None
    trained = train(ratings, corpus, min_ratings=min_ratings, pictures=pictures, design=design)
    assert trained.x is not None and trained.y is not None
    predicted, baseline = held_out_predictions(trained.x, trained.y)
    trained.repeated = repeated(trained.y, predicted, baseline)
    trained.levels = choose_levels(trained.x, trained.y, predicted)
    trained.ceiling = reliability(paired(ratings, corpus, pictures)[0] if pictures else ratings)
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
        "conditions": banner(conditions()),
    }
    save_model(trained, model_path)
    save_coefficients(trained, model_path.with_suffix(".json"))
    write_evaluation(trained, evaluation_path)
    return trained


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--ratings", type=Path, default=RATINGS)
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument("--model", type=Path, default=MODEL)
    parser.add_argument("--evaluation", type=Path, default=EVALUATION)
    parser.add_argument("--min-ratings", type=int, default=MIN_RATINGS,
                        help=f"train with fewer than {MIN_RATINGS} ratings on a page; "
                             "the run says so wherever it reports")
    args = parser.parse_args()
    try:
        trained = run(args.ratings, args.corpus, args.model, args.evaluation,
                      min_ratings=args.min_ratings)
    except RefusedToTrain as reason:
        print(f"Not training: {reason}")
        raise SystemExit(2) from None
    print(report(trained))
    print(f"Saved {args.model}; appended to {args.evaluation}.")


if __name__ == "__main__":
    main()
