/**
 * Which picture a tile on the home screen wears, and so its colour
 * (2026-11-10). Four pictures: a train, a bill, a book and a globe. Each has
 * its own calm colour (`--pic-*` in `index.css`), and the colour always goes
 * with the picture, never on its own: two tiles of the same colour show the
 * same picture, and the tile's words say the same thing as both.
 *
 * The three things SIMBA can do wear theirs by what they are. A tile the
 * person kept, or one a helper taught, wears the picture its name asks for,
 * by `pictureForName`: the first word in the name that is on one of the
 * lists below decides; a name with none of them gets the globe, which says
 * "something on a website" and nothing more.
 */

import type { FlowName } from "@shared/schema";

export type PictureKind = "train" | "bill" | "course" | "other";

/** The words that ask for each picture, whole words, any case. */
export const PICTURE_WORDS: Record<Exclude<PictureKind, "other">, readonly string[]> = {
  train: ["train", "trains", "railway", "railways"],
  bill: ["bill", "bills", "electricity", "electric"],
  course: ["course", "courses", "register", "registration"],
};

/** A built-in thing SIMBA can do, by what it is. */
export function pictureForFlow(flow: FlowName): PictureKind {
  return flow === "railways" ? "train" : flow === "billing" ? "bill" : "course";
}

/**
 * A kept or taught tile, by its name: the first word in it that is on one of
 * the lists, so "Trains to pay my bill" is a train. None: the globe.
 */
export function pictureForName(name: string): PictureKind {
  const words = name.toLowerCase().match(/[a-z]+/g) ?? [];
  for (const word of words) {
    for (const kind of ["train", "bill", "course"] as const) {
      if (PICTURE_WORDS[kind].includes(word)) return kind;
    }
  }
  return "other";
}
