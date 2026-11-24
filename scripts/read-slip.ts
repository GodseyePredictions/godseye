/* Read one bet slip screenshot with the live Claude vision call and print what came back.

   Usage: ANTHROPIC_API_KEY=... npm run slip:read -- fixtures/slips/bet365-sgp.png

   Prints the draft the confirm screen would show. If a <name>.expected.json sits beside the image,
   it also lists every field where the live reading differs from the expected one.
   This spends a small amount on the API each time it runs. */
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { toDraft, type ParsedSlip } from "../src/lib/slip/schema.ts";
import { IMAGE_TYPES, SlipReadError, readSlipImage, type ImageType } from "../src/lib/slip/vision.ts";

const file = process.argv[2];
if (!file) {
  console.error("Give the path to a screenshot, for example: npm run slip:read -- fixtures/slips/bet365-sgp.png");
  process.exit(2);
}
const types: Record<string, ImageType> = { ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif" };
const mediaType = types[path.extname(file).toLowerCase()];
if (!mediaType || !IMAGE_TYPES.includes(mediaType)) {
  console.error("That file is not a PNG, JPEG, WebP or GIF image.");
  process.exit(2);
}

let parsed: ParsedSlip;
try {
  parsed = await readSlipImage({ data: readFileSync(file), mediaType });
} catch (error) {
  console.error(error instanceof SlipReadError ? error.message : error);
  process.exit(1);
}
const draft = toDraft(parsed);
console.log(`book: ${draft.book ?? "not shown"} · type: ${draft.betType} · slip price: ${draft.totalOdds ?? "not shown"} · stake: ${draft.stake ?? "not shown"}`);
draft.legs.forEach((l, i) =>
  console.log(`  ${i + 1}. ${l.player ?? "(no player)"} | ${l.market ?? "(no market)"} | ${l.threshold ?? "-"} ${l.side ?? ""} | price ${l.odds ?? "-"}${l.needs.length ? ` | NEEDS: ${l.needs.join(", ")}` : ""}`));
draft.problems.forEach((p) => console.log(`  problem: ${p}`));

const expectedFile = file.replace(/\.[^.]+$/, ".expected.json");
if (existsSync(expectedFile)) {
  const want = toDraft(JSON.parse(readFileSync(expectedFile, "utf8")));
  const diffs: string[] = [];
  if (want.legs.length !== draft.legs.length) diffs.push(`legs: expected ${want.legs.length}, read ${draft.legs.length}`);
  want.legs.forEach((w, i) => {
    const g = draft.legs[i];
    if (!g) return;
    for (const k of ["player", "market", "threshold", "side", "odds"] as const)
      if ((w[k] ?? null) !== (g[k] ?? null)) diffs.push(`leg ${i + 1} ${k}: expected ${w[k] ?? "nothing"}, read ${g[k] ?? "nothing"}`);
  });
  for (const k of ["totalOdds", "stake", "book"] as const)
    if ((want[k] ?? null) !== (draft[k] ?? null)) diffs.push(`${k}: expected ${want[k] ?? "nothing"}, read ${draft[k] ?? "nothing"}`);
  console.log(diffs.length ? `\n${diffs.length} difference(s) from ${path.basename(expectedFile)}:\n  ${diffs.join("\n  ")}` : `\nMatches ${path.basename(expectedFile)}.`);
  process.exit(diffs.length ? 1 : 0);
}
