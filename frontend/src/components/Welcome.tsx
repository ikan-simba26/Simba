/**
 * Getting to know the person (2026-10-18): the first time SIMBA opens, four
 * short questions, one at a time — what to call them, which of three ways of
 * showing a question feels comfortable, whether to show the button that reads
 * things aloud, and whether to ask before each thing. Every one can be
 * skipped; skipping leaves what was there. "Change my settings" on the home
 * screen opens it again, with their answers already chosen.
 *
 * What they say is kept on this computer only (`profile.ts`). The name never
 * leaves the overlay; the level goes with each task as `start_level`.
 */

import { motion } from "framer-motion";
import { useLayoutEffect, useRef, useState } from "react";

import type { Level, StepPresented } from "@shared/schema";

import { TEACH, WELCOME } from "../copy";
import { ARRIVE } from "../design";
import { NAME_MAX, cleanName } from "../profile";
import { useStore } from "../store";
import { StepShell } from "./StepShell";
import { Button } from "./ui";

const QUESTIONS = ["name", "level", "read", "ask"] as const;
type Question = (typeof QUESTIONS)[number];

/** The question every example shows: one a journey asks. */
const SAMPLE: StepPresented = {
  step_index: 1,
  step_total: 3,
  instruction: WELCOME.sample.instruction,
  detail: WELCOME.sample.detail,
  fields: [],
  actions: [
    ...WELCOME.sample.answers.map((label, index) => (
      { id: `choice:${index}`, label, kind: "primary" as const })),
    { id: "cancel", label: WELCOME.sample.stop, kind: "secondary" as const },
  ],
  requires_confirmation: true,
  findings: [],
  step_kind: "date",
};

/** The width the examples are laid out at, then drawn smaller to fit their
 *  cards. Narrower than the real column (880): at its width, a card a third
  of the window drew the question at 0.3 of its size, too small to read; at
 *  600 the third answer was cut off at its right edge. */
const EXAMPLE_WIDTH = 700;

