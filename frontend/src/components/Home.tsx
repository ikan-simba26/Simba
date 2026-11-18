/**
 * The first screen (redesigned 2026-11-14, Raham: "the home screen must not
 * look like three tasks").
 *
 * Two questions, one at a time:
 *
 *   1. "Where do you want to go?" — the websites SIMBA can work with as large
 *      cards, each with the website's icon and name, grouped by kind; one more
 *      card for a website that is not there; and one box, which finds a
 *      website among the cards as it is typed in, goes to an address, and
 *      takes anything else as something to do, as the box always has.
 *   2. "What do you want to do there?" — the chosen website's name and icon,
 *      what SIMBA can do there as a few big suggestions, and a box to say
 *      anything else in the person's own words.
 *
 * The three built-in tasks are suggestions on their own websites, not the
 * home screen's tiles. The person's own tasks — kept, or shown by a helper —
 * are a row of their own on the first screen, only when there are some.
 * "Teach a task" stays in the corner (`App.TeachEntry`).
 *
 * Until now the websites were a narrow list down the left and the middle of
 * the screen was three tiles: the list was the afterthought, and the screen
 * read as "SIMBA does three things".
 */

import { useRef, useState } from "react";

import type { CatalogueSite, CatalogueTask, FlowName, PastGoal } from "@shared/schema";

import { BOOKINGS, FLOWS, HOME, SETTINGS, SITES, TILES } from "../copy";
import { useStore } from "../store";
import { pictureForFlow, pictureForName } from "../pictures";
import { hostOf, pictureForGenre } from "./Sites";
import { AgainIcon, Button, ChevronIcon, PictureChip, SpeechIcon } from "./ui";

/** How wide the first screen is: wider than a step's column, for five cards. */
export const HOME_WIDTH = 1128;

/** `chosenSite` when the person pressed "Another website". */
export const ANOTHER = "another-website";

/** A suggestion to finish before it starts: its goal has a gap in it. */
const GAP = "…";

/** With no list of websites offered — an older backend, or a list that could
 *  not be read — the first screen is not left empty: the three tasks SIMBA
 *  knows by heart are cards in the websites' place. */
const KNOWN: FlowName[] = ["registration", "billing", "railways"];

/** Whether what was typed is a website's address rather than words. */
export function looksLikeAddress(text: string): boolean {
  return /^(https?:\/\/)?([a-z0-9-]+\.)+[a-z]{2,}(\/\S*)?$/i.test(text.trim());
}

/**
 * A website's own icon, when it serves one where icons are usually kept; its
 * first letter on its kind's colour otherwise, and until the icon arrives.
 * Never from a third party: only the website itself is asked.
 */
export function SiteIcon({ address, name, genre, size = 44, solid = false }:
                         { address: string; name: string; genre: string; size?: number;
                           /** The first screen's cards (2026-11-17): the kind's colour, a light letter. */
                           solid?: boolean }) {
  let icon: string | null = null;
  try {
    const url = new URL(address);
    if (url.protocol === "https:") icon = `${url.origin}/favicon.ico`;
  } catch {
    icon = null;
  }
  const [state, setState] = useState<"waiting" | "shown" | "none">(icon ? "waiting" : "none");
  const kind = pictureForGenre(genre);
  return (
    <span className="relative flex shrink-0 items-center justify-center overflow-hidden
                     rounded-lg font-semibold"
          style={{ width: size, height: size, fontSize: Math.round(size * 0.5),
                   background: solid ? `var(--pic-${kind})` : `var(--pic-${kind}-tint)`,
                   color: solid ? "var(--surface)" : `var(--pic-${kind})` }}
          data-testid="site-icon" data-icon={state} aria-hidden>
      {state !== "shown" && (name.trim()[0] ?? "?").toUpperCase()}
      {icon && state !== "none" && (
        <img src={icon} alt="" referrerPolicy="no-referrer"
             className={`absolute inset-0 h-full w-full bg-surface object-contain p-1.5
                         ${state === "shown" ? "" : "opacity-0"}`}
             onLoad={(event) =>
               setState(event.currentTarget.naturalWidth > 1 ? "shown" : "none")}
             onError={() => setState("none")} />
      )}
    </span>
  );
}

