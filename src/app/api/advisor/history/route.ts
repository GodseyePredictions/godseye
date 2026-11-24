/* A user's own advisor history.
   GET     their conversations (newest first), what the advisor remembers about them, and their plan
   DELETE  clear all of it: every conversation and the remembered summary. Bets and bankroll are not touched. */
import { clearMemory } from "@/lib/advisor/memory";
import { deps, userIdFrom, userStore } from "@/lib/advisor/server";
import { demoEnabled } from "@/lib/advisor/demo-model";
import { readHistory } from "@/lib/advisor/service";

export async function GET(request: Request) {
  const userId = userIdFrom(request);
  if (!userId) return Response.json({ error: "Missing or invalid user id." }, { status: 400 });
  const history = await readHistory(userStore(), userId, new Date(), deps().env);
  return Response.json({ ...history, demo: demoEnabled() }, { headers: { "Cache-Control": "no-store" } });
}

export async function DELETE(request: Request) {
  const userId = userIdFrom(request);
  if (!userId) return Response.json({ error: "Missing or invalid user id." }, { status: 400 });
  await userStore().update(userId, clearMemory);
  return Response.json({ cleared: true });
}
