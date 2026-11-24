/**
 * The check on every advisor reply before it stands: its figures and its picks must trace back to a tool.
 *
 * The system prompt tells the model the rules. This file enforces the two that matter most, in code,
 * so they hold even when the model gets it wrong:
 *
 *  1. Figures. Every percentage, price (American odds), dollar amount and unit stake in the reply must be
 *     a number a tool returned in this conversation, the user typed, or a fixed rule (a floor, a cap).
 *     A figure with no source is one the model worked out or made up.
 *  2. Picks. Every leg the reply names ("Josh Allen 225+ passing yards", "anytime touchdown") must name a
 *     player a tool returned or the user mentioned, so a pick cannot be invented when the tools came back empty.
 *
 * It only reads text. It does not judge whether advice is good.
 */
import { TICKET_RULES } from "./audit.ts";
import type { ChatMessage } from "./agent.ts";
import { CUSTOM_BOUNDS, KELLY_FRACTION, PROFILES, UNIT_PCT } from "../staking.ts";

export type Violation = { kind: "figure" | "pick"; text: string; why: string };
/**
 * What a reply may draw on. Figures are kept by kind, because the same number means different things:
 * a 20 that is a "20+ rushing yards" rung does not make "$20" a stake anyone worked out.
 */
export type Facts = {
  /** Every number seen: the source for probabilities and percentages. */
  numbers: number[];
  /** Prices in American odds. */
  odds: number[];
  /** Dollar amounts: stakes, bankroll, caps, results. */
  dollars: number[];
  /** Stakes in units. */
  units: number[];
  /** All the text, lower-cased, for checking that a named player came from somewhere. */
  corpus: string;
};

/** Probabilities and shares that are rules of the product, which the advisor may always quote as percentages. */
const RULE_NUMBERS: number[] = [
  ...Object.values(TICKET_RULES).flatMap((r) => [r.floor, r.weak]).filter((n): n is number => typeof n === "number"),
  ...Object.values(PROFILES).flatMap((p) => [p.maxBetPct, p.maxNightlyPct]),
  UNIT_PCT, KELLY_FRACTION, CUSTOM_BOUNDS.unitPct.min, CUSTOM_BOUNDS.unitPct.max, CUSTOM_BOUNDS.maxBetPct, CUSTOM_BOUNDS.maxNightlyPct,
];

const NUMBER = /-?\d+(?:,\d{3})*(?:\.\d+)?/g;
/** Dates, times and ids are not figures; left in, their digits would vouch for unrelated numbers. */
const NOISE = /\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)?|\b\d{1,2}:\d{2}\b|\b\d{2}-\d{7}\b/g;
const numbersIn = (text: string) => (text.replace(NOISE, " ").match(NUMBER) ?? []).map((n) => Number(n.replace(/,/g, ""))).filter(Number.isFinite);
const DOLLAR_TOKEN = /\$\s?(\d+(?:,\d{3})*(?:\.\d{1,2})?)/g;
const UNIT_TOKEN = /(?<![\w.])(\d+(?:\.\d+)?)\s?u(?:nits?)?\b/gi;
const ODDS_TOKEN = /(?<![\w.$])([+\u2212-]\d{3,5})(?!\w)/g;
const tokens = (text: string, re: RegExp) => [...text.matchAll(re)].map((m) => Number(m[1].replace(/,/g, "").replace("\u2212", "-"))).filter(Number.isFinite);

const MONEY_KEY = /dollar|stake|bankroll|profit|staked|payout|return/i;
const UNIT_KEY = /(^|_)units?($|_)/i;
const ODDS_KEY = /odds|price/i;

function collect(value: unknown, key: string, f: Facts, strings: string[]): void {
  if (typeof value === "number" && Number.isFinite(value)) {
    f.numbers.push(value);
    if (ODDS_KEY.test(key)) f.odds.push(value);
    if (UNIT_KEY.test(key) && !/dollar|percent/i.test(key)) f.units.push(value);
    else if (MONEY_KEY.test(key)) f.dollars.push(value);
  } else if (typeof value === "string") {
    addText(value, f, strings);
  } else if (Array.isArray(value)) {
    for (const v of value) collect(v, key, f, strings);
  } else if (value && typeof value === "object") {
    for (const [k, v] of Object.entries(value)) { strings.push(k); collect(v, k, f, strings); }
  }
}

/** Text from a tool or the context: its numbers count, and so do the typed figures written in it ("1.5u ($15)", "+450"). */
function addText(text: string, f: Facts, strings: string[]): void {
  strings.push(text);
  f.numbers.push(...numbersIn(text));
  f.dollars.push(...tokens(text, DOLLAR_TOKEN));
  f.units.push(...tokens(text, UNIT_TOKEN));
  f.odds.push(...tokens(text, ODDS_TOKEN));
}

/** What the user typed: they may give a price or a stake as a bare number ("450", "25 bucks"), so every number counts for both. */
function addUserText(text: string, f: Facts, strings: string[]): void {
  // the note that reports a failed check quotes the very figures that failed; it must not vouch for them
  if (text.startsWith("[Automatic check]")) return;
  addText(text, f, strings);
  const all = numbersIn(text);
  f.odds.push(...all);
  f.dollars.push(...all);
}

