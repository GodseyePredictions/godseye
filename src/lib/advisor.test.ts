import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parseLeg } from "./advisor/parse.ts";
import { matchPlayers, nbaCatalog, nflCatalog, normName, parseConsoleData, type Catalog } from "./advisor/legs.ts";
import { auditLeg, auditSlip } from "./advisor/audit.ts";
import { openAccount } from "./staking.ts";

// ---------- a small made-up slate ----------
const NFL: Catalog = nflCatalog({
  meta: { built: "test build" },
  games: [
    { id: "g1", away: "BUF", home: "KC", started: false },
    { id: "g2", away: "DAL", home: "NYG", started: true },
  ],
  players: [
    { id: "a", name: "Josh Allen", team: "BUF", game: "g1", p: 0.42 },
    { id: "b", name: "Keon Coleman", team: "BUF", game: "g1", p: 0.31, singles: true },
    { id: "c", name: "Travis Kelce", team: "KC", game: "g1", p: 0.38 },
    { id: "d", name: "Josh Jacobs", team: "KC", game: "g1", p: 0.5 },
    { id: "e", name: "Kyren Allen", team: "KC", game: "g1", p: 0.2 },
    { id: "z", name: "Dak Prescott", team: "DAL", game: "g2", p: 0.1 },
  ],
  props: {
    a: { pass_yds: { k: [200, 225, 250], p: [0.86, 0.74, 0.58] }, pass_td: { k: [1, 2], p: [0.9, 0.62] }, rush_yds: { k: [20, 30], p: [0.81, 0.6] } },
    b: { rec_yds: { k: [20, 30, 40], p: [0.88, 0.76, 0.61] }, rec: { k: [2, 3], p: [0.9, 0.72] } },
    c: { rec: { k: [3, 4, 5], p: [0.92, 0.8, 0.63] }, rec_yds: { k: [30, 40], p: [0.84, 0.71] } },
    d: { rush_yds: { k: [40, 50, 60], p: [0.9, 0.79, 0.64] } },
    z: { pass_yds: { k: [200], p: [0.8] } },
  },
});
const NBA: Catalog = nbaCatalog({
  run_at: "test run",
  games: [{
    home: "IND", away: "OKC",
    singles: [
      { name: "Andrew Nembhard", market: "ast", line: 5.5, side: "over", p: 0.8 },
      { name: "Andrew Nembhard", market: "reb", line: 3.5, side: "over", p: 0.78 },
      { name: "Kelly Oubre Jr.", market: "fg3m", line: 2.5, side: "over", p: 0.31 },
      { name: "Pascal Siakam", market: "pts", line: 19.5, side: "over", p: 0.77 },
      { name: "Pascal Siakam", market: "reb", line: 5.5, side: "over", p: 0.76 },
    ],
    tickets: [{ legs: [{ name: "Pascal Siakam", market: "pts", line: 24.5, side: "over", p: 0.41 }] }],
  }, { home: "LAL", away: "BOS", preview: true, singles: [{ name: "Luka Doncic", market: "pts", line: 29.5, side: "over", p: 0.6 }] }],
});

// ---------- reading a leg ----------
test("reads bet365 milestone legs", () => {
  assert.deepEqual(parseLeg("Josh Allen 225+ Passing Yards"), { player: "Josh Allen", market: "pass_yds", threshold: 225, side: "over" });
  assert.deepEqual(parseLeg("Josh Jacobs 50+ Rush Yds"), { player: "Josh Jacobs", market: "rush_yds", threshold: 50, side: "over" });
  assert.deepEqual(parseLeg("Travis Kelce 4+ Receptions"), { player: "Travis Kelce", market: "rec", threshold: 4, side: "over" });
  assert.deepEqual(parseLeg("Keon Coleman 30+ Receiving Yards"), { player: "Keon Coleman", market: "rec_yds", threshold: 30, side: "over" });
  assert.deepEqual(parseLeg("Josh Allen 2+ Passing TDs"), { player: "Josh Allen", market: "pass_td", threshold: 2, side: "over" });
  assert.deepEqual(parseLeg("Andrew Nembhard 6+ Assists"), { player: "Andrew Nembhard", market: "ast", threshold: 6, side: "over" });
  assert.deepEqual(parseLeg("Kelly Oubre Jr. 3+ Threes Made"), { player: "Kelly Oubre Jr.", market: "fg3m", threshold: 3, side: "over" });
  assert.deepEqual(parseLeg("Pascal Siakam 20+ Points"), { player: "Pascal Siakam", market: "pts", threshold: 20, side: "over" });
});

