"""Saved sign-in details: encrypted at rest, typed by the backend, never seen.

Three things are tested here, in order of how badly they could go wrong:

1. **A saved secret appears nowhere it could be read.** A whole task runs
   through the real loop, the real LLM planner and the real provider class —
   only its network call replaced — with a password saved for the site, trace
   memory on, the step recorder on and every log line captured. Then every
   prompt, every transcript line, the trace database, the recorder's file,
   every log record, every message to the overlay, and every file the run
   created or changed under `logs/` and `data/` is searched for it. And the
   page really did get it: the backend typed it.
2. **The vault encrypts.** Nothing readable is on disk, a tampered entry is
   refused rather than misread, and nothing prints its values.
3. **The person's part**: a password typed once into a protected field and
   kept, used without asking the next time, and forgotten on request.

The registration replica accepts any password, so "the wrong password is not
kept" is tested with a step rigged to fail rather than a rejected sign-in.
"""

import asyncio
import json
from dataclasses import replace
import logging
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from playwright.async_api import async_playwright

from backend.estimator.pairing import Recorder
from backend.orchestrator import loop, voice
from backend.orchestrator.llm import OpenAICompatibleProvider, Transcript
from backend.orchestrator.llm_loop import REGISTRATION_TASK, LLMPlanner
from backend.orchestrator.loop import Connection, Move, run_task, with_saved_details
from backend.orchestrator.plan import (
    REGISTRATION_PLAN,
    About,
    Expectation,
    HardcodedPlanner,
)
from backend.orchestrator.replay import TracePlanner
from backend.orchestrator.test_orchestrator import replica  # noqa: F401
from backend.orchestrator.traces import TraceStore
from backend.orchestrator.vault import Credentials, Vault, site_of
from backend.orchestrator.voice import actions
from backend.orchestrator.loop import Task
from shared.schema import StepField

REPO = Path(__file__).resolve().parents[2]
SECRET = "Pw-7f3a!only-in-the-vault"
USERNAME = "raham"

pytestmark = pytest.mark.skipif(not Vault(Path("unused")).available,
                                reason="the vault needs Windows (DPAPI)")


# --- a connection that answers like a person, and says what it was shown -----


class Person(Connection):
    """Answers each step: a typed username where it is asked, and the button
    named in `presses` (go-ahead otherwise). Sends one telemetry sample with
    every answer, the way the overlay does, so the recorder writes rows."""

    def __init__(self, presses: list[str] | None = None,
                 typed: dict[str, str] | None = None) -> None:
        self.sent: list[tuple[str, dict]] = []
        self.presses = list(presses or [])
        self.typed = typed or {}

    async def send(self, message_type: str, payload) -> None:
        self.sent.append((message_type, payload.model_dump()))

    async def receive(self, message_type: str, step_index: int | None = None,
                      on_other=None) -> dict:
        if on_other is not None:
            await on_other({"type": "telemetry", "payload": {
                "step_index": step_index, "answered": True, "hesitation_ms": 900,
                "path_ratio": 1.1, "backtracks": 0, "rereads": 0, "help_presses": 0}})
        step = [p for t, p in self.sent if t == "step.presented"][-1]
        values = {f["id"]: self.typed.get(f["id"], "") for f in step["fields"]}
        press = self.presses.pop(0) if self.presses else voice.CONFIRM_ID
        return {"type": "step.response", "payload": {
            "step_index": step_index, "action_id": press, "input_values": values}}

    def of(self, kind: str) -> list[dict]:
        return [p for t, p in self.sent if t == kind]


# --- the real provider class, with only its network call replaced -------------


