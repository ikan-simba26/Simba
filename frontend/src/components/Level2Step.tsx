/**
 * A step at level 2: the instruction, whatever it needs from you, and the
 * choices. Nothing else.
 *
 * `detail` is deliberately not rendered. CONTRACT.md: "detail renders only at
 * level 1." Level 2 is the default, and the whole point of it is that the
 * extra sentence is not there unless someone is struggling.
 */

import { motion } from "framer-motion";

import type { StepRendererProps } from "./StepView";

const EASE = [0.22, 0.61, 0.36, 1] as const;

export function Level2Step({
  step,
  values,
  onChange,
  onAction,
  waiting,
  answered,
}: StepRendererProps) {
  return (
    <div className="flex flex-col gap-10">
      <motion.h1
        layout
        className="text-[30px] leading-[1.35] font-medium tracking-[-0.01em]"
        animate={{ opacity: waiting ? 0.55 : 1 }}
        transition={{ duration: 0.3, ease: EASE }}
      >
        {step.instruction}
      </motion.h1>

      {step.fields.length > 0 && (
        <motion.div
          layout
          className="flex flex-col gap-5"
          animate={{ opacity: waiting ? 0.75 : 1 }}
          transition={{ duration: 0.3, ease: EASE }}
        >
          {step.fields.map((field) => (
            <label key={field.id} className="flex flex-col gap-2">
              <span className="text-[15px] text-muted">{field.label}</span>
              <input
                className="h-14 rounded-lg border border-line bg-raised px-4 text-[19px]
                           text-ink outline-none transition-colors duration-300
                           focus:border-accent"
                type={field.type === "password" ? "password" : "text"}
                value={values[field.id] ?? ""}
                onChange={(event) => onChange(field.id, event.target.value)}
                aria-label={field.label}
              />
            </label>
          ))}
        </motion.div>
      )}

      <motion.div layout className="flex flex-col gap-3">
        {step.actions.map((action, index) => (
          <motion.button
            key={action.id}
            type="button"
            onClick={() => onAction(action.id)}
            disabled={answered}
            className={buttonClass(action.kind, index === 0)}
            animate={{ opacity: answered ? 0.4 : waiting ? 1 : 0.85 }}
            transition={{ duration: 0.3, ease: EASE }}
            whileTap={{ scale: 0.99 }}
          >
            {action.label}
          </motion.button>
        ))}
      </motion.div>
    </div>
  );
}

/**
 * One accent colour. The primary action carries it; everything else is an
 * outline, so there is never a question of which button is the one.
 */
function buttonClass(kind: string, isFirst: boolean): string {
  const base =
    "h-16 w-full rounded-xl px-6 text-[19px] font-medium " +
    "transition-colors duration-300 outline-none";

  if (kind === "primary" || (isFirst && kind !== "destructive")) {
    return `${base} bg-accent text-accent-ink hover:brightness-105`;
  }
  if (kind === "destructive") {
    return `${base} border border-stuck text-stuck hover:bg-stuck/10`;
  }
  return `${base} border border-line text-muted hover:text-ink hover:border-ink/40`;
}
