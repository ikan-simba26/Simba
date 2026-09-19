/**
 * The overlay. This is what the person actually sees.
 *
 * One column, one thing at a time, nothing in the corners. Everything the
 * developer might want — the log, the connection, the raw messages — lives
 * behind Ctrl+Shift+D and is not on screen otherwise.
 *
 * All three levels, with the change between them animated as a fold rather
 * than a swap — see `StepShell`.
 */

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

import { DebugPanel, useDebugShortcut } from "./components/Debug";
import { LevelControl, LevelNotice } from "./components/LevelControl";
import { TrustControl, TrustPanel } from "./components/TrustPanel";
import { ActingLine, StuckNote, ThinkingPulse, isWaiting } from "./components/StateSignal";
import { StepFailureNotice } from "./components/StepNotice";
import { ENDING, HOME, STOPPED, presence } from "./copy";
import { StepView } from "./components/StepView";
import type { Finding } from "@shared/schema";

import { useStore } from "./store";
import { useOverflowGuard } from "./useOverflowGuard";

const EASE = [0.22, 0.61, 0.36, 1] as const;
const TRANSITION = { duration: 0.3, ease: EASE };

export default function App() {
  const connect = useStore((state) => state.connect);
  useDebugShortcut();

  useEffect(() => {
    connect();
  }, [connect]);

  return (
    <div className="flex min-h-full justify-center bg-canvas px-6 py-24">
      <div className="w-full max-w-[640px]">
        <LevelNotice />
        <StepFailureNotice />
        <Column />
      </div>
      <TrustPanel />
      <DebugPanel />
    </div>
  );
}

function Column() {
  const { state, step, help, completed, failed, stoppedByPerson, task, trustOpen } = useStore();

  const acting = state === "acting";
  const thinking = state === "thinking";
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
          : task
            ? "working"
            : "idle";

  return (
    <motion.div
      // Out of the way while the real page is being shown.
      animate={{ y: trustOpen ? -28 : 0, opacity: trustOpen ? 0 : 1 }}
      transition={{ duration: 0.42, ease: [0.32, 0.72, 0, 1] }}
      style={{ pointerEvents: trustOpen ? "none" : "auto" }}
    >
      <ActingLine active={acting} />

      <ThinkingPulse active={thinking && !step}>
        {/* Both screens share one grid cell, so the outgoing and incoming
            ones overlap during the crossfade instead of stacking and
            shoving the column down. `mode="wait"` would avoid the overlap
            by serialising them, but it strands the transition here: the
            exiting child stays mounted at opacity 0 and the next one never
            arrives, leaving the column blank. */}
        <div className="grid">
          <AnimatePresence initial={false}>
            <motion.div
              key={screen}
              /* No `layout` on this element: reflow is done with `layout`
                 on the blocks inside a step instead. */
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={TRANSITION}
              className="pt-10 [grid-area:1/1]"
            >
              {screen === "idle" && <Home />}
              {screen === "working" && <Working />}
              {screen.startsWith("step-") && <Step />}
              {screen === "completed" && <Completed />}
              {screen === "failed" && <Failed />}
              {screen === "stopped" && <StoppedByPerson />}
              {screen === "stuck" && <Stuck />}
            </motion.div>
          </AnimatePresence>
        </div>
      </ThinkingPulse>
    </motion.div>
  );
}

