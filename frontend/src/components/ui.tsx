/**
 * The few pieces every screen is built from.
 *
 * A screen that needs a button, a card or an icon takes it from here, so a
 * button looks, moves and responds the same wherever it appears. Someone who
 * has learned what a pressable thing looks like on one screen should never
 * meet a different one on the next.
 */

import type { ReactNode } from "react";

import type { FlowName, StepKind } from "@shared/schema";

import { Shape } from "./Shape";

import { NOTICE, STATUS } from "../copy";

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
        // 80px, and 64 in a short window: still the largest thing to press.
        ? "min-h-20 short:min-h-16 rounded-lg px-9 text-lead font-semibold"
        : size === "fluid"
          ? "rounded-lg px-9 text-lead font-semibold"
          : "min-h-16 short:min-h-14 rounded-md px-7 text-body font-semibold";
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
      className="group flex w-full items-center gap-6 rounded-lg border border-line bg-surface
                 px-6 py-4 text-left shadow-press transition-[box-shadow,border-color,transform]
                 short:gap-5 short:py-3
                 duration-200 ease-[cubic-bezier(0.4,0,0.2,1)] hover:border-accent/50
                 hover:shadow-lift active:translate-y-px active:shadow-press"
    >
      <span
        className="flex h-14 w-14 shrink-0 items-center justify-center rounded-md bg-tint
                   text-accent short:h-12 short:w-12"
        aria-hidden
      >
        {icon}
      </span>
      {/* Two lines at most. A remembered goal is a whole sentence, and three of
          them wrapping onto a third line each would push the text box off a
          100% window (2026-09-30). The words are all still there — clamped,
          not cut — so a screen reader and the button's name read the lot. */}
      <span className="line-clamp-2 flex-1 text-lead font-medium text-ink short:text-body">
        {children}
      </span>
      <Arrow />
    </button>
  );
}

/* --------------------------------------------------------------- notices */

export function DismissButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={NOTICE.dismiss}
      className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-soft
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
      <Svg size={30}>
        <path d="M2 9.5 12 5l10 4.5-10 4.5L2 9.5Z" />
        <path d="M6 11.3V16c0 1.4 2.7 3 6 3s6-1.6 6-3v-4.7" />
      </Svg>
    );
  }
  if (flow === "billing") {
    return (
      <Svg size={30}>
        <path d="M13 2 5 13.5h6L10 22l8-11.5h-6L13 2Z" />
      </Svg>
    );
  }
  return (
    <Svg size={30}>
      <rect x="5" y="3" width="14" height="13" rx="3" />
      <path d="M5 10h14M9 20l-2 2M15 20l2 2M9 13h.01M15 13h.01" />
    </Svg>
  );
}

/** A remembered goal. */
export function AgainIcon() {
  return (
    <Svg size={30}>
      <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
      <path d="M3 3v5h5M12 7v5l3 2" />
    </Svg>
  );
}

export function Arrow() {
  return (
    <span className="text-soft transition-transform duration-200 group-hover:translate-x-0.5">
      <Svg size={28}>
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
    <Svg size={26}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5M12 8h.01" />
    </Svg>
  );
}

export function CloseIcon() {
  return (
    <Svg size={24}>
      <path d="M6 6l12 12M18 6 6 18" />
    </Svg>
  );
}

/** Looking at the real page. */
export function EyeIcon() {
  return (
    <Svg size={26}>
      <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" />
      <circle cx="12" cy="12" r="3" />
    </Svg>
  );
}

/** The real page itself: a browser window. Not the eye, which is "What are
 *  you doing?" beside it — two buttons with two jobs should not look alike. */
export function PageIcon() {
  return (
    <Svg size={26}>
      <rect x="3" y="4.5" width="18" height="15" rx="2.5" />
      <path d="M3 9h18M6.5 6.8h.01M9 6.8h.01" />
    </Svg>
  );
}

export function SpeechIcon() {
  return (
    <Svg size={30}>
      <path d="M4 5h16v11H9l-5 4V5Z" />
    </Svg>
  );
}

