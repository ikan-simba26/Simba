"""Both colour directions are readable for low-vision readers, light and dark.

Read from `src/index.css` itself, so a colour changed there is measured here.
WCAG 2.2 contrast ratios:

- ink, the words people read, at AAA (7:1) on every ground it sits on;
- every other text pairing — softer text, the accent as text, the label on an
  accent button, the stuck colour — at least 4.5:1, which is AA for any size
  and AAA for SIMBA's text, none of it under 18px;
- the accent at least 3:1 against the canvas, where it is the edge of
  something to press and the keyboard focus ring (WCAG 1.4.11);
- the edge of every other thing to press or type in at least 3:1 against
  every ground it sits on (WCAG 1.4.11). Until 2026-10-14 those edges were
  the divider colour, at 1.3:1 to 1.6:1.
"""

import re
from pathlib import Path

import pytest

CSS = (Path(__file__).parent / "src" / "index.css").read_text(encoding="utf-8")

ROLES = ["canvas", "surface", "sunk", "line", "edge", "field", "ink", "soft", "accent", "accent-hover",
         "accent-ink", "tint", "stuck", "stuck-tint"]


def block(selector: str, dark: bool) -> str:
    """The body of the block that sets a direction's colours."""
    if dark:
        pattern = (r"@media \(prefers-color-scheme: dark\) \{\s*"
                   + re.escape(selector) + r" \{(.*?)\n  \}")
    else:
        pattern = r"^" + re.escape(selector) + r" \{(.*?)\n\}"
    found = re.search(pattern, CSS, re.S | re.M)
    assert found, (selector, dark)
    return found.group(1)


def palette(selector: str, dark: bool) -> dict[str, str]:
    values = dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6});", block(selector, dark)))
    assert set(ROLES) <= set(values), sorted(set(ROLES) - set(values))
    return values


