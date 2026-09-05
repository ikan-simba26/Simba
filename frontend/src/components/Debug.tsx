/**
 * The development view. Hidden by default and reachable only by keyboard.
 *
 * None of this belongs in front of the person the app is for — it is here so
 * whoever is building it can see the wire without running a second window.
 *
 * Ctrl+Shift+D toggles it.
 */

import { AnimatePresence, motion } from "framer-motion";
import { useEffect } from "react";

import { useStore } from "../store";

const EASE = [0.22, 0.61, 0.36, 1] as const;

export function useDebugShortcut(): void {
  const toggleDebug = useStore((state) => state.toggleDebug);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "d") {
        event.preventDefault();
        toggleDebug();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggleDebug]);
}

export function DebugPanel() {
  const { debug, log, status, statusDetail, state, level, wsUrl } = useStore();

  return (
    <AnimatePresence>
      {debug && (
        <motion.aside
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 12 }}
          transition={{ duration: 0.3, ease: EASE }}
          className="fixed inset-x-0 bottom-0 max-h-[45vh] overflow-auto border-t
                     border-line bg-raised/95 p-4 font-mono text-[11px] text-muted"
        >
          <p className="mb-2 text-ink">
            {status}
            {statusDetail ? ` — ${statusDetail}` : ""} · state {state ?? "—"} · level{" "}
            {level} · {wsUrl} · {log.length} messages · Ctrl+Shift+D to hide
          </p>
          <ol className="flex flex-col gap-[2px]">
            {log.map((entry, index) => (
              <li key={`${entry.seq}-${index}`}>
                <span className="text-muted/60">#{entry.seq}</span>{" "}
                <span className="text-ink/80">{entry.type}</span>
                {entry.note ? ` — ${entry.note}` : ""} {summarise(entry.payload)}
              </li>
            ))}
          </ol>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}

/** A base64 screenshot would drown the log; say how big it was instead. */
function summarise(payload: unknown): string {
  const text = JSON.stringify(payload, (key, value) =>
    key === "screenshot" && typeof value === "string"
      ? `<${value.length} bytes of png>`
      : value,
  );
  return text && text.length > 220 ? `${text.slice(0, 220)}…` : (text ?? "");
}
