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

import { CHOOSE, FOUND, STAGES } from "../copy";
import { useStore } from "../store";
import { EASE, MOTION, TYPE } from "../design";
import { LEVELS, firstSentence, fitted, typeSize } from "../levels";
import { useShortWindow } from "../useShortWindow";
import type { StepRendererProps } from "./StepView";
import { CheckIcon, StepKindIcon, buttonClass } from "./ui";

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
  // The same regions at every height; a short window only packs them closer.
  const spec = fitted(LEVELS[level], useShortWindow());

  const instruction =
    spec.instruction === "first-sentence" ? firstSentence(step.instruction) : step.instruction;

  // "Required" is decided by what the backend sent, not by what has been
  // typed since. Until 2026-10-06 it read the typed value too, so at level 3
  // a box the person was answering a question in vanished at the first
  // keystroke, and took their answer with it.
  const fields =
    spec.fields === "required-only" ? step.fields.filter((field) => !field.value) : step.fields;

  const findings: Finding[] = step.findings ?? [];

  // Everything but the one way to stop is an answer, and every answer is a
  // button. Until 2026-09-30 exactly two were rendered — the first and one
  // more — which was enough while every step offered go-ahead and stop, and
  // silently dropped the rest once a question offered three answers: "Pick a
  // day" never appeared, and neither did the way to stop.
  const [lead, ...alternatives] = orderActions(step.actions);
  const stop = step.actions.find((action) => action.kind === "secondary");

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
        className="pointer-events-none absolute -inset-x-12 -inset-y-10 rounded-xl border
                   border-line short:-inset-y-7"
        animate={{ opacity: spec.shell === "card" ? 1 : 0 }}
        transition={FOLD}
      />

      <div className="relative flex flex-col">
        <Fold show={spec.progress !== "none"} gap={0}>
          {/* Where the person is, by name — never a count, which grew every
              time a question was asked again (2026-10-14). Level 1 states it;
              level 2 murmurs it; level 3, one sentence and one thing to
              press, has none. */}
          <StageRow current={step.stage} full={spec.progress === "full"} />
        </Fold>

        {/* No `layout` here. A layout animation projects the element's box
            with a transform, which fights an animation of fontSize — the
            heading rendered at roughly a third of its size at level 3. The
            container's `layout` handles the reflow; the heading only grows. */}
        {/* "It is your turn: the buttons lead and the rest recedes." The
            recede is kept and softened: at 0.55 the instruction measured
            3.8:1 on the light card, which fails for the one sentence the
            person most needs to read. At 0.8 it is 8.7:1. */}
        {/* What the step is about, as one plain shape beside its sentence
            (2026-10-07). Beside, not above: it costs width, not height, and
            height is what a 150% window runs out of. */}
        <div className="flex items-start gap-5 short:gap-4">
          {step.step_kind && (
            <motion.span
              aria-hidden
              data-testid="step-kind"
              data-kind={step.step_kind}
              animate={{ marginTop: spec.progress === "none" ? 0 : spec.gap * 0.35 }}
              transition={FOLD}
              className="flex h-16 w-16 shrink-0 items-center justify-center rounded-lg bg-tint
                         text-accent short:h-13 short:w-13"
            >
              <StepKindIcon kind={step.step_kind} />
            </motion.span>
          )}
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
            className="min-w-0 flex-1 font-semibold leading-[1.25] tracking-[-0.015em] text-ink"
          >
            {instruction}
          </motion.h1>
        </div>

        {/* What has been found so far, when the task was looking for
            something. Under the instruction and larger than it: the
            instruction says what is happening now, the finding is what the
            person actually asked for, and showing the answer as a step label
            buries it.

            Not at level 3: that level is one sentence and one thing to press,
            and a second block on it is the clutter the level exists to
            remove. The answer is still waiting on the closing screen. */}
        <Fold show={findings.length > 0 && spec.progress !== "none"} gap={spec.gap * 0.5}>
          <div className="flex flex-col gap-1 rounded-lg bg-tint px-6 py-5 short:py-3">
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
              action={lead}
              height={spec.actionHeight}
              answered={answered}
              waiting={waiting}
              onAction={onAction}
              grow={spec.actionLayout === "row"}
            />

            {/* The other answers to a question. Buttons at every level,
                including level 3: an answer that has been demoted to a line
                of text is one the person cannot give. */}
            {alternatives.map((action) => (
              <ActionButton
                key={action.id}
                action={action}
                height={spec.actionHeight}
                answered={answered}
                waiting={waiting}
                onAction={onAction}
                grow={spec.actionLayout === "row"}
                quiet
              />
            ))}

            {/* Level 3 demotes the way to stop to plain text. The button
                collapsing into a line of text is the clearest single moment
                in the 2 -> 3 fold, so the two forms are separate presences
                rather than one element restyled. */}
            {stop && spec.secondary === "button" && (
              <ActionButton
                action={stop}
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

        <Fold show={Boolean(stop) && spec.secondary === "text"} gap={spec.gap * 0.4}>
          <button
            type="button"
            disabled={answered}
            onClick={() => stop && onAction(stop.id)}
            className={`${buttonClass("quiet")} w-full justify-center disabled:opacity-40`}
          >
            {stop?.label}
          </button>
        </Fold>
      </div>
    </div>
  );
}

