import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import {
  ADVISOR_CONFIG, ADVISOR_SYSTEM_PROMPT, ADVISOR_TOOLS, runAdvisorTurn, trimHistory, userContext,
  type AdvisorContext, type CallModel, type ChatMessage, type ModelReply, type TurnEvent,
} from "./advisor/agent.ts";
import { demoModel } from "./advisor/demo-model.ts";
import { SAFE_REPLY, checkReply, factsFrom } from "./advisor/guard.ts";
import { gameIntel, nbaIntel, nflIntel, playerIntel } from "./advisor/intel.ts";
import { nbaCatalog, nflCatalog } from "./advisor/legs.ts";
import { clearMemory, pendingSummaries, transcript } from "./advisor/memory.ts";
import { algoPicks, nbaPicks, nflPicks, oddsFor } from "./advisor/picks.ts";
import { handleTurn, readHistory, type ServiceDeps, type ServiceEvent } from "./advisor/service.ts";
import { ADVISOR_LIMITS, applySubscriptionEvent, chatAllowance, effectiveTier, purgeExpiredArchive, visibleConversations } from "./advisor/subscription.ts";
import { costUsd, logUsage, usageTotals } from "./advisor/usage.ts";
import { bankrollStatus, logBetFor, sizeBetFor, userHistory } from "./advisor/user-tools.ts";
import type { Bet } from "./bets.ts";
import { picksOfTheDay } from "./picks-of-day.ts";
import { openAccount } from "./staking.ts";
import { FileStore } from "./store/file.ts";
import { MemoryStore, newUser, validUserId, type UserRecord } from "./store/types.ts";

// ---------- real output, so the tools are exercised on real shapes ----------
// NFL comes from a frozen sample: the live file changes weekly and has no open legs once a week is over.
const nflRaw = JSON.parse(readFileSync(new URL("../../fixtures/algo/nfl-sample.json", import.meta.url), "utf8"));
const nbaRaw = JSON.parse(readFileSync(new URL("../../model/nba/output/nba_site.json", import.meta.url), "utf8"));
const NOW = new Date("2026-11-25T23:00:00Z");
const algo = {
  catalogs: { NFL: nflCatalog(nflRaw), NBA: nbaCatalog(nbaRaw) },
  intel: { NFL: nflIntel(nflRaw), NBA: nbaIntel(nbaRaw) },
  picks: { NFL: nflPicks({ ...nflRaw, algo: { sgp: [], atd: [], atd_combos: [] } }), NBA: nbaPicks(nbaRaw) },
};
const NFL = algo.catalogs.NFL;
const strong = NFL.legs.find((l) => l.market === "rec" && l.prob > 0.8)!;
const second = NFL.legs.find((l) => l.market === "rush_yds" && l.prob > 0.8 && l.gameId === strong.gameId && l.player !== strong.player)!;
const legOf = (l: typeof strong, odds: number | null = null) => ({ player: l.player, market: l.market, threshold: l.threshold, side: "over" as const, odds });

const someone = (over: Partial<UserRecord> = {}): UserRecord => ({ ...newUser("user_test_0001", NOW), account: openAccount(1000, "balanced", NOW), ...over });
const ctxFor = (user: UserRecord, more: Partial<AdvisorContext> = {}): AdvisorContext => ({
  ...algo, user, now: NOW, context: userContext(user, { now: NOW, built: { NFL: NFL.built }, tier: "pro", remainingToday: 19 }), newId: (() => { let i = 0; return () => `id_${++i}`; })(), ...more,
});

/** A stand-in for the model: replies from a script and records every request it was sent. */
function scripted(replies: (ModelReply | ((messages: ChatMessage[]) => ModelReply))[]) {
  const requests: { system: string; context: string; messages: ChatMessage[] }[] = [];
  const call: CallModel = async (request, onText) => {
    requests.push({ system: request.system, context: request.context, messages: structuredClone(request.messages) });
    const next = replies[requests.length - 1];
    if (!next) throw new Error("the script ran out of replies");
    const reply = typeof next === "function" ? next(request.messages) : next;
    for (const b of reply.content) if (b.type === "text") onText(b.text);
    return { usage: { inputTokens: 1000, outputTokens: 200, cacheReadTokens: 0, cacheWriteTokens: 0 }, ...reply };
  };
  return { call, requests };
}
const text = (t: string) => ({ type: "text", text: t, citations: null }) as ModelReply["content"][number];
const use = (id: string, name: string, input: unknown) => ({ type: "tool_use", id, name, input }) as ModelReply["content"][number];
const thinking = { type: "thinking", thinking: "", signature: "sig-abc" } as ModelReply["content"][number];
const answer = (t: string): ModelReply => ({ content: [text(t)], stop_reason: "end_turn" });
const calls = (...c: ModelReply["content"]): ModelReply => ({ content: c, stop_reason: "tool_use" });
const user = (t: string): ChatMessage => ({ role: "user", content: t });
const resultsOf = (m: ChatMessage) => (m.content as { type: string; tool_use_id: string; content: string; is_error?: boolean }[]).filter((b) => b.type === "tool_result");

