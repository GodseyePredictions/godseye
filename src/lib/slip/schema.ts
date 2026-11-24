/**
 * The shape of a bet slip read from a screenshot, and the checks it must pass.
 *
 * The vision model fills this in. It is told to leave a field empty and name it in `unreadable`
 * rather than guess, and nothing here fills a gap either: a leg that is missing a player, a market
 * or a number goes back to the user to complete on the confirm screen.
 */
import { z } from "zod";
import { decimalToAmerican } from "../bets.ts";
import type { Market, Side } from "../advisor/legs.ts";

export const MARKET_VALUES = [
  "pass_yds", "pass_td", "pass_att", "rush_yds", "carries", "rec", "rec_yds", "atd",
  "pts", "reb", "ast", "fg3m", "stl", "blk", "pra", "pr", "pa",
  "other",
] as const;

export const ParsedLegSchema = z.object({
  sport: z.enum(["NFL", "NBA", "CFB", "other"]).nullable().describe("The sport of this leg, or null if it cannot be told."),
  game: z.string().nullable().describe('The matchup as printed, e.g. "BUF @ KC" or "Bills v Chiefs". Null if not shown.'),
  player: z.string().nullable().describe("The player's name exactly as printed. Null for a game line (moneyline, spread, total) or if unreadable."),
  market: z.enum(MARKET_VALUES).nullable().describe(
    "pass_yds passing yards; pass_td passing touchdowns; pass_att pass attempts; rush_yds rushing yards; carries rushing attempts; " +
    "rec receptions; rec_yds receiving yards; atd anytime touchdown scorer; pts points; reb rebounds; ast assists; fg3m three-pointers made; " +
    "stl steals; blk blocks; pra points+rebounds+assists; pr points+rebounds; pa points+assists; other for anything else. Null if unreadable."),
  market_text: z.string().describe("The market exactly as printed on the slip."),
  threshold: z.number().nullable().describe(
    'The number on the leg as printed: 225 for "225+", 224.5 for "Over 224.5". Null for anytime touchdown or if unreadable. Do not convert or round.'),
  side: z.enum(["over", "under", "milestone"]).nullable().describe('"milestone" for a "225+" style leg, "over" or "under" for a line. Null if neither applies.'),
  odds_text: z.string().nullable().describe('This leg\'s own price exactly as printed, e.g. "-115", "+140", "1.87", "5/2". Null if the slip shows no price for the leg.'),
  unreadable: z.array(z.string()).describe("Names of the fields above that are cut off, blurred or otherwise not legible. Empty when everything was read."),
});

export const ParsedSlipSchema = z.object({
  is_bet_slip: z.boolean().describe("False if the image is not a sportsbook bet slip."),
  book: z.string().nullable().describe('The sportsbook, e.g. "bet365" or "BetVictor", if it can be told from the image. Otherwise null.'),
  bet_type: z.enum(["single", "parlay", "same_game_parlay", "unknown"]),
  legs: z.array(ParsedLegSchema),
  total_odds_text: z.string().nullable().describe("The price of the whole bet exactly as printed. Null if not shown."),
  stake_text: z.string().nullable().describe('The stake exactly as printed, e.g. "$25.00". Null if not shown.'),
  unreadable: z.array(z.string()).describe("Anything on the slip as a whole that could not be read."),
});

export type ParsedLeg = z.infer<typeof ParsedLegSchema>;
export type ParsedSlip = z.infer<typeof ParsedSlipSchema>;

// ---------- prices and money, converted in code and never by the model ----------
/** A price as printed, in American odds. Null when it is not a price this code recognises. */
export function oddsToAmerican(text: string | null | undefined): number | null {
  if (!text) return null;
  const t = text.replace(/[\u2212\u2013\u2014]/g, "-").replace(/\s/g, "").replace(/^@/, "");
  if (/^(evs|evens?)$/i.test(t)) return 100;
  const frac = /^(\d+)\/(\d+)$/.exec(t);
  if (frac) {
    const [n, d] = [Number(frac[1]), Number(frac[2])];
    return n > 0 && d > 0 ? decimalToAmerican(1 + n / d) : null;
  }
  if (/^[+-]\d{3,6}$/.test(t)) return Number(t);
  // a bare number with a decimal point is a decimal price; a bare whole number of 100 or more is American
  if (/^\d+\.\d+$/.test(t)) {
    const d = Number(t);
    return d > 1 ? decimalToAmerican(d) : null;
  }
  if (/^\d{3,6}$/.test(t)) return Number(t);
  return null;
}

