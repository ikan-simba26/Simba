"""The overwhelm index again, from what was saved: the live model and the new one.

    python -m tools.evaluation.rescore_index --by live  # ranked by the live model, the nine
    python -m tools.evaluation.rescore_index            # ranked by the model from train_visual
    python -m tools.evaluation.rescore_index --preview  # the preview's, marked as one

Works the table out from `data/visual_features.json`, where every site has all
fourteen features from one load. **It visits nothing.** Both models are given the
same read, so the two columns are of one page, and the first index
(`overwhelm_index`, `.scratch/overwhelm-index/`) is left as it is: this writes to
`.scratch/overwhelm-index/visual/`.

**Ranked by the model the gate keeps** (`train_visual` passes `by`): each row's
reasons, what pushed it up and what held it down, and SIMBA's level, are that
model's. The other model's rating is a column beside it.

**Where people rated a site** (Set 3), their mean is beside it, and the report
holds both models against it: error, lean and order. Only answers given to the
picture Set 3 names are counted, as training counts them.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
from scipy.stats import spearmanr

from backend.estimator import page_model, train
from backend.estimator.page_model import VISUAL_FEATURES, PageModel
from backend.estimator.rules import LevelRules
from backend.estimator.train_visual import ALL_FEATURES, CANDIDATE, PREVIEW, SET3, VISUAL

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / ".scratch" / "overwhelm-index" / "visual"
#: What each ranking is called in a report.
NAMED = {"live": "the live model (the nine)", "new": "the new model (the nine and the five)"}


class Unscored(Exception):
    """One of the two models is not there to score with, and which."""


class SavedPage(SimpleNamespace):
    """A saved row where `rules` and `page_model` expect `PageFeatures`."""

    def as_dict(self) -> dict[str, Any]:
        return vars(self)


def people(ratings: Path = train.RATINGS, set3: Path = SET3) -> dict[str, tuple[float, int]]:
    """Set 3's sites as people rated them: address -> (mean, raters). A rater's two
    answers to a repeated picture count once (`train.page_means`), and an answer to
    any other picture of the site is not counted. Empty with nothing to read."""
    if not ratings.exists() or not set3.exists():
        return {}
    chosen = train.read_pictures(set3)
    answered = [r for r in train.read_ratings(ratings)
                if r.key in chosen and r.image in ("", chosen[r.key]["sha256"])]
    return {key[0]: found for key, found in train.page_means(answered).items()}


def _words(model: PageModel, found: SavedPage, up: bool) -> list[str]:
    """The features that moved this page most one way, by `model`, in words."""
    moved = model.contributions(found)  # type: ignore[arg-type]
    chosen = sorted(((name, by) for name, by in moved.items()
                     if (by > 0) == up and abs(by) >= page_model.SMALLEST_REASON),
                    key=lambda item: -abs(item[1]))[:page_model.TOP]
    return [model._word(name, found) for name, _ in chosen]  # type: ignore[arg-type]


def rescored(rows: list[dict], live: PageModel, new: PageModel, by: str = "new",
             people: dict[str, tuple[float, int]] | None = None) -> list[dict]:
    """Every site read with all fourteen, by both models, with no visit to anything.
    The live model's score is worked out here, on this read's features, so the two
    columns are the same page. Ranked by `by`, `"new"` or `"live"`, whose reasons and
    level each row gives; `people` puts a rated site's mean beside it."""
    ranking = new if by == "new" else live
    said = people or {}
    out = []
    for row in rows:
        if row["status"] != "scored":
            continue
        found = SavedPage(**{name: row[name] for name in ALL_FEATURES},
                          controls=row["interactive"] + row["links"])
        judged = new.judge(found)  # type: ignore[arg-type]
        before = live.judge(found)  # type: ignore[arg-type]
        decision = LevelRules(page_model=ranking).start_step(0, found)  # type: ignore[arg-type]
        mean, raters = said.get(row["url"], (None, 0))
        out.append({"site": row["site"], "category": row["category"], "url": row["url"],
                    "ranked_by": by,
                    "old_rating": before.rating, "old_band": before.level,
                    "rating": judged.rating, "band": judged.level,
                    "simba_level": decision.level,
                    "reasons": list(ranking.judge(found).reasons),  # type: ignore[arg-type]
                    "pushed_up_by": _words(ranking, found, up=True),
                    "held_down_by": _words(ranking, found, up=False),
                    "people": mean, "raters": raters,
                    **{name: row[name] for name in VISUAL_FEATURES}})
    key = "rating" if by == "new" else "old_rating"
    return sorted(out, key=lambda row: (-row[key], row["site"]))


