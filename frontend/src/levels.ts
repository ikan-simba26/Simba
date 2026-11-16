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
import { TYPE } from "./design";

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
  /** Side by side reads as denser, but it also makes level 1 the *shortest*
   *  layout, which breaks the height ordering the levels depend on. */
  actionLayout: "row" | "stacked";

  /** Type size for a short instruction. Long ones are capped — see `typeSize`. */
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
    actionLayout: "stacked",
    instructionSize: TYPE.title,
    gap: 30,
    fieldHeight: 58,
    actionHeight: 70,
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
    actionLayout: "stacked",
    instructionSize: TYPE.heading,
    gap: 48,
    fieldHeight: 70,
    actionHeight: 80,
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
    actionLayout: "stacked",
    instructionSize: TYPE.display,
    gap: 30,
    fieldHeight: 66,
    actionHeight: 80,
  },
};

/**
 * A level's spec in a short window: the same regions, packed closer.
 *
 * Spacing shrinks to two thirds and controls lose about a fifth of their
 * height — 80px buttons become 64px, the height of the home screen's `md`
 * button. Type sizes are untouched: what gets smaller in a short window is
 * the air, not what the person reads. Every level is scaled by the same
 * factors, so their order by height is kept.
 */
export function fitted(spec: LevelSpec, short: boolean): LevelSpec {
  if (!short) return spec;
  return {
    ...spec,
    gap: Math.round(spec.gap * 0.65),
    fieldHeight: Math.round(spec.fieldHeight * 0.85),
    actionHeight: Math.round(spec.actionHeight * 0.8),
  };
}

/**
 * How big the instruction is allowed to be at this level.
 *
 * Level 3 is meant to be the largest type, but a fixed 40px on a long
 * instruction made level 3 nearly twice the height of level 2 — simplifying
 * pushed content off the screen, which is the opposite of the point. So the
 * size is capped by how much there is to read: a short sentence gets the full
 * 40px, a long one gets less. Levels 1 and 2 have fixed sizes; their content
 * is denser to begin with and they never won the height contest.
 */
export function typeSize(level: Level, instruction: string): number {
  const base = LEVELS[level].instructionSize;
  if (level !== 3) return base;
  if (instruction.length <= 70) return base;
  if (instruction.length <= 150) return TYPE.heading;
  return TYPE.title;
}

/** Station and title abbreviations whose full stop does not end a sentence. */
const ABBREVIATION = /\b(?:Jn|Jct|Cantt|St|Dr|Mr|Mrs|Ms|No|Rs|vs|etc)$/i;

/**
 * The first sentence, or the whole thing if it is already one.
 *
 * A full stop after "Jn" or "Cantt", or one followed by a lower-case word, is
 * not the end (2026-11-16): "Lahore Jn. to Karachi Cantt, tomorrow. Is that
 * right?" was cut to "Lahore Jn." at level 3, and the person was asked to say
 * yes to a journey they could not see the end of.
 */
export function firstSentence(text: string): string {
  const end = /[.!?](?=\s|$)/g;
  for (let found = end.exec(text); found; found = end.exec(text)) {
    if (found[0] === ".") {
      const after = text.slice(found.index + 1).trimStart();
      if (ABBREVIATION.test(text.slice(0, found.index)) || /^[a-z]/.test(after)) continue;
    }
    return text.slice(0, found.index + 1);
  }
  return text;
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
 *
 * From level 3 it goes straight to level 1 (2026-10-30). The guard has one hop
 * per step, and level 3 is never taller than level 2 (`test_first_screen.py`),
 * so a step that does not fit at 3 cannot fit at 2 and a hop there is the hop
 * wasted. It was: once the trained estimator started a heavy page at level 3,
 * the sign-in screen stopped at level 2, 60px to 86px past the window. The next
 * step goes back (`overflowFrom` in `store.ts`).
 */
export function denser(level: Level): Level | null {
  return level === 1 ? null : 1;
}
