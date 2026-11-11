# NBA module backtest

Walk-forward over the last two full seasons, 2024-25 and 2025-26: 2,462 games, 49,138 player-games, 2.08 million graded legs. Run on 11 November 2026 with 2,000 simulations per game (live slates use 10,000). Reproduce with `python3 -m nba.backtest 2000` then `python3 -m nba.validate` from `model/`.

## Read this first

0. **Known live issue found after launch, 11 November 2026.** On teams with deep or reshuffled rosters early in the season, projected minutes for the top starters read 3 to 5 minutes low (for example a 35-minute guard projected at 30). The cause is bench players whose baseline still leans on last season's role. The backtest average for high-minute players is under 1 minute low, so this is concentrated in a few teams. It makes star legs conservative rather than aggressive. Not yet fixed.

1. **This backtest cannot tell you whether the system makes money.** There are no historical book prices in the project: no Odds API key was available, and ESPN drops old lines. So there is no ROI, no closing line value and no comparison with the closing line anywhere below. Everything here is calibration and hit rate.
2. **Legs are a fixed grid of thresholds, not bet365 rungs.** For example 10, 15, 20, 25, 30, 35 points for every player. Real ladders differ.
3. **Tickets in the backtest are chosen for highest joint probability**, because without prices there is no expected value to rank by. Live tickets are chosen by expected value.
4. **The noise settings of the simulation were tuned on sampled games from both test seasons.** Model coefficients are strictly walk-forward (fitted on earlier seasons only), but these few spread settings are not, so calibration figures are a little flattering. The 2026-27 season to date was not used for tuning and will be the first clean check.
5. **Which players were listed for a game comes from that game's box score** (who dressed or was listed inactive). Their status, minutes and everything else come from before tip-off.

## Where each model stands

| Part | Result | Verdict |
|---|---|---|
| Leg probabilities | Legs called 70-80% hit 77.4% (78,913 legs). Legs called 80-90% hit 86.7%. Every market within 3 points at the 70%+ end | Good, slightly cautious |
| Game legs | Moneyline, spread and total probabilities within 1 point of actual in every bucket | Good |
| Game simulation spread | Actual margin fell inside the simulated 10-90% band 79.4% of the time, totals 79.6% (target 80%) | Good |
| Blowouts | Predicted 45.7% of games, actual 47.0%. Overtime predicted 4.6%, actual 4.6% | Good |
| Team projection | Margin error 11.14 points. Ratings alone: 11.18. Rest, style, referees and absences add almost nothing | Weak edge over a plain rating |
| Minutes | Error 5.03 minutes against 5.07 for a simple recent-average. Better when a rotation player is out, worse in ordinary games | No better than the baseline overall |
| Minutes percentiles | 10th percentile beaten 89.1% (target 90%), 90th exceeded 9.9% (target 10%) | Good |
| Ticket joint probability | 4-leg: modelled 65.2%, hit 69.0%. 6-leg: modelled 49.5%, hit 55.1%. Multiplying legs would have said 63.6% and 47.6% | Too low by 4 to 6 points |
| Teammate correlations | Two top scorers' points: simulated -0.13, historical +0.02. Guard assists with centre points: simulated +0.02, historical +0.15 | Understated |
| Double-doubles | Under-forecast by 4 to 7 points between 20% and 60% | Weak |
| Triple-doubles | Forecast 0.46%, actual 0.88% | Poor: do not bet |

## Validation asked for in each step

### Step 3: minutes (last season, 2025-26)

| Games | Player-games | Error, model | Error, baseline | Beat 10th pct | Beat 50th | Beat 90th |
|---|---|---|---|---|---|---|
| All | 24,966 | 5.01 | 5.05 | 89.0% | 50.9% | 9.5% |
| Normal (no rotation player out, no blowout) | 9,645 | 5.08 | 4.89 | 90.8% | 59.0% | 12.9% |
| A rotation player out | 5,901 | 5.35 | 5.55 | 87.4% | 44.6% | 7.2% |
| Blowouts | 12,375 | 4.94 | 5.08 | 87.6% | 45.4% | 7.6% |

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

