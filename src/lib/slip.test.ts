import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { fairAmerican, gameJoint, jointProbability, normInv } from "./advisor/joint.ts";
import { nbaCatalog, nflCatalog, type Catalog, type RatedLeg } from "./advisor/legs.ts";
import { gradeSlip, type SlipLegInput } from "./slip/grade.ts";
import { recheckSlip, toSavedLeg, type SavedSlip } from "./slip/recheck.ts";
import { ParsedSlipSchema, oddsToAmerican, stakeToDollars, toDraft } from "./slip/schema.ts";
import { suggestChanges, validRung } from "./slip/suggest.ts";
import { draftToInput, gradeSlipTool, parseSlipFromJson, suggestChangesTool, TOOLS } from "./slip/tools.ts";
import { openAccount } from "./staking.ts";

const near = (a: number, b: number, eps: number) => assert.ok(Math.abs(a - b) <= eps, `${a} vs ${b} (±${eps})`);

// ---------- a small made-up slate with measured-looking correlations ----------
const CORR = {
  atd: { OPP: 0.03, "TM:default": -0.04, "TM:RB-WR": -0.08 },
  legs: {
    "TM|pass_yds@QB|rec_yds@WR": 0.45, "TM|pass_yds@QB|rec@WR": 0.35, "TM|pass_yds@QB|rec_yds@TE": 0.3, "TM|pass_yds@QB|rec@TE": 0.25,
    "TM|pass_yds@QB|rush_yds@RB": -0.2, "TM|rec@WR|rush_yds@RB": -0.12, "TM|rec_yds@WR|rush_yds@RB": -0.15,
    "SELF|rec@WR|rec_yds@WR": 0.7, "SELF|rec@TE|rec_yds@TE": 0.7, "OPP|pass_yds@QB|pass_yds@QB": 0.15,
    "OPP|pass_yds@QB|rush_yds@RB": -0.1, _rel: { SELF: 0.28, TM: 0.01, OPP: 0.002 },
  },
};
const slate = (over: Record<string, unknown> = {}) => ({
  meta: { built: "build one" },
  games: [{ id: "g1", away: "BUF", home: "KC", started: false }, { id: "g2", away: "DAL", home: "NYG", started: false }],
  players: [
    { id: "qb1", name: "Josh Allen", team: "BUF", game: "g1", pos: "QB", p: 0.42, inj: null, risk: "mobile QB: rushing TDs come and go" },
    { id: "wr1", name: "Keon Coleman", team: "BUF", game: "g1", pos: "WR", p: 0.31, inj: null },
    { id: "wr2", name: "Khalil Shakir", team: "BUF", game: "g1", pos: "WR", p: 0.28, inj: null },
    { id: "rb1", name: "James Cook", team: "BUF", game: "g1", pos: "RB", p: 0.55, inj: null, riskm: { rush_yds: "big favourite: may run the clock late" } },
    { id: "te1", name: "Travis Kelce", team: "KC", game: "g1", pos: "TE", p: 0.38, inj: null },
    { id: "qb2", name: "Patrick Mahomes", team: "KC", game: "g1", pos: "QB", p: 0.1, inj: null },
    { id: "rb2", name: "Isiah Pacheco", team: "KC", game: "g1", pos: "RB", p: 0.45, inj: null, singles: true },
    { id: "qb3", name: "Dak Prescott", team: "DAL", game: "g2", pos: "QB", p: 0.08, inj: null },
  ],
  props: {
    qb1: { pass_yds: { k: [200, 225, 250, 275], p: [0.88, 0.76, 0.58, 0.4], hits: [8, 7, 5, 3], n: 9 }, pass_td: { k: [1, 2], p: [0.9, 0.62] } },
    wr1: { rec_yds: { k: [20, 30, 40, 50, 60], p: [0.9, 0.82, 0.74, 0.62, 0.5] }, rec: { k: [2, 3, 4], p: [0.9, 0.78, 0.6] } },
    wr2: { rec_yds: { k: [20, 30, 40, 50], p: [0.92, 0.84, 0.76, 0.63] }, rec: { k: [3, 4, 5], p: [0.88, 0.77, 0.59] } },
    rb1: { rush_yds: { k: [40, 50, 60, 70], p: [0.9, 0.8, 0.66, 0.5] }, carries: { k: [10, 15], p: [0.92, 0.74] } },
    te1: { rec: { k: [3, 4, 5], p: [0.92, 0.8, 0.63] }, rec_yds: { k: [30, 40, 50], p: [0.86, 0.75, 0.6] } },
    qb2: { pass_yds: { k: [200, 225, 250], p: [0.9, 0.8, 0.64] } },
    rb2: { rush_yds: { k: [30, 40, 50], p: [0.88, 0.77, 0.6] } },
    qb3: { pass_yds: { k: [200, 225], p: [0.85, 0.72] } },
  },
  corr: CORR,
  ...over,
});
const NFL = nflCatalog(slate());
const leg = (player: string, market: SlipLegInput["market"], threshold: number | null, odds: number | null = null): SlipLegInput =>
  ({ player, market, threshold, side: "over", odds });
