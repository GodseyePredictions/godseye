/**
 * The user store on Postgres (db/schema.sql), for the hosted site.
 *
 * Same contract as the file store: get a whole user record, or read-change-save it in one step.
 * An update runs in one transaction with the user's row locked, so two requests for the same user
 * (on any number of server instances) cannot overwrite each other. Only what changed is written.
 */
import { newUser, validUserId, type Conversation, type UsageEntry, type UserRecord, type UserStore } from "./types.ts";
import type { Bet } from "../bets.ts";
import type { SavedSlip } from "../slip/recheck.ts";

/** The part of a `pg` client or pool this store uses, so tests and other drivers can stand in. */
export type Queryable = { query(text: string, values?: unknown[]): Promise<{ rows: Record<string, unknown>[] }> };
export type PoolLike = Queryable & { connect(): Promise<Queryable & { release(): void }> };

const iso = (v: unknown): string | null => (v == null ? null : v instanceof Date ? v.toISOString() : new Date(String(v)).toISOString());
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
const json = (v: unknown) => JSON.stringify(v);

export class PgStore implements UserStore {
  private readonly pool: PoolLike;
  private readonly now: () => Date;
  constructor(pool: PoolLike, now: () => Date = () => new Date()) {
    this.pool = pool;
    this.now = now;
  }

  private async read(db: Queryable, id: string, lock: boolean): Promise<{ user: UserRecord; exists: boolean }> {
    if (!validUserId(id)) throw new Error("That is not a valid user id.");
    const { rows } = await db.query(`select * from users where id = $1${lock ? " for update" : ""}`, [id]);
    if (!rows.length) return { user: newUser(id, this.now()), exists: false };
    const u = rows[0];
    // one at a time: inside an update these share a single connection
    const bets = await db.query("select data from bets where user_id = $1 order by placed_at, id", [id]);
    const slips = await db.query("select data from saved_slips where user_id = $1 order by saved_at, id", [id]);
    const conversations = await db.query("select * from conversations where user_id = $1 order by started_at, id", [id]);
    const messages = await db.query("select sent_at from advisor_messages where user_id = $1 order by sent_at", [id]);
    const usage = await db.query("select * from usage where user_id = $1 order by id", [id]);
    const user: UserRecord = {
      id,
      createdAt: iso(u.created_at)!,
      profile: { ...(u.profile as UserRecord["profile"]), summary: (u.profile as UserRecord["profile"])?.summary ?? "" },
      account: (u.account as UserRecord["account"]) ?? null,
      bets: bets.rows.map((r) => r.data as Bet),
      slips: slips.rows.map((r) => r.data as SavedSlip),
      conversations: conversations.rows.map((r): Conversation => ({
        id: r.id as string, startedAt: iso(r.started_at)!, updatedAt: iso(r.updated_at)!,
        messages: r.messages as Conversation["messages"], display: r.display as Conversation["display"],
        summarized: r.summarized as boolean, ...(r.archived ? { archived: true } : {}),
      })),
      subscription: {
        tier: u.subscription_tier as UserRecord["subscription"]["tier"],
        status: u.subscription_status as UserRecord["subscription"]["status"],
        currentPeriodEnd: iso(u.current_period_end), canceledAt: iso(u.canceled_at), archivedUntil: iso(u.archived_until),
        customerId: (u.billing_customer_id as string) ?? null, lastEventAt: iso(u.billing_event_at),
      },
      usage: usage.rows.map((r): UsageEntry => ({
        at: iso(r.at)!, model: r.model as string, purpose: r.purpose as UsageEntry["purpose"],
        inputTokens: r.input_tokens as number, outputTokens: r.output_tokens as number,
        cacheReadTokens: r.cache_read_tokens as number, cacheWriteTokens: r.cache_write_tokens as number, costUsd: Number(r.cost_usd),
      })),
      messageLog: messages.rows.map((r) => iso(r.sent_at)!),
    };
    return { user, exists: true };
  }

  async get(id: string) {
    return (await this.read(this.pool, id, false)).user;
  }

  async update(id: string, change: (user: UserRecord) => void): Promise<UserRecord> {
    if (!validUserId(id)) throw new Error("That is not a valid user id.");
    const db = await this.pool.connect();
    try {
      await db.query("begin");
      // make sure the row exists, then lock it for the rest of the transaction
      await db.query("insert into users (id, created_at) values ($1, $2) on conflict (id) do nothing", [id, this.now().toISOString()]);
      const { user: before } = await this.read(db, id, true);
      const user = structuredClone(before);
      change(user);
      await this.write(db, before, user);
      await db.query("commit");
      return user;
    } catch (error) {
      await db.query("rollback").catch(() => undefined);
      throw error;
    } finally {
      db.release();
    }
  }

