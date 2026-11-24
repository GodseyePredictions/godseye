/**
 * Audit a user's own bet slip against the algorithms.
 *
 * Every leg comes back either rated, with the algorithm's own probability, or unrated with the reason.
 * Nothing is estimated, rounded to a nearby rung or filled in: unrated means unrated.
 * The chance of the whole slip is not worked out here. It depends on how the legs move together, which
 * only the algorithms measure, so it stays empty until an algorithm supplies it.
 */
import { impliedProb } from "../odds.ts";
import { sizeBet, type Account, type Sizing, type Tonight } from "../staking.ts";
import { MARKET_LABEL, matchPlayers, type Catalog, type Market, type RatedLeg, type Sport } from "./legs.ts";
import { parseLeg, type ParsedLeg } from "./parse.ts";

/** Ticket rules by sport (CLAUDE.md). A rule in one sport does not apply to the other. */
export const TICKET_RULES = {
  NFL: { floor: 0.7, weak: 0.65, maxWeak: 1, maxRebounds: null as number | null },
  NBA: { floor: 0.75, weak: null as number | null, maxWeak: null as number | null, maxRebounds: 1 },
};

export type SlipLeg = { text: string; /** The leg's own price, American odds, if the slip shows one. */ odds?: number | null };

export type Unrated =
  | "unreadable" // the text could not be read as player + market + number
  | "player-not-found" // the algorithm has no numbers for this player on the current slate
  | "ambiguous-player" // the name fits more than one player
  | "market-not-rated" // the algorithm does not rate this market for this player
  | "rung-not-rated"; // it rates the market, but not this milestone

export type LegAudit = {
  text: string;
  parsed: ParsedLeg | null;
  status: "rated" | "unrated";
  /** The algorithm's chance. Null when unrated. */
  prob: number | null;
  /** The catalogue entry the leg matched. */
  match: RatedLeg | null;
  unrated: Unrated | null;
  /** Plain-English reason, for a person. */
  note: string;
  /** Milestones the algorithm does rate for this player and market, when the one asked for is not among them. */
  ratedRungs: number[];
  /** Candidates when the name is ambiguous. */
  candidates: string[];
  /** The algorithm's chance minus the chance the leg's own price implies. Null without both. */
  edge: number | null;
};

export type RuleFinding = { level: "warn" | "info"; rule: string; detail: string };

export type SlipAudit = {
  sport: Sport;
  built: string;
  legs: LegAudit[];
  rated: number;
  unrated: number;
  rules: RuleFinding[];
  /** The whole slip's chance. Always null for more than one leg: see the note at the top of this file. */
  slipProb: number | null;
  slipProbNote: string;
  /** A stake, only when the engine has a rated chance and a real price to size against. */
  stake: Sizing | null;
};

const rung = (mk: Market, k: number | null) => (mk === "atd" ? "anytime touchdown" : `${k}+ ${MARKET_LABEL[mk]}`);
const pct = (p: number) => `${Math.round(p * 100)}%`;

export function auditLeg(leg: SlipLeg, catalog: Catalog): LegAudit {
  const base = { text: leg.text, prob: null, match: null, ratedRungs: [] as number[], candidates: [] as string[], edge: null };
  const parsed = parseLeg(leg.text);
  if (!parsed)
    return { ...base, parsed: null, status: "unrated", unrated: "unreadable",
             note: "Could not read this leg as a player, a market and a number." };

  const players = matchPlayers(parsed.player, catalog);
  if (players.length === 0)
    return { ...base, parsed, status: "unrated", unrated: "player-not-found",
             note: `The ${catalog.sport} algorithm has no numbers for ${parsed.player} on the current slate.` };
  if (players.length > 1)
    return { ...base, parsed, status: "unrated", unrated: "ambiguous-player", candidates: players,
             note: `"${parsed.player}" could be ${players.join(" or ")}. Give the full name.` };

  const player = players[0];
  const market = catalog.legs.filter((l) => l.player === player && l.market === parsed.market && l.side === parsed.side);
  if (market.length === 0)
    return { ...base, parsed, status: "unrated", unrated: "market-not-rated",
             note: parsed.side === "under"
               ? `The algorithm rates milestones (for example 20+), not unders, for ${player}.`
               : catalog.sport === "NBA"
                 ? `No ${MARKET_LABEL[parsed.market]} leg for ${player} is among tonight's posted NBA picks, so it is unrated here.`
                 : `The algorithm does not rate ${MARKET_LABEL[parsed.market]} for ${player}.` };

  const match = market.find((l) => l.threshold === parsed.threshold);
  if (!match) {
    const ratedRungs = market.map((l) => l.threshold).filter((k): k is number => k !== null).sort((a, b) => a - b);
    return { ...base, parsed, status: "unrated", unrated: "rung-not-rated", ratedRungs,
             note: `${catalog.sport === "NBA" ? "Tonight's posted NBA picks do not include" : "The algorithm does not rate"} ${rung(parsed.market, parsed.threshold)} for ${player}. ${catalog.sport === "NBA" ? "They include" : "It rates"} ${ratedRungs.map((k) => `${k}+`).join(", ")}.` };
  }
  const priced = typeof leg.odds === "number" && Number.isFinite(leg.odds) && Math.abs(leg.odds) >= 100;
  return {
    ...base, parsed, status: "rated", unrated: null, prob: match.prob, match,
    edge: priced ? match.prob - impliedProb(leg.odds as number) : null,
    note: `${player} ${rung(match.market, match.threshold)}: the algorithm makes it ${pct(match.prob)}.`
      + (match.singlesOnly ? " The algorithm marks him as a single only this week, not a parlay leg." : ""),
  };
}

