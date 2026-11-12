# SIMBA message contract — v1

**Status: DRAFT.** Ratify in a session with all three owners, then treat as
frozen. Additive optional fields are allowed afterwards. Renames and removals
require all three owners and a version bump.

Transport: WebSocket, JSON, one connection per app session.

## Envelope

Every message, both directions:

```json
{
  "v": 1,
  "type": "step.presented",
  "task_id": "t_8f2a",
  "seq": 14,
  "ts": 1757001234567,
  "payload": {}
}
```

`seq` is a per-connection monotonic counter, independent per direction. A gap
means a dropped message — log it, don't silently continue.

---

## Backend to frontend

### `task.started`
```json
{ "goal": "Register for CS-401", "estimated_steps": 6 }
```

### `state.changed`
```json
{ "state": "thinking" }
```
`state` is one of `thinking` | `acting` | `waiting` | `stuck`. Drives the four
visual states. Exactly one is active at a time.

### `history.offered`
Added 2026-09-15. **Pending ratification** — see below. Sent **once, when the
socket opens**, before any task.
```json
{
  "goals": [
    { "goal": "Register for CS-401", "site": "http://127.0.0.1:5000" },
    { "goal": "Check my electricity bill", "site": "http://127.0.0.1:5100" }
  ]
}
```
**`label` is additive and optional** (added 2026-10-16): the goal in a few
words for the home screen's one line, `"Bill ending 7890"`, `"Trains Lahore
Cantt to Rawalpindi"`, `"Course CS-401"`. Absent, the goal's own words are
shown.

**`tiles` is additive and optional** (added 2026-10-18): the person's own
tiles, in their order — a task they kept from its closing screen, by the
name they gave it. Each is `id`, `label` and `flow` only: what the tile keeps
(a reference number, two stations) stays in the backend, encrypted with the
vault's key (`backend/orchestrator/tiles.py`), and never crosses the socket.
Also sent again, whole, in answer to every `tile.change`. Absent: none.
```json
{ "goals": [], "tiles": [ { "id": "3f9a1c2e7b40", "label": "My bill", "flow": "billing" } ] }
```

What the home screen offers instead of an empty text box. Read from the same
SQLite trace store that replay uses, newest first, capped at three — so the
cards are exactly the goals that would replay, rather than a second list that
could disagree with the first.

An empty list is normal and means the text box is shown directly. A frontend
that ignores this message sees exactly what it saw before.

This is the only message the backend sends unprompted.

**Status: pending ratification** (recorded 2026-09-17). It was added by one
owner to serve the home screen. It is additive in effect, but it is a new
message *type* rather than an optional field on an existing one, and this
file's rule for changes without ceremony names only additive optional
fields. It needs agreeing by Nahail, Raham and Aly, at the same session that
ratifies the rest of this draft. Until then, treat it as provisional: a
frontend must keep working without it, and does.

**Why a WebSocket message and not an HTTP endpoint.** The obvious alternative
was `GET /history` on the FastAPI app, fetched by the home screen. It was not
chosen, for these reasons:

- **One channel.** CLAUDE.md says the two processes talk over WebSocket and
  that nothing crosses the boundary that is not in this file. An HTTP route
  would be a second transport with its own error handling and its own place
  to document, for one list of strings.
- **No new request is needed.** The overlay opens the socket as soon as it
  starts, and the backend has nothing to wait for before answering. A GET
  would be a second round trip to learn something the connection could carry.
- **It is visible where everything else is.** A message gets an envelope and
  a `seq`, and shows in the development view's log (Ctrl+Shift+D) beside
  every other message. An HTTP response would not.
- **The mock plays it too.** `tools/mock_backend.py` is the demo-day
  fallback and speaks only this protocol. A route would need a second fake.
- **No cross-origin setup.** The Electron overlay is loaded from `file:`, so
  a fetch to `http://127.0.0.1:8000` would need CORS configured on the
  backend. The WebSocket already connects from there.
- **Unprompted rather than asked for**, because asking would have needed a
  second new message type (a frontend-to-backend request) for no gain: there
  is only ever one answer and it is wanted immediately.

**What it costs, known on 2026-09-17:**

- It is only as fresh as the connection. The backend closes the socket when a
  task ends, and the frontend reconnects only when the next task starts. So
  the home screen reached from a finished task shows the list from *before*
  that task, and a goal just done does not appear until the next connection.
  A GET re-fetched on the way home would not have this problem; fixing it
  here means reconnecting on the way home, or a request message.
- The list is read from the trace store, and only `SIMBA_TRACE_MEMORY=1`
  writes to it. With the launchers' defaults the list is whatever an earlier
  trace-memory run left in `traces.db`, which is usually nothing.

### `goal.answered`
Added 2026-09-21. **Pending ratification**, on the same terms as
`history.offered`: a new message type, not an optional field, so it needs
Nahail, Raham and Aly. Until then a frontend must keep working without it.

