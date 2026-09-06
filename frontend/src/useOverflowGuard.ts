/**
 * If a step will not fit, show less of it rather than a scrollbar.
 *
 * A scrollbar on a one-step-at-a-time overlay is a small failure: it hides
 * part of the decision below the fold and asks someone who is already
 * struggling to go looking for it. Dropping a level removes the least
 * important region instead, which is the same trade the levels exist to make.
 *
 * Only ever moves one way, so it cannot oscillate: a step can go from level
 * 3 to 2 to 1 and then stops.
 */

import { useEffect, type RefObject } from "react";

import type { Level } from "@shared/schema";

import { denser } from "./levels";
import { useStore } from "./store";

/** Long enough for a 350ms fold to finish before anything is measured. */
const SETTLE_MS = 480;

export function useOverflowGuard(
  ref: RefObject<HTMLElement | null>,
  { level, active }: { level: Level; active: boolean },
): void {
  const simplifyForOverflow = useStore((state) => state.simplifyForOverflow);

  useEffect(() => {
    if (!active) return;

    const check = () => {
      const element = ref.current;
      if (!element) return;

      const next = denser(level);
      if (next === null) return; // Level 1 is the floor; a scrollbar it is.

      // Ask the page, rather than guessing how much room the chrome takes.
      // The step is not the only thing on screen: there is the padding, the
      // notice and the level control too, and an earlier version measured
      // only the step and concluded a scrolling page fitted.
      const overflowing =
        document.documentElement.scrollHeight > window.innerHeight + 2;
      if (overflowing && element.isConnected) {
        simplifyForOverflow(next);
      }
    };

    // Measure once the fold has settled, otherwise the height read is
    // whatever the animation happened to be passing through.
    const timer = window.setTimeout(check, SETTLE_MS);
    window.addEventListener("resize", check);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("resize", check);
    };
  }, [ref, level, active, simplifyForOverflow]);
}
