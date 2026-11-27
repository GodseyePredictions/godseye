/**
 * Anytime-TD-only slips across a day's NFL games, for the site's "Anytime TD" tab.
 *
 *   node scripts/nfl-atd-slips.ts            writes model/output/nfl_atd_slips.json
 *
 * Reads the day's games and parlay holds from model/output/nfl_atd_versions.json (scripts/nfl-atd-versions.py), each
 * game's matchups (model/output/nfl_matchups_<game>.json, scripts/nfl-matchups.py) and listed prices
 * (model/output/nfl_listed_rungs_<game>.json). Every chance is the NFL algorithm's (public/console/data.js); combined
 * chances come from its correlation engine (src/lib/advisor/joint.ts).
 *
 * Who may go on a slip:
 *   - ground (owner, 26 November): a back's matchup must clear, i.e. not weak once the run defence is checked; a quarterback
 *     goes on only when the defence he faces is not stingy against the run;
 *   - air (receivers and tight ends): only when the matchup clears, i.e. the player's matchup is not weak once the
 *     defence is checked (a defence stingy against his position pulls the tag down a step, a soft one lifts it);
 *   - a book must list the player's anytime TD, at 20% or better by the algorithm, and not held or singles-only.
 * Several scorers from one game or one team may share a slip (owner, 26 November): per team at most one back, the
 * quarterback and three pass-catchers; teammates share touchdowns and the chance accounts for that.
 * Prices never choose a leg. They show what each leg pays.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { nflCatalog, parseConsoleData, type RatedLeg } from "../src/lib/advisor/legs.ts";
import { fairAmerican, jointProbability } from "../src/lib/advisor/joint.ts";
import { toDecimal } from "../src/lib/odds.ts";

export const NFL_ATD = { minChance: 0.2, sizes: [2, 3, 4, 5, 6, 8, 10, 12], lotto: [12, 16, 18, 20], lottoKeep: 1500, keep: 400, rate: 60, searchSims: 40_000, finalSims: 400_000 };

const root = new URL("..", import.meta.url).pathname;
const read = (f: string) => JSON.parse(readFileSync(root + f, "utf8"));
const src = readFileSync(root + "public/console/data.js", "utf8");
const D = JSON.parse(src.slice(src.indexOf("{"), src.lastIndexOf("}") + 1));
const cat = nflCatalog(parseConsoleData(src));
const atd = read("model/output/nfl_atd_versions.json") as { games: string[]; held: string[][] };
const G = Object.fromEntries(D.games.map((g: { id: string }) => [g.id, g]));
const when = (gid: string) => `${G[gid].away} @ ${G[gid].home} · ${String(G[gid].weekday).slice(0, 3)} ${G[gid].kick}`;

// ---- prices and matchups for every game of the day
const prices = new Map<string, Record<string, number>>();
const match = new Map<string, { tag: string; defence: string; index: number; opp?: string; weather_step?: number }>();
const runD = new Map<string, string>();
let pulled = "", source = "";
for (const g of atd.games) {
  const L = read(`model/output/nfl_listed_rungs_${g}.json`);
  pulled = pulled && pulled < L.pulled_at ? pulled : L.pulled_at; source = L.source;
  for (const r of L.rungs) if (r.market === "atd") prices.set(r.player.toLowerCase(), r.prices);
  const M = read(`model/output/nfl_matchups_${g}.json`);
  for (const [name, m] of Object.entries(M.players as Record<string, { tag: string; defence: string; index: number; opp: string }>)) match.set(name, m);
  for (const [t, d] of Object.entries(M.defences as Record<string, { run: string }>)) runD.set(t, d.run);
}
const order = ["weak", "neutral", "strong"] as const;
const tagOf = (name: string) => {
  const m = match.get(name); if (!m) return "neutral";
  let i = order.indexOf(m.tag as (typeof order)[number]);
  if (m.defence.startsWith("stingy")) i = Math.max(0, i - 1);
  if (m.defence.startsWith("soft")) i = Math.min(2, i + 1);
  i = Math.max(0, Math.min(2, i + (m.weather_step ?? 0))); // weather step (scripts/nfl-matchups.py)
  return order[i];
};
const best = (p: Record<string, number> | undefined) => (p ? Object.entries(p).sort((a, b) => toDecimal(b[1]) - toDecimal(a[1]))[0] : null);
const book = (b: string) => (b === "draftkings" ? "DraftKings" : "FanDuel");

// ---- the pool
const ground = (pos: string) => pos === "RB" || pos === "QB";
/** Why a scorer's matchup does not clear, or "" when it does. A back or pass-catcher clears when his matchup is not weak once the defence is checked; a quarterback when the run defence he faces is not stingy. */
const blocked = (name: string, pos: string) => {
  const m = match.get(name), tag = tagOf(name);
  if (pos === "QB") { const d = m?.opp ? runD.get(m.opp) ?? "" : ""; return d.startsWith("stingy") ? `ground matchup does not clear: ${d}` : ""; }
  if (pos === "RB") return tag === "weak" ? `ground matchup does not clear: weak, ${m?.defence ?? ""}` : "";
  return tag === "weak" ? `air matchup does not clear: weak, ${m?.defence ?? ""}` : "";
};
const held = new Map(atd.held.map((h) => [h[0], h[2]]));
const heldTeams = new Set(atd.held.filter((h) => /backup-QB/.test(h[2])).map((h) => h[1]));
type P = { name: string; team: string; pos: string; game: string; p: number; leg: RatedLeg; tag: string };
const tdLeg = (name: string) => cat.legs.find((l) => l.player === name && l.market === "atd") as RatedLeg | undefined;
const considered = (D.players as { name: string; team: string; pos: string; game: string; p: number; singles: boolean }[]).filter((x) => atd.games.includes(x.game) && x.p >= NFL_ATD.minChance);
const left: { name: string; team: string; why: string }[] = [];
const pool: P[] = [];
for (const x of considered) {
  const leg = tdLeg(x.name), tag = tagOf(x.name), m = match.get(x.name);
  const why = x.singles ? "singles only this week" : held.has(x.name) ? `held out of parlays: ${held.get(x.name)}` : heldTeams.has(x.team) ? "team held out of touchdown parlays (backup-QB offence)"
    : !prices.has(x.name.toLowerCase()) ? "no book lists his anytime TD" : !leg ? "not in the algorithm's catalogue"
    : blocked(x.name, x.pos);
  if (why) { left.push({ name: x.name, team: x.team, why }); continue; }
  pool.push({ name: x.name, team: x.team, pos: x.pos, game: x.game, p: x.p, leg: leg as RatedLeg, tag });
}

