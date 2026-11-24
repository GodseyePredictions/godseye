import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  ADVISOR_CONFIG, ADVISOR_TOOLS, advisorSystemPrompt, runAdvisorTurn, trimHistory,
  type AdvisorContext, type CallModel, type ChatMessage, type ModelReply, type TurnEvent,
} from "./advisor/agent.ts";
import { gameIntel, nbaIntel, nflIntel, playerIntel } from "./advisor/intel.ts";
import { nbaCatalog, nflCatalog, parseConsoleData } from "./advisor/legs.ts";
import { openAccount } from "./staking.ts";

// ---------- the real output files, so the tools are exercised on real shapes ----------
const nflRaw = parseConsoleData(readFileSync(new URL("../../public/console/data.js", import.meta.url), "utf8"));
const nbaRaw = JSON.parse(readFileSync(new URL("../../model/nba/output/nba_site.json", import.meta.url), "utf8"));
const NOW = new Date("2026-11-25T23:00:00Z");
const ctx: AdvisorContext = {
  catalogs: { NFL: nflCatalog(nflRaw), NBA: nbaCatalog(nbaRaw) },
  intel: { NFL: nflIntel(nflRaw), NBA: nbaIntel(nbaRaw) },
  money: { account: openAccount(1000, "balanced", NOW), tonight: { staked: 0, settledProfit: 0 }, now: NOW },
};
const somePlayer = ctx.catalogs.NFL!.legs.find((l) => l.market === "rec" && l.prob > 0.7)!;

/** A stand-in for the model: replies from a script and records every request it was sent. */
function scripted(replies: ModelReply[]) {
  const requests: { system: string; messages: ChatMessage[] }[] = [];
  const call: CallModel = async (request, onText) => {
    requests.push({ system: request.system, messages: structuredClone(request.messages) });
    const reply = replies[requests.length - 1];
    if (!reply) throw new Error("the script ran out of replies");
    for (const b of reply.content) if (b.type === "text") onText(b.text);
    return reply;
  };
  return { call, requests };
}
const text = (t: string) => ({ type: "text", text: t, citations: null }) as ModelReply["content"][number];
const use = (id: string, name: string, input: unknown) => ({ type: "tool_use", id, name, input }) as ModelReply["content"][number];
const thinking = { type: "thinking", thinking: "", signature: "sig-abc" } as ModelReply["content"][number];
const user = (t: string): ChatMessage => ({ role: "user", content: t });
const leg = { player: somePlayer.player, market: somePlayer.market, threshold: somePlayer.threshold, side: "over", odds: -200 };

// ---------- the loop ----------
test("a plain answer ends the turn", async () => {
  const m = scripted([{ content: [text("No bet there.")], stop_reason: "end_turn" }]);
  const events: TurnEvent[] = [];
  const r = await runAdvisorTurn([user("thoughts?")], ctx, m.call, (e) => events.push(e));
  assert.equal(r.ended, "answered");
  assert.equal(r.messages.length, 2);
  assert.deepEqual(events, [{ type: "text", delta: "No bet there." }]);
});

test("a tool call is run and its result goes back to the model", async () => {
  const m = scripted([
    { content: [thinking, use("t1", "grade_slip", { sport: "NFL", legs: [leg], total_odds: null })], stop_reason: "tool_use" },
    { content: [text("Graded.")], stop_reason: "end_turn" },
  ]);
  const events: TurnEvent[] = [];
  const r = await runAdvisorTurn([user("grade this")], ctx, m.call, (e) => events.push(e));
  assert.equal(r.ended, "answered");
  assert.deepEqual(events.filter((e) => e.type === "tool"), [{ type: "tool", name: "grade_slip" }]);
  // the second request carries the assistant turn unchanged (thinking block included) and one tool result
  const second = m.requests[1].messages;
  assert.deepEqual((second[1].content as unknown[])[0], thinking);
  const results = second[2].content as { type: string; tool_use_id: string; content: string; is_error?: boolean }[];
  assert.equal(results.length, 1);
  assert.equal(results[0].tool_use_id, "t1");
  const graded = JSON.parse(results[0].content);
  assert.equal(graded.legs[0].prob, Math.round(somePlayer.prob * 10000) / 10000); // the algorithm's number, to four places
  assert.equal(graded.stake.status, "bet"); // sized by the bankroll engine
});

