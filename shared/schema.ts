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
  | "telemetry"
  // Pending agreement (2026-10-18): the person changing their own tiles.
  | "tile.change"
  // Pending agreement (2026-11-04, "Show me once"): a helper showing SIMBA a
  // task once, and a routine saved to a file or read from one.
  | "teach.watching"
  | "routine.file"
  | "teach.start"
  | "teach.answer"
  | "routine.export"
  | "routine.import"
  // Pending agreement (2026-11-13, the advisor's direction): a website added
  // to the list on the home screen.
  | "site.add";

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
/** One of the person's own tiles (2026-10-18). Its details stay in the
 *  backend, encrypted; it is run by `id` (`TaskStart.tile`). */
export interface PersonalTile {
  id: string;
  label: string;
  flow: FlowName;
}

/** A routine a helper showed SIMBA once (2026-11-04), as a tile: its name,
 *  and the host of the site it runs on. Run by `id` (`TaskStart.routine`). */
export interface TaughtTile {
  id: string;
  label: string;
  site: string;
}

/** How SIMBA does a task on a listed website (2026-11-13). */
export type How = "built-in" | "ai" | "taught";

/** Something SIMBA can do on a listed website (2026-11-13), and how:
 *  `built-in` runs a written plan (`flow`), `ai` asks the AI planner to work it
 *  out on the live page, `taught` runs a routine a helper showed (`routine`).
 *  Pressing it sends `goal` with `site`. */
export interface CatalogueTask {
  label: string;
  goal: string;
  how: How;
  flow?: FlowName;
  routine?: string;
}

/** A website SIMBA can work with, listed on the home screen's left by genre
 *  (2026-11-13). `added`: added in the app, not shipped. */
export interface CatalogueSite {
  id: string;
  name: string;
  address: string;
  genre: string;
  tasks: CatalogueTask[];
  added?: boolean;
}

export interface HistoryOffered {
  goals: PastGoal[];
  /** Additive and optional (2026-10-18): the person's own tiles, in order. */
  tiles?: PersonalTile[];
  /** Additive and optional (2026-11-04): the routines helpers have shown, as
   *  tiles. They share the home screen's row of three with `tiles`. */
  routines?: TaughtTile[];
  /** Additive and optional (2026-11-13): the websites SIMBA can work with, in
   *  the list's order, and the genres in theirs. Sent again after each
   *  `site.add`. Absent: no list, and the home screen is as it was. */
  sites?: CatalogueSite[];
  genres?: string[];
}

export type FlowName = "registration" | "billing" | "railways";
/** "not_yet" (2026-11-13, additive): a goal on a website SIMBA has no way to
 *  do yet; the overlay offers a helper's "Show me once" on it (`site`). */
export type AnswerKind = "greeting" | "unsupported" | "clarify" | "not_yet" | "not_allowed";

/**
 * A typed goal that did not start a task, and what to offer instead.
 * Added 2026-09-21, pending ratification (CONTRACT.md). Carries no words: the
 * overlay writes every sentence from `copy.ts`.
 */
export interface GoalAnswered {
  kind: AnswerKind;
  goal: string;
  flows: FlowName[];
  /** Additive and optional (2026-11-13): the website the goal was for. */
  site?: string;
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
  /**
   * Additive and optional (2026-11-04). What a helper has just shown SIMBA,
   * read back in plain words, one line each, in order, before it is kept.
   * Absent: an ordinary step.
   */
  routine?: string[];
  /** Additive and optional (2026-11-13): which AI provider worked this move
   *  out, said small under the step. Absent: a plan, a routine, replay. */
  worked_out_by?: string;
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
  /** Additive and optional (2026-11-13): the AI planner could not do a goal
   *  on this website; the overlay offers a helper's "Show me once" there. */
  teach_site?: string;
}

/** What can follow an answer, on our replicas (2026-10-16): a quiet second
 *  button on the closing screen. Pressed, the overlay sends a `step.response`
 *  whose `action_id` is `id`. */
export interface TaskOffer {
  id: string;
  label: string;
}

