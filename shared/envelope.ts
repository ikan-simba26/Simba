/**
 * Envelope construction, mirrored from CONTRACT.md.
 *
 * Every message in both directions is wrapped in the same envelope. It is
 * built in exactly one place so the two ends cannot drift apart. Keep this in
 * step with `shared/envelope.py`.
 *
 * `seq` is deliberately not tracked here: it is a per-connection monotonic
 * counter, independent per direction, so it belongs to whatever owns the
 * connection.
 */

import type { Envelope, MessageType } from "./schema";

export const PROTOCOL_VERSION = 1;

/** Epoch milliseconds — the contract's timestamp unit. */
export function nowMs(): number {
  return Date.now();
}

/** Wrap one payload in a contract envelope. */
export function envelope<T>(
  messageType: MessageType,
  taskId: string,
  seq: number,
  payload: T,
  ts?: number,
): Envelope<T> {
  return {
    v: PROTOCOL_VERSION,
    type: messageType,
    task_id: taskId,
    seq,
    ts: ts ?? nowMs(),
    payload,
  };
}
