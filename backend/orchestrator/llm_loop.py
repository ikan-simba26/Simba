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
import logging
import re
from collections import Counter
from urllib.parse import urlsplit
from dataclasses import dataclass, replace

from backend.orchestrator import cards as cardlib
from backend.orchestrator import profile as profilelib
from backend.orchestrator.llm import Action, LLMError, Provider
from backend.orchestrator.loop import CHANGE_WORDS, Move, Task, is_stepping, resolve
from backend.orchestrator import voice
from backend.orchestrator.plan import About, Expectation, Operation, Target
from backend.perception.content import Content
from backend.perception.serializer import VIEWPORT, Element
from shared.schema import Detail, Finding, StepAction, StepField

log = logging.getLogger("simba.llm")

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


#: Roles of a box a person types or chooses in.
ENTRY_ROLES = ("textbox", "searchbox", "combobox", "spinbutton")


def echoes(elements: list[Element]) -> set[int]:
    """The ids of floating labels read as buttons (2026-11-17): a `<label>` that
    perception took for a button because the page makes it pointable, standing
    just before the very box it names (Daewoo's sign-up form has one before
    every box). Choosing one to type in cannot work and was how a CNIC step
    failed in the real window; the box itself is what is offered."""
    found: set[int] = set()
    for index, element in enumerate(elements[:-1]):
        if element.tag == "label" and element.role == "button":
            following = elements[index + 1]
            if following.role in ENTRY_ROLES or following.input_type in ("password", "text"):
                found.add(element.id)
    return found


