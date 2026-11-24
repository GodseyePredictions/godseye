import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import pg from "pg";
import { ADVISOR_LIMITS, chatAllowance, visibleConversations } from "./advisor/subscription.ts";
import { BILLING_CONFIG, BillingError, handleStripeWebhook, readEvent, sign, tierForPrice, verifySignature } from "./billing/stripe.ts";
import type { Bet } from "./bets.ts";
import { OWNER_CONFIG, ownerAccess, ownerSummary } from "./owner.ts";
import { openAccount } from "./staking.ts";
import { PgStore } from "./store/postgres.ts";
import { MemoryStore, type Conversation, type UserRecord } from "./store/types.ts";

const NOW = new Date("2026-11-25T23:00:00Z");
const SECRET = "whsec_test_only";
const ENV = { STRIPE_WEBHOOK_SECRET: SECRET, STRIPE_PRICE_PRO: "price_pro_m, price_pro_y", STRIPE_PRICE_ELITE: "price_elite_m" };
const USER = "user_bill_0001";

function subEvent(over: { type?: string; status?: string; price?: string; created?: number; user?: string | null; end?: number } = {}) {
  const created = over.created ?? Math.floor(NOW.getTime() / 1000);
  return {
    id: `evt_${created}`, type: over.type ?? "customer.subscription.updated", created,
    data: { object: {
      id: "sub_1", customer: "cus_123", status: over.status ?? "active",
      metadata: over.user === null ? {} : { [BILLING_CONFIG.userKey]: over.user ?? USER },
      items: { data: [{ price: { id: over.price ?? "price_pro_m" }, current_period_end: over.end ?? created + 30 * 86_400 }] },
    } },
  };
}
const send = (store: MemoryStore, event: unknown, now = NOW, signature?: string | null) => {
  const body = JSON.stringify(event);
  return handleStripeWebhook({ body, signature: signature === undefined ? sign(body, SECRET, now) : signature, store, env: ENV, now });
};
const status = async (fn: () => Promise<unknown>) => {
  try {
    await fn();
  } catch (e) {
    assert.ok(e instanceof BillingError, String(e));
    return e.status;
  }
  return 200;
};
const conversation = (id: string): Conversation => ({ id, startedAt: NOW.toISOString(), updatedAt: NOW.toISOString(), messages: [{ role: "user", content: "hi" }], display: [{ type: "line", who: "you", text: "hi", at: NOW.toISOString() }], summarized: false });

// ================= billing: signature =================
test("a webhook call is accepted only with a genuine, recent signature", async () => {
  const body = JSON.stringify(subEvent());
  verifySignature(body, sign(body, SECRET, NOW), SECRET, NOW);
  assert.throws(() => verifySignature(body, null, SECRET, NOW), /not signed/);
  assert.throws(() => verifySignature(body, "t=abc,v1=zz", SECRET, NOW), /malformed/);
  assert.throws(() => verifySignature(body, sign(body, "whsec_other", NOW), SECRET, NOW), /does not match/);
  assert.throws(() => verifySignature(body + " ", sign(body, SECRET, NOW), SECRET, NOW), /does not match/);
  const old = new Date(NOW.getTime() - (BILLING_CONFIG.toleranceSeconds + 5) * 1000);
  assert.throws(() => verifySignature(body, sign(body, SECRET, old), SECRET, NOW), /too old/);
  // a rotated secret sends two v1 values; either may match
  const good = sign(body, SECRET, NOW);
  verifySignature(body, `${good},v1=${"0".repeat(64)}`, SECRET, NOW);

  const store = new MemoryStore(() => NOW);
  assert.equal(await status(() => send(store, subEvent(), NOW, "t=1,v1=" + "a".repeat(64))), 400);
  assert.equal((await store.get(USER)).subscription.tier, "none", "an unsigned call changes nothing");
  assert.equal(await status(() => handleStripeWebhook({ body, signature: good, store, env: {}, now: NOW })), 503);
});

