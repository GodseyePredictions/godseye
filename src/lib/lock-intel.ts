/**
 * The reasoning behind an NBA slip, in the algorithm's own words and numbers.
 *
 * Nothing is worked out here: the game read comes from the game simulation's card (pace, total, margin,
 * blowout and close-game chances, the likeliest scripts) and each leg's reason is the itemised list of
 * adjustments the algorithm attached to it. This only chooses what to print and rounds it.
 */
type Card = {
  matchup?: string; pace?: { ours?: number }; total?: { simulated?: number; market?: number }; margin_home?: { simulated?: number };
  win_prob_home?: number; blowout_prob?: number; close_prob?: number; blowout_warning?: string | boolean | null;
  scripts?: { script?: string; probability?: number; who?: string }[];
};
type Leg = { label?: string; reason?: string | null; p_blowout?: number | null; p_close?: number | null };
type Game = { home: string; away: string; preview?: boolean; card?: Card; tickets?: { legs: Leg[] }[]; singles?: Leg[] };

export type SlipWhy = { intel: string[]; legs: Record<string, string[]> };

export const LOCK_INTEL = { scripts: 2 };
const pc = (x: number) => `${Math.round(x * 100)}%`;
const one = (x: number) => (Math.round(x * 10) / 10).toFixed(1);

export function nbaWhy(data: unknown, game: string): SlipWhy | null {
  const g = (data as { games?: Game[] }).games?.find((x) => !x.preview && `${x.away} @ ${x.home}` === game);
  if (!g) return null;
  const c = g.card ?? {};
  const intel: string[] = [];
  const m = c.margin_home?.simulated;
  if (typeof m === "number" && typeof c.win_prob_home === "number") {
    const fav = m >= 0 ? g.home : g.away;
    intel.push(`Simulated result: ${fav} by ${one(Math.abs(m))}; ${g.home} win ${pc(c.win_prob_home)} of simulations.`);
  }
  if (typeof c.total?.simulated === "number")
    intel.push(`Simulated total ${one(c.total.simulated)}${typeof c.total.market === "number" ? ` (book ${c.total.market})` : ""}${typeof c.pace?.ours === "number" ? `; pace ${one(c.pace.ours)} possessions` : ""}.`);
  if (typeof c.blowout_prob === "number" && typeof c.close_prob === "number")
    intel.push(`Blowout risk ${pc(c.blowout_prob)}; close finish ${pc(c.close_prob)}.`);
  if (typeof c.blowout_warning === "string" && c.blowout_warning.trim()) intel.push(c.blowout_warning.trim());
  else if (c.blowout_warning === true) intel.push("The algorithm flags this game for blowout risk: starters may sit late.");
  for (const s of (c.scripts ?? []).filter((x) => x.script && typeof x.probability === "number").slice(0, LOCK_INTEL.scripts))
    intel.push(`${pc(s.probability as number)}: ${s.script}${s.who ? ` (${s.who})` : ""}.`);

  const legs: Record<string, string[]> = {};
  for (const l of [...(g.tickets ?? []).flatMap((t) => t.legs), ...(g.singles ?? [])]) {
    if (!l.label || legs[l.label]) continue;
    const why = (l.reason ?? "").split(";").map((x) => x.trim()).filter(Boolean);
    if (typeof l.p_blowout === "number" && typeof l.p_close === "number") why.push(`hits ${pc(l.p_close)} in close games, ${pc(l.p_blowout)} in blowouts`);
    if (why.length) legs[l.label] = why;
  }
  return { intel: intel.filter((x) => x.trim()), legs };
}

// ---------- NHL ----------
type NhlLeg = { label?: string; prob?: number; why?: string[] };
type NhlTicket = { id?: string; title?: string; chance?: number; miss?: number; fair_price?: number | null; legs?: NhlLeg[] };
type NhlGame = { label?: string; start_utc?: string; made_after_start?: boolean; notes?: string[]; tickets?: NhlTicket[] };
export type NhlLock = {
  id: string; game: string; title: string; chance: number; miss: number; fairPrice: number | null;
  legs: { text: string; prob: number; why: string[] }[]; notes: string[];
};

export const NHL_LOCKS = { best: 3, whyPerLeg: 4, notes: 3 };

/**
 * The NHL algorithm's highest-chance slip in each game, best first, for the home page.
 * The chance is the algorithm's own; this only ranks by it. A slip made after puck drop is never shown.
 */
export function nhlTopSlips(data: unknown, limit = NHL_LOCKS.best): NhlLock[] {
  const games = (data as { games?: NhlGame[] }).games ?? [];
  const out: NhlLock[] = [];
  for (const g of games) {
    if (g.made_after_start || !g.label) continue;
    let top: NhlTicket | null = null;
    for (const t of g.tickets ?? [])
      if (typeof t.chance === "number" && (t.legs?.length ?? 0) > 0 && (!top || t.chance > (top.chance as number))) top = t;
    if (!top) continue;
    out.push({
      id: top.id ?? `${g.label}-${top.title}`, game: g.label, title: top.title ?? "Slip", chance: top.chance as number,
      miss: typeof top.miss === "number" ? top.miss : 1 - (top.chance as number), fairPrice: top.fair_price ?? null,
      legs: (top.legs ?? []).filter((l) => l.label && typeof l.prob === "number")
        .map((l) => ({ text: l.label as string, prob: l.prob as number, why: (l.why ?? []).slice(0, NHL_LOCKS.whyPerLeg) })),
      notes: (g.notes ?? []).slice(0, NHL_LOCKS.notes),
    });
  }
  return out.sort((a, b) => b.chance - a.chance).slice(0, limit);
}
