# godseye NFL model

`nfl_model.py` rates every team in points and predicts the home margin and win
chance for each game. `backtest.py` tunes it on seasons up to 2014, then scores
it on 2015 onward against the closing betting line.

Run it:

    pip install pandas numpy
    python3 backtest.py

Outputs land in `output/`: `backtest.json` (the scorecard) and
`predictions.json` (the next unplayed week).

Game data is `data/games.csv` from the public nflverse `nfldata` repository.
Refresh it by downloading the latest copy of that file.

## Current result

Version 1 does not beat the market. Its margin error is higher than the closing
spread's, and betting its disagreements with the spread loses money at -110.
It is a baseline to improve on, not a source of picks.

## Game-script metrics: time of possession and penalties

`fetch_data.py` downloads play-by-play (not committed; about 105 MB for 2021 to 2026) and refreshes `data/games.csv`. `team_metrics.py` then builds opponent-adjusted team ratings for time of possession and for offensive and defensive penalties, forecasts the next week's games alongside the market spread, total and moneyline, and writes `output/team_metrics.json`.

    pip install pandas numpy
    python3 fetch_data.py
    python3 team_metrics.py

Every rating is checked walk-forward on 2024 onward. These stats are mostly noise game to game: the possession forecast beats a 50/50 guess by about 4%, mostly through the point spread, and penalty forecasts beat the league average by under 1%.

## Game markets: moneylines, spreads, totals, interceptions and hybrid SGPs

    python3 fetch_data.py 2015 2026     # play-by-play, about 220 MB, not committed
    python3 features.py                 # builds data/cache/*.csv (committed, small)
    python3 game_markets.py             # writes output/game_markets.json

`game_markets.py` rates every team each week on efficiency, pace, possession, turnovers, penalties and its quarterback, forecasts margin and total without seeing the line, then blends that with the market line using a weight fitted on earlier seasons. From the blended numbers it builds 4, 6 and 8-leg moneyline, spread and total tickets ranked by value at the listed price, interception chances for each starting quarterback, and hybrid same-game parlays that tie a game leg to the console's touchdown legs with correlations measured on past games.

The scorecard in the output is walk-forward on 2020 onward. The model does not beat the closing line: the fitted weight on its own view is about 7% for margins and 13% for totals, and single bets on its sides lose roughly the bookmaker's margin. The tickets are fair-price references, not proven edges.

It reads `../public/console/data.js` for this week's touchdown probabilities, weather, singles-only list and injury flags, so re-run it after importing a new console export.

### Matchup checks, safe picks and alternative lines

`matchups.py` (run it after `features.py`) builds the unit-level tables: inside and outside runs against the front, receiver targets by depth and area, tight end targets, pressure, play-calling tendencies, and how many usual starters on the offensive line, defence and skill positions are ruled Out or Doubtful. `game_markets.py` rates those the same way as everything else and feeds them into the forecast.

Every moneyline and spread pick carries seven checks: home vs away, personnel, offensive play-calling, defensive play-calling and pressure, running backs vs defensive line with line health, receivers (deep, slot area, outside), and tight ends. A pick missing any check is dropped. A favourite needs the checks to lean its way to make a ticket. "Safe" moneylines need a 65% model chance, two more checks for than against, and personnel not against.

Public data has no slot alignment or coverage assignments, so the slot is measured by short-middle targets and coverage by what each defence allows in that area. Injury designations for the coming week appear late in the week, so re-run `fetch_data.py`, `matchups.py` and `game_markets.py` after they post.

On 2020 onward: favourites that passed the safe rule returned -0.6% (555 bets), those that did not -3.8% (297), and those with the checks against them -6.8% (59). Alternative-line forecasts were within a point or two of what happened at every distance tested.

### Live odds, prop hybrids and touchdown slips

`fetch_odds.py` pulls current game lines (DraftKings, through ESPN's public scoreboard) into `data/live_odds.json` and writes `../public/console/odds-update.js`, which refreshes the lines the console displays. `game_markets.py` uses those prices for the coming week when the file is present. There is no bet365 feed; in the app a user can type their own book's price on any game leg and the value figures and tickets use it.

Hybrids now include player props from the console's prop ladders, joined to game legs with correlations measured on past games (for example a running back's carries with his team winning, 0.37; a quarterback's pass attempts with his team winning, -0.35), and to each other with the console's own prop correlations. Each game also gets 3 and 4-pick touchdown slips: running backs, receivers and tight ends, at most two per team and never two teammates at the same position.

Weekly order: `fetch_data.py`, `features.py`, `matchups.py`, `fetch_odds.py`, `game_markets.py`.

### User reads and late news

`overrides.json` records news the weekly snapshot missed (a player back from injury, a role change). `apply_overrides.py` re-estimates the affected players from expected snap share, marks them singles only, withdraws prop lines and precomputed tickets priced on the old role, logs the read in the console's personnel panel, and writes `../public/console/personnel-update.js`. `game_markets.py` applies the same changes before building slips and hybrids. These numbers are estimates, labelled as such, until the touchdown model is re-run.

### Roster freshness audit (run before trusting any pick)

`freshness.py` compares the console snapshot with the latest snap counts, injury reports and roster status. It flags regular players missing from the snapshot, priced teammates whose numbers assumed that player was out, priced players now ruled out, and teams the snapshot does not price. `game_markets.py` runs it on every build: players with an open alert are kept off slips and hybrids, and a game with an open quarterback alert or an unpriced team is held off every ticket. Confirmed alerts (the team's report is posted) also withdraw the console's own precomputed tickets through `../public/console/freshness-update.js`. An alert clears when the report rules the player out or `overrides.json` records a read for him.

`python3 run_week.py` runs every step in order. Run it after each injury report posts and again when inactives are announced.
