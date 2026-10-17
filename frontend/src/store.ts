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
  PersonalTile,
  TileChange,
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
import { FINAL } from "./copy";
import { type Profile, loadProfile, saveProfile, welcomeEnabled } from "./profile";
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
  /** The stage the last step was in, for a step that does not say. */
  stageNow: number | null;
  /**
   * The checklist: moves SIMBA is doing by itself (`requires_confirmation:
   * false`, 2026-10-14), in order. The last is the one being done.
   */
  checklist: { index: number; label: string }[];
  /** The checklist lines still to come, as the last line said (2026-10-15). */
  coming: string[];
  /** Pause has been pressed and SIMBA has not stopped yet. */
  pausing: boolean;
  /**
   * The task's first screen is up and has not been answered (2026-10-14).
   * No notice is shown on it, ever: a level change there is the screen
   * arriving as it is, not a change the person saw happen.
   */
  firstScreen: boolean;
  /** The person's setting: ask before every move. Kept on this computer. */
  askEachTime: boolean;
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
  /**
   * The person answered "don't" on a final screen (2026-10-16): the task
   * ends, and nothing was changed. Set on the press, like a stop, and also
   * from the backend's own `task.failed` saying so.
   */
  declined: boolean;
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
   * The level the person chose, which is what a lock holds. `level` can
   * differ from it for one step, when the overflow guard drops a level to
   * make a step fit; the next step is shown at this one again. A lock is only
   * ever the person's own choice, never a level the guard moved to.
   */
  chosenLevel: Level;
  /**
   * Set when something other than the user changed the level, so the
   * interface can say so. The interface never reshapes silently.
   *
   * `because` is what moved it, kept in the store for whoever is debugging.
   * It is never rendered: the words on screen come from `copy.levelNotice`,
   * by direction alone.
   */
  levelNotice: { from: Level; to: Level; because: string; fitted?: boolean } | null;
  /** The shown step has been answered and is waiting to be replaced. */
  answered: boolean;
  /** The development view, off unless someone asks for it by keyboard. */
  debug: boolean;
  /** The trust panel: the user has asked to see the real page. */
  trustOpen: boolean;
  /** The closing screen's picture of the real page is open (2026-10-16). */
  proofOpen: boolean;
  /**
   * "What are you doing?" was pressed and no picture came: the backend said
   * it dropped one, or none arrived in `PICTURE_WAIT_MS` (2026-10-16). The
   * panel says so, rather than the press doing nothing.
   */
  noPicture: boolean;

  toggleDebug: () => void;
  /** Send trust.requested and open the panel when the preview lands. */
  askWhat: () => void;
  closeTrust: () => void;
  openProof: () => void;
  /**
   * The closing screen's offer pressed (2026-10-16): the run, kept open for
   * it, goes on to book or pay. Its id is sent as a `step.response`.
   */
  takeOffer: () => void;
  closeProof: () => void;
  /** Stop the checklist before its next move. */
  pause: () => void;
  setAskEachTime: (on: boolean) => void;
  /**
   * What the person told SIMBA in the welcome (2026-10-18), kept on this
   * computer (`profile.ts`). Their name greets them; their level is where
   * every task starts.
   */
  profile: Profile;
  /** The welcome is on screen: a first open, or "Change my settings". */
  welcomeOpen: boolean;
  /** Part of the profile, as the welcome hears it: kept at once. */
  updateProfile: (change: Partial<Profile>) => void;
  /** The welcome done or skipped: it is not shown on its own again. */
  finishWelcome: () => void;
  /** "Change my settings": the welcome again, with what they said before. */
  openWelcome: () => void;
  /**
   * The person's own tiles, in their order (2026-10-18), as the backend last
   * offered them. Their details are never here: a tile is run by its id.
   */
  tiles: PersonalTile[];
  /** The place to rename, move and remove them is open. */
  tilesOpen: boolean;
  /** The closing screen's offer to keep this task: kept, declined, or not yet. */
  keepAnswer: "kept" | "declined" | null;
  /** Run one of their own tiles. */
  startTile: (tile: PersonalTile) => void;
  keepTile: () => void;
  declineKeep: () => void;
  /** Rename, move or remove one of their own tiles, or clear them all. */
  changeTile: (change: TileChange) => void;
  setTilesOpen: (open: boolean) => void;
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
  startTask: (goal: string, flow?: FlowName, tile?: string) => void;
  respond: (actionId: string, values: Record<string, string>) => void;
  cancel: () => void;
}