**Shooting gate:** scoring legs at 70%+ that pass the gate hit 87.0%; those that fail hit 86.2%, from almost the same forecast (85.3% and 84.2%). The gate does not separate good legs from bad ones in this data. It is still enforced because it is a standing rule. For your review.

**Blowout rule:** in flagged games, legs that clear 70% inside blowout simulations hit 86.2%; legs that do not hit 72.9% (1,155 legs). This rule earns its place.

### Step 6: simulation

- Calibration by market and bucket: tables below.
- Speed: a 10-game slate at 10,000 simulations per game takes 118 seconds on 4 cores, of which about 50 seconds is building features and fitting. The backtest takes 2.2 seconds per game per core at 2,000 simulations, most of it building and ranking tickets.

### Step 8: by situation (legs at 70%+)

| Situation | Legs | Forecast | Actual |
|---|---|---|---|
| Blowout-flagged games | 27,935 | 84.5% | 85.7% |
| Other games | 196,148 | 84.7% | 86.4% |
| First 20 games | 55,648 | 84.7% | 87.0% |
| Games 21-55 | 95,261 | 84.8% | 86.5% |
| Games 56-72 | 45,302 | 84.6% | 86.6% |
| Final weeks (73+) | 27,872 | 84.6% | 83.4% |
| Team has a rotation player out | 66,469 | 84.6% | 83.4% |

The two weak spots are the final weeks (resting and tanking) and games with a rotation player out. Both are over-forecast by about 1.2 points while everything else is under-forecast.

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
| 2025 | all games | 24172 | 5.041 | 5.083 | 0.893 | 0.517 | 0.102 |
| 2025 | normal (no rotation player out, no blowout) | 9009 | 4.998 | 4.803 | 0.912 | 0.593 | 0.128 |
| 2025 | a rotation player out | 6966 | 5.468 | 5.729 | 0.878 | 0.480 | 0.096 |
| 2025 | blowouts | 11542 | 4.997 | 5.144 | 0.878 | 0.459 | 0.082 |
| 2026 | all games | 24966 | 5.011 | 5.052 | 0.890 | 0.509 | 0.095 |
| 2026 | normal (no rotation player out, no blowout) | 9645 | 5.078 | 4.893 | 0.908 | 0.590 | 0.129 |
| 2026 | a rotation player out | 5901 | 5.350 | 5.551 | 0.874 | 0.446 | 0.072 |
| 2026 | blowouts | 12375 | 4.939 | 5.078 | 0.876 | 0.454 | 0.076 |
| both | all games | 49138 | 5.025 | 5.067 | 0.891 | 0.513 | 0.099 |
| both | normal (no rotation player out, no blowout) | 18654 | 5.039 | 4.850 | 0.910 | 0.592 | 0.129 |
| both | a rotation player out | 12867 | 5.414 | 5.647 | 0.876 | 0.464 | 0.085 |
| both | blowouts | 23917 | 4.967 | 5.110 | 0.877 | 0.457 | 0.079 |

## Game script engine

| season | games | margin MAE (ours) | margin MAE (ratings only) | margin MAE (always 0) | total MAE (ours) | total MAE (season average) | winner picked | margin inside 10-90% band | total inside 10-90% band |
|---|---|---|---|---|---|---|---|---|---|
| 2025 | 1231 | 11.005 | 11.009 | 12.751 | 14.575 | 15.817 | 0.665 | 0.798 | 0.805 |
| 2026 | 1231 | 11.284 | 11.352 | 13.272 | 14.922 | 15.831 | 0.684 | 0.790 | 0.787 |
| both | 2462 | 11.144 | 11.181 | 13.011 | 14.748 | 15.868 | 0.674 | 0.794 | 0.796 |

**Home win probability calibration**

