# The rating form: step by step

This folder becomes two Google Forms, A and B, that people fill in on their
own computer: a consent question, three questions about them, then 55
pictures of web pages, one per page, each rated from 1 to 7. The two forms
are the same except for the order of the pictures: B shows them in the
reverse of A's order, so that tiredness late in the form does not always fall
on the same pages. Half the raters get A and half get B. Their answers come
back as two CSVs that `tools/rating/from_form.py` turns into
`data/ratings.jsonl` for the estimator.

What is in the folder:

- `P01.png` to `P50.png`: the 50 pages. `P51.png` to `P55.png`: five of them
  again (the repeats), so we can see how consistent each person is.
- `mapping.json`: which page each picture is, the order each form shows them
  in, and every question's wording. The form script reads it. A copy is
  committed as `data/rating/form.json`.
- `make_form.gs`: the script that makes the two forms.
- `README.md`: this.

## 1. Make the folder (already done if you can read this)

From the repository root:

    backend\venv\Scripts\python -m tools.rating.export_form

It writes everything here. Run it again only if the pictures were recaptured,
and never once a form has answers, because the names would point to
different pictures.

## 2. Upload it to Google Drive

1. Open <https://drive.google.com> with the account that should own the form.
2. **New → Folder upload**, and choose this `rating-form` folder. Wait until
   all 58 files are uploaded.
3. Open the folder in Drive. Its address ends in `/folders/` and a long id,
   for example `.../folders/1AbCdEf...`. Copy the id, the part after
   `/folders/`.

If you uploaded an earlier version of this folder, delete it from Drive
first (and any form made from it), and upload this one: the earlier
`mapping.json` has only one order.

## 3. Make the two forms

1. Open <https://script.google.com> and press **New project**.
2. Click "Untitled project" at the top and name it "SIMBA rating form".
3. Delete everything in `Code.gs` and paste in the whole of `make_form.gs`.
4. On the line `const FOLDER_ID = 'PASTE-THE-FOLDER-ID-HERE';` replace
   `PASTE-THE-FOLDER-ID-HERE` with the id you copied. Keep the quotes.
5. Press **Save** (the disk icon).
6. In the toolbar, choose the function `makeFormA` and press **Run**.
7. Google asks for permission the first time: **Review permissions**, choose
   your account, then (because the script is yours and unpublished)
   **Advanced → Go to SIMBA rating form (unsafe) → Allow**. It needs your
   Drive, to read the pictures, and your Forms, to make the form.
8. Wait. It takes a minute or two; the log at the bottom counts the pictures.
   When it says **Done: form A**, it gives two links: one to edit the form,
   and the one to send to raters. Copy both somewhere, labelled A.
9. Choose the function `makeFormB` and press **Run**. Copy its two links,
   labelled B.

Both forms are saved into the same Drive folder, as "SIMBA rating form A"
and "SIMBA rating form B". Raters see the same title on both.

If it stops with an error, read the message: it names the missing file or
setting. If it stopped halfway, delete the half-made form from Drive and run
it again.

## 4. Check both before anyone sees them

Do all of this for form A, then again for form B.

1. Open the edit link, then press the **Preview** (eye) icon. Go through the
   whole form on a laptop: the consent, the three questions, and a few
   pictures. Check that every picture appears above its question and is
   readable, and that answering "No" to consent ends the form. Form B's
   first picture should be form A's last.
2. In the form's **Settings**:
   - **Responses → Collect email addresses**: *Do not collect*.
   - **Responses → Limit to 1 response**: off (it would make raters sign in).
   - If you use a university Google account: **Responses → Restrict to users
     in your organisation**: off, unless every rater is at the university.
3. Do not edit, move or retitle the rating questions. The `[P07]` at the end
   of each title is how the answers are matched to pictures. Wording at the
   top of the form can be changed freely.
4. Delete the test answers you made in preview: **Responses → ⋮ → Delete all
   responses**.

## 5. Send them

In each form press **Send → the link icon**, tick **Shorten URL**, and copy
the link. **Give each rater one link, alternating: the first person A, the
next B, and so on**, so the two forms get about the same number of people.
Never send anyone both. When you send it, ask people to:

- use a laptop or desktop computer, not a phone (phone answers are not used);
- do it in one go, somewhere quiet, in about 15 minutes;
- not talk to anyone else about their answers until they have finished.

Keep a note of how many people you sent each form to and when, for the
write-up.

## 6. Bring the answers back

1. In form A, **Responses → ⋮ → Download responses (.csv)**. Google gives a
   `.zip`; open it and save the `.csv` inside as
   `.scratch/rating-form/responses-A.csv`. Do the same in form B, saving it
   as `.scratch/rating-form/responses-B.csv`.
2. From the repository root:

        backend\venv\Scripts\python -m tools.rating.from_form .scratch/rating-form/responses-A.csv .scratch/rating-form/responses-B.csv

   It works out which form each file is from by the order of its questions,
   and refuses a file whose questions are in neither order. If that happens,
   name the form yourself, e.g. `A=.scratch/rating-form/responses-A.csv`. It
   prints, for each form, how many responses there were and how many are
   usable; who was dropped and why (did not agree, on a phone, or
   incomplete); and how many usable raters there are in all, against the ten
   the estimator needs. Every row records which form its rater used. It can
   be run again whenever more answers come in, with one file or both; it
   replaces the online rows of the forms it is given and keeps the rest.
   Do not delete responses from a form between runs: raters are numbered by
   their row.
3. With ten or more usable raters:

        backend\venv\Scripts\python -m backend.estimator.train

The CSVs and `data/ratings.jsonl` hold people's answers. Neither is committed;
keep them on this machine.