// ================= the loop =================
test("a plain answer ends the turn", async () => {
  const m = scripted([answer("No bet there.")]);
  const events: TurnEvent[] = [];
  const r = await runAdvisorTurn([user("thoughts?")], ctxFor(someone()), m.call, (e) => events.push(e));
  assert.equal(r.ended, "answered");
  assert.equal(r.reply, "No bet there.");
  assert.deepEqual(events, [{ type: "text", delta: "No bet there." }]);
});

test("a tool call is run, its result goes back to the model, and a card is shown", async () => {
  const m = scripted([calls(thinking, use("t1", "grade_slip", { sport: "NFL", legs: [legOf(strong, -200)], total_odds: null })), answer("Graded.")]);
  const events: TurnEvent[] = [];
  const r = await runAdvisorTurn([user("grade this")], ctxFor(someone()), m.call, (e) => events.push(e));
  assert.equal(r.ended, "answered");
  // the second request carries the assistant turn unchanged (thinking block included) and one tool result
  const second = m.requests[1].messages;
  assert.deepEqual((second[1].content as unknown[])[0], thinking);
  const graded = JSON.parse(resultsOf(second[2])[0].content);
  assert.equal(graded.legs[0].prob, Math.round(strong.prob * 10000) / 10000);
  assert.deepEqual(r.cards.map((c) => c.kind), ["audit"]);
  assert.ok(events.some((e) => e.type === "card"));
});

test("several tool calls in one reply are answered together in a single message", async () => {
  const m = scripted([calls(use("a", "get_player_intel", { sport: "NFL", player: strong.player }), use("b", "get_game_intel", { sport: "NFL", game: strong.game })), answer("Here is the read.")]);
  await runAdvisorTurn([user("tell me about him")], ctxFor(someone()), m.call);
  const results = resultsOf(m.requests[1].messages[2]);
  assert.deepEqual(results.map((r) => r.tool_use_id), ["a", "b"]);
  assert.equal(JSON.parse(results[0].content).found, true);
});

test("a tool that fails still gets a result, marked as an error", async () => {
  const m = scripted([calls(use("x", "grade_slip", { sport: "CFB", legs: [legOf(strong)], total_odds: null }), use("y", "parse_slip", { image_id: "slip-1" })), answer("I could not grade that.")]);
  await runAdvisorTurn([user("grade my college slip")], ctxFor(someone()), m.call);
  const results = resultsOf(m.requests[1].messages[2]);
  assert.equal(results[0].is_error, true);
  assert.match(results[0].content, /CFB/);
  assert.equal(results[1].is_error, true); // no screenshot was attached in this turn
});

test("a refusal, a cut-off answer and a runaway loop all end cleanly", async () => {
  assert.equal((await runAdvisorTurn([user("x")], ctxFor(someone()), scripted([{ content: [], stop_reason: "refusal" }]).call)).ended, "refused");
  const cut = scripted([{ content: [text("Half an ans"), use("z", "grade_slip", { sport: "NFL" })], stop_reason: "max_tokens" }]);
  const cutResult = await runAdvisorTurn([user("x")], ctxFor(someone()), cut.call);
  assert.equal(cutResult.ended, "cut-off");
  assert.equal(cut.requests.length, 1); // the half-written tool call is never run
  const loop = scripted(Array.from({ length: 20 }, (_, i) => calls(use(`l${i}`, "get_game_intel", { sport: "NFL", game: "nowhere" }))));
  const looped = await runAdvisorTurn([user("x")], ctxFor(someone()), loop.call);
  assert.equal(looped.ended, "too-many-rounds");
  assert.equal(loop.requests.length, ADVISOR_CONFIG.maxRounds);
  assert.equal(looped.messages[looped.messages.length - 1].role, "user"); // every tool call has its result
});

// ================= hard rule: picks only from the algorithm =================
test("when the pick tool returns nothing, an invented pick never reaches the user", async () => {
  // a model that ignores its instructions: the tools came back empty and it offers a pick of its own anyway
  const invented = "Nothing from the algorithm today, but I like Patrick Mahomes 275+ passing yards and Travis Kelce anytime touchdown.";
  const m = scripted([calls(use("p", "get_algo_picks", { sport: "NFL", date: null, game: null })), answer(invented), answer(invented)]);
  const events: TurnEvent[] = [];
  const r = await runAdvisorTurn([user("give me a pick for tonight")], ctxFor(someone()), m.call, (e) => events.push(e));
  assert.equal(JSON.parse(resultsOf(m.requests[1].messages[2])[0].content).picks.length, 0);
  assert.equal(r.ended, "withheld");
  assert.equal(r.reply, SAFE_REPLY);
  assert.ok(r.guard.violations.some((v) => v.kind === "pick" && /Mahomes/.test(v.text)));
  assert.ok(events.some((e) => e.type === "retract")); // the streamed text was taken back
  assert.equal(r.reply.includes("Mahomes"), false);
});

test("a model that follows the rules and says there is nothing to recommend passes", async () => {
  const m = scripted([calls(use("p", "get_algo_picks", { sport: "NFL", date: "2031-01-01", game: null })), answer("The algorithm has no NFL output for that date, so I have nothing to recommend. Ask me again when the slate is built.")]);
  const r = await runAdvisorTurn([user("picks for new year 2031?")], ctxFor(someone()), m.call);
  assert.equal(r.ended, "answered");
  assert.equal(r.guard.violations.length, 0);
});

