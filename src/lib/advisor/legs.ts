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
  /** The algorithm's own ids and context. Present for NFL, where the correlation engine needs them. */
  playerId?: string;
  pos?: string;
  gameId?: string;
  /** The official injury designation the algorithm loaded, if any (for example "Questionable"). */
  injury?: string | null;
  /** The algorithm's own risk note for this leg (game script, blowout, role). */
  risk?: string | null;
  /** How often this milestone was cleared this season: `hits` of `games`. */
  hits?: number | null;
  games?: number | null;
};

/** The measured correlations the NFL algorithm ships with its weekly output. */
export type NflCorr = { atd: Record<string, number>; legs: Record<string, number> & { _rel?: Record<string, number> } };

/**
 * The correlations the NBA algorithm measures from each night's simulations (model/nba/audit_export.py):
 * one number per pair of (player, market) in a game, keyed "playerId:market|playerId:market" in sorted order.
 */
export type NbaCorr = { kind: "nba"; pairs: Record<string, Record<string, number>> };
export type Corr = NflCorr | NbaCorr;

export type Catalog = {
  sport: Sport;
  /** When the algorithm built this output, as it wrote it. */
  built: string;
  legs: RatedLeg[];
  /** Without it, the chance of a multi-leg slip cannot be worked out and is not stated. */
  corr?: Corr;
  /** Players whose game has already kicked off. They have no legs in `legs`. */
  startedPlayers?: string[];
};

// ---------- NFL: the console data (public/console/data.js) ----------
type NflData = {
  meta: { built?: string };
  games: { id: string; away: string; home: string; started?: boolean }[];
  players: {
    id: string; name: string; team: string; game: string; p: number; singles?: boolean; pos?: string;
    inj?: string | null; risk?: string | null; riskm?: Record<string, string> | null;
  }[];
  props: Record<string, Record<string, { k: number[]; p: number[]; hits?: number[]; n?: number }>>;
  corr?: NflCorr;
};
const NFL_MARKETS = new Set<string>(["pass_yds", "pass_td", "pass_att", "rush_yds", "carries", "rec", "rec_yds"]);

/** `started` games are left out: a rating made before kick-off says nothing once the game is under way. */
export function nflCatalog(data: unknown): Catalog {
  const D = data as NflData;
  const open = new Map(D.games.filter((g) => !g.started).map((g) => [g.id, `${g.away} @ ${g.home}`]));
  const legs: RatedLeg[] = [];
  const startedPlayers: string[] = [];
  for (const p of D.players) {
    const game = open.get(p.game);
    if (!game) {
      startedPlayers.push(p.name);
      continue;
    }
    const base = {
      sport: "NFL" as const, player: p.name, team: p.team, game, singlesOnly: !!p.singles,
      playerId: p.id, pos: p.pos, gameId: p.game, injury: p.inj ?? null,
    };
    if (Number.isFinite(p.p))
      legs.push({ ...base, market: "atd", threshold: null, side: "over", prob: p.p, risk: p.risk ?? null });
    for (const [mk, lad] of Object.entries(D.props[p.id] ?? {})) {
      if (!NFL_MARKETS.has(mk)) continue;
      lad.k.forEach((k, i) => {
        if (Number.isFinite(lad.p[i]))
          legs.push({
            ...base, market: mk as Market, threshold: k, side: "over", prob: lad.p[i],
            risk: p.riskm?.[mk] ?? p.risk ?? null, hits: lad.hits?.[i] ?? null, games: lad.n ?? null,
          });
      });
    }
  }
  return { sport: "NFL", built: D.meta.built ?? "", legs, corr: D.corr, startedPlayers };
}

/** Parse public/console/data.js (`const D = {...};`) into its data object. */
export function parseConsoleData(source: string): unknown {
  return JSON.parse(source.slice(source.indexOf("{"), source.lastIndexOf("}") + 1));
}

