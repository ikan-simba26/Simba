"""Getting to know the person, the first time SIMBA opens (2026-10-18).

Four questions, one at a time, each skippable: what to call them, which of
three ways of showing a question is comfortable, whether to show "Read this
aloud", and whether to ask before each thing. Kept on this computer as their
profile; the level goes with every task as `start_level`, and the name only
ever greets them. "Change my settings" opens it again.

The tests' own builds turn the welcome off (every other test expects the home
screen); these turn it back on with `window.__simbaWelcome`, the way the
press guard's tests turn on the guard.
"""

import json
from collections.abc import Iterator

import pytest
from playwright.sync_api import Page

from frontend.test_home import SIZES, History, browser, history  # noqa: F401 - fixtures
from frontend.test_terminal_states import A_STEP, AWAIT_RESPONSE, Backend, overlay  # noqa: F401

QUESTIONS = ["name", "level", "read", "ask"]


@pytest.fixture
def pages(browser) -> Iterator[list]:  # noqa: F811
    opened: list = []
    yield opened
    for page in opened:
        page.context.close()


def first_open(browser, overlay: str, port: int, pages: list,  # noqa: F811
               size: str = "100%") -> Page:
    """A brand-new person's first open: a fresh browser profile, the welcome on."""
    width, height, scale = SIZES[size]
    context = browser.new_context(viewport={"width": width, "height": height},
                                  device_scale_factor=scale)
    context.add_init_script("window.__simbaWelcome = true; window.__simbaSettleMs = 0")
    page = context.new_page()
    pages.append(page)
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{port}")
    page.get_by_test_id("welcome").wait_for(timeout=15000)
    return page


def question(page: Page) -> str:
    return page.get_by_test_id("welcome").get_attribute("data-question")


def saved(page: Page) -> dict:
    return json.loads(page.evaluate("() => localStorage.getItem('simba.profile') || '{}'"))


def test_every_question_can_be_skipped_and_it_is_not_shown_again(
    browser, overlay: str, history: History, pages: list  # noqa: F811
) -> None:
    page = first_open(browser, overlay, history.port, pages)

    asked = []
    for _ in QUESTIONS:
        asked.append(question(page))
        page.get_by_test_id("welcome-skip").click()
        page.wait_for_timeout(250)

    assert asked == QUESTIONS
    greeting = page.get_by_test_id("greeting").inner_text()
    assert greeting.endswith("Where do you want to go?") and "," not in greeting
    assert saved(page)["welcomed"] is True
    assert "level" not in saved(page) and "name" not in saved(page)

    # A second open is not a first open.
    page.reload()
    page.get_by_test_id("greeting").wait_for(timeout=15000)
    assert page.get_by_test_id("welcome").count() == 0


def test_the_answers_make_the_profile_and_the_level_goes_with_every_task(
    browser, overlay: str, history: History, pages: list  # noqa: F811
) -> None:
    page = first_open(browser, overlay, history.port, pages)

    page.get_by_role("textbox").fill("  Ayesha  ")
    page.get_by_role("button", name="Next").click()
    # The three examples are the same question at levels 1, 2 and 3.
    examples = page.get_by_test_id("welcome-level")
    examples.first.wait_for()
    assert [e.get_attribute("data-level") for e in examples.all()] == ["1", "2", "3"]
    assert all(e.locator("[data-testid=step-shell]").count() == 1 for e in examples.all())
    page.locator("[data-testid=welcome-level][data-level='3']").click()
    page.get_by_role("button", name="No, thank you").click()
    page.get_by_role("button", name="Just do it and show me").click()

    greeting = page.get_by_test_id("greeting")
    greeting.wait_for(timeout=5000)
    assert ", Ayesha. Where do you want to go?" in greeting.inner_text()
    assert saved(page) == {"name": "Ayesha", "level": 3, "readAloud": False,
                           "askEach": False, "welcomed": True}

    history.received.clear()
    page.get_by_test_id("tile").first.click()
    page.wait_for_timeout(800)
    start = next(m for m in history.received if m["type"] == "task.start")
    assert start["payload"]["start_level"] == 3
    # The name never leaves the overlay.
    assert "Ayesha" not in json.dumps(history.received)


def test_a_person_who_said_no_to_reading_aloud_has_no_button_for_it(
    browser, overlay: str, pages: list  # noqa: F811
) -> None:
    backend = Backend()
    backend.script = [("task.started", {"goal": "g", "estimated_steps": 3}),
                      ("state.changed", {"state": "waiting"}), ("step.presented", A_STEP),
                      (AWAIT_RESPONSE, {})]
    page = first_open(browser, overlay, backend.port, pages)
    for _ in range(2):
        page.get_by_test_id("welcome-skip").click()
        page.wait_for_timeout(250)
    page.get_by_role("button", name="No, thank you").click()
    page.get_by_test_id("welcome-skip").click()
    page.get_by_role("textbox", name="What would you like me to do?").fill("check my bill")
    page.get_by_role("button", name="Start", exact=True).click()
    page.get_by_test_id("step-shell").wait_for(timeout=15000)

    assert page.get_by_role("button", name="Read this aloud").count() == 0


