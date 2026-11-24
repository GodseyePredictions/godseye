/**
 * The algorithms' own picks and whatever prices their output carries, for get_algo_picks and get_odds.
 *
 * Read straight from each sport's output file. A request for a date or game the output does not cover
 * returns nothing, with a note saying so; the advisor then has no picks to give.
 */
import { MARKET_LABEL, type Market, type Sport } from "./legs.ts";

export type PickLeg = { leg: string; probability: number; price?: number | null };
export type Pick = {
  kind: string;
  game: string;
  legs: PickLeg[];
  /** The algorithm's chance that every leg hits. */
  joint_probability: number | null;
  /** The book's listed price if the output has one, and whether it is only leg prices multiplied together. */
  book_price?: number | null;
  price_is_estimate?: boolean;
};
export type GameLine = { game: string; date: string; started: boolean; lines: Record<string, unknown>; prop_prices: { leg: string; market: string; price: number; probability: number }[] };
export type PicksIndex = { sport: Sport; built: string; dates: string[]; picks: (Pick & { date: string })[]; games: GameLine[]; book: string | null };

type NflRaw = {
  meta: { built?: string };
  games: { id: string; away: string; home: string; day?: string; started?: boolean; spread_home?: number; total?: number; implied?: Record<string, number> }[];
  players: { id: string; name: string; game: string; p: number; singles?: boolean }[];
  algo?: {
    sgp?: { game: string; p: number; legs: { id: string; mk: string; k: number | null; p: number }[] }[];
    atd_combos?: { game: string; n: number; legs: string[]; p: number }[];
    atd?: { n: number; legs: string[]; p: number }[];
  };
};

const nflLeg = (name: string, mk: string, k: number | null) => (mk === "atd" ? `${name} anytime touchdown` : `${name} ${k}+ ${MARKET_LABEL[mk as Market] ?? mk}`);

export function nflPicks(data: unknown): PicksIndex {
  const D = data as NflRaw;
  const P = new Map(D.players.map((p) => [p.id, p]));
  const G = new Map(D.games.map((g) => [g.id, g]));
  const label = (id: string) => { const g = G.get(id); return g ? `${g.away} @ ${g.home}` : id; };
  const open = (id: string) => { const g = G.get(id); return !!g && !g.started; };
  const picks: PicksIndex["picks"] = [];
  for (const t of D.algo?.sgp ?? []) {
    if (!open(t.game)) continue;
    picks.push({ kind: "props same-game parlay", game: label(t.game), date: G.get(t.game)?.day ?? "", joint_probability: t.p,
                 legs: t.legs.map((l) => ({ leg: nflLeg(P.get(l.id)?.name ?? l.id, l.mk, l.k), probability: l.p })) });
  }
  for (const t of D.algo?.atd_combos ?? []) {
    if (!open(t.game)) continue;
    picks.push({ kind: `anytime-touchdown ${t.n === 2 ? "double" : `${t.n}-leg ticket`}`, game: label(t.game), date: G.get(t.game)?.day ?? "", joint_probability: t.p,
                 legs: t.legs.map((id) => ({ leg: nflLeg(P.get(id)?.name ?? id, "atd", null), probability: P.get(id)?.p ?? NaN })).filter((l) => Number.isFinite(l.probability)) });
  }
  for (const t of D.algo?.atd ?? []) {
    const games = [...new Set(t.legs.map((id) => P.get(id)?.game).filter((g): g is string => !!g))];
    if (!games.length || !games.every(open)) continue;
    picks.push({ kind: `anytime-touchdown ${t.n}-leg ticket across games`, game: games.map(label).join(", "), date: G.get(games[0])?.day ?? "", joint_probability: t.p,
                 legs: t.legs.map((id) => ({ leg: nflLeg(P.get(id)?.name ?? id, "atd", null), probability: P.get(id)?.p ?? NaN })).filter((l) => Number.isFinite(l.probability)) });
  }
  const games: GameLine[] = D.games.map((g) => ({
    game: `${g.away} @ ${g.home}`, date: g.day ?? "", started: !!g.started,
    lines: { home_spread: g.spread_home ?? null, total: g.total ?? null, implied_team_points: g.implied ?? null },
    prop_prices: [], // the NFL output carries the market's game lines only; there is no player-prop price feed
  }));
  return { sport: "NFL", built: D.meta.built ?? "", dates: [...new Set(games.filter((g) => !g.started).map((g) => g.date).filter(Boolean))].sort(), picks, games, book: null };
}

