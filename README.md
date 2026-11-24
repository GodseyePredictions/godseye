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

The NFL console takes its numbers straight from the NFL algorithm in `model/nfl`. After the algorithm's weekly build:

    cd model/nfl
    python run.py site --season 2026 --week 12     # checks the data, then writes outputs/site/nfl_site.json
    cd ../..
    npm run nfl:site                                # puts it on the site and refreshes "Locks of the week"

The first command refuses to write anything if the data is malformed or breaks a ticket rule (`model/nfl/attd/site_check.py`). The second rewrites `public/console/data.js` (the week's model data), `public/console/app.js` (the console logic from `model/nfl/attd/site_template.html`, patched for this site), `src/app/(console)/console-base.css` and `model/output/locks.json`. Site-specific styling lives in `src/app/(console)/console.css`.

An exported console page can still be imported by hand with `python3 -I scripts/import-console.py path/to/console.html`.

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

"Advisor chat" (on both the NFL and NBA sides) is one agent for every subscriber, made personal by that user's own record: profile, bankroll, recent slips, and a running summary of earlier conversations, all loaded on every message.

Try it locally with the real model (needs `ANTHROPIC_API_KEY` in `.env.local`):

    ADVISOR_DEV_TIER=pro npm run dev          # then open http://localhost:3000/nfl#advisor

Or without an API key, on a scripted stand-in that is clearly labelled in the chat and exercises everything except the model itself:

    ADVISOR_DEMO=1 npm run dev

Demo walk-through: attach `fixtures/slips/bet365-sgp.png` and send "Is this worth playing?", then "yes", then "can you swap anything to make it better?", then "my book has the new one at +320, how much?", then "placed it, $20 at +320".

How it is put together:

- `src/lib/advisor/agent.ts`: the instructions (the hard rules), the eleven tools and the loop. The model call is passed in, so the loop is tested without the network.
- `src/lib/advisor/guard.ts`: the check on every reply. A percentage, price, dollar amount, unit stake or named leg that no tool returned is not shown: the model is asked to rewrite once, then a safe reply is used.
- `src/lib/advisor/user-tools.ts`, `picks.ts`, `intel.ts`, `src/lib/slip/tools.ts`: the tools. `size_bet` takes legs and a price, never a probability.
- `src/lib/advisor/memory.ts`: stored conversations and the profile summary. Users can view and clear both from the History button.
- `src/lib/advisor/subscription.ts`: plan check, daily message caps (`ADVISOR_LIMITS`), archive on cancel and restore on return. The Stripe webhook (below) calls `applySubscriptionEvent`; `ADVISOR_DEV_TIER` grants a plan locally without payments.
- `src/lib/advisor/usage.ts` and `npm run usage:report`: token usage and API cost per user.
- `src/lib/store/`: the per-user store. Postgres when `DATABASE_URL` is set (`postgres.ts`, tables in `db/schema.sql`), local files under `.data/` otherwise.
- `src/lib/advisor/claude.ts`: the model call. `ADVISOR_MODEL` defaults to `claude-sonnet-5-5`.

There is no sign-in yet: the user id is an anonymous id the browser keeps. Do not put the API routes on a public address before logins are in, because anyone who found them could spend the API key and an id proves nothing about who is asking.

## The database

User records (profile, bankroll, bets, saved slips, conversations, subscription, API usage) go to Postgres when `DATABASE_URL` is set, and to local files otherwise. Any Postgres works (Neon is the plan for the hosted site).

    DATABASE_URL=postgres://... npm run db:migrate      # creates the tables in db/schema.sql; safe to run again

Each update runs in one transaction with the user's row locked, so two requests for the same user cannot overwrite each other. The store's own test runs only when given a scratch database (it uses and drops a `godseye_test` schema):

    TEST_DATABASE_URL=postgres://... npm test

## Subscriptions (Stripe)

`POST /api/billing/webhook` receives Stripe's subscription events, checks the signature, and turns them into plan changes (`src/lib/billing/stripe.ts`). To connect a Stripe account, set three environment variables and one thing at checkout:

- `STRIPE_WEBHOOK_SECRET`: the signing secret of the webhook endpoint.
- `STRIPE_PRICE_PRO` and `STRIPE_PRICE_ELITE`: the price ids of each plan (comma separated if a plan has monthly and yearly prices).
- The subscription's metadata must carry `godseye_user`, the user's id.

Point the endpoint at `customer.subscription.created`, `.updated` and `.deleted`. A cancel archives the user's chat history for 90 days and a return inside that time restores it. Late or repeated events are ignored. The checkout page itself is not built: it needs the Stripe account and logins.

## What is not built yet

Logins, a checkout page, live odds and sportsbook sync. Bankroll settings, tracked bets and saved slips in the consoles are still stored in the visitor's browser until logins exist; advisor conversations are stored on the server.

The NFL player-prop and anytime-touchdown algorithm is in `model/nfl` (see `model/nfl/README.md`). The NFL game-market and team-rating code in `model/` is documented in `model/README.md`, and the NBA module in `model/nba/README.md`. Each sport's algorithm is separate.

## The shareable single-file app

    node scripts/build-preview.mjs godseye-preview.html

builds the landing page, the NFL console and the NBA side into one HTML file (the Claude artifact). In that file the three share one page: no address is the landing page, `#home`, `#picks` and the other console tabs are NFL, and `#nba-home`, `#nba-sgp` and so on are NBA. Rebuild and republish it after a new NFL import or a new NBA slate.

## Player photos on the landing page

The featured-player cards show initials unless a photo exists at `public/players/<name-slug>.jpg` (for example `patrick-mahomes.jpg`, `shai-gilgeous-alexander.jpg`). No photos ship with the repo. Add only images you hold a licence for, then re-run `python3 -I scripts/build-locks.py` and rebuild.
