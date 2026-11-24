/* Draw the sample bet slip screenshots in fixtures/slips.

   Usage: node scripts/make-slip-fixtures.mjs

   These are made-up slips drawn as plain HTML, not captures from a sportsbook: they exist so the
   screenshot reader can be tried without anyone's real account on screen. The players are from the
   week whose data is in public/console/data.js, so the slips grade against the algorithm.
   Each PNG has a hand-written <name>.expected.json beside it: what a correct reading looks like. */
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Playwright is a tool on the machine, not a dependency of the site (npm i -g playwright if it is missing).
const { chromium } = createRequire(import.meta.url)("playwright");

const out = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "fixtures", "slips");

const css = `
  * { box-sizing: border-box; margin: 0; }
  body { font: 15px/1.35 -apple-system, "Segoe UI", Roboto, Arial, sans-serif; background: #1d1f22; color: #f2f2f2; width: 430px; }
  .bar { display: flex; justify-content: space-between; align-items: center; padding: 14px 16px; background: #14614a; font-weight: 700; }
  .bar small { font-weight: 500; opacity: .85; }
  .card { margin: 10px; background: #2a2d31; border-radius: 8px; overflow: hidden; }
  .head { display: flex; justify-content: space-between; padding: 12px 14px; border-bottom: 1px solid #3a3d42; font-weight: 700; }
  .head .px { color: #ffd65a; }
  .game { padding: 8px 14px; font-size: 12.5px; color: #a8adb4; border-bottom: 1px solid #3a3d42; }
  .leg { display: flex; justify-content: space-between; gap: 12px; padding: 11px 14px; border-bottom: 1px solid #34373c; }
  .leg b { display: block; font-weight: 600; }
  .leg span { color: #a8adb4; font-size: 12.5px; }
  .leg .px { color: #ffd65a; font-weight: 700; white-space: nowrap; }
  .foot { padding: 12px 14px; display: grid; grid-template-columns: 1fr auto; row-gap: 6px; }
  .foot .k { color: #a8adb4; }
  .foot .v { font-weight: 700; text-align: right; }
  .light { background: #f4f5f7; color: #15171a; }
  .light .bar { background: #b3122a; color: #fff; }
  .light .card { background: #fff; border: 1px solid #dfe2e6; }
  .light .head, .light .game, .light .leg { border-color: #e6e8eb; }
  .light .game, .light .leg span, .light .foot .k { color: #5c636b; }
  .light .px, .light .head .px { color: #b3122a; }
  .crop { height: 264px; overflow: hidden; }
`;

const slips = {
  // a bet365-style same-game parlay: milestones, one price for the whole bet
  "bet365-sgp": `<body>
    <div class="bar"><span>bet365</span><small>Bet Slip</small></div>
    <div class="card">
      <div class="head"><span>Same Game Parlay · 4 Selections</span><span class="px">+450</span></div>
      <div class="game">WAS Commanders @ NY Giants · Thu 8:15 PM</div>
      <div class="leg"><div><b>Isaiah Likely</b><span>2+ Receptions</span></div></div>
      <div class="leg"><div><b>Rachaad White</b><span>20+ Rushing Yards</span></div></div>
      <div class="leg"><div><b>Isaiah Likely</b><span>20+ Receiving Yards</span></div></div>
      <div class="leg"><div><b>Devin Singletary</b><span>Anytime Touchdown Scorer</span></div></div>
      <div class="foot"><span class="k">Stake</span><span class="v">$25.00</span><span class="k">To Return</span><span class="v">$137.50</span></div>
    </div></body>`,
  // a bet365-style single with its own price
  "bet365-single": `<body>
    <div class="bar"><span>bet365</span><small>Bet Slip</small></div>
    <div class="card">
      <div class="head"><span>Single</span><span class="px">-300</span></div>
      <div class="game">WAS Commanders @ NY Giants · Thu 8:15 PM</div>
      <div class="leg"><div><b>Rachaad White</b><span>Player Rushing Yards · 20+</span></div><span class="px">-300</span></div>
      <div class="foot"><span class="k">Stake</span><span class="v">$30.00</span><span class="k">To Return</span><span class="v">$40.00</span></div>
    </div></body>`,
  // another book: decimal prices per leg, over/under lines, a game line, and the bottom cut off
  "betvictor-cutoff": `<body class="light"><div class="crop">
    <div class="bar"><span>BetVictor</span><small>My Bets</small></div>
    <div class="card">
      <div class="head"><span>Treble</span><span class="px">5.42</span></div>
      <div class="leg"><div><b>Isaiah Likely</b><span>Receptions · Over 1.5 · Commanders v Giants</span></div><span class="px">1.17</span></div>
      <div class="leg"><div><b>New York Giants</b><span>Handicap -2.5 · Commanders v Giants</span></div><span class="px">1.91</span></div>
      <div class="leg"><div><b>Rachaad White</b><span>Rushing Yards · Over 34.5 · Commanders v Giants</span></div><span class="px">2.43</span></div>
      <div class="foot"><span class="k">Stake</span><span class="v">£10.00</span><span class="k">Returns</span><span class="v">£54.20</span></div>
    </div></div></body>`,
};

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 430, height: 600 }, deviceScaleFactor: 2 });
for (const [name, body] of Object.entries(slips)) {
  await page.setContent(`<!doctype html><html><head><meta charset="utf8"><style>${css}</style></head>${body}</html>`);
  const el = await page.$("body");
  await el.screenshot({ path: path.join(out, `${name}.png`) });
  console.log(`wrote fixtures/slips/${name}.png`);
}
await browser.close();
