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

### `help.requested`
```json
{ "reason": "Could not find the submit button after two attempts",
  "suggestion": "Can you click it for me? I'll carry on from there." }
```

### `task.completed`
```json
{ "summary": "Registered for CS-401.", "duration_ms": 48200,
  "steps_taken": 6, "llm_calls": 4, "replayed": false,
  "findings": [{ "label": "Your bill", "value": "14,382" }] }
```
`findings` is the answer, when the task had one, and the closing screen is
built from it. A task that looked something up and ends without saying what it
found has not finished from the user's side of the screen.

Accumulated across the run rather than read from the last page: the answer is
often not on the page the task ends on. The billing amount is on the results
page, and the run then opens the detail page where that column does not exist.

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

### `task.cancel`
```json
{}
```

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

## Notes

- Timestamps are epoch milliseconds.
- Unknown message types are logged and ignored, never fatal.
- The mock harness (`tools/mock_backend.py`) replays a scripted sequence of
  these messages so the frontend can be built with no backend running. Keep it
  in sync with this file — it is also the demo-day fallback.
