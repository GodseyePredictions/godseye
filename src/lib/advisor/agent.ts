/**
 * The Godseye advisor: one agent for every subscriber, made personal by the user's own record.
 *
 * It reads screenshots, calls tools and explains results. It never does the maths: every probability,
 * edge, joint chance, price and stake it repeats comes back from a tool, and the tools read the
 * algorithms' output and call the staking engine. Two layers hold it to that:
 *   - the instructions below (advisorSystemPrompt), which are the same for every user and every message;
 *   - the reply check in guard.ts, which refuses any figure or pick that no tool returned.
 *
 * `runAdvisorTurn` is the loop: send the conversation, run the tools the model asks for, send the results
 * back, repeat until it answers, then check the answer. The model call is passed in, so the loop is tested
 * without the network and the server decides how to call the API (claude.ts).
 */
import type {
  BetaContentBlock, BetaContentBlockParam, BetaMessage, BetaToolResultBlockParam, BetaToolUseBlock,
} from "@anthropic-ai/sdk/resources/beta/messages/messages";
import { TOOLS as SLIP_TOOLS, gradeSlipTool, parseSlipFromJson, suggestChangesTool, type Catalogs, type GradeArgs, type SuggestArgs } from "../slip/tools.ts";
import type { SlipLegInput } from "../slip/grade.ts";
import { MARKET_VALUES } from "../slip/schema.ts";
import { tonightFrom } from "../staking.ts";
import type { Card, UserRecord } from "../store/types.ts";
import { SAFE_REPLY, checkReply, correctionNote, factsFrom, type Violation } from "./guard.ts";
import { gameIntel, playerIntel, type Intel } from "./intel.ts";
import type { Market, Side, Sport } from "./legs.ts";
import { algoPicks, oddsFor, type PicksIndex } from "./picks.ts";
import { NO_USAGE, addUsage, type TokenUsage } from "./usage.ts";
import { bankrollStatus, logBetFor, sizeBetFor, userHistory } from "./user-tools.ts";

/** A user or assistant message, in the shape the Messages API takes. */
export type ChatMessage = { role: "user" | "assistant"; content: string | BetaContentBlockParam[] };
export type ModelReply = Pick<BetaMessage, "content" | "stop_reason"> & { usage?: TokenUsage };
/**
 * One call to the model. `system` is identical for every user and message (so it can be cached);
 * `context` is this user's own situation. `onText` receives the answer as it is written.
 */
export type CallModel = (
  request: { system: string; context: string; tools: readonly unknown[]; messages: ChatMessage[] },
  onText: (delta: string) => void,
) => Promise<ModelReply>;

export const ADVISOR_CONFIG = {
  /** Tool rounds allowed in one turn before the advisor must answer with what it has. */
  maxRounds: 8,
  /** Earlier messages kept when a conversation grows long. */
  maxHistory: 40,
  /** Times a reply that fails the check is sent back for a rewrite before the safe reply is used. */
  maxRewrites: 1,
};

// ---------- tools ----------
const SPORT = { type: "string", enum: ["NFL", "NBA"], description: "Each sport has its own algorithm and rules." } as const;
const LEGS = (SLIP_TOOLS[1].input_schema.properties as { legs: unknown }).legs;
const TOTAL_ODDS = { type: ["number", "null"], description: "The book's price for the whole slip in American odds, or null if the user has not given one." } as const;