export function Home() {
  const { sites, chosenSite } = useStore();
  if (chosenSite === ANOTHER) return <Body><There site={null} /></Body>;
  const chosen = sites.find((site) => site.id === chosenSite);
  return <Body>{chosen ? <There site={chosen} /> : <Where />}</Body>;
}

/** The first screen under its bar: the screen itself, and the person's own things beside it. */
function Body({ children }: { children: React.ReactNode }) {
  return (
    <>
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        {children}
        <div className="shrink-0 pt-3 short:pt-2"><AskEachSetting /></div>
      </div>
      <Aside />
    </>
  );
}

/* ---------------------------------------------------------------- where */

/** How many website cards the first screen shows before "See all": two rows
 *  of four, the last one being "Another website". */
const SHOWN_SITES = 7;

/** Run one thing a website can do, as a suggestion pressed. */
function runTask(site: CatalogueSite, task: CatalogueTask): void {
  const { routines, startRoutine, startTask } = useStore.getState();
  const routine = task.routine ? routines.find((r) => r.id === task.routine) : undefined;
  if (routine && task.taught_on) {
    // Taught on a sister website (2026-11-13): run here.
    startTask(routine.label, undefined, undefined, routine.id, site.address);
  } else if (routine) {
    startRoutine(routine);
  } else {
    startTask(task.goal, task.flow, undefined, undefined, task.flow ? undefined : site.address);
  }
}

