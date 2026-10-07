/**
 * The overlay. This is what the person actually sees.
 *
 * One column, one thing at a time, nothing in the corners. The assistant's
 * presence sits above the column in the same place on every screen; the
 * screen below it changes. Everything the developer might want — the log,
 * the connection, the raw messages — lives behind Ctrl+Shift+D.
 *
 * All three levels, with the change between them animated as a fold rather
 * than a swap — see `StepShell`. Every size, colour and duration comes from
 * the tokens in `index.css` and `design.ts`.
 */

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { Backdrop, PeekBack, PeekButton } from "./components/Backdrop";
import { Shape } from "./components/Shape";
import { DebugPanel, useDebugShortcut } from "./components/Debug";
import { LevelControl, LevelNotice } from "./components/LevelControl";
import { TrustControl, TrustPanel } from "./components/TrustPanel";
import { StuckNote, isWaiting } from "./components/StateSignal";
import { StepFailureNotice } from "./components/StepNotice";
import {
  AgainIcon,
  Button,
  Card,
  CheckIcon,
  ChoiceCard,
  FlowIcon,
  PauseIcon,
  Presence,
  SpeechIcon,
  type PresenceMode,
} from "./components/ui";
import { ENDING, FLOWS, HOME, REPLY, STOPPED, WHICH, presence } from "./copy";
import { ARRIVE, COLUMN, TYPE } from "./design";
import { StepView } from "./components/StepView";
import type { Finding, FlowName, PastGoal } from "@shared/schema";

import { useStore } from "./store";
import { useOverflowGuard } from "./useOverflowGuard";

const ALL_FLOWS: FlowName[] = ["registration", "billing", "railways"];

/**
 * The most cards the home screen shows, remembered goals and the things SIMBA
 * can do together. Until 2026-09-30 it was three of each: six cards, and at
 * 150% the text box below them fell off the bottom of the window.
 */
export const HOME_CARDS = 3;

/** One card on the home screen, and what pressing it asks for. */
export interface HomeCard {
  goal: string;
  /** Sent with the goal when the card is one of the things SIMBA can do, so
   *  the backend runs exactly that and does not guess from the words. */
  flow?: FlowName;
  /** Asked for before, which the card's icon says. */
  remembered: boolean;
}

/** Two goals are the same card if they differ only in case, spacing or a
 *  closing full stop — "Check my electricity bill." is the bill card. */
function sameGoal(a: string, b: string): boolean {
  const plain = (text: string) =>
    text.trim().replace(/\s+/g, " ").replace(/[.!?]+$/, "").toLowerCase();
  return plain(a) === plain(b);
}

/**
 * The home screen's one list: what this person asked for before, most recent
 * first, then the things SIMBA can do, with nothing twice and never more than
 * `HOME_CARDS`. A remembered goal that is one of the things SIMBA can do stays
 * in its remembered place and keeps that flow, so pressing it runs exactly
 * what the card always ran.
 */
export function homeCards(history: PastGoal[]): HomeCard[] {
  const cards: HomeCard[] = [];
  const add = (card: HomeCard) => {
    if (cards.length < HOME_CARDS && !cards.some((c) => sameGoal(c.goal, card.goal))) {
      cards.push(card);
    }
  };
  for (const past of history) {
    const flow = ALL_FLOWS.find((name) => sameGoal(FLOWS[name], past.goal));
    add(flow ? { goal: FLOWS[flow], flow, remembered: true }
             : { goal: past.goal, remembered: true });
  }
  for (const flow of ALL_FLOWS) add({ goal: FLOWS[flow], flow, remembered: false });
  return cards;
}

export default function App() {
  const connect = useStore((state) => state.connect);
  const watchTelemetry = useStore((state) => state.watchTelemetry);
  useDebugShortcut();

  useEffect(() => {
    connect();
  }, [connect]);

  // Channel B, for as long as the window is up: the pointer is watched and a
  // sample goes out on a timer while a step waits (`telemetry.ts`).
  useEffect(() => watchTelemetry(), [watchTelemetry]);

  return (
    // The bottom padding is the one space on every screen nothing reads:
    // 32px, and 4px in a short window, since the step row and the real page's
    // button (2026-10-07) took the last few pixels at 100% and 150%.
    <div className="flex min-h-full flex-col items-center bg-canvas px-8 pt-6 pb-8
                    short:pt-3 short:pb-1">
      {/* The real page, softened, behind everything else (`Backdrop`). */}
      <Backdrop />
      <PresenceBar />
      {/* Most of the window, not a third of it: 880 of 1280. The first
          column was 680, which at this type size left the person reading
          a narrow strip down the middle of an empty screen. */}
      {/* `relative`: the level notice floats over the card's top edge,
          positioned against this column (`FLOATING_NOTICE_CLASS`). */}
      <div className="relative z-[1] mt-6 w-full short:mt-3" style={{ maxWidth: COLUMN }}>
        <LevelNotice />
        <StepFailureNotice />
        <Column />
      </div>
      <PeekBack />
      <TrustPanel />
      <DebugPanel />
    </div>
  );
}