/**
 * The one action id that stops a task. Every other id a step offers is an
 * answer and the run carries on — go-ahead on an ordinary step, and since
 * 2026-09-30 one of the few buttons a question offers, or the button that
 * finishes something typed into one (`backend/orchestrator/voice.py`,
 * `CANCEL_ID` and `choices`). Until then the overlay showed its stop screen
 * for any answer but go-ahead, so pressing "Tomorrow" ended the task.
 * `test_copy.py` checks this id and the backend's agree.
 */
const STOP_ID = "cancel";

/** "Keep it" on the closing screen's offer of a tile (`voice.KEEP_ID`). */
const KEEP_ID = "keep";

/** "Don't" on a final screen, and No to a yes-or-no question (`voice.DECLINE_ID`). */
const DECLINE_ID = "decline";

/** What the backend says when "don't" was the answer: `voice.NOTHING_CHANGED`. */
const NOTHING_CHANGED = `${FINAL.notDone} ${FINAL.nothingChanged}`;

/** How long "What are you doing?" waits for a picture before saying none
 *  came: the backend's own limit (5s) and a little more. */
const PICTURE_WAIT_MS = 7000;

/** The profile as this window opened with it. */
const STARTING_PROFILE = loadProfile();

const EMPTY = {
  proofOpen: false,
  keepAnswer: null,
  task: null,
  state: null,
  step: null,
  answered: false,
  load: null,
  preview: null,
  stageNow: null,
  checklist: [],
  coming: [],
  pausing: false,
  firstScreen: false,
  help: null,
  completed: null,
  failed: null,
  stoppedByPerson: false,
  declined: false,
  error: null,
  stepFailure: null,
  reply: null,
  asking: null,
};

declare global {
  interface Window {
    /**
     * Whether a task has been started from this overlay since it loaded
     * (2026-10-17). The backend reads it beside the window state the host
     * writes (`window.__simbaWindow`, `backend/orchestrator/browser.py`):
     * the host's window matters to a run only when the person is working in
     * it. A run driven from another overlay — the demo recorder's, a script's
     * — is not paused because the host's window is minimised; on 2026-10-16
     * two recorded clips sat for minutes on exactly that.
     */
    __simbaStarted?: boolean;
  }
}

