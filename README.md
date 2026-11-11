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

## What is not built yet

Logins, subscriptions, the AI advisor chat, live odds and sportsbook sync. Bets are stored in the visitor's browser until accounts exist.

The separate team-rating model in `model/` is documented in `model/README.md`.
