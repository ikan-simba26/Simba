/**
 * The final screen (2026-10-16): the one step before SIMBA books, pays,
 * registers or changes a record (CLAUDE.md, the final-step rule).
 *
 * It says in plain words exactly what will happen (the backend's sentence),
 * shows the key details — what, how much, when — as the page stated them a
 * moment ago (`step.final`), and has two buttons: do it, and don't. Neither
 * is the default: they are the same size, the same colour and the same
 * weight, nothing has focus when the screen arrives, and nothing moves on by
 * itself. Every detail shows at every level: folding a level away must never
 * hide what is about to be done.
 */

import type { StepPresented } from "@shared/schema";

import { Button } from "./ui";
import { TopLine } from "./StepShell";

export function FinalCheck({ step, answered, onAction }: {
  step: StepPresented;
  answered: boolean;
  onAction: (actionId: string) => void;
}) {
  const details = step.final ?? [];
  return (
    <div className="flex flex-col gap-4 short:gap-3" data-testid="final-check">
      <TopLine step={step} stages full answered={answered} />
      <h1 className="text-title font-semibold leading-[1.25] tracking-[-0.015em] text-ink
                     short:text-lead">
        {step.instruction}
      </h1>
      {/* Two columns, each detail one line, its name before it: four to a
          row wrapped "17 October 2026" and a passenger's full name onto two
          lines, and put the answers past a 606px window (2026-10-16). */}
      <dl className="grid grid-cols-2 gap-x-8 gap-y-2 rounded-lg bg-tint px-6 py-4
                     short:gap-y-1 short:py-3" data-testid="final-details">
        {details.map((detail) => (
          <div key={detail.label} className="flex min-w-0 items-baseline gap-3">
            <dt className="w-28 shrink-0 text-caption text-soft short:w-24">{detail.label}</dt>
            <dd className="min-w-0 text-body font-semibold text-ink tabular-nums short:text-small">
              {detail.value}
            </dd>
          </div>
        ))}
      </dl>
      {step.detail && <p className="text-body text-soft" data-testid="final-waits">{step.detail}</p>}
      {/* Two answers of equal weight, side by side: no default. */}
      <div className="flex flex-row gap-3" data-testid="final-answers">
        {step.actions.map((action) => (
          <Button key={action.id} variant="secondary" size="md" className="flex-1"
                  disabled={answered} onClick={() => onAction(action.id)}>
            {action.label}
          </Button>
        ))}
      </div>
    </div>
  );
}
