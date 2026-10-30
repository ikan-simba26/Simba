"""The trained estimator held against the provisional rules, and against itself.

    python -m tools.evaluation.estimator_compare --csv "Set 1.csv" --csv "Set 2.csv"

Spends no model quota and touches no site: it reads `data/ratings.jsonl`,
`data/corpus.json`, `data/estimator.json` and `data/steps.jsonl`. Run it after
`backend.estimator.train`, or let `tools.rating.retrain` run both. What it does:

1. **Rules against model on the 50 pages.** Both judge every page: the rules by
   their three signs, the model by the score and cut points saved with it. The
   model is scored on **held-out** predictions, so it is never marked on a page
   it was fitted to; the rules were never fitted to ratings at all, though
   their thresholds were read off this corpus's spread (DECISIONS.md).
2. **The rules' logged decisions.** Every `start` row in `data/steps.jsonl` is
   replayed through the model. Those rows are from replicas and scripts.
3. **The two environments.** The model was trained on the headless rows, and
   the product runs in Electron, so every page read in both is scored both ways.
4. **How much the handling of the data matters**: the pages at the floor only,
   the phone raters let back in (needs `--csv`), and the raters who ran against
   everyone else taken out. All three are checks, none is the model.
5. **Writes** `data/estimator_pages.json`, each page's score and reasons in
   plain words (committed: no rating in it); `.scratch/estimator/`, the two
   charts and each page beside its rated mean (not committed, DECISIONS.md, *The
   trained model is committed; the ratings are not*); and a section of
   EVALUATION.md.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import spearmanr

from backend.estimator import page_model, train
from backend.estimator.page_features import PageFeatures
from backend.estimator.pairing import DEFAULT_PATH as STEPS, read_rows
from backend.estimator.rules import THRESHOLDS, page_signs
from tools.evaluation.conditions import banner, conditions
from tools.rating import from_form

REPO = Path(__file__).resolve().parents[2]
PAGES = REPO / "data" / "estimator_pages.json"
SCRATCH = REPO / ".scratch" / "estimator"
BOOTSTRAPS = 2000
SEED = 0
#: A rater this far from everyone else (Spearman) is left out of one check.
OUT_OF_STEP = 0.2

#: Chart colours, the reference palette's first slot and its neutral inks.
SURFACE, INK, MUTED, GRID, SERIES = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#2a78d6"


def features_of(row: dict[str, Any]) -> PageFeatures:
    """A corpus row or a logged `page` as `PageFeatures`, whatever else it holds."""
    return PageFeatures(**{name: row[name] for name in PageFeatures.__dataclass_fields__})


@dataclass
class Page:
    key: tuple[str, str]
    kind: str
    ratings: int
    rated: float
    #: Mean over the shuffles of what a model that never saw the page said.
    held_out: float
    #: The model that ships, fitted to every page.
    rating: float
    level: int
    rules_level: int
    signs: list[str]
    reasons: tuple[str, ...]

    @property
    def name(self) -> str:
        url = self.key[0].replace("https://", "").replace("http://", "").rstrip("/")
        return url if self.key[1] == "as it loads" else f"{url} ({self.key[1]})"

    @property
    def start_level(self) -> int:
        """Where the model starts someone who has not said: `LevelRules`."""
        return max(2, self.level)


def pages_of(trained: train.Trained, model: page_model.PageModel, corpus: dict,
             held_out: np.ndarray) -> list[Page]:
    assert trained.y is not None and trained.coverage is not None
    means = held_out.mean(axis=0)
    found = []
    for index, key in enumerate(trained.pages):
        row = corpus[key]
        features = features_of(row)
        judged = model.judge(features)
        signs = page_signs(features)
        found.append(Page(
            key=key, kind=str(row.get("kind", "?")), ratings=trained.coverage.counts[key],
            rated=float(trained.y[index]), held_out=float(means[index]), rating=judged.rating,
            level=judged.level, rules_level=3 if len(signs) >= THRESHOLDS.heavy_signs else 2,
            signs=signs, reasons=judged.reasons))
    return found


# --- the comparison -------------------------------------------------------------


def heavy_calls(called: np.ndarray, rated: np.ndarray) -> dict[str, float]:
    """A heavy call against pages the raters put at "Very" or more."""
    heavy = rated >= train.BANDS[1]
    hits = int((called & heavy).sum())
    false = int((called & ~heavy).sum())
    missed = int((~called & heavy).sum())
    return {"called": hits + false, "hits": hits, "false": false, "missed": missed,
            "precision": hits / (hits + false) if hits + false else 0.0,
            "recall": hits / (hits + missed) if hits + missed else 0.0,
            "accuracy": float((called == heavy).mean())}


def compare(pages: list[Page], held_out: np.ndarray, heavy_cut: float,
            nested_bands: list[list[int]]) -> dict[str, Any]:
    rated = np.array([p.rated for p in pages])
    signs = np.array([len(p.signs) for p in pages], dtype=float)
    scores = np.array([p.held_out for p in pages])
    rule_calls = np.array([p.rules_level == 3 for p in pages])
    model_rho = [float(spearmanr(row, rated)[0]) for row in held_out]
    runs = [heavy_calls(row >= heavy_cut, rated) for row in held_out]
    nested = [heavy_calls(np.array(bands) == 2, rated) for bands in nested_bands]

    rng = np.random.default_rng(SEED)
    gaps = []
    for _ in range(BOOTSTRAPS):
        pick = rng.integers(0, len(pages), len(pages))
        if len(set(signs[pick])) > 1:
            gaps.append(float(spearmanr(scores[pick], rated[pick])[0])
                        - float(spearmanr(signs[pick], rated[pick])[0]))
    return {
        "rules_rho": float(spearmanr(signs, rated)[0]),
        "model_rho": float(np.mean(model_rho)),
        "gap": (float(np.percentile(gaps, 2.5)), float(np.percentile(gaps, 97.5))),
        "rules": heavy_calls(rule_calls, rated),
        "model": {k: float(np.mean([r[k] for r in runs])) for k in runs[0]},
        "nested": {k: float(np.mean([r[k] for r in nested])) for k in nested[0]},
        "rules_called_mean": float(rated[rule_calls].mean()),
        "rules_other_mean": float(rated[~rule_calls].mean()),
    }


def replay_logged(model: page_model.PageModel, steps: Path) -> list[dict[str, Any]]:
    """Each distinct page behind the rules' logged start decisions: how often,
    what the rules made of it, and what the model makes of it."""
    seen: dict[str, dict[str, Any]] = {}
    for row in read_rows(steps):
        if row.get("kind") != "decision" or row.get("at") != "start":
            continue
        page = (row.get("inputs") or {}).get("page")
        if not page:
            continue
        key = json.dumps({f: page[f] for f in page_model.FEATURES}, sort_keys=True)
        entry = seen.setdefault(key, {"rows": 0, "page": page, "levels": {}})
        entry["rows"] += 1
        entry["levels"][row["level"]] = entry["levels"].get(row["level"], 0) + 1
    found = []
    for entry in sorted(seen.values(), key=lambda e: -e["rows"]):
        features = features_of(entry["page"])
        judged = model.judge(features)
        found.append({
            "rows": entry["rows"], "controls": features.controls,
            "text_density": features.text_density, "levels": entry["levels"],
            "rules_heavy": len(page_signs(features)) >= THRESHOLDS.heavy_signs,
            "rating": judged.rating, "level": judged.level})
    return found


def environments(model: page_model.PageModel) -> dict[str, Any]:
    """Every page read in both environments, scored both ways."""
    data = json.loads(train.CORPUS.read_text(encoding="utf-8"))
    rows = {env: {(r["url"], r["state"]): r for r in data["results"][env] if "error" not in r}
            for env in ("headless", "host")}
    both = sorted(set(rows["headless"]) & set(rows["host"]))
    gaps, changed = [], []
    for key in both:
        one = model.judge(features_of(rows["headless"][key]))
        two = model.judge(features_of(rows["host"][key]))
        gaps.append(abs(one.rating - two.rating))
        if one.level != two.level:
            changed.append((key, one.rating, one.level, two.rating, two.level))
    return {"pages": len(both), "mean_gap": float(np.mean(gaps)), "largest": float(np.max(gaps)),
            "changed": changed}


# --- how much the handling matters ----------------------------------------------


def with_phones(paths: list[Path], mapping: dict) -> tuple[list[train.Rating], set[int]]:
    """Every response's ratings, phones included, and who was on a phone. For
    this check only: `from_form` still drops them, and the model never saw them."""
    rows: list[dict] = []
    phones: set[int] = set()
    for path in paths:
        with path.open(encoding="utf-8-sig", newline="") as file:
            table = list(csv.reader(file))
        form = from_form.form_of(table[0], mapping)
        if form is None:
            raise SystemExit(f"{path}: cannot tell which set this is")
        device = next(i for i, title in enumerate(table[0])
                      if title == mapping["questions"]["device"]["title"])
        phone = mapping["questions"]["device"]["choices"]["phone"]
        laptop = mapping["questions"]["device"]["choices"]["laptop"]
        for number, answer in enumerate(table[1:], start=1):
            if answer[device] == phone:
                phones.add(from_form.FORMS[form] + number)
                answer[device] = laptop
        rows += from_form.convert(table, mapping, form).rows
    return ([train.Rating(rater=r["rater"], url=r["url"], state=r["state"], page=r["page"],
                          repeat=r["repeat"], rating=r["rating"], image=r["image_sha256"],
                          set=r["set"]) for r in rows], phones)


def case(name: str, ratings: list[train.Rating], corpus: dict,
         keep: set[tuple[str, str]] | None = None) -> dict[str, Any]:
    if keep is not None:
        ratings = [r for r in ratings if r.key in keep]
    means = train.page_means(ratings)
    pages = sorted(k for k in means if k in corpus)
    x = np.array([[float(corpus[k][f]) for f in train.FEATURES] for k in pages])
    y = np.array([means[k][0] for k in pages])
    predicted, baseline = train.held_out_predictions(x, y)
    found = train.repeated(y, predicted, baseline)
    within = {k: v for k, v in train.ratings_per_page(ratings).items() if k in pages}
    return {"name": name, "pages": len(pages), "raters": len({r.rater for r in ratings}),
            "fewest": min(within.values()), "alpha": train.agreement(ratings).alpha,
            "r2": found.r2, "mae": found.mae}


def noisy_pages_help(trained: train.Trained, at_floor: set[tuple[str, str]]) -> dict[str, float]:
    """Whether the pages under the floor help or hurt, on the pages at it: each
    of those is predicted by a model fitted to the other pages at the floor,
    alone and with every page under it added. The same held-out pages either
    way, so the two figures can be set side by side."""
    assert trained.x is not None and trained.y is not None
    inside = np.array([k in at_floor for k in trained.pages])
    x, y = trained.x[inside], trained.y[inside]
    extra_x, extra_y = trained.x[~inside], trained.y[~inside]
    alone, added = [], []
    for repeat in range(train.REPEATS):
        one, two = np.zeros(len(y)), np.zeros(len(y))
        folds = train.KFold(n_splits=train.FOLDS, shuffle=True, random_state=SEED + repeat)
        for fit, score in folds.split(x):
            one[score] = train._model().fit(x[fit], y[fit]).predict(x[score])
            two[score] = train._model().fit(np.vstack([x[fit], extra_x]),
                                            np.concatenate([y[fit], extra_y])).predict(x[score])
        alone.append(float(np.mean(np.abs(np.clip(one, *train.SCALE) - y))))
        added.append(float(np.mean(np.abs(np.clip(two, *train.SCALE) - y))))
    return {"pages": len(y), "alone": float(np.mean(alone)), "added": float(np.mean(added))}


def sensitivity(ratings: list[train.Rating], corpus: dict, trained: train.Trained,
                csvs: list[Path], mapping: dict
                ) -> tuple[list[dict[str, Any]], str | None, dict[str, float] | None]:
    cases = [case("As shipped: every usable rater, every page", ratings, corpus)]
    at_floor = {k for k, n in train.ratings_per_page(ratings).items() if n >= train.MIN_RATINGS}
    helped = None
    if len(at_floor) < len(trained.pages):
        cases.append(case(f"Only the pages with {train.MIN_RATINGS} ratings or more", ratings,
                          corpus, at_floor))
        helped = noisy_pages_help(trained, at_floor)
    away = {r for r, rho in trained.agreement.rater_vs_rest.items()
            if rho is not None and rho < OUT_OF_STEP}
    if away:
        cases.append(case(f"Without the {len(away)} raters under ρ {OUT_OF_STEP} "
                          f"({', '.join(map(str, sorted(away)))})",
                          [r for r in ratings if r.rater not in away], corpus))
    against = None
    if csvs:
        everyone, phones = with_phones(csvs, mapping)
        cases.append(case(f"With the {len(phones)} phone raters put back", everyone, corpus))
        on_phone = train.page_means([r for r in everyone if r.rater in phones])
        off_phone = train.page_means([r for r in everyone if r.rater not in phones])
        shared = sorted(set(on_phone) & set(off_phone))
        a = [off_phone[k][0] for k in shared]
        b = [on_phone[k][0] for k in shared]
        against = (f"Phone raters against the others, page by page: Pearson "
                   f"{np.corrcoef(a, b)[0, 1]:.2f}, and {np.mean(np.array(b) - np.array(a)):+.2f} "
                   f"on the scale on average. Alone their alpha is "
                   f"{train.agreement([r for r in everyone if r.rater in phones]).alpha:.3f} and "
                   f"their repeats correlate "
                   f"{train.agreement([r for r in everyone if r.rater in phones]).repeat_correlation:.3f}.")
    return cases, against, helped


# --- charts, as plain SVG: matplotlib is not a dependency here -----------------


def _svg(width: int, height: int, body: list[str]) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" font-family="Segoe UI, Arial, sans-serif">'
            f'<rect width="{width}" height="{height}" fill="{SURFACE}"/>' + "".join(body) + "</svg>")


def _text(x: float, y: float, words: str, size: int = 13, colour: str = INK,
          anchor: str = "start", weight: int = 400) -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{colour}" '
            f'text-anchor="{anchor}" font-weight="{weight}">{escape(words)}</text>')


def importance_chart(trained: train.Trained) -> str:
    ranked = sorted(train.FEATURES, key=lambda f: trained.importance[f][0], reverse=True)
    left, top, right, row = 190, 74, 60, 34
    width, height = 760, top + row * len(ranked) + 44
    top_value = max(0.1, max(trained.importance[f][0] for f in ranked))
    scale = (width - left - right) / top_value
    body = [_text(20, 30, "Text on screen and links carry the score", 18, weight=600),
            _text(20, 52, "R² lost on held-out pages when one feature is shuffled. Means of "
                          "250 shuffles; the spread is wide on 50 pages.", 13, MUTED)]
    for tick in np.arange(0, top_value + 0.001, 0.2):
        x = left + tick * scale
        body.append(f'<line x1="{x:.1f}" y1="{top - 6}" x2="{x:.1f}" '
                    f'y2="{top + row * len(ranked)}" stroke="{GRID}"/>')
        body.append(_text(x, top + row * len(ranked) + 18, f"{tick:.1f}", 12, MUTED, "middle"))
    for index, name in enumerate(ranked):
        value = trained.importance[name][0]
        y = top + index * row
        shown = max(value, 0.0) * scale
        body.append(_text(left - 10, y + 19, name, 13, INK, "end"))
        if shown >= 1:
            body.append(f'<path d="M{left},{y + 6} h{max(shown - 4, 0):.1f} q4,0 4,4 v10 q0,4 -4,4 '
                        f'h-{max(shown - 4, 0):.1f} z" fill="{SERIES}"><title>{name}: R² lost '
                        f'{value:.3f} ± {trained.importance[name][1]:.3f}</title></path>')
        body.append(_text(left + shown + 7, y + 19, f"{value:.3f}", 12, MUTED))
    return _svg(width, height, body)


def scatter_chart(pages: list[Page], cuts: tuple[float, float]) -> str:
    left, top, side = 64, 88, 520
    span = (1.0, 5.0)

    def at(v: float) -> float:
        return side * (v - span[0]) / (span[1] - span[0])

    def px(v: float) -> float:
        return left + at(v)

    def py(v: float) -> float:
        return top + side - at(v)

    body = [_text(20, 30, "Held-out scores follow the ratings, and the middle is loose", 18, weight=600),
            _text(20, 52, "Each dot is one page, scored by a model that never saw it (mean of 40 "
                          "shuffles of the folds)", 13, MUTED)]
    for tick in range(1, 6):
        body += [f'<line x1="{px(tick):.1f}" y1="{top}" x2="{px(tick):.1f}" y2="{top + side}" '
                 f'stroke="{GRID}"/>',
                 f'<line x1="{left}" y1="{py(tick):.1f}" x2="{left + side}" y2="{py(tick):.1f}" '
                 f'stroke="{GRID}"/>',
                 _text(px(tick), top + side + 20, str(tick), 12, MUTED, "middle"),
                 _text(left - 10, py(tick) + 4, str(tick), 12, MUTED, "end")]
    body.append(f'<line x1="{px(1)}" y1="{py(1)}" x2="{px(5)}" y2="{py(5)}" stroke="{MUTED}" '
                f'stroke-dasharray="5 5"/>')
    body.append(_text(px(4.12), py(4.42), "score = rating", 12, MUTED, "end"))
    for cut, name in zip(cuts, ("calm | middle", "middle | heavy")):
        body.append(f'<line x1="{px(cut):.1f}" y1="{top}" x2="{px(cut):.1f}" y2="{top + side}" '
                    f'stroke="{INK}" stroke-width="1"/>')
    body.append(_text(px(cuts[0]) - 5, top + 14, f"calm under {cuts[0]:.2f}", 12, MUTED, "end"))
    body.append(_text(px(cuts[1]) + 5, top + 14, f"heavy from {cuts[1]:.2f}", 12, MUTED))
    for bound in train.BANDS:
        body.append(f'<line x1="{left}" y1="{py(bound):.1f}" x2="{left + side}" y2="{py(bound):.1f}" '
                    f'stroke="{INK}" stroke-width="1" stroke-dasharray="1 3"/>')
    for page in sorted(pages, key=lambda p: p.ratings):
        few = page.ratings < train.MIN_RATINGS
        tip = escape(f"{page.name}: rated {page.rated:.2f} by {page.ratings}, "
                     f"held-out score {page.held_out:.2f}")
        body.append(f'<circle cx="{px(page.held_out):.1f}" cy="{py(page.rated):.1f}" r="5" '
                    f'fill="{SURFACE if few else SERIES}" stroke="{SERIES}" stroke-width="2">'
                    f'<title>{tip}</title></circle>')
    body.append(_text(left + side / 2, top + side + 44, "Held-out score", 13, INK, "middle"))
    body.append(f'<text transform="translate(18 {top + side / 2}) rotate(-90)" font-size="13" '
                f'fill="{INK}" text-anchor="middle">Mean rating</text>')
    legend = left + side + 26
    body += [f'<circle cx="{legend + 6}" cy="{top + 8}" r="5" fill="{SERIES}" stroke="{SERIES}" '
             f'stroke-width="2"/>',
             _text(legend + 20, top + 13, f"{train.MIN_RATINGS} ratings or more"),
             f'<circle cx="{legend + 6}" cy="{top + 32}" r="5" fill="{SURFACE}" stroke="{SERIES}" '
             f'stroke-width="2"/>',
             _text(legend + 20, top + 37, f"Under {train.MIN_RATINGS} ratings"),
             f'<line x1="{legend}" y1="{top + 56}" x2="{legend + 14}" y2="{top + 56}" stroke="{INK}" '
             f'stroke-dasharray="1 3"/>',
             _text(legend + 20, top + 61, "Raters' bands, 2.5 and 3.5")]
    return _svg(left + side + 214, top + side + 62, body)


def render(svg_paths: list[Path]) -> None:
    """Each chart as a PNG beside its SVG, from its own page: no screen involved."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as driver:
        browser = driver.chromium.launch()
        for path in svg_paths:
            page = browser.new_page()
            page.set_content(f"<!doctype html><body style='margin:0'>"
                             f"{path.read_text(encoding='utf-8')}</body>")
            page.locator("svg").screenshot(path=str(path.with_suffix(".png")))
            page.close()
        browser.close()


