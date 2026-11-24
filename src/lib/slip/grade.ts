/**
 * Grade a confirmed slip against the algorithm.
 *
 * Per leg: the algorithm's chance against the chance the leg's price implies, the edge, the algorithm's
 * own game-script and role risk note, and its injury designation.
 * Whole slip: the joint chance from the correlation engine (never the legs multiplied together),
 * the fair price, and the value at the book's price.
 *
 * Unrated legs are kept on the slip, labelled, and left out of every number.
 */
import { impliedProb, toDecimal } from "../odds.ts";
import { auditParsed, TICKET_RULES, type LegAudit } from "../advisor/audit.ts";
import { fairAmerican, jointProbability, legCorrelation } from "../advisor/joint.ts";
import { MARKET_LABEL, type Catalog, type Market, type RatedLeg, type Side, type Sport } from "../advisor/legs.ts";
import { sizeBet, type Account, type Sizing, type Tonight } from "../staking.ts";

/** Settings for grading and suggestions. Ticket floors live in TICKET_RULES (per sport). */
export const GRADE_CONFIG = {
  /** A leg whose chance trails its own price by more than this is a negative-value leg. */
  negativeEdge: -0.02,
  /** A leg whose correlations with the rest of the slip sum below this is fighting the other legs. */
  fightsScript: -0.04,
  /** Injury designations that take a player off a ticket. */
  outStatuses: ["out", "doubtful", "inactive", "ir", "injured reserve", "pup", "suspended"],
  /** Designations that make a leg worth a warning. */
  doubtStatuses: ["questionable"],
};

export type SlipLegInput = {
  player: string | null;
  market: Market | null;
  threshold: number | null;
  side: Side | null;
  /** The leg's own price, American odds. */
  odds?: number | null;
  /** How the leg read on the slip, for display. */
  text?: string;
};

export type LegFlag = "negative-value" | "fights-script" | "out" | "questionable" | "singles-only" | "below-floor";

export type GradedLeg = LegAudit & {
  odds: number | null;
  /** The chance the leg's own price implies, bookmaker margin included. */
  implied: number | null;
  injury: string | null;
  /** The algorithm's own risk note (game script, blowout, role). */
  risk: string | null;
  /** Sum of this leg's correlations with the other rated legs. Negative means it works against them. */
  withRest: number | null;
  flags: LegFlag[];
};

export type SlipGrade = {
  sport: Sport;
  built: string;
  legs: GradedLeg[];
  rated: number;
  unrated: number;
  /** The chance every rated leg hits. Null when the algorithm's output cannot give it. */
  joint: number | null;
  jointNote: string;
  /** American odds at which the rated legs break even. */
  fairOdds: number | null;
  /** The book's price for the whole slip, American odds. */
  bookOdds: number | null;
  bookImplied: number | null;
  /** Expected profit per $1 staked at the book's price. Null unless every leg is rated and there is a price. */
  value: number | null;
  valueNote: string;
  rules: { level: "warn" | "info"; rule: string; detail: string }[];
  stake: Sizing | null;
};

export type GradeOptions = { totalOdds?: number | null; account?: Account | null; tonight?: Tonight; now?: Date; sims?: number };

const label = (l: SlipLegInput) =>
  l.text ?? [l.player, l.market === "atd" ? "anytime touchdown" : l.market ? `${l.side === "under" ? "under " : ""}${l.threshold ?? "?"}${l.side === "under" ? "" : "+"} ${MARKET_LABEL[l.market]}` : "unknown market"].filter(Boolean).join(" ");
const validOdds = (o: number | null | undefined): o is number => typeof o === "number" && Number.isFinite(o) && Math.abs(o) >= 100;
const pct = (p: number) => `${Math.round(p * 100)}%`;

export function ratedLegs(legs: GradedLeg[]): RatedLeg[] {
  return legs.filter((l) => l.status === "rated" && l.match).map((l) => l.match as RatedLeg);
}

/** Ticket-rule findings for a set of rated legs (plus a count of unrated ones). */
export function ruleCheck(sport: Sport, rated: RatedLeg[], unrated: number): SlipGrade["rules"] {
  const out: SlipGrade["rules"] = [];
  const rules = TICKET_RULES[sport];
  const total = rated.length + unrated;
  if (total < 2) return out;
  const props = rated.filter((l) => l.market !== "atd");
  const below = props.filter((l) => l.prob < rules.floor);
  if (below.length)
    out.push({ level: "info", rule: "floor", detail: `${below.length} leg${below.length > 1 ? "s are" : " is"} under the ${pct(rules.floor)} floor Godseye uses for parlay legs.` });
  if (rules.weak !== null && rules.maxWeak !== null) {
    const weak = props.filter((l) => l.prob < rules.weak!);
    if (weak.length > rules.maxWeak)
      out.push({ level: "warn", rule: "weak-legs", detail: `${weak.length} legs are under ${pct(rules.weak)}. Godseye allows at most ${rules.maxWeak} on a ticket.` });
  }
  if (sport === "NFL" && rated.some((l) => l.market === "atd") && props.length)
    out.push({ level: "warn", rule: "td-with-props", detail: "This slip mixes a touchdown leg with player props. Godseye keeps anytime-TD tickets separate from props tickets." });
  const singles = rated.filter((l) => l.singlesOnly);
  if (singles.length)
    out.push({ level: "warn", rule: "singles-only", detail: `${[...new Set(singles.map((l) => l.player))].join(", ")}: the algorithm plays ${singles.length > 1 ? "these players" : "this player"} as a single only this week.` });
  if (rules.maxRebounds !== null && rated.filter((l) => l.market === "reb").length > rules.maxRebounds)
    out.push({ level: "warn", rule: "rebounds", detail: `More than ${rules.maxRebounds} rebound leg. Godseye allows at most ${rules.maxRebounds} on a slip.` });
  if (unrated)
    out.push({ level: "warn", rule: "unrated", detail: `${unrated} of ${total} legs ${unrated > 1 ? "are" : "is"} unrated and left out of every number below.` });
  return out;
}

