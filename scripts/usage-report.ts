/* API cost per subscriber, from the user store (Postgres when DATABASE_URL is set, local files otherwise).

   Usage: npm run usage:report            every user, all time
          npm run usage:report -- 7       the last 7 days */
import { effectiveTier } from "../src/lib/advisor/subscription.ts";
import { usageTotals } from "../src/lib/advisor/usage.ts";
import { openStore } from "../src/lib/store/open.ts";

const days = Number(process.argv[2]);
const since = days > 0 ? new Date(Date.now() - days * 86_400_000) : undefined;
const store = openStore();
const rows = [];
for (const id of await store.list()) {
  const u = await store.get(id);
  const t = usageTotals(u, since);
  if (t.calls) rows.push({ user: id, plan: effectiveTier(u, {}), calls: t.calls, input: t.inputTokens, output: t.outputTokens, cached: t.cacheReadTokens, cost: t.costUsd, unpriced: t.unpricedCalls });
}
rows.sort((a, b) => b.cost - a.cost);
console.log(`Advisor API usage${since ? `, last ${days} days` : ", all time"}: ${rows.length} user(s)`);
for (const r of rows)
  console.log(
    `  ${r.user.padEnd(38)} ${r.plan.padEnd(6)} ${String(r.calls).padStart(5)} calls  in ${String(r.input).padStart(9)}  out ${String(r.output).padStart(8)}  cached ${String(r.cached).padStart(9)}  $${r.cost.toFixed(4)}` +
      (r.unpriced ? `  (${r.unpriced} calls on a model with no price set)` : ""),
  );
console.log(`  total $${rows.reduce((a, r) => a + r.cost, 0).toFixed(4)}`);