// ================= billing: reading events =================
test("prices map to plans from the environment, and unknown ones are refused", () => {
  assert.equal(tierForPrice("price_pro_y", ENV), "pro");
  assert.equal(tierForPrice("price_elite_m", ENV), "elite");
  assert.equal(tierForPrice("price_other", ENV), null);
  assert.equal(tierForPrice("price_pro_m", {}), null);

  assert.equal(readEvent({ type: "invoice.paid" }, ENV), null);
  assert.equal(readEvent({ type: "customer.subscription.trial_will_end" }, ENV), null);
  const c = readEvent(subEvent({ status: "trialing", price: "price_elite_m" }), ENV)!;
  assert.deepEqual([c.userId, c.customerId, c.event.tier, c.event.status], [USER, "cus_123", "elite", "active"]);
  assert.equal(readEvent(subEvent({ status: "unpaid" }), ENV)!.event.status, "past_due");
  assert.equal(readEvent(subEvent({ type: "customer.subscription.deleted", status: "active" }), ENV)!.event.status, "canceled");
  assert.deepEqual(readEvent(subEvent({ status: "incomplete", price: "price_other" }), ENV)!.event.tier, "none");
  assert.throws(() => readEvent(subEvent({ price: "price_other" }), ENV), /not listed/);
  assert.throws(() => readEvent(subEvent({ user: null }), ENV), /godseye_user/);
  assert.throws(() => readEvent(subEvent({ user: "../x" }), ENV), /godseye_user/);
  assert.throws(() => readEvent(subEvent({ status: "mystery" }), ENV), /Unknown subscription status/);
});

// ================= billing: end to end =================
test("subscribe, cancel and return: the plan gates the chat and history is archived then restored", async () => {
  const store = new MemoryStore(() => NOW);
  await store.update(USER, (u) => { u.conversations.push(conversation("c1")); u.profile.summary = "plays 4-leg slips"; });
  assert.equal(chatAllowance(await store.get(USER), NOW, {}).ok, false);

  const t0 = Math.floor(NOW.getTime() / 1000);
  assert.deepEqual(await send(store, subEvent({ type: "customer.subscription.created", created: t0 })), { handled: true, note: "applied" });
  let u = await store.get(USER);
  assert.deepEqual([u.subscription.tier, u.subscription.status, u.subscription.customerId], ["pro", "active", "cus_123"]);
  assert.equal(chatAllowance(u, NOW, {}).ok, true);

  // upgrade
  await send(store, subEvent({ price: "price_elite_m", created: t0 + 10 }));
  assert.equal((await store.get(USER)).subscription.tier, "elite");

  // a late copy of the older event must not downgrade them
  const late = await send(store, subEvent({ price: "price_pro_m", created: t0 + 5 }));
  assert.equal(late.handled, false);
  assert.equal((await store.get(USER)).subscription.tier, "elite");
  // the same event delivered twice is harmless
  await send(store, subEvent({ price: "price_elite_m", created: t0 + 10 }));
  assert.equal((await store.get(USER)).subscription.tier, "elite");

  // cancel: chat closes, history is held but hidden
  await send(store, subEvent({ type: "customer.subscription.deleted", status: "canceled", created: t0 + 20 }));
  u = await store.get(USER);
  assert.deepEqual([u.subscription.tier, u.subscription.status], ["none", "canceled"]);
  assert.equal(chatAllowance(u, NOW, {}).ok, false);
  assert.equal(u.conversations.length, 1);
  assert.equal(visibleConversations(u).length, 0);
  assert.equal(u.subscription.customerId, "cus_123");

  // return inside the holding period: history and summary come back
  const back = new Date(NOW.getTime() + (ADVISOR_LIMITS.archiveDays - 1) * 86_400_000);
  await send(store, subEvent({ type: "customer.subscription.created", created: Math.floor(back.getTime() / 1000) }), back);
  u = await store.get(USER);
  assert.equal(visibleConversations(u).length, 1);
  assert.equal(u.profile.summary, "plays 4-leg slips");

  // failed payment keeps the plan but marks it; events for other things are ignored
  await send(store, subEvent({ status: "past_due", created: Math.floor(back.getTime() / 1000) + 5 }), back);
  assert.equal((await store.get(USER)).subscription.status, "past_due");
  assert.deepEqual(await send(store, { type: "invoice.paid", created: 1 }, back), { handled: false, note: "ignored: not a subscription event" });
  assert.equal(await status(() => send(store, subEvent({ price: "price_other", created: Math.floor(back.getTime() / 1000) + 9 }), back)), 422);
});

