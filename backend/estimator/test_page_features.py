"""The raw features, on pages whose answers are known by hand.

Two kinds of test, on purpose:

  * arithmetic, on text and on small hand-built documents, where the expected
    number can be worked out on paper;
  * a real browser on the replicas, where the expected number is whatever the
    other perception tests already record — 66 elements on the course list, 1
    overlay, and so on. A feature that disagrees with the serializer about how
    many elements a page has is measuring something else.

Nothing here asserts that a number is *good*. There is no scoring yet and
these features are raw by decision (DECISIONS.md, 2026-09-19).
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest
from playwright.async_api import async_playwright

from backend.estimator.page_features import (
    FIELD_ROLES,
    FIELD_TAGS,
    PageFeatures,
    features,
    max_depth,
    reading_grade,
    syllables,
)
from backend.perception.serializer import VIEWPORT, read_async
from backend.perception.snapshot import ELEMENT_NODE, TEXT_NODE, Document

# --- the arithmetic ---------------------------------------------------------


@pytest.mark.parametrize("word, expected", [
    ("a", 1), ("the", 1), ("cat", 1), ("water", 2), ("beautiful", 3),
    ("registration", 4), ("cognitive", 3), ("make", 1), ("little", 2),
    ("free", 1), ("agree", 2), ("", 0),
])
def test_syllables_are_counted_by_vowel_group(word: str, expected: int) -> None:
    assert syllables(word) == expected


def test_a_short_plain_sentence_reads_as_a_low_grade() -> None:
    """"The cat sat on the mat." — six one-syllable words, one sentence.

    0.39 × 6 + 11.8 × 1 − 15.59 = −1.45. Flesch-Kincaid goes negative on text
    this simple, and that is the formula being right rather than a bug: the
    scale is a US school grade and there is no grade below the first.
    """
    grade, words, sentences, counted = reading_grade("The cat sat on the mat.")
    assert (words, sentences, counted) == (6, 1, 6)
    assert grade == pytest.approx(-1.45, abs=0.01)


def test_a_long_latinate_sentence_reads_as_a_high_grade() -> None:
    text = ("Notwithstanding the aforementioned considerations, the "
            "administrative determination regarding eligibility requires "
            "documentation substantiating continuous residency.")
    grade, words, sentences, _ = reading_grade(text)
    assert sentences == 1
    assert grade > 20, grade


def test_text_with_nothing_to_read_has_no_grade_rather_than_an_easy_one() -> None:
    assert reading_grade("   ") == (0.0, 0, 0, 0)
    assert reading_grade("£ 14,382 — 15-09-2026") == (0.0, 0, 0, 0)


def test_a_page_with_no_full_stop_still_has_a_sentence() -> None:
    """A page of headings is not a division by zero."""
    grade, words, sentences, _ = reading_grade("Course Registration Portal")
    assert (words, sentences) == (3, 1)
    assert grade > 0


def test_a_wall_of_links_is_not_one_enormous_sentence() -> None:
    """Each block is at least one sentence, so formatting counts as
    punctuation.

    Counted across the page instead, `lite.cnn.com` measured **grade 293** and
    Wikipedia's main page **110** in the first corpus run — a link count in the
    shape of a reading level (EVALUATION.md, 2026-09-19b).
    """
    links = ["World news", "Business", "Sport today", "Weather", "Contact us"] * 6

    as_blocks, words, sentences, _ = reading_grade(links)
    as_one_page, same_words, one_sentence, _ = reading_grade(" ".join(links))

    assert (words, sentences) == (48, 30)
    assert (same_words, one_sentence) == (48, 1)
    # The same words, read two ways: a nav full of two-word labels, or one
    # forty-eight-word sentence nobody wrote.
    assert as_blocks < 10 < as_one_page


def test_prose_in_one_block_is_still_split_on_full_stops() -> None:
    """Blocks add boundaries; they do not remove the ones punctuation gives."""
    grade, words, sentences, _ = reading_grade(["The cat sat. The dog ran."])
    assert (words, sentences) == (6, 2)
    assert grade < 0


# --- small documents, built by hand -----------------------------------------


def document_of(*nodes: tuple[int, int, str, str]) -> Document:
    """A `Document` from `(parent, node_type, name, value)` rows, in order."""
    parents = [row[0] for row in nodes]
    children: dict[int, list[int]] = {}
    for index, parent in enumerate(parents):
        children.setdefault(parent, []).append(index)
    return Document(
        strings=[],
        parents=parents,
        node_types=[row[1] for row in nodes],
        node_names=[row[2] for row in nodes],
        node_values=[row[3] for row in nodes],
        backend_ids=list(range(len(nodes))),
        attributes=[{} for _ in nodes],
        children=children,
        index_of_backend_id={i: i for i in range(len(nodes))},
    )


def test_depth_counts_the_deepest_element_with_the_root_as_one() -> None:
    #  html > body > div > p
    flat = document_of((-1, ELEMENT_NODE, "HTML", ""), (0, ELEMENT_NODE, "BODY", ""))
    assert max_depth(flat) == 2

    nested = document_of(
        (-1, ELEMENT_NODE, "HTML", ""), (0, ELEMENT_NODE, "BODY", ""),
        (1, ELEMENT_NODE, "DIV", ""), (2, ELEMENT_NODE, "P", ""),
        (3, TEXT_NODE, "#text", "hello"),
    )
    # The text node is a node, not an element, and does not add a level.
    assert max_depth(nested) == 4


def test_text_outside_the_viewport_is_read_but_not_counted_as_density() -> None:
    """Both numbers come from one walk, and they answer different questions.

    `characters` is what the page says; `viewport_characters` is what is on
    the screen at 1280x800, which is what density is per.
    """
    document = document_of(
        (-1, ELEMENT_NODE, "HTML", ""),
        (0, ELEMENT_NODE, "P", ""), (1, TEXT_NODE, "#text", "on screen"),
        (0, ELEMENT_NODE, "P", ""), (3, TEXT_NODE, "#text", "far below"),
    )
    document.bounds[1] = (0.0, 10.0, 200.0, 20.0)
    document.bounds[3] = (0.0, 5000.0, 200.0, 20.0)

    found = features(_view(), document)

    assert found.characters == len("on screen far below")
    assert found.viewport_characters == len("on screen")
    # 9 characters over 1024 units of 1000px².
    assert found.text_density == pytest.approx(9 / 1024, abs=0.001)


def test_a_box_is_read_as_css_pixels_because_parse_converted_it() -> None:
    """The host reads at 1.5 device pixels to the CSS pixel, and CDP sends
    boxes in the first of those units.

    Measured on example.com's `<h1>`: `(256, 120, 768, 32)` headless,
    `(384, 180, 1152, 48)` in the host, same page, same CSS layout
    (EVALUATION.md, 2026-09-19b). `snapshot.parse` divides by the ratio on the
    way in (2026-09-20), so everything here is CSS pixels and this module has
    no ratio of its own — see `test_snapshot.py` for the conversion itself.
    """
    document = document_of(
        (-1, ELEMENT_NODE, "HTML", ""),
        (0, ELEMENT_NODE, "P", ""), (1, TEXT_NODE, "#text", "near the fold"),
    )
    # CSS y = 700, which is on an 800-tall screen.
    document.bounds[1] = (0.0, 700.0, 300.0, 30.0)
    assert features(_view(), document, VIEWPORT).viewport_characters == 13

    # And the same box where the conversion did not happen: 1050 device
    # pixels is off the bottom of a CSS viewport, and reads as off the screen.
    document.bounds[1] = (0.0, 1050.0, 300.0, 30.0)
    assert features(_view(), document, VIEWPORT).viewport_characters == 0


def test_script_source_is_not_reading_material() -> None:
    """A `<script>` is not in the layout tree, so it has no computed style in
    the snapshot, so "nothing is hiding it" is true and useless.

    Counted as prose it put 23,422 words and a reading grade of 98 on
    `lite.cnn.com`, which is a page of headlines (EVALUATION.md, 2026-09-19b).
    """
    document = document_of(
        (-1, ELEMENT_NODE, "HTML", ""),
        (0, ELEMENT_NODE, "P", ""), (1, TEXT_NODE, "#text", "Today's news"),
        (0, ELEMENT_NODE, "SCRIPT", ""),
        (3, TEXT_NODE, "#text", "var tracker = function (page) { return page; };"),
        (0, ELEMENT_NODE, "STYLE", ""), (5, TEXT_NODE, "#text", ".a { color: red }"),
    )
    document.bounds[1] = (0.0, 0.0, 200.0, 20.0)

    found = features(_view(), document)

    assert found.characters == len("Today's news")
    assert found.words == 2


def test_hidden_text_is_not_read_at_all() -> None:
    document = document_of(
        (-1, ELEMENT_NODE, "HTML", ""),
        (0, ELEMENT_NODE, "P", ""), (1, TEXT_NODE, "#text", "shown"),
        (0, ELEMENT_NODE, "P", ""), (3, TEXT_NODE, "#text", "hidden"),
    )
    document.bounds[1] = document.bounds[3] = (0.0, 0.0, 100.0, 20.0)
    document.styles[3] = {"display": "none"}

    assert features(_view(), document).characters == len("shown")


def _view():
    from backend.perception.serializer import PageView
    return PageView()


# --- the element-side features, against a real page -------------------------
#
# Async, and not because these tests need to be: a live `sync_playwright`
# session breaks `asyncio.run` in the same thread, and the orchestrator's
# tests are all `asyncio.run`. A session-scoped sync browser opened by a
# module that sorts before `orchestrator/` — `estimator/` does — failed 54 of
# them (`backend/conftest.py`). The replicas come from there; the browser is
# opened and closed here.


def drive_and_read(url: str, drive=None) -> tuple[PageFeatures, list]:
    """`_read`, run on a thread of its own.

    `asyncio.run` fails while a sync Playwright session is alive in the same
    thread, and perception's tests keep one open for the whole session. Which
    of the two runs first depends on how pytest was invoked — `pytest` sorts
    `estimator/` before `perception/` and everything passes, `pytest
    backend/perception backend/estimator` does not — and a test that depends
    on the order of the command line is a test that will fail on somebody
    else's machine. A worker thread has no sync session in it, so neither
    order matters (`backend/conftest.py`).
    """
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(_read(url, drive))).result()


async def _read(url: str, drive=None) -> tuple[PageFeatures, list]:
    """Load a page, optionally do something on it, and measure what is there."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": VIEWPORT[0],
                                                "height": VIEWPORT[1]})
        try:
            await page.goto(url)
            if drive is not None:
                await drive(page)
            view = await read_async(page, VIEWPORT)
            assert view.document is not None, "the read brought back no snapshot"
            return features(view, view.document, VIEWPORT), view.elements
        finally:
            await browser.close()


