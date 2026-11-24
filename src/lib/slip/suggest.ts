/**
 * Suggest removals, swaps and adds for a graded slip. Algorithm output only.
 *
 * Every suggested leg is one the algorithm has rated, on a rung from its own ladder. The book's actual
 * ladder is not known here (there is no price feed), so every swap and add carries the note to check the
 * rung is offered, and the improved slip has no book price until the user re-prices it.
 *
 * Without the algorithm's correlations (an NBA night with no audit data) there is no joint chance, so only rule-based removals
 * and same-player safer rungs are suggested, and no "improved" chance is stated.
 */
import { NBA_PROPS_RULES, TICKET_RULES } from "../advisor/audit.ts";
import { fairAmerican, jointProbability } from "../advisor/joint.ts";
import { MARKET_LABEL, type Catalog, type Market, type RatedLeg } from "../advisor/legs.ts";
import { GRADE_CONFIG, ratedLegs, ruleCheck, type SlipGrade } from "./grade.ts";

export const SUGGEST_CONFIG = {
  /** Replacement and added legs come from this band of the ladder: at or above the floor, not so safe they pay nothing. */
  rungCeiling: 0.88,
  rungTarget: 0.78,
  /** A swap to another player must lift the slip's chance by at least this much. */
  minSwapGain: 0.004,
  /** Simulations used while comparing candidates; the final numbers use the full count. */
  searchSims: 16_000,
  maxLegs: 12,
};

const YARDS: Market[] = ["pass_yds", "rush_yds", "rec_yds"];
const LADDER_START: Partial<Record<Market, number>> = { rush_yds: 20, rec_yds: 20 };

/** bet365 milestone rules: yardage rungs in steps of 5, rushing and receiving yards from 20+. */
export function validRung(market: Market, k: number | null): boolean {
  if (market === "atd") return k === null;
  if (k === null || !(k > 0)) return false;
  if (YARDS.includes(market) && k % 5 !== 0) return false;
  return k >= (LADDER_START[market] ?? 0);
}

/** NBA ticket structure: at most one rebound leg, none on a small slip, and a small slip has one leg per player. */
function nbaFits(current: RatedLeg[], c: RatedLeg, size: number): boolean {
  const small = size <= NBA_PROPS_RULES.smallSlip;
  if (c.market === "reb" && (small || current.filter((l) => l.market === "reb").length >= (TICKET_RULES.NBA.maxRebounds ?? 0))) return false;
  if (small && current.some((l) => l.player === c.player)) return false;
  return true;
}

export const legLabel = (l: RatedLeg) => (l.market === "atd" ? `${l.player} anytime touchdown` : `${l.player} ${l.threshold}+ ${MARKET_LABEL[l.market]}`);
const same = (a: RatedLeg, b: RatedLeg) => a.player === b.player && a.market === b.market && a.threshold === b.threshold && a.side === b.side;
const pct = (p: number) => `${(p * 100).toFixed(1)}%`;

export type Removal = { index: number; leg: RatedLeg; kind: "out" | "rule" | "negative-value" | "fights-script" | "weak"; reason: string };
export type Swap = { index: number; from: RatedLeg; to: RatedLeg; kind: "safer-rung" | "stronger-leg"; reason: string };
export type Add = { leg: RatedLeg; reason: string };

export type ImprovedSlip = {
  legs: RatedLeg[];
  /** Legs from the original slip the algorithm could not rate, carried over untouched. */
  unratedKept: string[];
  joint: number | null;
  fairOdds: number | null;
  rules: SlipGrade["rules"];
  note: string;
};

export type Suggestions = {
  remove: Removal[];
  swap: Swap[];
  add: Add[];
  /** Null when nothing would change. */
  improved: ImprovedSlip | null;
  notes: string[];
};

export type Preferences = {
  /** How many legs the user wants on the slip. Removed legs are replaced, and legs added, to reach it. */
  legCount?: number | null;
  book?: string | null;
};

/** The best rung of one player's market inside the suggestion band, or null. */
function bandRung(catalog: Catalog, player: string, market: Market, floor: number): RatedLeg | null {
  let best: RatedLeg | null = null;
  for (const l of catalog.legs) {
    if (l.player !== player || l.market !== market || l.side !== "over" || !validRung(market, l.threshold)) continue;
    if (l.prob < floor || l.prob > SUGGEST_CONFIG.rungCeiling) continue;
    if (!best || Math.abs(l.prob - SUGGEST_CONFIG.rungTarget) < Math.abs(best.prob - SUGGEST_CONFIG.rungTarget)) best = l;
  }
  return best;
}

