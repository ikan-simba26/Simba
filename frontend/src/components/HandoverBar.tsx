/**
 * The bar at the top while the real page is the person's (2026-11-13, the
 * advisor's direction): to pay — card details, a bank's one-time code, the
 * press that pays — or to pass a check that a person is there. SIMBA never
 * does either. The rest of the window is the website, shown below this bar by
 * the host (`store.hostBar`), as for "Show me once"; nothing typed there is
 * read, logged or kept.
 *
 * One sentence from the backend (`HandOver.sentence`), the website's name,
 * and two buttons: "I've finished", when it is done, and the way to stop, which
 * changes nothing SIMBA did not already do.
 */

import type { HandOver } from "@shared/schema";

import { HANDOVER } from "../copy";
import { TEACH_BAR, useStore } from "../store";
import { Button } from "./ui";

export function HandoverBar({ bar }: { bar: HandOver }) {
  const answer = useStore((state) => state.answerHandover);
  return (
    <div className="flex w-full items-center gap-6 border-b border-edge bg-surface px-6 shadow-card"
         style={{ height: TEACH_BAR }} data-testid="handover-bar" data-reason={bar.reason}>
      <span className="relative flex h-4 w-4 shrink-0" aria-hidden>
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent
                         opacity-40 motion-reduce:animate-none" />
        <span className="relative inline-flex h-4 w-4 rounded-full bg-accent" />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-1" aria-live="polite">
        <p className="text-body font-semibold text-ink" data-testid="handover-sentence">
          {bar.sentence}
        </p>
        <p className="truncate text-small text-soft">{HANDOVER.on(bar.site)}</p>
      </div>
      <div className="flex shrink-0 items-center gap-3">
        <Button size="md" wide={false} data-testid="handover-done"
                onClick={() => answer("done")}>
          {HANDOVER.done}
        </Button>
        <Button size="md" wide={false} variant="quiet" data-testid="handover-stop"
                onClick={() => answer("cancel")}>
          {HANDOVER.stop}
        </Button>
      </div>
    </div>
  );
}
