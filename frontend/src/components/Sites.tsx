/**
 * The websites SIMBA can work with (2026-11-13, the advisor's direction).
 *
 * The list on the home screen's left, by genre, from the catalogue the
 * backend offers (`history.offered.sites`) — so the home screen no longer
 * reads as three fixed tasks, and the answer to "what about my website?" is in
 * front of the person: pick it here, type it beside the box to ask in, or add
 * it with "Add a website" at the foot of the list. Choosing a website puts what
 * SIMBA can do there in the middle of the screen, with how it does each one.
 *
 * Shown only when the backend offers a list; a backend that offers none gets
 * the home screen as it was.
 */

import { useState } from "react";

import type { CatalogueSite } from "@shared/schema";

import { SITES, TEACH } from "../copy";
import { pictureForName, type PictureKind } from "../pictures";
import { useStore } from "../store";
import { Button, PictureChip, PictureIcon } from "./ui";

/** The list's width, in the overlay's pixels. The home screen's column moves
 *  right by this much while the list is there: 1266 - 272 - 64 leaves 930
 *  for the 880 column at 150%. */
export const SITE_LIST_WIDTH = 272;

/** A genre's picture, from the same four as the tiles: a train for travel, a
 *  bill for bills, a book for education, the globe for the rest. */
export function pictureForGenre(genre: string): PictureKind {
  const named = pictureForName(genre);
  if (named !== "other") return named;
  return /travel/i.test(genre) ? "train"
    : /bill/i.test(genre) ? "bill"
    : /educat|school|universit/i.test(genre) ? "course"
    : "other";
}

/** The website's host, as a person reads it: no scheme, no "www.". */
export function hostOf(address: string): string {
  try {
    const host = new URL(address).host;
    return host.startsWith("www.") ? host.slice(4) : host;
  } catch {
    return address;
  }
}