test("several tool calls in one reply are answered together in a single message", async () => {
  const m = scripted([
    { content: [use("a", "get_player_intel", { sport: "NFL", player: somePlayer.player }), use("b", "get_game_intel", { sport: "NFL", game: somePlayer.game })], stop_reason: "tool_use" },
    { content: [text("Here is the read.")], stop_reason: "end_turn" },
  ]);
  await runAdvisorTurn([user("tell me about him")], ctx, m.call);
  const results = m.requests[1].messages[2].content as { tool_use_id: string; content: string }[];
  assert.deepEqual(results.map((r) => r.tool_use_id), ["a", "b"]);
  assert.equal(JSON.parse(results[0].content).found, true);
  assert.equal(JSON.parse(results[1].content).data.game, somePlayer.game);
});

test("a tool that fails still gets a result, marked as an error", async () => {
  const m = scripted([
    { content: [use("x", "grade_slip", { sport: "CFB", legs: [leg], total_odds: null }), use("y", "parse_slip", { image_id: "slip-1" })], stop_reason: "tool_use" },
    { content: [text("I could not grade that.")], stop_reason: "end_turn" },
  ]);
  const r = await runAdvisorTurn([user("grade my college slip")], ctx, m.call);
  const results = m.requests[1].messages[2].content as { is_error?: boolean; content: string }[];
  assert.equal(results[0].is_error, true);
  assert.match(results[0].content, /CFB/);
  assert.equal(results[1].is_error, true); // no screenshot was attached in this turn
  assert.equal(r.ended, "answered");
});

test("parse_slip reads the screenshot attached to the turn", async () => {
  const expected = JSON.parse(readFileSync(new URL("../../fixtures/slips/bet365-sgp.expected.json", import.meta.url), "utf8"));
  const m = scripted([
    { content: [use("p", "parse_slip", { image_id: "slip-1" })], stop_reason: "tool_use" },
    { content: [text("Is this your slip?")], stop_reason: "end_turn" },
  ]);
  await runAdvisorTurn([user("here is my slip")], { ...ctx, readImage: async (id) => (id === "slip-1" ? expected : Promise.reject(new Error("no image"))) }, m.call);
  const draft = JSON.parse((m.requests[1].messages[2].content as { content: string }[])[0].content);
  assert.equal(draft.legs.length, 4);
  assert.equal(draft.totalOdds, 450);
});

test("a refusal, a cut-off answer and a runaway loop all end cleanly", async () => {
  const refused = await runAdvisorTurn([user("x")], ctx, scripted([{ content: [], stop_reason: "refusal" }]).call);
  assert.equal(refused.ended, "refused");

  const cut = scripted([{ content: [text("Half an ans"), use("z", "grade_slip", { sport: "NFL" })], stop_reason: "max_tokens" }]);
  const cutResult = await runAdvisorTurn([user("x")], ctx, cut.call);
  assert.equal(cutResult.ended, "cut-off");
  assert.equal(cut.requests.length, 1); // the half-written tool call is never run
  assert.equal((cutResult.messages[1].content as { type: string }[]).some((b) => b.type === "tool_use"), false);

  const loop = scripted(Array.from({ length: 20 }, (_, i) => ({ content: [use(`l${i}`, "get_game_intel", { sport: "NFL", game: "nowhere" })], stop_reason: "tool_use" as const })));
  const looped = await runAdvisorTurn([user("x")], ctx, loop.call);
  assert.equal(looped.ended, "too-many-rounds");
  assert.equal(loop.requests.length, ADVISOR_CONFIG.maxRounds);
  // every tool call in the history has its result, so the conversation can continue
  const last = looped.messages[looped.messages.length - 1];
  assert.equal(last.role, "user");
});

// ---------- instructions and tools ----------
test("the instructions carry the non-negotiable rules", () => {
  const p = advisorSystemPrompt({ sports: ["NFL", "NBA"], hasBankroll: false, built: { NFL: "Tue", NBA: "Mon" } });
  for (const phrase of ["must come from a tool result", "do no arithmetic", "has no number for it", "its own ticket rules", "confirm or correct", "Never promise", "cool-off", "has not set a bankroll"])
    assert.ok(p.includes(phrase), phrase);
  assert.ok(advisorSystemPrompt({ sports: ["NFL"], hasBankroll: true, built: {} }).includes("has a bankroll set"));
  assert.equal(/guaranteed (win|night)s? (are|is) /i.test(p), false);
});

