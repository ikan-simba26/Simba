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
  FlowName,
  GoalAnswered,
  HelpRequested,
  HistoryOffered,
  PastGoal,
  LoadUpdated,
  PagePreview,
  State,
  StepFailed,
  StepPresented,
  StepResponse,
  TaskCompleted,
  TaskFailed,
  TaskStarted,
} from "@shared/schema";

import { BackendConnection, DEFAULT_WS_URL, type ConnectionStatus } from "./connection";
import { tracker, watch } from "./telemetry";

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
  /**
   * The person pressed stop on a step, and the task has ended because they
   * chose it.
   *
   * Set the moment they press it, not when the backend replies. The backend
   * acts on nothing until it has a response, treats any response other than
   * go-ahead as a stop, and reports that stop as `task.failed` — which is the
   * contract's only way to say a task ended without completing. Waiting for
   * that message and showing it would tell someone who chose to stop that the
   * assistant had failed.
   */
  stoppedByPerson: boolean;
  error: ErrorPayload | null;
  /**
   * The most recent step the run could not do and carried on past. Shown
   * briefly and quietly — the run is still going, so this is not the stuck
   * screen and must not read like one. Deliberately *not* cleared by the
   * next `step.presented`: that arrives immediately afterwards, and clearing
   * it there would make the notice unreachable in exactly the case it exists
   * for.
   */
  stepFailure: StepFailed | null;
  /**
   * Goals this person has asked for before, offered on the home screen.
   *
   * Not cleared with a task: they are the same goals afterwards, and the
   * closing screen's "do something else" goes straight back to them.
   */
  history: PastGoal[];
  /**
   * The backend's answer to a goal that did not start a task: a greeting, a
   * polite "I can't do that", or "which of these did you mean". Nothing is
   * running while this is set; the next choice is the person's.
   */
  reply: GoalAnswered | null;
  /**
   * What the person just asked for, while the backend decides what it is.
   * Set by `startTask`, cleared by whatever answers it — a task starting, a
   * reply, an ending. Without it the screen showed nothing for as long as the
   * routing took, which with a model deciding was up to eight seconds.
   */
  asking: string | null;

  log: LogEntry[];

  /** Detail level. Level 2 until the estimator or the user says otherwise. */
  level: Level;
  /** Set by the user. While true, load.updated must not change the level. */
  levelLocked: boolean;
  /**
   * Set when something other than the user changed the level, so the
   * interface can say so. The interface never reshapes silently.
   *
   * `because` is what moved it, kept in the store for whoever is debugging.
   * It is never rendered: the words on screen come from `copy.levelNotice`,
   * by direction alone.
   */
  levelNotice: { from: Level; to: Level; because: string } | null;
  /** The shown step has been answered and is waiting to be replaced. */
  answered: boolean;
  /** The development view, off unless someone asks for it by keyboard. */
  debug: boolean;
  /** The trust panel: the user has asked to see the real page. */
  trustOpen: boolean;

  toggleDebug: () => void;
  /** Send trust.requested and open the panel when the preview lands. */
  askWhat: () => void;
  closeTrust: () => void;
  /** The user picking a level, which also locks it. */
  chooseLevel: (level: Level) => void;
  /** Give the level back to the estimator. */
  unlockLevel: () => void;
  /** Drop a level because the step does not fit. Overrides the lock. */
  simplifyForOverflow: (to: Level) => void;
  /** True once this step has already been moved for overflow. One hop only. */
  overflowHopped: boolean;
  dismissLevelNotice: () => void;
  dismissStepFailure: () => void;
  /** Back to the home screen without dropping the connection. */
  startOver: () => void;
  /**
   * Start watching the pointer and sampling on a timer. Called once, by the
   * app, and returns the function that stops it. Everything it measures is in
   * `telemetry.ts`.
   */
  watchTelemetry: () => () => void;
  connect: (url?: string) => void;
  setWsUrl: (url: string) => void;
  /**
   * Ask for something. `flow` is set when the person picked one of the things
   * offered — a card, or an answer to "which did you mean" — so the backend
   * runs exactly that and does not guess again.
   */
  startTask: (goal: string, flow?: FlowName) => void;
  respond: (actionId: string, values: Record<string, string>) => void;
  cancel: () => void;
}

/**
 * The one action id the backend treats as "go ahead". Anything else stops the
 * task (`backend/orchestrator/loop.py`, `voice.CONFIRM_ID`); `test_copy.py`
 * checks the two agree.
 */