/**
 * The task's stages, in a row: those done ticked, the one the person is in
 * marked, those to come quiet. Fixed for the task, so it never grows.
 */
export function StageRow({ current, full }: { current?: number; full: boolean }) {
  const stages = useStore((state) => state.task?.stages) ?? [];
  const known = useStore((state) => state.stageNow);
  const at = current ?? known ?? 0;
  if (stages.length === 0) return null;
  return (
    <ol aria-label={STAGES.label} data-testid="stages"
        className={`flex flex-wrap items-center gap-x-2 gap-y-1 font-medium tracking-wide
                    ${full ? "text-caption" : "text-[16px]"}`}>
      {stages.map((name, index) => (
        <li key={name} className="flex items-center gap-2"
            aria-current={index === at ? "step" : undefined}
            data-state={index < at ? "done" : index === at ? "now" : "to come"}>
          {index > 0 && <span aria-hidden className="text-soft/50">·</span>}
          <span className={index === at ? "rounded-full bg-tint px-3 py-0.5 text-accent"
                           : index < at ? "text-soft" : "text-soft/70"}>
            {index < at && <span aria-hidden className="mr-1">✓</span>}
            {name}
          </span>
        </li>
      ))}
    </ol>
  );
}

/**
 * How big a finding is on the step card: larger than the instruction beside
 * it, and capped so a long answer cannot push the step off the screen.
 */
