"""Two charts of `train_visual`'s comparison, as plain SVG: no plotting library.

    python -m backend.estimator.train_visual --min-ratings 5 --charts

- `importance.svg`: each feature's held-out importance (R² lost when it is shuffled,
  with its spread over folds) in the old model, the new one and the five alone, one
  panel each, on one shared scale and one feature order (the new model's).
- `predicted.svg`: each page's held-out prediction (the mean over the shuffles)
  against people's mean rating, one panel per arm, the Pakistani pages marked apart.
  Points on the diagonal are predicted exactly.

Each chart has a CSV beside it with the numbers it draws, as its table view, and
every mark has a tooltip (`<title>`). Colours are the first two slots of the
dataviz reference palette, which pass its colour-blindness checks as a pair; the
two kinds of page also differ in shape, so colour is never the only cue.
"""

from __future__ import annotations

import csv
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from backend.estimator.train_visual import Comparison

SURFACE, INK, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
RATED, SITES = "#2a78d6", "#eb6834"
FONT = "font-family='Segoe UI, Helvetica, Arial, sans-serif'"
PANELS = ("old", "new", "visual")


def _text(x: float, y: float, words: str, size: int = 12, anchor: str = "start",
          colour: str = INK, weight: str = "normal") -> str:
    return (f"<text x='{x:.1f}' y='{y:.1f}' font-size='{size}' text-anchor='{anchor}' "
            f"fill='{colour}' font-weight='{weight}' {FONT}>{escape(words)}</text>")


def _svg(width: int, height: int, body: list[str], title: str) -> str:
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' "
            f"viewBox='0 0 {width} {height}' role='img' aria-label='{escape(title)}'>"
            f"<rect width='{width}' height='{height}' fill='{SURFACE}'/>" + "".join(body)
            + "</svg>\n")


def importance_svg(found: Comparison) -> str:
    from backend.estimator.train_visual import LABELS
    order = [name for name, _ in sorted(found.importance.items(), key=lambda kv: -kv[1][0])]
    shown = [arm for arm in PANELS if arm in found.importances]
    highs = [lost + sd for arm in shown for lost, sd, _ in found.importances[arm].values()]
    lows = [lost - sd for arm in shown for lost, sd, _ in found.importances[arm].values()]
    low, high = min(-0.05, min(lows)), max(0.05, max(highs))
    label_w, panel_w, row, top, gap = 150, 230, 24, 78, 24
    width = label_w + len(shown) * (panel_w + gap)
    height = top + row * len(order) + 56

    def at(value: float, left: float) -> float:
        return left + (value - low) / (high - low) * panel_w

    body = [_text(16, 28, "Which features carry the prediction, held out", 16, weight="600"),
            _text(16, 48, "R² lost when one feature is shuffled; the line is ± one sd over "
                  "folds. Empty rows: the arm does not have that feature.", 12, colour=MUTED)]
    for at_row, feature in enumerate(order):
        y = top + at_row * row + row / 2
        body.append(_text(label_w - 10, y + 4, feature, 12, "end", MUTED))
    ticks = [t for t in np.round(np.arange(np.floor(low * 10) / 10, high + 0.001, 0.1), 2)
             if low <= t <= high]
    for n, arm in enumerate(shown):
        left = label_w + n * (panel_w + gap)
        body.append(_text(left, top - 12, LABELS[arm], 13, weight="600"))
        for t in ticks:
            x = at(float(t), left)
            stroke = MUTED if t == 0 else GRID
            body.append(f"<line x1='{x:.1f}' y1='{top}' x2='{x:.1f}' "
                        f"y2='{top + row * len(order)}' stroke='{stroke}' stroke-width='1'/>")
            body.append(_text(x, top + row * len(order) + 16, f"{t:g}", 11, "middle", MUTED))
        for at_row, feature in enumerate(order):
            if feature not in found.importances[arm]:
                continue
            lost, sd, coefficient = found.importances[arm][feature]
            y = top + at_row * row + row / 2
            zero, end = at(0.0, left), at(lost, left)
            x0, x1 = min(zero, end), max(zero, end)
            tip = (f"{LABELS[arm]}, {feature}: R² lost {lost:.3f} ± {sd:.3f}, "
                   f"coefficient {coefficient:+.3f}")
            body.append(f"<g><title>{escape(tip)}</title>"
                        f"<rect x='{x0:.1f}' y='{y - 7:.1f}' width='{max(x1 - x0, 1):.1f}' "
                        f"height='14' rx='3' fill='{RATED}'/>"
                        f"<line x1='{at(lost - sd, left):.1f}' y1='{y:.1f}' "
                        f"x2='{at(lost + sd, left):.1f}' y2='{y:.1f}' stroke='{INK}' "
                        f"stroke-width='1.5'/>"
                        f"<rect x='{at(low, left):.1f}' y='{y - row / 2:.1f}' "
                        f"width='{panel_w}' height='{row}' fill='transparent'/></g>")
        body.append(_text(left + panel_w / 2, top + row * len(order) + 34, "R² lost", 11,
                          "middle", MUTED))
    return _svg(width, height, body, "Feature importance by arm")


