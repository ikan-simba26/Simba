"""The rating tool: the two sets, the session plan, the server, a whole session
in a browser, and the capture's size and scrollbar.

Everything runs against a temporary study — a handful of generated pictures —
so nothing here touches `data/ratings.jsonl` or the captured corpus.
"""

import asyncio
import base64
import concurrent.futures
import json
import random
import struct
import threading
from pathlib import Path

import pytest
from playwright.async_api import async_playwright
from playwright.sync_api import Playwright

from tools.evaluation.collect_corpus import STARTER_LIST
from tools.rating import capture
from tools.rating.serve import LABELS, QUESTION, SCALE, Study, serve
from tools.rating.session import (MIN_GAP, anchors, feature_ranks, heaviness, imbalance, plan,
                                  set_of, split)

#: A 1x1 PNG: the tool shows a picture, any picture will do.
PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


# --- the plan ---------------------------------------------------------------------


def test_every_page_once_and_two_repeats() -> None:
    pages = [f"p{n}" for n in range(50)]
    items = plan(pages, seed=7)

    assert len(items) == 52
    firsts = [item["page"] for item in items if not item["repeat"]]
    assert sorted(firsts) == sorted(pages)
    repeats = [item for item in items if item["repeat"]]
    assert len(repeats) == 2 and len({r["page"] for r in repeats}) == 2


def test_a_repeat_comes_well_after_its_first_showing() -> None:
    pages = [f"p{n}" for n in range(50)]
    for seed in range(200):
        items = plan(pages, seed=seed)
        for position, item in enumerate(items):
            if item["repeat"]:
                first = next(i for i, it in enumerate(items) if it["page"] == item["page"])
                assert position - first > MIN_GAP, (seed, first, position)


def test_the_order_is_random_and_the_seed_reproduces_it() -> None:
    pages = [f"p{n}" for n in range(50)]
    assert plan(pages, seed=1) == plan(pages, seed=1)
    assert plan(pages, seed=1) != plan(pages, seed=2)


def test_a_short_list_still_gets_its_repeats() -> None:
    items = plan(["a", "b", "c", "d"], seed=3)
    assert len(items) == 6 and sum(item["repeat"] for item in items) == 2


def test_only_the_pages_allowed_are_repeated() -> None:
    pages = [f"p{n}" for n in range(28)]
    allowed = set(pages[:22])
    for seed in range(200):
        repeated = {i["page"] for i in plan(pages, seed, repeatable=allowed) if i["repeat"]}
        assert len(repeated) == 2 and repeated <= allowed, seed


# --- the two sets ---------------------------------------------------------------------


def skewed_features(count: int = 50, seed: int = 4) -> dict[str, dict[str, float]]:
    """Features as lopsided as the corpus's: a few pages with most of the links."""
    rng = random.Random(seed)
    return {f"p{n:02d}": {"links": rng.paretovariate(1.2) * 20, "text": rng.uniform(0, 5),
                          "depth": rng.randint(4, 40), "overlays": rng.choice([0, 0, 0, 1, 2])}
            for n in range(count)}


def test_the_split_is_two_halves_of_every_page() -> None:
    features = skewed_features()
    sets = split(features, seed=1)
    assert len(sets[1]) == len(sets[2]) == 25
    assert sorted(sets[1] + sets[2]) == sorted(features)


def test_the_split_is_more_even_than_chance() -> None:
    """Against 200 random halvings of the same pages, the split's worst
    feature is closer between the sets than all but a few of them."""
    features = skewed_features()
    ranks = feature_ranks(features)
    found = imbalance(split(features, seed=1), ranks)
    rng = random.Random(9)
    pages = sorted(features)
    chance = []
    for _ in range(200):
        rng.shuffle(pages)
        chance.append(imbalance({1: pages[:25], 2: pages[25:]}, ranks))
    assert found < 0.05
    assert sum(c <= found for c in chance) <= 2


