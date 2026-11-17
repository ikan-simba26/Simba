/**
 * "Which one?" (2026-11-17): the site's own choices — products from a search,
 * a bus at a time, a class, a size — drawn as big simple cards, each with its
 * name, a line under it (a price, a time) and its picture when the site has
 * one. Pressing a card answers; the backend then presses the real one on the
 * website. At most a handful are shown, so none is below the fold.
 *
 * Used when any of the step's actions carries a `sub` or a `picture`
 * (`shared/schema`); every other step is drawn as before.
 */

import type { StepPresented } from "@shared/schema";

import { TopLine } from "./StepShell";
import { Button } from "./ui";

export function isChoiceStep(step: StepPresented): boolean {
  return step.actions.some((action) => Boolean(action.picture || action.sub));
}

export function ChoiceCards({ step, answered, onAction }: {
  step: StepPresented;
  answered: boolean;
  onAction: (actionId: string) => void;
}) {
  const cards = step.actions.filter((action) => action.picture || action.sub);
  const others = step.actions.filter((action) => !(action.picture || action.sub));
  const columns = cards.length <= 2 ? "grid-cols-1" : "grid-cols-2";
  return (
    <div className="flex flex-col gap-4 short:gap-3" data-testid="choice-cards">
      <TopLine step={step} stages full answered={answered} />
      <h1 className="text-title font-semibold leading-[1.25] tracking-[-0.015em] text-ink
                     short:text-lead">
        {step.instruction}
      </h1>
      {step.detail && <p className="text-body text-soft short:text-small">{step.detail}</p>}
      <div className={`grid max-h-[46vh] gap-3 overflow-y-auto pr-1 ${columns}`}
           data-testid="cards">
        {cards.map((card) => (
          <button key={card.id} type="button" disabled={answered}
                  data-testid="card" onClick={() => onAction(card.id)}
                  className="flex min-h-24 items-center gap-4 rounded-lg border border-edge
                             bg-surface p-3 text-left shadow-press transition-[box-shadow,
                             border-color] duration-200 hover:border-accent hover:shadow-lift
                             active:translate-y-px disabled:opacity-50">
            {card.picture ? (
              <img src={card.picture} alt="" className="h-20 w-20 shrink-0 rounded-md bg-tint
                                                        object-contain" />
            ) : null}
            <span className="flex min-w-0 flex-col gap-1">
              <span className="line-clamp-2 text-body font-semibold text-ink short:text-small">
                {card.label}
              </span>
              {card.sub && (
                <span className="text-body font-semibold text-accent tabular-nums short:text-small">
                  {card.sub}
                </span>
              )}
            </span>
          </button>
        ))}
      </div>
      <div className="flex flex-row gap-3">
        {others.map((action) => (
          <Button key={action.id} variant="secondary" size="md" wide={false}
                  disabled={answered} onClick={() => onAction(action.id)}>
            {action.label}
          </Button>
        ))}
      </div>
    </div>
  );
}
