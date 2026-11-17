/**
 * "My bookings" (2026-11-17): every booking or order SIMBA completed, as a
 * clean card — what, the details the website confirmed, the number, the
 * amount. Kept on this computer only (`backend/orchestrator/bookings.py`),
 * never a card number, a code or a detail that identifies the person.
 */

import { BOOKINGS } from "../copy";
import { useStore } from "../store";
import { Button } from "./ui";

export function Bookings() {
  const { bookings, setBookingsOpen } = useStore();
  return (
    <div className="flex flex-col gap-5 short:gap-3" data-testid="bookings">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-display font-semibold tracking-[-0.015em] text-ink short:text-heading">
          {BOOKINGS.title}
        </h1>
        <Button size="md" wide={false} variant="secondary" data-testid="bookings-back"
                onClick={() => setBookingsOpen(false)}>
          {BOOKINGS.back}
        </Button>
      </div>
      {bookings.length === 0 ? (
        <p className="rounded-lg bg-tint px-5 py-4 text-lead text-ink" data-testid="bookings-none">
          {BOOKINGS.none}
        </p>
      ) : (
        <div className="grid max-h-[62vh] gap-3 overflow-y-auto pr-1" data-testid="booking-list">
          {bookings.map((booking) => (
            <article key={booking.id} data-testid="booking"
                     className="flex flex-col gap-2 rounded-lg border border-edge bg-surface px-6
                                py-4 shadow-press">
              <div className="flex items-baseline justify-between gap-4">
                <h2 className="text-lead font-semibold text-ink short:text-body">{booking.title}</h2>
                {booking.amount && (
                  <span className="text-lead font-semibold text-accent tabular-nums short:text-body">
                    {booking.amount}
                  </span>
                )}
              </div>
              <p className="text-small text-soft">{booking.site} · {booking.when}</p>
              {booking.lines.length > 0 && (
                <dl className="grid grid-cols-2 gap-x-6 gap-y-1">
                  {booking.lines.map((line, index) => (
                    <div key={`${line.label}-${index}`} className="flex min-w-0 items-baseline gap-3">
                      <dt className="w-28 shrink-0 text-caption text-soft">{line.label}</dt>
                      <dd className="min-w-0 text-small font-semibold text-ink">{line.value}</dd>
                    </div>
                  ))}
                </dl>
              )}
              {booking.number && (
                <p className="text-body font-semibold text-ink">
                  {BOOKINGS.number} <span className="tabular-nums">{booking.number}</span>
                </p>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
