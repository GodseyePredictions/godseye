/**
 * The staking engine: the only place a stake number is worked out.
 * The site and the chat advisor both call this module; neither does its own sizing.
 *
 * Rules it implements (see CLAUDE.md, "Staking" and "Responsible gambling"):
 *  - quarter-Kelly on the algorithm's probability, never anyone's guess;
 *  - capped by the risk profile's maximum per bet and maximum nightly exposure;
 *  - a unit is 1% of bankroll (or the user's own share in a Custom profile), set once a week and not moved
 *    by a win or a loss in between;
 *  - a leg or slip the algorithm has not rated gets no stake number at all ("unrated");
 *  - the user's own stop-loss, profit lock, nightly cap and cool-off always win over a suggestion.
 *
 * Money is in dollars. Probabilities are 0..1. Prices are American odds.
 */
import { expectedValue, kellyStake } from "./odds.ts";
import { betProfit, type Bet } from "./bets.ts";

// ---------- settings: every threshold lives here ----------
export const KELLY_FRACTION = 0.25;
/** One unit as a share of bankroll. */
export const UNIT_PCT = 0.01;
/** Stakes are shown to a tenth of a unit, always rounded down so a cap is never exceeded. */
export const UNIT_STEP = 0.1;
/** The betting day and the staking week both turn over at 10:00 UTC (early morning in North America). */
export const DAY_TURNOVER_UTC_HOUR = 10;
/** The staking week starts on Tuesday, after Monday night's games. 0 = Sunday. */
export const WEEK_START_DAY = 2;

export type PresetId = "conservative" | "balanced" | "aggressive";
export type ProfileId = PresetId | "custom";
export type Profile = { label: string; blurb: string; maxBetPct: number; maxNightlyPct: number };
export const PROFILES: Record<PresetId, Profile> = {
  conservative: { label: "Conservative", blurb: "Up to 1% of bankroll on a bet, 3% in a night.", maxBetPct: 0.01, maxNightlyPct: 0.03 },
  balanced: { label: "Balanced", blurb: "Up to 2% of bankroll on a bet, 5% in a night.", maxBetPct: 0.02, maxNightlyPct: 0.05 },
  aggressive: { label: "Aggressive", blurb: "Up to 3% of bankroll on a bet, 8% in a night.", maxBetPct: 0.03, maxNightlyPct: 0.08 },
};

/**
 * A Custom profile: the user's own risk tolerance, in units.
 * Sizing is still quarter-Kelly; these only set how big a unit is and where the caps sit.
 */
export type CustomProfile = {
  /** One unit as a share of bankroll, e.g. 0.01 for 1%. */
  unitPct: number;
  /** The most units on one bet. */
  maxBetUnits: number;
  /** The most units staked in one night. */
  maxNightlyUnits: number;
};
/** How far a Custom profile may go. Anything outside is pulled back to the nearest allowed value. */
export const CUSTOM_BOUNDS = {
  unitPct: { min: 0.0025, max: 0.02 },
  /** No single bet above this share of bankroll, whatever the unit settings multiply out to. */
  maxBetPct: 0.05,
  /** No night above this share of bankroll. */
  maxNightlyPct: 0.15,
  minUnits: 0.5,
};
export const CUSTOM_DEFAULT: CustomProfile = { unitPct: UNIT_PCT, maxBetUnits: 2, maxNightlyUnits: 5 };

const clamp = (x: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, x));
const finite = (x: unknown, fallback: number) => (typeof x === "number" && Number.isFinite(x) ? x : fallback);