def predicted_svg(found: Comparison) -> str:
    from backend.estimator.train_visual import LABELS
    shown = [arm for arm in PANELS if arm in found.arms]
    sites = found.sites if found.sites is not None else np.zeros(len(found.pages), bool)
    size, gap, left0, top = 280, 40, 56, 116
    width = left0 + len(shown) * (size + gap)
    height = top + size + 60
    low, high = 1.0, 5.0  # the whole scale: nothing can fall outside it

    def px(value: float, left: float) -> float:
        return left + (value - low) / (high - low) * size

    def py(value: float) -> float:
        return top + size - (value - low) / (high - low) * size

    body = [_text(16, 28, "Held-out prediction against people's rating, each page", 16,
                  weight="600"),
            _text(16, 48, "Each point is a page predicted by a model that never saw it, "
                  "averaged over 40 shuffles. On the diagonal: exactly right.", 12,
                  colour=MUTED),
            f"<circle cx='22' cy='74' r='5' fill='{RATED}' stroke='{SURFACE}' stroke-width='2'/>",
            _text(32, 78, f"Pages of Sets 1 and 2 ({int((~sites).sum())})", 12, colour=INK),
            f"<rect x='232' y='69' width='10' height='10' fill='{SITES}' stroke='{SURFACE}' "
            f"stroke-width='2'/>",
            _text(248, 78, f"Pakistani pages, Set 3 ({int(sites.sum())})", 12, colour=INK)]
    for n, arm in enumerate(shown):
        left = left0 + n * (size + gap)
        predicted = found.arms[arm].predicted.mean(axis=0)
        error = found.arms[arm].repeated.mae[0]
        body.append(_text(left, top - 12, f"{LABELS[arm]} (error {error:.2f})", 13,
                          weight="600"))
        for t in (1, 2, 3, 4, 5):
            body += [f"<line x1='{px(t, left):.1f}' y1='{top}' x2='{px(t, left):.1f}' "
                     f"y2='{top + size}' stroke='{GRID}'/>",
                     f"<line x1='{left}' y1='{py(t):.1f}' x2='{left + size}' y2='{py(t):.1f}' "
                     f"stroke='{GRID}'/>",
                     _text(px(t, left), top + size + 16, str(t), 11, "middle", MUTED),
                     _text(left - 6, py(t) + 4, str(t), 11, "end", MUTED)]
        body.append(f"<line x1='{px(low, left):.1f}' y1='{py(low):.1f}' x2='{px(high, left):.1f}' "
                    f"y2='{py(high):.1f}' stroke='{MUTED}' stroke-dasharray='4 4'/>")
        for at_page in np.argsort(sites):  # the Pakistani pages drawn last, on top
            key, rated, guess = found.pages[at_page], found.y[at_page], predicted[at_page]
            x, y = px(float(rated), left), py(float(guess))
            tip = f"{key[0]} [{key[1]}]: people {rated:.2f}, predicted {guess:.2f}"
            mark = (f"<rect x='{x - 4.5:.1f}' y='{y - 4.5:.1f}' width='9' height='9' "
                    f"fill='{SITES}' stroke='{SURFACE}' stroke-width='2'/>" if sites[at_page]
                    else f"<circle cx='{x:.1f}' cy='{y:.1f}' r='4.5' fill='{RATED}' "
                         f"stroke='{SURFACE}' stroke-width='2'/>")
            body.append(f"<g><title>{escape(tip)}</title>{mark}"
                        f"<circle cx='{x:.1f}' cy='{y:.1f}' r='9' fill='transparent'/></g>")
        body.append(_text(left + size / 2, top + size + 36, "People's mean rating", 11,
                          "middle", MUTED))
    body.append(f"<text transform='translate(16 {top + size / 2}) rotate(-90)' font-size='11' "
                f"text-anchor='middle' fill='{MUTED}' {FONT}>Predicted, held out</text>")
    return _svg(width, height, body, "Predicted against rated, old, new and the five alone")


def write(found: Comparison, out: Path) -> list[Path]:
    """Both charts and their tables into `out`; the paths written."""
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name, drawn in (("importance.svg", importance_svg(found)),
                        ("predicted.svg", predicted_svg(found))):
        (out / name).write_text(drawn, encoding="utf-8")
        written.append(out / name)
    with (out / "importance.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["arm", "feature", "r2_lost", "sd", "coefficient"])
        for arm, measured in found.importances.items():
            for feature, (lost, sd, coefficient) in measured.items():
                writer.writerow([arm, feature, f"{lost:.4f}", f"{sd:.4f}", f"{coefficient:.4f}"])
    sites = found.sites if found.sites is not None else np.zeros(len(found.pages), bool)
    with (out / "predicted.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["url", "state", "pakistani", "people", *[f"held_out_{a}" for a in found.arms]])
        for at_page, key in enumerate(found.pages):
            writer.writerow([key[0], key[1], bool(sites[at_page]), f"{found.y[at_page]:.3f}",
                             *[f"{arm.predicted[:, at_page].mean():.3f}"
                               for arm in found.arms.values()]])
    written += [out / "importance.csv", out / "predicted.csv"]
    return written
