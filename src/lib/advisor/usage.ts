/**
 * What each subscriber's use of the advisor costs in API fees.
 * Every model call's token counts are logged on the user's record, priced from the table below.
 */
import type { UsageEntry, UserRecord } from "../store/types.ts";

/** US dollars per million tokens. Update when prices change; unknown models are logged at zero cost and flagged. */
export const PRICES: Record<string, { input: number; output: number; cacheRead: number; cacheWrite: number }> = {
  "claude-sonnet-5-5": { input: 2, output: 10, cacheRead: 0.1, cacheWrite: 2.5 },
  "claude-opus-5-5": { input: 4, output: 20, cacheRead: 0.2, cacheWrite: 5 },
  "claude-haiku-5-5": { input: 0.1, output: 0.5, cacheRead: 0.01, cacheWrite: 0.125 },
};

export type TokenUsage = { inputTokens: number; outputTokens: number; cacheReadTokens: number; cacheWriteTokens: number };
export const NO_USAGE: TokenUsage = { inputTokens: 0, outputTokens: 0, cacheReadTokens: 0, cacheWriteTokens: 0 };

export function addUsage(a: TokenUsage, b: TokenUsage): TokenUsage {
  return {
    inputTokens: a.inputTokens + b.inputTokens, outputTokens: a.outputTokens + b.outputTokens,
    cacheReadTokens: a.cacheReadTokens + b.cacheReadTokens, cacheWriteTokens: a.cacheWriteTokens + b.cacheWriteTokens,
  };
}

export function costUsd(model: string, u: TokenUsage): number {
  const p = PRICES[model];
  if (!p) return 0;
  return (u.inputTokens * p.input + u.outputTokens * p.output + u.cacheReadTokens * p.cacheRead + u.cacheWriteTokens * p.cacheWrite) / 1_000_000;
}

const KEEP = 2000;

export function logUsage(user: UserRecord, model: string, purpose: UsageEntry["purpose"], u: TokenUsage, now: Date): void {
  if (u.inputTokens + u.outputTokens + u.cacheReadTokens + u.cacheWriteTokens === 0) return;
  user.usage = [...user.usage, { at: now.toISOString(), model, purpose, ...u, costUsd: Math.round(costUsd(model, u) * 1e6) / 1e6 }].slice(-KEEP);
}

export type UsageTotals = { calls: number; inputTokens: number; outputTokens: number; cacheReadTokens: number; cacheWriteTokens: number; costUsd: number; unpricedCalls: number };

/** Totals for one user, optionally since a given time. */
export function usageTotals(user: Pick<UserRecord, "usage">, since?: Date): UsageTotals {
  const t: UsageTotals = { calls: 0, inputTokens: 0, outputTokens: 0, cacheReadTokens: 0, cacheWriteTokens: 0, costUsd: 0, unpricedCalls: 0 };
  for (const e of user.usage) {
    if (since && new Date(e.at).getTime() < since.getTime()) continue;
    t.calls++;
    t.inputTokens += e.inputTokens; t.outputTokens += e.outputTokens; t.cacheReadTokens += e.cacheReadTokens; t.cacheWriteTokens += e.cacheWriteTokens;
    t.costUsd += e.costUsd;
    if (!PRICES[e.model]) t.unpricedCalls++;
  }
  t.costUsd = Math.round(t.costUsd * 1e4) / 1e4;
  return t;
}