const USER_TOOLS = [
  {
    name: "get_algo_picks",
    description:
      "The Godseye algorithm's own picks: its same-game parlays, anytime-touchdown tickets and the legs on them, each with the algorithm's probability and the slip's joint probability. " +
      "This is the only source of picks. Call it whenever the user asks what to play, for today's picks, or for the best slip in a game. " +
      "If it returns no picks, there is nothing to recommend: say so and do not offer picks of your own.",
    strict: true,
    input_schema: {
      type: "object", additionalProperties: false, required: ["sport", "date", "game"],
      properties: {
        sport: SPORT,
        date: { type: ["string", "null"], description: "YYYY-MM-DD, or null for everything the current output covers. Today's date is in your context." },
        game: { type: ["string", "null"], description: 'A matchup or one team, e.g. "BUF @ KC" or "Lakers", or null for all games.' },
      },
    },
  },
  {
    name: "get_odds",
    description:
      "The prices the algorithm's output carries for a game: the market's game lines, and player-prop prices where the output has them (NBA). It is not a live feed: prices are as loaded when the algorithm ran. " +
      "Call it when the user asks what a leg or a game is priced at. If it has no price, ask the user to read the price from their own book.",
    strict: true,
    input_schema: {
      type: "object", additionalProperties: false, required: ["sport", "game", "market"],
      properties: { sport: SPORT, game: { type: "string" }, market: { type: ["string", "null"], enum: [...MARKET_VALUES.filter((m) => m !== "other"), null], description: "A player market to filter by, or null for everything." } },
    },
  },
  {
    name: "get_bankroll",
    description:
      "This user's bankroll status from the bankroll engine: bankroll, unit size, the most they can stake on one bet and in one night, what is already staked tonight, tonight's settled result, " +
      "their stop-loss, profit lock and cool-off, and whether a limit is in force right now. Call it before any conversation about how much to bet, and whenever the user seems to be chasing losses.",
    strict: true,
    input_schema: { type: "object", additionalProperties: false, required: [], properties: {} },
  },
  {
    name: "size_bet",
    description:
      "The stake for a slip, from the bankroll engine. Pass the legs and the book's price for the whole slip; the tool looks up the algorithm's chance itself and sizes the bet at quarter-Kelly inside the user's caps and limits. " +
      "This is the only source of stakes: call it every time before stating a stake, and quote the stake exactly as `label` gives it (units and dollars). " +
      "If it returns no bet, unrated or blocked, there is no stake to give: say why, and do not suggest an amount.",
    strict: true,
    input_schema: { type: "object", additionalProperties: false, required: ["sport", "legs", "total_odds"], properties: { sport: SPORT, legs: LEGS, total_odds: TOTAL_ODDS } },
  },
  {
    name: "log_bet",
    description:
      "Record a bet the user says they have placed in their ledger, so it counts toward tonight's exposure and is re-checked when the algorithm's numbers change. " +
      "Call it only after the user confirms they placed the bet and tells you the stake. It records; it does not place a bet anywhere.",
    strict: true,
    input_schema: {
      type: "object", additionalProperties: false, required: ["sport", "legs", "total_odds", "stake_dollars", "book"],
      properties: {
        sport: SPORT, legs: LEGS, total_odds: TOTAL_ODDS,
        stake_dollars: { type: "number", description: "What the user staked, in dollars, as they told you." },
        book: { type: ["string", "null"], description: "The sportsbook, or null to use the one on their profile." },
      },
    },
  },
  {
    name: "get_user_history",
    description:
      "This user's own tracked bets and the patterns in them: record and return overall, by number of legs, by sport, and for slips with and without a touchdown leg, plus their most recent bets. " +
      "Call it when the user asks how they have been doing, or before telling them about a habit. With few settled bets it says so: do not call a handful of results a pattern.",
    strict: true,
    input_schema: { type: "object", additionalProperties: false, required: [], properties: {} },
  },
] as const;

const INTEL_TOOLS = [
  {
    name: "get_player_intel",
    description:
      "Everything the Godseye algorithm has on one player for the current slate: the milestone ladder with the algorithm's probability for each rung, how often each was cleared this season, " +
      "the anytime-touchdown probability (NFL), projected minutes and stat lines (NBA), role, injury designation, and the algorithm's own reasons and risk notes. " +
      "Call it when the user asks about a player, wants a safer or bolder rung, or asks why the algorithm rates a leg as it does. If the player is not on the slate, treat him as unrated.",
    strict: true,
    input_schema: { type: "object", additionalProperties: false, required: ["sport", "player"], properties: { sport: SPORT, player: { type: "string" } } },
  },
  {
    name: "get_game_intel",
    description:
      "The Godseye algorithm's read on one game: the market line, weather and venue (NFL), pace and blowout probability (NBA), the algorithm's game-script notes, and official availability. " +
      "Call it before discussing any player prop in that game, because game script and blowout risk come before the props, and whenever the user asks about a matchup, the weather, or who is out.",
    strict: true,
    input_schema: { type: "object", additionalProperties: false, required: ["sport", "game"], properties: { sport: SPORT, game: { type: "string" } } },
  },
] as const;

