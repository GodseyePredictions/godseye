# godseye NHL engine

A standalone engine: its own data, tables, config and (in later phases) models and tickets. It imports nothing from the NFL
or NBA code; only `model/common/` is shared. The spec is `SPEC.md`. The spec's `godseye/nhl/` is `model/nhl/` in this
repository and its `godseye/shared/` is `model/common/`.

**Built so far: all five phases, as a test build.** Ingest and derived tables (Phase 1), gates and game sim (2), player
props (3), correlation and tickets (4), backtest and grading (5). No NHL market has been tested against closing lines,
because the project holds no historical NHL prices, so by the spec's own rule no market is live: slips are test slips.

Run everything from `model/`.

    pip install pandas numpy pyyaml pytest
    python3 -m nhl.run_daily nightly       # schedule, finished games, MoneyPuck xG, rosters, every derived table
    python3 -m nhl.run_daily gameday       # goalies, lines and PP units, referees, odds and ladders
    python3 -m nhl.run_daily watch         # from 90 minutes before puck drop, gameday every 30 minutes until goalies are confirmed
    python3 -m nhl.run_daily slate [DATE]  # gameday refresh, then gates, sim, props and tickets for every game not started
    python3 -m nhl.run_daily grade         # nightly ingest, then grade finished tickets and rewrite the report card
    python3 -m nhl.backtest [SIMS] [FIRST_SEASON]   # walk-forward backtest, writes output/backtest_report.json
    python3 -m nhl.run_daily derive [UTC]  # rebuild the derived tables as of a time
    python3 -m nhl.run_daily status
    python3 -m nhl.spotcheck               # the Phase 1 check: 3 teams' xG and 5 players' TOI against the sources
    python3 -m pytest nhl/tests

The first `nightly` pulls three seasons plus the current one (about 13,000 requests, 25 minutes) into `data/raw/`; after that a
night is a few dozen requests. `data/nhl.sqlite` and `data/raw/` are not committed.

## Order of work for one game (`slate.py`)

1. `gates.py` - both starting goalies confirmed, game-day lines in hand, injury check on the player and his line-mates,
   rung on the book's ladder. Any fail removes the leg, and the slate says which and why.