def test_both_sets_run_from_calm_to_heavy() -> None:
    features = skewed_features()
    heavy = heaviness(features)
    ordered = sorted(features, key=heavy.get)
    sets = split(features, seed=1)
    for pages in sets.values():
        # Pages are paired by heaviness and one of each pair goes to each set.
        assert any(p in pages for p in ordered[:2]) and any(p in pages for p in ordered[-2:])


def test_the_seed_makes_the_same_split_and_kinds_are_kept_even() -> None:
    features = skewed_features()
    kinds = {p: ("demo" if n % 3 else "public") for n, p in enumerate(sorted(features))}
    assert split(features, 5, kinds) == split(features, 5, kinds)
    sets = split(features, 5, kinds)
    counts = [sum(kinds[p] == "public" for p in sets[s]) for s in (1, 2)]
    assert abs(counts[0] - counts[1]) <= 2


def test_anchors_are_a_calm_a_middling_and_a_heavy_page() -> None:
    heavy = {f"p{n:02d}": n / 24 for n in range(25)}
    assert anchors(list(heavy), heavy) == ["p04", "p12", "p20"]


def test_odd_raters_rate_set_one_and_even_set_two() -> None:
    assert [set_of(n) for n in (1, 2, 3, 4, 101)] == [1, 2, 1, 2, 1]


# --- the server ---------------------------------------------------------------------


@pytest.fixture
def study(tmp_path: Path) -> Study:
    """Twelve pages in two sets of six; each set lends one page to the other,
    so a session is 6 + 1 pictures and two repeats."""
    folder = tmp_path / "rating"
    pages = folder / "pages"
    pages.mkdir(parents=True)
    rows, pictures = [], {}
    for n in range(12):
        (pages / f"page-{n}.png").write_bytes(PIXEL)
        rows.append({"id": f"page-{n}", "url": f"https://example.test/{n}",
                     "state": "as it loads", "kind": "public", "file": f"page-{n}.png",
                     "sha256": f"hash{n}"})
        pictures[f"P{n + 1:02d}"] = {"page": f"page-{n}"}
    rows.append({"id": "broken", "url": "https://example.test/x", "state": "as it loads",
                 "kind": "public", "error": "TimeoutError"})
    manifest = folder / "pages.json"
    manifest.write_text(json.dumps({"pages": rows}), encoding="utf-8")
    (folder / "examples").mkdir()
    (folder / "examples" / "E1.png").write_bytes(PIXEL)
    (folder / "examples" / "E2.png").write_bytes(PIXEL)
    design = folder / "form.json"
    design.write_text(json.dumps({"pictures": pictures, "sets": {
        "1": {"own": [f"P{n:02d}" for n in range(1, 7)], "lends": ["P03"], "anchors": ["P09"]},
        "2": {"own": [f"P{n:02d}" for n in range(7, 13)], "lends": ["P09"], "anchors": ["P03"]},
    }, "examples": [
        {"file": "E1.png", "says": "A calm one.", "answer": 1, "label": "Not at all"},
        {"file": "E2.png", "says": "A busy one.", "answer": 4, "label": "Very"},
    ]}), encoding="utf-8")
    return Study(manifest, tmp_path / "ratings.jsonl", design)


def test_a_session_is_the_raters_set_and_the_other_sets_anchor(study: Study) -> None:
    for rater, own, anchor in ((3, range(0, 6), "page-8"), (4, range(6, 12), "page-2")):
        started = study.start(rater)
        assert started["set"] == set_of(rater) and len(started["items"]) == 6 + 1 + 2
        state = study.sessions[started["session"]]
        shown = {item["page"] for item in state["items"]}
        assert shown == {f"page-{n}" for n in own} | {anchor}
        assert all("broken" not in item["image"] for item in started["items"])
        assert started["labels"] == LABELS and started["scale"] == SCALE == (1, 5)
        assert [e["image"] for e in started["examples"]] == ["/examples/E1.png",
                                                             "/examples/E2.png"]