function ruleFindings(sport: Sport, legs: LegAudit[]): RuleFinding[] {
  const out: RuleFinding[] = [];
  const rules = TICKET_RULES[sport];
  const rated = legs.filter((l) => l.status === "rated" && l.match);
  if (legs.length < 2) return out;

  // the floor and the weak-leg rule are about prop legs; an anytime touchdown is a different kind of ticket
  const props = rated.filter((l) => l.match!.market !== "atd");
  const below = props.filter((l) => (l.prob as number) < rules.floor);
  if (below.length)
    out.push({ level: "info", rule: "floor",
               detail: `${below.length} leg${below.length > 1 ? "s are" : " is"} under the ${pct(rules.floor)} floor Godseye uses for parlay legs: ${below.map((l) => `${l.match!.player} ${rung(l.match!.market, l.match!.threshold)} (${pct(l.prob as number)})`).join("; ")}.` });

  if (rules.weak !== null && rules.maxWeak !== null) {
    const weak = props.filter((l) => (l.prob as number) < rules.weak!);
    if (weak.length > rules.maxWeak)
      out.push({ level: "warn", rule: "weak-legs",
                 detail: `${weak.length} legs are under ${pct(rules.weak)}. Godseye allows at most ${rules.maxWeak} on a ticket.` });
  }
  if (sport === "NFL") {
    const td = legs.some((l) => l.parsed?.market === "atd");
    const prop = legs.some((l) => l.parsed && l.parsed.market !== "atd");
    if (td && prop)
      out.push({ level: "warn", rule: "td-with-props",
                 detail: "This slip mixes a touchdown leg with player props. Godseye keeps anytime-TD tickets separate from props tickets." });
    const singles = rated.filter((l) => l.match!.singlesOnly);
    if (singles.length)
      out.push({ level: "warn", rule: "singles-only",
                 detail: `${singles.map((l) => l.match!.player).join(", ")}: the algorithm plays ${singles.length > 1 ? "these players" : "this player"} as a single only this week.` });
  }
  if (rules.maxRebounds !== null) {
    const reb = legs.filter((l) => l.parsed?.market === "reb").length;
    if (reb > rules.maxRebounds)
      out.push({ level: "warn", rule: "rebounds",
                 detail: `${reb} rebound legs. Godseye allows at most ${rules.maxRebounds} on a slip.` });
  }
  const unrated = legs.length - rated.length;
  if (unrated)
    out.push({ level: "warn", rule: "unrated",
               detail: `${unrated} of ${legs.length} legs ${unrated > 1 ? "are" : "is"} unrated, so the algorithm cannot say anything about this slip as a whole.` });
  return out;
}

export type AuditOptions = {
  /** The price of the whole slip, American odds. */
  price?: number | null;
  /** With these, a single rated leg is sized by the staking engine. */
  account?: Account | null;
  tonight?: Tonight;
  now?: Date;
};

export function auditSlip(legs: SlipLeg[], catalog: Catalog, opts: AuditOptions = {}): SlipAudit {
  const audited = legs.map((l) => auditLeg(l, catalog));
  const rated = audited.filter((l) => l.status === "rated").length;
  const single = audited.length === 1 ? audited[0] : null;

  // One leg: the slip's chance is that leg's chance. More than one: only an algorithm can say.
  const slipProb = single && single.status === "rated" ? single.prob : null;
  const slipProbNote =
    audited.length === 0 ? "No legs to audit."
    : single ? (slipProb === null ? "This leg is unrated." : "A single: the slip's chance is the leg's chance.")
    : "Not stated. A parlay's chance depends on how its legs move together, which only the algorithm's own simulation measures. Multiplying the legs would be a guess.";

  let stake: Sizing | null = null;
  if (opts.account && opts.tonight && opts.now) {
    const price = opts.price ?? (single ? single.match && legs[0].odds : null) ?? null;
    stake = sizeBet({ prob: slipProb, price }, opts.account, opts.tonight, opts.now);
  }
  return { sport: catalog.sport, built: catalog.built, legs: audited, rated, unrated: audited.length - rated,
           rules: ruleFindings(catalog.sport, audited), slipProb, slipProbNote, stake };
}
