/**
 * Everything Godseye keeps about one subscriber.
 *
 * There is one advisor for everyone; what makes it personal is this record, loaded on every message.
 * The shape is the contract between the app and whatever holds the data: local files today
 * (store/file.ts), Postgres once the database exists (db/schema.sql has the matching tables).
 */
import type { ChatMessage } from "../advisor/agent.ts";
import type { Sport } from "../advisor/legs.ts";
import type { Bet } from "../bets.ts";
import type { SavedSlip } from "../slip/recheck.ts";
import type { Account } from "../staking.ts";

export type Tier = "none" | "pro" | "elite";
export type SubscriptionStatus = "none" | "active" | "past_due" | "canceled";

export type Subscription = {
  tier: Tier;
  status: SubscriptionStatus;
  /** When the paid period ends (ISO). */
  currentPeriodEnd?: string | null;
  canceledAt?: string | null;
  /** After a cancel: history is kept, hidden, until this time (ISO), then deleted. */
  archivedUntil?: string | null;
};

export type Profile = {
  /** How many legs this user usually plays, if they have said or shown it. */
  usualLegCount?: number | null;
  book?: string | null;
  sports?: Sport[];
  /** The running summary of past conversations: preferences, habits, recurring mistakes. */
  summary: string;
  summaryUpdatedAt?: string | null;
};

/** A rich card shown in the chat: a pick list, a slip audit, a stake, and so on. */
export type Card = { kind: "slip" | "audit" | "changes" | "stake" | "picks" | "bankroll" | "logged" | "history"; data: unknown };

export type DisplayItem =
  | { type: "line"; who: "you" | "advisor"; text: string; image?: boolean; at: string }
  | { type: "card"; card: Card };

export type Conversation = {
  id: string;
  startedAt: string;
  updatedAt: string;
  /** The exchange as the model needs it back, tool traffic included. */
  messages: ChatMessage[];
  /** What the user saw, in order: the words exchanged and the cards shown. */
  display: DisplayItem[];
  /** True once this conversation has been folded into the profile summary. */
  summarized: boolean;
  /** True while a cancelled subscriber's history is being held for a possible return. */
  archived?: boolean;
};

export type UsageEntry = {
  at: string;
  model: string;
  purpose: "chat" | "summary" | "slip-read";
  inputTokens: number;
  outputTokens: number;
  cacheReadTokens: number;
  cacheWriteTokens: number;
  costUsd: number;
};

export type UserRecord = {
  id: string;
  createdAt: string;
  profile: Profile;
  account: Account | null;
  bets: Bet[];
  slips: SavedSlip[];
  conversations: Conversation[];
  subscription: Subscription;
  usage: UsageEntry[];
  /** When this user sent each recent chat message (ISO), for the daily cap. */
  messageLog: string[];
};

export function newUser(id: string, now: Date): UserRecord {
  return {
    id, createdAt: now.toISOString(), profile: { summary: "" }, account: null, bets: [], slips: [], conversations: [],
    subscription: { tier: "none", status: "none" }, usage: [], messageLog: [],
  };
}

export interface UserStore {
  /** The user's record, created empty if they are new. */
  get(id: string): Promise<UserRecord>;
  /** Read, change and save in one step, so two requests for the same user cannot overwrite each other. */
  update(id: string, change: (user: UserRecord) => void): Promise<UserRecord>;
  /** Every user id the store holds. */
  list(): Promise<string[]>;
}

/** A store that lives in memory, for tests. */
export class MemoryStore implements UserStore {
  private users = new Map<string, UserRecord>();
  private readonly now: () => Date;
  constructor(now: () => Date = () => new Date()) {
    this.now = now;
  }
  async get(id: string) {
    if (!this.users.has(id)) this.users.set(id, newUser(id, this.now()));
    return structuredClone(this.users.get(id)!);
  }
  async update(id: string, change: (user: UserRecord) => void) {
    const user = await this.get(id);
    change(user);
    this.users.set(id, structuredClone(user));
    return user;
  }
  async list() {
    return [...this.users.keys()];
  }
}

const USER_ID = /^[A-Za-z0-9_-]{8,64}$/;
/** User ids become file names and database keys, so only plain identifiers are accepted. */
export function validUserId(id: unknown): id is string {
  return typeof id === "string" && USER_ID.test(id);
}
