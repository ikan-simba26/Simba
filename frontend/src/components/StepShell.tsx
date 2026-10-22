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
import { useEffect, useState, type ReactNode } from "react";

import type { Finding, Level, StepAction, StepField, StepPresented } from "@shared/schema";

import { CHOOSE, FOUND, SIGN_IN, STAGES } from "../copy";
import { NoticeLine, useNotice } from "./Notices";
import { SpeakButton } from "./Speak";
import { useStore } from "../store";
import { EASE, MOTION, TYPE } from "../design";
import { LEVELS, firstSentence, fitted, typeSize } from "../levels";
import { useShortWindow } from "../useShortWindow";
import type { StepRendererProps } from "./StepView";
import { CheckIcon, InfoIcon, StepKindIcon, buttonClass } from "./ui";

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

  // What was wrong with the last answer (`note`, 2026-10-14) stays beside the
  // question until a valid answer is chosen — a name from the site's own list
  // — and then goes: the person has put it right, and a sentence still saying
  // they had not would be wrong. A typed answer cannot be checked here, so its
  // note stays until it is sent and the backend has checked it.
  const chosenFromList = step.fields.some((field) =>
    (field.options ?? []).some((option) => plain(option) === plain(values[field.id] ?? "")));
  const note = step.note && !chosenFromList ? step.note : null;

  // Everything but the one way to stop is an answer, and every answer is a
  // button. Until 2026-09-30 exactly two were rendered — the first and one
  // more — which was enough while every step offered go-ahead and stop, and
  // silently dropped the rest once a question offered three answers: "Pick a
  // day" never appeared, and neither did the way to stop.
  // Saving the password, when the backend offers it, is a box to tick, not
  // a second button (2026-10-15): "Sign in" sends the offer's own id when it
  // is ticked, and its own when it is not. Unticked for every new step.
  const saveOffer = step.actions.find((action) => action.id === SAVE_ID);
  const [save, setSave] = useState(false);
  useEffect(() => setSave(false), [step.step_index]);
  const answers = step.actions.filter((action) => action.id !== SAVE_ID);
  const act = (id: string) =>
    onAction(saveOffer && save && id === lead?.id ? saveOffer.id : id);

  const [lead, ...alternatives] = orderActions(answers);
  const stop = step.actions.find((action) => action.kind === "secondary");
  const layout = answersLayout({ ...step, actions: answers });
  // A box the step asks the person to fill, still empty: the main button
  // waits for it (2026-10-15). Pressed on an empty box, "That's it" sent
  // nothing and the same question came back.
  // A box whose answers are the site's own list waits for one of them,
  // chosen or typed whole (2026-10-16): with "Lahor" typed and two Lahore
  // stations listed, "Use this station" did not say which it would use.
  const unanswered = step.fields.some((field) => {
    if (field.value) return false;
    const typed = (values[field.id] ?? "").trim();
    if (!typed) return true;
    const listed = field.options ?? [];
    return listed.length > 0 && !listed.some((option) => plain(option) === plain(typed));
  });

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
        {/* The card's first line: one thing at a time (2026-10-14). A notice
            if one is up, else where the person is — the stages, which level 3
            leaves out — and "Read this aloud" at the right end, which nothing
            is drawn over. */}
        <TopLine step={step} stages={spec.progress !== "none"}
                 full={spec.progress === "full"} answered={answered} />

        {/* No `layout` here. A layout animation projects the element's box
            with a transform, which fights an animation of fontSize — the
            heading rendered at roughly a third of its size at level 3. The
            container's `layout` handles the reflow; the heading only grows. */}
        {/* "It is your turn: the buttons lead and the rest recedes." The
            recede is kept and softened: at 0.55 the instruction measured
            3.8:1 on the light card, which fails for the one sentence the
            person most needs to read. At 0.8 it is 8.7:1. */}
        {/* What was wrong with the last answer, kindly, above the question. */}
        <Fold show={note !== null} gap={spec.progress === "none" ? 0 : spec.gap * 0.35}>
          <p className="flex items-start gap-3 rounded-lg bg-tint px-5 py-3 text-body text-ink
                        short:py-2" data-testid="note" role="status">
            <span className="mt-1 shrink-0 text-accent" aria-hidden><InfoIcon /></span>
            <span>{note ?? step.note}</span>
          </p>
        </Fold>

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
              // Always at full strength (2026-10-15). It was 0.8 while SIMBA
              // waited for the person — exactly when they have to read it.
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

        <Fold show={Boolean(saveOffer)} gap={spec.gap * 0.4}>
          <label className="flex cursor-pointer items-center gap-3 text-body text-ink"
                 data-testid="save-password">
            <input type="checkbox" className="h-6 w-6 shrink-0 accent-[var(--accent)]"
                   checked={save} disabled={answered}
                   onChange={(event) => setSave(event.target.checked)} />
            {SIGN_IN.save}
          </label>
        </Fold>

        <Fold show gap={spec.gap}>
          {/* A question's answers, laid out to fit (2026-10-14): a task's
              first question has to fit at level 2 without folding, and at
              150% the station question was 65px too tall. One answer and the
              way to stop sit side by side; two or three short answers share
              a row, with the way to stop under them. Ordinary steps keep
              the column. */}
          <motion.div transition={FOLD} className="flex flex-col gap-3">
            {layout === "pair" ? (
              <div className="flex flex-row gap-3">
                <ActionButton action={lead} height={spec.actionHeight} answered={answered}
                              waiting={waiting} onAction={act} grow
                              blocked={unanswered} />
                {stop && spec.secondary === "button" && (
                  <ActionButton action={stop} height={spec.actionHeight} answered={answered}
                                waiting={waiting} onAction={act} grow quiet />
                )}
                {/* Level 3: the way to stop as its line of text, still beside
                    the answer. Under it, level 3 was 18px taller than level 2
                    (frontend/test_levels.py), and simplifying must never make
                    a step taller. */}
                {stop && spec.secondary === "text" && (
                  <button type="button" disabled={answered}
                          onClick={() => act(stop.id)}
                          className={`${buttonClass("quiet")} shrink-0 px-6
                                      disabled:opacity-40`}>
                    {stop.label}
                  </button>
                )}
              </div>
            ) : (
              <>
                <div className={layout === "row" ? "flex flex-row gap-3" : "flex flex-col gap-3"}>
                  <ActionButton action={lead} height={spec.actionHeight} answered={answered}
                                waiting={waiting} onAction={act}
                                grow={layout === "row"} blocked={unanswered} />
                  {/* The other answers to a question. Buttons at every level,
                      including level 3: an answer that has been demoted to a
                      line of text is one the person cannot give. */}
                  {alternatives.map((action) => (
                    <ActionButton key={action.id} action={action} height={spec.actionHeight}
                                  answered={answered} waiting={waiting} onAction={act}
                                  grow={layout === "row"} quiet />
                  ))}
                </div>
                {/* Level 3 demotes the way to stop to plain text. The button
                    collapsing into a line of text is the clearest single moment
                    in the 2 -> 3 fold, so the two forms are separate presences
                    rather than one element restyled. */}
                {stop && spec.secondary === "button" && (
                  <ActionButton action={stop} height={spec.actionHeight} answered={answered}
                                waiting={waiting} onAction={act} quiet />
                )}
              </>
            )}
          </motion.div>
        </Fold>

        <Fold show={Boolean(stop) && spec.secondary === "text" && layout !== "pair"}
              gap={spec.gap * 0.4}>
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

