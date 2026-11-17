/**
 * What SIMBA has learned so far, as the card that builds (2026-11-17).
 *
 * Every task screen has the same three parts: what is finished, the one thing
 * now, and a card that starts out empty and fills in field by field, the
 * moment each thing is known — from the goal, from a choice or a detail the
 * person gave, or from the page. This file is the whole of that logic, with
 * no React in it: facts go in, a card comes out.
 *
 * Built only from messages the backend already sends (`task.started`, each
 * step and the answer to it, the final screen's details, the findings). No
 * message was added. Nothing here guesses a value: a field whose fact has not
 * been seen stays empty, and a value is only ever what the person or the page
 * said, in their words.
 *
 * Never on the card: a card number, a code, or a password. A fact whose name
 * says it is one is dropped before it is stored (`isSecret`), and a password
 * box on a form is shown as "kept safely" with no value.
 */

import type { Detail, Finding, StepPresented } from "@shared/schema";

/** What the finished thing looks like. */
export type Shape = "ticket" | "receipt" | "bill" | "form" | "answer";

/** One thing learned: a name, and the value as it was said. */
export interface Fact {
  label: string;
  value: string;
  /** Where it came from, for a developer; never shown. */
  from: "goal" | "typed" | "chosen" | "page";
  /** A picture that came with a choice (a product's), a `data:` address. */
  picture?: string;
  /** A secret the person typed: only the fact that it was kept, never its value. */
  kept?: boolean;
}

/** One line of the card. */
export interface Slot {
  key: string;
  label: string;
  /** Null: not known yet. */
  value: string | null;
  /** The person's to give, and SIMBA is waiting for it. */
  waiting: boolean;
  /** Shown as "kept safely" with no value (a password on a form). */
  kept?: boolean;
  picture?: string;
  /** A line under the value, in small type ("Only 1, as you asked"). */
  note?: string;
}

export interface CardModel {
  shape: Shape;
  slots: Slot[];
  filled: number;
  total: number;
  /** The page's own final screen has been shown: the card is complete. */
  complete: boolean;
}

/* ---------------------------------------------------------------- shapes */

/**
 * Which finished thing a task makes, from what was asked and the kind of
 * website. The order matters: "book a bus" is a ticket, not an order.
 */
export function shapeOf(goal: string, genre?: string | null): Shape {
  const text = goal.toLowerCase();
  if (/\b(bus|train|ticket|flight|seat|journey|coach|railway|travel)\b/.test(text)) return "ticket";
  if (/\b(bill|electricity|gas|water|utility|utilities|invoice|dues?)\b/.test(text)) return "bill";
  if (/\b(register|sign ?up|sign up|create (an |my )?account|enrol|enroll|apply|admission)\b/
      .test(text)) return "form";
  if (/\b(order|buy|purchase|shop|cart|deliver)\b/.test(text)) return "receipt";
  switch (genre) {
    case "Travel": return "ticket";
    case "Shopping": return "receipt";
    case "Bills": case "Utilities": return "bill";
    default: return "answer";
  }
}

/* ---------------------------------------------------------------- secrets */

/**
 * A name that says what it holds is never to be shown: a card number, a code
 * sent to a phone, a password. Checked on the label of every fact and every
 * field before anything is kept.
 */
export function isSecret(label: string): boolean {
  return /pass ?word|passcode|\bpin\b|card|cvv|cvc|expiry|\botp\b|one.?time|verification|security code|\bcode\b/i
    .test(label);
}

/* ------------------------------------------------------------------ text */

function capital(text: string): string {
  return text.trim().replace(/\s+/g, " ").replace(/(^|[\s-])([a-z])/g, (_, a, b) => a + b.toUpperCase());
}

/** A sentence's first words as one short line: no full stop, at most `most` characters. */
export function brief(text: string, most = 46): string {
  const clean = text.replace(/\s+/g, " ").trim().replace(/[.!?]+$/, "");
  if (clean.length <= most) return clean;
  const cut = clean.slice(0, most - 1);
  return `${cut.slice(0, cut.lastIndexOf(" ") > 20 ? cut.lastIndexOf(" ") : cut.length)}…`;
}

