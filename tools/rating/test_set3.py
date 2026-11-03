"""Set 3: twenty pictures, chosen to cover what the new features can see.

Everything runs against a temporary study, except the last tests, which read the
committed mapping. What matters most is what must not move: answers to Sets 1 and 2
are matched to pictures by name, so nothing in the mapping they use may change.
"""

import base64
import csv
import hashlib
import json
from pathlib import Path

import pytest

from backend.estimator import train
from backend.estimator.page_model import VISUAL_FEATURES
from tools.rating import export_form, export_set3, from_form, serve
from tools.rating.export_form import ExportRefused
from tools.rating.export_set3 import (ANCHORS, FIRST_NAME, LEAST, MOST, OVERRIDES, OWN_PAGES,
                                      PICTURES, add_set3, anchors, choose, coverage, without_set3)
from tools.rating.serve import LABELS, Study
from tools.rating.session import MIN_GAP

from tools.rating.test_form import make_study

PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
CATEGORIES = ("Government services", "Utilities", "Universities", "Banks", "Telecoms",
              "Transport", "Health")


def sites(count: int = 35) -> dict[str, dict]:
    """A list of sites spread evenly over the seven categories and every feature."""
    rows = {}
    for n in range(count):
        key = f"site-{n:02d}"
        rows[key] = {
            "site": f"Site {n}", "category": CATEGORIES[n % 7], "status": "scored",
            "url": f"https://site-{n:02d}.example.pk/", "screenshot": f"{key}.png",
            "sha256": hashlib.sha256(PIXEL + bytes([n])).hexdigest(), "title": f"Site {n}",
            "image_area": (n * 7 % count) / count, "motion": (n * 11 % count) / count,
            "covered": (n * 13 % count) / count, "first_screen_links": n * 3 % count,
            "first_screen_text": (n * 17 % count) / 10}
    return rows


def with_ratings(tmp_path: Path, made: dict) -> Path:
    """Ratings that put the six shared pages in a known order: P-names by page."""
    path = tmp_path / "ratings.jsonl"
    shared = [n for s in ("1", "2") for n in made["sets"][s]["anchors"]]
    path.write_text("".join(
        json.dumps({"page": made["pictures"][name]["page"], "rating": 1 + at % 5, "rater": rater,
                    "repeat": False}) + "\n"
        for at, name in enumerate(shared) for rater in (1, 2)), encoding="utf-8")
    return path


@pytest.fixture
def made(tmp_path: Path) -> dict:
    manifest = make_study(tmp_path / "study")
    return export_form.mapping(manifest, manifest.parent / "corpus.json")


# --- which pages -----------------------------------------------------------------


def test_fifteen_pages_and_every_category_at_least_twice() -> None:
    rows = sites()
    chosen = choose(rows)
    held = [rows[key]["category"] for key in chosen]
    assert len(chosen) == len(set(chosen)) == OWN_PAGES
    for category in CATEGORIES:
        assert LEAST <= held.count(category) <= MOST, category


def test_the_choice_reaches_both_ends_of_every_new_feature() -> None:
    """The point of the choice: a page at each end, or the model learns the middle."""
    rows = sites()
    spans = coverage(rows, choose(rows))
    for name in VISUAL_FEATURES:
        span = spans[name]
        whole = span["highest"] - span["lowest"]
        assert span["highest_chosen"] - span["lowest_chosen"] >= 0.75 * whole, name


def test_the_choice_is_wider_than_taking_the_first_fifteen() -> None:
    rows = sites()
    first = sorted(rows)[:OWN_PAGES]
    wide, plain = coverage(rows, choose(rows)), coverage(rows, first)
    assert sum(s["highest_chosen"] - s["lowest_chosen"] for s in wide.values()) \
        >= sum(s["highest_chosen"] - s["lowest_chosen"] for s in plain.values())


def test_the_choice_is_the_same_every_time() -> None:
    assert choose(sites()) == choose(sites())


def test_a_list_too_short_for_the_limits_is_refused() -> None:
    rows = {key: {**row, "category": "Banks"} for key, row in sites().items()}
    with pytest.raises(ExportRefused, match="only 3 pages"):
        choose(rows)


# --- the anchors -----------------------------------------------------------------


def test_three_anchors_at_the_low_middle_and_high_of_what_raters_said(
        made: dict, tmp_path: Path) -> None:
    found = anchors(made, with_ratings(tmp_path, made))
    shared = [n for s in ("1", "2") for n in made["sets"][s]["anchors"]]
    assert len(found) == ANCHORS and set(found) <= set(shared)
    rated = {name: 1 + at % 5 for at, name in enumerate(shared)}
    assert min(rated[n] for n in found) == min(rated.values())
    assert max(rated[n] for n in found) == max(rated.values())


