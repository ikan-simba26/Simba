/**
 * Every word the interface says, in one place.
 *
 * Here rather than scattered through components for three reasons, in order
 * of how much they matter to the person reading the screen:
 *
 *   1. **The same situation must produce the same sentence, every time.**
 *      Someone who has learned that "Give me a moment." means waiting should
 *      never meet "One moment…" or "Working…" for the same state. Varying the
 *      wording asks the reader to work out whether something new is happening.
 *      A component that writes its own string cannot be checked for this; a
 *      table can, and `frontend/test_copy.py` does.
 *   2. **Wording is a design decision, and not an engineering one.** These
 *      strings are read by people with cognitive disabilities. They should be
 *      reviewable by someone who does not read TypeScript, in one file, in
 *      one sitting.
 *   3. Announcing every change means there is a sentence for every change,
 *      and they have to agree with each other.
 *
 * The rules they are written to:
 *
 *   - Speak to the person, not about the system. "Let me sign you in" rather
 *     than "Signing in".
 *   - One idea per sentence. No sentence needs the previous one held in mind.
 *   - No word where a shorter one exists. "Bill", not "invoice".
 *   - Say what is happening now, not what happened or will happen.
 *   - Never a word the reader has to be taught: no "step", "session",
 *     "verify", "retry", "overlay". (A count, "Step 2 of 6", broke this one until
 *     2026-10-14; the stages replaced it —
 *     see the note on it.)
 *   - A sentence ends with a full stop or a question mark. A lead-in that sits
 *     above the thing it introduces ends with nothing. A button label ends
 *     with nothing.
 *   - Straight apostrophes only, here and in the backend, so one screen never
 *     mixes `I'm` with `I’ll`.
 *
 * **The other half of the voice.** The instruction on each step, its detail
 * line and the labels on its buttons come from the backend — from a plan, or
 * from the LLM planner's sentence templates — along with the stuck screen's
 * suggestion and the trust panel's caption. Those live in
 * `backend/orchestrator/voice.py` and the plans that use it, and
 * `frontend/test_copy.py` holds them to the same rules as this file. Where the
 * two sides voice the same situation (the stuck screen's suggestion), the test
 * requires them to be the same sentence.
 */

import type { FlowName, Level } from "@shared/schema";

/* ----------------------------------------------------------------- brand */

/** The name as the logo writes it: what a screen reader says for the logo. */
export const BRAND = { name: "simba" } as const;

/* --------------------------------------------------------------- onward */

/**
 * Back to the home screen, from any screen that has ended.
 *
 * One name, because it is one destination. The closing screen and the two
 * screens that end without finishing used to call it "Do something else" and
 * "Start again", and "Start again" also suggested it would retry the same
 * task, which it never did. The closing screen also had "I'm done" beside it,
 * which went to the same place: two buttons for one way on. Since 2026-10-16
 * there is one, everywhere, and it says where it goes.
 */
export const ONWARD = "Back to start";

/* ------------------------------------------------------------------ home */

export const HOME = {
  /**
   * The first thing anyone sees: a greeting for the time of day, then the
   * question (2026-10-14). Morning until noon, afternoon until five, evening
   * after; the small hours are still evening, which is what people say.
   */
  morning: "Good morning. What can I do for you?",
  afternoon: "Good afternoon. What can I do for you?",
  evening: "Good evening. What can I do for you?",
  /** Above the goals asked for before, under the tiles. A lead-in. */
  again: "You asked before",
  /** Beside a remembered bill, when two would otherwise look the same: the
   *  reference number's last four digits (2026-10-15). */
  ending: (digits: string) => `ending ${digits}`,
  /** Beside one of two remembered journeys labelled alike: its day, as
   *  people say it ("1 October"). */
  onDay: (day: number, month: number) =>
    `${day} ${["January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December"][month - 1]}`,
  /** Above the three things SIMBA can do (2026-10-18): shown again, now that
   *  the person's own tiles can sit above them. */
  canHelp: "Things I can help with",
  /** Reveals the text box. Deliberately last, and quiet. */
  somethingElse: "Ask for something new",
  /** Opens the welcome again, to change what the person told it (2026-10-18). */
  settings: "Change my settings",
  /** Above the text box, once it is showing. */
  askHeading: "What would you like me to do?",
  /** What SIMBA really does, in the words a person would type. It said "Pay
   *  my electricity bill" until 2026-10-14, and SIMBA never pays anything. */
  placeholder: "Trains from Lahore to Karachi tomorrow",
  start: "Start",
} as const;

