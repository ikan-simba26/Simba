/**
 * What each detail level shows, and how densely.
 *
 * The three levels are structurally different, not one layout at three type
 * sizes: level 1 is a compact card with everything inline, level 2 is the
 * open column, level 3 is a single sentence and a single action. What
 * changes between them is which regions exist at all, how fields and actions
 * are laid out, and how much room everything is given.
 *
 * They are described as data rather than as three component trees because
 * the transition between them has to *fold* — regions collapsing to nothing
 * while the rest slides up — and that only works if one tree persists across
 * the change. Three separate trees can only crossfade, which reads as a swap.
 * See DECISIONS.md.
 */

import type { Level } from "@shared/schema";

export interface LevelSpec {
  /** "Step 2 of 6". Level 3 hides it: the count is pressure, not help. */
  progress: "full" | "subtle" | "none";
  /** The `detail` line. CONTRACT.md renders it at level 1 only. */
  detail: boolean;
  /** Level 3 keeps only fields it cannot proceed without. */
  fields: "all" | "required-only";
  /** Inline puts the label beside the input; stacked puts it above. */
  fieldLayout: "inline" | "stacked";
  /** Level 3 demotes the secondary action to plain text under the primary. */
  secondary: "button" | "text";
  /** Level 3 trims the instruction to its first sentence. */
  instruction: "full" | "first-sentence";
  /** A bordered card at level 1; bare canvas at 2 and 3. */
  shell: "card" | "bare";

  instructionSize: number;
  gap: number;
  fieldHeight: number;
  actionHeight: number;
}

export const LEVELS: Record<Level, LevelSpec> = {
  // Coping well: more context, tighter packing, everything at once.
  1: {
    progress: "full",
    detail: true,
    fields: "all",
    fieldLayout: "inline",
    secondary: "button",
    instruction: "full",
    shell: "card",
    instructionSize: 22,
    gap: 16,
    fieldHeight: 44,
    actionHeight: 48,
  },
  // The default.
  2: {
    progress: "subtle",
    detail: false,
    fields: "all",
    fieldLayout: "stacked",
    secondary: "button",
    instruction: "full",
    shell: "bare",
    instructionSize: 30,
    gap: 40,
    fieldHeight: 56,
    actionHeight: 64,
  },
  // Struggling: one sentence, one thing to press.
  3: {
    progress: "none",
    detail: false,
    fields: "required-only",
    fieldLayout: "stacked",
    secondary: "text",
    instruction: "first-sentence",
    shell: "bare",
    instructionSize: 40,
    gap: 48,
    fieldHeight: 56,
    actionHeight: 64,
  },
};

/** The first sentence, or the whole thing if it is already one. */
export function firstSentence(text: string): string {
  const match = text.match(/^.*?[.!?](?=\s|$)/);
  return match ? match[0] : text;
}

/**
 * The next level down, for content that will not fit.
 *
 * Note the direction: level 1 is the *compact* one. Its type is smallest, its
 * spacing tightest and its fields inline, so it holds the most in the least
 * room. Level 3 is the roomiest — one sentence at 40px with generous gaps —
 * and for a long instruction it is by far the tallest. Measured on a step
 * with three fields and three actions: 449px at level 1 against 851px at
 * level 3.
 *
 * So overflow moves *towards* level 1, not away from it. Simplifying and
 * fitting are different axes, and only one of them is about height.
 */
export function denser(level: Level): Level | null {
  return level === 3 ? 2 : level === 2 ? 1 : null;
}
