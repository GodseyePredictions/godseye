/**
 * The advisor's tools that work on one user's own data: bankroll, stake sizing, logging a bet, history.
 *
 * `sizeBetFor` takes legs and a price, never a probability: it grades the slip itself and hands the
 * algorithm's chance to the staking engine. That is what keeps every stake traceable to the algorithm.
 */
import { betProfit, summarize, type Bet } from "../bets.ts";
import { gradeSlip, ratedLegs, type SlipLegInput } from "../slip/grade.ts";
import { toSavedLeg } from "../slip/recheck.ts";
import { legLabel } from "../slip/suggest.ts";
import { PROFILES, checkLimits, termsOf, tonightFrom, withWeeklyUnit, type Sizing } from "../staking.ts";
import type { UserRecord } from "../store/types.ts";
import type { Catalog } from "./legs.ts";

const round = (n: number, d = 2) => Math.round(n * 10 ** d) / 10 ** d;

/** get_bankroll */
export function bankrollStatus(user: UserRecord, now: Date) {
  if (!user.account || !(user.account.bankroll > 0))
    return { set: false, note: "This user has not set a bankroll. No stake can be suggested until they set one in Bankroll Strategy." };
  const account = withWeeklyUnit(user.account, now);
  const tonight = tonightFrom(user.bets, now);
  const limits = checkLimits(account, tonight, now);
  const terms = termsOf(account);
  return {
    set: true,
    bankroll_dollars: account.bankroll,
    risk_profile: account.profile === "custom" ? "Custom" : PROFILES[account.profile].label,
    unit_dollars: account.unit!.size,
    unit_percent_of_bankroll: round(terms.unitPct * 100),
    most_on_one_bet_dollars: limits.maxBet,
    most_in_one_night_dollars: limits.nightlyCap,
    staked_tonight_dollars: tonight.staked,
    room_left_tonight_dollars: limits.remaining,
    settled_result_tonight_dollars: tonight.settledProfit,
    user_limits: { stop_loss_dollars: account.limits.stopLoss ?? null, profit_lock_dollars: account.limits.profitLock ?? null, cool_off_until: account.limits.coolOffUntil ?? null },
    /** Null when betting is open. Otherwise no new bet may be sized. */
    limit_in_force: limits.stop,
    limit_message: limits.stop ? limits.message : null,
  };
}

export type SizeResult = {
  stake: Pick<Sizing, "status" | "label" | "units" | "dollars" | "reason" | "stop" | "cappedBy">;
  joint_probability: number | null;
  book_odds: number | null;
  rated_legs: number;
  unrated_legs: number;
  note: string;
};

/** size_bet */
export function sizeBetFor(user: UserRecord, legs: SlipLegInput[], totalOdds: number | null, catalog: Catalog, now: Date): SizeResult {
  if (!user.account || !(user.account.bankroll > 0))
    return { stake: { status: "blocked", label: "no bet", units: 0, dollars: 0, reason: "No bankroll is set.", stop: "setup", cappedBy: null },
             joint_probability: null, book_odds: totalOdds, rated_legs: 0, unrated_legs: legs.length,
             note: "The user has not set a bankroll, so there is no stake. Point them to Bankroll Strategy." };
  const grade = gradeSlip(legs, catalog, { totalOdds, account: user.account, tonight: tonightFrom(user.bets, now), now });
  const s = grade.stake!;
  return {
    stake: { status: s.status, label: s.label, units: s.units, dollars: s.dollars, reason: s.reason, stop: s.stop, cappedBy: s.cappedBy },
    joint_probability: grade.unrated === 0 ? grade.joint : null,
    book_odds: grade.bookOdds, rated_legs: grade.rated, unrated_legs: grade.unrated,
    note: s.status === "bet" ? "Quote the stake exactly as `label` gives it."
      : s.status === "blocked" ? "A limit is in force. Do not suggest a stake or a way around the limit."
      : s.status === "unrated" ? (grade.bookOdds === null ? "There is no price for the whole slip. Ask the user for their book's price." : `${grade.unrated || "Some"} leg(s) are unrated or the slip has no joint chance, so the engine gives no stake. Do not suggest one.`)
      : "The engine says no bet at this price. Do not suggest a stake.",
  };
}

