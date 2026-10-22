"""The Google Forms' answers as rating rows, beside the in-person ones.

    python -m tools.rating.from_form .scratch/rating-form/responses-A.csv .scratch/rating-form/responses-B.csv

Reads the CSVs that Google Forms downloads ("Download responses (.csv)"), one
per form, and writes one row per answer to `data/ratings.jsonl`, in the shape
`tools/rating/serve.py` writes and `backend/estimator/train.py` reads. The
picture each answer belongs to comes from its column's name, `[P07]`, looked
up in the mapping `export_form.py` wrote (`data/rating/form.json`).

**Which form a CSV is from.** Form A shows the pictures in one order and form
B in the reverse (`export_form.py`), and Google writes a form's columns in the
order of its questions, so a CSV's form is read from its columns. A CSV can
also be named, `B=path.csv`: a named CSV whose columns are in the other
form's order is refused (the files were likely swapped); one whose columns
are in neither order is taken as named, and the converter says so.

**Who is left out, and why.** A response is dropped, whole, if the person did
not agree to take part, if they answered on a phone (the picture is too small
there to judge a 1280x800 page by), or if any answer is missing or not a
whole number from 1 to 7. Everyone else is a usable rater, and the count is
printed against the ten `train.py` needs.

**Online rows say so.** Each carries `"online": true` and the form, `"A"` or
`"B"`, with the device, age range and whether the person studies or works in
computing, so in-person and online raters — and the two forms — can be told
apart and compared. `position` is the picture's place in that rater's form,
and `repeat` marks the later of a page's two showings in it. An online
rater's number is their form's base in `FORMS` plus their row in its CSV, so
numbers stay the same when the converter is run again on a longer CSV — as
long as no response is deleted from the form. `seed`, `ms`, `shown` and
`window` are None: the forms fix their order (`mapping.json`), and record
neither timing nor size.

**Running it again replaces the online rows of the forms it is given** and
keeps the rest: the in-person tool's rows, and another form's online rows
when only one CSV is given. It refuses to run if an in-person rater's number
falls among the online ones.
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
#: Each form's online raters are numbered from here, a thousand apart; the
#: in-person tool's are typed by the rater, 1 to 9999, and in practice small.
FORMS = {"A": 5000, "B": 6000}
#: The picture's name at the end of a rating question's title.
NAME = re.compile(r"\[(P\d{2,})\]\s*$")


class ConversionRefused(Exception):
    """The CSV or the ratings file cannot be converted honestly, and why."""


@dataclass
class Converted:
    rows: list[dict] = field(default_factory=list)
    #: Form -> how many responses its CSV held.
    responses: dict[str, int] = field(default_factory=dict)
    dropped: dict[str, list[int]] = field(default_factory=dict)
    #: Anything the converter assumed and the person running it should know.
    notes: list[str] = field(default_factory=list)
    kept: int = 0

    @property
    def raters(self) -> list[int]:
        return sorted({row["rater"] for row in self.rows})

    def raters_of(self, form: str) -> list[int]:
        return sorted({row["rater"] for row in self.rows if row["form"] == form})

    def add(self, other: Converted) -> None:
        self.rows += other.rows
        self.responses |= other.responses
        for why, who in other.dropped.items():
            self.dropped.setdefault(why, []).extend(who)
        self.notes += other.notes


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


def form_of(header: list[str], mapping: dict) -> str | None:
    """The form whose order the CSV's rating columns are in, if either."""
    names = [found.group(1) for title in header if (found := NAME.search(title))]
    return next((form for form, order in mapping["orders"].items() if names == order), None)


def which_form(header: list[str], mapping: dict, named: str | None, source: str
               ) -> tuple[str, str | None]:
    """The CSV's form, and a note if it was taken on trust from its name."""
    found = form_of(header, mapping)
    if named is None:
        if found is None:
            raise ConversionRefused(
                f"{source}: the questions are in neither form's order, so which form it "
                f"is from cannot be told. Name it: A={source} or B={source}")
        return found, None
    if named not in mapping["orders"]:
        raise ConversionRefused(f"{source}: there is no form {named!r}")
    if found is not None and found != named:
        raise ConversionRefused(
            f"{source} is named form {named}, but its questions are in form {found}'s "
            f"order. Were the two files swapped?")
    if found is None:
        return named, (f"{source}: the questions are in neither form's order; "
                       f"taken as form {named}, as named")
    return named, None