2. `sim/game_sim.py` - expected goals by strength (5v5, power play, shorthanded), then the itemised adjustments (opposing
   goalie's GSAx, home ice, rest and travel, absent regulars), then 20,000 simulated games: score effects re-read every
   half-period, the empty-net window, overtime and shootout. League constants are measured from the store (`sim/fit.py`).
3. `props/` - shots, hits and blocks drawn around each simulated game's own script; goals and assists handed out from that
   game's team goals (points are the joint draw); saves are the opponent's simulated shots minus goals, with pull risk.
4. `correlation.py` - a slip's chance is the share of simulated games in which every leg hits.
5. `tickets.py` - floor rungs at 70%+, a 4-leg and a 6-leg props SGP, an anytime-scorer slip on its own, and a game-line
   closer when the edge over the listed price clears the bar. Blowout guard, two-points-per-line and saves rules applied.
6. `grade.py` - grades the ledger from the NHL's play-by-play and writes the private report card.

Outputs in `output/`: `nhl_site.json` (what the site shows; no results), `nhl_slate.json` (full detail), `nhl_ledger.json`
(every ticket with the time it was made, locked at puck drop), `nhl_report_card.json`, `backtest_report.json`.

**Paper mode.** The only prices in hand are DraftKings game lines from the NHL's own partner feed. No prop ladder is
connected (no `ODDS_API_KEY`, no bet365 sheet), so `gates.require_book_rung` is false: props legs use the spec's standard
milestone rungs (`tickets.paper_ladders`), are marked "rung not verified", carry no price and no stake. Set it to true once
a ladder source is connected and the fourth gate applies as written.

**What the sim found in the data** (4,320 games): goals are slightly under-dispersed (variance/mean 0.97), so the
negative-binomial mixing is set near zero; trailing teams shoot and score more and leading teams block more, but leading
teams hit less, not more; and tied games tighten up late, which the sim needs to reproduce the league's 22% overtime rate.

## Backtest (`output/backtest_report.json`)

Walk-forward over 4,093 games (2023-24 to 23 November 2026), 2,000 simulated games each, every game priced only with
what was known before its date. Starting goalies and dressed skaters are taken as known; there are no game-day lines.
The scoring scale, shot spread and saves floor in `config.yaml` were set from this same backtest, so these numbers are
in-sample for those three settings.

| Market | Legs at or above the floor | Model said | Actually hit |
| --- | --- | --- | --- |
| Shots on goal | 14,210 | 76.3% | 78.7% |
| Hits | 56,876 | 80.4% | 82.0% |
| Blocked shots | 26,055 | 76.8% | 80.0% |
| Points | 812 | 73.6% | 79.1% |
| Saves (floor 85%) | 2,096 | 88.8% | 86.9% |

- **Moneyline:** calibrated (home win predicted 53.2%, actual 54.3%) and better than the base rate (Brier 0.2386 against 0.2482).
- **Puck line:** the favourite at -1.5 is over-rated by about two points (38.4% predicted, 36.4% actual).
- **Totals:** no better than the base rate, so totals are left out of game-line closers.
- **Saves:** the weakest prop. Legs the model calls 85 to 95% hit two to four points less often, so saves legs need 85%.
- **Assists and anytime scorers** almost never reach 70%, so they do not appear in props SGPs.
- **ROI and closing line value: not available.** No historical NHL prices are held. Until they are, no market is live.

## Sources

| Source | Module | What is taken | Status |
| --- | --- | --- | --- |
| NHL API (`api-web.nhle.com`, `api.nhle.com/stats`) | `ingest/nhl_api.py` | schedule, play-by-play, shift charts, officials and scratches, league TOI by strength, rosters | live |
| MoneyPuck | `ingest/moneypuck.py` | xG of every unblocked shot (one file per season); season files for the spot-check | live |
| Daily Faceoff | `ingest/dailyfaceoff.py` | starting goalies with Confirmed / Likely / Unconfirmed, lines, PP and PK units, injured reserve | live |
| Scouting the Refs | `ingest/refs.py` | tonight's referee crews; penalty-rate history comes from the officials on each NHL game | live |
| The Odds API (`icehockey_nhl`) | `ingest/odds.py` | ML, puck line, totals, player props and alternates | written to the published format, not yet run with a key |
| bet365 sheet | `ingest/odds.py` | milestone ladders from `data/manual/bet365/` | live (hand-entered) |
| Natural Stat Trick | `ingest/nst.py` | hand exports from `data/manual/nst/` only | the site refuses automated requests |

Four things a later phase should know:

- **Natural Stat Trick cannot be pulled.** Its Cloudflare answers 403 to any automated client. The on-ice rates, home/away
  and score-state splits the spec takes from it are built here from the NHL's own play-by-play and shift charts with
  MoneyPuck's xG. Line-mate tables are not built yet. Decision (owner, 24 November 2026): the engine runs on these
  NHL-derived tables; hand exports are optional and only feed the spot-check.
- **The NHL API has no injury feed.** Injured reserve comes from Daily Faceoff's line pages, scratches from each game's
  NHL record.
- **The league's shift-chart feed is empty for some games** (141 of 4,320 on 24 November 2026, 84 of them this season).
  Those games are built from the play-by-play situation codes and the league's own ice time instead: team strength time
  lands within about 1.5% of the shift-chart method, skater ice time is the league's exactly, and on-ice numbers are left
  empty and kept out of on-ice rates. This season's are asked for again once a day in case the chart is posted late.
- **The Odds API lists no player-hits market for the NHL**, so hits ladders can only come from the bet365 sheet.

## Tables (`store.py`)

Per finished game, each row stamped `known_at` (puck drop plus four hours), read through `store.before(con, table, as_of)`:

- `games`, `team_game` - score by period, how it was decided, starters, empty-net time and goals, hits, blocks, shots, penalties.
- `team_game_strength` - ice time, goals, xG, attempts, shots, high-danger shots, hits, blocks, penalties, by strength state.
- `team_game_score` - the same by score state (down 2+, down 1, tied, up 1, up 2+), at 5v5 and overall. Feeds score effects.
- `player_game_strength` - each skater's ice time, shots, attempts, ixG, goals, assists, hits, blocks, penalties and on-ice xG by strength.
- `goalie_game` - starter, relieved, shots, saves, xG against. GSAx is xG against minus goals against.
- `officials`, `scratches`, `toi_official`, `shots`.

Strength states, from the shift chart second by second: `ev5` (5v5, both goalies in), `pp`, `pk`, `evo` (4v4, 3v3, empty
net). `ev5 + evo` is the league's "even strength". A game with a missing or broken shift chart falls back to the
play-by-play situation code and the league's own ice time (`games.toi_source = 'pbp'`); its on-ice numbers are left empty.

Game day: `goalie_starts`, `lines`, `ref_assignments`, `odds`. Hand exports: `nst`.

Derived, rebuilt by `derive` from rows known before `as_of` (`features/`):

- `team_rates` - per-60 by strength, 60% season / 40% last 10, with league index; penalties drawn and taken per 60.
- `player_rates` - per-60 by EV / PP / PK, shrunk to the position's league rate, with sample sizes; `goalie_rates` - GSAx/60, shrunk, 15-start minimum.
- `toi_projection` - EV / PP / PK seconds per game: last 10 shrunk toward season, then tonight's line slot and PP unit.
- `schedule_spots` - rest, back-to-back, three-in-four, travel km, time-zone shift, rest differential.
- `arena_bias` - hits, blocks and shots factor per rink, three seasons, shrunk toward 1.00, capped at 25%.
- `ref_rates` - penalties per game by referee, shrunk; `ingest/refs.crew_factor` turns a crew into the power-play multiplier.

Every threshold is in `config.yaml`.
