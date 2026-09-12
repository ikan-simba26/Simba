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

import { useStore } from "../store";

const EASE = [0.22, 0.61, 0.36, 1] as const;
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
          transition={{ duration: 0.35, ease: EASE }}
          className="mb-6 flex items-start justify-between gap-4 rounded-lg
                     border border-line bg-raised px-4 py-3"
          data-transient
          role="status"
        >
          <div className="flex flex-col gap-1">
            <span className="text-[14px] text-ink/85">
              I couldn&rsquo;t do that step &mdash; {lowerFirst(stepFailure.instruction)}{" "}
              I&rsquo;m carrying on.
            </span>
            {/* The mechanical reason, smaller. Someone who wants it can read
                it; someone who does not is not made to. */}
            <span className="text-[13px] leading-relaxed text-muted">
              {stepFailure.reason}
            </span>
          </div>
          <button
            type="button"
            onClick={dismissStepFailure}
            aria-label="Dismiss"
            className="shrink-0 px-2 text-muted transition-colors duration-300 hover:text-ink"
          >
            &times;
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/** So the instruction reads as part of the sentence around it. */
function lowerFirst(text: string): string {
  if (!text) return text;
  // Only when the first word is ordinary prose. "LAHORE CANTT" stays as it is.
  const [first] = text.split(" ");
  if (first !== first.toLowerCase() && first === first.toUpperCase()) return text;
  return text[0].toLowerCase() + text.slice(1);
}