def convert(rows: list[list[str]], mapping: dict, form: str) -> Converted:
    """The rating rows of every usable response to `form`, and who was dropped
    and why. `rows` is the CSV, header first. Raters are numbered by their row."""
    if not rows:
        raise ConversionRefused("the CSV is empty")
    header, answers = rows[0], rows[1:]
    questions = mapping["questions"]
    pictures = mapping["pictures"]
    order = mapping["orders"][form]
    position = {name: n for n, name in enumerate(order, start=1)}
    # The later of a page's two showings in this form is the repeat.
    repeat: dict[str, bool] = {}
    seen: set[str] = set()
    for name in order:
        repeat[name] = pictures[name]["page"] in seen
        seen.add(pictures[name]["page"])
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
        rater = FORMS[form] + number
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
        for name in order:
            picture = pictures[name]
            out.append({
                "rater": rater, "online": True, "form": form,
                "session": f"form-{form}-{number}",
                "submitted": answer[timestamp].strip(), "seed": None,
                "position": position[name], "of": len(position),
                "page": picture["page"], "url": picture["url"], "state": picture["state"],
                "kind": picture["kind"], "image_sha256": picture["sha256"],
                "repeat": repeat[name], "rating": ratings[name], "ms": None,
                "question": questions["rating"]["title"], "shown": None, "window": None,
                "picture": name, "device": on, "age": answer[age].strip() or None,
                "computing": works,
            })
    return Converted(rows=out, responses={form: len(answers)}, dropped=dropped)


def convert_all(csvs: list[tuple[str | None, str, list[list[str]]]], mapping: dict
                ) -> Converted:
    """Every CSV given, as `(named form or None, where it came from, rows)`."""
    converted = Converted()
    for named, source, rows in csvs:
        if not rows:
            raise ConversionRefused(f"{source} is empty")
        form, note = which_form(rows[0], mapping, named, source)
        if form in converted.responses:
            raise ConversionRefused(f"two CSVs are from form {form}; give one per form")
        one = convert(rows, mapping, form)
        if note:
            one.notes.append(note)
        converted.add(one)
    return converted


def merge(converted: Converted, ratings: Path) -> list[dict]:
    """The rows already in `ratings` that are not from the forms converted —
    in-person rows, and another form's — then the converted rows."""
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
            if not (row.get("online") and row.get("form", "A") in converted.responses):
                kept.append(row)
    in_person = {r.get("rater") for r in kept if not r.get("online")}
    clash = sorted(in_person & set(converted.raters))
    if clash:
        raise ConversionRefused(
            f"in-person raters {', '.join(map(str, clash))} have numbers from the online "
            f"ranges ({', '.join(f'{base + 1} up' for base in FORMS.values())}); renumber "
            f"them before converting")
    converted.kept = len(kept)
    return kept + converted.rows


def write(rows: list[dict], ratings: Path) -> None:
    ratings.parent.mkdir(parents=True, exist_ok=True)
    partial = ratings.with_name(ratings.name + ".partial")
    partial.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                       encoding="utf-8")
    partial.replace(ratings)


def summary(converted: Converted) -> str:
    raters = len(converted.raters)
    lines = [f"Form {form}: {count} responses in the CSV, "
             f"{len(converted.raters_of(form))} usable."
             for form, count in sorted(converted.responses.items())]
    for why, who in sorted(converted.dropped.items()):
        lines.append(f"  dropped, {why}: {len(who)} ({', '.join(map(str, who))})")
    lines += [f"  note: {note}" for note in converted.notes]
    lines.append(f"Usable online raters: {raters}, {len(converted.rows)} rows written.")
    if converted.kept:
        lines.append(f"Kept {converted.kept} rows from in person or another form as they were.")
    short = MIN_RATERS - raters
    lines.append(f"train.py needs {MIN_RATERS} raters in all"
                 + (f"; these alone are {short} short." if short > 0
                    else "; these alone have enough."))
    return "\n".join(lines)


def named(argument: str) -> tuple[str | None, Path]:
    """`B=path.csv` -> ("B", path); a bare path -> (None, path)."""
    form, sep, rest = argument.partition("=")
    if sep and form in FORMS:
        return form, Path(rest)
    return None, Path(argument)


def run(csvs: list[tuple[str | None, Path]], mapping_path: Path = MAPPING,
        ratings: Path = RATINGS) -> Converted:
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    read = []
    for form, path in csvs:
        with path.open(encoding="utf-8-sig", newline="") as file:
            read.append((form, str(path), list(csv.reader(file))))
    converted = convert_all(read, mapping)
    write(merge(converted, ratings), ratings)
    return converted


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv", nargs="+",
                        help="a form's responses, downloaded as CSV; A=path or B=path to name its form")
    parser.add_argument("--mapping", type=Path, default=MAPPING)
    parser.add_argument("--ratings", type=Path, default=RATINGS)
    args = parser.parse_args()
    try:
        converted = run([named(a) for a in args.csv], args.mapping, args.ratings)
    except ConversionRefused as reason:
        print(f"Not converted: {reason}")
        raise SystemExit(2) from None
    print(summary(converted))
    print(f"Written to {args.ratings}.")


if __name__ == "__main__":
    main()
