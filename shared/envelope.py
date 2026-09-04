"""Envelope construction, mirrored from CONTRACT.md.

Every message in both directions is wrapped in the same envelope. It is built
in exactly one place so the two ends cannot drift apart. Keep this in step
with `shared/envelope.ts`.

`seq` is deliberately not tracked here: it is a per-connection monotonic
counter, independent per direction, so it belongs to whatever owns the
connection.
"""

import time
from typing import Any

from pydantic import BaseModel

PROTOCOL_VERSION = 1


def envelope(
    message_type: str,
    task_id: str,
    seq: int,
    payload: BaseModel | dict[str, Any],
    ts: int | None = None,
) -> dict[str, Any]:
    """Wrap one payload in a contract envelope."""
    return {
        "v": PROTOCOL_VERSION,
        "type": message_type,
        "task_id": task_id,
        "seq": seq,
        "ts": now_ms() if ts is None else ts,
        "payload": payload.model_dump() if isinstance(payload, BaseModel) else payload,
    }


def now_ms() -> int:
    """Epoch milliseconds — the contract's timestamp unit."""
    return int(time.time() * 1000)
