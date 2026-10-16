/**
 * SIMBA message contract, mirrored from CONTRACT.md.
 *
 * Keep field names identical to shared/schema.py and to CONTRACT.md.
 * Additive optional fields are fine; renames and removals require all three
 * owners and a version bump (see CLAUDE.md).
 */

// --- Shared vocab ------------------------------------------------------------

export type State = "thinking" | "acting" | "waiting" | "stuck";
export type Level = 1 | 2 | 3;
export type ActionKind = "primary" | "secondary" | "destructive";
export type InputMode = "text" | "voice";
/** What a step is about, for the icon beside it (2026-10-07). */
export type StepKind = "date" | "place" | "choose" | "type" | "read" | "confirm";

export type MessageType =
  // backend -> frontend
  | "task.started"
  | "state.changed"
  | "history.offered"
  | "goal.answered"
  | "step.presented"
  | "step.failed"
  | "load.updated"
  | "page.preview"
  | "help.requested"
  | "task.completed"
  | "task.failed"
  | "error"
  // frontend -> backend
  | "task.start"
  | "step.response"
  | "level.override"
  | "trust.requested"
  | "task.cancel"
  | "telemetry";

// --- Backend to frontend -----------------------------------------------------

export interface TaskStarted {
  goal: string;
  estimated_steps: number;
  /**
   * Additive and optional (2026-10-14). The task's stages by name, shown in
   * place of a count. Fixed for the task. Absent or empty: no stages shown.
   */
  stages?: string[];
}

export interface StateChanged {
  state: State;
}

/** Something this person asked for before, and where they asked it. */
export interface PastGoal {
  goal: string;
  site: string;
  /**
   * Additive and optional (2026-10-16). The goal in a few words, for the home
   * screen's one line: "Bill ending 7890". Absent: the goal's own words.
   */
  label?: string;
}

/**
 * What the home screen offers instead of an empty box.
 *
 * Sent once, when the socket opens, before any task. A frontend that ignores
 * it sees exactly what it saw before.
 */
export interface HistoryOffered {
  goals: PastGoal[];
}

export type FlowName = "registration" | "billing" | "railways";
export type AnswerKind = "greeting" | "unsupported" | "clarify";

/**
 * A typed goal that did not start a task, and what to offer instead.
 * Added 2026-09-21, pending ratification (CONTRACT.md). Carries no words: the
 * overlay writes every sentence from `copy.ts`.
 */
export interface GoalAnswered {
  kind: AnswerKind;
  goal: string;
  flows: FlowName[];
}

/**
 * A value the task was looking for, and the name to show it under.
 *
 * `label` is for a person to read, not the page's own column heading: the
 * billing replica calls the amount `P/WITHIN`, and nobody outside a billing
 * department knows what that means. The plan supplies the readable name.
 */
export interface Finding {
  label: string;
  /** One line: the values joined, counting the rest past four. */
  value: string;
  /** Every value, in page order. Optional and additive; absent means [value]. */
  values?: string[];
  /**
   * On the first finding of a message only: every result as a whole row, one
   * cell per finding in that message, in their order, repeats kept, "" for
   * none. Optional and additive; absent when the values are not from a table.
   */
  rows?: string[][];
}

export interface StepField {
  id: string;
  label: string;
  type: string;
  value: string;
  /**
   * Additive and optional (2026-10-06). The answers a field accepts, when they
   * are a known list — the site's own stations. The overlay shows the ones
   * that match what has been typed so far. Absent or empty means any text.
   */
  options?: string[];
}

export interface StepAction {
  id: string;
  label: string;
  kind: ActionKind;
}

/** One thing a final screen shows, by name, as the page states it (2026-10-16). */
export interface Detail {
  label: string;
  value: string;
}

export interface StepPresented {
  step_index: number;
  step_total: number;
  instruction: string;
  detail: string;
  fields: StepField[];
  actions: StepAction[];
  requires_confirmation: boolean;
  /** What has been found so far, if the task was looking for anything. */
  findings?: Finding[];
  /**
   * Additive and optional (2026-10-07). What kind of thing the step is about,
   * so one plain icon can go beside it. Absent means no icon.
   */
  step_kind?: StepKind;
  /** Additive and optional (2026-10-14). Which of the task's stages this step
   *  is in, by position. Absent: the stage before it. */
  stage?: number;
  /**
   * Additive and optional (2026-10-14). What was wrong with the last answer,
   * beside the question asked again. Cleared once a valid answer is chosen.
   */
  note?: string;
  /**
   * Additive and optional (2026-10-15). On a checklist line: the lines SIMBA
   * expects to do by itself after this one, in order. Absent or empty:
   * nothing more it knows of.
   */
  coming?: string[];
  /**
   * Additive and optional (2026-10-16). The final screen before a move that
   * books, pays, registers or changes a record: the key details of what will
   * happen, read from the page. Exactly two actions, do it (`"confirm"`) and
   * don't (`"decline"`), neither the default. Absent: an ordinary step.
   */
  final?: Detail[];
}