test("an over on a half line is the next milestone", () => {
  assert.equal(parseLeg("Josh Allen Over 224.5 Passing Yards")!.threshold, 225);
  assert.equal(parseLeg("Josh Allen o224.5 pass yds")!.threshold, 225);
  assert.equal(parseLeg("Pascal Siakam Over 19.5 Points")!.threshold, 20);
});

test("reads unders, anytime touchdowns and combined markets", () => {
  assert.deepEqual(parseLeg("Travis Kelce Under 4.5 Receptions"), { player: "Travis Kelce", market: "rec", threshold: 4.5, side: "under" });
  assert.deepEqual(parseLeg("Josh Jacobs Anytime TD"), { player: "Josh Jacobs", market: "atd", threshold: null, side: "over" });
  assert.deepEqual(parseLeg("Josh Jacobs Anytime Touchdown Scorer"), { player: "Josh Jacobs", market: "atd", threshold: null, side: "over" });
  assert.deepEqual(parseLeg("Anytime TD: Josh Jacobs"), { player: "Josh Jacobs", market: "atd", threshold: null, side: "over" });
  assert.equal(parseLeg("Pascal Siakam 30+ Points + Rebounds + Assists")!.market, "pra");
  assert.equal(parseLeg("Pascal Siakam 25+ Pts + Rebs")!.market, "pr");
});

test("reads the market before the number, and odd dashes", () => {
  assert.deepEqual(parseLeg("Josh Allen Passing Yards 225+"), { player: "Josh Allen", market: "pass_yds", threshold: 225, side: "over" });
  assert.deepEqual(parseLeg("Josh Allen — 225+ Passing Yards"), { player: "Josh Allen", market: "pass_yds", threshold: 225, side: "over" });
});

test("returns nothing rather than guess", () => {
  assert.equal(parseLeg("Bills -3.5"), null); // a game line, not a player prop
  assert.equal(parseLeg("Josh Allen Passing Yards"), null); // no number
  assert.equal(parseLeg("225+ Passing Yards"), null); // no player
  assert.equal(parseLeg(""), null);
});

// ---------- names ----------
test("names match across punctuation and suffixes", () => {
  assert.equal(normName("Kelly Oubre Jr."), "kelly oubre");
  assert.equal(normName("Ja'Marr Chase"), "jamarr chase");
  assert.equal(normName("Amon-Ra St. Brown"), "amon ra st brown");
  assert.deepEqual(matchPlayers("kelly oubre", NBA), ["Kelly Oubre Jr."]);
  assert.deepEqual(matchPlayers("T. Kelce", NFL), ["Travis Kelce"]);
  assert.deepEqual(matchPlayers("Kelce", NFL), ["Travis Kelce"]);
});

test("a name that fits two players is ambiguous, not a pick of one", () => {
  assert.deepEqual(matchPlayers("Allen", NFL).sort(), ["Josh Allen", "Kyren Allen"]);
  assert.deepEqual(matchPlayers("J. Allen", NFL), ["Josh Allen"]);
});

// ---------- the catalogues ----------
test("games that have kicked off and preview games are left out", () => {
  assert.equal(NFL.legs.some((l) => l.player === "Dak Prescott"), false);
  assert.equal(NBA.legs.some((l) => l.player === "Luka Doncic"), false);
});

