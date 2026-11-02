"""The online rating forms: the folder exported for them, and their answers
turned back into rating rows that the estimator's training reads.

Everything runs against a temporary study — generated pictures, features and
CSVs — so nothing here touches `data/ratings.jsonl`, `data/rating/form.json`
or `.scratch/rating-form/`; except the last tests, which read the committed
mapping to check it is the design it says it is.
"""

import base64
import csv
import hashlib
import json
import random
from pathlib import Path

import pytest

from backend.estimator import train
from tools.rating import examples as worked
from tools.rating import export_form
from tools.rating.export_form import ExportRefused, export, mapping
from tools.rating.export_set3 import without_set3
from tools.rating.from_form import (FORMS, ConversionRefused, convert, convert_all, merge,
                                    named, run, summary)
from tools.rating.serve import LABELS, QUESTION
from tools.rating.session import MIN_GAP

PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
ONE, TWO = FORMS["1"], FORMS["2"]


def make_study(root: Path, count: int = 50) -> Path:
    """A manifest of `count` pages, each with its own picture and features,
    one failed page, and the two worked examples."""
    images = root / "pages"
    images.mkdir(parents=True)
    rng = random.Random(count)
    pages, features = [], []
    for n in range(count):
        png = PIXEL + bytes([n])  # a different hash for every picture
        page_id = f"site-{n:02d}"
        url = f"https://site-{n:02d}.example/"
        (images / f"{page_id}.png").write_bytes(png)
        pages.append({"id": page_id, "url": url, "state": "as it loads",
                      "kind": "public" if n % 2 else "demo", "run": "r1",
                      "file": f"{page_id}.png", "sha256": hashlib.sha256(png).hexdigest()})
        features.append({"url": url, "state": "as it loads", "run": "r1",
                         **{name: rng.uniform(0, 100) for name in train.FEATURES}})
    pages.append({"id": "broken", "url": "https://broken.example/", "state": "as it loads",
                  "error": "timed out"})
    manifest = root / "pages.json"
    manifest.write_text(json.dumps({"run": {"id": "r1"}, "pages": pages}), encoding="utf-8")
    (root / "corpus.json").write_text(json.dumps({"results": {"headless": features}}),
                                      encoding="utf-8")
    (root / "examples").mkdir()
    rows = []
    for example in worked.EXAMPLES:
        png = PIXEL + example["name"].encode()
        (root / "examples" / f"{example['name']}.png").write_bytes(png)
        rows.append({k: v for k, v in example.items() if k != "drive"}
                    | {"file": f"{example['name']}.png",
                       "sha256": hashlib.sha256(png).hexdigest()})
    (root / "examples.json").write_text(json.dumps({"examples": rows}), encoding="utf-8")
    return manifest


@pytest.fixture
def study(tmp_path: Path) -> tuple[Path, dict]:
    manifest = make_study(tmp_path / "study")
    return manifest, mapping(manifest, manifest.parent / "corpus.json")


def header(made: dict, form: str = "1") -> list[str]:
    """The CSV's columns as Google writes them: in the order of the form's questions."""
    q = made["questions"]
    return (["Timestamp", q["consent"]["title"], q["device"]["title"], q["age"]["title"],
             q["computing"]["title"]]
            + [made["rating_title"].format(question=q["rating"]["title"], name=name)
               for name in made["orders"][form]])


def response(made: dict, form: str = "1", rating: int = 3, consent: str | None = None,
             device: str = "Laptop", ratings: dict[str, str] | None = None) -> list[str]:
    """One response, every answer in words; `ratings` overrides by picture name."""
    q = made["questions"]
    given = {name: LABELS[rating - 1] for name in made["pictures"]} | (ratings or {})
    return (["2026/10/23 10:00:00 AM GMT+5", consent or q["consent"]["yes"], device,
             "25-34", "No"] + [given[name] for name in made["orders"][form]])


def first_showing(made: dict, form: str, page: str) -> str:
    return next(n for n in made["orders"][form] if made["pictures"][n]["page"] == page)


