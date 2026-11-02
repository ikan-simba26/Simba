# The rating forms: step by step

**Making Set 3?** Go to section 7. Sections 1 to 6 are Sets 1 and 2, and Set 3
has its own folder, so nothing in them needs doing again.

This folder becomes two Google Forms, **Set 1** and **Set 2**, that people
fill in on their own computer in about 5-7 minutes: a consent question, three
questions about them, two worked examples, then 30 pictures of web pages,
one per page, each with one question — "How overwhelming does this page
feel?" — and five answers: Not at all / A little / Somewhat / Very /
Extremely.

The 50 pages are split between the two forms, 25 each, so that both have a
similar spread of calm and heavy pages. Each form also shows three pages
from the other form (the anchors, the same six pages for everyone, so the
two groups of raters can be checked against each other) and two of its own
pages a second time (the repeats, so we can see how consistent each person
is): 25 + 3 + 2 = 30. Half the raters get Set 1 and half Set 2. Their answers
come back as two CSVs that `tools/rating/from_form.py` turns into
`data/ratings.jsonl` for the estimator. Why the forms are like this, and
what it costs: DECISIONS.md, *Two sets of 30*.

What is in the folder:

- `P01.png` to `P50.png`: the 50 pages. `P51.png` and `P52.png`: Set 1's
  repeats; `P53.png` and `P54.png`: Set 2's.
- `E1.png` and `E2.png`: the two worked examples, a calm page and a cluttered
  one, neither of them among the 50.
- `mapping.json`: which page each picture is, which pictures each set shows
  and in what order, the examples, and every question's wording. The form
  script reads it. A copy is committed as `data/rating/form.json`.
- `make_form.gs`: the script that makes the two forms.
- `README.md`: this.

## 1. Make the folder (already done if you can read this)

From the repository root:

    backend\venv\Scripts\python -m tools.rating.export_form

It writes everything here, and prints each set's anchors and repeats. Run it
again only if the pictures were recaptured, and never once a form has
answers, because the names would point to different pictures. (The examples
come from `python -m tools.rating.examples`, run once; the export refuses to
run without them.)

## 2. Upload it to Google Drive

1. Open <https://drive.google.com> with the account that should own the forms.
2. **New → Folder upload**, and choose this `rating-form` folder. Wait until
   all 59 files are uploaded.
3. Open the folder in Drive. Its address ends in `/folders/` and a long id,
   for example `.../folders/1AbCdEf...`. Copy the id, the part after
   `/folders/`.

If you uploaded an earlier version of this folder, delete it from Drive
first (and any form made from it, "SIMBA rating form A" or "B"), and upload
this one: the earlier `mapping.json` has no sets.

## 3. Make the two forms

1. Open <https://script.google.com> and press **New project**.
2. Click "Untitled project" at the top and name it "SIMBA rating form".
3. Delete everything in `Code.gs` and paste in the whole of `make_form.gs`.
4. On the line `const FOLDER_ID = 'PASTE-THE-FOLDER-ID-HERE';` replace
   `PASTE-THE-FOLDER-ID-HERE` with the id you copied. Keep the quotes.
5. Press **Save** (the disk icon).
6. In the toolbar, choose the function `makeFormSet1` and press **Run**.
7. Google asks for permission the first time: **Review permissions**, choose
   your account, then (because the script is yours and unpublished)
   **Advanced → Go to SIMBA rating form (unsafe) → Allow**. It needs your
   Drive, to read the pictures, and your Forms, to make the form.
8. Wait, about a minute; the log at the bottom counts the pictures. When it
   says **Done: Set 1**, it gives two links: one to edit the form, and the
   one to send to raters. Copy both somewhere, labelled Set 1.
9. Choose the function `makeFormSet2` and press **Run**. Copy its two links,
   labelled Set 2.

Both forms are saved into the same Drive folder, as "SIMBA rating form, Set 1"
and "SIMBA rating form, Set 2". Raters see the same title on both.

