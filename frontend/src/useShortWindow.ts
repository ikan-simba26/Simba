/**
 * Whether the window is short enough for the compact layout.
 *
 * The CSS side is the `short:` variant in `index.css`; this is the same test
 * for the sizes Framer animates, which a class cannot reach. Both read
 * `SHORT_HEIGHT`, the CSS by copy.
 */

import { useEffect, useState } from "react";

import { SHORT_HEIGHT } from "./design";

const QUERY = `(max-height: ${SHORT_HEIGHT}px)`;

export function useShortWindow(): boolean {
  const [short, setShort] = useState(() => window.matchMedia(QUERY).matches);

  useEffect(() => {
    const query = window.matchMedia(QUERY);
    const update = () => setShort(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  return short;
}
