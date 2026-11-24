import { test } from "node:test";
import assert from "node:assert/strict";
import {
  PROFILES, bettingDay, checkLimits, formatStake, openAccount, sizeBet, sizeSlate, stakingWeek, tonightFrom,
  unitFor, withWeeklyUnit, type Account, type Tonight,
} from "./staking.ts";
import { kellyStake } from "./odds.ts";

const near = (a: number, b: number, eps = 1e-6) => assert.ok(Math.abs(a - b) < eps, `${a} vs ${b}`);
const WED = new Date("2026-11-25T23:00:00Z"); // a Wednesday evening
const QUIET: Tonight = { staked: 0, settledProfit: 0 };
const acct = (bankroll = 1000, profile: Account["profile"] = "balanced", limits = {}) => openAccount(bankroll, profile, WED, limits);

// ---------- units ----------
test("a unit is 1% of bankroll", () => {
  assert.equal(unitFor(1000), 10);
  assert.equal(unitFor(250), 2.5);
  assert.equal(unitFor(-5), 0);
  assert.equal(acct(1000).unit!.size, 10);
});

test("the staking week starts on Tuesday at the day's turnover", () => {
  assert.equal(stakingWeek(WED), "2026-11-24");
  assert.equal(stakingWeek(new Date("2026-11-24T10:00:00Z")), "2026-11-24"); // Tuesday, just turned over
  assert.equal(stakingWeek(new Date("2026-11-24T09:59:00Z")), "2026-11-17"); // still Monday night's games
  assert.equal(stakingWeek(new Date("2026-11-30T22:00:00Z")), "2026-11-24"); // the following Monday
  assert.equal(stakingWeek(new Date("2026-12-01T12:00:00Z")), "2026-12-01");
});

test("late-night games belong to the evening they started", () => {
  assert.equal(bettingDay(new Date("2026-11-26T04:30:00Z")), "2026-11-25"); // 11:30pm ET Wednesday
  assert.equal(bettingDay(new Date("2026-11-26T10:00:00Z")), "2026-11-26");
});

test("the unit does not move after a loss or a win inside the week", () => {
  const a = acct(1000);
  const afterLoss = withWeeklyUnit({ ...a, bankroll: 820 }, new Date("2026-11-28T20:00:00Z"));
  assert.equal(afterLoss.unit!.size, 10);
  const afterWin = withWeeklyUnit({ ...a, bankroll: 1400 }, new Date("2026-11-30T20:00:00Z"));
  assert.equal(afterWin.unit!.size, 10);
});

test("the unit is recalculated when a new week starts", () => {
  const a = { ...acct(1000), bankroll: 820 };
  const next = withWeeklyUnit(a, new Date("2026-12-01T15:00:00Z"));
  assert.equal(next.unit!.size, 8.2);
  assert.equal(next.unit!.weekOf, "2026-12-01");
});

// ---------- sizing ----------
test("quarter-Kelly on the algorithm's chance", () => {
  // 55% at +100: full Kelly 10%, quarter 2.5% of $1000 = $25, but balanced caps a bet at 2% = $20
  const s = sizeBet({ prob: 0.55, price: 100 }, acct(1000, "aggressive"), QUIET, WED);
  assert.equal(s.status, "bet");
  assert.equal(s.dollars, 25);
  assert.equal(s.units, 2.5);
  assert.equal(s.label, "2.5u ($25)");
  assert.equal(s.cappedBy, null);
  near(s.edge!, 0.1);
});