export function Welcome() {
  const { profile, updateProfile, finishWelcome, forgetEverything, setTeachOpen } = useStore();
  const [at, setAt] = useState(0);
  // Opened again from "Change my settings", rather than a first open: only
  // then is there anything to forget (2026-10-18).
  const [reopened, setReopened] = useState(profile.welcomed);
  const [forgetting, setForgetting] = useState(false);
  // A new round after forgetting: every question starts empty again.
  const [round, setRound] = useState(0);
  const question: Question = QUESTIONS[at];
  const next = () => (at + 1 < QUESTIONS.length ? setAt(at + 1) : finishWelcome());

  if (forgetting) {
    return (
      <div className="flex min-h-[calc(100dvh-176px)] flex-col justify-center gap-7
                      short:min-h-[calc(100dvh-92px)] short:gap-4" data-testid="welcome"
           data-question="forget">
        <Heading ask={WELCOME.forgetAsk} detail={WELCOME.forgetDetail} />
        <div className="grid grid-cols-2 gap-4 short:gap-3">
          <Button variant="secondary" data-testid="forget-yes" onClick={() => {
            forgetEverything();
            setForgetting(false);
            setReopened(false);
            setAt(0);
            setRound(round + 1);
          }}>
            {WELCOME.forgetYes}
          </Button>
          <Button data-testid="forget-no" onClick={() => setForgetting(false)}>
            {WELCOME.forgetNo}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-[calc(100dvh-176px)] flex-col justify-center gap-7
                    short:min-h-[calc(100dvh-92px)] short:gap-4" data-testid="welcome"
         data-question={question}>
      <motion.div key={`${question}-${round}`} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
                  transition={ARRIVE} className="flex flex-col gap-7 short:gap-4">
        <p className="text-small font-medium text-soft">{WELCOME.lead}</p>
        {question === "name" && <NameQuestion name={profile.name ?? ""} onDone={(name) => {
          updateProfile({ name: cleanName(name) || undefined });
          next();
        }} onSkip={next} onForget={reopened ? () => setForgetting(true) : undefined}
           onTeach={reopened ? () => setTeachOpen(true) : undefined} />}
        {question === "level" && <LevelQuestion chosen={profile.level} onPick={(level) => {
          updateProfile({ level });
          next();
        }} onSkip={next} />}
        {question === "read" && (
          <Choice ask={WELCOME.readAsk} detail={WELCOME.readDetail}
                  answers={[{ label: WELCOME.readYes, chosen: profile.readAloud,
                              pick: () => updateProfile({ readAloud: true }) },
                            { label: WELCOME.readNo, chosen: !profile.readAloud,
                              pick: () => updateProfile({ readAloud: false }) }]}
                  onAnswer={next} onSkip={next} />
        )}
        {question === "ask" && (
          <Choice ask={WELCOME.askAsk} detail={WELCOME.askDetail}
                  answers={[{ label: WELCOME.askEach, chosen: profile.askEach,
                              pick: () => updateProfile({ askEach: true }) },
                            { label: WELCOME.justDo, chosen: !profile.askEach,
                              pick: () => updateProfile({ askEach: false }) }]}
                  onAnswer={next} onSkip={next} />
        )}
      </motion.div>
    </div>
  );
}

function Heading({ ask, detail }: { ask: string; detail: string }) {
  return (
    <div className="flex flex-col gap-3 short:gap-2">
      <h1 className="text-display font-semibold tracking-[-0.015em] text-ink short:text-heading">
        {ask}
      </h1>
      <p className="text-lead text-soft short:text-body">{detail}</p>
    </div>
  );
}

/** Skip, quietly, on the left; the way on, on the right. */
function Footer({ onSkip, children }: { onSkip: () => void; children?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <Button variant="quiet" size="md" wide={false} onClick={onSkip}
              data-testid="welcome-skip">
        {WELCOME.skip}
      </Button>
      {children}
    </div>
  );
}

function NameQuestion({ name, onDone, onSkip, onForget, onTeach }: {
  name: string; onDone: (name: string) => void; onSkip: () => void; onForget?: () => void;
  /** "Show me once", for a helper (2026-11-04): in the settings only. */
  onTeach?: () => void;
}) {
  const [typed, setTyped] = useState(name);
  return (
    <>
      <Heading ask={WELCOME.nameAsk} detail={WELCOME.nameDetail} />
      <input autoFocus value={typed} maxLength={NAME_MAX}
             onChange={(event) => setTyped(event.target.value)}
             onKeyDown={(event) => event.key === "Enter" && cleanName(typed) && onDone(typed)}
             placeholder={WELCOME.namePlaceholder} aria-label={WELCOME.nameAsk}
             className="simba-field-frame rounded-xl px-6 py-4 text-lead text-ink shadow-card
                        outline-none placeholder:text-soft short:py-3" />
      <Footer onSkip={onSkip}>
        <div className="flex items-center gap-4">
          {onTeach && (
            <Button variant="quiet" size="md" wide={false} onClick={onTeach}
                    data-testid="show-me-once">
              {TEACH.open}
            </Button>
          )}
          {onForget && (
            <Button variant="quiet" size="md" wide={false} onClick={onForget}
                    data-testid="forget">
              {WELCOME.forget}
            </Button>
          )}
          <Button size="md" wide={false} disabled={!cleanName(typed)}
                  onClick={() => onDone(typed)}>
            {WELCOME.next}
          </Button>
        </div>
      </Footer>
    </>
  );
}

/** Two answers as two large buttons; the one chosen before is marked. */
function Choice({ ask, detail, answers, onAnswer, onSkip }: {
  ask: string; detail: string;
  answers: { label: string; chosen: boolean; pick: () => void }[];
  onAnswer: () => void; onSkip: () => void;
}) {
  return (
    <>
      <Heading ask={ask} detail={detail} />
      <div className="grid grid-cols-2 gap-4 short:gap-3">
        {answers.map(({ label, chosen, pick }) => (
          <Button key={label} variant={chosen ? "primary" : "secondary"}
                  aria-pressed={chosen} onClick={() => { pick(); onAnswer(); }}>
            {label}
          </Button>
        ))}
      </div>
      <Footer onSkip={onSkip} />
    </>
  );
}

/**
 * The same question at levels 1, 2 and 3, side by side, each drawn small
 * enough that all three fit at 150%. The real step, not a picture of one: what
 * the person picks is exactly what they will see.
 */
function LevelQuestion({ chosen, onPick, onSkip }: {
  chosen?: Level; onPick: (level: Level) => void; onSkip: () => void;
}) {
  return (
    <>
      <Heading ask={WELCOME.levelAsk} detail={WELCOME.levelDetail} />
      <div className="grid grid-cols-3 gap-4 short:gap-3">
        {([1, 2, 3] as Level[]).map((level) => (
          <button key={level} type="button" onClick={() => onPick(level)}
                  aria-pressed={chosen === level} data-testid="welcome-level"
                  data-level={level}
                  className={`flex min-w-0 flex-col gap-3 rounded-xl border bg-surface p-3 text-left
                              shadow-card transition-[box-shadow,border-color] duration-200
                              hover:border-accent/50 hover:shadow-lift active:translate-y-px
                              short:gap-2 short:p-2 ${chosen === level
                                ? "border-accent" : "border-edge"}`}>
            <Example level={level} />
            <span className="mt-auto px-2 text-body font-semibold text-ink">
              {WELCOME.levelName(level)}
            </span>
          </button>
        ))}
      </div>
      <Footer onSkip={onSkip} />
    </>
  );
}

/** One example: the step laid out at a fixed width, drawn to the card's. */
function Example({ level }: { level: Level }) {
  const frame = useRef<HTMLDivElement>(null);
  const inner = useRef<HTMLDivElement>(null);
  const [drawn, setDrawn] = useState({ scale: 0.45, height: 180 });
  useLayoutEffect(() => {
    const element = frame.current;
    const example = inner.current;
    if (!element || !example) return;
    // An example takes no presses and no focus: it is only to look at.
    element.setAttribute("inert", "");
    // As large as the card's width allows, but never taller than the frame
    // may be (less in a short window), and no taller than it is drawn.
    const measure = () => {
      const tallest = parseFloat(getComputedStyle(element).maxHeight) || 240;
      const scale = Math.min(element.clientWidth / EXAMPLE_WIDTH,
                             tallest / example.offsetHeight);
      setDrawn({ scale, height: Math.ceil(example.offsetHeight * scale) });
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    observer.observe(example);
    return () => observer.disconnect();
  }, []);
  return (
    // The frame takes the card's width; the example is laid out inside it,
    // out of the flow, so its own width cannot widen the frame. Until
    // 2026-10-18 it was in the flow: the frame grew to the example's width,
    // measured itself at more than the example, and drew it larger than life
    // across its neighbours — seen in the real window.
    <div ref={frame} aria-hidden data-testid="welcome-example"
         style={{ height: drawn.height }}
         className="pointer-events-none relative max-h-60 w-full min-w-0 overflow-hidden
                    rounded-lg bg-canvas short:max-h-36">
      <div ref={inner} className="absolute top-0 left-0"
           style={{ width: EXAMPLE_WIDTH, transform: `scale(${drawn.scale})`,
                    transformOrigin: "top left", padding: "40px 48px" }}>
        <StepShell step={SAMPLE} values={{}} onChange={() => undefined}
                   onAction={() => undefined} waiting answered={false} level={level} />
      </div>
    </div>
  );
}