test("an NBA over line becomes its milestone", () => {
  const l = NBA.legs.find((x) => x.player === "Andrew Nembhard" && x.market === "ast")!;
  assert.equal(l.threshold, 6);
  assert.equal(l.prob, 0.8);
});

// ---------- one leg ----------
test("a rated leg carries the algorithm's own number, unchanged", () => {
  const a = auditLeg({ text: "Josh Allen 225+ Passing Yards", odds: -150 }, NFL);
  assert.equal(a.status, "rated");
  assert.equal(a.prob, 0.74);
  assert.ok(Math.abs(a.edge! - (0.74 - 0.6)) < 1e-9);
  assert.equal(auditLeg({ text: "Josh Jacobs Anytime TD" }, NFL).prob, 0.5);
  assert.equal(auditLeg({ text: "Josh Jacobs Anytime TD" }, NFL).edge, null); // no price, no edge
});

test("a milestone the algorithm does not rate is unrated, never interpolated", () => {
  const a = auditLeg({ text: "Josh Allen 210+ Passing Yards" }, NFL);
  assert.equal(a.status, "unrated");
  assert.equal(a.unrated, "rung-not-rated");
  assert.equal(a.prob, null);
  assert.deepEqual(a.ratedRungs, [200, 225, 250]);
});

test("every other reason a leg is unrated", () => {
  assert.equal(auditLeg({ text: "Patrick Mahomes 250+ Passing Yards" }, NFL).unrated, "player-not-found");
  assert.equal(auditLeg({ text: "Dak Prescott 200+ Passing Yards" }, NFL).unrated, "player-not-found"); // his game has started
  assert.equal(auditLeg({ text: "Allen 20+ Rushing Yards" }, NFL).unrated, "ambiguous-player");
  assert.equal(auditLeg({ text: "Travis Kelce 20+ Rushing Yards" }, NFL).unrated, "market-not-rated");
  assert.equal(auditLeg({ text: "Travis Kelce Under 4.5 Receptions" }, NFL).unrated, "market-not-rated");
  assert.equal(auditLeg({ text: "Bills moneyline" }, NFL).unrated, "unreadable");
  for (const t of ["Patrick Mahomes 250+ Passing Yards", "Allen 20+ Rushing Yards", "Bills moneyline"])
    assert.equal(auditLeg({ text: t }, NFL).prob, null);
});

// ---------- a whole slip ----------
test("a parlay's chance is never stated", () => {
  const s = auditSlip([{ text: "Josh Allen 200+ Passing Yards" }, { text: "Travis Kelce 3+ Receptions" }], NFL);
  assert.equal(s.rated, 2);
  assert.equal(s.slipProb, null);
  assert.match(s.slipProbNote, /Not stated/);
});

test("a single's chance is its leg's chance", () => {
  assert.equal(auditSlip([{ text: "Josh Jacobs 40+ Rushing Yards" }], NFL).slipProb, 0.9);
  assert.equal(auditSlip([{ text: "Josh Jacobs 45+ Rushing Yards" }], NFL).slipProb, null);
});

const rulesOf = (texts: string[], c: Catalog) => auditSlip(texts.map((text) => ({ text })), c).rules.map((r) => r.rule);

test("NFL ticket rules", () => {
  assert.deepEqual(rulesOf(["Josh Allen 200+ Passing Yards", "Travis Kelce 3+ Receptions"], NFL), []);
  // one leg under 65% is allowed, two are not
  assert.deepEqual(rulesOf(["Josh Allen 250+ Passing Yards", "Travis Kelce 3+ Receptions"], NFL), ["floor"]);
  assert.deepEqual(rulesOf(["Josh Allen 250+ Passing Yards", "Travis Kelce 5+ Receptions", "Josh Jacobs 40+ Rushing Yards"], NFL), ["floor", "weak-legs"]);
  assert.ok(rulesOf(["Josh Jacobs Anytime TD", "Travis Kelce 3+ Receptions"], NFL).includes("td-with-props"));
  assert.ok(rulesOf(["Keon Coleman 20+ Receiving Yards", "Travis Kelce 3+ Receptions"], NFL).includes("singles-only"));
  assert.ok(rulesOf(["Patrick Mahomes 250+ Passing Yards", "Travis Kelce 3+ Receptions"], NFL).includes("unrated"));
});

