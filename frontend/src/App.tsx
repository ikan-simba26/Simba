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
import { StepView } from "./components/StepView";
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
  const { state, step, help, completed, failed, task, trustOpen } = useStore();

  const acting = state === "acting";
  const thinking = state === "thinking";
  const stuck = state === "stuck" || Boolean(help);

  // One screen at a time, and only one. The key drives the crossfade.
  const screen = stuck
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
              {screen === "idle" && <Idle />}
              {screen === "working" && <Working />}
              {screen.startsWith("step-") && <Step />}
              {screen === "completed" && <Completed />}
              {screen === "failed" && <Failed />}
              {screen === "stuck" && (
                <StuckNote reason={help?.reason} suggestion={help?.suggestion} />
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </ThinkingPulse>
    </motion.div>
  );
}

function Idle() {
  const startTask = useStore((state) => state.startTask);
  const [goal, setGoal] = useState("");

  const start = () => {
    if (goal.trim()) startTask(goal.trim());
  };

  return (
    <div className="flex flex-col gap-10">
      <h1 className="text-[30px] leading-[1.35] font-medium tracking-[-0.01em]">
        What would you like me to do?
      </h1>

      <input
        autoFocus
        className="h-14 rounded-lg border border-line bg-raised px-4 text-[19px] text-ink
                   outline-none transition-colors duration-300 focus:border-accent"
        value={goal}
        onChange={(event) => setGoal(event.target.value)}
        onKeyDown={(event) => event.key === "Enter" && start()}
        placeholder="Pay my electricity bill"
        aria-label="What would you like me to do?"
      />

      <button
        type="button"
        onClick={start}
        disabled={!goal.trim()}
        className="h-16 w-full rounded-xl bg-accent px-6 text-[19px] font-medium
                   text-accent-ink transition-all duration-300 hover:brightness-105
                   disabled:opacity-35"
      >
        Start
      </button>
    </div>
  );
}

/** Between task.started and the first step. Says what it is doing, and waits. */
function Working() {
  const task = useStore((state) => state.task);
  return (
    <h1 className="text-[30px] leading-[1.35] font-medium tracking-[-0.01em] text-ink/80">
      {task?.goal ?? "Working on it"}
    </h1>
  );
}

function Step() {
  const { step, state, level, respond, answered } = useStore();
  const [values, setValues] = useState<Record<string, string>>({});
  const measured = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!step) return;
    const initial: Record<string, string> = {};
    for (const field of step.fields) initial[field.id] = field.value;
    setValues(initial);
  }, [step]);

  // A step that will not fit drops a level instead of growing a scrollbar.
  useOverflowGuard(measured, { level, active: Boolean(step) });

  if (!step) return null;

  return (
    <div ref={measured}>
      <StepView
        level={level}
        step={step}
        values={values}
        waiting={isWaiting(state)}
        answered={answered}
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

function Completed() {
  const completed = useStore((state) => state.completed);
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-[30px] leading-[1.35] font-medium tracking-[-0.01em]">
        Done.
      </h1>
      <p className="text-[19px] leading-relaxed text-ink/80">{completed?.summary}</p>
    </div>
  );
}

function Failed() {
  const failed = useStore((state) => state.failed);
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-[30px] leading-[1.35] font-medium tracking-[-0.01em] text-stuck">
        That didn&rsquo;t work.
      </h1>
      <p className="text-[19px] leading-relaxed text-ink/80">{failed?.reason}</p>
    </div>
  );
}
