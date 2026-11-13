# Why SIMBA is a desktop app, not a website

*For the FYP report. Written 2026-11-13, when SIMBA was first packaged as a
Windows installer (`tools/build_installer.py`).*

SIMBA does web tasks for people who find cluttered websites overwhelming. It
could look as if that belongs on the web: a site someone opens in their browser.
It cannot be one, for four reasons, each of them a property of what SIMBA *does*
rather than a preference.

**1. It drives a real browser, on the person's own computer.** SIMBA does not
describe what to do on a site; it does it. The real website is loaded in a
browser view inside SIMBA's own window, and the backend drives that view through
the Chrome DevTools Protocol (CDP) with Playwright: it reads the page, clicks,
types, and checks after every action that the page changed the way the plan
expected. CDP is a debugging interface on the local machine (`127.0.0.1`). A web
page cannot open it, and no browser lets a website reach into another tab and
press its buttons — that boundary is the browser's most basic security rule, and
SIMBA would need to break it on every step. A desktop app owns its browser view,
so the boundary is not crossed: the view is SIMBA's.

**2. The site is covered, not hidden.** The person never sees the cluttered
site; they see one plain step at a time. The obvious way to do that — hide the
site — does not work: a browser view marked invisible stops repainting, and the
screenshots SIMBA shows as proof failed 3 times in 5 (`CLAUDE.md`, architecture
constraints). SIMBA instead keeps the site view fully visible to the browser
engine at a fixed 1280×800 and lays its own overlay on top of it, which captured
20 of 20. Arranging two views in one window like that is something only the
application that owns the window can do; a web page has no control over another
page's rendering at all.

**3. Credentials stay on the computer.** SIMBA can sign in for the person. The
details are kept in a file encrypted with Windows' own per-account protection
(DPAPI, `backend/orchestrator/vault.py`), typed straight into the page by the
backend, and never shown to the language model or written to a log. As a desktop
app, those details never leave the person's machine. As a hosted service they
would have to be sent to, and kept on, someone else's server — exactly the thing
a person who finds the web hard to trust should not have to accept.

**4. A hosted site could not drive the person's own browser anyway.** The only
way a hosted SIMBA could act on websites is to run its own browser on a server
and stream it. Then the bank, the utility company or the college sees a
data-centre address instead of the person's own connection and their own
signed-in session; sites block such traffic, ask for extra checks, or both.
Running locally, SIMBA acts from the person's own computer, as the person
would.

## What being a desktop app costs

- **An installer.** `SIMBA-Setup-<version>.exe`, built by
  `tools/build_installer.py`: the Electron app plus an embedded Python 3.12 with
  the backend's packages, no separate Python install needed. About 200 MB to
  download (EVALUATION.md, 2026-11-13).
- **The installer is not code-signed.** Windows SmartScreen therefore shows
  "Windows protected your PC" the first time it is run; the person has to press
  *More info*, then *Run anyway*. Signing needs a paid certificate tied to a
  registered organisation, which a student project does not have; for the
  evaluation sessions we run the installer ourselves on the machine used. A
  product release would buy one, and the warning goes away.
- **One machine, one person.** There is no account and no sync: what SIMBA
  learns (tiles, routines, saved sign-ins) stays in the person's own profile
  folder, `%APPDATA%\SIMBA`.
- **Local ports.** The browser's debugging port and the backend's port are
  chosen at random on every launch and bound to `127.0.0.1` only, so nothing
  outside the computer can reach them and two launches never share one. A
  program already running on the same computer as the same user could still
  find them; that is the same trust boundary every desktop app has.
