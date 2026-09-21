/**
 * "That didn't work, I'm carrying on."
 *
 * The loop absorbs a first failure: it tells the planner, which may choose
 * differently, and moves on. For a long time it told the *person* nothing at
 * all, so a skipped step and a completed one looked exactly the same from
 * out here. Someone watching would see step 2, then step 3, and reasonably
 * conclude that step 2 had worked.
 *
 * So this is deliberately quiet and deliberately present. Not the stuck
 * screen — the run is still going, and dressing a recovered setback up as a
 * failure would teach people to distrust a system that is working. Not the
 * accent either: nothing here is asking to be acted on. The same muted card
 * the level notice uses, saying which step and what happened, then gone.
 *
 * It outlives the step it belongs to on purpose. `step.presented` for the
 * next step arrives within milliseconds, and clearing this then would make
 * it unreadable in precisely the case it was built for.
 */

import { AnimatePresence, motion } from "framer-motion";
import { useEffect } from "react";

import { NOTICE } from "../copy";
import { ARRIVE } from "../design";
import { useStore } from "../store";
import { DismissButton, InfoIcon, NOTICE_CLASS } from "./ui";
/** Long enough to read a sentence, short enough not to become furniture. */
const NOTICE_MS = 9000;

export function StepFailureNotice() {
  const { stepFailure, dismissStepFailure } = useStore();

  useEffect(() => {
    if (!stepFailure) return;
    const timer = window.setTimeout(dismissStepFailure, NOTICE_MS);
    return () => window.clearTimeout(timer);
  }, [stepFailure, dismissStepFailure]);

  return (
    <AnimatePresence initial={false}>
      {stepFailure && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={ARRIVE}
          className={NOTICE_CLASS}
          data-transient
          role="status"
        >
          <span className="shrink-0 text-soft" aria-hidden>
            <InfoIcon />
          </span>
          <span className="flex-1">{NOTICE.skipped}</span>
          <DismissButton onClick={dismissStepFailure} />
        </motion.div>
      )}
    </AnimatePresence>
  );
}