def test_change_my_settings_opens_it_again_with_the_answers_marked(
    browser, overlay: str, history: History, pages: list  # noqa: F811
) -> None:
    page = first_open(browser, overlay, history.port, pages)
    page.get_by_role("textbox").fill("Sam")
    page.get_by_role("button", name="Next").click()
    page.locator("[data-testid=welcome-level][data-level='1']").click()
    page.get_by_role("button", name="Yes, show it").click()
    page.get_by_role("button", name="Ask me before each thing").click()
    page.get_by_test_id("greeting").wait_for()

    page.get_by_test_id("change-settings").click()
    page.get_by_test_id("welcome").wait_for()
    assert page.get_by_role("textbox").input_value() == "Sam"
    page.get_by_role("button", name="Next").click()
    chosen = page.locator("[data-testid=welcome-level][aria-pressed=true]")
    assert chosen.get_attribute("data-level") == "1"
    page.get_by_test_id("welcome-skip").click()
    assert page.get_by_role("button", name="Yes, show it").get_attribute("aria-pressed") == "true"
    page.get_by_test_id("welcome-skip").click()
    assert (page.get_by_role("button", name="Ask me before each thing")
            .get_attribute("aria-pressed") == "true")
    page.get_by_test_id("welcome-skip").click()
    # Nothing skipped was lost.
    assert saved(page)["name"] == "Sam" and saved(page)["level"] == 1
    assert saved(page)["askEach"] is True


DRAWN_INSIDE = """() => [...document.querySelectorAll('[data-testid=welcome-level]')]
  .map(card => {
    const c = card.getBoundingClientRect();
    const step = card.querySelector('[data-testid=step-shell]').getBoundingClientRect();
    const frame = card.querySelector('[data-testid=welcome-example]').getBoundingClientRect();
    return {level: card.dataset.level,
            frameInCard: frame.left >= c.left - 1 && frame.right <= c.right + 1
                         && frame.top >= c.top - 1 && frame.bottom <= c.bottom + 1,
            stepInFrame: step.left >= frame.left - 1 && step.right <= frame.right + 1
                         && step.bottom <= frame.bottom + 1,
            stepWidth: Math.round(step.width), cardWidth: Math.round(c.width),
            cutOff: [...card.querySelectorAll('[data-testid=welcome-example] button')]
              .filter(b => b.getBoundingClientRect().right > frame.right + 0.5)
              .map(b => b.innerText.trim())};
  })"""


@pytest.mark.parametrize("size", list(SIZES))
def test_each_example_is_drawn_small_inside_its_own_card(
    size: str, browser, overlay: str, history: History, pages: list  # noqa: F811
) -> None:
    """Seen in the real window on 2026-10-18: each example drawn larger than
    life across its neighbours, because its frame grew to the example's width.
    Nothing else here measured the examples themselves."""
    page = first_open(browser, overlay, history.port, pages, size)
    page.get_by_test_id("welcome-skip").click()
    page.get_by_test_id("welcome-level").first.wait_for()
    page.wait_for_timeout(600)

    drawn = page.evaluate(DRAWN_INSIDE)

    assert [d["level"] for d in drawn] == ["1", "2", "3"]
    for example in drawn:
        assert example["frameInCard"] and example["stepInFrame"], (size, drawn)
        # And no answer cut off at the frame's edge (laid out at 600, the
        # third one was).
        assert example["cutOff"] == [], (size, drawn)
        # Drawn smaller than the card, but not so small it cannot be read.
        assert 0.5 * example["cardWidth"] < example["stepWidth"] < example["cardWidth"], (
            size, drawn)


FITS = """() => {
  const scrolls = document.scrollingElement.scrollHeight > innerHeight;
  const off = [...document.querySelectorAll('[data-testid=welcome] button')]
    .filter(b => b.offsetParent && !b.closest('[aria-hidden=true]'))
    .filter(b => { const r = b.getBoundingClientRect();
                   return r.top < 0 || r.bottom > innerHeight || r.right > innerWidth; })
    .map(b => b.innerText.trim());
  return {scrolls, off};
}"""


@pytest.mark.parametrize("size", list(SIZES))
def test_every_question_fits_the_window(
    size: str, browser, overlay: str, history: History, pages: list  # noqa: F811
) -> None:
    page = first_open(browser, overlay, history.port, pages, size)
    measured = {}
    for name in QUESTIONS:
        page.wait_for_timeout(400)
        measured[name] = page.evaluate(FITS)
        page.get_by_test_id("welcome-skip").click()

    assert all(not m["scrolls"] and not m["off"] for m in measured.values()), (size, measured)
