/**
 * Whether a screen is drawn inside the task frame (2026-11-17). Inside it, a
 * step leaves its own way to stop to the frame's header, and the level dots
 * live there too; everything else about the step is as it was.
 */

import { createContext, useContext } from "react";

export const FramedContext = createContext(false);
export const useFramed = (): boolean => useContext(FramedContext);