const find = (c: Catalog, player: string, market: string, threshold: number | null) =>
  c.legs.find((l) => l.player === player && l.market === market && l.threshold === threshold) as RatedLeg;

// ---------- joint probability against known answers ----------
test("the normal quantile is right at known points", () => {
  near(normInv(0.5), 0, 1e-9);
  near(normInv(0.975), 1.959964, 1e-4);
  near(normInv(0.1), -1.281552, 1e-4);
});

test("unrelated legs multiply", () => {
  const id3 = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
  near(gameJoint([0.8, 0.7, 0.6], id3), 0.8 * 0.7 * 0.6, 0.006);
});

test("two correlated coin-flip legs match the exact formula", () => {
  // for two standard normals with correlation r, P(both below their medians) = 1/4 + asin(r) / (2 pi)
  for (const r of [0.5, 0.25, -0.3, 0.8]) near(gameJoint([0.5, 0.5], [[1, r], [r, 1]]), 0.25 + Math.asin(r) / (2 * Math.PI), 0.006);
});

test("legs that move together cash more often; legs that fight cash less", () => {
  const p = [0.75, 0.7];
  const apart = gameJoint(p, [[1, 0], [0, 1]]);
  assert.ok(gameJoint(p, [[1, 0.5], [0.5, 1]]) > apart + 0.02);
  assert.ok(gameJoint(p, [[1, -0.4], [-0.4, 1]]) < apart - 0.02);
});

test("a slip is never more likely than its weakest leg", () => {
  for (const r of [0, 0.4, 0.9])
    assert.ok(gameJoint([0.9, 0.55, 0.8], [[1, r, r], [r, 1, r], [r, r, 1]]) <= 0.55 + 1e-9);
});

test("the same slip always gets the same number", () => {
  const legs = [find(NFL, "Josh Allen", "pass_yds", 225), find(NFL, "Keon Coleman", "rec_yds", 40), find(NFL, "James Cook", "rush_yds", 50)];
  assert.equal(jointProbability(legs, NFL.corr), jointProbability(legs, NFL.corr));
});

test("games are independent of each other, legs inside a game are not", () => {
  const a = find(NFL, "Josh Allen", "pass_yds", 225), b = find(NFL, "Keon Coleman", "rec_yds", 40), c = find(NFL, "Dak Prescott", "pass_yds", 225);
  const sameGame = jointProbability([a, b], NFL.corr)!;
  assert.ok(sameGame > a.prob * b.prob + 0.02, "QB yards and his receiver's yards rise together");
  near(jointProbability([a, b, c], NFL.corr)!, sameGame * c.prob, 1e-9);
  near(jointProbability([a, c], NFL.corr)!, a.prob * c.prob, 1e-9);
});

test("without correlations a parlay's chance is not stated", () => {
  const nba = nbaCatalog({ run_at: "x", games: [{ home: "IND", away: "OKC", singles: [
    { name: "A One", market: "pts", line: 19.5, side: "over", p: 0.8 }, { name: "B Two", market: "ast", line: 5.5, side: "over", p: 0.78 }] }] });
  assert.equal(jointProbability(nba.legs, nba.corr), null);
  assert.equal(jointProbability([nba.legs[0]], nba.corr), 0.8);
});

test("matches the console's own simulation on a frozen sample of real output", () => {
  // The console showed this 5-leg WAS @ NYG slip at 21.6% (19.2% if the legs were unrelated).
  const real = nflCatalog(JSON.parse(readFileSync(new URL("../../fixtures/algo/nfl-sample.json", import.meta.url), "utf8")));
  const want: [string, string, number | null][] = [
    ["Devin Singletary", "atd", null], ["Isaiah Likely", "rec", 2], ["Devin Singletary", "rec", 1], ["Isaiah Likely", "rec_yds", 20], ["Rachaad White", "rush_yds", 20]];
  const legs = want.map(([p, m, k]) => find(real, p, m, k));
  near(jointProbability(legs, real.corr)!, 0.216, 0.0015);
  near(legs.reduce((a, l) => a * l.prob, 1), 0.192, 0.0015);
});

test("fair odds", () => {
  assert.equal(fairAmerican(0.5), -100);
  assert.equal(fairAmerican(0.25), 300);
  assert.equal(fairAmerican(0.8), -400);
  assert.equal(fairAmerican(0), null);
});

