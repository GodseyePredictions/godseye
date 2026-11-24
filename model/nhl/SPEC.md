# Godseye NHL Engine Spec

Nov 24, 2026 · Gurtaj Sandher

## Overview

The NHL engine is a standalone module inside Godseye Predictions. It follows the same flow as the NFL and NBA algorithms (ingest, gate, simulate the game, project props, correlate, build tickets, grade), but it owns its own data pipeline, models, config and outputs. Nothing in it imports NFL or NBA model code. Only shared platform services are reused: odds client, ticket formatter, bankroll calculator, results tracker and the chat advisor.

**Markets covered**

| Group | Markets |
| --- | --- |
| Game lines | Moneyline, Puck line (spread ±1.5 and alt lines), Match totals and alt totals |
| Skater props | Shots on goal, Points, Assists, Goals (anytime scorer), Hits, Blocked shots |
| Goalie props | Saves |

**Core thesis:** simulate the whole game script first, then set props from that script. In hockey, most of the edge sits in high-volume props (shots, saves, blocks, hits), not in goals or sides, so the engine weights its output toward those markets.

## Pipeline flow

```
1. Ingest -> 2. Gates -> 3. Game sim -> 4. Player props
                                              |
8. Grade <- 7. Godseye site <- 6. Tickets <- 5. Correlation
   |
   +--> recalibrate weights --> back to 1. Ingest

Shared Godseye services (used by 6, 7, 8): odds client, bankroll, results tracker, chat advisor
```

| Stage | What it does |
| --- | --- |
| 1. Ingest | NHL API, MoneyPuck, NST, odds, lineups |
| 2. Gates | Goalies, lines, PP units, injuries, ladders |
| 3. Game sim | 20k sims: ML, puck line, totals |
| 4. Player props | Shots, points, hits, blocks, saves |
| 5. Correlation | SGP odds from the same sims |
| 6. Tickets | Milestone rungs, 70%+ floor legs |
| 7. Godseye site | Picks, chat advisor, bankroll sizing |
| 8. Grade | Nightly results, weekly report card |

The daily runner mirrors the NFL and NBA order, but every stage from ingest to grading is NHL-only code; only the shared services are reused. Grading feeds back into the model weights each week.

## Metrics that matter most

The confirmed starting goalie is the single biggest input, the way the QB is in the NFL engine. Ranked by impact on the model:

| Rank | Metric | Why it matters | Drives |
| --- | --- | --- | --- |
| 1 | Confirmed starting goalie + GSAx/60 (goals saved above expected) | A backup in net can move a total by half a goal and a moneyline by 20+ cents | ML, puck line, totals, saves, every scoring prop |
| 2 | 5v5 expected goals: xGF/60, xGA/60, xGF% | Shows who controls play, independent of puck luck | All game lines, team implied goals |
| 3 | Special teams: PP xGF/60, PK xGA/60, penalties drawn/taken per 60, referee crew call rate | Power plays drive totals, points and shot volume | Totals, points, assists, shots |
| 4 | Deployment: TOI split by EV / PP / PK, line slot, PP1 vs PP2 | The biggest single factor in any player prop | All skater props |
| 5 | Schedule spot: back-to-back, rest differential, travel, time zones | Second night of a B2B usually means the backup goalie and tired legs | Totals, ML, goalie gate |
| 6 | Shot volume: shot attempts/60 (Corsi) for and against, attempts-to-SOG rate | Feeds shots, saves and blocks directly | Shots, saves, blocks |
| 7 | Game script / score effects | Trailing teams shoot more; leading teams block and hit more | Shots, blocks, hits, saves |
| 8 | Arena scorer bias (hits, blocks, SOG) | Home scorekeepers log these, and some rinks inflate them heavily | Hits, blocks, shots |

**Supporting metrics:** high-danger chances for/against, individual xG/60 (ixG), individual shot attempts/60 (iCF), primary and secondary assist rates, on-ice xGF/60, hits/60, blocks/60, faceoff % (minor), empty-net frequency, goalie pull timing, recent form (last 10 games, shrunk toward season).

