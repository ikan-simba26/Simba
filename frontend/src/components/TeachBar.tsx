/**
 * The bar at the top while SIMBA watches a helper (2026-11-04, "Show me
 * once"). The rest of the window is the real website, and the helper uses it
 * directly; the host shows it below this bar for as long as watching lasts,
 * and covers it again the moment it ends (`store.hostBar`).
 *
 * One row: what SIMBA is doing, and under it the things kept so far in a few
 * words each, newest last (2026-11-10) — the last few and how many came
 * before them, since the bar has a fixed height and the website below must
 * stay usable; the one question about a typed value, or what to point at;
 * and Undo last thing, Finish and the way to stop. When the last thing could
 * not be taken back, the bar says so and offers Start again in their place.
 * Every word is the backend's lines or `copy.ts`.
 */

import type { TeachWatching } from "@shared/schema";

import { TEACH } from "../copy";
import { TEACH_BAR, useStore } from "../store";
import { Button, InfoIcon } from "./ui";

/** How many rows of the list the bar has room for: under one line of
 *  heading, or under a question, which can take two. */
const ROWS = 3;
const ROWS_WITH_QUESTION = 2;

/** The last few things kept, and how many came before them. */
export function lastFew(kept: string[], rows: number): { before: number; shown: string[] } {
  if (kept.length <= rows) return { before: 0, shown: kept };
  const shown = kept.slice(kept.length - (rows - 1));
  return { before: kept.length - shown.length, shown };
}

export function TeachBar({ bar }: { bar: TeachWatching }) {
  const teachAnswer = useStore((state) => state.teachAnswer);
  const question = bar.question ?? null;
  const stuck = bar.start_again === true;
  // A backend from before the list sends no `kept`: the count and the last
  // line, as before, and no Undo, which it would not understand.
  const kept = bar.kept ?? null;
  const last = bar.lines[bar.lines.length - 1];
  const { before, shown } = lastFew(kept ?? [], question ? ROWS_WITH_QUESTION : ROWS);
  return (
    <div className="flex w-full items-center gap-6 border-b border-edge bg-surface px-6 shadow-card"
         style={{ height: TEACH_BAR }} data-testid="teach-bar"
         data-pointing={bar.pointing ? "true" : undefined}
         data-start-again={stuck ? "true" : undefined}>
      <span className="relative flex h-4 w-4 shrink-0" aria-hidden>
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent
                         opacity-40 motion-reduce:animate-none" />
        <span className="relative inline-flex h-4 w-4 rounded-full bg-accent" />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5 overflow-hidden" aria-live="polite">
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
          <p className="text-body font-semibold text-ink">
            {TEACH.watching}{" "}
            {kept === null && bar.lines.length > 0 ? TEACH.count(bar.lines.length) : ""}
          </p>
        )}
        {kept === null ? (
          !bar.pointing && !question && !bar.note && (
            <p className="truncate text-small text-soft" data-testid="teach-last">
              {last ?? TEACH.watchingDetail}
            </p>
          )
        ) : shown.length > 0 && !bar.pointing ? (
          <ol className="text-small leading-snug text-soft" aria-label={TEACH.kept}
              data-testid="teach-kept">
            {before > 0 && (
              <li className="truncate" data-testid="teach-more">{TEACH.more(before)}</li>
            )}
            {shown.map((line, index) => (
              <li key={before + index} className="truncate" data-testid="teach-kept-line">
                {line}
              </li>
            ))}
          </ol>
        ) : !bar.pointing && !question && !bar.note && (
          <p className="truncate text-small text-soft" data-testid="teach-last">
            {TEACH.watchingDetail}
          </p>
        )}
      </div>
      {question && !bar.pointing && !stuck && (
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
      <div className="flex shrink-0 items-center gap-3">
        {kept !== null && kept.length > 0 && !bar.pointing && !stuck && (
          <Button size="md" wide={false} variant="quiet" data-testid="teach-undo"
                  onClick={() => teachAnswer("undo")}>
            {TEACH.undo}
          </Button>
        )}
        {stuck && (
          <Button size="md" wide={false} data-testid="teach-start-again"
                  onClick={() => teachAnswer("restart")}>
            {TEACH.startAgain}
          </Button>
        )}
        {!bar.pointing && !question && !stuck && (
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
