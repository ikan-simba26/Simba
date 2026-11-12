"""A goal with no plan, done by the AI planner (2026-11-13, the advisor's
direction): through the real loop, a real browser and a page served from this
machine, with only the model scripted.

What has to hold: the model's answer is shown only if the page says it word
for word; it is the answer only when the person says so; "No, keep looking"
goes back to the model; when the model cannot do it, the stuck screen offers a
helper's "Show me once" on that website; and the person is told which
provider worked each move out.
"""

import asyncio
import functools
import http.server
import socketserver
import threading
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from backend.orchestrator import voice
from backend.orchestrator.llm import Action
from backend.orchestrator.llm_loop import OpenGoalPlanner, render_content
from backend.orchestrator.loop import Task, _Run, carry_out
from backend.orchestrator.plan import About
from backend.orchestrator.test_verification import FakeConnection

PAGE = """<!doctype html><html><head><title>Bank holidays</title></head><body>
<h1>UK bank holidays</h1>
<label for="year">Year</label> <input id="year" name="year">
<button id="show" onclick="document.getElementById('more').hidden=false">Show more</button>
<table><thead><tr><th>Date</th><th>Holiday</th></tr></thead><tbody>
<tr><td>25 December</td><td>Christmas Day</td></tr>
<tr><td>26 December</td><td>Boxing Day</td></tr>
</tbody></table>
<p id="more" hidden>More holidays are listed for next year.</p>
</body></html>"""


@pytest.fixture(scope="module")
def site(tmp_path_factory) -> str:
    folder: Path = tmp_path_factory.mktemp("holidays")
    (folder / "index.html").write_text(PAGE, encoding="utf-8")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(folder))
    server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/index.html"
    server.shutdown()


class Scripted:
    """The model: answers from a script, records what it was shown."""

    def __init__(self, script: list[Action], label: str = "Gemini") -> None:
        self.script = list(script)
        self.label = label
        self.pages: list[str] = []
        self.systems: list[str] = []
        self.feedback: list[str | None] = []

    async def decide(self, system_prompt, page, goal, feedback=None, history=None):
        self.systems.append(system_prompt)
        self.pages.append(page)
        self.feedback.append(feedback)
        return self.script.pop(0)


class Answering(FakeConnection):
    """Answers each step with the next id in `answers`, then confirms."""

    def __init__(self, answers: list[str]) -> None:
        super().__init__()
        self.answers = list(answers)

    async def receive(self, message_type, step_index=None, on_other=None):
        response = await super().receive(message_type, step_index, on_other)
        if self.answers:
            response["payload"]["action_id"] = self.answers.pop(0)
        return response


def answer(text: str) -> Action:
    return Action(action="answer", element_id=0, value=text, reasoning="The page lists it.")


def run(site: str, provider: Scripted, connection: FakeConnection | None = None):
    connection = connection or FakeConnection()
    task = Task(goal="When is Boxing Day?", estimated_steps=3, success=None, about=About())

    async def go():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                run = _Run(page, connection, None, None)
                run.teach_site = site
                await run.open(task.goal, task.estimated_steps, site)
                await carry_out(run, OpenGoalPlanner(provider, task), task)
            finally:
                await browser.close()
    asyncio.run(go())
    return connection


def test_an_answer_the_page_says_is_asked_about_then_shown(site):
    provider = Scripted([answer("26 December")])
    connection = run(site, provider)
    question = connection.of("step.presented")[0]
    assert question["instruction"] == "The page says: 26 December. Is this what you wanted?"
    assert question["worked_out_by"] == "Gemini"
    done = connection.payload_of("task.completed")
    assert done["findings"] == [{"label": voice.WHAT_I_FOUND, "value": "26 December",
                                 "values": [], "rows": []}] or \
        done["findings"][0]["value"] == "26 December"
    # The model saw what the page says, not only what can be pressed.
    assert "What the page says:" in provider.pages[0]
    assert "26 December | Boxing Day" in provider.pages[0]


def test_an_answer_the_page_does_not_say_is_never_shown(site):
    provider = Scripted([answer("27 December"), answer("26 December")])
    connection = run(site, provider)
    # The first was sent back with why, and never reached the person.
    assert "is not on the page word for word" in (provider.feedback[1] or "")
    shown = " ".join(p["instruction"] for p in connection.of("step.presented"))
    assert "27 December" not in shown
    assert connection.payload_of("task.completed")["findings"][0]["value"] == "26 December"


def test_twice_not_on_the_page_is_stuck_and_offers_a_helper(site):
    provider = Scripted([answer("27 December"), answer("Boxing Day is the 26th")])
    connection = run(site, provider)
    assert "task.completed" not in connection.types()
    help_ = connection.payload_of("help.requested")
    assert help_["reason"] == voice.AI_COULD_NOT
    assert help_["suggestion"] == voice.AI_THEN_TEACH
    assert help_["teach_site"] == site


def test_no_keep_looking_goes_back_to_the_model(site):
    provider = Scripted([answer("25 December"), answer("26 December")])
    connection = run(site, provider, Answering([voice.DECLINE_ID, voice.CONFIRM_ID]))
    assert 'said "25 December" is not what they wanted' in (provider.feedback[1] or "")
    assert connection.payload_of("task.completed")["findings"][0]["value"] == "26 December"


def test_a_move_before_the_answer_is_worked_out_by_the_provider_named(site):
    provider = Scripted([
        Action(action="click", element_id=0, value=None, reasoning="placeholder"),
    ])
    # The id is filled in from the page once it has been read: the button.
    connection = FakeConnection()

    class FindsButton(Scripted):
        async def decide(self, system_prompt, page, goal, feedback=None, history=None):
            self.pages.append(page)
            self.feedback.append(feedback)
            if len(self.pages) == 1:
                line = next(l for l in page.splitlines() if "'Show more'" in l)
                return Action(action="click", element_id=int(line.split(".")[0]),
                              value=None, reasoning="Show the rest.")
            return answer("26 December")

    finder = FindsButton([], label="Groq")
    run(site, finder, connection)
    first = connection.of("step.presented")[0]
    assert first["worked_out_by"] == "Groq"
    assert connection.payload_of("task.completed")["findings"][0]["value"] == "26 December"


def test_what_the_page_says_is_cut_to_fit_a_free_tier():
    from backend.perception.content import Content, Heading

    long = Content(headings=[Heading(level=2, text="x" * 200) for _ in range(40)])
    rendered = render_content(long)
    assert len(rendered) <= 2400 + len("\n(... the rest is cut)")
    assert rendered.endswith("(... the rest is cut)")
    assert render_content(None) == "(the page says nothing readable)"