const GO_AHEAD_ID = "confirm";

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
  stoppedByPerson: false,
  error: null,
  stepFailure: null,
  reply: null,
  asking: null,
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
    history: [],
    levelLocked: false,
    levelNotice: null,
    overflowHopped: false,
    debug: false,
    trustOpen: false,
    ...EMPTY,

    toggleDebug: () => set((current) => ({ debug: !current.debug })),

    askWhat: () => {
      // Open immediately; the panel waits for the picture rather than the
      // press feeling like it did nothing.
      set({ trustOpen: true });
      // The loudest signal channel B has: they stopped and asked.
      tracker.helpPressed();
      connection.askWhat();
    },

    closeTrust: () => set({ trustOpen: false, preview: null }),

    chooseLevel: (level) => {
      // The user's own choice needs no notice: they are looking at it.
      set({ level, levelLocked: true, levelNotice: null });
      connection.overrideLevel(level, true);
    },

    unlockLevel: () => {
      set({ levelLocked: false, levelNotice: null });
      connection.overrideLevel(get().level, false);
    },

    simplifyForOverflow: (to) => {
      const { level: from, overflowHopped } = get();
      if (from === to) return;
      // One hop per step, then stop. Watching the interface reshape itself
      // twice in a second is worse than scrolling, and a guard that keeps
      // moving is indistinguishable from one that is broken.
      if (overflowHopped) return;
      set({
        level: to,
        overflowHopped: true,
        levelNotice: { from, to, because: "this step was too long to fit" },
      });
    },

    dismissLevelNotice: () => set({ levelNotice: null }),

    dismissStepFailure: () => set({ stepFailure: null }),

    // Clears the finished task but keeps the remembered goals, so "do
    // something else" lands on the home screen rather than an empty box.
    startOver: () => set({ ...EMPTY }),

    setWsUrl: (wsUrl) => set({ wsUrl }),

    connect: (url) => {
      set({ log: [], ...EMPTY });
      connection.connect(url ?? get().wsUrl);
    },

    startTask: (goal, flow) => {
      set({ ...EMPTY, asking: goal });
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
      connection.startTask(goal, flow);
    },

    watchTelemetry: () => watch(tracker, (sample) => connection.sendTelemetry(sample)),


    respond: (actionId, values) => {
      const step = get().step;
      if (!step) return;
      const response: StepResponse = {
        step_index: step.step_index,
        action_id: actionId,
        input_values: values,
      };
      // Before the response, so the backend has the sample in hand when it
      // pairs this step with the page it was showing — and marked as the one
      // that ends the step, rather than another timer tick.
      const sample = tracker.sample();
      if (sample) connection.sendTelemetry({ ...sample, answered: true });
      tracker.stop();
      connection.respondToStep(response);
      if (actionId !== GO_AHEAD_ID) {
        // The backend stops on anything but go-ahead (loop.run_task). Say so
        // now; there is nothing to wait for.
        set({ stoppedByPerson: true, step: null, answered: true });
        return;
      }
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
type SetStore = {
  (partial: Partial<Store>): void;
  (updater: (current: Store) => Partial<Store>): void;
};

function apply(message: AnyEnvelope, set: SetStore): void {
  switch (message.type) {
    case "task.started":
      set({
        task: message.payload as TaskStarted,
        completed: null,
        failed: null,
        asking: null,
      });
      return;
    case "state.changed":
      set({ state: (message.payload as { state: State }).state });
      return;
    case "step.presented":
      // A new decision: the clock and the pointer start again (telemetry.ts).
      tracker.start((message.payload as StepPresented).step_index);
      // A new step gets its own chance to be moved for overflow.
      set({
        step: message.payload as StepPresented,
        answered: false,
        overflowHopped: false,
        // The picture was of the previous step; it is stale now.
        preview: null,
        trustOpen: false,
      });
      return;
    case "history.offered":
      set({ history: (message.payload as HistoryOffered).goals });
      return;
    case "goal.answered":
      // No task started. The socket stays open for the person's next choice.
      set({ reply: message.payload as GoalAnswered, task: null, state: null, asking: null });
      return;
    case "step.failed":
      // Not cleared here or by the step that follows: see the store field.
      set({ stepFailure: message.payload as StepFailed });
      return;
    case "load.updated": {
      const load = message.payload as LoadUpdated;
      // The estimator proposes; a locked level refuses. `reason` is for logs
      // and ablation only and is never shown to the user (CONTRACT.md).
      set((current) => {
        if (current.levelLocked || current.level === load.level) {
          return { load };
        }
        return {
          load,
          level: load.level,
          // The estimator's own reason. Not shown to the user (CONTRACT.md).
          levelNotice: { from: current.level, to: load.level, because: load.reason },
        };
      });
      return;
    }
    case "page.preview":
      set({ preview: message.payload as PagePreview });
      return;
    case "help.requested":
      // The run is over; there is no decision on screen to measure.
      tracker.stop();
      set({ help: message.payload as HelpRequested, step: null });
      return;
    case "task.completed":
      tracker.stop();
      set({ completed: message.payload as TaskCompleted, step: null });
      return;
    case "task.failed":
      tracker.stop();
      // Kept even after the person stopped, for the development view. The
      // screen shows the stop, not this — see `stoppedByPerson`.
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