export function stakeToDollars(text: string | null | undefined): number | null {
  if (!text) return null;
  const m = /(\d+(?:[.,]\d{1,2})?)/.exec(text.replace(/,(?=\d{3}\b)/g, ""));
  if (!m) return null;
  const n = Number(m[1].replace(",", "."));
  return Number.isFinite(n) && n > 0 ? n : null;
}

// ---------- the draft the user confirms ----------
export type DraftLeg = {
  sport: "NFL" | "NBA" | "CFB" | "other" | null;
  game: string | null;
  player: string | null;
  market: (typeof MARKET_VALUES)[number] | null;
  marketText: string;
  /** The milestone: 225 for "225+" and for "Over 224.5". For an under, the line as printed. */
  threshold: number | null;
  side: Side | null;
  /** American odds, or null. */
  odds: number | null;
  /** What still needs the user's input before this leg can be graded. */
  needs: string[];
};
export type SlipDraft = {
  book: string | null;
  betType: ParsedSlip["bet_type"];
  legs: DraftLeg[];
  totalOdds: number | null;
  stake: number | null;
  /** Problems with the slip as a whole, in plain English. */
  problems: string[];
};

const FIELD_LABEL: Record<string, string> = { player: "player", market: "market", threshold: "number", odds_text: "price", game: "game", side: "over or under" };

/** What a leg still needs before it can be graded. Used again after the user edits a leg. */
export function legNeeds(l: Pick<DraftLeg, "player" | "market" | "threshold">): string[] {
  const needs: string[] = [];
  if (l.market === "other") return needs; // a game line or another market: it will be graded as unrated, nothing to fix
  if (!l.player) needs.push("player");
  if (!l.market) needs.push("market");
  if (l.market && l.market !== "atd" && l.threshold === null) needs.push("number");
  return needs;
}

/**
 * Validate what the model returned and turn it into the draft shown on the confirm screen.
 * Throws if the JSON does not match the schema at all. Anything merely missing becomes a "needs" note.
 */
export function toDraft(raw: unknown): SlipDraft {
  const slip = ParsedSlipSchema.parse(raw);
  const problems: string[] = [];
  if (!slip.is_bet_slip) problems.push("This does not look like a bet slip.");
  if (slip.is_bet_slip && slip.legs.length === 0) problems.push("No legs could be read from this image.");
  for (const u of slip.unreadable) problems.push(`Could not read: ${u}.`);

  const legs = slip.legs.map((l): DraftLeg => {
    // a milestone ("225+") and an over are both "at least this many"; only an under is the other side
    const side: Side | null = l.market === null ? null : l.side === "under" ? "under" : "over";
    // "Over 224.5" is the 225+ milestone. A milestone or an under keeps its number as printed.
    const threshold = l.threshold === null ? null : l.side === "over" ? Math.floor(l.threshold) + 1 : l.threshold;
    const leg: DraftLeg = {
      sport: l.sport, game: l.game, player: l.player?.trim() || null, market: l.market, marketText: l.market_text,
      threshold: l.market === "atd" ? null : threshold, side: l.market === "atd" ? "over" : side,
      odds: oddsToAmerican(l.odds_text), needs: [],
    };
    const flagged = l.unreadable.map((f) => FIELD_LABEL[f] ?? f).filter((f) => f !== "price" && f !== "game" && f !== "over or under");
    leg.needs = [...new Set([...legNeeds(leg), ...flagged])];
    if (l.odds_text && leg.odds === null) leg.needs.push("price");
    return leg;
  });

  const totalOdds = oddsToAmerican(slip.total_odds_text);
  if (slip.total_odds_text && totalOdds === null) problems.push(`The total price "${slip.total_odds_text}" could not be read as odds.`);
  return { book: slip.book, betType: slip.bet_type, legs, totalOdds, stake: stakeToDollars(slip.stake_text), problems };
}

/** The canonical market of a draft leg, or null when the algorithms have no such market. */
export const draftMarket = (l: DraftLeg): Market | null => (l.market && l.market !== "other" ? (l.market as Market) : null);