test("the instructions are the same from one request to the next, so they can be cached", () => {
  const a = scripted([{ content: [text("a")], stop_reason: "end_turn" }]);
  const b = scripted([{ content: [text("b")], stop_reason: "end_turn" }]);
  return Promise.all([runAdvisorTurn([user("one")], ctx, a.call), runAdvisorTurn([user("two"), { role: "assistant", content: "x" }, user("three")], ctx, b.call)])
    .then(() => assert.equal(a.requests[0].system, b.requests[0].system));
});

test("five tools, all with strict schemas", () => {
  assert.deepEqual(ADVISOR_TOOLS.map((t) => t.name), ["parse_slip", "grade_slip", "suggest_changes", "get_player_intel", "get_game_intel"]);
  for (const t of ADVISOR_TOOLS) {
    assert.equal(t.strict, true);
    assert.equal(t.input_schema.additionalProperties, false);
  }
});

// ---------- intel ----------
test("player intel is the algorithm's own, and carries no results", () => {
  const r = playerIntel(somePlayer.player, ctx.intel.NFL!, ctx.catalogs.NFL);
  assert.ok(r.found);
  const d = r.found ? (r.data as Record<string, unknown>) : {};
  const ladder = (d.milestone_ladders as Record<string, { milestone: string; probability: number }[]>)[somePlayer.market];
  assert.equal(ladder.find((x) => x.milestone === `${somePlayer.threshold}+`)!.probability, somePlayer.prob);
  assert.equal(JSON.stringify(ctx.intel.NFL).includes("cashed"), false); // no track record
  assert.equal(/<b>|<\/b>/.test(JSON.stringify(d)), false); // markup stripped
});

test("an unknown or ambiguous player is reported, not guessed", () => {
  assert.equal(playerIntel("Nobody McNothing", ctx.intel.NFL!, ctx.catalogs.NFL).found, false);
  const surnames = ctx.intel.NFL!.players.map((p) => p.player.split(" ").pop()!);
  const shared = surnames.find((s, i) => surnames.indexOf(s) !== i);
  if (shared) {
    const r = playerIntel(shared, ctx.intel.NFL!, ctx.catalogs.NFL);
    assert.equal(r.found, false);
    assert.ok(!r.found && (r.candidates?.length ?? 0) > 1);
  }
});

test("game intel finds a game by matchup or by one team", () => {
  const g = ctx.intel.NFL!.games[0];
  const [away, home] = g.game.split(" @ ");
  for (const q of [g.game, `${away} vs ${home}`, home]) {
    const r = gameIntel(q, ctx.intel.NFL!);
    assert.ok(r.found && r.data.game === g.game, q);
  }
  assert.equal(gameIntel("ZZZ @ QQQ", ctx.intel.NFL!).found, false);
  const nba = ctx.intel.NBA!.games[0];
  const r = gameIntel(nba.game, ctx.intel.NBA!);
  assert.ok(r.found && "blowout_probability" in r.data && Array.isArray((r.data as Record<string, unknown>).availability));
});

// ---------- history ----------
test("screenshots are dropped from the kept history; everything else stays", () => {
  const kept = trimHistory([
    { role: "user", content: [{ type: "image", source: { type: "base64", media_type: "image/png", data: "AAAA" } }, { type: "text", text: "my slip" }] },
    { role: "assistant", content: [thinking, text("Is this your slip?")] as ChatMessage["content"] },
  ]);
  assert.deepEqual(kept[0].content, [{ type: "text", text: "[bet slip screenshot, already read]" }, { type: "text", text: "my slip" }]);
  assert.deepEqual((kept[1].content as unknown[])[0], thinking);
});

test("a long history is cut at the start of a turn, never between a tool call and its result", () => {
  const long: ChatMessage[] = [];
  for (let i = 0; i < 30; i++) {
    long.push(user(`question ${i}`));
    long.push({ role: "assistant", content: [use(`t${i}`, "get_game_intel", { sport: "NFL", game: "x" })] as ChatMessage["content"] });
    long.push({ role: "user", content: [{ type: "tool_result", tool_use_id: `t${i}`, content: "{}" }] });
    long.push({ role: "assistant", content: `answer ${i}` });
  }
  const kept = trimHistory(long);
  assert.ok(kept.length <= ADVISOR_CONFIG.maxHistory);
  assert.equal(kept[0].role, "user");
  assert.equal(typeof kept[0].content, "string");
  assert.equal(kept[kept.length - 1].content, "answer 29");
});
