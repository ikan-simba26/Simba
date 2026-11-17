"""The checklist: what SIMBA does by itself once the person has decided (2026-10-14).

Against a scripted backend that sends checklist lines — `step.presented` with
`requires_confirmation: false` — the way the real one does
(`backend/orchestrator/test_checklist.py` covers the backend's side).
"""

import json
from collections.abc import Iterator

import pytest
from playwright.sync_api import Page, Playwright

from frontend.test_terminal_states import AWAIT_RESPONSE, Backend, overlay  # noqa: F401

GOAL = "trains from Rawalpindi to Sukkur tomorrow"
TRIP = ["From", "To", "Day", "Search", "Trains"]


LINES = ["Filling in where you're starting from", "Filling in where you're going",
         "Opening the calendar", "Choosing 15 October", "Searching"]


def line(index: int, label: str) -> dict:
    """A checklist line, saying what is still to come after it (2026-10-15)."""
    return {"step_index": index, "step_total": 9, "instruction": label, "detail": "",
            "fields": [], "actions": [], "requires_confirmation": False, "findings": [],
            "stage": 3, "coming": LINES[LINES.index(label) + 1:]}


PAUSED = {"step_index": 4, "step_total": 9,
          "instruction": "I've paused. Carry on when you're ready.", "detail": "",
          "fields": [], "requires_confirmation": True, "findings": [], "stage": 3,
          "actions": [{"id": "confirm", "label": "Carry on", "kind": "primary"},
                      {"id": "cancel", "label": "Stop this", "kind": "secondary"}]}

