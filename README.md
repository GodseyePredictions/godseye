# godseye predictions

A Next.js site with three sections:

- `/` is the landing page (`src/app/(site)`): the eye banner, how it works, this week's top algorithm tickets ("Locks of the week") and the NFL and NBA tabs.
- `/nba` is the NBA side (`src/components/NbaApp.tsx`): tonight's slate, a 4-leg and a 6-leg props SGP per game, game scripts, a projection board and availability. It reads `model/nba/output/nba_site.json`, written by `python3 -m nba.run_slate` (see `model/nba/README.md`).
- `/nfl` is the NFL side (`src/app/(console)`; `/app` redirects here): the God's Eye console (algorithm picks, game SGPs, ATD board, SGP builder, quick add, slip audit, model and rules), game parlays and hybrid SGPs from the game-market model, game scripts, and tracker tabs (paste a slip, my bets, my report).

## Run it

    npm install
    npm run dev

`npm test` runs the odds and bet-tracking tests. `npm run build` makes a production build.

## Updating the weekly picks

The console is imported from its exported HTML page:

    python3 -I scripts/import-console.py path/to/console.html

Then refresh the landing page's "Locks of the week" from the new data:

    python3 -I scripts/build-locks.py

The first command rewrites `public/console/data.js` (the week's model data), `public/console/app.js` (the console logic, patched for this site) and `src/app/(console)/console-base.css`. Site-specific styling lives in `src/app/(console)/console.css`.

## Auditing a slip from a screenshot

"Audit a screenshot" (on both the NFL and NBA sides) reads a bet slip image, asks the user to confirm what was read, grades it against the algorithm and suggests removals, swaps and adds.

Try it locally:

    echo "ANTHROPIC_API_KEY=your-key" > .env.local     # never committed
    npm install
    npm run dev

Open http://localhost:3000/nfl#shot and upload `fixtures/slips/bet365-sgp.png`. The sample slips are drawn by `npm run slip:fixtures` from made-up data for the week in `public/console/data.js`; they are not captures from a sportsbook.

To check the screenshot reader on its own, against the expected reading beside each sample:

    ANTHROPIC_API_KEY=your-key npm run slip:read -- fixtures/slips/bet365-sgp.png

Where things live:

- `src/lib/slip/vision.ts` sends the image to Claude (`claude-sonnet-5-5`), which only transcribes. `schema.ts` validates the result and converts prices in code.
- `src/lib/slip/grade.ts` grades each leg and the whole slip. The joint chance comes from `src/lib/advisor/joint.ts`, the console's correlation engine, never from multiplying legs.
- `src/lib/slip/suggest.ts` proposes changes from algorithm output only. `recheck.ts` re-grades saved slips when the algorithm's numbers are rebuilt.
- `src/lib/slip/tools.ts` exposes `parse_slip`, `grade_slip` and `suggest_changes` for the chat agent.

Limits today: the joint chance is NFL only (the NBA output carries no correlations); suggested rungs come from the algorithm's ladder because there is no book price feed, so the user checks the rung and types the new price; saved slips and alerts live in the browser until accounts exist.

## The advisor chat

"Advisor chat" (on both the NFL and NBA sides) is the 1-to-1 chat. A user types a question or attaches a slip screenshot; the advisor answers using the algorithms' output and the bankroll engine.

It needs the same `ANTHROPIC_API_KEY` in `.env.local` as the screenshot audit. Then `npm run dev` and open http://localhost:3000/nfl#advisor.

- `src/lib/advisor/agent.ts` holds the advisor's instructions and the loop: call the model, run the tools it asks for, send the results back. The model call is passed in, so the loop is tested without the network.
- `src/lib/advisor/claude.ts` is the model call. The model is `ADVISOR_MODEL` (default `claude-opus-5-5`).
- Tools: `parse_slip`, `grade_slip`, `suggest_changes` (`src/lib/slip/tools.ts`), `get_player_intel` and `get_game_intel` (`src/lib/advisor/intel.ts`). Every number the advisor quotes comes back from one of them.
- `src/app/api/advisor/route.ts` is the endpoint; `src/components/AdvisorChat.tsx` is the screen.

The conversation, the bankroll settings and tracked bets live in the browser and are sent with each message until accounts exist. The endpoint has no sign-in yet, so do not put it on a public address before logins are in: anyone who found it could spend the API key.

## What is not built yet

Logins, subscriptions, the AI advisor chat, live odds and sportsbook sync. Bets are stored in the visitor's browser until accounts exist.

The separate team-rating model in `model/` is documented in `model/README.md`.

## The shareable single-file app

    node scripts/build-preview.mjs godseye-preview.html

builds the landing page, the NFL console and the NBA side into one HTML file (the Claude artifact). In that file the three share one page: no address is the landing page, `#home`, `#picks` and the other console tabs are NFL, and `#nba-home`, `#nba-sgp` and so on are NBA. Rebuild and republish it after a new NFL import or a new NBA slate.

## Player photos on the landing page

The featured-player cards show initials unless a photo exists at `public/players/<name-slug>.jpg` (for example `patrick-mahomes.jpg`, `shai-gilgeous-alexander.jpg`). No photos ship with the repo. Add only images you hold a licence for, then re-run `python3 -I scripts/build-locks.py` and rebuild.
