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
import time
from dataclasses import dataclass, field, replace

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page

from backend.orchestrator import voice
from backend.orchestrator.loop import CHANGE_WORDS, Connection, on_replica
from backend.orchestrator.routines import Answer, Routine, RoutineStore, Step, asks_consent, path_of
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
  const sent = new WeakMap();
  const commit = async (el) => {
    if (!typed(el) || sent.get(el) === el.value) return;
    sent.set(el, el.value);
    if (card(el)) return report({kind: 'card', box: box(el)});
    return report({kind: 'fill', box: box(el), secret: secret(el),
                   value: secret(el) ? null : el.value});
  };
  let passing = false;
  // The last box typed in: committed before the next press even when the
  // page never fired its change.
  let pending = null;
  document.addEventListener('input', (event) => {
    if (on() && typed(event.target)) pending = event.target;
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
    // Into a box to type in, or opening a list: nothing to keep yet.
    if (typed(el) || el instanceof HTMLSelectElement || el instanceof HTMLOptionElement) return;
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

    def open_question(self) -> int | None:
        """The first typed value not yet asked about, by position."""
        return next((index for index, item in enumerate(self.taught)
                     if item.step.kind in ("fill", "select") and not item.step.secret
                     and item.same is None), None)

    def answer_question(self, index: int, same: bool) -> bool:
        if not 0 <= index < len(self.taught):
            return False
        item = self.taught[index]
        if item.step.kind not in ("fill", "select") or item.step.secret:
            return False
        item.same = same
        return True

    def lines(self) -> list[str]:
        return [voice.taught_line(item.step, item.same, item.typed, asks_consent(item.step))
                for item in self.taught]

    def routine(self, end_url: str, label: str = "", answer_name: str | None = None) -> Routine:
        """The routine as it will be kept: every value answered, and what the
        page did after each move, read from where it went and what appeared."""
        assert self.answer is not None
        steps: list[Step] = []
        for index, item in enumerate(self.taught):
            step = item.step
            if step.kind in ("fill", "select") and not step.secret:
                step = (replace(step, ask=False, value=item.typed) if item.same
                        else replace(step, ask=True, value=None))
            after_url = (self.taught[index + 1].url if index + 1 < len(self.taught)
                         else end_url)
            if path_of(after_url) != path_of(item.url):
                step = replace(step, expect_url=path_of(after_url))
            # Something the next move presses that was not on the page before
            # this one: this move made it appear — a list opening on a typed
            # name — and that is what its check waits for.
            if index + 1 < len(self.taught):
                following = self.taught[index + 1]
                wanted = (following.step.role, following.step.label)
                if (following.step.kind in ("click", "select") and wanted not in item.labels
                        and wanted in following.labels and following.step.label):
                    step = replace(step, expect_label=following.step.label,
                                   list_opens=step.kind in ("fill", "press"))
            steps.append(step)
        answer = self.answer
        if answer_name and answer_name.strip():
            answer = replace(answer, name=" ".join(answer_name.split())[:60])
        return Routine(id="", label=label, start=self.start, steps=tuple(steps), answer=answer)


class Teaching:
    """Watching one helper on one page, from `start` until `stop`.

    Every event from the page is handled one at a time, in the order the page
    sent them, under one lock: perception reads the page once per event, and
    two reads interleaved would describe two moments as one."""

    def __init__(self, page: Page, events: "asyncio.Queue | None" = None) -> None:
        self.page = page
        self.draft = Draft(start=page.url)
        self.pointing = False
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
            self._add(Step(kind="click", role=element.role, label=element.label,
                           nth=twin_index(elements, element),
                           qualifier=element.qualifier or None, changes=changes), url, labels)
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
                           changes=changes), url, labels)
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
                                 value=item.typed or "")
    return TeachWatching(lines=draft.lines(), question=question, pointing=teaching.pointing,
                         note=note)


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
        elif answer.action == "finish":
            if teaching.draft.open_question() is not None:
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
