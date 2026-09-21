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
import { useEffect, useRef, useState } from "react";

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
import { ARRIVE, TYPE } from "./design";
import { StepView } from "./components/StepView";
import type { Finding, FlowName } from "@shared/schema";

import { useStore } from "./store";
import { useOverflowGuard } from "./useOverflowGuard";

const ALL_FLOWS: FlowName[] = ["registration", "billing", "railways"];

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
    <div className="flex min-h-full flex-col items-center bg-canvas px-6 pt-8 pb-16">
      <PresenceBar />
      <div className="mt-8 w-full max-w-[680px]">
        <LevelNotice />
        <StepFailureNotice />
        <Column />
      </div>
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
  const { trustOpen } = useStore();
  const mode = usePresenceMode();
  return (
    <motion.div animate={{ opacity: trustOpen ? 0 : 1 }} transition={ARRIVE}>
      <Presence mode={mode} />
    </motion.div>
  );
}

function Column() {
  const { step, help, completed, failed, stoppedByPerson, task, trustOpen, reply, state, asking } =
    useStore();

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
      animate={{ y: trustOpen ? -28 : 0, opacity: trustOpen ? 0 : 1 }}
      transition={{ duration: 0.42, ease: [0.4, 0, 0.2, 1] }}
      style={{ pointerEvents: trustOpen ? "none" : "auto" }}
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
  // The box is revealed rather than shown when there is history: an empty
  // text field is the hardest thing on this screen, and it should not be the
  // first thing.
  //
  // Derived, not initial state. `history` arrives over the socket a moment
  // after the first render, so seeding `useState` from it meant the box was
  // always showing and the button that reveals it never appeared at all.
  const [revealed, setRevealed] = useState(false);
  const asking = revealed || history.length === 0;
  // A remembered goal that is word for word one of the cards is shown once.
  const again = history.filter((past) => !Object.values(FLOWS).includes(past.goal));

  return (
    <div className="flex flex-col gap-10">
      <h1 className="text-display font-semibold tracking-[-0.015em] text-ink">
        {HOME.greeting}
      </h1>

      <Section lead={HOME.canHelp}>
        {ALL_FLOWS.map((flow) => (
          <ChoiceCard key={flow} icon={<FlowIcon flow={flow} />}
                      onClick={() => startTask(FLOWS[flow], flow)}>
            {FLOWS[flow]}
          </ChoiceCard>
        ))}
      </Section>

      {again.length > 0 && (
        <Section lead={HOME.againHeading}>
          {again.map((past) => (
            <ChoiceCard key={`${past.site}|${past.goal}`} icon={<AgainIcon />}
                        onClick={() => startTask(past.goal)}>
              {past.goal}
            </ChoiceCard>
          ))}
        </Section>
      )}

      {/* The box, once asked for. `AnimatePresence` so it arrives rather than
          appearing: a control that was not there a moment ago should be seen
          to have been added. */}
      <AnimatePresence initial={false}>
        {asking ? (
          <motion.div
            key="ask"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={ARRIVE}
            className="-m-3 overflow-hidden p-3"
          >
            {/* Typing latches it open. History can arrive after the box has
                been shown, and before this the box then hid itself under
                "Ask for something new" with the person's words in it — found
                by a test that typed at the wrong moment (2026-09-21). */}
            <AskBox lead={history.length > 0 ? HOME.askHeading : undefined} autoFocus
                    onType={() => setRevealed(true)} />
          </motion.div>
        ) : (
          <motion.div key="something-else" exit={{ opacity: 0 }} transition={ARRIVE}
                      className="flex justify-center">
            <Button variant="quiet" onClick={() => setRevealed(true)}>
              {HOME.somethingElse}
            </Button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/** A lead-in and what it introduces. */
function Section({ lead, children }: { lead: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <p className="text-small font-medium text-soft">{lead}</p>
      <div className="flex flex-col gap-3">{children}</div>
    </section>
  );
}

/**
 * The place to ask in your own words. A soft card with the question inside
 * it rather than a bare form field: it should look like somewhere to talk,
 * not a box to fill in.
 */
function AskBox({
  lead,
  autoFocus,
  onType,
}: {
  lead?: string;
  autoFocus?: boolean;
  onType?: () => void;
}) {
  const { startTask } = useStore();
  const [goal, setGoal] = useState("");
  const start = () => {
    if (goal.trim()) startTask(goal.trim());
  };

  return (
    <div className="flex flex-col gap-3">
      {lead && <p className="text-small font-medium text-soft">{lead}</p>}
      <div
        className="flex items-center gap-3 rounded-xl border border-line bg-surface py-2 pr-2
                   pl-5 shadow-card transition-[border-color,box-shadow] duration-200
                   focus-within:border-accent"
      >
        <span className="shrink-0 text-soft" aria-hidden>
          <SpeechIcon />
        </span>
        <input
          autoFocus={autoFocus}
          className="min-w-0 flex-1 bg-transparent py-3 text-lead text-ink outline-none
                     placeholder:text-soft/80 focus-visible:outline-none"
          value={goal}
          onChange={(event) => {
            setGoal(event.target.value);
            onType?.();
          }}
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
    <div className="flex flex-col gap-10">
      <div className="flex flex-col gap-5">
        <h1 className="text-display font-semibold tracking-[-0.015em] text-ink">{heading}</h1>
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
      ) : (
        <Section lead={reply.kind === "unsupported" ? REPLY.canDo : HOME.canHelp}>
          {reply.flows.map((flow) => (
            <ChoiceCard key={flow} icon={<FlowIcon flow={flow} />}
                        onClick={() => startTask(FLOWS[flow], flow)}>
              {FLOWS[flow]}
            </ChoiceCard>
          ))}
        </Section>
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
    <div className="flex flex-col items-center gap-4 pt-16 text-center">
      <h1 className="text-display font-semibold tracking-[-0.015em] text-ink">
        {presence(situation)}
      </h1>
      {goal && <p className="max-w-[520px] text-lead text-soft">{goal}</p>}
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
      <Card className="px-10 py-9">
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
      <LevelControl />
      <TrustControl />
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

  return (
    <div className="flex flex-col gap-8">
      {findings.length > 0 ? (
        <Card className="px-10 py-10">
          <p className="mb-6 text-small font-medium text-soft">{ENDING.withAnswer}</p>
          <Findings findings={findings} size={TYPE.hero} />
        </Card>
      ) : (
        <div className="flex flex-col items-start gap-5">
          <span className="flex h-14 w-14 items-center justify-center rounded-full bg-tint
                           text-accent" aria-hidden>
            <CheckIcon />
          </span>
          <h1 className="text-display font-semibold tracking-[-0.015em] text-ink">
            {ENDING.withoutAnswer}
          </h1>
          <p className="text-lead text-soft">{task?.goal}</p>
        </div>
      )}

      <div className="flex flex-col gap-3">
        <Button onClick={startOver}>{ENDING.finish}</Button>
        <Button variant="secondary" onClick={startOver}>{ENDING.again}</Button>
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
 * Every result, one per line. A search that returns three trains was asked
 * about three trains, and `value` — the one line the step screen shows — stops
 * at four and counts the rest, so reading it here would hide results on the
 * one screen that exists to show them. `values` is the whole list; a message
 * from before it existed has none, and then the line is the answer.
 *
 * The type shrinks as the list grows rather than the list shortening. One
 * value keeps the full size, because one value is the billing case and it
 * should look exactly as it did. Enough of them and the screen scrolls, which
 * is a smaller failure on an ending than an answer that is not all there.
 */
export function Findings({ findings, size }: { findings: Finding[]; size: number }) {
  return (
    <div className="flex flex-col gap-7">
      {findings.map((finding, index) => {
        const values = finding.values?.length ? finding.values : [finding.value];
        // The first finding is the answer; any others support it.
        const lead = index === 0 ? size : Math.round(size * 0.55);
        const scale = values.length > 4 ? 0.55 : values.length > 1 ? 0.75 : 1;
        return (
          <div key={finding.label} className="flex flex-col gap-2">
            <div className="flex flex-col gap-1">
              {values.map((value) => (
                <span
                  key={value}
                  className="font-semibold leading-[1.08] tracking-[-0.02em] text-ink"
                  style={{ fontSize: Math.round(lead * scale) }}
                >
                  {value}
                </span>
              ))}
            </div>
            <span className="text-body text-soft">{finding.label}</span>
          </div>
        );
      })}
    </div>
  );
}

function Failed() {
  const { failed, startOver } = useStore();
  return (
    <div className="flex flex-col gap-8">
      <Card tone="stuck" className="flex flex-col gap-4 px-10 py-9">
        <span className="text-stuck" aria-hidden>
          <PauseIcon />
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
    <div className="flex flex-col gap-8">
      <Card tone="stuck" className="px-10 py-9">
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
    <div className="flex flex-col gap-8">
      <div className="flex flex-col items-start gap-5">
        <span className="flex h-14 w-14 items-center justify-center rounded-full bg-sunk
                         text-soft" aria-hidden>
          <CheckIcon />
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
