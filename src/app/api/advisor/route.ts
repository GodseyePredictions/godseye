/* One message to the advisor.

   POST JSON: { conversationId, text, image?, account?, bets? }  with the header x-godseye-user: <user id>
     conversationId  the chat to continue, or null to start a new one
     text            what the user typed
     image           an attached bet slip screenshot: { mediaType, data } with base64 data
     account, bets   the app's copy of the user's bankroll settings and tracked bets (they live in the browser for now)

   Replies with newline-delimited JSON events: text, tool, card, retract, notice, bet, blocked, then done or error.

   There is no sign-in yet: the user id is whatever the browser sends. Do not expose this route on a
   public address before logins are in place. */
import { deps, userIdFrom } from "@/lib/advisor/server";
import { AdvisorError } from "@/lib/advisor/claude";
import { MAX_TEXT, handleTurn, type ServiceEvent } from "@/lib/advisor/service";
import type { Bet } from "@/lib/bets";
import { IMAGE_TYPES, MAX_IMAGE_BYTES, type ImageType } from "@/lib/slip/vision";
import type { Account } from "@/lib/staking";

type Body = { conversationId?: unknown; text?: unknown; image?: { mediaType?: unknown; data?: unknown } | null; account?: Account | null; bets?: Bet[] };

export async function POST(request: Request) {
  const userId = userIdFrom(request);
  if (!userId) return Response.json({ error: "Missing or invalid user id." }, { status: 400 });
  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return Response.json({ error: "Send the message as JSON." }, { status: 400 });
  }
  const text = typeof body.text === "string" ? body.text.trim().slice(0, MAX_TEXT) : "";
  let image: { mediaType: ImageType; data: Buffer } | null = null;
  if (body.image) {
    const { mediaType, data } = body.image;
    if (typeof data !== "string" || typeof mediaType !== "string" || !(IMAGE_TYPES as readonly string[]).includes(mediaType))
      return Response.json({ error: "That attachment is not a PNG, JPEG, WebP or GIF image." }, { status: 415 });
    const bytes = Buffer.from(data, "base64");
    if (bytes.byteLength > MAX_IMAGE_BYTES) return Response.json({ error: "That image is larger than 5 MB. Crop it to the slip and try again." }, { status: 413 });
    image = { mediaType: mediaType as ImageType, data: bytes };
  }
  if (!text && !image) return Response.json({ error: "Type a message or attach a slip." }, { status: 400 });

  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      const send = (event: ServiceEvent | { type: "error"; message: string }) => controller.enqueue(encoder.encode(JSON.stringify(event) + "\n"));
      try {
        await handleTurn(
          { userId, conversationId: typeof body.conversationId === "string" ? body.conversationId : null, text, image, account: body.account ?? null, bets: Array.isArray(body.bets) ? body.bets : null },
          deps(),
          send,
        );
      } catch (error) {
        if (!(error instanceof AdvisorError)) console.error("advisor turn failed", error);
        send({ type: "error", message: error instanceof AdvisorError ? error.message : "Something went wrong. Try again." });
      } finally {
        controller.close();
      }
    },
  });
  return new Response(stream, { headers: { "Content-Type": "application/x-ndjson; charset=utf-8", "Cache-Control": "no-store" } });
}
