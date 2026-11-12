# NBA module backtest

Walk-forward over the last two full seasons, 2024-25 and 2025-26: 2,462 games, 49,074 player-games, 2.1 million graded legs. Last run on 12 November 2026, after the adjustments in `docs/nba_report_2026-11-11.md`, with 2,000 simulations per game (live slates use 10,000). Reproduce with `python3 -m nba.backtest 2000` then `python3 -m nba.validate` from `model/`.

## Read this first

0. **Known live issue, partly fixed 12 November 2026 (see `docs/nba_report_2026-11-11.md`).** On teams with deep or reshuffled rosters early in the season, projected minutes for the top starters read 3 to 5 minutes low (for example a 35-minute guard projected at 30). The cause is bench players whose baseline still leans on last season's role. The backtest average for high-minute players is under 1 minute low, so this is concentrated in a few teams. It makes star legs conservative rather than aggressive. Not yet fixed.

1. **This backtest cannot tell you whether the system makes money.** There are no historical book prices in the project: no Odds API key was available, and ESPN drops old lines. So there is no ROI, no closing line value and no comparison with the closing line anywhere below. Everything here is calibration and hit rate.
2. **Legs are a fixed grid of thresholds, not bet365 rungs.** For example 10, 15, 20, 25, 30, 35 points for every player. Real ladders differ.
3. **Tickets in the backtest are chosen for highest joint probability**, because without prices there is no expected value to rank by. Live tickets are chosen by expected value.
4. **The noise settings of the simulation were tuned on sampled games from both test seasons.** Model coefficients are strictly walk-forward (fitted on earlier seasons only), but these few spread settings are not, so calibration figures are a little flattering. The 2026-27 season to date was not used for tuning and will be the first clean check.
5. **Which players were listed for a game comes from that game's box score** (who dressed or was listed inactive). Their status, minutes and everything else come from before tip-off.

## Where each model stands

| Part | Result | Verdict |
|---|---|---|
| Leg probabilities | Legs called 70-80% hit 77.1% (79,294 legs). Legs called 80-90% hit 86.3%. Every market within 3 points at the 70%+ end | Good, slightly cautious |
| Game legs | Moneyline, spread and total probabilities within 1 point of actual in every bucket | Good |
| Game simulation spread | Actual margin fell inside the simulated 10-90% band 79.4% of the time, totals 79.6% (target 80%) | Good |
| Blowouts | Predicted 45.7% of games, actual 47.0%. Overtime predicted 4.6%, actual 4.6% | Good |
| Team projection | Margin error 11.14 points. Ratings alone: 11.18. Rest, style, referees and absences add almost nothing | Weak edge over a plain rating |
| Minutes | Error 5.00 minutes against 5.07 for a simple recent-average. Better when a rotation player is out, worse in ordinary games | Slightly better than the baseline overall |
| Minutes percentiles | 10th percentile beaten 89.0% (target 90%), 90th exceeded 9.6% (target 10%) | Good |
| Ticket joint probability | 4-leg: modelled 63.0%, hit 64.8%. 6-leg: modelled 46.4%, hit 51.0%. 8-leg: modelled 32.6%, hit 38.3%. Multiplying legs would have said 61.6%, 44.5% and 30.8% | Too low by 2 to 6 points |
| Teammate correlations | Two top scorers' points: simulated -0.13, historical +0.02. Guard assists with centre points: simulated +0.02, historical +0.15 | Understated |
| Double-doubles | Under-forecast by 4 to 7 points between 20% and 60% | Weak |
| Triple-doubles | Forecast 0.46%, actual 0.88% | Poor: do not bet |

## Validation asked for in each step

### Step 3: minutes (last season, 2025-26)

| Games | Player-games | Error, model | Error, baseline | Beat 10th pct | Beat 50th | Beat 90th |
|---|---|---|---|---|---|---|
| All | 24,930 | 4.99 | 5.05 | 88.8% | 50.7% | 9.4% |
| Normal (no rotation player out, no blowout) | 9,769 | 4.98 | 4.89 | 90.8% | 58.6% | 12.2% |
| A rotation player out | 5,664 | 5.44 | 5.61 | 86.9% | 44.5% | 7.4% |
| Blowouts | 12,349 | 4.96 | 5.08 | 87.3% | 45.3% | 7.8% |

The percentiles are for the whole pre-game distribution, which already mixes blowout and close scripts. That is why they sit high in normal games and low in blowouts: the model cannot know before tip-off which kind of game it will be.

