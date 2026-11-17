/**
 * The help-me step (2026-11-17): the person does one small thing on the real
 * page — tick a box, type a code the website sent, enter their card — and
 * nothing else of the page is shown.
 *
 * The overlay is the whole window and draws the sentence, a frame, and two
 * buttons. The frame is empty: the host puts the real website, zoomed and
 * scrollable, exactly over it (`[simba] host help …`, `frontend/electron/
 * main.ts`), so the person clicks and types on the page itself. SIMBA and the
 * AI never see what is typed there; the backend only notices when the part is
 * gone, filled or solved, and goes on by itself — or the person presses
 * "I've done it". Two minutes of nothing asks "Still there?".
 */

import { useLayoutEffect, useRef } from "react";

import type { HandOver } from "@shared/schema";

import { HELP } from "../copy";
import { useStore } from "../store";
import { Button } from "./ui";

/** How far the website is zoomed in the frame, by what is asked. */
const ZOOM: Record<string, number> = { captcha: 1.5, code: 1.5, card: 1.25, other: 1 };

export function HelpMe({ bar }: { bar: HandOver }) {
  const answer = useStore((state) => state.answerHandover);
  const hole = useRef<HTMLDivElement>(null);
  const kind = bar.kind ?? "other";

  // Tell the host where the frame is, now and whenever the window changes.
  useLayoutEffect(() => {
    const tell = () => {
      const box = hole.current?.getBoundingClientRect();
      if (!box) return;
      console.log(`[simba] host help ${Math.round(box.x)} ${Math.round(box.y)} `
        + `${Math.round(box.width)} ${Math.round(box.height)} ${ZOOM[kind] ?? 1}`);
    };
    tell();
    window.addEventListener("resize", tell);
    const watch = new ResizeObserver(tell);
    if (hole.current) watch.observe(hole.current);
    return () => {
      window.removeEventListener("resize", tell);
      watch.disconnect();
    };
  }, [kind, bar.idle]);

  return (
    <div className="flex h-full w-full flex-col items-center gap-4 bg-canvas px-8 pt-6 pb-6
                    short:gap-2 short:pt-3 short:pb-3" data-testid="help-me" data-kind={kind}>
      <div className="flex w-full max-w-[1100px] flex-col gap-1" aria-live="polite">
        <h1 className="text-title font-semibold leading-[1.2] tracking-[-0.015em] text-ink
                       short:text-lead" data-testid="handover-sentence">
          {bar.idle ? HELP.stillThere : bar.sentence}
        </h1>
        <p className="text-small text-soft">
          {bar.idle ? HELP.stillThereDetail : HELP.never(bar.site)}
        </p>
      </div>
      {/* The frame: empty. The real page is laid over it by the host. */}
      <div ref={hole} data-testid="help-hole"
           className="min-h-0 w-full max-w-[1100px] flex-1 rounded-xl border-2 border-accent
                      bg-surface shadow-card" />
      <div className="flex w-full max-w-[1100px] items-center gap-4">
        {bar.idle ? (
          <>
            <Button size="md" wide={false} data-testid="handover-again"
                    onClick={() => answer("again")}>
              {HELP.again}
            </Button>
            <Button size="md" wide={false} variant="secondary" data-testid="handover-stop"
                    onClick={() => answer("cancel")}>
              {HELP.stop}
            </Button>
          </>
        ) : (
          <>
            <Button size="md" wide={false} data-testid="handover-done"
                    onClick={() => answer("done")}>
              {HELP.done}
            </Button>
            <Button size="md" wide={false} variant="secondary" data-testid="handover-stop"
                    onClick={() => answer("cancel")}>
              {HELP.stop}
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
