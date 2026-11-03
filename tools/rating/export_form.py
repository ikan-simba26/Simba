"""The rating pictures as two Google Forms' folder, for raters who cannot come in.

    python -m tools.rating.export_form          # writes .scratch/rating-form/

**Two sets of 30** (2026-10-23; DECISIONS.md, *Two sets of 30*). The 50
rateable pages are split into Set 1 and Set 2, 25 each, alike in their
features (`session.split`). Each set lends three of its pages — a calm one, a
middling one and a heavy one (`session.anchors`) — to the other, so that both
groups of raters rate those six pages and can be compared on them. With two
repeats, a form is 25 + 3 + 2 = 30 pictures.

Writes `P01.png` to `P50.png`, one per page in the order of their ids, then
the repeats, `P51` and `P52` for Set 1 and `P53` and `P54` for Set 2, each a
copy of one of the set's own pages (never an anchor) shown again at least
`MIN_GAP` pictures later. An anchor keeps its own name in both forms. And
`E1.png` and `E2.png`: the two worked examples shown before the first picture,
neither of them among the 50 (`examples.py`).

**Each form has one fixed order.** Google Forms cannot shuffle a picture
together with its question when the form is made by a script, so each set's
pictures are in an order fixed by a seed (`session.plan`). The A/B forms in
reverse order (2026-10-22) are gone: a form of 30 leaves far less room for
tiredness to fall on the same pages.

Beside the pictures: `mapping.json` — which page each name is, the hash of the
exact picture, the two sets, each form's order, how alike the sets are, the
examples, and the wording of every question — which `make_form.gs` reads to
build the forms, `from_form.py` reads to turn their answers back into rows,
and the in-person tool reads for its sets (`serve.py`). The same mapping is
written to `data/rating/form.json`, which is committed, so the answers stay
readable when `.scratch/` is gone. `make_form.gs` and `README.md` are copied
in from `tools/rating/form/`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import statistics
import sys
from datetime import datetime
from pathlib import Path

from backend.estimator.train import CORPUS, ENVIRONMENT, FEATURES
from tools.rating import examples as worked
from tools.rating.serve import LABELS, MANIFEST, QUESTION, SCALE
from tools.rating.session import (ANCHORS, MIN_GAP, REPEATS, SETS, anchors, feature_ranks,
                                  heaviness, imbalance, plan, split)

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = REPO / ".scratch" / "rating-form"
RECORD = REPO / "data" / "rating" / "form.json"
#: Fixed, so the sets, orders and repeats can be made again from the manifest.
SEED = 20261023
PICTURES_PER_FORM = 30

#: Every question the forms ask, in the words they ask them. `make_form.gs`
#: builds the forms from these, and `from_form.py` finds the answers by them.
QUESTIONS = {
    "intro": ("About 5-7 minutes. Please fill this in on a laptop or desktop computer, "
              "not a phone: the pictures are too small on a phone to judge."),
    "consent": {
        "title": "Do you agree to take part?",
        "help": ("This is part of a final-year university project on making websites "
                 "easier to use. You will see 30 pictures of web pages and answer one "
                 "question about each, choosing one of five answers. It takes about 5-7 "
                 "minutes. We do not ask for your name or email address: we record only "
                 "your answers, the time you send them, and the three questions on the "
                 "next page. Your answers are used to train and test the project's "
                 "software and may be reported in summary in the project's write-up. "
                 "You must be 18 or over. You can stop at any time by closing this "
                 "page, and nothing is sent."),
        "yes": "Yes, I agree to take part",
        "no": "No",
    },
    "device": {
        "title": "What are you using to fill in this form?",
        "choices": {"laptop": "Laptop", "desktop": "Desktop computer", "phone": "Phone"},
    },
    "age": {
        "title": "What is your age range?",
        "choices": ["18-24", "25-34", "35-44", "45-54", "55-64", "65 or over",
                    "Prefer not to say"],
    },
    "computing": {
        "title": "Do you study or work in computing?",
        "choices": {"yes": "Yes", "no": "No"},
    },
    "examples": {
        "title": "Two examples first",
        "help": ("For each picture, imagine you had to use that page to get something "
                 "done, and choose the answer that fits. Here are two pages that are not "
                 "in the form, with the answer we would give."),
        "answer": "Answer: {label}.",
    },
    "rating": {
        "title": QUESTION,
        "help": ("Imagine you had to use this page to get something done. Go with your "
                 "first impression; there are no right answers."),
        "labels": list(LABELS), "scale": list(SCALE),
    },
}
#: The rating question's title in the form: the question, then the picture's
#: name, which is how an answer in the form's CSV is matched to its picture.
RATING_TITLE = "{question} [{name}]"


class ExportRefused(Exception):
    """The pictures on disk cannot be exported as they are, and why."""


def rateable(manifest: Path) -> list[dict]:
    """The manifest's pages that have a picture, sorted by id, each checked
    against the hash the manifest recorded for it."""
    data = json.loads(manifest.read_text(encoding="utf-8"))
    images = manifest.parent / "pages"
    pages = []
    for row in sorted(data["pages"], key=lambda r: r["id"]):
        if "error" in row:
            continue
        file = images / row["file"]
        if not file.exists():
            raise ExportRefused(f"{file} is missing; run python -m tools.rating.capture")
        if hashlib.sha256(file.read_bytes()).hexdigest() != row["sha256"]:
            raise ExportRefused(f"{file} is not the picture the manifest recorded")
        pages.append(row)
    return pages


def features_of(pages: list[dict], corpus: Path) -> dict[str, dict[str, float]]:
    """Each page's nine features, from the corpus run its picture came from."""
    data = json.loads(corpus.read_text(encoding="utf-8"))
    rows = {(r["url"], r["state"]): r for r in data["results"][ENVIRONMENT]
            if "error" not in r}
    found: dict[str, dict[str, float]] = {}
    for page in pages:
        row = rows.get((page["url"], page["state"]))
        if row is None or row.get("run") != page.get("run"):
            raise ExportRefused(f"{page['id']} has no {ENVIRONMENT} features from its "
                                f"picture's run in {corpus}; recapture with "
                                f"python -m tools.rating.capture")
        found[page["id"]] = {name: float(row[name]) for name in FEATURES}
    return found


