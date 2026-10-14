/**
 * Channel B: what the person does with a step, as five numbers.
 *
 * The estimator is meant to fuse what a *page* is like with how the person in
 * front of it is coping. The page half is measured in the backend
 * (`backend/estimator/page_features.py`); this is the other half, and until
 * now nothing sent it — `telemetry` has been in CONTRACT.md since 2026-09-04
 * with no sender.
 *
 * Five signals, each chosen because it can be measured from a pointer and a
 * clock without recording anything about the person:
 *
 * | Field | What it counts | Why it might mean something |
 * |---|---|---|
 * | `hesitation_ms` | from the step appearing to the answer | deciding takes longer when the decision is unclear |
 * | `cursor_path_ratio` | path length ÷ straight-line distance | 1.0 is a direct move; wandering is higher |
 * | `backtracks` | reversals of pointer direction | going back on yourself: a changed mind, or a lost target |
 * | `rereads` | returns to the text after leaving it | reading the instruction again |
 * | `help_presses` | presses of "What are you doing?" | asking, which is the loudest signal there is |
 *
 * **No keystrokes, no field values, no coordinates leave here.** The cursor is
 * reduced to two scalars before anything is sent, and nothing about what was
 * typed is looked at.
 *
 * None of this is interpreted here or in the backend. It is written down
 * beside the page it belongs to (`backend/estimator/pairing.py`) so that a
 * training set exists when there is something to train. Every threshold below
 * is a starting guess, and they are all in one place so the first person with
 * data can move them.
 */

import type { Telemetry } from "@shared/schema";

/** Pointer moves under this are noise — a hand resting, a trackpad twitch. */
const MIN_SEGMENT_PX = 8;

/**
 * How sharply the pointer has to turn before it counts as going back.
 *
 * Measured as the cosine of the angle between two consecutive segments: below
 * this, the direction has reversed by more than about 120°. A gentle curve
 * around a button is not a backtrack; turning round is.
 */
const BACKTRACK_COSINE = -0.5;

/** How often a sample goes out while a step sits there unanswered. */
export const SAMPLE_EVERY_MS = 3000;

/** The region whose text the person reads: the instruction and what follows. */
const TEXT_REGION = "[data-testid=step-shell]";

type Point = { x: number; y: number };

function distance(a: Point, b: Point): number {
  return Math.hypot(b.x - a.x, b.y - a.y);
}

export class StepTracker {
  private stepIndex: number | null = null;
  private startedAt = 0;
  private first: Point | null = null;
  private last: Point | null = null;
  private previous: Point | null = null;
  private lastDirection: Point | null = null;
  private pathLength = 0;
  private backtracks = 0;
  private rereads = 0;
  private helpPresses = 0;
  private readAloudPresses = 0;
  private insideText = false;

  /** A step is on screen. Everything starts again: it is a new decision. */
  start(stepIndex: number): void {
    this.stepIndex = stepIndex;
    this.startedAt = performance.now();
    this.first = this.last = this.previous = this.lastDirection = null;
    this.pathLength = 0;
    this.backtracks = 0;
    this.rereads = 0;
    this.helpPresses = 0;
    this.readAloudPresses = 0;
    this.insideText = false;
  }

  /** No step on screen: samples stop until the next one. */
  stop(): void {
    this.stepIndex = null;
  }

  get active(): boolean {
    return this.stepIndex !== null;
  }

  helpPressed(): void {
    if (this.stepIndex !== null) this.helpPresses += 1;
  }

  /**
   * "Read this aloud" was pressed (2026-10-14). Its own signal, not a help
   * press: a person who wants a step read may be finding it hard, or may
   * simply prefer to listen, and the estimator should be able to tell the
   * two apart rather than have them merged here. Nahail to confirm.
   */
  readAloud(): void {
    if (this.stepIndex !== null) this.readAloudPresses += 1;
  }

  moved(point: Point, overText: boolean): void {
    if (this.stepIndex === null) return;
    if (this.first === null) this.first = point;

    if (this.previous !== null) {
      const step = distance(this.previous, point);
      if (step >= MIN_SEGMENT_PX) {
        this.pathLength += step;
        const direction = { x: point.x - this.previous.x, y: point.y - this.previous.y };
        if (this.lastDirection !== null) {
          const dot =
            direction.x * this.lastDirection.x + direction.y * this.lastDirection.y;
          const sizes =
            Math.hypot(direction.x, direction.y) *
            Math.hypot(this.lastDirection.x, this.lastDirection.y);
          if (sizes > 0 && dot / sizes < BACKTRACK_COSINE) this.backtracks += 1;
        }
        this.lastDirection = direction;
        this.previous = point;
      }
    } else {
      this.previous = point;
    }

    this.last = point;

    // Leaving the text and coming back to it is a re-read. Counted on the way
    // in, so arriving at the step and reading it once is not one.
    if (overText && !this.insideText && this.pathLength > 0) this.rereads += 1;
    this.insideText = overText;
  }

  /**
   * The numbers as they stand.
   *
   * `cursor_path_ratio` is 1.0 when the pointer never moved: a person who
   * pressed without moving took the most direct route there is, and 0 would
   * read as "wandered less than possible", which is not a thing.
   */
  sample(): Telemetry | null {
    if (this.stepIndex === null) return null;
    const straight =
      this.first !== null && this.last !== null ? distance(this.first, this.last) : 0;
    const ratio = straight > 0 ? this.pathLength / straight : 1;
    return {
      step_index: this.stepIndex,
      hesitation_ms: Math.round(performance.now() - this.startedAt),
      cursor_path_ratio: Math.round(ratio * 100) / 100,
      backtracks: this.backtracks,
      rereads: this.rereads,
      help_presses: this.helpPresses,
      read_aloud: this.readAloudPresses,
    };
  }
}

/**
 * The one tracker. A step is on screen or it is not, and both the store's
 * actions and the message handler that receives `step.presented` need to say
 * so — so it is a module singleton rather than a thing passed around.
 */
export const tracker = new StepTracker();

/**
 * Watch the window, and send a sample on a timer while a step waits.
 *
 * Returns the function that stops it again. The pointer listener is passive
 * and does no layout work per move: `closest` on the event target is a tree
 * walk over a handful of nodes, and the numbers are scalars.
 */
export function watch(
  tracker: StepTracker,
  send: (sample: Telemetry) => void,
  every: number = SAMPLE_EVERY_MS,
): () => void {
  const onMove = (event: PointerEvent | MouseEvent) => {
    const target = event.target as Element | null;
    const overText = Boolean(target?.closest?.(TEXT_REGION));
    tracker.moved({ x: event.clientX, y: event.clientY }, overText);
  };
  window.addEventListener("pointermove", onMove, { passive: true });

  const timer = window.setInterval(() => {
    const sample = tracker.sample();
    // Only while a step is actually waiting: an answered step is reported by
    // `respond`, and there is nothing to say about a screen with no decision
    // on it.
    if (sample !== null) send(sample);
  }, every);

  return () => {
    window.removeEventListener("pointermove", onMove);
    window.clearInterval(timer);
  };
}
