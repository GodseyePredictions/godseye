/**
 * Read a bet slip screenshot with Claude (vision) into the ParsedSlip schema.
 *
 * Server only: it needs ANTHROPIC_API_KEY (or another credential the SDK finds in the environment).
 * The model only reads what is printed. It does no arithmetic, converts no prices and rates nothing;
 * prices are converted in schema.ts and every probability comes from the algorithms.
 */
import Anthropic from "@anthropic-ai/sdk";
import { betaZodOutputFormat } from "@anthropic-ai/sdk/helpers/beta/zod";
import { ParsedSlipSchema, type ParsedSlip } from "./schema.ts";

export const VISION_MODEL = "claude-sonnet-5-5";
export const IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp", "image/gif"] as const;
export type ImageType = (typeof IMAGE_TYPES)[number];
/** The API takes images up to 5 MB each once encoded. */
export const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

const SYSTEM = `You transcribe sportsbook bet slip screenshots into structured data for a betting analysis product. The data you return is checked by the user and then graded by statistical models, so an accurate transcription matters more than a complete one: a wrong player or number would be graded as if it were the user's bet.

Read only what is printed in the image.
- Copy names, markets, numbers, prices and the stake exactly as shown. Do not correct spellings, convert odds between formats, round a line, or work anything out.
- If part of the slip is cut off, covered, blurred or too small to read with confidence, set that field to null and add its name to that leg's "unreadable" list (or the slip's "unreadable" list for the total price, stake or book). Never fill a gap from what is likely or from your knowledge of the sport.
- One entry in "legs" per selection, in the order shown. A same-game parlay with four selections has four legs.
- bet365 player props are usually milestones such as "225+ Passing Yards" or "To Record 6+ Assists": set side to "milestone" and threshold to the printed number. For "Over 224.5" or "Under 4.5" set side to "over" or "under" and keep the printed line.
- "odds_text" is the leg's own price only if the slip prints one beside that leg. Same-game parlays often show one price for the whole bet: put that in "total_odds_text" and leave each leg's "odds_text" null.
- Markets that are not player props (moneyline, spread, totals, anything else) get market "other" and player null, with the printed text in "market_text".
- Name the book only if its name or logo is visible.
- If the image is not a bet slip, set "is_bet_slip" to false and return no legs.`;

export class SlipReadError extends Error {
  readonly status: number;
  constructor(message: string, status = 502) {
    super(message);
    this.status = status;
  }
}

let client: Anthropic | null = null;

/** The model's reading of the image, already validated against the schema. */
export async function readSlipImage(image: { data: Buffer | Uint8Array; mediaType: ImageType }): Promise<ParsedSlip> {
  if (image.data.byteLength > MAX_IMAGE_BYTES) throw new SlipReadError("That image is larger than 5 MB. Crop it to the slip and try again.", 413);
  try {
    client ??= new Anthropic();
  } catch {
    // the SDK found no credential in the environment
    throw new SlipReadError("The screenshot reader is not set up on this server: no Claude API key was found (ANTHROPIC_API_KEY).", 503);
  }
  let response;
  try {
    response = await client.beta.messages.parse({
      model: VISION_MODEL,
      max_tokens: 16000,
      // a reading task: low effort is enough, and it keeps the wait short
      output_config: { effort: "low", format: betaZodOutputFormat(ParsedSlipSchema) },
      // if the model declines, the API retries on its default fallback model inside the same call
      betas: ["server-side-fallback-2026-07-01"],
      fallbacks: "default",
      system: SYSTEM,
      messages: [
        {
          role: "user",
          content: [
            { type: "image", source: { type: "base64", media_type: image.mediaType, data: Buffer.from(image.data).toString("base64") } },
            { type: "text", text: "Transcribe this bet slip." },
          ],
        },
      ],
    });
  } catch (error) {
    if (error instanceof Anthropic.AuthenticationError) throw new SlipReadError("The Claude API key is missing or not valid. Set ANTHROPIC_API_KEY on the server.", 500);
    if (error instanceof Anthropic.RateLimitError) throw new SlipReadError("The screenshot reader is busy. Try again in a minute.", 429);
    if (error instanceof Anthropic.BadRequestError) throw new SlipReadError(`The image could not be read: ${error.message}`, 400);
    if (error instanceof Anthropic.APIError) throw new SlipReadError(`The screenshot reader failed (${error.status ?? "no status"}). Try again.`, 502);
    // The SDK raises a plain Error, before any request is sent, when it finds no credential in the environment.
    if (error instanceof Error && /authentication method/i.test(error.message))
      throw new SlipReadError("The screenshot reader is not set up on this server: no Claude API key was found (ANTHROPIC_API_KEY).", 503);
    throw error;
  }
  if (response.stop_reason === "refusal") throw new SlipReadError("The screenshot reader declined this image. Paste the slip as text instead.", 422);
  if (response.stop_reason === "max_tokens") throw new SlipReadError("The slip was too long to read in one go. Crop it to fewer legs and try again.", 422);
  if (!response.parsed_output) throw new SlipReadError("The screenshot reader returned something that is not a slip. Try a clearer screenshot.", 422);
  return response.parsed_output;
}