// ---------- grading ----------
test("each leg is graded against its own price", () => {
  const g = gradeSlip([leg("Josh Allen", "pass_yds", 225, -150), leg("Keon Coleman", "rec_yds", 40, -250)], NFL, { totalOdds: 200 });
  near(g.legs[0].implied!, 0.6, 1e-9);
  near(g.legs[0].edge!, 0.76 - 0.6, 1e-9);
  near(g.legs[1].edge!, 0.74 - 250 / 350, 1e-9);
  assert.equal(g.legs[0].match!.hits, 7);
  assert.equal(g.legs[0].match!.games, 9);
});

test("the slip's chance comes from the engine, with fair odds and value at the book's price", () => {
  const g = gradeSlip([leg("Josh Allen", "pass_yds", 225), leg("Keon Coleman", "rec_yds", 40)], NFL, { totalOdds: 110 });
  assert.ok(g.joint! > 0.76 * 0.74);
  assert.equal(g.fairOdds, fairAmerican(g.joint!));
  near(g.value!, g.joint! * 2.1 - 1, 1e-9);
  assert.match(g.jointNote, /correlation engine/);
});

test("unrated legs are labelled and left out of the math", () => {
  const g = gradeSlip([leg("Josh Allen", "pass_yds", 225), leg("Keon Coleman", "rec_yds", 40), leg("Josh Allen", "pass_yds", 210), leg("Nobody Here", "rec", 3)], NFL, { totalOdds: 500 });
  assert.equal(g.rated, 2);
  assert.equal(g.unrated, 2);
  assert.equal(g.legs[2].unrated, "rung-not-rated");
  assert.equal(g.legs[3].unrated, "player-not-found");
  near(g.joint!, gradeSlip([leg("Josh Allen", "pass_yds", 225), leg("Keon Coleman", "rec_yds", 40)], NFL).joint!, 1e-12);
  assert.equal(g.value, null); // the book's price covers legs the algorithm cannot rate
  assert.match(g.jointNote, /2 unrated legs are left out/);
  assert.ok(g.rules.some((r) => r.rule === "unrated"));
});

test("a game line or an unreadable leg is unrated, not an error", () => {
  const g = gradeSlip([{ player: null, market: null, threshold: -3.5, side: null, text: "Bills -3.5" }, leg("James Cook", "rush_yds", 50)], NFL);
  assert.equal(g.legs[0].status, "unrated");
  assert.equal(g.legs[0].unrated, "unreadable");
  assert.equal(g.rated, 1);
});

test("legs that fight the rest of the slip, and the algorithm's own risk note, are flagged", () => {
  const g = gradeSlip([leg("Josh Allen", "pass_yds", 250), leg("Keon Coleman", "rec_yds", 40), leg("James Cook", "rush_yds", 50)], NFL);
  assert.ok(g.legs[2].flags.includes("fights-script")); // a run-heavy script works against the passing legs
  assert.ok(g.legs[2].withRest! < -0.04);
  assert.match(g.legs[2].risk!, /run the clock/);
  assert.ok(g.legs[0].flags.includes("below-floor"));
});

test("injury status is read from the algorithm's data", () => {
  const hurt = nflCatalog(slate({ players: slate().players.map((p) => (p.id === "wr1" ? { ...p, inj: "Out" } : p.id === "te1" ? { ...p, inj: "Questionable" } : p)) }));
  const g = gradeSlip([leg("Keon Coleman", "rec_yds", 40), leg("Travis Kelce", "rec", 4)], hurt);
  assert.deepEqual(g.legs[0].flags.filter((f) => f === "out"), ["out"]);
  assert.ok(g.legs[1].flags.includes("questionable"));
  assert.equal(g.legs[0].injury, "Out");
});

const NOW = new Date("2026-11-25T23:00:00Z");
const money = { account: openAccount(1000, "balanced", NOW), tonight: { staked: 0, settledProfit: 0 }, now: NOW };

test("the stake comes from the bankroll engine, and only for a fully rated slip with a price", () => {
  const full = gradeSlip([leg("Josh Allen", "pass_yds", 225), leg("Keon Coleman", "rec_yds", 40)], NFL, { ...money, totalOdds: 110 });
  assert.equal(full.stake!.status, "bet");
  assert.equal(full.stake!.label, "2u ($20)");
  assert.equal(gradeSlip([leg("Josh Allen", "pass_yds", 225), leg("Nobody Here", "rec", 3)], NFL, { ...money, totalOdds: 110 }).stake!.status, "unrated");
  assert.equal(gradeSlip([leg("Josh Allen", "pass_yds", 225), leg("Keon Coleman", "rec_yds", 40)], NFL, money).stake!.status, "unrated");
});