/** The greeting for the hour it is, by the person's own clock — with their
 *  name, when they gave one in the welcome (2026-10-18): "Good morning,
 *  Ayesha. What can I do for you?" */
export function greetingAt(hour: number, name?: string): string {
  const greeting = hour >= 5 && hour < 12 ? HOME.morning
    : hour >= 12 && hour < 17 ? HOME.afternoon : HOME.evening;
  if (!name) return greeting;
  const [hello, ...rest] = greeting.split(". ");
  return `${hello}, ${name}. ${rest.join(". ")}`;
}

/* -------------------------------------------------------- your own tiles */

/**
 * The person's own tiles (2026-10-18): a task they did, kept on the home
 * screen with the details they gave, by the name they choose.
 */
export const TILES = {
  /** Above the person's own tiles, first on the home screen. A lead-in. */
  yours: "Yours",
  /** Opens the place to rename, move and remove them. */
  change: "Change my tiles",
  /** On the closing screen, once: keep this task as a tile. */
  keepAsk: (label: string) => `Shall I keep this on your home screen as ${label}?`,
  keep: "Keep it",
  notNow: "Not now",
  kept: (label: string) => `Kept on your home screen as ${label}.`,
  /** The place to change them. */
  editAsk: "Your tiles",
  editDetail: "Change a name, move a tile, or take one off your home screen.",
  /** Each tile's name, for a screen reader, beside the box to change it. */
  name: (label: string) => `Name of ${label}`,
  left: "Move left",
  right: "Move right",
  remove: "Take it off",
  /** When the last one has gone. */
  none: "You have no tiles of your own now.",
} as const;

/* --------------------------------------------------------- show me once */

/**
 * "Show me once" (2026-11-04): a helper — a carer, a family member, a
 * teacher — does a task once on the real website while SIMBA watches, and it
 * becomes a tile the person can press. Reached from "Change my settings",
 * behind a screen that says who it is for. While SIMBA watches, the window
 * is a bar at the top and the website is below it.
 */
export const TEACH = {
  /** In "Change my settings": opens the screen behind it. */
  open: "Show me once",
  /** On the home screen, apart from the rest and quiet (2026-11-10): the
   *  same screen, for a helper, with the line under it saying so. */
  enter: "Teach a task",
  enterDetail: "For a helper, like a carer or a teacher.",
  ask: "Show me a task once",
  detail: "This is for a helper, like a carer, a family member or a teacher. Do the task once on the real website while I watch. Then it becomes a tile, and I can do it again with one press.",
  how: "I'll step aside so you can use the website. I never keep a password, and on a real website I only read.",
  /** Above the box for the website's address. A lead-in. */
  where: "Which website",
  placeholder: "https://",
  start: "Start watching",
  back: "Not now",
  /** When the home screen's row of three is full. */
  noRoom: "There are already three tiles on the home screen. Take one off first.",
  fromFile: "Add one from a file",
  fileNotRead: "I couldn't use that file.",
  /** The bar at the top, while SIMBA watches. */
  watching: "I'm watching.",
  watchingDetail: "Do the task on the website below.",
  count: (n: number) => (n === 1 ? "1 thing so far." : `${n} things so far.`),
  sameOrAsk: (label: string) => `Is what you typed in ${label} the same every time?`,
  /** The same question about a day picked on a calendar (stage 2). */
  sameDay: "Is this day the same every time?",
  same: "Same every time",
  askEach: "Ask each time",
  pointing: "Last thing: click the answer on the website.",
  pointingDetail: "The thing this task is for, like the amount or the list of trains.",
  finish: "Finish",
  stop: "Stop watching",
  /** The things kept so far, each in a few words (2026-11-10). A lead-in,
   *  for a screen reader. */
  kept: "What I've kept so far",
  /** Above the last few, when the bar has no room for them all. */
  more: (n: number) => (n === 1 ? "1 more before these." : `${n} more before these.`),
  /** Takes the last thing off the list, and the website back if it moved. */
  undo: "Undo last thing",
  /** When the website could not be taken back: the first page again, with
   *  nothing kept. */
  startAgain: "Start again",
  /** On "Change my tiles", beside a tile a helper showed. */
  save: "Save to a file",
} as const;

