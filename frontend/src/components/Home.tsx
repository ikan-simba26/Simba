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

import type { CatalogueSite, CatalogueTask, PastGoal } from "@shared/schema";

import { HOME, SETTINGS, SITES, TILES, greetingAt } from "../copy";
import { pictureForName } from "../pictures";
import { useStore } from "../store";
import { hostOf, pictureForGenre } from "./Sites";
import { AgainIcon, Button, PictureChip, SpeechIcon } from "./ui";

/** How wide the first screen is: wider than a step's column, for five cards. */
export const HOME_WIDTH = 1128;

/** `chosenSite` when the person pressed "Another website". */
export const ANOTHER = "another-website";

/** A suggestion to finish before it starts: its goal has a gap in it. */
const GAP = "…";

/** Whether what was typed is a website's address rather than words. */
export function looksLikeAddress(text: string): boolean {
  return /^(https?:\/\/)?([a-z0-9-]+\.)+[a-z]{2,}(\/\S*)?$/i.test(text.trim());
}

/**
 * A website's own icon, when it serves one where icons are usually kept; its
 * first letter on its kind's colour otherwise, and until the icon arrives.
 * Never from a third party: only the website itself is asked.
 */
export function SiteIcon({ address, name, genre, size = 44 }:
                         { address: string; name: string; genre: string; size?: number }) {
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
                   background: `var(--pic-${kind}-tint)`, color: `var(--pic-${kind})` }}
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
  if (chosenSite === ANOTHER) return <There site={null} />;
  const chosen = sites.find((site) => site.id === chosenSite);
  return chosen ? <There site={chosen} /> : <Where />;
}

/* ---------------------------------------------------------------- where */

