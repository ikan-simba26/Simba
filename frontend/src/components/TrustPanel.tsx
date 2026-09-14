/**
 * "What are you doing?" — and the answer.
 *
 * The whole premise of SIMBA is that the real page stays out of sight, which
 * is a lot to ask someone to take on trust. This is the way back: press the
 * control and the overlay slides up off the screen, revealing a picture of
 * the actual page underneath, dimmed, with the thing about to be touched
 * ringed and named. Press again and it slides back down.
 *
 * The picture comes from `page.preview`, which the backend captures from the
 * covered site view. It is a screenshot rather than the live view on purpose:
 * the contract sends an image (CONTRACT.md), and showing the live page would
 * hand the user the cluttered interface this exists to spare them.
 */

import { AnimatePresence, motion } from "framer-motion";

import type { PagePreview } from "@shared/schema";

import { TRUST } from "../copy";
import { useStore } from "../store";

const EASE = [0.32, 0.72, 0, 1] as const;
const SLIDE = { duration: 0.42, ease: EASE };

/** The frozen viewport the backend captures at (CLAUDE.md). */
const CAPTURE = { width: 1280, height: 800 };

export function TrustControl() {
  const { task, completed, failed, trustOpen, askWhat } = useStore();

  // Only while there is something to be doing. The way *out* of the panel
  // lives inside the panel: this control sits under it and cannot be
  // clicked once it is open, which left no way to dismiss it at all.
  if (!task || completed || failed || trustOpen) return null;

  return (
    <button
      type="button"
      onClick={askWhat}
      className="mt-6 w-full text-center text-[14px] text-muted underline
                 underline-offset-4 transition-colors duration-300 hover:text-ink"
    >
      {TRUST.ask}
    </button>
  );
}

export function TrustPanel() {
  const { trustOpen, preview, closeTrust } = useStore();
  const showing = trustOpen && preview;

  return (
    <AnimatePresence>
      {showing && (
        <motion.div
          key="trust"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={SLIDE}
          className="fixed inset-0 z-10 flex flex-col items-center justify-center
                     bg-canvas px-6 py-10"
          data-testid="trust-panel"
        >
          <Shot preview={preview} />

          <button
            type="button"
            onClick={closeTrust}
            className="mt-8 text-[15px] text-muted underline underline-offset-4
                       transition-colors duration-300 hover:text-ink"
          >
            Hide the page
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function Shot({ preview }: { preview: PagePreview }) {
  const { highlight, caption, screenshot } = preview;
  const hasBox = highlight.w > 0 && highlight.h > 0;

  // Percentages rather than pixels: the capture is 1280x800 but the panel
  // shows it at whatever width the window allows.
  const box = {
    left: `${(highlight.x / CAPTURE.width) * 100}%`,
    top: `${(highlight.y / CAPTURE.height) * 100}%`,
    width: `${(highlight.w / CAPTURE.width) * 100}%`,
    height: `${(highlight.h / CAPTURE.height) * 100}%`,
  };

  return (
    <motion.div
      initial={{ y: 24, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      exit={{ y: 24, opacity: 0 }}
      transition={SLIDE}
      className="flex w-full max-w-[900px] flex-col gap-5"
    >
      <div className="relative overflow-hidden rounded-xl border border-line">
        <img
          src={`data:image/png;base64,${screenshot}`}
          alt="The page as it is right now"
          className="block w-full"
        />

        {/* Dimmed, so the ring is the only thing with any brightness. */}
        <div className="pointer-events-none absolute inset-0 bg-canvas/55" />

        {hasBox && (
          <motion.div
            className="pointer-events-none absolute rounded-[3px] ring-2 ring-accent"
            style={box}
            data-testid="trust-highlight"
            initial={{ opacity: 0, scale: 1.06 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ ...SLIDE, delay: 0.1 }}
          >
            <div className="absolute inset-0 bg-accent/15" />
          </motion.div>
        )}
      </div>

      <p className="text-center text-[19px] leading-relaxed text-ink/90">{caption}</p>
    </motion.div>
  );
}
