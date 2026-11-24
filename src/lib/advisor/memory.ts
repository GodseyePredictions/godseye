/**
 * The advisor's memory of a user between conversations.
 *
 * Every conversation is stored on the user's record. When one is over, it is folded into a short running
 * summary on their profile (preferences, habits, recurring mistakes), and that summary is loaded into the
 * next conversation. A user can read and clear all of it.
 */
import type { Conversation, UserRecord } from "../store/types.ts";
import type { CallModel, ChatMessage } from "./agent.ts";
import { NO_USAGE, type TokenUsage } from "./usage.ts";

export const MEMORY_CONFIG = {
  /** The longest the running summary may be, in words. */
  maxWords: 140,
  /** Conversations with fewer user messages than this are not worth summarising. */
  minUserMessages: 1,
  /** How much of a conversation's text is given to the summariser. */
  maxChars: 12_000,
  /** Conversations kept per user; the oldest are dropped once summarised. */
  keepConversations: 30,
};

const SUMMARY_SYSTEM = `You keep the notes a personal betting advisor holds on one subscriber. You will be given the notes so far and the transcript of the conversation that just ended. Write the updated notes.

The notes exist so the advisor can pick up next time where it left off, so keep what will still be useful then: how they like to bet (usual number of legs, sports, markets, sportsbook), how they size and what limits they set, habits and recurring mistakes the advisor has pointed out, what they are trying to improve, and anything they asked the advisor to remember. Leave out one-off details that will be stale tomorrow: specific legs, prices and probabilities from tonight, and the results of individual bets. Do not record anything sensitive that is not about their betting.

Merge with the existing notes rather than appending: update a line that has changed, drop one that no longer holds. Write plain sentences in the third person ("Prefers 4-leg NFL same-game parlays on bet365."), no headings or lists, at most ${MEMORY_CONFIG.maxWords} words. If the conversation adds nothing worth keeping, return the existing notes unchanged. Reply with the notes only.`;

/** The words exchanged in a conversation, without tool traffic. */
export function transcript(messages: ChatMessage[]): string {
  const lines: string[] = [];
  for (const m of messages) {
    const text = typeof m.content === "string" ? m.content : m.content.filter((b) => b.type === "text").map((b) => (b as { text: string }).text).join(" ");
    const clean = text.replace(/\[The user attached a bet slip screenshot[^\]]*\]/g, "[attached a slip]").trim();
    if (!clean || clean.startsWith("[Automatic check]")) continue;
    lines.push(`${m.role === "user" ? "User" : "Advisor"}: ${clean}`);
  }
  const all = lines.join("\n");
  return all.length > MEMORY_CONFIG.maxChars ? all.slice(-MEMORY_CONFIG.maxChars) : all;
}

const userMessages = (c: Conversation) => c.display.filter((d) => d.type === "line" && d.who === "you").length;

/** Conversations that are finished (not the one in progress) and not yet folded into the summary. */
export function pendingSummaries(user: UserRecord, currentId: string | null): Conversation[] {
  return user.conversations.filter((c) => !c.summarized && !c.archived && c.id !== currentId && userMessages(c) >= MEMORY_CONFIG.minUserMessages);
}

/**
 * Fold finished conversations into the profile summary. Changes `user` in place and returns the tokens used.
 * If the model call fails, the conversations stay pending and are tried again next time.
 */
export async function updateSummary(user: UserRecord, currentId: string | null, callModel: CallModel, now: Date): Promise<TokenUsage> {
  const pending = pendingSummaries(user, currentId);
  if (!pending.length) return NO_USAGE;
  const body = pending.map((c) => `Conversation of ${c.startedAt.slice(0, 10)}:\n${transcript(c.messages)}`).join("\n\n");
  const reply = await callModel(
    { system: SUMMARY_SYSTEM, context: "", tools: [], messages: [{ role: "user", content: `Notes so far:\n${user.profile.summary || "(none yet)"}\n\n${body}` }] },
    () => {},
  );
  const text = reply.content.filter((b) => b.type === "text").map((b) => (b as { text: string }).text).join("").trim();
  if (reply.stop_reason === "end_turn" && text) {
    const words = text.split(/\s+/);
    user.profile.summary = words.length > MEMORY_CONFIG.maxWords * 1.5 ? words.slice(0, Math.round(MEMORY_CONFIG.maxWords * 1.5)).join(" ") : text;
    user.profile.summaryUpdatedAt = now.toISOString();
    for (const c of pending) user.conversations.find((x) => x.id === c.id)!.summarized = true;
  }
  // keep the record from growing without end: drop the oldest conversations that are already in the summary
  const done = user.conversations.filter((c) => c.summarized && !c.archived);
  const extra = user.conversations.length - MEMORY_CONFIG.keepConversations;
  if (extra > 0) {
    const drop = new Set(done.slice(0, extra).map((c) => c.id));
    user.conversations = user.conversations.filter((c) => !drop.has(c.id));
  }
  return reply.usage ?? NO_USAGE;
}

/** Clear everything the advisor remembers about a user: conversations and the summary. Their bets and bankroll stay. */
export function clearMemory(user: UserRecord): void {
  user.conversations = [];
  user.profile = { ...user.profile, summary: "", summaryUpdatedAt: null };
}
