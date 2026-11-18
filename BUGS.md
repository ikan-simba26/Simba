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
- **Status:** reproduced (1–3), fixed → see below

### B2 — Users can't tell how many websites SIMBA can use
- **Steps:** open the home screen.
- **Expected:** "Works on any website. These are tested." with a small badge on tested sites and the count shown.
- **Actual (18 Nov, live):** only "Or pick a website … See all 30"; nothing says any website works, nothing marks which are tested.
- **Status:** reproduced

### B3 — No way back to a previous step; it starts all over
- **Steps:** start any task with several answers (a train: from, to, day) and look at "So far".
- **Expected:** each finished step in "So far" has a Change button: keep the other answers, go back to that point on the site (by replaying the earlier answers), ask that one again, continue. Not after Do it.
- **Actual (18 Nov, live):** "So far" is a plain list ("Lahore Jn", "Karachi City", "Yes, that's right"); the only way to change one is to stop and begin again.
- **Status:** reproduced

### B4 — It fills only the first option and ignores the rest of the page
- **Steps:** on Readings, goal "Order me an alchemist book on Readings"; and any form with several required fields.
- **Expected:** the whole page is read (scrolled so lazy content loads) before choosing; every real option is shown as "Which one?" cards; the first is never taken unless it is the only one; every required field of a form is filled.
- **Actual (18 Nov, live):** see B5 for the cards. A form's required fields: to be checked on the live sites (Step 3).
- **Status:** reproduced (cards); forms to check

## Found by the live smoke test (18 Nov)

### B5 — "Which one?" offers the home page's New Releases instead of the search results
- **Steps:** real window, goal "Order me an alchemist book on Readings", press "Yes, go ahead".
- **Expected:** it searches Readings for "alchemist" and shows the books it finds.
- **Actual:** four cards of the home page's "New Releases" strip (Laws, The Last Days Of Socrates, The Dialogues Of Plato, Gitnajali), none about an alchemist, with no search done. The page held 12 such books; only 4 reached the cards. Found at the smoke test; I stopped the run.
- **Status:** reproduced

### B6 — Home screen's "My bookings" shows a card named "g"
- **Steps:** open the home screen.
- **Expected:** a booking card has a real title.
- **Actual:** the first card reads "g" (a stored test booking in `data/bookings.json`).
- **Status:** open (data, not code: to be checked)

---

## Live-site runs (Step 3)

*(filled in as each site is tried)*
