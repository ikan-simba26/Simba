/**
 * How a step is drawn, at whichever level is current.
 *
 * The three levels used to be a table of components keyed by level, on the
 * assumption that they would be independent trees. Building the level change
 * showed that they cannot be: swapping one tree for another can only
 * crossfade, and the change has to read as the interface folding down. So
 * the levels are now one persistent tree in `StepShell`, described by the
 * data in `levels.ts`.
 *
 * This file stays as the seam. Everything upstream passes a level and a step
 * and does not care how either is drawn.
 */

import type { Level, StepPresented } from "@shared/schema";

import { StepShell } from "./StepShell";

export interface StepRendererProps {
  step: StepPresented;
  values: Record<string, string>;
  onChange: (fieldId: string, value: string) => void;
  onAction: (actionId: string) => void;
  /** True while the backend is waiting on the user: the actions lead. */
  waiting: boolean;
  /** Already answered: the step stays up, but cannot be answered twice. */
  answered: boolean;
}

export function StepView({ level, ...props }: StepRendererProps & { level: Level }) {
  return <StepShell level={level} {...props} />;
}