/** The highest rung below the current one, on the same player and market, that clears the floor. */
function saferRung(catalog: Catalog, leg: RatedLeg, floor: number): RatedLeg | null {
  if (leg.market === "atd" || leg.threshold === null) return null;
  const lower = catalog.legs
    .filter((l) => l.player === leg.player && l.market === leg.market && l.side === "over" && l.threshold !== null && l.threshold < (leg.threshold as number))
    .filter((l) => validRung(l.market, l.threshold) && l.prob >= floor)
    .sort((a, b) => (b.threshold as number) - (a.threshold as number));
  return lower[0] ?? null;
}

const unavailable = (injury: string | null | undefined) => !!injury && GRADE_CONFIG.outStatuses.some((x) => injury.toLowerCase().includes(x));

/**
 * One floor rung per player and market in the given games: the pool swaps and adds are drawn from.
 * Props only, and never a player who is out or whom the algorithm plays as a single only.
 */
function candidatePool(catalog: Catalog, games: Set<string>, floor: number): RatedLeg[] {
  const out: RatedLeg[] = [];
  const seen = new Set<string>();
  for (const l of catalog.legs) {
    if (!l.gameId || !games.has(l.gameId) || l.singlesOnly || l.market === "atd" || unavailable(l.injury)) continue;
    // NBA props tickets: four markets only, and never a rung the algorithm put a warning on
    if (catalog.sport === "NBA" && (!NBA_PROPS_RULES.markets.includes(l.market) || l.risk)) continue;
    const key = `${l.player}|${l.market}`;
    if (seen.has(key)) continue;
    seen.add(key);
    const rung = bandRung(catalog, l.player, l.market, floor);
    if (rung) out.push(rung);
  }
  return out;
}