def luminance(colour: str) -> float:
    channels = []
    for i in (1, 3, 5):
        c = int(colour[i:i + 2], 16) / 255
        channels.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    light, dark = sorted((luminance(a), luminance(b)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


THEMES = {
    "B light": (":root", False), "B dark": (":root", True),
    "A light": (':root[data-palette="a"]', False), "A dark": (':root[data-palette="a"]', True),
}
GROUNDS = ["canvas", "surface", "sunk", "tint", "field"]
TEXT = ([("ink", "stuck-tint")]
        + [("soft", ground) for ground in GROUNDS]
        + [("accent", ground) for ground in GROUNDS]
        + [("accent-ink", "accent"), ("accent-ink", "accent-hover"),
           ("stuck", "surface"), ("stuck", "canvas"), ("stuck", "stuck-tint")])


@pytest.mark.parametrize("theme", list(THEMES))
def test_ink_is_aaa_on_every_ground(theme: str) -> None:
    colours = palette(*THEMES[theme])
    for ground in GROUNDS + ["stuck-tint"]:
        assert contrast(colours["ink"], colours[ground]) >= 7, (theme, ground)


@pytest.mark.parametrize("theme", list(THEMES))
def test_every_other_text_pairing_is_at_least_4_5(theme: str) -> None:
    colours = palette(*THEMES[theme])
    low = {f"{text} on {ground}": round(contrast(colours[text], colours[ground]), 2)
           for text, ground in TEXT if contrast(colours[text], colours[ground]) < 4.5}
    assert not low, (theme, low)


@pytest.mark.parametrize("theme", list(THEMES))
def test_the_accent_stands_out_from_the_canvas(theme: str) -> None:
    colours = palette(*THEMES[theme])
    assert contrast(colours["accent"], colours["canvas"]) >= 3, theme


@pytest.mark.parametrize("theme", list(THEMES))
def test_the_edge_of_a_control_is_at_least_3(theme: str) -> None:
    colours = palette(*THEMES[theme])
    for ground in ["canvas", "surface", "sunk", "field"]:
        assert contrast(colours["edge"], colours[ground]) >= 3, (theme, ground)


SOURCE = Path(__file__).parent / "src"
#: Translucent text: a role's colour at less than full strength.
TRANSLUCENT = re.compile(r"(?:placeholder:)?text-(?:ink|soft|accent|stuck)/\d+")


def test_no_words_are_drawn_translucent() -> None:
    """The ratios above hold only at full strength. Until 2026-10-14 the
    stages still to come were `text-soft/70` (about 3.9:1) and the station
    box's example `placeholder:text-soft/70` (about 3.6:1 on its field).
    Decoration a screen reader skips may be lighter; the debug panel is not
    for the person."""
    found = []
    for path in SOURCE.rglob("*.tsx"):
        if path.name == "Debug.tsx":
            continue
        for number, text in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if TRANSLUCENT.search(text) and "aria-hidden" not in text:
                found.append(f"{path.name}:{number}: {text.strip()}")
    assert not found, found


def test_the_two_directions_differ() -> None:
    """A is a direction of its own, not B again."""
    for dark in (False, True):
        b, a = palette(":root", dark), palette(':root[data-palette="a"]', dark)
        assert a["accent"] != b["accent"] and a["canvas"] != b["canvas"]


# --- a tile's picture on its own colour (2026-11-10) ------------------------

PICTURES = ["train", "bill", "course", "other"]


def pictures(dark: bool) -> dict[str, str]:
    """The pictures' colours, set once in B's blocks and kept by A."""
    values = dict(re.findall(r"--(pic-[a-z-]+):\s*(#[0-9a-fA-F]{6});", block(":root", dark)))
    wanted = {f"pic-{kind}{part}" for kind in PICTURES for part in ("", "-tint")}
    assert wanted <= set(values), sorted(wanted - set(values))
    return values


@pytest.mark.parametrize("theme", list(THEMES))
def test_every_picture_is_plain_on_its_own_colour(theme: str) -> None:
    """Each picture at least 4.5:1 on its pale square, more than the 3:1 a
    picture needs, so it reads at a glance; ink at AAA on every pale, should
    words ever sit there; and each picture at least 3:1 on the tile round it."""
    selector, dark = THEMES[theme]
    colours, pics = palette(selector, dark), pictures(dark)
    for kind in PICTURES:
        deep, tint = pics[f"pic-{kind}"], pics[f"pic-{kind}-tint"]
        assert contrast(deep, tint) >= 4.5, (theme, kind, round(contrast(deep, tint), 2))
        assert contrast(colours["ink"], tint) >= 7, (theme, kind)
        assert contrast(deep, colours["surface"]) >= 3, (theme, kind)


def test_the_four_pictures_are_four_colours() -> None:
    for dark in (False, True):
        pics = pictures(dark)
        assert len({pics[f"pic-{kind}"] for kind in PICTURES}) == 4
        assert len({pics[f"pic-{kind}-tint"] for kind in PICTURES}) == 4


# --- the state colours (2026-11-17, the frontend redesign) -----------------------

def states(dark: bool) -> dict[str, str]:
    values = dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6});", block(":root", dark)))
    needed = {"turn", "turn-tint", "turn-ink", "done", "done-tint", "done-ink", "spot", "spot-ground"}
    assert needed <= set(values), sorted(needed - set(values))
    return values


@pytest.mark.parametrize("dark", [False, True], ids=["light", "dark"])
def test_the_words_on_a_state_colour_are_at_least_4_5(dark: bool) -> None:
    """"Your turn" on amber and "Done" on green, in the pill and on the card; and the
    help-me step's words, white on its dark ground."""
    colours = {**palette(":root", dark), **states(dark)}
    assert contrast(colours["turn-ink"], colours["turn-tint"]) >= 4.5
    assert contrast(colours["done-ink"], colours["done-tint"]) >= 4.5
    assert contrast("#ffffff", colours["spot-ground"]) >= 7
    # And the amber of the bar is seen against both the page and the card (a 6px band).
    for ground in ("canvas", "surface"):
        assert contrast(colours["turn"], colours[ground]) >= 1.8, ground
