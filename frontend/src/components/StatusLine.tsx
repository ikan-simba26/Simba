/**
 * Always on screen (2026-11-13, the advisor's direction, L): whether SIMBA is
 * connected, and what it is doing right now, in two or three plain words —
 * "Connected · Your turn". Small, in the bottom left corner, under everything
 * else; the screen itself still says what is happening in a whole sentence.
 *
 * Connected means the window can reach SIMBA's backend. The backend closes the
 * connection when a task ends, by design, so a closed one after a task is not
 * a fault; the home screen opens a new one by itself (`store.keepConnected`).
 * Only a connection that cannot be made says so.
 */

import { CONNECTION, STATUS } from "../copy";
import { useStore } from "../store";

export type Activity = keyof typeof STATUS;

export function StatusLine({ activity, inline = false }: { activity: Activity; inline?: boolean }) {
  const status = useStore((state) => state.status);
  const between = useStore((state) => Boolean(state.completed || state.failed
    || state.stoppedByPerson || state.declined || state.help));
  const words = status === "open" ? CONNECTION.connected
    : status === "error" ? CONNECTION.unreachable
    : status === "connecting" || status === "idle" ? CONNECTION.connecting
    // Closed by the backend after a task, as it always is: ready for the next.
    : between ? CONNECTION.connected : CONNECTION.connecting;
  const fault = status === "error";
  return (
    <p className={inline
         // The first screen's top bar (2026-11-17): a pill in the middle of it.
         ? "flex items-center gap-2 rounded-full bg-tint px-4 py-1 text-small font-medium text-accent"
         : `pointer-events-none fixed bottom-1.5 left-6 z-[2] flex items-center gap-2
            text-small text-soft`}
       role="status" aria-live="polite" data-testid="status-line"
       data-connection={status}>
      <span className={`inline-block h-2 w-2 rounded-full ${fault ? "bg-stuck"
        : status === "open" || between ? "bg-accent" : "bg-soft/60"}`} aria-hidden />
      <span>{words}</span>
      {!fault && <span aria-hidden>·</span>}
      {!fault && <span data-testid="status-activity">{STATUS[activity]}</span>}
    </p>
  );
}