/** The list on the left. */
export function SiteList() {
  const { sites, genres, chosenSite, chooseSite, setAddSiteOpen } = useStore();
  const groups = genres
    .map((genre) => ({ genre, sites: sites.filter((site) => site.genre === genre) }))
    .filter((group) => group.sites.length > 0);

  return (
    <nav aria-label={SITES.list} data-testid="site-list"
         className="fixed top-20 bottom-9 left-6 z-[1] flex flex-col gap-3 rounded-xl border
                    border-edge bg-surface/80 p-3 shadow-card short:top-14 short:bottom-9"
         style={{ width: SITE_LIST_WIDTH }}>
      <p className="px-2 pt-1 text-small font-medium text-soft">{SITES.list}</p>
      {/* The list scrolls on its own; the rest of the screen never does. */}
      <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto pr-1"
           data-testid="site-scroll">
        {groups.map(({ genre, sites: inGenre }) => (
          <section key={genre} aria-label={genre} data-testid="site-genre">
            <p className="flex items-center gap-2 px-2 pb-1 text-small font-semibold text-ink">
              <span className="text-accent" aria-hidden>
                <PictureIcon kind={pictureForGenre(genre)} size={18} />
              </span>
              {genre}
            </p>
            <ul className="flex flex-col">
              {inGenre.map((site) => {
                const chosen = site.id === chosenSite;
                return (
                  <li key={site.id}>
                    <button type="button" data-testid="site" aria-pressed={chosen}
                            title={hostOf(site.address)}
                            onClick={() => chooseSite(chosen ? null : site.id)}
                            className={`w-full rounded-md px-3 py-1.5 text-left text-body
                                        leading-snug transition-colors duration-150
                                        ${chosen ? "bg-tint font-semibold text-ink"
                                                 : "text-ink hover:bg-tint/60"}`}>
                      <span className="line-clamp-1">{site.name}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>
      <Button variant="secondary" size="md" onClick={() => setAddSiteOpen(true)}
              data-testid="add-site">
        {SITES.add}
      </Button>
    </nav>
  );
}

/**
 * The chosen website, in place of the row of three: its name and address, each
 * thing SIMBA can do there with how it does it, and, for a helper, "Show me a
 * task here", which opens "Show me once" on its address.
 */
export function SitePanel({ site }: { site: CatalogueSite }) {
  const { startTask, startRoutine, routines, chooseSite, setTeachOpen } = useStore();
  return (
    <section className="flex flex-col gap-3 short:gap-2" aria-label={site.name}
             data-testid="site-panel">
      {/* One row for the website and both ways out of it: with the person's
          own tiles above, a row each put the box to ask in off the bottom at
          150% (measured 2026-11-13). */}
      <div className="flex items-baseline justify-between gap-4">
        <p className="min-w-0 truncate text-small font-medium text-soft">
          <span className="font-semibold text-ink">{site.name}</span>
          <span className="ml-2">{hostOf(site.address)}</span>
        </p>
        <div className="flex shrink-0 items-baseline gap-4">
          <Button variant="quiet" size="md" wide={false}
                  onClick={() => setTeachOpen(true, site.address)} data-testid="site-show-here">
            {SITES.showHere}
          </Button>
          <Button variant="quiet" size="md" wide={false} onClick={() => chooseSite(null)}
                  data-testid="site-not-this">
            {SITES.notThis}
          </Button>
        </div>
      </div>
      <p className="text-small font-medium text-soft short:hidden">{SITES.hereICan}</p>
      <ul className="grid grid-cols-3 gap-4 short:gap-3" data-testid="site-tasks">
        {site.tasks.map((task) => (
          <li key={`${task.how}-${task.routine ?? task.label}`}>
            <button type="button" data-testid="site-task" data-how={task.how}
                    title={task.goal}
                    onClick={() => {
                      const routine = task.routine
                        ? routines.find((r) => r.id === task.routine) : undefined;
                      // Taught on a sister website (2026-11-13): run here.
                      if (routine && task.taught_on) {
                        startTask(routine.label, undefined, undefined, routine.id, site.address);
                      } else if (routine) startRoutine(routine);
                      else startTask(task.goal, task.flow, undefined, undefined,
                                     task.flow ? undefined : site.address);
                    }}
                    className="flex h-full w-full items-center gap-4 rounded-xl border
                               border-edge bg-surface px-5 py-2 text-left shadow-card
                               transition-[box-shadow,border-color,transform] duration-200
                               hover:border-accent/50 hover:shadow-lift active:translate-y-px
                               short:py-1.5">
              <PictureChip kind={pictureForGenre(site.genre)} taught={task.how === "taught"} />
              <span className="flex min-w-0 flex-col">
                <span className="line-clamp-2 text-body font-semibold leading-snug text-ink">
                  {task.label}
                </span>
                <span className="line-clamp-1 text-small text-soft">
                  {task.taught_on ? SITES.taughtOn(task.taught_on) : SITES.how[task.how]}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** "Add a website": what to call it, its address, and what kind it is. */
export function AddSite() {
  const { genres, addSite, setAddSiteOpen, addingSite, siteNote } = useStore();
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const choices = genres.includes("Other") ? genres : [...genres, "Other"];
  const [genre, setGenre] = useState(choices[0] ?? "Other");
  const ready = name.trim() !== "" && address.trim() !== "" && !addingSite;
  const add = () => ready && addSite({ name: name.trim(), address: address.trim(), genre });

  const field = "simba-field-frame w-full min-w-0 rounded-xl bg-transparent px-4 py-3 " +
                "text-body text-ink shadow-card outline-none placeholder:text-soft short:py-2";
  return (
    <div className="flex min-h-[calc(100dvh-176px)] flex-col justify-center gap-5
                    short:min-h-[calc(100dvh-92px)] short:gap-3" data-testid="add-site-screen">
      <div className="flex flex-col gap-2">
        <h1 className="text-display font-semibold tracking-[-0.015em] text-ink short:text-heading">
          {SITES.addAsk}
        </h1>
        <p className="text-lead text-ink short:text-body">{SITES.addDetail}</p>
      </div>
      {/* One row of three: stacked, the three boxes put "Add it" off the
          bottom of the window at 125% and 150% (measured 2026-11-13). */}
      <div className="grid grid-cols-[1fr_1.3fr_1fr] gap-4 short:gap-3">
        <label className="flex min-w-0 flex-col gap-2">
          <span className="text-small font-medium text-soft">{SITES.name}</span>
          <input className={field} value={name} maxLength={40} data-testid="add-site-name"
                 placeholder={SITES.namePlaceholder} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="flex min-w-0 flex-col gap-2">
          <span className="text-small font-medium text-soft">{SITES.address}</span>
          <input className={field} value={address} data-testid="add-site-address"
                 placeholder={SITES.addressPlaceholder}
                 onChange={(e) => setAddress(e.target.value)}
                 onKeyDown={(e) => e.key === "Enter" && add()} />
        </label>
        <label className="flex min-w-0 flex-col gap-2">
          <span className="text-small font-medium text-soft">{SITES.genre}</span>
          <select className={field} value={genre} data-testid="add-site-genre"
                  onChange={(e) => setGenre(e.target.value)}>
            {choices.map((choice) => <option key={choice} value={choice}>{choice}</option>)}
          </select>
        </label>
      </div>
      {siteNote && (
        <p className="rounded-lg bg-tint px-5 py-3 text-body text-ink" role="status"
           data-testid="site-note">
          {siteNote}
        </p>
      )}
      <div className="flex items-center justify-between gap-4">
        <Button variant="quiet" size="md" wide={false} onClick={() => setAddSiteOpen(false)}
                data-testid="add-site-back">
          {/* The same words as "Show me once"'s way back. */}
          {TEACH.back}
        </Button>
        <Button size="md" wide={false} disabled={!ready} onClick={add}
                data-testid="add-site-go">
          {SITES.addIt}
        </Button>
      </div>
    </div>
  );
}
