# godseye NBA module

Projects full distributions for NBA player props and builds bet365 same-game parlays from them. The standing rules are in `CLAUDE.md`; what data exists and what does not is in `docs/nba_audit.md`.

Run everything from `model/`.

    pip install pandas numpy scipy scikit-learn pytest
    python3 -m nba.fetch_data build            # three seasons of games into data/nba.sqlite (resumable, about 20 minutes cold)
    python3 -m nba.refresh injuries-history    # official injury reports for every past game date (resumable)
    python3 -m pytest nba/tests                # 39 tests

## Daily use

    python3 -m nba.run_slate                   # refresh, availability gate, game script, minutes, player models, simulation, tickets
    python3 -m nba.run_slate game GAME_ID      # re-run one game when news breaks
    python3 -m nba.run_slate watch             # re-check availability; re-run only games where a status changed
    python3 -m nba.run_slate place TICKET_ID [STAKE] [PRICE]   # mark a ticket placed: timestamped and locked
    python3 -m nba.run_slate grade [DATE]      # nightly grading and report card
    python3 -m nba.refresh gameday             # only what changes late: injuries, starters, odds, closing prices
    python3 -m nba.refresh csv FILE GAME_ID    # load a pasted bet365 sheet (columns: player, market, rung or line, price)

Prices come from The Odds API when `ODDS_API_KEY` is set in the environment, or from a pasted sheet. With neither, cards and projections are produced and every game says "no bet": a leg needs a rung the book actually offers.

## Order of work for one game

1. `availability.py` - who is confirmed in, questionable, doubtful, out, unknown (official report, timestamped).
2. `game_sim.py` - team projection, blend with the market, 10,000 simulated games, blowout states. Runs before any player number.
3. `minutes.py` and `inout.py` - minutes in each simulated game; where an absent teammate's volume goes.
4. `props.py` - per-minute rates: baseline, then form, then tonight, every adjustment itemised.
5. `player_sim.py` - hands each simulated game's team totals out to its players; probabilities are counted.
6. `sgp.py` and `common/tickets.py` - legs, eligibility rules, tickets, the printed card.
7. `ledger.py` and `grading.py` - timestamped record, locking, grading, report card.

Supporting files: `config.py` (every threshold), `store.py` (tables and the point-in-time view), `features.py` and `prep.py` (pre-game features), `fetch_data.py`, `espn.py`, `injuries.py`, `sources.py`, `ids.py`, `schedule.py`, `refresh.py`, `pipeline.py`, `backtest.py`, `validate.py`, `health.py`.

## Backtest

    python3 -m nba.backtest 2000               # walk-forward over 2024-25 and 2025-26, about 30 minutes on 4 cores
    python3 -m nba.validate                    # writes output/backtest_report.json and the tables in docs/nba_backtest.md

Results and limits are in `docs/nba_backtest.md`. In short: there are no historical book prices in this project, so the backtest measures calibration and hit rates, not profit.
