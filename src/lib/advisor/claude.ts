/**
 * The advisor's connection to Claude. Server only: it needs ANTHROPIC_API_KEY in the environment.
 *
 * The model is ADVISOR_MODEL (default Claude Sonnet 5.5). The request streams, so the answer appears as
 * it is written. The instructions and the tool list are identical for every user and message, so they are
 * cached and billed at the cache rate after the first request; each user's own context follows them.
 */
import Anthropic from "@anthropic-ai/sdk";
import type { BetaMessageParam, BetaTextBlockParam, BetaToolUnion } from "@anthropic-ai/sdk/resources/beta/messages/messages";
import type { CallModel } from "./agent.ts";

export const ADVISOR_MODEL = process.env.ADVISOR_MODEL || "claude-sonnet-5-5";

export class AdvisorError extends Error {
  readonly status: number;
  constructor(message: string, status = 502) {
    super(message);
    this.status = status;
  }
}

let client: Anthropic | null = null;

export const callClaude: CallModel = async (request, onText) => {
  client ??= new Anthropic();
  const system: BetaTextBlockParam[] = [{ type: "text", text: request.system, cache_control: { type: "ephemeral" } }];
  if (request.context) system.push({ type: "text", text: request.context });
  try {
    const stream = client.beta.messages.stream({
      model: ADVISOR_MODEL,
      max_tokens: 16000,
      // thinking is left to the model (adaptive); medium effort suits a conversation with a few tool calls
      output_config: { effort: "medium" },
      // if the model declines a request, the API retries on its default fallback model inside the same call
      betas: ["server-side-fallback-2026-07-01"],
      fallbacks: "default",
      system,
      ...(request.tools.length ? { tools: request.tools as unknown as BetaToolUnion[] } : {}),
      messages: request.messages as BetaMessageParam[],
    });
    stream.on("text", onText);
    const message = await stream.finalMessage();
    return {
      content: message.content,
      stop_reason: message.stop_reason,
      usage: {
        inputTokens: message.usage.input_tokens ?? 0,
        outputTokens: message.usage.output_tokens ?? 0,
        cacheReadTokens: message.usage.cache_read_input_tokens ?? 0,
        cacheWriteTokens: message.usage.cache_creation_input_tokens ?? 0,
      },
    };
  } catch (error) {
    if (error instanceof Anthropic.AuthenticationError) throw new AdvisorError("The Claude API key is not valid. Check ANTHROPIC_API_KEY on the server.", 500);
    if (error instanceof Anthropic.RateLimitError) throw new AdvisorError("The advisor is busy right now. Try again in a minute.", 429);
    if (error instanceof Anthropic.BadRequestError) throw new AdvisorError(`The advisor could not process that message: ${error.message}`, 400);
    if (error instanceof Anthropic.APIError) throw new AdvisorError(`The advisor is unavailable (${error.status ?? "no status"}). Try again.`, 502);
    // The SDK raises a plain Error, before any request is sent, when it finds no credential in the environment.
    if (error instanceof Error && /authentication method/i.test(error.message))
      throw new AdvisorError("The advisor is not set up on this server: no Claude API key was found (ANTHROPIC_API_KEY).", 503);
    throw error;
  }
};