def test_an_anchor_or_a_lent_page_is_never_repeated(study: Study) -> None:
    for _ in range(60):
        state = study.sessions[study.start(1)["session"]]
        repeated = {item["page"] for item in state["items"] if item["repeat"]}
        assert len(repeated) == 2 and not repeated & {"page-2", "page-8"}


def test_an_answer_is_written_with_what_was_actually_shown(study: Study) -> None:
    started = study.start(3)
    study.answer(started["session"], 1, 5, 4200)

    row = json.loads(study.ratings.read_text(encoding="utf-8"))
    assert (row["rater"], row["set"], row["position"], row["rating"], row["ms"]) == (
        3, 1, 1, 5, 4200)
    shown = started["items"][0]["image"]
    assert shown.endswith(f"{row['page']}.png")
    assert row["image_sha256"] == study.pages[row["page"]]["sha256"]
    assert row["question"] == QUESTION and row["of"] == 9
    # Both sets show page-8 and page-2: Set 2's anchor here, and Set 1's lent.
    assert row["anchor"] == (row["page"] in {"page-2", "page-8"})
    assert study.anchors == {"page-2", "page-8"}


def test_without_sets_the_tool_says_to_export_first(tmp_path: Path, study: Study) -> None:
    with pytest.raises(ValueError, match="export_form"):
        Study(study.images.parent / "pages.json", tmp_path / "r.jsonl", tmp_path / "none.json")


@pytest.mark.parametrize("rater", [0, -1, "3", 3.5, None, True, 5000])
def test_a_rater_must_be_a_number_below_the_online_ones(study: Study, rater) -> None:
    with pytest.raises(ValueError):
        study.start(rater)


@pytest.mark.parametrize("rating", [0, 6, "5", 4.5, None, True])
def test_a_rating_must_be_one_to_five(study: Study, rating) -> None:
    started = study.start(1)
    with pytest.raises(ValueError):
        study.answer(started["session"], 1, rating, 100)
    assert not study.ratings.exists()


def test_a_position_is_answered_once(study: Study) -> None:
    started = study.start(1)
    study.answer(started["session"], 2, 4, 100)
    with pytest.raises(ValueError):
        study.answer(started["session"], 2, 5, 100)
    with pytest.raises(ValueError):
        study.answer("not-a-session", 1, 5, 100)


# --- a whole session, in a browser ---------------------------------------------------


