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

from dataclasses import dataclass

from backend.orchestrator.llm import Action, LLMError, Provider
from backend.orchestrator.loop import Move, Task
from backend.orchestrator import voice
from backend.orchestrator.plan import About, Expectation, Operation, Target
from backend.perception.content import Content
from backend.perception.serializer import Element
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


def _label(text: str) -> str:
    """One line, no run of spaces, at most LABEL_CHARS."""
    text = " ".join(text.split())
    return text if len(text) <= LABEL_CHARS else text[:LABEL_CHARS - 1].rstrip() + "…"


def render_page(elements: list[Element]) -> str:
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
    - a label is one line of at most LABEL_CHARS.
    """
    blocked = any(element.overlay for element in elements)
    choices = [e for e in elements if e.inferred and e.role == "option"]
    behind = sum(1 for e in elements if e.occluded and not e.overlay)
    nowhere = sum(1 for e in elements if e.dead_link and not e.occluded and not e.overlay)
    listed = [e for e in elements if e.overlay or not (e.occluded or e.dead_link)]

    lines = []
    if blocked:
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
    if hidden:
        lines += [f"Not listed, since none can be used: {', '.join(hidden)}."]
    if lines and lines[-1] != "":
        lines += [""]

    for element in listed:
        line = f"{element.id}. {element.role} {_label(element.label)!r}"
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
    return voice.describe(action.action, element.label or f"element {element.id}")


class LLMPlanner:
    """Asks the model for one action and shapes it into a Move."""

    def __init__(self, provider: Provider, task: Task) -> None:
        self._provider = provider
        self._task = task
        self.calls_made = 0
        self.stuck_reason: str | None = None

    async def next_move(
        self, elements: list[Element], history: list[str], setback: str | None
    ) -> Move | None:
        choice = await self._choose(elements, history, setback)
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
            operations=[operation],
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
                action = await self._provider.decide(
                    SYSTEM_PROMPT, render_page(elements), self._task.goal, feedback, history
                )
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
# words on the page itself, and nothing is the answer until the person says
# it is what they wanted (DECISIONS.md, *An open goal ends by pointing at its
# answer*). Everything else — what may be pressed, what is checked after each
# move, what is never typed — is the loop's, as for every planner.

OPEN_GOAL_RULES = """
When the page shows what the goal asks for, answer instead of acting: \
action "answer", element_id 0, value the answer copied exactly, word for word, \
from "What the page says" below. Copy only words that are there; never \
rephrase, add or calculate. If the goal needs a search first, search first.
Never type card numbers, bank details, passwords or one-time codes, and never \
press a button that pays, orders, books, registers or submits: say in your \
reasoning that the person must do that themselves.
"""

#: How much of what the page says goes in the prompt. A free tier's tokens a
#: minute are the limit that bites (8,000 on Groq; EVALUATION.md, 2026-11-12).
CONTENT_CHARS = 2400
#: The most rows of one table put in the prompt.
TABLE_ROWS = 12


def render_content(content: Content | None, limit: int = CONTENT_CHARS) -> str:
    """What the page says, for the model: headings, labelled values and the
    first rows of each table, cut at `limit` characters."""
    if not content:
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
    text = "\n".join(line for line in lines if line.strip())
    return text if len(text) <= limit else text[:limit] + "\n(... the rest is cut)"


class OpenGoalPlanner(LLMPlanner):
    """The model on a goal with no plan: acts, or answers from the page.

    `answer` is the finding once the person has said it is what they wanted;
    the loop shows it, rings it in the picture of the page, and checks the
    page still says it before closing (`loop.carry_out`)."""

    #: The model does not mark its own changes: a press whose words say it
    #: books, pays or submits is the loop's to stop (`loop.would_change`).
    marks_changes = False
    #: The run ends with the person's agreed answer, or not at all.
    must_answer = True

    def __init__(self, provider: Provider, task: Task) -> None:
        super().__init__(provider, task)
        self._content: Content | None = None
        self._proposed: str | None = None
        self._declined: str | None = None
        self.answer: Finding | None = None
        #: Which provider worked out the last move: shown to the person.
        self.worked_out_by: str | None = None

    def look(self, content: Content) -> None:
        """What the page says now. The loop calls this before each move."""
        self._content = content

    def answered(self, action_id: str, values: dict) -> None:  # noqa: ARG002
        """The person's answer to "Is this what you wanted?"."""
        if self._proposed is None:
            return
        if action_id == voice.CONFIRM_ID:
            self.answer = Finding(label=voice.WHAT_I_FOUND, value=self._proposed)
        else:
            self._declined = self._proposed
        self._proposed = None

    async def next_move(self, elements: list[Element], history: list[str],
                        setback: str | None) -> Move | None:
        if self.answer is not None:
            return None  # done: the loop closes with the answer
        if self._declined is not None:
            setback = (f'The person said "{self._declined}" is not what they wanted. '
                       "Keep looking, or do what the goal needs to find it.")
            self._declined = None
        choice = await self._choose(elements, history, setback)
        self.worked_out_by = getattr(self._provider, "label", None)
        if choice is None:
            return None
        if choice.action.action == "answer":
            self._proposed = (choice.action.value or "").strip()
            return Move(instruction=voice.found_this(self._proposed), detail="", operations=[],
                        expect=Expectation(), fields=[], actions=voice.is_this_it(),
                        question=True, kind="read")
        move = await super()._shape(choice)
        return move

    async def _choose(self, elements: list[Element], history: list[str],
                      setback: str | None) -> _Choice | None:
        """One action, retried once with the error fed back; an answer only
        if the page says it, word for word."""
        feedback = setback
        valid = {element.id: element for element in elements}
        page = (render_page(elements) + "\n\nWhat the page says:\n"
                + render_content(self._content))
        for _ in range(2):
            self.calls_made += 1
            try:
                action = await self._provider.decide(
                    SYSTEM_PROMPT + OPEN_GOAL_RULES, page, self._task.goal, feedback, history)
            except LLMError as error:
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
                feedback = (f"element_id {action.element_id} is not on the page. "
                            f"Valid ids are 1 to {len(elements)}.")
                continue
            return _Choice(action=action, element=valid[action.element_id])
        self.stuck_reason = voice.AI_COULD_NOT
        return None