// ---------- suggestions ----------
test("milestone rules for a rung", () => {
  assert.equal(validRung("rush_yds", 20), true);
  assert.equal(validRung("rush_yds", 15), false); // rushing and receiving ladders start at 20+
  assert.equal(validRung("rec_yds", 10), false);
  assert.equal(validRung("rec_yds", 33), false); // steps of 5
  assert.equal(validRung("pass_yds", 225), true);
  assert.equal(validRung("pass_yds", 212), false);
  assert.equal(validRung("rec", 3), true);
  assert.equal(validRung("atd", null), true);
  assert.equal(validRung("atd", 1), false);
});

test("nothing to change on a clean slip", () => {
  const g = gradeSlip([leg("Josh Allen", "pass_yds", 225), leg("Keon Coleman", "rec_yds", 40)], NFL);
  const s = suggestChanges(g, NFL);
  assert.equal(s.improved, null);
  assert.deepEqual([s.remove.length, s.swap.length, s.add.length], [0, 0, 0]);
});

test("a leg under the floor is swapped to a safer rung on the same player", () => {
  const g = gradeSlip([leg("Josh Allen", "pass_yds", 275), leg("Keon Coleman", "rec_yds", 40)], NFL);
  const s = suggestChanges(g, NFL);
  const sw = s.swap.find((x) => x.index === 0)!;
  assert.equal(sw.kind, "safer-rung");
  assert.equal(sw.to.player, "Josh Allen");
  assert.equal(sw.to.threshold, 225); // the highest rung that clears 70%, not the lowest on the ladder
  assert.ok(sw.to.prob >= 0.7);
  assert.equal(s.improved!.legs.length, 2);
  assert.ok(s.improved!.joint! > g.joint!);
});

test("a touchdown leg in a props slip is removed and replaced to keep the leg count", () => {
  const g = gradeSlip([leg("Josh Allen", "pass_yds", 225), leg("Keon Coleman", "rec_yds", 40), leg("James Cook", "atd", null)], NFL);
  const s = suggestChanges(g, NFL);
  const sw = s.swap.find((x) => x.index === 2)!;
  assert.equal(sw.from.market, "atd");
  assert.equal(sw.kind, "stronger-leg");
  assert.equal(s.improved!.legs.length, 3);
  assert.ok(s.improved!.legs.every((l) => l.market !== "atd"));
  assert.equal(s.improved!.rules.some((r) => r.rule === "td-with-props"), false);
});

test("every suggested leg passes the ticket rules", () => {
  const slips = [
    [leg("Josh Allen", "pass_yds", 275), leg("Keon Coleman", "rec_yds", 60), leg("James Cook", "atd", null), leg("Travis Kelce", "rec", 5)],
    [leg("Josh Allen", "pass_yds", 250), leg("Khalil Shakir", "rec", 5), leg("Isiah Pacheco", "rush_yds", 40)],
  ];
  for (const slip of slips) {
    const s = suggestChanges(gradeSlip(slip, NFL), NFL, { legCount: 5 });
    for (const l of [...s.swap.map((x) => x.to), ...s.add.map((x) => x.leg)]) {
      assert.ok(l.prob >= 0.7, `${l.player} ${l.market} ${l.threshold} is ${l.prob}`);
      assert.ok(validRung(l.market, l.threshold));
      assert.notEqual(l.market, "atd");
      assert.notEqual(l.singlesOnly, true);
    }
    const out = s.improved!.legs;
    assert.ok(out.filter((l) => l.prob < 0.65).length <= 1);
    assert.equal(new Set(out.map((l) => `${l.player}|${l.market}`)).size, out.length, "no player has two legs in one market");
    assert.ok(out.length <= 5);
  }
});

test("a singles-only player comes off a parlay", () => {
  const s = suggestChanges(gradeSlip([leg("Isiah Pacheco", "rush_yds", 40), leg("Travis Kelce", "rec", 4)], NFL), NFL);
  assert.equal(s.improved!.legs.some((l) => l.player === "Isiah Pacheco"), false);
});

test("a negative-value leg is removed", () => {
  // Kelce 4+ receptions at 80% priced at -900 (90% implied)
  const g = gradeSlip([leg("Travis Kelce", "rec", 4, -900), leg("Josh Allen", "pass_yds", 225, -150), leg("Khalil Shakir", "rec_yds", 30, -250)], NFL);
  assert.ok(g.legs[0].flags.includes("negative-value"));
  const s = suggestChanges(g, NFL, { legCount: 2 });
  assert.ok(s.remove.some((r) => r.index === 0 && r.kind === "negative-value"));
  assert.equal(s.improved!.legs.length, 2);
});

