/**
 * The WebSocket to the backend, framed as contract envelopes.
 *
 * Every message in and out goes through `shared/envelope.ts`, so the two ends
 * cannot drift on the wrapper. `seq` is a per-connection monotonic counter,
 * independent per direction; a gap means a dropped message, which is logged
 * rather than silently ignored (CONTRACT.md).
 */

import { envelope } from "@shared/envelope";
import type {
  AnyEnvelope,
  Envelope,
  FlowName,
  Level,
  LevelOverride,
  MessageType,
  StepResponse,
  Telemetry,
  TaskStart,
} from "@shared/schema";

const FALLBACK_WS_URL = "ws://127.0.0.1:8000/ws";

/**
 * Where the backend is. Overridable with `?ws=` on the overlay's own URL so
 * a test or a second backend can be pointed at without a rebuild — the
 * overlay has no address bar and no settings, by design.
 */
export const DEFAULT_WS_URL = (() => {
  try {
    const fromQuery = new URLSearchParams(window.location.search).get("ws");
    return fromQuery || FALLBACK_WS_URL;
  } catch {
    return FALLBACK_WS_URL;
  }
})();

/** Our own task id. The backend stamps its own on messages it sends. */
const TASK_ID = "t_frontend";

export type ConnectionStatus = "idle" | "connecting" | "open" | "closed" | "error";

export interface Handlers {
  onStatus: (status: ConnectionStatus, detail?: string) => void;
  onMessage: (message: AnyEnvelope) => void;
  onSequenceGap: (expected: number, received: number) => void;
}

export class BackendConnection {
  private socket: WebSocket | null = null;
  private outgoingSeq = 0;
  private lastIncomingSeq = 0;
  /** Sends issued while the socket is still opening, flushed on open. */
  private pending: Array<() => void> = [];

  constructor(private readonly handlers: Handlers) {}

  connect(url: string = DEFAULT_WS_URL): void {
    this.close();
    this.outgoingSeq = 0;
    this.lastIncomingSeq = 0;
    this.pending = [];
    this.handlers.onStatus("connecting");

    const socket = new WebSocket(url);
    this.socket = socket;

    socket.onopen = () => {
      this.handlers.onStatus("open");
      const queued = this.pending;
      this.pending = [];
      for (const send of queued) send();
    };
    socket.onclose = () => this.handlers.onStatus("closed");
    socket.onerror = () => this.handlers.onStatus("error", `could not reach ${url}`);
    socket.onmessage = (event) => this.receive(event.data);
  }

  close(): void {
    if (this.socket) {
      this.socket.onclose = null;
      this.socket.close();
      this.socket = null;
    }
  }

  get isOpen(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  // --- sending -------------------------------------------------------------

  startTask(goal: string, flow?: FlowName, confirmEach = false): void {
    const payload: TaskStart = flow ? { goal, input_mode: "text", flow }
                                    : { goal, input_mode: "text" };
    // Only when the person asked to be asked every time (2026-10-14).
    if (confirmEach) payload.confirm_each = true;
    this.send("task.start", payload);
  }

  respondToStep(response: StepResponse): void {
    this.send("step.response", response);
  }

  cancelTask(): void {
    this.send("task.cancel", {});
  }

  /** Ask the backend what it is doing. It answers with page.preview. */
  askWhat(): void {
    this.send("trust.requested", {});
  }

  /**
   * Tell the backend the level changed on screen: the person chose it or
   * handed it back, or the overflow guard moved it (`by: "overflow"`, which the
   * backend never takes as a lock).
   */
  overrideLevel(level: Level, locked: boolean, by: "person" | "overflow" = "person"): void {
    const payload: LevelOverride = { level, locked, by };
    this.send("level.override", payload);
  }

  /**
   * Channel B for the estimator: how the person is getting on with this step.
   *
   * Sent on every step response and on a timer while one waits (CONTRACT.md).
   * The backend never answers it, so it is fire-and-forget by design — a
   * sample lost to a reconnect is one row missing from a training set, not a
   * step that fails to happen.
   */
  sendTelemetry(payload: Telemetry): void {
    this.send("telemetry", payload);
  }

  private send<T>(type: MessageType, payload: T): void {
    // Starting the backend after the window is the normal order of events, so
    // a send during connection waits rather than failing.
    if (this.socket?.readyState === WebSocket.CONNECTING) {
      this.pending.push(() => this.send(type, payload));
      return;
    }
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      this.handlers.onStatus("error", `cannot send ${type}: not connected`);
      return;
    }
    this.outgoingSeq += 1;
    const message: Envelope<T> = envelope(type, TASK_ID, this.outgoingSeq, payload);
    this.socket.send(JSON.stringify(message));
  }

  // --- receiving -----------------------------------------------------------

  private receive(raw: unknown): void {
    if (typeof raw !== "string") return;

    let message: AnyEnvelope;
    try {
      message = JSON.parse(raw) as AnyEnvelope;
    } catch {
      this.handlers.onStatus("error", "backend sent something that is not JSON");
      return;
    }

    const expected = this.lastIncomingSeq + 1;
    if (message.seq !== expected) {
      // A gap means a dropped message. Log it, don't silently continue.
      this.handlers.onSequenceGap(expected, message.seq);
    }
    this.lastIncomingSeq = message.seq;

    this.handlers.onMessage(message);
  }
}
