import { parlayDecimal, toDecimal, impliedProb } from "./odds.ts";

export type Leg = { description: string; odds: number; game?: string };
export type Status = "open" | "won" | "lost" | "push";
export type Bet = {
  id: string;
  placedAt: string; // ISO date
  sport: string;
  book: string;
  legs: Leg[];
  stake: number;
  status: Status;
  closingOdds?: number; // singles only
};

export function betDecimal(bet: Pick<Bet, "legs">): number {
  return bet.legs.length === 1
    ? toDecimal(bet.legs[0].odds)
    : parlayDecimal(bet.legs.map((l) => l.odds));
}

export function decimalToAmerican(d: number): number {
  return d >= 2 ? Math.round((d - 1) * 100) : Math.round(-100 / (d - 1));
}

export function formatAmerican(a: number): string {
  return a > 0 ? `+${a}` : `−${Math.abs(a)}`;
}

/** Profit or loss of a settled bet; 0 for open bets and pushes. */
export function betProfit(bet: Bet): number {
  if (bet.status === "won") return bet.stake * (betDecimal(bet) - 1);
  if (bet.status === "lost") return -bet.stake;
  return 0;
}

export function betType(bet: Pick<Bet, "legs">): string {
  const n = bet.legs.length;
  if (n === 1) return "Singles";
  if (n === 2) return "2-leg parlays";
  if (n === 3) return "3-leg parlays";
  return "4+ leg parlays";
}

export type Summary = {
  label: string;
  bets: number;
  won: number;
  lost: number;
  push: number;
  staked: number;
  profit: number;
  roi: number | null; // null until something has settled
};

export function summarize(label: string, bets: Bet[]): Summary {
  const settled = bets.filter((b) => b.status === "won" || b.status === "lost");
  const staked = settled.reduce((s, b) => s + b.stake, 0);
  const profit = settled.reduce((s, b) => s + betProfit(b), 0);
  return {
    label,
    bets: bets.length,
    won: bets.filter((b) => b.status === "won").length,
    lost: bets.filter((b) => b.status === "lost").length,
    push: bets.filter((b) => b.status === "push").length,
    staked,
    profit,
    roi: staked > 0 ? profit / staked : null,
  };
}

export function groupBy(bets: Bet[], key: (b: Bet) => string): Summary[] {
  const groups = new Map<string, Bet[]>();
  for (const b of bets) {
    const k = key(b) || "Not set";
    groups.set(k, [...(groups.get(k) ?? []), b]);
  }
  return [...groups.entries()].map(([k, v]) => summarize(k, v));
}

/** Average closing line value across singles that have a closing price. */
export function averageClv(bets: Bet[]): number | null {
  const withClose = bets.filter((b) => b.legs.length === 1 && b.closingOdds);
  if (!withClose.length) return null;
  const sum = withClose.reduce(
    (s, b) => s + impliedProb(b.closingOdds!) - impliedProb(b.legs[0].odds),
    0,
  );
  return sum / withClose.length;
}

/** Read legs from pasted text: one leg per line, American odds last. */
export function parseSlip(text: string): Leg[] {
  const legs: Leg[] = [];
  for (const raw of text.split("\n")) {
    const line = raw.replace(/−/g, "-").trim();
    if (!line) continue;
    const matches = [...line.matchAll(/(?:^|\s)([+-]\d{3,5})(?=\s|$)/g)];
    const last = matches.at(-1);
    if (!last) continue;
    const odds = Number(last[1]);
    const description = (
      line.slice(0, last.index) + line.slice(last.index! + last[0].length)
    ).trim();
    legs.push({ description: description || "Leg", odds });
  }
  return legs;
}