// ---- search: team by team, keeping the best partial slips of each size by the product of chances
const teams = [...new Set(pool.map((x) => x.team))];
function options(team: string, oneEach: boolean, n: number, from: P[] = pool): P[][] {
  const ps = from.filter((x) => x.team === team).sort((a, b) => b.p - a.p);
  const out: P[][] = [[]];
  if (oneEach) return out.concat(ps.map((x) => [x]));
  const rb = ps.filter((x) => x.pos === "RB").slice(0, 2), qb = ps.filter((x) => x.pos === "QB").slice(0, 1), air = ps.filter((x) => !ground(x.pos)).slice(0, 4);
  // two pass-catchers per team, three at twelve legs
  const airSets: P[][] = [[]];
  for (let mask = 1; mask < 1 << air.length; mask++) { const set = air.filter((_, i) => mask & (1 << i)); if (set.length <= 3) airSets.push(set); }
  for (const r of [[], ...rb.map((x) => [x])]) for (const q of [[], ...qb.map((x) => [x])]) for (const a of airSets) { const s = [...r, ...q, ...a]; if (s.length) out.push(s); }
  return out;
}
type C = { legs: P[]; naive: number };
function search(n: number, from: P[] = pool, keep = NFL_ATD.keep): C[] {
  // several scorers from one game or team may share a slip (owner, 26 November); the correlation engine prices that in
  const oneEach = false;
  let states: C[] = [{ legs: [], naive: 1 }];
  for (const t of [...new Set(from.map((x) => x.team))]) {
    const next: C[] = [];
    for (const s of states) for (const o of options(t, oneEach, n, from)) if (s.legs.length + o.length <= n) next.push({ legs: [...s.legs, ...o], naive: o.reduce((a, x) => a * x.p, s.naive) });
    // keep the best states at each size
    const bySize = new Map<number, C[]>();
    for (const c of next) bySize.set(c.legs.length, [...(bySize.get(c.legs.length) ?? []), c]);
    states = [...bySize.values()].flatMap((cs) => cs.sort((a, b) => b.naive - a.naive).slice(0, keep));
  }
  return states.filter((c) => c.legs.length === n).sort((a, b) => b.naive - a.naive).slice(0, NFL_ATD.rate);
}
const mixed = (c: C) => c.legs.some((x) => ground(x.pos)) && c.legs.some((x) => !ground(x.pos));
const multiplied = (ps: (number | null)[]) => { if (ps.some((x) => x == null)) return null; const d = ps.reduce((a: number, x) => a * toDecimal(x as number), 1); return d >= 2 ? Math.round((d - 1) * 100) : Math.round(-100 / (d - 1)); };
const NAME: Record<number, string> = { 2: "double", 3: "triple" };
function build(n: number, from: P[], label: (n: number) => string, extra: Record<string, unknown> = {}, minStrong = 0) {
  const rated = search(n, from, minStrong ? NFL_ATD.lottoKeep : NFL_ATD.keep).filter((c) => c.legs.filter((x) => x.tag === "strong").length >= minStrong).slice(0, NFL_ATD.rate).map((c) => ({ ...c, p: jointProbability(c.legs.map((x) => x.leg), cat.corr, NFL_ATD.searchSims) as number })).sort((a, b) => b.p - a.p);
  if (!rated.length) return [];
  // the pick is the highest chance; up to five legs, a second option carries the best ground + air mix
  const chosen = [rated[0]];
  if (n <= 5 && !minStrong) { const s = rated.slice(1).find((c) => mixed(rated[0]) || mixed(c)); if (s) chosen.push(s); }
  return chosen.map((c, i) => {
    const p = jointProbability(c.legs.map((x) => x.leg), cat.corr, NFL_ATD.finalSims) as number;
    const legs = [...c.legs].sort((a, b) => atd.games.indexOf(a.game) - atd.games.indexOf(b.game) || b.p - a.p).map((x) => {
      const bp = best(prices.get(x.name.toLowerCase()));
      return { text: `${x.name} anytime TD`, p: x.p, side: ground(x.pos) ? "Ground" : "Air", who: `${x.team} ${x.pos}`, game: when(x.game), listed: bp ? `${book(bp[0])} ${bp[1] > 0 ? "+" : ""}${bp[1]}` : "", price: bp ? bp[1] : null,
        matchup: x.pos === "QB" ? `ground matchup clears: ${runD.get(match.get(x.name)?.opp ?? "") ?? ""}` : `${tagOf(x.name)} ${ground(x.pos) ? "ground" : "air"} matchup: ${match.get(x.name)?.defence ?? ""}` };
    });
    const nAir = c.legs.filter((x) => !ground(x.pos)).length;
    const shared = new Set(c.legs.map((x) => x.team)).size < c.legs.length;
    return { title: label(n), size: n, ...extra, mix: `${n - nAir} ground + ${nAir} air`, pick: i === 0, p, fair: fairAmerican(p) as number,
      listedMultiplied: multiplied(legs.map((l) => l.price)), legs,
      note: shared ? "Carries more than one scorer from a team. Teammates share touchdowns, and the chance shown accounts for that." : undefined };
  });
}
const slips = NFL_ATD.sizes.flatMap((n) => build(n, pool, (k) => (NAME[k] ? `Anytime TD ${NAME[k]}` : `${k}-leg anytime TD`)));
// ---- lotto touchdown slips across the slate: built around the mismatches, at least half the legs strong matchups
const lotto = NFL_ATD.lotto.flatMap((n) => build(n, pool, (k) => `Lotto · ${k}-leg anytime TD`, { lotto: true }, Math.ceil(n / 2)));
// ---- each game's own touchdown slips: several scorers from one game
const perGame = atd.games.flatMap((g) => { const from = pool.filter((x) => x.game === g); const label = `${G[g].away} @ ${G[g].home}`;
  return from.length >= 3 ? [3, 4].filter((n) => n <= from.length).flatMap((n) => build(n, from, (k) => `${label}: ${k}-leg TD`, { game_id: g })) : []; });