test("legs are added only when the user asks for more, and each add is a floor rung", () => {
  const g = gradeSlip([leg("Josh Allen", "pass_yds", 225), leg("Keon Coleman", "rec_yds", 40)], NFL);
  assert.equal(suggestChanges(g, NFL).add.length, 0);
  const s = suggestChanges(g, NFL, { legCount: 4 });
  assert.equal(s.add.length, 2);
  assert.equal(s.improved!.legs.length, 4);
  assert.ok(s.improved!.joint! < g.joint!); // more legs always hit less often, and the note says so
  assert.match(s.improved!.note, /not like for like/);
});

test("the leg count the user asks for is respected", () => {
  const g = gradeSlip([leg("Josh Allen", "pass_yds", 225), leg("Keon Coleman", "rec_yds", 40), leg("James Cook", "atd", null)], NFL);
  assert.equal(suggestChanges(g, NFL, { legCount: 2 }).improved!.legs.length, 2);
  assert.equal(suggestChanges(g, NFL, { legCount: 3 }).improved!.legs.length, 3);
});

test("NBA: rule removals and safer rungs only, and no improved chance is stated", () => {
  const nba = nbaCatalog({ run_at: "x", games: [{ home: "IND", away: "OKC", singles: [
    { name: "A One", market: "pts", line: 24.5, side: "over", p: 0.5 }, { name: "A One", market: "pts", line: 19.5, side: "over", p: 0.8 },
    { name: "B Two", market: "ast", line: 5.5, side: "over", p: 0.78 }] }] });
  const g = gradeSlip([leg("A One", "pts", 25), leg("B Two", "ast", 6)], nba);
  assert.equal(g.joint, null);
  const s = suggestChanges(g, nba, { legCount: 3 });
  assert.equal(s.swap[0].to.threshold, 20);
  assert.equal(s.add.length, 0);
  assert.equal(s.improved!.joint, null);
  assert.ok(s.notes.some((n) => /correlations/.test(n)));
});

// ---------- re-check ----------
const savedFrom = (c: Catalog, picks: [string, string, number | null][]): SavedSlip =>
  ({ id: "s1", savedAt: "2026-11-25T12:00:00Z", sport: "NFL", built: c.built, legs: picks.map(([p, m, k]) => toSavedLeg(find(c, p, m, k))) });
const SAVED = savedFrom(NFL, [["Josh Allen", "pass_yds", 225], ["Keon Coleman", "rec_yds", 40], ["Travis Kelce", "rec", 4]]);
const rebuilt = (change: (p: ReturnType<typeof slate>["players"][number]) => unknown, more: Record<string, unknown> = {}) =>
  nflCatalog(slate({ meta: { built: "build two" }, players: slate().players.map(change).filter(Boolean), ...more }));

test("no alert while the algorithm's data is unchanged", () => {
  assert.deepEqual(recheckSlip(SAVED, NFL), []);
  assert.deepEqual(recheckSlip(SAVED, rebuilt((p) => p)), []);
});

test("your leg is out, here is a swap", () => {
  const a = recheckSlip(SAVED, rebuilt((p) => (p.id === "wr1" ? { ...p, inj: "Out" } : p)));
  assert.equal(a.length, 1);
  assert.equal(a[0].kind, "out");
  assert.equal(a[0].legIndex, 1);
  assert.equal(a[0].title, "Your leg is out");
  assert.ok(a[0].swap && a[0].swap.player !== "Keon Coleman" && a[0].swap.prob >= 0.7 && a[0].swap.market !== "atd");
});

test("a player pulled from the slate raises an alert", () => {
  const a = recheckSlip(SAVED, rebuilt((p) => (p.id === "te1" ? null : p)));
  assert.equal(a[0].kind, "pulled");
  assert.equal(a[0].legIndex, 2);
  assert.ok(a[0].swap);
});

test("a leg that has dropped under the floor raises an alert", () => {
  const weaker = { ...slate().props, qb1: { ...slate().props.qb1, pass_yds: { k: [200, 225, 250, 275], p: [0.8, 0.62, 0.45, 0.3] } } };
  const a = recheckSlip(SAVED, rebuilt((p) => p, { props: weaker }));
  assert.equal(a[0].kind, "weaker");
  assert.equal(a[0].swap!.threshold, 200);
});

test("a game that has kicked off is left alone", () => {
  const c = nflCatalog(slate({ meta: { built: "build two" }, games: [{ id: "g1", away: "BUF", home: "KC", started: true }, { id: "g2", away: "DAL", home: "NYG", started: false }] }));
  assert.deepEqual(recheckSlip(SAVED, c), []);
});

