/**
 * Pull the player-prop rungs the sportsbooks list for one NFL game, with their prices, from The Odds API.
 *
 *   npm run nfl:listings -- 2026_12_GB_LA
 *
 * The key travels in the x-api-key header. In the cloud environment the network proxy adds it from the saved
 * credential; elsewhere set ODDS_API_KEY. Node only goes through that proxy with NODE_USE_ENV_PROXY=1, which the
 * npm script sets; without it the request skips the proxy and the feed answers 401.
 *
 * Writes model/output/nfl_listed_rungs.json. These prices are only used to confirm a rung is listed and to show
 * what a leg pays. They are never an input to a probability (CLAUDE.md, "Odds never make a pick").
 */
import { readFileSync, writeFileSync } from "node:fs";

const API = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl";
const BOOKS = ["draftkings", "fanduel"];
const MARKETS: Record<string, string> = {
  player_pass_yds_alternate: "pass_yds", player_receptions_alternate: "rec", player_reception_yds_alternate: "rec_yds",
  player_rush_yds_alternate: "rush_yds", player_pass_attempts_alternate: "pass_att", player_anytime_td: "atd",
};
const NAMES: Record<string, string> = { draftkings: "DraftKings", fanduel: "FanDuel" };

const key = process.env.ODDS_API_KEY ?? "proxy-injected";
const gid = process.argv[2];
if (!gid) {
  console.error("Usage: node scripts/nfl-listings.ts <game_id>");
  process.exit(1);
}
const root = new URL("..", import.meta.url).pathname;
const src = readFileSync(root + "public/console/data.js", "utf8");
const D = JSON.parse(src.slice(src.indexOf("{"), src.lastIndexOf("}") + 1));
const game = D.games.find((g: { id: string }) => g.id === gid);
if (!game) throw new Error(`No game ${gid} in the NFL data`);

const get = async (url: string) => {
  const r = await fetch(url, { headers: { "x-api-key": key } });
  if (!r.ok) throw new Error(`${r.status} from the odds feed: ${(await r.text()).replaceAll(key, "<key>").slice(0, 200)}`);
  return { body: await r.json(), left: r.headers.get("x-requests-remaining") };
};
const team = (abbr: string) => (D.meta.team_names?.[abbr] as string | undefined) ?? abbr;
const { body: events } = await get(`${API}/events`);
const day = new Date(`${game.day}T12:00:00Z`).getTime();
const ev = (events as { id: string; home_team: string; away_team: string; commence_time: string }[]).find((e) => {
  const t = new Date(e.commence_time).getTime();
  return Math.abs(t - day) < 2 * 86_400_000 && [e.home_team, e.away_team].some((n) => n.toLowerCase().includes(String(team(game.home)).toLowerCase()) || n.toLowerCase().endsWith(teamWord(game.home)));
});
function teamWord(abbr: string) {
  const w: Record<string, string> = { LA: "rams", LAC: "chargers", GB: "packers", DET: "lions", CHI: "bears", DAL: "cowboys", PHI: "eagles", BUF: "bills", KC: "chiefs", PIT: "steelers", DEN: "broncos" };
  return w[abbr] ?? abbr.toLowerCase();
}
if (!ev) throw new Error(`The odds feed has no event for ${game.away} @ ${game.home}`);
const { body, left } = await get(`${API}/events/${ev.id}/odds?regions=us&markets=${Object.keys(MARKETS).join(",")}&oddsFormat=american&bookmakers=${BOOKS.join(",")}`);

const rows = new Map<string, { player: string; market: string; k: number | null; prices: Record<string, number> }>();
for (const b of body.bookmakers ?? []) for (const m of b.markets ?? []) {
  const market = MARKETS[m.key]; if (!market) continue;
  for (const o of m.outcomes ?? []) {
    if (o.name !== "Over" && o.name !== "Yes") continue;
    const k = market === "atd" ? null : Math.round(o.point + 0.5);
    const id = `${o.description}|${market}|${k}`;
    const row = rows.get(id) ?? { player: o.description as string, market, k, prices: {} as Record<string, number> };
    row.prices[b.key as string] = o.price as number;
    rows.set(id, row);
  }
}
const out = {
  game: `${game.away} @ ${game.home}`, game_id: gid, pulled_at: new Date().toISOString().slice(0, 19) + "+00:00",
  source: `The Odds API (${BOOKS.map((b) => NAMES[b]).join(", ")})`,
  note: "Rungs these books list, and their prices. Used only to confirm a rung is listed and to show what a play pays. Never an input to a probability.",
  rungs: [...rows.values()].sort((a, b) => a.player.localeCompare(b.player) || a.market.localeCompare(b.market) || (a.k ?? 0) - (b.k ?? 0)),
};
writeFileSync(root + "model/output/nfl_listed_rungs.json", JSON.stringify(out));
console.log(`${out.game}: ${out.rungs.length} listed rungs from ${out.source}; feed requests left ${left}`);
