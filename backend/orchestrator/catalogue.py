"""The websites SIMBA can work with, by genre (2026-11-13, the advisor's direction).

Adding a website is data, not code. Two files make the list:

- **`data/catalogue.json`**, committed: the sites SIMBA ships with, each with
  what it can do there and how — `built-in` (a written plan, run as `flow`) or
  `ai` (the AI planner works it out on the live page).
- **`data/catalogue.local.json`**, never committed: the sites the person or a
  helper added in the app ("Add a website"). Name, address and genre only; no
  task is written for them, because on a site nobody wrote a plan for, what
  SIMBA can do is whatever is asked for there.

Routines a helper taught (`routines.py`) are not written here. They are added
to the site they were taught on when the list is offered (`offered`), as tasks
done the way the helper showed — so the list and the tiles cannot disagree.

Nothing here opens a page or asks a model. An address is checked for its
shape only; whether a site may be used (robots.txt) is asked when a task
starts on it, not when it is listed.
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
from dataclasses import dataclass, field, replace
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from backend.orchestrator.vault import REPO

log = logging.getLogger("simba.catalogue")

DEFAULT_PATH = REPO / "data" / "catalogue.json"
LOCAL_PATH = REPO / "data" / "catalogue.local.json"

#: The ways SIMBA can do a task on a site.
HOWS = ("built-in", "ai", "taught")
#: The flows a built-in task can name.
FLOWS = ("registration", "billing", "railways")
#: Where a site whose genre is not one of the list goes.
OTHER = "Other"
#: The longest name a site keeps: one line in the list.
NAME_MAX = 40
#: How many sites a person can add. A list the person scrolls, not a database.
LOCAL_MAX = 30


class CatalogueError(ValueError):
    """A site that cannot be added. `reason` is a short code the overlay turns
    into words (`copy.ts`); the message is for the log."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class Task:
    label: str
    goal: str
    how: str
    flow: str | None = None
    routine: str | None = None
    #: A routine taught on another website (2026-11-13): that website's name.
    #: Run here, it is moved to this website (`routines.moved_to`).
    taught_on: str | None = None


@dataclass(frozen=True)
class Site:
    id: str
    name: str
    address: str
    genre: str
    tasks: tuple[Task, ...] = ()
    #: Added in the app, not shipped.
    added: bool = False
    #: Tried live, start to finish, on 2026-11-18 or later (BUGS.md, EVALUATION.md):
    #: the home screen marks it with a small badge (B2).
    tested: bool = False
    #: What SIMBA can do there is looking things up only: nothing is ordered,
    #: booked or sent, because the live run showed it does not work further.
    look_up_only: bool = False
    #: Left off the home screen's list (2026-11-18): the live runs showed it does
    #: not work yet. It still opens when its name or address is typed.
    hidden: bool = False
    #: How the website works, in a few plain lines (2026-11-18): given to the AI
    #: planner with the goal, never shown. Written from live runs.
    notes: str = ""

    @property
    def host(self) -> str:
        return host_of(self.address)


@dataclass
class Catalogue:
    genres: list[str] = field(default_factory=list)
    sites: list[Site] = field(default_factory=list)