| bucket | games | forecast | actual | gap | note |
|---|---|---|---|---|---|
| 0-10% | 14 | 0.076 | 0.000 | -0.076 | (too small to trust) |
| 10-20% | 96 | 0.160 | 0.125 | -0.035 | (too small to trust) |
| 20-30% | 194 | 0.253 | 0.237 | -0.015 | (too small to trust) |
| 30-40% | 310 | 0.353 | 0.355 | 0.001 |  |
| 40-50% | 378 | 0.448 | 0.455 | 0.007 |  |
| 50-60% | 431 | 0.548 | 0.571 | 0.023 |  |
| 60-70% | 410 | 0.648 | 0.624 | -0.023 |  |
| 70-80% | 343 | 0.749 | 0.770 | 0.021 |  |
| 80-90% | 226 | 0.846 | 0.841 | -0.005 |  |
| 90-100% | 60 | 0.925 | 0.933 | 0.009 | (too small to trust) |

**Blowout probability calibration** (blowout = lead of 15+ entering the fourth, or 20+ at any point in the second half)

| bucket | games | forecast | actual | gap | note |
|---|---|---|---|---|---|
| 30-40% | 539 | 0.387 | 0.421 | 0.034 |  |
| 40-50% | 1373 | 0.436 | 0.453 | 0.017 |  |
| 50-60% | 371 | 0.539 | 0.512 | -0.027 |  |
| 60-70% | 140 | 0.638 | 0.657 | 0.019 | (too small to trust) |
| 70-100% | 39 | 0.741 | 0.667 | -0.074 | (too small to trust) |

Predicted blowouts: games given 60%+ blowout probability were blowouts 65.9% of the time (179 games (too small to trust)). All games: predicted 45.7%, actual 47.0%. Close games: predicted 43.7%, actual 44.9%. Overtime: predicted 4.6%, actual 4.6%. The blowout warning (probability at or above 55%) fired in 12% of games.

## Player simulation, legs and tickets


**Player legs, season 2025** (1,022,626 legs on the calibration grid)

| bucket | legs | forecast | actual | gap | note |
|---|---|---|---|---|---|
| 0-10% | 475092 | 0.026 | 0.025 | -0.001 |  |
| 10-20% | 123864 | 0.146 | 0.148 | 0.002 |  |
| 20-30% | 85659 | 0.248 | 0.250 | 0.003 |  |
| 30-40% | 68744 | 0.349 | 0.359 | 0.011 |  |
| 40-50% | 59588 | 0.449 | 0.462 | 0.014 |  |
| 50-60% | 52111 | 0.549 | 0.571 | 0.022 |  |
| 60-70% | 45197 | 0.649 | 0.668 | 0.020 |  |
| 70-80% | 38604 | 0.749 | 0.778 | 0.029 |  |
| 80-90% | 35108 | 0.850 | 0.868 | 0.018 |  |
| 90-100% | 38659 | 0.950 | 0.955 | 0.005 |  |

**Player legs, season 2026** (1,051,468 legs on the calibration grid)

| bucket | legs | forecast | actual | gap | note |
|---|---|---|---|---|---|
| 0-10% | 488117 | 0.026 | 0.024 | -0.002 |  |
| 10-20% | 129865 | 0.146 | 0.140 | -0.006 |  |
| 20-30% | 89482 | 0.247 | 0.241 | -0.006 |  |
| 30-40% | 70498 | 0.348 | 0.349 | 0.000 |  |
| 40-50% | 60553 | 0.449 | 0.456 | 0.008 |  |
| 50-60% | 54066 | 0.549 | 0.562 | 0.013 |  |
| 60-70% | 47175 | 0.649 | 0.669 | 0.020 |  |
| 70-80% | 40309 | 0.749 | 0.771 | 0.022 |  |
| 80-90% | 36156 | 0.850 | 0.865 | 0.016 |  |
| 90-100% | 35247 | 0.948 | 0.952 | 0.004 |  |