function Where() {
  const { sites, genres, profile, chooseSite, startTask } = useStore();
  const [hour] = useState(() => new Date().getHours());
  const [typed, setTyped] = useState("");
  const [all, setAll] = useState(false);
  const box = useRef<HTMLInputElement>(null);
  const words = typed.trim().toLowerCase();
  const matches = (site: CatalogueSite) =>
    !words || site.name.toLowerCase().includes(words)
    || hostOf(site.address).toLowerCase().includes(words)
    || site.genre.toLowerCase().includes(words);
  const found = sites.filter(matches);
  const address = looksLikeAddress(typed);

  // The websites they chose in the setup first, then each kind.
  const favourites = sites.filter((site) => (profile.favourites ?? []).includes(site.id));
  const groups = [
    ...(favourites.length ? [{ genre: SITES.yours, sites: favourites.filter(matches) }] : []),
    ...genres.map((genre) => ({ genre,
                                sites: found.filter((site) => site.genre === genre) })),
  ].filter((group) => group.sites.length > 0);

  // The few shown before "See all": their favourites, then one from each kind in turn,
  // so the first screen shows what SIMBA covers rather than the first kind's websites.
  const shown: CatalogueSite[] = favourites.filter(matches).slice(0, SHOWN_SITES);
  // Within each kind, the tested ones come first (B2).
  const queues = genres.map((genre) => found.filter((site) => site.genre === genre)
    .sort((a, b) => Number(b.tested ?? false) - Number(a.tested ?? false)));
  for (let round = 0; shown.length < SHOWN_SITES && round < found.length; round++) {
    for (const queue of queues) {
      const next = queue[round];
      if (next && !shown.includes(next) && shown.length < SHOWN_SITES) shown.push(next);
    }
  }

  // Three suggestions, one from each of the first kinds: what to say, pressed.
  const chips: { key: string; label: string; run: () => void }[] = [];
  for (const group of genres.map((genre) => sites.filter((site) => site.genre === genre))) {
    const site = group.find((candidate) => candidate.tasks.some((task) => !task.goal.includes(GAP)));
    const task = site?.tasks.find((candidate) => !candidate.goal.includes(GAP));
    if (site && task && chips.length < 3) {
      chips.push({ key: `${site.id}-${task.label}`, label: task.label, run: () => runTask(site, task) });
    }
  }

  const go = () => {
    if (!words) {
      box.current?.focus();
      return;
    }
    if (address) {
      chooseSite(ANOTHER, typed.trim());
    } else if (found.length === 1) {
      chooseSite(found[0].id);
    } else {
      // Not one website's name: something to do, routed as it always was.
      startTask(typed.trim());
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-7 short:gap-4" data-testid="home-where">
      <section className="flex shrink-0 flex-col gap-4 rounded-2xl border border-line bg-surface px-9 py-8
                          shadow-card short:gap-2.5 short:px-6 short:py-4">
        <p className="text-small text-soft" data-testid="greeting">{HOME.hello(hour, profile.name)}</p>
        <label htmlFor="home-goal"
               className="text-heading font-bold leading-[1.1] tracking-[-0.02em] text-ink
                          short:text-title">
          {HOME.question}
        </label>
        <div className="flex items-stretch gap-3">
          <input id="home-goal" ref={box} data-testid="ask-goal"
                 className="simba-field min-h-16 min-w-0 flex-1 rounded-xl px-5 text-small
                            text-ink short:min-h-14"
                 style={{ borderColor: "var(--accent)", borderWidth: 2 }}
                 value={typed} onChange={(event) => setTyped(event.target.value)}
                 onKeyDown={(event) => event.key === "Enter" && go()}
                 placeholder={HOME.examplePlaceholder} aria-label={HOME.askHeading} />
          {/* Always strong, and always there: "Go" to the one website found or to an
              address, "Start" for anything else. Pressed with nothing typed it takes
              the person to the box (it was faint, and looked switched off). */}
          <button type="button" onClick={go} aria-disabled={!words} data-testid="home-go"
                  className="flex min-h-16 shrink-0 items-center gap-2 rounded-xl bg-accent px-8
                             text-small font-semibold text-accent-ink shadow-lift transition-colors
                             hover:bg-accent-hover active:translate-y-px short:min-h-14 short:px-6">
            {words && (address || found.length === 1) ? HOME.go : HOME.start}
            <span aria-hidden><ChevronIcon /></span>
          </button>
        </div>
        {chips.length > 0 && (
          <ul className="flex flex-wrap gap-2.5" data-testid="chips">
            {chips.map((chip) => (
              <li key={chip.key}>
                <button type="button" onClick={chip.run} data-testid="chip"
                        className="min-h-11 rounded-full bg-tint px-5 text-small text-accent
                                   transition-colors hover:bg-sunk active:translate-y-px">
                  {chip.label}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* With no list of websites offered — an older backend, or a list that could not be
          read — the three tasks SIMBA knows by heart are cards in the websites' place. */}
      {sites.length === 0 && !words && (
        <section className="flex flex-col gap-3" aria-label={HOME.canHelp} data-testid="tiles">
          <h2 className="text-lead font-semibold text-ink short:text-body" data-testid="can-help">
            {HOME.canHelp}
          </h2>
          <ul className="grid grid-cols-3 gap-3.5">
            {KNOWN.map((flow) => (
              <li key={flow}>
                <button type="button" data-testid="tile" className={`${CARD} w-full border-line`}
                        onClick={() => startTask(FLOWS[flow], flow)}>
                  <PictureChip kind={pictureForFlow(flow)} />
                  <span className="line-clamp-2 text-small font-semibold leading-tight text-ink">
                    {FLOWS[flow]}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {sites.length > 0 && (
        <section className="simba-scroll flex min-h-0 flex-1 flex-col gap-3.5 overflow-y-auto pb-1 pr-1
                            short:gap-2" aria-label={HOME.pickSite} data-testid="site-scroll">
          <div className="flex items-baseline justify-between gap-4">
            {/* One line (2026-11-18, B2): any address works, the listed ones are tried, and how many. */}
            <h2 className="flex min-w-0 flex-wrap items-baseline gap-x-4 text-lead font-semibold text-ink
                           short:text-body" data-testid="works-anywhere">
              <span>{HOME.worksAnywhere}</span>
              <span className="text-small font-normal text-soft" data-testid="site-count">
                {HOME.siteCount(sites.length, sites.filter((site) => site.tested).length)}
              </span>
            </h2>
            <button type="button" onClick={() => setAll(!all)} data-testid="see-all"
                    className="shrink-0 text-small font-medium text-accent underline underline-offset-4">
              {all ? HOME.seeFewer : HOME.seeAll(sites.length)}
            </button>
          </div>
          {words && found.length === 0 && !address && (
            <p className="text-body text-soft" role="status" data-testid="no-match">{HOME.noMatch}</p>
          )}
          {all ? (
            <div className="flex flex-col gap-5 short:gap-3" data-testid="site-grid">
              {groups.map(({ genre, sites: inGenre }) => (
                <section key={genre} aria-label={genre} data-testid="site-genre"
                         className="flex flex-col gap-2">
                  <p className="text-small font-semibold text-soft">{genre}</p>
                  <div className="grid grid-cols-4 gap-3.5 short:gap-2.5">
                    {inGenre.map((site) => <SiteCard key={`${genre}-${site.id}`} site={site} />)}
                  </div>
                </section>
              ))}
              <div className="grid grid-cols-4 gap-3.5"><AnotherCard /></div>
            </div>
          ) : (
            <div className="grid grid-cols-4 gap-3.5 short:gap-2.5" data-testid="site-grid">
              {shown.map((site) => <SiteCard key={site.id} site={site} />)}
              <AnotherCard />
            </div>
          )}
        </section>
      )}
    </div>
  );
}

const CARD =
  "flex min-h-[84px] min-w-0 items-center gap-3.5 rounded-2xl border bg-surface p-4 text-left "
  + "transition-[box-shadow,border-color,transform] duration-200 hover:border-accent/50 "
  + "hover:shadow-lift active:translate-y-px short:min-h-[68px] short:gap-2.5 short:p-2.5";

/** A website: its mark, its name, and what kind it is in a word. */
function SiteCard({ site }: { site: CatalogueSite }) {
  const chooseSite = useStore((state) => state.chooseSite);
  return (
    <button type="button" data-testid="site" title={hostOf(site.address)} aria-label={site.name}
            onClick={() => chooseSite(site.id)} className={`${CARD} border-line`}>
      <SiteIcon address={site.address} name={site.name} genre={site.genre} size={48} solid />
      <span className="flex min-w-0 flex-col">
        {/* Without a name's aside in brackets, which the kind already says: "(practice copy)". */}
        <span className="line-clamp-2 text-small font-semibold leading-tight text-ink">
          {site.name.replace(/\s*\([^)]*\)\s*$/, "")}
        </span>
        <span className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5">
          <span className="line-clamp-1 text-small text-soft">{site.genre}</span>
          {(site.tested || site.look_up_only) && (
            <strong data-testid={site.look_up_only ? "badge-lookup" : "badge-tested"}
                  className="rounded-full bg-tint px-2 text-small font-semibold text-accent">
              {site.look_up_only ? HOME.lookUpOnlyBadge : HOME.testedBadge}
            </strong>
          )}
        </span>
      </span>
    </button>
  );
}

/** For a website that is not among the cards: its address, typed. */
function AnotherCard() {
  const chooseSite = useStore((state) => state.chooseSite);
  return (
    <button type="button" data-testid="another-site" onClick={() => chooseSite(ANOTHER)}
            className={`${CARD} border-2 border-dashed border-edge bg-transparent`}>
      <span aria-hidden className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-tint
                                   text-accent short:h-10 short:w-10">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             strokeWidth="2" strokeLinecap="round"><path d="M12 5v14M5 12h14" /></svg>
      </span>
      <span className="flex min-w-0 flex-col">
        <span className="line-clamp-2 text-small font-semibold leading-tight text-accent">
          {HOME.anotherSite}
        </span>
        <span className="truncate text-small text-soft">{HOME.anotherSiteDetail}</span>
      </span>
    </button>
  );
}

/* ----------------------------------------------------------------- aside */

/** "2026-11-17 18:40" as people say it: "17 November". */
function dayOf(when: string): string {
  const found = /^(\d{4})-(\d{2})-(\d{2})/.exec(when);
  return found ? HOME.onDay(Number(found[3]), Number(found[2])) : when;
}

/** The person's own things, beside the screen: their bookings, and the tasks they kept. */
function Aside() {
  const { bookings, tiles, routines, startTile, startRoutine, setTilesOpen, setBookingsOpen } = useStore();
  const own = tiles.length + routines.length > 0;
  const [newest, ...older] = bookings;

  return (
    <aside className="simba-scroll flex w-[330px] shrink-0 flex-col gap-5 overflow-y-auto short:w-[290px]
                      short:gap-3" data-testid="home-aside">
      <section className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-5 shadow-card
                          short:gap-2 short:p-3.5" aria-label={BOOKINGS.title} data-testid="bookings-panel">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="text-lead font-semibold text-ink short:text-body">{BOOKINGS.title}</h2>
          <button type="button" onClick={() => setBookingsOpen(true)} data-testid="my-bookings"
                  className="text-small font-medium text-accent underline underline-offset-4">
            {BOOKINGS.seeAll}
          </button>
        </div>
        {newest ? (
          <>
            <article data-testid="booking-newest"
                     className="flex flex-col gap-1.5 rounded-xl bg-accent p-4 text-accent-ink short:p-3">
              <div className="flex justify-between gap-3 text-small opacity-90">
                <span className="truncate">{newest.site}</span>
                <span className="shrink-0">{dayOf(newest.when)}</span>
              </div>
              <p className="line-clamp-2 text-lead font-bold leading-tight short:text-body">{newest.title}</p>
              <p className="truncate text-small opacity-90">
                {[newest.number, newest.amount].filter(Boolean).join(" · ") || newest.lines[0]?.value}
              </p>
            </article>
            {older.slice(0, 2).map((booking, index) => (
              <article key={booking.id} data-testid="booking-older"
                       className={`flex items-center gap-3 rounded-xl border border-line p-3 short:p-2
                                   ${index > 0 ? "short:hidden" : ""}`}>
                <SiteIcon address={`https://${booking.site}`} name={booking.title} genre="Other"
                          size={44} solid />
                <span className="flex min-w-0 flex-col">
                  <span className="line-clamp-1 text-small font-semibold text-ink">{booking.title}</span>
                  <span className="truncate text-small text-soft">
                    {booking.number ?? booking.amount ?? booking.site}
                  </span>
                </span>
              </article>
            ))}
          </>
        ) : (
          <p className="text-small text-soft" data-testid="bookings-none">{BOOKINGS.none}</p>
        )}
      </section>

      {own && (
        <section className="flex flex-col gap-2.5 rounded-2xl border border-line bg-surface p-5 shadow-card
                            short:gap-2 short:p-3.5" aria-label={HOME.yourTasks} data-testid="own-tiles">
          <h2 className="text-lead font-semibold text-ink short:text-body">{HOME.yourTasks}</h2>
          <p className="text-small text-soft short:hidden">{HOME.tasksHint}</p>
          <ul className="flex flex-col gap-2.5 short:gap-2">
            {tiles.map((tile) => (
              <li key={tile.id}>
                <button type="button" onClick={() => startTile(tile)} data-testid="own-tile"
                        title={tile.label} className={OWN_TASK}>
                  <PictureChip kind={pictureForName(tile.label)} />
                  <span className="line-clamp-2 min-w-0 flex-1 text-small font-semibold text-ink">
                    {tile.label}
                  </span>
                  <span className="shrink-0 text-accent" aria-hidden><ChevronIcon /></span>
                </button>
              </li>
            ))}
            {routines.map((routine) => (
              <li key={routine.id}>
                <button type="button" onClick={() => startRoutine(routine)} data-testid="own-routine"
                        title={routine.label} className={OWN_TASK}>
                  <PictureChip kind={pictureForName(routine.label)} taught />
                  <span className="line-clamp-2 min-w-0 flex-1 text-small font-semibold text-ink">
                    {routine.label}
                  </span>
                  <span className="shrink-0 text-accent" aria-hidden><ChevronIcon /></span>
                </button>
              </li>
            ))}
          </ul>
          <Button variant="quiet" size="md" wide={false} onClick={() => setTilesOpen(true)}
                  data-testid="change-tiles" className="self-start">
            {TILES.change}
          </Button>
        </section>
      )}
    </aside>
  );
}

const OWN_TASK =
  "flex min-h-14 w-full min-w-0 items-center justify-between gap-3 rounded-xl border border-line "
  + "bg-canvas px-4 py-2 text-left transition-[box-shadow,border-color,transform] duration-200 "
  + "hover:border-accent/50 hover:shadow-lift active:translate-y-px short:min-h-12 short:py-1";

/** The person's own setting: be asked before every move (2026-10-14). */
function AskEachSetting() {
  const { askEachTime, setAskEachTime } = useStore();
  return (
    <label className="flex cursor-pointer items-center gap-3 text-small text-soft">
      <input type="checkbox" className="h-5 w-5 shrink-0 accent-[var(--accent)]" checked={askEachTime}
             onChange={(event) => setAskEachTime(event.target.checked)} />
      {SETTINGS.askEach}
    </label>
  );
}

/* ---------------------------------------------------------------- there */

/** A goal asked before on this website, most recent first, at most one. */
function askedHere(history: PastGoal[], site: CatalogueSite): PastGoal | undefined {
  const host = hostOf(site.address);
  return history.find((past) => past.site && hostOf(past.site) === host
    && !site.tasks.some((task) => task.goal === past.goal));
}

/** The most suggestions shown for one website. */
const MOST_SUGGESTIONS = 4;

function There({ site }: { site: CatalogueSite | null }) {
  const { startTask, routines, chooseSite, setTeachOpen, history, anotherAddress,
          setAddSiteOpen } = useStore();
  const [goal, setGoal] = useState("");
  const [where, setWhere] = useState(anotherAddress ?? "");
  const box = useRef<HTMLInputElement>(null);
  const again = site ? askedHere(history, site) : undefined;
  const tasks = site ? site.tasks.slice(0, again ? MOST_SUGGESTIONS - 1 : MOST_SUGGESTIONS) : [];
  const address = site ? site.address : where.trim();
  const ready = goal.trim() !== "" && (site !== null || looksLikeAddress(where));

  const start = () => {
    if (ready) startTask(goal.trim(), undefined, undefined, undefined, address);
  };

  const press = (task: CatalogueTask) => {
    if (!site) return;
    if (task.goal.includes(GAP) && !(task.routine && routines.some((r) => r.id === task.routine))) {
      // Something to finish first: "Find the price of the book …" goes in the
      // box, with the gap marked for typing over.
      setGoal(task.goal);
      const at = task.goal.indexOf(GAP);
      requestAnimationFrame(() => {
        box.current?.focus();
        box.current?.setSelectionRange(at, at + GAP.length);
      });
    } else {
      runTask(site, task);
    }
  };

  return (
    <div className="simba-scroll flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto rounded-2xl border
                    border-line bg-surface px-9 py-7 shadow-card short:gap-3 short:px-6 short:py-4"
         data-testid="home-there">
      <div className="flex items-center justify-between gap-4">
        <Button variant="quiet" size="md" wide={false} onClick={() => chooseSite(null)}
                data-testid="site-not-this">
          {SITES.notThis}
        </Button>
        {site ? (
          <Button variant="quiet" size="md" wide={false}
                  onClick={() => setTeachOpen(true, site.address)} data-testid="site-show-here">
            {SITES.showHere}
          </Button>
        ) : (
          // To keep a website among the cards (2026-11-13's "Add a website").
          <Button variant="quiet" size="md" wide={false}
                  onClick={() => setAddSiteOpen(true)} data-testid="add-site">
            {SITES.keepIt}
          </Button>
        )}
      </div>

      <div className="flex flex-col gap-3 short:gap-2">
        {site && (
          <p className="flex items-center gap-4" data-testid="site-chosen">
            <SiteIcon address={site.address} name={site.name} genre={site.genre} size={52} />
            <span className="flex min-w-0 flex-col">
              <span className="truncate text-title font-semibold text-ink short:text-lead">
                {site.name}
              </span>
              <span className="truncate text-small text-soft">{hostOf(site.address)}</span>
            </span>
          </p>
        )}
        <h1 className="text-display font-semibold tracking-[-0.015em] text-ink
                       short:text-heading" data-testid="there-heading">
          {site ? SITES.whatThere : SITES.anotherAsk}
        </h1>
      </div>

      {!site && (
        <label className="flex flex-col gap-2">
          <span className="text-small font-medium text-soft">{SITES.anotherAddress}</span>
          <input className="simba-field-frame w-full rounded-xl bg-transparent px-6 py-4
                            text-lead text-ink shadow-card outline-none placeholder:text-soft
                            short:py-3"
                 value={where} autoFocus={!where}
                 onChange={(event) => setWhere(event.target.value)}
                 placeholder={SITES.anotherPlaceholder} data-testid="ask-where" />
        </label>
      )}

      {(tasks.length > 0 || again) && (
        <ul className="grid gap-4 short:gap-3" data-testid="site-tasks"
            style={{ gridTemplateColumns:
                       `repeat(${Math.max(2, tasks.length + (again ? 1 : 0))}, minmax(0, 1fr))` }}>
          {tasks.map((task) => (
            <li key={`${task.how}-${task.routine ?? task.label}`}>
              <button type="button" data-testid="site-task" data-how={task.how}
                      title={task.goal} onClick={() => press(task)} className={SUGGESTION}>
                <span className="line-clamp-2 text-lead font-semibold leading-snug text-ink
                                 short:text-body">
                  {task.label}
                </span>
                <span className="line-clamp-1 text-small text-soft">
                  {task.taught_on ? SITES.taughtOn(task.taught_on) : SITES.how[task.how]}
                </span>
              </button>
            </li>
          ))}
          {again && (
            <li>
              <button type="button" data-testid="site-again" title={again.goal}
                      onClick={() => site && startTask(again.goal, undefined, undefined,
                                                       undefined, site.address)}
                      className={SUGGESTION}>
                <span className="line-clamp-2 text-lead font-semibold leading-snug text-ink
                                 short:text-body">
                  {again.label ?? again.goal}
                </span>
                <span className="flex items-center gap-2 text-small text-soft">
                  <span className="text-accent" aria-hidden><AgainIcon /></span>
                  {SITES.again}
                </span>
              </button>
            </li>
          )}
        </ul>
      )}

      <div className="flex flex-col gap-3 short:gap-2">
        <p className="text-small font-medium text-soft">
          {tasks.length > 0 || again ? SITES.ownWords : SITES.ownWordsOnly}
        </p>
        <div className="simba-field-frame flex items-center gap-4 rounded-xl py-2 pr-2.5 pl-6
                        shadow-card">
          <span className="shrink-0 text-soft" aria-hidden><SpeechIcon /></span>
          <input ref={box}
                 className="min-w-0 flex-1 bg-transparent py-4 text-lead text-ink outline-none
                            placeholder:text-soft focus-visible:outline-none short:py-3"
                 value={goal} autoFocus={Boolean(site) || Boolean(where)}
                 onChange={(event) => setGoal(event.target.value)}
                 onKeyDown={(event) => event.key === "Enter" && start()}
                 placeholder={SITES.therePlaceholder} aria-label={HOME.askHeading}
                 data-testid="ask-there" />
          {/* As strong as the first screen's: pressed with nothing to say it takes the person
              to the box, it does not look switched off. */}
          <button type="button" aria-disabled={!ready} data-testid="there-start"
                  onClick={() => (ready ? start() : box.current?.focus())}
                  className="flex min-h-14 shrink-0 items-center gap-2 rounded-xl bg-accent px-7 text-small
                             font-semibold text-accent-ink shadow-lift transition-colors
                             hover:bg-accent-hover active:translate-y-px">
            {HOME.start}
            <span aria-hidden><ChevronIcon /></span>
          </button>
        </div>
      </div>
    </div>
  );
}

const SUGGESTION =
  "flex h-full min-h-[112px] w-full flex-col justify-center gap-1 rounded-xl border "
  + "border-edge bg-surface px-6 py-4 text-left shadow-card "
  + "transition-[box-shadow,border-color,transform] duration-200 hover:border-accent/50 "
  + "hover:shadow-lift active:translate-y-px short:min-h-[88px] short:py-2";
