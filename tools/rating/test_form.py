"""The online rating forms: the folder exported for them, and their answers
turned back into rating rows that the estimator's training reads.

Everything runs against a temporary study — generated pictures and generated
CSVs — so nothing here touches `data/ratings.jsonl`, `data/rating/form.json`
or `.scratch/rating-form/`.
"""

import base64
import csv
import hashlib
import json
from pathlib import Path

import pytest

from backend.estimator import train
from tools.rating import export_form
from tools.rating.export_form import ExportRefused, export, mapping
from tools.rating.from_form import (FORMS, ConversionRefused, convert, convert_all, merge,
                                    named, run, summary)
from tools.rating.session import MIN_GAP

PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
A, B = FORMS["A"], FORMS["B"]


def make_study(root: Path, count: int = 50) -> Path:
    """A manifest of `count` pages, each with its own picture, and one failed page."""
    images = root / "pages"
    images.mkdir(parents=True)
    pages = []
    for n in range(count):
        png = PIXEL + bytes([n])  # a different hash for every picture
        page_id = f"site-{n:02d}"
        (images / f"{page_id}.png").write_bytes(png)
        pages.append({"id": page_id, "url": f"https://site-{n:02d}.example/",
                      "state": "as it loads", "kind": "public", "run": "r1",
                      "file": f"{page_id}.png", "sha256": hashlib.sha256(png).hexdigest()})
    pages.append({"id": "broken", "url": "https://broken.example/", "state": "as it loads",
                  "error": "timed out"})
    manifest = root / "pages.json"
    manifest.write_text(json.dumps({"run": {"id": "r1"}, "pages": pages}), encoding="utf-8")
    return manifest


@pytest.fixture
def study(tmp_path: Path) -> tuple[Path, dict]:
    manifest = make_study(tmp_path / "study")
    return manifest, mapping(manifest)


def header(made: dict, form: str = "A") -> list[str]:
    """The CSV's columns as Google writes them: in the order of the form's questions."""
    q = made["questions"]
    return (["Timestamp", q["consent"]["title"], q["device"]["title"], q["age"]["title"],
             q["computing"]["title"]]
            + [made["rating_title"].format(question=q["rating"]["title"], name=name)
               for name in made["orders"][form]])


def response(made: dict, form: str = "A", rating: int = 4, consent: str | None = None,
             device: str = "Laptop", ratings: dict[str, str] | None = None) -> list[str]:
    q = made["questions"]
    given = {name: str(rating) for name in made["pictures"]} | (ratings or {})
    return (["2026/10/23 10:00:00 AM GMT+5", consent or q["consent"]["yes"], device,
             "25-34", "No"] + [given[name] for name in made["orders"][form]])


def first_showing(made: dict, form: str, page: str) -> str:
    return next(n for n in made["orders"][form] if made["pictures"][n]["page"] == page)


# --- the export -------------------------------------------------------------------


def test_fifty_pages_by_id_then_five_repeats(study: tuple[Path, dict]) -> None:
    _, made = study
    names = list(made["pictures"])
    assert names == [f"P{n:02d}" for n in range(1, 56)]
    firsts = [made["pictures"][f"P{n:02d}"] for n in range(1, 51)]
    assert [p["page"] for p in firsts] == [f"site-{n:02d}" for n in range(50)]
    assert not any("of" in p for p in firsts)
    repeats = [made["pictures"][f"P{n}"] for n in range(51, 56)]
    assert len({p["of"] for p in repeats}) == 5
    for p in repeats:
        assert made["pictures"][p["of"]]["page"] == p["page"]
        assert made["pictures"][p["of"]]["sha256"] == p["sha256"]


def test_form_b_is_form_a_reversed(study: tuple[Path, dict]) -> None:
    _, made = study
    assert set(made["orders"]) == {"A", "B"}
    assert made["orders"]["B"] == made["orders"]["A"][::-1]


@pytest.mark.parametrize("form", ["A", "B"])
def test_each_form_shows_each_once_and_a_page_twice_well_apart(
        study: tuple[Path, dict], form: str) -> None:
    _, made = study
    order = made["orders"][form]
    assert sorted(order) == sorted(made["pictures"])
    for name, picture in made["pictures"].items():
        if "of" in picture:
            assert abs(order.index(name) - order.index(picture["of"])) > MIN_GAP


def test_the_seed_makes_the_same_forms_again(study: tuple[Path, dict]) -> None:
    manifest, made = study
    assert mapping(manifest) == made
    other = mapping(manifest, seed=export_form.SEED + 1)
    assert other["orders"]["A"] != made["orders"]["A"]


def test_the_folder_holds_the_pictures_the_mapping_and_the_script(
        tmp_path: Path, study: tuple[Path, dict]) -> None:
    manifest, _ = study
    out, record = tmp_path / "out", tmp_path / "form.json"
    made = export(out, manifest, record)

    for name, picture in made["pictures"].items():
        png = (out / f"{name}.png").read_bytes()
        assert hashlib.sha256(png).hexdigest() == picture["sha256"]
    assert len(list(out.glob("P*.png"))) == 55
    assert json.loads((out / "mapping.json").read_text(encoding="utf-8")) == made
    assert record.read_text(encoding="utf-8") == (out / "mapping.json").read_text(encoding="utf-8")
    assert (out / "make_form.gs").exists() and (out / "README.md").exists()


