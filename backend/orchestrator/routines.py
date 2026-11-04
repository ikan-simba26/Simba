"""Routines a helper showed SIMBA once (2026-11-04, "Show me once").

A helper — a carer, a family member, a teacher — does a task once on the real
site while SIMBA watches (`teach.py`). What they did is kept here as a
routine: each press and each typed value by perception's role and label at
that moment, never an element id and never a selector (CLAUDE.md), and the
thing the task is for, which the helper pointed at on the page. The person
then runs it from a tile on the home screen: SIMBA asks only the values the
helper said change, runs the rest as the checklist, checks every move, and
shows the answer with the picture of the real page. No model is asked.

**Kept like the person's own tiles** (`tiles.py`): encrypted with this Windows
account's own key, in `data/routines.json`, never committed. The whole list is
one blob, names and all. A routine and a tile share the home screen's one row
of three (`tiles.MAX_TILES`).

**Never a password.** The recorder never reads one off the page; a typed
password is kept as "a password goes here" and nothing else, and at run time
it is the vault's or the person's (`teach.py`, `RoutinePlanner`).

**A file to share** (`export`, `parse`): a helper can save a routine and load
it on another SIMBA. Every value the helper typed becomes one the person is
asked for, since a shared routine is for someone else, whose reference number
is not the helper's.
"""

from __future__ import annotations

import json
import os
import re
import secrets
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from urllib.parse import urlsplit

from backend.orchestrator.tiles import LABEL_MAX, MAX_TILES, clean_label
from backend.orchestrator.vault import REPO, Vault, VaultUnavailable, decrypt, encrypt

DEFAULT_PATH = REPO / "data" / "routines.json"
#: The file format's own name and version, so a file can be told apart from
#: any other JSON (`parse`).
FORMAT = "simba-routine"
VERSION = 1
#: The most moves a routine keeps. A task longer than this is not one a
#: helper can show in one go, and a file claiming more is not believed.
MOST_STEPS = 30
#: The longest role, label or value a routine keeps, in characters.
TEXT_MAX = 200
KINDS = ("fill", "click", "press", "select")


@dataclass(frozen=True)
class Step:
    """One thing the helper did, in perception's terms.

    `role` and `label` are what perception called the element at that moment;
    `nth` says which, when the page had several with the same role and label
    (the live train search has three unnamed links). Replay finds it again by
    these, on the page as it is then.
    """

    kind: str  # fill | click | press | select
    role: str
    label: str
    nth: int = 0
    #: Perception's few extra words, when it gave some: a calendar day that
    #: belongs to the previous month is "previous month".
    qualifier: str | None = None
    #: What was typed, chosen or pressed, when it is the same every time.
    value: str | None = None
    #: Asked of the person each time, as a question before the site is touched.
    ask: bool = False
    #: A password box. Nothing typed into it is ever kept: at run time the
    #: saved one is used, or the person types it.
    secret: bool = False
    #: Books, pays, registers or submits a change: on our replicas only, and
    #: only behind the final screen (CLAUDE.md, the final-step rule).
    changes: bool = False
    #: What the page did after it, as checked when it is done again: the
    #: address it went to (its path), and something that appeared — a list
    #: opening after a name is typed (`list_opens`).
    expect_url: str | None = None
    expect_label: str | None = None
    list_opens: bool = False


@dataclass(frozen=True)
class Answer:
    """What the routine is for, pointed at by the helper: its name for the
    person, and the page's own label for it, where it is read from."""

    name: str
    reads: str


@dataclass(frozen=True)
class Routine:
    id: str
    label: str
    #: Where it starts: the address the helper opened.
    start: str
    steps: tuple[Step, ...]
    answer: Answer

    def __repr__(self) -> str:  # never a value the helper typed, whatever prints this
        return f"Routine(id={self.id!r}, steps={len(self.steps)}, ...)"

    __str__ = __repr__

    @property
    def asks(self) -> list[int]:
        """The steps whose value the person is asked for, by position."""
        return [index for index, step in enumerate(self.steps) if step.ask]

    @property
    def changes(self) -> bool:
        return any(step.changes for step in self.steps)