def host_of(address: str) -> str:
    """The address's host and port, without a leading `www.`: what two
    addresses of one site share. The port counts: our practice copies are all
    on 127.0.0.1, one port each."""
    parts = urlsplit(address)
    host = (parts.hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    try:
        port = parts.port
    except ValueError:
        port = None
    return f"{host}:{port}" if port else host


# A web address as a person types it: optional scheme, a dotted host with a
# real top-level part of letters (so "14.382" is never one), or 127.0.0.1 /
# localhost with a port, then any path.
_ADDRESS = re.compile(
    r"^(?:(?P<scheme>https?)://)?"
    r"(?P<host>(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}"
    r"|127\.0\.0\.1|localhost)"
    r"(?P<port>:\d{2,5})?"
    r"(?P<rest>[/?#]\S*)?$",
    re.IGNORECASE,
)


def clean_address(typed: str) -> str:
    """A typed address made whole: `gov.uk/bank-holidays` becomes
    `https://gov.uk/bank-holidays`. Raises `CatalogueError("address")` for
    anything that is not a web address — a file, a script, a sentence."""
    text = (typed or "").strip()
    match = _ADDRESS.match(text)
    if match is None:
        raise CatalogueError("address", "not a web address")
    scheme = (match.group("scheme") or "").lower()
    host = match.group("host").lower()
    local = host in ("127.0.0.1", "localhost")
    if not scheme:
        scheme = "http" if local else "https"
    rest = match.group("rest") or "/"
    parts = urlsplit(f"{scheme}://{host}{match.group('port') or ''}{rest}")
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", parts.query, ""))


# An address inside a sentence ("bank holidays on gov.uk", "www.daewoo.com.pk
# bus times"): a dotted host ending in letters, at a word boundary.
_IN_SENTENCE = re.compile(
    r"(?<![@\w.])((?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,24}(?::\d{2,5})?(?:/[^\s,]*)?)",
    re.IGNORECASE,
)
# Words that look like hosts and are not: abbreviations people write.
_NOT_HOSTS = {"e.g", "i.e", "etc", "a.m", "p.m"}


def address_in(goal: str) -> str | None:
    """The first web address written inside a goal, made whole, or None."""
    for match in _IN_SENTENCE.finditer(goal or ""):
        candidate = match.group(1).rstrip(".?!)")
        if candidate.lower() in _NOT_HOSTS:
            continue
        try:
            return clean_address(candidate)
        except CatalogueError:
            continue
    return None


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:24] or "site"


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        # A damaged file is fewer sites, not a dead home screen.
        log.warning("catalogue: %s could not be read: %s", path.name, type(error).__name__)
        return {}


def _task(row: object) -> Task | None:
    if not isinstance(row, dict):
        return None
    label, goal, how = row.get("label"), row.get("goal"), row.get("how")
    flow = row.get("flow")
    if not (isinstance(label, str) and isinstance(goal, str) and how in HOWS):
        return None
    if how == "built-in" and flow not in FLOWS:
        return None
    if how != "built-in":
        flow = None
    return Task(label=label.strip(), goal=goal.strip(), how=how, flow=flow)


def _site(row: object, genres: list[str], added: bool) -> Site | None:
    if not isinstance(row, dict):
        return None
    try:
        address = clean_address(str(row.get("address", "")))
    except CatalogueError:
        return None
    name = " ".join(str(row.get("name", "")).split())[:NAME_MAX]
    if not name:
        return None
    genre = row.get("genre") if row.get("genre") in genres else OTHER
    tasks = tuple(task for task in map(_task, row.get("tasks") or []) if task is not None)
    site_id = str(row.get("id") or _slug(name))
    notes = " ".join(str(row.get("notes") or "").split())[:900]
    return Site(id=site_id, name=name, address=address, genre=genre, tasks=tasks, added=added,
                tested=row.get("tested") is True and not added,
                look_up_only=row.get("look_up_only") is True,
                hidden=row.get("hidden") is True and not added, notes=notes)