async def sign_in(page) -> None:
    await page.get_by_role("textbox", name="Student ID or Username").fill("student")
    await page.get_by_role("textbox", name="Password").fill("x")
    await page.get_by_role("button", name="Sign In").click()
    await page.wait_for_url("**/courses")


def test_the_course_list_matches_what_perception_records_for_it(replica: str) -> None:
    """66 elements, one overlay, 44 dead links — the figures in EVALUATION.md
    for this page, counted again through the features."""
    found, elements = drive_and_read(replica, sign_in)

    assert found.interactive == len(elements) == 66
    assert found.overlays == 1
    assert found.links == sum(1 for e in elements
                              if e.role == "link" or e.tag == "a")
    assert found.dead_link_ratio == pytest.approx(
        sum(1 for e in elements if e.dead_link) / found.links, abs=0.001)
    assert found.max_depth > 5
    assert found.words > 50
    assert found.text_density > 0


def test_the_login_page_is_the_simpler_of_the_two(replica: str) -> None:
    """Not a score — a sanity check that these numbers move with the page.

    A feature that reads the same on a three-field login as on a sixty-element
    course list is not measuring the page.
    """
    login, _ = drive_and_read(replica)
    courses, _ = drive_and_read(replica, sign_in)

    assert login.interactive < courses.interactive
    assert login.text_density < courses.text_density
    assert login.max_depth < courses.max_depth
    assert login.form_fields >= 2 and courses.form_fields == 0
    # And what does *not* move: both pages carry the same 45-link nav and
    # footer, so `links` and `dead_link_ratio` read identically on a page with
    # three fields and on a page with a modal over sixty controls. Recorded
    # because it is the kind of thing a corpus has to show before anything is
    # built on it (EVALUATION.md, 2026-09-19b).
    assert login.links == courses.links


def test_the_fields_on_the_billing_form_are_counted(billing: str) -> None:
    found, elements = drive_and_read(billing)

    assert found.form_fields >= 1
    assert found.interactive > found.form_fields
    # Nothing is covering this page, and nothing is inferred on it either.
    assert found.overlays == 0
    assert found.inferred == 0


def test_a_field_role_counts_even_when_the_tag_does_not(replica: str) -> None:
    """The set is roles *or* tags: a library that builds a field out of divs
    reaches perception as a role and nothing else."""
    assert "combobox" in FIELD_ROLES and "textbox" in FIELD_ROLES

    found, elements = drive_and_read(replica)

    assert found.form_fields == sum(
        1 for element in elements
        if element.tag in FIELD_TAGS or element.role in FIELD_ROLES
    )
    assert found.form_fields >= 2
