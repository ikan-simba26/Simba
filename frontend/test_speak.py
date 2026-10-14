"""Read this aloud: the system's English voice, only when asked (2026-10-14).

A headless browser has no speech, so a stand-in `speechSynthesis` is put into
the page before it loads: it records every utterance — its words, its voice,
its language, its rate — and every cancel. What is checked is what the overlay
asks the system to say and when it asks it to stop.
"""

import json
from collections.abc import Iterator

import pytest
from playwright.sync_api import Page, Playwright

from frontend.test_terminal_states import AWAIT_RESPONSE, Backend, overlay  # noqa: F401

GOAL = "trains to Rawalpindi tomorrow"

ENGLISH = [{"name": "Microsoft Zira", "lang": "en-US", "default": False},
           {"name": "Microsoft Hazel", "lang": "en-GB", "default": True},
           {"name": "Microsoft Hortense", "lang": "fr-FR", "default": False}]
FRENCH_ONLY = [{"name": "Microsoft Hortense", "lang": "fr-FR", "default": True}]

FAKE = """(voices) => {
  window.__spoken = []; window.__cancelled = 0;
  window.SpeechSynthesisUtterance = class {
    constructor(text) { this.text = text; this.voice = null; this.lang = ''; this.rate = 1; }
  };
  Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: {
    getVoices: () => voices,
    addEventListener() {}, removeEventListener() {},
    speak(u) { window.__spoken.push({text: u.text, lang: u.lang,
                                     voice: u.voice && u.voice.name, rate: u.rate}); },
    cancel() { window.__cancelled += 1; },
  }});
}"""

DAY = {
    "step_index": 1, "step_total": 6, "instruction": "What day are you travelling?",
    "detail": "", "fields": [], "requires_confirmation": True, "findings": [],
    "step_kind": "date",
    "actions": [{"id": "choice:0", "label": "Today", "kind": "primary"},
                {"id": "choice:1", "label": "Tomorrow", "kind": "primary"},
                {"id": "choice:2", "label": "Pick another day", "kind": "primary"},
                {"id": "cancel", "label": "Stop this", "kind": "secondary"}],
}
NEXT = {
    "step_index": 2, "step_total": 6, "instruction": "Let me set where you're starting from.",
    "detail": "", "fields": [], "requires_confirmation": True, "findings": [],
    "actions": [{"id": "confirm", "label": "Set the departure station", "kind": "primary"},
                {"id": "cancel", "label": "Stop this", "kind": "secondary"}],
}
SCRIPT = [
    ("task.started", {"goal": GOAL, "estimated_steps": 6}),
    ("state.changed", {"state": "waiting"}),
    ("step.presented", DAY),
    (AWAIT_RESPONSE, {}),
    ("state.changed", {"state": "waiting"}),
    ("step.presented", NEXT),
    (AWAIT_RESPONSE, {}),
]


@pytest.fixture(scope="module")
def backend() -> Backend:
    return Backend()


@pytest.fixture(scope="module")
def browser(playwright_instance: Playwright):
    browser = playwright_instance.chromium.launch()
    yield browser
    browser.close()


def open_with(browser, voices, size=(1280, 800), scale=1.0) -> Page:
    page = browser.new_page(viewport={"width": size[0], "height": size[1]},
                            device_scale_factor=scale)
    page.add_init_script(f"({FAKE})({json.dumps(voices)})")
    return page


@pytest.fixture
def page(browser) -> Iterator[Page]:
    page = open_with(browser, ENGLISH)
    yield page
    page.close()


def to_the_step(page: Page, overlay: str, backend: Backend) -> None:  # noqa: F811
    backend.script = SCRIPT
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    page.fill("input[aria-label='What would you like me to do?']", GOAL)
    page.get_by_role("button", name="Start").click()
    page.wait_for_selector("[data-testid=step-shell]", timeout=15000)
    page.wait_for_timeout(800)


def spoken(page: Page) -> list[dict]:
    return page.evaluate("window.__spoken")


def test_nothing_is_read_unless_asked(page: Page, overlay: str, backend: Backend) -> None:  # noqa: F811
    to_the_step(page, overlay, backend)
    page.wait_for_timeout(1500)

    assert spoken(page) == []
    assert page.get_by_role("button", name="Read this aloud").is_visible()


def test_pressing_it_reads_the_step_and_its_answers_in_english(
    page: Page, overlay: str, backend: Backend  # noqa: F811
) -> None:
    to_the_step(page, overlay, backend)

    page.get_by_role("button", name="Read this aloud").click()

    assert spoken(page) == [{
        "text": "What day are you travelling? You can press Today, Tomorrow or Pick another day.",
        "lang": "en-GB", "voice": "Microsoft Hazel", "rate": 0.9,
    }]
    stop = page.get_by_role("button", name="Stop reading")
    assert stop.get_attribute("aria-pressed") == "true"


def test_pressing_it_again_stops_the_reading(page: Page, overlay: str,  # noqa: F811
                                            backend: Backend) -> None:
    to_the_step(page, overlay, backend)
    page.get_by_role("button", name="Read this aloud").click()
    before = page.evaluate("window.__cancelled")

    page.get_by_role("button", name="Stop reading").click()

    assert page.evaluate("window.__cancelled") > before
    assert page.get_by_role("button", name="Read this aloud").is_visible()


def test_the_reading_stops_when_the_step_changes(page: Page, overlay: str,  # noqa: F811
                                                backend: Backend) -> None:
    to_the_step(page, overlay, backend)
    page.get_by_role("button", name="Read this aloud").click()
    before = page.evaluate("window.__cancelled")

    page.get_by_role("button", name="Tomorrow", exact=True).click()
    page.wait_for_selector("text=Let me set where you're starting from.", timeout=15000)
    page.wait_for_timeout(600)

    assert page.evaluate("window.__cancelled") > before
    # The new step is not read by itself: still off until asked.
    assert len(spoken(page)) == 1
    assert page.get_by_role("button", name="Read this aloud").is_visible()


def test_without_an_english_voice_there_is_no_button(browser, overlay: str,  # noqa: F811
                                                    backend: Backend) -> None:
    page = open_with(browser, FRENCH_ONLY)
    try:
        to_the_step(page, overlay, backend)
        assert page.get_by_test_id("speak").count() == 0
    finally:
        page.close()


def test_there_is_nothing_to_read_on_the_home_screen(page: Page, overlay: str,  # noqa: F811
                                                    backend: Backend) -> None:
    backend.script = []
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    page.get_by_role("textbox", name="What would you like me to do?").wait_for()
    page.wait_for_timeout(600)
    assert page.get_by_test_id("speak").count() == 0


@pytest.mark.parametrize("size, scale", [((1280, 800), 1.0), ((1266, 606), 1.5)])
def test_it_sits_above_the_card_and_adds_no_height(browser, overlay: str,  # noqa: F811
                                                  backend: Backend, size, scale) -> None:
    page = open_with(browser, ENGLISH, size, scale)
    try:
        to_the_step(page, overlay, backend)
        page.wait_for_timeout(1200)
        speak = page.get_by_test_id("speak").bounding_box()
        card = page.locator("[data-testid=step-shell]").bounding_box()
        assert speak and card and speak["y"] >= 0
        # Above the card's own padding: it never covers the step.
        assert speak["y"] + speak["height"] <= card["y"], (speak, card)
        assert not page.evaluate("document.scrollingElement.scrollHeight > innerHeight")
    finally:
        page.close()