// ---------- the screenshot schema ----------
const rawLeg = (o: Record<string, unknown> = {}) => ({
  sport: "NFL", game: "BUF @ KC", player: "Josh Allen", market: "pass_yds", market_text: "Passing Yards", threshold: 225, side: "milestone",
  odds_text: "-150", unreadable: [], ...o,
});
const rawSlip = (legs: unknown[], o: Record<string, unknown> = {}) => ({
  is_bet_slip: true, book: "bet365", bet_type: "same_game_parlay", legs, total_odds_text: "+450", stake_text: "$25.00", unreadable: [], ...o,
});

test("prices are converted in code, whatever format the book prints", () => {
  assert.equal(oddsToAmerican("-150"), -150);
  assert.equal(oddsToAmerican("+140"), 140);
  assert.equal(oddsToAmerican("−110"), -110);
  assert.equal(oddsToAmerican("2.50"), 150);
  assert.equal(oddsToAmerican("1.50"), -200);
  assert.equal(oddsToAmerican("5/2"), 250);
  assert.equal(oddsToAmerican("1/4"), -400);
  assert.equal(oddsToAmerican("EVS"), 100);
  assert.equal(oddsToAmerican("abc"), null);
  assert.equal(oddsToAmerican(null), null);
  assert.equal(stakeToDollars("$25.00"), 25);
  assert.equal(stakeToDollars("Stake: 1,250.50"), 1250.5);
  assert.equal(stakeToDollars(null), null);
});

test("a well-read slip becomes a draft with nothing to fix", () => {
  const d = toDraft(rawSlip([rawLeg(), rawLeg({ player: "Keon Coleman", market: "rec_yds", market_text: "Receiving Yards", threshold: 39.5, side: "over", odds_text: "1.40" })]));
  assert.deepEqual(d.problems, []);
  assert.equal(d.totalOdds, 450);
  assert.equal(d.stake, 25);
  assert.deepEqual(d.legs[0].needs, []);
  assert.equal(d.legs[1].threshold, 40); // over 39.5 is the 40+ milestone
  assert.equal(d.legs[1].odds, -250);
});

test("anything unreadable is flagged for the user, not guessed", () => {
  const d = toDraft(rawSlip([
    rawLeg({ player: null, unreadable: ["player"] }),
    rawLeg({ threshold: null, unreadable: ["threshold"] }),
    rawLeg({ market: null, market_text: "Pa... Ya...", unreadable: ["market"] }),
    rawLeg({ odds_text: "??" }),
    rawLeg({ player: null, market: "other", market_text: "Spread -3.5", threshold: -3.5, side: null }),
  ], { total_odds_text: "n/a", unreadable: ["stake is cut off"] }));
  assert.deepEqual(d.legs[0].needs, ["player"]);
  assert.deepEqual(d.legs[1].needs, ["number"]);
  assert.deepEqual(d.legs[2].needs, ["market"]);
  assert.deepEqual(d.legs[3].needs, ["price"]);
  assert.deepEqual(d.legs[4].needs, []); // a game line is a valid leg; it will be graded as unrated
  assert.equal(d.totalOdds, null);
  assert.equal(d.problems.length, 2);
});

test("an image that is not a slip, or JSON that breaks the schema, is refused", () => {
  assert.match(toDraft(rawSlip([], { is_bet_slip: false })).problems[0], /does not look like a bet slip/);
  assert.throws(() => toDraft({ legs: "none" }));
  assert.throws(() => toDraft(rawSlip([rawLeg({ market: "passing_yards" })]))); // not one of the known markets
  assert.throws(() => toDraft(rawSlip([{ player: "Josh Allen" }])));
});

// ---------- fixtures: every sample screenshot has an expected reading that passes the schema ----------
const FIXTURES = fileURLToPath(new URL("../../fixtures/slips/", import.meta.url));
test("every fixture's expected JSON matches the schema and grades without error", () => {
  const files = readdirSync(FIXTURES).filter((f) => f.endsWith(".expected.json"));
  assert.ok(files.length >= 3, "expected at least three fixtures");
  const real = nflCatalog(JSON.parse(readFileSync(new URL("../../fixtures/algo/nfl-sample.json", import.meta.url), "utf8")));
  for (const f of files) {
    const raw = JSON.parse(readFileSync(FIXTURES + f, "utf8"));
    assert.ok(ParsedSlipSchema.safeParse(raw).success, f);
    assert.ok(readdirSync(FIXTURES).includes(f.replace(".expected.json", ".png")), `${f} has no screenshot`);
    const draft = toDraft(raw);
    const g = gradeSlip(draftToInput(draft), real, { totalOdds: draft.totalOdds });
    assert.equal(g.legs.length, draft.legs.length, f);
  }
});

