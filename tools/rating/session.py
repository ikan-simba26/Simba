"""Which pages a rater sees, in what order, and the two that come back.

**Two sets** (2026-10-23). The 50 pages are split into Set 1 and Set 2, 25
each, so that a rater rates 30 pictures instead of 52 (DECISIONS.md, *Two
sets of 30*). `split` makes the two sets alike in how heavy their pages are,
feature by feature; `anchors` picks three pages of each set — one calm, one
middling, one heavy — that are shown in the other set as well, so that the
two groups of raters can be checked against each other on the same pages.
A rater of Set 1 sees its 25 pages, Set 2's three anchors, and two repeats:
30 pictures.

**Two repeats**: two of the set's own pages, chosen at random and shown a
second time later in the same session, marked as repeats. A rater who gives
a page 1 and then 5 is telling us how much a single rating from them is
worth, and without the repeats nobody could know that (test–retest
reliability, within a session). An anchor is never repeated, so every rater
answers each anchor exactly once.

A repeat is placed at least `MIN_GAP` pages after the first showing, so it is
not recognised from the page before it. On a very short list the gap shrinks
rather than the repeats disappearing.

Pure: the seed decides everything, so a session can be reconstructed from the
seed written in its rows.
"""

from __future__ import annotations

import random
from collections import Counter

REPEATS = 2
#: Pages between a page and its repeat, at least. Five of thirty is far enough
#: apart not to be a double take.
MIN_GAP = 5
SETS = (1, 2)
#: Pages of each set shown in the other set as well.
ANCHORS = 3
#: Random assignments `split` tries, keeping the most even.
TRIES = 4000


def plan(page_ids: list[str], seed: int, repeats: int = REPEATS,
         min_gap: int = MIN_GAP, repeatable: set[str] | None = None) -> list[dict]:
    """The items of one session, in order: `{"page": id, "repeat": bool}`.

    Only pages in `repeatable` may be repeated, when it is given."""
    rng = random.Random(seed)
    order = list(page_ids)
    rng.shuffle(order)
    items = [{"page": page, "repeat": False} for page in order]

    n = len(items)
    gap = min(min_gap, max(1, n // 3))
    # A page can be repeated only if there is room for the gap after it.
    eligible = [item["page"] for position, item in enumerate(items)
                if n - 1 - position >= gap
                and (repeatable is None or item["page"] in repeatable)]
    for page in rng.sample(eligible, min(repeats, len(eligible))):
        first = next(i for i, item in enumerate(items) if item["page"] == page)
        # After the gap, anywhere up to the end of the session.
        at = rng.randint(first + gap + 1, len(items))
        items.insert(at, {"page": page, "repeat": True})
    return items


def _ranks(values: dict[str, float]) -> dict[str, float]:
    """Each page's rank from 0 (lowest) to 1 (highest), ties sharing the average."""
    ordered = sorted(values, key=lambda page: values[page])
    ranks: dict[str, float] = {}
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and values[ordered[j + 1]] == values[ordered[i]]:
            j += 1
        for page in ordered[i:j + 1]:
            ranks[page] = (i + j) / 2 / max(1, len(ordered) - 1)
        i = j + 1
    return ranks


def feature_ranks(features: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    """Feature -> page -> rank. Ranks, not raw values, because the features
    are skewed (links run from 0 to 715) and a few pages would decide a mean."""
    names = sorted({name for row in features.values() for name in row})
    return {name: _ranks({page: float(row[name]) for page, row in features.items()})
            for name in names}


def heaviness(features: dict[str, dict[str, float]]) -> dict[str, float]:
    """Each page's mean rank over every feature: 0 for the page lowest on all
    of them, 1 for the highest. A guide for splitting, not a load score."""
    ranks = feature_ranks(features)
    return {page: sum(r[page] for r in ranks.values()) / len(ranks) for page in features}


def imbalance(sets: dict[int, list[str]], ranks: dict[str, dict[str, float]]) -> float:
    """The largest difference between the two sets' mean rank on any feature."""
    one, two = (sets[s] for s in SETS)
    return max(abs(sum(r[p] for p in one) / len(one) - sum(r[p] for p in two) / len(two))
               for r in ranks.values())


def split(features: dict[str, dict[str, float]], seed: int,
          kinds: dict[str, str] | None = None, tries: int = TRIES) -> dict[int, list[str]]:
    """The pages in two sets of equal size, alike in every feature.

    The pages are sorted by `heaviness` and taken two at a time, one of each
    pair to each set, so both sets run from the calmest page to the heaviest.
    Which of a pair goes where is tried `tries` times at random, and the
    assignment kept is the one whose sets differ least on their worst
    feature; with `kinds`, an uneven count of a kind (ours, public, demo...)
    breaks near-ties. An odd page out goes to Set 1."""
    rng = random.Random(seed)
    ranks = feature_ranks(features)
    heavy = heaviness(features)
    ordered = sorted(features, key=lambda page: (heavy[page], page))
    pairs = [ordered[i:i + 2] for i in range(0, len(ordered), 2)]

    def score(sets: dict[int, list[str]]) -> float:
        uneven = 0
        if kinds:
            one, two = (Counter(kinds[p] for p in sets[s]) for s in SETS)
            uneven = sum(abs(one[k] - two[k]) for k in set(one) | set(two))
        return imbalance(sets, ranks) + 0.005 * uneven

    best: tuple[float, dict[int, list[str]]] | None = None
    for _ in range(tries):
        sets: dict[int, list[str]] = {s: [] for s in SETS}
        for pair in pairs:
            if len(pair) == 1:
                sets[1].append(pair[0])
                continue
            first, second = pair if rng.random() < 0.5 else pair[::-1]
            sets[1].append(first)
            sets[2].append(second)
        found = score(sets)
        if best is None or found < best[0]:
            best = (found, sets)
    assert best is not None
    return {s: sorted(pages) for s, pages in best[1].items()}


def anchors(pages: list[str], heavy: dict[str, float], count: int = ANCHORS) -> list[str]:
    """`count` pages of one set spread over its heaviness: with three, the
    pages a sixth, a half and five sixths of the way from its calmest."""
    ordered = sorted(pages, key=lambda page: (heavy[page], page))
    return [ordered[min(len(ordered) - 1, int((k + 0.5) * len(ordered) / count))]
            for k in range(count)]


def set_of(rater: int) -> int:
    """The set an in-person rater rates: odd numbers Set 1, even Set 2, so
    raters numbered in turn alternate between the two."""
    return 1 if rater % 2 else 2
