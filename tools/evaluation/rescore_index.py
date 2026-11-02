"""The overwhelm index again, by a model that can see the first screen.

    python -m tools.evaluation.rescore_index            # the model from train_visual
    python -m tools.evaluation.rescore_index --preview  # the preview's, marked as one

Works the table out from `data/visual_features.json`, where every site has all
fourteen features from one load. **It visits nothing.** Both models are given the
same read, so the two columns are of one page, and the first index
(`overwhelm_index`, `.scratch/overwhelm-index/`) is left as it is: this writes to
`.scratch/overwhelm-index/visual/`.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from backend.estimator import page_model
from backend.estimator.page_model import VISUAL_FEATURES, PageModel
from backend.estimator.rules import LevelRules
from backend.estimator.train_visual import ALL_FEATURES, CANDIDATE, PREVIEW, VISUAL

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / ".scratch" / "overwhelm-index" / "visual"


class Unscored(Exception):
    """One of the two models is not there to score with, and which."""


class SavedPage(SimpleNamespace):
    """A saved row where `rules` and `page_model` expect `PageFeatures`."""

    def as_dict(self) -> dict[str, Any]:
        return vars(self)


def rescored(rows: list[dict], live: PageModel, new: PageModel) -> list[dict]:
    """Every site read with all fourteen, by both models, with no visit to anything.
    The live model's score is worked out here, on this read's features, so the two
    columns are the same page."""
    out = []
    for row in rows:
        if row["status"] != "scored":
            continue
        found = SavedPage(**{name: row[name] for name in ALL_FEATURES},
                          controls=row["interactive"] + row["links"])
        judged = new.judge(found)  # type: ignore[arg-type]
        before = live.judge(found)  # type: ignore[arg-type]
        decision = LevelRules(page_model=new).start_step(0, found)  # type: ignore[arg-type]
        moved = new.contributions(found)  # type: ignore[arg-type]
        up = sorted(((name, by) for name, by in moved.items() if by >= page_model.SMALLEST_REASON),
                    key=lambda item: -item[1])[:page_model.TOP]
        out.append({"site": row["site"], "category": row["category"], "url": row["url"],
                    "old_rating": before.rating, "old_band": before.level,
                    "rating": judged.rating, "band": judged.level,
                    "simba_level": decision.level, "reasons": list(judged.reasons),
                    "pushed_up_by": [new._word(name, found)  # type: ignore[arg-type]
                                     for name, _ in up],
                    **{name: row[name] for name in VISUAL_FEATURES}})
    return sorted(out, key=lambda row: (-row["rating"], row["site"]))


def rescored_report(rows: list[dict], live: PageModel, new: PageModel, preview: bool) -> str:
    lines = ["# The overwhelm index, by the model that can see the first screen", ""]
    if preview:
        lines += ["**A preview.** This model learned from Sets 1 and 2 alone, under the floor. "
                  "It has seen no busy Pakistani page, so this shows what the sums do and "
                  "not how these pages feel.", ""]
    moved = [row["rating"] - row["old_rating"] for row in rows]
    lines += [
        f"{len(rows)} sites, from what was saved. Nothing was visited.", "",
        f"Median {statistics.median(r['old_rating'] for r in rows):.2f} by the live model, "
        f"{statistics.median(r['rating'] for r in rows):.2f} by this one. Heavy: "
        f"{sum(r['old_band'] == 3 for r in rows)} and {sum(r['band'] == 3 for r in rows)}. Below "
        f"its own average page: {sum(r['old_rating'] < live.intercept for r in rows)} and "
        f"{sum(r['rating'] < new.intercept for r in rows)}. Mean move "
        f"{statistics.mean(moved):+.2f}.", "",
        "| # | Site | Category | Live | This model | Band | Level | Pushed up by |",
        "|---|---|---|---|---|---|---|---|"]
    for rank, row in enumerate(rows, 1):
        lines.append(f"| {rank} | {row['site']} | {row['category']} | {row['old_rating']:.2f} | "
                     f"{row['rating']:.2f} | {row['band']} | {row['simba_level']} | "
                     f"{', '.join(row['pushed_up_by']) or 'nothing much'} |")
    lines += ["", "## By category", "", "| Category | Sites | Live | This model |", "|---|---|---|---|"]
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(row["category"], []).append(row)
    for category, members in sorted(groups.items(),
                                    key=lambda item: -statistics.mean(r["rating"] for r in item[1])):
        lines.append(f"| {category} | {len(members)} | "
                     f"{statistics.mean(r['old_rating'] for r in members):.2f} | "
                     f"{statistics.mean(r['rating'] for r in members):.2f} |")
    pushes = Counter(reason for row in rows for reason in row["pushed_up_by"])
    lines += ["", "## What pushed pages up", "",
              *[f"- **{reason}**: {count} of {len(rows)}" for reason, count in pushes.most_common(3)],
              ""]
    return "\n".join(lines)


def write_rescored(candidate: Path = CANDIDATE, visual: Path = VISUAL, out: Path = OUT,
                   preview: bool = False) -> list[dict]:
    """The table and the report, beside the first index and not over it."""
    live = page_model.load()
    new = page_model.load(candidate, names=ALL_FEATURES)
    if live is None or new is None:
        raise Unscored(f"the live model or {candidate} is missing, or could not be read.")
    rows = json.loads(visual.read_text(encoding="utf-8"))["sites"]["rows"]
    table = rescored(rows, live, new)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "overwhelm_index.csv").open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=[
            "rank", "site", "category", "old_rating", "old_band", "rating", "band", "simba_level",
            "reasons", "pushed_up_by", *VISUAL_FEATURES, "url"])
        writer.writeheader()
        for rank, row in enumerate(table, 1):
            writer.writerow({**row, "rank": rank, "reasons": "; ".join(row["reasons"]),
                             "pushed_up_by": "; ".join(row["pushed_up_by"])})
    (out / "report.md").write_text(rescored_report(table, live, new, preview), encoding="utf-8")
    return table


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    candidate = PREVIEW / "estimator_visual.json" if args.preview else CANDIDATE
    out = PREVIEW / "overwhelm-index" if args.preview else OUT
    try:
        table = write_rescored(candidate, VISUAL, out, args.preview)
    except Unscored as reason:
        print(f"Not scored: {reason} Run python -m backend.estimator.train_visual first.")
        raise SystemExit(2) from None
    print(f"{len(table)} sites; {out}")


if __name__ == "__main__":
    main()
