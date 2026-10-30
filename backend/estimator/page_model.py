"""The trained estimator, as the running app uses it: features in, a load score
and a detail level out.

`train.py` fits a ridge regression to people's ratings of the corpus pages and
writes it down twice: `data/estimator.joblib`, the fitted scikit-learn
pipeline, and `data/estimator.json`, the same model as plain numbers. **This
reads the JSON.** A linear model is a sum, and importing scikit-learn to do
that sum took 5.6s here, on every start of the backend (2026-10-30). A test
holds the two to the same answer on every corpus page.

What comes out of one page, as a `Judgement`:

- `rating`, the predicted answer to "How overwhelming does this page feel?",
  1 (Not at all) to 5 (Extremely);
- `score`, the same on the contract's 0-1 (`load.updated`, CONTRACT.md);
- `level`, by the two cut points saved beside the model: under the first is
  calm (1), under the second middle (2), and from there on heavy (3);
- `reasons`, what moved this page's score most from the average page, in
  plain words, for the logs, the report and the demo. Never shown to the
  person in a task: `load.updated.reason` is not.

**The model only ever says what a page is like.** What the person then sees is
`rules.LevelRules`' decision: the page can start them simpler than the level
they chose as comfortable, never with more detail, and everything they do
after that moves the level as it always has.

**No model is not an error.** A missing file, one this cannot read, one with
different features, or a synthetic one gives `None`, and the rules go on
judging pages by their three signs, as they did before there was a model.
`SIMBA_PAGE_MODEL=0` asks for that on purpose.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.estimator.page_features import PageFeatures

PATH = Path(__file__).resolve().parents[2] / "data" / "estimator.json"
#: Set to "0" to judge pages by the rules even with a model in place.
ENV_SWITCH = "SIMBA_PAGE_MODEL"
#: The nine features, in the order `train.FEATURES` fits them. Held here too,
#: so that a model of something else is refused rather than read wrongly.
FEATURES: tuple[str, ...] = (
    "interactive", "links", "inferred", "text_density", "max_depth",
    "overlays", "form_fields", "dead_link_ratio", "reading_grade",
)
#: What a feature says when it is above and below the average page. Words for
#: a page, not a verdict on it: a model can lean on a feature in a direction
#: nobody would guess, and the sentence still says what the page is like.
WORDS: dict[str, tuple[str, str]] = {
    "interactive": ("many buttons and boxes", "few buttons and boxes"),
    "links": ("many links", "few links"),
    "inferred": ("many controls built from plain page parts",
                 "few controls built from plain page parts"),
    "text_density": ("a lot of text on screen", "little text on screen"),
    "max_depth": ("a deeply nested layout", "a shallow, plain layout"),
    "overlays": ("something covering the page", "nothing covering the page"),
    "form_fields": ("many things to fill in", "few things to fill in"),
    "dead_link_ratio": ("many links that go nowhere", "few links that go nowhere"),
    "reading_grade": ("hard words and long sentences", "easy words and short sentences"),
}
#: How many reasons a judgement gives.
TOP = 3
#: A feature that moved the score by less than this is not a reason.
SMALLEST_REASON = 0.05

log = logging.getLogger("simba.estimator")


@dataclass(frozen=True)
class Judgement:
    """What the model says about one page."""

    rating: float
    score: float
    level: int
    reasons: tuple[str, ...]

    def says(self) -> str:
        """`4.8 of 5: a lot of text on screen, many links`, for logs and for
        `load.updated.reason`."""
        because = ", ".join(self.reasons) or "much like the average page"
        return f"{self.rating:.1f} of 5: {because}"

    def as_row(self) -> dict[str, Any]:
        return {"rating": self.rating, "score": self.score, "level": self.level,
                "reasons": list(self.reasons)}


@dataclass(frozen=True)
class PageModel:
    """The numbers in `data/estimator.json`, and the sum they stand for."""

    version: str
    means: tuple[float, ...]
    spreads: tuple[float, ...]
    coefficients: tuple[float, ...]
    intercept: float
    calm: float
    heavy: float
    low: float = 1.0
    high: float = 5.0

    def contributions(self, features: PageFeatures) -> dict[str, float]:
        """How far each feature moves this page from the average page, in
        points of the 1-5 scale. Their sum and the intercept are the score."""
        return {
            name: coefficient * (float(getattr(features, name)) - mean) / spread
            for name, mean, spread, coefficient
            in zip(FEATURES, self.means, self.spreads, self.coefficients)
        }

    def rating(self, features: PageFeatures) -> float:
        """The predicted rating, clipped to the scale: a page with more links
        than any in the corpus is not more than "Extremely"."""
        raw = self.intercept + sum(self.contributions(features).values())
        return min(self.high, max(self.low, raw))

    def level(self, rating: float) -> int:
        """A rating on a cut goes up, as `train.band` does."""
        return 1 if rating < self.calm else 2 if rating < self.heavy else 3

    def reasons(self, features: PageFeatures) -> tuple[str, ...]:
        """The features that moved this page most the way its score went: for a
        page above the average what pushed it up, for one below what held it
        down. Fewer than `TOP` when fewer than that moved it noticeably."""
        moved = self.contributions(features)
        up = sum(moved.values()) >= 0
        chosen = sorted(((name, by) for name, by in moved.items()
                         if (by > 0) == up and abs(by) >= SMALLEST_REASON),
                        key=lambda found: abs(found[1]), reverse=True)[:TOP]
        return tuple(self._word(name, features) for name, _ in chosen)

    def _word(self, name: str, features: PageFeatures) -> str:
        index = FEATURES.index(name)
        above = float(getattr(features, name)) >= self.means[index]
        words = WORDS[name][0 if above else 1]
        return f"{words} ({int(getattr(features, name))})" if name == "links" else words

    def judge(self, features: PageFeatures) -> Judgement:
        rating = self.rating(features)
        return Judgement(
            rating=round(rating, 3),
            score=round((rating - self.low) / (self.high - self.low), 3),
            level=self.level(rating),
            reasons=self.reasons(features),
        )


def load(path: Path = PATH) -> PageModel | None:
    """The model at `path`, or None with the reason logged, so that the rules
    judge the page instead. Nothing here stops a run."""
    if not path.exists():
        log.info("page model: none at %s; the rules judge pages", path)
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("synthetic", True):
            raise ValueError("it was not trained on people's ratings")
        if tuple(data["features"]) != FEATURES:
            raise ValueError("its features are not these nine")
        spreads = tuple(float(v) for v in data["spreads"])
        if len(spreads) != len(FEATURES) or min(spreads) <= 0:
            raise ValueError("its spreads are not one positive number per feature")
        model = PageModel(
            version=str(data["version"]),
            means=tuple(float(v) for v in data["means"]),
            spreads=spreads,
            coefficients=tuple(float(v) for v in data["coefficients"]),
            intercept=float(data["intercept"]),
            calm=float(data["cuts"]["calm"]),
            heavy=float(data["cuts"]["heavy"]),
            low=float(data["scale"][0]),
            high=float(data["scale"][1]),
        )
        if not (len(model.means) == len(model.coefficients) == len(FEATURES)):
            raise ValueError("it does not have one number per feature")
        if not model.low < model.calm < model.heavy <= model.high:
            raise ValueError("its cut points are out of order")
    except (OSError, KeyError, TypeError, ValueError, IndexError) as error:
        log.warning("page model: %s not used, %s; the rules judge pages", path, error)
        return None
    log.info("page model: %s, from %s", model.version, path)
    return model


def wanted() -> bool:
    """On unless `SIMBA_PAGE_MODEL` says otherwise."""
    return os.environ.get(ENV_SWITCH, "1").strip().lower() not in {"0", "false", "no"}


def active(path: Path | None = None) -> PageModel | None:
    """The model the running app should use, if any. Read fresh for each
    connection: the file is small, and a retraining takes effect without a
    restart. The default path is looked up here so that tests can move it."""
    return load(path if path is not None else PATH) if wanted() else None
