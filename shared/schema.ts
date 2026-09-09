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

export interface Telemetry {
  step_index: number;
  hesitation_ms: number;
  cursor_path_ratio: number;
  backtracks: number;
  rereads: number;
  help_presses: number;
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