/**
 * What a step is about, as one shape beside it (2026-10-07): a calendar for a
 * day, a pin for a place, a list for choosing one of several, keys for
 * typing, a page for something to read, and a tick for agreeing to go ahead.
 * The step's sentence always says it too; the shape is for finding your place
 * at a glance, never the only way it is said.
 */
export function StepKindIcon({ kind, size = 36 }: { kind: StepKind; size?: number }) {
  switch (kind) {
    case "date":
      return (
        <Svg size={size}>
          <rect x="3.5" y="5" width="17" height="15.5" rx="3" />
          <path d="M3.5 10h17M8 3v4M16 3v4M8.5 14.5h.01M12 14.5h.01M15.5 14.5h.01" />
        </Svg>
      );
    case "place":
      return (
        <Svg size={size}>
          <path d="M12 21s-6.5-6-6.5-11.2a6.5 6.5 0 0 1 13 0C18.5 15 12 21 12 21Z" />
          <circle cx="12" cy="9.8" r="2.4" />
        </Svg>
      );
    case "choose":
      return (
        <Svg size={size}>
          <path d="M3.8 6.5 5.4 8l2.8-3M11 6.5h9.5M11 12h9.5M11 17.5h9.5" />
          <circle cx="6" cy="12" r="1.6" />
          <circle cx="6" cy="17.5" r="1.6" />
        </Svg>
      );
    case "type":
      return (
        <Svg size={size}>
          <rect x="2.5" y="6" width="19" height="12" rx="3" />
          <path d="M6.5 10h.01M10 10h.01M14 10h.01M17.5 10h.01M8 14h8" />
        </Svg>
      );
    case "read":
      return (
        <Svg size={size}>
          <path d="M7 3h7l5 5v13H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" />
          <path d="M14 3v5h5M9 13h7M9 17h5" />
        </Svg>
      );
    case "confirm":
      return (
        <Svg size={size}>
          <circle cx="12" cy="12" r="9" />
          <path d="M8 12.4 10.8 15 16 9.5" />
        </Svg>
      );
  }
}

/* -------------------------------------------------------------- presence */

export type PresenceMode = "ready" | "thinking" | "acting" | "waiting" | "stuck" | "done";

/**
 * The assistant, present on every screen, in one place, saying without words
 * what it is doing — and, since 2026-10-14, the one sign of SIMBA there is:
 * the 3D shape (`Shape`), where there used to be a dot and, beside it on the
 * home screen, the shape as well.
 *
 *   ready     still                             — here, nothing happening
 *   thinking  turning, slowly                   — working it out
 *   acting    turning, slowly                   — doing the thing now
 *   waiting   still                             — your turn
 *   stuck     still, in the warm colour         — it has stopped
 *   done      still, with a tick on its core    — finished
 *
 * Large on the home screen, where it is the first thing seen; small
 * everywhere else, where the step is the thing to look at. It moves only
 * while SIMBA is working, never under reduced motion, and never while the
 * window is not focused (`data-motion`, `main.tsx`).
 *
 * Wordless on screen on purpose: `copy.ts` gives `waiting` no sentence
 * because the step is the sentence. The state is named for a screen reader,
 * from `STATUS`, and announced when it changes.
 */
export function Presence({ mode, large = false }: { mode: PresenceMode; large?: boolean }) {
  const working = mode === "thinking" || mode === "acting";
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={STATUS[mode]}
      className={`relative flex items-center justify-center ${
        large ? "h-24 w-24 short:h-16 short:w-16" : "h-12 w-12"}`}
      data-presence={mode}
      data-size={large ? "large" : "small"}
    >
      <Shape className={large ? "h-24 w-24 short:h-16 short:w-16" : "h-10 w-10"}
             turning={working} stuck={mode === "stuck"} />
      {mode === "done" && (
        <span className="absolute inset-0 flex items-center justify-center text-accent-ink">
          <CheckIcon size={large ? 30 : 14} />
        </span>
      )}
    </div>
  );
}