**Player legs, season both** (2,074,094 legs on the calibration grid)

| bucket | legs | forecast | actual | gap | note |
|---|---|---|---|---|---|
| 0-10% | 963209 | 0.026 | 0.024 | -0.001 |  |
| 10-20% | 253729 | 0.146 | 0.144 | -0.002 |  |
| 20-30% | 175141 | 0.248 | 0.246 | -0.002 |  |
| 30-40% | 139242 | 0.349 | 0.354 | 0.005 |  |
| 40-50% | 120141 | 0.449 | 0.459 | 0.011 |  |
| 50-60% | 106177 | 0.549 | 0.566 | 0.017 |  |
| 60-70% | 92372 | 0.649 | 0.669 | 0.020 |  |
| 70-80% | 78913 | 0.749 | 0.774 | 0.025 |  |
| 80-90% | 71264 | 0.850 | 0.867 | 0.017 |  |
| 90-100% | 73906 | 0.949 | 0.953 | 0.005 |  |

**Legs the model calls 70% or better, by market**

| market | legs at 70%+ | forecast | actual | gap | note |
|---|---|---|---|---|---|
| ast | 25399 | 0.853 | 0.863 | 0.011 |  |
| blk | 1895 | 0.776 | 0.761 | -0.014 |  |
| fg3m | 22703 | 0.808 | 0.836 | 0.029 |  |
| pa | 39386 | 0.859 | 0.882 | 0.023 |  |
| pr | 49571 | 0.864 | 0.875 | 0.011 |  |
| pra | 38678 | 0.857 | 0.871 | 0.015 |  |
| pts | 22721 | 0.841 | 0.861 | 0.020 |  |
| reb | 19081 | 0.833 | 0.844 | 0.012 |  |
| stl | 4649 | 0.752 | 0.751 | -0.001 |  |

**Calibration by market**

| market | all legs | mean abs gap by bucket | 70-80% bucket legs | 70-80% forecast | 70-80% actual |
|---|---|---|---|---|---|
| ast | 225445 | 0.006 | 8284 | 0.750 | 0.766 |
| blk | 135267 | 0.010 | 1339 | 0.744 | 0.727 |
| fg3m | 225445 | 0.016 | 11347 | 0.748 | 0.785 |
| pa | 270534 | 0.016 | 11934 | 0.750 | 0.787 |
| pr | 270534 | 0.010 | 14142 | 0.750 | 0.775 |
| pra | 315623 | 0.014 | 11794 | 0.750 | 0.774 |
| pts | 270534 | 0.015 | 8303 | 0.749 | 0.778 |
| reb | 225445 | 0.014 | 7779 | 0.748 | 0.766 |
| stl | 135267 | 0.006 | 3991 | 0.738 | 0.742 |

**Combo markets only (PRA, P+R, P+A), counted from joint results**

| bucket | legs | forecast | actual | gap | note |
|---|---|---|---|---|---|
| 0-10% | 383397 | 0.025 | 0.023 | -0.002 |  |
| 10-20% | 95119 | 0.146 | 0.142 | -0.004 |  |
| 20-30% | 67098 | 0.248 | 0.249 | 0.002 |  |
| 30-40% | 54484 | 0.349 | 0.357 | 0.009 |  |
| 40-50% | 46986 | 0.449 | 0.465 | 0.017 |  |
| 50-60% | 42312 | 0.549 | 0.573 | 0.024 |  |
| 60-70% | 39660 | 0.650 | 0.673 | 0.024 |  |
| 70-80% | 37870 | 0.750 | 0.778 | 0.028 |  |
| 80-90% | 39583 | 0.851 | 0.868 | 0.017 |  |
| 90-100% | 50182 | 0.951 | 0.955 | 0.005 |  |

**Double-doubles** (32,313 player-games with 20+ projected minutes)

