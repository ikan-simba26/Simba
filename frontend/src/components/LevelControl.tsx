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

import { NOTICE } from "../copy";
import { useStore } from "../store";

const EASE = [0.22, 0.61, 0.36, 1] as const;
const LEVELS: Level[] = [1, 2, 3];
const NOTICE_MS = 8000;

export function LevelControl() {
  const { level, levelLocked, chooseLevel, unlockLevel } = useStore();

  return (
    <motion.div
      layout
      transition={{ duration: 0.35, ease: EASE }}
      className="mt-14 flex items-center justify-center gap-3 opacity-40
                 transition-opacity duration-300 hover:opacity-100"
    >
      {LEVELS.map((option) => (
        <button
          key={option}
          type="button"
          onClick={() => chooseLevel(option)}
          aria-label={`Show ${option === 1 ? "more" : option === 3 ? "less" : "the usual amount"}`}
          aria-pressed={level === option}
          className="p-2"
        >
          <motion.span
            className="block rounded-full"
            animate={{
              width: level === option ? 22 : 8,
              height: 8,
              backgroundColor: level === option ? "#d9a44e" : "#33291f",
            }}
            transition={{ duration: 0.35, ease: EASE }}
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
            transition={{ duration: 0.35, ease: EASE }}
            className="overflow-hidden whitespace-nowrap pl-2 text-[13px] text-muted
                       underline underline-offset-4 hover:text-ink"
          >
            let it choose
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
          transition={{ duration: 0.35, ease: EASE }}
          className="mb-6 flex items-center justify-between gap-4 rounded-lg
                     border border-line bg-raised px-4 py-3 text-[14px] text-muted"
          data-transient
        >
          <span>{levelNotice.because}.</span>
          <button
            type="button"
            onClick={dismissLevelNotice}
            aria-label={NOTICE.dismiss}
            className="shrink-0 px-2 text-muted transition-colors duration-300 hover:text-ink"
          >
            &times;
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
