/**
 * The brand on screen (2026-11-02): the stacked logo while SIMBA opens, and a
 * small horizontal one in the corner of the home screen. Nowhere else. The
 * shape stays SIMBA's presence on every screen (`ui.Presence`); a logo names
 * the app, and the shape says what it is doing.
 *
 * Every file is from `assets/brand/`. Two things in the kit did not work here,
 * so `assets/brand/derived/` has the same drawings with one element taken out
 * (`frontend/test_brand.py` holds them to that):
 *
 *   - the dark logos sit on a filled rectangle, #0F1A19, and the dark canvas
 *     is #0b1817 under a light from the top, so each stood in a visible box;
 *   - the horizontal logo's tagline is 26 units tall in 300. In the corner
 *     that is about 4px, a smear on a screen where nothing is under 20px.
 *
 * The theme is the system's, as everywhere (`prefers-color-scheme` in
 * `index.css`), so the browser picks the file.
 */

import { AnimatePresence, motion, useIsPresent, useReducedMotion } from "framer-motion";
import { useEffect, useState } from "react";

import horizontal from "../../../assets/brand/derived/simba-logo-horizontal-small.svg";
import horizontalDark from "../../../assets/brand/derived/simba-logo-horizontal-small-dark.svg";
import stackedDark from "../../../assets/brand/derived/simba-logo-stacked-dark.svg";
import stacked from "../../../assets/brand/simba-logo-stacked.svg";
import { BRAND } from "../copy";
import { ARRIVE, EASE, MOTION } from "../design";
import { useStore } from "../store";

declare global {
  interface Window {
    /** Overrides the build's splash switch: the splash's own tests set it. */
    __simbaSplash?: boolean;
  }
}

/** Never shorter than this, so a backend already up does not flash the logo. */
const LEAST_MS = 1200;

/**
 * Never longer than this. Then the home screen, backend or no backend: it
 * always was usable without one, and the next press connects (`store.startTask`).
 * On two real starts, on battery, it was up for 7.8s and 9.8s (EVALUATION.md,
 * 2026-11-02).
 */
const MOST_MS = 15000;

/** The wait between one attempt failing and the next. */
const AGAIN_MS = 500;

/**
 * Whether this build shows the logo while opening. On, except in the tests'
 * own builds (`VITE_SIMBA_SPLASH=0`), where every other test expects the home
 * screen at once; `test_brand.py` turns it back on, as the welcome's do.
 */
export function splashEnabled(): boolean {
  if (typeof window.__simbaSplash === "boolean") return window.__simbaSplash;
  return import.meta.env.VITE_SIMBA_SPLASH !== "0";
}

/**
 * Whether the logo is still up. Never under reduced motion: the home screen is
 * simply there, as its entrance is not played then either.
 *
 * It waits for the backend itself, which takes more than watching the socket.
 * `run.ps1` and `run.sh` start the window first, because the backend attaches
 * to it, so the first attempt fails while the backend is still importing, and
 * nothing tried again until the person pressed something. Waiting on that
 * attempt would never end, and leaving when it failed would leave too soon. So
 * while the logo is up it tries again, and only then: nothing can be pressed
 * behind it, whereas on the home screen a late attempt would replace the
 * connection a press had just opened.
 *
 * And it leaves on the backend's first message, not on the socket opening: the
 * first message is the home screen's offer (`history.offered`), which came
 * seconds after the socket opened on a real start (EVALUATION.md, 2026-11-02).
 * Leaving earlier showed a home screen that rearranged itself a moment later,
 * under someone's pointer, when their own tiles arrived.
 */
export function useSplash(): boolean {
  const reduce = useReducedMotion() ?? false;
  const status = useStore((state) => state.status);
  const heard = useStore((state) => state.log.length > 0);
  const connect = useStore((state) => state.connect);
  const [up, setUp] = useState(() => !reduce && splashEnabled());
  const [held, setHeld] = useState(false);

  useEffect(() => {
    if (!up) return;
    const least = window.setTimeout(() => setHeld(true), LEAST_MS);
    const most = window.setTimeout(() => setUp(false), MOST_MS);
    return () => {
      window.clearTimeout(least);
      window.clearTimeout(most);
    };
    // Once, from the moment it opens.
  }, []);

  useEffect(() => {
    if (held && heard) setUp(false);
  }, [held, heard]);

  useEffect(() => {
    if (!up || status !== "closed") return;
    const again = window.setTimeout(() => connect(), AGAIN_MS);
    return () => window.clearTimeout(again);
  }, [up, status, connect]);

  return up;
}

/** The light file, with the dark one in its place when the system is dark. */
function Logo({ light, dark, className }: { light: string; dark: string; className: string }) {
  return (
    <picture>
      <source srcSet={dark} media="(prefers-color-scheme: dark)" />
      <img src={light} alt={BRAND.name} draggable={false} className={className} />
    </picture>
  );
}

/**
 * The stacked logo, centred, over the canvas. It leaves as a fade, with the
 * home screen arriving behind it, and takes no presses while it does.
 */
function SplashScreen() {
  const present = useIsPresent();
  return (
    <motion.div
      className="simba-canvas fixed inset-0 z-50 flex items-center justify-center bg-canvas"
      style={{ pointerEvents: present ? "auto" : "none" }}
      exit={{ opacity: 0 }}
      transition={{ duration: MOTION.slow, ease: EASE }}
      data-testid="splash"
    >
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                  transition={{ duration: MOTION.slow, ease: EASE }}>
        <Logo light={stacked} dark={stackedDark} className="h-80 w-auto short:h-64" />
      </motion.div>
    </motion.div>
  );
}

export function Splash({ up }: { up: boolean }) {
  return <AnimatePresence>{up && <SplashScreen key="splash" />}</AnimatePresence>;
}

/**
 * The small logo, in the corner the home screen leaves empty: the column is
 * 880 of 1280 and the presence mark is centred, so it takes no room from
 * either and moves nothing. Fixed, because the screens themselves are
 * transformed while they arrive.
 */
export function HomeLogo({ shown }: { shown: boolean }) {
  return (
    <AnimatePresence initial={false}>
      {shown && (
        <motion.div key="home-logo"
                    className="pointer-events-none fixed top-6 left-8 z-[1] short:top-3"
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                    transition={ARRIVE} data-testid="home-logo">
          <Logo light={horizontal} dark={horizontalDark} className="h-12 w-auto" />
        </motion.div>
      )}
    </AnimatePresence>
  );
}