def usable(elements: list[Element],
           failed: "set[tuple[str, str]] | frozenset[tuple[str, str]]" = frozenset()
           ) -> list[Element]:
    """The elements a planner is shown, and so may choose (2026-11-14): what
    `render_page` lists. Part of an overlay, or neither behind one, nor a link
    that goes nowhere, nor off the side, nor something that just failed."""
    echo = echoes(elements)
    return [e for e in elements if e.id not in echo and (e.overlay
            or (not (e.occluded or e.dead_link) and not _off_the_side(e)
                and (e.role, e.label) not in failed))]


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
    echo = echoes(elements)
    gone = {id(e) for e in aside + tried} | {id(e) for e in elements if e.id in echo}
    listed = [e for e in elements if id(e) not in gone and (e.overlay
              or not (e.occluded or e.dead_link))]

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

    # A box with no name of its own is named by the floating label just before
    # it (2026-11-17): Daewoo's city list was "combobox (no name)", and the model
    # went on to press Register without ever choosing one.
    named = {}
    for index, element in enumerate(elements[:-1]):
        if element.id in echo and not elements[index + 1].label.strip():
            named[elements[index + 1].id] = element.label
    for element in listed:
        name = _label(element.label or named.get(element.id, ""))
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
you copied it, like: The kettle costs Rs. 4,500. Never take the example's \
figures or format: the value is whatever the page shows, as it shows it. The \
answer must be about what the goal asked for: never a cart, basket or order total, \
and never a zero or empty value such as "Rs 0"; if the page shows only those, keep \
looking and open the item itself. If the goal \
needs a search first, search first: choose "type" on the website's search box \
(a text box) with the words to look for. A menu that only sets what to search by \
(Keyword, Title, Author, a category) is not the search box; leave it as it is.
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
When the page offers ways to pay (cash on delivery, card, bank transfer, a \
wallet), choose the one the goal names; if the goal names none, choose any one: \
SIMBA asks the person which they want.
Never type card numbers, bank details, passwords or one-time codes: a payment \
page is handed to the person.
When the goal does not say which option to use for a choice the website offers \
(a bus or train time, a class, a seat type, a size, a delivery option), never \
pick one yourself: choose action "ask" with the element_id of that dropdown, or \
of one of its options, and reasoning a short question for the person, like: \
Which class? SIMBA shows the website's own options and presses the one they pick.
Never add more than one item to a cart or a booking unless the goal says so.
When a search or list shows several results that fit the goal, never take the first one because it is first: SIMBA shows the matches and the person chooses. Read the whole page before choosing anything on it.
Before you press the button that sends a form, make sure every box and every drop-down list in it has been filled or chosen, the lists too (a city, a title). If a message on the page says something is missing, do that, not the message.
When the website says you must be signed in (a "session has expired", "please log in again", a "Re-login" or "Log in" button), do that first, with its own Log in button, before anything else: the person gives their details and password in SIMBA's own screens. Booking and buying sites usually need it, so sign in before you search.
If the form or button the goal needs (a search for a journey, a booking form, \
a cart) is not on the page, it may need the person to be signed in first: look \
for a "Sign In", "Login" or "Book" link or button and use it, before anything \
else. Never type into a box that is not for the goal (a refund status, a \
newsletter, a complaints form).
"""

#: A goal that does something (2026-11-17): the person is asked "Which one?"
#: before one of several matches is opened, never left to the model's pick.
DOING_GOAL = re.compile(
    r"\b(order|buy|purchase|reserve|get me|add .{0,30} to (my )?(cart|basket|bag)|"
    r"register|apply|sign up)\b|^\s*(please\s+)?book\b|"
    r"\bbook (me|us|a|an|my|the) (bus|train|flight|room|ticket|seat|table|hotel|doctor|"
    r"appointment|trip|car|taxi|slot)\b", re.IGNORECASE)
#: A page that is the cart, a checkout or a payment is not a list of choices.
NOT_A_LIST = re.compile(r"(cart|basket|bag|checkout|payment|order|pay|thank|confirm)", re.IGNORECASE)
#: A link or button that is the way into a booking or search the page hides.
WAY_IN = re.compile(r"\b(sign ?in|log ?in|book(ing)?|reserve|buy ticket|my account)\b", re.IGNORECASE)
CARD_ID_PREFIX = "card:"
OPTION_ID_PREFIX = "opt:"
#: A page saying the person has to be signed in.
LOGIN_NEEDED = re.compile(
    r"(session (has )?expired|log ?in again|sign ?in again|please (log ?in|sign ?in)|"
    r"you (must|need to) (be )?(logged|signed) ?in|login required)", re.IGNORECASE)
#: A box that holds a date, by its words, and the shape a box shows for one.
DATE_BOX = re.compile(r"(\bdate\b|birth|\bdob\b|dd.?mm.?yy|mm.?dd.?yy|yyyy.?mm)", re.IGNORECASE)
DATE_SHAPE = re.compile(r"(dd.?mm.?yy|mm.?dd.?yy|yyyy.?mm.?dd)", re.IGNORECASE)
#: The most options of one choice put in front of the person.
MOST_OPTIONS = 10
_OPTIONS_JS = """e => {
  const label = r => { const l = (r.labels && r.labels[0]) ? r.labels[0] : r.closest('label');
    return ((l ? l.innerText : '') || r.value || r.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim(); };
  if (e.tagName === 'SELECT')
    return [...e.options].filter(o => !o.disabled && o.value !== '' && o.text.trim())
      .map(o => o.text.replace(/\\s+/g, ' ').trim());
  if (e.type === 'radio' && e.name)
    return [...document.querySelectorAll('input[type=radio]')].filter(r => r.name === e.name)
      .map(label).filter(Boolean);
  return [];
}"""
CART_GO_ID = "cart:go"

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
#: A way of paying a page offers (2026-11-16). Not "pay now" or "place order":
#: those are the press that finishes, not a way to pay.
PAYMENT_METHOD = re.compile(
    r"(cash on delivery|cash on delievery|\bcod\b|pay (online|by card|with card|on delivery|"
    r"at the door|later)|credit card|debit card|card payment|bank transfer|easypaisa|"
    r"jazz ?cash|wallet|raast|safepay)", re.IGNORECASE)
#: Roles that are a choice among ways, not a button that finishes.
METHOD_ROLES = {"radio", "checkbox", "option", "tab", "menuitemradio"}


def is_payment_method(element: Element) -> bool:
    """Whether an element is one of the ways of paying a page offers."""
    return bool(PAYMENT_METHOD.search(element.label or "")) and (
        element.role in METHOD_ROLES or element.role in ("button", "link"))


def names_a_method(goal: str) -> bool:
    """Whether the goal already says how to pay: "cash on delivery", "by card"."""
    return bool(PAYMENT_METHOD.search(goal) or re.search(r"\b(cash|card|online)\b", goal, re.I))


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


#: Words of a goal that say what to do or are filler, not what it is about.
GOAL_FILLER = {
    "order", "buy", "purchase", "book", "books", "reserve", "please", "get", "for", "the", "and",
    "with", "from", "ticket", "tickets", "online", "want", "need", "would", "like", "can", "you",
    "that", "this", "some", "any", "one", "cash", "delivery", "card", "pay", "payment", "register",
    "apply", "sign", "new", "find", "show", "give", "bus", "train", "flight", "seat", "seats",
    "shop", "store", "bookshop", "bookstore", "website", "site", "page", "them", "your", "into",
    "just", "tell", "make", "also", "have", "will", "when", "what", "which",
}


def goal_words(goal: str) -> list[str]:
    """What a goal is about: its longer words that are not filler."""
    return [w for w in re.findall(r"[a-z0-9]{4,}", (goal or "").lower()) if w not in GOAL_FILLER]


MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december"]


def goal_date(goal: str, shape: str = "", today=None) -> str | None:
    """The one exact date a goal names, written the way a box shows it (`shape`
    like "dd-MM-yyyy"), else as 2026-11-21. None when the goal names no date,
    or names one that has passed or is not in the calendar.

    One reader for every date (`details.find_day`): "21 November", "November
    21st 2027", "21 Nov", "tomorrow", "next Friday", "21/11", "2026-11-21".
    A year in the goal is kept (B1, 2026-11-18: "5 January 2028" was typed as
    2027); with no year it is the next time that day comes. Worked out from
    today's date before anything is typed, and never a day that has gone."""
    import datetime

    from backend.orchestrator.details import find_day

    today = today or datetime.date.today()
    when, _ = find_day(goal or "", today)
    if when is None or when < today:
        return None
    sep = next((c for c in shape if c in "-/."), "-")
    lowered = shape.lower()
    if lowered.startswith("dd"):
        return f"{when.day:02d}{sep}{when.month:02d}{sep}{when.year}"
    if lowered.startswith("mm"):
        return f"{when.month:02d}{sep}{when.day:02d}{sep}{when.year}"
    if lowered.startswith("yy"):
        return f"{when.year}{sep}{when.month:02d}{sep}{when.day:02d}"
    return when.isoformat()


def cards_about(cards: "list[cardlib.Card]", goal: str, site_words: set[str]
                ) -> "list[cardlib.Card]":
    """The cards that are about what the goal asks for, the ones that say the
    most of its words first. The website's own name is no topic (B5): "an
    alchemist book on Readings" is about "alchemist", and "(Readings Classics)"
    says nothing about it. No topic word in the goal means no card is about it."""
    words = [w for w in goal_words(goal) if w not in site_words]
    about = [c for c in cards if words and any(w in _plain(c.name) for w in words)]
    return sorted(about, key=lambda c: -sum(w in _plain(c.name) for w in words))


def _plain(text: str) -> str:
    return " ".join(re.sub(r"[^\w ]+", " ", (text or "").lower()).split())


def _control_for(card: "cardlib.Card", elements: list[Element]) -> Element | None:
    """The element a card is pressed by: a link or button whose words are the
    card's control text, the nearest to where the page had it."""
    wanted = _plain(card.link_text or card.name)
    if not wanted:
        return None
    candidates = [e for e in elements if e.role in ("link", "button")
                  and _plain(_without_icons(e.label))
                  and (wanted in _plain(_without_icons(e.label))
                       or _plain(_without_icons(e.label)) in wanted)]
    if not candidates:
        return None
    if card.link_rect is None or len(candidates) == 1:
        return candidates[0]
    cx = card.link_rect[0] + card.link_rect[2] / 2
    cy = card.link_rect[1] + card.link_rect[3] / 2

    def distance(element: Element) -> float:
        if element.rect is None:
            return float("inf")
        x, y, w, h = element.rect
        return abs(x + w / 2 - cx) + abs(y + h / 2 - cy)

    return min(candidates, key=distance)


#: A press that sends a form on, by its words (B4, 2026-11-18).
SENDS_FORM = re.compile(
    r"\b(submit|register|sign ?up|create( an| my)? account|continue|next|place order|send|apply|"
    r"confirm|checkout|check out|proceed|save)\b", re.IGNORECASE)

#: The required boxes of a button's form that are still empty, by their labels.
_EMPTY_REQUIRED_JS = """e => {
  const form = e.closest('form');
  if (!form) return [];
  const seen = x => { const r = x.getBoundingClientRect(), s = getComputedStyle(x);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const name = x => ((x.labels && x.labels[0] ? x.labels[0].innerText : '')
    || x.getAttribute('aria-label') || x.placeholder || x.name || x.type || '')
    .replace(/\\s+/g, ' ').trim().slice(0, 40);
  const out = [];
  for (const x of form.querySelectorAll('input, select, textarea')) {
    if (['hidden', 'submit', 'button', 'image', 'reset'].includes(x.type) || x.disabled) continue;
    if (!(x.required || x.getAttribute('aria-required') === 'true') || !seen(x)) continue;
    let empty;
    if (x.type === 'checkbox') empty = !x.checked;
    else if (x.type === 'radio') empty = !form.querySelector('input[type=radio][name="' + CSS.escape(x.name) + '"]:checked');
    else empty = !(x.value || '').trim();
    if (empty) out.push(name(x));
  }
  return [...new Set(out)].slice(0, 8);
}"""


async def empty_required_boxes(locator) -> list[str]:
    """The required boxes still empty in the form this button belongs to, by
    their labels; empty when it is in no form, or all are filled (B4)."""
    try:
        return list(await locator.evaluate(_EMPTY_REQUIRED_JS, timeout=3000) or [])
    except Exception:  # noqa: BLE001 - a page that will not say: the page's own check decides
        return []


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

    def __init__(self, provider: Provider, task: Task, ask_answer: bool = True,
                 notes: str = "") -> None:
        super().__init__(provider, task)
        self._ask_answer = ask_answer
        #: How this website works, in a few plain lines (`data/catalogue.json`,
        #: 2026-11-18): written from live runs, given to the model with the goal.
        self.notes = notes
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
        self._opened = False
        self._was_on_top = False
        # Which way to pay, when the page offers several (2026-11-16): asked once.
        self._method_asked = False
        self._method_options: dict[str, Element] = {}
        self._method_chosen: Element | None = None
        # "Which one?" (2026-11-17), the one-item rule and the cart check.
        self.page = None
        self._asked_which = False
        #: The address whose page was scrolled to load all of it (B4).
        self._scrolled_page = ""
        #: Times a form was held back for an empty required box (B4).
        self._form_checks = 0
        self._card_options: dict[str, cardlib.Card] = {}
        self._card_chosen: cardlib.Card | None = None
        self._added = 0
        self._pending_add = False
        self._cart_asked = False
        self._cart_ok = False
        self._new_facts: list[Detail] = []
        # A choice the site offers, asked of the person (2026-11-17).
        self._site_options: dict[str, str] = {}
        self._site_question: str = ""
        self._site_element: Element | None = None
        self._site_chosen: tuple[Element, str] | None = None

    def attach(self, page) -> None:
        """The page, for what only the page can say: the cards of a list and
        what a cart holds (`cards.py`). Called by the loop."""
        self.page = page

    def take_facts(self) -> list[Detail]:
        """What the person chose since last asked, for the final screen."""
        facts, self._new_facts = self._new_facts, []
        return facts

    def look(self, content: Content) -> None:
        """What the page says now. The loop calls this before each move."""
        self._content = content

    def answered(self, action_id: str, values: dict) -> None:  # noqa: ARG002
        """The person's answer to "Is this what you wanted?", or to "How do you
        want to pay?"."""
        if action_id in self._method_options:
            self._method_chosen = self._method_options[action_id]
            self._method_options = {}
            self._new_facts.append(Detail(
                label=voice.FACT_PAYING,
                value=voice.short_name(_without_icons(self._method_chosen.label))
                or self._method_chosen.label))
            return
        if action_id in self._card_options:
            self._card_chosen = self._card_options[action_id]
            self._card_options = {}
            self._new_facts.append(Detail(label=voice.FACT_CHOSEN, value=" - ".join(
                part for part in (self._card_chosen.name, self._card_chosen.price) if part)))
            return
        if action_id in self._site_options:
            chosen = self._site_options[action_id]
            if self._site_element is not None:
                self._site_chosen = (self._site_element, chosen)
                self._new_facts.append(Detail(
                    label=voice.short_name(self._site_question.rstrip("? ")) or voice.FACT_CHOSEN,
                    value=chosen))
            self._site_options = {}
            return
        if action_id == CART_GO_ID:
            self._cart_ok = True
            return
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
        # Whether the last press put something on top of the page that was
        # not there before it: a dialog this run opened itself.
        on_top = any(e.overlay for e in elements)
        self._opened = bool(self._made and self._made[0] == "click" and on_top
                            and not self._was_on_top and not setback)
        self._was_on_top = on_top
        self._weigh(page_signature(elements), setback)
        if self._stalled >= STALL_LIMIT:
            self.stuck_reason = voice.AI_NO_PROGRESS
            return None
        if (self._content is not None and LOGIN_NEEDED.search(self._content.text or "")
                and not setback):
            # The page itself says so (Pakistan Railways, 2026-11-17: "Your session has
            # expired. Please log in again!" over a booking that could not go on).
            setback = ("The website says you must log in. Use its Log in or Re-login "
                       "button now, before anything else.")
        if self._declined is not None:
            setback = (f'The person said "{self._declined}" is not what they wanted. '
                       "Keep looking, or do what the goal needs to find it.")
            self._declined = None
        elif self._stalled and not setback:
            setback = ("Your last action changed nothing, or brought you back to a page "
                       "you had already seen. Choose something different.")
        if self._method_chosen is not None:
            # The person chose how to pay: press that, on the page as it is now.
            wanted, self._method_chosen = self._method_chosen, None
            now = next((e for e in usable(elements, self._failed)
                        if e.label == wanted.label and e.role == wanted.role), None)
            if now is not None:
                self._made = ("click", now.role, now.label)
                return await self._shape(_Choice(
                    action=Action(action="click", element_id=now.id,
                                  reasoning="This is the way you chose to pay."),
                    element=now))
        if self._pending_add:
            self._pending_add = False
            if not setback:
                self._added += 1
        if self._site_chosen is not None:
            # The person chose among the site's own options: do that.
            wanted, text = self._site_chosen
            self._site_chosen = None
            if wanted.role == "option":
                option = next((e for e in usable(elements, self._failed)
                               if e.role == "option"
                               and _plain(_without_icons(e.label)) == _plain(text)), None)
                if option is not None:
                    self._made = ("click", option.role, option.label)
                    return await self._shape(_Choice(
                        action=Action(action="click", element_id=option.id,
                                      reasoning="This is the one you chose."), element=option))
            now = next((e for e in usable(elements, self._failed)
                        if (e.role, e.label) == (wanted.role, wanted.label)), None)
            if now is not None:
                if now.role == "radio":
                    option = next((e for e in usable(elements, self._failed)
                                   if e.role == "radio" and _plain(e.label) == _plain(text)), None)
                    action = Action(action="click", element_id=(option or now).id,
                                    reasoning="This is the one you chose.")
                    self._made = ("click", (option or now).role, (option or now).label)
                    return await self._shape(_Choice(action=action, element=option or now))
                self._made = ("select", now.role, now.label)
                return await self._shape(_Choice(
                    action=Action(action="select", element_id=now.id, value=text,
                                  reasoning="This is the one you chose."), element=now))
        if self._card_chosen is not None:
            # The person chose one of the cards: press that one, and only it.
            wanted, self._card_chosen = self._card_chosen, None
            now = _control_for(wanted, usable(elements, self._failed))
            if now is not None:
                self._made = ("click", now.role, now.label)
                return await self._shape(_Choice(
                    action=Action(action="click", element_id=now.id,
                                  reasoning="This is the one you chose."),
                    element=now))
        which = await self._which_one(elements, on_top)
        if which is not None:
            return which
        choice = await self._choose(elements, history, setback)
        self._chose(choice)
        self.worked_out_by = getattr(self._provider, "label", None)
        if choice is None:
            return None
        dated = self._date_box(choice, elements)
        if dated is not None:
            return await dated
        selecting = await self._select_box(choice, elements)
        if selecting is not None:
            return selecting
        if choice.action.action == "ask":
            asking = await self._ask_site(choice, elements)
            if asking is not None:
                return asking
            # An open list of suggestions or matches (Wikipedia's "The Alchemist" has a
            # novel, a play and a film): its own options, asked as buttons, and the
            # one chosen is pressed (2026-11-18).
            open_list = [e for e in usable(elements, self._failed)
                         if e.role == "option" and _without_icons(e.label).strip()]
            labels = list(dict.fromkeys(_without_icons(e.label).strip() for e in open_list))
            if len(labels) >= 2:
                labels = labels[:MOST_OPTIONS]
                question = (choice.action.reasoning or "").strip()
                if not question.endswith("?"):
                    question = voice.WHICH_ONE
                self._site_question = question
                self._site_element = open_list[0]
                self._site_options = {f"{OPTION_ID_PREFIX}{i}": text for i, text in enumerate(labels)}
                actions = [StepAction(id=key, label=text, kind="primary")
                           for key, text in self._site_options.items()]
                actions.append(StepAction(id=voice.CANCEL_ID, label=voice.STOP, kind="secondary"))
                return Move(instruction=question, detail=voice.WHICH_ONE_SITE, operations=[],
                            expect=Expectation(), fields=[], actions=actions, question=True,
                            kind="choose")
            # Several results the model cannot choose among (a list of ads, not a
            # drop-down): shown as "Which one?" cards, for a look-up too (PakWheels,
            # 2026-11-18: "Find a used Suzuki Alto" stopped with "I couldn't work out").
            listed = await self._which_one(elements, any(e.overlay for e in elements), force=True)
            if listed is not None:
                return listed
            self.stuck_reason = voice.AI_COULD_NOT
            return None
        checking = await self._cart_check(choice)
        if checking is not None:
            return checking
        if (choice.element is not None and not self._method_asked
                and is_payment_method(choice.element) and not names_a_method(self._task.goal)):
            self._method_asked = True
            ways: dict[str, Element] = {}
            for element in usable(elements, self._failed):
                if is_payment_method(element) and element.label not in {
                        w.label for w in ways.values()}:
                    ways[voice.PAY_ID_PREFIX + str(element.id)] = element
            if len(ways) >= 2:
                self._method_options = ways
                actions = [StepAction(id=key, label=voice.short_name(_without_icons(e.label))
                                      or e.label, kind="primary") for key, e in ways.items()]
                actions.append(StepAction(id=voice.CANCEL_ID, label=voice.STOP, kind="secondary"))
                return Move(instruction=voice.PAY_HOW, detail=voice.PAY_HOW_DETAIL,
                            operations=[], expect=Expectation(), fields=[], actions=actions,
                            question=True, kind="choose")
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
        if (choice.action.action == "click"
                and cardlib.ADD_WORDS.search(_without_icons(choice.element.label))):
            self._pending_add = True
        return await self._shape(choice)

    # --- "Which one?", one item, and the cart (2026-11-17) --------------------------

    async def _site_words(self) -> set[str]:
        """The words that name this website (its address and the start of its
        title): they say where, never what, so they never pick a card."""
        host = urlsplit(self.page.url).netloc.lower() if self.page is not None else ""
        words = set(re.findall(r"[a-z0-9]{4,}", host))
        try:
            title = (await self.page.title()).lower().split(" - ")[0].split(" | ")[0]
        except Exception:  # noqa: BLE001 - a page with no title: the address is enough
            title = ""
        return words | set(re.findall(r"[a-z0-9]{4,}", title))

    async def _which_one(self, elements: list[Element], on_top: bool,
                         force: bool = False) -> Move | None:
        """Several matches on the page, and the goal does something with one of
        them: the person chooses, as cards. Once per run, on a list page only,
        and never after something is in the cart."""
        if (self.page is None or self._asked_which or self._added or on_top
                or not (force or DOING_GOAL.search(self._task.goal))
                or NOT_A_LIST.search(urlsplit(self.page.url).path or "")):
            return None
        # The whole page is read first (lazy tiles load as it scrolls), and every
        # tile is looked at before the goal's words choose among them (B4).
        if self._scrolled_page != self.page.url:
            self._scrolled_page = self.page.url
            await cardlib.read_whole_page(self.page)
        found = await cardlib.find_cards(self.page)
        if len(found) < 2:
            return None
        usable_now = usable(elements, self._failed)
        # Only the ones about what was asked for: a shop's front page lists
        # its own picks, which are not matches (Readings, 2026-11-17). The
        # website's own name is not a topic: "alchemist book on Readings" must
        # not match "(Readings Classics)" (B5, 2026-11-18).
        about = cards_about(found, self._task.goal, await self._site_words())
        reachable = [c for c in about if _control_for(c, usable_now) is not None]
        if len(reachable) < 2:
            return None
        reachable = reachable[:cardlib.SHOW_CARDS]
        self._asked_which = True
        pictures = await cardlib.pictures(self.page, reachable)
        options: dict[str, cardlib.Card] = {}
        actions: list[StepAction] = []
        for card, picture in zip(reachable, pictures):
            key = f"{CARD_ID_PREFIX}{card.index}"
            options[key] = card
            actions.append(StepAction(id=key, label=card.name, kind="primary",
                                      sub=card.price or None, picture=picture))
        self._card_options = options
        actions.append(StepAction(id=voice.CANCEL_ID, label=voice.STOP, kind="secondary"))
        return Move(instruction=voice.WHICH_ONE, detail=voice.WHICH_ONE_DETAIL, operations=[],
                    expect=Expectation(), fields=[], actions=actions, question=True,
                    kind="choose")

    def _date_box(self, choice: "_Choice", elements: list[Element]):
        """A box for a date (2026-11-17), however the model tried to use it. A
        date picker's box is read-only, so pressing it shows a calendar nobody
        can use well: the person types the date, in the shape the box shows
        ("25-03-1998"), and SIMBA sets it. Returns the move to await, or None."""
        el = choice.element
        if el is None or el.role != "textbox" or choice.action.action not in (
                "click", "type", "select"):
            return None
        index = next((i for i, e in enumerate(elements) if e.id == el.id), 0)
        before = elements[index - 1] if index else None
        name = (_without_icons(before.label) if before is not None and before.tag == "label"
                else "")
        said = f"{el.label} {name} {el.name or ''}"
        birth = profilelib.kind_of(name or el.label, el.name) == "dob"
        # A press on a date box, or any move on a date of birth, is the person's to
        # type; a date the goal gave, typed by the model, is left alone.
        if not (birth or (DATE_BOX.search(said) and choice.action.action == "click")):
            return None
        shape = el.label if DATE_SHAPE.search(el.label or "") else ""
        label = f"{name or voice.DATE_WORD} ({shape})" if shape else (name or voice.DATE_WORD)
        asked = replace(el, label=label)
        self._made = ("fill", el.role, el.label)
        # A date the goal itself names is typed, in the box's own shape; a date
        # of birth, or none named, is the person's.
        named = None if birth else goal_date(self._task.goal, shape)
        return self._shape(_Choice(
            action=Action(action="type", element_id=el.id, value=named,
                          reasoning=voice.TYPE_DATE), element=asked))

    async def _select_box(self, choice: "_Choice", elements: list[Element]) -> Move | None:
        """A drop-down list (2026-11-17), however the model tried to use it —
        pressed, typed in, or chosen from. Pressing one does nothing the page
        shows ("Choose Please Select City did not work"), so it is always a
        choice among the list's own options: made by itself when the goal or
        a kept detail names one of them; else asked, as buttons when there are
        a few, or as a box that accepts only the list's own words when there
        are many (a city among 128)."""
        el = choice.element
        if (self.page is None or el is None or el.tag != "select"
                or choice.action.action not in ("click", "select", "type", "ask")):
            return None
        try:
            found = await resolve(self.page, elements, el.id).evaluate(_OPTIONS_JS, timeout=3000)
        except Exception:  # noqa: BLE001 - not a list we can read: left to the model
            return None
        options = [o for o in dict.fromkeys(found or []) if o]
        if len(options) < 2:
            return None
        index = next((i for i, e in enumerate(elements) if e.id == el.id), 0)
        before = elements[index - 1] if index else None
        name = _without_icons(el.label) or (_without_icons(before.label) if before is not None
                                            and before.tag == "label" else "") or el.name or "one"
        plain_options = {_plain(o): o for o in options}

        def option_for(text: str | None) -> str | None:
            return plain_options.get(_plain(text or "")) if text else None

        chosen = option_for(choice.action.value) if choice.action.action in ("select", "type") \
            else None
        if chosen is not None and not _said_in(chosen, self._task.goal):
            # The model's own pick, not the goal's: only for a list that is not
            # about the person (a size, a class) is that its call; a city or
            # anything of theirs is asked.
            if profilelib.kind_of(name, el.name) is not None:
                chosen = None
        detail = profilelib.kind_of(name, el.name)
        if chosen is None and detail is not None:
            saved = option_for(profilelib.ProfileVault().get(detail))
            if saved is not None:
                chosen = saved
                self.keep_private([saved])
        if chosen is not None:
            self._new_facts.append(Detail(label=voice.short_name(name) or name, value=chosen))
            self._made = ("select", el.role, el.label)
            return await self._shape(_Choice(
                action=Action(action="select", element_id=el.id, value=chosen,
                              reasoning="This is the one that fits."), element=el))
        question = voice.which_named(voice.short_name(name) or name)
        if len(options) <= MOST_OPTIONS:
            self._site_question = question
            self._site_element = el
            self._site_options = {f"{OPTION_ID_PREFIX}{i}": text for i, text in enumerate(options)}
            actions = [StepAction(id=key, label=text, kind="primary")
                       for key, text in self._site_options.items()]
            actions.append(StepAction(id=voice.CANCEL_ID, label=voice.STOP, kind="secondary"))
            return Move(instruction=question, detail=voice.WHICH_ONE_SITE, operations=[],
                        expect=Expectation(), fields=[], actions=actions, question=True,
                        kind="choose")
        # Many options: a box that takes only the list's own words.
        field_id = el.name or str(el.id)
        actions = voice.actions(voice.GO_AHEAD)
        kinds: tuple = ()
        if detail is not None:
            kinds = ((field_id, detail),)
            if profilelib.ProfileVault().available:
                actions = [actions[0], StepAction(id=voice.REMEMBER_ID,
                                                  label=voice.REMEMBER_DETAIL, kind="primary"),
                           *actions[1:]]
        self._made = ("select", el.role, el.label)
        return Move(
            instruction=question, detail=voice.TYPE_AND_PICK, kind="choose",
            operations=[Operation(kind="select", target=Target(role=el.role, label=el.label),
                                  element_id=el.id, value=None, value_key=field_id,
                                  node=el.backend_node_id)],
            expect=Expectation(),
            fields=[StepField(id=field_id, label=voice.short_name(name) or name, type="text",
                              value="", options=options)],
            actions=actions, kinds=kinds)

    async def _ask_site(self, choice: "_Choice", elements: list[Element]) -> Move | None:
        """The model says a choice is the person's: read the site's own
        options for it and ask, as buttons."""
        if self.page is None or choice.element is None:
            return None
        try:
            found = await resolve(self.page, elements, choice.element.id).evaluate(
                _OPTIONS_JS, timeout=3000)
        except Exception:  # noqa: BLE001 - nothing to ask about
            return None
        options = [o for o in dict.fromkeys(found or []) if o][:MOST_OPTIONS]
        if len(options) < 2:
            return None
        question = (choice.action.reasoning or "").strip()
        if not question.endswith("?"):
            question = voice.WHICH_ONE
        self._site_question = question
        self._site_element = choice.element
        self._site_options = {f"{OPTION_ID_PREFIX}{i}": text for i, text in enumerate(options)}
        actions = [StepAction(id=key, label=text, kind="primary")
                   for key, text in self._site_options.items()]
        actions.append(StepAction(id=voice.CANCEL_ID, label=voice.STOP, kind="secondary"))
        return Move(instruction=question, detail=voice.WHICH_ONE_SITE, operations=[],
                    expect=Expectation(), fields=[], actions=actions, question=True,
                    kind="choose")

    async def _cart_check(self, choice: "_Choice") -> Move | None:
        """About to start checking out with more in the cart than the goal
        asked for: say so first, once."""
        if (self.page is None or self._cart_asked or self._cart_ok or choice.element is None
                or choice.action.action != "click"
                or cardlib.goal_wants_many(self._task.goal)
                or not cardlib.CHECKOUT_WORDS.search(_without_icons(choice.element.label))):
            return None
        cart = await cardlib.read_cart(self.page)
        if cart is None or cart.things <= 1:
            return None
        self._cart_asked = True
        self._new_facts.append(Detail(label=voice.FACT_IN_CART, value=str(cart.things)))
        actions = voice.actions(voice.CART_GO_ON)
        actions[0] = StepAction(id=CART_GO_ID, label=voice.CART_GO_ON, kind="primary")
        return Move(instruction=voice.cart_has(cart.things), detail="; ".join(cart.names[:3]),
                    operations=[], expect=Expectation(), fields=[], actions=actions,
                    question=True, kind="confirm")

    # --- a move, in plain words, and whether it runs by itself --------------------

    async def _shape(self, choice: "_Choice") -> Move:
        action, element = choice.action, choice.element
        kind = "fill" if action.action == "type" else action.action
        label = _without_icons(element.label)
        # A search box is for the goal's words, whatever else its label says: OLX's own is
        # "Find Cars, Mobile Phones and more", which is no request for a phone number.
        personal = (bool(PERSONAL.search(" ".join(filter(None, [label, element.name]))))
                    and not _is_search(element))
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
        # The person's own details (2026-11-17): a box for a name, a CNIC, a
        # phone, an email, an address or a city is filled from what they chose
        # to keep on this computer, by SIMBA, and never by the model. Not kept
        # yet: asked in its own screen, with a way to keep it.
        detail = (profilelib.kind_of(label, element.name, element.input_type)
                  if kind == "fill" and not element.is_password and not given
                  and not _is_search(element) else None)
        remembered = None
        if detail is not None and asks:
            remembered = profilelib.ProfileVault().get(detail)
        if remembered:
            value, asks, search = remembered, False, False
            self.keep_private([remembered])
            self._new_facts.append(Detail(label=voice.short_name(label) or label, value=remembered))
        operation = Operation(kind=kind, target=Target(role=element.role, label=element.label),
                              element_id=element.id, value=value,
                              value_key=field_id if kind == "fill" else None,
                              node=element.backend_node_id)
        operations = [operation]
        if search:
            # Typing into a search box sends the search too (2026-11-14).
            operations.append(Operation(kind="press", target=operation.target,
                                        element_id=element.id, value="Enter",
                                        node=element.backend_node_id))
        fields = [StepField(
            id=field_id, label=voice.short_name(label) or element.label,
            type="password" if element.is_password else (element.input_type or "text"),
            value="" if element.is_password else (value or ""))] if asks else []
        instruction, doing = voice.plain_move(
            kind, element.role, label, None if asks else value, search=search,
            overlay=element.overlay, password=element.is_password)
        actions = voice.actions(voice.GO_AHEAD)
        kinds: tuple = ()
        if remembered:
            said = profilelib.WORDS.get(detail, "this")
            instruction, doing = voice.typing_detail(said), voice.typing_detail_doing(said)
        elif asks and detail is not None:
            kinds = ((field_id, detail),)
            said = profilelib.WORDS.get(detail, "this")
            instruction = voice.ask_detail(said)
            if profilelib.ProfileVault().available:
                actions = [actions[0], StepAction(id=voice.REMEMBER_ID,
                                                  label=voice.REMEMBER_DETAIL, kind="primary"),
                           *actions[1:]]
        if kind == "click":
            # A press that only moves a purchase on is a checklist line; the
            # loop still checks the page before believing it (`only_moves_on`).
            safe = not ((CHANGE_WORDS.search(label) and not is_stepping(label))
                        or CONSENT_WORDS.search(label))
        elif remembered:
            safe = True
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
            actions=actions,
            safe=safe,
            doing=doing,
            kinds=kinds,
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

    def _site_notes(self) -> str:
        """The catalogue's notes on this website, as the end of the prompt. The
        page itself always wins over them: a website changes."""
        if not self.notes:
            return ""
        return ("\n\nWhat is known about this website, from earlier tries (the page in front of "
                "you wins if it differs):\n" + self.notes)

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
                action = await self._decide(OPEN_GOAL_SYSTEM + OPEN_GOAL_RULES + self._site_notes(), page,
                                            feedback, history)
            except LLMError as error:
                unanswered += 1
                feedback = str(error)
                log.info("AI choice refused: no usable reply (%.60s)", feedback)
                continue
            if action.action == "answer":
                said = (action.value or "").strip()
                if said and self._content is not None and self._content.shows(said):
                    return _Choice(action=action, element=None)  # type: ignore[arg-type]
                log.info("AI choice refused: its answer is not on the page word for word")
                feedback = (f'"{said}" is not on the page word for word. Copy the answer '
                            'exactly from "What the page says", or act to find it.')
                continue
            if action.element_id not in valid:
                log.info("AI choice refused: %s element %s is not in the list", action.action, action.element_id)
                feedback = (f"element_id {action.element_id} is not in the list. Choose an "
                            "id from the list of elements, exactly as it is numbered there.")
                # A page with no form yet (Daewoo's search needs a sign-in): name
                # the way in, from what is listed (2026-11-17).
                ways = [f"{e.id}. {e.role} {_label(e.label)!r}" for e in usable(elements, self._failed)
                        if e.role in ("link", "button") and WAY_IN.search(e.label or "")][:3]
                if ways:
                    feedback += (" The page shows no form for the goal yet. It may need a sign-in "
                                 "or a booking page first: " + "; ".join(ways) + ".")
                continue
            chosen = valid[action.element_id]
            if (action.action == "type" and not DOING_GOAL.search(self._task.goal)
                    and not _is_search(chosen) and not chosen.is_password
                    and profilelib.kind_of(_without_icons(chosen.label), chosen.name,
                                           chosen.input_type) is not None):
                # A look-up needs none of the person's details (Chughtai Lab,
                # 2026-11-18: their email was typed into the page's newsletter box).
                log.info("AI choice refused: a look-up typing the person's details")
                feedback = ("The goal only looks something up. Never type the person's name, "
                            "email, phone or address into a box (a newsletter box, a contact "
                            "form). Use the website's search box or its links to find it.")
                continue
            if (self._added and action.action == "click"
                    and cardlib.ADD_WORDS.search(_without_icons(chosen.label))
                    and not cardlib.goal_wants_many(self._task.goal)):
                # One item, unless the goal asked for more (2026-11-17): on
                # Readings two matching books went into the cart.
                log.info("AI choice refused: a second add to the cart")
                feedback = ("One item is already in the cart and the goal asks for one. "
                            "Never add another. Go on to the cart and check out.")
                continue
            if (self._opened and action.action == "click" and chosen.overlay
                    and voice.CLOSE_WORDS.match(_without_icons(chosen.label) or "")):
                # Its own last press opened this; closing it undoes that press.
                # Flash-Lite did exactly this on Readings' sign-up form, in the
                # real window (EVALUATION.md, 2026-11-15a).
                feedback = ("Your own last action opened this dialog. Closing it would undo "
                            "that. Use what is in it: fill in its boxes or press its buttons.")
                continue
            if (action.action == "click" and self.page is not None and self._form_checks < 3
                    and SENDS_FORM.search(_without_icons(chosen.label) or "")):
                # Every required box is filled before a form is sent on (B4,
                # 2026-11-18); a box left empty is the model's to fill, not the page's
                # message to scold. Three checks a run, then the page decides.
                empty = await empty_required_boxes(resolve(self.page, elements, chosen.id))
                if empty:
                    self._form_checks += 1
                    log.info("AI choice refused: %d required boxes empty", len(empty))
                    feedback = ("This form still has required boxes that are empty: "
                                + ", ".join(empty) + ". Fill them in or choose them first, "
                                "then press this.")
                    continue
            return _Choice(action=action, element=chosen)
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
                 steps: int, auto: bool = True, reader: Provider | None = None,
                 notes: str = "") -> None:
        self.goal = goal
        self._notes = notes
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
        self.planner = OpenGoalPlanner(self._provider, task, ask_answer=not self._auto,
                                       notes=self._notes)
        return self.planner, task