class NotARoutine(ValueError):
    """A file, or a row, that is not a routine this SIMBA can run."""


def _text(value: object, what: str, required: bool = True) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or len(value) > TEXT_MAX:
        raise NotARoutine(f"{what} is not a short piece of text")
    return value


def step_from(row: object) -> Step:
    """A step from a stored or shared row, every field checked."""
    if not isinstance(row, dict):
        raise NotARoutine("a step is not a record")
    kind = row.get("kind")
    if kind not in KINDS:
        raise NotARoutine(f"a step does something unknown: {kind!r}")
    nth = row.get("nth", 0)
    if not isinstance(nth, int) or isinstance(nth, bool) or not 0 <= nth < 100:
        raise NotARoutine("a step's position is not a small number")
    flags = {}
    for name in ("ask", "secret", "changes", "list_opens"):
        flag = row.get(name, False)
        if not isinstance(flag, bool):
            raise NotARoutine(f"a step's {name} is not yes or no")
        flags[name] = flag
    step = Step(kind=kind, role=_text(row.get("role"), "a step's role"),
                label=_text(row.get("label"), "a step's label"), nth=nth,
                qualifier=_text(row.get("qualifier"), "a step's qualifier", required=False),
                value=_text(row.get("value"), "a step's value", required=False),
                expect_url=_text(row.get("expect_url"), "a step's address", required=False),
                expect_label=_text(row.get("expect_label"), "a step's expected label",
                                   required=False),
                **flags)
    if step.secret and step.value is not None:
        raise NotARoutine("a password box carries a value")
    if step.kind in ("fill", "select") and not step.secret and not step.ask \
            and step.value is None:
        raise NotARoutine("a step to type has nothing to type")
    return step


def routine_from(row: object) -> Routine:
    if not isinstance(row, dict):
        raise NotARoutine("not a record")
    start = _text(row.get("start"), "the starting address")
    parts = urlsplit(start)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise NotARoutine("the starting address is not a web address")
    steps = row.get("steps")
    if not isinstance(steps, list) or not 0 < len(steps) <= MOST_STEPS:
        raise NotARoutine("the routine has no moves, or too many")
    answer = row.get("answer")
    if not isinstance(answer, dict):
        raise NotARoutine("the routine has no answer")
    label = clean_label(_text(row.get("label"), "the name") or "")
    if not label:
        raise NotARoutine("the routine has no name")
    return Routine(
        id=str(row.get("id") or secrets.token_hex(6)), label=label, start=start,
        steps=tuple(step_from(step) for step in steps),
        answer=Answer(name=_text(answer.get("name"), "the answer's name") or "",
                      reads=_text(answer.get("reads"), "the answer's label") or ""))


def as_row(routine: Routine) -> dict:
    return {"id": routine.id, "label": routine.label, "start": routine.start,
            "steps": [asdict(step) for step in routine.steps],
            "answer": asdict(routine.answer)}


def export(routine: Routine) -> str:
    """The routine as a file to give to someone else.

    Every value the helper typed becomes one the person is asked for: a shared
    routine is for someone else, and a reference number or a name kept in it
    would be the helper's, in plain text, in a file. A press keeps its key.
    Nothing else is changed, and no id: the other SIMBA gives it its own."""
    steps = [replace(step, value=None, ask=True) if step.kind in ("fill", "select")
             and not step.secret else step for step in routine.steps]
    row = as_row(replace(routine, steps=tuple(steps)))
    row.pop("id")
    return json.dumps({"format": FORMAT, "version": VERSION, **row}, indent=2)


#: The largest file `parse` reads, in characters: thirty moves of short text.
FILE_MAX = 64_000


