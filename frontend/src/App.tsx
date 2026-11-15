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

import { AnimatePresence, motion, useIsPresent, useReducedMotion } from "framer-motion";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { HomeLogo, Splash, useSplash } from "./components/Brand";
import { DebugPanel, useDebugShortcut } from "./components/Debug";
import { LevelControl } from "./components/LevelControl";
import { FinalCheck } from "./components/FinalCheck";
import { ReadBack } from "./components/ReadBack";
import { TeachBar } from "./components/TeachBar";
import { HandoverBar } from "./components/HandoverBar";
import { StatusLine } from "./components/StatusLine";
import { TeachIntro } from "./components/TeachIntro";
import { ProofPanel } from "./components/ProofPanel";
import { TrustControl, TrustPanel } from "./components/TrustPanel";
import { StuckNote, isWaiting } from "./components/StateSignal";
import {
  Button,
  Card,
  CheckIcon,
  ChoiceCard,
  FlowIcon,
  AlertIcon,
  PageIcon,
  PauseIcon,
  Presence,
  SpeechIcon,
  type PresenceMode,
} from "./components/ui";
import { CHECKLIST, ENDING, FINAL, FLOWS, HOME, ONWARD, PROOF, REPLY, SITES, STOPPED,
         TEACH,
         TILES,
         WHICH,
         presence } from "./copy";
import { entrancePlayed } from "./entrance";
import { ARRIVE, COLUMN, EASE, TYPE } from "./design";
import { StepView } from "./components/StepView";
import { Welcome } from "./components/Welcome";
import { AddSite, hostOf } from "./components/Sites";
import { HOME_WIDTH, Home, SiteIcon } from "./components/Home";
import { TilesEditor } from "./components/TilesEditor";
import { TopLine } from "./components/StepShell";
import { NoticeTimers } from "./components/Notices";
import type { Finding } from "@shared/schema";

import { watchPresses } from "./pressGuard";
import { useStore } from "./store";
import { useOverflowGuard } from "./useOverflowGuard";
import { useShortWindow } from "./useShortWindow";

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

  // Every press logged, and a press on a button that has only just arrived
  // where it is ignored (2026-10-16, `pressGuard.ts`).
  useEffect(() => watchPresses(() => useStore.getState().level), []);

  // The logo while the backend comes up (`Brand.tsx`). The screens wait until
  // it starts to leave, so the home screen's entrance plays as it fades.
  const opening = useSplash();
  // While SIMBA watches a helper (2026-11-04), the overlay is the bar at the
  // top and nothing else: the host shows the real website below it.
  const teaching = useStore((state) => state.teaching);
  // The first screen is wider than a step's column (2026-11-14): its website
  // cards are five to a row.
  const screen = useScreen();

  // The real page handed to the person, to pay or pass a check (2026-11-13).
  const handover = useStore((state) => state.handover);

  if (teaching) return <TeachBar bar={teaching} />;
  if (handover) return <HandoverBar bar={handover} />;

  return (
    // The bottom padding is the one space on every screen nothing reads:
    // 32px, and 4px in a short window, since the step row and the real page's
    // button (2026-10-07) took the last few pixels at 100% and 150%.
    <div className="simba-canvas flex min-h-full flex-col items-center bg-canvas px-8 pt-6 pb-8
                    short:pt-3 short:pb-1">
      {!opening && (
        <>
          <CornerLogo />
          <TeachEntry />
          <PresenceBar />
          {/* Most of the window, not a third of it: 880 of 1280. The first
              column was 680, which at this type size left the person reading
              a narrow strip down the middle of an empty screen. */}
          <div className="relative z-[1] mt-6 w-full short:mt-3"
               style={{ maxWidth: screen === "idle" ? HOME_WIDTH : COLUMN }}>
            <NoticeTimers />
            <Column />
          </div>
        </>
      )}
      {!opening && <StatusNow />}
      <TrustPanel />
      <ProofPanel />
      <DebugPanel />
      <Splash up={opening} />
    </div>
  );
}

/** The status line, with what the presence mark means now (2026-11-13). */
function StatusNow() {
  const mode = usePresenceMode();
  return <StatusLine activity={mode} />;
}

/** The small logo, on the home screen and no other. */
function CornerLogo() {
  return <HomeLogo shown={useScreen() === "idle"} />;
}

/**
 * The way in for a helper (2026-11-10): "Teach a task", with the line under
 * it saying who it is for, in the window's top right corner on the home
 * screen and on no other, across from the small logo. It opens the same
 * "Show me a task once" screen as the settings do.
 *
 * Outside the person's column, as the logo is, because the column has no
 * height to give: with three own tiles, the three things SIMBA can do and two
 * goals asked before, the fullest home screen at 150% (1266x606) already
 * reaches the window's bottom edge, and one more row under the settings put
 * the box to ask in off the bottom by 73px; a row fixed at the bottom sat on
 * the settings row by 33px (both measured 2026-11-10). The corner costs the
 * column nothing; `test_home.box_fits` checks it stays above the greeting
 * and wholly in the window at every size.
 */