function foundSize(level: Level, instruction: string): number {
  return Math.min(TYPE.hero - 16, Math.round(typeSize(level, instruction) * 1.2));
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
  if (field.options?.length) {
    return <ChoiceField field={field} value={value} onChange={onChange} spec={spec} />;
  }

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
      <motion.div transition={FOLD} className="grid grid-cols-[210px_1fr] items-center gap-4">
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

/**
 * How many matches are shown at once: one row of two.
 *
 * Four, two to a row, until 2026-10-07: the row under the step card then fell
 * 52px below a 150% window as soon as anything matched, because the matches
 * arrive after the overflow guard has measured the step. Now the list has one
 * row of its own from the start — the hint before anything is typed, the
 * matches after — so the step is as tall when it arrives as it will ever be,
 * and the guard measures the real thing.
 */
const SHOWN_MATCHES = 2;

/** A name with case, dots and dashes taken out, as the backend compares them. */
function plain(text: string): string {
  return text.toLowerCase().replace(/[.\-'’]/g, " ").split(/\s+/).filter(Boolean).join(" ");
}

/** A name in capitals, as a person reads it: `LAHORE CANTT` as `Lahore Cantt`.
 *  The same rule as `voice.station_name`. */
export function readable(name: string): string {
  if (name !== name.toUpperCase() || !/[A-Z]/.test(name)) return name;
  return name.toLowerCase().replace(/(^|[^a-z])([a-z])/g, (_, before, letter) =>
    before + letter.toUpperCase());
}

/**
 * The options that match what has been typed, best first: the name itself,
 * then names that start with it, then names with a word that starts with each
 * typed word ("cantt" finds both Cantts), then names with it anywhere. Ties
 * keep the site's order.
 */
export function matching(options: string[], typed: string): string[] {
  const want = plain(typed);
  if (!want) return [];
  const words = want.split(" ");
  const rank = (option: string): number => {
    const name = plain(option);
    if (name === want) return 0;
    if (name.startsWith(want)) return 1;
    const own = name.split(" ");
    if (words.every((word) => own.some((w) => w.startsWith(word)))) return 2;
    return name.includes(want) ? 3 : 4;
  };
  return options
    .map((option, index) => ({ option, index, rank: rank(option) }))
    .filter((entry) => entry.rank < 4)
    .sort((a, b) => a.rank - b.rank || a.index - b.index)
    .map((entry) => entry.option);
}

/**
 * A question answered from a known list (2026-10-06): a box, and under it the
 * few names that match what has been typed, each a button. Pressing one puts
 * it in the box; the question's own button sends it. Nothing shows until
 * something is typed, so the screen never starts as a list to read.
 */
function ChoiceField({
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
  const options = field.options ?? [];
  const found = matching(options, value);
  const chosen = options.find((option) => plain(option) === plain(value));
  // More than fit: the first, and how many more in the second place.
  const crowded = !chosen && found.length > SHOWN_MATCHES;
  const shown = chosen ? [chosen] : found.slice(0, crowded ? SHOWN_MATCHES - 1 : SHOWN_MATCHES);
  const more = chosen ? 0 : found.length - shown.length;
  const typed = value.trim() !== "";
  const rowHeight = Math.round(spec.fieldHeight * 0.8);

  return (
    <div className="flex flex-col gap-3">
      {/* Beside its box at level 1, as every other field is there: above it,
          the label cost the one line that made a two-line station question
          scroll by 9px at 150% in the real window (2026-10-14). */}
      <motion.label transition={FOLD}
                    className={spec.fieldLayout === "inline"
                      ? "grid grid-cols-[210px_1fr] items-center gap-4"
                      : "flex flex-col gap-2"}>
        <span className={spec.fieldLayout === "inline"
          ? "text-caption font-medium text-soft" : "text-small font-medium text-soft"}>
          {field.label}
        </span>
        <motion.input
          animate={{ height: spec.fieldHeight, fontSize: `${TYPE.body}px` }}
          transition={FOLD}
          className="w-full rounded-md border border-line bg-sunk px-4 text-ink outline-none
                     transition-colors duration-200 placeholder:text-soft/70
                     focus:border-accent focus:bg-surface focus-visible:outline-none"
          type="text"
          value={value}
          autoComplete="off"
          onChange={(event) => onChange(field.id, event.target.value)}
          aria-label={field.label}
        />
      </motion.label>

      {/* One row, always there: the hint, then the matches. */}
      <motion.div role="group" aria-label={CHOOSE.matches}
                  className="grid grid-cols-2 items-center gap-2"
                  animate={{ minHeight: rowHeight }} transition={FOLD}>
        {!typed && <p className="col-span-2 text-small text-soft">{CHOOSE.hint}</p>}
        {shown.map((option) => (
          <motion.button
            key={option}
            type="button"
            aria-pressed={option === chosen}
            onClick={() => onChange(field.id, readable(option))}
            animate={{ height: rowHeight }}
            transition={FOLD}
            // Chosen, it is marked — a tick and the accent's edge — and not
            // filled: filled, it was a second solid button beside "That's
            // it", and two of those on one screen do not say which to press
            // (2026-10-14).
            className={`w-full ${buttonClass("secondary", "fluid")} ${
              option === chosen ? "border-2 border-accent bg-tint" : ""}`}
          >
            {option === chosen && <CheckIcon size={24} />}
            {readable(option)}
          </motion.button>
        ))}
        {more > 0 && <p className="text-small text-soft">{CHOOSE.more(more)}</p>}
        {typed && found.length === 0 && (
          <p className="col-span-2 text-small text-soft">{CHOOSE.none}</p>
        )}
      </motion.div>
    </div>
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

/**
 * Every answer a step offers, the prominent one first and the way to stop
 * left out — that has its own place below, because it is the one thing on a
 * step that is not an answer.
 */
function orderActions(actions: StepAction[]): StepAction[] {
  const answers = actions.filter((action) => action.kind !== "secondary");
  if (answers.length === 0) return actions;
  const primary = answers.find((action) => action.kind === "primary");
  if (!primary) return answers;
  return [primary, ...answers.filter((action) => action !== primary)];
}
