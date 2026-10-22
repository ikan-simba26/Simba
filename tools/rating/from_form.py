"""The Google Form's answers as rating rows, beside the in-person ones.

    python -m tools.rating.from_form .scratch/rating-form/responses.csv

Reads the CSV that Google Forms downloads ("Download responses (.csv)") and
writes one row per answer to `data/ratings.jsonl`, in the shape
`tools/rating/serve.py` writes and `backend/estimator/train.py` reads. The
picture each answer belongs to comes from its column's name, `[P07]`, looked
up in the mapping `export_form.py` wrote (`data/rating/form.json`).

**Who is left out, and why.** A response is dropped, whole, if the person did
not agree to take part, if they answered on a phone (the picture is too small
there to judge a 1280x800 page by), or if any answer is missing or not a
whole number from 1 to 7. Everyone else is a usable rater, and the count is
printed against the ten `train.py` needs.

**Online rows say so.** Each carries `"online": true`, with the device, age
range and whether the person studies or works in computing, so in-person and
online raters can be told apart and compared. An online rater's number is
`ONLINE_FROM` plus their row in the CSV, so numbers stay the same when the
converter is run again on a longer CSV — as long as no response is deleted
from the form. `seed`, `ms`, `shown` and `window` are None: the form fixes
one order for everyone (`mapping.json`), and records neither timing nor size.

**Running it again replaces the online rows and keeps the rest.** Rows from
the in-person tool are kept as they are; every row marked online is replaced
by this CSV's. It refuses to run if an in-person rater's number falls among
the online ones.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from backend.estimator.train import MIN_RATERS

REPO = Path(__file__).resolve().parents[2]
MAPPING = REPO / "data" / "rating" / "form.json"
RATINGS = REPO / "data" / "ratings.jsonl"
#: Online raters are numbered from here; the in-person tool's are typed by the
#: rater, 1 to 9999, and in practice small.
ONLINE_FROM = 5000
#: The picture's name at the end of a rating question's title.
NAME = re.compile(r"\[(P\d{2,})\]\s*$")


class ConversionRefused(Exception):
    """The CSV or the ratings file cannot be converted honestly, and why."""


@dataclass
class Converted:
    rows: list[dict]
    responses: int
    dropped: dict[str, list[int]] = field(default_factory=dict)
    kept_in_person: int = 0

    @property
    def raters(self) -> list[int]:
        return sorted({row["rater"] for row in self.rows})


def _column(header: list[str], title: str) -> int:
    for index, name in enumerate(header):
        if name.strip() == title:
            return index
    raise ConversionRefused(f"the CSV has no column {title!r}; is it this form's?")


def _key(answer: str, choices: dict[str, str]) -> str | None:
    """The short name of a choice (`laptop`) from the words the form shows."""
    for key, words in choices.items():
        if answer.strip() == words:
            return key
    return None


def convert(rows: list[list[str]], mapping: dict) -> Converted:
    """The rating rows of every usable response, and who was dropped and why.

    `rows` is the CSV, header first. Raters are numbered by their row in it."""
    if not rows:
        raise ConversionRefused("the CSV is empty")
    header, answers = rows[0], rows[1:]
    questions = mapping["questions"]
    pictures = mapping["pictures"]
    position = {name: n for n, name in enumerate(mapping["order"], start=1)}
    low, high = questions["rating"]["scale"]

    rating_columns: dict[str, int] = {}
    for index, title in enumerate(header):
        found = NAME.search(title)
        if found:
            if found.group(1) not in pictures:
                raise ConversionRefused(f"column {title!r} names a picture the mapping lacks")
            rating_columns[found.group(1)] = index
    missing = sorted(set(pictures) - set(rating_columns))
    if missing:
        raise ConversionRefused(f"the CSV has no column for {', '.join(missing)}")

    consent = _column(header, questions["consent"]["title"])
    device = _column(header, questions["device"]["title"])
    age = _column(header, questions["age"]["title"])
    computing = _column(header, questions["computing"]["title"])
    timestamp = 0  # Google Forms puts the time of sending first

    out: list[dict] = []
    dropped: dict[str, list[int]] = {}
    for number, answer in enumerate(answers, start=1):
        answer = answer + [""] * (len(header) - len(answer))
        rater = ONLINE_FROM + number
        if answer[consent].strip() != questions["consent"]["yes"]:
            dropped.setdefault("did not agree", []).append(rater)
            continue
        on = _key(answer[device], questions["device"]["choices"])
        if on == "phone":
            dropped.setdefault("on a phone", []).append(rater)
            continue
        ratings: dict[str, int] = {}
        for name, index in rating_columns.items():
            value = answer[index].strip()
            if value.isdigit() and low <= int(value) <= high:
                ratings[name] = int(value)
        if on is None or len(ratings) < len(pictures):
            dropped.setdefault("incomplete", []).append(rater)
            continue
        works = _key(answer[computing], questions["computing"]["choices"])
        for name in mapping["order"]:
            picture = pictures[name]
            out.append({
                "rater": rater, "online": True, "session": f"form-{number}",
                "submitted": answer[timestamp].strip(), "seed": None,
                "position": position[name], "of": len(position),
                "page": picture["page"], "url": picture["url"], "state": picture["state"],
                "kind": picture["kind"], "image_sha256": picture["sha256"],
                "repeat": picture["repeat"], "rating": ratings[name], "ms": None,
                "question": questions["rating"]["title"], "shown": None, "window": None,
                "picture": name, "device": on, "age": answer[age].strip() or None,
                "computing": works,
            })
    return Converted(rows=out, responses=len(answers), dropped=dropped)


def merge(converted: Converted, ratings: Path) -> list[dict]:
    """The in-person rows already in `ratings`, then this CSV's online rows."""
    kept: list[dict] = []
    if ratings.exists():
        for number, line in enumerate(ratings.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ConversionRefused(f"{ratings}, line {number}, is not JSON: {error}") \
                    from error
            if not row.get("online"):
                kept.append(row)
    clash = sorted({r.get("rater") for r in kept} & set(converted.raters))
    if clash:
        raise ConversionRefused(
            f"in-person raters {', '.join(map(str, clash))} have numbers from the online "
            f"range ({ONLINE_FROM + 1} up); renumber them before converting")
    converted.kept_in_person = len(kept)
    return kept + converted.rows


def write(rows: list[dict], ratings: Path) -> None:
    ratings.parent.mkdir(parents=True, exist_ok=True)
    partial = ratings.with_name(ratings.name + ".partial")
    partial.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                       encoding="utf-8")
    partial.replace(ratings)


