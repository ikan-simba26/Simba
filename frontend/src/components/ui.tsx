/**
 * The few pieces every screen is built from.
 *
 * A screen that needs a button, a card or an icon takes it from here, so a
 * button looks, moves and responds the same wherever it appears. Someone who
 * has learned what a pressable thing looks like on one screen should never
 * meet a different one on the next.
 */

import { motion } from "framer-motion";
import type { ReactNode } from "react";

import type { FlowName } from "@shared/schema";

import { NOTICE, STATUS } from "../copy";
import { EASE, MOTION } from "../design";

/* --------------------------------------------------------------- buttons */

export type ButtonVariant = "primary" | "secondary" | "danger" | "quiet";
/** `fluid` sets no height: for the step's buttons, whose height the level fold animates. */
export type ButtonSize = "lg" | "md" | "fluid";

/**
 * Every button's classes. Large, obviously pressable, and with a visible
 * answer to each thing a hand or a keyboard can do to it:
 *
 *   hover     the fill deepens (primary) or the surface sinks (secondary)
 *   focus     the one focus ring, from `index.css`
 *   pressed   it moves down a pixel and its shadow flattens — pressed in
 *   disabled  it fades and loses its shadow; it cannot look pressable
 *
 * No scale, no spring. The press is a pixel, because a button that grows or
 * bounces is asking to be looked at.
 */
export function buttonClass(variant: ButtonVariant, size: ButtonSize = "lg"): string {
  const base =
    "inline-flex items-center justify-center gap-3 select-none " +
    "transition-[background-color,border-color,box-shadow,color,transform] " +
    "duration-200 ease-[cubic-bezier(0.4,0,0.2,1)] " +
    "active:translate-y-px disabled:pointer-events-none";
  const sizing =
    variant === "quiet"
      ? "px-2 py-1 text-small"
      : size === "lg"
        ? "min-h-16 rounded-lg px-7 text-lead font-semibold"
        : size === "fluid"
          ? "rounded-lg px-7 text-lead font-semibold"
          : "min-h-14 rounded-md px-6 text-body font-semibold";
  const tone = {
    primary:
      "bg-accent text-accent-ink shadow-lift hover:bg-accent-hover " +
      "active:shadow-press disabled:opacity-45 disabled:shadow-none",
    secondary:
      "border border-line bg-surface text-ink shadow-press hover:border-soft/40 " +
      "hover:bg-sunk disabled:opacity-45",
    danger:
      "border border-stuck bg-surface text-stuck hover:bg-stuck-tint disabled:opacity-45",
    quiet:
      "rounded-md text-soft underline decoration-soft/40 underline-offset-[5px] " +
      "hover:text-ink hover:decoration-ink/60",
  }[variant];
  return `${base} ${sizing} ${tone}`;
}

export function Button({
  variant = "primary",
  size = "lg",
  wide = true,
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  wide?: boolean;
}) {
  return (
    <button
      type="button"
      className={`${buttonClass(variant, size)} ${wide && variant !== "quiet" ? "w-full" : ""} ${className}`}
      {...props}
    />
  );
}

/* ----------------------------------------------------------------- cards */

/** A raised surface. Soft depth, generous padding, rounded corners. */
export function Card({
  children,
  className = "",
  tone = "surface",
}: {
  children: ReactNode;
  className?: string;
  tone?: "surface" | "tint" | "stuck";
}) {
  const fill = { surface: "bg-surface", tint: "bg-tint", stuck: "bg-stuck-tint" }[tone];
  return <div className={`rounded-xl ${fill} shadow-card ${className}`}>{children}</div>;
}

/**
 * One thing to choose: an icon and one line. The home screen's three things
 * SIMBA can do, a remembered goal, and each answer to "which did you mean".
 */
export function ChoiceCard({
  icon,
  children,
  onClick,
}: {
  icon: ReactNode;
  children: ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex w-full items-center gap-5 rounded-lg border border-line bg-surface
                 px-5 py-4 text-left shadow-press transition-[box-shadow,border-color,transform]
                 duration-200 ease-[cubic-bezier(0.4,0,0.2,1)] hover:border-accent/50
                 hover:shadow-lift active:translate-y-px active:shadow-press"
    >
      <span
        className="flex h-12 w-12 shrink-0 items-center justify-center rounded-md bg-tint
                   text-accent"
        aria-hidden
      >
        {icon}
      </span>
      <span className="flex-1 text-lead font-medium text-ink">{children}</span>
      <Arrow />
    </button>
  );
}

/* --------------------------------------------------------------- notices */

/**
 * A change the person did not make, announced. Calm, raised, above the
 * column, and gone on its own: an icon, one sentence, and a way to dismiss it.
 * The outer element is the caller's, so it can carry its own motion and the
 * `data-transient` the overflow guard discounts.
 */
export const NOTICE_CLASS =
  "mb-6 flex items-center gap-3 rounded-lg border border-line bg-surface px-5 py-3 " +
  "text-small text-ink shadow-lift";

export function DismissButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={NOTICE.dismiss}
      className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-soft
                 transition-colors duration-200 hover:bg-sunk hover:text-ink"
    >
      <CloseIcon />
    </button>
  );
}

/* ----------------------------------------------------------------- icons */
/*
 * Simple, line-drawn, one weight, and never carrying words. Each is a shape a
 * person has seen before — a cap for a course, a bolt for electricity, a
 * train for trains — and never the only way something is said.
 */

function Svg({ children, size = 24 }: { children: ReactNode; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      {children}
    </svg>
  );
}