class OfflineProvider(OpenAICompatibleProvider):
    """`OpenAICompatibleProvider`'s own `decide`, prompt and transcript, with
    the HTTP call answered here: it reads the page it was sent and picks the
    element whose label is next in the script, as a model would."""

    LINE = re.compile(r"^(\d+)\. (\S+) '(.*?)'")

    def __init__(self, script: list[tuple[str, str]], transcript: Transcript) -> None:
        super().__init__(api_key="offline", base_url="http://127.0.0.1:9/",
                         model="offline", transcript=transcript)
        self.script = list(script)
        self.prompts: list[str] = []

    async def _call(self, messages: list[dict], response_format: dict):
        prompt = "\n".join(m["content"] for m in messages)
        self.prompts.append(prompt)
        kind, label = self.script.pop(0)
        for line in messages[-1]["content"].splitlines():
            match = self.LINE.match(line)
            if match and match.group(3) == label:
                answer = {"action": kind, "element_id": int(match.group(1)),
                          "value": None, "reasoning": f"{kind} {label}"}
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(answer)))],
                    usage=SimpleNamespace(prompt_tokens=100, completion_tokens=10))
        raise AssertionError(f"{label!r} is not on the page the model was sent")


def files_under(*roots: Path) -> dict[Path, float]:
    """Every file under these, with when it was last written."""
    found = {}
    for root in roots:
        if root.is_file():
            found[root] = root.stat().st_mtime
        elif root.exists():
            found.update({p: p.stat().st_mtime for p in root.rglob("*") if p.is_file()})
    return found


# --- 1. a saved secret appears nowhere ----------------------------------------


def test_a_saved_password_is_in_no_prompt_log_trace_file_or_message(
    replica: str, tmp_path: Path, caplog  # noqa: F811
) -> None:
    vault = Vault(tmp_path / "vault.json")
    vault.put(replica, Credentials(USERNAME, SECRET))
    transcript = Transcript(tmp_path / "llm.jsonl")
    provider = OfflineProvider([
        ("type", "Student ID or Username"), ("type", "Password"), ("click", "Sign In"),
        ("click", "Close"), ("click", "Register for CS-401"),
    ], transcript)
    store = TraceStore(tmp_path / "traces.db")
    recorder = Recorder(path=tmp_path / "steps.jsonl", task_id="t_vault")
    person = Person(typed={"username": USERNAME})
    watched = (REPO / "logs", REPO / "data", REPO / "traces.db")
    before = files_under(*watched)

    typed: list[tuple[str, str]] = []
    original_act = loop.act

    async def watching(page, elements, element_id, operation, value, strategy):
        element = next(e for e in elements if e.id == element_id)
        typed.append((element.label, value))
        return await original_act(page, elements, element_id, operation, value, strategy)

    async def go() -> None:
        loop.act = watching
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch()
                page = await browser.new_page(viewport={"width": 1280, "height": 800})
                try:
                    planner = TracePlanner(store, REGISTRATION_TASK, site_of(replica),
                                           LLMPlanner(provider, REGISTRATION_TASK))
                    await run_task(page, person, planner, REGISTRATION_TASK, replica,
                                   recorder=recorder, vault=vault)
                finally:
                    await browser.close()
        finally:
            loop.act = original_act

    with caplog.at_level(logging.DEBUG):
        asyncio.run(go())

    # It worked, and the backend typed the saved password into the page itself.
    assert person.of("task.completed"), person.sent[-1]
    assert ("Password", SECRET) in typed
    # The password step showed no field for it, and said it would use the saved one.
    signing_in = [p for p in person.of("step.presented") if p["detail"] == voice.USING_SAVED]
    assert len(signing_in) == 1 and signing_in[0]["fields"] == []

    places = {
        "every prompt the model was sent": "\n".join(provider.prompts),
        "the transcript": (tmp_path / "llm.jsonl").read_text(encoding="utf-8"),
        "the trace database": (tmp_path / "traces.db").read_bytes().decode("latin-1"),
        "the step recorder": (tmp_path / "steps.jsonl").read_text(encoding="utf-8"),
        "every log record": caplog.text,
        "every message to the overlay": json.dumps(person.sent),
        "the vault file itself": (tmp_path / "vault.json").read_text(encoding="utf-8"),
    }
    assert len(provider.prompts) >= 5
    assert (tmp_path / "steps.jsonl").stat().st_size > 0
    for place, text in places.items():
        assert SECRET not in text, f"the saved password is in {place}"
    assert USERNAME not in places["the vault file itself"]

    # And nothing else the run wrote, anywhere under logs/ or data/.
    after = files_under(*watched)
    touched = [p for p, when in after.items() if p not in before or when > before[p]]
    for path in touched:
        assert SECRET not in path.read_bytes().decode("latin-1"), f"in {path}"


