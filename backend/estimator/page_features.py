"""What a page is like, as numbers, before anyone decides what they mean.

The estimator's job will be to say how much a page is asking of the person in
front of it. This module is the half of that which can be measured: raw counts
and two ratios, read from one page read, with **no scoring, no weighting and
no normalisation**. Those need a corpus and a calibration, and neither exists
yet (STATUS.md). A feature here is a fact about the page, not a judgement
about it, and nothing in this file knows which direction is "harder".

That order matters more than it looks. Weights chosen before there is a corpus
are weights chosen from intuition, and they then decide what the corpus is
allowed to say. So: collect first (`tools/evaluation/collect_corpus`), look at
the spread, and only then argue about what a load score is.

The features, and what each one is:

| Feature | Unit | Read from |
|---|---|---|
| `interactive` | count | the controls that are not links: buttons, fields, pickers |
| `links` | count | links, live and dead |
| `inferred` | count | of those, the ones whose role was worked out from layout |
| `text_density` | characters per 1000px² | text boxes inside the viewport |
| `max_depth` | count | the deepest element in the DOM |
| `overlays` | count | things covering the page (`overlays.analyse`) |
| `form_fields` | count | inputs, textareas, selects and field roles |
| `dead_link_ratio` | 0–1 | dead links over links |
| `reading_grade` | US school grade | Flesch–Kincaid over the visible text, counted per block |

**`interactive` and `links` were one feature for a day, and the corpus took
it back.** They were merged into a single `controls` on 2026-09-20, on the
evidence of the first corpus: 19 of 20 pages differed in both and the two
numbers were within a few percent of each other, because a public page's
controls are nearly all links. Two features carrying one signal get weighted
twice, and that reasoning was right about the pages it was looking at.

It was looking at the wrong pages. The extended corpus separates them exactly
where SIMBA operates — `link_share` is **0.00** on a login (0 links, 3
controls), **0.18** on the railways calendar (12 of 66) and **0.50** on its
station list (12 of 24), against a median of 0.92 across everything else. A
form, a picker and a dropdown are controls that are not links, and those are
the pages this project exists for. So the two are separate features again,
and the merge is recorded in DECISIONS.md as instructed, implemented and
reversed rather than quietly dropped.

**The split is disjoint, which the pre-merge version was not.** `interactive`
used to be *every* element including links, with `links` beside it as a
subset, so a nav link counted twice before anything was weighted. That was
the real form of the double-counting the merge was reaching for. Now
`interactive` is the controls that are **not** links, `links` is the links,
and `controls = interactive + links` stays in every row as the total.

`controls`, `dead_links`, `characters`, `words`, `sentences` and `syllables`
come back as raw counts, with `link_share` as the ratio the argument was had
over. They are what the features are built from, and without them neither a
derived number nor a merge can be checked or undone later.

**Viewport.** Density is per *visible* area, which is why CLAUDE.md freezes
the viewport at 1280x800: change it and the density changes without the page
changing. Only text whose box falls inside the viewport counts, and the page
is assumed to be at the top of its scroll, which is how every read in this
project happens.

**Pixels.** Everything here is CSS pixels. `snapshot.parse` converts the
snapshot's device-pixel boxes on the way in (2026-09-20), so this module reads
`document.bounds` and the frozen 1280x800 viewport in the same units without
knowing anything about the display. It did carry a `device_pixel_ratio`
argument for a day, which is exactly the kind of thing every caller forgets.

**Reading grade is over all visible text**, not only what is in the viewport.
How hard a page is to read is a property of the page; how much of it is on
screen at once is what density is for.

No new dependency: Flesch–Kincaid is nine lines of arithmetic, and the
syllable counter below is the usual vowel-group heuristic.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass

from backend.perception.overlays import analyse
from backend.perception.serializer import VIEWPORT, PageView
from backend.perception.snapshot import ELEMENT_NODE, TEXT_NODE, Document, Rect, visible

#: Roles that mean "a thing the person has to fill in or choose", beyond the
#: tags below. A library that builds a field out of divs reaches perception as
#: one of these or not at all.
FIELD_ROLES = frozenset({
    "textbox", "searchbox", "combobox", "checkbox", "radio", "spinbutton",
    "slider", "listbox", "switch", "menuitemcheckbox", "menuitemradio",
})
FIELD_TAGS = frozenset({"input", "textarea", "select"})

#: One unit of area for the density, so the number lands in a readable range
#: rather than as 0.0004 characters per pixel.
AREA_UNIT = 1000.0

#: Tags whose text is in the document and never on the screen. A text node
#: inside one of these is not reading material.
#:
#: Checked by tag rather than by computed style, because a `display: none`
#: element is not in the layout tree at all and so has no style entry in the
#: snapshot — "no style" reads as "nothing hiding it" for every other node,
#: which is right for a plain `<div>` and catastrophically wrong for a
#: `<script>`. Counting script source as prose put **23,422 words** on
#: `lite.cnn.com` and a reading grade of 98 (EVALUATION.md, 2026-09-19b).
NOT_RENDERED = frozenset({"script", "style", "noscript", "template", "head",
                          "title", "meta", "link"})

_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")
_SENTENCE_END = re.compile(r"[.!?]+(?:\s|$)")
_VOWELS = "aeiouy"


@dataclass(frozen=True)
class PageFeatures:
    """One page, as raw numbers. Nothing here is scaled or scored."""

    interactive: int
    links: int
    inferred: int
    text_density: float
    max_depth: int
    overlays: int
    form_fields: int
    dead_link_ratio: float
    reading_grade: float

    # The raw counts the features are built from, so a derived number can be
    # recomputed — and this split merged again — without reading the page
    # again. `controls` is the total the two halves came from.
    controls: int
    dead_links: int
    characters: int
    viewport_characters: int
    words: int
    sentences: int
    syllables: int

    @property
    def link_share(self) -> float:
        """How much of what this page offers is a link.

        Near 1 on a page of links, near 0 on a form. This is the number the
        merge was argued over in both directions, so it stays in every row
        whichever way the argument goes next.
        """
        return round(self.links / self.controls, 3) if self.controls else 0.0

    def as_dict(self) -> dict[str, float]:
        return {**asdict(self), "link_share": self.link_share}


# --- the words on the page --------------------------------------------------


def syllables(word: str) -> int:
    """How many syllables a word has, by the usual heuristic.

    Vowel groups, less a silent final `e`, never fewer than one. It is wrong
    about "queue" and "business" and right often enough that the grade it
    feeds is stable across pages, which is what a feature needs to be. A
    dictionary would be more accurate and is a dependency (CLAUDE.md).
    """
    word = word.lower().strip("'’-")
    if not word:
        return 0
    groups = 0
    previous_was_vowel = False
    for letter in word:
        is_vowel = letter in _VOWELS
        if is_vowel and not previous_was_vowel:
            groups += 1
        previous_was_vowel = is_vowel
    if word.endswith("e") and not word.endswith(("le", "ee")) and groups > 1:
        groups -= 1
    return max(groups, 1)


def reading_grade(text: str | Sequence[str]) -> tuple[float, int, int, int]:
    """Flesch–Kincaid grade level, with the counts it was computed from.

    `0.39 × words/sentence + 11.8 × syllables/word − 15.59`, the standard
    coefficients. Returns `(grade, words, sentences, syllables)`.

    **Sentences are counted per block**, and a block with no full stop in it
    counts as one. Give it a string and the whole thing is one block; give it
    the page's blocks — a paragraph, a heading, a link, a table cell — and
    each is at least one sentence.

    That matters more than it sounds. Counting terminators across a whole page
    makes a wall of links a single enormous sentence: measured on this corpus
    before the change, `lite.cnn.com` came out at **grade 293** and Wikipedia's
    main page at **110**, which is not a reading level, it is a link count
    wearing one. Formatting is punctuation on a web page — a list item ends
    where the list item ends — and the raw counts come back beside the grade
    so anyone who disagrees can recompute it their way.

    Text with no words has no reading level, and that is reported as 0.0 with
    zero words beside it rather than as an easy page. A corpus row with
    `words: 0` is a page that had nothing to read, which is a fact about the
    page and not a missing measurement.
    """
    blocks = [text] if isinstance(text, str) else list(text)
    words = 0
    sentences = 0
    counted = 0
    for block in blocks:
        found = _WORD.findall(block)
        if not found:
            continue
        words += len(found)
        # At least one: a heading with no full stop is still a sentence's
        # worth of reading, and dividing by zero is not a grade.
        sentences += max(len(_SENTENCE_END.findall(block)), 1)
        counted += sum(syllables(word) for word in found)
    if not words:
        return 0.0, 0, 0, 0
    grade = (0.39 * words / sentences) + (11.8 * counted / words) - 15.59
    return round(grade, 2), words, sentences, counted


# --- the page ---------------------------------------------------------------


def _inside(box: Rect, viewport: tuple[int, int]) -> bool:
    """Whether a box shows any of itself in the viewport, unscrolled.

    Both are CSS pixels: `snapshot.parse` converted the box on the way in.
    """
    x, y, width, height = box
    if width <= 0 or height <= 0:
        return False
    return x < viewport[0] and y < viewport[1] and x + width > 0 and y + height > 0


def _visible_text(
    document: Document, viewport: tuple[int, int]
) -> tuple[list[str], int]:
    """The visible text as blocks, and how much of it is in the viewport.

    Walked from the text nodes rather than through `text_of`, because this
    needs every text node in the document and where each one sits, and
    `text_of` is built to answer the opposite question — the text under one
    node, capped.

    Text nodes are grouped by the nearest ancestor that is not `display:
    inline`, so `<p>Hello <b>world</b>. Bye.</p>` is one block of prose rather
    than three fragments, and each `<li>` in a nav is its own block.
    """
    shown: dict[int, bool] = {}
    block_of: dict[int, int] = {}

    def block(index: int) -> int:
        """The nearest ancestor that lays its text out as a block."""
        if index in block_of:
            return block_of[index]
        parent = document.parents[index] if index < len(document.parents) else -1
        if parent < 0:
            block_of[index] = index
            return index
        display = (document.styles.get(parent) or {}).get("display", "")
        result = parent if not display.startswith("inline") else block(parent)
        block_of[index] = result
        return result

    def is_shown(index: int) -> bool:
        """Whether this node, and everything above it, is on the screen."""
        if index in shown:
            return shown[index]
        style = document.styles.get(index)
        here = visible(style) if style else True
        if document.tag(index) in NOT_RENDERED:
            here = False
        parent = document.parents[index] if index < len(document.parents) else -1
        result = here and (parent < 0 or is_shown(parent))
        shown[index] = result
        return result

    blocks: dict[int, list[str]] = {}
    order: list[int] = []
    in_viewport = 0
    for index, node_type in enumerate(document.node_types):
        if node_type != TEXT_NODE:
            continue
        value = " ".join(document.node_values[index].split())
        if not value or not is_shown(index):
            continue
        owner = block(index)
        if owner not in blocks:
            blocks[owner] = []
            order.append(owner)
        blocks[owner].append(value)
        # A text node's own box when the snapshot gave it one, and its
        # parent's otherwise — the parent is the element the text is laid out
        # in, so its box is the right answer for "is this on screen".
        parent = document.parents[index] if index < len(document.parents) else -1
        box = document.bounds.get(index) or document.bounds.get(parent)
        if box is not None and _inside(box, viewport):
            in_viewport += len(value)
    return [" ".join(blocks[owner]) for owner in order], in_viewport


def max_depth(document: Document) -> int:
    """The deepest element in the document, counting the root as 1."""
    depth_of: dict[int, int] = {}

    def depth(index: int) -> int:
        if index in depth_of:
            return depth_of[index]
        parent = document.parents[index] if index < len(document.parents) else -1
        result = 1 if parent < 0 else depth(parent) + 1
        depth_of[index] = result
        return result

    deepest = 0
    for index, node_type in enumerate(document.node_types):
        if node_type == ELEMENT_NODE:
            deepest = max(deepest, depth(index))
    return deepest


def features(
    view: PageView,
    document: Document,
    viewport: tuple[int, int] = VIEWPORT,
) -> PageFeatures:
    """The raw features of one page read.

    `view` is what `serializer.read` / `read_async` returned, and `document`
    is the parsed snapshot from the same read — the two have to describe one
    moment, or the counts belong to different pages.

    Lengths are CSS pixels throughout: `document.bounds` were converted when
    the snapshot was parsed, and `document.device_pixel_ratio` says what by.

    A `document` is required rather than optional: every text feature needs
    it, and a call with `SIMBA_OVERLAY_DETECTION=0` and
    `SIMBA_INFERRED_ROLES=0` gets no snapshot at all, which would silently
    produce a page with no text on it.
    """
    if document is None:  # pragma: no cover - a caller mistake, said out loud
        raise ValueError(
            "page_features needs the parsed snapshot; read the page with the "
            "default switches, which is what fetches it"
        )

    elements = view.elements
    links = [element for element in elements
             if element.role == "link" or element.tag == "a"]
    dead = [element for element in links if element.dead_link]
    fields = [element for element in elements
              if element.tag in FIELD_TAGS or element.role in FIELD_ROLES]

    blocks, in_viewport = _visible_text(document, viewport)
    grade, words, sentences, counted = reading_grade(blocks)
    text = " ".join(blocks)
    area_units = (viewport[0] * viewport[1]) / AREA_UNIT

    return PageFeatures(
        # Disjoint on purpose: a link is counted in `links` and nowhere else,
        # so the two can be weighted independently without weighting a nav
        # twice. `controls` below is the total.
        interactive=len(elements) - len(links),
        links=len(links),
        inferred=sum(1 for element in elements if element.inferred),
        text_density=round(in_viewport / area_units, 3) if area_units else 0.0,
        max_depth=max_depth(document),
        # Page-level blockers only: `analyse` with no target reports what is
        # covering the page, which is the thing a person has to deal with
        # before anything else on it.
        overlays=len(analyse(document, viewport).blockers),
        form_fields=len(fields),
        # 0.0 when there are no links at all. `links` is beside it, so the
        # difference between "no dead links" and "no links" stays readable.
        dead_link_ratio=round(len(dead) / len(links), 3) if links else 0.0,
        reading_grade=grade,
        controls=len(elements),
        dead_links=len(dead),
        characters=len(text),
        viewport_characters=in_viewport,
        words=words,
        sentences=sentences,
        syllables=counted,
    )