/** log_bet: add a bet the user has placed to their ledger, and save its rated legs for re-checking. */
export function logBetFor(
  user: UserRecord, args: { sport: string; legs: SlipLegInput[]; totalOdds: number | null; stakeDollars: number; book: string | null },
  catalog: Catalog | undefined, now: Date, newId: () => string = () => crypto.randomUUID(),
): { logged: true; bet: Bet } | { logged: false; reason: string } {
  if (!(args.stakeDollars > 0)) return { logged: false, reason: "A bet needs a stake above zero. Ask the user what they staked." };
  if (!args.legs.length) return { logged: false, reason: "There are no legs to log." };
  const grade = catalog ? gradeSlip(args.legs, catalog, { totalOdds: args.totalOdds }) : null;
  const rated = grade ? ratedLegs(grade.legs) : [];
  const bet: Bet = {
    id: newId(), placedAt: now.toISOString(), sport: args.sport, book: args.book ?? user.profile.book ?? "", stake: round(args.stakeDollars), status: "open",
    legs: (grade?.legs ?? []).length
      ? grade!.legs.map((l) => ({ description: l.match ? legLabel(l.match) : l.text, odds: l.odds ?? 0 }))
      : args.legs.map((l) => ({ description: l.text ?? [l.player, l.threshold, l.market].filter(Boolean).join(" "), odds: l.odds ?? 0 })),
    ...(args.totalOdds != null ? { price: args.totalOdds } : {}),
    ...(grade && grade.unrated === 0 && grade.joint != null ? { modelChance: grade.joint } : {}),
  };
  user.bets = [bet, ...user.bets];
  if (catalog && rated.length)
    user.slips = [{ id: newId(), savedAt: bet.placedAt, sport: catalog.sport, built: catalog.built, betId: bet.id, legs: rated.map((l) => toSavedLeg(l)) }, ...user.slips].slice(0, 50);
  return { logged: true, bet };
}

const isTd = (b: Bet) => b.legs.some((l) => /anytime (td|touchdown)/i.test(l.description));
const record = (label: string, bets: Bet[]) => {
  const s = summarize(label, bets);
  return { group: label, bets: s.bets, won: s.won, lost: s.lost, open: s.bets - s.won - s.lost - s.push, staked_dollars: round(s.staked), profit_dollars: round(s.profit),
           hit_rate: s.won + s.lost > 0 ? round(s.won / (s.won + s.lost), 3) : null, return_on_stake: s.roi === null ? null : round(s.roi, 3) };
};

/** get_user_history: the user's own graded bets and the patterns in them. Their record, not the algorithm's. */
export function userHistory(user: UserRecord) {
  const bets = user.bets;
  if (!bets.length) return { bets: 0, note: "This user has no tracked bets yet, so there is no history or pattern to report." };
  const legGroup = (b: Bet) => (b.legs.length === 1 ? "singles" : b.legs.length <= 3 ? "2-3 leg parlays" : b.legs.length <= 5 ? "4-5 leg parlays" : "6+ leg parlays");
  const groups = ["singles", "2-3 leg parlays", "4-5 leg parlays", "6+ leg parlays"].map((g) => record(g, bets.filter((b) => legGroup(b) === g))).filter((r) => r.bets > 0);
  const sports = [...new Set(bets.map((b) => b.sport))].map((s) => record(s, bets.filter((b) => b.sport === s)));
  const settled = bets.filter((b) => b.status === "won" || b.status === "lost");
  const rated = settled.filter((b) => typeof b.modelChance === "number");
  return {
    overall: record("all tracked bets", bets),
    by_leg_count: groups,
    by_sport: sports,
    slips_with_a_touchdown_leg: record("slips with an anytime-touchdown leg", bets.filter(isTd)),
    slips_without_a_touchdown_leg: record("slips without one", bets.filter((b) => !isTd(b))),
    average_stake_dollars: round(bets.reduce((a, b) => a + b.stake, 0) / bets.length),
    largest_stake_dollars: Math.max(...bets.map((b) => b.stake)),
    average_legs_per_bet: round(bets.reduce((a, b) => a + b.legs.length, 0) / bets.length, 1),
    bets_the_algorithm_rated: rated.length,
    recent: bets.slice(0, 6).map((b) => ({ placed: b.placedAt.slice(0, 10), sport: b.sport, legs: b.legs.length, stake_dollars: b.stake, result: b.status, profit_dollars: round(betProfit(b)) })),
    note: settled.length < 20 ? `Only ${settled.length} settled bet(s): too few to call anything a pattern. Say so.` : "Patterns are from the user's own settled bets.",
  };
}