def common(rows: list[dict], key: str, top: int = 3) -> list[tuple[str, int]]:
    """The reasons most often given under `key`, each counted once whatever count it
    carries: "many links (217)" and "many links (326)" are one reason."""
    counted = Counter(re.sub(r" \(\d+\)$", "", reason) for row in rows for reason in row[key])
    return counted.most_common(top)


def against_people(rows: list[dict], preview: bool = False) -> list[str]:
    """Both models held against people's means on the sites people rated. The live
    model never saw these ratings; the new one, unless a preview, was fitted on them."""
    rated = [row for row in rows if row["people"] is not None]
    if len(rated) < 3:
        return []
    said = np.array([row["people"] for row in rated])
    lines = [f"## As people rated them: {len(rated)} sites, Set 3", "",
             "| Model | Error | Leans (model minus people) | Order kept (Spearman) | "
             "Heavy by people, by the model |", "|---|---|---|---|---|"]
    for name, key, band in (("live", "old_rating", "old_band"), ("new", "rating", "band")):
        given = np.array([row[key] for row in rated])
        heavy_people = int((train.band(said, train.BANDS) == 2).sum())
        heavy_model = sum(row[band] == 3 for row in rated)
        rho = float(spearmanr(said, given).statistic)
        lines.append(f"| {NAMED[name].capitalize()} | {np.abs(given - said).mean():.2f} | "
                     f"{(given - said).mean():+.2f} | {rho:.2f} | {heavy_people}, {heavy_model} |")
    lines += ["", f"People's means: {said.mean():.2f} on average, {said.min():.2f} to "
              f"{said.max():.2f}, {min(row['raters'] for row in rated)} to "
              f"{max(row['raters'] for row in rated)} raters each.", "",
              "The live model was trained before these ratings existed, so its row is a test "
              "on pages it never saw. " + (
                  "The preview never saw them either." if preview else
                  "**The new model's row is not held out**: it was fitted on every rated page, "
                  "these fifteen included, so it is bound to look closer. Held out, in the same "
                  "folds as the rest, the two do the same on these pages (`train_visual`'s "
                  "report, *On the Pakistani pages alone*)."), ""]
    return lines


