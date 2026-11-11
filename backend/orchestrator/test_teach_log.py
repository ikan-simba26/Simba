"""The line teaching logs for a press it lets through without keeping
(2026-11-11, `fix/teach-list-choice`): where, as two whole numbers, and how
many list options the page held. Never a typed value, a label or anything
else the page sent."""

import inspect
import re

import pytest

from backend.orchestrator import teach
from backend.orchestrator.teach import _coordinate


@pytest.mark.parametrize("given, logged", [
    (412, 412), (88.6, 88), (-3, -3), (0, 0),
    ("04141234567890", -1), ("hunter2", -1), (None, -1), (True, -1),
    ({"x": 1}, -1), ([1, 2], -1), (float("nan"), -1), (float("inf"), -1), (1e12, -1),
])
def test_a_coordinate_is_a_number_or_minus_one(given: object, logged: int) -> None:
    assert _coordinate(given) == logged
    assert isinstance(_coordinate(given), int)


def test_the_line_has_room_for_numbers_only() -> None:
    """Every placeholder in the message is %d: whatever is passed, the line
    cannot carry text."""
    source = inspect.getsource(teach)
    message = re.search(r'"teaching: a press at (.*?)"\s*\n\s*"(.*?)"', source)
    assert message, "the line for a press let through is gone or reworded"
    placeholders = re.findall(r"%[a-z]", message.group(1) + message.group(2))
    assert placeholders == ["%d", "%d", "%d"]
