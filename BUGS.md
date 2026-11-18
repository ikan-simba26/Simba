# SIMBA bug list

One row per bug: id, steps, expected, actual, status. Found by the team, or by
a live run in the real window (`run.ps1`, driven over the debug port). Every
bug is reproduced live before it is fixed and marked fixed only after the same
steps pass live. Dates are 2026.

Status: **open** · **reproduced** (seen live, not fixed) · **fixed** (proved live) · **wontfix** (with why)

---

## From the team (18 Nov)

### B1 — Date selection picks the wrong year
- **Steps:** (a) the AI planner on a site with a date box, goal "… from 5 January 2028": `llm_loop.goal_date("Book a hotel from 5 January 2028", "dd-MM-yyyy")`. (b) The train search, goal "Find trains from Lahore to Karachi on 25 November 2026", read the sentence before the search.
- **Expected:** the date in the goal becomes one exact date from today's date (2026-11-18) before anything is done; a calendar is read for its shown month and year and moved until they match; the box is read back and checked; never a past date; the read-back says the full date with the year.
- **Actual (18 Nov, live + direct):**
  1. `goal_date` ignores a year written in the goal: "5 January 2028" is typed as `05-01-2027`. It also finds nothing in "25 Nov 2026", "tomorrow", "2026-11-30", "30/11", so those are left to the person or the model's guess.
  2. The read-back drops the year when it is this year: "Lahore Jn. to Karachi City, Wednesday 25 November." (a next-year date says "… 2027").
  3. The train calendar presses "Next Month" a fixed number of times counted from today, assuming the picker opens on today's month, and reads the month shown only once after the presses; a different starting month ends as "wrong month" instead of moving on.
  4. Live Pakistan Railways, "3 January" → `03-01-2027` was correct; the wrong-year case was not reproduced on that site, only the three causes above.
- **Fix (18 Nov):** `llm_loop.goal_date` now uses the one shared reader (`details.find_day`): keeps the year, understands "tomorrow", weekdays, "25 Nov", ISO and 25/11, never returns a past or impossible day; the trip calendar reads the shown month and year (`teach.shown_month`) and presses Next/Previous Month by the difference, three corrections at most; the box is read back after choosing (`_search` already refuses a form whose date is not the one chosen); every read-back says the year (`voice.day_words`).
- **Proof live (real window, Pakistan Railways):** "…25 November 2026" read back as "Wednesday 25 November 2026" and the site held `25-11-2026`; "…3 January" read back "Sunday 3 January 2027", site held `03-01-2027`; after Change, "Lahore Cantt to Karachi City, Wednesday 25 November 2026", site held `LAHORE CANTT / KARACHI CITY / 25-11-2026`. Tests: 158 passed (trip, answers, checklist, open goal, llm loop, routine run) incl. new ones for a calendar a month or a year off and for the year in a goal.
- **Status:** fixed

### B2 — Users can't tell how many websites SIMBA can use
- **Steps:** open the home screen.
- **Expected:** "Works on any website. These are tested." with a small badge on tested sites and the count shown.
- **Actual (18 Nov, live):** only "Or pick a website … See all 30"; nothing says any website works, nothing marks which are tested.
- **Fix (18 Nov):** the heading line is "Works on any website. These are tested." with "30 websites listed · 3 tested" beside it; `tested` (additive, in `data/catalogue.json`) gives a site a small "Tested" badge, and a tested site comes first in its kind on the first screen. Only sites tried live start to finish carry it (updated in Step 3 and 5).
- **Proof live:** home screen in the real window shows the line, the count and the badge on Pakistan Railways and Readings (picture in `.scratch/live/shots/b2-home2.png`). Test: `frontend/test_sites.py` (badge count equals the tested sites; none on an untried one).
- **Status:** fixed