/* ------------------------------------------------------------- welcome */

/**
 * Getting to know the person, the first time SIMBA opens (2026-10-18): four
 * short questions, one at a time, each one skippable. What they say is kept
 * on this computer as their profile (`profile.ts`).
 */
export const WELCOME = {
  /** Above every question of the welcome. A lead-in. */
  lead: "Getting to know you",
  nameAsk: "What should I call you?",
  nameDetail: "Your first name is enough. It stays on this computer.",
  namePlaceholder: "Your name",
  levelAsk: "Which of these feels comfortable?",
  levelDetail: "Each shows the same question in its own way. I start with the one you pick, and show less when something seems hard.",
  /** Under each of the three examples: what it is like. */
  levelName: (level: Level) =>
    level === 1 ? "More on the screen" : level === 3 ? "Less on the screen" : "In between",
  readAsk: "Would you like a button that reads things aloud?",
  readDetail: "It reads the question in your computer's own voice, only when you press it.",
  readYes: "Yes, show it",
  readNo: "No, thank you",
  askAsk: "How would you like me to work?",
  askDetail: "Paying, booking and anything you have to choose always wait for you.",
  askEach: "Ask me before each thing",
  justDo: "Just do it and show me",
  next: "Next",
  skip: "Skip this",
  /** In "Change my settings" only (2026-10-18): for the next person to use
   *  this computer, or the next session of a study. */
  forget: "Forget me and start again",
  forgetAsk: "Shall I forget everything about you?",
  forgetDetail: "Your name, your settings and your own tiles go from this computer. Then I start again, as if you had just opened me.",
  forgetYes: "Yes, forget it all",
  forgetNo: "No, keep it",
  /** The example shown three ways: a question every journey asks. */
  sample: {
    instruction: "What day are you travelling?",
    detail: "I'll look up the trains for that day.",
    answers: ["Today", "Tomorrow", "Another day"],
    stop: "Stop this",
  },
} as const;

/* ---------------------------------------------------------------- flows */

/**
 * The three things SIMBA can do, one line each, as a person would ask.
 *
 * Each line is both what the card says and the goal it sends: pressing
 * "Check my electricity bill" asks for exactly that, in exactly those words,
 * so what the person chose and what runs cannot disagree. The goal is sent
 * with the flow's name, so the backend does not have to guess from it.
 *
 * **A card names no detail of its own** (2026-10-06). The train card read
 * "Find trains from Lahore to Karachi" and the course card "Register for
 * CS-401", and because the card's words are the goal, pressing either one
 * told the backend where the person was going or which course they wanted —
 * so it never asked. On `railways-local` that was the whole of "SIMBA never
 * asked where I was going". Each card now says what SIMBA can do, and the
 * backend asks for the rest.
 */
export const FLOWS: Record<FlowName, string> = {
  registration: "Register for a course",
  billing: "Check my electricity bill",
  railways: "Find train times",
};

/**
 * The same three, as answers to "which of these did you mean". Not the card
 * lines: these do not send their own words, they send the person's.
 */
export const WHICH: Record<FlowName, string> = {
  registration: "The course registration",
  billing: "The electricity bill",
  railways: "The train times",
};

/* ---------------------------------------------------------------- reply */

