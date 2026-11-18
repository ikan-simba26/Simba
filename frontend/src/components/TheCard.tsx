/**
 * The card that builds as you go (2026-11-17, the frontend redesign).
 *
 * When a task starts, the finished thing is shown empty — a ticket for a
 * journey, a receipt for an order, a bill, a copy of a form, an answer — and
 * each field fills the moment SIMBA learns it: from the goal, from a choice or
 * a detail the person gave, or from the page. The field just filled is washed
 * in the spotlight colour for a moment, and the foot says how many are done.
 * A field waiting for the person shows an amber "Waiting for you".
 *
 * The final screen is this card, complete, with an amber border: what is
 * about to happen is the thing the person is looking at. After "do it" it
 * gets its number (`BookedCard`).
 *
 * Never a card number, a code or a password: `journey.ts` drops them before
 * they are kept, and a password box is only ever "kept safely".
 */

import { useEffect, useMemo, useRef, useState } from "react";

import { CARD } from "../copy";
import { type CardModel, type Slot, buildCard } from "../journey";
import { useStore } from "../store";

/** Placeholder bar widths, so an empty card reads as a form to fill and not as a fault. */
const BAR: Record<string, string> = {
  from: "w-24", to: "w-24", date: "w-28", ride: "w-28", seat: "w-20", passenger: "w-32", price: "w-20",
  item: "w-32", delivery: "w-20", payment: "w-28", deliverTo: "w-28", total: "w-24",
  reference: "w-28", amount: "w-24", due: "w-24", answer: "w-32", site: "w-28",
};

/** The card for the task on screen, read from the store. */
export function TheCard() {
  const { task, asking, taskSite, facts, finalDetails, findingsSoFar, step, completed } = useStore();
  const goal = task?.goal ?? asking ?? "";
  const model = useMemo(
    () => buildCard({ goal, genre: taskSite?.genre, site: taskSite?.name ?? null, facts,
                      final: finalDetails, findings: completed?.findings ?? findingsSoFar,
                      step: step && !step.routine ? step : null }),
    [goal, taskSite, facts, finalDetails, findingsSoFar, step, completed]);
  return <CardView model={model} />;
}

export function CardView({ model, number, saved = false }: {
  model: CardModel; number?: string | null; saved?: boolean;
}) {
  const copy = CARD[model.shape];
  const complete = model.complete;
  const total = model.slots.find((slot) =>
    slot.key === "total" || (complete && model.shape === "ticket" && slot.key === "price"));
  const rows = model.slots.filter((slot) => slot !== total);
  const item = model.shape === "receipt" ? rows.find((slot) => slot.key === "item") : undefined;
  const lines = rows.filter((slot) => slot !== item);

  return (
    <aside aria-label={copy.title} data-testid="the-card" data-shape={model.shape}
           data-complete={complete ? "true" : undefined}
           className={`flex h-full w-[360px] flex-col overflow-hidden rounded-xl bg-surface shadow-card
                       ${complete ? "border-2 border-turn" : "border border-line"}`}>
      <div className="flex shrink-0 items-center justify-between gap-3 bg-accent px-5 py-3 text-accent-ink
                      short:py-2">
        <span className="text-small font-semibold">{copy.title}</span>
        {complete ? (
          <span className="rounded-full bg-turn-tint px-3 py-0.5 text-small font-semibold text-turn-ink"
                data-testid="card-status">{CARD.complete}</span>
        ) : (
          <span className="text-small opacity-90" data-testid="card-status">{CARD.filling}</span>
        )}
      </div>

      {number && (
        <div className="flex shrink-0 items-baseline justify-between gap-3 border-b border-dashed border-line
                        bg-done-tint px-5 py-2.5 text-done-ink" data-testid="card-number">
          <span className="text-small">{CARD.number}</span>
          <span className="text-small font-semibold tabular-nums">{number}</span>
        </div>
      )}

      <div className="simba-scroll min-h-0 flex-1 overflow-y-auto">
        {item && <ItemBlock slot={item} />}
        <dl className="flex flex-col px-3 py-2 short:py-1" data-testid="card-fields">
          {lines.map((slot) => <Row key={slot.key} slot={slot} />)}
        </dl>
      </div>

      {total ? (
        <div className="flex shrink-0 items-baseline justify-between gap-3 border-t-2 border-dashed border-line
                        px-5 py-3 short:py-2" data-testid="card-total">
          <span className="text-small text-soft">{total.key === "price" ? CARD.ticket.total : total.label}</span>
          {total.value !== null ? (
            <span className="text-[26px] font-bold leading-tight tracking-tight text-ink tabular-nums">
              {total.value}
            </span>
          ) : <Bar slot={total} />}
        </div>
      ) : null}

      <p className="shrink-0 border-t border-dashed border-line px-5 py-2.5 text-small text-soft"
         data-testid="card-count">
        {saved ? CARD.saved : complete ? CARD.ready : CARD.filled(model.filled, model.total)}
      </p>
    </aside>
  );
}

