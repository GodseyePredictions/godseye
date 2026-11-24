/**
 * A scripted stand-in for Claude, for running the advisor without an API key.
 *
 * Enabled only when ADVISOR_DEMO=1. It is NOT the advisor: it follows a fixed script (read a slip, confirm,
 * grade, suggest a swap, size a stake, show picks, show the bankroll) and understands nothing else.
 * What it does exercise for real is everything around the model: the tools, the algorithms' numbers,
 * the bankroll engine, the reply check, the cards, memory and limits. Use it to try the app and for
 * end-to-end tests; judge the advisor's actual conversation only with the real model.
 */
import { createHash } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import type { CallModel, ChatMessage, ModelReply } from "./agent.ts";

type Block = { type: string; [k: string]: unknown };
const blocks = (m: ChatMessage): Block[] => (typeof m.content === "string" ? [{ type: "text", text: m.content }] : (m.content as unknown as Block[]));
const pct = (p: number) => `${(p * 100).toFixed(1)}%`;

/** The most recent result of a tool in the conversation, parsed. */
function lastResult(messages: ChatMessage[], tool: string): Record<string, unknown> | null {
  const names = new Map<string, string>();
  for (const m of messages) if (m.role === "assistant") for (const b of blocks(m)) if (b.type === "tool_use") names.set(String(b.id), String(b.name));
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role !== "user") continue;
    for (const b of blocks(messages[i]))
      if (b.type === "tool_result" && names.get(String(b.tool_use_id)) === tool && !b.is_error) {
        try { return JSON.parse(String(b.content)); } catch { return null; }
      }
  }
  return null;
}

type Leg = { player: string | null; market: string | null; threshold: number | null; side: string | null; odds: number | null };
const draftLegs = (draft: Record<string, unknown>): Leg[] =>
  ((draft.legs as Record<string, unknown>[]) ?? []).map((l) => ({
    player: (l.player as string) ?? null, market: l.market === "other" ? null : ((l.market as string) ?? null), threshold: (l.threshold as number) ?? null,
    side: (l.side as string) ?? null, odds: (l.odds as number) ?? null,
  }));
const ratedLegs = (legs: Record<string, unknown>[]): Leg[] => legs.map((l) => ({ player: l.player as string, market: l.market as string, threshold: (l.threshold as number) ?? null, side: "over", odds: null }));
const legName = (l: Record<string, unknown>) => `${l.player} ${l.market === "atd" ? "anytime touchdown" : `${l.threshold}+ ${String(l.market).replace("_", " ")}`}`;

let n = 0;
const say = (text: string): ModelReply => ({ content: [{ type: "text", text, citations: null }] as ModelReply["content"], stop_reason: "end_turn" });
const call = (name: string, input: unknown): ModelReply => ({ content: [{ type: "tool_use", id: `demo_${++n}`, name, input }] as ModelReply["content"], stop_reason: "tool_use" });

export const demoModel: CallModel = async (request, onText) => {
  const reply = respond(request.messages, request.system.startsWith("You keep the notes"));
  for (const b of reply.content) if (b.type === "text") for (const piece of b.text.match(/[\s\S]{1,18}/g) ?? []) { onText(piece); await new Promise((r) => setTimeout(r, 12)); }
  return { ...reply, usage: { inputTokens: 0, outputTokens: 0, cacheReadTokens: 0, cacheWriteTokens: 0 } };
};