/**
 * When a goal did not start anything (`goal.answered`, CONTRACT.md).
 *
 * The backend never writes these. It says which kind of answer it is and
 * which flows to offer, and the words come from here, so the real backend and
 * the mock say the same thing and the copy tests see every sentence.
 */
export const REPLY = {
  /** Small talk, or nothing typed. */
  greeting: "Hello. Here's what I can help with.",
  /** A real request SIMBA cannot do. One plain sentence, then what it can. */
  unsupported: "I can't do that yet.",
  /** Above the cards, after the refusal. A lead-in. */
  canDo: "Here's what I can do",
  /** It could be more than one. */
  clarify: "Which of these did you mean?",
  /** Above the words the person typed, echoed back quietly. A lead-in. */
  youAsked: "You asked",
} as const;

/* ---------------------------------------------------------------- status */

/**
 * What the presence mark is doing, named for a screen reader.
 *
 * Never shown as text. The mark says it with shape and motion (`ui.Presence`),
 * and the step or the ending is the sentence on screen; these exist so that
 * somebody who cannot see the mark is told the same thing, in the same words
 * every time.
 */
export const STATUS = {
  ready: "Ready",
  thinking: "Thinking",
  acting: "Working on it",
  waiting: "Your turn",
  stuck: "Stopped",
  done: "Finished",
} as const;

/* -------------------------------------------------------------- presence */

/**
 * What the assistant says while it is working.
 *
 * Two situations, not three. Working out what to do and doing it used to have
 * a sentence each ("Give me a moment." and "I'm doing that now."), but from
 * where the person sits they are one situation — wait — and the difference is
 * already shown without words by the line crossing the top of the column
 * while an action runs (`StateSignal.ActingLine`). `waiting` has no sentence:
 * the step on screen is the sentence, and a second one beside it would be two
 * things to read.
 */
const PRESENCE: Record<"reading" | "opening" | "working", string> = {
  /**
   * Between pressing Start and the backend deciding what was asked for.
   *
   * Its own sentence because it is its own situation: nothing has been opened
   * yet, and it may turn out to be a greeting rather than a task. Up to eight
   * seconds with a model deciding (`router.py`), and until 2026-09-21 the
   * screen said nothing at all for that long, so pressing Start looked like
   * it had not worked.
   */
  reading: "Let me see what you need.",
  /** Between "start" and the first step, while the site loads. */
  opening: "Let me open that for you.",
  /** Working out what to do next, or doing it. */
  working: "Give me a moment.",
};

export type Presence = keyof typeof PRESENCE;

/** The sentence for this situation. Always the same one. */
export function presence(situation: Presence): string {
  return PRESENCE[situation];
}

/* ------------------------------------------------------------------ step */

/**
 * Where the person is in the task: the stages by name, which the backend
 * sends (`task.started.stages`, `voice.*_STAGES`), in place of "Step 2 of 6"
 * (2026-10-14). A count grew every time a question was asked again — "Step 13
 * of 13" — so every later screen claimed to be the last; and it used a word
 * the rules above forbid. The stage names are the backend's; this names the
 * row for a screen reader.
 */
export const STAGES = {
  /** The row of stages, named for a screen reader. */
  label: "Where you are",
} as const;

/* -------------------------------------------------------------- findings */

export const FOUND = {
  /** Above a value found mid-task. The value itself is the large type. A lead-in. */
  heading: "Here's what I found",
} as const;

/* --------------------------------------------------------------- ending */

export const ENDING = {
  /**
   * When the task found something.
   *
   * Deliberately the same sentence as `FOUND.heading` rather than a closing
   * variant of it. Showing a value mid-task and showing it at the end are the
   * same situation — here is the thing you asked for — and giving the ending
   * its own phrasing would mean the reader meets two sentences for one event
   * and has to decide whether they mean different things.
   */
  withAnswer: FOUND.heading,
  /** When it did not. Nothing was being looked for; something was done. */
  withoutAnswer: "That's done.",
  /** The one way on (2026-10-16): "I'm done" and "Do something else" both
   *  led home, and are one button now. */
  again: ONWARD,
  /**
   * Under a list of results cut short. The same words `voice.found` uses on
   * the step screen for the same thing, so one cut-short list reads one way.
   */
  more: (count: number) => `and ${count} more`,
  /**
   * On the result that takes least time, when every result's time can be
   * read (2026-10-07). The sentence above says which one it is; this marks it
   * where it is in the list. A tag, so it ends with nothing.
   */
  fastest: "Fastest",
} as const;

