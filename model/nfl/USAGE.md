# ATTD Engine: NFL Anytime Touchdown Model + Correlated Parlay Builder

Built on free nflverse data (play-by-play, snap counts, weekly rosters, injury reports, Vegas lines), 2021 onward.

## Quick start
```bash
pip install -r requirements.txt
python run.py download --season 2026          # refreshes current season + schedules each run
python run.py backtest                        # out-of-sample eval, fits leg-correlation model
python run.py project --season 2026 --week 10 --odds my_odds.csv --sgp-haircut 0.2
python run.py project --season 2026 --week 10 --out "Player A,Player B"   # force late scratches
```
`my_odds.csv` should have two columns, `player,odds` (American). Outputs go to `outputs/`.

## Weekly workflow (props + ATD pack)
```bash
python run.py download --season 2026                 # refresh data (rosters, injuries, stats, lines)
python run.py card --season 2026 --week 10           # full pack -> outputs/card_2026_wk10.md (+ .json)
python run.py card --season 2026 --week 10 --out "Player A"   # late scratch at inactives
python run.py grade-card --season 2026 --week 10     # after the games: graded as shipped
```
`data/personnel.csv` (name, team, status, note, as_of) is where late trades, scratches and your own reads go.
Every build applies it and logs it.

**Props model** (`attd/props.py`): one boosted model per market (carries, rush yds, receptions, rec yds, pass att, pass yds).
It is trained on official box-score lines with a stacked-threshold design (P(X ≥ k) for every rung, monotone in k, no normal
assumption), then calibrated with an out-of-fold Platt layer per market. It uses player volume, efficiency and spread (EWMA,
season-to-date, rolling SD), team volume, opponent yards/catches allowed to the position, game environment, and OC/DC tendencies.

**Tickets** (`attd/tickets.py`) follow the ledger's standing rules: bet365 ladders, props SGPs with no TD legs, floor (70–88%,
target 78%) and aggressive (55–68%, target 62%) 4/6/8-leg tiers, a per-game ATD ticket, all-position slips, cross-game combos
4/6/8/10/12 (≤2 legs per game, ≤1 per team), and a full-slate ATD slip. Questionable / return-from-absence = singles only.
Role gate, distinct players, market cap 2, one RB volume leg per team, 2026 rung sanity gate. Joint prices come from measured
leg correlations (`models/leg_correlations.json`), e.g. QB pass yds ↔ his WR's rec yds +0.23, RB1 ↔ RB2 carries −0.12.

## Architecture
1. **Play-level xTD models** (`attd/xtd.py`). Two LightGBM models estimate P(TD) for every carry
   (yardline, down, distance, QB or not) and every target (adds air yards and whether it was an end-zone target).
   Summed per player-game, this gives *expected* TDs, which stabilize far faster than real TDs.
2. **Leakage-safe features** (`attd/features.py`). Everything is shifted, then EWMA'd (half-lives 3 and 10 games).
   Features include shares of carries, red-zone, inside-10 and inside-5 carries, targets, red-zone and end-zone
   targets, and rush/receiving xTD; snap %; a shrunk finishing ratio; age; draft slot; and experience.
3. **Active-roster renormalization.** Shares are renormalized across the players who are actually active.
   Snaps a missing starter leaves behind (injury, inactive, trade) go to the teammates who suit up.
4. **Team layer** (`attd/model.py`). Poisson GLMs predict team **rushing** and **passing** TDs from the
   Vegas-implied team total, the spread, rolling offensive xTD, and the opponent's rolling xTD allowed.
5. **Structural player rate.** λ = λ_team_rush·rush_share + λ_team_pass·rec_share, times the finishing factor,
   and P = 1 − e^(−λ).
6. **Gradient-boosted top layer.** LightGBM over about 60 features, including the structural λ.
7. **Correlation model** (`attd/correlation.py`). A Gaussian copula whose ρ values are fit by maximum
   likelihood on out-of-sample pairs, one ρ per relationship type (teammates by position pair, or opponents).
8. **Parlay builder** (`attd/parlay.py`). Takes +EV legs, prices joint probability exactly across games and
   with the copula within a game, then ranks combos by quarter-Kelly expected log growth.

## Game-environment & matchup factors (`attd/context.py`, `attd/scheme.py`)
No media, expert picks or pick sites are used. The only inputs are nflverse data, the NWS forecast, and the Vegas spread and total.

| group (`--factors` name) | what it measures | in default model |
|---|---|---|
| `stadium_weather` | indoor/outdoor, grass/turf, weather category (clear/cloudy/rain/snow/fog), temp, wind; NWS forecast at kickoff for upcoming games; indoor = neutral | yes |
| `game_time` | early / late / night, Thu/Mon/Sat, international, divisional | yes |
| `travel_rest` | miles traveled, time-zone shift, kickoff hour on the team's home clock, rest days, short week, off bye | yes |
| `def_injuries` | opponent defenders ruled Out/Doubtful, weighted by recent snap share (DL / LB / DB) | yes |
| `def_scheme_dc` | blitz rate, pass rushers, box counts, PROE faced, deep/YAC/aDOT allowed, TDs allowed by position, red-zone TD% allowed | yes |
| `player_splits` | player home/away x roof / surface / slot / weather, shrunk toward his overall rate | no (leaned negative) |
| `off_playcalling_oc` | PROE (all, red zone, inside the 10), WR/TE/RB target split (all and red zone), deep/short/middle/screen, play-action, RPO, motion, shotgun, pace, QB designed runs | no (leaned negative) |
| `player_route_profile` | player deep/short target share, air yards, YAC | no (leaned negative) |
| `own_ol_injuries` | own offensive linemen out, snap-weighted | no |

Walk-forward test (train on prior seasons, test 2023/24/25/26, n = 23.7k): **no group cleared noise individually**.
All 95% CIs include zero (`outputs/factor_walkforward.csv`). The market total already prices most of this.
Run e.g. `--factors all` or `--factors none` to compare, or `--factors stadium_weather,game_time` for any mix.

Coordinators: there's no free data feed, so tendencies are measured per team with in-season updates. If you add
`data/coordinators.csv` (season,team,oc,dc), the tendencies follow the coordinator instead.

## Backtest (trained 2021–24, tested out-of-sample on 2025 + 2026 Weeks 1–8, n≈9,900 player-games)
| model | log loss | AUC |
|---|---|---|
| position average | 0.4444 | – |
| player rolling TD rate | 0.4405 | – |
| structural (team × share) | 0.3986 | – |
| **final** | **0.3871** | **0.764** |

Full report: `outputs/backtest_report.md`.

## Known limitations / honest caveats
- **Top-end overconfidence.** In the test period, legs priced above 60% hit 61% against 65% predicted.
  Cross-fitted isotonic calibration made out-of-sample results *worse*, so it is not applied. Treat
  favorites at −200 and shorter with extra skepticism.
- Injury handling uses the official report: Out and Doubtful are removed, Questionable players are kept and flagged.
  Re-run after inactives are announced (90 minutes before kickoff) and pass `--out` for late scratches.
- Only offensive TDs are labeled. Return and defensive TDs, which some books count, are ignored.
- The training population is players with at least one offensive snap (or a touch), so probabilities are *conditional on playing*.
- Same-game parlays: books price SGPs with their own correlation adjustments. Use `--sgp-haircut`
  or compare `p_joint` against the actual SGP quote.
- The market is the toughest benchmark. Paste real odds and only bet edges that survive the vig.
