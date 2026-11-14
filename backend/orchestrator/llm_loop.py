"""The LLM planner.

This module decides *which* action comes next and nothing else. Presenting,
acting, verifying, retrying and giving up all live in `loop.py` and are the
same code the hardcoded planner runs, so an A/B between the two compares
planning and only planning.

The model never sees a selector — it answers with an integer element id from
the list it was shown — and it never sees a credential: the page it is given
carries labels, never values, and vault values are substituted at execution
time by `loop.resolve_value`.

Its schema has no "done" verb, by design, so completion is decided by the
task's success condition rather than by the model claiming to be finished.
"""

import asyncio
import re
from collections import Counter
from dataclasses import dataclass, replace

from backend.orchestrator.llm import Action, LLMError, Provider
from backend.orchestrator.loop import CHANGE_WORDS, Move, Task
from backend.orchestrator import voice
from backend.orchestrator.plan import About, Expectation, Operation, Target
from backend.perception.content import Content
from backend.perception.serializer import VIEWPORT, Element
from shared.schema import Finding, StepField

SYSTEM_PROMPT = """You operate a web page on behalf of someone who finds \
cluttered interfaces overwhelming.

You are given a goal and a numbered list of the page's interactive elements. \
Choose the single next action that makes progress toward the goal.

Rules:
- Answer with an element_id taken from the list. Never write a CSS selector, \
an XPath, or element text as the id.
- One action at a time. Do not plan ahead in the answer.
- Use "type" for text fields, "click" for buttons and links, "select" for \
dropdowns.
- For a password or username field, set value to null. Those are filled from \
the user's vault, not by you.
- If any element is marked [overlay], something is covering the page. Dismiss \
it first, using one of the [overlay] elements, before anything else. What it \
covers is not listed until it is gone.
- When the goal needs the user signed in, fill the sign-in fields on this page \
rather than navigating. Prefer form fields and buttons over navigation links.
- Keep reasoning to one short sentence, phrased for the person you are helping.
"""

REGISTRATION_TASK = Task(
    goal="Register for the course CS-401.",
    estimated_steps=4,
    success=Expectation(url_contains="/register", title_contains="Registration Confirmed"),
    # Changes something rather than finding something out. The course code is
    # in the goal, but the confirmation page states it as text, not in a field.
    about=About(),
)


@dataclass(frozen=True)
class _Choice:
    action: Action
    element: Element


#: The longest label put in the prompt (2026-11-13). Past it, the rest is cut:
#: a link that is a whole sentence is told apart by its first words.
LABEL_CHARS = 80
#: Input types that say nothing the role does not: shown only when they add
#: something (password, email, number, date, a checkbox drawn as a button…).
PLAIN_INPUTS = {"text", "search", "button", "submit", "reset", "image"}


def _without_icons(text: str) -> str:
    """`text` without icon-font characters (Unicode's private use area): a
    search button drawn as `\\uf002` has no words, and the model and the person
    were shown a glyph that means nothing ("Click .", 2026-11-13j)."""
    return " ".join("".join(ch for ch in text if not "" <= ch <= "").split())


def _label(text: str) -> str:
    """One line, no run of spaces, no icon glyphs, at most LABEL_CHARS."""
    text = _without_icons(text)
    return text if len(text) <= LABEL_CHARS else text[:LABEL_CHARS - 1].rstrip() + "…"


#: A field whose typing is a search: Enter sends it (2026-11-14). By role, or
#: by the words a shop's search box uses.
SEARCH_LABEL = re.compile(r"\b(search|keyword|find)\b", re.IGNORECASE)


def _off_the_side(element: Element) -> bool:
    """Wholly left or right of the page's width: a sliding banner's hidden
    slide. Below the fold is not out of sight — a click scrolls to it."""
    if element.rect is None:
        return False
    x, _y, width, _height = element.rect
    return x >= VIEWPORT[0] or x + width <= 0


def _is_search(element: Element) -> bool:
    return element.role == "searchbox" or (
        element.role in ("combobox", "textbox") and bool(SEARCH_LABEL.search(element.label)))


def usable(elements: list[Element],
           failed: "set[tuple[str, str]] | frozenset[tuple[str, str]]" = frozenset()
           ) -> list[Element]:
    """The elements a planner is shown, and so may choose (2026-11-14): what
    `render_page` lists. Part of an overlay, or neither behind one, nor a link
    that goes nowhere, nor off the side, nor something that just failed."""
    return [e for e in elements if e.overlay
            or (not (e.occluded or e.dead_link) and not _off_the_side(e)
                and (e.role, e.label) not in failed)]


