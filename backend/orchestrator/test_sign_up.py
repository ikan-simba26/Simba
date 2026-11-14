"""Making an account with SIMBA (2026-11-14).

People with cognitive difficulties find making an account one of the hardest
things on the web: password rules, a second box for the same password, terms
to agree to, an email to open. Through the real loop, a real browser and a
sign-up page served from this machine, with only the model scripted:

  * a box asking for a new password offers "Make a strong password for me":
    SIMBA makes one, types it in both boxes, and keeps it in the vault — and
    it is never shown, sent to the overlay, or sent to a model;
  * a box to agree to the website's terms is the person's own choice, asked in
    plain words; "I don't agree" stops with nothing sent;
  * "Create account" is behind the final screen, like any change;
  * a page saying an email was sent tells the person what to do, and waits.
"""

import asyncio
import concurrent.futures
import functools
import http.server
import json
import re
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
from backend.orchestrator.test_verification import FakeConnection
from backend.orchestrator.vault import Vault

EMAIL = "test.person@example.com"

SIGN_UP = """<!doctype html><html><head><title>Join</title></head><body>
<h1>Create your account</h1>
<label for="email">Email</label> <input id="email" name="email" type="email">
<label for="pw">Create password</label> <input id="pw" name="pw" type="password">
<label for="pw2">Confirm password</label> <input id="pw2" name="pw2" type="password">
<input type="checkbox" id="terms" name="terms">
<label for="terms">I agree to the Terms and Conditions</label>
<button onclick="
  const pw = document.getElementById('pw').value;
  const ok = pw.length >= 12 && pw === document.getElementById('pw2').value
             && document.getElementById('terms').checked
             && document.getElementById('email').value;
  if (ok) { document.body.innerHTML =
    '<h2>Check your email</h2><p>We have sent a verification link to your email.</p>'; }
  else { document.getElementById('err').textContent = 'Please complete the form.'; }
">Create account</button>
<p id="err"></p>
</body></html>"""


@pytest.fixture(scope="module")
def site(tmp_path_factory) -> str:
    folder: Path = tmp_path_factory.mktemp("join")
    (folder / "index.html").write_text(SIGN_UP, encoding="utf-8")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(folder))
    server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/index.html"
    server.shutdown()


def element_id(page: str, words: str) -> int:
    return int(next(line.split(".")[0] for line in page.splitlines() if words in line))


class Joiner:
    """The model: fills the form in order, ticks the terms, creates the
    account, then answers with what the page says. Keeps every prompt."""

    label = "Gemini"

    def __init__(self) -> None:
        self.sent: list[str] = []
        self.done: list[str] = []

    async def decide(self, system_prompt, page, goal, feedback=None, history=None):
        self.sent.append("\n".join([page, feedback or "", *(history or [])]))
        if "verification link" in page:
            return Action(action="answer", element_id=0,
                          value="We have sent a verification link to your email.",
                          reasoning="The page says the account is made.")
        for kind, words in (("type", "Email"), ("type", "Create password"),
                            ("type", "Confirm password"), ("click", "I agree to the Terms"),
                            ("click", "Create account")):
            if words not in self.done:
                self.done.append(words)
                return Action(action=kind, element_id=element_id(page, words), value=None,
                              reasoning=f"{words}.")
        raise AssertionError("nothing left to do")


class Person(FakeConnection):
    """Types the email, asks SIMBA to make the password, and agrees — or not."""

    def __init__(self, agree: bool = True) -> None:
        super().__init__()
        self.agree = agree

    async def receive(self, message_type, step_index=None, on_other=None):
        response = await super().receive(message_type, step_index, on_other)
        step = next((p for kind, p in reversed(self.sent) if kind == "step.presented"), {})
        ids = [a["id"] for a in step.get("actions") or []]
        payload = response["payload"]
        payload["input_values"] = {}
        if voice.MAKE_PASSWORD_ID in ids:
            payload["action_id"] = voice.MAKE_PASSWORD_ID
        elif voice.DISAGREE_ID in ids:
            payload["action_id"] = voice.AGREE_ID if self.agree else voice.DISAGREE_ID
        else:
            payload["action_id"] = voice.CONFIRM_ID
            for field in step.get("fields") or []:
                if field["type"] in ("email", "text"):
                    payload["input_values"][field["id"]] = EMAIL
        return response


def run(url: str, provider, person: FakeConnection, vault: Vault) -> FakeConnection:
    task = Task(goal="Make me an account on this website", estimated_steps=8,
                success=None, about=About())

    async def go():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                run_ = _Run(page, person, None, None, vault=vault)
                await run_.open(task.goal, task.estimated_steps, url)
                await carry_out(run_, OpenGoalPlanner(provider, task), task)
            finally:
                await browser.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(lambda: asyncio.run(go())).result()
    return person


@pytest.fixture
def vault(tmp_path) -> Vault:
    store = Vault(tmp_path / "vault.json")
    if not store.available:
        pytest.skip("the vault needs Windows' DPAPI")
    return store


def test_an_account_is_made_with_a_password_simba_made_and_kept(site, vault):
    provider, person = Joiner(), Person()
    run(site, provider, person, vault)
    steps = person.of("step.presented")
    said = [s["instruction"] for s in steps]

    # The password step offered to make one, and said what it would do.
    offered = [s for s in steps if voice.MAKE_PASSWORD_ID in [a["id"] for a in s["actions"]]]
    assert len(offered) == 1, said
    assert offered[0]["detail"] == voice.NEW_PASSWORD_HELP
    # The terms were asked about, in plain words, once.
    assert said.count(voice.AGREE_TERMS) == 1, said
    # "Create account" was behind the final screen.
    assert len([s for s in steps if s.get("final")]) == 1, said
    # The email was explained, and the task ended with what the page says.
    assert voice.CHECK_EMAIL in said, said
    done = person.payload_of("task.completed")
    assert done["findings"][0]["value"] == "We have sent a verification link to your email."

    # Kept: for this site, with the email as the user name, and strong.
    saved = vault.get(site)
    assert saved is not None and saved.username == EMAIL
    password = saved.password
    assert len(password) >= 16
    assert re.search(r"[a-z]", password) and re.search(r"[A-Z]", password)
    assert re.search(r"[0-9]", password) and re.search(r"[^A-Za-z0-9]", password)
    # And never shown, never sent to the overlay, never sent to a model.
    assert password not in json.dumps(person.sent)
    assert not any(password in prompt for prompt in provider.sent)
    assert EMAIL not in "".join(provider.sent)


def test_not_agreeing_to_the_terms_stops_with_nothing_sent(site, vault):
    provider, person = Joiner(), Person(agree=False)
    run(site, provider, person, vault)
    failed = person.payload_of("task.failed")
    assert failed["reason"] == voice.DID_NOT_AGREE
    assert not [s for s in person.of("step.presented") if s.get("final")]
    assert "task.completed" not in person.types()