function TeachEntry() {
  const shown = useScreen() === "idle";
  const setTeachOpen = useStore((state) => state.setTeachOpen);
  return (
    <AnimatePresence initial={false}>
      {shown && (
        <motion.div key="teach-entry"
                    className="fixed top-6 right-8 z-[1] flex flex-col items-end gap-0.5 text-right
                               short:top-3"
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                    transition={ARRIVE} data-testid="teach-entry">
          <Button variant="quiet" size="md" wide={false} onClick={() => setTeachOpen(true)}
                  data-testid="teach-a-task">
            {TEACH.enter}
          </Button>
          <p className="px-2 text-small text-soft">{TEACH.enterDetail}</p>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/** Which of the presence mark's six shapes the current screen means. */
function usePresenceMode(): PresenceMode {
  const { state, step, help, completed, failed, stoppedByPerson, task, asking,
          declined } = useStore();
  // The person's own decision, carried out: calm, not stuck.
  if (stoppedByPerson || declined) return "ready";
  if (help || failed || state === "stuck") return "stuck";
  if (completed) return "done";
  if (state === "acting") return "acting";
  if (step && isWaiting(state)) return "waiting";
  if (task || asking) return "thinking";
  return "ready";
}

function PresenceBar() {
  const { trustOpen, task, asking, reply, completed, failed, help,
          stoppedByPerson, declined } = useStore();
  const mode = usePresenceMode();
  // Large on the home screen, the first thing seen; small everywhere else.
  const home = !task && !asking && !reply && !completed && !failed && !help && !stoppedByPerson
    && !declined;
  // It settles into place once, when SIMBA opens (`entrance.ts`), at the
  // same moment the tiles' entrance is decided — never under reduced motion.
  const reduce = useReducedMotion() ?? false;
  const [settle] = useState(() => !reduce && !entrancePlayed());
  const aside = trustOpen;
  return (
    // Out of the way while the real page is being shown. Nothing else is in
    // this row: since
    // 2026-10-14 notices and "Read this aloud" are in the card's first line.
    <motion.div className="relative z-[1] flex w-full justify-center"
                style={{ maxWidth: COLUMN, pointerEvents: aside ? "none" : "auto" }}
                animate={{ opacity: aside ? 0 : 1 }} transition={ARRIVE}>
      <motion.div initial={home && settle ? { opacity: 0, scale: 0.9 } : false}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.9, ease: EASE }}>
        {/* Small on the first screen too since 2026-11-14: the websites
            need the height, and the lion in the corner is the brand there. */}
        <Presence mode={mode} />
      </motion.div>
    </motion.div>
  );
}

/**
 * One screen at a time, and only one: which, by name. "idle" is the home
 * screen. `Column`'s key, so it drives the crossfade.
 *
 * The person's own stop comes first: once they have pressed it, the backend's
 * `task.failed` that follows is the stop being carried out, not a failure to
 * show them.
 */
function useScreen(): string {
  const { step, help, completed, failed, stoppedByPerson, task, reply, state,
          asking, checklist, declined, welcomeOpen, tilesOpen, teachOpen,
          addSiteOpen } = useStore();
  const stuck = state === "stuck" || Boolean(help);

  return declined
    ? "declined"
    : stoppedByPerson
    ? "stopped"
    : stuck
    ? "stuck"
    : completed
      ? "completed"
      : failed
        ? "failed"
        : step
          ? `step-${step.step_index}`
          : checklist.length > 0
            ? "checklist"
          : task || asking
            ? "working"
            : reply
              ? `reply-${reply.kind}`
              // "Add a website", from the foot of the list (2026-11-13).
              : addSiteOpen
                ? "addsite"
              // "Show me once", for a helper, from the settings (2026-11-04).
              : teachOpen
                ? "teach"
              // The welcome takes the home screen's place, first time only
              // or when asked for again (2026-10-18).
              : welcomeOpen
                ? "welcome"
                : tilesOpen
                  ? "tiles"
                  : "idle";
}

function Column() {
  const trustOpen = useStore((state) => state.trustOpen);
  const screen = useScreen();
  // Put aside while the real page is shown: the trust panel's picture.
  const aside = trustOpen;

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
          <ScreenFrame key={screen}>
            {screen === "idle" && <Home />}
            {screen === "welcome" && <Welcome />}
            {screen === "teach" && <TeachIntro />}
            {screen === "addsite" && <AddSite />}
            {screen === "tiles" && <TilesEditor />}
            {screen.startsWith("reply-") && <Reply />}
            {screen === "working" && <Working />}
            {screen.startsWith("step-") && <Step index={Number(screen.slice(5))} />}
            {screen === "checklist" && <Checklist />}
            {screen === "completed" && <Completed />}
            {screen === "failed" && <Failed />}
            {screen === "stopped" && <StoppedByPerson />}
            {screen === "declined" && <NothingChanged />}
            {screen === "stuck" && <Stuck />}
          </ScreenFrame>
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

/**
 * One screen of the column, arriving and leaving as a crossfade. A screen on
 * its way out takes no presses (2026-10-16): while a step faded out beside
 * the next one, the two copies' buttons sat at different heights, and a
 * press aimed at "Tomorrow" on the fading copy landed on the arriving
 * screen's "Stop this" — the stop nobody could explain from the first walk
 * of 2026-10-16. Found by logging every press (`pressGuard.ts`).
 */
function ScreenFrame({ children }: { children: React.ReactNode }) {
  const present = useIsPresent();
  return (
    <motion.div
      /* No `layout` on this element: reflow is done with `layout` on the
         blocks inside a step instead. */
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={ARRIVE}
      className="[grid-area:1/1]"
      style={{ pointerEvents: present ? "auto" : "none" }}
      aria-hidden={!present}
      data-leaving={present ? undefined : "true"}
    >
      {children}
    </motion.div>
  );
}

/* ----------------------------------------------------------------- home */

// The first screen is `components/Home.tsx` since 2026-11-14: "Where do you
// want to go?", then "What do you want to do there?".

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
  const { startTask, sites, chosenSite } = useStore();
  const [goal, setGoal] = useState("");
  // Any website (2026-11-13): typed here, or the one chosen in the list. Only
  // when the backend offers a list, so a backend without one sees no box.
  const [where, setWhere] = useState("");
  const chosen = sites.find((site) => site.id === chosenSite);
  const start = () => {
    const site = where.trim() || chosen?.address;
    if (goal.trim()) startTask(goal.trim(), undefined, undefined, undefined, site);
  };

  return (
    <div className="flex flex-col gap-3 short:gap-2">
      {lead && (
        <p className={`text-small font-medium text-soft${leadWhenShort ? "" : " short:hidden"}`}>
          {lead}
        </p>
      )}
      <div
        className="simba-field-frame flex items-center gap-4 rounded-xl py-2.5 pr-2.5 pl-6
                   shadow-card"
      >
        <span className="shrink-0 text-soft" aria-hidden>
          <SpeechIcon />
        </span>
        <input
          autoFocus={autoFocus}
          className="min-w-0 flex-1 bg-transparent py-4 text-lead text-ink outline-none short:py-3
                     placeholder:text-soft focus-visible:outline-none"
          value={goal}
          onChange={(event) => setGoal(event.target.value)}
          onKeyDown={(event) => event.key === "Enter" && start()}
          placeholder={HOME.placeholder}
          aria-label={HOME.askHeading}
        />
        {sites.length > 0 && (
          <input
            className="w-56 shrink-0 rounded-lg border border-edge bg-surface px-4 py-3 text-body
                       text-ink outline-none placeholder:text-soft focus-visible:border-accent
                       short:py-2"
            value={where}
            onChange={(event) => setWhere(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && start()}
            placeholder={chosen ? chosen.name : SITES.wherePlaceholder}
            aria-label={SITES.where}
            data-testid="ask-where"
          />
        )}
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
  const { reply, startTask, sites, setTeachOpen, startOver } = useStore();
  if (!reply) return null;

  const heading =
    reply.kind === "greeting" ? REPLY.greeting
    : reply.kind === "unsupported" ? REPLY.unsupported
    : reply.kind === "not_yet" ? REPLY.notYet(hostOf(reply.site ?? ""))
    : reply.kind === "not_allowed" ? REPLY.notAllowed(hostOf(reply.site ?? ""))
    : REPLY.clarify;

  return (
    <div className="flex flex-col gap-10 short:gap-6">
      <div className="flex flex-col gap-5 short:gap-3">
        {/* A way back on every reply (2026-11-15). A greeting, a question and
            "I can't do that" had none: "hello" left the person on a screen
            with no road to the first one. Beside the heading, so the screen
            is no taller; the two replies that carry their own are left alone. */}
        <div className="flex items-start justify-between gap-6">
          <h1 className="min-w-0 flex-1 text-display font-semibold tracking-[-0.015em] text-ink
                         short:text-heading">
            {heading}
          </h1>
          {reply.kind !== "not_yet" && reply.kind !== "not_allowed" && (
            <Button variant="secondary" size="md" wide={false} onClick={startOver}
                    data-testid="reply-back">
              {ONWARD}
            </Button>
          )}
        </div>
        {/* Their words on one line with the lead-in, not two: the reply to
            "book a flight" scrolled by 24px at 100% and 45px at 150% until
            2026-10-14. */}
        {reply.kind !== "greeting" && reply.goal && (
          <p className="flex flex-wrap items-baseline gap-x-3 border-l-4 border-tint pl-4">
            <span className="text-small font-medium text-soft">{REPLY.youAsked}</span>
            <span className="text-lead text-ink">{reply.goal}</span>
          </p>
        )}
      </div>

      {reply.kind === "not_allowed" ? (
        // The website's robots.txt says no (2026-11-13): SIMBA does not use
        // it, and offers no helper either, since a taught task would too.
        <div className="flex flex-col gap-4" data-testid="not-allowed">
          <p className="text-lead text-ink short:text-body">{REPLY.notAllowedDetail}</p>
          <div>
            <Button variant="secondary" size="md" wide={false} onClick={startOver}>
              {ONWARD}
            </Button>
          </div>
        </div>
      ) : reply.kind === "not_yet" ? (
        // A website with no way to do it yet (2026-11-13): AI first, then a
        // helper. "Show me once" opens on this website's address.
        <div className="flex flex-col gap-4" data-testid="not-yet">
          <p className="text-lead text-ink short:text-body">{REPLY.notYetDetail}</p>
          <div className="flex flex-wrap items-center gap-4">
            <Button size="md" wide={false} data-testid="show-me-once"
                    onClick={() => setTeachOpen(true, reply.site)}>
              {REPLY.showMeOnce}
            </Button>
            <Button variant="secondary" size="md" wide={false} onClick={startOver}>
              {ONWARD}
            </Button>
          </div>
        </div>
      ) : reply.kind === "clarify" ? (
        <div className="flex flex-col gap-3">
          {reply.flows.map((flow) => (
            <ChoiceCard key={flow} icon={<FlowIcon flow={flow} />}
                        onClick={() => startTask(reply.goal, flow)}>
              {WHICH[flow]}
            </ChoiceCard>
          ))}
        </div>
      ) : reply.kind === "unsupported" ? (
        <>
        {/* With the list of websites, the lead-in says a website can be named
            (2026-11-13). In place of a sentence of its own, which put "Start"
            off the bottom at 100% and 150%. */}
        <Section lead={sites.length > 0 ? REPLY.canDoOrWhere : REPLY.canDo}>
          {reply.flows.map((flow) => (
            <ChoiceCard key={flow} icon={<FlowIcon flow={flow} />}
                        onClick={() => startTask(FLOWS[flow], flow)}>
              {FLOWS[flow]}
            </ChoiceCard>
          ))}
        </Section>
        </>
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

      {/* In a short window the box's lead-in goes, as on the home screen:
          the heading above has just asked, and it keeps it as its name. */}
      <AskBox lead={HOME.askHeading} leadWhenShort={false} />
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
    <div className="flex flex-col items-center gap-5 pt-20 text-center">
      <h1 className="text-display font-semibold tracking-[-0.015em] text-ink">
        {presence(situation)}
      </h1>
      {goal && <p className="max-w-[700px] text-lead text-soft">{goal}</p>}
    </div>
  );
}

/* ----------------------------------------------------------------- step */

function Step({ index }: { index: number }) {
  const { step: current, state, level, respond, answered } = useStore();
  // Only its own step (2026-10-16). A screen on its way out kept rendering
  // whatever step was current — the next one — with its old boxes still
  // folding away, so its buttons stood where the arriving screen's were not.
  const step = current && current.step_index === index ? current : null;
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
  // step, every ending's button
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
  // Not on a final screen, which keeps its own layout at every level, nor on
  // a helper's read-back (2026-11-04), which does the same.
  useOverflowGuard(measured, { level, active: Boolean(step) && !step?.final
                                              && !step?.routine });

  if (!shown) return null;

  return (
    <div ref={measured}>
      <Card className="px-12 py-10 short:py-7">
        {shown.final ? (
          // The final screen before a change (2026-10-16): its own layout,
          // whatever the level, so nothing about what will happen folds away.
          <FinalCheck step={shown} answered={answered || !step}
                      onAction={(actionId) => respond(actionId, values)} />
        ) : shown.routine ? (
          // What a helper showed, read back before it is kept (2026-11-04).
          <ReadBack step={shown} values={values} answered={answered || !step}
                    onChange={(fieldId, value) =>
                      setValues((current) => ({ ...current, [fieldId]: value }))}
                    onAction={(actionId) => respond(actionId, values)} />
        ) : (
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
        )}
      </Card>
      {/* The level dots and "What are you doing?" share one row under the
          card: at this type size, stacked, they pushed a step with a field
          past the bottom of the window. "What are you doing?" is the one way
          to see the page during a task (2026-10-16): it opens the close-up,
          with the whole page inside it. "Show the real page" beside it was a
          second way to the same page, and went. */}
      {/* Not under a helper's read-back (2026-11-04): it is not a step of a
          task, and with this row it did not fit a 606px window. */}
      {!shown.routine && (
        <div className="mt-8 flex flex-wrap items-center justify-between gap-4 short:mt-4">
          <TrustControl />
          <LevelControl />
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------- checklist */

/**
 * What SIMBA is doing by itself, once the person has decided (2026-10-14).
 *
 * The safe mechanical moves — filling in the form, opening the calendar,
 * searching — used to be a screen each, with a button to press for each.
 * Now they run, and each is one line here, in the backend's plain words. One
 * button, Pause, which stops SIMBA before its next move. Anything that is a
 * real choice, that went wrong, or that would pay, book, register or change
 * a record still asks.
 *
 * Drawn as a path since 2026-11-10: a dot for each move, joined by a line,
 * done ones filled and ticked, the one being done larger with "Doing this
 * now" beside it, and those to come empty, the line to them dashed. Still an
 * ordered list, the one being done marked as the current step, so a screen
 * reader reads it as it did. At the simplest level, the least: the move
 * being done and how many are still to come.
 */
function Checklist() {
  const { checklist, coming, pausing, pause, level, livePreview } = useStore();
  const reduce = useReducedMotion() ?? false;
  const simplest = level === 3;
  const at = checklist.length - 1;
  const rows: { key: string; label: string; state: "done" | "now" | "to come" }[] = [
    ...checklist.map((row, index) => ({
      key: `row-${row.index}`, label: row.label,
      state: index < at ? ("done" as const) : ("now" as const) })),
    ...coming.map((label, index) => ({ key: `coming-${index}-${label}`, label,
                                       state: "to come" as const })),
  ];
  const shown = simplest ? rows.filter((row) => row.state === "now") : rows;
  return (
    <Card className="px-12 py-10 short:py-7">
      <div className="flex flex-col gap-6 short:gap-4" data-testid="checklist">
        <TopLine step={null} stages full answered />
        <h1 className="text-heading font-semibold tracking-[-0.015em] text-ink short:text-title">
          {CHECKLIST.heading}
        </h1>
        <div className="flex items-start gap-8">
        <div className="flex min-w-0 flex-1 flex-col gap-3 short:gap-2">
          <ol className="flex flex-col gap-3 short:gap-2" aria-live="polite"
              data-testid="checklist-lines" data-level={level}>
            {shown.map((row, index) => {
              const done = row.state === "done";
              const now = row.state === "now";
              return (
                <li key={row.key} className="relative flex items-center gap-4 text-lead"
                    data-state={row.state} aria-current={now ? "step" : undefined}>
                  {/* The path to the next dot: solid where it has been, dashed
                      where it has still to go. Under the dots, which are solid. */}
                  {index < shown.length - 1 && (
                    <span aria-hidden data-testid="journey-path"
                          className={`absolute top-1/2 h-[calc(100%+12px)] short:h-[calc(100%+8px)]
                                      ${done ? "left-[20.5px] border-l-[3px] border-accent"
                                             : "left-[21px] border-l-2 border-dashed border-edge"}`} />
                  )}
                  <span className="relative z-[1] flex w-11 shrink-0 justify-center" aria-hidden>
                    {done ? (
                      <span className="flex h-9 w-9 items-center justify-center rounded-full
                                       bg-accent text-accent-ink">
                        <CheckIcon size={20} />
                      </span>
                    ) : now ? (
                      // Larger, with a pale ring round it, and grown into
                      // place when it arrives: once, small and slow, and not
                      // at all under reduced motion.
                      <motion.span key={row.key} data-testid="journey-now"
                                   initial={reduce ? false : { scale: 0.6, opacity: 0 }}
                                   animate={{ scale: 1, opacity: 1 }}
                                   transition={{ duration: 0.4, ease: EASE }}
                                   className="flex h-11 w-11 items-center justify-center
                                              rounded-full border-[3px] border-accent bg-surface
                                              shadow-[0_0_0_5px_var(--tint)]">
                        <span className="h-3.5 w-3.5 rounded-full bg-accent" />
                      </motion.span>
                    ) : (
                      <span className="h-9 w-9 rounded-full border-2 border-dashed border-edge
                                       bg-surface" />
                    )}
                  </span>
                  {now ? (
                    // Said, not only shown: where the person is, in the words
                    // a screen reader always read here. Placed after the words
                    // on screen, read before them.
                    <span className="order-last shrink-0 rounded-full bg-tint px-3
                                     py-0.5 text-caption font-medium text-accent"
                          data-testid="journey-here">
                      {CHECKLIST.now}
                    </span>
                  ) : (
                    <span className="sr-only">{done ? CHECKLIST.done : CHECKLIST.next}</span>
                  )}
                  {/* Softer, never fainter than 4.5:1 (`test_contrast.py`). */}
                  <span className={now ? "font-semibold text-ink" : "text-soft"}>{row.label}</span>
                </li>
              );
            })}
          </ol>
          {simplest && coming.length > 0 && (
            <p className="pl-[60px] text-body text-soft" data-testid="journey-left">
              {CHECKLIST.left(coming.length)}
            </p>
          )}
        </div>
        {/* The real page, small, as SIMBA works (2026-11-14): the latest
            picture the backend sent. Not at the simplest level, which shows
            the one move being made and nothing else. */}
        {!simplest && livePreview && (
          <figure className="flex w-[300px] shrink-0 flex-col gap-2 short:w-[240px]"
                  data-testid="live-page">
            <img src={`data:image/png;base64,${livePreview}`} alt=""
                 className="aspect-[16/10] w-full rounded-lg border border-edge object-cover
                            object-top shadow-press" />
            <figcaption className="text-caption text-soft">{SITES.livePage}</figcaption>
          </figure>
        )}
        </div>
        <div>
          <Button variant="secondary" size="md" wide={false} onClick={pause} disabled={pausing}>
            <span data-icon="pause"><PauseIcon size={24} /></span>
            {pausing ? CHECKLIST.pausing : CHECKLIST.pause}
          </Button>
        </div>
      </div>
    </Card>
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
 * One action, the same on every ending: "Back to start" (2026-10-16). Until
 * then there were two here, "I'm done" and "Do something else", and both led
 * to the home screen.
 */
/** Above an answer (2026-11-14): the website it came from, by its icon and
 *  the name the person knows it by. Nothing when it cannot be told. */
function AnswerSite() {
  const site = useStore((state) => state.taskSite);
  if (!site) return null;
  return (
    <p className="mb-4 flex items-center gap-3 short:mb-2" data-testid="answer-site">
      <SiteIcon address={site.address} name={site.name} genre={site.genre} size={36} />
      <span className="text-small font-medium text-soft">{SITES.from(site.name)}</span>
    </p>
  );
}

function Completed() {
  const { completed, task, startOver, takeOffer, status, keepAnswer, keepTile,
          declineKeep } = useStore();
  // The offer is there only while the run waiting for it is (2026-10-17): a
  // run left on its closing screen closes itself after a while
  // (`loop.OFFER_IDLE_S`), and a press then would go nowhere.
  const offer = status === "open" ? completed?.offer : null;
  const findings = completed?.findings ?? [];
  // One plain sentence saying what the result means, written by the backend
  // from the page's own values (`voice.explain_*`). This screen writes none of
  // its own: there is nothing in `copy.ts` for it because every word of it is
  // the page's or `voice.py`'s, and `test_copy.py` holds those to the same
  // rules. Absent, the lead-in "Here's what I found" is there instead.
  const explanation = completed?.explanation ?? null;
  const said = useRef<HTMLParagraphElement>(null);
  const lines = useLines(said);
  const short = useShortWindow();
  const screen = useRef<HTMLDivElement>(null);
  const dropped = useFitByDropping(screen);

  return (
    <div ref={screen} className="flex flex-col gap-8 short:gap-5">
      {completed?.confirmation ? (
        // A change the site has confirmed (2026-10-16): said done, in the
        // site's own words, with what it gave back.
        <ChangeDone />
      ) : findings.length > 0 ? (
        <Card className="px-12 py-12 short:py-8">
          <AnswerSite />
          {/* The sentence, when there is one, in the lead-in's place: it
              says what the lead-in says and more, and both together were the
              line that kept nine results off a 606px window (2026-10-05). */}
          {/* What the results are for: the journey the person agreed, not
              anything the page said (2026-10-14). */}
          {completed?.heading && (
            <p className="mb-2 text-title font-semibold tracking-[-0.01em] text-ink
                          short:text-lead" data-testid="heading">
              {completed.heading}
            </p>
          )}
          {explanation ? (
            <p ref={said}
               className="mb-6 text-lead font-medium text-ink short:mb-4 short:text-body"
               data-testid="explanation">
              {explanation}
            </p>
          ) : (
            <p className="mb-6 text-small font-medium text-soft short:mb-4">{ENDING.withAnswer}</p>
          )}
          {/* One result fewer in a short window for the last line, as for a
              sentence's second line: with it, nine results put the buttons
              off a 606px window (2026-10-16). */}
          <Findings findings={findings} size={TYPE.hero}
                    less={Math.max(0, lines - 1) + dropped}
                    footer={short && Boolean(completed?.scope || completed?.proof
                                             || completed?.proof_note)} />
          {/* The answer's footer (2026-10-16): the way to see it on the real
              page, and what was done and what was not — one row, so nine
              results still leave the way onward on a 606px window. */}
          {(completed?.scope || completed?.proof || completed?.proof_note) && (
            <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-3 short:mt-4">
              <ProofLine />
              {completed?.scope && (
                <p className="min-w-0 flex-1 basis-80 text-body text-soft" data-testid="scope">
                  {completed.scope}
                </p>
              )}
            </div>
          )}
        </Card>
      ) : (
        <div className="flex flex-col items-start gap-5 short:gap-3">
          {/* The mark beside the heading, not above it (2026-10-16): with the
              portal's caveat quoted under its confirmation, the stacked
              screen scrolled a 606px window. */}
          <div className="flex items-center gap-5">
            <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full
                             bg-tint text-accent" aria-hidden>
              <CheckIcon size={34} />
            </span>
            <h1 className="text-display font-semibold tracking-[-0.015em] text-ink">
              {ENDING.withoutAnswer}
            </h1>
          </div>
          {/* What happened, when the page said; otherwise what was asked for
              — unless the last line says what changed. */}
          {(explanation || !completed?.scope) && (
            <p className="text-lead text-soft"
               data-testid={explanation ? "explanation" : undefined}>
              {explanation ?? task?.goal}
            </p>
          )}
          {completed?.scope && (
            <p className="text-lead text-ink" data-testid="scope">{completed.scope}</p>
          )}
          <ProofLine />
        </div>
      )}

      {/* Once, the offer to keep this task on the home screen (2026-10-18):
          one quiet line, so the answer above keeps its room. Gone once
          answered, or when the run waiting for the answer has closed. */}
      {completed?.keep && keepAnswer === "kept" && (
        <p className="text-body text-soft" data-testid="kept" role="status">
          {TILES.kept(completed.keep.label)}
        </p>
      )}
      {completed?.keep && keepAnswer === null && status === "open" && (
        <div className="flex items-center gap-3 rounded-lg bg-tint px-5 py-2 short:py-1"
             data-testid="keep">
          <p className="min-w-0 flex-1 text-body text-ink">
            {TILES.keepAsk(completed.keep.label)}
          </p>
          <Button variant="secondary" size="md" wide={false} onClick={keepTile}
                  data-testid="keep-it">
            {TILES.keep}
          </Button>
          <Button variant="quiet" size="md" wide={false} onClick={declineKeep}>
            {TILES.notNow}
          </Button>
        </div>
      )}

      {/* One way on (2026-10-16). "I'm done" and "Do something else" sat
          here side by side and both went home. On our replicas, what can
          follow the answer — "Book one of these", "Pay this bill" — sits
          beside it, quieter: someone who wanted only the answer presses
          nothing more. */}
      {offer ? (
        <div className="flex flex-row gap-3" data-testid="onward">
          <Button className="flex-1" onClick={startOver}>{STOPPED.again}</Button>
          <Button className="flex-1" variant="secondary" onClick={takeOffer}
                  data-testid="offer">
            {offer.label}
          </Button>
        </div>
      ) : (
        <OnwardButton onClick={startOver} />
      )}
    </div>
  );
}

/**
 * The closing screen for a change the site has confirmed (2026-10-16): a
 * booking, a payment, a registration. "That's done." is said only here, and
 * only with the site's confirmation on the page (`task.completed.confirmation`,
 * which the backend sends with nothing less). Then what was done, the site's
 * own words quoted, what it gave back by its own names — the booking number,
 * the seat, the receipt — what it says against it, and the page itself.
 */
function ChangeDone() {
  const { completed } = useStore();
  const receipt = completed?.findings ?? [];
  // When the site qualifies what it confirmed — "not final until fees are
  // paid" — the screen does not say "That's done." (2026-10-16). It says what
  // the site confirmed, and, straight under it, what the site says against
  // it: "You're registered for CS-401. The portal says it isn't final until
  // tuition and fees are paid, or a payment plan is in place." A booking or a
  // payment on a practice copy is said the same way (2026-10-17): "Booked on
  // the practice site." over "Booking number PR-482193. This was a practice
  // copy, so no real ticket was booked and no money was taken." Both are the
  // backend's words (`heading`, `caveat`).
  const qualified = Boolean(completed?.heading && completed?.caveat);
  return (
    <div className="flex flex-col items-start gap-5 short:gap-3" data-testid="change-done">
      <div className="flex items-center gap-5">
        <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full
                         bg-tint text-accent" aria-hidden>
          <CheckIcon size={34} />
        </span>
        <h1 className="text-display font-semibold tracking-[-0.015em] text-ink
                       short:text-heading" data-testid="done-heading">
          {qualified ? completed?.heading : ENDING.withoutAnswer}
        </h1>
      </div>
      {qualified ? (
        <p className="text-lead font-medium text-ink" data-testid="caveat">{completed?.caveat}</p>
      ) : completed?.scope && (
        <p className="text-lead text-ink" data-testid="scope">{completed.scope}</p>
      )}
      <p className="border-l-4 border-accent pl-5 text-body text-ink" data-testid="confirmation">
        {unbroken(completed?.confirmation ?? "")}
      </p>
      {receipt.length > 0 && (
        <dl className="grid w-full grid-cols-2 gap-x-8 gap-y-2 rounded-lg bg-tint px-6 py-4
                       short:gap-y-1 short:py-3" data-testid="receipt">
          {receipt.map((finding) => (
            <div key={finding.label} className="flex min-w-0 items-baseline gap-3">
              <dt className="w-36 shrink-0 text-caption text-soft">{finding.label}</dt>
              <dd className="min-w-0 text-body font-semibold text-ink tabular-nums">
                {unbroken(finding.values?.[0] ?? finding.value)}
              </dd>
            </div>
          ))}
        </dl>
      )}
      {/* What the site says against it, in its own words: never more than
          the site says (2026-10-16). */}
      {completed?.caveat && !qualified && (
        <p className="border-l-4 border-line pl-5 text-body text-ink" data-testid="caveat">
          {completed.caveat}
        </p>
      )}
      <ProofLine />
    </div>
  );
}

/** The most results the closing screen gives up to fit, one at a time. */
const MOST_DROPPED = 8;

/**
 * How many more results the closing screen gives up so it fits the window,
 * found by measuring it (2026-10-16). The counts in `Findings` and `Tickets`
 * assume a result is one line; on the live site a train arriving the next day
 * wraps its ticket onto two, and nine of them put the way on 179px below a
 * 1280x800 window. Measured from layout (`offsetTop`, `offsetHeight`), which
 * the screen's entrance transform and the screen fading out beside it do not
 * move, after every render until it fits.
 */
function useFitByDropping(ref: React.RefObject<HTMLElement>): number {
  const [dropped, setDropped] = useState(0);
  useLayoutEffect(() => {
    const element = ref.current;
    if (element === null || dropped >= MOST_DROPPED) return;
    let top = 0;
    for (let at: HTMLElement | null = element; at; at = at.offsetParent as HTMLElement | null) {
      top += at.offsetTop;
    }
    const canvas = element.closest(".simba-canvas");
    const padding = canvas ? parseFloat(getComputedStyle(canvas).paddingBottom) || 0 : 0;
    if (top + element.offsetHeight + padding > window.innerHeight) setDropped(dropped + 1);
  });
  return dropped;
}

/**
 * A sentence with every code in it — a word with a digit, REG-10301-2026 —
 * kept on one line (2026-10-16): broken at its hyphen, a confirmation number
 * read as two.
 */
function unbroken(sentence: string) {
  return sentence.split(/(\S*\d\S*)/).map((part, index) =>
    index % 2 ? <span key={index} className="whitespace-nowrap">{part}</span> : part);
}

/**
 * The way to see the answer on the real page (2026-10-16), or, when the
 * backend could not take that picture, why not — in its words. Never a
 * picture from earlier in the task in its place.
 */
function ProofLine() {
  const { completed, openProof } = useStore();
  if (completed?.proof) {
    return (
      <Button variant="secondary" size="md" wide={false} onClick={openProof}>
        <PageIcon />
        {PROOF.see}
      </Button>
    );
  }
  if (completed?.proof_note) {
    return (
      <p className="text-body text-soft" data-testid="proof-note">
        {completed.proof_note}
      </p>
    );
  }
  return null;
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
export function Findings({ findings, size, less = 0, footer = false }: {
  findings: Finding[]; size: number; less?: number;
  /** A footer under the answer in a short window (2026-10-16): the way to
   *  see it on the real page, and what was not done. It costs a list two
   *  of its lines, and the tickets one. */
  footer?: boolean;
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
  const shown = Math.max(1, Math.min(count, LISTED - apart.length - less - (footer ? 2 : 0)));
  const rows = Array.from({ length: shown }, (_, row) =>
    findings.flatMap((_, index) => !onLine(index) ? []
      : [byRows ? sent[row][index] ?? "" : lists[index][row]])
      .filter(Boolean)
      .join(", "));
  // 54px for a few; past four, the size of a step's instruction.
  const rowSize = count > 4 ? TYPE.title : Math.round(size * 0.75);

  if (byRows) {
    return (
      <Tickets findings={findings} rows={sent} onLine={onLine} apart={apart}
               less={less + (footer ? 1 : 0)} />
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

/** How many results are shown before the rest are counted: fewer in a short
 *  window, where each takes the same height. */
const TICKETS = { full: 5, short: 3 };

/**
 * Results that came as whole rows, one ticket each (2026-10-07; one to a row
 * since 2026-10-14).
 *
 * The first cell is the result — a train's number — large. The rest follow
 * in the page's own words, each under its own name: "Leaves 08:04", "Arrives
 * 06:20", "Journey 22 h 16 min" — the live site prints both times in one
 * cell, and the backend reads them apart (`Answer.part`); a page that prints
 * one gives an empty "Arrives", which is left out, not worked out. The line
 * that used to name the columns, "Train, Journey", is gone: each value now
 * says what it is. The fastest is marked where the times can be read, and is
 * never among those counted. Each extra line the sentence above takes, and
 * each detail that is not on the tickets, gives up one ticket.
 */
function Tickets({ findings, rows, onLine, apart, less }: {
  findings: Finding[]; rows: string[][]; onLine: (index: number) => boolean;
  apart: Finding[]; less: number;
}) {
  const short = useShortWindow();
  const count = rows.length;
  const columns = findings.flatMap((_, index) => (onLine(index) ? [index] : []));
  const room = short ? TICKETS.short : TICKETS.full;
  const shown = Math.min(count, Math.max(1, room - apart.length - less));
  const fastest = fastestRows(rows);
  // The rows shown, in the page's order — and when the fastest is not among
  // them, it takes the last place, so the one marked is never in "and N more".
  const picked = Array.from({ length: shown }, (_, index) => index);
  const best = [...fastest][0];
  if (best !== undefined && !picked.some((index) => fastest.has(index))) {
    picked[picked.length - 1] = best;
  }

  return (
    <div className="flex flex-col gap-2" data-testid="findings" data-shape="tickets">
      <ul className="flex flex-col gap-2">
        {picked.map((index) => {
          const row = rows[index];
          const [first, ...rest] = columns.map((column) => row[column] ?? "");
          const named = rest.map((value, at) => ({ value, name: findings[columns[at + 1]].label }))
            .filter((cell) => cell.value);
          const quickest = fastest.has(index);
          return (
            <li key={index}
                data-testid="ticket"
                data-fastest={quickest ? "true" : undefined}
                // Its cells wrap onto a second line rather than run past the
                // column (2026-10-16): on the live site "06:20, next day", a
                // 22-hour journey and "Fastest" pushed the card 112px wider
                // than the buttons under it.
                className={`flex flex-wrap items-center gap-x-6 gap-y-1 rounded-lg border-2
                            bg-canvas px-5 py-2 short:py-1.5
                            ${quickest ? "border-accent" : "border-line"}`}>
              <span className="w-28 shrink-0 font-semibold leading-[1.1] tracking-[-0.02em]
                               text-ink" style={{ fontSize: TYPE.title }}>
                {first}
              </span>
              {named.map((cell) => (
                // One line, the name quietly before its value: under it, each
                // ticket was 70px and six put the way on off a 800px window.
                <span key={cell.name} className="flex items-baseline gap-2 whitespace-nowrap"
                      data-testid="ticket-cell">
                  <span className="text-caption text-soft">{cell.name}</span>
                  {/* The interface's own face, with figures of one width so
                      times line up from ticket to ticket (2026-10-15). Its
                      zero is slashed in every setting: that is the face's
                      way of never being read as O. */}
                  <span className="text-body font-semibold text-ink tabular-nums">
                    {cell.value}
                  </span>
                </span>
              ))}
              {quickest && (
                <span className="ml-auto shrink-0 rounded-full bg-accent px-3 py-0.5
                                 text-caption font-semibold text-accent-ink">
                  {ENDING.fastest}
                </span>
              )}
            </li>
          );
        })}
      </ul>
      {count > shown && (
        <p className="text-body font-medium text-soft">{ENDING.more(count - shown)}</p>
      )}
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
          <AlertIcon size={34} />
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
  const { help, startOver, setTeachOpen } = useStore();
  // AI first, then teach (2026-11-13): when the AI planner could not do a
  // goal on a website, a helper can show SIMBA there, from here.
  const teachSite = help?.teach_site;
  return (
    <div className="flex flex-col gap-8 short:gap-5">
      <Card tone="stuck" className="px-12 py-10 short:py-7">
        <StuckNote reason={help?.reason} suggestion={help?.suggestion}
                   unconfirmed={help?.unconfirmed ?? false} />
      </Card>
      {teachSite ? (
        <div className="flex flex-wrap items-center gap-4">
          <Button size="md" wide={false} data-testid="stuck-show-me-once"
                  onClick={() => { startOver(); setTeachOpen(true, teachSite); }}>
            {REPLY.showMeOnce}
          </Button>
          <OnwardButton onClick={startOver} />
        </div>
      ) : (
        <OnwardButton onClick={startOver} />
      )}
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

/**
 * "Don't" on a final screen (2026-10-16): the person decided, nothing was
 * done, and the screen says so calmly — the stop screen's quiet mark, not the
 * warm colour of something gone wrong.
 */
function NothingChanged() {
  const { startOver } = useStore();
  return (
    <div className="flex flex-col gap-8 short:gap-5" data-testid="nothing-changed">
      <div className="flex flex-col items-start gap-5">
        <span className="flex h-16 w-16 items-center justify-center rounded-full bg-sunk
                         text-soft" aria-hidden>
          <CheckIcon size={34} />
        </span>
        <h1 className="text-display font-semibold tracking-[-0.015em] text-ink">
          {FINAL.notDone}
        </h1>
        <p className="text-lead text-ink">{FINAL.nothingChanged}</p>
      </div>
      <OnwardButton onClick={startOver} />
    </div>
  );
}

/** The one way onward from a screen that has ended. Same words, same place. */
function OnwardButton({ onClick }: { onClick: () => void }) {
  return <Button onClick={onClick}>{STOPPED.again}</Button>;
}
