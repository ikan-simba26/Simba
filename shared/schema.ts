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

export type MessageType =
  // backend -> frontend
  | "task.started"
  | "state.changed"
  | "history.offered"
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
}

export interface StateChanged {
  state: State;
}

/** Something this person asked for before, and where they asked it. */
export interface PastGoal {
  goal: string;
  site: string;
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
}

export interface StepField {
  id: string;
  label: string;
  type: string;
  value: string;
}

export interface StepAction {
  id: string;
  label: string;
  kind: ActionKind;
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

export interface HelpRequested {
  reason: string;
  suggestion: string;
}

export interface TaskCompleted {
  summary: string;
  duration_ms: number;
  steps_taken: number;
  llm_calls: number;
  replayed: boolean;
  /** The answer, when the task had one. */
  findings?: Finding[];
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
  goal: string;
  input_mode: InputMode;
}

export interface StepResponse {
  step_index: number;
  action_id: string;
  input_values: Record<string, string>;
}

export interface LevelOverride {
  level: Level;
  locked: boolean;
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