#: Said above the list, for a goal with no plan, when something is on top of
#: the page (2026-11-14). The written plans' banner says "dismiss it first",
#: which is right for a cookie notice and wrong for the sign-in dialog a goal
#: needs: on Readings the model was shown `link 'Register.' [overlay]` under
#: that banner and pressed Close instead, five times (EVALUATION.md, 2026-11-14c).
ON_TOP_BANNER = (
    "SOMETHING IS ON TOP OF THE PAGE. Only the elements marked [overlay] can be "
    "used now; what it covers is not listed until it is gone. If it is what the "
    "goal needs (a sign-in or sign-up form, a search), use it. If it is in the "
    "way (cookies, an advert, a notice), close it.")


def render_page(elements: list[Element],
                failed: "set[tuple[str, str]] | frozenset[tuple[str, str]]" = frozenset(),
                on_top: str | None = None) -> str:
    """The page as the model sees it: ids, roles, labels. Never values.

    Perception's structural flags are spelled out rather than left implicit.
    A model cannot infer from a list of sixty buttons that one of them belongs
    to a modal covering the rest — nor that six of them appeared a moment ago
    because someone started typing, and are the only way to commit a choice.

    **Trimmed on 2026-11-13** to spend fewer tokens on what no move can use,
    measured on seven pages to pick the same elements (EVALUATION.md):

    - what can never be chosen is not listed, only counted — an element behind
      the overlay, and a link that goes nowhere — unless it is part of the
      overlay itself, which is how the overlay is closed;
    - the marks are short (`[overlay]`, `[inferred]`), said once what they mean;
    - an input type is shown only where the role does not already say it;
    - a label is one line of at most LABEL_CHARS;
    - nor what is out of sight off the side of the page (a sliding banner's
      hidden slides), nor what the model chose and did not work just now
      (`failed`, by role and label) — both 2026-11-14.
    """
    blocked = any(element.overlay for element in elements)
    choices = [e for e in elements if e.inferred and e.role == "option"]
    behind = sum(1 for e in elements if e.occluded and not e.overlay)
    nowhere = sum(1 for e in elements if e.dead_link and not e.occluded and not e.overlay)
    aside = [e for e in elements if not e.overlay and not (e.occluded or e.dead_link)
             and _off_the_side(e)]
    tried = [e for e in elements if not e.overlay and not (e.occluded or e.dead_link)
             and not _off_the_side(e) and (e.role, e.label) in failed]
    gone = {id(e) for e in aside + tried}
    listed = [e for e in elements if e.overlay
              or (not (e.occluded or e.dead_link) and id(e) not in gone)]

    lines = []
    if blocked and on_top:
        lines += [on_top, ""]
    elif blocked:
        lines += [
            "AN OVERLAY IS COVERING THE PAGE. Dismiss it first, using an element "
            "marked [overlay]; what it covers is not listed until it is gone.",
            "",
        ]
    if choices:
        # A banner, not a rule in the list. The same move the OVERLAY case
        # makes, for the same reason and on the same evidence: told as one
        # rule among nine, a model reads it and proceeds anyway. The first
        # live LLM run was shown `option 'LAHORE CANTT'` and the rule saying
        # to click it, and typed into the next field instead — because from
        # where it sits, having typed the station name, the field is done.
        # The page disagrees, and says so only by silently emptying it.
        lines += [
            f"A LIST OF CHOICES IS OPEN, with {len(choices)} option(s) marked "
            "[inferred] below. Nothing is chosen yet. Typing the text is not "
            "choosing: click the option you want NOW, before touching any "
            "other field, or what you typed will be discarded."
        ]

        # And say what it is showing, if it says so itself.
        #
        # A month of day cells is not self-describing: every month has a 15th,
        # and which month is on screen is stated once, in a header, in text a
        # planner had no reason to single out. Both live LLM runs clicked the
        # 15th of the month the picker happened to open on, with the goal
        # naming a different one and `button 'September'` sitting unremarked
        # in a list of eighteen. Promoted here for the same reason the overlay
        # banner is promoted: a fact that changes which element is correct
        # belongs above the list, not in it.
        showing = _headings_of(choices)
        if showing:
            lines += [
                f"IT IS SHOWING: {showing}. Check that against the goal before "
                "picking anything. If it is the wrong one, the controls that "
                "change it are in the list below — use them first.",
            ]
        lines += [""]

    # Say that a role is a guess. The model is choosing partly on the strength
    # of the role word, and "option" read from the page and "option" worked
    # out from a mouse cursor are not the same claim. Said once here, and
    # marked on each line, rather than spelled out on all forty-two day cells.
    if any(e.inferred for e in listed):
        lines += ["[inferred] means the role was worked out from the layout, "
                  "not declared by the page."]
    hidden = []
    if behind:
        hidden.append(f"{behind} behind the overlay")
    if nowhere:
        hidden.append(f"{nowhere} links that go nowhere")
    if aside:
        hidden.append(f"{len(aside)} out of sight to the side (a sliding banner)")
    if tried:
        hidden.append(f"{len(tried)} that did not work just now")
    if hidden:
        lines += [f"Not listed, since none can be used: {', '.join(hidden)}."]
    if lines and lines[-1] != "":
        lines += [""]

    for element in listed:
        name = _label(element.label)
        line = f"{element.id}. {element.role} {name!r}" if name else f"{element.id}. {element.role} (no name)"
        if element.qualifier:
            # Without this a month grid offers two elements called '30' and
            # nothing to choose between them.
            line += f" ({element.qualifier})"
        if (element.input_type and element.input_type not in PLAIN_INPUTS
                and element.input_type != element.role):
            line += f" [input type={element.input_type}]"
        if element.overlay:
            line += " [overlay]"
        if element.inferred:
            line += " [inferred]"
        lines.append(line)
    return "\n".join(lines)