/** A grey bar where a value is not yet known. */
function Bar({ slot }: { slot: Slot }) {
  return <dd aria-label={CARD.notYet} className={`h-3 rounded-md bg-sunk ${BAR[slot.key] ?? "w-24"}`} />;
}

/**
 * One line: its name and its value. When the value arrives, the line is
 * washed once in the spotlight colour (`simba-flash`); one that is waiting
 * for the person is amber and dashed.
 */
function Row({ slot }: { slot: Slot }) {
  const before = useRef<string | null>(slot.value);
  const [flash, setFlash] = useState(false);
  useEffect(() => {
    if (slot.value !== null && slot.value !== before.current) {
      setFlash(true);
      const timer = window.setTimeout(() => setFlash(false), 2400);
      before.current = slot.value;
      return () => window.clearTimeout(timer);
    }
    before.current = slot.value;
  }, [slot.value]);
  // A value known when the card is first drawn (from the goal) arrives with a wash too.
  useEffect(() => {
    if (slot.value === null) return;
    setFlash(true);
    const timer = window.setTimeout(() => setFlash(false), 2400);
    return () => window.clearTimeout(timer);
  }, []);

  if (slot.waiting) {
    return (
      <div className="my-0.5 flex items-center justify-between gap-3 rounded-lg border-2 border-dashed
                      border-turn bg-turn-tint px-3 py-2 text-turn-ink" data-testid="card-row"
           data-state="waiting" data-key={slot.key}>
        <dt className="text-small font-semibold">{slot.label}</dt>
        <dd className="text-small font-semibold">{CARD.waiting}</dd>
      </div>
    );
  }
  return (
    <div className={`flex items-center justify-between gap-3 rounded-lg px-3 py-2 ${
                      flash ? "simba-flash" : ""}`}
         data-testid="card-row" data-state={slot.value !== null ? "filled" : "empty"} data-key={slot.key}
         data-fresh={flash ? "true" : undefined}>
      <dt className="shrink-0 text-small text-soft">{slot.label}</dt>
      {slot.kept ? (
        <dd className="text-small font-semibold text-ink" data-testid="card-kept">{CARD.kept}</dd>
      ) : slot.value !== null ? (
        <dd className="min-w-0 break-words text-right text-small font-semibold text-ink tabular-nums">
          {slot.value}
        </dd>
      ) : <Bar slot={slot} />}
    </div>
  );
}

/** A receipt's item: its picture, its name, and that it is only the one asked for. */
function ItemBlock({ slot }: { slot: Slot }) {
  const initial = (slot.value ?? "").trim().charAt(0).toUpperCase();
  return (
    <div className="flex items-center gap-4 border-b border-dashed border-line px-5 py-3"
         data-testid="card-item" data-state={slot.value !== null ? "filled" : "empty"}>
      {slot.picture ? (
        <img src={slot.picture} alt="" className="h-20 w-14 shrink-0 rounded-md bg-tint object-contain" />
      ) : (
        <span aria-hidden className={`flex h-20 w-14 shrink-0 items-end rounded-md p-1.5 text-small
                                      font-bold ${slot.value !== null ? "bg-turn-tint text-turn-ink" : "bg-sunk"}`}>
          {initial}
        </span>
      )}
      <div className="flex min-w-0 flex-col gap-1">
        <span className="text-small text-soft">{slot.label}</span>
        {slot.value !== null ? (
          <span className="break-words text-small font-semibold text-ink">{slot.value}</span>
        ) : <span aria-label={CARD.notYet} className="h-3 w-28 rounded-md bg-sunk" />}
        {slot.note === "onlyOne" && <span className="text-small text-soft">{CARD.onlyOne}</span>}
      </div>
    </div>
  );
}