def parse(text: str) -> Routine:
    """A routine from a file someone shared, or `NotARoutine` saying why not.

    Read as data and nothing else. A routine names roles and labels, never a
    selector or a script, and whatever it asks to do still goes through the
    loop's rules: a change only on our replicas and behind the final screen,
    and never a card's details."""
    if not isinstance(text, str) or len(text) > FILE_MAX:
        raise NotARoutine("the file is too large to be a routine")
    try:
        row = json.loads(text)
    except ValueError as error:
        raise NotARoutine("the file is not a routine") from error
    if not isinstance(row, dict) or row.get("format") != FORMAT:
        raise NotARoutine("the file is not a routine")
    if row.get("version") != VERSION:
        raise NotARoutine("the file is a routine from a different version of SIMBA")
    routine = routine_from({**row, "id": None})
    # A shared routine never carries a value of someone else's, whatever the
    # file says: every typed value is asked for.
    if any(step.kind in ("fill", "select") and not step.ask and not step.secret
           for step in routine.steps):
        raise NotARoutine("the file carries a typed value, which a shared routine never does")
    return routine


class RoutineStore:
    """The routines, in the order they were kept. Every change is written at once."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or os.environ.get("SIMBA_ROUTINES") or DEFAULT_PATH)
        self._available: bool | None = None

    @property
    def available(self) -> bool:
        """Whether this machine can encrypt a routine at all. Asked once."""
        if self._available is None:
            self._available = Vault().available
        return self._available

    def all(self) -> list[Routine]:
        if not self.available or not self.path.exists():
            return []
        try:
            blob = json.loads(self.path.read_text(encoding="utf-8"))["routines"]
            rows = json.loads(decrypt(bytes.fromhex(blob)).decode("utf-8"))
        except (OSError, ValueError, KeyError, VaultUnavailable):
            return []
        kept: list[Routine] = []
        for row in rows:
            try:
                kept.append(routine_from(row))
            except NotARoutine:
                continue  # one damaged row is that routine gone, not all of them
        return kept

    def get(self, routine_id: str | None) -> Routine | None:
        return next((r for r in self.all() if r.id == routine_id), None)

    def room(self, tiles: int = 0) -> bool:
        """Whether there is a place on the home screen's row for one more,
        beside `tiles` of the person's own."""
        return self.available and len(self.all()) + tiles < MAX_TILES

    def add(self, routine: Routine, tiles: int = 0) -> Routine | None:
        """Kept, under a fresh id, at the end of the row; None if it cannot be."""
        name = clean_label(routine.label)
        if not name or not self.room(tiles):
            return None
        kept = replace(routine, id=secrets.token_hex(6), label=name)
        self._write([*self.all(), kept])
        return kept

    def rename(self, routine_id: str, label: str) -> bool:
        name = clean_label(label)
        routines = self.all()
        if not name or not any(r.id == routine_id for r in routines):
            return False
        self._write([replace(r, label=name) if r.id == routine_id else r for r in routines])
        return True

    def remove(self, routine_id: str) -> bool:
        routines = self.all()
        kept = [r for r in routines if r.id != routine_id]
        if len(kept) == len(routines):
            return False
        self._write(kept)
        return True

    def clear(self) -> None:
        """Every routine gone, and the file with them: for the next person."""
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def _write(self, routines: list[Routine]) -> None:
        rows = [as_row(r) for r in routines]
        blob = encrypt(json.dumps(rows).encode("utf-8")).hex()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"routines": blob}), encoding="utf-8")


#: A press about consent on someone else's site. Asked of the person each time,
#: Yes or No, as the bill's cookie question is (`voice.ASK_COOKIES`,
#: 2026-10-16), whatever the helper chose: consent is the person's to give.
CONSENT_WORDS = re.compile(r"\b(cookies?|consent)\b", re.IGNORECASE)


def asks_consent(step: Step) -> bool:
    return step.kind == "click" and not step.changes and bool(CONSENT_WORDS.search(step.label))


def path_of(url: str) -> str:
    """The part of an address a step checks it went to: the path, without the
    query, which may hold a value the person typed."""
    return urlsplit(url).path or "/"


#: A short name for the file a routine is saved to: letters, digits and dashes.
def file_name(label: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9]+", "-", label).strip("-").lower()[:LABEL_MAX] or "routine"
    return f"{stem}.simba-routine.json"