/* -------------------------------------------------------- when it stops */

export const STOPPED = {
  /**
   * The assistant could not go on, and has stopped.
   *
   * Says what has happened, and nothing it cannot keep. It used to read "I
   * need your help with this." and then "Can you do this part? I'll carry on
   * after." — and none of that was true. When the backend sends
   * `help.requested` the run is over and the connection is closed, so nothing
   * carries on; and the page is covered by this overlay by design, so the
   * person could not do "this part" even if they wanted to. Asking someone to
   * do something they cannot see, and promising to resume when nothing will,
   * is the worst thing this screen could say to this audience.
   */
  heading: "I'm stuck, so I've stopped.",
  /** Instead, when a change was tried and the site did not confirm it
   *  (2026-10-16): not stuck, and never "done". */
  unconfirmed: "It isn't confirmed.",
  /**
   * What happens now: nothing more, and they can choose something else.
   *
   * The backend sends its own suggestion in `help.requested`, and that is what
   * is shown when it arrives. `voice.HELP_SUGGESTION` is required by
   * `test_copy.py` to be this same sentence, so the screen reads the same
   * whichever side supplied it.
   */
  suggestion: "I won't do any more on this. You can ask me for something else.",
  /** The backend ended the task, and it was not the person's choice. */
  failedHeading: "I couldn't finish this.",
  /**
   * The person pressed stop, and it has.
   *
   * Its own sentence, not `failedHeading`. The backend reports a stop as
   * `task.failed`, and for a while the screen said "I couldn't finish this."
   * to someone who had just chosen to stop — a decision they made, read back
   * to them as the assistant failing.
   */
  byYou: "I've stopped, as you asked.",
  /** Offered on every ending, so there is always a way onwards. */
  again: ONWARD,
} as const;

/**
 * "Don't" on a final screen (2026-10-16): the task ends, calmly, and nothing
 * on the site was changed — true by construction, since nothing that books,
 * pays or registers is done before that screen. The backend's
 * `task.failed.reason` is these two sentences, `voice.NOTHING_CHANGED`.
 */
export const FINAL = {
  notDone: "I didn't do it.",
  nothingChanged: "Nothing was changed.",
} as const;

/* -------------------------------------------------------------- notices */

/**
 * Every change the person did not make is announced.
 *
 * Each of these is one situation with one sentence. `levelNotice` is a
 * function only because there are two directions; it is not free text.
 */
export const NOTICE = {
  /** The interface simplified itself, because the person seemed to be finding
   *  it hard. It comes back after two calm steps, so "for a moment" is true. */
  simpler: "I'm showing less for a moment.",
  /**
   * The level rules made it fuller. Not "again" (until 2026-10-14): a task
   * whose first page started it simpler had never shown more, and the
   * sentence said it had.
   */
  fuller: "I'm showing a bit more now.",
  /**
   * The step was too long for the window and was packed closer to fit — the
   * overflow guard, not the level rules. It used to say `fuller`'s "I'm
   * showing a bit more again.", which was not what had happened: in the real
   * window it greeted the very first question of a task, where nothing had
   * been shown before to show "again" (EVALUATION.md, 2026-10-14).
   */
  fitted: "I've made this smaller so it fits.",
  /**
   * A step did not work and the run carried on.
   *
   * No interpolation, deliberately. The old version read "I couldn't do that
   * step — close the registration alert. I'm carrying on." and quoted the
   * instruction back, which is a second thing to read at the moment something
   * has already gone wrong, and it named a step the person may never have
   * seen. The technical reason underneath it — `Locator.click: Timeout
   * 10000ms exceeded` — was worse. Both are still in the development view.
   */
  skipped: "I couldn't do that. I'm carrying on.",
  /** Dismisses any notice. */
  dismiss: "Dismiss",
} as const;

