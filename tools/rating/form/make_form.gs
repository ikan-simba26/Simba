/**
 * Makes SIMBA's two rating forms, A and B, from a Google Drive folder of
 * pictures. Run makeFormA, then makeFormB: one form per run, because each
 * takes a minute or two and a script may run for six.
 *
 * The folder is .scratch/rating-form/ uploaded as it is: P01.png to P55.png
 * and mapping.json, written by `python -m tools.rating.export_form`. Every
 * question's wording, and the order the pictures are shown in, come from
 * mapping.json, so the form and tools/rating/from_form.py agree on them.
 *
 * Each form: a consent question (answering "No" ends it), three questions
 * about the person, a page of instructions, then one page per picture: the
 * picture and a 1-7 question. A picture cannot be shuffled together with its
 * question in a form made by a script, so each form has a fixed order: A the
 * random order in mapping.json, B the same reversed, each repeated picture
 * well apart from its other showing in both. Send half the raters A and half
 * B. The two look the same to a rater; only their names in Drive differ.
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

function makeFormA() { makeForm('A'); }

function makeFormB() { makeForm('B'); }

function makeForm(letter) {
  if (FOLDER_ID.indexOf('PASTE') === 0) {
    throw new Error('Set FOLDER_ID at the top of the script to your folder\'s id first.');
  }
  const folder = DriveApp.getFolderById(FOLDER_ID);
  const mapping = JSON.parse(fileNamed(folder, 'mapping.json').getBlob().getDataAsString('UTF-8'));
  const q = mapping.questions;
  const order = mapping.orders[letter];
  if (!order) throw new Error('mapping.json has no form ' + letter + '. Upload the latest rating-form folder.');
  // Every picture is checked for before anything is made, so a missing one
  // does not leave half a form behind.
  const pictures = {};
  order.forEach(function (name) { pictures[name] = fileNamed(folder, name + '.png'); });

  const form = FormApp.create('SIMBA rating form ' + letter)
    .setTitle(FORM_TITLE)
    .setDescription(
      'Please fill this in on a laptop or desktop computer, not a phone: the pictures ' +
      'are too small on a phone to judge. It takes about 15 minutes.')
    .setCollectEmail(false)
    .setProgressBar(true)
    .setShuffleQuestions(false)
    .setAllowResponseEdits(false)
    .setShowLinkToRespondAgain(false)
    .setConfirmationMessage('Thank you - that is all of them.');

  // 1. Consent. "No" sends the form at once, with nothing in it.
  const consent = form.addMultipleChoiceItem()
    .setTitle(q.consent.title)
    .setHelpText(q.consent.help)
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

  // 3. What to do.
  form.addPageBreakItem().setTitle('The pictures').setHelpText(
    'You will see ' + order.length + ' pictures of web pages, one at a time. For each ' +
    'one, imagine you had to use that page to get something done, and answer one ' +
    'question: ' + q.rating.title + ' Answer from ' + q.rating.scale[0] + ' (' +
    q.rating.low.toLowerCase() + ' overwhelming) to ' + q.rating.scale[1] + ' (' +
    q.rating.high.toLowerCase() + ' overwhelming). Go with your first impression - ' +
    'there are no right answers. Some pages may come up more than once.');

  // 4. One page per picture.
  order.forEach(function (name, index) {
    form.addPageBreakItem().setTitle('Picture ' + (index + 1) + ' of ' + order.length);
    form.addImageItem()
      .setImage(pictures[name].getBlob())
      .setAlignment(FormApp.Alignment.CENTER);
    form.addScaleItem()
      .setTitle(mapping.rating_title.replace('{question}', q.rating.title).replace('{name}', name))
      .setHelpText(q.rating.help)
      .setBounds(q.rating.scale[0], q.rating.scale[1])
      .setLabels(q.rating.low, q.rating.high)
      .setRequired(true);
    if ((index + 1) % 10 === 0) Logger.log('%s of %s pictures added', index + 1, order.length);
  });

  DriveApp.getFileById(form.getId()).moveTo(folder);
  Logger.log('Done: form %s. Edit it at: %s', letter, form.getEditUrl());
  Logger.log("Send form %s's raters this link: %s", letter, form.getPublishedUrl());
}

function fileNamed(folder, name) {
  const files = folder.getFilesByName(name);
  if (!files.hasNext()) throw new Error('The folder has no ' + name + '. Upload the whole rating-form folder.');
  const file = files.next();
  if (files.hasNext()) throw new Error('The folder has two files called ' + name + '. Remove one.');
  return file;
}
