/**
 * All the state the harness holds, and the one place messages are applied.
 *
 * Every backend-to-frontend type in CONTRACT.md is handled explicitly. An
 * unknown type is logged and ignored, never fatal.
 */

import { create } from "zustand";

import type {
  AnyEnvelope,
  Level,
  ErrorPayload,
  HelpRequested,
  LoadUpdated,
  PagePreview,
  State,
  StepPresented,
  StepResponse,
  TaskCompleted,
  TaskFailed,
  TaskStarted,
} from "@shared/schema";

import { BackendConnection, DEFAULT_WS_URL, type ConnectionStatus } from "./connection";

export interface LogEntry {
  seq: number;
  type: string;
  ts: number;
  payload: unknown;
  note?: string;
}

interface Store {
  status: ConnectionStatus;
  statusDetail?: string;
  wsUrl: string;

  task: TaskStarted | null;
  state: State | null;
  step: StepPresented | null;
  load: LoadUpdated | null;
  preview: PagePreview | null;
  help: HelpRequested | null;
  completed: TaskCompleted | null;
  failed: TaskFailed | null;
  error: ErrorPayload | null;

  log: LogEntry[];

  /** Detail level. Level 2 until the estimator or the user says otherwise. */
  level: Level;
  /** The shown step has been answered and is waiting to be replaced. */
  answered: boolean;
  /** The development view, off unless someone asks for it by keyboard. */
  debug: boolean;

  toggleDebug: () => void;
  connect: (url?: string) => void;
  setWsUrl: (url: string) => void;
  startTask: (goal: string) => void;
  respond: (actionId: string, values: Record<string, string>) => void;
  cancel: () => void;
}

const EMPTY = {
  task: null,
  state: null,
  step: null,
  answered: false,
  load: null,
  preview: null,
  help: null,
  completed: null,
  failed: null,
  error: null,
};

export const useStore = create<Store>((set, get) => {
  const append = (entry: LogEntry) =>
    set((current) => ({ log: [...current.log, entry] }));

  const connection = new BackendConnection({
    onStatus: (status, detail) => set({ status, statusDetail: detail }),

    onSequenceGap: (expected, received) => {
      const note = `sequence gap: expected seq ${expected}, got ${received}`;
      console.warn(`[simba] ${note}`);
      append({ seq: received, type: "warning", ts: Date.now(), payload: {}, note });
    },

    onMessage: (message: AnyEnvelope) => {
      apply(message, set);
      append({
        seq: message.seq,
        type: message.type,
        ts: message.ts,
        payload: message.payload,
      });
    },
  });

  return {
    status: "idle",
    wsUrl: DEFAULT_WS_URL,
    log: [],
    level: 2,
    debug: false,
    ...EMPTY,

    toggleDebug: () => set((current) => ({ debug: !current.debug })),

    setWsUrl: (wsUrl) => set({ wsUrl }),

    connect: (url) => {
      set({ log: [], ...EMPTY });
      connection.connect(url ?? get().wsUrl);
    },

    startTask: (goal) => {
      set({ ...EMPTY });
      // A dead socket is the usual state when the backend was started after
      // the window, and after every completed task, since the backend closes
      // the socket when it is done. Reconnect and let the send queue behind it.
      //
      // The log is cleared with the reconnect, not with the task: seq is a
      // per-connection counter, so keeping entries across a reconnect would
      // show two runs interleaved with duplicate numbers.
      if (!connection.isOpen) {
        set({ log: [] });
        connection.connect(get().wsUrl);
      }
      connection.startTask(goal);
    },

    respond: (actionId, values) => {
      const step = get().step;
      if (!step) return;
      const response: StepResponse = {
        step_index: step.step_index,
        action_id: actionId,
        input_values: values,
      };
      connection.respondToStep(response);
      // Mark it answered rather than clearing it. Clearing would drop the
      // screen back to the goal for the few milliseconds before the next
      // message lands, and that flash is both ugly and — with an
      // AnimatePresence that waits for an exit — enough to strand the
      // transition and leave the column blank.
      set({ answered: true });
    },

    cancel: () => connection.cancelTask(),
  };
});

/** Apply one backend message. Every type in CONTRACT.md, explicitly. */
function apply(message: AnyEnvelope, set: (partial: Partial<Store>) => void): void {
  switch (message.type) {
    case "task.started":
      set({ task: message.payload as TaskStarted, completed: null, failed: null });
      return;
    case "state.changed":
      set({ state: (message.payload as { state: State }).state });
      return;
    case "step.presented":
      set({ step: message.payload as StepPresented, answered: false });
      return;
    case "load.updated": {
      const load = message.payload as LoadUpdated;
      // The estimator drives the level. Nothing sends this yet.
      set({ load, level: load.level });
      return;
    }
    case "page.preview":
      set({ preview: message.payload as PagePreview });
      return;
    case "help.requested":
      set({ help: message.payload as HelpRequested, step: null });
      return;
    case "task.completed":
      set({ completed: message.payload as TaskCompleted, step: null });
      return;
    case "task.failed":
      set({ failed: message.payload as TaskFailed, step: null });
      return;
    case "error":
      set({ error: message.payload as ErrorPayload });
      return;
    default:
      // Unknown types are logged and ignored, never fatal (CONTRACT.md).
      console.warn(`[simba] ignoring unknown message type: ${message.type}`);
  }
}
