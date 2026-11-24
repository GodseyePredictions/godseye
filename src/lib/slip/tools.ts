/**
 * The slip audit as three tools the chat agent can call: parse_slip, grade_slip, suggest_changes.
 *
 * The agent reads a screenshot and explains results. Every number it repeats comes back from these
 * functions, which read the algorithms' output and call the staking engine. If a tool returns no number
 * (an unrated leg, a parlay's chance where the output has no correlations), the agent has none to state.
 *
 * `TOOLS` are the definitions to pass to the Messages API (`tools: TOOLS`, each is `strict`).
 * `runTool` executes a call. `parse_slip` needs the vision model, so its image handler is passed in
 * by the server (src/lib/slip/vision.ts); everything else is plain code and runs anywhere.
 */
import type { Catalog, Market, Side, Sport } from "../advisor/legs.ts";
import type { Account, Tonight } from "../staking.ts";
import { gradeSlip, type SlipGrade, type SlipLegInput } from "./grade.ts";
import { MARKET_VALUES, draftMarket, toDraft, type SlipDraft } from "./schema.ts";
import { suggestChanges, type Suggestions } from "./suggest.ts";

export type Catalogs = Partial<Record<Sport, Catalog>>;
export type Money = { account?: Account | null; tonight?: Tonight; now?: Date };

/** The confirmed draft, as the legs the grader takes. */
export function draftToInput(draft: SlipDraft): SlipLegInput[] {
  return draft.legs.map((l) => ({
    player: l.player, market: draftMarket(l), threshold: l.threshold, side: l.side, odds: l.odds,
    text: [l.player, l.market === "atd" ? "anytime touchdown" : `${l.threshold ?? ""}${l.side === "under" ? " under" : l.threshold !== null ? "+" : ""} ${l.marketText}`].filter(Boolean).join(" ").replace(/\s+/g, " ").trim(),
  }));
}

/** parse_slip, second half: validate the vision model's JSON and build the draft the user confirms. */
export function parseSlipFromJson(raw: unknown): SlipDraft {
  return toDraft(raw);
}

type ToolLeg = { player: string | null; market: string | null; threshold: number | null; side: string | null; odds: number | null };
export type GradeArgs = { sport: string; legs: ToolLeg[]; total_odds: number | null };
export type SuggestArgs = GradeArgs & { leg_count: number | null; book: string | null };

function catalogFor(sport: string, catalogs: Catalogs): Catalog {
  const c = catalogs[sport as Sport];
  if (!c) throw new Error(`The ${sport} algorithm's output is not loaded, so this slip cannot be graded. Covered sports: ${Object.keys(catalogs).join(", ") || "none"}.`);
  return c;
}
const toInput = (legs: ToolLeg[]): SlipLegInput[] =>
  legs.map((l) => ({
    player: l.player,
    market: l.market && (MARKET_VALUES as readonly string[]).includes(l.market) && l.market !== "other" ? (l.market as Market) : null,
    threshold: l.threshold,
    side: l.side === "under" ? "under" : l.side === null && l.market === null ? null : ("over" as Side),
    odds: l.odds,
  }));

export function gradeSlipTool(args: GradeArgs, catalogs: Catalogs, money: Money = {}): SlipGrade {
  return gradeSlip(toInput(args.legs), catalogFor(args.sport, catalogs), { totalOdds: args.total_odds, ...money });
}

export function suggestChangesTool(args: SuggestArgs, catalogs: Catalogs, money: Money = {}): Suggestions {
  const catalog = catalogFor(args.sport, catalogs);
  const grade = gradeSlip(toInput(args.legs), catalog, { totalOdds: args.total_odds, ...money });
  return suggestChanges(grade, catalog, { legCount: args.leg_count, book: args.book });
}

