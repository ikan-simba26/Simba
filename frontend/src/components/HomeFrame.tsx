/**
 * The first screen's frame (2026-11-17, the home redesign, "Concept 2"): a top
 * bar with the logo on the left, the status pill in the middle and, on the
 * right, "For helpers: teach a task" as a proper button and the settings.
 * Under it, the screen itself, with room of its own.
 *
 * Until now "Teach a task" and "My bookings" were fixed in the window's top
 * right corner and, at 150%, drew over the greeting. In a bar of their own,
 * nothing can reach anything else: the three parts of the bar share one row
 * that cannot be narrower than they are.
 */

import type { ReactNode } from "react";

import { HOME } from "../copy";
import { usePresenceMode } from "../presenceMode";
import { useStore } from "../store";
import { BrandMark } from "./Brand";
import { StatusLine } from "./StatusLine";
import { GearIcon } from "./ui";

export function HomeFrame({ children }: { children: ReactNode }) {
  const setTeachOpen = useStore((state) => state.setTeachOpen);
  const openWelcome = useStore((state) => state.openWelcome);
  const mode = usePresenceMode();

  return (
    <div className="simba-canvas flex h-full min-h-0 flex-col bg-canvas" data-testid="home-frame">
      <header className="grid h-[76px] shrink-0 grid-cols-[1fr_auto_1fr] items-center gap-4 border-b
                         border-line bg-surface px-9 short:h-[60px] short:px-5"
              data-testid="home-bar">
        <div className="flex min-w-0 items-center">
          <BrandMark />
        </div>
        <StatusLine activity={mode} inline />
        <div className="flex min-w-0 items-center justify-end gap-3">
          <button type="button" onClick={() => setTeachOpen(true)} data-testid="teach-a-task"
                  className="min-h-12 truncate rounded-lg border-2 border-accent bg-surface px-5 text-small
                             font-semibold text-accent transition-colors hover:bg-tint short:min-h-11
                             short:px-4">
            {HOME.forHelpers}
          </button>
          <button type="button" onClick={openWelcome} aria-label={HOME.settings}
                  data-testid="change-settings"
                  className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg border
                             border-edge bg-surface text-ink transition-colors hover:bg-tint
                             short:h-11 short:w-11">
            <GearIcon />
          </button>
        </div>
      </header>
      <div className="flex min-h-0 flex-1 gap-7 px-9 pt-7 pb-5 short:gap-4 short:px-5 short:pt-4 short:pb-3">
        {children}
      </div>
    </div>
  );
}
