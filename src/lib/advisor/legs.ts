/**
 * The catalogue of legs the algorithms have rated.
 *
 * The advisor and the slip audit read a rating from here or say "unrated". Nothing in this folder
 * works out a probability: every number is one the NFL or NBA algorithm wrote to its own output.
 */

export type Sport = "NFL" | "NBA";
export type Side = "over" | "under";

/** Canonical market names shared by slips and the catalogue. */
export type Market =
  // NFL
  | "pass_yds" | "pass_td" | "pass_att" | "rush_yds" | "carries" | "rec" | "rec_yds" | "atd"
  // NBA
  | "pts" | "reb" | "ast" | "fg3m" | "stl" | "blk" | "pra" | "pr" | "pa";

export const MARKET_LABEL: Record<Market, string> = {
  pass_yds: "passing yards", pass_td: "passing touchdowns", pass_att: "pass attempts", rush_yds: "rushing yards",
  carries: "carries", rec: "receptions", rec_yds: "receiving yards", atd: "anytime touchdown",
  pts: "points", reb: "rebounds", ast: "assists", fg3m: "threes made", stl: "steals", blk: "blocks",
  pra: "points + rebounds + assists", pr: "points + rebounds", pa: "points + assists",
};

export type RatedLeg = {
  sport: Sport;
  player: string;
  team?: string;
  game?: string;
  market: Market;
  /** The milestone: "225+" is 225. Null for anytime touchdown. */
  threshold: number | null;
  side: Side;
  /** The algorithm's chance that the leg hits. */
  prob: number;
  /** True when the algorithm marks the player as a single only (not a parlay leg) this week. */
  singlesOnly?: boolean;
};

export type Catalog = {
  sport: Sport;
  /** When the algorithm built this output, as it wrote it. */
  built: string;
  legs: RatedLeg[];
};

// ---------- NFL: the console data (public/console/data.js) ----------
type NflData = {
  meta: { built?: string };
  games: { id: string; away: string; home: string; started?: boolean }[];
  players: { id: string; name: string; team: string; game: string; p: number; singles?: boolean }[];
  props: Record<string, Record<string, { k: number[]; p: number[] }>>;
};
const NFL_MARKETS = new Set<string>(["pass_yds", "pass_td", "pass_att", "rush_yds", "carries", "rec", "rec_yds"]);

/** `started` games are left out: a rating made before kick-off says nothing once the game is under way. */
export function nflCatalog(data: unknown): Catalog {
  const D = data as NflData;
  const open = new Map(D.games.filter((g) => !g.started).map((g) => [g.id, `${g.away} @ ${g.home}`]));
  const legs: RatedLeg[] = [];
  for (const p of D.players) {
    const game = open.get(p.game);
    if (!game) continue;
    const base = { sport: "NFL" as const, player: p.name, team: p.team, game, singlesOnly: !!p.singles };
    if (Number.isFinite(p.p)) legs.push({ ...base, market: "atd", threshold: null, side: "over", prob: p.p });
    for (const [mk, lad] of Object.entries(D.props[p.id] ?? {})) {
      if (!NFL_MARKETS.has(mk)) continue;
      lad.k.forEach((k, i) => {
        if (Number.isFinite(lad.p[i])) legs.push({ ...base, market: mk as Market, threshold: k, side: "over", prob: lad.p[i] });
      });
    }
  }
  return { sport: "NFL", built: D.meta.built ?? "", legs };
}

/** Parse public/console/data.js (`const D = {...};`) into its data object. */
export function parseConsoleData(source: string): unknown {
  return JSON.parse(source.slice(source.indexOf("{"), source.lastIndexOf("}") + 1));
}

// ---------- NBA: the slate (model/nba/output/nba_site.json) ----------
type NbaLeg = { name?: string; market?: string; line?: number; side?: string; p?: number };
type NbaData = {
  run_at?: string;
  games: { home: string; away: string; preview?: boolean; singles?: NbaLeg[]; tickets?: { legs: NbaLeg[] }[] }[];
};
const NBA_MARKETS = new Set<string>(["pts", "reb", "ast", "fg3m", "stl", "blk", "pra", "pr", "pa"]);

export function nbaCatalog(data: unknown): Catalog {
  const D = data as NbaData;
  const seen = new Map<string, RatedLeg>();
  for (const g of D.games) {
    if (g.preview) continue;
    const game = `${g.away} @ ${g.home}`;
    const all = [...(g.singles ?? []), ...(g.tickets ?? []).flatMap((t) => t.legs)];
    for (const l of all) {
      if (!l.name || !l.market || !NBA_MARKETS.has(l.market) || typeof l.line !== "number" || typeof l.p !== "number") continue;
      const side: Side = l.side === "under" ? "under" : "over";
      // an over on 5.5 is the 6+ milestone; an under on 5.5 is "5 or fewer", kept as its line
      const threshold = side === "over" ? Math.floor(l.line) + 1 : l.line;
      const leg: RatedLeg = { sport: "NBA", player: l.name, game, market: l.market as Market, threshold, side, prob: l.p };
      seen.set(`${l.name}|${l.market}|${side}|${threshold}`, leg);
    }
  }
  return { sport: "NBA", built: D.run_at ?? "", legs: [...seen.values()] };
}

// ---------- names ----------
const SUFFIX = /\b(jr|sr|ii|iii|iv|v)\b/g;
/** "Kelly Oubre Jr." and "kelly oubre" compare equal. */
export function normName(name: string): string {
  return name
    .normalize("NFD").replace(/[̀-ͯ]/g, "")
    .toLowerCase().replace(/[.'’`]/g, "").replace(/-/g, " ")
    .replace(SUFFIX, " ").replace(/\s+/g, " ").trim();
}

/**
 * The catalogue's players that a slip's name could mean: the full name, an initial and surname
 * ("J. Allen"), or a surname alone. More than one result means the name is ambiguous.
 */
export function matchPlayers(name: string, catalog: Catalog): string[] {
  const want = normName(name);
  if (!want) return [];
  const players = [...new Set(catalog.legs.map((l) => l.player))];
  const exact = players.filter((p) => normName(p) === want);
  if (exact.length) return exact;
  const parts = want.split(" ");
  const last = parts[parts.length - 1];
  const first = parts.length > 1 ? parts[0] : "";
  return players.filter((p) => {
    const n = normName(p).split(" ");
    const surname = n.slice(1).join(" ") || n[0];
    if (parts.length === 1) return surname === last || n[n.length - 1] === last;
    // initial + surname, e.g. "j allen" for "josh allen"
    return first.length === 1 && n[0].startsWith(first) && (surname === parts.slice(1).join(" ") || n[n.length - 1] === last);
  });
}
