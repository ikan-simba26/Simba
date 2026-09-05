/**
 * The four states, shown rather than described.
 *
 * CONTRACT.md: exactly one of thinking | acting | waiting | stuck is active
 * at a time. Someone glancing at the screen should know which without
 * reading a word:
 *
 *   thinking  a slow soft pulse — something is happening, nothing is wanted
 *   acting    a thin line crossing the top — it is doing the thing now
 *   waiting   the buttons brighten and the rest recedes — it is your turn
 *   stuck     warm colour and a plain apology — it needs you
 */

import { AnimatePresence, motion } from "framer-motion";

import type { State } from "@shared/schema";

const EASE = [0.22, 0.61, 0.36, 1] as const;

/** A 2px line crossing the top of the column while an action is running. */
export function ActingLine({ active }: { active: boolean }) {
  return (
    <div className="h-[2px] w-full overflow-hidden" aria-hidden>
      <AnimatePresence>
        {active && (
          <motion.div
            className="h-full w-1/3 rounded-full bg-accent"
            initial={{ opacity: 0, x: "-100%" }}
            animate={{
              opacity: 1,
              x: ["-100%", "300%"],
              transition: {
                opacity: { duration: 0.3, ease: EASE },
                x: { duration: 1.4, ease: "easeInOut", repeat: Infinity },
              },
            }}
            exit={{ opacity: 0, transition: { duration: 0.3, ease: EASE } }}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

/**
 * The slow breath under `thinking`. Wraps the column rather than sitting
 * beside it, so the whole thing settles rather than something blinking at
 * you from a corner.
 */
export function ThinkingPulse({
  active,
  children,
}: {
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <motion.div
      animate={active ? { opacity: [1, 0.62, 1] } : { opacity: 1 }}
      transition={
        active
          ? { duration: 2.6, ease: "easeInOut", repeat: Infinity }
          : { duration: 0.3, ease: EASE }
      }
    >
      {children}
    </motion.div>
  );
}

/** Shown only when stuck. Plain words, no jargon, no error code. */
export function StuckNote({ reason, suggestion }: { reason?: string; suggestion?: string }) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.3, ease: EASE }}
      className="flex flex-col gap-4"
    >
      <h1 className="text-[30px] leading-[1.35] font-medium text-stuck">
        Sorry — I&rsquo;m stuck.
      </h1>
      <p className="text-[19px] leading-relaxed text-ink/85">
        {suggestion ?? "Could you take it from here? I'll carry on afterwards."}
      </p>
      {reason ? <p className="text-[15px] leading-relaxed text-muted">{reason}</p> : null}
    </motion.div>
  );
}

/** True when the backend is waiting on the person, so the actions should lead. */
export function isWaiting(state: State | null): boolean {
  return state === "waiting";
}