| bucket | legs | forecast | actual | gap | note |
|---|---|---|---|---|---|
| 0-10% | 22053 | 0.031 | 0.037 | 0.006 |  |
| 10-20% | 4794 | 0.142 | 0.161 | 0.019 |  |
| 20-30% | 2261 | 0.246 | 0.288 | 0.043 |  |
| 30-40% | 1343 | 0.347 | 0.404 | 0.057 |  |
| 40-50% | 829 | 0.446 | 0.502 | 0.055 |  |
| 50-60% | 514 | 0.547 | 0.625 | 0.078 |  |
| 60-70% | 311 | 0.643 | 0.659 | 0.016 |  |
| 70-80% | 143 | 0.739 | 0.741 | 0.002 | (too small to trust) |
| 80-90% | 58 | 0.841 | 0.845 | 0.004 | (too small to trust) |
| 90-100% | 7 | 0.926 | 0.857 | -0.069 | (too small to trust) |

**Triple-doubles**: forecast 0.46%, actual 0.88% over 32,313 player-games; players given 10%+: forecast 22.9%, actual 33.6% (271 cases).

**Game legs (moneyline, spreads, totals on a fixed grid)**

| bucket | legs | forecast | actual | gap | note |
|---|---|---|---|---|---|
| 0-10% | 3839 | 0.063 | 0.065 | 0.002 |  |
| 10-20% | 7097 | 0.152 | 0.158 | 0.006 |  |
| 20-30% | 8177 | 0.250 | 0.245 | -0.005 |  |
| 30-40% | 8807 | 0.350 | 0.348 | -0.002 |  |
| 40-50% | 8985 | 0.450 | 0.445 | -0.005 |  |
| 50-60% | 8995 | 0.550 | 0.554 | 0.005 |  |
| 60-70% | 8796 | 0.649 | 0.651 | 0.002 |  |
| 70-80% | 8194 | 0.749 | 0.754 | 0.005 |  |
| 80-90% | 7104 | 0.848 | 0.842 | -0.006 |  |
| 90-100% | 3866 | 0.936 | 0.934 | -0.002 |  |

| market | legs | mean abs gap by bucket |
|---|---|---|
| ml | 4924 | 0.012 |
| spread | 39392 | 0.005 |
| total | 29544 | 0.003 |

**Tickets: hit rate against modelled joint probability** (no prices: these are built for highest joint probability, not value)

| ticket | season | tickets | modelled joint probability | actual hit rate | gap | if legs were multiplied | note |
|---|---|---|---|---|---|---|---|
| double_double | 2025 | 107 | 0.757 | 0.766 | 0.010 | 0.756 | (too small to trust) |
| double_double | 2026 | 90 | 0.774 | 0.767 | -0.007 | 0.774 | (too small to trust) |
| double_double | both | 197 | 0.765 | 0.766 | 0.002 | 0.764 | (too small to trust) |
| game_script | 2025 | 1231 | 0.605 | 0.644 | 0.039 | 0.586 |  |
| game_script | 2026 | 1231 | 0.612 | 0.646 | 0.034 | 0.593 |  |
| game_script | both | 2462 | 0.609 | 0.645 | 0.036 | 0.589 |  |
| props_4 | 2025 | 1231 | 0.653 | 0.695 | 0.041 | 0.636 |  |
| props_4 | 2026 | 1231 | 0.652 | 0.685 | 0.033 | 0.636 |  |
| props_4 | both | 2462 | 0.652 | 0.690 | 0.037 | 0.636 |  |
| props_6 | 2025 | 1228 | 0.496 | 0.556 | 0.060 | 0.476 |  |
| props_6 | 2026 | 1231 | 0.494 | 0.546 | 0.052 | 0.475 |  |
| props_6 | both | 2459 | 0.495 | 0.551 | 0.056 | 0.476 |  |

**70%+ legs by situation**

