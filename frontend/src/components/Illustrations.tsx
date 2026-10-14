/**
 * One simple picture for each thing SIMBA can do, on the home screen's tiles
 * (2026-10-14). Original, drawn here: a few calm shapes in the accent and its
 * tint, no words, no faces, nothing to decode. Each is decoration — the
 * tile's words say what it is — so each is hidden from a screen reader.
 */

import type { FlowName } from "@shared/schema";

function Frame({ children }: { children: React.ReactNode }) {
  return (
    <svg viewBox="0 0 120 96" className="h-full w-full" fill="none" aria-hidden
         strokeLinecap="round" strokeLinejoin="round">
      {children}
    </svg>
  );
}

const TINT = "var(--tint)";
const ACCENT = "var(--accent)";
const SURFACE = "var(--surface)";

export function FlowIllustration({ flow }: { flow: FlowName }) {
  if (flow === "registration") {
    // A book standing open, and a cap resting above it.
    return (
      <Frame>
        <ellipse cx="60" cy="84" rx="40" ry="6" fill={TINT} />
        <path d="M24 40c12-6 24-6 36 2v40c-12-8-24-8-36-2V40Z" fill={SURFACE} stroke={ACCENT}
              strokeWidth="3" />
        <path d="M96 40c-12-6-24-6-36 2v40c12-8 24-8 36-2V40Z" fill={TINT} stroke={ACCENT}
              strokeWidth="3" />
        <path d="M60 10 92 22 60 34 28 22 60 10Z" fill={ACCENT} />
        <path d="M44 28v8c0 3 7 6 16 6s16-3 16-6v-8" stroke={ACCENT} strokeWidth="3" />
        <path d="M88 23v12" stroke={ACCENT} strokeWidth="3" />
      </Frame>
    );
  }
  if (flow === "billing") {
    // A bill, with its total, and a small bolt in a circle.
    return (
      <Frame>
        <ellipse cx="60" cy="86" rx="38" ry="6" fill={TINT} />
        <path d="M34 10h40l12 12v58H34V10Z" fill={SURFACE} stroke={ACCENT} strokeWidth="3" />
        <path d="M74 10v12h12" stroke={ACCENT} strokeWidth="3" />
        <path d="M44 34h22M44 44h30M44 54h18" stroke={ACCENT} strokeWidth="3" opacity="0.55" />
        <path d="M44 68h32" stroke={ACCENT} strokeWidth="4" />
        <circle cx="86" cy="66" r="15" fill={ACCENT} />
        <path d="M88 56 81 68h6l-2 9 8-12h-6l1-9Z" fill={SURFACE} />
      </Frame>
    );
  }
  // A train coming towards you along its rails.
  return (
    <Frame>
      <ellipse cx="60" cy="86" rx="42" ry="6" fill={TINT} />
      <path d="M40 92 50 72M80 92 70 72" stroke={ACCENT} strokeWidth="3" />
      <rect x="34" y="10" width="52" height="58" rx="14" fill={SURFACE} stroke={ACCENT}
            strokeWidth="3" />
      <rect x="42" y="20" width="36" height="20" rx="5" fill={TINT} stroke={ACCENT}
            strokeWidth="3" />
      <circle cx="47" cy="54" r="4" fill={ACCENT} />
      <circle cx="73" cy="54" r="4" fill={ACCENT} />
      <path d="M52 62h16" stroke={ACCENT} strokeWidth="3" />
    </Frame>
  );
}