class CatalogueStore:
    """The shipped list and the person's additions, read fresh every time: the
    files are small, and a second SIMBA window must see a site the first added."""

    def __init__(self, path: Path | None = None, local: Path | None = None) -> None:
        self.path = Path(path or os.environ.get("SIMBA_CATALOGUE") or DEFAULT_PATH)
        self.local = Path(local or os.environ.get("SIMBA_CATALOGUE_LOCAL") or LOCAL_PATH)

    def load(self) -> Catalogue:
        shipped = _read(self.path)
        genres = [g for g in shipped.get("genres") or [] if isinstance(g, str)]
        sites: list[Site] = []
        seen: set[str] = set()
        for added, rows in ((False, shipped.get("sites")), (True, _read(self.local).get("sites"))):
            for row in rows or []:
                site = _site(row, genres, added)
                if site is None or site.id in seen:
                    continue
                seen.add(site.id)
                sites.append(site)
        if any(site.genre == OTHER for site in sites) and OTHER not in genres:
            genres.append(OTHER)
        return Catalogue(genres=genres, sites=sites)

    def find(self, site_id: str | None) -> Site | None:
        if not site_id:
            return None
        return next((site for site in self.load().sites if site.id == site_id), None)

    def for_address(self, address: str) -> Site | None:
        """The listed site an address belongs to, by host, or None."""
        host = host_of(address)
        return next((site for site in self.load().sites if site.host == host), None)

    def named_in(self, goal: str) -> Site | None:
        """The listed site a goal names in words (2026-11-16): "price of the
        book alchemist on readings" is for Readings. By the site's full name,
        or by its one-word id ("readings", "olx", "wikipedia") as a whole word.
        None when no site is named, or when two are: a goal that names two
        websites is not decided here."""
        text = " ".join(re.findall(r"[a-z0-9]+", (goal or "").lower()))
        if not text:
            return None
        padded = f" {text} "
        found: list[Site] = []
        for site in self.load().sites:
            name = " ".join(re.findall(r"[a-z0-9]+", site.name.lower()))
            word = site.id if site.id.isalpha() and len(site.id) >= 3 else None
            if (name and f" {name} " in padded) or (word and f" {word} " in padded):
                found.append(site)
        return found[0] if len(found) == 1 else None

    def add(self, name: str, address: str, genre: str) -> Site:
        """A site added in the app. Raises `CatalogueError` with a reason the
        overlay can say: `name`, `address`, `listed` (already in the list),
        `full`."""
        name = " ".join((name or "").split())[:NAME_MAX]
        if not name:
            raise CatalogueError("name", "no name")
        address = clean_address(address)
        catalogue = self.load()
        if any(site.host == host_of(address) and urlsplit(site.address).path
               == urlsplit(address).path for site in catalogue.sites):
            raise CatalogueError("listed", "already in the list")
        rows = list(_read(self.local).get("sites") or [])
        if len(rows) >= LOCAL_MAX:
            raise CatalogueError("full", "the list of added sites is full")
        site_id = f"{_slug(name)}-{secrets.token_hex(3)}"
        row = {"id": site_id, "name": name, "address": address,
               "genre": genre if genre in catalogue.genres else OTHER}
        rows.append(row)
        self._write(rows)
        log.info("catalogue: a site added (%s)", host_of(address))
        site = _site(row, catalogue.genres + [OTHER], added=True)
        assert site is not None
        return site

    def remove(self, site_id: str) -> bool:
        """Takes off a site the person added. A shipped site cannot be."""
        rows = list(_read(self.local).get("sites") or [])
        kept = [row for row in rows if not (isinstance(row, dict) and row.get("id") == site_id)]
        if len(kept) == len(rows):
            return False
        self._write(kept)
        return True

    def clear(self) -> None:
        """"Forget me and start again": the sites the person added go too."""
        try:
            self.local.unlink()
        except FileNotFoundError:
            pass

    def _write(self, rows: list) -> None:
        self.local.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.local.with_suffix(".tmp")
        temporary.write_text(json.dumps({"sites": rows}, indent=2), encoding="utf-8")
        temporary.replace(self.local)


def offered(catalogue: Catalogue, routines: list | None = None) -> list[Site]:
    """The sites as the home screen lists them: each routine a helper taught is
    added to the site it was taught on, by host, as a task done "taught". A
    routine on a site that is not listed stays a tile only.

    And to every other listed site of the same genre, marked with where it was
    taught (2026-11-13, "one taught routine may move from one website to
    another"): a bill taught on one electricity company's page is offered on
    another's. Run there, every move is still found by role and label and
    checked; a site laid out differently stops honestly."""
    shown = [site for site in catalogue.sites if not site.hidden]
    if not routines:
        return shown
    by_host = {site.host: site for site in catalogue.sites}
    here: dict[str, list[Task]] = {}
    elsewhere: dict[str, list[Task]] = {}
    for routine in routines:
        host = host_of(getattr(routine, "start", ""))
        here.setdefault(host, []).append(
            Task(label=routine.label, goal=routine.label, how="taught", routine=routine.id))
        origin = by_host.get(host)
        if origin is None:
            continue
        for site in catalogue.sites:
            if site.host != host and site.genre == origin.genre:
                elsewhere.setdefault(site.host, []).append(
                    Task(label=routine.label, goal=routine.label, how="taught",
                         routine=routine.id, taught_on=origin.name))
    # Every field is kept (the Tested badge, "look up only"), not only the first few.
    return [replace(site, tasks=site.tasks + tuple(here.get(site.host, ()))
                    + tuple(elsewhere.get(site.host, ())))
            for site in shown]
