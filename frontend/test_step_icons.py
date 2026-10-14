"""One plain shape beside each step, for what it is about (2026-10-07)."""

from collections.abc import Iterator

import pytest
from playwright.sync_api import Page, Playwright

from frontend.test_terminal_states import AWAIT_RESPONSE, Backend, overlay  # noqa: F401

GOAL = "trains to Rawalpindi tomorrow"
LONG = ("There is no 31 February in the calendar. Which day would you like to travel? "
        "You can type it like 3 October.")


def a_step(kind: str | None, instruction: str = "Let me find the right month.") -> dict:
    step = {
        "step_index": 1, "step_total": 6, "instruction": instruction,
        "detail": "Travelling on 8 October.", "fields": [], "requires_confirmation": True,
        "findings": [],
        "actions": [{"id": "confirm", "label": "Open the calendar", "kind": "primary"},
                    {"id": "cancel", "label": "Stop this", "kind": "secondary"}],
    }
    if kind:
        step["step_kind"] = kind
    return step


def script(step: dict, level: int | None = None) -> list:
    out = [("task.started", {"goal": GOAL, "estimated_steps": 6})]
    if level:
        out.append(("load.updated", {"score": 0.5, "level": level, "reason": "pause"}))
    return out + [("state.changed", {"state": "waiting"}), ("step.presented", step),
                  (AWAIT_RESPONSE, {})]


@pytest.fixture(scope="module")
def backend() -> Backend:
    return Backend()


@pytest.fixture(scope="module")
def browser(playwright_instance: Playwright):
    browser = playwright_instance.chromium.launch()
    yield browser
    browser.close()


@pytest.fixture
def page(browser) -> Iterator[Page]:
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    yield page
    page.close()


def show(page: Page, overlay: str, backend: Backend, steps) -> None:  # noqa: F811
    backend.script = steps
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    page.fill("input[aria-label='What would you like me to do?']", GOAL)
    page.get_by_role("button", name="Start").click()
    page.wait_for_selector("[data-testid=step-shell]", timeout=15000)
    page.wait_for_timeout(900)


@pytest.mark.parametrize("kind", ["date", "place", "choose", "type", "read", "confirm"])
def test_each_kind_has_its_shape(page: Page, overlay: str, backend: Backend,  # noqa: F811
                                 kind: str) -> None:
    show(page, overlay, backend, script(a_step(kind)))

    icon = page.get_by_test_id("step-kind")
    assert icon.get_attribute("data-kind") == kind
    assert icon.locator("svg").count() == 1
    # Decoration: the sentence says it, and a screen reader hears it once.
    assert icon.get_attribute("aria-hidden") == "true"


def test_the_six_shapes_are_six_different_shapes(page: Page, overlay: str,  # noqa: F811
                                                 backend: Backend) -> None:
    drawn = set()
    for kind in ("date", "place", "choose", "type", "read", "confirm"):
        show(page, overlay, backend, script(a_step(kind)))
        drawn.add(page.get_by_test_id("step-kind").inner_html())
    assert len(drawn) == 6


def test_a_step_that_does_not_say_has_no_shape(page: Page, overlay: str,  # noqa: F811
                                               backend: Backend) -> None:
    show(page, overlay, backend, script(a_step(None)))
    assert page.get_by_test_id("step-kind").count() == 0


@pytest.mark.parametrize("level", [1, 2, 3])
def test_a_long_sentence_with_its_shape_fits_at_150_percent(
    browser, overlay: str, backend: Backend, level: int  # noqa: F811
) -> None:
    page = browser.new_page(viewport={"width": 1266, "height": 606}, device_scale_factor=1.5)
    try:
        show(page, overlay, backend, script(a_step("date", LONG), level))
        page.wait_for_timeout(1200)  # the overflow guard, if it moves, has moved
        for name in ("Open the calendar", "Stop this"):
            box = page.get_by_role("button", name=name, exact=True).bounding_box()
            assert box and box["y"] + box["height"] <= 606, (level, name, box)
        assert not page.evaluate("document.scrollingElement.scrollHeight > innerHeight")
    finally:
        page.close()
