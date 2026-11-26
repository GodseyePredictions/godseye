/**
 * Tonight's NFL slips for one game, built so every one can actually be placed.
 *
 *   node scripts/nfl-today.ts <game_id>      writes model/output/nfl_today_<game_id>.json
 *   (scripts/nfl-slate.sh runs it for a day's games and joins them into model/output/nfl_today.json)
 *
 * Every probability is the NFL algorithm's (public/console/data.js) and every combined chance comes from its
 * correlation engine (src/lib/advisor/joint.ts). This script only chooses among the algorithm's legs:
 *   - a props leg is used only if a sportsbook lists that exact rung (model/output/nfl_listed_rungs.json),
 *     and receptions start at 2+, which is where bet365's ladders start;
 *   - floor legs are 70% or better, at most two legs per player, and a props slip carries no touchdown leg;
 *   - a touchdown leg on a parlay comes only from players the algorithm clears for touchdown parlays
 *     (model/output/nfl_atd_versions.json, written by attd/atd_versions.py);
 *   - within those rules, each slip is the combination with the highest chance of hitting.
 * Prices are never an input to a probability. They confirm a rung exists and show what a play pays.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { nflCatalog, parseConsoleData, type RatedLeg } from "../src/lib/advisor/legs.ts";
import { fairAmerican, jointProbability } from "../src/lib/advisor/joint.ts";
import { validRung } from "../src/lib/slip/suggest.ts";
import { toDecimal } from "../src/lib/odds.ts";

export const NFL_TODAY = {
  floor: 0.7,
  aggressive: [0.55, 0.68] as [number, number],
  receptionsFrom: 2,
  maxLegsPerPlayer: 2,
  sizes: [4, 6, 8],
  lottoFairFrom: 1500,
  ladderBand: [100, 200] as [number, number],
  searchKeep: 600,
  searchSims: 20_000,
  finalSims: 200_000,
};

const root = new URL("..", import.meta.url).pathname;
const read = (f: string) => JSON.parse(readFileSync(root + f, "utf8"));
const src = readFileSync(root + "public/console/data.js", "utf8");
const D = JSON.parse(src.slice(src.indexOf("{"), src.lastIndexOf("}") + 1));
const cat = nflCatalog(parseConsoleData(src));
const GID_ARG = process.argv[2];
if (!GID_ARG) throw new Error("Usage: node scripts/nfl-today.ts <game_id>");
const listed = read(`model/output/nfl_listed_rungs_${GID_ARG}.json`) as { game: string; game_id: string; pulled_at: string; source: string; rungs: { player: string; market: string; k: number | null; prices: Record<string, number> }[] };
const atd = read("model/output/nfl_atd_versions.json") as { games: string[]; held: string[][]; versions: Record<string, { name: string; note: string; tickets: { n: number; p: number; mix: string; legs: { name: string; team: string; pos: string; game: string; p: number; id: string }[] }[] }>; board: { name: string; team: string; pos: string; game: string; p: number; singles: boolean; id?: string }[] };
const GAME = listed.game, GID = listed.game_id;
// touchdown prices for every game on the tonight + Thanksgiving slips (scripts/nfl-listings.ts writes one file per game)
const tdPrices = new Map<string, Record<string, number>>();
for (const f of atd.games.map((g) => { try { return read(`model/output/nfl_listed_rungs_${g}.json`); } catch { return null; } }))
  if (f) for (const r of f.rungs as { player: string; market: string; prices: Record<string, number> }[]) if (r.market === "atd") tdPrices.set(r.player.toLowerCase(), r.prices);
// ---- matchups (scripts/nfl-matchups.py): strong, neutral or weak for each player, from the algorithm's matchup index.
// A defence that is stingy against a player's position caps him at neutral; a soft one lifts a weak tag to neutral.
const MATCH = read(`model/output/nfl_matchups_${GID}.json`) as { players: Record<string, { team: string; pos: string; index: number; tag: string; defence: string }> };
const tagOf = (player: string): "strong" | "neutral" | "weak" => {
  const m = MATCH.players[player]; if (!m) return "neutral";
  // the index, moved one step toward how this defence plays the position: stingy pulls it down, soft lifts it
  const order = ["weak", "neutral", "strong"] as const;
  let i = order.indexOf(m.tag as "weak" | "neutral" | "strong");
  if (m.defence.startsWith("stingy")) i = Math.max(0, i - 1);
  if (m.defence.startsWith("soft")) i = Math.min(2, i + 1);
  return order[i];
};
// the rung each matchup earns: a strong mismatch may step up, a neutral one takes a floor rung, a weak one stays safe
export const RUNG_BY_MATCHUP = { strong: 0.66, neutral: 0.75, weak: 0.8 };
const UNDER = 0.65; // NFL rule: at most one leg under 65% on a ticket
const game = D.games.find((g: { id: string }) => g.id === GID);

const key = (player: string, market: string, k: number | null) => `${player.toLowerCase()}|${market}|${k ?? ""}`;
const prices = new Map(listed.rungs.map((r) => [key(r.player, r.market, r.k), r.prices]));
const priceOf = (l: RatedLeg) => prices.get(key(l.player, l.market, l.market === "atd" ? null : l.threshold));
const best = (p: Record<string, number> | undefined) => (p ? Object.entries(p).sort((a, b) => toDecimal(b[1]) - toDecimal(a[1]))[0] : null);
const LABEL: Record<string, string> = { rec: "receptions", rec_yds: "rec yds", rush_yds: "rush yds", pass_yds: "pass yds", pass_att: "pass attempts", carries: "carries", pass_td: "pass TD" };
const text = (l: RatedLeg) => (l.market === "atd" ? `${l.player} anytime TD` : `${l.player} ${l.threshold}+ ${LABEL[l.market] ?? l.market}`);

// ---- the legs that may go on a props slip
// a back the algorithm flags as displaced (a teammate is back and out-carried him) keeps no rushing leg on a slip
const displaced = new Set(atd.held.filter((h) => /^displaced/.test(h[2])).map((h) => h[0]));
const propsOk = (l: RatedLeg, lo: number, hi: number) =>
  !(displaced.has(l.player) && (l.market === "rush_yds" || l.market === "carries")) &&
  l.game === GAME && l.market !== "atd" && l.side === "over" && !l.singlesOnly && l.prob >= lo && l.prob <= hi && validRung(l.market, l.threshold) &&
  !!priceOf(l) && (l.market !== "rec" || (l.threshold as number) >= NFL_TODAY.receptionsFrom);
const listedOk = cat.legs.filter((l) => propsOk(l, RUNG_BY_MATCHUP.strong, 1));
const floorPool: RatedLeg[] = [];
for (const k of new Set(listedOk.map((l) => `${l.player}|${l.market}`))) {
  const [player] = k.split("|");
  const need = RUNG_BY_MATCHUP[tagOf(player)];
  const rung = listedOk.filter((l) => `${l.player}|${l.market}` === k && l.prob >= need).sort((a, b) => (b.threshold as number) - (a.threshold as number))[0];
  if (rung) floorPool.push(rung);
}
const aggressivePool = cat.legs.filter((l) => propsOk(l, NFL_TODAY.aggressive[0], NFL_TODAY.aggressive[1]));
// ---- touchdown scorers the algorithm clears for parlays, this game
const held = new Map(atd.held.map((h) => [h[0], h[2]]));
const tdLeg = (name: string) => cat.legs.find((l) => l.player === name && l.market === "atd" && l.game !== undefined) as RatedLeg | undefined;
const tdEligible = atd.board.filter((b) => b.game === GID && !b.singles && !held.has(b.name) && b.p >= 0.2).map((b) => tdLeg(b.name)).filter((l): l is RatedLeg => !!l);

type Built = { legs: RatedLeg[]; p: number };
const allowed = (legs: RatedLeg[], c: RatedLeg) =>
  !(c.prob < UNDER && c.market !== "atd" && legs.some((l) => l.prob < UNDER && l.market !== "atd")) &&
  !legs.some((l) => l.player === c.player && l.market === c.market) && legs.filter((l) => l.player === c.player).length < NFL_TODAY.maxLegsPerPlayer;

/** The `count` highest-chance slips of `n` legs from `pool` (plus `fixed` legs), each differing from the ones before it by at least two legs. */
const strongLeg = (l: RatedLeg) => l.market !== "atd" && tagOf(l.player) === "strong";
function topSlips(pool: RatedLeg[], n: number, fixed: RatedLeg[] = [], count = 2, accept: (p: number) => boolean = () => true, lead = true, naiveMax = 1): Built[] {
  const need = n - fixed.length;
  const minStrong = lead ? Math.min(Math.ceil(n / 2), pool.filter(strongLeg).length) : 0;
  const sorted = [...pool].sort((a, b) => b.prob - a.prob);
  const cands: { legs: RatedLeg[]; naive: number }[] = [];
  const base = fixed.reduce((a, l) => a * l.prob, 1);
  const walk = (start: number, legs: RatedLeg[], naive: number) => {
    if (legs.length === need) {
      if (naive <= naiveMax && [...fixed, ...legs].filter(strongLeg).length >= minStrong) cands.push({ legs: [...fixed, ...legs], naive });
      // keep only the best candidates as the search goes, so a big pool cannot run out of memory
      if (cands.length > 50_000) { cands.sort((a, b) => b.naive - a.naive); cands.length = NFL_TODAY.searchKeep; }
      return;
    }
    for (let i = start; i < sorted.length; i++) {
      if (sorted.length - i < need - legs.length) break;
      const c = sorted[i];
      if (!allowed([...fixed, ...legs], c)) continue;
      legs.push(c); walk(i + 1, legs, naive * c.prob); legs.pop();
    }
  };
  walk(0, [], base);
  const rated = cands.sort((a, b) => b.naive - a.naive).slice(0, NFL_TODAY.searchKeep)
    .map((c) => ({ legs: c.legs, p: jointProbability(c.legs, cat.corr, NFL_TODAY.searchSims) as number }))
    .filter((c) => accept(c.p)).sort((a, b) => b.p - a.p);
  const out: Built[] = [];
  for (const c of rated) {
    if (out.every((o) => c.legs.filter((l) => !o.legs.includes(l)).length >= 2)) out.push({ legs: c.legs, p: jointProbability(c.legs, cat.corr, NFL_TODAY.finalSims) as number });
    if (out.length === count) break;
  }
  return out.sort((a, b) => b.p - a.p);
}