/** A Custom profile pulled inside the bounds. A night can never be capped below a single bet. */
export function clampCustom(c: Partial<CustomProfile> | undefined): CustomProfile {
  const b = CUSTOM_BOUNDS;
  const unitPct = clamp(finite(c?.unitPct, CUSTOM_DEFAULT.unitPct), b.unitPct.min, b.unitPct.max);
  const maxBetUnits = clamp(finite(c?.maxBetUnits, CUSTOM_DEFAULT.maxBetUnits), b.minUnits, b.maxBetPct / unitPct);
  const maxNightlyUnits = clamp(finite(c?.maxNightlyUnits, CUSTOM_DEFAULT.maxNightlyUnits), maxBetUnits, b.maxNightlyPct / unitPct);
  const r = (x: number) => Math.round(x * 100) / 100;
  return { unitPct, maxBetUnits: r(maxBetUnits), maxNightlyUnits: r(maxNightlyUnits) };
}

/** The numbers the engine sizes with, whichever kind of profile the account uses. */
export type Terms = { unitPct: number; maxBetPct: number; maxNightlyPct: number };
export function termsOf(account: Pick<Account, "profile" | "custom">): Terms {
  if (account.profile === "custom") {
    const c = clampCustom(account.custom);
    return { unitPct: c.unitPct, maxBetPct: c.unitPct * c.maxBetUnits, maxNightlyPct: c.unitPct * c.maxNightlyUnits };
  }
  const p = PROFILES[account.profile] ?? PROFILES.balanced;
  return { unitPct: UNIT_PCT, maxBetPct: p.maxBetPct, maxNightlyPct: p.maxNightlyPct };
}

/** Limits the user sets for themselves. Each one can only make the engine stricter. */
export type Limits = {
  /** Stop for the night once tonight's settled losses reach this many dollars. */
  stopLoss?: number;
  /** Stop for the night once tonight's settled profit reaches this many dollars. */
  profitLock?: number;
  /** The most to stake in one night, in dollars. Used when it is lower than the profile's cap. */
  nightlyCap?: number;
  /** No stakes are suggested until this time (ISO date). */
  coolOffUntil?: string;
};

export type Account = {
  bankroll: number;
  profile: ProfileId;
  /** The user's own settings, used when `profile` is "custom". */
  custom?: CustomProfile;
  /** This week's unit, fixed when the week began. `pct` is the share of bankroll it was set at. */
  unit: { size: number; weekOf: string; pct?: number } | null;
  limits: Limits;
};

/** What has already happened tonight. */
export type Tonight = { staked: number; settledProfit: number };

const cents = (n: number) => Math.round(n * 100) / 100;
const HOUR = 3_600_000;

// ---------- weeks and nights ----------
/** The betting day a moment belongs to, as YYYY-MM-DD. */
export function bettingDay(now: Date): string {
  return new Date(now.getTime() - DAY_TURNOVER_UTC_HOUR * HOUR).toISOString().slice(0, 10);
}

/** The first betting day (a Tuesday) of the staking week a moment belongs to. */
export function stakingWeek(now: Date): string {
  const d = new Date(`${bettingDay(now)}T00:00:00Z`);
  const back = (d.getUTCDay() - WEEK_START_DAY + 7) % 7;
  return new Date(d.getTime() - back * 24 * HOUR).toISOString().slice(0, 10);
}

/** One unit for a bankroll, at 1% or at the share given. */
export function unitFor(bankroll: number, unitPct: number = UNIT_PCT): number {
  return cents(Math.max(0, bankroll) * unitPct);
}

/**
 * The account with this week's unit in place. Inside a week the unit never changes, whatever has
 * happened to the bankroll; when a new week starts it is set again from the bankroll at that moment.
 * Choosing a different unit share (a Custom profile, or leaving one) is a deliberate change and applies at once.
 */
export function withWeeklyUnit(account: Account, now: Date): Account {
  const weekOf = stakingWeek(now);
  const pct = termsOf(account).unitPct;
  const u = account.unit;
  if (u && u.weekOf === weekOf && u.size > 0 && (u.pct ?? UNIT_PCT) === pct) return account;
  return { ...account, unit: { size: unitFor(account.bankroll, pct), weekOf, pct } };
}

