/**
 * Game and player intel for the advisor, read straight from the algorithms' output.
 *
 * These are the notes and numbers the algorithms already write for the console (game scripts, weather,
 * roles, matchup reads, availability). Nothing is added or worked out here. Results and track records
 * are deliberately left out: they are never shown on the site.
 */
import { matchPlayers, normName, type Catalog, type Sport } from "./legs.ts";

export type PlayerIntel = { sport: Sport; player: string; team?: string; position?: string; game?: string; [k: string]: unknown };
export type GameIntel = { sport: Sport; game: string; [k: string]: unknown };
export type Intel = { sport: Sport; built: string; players: PlayerIntel[]; games: GameIntel[] };

const plain = (html: unknown) => String(html ?? "").replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();

type NflRaw = {
  meta: { built?: string; season?: number; week?: number };
  games: { id: string; away: string; home: string; weekday?: string; kick?: string; venue?: string; started?: boolean; spread_home?: number; total?: number;
           implied?: Record<string, number>; roof?: string; wx?: string; temp?: number; wind?: number; qb?: Record<string, string> }[];
  players: { id: string; name: string; team: string; opp?: string; game: string; pos?: string; p: number; singles?: boolean; inj?: string | null; risk?: string;
             why?: string[] }[];
  props: Record<string, Record<string, { k: number[]; p: number[]; hits?: number[]; n?: number }>>;
  script_sgp?: { game: string; notes?: string[] }[];
};

export function nflIntel(data: unknown): Intel {
  const D = data as NflRaw;
  const label = new Map(D.games.map((g) => [g.id, `${g.away} @ ${g.home}`]));
  const scripts = new Map((D.script_sgp ?? []).map((s) => [s.game, s.notes ?? []]));
  return {
    sport: "NFL",
    built: D.meta.built ?? "",
    games: D.games.map((g) => ({
      sport: "NFL" as const, game: label.get(g.id)!, week: D.meta.week, kickoff: [g.weekday, g.kick].filter(Boolean).join(" "), venue: g.venue,
      already_started: !!g.started, home_spread: g.spread_home, total: g.total, implied_team_points: g.implied, roof: g.roof, weather: g.wx,
      temperature_f: g.temp, wind_mph: g.wind, quarterbacks: g.qb, algorithm_game_script: scripts.get(g.id) ?? [],
    })),
    players: D.players.map((p) => ({
      sport: "NFL" as const, player: p.name, team: p.team, opponent: p.opp, position: p.pos, game: label.get(p.game),
      anytime_touchdown_probability: p.p, singles_only_this_week: !!p.singles, injury_designation: p.inj ?? null, algorithm_risk_note: p.risk ?? null,
      algorithm_reasons: (p.why ?? []).map(plain),
      milestone_ladders: Object.fromEntries(Object.entries(D.props[p.id] ?? {}).map(([mk, lad]) => [mk, lad.k.map((k, i) => ({
        milestone: `${k}+`, probability: lad.p[i], ...(lad.hits && lad.n ? { cleared_this_season: `${lad.hits[i]} of ${lad.n} games` } : {}),
      }))])),
    })),
  };
}

type NbaRaw = {
  run_at?: string;
  games: { home: string; away: string; tip_utc?: string; preview?: boolean; notes?: string[];
           card?: { pace?: { ours?: number }; margin_home?: Record<string, number>; total?: Record<string, number>; win_prob_home?: number; blowout_prob?: number;
                    close_prob?: number; scripts?: { script: string; probability: number; who?: string }[]; blowout_warning?: unknown };
           players?: { name: string; status?: string; role?: string; role_change?: string; min_mean?: number; min_p10?: number; min_p90?: number;
                       pts?: number; reb?: number; ast?: number; fg3m?: number; blowout_exposure?: number; inout_notes?: string; adjustments?: string[] }[];
           availability?: { name: string; status: string; reason: string | null }[] }[];
};

export function nbaIntel(data: unknown): Intel {
  const D = data as NbaRaw;
  const games = D.games.filter((g) => !g.preview);
  return {
    sport: "NBA",
    built: D.run_at ?? "",
    games: games.map((g) => ({
      sport: "NBA" as const, game: `${g.away} @ ${g.home}`, tip_utc: g.tip_utc, pace: g.card?.pace?.ours, home_margin: g.card?.margin_home, total: g.card?.total,
      home_win_probability: g.card?.win_prob_home, blowout_probability: g.card?.blowout_prob, close_game_probability: g.card?.close_prob,
      algorithm_game_scripts: (g.card?.scripts ?? []).map((s) => ({ script: s.script, probability: s.probability, who_gains_or_loses: s.who })),
      algorithm_notes: g.notes ?? [],
      availability: (g.availability ?? []).map((a) => ({ player: a.name, status: a.status, reason: a.reason })),
    })),
    players: games.flatMap((g) => (g.players ?? []).map((p) => ({
      sport: "NBA" as const, player: p.name, game: `${g.away} @ ${g.home}`, status: p.status, role: p.role, role_change: p.role_change,
      projected_minutes: { mean: p.min_mean, low: p.min_p10, high: p.min_p90 },
      projected: { points: p.pts, rebounds: p.reb, assists: p.ast, threes: p.fg3m },
      blowout_exposure: p.blowout_exposure, teammate_absence_notes: p.inout_notes, algorithm_adjustments: p.adjustments ?? [],
    }))),
  };
}

export type IntelLookup = { found: true; data: PlayerIntel | GameIntel; rated_legs?: unknown[] } | { found: false; reason: string; candidates?: string[] };

/** Everything the algorithm has on one player, plus the legs it rates for him tonight. */
export function playerIntel(name: string, intel: Intel, catalog?: Catalog): IntelLookup {
  const names = [...new Set(intel.players.map((p) => p.player))];
  const want = normName(name);
  let hits = names.filter((n) => normName(n) === want);
  if (!hits.length) hits = catalog ? matchPlayers(name, catalog).filter((n) => names.includes(n)) : [];
  if (!hits.length) hits = names.filter((n) => normName(n).split(" ").pop() === want.split(" ").pop());
  if (hits.length === 0) return { found: false, reason: `The ${intel.sport} algorithm has nothing on "${name}" for the current slate.` };
  if (hits.length > 1) return { found: false, reason: `"${name}" could be more than one player. Ask which one.`, candidates: hits };
  const data = intel.players.find((p) => p.player === hits[0])!;
  const rated = catalog?.legs.filter((l) => l.player === hits[0]).map((l) => ({ market: l.market, milestone: l.threshold === null ? null : `${l.threshold}+`, probability: l.prob }));
  return { found: true, data, ...(intel.sport === "NBA" && rated ? { rated_legs: rated } : {}) };
}

/** The algorithm's read on one game. `query` can be "BUF @ KC", a team code or a team name fragment. */
export function gameIntel(query: string, intel: Intel): IntelLookup {
  const q = query.toLowerCase().replace(/\s+(vs?\.?|at|@|v)\s+/g, " @ ").trim();
  const parts = q.split("@").map((s) => s.trim()).filter(Boolean);
  const hits = intel.games.filter((g) => {
    const teams = g.game.toLowerCase().split(" @ ");
    return parts.every((p) => teams.some((t) => t === p || p.includes(t) || t.includes(p)));
  });
  if (hits.length === 0) return { found: false, reason: `No ${intel.sport} game matching "${query}" on the current slate.`, candidates: intel.games.map((g) => g.game) };
  if (hits.length > 1) return { found: false, reason: `"${query}" matches more than one game. Ask which one.`, candidates: hits.map((g) => g.game) };
  return { found: true, data: hits[0] };
}