## Data stack and ingestion

All NHL data lands in the engine's own store (`nhl/data/`), refreshed daily and again 90 minutes before puck drop for lineups and goalies.

| Source | What it provides | Refresh |
| --- | --- | --- |
| NHL API (api-web.nhle.com) | Schedule, play-by-play, box scores, TOI by strength, rosters, injuries | Nightly + game day |
| MoneyPuck | xG, GSAx, high-danger chances, player and team, by strength state | Nightly |
| Natural Stat Trick | On-ice rates, linemate data, splits (home/away, score state) | Nightly |
| Daily Faceoff | Confirmed starting goalies, line combos, PP units | Game day, every 30 min until confirmed |
| the-odds-api (`icehockey_nhl`) | ML, puck line, totals, player prop lines | Game day |
| bet365 manual CSV | Milestone ladders (shots 2+/3+/4+, points 1+/2+, saves ladders) | Game day |
| Referee assignments (Scouting the Refs or NHL) | Crew for the game, crew penalty rate history | Game day |

**Derived tables the engine builds itself:** team rates by strength state, player per-60 rates by strength, rolling TOI projections, arena bias factors (each rink's home-scorer hits/blocks/SOG vs the same teams' road numbers), and a schedule table with rest days and travel distance.

**History for backtesting:** at least three full seasons of play-by-play, so the arena bias and shrinkage weights have enough sample.

## Game simulation engine

Every game is simulated 20,000 times before any prop is touched. The sim outputs the full score distribution, which prices moneyline, puck line and totals and feeds the game script into Layer 2.

**Step 1: Expected goals per team, by strength state**

```
EV_xG  = shrunk 5v5 xGF/60 (season 60% / last 10 games 40%)
         × opponent 5v5 xGA/60 index × projected 5v5 minutes / 60
PP_xG  = PP xGF/60 × projected PP minutes / 60
         (PP minutes = own penalties drawn/60 × opp penalties taken/60 × ref crew factor)
PK_xGA = mirror of PP for the opponent
Team λ = EV_xG + PP_xG + shorthanded xG
```

**Step 2: Adjustments**

- Opposing goalie: λ × (1 − GSAx/60 ÷ league xGA/60), GSAx shrunk toward league average with a minimum sample of 15 starts
- Home ice: small fixed boost, fitted from backtest
- Rest and travel: B2B second night, 3-in-4, time-zone crossings, rest differential
- Injuries: remove the player's share of team xG and redistribute TOI to the next man up

**Step 3: Simulate**

- Negative binomial goal draws per period, with correlation between the two teams' scoring
- Score effects: trailing team's shot rate rises and leading team's falls as the game state changes
- Empty net model: trailing team pulls the goalie with about 2 to 3 minutes left when down 1 or 2; empty-net goals for and against are simulated
- Overtime (3v3) and shootout resolution

**Step 4: Price the markets**

| Market | How it is priced |
| --- | --- |
| Moneyline | Win % from the sim, including OT and shootout (check the bet365 market; 60-minute 3-way priced separately from regulation results) |
| Puck line ±1.5 and alts | Margin distribution from the sim; empty-net goals must be included or favourites at −1.5 are undervalued |
| Totals and alts | Total goals distribution; flag when both starting goalies are unconfirmed |

**Edge = model probability − implied probability (vig removed).** Only edges above the tier thresholds go to tickets.

## Player prop models

Every prop uses one formula: **projected TOI by strength × per-60 rate × opponent adjustment × game-script adjustment × arena factor**. Props are drawn inside the same 20,000 game sims, so a player's shots, the opposing goalie's saves and the game total all come from the same simulated game.

**TOI projection (feeds every skater prop)**

- Base: last 10 games TOI by EV / PP / PK, shrunk toward season
- Line slot and PP unit from game-day Daily Faceoff lines (PP1 gets about 60 to 65% of PP time)
- Script: blowout risk from the sim trims top-line TOI late; trailing teams lean on top lines
- Teammate in/out: redistribute minutes when a regular is scratched or injured