Sent in answer to a `task.start` whose goal is **not** a request for one of
the flows. No task starts. The socket stays open, and the next `task.start`
arrives on it.
```json
{ "kind": "clarify", "goal": "I need to pay for my course",
  "flows": ["registration", "billing"] }
```
`kind` is one of:

- `greeting` — small talk, or an empty goal. Offer what can be done.
- `unsupported` — a real request SIMBA cannot do. Say so, and offer what can.
- `clarify` — it could be two or more flows. Ask which; each of `flows` is a
  choice.

`flows` is what to offer, from `registration` | `billing` | `railways`: all
of them for `greeting` and `unsupported`, the candidates for `clarify`.
`goal` is what was typed, so a clarifying choice can send it back unchanged.

**It carries no words.** The overlay writes every sentence and every card
from `copy.ts`, where the rest of what the person reads is kept and tested —
so the real backend and the mock cannot disagree about what is said, and no
sentence reaches the screen that the copy rules have not checked.

**Why this exists.** Until 2026-09-21 the backend's `SIMBA_FLOW` chose the
task and the goal was only its label: "hello" typed into a backend started as
`billing` began on somebody's bill. The rule this serves is that nothing
starts that the person did not ask for, and keeping it needs a way to answer
without starting anything.

### `step.presented`
The main message.
```json
{
  "step_index": 2,
  "step_total": 6,
  "instruction": "Your bill is PKR 5,420. Pay it now?",
  "detail": "Due 15 September. Account ending 8841.",
  "fields": [
    { "id": "consumer_no", "label": "Consumer number", "type": "text", "value": "" }
  ],
  "actions": [
    { "id": "confirm", "label": "Yes, pay PKR 5,420", "kind": "primary" },
    { "id": "cancel",  "label": "Not now",            "kind": "secondary" }
  ],
  "requires_confirmation": true
}
```
`detail` renders only at level 1. `fields` is usually empty. `kind` is
`primary` | `secondary` | `destructive`.

**`requires_confirmation: false` is a checklist line** (since 2026-10-14). The
backend is doing the move by itself: nothing waits for a `step.response`, and
the overlay shows `instruction` as one line of a checklist that ticks off.
Its one answer is Pause: a `step.response` with `"action_id": "pause"` and that
line's `step_index`, after which the backend does nothing more until the
person says to carry on. `task.start.confirm_each: true` (additive and
optional) asks for every move to be confirmed instead.

