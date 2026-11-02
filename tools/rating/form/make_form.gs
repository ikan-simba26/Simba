/**
 * Makes SIMBA's rating forms from a Google Drive folder of pictures, one form
 * per run: makeFormSet1 and makeFormSet2 from the rating-form folder, and
 * makeFormSet3 from the rating-form-set3 folder.
 *
 * The folder is .scratch/rating-form/ uploaded as it is: P01.png to P54.png,
 * E1.png and E2.png, and mapping.json, written by
 * `python -m tools.rating.export_form`. Every question's wording, which
 * pictures each set shows and in what order, and the two worked examples come
 * from mapping.json, so the forms and tools/rating/from_form.py agree on them.
 *
 * Each form: "about 5-7 minutes" at the top, a consent question (answering
 * "No" ends it), three questions about the person, a page with two worked
 * examples (a calm page and a cluttered one, neither among the 50, each with
 * its answer), then one page per picture: the picture and one question with
 * five labelled answers, Not at all / A little / Somewhat / Very / Extremely.
 * 30 pictures: the set's 25 pages, three anchor pages from the other set,
 * and two repeats. The progress bar is on. A picture cannot be shuffled
 * together with its question in a form made by a script, so each form has
 * the fixed order in mapping.json. Send half the raters Set 1 and half Set 2.
 *
 * Set 3 is the same form with 20 pictures, about 3-4 minutes: 15 Pakistani
 * pages, three anchor pages and two repeats. Its folder has its own pictures,
 * under the same kind of name, E1.png and E2.png, and the same mapping.json with
 * Set 3 in it, and the words that differ are under mapping.overrides.
 *
 * Each rating question's title ends in the picture's name, "[P07]". That is
 * how from_form.py knows which answer is which picture: do not edit those
 * titles in the form.
 *
 * Source: tools/rating/form/make_form.gs in the SIMBA repository.
 */

// The folder's id: the part of its address after /folders/.
const FOLDER_ID = 'PASTE-THE-FOLDER-ID-HERE';
const FORM_TITLE = 'How overwhelming is this web page?';

function makeFormSet1() { makeForm('1'); }

function makeFormSet2() { makeForm('2'); }

function makeFormSet3() { makeForm('3'); }

function makeForm(set) {
  if (FOLDER_ID.indexOf('PASTE') === 0) {
    throw new Error('Set FOLDER_ID at the top of the script to your folder\'s id first.');
  }
  const folder = DriveApp.getFolderById(FOLDER_ID);
  const mapping = JSON.parse(fileNamed(folder, 'mapping.json').getBlob().getDataAsString('UTF-8'));
  const q = mapping.questions;
  const over = (mapping.overrides && mapping.overrides[set]) || {};
  const order = mapping.orders && mapping.orders[set];
  if (!order) throw new Error('mapping.json has no Set ' + set + '. Upload the latest rating-form folder.');
  // Every picture is checked for before anything is made, so a missing one
  // does not leave half a form behind.
  const pictures = {};
  order.forEach(function (name) { pictures[name] = fileNamed(folder, name + '.png'); });
  const examples = mapping.examples.map(function (example) {
    return { file: fileNamed(folder, example.file), says: example.says, label: example.label };
  });

  const form = FormApp.create('SIMBA rating form, Set ' + set)
    .setTitle(FORM_TITLE)
    .setDescription(over.intro || q.intro)
    .setCollectEmail(false)
    .setProgressBar(true)
    .setShuffleQuestions(false)
    .setAllowResponseEdits(false)
    .setShowLinkToRespondAgain(false)
    .setConfirmationMessage('Thank you - that is all of them.');

  // 1. Consent. "No" sends the form at once, with nothing in it.
  const consent = form.addMultipleChoiceItem()
    .setTitle(q.consent.title)
    .setHelpText(over.consent_help || q.consent.help)
    .setRequired(true);
  consent.setChoices([
    consent.createChoice(q.consent.yes, FormApp.PageNavigationType.CONTINUE),
    consent.createChoice(q.consent.no, FormApp.PageNavigationType.SUBMIT),
  ]);

  // 2. About the person.
  form.addPageBreakItem().setTitle('About you');
  form.addMultipleChoiceItem().setTitle(q.device.title)
    .setChoiceValues(Object.values(q.device.choices)).setRequired(true);
  form.addMultipleChoiceItem().setTitle(q.age.title)
    .setChoiceValues(q.age.choices).setRequired(true);
  form.addMultipleChoiceItem().setTitle(q.computing.title)
    .setChoiceValues(Object.values(q.computing.choices)).setRequired(true);

  // 3. What to do, and two worked examples: each picture, one sentence, its answer.
  form.addPageBreakItem().setTitle(q.examples.title).setHelpText(
    q.examples.help + ' The question for every picture: ' + q.rating.title + ' ' +
    'There are ' + order.length + ' pictures. Some pages may come up more than once.');
  examples.forEach(function (example) {
    form.addImageItem()
      .setImage(example.file.getBlob())
      .setHelpText(example.says + ' ' + q.examples.answer.replace('{label}', example.label))
      .setAlignment(FormApp.Alignment.CENTER);
  });

  // 4. One page per picture.
  order.forEach(function (name, index) {
    form.addPageBreakItem().setTitle('Picture ' + (index + 1) + ' of ' + order.length);
    form.addImageItem()
      .setImage(pictures[name].getBlob())
      .setAlignment(FormApp.Alignment.CENTER);
    form.addMultipleChoiceItem()
      .setTitle(mapping.rating_title.replace('{question}', q.rating.title).replace('{name}', name))
      .setHelpText(q.rating.help)
      .setChoiceValues(q.rating.labels)
      .setRequired(true);
    if ((index + 1) % 10 === 0) Logger.log('%s of %s pictures added', index + 1, order.length);
  });

  DriveApp.getFileById(form.getId()).moveTo(folder);
  Logger.log('Done: Set %s. Edit it at: %s', set, form.getEditUrl());
  Logger.log("Send Set %s's raters this link: %s", set, form.getPublishedUrl());
}

function fileNamed(folder, name) {
  const files = folder.getFilesByName(name);
  if (!files.hasNext()) throw new Error('The folder has no ' + name + '. Upload the whole rating-form folder.');
  const file = files.next();
  if (files.hasNext()) throw new Error('The folder has two files called ' + name + '. Remove one.');
  return file;
}
