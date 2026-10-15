/**
 * The four states, shown rather than described.
 *
 * CONTRACT.md: exactly one of thinking | acting | waiting | stuck is active
 * at a time. Someone glancing at the screen should know which without
 * reading a word. Since 2026-09-21 that is the presence mark's job
 * (`ui.Presence`), above the column on every screen:
 *
 *   thinking  the mark breathes, slowly — something is happening, nothing is wanted
 *   acting    a thin arc circles it — it is doing the thing now
 *   waiting   the mark fills and haloes, and the buttons lead — it is your turn
 *   stuck     warm colour and a plain apology — it has stopped
 *
 * What is left here is the stuck screen's words, and the one question the
 * step asks of the state.
 */

import { motion } from "framer-motion";

import type { State } from "@shared/schema";

import { STOPPED } from "../copy";
import { ARRIVE } from "../design";

/** Shown only when stuck. Plain words, no jargon, no error code. */
export function StuckNote({ reason, suggestion, unconfirmed = false }: {
  reason?: string; suggestion?: string; unconfirmed?: boolean;
}) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={ARRIVE}
      className="flex flex-col gap-4"
    >
      <h1 className="text-display font-semibold tracking-[-0.015em] text-stuck">
        {unconfirmed ? STOPPED.unconfirmed : STOPPED.heading}
      </h1>
      {/* A change the site did not confirm: the reason is the message, read
          first and at reading size (2026-10-16). */}
      {unconfirmed && reason ? (
        <p className="text-lead text-ink" data-testid="unconfirmed">{reason}</p>
      ) : null}
      <p className="text-lead text-ink">{suggestion ?? STOPPED.suggestion}</p>
      {reason && !unconfirmed ? <p className="text-small text-soft">{reason}</p> : null}
    </motion.div>
  );
}

/** True when the backend is waiting on the person, so the actions should lead. */
export function isWaiting(state: State | null): boolean {
  return state === "waiting";
}
