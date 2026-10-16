"""The overlay says whether a task has been started from it (2026-10-17).

The backend waits while the host's window is minimised, and says so after
(`backend/orchestrator/test_window.py`). That is right only when the person is
working in that window: a run driven from another overlay — the demo
recorder's — waited for minutes on 2026-10-16 because the host's window,
which nobody was looking at, was minimised. The overlay now writes
`window.__simbaStarted`, false when it loads and true once a task is started
from it, and the backend counts the window only when it is true.
"""

from frontend.test_closing import GOAL, backend, browser, completed  # noqa: F401 - fixtures
from frontend.test_terminal_states import Backend, overlay  # noqa: F401 - fixtures


def test_the_overlay_says_when_a_task_was_started_from_it(
    browser, overlay: str, backend: Backend  # noqa: F811
) -> None:
    backend.script = completed(None, [])
    backend.responses.clear()
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    box = page.get_by_role("textbox", name="What would you like me to do?")
    box.wait_for()

    assert page.evaluate("() => window.__simbaStarted") is False

    box.fill(GOAL)
    page.get_by_role("button", name="Start").click()
    page.get_by_role("button", name="Back to start").wait_for(timeout=15000)

    assert page.evaluate("() => window.__simbaStarted") is True
