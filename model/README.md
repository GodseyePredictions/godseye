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
