# The rating form: step by step

This folder becomes a Google Form that people fill in on their own computer:
a consent question, three questions about them, then 55 pictures of web pages,
one per page, each rated from 1 to 7. Their answers come back as a CSV that
`tools/rating/from_form.py` turns into `data/ratings.jsonl` for the estimator.

What is in the folder:

- `P01.png` to `P50.png`: the 50 pages. `P51.png` to `P55.png`: five of them
  again (the repeats), so we can see how consistent each person is.
- `mapping.json`: which page each picture is, the order the form shows them
  in, and every question's wording. The form script reads it. A copy is
  committed as `data/rating/form.json`.
- `make_form.gs`: the script that makes the form.
- `README.md`: this.

## 1. Make the folder (already done if you can read this)

From the repository root:

    backend\venv\Scripts\python -m tools.rating.export_form

It writes everything here. Run it again only if the pictures were recaptured,
and never once the form has answers, because the names would point to
different pictures.

## 2. Upload it to Google Drive

1. Open <https://drive.google.com> with the account that should own the form.
2. **New → Folder upload**, and choose this `rating-form` folder. Wait until
   all 58 files are uploaded.
3. Open the folder in Drive. Its address ends in `/folders/` and a long id,
   for example `.../folders/1AbCdEf...`. Copy the id, the part after
   `/folders/`.

## 3. Make the form

1. Open <https://script.google.com> and press **New project**.
2. Click "Untitled project" at the top and name it "SIMBA rating form".
3. Delete everything in `Code.gs` and paste in the whole of `make_form.gs`.
4. On the line `const FOLDER_ID = 'PASTE-THE-FOLDER-ID-HERE';` replace
   `PASTE-THE-FOLDER-ID-HERE` with the id you copied. Keep the quotes.
5. Press **Save** (the disk icon).
6. In the toolbar, make sure the function shown is `makeForm`, and press
   **Run**.
7. Google asks for permission the first time: **Review permissions**, choose
   your account, then (because the script is yours and unpublished)
   **Advanced → Go to SIMBA rating form (unsafe) → Allow**. It needs your
   Drive, to read the pictures, and your Forms, to make the form.
8. Wait. It takes a minute or two; the log at the bottom counts the pictures.
   When it says **Done**, it gives two links: one to edit the form, and the
   one to send to raters. The form is also saved into the same Drive folder.

If it stops with an error, read the message: it names the missing file or
setting. If it stopped halfway, delete the half-made form from Drive and run
it again.

## 4. Check it before anyone sees it

1. Open the edit link, then press the **Preview** (eye) icon. Go through the
   whole form on a laptop: the consent, the three questions, and a few
   pictures. Check that every picture appears above its question and is
   readable, and that answering "No" to consent ends the form.
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

## 5. Send it

Press **Send → the link icon**, tick **Shorten URL**, and copy the link. When
you send it, ask people to:

- use a laptop or desktop computer, not a phone (phone answers are not used);
- do it in one go, somewhere quiet, in about 15 minutes;
- not talk to anyone else about their answers until they have finished.

Keep a note of how many people you sent it to and when, for the write-up.

## 6. Bring the answers back

1. In the form, **Responses → ⋮ → Download responses (.csv)**. Google gives a
   `.zip`; open it and save the `.csv` inside as
   `.scratch/rating-form/responses.csv`.
2. From the repository root:

        backend\venv\Scripts\python -m tools.rating.from_form .scratch/rating-form/responses.csv

   It prints how many responses there were, who was dropped and why (did not
   agree, on a phone, or incomplete), and how many usable raters there are,
   against the ten the estimator needs. It can be run again whenever more
   answers come in; it replaces the online rows and keeps any in-person ones.
   Do not delete responses from the form between runs: raters are numbered by
   their row.
3. With ten or more usable raters:

        backend\venv\Scripts\python -m backend.estimator.train

The CSV and `data/ratings.jsonl` hold people's answers. Neither is committed;
keep them on this machine.