# --- writing --------------------------------------------------------------------


def _row(r: dict[str, float], integers: bool) -> str:
    n = "{:.0f}" if integers else "{:.1f}"
    return (f"{n.format(r['called'])} | {n.format(r['hits'])} | {n.format(r['false'])} | "
            f"{n.format(r['missed'])} | {r['precision']:.2f} | {r['recall']:.2f} | "
            f"{r['accuracy']:.2f}")


def section(pages: list[Page], found: dict[str, Any], logged: list[dict[str, Any]],
            both: dict[str, Any], cases: list[dict[str, Any]], against: str | None,
            helped: dict[str, float] | None, model: page_model.PageModel,
            conditions_block: str, when: datetime) -> str:
    both_heavy = [p for p in pages if p.start_level == 3 and p.rules_level == 3]
    neither = [p for p in pages if p.start_level == 2 and p.rules_level == 2]
    only_model = [p for p in pages if p.start_level == 3 and p.rules_level == 2]
    only_rules = [p for p in pages if p.start_level == 2 and p.rules_level == 3]
    differ = only_model + only_rules
    model_right = sum(1 for p in only_model if p.rated >= train.BANDS[1]) \
        + sum(1 for p in only_rules if p.rated < train.BANDS[1])
    lines = [
        f"## {when:%Y-%m-%db} — the trained estimator against the provisional rules", "",
        "`python -m tools.evaluation.estimator_compare`. Which judges a page more as people "
        "do, for a person who has not said what level they want: the model's heavy call "
        "(level 3) or the rules' (two of three signs). The model is marked on held-out "
        "predictions throughout; rated heavy means a mean of 3.5 or more.", "",
        f"```text\n{conditions_block}\n```", "",
        "### Which is closer to the ratings", "",
        "| | Pages called heavy | Rated heavy too | False alarms | Rated heavy, missed | "
        "Precision | Recall | Right on heavy or not |", "|---|---|---|---|---|---|---|---|",
        f"| Provisional rules | {_row(found['rules'], True)} |",
        f"| Trained model, held out, the shipped cut | {_row(found['model'], False)} |",
        f"| Trained model, held out, the cut held out too | {_row(found['nested'], False)} |",
        "",
        f"Rank correlation with the mean ratings: rules (signs shown, 0 to 3) "
        f"**{found['rules_rho']:.3f}**, held-out model **{found['model_rho']:.3f}**. The "
        f"difference, bootstrapped over pages {BOOTSTRAPS} times, has a 95% interval of "
        f"{found['gap'][0]:+.3f} to {found['gap'][1]:+.3f}. The pages the rules call heavy "
        f"average {found['rules_called_mean']:.2f} against {found['rules_other_mean']:.2f} for "
        f"the rest. The rules' thresholds were never fitted to ratings, but they were read "
        f"off this corpus's spread, so neither side is wholly on unseen ground for its "
        f"thresholds. The second model row is the fair one: its cut was chosen without the "
        f"page it scores.", "",
        "### Where they agree and where they differ", "",
        "The model as shipped, fitted to all 50 pages, for a person who has not said:", "",
        "| | Rules: ordinary, level 2 | Rules: heavy, level 3 |", "|---|---|---|",
        f"| Model: level 2 | **{len(neither)}** | {len(only_rules)} |",
        f"| Model: level 3 | {len(only_model)} | **{len(both_heavy)}** |", "",
        f"They agree on **{len(neither) + len(both_heavy)} of {len(pages)}**. Of the "
        f"{len(differ)} where they differ, the raters side with the model on {model_right} "
        f"and with the rules on {len(differ) - model_right}, the raters' side being heavy "
        f"for a mean of 3.5 or more and not heavy otherwise.", "",
        "| Page | Model | Rules | The rules' signs |", "|---|---|---|---|",
        *[f"| {p.name} | {p.rating:.2f}, level {p.start_level} | level {p.rules_level} | "
          f"{', '.join(p.signs) or 'none'} |" for p in sorted(differ, key=lambda p: -p.rating)], "",
        "### The rules' logged decisions, replayed", "",
        f"Every `start` decision in `data/steps.jsonl`: {sum(e['rows'] for e in logged)} rows, "
        f"{len(logged)} distinct pages, from replicas and scripts, no person's choice of "
        "page. The level logged includes any level the person chose.", "",
        "| Rows | Controls | Text density | Logged levels | Rules: heavy | Model | Model's page level |",
        "|---|---|---|---|---|---|---|",
        *[f"| {e['rows']} | {e['controls']} | {e['text_density']:g} | "
          + ", ".join(f"{k}: {v}" for k, v in sorted(e['levels'].items()))
          + f" | {'yes' if e['rules_heavy'] else 'no'} | {e['rating']:.2f} | {e['level']} |"
          for e in logged], "",
        "### The environment the product runs in", "",
        f"The model was fitted to the headless rows. Of {both['pages']} pages read in both "
        f"environments, the score differs by {both['mean_gap']:.3f} on average and "
        f"{both['largest']:.3f} at most, and the page's level changes on "
        f"**{len(both['changed'])}**"
        + (": " + "; ".join(f"{k[0]} [{k[1]}], {a:.2f} (level {la}) headless, {b:.2f} (level "
                            f"{lb}) in the host" for k, a, la, b, lb in both['changed'])
           if both['changed'] else "") + ".", "",
        "### How much the handling of the data matters", "",
        "Pooled held-out figures over 40 shuffles of the folds. Only the first row is the "
        "model; the others are checks, and taking raters out because they disagree raises "
        "alpha by construction.", "",
        "| Data | Raters | Pages | Fewest ratings | Alpha | R² | Mean absolute error |",
        "|---|---|---|---|---|---|---|",
        *[f"| {c['name']} | {c['raters']} | {c['pages']} | {c['fewest']} | {c['alpha']:.3f} | "
          f"{c['r2'][0]:.3f} ± {c['r2'][1]:.3f} | {c['mae'][0]:.3f} ± {c['mae'][1]:.3f} |"
          for c in cases], "",
        *([f"Do the pages under the floor help or hurt? Scored only on the {helped['pages']} "
           f"pages at the floor, the same held-out pages either way, mean absolute error is "
           f"**{helped['alone']:.3f}** fitted to those pages alone and "
           f"**{helped['added']:.3f}** with the pages under the floor added to the fit.", ""]
          if helped else []),
        *([against, ""] if against else []),
        "### Each page, and why", "",
        f"The model as shipped, `{model.version}`. Level is the page's own: {model.calm:.2f} and "
        f"{model.heavy:.2f} divide it. The reasons are what moved the score most from the "
        f"average page ({model.intercept:.2f}). `data/estimator_pages.json` has the same. "
        "Per-page rated means are not committed (DECISIONS.md, *The trained model is committed; "
        "the ratings are not*).", "",
        "| Page | Kind | Score | Level | Rules' level | Why |", "|---|---|---|---|---|---|",
        *[f"| {p.name} | {p.kind} | {p.rating:.2f} | {p.level} | {p.rules_level} | "
          f"{', '.join(p.reasons) or 'much like the average page'} |"
          for p in sorted(pages, key=lambda p: -p.rating)],
    ]
    return "\n".join(lines) + "\n"


