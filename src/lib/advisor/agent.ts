/**
 * The 1-to-1 chat advisor: one conversation turn.
 *
 * The advisor reads screenshots, calls tools and explains results. It never does the maths itself:
 * every probability, edge, joint chance and stake it repeats comes back from a tool, and the tools read
 * the algorithms' output and call the staking engine. Its instructions tell it so, and the tools return
 * null (never an estimate) wherever the algorithms have no number.
 *
 * `runAdvisorTurn` is the loop: send the conversation, run any tools the model asks for, send the
 * results back, repeat until it answers. The model call is passed in, so the loop is tested without
 * the network and the server decides how to call the API (src/lib/advisor/claude.ts).
 */
import type {
  BetaContentBlock, BetaContentBlockParam, BetaMessage, BetaToolResultBlockParam, BetaToolUseBlock,
} from "@anthropic-ai/sdk/resources/beta/messages/messages";
import { TOOLS as SLIP_TOOLS, runTool, type Catalogs, type Money } from "../slip/tools.ts";
import { gameIntel, playerIntel, type Intel } from "./intel.ts";
import type { Sport } from "./legs.ts";

/** A user or assistant message, in the shape the Messages API takes. */
export type ChatMessage = { role: "user" | "assistant"; content: string | BetaContentBlockParam[] };
export type ModelReply = Pick<BetaMessage, "content" | "stop_reason">;
/** One call to the model. `onText` receives the answer as it is written. */
export type CallModel = (request: { system: string; tools: readonly unknown[]; messages: ChatMessage[] }, onText: (delta: string) => void) => Promise<ModelReply>;

export const ADVISOR_CONFIG = {
  /** Tool rounds allowed in one turn before the advisor must answer with what it has. */
  maxRounds: 8,
  /** Earlier messages kept when a conversation grows long. */
  maxHistory: 40,
};

const INTEL_TOOLS = [
  {
    name: "get_player_intel",
    description:
      "Everything the Godseye algorithm has on one player for the current slate: the milestone ladder with the algorithm's probability for each rung, " +
      "how often each was cleared this season, the anytime-touchdown probability (NFL), projected minutes and stat lines (NBA), role, injury designation, " +
      "and the algorithm's own reasons and risk notes. Call it when the user asks about a player, wants a safer or bolder rung, or asks why the algorithm rates a leg as it does. " +
      "If the player is not on the slate it says so; treat that as unrated.",
    strict: true,
    input_schema: {
      type: "object", additionalProperties: false, required: ["sport", "player"],
      properties: { sport: { type: "string", enum: ["NFL", "NBA"] }, player: { type: "string", description: "The player's name as the user gave it." } },
    },
  },
  {
    name: "get_game_intel",
    description:
      "The Godseye algorithm's read on one game: the market line, weather and venue (NFL), pace and blowout probability (NBA), the algorithm's game-script notes, " +
      "and official availability. Call it before discussing any player prop in that game, because game script and blowout risk come before the props, " +
      "and whenever the user asks about a matchup, the weather, or who is out.",
    strict: true,
    input_schema: {
      type: "object", additionalProperties: false, required: ["sport", "game"],
      properties: { sport: { type: "string", enum: ["NFL", "NBA"] }, game: { type: "string", description: 'The matchup or one team, e.g. "BUF @ KC" or "Giants".' } },
    },
  },
] as const;

export const ADVISOR_TOOLS = [...SLIP_TOOLS, ...INTEL_TOOLS] as const;

export type AdvisorContext = {
  catalogs: Catalogs;
  intel: Partial<Record<Sport, Intel>>;
  money?: Money;
  /** Screenshots uploaded in this turn, by id. */
  readImage?: (imageId: string) => Promise<unknown>;
};

export function advisorSystemPrompt(ctx: { sports: Sport[]; hasBankroll: boolean; built: Partial<Record<Sport, string>> }): string {
  return `You are the Godseye advisor, a one-to-one betting advisor inside Godseye Predictions, a paid service built on its own statistical algorithms for ${ctx.sports.join(" and ")}. The person you are talking to is a subscriber deciding what, if anything, to bet. Your job is to help them reach an informed decision of their own: show them what the algorithm says, what it does not know, and what that means for the bet in front of them.

Where your numbers come from
Every probability, edge, joint chance, fair price and stake you state must come from a tool result in this conversation. The tools read the algorithms' output and the bankroll engine, which is why subscribers pay for this service; a number you estimated, remembered or worked out yourself would look identical to them and would be wrong to present as Godseye's. So do no arithmetic on probabilities or stakes: do not multiply legs together, average, round to a nearby milestone or convert a chance into a price. If a tool returns null, "unrated" or "not stated" for something, tell the user plainly that the algorithm has no number for it and why, and carry on with what is known. Your general knowledge of players and teams is not algorithm output: do not offer it as a pick, a lean or a reason to bet. The only picks, legs, swaps and adds you suggest are ones a tool returned.

Each sport has its own algorithm and its own ticket rules. Do not apply an NFL rule to an NBA slip or the reverse; the tools apply the right rules for the sport you pass.

Working with a slip
When the user shares a screenshot, call parse_slip, then show them the legs you read and ask them to confirm or correct them. Grade only after they confirm, because grading the wrong player or number would mislead them. If a field could not be read, ask for it. Then call grade_slip, and suggest_changes when they want to know what to change. Before discussing a prop, look at the game with get_game_intel: game script and blowout risk come first. Suggested rungs come from the algorithm's ladder, not from the sportsbook, so ask the user to check their book offers the rung and to tell you the new price before you talk about value or a stake for a changed slip.

Stakes
Stakes come only from the bankroll engine through the tools, shown in units and dollars such as "1.5u ($15)". ${ctx.hasBankroll ? "This user has a bankroll set." : "This user has not set a bankroll yet, so the tools return no stake: point them to the Bankroll Strategy tab rather than suggesting an amount."} If the engine says a limit is in force (stop-loss, profit lock, nightly cap or cool-off), respect it: say so and do not look for a way around it.

How to talk
Be direct and plain, like a sharp friend who knows the numbers. Lead with the answer, then the two or three facts that matter most, and say what would change your read. Say clearly when the algorithm does not like a bet, including one the user is excited about. Never promise or imply a win, a lock or a guaranteed night: a well-priced bet still loses often and a parlay loses more often than it wins, and it is fine to say "no bet" or "pass". If the user seems to be chasing losses, betting money they cannot afford to lose, or asks you to help get around a limit they set, slow down, say what you are noticing, and mention the cool-off in Bankroll Strategy. Do not report past results or records; they are not shown in this product.

Write in short paragraphs of plain text. The chat window does not render markdown, so do not use headings, tables, bold markers or bullet symbols. Keep most replies under 150 words unless the user asks for the full breakdown.

The algorithm output loaded right now: ${ctx.sports.map((s) => `${s} built ${ctx.built[s] || "at an unknown time"}`).join("; ")}. If the user asks about a game that has already started or a slate that is not loaded, say the algorithm has no current numbers for it.`;
}

