/**
 * Which renderer draws a step, by detail level.
 *
 * The three levels in CONTRACT.md differ in how much of a step is shown, not
 * in what a step *is*. So every level takes the same props and returns the
 * same shape, and adding level 1 or 3 later means writing one component and
 * adding one line to RENDERERS — no change to App, the store, or level 2.
 *
 * Only level 2 exists today. `CLAUDE.md` defers the other two until the
 * skeleton runs end to end, and it does not yet.
 */

import type { ComponentType } from "react";

import type { Level, StepPresented } from "@shared/schema";

import { Level2Step } from "./Level2Step";

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

export type StepRenderer = ComponentType<StepRendererProps>;

/**
 * Level 1 shows more (the `detail` line, per CONTRACT.md). Level 3 shows
 * less. Both slot in here.
 */
const RENDERERS: Partial<Record<Level, StepRenderer>> = {
  2: Level2Step,
};

const FALLBACK: StepRenderer = Level2Step;

export function StepView({ level, ...props }: StepRendererProps & { level: Level }) {
  const Renderer = RENDERERS[level] ?? FALLBACK;
  return <Renderer {...props} />;
}