# --- the export: two sets of 30 ---------------------------------------------------


def test_fifty_pages_by_id_then_two_repeats_per_set(study: tuple[Path, dict]) -> None:
    _, made = study
    names = list(made["pictures"])
    assert names == [f"P{n:02d}" for n in range(1, 55)]
    firsts = [made["pictures"][f"P{n:02d}"] for n in range(1, 51)]
    assert [p["page"] for p in firsts] == [f"site-{n:02d}" for n in range(50)]
    assert not any("of" in p for p in firsts)
    assert made["sets"]["1"]["repeats"] == ["P51", "P52"]
    assert made["sets"]["2"]["repeats"] == ["P53", "P54"]
    for n in range(51, 55):
        p = made["pictures"][f"P{n}"]
        assert made["pictures"][p["of"]]["page"] == p["page"]
        assert made["pictures"][p["of"]]["sha256"] == p["sha256"]


def test_the_fifty_are_split_25_and_25_with_nothing_left_out(study: tuple[Path, dict]) -> None:
    _, made = study
    one, two = (set(made["sets"][s]["own"]) for s in ("1", "2"))
    assert len(one) == len(two) == 25
    assert not one & two
    assert one | two == {f"P{n:02d}" for n in range(1, 51)}


@pytest.mark.parametrize("form", ["1", "2"])
def test_each_form_is_25_own_3_anchors_and_2_repeats(study: tuple[Path, dict], form: str) -> None:
    _, made = study
    other = "2" if form == "1" else "1"
    chosen, order = made["sets"][form], made["orders"][form]
    assert len(order) == export_form.PICTURES_PER_FORM == 30
    assert len(set(order)) == 30
    assert set(order) == set(chosen["own"]) | set(chosen["anchors"]) | set(chosen["repeats"])
    # The anchors are the other set's, the three it lends.
    assert chosen["anchors"] == made["sets"][other]["lends"]
    assert set(chosen["anchors"]) <= set(made["sets"][other]["own"])
    assert len(chosen["anchors"]) == 3
    for name in chosen["repeats"]:
        of = made["pictures"][name]["of"]
        # Of the set's own pages, never an anchor, and well after the first showing.
        assert of in chosen["own"] and of not in chosen["lends"]
        assert order.index(name) - order.index(of) > MIN_GAP


def test_the_sets_are_alike_in_their_features(study: tuple[Path, dict]) -> None:
    """Every feature's mean rank differs by little between the two sets, and
    the anchors run from a calm page to a heavy one."""
    _, made = study
    assert made["balance"]["largest_rank_difference"] < 0.06
    for s in ("1", "2"):
        heavy = [made["pictures"][n]["heaviness"] for n in made["sets"][s]["lends"]]
        own = sorted(made["pictures"][n]["heaviness"] for n in made["sets"][s]["own"])
        assert heavy == sorted(heavy)
        assert heavy[0] < own[12] < heavy[2]


def test_the_examples_and_the_scale_are_in_the_mapping(study: tuple[Path, dict]) -> None:
    _, made = study
    assert [(e["file"], e["label"]) for e in made["examples"]] == [
        ("E1.png", "Not at all"), ("E2.png", "Very")]
    assert all(e["says"] and e["says"].endswith(".") for e in made["examples"])
    rating = made["questions"]["rating"]
    assert rating["title"] == QUESTION == "How overwhelming does this page feel?"
    assert rating["labels"] == ["Not at all", "A little", "Somewhat", "Very", "Extremely"]
    assert rating["scale"] == [1, 5]
    assert "about 5-7 minutes" in made["questions"]["intro"].lower()
    assert "30 pictures" in made["questions"]["consent"]["help"]


def test_the_seed_makes_the_same_forms_again(study: tuple[Path, dict]) -> None:
    manifest, made = study
    corpus = manifest.parent / "corpus.json"
    assert mapping(manifest, corpus) == made
    other = mapping(manifest, corpus, seed=export_form.SEED + 1)
    assert other["orders"]["1"] != made["orders"]["1"]