### Step 4: game script

- Win probability is calibrated within 2.3 points in every bucket with 200 or more games.
- Margin error 11.0 (2024-25) and 11.3 (2025-26). Total error 14.6 and 14.9, against 15.8 for always guessing the season average.
- Games given a 60% or higher blowout chance were blowouts 65.9% of the time (179 games, too small to trust).
- **Did the blended number beat the closing line? Unknown.** No historical lines exist here to test it. The blend weight in config (85% market early in the season, 65% later) is a prior, not a fitted value.

### Step 5: factor review

Change in out-of-sample fit when a factor group is removed (positive means it helps):

| Factor group | Mean gain | Helps in both seasons | Decision |
|---|---|---|---|
| Last-5 form | +1.51% | Yes | Keep. The only factor with real weight |
| Opponent versus position | +0.17% | Yes | Keep |
| Opponent shot profile | +0.07% | Yes | Keep, marginal |
| Teammate in/out (rates) | +0.06% | Yes | Keep. Most of its effect is on minutes |
| Rim protection | +0.04% | Yes | Keep, marginal |
| Referee crew | +0.03% | Yes | Keep, marginal |
| Situation: home/away, back-to-back, season phase | +0.01% | Mixed by stat | **Switched off in config. For your review** |

Left out entirely because no reachable source has the data: pick-and-roll coverage, zone frequency, play types, individual defender matchup, shot contests, off-ball movement and screens, double teams, touches, drives, potential assists, rebound chances, deflections.

**Shooting gate:** scoring legs at 70%+ that pass the gate hit 86.9%; those that fail hit 85.8%, from almost the same forecast (85.5% and 84.3%). The gate does not separate good legs from bad ones in this data. It is still enforced because it is a standing rule. For your review.

**Blowout rule:** in flagged games, legs that clear 70% inside blowout simulations hit 86.0%; legs that do not hit 73.0% (1,176 legs). This rule earns its place.

### Step 6: simulation

- Calibration by market and bucket: tables below.
- Speed: a 10-game slate at 10,000 simulations per game takes 118 seconds on 4 cores, of which about 50 seconds is building features and fitting. The backtest takes 2.2 seconds per game per core at 2,000 simulations, most of it building and ranking tickets.

### Step 8: by situation (legs at 70%+)

| Situation | Legs | Forecast | Actual |
|---|---|---|---|
| Blowout-flagged games | 28,369 | 84.6% | 85.4% |
| Other games | 199,587 | 84.8% | 86.2% |
| First 20 games | 56,376 | 84.8% | 86.8% |
| Games 21-55 | 96,958 | 84.9% | 86.3% |
| Games 56-72 | 46,184 | 84.7% | 86.4% |
| Final weeks (73+) | 28,438 | 84.7% | 83.2% |
| Team has a rotation player out | 65,096 | 84.8% | 83.1% |

The two weak spots are the final weeks (resting and tanking) and games with a rotation player out. Both are over-forecast by about 1.6 points while everything else is under-forecast.

## Not delivered, and why

| Asked for | Status |
|---|---|
| ROI by market, ticket type, season phase | Not possible without historical prices |
| Closing line value on singles | Not possible without historical prices. The code path exists and is tested |
| Blended number versus closing line | Not possible: no historical lines |
| Ablation for scheme, matchup and off-ball groups | No data for these groups. Opponent shot profile and opponent versus position are the stand-ins |
| Coach-specific blowout habits | Sources carry no coach name. The team stands in for its coach |

---

# Full tables

## Minutes and role model

