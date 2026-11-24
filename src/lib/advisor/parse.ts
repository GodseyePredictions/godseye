/**
 * Read one leg of a user's bet slip into player, market, milestone and side.
 * This only reads text. Whether the algorithm rates the leg is decided in audit.ts.
 */
import type { Market, Side } from "./legs.ts";

export type ParsedLeg = {
  player: string;
  market: Market;
  /** "225+" and "Over 224.5" are both 225. Null for anytime touchdown. For an under, the line as written. */
  threshold: number | null;
  side: Side;
};

/** Longest phrases first, so "passing touchdowns" is not read as "touchdowns". */
const MARKET_WORDS: [RegExp, Market][] = [
  [/\b(anytime|any time)\s+(td|touchdown)s?(\s+scorer)?\b|\b(to score a|scores? a)\s+(td|touchdown)\b|\batd\b/, "atd"],
  [/\b(pts?|points)\s*(\+|&|and)\s*(rebs?|rebounds)\s*(\+|&|and)\s*(asts?|assists)\b|\bpra\b/, "pra"],
  [/\b(pts?|points)\s*(\+|&|and)\s*(rebs?|rebounds)\b/, "pr"],
  [/\b(pts?|points)\s*(\+|&|and)\s*(asts?|assists)\b/, "pa"],
  [/\bpass(ing)?\s+(tds?|touchdowns?)\b|\b(td|touchdown)\s+passes\b/, "pass_td"],
  [/\bpass(ing)?\s+(yds?|yards)\b/, "pass_yds"],
  [/\bpass(ing)?\s+(att|atts|attempts)\b/, "pass_att"],
  [/\brush(ing)?\s+(yds?|yards)\b/, "rush_yds"],
  [/\brush(ing)?\s+(att|atts|attempts)\b|\bcarries\b/, "carries"],
  [/\brec(eiving)?\s+(yds?|yards)\b/, "rec_yds"],
  [/\breceptions?\b|\bcatches\b|\brecs?\b/, "rec"],
  [/\b(3|three)[\s-]?(pt|pts|pointers?|point)\b.*\bmade\b|\bthrees?(\s+made)?\b|\b3pm\b|\bmade\s+threes\b/, "fg3m"],
  [/\brebounds?\b|\brebs?\b/, "reb"],
  [/\bassists?\b|\basts?\b/, "ast"],
  [/\bsteals?\b|\bstls?\b/, "stl"],
  [/\bblocks?\b|\bblks?\b/, "blk"],
  [/\bpoints\b|\bpts\b/, "pts"],
];

const NUM = String.raw`(\d+(?:\.\d+)?)`;

/** Returns null when no market can be read, or a prop has no number. */
export function parseLeg(text: string): ParsedLeg | null {
  const raw = text.replace(/[−–—]/g, "-").replace(/\s+/g, " ").trim();
  const lower = raw.toLowerCase();

  let market: Market | null = null;
  let marketAt = -1;
  let marketEnd = -1;
  for (const [re, mk] of MARKET_WORDS) {
    const m = re.exec(lower);
    if (m) {
      market = mk;
      marketAt = m.index;
      marketEnd = m.index + m[0].length;
      break;
    }
  }
  if (!market) return null;

  // the number: "225+", "over 224.5", "o224.5", "under 5.5", "u5.5"
  let threshold: number | null = null;
  let side: Side = "over";
  let numAt = -1;
  let numEnd = -1;
  const plus = new RegExp(String.raw`${NUM}\s*\+`).exec(lower);
  const ou = new RegExp(String.raw`\b(over|under|o|u)\s*${NUM}\b`).exec(lower);
  if (plus) {
    threshold = Number(plus[1]);
    [numAt, numEnd] = [plus.index, plus.index + plus[0].length];
  } else if (ou) {
    const line = Number(ou[2]);
    side = ou[1].startsWith("u") ? "under" : "over";
    // over 224.5 is the 225+ milestone; a whole-number over (over 224) needs 225 as well
    threshold = side === "over" ? Math.floor(line) + 1 : line;
    [numAt, numEnd] = [ou.index, ou.index + ou[0].length];
  }
  if (market !== "atd" && threshold === null) return null;
  if (market === "atd") threshold = null;

  // the player is what comes before the first of the market words and the number
  const cuts = [marketAt, numAt].filter((i) => i >= 0);
  let player = raw.slice(0, Math.min(...cuts)).trim();
  if (!player) {
    // "Anytime TD: Josh Allen" or "225+ Passing Yards Josh Allen"
    player = raw.slice(Math.max(marketEnd, numEnd)).trim();
  }
  player = player.replace(/^[\s:,\-|]+|[\s:,\-|(]+$/g, "").replace(/\s+(to|will)$/i, "").trim();
  if (!player || /\d/.test(player)) return null;
  return { player, market, threshold, side };
}