def test_the_folder_holds_the_pictures_the_examples_the_mapping_and_the_script(
        tmp_path: Path, study: tuple[Path, dict]) -> None:
    manifest, _ = study
    out, record = tmp_path / "out", tmp_path / "form.json"
    made = export(out, manifest, record, corpus=manifest.parent / "corpus.json")

    for name, picture in made["pictures"].items():
        png = (out / f"{name}.png").read_bytes()
        assert hashlib.sha256(png).hexdigest() == picture["sha256"]
    assert len(list(out.glob("P*.png"))) == 54
    for example in made["examples"]:
        png = (out / example["file"]).read_bytes()
        assert hashlib.sha256(png).hexdigest() == example["sha256"]
    assert json.loads((out / "mapping.json").read_text(encoding="utf-8")) == made
    assert record.read_text(encoding="utf-8") == (out / "mapping.json").read_text(encoding="utf-8")
    assert (out / "make_form.gs").exists() and (out / "README.md").exists()


def test_a_picture_that_is_not_the_manifests_is_refused(study: tuple[Path, dict]) -> None:
    manifest, _ = study
    (manifest.parent / "pages" / "site-07.png").write_bytes(PIXEL + b"changed")
    with pytest.raises(ExportRefused, match="site-07"):
        mapping(manifest, manifest.parent / "corpus.json")


def test_features_from_another_run_are_refused(study: tuple[Path, dict]) -> None:
    manifest, _ = study
    corpus = manifest.parent / "corpus.json"
    data = json.loads(corpus.read_text(encoding="utf-8"))
    data["results"]["headless"][3]["run"] = "r0"
    corpus.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ExportRefused, match="site-03"):
        mapping(manifest, corpus)


def test_an_example_that_is_not_the_one_recorded_is_refused(study: tuple[Path, dict]) -> None:
    manifest, _ = study
    (manifest.parent / "examples" / "E2.png").write_bytes(PIXEL + b"another")
    with pytest.raises(worked.ExamplesMissing, match="E2"):
        mapping(manifest, manifest.parent / "corpus.json")


def test_the_script_reads_the_names_the_export_writes() -> None:
    script = (Path(export_form.HERE) / "form" / "make_form.gs").read_text(encoding="utf-8")
    for used in ("mapping.json", "mapping.orders[set]", "rating_title", "q.consent.yes",
                 "q.consent.no", "q.device.choices", "q.age.choices", "q.computing.choices",
                 "q.rating.labels", "q.intro", "mapping.examples", "q.examples.answer",
                 "setProgressBar(true)", "function makeFormSet1()", "function makeFormSet2()"):
        assert used in script, used
    assert "setBounds" not in script  # no 1-7 scale item any more
    assert "{question}" in export_form.RATING_TITLE and "{name}" in export_form.RATING_TITLE


# --- the converter ----------------------------------------------------------------


def test_every_answer_of_a_usable_rater_becomes_a_row(study: tuple[Path, dict]) -> None:
    _, made = study
    name = made["orders"]["1"][4]
    done = convert([header(made), response(made, ratings={name: "Extremely"})], made, "1")

    assert done.raters == [ONE + 1]
    assert len(done.rows) == 30
    row = next(r for r in done.rows if r["picture"] == name)
    picture = made["pictures"][name]
    assert row["rating"] == 5 and row["page"] == picture["page"]
    assert row["url"] == picture["url"] and row["image_sha256"] == picture["sha256"]
    assert row["online"] is True and row["set"] == 1 and row["device"] == "laptop"
    assert row["age"] == "25-34" and row["computing"] == "no"
    assert row["position"] == 5 and row["of"] == 30
    assert sum(r["repeat"] for r in done.rows) == 2
    # The six pages both sets show: Set 2's three shown here, and Set 1's three
    # it lends.
    both = made["sets"]["1"]["anchors"] + made["sets"]["1"]["lends"]
    assert {r["page"] for r in done.rows if r["anchor"]} == {
        made["pictures"][n]["page"] for n in both}