**Keeping a password** (2026-10-15; no change to the messages). A sign-in
step whose password can be kept offers a second answer, `"id": "remember"`,
beside its own. The overlay draws that offer as a box to tick ("Save my
password for next time") rather than as a button, and its one sign-in button
sends `remember` when the box is ticked and its own id when it is not. A
backend that offers nothing to keep gets no box.

**`task.completed.scope` is additive and optional** (added 2026-10-16). The
closing screen's last line, saying what was done and what was not: "I only
looked up times. I did not book a ticket or pay for anything." For a task
that changed something, what changed: "You are registered for CS-401 section
001." Written in `voice.py` for each flow; absent for a model-planned task.

**`task.completed.confirmation` is additive and optional** (added
2026-10-16). For a task that changed something, the site's own confirmation,
quoted from the final page: 'The portal says "Registration Confirmed", with
confirmation number REG-10234-2026.' A task that changes something is
completed only when that confirmation is on the page; otherwise it ends in
`help.requested`, saying plainly that it is not confirmed, with
`"unconfirmed": true` (additive and optional) so the overlay leads with that
rather than with being stuck. The step that
makes the change is tried once, never again a second way: a second press
could make the change twice.

**`task.completed.caveat` is additive and optional** (added 2026-10-16). What
the site says against its own confirmation, its sentence quoted whole from
the final page: 'The portal also says "Registration is not final until
tuition and fees are paid or a payment plan is in place".' Sent only when
the page says it; the closing screen shows it under the confirmation, so it
never says more than the site does.

**`task.completed.proof` and `proof_note` are additive and optional**
(added 2026-10-16), with a new shape, `Proof`: `{ "screenshot": "<base64
png>", "rings": [Highlight, ...], "caption": "What I read is ringed." }`.
Before closing, the backend reads the page again and compares it with what
it is about to show; if they differ it shows no answer and says so
(`help.requested`, `"unconfirmed": true`). Then it takes a still of the page
with every row or value it read ringed, in the screenshot's own pixels
(1280x800). When it cannot, `proof_note` says why in plain words. Never an
empty or stale picture.

**`final` is additive and optional** (added 2026-10-16), with a new shape,
`Detail`: `{ "label": "Fare", "value": "Rs 3,250" }`. A step that carries it
is the **final screen** before a move that books, pays, registers or changes
a record (CLAUDE.md, the final-step rule): `instruction` says in plain words
exactly what will happen, `final` lists what, how much and when as the page
states them at that moment, and `actions` are exactly two — do it,
`"id": "confirm"`, and don't, `"id": "decline"` — with neither drawn as the
default and nothing moving on by itself. "Don't" ends the task:
`task.failed` with the reason "I didn't do it. Nothing was changed.". The
backend sends a final screen only on a replica, and acts on such a move only
after "confirm" on it.

**`task.completed.offer` is additive and optional** (added 2026-10-16),
with a new shape, `TaskOffer`: `{ "id": "book", "label": "Book one of
these" }`. On our replicas only, what can follow the answer — booking one of
the trains found, paying the bill — drawn as a quiet second button beside
"Back to start". The backend keeps the connection open after such a
`task.completed`. Pressed, the overlay sends `step.response` with
`"action_id"` the offer's `id` (and `step_index` 0), and the run goes on
with ordinary steps and, at the end, a second `task.completed`. Going back
to start instead closes the connection; `task.cancel` ends it too. A goal
that already asked to book or pay gets no offer: the run goes straight on.

**`coming` is additive and optional** (added 2026-10-15). On a checklist
line, the lines the backend expects to run by itself after it, in order —
after "Filling in where you're starting from": `["Filling in where you're
going", "Opening the calendar", "Choosing 15 October", "Searching"]` — so
the overlay can show what is next. It is what the plan expects, not a
promise: a line that does not work turns into a question, and the list ends
at anything that will ask.

**`note` is additive and optional** (added 2026-10-14). What was wrong with
the last answer, in one sentence — "I couldn't find a station called
Narnia." — beside the question asked again, which reads on its own. The
overlay clears it once a valid answer is chosen from a list; a typed answer's
note stays until it is sent and checked.

**`stage` is additive and optional, and so is `task.started.stages`**
(added 2026-10-14). `task.started` names the task's stages once — trains:
`["From", "To", "Day", "Search", "Trains"]` — and each step says which it is
in, by position. The overlay shows the names in place of a count, which grew
every time a question was asked again. A question asked again stays in its
stage. A step without `stage` is in the stage before it; a task without
`stages` shows none.

**`step_kind` is additive and optional** (added 2026-10-07). What the step is
about — `date`, `place`, `choose`, `type`, `read` or `confirm` — so the overlay
can put one plain icon beside it. The backend sends it on every step; a sender
that omits it gets no icon, and nothing else changes.

**A field's `options` is additive and optional** (added 2026-10-06, the kind
of change CLAUDE.md allows without a ratification session). When a field's
answer is one of a known list — the train search's own stations, read from the
site before anything on it is touched — the backend sends the list, and
`type` is `choice`:
`{ "id": "origin", "label": "From", "type": "choice", "value": "", "options": ["LAHORE JN.", "LAHORE CANTT", …] }`.
The overlay shows nothing from it until something is typed, then the few that
match as buttons; the answer still comes back as text in `input_values`, and
the backend matches it to the list. Absent or empty means any text, as before.

`findings` is what the task has been asked to find out, as far as it has got —
`[{ "label": "Your bill", "value": "14,382", "values": ["14,382"] }]`. Empty
for a task that changes something rather than finding something out, which is
most of them.

`value` is one line and `values` is every value the page gave that label, in
page order. They differ when a results table has a row per result: `value`
reads `2DN, 14DN` and stops at four with `and 2 more`, while `values` holds
all of them. The step screen shows `value`, because a run in progress shows
its finding in large type beside the instruction; the closing screen shows
`values`, because it is the answer.

**`values` is additive and optional** (added 2026-09-19, and the kind of
change CLAUDE.md allows without a ratification session). A sender that omits
it means `[value]`, and a reader that ignores it behaves exactly as before.

`values` drops a repeated value, so two findings' `values` cannot be paired by
position: two trains with one journey time give two trains and one time.
**`rows`** carries the results whole, on the **first finding of a message
only**: one list per result, in page order, repeats kept, with one cell per
finding in that message, in the same order as the findings, and `""` where the
page's row had nothing for it:

```json
[{ "label": "Train", "value": "13UP, 39UP", "values": ["13UP", "39UP"],
   "rows": [["13UP", "6 h 6 min"], ["39UP", "6 h 6 min"]] },
 { "label": "Journey", "value": "6 h 6 min", "values": ["6 h 6 min"] }]
```

Absent or empty when the values did not come from a table. **`rows` is
additive and optional** (added 2026-10-05, same rule as `values`): a reader
that ignores it behaves exactly as before, and the closing screen reads it
when it is there.

`label` is for a person to read, not the page's own column heading: the
billing replica calls that column `P/WITHIN`. The plan supplies the readable
name, because only the plan knows what the goal was about.

### `step.failed`
Added 2026-09-09. A step did not work and the run is **carrying on past it**.
```json
{
  "step_index": 2,
  "instruction": "Choose where you are travelling to.",
  "reason": "fill on 'To' failed: Locator.fill: Timeout 10000ms exceeded",
  "strategies_tried": 2
}
```
The loop absorbs a first failure: the planner is told, and may choose
differently next time. Before this message existed it told the *frontend*
nothing at all, so a user saw step 2, then step 3, with no way to tell a
skipped step from a completed one — and neither could anyone reading a
transcript. That cost a day of misdiagnosis on the first live run
(EVALUATION.md, case 5).