def test_a_picture_that_is_not_the_manifests_is_refused(study: tuple[Path, dict]) -> None:
    manifest, _ = study
    (manifest.parent / "pages" / "site-07.png").write_bytes(PIXEL + b"changed")
    with pytest.raises(ExportRefused, match="site-07"):
        mapping(manifest)


def test_the_script_reads_the_names_the_export_writes() -> None:
    script = (Path(export_form.HERE) / "form" / "make_form.gs").read_text(encoding="utf-8")
    for used in ("mapping.json", "mapping.orders[letter]", "rating_title", "q.consent.yes",
                 "q.consent.no", "q.device.choices", "q.age.choices", "q.computing.choices",
                 "q.rating.scale", "function makeFormA()", "function makeFormB()"):
        assert used in script
    assert "{question}" in export_form.RATING_TITLE and "{name}" in export_form.RATING_TITLE


# --- the converter ----------------------------------------------------------------


def test_every_answer_of_a_usable_rater_becomes_a_row(study: tuple[Path, dict]) -> None:
    _, made = study
    done = convert([header(made), response(made, ratings={"P03": "7"})], made, "A")

    assert done.raters == [A + 1]
    assert len(done.rows) == 55
    row = next(r for r in done.rows if r["picture"] == "P03")
    picture = made["pictures"]["P03"]
    assert row["rating"] == 7 and row["page"] == picture["page"]
    assert row["url"] == picture["url"] and row["image_sha256"] == picture["sha256"]
    assert row["online"] is True and row["form"] == "A" and row["device"] == "laptop"
    assert row["age"] == "25-34" and row["computing"] == "no"
    assert row["position"] == made["orders"]["A"].index("P03") + 1 and row["of"] == 55
    assert sum(r["repeat"] for r in done.rows) == 5


@pytest.mark.parametrize("form", ["A", "B"])
def test_the_repeat_is_the_later_showing_in_the_raters_form(
        study: tuple[Path, dict], form: str) -> None:
    _, made = study
    done = convert([header(made, form), response(made, form)], made, form)
    for row in done.rows:
        earlier = first_showing(made, form, row["page"])
        assert row["repeat"] == (row["picture"] != earlier)
        assert row["position"] == made["orders"][form].index(row["picture"]) + 1
    # In B, the names from P51 up come first.
    late = {r["picture"] for r in done.rows if r["repeat"]}
    assert late == ({f"P{n}" for n in range(51, 56)} if form == "A"
                    else {made["pictures"][f"P{n}"]["of"] for n in range(51, 56)})


def test_phone_declined_and_incomplete_answers_are_dropped(study: tuple[Path, dict]) -> None:
    _, made = study
    rows = [header(made),
            response(made),                                  # 5001, usable
            response(made, device="Phone"),                  # 5002
            response(made, consent="No"),                    # 5003
            response(made, ratings={"P10": ""}),             # 5004
            response(made, ratings={"P52": "9"}),            # 5005, out of range
            response(made, device=""),                       # 5006
            response(made, rating=2, device="Desktop computer")]  # 5007, usable
    done = convert(rows, made, "A")

    assert done.raters == [A + 1, A + 7]
    assert done.dropped == {"on a phone": [A + 2], "did not agree": [A + 3],
                            "incomplete": [A + 4, A + 5, A + 6]}
    text = summary(done)
    assert "Form A: 7 responses in the CSV, 2 usable." in text
    assert "Usable online raters: 2" in text and f"train.py needs {train.MIN_RATERS}" in text


def test_a_declined_response_with_no_other_answers_is_dropped(study: tuple[Path, dict]) -> None:
    _, made = study
    # Google writes a response that said "No" with every other cell empty, and
    # a short line when the trailing cells are empty.
    done = convert([header(made), ["2026/10/23 10:00:00 AM GMT+5", "No"]], made, "A")
    assert done.rows == [] and done.dropped == {"did not agree": [A + 1]}


def test_a_csv_from_another_form_is_refused(study: tuple[Path, dict]) -> None:
    _, made = study
    columns = header(made)
    with pytest.raises(ConversionRefused, match="P07"):
        convert([[c for c in columns if not c.endswith("[P07]")]], made, "A")
    with pytest.raises(ConversionRefused, match="age"):
        convert([[c for c in columns if c != made["questions"]["age"]["title"]]], made, "A")


# --- both forms -------------------------------------------------------------------