def test_an_anchor_nobody_rated_is_refused(made: dict, tmp_path: Path) -> None:
    empty = tmp_path / "none.jsonl"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ExportRefused, match="no ratings"):
        anchors(made, empty)


# --- the mapping: added to, and otherwise untouched ----------------------------------


def added(made: dict, tmp_path: Path) -> dict:
    rows = sites()
    return add_set3(made, rows, choose(rows), anchors(made, with_ratings(tmp_path, made)))


def test_twenty_pictures_fifteen_three_and_two(made: dict, tmp_path: Path) -> None:
    whole = added(made, tmp_path)
    chosen, order = whole["sets"]["3"], whole["orders"]["3"]
    assert len(order) == len(set(order)) == PICTURES == 20
    assert (len(chosen["own"]), len(chosen["anchors"]), len(chosen["repeats"])) == (15, 3, 2)
    assert set(order) == set(chosen["own"]) | set(chosen["anchors"]) | set(chosen["repeats"])


def test_nothing_sets_1_and_2_use_has_changed(made: dict, tmp_path: Path) -> None:
    whole = added(made, tmp_path)
    assert without_set3(whole) == made
    for name, picture in made["pictures"].items():
        assert whole["pictures"][name] == picture, name
    for form in ("1", "2"):
        assert whole["orders"][form] == made["orders"][form]
        assert whole["sets"][form] == made["sets"][form]
    assert whole["questions"] == made["questions"]


def test_the_new_names_follow_the_old_ones(made: dict, tmp_path: Path) -> None:
    whole = added(made, tmp_path)
    new = sorted(set(whole["pictures"]) - set(made["pictures"]))
    assert new == [f"P{FIRST_NAME + n:02d}" for n in range(17)]
    assert FIRST_NAME == len(made["pictures"]) + 1


def test_an_anchor_keeps_its_own_name_and_its_own_picture(made: dict, tmp_path: Path) -> None:
    whole = added(made, tmp_path)
    for name in whole["sets"]["3"]["anchors"]:
        assert int(name[1:]) < FIRST_NAME
        assert whole["pictures"][name]["sha256"] == made["pictures"][name]["sha256"]


def test_a_repeat_is_of_a_page_of_its_own_and_comes_well_after_it(made: dict, tmp_path: Path) -> None:
    whole = added(made, tmp_path)
    chosen, order = whole["sets"]["3"], whole["orders"]["3"]
    for name in chosen["repeats"]:
        first = whole["pictures"][name]["of"]
        assert first in chosen["own"]
        assert order.index(name) - order.index(first) > MIN_GAP


def test_the_same_question_labels_and_examples_and_only_the_time_differs(
        made: dict, tmp_path: Path) -> None:
    whole = added(made, tmp_path)
    assert whole["questions"]["rating"] == made["questions"]["rating"]
    assert whole["examples"] == made["examples"]
    words = whole["overrides"]["3"]
    assert "About 3-4 minutes" in words["intro"]
    assert "20 pictures" in words["consent_help"] and "3-4 minutes" in words["consent_help"]
    assert "30 pictures" not in words["consent_help"]
    assert words["consent_help"].replace("20 pictures", "30 pictures").replace(
        "3-4", "5-7") == made["questions"]["consent"]["help"]


def test_adding_it_twice_is_refused(made: dict, tmp_path: Path) -> None:
    whole = added(made, tmp_path)
    with pytest.raises(ExportRefused, match="already"):
        add_set3(whole, sites(), choose(sites()), [])


# --- the folder -----------------------------------------------------------------


def exported(tmp_path: Path, made: dict) -> dict:
    """A whole export into `tmp_path`, from a study of its own."""
    measured = tmp_path / "measured"
    measured.mkdir()
    rows = list(sites().values())
    for n, row in enumerate(rows):
        (measured / row["screenshot"]).write_bytes(PIXEL + bytes([n]))
    (tmp_path / "visual.json").write_text(json.dumps(
        {"sites": {"run": {"id": "r3"}, "rows": rows}}), encoding="utf-8")
    pages = tmp_path / "study" / "pages"
    for name, picture in made["pictures"].items():
        assert (pages / picture["file"]).exists(), name
    record = tmp_path / "form.json"
    record.write_text(json.dumps(made), encoding="utf-8")
    examples = tmp_path / "study" / "examples"
    return dict(out=tmp_path / "out", record=record, visual=tmp_path / "visual.json",
                measured=measured, pages=pages, written=tmp_path / "set3.json",
                ratings=with_ratings(tmp_path, made), examples=examples)