def _headings_of(choices: list[Element]) -> str:
    """What the open panels say they are showing, in the order they appear.

    Distinct, because forty-two day cells share one heading and repeating it
    forty-two times is how a banner stops being read.
    """
    seen: list[str] = []
    for element in choices:
        if element.panel and element.panel not in seen:
            seen.append(element.panel)
    return "; ".join(seen)


def describe(action: Action, element: Element) -> str:
    """The action as a sentence for the person being helped. See `voice.describe`."""
    name = _without_icons(element.label)
    if not name:
        name = "the button with no name" if element.role == "button" else f"item {element.id}"
    return voice.describe(action.action, name)


#: What a private value is replaced with in anything sent to a model.
PRIVATE_MARK = "[what you typed]"


class LLMPlanner:
    """Asks the model for one action and shapes it into a Move."""

    def __init__(self, provider: Provider, task: Task) -> None:
        self._provider = provider
        self._task = task
        self.calls_made = 0
        self.stuck_reason: str | None = None
        #: Everything the person typed in this run, and any saved sign-in
        #: used: never sent to a model, even when the site shows it back
        #: ("Deliver to: …", "Hello, …"). Free providers may keep what they
        #: are sent (2026-11-14; DECISIONS.md, 2026-11-13).
        self._private: set[str] = set()
        #: The element of the last choice, and those that did not work since
        #: the last move that did — by role and label, as ids change with
        #: every read (2026-11-14).
        self._last: tuple[str, str] | None = None
        self._failed: set[tuple[str, str]] = set()

    def keep_private(self, values) -> None:
        """Called by the loop with the values it is about to type."""
        for value in values:
            value = " ".join(str(value or "").split())
            # Two characters or fewer would blank out ordinary words ("No").
            if len(value) >= 3:
                self._private.add(value)

    def _redacted(self, text: str | None) -> str | None:
        """`text` with every private value replaced, longest first."""
        if not text or not self._private:
            return text
        for value in sorted(self._private, key=len, reverse=True):
            text = re.sub(re.escape(value).replace(r"\ ", r"\s+"), PRIVATE_MARK, text,
                          flags=re.IGNORECASE)
        return text

    async def _decide(self, system: str, page: str, feedback: str | None,
                      history: list[str] | None) -> Action:
        """The one way a planner asks the model: with nothing private in it."""
        return await self._provider.decide(
            system, self._redacted(page) or "", self._task.goal, self._redacted(feedback),
            [self._redacted(line) or "" for line in history] if history else history)

    def _note(self, setback: str | None) -> None:
        """A setback means the last choice did not work: not offered again
        until something works. No setback: the last move worked."""
        if setback and self._last is not None:
            self._failed.add(self._last)
        elif not setback:
            self._failed.clear()

    def _chose(self, choice: "_Choice | None") -> None:
        element = choice.element if choice is not None else None
        self._last = (element.role, element.label) if element is not None else None

    async def next_move(
        self, elements: list[Element], history: list[str], setback: str | None
    ) -> Move | None:
        self._note(setback)
        choice = await self._choose(elements, history, setback)
        self._chose(choice)
        if choice is None:
            return None
        return await self._shape(choice)

    async def _shape(self, choice: "_Choice") -> Move:
        """A chosen action as a Move: what is said, done and checked."""
        action, element = choice.action, choice.element
        operation = Operation(
            kind="fill" if action.action == "type" else action.action,
            target=Target(role=element.role, label=element.label),
            element_id=element.id,
            value=action.value,
        )
        operations = [operation]
        # Typing into a search box sends the search too (2026-11-14): a search
        # button is often only an icon, and Readings' was typed into seven
        # times and never sent (EVALUATION.md, 2026-11-13j).
        if action.action == "type" and _is_search(element):
            operations.append(Operation(kind="press", target=operation.target,
                                        element_id=element.id, value="Enter"))

        # A field for whatever is being typed, so the person can say it. A
        # password field is offered too, as a protected one, always empty: the
        # loop types a saved password itself and hides the field, or the person
        # types it and may keep it (`vault.py`). Until 2026-10-03 a password
        # step offered no field and, with no vault, could not be done at all.
        # The model's own value for a password is never used (`resolve_value`).
        fields = (
            [
                StepField(
                    id=element.name or str(element.id),
                    label=element.label,
                    type="password" if element.is_password else (element.input_type or "text"),
                    value="",
                )
            ]
            if action.action == "type"
            else []
        )

        return Move(
            instruction=describe(action, element),
            detail=action.reasoning,
            operations=operations,
            # The model declares no expectation, so the bar is the general one:
            # the page must actually have changed. A typed value is checked by
            # reading the field back, in loop.attempt_move.
            expect=Expectation(),
            fields=fields,
            actions=voice.actions(voice.GO_AHEAD),
        )

    async def _choose(
        self, elements: list[Element], history: list[str], setback: str | None
    ) -> _Choice | None:
        """One action, retried once with the specific error fed back."""
        feedback = setback
        valid = {element.id: element for element in elements}

        for _ in range(2):
            self.calls_made += 1
            try:
                action = await self._decide(SYSTEM_PROMPT,
                                            render_page(elements, self._failed),
                                            feedback, history)
            except LLMError as error:
                feedback = str(error)
                continue

            if action.element_id not in valid:
                feedback = (
                    f"element_id {action.element_id} is not on the page. "
                    f"Valid ids are 1 to {len(elements)}."
                )
                continue

            return _Choice(action=action, element=valid[action.element_id])

        self.stuck_reason = f"I could not work out the next step: {feedback}"
        return None



