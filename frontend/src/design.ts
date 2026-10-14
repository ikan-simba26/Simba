/**
 * The design tokens JavaScript needs: motion, and the sizes Framer animates.
 *
 * Colours, radii, shadows and the type scale's CSS side live in `index.css`.
 * These are the same scale, as numbers, for the places a size is animated
 * rather than set by a class — the step's instruction folding between levels,
 * a finding growing. One scale, two readers; the numbers here must match the
 * `--text-*` values there.
 */

/** The type scale in pixels. Mirrors `--text-*` in `index.css`. */
export const TYPE = {
  caption: 18,
  small: 20,
  body: 23,
  lead: 26,
  title: 30,
  heading: 38,
  display: 48,
  hero: 72,
} as const;

/** How wide the column is. Most of the 1280px window, with room either side. */
export const COLUMN = 880;

/**
 * Below this window height the layout is compact: tighter spacing, smaller
 * cards and buttons, the greeting a step down. The type the person reads does
 * not shrink — body stays 23px, card text 26px.
 *
 * The window is sized to the screen (`electron/main.ts`) and the overlay lays
 * out at the window's real size, so a 1080p laptop at 125% gets about 734px
 * and at 150% about 608px, against 800 at 100%. The home screen needs about
 * 770px at full spacing, so both of those are compact.
 *
 * `index.css` repeats this number in its `short` variant, because a Tailwind
 * variant cannot read JavaScript. Change both.
 */
export const SHORT_HEIGHT = 760;

/** The spacing steps in pixels. Tailwind's 4px scale, at these values only. */
export const SPACE = {
  1: 4,
  2: 8,
  3: 12,
  4: 16,
  6: 24,
  8: 32,
  10: 40,
  12: 48,
  16: 64,
  24: 96,
} as const;

/**
 * One easing curve for everything that moves, and never a spring.
 *
 * A standard ease-in-out: it accelerates and decelerates evenly, with no
 * overshoot anywhere, so nothing bounces, wobbles or snaps. Slow on purpose.
 * Something that moves quickly asks to be looked at, and the only thing this
 * audience should have to look at is the step.
 */
export const EASE = [0.4, 0, 0.2, 1] as const;

export const MOTION = {
  /** Hover and press feedback. Quick enough to feel connected to the hand. */
  quick: 0.2,
  /** A screen arriving, a notice appearing. */
  base: 0.45,
  /** The trust panel sliding in; anything that covers the whole screen. */
  slow: 0.6,
  /**
   * The level fold. Kept at its measured values — it was tuned so the column
   * height falls monotonically between levels (`StepShell`, `FOLD`).
   */
  fold: 0.35,
  unfold: 0.28,
  unfoldDelay: 0.12,
  /** One full breath of the presence mark while thinking. */
  breath: 3.2,
  /** One slow orbit of the presence mark while acting. */
  orbit: 2.8,
  /** The real page appearing for a peek, and going again. */
  veil: 0.9,
} as const;

/** A screen arriving or leaving: a fade and a short, slow rise. */
export const ARRIVE = { duration: MOTION.base, ease: EASE };