def test_the_folder_has_what_the_form_needs_and_nothing_else(made: dict, tmp_path: Path) -> None:
    options = exported(tmp_path, made)
    done = export_set3.export(**options)["made"]
    files = sorted(f.name for f in options["out"].iterdir())
    assert files == sorted({f"{n}.png" for n in done["orders"]["3"]}
                           | {"E1.png", "E2.png", "mapping.json", "make_form.gs", "README.md"})


def test_a_page_caught_loading_is_never_chosen(
        made: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    options = exported(tmp_path, made)
    plain = export_set3.export(**options)
    gone = plain["chosen"][0]
    (tmp_path / "form.json").write_text(json.dumps(made), encoding="utf-8")
    monkeypatch.setattr(export_set3, "EXCLUDED", {gone: "caught mid-load"})
    done = export_set3.export(**options)
    assert gone not in done["chosen"] and len(done["chosen"]) == OWN_PAGES


def test_each_picture_is_the_one_its_hash_says(made: dict, tmp_path: Path) -> None:
    options = exported(tmp_path, made)
    done = export_set3.export(**options)["made"]
    for name in done["orders"]["3"]:
        expected = done["pictures"][name]["sha256"]
        assert hashlib.sha256((options["out"] / f"{name}.png").read_bytes()).hexdigest() == expected


def test_a_picture_that_is_not_the_one_read_is_refused(made: dict, tmp_path: Path) -> None:
    options = exported(tmp_path, made)
    for picture in options["measured"].iterdir():
        picture.write_bytes(PIXEL + b"changed")
    with pytest.raises(ExportRefused, match="not the picture read"):
        export_set3.export(**options)


def test_run_again_it_makes_the_same_set(made: dict, tmp_path: Path) -> None:
    options = exported(tmp_path, made)
    first = export_set3.export(**options)["made"]
    assert export_set3.export(**options)["made"] == first


def test_it_will_not_make_a_different_set_once_there_is_one(made: dict, tmp_path: Path) -> None:
    options = exported(tmp_path, made)
    export_set3.export(**options)
    data = json.loads(options["visual"].read_text(encoding="utf-8"))
    for row in data["sites"]["rows"]:
        row["image_area"] = 1 - row["image_area"] ** 2
        row["motion"] = 0.5
    options["visual"].write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ExportRefused, match="different"):
        export_set3.export(**options)


def test_the_manifest_is_one_train_can_read(made: dict, tmp_path: Path) -> None:
    options = exported(tmp_path, made)
    export_set3.export(**options)
    pictures = train.read_pictures(options["written"])
    assert len(pictures) == OWN_PAGES
    assert {row["run"] for row in pictures.values()} == {"r3"}


def test_sets_1_and_2_cannot_be_exported_over_set_3(made: dict, tmp_path: Path) -> None:
    options = exported(tmp_path, made)
    export_set3.export(**options)
    with pytest.raises(ExportRefused, match="Set 3"):
        export_form.export(tmp_path / "again", tmp_path / "study" / "pages.json",
                           options["record"], corpus=tmp_path / "study" / "corpus.json")


# --- its answers ---------------------------------------------------------------------


def header(whole: dict, form: str = "3") -> list[str]:
    q = whole["questions"]
    return (["Timestamp", q["consent"]["title"], q["device"]["title"], q["age"]["title"],
             q["computing"]["title"]]
            + [whole["rating_title"].format(question=q["rating"]["title"], name=name)
               for name in whole["orders"][form]])


def answer(whole: dict, rating: int = 3, form: str = "3", device: str = "Laptop") -> list[str]:
    q = whole["questions"]
    return (["2026/11/10 10:00:00 AM GMT+5", q["consent"]["yes"], device, "25-34", "No"]
            + [LABELS[rating - 1]] * len(whole["orders"][form]))


def test_a_set_3_rater_is_numbered_apart_from_the_others() -> None:
    assert from_form.FORMS["3"] == 7000
    assert from_form.named("3=path.csv")[0] == "3"


def test_the_converter_knows_a_set_3_csv_by_its_questions(made: dict, tmp_path: Path) -> None:
    whole = added(made, tmp_path)
    table = [header(whole), answer(whole)]
    assert from_form.form_of(table[0], whole) == "3"
    done = from_form.convert_all([(None, "set3.csv", table)], whole)
    assert done.raters == [7001]
    assert {row["set"] for row in done.rows} == {3}
    assert len(done.rows) == 20