### B3 — No way back to a previous step; it starts all over
- **Steps:** start any task with several answers (a train: from, to, day) and look at "So far".
- **Expected:** each finished step in "So far" has a Change button: keep the other answers, go back to that point on the site (by replaying the earlier answers), ask that one again, continue. Not after Do it.
- **Actual (18 Nov, live):** "So far" is a plain list ("Lahore Jn", "Karachi City", "Yes, that's right"); the only way to change one is to stop and begin again.
- **Fix (18 Nov):** each answer in "So far" has a Change button until something is done on the website (Do it / Pay now), the task ends or a help-me step is open. Pressing it ends the task on screen and starts it again on the same website with every other answer kept (`task.start.keep_answers`, additive, in `shared/schema.*`); the backend answers each matching question by the kept answer (found by the button's words, never by position), and never a final screen, a read-back or a secret; the changed question is asked again and its chip goes back where it was.
- **Proof live (Pakistan Railways):** answered "Lahore Jn." and "Karachi City", pressed Change on Lahore: only "Which Lahore station" was asked again, Karachi City stayed, chosen "Lahore Cantt" gave the read-back "Lahore Cantt to Karachi City, Wednesday 25 November 2026", the site held `LAHORE CANTT / KARACHI CITY / 25-11-2026`. First attempt failed: `task.cancel` is ignored while a question is open, so it did not restart; fixed by answering the open question with Stop first. Tests: `backend/orchestrator/test_keep_answers.py` (8), `frontend/test_change_answer.py` (4).
- **Status:** fixed

### B4 — It fills only the first option and ignores the rest of the page
- **Steps:** on Readings, goal "Order me an alchemist book on Readings"; and any form with several required fields.
- **Expected:** the whole page is read (scrolled so lazy content loads) before choosing; every real option is shown as "Which one?" cards; the first is never taken unless it is the only one; every required field of a form is filled.
- **Actual (18 Nov, live):** the first 6 tiles of the page were read, in page order, *before* the goal's words were looked at, so a match further down never reached the person; lazy-loaded tiles were never loaded; see B5 for what the cards held. A form's required fields: to be checked on the live sites (Step 3).
- **Fix (18 Nov):** `cards.read_whole_page` scrolls the page (once per address) so lazy tiles load; `find_cards` reads up to 60 tiles; `llm_loop.cards_about` keeps those about the goal (most words first) and up to 12 are shown as "Which one?"; the model's prompt says never to take the first of several matches.
- **Proof live (Readings):** searched "The Alchemist", then "Which one?" showed 12 matches with price, none taken for the person. Tests: `backend/orchestrator/test_which_one.py` (5, incl. a page whose tiles load only on scroll: 10 → 30 found).
- **Status:** fixed (cards). Required fields of a form: see Step 3.

## Found by the live smoke test (18 Nov)

### B5 — "Which one?" offers the home page's New Releases instead of the search results
- **Steps:** real window, goal "Order me an alchemist book on Readings", press "Yes, go ahead".
- **Expected:** it searches Readings for "alchemist" and shows the books it finds.
- **Actual:** four cards of the home page's "New Releases" strip (Laws, The Last Days Of Socrates, The Dialogues Of Plato, Gitnajali), none about an alchemist, with no search done. The page held 12 such books; only 4 reached the cards. Found at the smoke test; I stopped the run.
- **Cause:** the goal's "Readings" matched the titles "(Readings Classics)" (the site's own name counted as a topic), and no search had been done yet.
- **Fix (18 Nov):** the website's own name (address, start of the page title) is never a topic word (`cards_about`).
- **Proof live (Readings):** the same goal searched first and showed matches about an alchemist (see B4).
- **Status:** fixed

### B6 — Home screen's "My bookings" shows a card named "g"
- **Steps:** open the home screen.
- **Expected:** a booking card has a real title.
- **Actual:** the first card reads "g" (a stored test booking in `data/bookings.json`).
- **Status:** not reproduced after restart (the card is a stored test booking in `data/bookings.json`, which is not committed; Raham flagged it himself on 17 Nov).

