"""Set 3: Pakistani pages for raters, so that a model can learn what it cannot see.

    python -m tools.rating.export_set3          # writes .scratch/rating-form-set3/

The overwhelm index found that the model calls Pakistan's public sites calm while
their pictures are busy, and nothing tested that: no busy Pakistani page has been
rated. Set 3 is the test. Twenty pictures, about 3-4 minutes:

- **15 of the sites read for `tools/evaluation/visual_features.py`**, each picture
  from the same load as its fourteen features. `choose` takes them to cover the
  range of the five new features and every category;
- **3 anchors**, of the six pages Sets 1 and 2 share: the calmest, the middle and
  the heaviest by what raters said, so that Set 3's raters can be held against
  theirs on the same pictures (`anchors`). These are the pictures already rated;
- **2 repeats** of Set 3's own pages, shown again at least `MIN_GAP` later.

**It adds to the mapping and changes nothing in it.** Answers to Sets 1 and 2 are
matched to pictures by name, so P01 to P54, the two orders and every word of those
forms stay exactly as they are; a test holds that. Set 3's own wording, the time
and the number of pictures, is under `overrides`. The new names start at P55.

**Its pictures are frozen the moment they are chosen.** They go to
`data/rating/pages/` beside the others, not committed, with their hashes in
`data/rating/set3.json`, which is. That file is a second manifest rather than
more rows in `pages.json` because `train.py` asks for eight ratings on every page
in that one, which would stop the current model being retrained on Sets 1 and 2.

Once a form has answers this must not make a different Set 3: run again it either
makes the same one or refuses. The folder has only what Set 3's form needs, so a
form made from it cannot disturb the other two.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from backend.estimator.page_model import VISUAL_FEATURES
from tools.evaluation.visual_features import OUT as MEASURED
from tools.evaluation.visual_features import RECORD as VISUAL
from tools.rating.export_form import HERE, OUT as FOLDER_OF_SETS, RECORD
from tools.rating.export_form import ExportRefused
from tools.rating.serve import RATINGS
from tools.rating.session import MIN_GAP, REPEATS, feature_ranks, heaviness, plan

REPO = Path(__file__).resolve().parents[2]
OUT = FOLDER_OF_SETS.with_name("rating-form-set3")
MANIFEST = REPO / "data" / "rating" / "set3.json"
PAGES = REPO / "data" / "rating" / "pages"
SET = "3"
#: Fixed, so that the choice and the order can be made again.
SEED = 20261102
OWN_PAGES = 15
ANCHORS = 3
#: Every category gets at least this many pages, and none more than `MOST`.
LEAST, MOST = 2, 3
FIRST_NAME = 55
#: Pages no rater should be shown, by eye, each with why. A rule on flatness would
#: not have found this one, at 0.53, and a rule made for one page is a guess.
EXCLUDED = {"www-mepco-com-pk": "caught mid-load: the site's own loader, at 91%, over a pop-up"}
PICTURES = OWN_PAGES + ANCHORS + REPEATS

OVERRIDES = {
    "intro": ("About 3-4 minutes. Please fill this in on a laptop or desktop computer, "
              "not a phone: the pictures are too small on a phone to judge."),
    "consent_help": ("This is part of a final-year university project on making websites "
                     "easier to use. You will see 20 pictures of web pages and answer one "
                     "question about each, choosing one of five answers. It takes about 3-4 "
                     "minutes. We do not ask for your name or email address: we record only "
                     "your answers, the time you send them, and the three questions on the "
                     "next page. Your answers are used to train and test the project's "
                     "software and may be reported in summary in the project's write-up. "
                     "You must be 18 or over. You can stop at any time by closing this "
                     "page, and nothing is sent."),
}


def scored_sites(record: Path = VISUAL) -> dict[str, dict]:
    """The sites read with all fourteen features, by their page id."""
    data = json.loads(record.read_text(encoding="utf-8"))
    rows = [row for row in data["sites"]["rows"] if row["status"] == "scored"]
    return {Path(row["screenshot"]).stem: row for row in rows}


def choose(rows: dict[str, dict], count: int = OWN_PAGES) -> list[str]:
    """`count` pages spread over the new features, by ranks: each next page is the
    one furthest from every page chosen so far, so the ends of each feature come
    in early. A category under `LEAST` is seen to before anything else fills the
    places left, and one at `MOST` takes no more. Ties go by id."""
    features = {key: {name: float(row[name]) for name in VISUAL_FEATURES}
                for key, row in rows.items()}
    ranks = feature_ranks(features)
    category = {key: row["category"] for key, row in rows.items()}
    chosen: list[str] = []
    held: Counter[str] = Counter()

    def distance(one: str, two: str) -> float:
        return sum(abs(ranks[name][one] - ranks[name][two]) for name in VISUAL_FEATURES)

    def eligible() -> list[str]:
        short = sum(max(0, LEAST - held[c]) for c in set(category.values()))
        left = count - len(chosen)
        pool = [key for key in sorted(rows) if key not in chosen and held[category[key]] < MOST]
        if short >= left:
            pool = [key for key in pool if held[category[key]] < LEAST]
        return pool

    middle = {name: statistics.median(ranks[name].values()) for name in VISUAL_FEATURES}
    start = max(sorted(rows), key=lambda key: sum(abs(ranks[name][key] - middle[name])
                                                  for name in VISUAL_FEATURES))
    chosen.append(start)
    held[category[start]] += 1
    while len(chosen) < count:
        pool = eligible()
        if not pool:
            raise ExportRefused(f"only {len(chosen)} pages can be chosen under the category "
                                f"limits, of {count}")
        best = max(pool, key=lambda key: min(distance(key, other) for other in chosen))
        chosen.append(best)
        held[category[best]] += 1
    return sorted(chosen)


def coverage(rows: dict[str, dict], chosen: list[str]) -> dict[str, dict[str, float]]:
    """Each new feature's range over all the sites and over the pages chosen."""
    found: dict[str, dict[str, float]] = {}
    for name in VISUAL_FEATURES:
        everything = [float(row[name]) for row in rows.values()]
        picked = [float(rows[key][name]) for key in chosen]
        found[name] = {"lowest": min(everything), "highest": max(everything),
                       "lowest_chosen": min(picked), "highest_chosen": max(picked)}
    return found


