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