# --- any goal, on any website (2026-11-13, the advisor's direction) ----------
#
# A goal nobody wrote a plan for, on a live website. The model chooses one
# move at a time from the numbered elements, as `LLMPlanner` does, and also
# reads what the page says — headings, labelled values, tables — so it can
# tell when the answer is in front of it. Then it answers, copying the answer
# from the page. Nothing it answers is shown until SIMBA has found those exact
# words on the page itself. Everything else — what may be pressed, what is
# checked after each move, what is never typed — is the loop's, as for every
# planner.
#
# **Changed 2026-11-14 (Raham, after trying it in the real window)**: it works
# like the built-in tasks. What it is about to do is read back once and agreed
# once (`OpenGoalBrief`); then the moves that only look — searching, opening,
# reading, filling a box with something the goal said — run by themselves as
# lines of the checklist, with one Pause (`Move.safe`). It stops for the person
# only for a real choice, something only they can type, the final screen, the
# payment handover and a check that a person is there. It says what each move
# will do in plain words (`voice.plain_move`). And it stops, rather than
# wander, when it is not getting anywhere (`STALL_LIMIT`). Until then every
# move was asked: ten questions on Readings in one run (DECISIONS.md, *The AI
# planner asks once*).

#: The planner's own instructions for a goal with no plan (2026-11-14). Not
#: `SYSTEM_PROMPT`, which the measured registration benchmark uses unchanged.
OPEN_GOAL_SYSTEM = """You operate a web page for someone who finds cluttered \
websites overwhelming. They have agreed to the goal once; you do the looking \
and the clicking for them.

You are given the goal, what has been done so far, a numbered list of the \
page's elements, and what the page says. Choose the single next action that \
makes progress toward the goal.

Rules:
- Answer with an element_id taken from the list. Only ids in the list can be \
used. Never write a CSS selector, an XPath, or element text as the id.
- One action at a time. Use "type" for text boxes, "click" for buttons and \
links, "select" for dropdowns.
- Take the shortest way. If the goal names something to find and the page has \
a search box, search for it first. Open a result only when the answer is not \
already on the page.
- Never repeat an action from "Already done" that did not help. If you are \
back on a page you have already seen, choose something different.
- Elements marked [overlay] are on top of the page: a dialog, a pop-up, a \
cookie notice. If it is what the goal needs (a sign-in or sign-up form), use \
it. If it is in the way, close it, preferring "Reject", "No thanks" or \
"Close" to accepting.
- Never open a help chat, an advert, a social media link or an app download.
- Keep reasoning to one short sentence, phrased for the person you are helping.
"""

