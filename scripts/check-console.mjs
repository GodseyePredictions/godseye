// Loads the console data with every update script applied, exactly as the page does, and fails
// if any game has been left without its SGPs or props tickets.
//
// Usage: node scripts/check-console.mjs
import { readFileSync, existsSync } from "node:fs";
import path from "node:path";
import vm from "node:vm";

const dir = path.resolve(import.meta.dirname, "../public/console");
const ctx = vm.createContext({});
const run = (f) => existsSync(path.join(dir, f)) && vm.runInContext(readFileSync(path.join(dir, f), "utf8").replace(/^const D = /, "var D = "), ctx);
["data.js", "personnel-update.js", "freshness-update.js", "rebuild-update.js", "odds-update.js"].forEach(run);
const D = ctx.D;

const priced = new Set(D.players.map((p) => p.team));
const problems = [];
for (const g of D.games) {
  if (g.started) continue;
  const label = `${g.away} @ ${g.home}`;
  const teams = [g.home, g.away].filter((t) => priced.has(t));
  if (teams.length < 2) {
    console.log(`${label}: skipped, the snapshot has no players for ${[g.home, g.away].filter((t) => !priced.has(t)).join(" and ")}`);
    if (!teams.length) continue;
  }
  const sgp = (D.algo.sgp || []).some((t) => t.game === g.id && t.legs.length >= 2);
  const script = (D.script_sgp || []).some((t) => t.game === g.id && t.ladder.length);
  const props = (D.algo.props || []).filter((t) => String(t.ticket).startsWith(g.id + "|")).length;
  if (!sgp) problems.push(`${label}: no Game SGP`);
  if (!script) problems.push(`${label}: no Script SGP ladder`);
  if (!props) problems.push(`${label}: no props tickets under Algorithm picks`);
}
const ids = new Set(D.players.map((p) => p.id));
const legIds = (t) => (t?.legs || []).map((l) => (typeof l === "string" ? l : l.id));
const all = [...(D.algo.sgp || []), ...(D.algo.props || []), ...(D.script_sgp || []).flatMap((t) => [...t.ladder, t.hybrid1, t.hybrid2])];
for (const t of all) for (const id of legIds(t)) if (!ids.has(id)) problems.push(`a ticket refers to a player who is not in the data: ${id}`);
const atd = Object.values(D.algo.atd_styles || {}).reduce((n, s) => n + s.tickets.length, 0) || (D.algo.atd || []).length;
console.log(`${D.games.length} games, ${(D.algo.sgp || []).length} Game SGPs, ${(D.script_sgp || []).length} Script SGPs, ${(D.algo.props || []).length} props tickets, ${atd} ATD tickets`);
if (!atd) problems.push("no ATD tickets left under Algorithm picks");
if (problems.length) {
  console.error("PROBLEMS:\n  " + problems.join("\n  "));
  process.exit(1);
}
console.log("OK: every priced game has its Game SGP, Script SGP and props tickets.");
