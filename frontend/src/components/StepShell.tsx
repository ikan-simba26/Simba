/**
 * One step, at whichever level is current — and the fold between levels.
 *
 * This is deliberately a single persistent tree rather than three components
 * swapped by level. A swap can only crossfade; what has to happen when the
 * level changes is a *collapse*: the regions that stop existing shrink to
 * nothing while everything below slides up into the space. That needs the
 * surviving elements to stay mounted throughout, so the levels differ by
 * which regions they include and how those regions are laid out, not by
 * which component is on screen.
 *
 * Every region that can come and go lives in a <Fold>, which animates its own
 * height to zero on the way out and takes its spacing with it.
 */

import { AnimatePresence, motion } from "framer-motion";
import type { ReactNode } from "react";

import type { Finding, Level, StepAction, StepField } from "@shared/schema";

import { FOUND, STEP } from "../copy";
import { EASE, MOTION, TYPE } from "../design";
import { LEVELS, firstSentence, typeSize } from "../levels";
import type { StepRendererProps } from "./StepView";
import { buttonClass } from "./ui";

/**
 * The one curve and duration the level change uses.
 *
 * Measured rather than guessed: [0.32, 0.72, 0, 1] put 72% of the movement
 * into the first third of the duration, which reads as a snap with a long
 * tail rather than something folding. This curve accelerates and decelerates
 * evenly, so the collapse is legible the whole way down.
 */
export const FOLD = { duration: MOTION.fold, ease: EASE };

/**
 * Arrivals wait for departures.
 *
 * Run both at once and the column briefly gets *taller* before it folds —
 * measured at 253px growing to 263px on the way from level 2 to level 3,
 * because the outgoing button was still collapsing while the incoming text
 * and the larger heading were already expanding. A bump upwards is the
 * opposite of the gesture. Letting the collapse lead by 120ms makes the
 * height fall monotonically, which is what reads as folding.
 */
export const UNFOLD = { ...FOLD, duration: MOTION.unfold, delay: MOTION.unfoldDelay };

/**
 * A region that may not exist at every level. Collapses its own height and
 * its own leading space, so nothing is left behind holding a gap open.
 */