/** Which of the presence mark's six shapes the current screen means. */
function usePresenceMode(): PresenceMode {
  const { state, step, help, completed, failed, stoppedByPerson, task, asking } = useStore();
  if (stoppedByPerson) return "ready";
  if (help || failed || state === "stuck") return "stuck";
  if (completed) return "done";
  if (state === "acting") return "acting";
  if (step && isWaiting(state)) return "waiting";
  if (task || asking) return "thinking";
  return "ready";
}

function PresenceBar() {
  const { trustOpen, peeking } = useStore();
  const mode = usePresenceMode();
  return (
    // Above the real page behind it (`Backdrop`), and out of the way while
    // that page is being shown.
    <motion.div className="relative z-[1]" animate={{ opacity: trustOpen || peeking ? 0 : 1 }}
                transition={ARRIVE}>
      <Presence mode={mode} />
    </motion.div>
  );
}

function Column() {
  const { step, help, completed, failed, stoppedByPerson, task, trustOpen, peeking, reply, state,
          asking } = useStore();
  // Put aside while the real page is shown: the trust panel's picture, or
  // the page itself behind the step (`Backdrop`).
  const aside = trustOpen || peeking;

  const stuck = state === "stuck" || Boolean(help);

  // One screen at a time, and only one. The key drives the crossfade.
  //
  // The person's own stop comes first: once they have pressed it, the
  // backend's `task.failed` that follows is the stop being carried out, not a
  // failure to show them.
  const screen = stoppedByPerson
    ? "stopped"
    : stuck
    ? "stuck"
    : completed
      ? "completed"
      : failed
        ? "failed"
        : step
          ? `step-${step.step_index}`
          : task || asking
            ? "working"
            : reply
              ? `reply-${reply.kind}`
              : "idle";

  return (
    <motion.div
      // Out of the way while the real page is being shown.
      animate={{ y: aside ? -28 : 0, opacity: aside ? 0 : 1 }}
      transition={{ duration: 0.42, ease: [0.4, 0, 0.2, 1] }}
      style={{ pointerEvents: aside ? "none" : "auto" }}
    >
      {/* Both screens share one grid cell, so the outgoing and incoming ones
          overlap during the crossfade instead of stacking and shoving the
          column down. `mode="wait"` would avoid the overlap by serialising
          them, but it strands the transition here: the exiting child stays
          mounted at opacity 0 and the next one never arrives, leaving the
          column blank. */}
      <div className="grid">
        <AnimatePresence initial={false}>
          <motion.div
            key={screen}
            /* No `layout` on this element: reflow is done with `layout` on
               the blocks inside a step instead. */
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={ARRIVE}
            className="[grid-area:1/1]"
          >
            {screen === "idle" && <Home />}
            {screen.startsWith("reply-") && <Reply />}
            {screen === "working" && <Working />}
            {screen.startsWith("step-") && <Step />}
            {screen === "completed" && <Completed />}
            {screen === "failed" && <Failed />}
            {screen === "stopped" && <StoppedByPerson />}
            {screen === "stuck" && <Stuck />}
          </motion.div>
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

/* ----------------------------------------------------------------- home */

/**
 * The first screen: a greeting, the three things SIMBA can do, and a place
 * to ask for something in your own words.
 *
 * The cards come first because choosing is easier than composing. Each is an
 * icon and one line, and the line is exactly what gets asked for.
 */
function Home() {
  const { startTask, history } = useStore();
  // The box is always there, below the cards (2026-09-21). It used to be
  // revealed behind "Ask for something new" whenever there was history, on
  // the reasoning that an empty field is the hardest thing on the screen and
  // should not be the first. The cards now come first and carry that job;
  // hiding the box as well made asking in your own words look like a
  // secondary route, and it could hide itself mid-sentence when history
  // arrived late.
  // One list, remembered goals first, never more than three cards: a second
  // list of up to three more is what pushed the box off a 150% screen.
  const cards = homeCards(history);

  return (
    // 32px between the greeting, the cards and the box, not 40: three
    // remembered goals of two lines each need the room at 100%.
    <div className="flex flex-col gap-8 short:gap-6">
      {/* A step down in a short window: 48px to 38px. The greeting is the
          one line on this screen nobody needs to read twice. */}
      {/* The shape beside the greeting, no taller than its line, so the
          home screen is no taller for it. */}
      <div className="flex items-center justify-between gap-6">
        <h1 className="text-display font-semibold tracking-[-0.015em] text-ink
                       short:text-heading">
          {HOME.greeting}
        </h1>
        <Shape className="h-14 w-14 short:h-11 short:w-11" />
      </div>

      <Section lead={HOME.canHelp}>
        {cards.map((card) => (
          <ChoiceCard key={card.goal}
                      icon={card.remembered || !card.flow ? <AgainIcon />
                            : <FlowIcon flow={card.flow} />}
                      onClick={() => startTask(card.goal, card.flow)}>
            {card.goal}
          </ChoiceCard>
        ))}
      </Section>

      {/* In a short window the box's lead-in goes: the greeting above has
          just asked the same question, and three remembered goals of two
          lines each need the room at 150%. The box keeps it as its name. */}
      <AskBox lead={HOME.askHeading} leadWhenShort={false} />
    </div>
  );
}

/** A lead-in and what it introduces. */
function Section({ lead, children }: { lead: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3 short:gap-2">
      <p className="text-small font-medium text-soft">{lead}</p>
      <div className="flex flex-col gap-3 short:gap-2">{children}</div>
    </section>
  );
}

/**
 * The place to ask in your own words. A soft card with the question inside
 * it rather than a bare form field: it should look like somewhere to talk,
 * not a box to fill in.
 */
function AskBox({ lead, autoFocus, leadWhenShort = true }:
                { lead?: string; autoFocus?: boolean; leadWhenShort?: boolean }) {
  const { startTask } = useStore();
  const [goal, setGoal] = useState("");
  const start = () => {
    if (goal.trim()) startTask(goal.trim());
  };

  return (
    <div className="flex flex-col gap-3 short:gap-2">
      {lead && (
        <p className={`text-small font-medium text-soft${leadWhenShort ? "" : " short:hidden"}`}>
          {lead}
        </p>
      )}
      <div
        className="flex items-center gap-4 rounded-xl border-2 border-line bg-surface py-2.5
                   pr-2.5 pl-6 shadow-card transition-[border-color,box-shadow] duration-200
                   focus-within:border-accent"
      >
        <span className="shrink-0 text-soft" aria-hidden>
          <SpeechIcon />
        </span>
        <input
          autoFocus={autoFocus}
          className="min-w-0 flex-1 bg-transparent py-4 text-lead text-ink outline-none short:py-3
                     placeholder:text-soft/80 focus-visible:outline-none"
          value={goal}
          onChange={(event) => setGoal(event.target.value)}
          onKeyDown={(event) => event.key === "Enter" && start()}
          placeholder={HOME.placeholder}
          aria-label={HOME.askHeading}
        />
        <Button size="md" wide={false} onClick={start} disabled={!goal.trim()}>
          {HOME.start}
        </Button>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- reply */

/**
 * A goal that started nothing: hello, something SIMBA cannot do, or a
 * question about which of two things was meant.
 *
 * Never a dead end. A greeting and a refusal both show what can be done, as
 * the same cards as the home screen, and the box is there to ask again. A
 * question shows its choices as the same cards, and each one sends the
 * person's own words back with the flow they picked, so what runs is what
 * they typed.
 */
function Reply() {
  const { reply, startTask } = useStore();
  if (!reply) return null;

  const heading =
    reply.kind === "greeting" ? REPLY.greeting
    : reply.kind === "unsupported" ? REPLY.unsupported
    : REPLY.clarify;

  return (
    <div className="flex flex-col gap-10 short:gap-6">
      <div className="flex flex-col gap-5 short:gap-3">
        <h1 className="text-display font-semibold tracking-[-0.015em] text-ink short:text-heading">
          {heading}
        </h1>
        {reply.kind !== "greeting" && reply.goal && (
          <div className="flex flex-col gap-1 border-l-4 border-tint pl-4">
            <p className="text-small font-medium text-soft">{REPLY.youAsked}</p>
            <p className="text-lead text-ink">{reply.goal}</p>
          </div>
        )}
      </div>

      {reply.kind === "clarify" ? (
        <div className="flex flex-col gap-3">
          {reply.flows.map((flow) => (
            <ChoiceCard key={flow} icon={<FlowIcon flow={flow} />}
                        onClick={() => startTask(reply.goal, flow)}>
              {WHICH[flow]}
            </ChoiceCard>
          ))}
        </div>
      ) : reply.kind === "unsupported" ? (
        <Section lead={REPLY.canDo}>
          {reply.flows.map((flow) => (
            <ChoiceCard key={flow} icon={<FlowIcon flow={flow} />}
                        onClick={() => startTask(FLOWS[flow], flow)}>
              {FLOWS[flow]}
            </ChoiceCard>
          ))}
        </Section>
      ) : (
        // The greeting's heading already says "Here's what I can help with";
        // a lead above the cards saying it again is the same sentence twice.
        <div className="flex flex-col gap-3">
          {reply.flows.map((flow) => (
            <ChoiceCard key={flow} icon={<FlowIcon flow={flow} />}
                        onClick={() => startTask(FLOWS[flow], flow)}>
              {FLOWS[flow]}
            </ChoiceCard>
          ))}
        </div>
      )}

      <AskBox lead={HOME.askHeading} />
    </div>
  );
}

/* -------------------------------------------------------------- working */

/**
 * Between task.started and the first step, and between steps.
 *
 * Says what is happening in the same plain voice as everything else, rather
 * than leaving an unlabelled pulse to be interpreted. The sentence comes from
 * `copy.ts` and is the same one every time this situation occurs. The
 * presence mark above breathes; the words do not.
 */
function Working() {
  const { task, asking } = useStore();
  // Thinking and acting are one situation from the person's side — wait —
  // and share a sentence. The presence mark tells them apart. Before a task
  // exists, the backend is still working out what was asked for.
  const situation = task ? "working" : asking ? "reading" : "opening";
  const goal = task?.goal ?? asking;
  return (
    <div className="flex flex-col items-center gap-5 pt-6 text-center">
      {/* In the room the screen kept empty above the sentence. */}
      <Shape className="mb-4 h-22 w-22" />
      <h1 className="text-display font-semibold tracking-[-0.015em] text-ink">
        {presence(situation)}
      </h1>
      {goal && <p className="max-w-[700px] text-lead text-soft">{goal}</p>}
    </div>
  );
}

/* ----------------------------------------------------------------- step */

function Step() {
  const { step, state, level, respond, answered } = useStore();
  const [values, setValues] = useState<Record<string, string>>({});
  const measured = useRef<HTMLDivElement>(null);

  // The step on its way out, kept on screen while it fades.
  //
  // Every ending clears `step` in the same update that changes the screen, so
  // this component is still mounted — inside the exiting half of the
  // crossfade — when `step` becomes null. It used to return null at that
  // point. The exiting element then emptied mid-exit, Framer never finished
  // removing it, and it stayed in the column's grid cell at opacity 0 on top
  // of the ending, swallowing every click. Measured on 2026-09-17: after any
  // step, "I'm done", "Do something else" and every other ending's button
  // could not be pressed, and had not been since at least `cc4704f`. Keeping
  // the last step rendered lets the exit run to completion.
  const leaving = useRef(step);
  if (step) leaving.current = step;
  const shown = step ?? leaving.current;

  useEffect(() => {
    if (!step) return;
    const initial: Record<string, string> = {};
    for (const field of step.fields) initial[field.id] = field.value;
    setValues(initial);
  }, [step]);

  // A step that will not fit drops a level instead of growing a scrollbar.
  useOverflowGuard(measured, { level, active: Boolean(step) });

  if (!shown) return null;

  return (
    <div ref={measured}>
      <Card className="px-12 py-10 short:py-7">
        <StepView
          level={level}
          step={shown}
          values={values}
          waiting={isWaiting(state)}
          // A step that is leaving can no longer be answered.
          answered={answered || !step}
          onChange={(fieldId, value) =>
            setValues((current) => ({ ...current, [fieldId]: value }))
          }
          onAction={(actionId) => respond(actionId, values)}
        />
      </Card>
      {/* The level dots and "What are you doing?" share one row under the
          card: at this type size, stacked, they pushed a step with a field
          past the bottom of the window. */}
      <div className="mt-8 flex flex-wrap items-center justify-between gap-4 short:mt-4">
        <div className="flex flex-wrap items-center gap-3">
          <TrustControl />
          <PeekButton />
        </div>
        <LevelControl />
      </div>
    </div>
  );
}

/* --------------------------------------------------------------- endings */

/**
 * The closing screen: the answer, then a way out.
 *
 * It used to say "Done." and the goal and the URL, which tells somebody who
 * asked what their bill was precisely nothing. A task that looked something
 * up ends with what it found, as the hero of the screen, because that is the
 * thing the person came for. A task that changed something instead says so
 * plainly, and restates what was asked for.
 *
 * What was asked for, not `task.completed.summary`. The backend builds the
 * summary as the goal followed by the final URL, which the tests and the logs
 * read to see where a run ended — and which put an address like
 * `http://127.0.0.1:5000/register` on this screen in 26px type.
 *
 * Two actions, always in the same order and the same place: finish, or ask
 * for something else. Both currently lead to the home screen; see STATUS.md.
 */
function Completed() {
  const { completed, task, startOver } = useStore();
  const findings = completed?.findings ?? [];
  // One plain sentence saying what the result means, written by the backend
  // from the page's own values (`voice.explain_*`). This screen writes none of
  // its own: there is nothing in `copy.ts` for it because every word of it is
  // the page's or `voice.py`'s, and `test_copy.py` holds those to the same
  // rules. Absent, the lead-in "Here's what I found" is there instead.
  const explanation = completed?.explanation ?? null;
  const said = useRef<HTMLParagraphElement>(null);
  const lines = useLines(said);

  return (
    <div className="flex flex-col gap-8 short:gap-5">
      {findings.length > 0 ? (
        <Card className="px-12 py-12 short:py-8">
          {/* The sentence, when there is one, in the lead-in's place: it
              says what the lead-in says and more, and both together were the
              line that kept nine results off a 606px window (2026-10-05). */}
          {explanation ? (
            <p ref={said}
               className="mb-6 text-lead font-medium text-ink short:mb-4 short:text-body"
               data-testid="explanation">
              {explanation}
            </p>
          ) : (
            <p className="mb-6 text-small font-medium text-soft short:mb-4">{ENDING.withAnswer}</p>
          )}
          <Findings findings={findings} size={TYPE.hero} less={Math.max(0, lines - 1)} />
        </Card>
      ) : (
        <div className="flex flex-col items-start gap-5">
          <span className="flex h-16 w-16 items-center justify-center rounded-full bg-tint
                           text-accent" aria-hidden>
            <CheckIcon size={34} />
          </span>
          <h1 className="text-display font-semibold tracking-[-0.015em] text-ink">
            {ENDING.withoutAnswer}
          </h1>
          {/* What happened, when the page said; otherwise what was asked for. */}
          <p className="text-lead text-soft" data-testid={explanation ? "explanation" : undefined}>
            {explanation ?? task?.goal}
          </p>
        </div>
      )}

      {/* Side by side, in the same order, finish first. Stacked, the pair is
          140px at 150% and 172px at 100%: at 150% that is what put six results
          and both buttons out of reach of a 606px window, and at 100% it left
          nine results 0px from a scrollbar (2026-10-05). */}
      <div className="flex flex-row gap-3">
        <Button className="flex-1" onClick={startOver}>{ENDING.finish}</Button>
        <Button className="flex-1" variant="secondary" onClick={startOver}>
          {ENDING.again}
        </Button>
      </div>
    </div>
  );
}

/**
 * What was found, largest thing on the screen.
 *
 * The value leads and the label follows underneath, small — the number is
 * what was asked for, and "Your bill" is only there to say what the number
 * is. The other way round makes the reader find the answer inside a sentence.
 *
 * One value keeps the full size, because one value is the billing case and it
 * should look exactly as it did: the answer, then what supports it, each with
 * its label underneath.
 *
 * Several results are a list, and each result is one line with its detail
 * beside it — "13UP, 6 h 6 min" — under one label line naming both. Until
 * 2026-10-05 every value had a line of its own, finding after finding, so
 * three trains and their journey times were six lines and the way onward was
 * below the window at every scale; nine were eighteen. `value` — the one line
 * the step screen shows — is not used for the list, because it stops at four.
 * `values` is the whole list; a message from before it existed has none, and
 * then the line is the answer.
 *
 * The results are read whole from `rows` when the backend sends them
 * (2026-10-05): each row is one result's cells, kept together from the page's
 * own table row, repeats included, so each train has its own time and nothing
 * here pairs anything. Without rows — a message from before them, or values
 * that did not come from a table — the lists in `values` are the only source,
 * and they drop a repeated value: two trains with one journey time give two
 * trains and one time. Then a finding is put beside the answer only when it
 * has exactly as many values, and even that is not proof (a repeat dropped
 * from each list on different rows leaves two lists of one length that do not
 * line up). Either way, a finding that cannot go on the results' lines is one
 * line under the list, in the step screen's form, and takes one result's
 * place.
 *
 * Past `LISTED` results the first ones are shown and the rest counted, and
 * past four the type is a step smaller. Both are for the same reason: the
 * closing screen must fit, buttons and all, at 150% with nine results, with a
 * sentence above them or without (`test_closing.py`).
 */
export function Findings({ findings, size, less = 0 }: {
  findings: Finding[]; size: number; less?: number;
}) {
  const lists = findings.map((finding) =>
    finding.values?.length ? finding.values : [finding.value]);
  const sent = findings[0]?.rows ?? [];
  const byRows = sent.length > 1;
  const count = byRows ? sent.length : lists[0]?.length ?? 0;

  if (count <= 1) {
    const [answer, ...support] = findings;
    // A slip, like the bill it usually is (2026-10-07): the answer large with
    // what it is under it, a torn-paper rule, then what supports it, each
    // value beside its label. Nothing is added that the page did not say.
    return (
      <div className="flex flex-col gap-6 short:gap-4" data-testid="findings" data-shape="slip">
        <Found label={answer.label} size={size}>
          <span>{lists[0].length === 1 ? lists[0][0] : answer.value}</span>
        </Found>
        {support.length > 0 && (
          <div className="flex flex-col gap-2 border-t-2 border-dashed border-line pt-5 short:pt-3">
            {support.map((finding, index) => (
              <p key={finding.label}
                 className="flex items-baseline justify-between gap-6 text-lead short:text-body">
                <span className="text-soft">{finding.label}</span>
                {/* A supporting finding with several values is the step
                    screen's one line, which counts past four. */}
                <span className="font-semibold text-ink">
                  {lists[index + 1].length === 1 ? lists[index + 1][0] : finding.value}
                </span>
              </p>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Whether a finding can go on each result's line: from rows, any finding
  // with a cell in some row; from lists, only one exactly as long.
  const onLine = (index: number) => byRows
    ? sent.some((row) => Boolean(row[index]))
    : lists[index].length === count;
  const beside = findings.filter((_, index) => onLine(index));
  const apart = findings.filter((_, index) => !onLine(index));
  // Each detail that does not line up takes one result's place, so the screen
  // is no taller for it: as its own block, label and all, it put both buttons
  // below a 606px window with nine trains and eight journey times
  // (`test_terminal_states.py`, 2026-10-05).
  // And each line the sentence above takes past its first gives up one too
  // (`less`): a sentence that names a tie of three trains wraps at 150%, and
  // the page then scrolled by 10px (2026-10-06).
  const shown = Math.max(1, Math.min(count, LISTED - apart.length - less));
  const rows = Array.from({ length: shown }, (_, row) =>
    findings.flatMap((_, index) => !onLine(index) ? []
      : [byRows ? sent[row][index] ?? "" : lists[index][row]])
      .filter(Boolean)
      .join(", "));
  // 54px for a few; past four, the size of a step's instruction.
  const rowSize = count > 4 ? TYPE.title : Math.round(size * 0.75);

  if (byRows) {
    return (
      <Tickets findings={findings} rows={sent} onLine={onLine} apart={apart} less={less} />
    );
  }

  return (
    <div className="flex flex-col gap-2" data-testid="findings">
      <Found label={beside.map((finding) => finding.label).join(", ")}
             size={rowSize}>
        {rows.map((row, index) => <span key={index}>{row}</span>)}
        {count > shown && (
          <span className="text-body font-medium text-soft">{ENDING.more(count - shown)}</span>
        )}
      </Found>
      {/* Not beside any one result, so under the list, in the label's type. */}
      {apart.map((finding) => (
        <p key={finding.label} className="text-body text-soft">
          {finding.label}: <span className="font-medium text-ink">{finding.value}</span>
        </p>
      ))}
    </div>
  );
}

/** `6 h 3 min` as 363, or null for anything else (`voice._minutes`). */
function minutes(text: string): number | null {
  const match = /^\s*(\d+)\s*h\s*(\d+)\s*min\s*$/.exec(text);
  return match ? Number(match[1]) * 60 + Number(match[2]) : null;
}

/**
 * Which results take least time, by row: the column whose every cell is a
 * journey time, its smallest value, and every row that has it. Empty when no
 * column is all times, or when every result takes the same — then none is
 * faster, and the sentence above already says they all take that long.
 */
export function fastestRows(rows: string[][]): Set<number> {
  const width = Math.max(0, ...rows.map((row) => row.length));
  for (let column = 0; column < width; column++) {
    const times = rows.map((row) => minutes(row[column] ?? ""));
    if (times.some((time) => time === null)) continue;
    const best = Math.min(...(times as number[]));
    const at = new Set(times.flatMap((time, row) => (time === best ? [row] : [])));
    return at.size === rows.length ? new Set() : at;
  }
  return new Set();
}

/** Results in a grid, two to a row. */
const TICKETS_PER_ROW = 2;
/** At most this many rows of them; the rest are counted. */
const TICKET_ROWS = 3;

/**
 * Results that came as whole rows, one ticket each (2026-10-07).
 *
 * The first cell is the result — a train's number — and the rest sit after a
 * torn-paper rule, in the page's own words; under the grid, one line names
 * what the cells are, as it did when results were lines. The fastest is
 * marked where the times can be read. Two to a row and three rows at most:
 * one line per ticket, so six of them are no taller than the six lines they
 * replace, and the closing screen still fits nine trains at 150%
 * (`test_closing.py`). Each extra line the sentence above takes, and each
 * detail that is not on the tickets, gives up a whole row of them.
 */
function Tickets({ findings, rows, onLine, apart, less }: {
  findings: Finding[]; rows: string[][]; onLine: (index: number) => boolean;
  apart: Finding[]; less: number;
}) {
  const count = rows.length;
  const columns = findings.flatMap((_, index) => (onLine(index) ? [index] : []));
  const shown = Math.min(count,
    Math.max(1, TICKET_ROWS - apart.length - less) * TICKETS_PER_ROW);
  const fastest = fastestRows(rows);
  const few = count <= 4;
  // The rows shown, in the page's order — and when the fastest is not among
  // them, it takes the last place, so the one marked is never in "and N more".
  const picked = Array.from({ length: shown }, (_, index) => index);
  const best = [...fastest][0];
  if (best !== undefined && !picked.some((index) => fastest.has(index))) {
    picked[picked.length - 1] = best;
  }

  return (
    <div className="flex flex-col gap-3" data-testid="findings" data-shape="tickets">
      <ul className="grid grid-cols-2 gap-3 short:gap-2">
        {picked.map((index) => {
          const row = rows[index];
          const [first, ...rest] = columns.map((column) => row[column] ?? "");
          const quickest = fastest.has(index);
          return (
            <li key={index}
                data-testid="ticket"
                data-fastest={quickest ? "true" : undefined}
                className={`flex items-center gap-4 rounded-lg border-2 bg-canvas px-5
                            ${few ? "py-4 short:py-3" : "py-2.5 short:py-1.5"}
                            ${quickest ? "border-accent" : "border-line"}`}>
              <span className="font-semibold leading-[1.1] tracking-[-0.02em] text-ink"
                    style={{ fontSize: few ? TYPE.heading : TYPE.title }}>
                {first}
              </span>
              {rest.some(Boolean) && (
                <span className="min-w-0 flex-1 truncate border-l-2 border-dashed border-line
                                 pl-4 text-body font-medium text-ink">
                  {rest.filter(Boolean).join(", ")}
                </span>
              )}
              {quickest && (
                <span className="shrink-0 rounded-full bg-accent px-3 py-0.5 text-caption
                                 font-semibold text-accent-ink">
                  {ENDING.fastest}
                </span>
              )}
            </li>
          );
        })}
      </ul>
      <p className="flex flex-wrap items-baseline gap-x-4 text-body text-soft">
        <span>{columns.map((index) => findings[index].label).join(", ")}</span>
        {count > shown && <span className="font-medium">{ENDING.more(count - shown)}</span>}
      </p>
      {/* Not on any one ticket, so under them, in the label's type. */}
      {apart.map((finding) => (
        <p key={finding.label} className="text-body text-soft">
          {finding.label}: <span className="font-medium text-ink">{finding.value}</span>
        </p>
      ))}
    </div>
  );
}

/**
 * How many lines a paragraph takes, measured after layout and again whenever
 * its box changes size (the compact layout sets it smaller). 1 until measured,
 * and 0 for a paragraph that is not there.
 */
function useLines(ref: React.RefObject<HTMLElement>): number {
  const [lines, setLines] = useState(1);
  useLayoutEffect(() => {
    const element = ref.current;
    if (element === null) {
      setLines(0);
      return;
    }
    const measure = (): void => {
      const height = element.getBoundingClientRect().height;
      const lineHeight = parseFloat(getComputedStyle(element).lineHeight);
      setLines(lineHeight > 0 ? Math.max(1, Math.round(height / lineHeight)) : 1);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [ref]);
  return lines;
}

/** How many results the closing screen lists before it counts the rest. */
const LISTED = 6;

/** Values in large type, one per line, and the label under them, small. */
function Found({ label, size, children }: {
  label: string; size: number; children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-col gap-1 font-semibold leading-[1.08] tracking-[-0.02em] text-ink"
           style={{ fontSize: size }}>
        {children}
      </div>
      <span className="text-body text-soft">{label}</span>
    </div>
  );
}

function Failed() {
  const { failed, startOver } = useStore();
  return (
    <div className="flex flex-col gap-8 short:gap-5">
      <Card tone="stuck" className="flex flex-col gap-4 px-12 py-10 short:py-7">
        <span className="text-stuck" aria-hidden>
          <PauseIcon size={34} />
        </span>
        <h1 className="text-display font-semibold tracking-[-0.015em] text-stuck">
          {STOPPED.failedHeading}
        </h1>
        <p className="text-lead text-ink">{failed?.reason}</p>
      </Card>
      <OnwardButton onClick={startOver} />
    </div>
  );
}

/**
 * The assistant could not go on, and has stopped.
 *
 * This screen had no action at all. `STOPPED.again` existed in `copy.ts` and
 * nothing rendered it, so a stuck task was a dead end: a heading, a request,
 * and nothing to press. For this audience that is the worst screen there is —
 * the one moment the system admits it needs them is the one moment it gives
 * them nowhere to go. The backend closes the socket after `help.requested`,
 * so there is nothing to wait for either.
 *
 * `test_terminal_states.py` renders every ending and fails if one has nothing
 * to press, or if pressing it does not lead anywhere.
 */
function Stuck() {
  const { help, startOver } = useStore();
  return (
    <div className="flex flex-col gap-8 short:gap-5">
      <Card tone="stuck" className="px-12 py-10 short:py-7">
        <StuckNote reason={help?.reason} suggestion={help?.suggestion} />
      </Card>
      <OnwardButton onClick={startOver} />
    </div>
  );
}

/**
 * The person pressed stop, and it has.
 *
 * Not `Failed`. Stopping was their decision, and the screen says the decision
 * was carried out — in the same calm type as everything else, not the warm
 * colour the stuck and failed screens use to say something went wrong.
 */
function StoppedByPerson() {
  const { startOver } = useStore();
  return (
    <div className="flex flex-col gap-8 short:gap-5">
      <div className="flex flex-col items-start gap-5">
        <span className="flex h-16 w-16 items-center justify-center rounded-full bg-sunk
                         text-soft" aria-hidden>
          <CheckIcon size={34} />
        </span>
        <h1 className="text-display font-semibold tracking-[-0.015em] text-ink">
          {STOPPED.byYou}
        </h1>
      </div>
      <OnwardButton onClick={startOver} />
    </div>
  );
}

/** The one way onward from a screen that has ended. Same words, same place. */
function OnwardButton({ onClick }: { onClick: () => void }) {
  return <Button onClick={onClick}>{STOPPED.again}</Button>;
}
