"""The rating tool: the session plan, the server, a whole session in a browser,
and the capture's size and scrollbar.

Everything runs against a temporary study — a handful of generated pictures —
so nothing here touches `data/ratings.jsonl` or the captured corpus.
"""

import asyncio
import base64
import concurrent.futures
import json
import struct
import threading
from pathlib import Path

import pytest
from playwright.async_api import async_playwright
from playwright.sync_api import Playwright

from tools.evaluation.collect_corpus import STARTER_LIST
from tools.rating import capture
from tools.rating.serve import QUESTION, Study, serve
from tools.rating.session import MIN_GAP, plan

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


# --- the server ---------------------------------------------------------------------


@pytest.fixture
def study(tmp_path: Path) -> Study:
    pages = tmp_path / "rating" / "pages"
    pages.mkdir(parents=True)
    rows = []
    for n in range(5):
        (pages / f"page-{n}.png").write_bytes(PIXEL)
        rows.append({"id": f"page-{n}", "url": f"https://example.test/{n}",
                     "state": "as it loads", "kind": "public", "file": f"page-{n}.png",
                     "sha256": f"hash{n}"})
    rows.append({"id": "broken", "url": "https://example.test/x", "state": "as it loads",
                 "kind": "public", "error": "TimeoutError"})
    manifest = tmp_path / "rating" / "pages.json"
    manifest.write_text(json.dumps({"pages": rows}), encoding="utf-8")
    return Study(manifest, tmp_path / "ratings.jsonl")


def test_a_page_that_failed_to_capture_is_never_shown(study: Study) -> None:
    started = study.start(3)
    assert len(started["items"]) == 5 + 2
    assert all("broken" not in item["image"] for item in started["items"])


def test_an_answer_is_written_with_what_was_actually_shown(study: Study) -> None:
    started = study.start(3)
    study.answer(started["session"], 1, 6, 4200)

    row = json.loads(study.ratings.read_text(encoding="utf-8"))
    assert (row["rater"], row["position"], row["rating"], row["ms"]) == (3, 1, 6, 4200)
    shown = started["items"][0]["image"]
    assert shown.endswith(f"{row['page']}.png")
    assert row["image_sha256"] == study.pages[row["page"]]["sha256"]
    assert row["question"] == QUESTION and row["of"] == 7


@pytest.mark.parametrize("rater", [0, -1, "3", 3.5, None, True, 10000])
def test_a_rater_must_be_a_number(study: Study, rater) -> None:
    with pytest.raises(ValueError):
        study.start(rater)


@pytest.mark.parametrize("rating", [0, 8, "5", 4.5, None, True])
def test_a_rating_must_be_one_to_seven(study: Study, rating) -> None:
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
        page.fill("#rater", "12")
        page.click("#begin")
        page.wait_for_selector("#rate:not([hidden])")
        assert page.inner_text("#question") == QUESTION

        answers = [3, 5, 1, 7, 2, 6, 4]
        for n, rating in enumerate(answers, start=1):
            page.wait_for_function(f"document.getElementById('progress').innerText === 'Page {n} of 7'"
                                   " && !document.querySelector('#scale button').disabled")
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
    assert [row["position"] for row in rows] == list(range(1, 8))
    assert {row["rater"] for row in rows} == {12}
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

    async def go() -> dict:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(args=["--hide-scrollbars"])
            page = await browser.new_page(viewport=capture.VIEWPORT, device_scale_factor=1)
            try:
                return await capture.photograph(page, tall, None, "test")
            finally:
                await browser.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        row = pool.submit(lambda: asyncio.run(go())).result()

    assert "error" not in row, row
    assert row["layout_width"] == 1280
    width, height = struct.unpack(">II", (tmp_path / row["file"]).read_bytes()[16:24])
    assert (width, height) == (1280, 800)