| Prop | Core inputs | Opponent and context adjustments | Distribution |
| --- | --- | --- | --- |
| Shots on goal | iCF/60 × attempts-to-SOG %, by strength | Opponent SOG allowed/60 vs forwards or D, PP1 status, trailing-script boost, arena SOG bias | Poisson (negative binomial for high-volume shooters) |
| Goals (anytime) | ixG/60 × TOI, finishing talent heavily shrunk | Opposing goalie GSAx, PP1 net-front role, team implied goals | Bernoulli per sim from team goal events |
| Assists | On-ice xGF/60 × player's assist share (primary + secondary) | Linemates in/out, PP quarterback role for D-men | Drawn from simulated team goals |
| Points | Joint draw of goals + assists in the same sim | Team implied goals, PP1 | Never goals + assists added separately |
| Hits | Hits/60 × TOI | Team possession deficit (fewer shot attempts = more hits), opponent physicality, **arena scorer bias** | Negative binomial |
| Blocked shots | Blocks/60 × TOI, PK minutes | Opponent shot attempts/60, leading-script boost, arena bias | Negative binomial |
| Goalie saves | Opponent projected SOG × (1 − projected goals per SOG) | Starter confirmed, **pull risk in blowouts**, OT/SO counting rule per book | From the sim's opposing SOG and goals |

**Arena bias factor:** for each rink, compare hits, blocks and SOG recorded there against the same teams' road games over three seasons. Shrink toward 1.00 and cap at ±25%. Apply to both teams in that building.

## Correlation engine and SGP builder

SGP probability is the share of the 20,000 sims where every leg hits together, not the product of single-leg probabilities. Props from both teams are considered, and the best legs win regardless of side.

| Leg pair | Correlation | How the builder uses it |
| --- | --- | --- |
| Team A shots ↔ Team B goalie saves | Strong positive | Stack together when the sim favours volume |
| Game total over ↔ player points / assists | Positive | Pair with top-line PP1 points |
| Team trailing ↔ its shots up, opponent blocks and hits up | Positive | Script-driven stacks |
| Heavy favourite ↔ opposing goalie saves up | Positive, but pull risk | Cap saves legs when blowout probability is high |
| Same-line forwards' points | Positive | Allowed, but max two from one line |
| Goalie saves over ↔ his team's ML | Mildly negative | Avoid stacking both |

**Builder output per game:** a 4-leg props SGP, a 6-leg props SGP, an anytime goal scorer ticket (separate), and a game-line closer (ML, puck line or total) when the sim supports it.

## Ticket rules and gates

The NFL and NBA ticket rules carry over unchanged. Picks come only from the engine's own output, never from media or expert picks.

**Gates (any fail = the leg is removed)**

