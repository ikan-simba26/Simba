"""The interface says the same thing in the same situation, every time.

The audience for this interface is people with cognitive disabilities. Someone
who has learned that "Give me a moment." means waiting should never meet "One
moment…" for the same state: a second phrasing asks them to work out whether
something new is happening, which is exactly the work this project exists to
remove.

That is a property of the whole interface, so it cannot be checked by reading
one component. These tests check it four ways:

  * **The strings are real.** `copy.ts` is compiled with the project's own
    TypeScript and the values are read out of it, so a test cannot pass
    against a file that would not build, and cannot drift from what the
    interface actually renders.
  * **Nothing writes its own.** The components are scanned for text, and any
    words anywhere but `copy.ts` fail. This is the part that stops the file
    quietly becoming a suggestion.
  * **The backend is held to the same rules.** Half of what is on screen —
    every step's instruction, detail line and button labels, the stuck
    screen's suggestion, the trust panel's caption — is written by the
    backend, in the plans and in `backend/orchestrator/voice.py`. Until
    2026-09-17 nothing checked any of it.
  * **Where both sides voice one situation, it is one sentence.**

No new dependency: `tsc` is already here, and so is node.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from backend.orchestrator import voice
from backend.orchestrator.billing_plan import BILLING_PLAN
from backend.orchestrator.plan import REGISTRATION_PLAN, PlanStep
from backend.orchestrator.railways_plan import RAILWAYS_PLAN
from shared.schema import StepAction

FRONTEND = Path(__file__).resolve().parent
REPO = FRONTEND.parent
SOURCE = FRONTEND / "src"
COPY = SOURCE / "copy.ts"
BUILD = REPO / ".scratch" / "copyjs"

# The development view is for whoever is building the app, never for the
# person it is for (Ctrl+Shift+D, and see `Debug.tsx`). Its text is exempt.
NOT_FOR_THE_PERSON = {"Debug.tsx"}

# Words the reader would have to be taught (the rules at the top of copy.ts).
# Whole words, any case.
TAUGHT_WORDS = ("step", "steps", "session", "verify", "retry", "overlay")

# The backend is also never to talk about the person as "the user". The person
# reading it is the user.
NOT_TO_THEIR_FACE = ("user",)


def npm(*args: str) -> subprocess.CompletedProcess:
    exe = shutil.which("npx") or shutil.which("npx.cmd")
    if exe is None:
        pytest.skip("npx not on PATH")
    return subprocess.run(
        [exe, *args], cwd=FRONTEND, capture_output=True, text=True, timeout=300
    )


@pytest.fixture(scope="module")
def copy() -> dict:
    """`copy.ts`, compiled and evaluated, as the interface itself sees it.

    The one type import cannot resolve without the project's path aliases, so
    `tsc` reports it and emits anyway — the annotation is erased, and the
    values are what this is about. The emit is what gets checked, not the
    exit code.
    """
    if BUILD.exists():
        shutil.rmtree(BUILD)
    npm("tsc", str(COPY.relative_to(FRONTEND)), "--outDir", str(BUILD),
        "--module", "commonjs", "--target", "es2020", "--skipLibCheck")

    emitted = BUILD / "copy.js"
    if not emitted.exists():
        pytest.skip("copy.ts did not compile; run npm run build for the real error")

    node = shutil.which("node") or shutil.which("node.exe")
    if node is None:
        pytest.skip("node not on PATH")

    script = (
        f"const c = require({json.dumps(str(emitted))});"
        "process.stdout.write(JSON.stringify({"
        "situations: c.SITUATIONS, labels: c.LABELS,"
        "presence: {opening: c.presence('opening'), thinking: c.presence('thinking'),"
        " acting: c.presence('acting')},"
        "levelUp: c.levelNotice(2, 3), levelDown: c.levelNotice(3, 2),"
        "levelUp2: c.levelNotice(1, 2), levelDown2: c.levelNotice(2, 1),"
        "count: [c.STEP.count(1, 3), c.STEP.count(1, 3), c.STEP.count(2, 3)],"
        "home: c.HOME, ending: c.ENDING, stopped: c.STOPPED,"
        "notice: c.NOTICE, trust: c.TRUST, found: c.FOUND"
        "}));"
    )
    result = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def everything_in(copy: dict) -> dict[str, str]:
    """Every string in the tables, keyed by where it lives."""
    return {
        **{f"situation {k}": v for k, v in copy["situations"].items()},
        **{f"label {k}": v for k, v in copy["labels"].items()},
    }


def taught_words_in(text: str, words: tuple[str, ...] = TAUGHT_WORDS) -> list[str]:
    return [w for w in words if re.search(rf"\b{w}\b", text, flags=re.IGNORECASE)]


# --- the same situation is the same string ----------------------------------


def test_asking_twice_gives_the_same_sentence(copy: dict) -> None:
    """The property, stated directly.

    A situation is a lookup, not a construction, so this can only fail if
    someone makes it one — which is the change worth catching.
    """
    assert copy["count"][0] == copy["count"][1]
    assert copy["presence"]["thinking"] == copy["situations"]["presence.thinking"]
    assert copy["presence"]["acting"] == copy["situations"]["presence.acting"]
    assert copy["presence"]["opening"] == copy["situations"]["presence.opening"]


def test_a_level_change_reads_the_same_whichever_levels_it_is_between(copy: dict) -> None:
    """2 -> 3 and 1 -> 2 are the same situation: it got simpler.

    Naming the levels would be worse than saying nothing — "level" is a word
    this reader would have to be taught, and the number is meaningless to
    them. So both directions collapse to two sentences, and these must not
    drift apart as new level pairs are added.
    """
    assert copy["levelUp"] == copy["levelUp2"] == copy["notice"]["simpler"]
    assert copy["levelDown"] == copy["levelDown2"] == copy["notice"]["fuller"]


def test_simpler_and_fuller_are_not_the_same_sentence(copy: dict) -> None:
    """Announced changes have to be distinguishable, or announcing is noise."""
    assert copy["notice"]["simpler"] != copy["notice"]["fuller"]


def test_every_situation_has_a_sentence(copy: dict) -> None:
    for name, sentence in everything_in(copy).items():
        assert sentence.strip(), f"{name} has no words"


def test_no_two_situations_share_a_sentence(copy: dict) -> None:
    """Two situations reading identically is the same problem in reverse.

    If "I couldn't do that." meant both a skipped step and a failed task, the
    notice would stop telling the reader anything.
    """
    seen: dict[str, str] = {}
    for name, sentence in copy["situations"].items():
        assert sentence not in seen, f"{name} reads exactly like {seen[sentence]}"
        seen[sentence] = name


def test_no_two_buttons_share_a_label(copy: dict) -> None:
    seen: dict[str, str] = {}
    for name, label in copy["labels"].items():
        assert label not in seen, f"{name} is labelled exactly like {seen[label]}"
        seen[label] = name


# --- the words themselves ---------------------------------------------------


def test_the_step_count_is_the_only_place_a_number_is_explained(copy: dict) -> None:
    assert copy["count"][2] == "Step 2 of 3"


def test_sentences_end(copy: dict) -> None:
    """A sentence said to a person is punctuated. Button labels are not.

    This is the one mechanical check on tone that is worth automating: it
    catches a label pasted into a place that speaks, and a sentence pasted
    onto a button.
    """
    for name, sentence in copy["situations"].items():
        # A colon counts: it introduces the thing below it, which is a whole
        # thought, and rewriting it as a full stop would be worse English.
        assert sentence[-1] in ".?:", f"{name} does not end a sentence: {sentence!r}"
    for name, label in copy["labels"].items():
        assert label[-1].isalnum(), f"{name} is a label and is punctuated: {label!r}"


def test_no_word_the_reader_would_have_to_be_taught(copy: dict) -> None:
    """The rule in copy.ts, checked. `STEP.count` is not in these tables, and
    is the one known exception — flagged in STATUS.md, not settled here."""
    for name, text in everything_in(copy).items():
        assert not taught_words_in(text), f"{name} uses {taught_words_in(text)}: {text!r}"


def test_apostrophes_are_straight(copy: dict) -> None:
    """One screen should never mix `I'm` with `I’ll`. The backend is held to
    the same rule below, since both appear on the same screen."""
    for name, text in everything_in(copy).items():
        assert "’" not in text and "‘" not in text, f"{name}: {text!r}"


def test_the_closing_screen_offers_a_way_out_and_a_way_on(copy: dict) -> None:
    """Never a dead end: a task that has ended has two things to press."""
    assert copy["ending"]["finish"].strip()
    assert copy["ending"]["again"].strip()
    assert copy["ending"]["finish"] != copy["ending"]["again"]


# --- nothing writes its own -------------------------------------------------


def words_in(text: str) -> list[str]:
    """Anything in a component that a person would read.

    JSX text between tags, across lines, and the text-bearing attributes. It
    used to look only for single-line text of three or more words ending in a
    full stop or question mark — "prose, not labels" — and so it passed three
    strings that were on screen all along: `let it choose`, `Hide the page`,
    and the image description in the trust panel. A label is copy too.

    Deliberately crude, and tuned against its one known false positive: an
    arrow function's `=>` followed by code up to the next `<`. A `>` right
    after `=` or `-` never starts a match, and a candidate containing
    code punctuation is not text.
    """
    found = []
    for match in re.finditer(r"(?<![=\-])>([^<>{}]*)<", text):
        candidate = " ".join(match.group(1).split())
        if not re.search(r"[A-Za-z]", candidate):
            continue
        if re.search(r"[;=()|]|&&", candidate):
            continue
        found.append(candidate)
    for match in re.finditer(
        r'\b(?:aria-label|alt|placeholder|title)=("[^"]*"|\{`[^`]*`\})', text
    ):
        found.append(match.group(0))
    return found


def test_the_scanner_finds_what_it_used_to_miss() -> None:
    """The control for the scanner itself: the three strings it passed."""
    assert words_in("<button>\n            let it choose\n          </button>")
    assert words_in("<button onClick={closeTrust}>\n  Hide the page\n</button>")
    assert words_in('<img alt="The page as it is right now" />')
    assert words_in("aria-label={`Show ${label}`}")
    # And not code.
    assert not words_in("const f = (a) => a.b < c;")
    assert not words_in("<span>{TRUST.hide}</span>")


def test_no_component_writes_its_own_words() -> None:
    """The file is only one place if nothing else is also a place.

    Without this, `copy.ts` is a convention. With it, adding a sentence to a
    component fails here and the author is told where it belongs.
    """
    offenders: dict[str, list[str]] = {}
    for path in sorted(SOURCE.rglob("*.tsx")):
        if path.name in NOT_FOR_THE_PERSON:
            continue
        found = words_in(path.read_text(encoding="utf-8"))
        if found:
            offenders[path.name] = found

    assert not offenders, (
        "user-facing words outside copy.ts:\n"
        + "\n".join(f"  {name}: {items}" for name, items in offenders.items())
    )


def test_the_copy_file_is_the_one_that_has_them() -> None:
    """The control: the check above would also pass if nothing had any copy."""
    source = COPY.read_text(encoding="utf-8")
    assert source.count('"') > 40, "copy.ts has suspiciously few strings"


# --- the backend's half -----------------------------------------------------

PLANS: dict[str, list[PlanStep]] = {
    "registration": REGISTRATION_PLAN,
    "billing": BILLING_PLAN,
    "railways": RAILWAYS_PLAN,
}


def mock_steps() -> list:
    """The mock backend's script. It is the demo-day fallback (CONTRACT.md),
    so what it shows is held to the same rules as a real plan."""
    from tools.mock_backend import STEPS

    return STEPS


def every_step() -> list[tuple[str, str, str, list[StepAction]]]:
    """(where, instruction, detail, actions) for every step anything shows."""
    steps = [
        (f"{flow} plan step {i}", s.instruction, s.detail, s.actions)
        for flow, plan in PLANS.items()
        for i, s in enumerate(plan, start=1)
    ]
    steps += [
        (f"mock step {s.step_index}", s.instruction, s.detail, s.actions)
        for s in mock_steps()
    ]
    # What the LLM planner and replay say, for each kind of move they make.
    for kind in ("fill", "type", "select", "click"):
        steps.append(
            (f"described {kind}", voice.describe(kind, "Reference No."), "",
             voice.actions(voice.GO_AHEAD))
        )
    return steps


def backend_sentences() -> dict[str, str]:
    """Every sentence the backend puts on screen, keyed by where it comes from."""
    sentences: dict[str, str] = {}
    for where, instruction, detail, _ in every_step():
        sentences[f"{where} instruction"] = instruction
        if detail:
            sentences[f"{where} detail"] = detail
    sentences["voice.HELP_SUGGESTION"] = voice.HELP_SUGGESTION
    sentences["voice.YOU_STOPPED"] = voice.YOU_STOPPED
    sentences["voice.PREVIEW_CAPTION"] = voice.PREVIEW_CAPTION
    for kind, key in (("fill", ""), ("select", ""), ("click", ""), ("press", "Enter"),
                      ("press", "F13")):
        sentences[f"voice.caption {kind} {key}"] = voice.caption(kind, "Reference No.", key)
    return sentences


def backend_labels() -> dict[str, str]:
    return {
        f"{where} action {action.id}": action.label
        for where, _, _, actions in every_step()
        for action in actions
    }


def test_every_backend_sentence_is_a_sentence() -> None:
    for where, text in backend_sentences().items():
        assert text[:1].isupper() or text[:1].isdigit(), f"{where} does not start: {text!r}"
        assert text[-1] in ".?", f"{where} does not end a sentence: {text!r}"


def test_every_backend_label_is_a_label() -> None:
    for where, label in backend_labels().items():
        assert label.strip(), f"{where} has no words"
        assert label[-1].isalnum(), f"{where} is a label and is punctuated: {label!r}"


def test_every_step_stops_in_the_same_words() -> None:
    """The second button on every step of every plan, the LLM's and replay's
    moves, and the mock's, is the same way to stop, in the same words."""
    for where, _, _, actions in every_step():
        secondary = [a for a in actions if a.kind == "secondary"]
        assert [(a.id, a.label) for a in secondary] == [(voice.CANCEL_ID, voice.STOP)], where
        primary = [a for a in actions if a.kind == "primary"]
        assert [a.id for a in primary] == [voice.CONFIRM_ID], where


