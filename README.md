# godseye predictions

A Next.js site with two sections:

- `/` is the marketing page (`src/app/(site)`).
- `/app` is the product (`src/app/(console)`): the God's Eye console (algorithm picks, game SGPs, ATD board, SGP builder, quick add, slip audit, model and rules) plus tracker tabs (paste a slip, my bets, my report, game predictions).

## Run it

    npm install
    npm run dev

`npm test` runs the odds and bet-tracking tests. `npm run build` makes a production build.

## Updating the weekly picks

The console is imported from its exported HTML page:

    python3 -I scripts/import-console.py path/to/console.html

This rewrites `public/console/data.js` (the week's model data), `public/console/app.js` (the console logic, recoloured for this site) and `src/app/(console)/console-base.css`. Site-specific styling lives in `src/app/(console)/console.css`.

## What is not built yet

Logins, subscriptions, the AI advisor chat, live odds and sportsbook sync. Bets are stored in the visitor's browser until accounts exist.

The separate team-rating model in `model/` is documented in `model/README.md`.
