/**
 * Stripe subscription webhooks, turned into the app's own subscription events.
 *
 * Stripe calls POST /api/billing/webhook whenever a subscription starts, changes or ends. This file
 * proves the call is from Stripe (the signature), works out which user and which plan it is about,
 * and hands the result to applySubscriptionEvent, which does the gating, archiving and restoring.
 *
 * It needs three settings, all environment variables:
 *   STRIPE_WEBHOOK_SECRET   the signing secret of the webhook endpoint (whsec_...)
 *   STRIPE_PRICE_PRO        the price id(s) of the Pro plan, comma separated
 *   STRIPE_PRICE_ELITE      the price id(s) of the Elite plan, comma separated
 * and one thing at checkout: the subscription's metadata must carry `godseye_user`, the user's id.
 */
import { createHmac, timingSafeEqual } from "node:crypto";
import { applySubscriptionEvent, type SubscriptionEvent } from "../advisor/subscription.ts";
import { validUserId, type Subscription, type Tier, type UserStore } from "../store/types.ts";

export const BILLING_CONFIG = {
  /** A signed call older than this is refused, so a captured one cannot be replayed later. */
  toleranceSeconds: 300,
  userKey: "godseye_user",
};

export class BillingError extends Error {
  readonly status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

type Env = Record<string, string | undefined>;

/** Check the Stripe-Signature header against the exact bytes received. Throws unless it is genuine and recent. */
export function verifySignature(body: string, header: string | null, secret: string, now: Date): void {
  if (!header) throw new BillingError("The call is not signed.", 400);
  const parts = header.split(",").map((p) => p.trim().split("="));
  const t = parts.find(([k]) => k === "t")?.[1];
  const given = parts.filter(([k]) => k === "v1").map(([, v]) => v);
  if (!t || !/^\d+$/.test(t) || !given.length) throw new BillingError("The signature is malformed.", 400);
  const expected = createHmac("sha256", secret).update(`${t}.${body}`).digest();
  const ok = given.some((v) => {
    if (!/^[0-9a-f]{64}$/i.test(v ?? "")) return false;
    return timingSafeEqual(Buffer.from(v, "hex"), expected);
  });
  if (!ok) throw new BillingError("The signature does not match.", 400);
  if (Math.abs(now.getTime() / 1000 - Number(t)) > BILLING_CONFIG.toleranceSeconds) throw new BillingError("The call is too old.", 400);
}

/** Sign a body the way Stripe does. For tests and for sending a test call by hand. */
export function sign(body: string, secret: string, now: Date): string {
  const t = Math.floor(now.getTime() / 1000);
  return `t=${t},v1=${createHmac("sha256", secret).update(`${t}.${body}`).digest("hex")}`;
}

const STATUS: Record<string, Subscription["status"]> = {
  active: "active", trialing: "active",
  past_due: "past_due", unpaid: "past_due",
  canceled: "canceled", incomplete_expired: "canceled",
  incomplete: "none", paused: "none",
};

function priceIds(env: Env, key: string): string[] {
  return (env[key] ?? "").split(",").map((s) => s.trim()).filter(Boolean);
}

/** Which plan a Stripe price belongs to, from the environment. Null if it is not one of ours. */
export function tierForPrice(priceId: string | undefined, env: Env): Tier | null {
  if (!priceId) return null;
  if (priceIds(env, "STRIPE_PRICE_ELITE").includes(priceId)) return "elite";
  if (priceIds(env, "STRIPE_PRICE_PRO").includes(priceId)) return "pro";
  return null;
}

export type BillingChange = { userId: string; customerId: string | null; createdAt: string; event: SubscriptionEvent };

type StripeSubscription = {
  customer?: string | { id?: string }; status?: string; metadata?: Record<string, string>;
  current_period_end?: number;
  items?: { data?: { price?: { id?: string }; current_period_end?: number }[] };
};
type StripeEvent = { id?: string; type?: string; created?: number; data?: { object?: StripeSubscription } };

/**
 * What a Stripe event means for a user. Null for event types this app does not act on.
 * Throws if a subscription event cannot be tied to a user or a plan: those need a person to look.
 */
export function readEvent(raw: unknown, env: Env): BillingChange | null {
  const e = raw as StripeEvent;
  if (!e || typeof e.type !== "string" || !e.type.startsWith("customer.subscription.")) return null;
  if (!["customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"].includes(e.type)) return null;
  const sub = e.data?.object;
  if (!sub) throw new BillingError("The event carries no subscription.", 400);
  const userId = sub.metadata?.[BILLING_CONFIG.userKey];
  if (!validUserId(userId)) throw new BillingError(`The subscription has no valid ${BILLING_CONFIG.userKey} in its metadata.`, 422);

  const status = e.type === "customer.subscription.deleted" ? "canceled" : STATUS[sub.status ?? ""];
  if (!status) throw new BillingError(`Unknown subscription status "${sub.status}".`, 422);
  const item = sub.items?.data?.[0];
  const paying = status === "active" || status === "past_due";
  const tier = tierForPrice(item?.price?.id, env);
  if (paying && !tier) throw new BillingError(`Price "${item?.price?.id ?? ""}" is not listed in STRIPE_PRICE_PRO or STRIPE_PRICE_ELITE.`, 422);

  const end = item?.current_period_end ?? sub.current_period_end;
  const created = typeof e.created === "number" ? e.created : null;
  if (created == null) throw new BillingError("The event has no creation time.", 400);
  return {
    userId,
    customerId: typeof sub.customer === "string" ? sub.customer : (sub.customer?.id ?? null),
    createdAt: new Date(created * 1000).toISOString(),
    event: { tier: paying ? tier! : "none", status, currentPeriodEnd: typeof end === "number" ? new Date(end * 1000).toISOString() : null },
  };
}

export type WebhookResult = { handled: boolean; note: string };

/**
 * Handle one webhook call end to end. `body` must be the exact text received.
 * A call that is older than the last one applied for that user is acknowledged and ignored,
 * because Stripe does not promise to deliver events in order and may deliver one twice.
 */
export async function handleStripeWebhook(input: { body: string; signature: string | null; store: UserStore; env?: Env; now?: Date }): Promise<WebhookResult> {
  const env = input.env ?? process.env;
  const now = input.now ?? new Date();
  const secret = env.STRIPE_WEBHOOK_SECRET;
  if (!secret) throw new BillingError("Billing is not set up on this server.", 503);
  verifySignature(input.body, input.signature, secret, now);

  let parsed: unknown;
  try {
    parsed = JSON.parse(input.body);
  } catch {
    throw new BillingError("The body is not JSON.", 400);
  }
  const change = readEvent(parsed, env);
  if (!change) return { handled: false, note: "ignored: not a subscription event" };

  let note = "applied";
  await input.store.update(change.userId, (user) => {
    const last = user.subscription.lastEventAt;
    if (last && new Date(last).getTime() > new Date(change.createdAt).getTime()) {
      note = "ignored: a newer event was already applied";
      return;
    }
    applySubscriptionEvent(user, change.event, now);
    user.subscription.customerId = change.customerId ?? user.subscription.customerId ?? null;
    user.subscription.lastEventAt = change.createdAt;
  });
  return { handled: note === "applied", note };
}
