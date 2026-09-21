/**
 * The user's own hand on the level, and the notice when something else moves it.
 *
 * Both are deliberately quiet. The control is three dots at the foot of the
 * column — visible if you look for it, ignorable if you do not. The notice
 * exists because the interface must never reshape under someone without
 * saying so; an overlay that silently rearranges itself is exactly the thing
 * this project is supposed to be the opposite of.
 */

import { AnimatePresence, motion } from "framer-motion";
import { useEffect } from "react";

import type { Level } from "@shared/schema";

import { LEVEL, levelNotice as noticeFor } from "../copy";
import { ARRIVE, EASE, MOTION } from "../design";
import { useStore } from "../store";
import { DismissButton, InfoIcon, NOTICE_CLASS } from "./ui";

const LEVELS: Level[] = [1, 2, 3];
const NOTICE_MS = 8000;

export function LevelControl() {
  const { level, levelLocked, chooseLevel, unlockLevel } = useStore();

  return (
    <motion.div
      layout
      transition={{ duration: MOTION.fold, ease: EASE }}
      // Quiet until reached for, as before — but not so faint that the dots
      // cannot be found: 0.4 put the resting dot below any contrast rule for
      // a control. The colours come from the theme; they were the dark
      // theme's hex values, written in.
      className="flex items-center justify-center gap-2 opacity-70
                 transition-opacity duration-300 hover:opacity-100 focus-within:opacity-100"
    >
      {LEVELS.map((option) => (
        <button
          key={option}
          type="button"
          onClick={() => chooseLevel(option)}
          aria-label={LEVEL.choose(option)}
          aria-pressed={level === option}
          className="rounded-full p-2.5"
        >
          <motion.span
            className={`block rounded-full transition-colors duration-300 ${
              level === option ? "bg-accent" : "bg-line"
            }`}
            animate={{ width: level === option ? 30 : 11, height: 11 }}
            transition={{ duration: MOTION.fold, ease: EASE }}
          />
        </button>
      ))}

      <AnimatePresence initial={false}>
        {levelLocked && (
          <motion.button
            type="button"
            onClick={unlockLevel}
            initial={{ opacity: 0, width: 0 }}
            animate={{ opacity: 1, width: "auto" }}
            exit={{ opacity: 0, width: 0 }}
            transition={{ duration: MOTION.fold, ease: EASE }}
            className="overflow-hidden whitespace-nowrap pl-2 text-caption text-soft
                       underline underline-offset-4 hover:text-ink"
          >
            {LEVEL.unlock}
          </motion.button>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export function LevelNotice() {
  const { levelNotice, dismissLevelNotice } = useStore();

  // Say it, then get out of the way. It can also be dismissed by hand.
  useEffect(() => {
    if (!levelNotice) return;
    const timer = window.setTimeout(dismissLevelNotice, NOTICE_MS);
    return () => window.clearTimeout(timer);
  }, [levelNotice, dismissLevelNotice]);

  return (
    <AnimatePresence initial={false}>
      {levelNotice && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={ARRIVE}
          className={NOTICE_CLASS}
          data-transient
        >
          {/* The sentence comes from the direction alone. `because` says what
              moved the level and stays in the store: it used to be
              rendered here, which put "this step was too long to fit." —
              lower case, and with a word the reader has to be taught — on
              screen whenever the overflow guard fired. */}
          <span className="shrink-0 text-soft" aria-hidden>
            <InfoIcon />
          </span>
          <span className="flex-1">{noticeFor(levelNotice.from, levelNotice.to)}</span>
          <DismissButton onClick={dismissLevelNotice} />
        </motion.div>
      )}
    </AnimatePresence>
  );
}
