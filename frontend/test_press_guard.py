"""A press on a button that has only just arrived is ignored (2026-10-16).

The first real-window walk of 2026-10-16 twice ended "I've stopped, as you
asked." with nobody having pressed stop. Logging every press found it: while
a step faded out beside the next, the fading copy showed the new question
with its old box still folding away, so its buttons stood lower than the
arriving copy's; a press aimed at "Tomorrow" on the fading copy landed on the
arriving screen's "Stop this", 89ms after that button appeared.

Two fixes, both checked here in a real browser: a screen on its way out shows
its own step and takes no presses; and the overlay ignores a press on a
button that moved or appeared in the last 500ms, or where a different button
was in the last 500ms. Every press is logged (`window.__simbaPresses`).
"""

from collections.abc import Iterator

import pytest
from playwright.sync_api import Page

from frontend.test_terminal_states import AWAIT_RESPONSE, Backend, overlay  # noqa: F401

GOAL = "trains to Karachi tomorrow"
STEP = {"step_index": 1, "step_total": 3, "instruction": "What day are you travelling?",
        "detail": "", "fields": [], "requires_confirmation": True, "findings": [],
        "actions": [{"id": "choice:0", "label": "Today", "kind": "primary"},
                    {"id": "choice:1", "label": "Tomorrow", "kind": "primary"},
                    {"id": "cancel", "label": "Stop this", "kind": "secondary"}]}
NEXT = {**STEP, "step_index": 2, "instruction": "Lahore Cantt to Karachi Cantt. Is that right?",
        "actions": [{"id": "choice:0", "label": "Yes, that's right", "kind": "primary"},
                    {"id": "cancel", "label": "Stop this", "kind": "secondary"}]}


@pytest.fixture(scope="module")
def backend() -> Backend:
    return Backend()


@pytest.fixture
def page(playwright_instance) -> Iterator[Page]:
    browser = playwright_instance.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    # The test builds have the guard off; this turns it on, at the real 500ms.
    page.add_init_script("window.__simbaSettleMs = 500")
    yield page
    browser.close()


def start(page: Page, overlay: str, backend: Backend, script) -> None:  # noqa: F811
    backend.script = [("task.started", {"goal": GOAL, "estimated_steps": 3}),
                      ("state.changed", {"state": "waiting"}), *script]
    backend.responses.clear()
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    page.wait_for_timeout(700)
    page.fill("input[aria-label='What would you like me to do?']", GOAL)
    page.get_by_role("button", name="Start", exact=True).click()


def answers(backend: Backend) -> list[str]:
    return [m["payload"]["action_id"] for m in backend.responses
            if m.get("type") == "step.response"]


def test_a_press_on_a_button_just_arrived_is_ignored_and_logged(
    page: Page, overlay: str, backend: Backend  # noqa: F811
) -> None:
    start(page, overlay, backend, [("step.presented", STEP), (AWAIT_RESPONSE, {})])
    page.get_by_role("button", name="Tomorrow").wait_for()
    page.get_by_role("button", name="Tomorrow").click()  # as soon as it is there
    page.wait_for_timeout(300)
    assert answers(backend) == []

    page.wait_for_timeout(1500)  # long settled, even with animations slowed by load
    page.get_by_role("button", name="Tomorrow").click()
    page.wait_for_timeout(500)
    assert answers(backend) == ["choice:1"]

    log = page.evaluate("window.__simbaPresses")
    tomorrow = [p for p in log if p["label"] == "Tomorrow"]
    assert [p["ignored"] for p in tomorrow] == [True, False], tomorrow
    assert tomorrow[0]["sinceButtonMs"] < 500 <= tomorrow[1]["sinceButtonMs"]
    assert all(p["level"] in (1, 2, 3) for p in tomorrow)
    assert all("sinceLayoutMs" in p for p in tomorrow)


def test_a_screen_on_its_way_out_takes_no_presses_and_keeps_its_own_step(
    page: Page, overlay: str, backend: Backend  # noqa: F811
) -> None:
    start(page, overlay, backend, [("step.presented", STEP), (AWAIT_RESPONSE, {}),
                                   ("step.presented", NEXT), (AWAIT_RESPONSE, {})])
    page.get_by_role("button", name="Tomorrow").wait_for()
    page.wait_for_timeout(2000)  # settled, and the home screen's tiles long gone
    page.get_by_role("button", name="Tomorrow").click()
    leaving = page.locator("[data-leaving=true]")
    leaving.wait_for(state="attached", timeout=5000)
    assert leaving.evaluate("e => getComputedStyle(e).pointerEvents") == "none"
    # Its own question, not the arriving one.
    assert "What day are you travelling?" in leaving.inner_text()
    assert "Is that right?" not in leaving.inner_text()


def test_a_press_where_another_button_just_was_is_ignored(
    page: Page, overlay: str  # noqa: F811
) -> None:
    """"Stop this" never takes a press meant for a button that was over that
    spot a moment ago, even when "Stop this" itself has not moved."""
    page.goto(overlay)
    page.wait_for_timeout(700)
    page.evaluate("""() => {
        window.__pressed = [];
        const make = (name, top) => {
            const b = document.createElement('button');
            b.textContent = name;
            Object.assign(b.style, {position: 'fixed', left: '100px', top: top + 'px',
                                    width: '200px', height: '60px', zIndex: 50});
            b.onclick = () => window.__pressed.push(name);
            document.body.appendChild(b);
            return b;
        };
        window.__stop = make('Stop this', 400);
        window.__other = make('Tomorrow', 400);   // on top of it, at first
    }""")
    page.wait_for_timeout(900)  # both settled where they are
    page.evaluate("() => { window.__other.style.top = '100px'; }")  # moves away
    page.wait_for_timeout(150)
    page.mouse.click(200, 430)  # where "Tomorrow" was a moment ago
    page.wait_for_timeout(200)
    assert page.evaluate("window.__pressed") == []
    log = page.evaluate("window.__simbaPresses")
    assert log[-1]["label"] == "Stop this" and log[-1]["ignored"] is True
    assert log[-1]["wasUnder"] == "Tomorrow"

    page.wait_for_timeout(700)
    page.mouse.click(200, 430)
    page.wait_for_timeout(200)
    assert page.evaluate("window.__pressed") == ["Stop this"]
