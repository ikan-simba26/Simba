/**
 * The bar at the top while SIMBA watches a helper (2026-11-04, "Show me
 * once"). The rest of the window is the real website, and the helper uses it
 * directly; the host shows it below this bar for as long as watching lasts,
 * and covers it again the moment it ends (`store.hostBar`).
 *
 * One row: what SIMBA is doing and how much it has kept; the one question
 * about a typed value, or what to point at; and Finish and the way to stop.
 * Every word is the backend's lines or `copy.ts`.
 */

import type { TeachWatching } from "@shared/schema";

import { TEACH } from "../copy";
import { TEACH_BAR, useStore } from "../store";
import { Button, InfoIcon } from "./ui";

export function TeachBar({ bar }: { bar: TeachWatching }) {
  const teachAnswer = useStore((state) => state.teachAnswer);
  const question = bar.question ?? null;
  const last = bar.lines[bar.lines.length - 1];
  return (
    <div className="flex w-full items-center gap-6 border-b border-edge bg-surface px-6 shadow-card"
         style={{ height: TEACH_BAR }} data-testid="teach-bar"
         data-pointing={bar.pointing ? "true" : undefined}>
      <span className="relative flex h-4 w-4 shrink-0" aria-hidden>
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent
                         opacity-40 motion-reduce:animate-none" />
        <span className="relative inline-flex h-4 w-4 rounded-full bg-accent" />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5" aria-live="polite">
        {bar.note ? (
          <p className="flex items-center gap-2 text-body font-semibold text-ink"
             data-testid="teach-note" role="status">
            <span className="shrink-0 text-accent" aria-hidden><InfoIcon /></span>
            {bar.note}
          </p>
        ) : bar.pointing ? (
          <>
            <p className="text-body font-semibold text-ink">{TEACH.pointing}</p>
            <p className="truncate text-small text-soft">{TEACH.pointingDetail}</p>
          </>
        ) : question ? (
          <p className="text-body font-semibold text-ink" data-testid="teach-question">
            {question.kind === "day" ? TEACH.sameDay : TEACH.sameOrAsk(question.label)}
          </p>
        ) : (
          <>
            <p className="text-body font-semibold text-ink">
              {TEACH.watching} {bar.lines.length > 0 ? TEACH.count(bar.lines.length) : ""}
            </p>
            <p className="truncate text-small text-soft" data-testid="teach-last">
              {last ?? TEACH.watchingDetail}
            </p>
          </>
        )}
      </div>
      {question && !bar.pointing && (
        <div className="flex shrink-0 gap-3">
          <Button size="md" wide={false} data-testid="teach-same"
                  onClick={() => teachAnswer("same", question.step)}>
            {TEACH.same}
          </Button>
          <Button size="md" wide={false} variant="secondary" data-testid="teach-ask"
                  onClick={() => teachAnswer("ask", question.step)}>
            {TEACH.askEach}
          </Button>
        </div>
      )}
      <div className="flex shrink-0 gap-3">
        {!bar.pointing && !question && (
          <Button size="md" wide={false} data-testid="teach-finish"
                  onClick={() => teachAnswer("finish")}>
            {TEACH.finish}
          </Button>
        )}
        <Button size="md" wide={false} variant="quiet" data-testid="teach-stop"
                onClick={() => teachAnswer("cancel")}>
          {TEACH.stop}
        </Button>
      </div>
    </div>
  );
}