const out = { made_at: new Date().toISOString(), games: atd.games.map(when), listings: { source, pulled_at: pulled },
  rules: ["Ground: a back goes on only when his matchup clears (not weak once the run defence is checked); a quarterback only when the defence he faces is not stingy against the run.",
    "Air (receivers and tight ends): only when the matchup clears, i.e. not weak once the defence is checked. A defence stingy against his position pulls a player down a step; a soft one lifts him.",
    "Several scorers from one game or one team may share a slip; the chance shown accounts for teammates sharing touchdowns.",
    "Weather: outdoors in rain, snow or wind of 15 mph or more, backs move up a step and the passing game down a step.", "Every leg is an anytime TD a book lists, at its listed price."],
  perGame, lotto, pool: pool.map((x) => ({ name: x.name, team: x.team, pos: x.pos, p: x.p, side: ground(x.pos) ? "Ground" : "Air" })), left, slips };
writeFileSync(root + "model/output/nfl_atd_slips.json", JSON.stringify(out));
console.log(`pool ${pool.length}: ${pool.map((x) => `${x.name} (${ground(x.pos) ? "G" : "A"} ${Math.round(x.p * 100)})`).join(", ")}`);
for (const s of [...slips, ...lotto, ...perGame]) console.log(`  ${s.pick ? "*" : " "} ${s.title.padEnd(22)} ${(s.p * 100).toFixed(2).padStart(6)}%  books ${s.listedMultiplied}  ${s.mix}  ${s.legs.map((l) => l.text.replace(" anytime TD", "")).join(", ")}`);