test("a pick the tools did return can be recommended", async () => {
  const pick = algo.picks.NBA.picks[0];
  const name = pick.legs[0].leg;
  const m = scripted([calls(use("p", "get_algo_picks", { sport: "NBA", date: null, game: null })), answer(`The algorithm's ticket in ${pick.game} starts with ${name}.`)]);
  const r = await runAdvisorTurn([user("nba picks")], ctxFor(someone()), m.call);
  assert.equal(r.ended, "answered");
  assert.deepEqual(r.cards.map((c) => c.kind), ["picks"]);
});

test("after one failed check the model is asked to rewrite, and a clean rewrite is what the user gets", async () => {
  const m = scripted([answer("Take Patrick Mahomes 275+ passing yards, it is 81% to hit."), answer("The algorithm has nothing on that, so I have no pick to give you.")]);
  const r = await runAdvisorTurn([user("who should I take?")], ctxFor(someone()), m.call);
  assert.equal(r.ended, "answered");
  assert.equal(r.guard.rewrites, 1);
  assert.match(r.reply, /no pick to give/);
  const note = m.requests[1].messages[m.requests[1].messages.length - 1].content as string;
  assert.match(note, /^\[Automatic check\]/);
  assert.match(note, /81%/);
});

// ================= hard rule: every stake from size_bet =================
test("a stake stated without size_bet is withheld", async () => {
  const m = scripted([answer("Put 2u ($20) on it."), answer("I would go 2u ($20).")]);
  const r = await runAdvisorTurn([user("how much on this?")], ctxFor(someone({ account: null })), m.call);
  assert.equal(r.ended, "withheld");
  assert.ok(r.guard.violations.some((v) => /size_bet/.test(v.why) || /dollar/.test(v.why)));
});