| season | games | player-games | MAE model | MAE baseline | beat 10th pct | beat 50th pct | beat 90th pct |
|---|---|---|---|---|---|---|---|
| 2025 | all games | 24144 | 5.003 | 5.079 | 0.891 | 0.514 | 0.098 |
| 2025 | normal (no rotation player out, no blowout) | 9161 | 4.907 | 4.800 | 0.912 | 0.591 | 0.119 |
| 2025 | a rotation player out | 6684 | 5.460 | 5.732 | 0.876 | 0.469 | 0.094 |
| 2025 | blowouts | 11521 | 5.006 | 5.139 | 0.874 | 0.458 | 0.081 |
| 2026 | all games | 24930 | 4.987 | 5.051 | 0.888 | 0.507 | 0.094 |
| 2026 | normal (no rotation player out, no blowout) | 9769 | 4.982 | 4.886 | 0.908 | 0.586 | 0.122 |
| 2026 | a rotation player out | 5664 | 5.437 | 5.605 | 0.869 | 0.445 | 0.074 |
| 2026 | blowouts | 12349 | 4.957 | 5.077 | 0.873 | 0.453 | 0.078 |
| both | all games | 49074 | 4.995 | 5.065 | 0.890 | 0.511 | 0.096 |
| both | normal (no rotation player out, no blowout) | 18930 | 4.946 | 4.844 | 0.910 | 0.589 | 0.121 |
| both | a rotation player out | 12348 | 5.449 | 5.674 | 0.873 | 0.458 | 0.085 |
| both | blowouts | 23870 | 4.981 | 5.107 | 0.874 | 0.455 | 0.080 |

## Game script engine

| season | games | margin MAE (ours) | margin MAE (ratings only) | margin MAE (always 0) | total MAE (ours) | total MAE (season average) | winner picked | margin inside 10-90% band | total inside 10-90% band |
|---|---|---|---|---|---|---|---|---|---|
| 2025 | 1231 | 11.014 | 11.009 | 12.751 | 14.574 | 15.817 | 0.665 | 0.797 | 0.805 |
| 2026 | 1231 | 11.287 | 11.352 | 13.272 | 14.921 | 15.831 | 0.685 | 0.790 | 0.786 |
| both | 2462 | 11.150 | 11.181 | 13.011 | 14.747 | 15.868 | 0.675 | 0.793 | 0.795 |

**Home win probability calibration**

| bucket | games | forecast | actual | gap | note |
|---|---|---|---|---|---|
| 0-10% | 14 | 0.077 | 0.000 | -0.077 | (too small to trust) |
| 10-20% | 97 | 0.160 | 0.134 | -0.026 | (too small to trust) |
| 20-30% | 192 | 0.253 | 0.240 | -0.013 | (too small to trust) |
| 30-40% | 312 | 0.353 | 0.353 | -0.001 |  |
| 40-50% | 378 | 0.449 | 0.450 | 0.001 |  |
| 50-60% | 432 | 0.549 | 0.574 | 0.026 |  |
| 60-70% | 410 | 0.648 | 0.624 | -0.024 |  |
| 70-80% | 340 | 0.748 | 0.774 | 0.025 |  |
| 80-90% | 225 | 0.845 | 0.840 | -0.005 |  |
| 90-100% | 62 | 0.924 | 0.919 | -0.005 | (too small to trust) |

**Blowout probability calibration** (blowout = lead of 15+ entering the fourth, or 20+ at any point in the second half)

| bucket | games | forecast | actual | gap | note |
|---|---|---|---|---|---|
| 30-40% | 540 | 0.387 | 0.426 | 0.039 |  |
| 40-50% | 1375 | 0.436 | 0.452 | 0.016 |  |
| 50-60% | 368 | 0.539 | 0.511 | -0.028 |  |
| 60-70% | 139 | 0.638 | 0.662 | 0.024 | (too small to trust) |
| 70-100% | 40 | 0.740 | 0.650 | -0.090 | (too small to trust) |

Predicted blowouts: games given 60%+ blowout probability were blowouts 65.9% of the time (179 games (too small to trust)). All games: predicted 45.7%, actual 47.0%. Close games: predicted 43.7%, actual 44.9%. Overtime: predicted 4.6%, actual 4.6%. The blowout warning (probability at or above 55%) fired in 12% of games.

## Player simulation, legs and tickets


**Player legs, season 2025** (1,019,222 legs on the calibration grid)

| bucket | legs | forecast | actual | gap | note |
|---|---|---|---|---|---|
| 0-10% | 472732 | 0.026 | 0.025 | -0.001 |  |
| 10-20% | 122927 | 0.146 | 0.147 | 0.001 |  |
| 20-30% | 85213 | 0.248 | 0.250 | 0.002 |  |
| 30-40% | 68443 | 0.349 | 0.359 | 0.010 |  |
| 40-50% | 58998 | 0.449 | 0.460 | 0.011 |  |
| 50-60% | 51586 | 0.549 | 0.569 | 0.021 |  |
| 60-70% | 45151 | 0.649 | 0.666 | 0.017 |  |
| 70-80% | 38763 | 0.749 | 0.774 | 0.025 |  |
| 80-90% | 35345 | 0.850 | 0.864 | 0.014 |  |
| 90-100% | 40064 | 0.950 | 0.954 | 0.004 |  |

