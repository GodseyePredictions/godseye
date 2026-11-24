/**
 * The chance that every leg of a slip hits, from the NFL algorithm's own numbers.
 *
 * This is the console's correlation engine (public/console/app.js, `rho` and `jointPN`) moved here so the
 * server, the chat advisor and the site all run one copy. It does not invent anything: each leg's chance
 * is the algorithm's, and how legs move together comes from the correlation tables the algorithm fitted
 * on past games and ships with its weekly output. Legs in different games are independent.
 *
 * Method: a Gaussian copula. Within a game, draw correlated normal variables and count the share of
 * draws in which every leg clears its threshold. Legs are never multiplied as if unrelated.
 */
import type { NflCorr, RatedLeg } from "./legs.ts";

export const DEFAULT_SIMS = 60_000;
/** Two rungs of one market for one player rise and fall together almost perfectly. */
const SAME_MARKET_SELF = 0.95;

/** Inverse of the standard normal distribution function (Acklam's approximation). */
export function normInv(p: number): number {
  const a = [-39.69683028665376, 220.9460984245205, -275.9285104469687, 138.357751867269, -30.66479806614716, 2.506628277459239];
  const b = [-54.47609879822406, 161.5858368580409, -155.6989798598866, 66.80131188771542, -13.28068155288572];
  const c = [-0.007784894002430293, -0.3223964580411365, -2.400758277161838, -2.549732539343734, 4.374664141464968, 2.938163982698783];
  const d = [0.007784695709041462, 0.3224671290700398, 2.445134137142996, 3.754408661907416];
  const pl = 0.02425;
  if (p < pl) {
    const q = Math.sqrt(-2 * Math.log(p));
    return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
  }
  if (p > 1 - pl) {
    const q = Math.sqrt(-2 * Math.log(1 - p));
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
  }
  const q = p - 0.5;
  const r = q * q;
  return ((((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q) / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
}

/** A small seeded generator, so the same slip always gets the same answer. */
function rng(seed: number) {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function cholesky(S: number[][]): number[][] | null {
  const n = S.length;
  const L = S.map(() => Array<number>(n).fill(0));
  for (let i = 0; i < n; i++)
    for (let j = 0; j <= i; j++) {
      let s = S[i][j];
      for (let k = 0; k < j; k++) s -= L[i][k] * L[j][k];
      if (i === j) {
        if (s <= 1e-9) return null;
        L[i][i] = Math.sqrt(s);
      } else L[i][j] = s / L[j][j];
    }
  return L;
}

/** How two legs move together, from the algorithm's fitted tables. Different games: not at all. */
export function legCorrelation(a: RatedLeg, b: RatedLeg, corr: NflCorr): number {
  if (!a.gameId || a.gameId !== b.gameId) return 0;
  const rel = a.playerId === b.playerId ? "SELF" : a.team === b.team ? "TM" : "OPP";
  if (a.market === "atd" && b.market === "atd") {
    if (rel === "OPP") return corr.atd.OPP ?? 0.03;
    const k = "TM:" + [a.pos, b.pos].sort().join("-");
    return corr.atd[k] ?? corr.atd["TM:default"] ?? -0.04;
  }
  if (rel === "SELF" && a.market === b.market) return SAME_MARKET_SELF;
  const x = [`${a.market}@${a.pos}`, `${b.market}@${b.pos}`].sort();
  const k = `${rel}|${x[0]}|${x[1]}`;
  if (k in corr.legs) return corr.legs[k];
  return rel === "SELF" ? (corr.legs._rel?.SELF ?? 0.3) : 0;
}

/** The share of simulated games in which every one of these same-game legs hits. */
export function gameJoint(probs: number[], sigma: number[][], sims = DEFAULT_SIMS): number {
  const n = probs.length;
  if (n === 0) return 1;
  if (n === 1) return probs[0];
  let S = sigma;
  let C = cholesky(S);
  let shrink = 1;
  // a table of pairwise estimates is not always a valid correlation matrix; pull it toward independence until it is
  while (!C && shrink > 0.2) {
    shrink *= 0.9;
    S = S.map((row, i) => row.map((v, j) => (i === j ? 1 : v * 0.9)));
    C = cholesky(S);
  }
  if (!C) return probs.reduce((a, p) => a * p, 1);
  const t = probs.map(normInv);
  const R = rng(1234 + n * 7);
  let hit = 0;
  const z = new Array<number>(n);
  for (let s = 0; s < sims; s++) {
    for (let i = 0; i < n; i++) {
      const u1 = R() || 1e-12;
      const u2 = R();
      z[i] = Math.sqrt(-2 * Math.log(u1)) * Math.cos(6.283185307179586 * u2);
    }
    let ok = true;
    for (let i = 0; i < n && ok; i++) {
      let x = 0;
      for (let k = 0; k <= i; k++) x += C[i][k] * z[k];
      if (x >= t[i]) ok = false;
    }
    if (ok) hit++;
  }
  return hit / sims;
}

/**
 * The chance every leg hits. Null when it cannot be worked out from the algorithm's output:
 * no legs, or legs without the ids and correlation tables the engine needs (NBA today).
 */
export function jointProbability(legs: RatedLeg[], corr: NflCorr | undefined, sims = DEFAULT_SIMS): number | null {
  if (!legs.length) return null;
  if (legs.length === 1) return legs[0].prob;
  if (!corr || legs.some((l) => !l.gameId || !l.playerId)) return null;
  const byGame = new Map<string, RatedLeg[]>();
  for (const l of legs) byGame.set(l.gameId!, [...(byGame.get(l.gameId!) ?? []), l]);
  let out = 1;
  for (const group of byGame.values()) {
    const sigma = group.map((a, i) => group.map((b, j) => (i === j ? 1 : legCorrelation(a, b, corr))));
    out *= gameJoint(group.map((l) => l.prob), sigma, sims);
  }
  return out;
}

/** American odds at which a bet with this chance breaks even. */
export function fairAmerican(p: number): number | null {
  if (!(p > 0 && p < 1)) return null;
  return p >= 0.5 ? Math.round((-100 * p) / (1 - p)) : Math.round((100 * (1 - p)) / p);
}
