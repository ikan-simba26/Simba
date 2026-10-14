/**
 * The notices, as one line in the card's first line (2026-10-14).
 *
 * Until then the level notice floated over the card's top edge and the
 * step-failure notice sat in the column above it, so the top of a step could
 * hold a notice, the presence mark and "Read this aloud" at once, one over
 * the other. Now the top of a step shows one thing at a time: above the card,
 * only the presence mark; in the card's first line, one of these — a step
 * that did not work, then a change of level — or, with neither, where the
 * person is (the stages). "Read this aloud" keeps the right end of that line,
 * and nothing is ever drawn over it or over the mark.
 *
 * Each says its sentence, then goes by itself: the level notice after eight
 * seconds and the failure after nine, as before. Either can be dismissed.
 */

import { useEffect } from "react";

import { levelNotice as noticeFor, NOTICE } from "../copy";
import { useStore } from "../store";
import { DismissButton, InfoIcon } from "./ui";

const LEVEL_MS = 8000;
const FAILURE_MS = 9000;

/** Whether a notice is up, so the line can show it instead of the stages. */
export function useNotice(): string | null {
  const { levelNotice, stepFailure } = useStore();
  if (stepFailure) return NOTICE.skipped;
  if (levelNotice) return noticeFor(levelNotice.from, levelNotice.to, levelNotice.fitted);
  return null;
}

/** Keeps the notices' timers running wherever they are shown. */
export function NoticeTimers() {
  const { levelNotice, stepFailure, dismissLevelNotice, dismissStepFailure } = useStore();
  useEffect(() => {
    if (!levelNotice) return;
    const timer = window.setTimeout(dismissLevelNotice, LEVEL_MS);
    return () => window.clearTimeout(timer);
  }, [levelNotice, dismissLevelNotice]);
  useEffect(() => {
    if (!stepFailure) return;
    const timer = window.setTimeout(dismissStepFailure, FAILURE_MS);
    return () => window.clearTimeout(timer);
  }, [stepFailure, dismissStepFailure]);
  return null;
}

/** The one notice that is up, as a single quiet line, or nothing. */
export function NoticeLine() {
  const { stepFailure, dismissLevelNotice, dismissStepFailure } = useStore();
  const said = useNotice();
  if (!said) return null;
  return (
    <p role="status" data-testid="notice-line"
       className="flex min-w-0 items-center gap-3 rounded-full bg-tint py-1 pr-1 pl-4
                  text-small text-ink">
      <span className="shrink-0 text-soft" aria-hidden><InfoIcon /></span>
      <span className="min-w-0 flex-1 truncate">{said}</span>
      <DismissButton onClick={stepFailure ? dismissStepFailure : dismissLevelNotice} />
    </p>
  );
}
