"""The comparison's two charts: well-formed SVG, one mark per number, nothing invented.
On the synthetic study `backend/estimator/test_train_visual.py` makes."""

import csv
import xml.etree.ElementTree as ET
from pathlib import Path

from backend.estimator.test_train_visual import compared, quick, world  # noqa: F401
from tools.evaluation import visual_charts

SVG = "{http://www.w3.org/2000/svg}"


def drawn(tmp_path: Path):
    found = compared(world(tmp_path / "study"))
    return found, visual_charts.write(found, tmp_path / "charts")


def test_both_charts_and_their_tables_are_written(tmp_path: Path) -> None:
    _, written = drawn(tmp_path)
    assert {p.name for p in written} == {"importance.svg", "predicted.svg", "importance.csv",
                                         "predicted.csv"}
    for path in written:
        if path.suffix == ".svg":
            assert ET.parse(path).getroot().tag == f"{SVG}svg"


def test_every_page_is_a_point_in_every_panel(tmp_path: Path) -> None:
    found, _ = drawn(tmp_path)
    root = ET.parse(tmp_path / "charts" / "predicted.svg").getroot()
    tips = [t.text for t in root.iter(f"{SVG}title")]
    assert len(tips) == len(found.pages) * 3


def test_every_feature_an_arm_has_is_a_bar_and_no_other(tmp_path: Path) -> None:
    found, _ = drawn(tmp_path)
    root = ET.parse(tmp_path / "charts" / "importance.svg").getroot()
    tips = [t.text or "" for t in root.iter(f"{SVG}title")]
    assert len(tips) == sum(len(m) for m in found.importances.values()) == 9 + 14 + 5
    assert not any("The five alone, links:" in tip for tip in tips)


def test_the_tables_hold_the_numbers_drawn(tmp_path: Path) -> None:
    found, _ = drawn(tmp_path)
    with (tmp_path / "charts" / "predicted.csv").open(encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == len(found.pages)
    assert sum(row["pakistani"] == "True" for row in rows) == 15
    first = rows[0]
    assert float(first["held_out_old"]) == round(float(found.arms["old"].predicted[:, 0].mean()), 3)


def test_no_point_falls_outside_its_panel(tmp_path: Path) -> None:
    """Found by looking: with the scale cut at 4.5, a page predicted 4.8 was drawn
    over the panel's title."""
    drawn(tmp_path)
    root = ET.parse(tmp_path / "charts" / "predicted.svg").getroot()
    ys = [float(c.get("cy")) for c in root.iter(f"{SVG}circle") if c.get("r") == "4.5"]
    ys += [float(r.get("y")) + 4.5 for r in root.iter(f"{SVG}rect") if r.get("width") == "9"]
    assert ys and min(ys) >= 116 and max(ys) <= 116 + 280
