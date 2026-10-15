/**
 * "See it on the real page" — the answer on the page it came from
 * (2026-10-16).
 *
 * Before a task closes the backend reads the page again, checks it still says
 * what is about to be shown, and takes a still of it with every row or value
 * it read ringed (`task.completed.proof`). This is that still, whole, at the
 * page's own proportions, with the rings drawn where the backend found them,
 * close up on them first and the whole page a press away.
 * It is never a picture from earlier in the task: only the one sent with the
 * ending, and when there is none the closing screen says why instead.
 */

import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";

import type { Highlight } from "@shared/schema";

import { PROOF, TRUST } from "../copy";
import { EASE, MOTION } from "../design";
import { useStore } from "../store";
import { Button } from "./ui";

/** The frozen viewport the backend captures at (CLAUDE.md). */
const CAPTURE = { width: 1280, height: 800 };

/** Room round the rings in the close-up, and its narrowest. */
const MARGIN = 60;
const CLOSE_UP_MIN_WIDTH = 560;

/**
 * The part of the page to show: round every ring, with room to read what is
 * beside them — a column's heading, the row's other cells — at the page's
 * own proportions, or the whole page (2026-10-16). On the whole bill page the
 * two ringed cells were a few pixels high.
 */
export function proofFrame(rings: Highlight[], whole: boolean) {
  if (whole || rings.length === 0) return { x: 0, y: 0, w: CAPTURE.width, h: CAPTURE.height };
  const left = Math.min(...rings.map((r) => r.x)) - MARGIN;
  const top = Math.min(...rings.map((r) => r.y)) - MARGIN;
  const right = Math.max(...rings.map((r) => r.x + r.w)) + MARGIN;
  const bottom = Math.max(...rings.map((r) => r.y + r.h)) + MARGIN;
  const ratio = CAPTURE.width / CAPTURE.height;
  let w = Math.max(CLOSE_UP_MIN_WIDTH, right - left, (bottom - top) * ratio);
  w = Math.min(w, CAPTURE.width);
  const h = w / ratio;
  const x = Math.min(Math.max((left + right - w) / 2, 0), CAPTURE.width - w);
  const y = Math.min(Math.max((top + bottom - h) / 2, 0), CAPTURE.height - h);
  return { x, y, w, h };
}

export function ProofPanel() {
  const { proofOpen, completed, closeProof } = useStore();
  const proof = completed?.proof;
  const [whole, setWhole] = useState(false);
  const frame = proofFrame(proof?.rings ?? [], whole);
  // The page, scaled and moved so `frame` fills the window onto it.
  const page = {
    width: `${(CAPTURE.width / frame.w) * 100}%`,
    height: `${(CAPTURE.height / frame.h) * 100}%`,
    left: `${(-frame.x / frame.w) * 100}%`,
    top: `${(-frame.y / frame.h) * 100}%`,
  };

  return (
    <AnimatePresence>
      {proofOpen && proof && (
        <motion.div
          key="proof"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: MOTION.slow, ease: EASE }}
          className="fixed inset-0 z-10 flex flex-col items-center justify-center gap-5
                     bg-canvas px-6 py-6 short:gap-3 short:py-3"
          data-testid="proof-panel"
        >
          <p className="text-lead font-semibold text-ink short:text-body">{proof.caption}</p>
          {/* As large as the window allows, never stretched. */}
          <div className="relative w-full overflow-hidden rounded-lg border-2 border-edge
                          shadow-lift"
               style={{ maxWidth: `min(1180px, calc((100dvh - 190px) * ${CAPTURE.width / CAPTURE.height}))`,
                        aspectRatio: `${CAPTURE.width} / ${CAPTURE.height}` }}>
            <div className="absolute transition-all duration-500" style={page}
                 data-testid="proof-page">
            <img src={`data:image/png;base64,${proof.screenshot}`} alt={PROOF.picture}
                 className="absolute inset-0 block h-full w-full max-w-none" />
            {proof.rings.map((ring, index) => (
              <span key={index} aria-hidden data-testid="proof-ring"
                    className="absolute rounded-sm border-[3px] border-accent"
                    // Exactly round what was read, never wider (2026-10-16):
                    // drawn 6px outside it, a ring covered the column heading
                    // that says what the value is, and the next row's text.
                    style={{
                      left: `${(ring.x / CAPTURE.width) * 100}%`,
                      top: `${(ring.y / CAPTURE.height) * 100}%`,
                      width: `${(ring.w / CAPTURE.width) * 100}%`,
                      height: `${(ring.h / CAPTURE.height) * 100}%`,
                    }} />
            ))}
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <Button variant="secondary" size="md" wide={false} onClick={closeProof}>
              {PROOF.back}
            </Button>
            <Button variant="quiet" size="md" wide={false} onClick={() => setWhole(!whole)}>
              {whole ? TRUST.closeUp : TRUST.whole}
            </Button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