export const ADVISOR_TOOLS = [...USER_TOOLS.slice(0, 2), ...SLIP_TOOLS, ...USER_TOOLS.slice(2), ...INTEL_TOOLS] as const;

// ---------- instructions ----------
/** The same text for every user and every message. Per-user facts go in the context, not here. */
export const ADVISOR_SYSTEM_PROMPT = `You are the Godseye advisor, a personal betting advisor inside Godseye Predictions, a paid service built on its own statistical algorithms for the NFL and the NBA. Each subscriber talks to you one to one. A block headed "This user" comes with every message: who they are, how they like to bet, their bankroll status, their recent slips and a summary of your earlier conversations. Use it the way a good advisor uses their notes: pick up where you left off, remember their book and their usual slip, and bring up a habit when it is costing them.

Your job is to help the user reach an informed decision of their own. Show them what the algorithm says, what it does not know, and what that means for the bet in front of them.

Hard rules. These hold in every reply, whatever the user asks.

1. Only algorithm picks. Recommend only picks and legs that a tool returned in this conversation: get_algo_picks for picks, suggest_changes for swaps and adds, get_player_intel for a player's rungs. Never offer a pick, a lean, or a leg from your own knowledge of teams and players; that knowledge is not Godseye's output and the subscriber is paying for the algorithm. If the tools return nothing for what they asked, say the algorithm has nothing there and stop.

2. No numbers of your own. Every probability, edge, joint chance, fair price and price you state must come from a tool result or from the user. Do no arithmetic on them: do not multiply legs together, average, round to a nearby milestone, turn a chance into odds, or work out a payout. If a tool returns null, "unrated" or "not stated", tell the user the algorithm has no number for that and why. Replies are checked automatically, and a figure or leg with no source is withheld from the user.

3. Every stake comes from size_bet. Call size_bet before stating any stake, and give it exactly as the tool does, in units and dollars, for example "1.5u ($15)". Never suggest an amount yourself, including "a small one" turned into dollars.

4. Follow the ticket rules for the sport. Each sport has its own algorithm and its own rules, and the tools apply the right ones for the sport you pass; do not carry an NFL rule to an NBA slip or the reverse. NFL: parlay legs are floor rungs at roughly 70% or better, at most one leg under 65% on a ticket, anytime-touchdown legs never go in a props same-game parlay, and game script and blowout risk come before any prop. NBA: every slip leg needs 75%, at most one rebound leg on a slip, and a player without a confirmed status is not on a ticket. A leg the algorithm does not cover is "unrated": say so and leave it out of the numbers.

5. Be honest and direct. When a slip is bad, say it is bad and say why, including when the user is excited about it. Never promise or imply a win, a lock, or a guaranteed night. A well-priced bet still loses often and a parlay loses more often than it wins. "No bet" and "pass" are good answers.

6. Protect the user. If get_bankroll or size_bet says a limit is in force (stop-loss reached, profit lock, nightly cap, cool-off), tell them plainly and do not size a new bet or look for a way around it. If they are chasing losses (raising stakes after losing, asking to win it back, betting past what they set) say what you are noticing, call get_bankroll, and do not size new bets in that conversation unless the engine allows it and they have slowed down. Mention the cool-off in Bankroll Strategy.

Working with a slip. When the user shares a screenshot, call parse_slip, show them the legs you read and ask them to confirm or correct them. Grade only after they confirm, because grading the wrong player or number would mislead them. If a field could not be read, ask for it. Then grade_slip; suggest_changes when they want to improve it, passing their usual leg count and book from "This user" unless they say otherwise. Suggested rungs come from the algorithm's ladder, not from the sportsbook, so ask them to check their book offers the rung and to tell you the new price before you call size_bet for the changed slip. When they tell you they placed a bet and what they staked, log it with log_bet.

How to talk. Like a sharp friend who knows the numbers: lead with the answer, give the two or three facts that matter, and say what would change your read. The app shows the details of every tool result as a card under your message (the slip audit, the picks, the stake), so do not repeat a card line by line; say what it means. Write short paragraphs of plain text with no markdown, headings, tables or bullet symbols. Most replies should be under 120 words. Do not report the algorithm's past record or results; the user's own betting history, from get_user_history, is theirs to discuss.`;