function respond(messages: ChatMessage[], isSummary: boolean): ModelReply {
  if (isSummary) return say("Has tried the advisor in demo mode. Uploads same-game parlay screenshots, asks for swaps and wants stakes sized from the bankroll engine.");
  const last = messages[messages.length - 1];
  const lastBlocks = blocks(last);
  const sport = "NFL";

  // ---- a tool has just answered: say what it means
  if (lastBlocks.some((b) => b.type === "tool_result")) {
    const names = new Map<string, string>();
    for (const m of messages) if (m.role === "assistant") for (const b of blocks(m)) if (b.type === "tool_use") names.set(String(b.id), String(b.name));
    const tool = names.get(String(lastBlocks.find((b) => b.type === "tool_result")!.tool_use_id));
    const r = tool ? lastResult(messages, tool) : null;
    if (!r) return say("That did not work. Try again, or attach the slip once more.");
    if (tool === "parse_slip") {
      const legs = (r.legs as Record<string, unknown>[]) ?? [];
      if (!legs.length) return say("I could not read a slip in that image. In demo mode I can only read the sample slips in fixtures/slips.");
      return say(`I read ${legs.length === 1 ? "one leg" : `these legs`} from ${r.book ?? "your book"}: ${legs.map((l) => [l.player, l.marketText].filter(Boolean).join(" ")).join("; ")}. Is this your slip? Say yes and I will grade it, or tell me what to fix.`);
    }
    if (tool === "grade_slip") {
      const rules = ((r.rules as { level: string; detail: string }[]) ?? []).filter((x) => x.level === "warn");
      const joint = r.joint as number | null;
      return say([
        joint === null ? "The algorithm cannot state a chance for this slip as a whole." : `The algorithm makes this slip ${pct(joint)} to hit.`,
        r.value !== null && r.value !== undefined ? ((r.value as number) > 0 ? "At your price that is good value." : "At your price it does not pay enough.") : String(r.valueNote ?? ""),
        rules.length ? `One thing is wrong with it: ${rules[0].detail}` : "It passes the ticket rules.",
        "The card above has every leg. Want me to look for a better version?",
      ].join(" "));
    }
    if (tool === "suggest_changes") {
      const swaps = (r.swap as { from: Record<string, unknown>; to: Record<string, unknown> }[]) ?? [];
      const imp = r.improved as { joint: number | null } | null;
      if (!imp) return say("The algorithm has nothing to change on this slip.");
      return say([
        swaps.length ? `Swap ${legName(swaps[0].from)} for ${legName(swaps[0].to)}.` : "I would drop the legs marked on the card.",
        imp.joint !== null ? `That version is ${pct(imp.joint)} to hit.` : "",
        "Check your book lists that rung, then tell me the new price and I will size the stake.",
      ].filter(Boolean).join(" "));
    }
    if (tool === "size_bet") {
      const s = r.stake as { status: string; label: string; reason: string };
      return say(s.status === "bet" ? `Stake ${s.label}. ${s.reason}` : `No stake on this one. ${s.reason}`);
    }
    if (tool === "get_algo_picks") {
      const picks = (r.picks as { kind: string; game: string; joint_probability: number | null; legs: { leg: string }[] }[]) ?? [];
      if (!picks.length) return say(`${r.note} I have nothing to recommend.`);
      const top = [...picks].sort((a, b) => (b.joint_probability ?? 0) - (a.joint_probability ?? 0))[0];
      return say(`The algorithm's strongest ticket right now is the ${top.kind} in ${top.game}${top.joint_probability !== null ? `, ${pct(top.joint_probability)} to hit` : ""}. All ${picks.length} are on the card above.`);
    }
    if (tool === "get_bankroll") return say(r.set ? (r.limit_in_force ? String(r.limit_message) : `Your bankroll is $${r.bankroll_dollars} and one unit is $${r.unit_dollars}. You have $${r.room_left_tonight_dollars} of room left tonight.`) : String(r.note));
    if (tool === "log_bet") return say(r.logged ? "Logged. It now counts toward tonight and will be re-checked if the algorithm's numbers change." : String(r.reason));
    if (tool === "get_user_history") return say(String(r.note ?? "Your history is on the card above."));
    return say("Done.");
  }

  // ---- a new message from the user
  const text = lastBlocks.filter((b) => b.type === "text").map((b) => String(b.text)).join(" ");
  const lower = text.toLowerCase();
  if (text.includes("image_id for parse_slip")) return call("parse_slip", { image_id: "slip-1" });
  const draft = lastResult(messages, "parse_slip");
  const changes = lastResult(messages, "suggest_changes");
  const priceMatch = /([+-]\d{3,5})/.exec(text);
  const price = priceMatch ? Number(priceMatch[1]) : null;

  if (/\b(placed|log (it|this|that))\b/.test(lower) && draft) {
    const stake = /\$\s?(\d+(?:\.\d+)?)/.exec(text);
    const imp = (changes?.improved as { legs: Record<string, unknown>[] } | null) ?? null;
    return stake ? call("log_bet", { sport, legs: imp ? ratedLegs(imp.legs) : draftLegs(draft), total_odds: price ?? (draft.totalOdds as number | null) ?? null, stake_dollars: Number(stake[1]), book: (draft.book as string) ?? null })
      : say("What did you stake on it? Give me the dollar amount and I will log it.");
  }
  if (price !== null && changes?.improved) return call("size_bet", { sport, legs: ratedLegs((changes.improved as { legs: Record<string, unknown>[] }).legs), total_odds: price });
  if (/\b(stake|how much|size)\b/.test(lower) && draft) return call("size_bet", { sport, legs: draftLegs(draft), total_odds: price ?? (draft.totalOdds as number | null) ?? null });
  if (/\b(swap|improve|better|change|fix)\b/.test(lower) && draft) return call("suggest_changes", { sport, legs: draftLegs(draft), total_odds: (draft.totalOdds as number | null) ?? null, leg_count: null, book: (draft.book as string) ?? null });
  if (/^(yes|yep|yeah|correct|that'?s (it|right)|confirm|looks right)/.test(lower.trim()) && draft) return call("grade_slip", { sport, legs: draftLegs(draft), total_odds: (draft.totalOdds as number | null) ?? null });
  if (/\b(bankroll|unit|limit)\b/.test(lower)) return call("get_bankroll", {});
  if (/\b(history|record|how (am|have) i)\b/.test(lower)) return call("get_user_history", {});
  if (/\b(pick|picks|play|tonight|today)\b/.test(lower)) return call("get_algo_picks", { sport: /\bnba\b/.test(lower) ? "NBA" : sport, date: null, game: null });
  return say("This is demo mode: a scripted stand-in, not the real advisor. Attach a sample slip from fixtures/slips, or ask for picks, your bankroll or your history.");
}

/** In demo mode, a screenshot is "read" only if it is one of the sample slips, by returning its expected reading. */
export async function demoReadImage(image: { data: Uint8Array }): Promise<unknown> {
  const dir = path.join(process.cwd(), "fixtures/slips");
  const hash = createHash("sha256").update(image.data).digest("hex");
  for (const f of readdirSync(dir).filter((x) => x.endsWith(".png"))) {
    if (createHash("sha256").update(readFileSync(path.join(dir, f))).digest("hex") === hash)
      return JSON.parse(readFileSync(path.join(dir, f.replace(/\.png$/, ".expected.json")), "utf8"));
  }
  return { is_bet_slip: false, book: null, bet_type: "unknown", legs: [], total_odds_text: null, stake_text: null, unreadable: ["demo mode reads only the sample slips in fixtures/slips"] };
}

export const demoEnabled = (env: Record<string, string | undefined> = process.env) => env.ADVISOR_DEMO === "1";
