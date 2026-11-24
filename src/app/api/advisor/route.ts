/* One turn of the advisor chat.

   POST JSON: { messages, text, image?, account?, bets? }
     messages  the conversation so far, exactly as the last reply's "done" event returned it
     text      what the user just typed
     image     an attached bet slip screenshot: { mediaType, data } with base64 data
     account   the user's bankroll settings, and bets their tracked bets (both live in the browser for now)

   Replies with newline-delimited JSON events: {type:"text",delta}, {type:"tool",name}, {type:"notice",message},
   then {type:"done",messages,ended} or {type:"error",message}. */
import { runAdvisorTurn, trimHistory, type ChatMessage, type TurnEvent } from "@/lib/advisor/agent";
import { AdvisorError, callClaude } from "@/lib/advisor/claude";
import { loadAlgorithmData } from "@/lib/advisor/server-data";
import type { Bet } from "@/lib/bets";
import { IMAGE_TYPES, MAX_IMAGE_BYTES, readSlipImage, type ImageType } from "@/lib/slip/vision";
import { tonightFrom, withWeeklyUnit, type Account } from "@/lib/staking";

const MAX_TEXT = 4000;
const MAX_MESSAGES = 120;

type Body = { messages?: unknown; text?: unknown; image?: { mediaType?: unknown; data?: unknown } | null; account?: Account | null; bets?: Bet[] };

function validHistory(m: unknown): m is ChatMessage[] {
  return Array.isArray(m) && m.length <= MAX_MESSAGES &&
    m.every((x) => x && (x.role === "user" || x.role === "assistant") && (typeof x.content === "string" || Array.isArray(x.content)));
}

export async function POST(request: Request) {
  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return Response.json({ error: "Send the message as JSON." }, { status: 400 });
  }
  const text = typeof body.text === "string" ? body.text.trim().slice(0, MAX_TEXT) : "";
  const history = body.messages ?? [];
  if (!validHistory(history)) return Response.json({ error: "The conversation could not be read. Start a new chat." }, { status: 400 });

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

  const IMAGE_ID = "slip-1";
  const userMessage: ChatMessage = image
    ? {
        role: "user",
        content: [
          { type: "image", source: { type: "base64", media_type: image.mediaType, data: image.data.toString("base64") } },
          { type: "text", text: `${text || "Here is my bet slip."}\n\n[The user attached a bet slip screenshot. Its image_id for parse_slip is "${IMAGE_ID}".]` },
        ],
      }
    : { role: "user", content: text };

  const now = new Date();
  const account = body.account && typeof body.account.bankroll === "number" ? withWeeklyUnit(body.account, now) : null;
  const money = account ? { account, tonight: tonightFrom(Array.isArray(body.bets) ? body.bets : [], now), now } : {};
  const context = {
    ...loadAlgorithmData(),
    money,
    readImage: async (id: string) => {
      if (!image || id !== IMAGE_ID) throw new Error("There is no screenshot with that id in this message. Ask the user to attach the slip again.");
      return readSlipImage(image);
    },
  };

  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      const send = (event: TurnEvent | { type: "done"; messages: ChatMessage[]; ended: string } | { type: "error"; message: string }) =>
        controller.enqueue(encoder.encode(JSON.stringify(event) + "\n"));
      try {
        const result = await runAdvisorTurn([...history, userMessage], context, callClaude, send);
        send({ type: "done", messages: trimHistory(result.messages), ended: result.ended });
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
