"""The rating pictures as a Google Form's folder, for raters who cannot come in.

    python -m tools.rating.export_form          # writes .scratch/rating-form/

Writes `P01.png` to `P50.png`, one per rateable page in the order of their
ids, and `P51.png` to `P55.png`, five of them again: the repeats. They are
chosen the way a session chooses its two (`session.plan`), with five instead
of two and a fixed seed, so everyone who fills in either form sees the same
five again, each more than `MIN_GAP` pictures from its other showing.

**Two forms, each in a fixed order.** Google Forms cannot shuffle a picture
together with its question when the form is made by a script, so each form
shows one picture per page in a fixed order: form A in the order `plan`
gives, form B in the reverse of it, so that whatever tiredness does late in
a form falls on different pages in each (DECISIONS.md, *Ratings collected
online*; *Two forms*). Reversing keeps every gap between a page and its
repeat, but in B the name `P51` to `P55` is the first showing and the
original the second; `from_form.py` takes whichever comes later as the
repeat.

Beside the pictures: `mapping.json` — which page each name is, the hash of the
exact picture, both forms' orders, and the wording of every question — which
`make_form.gs` reads to build the form and `from_form.py` reads to turn its
answers back into rows. The same mapping is written to `data/rating/form.json`,
which is committed, so the answers stay readable when `.scratch/` is gone.
`make_form.gs` and `README.md` are copied in from `tools/rating/form/`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

from tools.rating.serve import MANIFEST, QUESTION, SCALE
from tools.rating.session import MIN_GAP, plan

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = REPO / ".scratch" / "rating-form"
RECORD = REPO / "data" / "rating" / "form.json"
REPEATS = 5
#: Fixed, so the forms' orders and repeats can be made again from the manifest.
SEED = 20261022

#: Every question the form asks, in the words it asks them. `make_form.gs`
#: builds the form from these, and `from_form.py` finds the answers by them.
QUESTIONS = {
    "consent": {
        "title": "Do you agree to take part?",
        "help": ("This is part of a final-year university project on making websites "
                 "easier to use. You will see 55 pictures of web pages and rate each "
                 "one from 1 to 7. It takes about 15 minutes. We do not ask for your "
                 "name or email address: we record only your answers, the time you "
                 "send them, and the three questions on the next page. Your answers "
                 "are used to train and test the project's software and may be "
                 "reported in summary in the project's write-up. You must be 18 or "
                 "over. You can stop at any time by closing this page, and nothing "
                 "is sent."),
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
    "rating": {
        "title": QUESTION,
        "help": ("Imagine you had to use this page to get something done. Go with your "
                 "first impression; there are no right answers."),
        "low": "Not at all", "high": "Extremely", "scale": list(SCALE),
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


def mapping(manifest: Path = MANIFEST, seed: int = SEED, repeats: int = REPEATS) -> dict:
    """Which page each name is, the order each form shows them in, and the questions.

    A name from `P51` up carries `of`: the name of the same page's first
    picture. Which of the two a rater saw first depends on their form."""
    pages = rateable(manifest)
    if not pages:
        raise ExportRefused(f"no rateable pages in {manifest}")
    by_id = {row["id"]: row for row in pages}
    names = {row["id"]: f"P{n:02d}" for n, row in enumerate(pages, start=1)}
    pictures: dict[str, dict] = {}
    for page_id, name in names.items():
        row = by_id[page_id]
        pictures[name] = {"page": page_id, "url": row["url"], "state": row["state"],
                          "kind": row["kind"], "file": row["file"],
                          "sha256": row["sha256"]}
    order: list[str] = []
    for item in plan(sorted(by_id), seed, repeats=repeats):
        if not item["repeat"]:
            order.append(names[item["page"]])
            continue
        name = f"P{len(pictures) + 1:02d}"
        pictures[name] = {**pictures[names[item["page"]]], "of": names[item["page"]]}
        order.append(name)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    return {
        "made_by": "python -m tools.rating.export_form",
        "run": data.get("run", {}).get("id"),
        "seed": seed, "repeats": repeats, "min_gap": MIN_GAP,
        "pictures": pictures, "orders": {"A": order, "B": order[::-1]},
        "questions": QUESTIONS, "rating_title": RATING_TITLE,
    }


def export(out: Path = OUT, manifest: Path = MANIFEST, record: Path | None = RECORD,
           seed: int = SEED) -> dict:
    """Write the pictures, the mapping, the form script and its instructions."""
    made = mapping(manifest, seed)
    made["exported_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob("P*.png"):
        stale.unlink()
    images = manifest.parent / "pages"
    for name, picture in made["pictures"].items():
        shutil.copyfile(images / picture["file"], out / f"{name}.png")
    text = json.dumps(made, indent=2, ensure_ascii=False) + "\n"
    (out / "mapping.json").write_text(text, encoding="utf-8")
    for name in ("make_form.gs", "README.md"):
        shutil.copyfile(HERE / "form" / name, out / name)
    if record is not None:
        record.write_text(text, encoding="utf-8")
    return made


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    try:
        made = export(args.out)
    except ExportRefused as reason:
        print(f"Not exported: {reason}")
        raise SystemExit(2) from None
    repeats = [f"{n} = {p['of']}" for n, p in made["pictures"].items() if "of" in p]
    print(f"{len(made['pictures'])} pictures in {args.out} "
          f"({len(made['pictures']) - len(repeats)} pages, repeats {', '.join(repeats)})")
    print(f"mapping also written to {RECORD.relative_to(REPO)}")


if __name__ == "__main__":
    main()