// ---------- the tools the chat agent calls ----------
test("the three tools are defined with strict schemas", () => {
  assert.deepEqual(TOOLS.map((t) => t.name), ["parse_slip", "grade_slip", "suggest_changes"]);
  for (const t of TOOLS) {
    assert.equal(t.input_schema.type, "object");
    assert.equal(t.input_schema.additionalProperties, false);
    assert.ok(t.description.length > 40);
  }
});

test("the tools chain: parsed JSON, then grade, then suggestions", () => {
  const draft = parseSlipFromJson(rawSlip([rawLeg({ threshold: 275 }), rawLeg({ player: "Keon Coleman", market: "rec_yds", market_text: "Receiving Yards", threshold: 40, odds_text: null })]));
  const legs = draft.legs.map((l) => ({ player: l.player, market: l.market === "other" ? null : l.market, threshold: l.threshold, side: l.side, odds: l.odds }));
  const g = gradeSlipTool({ sport: "NFL", legs, total_odds: draft.totalOdds }, { NFL });
  assert.equal(g.rated, 2);
  assert.equal(g.legs[0].prob, 0.4);
  const s = suggestChangesTool({ sport: "NFL", legs, total_odds: draft.totalOdds, leg_count: null, book: "bet365" }, { NFL });
  assert.equal(s.swap[0].to.threshold, 225);
  assert.throws(() => gradeSlipTool({ sport: "NBA", legs, total_odds: null }, { NFL }), /NBA/);
});

// ================= NBA: the combined chance from the algorithm's audit data =================
type AuditFile = {
  run_at: string;
  games: { id: string; home: string; away: string; ladder: { player_id: string; name: string; market: string; line: number; side: string; p: number }[]; corr: Record<string, number> }[];
  checks: { legs: { player_id: string; market: string; line: number; side: string }[]; counted: number; independent: number }[];
};
const AUDIT = JSON.parse(readFileSync(new URL("../../fixtures/algo/nba-audit-sample.json", import.meta.url), "utf8")) as AuditFile;
const NBA_SITE = { run_at: AUDIT.run_at, games: [{ home: "HOM", away: "AWY", singles: [], tickets: [] }] };
const NBA_FULL = nbaCatalog(NBA_SITE, AUDIT);
const nbaLeg = (id: string, market: string, k: number, side = "over") =>
  NBA_FULL.legs.find((l) => l.playerId === id && l.market === market && l.threshold === k && l.side === side)!;

test("NBA: with the audit data every rated rung is in the catalogue, and only from the same run", () => {
  assert.equal(NBA_FULL.legs.length, AUDIT.games[0].ladder.length);
  assert.ok(NBA_FULL.corr && "pairs" in NBA_FULL.corr);
  assert.ok(NBA_FULL.legs.every((l) => l.playerId && l.gameId === "g1" && l.team));
  // an over on 6.5 is the 7+ milestone; an under keeps its line
  assert.equal(nbaLeg("h1", "ast", 7).prob, AUDIT.games[0].ladder.find((l) => l.player_id === "h1" && l.market === "ast" && l.line === 6.5)!.p);
  assert.ok(nbaLeg("h2", "pts", 21.5, "under"));
  // audit data from another run, or for a game not on tonight's slate, is not used
  assert.equal(nbaCatalog({ ...NBA_SITE, run_at: "another run" }, AUDIT).corr, undefined);
  assert.equal(nbaCatalog({ run_at: AUDIT.run_at, games: [{ home: "XXX", away: "YYY", singles: [], tickets: [] }] }, AUDIT).legs.length, 0);
  assert.equal(nbaCatalog({ run_at: AUDIT.run_at, games: [{ home: "HOM", away: "AWY", preview: true }] }, AUDIT).legs.length, 0);
  assert.equal(nbaCatalog(NBA_SITE, { run_at: AUDIT.run_at, games: [] }).corr, undefined);
});

test("NBA: the combined chance matches what the algorithm's simulations counted", () => {
  let total = 0, totalNaive = 0;
  for (const c of AUDIT.checks) {
    const legs = c.legs.map((l) => nbaLeg(l.player_id, l.market, l.side === "over" ? Math.floor(l.line) + 1 : l.line, l.side));
    assert.ok(legs.every(Boolean));
    const p = jointProbability(legs, NBA_FULL.corr)!;
    near(p, c.counted, 0.02);
    total += Math.abs(p - c.counted);
    totalNaive += Math.abs(c.independent - c.counted);
  }
  const mean = total / AUDIT.checks.length;
  assert.ok(mean < 0.006, `mean error ${mean}`);
  assert.ok(mean < (totalNaive / AUDIT.checks.length) / 5, "far closer than multiplying the legs");
});