def save_pages(pages: list[Page], model: page_model.PageModel, path: Path) -> None:
    path.write_text(json.dumps({"model": model.version, "cuts": [model.calm, model.heavy],
                                "pages": [{
        "url": p.key[0], "state": p.key[1], "kind": p.kind, "score": p.rating, "level": p.level,
        "rules_level": p.rules_level, "reasons": list(p.reasons),
        "sentence": f"{p.rating:.1f} of 5, level {p.level}: "
                    f"{', '.join(p.reasons) or 'much like the average page'}.",
    } for p in sorted(pages, key=lambda p: -p.rating)]}, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def save_with_ratings(pages: list[Page], path: Path) -> None:
    """Beside the rated means, so this stays out of the repository."""
    lines = ["| Page | Ratings | Rated | Held-out | Shipped score | Level | Rules |",
             "|---|---|---|---|---|---|---|"]
    lines += [f"| {p.name} | {p.ratings} | {p.rated:.2f} | {p.held_out:.2f} | {p.rating:.2f} | "
              f"{p.level} | {p.rules_level} |" for p in sorted(pages, key=lambda p: -p.rated)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(csvs: list[Path], ratings_path: Path = train.RATINGS, corpus_path: Path = train.CORPUS,
        model_path: Path = train.COEFFICIENTS, evaluation: Path | None = train.EVALUATION,
        pages_path: Path = PAGES, scratch: Path = SCRATCH, steps: Path = STEPS,
        pictures_path: Path | None = train.PICTURES,
        mapping_path: Path = from_form.MAPPING) -> str:
    model = page_model.load(model_path)
    if model is None:
        raise SystemExit(f"no usable model at {model_path}; train one first")
    saved = json.loads(model_path.read_text(encoding="utf-8"))
    ratings = train.read_ratings(ratings_path)
    corpus, _ = train.read_corpus(corpus_path)
    pictures = train.read_pictures(pictures_path) if pictures_path is not None else None
    trained = train.train(ratings, corpus, min_ratings=saved["min_ratings"], pictures=pictures)
    assert trained.x is not None and trained.y is not None
    usable = train.paired(ratings, corpus, pictures)[0] if pictures is not None else ratings
    held_out, _ = train.held_out_predictions(trained.x, trained.y)
    pages = pages_of(trained, model, corpus, held_out)
    levels = train.choose_levels(trained.x, trained.y, held_out)
    found = compare(pages, held_out, model.heavy, levels.nested_bands)
    logged = replay_logged(model, steps)
    both = environments(model)
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    cases, against, helped = sensitivity(usable, corpus, trained, csvs, mapping)

    scratch.mkdir(parents=True, exist_ok=True)
    charts = [scratch / "feature_importance.svg", scratch / "predicted_against_rated.svg"]
    charts[0].write_text(importance_chart(trained), encoding="utf-8")
    charts[1].write_text(scatter_chart(pages, (model.calm, model.heavy)), encoding="utf-8")
    render(charts)
    save_with_ratings(pages, scratch / "pages_with_ratings.md")
    save_pages(pages, model, pages_path)

    text = section(pages, found, logged, both, cases, against, helped, model,
                   banner(conditions()), datetime.now().astimezone())
    if evaluation is not None:
        with evaluation.open("a", encoding="utf-8") as out:
            out.write("\n---\n\n" + text)
    return text


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--csv", type=Path, action="append", default=[],
                        help="a form's responses, for the check with phone raters put back")
    parser.add_argument("--no-write", action="store_true", help="print; leave EVALUATION.md alone")
    args = parser.parse_args()
    print(run(args.csv, evaluation=None if args.no_write else train.EVALUATION))


if __name__ == "__main__":
    main()