function Where() {
  const { sites, genres, profile, tiles, routines, chooseSite, startTask, startTile,
          startRoutine, setTilesOpen, openWelcome } = useStore();
  const [hour] = useState(() => new Date().getHours());
  const [typed, setTyped] = useState("");
  const words = typed.trim().toLowerCase();
  const matches = (site: CatalogueSite) =>
    !words || site.name.toLowerCase().includes(words)
    || hostOf(site.address).toLowerCase().includes(words)
    || site.genre.toLowerCase().includes(words);
  const found = sites.filter(matches);
  const address = looksLikeAddress(typed);
  const own = tiles.length + routines.length > 0;

  // The websites they chose in the setup first, then each kind.
  const favourites = sites.filter((site) => (profile.favourites ?? []).includes(site.id));
  const groups = [
    ...(favourites.length ? [{ genre: SITES.yours, sites: favourites.filter(matches) }] : []),
    ...genres.map((genre) => ({ genre,
                                sites: found.filter((site) => site.genre === genre) })),
  ].filter((group) => group.sites.length > 0);

  const go = () => {
    if (!words) return;
    if (address) {
      chooseSite(ANOTHER, typed.trim());
    } else if (found.length === 1) {
      chooseSite(found[0].id);
    } else if (found.length === 0) {
      // Not a website's name: something to do, routed as it always was.
      startTask(typed.trim());
    }
  };

  return (
    <div className="flex h-[calc(100dvh-162px)] flex-col gap-5 pt-3
                    short:h-[calc(100dvh-110px)] short:gap-3 short:pt-2" data-testid="home-where">
      <h1 className="text-center text-display font-semibold tracking-[-0.015em] text-ink
                     text-balance short:text-heading" data-testid="greeting">
        {greetingAt(hour, profile.name)}
      </h1>

      <div className="flex items-stretch gap-4">
        <div className="simba-field-frame flex min-w-0 flex-1 items-center gap-4 rounded-xl
                        py-1.5 pr-2 pl-6 shadow-card">
          <span className="shrink-0 text-soft" aria-hidden><SpeechIcon /></span>
          <input className="min-w-0 flex-1 bg-transparent py-3 text-lead text-ink outline-none
                            placeholder:text-soft focus-visible:outline-none short:py-2"
                 value={typed} onChange={(event) => setTyped(event.target.value)}
                 onKeyDown={(event) => event.key === "Enter" && go()}
                 placeholder={HOME.findPlaceholder} aria-label={HOME.find}
                 data-testid="ask-goal" />
          {words && (address || found.length <= 1) && (
            <Button size="md" wide={false} onClick={go} data-testid="home-go">
              {address || found.length === 1 ? HOME.go : HOME.start}
            </Button>
          )}
        </div>
        {/* Beside the box, not after the last card: a row of cards fewer,
            which is what fits every listed website into a 150% window. */}
        <button type="button" data-testid="another-site"
                onClick={() => chooseSite(ANOTHER, address ? typed.trim() : undefined)}
                className="flex shrink-0 items-center gap-3 rounded-xl border border-dashed
                           border-edge bg-surface px-5 text-left shadow-card
                           transition-[box-shadow,border-color,transform] duration-200
                           hover:border-accent/50 hover:shadow-lift active:translate-y-px">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg
                           bg-tint text-[28px] font-semibold leading-none text-accent"
                aria-hidden>
            +
          </span>
          <span className="text-small font-semibold leading-tight text-ink">
            {HOME.another}
          </span>
        </button>
      </div>

      {own && !words && (
        <section className="flex items-center gap-3" aria-label={HOME.yourTasks}
                 data-testid="own-tiles">
          <p className="shrink-0 text-small font-medium text-soft">{HOME.yourTasks}</p>
          <ul className="flex min-w-0 flex-1 gap-3 overflow-hidden">
            {tiles.map((tile) => (
              <li key={tile.id} className="min-w-0">
                <button type="button" onClick={() => startTile(tile)} data-testid="own-tile"
                        title={tile.label} className={OWN_TASK}>
                  <PictureChip kind={pictureForName(tile.label)} />
                  <span className="line-clamp-1 text-small font-semibold text-ink">
                    {tile.label}
                  </span>
                </button>
              </li>
            ))}
            {routines.map((routine) => (
              <li key={routine.id} className="min-w-0">
                <button type="button" onClick={() => startRoutine(routine)}
                        data-testid="own-routine" title={routine.label} className={OWN_TASK}>
                  <PictureChip kind={pictureForName(routine.label)} taught />
                  <span className="line-clamp-1 text-small font-semibold text-ink">
                    {routine.label}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <Button variant="quiet" size="md" wide={false} onClick={() => setTilesOpen(true)}
                  data-testid="change-tiles">
            {TILES.change}
          </Button>
        </section>
      )}

      {/* The cards scroll on their own when there are more than fit; the rest
          of the screen never does. */}
      <div className="-mx-2 flex min-h-0 flex-1 flex-wrap content-start gap-x-6 gap-y-4
                      overflow-y-auto px-2 pb-2 short:gap-y-2" data-testid="site-grid">
        {groups.map(({ genre, sites: inGenre }) => (
          <section key={genre} aria-label={genre} data-testid="site-genre"
                   className="flex flex-col gap-1.5 short:gap-1">
            <p className="text-small font-medium text-soft">{genre}</p>
            <ul className="flex gap-3">
              {inGenre.map((site) => (
                <li key={`${genre}-${site.id}`}>
                  <button type="button" data-testid="site" title={hostOf(site.address)}
                          aria-label={site.name}
                          onClick={() => chooseSite(site.id)} className={SITE_CARD}>
                    <SiteIcon address={site.address} name={site.name} genre={site.genre}
                              size={40} />
                    {/* Without a name's aside in brackets, which the kind above
                        the card already says: "(practice copy)". */}
                    <span className="line-clamp-2 text-small font-semibold leading-tight
                                     text-ink">
                      {site.name.replace(/\s*\([^)]*\)\s*$/, "")}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
        {words && found.length === 0 && !address && (
          <p className="w-full text-body text-soft" role="status" data-testid="no-match">
            {HOME.noMatch}
          </p>
        )}
      </div>

      <div className="flex items-center justify-between gap-4">
        <Button variant="quiet" size="md" wide={false} onClick={openWelcome}
                data-testid="change-settings">
          {HOME.settings}
        </Button>
        <AskEachSetting />
      </div>
    </div>
  );
}

const SITE_CARD =
  "flex h-[76px] w-[200px] items-center gap-3 rounded-xl border border-edge bg-surface px-3 "
  + "text-left shadow-card transition-[box-shadow,border-color,transform] duration-200 "
  + "hover:border-accent/50 hover:shadow-lift active:translate-y-px short:h-[66px]";

const OWN_TASK =
  "flex w-full min-w-0 items-center gap-3 rounded-xl border border-accent/40 bg-surface px-4 "
  + "py-1.5 text-left shadow-card transition-[box-shadow,border-color,transform] duration-200 "
  + "hover:border-accent hover:shadow-lift active:translate-y-px short:py-1";

/** The person's own setting: be asked before every move (2026-10-14). */
function AskEachSetting() {
  const { askEachTime, setAskEachTime } = useStore();
  return (
    <label className="flex cursor-pointer items-center gap-3 text-small text-soft">
      <input type="checkbox" className="h-5 w-5 accent-[var(--accent)]" checked={askEachTime}
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
  const { startTask, startRoutine, routines, chooseSite, setTeachOpen, history,
          anotherAddress } = useStore();
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
    const routine = task.routine ? routines.find((r) => r.id === task.routine) : undefined;
    if (routine && task.taught_on) {
      // Taught on a sister website (2026-11-13): run here.
      startTask(routine.label, undefined, undefined, routine.id, site.address);
    } else if (routine) {
      startRoutine(routine);
    } else if (task.goal.includes(GAP)) {
      // Something to finish first: "Find the price of the book …" goes in the
      // box, with the gap marked for typing over.
      setGoal(task.goal);
      const at = task.goal.indexOf(GAP);
      requestAnimationFrame(() => {
        box.current?.focus();
        box.current?.setSelectionRange(at, at + GAP.length);
      });
    } else {
      startTask(task.goal, task.flow, undefined, undefined,
                task.flow ? undefined : site.address);
    }
  };

  return (
    <div className="flex min-h-[calc(100dvh-150px)] flex-col justify-center gap-6
                    short:min-h-[calc(100dvh-104px)] short:gap-3" data-testid="home-there">
      <div className="flex items-center justify-between gap-4">
        <Button variant="quiet" size="md" wide={false} onClick={() => chooseSite(null)}
                data-testid="site-not-this">
          {SITES.notThis}
        </Button>
        {site && (
          <Button variant="quiet" size="md" wide={false}
                  onClick={() => setTeachOpen(true, site.address)} data-testid="site-show-here">
            {SITES.showHere}
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
          <Button size="md" wide={false} onClick={start} disabled={!ready}
                  data-testid="there-start">
            {HOME.start}
          </Button>
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