**Player legs, season 2026** (1,045,350 legs on the calibration grid)

| bucket | legs | forecast | actual | gap | note |
|---|---|---|---|---|---|
| 0-10% | 483622 | 0.026 | 0.024 | -0.002 |  |
| 10-20% | 128667 | 0.146 | 0.140 | -0.006 |  |
| 20-30% | 88904 | 0.247 | 0.242 | -0.006 |  |
| 30-40% | 69987 | 0.349 | 0.347 | -0.001 |  |
| 40-50% | 59828 | 0.449 | 0.457 | 0.008 |  |
| 50-60% | 53682 | 0.549 | 0.559 | 0.010 |  |
| 60-70% | 46876 | 0.649 | 0.663 | 0.014 |  |
| 70-80% | 40531 | 0.749 | 0.768 | 0.019 |  |
| 80-90% | 36476 | 0.850 | 0.861 | 0.012 |  |
| 90-100% | 36777 | 0.948 | 0.950 | 0.002 |  |

**Player legs, season both** (2,064,572 legs on the calibration grid)

| bucket | legs | forecast | actual | gap | note |
|---|---|---|---|---|---|
| 0-10% | 956354 | 0.026 | 0.025 | -0.001 |  |
| 10-20% | 251594 | 0.146 | 0.143 | -0.003 |  |
| 20-30% | 174117 | 0.248 | 0.246 | -0.002 |  |
| 30-40% | 138430 | 0.349 | 0.353 | 0.005 |  |
| 40-50% | 118826 | 0.449 | 0.458 | 0.009 |  |
| 50-60% | 105268 | 0.549 | 0.564 | 0.015 |  |
| 60-70% | 92027 | 0.649 | 0.664 | 0.015 |  |
| 70-80% | 79294 | 0.749 | 0.771 | 0.022 |  |
| 80-90% | 71821 | 0.850 | 0.863 | 0.013 |  |
| 90-100% | 76841 | 0.949 | 0.952 | 0.003 |  |

**Legs the model calls 70% or better, by market**

| market | legs at 70%+ | forecast | actual | gap | note |
|---|---|---|---|---|---|
| ast | 25639 | 0.853 | 0.862 | 0.009 |  |
| blk | 1969 | 0.775 | 0.763 | -0.012 |  |
| fg3m | 22842 | 0.809 | 0.837 | 0.027 |  |
| pa | 40026 | 0.861 | 0.879 | 0.018 |  |
| pr | 50287 | 0.866 | 0.873 | 0.008 |  |
| pra | 39660 | 0.858 | 0.868 | 0.010 |  |
| pts | 23239 | 0.842 | 0.859 | 0.017 |  |
| reb | 19448 | 0.834 | 0.843 | 0.008 |  |
| stl | 4846 | 0.752 | 0.748 | -0.004 |  |

**Calibration by market**

| market | all legs | mean abs gap by bucket | 70-80% bucket legs | 70-80% forecast | 70-80% actual |
|---|---|---|---|---|---|
| ast | 224410 | 0.005 | 8335 | 0.750 | 0.765 |
| blk | 134646 | 0.009 | 1386 | 0.743 | 0.730 |
| fg3m | 224410 | 0.016 | 11286 | 0.749 | 0.785 |
| pa | 269292 | 0.014 | 11952 | 0.750 | 0.779 |
| pr | 269292 | 0.008 | 14114 | 0.750 | 0.772 |
| pra | 314174 | 0.011 | 11937 | 0.750 | 0.769 |
| pts | 269292 | 0.013 | 8349 | 0.749 | 0.775 |
| reb | 224410 | 0.012 | 7779 | 0.748 | 0.761 |
| stl | 134646 | 0.006 | 4156 | 0.738 | 0.740 |

**Combo markets only (PRA, P+R, P+A), counted from joint results**

| bucket | legs | forecast | actual | gap | note |
|---|---|---|---|---|---|
| 0-10% | 380844 | 0.025 | 0.023 | -0.002 |  |
| 10-20% | 93886 | 0.146 | 0.142 | -0.004 |  |
| 20-30% | 66676 | 0.248 | 0.249 | 0.001 |  |
| 30-40% | 53801 | 0.349 | 0.357 | 0.009 |  |
| 40-50% | 46532 | 0.449 | 0.462 | 0.013 |  |
| 50-60% | 41787 | 0.549 | 0.572 | 0.022 |  |
| 60-70% | 39259 | 0.650 | 0.669 | 0.019 |  |
| 70-80% | 38003 | 0.750 | 0.773 | 0.023 |  |
| 80-90% | 39808 | 0.851 | 0.863 | 0.012 |  |
| 90-100% | 52162 | 0.951 | 0.954 | 0.003 |  |