# --- 2. the vault encrypts ----------------------------------------------------


def test_nothing_readable_is_on_disk(tmp_path: Path) -> None:
    vault = Vault(tmp_path / "vault.json")
    vault.put("http://127.0.0.1:5000/login", Credentials(USERNAME, SECRET))

    on_disk = (tmp_path / "vault.json").read_bytes()

    assert SECRET.encode() not in on_disk and USERNAME.encode() not in on_disk
    assert vault.get("http://127.0.0.1:5000/courses") == Credentials(USERNAME, SECRET)


def test_an_entry_is_for_one_site(tmp_path: Path) -> None:
    vault = Vault(tmp_path / "vault.json")
    vault.put("http://127.0.0.1:5000/", Credentials(USERNAME, SECRET))

    assert vault.get("http://127.0.0.1:5100/") is None
    assert vault.get("https://127.0.0.1:5000/") is None
    assert vault.sites() == ["http://127.0.0.1:5000"]


def test_a_tampered_entry_is_refused_not_misread(tmp_path: Path) -> None:
    vault = Vault(tmp_path / "vault.json")
    vault.put("http://127.0.0.1:5000/", Credentials(USERNAME, SECRET))
    data = json.loads((tmp_path / "vault.json").read_text(encoding="utf-8"))
    data["sites"]["http://127.0.0.1:5000"] = "dGFtcGVyZWQ="  # "tampered"
    (tmp_path / "vault.json").write_text(json.dumps(data), encoding="utf-8")

    assert vault.get("http://127.0.0.1:5000/") is None


def test_saved_details_never_print(tmp_path: Path) -> None:
    saved = Credentials(USERNAME, SECRET)
    assert SECRET not in repr(saved) and SECRET not in str(saved)
    assert SECRET not in f"{saved}" and SECRET not in repr([saved])


def test_forgetting_deletes_the_entry(tmp_path: Path) -> None:
    vault = Vault(tmp_path / "vault.json")
    vault.put("http://127.0.0.1:5000/", Credentials(USERNAME, SECRET))

    assert vault.forget("http://127.0.0.1:5000/courses") is True
    assert vault.get("http://127.0.0.1:5000/") is None
    assert vault.forget("http://127.0.0.1:5000/") is False
    assert SECRET.encode() not in (tmp_path / "vault.json").read_bytes()



def test_a_reset_forgets_every_site(tmp_path: Path) -> None:
    """"Forget me and start again" (2026-10-21): the next person is never
    signed in as the last one, nor told "the details you saved"."""
    vault = Vault(tmp_path / "vault.json")
    vault.put("http://127.0.0.1:5000/", Credentials(USERNAME, SECRET))
    vault.put("http://127.0.0.1:5100/", Credentials(USERNAME, SECRET))

    vault.clear()
    assert vault.sites() == [] and not (tmp_path / "vault.json").exists()
    vault.clear()  # nothing saved: nothing to do

# --- 3. the person's part -----------------------------------------------------


def sign_in(replica: str, vault: Vault, person: Person, plan=None) -> Person:  # noqa: F811
    task = Task(goal="Sign in.", estimated_steps=1, about=About(),
                success=Expectation(url_contains="/courses"))

    async def go() -> None:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await run_task(page, person, HardcodedPlanner(plan or REGISTRATION_PLAN[:1]),
                               task, replica, vault=vault)
            finally:
                await browser.close()

    asyncio.run(go())
    return person


