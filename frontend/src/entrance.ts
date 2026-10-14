/**
 * The home screen's entrance plays once (2026-10-14): when SIMBA opens, the
 * shape settles and the tiles rise in. Coming back to the home screen after a
 * task, it is simply there. Under reduced motion it never plays.
 */

let played = false;

/** Whether the entrance should play now. Asking says it has been used. */
export function takeEntrance(reducedMotion: boolean): boolean {
  if (played || reducedMotion) {
    played = true;
    return false;
  }
  played = true;
  return true;
}

/** Whether it has played (or been passed over) already. */
export function entrancePlayed(): boolean {
  return played;
}