#: Changed 2026-11-14 (Raham; the advisor's "tasks carried out on live sites,
#: not only read"): the model may now press the button that orders, books,
#: registers, applies or pays when the goal asks for it. It never presses it
#: unseen — the loop puts every such press on the final screen first, and a
#: payment page is then handed to the person (`loop.carry_out`). Until then
#: the rule read "never press a button that pays, orders, books, registers or
#: submits", and the AI planner could only find things.
OPEN_GOAL_RULES = """
When the page shows what the goal asks for, answer instead of acting: \
action "answer", element_id 0, value the answer copied exactly, word for word, \
from "What the page says" below — the answer itself and nothing round it (a \
price, a date, a time, a name, a confirmation). Copy only words that are \
there; never rephrase, add or calculate. In reasoning, write one short \
sentence that tells the person the answer and contains the value exactly as \
you copied it, like: Atomic Habits costs Rs. 3,221 on Readings. If the goal \
needs a search first, search first.
When the goal asks you to do something — order, book, register, apply, \
submit, pay — do it: fill in what is needed and press the button that does it. \
SIMBA shows the person what that button will do and presses it only if they \
say so, so press it when the form is ready. Once the page confirms it was \
done, answer with the confirmation copied word for word, with any order or \
reference number the page gives.
For the person's own details — name, address, phone, email, ID numbers — \
choose "type" with value null: the person types them. Use a value from the \
goal only if the goal gives it.
To make an account: fill in the form the same way; for every password box \
choose "type" with value null (SIMBA can make a strong password and keep it); \
tick a box agreeing to the website's terms when the form needs it (SIMBA asks \
the person first); then press the button that creates the account.
Never type card numbers, bank details, passwords or one-time codes: a payment \
page is handed to the person.
"""

#: How much of what the page says goes in the prompt. A free tier's tokens a
#: minute are the limit that bites (8,000 on Groq; EVALUATION.md, 2026-11-12).
CONTENT_CHARS = 2400
#: The most rows of one table put in the prompt.
TABLE_ROWS = 12


def render_content(content: Content | None, limit: int = CONTENT_CHARS) -> str:
    """What the page says, for the model: headings, labelled values and the
    first rows of each table, cut at `limit` characters."""
    if not content and not (content is not None and content.text):
        return "(the page says nothing readable)"
    lines: list[str] = []
    lines += [f"# {heading.text}" for heading in content.headings]
    lines += [f"{pair.label}: {pair.value}" for pair in content.pairs]
    lines += [value.text for value in content.values]
    for table in content.tables:
        if table.caption:
            lines.append(f"Table: {table.caption}")
        lines.append(" | ".join(table.headers))
        for row in table.rows[:TABLE_ROWS]:
            lines.append(" | ".join(row.values))
        if len(table.rows) > TABLE_ROWS:
            lines.append(f"(... {len(table.rows) - TABLE_ROWS} more rows)")
    # And the page's own text, in order, in whatever room is left (2026-11-14):
    # a confirmation's order number or a shop's price is often a plain
    # paragraph, in none of the parts above, and the model could not answer
    # with what it was never shown (EVALUATION.md, 2026-11-13h and -14a).
    text = "\n".join(line for line in lines if line.strip())
    if content.text:
        text = (text + "\n\n" if text else "") + "All the text, in order:\n" + content.text
    return text if len(text) <= limit else text[:limit] + "\n(... the rest is cut)"


# --- what runs by itself, and what stops (2026-11-14) --------------------------

#: A box for something about the person: theirs to type, never the model's to
#: make up, and asked for even when the goal gave it.
PERSONAL = re.compile(
    r"\b(name|e-?mail|phone|mobile|cell|contact|address|city|town|post ?code|postal|zip|"
    r"cnic|nic|passport|birth|dob|age|gender|user ?name|login|password|pin|card|cvv|iban|"
    r"account)\b", re.IGNORECASE)
#: A press that says yes for the person: cookies, notifications, a newsletter.
#: Theirs to choose, so asked (`voice.ASK_COOKIES` is the written plans' way).
CONSENT_WORDS = re.compile(
    r"\b(accept|allow|agree|consent|i understand|opt in|notify me|subscribe)\b", re.IGNORECASE)
#: A floating button for a help chat (2026-11-14). Perception marks one as an
#: overlay when it is all that is on top of a page still loading, and under
#: "dismiss the overlay first" the model's first move on Readings, in the real
#: window, was "Click Open help chat" (EVALUATION.md, 2026-11-14c). It is not
#: in the way of anything, and is never offered.
WIDGET_WORDS = re.compile(
    r"\b(chat|help ?desk|live help|whatsapp|messenger|feedback|support)\b", re.IGNORECASE)

#: Moves in a row that got nowhere before the run stops (Raham, 2026-11-14:
#: "no page change for 3 moves: stop and offer a helper").
STALL_LIMIT = 3
#: The same press, chosen again after it has twice been made: the third is not
#: made, unless each of the first two led somewhere new (a calendar's "Next").
REPEAT_LIMIT = 2
#: The longest one choice may take, every provider and retry included.
DECIDE_BUDGET_S = 45.0
#: The longest the read-back's sentence is waited for.
READ_BACK_BUDGET_S = 10.0