def anchors(made: dict, ratings: Path = RATINGS, count: int = ANCHORS) -> list[str]:
    """Of the pages Sets 1 and 2 share, the calmest, the middle and the heaviest
    by what their raters said: the ends are what show a group rating differently."""
    shared = [name for key in ("1", "2") for name in made["sets"][key]["anchors"]]
    pages = {made["pictures"][name]["page"]: name for name in shared}
    means: dict[str, list[int]] = {}
    for line in ratings.read_text(encoding="utf-8").splitlines():
        row = json.loads(line) if line.strip() else None
        if row is not None and row["page"] in pages and not row.get("repeat"):
            means.setdefault(row["page"], []).append(int(row["rating"]))
    missing = sorted(set(pages) - set(means))
    if missing:
        raise ExportRefused(f"no ratings of anchors {', '.join(missing)} in {ratings}")
    ordered = sorted(pages, key=lambda page: (statistics.mean(means[page]), page))
    last = len(ordered) - 1
    return sorted(pages[ordered[round(k * last / (count - 1))]] for k in range(count))


def add_set3(made: dict, rows: dict[str, dict], chosen: list[str], anchored: list[str],
             seed: int = SEED) -> dict:
    """The mapping with Set 3 added. Nothing already in it is changed."""
    if SET in made["orders"]:
        raise ExportRefused("the mapping already has Set 3")
    out = json.loads(json.dumps(made))
    pictures = out["pictures"]
    heavy = heaviness({key: {name: float(rows[key][name]) for name in VISUAL_FEATURES}
                       for key in chosen})
    names = {key: f"P{FIRST_NAME + n:02d}" for n, key in enumerate(chosen)}
    for key in chosen:
        row = rows[key]
        pictures[names[key]] = {
            "page": key, "url": row["url"], "state": "as it loads", "kind": row["category"],
            "file": row["screenshot"], "sha256": row["sha256"],
            "heaviness": round(heavy[key], 3)}
    by_page = {key: name for key, name in names.items()}
    by_page |= {pictures[name]["page"]: name for name in anchored}
    order: list[str] = []
    repeats: list[str] = []
    for item in plan(sorted(by_page), seed, repeats=REPEATS, repeatable=set(chosen)):
        if not item["repeat"]:
            order.append(by_page[item["page"]])
            continue
        name = f"P{FIRST_NAME + len(chosen) + len(repeats):02d}"
        pictures[name] = {**pictures[by_page[item["page"]]], "of": by_page[item["page"]]}
        order.append(name)
        repeats.append(name)
    out["sets"][SET] = {"own": sorted(names.values()), "lends": [], "anchors": list(anchored),
                        "repeats": repeats}
    out["orders"][SET] = order
    out.setdefault("overrides", {})[SET] = OVERRIDES
    return out


