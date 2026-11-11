import { test } from "node:test";
import assert from "node:assert/strict";
import {
  toDecimal, impliedProb, fairProbs, hold, parlayDecimal, profit,
  expectedValue, kellyStake, closingLineValue,
} from "./odds.ts";

const near = (a: number, b: number, eps = 1e-3) => assert.ok(Math.abs(a - b) < eps, `${a} vs ${b}`);

test("converts American to decimal", () => {
  near(toDecimal(-110), 1.9091);
  near(toDecimal(250), 3.5);
  assert.throws(() => toDecimal(0));
});

test("implied probability", () => {
  near(impliedProb(-110), 0.5238);
  near(impliedProb(100), 0.5);
});

test("fair probabilities sum to 1 and remove the margin", () => {
  const [a, b] = fairProbs([-110, -110]);
  near(a, 0.5); near(b, 0.5);
  near(hold([-110, -110]), 0.0455);
  const fav = fairProbs([-310, 250]);
  near(fav[0] + fav[1], 1);
  near(fav[0], 0.7258);
});

test("parlay price and profit", () => {
  const d = parlayDecimal([-110, -115, -310]);
  near(d, 4.7206);
  near(profit(25, d), 93.01, 0.01);
});

test("expected value and Kelly", () => {
  near(expectedValue(0.5238, -110), 0, 1e-3);
  assert.ok(expectedValue(0.5, -110) < 0);
  assert.equal(kellyStake(0.5, -110), 0);
  near(kellyStake(0.55, -110, 1), 0.055);
});

test("closing line value sign", () => {
  assert.ok(closingLineValue(-105, -120) > 0);
  assert.ok(closingLineValue(-120, -105) < 0);
});