If it stops with an error, read the message: it names the missing file or
setting. If it stopped halfway, delete the half-made form from Drive and run
it again.

## 4. Check both before anyone sees them

Do all of this for Set 1, then again for Set 2.

1. Open the edit link, then press the **Preview** (eye) icon. Go through the
   whole form on a laptop. Check that:
   - "About 5-7 minutes" is at the top, under the title;
   - answering "No" to consent ends the form;
   - the page after "About you" shows the two examples, each picture with
     its sentence and its answer (Not at all, then Very);
   - every picture appears above its question, is readable, and the
     question has all five answers in order;
   - the progress bar moves as you go;
   - there are 30 pictures ("Picture 30 of 30" on the last).
2. In the form's **Settings**:
   - **Presentation → Show progress bar**: on (the script turns it on; check).
   - **Responses → Collect email addresses**: *Do not collect*.
   - **Responses → Limit to 1 response**: off (it would make raters sign in).
   - If you use a university Google account: **Responses → Restrict to users
     in your organisation**: off, unless every rater is at the university.
3. Do not edit, move or retitle the rating questions, or change their
   answers' words. The `[P07]` at the end of each title is how the answers
   are matched to pictures, and the words are how they are turned into 1 to
   5. Wording at the top of the form can be changed freely.
4. Delete the test answers you made in preview: **Responses → ⋮ → Delete all
   responses**.

## 5. Send them

In each form press **Send → the link icon**, tick **Shorten URL**, and copy
the link. **Give each rater one link, alternating: the first person Set 1,
the next Set 2, and so on**, so the two forms get about the same number of
people. Never send anyone both. When you send it, ask people to:

- use a laptop or desktop computer, not a phone (phone answers are not used);
- do it in one go, somewhere quiet; it takes about 5-7 minutes;
- not talk to anyone else about their answers until they have finished.

**How many people.** Every page needs at least **8 ratings** before the
estimator can be trained. A page in one set is rated only by that set's
raters, so that is **at least 8 usable raters per set, 16 in all**, and in
practice a few more, because some responses are dropped (step 6). Raters in
person count too: odd rater numbers rate Set 1 and even numbers Set 2
(`RUNNING.md`).

Keep a note of how many people you sent each form to and when, for the
write-up.

## 6. Bring the answers back

1. In the Set 1 form, **Responses → ⋮ → Download responses (.csv)**. Google
   gives a `.zip`; open it and save the `.csv` inside as
   `.scratch/rating-form/responses-1.csv`. Do the same in Set 2, saving it
   as `.scratch/rating-form/responses-2.csv`.
2. From the repository root:

        backend\venv\Scripts\python -m tools.rating.from_form .scratch/rating-form/responses-1.csv .scratch/rating-form/responses-2.csv

   It works out which set each file is from by its questions, and refuses a
   file whose questions are in neither set's order. If that happens, name
   the set yourself, e.g. `2=.scratch/rating-form/responses-2.csv`. It
   prints, for each set, how many responses there were and how many are
   usable; who was dropped and why (did not agree, on a phone, or
   incomplete); and, counting every rating in `data/ratings.jsonl` (in
   person too), how many pages still have fewer than 8 ratings, how many
   more ratings that is, and **how many more raters of each set** it takes.
   Every row records its rater's set. It can be run again whenever more
   answers come in, with one file or both; it replaces the online rows of
   the sets it is given and keeps the rest. Do not delete responses from a
   form between runs: raters are numbered by their row.
3. When it says every page has at least 8 ratings:

        backend\venv\Scripts\python -m backend.estimator.train

   Before anything is fitted, it reports how far the raters agree, and
   whether the two groups rate the six anchor pages alike. If it refuses,
   it says how many more ratings, and raters of each set, are needed.

   Or do steps 2 and 3 in one command, with the comparison against the rules
   as well: `RUNNING.md`, *Retraining the estimator*.

