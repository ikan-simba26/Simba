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
import { useState } from "react";

import type { Highlight, PagePreview } from "@shared/schema";

import { FRAME, TRUST } from "../copy";
import { EASE, MOTION } from "../design";
import { useStore } from "../store";
import { useFramed } from "./framed";
import { Button, EyeIcon } from "./ui";

const SLIDE = { duration: MOTION.slow, ease: EASE };

/** The frozen viewport the backend captures at (CLAUDE.md). */
const CAPTURE = { width: 1280, height: 800 };

/**
 * How much of the page the close-up shows, in capture pixels.
 *
 * At least this wide, and at least four times the target: wide enough that
 * the ringed thing is seen in its place on the page — the field it sits
 * under, the words beside it — and narrow enough that it is several times its
 * real size. A 110px button comes out about 230px wide in the panel.
 */
const CLOSE_UP_MIN_WIDTH = 480;
const CLOSE_UP_TARGET_MULTIPLE = 4;

/** The part of the capture to show: the whole page, or around the target. */
function frameFor(highlight: Highlight, whole: boolean) {
  if (whole) return { x: 0, y: 0, w: CAPTURE.width, h: CAPTURE.height };
  const w = Math.min(
    CAPTURE.width,
    Math.max(CLOSE_UP_MIN_WIDTH, highlight.w * CLOSE_UP_TARGET_MULTIPLE),
  );
  // Same shape as the page, so the picture never stretches.
  const h = (w * CAPTURE.height) / CAPTURE.width;
  const cx = highlight.x + highlight.w / 2;
  const cy = highlight.y + highlight.h / 2;
  const x = Math.min(Math.max(cx - w / 2, 0), CAPTURE.width - w);
  const y = Math.min(Math.max(cy - h / 2, 0), CAPTURE.height - h);
  return { x, y, w, h };
}

export function TrustControl() {
  const { task, completed, failed, trustOpen, askWhat } = useStore();
  // "See the real page" in the task frame (2026-11-17): the same press, the same
  // picture, shown in the middle panel with a glowing ring on what SIMBA touches.
  const framed = useFramed();

  // Only while there is something to be doing. The way *out* of the panel
  // lives inside the panel: this control sits under it and cannot be
  // clicked once it is open, which left no way to dismiss it at all.
  if (!task || completed || failed || trustOpen) return null;

  return (
    // A real button, and a visible one (2026-09-21). It was a grey
    // underlined link, which is the one form of control this audience is
    // least likely to recognise as pressable — on the one question that
    // exists to make the whole system trustworthy.
    <Button variant="secondary" size="md" wide={false} onClick={askWhat}>
      <EyeIcon />
      {framed ? FRAME.seeReal : TRUST.ask}
    </Button>
  );
}