/**
 * Which sentence a level change gets. Same cause and direction, same words,
 * always.
 *
 * A step packed to fit the window says so (`fitted`), whichever levels it
 * moved between. Otherwise the level rules moved it, and the direction says
 * which of the other two. The rules' own reason is for the development view,
 * not the screen.
 */
export function levelNotice(from: Level, to: Level, fitted = false): string {
  if (fitted) return NOTICE.fitted;
  return to > from ? NOTICE.simpler : NOTICE.fuller;
}

/* ---------------------------------------------------------------- level */

export const LEVEL = {
  /** The three dots' names, for a screen reader. Generated from the level. */
  choose: (level: Level) =>
    level === 1 ? "Show more" : level === 3 ? "Show less" : "Show the usual amount",
  /** Hands the level back to the estimator once the person has locked it. */
  unlock: "let it choose",
} as const;

/* ---------------------------------------------------------------- trust */

export const TRUST = {
  /** The question the person can always ask. */
  ask: "What are you doing?",
  /** Closes the picture of the real page. */
  hide: "Hide the page",
  /** The picture's description, for a screen reader. */
  picture: "The page as it is right now",
  /** From the close-up out to the whole page. */
  whole: "Show the whole page",
  /** And back in to the thing about to be touched. */
  closeUp: "Show it close up",
  close: "Close",
  /** Asked, and no picture came in time (2026-10-16). The backend says the
   *  same words, `voice.NO_PICTURE`. */
  noPicture: "I couldn't get a picture just now.",
  /** Under it: what to do next. */
  tryAgain: "You can ask again in a moment.",
} as const;

/**
 * The answer on the real page (2026-10-16): a still of the page as the task
 * closed, with what was read ringed. The caption, and why there is no
 * picture when there is none, come from the backend (`voice.PROOF_CAPTION`,
 * `voice.NO_PROOF_PICTURE`).
 */
export const PROOF = {
  /** Under the answer. */
  see: "See it on the real page",
  /** Back from the picture. */
  back: "Back to the answer",
  /** The picture, for a screen reader. */
  picture: "The real page as I finished, with what I read ringed",
} as const;

/* ------------------------------------------------------------ the checklist */

/**
 * What SIMBA does by itself once the person has decided (2026-10-14): the
 * safe mechanical moves, as a short list that ticks off. Each line is the
 * backend's (`voice.DOING_*`); these are the words round it.
 */
/**
 * Signing in (2026-10-15). Saving the password is a box to tick under the
 * boxes to type in, not a second "Sign in and save my password" button: one
 * way to sign in, and a choice about it. Raham's decision; Aly to be told.
 */
export const SIGN_IN = {
  /** Ticked, signing in also keeps the password on this computer. */
  save: "Save my password for next time",
} as const;

export const CHECKLIST = {
  heading: "I'm doing what you asked.",
  /** Stops before the next move; SIMBA then waits to be told to carry on. */
  pause: "Pause",
  /** On the button once pressed, until SIMBA has stopped. */
  pausing: "Pausing",
  /** A line that is done, for a screen reader. */
  done: "Done",
  /** The line being done, for a screen reader. */
  now: "Doing this now",
  /** A line still to come, for a screen reader (2026-10-15). */
  next: "Still to do",
  /** At the simplest level, under the move being done, in place of the
   *  moves themselves (2026-11-10): how many are still to come. */
  left: (n: number) => (n === 1 ? "Then 1 more thing." : `Then ${n} more things.`),
} as const;

/**
 * The person's own settings, kept on this computer (2026-10-14).
 */
export const SETTINGS = {
  /** Off: SIMBA runs the safe moves itself. On: it asks before every one. */
  askEach: "Ask me before each thing I do",
} as const;

/* ------------------------------------------------------------ read aloud */