async function runAdvisorTool(name: string, input: unknown, ctx: AdvisorContext): Promise<unknown> {
  if (name === "get_player_intel" || name === "get_game_intel") {
    const a = input as { sport: Sport; player?: string; game?: string };
    const intel = ctx.intel[a.sport];
    if (!intel) return { found: false, reason: `The ${a.sport} algorithm's output is not loaded.` };
    return name === "get_player_intel" ? playerIntel(String(a.player ?? ""), intel, ctx.catalogs[a.sport]) : gameIntel(String(a.game ?? ""), intel);
  }
  return runTool(name, input, { catalogs: ctx.catalogs, money: ctx.money, readImage: ctx.readImage });
}

/** Simulation arrays and other bulk are no use to the model; keep tool results compact. */
function compact(result: unknown): string {
  return JSON.stringify(result, (_k, v) => (typeof v === "number" && !Number.isInteger(v) ? Math.round(v * 10000) / 10000 : v));
}

export type TurnEvent = { type: "text"; delta: string } | { type: "tool"; name: string } | { type: "notice"; message: string };
export type TurnResult = {
  /** The conversation including this turn, to send back next time. */
  messages: ChatMessage[];
  /** Why the turn ended. */
  ended: "answered" | "refused" | "cut-off" | "too-many-rounds";
};

/**
 * Run one turn: the user's message is already the last entry in `messages`.
 * Tool calls from one model reply are run together and all their results go back in a single message.
 */
export async function runAdvisorTurn(messages: ChatMessage[], ctx: AdvisorContext, callModel: CallModel, onEvent: (e: TurnEvent) => void = () => {}): Promise<TurnResult> {
  const sports = (Object.keys(ctx.catalogs) as Sport[]).filter((s) => ctx.catalogs[s]);
  const system = advisorSystemPrompt({
    sports, hasBankroll: !!ctx.money?.account && ctx.money.account.bankroll > 0,
    built: Object.fromEntries(sports.map((s) => [s, ctx.catalogs[s]!.built])),
  });
  const convo = [...messages];
  for (let round = 0; round < ADVISOR_CONFIG.maxRounds; round++) {
    const reply = await callModel({ system, tools: ADVISOR_TOOLS, messages: convo }, (delta) => onEvent({ type: "text", delta }));
    // Keep the whole reply, thinking blocks included: the API needs them back unchanged on the next request.
    convo.push({ role: "assistant", content: reply.content as BetaContentBlockParam[] });
    if (reply.stop_reason === "refusal") {
      onEvent({ type: "notice", message: "The advisor could not answer that one. Try asking it another way." });
      return { messages: convo, ended: "refused" };
    }
    if (reply.stop_reason === "pause_turn") continue;
    const calls = reply.content.filter((b): b is BetaToolUseBlock => b.type === "tool_use");
    if (reply.stop_reason === "max_tokens") {
      // a tool call cut off mid-input must not be run; drop it so the history stays valid
      if (calls.length) convo[convo.length - 1] = { role: "assistant", content: (reply.content as BetaContentBlock[]).filter((b) => b.type !== "tool_use") as BetaContentBlockParam[] };
      onEvent({ type: "notice", message: "That answer was cut off for length. Ask for the rest, or ask a narrower question." });
      return { messages: convo, ended: "cut-off" };
    }
    if (calls.length === 0) return { messages: convo, ended: "answered" };

    const results = await Promise.all(calls.map(async (call): Promise<BetaToolResultBlockParam> => {
      onEvent({ type: "tool", name: call.name });
      try {
        return { type: "tool_result", tool_use_id: call.id, content: compact(await runAdvisorTool(call.name, call.input, ctx)) };
      } catch (error) {
        // a failed tool still gets a result, marked as an error, so the model can tell the user what could not be done
        return { type: "tool_result", tool_use_id: call.id, is_error: true, content: error instanceof Error ? error.message : "The tool failed." };
      }
    }));
    convo.push({ role: "user", content: results });
  }
  onEvent({ type: "notice", message: "The advisor needed too many steps for that. Try a narrower question." });
  return { messages: convo, ended: "too-many-rounds" };
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
  const startsTurn = (m: ChatMessage) => m.role === "user" && (typeof m.content === "string" || m.content.every((b) => b.type !== "tool_result"));
  while (start < light.length && !startsTurn(light[start])) start++;
  return start < light.length ? light.slice(start) : light;
}
