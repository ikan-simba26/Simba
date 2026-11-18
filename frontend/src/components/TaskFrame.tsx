/**
 * The one layout every task screen has (2026-11-17, the frontend redesign).
 *
 * Left, "So far": each finished thing as a small chip, the thing now at the
 * foot, highlighted. Middle: the one question, or the one thing happening, as
 * large as the window allows. Right: the card that builds, filling in field by
 * field as SIMBA learns each thing (`TheCard`). The three never move between
 * screens; only the middle changes.
 *
 * At the simplest level the model has folded the screen: the side panels go,
 * the middle stays, with one line saying why and "Show more" to bring them
 * back. A final screen is never folded: the card is what is about to happen.
 *
 * The colours say whose turn it is, and are the same everywhere: a bar at the
 * top and a pill beside the lion — teal and a soft halo while SIMBA works,
 * amber for the person's turn or decision, green once done.
 */

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useRef, type ReactNode } from "react";

import lionMint from "../../../assets/brand/simba-lion-mint.svg";
import lionTeal from "../../../assets/brand/simba-lion-teal.svg";
import { FRAME, STATUS } from "../copy";
import { EASE, MOTION } from "../design";
import { brief, firstLine } from "../journey";
import { FramedContext } from "./framed";
import { usePresenceMode } from "../presenceMode";
import { useStore } from "../store";
import { LevelControl } from "./LevelControl";
import { TheCard } from "./TheCard";
import { CheckIcon } from "./ui";

/** Whose turn it is, by name: the bar and the pill are drawn from it. */
export type Phase = "working" | "turn" | "decision" | "help" | "done" | "stuck" | "calm";

/**
 * The phase of what is on screen, or null on the home screen and the
 * screens that are not a task. The same everywhere a colour is drawn.
 */
export function usePhase(): Phase | null {
  const { step, handover, completed, failed, help, state, stoppedByPerson, declined, task,
          asking, checklist, answered } = useStore();
  if (handover) return "help";
  if (stoppedByPerson || declined) return "calm";
  if (completed) return "done";
  if (help || failed || state === "stuck") return "stuck";
  if (step && !answered && !step.routine) return step.final ? "decision" : "turn";
  if (task || asking || checklist.length > 0 || step) return "working";
  return null;
}

const BAR: Record<Phase, string> = {
  working: "bg-accent", turn: "bg-turn", decision: "bg-turn", help: "bg-spot",
  done: "bg-done", stuck: "bg-stuck", calm: "bg-line",
};

/** The 6px bar across the top of every task screen. */
export function StateBar() {
  const phase = usePhase();
  if (!phase) return null;
  return (
    <div aria-hidden className={`fixed inset-x-0 top-0 z-[3] h-1.5 ${BAR[phase]}`}
         data-testid="state-bar" data-phase={phase} />
  );
}

const PILL: Record<"working" | "turn" | "decision" | "done", { words: string; box: string; dot: string }> = {
  working: { words: FRAME.working, box: "bg-accent text-accent-ink", dot: "bg-spot simba-halo" },
  turn: { words: FRAME.turn, box: "bg-turn-tint text-turn-ink", dot: "bg-turn" },
  decision: { words: FRAME.decision, box: "bg-turn-tint text-turn-ink", dot: "bg-turn" },
  done: { words: FRAME.done, box: "bg-done-tint text-done-ink", dot: "bg-done" },
};

export function Lion({ className = "h-10 w-10" }: { className?: string }) {
  return (
    <>
      <img src={lionTeal} alt="" className={`${className} object-contain dark:hidden`} />
      <img src={lionMint} alt="" className={`${className} hidden object-contain dark:block`} />
    </>
  );
}

/** The left panel is 250 wide, the card 360, and the gap between them 24. */
const SIDE = { left: 250, right: 360, gap: 24 };