**Double-doubles** (32,148 player-games with 20+ projected minutes)

| bucket | legs | forecast | actual | gap | note |
|---|---|---|---|---|---|
| 0-10% | 21693 | 0.031 | 0.036 | 0.005 |  |
| 10-20% | 4782 | 0.142 | 0.159 | 0.017 |  |
| 20-30% | 2282 | 0.243 | 0.283 | 0.039 |  |
| 30-40% | 1423 | 0.345 | 0.395 | 0.050 |  |
| 40-50% | 864 | 0.447 | 0.481 | 0.035 |  |
| 50-60% | 540 | 0.547 | 0.611 | 0.064 |  |
| 60-70% | 335 | 0.646 | 0.663 | 0.017 |  |
| 70-80% | 155 | 0.740 | 0.723 | -0.017 | (too small to trust) |
| 80-90% | 68 | 0.846 | 0.838 | -0.008 | (too small to trust) |
| 90-100% | 6 | 0.936 | 0.833 | -0.103 | (too small to trust) |

**Triple-doubles**: forecast 0.48%, actual 0.88% over 32,148 player-games; players given 10%+: forecast 22.8%, actual 33.7% (291 cases).

**Game legs (moneyline, spreads, totals on a fixed grid)**

| bucket | legs | forecast | actual | gap | note |
|---|---|---|---|---|---|
| 0-10% | 3835 | 0.063 | 0.065 | 0.002 |  |
| 10-20% | 7084 | 0.152 | 0.158 | 0.006 |  |
| 20-30% | 8195 | 0.250 | 0.245 | -0.005 |  |
| 30-40% | 8807 | 0.350 | 0.349 | -0.001 |  |
| 40-50% | 8988 | 0.450 | 0.445 | -0.005 |  |
| 50-60% | 8993 | 0.550 | 0.554 | 0.005 |  |
| 60-70% | 8796 | 0.649 | 0.651 | 0.002 |  |
| 70-80% | 8211 | 0.749 | 0.754 | 0.005 |  |
| 80-90% | 7095 | 0.848 | 0.842 | -0.006 |  |
| 90-100% | 3856 | 0.937 | 0.935 | -0.002 |  |

| market | legs | mean abs gap by bucket |
|---|---|---|
| ml | 4924 | 0.013 |
| spread | 39392 | 0.005 |
| total | 29544 | 0.003 |

**Tickets: hit rate against modelled joint probability** (no prices: these are built for highest joint probability, not value)

| ticket | season | tickets | modelled joint probability | actual hit rate | gap | if legs were multiplied | note |
|---|---|---|---|---|---|---|---|
| double_double | 2025 | 124 | 0.758 | 0.758 | 0.000 | 0.757 | (too small to trust) |
| double_double | 2026 | 94 | 0.782 | 0.745 | -0.037 | 0.782 | (too small to trust) |
| double_double | both | 218 | 0.768 | 0.752 | -0.016 | 0.768 |  |
| game_script | 2025 | 1231 | 0.585 | 0.603 | 0.017 | 0.568 |  |
| game_script | 2026 | 1231 | 0.591 | 0.613 | 0.022 | 0.574 |  |
| game_script | both | 2462 | 0.588 | 0.608 | 0.020 | 0.571 |  |
| props_4 | 2025 | 1231 | 0.632 | 0.649 | 0.017 | 0.617 |  |
| props_4 | 2026 | 1231 | 0.629 | 0.647 | 0.019 | 0.616 |  |
| props_4 | both | 2462 | 0.630 | 0.648 | 0.018 | 0.616 |  |
| props_6 | 2025 | 1231 | 0.466 | 0.505 | 0.040 | 0.445 |  |
| props_6 | 2026 | 1231 | 0.462 | 0.514 | 0.052 | 0.444 |  |
| props_6 | both | 2462 | 0.464 | 0.510 | 0.046 | 0.445 |  |
| props_8 | 2025 | 1231 | 0.328 | 0.387 | 0.059 | 0.307 |  |
| props_8 | 2026 | 1231 | 0.325 | 0.379 | 0.054 | 0.308 |  |
| props_8 | both | 2462 | 0.326 | 0.383 | 0.056 | 0.308 |  |