test("a stake that came from size_bet is quoted as the engine gave it", async () => {
  const legs = [legOf(strong), legOf(second)];
  const m = scripted([
    calls(use("s", "size_bet", { sport: "NFL", legs, total_odds: 150 })),
    (messages) => { const r = JSON.parse(resultsOf(messages[messages.length - 1])[0].content); return answer(`Stake ${r.stake.label}. ${r.stake.reason}`); },
  ]);
  const r = await runAdvisorTurn([user("price is +150, how much?")], ctxFor(someone()), m.call);
  assert.equal(r.ended, "answered");
  assert.match(r.reply, /^Stake \d+(\.\d)?u \(\$\d+/);
  assert.deepEqual(r.cards.map((c) => c.kind), ["stake"]);
  const sized = r.cards[0].data as { stake: { status: string }; joint_probability: number };
  assert.equal(sized.stake.status, "bet");
  assert.ok(sized.joint_probability > strong.prob * second.prob - 0.05); // the engine worked the chance out itself
});

test("size_bet takes legs and a price, never a probability", () => {
  const tool = ADVISOR_TOOLS.find((t) => t.name === "size_bet")!;
  assert.deepEqual(Object.keys(tool.input_schema.properties), ["sport", "legs", "total_odds"]);
  assert.equal(JSON.stringify(tool.input_schema).includes("probab"), false);
});

test("with a limit in force, size_bet gives no stake and says not to look for one", () => {
  const u = someone({ account: openAccount(1000, "balanced", NOW, { coolOffUntil: "2026-11-27T00:00:00Z" }) });
  const r = sizeBetFor(u, [legOf(strong), legOf(second)], 150, NFL, NOW);
  assert.equal(r.stake.status, "blocked");
  assert.equal(r.stake.stop, "cool-off");
  assert.equal(r.stake.dollars, 0);
  assert.match(r.note, /limit is in force/);
  const stopLoss = someone({ account: openAccount(1000, "balanced", NOW, { stopLoss: 40 }), bets: [{ id: "b", placedAt: NOW.toISOString(), sport: "NFL", book: "", legs: [{ description: "x", odds: 100 }], stake: 50, status: "lost" }] });
  assert.equal(sizeBetFor(stopLoss, [legOf(strong), legOf(second)], 150, NFL, NOW).stake.stop, "stop-loss");
  assert.equal(bankrollStatus(stopLoss, NOW).limit_in_force, "stop-loss");
  assert.match(userContext(stopLoss, { now: NOW, built: {}, tier: "pro", remainingToday: 5 }), /A LIMIT IS IN FORCE \(stop-loss\)/);
});

// ================= the reply check on its own =================
test("figures that came from a tool or the user pass; others do not", () => {
  const facts = factsFrom([
    user("my book has it at +450 and I staked $25"),
    { role: "user", content: [{ type: "tool_result", tool_use_id: "t", content: JSON.stringify({ joint: 0.2461, fairOdds: 306, legs: [{ player: "Isaiah Likely", prob: 0.864, edge: 0.0834, threshold: 2 }], stake: { label: "1.9u ($19)", units: 1.9, dollars: 19 } }) }] },
  ]);
  assert.deepEqual(checkReply("It is 24.6% to hit, fair +306 against your +450. Isaiah Likely 2+ receptions is 86%, an edge of +8.3 pts. Stake 1.9u ($19); you put $25 on it.", facts), []);
  const bad = checkReply("It is 31% to hit at +520. Stake 3u ($30).", facts).map((v) => v.text);
  assert.deepEqual(bad, ["31%", "+520", "$30", "3u"]);
});

test("the product's own rule numbers may always be quoted", () => {
  const facts = factsFrom([]);
  assert.deepEqual(checkReply("Godseye wants parlay legs at 70% or better, at most one under 65%, and 75% for NBA. A unit is 1% of bankroll.", facts), []);
});

test("multiplying two legs together is caught", () => {
  const facts = factsFrom([{ role: "user", content: [{ type: "tool_result", tool_use_id: "t", content: JSON.stringify({ legs: [{ prob: 0.8 }, { prob: 0.7 }], joint: null }) }] }]);
  assert.deepEqual(checkReply("Those two together are about 56%.", facts).map((v) => v.text), ["56%"]);
});

test("ordinary sentences are not mistaken for picks or figures", () => {
  const facts = factsFrom([user("thoughts on the Giants game?")]);
  assert.deepEqual(checkReply("No bet there. The Giants are at home in the rain at 8:15 pm, Week 10, and I have nothing rated for it. Ask me about a player and I will pull his rungs.", facts), []);
});

// ================= tools on the user's own data =================
test("get_algo_picks returns the algorithm's tickets, or nothing with the reason", () => {
  const nba = algoPicks(algo.picks.NBA, null, null);
  assert.ok(nba.picks.length > 0);
  assert.ok(nba.picks.every((p) => p.legs.length > 0 && p.joint_probability! > 0 && p.joint_probability! <= 1));
  const one = algoPicks(algo.picks.NBA, null, nba.picks[0].game);
  assert.ok(one.picks.length > 0 && one.picks.every((p) => p.game === nba.picks[0].game));
  const none = algoPicks(algo.picks.NBA, "2031-01-01", null);
  assert.equal(none.picks.length, 0);
  assert.match(none.note, /no output for 2031-01-01/);
  const real = nflPicks(nflRaw);
  assert.equal(real.sport, "NFL");
});

test("get_odds gives the prices the output carries and says when it has none", () => {
  const g = algo.picks.NBA.games[0];
  const nba = oddsFor(algo.picks.NBA, g.game, null);
  assert.equal(nba.found, true);
  assert.ok((nba.prop_prices ?? []).length > 0);
  const nfl = oddsFor(algo.picks.NFL, algo.picks.NFL.games[0].game, "rec");
  assert.equal(nfl.found, true);
  assert.equal((nfl.prop_prices ?? []).length, 0);
  assert.match(nfl.note, /read the price from their book/);
  assert.equal(oddsFor(algo.picks.NFL, "ZZZ @ QQQ", null).found, false);
});

test("get_bankroll reports the engine's numbers, or that no bankroll is set", () => {
  const b = bankrollStatus(someone(), NOW);
  assert.equal(b.set, true);
  assert.equal(b.unit_dollars, 10);
  assert.equal(b.most_on_one_bet_dollars, 20);
  assert.equal(b.most_in_one_night_dollars, 50);
  assert.equal(b.limit_in_force, null);
  assert.equal(bankrollStatus(someone({ account: null }), NOW).set, false);
});

test("log_bet adds the bet to the ledger and saves the slip for re-checking", () => {
  const u = someone();
  const r = logBetFor(u, { sport: "NFL", legs: [legOf(strong), legOf(second)], totalOdds: 150, stakeDollars: 20, book: "bet365" }, NFL, NOW, () => "fixed");
  assert.equal(r.logged, true);
  assert.equal(u.bets.length, 1);
  assert.equal(u.bets[0].stake, 20);
  assert.equal(u.bets[0].price, 150);
  assert.ok(u.bets[0].modelChance! > 0);
  assert.equal(u.slips[0].legs.length, 2);
  assert.equal(logBetFor(u, { sport: "NFL", legs: [legOf(strong)], totalOdds: null, stakeDollars: 0, book: null }, NFL, NOW).logged, false);
});

const bet = (o: Partial<Bet>): Bet => ({ id: Math.random().toString(36).slice(2), placedAt: "2026-11-20T23:00:00Z", sport: "NFL", book: "bet365", legs: [{ description: "A 20+ rushing yards", odds: -110 }], stake: 10, status: "won", ...o });

test("get_user_history finds patterns in the user's own bets, and says when there are too few", () => {
  const td = { description: "B anytime touchdown", odds: 150 };
  const bets = [
    ...Array.from({ length: 6 }, () => bet({ legs: [td, { description: "C 3+ receptions", odds: -200 }, { description: "D 40+ receiving yards", odds: -150 }, td], status: "lost", price: 900 })),
    ...Array.from({ length: 4 }, () => bet({ status: "won" })), bet({ status: "lost" }), bet({ status: "open" }),
  ];
  const h = userHistory(someone({ bets })) as ReturnType<typeof userHistory> & { slips_with_a_touchdown_leg: { hit_rate: number; lost: number }; by_leg_count: { group: string; hit_rate: number }[] };
  assert.equal(h.slips_with_a_touchdown_leg.lost, 6);
  assert.equal(h.slips_with_a_touchdown_leg.hit_rate, 0);
  assert.equal(h.by_leg_count.find((g) => g.group === "singles")!.hit_rate, 0.8);
  assert.match(String(h.note), /too few/);
  assert.equal((userHistory(someone()) as { bets: number }).bets, 0);
});

// ================= instructions =================
test("the instructions carry the hard rules and are the same for every user", async () => {
  for (const phrase of ["Only algorithm picks", "No numbers of your own", "Every stake comes from size_bet", "Follow the ticket rules", "Be honest and direct", "Never promise", "chasing losses", "cool-off", "confirm or correct", "unrated"])
    assert.ok(ADVISOR_SYSTEM_PROMPT.includes(phrase), phrase);
  const a = scripted([answer("a")]);
  const b = scripted([answer("b")]);
  await runAdvisorTurn([user("one")], ctxFor(someone()), a.call);
  await runAdvisorTurn([user("two")], ctxFor(someone({ account: null, profile: { summary: "Likes 6-leg slips.", book: "bet365" } })), b.call);
  assert.equal(a.requests[0].system, b.requests[0].system); // cacheable across users
  assert.notEqual(a.requests[0].context, b.requests[0].context); // personal
  assert.match(b.requests[0].context, /Likes 6-leg slips/);
  assert.match(b.requests[0].context, /Book: bet365/);
  assert.match(b.requests[0].context, /Bankroll: not set/);
});

test("eleven tools, all with strict schemas", () => {
  assert.deepEqual(ADVISOR_TOOLS.map((t) => t.name),
    ["get_algo_picks", "get_odds", "parse_slip", "grade_slip", "suggest_changes", "get_bankroll", "size_bet", "log_bet", "get_user_history", "get_player_intel", "get_game_intel"]);
  for (const t of ADVISOR_TOOLS) {
    assert.equal(t.strict, true);
    assert.equal(t.input_schema.additionalProperties, false);
  }
});

// ================= subscriptions and limits =================
const PRO = { ADVISOR_DEV_TIER: undefined };
const active = (tier: "pro" | "elite", over: Partial<UserRecord> = {}) => someone({ subscription: { tier, status: "active" }, ...over });

test("no subscription, no chat; the dev tier is for local use only", () => {
  const a = chatAllowance(someone(), NOW, PRO);
  assert.equal(a.ok, false);
  assert.equal(!a.ok && a.reason, "no-subscription");
  assert.equal(effectiveTier(someone(), { ADVISOR_DEV_TIER: "elite" }), "elite");
  assert.equal(effectiveTier(someone(), { ADVISOR_DEV_TIER: "platinum" }), "none");
  assert.equal(effectiveTier(active("pro"), { ADVISOR_DEV_TIER: "elite" }), "pro"); // a real subscription wins
});

test("Pro is capped per day, Elite is not, and the cap resets with the betting day", () => {
  const cap = ADVISOR_LIMITS.dailyMessages.pro!;
  const log = (n: number, at = NOW) => Array.from({ length: n }, () => at.toISOString());
  const almost = chatAllowance(active("pro", { messageLog: log(cap - 1) }), NOW, PRO);
  assert.ok(almost.ok && almost.remaining === 1);
  const full = chatAllowance(active("pro", { messageLog: log(cap) }), NOW, PRO);
  assert.ok(!full.ok && full.reason === "daily-cap");
  assert.ok(chatAllowance(active("elite", { messageLog: log(500) }), NOW, PRO).ok);
  assert.ok(chatAllowance(active("pro", { messageLog: log(cap, new Date("2026-11-24T23:00:00Z")) }), NOW, PRO).ok); // yesterday's messages
});

test("cancel archives the history; returning in time restores it; returning late starts fresh", () => {
  const convo = { id: "c1", startedAt: NOW.toISOString(), updatedAt: NOW.toISOString(), messages: [], display: [], summarized: true };
  const u = active("pro", { conversations: [structuredClone(convo)], profile: { summary: "Prefers 4-leg slips." } });
  applySubscriptionEvent(u, { tier: "none", status: "canceled" }, NOW);
  assert.equal(u.subscription.status, "canceled");
  assert.equal(visibleConversations(u).length, 0); // hidden, not deleted
  assert.equal(u.conversations.length, 1);
  assert.equal(chatAllowance(u, NOW, PRO).ok, false);

  const back = structuredClone(u);
  applySubscriptionEvent(back, { tier: "elite", status: "active" }, new Date(NOW.getTime() + 30 * 86_400_000));
  assert.equal(visibleConversations(back).length, 1);
  assert.equal(back.profile.summary, "Prefers 4-leg slips.");
  assert.equal(back.subscription.tier, "elite");

  const late = structuredClone(u);
  const after = new Date(NOW.getTime() + (ADVISOR_LIMITS.archiveDays + 1) * 86_400_000);
  assert.equal(purgeExpiredArchive(late, after), true);
  applySubscriptionEvent(late, { tier: "pro", status: "active" }, after);
  assert.equal(late.conversations.length, 0);
  assert.equal(late.profile.summary, "");
});

test("token usage is priced and totalled per user", () => {
  assert.equal(costUsd("claude-sonnet-5-5", { inputTokens: 1_000_000, outputTokens: 100_000, cacheReadTokens: 2_000_000, cacheWriteTokens: 0 }), 2 + 1 + 0.2);
  assert.equal(costUsd("some-future-model", { inputTokens: 5, outputTokens: 5, cacheReadTokens: 0, cacheWriteTokens: 0 }), 0);
  const u = someone();
  logUsage(u, "claude-sonnet-5-5", "chat", { inputTokens: 10_000, outputTokens: 1_000, cacheReadTokens: 0, cacheWriteTokens: 0 }, NOW);
  logUsage(u, "some-future-model", "chat", { inputTokens: 10, outputTokens: 10, cacheReadTokens: 0, cacheWriteTokens: 0 }, NOW);
  logUsage(u, "claude-sonnet-5-5", "chat", { inputTokens: 0, outputTokens: 0, cacheReadTokens: 0, cacheWriteTokens: 0 }, NOW); // nothing to log
  const t = usageTotals(u);
  assert.equal(t.calls, 2);
  assert.equal(t.costUsd, 0.03);
  assert.equal(t.unpricedCalls, 1);
});

// ================= the whole service: one user, several messages =================
function service(replies: Parameters<typeof scripted>[0], env: Record<string, string | undefined> = { ADVISOR_DEV_TIER: "pro" }) {
  const store = new MemoryStore(() => NOW);
  const model = scripted(replies);
  let clock = NOW.getTime();
  let id = 0;
  const deps: ServiceDeps = { store, callModel: model.call, model: "claude-sonnet-5-5", algo, now: () => new Date((clock += 1000)), newId: () => `gen_${++id}`, env,
    readImage: async () => JSON.parse(readFileSync(new URL("../../fixtures/slips/bet365-sgp.expected.json", import.meta.url), "utf8")) };
  const send = async (textIn: string, more: Partial<Parameters<typeof handleTurn>[0]> = {}) => {
    const events: ServiceEvent[] = [];
    const r = await handleTurn({ userId: "user_test_0001", conversationId: null, text: textIn, ...more }, deps, (e) => events.push(e));
    return { events, ...r };
  };
  return { store, model, send, deps };
}

test("a message past the daily cap is refused without calling the model, and is not counted", async () => {
  const cap = ADVISOR_LIMITS.dailyMessages.pro!;
  const s = service(Array.from({ length: cap + 5 }, () => answer("ok")));
  let conversationId: string | null = null;
  for (let i = 0; i < cap; i++) conversationId = (await s.send(`message ${i}`, { conversationId })).conversationId;
  assert.equal(s.model.requests.length, cap);
  const over = await s.send("one more", { conversationId });
  assert.equal(over.allowance.ok, false);
  assert.deepEqual(over.events.map((e) => e.type), ["blocked"]);
  assert.equal(s.model.requests.length, cap); // the model was not called
  assert.equal((await s.store.get("user_test_0001")).messageLog.length, cap);
});

test("without a subscription the chat does not answer; an Elite subscriber is not capped", async () => {
  const none = service([answer("ok")], {});
  const r = await none.send("hello");
  assert.equal(r.allowance.ok, false);
  assert.equal(none.model.requests.length, 0);
  const elite = service(Array.from({ length: 30 }, () => answer("ok")), {});
  await elite.store.update("user_test_0001", (u) => applySubscriptionEvent(u, { tier: "elite", status: "active" }, NOW));
  let conversationId: string | null = null;
  for (let i = 0; i < 25; i++) conversationId = (await elite.send(`m${i}`, { conversationId })).conversationId;
  assert.equal(elite.model.requests.length, 25);
});

test("a conversation is stored, with what the user saw, and token usage is logged", async () => {
  const s = service([calls(use("g", "get_bankroll", {})), answer("You have room left tonight.")]);
  const r = await s.send("how is my bankroll?", { account: openAccount(500, "balanced", NOW) });
  const u = await s.store.get("user_test_0001");
  assert.equal(u.account!.bankroll, 500); // synced from the app
  assert.equal(u.conversations.length, 1);
  const c = u.conversations[0];
  assert.equal(c.id, r.conversationId);
  assert.deepEqual(c.display.map((d) => (d.type === "line" ? `${d.who}: ${d.text}` : `card:${d.card.kind}`)), ["you: how is my bankroll?", "card:bankroll", "advisor: You have room left tonight."]);
  assert.equal(c.messages.length, 4);
  assert.equal(u.usage.length, 1);
  assert.equal(u.usage[0].inputTokens, 2000); // two model calls in the turn
  assert.ok(u.usage[0].costUsd > 0);
  assert.deepEqual(r.events.at(-1), { type: "done", conversationId: c.id, ended: "answered", remainingToday: ADVISOR_LIMITS.dailyMessages.pro! - 1, tier: "pro" });
});

test("a bet the advisor logs lands in the user's ledger and is sent to the app", async () => {
  const s = service([calls(use("l", "log_bet", { sport: "NFL", legs: [legOf(strong), legOf(second)], total_odds: 150, stake_dollars: 20, book: "bet365" })), answer("Logged.")]);
  const r = await s.send("I placed it for $20 at +150", { account: openAccount(1000, "balanced", NOW), bets: [] });
  const u = await s.store.get("user_test_0001");
  assert.equal(u.bets.length, 1);
  assert.equal(u.slips.length, 1);
  const sent = r.events.find((e) => e.type === "bet");
  assert.ok(sent && sent.type === "bet" && sent.bet.id === u.bets[0].id);
});

test("memory: a finished conversation is summarised and the next one starts from it", async () => {
  const s = service([
    answer("Noted: you like four legs on bet365."),                          // conversation 1
    answer("Prefers 4-leg NFL same-game parlays on bet365."),                 // the summary, written when conversation 2 starts
    answer("Welcome back."),                                                  // conversation 2
  ]);
  await s.send("I always play 4-leg SGPs on bet365");
  let u = await s.store.get("user_test_0001");
  assert.equal(u.profile.summary, ""); // not summarised while it is the current conversation
  assert.equal(pendingSummaries(u, null).length, 1);
  await s.send("back again"); // conversationId null: a new chat
  u = await s.store.get("user_test_0001");
  assert.equal(u.profile.summary, "Prefers 4-leg NFL same-game parlays on bet365.");
  assert.equal(u.conversations.length, 2);
  assert.equal(u.conversations[0].summarized, true);
  // the summariser saw the first conversation; the second conversation's first reply saw the summary
  assert.match(s.model.requests[1].messages[0].content as string, /I always play 4-leg SGPs on bet365/);
  assert.match(s.model.requests[2].context, /Prefers 4-leg NFL same-game parlays on bet365/);
  assert.equal(u.usage.filter((e) => e.purpose === "summary").length, 1);
});

test("a user can view their history and clear it", async () => {
  const s = service([answer("first answer"), answer("notes"), answer("second answer")]);
  await s.send("first question");
  await s.send("second question");
  const h = await readHistory(s.store, "user_test_0001", NOW, { ADVISOR_DEV_TIER: "pro" });
  assert.equal(h.conversations.length, 2);
  assert.equal(h.summary, "notes");
  assert.equal(h.plan.tier, "pro");
  assert.equal(h.plan.usedToday, 2);
  await s.store.update("user_test_0001", clearMemory);
  const after = await readHistory(s.store, "user_test_0001", NOW, { ADVISOR_DEV_TIER: "pro" });
  assert.equal(after.conversations.length, 0);
  assert.equal(after.summary, "");
});

test("the transcript given to the summariser has the words, not the tool traffic", () => {
  const t = transcript([
    user("my slip"), { role: "assistant", content: [use("t", "grade_slip", {})] as ChatMessage["content"] },
    { role: "user", content: [{ type: "tool_result", tool_use_id: "t", content: '{"joint":0.4}' }] },
    { role: "assistant", content: [thinking, text("It is a pass.")] as ChatMessage["content"] }, user("[Automatic check] rewrite"),
  ]);
  assert.equal(t, "User: my slip\nAdvisor: It is a pass.");
});

// ================= the demo walk-through, on the scripted stand-in =================
test("demo script: upload a slip, get the audit, ask for a swap, get a sized stake, log the bet", async () => {
  const store = new MemoryStore(() => NOW);
  const real = { catalogs: algo.catalogs, intel: algo.intel, picks: { NFL: nflPicks(nflRaw), NBA: algo.picks.NBA } };
  const deps: ServiceDeps = { store, callModel: demoModel, model: "demo", algo: real, now: () => NOW, env: { ADVISOR_DEV_TIER: "pro" },
    readImage: async () => JSON.parse(readFileSync(new URL("../../fixtures/slips/bet365-sgp.expected.json", import.meta.url), "utf8")) };
  let conversationId: string | null = null;
  const say = async (t: string, image = false) => {
    const events: ServiceEvent[] = [];
    const r = await handleTurn({ userId: "user_demo_0001", conversationId, text: t, account: openAccount(1000, "balanced", NOW), bets: (await store.get("user_demo_0001")).bets,
                                 image: image ? { mediaType: "image/png", data: new Uint8Array([1, 2, 3]) } : null }, deps, (e) => events.push(e));
    conversationId = r.conversationId;
    const cards = events.filter((e) => e.type === "card").map((e) => (e.type === "card" ? e.card : null)!);
    const done = events.find((e) => e.type === "done");
    return { cards, ended: done && done.type === "done" ? done.ended : "none", events };
  };
  const a = await say("Is this worth playing?", true);
  assert.deepEqual(a.cards.map((c) => c.kind), ["slip"]);
  const b = await say("yes");
  assert.deepEqual(b.cards.map((c) => c.kind), ["audit"]);
  const c = await say("can you swap anything to make it better?");
  assert.deepEqual(c.cards.map((x) => x.kind), ["changes"]);
  const d = await say("my book has the new one at +320, how much?");
  assert.deepEqual(d.cards.map((x) => x.kind), ["stake"]);
  assert.equal((d.cards[0].data as { stake: { status: string; label: string } }).stake.status, "bet");
  const e = await say("placed it, $20 at +320");
  assert.deepEqual(e.cards.map((x) => x.kind), ["logged"]);
  for (const step of [a, b, c, d, e]) assert.equal(step.ended, "answered"); // every scripted reply passed the reply check
  const u = await store.get("user_demo_0001");
  assert.equal(u.bets.length, 1);
  assert.equal(u.bets[0].stake, 20);
  assert.equal(u.conversations[0].display.filter((x) => x.type === "card").length, 5);
});

// ================= picks of the day =================
test("picks of the day are the algorithm's own slips, one per game, ranked by its own chance", () => {
  const day = picksOfTheDay(algo.picks.NBA);
  assert.ok(day.topPerGame.length > 0);
  assert.equal(new Set(day.topPerGame.map((p) => p.game)).size, day.topPerGame.length); // one per game
  for (let i = 1; i < day.topPerGame.length; i++) assert.ok(day.topPerGame[i - 1].joint_probability! >= day.topPerGame[i].joint_probability!);
  assert.deepEqual(day.best, day.topPerGame.slice(0, 3));
  // each is the best slip the algorithm has for its game, unchanged
  for (const p of day.topPerGame) {
    const sameGame = algo.picks.NBA.picks.filter((x) => x.game === p.game && x.date === day.date);
    assert.equal(p.joint_probability, Math.max(...sameGame.map((x) => x.joint_probability!)));
    assert.ok(sameGame.includes(p));
  }
  const empty = picksOfTheDay({ ...algo.picks.NBA, picks: [], dates: [] });
  assert.deepEqual([empty.best.length, empty.topPerGame.length, empty.date], [0, 0, null]);
});

// ================= storage =================
test("the file store keeps one record per user and survives concurrent updates", async () => {
  const store = new FileStore(mkdtempSync(path.join(tmpdir(), "godseye-store-")), () => NOW);
  const id = "user_file_0001";
  assert.equal((await store.get(id)).bets.length, 0);
  await Promise.all(Array.from({ length: 20 }, (_, i) => store.update(id, (u) => { u.messageLog.push(`m${i}`); })));
  assert.equal((await store.get(id)).messageLog.length, 20);
  assert.deepEqual(await store.list(), [id]);
  await assert.rejects(() => store.get("../../etc/passwd"));
  assert.equal(validUserId("ok_id-12345"), true);
  assert.equal(validUserId("short"), false);
  assert.equal(validUserId("has/slash/in/it"), false);
});

// ================= intel =================
test("player intel is the algorithm's own, and carries no results", () => {
  const r = playerIntel(strong.player, algo.intel.NFL, NFL);
  assert.ok(r.found);
  const d = r.found ? (r.data as Record<string, unknown>) : {};
  const ladder = (d.milestone_ladders as Record<string, { milestone: string; probability: number }[]>)[strong.market];
  assert.equal(ladder.find((x) => x.milestone === `${strong.threshold}+`)!.probability, strong.prob);
  assert.equal(JSON.stringify(algo.intel.NFL).includes("cashed"), false);
  assert.equal(/<b>|<\/b>/.test(JSON.stringify(d)), false);
  assert.equal(playerIntel("Nobody McNothing", algo.intel.NFL, NFL).found, false);
});

test("game intel finds a game by matchup or by one team", () => {
  const g = algo.intel.NFL.games[0];
  const [away, home] = g.game.split(" @ ");
  for (const q of [g.game, `${away} vs ${home}`, home]) {
    const r = gameIntel(q, algo.intel.NFL);
    assert.ok(r.found && r.data.game === g.game, q);
  }
  assert.equal(gameIntel("ZZZ @ QQQ", algo.intel.NFL).found, false);
});

// ================= history trimming =================
test("screenshots are dropped from the kept history; a long history is cut at the start of a turn", () => {
  const kept = trimHistory([
    { role: "user", content: [{ type: "image", source: { type: "base64", media_type: "image/png", data: "AAAA" } }, { type: "text", text: "my slip" }] },
    { role: "assistant", content: [thinking, text("Is this your slip?")] as ChatMessage["content"] },
  ]);
  assert.deepEqual(kept[0].content, [{ type: "text", text: "[bet slip screenshot, already read]" }, { type: "text", text: "my slip" }]);
  const long: ChatMessage[] = [];
  for (let i = 0; i < 30; i++) {
    long.push(user(`question ${i}`));
    long.push({ role: "assistant", content: [use(`t${i}`, "get_game_intel", { sport: "NFL", game: "x" })] as ChatMessage["content"] });
    long.push({ role: "user", content: [{ type: "tool_result", tool_use_id: `t${i}`, content: "{}" }] });
    long.push({ role: "assistant", content: `answer ${i}` });
  }
  const cut = trimHistory(long);
  assert.ok(cut.length <= ADVISOR_CONFIG.maxHistory);
  assert.equal(typeof cut[0].content, "string");
  assert.equal(cut[cut.length - 1].content, "answer 29");
});