`instruction` is the same wording the user was already shown for that step,
so the message names something they recognise rather than an internal target.
`reason` is the failure as the loop saw it. `strategies_tried` is how many
routes were attempted before giving up on the step — 2 today, always.

Not the same thing as `error`. `error` is the harness failing; this is the
task failing at something and continuing. It is shown quietly and briefly,
not as an alarm.

A second consecutive failure ends the run with `help.requested` instead, so
these two never describe the same moment.

### `load.updated`
```json
{ "score": 0.72, "level": 2, "reason": "high element count, two backtracks" }
```
`score` is 0.0–1.0. `level` is 1, 2 or 3. `reason` is for logs and for the
ablation analysis — never shown to the user.

### `page.preview`
Sent only in response to `trust.requested`.
```json
{
  "screenshot": "<base64 png>",
  "highlight": { "x": 412, "y": 260, "w": 180, "h": 44 },
  "caption": "I'm typing your consumer number here."
}
```
Every password box on the page is painted over in `screenshot` before it is
sent (2026-10-07): boxes of type `password`, and boxes that autocomplete a
current or new password, so a "show password" switch does not uncover one.

### `help.requested`
```json
{ "reason": "Could not find the submit button after two attempts",
  "suggestion": "Can you click it for me? I'll carry on from there." }
```

### `task.completed`
```json
{ "summary": "Registered for CS-401.", "duration_ms": 48200,
  "steps_taken": 6, "llm_calls": 4, "replayed": false,
  "findings": [{ "label": "Your bill", "value": "14,382" }],
  "explanation": "Your bill is 14,382, and it is due on 15-09-2026." }
```
`explanation` (optional, added 2026-10-03) is one plain sentence the closing
screen shows above the result. The backend builds it only from values the page
returned; it is absent when nothing can be said safely. The overlay never
writes it itself. (In practice `summary` is the goal followed by the final URL,
which tests and logs read to see where a run ended; the closing screen does not
show it.)
`findings` is the answer, when the task had one, and the closing screen is
built from it. A task that looked something up and ends without saying what it
found has not finished from the user's side of the screen.

Accumulated across the run rather than read from the last page: the answer is
often not on the page the task ends on. The billing amount is on the results
page, and the run then opens the detail page where that column does not exist.

`heading` is additive and optional (added 2026-10-14): what the results are
for, from what the person asked and agreed — "Lahore Cantt to Karachi Cantt,
Thursday 15 October" — never from the page. Absent: no heading.

`keep` is additive and optional (added 2026-10-18): `{ "label": "My bill" }`,
offered **once** — "Shall I keep this on your home screen as My bill?" — when
the task looked up a bill or a journey, is not already one of the person's
tiles, there is room for another (three at most), and was not itself run from
a tile. The run stays open for the answer, as for `offer` (it closes itself
after ten minutes). Kept: a `step.response` with `"action_id": "keep"` and the
name as `input_values.label`; the backend keeps the tile and goes on waiting
for `offer`, if there is one. Declined: nothing is sent.
```json
{ "step_index": 0, "action_id": "keep", "input_values": { "label": "My bill" } }
```

### `task.failed`
```json
{ "reason": "Portal timed out", "recoverable": true }
```

### `error`
```json
{ "code": "PERCEPTION_TIMEOUT", "message": "Page did not settle in 10s" }
```

---

## Frontend to backend

### `task.start`
```json
{ "goal": "Pay my electricity bill", "input_mode": "text" }
```
`input_mode` is `text` | `voice`.

`goal` is what the task *is*, and since 2026-09-21 it also decides **which**
task, if any. The backend classifies it — one call to the configured model,
keywords if there is none — and runs the matching flow with the goal as
typed, or answers with `goal.answered` and starts nothing. Configuration no
longer chooses the task.

**Changed on 2026-09-21, and needs ratifying with the rest:** a `goal` that
is empty or whitespace used to fall back to the configured flow, "so a
frontend that omits it still gets a working task". It is now answered as a
`greeting`. An empty box is nobody asking for anything, and with a backend
configured for billing the old rule looked up a bill nobody had asked about.

`flow` is **additive and optional** (2026-09-21): `registration` | `billing`
| `railways`. The overlay sets it when the person picked a flow — pressing a
card, or answering a `clarify` — and the backend then runs exactly that flow
without classifying again. Any other value is ignored and the goal is
classified as usual.
```json
{ "goal": "I need to pay for my course", "input_mode": "text", "flow": "billing" }
```

`start_level` is **additive and optional** (2026-10-18): `1` | `2` | `3`, the
level the person chose as comfortable in the overlay's welcome, kept on their
computer. The backend's level rules start the task there — a heavy page still
starts at 3 — and come back to it after calm steps, where they came back to 2.
Absent: 2, as before. The overlay sends nothing else from the profile; the
person's name never leaves it.
```json
{ "goal": "Check my electricity bill", "input_mode": "text", "flow": "billing", "start_level": 1 }
```

