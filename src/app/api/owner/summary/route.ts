import { readFileSync } from "node:fs";
import path from "node:path";
import { userStore } from "@/lib/advisor/server";
import { ownerAccess, ownerSummary, type RecordFile } from "@/lib/owner";

/** The owner's private summary. Needs the header `Authorization: Bearer <OWNER_KEY>`. */
export async function GET(request: Request) {
  const access = ownerAccess(request.headers.get("authorization"));
  if (access === "not-set-up") return Response.json({ error: "The owner page is not set up on this server: OWNER_KEY is missing or too short." }, { status: 503 });
  if (access !== "ok") return Response.json({ error: "That key is not right." }, { status: 401 });

  let record: RecordFile | null = null;
  try {
    record = JSON.parse(readFileSync(path.join(process.cwd(), "model/nba/output/nba_cashed.json"), "utf8"));
  } catch {
    record = null;
  }
  return Response.json(await ownerSummary(userStore(), new Date(), record), { headers: { "Cache-Control": "no-store" } });
}