// ---------- NBA: the slate (model/nba/output/nba_site.json) and its audit data (nba_audit.json) ----------
type NbaLeg = { name?: string; market?: string; line?: number; side?: string; p?: number };
type NbaData = {
  run_at?: string;
  games: { home: string; away: string; preview?: boolean; singles?: NbaLeg[]; tickets?: { legs: NbaLeg[] }[] }[];
};
type NbaAudit = {
  run_at?: string;
  games?: {
    id: string; home: string; away: string; corr?: Record<string, number>;
    ladder?: (NbaLeg & { player_id?: string; team?: string; note?: string | null })[];
  }[];
};
const NBA_MARKETS = new Set<string>(["pts", "reb", "ast", "fg3m", "stl", "blk", "pra", "pr", "pa"]);

/** An over on 5.5 is the 6+ milestone; an under on 5.5 is "5 or fewer", kept as its line. */
const nbaThreshold = (side: Side, line: number) => (side === "over" ? Math.floor(line) + 1 : line);

/**
 * Every NBA leg the algorithm rated tonight. With the audit data (written by the same run) that is every
 * offered rung for every confirmed player, with the ids and correlations the joint-probability engine needs.
 * Without it, or if it is from a different run, only the legs on the posted slips are rated and a multi-leg
 * slip gets no combined chance.
 */
export function nbaCatalog(data: unknown, audit?: unknown): Catalog {
  const D = data as NbaData;
  const seen = new Map<string, RatedLeg>();
  for (const g of D.games) {
    if (g.preview) continue;
    const game = `${g.away} @ ${g.home}`;
    const all = [...(g.singles ?? []), ...(g.tickets ?? []).flatMap((t) => t.legs)];
    for (const l of all) {
      if (!l.name || !l.market || !NBA_MARKETS.has(l.market) || typeof l.line !== "number" || typeof l.p !== "number") continue;
      const side: Side = l.side === "under" ? "under" : "over";
      const threshold = nbaThreshold(side, l.line);
      const leg: RatedLeg = { sport: "NBA", player: l.name, game, market: l.market as Market, threshold, side, prob: l.p };
      seen.set(`${l.name}|${l.market}|${side}|${threshold}`, leg);
    }
  }
  const A = audit as NbaAudit | undefined;
  // numbers from two different runs must never be mixed
  if (!A?.games?.length || !D.run_at || A.run_at !== D.run_at) return { sport: "NBA", built: D.run_at ?? "", legs: [...seen.values()] };

  const live = new Set(D.games.filter((g) => !g.preview).map((g) => `${g.away} @ ${g.home}`));
  const pairs: NbaCorr["pairs"] = {};
  for (const g of A.games) {
    const game = `${g.away} @ ${g.home}`;
    if (!live.has(game)) continue;
    pairs[g.id] = g.corr ?? {};
    for (const l of g.ladder ?? []) {
      if (!l.name || !l.player_id || !l.market || !NBA_MARKETS.has(l.market) || typeof l.line !== "number" || typeof l.p !== "number") continue;
      const side: Side = l.side === "under" ? "under" : "over";
      const threshold = nbaThreshold(side, l.line);
      seen.set(`${l.name}|${l.market}|${side}|${threshold}`, {
        sport: "NBA", player: l.name, team: l.team || undefined, game, market: l.market as Market, threshold, side, prob: l.p,
        playerId: l.player_id, gameId: g.id, risk: l.note ?? null,
      });
    }
  }
  // a posted leg whose player is not in the audit data has no id; the engine then declines to combine it
  return { sport: "NBA", built: D.run_at, legs: [...seen.values()], corr: { kind: "nba", pairs } };
}

// ---------- names ----------
const SUFFIX = /\b(jr|sr|ii|iii|iv|v)\b/g;
/** "Kelly Oubre Jr." and "kelly oubre" compare equal. */
export function normName(name: string): string {
  return name
    .normalize("NFD").replace(/\p{M}/gu, "")
    .toLowerCase().replace(/[.'\u2019`]/g, "").replace(/-/g, " ")
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