/** A fresh account. Setting up (or deliberately resetting) a bankroll is the one time the unit is set mid-week. */
export function openAccount(bankroll: number, profile: ProfileId, now: Date, limits: Limits = {}, custom?: CustomProfile): Account {
  return withWeeklyUnit({ bankroll, profile, unit: null, limits, ...(custom ? { custom } : {}) }, now);
}

/** Tonight's staking and settled result, from the user's tracked bets. */
export function tonightFrom(bets: Pick<Bet, "placedAt" | "stake" | "status" | "legs" | "price">[], now: Date): Tonight {
  const day = bettingDay(now);
  let staked = 0;
  let settledProfit = 0;
  for (const b of bets) {
    const placed = new Date(b.placedAt);
    if (Number.isNaN(placed.getTime()) || bettingDay(placed) !== day) continue;
    staked += b.stake;
    settledProfit += betProfit(b as Bet);
  }
  return { staked: cents(staked), settledProfit: cents(settledProfit) };
}

// ---------- limits ----------
export type Stop = "setup" | "cool-off" | "stop-loss" | "profit-lock" | "nightly-cap";
export type LimitState = {
  /** Why no stake can be suggested right now, or null if betting is open. */
  stop: Stop | null;
  message: string;
  /** The most that can be staked in one night, in dollars. */
  nightlyCap: number;
  /** Dollars of tonight's cap not yet staked. */
  remaining: number;
  /** The most that can go on one bet, in dollars. */
  maxBet: number;
};

export function checkLimits(account: Account, tonight: Tonight, now: Date): LimitState {
  const profile = termsOf(account);
  const bankroll = Number.isFinite(account.bankroll) ? Math.max(0, account.bankroll) : 0;
  const own = account.limits.nightlyCap;
  const nightlyCap = cents(Math.min(bankroll * profile.maxNightlyPct, own !== undefined && own >= 0 ? own : Infinity));
  const remaining = cents(Math.max(0, nightlyCap - tonight.staked));
  const maxBet = cents(bankroll * profile.maxBetPct);
  const state = (stop: Stop | null, message: string): LimitState => ({ stop, message, nightlyCap, remaining, maxBet });

  if (bankroll <= 0) return state("setup", "Set a bankroll first.");
  const until = account.limits.coolOffUntil ? new Date(account.limits.coolOffUntil) : null;
  if (until && !Number.isNaN(until.getTime()) && until.getTime() > now.getTime())
    return state("cool-off", `Cool-off is on until ${until.toISOString().slice(0, 16).replace("T", " ")} UTC. No stakes are suggested until then.`);
  const { stopLoss, profitLock } = account.limits;
  if (stopLoss !== undefined && stopLoss > 0 && tonight.settledProfit <= -stopLoss)
    return state("stop-loss", `Your stop-loss of $${fmtDollars(stopLoss)} has been reached tonight. Done for the night.`);
  if (profitLock !== undefined && profitLock > 0 && tonight.settledProfit >= profitLock)
    return state("profit-lock", `Your profit lock of $${fmtDollars(profitLock)} has been reached tonight. The night's profit is locked.`);
  if (remaining <= 0) return state("nightly-cap", `Tonight's cap of $${fmtDollars(nightlyCap)} is fully staked.`);
  return state(null, "");
}

// ---------- sizing ----------
export type StakeRequest = {
  /** The algorithm's chance that the bet wins. Null or missing means the algorithm has not rated it. */
  prob: number | null | undefined;
  /** The price on offer, American odds. */
  price: number | null | undefined;
};

export type Sizing = {
  /** bet: stake this. pass: no stake (no edge at the price, or too small to place). unrated: no number. blocked: a limit is in force. */
  status: "bet" | "pass" | "unrated" | "blocked";
  /** Null when unrated: the engine states no number it did not work out. */
  units: number | null;
  dollars: number | null;
  /** How to show it, for example "1.5u ($15)". */
  label: string;
  /** Expected profit per $1 staked at this price. Null when unrated. */
  edge: number | null;
  /** What held the stake below plain quarter-Kelly, if anything. */
  cappedBy: "max-bet" | "nightly-cap" | null;
  stop: Stop | null;
  reason: string;
};