/** What the reply is allowed to draw on: tool results and the user's own words in this conversation, plus `context`. */
export function factsFrom(messages: ChatMessage[], context = ""): Facts {
  const f: Facts = { numbers: [...RULE_NUMBERS], odds: [], dollars: [], units: [], corpus: "" };
  const strings: string[] = [];
  addText(context, f, strings);
  for (const m of messages) {
    if (m.role !== "user") continue;
    if (typeof m.content === "string") { addUserText(m.content, f, strings); continue; }
    for (const b of m.content) {
      if (b.type === "text") addUserText(b.text, f, strings);
      else if (b.type === "tool_result") {
        const raw = typeof b.content === "string" ? b.content : JSON.stringify(b.content ?? "");
        try { collect(JSON.parse(raw), "", f, strings); } catch { addText(raw, f, strings); }
      }
    }
  }
  f.corpus = strings.join("\n").toLowerCase();
  return f;
}

const near = (list: number[], x: number, tol: number) => list.some((n) => Math.abs(n - x) <= tol);

// what counts as a figure in a reply
const PERCENT = /(?<![\w.])(-?\d+(?:\.\d+)?)\s?%/g;
const ODDS = /(?<![\w.$])([+−-]\d{3,5})(?![\d.]*\s?%)(?!\w)/g;
const DOLLARS = /\$\s?(\d+(?:,\d{3})*(?:\.\d{1,2})?)/g;
const UNITS = /(?<![\w.])(\d+(?:\.\d+)?)\s?u(?:nits?)?\b/gi;
const POINTS = /([+−-]?\d+(?:\.\d+)?)\s?(?:pts|points)\b(?!\s*(?:\+|and|&)\s*(?:reb|ast))/gi;

/** A leg named in prose: a capitalised name followed by a milestone or "anytime touchdown". */
const LEG = /((?:[A-Z][A-Za-z.'’-]+\s){1,4})(?:(\d+)\+\s?(?:[a-z-]+\s?){1,4}|anytime (?:td|touchdown))/g;
const NOT_NAMES = new Set(["the", "a", "an", "and", "or", "but", "your", "my", "this", "that", "his", "her", "their", "with", "for", "swap", "add", "remove", "take", "play", "keep",
  "drop", "try", "leg", "legs", "over", "under", "at", "on", "in", "if", "so", "then", "also", "instead", "i", "it", "is", "are", "was", "to", "of", "no", "yes", "both", "each"]);

export function checkReply(reply: string, facts: Facts): Violation[] {
  const out: Violation[] = [];
  const seen = new Set<string>();
  const flag = (kind: Violation["kind"], text: string, why: string) => {
    const key = `${kind}:${text}`;
    if (!seen.has(key)) { seen.add(key); out.push({ kind, text, why }); }
  };
  const num = (s: string) => Number(s.replace(/,/g, "").replace("−", "-"));

  for (const m of reply.matchAll(PERCENT)) {
    const x = num(m[1]);
    // a tool gives a probability as 0.835 or a percentage as 83.5; either may be quoted as "83.5%" or "84%"
    const ok = facts.numbers.some((n) => Math.abs(n * 100 - x) <= 0.55 || Math.abs(Math.abs(n) * 100 - Math.abs(x)) <= 0.55 || Math.abs(n - x) <= 0.55);
    if (!ok) flag("figure", m[0].trim(), "a percentage no tool returned");
  }
  for (const m of reply.matchAll(ODDS)) if (!near(facts.odds, num(m[1]), 0.5) && !near(facts.odds, Math.abs(num(m[1])), 0.5)) flag("figure", m[1], "a price no tool returned and the user did not give");
  for (const m of reply.matchAll(DOLLARS)) if (!near(facts.dollars, num(m[1]), 0.011)) flag("figure", m[0], "a dollar amount no tool returned");
  for (const m of reply.matchAll(UNITS)) if (!near(facts.units, num(m[1]), 0.051)) flag("figure", m[0].trim(), "a unit stake that did not come from size_bet");
  for (const m of reply.matchAll(POINTS)) {
    const x = Math.abs(num(m[1]));
    // an edge in points is a probability difference times 100; projected points (NBA) are plain numbers
    if (!facts.numbers.some((n) => Math.abs(Math.abs(n) * 100 - x) <= 0.55 || Math.abs(Math.abs(n) - x) <= 0.55)) flag("figure", m[0].trim(), "a points figure no tool returned");
  }

  for (const m of reply.matchAll(LEG)) {
    const words = m[1].trim().split(/\s+/).filter((w) => !NOT_NAMES.has(w.toLowerCase().replace(/[.'’]/g, "")));
    if (!words.length) continue;
    const surname = words[words.length - 1].toLowerCase().replace(/[.'’]/g, "");
    if (surname.length < 3) continue;
    const known = facts.corpus.replace(/[.'’]/g, "").includes(surname);
    const rung = m[2] ? near(facts.numbers, Number(m[2]), 0.01) : true;
    if (!known) flag("pick", m[0].trim(), `${words.join(" ")} was not returned by any tool or mentioned by the user`);
    else if (!rung) flag("pick", m[0].trim(), `the ${m[2]}+ milestone was not returned by any tool or mentioned by the user`);
  }
  return out;
}

/** The note sent back to the model when a reply fails the check, asking for one rewrite. */
export function correctionNote(violations: Violation[]): string {
  return [
    "[Automatic check] Your last reply was not shown to the user because it contained things that did not come from a tool result:",
    ...violations.slice(0, 12).map((v) => `- "${v.text}": ${v.why}`),
    "Write the reply again. Use only figures and legs that a tool returned in this conversation or that the user gave you. If you need a number you do not have, call the tool that returns it; if no tool returns it, say plainly that the algorithm has no number for it. Do not mention this check.",
  ].join("\n");
}

/** What the user sees if a rewrite also fails: nothing unverified reaches them. */
export const SAFE_REPLY =
  "I could not back up everything in my answer with the algorithm's output, so I have held it back rather than show you a number I cannot stand behind. Ask me again, or ask for one thing at a time: a player's rungs, a slip audit, or a stake for a slip with its price.";