RUNNING = [
    ("task.started", {"goal": GOAL, "estimated_steps": 6, "stages": TRIP}),
    ("state.changed", {"state": "acting"}),
    ("step.presented", line(1, "Filling in where you're starting from")),
    ("step.presented", line(2, "Filling in where you're going")),
    ("step.presented", line(3, "Opening the calendar")),
    # Held here: the next thing the backend waits for is the Pause.
    (AWAIT_RESPONSE, {}),
    ("state.changed", {"state": "waiting"}),
    ("step.presented", PAUSED),
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


@pytest.fixture
def page(browser) -> Iterator[Page]:
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()
    yield page
    context.close()


def begin(page: Page, overlay: str, backend: Backend, script=RUNNING) -> None:  # noqa: F811
    backend.script = script
    backend.responses.clear()
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    page.fill("input[aria-label='What would you like me to do?']", GOAL)
    page.get_by_role("button", name="Start").click()
    page.wait_for_selector("[data-testid=checklist]", timeout=15000)
    page.wait_for_timeout(900)


def lines(page: Page) -> list[tuple[str, str]]:
    return [tuple(x) for x in page.eval_on_selector_all(
        "[data-testid=checklist-lines] li",
        "items => items.map(i => [i.lastElementChild.innerText, i.dataset.state])")]


def test_the_lines_tick_off_and_the_last_is_being_done(page: Page, overlay: str,  # noqa: F811
                                                        backend: Backend) -> None:
    begin(page, overlay, backend)

    assert lines(page) == [("Filling in where you're starting from", "done"),
                           ("Filling in where you're going", "done"),
                           ("Opening the calendar", "now"),
                           # What is next, so nothing comes as a surprise.
                           ("Choosing 15 October", "to come"),
                           ("Searching", "to come")]
    # Softer, never fainter: the soft colour at full strength, as text that
    # is done is (`test_contrast.py`).
    colours = page.eval_on_selector_all(
        "[data-testid=checklist-lines] li",
        "items => items.map(i => [i.dataset.state, "
        "getComputedStyle(i.lastElementChild).color, getComputedStyle(i).opacity])")
    soft = {colour for state, colour, _ in colours if state == "done"}
    assert {colour for state, colour, _ in colours if state == "to come"} == soft
    assert {opacity for _, _, opacity in colours} == {"1"}
    assert page.get_by_text("I'm doing what you asked.").is_visible()
    # One thing to press, and it is Pause.
    buttons = page.eval_on_selector_all(
        "[data-testid=checklist] button", "bs => bs.map(b => b.innerText.trim())")
    assert buttons == ["Pause", "See the real page"]
    # With a pause sign: two upright bars, not the alert's circle (2026-10-15).
    icon = page.eval_on_selector("[data-testid=checklist] button [data-icon=pause] svg",
                                 "svg => [svg.querySelectorAll('circle').length, "
                                 "svg.querySelector('path').getAttribute('d')]")
    assert icon == [0, "M9 6v12M15 6v12"], icon


def test_pause_asks_the_backend_to_stop_before_its_next_move(page: Page, overlay: str,  # noqa: F811
                                                             backend: Backend) -> None:
    begin(page, overlay, backend)

    page.get_by_role("button", name="Pause").click()
    page.wait_for_selector("text=I've paused. Carry on when you're ready.", timeout=10000)

    pauses = [m["payload"] for m in backend.responses if m.get("type") == "step.response"]
    assert pauses[0] == {"step_index": 3, "action_id": "pause", "input_values": {}}
    assert page.get_by_role("button", name="Carry on").is_visible()


def test_no_telemetry_is_about_a_checklist_line(page: Page, overlay: str,  # noqa: F811
                                               backend: Backend) -> None:
    """There was no decision to measure."""
    begin(page, overlay, backend)
    page.wait_for_timeout(3500)  # past a timer sample, if one were sent

    samples = [m["payload"] for m in backend.responses if m.get("type") == "telemetry"]
    assert all(s["step_index"] not in (1, 2, 3) for s in samples), samples


def test_no_picture_is_asked_for_on_a_checklist_line_or_a_question(
    page: Page, overlay: str, backend: Backend  # noqa: F811
) -> None:
    """Each picture asked for was answered — a screenshot each — before the
    next question's answer was read, and in the real window that held
    "Register for CS-401" for 31s (2026-10-14). Since 2026-10-16 none is asked
    for at all unless the person asks: the page behind a step is gone."""
    begin(page, overlay, backend)
    page.get_by_role("button", name="Pause").click()
    page.wait_for_selector("text=I've paused. Carry on when you're ready.", timeout=10000)
    page.get_by_role("button", name="Carry on").click()
    page.wait_for_timeout(600)

    said = [m.get("type") for m in backend.responses]
    pause_at = said.index("step.response")
    assert "trust.requested" not in said[:pause_at], said
    assert "trust.requested" not in said[pause_at + 1:], said


def test_the_setting_to_be_asked_every_time_is_sent_and_kept(page: Page, overlay: str,  # noqa: F811
                                                            backend: Backend) -> None:
    backend.script = []
    page.goto(f"{overlay}?ws=ws://127.0.0.1:{backend.port}")
    box = page.get_by_role("checkbox", name="Ask me before each thing I do")
    assert not box.is_checked()

    box.check()
    page.reload()
    assert page.get_by_role("checkbox", name="Ask me before each thing I do").is_checked()


def test_the_setting_reaches_the_backend(browser, overlay: str) -> None:  # noqa: F811
    """Read off the socket as the task starts."""
    import asyncio
    import threading

    import websockets

    started: list[dict] = []
    ready = threading.Event()
    port_holder: list[int] = []

    def serve() -> None:
        async def handler(ws):
            await ws.send(json.dumps({"v": 1, "type": "history.offered", "task_id": "t",
                                      "seq": 1, "ts": 0, "payload": {"goals": []}}))
            started.append(json.loads(await ws.recv()))
            await asyncio.Future()

        async def main() -> None:
            server = await websockets.serve(handler, "127.0.0.1", 0)
            port_holder.append(server.sockets[0].getsockname()[1])
            ready.set()
            await asyncio.Future()

        asyncio.new_event_loop().run_until_complete(main())

    threading.Thread(target=serve, daemon=True).start()
    ready.wait(10)
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()
    try:
        page.goto(f"{overlay}?ws=ws://127.0.0.1:{port_holder[0]}")
        page.get_by_role("checkbox", name="Ask me before each thing I do").check()
        page.fill("input[aria-label='What would you like me to do?']", GOAL)
        page.get_by_role("button", name="Start").click()
        page.wait_for_timeout(1500)
        assert started and started[0]["payload"]["confirm_each"] is True
    finally:
        context.close()


def test_the_checklist_fits_at_150_percent(browser, overlay: str,  # noqa: F811
                                          backend: Backend) -> None:
    context = browser.new_context(viewport={"width": 1266, "height": 632},
                                  device_scale_factor=1.5)
    page = context.new_page()
    try:
        five = RUNNING[:2] + [("step.presented", line(i, label)) for i, label in enumerate(
            ["Filling in where you're starting from", "Filling in where you're going",
             "Opening the calendar", "Choosing 15 October", "Searching"], start=1)] + [
            (AWAIT_RESPONSE, {})]
        begin(page, overlay, backend, five)
        assert not page.evaluate("document.scrollingElement.scrollHeight > innerHeight")
        box = page.get_by_role("button", name="Pause").bounding_box()
        assert box and box["y"] + box["height"] <= 632
    finally:
        context.close()


# --- the journey line (2026-11-10) -----------------------------------------
#
# The same lines drawn as a path of dots: done ones filled, the one being
# done larger with "Doing this now" beside it, those to come empty. Still a
# list with the current step marked; at the simplest level only the move
# being done and how many are left; calm motion, and none when asked.

SIX = ["Filling in where you're starting from", "Filling in where you're going",
       "Opening the calendar", "Choosing 15 October", "Searching", "Reading the trains"]


def six_line(index: int) -> dict:
    return {"step_index": index, "step_total": 9, "instruction": SIX[index - 1], "detail": "",
            "fields": [], "actions": [], "requires_confirmation": False, "findings": [],
            "stage": 3, "coming": SIX[index:]}


#: Three done, the fourth being done, two to come.
FOURTH = RUNNING[:2] + [("step.presented", six_line(i)) for i in (1, 2, 3, 4)] + [
    (AWAIT_RESPONSE, {})]


def at_level(browser, level: int | None, size: str = "100%", reduced: bool = False,
             theme: str = "light"):
    from frontend.test_home import SIZES

    width, height, scale = SIZES[size]
    context = browser.new_context(viewport={"width": width, "height": height},
                                  device_scale_factor=scale, color_scheme=theme,
                                  reduced_motion="reduce" if reduced else "no-preference")
    if level is not None:
        context.add_init_script(
            "window.localStorage.setItem('simba.profile', JSON.stringify("
            f"{{welcomed: true, askEach: false, readAloud: false, level: {level}}}))")
    return context, context.new_page()


def test_the_journey_is_a_list_with_where_you_are_marked(page: Page, overlay: str,  # noqa: F811
                                                         backend: Backend) -> None:
    begin(page, overlay, backend, FOURTH)
    # Still an ordered list a screen reader reads as one, every move a line.
    assert page.get_by_role("list").filter(has_text=SIX[0]).count() == 1
    assert lines(page) == [(SIX[0], "done"), (SIX[1], "done"), (SIX[2], "done"),
                           (SIX[3], "now"), (SIX[4], "to come"), (SIX[5], "to come")]
    # One current step, and it is the move being done.
    current = page.locator("[data-testid=checklist-lines] li[aria-current=step]")
    assert current.count() == 1 and current.get_attribute("data-state") == "now"
    # Where you are, said in the words a screen reader always heard here, now
    # on screen too, and read before the move's words.
    here = page.get_by_test_id("journey-here")
    assert here.inner_text() == "Doing this now" and here.is_visible()
    assert current.inner_text().split("\n")[0] == "Doing this now"
    for state, words in (("done", "Done"), ("to come", "Still to do")):
        hidden = page.eval_on_selector_all(
            f"[data-testid=checklist-lines] li[data-state='{state}'] .sr-only",
            "els => els.map(e => e.innerText)")
        assert set(hidden) == {words}, (state, hidden)
    # Drawn in the task frame (2026-11-17): the move being done, large, with the lion
    # haloed above it, and what comes next said under it. The list above is kept for a
    # screen reader (`sr-only`); the dots and the path between them are not drawn.
    assert page.get_by_test_id("journey-doing").inner_text() == SIX[3]
    assert page.get_by_test_id("journey-doing").evaluate(
        "e => parseFloat(getComputedStyle(e).fontSize)") >= 30
    assert "simba-halo" in page.get_by_test_id("frame-lion").get_attribute("class")
    assert page.get_by_test_id("journey-next").inner_text() == f"Next: {SIX[4]} · {SIX[5]}"
    assert page.get_by_test_id("journey-path").count() == 0
    # Pause, and nothing else to press, as before.
    buttons = page.eval_on_selector_all(
        "[data-testid=checklist] button", "bs => bs.map(b => b.innerText.trim())")
    assert buttons == ["Pause", "See the real page"]


@pytest.mark.parametrize("level, shown", [(1, 6), (2, 6), (3, 1)])
def test_the_simplest_level_shows_only_where_you_are_and_how_many_are_left(
        browser, overlay: str, backend: Backend, level: int, shown: int) -> None:  # noqa: F811
    context, page = at_level(browser, level)
    try:
        begin(page, overlay, backend, FOURTH)
        assert page.get_by_test_id("checklist-lines").get_attribute("data-level") == str(level)
        listed = lines(page)
        assert len(listed) == shown, listed
        left = page.get_by_test_id("journey-left")
        if level == 3:
            # The move being done, and how many are left: never the others.
            assert listed == [(SIX[3], "now")]
            assert left.inner_text() == "Then 2 more things."
            assert page.locator("[data-testid=checklist-lines] li[aria-current=step]").count() == 1
            assert page.get_by_test_id("journey-path").count() == 0
        else:
            assert left.count() == 0
        # Never more than the checklist had: every word it had is a line here.
        assert {words for words, _ in listed} <= set(SIX)
        assert page.get_by_role("button", name="Pause").is_visible()
    finally:
        context.close()


def test_the_last_move_at_the_simplest_level_says_nothing_is_left(
        browser, overlay: str, backend: Backend) -> None:  # noqa: F811
    context, page = at_level(browser, 3)
    try:
        last = RUNNING[:2] + [("step.presented", six_line(i)) for i in range(1, 7)] + [
            (AWAIT_RESPONSE, {})]
        begin(page, overlay, backend, last)
        assert lines(page) == [(SIX[5], "now")]
        assert page.get_by_test_id("journey-left").count() == 0
    finally:
        context.close()


def test_one_more_thing_is_said_as_one(browser, overlay: str,  # noqa: F811
                                       backend: Backend) -> None:
    context, page = at_level(browser, 3)
    try:
        five = RUNNING[:2] + [("step.presented", six_line(i)) for i in range(1, 6)] + [
            (AWAIT_RESPONSE, {})]
        begin(page, overlay, backend, five)
        assert page.get_by_test_id("journey-left").inner_text() == "Then 1 more thing."
    finally:
        context.close()


@pytest.mark.parametrize("reduced", [False, True])
def test_the_lions_halo_breathes_and_not_under_reduced_motion(browser, overlay: str,  # noqa: F811
                                                              backend: Backend,
                                                              reduced: bool) -> None:
    """The halo round the lion is a soft shadow that breathes while SIMBA works
    (the task frame, 2026-11-17); asked for less motion, it is still."""
    context, page = at_level(browser, None, reduced=reduced)
    try:
        begin(page, overlay, backend, FOURTH)
        name = page.get_by_test_id("frame-lion").evaluate(
            "e => getComputedStyle(e, '::before').animationName")
        assert (name == "none") if reduced else (name == "simba-halo"), name
    finally:
        context.close()


@pytest.mark.parametrize("level", [1, 2, 3])
@pytest.mark.parametrize("size", ["100%", "125%", "150%", "150%, 632"])
def test_the_journey_fits_at_every_size_and_level(browser, overlay: str,  # noqa: F811
                                                  backend: Backend, size: str,
                                                  level: int) -> None:
    from frontend.test_home import SIZES

    context, page = at_level(browser, level, size)
    try:
        begin(page, overlay, backend, FOURTH)
        height = SIZES[size][1]
        assert not page.evaluate("document.scrollingElement.scrollHeight > innerHeight")
        box = page.get_by_role("button", name="Pause").bounding_box()
        assert box and box["y"] + box["height"] <= height
        # The move being done and "Doing this now" wholly in the middle panel.
        centre = page.get_by_test_id("frame-centre").bounding_box()
        for name in ("journey-doing", "journey-here"):
            box = page.get_by_test_id(name).bounding_box()
            assert box["y"] >= centre["y"] and box["y"] + box["height"] <= centre["y"] + centre["height"]
            assert box["x"] >= centre["x"] and box["x"] + box["width"] <= centre["x"] + centre["width"] + 1
    finally:
        context.close()