export function TrustPanel() {
  const { trustOpen, preview, noPicture, closeTrust } = useStore();
  const showing = trustOpen && (preview || noPicture);

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
          {/* The way back is inside `Shot`, beside the close-up toggle, so
              the two choices sit together under the picture. */}
          {preview ? <Shot preview={preview} onHide={closeTrust} /> : (
            // No picture came (2026-10-16): said, with the way back.
            <div className="flex max-w-xl flex-col items-center gap-6 text-center"
                 data-testid="no-picture" role="status">
              <p className="text-title font-semibold text-ink">{TRUST.noPicture}</p>
              <p className="text-body text-soft">{TRUST.tryAgain}</p>
              <Button variant="secondary" size="md" wide={false} onClick={closeTrust}>
                {TRUST.close}
              </Button>
            </div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/**
 * The picture of the real page, close up on the thing about to be touched.
 *
 * It used to show the whole 1280x800 page shrunk into the panel, which made
 * a button the size of a word: the ring was there, and so small that the
 * person had to find it (2026-09-21). Now it opens on the area round the
 * target, several times larger, and the whole page is one button away for
 * someone who wants to see where on the page that is. With nothing ringed —
 * a preview with an empty highlight — there is nothing to zoom to, and the
 * whole page is all it shows.
 *
 * The zoom is the one picture moved, not two pictures swapped: the frame
 * slides out from the target to the page and back, slowly, so the person
 * sees the close-up is part of the whole.
 */
function Shot({ preview, onHide, inline = false }: {
  preview: PagePreview; onHide: () => void; inline?: boolean;
}) {
  const site = useStore((state) => state.taskSite);
  const { highlight, caption, screenshot } = preview;
  const hasBox = highlight.w > 0 && highlight.h > 0;
  const [whole, setWhole] = useState(!hasBox);
  const frame = frameFor(highlight, whole || !hasBox);

  // Everything in percentages of the frame, so the same numbers work at any
  // panel width and animate smoothly between the close-up and the page.
  const picture = {
    width: `${(CAPTURE.width / frame.w) * 100}%`,
    left: `${(-frame.x / frame.w) * 100}%`,
    top: `${(-frame.y / frame.h) * 100}%`,
  };
  const ring = {
    left: `${((highlight.x - frame.x) / frame.w) * 100}%`,
    top: `${((highlight.y - frame.y) / frame.h) * 100}%`,
    width: `${(highlight.w / frame.w) * 100}%`,
    height: `${(highlight.h / frame.h) * 100}%`,
  };

  const picturebox = (
      <div
        className={`relative overflow-hidden rounded-xl border border-line bg-sunk shadow-card
                    ${inline ? "max-h-full max-w-full" : "w-full"}`}
        style={inline ? { aspectRatio: `${CAPTURE.width} / ${CAPTURE.height}`, height: "100%" }
                      : { aspectRatio: `${CAPTURE.width} / ${CAPTURE.height}` }}
      >
        <motion.img
          src={`data:image/png;base64,${screenshot}`}
          alt={TRUST.picture}
          className="absolute block max-w-none"
          initial={false}
          animate={picture}
          transition={SLIDE}
        />

        {/* Dimmed, so the ring is the only thing with any brightness. */}
        {(!inline || hasBox) && <div className="pointer-events-none absolute inset-0 bg-canvas/45" />}

        {hasBox && (
          <motion.div
            className={`pointer-events-none absolute rounded-[6px] ${inline ? "simba-ring-glow"
                        : "ring-4 ring-accent"}`}
            data-testid="trust-highlight"
            initial={false}
            animate={ring}
            transition={SLIDE}
          >
            <div className="absolute inset-0 bg-accent/15" />
          </motion.div>
        )}
      </div>
  );

  const buttons = (
      <div className="flex flex-wrap items-center justify-center gap-4">
        {hasBox && (
          <Button variant="secondary" size="md" wide={false} onClick={() => setWhole(!whole)}>
            {whole ? TRUST.closeUp : TRUST.whole}
          </Button>
        )}
        {/* A real button, not a link: this is the only way back, and it has
            to look like something that can be pressed. */}
        <Button size="md" wide={false} onClick={onHide}>
          {inline ? FRAME.hideReal : TRUST.hide}
        </Button>
      </div>
  );

  if (inline) {
    // In the middle panel of the task frame (screen C): a browser's bar saying
    // it is live, the page with the ring, and the way back.
    return (
      <div className="flex h-full flex-col gap-3 p-5 short:gap-2 short:p-3" data-testid="live-page-centre">
        <div className="flex shrink-0 items-center gap-3 rounded-lg bg-sunk px-4 py-2 text-small text-soft">
          <span className="rounded-full bg-accent px-3 py-0.5 text-small font-semibold text-accent-ink">
            {FRAME.live}
          </span>
          <span className="min-w-0 truncate">{site ? site.address.replace(/^https?:\/\//, "") : ""}</span>
        </div>
        <div className="flex min-h-0 flex-1 items-center justify-center">{picturebox}</div>
        {caption && <p className="shrink-0 text-center text-lead font-semibold text-ink short:text-body">{caption}</p>}
        <div className="shrink-0">{buttons}</div>
        <p className="shrink-0 text-center text-small text-soft short:hidden">{FRAME.liveNote}</p>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ y: 24, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      exit={{ y: 24, opacity: 0 }}
      transition={SLIDE}
      className="flex w-full max-w-[860px] flex-col items-center gap-6"
    >
      {picturebox}
      <p className="text-center text-title font-semibold text-ink">{caption}</p>
      {buttons}
    </motion.div>
  );
}

/**
 * "See the real page" in the middle panel of the task frame (2026-11-17,
 * screen C): the live website, as the backend last pictured it, with a
 * glowing ring on what SIMBA is about to touch or is touching. The small live
 * picture the backend sends while SIMBA works is shown at once, ringless,
 * until the one asked for arrives.
 */
export function LivePage() {
  const { preview, livePreview, noPicture, closeTrust } = useStore();
  const shown: PagePreview | null = preview ?? (livePreview
    ? { screenshot: livePreview, highlight: { x: 0, y: 0, w: 0, h: 0 }, caption: "" } : null);
  return (
    <div className="h-full" data-testid="trust-panel">
      {shown ? <Shot key={preview ? "asked" : "live"} preview={shown} onHide={closeTrust} inline /> : (
        <div className="flex h-full flex-col items-center justify-center gap-5 p-8 text-center" role="status"
             data-testid={noPicture ? "no-picture" : "live-page-waiting"}>
          <p className="text-title font-semibold text-ink">{noPicture ? TRUST.noPicture : FRAME.waitingPicture}</p>
          {noPicture && <p className="text-body text-soft">{TRUST.tryAgain}</p>}
          <Button variant="secondary" size="md" wide={false} onClick={closeTrust}>
            {noPicture ? TRUST.close : FRAME.hideReal}
          </Button>
        </div>
      )}
    </div>
  );
}