export function FlowIcon({ flow }: { flow: FlowName }) {
  if (flow === "registration") {
    return (
      <Svg>
        <path d="M2 9.5 12 5l10 4.5-10 4.5L2 9.5Z" />
        <path d="M6 11.3V16c0 1.4 2.7 3 6 3s6-1.6 6-3v-4.7" />
      </Svg>
    );
  }
  if (flow === "billing") {
    return (
      <Svg>
        <path d="M13 2 5 13.5h6L10 22l8-11.5h-6L13 2Z" />
      </Svg>
    );
  }
  return (
    <Svg>
      <rect x="5" y="3" width="14" height="13" rx="3" />
      <path d="M5 10h14M9 20l-2 2M15 20l2 2M9 13h.01M15 13h.01" />
    </Svg>
  );
}

/** A remembered goal. */
export function AgainIcon() {
  return (
    <Svg>
      <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
      <path d="M3 3v5h5M12 7v5l3 2" />
    </Svg>
  );
}

export function Arrow() {
  return (
    <span className="text-soft transition-transform duration-200 group-hover:translate-x-0.5">
      <Svg size={22}>
        <path d="M9 6l6 6-6 6" />
      </Svg>
    </span>
  );
}

export function CheckIcon({ size = 28 }: { size?: number }) {
  return (
    <Svg size={size}>
      <path d="M5 12.5 10 17l9-10" />
    </Svg>
  );
}

export function PauseIcon({ size = 28 }: { size?: number }) {
  return (
    <Svg size={size}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7.5v5M12 16h.01" />
    </Svg>
  );
}

export function InfoIcon() {
  return (
    <Svg size={20}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5M12 8h.01" />
    </Svg>
  );
}

export function CloseIcon() {
  return (
    <Svg size={20}>
      <path d="M6 6l12 12M18 6 6 18" />
    </Svg>
  );
}

export function SpeechIcon() {
  return (
    <Svg>
      <path d="M4 5h16v11H9l-5 4V5Z" />
    </Svg>
  );
}

/* -------------------------------------------------------------- presence */

export type PresenceMode = "ready" | "thinking" | "acting" | "waiting" | "stuck" | "done";

/**
 * The assistant, present on every screen, in one place, saying without words
 * what it is doing.
 *
 *   ready     a still dot                       — here, nothing happening
 *   thinking  the dot breathes, slowly          — working it out; nothing wanted
 *   acting    a thin arc circles it, slowly     — doing the thing now
 *   waiting   the dot is full, with a halo      — your turn
 *   stuck     the dot turns the warm colour     — it has stopped
 *   done      a still dot with a small tick     — finished
 *
 * Wordless on screen on purpose: `copy.ts` gives `waiting` no sentence
 * because the step is the sentence, and a second thing to read beside it is
 * the clutter this project removes. The state is named for a screen reader,
 * from `STATUS`, and announced when it changes.
 *
 * It replaces two earlier signals: a line crossing the top of the column
 * while acting, and a pulse that dimmed the whole column while thinking. The
 * pulse also dimmed the answer on the closing screen, because the backend
 * never leaves `thinking` after finishing — the one screen that exists to be
 * read was the one that faded in and out (EVALUATION.md, 2026-09-21).
 */
export function Presence({ mode }: { mode: PresenceMode }) {
  const colour = mode === "stuck" ? "bg-stuck" : "bg-accent";
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={STATUS[mode]}
      className="relative flex h-10 w-10 items-center justify-center"
      data-presence={mode}
    >
      {/* The halo: only when it is the person's turn. */}
      <motion.span
        className={`absolute inset-0 rounded-full ${colour}`}
        animate={{ opacity: mode === "waiting" ? 0.16 : 0, scale: mode === "waiting" ? 1 : 0.6 }}
        transition={{ duration: MOTION.base, ease: EASE }}
      />
      {/* The orbit: only while acting. */}
      <motion.svg
        className="absolute inset-0 text-accent"
        viewBox="0 0 40 40"
        animate={{ opacity: mode === "acting" ? 1 : 0, rotate: mode === "acting" ? 360 : 0 }}
        transition={
          mode === "acting"
            ? { opacity: { duration: MOTION.base, ease: EASE },
                rotate: { duration: MOTION.orbit, ease: "linear", repeat: Infinity } }
            : { duration: MOTION.base, ease: EASE }
        }
        aria-hidden
      >
        <circle cx="20" cy="20" r="17" fill="none" stroke="currentColor" strokeWidth="2"
                strokeLinecap="round" strokeDasharray="22 85" />
      </motion.svg>
      {/* The dot itself. Finished, it grows into a disc with a tick in it —
          the same mark, completed, rather than a second thing beside it. */}
      <motion.span
        className={`relative flex h-4 w-4 items-center justify-center rounded-full ${colour}`}
        animate={
          mode === "thinking"
            ? { scale: [1, 0.72, 1], opacity: [1, 0.6, 1] }
            : {
                scale: mode === "done" ? 1.75 : mode === "waiting" ? 1.15 : 1,
                opacity: mode === "ready" ? 0.7 : 1,
              }
        }
        transition={
          mode === "thinking"
            ? { duration: MOTION.breath, ease: "easeInOut", repeat: Infinity }
            : { duration: MOTION.base, ease: EASE }
        }
      >
        {mode === "done" && (
          <span className="text-accent-ink">
            <CheckIcon size={11} />
          </span>
        )}
      </motion.span>
    </div>
  );
}