def without_widgets(elements: list[Element]) -> list[Element]:
    """`elements` without help-chat buttons; and, when one of those was all
    that was "covering" the page, with nothing behind an overlay any more."""
    widgets = {id(e) for e in elements if e.overlay and WIDGET_WORDS.search(e.label or "")}
    if not widgets:
        return elements
    rest = [e for e in elements if id(e) not in widgets]
    if any(e.overlay for e in rest):
        return rest
    return [replace(e, occluded=False) if e.occluded else e for e in rest]


def page_signature(elements: list[Element]) -> frozenset:
    """What tells one state of a page from another, for noticing a move that
    led nowhere: every element's role, words and place in the page's layers.
    Not positions, which a sliding banner changes by itself, nor values."""
    return frozenset((e.role, e.label, e.qualifier, e.panel, e.overlay) for e in elements)


def _said_in(value: str, text: str) -> bool:
    plain = lambda words: " ".join(str(words).lower().split())  # noqa: E731
    return bool(plain(value)) and plain(value) in plain(text)


def answer_sentence(value: str, sentence: str | None, goal: str) -> str | None:
    """The model's one sentence giving the answer, if it can be trusted with
    it: it holds the value exactly as the page says it, is one short sentence,
    and has no number in it that is neither in the value nor in the goal — so
    a figure the page does not show cannot ride in on it. None otherwise, and
    the answer is then shown by itself."""
    words = " ".join((sentence or "").split())
    if not words or value not in words or len(words) > 160 or "http" in words.lower():
        return None
    allowed = value + " " + goal
    rest = words.replace(value, " ")
    # One sentence: no full stop but the last, the value's own aside.
    if any(mark in rest.rstrip(".!? ") for mark in (". ", "! ", "? ")):
        return None
    if any(number not in allowed for number in re.findall(r"\d[\d,.]*\d|\d", rest)):
        return None
    return words if words[-1] in ".!?" else words + "."


READ_BACK_PROMPT = """A person typed a goal for a website. Say back, in ONE \
short plain sentence, what you will do for them there. Start with "I'll" and \
name the website by the name you are given. At most 20 words. No web address, \
no list of steps. If the goal orders, books, pays, registers or sends \
something, say so plainly.
Answer with action "answer", element_id 0, value that sentence, reasoning ""."""


async def restate(provider: Provider, goal: str, site: str) -> str | None:
    """The goal said back in one sentence — "I'll search Readings for Atomic
    Habits and tell you the price" — or None when no model gave a usable one
    in time: then the person's own words are read back (`voice.plain_read_back`)."""
    try:
        action = await asyncio.wait_for(provider.decide(
            READ_BACK_PROMPT, f"(No page is open yet. The website is called {site}.)", goal),
            READ_BACK_BUDGET_S)
    except (LLMError, asyncio.TimeoutError):
        return None
    words = " ".join((action.value or "").split())
    lowered = words.lower()
    if (action.action != "answer" or not words.startswith("I'll ") or len(words) > 170
            or "http" in lowered or "www." in lowered):
        return None
    return words