/** The first sentence of an instruction (a full stop after an abbreviation is not the end). */
export function firstLine(text: string): string {
  const end = /[.!?](?=\s|$)/g;
  for (let found = end.exec(text); found; found = end.exec(text)) {
    const before = text.slice(0, found.index);
    const after = text.slice(found.index + 1).trimStart();
    if (found[0] === "." && (/\b(?:Jn|Jct|Cantt|St|Dr|Mr|Mrs|Ms|No|Rs|vs|etc)$/i.test(before)
                             || /^[a-z]/.test(after))) continue;
    return text.slice(0, found.index + 1);
  }
  return text;
}

const MONEY = /(?:\brs\.?|\bpkr)\s?\d[\d,]*(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s?(?:\brs\.?|\bpkr)\b/i;

/** A booking or order number the page's own words give (the backend's `bookings.number_in`). */
export function numberIn(text: string): string | null {
  const found = /(?:order|booking|reservation|ticket|reference|confirmation|invoice|receipt|pnr)\s*(?:no\.?|number|#|id|ref\.?|code)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9-]{3,})/gi;
  for (let match = found.exec(text); match; match = found.exec(text)) {
    const value = match[1].replace(/^-+|-+$/g, "");
    if (/\d/.test(value)) return value;
  }
  return null;
}

/* ------------------------------------------------------------- the goal */

const DAYS = "(?:today|tonight|tomorrow|day after tomorrow|(?:this |next |on )?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))";
const MONTHS = "(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*";
const STOP = "(?=\\s+(?:on|for|this|next|tomorrow|today|tonight|at|by|in|please|and|with|using)\\b|[.,!?]|$)";

/** What the goal itself says, as facts: where from, where to, and the day. */
export function goalFacts(goal: string, shape: Shape): Fact[] {
  const facts: Fact[] = [];
  const add = (label: string, value: string | undefined) => {
    if (value && value.trim()) facts.push({ label, value: value.trim(), from: "goal" });
  };
  if (shape === "ticket") {
    const trip = new RegExp(`\\bfrom\\s+([a-z][a-z .'-]*?)\\s+(?:to|towards)\\s+([a-z][a-z .'-]*?)${STOP}`, "i").exec(goal);
    if (trip) {
      add("From", capital(trip[1]));
      add("To", capital(trip[2]));
    } else {
      const to = new RegExp(`\\b(?:to|for)\\s+([a-z][a-z .'-]*?)${STOP}`, "i").exec(goal);
      if (to && !new RegExp(`^${DAYS}$`, "i").test(to[1])) add("To", capital(to[1]));
    }
    const day = new RegExp(`\\b(${DAYS}|\\d{1,2}(?:st|nd|rd|th)?\\s+${MONTHS}(?:\\s+\\d{4})?|${MONTHS}\\s+\\d{1,2}(?:st|nd|rd|th)?(?:\\s+\\d{4})?)\\b`, "i").exec(goal);
    if (day) add("Date", capital(day[1].replace(/^on /i, "")));
  } else if (shape === "bill") {
    const ending = /\b(?:ending|reference|ref|consumer|number)\s*(?:no\.?|number|#)?\s*(\d{3,})/i.exec(goal)
      ?? /\b(\d{6,})\b/.exec(goal);
    if (ending) add("Reference", endingOf(ending[1]));
  } else if (shape === "receipt") {
    const item = /\b(?:order|buy|purchase|get)\s+(?:me\s+)?(?:an?\s+|the\s+|one\s+)?(.+?)(?:\s+(?:from|on|at|for|to|and)\b|[.,!?]|$)/i.exec(goal);
    if (item && item[1].length > 1) add("Item", capital(item[1]));
  }
  return facts;
}

/** A reference shown by its end: "ending 7890". */
function endingOf(reference: string): string {
  const digits = reference.replace(/\D/g, "");
  return digits.length >= 6 ? `ending ${digits.slice(-4)}` : reference;
}

/* ------------------------------------------------------------- the steps */

/**
 * What the person's answer told SIMBA: the boxes they filled in (never a
 * secret), and the choice they pressed. A plain "go ahead" teaches nothing.
 */
export function factsFromAnswer(step: StepPresented, actionId: string,
                                values: Record<string, string>): Fact[] {
  const facts: Fact[] = [];
  for (const field of step.fields) {
    const value = (values[field.id] ?? field.value ?? "").trim();
    if (!value) continue;
    // A password or a code is never kept: only that it was given, and safely.
    if (isSecret(field.label) || field.type === "password") {
      facts.push({ label: field.label, value: "", from: "typed", kept: true });
      continue;
    }
    facts.push({ label: field.label, value, from: "typed" });
  }
  const action = step.actions.find((candidate) => candidate.id === actionId);
  if (action && (action.sub || action.picture || actionId.startsWith("choice:"))) {
    const sort = whatIsAsked(step);
    const priced = MONEY.exec(`${action.sub ?? ""} ${action.label}`);
    facts.push({ label: sort ?? "You chose", value: action.label, from: "chosen",
                 picture: action.picture });
    if (priced) facts.push({ label: "Price", value: priced[0], from: "chosen" });
  }
  return facts;
}

/**
 * What a question is about, from its words: a bus or train, a seat, a name, a
 * place. Null when it cannot be told, and then nothing is waiting on the card.
 */
export function whatIsAsked(step: StepPresented): string | null {
  const text = `${step.instruction} ${step.fields.map((field) => field.label).join(" ")}`.toLowerCase();
  if (/\bseat/.test(text)) return "Seat";
  if (/\b(bus|train|coach|flight|service|which one|time)\b/.test(text)) return "Ride";
  if (/\b(passenger|your name|full name|traveller)\b/.test(text)) return "Passenger";
  if (/\bwhere from|from\b/.test(text)) return "From";
  if (/\bwhere to|going|\bto\b|destination/.test(text)) return "To";
  if (/\b(date|day|when|travelling)\b/.test(text)) return "Date";
  if (/\b(address|deliver|ship)\b/.test(text)) return "Deliver to";
  if (/\b(pay|payment)\b/.test(text)) return "Payment";
  if (/\b(edition|which book|which one|which item|which product|choose|pick)\b/.test(text)) return "Item";
  return null;
}

/**
 * The left panel's chip for an answer, in a few words: the choice as it was
 * pressed, the boxes as they were filled, or what was agreed.
 */
export function chipForAnswer(step: StepPresented, actionId: string,
                              values: Record<string, string>): string | null {
  if (actionId === "cancel" || actionId === "decline") return null;
  const action = step.actions.find((candidate) => candidate.id === actionId);
  if (action && (action.sub || action.picture || actionId.startsWith("choice:"))) {
    const price = MONEY.exec(`${action.sub ?? ""}`);
    return brief(price ? `${action.label} · ${price[0]}` : action.label, 40);
  }
  const typed = step.fields.flatMap((field) => {
    const value = (values[field.id] ?? field.value ?? "").trim();
    if (!value) return [];
    return [isSecret(field.label) || field.type === "password" ? field.label : `${field.label}: ${value}`];
  });
  if (typed.length > 0) {
    const secrets = step.fields.every((field) => isSecret(field.label) || field.type === "password");
    return brief(typed.join(" · "), secrets ? 40 : 56);
  }
  return step.final ? null : brief(firstLine(step.instruction), 50);
}

/* ------------------------------------------------------------- the card */

type Matcher = { key: string; label: string; test: RegExp };

const TICKET: Matcher[] = [
  { key: "from", label: "From", test: /^(from|origin|leaving|starting|departure (city|station))\b/i },
  { key: "to", label: "To", test: /^(to|destination|going|arriv\w*|travelling to)\b/i },
  { key: "date", label: "Date", test: /\b(date|day|when)\b/i },
  { key: "ride", label: "Bus", test: /\b(ride|bus|train|coach|service|flight|time|you chose|departure|class)\b/i },
  { key: "seat", label: "Seat", test: /\bseat/i },
  { key: "passenger", label: "Passenger", test: /\b(passenger|name|traveller)\b/i },
  { key: "price", label: "Price", test: /\b(amount|total|fare|price|cost|paying)\b/i },
];

const RECEIPT: Matcher[] = [
  { key: "item", label: "Item", test: /\b(item|items|product|title|you chose|book|what)\b/i },
  { key: "price", label: "Price", test: /^(price|item price|subtotal|book price)\b/i },
  { key: "delivery", label: "Delivery", test: /\b(delivery|shipping)\b/i },
  { key: "payment", label: "Payment", test: /\b(payment|paying|pay by|pay with)\b/i },
  { key: "deliverTo", label: "Deliver to", test: /\b(address|deliver to|ship to|city)\b/i },
  { key: "total", label: "Total", test: /\b(total|amount)\b/i },
];

const BILL: Matcher[] = [
  { key: "reference", label: "Reference", test: /\b(reference|consumer|account|number|customer)\b/i },
  { key: "amount", label: "Amount", test: /\b(amount|bill|payable|total|your bill)\b/i },
  { key: "due", label: "Due", test: /\b(due|before|pay by|last date)\b/i },
];

const MATCHERS: Partial<Record<Shape, Matcher[]>> = { ticket: TICKET, receipt: RECEIPT, bill: BILL };

/** Which slot a fact goes in, by its name (and, for a vague name, its value). */
function slotFor(shape: Shape, fact: Fact): string | null {
  const matchers = MATCHERS[shape];
  if (!matchers) return null;
  const label = fact.label.trim();
  // How many is not what: "Items in cart: 1" is a note on the item, not the item.
  if (/\b(items in cart|quantity|qty)\b/i.test(label)) return null;
  // "Trip: Lahore to Karachi" is two slots (handled by the caller).
  // A vague name is told by its value: "You chose" a seat is a seat.
  if (/^you chose$/i.test(label)) {
    if (shape === "ticket") return /\bseat\b/i.test(fact.value) ? "seat" : "ride";
    if (shape === "receipt") return "item";
  }
  if (shape === "ticket" && /\bseat/i.test(label)) return "seat";
  // The more specific names first.
  const order = shape === "ticket"
    ? ["seat", "passenger", "from", "to", "date", "price", "ride"]
    : shape === "receipt"
      ? ["deliverTo", "delivery", "payment", "total", "price", "item"]
      : ["due", "reference", "amount"];
  for (const key of order) {
    const matcher = matchers.find((candidate) => candidate.key === key);
    if (matcher?.test.test(label)) return key;
  }
  return null;
}

/** Fold a list of facts into slots: the latest fact for a slot wins. */
function place(shape: Shape, facts: Fact[]): Map<string, Fact> {
  const placed = new Map<string, Fact>();
  for (const fact of facts) {
    if (isSecret(fact.label) || fact.kept) continue;
    if (shape === "ticket" && /^(trip|route|journey)$/i.test(fact.label.trim())) {
      const split = /^(.+?)\s+(?:to|→|-)\s+(.+)$/i.exec(fact.value);
      if (split) {
        placed.set("from", { ...fact, label: "From", value: split[1] });
        placed.set("to", { ...fact, label: "To", value: split[2] });
      }
      continue;
    }
    const key = slotFor(shape, fact);
    // An amount is an amount: "Paying: Cash" is how, not how much.
    if (key && /^(price|total|amount)$/.test(key) && !/\d/.test(fact.value)) continue;
    if (!key) continue;
    // Where it goes is its address, then its city: both are said, in the order they were given.
    const before = placed.get(key);
    if (key === "deliverTo" && before && before.from !== "page" && fact.from !== "page"
        && !before.value.includes(fact.value) && !fact.value.includes(before.value)) {
      placed.set(key, { ...fact, value: `${before.value}, ${fact.value}` });
    } else {
      placed.set(key, fact);
    }
  }
  return placed;
}

/** What goes into the card, from the store. */
export interface CardInput {
  goal: string;
  genre?: string | null;
  site?: string | null;
  /** Everything learned, in order: the goal's, the person's, the page's. */
  facts: Fact[];
  /** The page's final screen, when it has been shown. */
  final: Detail[] | null;
  /** What was found: a look-up's answer, a bill's amount. */
  findings: Finding[];
  /** The step on screen, if it asks something. */
  step: StepPresented | null;
}

export function buildCard(input: CardInput): CardModel {
  const shape = shapeOf(input.goal, input.genre);
  const facts = [
    ...goalFacts(input.goal, shape),
    ...input.facts,
    ...(input.final ?? []).filter((detail) => !/^website$/i.test(detail.label))
      .map((detail): Fact => ({ label: detail.label, value: detail.value, from: "page" })),
    ...findingFacts(shape, input.findings),
  ];
  // Complete only when the page's final screen said something: with no details there is
  // nothing to have completed, and a card claiming it would be wrong.
  const complete = (input.final?.length ?? 0) > 0;

  if (shape === "form") return formCard(facts, input, complete);
  if (shape === "answer") return answerCard(input, complete);

  const matchers = MATCHERS[shape] ?? [];
  const placed = place(shape, facts);
  const asked = input.step && !input.step.final ? askedKey(shape, input.step) : null;
  const slots: Slot[] = matchers.map((matcher): Slot => {
    const fact = placed.get(matcher.key);
    const waiting = !fact && matcher.key === asked;
    const slot: Slot = { key: matcher.key, label: matcher.label, value: fact?.value ?? null, waiting };
    if (shape === "ticket" && matcher.key === "ride") slot.label = rideWord(input.goal, input.genre);
    if (shape === "receipt" && matcher.key === "item") {
      slot.picture = fact?.picture;
      const one = facts.find((candidate) => /items in cart|quantity/i.test(candidate.label));
      if (fact && one && one.value.trim() === "1") slot.note = "onlyOne";
    }
    return slot;
  });
  // A receipt's total is the page's own, never added up here.
  const filled = slots.filter((slot) => slot.value !== null).length;
  return { shape, slots, filled, total: slots.length, complete };
}

function askedKey(shape: Shape, step: StepPresented): string | null {
  const asked = whatIsAsked(step);
  if (!asked) return null;
  const key = {
    "Seat": "seat", "Ride": shape === "receipt" ? "item" : "ride", "Passenger": "passenger",
    "From": "from", "To": "to", "Date": "date", "Deliver to": "deliverTo", "Payment": "payment",
    "Item": "item",
  }[asked];
  return key ?? null;
}

/** "Bus", "Train" or "Flight": the word the goal used for the thing booked. */
export function rideWord(goal: string, genre?: string | null): string {
  const word = /\b(bus|train|flight|coach)\b/i.exec(goal)?.[1]?.toLowerCase();
  if (word === "train") return "Train";
  if (word === "flight") return "Flight";
  if (word === "coach") return "Coach";
  return genre === "Travel" || word ? "Bus" : "Bus";
}

function findingFacts(shape: Shape, findings: Finding[]): Fact[] {
  if (shape !== "bill") return [];
  return findings.map((finding): Fact => ({
    label: finding.label, value: finding.values?.[0] ?? finding.value, from: "page" }));
}

function formCard(facts: Fact[], input: CardInput, complete: boolean): CardModel {
  const slots: Slot[] = [];
  const seen = new Set<string>();
  for (const fact of facts) {
    const name = fact.label.toLowerCase();
    if (seen.has(name)) continue;
    if (fact.kept) {
      seen.add(name);
      slots.push({ key: fact.label, label: fact.label, value: "", waiting: false, kept: true });
      continue;
    }
    if (isSecret(fact.label)) continue;
    seen.add(name);
    slots.push({ key: fact.label, label: fact.label, value: fact.value, waiting: false });
  }
  // The boxes the person is being asked for, the first of them waiting.
  let first = true;
  for (const field of input.step?.fields ?? []) {
    if (seen.has(field.label.toLowerCase())) continue;
    seen.add(field.label.toLowerCase());
    const secret = field.type === "password" || isSecret(field.label);
    slots.push({ key: field.label, label: field.label, value: null, waiting: first && !secret });
    if (!secret) first = false;
  }
  const filled = slots.filter((slot) => slot.value !== null).length;
  return { shape: "form", slots, filled, total: Math.max(slots.length, 1), complete };
}

function answerCard(input: CardInput, complete: boolean): CardModel {
  const found = input.findings[0] ?? input.step?.findings?.[0];
  const slots: Slot[] = [
    { key: "answer", label: "Answer", value: found ? (found.values?.[0] ?? found.value) : null, waiting: false },
    { key: "site", label: "From", value: input.site ?? null, waiting: false },
  ];
  return { shape: "answer", slots, filled: slots.filter((slot) => slot.value !== null).length,
           total: slots.length, complete };
}