`tile` is **additive and optional** (2026-10-18): the id of one of the
person's own tiles (`history.offered.tiles`). The backend runs that tile's
flow with the details kept with it, and asks only what can change — the day
of a journey. The goal is the tile's name and is not classified, and nothing
kept is read by, or sent to, a model. An id it does not hold is ignored and
the goal is taken as usual.
```json
{ "goal": "My bill", "input_mode": "text", "flow": "billing", "tile": "3f9a1c2e7b40" }
```

### `step.response`
```json
{ "step_index": 2, "action_id": "confirm",
  "input_values": { "consumer_no": "04141234567" } }
```
`action_id` must match an `id` from the corresponding `step.presented`.

### `level.override`
```json
{ "level": 3, "locked": true }
```
User's manual control. While `locked` is true the estimator must not change
the level.

**`by`** is additive and optional (2026-09-25): `person` | `overflow`. The
overlay also moves the level itself when a step will not fit the window — one
level towards the compact level 1, once per step — and says so with
`by: "overflow"`, so the backend's level rules know what is on screen. A
guard move never becomes the lock: it carries the current `locked` unchanged,
and the next step is shown at the person's own level again. Omitted means
`person`, which is what every override was before.
```json
{ "level": 1, "locked": false, "by": "overflow" }
```

### `trust.requested`
```json
{}
```
Since 2026-10-07 the overlay also sends it, quietly, when each step arrives,
and shows the picture softened behind the step. No message changed: the
backend answers it the same way whoever asked. Only the person pressing
"What are you doing?" counts as asking for help in `telemetry`.

### `task.cancel`
```json
{}
```

### `tile.change`
Added 2026-10-18. **Pending agreement** — a new message type, with the rest
listed in HANDOVER.md. The person renaming, moving or removing one of their own
tiles from the home screen, or clearing them all (the reset). Answered with
`history.offered`, whole, as the tiles now stand; a change the backend cannot
make (an id it does not hold, an empty name) is answered the same way, with
nothing changed.
```json
{ "action": "rename", "id": "3f9a1c2e7b40", "label": "Electricity" }
{ "action": "move", "id": "3f9a1c2e7b40", "to": 0 }
{ "action": "remove", "id": "3f9a1c2e7b40" }
{ "action": "clear" }
```
`to` counts from 0 at the left. Read only before a task starts, on the home
screen; one sent during a task is ignored.

`clear` is the reset, "Forget me and start again", and its only sender
(2026-10-21, no field changed): the backend deletes the tiles and every saved
sign-in, and from then on offers no goal asked before it in `history.offered`
— the goals stay in the replay store, never on screen. Until a `clear` is
answered, the overlay shows no `history.offered` from before it, and says it
again on each new connection.

### `telemetry`
Channel B signals for the estimator. Sent on every step response, and on a
timer while waiting (every 3s as of 2026-09-20).
```json
{
  "step_index": 2,
  "hesitation_ms": 4200,
  "cursor_path_ratio": 3.8,
  "backtracks": 1,
  "rereads": 2,
  "help_presses": 0,
  "answered": true
}
```
`cursor_path_ratio` is total cursor path length divided by straight-line
distance — 1.0 is a direct move, higher means wandering.

**`answered`** is additive and optional (2026-09-20): true on the sample that
goes with the step response, absent or false on a timer sample. A step that
took someone a while leaves a trail of timer samples and one answered one, and
the trail is the part worth keeping.

Every counter restarts when a step is presented, and nothing is sent while no
step is waiting. The sender is `frontend/src/telemetry.ts`, and it is the only
place any of these are defined:

| Field | How it is measured |
|---|---|
| `hesitation_ms` | from the step being presented to the sample |
| `cursor_path_ratio` | pointer path length ÷ distance from where it started to where it ended; 1.0 when it never moved |
| `backtracks` | consecutive pointer segments (each ≥ 8px) turning by more than about 120° |
| `rereads` | the pointer re-entering the step's text after having left it |
| `help_presses` | presses of "What are you doing?" during this step |

The backend never replies to it. It is written down beside the page features
of the step it belongs to (`backend/estimator/pairing.py`), and nothing reads
it back yet — there is no estimator, by decision (DECISIONS.md, 2026-09-19).

**No keystrokes, no field values and no coordinates cross the boundary.** The
cursor becomes two scalars in the renderer before anything is sent.

---

## Show me once (2026-11-04)

Added 2026-11-04 on `feat/show-me-once`, after the freeze, by Raham's decision
(DECISIONS.md, *"Show me once" goes in after the feature freeze*). **Pending
agreement: Nahail and Aly.** Every change is additive. A side that ignores all
of it works as it did on 2026-11-03: no tile appears, nothing asks to teach.

**For Nahail and Aly, the whole list:**