function Home() {
  const { startTask, history } = useStore();
  const [goal, setGoal] = useState("");
  // The box is revealed rather than shown: an empty text field is the hardest
  // thing on this screen, and it should not be the first thing.
  //
  // Derived, not initial state. `history` arrives over the socket a moment
  // after the first render, so seeding `useState` from it meant the box was
  // always showing and the button that reveals it never appeared at all.
  const [revealed, setRevealed] = useState(false);
  const asking = revealed || history.length === 0;

  const start = () => {
    if (goal.trim()) startTask(goal.trim());
  };

  return (
    <div className="flex flex-col gap-8">
      <h1 className="text-[30px] leading-[1.35] font-medium tracking-[-0.01em]">
        {HOME.greeting}
      </h1>

      {history.length > 0 && (
        <div className="flex flex-col gap-3">
          <p className="text-[15px] text-muted">{HOME.againHeading}</p>
          {history.map((past) => (
            <button
              key={`${past.site}|${past.goal}`}
              type="button"
              onClick={() => startTask(past.goal)}
              className="w-full rounded-xl border border-line bg-raised px-5 py-5
                         text-left text-[21px] leading-snug text-ink
                         transition-colors duration-300 hover:border-accent"
            >
              {past.goal}
            </button>
          ))}
        </div>
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
            transition={TRANSITION}
            className="overflow-hidden"
          >
            <div className="flex flex-col gap-4">
              {history.length > 0 && (
                <p className="text-[15px] text-muted">{HOME.askHeading}</p>
              )}
              <input
                autoFocus
                className="h-14 rounded-lg border border-line bg-raised px-4 text-[19px] text-ink
                           outline-none transition-colors duration-300 focus:border-accent"
                value={goal}
                onChange={(event) => setGoal(event.target.value)}
                onKeyDown={(event) => event.key === "Enter" && start()}
                placeholder={HOME.placeholder}
                aria-label={HOME.askHeading}
              />
              <button
                type="button"
                onClick={start}
                disabled={!goal.trim()}
                className="h-16 w-full rounded-xl bg-accent px-6 text-[19px] font-medium
                           text-accent-ink transition-all duration-300 hover:brightness-105
                           disabled:opacity-35"
              >
                {HOME.start}
              </button>
            </div>
          </motion.div>
        ) : (
          <motion.button
            key="something-else"
            type="button"
            exit={{ opacity: 0 }}
            transition={TRANSITION}
            onClick={() => setRevealed(true)}
            className="w-full text-center text-[17px] text-muted underline underline-offset-4
                       transition-colors duration-300 hover:text-ink"
          >
            {HOME.somethingElse}
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  );
}

/**
 * Between task.started and the first step, and between steps.
 *
 * Says what is happening in the same plain voice as everything else, rather
 * than leaving an unlabelled pulse to be interpreted. The sentence comes from
 * `copy.ts` and is the same one every time this situation occurs.
 */
function Working() {
  const { task } = useStore();
  // Thinking and acting are one situation from the person's side — wait —
  // and share a sentence. The acting line above the column tells them apart.
  const situation = task ? "working" : "opening";
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-[30px] leading-[1.35] font-medium tracking-[-0.01em] text-ink/80">
        {presence(situation)}
      </h1>
      {task && <p className="text-[17px] leading-relaxed text-muted">{task.goal}</p>}
    </div>
  );
}

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
      <LevelControl />
      <TrustControl />
    </div>
  );
}

/**
 * The closing screen: the answer, then a way out.
 *
 * It used to say "Done." and the goal and the URL, which tells somebody who
 * asked what their bill was precisely nothing. A task that looked something
 * up ends with what it found, in the largest type on the screen, because
 * that is the thing the person came for. A task that changed something
 * instead says so plainly, and restates what was asked for.
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
      <p className="text-[17px] text-muted">
        {findings.length > 0 ? ENDING.withAnswer : ENDING.withoutAnswer}
      </p>

      {findings.length > 0 ? (
        <Findings findings={findings} size={44} />
      ) : (
        <p className="text-[26px] leading-snug text-ink">{task?.goal}</p>
      )}

      <div className="flex flex-col gap-3">
        <button
          type="button"
          onClick={startOver}
          className="h-16 w-full rounded-xl bg-accent px-6 text-[19px] font-medium
                     text-accent-ink transition-all duration-300 hover:brightness-105"
        >
          {ENDING.finish}
        </button>
        <button
          type="button"
          onClick={startOver}
          className="h-14 w-full rounded-xl border border-line px-6 text-[17px] text-muted
                     transition-colors duration-300 hover:border-ink/40 hover:text-ink"
        >
          {ENDING.again}
        </button>
      </div>
    </div>
  );
}

/**
 * What was found, largest thing on the card.
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
    <div className="flex flex-col gap-5">
      {findings.map((finding, index) => {
        const values = finding.values?.length ? finding.values : [finding.value];
        // The first finding is the answer; any others support it.
        const lead = index === 0 ? size : Math.round(size * 0.6);
        const scale = values.length > 4 ? 0.55 : values.length > 1 ? 0.75 : 1;
        return (
          <div key={finding.label} className="flex flex-col gap-1">
            <div className="flex flex-col gap-1">
              {values.map((value) => (
                <span
                  key={value}
                  className="font-medium leading-[1.15] tracking-[-0.01em] text-ink"
                  style={{ fontSize: Math.round(lead * scale) }}
                >
                  {value}
                </span>
              ))}
            </div>
            <span className="text-[15px] text-muted">{finding.label}</span>
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
      <h1 className="text-[30px] leading-[1.35] font-medium tracking-[-0.01em] text-stuck">
        {STOPPED.failedHeading}
      </h1>
      <p className="text-[19px] leading-relaxed text-ink/80">{failed?.reason}</p>
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
      <StuckNote reason={help?.reason} suggestion={help?.suggestion} />
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
      <h1 className="text-[30px] leading-[1.35] font-medium tracking-[-0.01em] text-ink">
        {STOPPED.byYou}
      </h1>
      <OnwardButton onClick={startOver} />
    </div>
  );
}

/** The one way onward from a screen that has ended. Same words, same place. */
function OnwardButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="h-16 w-full rounded-xl bg-accent px-6 text-[19px] font-medium
                 text-accent-ink transition-all duration-300 hover:brightness-105"
    >
      {STOPPED.again}
    </button>
  );
}