function Fold({
  show,
  gap,
  children,
}: {
  show: boolean;
  gap: number;
  children: ReactNode;
}) {
  return (
    <AnimatePresence initial={false}>
      {show && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto", transition: UNFOLD }}
          exit={{ opacity: 0, height: 0, transition: FOLD }}
          className="overflow-hidden"
        >
          {/* Spacing grows on the way to a simpler level too, so it waits
              with everything else that arrives. Left on FOLD it added 8px
              while the button below was still collapsing — a small bump, but
              in the wrong direction. */}
          <motion.div animate={{ paddingTop: gap, transition: UNFOLD }}>
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function StepShell({
  step,
  values,
  onChange,
  onAction,
  waiting,
  answered,
  level,
}: StepRendererProps & { level: Level }) {
  const spec = LEVELS[level];

  const instruction =
    spec.instruction === "first-sentence" ? firstSentence(step.instruction) : step.instruction;

  const fields =
    spec.fields === "required-only"
      ? step.fields.filter((field) => !(values[field.id] ?? field.value))
      : step.fields;

  const findings: Finding[] = step.findings ?? [];

  const [primary, ...rest] = orderActions(step.actions);
  const secondary = rest[0];

  return (
    // No `layout` on this container either. Every region below animates its
    // own height, so a layout projection on top of them has nothing to add
    // and actively fought them: it threw the column 11px taller for the first
    // ~50ms of every fold before the descent started.
    <div className="relative" data-testid="step-shell">
      {/* Every level sits on a card now (`App.Step`). Level 1, the fullest,
          adds a hairline round it — faded in rather than a border that pops —
          so the densest level still reads as the most form-like. The insets
          match the card's padding, so the line is the card's own edge. */}
      <motion.div
        aria-hidden
        className="pointer-events-none absolute -inset-x-10 -inset-y-9 rounded-xl border
                   border-line"
        animate={{ opacity: spec.shell === "card" ? 1 : 0 }}
        transition={FOLD}
      />

      <div className="relative flex flex-col">
        <Fold show={spec.progress !== "none"} gap={0}>
          {/* Quieter at level 2 than at level 1, and still readable: 0.4 of
              the soft colour was 2.5:1, under any contrast rule. 0.75 keeps
              it above 4.5:1 in both themes. */}
          <motion.p
            animate={{
              // Level 1 states it; level 2 murmurs it. A step counter is
              // reassurance for someone coping and pressure for someone who
              // is not, which is why level 3 has none at all.
              fontSize: spec.progress === "full" ? `${TYPE.caption}px` : "13px",
              opacity: spec.progress === "full" ? 1 : 0.75,
            }}
            transition={FOLD}
            className="font-medium tracking-wide text-soft"
          >
            {STEP.count(step.step_index, step.step_total)}
          </motion.p>
        </Fold>

        {/* No `layout` here. A layout animation projects the element's box
            with a transform, which fights an animation of fontSize — the
            heading rendered at roughly a third of its size at level 3. The
            container's `layout` handles the reflow; the heading only grows. */}
        {/* "It is your turn: the buttons lead and the rest recedes." The
            recede is kept and softened: at 0.55 the instruction measured
            3.8:1 on the light card, which fails for the one sentence the
            person most needs to read. At 0.8 it is 8.7:1. */}
        <motion.h1
          animate={{
            // Units are required: Framer silently ignores a bare number
            // for fontSize, where it appends px for height and padding.
            fontSize: `${typeSize(level, instruction)}px`,
            opacity: waiting ? 0.8 : 1,
            paddingTop: spec.progress === "none" ? 0 : spec.gap * 0.35,
            // Grow after the collapse, for the same reason as UNFOLD.
            transition: { ...FOLD, delay: 0.1 },
          }}
          className="font-semibold leading-[1.25] tracking-[-0.015em] text-ink"
        >
          {instruction}
        </motion.h1>

        {/* What has been found so far, when the task was looking for
            something. Under the instruction and larger than it: the
            instruction says what is happening now, the finding is what the
            person actually asked for, and showing the answer as a step label
            buries it.

            Not at level 3: that level is one sentence and one thing to press,
            and a second block on it is the clutter the level exists to
            remove. The answer is still waiting on the closing screen. */}
        <Fold show={findings.length > 0 && spec.progress !== "none"} gap={spec.gap * 0.5}>
          <div className="flex flex-col gap-1 rounded-lg bg-tint px-5 py-4">
            <span className="text-caption font-medium text-soft">{FOUND.heading}</span>
            <motion.span
              animate={{ fontSize: `${foundSize(level, instruction)}px` }}
              transition={FOLD}
              className="font-semibold leading-[1.1] tracking-[-0.02em] text-ink"
            >
              {findings[0]?.value}
            </motion.span>
            <span className="text-caption text-soft">{findings[0]?.label}</span>
          </div>
        </Fold>

        <Fold show={spec.detail && Boolean(step.detail)} gap={spec.gap * 0.3}>
          <p className="text-small text-soft">{step.detail}</p>
        </Fold>

        <Fold show={fields.length > 0} gap={spec.gap}>
          <div className="flex flex-col gap-3">
            {fields.map((field) => (
              <Field
                key={field.id}
                field={field}
                value={values[field.id] ?? ""}
                onChange={onChange}
                spec={spec}
              />
            ))}
          </div>
        </Fold>

        <Fold show gap={spec.gap}>
          <motion.div
            transition={FOLD}
            className={spec.actionLayout === "row" ? "flex flex-row gap-3" : "flex flex-col gap-3"}
          >
            <ActionButton
              action={primary}
              height={spec.actionHeight}
              answered={answered}
              waiting={waiting}
              onAction={onAction}
              grow={spec.actionLayout === "row"}
            />

            {/* Level 3 demotes the second choice to plain text. The button
                collapsing into a line of text is the clearest single moment
                in the 2 -> 3 fold, so the two forms are separate presences
                rather than one element restyled. */}
            {secondary && spec.secondary === "button" && (
              <ActionButton
                action={secondary}
                height={spec.actionHeight}
                answered={answered}
                waiting={waiting}
                onAction={onAction}
                grow={spec.actionLayout === "row"}
                quiet
              />
            )}
          </motion.div>
        </Fold>

        <Fold show={Boolean(secondary) && spec.secondary === "text"} gap={spec.gap * 0.4}>
          <button
            type="button"
            disabled={answered}
            onClick={() => secondary && onAction(secondary.id)}
            className={`${buttonClass("quiet")} w-full justify-center disabled:opacity-40`}
          >
            {secondary?.label}
          </button>
        </Fold>
      </div>
    </div>
  );
}

/**
 * How big a finding is on the step card: larger than the instruction beside
 * it, and capped so a long answer cannot push the step off the screen.
 */
function foundSize(level: Level, instruction: string): number {
  return Math.min(44, Math.round(typeSize(level, instruction) * 1.2));
}

function Field({
  field,
  value,
  onChange,
  spec,
}: {
  field: StepField;
  value: string;
  onChange: (id: string, value: string) => void;
  spec: (typeof LEVELS)[Level];
}) {
  const input = (
    <motion.input
      animate={{
        height: spec.fieldHeight,
        fontSize: spec.fieldLayout === "inline" ? `${TYPE.small}px` : `${TYPE.body}px`,
      }}
      transition={FOLD}
      className="w-full rounded-md border border-line bg-sunk px-4 text-ink outline-none
                 transition-colors duration-200 focus:border-accent focus:bg-surface
                 focus-visible:outline-none"
      type={field.type === "password" ? "password" : "text"}
      value={value}
      onChange={(event) => onChange(field.id, event.target.value)}
      aria-label={field.label}
    />
  );

  if (spec.fieldLayout === "inline") {
    return (
      <motion.div transition={FOLD} className="grid grid-cols-[150px_1fr] items-center gap-3">
        <span className="text-caption font-medium text-soft">{field.label}</span>
        {input}
      </motion.div>
    );
  }

  return (
    <motion.label transition={FOLD} className="flex flex-col gap-2">
      <span className="text-small font-medium text-soft">{field.label}</span>
      {input}
    </motion.label>
  );
}

function ActionButton({
  action,
  height,
  answered,
  waiting,
  onAction,
  grow,
  quiet,
}: {
  action?: StepAction;
  height: number;
  answered: boolean;
  waiting: boolean;
  onAction: (id: string) => void;
  grow?: boolean;
  quiet?: boolean;
}) {
  if (!action) return null;

  const destructive = action.kind === "destructive";
  const tone = destructive ? "danger" : quiet ? "secondary" : "primary";

  return (
    <motion.button
      type="button"
      disabled={answered}
      onClick={() => onAction(action.id)}
      animate={{ height, opacity: answered ? 0.4 : waiting ? 1 : 0.85 }}
      transition={FOLD}
      className={`${grow ? "flex-1" : "w-full"} ${buttonClass(tone, "fluid")}`}
    >
      {action.label}
    </motion.button>
  );
}

/** Primary first, whatever order the backend sent them in. */
function orderActions(actions: StepAction[]): StepAction[] {
  const primary = actions.find((action) => action.kind === "primary");
  if (!primary) return actions;
  return [primary, ...actions.filter((action) => action !== primary)];
}
