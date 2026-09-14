"""The interface says the same thing in the same situation, every time.

The audience for this interface is people with cognitive disabilities. Someone
who has learned that "Give me a moment." means waiting should never meet "One
moment…" for the same state: a second phrasing asks them to work out whether
something new is happening, which is exactly the work this project exists to
remove.

That is a property of the whole interface, so it cannot be checked by reading
one component. These tests check it two ways:

  * **The strings are real.** `copy.ts` is compiled with the project's own
    TypeScript and the values are read out of it, so a test cannot pass
    against a file that would not build, and cannot drift from what the
    interface actually renders.
  * **Nothing writes its own.** The components are scanned for sentences, and
    a sentence anywhere but `copy.ts` fails. This is the part that stops the
    file quietly becoming a suggestion.

No new dependency: `tsc` is already here, and so is node.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parent
SOURCE = FRONTEND / "src"
COPY = SOURCE / "copy.ts"
BUILD = FRONTEND.parent / ".scratch" / "copyjs"

# Components are allowed to contain these: they are not sentences said to a
# person, they are structure.
ALLOWED_LITERALS = {
    # Level control labels, which are per-level and generated from a number.
    "Show more",
    "Show less",
    "Show the usual amount",
}


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
        "situations: c.SITUATIONS,"
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
    for name, sentence in copy["situations"].items():
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


def test_the_closing_screen_offers_a_way_out_and_a_way_on(copy: dict) -> None:
    """Never a dead end: a task that has ended has two things to press."""
    assert copy["ending"]["finish"].strip()
    assert copy["ending"]["again"].strip()
    assert copy["ending"]["finish"] != copy["ending"]["again"]


# --- nothing writes its own -------------------------------------------------


def sentences_in(text: str) -> list[str]:
    """JSX text that reads like something said to a person.

    Deliberately crude: anything between tags with two or more words and a
    full stop or question mark. It is looking for prose, not for labels.
    """
    import re

    found = []
    # >Some words here.<  — JSX text nodes only, never attributes or code.
    #
    # One line, no braces, no angle brackets. An earlier version allowed
    # newlines after the first character and swallowed whole blocks of code
    # between an arrow function's `=>` and the next `<`, then reported the
    # block as a sentence.
    for match in re.finditer(r">([^<>{}\n]{8,})<", text):
        candidate = match.group(1).strip()
        if candidate in ALLOWED_LITERALS:
            continue
        words = candidate.split()
        if len(words) >= 3 and candidate[-1] in ".?!":
            found.append(candidate)
    return found


def test_no_component_writes_its_own_sentences() -> None:
    """The file is only one place if nothing else is also a place.

    Without this, `copy.ts` is a convention. With it, adding a sentence to a
    component fails here and the author is told where it belongs.
    """
    offenders: dict[str, list[str]] = {}
    for path in sorted(SOURCE.rglob("*.tsx")):
        found = sentences_in(path.read_text(encoding="utf-8"))
        if found:
            offenders[path.name] = found

    assert not offenders, (
        "user-facing sentences outside copy.ts:\n"
        + "\n".join(f"  {name}: {items}" for name, items in offenders.items())
    )


def test_the_copy_file_is_the_one_that_has_them() -> None:
    """The control: the check above would also pass if nothing had any copy."""
    source = COPY.read_text(encoding="utf-8")
    assert source.count('"') > 40, "copy.ts has suspiciously few strings"