/**
 * A step did not work, and the run is carrying on past it.
 *
 * Emitted where the loop previously said nothing at all. Not the same thing
 * as `error`, which is the harness failing — this is the task failing at
 * something and continuing, which the user should see quietly rather than be
 * alarmed by.
 */
export interface StepFailed {
  step_index: number;
  /** What was attempted, in the words the user was shown. */
  instruction: string;
  /** Why it did not work. */
  reason: string;
  strategies_tried: number;
}

export interface LoadUpdated {
  score: number;
  level: Level;
  reason: string;
}

export interface Highlight {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface PagePreview {
  screenshot: string;
  highlight: Highlight;
  caption: string;
}

/**
 * A still of the real page at the end of a task, with what was read ringed
 * (2026-10-16).
 */
export interface Proof {
  screenshot: string;
  rings: Highlight[];
  caption: string;
}

export interface HelpRequested {
  reason: string;
  suggestion: string;
  /**
   * Additive and optional (2026-10-16). A change was tried and the site did
   * not confirm it: not "stuck", and the reason is what must be read.
   */
  unconfirmed?: boolean;
}

export interface TaskCompleted {
  /**
   * Additive and optional (2026-10-16). The closing screen's last line: what
   * was done, and what was not.
   */
  scope?: string;
  /**
   * Additive and optional (2026-10-16). For a task that changed something,
   * the site's own confirmation, quoted. Only when it is on the page.
   */
  confirmation?: string;
  /**
   * Additive and optional (2026-10-16). What the site says against that
   * confirmation, its own sentence quoted whole. Only when the page says it.
   */
  caveat?: string;
  /**
   * Additive and optional (2026-10-16). The real page when the task closed,
   * with every row or value shown ringed.
   */
  proof?: Proof;
  /** Additive and optional (2026-10-16). Why there is no `proof`. */
  proof_note?: string;
  /** Additive and optional (2026-10-14). What the results are for, above them:
   *  "Lahore Cantt to Karachi Cantt, Thursday 15 October". */
  heading?: string;
  summary: string;
  duration_ms: number;
  steps_taken: number;
  llm_calls: number;
  replayed: boolean;
  /** The answer, when the task had one. */
  findings?: Finding[];
  /**
   * One plain sentence above the result, saying what it means — "There are 3
   * trains. The fastest takes 6 hours 3 minutes." Built by the backend only
   * from values the page returned. Optional and additive (2026-10-03).
   */
  explanation?: string | null;
}

export interface TaskFailed {
  reason: string;
  recoverable: boolean;
}

export interface ErrorPayload {
  code: string;
  message: string;
}

// --- Frontend to backend -----------------------------------------------------

export interface TaskStart {
  /**
   * Additive and optional (2026-10-14). Ask before every move rather than
   * running the safe ones as a checklist. Absent: the checklist.
   */
  confirm_each?: boolean;
  goal: string;
  input_mode: InputMode;
  /** Additive, optional (2026-09-21): the flow the person picked. */
  flow?: FlowName;
}

export interface StepResponse {
  step_index: number;
  action_id: string;
  input_values: Record<string, string>;
}

export interface LevelOverride {
  level: Level;
  locked: boolean;
  /**
   * Additive and optional (2026-09-25). Who moved the level: the person, or
   * the overlay's guard because a step did not fit. A guard move never becomes
   * the lock. Omitted means the person.
   */
  by?: "person" | "overflow";
}

// eslint-disable-next-line @typescript-eslint/no-empty-interface
export interface TrustRequested {}

// eslint-disable-next-line @typescript-eslint/no-empty-interface
export interface TaskCancel {}

/**
 * Channel B: how the person is getting on with the step on screen.
 *
 * Sent on every step response and on a timer while one waits. `answered` is
 * additive and optional; absent means a timer sample.
 */
export interface Telemetry {
  step_index: number;
  hesitation_ms: number;
  cursor_path_ratio: number;
  backtracks: number;
  rereads: number;
  help_presses: number;
  /** Additive and optional (2026-10-14). Presses of "Read this aloud" on this
   *  step: its own signal, not `help_presses`. */
  read_aloud?: number;
  /** True on the sample that goes with the answer. Absent means a timer tick. */
  answered?: boolean;
}

// --- Envelope ----------------------------------------------------------------

export interface Envelope<T> {
  v: 1;
  type: MessageType;
  task_id: string;
  seq: number;
  ts: number;
  payload: T;
}

export type AnyEnvelope =
  | Envelope<TaskStarted>
  | Envelope<StateChanged>
  | Envelope<HistoryOffered>
  | Envelope<GoalAnswered>
  | Envelope<StepPresented>
  | Envelope<StepFailed>
  | Envelope<LoadUpdated>
  | Envelope<PagePreview>
  | Envelope<HelpRequested>
  | Envelope<TaskCompleted>
  | Envelope<TaskFailed>
  | Envelope<ErrorPayload>
  | Envelope<TaskStart>
  | Envelope<StepResponse>
  | Envelope<LevelOverride>
  | Envelope<TrustRequested>
  | Envelope<TaskCancel>
  | Envelope<Telemetry>;