| 70%+ legs in | legs | forecast | actual | gap | note |
|---|---|---|---|---|---|
| blowout-flagged games | 27935 | 0.845 | 0.857 | 0.012 |  |
| other games | 196148 | 0.847 | 0.864 | 0.016 |  |
| early season (first 20 games) | 55648 | 0.847 | 0.870 | 0.023 |  |
| mid-season (21-55) | 95261 | 0.848 | 0.865 | 0.017 |  |
| after the All-Star break (56-72) | 45302 | 0.846 | 0.866 | 0.020 |  |
| final weeks (73+) | 27872 | 0.846 | 0.834 | -0.011 |  |
| starters | 195380 | 0.855 | 0.871 | 0.016 |  |
| bench | 28703 | 0.792 | 0.808 | 0.016 |  |
| team has a rotation player out | 66469 | 0.846 | 0.834 | -0.012 |  |

Blowout rule: in flagged games, 70%+ legs that also clear 70% inside blowout simulations hit 86.2% (26,780 legs); those that do not hit 72.9% (1,155 legs).

**Shooting gate**

| 70%+ scoring legs | legs | forecast | actual | gap |
|---|---|---|---|---|
| pass the shooting gate | 137452 | 0.853 | 0.870 | 0.017 |
| fail the shooting gate | 35607 | 0.842 | 0.862 | 0.020 |

**Simulated against historical correlation** (historical = average product of standardised surprises)

| pair | cases | simulated correlation | historical correlation |
|---|---|---|---|
| guard assists with centre points | 4468 | 0.023 | 0.151 |
| top scorer's points with game total | 4924 | 0.210 | 0.230 |
| two top scorers' points | 4924 | -0.130 | 0.018 |

## Factor ablation

Each cell is how much worse the out-of-sample fit gets when the group is removed (positive = the group helps). Fitted on earlier seasons, scored on 2024-25 and 2025-26.

| factor group | fg2a | fg3a | fta | reb | ast | stl | blk | fg2m | fg3m | mean | helps in both seasons | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| last-5 form | +4.72% | +5.41% | +1.12% | +0.38% | +1.56% | +0.13% | +0.22% | +0.03% | -0.00% | +1.51% | yes | keep |
| opponent shot profile | +0.06% | +0.12% | +0.13% | +0.00% | n/a | +0.09% | n/a | +0.06% | +0.01% | +0.07% | yes | keep |
| opponent vs position | +0.11% | +0.20% | +0.02% | +0.23% | +0.44% | +0.07% | +0.09% | n/a | n/a | +0.17% | yes | keep |
| rim protection | n/a | n/a | n/a | n/a | n/a | n/a | +0.04% | +0.03% | n/a | +0.04% | yes | keep |
| situation | +0.06% | +0.05% | +0.01% | -0.01% | +0.03% | +0.00% | +0.04% | -0.00% | -0.05% | +0.01% | yes | switch off |
| teammate in/out | +0.19% | +0.03% | +0.02% | +0.00% | +0.04% | n/a | n/a | n/a | n/a | +0.06% | yes | keep |
| referee crew | n/a | n/a | +0.03% | n/a | n/a | n/a | n/a | n/a | n/a | +0.03% | yes | keep |

**Game-level inputs** (margin and total error with and without each)

| input | season | margin MAE with | margin MAE without | total MAE with | total MAE without |
|---|---|---|---|---|---|
| referee crew | 2025 | 11.005 | 11.005 | 14.575 | 14.625 |
| referee crew | 2026 | 11.284 | 11.284 | 14.922 | 14.922 |
| style clash | 2025 | 11.005 | 11.005 | 14.575 | 14.575 |
| style clash | 2026 | 11.284 | 11.284 | 14.922 | 14.957 |
| rest, back-to-back, travel | 2025 | 11.005 | 11.074 | 14.575 | 14.571 |
| rest, back-to-back, travel | 2026 | 11.284 | 11.311 | 14.922 | 14.913 |
| who is missing tonight | 2025 | 11.005 | 10.940 | 14.575 | 14.571 |
| who is missing tonight | 2026 | 11.284 | 11.310 | 14.922 | 14.929 |