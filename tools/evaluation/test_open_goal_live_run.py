"""The live-run script never presses "Do it" (2026-11-13).

`open_goal_live_run.py` plays the person by saying yes to every step. Since a
live site may now be changed after the final screen, it must say "Don't do it"
to that screen whatever the model wants. Tested on a page served from this
machine, with only the model scripted.
"""

import asyncio
import concurrent.futures
import functools
import http.server
import socketserver
import threading
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from backend.orchestrator import voice
from backend.orchestrator.llm import Action
from backend.orchestrator.llm_loop import OpenGoalPlanner
from backend.orchestrator.loop import Task, _Run, carry_out
from backend.orchestrator.plan import About
from tools.evaluation.open_goal_live_run import Recording

FORM = """<!doctype html><html><head><title>Admission form</title></head><body>
<h1>Admission form</h1>
<label for="name">Full name</label> <input id="name" name="name">
<button id="submit" onclick="document.title='SUBMITTED'">Submit application</button>
</body></html>"""


@pytest.fixture(scope="module")
def site(tmp_path_factory) -> str:
    folder: Path = tmp_path_factory.mktemp("form")
    (folder / "index.html").write_text(FORM, encoding="utf-8")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(folder))
    server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/index.html"
    server.shutdown()


def in_own_thread(go) -> None:
    """`asyncio.run(go())` on a thread of its own: in the whole suite a
    synchronous Playwright session from an earlier test still holds this
    thread's event loop, and `asyncio.run` refuses to start under it."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(lambda: asyncio.run(go())).result()


class Presses:
    """A model that fills the name and then presses Submit."""

    label = "Gemini"

    def __init__(self) -> None:
        self.calls = 0

    async def decide(self, system_prompt, page, goal, feedback=None, history=None):
        self.calls += 1
        number = next(line.split(".")[0] for line in page.splitlines()
                      if "Submit application" in line)
        return Action(action="click", element_id=int(number), value=None,
                      reasoning="Submit the form.")


class Answers:
    """A model that answers from the page at once."""

    label = "Gemini"

    async def decide(self, system_prompt, page, goal, feedback=None, history=None):
        return Action(action="answer", element_id=0, value="Admission form",
                      reasoning="The page says it.")


def test_an_answer_is_still_accepted_not_taken_for_a_final_screen(site):
    """"Is this what you wanted?" offers "No, keep looking" under the same id
    as "Don't do it"; the first version of this script declined it (run C)."""
    connection = Recording()

    async def go():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                task = Task(goal="What is this page?", estimated_steps=3,
                            success=None, about=About())
                run = _Run(page, connection, None, None)
                await run.open(task.goal, task.estimated_steps, site)
                await carry_out(run, OpenGoalPlanner(Answers(), task), task)
            finally:
                await browser.close()

    in_own_thread(go)
    kinds = [kind for kind, _ in connection.sent]
    assert connection.declined == []
    assert "task.completed" in kinds


def test_a_final_screen_is_answered_dont_and_nothing_is_pressed(site):
    connection = Recording()
    title: list[str] = []

    async def go():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                task = Task(goal="Fill in the admission form", estimated_steps=3,
                            success=None, about=About())
                run = _Run(page, connection, None, None)
                await run.open(task.goal, task.estimated_steps, site)
                await carry_out(run, OpenGoalPlanner(Presses(), task), task)
                title.append(await page.title())
            finally:
                await browser.close()

    in_own_thread(go)
    kinds = [kind for kind, _ in connection.sent]
    assert connection.declined and connection.declined[0].startswith("final screen")
    failed = [p for kind, p in connection.sent if kind == "task.failed"]
    assert failed and failed[-1]["reason"] == voice.NOTHING_CHANGED, kinds
    assert title == ["Admission form"]   # Submit was never pressed
    assert "task.completed" not in kinds