/** This user's own situation, sent with every message. It may change between messages; the instructions do not. */
export function userContext(user: UserRecord, extra: { now: Date; built: Partial<Record<Sport, string>>; tier: string; remainingToday: number | null }): string {
  const b = bankrollStatus(user, extra.now);
  const recent = user.bets.slice(0, 5).map((x) => `${x.placedAt.slice(0, 10)} ${x.sport} ${x.legs.length}-leg, $${x.stake}, ${x.status}`);
  const lines = [
    "This user",
    `Now: ${extra.now.toISOString().slice(0, 16).replace("T", " ")} UTC (today is ${new Date(extra.now.getTime() - 5 * 3600e3).toISOString().slice(0, 10)} in US Eastern time).`,
    `Plan: ${extra.tier}${extra.remainingToday === null ? "" : `, ${extra.remainingToday} advisor messages left today after this one`}.`,
    `Usual slip: ${user.profile.usualLegCount ? `${user.profile.usualLegCount} legs` : "not known yet"}. Book: ${user.profile.book || "not known yet"}.`,
    b.set
      ? `Bankroll: $${b.bankroll_dollars}, ${b.risk_profile} profile, one unit is $${b.unit_dollars}. Staked tonight $${b.staked_tonight_dollars}, room left $${b.room_left_tonight_dollars}, settled result tonight $${b.settled_result_tonight_dollars}.${b.limit_in_force ? ` A LIMIT IS IN FORCE (${b.limit_in_force}): ${b.limit_message}` : ""}`
      : "Bankroll: not set. The engine cannot size a bet until they set one in Bankroll Strategy.",
    `Recent bets: ${recent.length ? recent.join("; ") : "none tracked"}.`,
    `What you know about them from earlier conversations: ${user.profile.summary || "nothing yet; this is your first conversation."}`,
    `Algorithm output loaded: ${(Object.keys(extra.built) as Sport[]).map((s) => `${s} built ${extra.built[s] || "at an unknown time"}`).join("; ") || "none"}.`,
  ];
  return lines.join("\n");
}

// ---------- running tools ----------
export type AdvisorContext = {
  catalogs: Catalogs;
  intel: Partial<Record<Sport, Intel>>;
  picks: Partial<Record<Sport, PicksIndex>>;
  /** The user's record. log_bet changes it; the caller saves it after the turn. */
  user: UserRecord;
  now: Date;
  /** The per-user context block for this turn. */
  context: string;
  /** Screenshots uploaded in this turn, by id. */
  readImage?: (imageId: string) => Promise<unknown>;
  newId?: () => string;
};

type ToolLeg = { player: string | null; market: string | null; threshold: number | null; side: string | null; odds: number | null };
const toInput = (legs: ToolLeg[]): SlipLegInput[] =>
  (Array.isArray(legs) ? legs : []).map((l) => ({
    player: l.player,
    market: l.market && (MARKET_VALUES as readonly string[]).includes(l.market) && l.market !== "other" ? (l.market as Market) : null,
    threshold: l.threshold, side: l.side === "under" ? "under" : l.market === null ? null : ("over" as Side), odds: l.odds,
  }));

const CARD_KIND: Partial<Record<string, Card["kind"]>> = {
  parse_slip: "slip", grade_slip: "audit", suggest_changes: "changes", size_bet: "stake", get_algo_picks: "picks", get_bankroll: "bankroll", log_bet: "logged", get_user_history: "history",
};