// ================= the owner's summary =================
test("the owner's summary needs the owner key, and counts subscribers, usage and the record", async () => {
  const key = "k".repeat(OWNER_CONFIG.minKeyLength);
  assert.equal(ownerAccess(`Bearer ${key}`, { OWNER_KEY: key }), "ok");
  assert.equal(ownerAccess(`bearer ${key}`, { OWNER_KEY: key }), "ok");
  assert.equal(ownerAccess(`Bearer ${key}x`, { OWNER_KEY: key }), "denied");
  assert.equal(ownerAccess(null, { OWNER_KEY: key }), "denied");
  assert.equal(ownerAccess("Bearer ", { OWNER_KEY: key }), "denied");
  assert.equal(ownerAccess("Bearer short", { OWNER_KEY: "short" }), "not-set-up", "a weak key is refused even when it matches");
  assert.equal(ownerAccess("Bearer ", {}), "not-set-up");

  const store = new MemoryStore(() => NOW);
  const entry = (daysAgo: number, costUsd: number) => ({ at: new Date(NOW.getTime() - daysAgo * 86_400_000).toISOString(), model: "claude-sonnet-5-5", purpose: "chat" as const, inputTokens: 1, outputTokens: 1, cacheReadTokens: 0, cacheWriteTokens: 0, costUsd });
  await store.update("user_own_pro01", (u) => {
    u.subscription = { tier: "pro", status: "active" };
    u.account = openAccount(500, "balanced", NOW);
    u.usage.push(entry(1, 0.5), entry(10, 0.25), entry(40, 1));
    u.messageLog.push(NOW.toISOString(), NOW.toISOString());
  });
  await store.update("user_own_elite", (u) => { u.subscription = { tier: "elite", status: "past_due" }; u.usage.push(entry(2, 2)); });
  await store.update("user_own_gone1", (u) => { u.subscription = { tier: "none", status: "canceled" }; });
  await store.update("user_own_free1", () => undefined);

  const s = await ownerSummary(store, NOW, { from: "2026-11-11", to: "2026-11-23", issued: 10, cashed: 4, all_staked: 600, all_net: -35.5 });
  assert.deepEqual(s.users, { total: 4, byPlan: { none: 2, pro: 1, elite: 1 }, pastDue: 1, canceled: 1, withBankroll: 1 });
  assert.deepEqual(s.advisor.cost, { last7Days: 2.5, last30Days: 2.75, allTime: 3.75 });
  assert.deepEqual(s.advisor.calls, { last7Days: 2, last30Days: 3, allTime: 4 });
  assert.equal(s.advisor.messagesToday, 2);
  assert.deepEqual(s.advisor.top.map((r) => [r.user, r.cost30]), [["user_own_elite", 2], ["user_own_pro01", 0.75]]);
  assert.deepEqual(s.nba, { from: "2026-11-11", to: "2026-11-23", issued: 10, cashed: 4, lost: 6, hitRate: 0.4, exampleStaked: 600, exampleNet: -35.5 });
  assert.equal((await ownerSummary(store, NOW, null)).nba, null);
  assert.equal((await ownerSummary(new MemoryStore(), NOW, {})).users.total, 0);
});

