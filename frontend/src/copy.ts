/**
 * Every word the interface says, in one place.
 *
 * Here rather than scattered through components for three reasons, in order
 * of how much they matter to the person reading the screen:
 *
 *   1. **The same situation must produce the same sentence, every time.**
 *      Someone who has learned that "Give me a moment." means waiting should
 *      never meet "One moment…" or "Working…" for the same state. Varying the
 *      wording asks the reader to work out whether something new is happening.
 *      A component that writes its own string cannot be checked for this; a
 *      table can, and `copy.test.ts` does.
 *   2. **Wording is a design decision, and not an engineering one.** These
 *      strings are read by people with cognitive disabilities. They should be
 *      reviewable by someone who does not read TypeScript, in one file, in
 *      one sitting.
 *   3. Announcing every change means there is a sentence for every change,
 *      and they have to agree with each other.
 *
 * The rules they are written to:
 *
 *   - Speak to the person, not about the system. "Let me sign you in" rather
 *     than "Signing in".
 *   - One idea per sentence. No sentence needs the previous one held in mind.
 *   - No word where a shorter one exists. "Bill", not "invoice".
 *   - Say what is happening now, not what happened or will happen.
 *   - Never a word the reader has to be taught: no "step", "session",
 *     "verify", "retry", "overlay".
 *
 * **What is not here.** The instructions on each step, and the labels on
 * their buttons, come from the backend's plans — they are about the task, not
 * about the interface, and a plan for a new site brings its own. So the voice
 * is set in two places, and only this one is enforceable. See RUNNING.md and
 * the note in STATUS.md.
 */

import type { Level } from "@shared/schema";

/* ------------------------------------------------------------------ home */

export const HOME = {
  /** The first thing anyone sees. A greeting, not a prompt. */
  greeting: "Hello. What can I do for you?",
  /** Above the remembered goals. Only shown when there are some. */
  againHeading: "You've asked me for these before:",
  /** Reveals the text box. Deliberately last, and quiet. */
  somethingElse: "Something else",
  /** Above the text box, once it is showing. */
  askHeading: "What would you like me to do?",
  placeholder: "Pay my electricity bill",
  start: "Start",
} as const;

/* -------------------------------------------------------------- presence */

/**
 * What the assistant says while it is working.
 *
 * One sentence per situation, and the situations are the contract's own
 * states. `waiting` has no sentence: the step on screen is the sentence, and
 * a second one beside it would be two things to read.
 */
const PRESENCE: Record<"opening" | "thinking" | "acting", string> = {
  /** Between "start" and the first step, while the site loads. */
  opening: "Let me open that for you.",
  /** Working out what to do next. */
  thinking: "Give me a moment.",
  /** Doing it. */
  acting: "I'm doing that now.",
};

export type Presence = keyof typeof PRESENCE;

/** The sentence for this situation. Always the same one. */
export function presence(situation: Presence): string {
  return PRESENCE[situation];
}

/* ------------------------------------------------------------------ step */

export const STEP = {
  /**
   * Small, and in the same place on every step.
   *
   * Kept because knowing how much is left is reassuring, and made quiet
   * because it is also pressure. Level 3 drops it entirely — see `levels.ts`.
   */
  count: (index: number, total: number) => `Step ${index} of ${total}`,
} as const;

/* -------------------------------------------------------------- findings */

export const FOUND = {
  /** Above a value found mid-task. The value itself is the large type. */
  heading: "Here's what I found:",
} as const;

/* --------------------------------------------------------------- ending */

export const ENDING = {
  /**
   * When the task found something.
   *
   * Deliberately the same sentence as `FOUND.heading` rather than a closing
   * variant of it. Showing a value mid-task and showing it at the end are the
   * same situation — here is the thing you asked for — and giving the ending
   * its own phrasing would mean the reader meets two sentences for one event
   * and has to decide whether they mean different things.
   */
  withAnswer: FOUND.heading,
  /** When it did not. Nothing was being looked for; something was done. */
  withoutAnswer: "That's done.",
  /** Ends the task. */
  finish: "Thank you",
  /** Starts another. */
  again: "Do something else",
} as const;

/* -------------------------------------------------------- when it stops */

export const STOPPED = {
  /** The assistant cannot continue and needs the person. */
  heading: "I need your help with this.",
  /** Fallback when the backend sends no suggestion of its own. */
  suggestion: "Could you take it from here? I'll carry on afterwards.",
  /** The task ended rather than paused. */
  failedHeading: "I couldn't finish this.",
  /** Offered on both, so there is always a way onwards. */
  again: "Start again",
} as const;

/* -------------------------------------------------------------- notices */

/**
 * Every change the person did not make is announced.
 *
 * Each of these is one situation with one sentence. `levelNotice` is a
 * function only because there are two directions; it is not free text.
 */
export const NOTICE = {
  /** The interface simplified itself. */
  simpler: "I'm showing less for a moment.",
  /** And put it back. */
  fuller: "I'm showing a bit more again.",
  /**
   * A step did not work and the run carried on.
   *
   * No interpolation, deliberately. The old version read "I couldn't do that
   * step — close the registration alert. I'm carrying on." and quoted the
   * instruction back, which is a second thing to read at the moment something
   * has already gone wrong, and it named a step the person may never have
   * seen. The technical reason underneath it — `Locator.click: Timeout
   * 10000ms exceeded` — was worse. Both are still in the development view.
   */
  skipped: "I couldn't do that. I'm carrying on.",
  /** Dismisses any notice. */
  dismiss: "Dismiss",
} as const;

/** Which sentence a level change gets. Same direction, same words, always. */
export function levelNotice(from: Level, to: Level): string {
  return to > from ? NOTICE.simpler : NOTICE.fuller;
}

/* ---------------------------------------------------------------- trust */

export const TRUST = {
  /** The question the person can always ask. */
  ask: "What are you doing?",
  close: "Close",
} as const;

/* ------------------------------------------------------ the whole table */

/**
 * Every situational string, keyed by situation.
 *
 * This exists so consistency is *checkable* rather than intended: the test
 * walks it and fails if one situation can produce two different strings, or
 * if two situations that should read the same have drifted apart.
 */
export const SITUATIONS: Record<string, string> = {
  "presence.opening": presence("opening"),
  "presence.thinking": presence("thinking"),
  "presence.acting": presence("acting"),
  "notice.simpler": NOTICE.simpler,
  "notice.fuller": NOTICE.fuller,
  "notice.skipped": NOTICE.skipped,
  "ending.withoutAnswer": ENDING.withoutAnswer,
  "stopped.heading": STOPPED.heading,
  "stopped.failedHeading": STOPPED.failedHeading,
  "home.greeting": HOME.greeting,
  "found.heading": FOUND.heading,
};
