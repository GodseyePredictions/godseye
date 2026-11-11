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