def mapping(manifest: Path = MANIFEST, corpus: Path = CORPUS, seed: int = SEED,
            examples: list[dict] | None = None) -> dict:
    """Which page each name is, the two sets, each form's order, and the questions.

    A name from `P51` up carries `of`: the name of the same page's own picture."""
    pages = rateable(manifest)
    if len(pages) < 2 * (ANCHORS + REPEATS + 1):
        raise ExportRefused(f"only {len(pages)} rateable pages in {manifest}")
    features = features_of(pages, corpus)
    heavy = heaviness(features)
    names = {row["id"]: f"P{n:02d}" for n, row in enumerate(pages, start=1)}
    pictures: dict[str, dict] = {}
    for row in pages:
        pictures[names[row["id"]]] = {
            "page": row["id"], "url": row["url"], "state": row["state"],
            "kind": row["kind"], "file": row["file"], "sha256": row["sha256"],
            "heaviness": round(heavy[row["id"]], 3)}

    groups = split(features, seed, {row["id"]: row["kind"] for row in pages})
    lends = {s: anchors(groups[s], heavy) for s in SETS}
    sets: dict[str, dict] = {}
    orders: dict[str, list[str]] = {}
    for s in SETS:
        other = SETS[1] if s == SETS[0] else SETS[0]
        shown = groups[s] + lends[other]
        repeatable = set(groups[s]) - set(lends[s])
        order: list[str] = []
        repeats: list[str] = []
        for item in plan(sorted(shown), seed + s, repeats=REPEATS, repeatable=repeatable):
            if not item["repeat"]:
                order.append(names[item["page"]])
                continue
            name = f"P{len(pictures) + 1:02d}"
            pictures[name] = {**pictures[names[item["page"]]], "of": names[item["page"]]}
            order.append(name)
            repeats.append(name)
        sets[str(s)] = {"own": sorted(names[p] for p in groups[s]),
                        "lends": [names[p] for p in lends[s]],
                        "anchors": [names[p] for p in lends[other]],
                        "repeats": repeats}
        orders[str(s)] = order

    ranks = feature_ranks(features)
    balance = {name: [round(statistics.mean(features[p][name] for p in groups[s]), 3)
                      for s in SETS] for name in FEATURES}
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if examples is None:
        examples = worked.read(folder=manifest.parent / "examples",
                               record=manifest.parent / "examples.json")
    return {
        "made_by": "python -m tools.rating.export_form",
        "run": data.get("run", {}).get("id"),
        "seed": seed, "repeats": REPEATS, "anchors": ANCHORS, "min_gap": MIN_GAP,
        "pictures": pictures, "sets": sets, "orders": orders,
        "balance": {"largest_rank_difference": round(imbalance(groups, ranks), 3),
                    "means": balance},
        "examples": [{"name": e["name"], "file": e["file"], "url": e["url"],
                      "sha256": e["sha256"], "answer": e["answer"],
                      "label": LABELS[e["answer"] - SCALE[0]], "says": e["says"]}
                     for e in examples],
        "questions": QUESTIONS, "rating_title": RATING_TITLE,
    }