def test_each_label_is_its_number(study: tuple[Path, dict]) -> None:
    _, made = study
    order = made["orders"]["1"]
    given = {order[i]: label for i, label in enumerate(LABELS)}
    done = convert([header(made), response(made, ratings=given)], made, "1")
    by_name = {r["picture"]: r["rating"] for r in done.rows}
    assert [by_name[order[i]] for i in range(5)] == [1, 2, 3, 4, 5]


@pytest.mark.parametrize("form", ["1", "2"])
def test_the_repeat_is_the_later_showing(study: tuple[Path, dict], form: str) -> None:
    _, made = study
    done = convert([header(made, form), response(made, form)], made, form)
    for row in done.rows:
        earlier = first_showing(made, form, row["page"])
        assert row["repeat"] == (row["picture"] != earlier)
    assert {r["picture"] for r in done.rows if r["repeat"]} == set(made["sets"][form]["repeats"])


def test_phone_declined_and_incomplete_answers_are_dropped(study: tuple[Path, dict]) -> None:
    _, made = study
    some = made["orders"]["1"][9]
    rows = [header(made),
            response(made),                                  # 5001, usable
            response(made, device="Phone"),                  # 5002
            response(made, consent="No"),                    # 5003
            response(made, ratings={some: ""}),              # 5004
            response(made, ratings={some: "7"}),             # 5005, not one of the five
            response(made, device=""),                       # 5006
            response(made, rating=2, device="Desktop computer")]  # 5007, usable
    done = convert(rows, made, "1")

    assert done.raters == [ONE + 1, ONE + 7]
    assert done.dropped == {"on a phone": [ONE + 2], "did not agree": [ONE + 3],
                            "incomplete": [ONE + 4, ONE + 5, ONE + 6]}
    text = summary(done)
    assert "Set 1: 7 responses in the CSV, 2 usable." in text
    assert "Usable online raters: 2" in text


def test_a_declined_response_with_no_other_answers_is_dropped(study: tuple[Path, dict]) -> None:
    _, made = study
    # Google writes a response that said "No" with every other cell empty, and
    # a short line when the trailing cells are empty.
    done = convert([header(made), ["2026/10/23 10:00:00 AM GMT+5", "No"]], made, "1")
    assert done.rows == [] and done.dropped == {"did not agree": [ONE + 1]}


def test_a_csv_from_another_form_is_refused(study: tuple[Path, dict]) -> None:
    _, made = study
    columns = header(made)
    missing = made["orders"]["1"][6]
    with pytest.raises(ConversionRefused, match=missing):
        convert([[c for c in columns if not c.endswith(f"[{missing}]")]], made, "1")
    with pytest.raises(ConversionRefused, match="age"):
        convert([[c for c in columns if c != made["questions"]["age"]["title"]]], made, "1")
    with pytest.raises(ConversionRefused, match="does not show"):
        convert([header(made, "2")], made, "1")


# --- both sets --------------------------------------------------------------------


def test_each_csvs_set_is_read_from_its_columns(study: tuple[Path, dict]) -> None:
    _, made = study
    done = convert_all([(None, "2.csv", [header(made, "2"), response(made, "2")]),
                        (None, "1.csv", [header(made, "1"), response(made, "1"),
                                         response(made, "1", rating=5)])], made)

    assert done.raters == [ONE + 1, ONE + 2, TWO + 1]
    assert {r["rater"]: r["set"] for r in done.rows} == {ONE + 1: 1, ONE + 2: 1, TWO + 1: 2}
    assert {r["session"] for r in done.rows} == {"form-set1-1", "form-set1-2", "form-set2-1"}
    assert done.notes == []
    text = summary(done)
    assert "Set 1: 2 responses in the CSV, 2 usable." in text
    assert "Set 2: 1 responses in the CSV, 1 usable." in text
    assert "Usable online raters: 3" in text


