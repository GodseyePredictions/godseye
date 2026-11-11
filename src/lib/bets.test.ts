import { test } from "node:test";
import assert from "node:assert/strict";
import {
  parseSlip,
  summarize,
  betProfit,
  betType,
  groupBy,
  averageClv,
  decimalToAmerican,
  type Bet,
} from "./bets.ts";
import { checkSlip } from "./slip.ts";

const bet = (over: Partial<Bet>): Bet => ({
  id: "x",
  placedAt: "2026-11-01",
  sport: "NFL",
  book: "bet365",
  legs: [{ description: "Bills -3.5", odds: -110 }],
  stake: 110,
  status: "open",
  ...over,
});

test("parses pasted slips, including the unicode minus", () => {
  const legs = parseSlip(
    "Bills -3.5 -110\n\nJosh Allen over 249.5 pass yds −115\nChiefs ML +150\nno odds here",
  );
  assert.equal(legs.length, 3);
  assert.deepEqual(legs[0], { description: "Bills -3.5", odds: -110 });
  assert.equal(legs[1].odds, -115);
  assert.equal(legs[2].description, "Chiefs ML");
});

test("profit and summary", () => {
  assert.equal(Math.round(betProfit(bet({ status: "won" }))), 100);
  assert.equal(betProfit(bet({ status: "lost" })), -110);
  assert.equal(betProfit(bet({ status: "push" })), 0);
  const s = summarize("All", [bet({ status: "won" }), bet({ status: "lost" }), bet({})]);
  assert.equal(s.bets, 3);
  assert.equal(s.staked, 220);
  assert.ok(Math.abs(s.roi! - -10 / 220) < 1e-9);
  assert.equal(summarize("None", [bet({})]).roi, null);
});

test("grouping, bet type and closing line value", () => {
  const two = bet({
    legs: [
      { description: "a", odds: -110 },
      { description: "b", odds: -110 },
    ],
  });
  assert.equal(betType(two), "2-leg parlays");
  assert.equal(groupBy([bet({}), two], betType).length, 2);
  assert.ok(averageClv([bet({ closingOdds: -130 })])! > 0);
  assert.equal(averageClv([bet({})]), null);
  assert.equal(decimalToAmerican(3.5), 250);
  assert.equal(decimalToAmerican(1.5), -200);
});

test("slip check flags same-game legs and heavy favourites", () => {
  const r = checkSlip(
    [
      { description: "Bills -3.5", odds: -110, game: "BUF @ MIA" },
      { description: "Allen o249.5", odds: -115, game: "buf @ mia" },
      { description: "Chiefs ML", odds: -310 },
    ],
    25,
  );
  assert.ok(Math.abs(r.toWin - 93.01) < 0.01);
  assert.ok(r.findings.some((f) => f.title.includes("same game")));
  assert.ok(r.findings.some((f) => f.title === "Leg 3 adds little"));
  assert.equal(checkSlip([], 10).findings.length, 0);
});