def test_each_csvs_form_is_read_from_its_columns(study: tuple[Path, dict]) -> None:
    _, made = study
    done = convert_all([(None, "b.csv", [header(made, "B"), response(made, "B")]),
                        (None, "a.csv", [header(made, "A"), response(made, "A"),
                                         response(made, "A", rating=6)])], made)

    assert done.raters == [A + 1, A + 2, B + 1]
    assert {r["rater"]: r["form"] for r in done.rows} == {A + 1: "A", A + 2: "A", B + 1: "B"}
    assert {r["session"] for r in done.rows} == {"form-A-1", "form-A-2", "form-B-1"}
    assert done.notes == []
    text = summary(done)
    assert "Form A: 2 responses in the CSV, 2 usable." in text
    assert "Form B: 1 responses in the CSV, 1 usable." in text
    assert "Usable online raters: 3" in text


def test_swapped_names_are_refused(study: tuple[Path, dict]) -> None:
    _, made = study
    with pytest.raises(ConversionRefused, match="swapped"):
        convert_all([("A", "b.csv", [header(made, "B"), response(made, "B")])], made)


def test_two_csvs_from_one_form_are_refused(study: tuple[Path, dict]) -> None:
    _, made = study
    rows = [header(made, "A"), response(made, "A")]
    with pytest.raises(ConversionRefused, match="two CSVs are from form A"):
        convert_all([(None, "1.csv", rows), (None, "2.csv", rows)], made)


def test_columns_in_neither_order_need_a_name(study: tuple[Path, dict]) -> None:
    _, made = study
    columns = header(made, "B")
    mixed = columns[:5] + sorted(columns[5:])
    answers = [response(made, "B")[:5] + ["4"] * 55]
    with pytest.raises(ConversionRefused, match="B=mixed.csv"):
        convert_all([(None, "mixed.csv", [mixed] + answers)], made)

    done = convert_all([("B", "mixed.csv", [mixed] + answers)], made)
    assert done.raters == [B + 1] and len(done.notes) == 1 and "taken as form B" in done.notes[0]


def test_a_form_is_named_with_an_equals_sign() -> None:
    assert named("B=.scratch/rating-form/responses-B.csv") == (
        "B", Path(".scratch/rating-form/responses-B.csv"))
    assert named("responses.csv") == (None, Path("responses.csv"))
    assert named("C=x.csv") == (None, Path("C=x.csv"))


def test_the_rows_of_both_forms_are_what_training_reads(
        tmp_path: Path, study: tuple[Path, dict]) -> None:
    manifest, made = study
    done = convert_all([
        (None, "a.csv", [header(made, "A")] + [response(made, "A", rating=n) for n in (2, 3)]),
        (None, "b.csv", [header(made, "B")] + [response(made, "B", rating=n) for n in (5, 6)]),
    ], made)
    out = tmp_path / "ratings.jsonl"
    out.write_text("".join(json.dumps(r) + "\n" for r in merge(done, out)), encoding="utf-8")

    ratings = train.read_ratings(out)
    assert len(ratings) == 4 * 55 and not any(r.synthetic for r in ratings)
    found = train.agreement(ratings)
    assert found.raters == 4 and found.pages == 50 and len(found.repeat_pairs) == 20
    means = train.page_means(ratings)
    assert all(n == 4 for _, n in means.values())
    kept, left_out = train.paired(ratings, {}, train.read_pictures(manifest))
    assert len(kept) == len(ratings) and left_out == []


def write_csv(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        csv.writer(file).writerows(rows)


def test_running_again_replaces_only_the_forms_given(
        tmp_path: Path, study: tuple[Path, dict]) -> None:
    _, made = study
    record = tmp_path / "form.json"
    record.write_text(json.dumps(made), encoding="utf-8")
    ratings = tmp_path / "ratings.jsonl"
    in_person = {"rater": 3, "page": "site-01", "url": "https://site-01.example/",
                 "state": "as it loads", "rating": 4, "repeat": False}
    ratings.write_text(json.dumps(in_person) + "\n", encoding="utf-8")
    a, b = tmp_path / "responses-A.csv", tmp_path / "responses-B.csv"

    write_csv(a, [header(made, "A"), response(made, "A")])
    write_csv(b, [header(made, "B"), response(made, "B")])
    run([(None, a), (None, b)], record, ratings)
    write_csv(a, [header(made, "A"), response(made, "A"), response(made, "A", rating=6)])
    done = run([(None, a)], record, ratings)

    rows = [json.loads(line) for line in ratings.read_text(encoding="utf-8").splitlines()]
    assert rows[0] == in_person
    assert len(rows) == 1 + 3 * 55
    assert sorted({r["rater"] for r in rows}) == [3, A + 1, A + 2, B + 1]
    assert done.kept == 1 + 55  # the in-person row, and form B's rater


def test_an_in_person_rater_numbered_like_an_online_one_is_refused(
        tmp_path: Path, study: tuple[Path, dict]) -> None:
    _, made = study
    ratings = tmp_path / "ratings.jsonl"
    ratings.write_text(json.dumps({"rater": B + 1, "rating": 4}) + "\n", encoding="utf-8")
    done = convert_all([(None, "b.csv", [header(made, "B"), response(made, "B")])], made)
    with pytest.raises(ConversionRefused, match=str(B + 1)):
        merge(done, ratings)