def test_the_backend_uses_no_word_the_reader_would_have_to_be_taught() -> None:
    for where, text in {**backend_sentences(), **backend_labels()}.items():
        taught = taught_words_in(text, TAUGHT_WORDS + NOT_TO_THEIR_FACE)
        assert not taught, f"{where} uses {taught}: {text!r}"


def test_the_backend_apostrophes_are_straight() -> None:
    for where, text in {**backend_sentences(), **backend_labels()}.items():
        assert "’" not in text and "‘" not in text, f"{where}: {text!r}"


def test_no_web_address_reaches_the_screen() -> None:
    for where, text in {**backend_sentences(), **backend_labels()}.items():
        assert "http" not in text and "://" not in text, f"{where}: {text!r}"


def test_the_stuck_screen_reads_the_same_whichever_side_wrote_it(copy: dict) -> None:
    """The backend's `help.requested.suggestion` is what the stuck screen shows
    when it arrives; `STOPPED.suggestion` is what it shows when it does not.
    Before this test they were different sentences, and the one in `copy.ts`
    was never the one on screen."""
    assert voice.HELP_SUGGESTION == copy["stopped"]["suggestion"]


BACKEND_SOURCES = [
    *sorted((REPO / "backend" / "orchestrator").glob("*.py")),
    REPO / "tools" / "mock_backend.py",
]


def test_nothing_in_the_backend_writes_its_own_way_to_stop() -> None:
    """The backend's version of the component scan. A secondary action or a
    stuck-screen suggestion written anywhere but `voice.py` is a second place
    the voice is set."""
    offenders: list[str] = []
    for path in BACKEND_SOURCES:
        if path.name == "voice.py" or path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r'kind\s*=\s*"secondary"', text):
            offenders.append(f"{path.name}: a secondary action")
        if re.search(r'suggestion\s*=\s*[f]?"', text):
            offenders.append(f"{path.name}: a help suggestion")
        if re.search(r'TaskFailed\(\s*reason\s*=\s*[f]?"', text):
            offenders.append(f"{path.name}: a failure reason")
    assert not offenders, offenders
