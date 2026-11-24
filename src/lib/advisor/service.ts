/**
 * One advisor message, start to finish, for one user. The API route is a thin wrapper around this.
 *
 *   1. load the user's record and bring it up to date (bankroll and bets synced from the app, expired archive purged)
 *   2. check their subscription and today's message cap: if they may not chat, answer without calling the model
 *   3. fold any finished conversation into their profile summary
 *   4. build their context, run the advisor turn, and check the reply
 *   5. save the conversation, the cards shown, any bet logged, and the token usage
 *
 * Everything it needs is passed in (store, model, algorithm output, clock), so it runs the same in tests.
 */
import type { Bet } from "../bets.ts";
import type { ImageType } from "../slip/vision.ts";
import { withWeeklyUnit, type Account } from "../staking.ts";
import type { Card, Conversation, DisplayItem, UserRecord, UserStore } from "../store/types.ts";
import { ADVISOR_CONFIG, runAdvisorTurn, trimHistory, userContext, type AdvisorContext, type CallModel, type ChatMessage, type TurnEvent } from "./agent.ts";
import { updateSummary } from "./memory.ts";
import { chatAllowance, purgeExpiredArchive, recordMessage, visibleConversations, type Allowance } from "./subscription.ts";
import { logUsage } from "./usage.ts";
import type { Sport } from "./legs.ts";

export const MAX_TEXT = 4000;
export const IMAGE_ID = "slip-1";

export type TurnInput = {
  userId: string;
  /** The conversation to continue, or null to start a new one. */
  conversationId: string | null;
  text: string;
  image?: { mediaType: ImageType; data: Uint8Array } | null;
  /** The app's copy of the user's bankroll settings and tracked bets, while those still live in the browser. */
  account?: Account | null;
  bets?: Bet[] | null;
};

export type ServiceEvent =
  | TurnEvent
  | { type: "blocked"; reason: "no-subscription" | "daily-cap"; message: string }
  | { type: "bet"; bet: Bet }
  | { type: "done"; conversationId: string; ended: string; remainingToday: number | null; tier: string };

export type ServiceDeps = {
  store: UserStore;
  callModel: CallModel;
  /** The model's name, for the usage log. */
  model: string;
  algo: Pick<AdvisorContext, "catalogs" | "intel" | "picks">;
  readImage?: (image: { mediaType: ImageType; data: Uint8Array }) => Promise<unknown>;
  now?: () => Date;
  newId?: () => string;
  env?: Record<string, string | undefined>;
};

function userMessage(text: string, image: TurnInput["image"]): ChatMessage {
  if (!image) return { role: "user", content: text };
  return {
    role: "user",
    content: [
      { type: "image", source: { type: "base64", media_type: image.mediaType, data: Buffer.from(image.data).toString("base64") } },
      { type: "text", text: `${text || "Here is my bet slip."}\n\n[The user attached a bet slip screenshot. Its image_id for parse_slip is "${IMAGE_ID}".]` },
    ],
  };
}

/** Bring the stored record in line with the app's copy of bankroll and bets, which is the newer one for now. */
function syncFromApp(user: UserRecord, input: TurnInput, now: Date): void {
  if (input.account && typeof input.account.bankroll === "number" && input.account.bankroll >= 0) user.account = withWeeklyUnit(input.account, now);
  // the app's list is the one the user edits (marking results, deleting), so it replaces the stored one
  if (Array.isArray(input.bets)) user.bets = input.bets.filter((b) => b && typeof b.id === "string").sort((a, b) => b.placedAt.localeCompare(a.placedAt));
}