**70%+ legs by situation**

| 70%+ legs in | legs | forecast | actual | gap | note |
|---|---|---|---|---|---|
| blowout-flagged games | 28369 | 0.846 | 0.854 | 0.008 |  |
| other games | 199587 | 0.848 | 0.862 | 0.013 |  |
| early season (first 20 games) | 56376 | 0.848 | 0.868 | 0.020 |  |
| mid-season (21-55) | 96958 | 0.849 | 0.863 | 0.014 |  |
| after the All-Star break (56-72) | 46184 | 0.847 | 0.864 | 0.017 |  |
| final weeks (73+) | 28438 | 0.847 | 0.832 | -0.015 |  |
| starters | 200396 | 0.856 | 0.868 | 0.012 |  |
| bench | 27560 | 0.791 | 0.810 | 0.019 |  |
| team has a rotation player out | 65096 | 0.848 | 0.831 | -0.017 |  |

Blowout rule: in flagged games, 70%+ legs that also clear 70% inside blowout simulations hit 86.0% (27,193 legs); those that do not hit 73.0% (1,176 legs).

**Shooting gate**

| 70%+ scoring legs | legs | forecast | actual | gap |
|---|---|---|---|---|
| pass the shooting gate | 139929 | 0.855 | 0.869 | 0.014 |
| fail the shooting gate | 36125 | 0.843 | 0.858 | 0.015 |

**Simulated against historical correlation** (historical = average product of standardised surprises)

| pair | cases | simulated correlation | historical correlation |
|---|---|---|---|
| guard assists with centre points | 4468 | 0.023 | 0.134 |
| top scorer's points with game total | 4924 | 0.211 | 0.229 |
| two top scorers' points | 4924 | -0.133 | 0.015 |

## Factor ablation

Each cell is how much worse the out-of-sample fit gets when the group is removed (positive = the group helps). Fitted on earlier seasons, scored on 2024-25 and 2025-26.

| factor group | fg2a | fg3a | fta | reb | ast | stl | blk | fg2m | fg3m | mean | helps in both seasons | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| last-5 form | +4.53% | +5.48% | +1.10% | +0.37% | +1.53% | +0.13% | +0.24% | +0.03% | -0.00% | +1.49% | yes | keep |
| opponent shot profile | +0.06% | +0.12% | +0.13% | +0.00% | n/a | +0.09% | n/a | +0.06% | +0.01% | +0.07% | yes | keep |
| opponent vs position | +0.11% | +0.19% | +0.02% | +0.23% | +0.45% | +0.07% | +0.09% | n/a | n/a | +0.17% | yes | keep |
| rim protection | n/a | n/a | n/a | n/a | n/a | n/a | +0.04% | +0.03% | n/a | +0.04% | yes | keep |
| situation | +0.06% | +0.05% | +0.01% | -0.01% | +0.03% | +0.00% | +0.04% | -0.00% | -0.05% | +0.01% | yes | switch off |
| teammate in/out | +0.20% | +0.03% | +0.02% | +0.00% | +0.04% | n/a | n/a | n/a | n/a | +0.06% | yes | keep |
| referee crew | n/a | n/a | +0.03% | n/a | n/a | n/a | n/a | n/a | n/a | +0.03% | yes | keep |

**Game-level inputs** (margin and total error with and without each)

| input | season | margin MAE with | margin MAE without | total MAE with | total MAE without |
|---|---|---|---|---|---|
| referee crew | 2025 | 11.014 | 11.014 | 14.574 | 14.624 |
| referee crew | 2026 | 11.287 | 11.287 | 14.921 | 14.921 |
| style clash | 2025 | 11.014 | 11.014 | 14.574 | 14.574 |
| style clash | 2026 | 11.287 | 11.287 | 14.921 | 14.956 |
| rest, back-to-back, travel | 2025 | 11.014 | 11.086 | 14.574 | 14.570 |
| rest, back-to-back, travel | 2026 | 11.287 | 11.316 | 14.921 | 14.911 |
| who is missing tonight | 2025 | 11.014 | 10.940 | 14.574 | 14.571 |
| who is missing tonight | 2026 | 11.287 | 11.310 | 14.921 | 14.929 |