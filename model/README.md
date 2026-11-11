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