def rescored_report(rows: list[dict], live: PageModel, new: PageModel, preview: bool,
                    by: str = "new") -> str:
    if by == "new":
        lines = ["# The overwhelm index, by the model that can see the first screen", ""]
    else:
        lines = ["# The overwhelm index again, by the live model, on the first-screen read", "",
                 "The gate kept the live model, so this is ranked by it: reasons, bands and "
                 "levels are its own. The new model is a column beside it.", ""]
    if preview:
        lines += ["**A preview.** This model learned from Sets 1 and 2 alone, under the floor. "
                  "It has seen no busy Pakistani page, so this shows what the sums do and "
                  "not how these pages feel.", ""]
    moved = [row["rating"] - row["old_rating"] for row in rows]
    rank_key, band_key = ("rating", "band") if by == "new" else ("old_rating", "old_band")
    other_key = "old_rating" if by == "new" else "rating"
    lines += [
        f"{len(rows)} sites, from what was saved. Nothing was visited.", "",
        f"Median {statistics.median(r['old_rating'] for r in rows):.2f} by the live model, "
        f"{statistics.median(r['rating'] for r in rows):.2f} by the new one. Heavy: "
        f"{sum(r['old_band'] == 3 for r in rows)} and {sum(r['band'] == 3 for r in rows)}. Below "
        f"its own average page: {sum(r['old_rating'] < live.intercept for r in rows)} and "
        f"{sum(r['rating'] < new.intercept for r in rows)}. Mean move, new minus live, "
        f"{statistics.mean(moved):+.2f}.", "",
        f"| # | Site | Category | {'New' if by == 'new' else 'Live'} | Band | Level | "
        f"{'Live' if by == 'new' else 'New'} | People (raters) | Pushed up by | Held down by |",
        "|---|---|---|---|---|---|---|---|---|---|"]
    for rank, row in enumerate(rows, 1):
        rated = f"{row['people']:.2f} ({row['raters']})" if row["people"] is not None else ""
        lines.append(f"| {rank} | {row['site']} | {row['category']} | {row[rank_key]:.2f} | "
                     f"{row[band_key]} | {row['simba_level']} | {row[other_key]:.2f} | {rated} | "
                     f"{', '.join(row['pushed_up_by']) or 'nothing much'} | "
                     f"{', '.join(row['held_down_by']) or 'nothing much'} |")
    lines += ["", "## By category", "", "| Category | Sites | Live | New | People, where rated |",
              "|---|---|---|---|---|"]
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(row["category"], []).append(row)
    for category, members in sorted(groups.items(),
                                    key=lambda item: -statistics.mean(r[rank_key] for r in item[1])):
        rated = [r["people"] for r in members if r["people"] is not None]
        lines.append(f"| {category} | {len(members)} | "
                     f"{statistics.mean(r['old_rating'] for r in members):.2f} | "
                     f"{statistics.mean(r['rating'] for r in members):.2f} | "
                     f"{f'{statistics.mean(rated):.2f} ({len(rated)})' if rated else ''} |")
    lines += ["", "## What pushed pages up, and what held them down", "",
              *[f"- up, **{reason}**: {count} of {len(rows)}"
                for reason, count in common(rows, "pushed_up_by")],
              *[f"- down, **{reason}**: {count} of {len(rows)}"
                for reason, count in common(rows, "held_down_by")], ""]
    lines += against_people(rows, preview)
    return "\n".join(lines)


def write_rescored(candidate: Path = CANDIDATE, visual: Path = VISUAL, out: Path = OUT,
                   preview: bool = False, by: str = "new",
                   people: dict[str, tuple[float, int]] | None = None) -> list[dict]:
    """The table and the report, beside the first index and not over it."""
    live = page_model.load()
    new = page_model.load(candidate, names=ALL_FEATURES)
    if live is None or new is None:
        raise Unscored(f"the live model or {candidate} is missing, or could not be read.")
    rows = json.loads(visual.read_text(encoding="utf-8"))["sites"]["rows"]
    table = rescored(rows, live, new, by, people)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "overwhelm_index.csv").open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=[
            "rank", "site", "category", "ranked_by", "old_rating", "old_band", "rating", "band",
            "simba_level", "people", "raters", "reasons", "pushed_up_by", "held_down_by",
            *VISUAL_FEATURES, "url"])
        writer.writeheader()
        for rank, row in enumerate(table, 1):
            writer.writerow({**row, "rank": rank, "reasons": "; ".join(row["reasons"]),
                             "pushed_up_by": "; ".join(row["pushed_up_by"]),
                             "held_down_by": "; ".join(row["held_down_by"])})
    (out / "report.md").write_text(rescored_report(table, live, new, preview, by),
                                   encoding="utf-8")
    return table


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--by", choices=("new", "live"), default="new",
                        help="the model to rank by: the one the gate kept")
    args = parser.parse_args()
    candidate = PREVIEW / "estimator_visual.json" if args.preview else CANDIDATE
    out = PREVIEW / "overwhelm-index" if args.preview else OUT
    try:
        table = write_rescored(candidate, VISUAL, out, args.preview, args.by, people())
    except Unscored as reason:
        print(f"Not scored: {reason} Run python -m backend.estimator.train_visual first.")
        raise SystemExit(2) from None
    print(f"{len(table)} sites; {out}")


if __name__ == "__main__":
    main()