| Change | Kind | Direction |
|---|---|---|
| `teach.start` | new message type | frontend -> backend |
| `teach.answer` | new message type | frontend -> backend |
| `teach.watching` | new message type | backend -> frontend |
| `routine.export` | new message type | frontend -> backend |
| `routine.file` | new message type | backend -> frontend |
| `routine.import` | new message type | frontend -> backend |
| `history.offered.routines` | optional field, new shape `TaughtTile` | backend -> frontend |
| `task.start.routine` | optional field | frontend -> backend |
| `step.presented.routine` | optional field | backend -> frontend |
| `teach.watching.question.kind` (stage 2) | optional field, `"typed"` or `"day"` | backend -> frontend |
| `tile.change` with a routine's `id` | no field changed: a routine is renamed or removed like a tile | frontend -> backend |
| `error` code `ROUTINE_NOT_READ` | new code | backend -> frontend |
| `teach.watching.kept` (2026-11-10) | optional field, a list of short lines | backend -> frontend |
| `teach.watching.start_again` (2026-11-10) | optional field, true or false | backend -> frontend |
| `teach.answer.action` `"undo"` and `"restart"` (2026-11-10) | two more values of an existing field | frontend -> backend |

*To undo any one:* drop it on both sides. Nothing else reads it.

### `teach.start`
The helper pressed "Start watching" on the screen behind "Show me once". Sent
on a connection where no task has started, in place of `task.start`. The
backend opens `url` in the site view and starts watching; the overlay steps
aside to a bar at the top of the window until `teach.watching` stops coming —
on any `step.presented`, `help.requested`, `task.completed` or `task.failed`.
```json
{ "url": "http://127.0.0.1:5100/" }
```
Answered with `help.requested` at once, and nothing watched, when there is no
room for another tile (the home screen's row of three) or this machine cannot
encrypt one.

### `teach.watching`
What the bar says, sent whenever it changes.
```json
{
  "lines": ["Ask about cookies, and press Accept all cookies if the answer is yes.",
            "Type 04141234567890 in Reference No."],
  "question": { "step": 1, "label": "Reference No.", "value": "04141234567890" },
  "pointing": false,
  "note": null
}
```
`lines` is what has been kept so far, in plain words (`voice.routine_line`).
`question` is the one typed value not yet asked about: the same every time, or
ask each time? `value` is what the helper typed, so they can decide; a password
is never asked about and never sent. Its optional `kind` (stage 2, additive) is
`"typed"`, or `"day"` for a day picked on a calendar, which is asked about the
same way; absent, typed. `pointing` is true once the helper has
pressed Finish: the next click on the page is the answer, and nothing is let
through. `note` says what was wrong with the last press of the bar ("First,
tell me whether what you typed is the same every time.").

Since 2026-11-10 (`feat/interface-teach-entry`, additive, **pending Nahail and
Aly**) two more optional fields:
```json
{ "lines": ["..."], "kept": ["Pressed Accept all cookies.", "Typed in Reference No."],
  "start_again": false, "question": null, "pointing": false, "note": null }
```
`kept` is each thing kept so far in a few words, newest last, one for one
with `lines`, for the bar's list (`voice.kept_line`): what was done and where,
never what was typed; a password is `"Typed a password."` and nothing more.
A backend that omits it gets the bar as it was, the count and the last of
`lines`, and no Undo. `start_again` is true when the last thing could not be
taken back (below): the website is not on the page it was, nothing on it is
let through, the list stays as it was, and the bar offers Start again in
place of Undo last thing and Finish; absent, false.

### `teach.answer`
The helper's press on the bar.
```json
{ "action": "ask", "step": 1 }
{ "action": "same", "step": 1 }
{ "action": "finish" }
{ "action": "cancel" }
```
`finish` with a question open, or nothing shown, is answered with a `note`.
`cancel` (or `task.cancel`) is answered with `task.failed` and the stop reason.

Since 2026-11-10 (additive, **pending Nahail and Aly**) two more actions:
```json
{ "action": "undo" }
{ "action": "restart" }
```
`undo` takes the last thing off the list. A typed value is taken out of its
box as well; a press that moved the website to another page takes the
website back, and comes off the list only once the page is really the one
it was pressed on, with what the list says was typed there in its boxes
again. When it cannot be — the page cannot be reached by going back, or a
choice was made from a list, a day picked or a password typed on it — the
answer is `teach.watching` with `note` saying so and `start_again: true`.
`restart` opens the first page again with nothing kept, and watching goes on.
Both are ignored while pointing. A backend from before them ignores them.

**After the answer is pointed at** the backend sends `task.started` (goal "Show
me once") and one `step.presented` with `routine`: the read-back. Its two fields
are `name` (the name on the home screen) and `answer` (what the answer is
called); its actions are "Keep it" (`confirm`) and the usual stop. Kept, it ends
with `task.completed` (`explanation` names the tile); no name, and it is asked
again with a `note`.

### `step.presented.routine`
Additive and optional: the read-back's lines, in order, the last one what is
read at the end. Absent on every other step.

### `history.offered.routines`
Additive and optional: the routines, as `TaughtTile`s, in the order they were
kept. They share the home screen's row of three with `tiles`.
```json
{ "goals": [], "tiles": [], "routines": [
  { "id": "a1b2c3d4e5f6", "label": "My bill", "site": "127.0.0.1:5100" } ] }
```

### `task.start.routine`
Additive and optional: run a routine by its id. The goal is its name and is not
classified. What the helper said changes is asked, one question at a time,
before the site is touched; then it runs as the checklist.
```json
{ "goal": "My bill", "input_mode": "text", "routine": "a1b2c3d4e5f6" }
```

### `routine.export` and `routine.file`
Save a routine to a file, from "Change my tiles". Answered with `routine.file`:
a suggested file name and the file's whole text, which the overlay saves where
the helper chooses. In the file, every value the helper typed is asked for
instead: a shared routine is for someone else.
```json
{ "id": "a1b2c3d4e5f6" }
{ "label": "My bill", "name": "my-bill.simba-routine.json", "file": "{...}" }
```

### `routine.import`
A routine read from a file someone shared, as its whole text. Answered with
`history.offered`, with it there when it was kept; when it was not, first an
`error` with code `ROUTINE_NOT_READ` and a plain message saying why (not a
routine, a typed value in it, no room).
```json
{ "file": "{\"format\": \"simba-routine\", \"version\": 1, ...}" }
```
Since 2026-11-04 (`fix/show-me-once`) a step in the file may carry three more
optional keys, still version 1: `row` (the column naming the row the person
chooses, with `{}` in the step's label), `opens` (a press whose words say book
that only opens a page) and `shows` (the page's labels for a final screen's
details). Only the backend reads the file; the overlay passes it through.
A SIMBA without them reads the file and stops honestly at the row press.

## Any website (2026-11-13)

Added 2026-11-13 on `feat/catalogue-any-site`, by the advisor's direction of
12 November, approved by Raham (DECISIONS.md, *The advisor's direction of 12
November*). **Pending agreement: Nahail and Aly.** Every change is additive. A
side that ignores all of it works as it did on 2026-11-12: no list, no
website box, and a goal is routed to the three flows or answered.

**For Nahail and Aly, the whole list:**

| Change | Kind | Direction |
|---|---|---|
| `history.offered.sites` and `.genres` | optional fields, new shapes `CatalogueSite`, `CatalogueTask` | backend -> frontend |
| `task.start.site` | optional field | frontend -> backend |
| `goal.answered.kind` `"not_yet"` | one more value of an existing field | backend -> frontend |
| `goal.answered.site` | optional field | backend -> frontend |
| `site.add` | new message type | frontend -> backend |
| `error` code `SITE_NOT_ADDED` | new code | backend -> frontend |
| `goal.answered.kind` `"not_allowed"` (phase 2) | one more value of an existing field | backend -> frontend |
| `step.presented.worked_out_by` (phase 2) | optional field | backend -> frontend |
| `help.requested.teach_site` (phase 2) | optional field | backend -> frontend |
| `CatalogueTask.taught_on` (phase 3) | optional field | backend -> frontend |
| `handover` (phase 4) | new message type, shape `HandOver` | backend -> frontend |
| `handover.done` (phase 4) | new message type, shape `HandoverDone` | frontend -> backend |
| `ai.setup` (phase 7b) | new message type, shape `AiSetup` | frontend -> backend |
| `ai.status` (phase 7b) | new message type, shape `AiStatus` | backend -> frontend |
| `history.offered.ai` (phase 7b) | optional field, shape `AiStatus` | backend -> frontend |
| `task.start.routine` with `site` (phase 3) | no field changed: the routine runs on `site` | frontend -> backend |

*To undo any one:* drop it on both sides. Nothing else reads it.

### `history.offered.sites` and `.genres`
The websites SIMBA can work with, for the list on the home screen's left, and
the genres to group them under, in order. Read from `data/catalogue.json`
(shipped) and `data/catalogue.local.json` (added in the app, never
committed). A routine a helper taught appears as a `taught` task on the site
it was taught on, by host and port.
```json
{ "goals": [], "genres": ["Travel", "Bills"],
  "sites": [
    { "id": "pakrailways", "name": "Pakistan Railways",
      "address": "https://www.pakrailways.gov.pk/train", "genre": "Travel", "added": false,
      "tasks": [ { "label": "Find train times", "goal": "Find train times",
                   "how": "built-in", "flow": "railways" } ] },
    { "id": "iesco-bill", "name": "IESCO electricity bill",
      "address": "https://bill.pitc.com.pk/iescobill", "genre": "Bills", "added": false,
      "tasks": [ { "label": "Look up my bill", "goal": "Look up my electricity bill",
                   "how": "ai" } ] } ] }
```
`how` is `built-in` (a written plan: send `flow`), `ai` (the AI planner works it
out on the live page) or `taught` (send `routine`, its id).

### `task.start.site`
The website to work on: a listed site's address, or one the person typed (the
backend makes `gov.uk` into `https://gov.uk/` and refuses anything that is
not `http` or `https`). With no `flow`, the backend routes the goal as usual;
a built-in flow runs only when the site is that flow's own; anything else is
done on `site` by the AI planner. A goal with no `site` that has an address
written in it ("bank holidays on gov.uk") is treated as if `site` were that
address.
```json
{ "goal": "When is the next bank holiday?", "input_mode": "text",
  "site": "https://www.gov.uk/bank-holidays" }
```

### `goal.answered` `not_yet`
A goal on a website SIMBA cannot do yet — until the AI planner is set up, every
goal on a site with no built-in plan. `site` is where the overlay offers a
helper's "Show me once". `flows` is empty. No task starts.
```json
{ "kind": "not_yet", "goal": "Track my passport application", "flows": [],
  "site": "https://dgip.gov.pk/" }
```

### Phase 2: the AI planner on a website (2026-11-13)
Once an AI provider is set up, a goal on a website with no plan is not
answered `not_yet`: it runs, as an ordinary task, with the AI planner choosing
each move. Three additions say what the person needs to know:

- `goal.answered` `not_allowed`: the website's robots.txt asks programs not to
  use that page (or would not say), so nothing is opened. `site` is the page.
- `step.presented.worked_out_by`: which provider chose this move, `"Gemini"`
  or `"Groq"`, shown small under the step at every level. Absent for a written
  plan, a routine and replay.
- `help.requested.teach_site`: the AI planner could not do it; the stuck
  screen offers a helper's "Show me once" on this address.

The answer to an open goal is a question first — "The page says: 26 December.
Is this what you wanted?" — asked only after SIMBA has found those exact words
on the page; "Yes, that's it" closes the task with it as the finding, "No,
keep looking" goes back to the planner.

### Phase 3: a taught routine on a sister website (2026-11-13)
A routine a helper taught is listed, as a `taught` task, on the website it was
taught on and on every other listed website of the same genre; on those it
carries `taught_on`, the name of the website where it was taught. Pressed
there, the overlay sends `task.start` with `routine` and that website's
address as `site`, and the backend runs the routine there: its start, and each
move's expected address under the start's path, moved to the new address
(`routines.moved_to`). Every move is still found by role and label and checked;
a site laid out differently stops as a changed site does. robots.txt is asked
first, and `not_allowed` answers a no.

### Phase 4: the real page handed to the person (2026-11-13)
`handover` is sent when the page is the person's to act on: `reason` is
`payment` (a press that pays on a live site, after its final screen; a page
asking for card or bank details; a one-time code) or `check` (a CAPTCHA, a
check that a person is there). `sentence` is what the bar says; `site` the
page's host. The overlay steps aside to a bar, the host shows the website
below it (`[simba] host bar 160`), and nothing on the page is read until the
person answers `handover.done` with `done` or `cancel` (or `task.cancel`).
After `done`, a payment ends in `task.completed` quoting the page's own words
(`heading` "The website says it went through.", `caveat` that SIMBA did not
see or keep the card details) or in `help.requested` with `unconfirmed` when
the page says nothing either way; a check goes on with the task. `cancel`
ends in `task.failed`: stopped, nothing changed.
```json
{ "reason": "payment", "site": "127.0.0.1:5100",
  "sentence": "Your turn: pay on the page below. Type your card details or code there yourself. I don't see or keep them. Press I've finished when it's done." }
```
```json
{ "action": "done" }
```

### Phase 7b: the AI provider, set up in the app (2026-11-13)
`history.offered.ai` says whether an AI provider is set up (`configured`), its
name, and — when it was set up in the app — the key's last four characters
(`ends_with`); present, the first-time setup asks about it. `ai.setup` sends
the provider (`gemini`, `groq`, or `openai` with `base_url` and `model`) and the
key, once; the backend keeps it encrypted with this Windows account's key,
checks it with one small question, and answers `ai.status` with `check`: `ok`,
`key`, `limit`, `network`, `other`, or what was wrong with the setup itself
(`provider`, `address`, `model`, `vault`). The key never comes back.
```json
{ "provider": "gemini", "key": "<the key>" }
```
```json
{ "configured": true, "provider": "Gemini", "ends_with": "9f3c", "check": "ok" }
```

### `site.add`
"Add a website" on the home screen. Answered with `history.offered` as it now
stands, or `error` with code `SITE_NOT_ADDED` and, as its `message`, the reason
the overlay says in words: `name` (none given), `address` (not a web
address), `listed` (already in the list), `full` (30 added already).
```json
{ "name": "My clinic", "address": "clinic.example.pk", "genre": "Health" }
```

## Notes

- Timestamps are epoch milliseconds.
- Unknown message types are logged and ignored, never fatal.
- The mock harness (`tools/mock_backend.py`) replays a scripted sequence of
  these messages so the frontend can be built with no backend running. Keep it
  in sync with this file — it is also the demo-day fallback.