def test_a_repeat_and_an_anchor_are_marked_as_they_are_in_the_other_sets(
        made: dict, tmp_path: Path) -> None:
    whole = added(made, tmp_path)
    rows = from_form.convert([header(whole), answer(whole)], whole, "3").rows
    assert sum(row["repeat"] for row in rows) == 2
    assert sum(row["anchor"] for row in rows) >= 3
    pages = {whole["pictures"][n]["page"] for n in whole["sets"]["3"]["anchors"]}
    assert all(row["anchor"] for row in rows if row["page"] in pages)


def test_converting_set_3_keeps_what_the_other_sets_had(made: dict, tmp_path: Path) -> None:
    whole = added(made, tmp_path)
    ratings = tmp_path / "ratings.jsonl"
    ratings.write_text(json.dumps({"rater": 5001, "online": True, "set": 1, "rating": 2}) + "\n",
                       encoding="utf-8")
    done = from_form.convert([header(whole), answer(whole)], whole, "3")
    merged = from_form.merge(done, ratings)
    assert {row["set"] for row in merged} == {1, 3}


def test_the_count_of_what_is_needed_names_set_3(made: dict, tmp_path: Path) -> None:
    whole = added(made, tmp_path)
    done = from_form.convert([header(whole), answer(whole)], whole, "3")
    said = from_form.coverage(done.rows, whole).says()
    assert "7 more Set 3 raters" in said


def test_a_phone_answer_to_set_3_is_dropped_like_any_other(made: dict, tmp_path: Path) -> None:
    whole = added(made, tmp_path)
    done = from_form.convert([header(whole), answer(whole, device="Phone")], whole, "3")
    assert done.rows == [] and done.dropped == {"on a phone": [7001]}


# --- the in-person tool, and the form script ---------------------------------------


def test_the_in_person_tool_stays_on_sets_1_and_2(made: dict, tmp_path: Path) -> None:
    whole = added(made, tmp_path)
    design = tmp_path / "form.json"
    design.write_text(json.dumps(whole), encoding="utf-8")
    study = Study(tmp_path / "study" / "pages.json", tmp_path / "r.jsonl", design)
    assert sorted(study.sets) == [1, 2]
    assert len(study.start(1)["items"]) == 30 and len(study.start(2)["items"]) == 30


def test_the_script_makes_set_3_from_the_mapping() -> None:
    script = (export_set3.HERE / "form" / "make_form.gs").read_text(encoding="utf-8")
    for used in ("function makeFormSet3()", "makeForm('3')", "mapping.overrides",
                 "over.intro || q.intro", "over.consent_help || q.consent.help",
                 "setProgressBar(true)"):
        assert used in script, used


def test_the_readme_gives_the_steps_for_set_3() -> None:
    text = (export_set3.HERE / "form" / "README.md").read_text(encoding="utf-8")
    for needed in ("makeFormSet3", "rating-form-set3", "About 3-4 minutes", "3=",
                   "backend.estimator.train_visual"):
        assert needed in text, needed


# --- what was committed ---------------------------------------------------------------


def committed() -> dict:
    return json.loads(export_form.RECORD.read_text(encoding="utf-8"))


def test_the_committed_set_3_is_twenty_pictures_of_this_design() -> None:
    whole = committed()
    chosen, order = whole["sets"]["3"], whole["orders"]["3"]
    assert len(order) == len(set(order)) == 20
    assert (len(chosen["own"]), len(chosen["anchors"]), len(chosen["repeats"])) == (15, 3, 2)
    shared = whole["sets"]["1"]["anchors"] + whole["sets"]["2"]["anchors"]
    assert set(chosen["anchors"]) <= set(shared)


def test_no_excluded_page_was_committed() -> None:
    assert not {row["id"] for row in json.loads(export_set3.MANIFEST.read_text(
        encoding="utf-8"))["pages"]} & set(export_set3.EXCLUDED)


def test_the_committed_manifest_is_the_pages_the_mapping_names() -> None:
    whole = committed()
    pictures = train.read_pictures(export_set3.MANIFEST)
    named = {(whole["pictures"][n]["url"], whole["pictures"][n]["state"]):
             whole["pictures"][n]["sha256"] for n in whole["sets"]["3"]["own"]}
    assert {key: row["sha256"] for key, row in pictures.items()} == named


def test_the_committed_sets_1_and_2_match_their_hashes_in_the_manifest() -> None:
    whole = committed()
    rated = train.read_pictures(train.PICTURES)
    for name in whole["sets"]["1"]["own"] + whole["sets"]["2"]["own"]:
        picture = whole["pictures"][name]
        assert rated[(picture["url"], picture["state"])]["sha256"] == picture["sha256"]