test("never more than quarter-Kelly, the per-bet cap, or tonight's room", () => {
  for (const profile of ["conservative", "balanced", "aggressive"] as const)
    for (const [prob, price] of [[0.55, 100], [0.8, -200], [0.3, 400], [0.62, -110], [0.9, -500]] as const)
      for (const staked of [0, 20, 49]) {
        const a = acct(1000, profile);
        const s = sizeBet({ prob, price }, a, { staked, settledProfit: 0 }, WED);
        const d = s.dollars ?? 0;
        assert.ok(d <= kellyStake(prob, price) * 1000 + 1e-9, "over quarter-Kelly");
        assert.ok(d <= 1000 * PROFILES[profile].maxBetPct + 1e-9, "over the per-bet cap");
        assert.ok(d + staked <= Math.max(staked, 1000 * PROFILES[profile].maxNightlyPct) + 1e-9, "over the nightly cap");
      }
});

test("the profile's maximum per bet holds the stake down", () => {
  const s = sizeBet({ prob: 0.55, price: 100 }, acct(1000, "balanced"), QUIET, WED);
  assert.equal(s.dollars, 20);
  assert.equal(s.label, "2u ($20)");
  assert.equal(s.cappedBy, "max-bet");
  assert.equal(sizeBet({ prob: 0.55, price: 100 }, acct(1000, "conservative"), QUIET, WED).dollars, 10);
});

test("stakes round down to a tenth of a unit", () => {
  // 53% at +100: quarter-Kelly 1.5% = $15 exactly; 52.3% gives $11.50 -> 1.1u ($11)
  assert.equal(sizeBet({ prob: 0.53, price: 100 }, acct(), QUIET, WED).label, "1.5u ($15)");
  const s = sizeBet({ prob: 0.523, price: 100 }, acct(), QUIET, WED);
  assert.equal(s.units, 1.1);
  assert.equal(s.dollars, 11);
});

test("no edge means no bet", () => {
  const s = sizeBet({ prob: 0.5, price: -110 }, acct(), QUIET, WED);
  assert.equal(s.status, "pass");
  assert.equal(s.dollars, 0);
  assert.ok(s.edge! < 0);
});

test("an edge too thin for a tenth of a unit is a pass", () => {
  const s = sizeBet({ prob: 0.5005, price: 100 }, acct(), QUIET, WED);
  assert.equal(s.status, "pass");
  assert.equal(s.units, 0);
});

test("unrated means unrated: no number is stated", () => {
  for (const req of [{ prob: null, price: -110 }, { prob: undefined, price: 150 }, { prob: 0.6, price: null },
                     { prob: Number.NaN, price: -110 }, { prob: 1.2, price: -110 }, { prob: 0.6, price: 50 }]) {
    const s = sizeBet(req, acct(), QUIET, WED);
    assert.equal(s.status, "unrated");
    assert.equal(s.units, null);
    assert.equal(s.dollars, null);
    assert.equal(s.edge, null);
    assert.equal(s.label, "unrated");
  }
});

test("stakes use the week's unit even after the bankroll has moved", () => {
  const a = { ...acct(1000, "aggressive"), bankroll: 800 };
  const s = sizeBet({ prob: 0.55, price: 100 }, a, QUIET, new Date("2026-11-27T23:00:00Z"));
  assert.equal(s.dollars, 20); // quarter-Kelly on the $800 now in the account
  assert.equal(s.units, 2); // shown in the unit fixed at the start of the week ($10)
});

// ---------- nightly exposure ----------
test("tonight's cap shrinks the stake, then stops it", () => {
  const a = acct(1000, "balanced"); // $50 a night
  const part = sizeBet({ prob: 0.55, price: 100 }, a, { staked: 38, settledProfit: 0 }, WED);
  assert.equal(part.dollars, 12);
  assert.equal(part.cappedBy, "nightly-cap");
  const full = sizeBet({ prob: 0.55, price: 100 }, a, { staked: 50, settledProfit: 0 }, WED);
  assert.equal(full.status, "blocked");
  assert.equal(full.stop, "nightly-cap");
  assert.equal(full.dollars, 0);
});