async function runAdvisorTool(name: string, input: unknown, ctx: AdvisorContext): Promise<unknown> {
  const a = (input ?? {}) as Record<string, unknown>;
  const sport = a.sport as Sport;
  const money = ctx.user.account ? { account: ctx.user.account, tonight: tonightFrom(ctx.user.bets, ctx.now), now: ctx.now } : {};
  const needCatalog = () => {
    const c = ctx.catalogs[sport];
    if (!c) throw new Error(`The ${sport} algorithm's output is not loaded. Covered sports: ${Object.keys(ctx.catalogs).join(", ") || "none"}.`);
    return c;
  };
  switch (name) {
    case "parse_slip":
      if (!ctx.readImage) throw new Error("Reading screenshots is not available here.");
      return parseSlipFromJson(await ctx.readImage(String(a.image_id)));
    case "grade_slip":
      return gradeSlipTool(a as unknown as GradeArgs, ctx.catalogs, money);
    case "suggest_changes":
      return suggestChangesTool(a as unknown as SuggestArgs, ctx.catalogs, money);
    case "get_algo_picks": {
      const index = ctx.picks[sport];
      if (!index) return { sport, picks: [], note: `The ${sport} algorithm's output is not loaded. There is nothing to recommend.` };
      return algoPicks(index, (a.date as string | null) || null, (a.game as string | null) || null);
    }
    case "get_odds": {
      const index = ctx.picks[sport];
      if (!index) return { found: false, note: `The ${sport} algorithm's output is not loaded.` };
      return oddsFor(index, String(a.game ?? ""), (a.market as string | null) || null);
    }
    case "get_bankroll":
      return bankrollStatus(ctx.user, ctx.now);
    case "size_bet":
      return sizeBetFor(ctx.user, toInput(a.legs as ToolLeg[]), (a.total_odds as number | null) ?? null, needCatalog(), ctx.now);
    case "log_bet":
      return logBetFor(ctx.user, { sport, legs: toInput(a.legs as ToolLeg[]), totalOdds: (a.total_odds as number | null) ?? null, stakeDollars: Number(a.stake_dollars), book: (a.book as string | null) ?? null },
                       ctx.catalogs[sport], ctx.now, ctx.newId);
    case "get_user_history":
      return userHistory(ctx.user);
    case "get_player_intel":
    case "get_game_intel": {
      const intel = ctx.intel[sport];
      if (!intel) return { found: false, reason: `The ${sport} algorithm's output is not loaded.` };
      return name === "get_player_intel" ? playerIntel(String(a.player ?? ""), intel, ctx.catalogs[sport]) : gameIntel(String(a.game ?? ""), intel);
    }
    default:
      throw new Error(`Unknown tool: ${name}`);
  }
}

/** Tool results are sent to four decimal places: enough for any figure the advisor quotes. */
function compact(result: unknown): string {
  return JSON.stringify(result, (_k, v) => (typeof v === "number" && !Number.isInteger(v) ? Math.round(v * 10000) / 10000 : v));
}

// ---------- the turn ----------
export type TurnEvent =
  | { type: "text"; delta: string }
  | { type: "tool"; name: string }
  | { type: "card"; card: Card }
  /** Discard the text streamed so far in this turn: the reply failed the check and is being rewritten. */
  | { type: "retract" }
  | { type: "notice"; message: string };

export type TurnResult = {
  /** The conversation including this turn, to send back next time. */
  messages: ChatMessage[];
  ended: "answered" | "refused" | "cut-off" | "too-many-rounds" | "withheld";
  /** The text the user was shown. */
  reply: string;
  cards: Card[];
  usage: TokenUsage;
  /** What the reply check found, for logging. */
  guard: { rewrites: number; violations: Violation[] };
};

const textOf = (content: BetaContentBlock[]) => content.filter((b) => b.type === "text").map((b) => (b as { text: string }).text).join("");

/**
 * Run one turn: the user's message is already the last entry in `messages`.
 * Tool calls from one model reply are run together and all their results go back in a single message.
 */
