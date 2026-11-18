/**
 * Which of the presence mark's six shapes the current screen means
 * (`ui.Presence`), by name. The lion's halo in the task frame says the same
 * thing in the same words (2026-11-17), so both read it from here.
 */

import type { PresenceMode } from "./components/ui";
import { isWaiting } from "./components/StateSignal";
import { useStore } from "./store";

export function usePresenceMode(): PresenceMode {
  const { state, step, help, completed, failed, stoppedByPerson, task, asking,
          declined } = useStore();
  // The person's own decision, carried out: calm, not stuck.
  if (stoppedByPerson || declined) return "ready";
  if (help || failed || state === "stuck") return "stuck";
  if (completed) return "done";
  if (state === "acting") return "acting";
  if (step && isWaiting(state)) return "waiting";
  if (task || asking) return "thinking";
  return "ready";
}