const statusIn = (injury: string | null | undefined, list: string[]) => !!injury && list.some((s) => injury.toLowerCase().includes(s));

export function gradeSlip(input: SlipLegInput[], catalog: Catalog, opts: GradeOptions = {}): SlipGrade {
  const rules = TICKET_RULES[catalog.sport];
  const audited = input.map((l) => {
    const parsed = l.player && l.market && l.side && (l.market === "atd" || l.threshold !== null)
      ? { player: l.player, market: l.market, threshold: l.market === "atd" ? null : l.threshold, side: l.side }
      : null;
    return auditParsed(parsed, { text: label(l), odds: l.odds ?? null }, catalog);
  });
  const matches = audited.map((a) => (a.status === "rated" ? a.match : null));
  const rated = matches.filter((m): m is RatedLeg => !!m);

  const legs: GradedLeg[] = audited.map((a, i) => {
    const odds = validOdds(input[i].odds) ? (input[i].odds as number) : null;
    const m = matches[i];
    const withRest = m && catalog.corr && rated.length > 1
      ? rated.filter((o) => o !== m).reduce((sum, o) => sum + legCorrelation(m, o, catalog.corr!), 0)
      : null;
    const flags: LegFlag[] = [];
    if (m) {
      if (a.edge !== null && a.edge < GRADE_CONFIG.negativeEdge) flags.push("negative-value");
      if (withRest !== null && withRest < GRADE_CONFIG.fightsScript) flags.push("fights-script");
      if (statusIn(m.injury, GRADE_CONFIG.outStatuses)) flags.push("out");
      else if (statusIn(m.injury, GRADE_CONFIG.doubtStatuses)) flags.push("questionable");
      if (m.singlesOnly && input.length > 1) flags.push("singles-only");
      if (m.market !== "atd" && m.prob < rules.floor && input.length > 1) flags.push("below-floor");
    }
    return { ...a, odds, implied: odds === null ? null : impliedProb(odds), injury: m?.injury ?? null, risk: m?.risk ?? null, withRest, flags };
  });

  const unrated = legs.length - rated.length;
  const joint = jointProbability(rated, catalog.corr, opts.sims);
  const jointNote =
    rated.length === 0 ? "No leg on this slip is rated, so there is nothing to work out."
    : joint === null ? `Not stated. The ${catalog.sport} algorithm's output does not carry the correlations needed for a parlay's chance, and multiplying the legs would be a guess.`
    : rated.length === 1 ? "One rated leg: the chance is that leg's chance."
    : `From the algorithm's correlation engine over ${rated.length} rated legs, not the legs multiplied together.` + (unrated ? ` ${unrated} unrated leg${unrated > 1 ? "s are" : " is"} left out, so the real slip is less likely than this.` : "");

  const bookOdds = validOdds(opts.totalOdds) ? opts.totalOdds : legs.length === 1 ? legs[0].odds : null;
  const complete = unrated === 0 && joint !== null;
  const value = complete && bookOdds !== null ? joint * toDecimal(bookOdds) - 1 : null;
  const valueNote =
    value !== null ? (value > 0 ? "The algorithm's chance beats the book's price." : "The book's price does not pay enough for the algorithm's chance.")
    : bookOdds === null ? "No price for the whole slip, so its value cannot be worked out."
    : unrated ? "Not stated: the book's price covers every leg, and some legs are unrated."
    : "Not stated: there is no joint chance to compare with the price.";

  let stake: Sizing | null = null;
  if (opts.account && opts.tonight && opts.now)
    stake = sizeBet({ prob: complete ? joint : null, price: bookOdds }, opts.account, opts.tonight, opts.now);

  return {
    sport: catalog.sport, built: catalog.built, legs, rated: rated.length, unrated, joint, jointNote,
    fairOdds: joint === null ? null : fairAmerican(joint), bookOdds, bookImplied: bookOdds === null ? null : impliedProb(bookOdds),
    value, valueNote, rules: ruleCheck(catalog.sport, rated, unrated), stake,
  };
}
