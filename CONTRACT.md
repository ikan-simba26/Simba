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
  "steps_taken": 6, "llm_calls": 4, "replayed": false }
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

`goal` is what the task *is*. The backend runs it as sent; it does not
substitute a goal of its own. Where the backend is configured for a
particular site, that configuration chooses the site and any pre-written
plan, never the goal. A `goal` that is empty or whitespace falls back to
whatever the backend was configured with, so a frontend that omits it still
gets a working task.

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
timer while waiting.
```json
{
  "step_index": 2,
  "hesitation_ms": 4200,
  "cursor_path_ratio": 3.8,
  "backtracks": 1,
  "rereads": 2,
  "help_presses": 0
}
```
`cursor_path_ratio` is total cursor path length divided by straight-line
distance — 1.0 is a direct move, higher means wandering.

---

## Notes

- Timestamps are epoch milliseconds.
- Unknown message types are logged and ignored, never fatal.
- The mock harness (`tools/mock_backend.py`) replays a scripted sequence of
  these messages so the frontend can be built with no backend running. Keep it
  in sync with this file — it is also the demo-day fallback.
