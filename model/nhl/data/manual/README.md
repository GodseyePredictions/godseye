# Hand-entered files

Nothing in here is committed except this note.

- `bet365/YYYY-MM-DD*.csv` - the day's bet365 milestone ladders. Columns: `game` (AWAY@HOME), `player`, `market`,
  `rung or line` (`3+` or `o24.5`), `price`; optional `side`. Read by `python3 -m nhl.run_daily gameday`. Rows that do not
  validate are rejected and listed, never repaired.
- `nst/<kind>_<situation>.csv` - tables exported by hand from Natural Stat Trick (for example `team_5v5.csv`). The site
  refuses automated requests, so this is the only way its numbers reach the engine. Read by the nightly run and shown
  in `python3 -m nhl.spotcheck`.