test("touchdown legs are not held to the props floor", () => {
  // two anytime-TD legs at 50% and 42%: an anytime-TD ticket, so neither the 70% floor nor the 65% rule applies
  assert.deepEqual(rulesOf(["Josh Jacobs Anytime TD", "Josh Allen Anytime TD"], NFL), []);
});

test("NBA ticket rules are the NBA's own", () => {
  // 77% clears the NFL's 70% floor but is fine in the NBA too (75%); 31% is under it
  assert.deepEqual(rulesOf(["Pascal Siakam 20+ Points", "Andrew Nembhard 6+ Assists"], NBA), []);
  assert.deepEqual(rulesOf(["Kelly Oubre Jr. 3+ Threes Made", "Andrew Nembhard 6+ Assists"], NBA), ["floor"]);
  assert.deepEqual(rulesOf(["Pascal Siakam 6+ Rebounds", "Andrew Nembhard 4+ Rebounds"], NBA), ["rebounds"]);
  // the NFL's "at most one leg under 65%" rule is not applied to an NBA slip
  assert.equal(rulesOf(["Kelly Oubre Jr. 3+ Threes Made", "Pascal Siakam 25+ Points"], NBA).includes("weak-legs"), false);
});

test("a single has no parlay rules", () => {
  assert.deepEqual(rulesOf(["Josh Allen 250+ Passing Yards"], NFL), []);
});

// ---------- stakes come from the staking engine, or not at all ----------
const NOW = new Date("2026-11-25T23:00:00Z");
const opts = { account: openAccount(1000, "balanced", NOW), tonight: { staked: 0, settledProfit: 0 }, now: NOW };

test("a rated single with a price is sized by the engine", () => {
  const s = auditSlip([{ text: "Josh Jacobs 50+ Rushing Yards", odds: -200 }], NFL, opts); // 79% at -200
  assert.equal(s.stake!.status, "bet");
  assert.equal(s.stake!.label, "2u ($20)");
});

test("a parlay or an unrated leg gets no stake number", () => {
  const parlay = auditSlip([{ text: "Josh Allen 200+ Passing Yards" }, { text: "Travis Kelce 3+ Receptions" }], NFL, { ...opts, price: 150 });
  assert.equal(parlay.stake!.status, "unrated");
  assert.equal(parlay.stake!.dollars, null);
  const ghost = auditSlip([{ text: "Josh Allen 210+ Passing Yards", odds: -110 }], NFL, opts);
  assert.equal(ghost.stake!.status, "unrated");
  assert.equal(auditSlip([{ text: "Josh Jacobs 50+ Rushing Yards" }], NFL, opts).stake!.status, "unrated"); // rated, but no price
});

// ---------- the real output files ----------
test("the catalogues build from the algorithms' real output", () => {
  const nfl = nflCatalog(parseConsoleData(readFileSync(new URL("../../public/console/data.js", import.meta.url), "utf8")));
  const nba = nbaCatalog(JSON.parse(readFileSync(new URL("../../model/nba/output/nba_site.json", import.meta.url), "utf8")));
  for (const c of [nfl, nba]) {
    assert.ok(c.built);
    for (const l of c.legs) assert.ok(l.prob >= 0 && l.prob <= 1 && l.player, `${l.player} ${l.market}`);
  }
  assert.ok(nba.legs.length > 0);
  if (nba.legs.length) {
    const l = nba.legs[0];
    const a = auditLeg({ text: `${l.player} ${l.threshold}+ ${{ pts: "Points", reb: "Rebounds", ast: "Assists", fg3m: "Threes Made" }[l.market as "pts"] ?? l.market}` }, nba);
    assert.equal(a.prob, l.prob);
  }
});