/** The card's first line: a notice or the stages, and "Read this aloud". */
export function TopLine({ step, stages, full, answered }: {
  step: StepPresented | null; stages: boolean; full: boolean; answered: boolean;
}) {
  const notice = useNotice();
  // "Read this aloud" unless the person said, in the welcome, they did not
  // want it (2026-10-18). Speech is still only ever on a press.
  const readAloud = useStore((state) => state.profile.readAloud);
  // One thing on the left: a notice if one is up, else the stages.
  let left: React.ReactNode = null;
  if (notice) left = <NoticeLine />;
  else if (stages) left = <StageRow current={step?.stage} full={full} />;
  return (
    <div className="flex min-h-10 items-center justify-between gap-4" data-testid="top-line">
      <div className="min-w-0 flex-1">
        {left}
      </div>
      {readAloud && <SpeakButton step={step && !answered ? step : null} />}
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
                           : "text-soft"}>
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
      className="simba-field w-full rounded-md px-4"
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
 *  The same rule as `voice.station_name`. Not a code: `MATH-210` is written as
 *  the portal writes it, and "Math-210" is not a course (2026-10-16). */
export function readable(name: string): string {
  if (name !== name.toUpperCase() || !/[A-Z]/.test(name) || /\d/.test(name)) return name;
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
          className="simba-field w-full rounded-md px-4"
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
  blocked = false,
}: {
  action?: StepAction;
  height: number;
  answered: boolean;
  waiting: boolean;
  onAction: (id: string) => void;
  grow?: boolean;
  quiet?: boolean;
  /** Waiting for an answer in a box: not pressable yet. */
  blocked?: boolean;
}) {
  if (!action) return null;

  const destructive = action.kind === "destructive";
  const tone = destructive ? "danger" : quiet ? "secondary" : "primary";

  return (
    <motion.button
      type="button"
      disabled={answered || blocked}
      onClick={() => onAction(action.id)}
      animate={{ height, opacity: answered ? 0.4 : blocked ? 0.45 : waiting ? 1 : 0.85 }}
      transition={FOLD}
      className={`${grow ? "flex-1" : "w-full"} ${buttonClass(tone, "fluid")}`}
    >
      {action.label}
    </motion.button>
  );
}

