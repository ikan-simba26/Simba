/**
 * "See it on the real page" — the answer on the page it came from
 * (2026-10-16).
 *
 * Before a task closes the backend reads the page again, checks it still says
 * what is about to be shown, and takes a still of it with every row or value
 * it read ringed (`task.completed.proof`). This is that still, whole, at the
 * page's own proportions, with the rings drawn where the backend found them.
 * It is never a picture from earlier in the task: only the one sent with the
 * ending, and when there is none the closing screen says why instead.
 */

import { AnimatePresence, motion } from "framer-motion";

import { PROOF } from "../copy";
import { EASE, MOTION } from "../design";
import { useStore } from "../store";
import { Button } from "./ui";

/** The frozen viewport the backend captures at (CLAUDE.md). */
const CAPTURE = { width: 1280, height: 800 };

export function ProofPanel() {
  const { proofOpen, completed, closeProof } = useStore();
  const proof = completed?.proof;

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
            <img src={`data:image/png;base64,${proof.screenshot}`} alt={PROOF.picture}
                 className="absolute inset-0 block h-full w-full" />
            {proof.rings.map((ring, index) => (
              <span key={index} aria-hidden data-testid="proof-ring"
                    className="absolute rounded-md border-4 border-accent"
                    style={{
                      left: `calc(${(ring.x / CAPTURE.width) * 100}% - 6px)`,
                      top: `calc(${(ring.y / CAPTURE.height) * 100}% - 6px)`,
                      width: `calc(${(ring.w / CAPTURE.width) * 100}% + 12px)`,
                      height: `calc(${(ring.h / CAPTURE.height) * 100}% + 12px)`,
                      boxShadow: "0 0 0 3px var(--surface)",
                    }} />
            ))}
          </div>
          <Button variant="secondary" size="md" wide={false} onClick={closeProof}>
            {PROOF.back}
          </Button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
