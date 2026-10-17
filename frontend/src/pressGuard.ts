/**
 * Every press, logged; and a press on a button that has only just arrived
 * where it is, ignored (2026-10-16).
 *
 * Why. In the real window a walk pressing "Tomorrow" the moment the day
 * question appeared twice ended "I've stopped, as you asked." — a press that
 * landed on "Stop this". Layout moves under a pointer: a screen sliding in, a
 * level folding, a notice arriving. Someone aiming at one button can hit
 * another that was not there a moment before.
 *
 * The log. Each press records which button it landed on, the level at that
 * moment, how long since that button last moved or appeared, and how long
 * since anything on screen last moved. Kept in `window.__simbaPresses` (the
 * last 200) for a script reading the real window, and in the console.
 *
 * The guard. A press is ignored — nothing happens, as if it had missed —
 * when the button it landed on moved or appeared in the last `settleMs`
 * (500), or when a different button was under that point in the last
 * `settleMs`. So "Stop this" can never be pressed where another button was a
 * moment before, and nothing is pressed that the person could not yet have
 * seen. A person who pressed too soon presses again.
 *
 * Measured from what is on screen, not from what the app meant to do: every
 * visible button's box is read whenever the page changes (a mutation, a
 * resize), frame by frame until nothing moves, and not at all at rest.
 */

import type { Level } from "@shared/schema";

export interface Press {
  /** The button's own words, or its accessible name. */
  label: string;
  level: Level;
  /** Since that button last moved or appeared, in milliseconds. */
  sinceButtonMs: number;
  /** Since anything on screen last moved, in milliseconds. */
  sinceLayoutMs: number;
  /** A different button that was under this point within `settleMs`. */
  wasUnder: string | null;
  ignored: boolean;
  at: number;
}

declare global {
  /** Vite's build-time values; only `VITE_SIMBA_SETTLE_MS` is read here. */
  interface ImportMeta {
    readonly env: Record<string, string | undefined>;
  }
  interface Window {
    __simbaPresses?: Press[];
    /** Overrides the build's settle time: tests of the guard set it. */
    __simbaSettleMs?: number;
    /** The settle time in force, for a script that has to press like a person. */
    __simbaSettle?: number;
  }
}

/** How long a button must have stayed put before a press on it counts. */
export function settleMs(): number {
  if (typeof window.__simbaSettleMs === "number") return window.__simbaSettleMs;
  const built = import.meta.env.VITE_SIMBA_SETTLE_MS;
  return built !== undefined && Number.isFinite(Number(built)) ? Number(built) : 500;
}

interface Seen {
  /** Where it was when it last counted as moving. */
  key: string;
  /** Where it was on the last frame looked at, to the pixel. */
  exact: string;
  since: number;
  /** Where it has been, recently: [left, top, right, bottom, until]. */
  trail: [number, number, number, number, number][];
}

const LOG_SIZE = 200;

/** Movement up to this much is not moving: a pressed button's own 1px nudge
 *  (`active:translate-y-px`) made every press look like a press on a button
 *  that had just moved (found on the first logged walk, 2026-10-16). */
const STILL_PX = 2;

function near(a: string, b: string): boolean {
  const one = a.split(",").map(Number);
  const two = b.split(",").map(Number);
  return one.every((value, index) => Math.abs(value - two[index]) <= STILL_PX);
}

function nameOf(button: HTMLElement): string {
  return (button.innerText || button.getAttribute("aria-label") || "?").trim().replace(/\s+/g, " ");
}

/**
 * Start watching. Returns the function that stops it. `level` is read at the
 * moment of each press.
 */