/** Keep this task as a tile, under `label` (2026-10-18). Answered with a
 *  `step.response` whose `action_id` is "keep" and whose `input_values.label`
 *  is the name. */
export interface KeepOffer {
  label: string;
}

export interface TaskCompleted {
  /** Additive and optional (2026-10-16). On our replicas, what can follow
   *  the answer, as a quiet second button beside "Back to start". */
  offer?: TaskOffer;
  /** Additive and optional (2026-10-18): offered once, keep this as a tile. */
  keep?: KeepOffer;
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

/** The bar's question about one typed value (2026-11-04): the same every
 *  time, or ask each time? `value` is never a password's. */
export interface TeachQuestion {
  step: number;
  label: string;
  value: string;
  /** Additive and optional (stage 2): something typed, or a day on a
   *  calendar. Absent: typed. */
  kind?: "typed" | "day";
}

/** What the bar says while a helper shows SIMBA a task (2026-11-04, pending
 *  agreement). Sent whenever any of it changes. */
export interface TeachWatching {
  lines: string[];
  question?: TeachQuestion | null;
  pointing?: boolean;
  note?: string | null;
  /** Additive and optional (2026-11-10): each thing kept so far in a few
   *  words, newest last, for the bar's list. A password is "Typed a
   *  password." and nothing more. Absent: the count and the last line. */
  kept?: string[] | null;
  /** Additive and optional (2026-11-10): the last thing could not be taken
   *  back. Nothing on the website is let through; the bar offers Start again
   *  in place of Undo and Finish. */
  start_again?: boolean;
}

/** A routine saved to a file (2026-11-04, pending agreement), in answer to
 *  `routine.export`: a suggested file name and the whole text. */
export interface RoutineFile {
  label: string;
  name: string;
  file: string;
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
  /**
   * Additive and optional (2026-10-18): the level the person chose as
   * comfortable in the welcome. The level rules start from it. Absent: 2.
   */
  start_level?: Level;
  /**
   * Additive and optional (2026-10-18): one of the person's own tiles, by id.
   * Runs with the details kept with it; asks only what can change.
   */
  tile?: string;
  /**
   * Additive and optional (2026-11-04): a routine a helper showed SIMBA, by
   * id. Runs as shown, asking only what the helper said changes.
   */
  routine?: string;
  /**
   * Additive and optional (2026-11-13): the website to work on, listed or
   * typed. With no `flow`, the goal is done there — by a built-in plan if it
   * is one and this is its site, otherwise by the AI planner.
   */
  site?: string;
}

/** A website added to the home screen's list (2026-11-13, pending agreement).
 *  Answered with `history.offered`, or `error` `SITE_NOT_ADDED` whose message
 *  is one of `name`, `address`, `listed`, `full`. */
export interface SiteAdd {
  name: string;
  address: string;
  genre: string;
}

/** Start watching a helper on this address (2026-11-04, pending agreement). */
export interface TeachStart {
  url: string;
}

/** The helper's press on the bar (2026-11-04, pending agreement). Additive
 *  (2026-11-10): "undo" takes the last thing off, and the website back when
 *  that thing moved it; "restart" opens the first page again, nothing kept. */
export interface TeachAnswer {
  action: "same" | "ask" | "finish" | "cancel" | "undo" | "restart";
  step?: number;
}

/** Save one routine to a file (2026-11-04, pending agreement). */
export interface RoutineExport {
  id: string;
}

/** A routine read from a file someone shared (2026-11-04, pending agreement).
 *  Answered with `history.offered`, or an `error` coded `ROUTINE_NOT_READ`. */
export interface RoutineImport {
  file: string;
}

/** The person changing their own tiles (2026-10-18). Answered with
 *  `history.offered`. Pending agreement: a new message type. */
export interface TileChange {
  action: "rename" | "move" | "remove" | "clear";
  id?: string;
  label?: string;
  /** For "move": where it goes, counting from 0 at the left. */
  to?: number;
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
  | Envelope<Telemetry>
  | Envelope<TeachWatching>
  | Envelope<RoutineFile>
  | Envelope<TeachStart>
  | Envelope<TeachAnswer>
  | Envelope<RoutineExport>
  | Envelope<RoutineImport>;