/**
 * Reading a step aloud in the system's own English voice, when asked
 * (2026-10-14). Nothing is read unless the button is pressed.
 */
export const SPEAK = {
  read: "Read this aloud",
  stop: "Stop reading",
  /** After the step's sentence: the answers it offers, in the buttons' words. */
  answers: (labels: string[]) =>
    labels.length === 1
      ? `You can press ${labels[0]}.`
      : `You can press ${labels.slice(0, -1).join(", ")} or ${labels[labels.length - 1]}.`,
} as const;

/* --------------------------------------------------- a list to choose from */

/**
 * A question whose answer is one of a known list: the train search's own
 * stations, read from the site before anything on it is touched (2026-10-06).
 * The box narrows the list as the person types, and the few that match are
 * buttons to press. The names themselves come from the site.
 */
export const CHOOSE = {
  /** Where the names will be, before anything is typed. */
  hint: "Type the first few letters to see the names.",
  /** Under the matches, when more match than are shown. */
  more: (count: number) =>
    count === 1 ? "1 more. Keep typing to find yours." : `${count} more. Keep typing to find yours.`,
  /** When nothing on the list has what has been typed. */
  none: "Nothing on the list matches that yet.",
  /** The matches, named for a screen reader. */
  matches: "Matching names",
} as const;

/* ------------------------------------------------------ the whole table */

/**
 * Every situational string, keyed by situation.
 *
 * This exists so consistency is *checkable* rather than intended: the test
 * walks it and fails if one situation can produce two different strings, or
 * if two situations that should read the same have drifted apart.
 */
export const SITUATIONS: Record<string, string> = {
  "trust.noPicture": TRUST.noPicture,
  "trust.tryAgain": TRUST.tryAgain,
  "presence.opening": presence("opening"),
  "presence.working": presence("working"),
  "presence.reading": presence("reading"),
  "notice.simpler": NOTICE.simpler,
  "notice.fuller": NOTICE.fuller,
  "notice.fitted": NOTICE.fitted,
  "notice.skipped": NOTICE.skipped,
  "ending.withoutAnswer": ENDING.withoutAnswer,
  "stopped.heading": STOPPED.heading,
  "stopped.unconfirmed": STOPPED.unconfirmed,
  "stopped.suggestion": STOPPED.suggestion,
  "stopped.failedHeading": STOPPED.failedHeading,
  "stopped.byYou": STOPPED.byYou,
  "final.notDone": FINAL.notDone,
  "final.nothingChanged": FINAL.nothingChanged,
  "home.morning": HOME.morning,
  "home.afternoon": HOME.afternoon,
  "home.evening": HOME.evening,
  "checklist.heading": CHECKLIST.heading,
  "home.askHeading": HOME.askHeading,
  "home.morningNamed": greetingAt(9, "Ayesha"),
  "welcome.nameAsk": WELCOME.nameAsk,
  "welcome.nameDetail": WELCOME.nameDetail,
  "welcome.levelAsk": WELCOME.levelAsk,
  "welcome.levelDetail": WELCOME.levelDetail,
  "welcome.readAsk": WELCOME.readAsk,
  "welcome.readDetail": WELCOME.readDetail,
  "welcome.askAsk": WELCOME.askAsk,
  "welcome.askDetail": WELCOME.askDetail,
  "welcome.forgetAsk": WELCOME.forgetAsk,
  "welcome.forgetDetail": WELCOME.forgetDetail,
  "tiles.keepAsk": TILES.keepAsk("My bill"),
  "tiles.kept": TILES.kept("My bill"),
  "tiles.editDetail": TILES.editDetail,
  "tiles.none": TILES.none,
  "trust.ask": TRUST.ask,
  "reply.greeting": REPLY.greeting,
  "reply.unsupported": REPLY.unsupported,
  "reply.clarify": REPLY.clarify,
  "choose.more": CHOOSE.more(5),
  "choose.none": CHOOSE.none,
  "choose.hint": CHOOSE.hint,
  "speak.answers": SPEAK.answers(["Today", "Tomorrow", "Pick another day"]),
};