class OpenGoalPlanner(LLMPlanner):
    """The model on a goal with no plan: acts, or answers from the page.

    `answer` is the finding the run ends with; the loop shows it, rings it in
    the picture of the page, and checks the page still says it before closing
    (`loop.carry_out`). With `ask_answer` — the person asked to confirm every
    move — it is the answer only once they say it is what they wanted."""

    #: The model does not mark its own changes: a press whose words say it
    #: books, pays or submits is the loop's to stop (`loop.would_change`).
    marks_changes = False
    #: The run ends with an answer the page says, or not at all.
    must_answer = True
    #: A live page is read only once it has stopped arriving (`loop.settled`).
    waits_for_page = True
    #: What the loop says when two moves running did not work (2026-11-14), in
    #: place of the move's own words and the browser's: it stops and offers a
    #: helper, as when the planner notices it is going nowhere.
    no_progress = voice.AI_NO_PROGRESS

    def __init__(self, provider: Provider, task: Task, ask_answer: bool = True) -> None:
        super().__init__(provider, task)
        self._ask_answer = ask_answer
        self._content: Content | None = None
        self._proposed: str | None = None
        self._proposed_sentence: str | None = None
        self._declined: str | None = None
        self.answer: Finding | None = None
        #: The answer in one sentence, when the model gave one that holds
        #: (`answer_sentence`): the closing screen's explanation.
        self.answer_sentence: str | None = None
        #: Which provider worked out the last move: shown to the person.
        self.worked_out_by: str | None = None
        # Noticing a run that is going nowhere (2026-11-14).
        self._seen: set[frozenset] = set()
        self._before: frozenset | None = None
        self._made: tuple[str, str, str] | None = None
        self._typed: set[tuple[frozenset, tuple[str, str, str]]] = set()
        self._led: dict[tuple[str, str, str], list[bool]] = {}
        self._stalled = 0
        self._chosen: Counter = Counter()

    def look(self, content: Content) -> None:
        """What the page says now. The loop calls this before each move."""
        self._content = content

    def answered(self, action_id: str, values: dict) -> None:  # noqa: ARG002
        """The person's answer to "Is this what you wanted?"."""
        if self._proposed is None:
            return
        if action_id == voice.CONFIRM_ID:
            self.answer = Finding(label=voice.WHAT_I_FOUND, value=self._proposed)
            self.answer_sentence = self._proposed_sentence
        else:
            self._declined = self._proposed
        self._proposed = None

    # --- going nowhere -------------------------------------------------------

    def _weigh(self, now: frozenset, setback: str | None) -> None:
        """Whether the last move got anywhere, from the page as it is now."""
        made, before = self._made, self._before
        self._made = None
        if made is not None:
            if setback:
                got_on = False
            elif made[0] in ("type", "select"):
                # A box filled is progress once: the same box, on the same
                # page, with the page no different, is not.
                got_on = (before, made) not in self._typed or now not in self._seen
                self._typed.add((before, made))
            else:
                got_on = now not in self._seen
            self._led.setdefault(made, []).append(got_on)
            self._stalled = 0 if got_on else self._stalled + 1
        self._seen.add(now)
        self._before = now

    def _repeats(self, key: tuple[str, str, str]) -> bool:
        led = self._led.get(key, [])
        return len(led) >= REPEAT_LIMIT and not all(led)

    async def next_move(self, elements: list[Element], history: list[str],
                        setback: str | None) -> Move | None:
        if self.answer is not None:
            return None  # done: the loop closes with the answer
        elements = without_widgets(elements)
        self._note(setback)
        self._weigh(page_signature(elements), setback)
        if self._stalled >= STALL_LIMIT:
            self.stuck_reason = voice.AI_NO_PROGRESS
            return None
        if self._declined is not None:
            setback = (f'The person said "{self._declined}" is not what they wanted. '
                       "Keep looking, or do what the goal needs to find it.")
            self._declined = None
        elif self._stalled and not setback:
            setback = ("Your last action changed nothing, or brought you back to a page "
                       "you had already seen. Choose something different.")
        choice = await self._choose(elements, history, setback)
        self._chose(choice)
        self.worked_out_by = getattr(self._provider, "label", None)
        if choice is None:
            return None
        if choice.action.action == "answer":
            said = (choice.action.value or "").strip()
            sentence = answer_sentence(said, choice.action.reasoning, self._task.goal)
            if not self._ask_answer:
                # The page says it, word for word (`_choose`): the run ends
                # with it, as a built-in task ends with what it read.
                self.answer = Finding(label=voice.WHAT_I_FOUND, value=said)
                self.answer_sentence = sentence
                return None
            self._proposed, self._proposed_sentence = said, sentence
            return Move(instruction=voice.found_this(said), detail="", operations=[],
                        expect=Expectation(), fields=[], actions=voice.is_this_it(),
                        question=True, kind="read")
        key = (choice.action.action, choice.element.role, choice.element.label)
        if self._repeats(key):
            self.stuck_reason = voice.AI_NO_PROGRESS
            return None
        self._made = key
        return await self._shape(choice)

    # --- a move, in plain words, and whether it runs by itself --------------------

    async def _shape(self, choice: "_Choice") -> Move:
        action, element = choice.action, choice.element
        kind = "fill" if action.action == "type" else action.action
        label = _without_icons(element.label)
        personal = bool(PERSONAL.search(" ".join(filter(None, [label, element.name]))))
        value = action.value if kind in ("fill", "select") else None
        # The person's own details are theirs to give: a value the model made
        # up for one is dropped, and one the goal gave is shown in the box for
        # them to agree. A password is never the model's.
        given = bool(value) and _said_in(value, self._task.goal)
        if kind == "fill" and (element.is_password or (personal and not given)):
            value = None
        search = kind == "fill" and not personal and _is_search(element)
        asks = kind == "fill" and (value is None or personal)
        field_id = element.name or str(element.id)
        operation = Operation(kind=kind, target=Target(role=element.role, label=element.label),
                              element_id=element.id, value=value,
                              value_key=field_id if kind == "fill" else None)
        operations = [operation]
        if search:
            # Typing into a search box sends the search too (2026-11-14).
            operations.append(Operation(kind="press", target=operation.target,
                                        element_id=element.id, value="Enter"))
        fields = [StepField(
            id=field_id, label=voice.short_name(label) or element.label,
            type="password" if element.is_password else (element.input_type or "text"),
            value="" if element.is_password else (value or ""))] if asks else []
        instruction, doing = voice.plain_move(
            kind, element.role, label, None if asks else value, search=search,
            overlay=element.overlay, password=element.is_password)
        if kind == "click":
            safe = not (CHANGE_WORDS.search(label) or CONSENT_WORDS.search(label))
        else:
            safe = bool(value) and not asks and not personal
        return Move(
            instruction=instruction,
            detail=action.reasoning,
            operations=operations,
            # The model declares no expectation, so the bar is the general one:
            # the page must actually have changed. A typed value is checked by
            # reading the field back, in loop.attempt_move.
            expect=Expectation(),
            fields=fields,
            actions=voice.actions(voice.GO_AHEAD),
            safe=safe,
            doing=doing,
        )

    # --- asking the model ------------------------------------------------------

    async def _decide(self, system: str, page: str, feedback: str | None,
                      history: list[str] | None) -> Action:
        """One choice, in bounded time: a service that is slow tonight is an
        error to move on from, not a wait (`DECIDE_BUDGET_S`)."""
        try:
            return await asyncio.wait_for(super()._decide(system, page, feedback, history),
                                          DECIDE_BUDGET_S)
        except asyncio.TimeoutError as error:
            raise LLMError("no AI service answered in time") from error

    async def _choose(self, elements: list[Element], history: list[str],
                      setback: str | None) -> _Choice | None:
        """One action, retried once with the error fed back; an answer only
        if the page says it, word for word; an element only if it was listed."""
        feedback = setback
        valid = {element.id: element for element in usable(elements, self._failed)}
        page = (render_page(elements, self._failed, on_top=ON_TOP_BANNER)
                + "\n\nWhat the page says:\n" + render_content(self._content))
        unanswered = 0
        for _ in range(2):
            self.calls_made += 1
            try:
                action = await self._decide(OPEN_GOAL_SYSTEM + OPEN_GOAL_RULES, page,
                                            feedback, history)
            except LLMError as error:
                unanswered += 1
                feedback = str(error)
                continue
            if action.action == "answer":
                said = (action.value or "").strip()
                if said and self._content is not None and self._content.shows(said):
                    return _Choice(action=action, element=None)  # type: ignore[arg-type]
                feedback = (f'"{said}" is not on the page word for word. Copy the answer '
                            'exactly from "What the page says", or act to find it.')
                continue
            if action.element_id not in valid:
                feedback = (f"element_id {action.element_id} is not in the list. Choose an "
                            "id from the list of elements, exactly as it is numbered there.")
                continue
            return _Choice(action=action, element=valid[action.element_id])
        self.stuck_reason = voice.AI_TOO_SLOW if unanswered == 2 else voice.AI_COULD_NOT
        return None


