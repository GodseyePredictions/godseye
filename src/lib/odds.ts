/**
 * Odds maths used by the advisor and the reports.
 * All odds in are American (-110, +250). Probabilities are 0..1.
 */

/** Total returned per $1 staked, including the stake. */
export function toDecimal(american: number): number {
  if (american === 0 || !Number.isFinite(american)) throw new Error("Invalid American odds");
  return american > 0 ? 1 + american / 100 : 1 + 100 / -american;
}

/** Win chance the price implies, bookmaker margin included. */
export function impliedProb(american: number): number {
  return 1 / toDecimal(american);
}

/**
 * Remove the bookmaker's margin from a full market (every outcome listed)
 * to get fair probabilities that sum to 1.
 */
export function fairProbs(americanPrices: number[]): number[] {
  const raw = americanPrices.map(impliedProb);
  const total = raw.reduce((a, b) => a + b, 0);
  return raw.map((p) => p / total);
}

/** Bookmaker margin on a full market, e.g. 0.045 for a -110/-110 line. */
export function hold(americanPrices: number[]): number {
  const total = americanPrices.map(impliedProb).reduce((a, b) => a + b, 0);
  return 1 - 1 / total;
}

/** Combined decimal price of a parlay, assuming the legs are unrelated. */
export function parlayDecimal(legs: number[]): number {
  return legs.map(toDecimal).reduce((a, b) => a * b, 1);
}

/** Profit if a bet wins. */
export function profit(stake: number, decimal: number): number {
  return stake * (decimal - 1);
}

/** Expected profit per $1 staked, given your estimate of the true win chance. */
export function expectedValue(trueProb: number, american: number): number {
  return trueProb * (toDecimal(american) - 1) - (1 - trueProb);
}

/**
 * Share of bankroll the Kelly rule suggests, scaled by `fraction`
 * (0.25 = quarter Kelly, a common cautious setting). Never negative.
 */
export function kellyStake(trueProb: number, american: number, fraction = 0.25): number {
  const b = toDecimal(american) - 1;
  const full = (trueProb * b - (1 - trueProb)) / b;
  return Math.max(0, full * fraction);
}

/**
 * How much better or worse your price was than the closing price,
 * as a change in implied win chance. Positive means you beat the close.
 */
export function closingLineValue(betAmerican: number, closeAmerican: number): number {
  return impliedProb(closeAmerican) - impliedProb(betAmerican);
}