def without_set3(made: dict) -> dict:
    """The mapping as it was before Set 3, which the seed in `export_form` makes."""
    out = json.loads(json.dumps(made))
    third = out["sets"].pop(SET, None)
    out["orders"].pop(SET, None)
    out.pop("overrides", None)
    if third is not None:
        for name in third["own"] + third["repeats"]:
            del out["pictures"][name]
    return out


def manifest(rows: dict[str, dict], chosen: list[str], run: dict) -> dict:
    """Set 3's pictures as `train.read_pictures` reads a manifest."""
    return {"run": run, "viewport": {"width": 1280, "height": 800}, "device_scale_factor": 1,
            "scrollbars": "hidden", "corpus": "data/visual_features.json, the same run",
            "pages": [{"id": key, "url": rows[key]["url"], "state": "as it loads",
                       "kind": rows[key]["category"], "run": run["id"],
                       "file": rows[key]["screenshot"], "sha256": rows[key]["sha256"],
                       "title": rows[key].get("title", ""), "site": rows[key]["site"]}
                      for key in chosen]}


def checked_picture(folder: Path, row: dict) -> Path:
    path = folder / row["screenshot"]
    if not path.exists():
        raise ExportRefused(f"{path} is missing; the sites' pictures were not kept")
    if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
        raise ExportRefused(f"{path} is not the picture read with its features")
    return path


def export(out: Path = OUT, record: Path = RECORD, visual: Path = VISUAL,
           measured: Path = MEASURED / "sites", pages: Path = PAGES,
           written: Path = MANIFEST, ratings: Path = RATINGS,
           examples: Path = REPO / "data" / "rating" / "examples") -> dict:
    """Everything Set 3's form needs, and the two files that keep it."""
    made = json.loads(record.read_text(encoding="utf-8"))
    before = without_set3(made)
    rows = {key: row for key, row in scored_sites(visual).items() if key not in EXCLUDED}
    chosen = choose(rows)
    whole = add_set3(before, rows, chosen, anchors(before, ratings))
    if SET in made["orders"] and made != whole:
        raise ExportRefused("Set 3 is already in the mapping and this would make a different "
                            "one. Once its form has answers it must not change.")
    for key in chosen:
        source = checked_picture(measured, rows[key])
        pages.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, pages / rows[key]["screenshot"])
    if out.exists():
        for stale in [*out.glob("P*.png"), *out.glob("E*.png")]:
            stale.unlink()
    out.mkdir(parents=True, exist_ok=True)
    for name in whole["orders"][SET]:
        picture = whole["pictures"][name]
        shutil.copyfile(pages / picture["file"], out / f"{name}.png")
    for example in whole["examples"]:
        shutil.copyfile(examples / example["file"], out / example["file"])
    text = json.dumps(whole, indent=2, ensure_ascii=False) + "\n"
    (out / "mapping.json").write_text(text, encoding="utf-8")
    for name in ("make_form.gs", "README.md"):
        shutil.copyfile(HERE / "form" / name, out / name)
    record.write_text(text, encoding="utf-8")
    run = json.loads(visual.read_text(encoding="utf-8"))["sites"]["run"]
    written.write_text(json.dumps(manifest(rows, chosen, run), indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    return {"made": whole, "chosen": chosen, "rows": rows}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    try:
        done = export(args.out)
    except ExportRefused as reason:
        print(f"Not exported: {reason}")
        raise SystemExit(2) from None
    made, chosen, rows = done["made"], done["chosen"], done["rows"]
    chosen_set = made["sets"][SET]
    print(f"Set 3: {len(made['orders'][SET])} pictures: {len(chosen_set['own'])} own, anchors "
          f"{', '.join(chosen_set['anchors'])}, repeats "
          + ", ".join(f"{n} = {made['pictures'][n]['of']}" for n in chosen_set["repeats"]))
    print(Counter(rows[key]["category"] for key in chosen).most_common())
    for key in chosen:
        print(f"  {rows[key]['site'][:34]:<34} {rows[key]['category'][:20]:<20} " + "  ".join(
            f"{name} {float(rows[key][name]):.2f}" for name in VISUAL_FEATURES))
    for name, found in coverage(rows, chosen).items():
        print(f"  {name:<20} all {found['lowest']:.2f} to {found['highest']:.2f}; "
              f"chosen {found['lowest_chosen']:.2f} to {found['highest_chosen']:.2f}")
    print(f"{args.out}; {RECORD.relative_to(REPO)}; {MANIFEST.relative_to(REPO)}")


if __name__ == "__main__":
    main()