window.__simbaStarted = false;

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
      // No picture is asked for unless the person asks (2026-10-16): the
      // one asked for with every step was for the page behind it, which went
      // with "Show the real page".
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
    // Where the person said they were comfortable, else the usual (2026-10-18).
    level: STARTING_PROFILE.level ?? 2,
    history: [],
    levelLocked: false,
    chosenLevel: STARTING_PROFILE.level ?? 2,
    levelNotice: null,
    overflowHopped: false,
    debug: false,
    trustOpen: false,
    noPicture: false,
    askEachTime: STARTING_PROFILE.askEach,
    profile: STARTING_PROFILE,
    tiles: [],
    tilesOpen: false,
    welcomeOpen: welcomeEnabled() && !STARTING_PROFILE.welcomed,
    ...EMPTY,

    toggleDebug: () => set((current) => ({ debug: !current.debug })),

    askWhat: () => {
      // Open immediately; the panel waits for the picture rather than the
      // press feeling like it did nothing.
      set({ trustOpen: true, noPicture: false });
      // And if no picture comes, it says so (2026-10-16). The backend drops
      // a picture after 5s and says it did; this is for when even that
      // does not arrive.
      window.setTimeout(() => {
        const now = get();
        if (now.trustOpen && !now.preview) set({ noPicture: true });
      }, PICTURE_WAIT_MS);
      // The loudest signal channel B has: they stopped and asked.
      tracker.helpPressed();
      connection.askWhat();
    },

    closeTrust: () => set({ trustOpen: false, preview: null, noPicture: false }),

    openProof: () => set({ proofOpen: true }),
    closeProof: () => set({ proofOpen: false }),

    pause: () => {
      const last = get().checklist[get().checklist.length - 1];
      if (!last || get().pausing) return;
      set({ pausing: true });
      connection.respondToStep({ step_index: last.index, action_id: "pause", input_values: {} });
    },

    setAskEachTime: (on) => get().updateProfile({ askEach: on }),

    updateProfile: (change) => {
      const profile = { ...get().profile, ...change };
      saveProfile(profile);
      set({
        profile,
        askEachTime: profile.askEach,
        // A level chosen here is where the next task starts, not a lock.
        ...(change.level !== undefined && !get().levelLocked
          ? { level: change.level, chosenLevel: change.level } : {}),
      });
    },

    finishWelcome: () => {
      get().updateProfile({ welcomed: true });
      set({ welcomeOpen: false });
    },

    openWelcome: () => set({ welcomeOpen: true }),

    startTile: (tile) => get().startTask(tile.label, tile.flow, tile.id),

    keepTile: () => {
      const keep = get().completed?.keep;
      if (!keep) return;
      connection.respondToStep({ step_index: 0, action_id: KEEP_ID,
                                 input_values: { label: keep.label } });
      set({ keepAnswer: "kept" });
    },

    // Nothing is sent: the run goes on waiting for the other offer, if any,
    // and ends with "Back to start" as always.
    declineKeep: () => set({ keepAnswer: "declined" }),

    changeTile: (change) => {
      // The home screen's connection may have closed with the last task; a
      // new one is offered the tiles first, then answers the change.
      if (!connection.isOpen) connection.connect(get().wsUrl);
      connection.changeTile(change);
    },

    setTilesOpen: (open) => set({ tilesOpen: open }),

    chooseLevel: (level) => {
      // The user's own choice needs no notice: they are looking at it.
      set({ level, chosenLevel: level, levelLocked: true, levelNotice: null });
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
        // Never on the task's first screen.
        levelNotice: get().firstScreen ? null
          : { from, to, because: "this step was too long to fit", fitted: true },
      });
      // Said to the backend, so its level rules know what is on screen — and
      // marked as the guard's, so it is never taken for the person's choice.
      // Under a lock the lock stays where the person put it (`chosenLevel`).
      connection.overrideLevel(to, get().levelLocked, "overflow");
    },

    dismissLevelNotice: () => set({ levelNotice: null }),

    dismissStepFailure: () => set({ stepFailure: null }),

    // Clears the finished task but keeps the remembered goals, so "do
    // something else" lands on the home screen rather than an empty box.
    startOver: () => {
      // A run still waiting on the closing screen's offer (2026-10-16), or on
      // its offer to keep a tile (2026-10-18), is over: the connection closes.
      const completed = get().completed;
      if (completed?.offer || completed?.keep) connection.close();
      set({ ...EMPTY });
      // And a new one, so the home screen is offered the tiles as they now
      // stand — one just kept among them — as when SIMBA opened.
      if (!connection.isOpen) connection.connect(get().wsUrl);
    },

    takeOffer: () => {
      const offer = get().completed?.offer;
      if (!offer) return;
      connection.respondToStep({ step_index: 0, action_id: offer.id, input_values: {} });
      // Back to "working" until the booking's or the payment's first screen.
      set({ completed: null, proofOpen: false, firstScreen: false, state: "thinking" });
    },

    setWsUrl: (wsUrl) => set({ wsUrl }),

    connect: (url) => {
      set({ log: [], ...EMPTY });
      connection.connect(url ?? get().wsUrl);
    },

    startTask: (goal, flow, tile) => {
      window.__simbaStarted = true;
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
      // A lock outlives the connection it was set on, and the backend's level
      // rules are made fresh with each one. Said again before the task, so
      // the new rules hold it from the first step rather than proposing
      // levels this store would only refuse.
      // The person's own level, not whatever the guard last moved the screen
      // to: a lock carried into a new task is still only their choice.
      const { chosenLevel, levelLocked } = get();
      if (levelLocked) connection.overrideLevel(chosenLevel, true);
      // Every task starts at the person's own level (2026-10-18): the
      // backend's rules start from it and come back to it after calm steps.
      const start = get().profile.level;
      if (start && !levelLocked) set({ level: start, chosenLevel: start });
      connection.startTask(goal, flow, get().askEachTime, start, tile);
    },

    watchTelemetry: () => watch(tracker, (sample) => connection.sendTelemetry(sample)),


    respond: (actionId, values) => {
      const step = get().step;
      if (!step) return;
      // Answered: what follows is no longer the task's first screen.
      set({ firstScreen: false });
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
      if (step.final && actionId === DECLINE_ID) {
        // "Don't" on a final screen: nothing was done, and the task ends.
        set({ declined: true, step: null, answered: true });
        return;
      }
      if (actionId === STOP_ID) {
        // The backend stops on this one answer and nothing else
        // (`loop.is_answer`). Say so now; there is nothing to wait for.
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
        stageNow: null,
        firstScreen: true,
      });
      return;
    case "state.changed":
      set({ state: (message.payload as { state: State }).state });
      return;
    case "step.presented":
      // A line of the checklist (2026-10-14): something SIMBA is doing by
      // itself. Nothing to answer and no decision to measure, so the
      // telemetry clock is not started for it.
      if ((message.payload as StepPresented).requires_confirmation === false) {
        const row = message.payload as StepPresented;
        set((current) => ({
          checklist: [...current.checklist, { index: row.step_index, label: row.instruction }],
          coming: row.coming ?? [],
          step: null,
          stageNow: row.stage ?? current.stageNow,
          trustOpen: false,
        }));
        return;
      }
      // A new decision: the clock and the pointer start again (telemetry.ts).
      tracker.start((message.payload as StepPresented).step_index);
      // A new step gets its own chance to be moved for overflow — and under a
      // lock it starts at the person's own level again, whatever the guard
      // did to the last one. No notice: this is a new screen, not the old one
      // reshaping.
      set((current) => ({
        step: message.payload as StepPresented,
        stageNow: (message.payload as StepPresented).stage ?? current.stageNow,
        // A step that asks ends the checklist before it.
        checklist: [],
        coming: [],
        pausing: false,
        answered: false,
        overflowHopped: false,
        ...(current.levelLocked ? { level: current.chosenLevel } : {}),
        // The picture was of the previous step; it is stale now.
        preview: null,
        trustOpen: false,
        // A final screen keeps its own layout at every level (2026-10-16):
        // "I've made this smaller so it fits", carried over from the screen
        // before, was untrue on it, and hid where the person is.
        ...((message.payload as StepPresented).final ? { levelNotice: null } : {}),
      }));
      return;
    case "history.offered":
      set({ history: (message.payload as HistoryOffered).goals,
            tiles: (message.payload as HistoryOffered).tiles ?? [] });
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
          // Never on the task's first screen, nor before it.
          levelNotice: current.firstScreen ? null
            : { from: current.level, to: load.level, because: load.reason },
        };
      });
      return;
    }
    case "page.preview":
      set({ preview: message.payload as PagePreview, noPicture: false });
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
      set((current) => ({
        failed: message.payload as TaskFailed, step: null,
        // The backend's word that "don't" was the answer, even if the press
        // itself was not seen here (2026-10-16).
        declined: current.declined || (message.payload as TaskFailed).reason === NOTHING_CHANGED,
      }));
      return;
    case "error": {
      const error = message.payload as ErrorPayload;
      // A picture that was dropped matters only to someone waiting for it.
      const lost = error.code.startsWith("PREVIEW_");
      set((current) => ({
        error,
        noPicture: current.noPicture || (lost && current.trustOpen && !current.preview),
      }));
      return;
    }
    default:
      // Unknown types are logged and ignored, never fatal (CONTRACT.md).
      console.warn(`[simba] ignoring unknown message type: ${message.type}`);
  }
}