/** The id of the backend's offer to keep a password (`voice.REMEMBER_ID`),
 *  shown as a box to tick rather than as a button. */
export const SAVE_ID = "remember";

/** No, to a yes-or-no question about one move (`voice.DECLINE_ID`): the move
 *  is left undone and the task goes on. An answer, not a way to stop. */
export const DECLINE_ID = "decline";

/** Answers this long or shorter share a row; longer ones keep the column. */
const SHORT_ANSWER = 22;

/**
 * How a step's answers are laid out. A question — its answers carry ids of
 * their own, or it has a box to type in — whose one answer finishes it
 * puts it beside the way to stop ("pair"); one with two or three short
 * answers puts them in a row ("row"). Everything else keeps the column. At
 * level 3, where the way to stop is a line of text, the layouts hold: a pair
 * keeps the text beside its answer, a row keeps its row with the text under
 * it. Falling back to the column there made level 3 up to 107px taller than
 * level 2, and simplifying must never make a step taller.
 */
function answersLayout(step: StepPresented): "pair" | "row" | "column" {
  const answers = step.actions.filter((action) => action.kind !== "secondary");
  const choices = answers.filter((action) => action.id.startsWith("choice:"));
  const typed = step.fields.some((field) => !field.value);
  if (typed && answers.length === 1) return "pair";
  // Two or three short choices share a row — and "No" beside them counts as
  // one (2026-10-16): "7UP, leaves 07:25", "8DN, leaves 16:35", "No, just
  // the times" stacked put the way to stop past a 606px window.
  const replies = answers.filter((action) => action.id.startsWith("choice:") ||
                                             action.id === DECLINE_ID);
  if (choices.length >= 1 && replies.length >= 2 && replies.length === answers.length &&
      answers.length <= 3 &&
      answers.every((action) => action.label.length <= SHORT_ANSWER)) return "row";
  // Yes and No about one move (2026-10-16): two answers side by side.
  if (answers.length === 2 && answers.some((action) => action.id === DECLINE_ID)) return "row";
  return "column";
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
