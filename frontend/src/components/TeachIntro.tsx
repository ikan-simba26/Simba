/**
 * The screen behind "Show me once" (2026-11-04), reached from "Change my
 * settings": who it is for — a helper — and what will happen, the website to
 * watch on, and a way to add a routine someone shared as a file.
 *
 * Nothing is watched until "Start watching". With the home screen's row of
 * three full, it says so and starts nothing.
 */

import { useRef, useState } from "react";

import { TEACH } from "../copy";
import { useStore } from "../store";
import { Button } from "./ui";

/** How many tiles the home screen's one row holds: the person's and the
 *  routines together (`tiles.MAX_TILES`). */
const ROW = 3;

/** An address as typed, made whole: "example.com" is https://example.com,
 *  and this computer's own address, where our practice sites are, is http. */
export function addressOf(typed: string): string | null {
  const text = typed.trim();
  if (!text) return null;
  const local = /^(localhost|127\.0\.0\.1)(:|\/|$)/i.test(text);
  const whole = /^https?:\/\//i.test(text) ? text : `${local ? "http" : "https"}://${text}`;
  try {
    const url = new URL(whole);
    return url.hostname.includes(".") || url.hostname === "localhost" ? url.href : null;
  } catch {
    return null;
  }
}

export function TeachIntro() {
  const { startTeaching, setTeachOpen, tiles, routines, importRoutine, fileNote,
          teachAddress } = useStore();
  // Offered on a website (2026-11-13), the box starts with its address.
  const [typed, setTyped] = useState(teachAddress ?? "");
  const file = useRef<HTMLInputElement>(null);
  const url = addressOf(typed);
  const full = tiles.length + routines.length >= ROW;
  const start = () => url && !full && startTeaching(url);

  return (
    <div className="flex min-h-[calc(100dvh-176px)] flex-col justify-center gap-6
                    short:min-h-[calc(100dvh-92px)] short:gap-4" data-testid="teach-intro">
      <div className="flex flex-col gap-3 short:gap-2">
        <h1 className="text-display font-semibold tracking-[-0.015em] text-ink short:text-heading">
          {TEACH.ask}
        </h1>
        <p className="text-lead text-ink short:text-body">{TEACH.detail}</p>
        <p className="text-body text-soft">{TEACH.how}</p>
      </div>
      {full ? (
        <p className="rounded-lg bg-tint px-5 py-3 text-body text-ink" role="status"
           data-testid="teach-full">
          {TEACH.noRoom}
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          <p className="text-small font-medium text-soft">{TEACH.where}</p>
          <div className="simba-field-frame flex items-center gap-4 rounded-xl py-2 pr-2 pl-6
                          shadow-card">
            <input value={typed} onChange={(event) => setTyped(event.target.value)}
                   onKeyDown={(event) => event.key === "Enter" && start()}
                   placeholder={TEACH.placeholder} aria-label={TEACH.where}
                   data-testid="teach-address"
                   className="min-w-0 flex-1 bg-transparent py-3 text-lead text-ink outline-none
                              placeholder:text-soft" />
            <Button size="md" wide={false} disabled={!url} onClick={start}
                    data-testid="teach-start">
              {TEACH.start}
            </Button>
          </div>
        </div>
      )}
      {fileNote && (
        <p className="text-body text-ink" role="status" data-testid="file-note">{fileNote}</p>
      )}
      <div className="flex items-center justify-between gap-4">
        <Button variant="quiet" size="md" wide={false} onClick={() => setTeachOpen(false)}
                data-testid="teach-back">
          {TEACH.back}
        </Button>
        {!full && (
          <Button variant="secondary" size="md" wide={false} data-testid="teach-from-file"
                  onClick={() => file.current?.click()}>
            {TEACH.fromFile}
          </Button>
        )}
        <input ref={file} type="file" accept=".json,application/json" className="hidden"
               data-testid="teach-file"
               onChange={async (event) => {
                 const chosen = event.target.files?.[0];
                 event.target.value = "";
                 if (chosen) importRoutine(await chosen.text());
               }} />
      </div>
    </div>
  );
}