def test_swapped_names_are_refused(study: tuple[Path, dict]) -> None:
    _, made = study
    with pytest.raises(ConversionRefused, match="swapped"):
        convert_all([("1", "2.csv", [header(made, "2"), response(made, "2")])], made)


def test_two_csvs_from_one_set_are_refused(study: tuple[Path, dict]) -> None:
    _, made = study
    rows = [header(made, "1"), response(made, "1")]
    with pytest.raises(ConversionRefused, match="two CSVs are from Set 1"):
        convert_all([(None, "a.csv", rows), (None, "b.csv", rows)], made)


def test_columns_in_neither_order_need_a_name(study: tuple[Path, dict]) -> None:
    _, made = study
    columns = header(made, "2")
    mixed = columns[:5] + sorted(columns[5:])
    answers = [response(made, "2")[:5] + ["Somewhat"] * 30]
    with pytest.raises(ConversionRefused, match="2=mixed.csv"):
        convert_all([(None, "mixed.csv", [mixed] + answers)], made)

    done = convert_all([("2", "mixed.csv", [mixed] + answers)], made)
    assert done.raters == [TWO + 1] and len(done.notes) == 1
    assert "taken as Set 2" in done.notes[0]


def test_a_set_is_named_with_an_equals_sign() -> None:
    assert named("2=.scratch/rating-form/responses-2.csv") == (
        "2", Path(".scratch/rating-form/responses-2.csv"))
    assert named("responses.csv") == (None, Path("responses.csv"))
    assert named("A=x.csv") == (None, Path("A=x.csv"))


def test_the_rows_of_both_sets_are_what_training_reads(
        tmp_path: Path, study: tuple[Path, dict]) -> None:
    """Each rater rates 30 of the pictures: every page is rated by its own
    set's raters, the anchors by both."""
    manifest, made = study
    done = convert_all([
        (None, "1.csv", [header(made, "1")] + [response(made, "1", rating=n) for n in (2, 3)]),
        (None, "2.csv", [header(made, "2")] + [response(made, "2", rating=n) for n in (4, 5)]),
    ], made)
    out = tmp_path / "ratings.jsonl"
    out.write_text("".join(json.dumps(r) + "\n" for r in merge(done, out)), encoding="utf-8")

    ratings = train.read_ratings(out)
    assert len(ratings) == 4 * 30 and not any(r.synthetic for r in ratings)
    found = train.agreement(ratings)
    assert found.raters == 4 and found.pages == 50 and len(found.repeat_pairs) == 8
    assert found.raters_by_set == {1: 2, 2: 2}
    counts = sorted(n for _, n in train.page_means(ratings).values())
    assert counts == [2] * 44 + [4] * 6  # the six anchors, rated by all four
    assert found.groups is not None and len(found.groups.anchors) == 6
    assert found.groups.difference == pytest.approx(2.0)  # 4.5 against 2.5
    kept, left_out = train.paired(ratings, {}, train.read_pictures(manifest))
    assert len(kept) == len(ratings) and left_out == []