def test_a_whole_session_through_the_page(study: Study, playwright_instance: Playwright) -> None:
    server = serve(study, port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    browser = playwright_instance.chromium.launch()
    try:
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.goto(url)
        assert "About 5-7 minutes" in page.inner_text("#start")
        page.fill("#rater", "12")
        page.click("#begin")
        # The two worked examples first, each with its sentence and answer.
        page.wait_for_selector("#examples:not([hidden])")
        assert page.locator("#example-list figure").count() == 2
        figures = page.locator("#example-list figure").all_inner_texts()
        assert [f.split() for f in figures] == [
            "A calm one. Answer: Not at all.".split(), "A busy one. Answer: Very.".split()]
        page.click("#go")
        page.wait_for_selector("#rate:not([hidden])")
        assert page.inner_text("#question") == QUESTION
        # Five buttons, every one with its words.
        assert [b.strip().split("\n")[0] for b in
                page.locator("#scale button").all_inner_texts()] == list(LABELS)

        answers = [3, 5, 1, 4, 2, 5, 4, 1, 2]
        for n, rating in enumerate(answers, start=1):
            page.wait_for_function(
                f"document.getElementById('progress').innerText === 'Picture {n} of 9'"
                " && !document.querySelector('#scale button').disabled")
            assert page.get_attribute("#bar", "aria-valuenow") == str(n - 1)
            page.wait_for_timeout(150)
            if n % 2:
                page.keyboard.press(str(rating))          # by key
            else:
                page.click(f"#scale button[data-rating='{rating}']")   # by pressing
        page.wait_for_selector("#done:not([hidden])")
    finally:
        browser.close()
        server.shutdown()
        server.server_close()

    rows = [json.loads(line) for line in study.ratings.read_text(encoding="utf-8").splitlines()]
    assert [row["rating"] for row in rows] == answers
    assert [row["position"] for row in rows] == list(range(1, 10))
    assert {row["rater"] for row in rows} == {12} and {row["set"] for row in rows} == {2}
    assert sum(row["repeat"] for row in rows) == 2
    assert all(row["ms"] >= 100 for row in rows), [row["ms"] for row in rows]
    # What the rater actually saw, in size: the 1x1 picture, in a 1280x720 window.
    assert all(row["window"] == [1280, 720] for row in rows), rows[0]
    assert all(row["shown"] and row["shown"][0] >= 1 for row in rows), rows[0]


# --- the capture ---------------------------------------------------------------------


def test_every_corpus_page_has_its_own_id() -> None:
    ids = [capture.page_id(url, capture.name_of(drive)) for url, drive, _ in STARTER_LIST]
    assert len(ids) == len(set(ids))


def test_a_capture_is_1280x800_with_no_scrollbar(tmp_path: Path, monkeypatch) -> None:
    """A page three screens tall: the picture is the top 1280x800, and the
    page is laid out at the full 1280 — no 17px lost to a scrollbar.

    This checks the result, not the hiding: headless Chromium already shows
    no scrollbar here without the flag or the style (2026-09-25), so it would
    still pass if they were removed. It fails if a Chromium ever lays the
    page out narrower."""
    monkeypatch.setattr(capture, "PAGES", tmp_path)
    tall = "data:text/html," + "<p style='height:2400px;margin:0'>tall</p>"

    async def go() -> tuple[dict, dict]:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(args=["--hide-scrollbars"])
            page = await browser.new_page(viewport=capture.VIEWPORT, device_scale_factor=1)
            try:
                return await capture.photograph(page, tall, None, "test")
            finally:
                await browser.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        row, _ = pool.submit(lambda: asyncio.run(go())).result()

    assert "error" not in row, row
    assert row["layout_width"] == 1280
    width, height = struct.unpack(">II", (tmp_path / row["file"]).read_bytes()[16:24])
    assert (width, height) == (1280, 800)


def test_the_features_are_of_the_page_in_the_picture(tmp_path: Path, monkeypatch) -> None:
    """Since 2026-10-03 the picture and its corpus row come from one load: the
    page is navigated to once, read, and photographed. A page that says
    something different every time it loads shows it: the row's text is what
    that one load said, and both rows carry the run's id."""
    monkeypatch.setattr(capture, "PAGES", tmp_path)
    # Different text on every load, so two loads would not agree.
    changing = ("data:text/html,<p id=t></p><script>document.getElementById('t')"
                ".textContent = 'x'.repeat(10 + Math.floor(Math.random() * 500))</script>")
    run = capture.new_run()

    async def go() -> tuple[dict, dict, int, int]:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(args=["--hide-scrollbars"])
            page = await browser.new_page(viewport=capture.VIEWPORT, device_scale_factor=1)
            loads = []
            page.on("load", lambda _: loads.append(1))
            try:
                row, features = await capture.photograph(page, changing, None, "test", run)
                shown = len(await page.inner_text("#t"))
                return row, features, len(loads), shown
            finally:
                await browser.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        row, features, loads, shown = pool.submit(lambda: asyncio.run(go())).result()

    assert "error" not in row and "error" not in features, (row, features)
    assert loads == 1
    # The text the features counted is the text on the page that was photographed.
    assert features["characters"] == shown
    assert row["run"] == features["run"] == run["id"]
    assert run["date"] == run["taken_at"][:10]


def test_a_partial_capture_is_refused(monkeypatch) -> None:
    """Recapturing some pages would leave two runs side by side."""
    monkeypatch.setattr("sys.argv", ["capture", "--only", "pypi-org"])
    with pytest.raises(SystemExit, match="all pages in one run"):
        capture.main()