1. Starting goalie confirmed for both teams (no confirmed starter, no leg on that game's totals, saves or scoring props)
2. Game-day line combos and PP units confirmed
3. Injury and scratch check passed for the player and key linemates
4. Line exists on the book's ladder (no invented rungs)

**Ticket construction**

- Props are built in bet365 milestone format (shots 2+/3+/4+, points 1+/2+, saves ladders)
- SGP legs use floor rungs at 70%+ model probability; edge rungs are for straight singles only
- Max one leg below 65% per ticket
- Anytime goal scorer picks go on their own ticket, never inside the props SGPs
- Close with ML, puck line, total or alt total only when the sim supports it
- Blowout guard: when the sim's blowout probability is high, cut late-TOI props on the favourite and saves overs on the losing goalie
- Stake sizing through the shared bankroll calculator (quarter-Kelly default, tiered by edge)

## Backtesting, grading and build

**Backtesting:** walk-forward over the last three seasons using only data available before each game. Report hit rate, ROI, calibration (predicted vs actual by 5% bucket) and closing line value per market. A market goes live only after it beats the closing line in backtest.

**Grading:** nightly results grading and a weekly report card per market, same as NFL. Every graded pick feeds each subscriber's personal win tracker.

**File structure**

```
godseye/
  shared/            # odds client, ticket formatter, bankroll, results tracker, chat advisor
  nfl/               # existing
  nba/               # existing
  nhl/
    SPEC.md          # this file
    config.yaml      # thresholds, sim count, shrinkage weights, gates
    data/            # raw + derived tables
    ingest/          # nhl_api.py, moneypuck.py, nst.py, dailyfaceoff.py, odds.py, refs.py
    features/        # team_rates.py, player_rates.py, toi.py, schedule.py, arena_bias.py
    gates.py         # goalie, lines, injuries, ladder checks
    sim/             # game_sim.py (score effects, empty net, OT/SO)
    props/           # shots.py, goals.py, assists.py, points.py, hits.py, blocks.py, saves.py
    correlation.py   # SGP joint probability from sims
    tickets.py       # milestone ladders, ticket rules
    backtest.py
    grade.py
    run_daily.py     # the daily runner
```

**Claude Code build prompt (paste as is)**

```
Build a standalone NHL engine for Godseye Predictions in godseye/nhl/.
It must follow the same flow as the NFL and NBA engines (ingest, gate,
simulate game, project props, correlate, build tickets, grade) but run
as its own engine: no imports from nfl/ or nba/ model code. Reuse only
godseye/shared/ (odds client, ticket formatter, bankroll calculator,
results tracker, chat advisor).

Follow the Godseye NHL Engine Spec exactly:
1. Ingest NHL API, MoneyPuck, Natural Stat Trick, Daily Faceoff goalies
   and lines, the-odds-api icehockey_nhl, bet365 CSV ladders, ref crews.
2. Build team and player per-60 rates by strength state (EV/PP/PK),
   TOI projections, schedule/rest table, and arena bias factors.
3. Gates: confirmed goalies, confirmed lines and PP units, injuries,
   ladder exists. Any fail removes the leg.
4. Game sim: 20,000 sims per game, negative binomial goals by period,
   score effects, empty-net model, OT and shootout. Price ML, puck line
   +/-1.5 and alts, totals and alts.
5. Props drawn inside the same sims: shots, goals, assists, points
   (joint), hits, blocks, goalie saves (with pull risk).
6. Correlation engine: SGP probability = share of sims where all legs hit.
7. Tickets: bet365 milestone format, 70%+ floor rungs for SGP legs,
   edge rungs singles only, max one sub-65% leg, anytime goal scorer on
   its own ticket, blowout guard, quarter-Kelly via shared bankroll.
8. Walk-forward backtest over 3 seasons, nightly grading, weekly report.
9. run_daily.py runs the full pipeline and refreshes 90 minutes before
   puck drop.
All thresholds live in nhl/config.yaml. Write tests for each module.
```

## Deploying with Claude Code

Save this spec into the repo as `godseye/nhl/SPEC.md` and build in phases, checking each one before the next.

**Setup**

1. Download this doc as Markdown and save it as `godseye/nhl/SPEC.md`.
2. Add this line to the project's `CLAUDE.md` so every session follows it:

```
NHL engine spec lives in godseye/nhl/SPEC.md. Always read and follow it for any NHL work. The NHL engine is standalone: never import from nfl/ or nba/ model code; reuse only godseye/shared/.
```

3. Start each session with: *"Read godseye/nhl/SPEC.md. Build Phase N only, exactly to spec. Don't touch nfl/ or nba/."*

**Build phases**

| Phase | Build | Check before moving on |
| --- | --- | --- |
| 1 | Data ingest and derived tables (rates, TOI, schedule, arena bias) | Spot-check 3 teams' xG and 5 players' TOI against MoneyPuck and NST |
| 2 | Gates and game sim (ML, puck line, totals) | Run last night's games; compare model odds to closing lines |
| 3 | Player props | Compare projections to last night's actual box scores |
| 4 | Correlation engine and tickets | Confirm slips use real bet365 rungs and follow every ticket rule |
| 5 | Backtest and grading | Review calibration and CLV per market before any market goes live |
