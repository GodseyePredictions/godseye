/**
 * Picks of the day: the algorithm's own slips, ranked by the algorithm's own chance.
 *
 * Nothing is chosen by hand and nothing is worked out here. For each game it takes the slip the algorithm
 * gives the best chance of hitting; "of the day" is the few with the best chance across the whole slate.
 * It updates whenever the algorithm's output does.
 */
import type { Pick, PicksIndex } from "./advisor/picks.ts";

export type DayPick = Pick & { date: string };
export type PicksOfTheDay = {
  sport: PicksIndex["sport"];
  built: string;
  /** The slate these are for (the earliest date in the output), or null when there is nothing upcoming. */
  date: string | null;
  /** The best slip in each game, best first. */
  topPerGame: DayPick[];
  /** The best few across the slate. */
  best: DayPick[];
  /** How many games the output covers on that date. */
  games: number;
};

export const PICKS_OF_DAY = { best: 3 };

const chance = (p: Pick) => p.joint_probability ?? -1;

export function picksOfTheDay(index: PicksIndex): PicksOfTheDay {
  const date = index.dates[0] ?? null;
  const today = index.picks.filter((p) => p.joint_probability !== null && p.legs.length > 0 && (!date || p.date === date));
  const byGame = new Map<string, DayPick>();
  for (const p of today) {
    const have = byGame.get(p.game);
    if (!have || chance(p) > chance(have)) byGame.set(p.game, p);
  }
  const topPerGame = [...byGame.values()].sort((a, b) => chance(b) - chance(a));
  return { sport: index.sport, built: index.built, date, topPerGame, best: topPerGame.slice(0, PICKS_OF_DAY.best), games: index.games.filter((g) => !date || g.date === date).length };
}