type NbaLeg = { label?: string; market?: string; p?: number; price?: number | null };
type NbaRaw = {
  run_at?: string; book?: string;
  games: { home: string; away: string; tip_utc?: string; preview?: boolean; notes?: string[]; card?: { date?: string; matchup?: string };
           tickets?: { type: string; joint: number; book_price?: number | null; price_is_estimate?: boolean; legs: NbaLeg[] }[]; singles?: NbaLeg[] }[];
};
const NBA_KIND: Record<string, string> = { props_4: "4-leg props same-game parlay", props_4b: "second 4-leg props same-game parlay", props_6: "6-leg props same-game parlay" };

export function nbaPicks(data: unknown): PicksIndex {
  const D = data as NbaRaw;
  const picks: PicksIndex["picks"] = [];
  const games: GameLine[] = [];
  for (const g of D.games) {
    if (g.preview) continue;
    const game = `${g.away} @ ${g.home}`;
    const date = g.card?.date ?? (g.tip_utc ? new Date(new Date(g.tip_utc).getTime() - 5 * 3600e3).toISOString().slice(0, 10) : "");
    for (const t of g.tickets ?? [])
      picks.push({ kind: NBA_KIND[t.type] ?? t.type, game, date, joint_probability: t.joint, book_price: t.book_price ?? null, price_is_estimate: !!t.price_is_estimate,
                   legs: t.legs.filter((l) => l.label && typeof l.p === "number").map((l) => ({ leg: l.label as string, probability: l.p as number, price: l.price ?? null })) });
    const priced = new Map<string, { leg: string; market: string; price: number; probability: number }>();
    for (const l of [...(g.singles ?? []), ...(g.tickets ?? []).flatMap((t) => t.legs)])
      if (l.label && l.market && typeof l.price === "number" && typeof l.p === "number") priced.set(l.label, { leg: l.label, market: l.market, price: l.price, probability: l.p });
    const gameLines = (g.notes ?? []).find((n) => n.startsWith("Game lines")) ?? null;
    games.push({ game, date, started: false, lines: { game_lines_with_algorithm_chance: gameLines }, prop_prices: [...priced.values()] });
  }
  return { sport: "NBA", built: D.run_at ?? "", dates: [...new Set(games.map((g) => g.date).filter(Boolean))].sort(), picks, games, book: D.book ?? null };
}

const sameGame = (query: string, game: string) => {
  const q = query.toLowerCase().replace(/\s+(vs?\.?|at|@|v)\s+/g, " @ ").split("@").map((s) => s.trim()).filter(Boolean);
  const teams = game.toLowerCase().split(/ @ |, /);
  return q.every((p) => teams.some((t) => t === p || p.includes(t) || t.includes(p)));
};

/** get_algo_picks: the algorithm's tickets for a date (and optionally one game). Empty when it has none. */
export function algoPicks(index: PicksIndex, date: string | null, game: string | null) {
  let picks = index.picks;
  if (date) picks = picks.filter((p) => p.date === date);
  if (game) picks = picks.filter((p) => sameGame(game, p.game));
  const note = picks.length ? `Algorithm output built ${index.built}.`
    : date && !index.dates.includes(date) ? `The ${index.sport} algorithm has no output for ${date}. It covers: ${index.dates.join(", ") || "no upcoming games"}.`
    : `The ${index.sport} algorithm has no picks${game ? ` for ${game}` : ""}${date ? ` on ${date}` : ""}. There is nothing to recommend.`;
  return { sport: index.sport, picks: picks.map(({ date: d, ...p }) => ({ ...p, date: d })), note };
}

/** get_odds: the prices the algorithm's output carries for a game. It is not a live odds feed. */
export function oddsFor(index: PicksIndex, game: string, market: string | null) {
  const hits = index.games.filter((g) => sameGame(game, g.game));
  if (hits.length !== 1)
    return { found: false, note: hits.length ? `"${game}" matches more than one game.` : `No ${index.sport} game matching "${game}" in the algorithm's output.`, games: index.games.map((g) => g.game) };
  const g = hits[0];
  const m = market?.toLowerCase() ?? null;
  const props = m ? g.prop_prices.filter((p) => p.market === m || p.leg.toLowerCase().includes(m)) : g.prop_prices;
  return {
    found: true, game: g.game, book: index.book, game_lines: g.lines, prop_prices: props,
    note: props.length ? `Prices as loaded when the algorithm ran (${index.built}); they move, so the user should confirm on their book.`
      : `The ${index.sport} algorithm's output has no ${m ? `${m} ` : "player-prop "}prices for this game. Ask the user to read the price from their book.`,
  };
}