const fmtDollars = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(2));
const fmtUnits = (u: number) => (Math.round(u * 10) / 10).toFixed(Number.isInteger(Math.round(u * 10) / 10) ? 0 : 1);

/** "1.5u ($15)" */
export function formatStake(units: number, dollars: number): string {
  return `${fmtUnits(units)}u ($${fmtDollars(dollars)})`;
}

const rated = (r: StakeRequest): r is { prob: number; price: number } =>
  typeof r.prob === "number" && Number.isFinite(r.prob) && r.prob > 0 && r.prob < 1 &&
  typeof r.price === "number" && Number.isFinite(r.price) && Math.abs(r.price) >= 100;

/** The stake for one bet, given the account and what has already been staked tonight. */
export function sizeBet(request: StakeRequest, account: Account, tonight: Tonight, now: Date): Sizing {
  if (!rated(request))
    return { status: "unrated", units: null, dollars: null, label: "unrated", edge: null, cappedBy: null, stop: null,
             reason: "The algorithm has not rated this bet, so there is no stake to suggest." };
  const acct = withWeeklyUnit(account, now);
  const limits = checkLimits(acct, tonight, now);
  const edge = expectedValue(request.prob, request.price);
  const none = (status: "pass" | "blocked", reason: string, stop: Stop | null = null): Sizing =>
    ({ status, units: 0, dollars: 0, label: "no bet", edge, cappedBy: null, stop, reason });
  if (limits.stop) return none("blocked", limits.message, limits.stop);
  const unit = acct.unit!.size;
  if (unit <= 0) return none("blocked", "Set a bankroll first.", "setup");

  const kelly = kellyStake(request.prob, request.price, KELLY_FRACTION) * acct.bankroll;
  if (kelly <= 0) return none("pass", "No edge at this price: the algorithm's chance does not beat what the odds imply.");

  let dollars = kelly;
  let cappedBy: Sizing["cappedBy"] = null;
  if (dollars > limits.maxBet) { dollars = limits.maxBet; cappedBy = "max-bet"; }
  if (dollars > limits.remaining) { dollars = limits.remaining; cappedBy = "nightly-cap"; }
  // round down to a tenth of a unit, so no cap is ever exceeded (the small nudge absorbs floating-point error)
  const units = Math.floor(dollars / unit / UNIT_STEP + 1e-9) * UNIT_STEP;
  if (units < UNIT_STEP)
    return none("pass", cappedBy === "nightly-cap" ? "Too little of tonight's cap is left to place this bet." : "The edge is too thin to be worth a stake.");
  const u = Math.round(units * 10) / 10;
  const d = cents(u * unit);
  const why = cappedBy === "max-bet" ? `Held to your profile's maximum of $${fmtDollars(limits.maxBet)} a bet.`
    : cappedBy === "nightly-cap" ? `Held to what is left of tonight's cap ($${fmtDollars(limits.remaining)}).`
    : "Quarter-Kelly on the algorithm's chance.";
  return { status: "bet", units: u, dollars: d, label: formatStake(u, d), edge, cappedBy, stop: null, reason: why };
}

/**
 * Stakes for several bets on the same night, in the order given. Each stake uses up part of tonight's cap,
 * so later bets see less room. Put the bets you care about most first.
 */
export function sizeSlate(requests: StakeRequest[], account: Account, tonight: Tonight, now: Date): Sizing[] {
  let staked = tonight.staked;
  return requests.map((r) => {
    const s = sizeBet(r, account, { ...tonight, staked }, now);
    if (s.status === "bet" && s.dollars) staked = cents(staked + s.dollars);
    return s;
  });
}