type Slip = { title: string; kind: string; pick: boolean; p: number; fair: number; listedMultiplied: number | null; legs: { text: string; p: number; record: string; listed: string; why: string[] }[]; note?: string };
const players = Object.fromEntries((D.players as { name: string; why?: string[]; risk?: string | null; team: string; pos: string }[]).map((p) => [p.name, p]));
const strip = (t: string) => t.replace(/<[^>]+>/g, "").replace(/&amp;/g, "&").replace(/&#39;|&apos;/g, "'");
const whyOf = (l: RatedLeg) => {
  const w = (players[l.player]?.why ?? []).map(strip);
  const role = w.find((x) => /^(Volume|Red-zone role|Goal-line role)/.test(x)), matchup = w.find((x) => /^(vs |[A-Z]{2,3} O-line)/.test(x));
  const m = MATCH.players[l.player];
  const head = m ? `${tagOf(l.player)[0].toUpperCase()}${tagOf(l.player).slice(1)} matchup: ${m.defence}; ${l.prob >= RUNG_BY_MATCHUP.neutral ? (tagOf(l.player) === "strong" ? "the algorithm still rates this rung high" : "floor rung") : "stepped up a rung on the mismatch"}.` : "";
  return [head, role, matchup, l.risk ? `Risk: ${l.risk}` : ""].filter((x): x is string => !!x).map((x) => (x.length > 220 ? x.slice(0, 220).replace(/\s+\S*$/, "") + "…" : x));
};
const toSlip = (title: string, kind: string, b: Built, pick: boolean, note?: string): Slip => ({
  title, kind, pick, p: b.p, fair: fairAmerican(b.p) as number, note,
  // the listed prices of the legs multiplied together: what the books charge leg by leg. A book prices a same-game
  // parlay lower than this. Shown so the slip's price is never mistaken for the algorithm's fair price.
  listedMultiplied: (() => { const d = b.legs.reduce((a, l) => { const bp = best(priceOf(l)); return a * (bp ? toDecimal(bp[1]) : NaN); }, 1); return Number.isFinite(d) ? (d >= 2 ? Math.round((d - 1) * 100) : Math.round(-100 / (d - 1))) : null; })(),
  legs: b.legs.map((l) => { const bp = best(priceOf(l)); return { text: text(l), p: l.prob, record: l.hits != null && l.games ? `cleared in ${l.hits} of ${l.games} games` : "", listed: bp ? `${bp[0] === "draftkings" ? "DraftKings" : "FanDuel"} ${bp[1] > 0 ? "+" : ""}${bp[1]}` : "", why: whyOf(l) }; }),
});

// ---- 1. props SGPs and 2. SGP + one anytime TD, at each size: the algorithm's pick and the next best
const sgps: Slip[] = [], hybrids: Slip[] = [];
for (const n of NFL_TODAY.sizes) {
  topSlips(floorPool, n).forEach((b, i) => sgps.push(toSlip(`${n}-leg SGP`, "sgp", b, i === 0)));
  const options = tdEligible.flatMap((td) => topSlips(floorPool, n, [td], 1)).sort((a, b) => b.p - a.p).slice(0, 2);
  options.forEach((b, i) => hybrids.push(toSlip(`${n}-leg SGP + anytime TD`, "sgp_atd", b, i === 0)));
}
// ---- 3. lotto: the highest-chance slip of aggressive legs whose fair price is +1500 or longer
// lotto pool: listed props legs from 55% up (still at most one under 65%) plus the touchdown scorers cleared for parlays
const lottoProps = new Map<string, RatedLeg>();
// per player and market: the highest listed rung at 65%+ and the highest at 55%+ (a slip may carry one of the latter)
for (const l of cat.legs.filter((x) => propsOk(x, NFL_TODAY.aggressive[0], 1))) for (const tier of [UNDER, NFL_TODAY.aggressive[0]]) {
  if (l.prob < tier) continue;
  const k = `${l.player}|${l.market}|${tier}`; const o = lottoProps.get(k); if (!o || (l.threshold as number) > (o.threshold as number)) lottoProps.set(k, l);
}
const lottoPool = [...new Set([...lottoProps.values()].sort((a, b) => b.prob - a.prob))].slice(0, 22).concat(tdEligible.slice(0, 4));
const lottoCands = [6, 7, 8].flatMap((n) => topSlips(lottoPool, n, [], 10, (p) => (fairAmerican(p) as number) >= NFL_TODAY.lottoFairFrom, false, 1 / 22)).filter((b) => (fairAmerican(b.p) as number) >= NFL_TODAY.lottoFairFrom && (toSlip("", "", b, false).listedMultiplied ?? 0) >= NFL_TODAY.lottoFairFrom).sort((a, b) => b.p - a.p);
const lotto = lottoCands[0] ? toSlip(`Lotto · ${lottoCands[0].legs.length}-leg`, "lotto", lottoCands[0], true, `Higher rungs and touchdown scorers the algorithm rates ${Math.round(NFL_TODAY.aggressive[0] * 100)}% or better, at most one props leg under 65%. A lotto is 1 in 16 or longer.`) : null;

// ---- 4. anytime TD, tonight: singles, and the double the one-player-per-team rule allows
const board = atd.board.filter((b) => b.game === GID).slice(0, 6).map((b) => { const l = tdLeg(b.name); const bp = l ? best(priceOf(l)) : null; return { name: b.name, team: b.team, pos: b.pos, p: b.p, fair: fairAmerican(b.p) as number, flag: b.singles ? "single only this week" : held.has(b.name) ? `held out of parlays: ${held.get(b.name)}` : "", listed: bp ? `${bp[0] === "draftkings" ? "DraftKings" : "FanDuel"} ${bp[1] > 0 ? "+" : ""}${bp[1]}` : "", price: bp ? bp[1] : null, why: l ? whyOf(l) : [] }; });
const byTeam = new Map<string, RatedLeg[]>();
for (const l of tdEligible) byTeam.set(l.team as string, [...(byTeam.get(l.team as string) ?? []), l]);
const teams = [...byTeam.values()];
let dbl: Built | null = null;
if (teams.length >= 2) for (const a of teams[0]) for (const b of teams[1]) { const p = jointProbability([a, b], cat.corr, NFL_TODAY.finalSims) as number; if (!dbl || p > dbl.p) dbl = { legs: [a, b], p }; }

// ---- 5. anytime TD, tonight plus tomorrow: the algorithm's combo slips, then longer ones that add a second scorer per team
const leg = (x: { name: string }) => tdLeg(x.name) as RatedLeg;
const G = Object.fromEntries(D.games.map((g: { id: string }) => [g.id, g]));
const when = (gid: string) => `${G[gid].away} @ ${G[gid].home} · ${String(G[gid].weekday).slice(0, 3)} ${G[gid].kick}`;
const ground = (pos: string) => pos === "RB" || pos === "QB";
type CrossLeg = { text: string; p: number; side: string; who: string; game: string; listed: string; price: number | null };
type Cross = { title: string; mix: string; pick: boolean; p: number; fair: number; listedMultiplied: number | null; legs: CrossLeg[]; note?: string };
const bookName = (b: string) => (b === "draftkings" ? "DraftKings" : "FanDuel");
const crossLeg = (b: { name: string; team: string; pos: string; game: string; p: number }): CrossLeg => {
  const bp = best(tdPrices.get(b.name.toLowerCase()));
  return { text: `${b.name} anytime TD`, p: b.p, side: ground(b.pos) ? "Ground" : "Air", who: `${b.team} ${b.pos}`, game: when(b.game), listed: bp ? `${bookName(bp[0])} ${bp[1] > 0 ? "+" : ""}${bp[1]}` : "", price: bp ? bp[1] : null };
};
const multiplied = (ps: (number | null)[]) => { if (ps.some((x) => x == null)) return null; const d = ps.reduce((a: number, x) => a * toDecimal(x as number), 1); return d >= 2 ? Math.round((d - 1) * 100) : Math.round(-100 / (d - 1)); };
const cross: Cross[] = atd.versions.combo.tickets.map((t) => { const legs = t.legs.map(crossLeg); return { title: `${t.n}-leg ground + air`, mix: t.mix, pick: true, p: t.p, fair: fairAmerican(t.p) as number, listedMultiplied: multiplied(legs.map((l) => l.price)), legs }; });
// eligible scorers in the four games: each team's top back and top two pass-catchers
const elig = atd.board.filter((b) => atd.games.includes(b.game) && !b.singles && !held.has(b.name) && b.p >= 0.2 && tdLeg(b.name) && !["PHI"].includes(held.has(b.name) ? b.team : ""));
const heldTeams = new Set(atd.held.filter((h) => /backup-QB/.test(h[2])).map((h) => h[1]));
const crossPool = elig.filter((b) => !heldTeams.has(b.team) && tdPrices.has(b.name.toLowerCase()));
const perTeam = [...new Set(crossPool.map((b) => b.team))].map((t) => ({ g: crossPool.filter((b) => b.team === t && ground(b.pos))[0], a: crossPool.filter((b) => b.team === t && !ground(b.pos)).slice(0, 2) }));
function extended(n: number, nAir: number): Cross | null {
  // one back at most and one pass-catcher at most per team (two at ten legs); `nAir` pass-catchers in all
  const cands: { ids: typeof crossPool; naive: number }[] = [];
  const walk = (ti: number, picked: typeof crossPool) => {
    if (picked.length === n) { if (picked.filter((b) => !ground(b.pos)).length === nAir) cands.push({ ids: [...picked], naive: picked.reduce((a, b) => a * b.p, 1) }); return; }
    if (ti >= perTeam.length) return;
    const t = perTeam[ti];
    const opts: (typeof crossPool)[] = [[]];
    if (t.g) opts.push([t.g]);
    for (const a of t.a) { opts.push([a]); if (t.g) opts.push([t.g, a]); }
    // ten legs across few teams: a team may also carry its two main pass-catchers
    if (n >= 10 && t.a.length === 2) { opts.push([...t.a]); if (t.g) opts.push([t.g, ...t.a]); }
    for (const o of opts) if (picked.length + o.length <= n) walk(ti + 1, [...picked, ...o]);
  };
  walk(0, []);
  if (!cands.length) return null;
  const top = cands.sort((a, b) => b.naive - a.naive).slice(0, 60).map((c) => ({ ...c, p: jointProbability(c.ids.map(leg), cat.corr, 40_000) as number })).sort((a, b) => b.p - a.p)[0];
  const p = jointProbability(top.ids.map(leg), cat.corr, 400_000) as number;
  const order = [...top.ids].sort((a, b) => atd.games.indexOf(a.game) - atd.games.indexOf(b.game) || b.p - a.p);
  const legs = order.map(crossLeg);
  return { title: `${n}-leg ground + air`, mix: `${n - nAir} ground + ${nAir} air`, pick: true, p, fair: fairAmerican(p) as number, listedMultiplied: multiplied(legs.map((l) => l.price)), legs,
    note: "Longer than the algorithm's one-scorer-per-team rule allows across these games, so some teams carry a back and a pass-catcher. Teammates share touchdowns, and the chance shown accounts for that." };
}
// each size takes the ground/air split the algorithm rates most likely among those the games allow
for (const n of [6, 8, 10]) if (!cross.some((c) => c.legs.length === n)) {
  const x = [Math.floor(n / 3), Math.floor(n / 3) + 1, Math.ceil(n / 2)].map((nAir) => extended(n, nAir)).filter((c): c is Cross => !!c).sort((a, b) => b.p - a.p)[0];
  if (x) cross.push(x);
}

const out = {
  game: GAME, game_id: GID, kickoff: `${game.weekday} ${game.kick}`, day: game.day, venue: game.venue,
  built_from: D.meta.built, made_at: new Date().toISOString(), listings: { source: listed.source, pulled_at: listed.pulled_at },
  script: (D.script_sgp.find((x: { game: string }) => x.game === GID)?.notes ?? []) as string[],
  rules: ["Slips are built around the mismatches: at least half the legs come from strong matchups where the game has them.", "Each leg is set by its matchup: a strong mismatch steps up a rung (66%+), a neutral matchup takes a floor rung (75%+), a weak one stays conservative (80%+).", `Every props leg is a rung a sportsbook lists, at its listed price; receptions start at ${NFL_TODAY.receptionsFrom}+.`, `At most one leg under 65% and at most ${NFL_TODAY.maxLegsPerPlayer} legs per player.`, "Props slips carry no touchdown leg; SGP + anytime TD slips carry exactly one, from a scorer the algorithm clears for parlays.", ...[...displaced].map((n) => `${n} carries no rushing leg: the algorithm flags him as displaced (${atd.held.find((h) => h[0] === n)?.[2].replace(/^displaced: /, "")}).`)],
  sgps, hybrids, lotto,
  atd: { singles: board, double: dbl ? toSlip("Anytime TD double", "atd", dbl, true, "One scorer from each team: teammates share the same touchdowns.") : null, held: atd.held.filter((h) => atd.board.some((b) => b.name === h[0] && b.game === GID)).map((h) => ({ name: h[0], why: h[2] })) },
  cross: { games: atd.games.map(when), slips: cross, held: atd.held.map((h) => ({ name: h[0], team: h[1], why: h[2] })) },
};
writeFileSync(root + `model/output/nfl_today_${GID}.json`, JSON.stringify(out));
const line = (s: { title: string; pick: boolean; p: number; fair: number; legs: { text: string }[] }) => `  ${s.pick ? "*" : " "} ${s.title.padEnd(26)} ${(s.p * 100).toFixed(1).padStart(5)}%  fair ${String(s.fair).padStart(6)}  ${s.legs.map((l) => l.text).join("; ")}`;
console.log(`${GAME}: floor pool ${floorPool.length}, aggressive pool ${aggressivePool.length}, TD-eligible ${tdEligible.map((l) => l.player).join(", ")}`);
for (const s of [...sgps, ...hybrids, ...(lotto ? [lotto] : []), ...(out.atd.double ? [out.atd.double] : [])]) console.log(line(s));
for (const s of cross) console.log(line(s));
