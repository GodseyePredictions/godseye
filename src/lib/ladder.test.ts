import { test } from "node:test";
import assert from "node:assert/strict";
import { chanceOfAll, ladderBalances, ladderChance, rungsNeeded } from "./ladder.ts";

const near = (a: number, b: number, eps: number) => assert.ok(Math.abs(a - b) <= eps, `${a} vs ${b}`);

test("each win rolls the whole balance onto the next price", () => {
  assert.deepEqual(ladderBalances(100, [100, 100, 100]), [200, 400, 800]);
  assert.deepEqual(ladderBalances(100, [-200, 150]), [150, 375]);
  assert.deepEqual(ladderBalances(100, []), []);
});

test("wins in a row needed to reach a target", () => {
  assert.equal(rungsNeeded(100, 50_000, 100), 9); // 2^9 = 512
  assert.equal(rungsNeeded(100, 50_000, -200), 16); // 1.5^16 = 657
  assert.equal(rungsNeeded(100, 50_000, 200), 6); // 3^6 = 729
  assert.equal(rungsNeeded(100, 800, 100), 3, "an exact target counts");
  assert.equal(rungsNeeded(100, 100, 100), 0);
  assert.equal(rungsNeeded(100, 50, 100), 0);
});

test("the chance of every rung is the product only across different games", () => {
  near(chanceOfAll([0.8, 0.7, 0.6]), 0.336, 1e-12);
  assert.equal(chanceOfAll([]), 1);
});

test("at fair prices a ladder's chance is about start over goal, whatever the price", () => {
  // even money, a true 50% play: 9 rungs, 0.5^9
  near(ladderChance(100, 50_000, 100, 0.5).chance, 0.5 ** 9, 1e-12);
  // a true 2-in-3 play at its fair price of -200: 16 rungs
  const fav = ladderChance(100, 50_000, -200, 2 / 3);
  assert.equal(fav.rungs, 16);
  near(fav.chance, (2 / 3) ** 16, 1e-12);
  // both land close to 100 / 50,000 = 0.2%, a little under because the last rung overshoots
  for (const c of [ladderChance(100, 50_000, 100, 0.5).chance, fav.chance]) assert.ok(c < 0.002 && c > 0.001);
  // an edge is the only thing that lifts it: the same -200 price with a true 72% play
  assert.ok(ladderChance(100, 50_000, -200, 0.72).chance > 2 * fav.chance);
});

test("a cash-out ladder banks on schedule and stops when banked plus riding reaches the goal", async () => {
  const { cashOutLadder } = await import("./ladder.ts");
  // no cash-outs: the plain ladder, 9 rungs at even money
  const plain = cashOutLadder(100, 50_000, 100, { stakeBackAfterRung: null, bankFromRung: 99, bankShare: 0 });
  assert.equal(plain.length, 9);
  assert.deepEqual(plain.map((r) => r.returns), [200, 400, 800, 1600, 3200, 6400, 12800, 25600, 51200]);
  assert.equal(plain[8].total, 51200);
  assert.equal(plain[8].rolls, 0, "at the goal everything comes off");

  const r = cashOutLadder(100, 50_000, 100, { stakeBackAfterRung: 3, bankFromRung: 5, bankShare: 0.25 });
  assert.deepEqual([r[2].returns, r[2].cashOut, r[2].rolls], [800, 100, 700], "the stake comes back after rung 3");
  assert.deepEqual([r[3].stake, r[3].returns, r[3].cashOut], [700, 1400, 0]);
  assert.deepEqual([r[4].returns, r[4].cashOut, r[4].rolls, r[4].banked], [2800, 700, 2100, 800], "a quarter is banked from rung 5");
  for (const x of r) {
    assert.equal(x.total, Math.round((x.banked + x.rolls) * 100) / 100);
    assert.ok(x.cashOut >= 0 && x.rolls >= 0);
  }
  const last = r[r.length - 1];
  assert.ok(last.total >= 50_000 && r[r.length - 2].total < 50_000);
  assert.ok(r.length > plain.length, "banking along the way costs extra rungs");
  // money banked is never put back at risk
  for (let i = 1; i < r.length; i++) assert.ok(r[i].banked >= r[i - 1].banked);
  assert.deepEqual(cashOutLadder(0, 50_000, 100, { stakeBackAfterRung: null, bankFromRung: 1, bankShare: 0.2 }), []);
});

test("a split start: two half-stake slips in different games", async () => {
  const { splitStart } = await import("./ladder.ts");
  const s = splitStart(100, 100, 0.5);
  assert.deepEqual([s.both.balance, s.one.balance, s.none.balance], [200, 100, 0]);
  near(s.both.chance + s.one.chance + s.none.chance, 1, 1e-12);
  near(s.one.chance, 0.5, 1e-12);
  assert.equal(splitStart(100, 150, 0.45).one.balance, 125);
});
