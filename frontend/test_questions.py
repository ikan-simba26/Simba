"""A question the backend asks, answered in a real browser.

Since 2026-09-30 a step is not always something to agree to. When a goal
leaves out something the task needs — where a journey starts, which day, the
reference number on a bill — the backend asks for it as an ordinary
`step.presented`, with a few buttons where the answers are few
(`backend/orchestrator/details.py`). Those buttons carry ids of their own:
`choice:0`, `choice:1`, and so on.

The overlay used to stop the task on any answer but go-ahead, so pressing
"Tomorrow" showed the stop screen and the run was over — the backend went on
waiting for a response it had already been sent, and the person saw "I've
stopped, as you asked." to a question they had just answered. The one id that
stops is `cancel`, and this renders the case in a real browser to prove it:
nothing but a declaration changed in `store.ts`, and a declaration is not
where this defect lived (DECISIONS.md, "measure the rendered result").

Built from source, through the same built overlay `test_terminal_states.py`
serves, against a scripted backend.
"""


from collections.abc import Iterator

import pytest
from playwright.sync_api import Page, Playwright

from frontend.test_terminal_states import (  # noqa: F401 - fixtures
    AWAIT_RESPONSE,
    Backend,
    overlay,
)

GOAL = "trains to Rawalpindi tomorrow"

# Three answers as buttons, which is what `voice.choices` builds, and the same
# way to stop every step offers.
A_QUESTION = {
    "step_index": 1, "step_total": 4,
    "instruction": "What day are you travelling?", "detail": "",
    "fields": [], "requires_confirmation": True, "findings": [],
    "actions": [
        {"id": "choice:0", "label": "Today", "kind": "primary"},
        {"id": "choice:1", "label": "Tomorrow", "kind": "primary"},
        {"id": "choice:2", "label": "Pick a day", "kind": "primary"},
        {"id": "cancel", "label": "Stop this", "kind": "secondary"},
    ],
}

# The other shape a question takes: one box, and one button to say that is it.
A_TYPED_QUESTION = {
    "step_index": 1, "step_total": 4,
    "instruction": "Where are you travelling from?", "detail": "",
    "fields": [{"id": "origin", "label": "From", "type": "text", "value": ""}],
    "requires_confirmation": True, "findings": [],
    "actions": [
        {"id": "confirm", "label": "That's it", "kind": "primary"},
        {"id": "cancel", "label": "Stop this", "kind": "secondary"},
    ],
}

A_STEP = {
    "step_index": 2, "step_total": 4,
    "instruction": "Let me set where you're starting from.",
    "detail": "Starting at Lahore.",
    "fields": [], "requires_confirmation": True, "findings": [],
    "actions": [
        {"id": "confirm", "label": "Set the departure station", "kind": "primary"},
        {"id": "cancel", "label": "Stop this", "kind": "secondary"},
    ],
}

STOPPED = "I've stopped, as you asked."


def asked(question: dict) -> list[tuple[str, dict]]:
    """A task that asks one question, and then gets on with a step."""
    return [
        ("task.started", {"goal": GOAL, "estimated_steps": 4}),
        ("state.changed", {"state": "thinking"}),
        ("state.changed", {"state": "waiting"}),
        ("step.presented", question),
        (AWAIT_RESPONSE, {}),
        ("state.changed", {"state": "thinking"}),
        ("state.changed", {"state": "waiting"}),
        ("step.presented", A_STEP),
    ]


@pytest.fixture(scope="module")
def backend() -> Backend:
    return Backend()


@pytest.fixture(scope="module")
def page(playwright_instance: Playwright) -> Iterator[Page]:
    browser = playwright_instance.chromium.launch()
    # The frozen viewport (CLAUDE.md).
    yield browser.new_page(viewport={"width": 1280, "height": 800})
    browser.close()


def ask(page: Page, overlay: str, backend: Backend, script) -> None:  # noqa: F811
    backend.script = script
    backend.responses.clear()
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    page.fill("input[aria-label='What would you like me to do?']", GOAL)
    page.get_by_role("button", name="Start").click()
    page.wait_for_selector("[data-testid=step-shell]", timeout=15000)


def answer(backend: Backend) -> dict:
    """The payload of the one `step.response` the overlay sent."""
    responses = [m for m in backend.responses if m.get("type") == "step.response"]
    assert len(responses) == 1, backend.responses
    return responses[0]["payload"]


def test_pressing_one_of_the_answers_answers_it(
    page: Page, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """The whole defect: the answer goes back, and the run carries on."""
    ask(page, overlay, backend, asked(A_QUESTION))
    page.get_by_role("button", name="Tomorrow", exact=True).click()

    page.wait_for_selector("text=Let me set where you're starting from.", timeout=15000)
    assert answer(backend)["action_id"] == "choice:1"
    assert STOPPED not in page.inner_text("body")


def test_every_answer_a_question_offers_carries_on(
    page: Page, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """Not just the first button: each one is an answer, and none stops."""
    for index, label in enumerate(("Today", "Tomorrow", "Pick a day")):
        ask(page, overlay, backend, asked(A_QUESTION))
        page.get_by_role("button", name=label, exact=True).click()
        page.wait_for_selector(
            "text=Let me set where you're starting from.", timeout=15000
        )
        assert answer(backend)["action_id"] == f"choice:{index}"
        assert STOPPED not in page.inner_text("body")


def test_a_typed_answer_carries_what_was_typed(
    page: Page, overlay: str, backend: Backend  # noqa: F811
) -> None:
    ask(page, overlay, backend, asked(A_TYPED_QUESTION))
    page.fill("input[aria-label='From']", "Lahore")
    page.get_by_role("button", name="That's it", exact=True).click()

    page.wait_for_selector("text=Let me set where you're starting from.", timeout=15000)
    payload = answer(backend)
    assert payload["action_id"] == "confirm"
    assert payload["input_values"] == {"origin": "Lahore"}


def test_stop_on_a_question_still_stops(
    page: Page, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """The one answer that does end the task, on a question like any step."""
    ask(page, overlay, backend, [
        ("task.started", {"goal": GOAL, "estimated_steps": 4}),
        ("state.changed", {"state": "thinking"}),
        ("state.changed", {"state": "waiting"}),
        ("step.presented", A_QUESTION),
        (AWAIT_RESPONSE, {}),
        ("task.failed", {"reason": "You asked me to stop.", "recoverable": True}),
    ])
    page.get_by_role("button", name="Stop this", exact=True).click()

    page.wait_for_selector(f"text={STOPPED}", timeout=15000)
    assert answer(backend)["action_id"] == "cancel"


def test_the_question_is_not_a_web_address_and_has_buttons(
    page: Page, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """A question is a step screen like any other, so what is true of every
    step is true of it: something to press, and no web address on it."""
    ask(page, overlay, backend, asked(A_QUESTION))
    labels = page.eval_on_selector_all(
        "button:not([disabled])",
        "buttons => buttons.filter(b => b.offsetParent !== null)"
        ".map(b => b.innerText.trim())",
    )
    assert "Today" in labels and "Stop this" in labels
    body = page.inner_text("body")
    for address in ("http://", "https://", "127.0.0.1"):
        assert address not in body, address
    # Nothing was sent before the person answered.
    assert not [m for m in backend.responses if m.get("type") == "step.response"]
