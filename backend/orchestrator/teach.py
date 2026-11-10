"""Watching a helper do a task once, and keeping it as a routine (2026-11-04).

"Show me once". The overlay steps aside to a bar at the top of the window and
the helper uses the real site below it; everything else about the site view is
as always (CLAUDE.md: covered, not hidden, whenever SIMBA is not being shown).
What the helper does is read by a small script in the page (`RECORDER_JS`)
and handed to the backend one thing at a time:

- **A press is held** until perception has read the page it was made on, then
  let through. A press usually moves the page on — a link opens another — and
  what was pressed has to be read on the page it was pressed on. So the click
  is stopped in the page, the backend reads the page and finds the element
  under the pointer by where perception says each element is, and the page is
  told to go ahead (`el.click()`). The helper sees a press that takes a moment.
- **A typed value is read when it is committed** (the box's `change`, Enter,
  or the next press), from the box the helper typed in, found the same way.
  A password box's value is never read: the script sends that it was a
  password and nothing more, and the routine keeps a place for one.
- **Never an id, never a selector.** Each is kept as perception's role and
  label at that moment, and which of several alike it was (`routines.Step`),
  so it can be found again on the page as it is next time.

**Safety, while teaching.** On a live site teaching only reads: a press whose
words say it would book, pay, register or submit (`loop.CHANGE_WORDS`, the
words the loop itself stops on) is not let through, and watching stops,
saying why. On our replicas such a press is kept, and when the routine runs it
waits behind the final screen like every change. A box for card or bank
details stops watching the moment it is entered, before anything is typed.

**Undo** (2026-11-10). The helper takes the last thing off the list from the
bar. The routine kept must still match the page: a typed value taken back is
taken out of its box; a press that moved the website to another page takes
the website back (`page.go_back`), and comes off the list only once the page
is really the one it was pressed on. When it is not, the bar says so, nothing
on the website is let through, and the only ways on are Start again — the
first page again, nothing kept — and stop. A press that stayed on its page
comes off the list and the page is left as it is.

**The answer.** Before it is kept, the helper points at what the task is for —
the amount, the list of trains — by clicking it. Nothing is let through while
pointing. What was clicked is found in what perception reads the page as
saying (`Content`), by the page's own label for it, and that label becomes the
routine's answer: what it reads at the end, what must be there for it to
finish, and what is ringed on the picture of the page.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field, replace

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page

from backend.orchestrator import voice
from backend.orchestrator.loop import CHANGE_WORDS, Connection, on_replica, resolve
from backend.orchestrator.routine_plan import find
from backend.orchestrator.routines import (
    MOST_SHOWN,
    TEXT_MAX,
    Answer,
    Routine,
    RoutineStore,
    Step,
    asks_consent,
    path_of,
)
from backend.orchestrator.tiles import clean_label
from backend.perception.content import Content
from backend.perception.serializer import Element, read_async
from shared.schema import (
    HelpRequested,
    StepField,
    StepPresented,
    TaskCompleted,
    TaskFailed,
    TaskStarted,
    TeachAnswer,
    TeachQuestion,
    TeachWatching,
)

log = logging.getLogger("simba.teach")

#: The name the page calls the backend by.
BINDING = "__simbaTaught"

#: The script in the page. Installed on the page as it is and on every page it
#: goes to while teaching. It does nothing unless `window.__simbaTeaching` is
#: true and the backend is there to answer, and it lets a press through if the
#: backend has not answered in `ANSWER_MS`: a page must never be left with
#: presses that go nowhere.
RECORDER_JS = r"""
(() => {
  if (window.__simbaRecorder) return;
  window.__simbaRecorder = true;
  const ANSWER_MS = 8000;
  const CARD = /\b(card|cvv|cvc|csc|security code|expiry|expiration|iban|swift|bank account)\b/i;
  const NOT_TYPED = new Set(['button', 'submit', 'reset', 'checkbox', 'radio', 'image', 'file',
                             'range', 'color', 'hidden']);
  const on = () => window.__simbaTeaching === true && typeof window.__simbaTaught === 'function';
  const typed = (el) => el instanceof HTMLTextAreaElement
    || (el instanceof HTMLInputElement && !NOT_TYPED.has((el.type || 'text').toLowerCase()));
  const secret = (el) => (el.type || '').toLowerCase() === 'password'
    || /password/i.test(el.autocomplete || '');
  const named = (el) => [el.labels && el.labels[0] ? el.labels[0].innerText : '',
                         el.getAttribute('aria-label') || '', el.placeholder || '',
                         el.name || '', el.id || ''].join(' ');
  const card = (el) => /^cc-/i.test(el.autocomplete || '') || CARD.test(named(el));
  const box = (el) => {
    const r = el.getBoundingClientRect();
    return {x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height};
  };
  const words = (el) => (el.innerText || el.textContent || el.value || '')
    .trim().replace(/\s+/g, ' ').slice(0, 200);
  const report = (event) => Promise.race([
    window.__simbaTaught(event),
    new Promise((done) => setTimeout(() => done('go'), ANSWER_MS)),
  ]).catch(() => 'go');
  let pending = null;
  const sent = new WeakMap();
  // Boxes the helper typed in. A value the page writes itself — a station
  // chosen from a list, a day picked on a calendar — is never typing.
  const edited = new WeakSet();
  const commit = async (el) => {
    if (!typed(el) || !edited.has(el) || sent.get(el) === el.value) return;
    sent.set(el, el.value);
    // Kept: whatever the page writes into it from now on is the page's,
    // until the helper types in it again.
    edited.delete(el);
    if (pending === el) pending = null;
    if (card(el)) return report({kind: 'card', box: box(el)});
    return report({kind: 'fill', box: box(el), secret: secret(el),
                   value: secret(el) ? null : el.value});
  };
  let passing = false;
  // The backend putting a value back into a box (2026-11-10, undo): the
  // page sees it as typing, the recorder does not, and the box's next real
  // typing is reported whatever it was before.
  window.__simbaRestore = (el, value) => {
    edited.delete(el);
    if (pending === el) pending = null;
    if (el instanceof HTMLSelectElement) {
      const option = [...el.options].find((o) => o.text.trim() === value);
      el.value = option ? option.value : '';
    } else {
      el.value = value;
    }
    el.dispatchEvent(new Event('input', {bubbles: true}));
    el.dispatchEvent(new Event('change', {bubbles: true}));
    edited.delete(el);
    sent.set(el, el.value);
  };
  // `pending`, above: the last box typed in, committed before the next
  // press even when the page never fired its change.
  document.addEventListener('input', (event) => {
    if (on() && typed(event.target)) {
      pending = event.target;
      edited.add(event.target);
    }
  }, true);
  document.addEventListener('focusin', (event) => {
    if (on() && typed(event.target) && card(event.target)) {
      report({kind: 'card', box: box(event.target)});
    }
  }, true);
  document.addEventListener('change', (event) => {
    if (!on()) return;
    const el = event.target;
    if (typed(el)) commit(el);
    else if (el instanceof HTMLSelectElement) {
      const chosen = el.selectedOptions[0];
      report({kind: 'select', box: box(el), value: chosen ? chosen.text.trim() : ''});
    }
  }, true);
  document.addEventListener('click', async (event) => {
    if (passing || !on()) return;
    const el = event.target;
    if (!(el instanceof Element)) return;
    const point = {x: event.clientX + scrollX, y: event.clientY + scrollY};
    if (window.__simbaPointing === true) {
      event.preventDefault();
      event.stopImmediatePropagation();
      report({kind: 'point', point, box: box(el), text: words(el)});
      return;
    }
    // Into a box: not held, since nothing can navigate, but said — a box
    // that is read-only until clicked, or that opens a calendar, needs the
    // click (2026-11-04, stage 2). Opening a list the page draws: nothing.
    if (typed(el)) {
      report({kind: 'click', point, box: box(el), text: ''});
      return;
    }
    if (el instanceof HTMLSelectElement || el instanceof HTMLOptionElement) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const active = document.activeElement;
    if (pending && pending.isConnected) await commit(pending);
    if (active && typed(active)) await commit(active);
    const verdict = await report({kind: 'click', point, box: box(el), text: words(el)});
    if (verdict !== 'go') return;
    passing = true;
    try { el.click(); } finally { passing = false; }
  }, true);
  document.addEventListener('keydown', async (event) => {
    if (passing || !on() || event.key !== 'Enter') return;
    const el = event.target;
    if (!typed(el) || el instanceof HTMLTextAreaElement) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    await commit(el);
    const button = el.form
      ? el.form.querySelector('button:not([type=button]):not([type=reset]), input[type=submit]')
      : null;
    const verdict = await report({kind: 'press', key: 'Enter', box: box(el),
                                  submits: button ? words(button) : ''});
    if (verdict !== 'go') return;
    passing = true;
    try {
      if (el.form) el.form.requestSubmit(button || undefined);
      else el.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', code: 'Enter',
                                                         keyCode: 13, which: 13, bubbles: true}));
    } finally { passing = false; }
  }, true);
  // A page opened while teaching asks what it is for: the helper may have
  // pressed Finish while it was still loading.
  if (on()) {
    report({kind: 'mode'}).then((mode) => {
      if (mode === 'pointing') window.__simbaPointing = true;
      if (mode === 'stop') window.__simbaTeaching = false;
    });
  }
})();
"""

#: How long taking the website back, or to its first page, may take.
BACK_MS = 10_000

#: Sets the page's switches: watching, and pointing at the answer.
SWITCH_JS = "([teaching, pointing]) => { window.__simbaTeaching = teaching; " \
            "window.__simbaPointing = pointing; }"


# --- finding what was pressed, on perception's own reading -------------------------


def _area(element: Element) -> float:
    return element.rect[2] * element.rect[3] if element.rect else float("inf")


def element_at(elements: list[Element], x: float, y: float) -> Element | None:
    """The element under a point, in the page's own coordinates: the smallest
    one perception read whose box holds it, so a link inside a row is the
    link, not the row."""
    inside = [e for e in elements if e.rect is not None
              and e.rect[0] <= x <= e.rect[0] + e.rect[2]
              and e.rect[1] <= y <= e.rect[1] + e.rect[3]]
    return min(inside, key=_area) if inside else None


def overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    """How much two boxes are the same box: shared area over both, 0 to 1."""
    left, top = max(a[0], b[0]), max(a[1], b[1])
    right, bottom = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    shared = max(0.0, right - left) * max(0.0, bottom - top)
    union = a[2] * a[3] + b[2] * b[3] - shared
    return shared / union if union > 0 else 0.0


#: How much of a box perception's element has to share with the box the page
#: reported for them to be the same thing.
SAME_BOX = 0.5


def element_over(elements: list[Element], box: dict) -> Element | None:
    """The element perception read at a box the page reported."""
    wanted = (box["x"], box["y"], box["w"], box["h"])
    scored = [(overlap(e.rect, wanted), e) for e in elements if e.rect is not None]
    best = max(scored, key=lambda pair: pair[0], default=(0.0, None))
    return best[1] if best[0] >= SAME_BOX else None


def twin_index(elements: list[Element], element: Element) -> int:
    """Which of the elements alike in role, label and qualifier this is."""
    twins = [e for e in elements if e.role == element.role and e.label == element.label
             and e.qualifier == element.qualifier]
    return next((index for index, e in enumerate(twins) if e is element), 0)


def labels_for(content: Content, text: str) -> list[str]:
    """The page's own labels for a value it says, as perception reads it.

    Exact first; then a value that holds the words clicked, for a cell whose
    text perception reads with something beside it."""
    text = " ".join((text or "").split())
    if not text:
        return []
    exact = [pair.label for pair in content.pairs if pair.value == text]
    if exact:
        return list(dict.fromkeys(exact))
    near = [pair.label for pair in content.pairs
            if text in pair.value or (pair.value and pair.value in text)]
    return list(dict.fromkeys(near))


def row_of(content: Content, elements: list[Element],
           element: Element) -> tuple[str, str] | None:
    """When a press is one of a column of alike presses, one in each row of a
    table — "Book train 7UP", "Book train 8DN" — the column whose value names
    its row, and its label with that value taken out: ("Train No.", "Book
    train {}"). Which row is then the person's choice (2026-11-04, fix). None
    for a press that is the only one of its kind, or a table of one row.

    Every other row must have its own press, named the same way: a label that
    merely holds a word from one cell is not a column of presses."""
    label = element.label or ""
    if not label or "{}" in label:
        return None
    alike = {e.label for e in elements if e.role == element.role}
    for table in content.tables:
        for header in table.headers:
            values = list(dict.fromkeys(row.get(header) for row in table.rows
                                        if row.get(header)))
            if len(values) < 2:
                continue
            for value in sorted((v for v in values if v in label), key=len, reverse=True):
                template = label.replace(value, "{}", 1)
                if all(template.replace("{}", other, 1) in alike
                       for other in values if other != value):
                    return header, template
    return None


#: The longest value a final screen's detail may have when it is taught: a
#: paragraph is not a detail.
SHOWN_MAX = 80


def shown_details(content: Content, pressed: str) -> tuple[str, ...]:
    """What a final screen shows for a press that changes something: the
    page's own labels for what it states once, short, at the moment the
    helper pressed it ("Train", "Date", "Fare"), in the page's order, at most
    `MOST_SHOWN` (2026-11-04, fix). A label the page gives several values,
    as a table's column does, is not one detail."""
    shown: list[str] = []
    for pair in content.pairs:
        label, value = " ".join(pair.label.split()), " ".join(pair.value.split())
        if (not label or not value or label == pressed or label in shown
                or len(value) > SHOWN_MAX or len(label) > TEXT_MAX
                or len(content.values_for(pair.label)) != 1):
            continue
        shown.append(label)
    return tuple(shown[:MOST_SHOWN])


# --- what was done, while watching -------------------------------------------------


@dataclass
class Taught:
    """One thing the helper did, with what is needed only until it is kept:
    where the page was and what it offered when it was done, and what was
    typed, to ask about."""

    step: Step
    url: str
    labels: frozenset[tuple[str, str]]
    #: What was typed, for "the same every time, or ask each time?". Never
    #: a password's: there is none to show.
    typed: str | None = None
    #: The answer to that question: None until it is given.
    same: bool | None = None


@dataclass
class Draft:
    """A routine as it stands while it is being shown."""

    start: str
    taught: list[Taught] = field(default_factory=list)
    answer: Answer | None = None
    #: What the answer said when it was pointed at, for the read-back only.
    example: str | None = None

    @staticmethod
    def asked_about(step: Step) -> bool:
        """A move the helper is asked about: a typed value, a choice from a
        list the page draws itself, or a day on a calendar (stage 2)."""
        return (step.kind in ("fill", "select") and not step.secret) or step.day

    def open_question(self) -> int | None:
        """The first such move not yet asked about, by position."""
        return next((index for index, item in enumerate(self.taught)
                     if self.asked_about(item.step) and item.same is None), None)

    def answer_question(self, index: int, same: bool) -> bool:
        if not 0 <= index < len(self.taught) or not self.asked_about(self.taught[index].step):
            return False
        self.taught[index].same = same
        return True

    def lines(self) -> list[str]:
        return [voice.taught_line(item.step, item.same, item.typed, asks_consent(item.step))
                for item in self.taught]

    def kept(self) -> list[str]:
        """Each thing kept, in a few words, newest last, for the bar's list
        (2026-11-10). Never what was typed; a password is a password."""
        return [voice.kept_line(item.step) for item in self.taught]

    def routine(self, end_url: str, label: str = "", answer_name: str | None = None) -> Routine:
        """The routine as it will be kept: every value answered, and what the
        page did after each move, read from where it went and what appeared."""
        assert self.answer is not None
        taught = self._folded()
        steps: list[Step] = []
        for index, item in enumerate(taught):
            step = item.step
            if step.kind in ("fill", "select") and not step.secret:
                step = (replace(step, ask=False, value=item.typed) if item.same
                        else replace(step, ask=True, value=None))
            if step.day:
                step = replace(step, ask=not item.same)
            after_url = taught[index + 1].url if index + 1 < len(taught) else end_url
            if path_of(after_url) != path_of(item.url):
                step = replace(step, expect_url=path_of(after_url))
            # Something the next move is made on that was not on the page
            # before this one: this move made it appear — a list opening on a
            # typed name, a box on the next part of a form — and that is what
            # its check waits for.
            if index + 1 < len(taught):
                following = taught[index + 1]
                wanted = (following.step.role, following.step.label)
                # Typing and then choosing from a list is a list choice, by its
                # shape: what the page offered before the typing cannot be
                # told, since the click into the box is not held (stage 2).
                if (step.kind == "fill" and following.step.kind == "click"
                        and following.step.role == "option" and following.step.label
                        and not following.step.day):
                    step = replace(step, expect_label=following.step.label, list_opens=True)
                elif (wanted not in item.labels and wanted in following.labels
                        and following.step.label and not following.step.day):
                    step = replace(step, expect_label=following.step.label,
                                   list_opens=step.kind in ("fill", "press"))
                # Before a day asked each time: the calendar has to be open,
                # which its own press for the next month says.
                elif following.step.day and following.step.nav:
                    step = replace(step, expect_label=following.step.nav)
            # A list choice after a box asked each time is the person's
            # choice: the option their answer names.
            if (steps and step.kind == "click" and step.role == "option" and not step.day
                    and steps[-1].kind == "fill" and steps[-1].ask
                    and steps[-1].expect_label == step.label):
                step = replace(step, pick=True)
            steps.append(step)
        # One final screen per booking (2026-11-04, fix): a link whose words
        # say book, that went to another page, before a press that changes
        # something, only opened the form that one sends. That press keeps
        # the final screen; the link is a page to read.
        for index, step in enumerate(steps):
            if (step.changes and step.role == "link" and step.expect_url
                    and any(later.changes for later in steps[index + 1:])):
                steps[index] = replace(step, changes=False, opens=True)
        answer = self.answer
        if answer_name and answer_name.strip():
            answer = replace(answer, name=" ".join(answer_name.split())[:60])
        return Routine(id="", label=label, start=self.start, steps=tuple(steps), answer=answer)

    def _folded(self) -> list[Taught]:
        """What was done, with two kinds of press folded into what they were
        for: a click into a box that is then typed in, which becomes part of
        the typing; and, before a day asked each time, the presses that moved
        the calendar on, which become how to move it (`Step.nav`)."""
        out: list[Taught] = []
        for item in self.taught:
            step = item.step
            if (step.kind == "fill" and out and out[-1].step.kind == "click"
                    and (out[-1].step.role, out[-1].step.label, out[-1].step.nth)
                    == (step.role, step.label, step.nth)):
                clicked = out.pop()
                out.append(replace(item, step=replace(step, click_first=True), url=clicked.url,
                                   labels=clicked.labels))
                continue
            if step.day and item.same is False:
                moved: list[Taught] = []
                while out and out[-1].step.kind == "click" and MONTH_PRESS.search(
                        f"{out[-1].step.label} {out[-1].step.role}") and out[-1].step.role in (
                        "button", "link"):
                    moved.insert(0, out.pop())
                nav = moved[-1].step.label if moved else None
                out.append(replace(item, step=replace(step, nav=nav),
                                   url=moved[0].url if moved else item.url,
                                   labels=moved[0].labels if moved else item.labels))
                continue
            out.append(item)
        return out


#: A press that moves a calendar on or back: "Next Month", "Previous Month".
MONTH_PRESS = re.compile(r"\b(month|next|previous|prev)\b", re.IGNORECASE)

#: A calendar's month, as perception reads its banner: "2026 December".
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december"]


def shown_month(panel: str) -> tuple[int, int] | None:
    """The (year, month) a calendar says it shows, or None."""
    words = (panel or "").casefold().split()
    year = next((int(w) for w in words if w.isdigit() and len(w) == 4), None)
    month = next((MONTHS.index(w) + 1 for w in words if w in MONTHS), None)
    return (year, month) if year and month else None


def is_day(element: Element) -> bool:
    """A day on a calendar: a number, in a panel that names a month."""
    return (element.role == "option" and element.label.isdigit()
            and shown_month(element.panel) is not None)


class Teaching:
    """Watching one helper on one page, from `start` until `stop`.

    Every event from the page is handled one at a time, in the order the page
    sent them, under one lock: perception reads the page once per event, and
    two reads interleaved would describe two moments as one."""

    def __init__(self, page: Page, events: "asyncio.Queue | None" = None) -> None:
        self.page = page
        self.draft = Draft(start=page.url)
        self.pointing = False
        #: Undo could not take the website back to the page the last thing
        #: was done on (2026-11-10): nothing is let through, nothing is kept,
        #: until Start again.
        self.stuck = False
        #: Why watching stopped, once it has.
        self.stopped: str | None = None
        #: What the session should hear about, in order: ("changed", None),
        #: ("stopped", reason), ("pointed", None) or ("missed", note). The
        #: session puts what the overlay says on the same queue (`teach`).
        self.events: asyncio.Queue = events if events is not None else asyncio.Queue()
        self._lock = asyncio.Lock()
        self._installed = False

    async def start(self) -> None:
        self.draft.start = self.page.url
        await self.page.expose_binding(BINDING, self._heard)
        script = f"window.__simbaTeaching = true;\n{RECORDER_JS}"
        await self.page.add_init_script(script)
        await self.page.evaluate(script)
        self._installed = True
        log.info("teaching started on %s", path_of(self.page.url))

    async def point(self, on: bool) -> None:
        self.pointing = on
        await self._switch(True, on)

    async def stop(self) -> None:
        """The page goes back to being an ordinary page: nothing held."""
        if self._installed:
            await self._switch(False, False)

    async def _switch(self, teaching: bool, pointing: bool) -> None:
        try:
            await self.page.evaluate(SWITCH_JS, [teaching, pointing])
        except PlaywrightError:
            pass  # between pages: the next one starts from the init script

    def _end(self, reason: str) -> str:
        self.stopped = reason
        self.events.put_nowait(("stopped", reason))
        return "stop"

    async def undo(self) -> str | None:
        """Takes the last thing off the list, and the website back when that
        thing moved it to another page (2026-11-10). Returns what the bar
        should say when it could not, and None when it is done."""
        async with self._lock:
            if self.stuck:
                return voice.TEACH_NOT_BACK
            if self.pointing or not self.draft.taught:
                return None
            item = self.draft.taught[-1]
            if path_of(self.page.url) != path_of(item.url):
                if not await self._back_to(item.url):
                    # Not the page it was pressed on, or not a page that can
                    # be put back as it was: the list no longer matches the
                    # website, and nothing more is let through.
                    self.stuck = True
                    log.info("teaching: undo could not take the page back; start again")
                    return voice.TEACH_NOT_BACK
            self.draft.taught.pop()
            log.info("teaching: took a %s off, %d kept", item.step.kind, len(self.draft.taught))
            if item.step.kind in ("fill", "select"):
                await self._restore(item.step, "")
            return None

    async def _back_to(self, url: str) -> bool:
        """The website back to the page the last thing was pressed on, as the
        list says it was: True when it is really that page and what the list
        says was typed on it is in its boxes again. A page where a choice
        was made from a list, a day picked, or a password typed cannot be put
        back as it was, and that is False too."""
        try:
            await self.page.go_back(wait_until="load", timeout=BACK_MS)
        except PlaywrightError as error:
            log.info("teaching: going back: %s", str(error).splitlines()[0])
        if path_of(self.page.url) != path_of(url):
            return False
        there = [item for item in self.draft.taught[:-1] if path_of(item.url) == path_of(url)]
        if any(item.step.secret or item.step.day or (item.step.kind == "click"
                                                     and item.step.role == "option")
               for item in there):
            return False
        for item in there:
            if item.step.kind in ("fill", "select") and item.typed:
                await self._restore(item.step, item.typed)
        return True

    async def _restore(self, step: Step, value: str) -> None:
        """A box as the list says it is: a typed value taken back is taken
        out of it, and one the list keeps is put back after the website goes
        back. Found as the routine will find it, by role and label, never a
        selector; put there through the recorder, so it is not typing."""
        try:
            view = await read_async(self.page)
            element = find(view.elements, step)
            if element is not None:
                await resolve(self.page, view.elements, element.id).evaluate(
                    "(el, value) => window.__simbaRestore(el, value)", value, timeout=BACK_MS)
        except PlaywrightError as error:
            log.info("teaching: could not put the box back: %s", str(error).splitlines()[0])

    async def restart(self) -> str | None:
        """The first page again, with nothing kept (2026-11-10)."""
        async with self._lock:
            self.draft = Draft(start=self.draft.start)
            self.stuck = False
            self.pointing = False
            try:
                await self.page.goto(self.draft.start, wait_until="load", timeout=BACK_MS)
            except PlaywrightError as error:
                log.info("teaching: starting again: %s", str(error).splitlines()[0])
            if path_of(self.page.url) != path_of(self.draft.start):
                self.stuck = True
                return voice.TEACH_NOT_RESTARTED
            await self._switch(True, False)
            log.info("teaching: started again on %s", path_of(self.page.url))
            return None

    async def _heard(self, source, event: dict) -> str:  # noqa: ARG002 - Playwright's
        """One thing from the page. Returns what the page should do with a
        press it is holding: "go", or "stop"."""
        async with self._lock:
            if self.stopped is not None:
                return "stop"
            try:
                return await self._handle(event or {})
            except PlaywrightError as error:
                # The page moved under the read. Let the press through and
                # keep nothing for it, rather than hold a page that waits.
                log.info("teaching: page moved while reading it: %s", str(error).splitlines()[0])
                return "go"

    async def _handle(self, event: dict) -> str:
        kind = event.get("kind")
        if kind == "mode":
            return "pointing" if self.pointing else "watching"
        if self.stuck:
            return "stop"  # held, never made, and not kept: the page is not where it was
        if kind == "card":
            return self._end(voice.TEACH_STOPPED_CARD)
        if kind == "point" or (self.pointing and kind == "click"):
            await self._pointed(event)
            return "stop"
        if self.pointing:
            return "stop"
        view = await read_async(self.page)
        elements = view.elements
        labels = frozenset((e.role, e.label) for e in elements)
        url = self.page.url
        if kind in ("fill", "select"):
            element = element_over(elements, event.get("box") or {})
            if element is None:
                return "go"
            self._typed(element, elements, kind, event, url, labels)
            return "go"
        if kind == "click":
            point = event.get("point") or {}
            element = (element_at(elements, point.get("x", -1), point.get("y", -1))
                       or element_over(elements, event.get("box") or {}))
            if element is None:
                return "go"  # nothing perception counts as something to press
            changes = bool(CHANGE_WORDS.search(element.label or ""))
            if changes and not on_replica(url):
                return self._end(voice.TEACH_STOPPED_CHANGE)
            step = Step(kind="click", role=element.role, label=element.label,
                        nth=twin_index(elements, element),
                        qualifier=element.qualifier or None, changes=changes,
                        day=is_day(element))
            row = None if step.day else row_of(view.content, elements, element)
            if row is not None:
                # One train of the several found: the person's to choose.
                step = replace(step, row=row[0], label=row[1], nth=0)
            if changes:
                step = replace(step, shows=shown_details(view.content, element.label))
            self._add(step, url, labels)
            return "go"
        if kind == "press":
            element = element_over(elements, event.get("box") or {})
            submits = event.get("submits") or ""
            changes = bool(CHANGE_WORDS.search(submits))
            if changes and not on_replica(url):
                return self._end(voice.TEACH_STOPPED_CHANGE)
            if element is None:
                return "go"
            self._add(Step(kind="press", role=element.role, label=element.label,
                           nth=twin_index(elements, element), value=event.get("key") or "Enter",
                           changes=changes,
                           shows=shown_details(view.content, submits) if changes else ()),
                      url, labels)
            return "go"
        return "go"

    def _typed(self, element: Element, elements: list[Element], kind: str, event: dict,
               url: str, labels: frozenset) -> None:
        secret = bool(event.get("secret")) or element.is_password
        value = None if secret else str(event.get("value") or "")
        step = Step(kind="fill" if kind == "fill" else "select", role=element.role,
                    label=element.label, nth=twin_index(elements, element), secret=secret)
        last = self.draft.taught[-1] if self.draft.taught else None
        if last is not None and last.step.kind == step.kind and (
                last.step.role, last.step.label, last.step.nth) == (step.role, step.label,
                                                                      step.nth):
            # The same box again: the value it ends with is the one.
            if not secret and not value:
                self.draft.taught.pop()
            else:
                last.typed = value
            self.events.put_nowait(("changed", None))
            return
        if not secret and not value:
            return  # a box left empty is nothing to do
        self._add(step, url, labels, typed=value)

    def _add(self, step: Step, url: str, labels: frozenset, typed: str | None = None) -> None:
        if asks_consent(step) and any(
                path_of(item.url) == path_of(url) and item.step == step
                for item in self.draft.taught):
            # The banner back after the website went back (undo): one press.
            log.info("teaching: a consent press pressed again on the same page")
            return
        self.draft.taught.append(Taught(step=step, url=url, labels=labels, typed=typed))
        log.info("teaching: kept a %s on a %s", step.kind, step.role)
        self.events.put_nowait(("changed", None))

    async def _pointed(self, event: dict) -> None:
        view = await read_async(self.page)
        found = labels_for(view.content, event.get("text") or "")
        if not found:
            self.events.put_nowait(("missed", voice.POINT_AGAIN))
            return
        text = " ".join((event.get("text") or "").split())
        self.draft.answer = Answer(name=found[0], reads=found[0])
        self.draft.example = text
        self.pointing = False
        await self._switch(True, False)
        log.info("teaching: answer pointed at")
        self.events.put_nowait(("pointed", None))


def watching(teaching: Teaching, note: str | None = None) -> TeachWatching:
    """What the bar shows: what has been kept so far, in plain words, the one
    question open about a typed value, whether the helper is pointing at the
    answer, and a note."""
    draft = teaching.draft
    index = draft.open_question()
    question = None
    if index is not None:
        item = draft.taught[index]
        question = TeachQuestion(step=index, label=item.step.label or item.step.role,
                                 value=item.typed or "",
                                 kind="day" if item.step.day else "typed")
    return TeachWatching(lines=draft.lines(), kept=draft.kept(), question=question,
                         pointing=teaching.pointing, note=note, start_again=teaching.stuck)


# --- the conversation, from "Show me once" to a tile -------------------------------


async def teach(page: Page, connection: Connection, url: str, routines: RoutineStore,
                tiles: int = 0) -> Routine | None:
    """Watch the helper on `url`, then read back what was learned, and keep it
    under the name the helper gives. Returns what was kept, or None.

    `tiles` is how many of the person's own tiles are on the home screen: a
    routine takes a place in the same row of three, so with none left nothing
    is watched at all."""
    started = time.monotonic()
    if not routines.available:
        await _help(connection, voice.TEACH_CANNOT_KEEP)
        return None
    if not routines.room(tiles):
        await _help(connection, voice.TEACH_NO_ROOM)
        return None
    await page.goto(url)
    events: asyncio.Queue = asyncio.Queue()
    teaching = Teaching(page, events)
    await teaching.start()
    reader = asyncio.create_task(_read(connection, events))
    try:
        await connection.send("teach.watching", watching(teaching))
        if not await _watch(teaching, connection, events):
            return None
        await teaching.stop()
        return await _keep(teaching, connection, events, routines, tiles, started)
    finally:
        reader.cancel()
        await teaching.stop()


async def _read(connection: Connection, events: asyncio.Queue) -> None:
    """Everything the overlay says, onto the queue the page's events go on."""
    while True:
        try:
            message = await connection.next_message()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - the connection closed
            await events.put(("closed", None))
            return
        await events.put(("overlay", message))


async def _help(connection: Connection, reason: str) -> None:
    await connection.send("help.requested",
                          HelpRequested(reason=reason, suggestion=voice.TEACH_SUGGESTION))


async def _stopped(connection: Connection) -> None:
    await connection.send("task.failed", TaskFailed(reason=voice.YOU_STOPPED, recoverable=True))


async def _watch(teaching: Teaching, connection: Connection, events: asyncio.Queue) -> bool:
    """Until the helper has shown it and pointed at the answer: True. False
    when watching stopped, for any reason, and the person has been told."""
    while True:
        what, data = await events.get()
        if what == "closed":
            return False
        if what == "stopped":
            await _help(connection, str(data))
            return False
        if what == "pointed":
            return True
        if what in ("changed", "missed"):
            await connection.send("teach.watching", watching(teaching, data))
            continue
        message = data if isinstance(data, dict) else {}
        kind = message.get("type")
        if kind == "task.cancel":
            await _stopped(connection)
            return False
        if kind != "teach.answer":
            continue  # telemetry, a level: nothing to do while watching
        try:
            answer = TeachAnswer.model_validate(message.get("payload") or {})
        except ValueError:
            continue
        note = None
        if answer.action == "cancel":
            await _stopped(connection)
            return False
        if answer.action in ("same", "ask") and answer.step is not None:
            teaching.draft.answer_question(answer.step, answer.action == "same")
        elif answer.action == "undo":
            note = await teaching.undo()
        elif answer.action == "restart":
            note = await teaching.restart()
        elif answer.action == "finish":
            if teaching.stuck:
                note = voice.TEACH_START_AGAIN_FIRST
            elif teaching.draft.open_question() is not None:
                note = voice.TEACH_ANSWER_FIRST
            elif not teaching.draft.taught:
                note = voice.TEACH_NOTHING_YET
            else:
                await teaching.point(True)
        await connection.send("teach.watching", watching(teaching, note))


async def _keep(teaching: Teaching, connection: Connection, events: asyncio.Queue,
                routines: RoutineStore, tiles: int, started: float) -> Routine | None:
    """The read-back, and the name: kept, or not, and said either way."""
    draft = teaching.draft
    end_url = teaching.page.url
    shown = draft.routine(end_url)
    await connection.send("task.started", TaskStarted(goal=voice.TEACH_GOAL, estimated_steps=1))
    note: str | None = None
    index = 0
    name = ""
    answer_name = draft.answer.name if draft.answer else ""
    while True:
        index += 1
        await connection.send("step.presented", StepPresented(
            step_index=index, step_total=1, instruction=voice.TEACH_READ_BACK,
            detail=voice.TEACH_NAME_IT,
            fields=[StepField(id="name", label=voice.FIELD_ROUTINE_NAME, type="text", value=name),
                    StepField(id="answer", label=voice.FIELD_ANSWER_NAME, type="text",
                              value=answer_name)],
            actions=voice.actions(voice.KEEP_ROUTINE), requires_confirmation=True,
            step_kind="confirm", note=note,
            routine=voice.routine_lines(shown, draft.example)))
        response = await _response(events, index)
        if response is None:
            return None
        if response.get("action_id") != voice.CONFIRM_ID:
            await _stopped(connection)
            return None
        values = response.get("input_values") or {}
        name = clean_label(values.get("name") or "")
        answer_name = " ".join((values.get("answer") or answer_name).split())
        if not name:
            note = voice.NAME_IT_FIRST
            continue
        kept = routines.add(draft.routine(end_url, name, answer_name), tiles=tiles)
        if kept is None:
            await _help(connection, voice.TEACH_NO_ROOM)
            return None
        log.info("teaching: kept a routine of %d moves in %.1fs", len(kept.steps),
                 time.monotonic() - started)
        await connection.send("task.completed", TaskCompleted(
            summary=f"{voice.TEACH_GOAL} {end_url}",
            duration_ms=int((time.monotonic() - started) * 1000),
            steps_taken=len(kept.steps), llm_calls=0, replayed=False,
            explanation=voice.taught_kept(kept.label), scope=voice.TEACH_KEPT_SCOPE))
        return kept


async def _response(events: asyncio.Queue, index: int) -> dict | None:
    """The overlay's answer to the read-back, or None if it went away."""
    while True:
        what, data = await events.get()
        if what == "closed":
            return None
        if what != "overlay" or not isinstance(data, dict):
            continue
        if data.get("type") == "task.cancel":
            return {"action_id": voice.CANCEL_ID}
        payload = data.get("payload") or {}
        if data.get("type") == "step.response" and payload.get("step_index") == index:
            return payload