test("a slate never adds up to more than the nightly cap", () => {
  const a = acct(1000, "balanced");
  const out = sizeSlate(Array.from({ length: 6 }, () => ({ prob: 0.55, price: 100 })), a, QUIET, WED);
  assert.deepEqual(out.map((s) => s.dollars), [20, 20, 10, 0, 0, 0]);
  assert.equal(out.reduce((t, s) => t + (s.dollars ?? 0), 0), 50);
  assert.equal(out[3].status, "blocked");
});

test("an unrated bet in a slate uses none of the cap", () => {
  const out = sizeSlate([{ prob: null, price: 100 }, { prob: 0.55, price: 100 }], acct(), QUIET, WED);
  assert.equal(out[0].status, "unrated");
  assert.equal(out[1].dollars, 20);
});

test("the user's own nightly cap wins when it is lower, and cannot raise the profile's", () => {
  assert.equal(checkLimits(acct(1000, "balanced", { nightlyCap: 30 }), QUIET, WED).nightlyCap, 30);
  assert.equal(checkLimits(acct(1000, "balanced", { nightlyCap: 500 }), QUIET, WED).nightlyCap, 50);
  assert.equal(sizeBet({ prob: 0.55, price: 100 }, acct(1000, "balanced", { nightlyCap: 15 }), QUIET, WED).dollars, 15);
});

// ---------- the user's limits ----------
test("stop-loss ends the night", () => {
  const a = acct(1000, "balanced", { stopLoss: 40 });
  assert.equal(sizeBet({ prob: 0.55, price: 100 }, a, { staked: 20, settledProfit: -39.99 }, WED).status, "bet");
  const s = sizeBet({ prob: 0.55, price: 100 }, a, { staked: 20, settledProfit: -40 }, WED);
  assert.equal(s.status, "blocked");
  assert.equal(s.stop, "stop-loss");
  assert.equal(s.dollars, 0);
});

test("profit lock ends the night", () => {
  const a = acct(1000, "balanced", { profitLock: 60 });
  const s = sizeBet({ prob: 0.55, price: 100 }, a, { staked: 20, settledProfit: 75 }, WED);
  assert.equal(s.stop, "profit-lock");
  assert.equal(s.dollars, 0);
});

test("cool-off blocks every stake until it ends", () => {
  const a = acct(1000, "balanced", { coolOffUntil: "2026-11-27T00:00:00Z" });
  assert.equal(sizeBet({ prob: 0.55, price: 100 }, a, QUIET, WED).stop, "cool-off");
  assert.equal(sizeBet({ prob: 0.55, price: 100 }, a, QUIET, new Date("2026-11-27T00:01:00Z")).status, "bet");
});

test("no bankroll, no stake", () => {
  const s = sizeBet({ prob: 0.55, price: 100 }, acct(0), QUIET, WED);
  assert.equal(s.status, "blocked");
  assert.equal(s.stop, "setup");
});

// ---------- tonight, from tracked bets ----------
test("tonight counts only this betting day's bets", () => {
  const leg = [{ description: "x", odds: 100 }];
  const t = tonightFrom([
    { placedAt: "2026-11-25T22:00:00Z", stake: 20, status: "lost", legs: leg },
    { placedAt: "2026-11-26T03:00:00Z", stake: 10, status: "won", legs: leg }, // after midnight UTC, same night
    { placedAt: "2026-11-25T23:30:00Z", stake: 15, status: "open", legs: leg },
    { placedAt: "2026-11-24T23:00:00Z", stake: 99, status: "lost", legs: leg }, // last night
    { placedAt: "not a date", stake: 99, status: "lost", legs: leg },
  ], WED);
  assert.equal(t.staked, 45);
  assert.equal(t.settledProfit, -10);
});

// ---------- display ----------
test("stakes read in units and dollars", () => {
  assert.equal(formatStake(1.5, 15), "1.5u ($15)");
  assert.equal(formatStake(2, 20), "2u ($20)");
  assert.equal(formatStake(0.5, 1.25), "0.5u ($1.25)");
});