export function suggestChanges(grade: SlipGrade, catalog: Catalog, prefs: Preferences = {}): Suggestions {
  const rules = TICKET_RULES[grade.sport];
  const original = grade.legs;
  const rated = ratedLegs(original);
  const canSimulate = !!catalog.corr && rated.every((l) => l.gameId && l.playerId);
  const joint = (legs: RatedLeg[], sims = SUGGEST_CONFIG.searchSims) => (canSimulate ? jointProbability(legs, catalog.corr, sims) : null);
  const notes: string[] = [];
  const remove: Removal[] = [];
  const swap: Swap[] = [];
  const add: Add[] = [];
  if (!rated.length) return { remove, swap, add, improved: null, notes: ["No leg on this slip is rated, so there is nothing to suggest."] };

  // working slip: the rated legs, each remembering its place on the original slip
  let work = original.map((l, index) => ({ index, leg: l.status === "rated" ? l.match : null, flags: l.flags, edge: l.edge })).filter((w) => w.leg) as
    { index: number; leg: RatedLeg; flags: SlipGrade["legs"][number]["flags"]; edge: number | null }[];
  const drop = (index: number) => { work = work.filter((w) => w.index !== index); };
  const multi = original.length > 1;

  // ---- 1. legs that cannot stay: out, singles-only, or the wrong kind of leg for the ticket
  const tdCount = work.filter((w) => w.leg.market === "atd").length;
  const propCount = work.length - tdCount;
  const minorityIsTd = grade.sport === "NFL" && tdCount > 0 && propCount > 0 && tdCount <= propCount;
  const minorityIsProp = grade.sport === "NFL" && tdCount > 0 && propCount > 0 && propCount < tdCount;
  const needReplacement: { index: number; leg: RatedLeg }[] = [];
  for (const w of [...work]) {
    let r: Removal | null = null;
    if (w.flags.includes("out")) r = { index: w.index, leg: w.leg, kind: "out", reason: `${w.leg.player} is listed ${w.leg.injury}. A player who is not confirmed to play cannot be on a ticket.` };
    else if (multi && w.leg.singlesOnly) r = { index: w.index, leg: w.leg, kind: "rule", reason: `The algorithm plays ${w.leg.player} as a single only this week, not as a parlay leg.` };
    else if (minorityIsTd && w.leg.market === "atd") r = { index: w.index, leg: w.leg, kind: "rule", reason: "A touchdown leg inside a props slip. Godseye keeps anytime-TD tickets separate from props tickets." };
    else if (minorityIsProp && w.leg.market !== "atd") r = { index: w.index, leg: w.leg, kind: "rule", reason: "A props leg inside an anytime-TD ticket. Godseye keeps the two kinds of ticket separate." };
    if (r) { remove.push(r); needReplacement.push({ index: w.index, leg: w.leg }); drop(w.index); }
  }

  // ---- 2. prop legs under the floor: a safer rung on the same player first
  if (multi)
    for (const w of [...work]) {
      if (w.leg.market === "atd" || w.leg.prob >= rules.floor) continue;
      const safer = saferRung(catalog, w.leg, rules.floor);
      if (safer) {
        swap.push({ index: w.index, from: w.leg, to: safer, kind: "safer-rung",
                    reason: `${legLabel(w.leg)} is ${pct(w.leg.prob)}, under the ${Math.round(rules.floor * 100)}% floor. ${safer.threshold}+ is ${pct(safer.prob)}.` });
        work = work.map((x) => (x.index === w.index ? { ...x, leg: safer, flags: x.flags.filter((f) => f !== "below-floor"), edge: null } : x));
      }
    }

  // ---- 3. negative-value legs and legs working against the rest (parlays only)
  if (multi)
    for (const w of [...work]) {
      if (work.length <= 1) break;
      const swapped = swap.some((s) => s.index === w.index);
      if (!swapped && w.edge !== null && w.edge < GRADE_CONFIG.negativeEdge) {
        remove.push({ index: w.index, leg: w.leg, kind: "negative-value", reason: `${legLabel(w.leg)}: the algorithm makes it ${pct(w.leg.prob)}, ${Math.abs(w.edge * 100).toFixed(1)} points less than its price implies.` });
        needReplacement.push({ index: w.index, leg: w.leg }); drop(w.index);
      } else if (!swapped && w.flags.includes("fights-script") && canSimulate) {
        const withLeg = joint(work.map((x) => x.leg));
        const without = joint(work.filter((x) => x.index !== w.index).map((x) => x.leg));
        if (withLeg !== null && without !== null && without > withLeg) {
          remove.push({ index: w.index, leg: w.leg, kind: "fights-script", reason: `${legLabel(w.leg)} works against your other legs in the same game: when they hit, it is less likely to.` });
          needReplacement.push({ index: w.index, leg: w.leg }); drop(w.index);
        }
      }
    }

  // ---- 4. still more than the allowed number of weak legs: drop the weakest
  if (multi && rules.weak !== null && rules.maxWeak !== null) {
    const weak = work.filter((w) => w.leg.market !== "atd" && w.leg.prob < rules.weak!).sort((a, b) => a.leg.prob - b.leg.prob);
    for (const w of weak.slice(0, Math.max(0, weak.length - rules.maxWeak))) {
      remove.push({ index: w.index, leg: w.leg, kind: "weak", reason: `${legLabel(w.leg)} is ${pct(w.leg.prob)} and the algorithm rates no safer rung for it. Godseye allows at most ${rules.maxWeak} leg under ${Math.round(rules.weak * 100)}%.` });
      needReplacement.push({ index: w.index, leg: w.leg }); drop(w.index);
    }
  }

  // ---- 5. replacements and adds, from either team, to reach the leg count the user wants
  const ratedTarget = Math.min(SUGGEST_CONFIG.maxLegs, Math.max(0, (prefs.legCount ?? original.length) - grade.unrated));
  const isPropsSlip = work.every((w) => w.leg.market !== "atd");
  if (canSimulate && isPropsSlip && work.length < ratedTarget) {
    const games = new Set(rated.map((l) => l.gameId as string));
    let pool = candidatePool(catalog, games, rules.floor);
    while (work.length < ratedTarget) {
      const current = work.map((w) => w.leg);
      pool = pool.filter((c) => !current.some((l) => l.player === c.player && l.market === c.market));
      if (grade.sport === "NBA") pool = pool.filter((c) => nbaFits(current, c, ratedTarget));
      let best: { leg: RatedLeg; p: number } | null = null;
      for (const c of pool) {
        const p = joint([...current, c]);
        if (p !== null && (!best || p > best.p)) best = { leg: c, p };
      }
      if (!best) break;
      const replaced = needReplacement.shift();
      if (replaced) {
        swap.push({ index: replaced.index, from: replaced.leg, to: best.leg, kind: "stronger-leg",
                    reason: `In place of ${legLabel(replaced.leg)}: ${legLabel(best.leg)} is ${pct(best.leg.prob)} and fits your other legs best of the floor rungs in the game.` });
        const i = remove.findIndex((r) => r.index === replaced.index);
        if (i >= 0) remove.splice(i, 1);
        work.push({ index: replaced.index, leg: best.leg, flags: [], edge: null });
      } else {
        add.push({ leg: best.leg, reason: `${legLabel(best.leg)} is ${pct(best.leg.prob)} and lowers the slip's chance least of the floor rungs in the game.` });
        work.push({ index: original.length + add.length, leg: best.leg, flags: [], edge: null });
      }
    }
    if (work.length < ratedTarget) notes.push("The algorithm has no more floor rungs in these games that pass the ticket rules, so the slip stays shorter than you asked for.");
  } else if (work.length < ratedTarget) {
    notes.push(
      !canSimulate ? `Replacement legs and adds need the ${grade.sport} algorithm's correlations, which its output does not carry yet.`
      : "Replacement legs are suggested for props slips only.");
  }

  // ---- 6. a leg still flagged (under the floor with no safer rung, working against the rest, or questionable):
  //         one stronger leg at the same position, if it lifts the slip's chance. A clean leg is never second-guessed.
  if (canSimulate && isPropsSlip && multi && work.length > 1) {
    const games = new Set(work.map((w) => w.leg.gameId as string));
    const pool = candidatePool(catalog, games, rules.floor);
    const base = joint(work.map((w) => w.leg)) as number;
    let best: { index: number; to: RatedLeg; p: number } | null = null;
    for (const w of work) {
      if (swap.some((s) => s.index === w.index) || w.index >= original.length) continue;
      const flagged = w.flags.includes("fights-script") || w.flags.includes("questionable") || (w.leg.market !== "atd" && w.leg.prob < rules.floor);
      if (!flagged) continue;
      for (const c of pool) {
        if (c.market !== w.leg.market || c.pos !== w.leg.pos || work.some((x) => x.leg.player === c.player && x.leg.market === c.market)) continue;
        if (grade.sport === "NBA" && !nbaFits(work.filter((x) => x.index !== w.index).map((x) => x.leg), c, work.length)) continue;
        const p = joint(work.map((x) => (x.index === w.index ? c : x.leg))) as number;
        if (p > base + SUGGEST_CONFIG.minSwapGain && (!best || p > best.p)) best = { index: w.index, to: c, p };
      }
    }
    if (best) {
      const from = work.find((w) => w.index === best!.index)!.leg;
      swap.push({ index: best.index, from, to: best.to, kind: "stronger-leg",
                  reason: `${legLabel(best.to)} (${pct(best.to.prob)}) fits your other legs better than ${legLabel(from)} (${pct(from.prob)}).` });
      work = work.map((w) => (w.index === best!.index ? { ...w, leg: best!.to } : w));
    }
  }

  const changed = remove.length + swap.length + add.length > 0;
  if (changed) notes.push("Swaps and adds use rungs from the algorithm's ladder. Check your book lists the rung, then type the new price to see the slip's value and a stake.");
  if (prefs.book) notes.push(`Prices are yours to read from ${prefs.book}: the algorithm has no price feed for it.`);
  if (!changed) return { remove, swap, add, improved: null, notes: notes.length ? notes : ["Nothing to change: the slip passes the ticket rules and no leg is working against the others."] };

  work.sort((a, b) => a.index - b.index);
  const finalLegs = work.map((w) => w.leg);
  // guard: never hand back the same leg twice
  const unique = finalLegs.filter((l, i) => finalLegs.findIndex((o) => same(o, l)) === i);
  const p = canSimulate ? jointProbability(unique, catalog.corr) : unique.length === 1 ? unique[0].prob : null;
  const unratedKept = original.filter((l) => l.status !== "rated").map((l) => l.text);
  return {
    remove, swap, add, notes,
    improved: {
      legs: unique, unratedKept, joint: p, fairOdds: p === null ? null : fairAmerican(p), rules: ruleCheck(grade.sport, unique, unratedKept.length),
      note: p === null ? "The improved slip's chance is not stated: the algorithm's output does not carry the correlations for it."
        : unique.length !== rated.length ? "Fewer or more legs than your slip, so the two chances are not like for like: fewer legs always hit more often and pay less."
        : "Same number of rated legs as your slip.",
    },
  };
}