The CSVs and `data/ratings.jsonl` hold people's answers. Neither is committed;
keep them on this machine.

## 7. Set 3: Pakistani pages

Set 3 is a third form, about **3-4 minutes**: 20 pictures, with the same question,
the same five answers, the same two worked examples and a progress bar. Fifteen are
pictures of Pakistani public pages, three are anchors already rated in Sets 1 and 2,
and two are repeats. Why it exists: EVALUATION.md, 2026-11-02b and 2026-11-02c. Sets
1 and 2 are not touched: leave those forms as they are.

### Make it

1. `.scratch/rating-form-set3/` is the folder, 25 files: the 20 pictures, `E1.png`,
   `E2.png`, `mapping.json`, `make_form.gs` and this README. If it is not there, make
   it from the repository root, which changes nothing else:

       backend\venv\Scripts\python -m tools.rating.export_set3

2. In <https://drive.google.com>, press **New → Folder upload** and choose
   `rating-form-set3`. Wait until all 25 files are uploaded. Open the folder and copy
   its id, the part of its address after `/folders/`.
3. In <https://script.google.com>, open the "SIMBA rating form" project from before,
   or make a new one and paste in the whole of `make_form.gs`. If you kept the old
   project, paste this `make_form.gs` over the old one: the old one has no Set 3.
4. On the line `const FOLDER_ID = '...';` put in the new folder's id. Keep the quotes.
   Press **Save**.
5. In the toolbar, choose the function **`makeFormSet3`** and press **Run**. Allow it
   if Google asks, as in section 3.
6. Wait about a minute. When the log says **Done: Set 3**, copy its two links, labelled
   Set 3. The form is saved in the same Drive folder as "SIMBA rating form, Set 3".

### Check it

Do everything in section 4, with these differences:

- the top of the form says **"About 3-4 minutes"**, and so does the consent question,
  which also says 20 pictures;
- there are **20** pictures, and the last says "Picture 20 of 20";
- the two examples are the same two as the other forms.

### Send it

Send the link as in section 5: laptop or desktop, in one go, somewhere quiet.
**Anyone may do Set 3, including people who did Set 1 or Set 2**, but ask them only
once. Keep a note of who has already rated, because that belongs in the write-up.
Every page needs **8 ratings**, and these pages are only in Set 3, so that is **at
least 8 usable raters, and in practice 10**. Set 2 also still needs **3 more** usable
raters, so the whole comparison needs those too.

If you can reach anyone older, or anyone who is not in computing, they are worth more
than another student: 13 of the 15 raters so far are 18 to 24, and 10 are in computing.

### Bring the answers back

1. In the Set 3 form, **Responses → ⋮ → Download responses (.csv)**. Open the `.zip`
   and save the `.csv` as `.scratch/rating-form/responses-3.csv`. Download Sets 1 and 2
   again as well, if any answers have come in.
2. From the repository root, one command does everything:

       backend\venv\Scripts\python -m backend.estimator.train_visual "SIMBA rating form, Set 1.csv" "SIMBA rating form, Set 2.csv" .scratch/rating-form/responses-3.csv

   It works out each file's set from its questions (name one with `3=path.csv` if it
   cannot), and **refuses until every page has 8 ratings, saying how many more raters of
   which set**. Run it again whenever more answers come in. When there are enough, it
   compares the old model, the new one and the new features alone on the same pages and
   folds, and works the overwhelm index out again from what was saved.
3. Read **the gate** at the end of what it prints, which is also added to EVALUATION.md.
   Whatever it says, `data/estimator.json` is unchanged and SIMBA goes on running the
   same model. Add `data/estimator_visual.json` and EVALUATION.md by name. The CSVs and
   `data/ratings.jsonl` are never committed.

To see the sums on the ratings there already, with no Set 3 and writing only to
`.scratch/`: `backend\venv\Scripts\python -m backend.estimator.train_visual --preview`.
