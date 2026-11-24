# godseye NHL engine

A standalone engine: its own data, tables, config and (in later phases) models and tickets. It imports nothing from the NFL
or NBA code; only `model/common/` is shared. The spec is `SPEC.md`. The spec's `godseye/nhl/` is `model/nhl/` in this
repository and its `godseye/shared/` is `model/common/`.

**Built so far: Phase 1, data ingest and derived tables.** Gates, the game sim, props, correlation, tickets, backtest and
grading are Phases 2 to 5 and are not here yet. Nothing in this module produces a pick.

Run everything from `model/`.

    pip install pandas numpy pyyaml pytest
    python3 -m nhl.run_daily nightly       # schedule, finished games, MoneyPuck xG, rosters, every derived table
    python3 -m nhl.run_daily gameday       # goalies, lines and PP units, referees, odds and ladders
    python3 -m nhl.run_daily watch         # from 90 minutes before puck drop, gameday every 30 minutes until goalies are confirmed
    python3 -m nhl.run_daily derive [UTC]  # rebuild the derived tables as of a time
    python3 -m nhl.run_daily status
    python3 -m nhl.spotcheck               # the Phase 1 check: 3 teams' xG and 5 players' TOI against the sources
    python3 -m pytest nhl/tests

The first `nightly` pulls three seasons plus the current one (about 13,000 requests, 25 minutes) into `data/raw/`; after that a
night is a few dozen requests. `data/nhl.sqlite` and `data/raw/` are not committed.

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
  MoneyPuck's xG. Line-mate tables are not built yet.
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
