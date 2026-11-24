/**
 * Re-grade saved slips when the algorithm's data changes.
 *
 * A saved slip remembers what the algorithm said about each leg when it was saved. Each time fresh
 * algorithm output is loaded, the saved legs are looked up again: a leg whose player is now out, has been
 * pulled from the slate, or has dropped under the floor raises an alert with a swap from the algorithm.
 * A game that has kicked off is left alone.
 */
import { TICKET_RULES } from "../advisor/audit.ts";
import type { Catalog, Market, RatedLeg, Side, Sport } from "../advisor/legs.ts";
import { GRADE_CONFIG, gradeSlip } from "./grade.ts";
import { legLabel, suggestChanges } from "./suggest.ts";

export const RECHECK_CONFIG = {
  /** A leg that has lost at least this much chance since it was saved, and is now under the floor, is flagged. */
  dropAlert: 0.08,
};

export type SavedLeg = {
  player: string; market: Market; threshold: number | null; side: Side;
  /** What the algorithm said when the slip was saved. */
  prob: number; injury: string | null; game: string | null; odds: number | null;
};
export type SavedSlip = {
  id: string; savedAt: string; sport: Sport; built: string; legs: SavedLeg[];
  /** The tracked bet this slip was logged as. */
  betId?: string;
};

export type SlipAlert = {
  slipId: string; legIndex: number;
  kind: "out" | "pulled" | "weaker";
  /** For the user, e.g. "Your leg is out". */
  title: string; detail: string;
  /** The algorithm's replacement, if it has one. */
  swap: RatedLeg | null;
};

export function toSavedLeg(l: RatedLeg, odds: number | null = null): SavedLeg {
  return { player: l.player, market: l.market, threshold: l.threshold, side: l.side, prob: l.prob, injury: l.injury ?? null, game: l.game ?? null, odds };
}

const isOut = (injury: string | null | undefined) => !!injury && GRADE_CONFIG.outStatuses.some((s) => injury.toLowerCase().includes(s));
const savedLabel = (l: SavedLeg) => legLabel({ ...l, sport: "NFL" } as RatedLeg);

export function recheckSlip(slip: SavedSlip, catalog: Catalog): SlipAlert[] {
  if (slip.sport !== catalog.sport || slip.built === catalog.built) return [];
  const floor = TICKET_RULES[catalog.sport].floor;
  const started = new Set(catalog.startedPlayers ?? []);
  const grade = gradeSlip(slip.legs.map((l) => ({ player: l.player, market: l.market, threshold: l.threshold, side: l.side, odds: l.odds })), catalog);
  const alerts: SlipAlert[] = [];
  slip.legs.forEach((saved, legIndex) => {
    if (started.has(saved.player)) return; // the game is under way: nothing to change now
    const now = grade.legs[legIndex];
    const match = now.status === "rated" ? now.match : null;
    let alert: Omit<SlipAlert, "swap"> | null = null;
    if (!match && now.unrated === "player-not-found")
      alert = { slipId: slip.id, legIndex, kind: "pulled", title: "A leg has been pulled",
                detail: `${saved.player} is no longer in the algorithm's numbers for this slate, so ${savedLabel(saved)} is unrated now.` };
    else if (match && isOut(match.injury) && !isOut(saved.injury))
      alert = { slipId: slip.id, legIndex, kind: "out", title: "Your leg is out",
                detail: `${saved.player} is now listed ${match.injury}. ${savedLabel(saved)} should come off the slip.` };
    else if (match && match.singlesOnly && slip.legs.length > 1 && grade.legs[legIndex].flags.includes("singles-only") && saved.injury === null && match.injury)
      alert = { slipId: slip.id, legIndex, kind: "out", title: "A leg is now singles only",
                detail: `${saved.player} is listed ${match.injury}, and the algorithm now plays him as a single only.` };
    else if (match && match.market !== "atd" && saved.prob - match.prob >= RECHECK_CONFIG.dropAlert && match.prob < floor)
      alert = { slipId: slip.id, legIndex, kind: "weaker", title: "A leg has weakened",
                detail: `${savedLabel(saved)} was ${Math.round(saved.prob * 100)}% when you saved it and is ${Math.round(match.prob * 100)}% now.` };
    if (!alert) return;
    // the swap: what the algorithm would put in this leg's place, keeping the slip the same length
    let swap: RatedLeg | null = null;
    if (match) {
      const s = suggestChanges(grade, catalog, { legCount: slip.legs.length });
      swap = s.swap.find((x) => x.index === legIndex)?.to ?? null;
    } else {
      // the pulled leg is still counted as an (unrated) leg of the slip, so ask for one more to fill its place
      const s = suggestChanges(grade, catalog, { legCount: slip.legs.length + 1 });
      swap = s.add[0]?.leg ?? null;
    }
    alerts.push({ ...alert, swap });
  });
  return alerts;
}

export function recheckAll(slips: SavedSlip[], catalog: Catalog): SlipAlert[] {
  return slips.flatMap((s) => recheckSlip(s, catalog));
}