export function watchPresses(level: () => Level): () => void {
  const seen = new Map<HTMLElement, Seen>();
  /** Buttons gone from where they were: for "was another button under here". */
  const ghosts: { name: string; box: [number, number, number, number]; until: number }[] = [];
  /** A pointer press ignored, so the click that follows it is too. */
  let refused: { button: HTMLElement; at: number } | null = null;
  let lastLayout = performance.now();
  let frame = 0;
  let stillFrames = 0;

  /** Moved past the tolerance, or still easing by a pixel: keep looking. */
  const scan = (): { moved: boolean; easing: boolean } => {
    const now = performance.now();
    let moved = false;
    let easing = false;
    const shown = new Set<HTMLElement>();
    for (const button of document.querySelectorAll<HTMLElement>("button")) {
      const r = button.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      shown.add(button);
      const key = `${Math.round(r.left)},${Math.round(r.top)},${Math.round(r.width)},` +
                  `${Math.round(r.height)}`;
      const was = seen.get(button);
      if (!was || !near(was.key, key)) {
        const trail = (was?.trail ?? []).filter((t) => now - t[4] < settleMs() + 50);
        if (was) {
          const [l, t, w, h] = was.key.split(",").map(Number);
          trail.push([l, t, l + w, t + h, now]);
        }
        seen.set(button, { key, exact: key, since: now, trail });
        moved = true;
      } else if (was.exact !== key) {
        // Easing its last pixel or two: not a move, but keep looking until
        // it stops, and keep where it is up to date. Stopping a pixel early
        // left the place it was last seen stale, and the look taken at a
        // press then read the gap as a fresh move (2026-10-16).
        was.exact = key;
        easing = true;
      }
    }
    // A button that has gone leaves its last place behind, for a moment.
    for (const [button, was] of seen) {
      if (shown.has(button)) continue;
      const [l, t, w, h] = was.key.split(",").map(Number);
      ghosts.push({ name: nameOf(button), box: [l, t, l + w, t + h], until: now });
      seen.delete(button);
      moved = true;
    }
    ghosts.splice(0, ghosts.length, ...ghosts.filter((g) => now - g.until < settleMs() + 50));
    if (moved) lastLayout = now;
    return { moved, easing };
  };

  const settle = () => {
    frame = 0;
    const { moved, easing } = scan();
    stillFrames = moved || easing ? 0 : stillFrames + 1;
    // Keep looking while things move, and two frames after.
    if (stillFrames < 2) frame = requestAnimationFrame(settle);
  };
  const changed = () => {
    stillFrames = 0;
    if (!frame) frame = requestAnimationFrame(settle);
  };

  const observer = new MutationObserver(changed);
  observer.observe(document.body, {
    subtree: true, childList: true, attributes: true,
    attributeFilter: ["style", "class", "disabled", "hidden"],
  });
  window.addEventListener("resize", changed);
  window.__simbaSettle = settleMs();
  scan();

  const onPress = (event: MouseEvent) => {
    const button = (event.target as Element | null)?.closest?.("button") as HTMLElement | null;
    if (!button || !document.body.contains(button)) {
      // A press that landed on no button at all: logged, for finding out
      // what a press aimed at a button that had just moved hit instead.
      if (event.type === "click") {
        const target = event.target as HTMLElement | null;
        const log = (window.__simbaPresses ??= []);
        log.push({
          label: `(no button: ${target?.tagName?.toLowerCase() ?? "?"} ` +
                 `${(target?.innerText ?? "").trim().slice(0, 30)})`,
          level: level(), sinceButtonMs: -1,
          sinceLayoutMs: Math.round(performance.now() - lastLayout), wasUnder: null,
          ignored: false, at: Date.now(),
        });
      }
      return;
    }
    scan();  // as it is at this instant, not as it was a frame ago
    const now = performance.now();
    const own = seen.get(button);
    const sinceButton = own ? now - own.since : 0;
    const x = event.clientX;
    const y = event.clientY;
    const inside = (b: [number, number, number, number]) =>
      x >= b[0] && x <= b[2] && y >= b[1] && y <= b[3];
    const limit = settleMs();
    let wasUnder: string | null = null;
    for (const [other, was] of seen) {
      if (other === button) continue;
      const [l, t, w, h] = was.key.split(",").map(Number);
      const recent = was.trail.some((p) => now - p[4] < limit && inside([p[0], p[1], p[2], p[3]]));
      if (recent || (now - was.since < limit && inside([l, t, l + w, t + h]))) {
        wasUnder = nameOf(other);
        break;
      }
    }
    if (!wasUnder) {
      const ghost = ghosts.find((g) => now - g.until < limit && inside(g.box));
      if (ghost) wasUnder = ghost.name;
    }
    // A keyboard press has no point; only its own button's settling counts.
    const keyboard = event.detail === 0 && event.type === "click";
    const followsRefused = event.type === "click" && refused !== null &&
      refused.button === button && now - refused.at < 1000;
    const ignored = followsRefused ||
      (limit > 0 && (sinceButton < limit || (!keyboard && wasUnder !== null)));
    if (event.type === "pointerdown") refused = ignored ? { button, at: now } : null;
    if (event.type === "click" || ignored) {
      const press: Press = {
        label: nameOf(button), level: level(), sinceButtonMs: Math.round(sinceButton),
        sinceLayoutMs: Math.round(now - lastLayout), wasUnder, ignored, at: Date.now(),
      };
      if (event.type === "click") {
        const log = (window.__simbaPresses ??= []);
        log.push(press);
        if (log.length > LOG_SIZE) log.splice(0, log.length - LOG_SIZE);
        // As text, so the host can copy it into its log (frontend/electron/main.ts).
        console.debug(`[simba] press ${JSON.stringify(press)}`);
      }
    }
    if (ignored) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  };

  window.addEventListener("pointerdown", onPress, true);
  window.addEventListener("click", onPress, true);
  return () => {
    observer.disconnect();
    window.removeEventListener("resize", changed);
    window.removeEventListener("pointerdown", onPress, true);
    window.removeEventListener("click", onPress, true);
    if (frame) cancelAnimationFrame(frame);
  };
}
