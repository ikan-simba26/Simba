"""The demo recorder never records against the live site, and answers questions.

No browser and no stack: the recording itself is checked by running it and
reading what it says it did (EVALUATION.md). These hold the two promises a
recording cannot show by itself.
"""

import pytest

from tools import record_demo


@pytest.mark.parametrize("site", [
    "https://www.pakrailways.gov.pk/train", "http://www.pakrailways.gov.pk/", "",
])
def test_a_railways_clip_is_refused_unless_it_runs_on_our_copy(site: str) -> None:
    with pytest.raises(SystemExit, match="railways-local"):
        record_demo.refuse_the_live_site(site)


def test_our_copy_is_accepted() -> None:
    record_demo.refuse_the_live_site("http://127.0.0.1:5200")


def test_the_railways_clip_is_the_demo_script() -> None:
    """The goal and the answers DEMO.md tells a presenter to give."""
    clip = next(c for c in record_demo.CLIPS if c[0] == "railways")
    assert clip[2] == "trains to Rawalpindi tomorrow"
    assert record_demo.ANSWERS["railways"] == {"type": ["Lahore"], "pick": ["Lahore Cantt"]}


def test_a_clip_whose_goal_leaves_out_the_bill_has_one_to_give() -> None:
    """A clip with no reference number in its goal is asked for one, and must
    have one to type, or it presses "That's it" on an empty box until the run
    gives up."""
    from datetime import date

    from backend.orchestrator.details import by_keywords

    for name, backend, goal, _ in record_demo.CLIPS:
        if backend != "real" or "bill" not in goal.lower():
            continue
        asked = by_keywords("billing", goal, date(2026, 10, 1)).reference is None
        assert not asked or record_demo.ANSWERS.get(name, {}).get("type"), name