// ---------- definitions for the Messages API ----------
const LEG_SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: ["player", "market", "threshold", "side", "odds"],
  properties: {
    player: { type: ["string", "null"], description: "Player name as confirmed by the user. Null for a game line." },
    market: { type: ["string", "null"], enum: [...MARKET_VALUES, null], description: "Canonical market, or null if it is not a player market the algorithms cover." },
    threshold: { type: ["number", "null"], description: 'The milestone: 225 for "225+" or "Over 224.5". Null for anytime touchdown.' },
    side: { type: ["string", "null"], enum: ["over", "under", null] },
    odds: { type: ["number", "null"], description: "The leg's own price in American odds, or null if the slip shows none." },
  },
} as const;

const SLIP_PROPS = {
  sport: { type: "string", enum: ["NFL", "NBA"], description: "Which algorithm grades the slip. Each sport has its own algorithm and rules." },
  legs: { type: "array", items: LEG_SCHEMA, description: "The legs exactly as the user confirmed them." },
  total_odds: { type: ["number", "null"], description: "The book's price for the whole slip in American odds, or null." },
} as const;

export const TOOLS = [
  {
    name: "parse_slip",
    description:
      "Read a bet slip screenshot the user has uploaded into structured legs (player, market, milestone, prices, stake, book). " +
      "Call this first whenever the user shares a slip image. It returns a draft: show it to the user and get their confirmation or corrections " +
      "before calling grade_slip. Fields it could not read come back listed under `needs`; ask the user for them, never fill them in yourself.",
    strict: true,
    input_schema: {
      type: "object", additionalProperties: false, required: ["image_id"],
      properties: { image_id: { type: "string", description: "The id of the uploaded image, as given in the conversation." } },
    },
  },
  {
    name: "grade_slip",
    description:
      "Grade a confirmed slip against the Godseye algorithm for its sport. Returns, per leg, the algorithm's probability, the probability the leg's price implies, " +
      "the edge, the algorithm's game-script risk note and injury designation, or `unrated` with the reason. For the whole slip it returns the joint hit " +
      "probability from the correlation engine, fair odds, value at the book's price, ticket-rule findings and a stake from the bankroll engine. " +
      "Call it only after the user has confirmed the legs. Any field that comes back null has no number: say it is not available, do not estimate it.",
    strict: true,
    input_schema: { type: "object", additionalProperties: false, required: ["sport", "legs", "total_odds"], properties: SLIP_PROPS },
  },
  {
    name: "suggest_changes",
    description:
      "Suggest removals, swaps and adds for a confirmed slip, from algorithm output only, and return the improved slip with its joint probability and fair odds. " +
      "Use it when the user asks how to improve a slip or what to change. Pass `leg_count` when the user says how many legs they want, and `book` when they name their sportsbook. " +
      "Suggested rungs come from the algorithm's ladder: tell the user to check the book lists the rung and to give you the new price before quoting value or a stake.",
    strict: true,
    input_schema: {
      type: "object", additionalProperties: false, required: ["sport", "legs", "total_odds", "leg_count", "book"],
      properties: {
        ...SLIP_PROPS,
        leg_count: { type: ["integer", "null"], description: "How many legs the user wants on the final slip, or null to keep the current count." },
        book: { type: ["string", "null"], description: "The user's sportsbook, e.g. bet365, or null." },
      },
    },
  },
] as const;

export type ToolName = (typeof TOOLS)[number]["name"];

/** Run one tool call. `readImage` turns an uploaded image id into the vision model's JSON (server side). */
export async function runTool(
  name: string,
  input: unknown,
  ctx: { catalogs: Catalogs; money?: Money; readImage?: (imageId: string) => Promise<unknown> },
): Promise<SlipDraft | SlipGrade | Suggestions> {
  switch (name) {
    case "parse_slip": {
      if (!ctx.readImage) throw new Error("Reading screenshots is not available here.");
      return parseSlipFromJson(await ctx.readImage((input as { image_id: string }).image_id));
    }
    case "grade_slip":
      return gradeSlipTool(input as GradeArgs, ctx.catalogs, ctx.money);
    case "suggest_changes":
      return suggestChangesTool(input as SuggestArgs, ctx.catalogs, ctx.money);
    default:
      throw new Error(`Unknown tool: ${name}`);
  }
}