  private async write(db: Queryable, before: UserRecord, user: UserRecord) {
    const id = user.id;
    const s = user.subscription;
    if (!same(before.profile, user.profile) || !same(before.account, user.account) || !same(before.subscription, s)) {
      await db.query(
        `update users set profile = $2, account = $3, subscription_tier = $4, subscription_status = $5, current_period_end = $6,
           canceled_at = $7, archived_until = $8, billing_customer_id = $9, billing_event_at = $10 where id = $1`,
        [id, json(user.profile), user.account ? json(user.account) : null, s.tier, s.status, s.currentPeriodEnd ?? null,
          s.canceledAt ?? null, s.archivedUntil ?? null, s.customerId ?? null, s.lastEventAt ?? null],
      );
    }

    // slips point at bets, so bets are written first and removed last
    const oldBets = new Map(before.bets.map((b) => [b.id, b]));
    for (const b of user.bets) {
      if (same(oldBets.get(b.id), b)) continue;
      await db.query(
        `insert into bets (id, user_id, placed_at, sport, book, legs, stake, status, price, closing_odds, model_chance, data)
         values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
         on conflict (id) do update set placed_at = excluded.placed_at, sport = excluded.sport, book = excluded.book, legs = excluded.legs,
           stake = excluded.stake, status = excluded.status, price = excluded.price, closing_odds = excluded.closing_odds,
           model_chance = excluded.model_chance, data = excluded.data
         where bets.user_id = excluded.user_id`,
        [b.id, id, b.placedAt, b.sport, b.book ?? "", json(b.legs), b.stake, b.status, b.price == null ? null : Math.round(b.price),
          b.closingOdds == null ? null : Math.round(b.closingOdds), b.modelChance ?? null, json(b)],
      );
    }

    const oldSlips = new Map(before.slips.map((x) => [x.id, x]));
    const betIds = new Set(user.bets.map((b) => b.id));
    for (const x of user.slips) {
      if (same(oldSlips.get(x.id), x)) continue;
      await db.query(
        `insert into saved_slips (id, user_id, bet_id, saved_at, sport, built, legs, data) values ($1,$2,$3,$4,$5,$6,$7,$8)
         on conflict (id) do update set bet_id = excluded.bet_id, saved_at = excluded.saved_at, sport = excluded.sport,
           built = excluded.built, legs = excluded.legs, data = excluded.data
         where saved_slips.user_id = excluded.user_id`,
        [x.id, id, x.betId && betIds.has(x.betId) ? x.betId : null, x.savedAt, x.sport, x.built, json(x.legs), json(x)],
      );
    }
    await this.removeMissing(db, "saved_slips", id, before.slips, user.slips);
    await this.removeMissing(db, "bets", id, before.bets, user.bets);

    const oldConvs = new Map(before.conversations.map((c) => [c.id, c]));
    for (const c of user.conversations) {
      if (same(oldConvs.get(c.id), c)) continue;
      await db.query(
        `insert into conversations (id, user_id, started_at, updated_at, messages, display, summarized, archived) values ($1,$2,$3,$4,$5,$6,$7,$8)
         on conflict (id) do update set updated_at = excluded.updated_at, messages = excluded.messages, display = excluded.display,
           summarized = excluded.summarized, archived = excluded.archived
         where conversations.user_id = excluded.user_id`,
        [c.id, id, c.startedAt, c.updatedAt, json(c.messages), json(c.display), c.summarized, !!c.archived],
      );
    }
    await this.removeMissing(db, "conversations", id, before.conversations, user.conversations);

    if (!same(before.messageLog, user.messageLog)) {
      await db.query("delete from advisor_messages where user_id = $1", [id]);
      if (user.messageLog.length) {
        await db.query("insert into advisor_messages (user_id, sent_at) select $1, unnest($2::timestamptz[])", [id, user.messageLog]);
      }
    }

    // usage is a ledger: rows are added, and only a full reset removes them
    const kept = before.usage.length <= user.usage.length && same(before.usage, user.usage.slice(0, before.usage.length));
    if (!kept) await db.query("delete from usage where user_id = $1", [id]);
    for (const e of kept ? user.usage.slice(before.usage.length) : user.usage) {
      await db.query(
        `insert into usage (user_id, at, model, purpose, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, cost_usd)
         values ($1,$2,$3,$4,$5,$6,$7,$8,$9)`,
        [id, e.at, e.model, e.purpose, e.inputTokens, e.outputTokens, e.cacheReadTokens, e.cacheWriteTokens, e.costUsd],
      );
    }
  }

  private async removeMissing(db: Queryable, table: "bets" | "saved_slips" | "conversations", userId: string, before: { id: string }[], after: { id: string }[]) {
    const keep = new Set(after.map((x) => x.id));
    const gone = before.map((x) => x.id).filter((x) => !keep.has(x));
    if (gone.length) await db.query(`delete from ${table} where user_id = $1 and id = any($2::text[])`, [userId, gone]);
  }

  async list() {
    const { rows } = await this.pool.query("select id from users order by created_at, id");
    return rows.map((r) => r.id as string);
  }
}
