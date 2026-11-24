/**
 * Subscription status, message caps and what happens to a user's history when they cancel and return.
 *
 * Nothing here talks to a payment provider. A provider's webhook handler calls `applySubscriptionEvent`
 * with what changed, and the chat calls `chatAllowance` before answering. Every limit is in ADVISOR_LIMITS.
 */
import { bettingDay } from "../staking.ts";
import type { Subscription, Tier, UserRecord } from "../store/types.ts";

export const ADVISOR_LIMITS = {
  /** Chat messages a user may send per day. Null means no cap. */
  dailyMessages: { none: 0, pro: 20, elite: null } as Record<Tier, number | null>,
  /** After a cancel, history is held this many days for a possible return, then deleted. */
  archiveDays: 90,
  /** Timestamps kept for counting the daily cap. */
  messageLogKeep: 400,
};

const TIERS: Tier[] = ["none", "pro", "elite"];

/**
 * The tier a user chats on. Until a payment provider is connected nobody has a paid subscription,
 * so ADVISOR_DEV_TIER (pro or elite) grants that tier to everyone: for local use and demos only.
 */
export function effectiveTier(user: Pick<UserRecord, "subscription">, env: Record<string, string | undefined> = process.env): Tier {
  const s = user.subscription;
  if (s.status === "active" || s.status === "past_due") return s.tier;
  const dev = env.ADVISOR_DEV_TIER as Tier | undefined;
  return dev && TIERS.includes(dev) && dev !== "none" ? dev : "none";
}

export type Allowance =
  | { ok: true; tier: Tier; usedToday: number; cap: number | null; remaining: number | null }
  | { ok: false; tier: Tier; reason: "no-subscription" | "daily-cap"; message: string; usedToday: number; cap: number | null };

/** Whether this user may send a chat message now. Called before the model is. */
export function chatAllowance(user: UserRecord, now: Date, env: Record<string, string | undefined> = process.env): Allowance {
  const tier = effectiveTier(user, env);
  const day = bettingDay(now);
  const usedToday = user.messageLog.filter((t) => bettingDay(new Date(t)) === day).length;
  const cap = ADVISOR_LIMITS.dailyMessages[tier];
  if (tier === "none")
    return { ok: false, tier, reason: "no-subscription", usedToday, cap,
             message: user.subscription.status === "canceled" ? "Your subscription has ended. Resubscribe to pick up where you left off: your history is being kept for you."
               : "The advisor is part of a Godseye subscription." };
  if (cap !== null && usedToday >= cap)
    return { ok: false, tier, reason: "daily-cap", usedToday, cap,
             message: `You have used all ${cap} of today's advisor messages on the ${tier === "pro" ? "Pro" : "Elite"} plan. They reset in the morning.` };
  return { ok: true, tier, usedToday, cap, remaining: cap === null ? null : cap - usedToday };
}

/** Count one message against today's cap. */
export function recordMessage(user: UserRecord, now: Date): void {
  user.messageLog = [...user.messageLog, now.toISOString()].slice(-ADVISOR_LIMITS.messageLogKeep);
}

export type SubscriptionEvent = { tier: Tier; status: Subscription["status"]; currentPeriodEnd?: string | null };

/**
 * Apply a change of subscription, as reported by the payment provider.
 * Cancel: history is archived (kept but hidden) for ADVISOR_LIMITS.archiveDays.
 * Return within that time: history comes back. Return after it: they start fresh.
 */
export function applySubscriptionEvent(user: UserRecord, event: SubscriptionEvent, now: Date): void {
  purgeExpiredArchive(user, now);
  const wasActive = user.subscription.status === "active" || user.subscription.status === "past_due";
  const isActive = event.status === "active" || event.status === "past_due";
  if (!isActive && event.status === "canceled") {
    const until = new Date(now.getTime() + ADVISOR_LIMITS.archiveDays * 86_400_000).toISOString();
    for (const c of user.conversations) c.archived = true;
    user.subscription = { tier: "none", status: "canceled", currentPeriodEnd: event.currentPeriodEnd ?? null, canceledAt: wasActive || !user.subscription.canceledAt ? now.toISOString() : user.subscription.canceledAt, archivedUntil: until };
    return;
  }
  if (isActive) {
    for (const c of user.conversations) c.archived = false; // anything still held is restored
    user.subscription = { tier: event.tier, status: event.status, currentPeriodEnd: event.currentPeriodEnd ?? null, canceledAt: null, archivedUntil: null };
    return;
  }
  user.subscription = { tier: "none", status: event.status, currentPeriodEnd: event.currentPeriodEnd ?? null };
}

/** Delete archived history whose holding period has run out. Safe to call on every request. */
export function purgeExpiredArchive(user: UserRecord, now: Date): boolean {
  const until = user.subscription.archivedUntil;
  if (!until || new Date(until).getTime() > now.getTime()) return false;
  user.conversations = user.conversations.filter((c) => !c.archived);
  user.profile = { ...user.profile, summary: "", summaryUpdatedAt: null };
  user.subscription = { ...user.subscription, archivedUntil: null };
  return true;
}

/** The conversations a user can see: archived ones are hidden while they are held. */
export const visibleConversations = (user: UserRecord) => user.conversations.filter((c) => !c.archived);