// ================= the Postgres store =================
// Runs only when TEST_DATABASE_URL points at a scratch database. Everything in its `godseye_test` schema is dropped.
const TEST_DB = process.env.TEST_DATABASE_URL;
test("the Postgres store round-trips a full user record and survives concurrent updates", { skip: TEST_DB ? false : "set TEST_DATABASE_URL to run" }, async () => {
  const pool = new pg.Pool({ connectionString: TEST_DB, max: 8, options: "-c search_path=godseye_test" });
  try {
    await pool.query("drop schema if exists godseye_test cascade; create schema godseye_test");
    const schema = readFileSync(new URL("../../db/schema.sql", import.meta.url), "utf8");
    await pool.query(schema);
    await pool.query(schema); // applying it twice is safe

    const store = new PgStore(pool, () => NOW);
    const id = "user_pg_00001";
    const fresh = await store.get(id);
    assert.deepEqual([fresh.bets.length, fresh.subscription.tier, fresh.profile.summary], [0, "none", ""]);
    assert.deepEqual(await store.list(), [], "reading a new user does not create a row");

    const bet: Bet = { id: "bet_1", placedAt: NOW.toISOString(), sport: "NFL", book: "bet365", legs: [{ description: "J. Allen 200+ pass yds", odds: -250, game: "BUF @ MIA" }], stake: 20, status: "open", price: 320, modelChance: 0.31 };
    const fill = (u: UserRecord) => {
      u.profile = { summary: "likes floor rungs", usualLegCount: 4, book: "bet365", sports: ["NFL"], summaryUpdatedAt: NOW.toISOString() };
      u.account = openAccount(1000, "balanced", NOW);
      u.bets.push(bet, { ...bet, id: "bet_2", status: "won" });
      u.slips.push({ id: "slip_1", savedAt: NOW.toISOString(), sport: "NFL", built: "wk12", legs: [], betId: "bet_1" });
      u.conversations.push(conversation("conv_1"), conversation("conv_2"));
      u.messageLog.push(NOW.toISOString(), new Date(NOW.getTime() + 1000).toISOString());
      u.usage.push({ at: NOW.toISOString(), model: "m", purpose: "chat", inputTokens: 100, outputTokens: 20, cacheReadTokens: 5, cacheWriteTokens: 1, costUsd: 0.001234 });
      u.subscription = { tier: "pro", status: "active", currentPeriodEnd: NOW.toISOString(), canceledAt: null, archivedUntil: null, customerId: "cus_9", lastEventAt: NOW.toISOString() };
    };
    const written = await store.update(id, fill);
    const read = await store.get(id);
    assert.deepEqual(read, written, "what comes back is exactly what was saved");
    assert.deepEqual(read.bets.map((b) => b.id), ["bet_1", "bet_2"]);
    assert.equal(read.usage[0].costUsd, 0.001234);
    assert.deepEqual(await store.list(), [id]);

    // change, remove and add in one update
    await store.update(id, (u) => {
      u.bets = u.bets.filter((b) => b.id !== "bet_1"); // the slip that pointed at it stays, unlinked in the table
      u.bets[0].status = "lost";
      u.conversations = u.conversations.filter((c) => c.id !== "conv_1");
      u.conversations[0].archived = true;
      u.usage.push({ ...u.usage[0], purpose: "summary" });
      u.messageLog = u.messageLog.slice(1);
      u.account = null;
    });
    const after = await store.get(id);
    assert.deepEqual(after.bets.map((b) => [b.id, b.status]), [["bet_2", "lost"]]);
    assert.deepEqual(after.conversations.map((c) => [c.id, c.archived]), [["conv_2", true]]);
    assert.deepEqual([after.usage.length, after.messageLog.length, after.account, after.slips.length], [2, 1, null, 1]);

    // twenty requests at once for the same user: none is lost
    const busy = "user_pg_00002";
    await Promise.all(Array.from({ length: 20 }, (_, i) => store.update(busy, (u) => { u.messageLog.push(new Date(NOW.getTime() + i * 1000).toISOString()); })));
    assert.equal((await store.get(busy)).messageLog.length, 20);

    // a failed change saves nothing
    await assert.rejects(() => store.update(busy, (u) => { u.messageLog = []; throw new Error("boom"); }), /boom/);
    assert.equal((await store.get(busy)).messageLog.length, 20);

    // one user cannot overwrite another's row by reusing an id
    await store.update(busy, (u) => { u.bets.push({ ...bet, id: "bet_2", stake: 999 }); });
    assert.equal((await store.get(id)).bets[0].stake, 20);
    await assert.rejects(() => store.get("../../etc/passwd"));

    // the billing webhook works against this store too
    const body = JSON.stringify(subEvent({ user: busy, price: "price_elite_m" }));
    await handleStripeWebhook({ body, signature: sign(body, SECRET, NOW), store, env: ENV, now: NOW });
    assert.deepEqual([(await store.get(busy)).subscription.tier, (await store.get(busy)).subscription.customerId], ["elite", "cus_123"]);
  } finally {
    await pool.query("drop schema if exists godseye_test cascade").catch(() => undefined);
    await pool.end();
  }
});
