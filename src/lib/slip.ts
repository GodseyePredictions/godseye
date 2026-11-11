import { impliedProb } from "./odds.ts";
import { betDecimal, type Leg } from "./bets.ts";

export type Finding = {
  level: "warn" | "info";
  title: string;
  detail: string;
};

/** A two-way market at typical prices carries about this much bookmaker margin per leg. */
const TYPICAL_MARGIN_PER_LEG = 0.045;

const pct = (p: number) => `${(p * 100).toFixed(1)}%`;

/** Rule-based review of a slip. No predictions: only what the prices themselves say. */
export function checkSlip(legs: Leg[], stake: number) {
  const findings: Finding[] = [];
  if (!legs.length) return { findings, decimal: 0, toWin: 0, impliedChance: 0 };

  const decimal = betDecimal({ legs });
  const impliedChance = legs.reduce((p, l) => p * impliedProb(l.odds), 1);

  // Legs from the same game
  const byGame = new Map<string, number[]>();
  legs.forEach((l, i) => {
    const g = l.game?.trim().toLowerCase();
    if (g) byGame.set(g, [...(byGame.get(g) ?? []), i]);
  });
  for (const idx of byGame.values()) {
    if (idx.length > 1) {
      findings.push({
        level: "warn",
        title: `Legs ${idx.map((i) => i + 1).join(" and ")} are from the same game`,
        detail:
          "Results in one game move together, so your book will price this as a same-game parlay, usually at a worse payout than the figure shown here.",
      });
    }
  }

  if (legs.length > 1) {
    // Heavy favourites that add little
    legs.forEach((l, i) => {
      if (l.odds <= -250) {
        const without = betDecimal({ legs: legs.filter((_, j) => j !== i) });
        const extra = stake * (decimal - without);
        findings.push({
          level: "warn",
          title: `Leg ${i + 1} adds little`,
          detail: `It raises the payout by $${extra.toFixed(2)}, but by its own price it still loses about ${pct(1 - impliedProb(l.odds))} of the time, and one loss sinks the whole parlay.`,
        });
      }
    });

    // Margin compounding
    const cost = 1 - Math.pow(1 - TYPICAL_MARGIN_PER_LEG, legs.length);
    findings.push({
      level: legs.length >= 4 ? "warn" : "info",
      title: `The book's margin stacks across ${legs.length} legs`,
      detail: `Each leg carries the book's margin, and a parlay multiplies them. At typical pricing that is roughly ${pct(cost)} of your stake given up before the games start, against about ${pct(TYPICAL_MARGIN_PER_LEG)} on a single. This is an estimate, not your book's exact figure.`,
    });
  }

  // Long shots
  legs.forEach((l, i) => {
    if (l.odds >= 400) {
      findings.push({
        level: "info",
        title: `Leg ${i + 1} is a long shot`,
        detail: `Its price implies it wins about ${pct(impliedProb(l.odds))} of the time, and the true chance is lower once the book's margin is removed.`,
      });
    }
  });

  findings.push({
    level: "info",
    title: "What the prices say about your chances",
    detail: `Taken at face value, the prices imply this slip wins about ${pct(impliedChance)} of the time. The true chance is lower, because every price includes the book's margin.`,
  });

  return { findings, decimal, toWin: stake * (decimal - 1), impliedChance };
}
