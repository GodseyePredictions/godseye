/**
 * Ladder (rollover) arithmetic: the whole stake, winnings included, goes on the next play.
 *
 * Nothing here picks a play or rates one. It answers three questions about a ladder from numbers it is
 * given: what the stake becomes after each win, how many wins in a row a target needs at a given price,
 * and what the chance is of winning every rung when the rungs are in different games (independent).
 */
import { toDecimal } from "./odds.ts";

const cents = (x: number) => Math.round(x * 100) / 100;

/** The balance after each winning rung, starting from `start`, at each rung's American price. */
export function ladderBalances(start: number, prices: number[]): number[] {
  const out: number[] = [];
  let balance = start;
  for (const p of prices) {
    balance = cents(balance * toDecimal(p));
    out.push(balance);
  }
  return out;
}

/** How many wins in a row, each at this American price, turn `start` into at least `goal`. */
export function rungsNeeded(start: number, goal: number, price: number): number {
  if (!(start > 0) || !(goal > start)) return 0;
  const d = toDecimal(price);
  if (!(d > 1)) return Infinity;
  return Math.ceil(Math.log(goal / start) / Math.log(d) - 1e-9);
}

/** The chance of winning every rung, for rungs in different games. Legs inside one game are never multiplied. */
export function chanceOfAll(chances: number[]): number {
  return chances.reduce((a, p) => a * p, 1);
}

/**
 * The chance of reaching `goal` from `start` when every rung is one play with this chance at this price.
 * At a fair price this is start / goal whatever the price: only a price better than fair improves it.
 */
export function ladderChance(start: number, goal: number, price: number, chance: number): { rungs: number; chance: number } {
  const rungs = rungsNeeded(start, goal, price);
  return { rungs, chance: Number.isFinite(rungs) ? chance ** rungs : 0 };
}

// ---------- a ladder with cash-outs ----------
export type CashOutRules = {
  /** After winning this rung, the starting stake is taken out for good. Null: never. */
  stakeBackAfterRung: number | null;
  /** From this rung on, this share of each win's balance is banked and the rest rolls. */
  bankFromRung: number;
  bankShare: number;
};
export type LadderRung = {
  rung: number;
  /** What goes on this rung. */
  stake: number;
  /** What it returns if it wins. */
  returns: number;
  /** Taken out after this rung wins. */
  cashOut: number;
  /** Everything taken out so far, this rung included. */
  banked: number;
  /** What rolls onto the next rung. */
  rolls: number;
  /** Banked plus what is still riding. */
  total: number;
};

/**
 * The rungs of a cash-out ladder at one planning price, up to the rung where banked money plus the
 * balance still riding reaches the goal. Every rung is assumed to win: this is the plan, not a forecast.
 */
export function cashOutLadder(start: number, goal: number, price: number, rules: CashOutRules, maxRungs = 60): LadderRung[] {
  const d = toDecimal(price);
  const out: LadderRung[] = [];
  if (!(start > 0) || !(d > 1) || !(rules.bankShare >= 0 && rules.bankShare < 1)) return out;
  let stake = start, banked = 0;
  for (let rung = 1; rung <= maxRungs; rung++) {
    const returns = cents(stake * d);
    if (banked + returns >= goal) {
      // the goal is reached: everything comes off
      out.push({ rung, stake, returns, cashOut: returns, banked: cents(banked + returns), rolls: 0, total: cents(banked + returns) });
      return out;
    }
    let cashOut = 0;
    if (rules.stakeBackAfterRung === rung) cashOut += Math.min(start, returns);
    if (rung >= rules.bankFromRung) cashOut += (returns - cashOut) * rules.bankShare;
    cashOut = cents(cashOut);
    banked = cents(banked + cashOut);
    const rolls = cents(returns - cashOut);
    out.push({ rung, stake, returns, cashOut, banked, rolls, total: cents(banked + rolls) });
    stake = rolls;
  }
  return out;
}

/**
 * The first rung played as two equal slips in different games, each with this chance at this price:
 * the chance both win, exactly one wins, and neither wins, and the balance in each case.
 */
export function splitStart(start: number, price: number, chance: number) {
  const half = start / 2, win = cents(half * toDecimal(price));
  return {
    both: { chance: chance * chance, balance: cents(2 * win) },
    one: { chance: 2 * chance * (1 - chance), balance: win },
    none: { chance: (1 - chance) * (1 - chance), balance: 0 },
  };
}
