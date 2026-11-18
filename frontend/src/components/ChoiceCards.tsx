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

import { useStore } from "../store";
import { useFramed } from "./framed";
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
  const framed = useFramed();
  // The simplest level (2026-11-17): the choices as very large tiles, side by side.
  const simplest = useStore((state) => state.level) === 3 && framed;
  const cards = step.actions.filter((action) => action.picture || action.sub);
  // In the task frame the way to stop is the header's.
  const others = step.actions.filter((action) => !(action.picture || action.sub)
                                       && !(framed && action.kind === "secondary"));
  const columns = simplest ? (cards.length === 2 ? "grid-cols-2" : "grid-cols-3")
    : framed ? (cards.length <= 4 ? "grid-cols-1" : "grid-cols-2")
    : cards.length <= 2 ? "grid-cols-1" : "grid-cols-2";
  return (
    <div className="flex flex-col gap-4 short:gap-3" data-testid="choice-cards">
      <TopLine step={step} stages full answered={answered} />
      <h1 className={`font-semibold leading-[1.25] tracking-[-0.015em] text-ink short:text-lead
                      ${simplest ? "text-center text-display" : "text-title"}`}>
        {step.instruction}
      </h1>
      {step.detail && !simplest && <p className={`text-body text-soft ${framed ? "short:hidden" : "short:text-small"}`}>{step.detail}</p>}
      <div className={`grid gap-3 pr-1 ${framed ? "" : "max-h-[46vh] overflow-y-auto"} ${columns}`}
           data-testid="cards">
        {cards.map((card) => (
          <button key={card.id} type="button" disabled={answered}
                  data-testid="card" onClick={() => onAction(card.id)}
                  className={`flex items-center gap-4 rounded-lg border bg-surface text-left shadow-press
                              transition-[box-shadow,border-color] duration-200 hover:border-accent
                              hover:shadow-lift active:translate-y-px disabled:opacity-50
                              ${simplest ? "min-h-48 flex-col justify-center gap-3 border-2 border-edge p-6 text-center"
                                : framed ? "min-h-20 border-2 border-line p-3 short:min-h-16"
                                : "min-h-24 border-edge p-3"}`}>
            {card.picture ? (
              <img src={card.picture} alt="" className="h-20 w-20 shrink-0 rounded-md bg-tint
                                                        object-contain" />
            ) : null}
            <span className={`flex min-w-0 flex-1 gap-1 ${simplest ? "flex-col items-center"
                              : framed ? "items-center justify-between gap-4" : "flex-col"}`}>
              <span className={`line-clamp-2 font-semibold text-ink ${simplest
                ? "text-display short:text-title" : framed ? "max-w-[50%] shrink-0 text-lead short:text-body"
                : "text-body short:text-small"}`}>
                {card.label}
              </span>
              {card.sub && (
                <span className={`font-semibold tabular-nums text-accent ${simplest
                  ? "line-clamp-2 text-lead" : framed ? "line-clamp-2 text-right text-small"
                  : "text-body short:text-small"}`}>
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