def export(out: Path = OUT, manifest: Path = MANIFEST, record: Path | None = RECORD,
           seed: int = SEED, corpus: Path = CORPUS) -> dict:
    """Write the pictures, the examples, the mapping, the form script and its
    instructions."""
    if record is not None and record.exists() \
            and "3" in json.loads(record.read_text(encoding="utf-8"))["orders"]:
        raise ExportRefused(f"{record} has Set 3, which this would remove. Sets 1 and 2 "
                            f"have answers and must not be exported again.")
    examples = worked.read(folder=manifest.parent / "examples",
                           record=manifest.parent / "examples.json")
    made = mapping(manifest, corpus, seed, examples)
    made["exported_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    out.mkdir(parents=True, exist_ok=True)
    for stale in [*out.glob("P*.png"), *out.glob("E*.png")]:
        stale.unlink()
    images = manifest.parent / "pages"
    for name, picture in made["pictures"].items():
        shutil.copyfile(images / picture["file"], out / f"{name}.png")
    for example in examples:
        shutil.copyfile(example["path"], out / example["file"])
    text = json.dumps(made, indent=2, ensure_ascii=False) + "\n"
    (out / "mapping.json").write_text(text, encoding="utf-8")
    for name in ("make_form.gs", "README.md"):
        shutil.copyfile(HERE / "form" / name, out / name)
    if record is not None:
        record.write_text(text, encoding="utf-8")
    return made


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    try:
        made = export(args.out)
    except (ExportRefused, worked.ExamplesMissing) as reason:
        print(f"Not exported: {reason}")
        raise SystemExit(2) from None
    for s, chosen in made["sets"].items():
        repeats = ", ".join(f"{n} = {made['pictures'][n]['of']}" for n in chosen["repeats"])
        print(f"Set {s}: {len(made['orders'][s])} pictures — {len(chosen['own'])} own, "
              f"anchors {', '.join(chosen['anchors'])}, repeats {repeats}")
    print(f"sets alike within {made['balance']['largest_rank_difference']} of a rank "
          f"on every feature; examples {', '.join(e['file'] for e in made['examples'])}")
    print(f"{len(made['pictures'])} pictures in {args.out}; mapping also written to "
          f"{RECORD.relative_to(REPO)}")


if __name__ == "__main__":
    main()
