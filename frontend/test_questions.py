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
    "fields": [], "requires_confirmation": True, "findings": [], "step_kind": "date",
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


# --- a sign-in step that offers to keep the password ---------------------------

SIGN_IN = {
    "step_index": 1, "step_total": 3,
    "instruction": "Let me sign you in first.",
    "detail": "Fictional State University student portal.",
    "fields": [
        {"id": "username", "label": "Student ID or Username", "type": "text", "value": ""},
        {"id": "password", "label": "Password", "type": "password", "value": ""},
    ],
    "requires_confirmation": True, "findings": [],
    "actions": [
        {"id": "confirm", "label": "Sign in", "kind": "primary"},
        {"id": "remember", "label": "Sign in and save my password", "kind": "primary"},
        {"id": "cancel", "label": "Stop this", "kind": "secondary"},
    ],
}


@pytest.fixture
def short_page(playwright_instance: Playwright) -> Iterator[Page]:
    """The window's content at 150% (EVALUATION.md, 2026-09-25c)."""
    browser = playwright_instance.chromium.launch()
    yield browser.new_page(viewport={"width": 1266, "height": 606}, device_scale_factor=1.5)
    browser.close()


def test_a_sign_in_step_with_three_buttons_fits_at_150_percent(
    short_page: Page, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """The step that offers to keep a password has a third button. Every one of
    them, and both fields, must be on screen in a 150% window — by the
    overflow guard folding the step if it has to."""
    ask(short_page, overlay, backend, [
        ("task.started", {"goal": "Register for CS-401", "estimated_steps": 3}),
        ("state.changed", {"state": "waiting"}),
        ("step.presented", SIGN_IN),
        (AWAIT_RESPONSE, {}),
    ])
    short_page.wait_for_timeout(1500)  # the guard, if it folds, does so once

    height = short_page.viewport_size["height"]
    for name in ("Sign in", "Sign in and save my password", "Stop this"):
        box = short_page.get_by_role("button", name=name, exact=True).bounding_box()
        assert box is not None and box["y"] + box["height"] <= height, (name, box)
    password = short_page.locator("input[aria-label='Password']")
    assert password.get_attribute("type") == "password"
    box = password.bounding_box()
    assert box is not None and box["y"] + box["height"] <= height


def test_the_password_typed_goes_back_with_the_save_answer(
    short_page: Page, overlay: str, backend: Backend  # noqa: F811
) -> None:
    ask(short_page, overlay, backend, [
        ("task.started", {"goal": "Register for CS-401", "estimated_steps": 3}),
        ("state.changed", {"state": "waiting"}),
        ("step.presented", SIGN_IN),
        (AWAIT_RESPONSE, {}),
        ("state.changed", {"state": "acting"}),
    ])
    short_page.fill("input[aria-label='Student ID or Username']", "raham")
    short_page.fill("input[aria-label='Password']", "typed-here")
    short_page.get_by_role("button", name="Sign in and save my password", exact=True).click()
    short_page.wait_for_timeout(800)

    payload = answer(backend)
    assert payload["action_id"] == "remember"
    assert payload["input_values"] == {"username": "raham", "password": "typed-here"}
    assert "I've stopped, as you asked." not in short_page.inner_text("body")


# --- a question answered from the site's own list (2026-10-06) ------------------

# The live site's shape: capitals, a dot after JN., two stations in one city,
# and six names that begin with "Kot".
STATIONS = ["LAHORE JN.", "LAHORE CANTT", "KARACHI CANTT", "KARACHI CITY", "RAWALPINDI",
            "KOT LAKHPAT", "KOT RADHA KISHEN", "KOTRI JN.", "KOTADUJN.", "KOT NAJIBULLAH",
            "KOTSULTAN", "SUKKUR"]

A_LIST_QUESTION = {
    "step_index": 1, "step_total": 9,
    "instruction": "Where are you travelling to?", "detail": "",
    "fields": [{"id": "destination", "label": "To", "type": "choice", "value": "",
                "options": STATIONS}],
    "requires_confirmation": True, "findings": [],
    # With its shape since 2026-10-07, so the fit below includes it.
    "step_kind": "place",
    "actions": [
        {"id": "confirm", "label": "That's it", "kind": "primary"},
        {"id": "cancel", "label": "Stop this", "kind": "secondary"},
    ],
}

MATCHES = "[role=group][aria-label='Matching names'] button"


def matches_on(page: Page) -> list[str]:
    return [b.inner_text().strip() for b in page.locator(MATCHES).all()]


def test_nothing_from_the_list_shows_until_something_is_typed(
    page: Page, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """The screen does not start as a list to read."""
    ask(page, overlay, backend, asked(A_LIST_QUESTION))

    assert matches_on(page) == []
    # The row the names will be in holds the hint until then (2026-10-07).
    assert page.get_by_text("Type the first few letters to see the names.").is_visible()


def test_typing_shows_the_names_that_match_as_buttons(
    page: Page, overlay: str, backend: Backend  # noqa: F811
) -> None:
    ask(page, overlay, backend, asked(A_LIST_QUESTION))

    page.fill("input[aria-label='To']", "kar")

    assert matches_on(page) == ["Karachi Cantt", "Karachi City"]


def test_pressing_a_name_puts_it_in_the_box_and_that_is_what_is_sent(
    page: Page, overlay: str, backend: Backend  # noqa: F811
) -> None:
    ask(page, overlay, backend, asked(A_LIST_QUESTION))
    page.fill("input[aria-label='To']", "kar")

    page.locator(MATCHES, has_text="Karachi City").click()

    assert page.locator("input[aria-label='To']").input_value() == "Karachi City"
    assert matches_on(page) == ["Karachi City"]
    assert page.locator(MATCHES).first.get_attribute("aria-pressed") == "true"
    # Marked, not filled: "That's it" stays the one solid button on screen.
    fills = page.evaluate("""() => [
      getComputedStyle(document.querySelector('[aria-pressed=true]')).backgroundColor,
      getComputedStyle([...document.querySelectorAll('button')]
        .find(b => b.innerText.trim() === "That's it")).backgroundColor]""")
    assert fills[0] != fills[1], fills
    page.get_by_role("button", name="That's it", exact=True).click()
    page.wait_for_selector("text=Let me set where you're starting from.", timeout=15000)
    assert answer(backend)["input_values"] == {"destination": "Karachi City"}


def test_more_matches_than_fit_are_counted_not_listed(
    page: Page, overlay: str, backend: Backend  # noqa: F811
) -> None:
    ask(page, overlay, backend, asked(A_LIST_QUESTION))

    page.fill("input[aria-label='To']", "kot")

    # One row: the best match, and how many more in the second place.
    assert matches_on(page) == ["Kot Lakhpat"]
    assert page.get_by_text("5 more. Keep typing to find yours.").is_visible()


def test_a_name_nothing_on_the_list_has_says_so(
    page: Page, overlay: str, backend: Backend  # noqa: F811
) -> None:
    ask(page, overlay, backend, asked(A_LIST_QUESTION))

    page.fill("input[aria-label='To']", "narnia")

    assert matches_on(page) == []
    assert page.get_by_text("Nothing on the list matches that yet.").is_visible()


def test_a_list_question_fits_at_150_percent(
    short_page: Page, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """A match and the count of the rest, the box, both buttons and the row
    under the card, all on screen in a 150% window: nothing scrolls. Until
    2026-10-07 this checked the buttons only, and the row under the card was
    52px below the window."""
    ask(short_page, overlay, backend, asked(A_LIST_QUESTION))
    short_page.fill("input[aria-label='To']", "kot")
    short_page.wait_for_timeout(1500)  # the guard, if it folds, does so once

    height = short_page.viewport_size["height"]
    for name in ("That's it", "Stop this"):
        box = short_page.get_by_role("button", name=name, exact=True).bounding_box()
        assert box is not None and box["y"] + box["height"] <= height, (name, box)
    last = short_page.locator(MATCHES).last.bounding_box()
    assert last is not None and last["y"] + last["height"] <= height
    assert not short_page.evaluate("document.scrollingElement.scrollHeight > innerHeight")


# --- level 3 keeps the box a question is answered in -----------------------------


def test_at_level_3_the_box_stays_while_the_answer_is_typed(
    page: Page, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """Level 3 keeps only the fields a step cannot go on without. Until
    2026-10-06 it judged that by what had been typed, so the box vanished at
    the first keystroke and took the answer with it."""
    ask(page, overlay, backend, [
        ("task.started", {"goal": GOAL, "estimated_steps": 4}),
        ("load.updated", {"score": 0.9, "level": 3, "reason": "pause"}),
        ("state.changed", {"state": "waiting"}),
        ("step.presented", A_TYPED_QUESTION),
        (AWAIT_RESPONSE, {}),
        ("state.changed", {"state": "thinking"}),
        ("state.changed", {"state": "waiting"}),
        ("step.presented", A_STEP),
    ])
    box = page.locator("input[aria-label='From']")
    box.wait_for(timeout=5000)

    box.press_sequentially("Lahore", delay=40)
    page.wait_for_timeout(600)

    assert box.is_visible() and box.input_value() == "Lahore"
    page.get_by_role("button", name="That's it", exact=True).click()
    page.wait_for_selector("text=Let me set where you're starting from.", timeout=15000)
    assert answer(backend)["input_values"] == {"origin": "Lahore"}


def test_a_question_has_the_shape_of_what_it_asks(
    page: Page, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """The question screens look like every other step (2026-10-07)."""
    ask(page, overlay, backend, asked(A_LIST_QUESTION))
    assert page.get_by_test_id("step-kind").get_attribute("data-kind") == "place"
    ask(page, overlay, backend, asked(A_QUESTION))
    assert page.get_by_test_id("step-kind").get_attribute("data-kind") == "date"


# The sentence that explains a station the site does not have runs to two
# lines, and in the real window at 150% that question scrolled by 9px with a
# scrollbar down the side (EVALUATION.md, 2026-10-14): already at level 1, the
# guard's floor, the box's label still sat above it.
NARNIA = {**A_LIST_QUESTION,
          "instruction": "I couldn't find a station called Narnia. Type the first few letters "
                         "and choose where you're travelling from.",
          "fields": [{**A_LIST_QUESTION["fields"][0], "id": "origin", "label": "From"}]}


def test_a_two_line_station_question_fits_at_150_percent_at_level_1(
    short_page: Page, overlay: str, backend: Backend  # noqa: F811
) -> None:
    ask(short_page, overlay, backend, [
        ("task.started", {"goal": GOAL, "estimated_steps": 9}),
        ("load.updated", {"score": 0.2, "level": 1, "reason": "shown"}),
        ("state.changed", {"state": "waiting"}),
        ("step.presented", NARNIA),
        (AWAIT_RESPONSE, {}),
    ])
    short_page.fill("input[aria-label='From']", "lahor")
    short_page.wait_for_timeout(1500)

    over = short_page.evaluate("document.scrollingElement.scrollHeight - innerHeight")
    assert over <= 0, f"scrolls by {over}px"



# --- where you are, by name (2026-10-14) -------------------------------------------

TRIP = ["From", "To", "Day", "Search", "Trains"]


def staged(question: dict, stage: int) -> list:
    return [
        ("task.started", {"goal": GOAL, "estimated_steps": 9, "stages": TRIP}),
        ("state.changed", {"state": "waiting"}),
        ("step.presented", {**question, "stage": stage}),
        (AWAIT_RESPONSE, {}),
    ]


def stages_on(page: Page) -> list[tuple[str, str]]:
    return page.eval_on_selector_all(
        "[data-testid=stages] li",
        "items => items.map(i => [i.innerText.replace('✓', '').replace('·', '').trim(),"
        " i.dataset.state])")


def test_the_stages_show_where_the_person_is(
    page: Page, overlay: str, backend: Backend  # noqa: F811
) -> None:
    ask(page, overlay, backend, staged(A_QUESTION, 2))

    assert [tuple(s) for s in stages_on(page)] == [
        ("From", "done"), ("To", "done"), ("Day", "now"), ("Search", "to come"),
        ("Trains", "to come")]
    body = page.inner_text("body")
    assert "Step" not in body and " of 9" not in body



# --- what was wrong, cleared once it is put right (2026-10-14) ----------------------

NOTED = {**A_LIST_QUESTION, "instruction": "Where are you travelling to?",
         "note": "I couldn't find a station called Narnia."}


def test_the_note_goes_as_soon_as_a_name_from_the_list_is_chosen(
    page: Page, overlay: str, backend: Backend  # noqa: F811
) -> None:
    ask(page, overlay, backend, asked(NOTED))
    note = page.get_by_test_id("note")
    assert note.inner_text().strip() == "I couldn't find a station called Narnia."

    page.fill("input[aria-label='To']", "kar")
    page.wait_for_timeout(500)
    assert page.get_by_test_id("note").count() == 1, "typing is not choosing"

    page.locator(MATCHES, has_text="Karachi City").click()
    page.wait_for_timeout(900)
    assert page.get_by_test_id("note").count() == 0
    assert page.get_by_role("heading").first.inner_text().strip() == "Where are you travelling to?"


def test_a_typed_answers_note_stays_until_it_is_sent(
    page: Page, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """A day cannot be checked here; the backend says whether it was right."""
    typed = {**A_TYPED_QUESTION, "instruction": "Which day would you like to travel?",
             "fields": [{"id": "day", "label": "Day", "type": "text", "value": ""}],
             "note": "1 October has already passed."}
    ask(page, overlay, backend, asked(typed))

    page.fill("input[aria-label='Day']", "tomorrow")
    page.wait_for_timeout(600)

    assert page.get_by_test_id("note").inner_text().strip() == "1 October has already passed."