/** Lead-ins: text that introduces what sits below it. Never punctuated. */
export const LEADS: Record<string, string> = {
  "found.heading": FOUND.heading,
  "ending.fastest": ENDING.fastest,
  "home.canHelp": HOME.canHelp,
  "home.again": HOME.again,
  "welcome.lead": WELCOME.lead,
  "tiles.yours": TILES.yours,
  "tiles.editAsk": TILES.editAsk,
  "welcome.level1": WELCOME.levelName(1),
  "welcome.level2": WELCOME.levelName(2),
  "welcome.level3": WELCOME.levelName(3),
  "reply.canDo": REPLY.canDo,
  "reply.youAsked": REPLY.youAsked,
};

/** Everything that goes on a button. Never punctuated, never two for one place. */
export const LABELS: Record<string, string> = {
  onward: ONWARD,
  "home.somethingElse": HOME.somethingElse,
  "home.start": HOME.start,
  "notice.dismiss": NOTICE.dismiss,
  "level.unlock": LEVEL.unlock,
  "level.choose1": LEVEL.choose(1),
  "level.choose2": LEVEL.choose(2),
  "level.choose3": LEVEL.choose(3),
  "trust.hide": TRUST.hide,
  "trust.close": TRUST.close,
  "trust.whole": TRUST.whole,
  "trust.closeUp": TRUST.closeUp,
  "speak.read": SPEAK.read,
  "checklist.pause": CHECKLIST.pause,
  "checklist.pausing": CHECKLIST.pausing,
  "checklist.done": CHECKLIST.done,
  "checklist.now": CHECKLIST.now,
  "checklist.next": CHECKLIST.next,
  "signIn.save": SIGN_IN.save,
  "proof.see": PROOF.see,
  "proof.back": PROOF.back,
  "home.ending": HOME.ending("7890"),
  "home.onDay": HOME.onDay(1, 10),
  "settings.askEach": SETTINGS.askEach,
  "home.settings": HOME.settings,
  "teach.start": TEACH.start,
  "teach.same": TEACH.same,
  "teach.askEach": TEACH.askEach,
  "teach.finish": TEACH.finish,
  "teach.stop": TEACH.stop,
  "teach.save": TEACH.save,
  "teach.fromFile": TEACH.fromFile,
  "teach.enter": TEACH.enter,
  "teach.undo": TEACH.undo,
  "teach.startAgain": TEACH.startAgain,
  "teach.kept": TEACH.kept,
  "welcome.readYes": WELCOME.readYes,
  "welcome.readNo": WELCOME.readNo,
  "welcome.askEach": WELCOME.askEach,
  "welcome.justDo": WELCOME.justDo,
  "welcome.next": WELCOME.next,
  "welcome.skip": WELCOME.skip,
  "welcome.forget": WELCOME.forget,
  "welcome.forgetYes": WELCOME.forgetYes,
  "welcome.forgetNo": WELCOME.forgetNo,
  "tiles.change": TILES.change,
  "tiles.keep": TILES.keep,
  "tiles.notNow": TILES.notNow,
  "tiles.left": TILES.left,
  "tiles.right": TILES.right,
  "tiles.remove": TILES.remove,
  "speak.stop": SPEAK.stop,
  "flow.registration": FLOWS.registration,
  "flow.billing": FLOWS.billing,
  "flow.railways": FLOWS.railways,
  "which.registration": WHICH.registration,
  "which.billing": WHICH.billing,
  "which.railways": WHICH.railways,
  // Names, not buttons: the presence mark's state for a screen reader. Here
  // so they are held to the same rules and cannot collide with a button.
  "status.ready": STATUS.ready,
  "status.thinking": STATUS.thinking,
  "status.acting": STATUS.acting,
  "status.waiting": STATUS.waiting,
  "status.stuck": STATUS.stuck,
  "status.done": STATUS.done,
  "stages.label": STAGES.label,
  "choose.matches": CHOOSE.matches,
};