export function TaskFrame({ children, centre }: { children: ReactNode; centre?: ReactNode }) {
  const { level, step, task, asking, answered, respond, stopTask, levelLocked, chooseLevel,
          trustOpen } = useStore();
  const phase = usePhase();
  const mode = usePresenceMode();
  const reduce = useReducedMotion() ?? false;
  const goal = task?.goal ?? asking ?? "";
  // The simplest level folds the sides away; a final screen never folds.
  const folded = level === 3 && !step?.final;
  const stop = step && !answered ? step.actions.find((action) => action.kind === "secondary") : undefined;
  const pill = PILL[phase === "turn" || phase === "decision" || phase === "done" ? phase : "working"];
  const move = { duration: reduce ? 0 : MOTION.slow, ease: EASE };

  return (
    <FramedContext.Provider value>
      <div className="simba-canvas flex h-full min-h-0 flex-col bg-canvas pt-1.5" data-testid="task-frame"
           data-phase={phase ?? undefined} data-folded={folded ? "true" : undefined}>
        <header className="flex h-[72px] shrink-0 items-center justify-between gap-4 border-b border-line
                           bg-surface px-8 short:h-12 short:px-5">
          <div className="flex min-w-0 items-center gap-3">
            {/* The presence mark (2026-11-17): the lion, with a halo while SIMBA works.
                Announced as it always was: "Working on it", "Your turn". */}
            <span className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full short:h-10
                              short:w-10 ${phase === "working" ? "simba-halo" : ""}`}
                  role="status" aria-live="polite" aria-label={STATUS[mode]}
                  data-presence={mode} data-size="small" data-testid="frame-lion">
              <Lion className="h-9 w-9 short:h-8 short:w-8" />
            </span>
            <span className="truncate text-small font-semibold text-ink" data-testid="frame-title">
              {goal}
            </span>
          </div>
          <span className={`flex shrink-0 items-center gap-2 rounded-full px-4 py-1 text-small font-medium
                            ${pill.box}`} data-testid="state-pill">
            <span aria-hidden className={`h-2.5 w-2.5 rounded-full ${pill.dot}`} />
            {pill.words}
          </span>
          <div className="flex shrink-0 items-center gap-4">
            <span className="flex items-center gap-1" data-testid="frame-levels">
              <span className="text-small text-soft">{FRAME.show}</span>
              <LevelControl />
            </span>
            {stop ? (
              <button type="button" onClick={() => respond(stop.id, {})} data-testid="frame-stop"
                      className="min-h-12 rounded-md border border-edge bg-surface px-5 text-small
                                 font-medium text-ink shadow-press hover:bg-sunk">
                {stop.label}
              </button>
            ) : !step && phase === "working" ? (
              <button type="button" onClick={stopTask} data-testid="frame-stop"
                      className="min-h-12 rounded-md border border-edge bg-surface px-5 text-small
                                 font-medium text-ink shadow-press hover:bg-sunk">
                {FRAME.stop}
              </button>
            ) : null}
          </div>
        </header>

        <AnimatePresence initial={false}>
          {folded && (
            <motion.p key="busy" initial={reduce ? false : { opacity: 0, y: -8 }}
                      animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={move}
                      className="mx-auto mt-3 flex shrink-0 items-center gap-3 rounded-full bg-tint px-5 py-1.5
                                 text-small text-accent" data-testid="busy-line" role="status">
              <span>{levelLocked ? FRAME.lessAsked : FRAME.busy}</span>
              <button type="button" className="font-semibold underline underline-offset-4"
                      onClick={() => chooseLevel(2)} data-testid="show-more">
                {FRAME.showMore}
              </button>
            </motion.p>
          )}
        </AnimatePresence>

        <div className={`flex min-h-0 flex-1 px-8 pt-5 short:px-5 short:pt-2 ${
                     folded ? "pb-10 short:pb-10" : "pb-4 short:pb-2"}`}>
          <motion.div aria-hidden={folded} className="min-h-0 shrink-0 overflow-hidden"
                      initial={false}
                      animate={{ width: folded ? 0 : SIDE.left, opacity: folded ? 0 : 1,
                                 marginRight: folded ? 0 : SIDE.gap }}
                      transition={move}>
            <SoFar />
          </motion.div>

          <main className="relative min-h-0 min-w-0 flex-1 overflow-hidden rounded-xl bg-surface
                           shadow-card" data-testid="frame-centre" data-phase={phase ?? undefined}
                style={phase === "turn" || phase === "decision"
                  ? { boxShadow: "0 0 0 2px var(--turn-edge)" } : undefined}>
            {/* Kept mounted while the real page is shown, so what was typed in a
                box is still there when it is hidden again. */}
            <div data-frame-scroll
                 className={`simba-scroll h-full overflow-y-auto overflow-x-hidden px-9 py-7 short:px-6 short:py-2
                             ${trustOpen && centre ? "hidden" : ""}`}>
              {children}
            </div>
            {trustOpen && centre}
          </main>

          <motion.div aria-hidden={folded} className="min-h-0 shrink-0 overflow-hidden" initial={false}
                      animate={{ width: folded ? 0 : SIDE.right, opacity: folded ? 0 : 1,
                                 marginLeft: folded ? 0 : SIDE.gap }}
                      transition={move}>
            <TheCard />
          </motion.div>
        </div>
      </div>
    </FramedContext.Provider>
  );
}

/* --------------------------------------------------------------- so far */

/** One finished thing, as a chip with a tick, and a Change button when it was
 *  an answer the person gave and nothing has been done on the website yet. */
function Chip({ text, testid, onChange }: { text: string; testid?: string; onChange?: () => void }) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-line bg-surface px-3 py-2.5 text-small
                   leading-snug text-ink short:py-2" data-testid={testid ?? "chip"}>
      <span aria-hidden className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full
                                    bg-accent text-accent-ink">
        <CheckIcon size={14} />
      </span>
      <span className="min-w-0 flex-1 break-words line-clamp-3">{text}</span>
      {onChange && (
        <button type="button" onClick={onChange} aria-label={FRAME.changeThis(text)}
                data-testid="chip-change"
                className="-my-1 min-h-9 shrink-0 rounded-md px-2 text-small font-semibold text-accent
                           underline underline-offset-4 hover:bg-tint">
          {FRAME.change}
        </button>
      )}
    </div>
  );
}

function SoFar() {
  const { done, task, asking, step, checklist, answered, answerLog, committed, completed, declined,
          stoppedByPerson, failed, help, handover, changeAnswer } = useStore();
  const phase = usePhase();
  const goal = task?.goal ?? asking ?? "";
  // The checklist's lines before the one being done are finished too.
  const finishedRows = checklist.slice(0, -1).map((row) => brief(row.label, 48));
  const chips = [...done, ...finishedRows].filter((text, index, all) => text && text !== all[index - 1]);
  const now = step && !answered
    ? brief(firstLine(step.instruction), 70)
    : checklist.length > 0 ? brief(checklist[checklist.length - 1].label, 70) : FRAME.nowWorking;
  const turn = phase === "turn" || phase === "decision";
  // "Change" is for an answer the person gave, until something is done on the
  // website (Do it, Pay now) or the task has ended (B3).
  const canChange = !committed && !completed && !declined && !stoppedByPerson && !failed && !help
    && !handover;
  const used = new Set<number>();
  const recordOf = (text: string): number | null => {
    const found = answerLog.findIndex((record, position) => record.chip === text && !used.has(position));
    if (found >= 0) used.add(found);
    return found >= 0 ? found : null;
  };
  const end = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion() ?? false;
  useEffect(() => {
    end.current?.scrollIntoView({ block: "end", behavior: reduce ? "auto" : "smooth" });
  }, [chips.length, reduce]);

  return (
    <aside aria-label={FRAME.soFar} className="flex h-full w-[250px] flex-col gap-3 pb-9" data-testid="so-far">
      <p className="text-small font-semibold text-soft">{FRAME.soFar}</p>
      <div className="simba-scroll flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto pr-1">
        {goal && (
          <div className="flex items-start gap-3 rounded-lg border border-line bg-surface px-3 py-2.5
                         text-small leading-snug text-ink short:py-2" data-testid="chip-asked">
            <span aria-hidden className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center
                                          rounded-full bg-accent text-accent-ink"><CheckIcon size={14} /></span>
            <span className="min-w-0 break-words line-clamp-3">
              <span className="text-soft">{FRAME.asked}</span> {goal}
            </span>
          </div>
        )}
        {chips.map((text, index) => {
          const record = recordOf(text);
          return <Chip key={`${index}-${text}`} text={text}
                       onChange={canChange && record !== null ? () => changeAnswer(record) : undefined} />;
        })}
        <div ref={end} aria-hidden className="h-px shrink-0" />
      </div>
      <p className={`rounded-lg border-2 px-3 py-2.5 text-small font-semibold leading-snug
                     ${turn ? "border-turn bg-turn-tint text-turn-ink" : "border-accent bg-tint text-accent"}`}
         data-testid="chip-now" aria-current="step">
        <span>{FRAME.now}</span> <span className="break-words line-clamp-3">{now}</span>
      </p>
    </aside>
  );
}