def test_a_password_is_asked_once_and_kept_when_the_person_says_so(
    replica: str, tmp_path: Path  # noqa: F811
) -> None:
    vault = Vault(tmp_path / "vault.json")

    first = sign_in(replica, vault, Person(presses=[voice.REMEMBER_ID],
                                           typed={"username": USERNAME, "password": SECRET}))

    step = first.of("step.presented")[0]
    assert [f["type"] for f in step["fields"]] == ["text", "password"]
    assert all(f["value"] == "" for f in step["fields"])  # nothing pre-filled, ever
    assert [a["id"] for a in step["actions"]] == [voice.CONFIRM_ID, voice.REMEMBER_ID,
                                                 voice.CANCEL_ID]
    assert [a["label"] for a in step["actions"]][1] == "Sign in and save my password"
    assert first.of("task.completed")
    assert vault.get(replica) == Credentials(USERNAME, SECRET)


def test_not_asking_to_keep_it_keeps_nothing(replica: str, tmp_path: Path) -> None:  # noqa: F811
    vault = Vault(tmp_path / "vault.json")

    sign_in(replica, vault, Person(typed={"username": USERNAME, "password": SECRET}))

    assert vault.get(replica) is None


def test_the_next_time_it_is_typed_without_asking(replica: str, tmp_path: Path) -> None:  # noqa: F811
    vault = Vault(tmp_path / "vault.json")
    vault.put(replica, Credentials(USERNAME, SECRET))

    second = sign_in(replica, vault, Person())

    step = second.of("step.presented")[0]
    assert step["fields"] == []
    assert step["detail"] == voice.USING_SAVED
    assert [a["id"] for a in step["actions"]] == [voice.CONFIRM_ID, voice.FORGET_ID,
                                                 voice.CANCEL_ID]
    assert second.of("task.completed")
    assert SECRET not in json.dumps(second.sent)


def test_forgetting_deletes_it_and_asks_again(replica: str, tmp_path: Path) -> None:  # noqa: F811
    vault = Vault(tmp_path / "vault.json")
    vault.put(replica, Credentials(USERNAME, SECRET))

    run = sign_in(replica, vault, Person(presses=[voice.FORGET_ID, voice.CONFIRM_ID],
                                         typed={"username": USERNAME, "password": "typed"}))

    shown = run.of("step.presented")
    assert [s["detail"] for s in shown] == [voice.USING_SAVED, voice.FORGOTTEN]
    assert [f["type"] for f in shown[1]["fields"]] == ["text", "password"]
    assert vault.get(replica) is None
    assert run.of("task.completed")
    # One step, shown twice: forgetting is not a step taken.
    assert run.of("task.completed")[0]["steps_taken"] == 1


def test_a_password_that_did_not_sign_in_is_not_kept(replica: str, tmp_path: Path) -> None:  # noqa: F811
    """Kept only once the step has worked. Rigged: the step expects a page the
    sign-in never reaches, so it fails, and nothing is saved."""
    vault = Vault(tmp_path / "vault.json")
    never = replace(REGISTRATION_PLAN[0], expect=Expectation(url_contains="/never-reached"))

    sign_in(replica, vault, Person(presses=[voice.REMEMBER_ID, voice.CANCEL_ID],
                                   typed={"username": USERNAME, "password": SECRET}),
            plan=[never])

    assert vault.get(replica) is None


def test_a_step_that_asks_for_no_password_is_unchanged() -> None:
    move = Move(instruction="Choose a day.", detail="", operations=[],
                expect=Expectation(), fields=[StepField(id="d", label="Day", type="text",
                                                        value="")],
                actions=actions("Set the date"))

    assert with_saved_details(move, Credentials(USERNAME, SECRET), True) is move
    assert with_saved_details(move, None, True) is move


def test_with_no_vault_the_step_asks_as_it_always_did(replica: str) -> None:  # noqa: F811
    person = Person(typed={"username": USERNAME, "password": SECRET})

    async def go() -> None:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await run_task(page, person, HardcodedPlanner(REGISTRATION_PLAN[:1]),
                               Task(goal="Sign in.", estimated_steps=1, about=About(),
                                    success=Expectation(url_contains="/courses")), replica)
            finally:
                await browser.close()

    asyncio.run(go())

    step = person.of("step.presented")[0]
    assert [a["id"] for a in step["actions"]] == [voice.CONFIRM_ID, voice.CANCEL_ID]