test("NBA: linked legs move the chance the right way, and an under turns the link round", () => {
  const guardAst = nbaLeg("h1", "ast", 7), centrePts = nbaLeg("h2", "pts", 16), homeReb = nbaLeg("h2", "reb", 10), awayReb = nbaLeg("a2", "reb", 9);
  assert.ok(jointProbability([guardAst, centrePts], NBA_FULL.corr)! > guardAst.prob * centrePts.prob + 0.01);
  assert.ok(jointProbability([homeReb, awayReb], NBA_FULL.corr)! < homeReb.prob * awayReb.prob - 0.005);
  const under = nbaLeg("h2", "pts", 21.5, "under");
  assert.ok(jointProbability([guardAst, under], NBA_FULL.corr)! < guardAst.prob * under.prob);
  // two rungs of one market on one player: close to the harder rung alone
  const lo = nbaLeg("h1", "pts", 18), hi = nbaLeg("h1", "pts", 26);
  near(jointProbability([lo, hi], NBA_FULL.corr)!, hi.prob, 0.03);
  // a leg whose player is not in the audit data cannot be combined
  assert.equal(jointProbability([guardAst, { ...centrePts, playerId: undefined }], NBA_FULL.corr), null);
});

test("NBA: a user's slip is graded with a combined chance and suggestions follow the NBA ticket rules", () => {
  const name = (id: string) => AUDIT.games[0].ladder.find((l) => l.player_id === id)!.name;
  const L = (id: string, market: string, k: number): SlipLegInput => ({ player: name(id), market: market as SlipLegInput["market"], threshold: k, side: "over", text: `${name(id)} ${k}+ ${market}` });
  const slip = [L("h1", "ast", 7), L("h2", "pts", 12), L("a1", "pts", 28), L("a2", "reb", 9)];
  const g = gradeSlip(slip, NBA_FULL, { totalOdds: 600 });
  assert.equal(g.unrated, 0);
  assert.ok(g.joint !== null && g.joint > 0 && g.joint < 1);
  near(g.joint!, jointProbability(slip.map((l) => nbaLeg(AUDIT.games[0].ladder.find((x) => x.name === l.player)!.player_id, l.market!, l.threshold!)), NBA_FULL.corr)!, 1e-12);
  assert.ok(g.rules.some((r) => r.rule === "floor"));

  // legs under the floor move down to a safer rung on the same player; the user's own choices are kept
  const s = suggestChanges(g, NBA_FULL, { legCount: 4 });
  assert.ok(s.improved, "it proposes a better version");
  assert.ok(s.improved!.legs.every((l) => l.prob >= 0.75), "every leg clears the 75% floor");
  assert.deepEqual(s.improved!.legs.map((l) => l.player), slip.map((l) => l.player));
  assert.ok(s.improved!.joint! > g.joint!);
  for (const x of s.swap) assert.ok(NBA_FULL.legs.includes(x.to));

  // legs the algorithm adds to reach four: floor rungs, the four props markets, no rebound leg, four different players
  const two = [L("h1", "ast", 5), L("h2", "pts", 12)];
  const four = suggestChanges(gradeSlip(two, NBA_FULL), NBA_FULL, { legCount: 4 });
  assert.equal(four.add.length, 2);
  const out = four.improved!.legs;
  assert.ok(out.every((l) => l.prob >= 0.75 && ["pts", "reb", "ast", "fg3m"].includes(l.market)));
  assert.equal(out.filter((l) => l.market === "reb").length, 0, "no rebound leg added to a 4-leg slip");
  assert.equal(new Set(out.map((l) => l.player)).size, 4, "a 4-leg slip uses four different players");
  for (const x of four.add) assert.ok(NBA_FULL.legs.includes(x.leg), "an added leg is a rung the algorithm rated tonight");

  // a 6-leg request may carry one rebound leg, never two
  const six = suggestChanges(gradeSlip(two, NBA_FULL), NBA_FULL, { legCount: 6 });
  assert.equal(six.improved!.legs.length, 6);
  assert.ok((six.improved?.legs ?? []).filter((l) => l.market === "reb").length <= 1);

  // a leg the algorithm has no rung for stays unrated
  const u = gradeSlip([L("h1", "ast", 7), { player: name("h3"), market: "ast", threshold: 3, side: "over", text: "x" }], NBA_FULL);
  assert.equal(u.unrated, 1);
  assert.match(u.legs[1].note ?? "", /no assists rung|unrated/i);
});