def write_csv(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        csv.writer(file).writerows(rows)


def test_running_again_replaces_only_the_sets_given(
        tmp_path: Path, study: tuple[Path, dict]) -> None:
    _, made = study
    record = tmp_path / "form.json"
    record.write_text(json.dumps(made), encoding="utf-8")
    ratings = tmp_path / "ratings.jsonl"
    picture = made["pictures"]["P02"]
    in_person = {"rater": 3, "set": 1, "page": picture["page"], "url": picture["url"],
                 "state": "as it loads", "rating": 4, "repeat": False,
                 "image_sha256": picture["sha256"]}
    ratings.write_text(json.dumps(in_person) + "\n", encoding="utf-8")
    one, two = tmp_path / "responses-1.csv", tmp_path / "responses-2.csv"

    write_csv(one, [header(made, "1"), response(made, "1")])
    write_csv(two, [header(made, "2"), response(made, "2")])
    run([(None, one), (None, two)], record, ratings)
    write_csv(one, [header(made, "1"), response(made, "1"), response(made, "1", rating=5)])
    done = run([(None, one)], record, ratings)

    rows = [json.loads(line) for line in ratings.read_text(encoding="utf-8").splitlines()]
    assert rows[0] == in_person
    assert len(rows) == 1 + 3 * 30
    assert sorted({r["rater"] for r in rows}) == [3, ONE + 1, ONE + 2, TWO + 1]
    assert done.kept == 1 + 30  # the in-person row, and Set 2's rater


def test_the_summary_says_how_many_more_ratings_are_needed(
        tmp_path: Path, study: tuple[Path, dict]) -> None:
    """Three raters of Set 1 and one of Set 2: every page short of eight, and
    the raters each set still needs, counted on its own pages."""
    _, made = study
    record = tmp_path / "form.json"
    record.write_text(json.dumps(made), encoding="utf-8")
    one, two = tmp_path / "responses-1.csv", tmp_path / "responses-2.csv"
    write_csv(one, [header(made, "1")] + [response(made, "1")] * 3)
    write_csv(two, [header(made, "2"), response(made, "2")])

    done = run([(None, one), (None, two)], record, tmp_path / "ratings.jsonl")

    assert done.coverage is not None
    # 22 pages with 3, 22 with 1, the 6 anchors with 4: (5 + 7) * 22 + 4 * 6.
    assert done.coverage.needed == 12 * 22 + 4 * 6
    assert done.coverage.raters_by_set == {1: 5, 2: 7}
    text = summary(done)
    assert "50 of 50 pages have fewer than 8 ratings" in text
    assert f"{12 * 22 + 4 * 6} more ratings are needed" in text
    assert "5 more Set 1 raters and 7 more Set 2 raters" in text


def test_an_in_person_rater_numbered_like_an_online_one_is_refused(
        tmp_path: Path, study: tuple[Path, dict]) -> None:
    _, made = study
    ratings = tmp_path / "ratings.jsonl"
    ratings.write_text(json.dumps({"rater": TWO + 1, "rating": 4}) + "\n", encoding="utf-8")
    done = convert_all([(None, "2.csv", [header(made, "2"), response(made, "2")])], made)
    with pytest.raises(ConversionRefused, match=str(TWO + 1)):
        merge(done, ratings)


# --- the committed mapping is the design it says it is --------------------------


def test_the_committed_mapping_is_two_sets_of_30() -> None:
    made = json.loads(export_form.RECORD.read_text(encoding="utf-8"))
    own = [set(made["sets"][s]["own"]) for s in ("1", "2")]
    assert [len(o) for o in own] == [25, 25] and not own[0] & own[1]
    assert len(own[0] | own[1]) == 50
    for s, other in (("1", "2"), ("2", "1")):
        order = made["orders"][s]
        assert len(order) == len(set(order)) == 30
        assert made["sets"][s]["anchors"] == made["sets"][other]["lends"]
        assert len(made["sets"][s]["repeats"]) == 2
    assert made["balance"]["largest_rank_difference"] <= 0.05
    assert [e["label"] for e in made["examples"]] == ["Not at all", "Very"]
    assert made["run"] == json.loads(
        (export_form.REPO / "data" / "rating" / "pages.json").read_text(encoding="utf-8")
    )["run"]["id"]


def test_the_committed_mapping_is_what_the_seed_makes_again() -> None:
    """Re-deriving the sets, orders and repeats from the committed manifest
    and corpus gives the committed mapping — so nobody has to trust the file."""
    made = without_set3(json.loads(export_form.RECORD.read_text(encoding="utf-8")))
    if not all((export_form.MANIFEST.parent / "pages" / p["file"]).exists()
               for p in made["pictures"].values()):
        pytest.skip("the rating pictures are not on this machine (python -m tools.rating.capture)")
    again = mapping(examples=[{**e, "path": ""} for e in json.loads(
        worked.RECORD.read_text(encoding="utf-8"))["examples"]])
    for key in ("pictures", "sets", "orders", "balance", "examples", "questions"):
        assert again[key] == made[key], key
