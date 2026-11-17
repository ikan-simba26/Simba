"""The first-time setup's new questions (2026-11-13, the advisor's direction,
K): the AI helper and its key, and the websites to start with — after the
four of 2026-10-18, each skippable, asked only when the backend offers them.

The key goes to the backend once and is never shown again, kept in the page,
or put in the browser's storage; only its last four characters come back.
"""

import json

import pytest

from frontend.test_home import SIZES, browser  # noqa: F401 - fixture
from frontend.test_sites import Backend, offer, shipped_offer  # noqa: F401 - fixtures
from frontend.test_terminal_states import overlay  # noqa: F401 - the built overlay
from frontend.test_welcome import FITS, first_open, pages, question, saved  # noqa: F401

KEY = "AIzaTESTkey-not-a-real-one-9f3c"


class SetupBackend(Backend):
    """Answers `ai.setup` as the backend does, with the check's verdict."""

    def __init__(self, offer: dict, verdict: str = "ok") -> None:
        offer = json.loads(json.dumps(offer))
        offer["ai"] = {"configured": False, "check": "not_checked"}
        self.verdict = verdict
        super().__init__(offer)


@pytest.fixture
def setup_backend(offer):  # noqa: F811
    return SetupBackend(offer)


def skip_to(page, name: str) -> None:
    while question(page) != name:
        page.get_by_test_id("welcome-skip").click()
        page.wait_for_timeout(250)


def test_the_setup_asks_about_the_ai_and_the_websites_after_the_rest(
        browser, overlay, setup_backend, pages):  # noqa: F811
    page = first_open(browser, overlay, setup_backend.port, pages)
    asked = []
    for _ in range(6):
        asked.append(question(page))
        page.get_by_test_id("welcome-skip").click()
        page.wait_for_timeout(250)
    page.get_by_test_id("greeting").wait_for(timeout=5000)
    assert asked == ["name", "level", "read", "ask", "ai", "sites"]


def test_the_key_is_sent_once_and_never_kept_in_the_window(
        browser, overlay, setup_backend, pages):  # noqa: F811
    page = first_open(browser, overlay, setup_backend.port, pages)
    skip_to(page, "ai")
    page.get_by_test_id("ai-gemini").click()
    page.get_by_test_id("ai-key").fill(KEY)
    assert page.get_by_test_id("ai-key").get_attribute("type") == "password"
    page.get_by_test_id("ai-save").click()
    page.wait_for_timeout(500)
    assert setup_backend.sent("ai.setup")[-1] == {"provider": "gemini", "key": KEY}
    # Out of the box at once, and nowhere the window keeps things.
    assert page.get_by_test_id("ai-key").input_value() == ""
    assert KEY not in page.content()
    stored = page.evaluate("() => JSON.stringify(Object.assign({}, localStorage))")
    assert KEY not in stored


@pytest.mark.parametrize("verdict, words", [
    ("ok", "It works. This key is saved."),
    ("key", "That key didn't work. Check it was copied whole."),
    ("limit", "The key works, but today's free allowance is used up."),
])
def test_how_the_check_went_is_said_plainly(verdict, words, browser, overlay, offer, pages):  # noqa: F811
    backend = SetupBackend(offer, verdict)
    page = first_open(browser, overlay, backend.port, pages)
    skip_to(page, "ai")
    page.get_by_test_id("ai-key").fill(KEY)
    page.get_by_test_id("ai-save").click()
    check = page.get_by_test_id("ai-check")
    check.wait_for(timeout=5000)
    page.wait_for_function(
        "() => document.querySelector('[data-testid=ai-check]')?.dataset.check !== 'checking'",
        timeout=5000)
    assert check.inner_text().strip() == words


def test_another_provider_asks_for_its_address_and_model(
        browser, overlay, setup_backend, pages):  # noqa: F811
    page = first_open(browser, overlay, setup_backend.port, pages)
    skip_to(page, "ai")
    page.get_by_test_id("ai-openai").click()
    page.get_by_test_id("ai-key").fill(KEY)
    assert page.get_by_test_id("ai-save").is_disabled()
    page.get_by_test_id("ai-address").fill("https://llm.example.edu/v1")
    page.get_by_test_id("ai-model").fill("my-model")
    page.get_by_test_id("ai-save").click()
    page.wait_for_timeout(500)
    assert setup_backend.sent("ai.setup")[-1] == {
        "provider": "openai", "key": KEY, "base_url": "https://llm.example.edu/v1",
        "model": "my-model"}


def test_the_websites_chosen_go_first_in_the_list(browser, overlay, setup_backend, pages):  # noqa: F811
    page = first_open(browser, overlay, setup_backend.port, pages)
    skip_to(page, "sites")
    names = [b.inner_text() for b in page.get_by_test_id("setup-site").all()]
    assert "Electricity bill (practice copy)" not in names
    page.get_by_test_id("setup-site").filter(has_text="Wikipedia").click()
    page.get_by_test_id("setup-site").filter(has_text="Pakistan Railways").click()
    page.get_by_test_id("sites-done").click()
    page.get_by_test_id("site-grid").wait_for(timeout=5000)
    assert sorted(saved(page)["favourites"]) == ["pakrailways", "wikipedia"]
    # The first cards on the first screen are theirs (2026-11-17), and in the full list
    # they are a kind of their own, first.
    assert [s.get_attribute("aria-label") for s in page.get_by_test_id("site").all()][:2] == [
        "Pakistan Railways", "Wikipedia"]
    page.get_by_test_id("see-all").click()
    first = page.get_by_test_id("site-genre").first
    assert first.get_attribute("aria-label") == "Your websites"
    assert [s.get_attribute("aria-label") for s in first.get_by_test_id("site").all()] == [
        "Pakistan Railways", "Wikipedia"]


@pytest.mark.parametrize("size", list(SIZES))
def test_the_new_questions_fit_the_window(size, browser, overlay, setup_backend, pages):  # noqa: F811
    page = first_open(browser, overlay, setup_backend.port, pages, size)
    measured = {}
    for name in ("ai", "sites"):
        skip_to(page, name)
        if name == "ai":
            page.get_by_test_id("ai-openai").click()  # the tallest: three boxes
        page.wait_for_timeout(400)
        measured[name] = page.evaluate(FITS)
    assert all(not m["scrolls"] and not m["off"] for m in measured.values()), (size, measured)