export async function runAdvisorTurn(messages: ChatMessage[], ctx: AdvisorContext, callModel: CallModel, onEvent: (e: TurnEvent) => void = () => {}): Promise<TurnResult> {
  const convo = [...messages];
  const cards: Card[] = [];
  let usage = NO_USAGE;
  let rewrites = 0;
  const allViolations: Violation[] = [];
  const done = (ended: TurnResult["ended"], reply: string): TurnResult => ({ messages: convo, ended, reply, cards, usage, guard: { rewrites, violations: allViolations } });

  for (let round = 0; round < ADVISOR_CONFIG.maxRounds; round++) {
    const reply = await callModel({ system: ADVISOR_SYSTEM_PROMPT, context: ctx.context, tools: ADVISOR_TOOLS, messages: convo }, (delta) => onEvent({ type: "text", delta }));
    if (reply.usage) usage = addUsage(usage, reply.usage);
    const content = reply.content as BetaContentBlock[];
    // Keep the whole reply, thinking blocks included: the API needs them back unchanged on the next request.
    convo.push({ role: "assistant", content: content as BetaContentBlockParam[] });
    if (reply.stop_reason === "refusal") {
      onEvent({ type: "notice", message: "The advisor could not answer that one. Try asking it another way." });
      return done("refused", "");
    }
    if (reply.stop_reason === "pause_turn") continue;
    const calls = content.filter((b): b is BetaToolUseBlock => b.type === "tool_use");
    if (reply.stop_reason === "max_tokens") {
      // a tool call cut off mid-input must not be run; drop it so the history stays valid
      if (calls.length) convo[convo.length - 1] = { role: "assistant", content: content.filter((b) => b.type !== "tool_use") as BetaContentBlockParam[] };
      onEvent({ type: "notice", message: "That answer was cut off for length. Ask for the rest, or ask a narrower question." });
      return done("cut-off", textOf(content));
    }

    if (calls.length === 0) {
      // the answer: nothing reaches the user as final until its figures and picks trace back to a tool
      const text = textOf(content);
      const violations = checkReply(text, factsFrom(convo, ctx.context));
      if (!violations.length) return done("answered", text);
      allViolations.push(...violations);
      onEvent({ type: "retract" });
      if (rewrites < ADVISOR_CONFIG.maxRewrites) {
        rewrites++;
        convo.push({ role: "user", content: correctionNote(violations) });
        continue;
      }
      convo.push({ role: "assistant", content: SAFE_REPLY });
      onEvent({ type: "text", delta: SAFE_REPLY });
      return done("withheld", SAFE_REPLY);
    }

    const results = await Promise.all(calls.map(async (call): Promise<BetaToolResultBlockParam> => {
      onEvent({ type: "tool", name: call.name });
      try {
        const result = await runAdvisorTool(call.name, call.input, ctx);
        const kind = CARD_KIND[call.name];
        if (kind) {
          const card: Card = { kind, data: JSON.parse(compact(result)) };
          cards.push(card);
          onEvent({ type: "card", card });
        }
        return { type: "tool_result", tool_use_id: call.id, content: compact(result) };
      } catch (error) {
        // a failed tool still gets a result, marked as an error, so the model can tell the user what could not be done
        return { type: "tool_result", tool_use_id: call.id, is_error: true, content: error instanceof Error ? error.message : "The tool failed." };
      }
    }));
    convo.push({ role: "user", content: results });
    // any words the model wrote before calling tools were only a lead-in; the answer comes after the results
    if (textOf(content)) onEvent({ type: "retract" });
  }
  onEvent({ type: "notice", message: "The advisor needed too many steps for that. Try a narrower question." });
  return done("too-many-rounds", "");
}

/**
 * The conversation to keep after a turn: screenshots are replaced by a short note (they are large, and
 * the legs read from them are already in the tool results), and very long histories lose their oldest turns.
 */
export function trimHistory(messages: ChatMessage[]): ChatMessage[] {
  const light = messages.map((m): ChatMessage => {
    if (typeof m.content === "string") return m;
    return { ...m, content: m.content.map((b) => (b.type === "image" ? { type: "text" as const, text: "[bet slip screenshot, already read]" } : b)) };
  });
  if (light.length <= ADVISOR_CONFIG.maxHistory) return light;
  // cut at a user message that starts a turn (plain text, not tool results), so no tool call loses its result
  let start = light.length - ADVISOR_CONFIG.maxHistory;
  const startsTurn = (m: ChatMessage) =>
    m.role === "user" && (typeof m.content === "string" ? !m.content.startsWith("[Automatic check]") : m.content.every((b) => b.type !== "tool_result"));
  while (start < light.length && !startsTurn(light[start])) start++;
  return start < light.length ? light.slice(start) : light;
}
