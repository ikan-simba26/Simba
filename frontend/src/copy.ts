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
 *      table can, and `frontend/test_copy.py` does.
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
 *     "verify", "retry", "overlay". (`STEP.count` breaks this one, knowingly —
 *     see the note on it.)
 *   - A sentence ends with a full stop, a question mark, or a colon that
 *     introduces what sits below it. A button label ends with nothing.
 *   - Straight apostrophes only, here and in the backend, so one screen never
 *     mixes `I'm` with `I’ll`.
 *
 * **The other half of the voice.** The instruction on each step, its detail
 * line and the labels on its buttons come from the backend — from a plan, or
 * from the LLM planner's sentence templates — along with the stuck screen's
 * suggestion and the trust panel's caption. Those live in
 * `backend/orchestrator/voice.py` and the plans that use it, and
 * `frontend/test_copy.py` holds them to the same rules as this file. Where the
 * two sides voice the same situation (the stuck screen's suggestion), the test
 * requires them to be the same sentence.
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
   *
   * It uses "Step", which the rules above forbid. Not fixed here because it is
   * not only a wording change — it is a question about whether a count belongs
   * on screen at all — and it is flagged for review rather than settled.
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
  /**
   * What it asks of them.
   *
   * The backend sends its own suggestion in `help.requested`, and that is what
   * is shown when it arrives. `voice.HELP_SUGGESTION` is required by
   * `test_copy.py` to be this same sentence, so the screen reads the same
   * whichever side supplied it.
   */
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

/**
 * Which sentence a level change gets. Same direction, same words, always.
 *
 * Whatever moved the level — the estimator, or a step too long to fit — the
 * person sees one of these two sentences. The reason it moved is for the
 * development view, not the screen.
 */
export function levelNotice(from: Level, to: Level): string {
  return to > from ? NOTICE.simpler : NOTICE.fuller;
}

/* ---------------------------------------------------------------- level */

export const LEVEL = {
  /** The three dots' names, for a screen reader. Generated from the level. */
  choose: (level: Level) =>
    level === 1 ? "Show more" : level === 3 ? "Show less" : "Show the usual amount",
  /** Hands the level back to the estimator once the person has locked it. */
  unlock: "let it choose",
} as const;

/* ---------------------------------------------------------------- trust */

export const TRUST = {
  /** The question the person can always ask. */
  ask: "What are you doing?",
  /** Closes the picture of the real page. */
  hide: "Hide the page",
  /** The picture's description, for a screen reader. */
  picture: "The page as it is right now",
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
  "stopped.suggestion": STOPPED.suggestion,
  "stopped.failedHeading": STOPPED.failedHeading,
  "home.greeting": HOME.greeting,
  "home.askHeading": HOME.askHeading,
  "home.againHeading": HOME.againHeading,
  "found.heading": FOUND.heading,
  "trust.ask": TRUST.ask,
};

/** Everything that goes on a button. Never punctuated, never two for one place. */
export const LABELS: Record<string, string> = {
  "home.somethingElse": HOME.somethingElse,
  "home.start": HOME.start,
  "ending.finish": ENDING.finish,
  "ending.again": ENDING.again,
  "stopped.again": STOPPED.again,
  "notice.dismiss": NOTICE.dismiss,
  "level.unlock": LEVEL.unlock,
  "level.choose1": LEVEL.choose(1),
  "level.choose2": LEVEL.choose(2),
  "level.choose3": LEVEL.choose(3),
  "trust.hide": TRUST.hide,
  "trust.close": TRUST.close,
};