class OpenGoalBrief:
    """What a goal with no plan asks before anything is touched (2026-11-14):
    one read-back, one yes. `loop.run_brief` asks it with the site already
    open, and then runs the planner this settles on.

    `reader` says the goal back in one sentence (`restate`); a quick model is
    enough for it. With none, or no usable sentence in time, the person's own
    words are read back."""

    gave_up: str | None = None

    def __init__(self, provider: Provider, goal: str, site_name: str, *,
                 steps: int, auto: bool = True, reader: Provider | None = None) -> None:
        self.goal = goal
        self.estimated_steps = steps
        self._provider = provider
        self._reader = reader
        self._site = site_name
        self._auto = auto
        self._sentence: str | None = None
        self._agreed = False
        self.planner: OpenGoalPlanner | None = None

    async def prepare(self, page) -> None:  # noqa: ARG002 - nothing on the page is read
        if self._reader is not None:
            self._sentence = await restate(self._reader, self.goal, self._site)

    def question(self) -> Move | None:
        if self._agreed:
            return None
        words = (voice.open_read_back(self._sentence) if self._sentence
                 else voice.plain_read_back(self.goal, self._site))
        return Move(instruction=words, detail=voice.READ_BACK_DETAIL, operations=[],
                    expect=Expectation(), fields=[], actions=voice.read_back_actions(),
                    question=True, kind="confirm")

    def answered(self, action_id: str, input_values: dict[str, str]) -> None:  # noqa: ARG002
        self._agreed = action_id == voice.CONFIRM_ID

    def settle(self) -> tuple[OpenGoalPlanner, Task]:
        task = Task(goal=self.goal, estimated_steps=self.estimated_steps, success=None,
                    about=About())
        # Asked to confirm every move: the answer is asked about too, as it
        # was until 2026-11-14.
        self.planner = OpenGoalPlanner(self._provider, task, ask_answer=not self._auto)
        return self.planner, task
