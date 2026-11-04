/**
 * What SIMBA learned, read back to the helper before it is kept (2026-11-04,
 * "Show me once"): each move in plain words, numbered, the last what it reads
 * at the end; then the name for the home screen and what the answer is
 * called, and "Keep it". Like the final screen it has its own layout at every
 * level: the helper is checking a list, and folding it would hide part of it.
 * Every word is the backend's (`step.routine`, its fields and answers).
 */

import type { StepPresented } from "@shared/schema";

import { Button, InfoIcon } from "./ui";

export function ReadBack({ step, values, answered, onChange, onAction }: {
  step: StepPresented;
  values: Record<string, string>;
  answered: boolean;
  onChange: (fieldId: string, value: string) => void;
  onAction: (actionId: string) => void;
}) {
  const lines = step.routine ?? [];
  const [keep, ...rest] = step.actions;
  const named = Boolean((values.name ?? "").trim());
  return (
    <div className="flex flex-col gap-4 short:gap-2" data-testid="read-back">
      {step.note && (
        <p className="flex items-start gap-3 rounded-lg bg-tint px-5 py-3 text-body text-ink
                      short:py-2" data-testid="note" role="status">
          <span className="mt-1 shrink-0 text-accent" aria-hidden><InfoIcon /></span>
          <span>{step.note}</span>
        </p>
      )}
      <h1 className="text-title font-semibold leading-[1.25] tracking-[-0.015em] text-ink
                     short:text-lead">
        {step.instruction}
      </h1>
      <ol className="flex flex-col gap-1.5 rounded-lg bg-tint px-6 py-4 short:gap-0.5 short:py-2"
          data-testid="read-back-lines">
        {lines.map((line, index) => (
          <li key={index} className="flex items-baseline gap-3 text-body text-ink short:text-small">
            <span className="w-6 shrink-0 text-right font-semibold tabular-nums text-accent">
              {index + 1}.
            </span>
            <span className="min-w-0">{line}</span>
          </li>
        ))}
      </ol>
      {step.detail && <p className="text-body text-soft short:text-small">{step.detail}</p>}
      <div className="grid grid-cols-2 gap-4 short:gap-3">
        {step.fields.map((field) => (
          <label key={field.id} className="flex min-w-0 flex-col gap-1.5">
            <span className="text-small font-medium text-soft">{field.label}</span>
            <input value={values[field.id] ?? ""} maxLength={field.id === "name" ? 28 : 60}
                   disabled={answered} data-testid={`read-back-${field.id}`}
                   onChange={(event) => onChange(field.id, event.target.value)}
                   className="simba-field-frame rounded-xl px-5 py-3 text-body text-ink shadow-card
                              outline-none short:py-2" />
          </label>
        ))}
      </div>
      <div className="flex flex-row gap-3">
        {keep && (
          <Button size="md" className="flex-1" disabled={answered || !named}
                  data-testid="read-back-keep" onClick={() => onAction(keep.id)}>
            {keep.label}
          </Button>
        )}
        {rest.map((action) => (
          <Button key={action.id} size="md" variant="quiet" className="flex-1"
                  disabled={answered} onClick={() => onAction(action.id)}>
            {action.label}
          </Button>
        ))}
      </div>
    </div>
  );
}