export async function handleTurn(input: TurnInput, deps: ServiceDeps, onEvent: (e: ServiceEvent) => void): Promise<{ allowance: Allowance; conversationId: string | null }> {
  const now = (deps.now ?? (() => new Date()))();
  const newId = deps.newId ?? (() => crypto.randomUUID());
  const text = input.text.trim().slice(0, MAX_TEXT);

  // 1 and 2: load, sync, check the plan. A message that is refused is not counted and costs nothing.
  let allowance!: Allowance;
  const before = await deps.store.update(input.userId, (u) => {
    purgeExpiredArchive(u, now);
    syncFromApp(u, input, now);
    allowance = chatAllowance(u, now, deps.env);
    if (allowance.ok) recordMessage(u, now);
  });
  if (!allowance.ok) {
    onEvent({ type: "blocked", reason: allowance.reason, message: allowance.message });
    return { allowance, conversationId: input.conversationId };
  }

  // work on a copy; it is saved in one step at the end
  const user = structuredClone(before);
  let convo = input.conversationId ? visibleConversations(user).find((c) => c.id === input.conversationId) ?? null : null;
  const isNew = !convo;
  if (!convo) {
    convo = { id: newId(), startedAt: now.toISOString(), updatedAt: now.toISOString(), messages: [], display: [], summarized: false };
    user.conversations.push(convo);
  }

  // 3: memory. Done before the first reply of a new conversation, so that reply already knows the user.
  let summaryUsage = null;
  if (isNew) {
    try {
      summaryUsage = await updateSummary(user, convo.id, deps.callModel, now);
    } catch {
      /* the summary is retried next time; the chat goes on without it */
    }
  }

  // 4: the turn
  const built = Object.fromEntries((Object.keys(deps.algo.catalogs) as Sport[]).map((s) => [s, deps.algo.catalogs[s]!.built]));
  const remainingAfter = allowance.remaining === null ? null : allowance.remaining - 1;
  const context = userContext(user, { now, built, tier: allowance.tier, remainingToday: remainingAfter });
  const betsBefore = new Set(user.bets.map((b) => b.id));
  const cards: Card[] = [];
  const ctx: AdvisorContext = {
    ...deps.algo, user, now, context, newId,
    readImage: async (id) => {
      if (!input.image || id !== IMAGE_ID || !deps.readImage) throw new Error("There is no screenshot with that id in this message. Ask the user to attach the slip again.");
      return deps.readImage(input.image);
    },
  };
  const result = await runAdvisorTurn([...convo.messages, userMessage(text, input.image)], ctx, deps.callModel, (e) => {
    if (e.type === "card") cards.push(e.card);
    onEvent(e);
  });

  // 5: save
  const at = now.toISOString();
  const display: DisplayItem[] = [
    { type: "line", who: "you", text, image: !!input.image, at },
    ...cards.map((card): DisplayItem => ({ type: "card", card })),
    ...(result.reply ? [{ type: "line" as const, who: "advisor" as const, text: result.reply, at }] : []),
  ];
  const logged = user.bets.filter((b) => !betsBefore.has(b.id));
  await deps.store.update(input.userId, (u) => {
    const target = u.conversations.find((c) => c.id === convo!.id);
    const saved: Conversation = { ...convo!, messages: trimHistory(result.messages), display: [...convo!.display, ...display].slice(-ADVISOR_CONFIG.maxHistory * 4), updatedAt: at };
    if (target) Object.assign(target, saved);
    else u.conversations.push(saved);
    // the summary and which conversations it covers
    u.profile = user.profile;
    for (const c of u.conversations) if (user.conversations.find((x) => x.id === c.id)?.summarized) c.summarized = true;
    u.conversations = u.conversations.filter((c) => user.conversations.some((x) => x.id === c.id));
    // anything the advisor logged
    for (const b of logged) if (!u.bets.some((x) => x.id === b.id)) u.bets.unshift(b);
    for (const s of user.slips) if (!u.slips.some((x) => x.id === s.id)) u.slips.unshift(s);
    logUsage(u, deps.model, "chat", result.usage, now);
    if (summaryUsage) logUsage(u, deps.model, "summary", summaryUsage, now);
  });
  for (const bet of logged) onEvent({ type: "bet", bet });
  onEvent({ type: "done", conversationId: convo.id, ended: result.ended, remainingToday: remainingAfter, tier: allowance.tier });
  return { allowance, conversationId: convo.id };
}

/** What the History screen shows: the user's conversations, newest first, and what the advisor remembers. */
export async function readHistory(store: UserStore, userId: string, now: Date, env?: Record<string, string | undefined>) {
  const user = await store.update(userId, (u) => { purgeExpiredArchive(u, now); });
  const allowance = chatAllowance(user, now, env);
  return {
    summary: user.profile.summary,
    summaryUpdatedAt: user.profile.summaryUpdatedAt ?? null,
    conversations: visibleConversations(user).map((c) => ({ id: c.id, startedAt: c.startedAt, updatedAt: c.updatedAt, display: c.display })).sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)),
    plan: { tier: allowance.tier, cap: allowance.cap, usedToday: allowance.usedToday, canChat: allowance.ok, message: allowance.ok ? null : allowance.message },
  };
}
