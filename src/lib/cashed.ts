/**
 * What a winning slip returns on a fixed wager at the slip's American odds (stake included).
 * Used by the Cashed slips tabs, which show the algorithm's winning slips with a set wager.
 */
import { toDecimal } from "./odds.ts";

/** The NHL Cashed slips tab shows every slip at this wager (owner, 25 November 2026). */
export const NHL_CASHED_WAGER = 125;

export function cashedReturn(wager: number, american: number | null | undefined): number | null {
  if (american == null || !Number.isFinite(american) || Math.abs(american) < 100 || !(wager > 0)) return null;
  return Math.round(wager * toDecimal(american) * 100) / 100;
}

export const dollars = (x: number) => `$${x.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
