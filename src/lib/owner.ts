/**
 * The owner's private summary: subscribers, advisor usage and cost, and the algorithm's full record.
 *
 * Results are never shown to the public (only winning slips, on the Cashed slips tab). This summary
 * includes the full record, so it is served only to a caller holding OWNER_KEY.
 */
import { createHash, timingSafeEqual } from "node:crypto";
import { effectiveTier } from "./advisor/subscription.ts";
import { usageTotals } from "./advisor/usage.ts";
import { bettingDay } from "./staking.ts";
import type { Tier, UserStore } from "./store/types.ts";

export const OWNER_CONFIG = {
  /** A shorter key is refused, so a weak one cannot be set by accident. */
  minKeyLength: 24,
  /** Most expensive users listed. */
  topUsers: 50,
};

type Env = Record<string, string | undefined>;

/** "ok", or why not. The comparison takes the same time whatever was sent. */
export function ownerAccess(authorization: string | null, env: Env = process.env): "ok" | "not-set-up" | "denied" {
  const key = env.OWNER_KEY ?? "";
  if (key.length < OWNER_CONFIG.minKeyLength) return "not-set-up";
  const given = /^Bearer\s+(.+)$/i.exec(authorization ?? "")?.[1] ?? "";
  const hash = (s: string) => createHash("sha256").update(s).digest();
  return timingSafeEqual(hash(given), hash(key)) ? "ok" : "denied";
}

/** The full record behind the Cashed slips tab (model/nba/output/nba_cashed.json). */
export type RecordFile = { from?: string; to?: string; issued?: number; cashed?: number; all_staked?: number; all_net?: number; stake_rule?: unknown };

export type OwnerSummary = {
  at: string;
  users: { total: number; byPlan: Record<Tier, number>; pastDue: number; canceled: number; withBankroll: number };
  advisor: {
    messagesToday: number;
    cost: { last7Days: number; last30Days: number; allTime: number };
    calls: { last7Days: number; last30Days: number; allTime: number };
    unpricedCalls: number;
    top: { user: string; plan: Tier; status: string; calls30: number; cost30: number; costAll: number; messagesToday: number }[];
  };
  nba: null | { from: string | null; to: string | null; issued: number; cashed: number; lost: number; hitRate: number | null; exampleStaked: number; exampleNet: number };
};

const round = (x: number, places: number) => Math.round(x * 10 ** places) / 10 ** places;

export async function ownerSummary(store: UserStore, now: Date, record: RecordFile | null): Promise<OwnerSummary> {
  const d7 = new Date(now.getTime() - 7 * 86_400_000);
  const d30 = new Date(now.getTime() - 30 * 86_400_000);
  const today = bettingDay(now);
  const s: OwnerSummary = {
    at: now.toISOString(),
    users: { total: 0, byPlan: { none: 0, pro: 0, elite: 0 }, pastDue: 0, canceled: 0, withBankroll: 0 },
    advisor: { messagesToday: 0, cost: { last7Days: 0, last30Days: 0, allTime: 0 }, calls: { last7Days: 0, last30Days: 0, allTime: 0 }, unpricedCalls: 0, top: [] },
    nba: null,
  };
  for (const id of await store.list()) {
    const u = await store.get(id);
    // the plan as paid for: a local ADVISOR_DEV_TIER override is not a subscriber
    const plan = effectiveTier(u, {});
    s.users.total++;
    s.users.byPlan[plan]++;
    if (u.subscription.status === "past_due") s.users.pastDue++;
    if (u.subscription.status === "canceled") s.users.canceled++;
    if (u.account) s.users.withBankroll++;
    const messagesToday = u.messageLog.filter((t) => bettingDay(new Date(t)) === today).length;
    const all = usageTotals(u), m = usageTotals(u, d30), w = usageTotals(u, d7);
    s.advisor.messagesToday += messagesToday;
    s.advisor.cost.allTime += all.costUsd; s.advisor.cost.last30Days += m.costUsd; s.advisor.cost.last7Days += w.costUsd;
    s.advisor.calls.allTime += all.calls; s.advisor.calls.last30Days += m.calls; s.advisor.calls.last7Days += w.calls;
    s.advisor.unpricedCalls += all.unpricedCalls;
    if (all.calls || messagesToday) s.advisor.top.push({ user: id, plan, status: u.subscription.status, calls30: m.calls, cost30: m.costUsd, costAll: all.costUsd, messagesToday });
  }
  for (const k of ["last7Days", "last30Days", "allTime"] as const) s.advisor.cost[k] = round(s.advisor.cost[k], 4);
  s.advisor.top.sort((a, b) => b.cost30 - a.cost30 || b.costAll - a.costAll || a.user.localeCompare(b.user));
  s.advisor.top = s.advisor.top.slice(0, OWNER_CONFIG.topUsers);

  if (record && typeof record.issued === "number" && typeof record.cashed === "number") {
    s.nba = {
      from: record.from ?? null, to: record.to ?? null, issued: record.issued, cashed: record.cashed, lost: record.issued - record.cashed,
      hitRate: record.issued > 0 ? round(record.cashed / record.issued, 4) : null,
      exampleStaked: record.all_staked ?? 0, exampleNet: record.all_net ?? 0,
    };
  }
  return s;
}