### B7 — Three tests fail on main, independent of this work
- `test_calm_planner::test_a_box_for_the_persons_own_details_is_theirs_to_type` passed only on a machine with no kept name (it read the real `data/profile.json`) and pinned old wording. **Fixed** (isolated with `SIMBA_PROFILE`, wording updated).
- `test_copy::test_nothing_in_the_backend_writes_its_own_way_to_stop`: `loop.py` and `llm_loop.py` write `kind="secondary"` outside `voice.py`. Same count on main. **Open.**
- `test_first_screen::test_an_empty_box_looks_ready_to_type_in` (border 1px, expected 2px). Not checked on main. **Open.**

---

## Live-site runs (Step 3) — 18 November, real window, one realistic task each

| Site | Task | Result | Bug found |
|---|---|---|---|
| Pakistan Railways | trains Lahore to Karachi, 25 Nov 2026 | works (1 train, 26 h 20 min) | W1 |
| Readings | price of "The Alchemist" | works: searches, "Which one?" with 12 editions | W2 |
| OLX | price of a used laptop | works after fix: "Rs 33,000" | O1, O2 |
| PakWheels | find a used Suzuki Alto | works after fix | P1 |
| Zameen | house to rent in Lahore | works: "6,673 houses for rent" | — |
| Dawn (news, added) | top story | works | — |
| Wikipedia | who wrote The Alchemist | answers "Paulo Coelho" in some runs; stops on the disambiguation page in others | K1 |
| IESCO bill (live) | look up a bill | stops at an image CAPTCHA, handed to the person (correct); wording was wrong, fixed | I1 |
| PIA flights | Lahore to Karachi | stops at a bot check for the person (correct) | — |
| Chughtai Lab | price of a CBC test | wanders to "Book a Test", stopped by the final screen; nothing changed | C1 |
| FBR | how to get a tax number | a menu link named "Register…" counts as a change (final screen), or it stalls | F1 |
| NUST | admission requirements | the website does not load (Chrome error page) | N1 |

- **W1 (Railways, serious).** In a batch of three runs the first station-typing step was marked "not done" within 2 s and SIMBA stopped ("The site didn't offer me any stations"), for Lahore Jn. and Lahore Cantt alike, after four earlier passes. By hand the live list opens. After a fresh restart of the window and backend it passed again. Cause not found; the failures began after hours of one window. Treat a long-running window as suspect. **Open (see EVALUATION.md for the re-runs).**
- **W2 (Readings).** The model "asked" which edition on the front page before searching, and the run stopped. **Fixed in code** (sent back to search twice before giving up), re-run numbers in EVALUATION.md.
- **O1 (OLX).** The search box label "Find Cars, Mobile Phones and more" was read as a request for the person's phone number: it asked instead of searching and never pressed Enter. **Fixed**, test added.
- **O2 (OLX).** After searching, a drop-down with many options asked "Which one? one". **Open** (it still finishes the look-up).
- **P1 (PakWheels).** The model asked which ad; there was no drop-down, so the run stopped. **Fixed:** a list of ads or open suggestions becomes "Which one?" cards or buttons.
- **K1 (Wikipedia).** On a disambiguation page the choices are links, not options, so there is nothing to show. **Open.**
- **I1 (IESCO).** "Enter CAPTCHA code" was shown as "Type the code the website sent to your phone." **Fixed:** a picture CAPTCHA is its own kind, shown with its picture and box.
- **C1 (Chughtai).** (a) The planner typed the person's saved email into a newsletter box on a look-up and queued "Book a Test"; the final screen stopped it and nothing was sent. **Fixed:** a look-up never types the person's details. (b) It still wanders to Book buttons. **Open.**
- **F1 (FBR).** The default-deny rule treats any press with "register" as a change. Left as it is; flagged for review.
- **N1 (NUST).** Not our bug: the page does not load. Hidden/marked in the catalogue.
- **Harness note.** A minimised window makes SIMBA wait ("I waited while the window was closed"); my runner restores it.
