/**
 * The person's profile (2026-10-18): what they told SIMBA in the welcome, kept
 * on this computer.
 *
 * Kept in this window's own storage and nowhere else. The name is used for the
 * greeting and never leaves the overlay: nothing here is sent to the backend
 * but the starting level, on each `task.start`, and the "ask me before each
 * thing" setting, which already went with it. A reset (`clearProfile`) is the
 * user study's way to hand the laptop to the next person.
 */

import type { Level } from "@shared/schema";

export interface Profile {
  /** What to call them. Absent: the greeting has no name in it. */
  name?: string;
  /** The level they found comfortable; the level rules start from it. */
  level?: Level;
  /** Show the "Read this aloud" button on each step. On unless they said not. */
  readAloud: boolean;
  /** Ask before each thing, rather than "just do it and show me". */
  askEach: boolean;
  /** The welcome has been seen — finished or skipped — so it is not shown again. */
  welcomed: boolean;
  /** The websites they use most, by catalogue id (2026-11-13): first in the
   *  list. Absent: none chosen. */
  favourites?: string[];
}

const KEY = "simba.profile";
/** Where "ask me before each thing" was kept before there was a profile. */
const OLD_ASK_EACH_KEY = "simba.askEachTime";
/** The longest name kept: a greeting has one line. */
export const NAME_MAX = 24;

export const NEW_PROFILE: Profile = { readAloud: true, askEach: false, welcomed: false };

function storage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

/** The saved profile, or a new one. Never throws: no storage reads as new. */
export function loadProfile(): Profile {
  const store = storage();
  let saved: Partial<Profile> = {};
  try {
    saved = JSON.parse(store?.getItem(KEY) ?? "{}") as Partial<Profile>;
  } catch {
    saved = {};
  }
  let askEach = saved.askEach;
  if (askEach === undefined) {
    try {
      askEach = store?.getItem(OLD_ASK_EACH_KEY) === "1";
    } catch {
      askEach = false;
    }
  }
  const level = saved.level === 1 || saved.level === 2 || saved.level === 3 ? saved.level : undefined;
  const name = typeof saved.name === "string" ? cleanName(saved.name) : undefined;
  return {
    name: name || undefined,
    level,
    readAloud: saved.readAloud !== false,
    askEach: Boolean(askEach),
    welcomed: saved.welcomed === true,
    // The websites chosen in the setup (2026-11-13); absent, none.
    favourites: Array.isArray(saved.favourites)
      ? saved.favourites.filter((id): id is string => typeof id === "string").slice(0, 30)
      : undefined,
  };
}

/** Kept, if this window can keep anything; otherwise it holds until it closes. */
export function saveProfile(profile: Profile): void {
  try {
    storage()?.setItem(KEY, JSON.stringify(profile));
  } catch {
    // No storage: the profile holds for this session only.
  }
}

/** Gone, and the old setting with it: the next open is a first open. */
export function clearProfile(): void {
  try {
    storage()?.removeItem(KEY);
    storage()?.removeItem(OLD_ASK_EACH_KEY);
  } catch {
    // Nothing kept, so nothing to clear.
  }
}

/**
 * A reset the backend has not answered yet (2026-10-21): set when the person
 * says "forget it all", cleared only by the backend's answer to the
 * `tile.change` `clear` it sends. Kept here, not in memory, so a reset made
 * while the backend was not running still holds on the next open: until it is
 * answered, nothing a backend offers from before it is shown.
 */
const FORGETTING_KEY = "simba.forgetting";

export function markForgetting(): void {
  try {
    storage()?.setItem(FORGETTING_KEY, "1");
  } catch {
    // No storage: the reset holds for this session only.
  }
}

export function forgetting(): boolean {
  try {
    return storage()?.getItem(FORGETTING_KEY) === "1";
  } catch {
    return false;
  }
}

export function doneForgetting(): void {
  try {
    storage()?.removeItem(FORGETTING_KEY);
  } catch {
    // Nothing kept, so nothing to clear.
  }
}

/** A name as typed, tidied: spaces collapsed, cut to `NAME_MAX`. */
export function cleanName(name: string): string {
  return name.replace(/\s+/g, " ").trim().slice(0, NAME_MAX).trim();
}

declare global {
  interface Window {
    /** Overrides the build's welcome switch: tests of the welcome set it. */
    __simbaWelcome?: boolean;
  }
}

/**
 * Whether this build shows the welcome on a first open. On, except in the
 * tests' own builds (`VITE_SIMBA_WELCOME=0`), where every other test expects
 * the home screen; the welcome's own tests turn it back on.
 */
export function welcomeEnabled(): boolean {
  if (typeof window.__simbaWelcome === "boolean") return window.__simbaWelcome;
  return import.meta.env.VITE_SIMBA_WELCOME !== "0";
}
