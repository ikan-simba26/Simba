"""The order one rater sees the pages in, and the two that come back.

Every rateable page once, shuffled, plus **two repeats**: two pages chosen at
random and shown a second time later in the same session, marked as repeats.
A rater who gives a page 2 and then 6 is telling us how much a single rating
from them is worth, and without the repeats nobody could know that
(test–retest reliability, within a session).

A repeat is placed at least `MIN_GAP` pages after the first showing, so it is
not recognised from the page before it. On a very short list the gap shrinks
rather than the repeats disappearing.

Pure: the seed decides everything, so a session can be reconstructed from the
seed written in its rows.
"""

from __future__ import annotations

import random

REPEATS = 2
#: Pages between a page and its repeat, at least. Five of fifty is far enough
#: apart not to be a double take.
MIN_GAP = 5


def plan(page_ids: list[str], seed: int, repeats: int = REPEATS,
         min_gap: int = MIN_GAP) -> list[dict]:
    """The items of one session, in order: `{"page": id, "repeat": bool}`."""
    rng = random.Random(seed)
    order = list(page_ids)
    rng.shuffle(order)
    items = [{"page": page, "repeat": False} for page in order]

    n = len(items)
    gap = min(min_gap, max(1, n // 3))
    # A page can be repeated only if there is room for the gap after it.
    eligible = [item["page"] for position, item in enumerate(items) if n - 1 - position >= gap]
    for page in rng.sample(eligible, min(repeats, len(eligible))):
        first = next(i for i, item in enumerate(items) if item["page"] == page)
        # After the gap, anywhere up to the end of the session.
        at = rng.randint(first + gap + 1, len(items))
        items.insert(at, {"page": page, "repeat": True})
    return items