def summary(converted: Converted) -> str:
    raters = len(converted.raters)
    lines = [f"{converted.responses} responses in the CSV."]
    for why, who in sorted(converted.dropped.items()):
        lines.append(f"  dropped, {why}: {len(who)} ({', '.join(map(str, who))})")
    lines.append(f"Usable online raters: {raters}, {len(converted.rows)} rows written.")
    if converted.kept_in_person:
        lines.append(f"Kept {converted.kept_in_person} in-person rows as they were.")
    short = MIN_RATERS - raters
    lines.append(f"train.py needs {MIN_RATERS} raters in all"
                 + (f"; online alone is {short} short." if short > 0 else "; online alone has enough."))
    return "\n".join(lines)


def run(csv_path: Path, mapping_path: Path = MAPPING, ratings: Path = RATINGS) -> Converted:
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    with csv_path.open(encoding="utf-8-sig", newline="") as file:
        converted = convert(list(csv.reader(file)), mapping)
    write(merge(converted, ratings), ratings)
    return converted


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv", type=Path, help="the form's responses, downloaded as CSV")
    parser.add_argument("--mapping", type=Path, default=MAPPING)
    parser.add_argument("--ratings", type=Path, default=RATINGS)
    args = parser.parse_args()
    try:
        converted = run(args.csv, args.mapping, args.ratings)
    except ConversionRefused as reason:
        print(f"Not converted: {reason}")
        raise SystemExit(2) from None
    print(summary(converted))
    print(f"Written to {args.ratings}.")


if __name__ == "__main__":
    main()
