/**
 * The real page, behind the step (2026-10-07).
 *
 * Until now the overlay covered the site completely, and the only way to see
 * it was the trust panel. That kept the screen calm, and it also made SIMBA a
 * box with words in it: nothing said there was a real website underneath,
 * being worked on. Now, when a task starts, the page shows clearly for a
 * moment (`MOTION.reveal`), then softens — blurred and covered by the canvas
 * colour — behind the step card, where nothing on it can be read and the
 * card is still the only thing to look at.
 *
 * It is a picture, not the page. The site view is still covered by the
 * overlay exactly as before (CLAUDE.md, architecture constraints); this is the
 * backend's capture of it, the same `page.preview` the trust panel shows, at
 * the site view's own size and position — the top-left corner of the window,
 * 1280x800 — so it lies exactly over the page it is a picture of. A new one
 * is asked for with every step. Password boxes are painted over before the
 * picture leaves the backend (`loop.send_preview`).
 *
 * "Show the real page" clears it. Pressed and held, it shows for as long as
 * it is held; pressed briefly, it stays until "Hide the real page". Neither
 * is counted as asking for help: only "What are you doing?" is.
 *
 * Every change here is a fade, so reduced motion changes nothing about it:
 * the sharp and the softened picture are two layers, and only their opacity
 * moves. No filter is ever animated.
 */

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

import { REVEAL } from "../copy";
import { EASE, MOTION, VEIL } from "../design";
import { useStore } from "../store";
import { Button, EyeIcon } from "./ui";

/** The frozen viewport the site view has and the backend captures at. */
const CAPTURE = { width: 1280, height: 800 };

/** Held for longer than this, a press is a hold: let go and it hides again. */
const HOLD_MS = 400;

const FADE = { duration: MOTION.veil, ease: EASE };

/** Whether a task is under way: a step or a question is, or is coming. */
function useRunning(): boolean {
  const { task, completed, failed, help, stoppedByPerson } = useStore();
  return Boolean(task) && !completed && !failed && !help && !stoppedByPerson;
}

export function Backdrop() {
  const { backdrop, task, peeking } = useStore();
  const running = useRunning();
  const [revealing, setRevealing] = useState(false);
  const revealedFor = useRef<unknown>(null);

  // The first picture of each task is shown clearly, once.
  useEffect(() => {
    if (running && backdrop && revealedFor.current !== task) {
      revealedFor.current = task;
      setRevealing(true);
    }
  }, [running, backdrop, task]);

  useEffect(() => {
    if (!revealing) return;
    const timer = window.setTimeout(() => setRevealing(false), MOTION.reveal * 1000);
    return () => window.clearTimeout(timer);
  }, [revealing]);

  const clear = revealing || peeking;
  const source = backdrop ? `data:image/png;base64,${backdrop.screenshot}` : "";

  return (
    <AnimatePresence>
      {running && backdrop && (
        <motion.div
          key="backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={FADE}
          className="pointer-events-none fixed top-0 left-0 z-0 overflow-hidden"
          style={{ width: CAPTURE.width, height: CAPTURE.height }}
          data-testid="backdrop"
          data-clear={clear ? "true" : "false"}
          role="img"
          aria-label={REVEAL.picture}
        >
          <img src={source} alt="" className="absolute inset-0 block h-full w-full max-w-none" />
          {/* Softened: blurred, and a little larger so the blur has no
              pale edge, then covered. Faded in and out, never re-blurred. */}
          <motion.img
            src={source}
            alt=""
            className="absolute inset-0 block h-full w-full max-w-none"
            style={{ filter: `blur(${VEIL.blur}px)`, scale: 1.06 }}
            initial={false}
            animate={{ opacity: clear ? 0 : 1 }}
            transition={FADE}
          />
          <motion.div
            className="absolute inset-0 bg-canvas"
            initial={false}
            animate={{ opacity: clear ? 0 : VEIL.cover }}
            transition={FADE}
          />
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/**
 * "Show the real page", under the step card. Hold to look; tap to keep it.
 */
export function PeekButton() {
  const { backdrop, peek } = useStore();
  const pressedAt = useRef(0);

  if (!backdrop) return null;

  const down = () => {
    pressedAt.current = performance.now();
    peek(true);
    // Let go anywhere — the button fades with the step while the page shows.
    const up = () => {
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
      if (performance.now() - pressedAt.current > HOLD_MS) peek(false);
    };
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
  };

  return (
    <Button
      variant="secondary"
      size="md"
      wide={false}
      onPointerDown={down}
      // A keyboard press has no pointer: it toggles, like a tap.
      onClick={(event) => event.detail === 0 && peek(true)}
      data-testid="peek"
    >
      <EyeIcon />
      {REVEAL.show}
    </Button>
  );
}

/** The way back from a peek that was tapped rather than held. */
export function PeekBack() {
  const { peeking, peek } = useStore();
  const running = useRunning();
  return (
    <AnimatePresence>
      {running && peeking && (
        <motion.div
          key="peek-back"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={FADE}
          className="fixed inset-x-0 bottom-8 z-20 flex justify-center short:bottom-4"
        >
          <Button size="md" wide={false} onClick={() => peek(false)}>
            {REVEAL.hide}
          </Button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
