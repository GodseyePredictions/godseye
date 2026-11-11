# NBA module backtest

Walk-forward over the last two full seasons, 2024-25 and 2025-26: 2,462 games, 49,122 player-games, 2.07 million graded legs. Run on 11 November 2026 with 2,000 simulations per game (live slates use 10,000). Reproduce with `python3 -m nba.backtest 2000` then `python3 -m nba.validate` from `model/`.

## Read this first

1. **This backtest cannot tell you whether the system makes money.** There are no historical book prices in the project: no Odds API key was available, and ESPN drops old lines. So there is no ROI, no closing line value and no comparison with the closing line anywhere below. Everything here is calibration and hit rate.
2. **Legs are a fixed grid of thresholds, not bet365 rungs.** For example 10, 15, 20, 25, 30, 35 points for every player. Real ladders differ.
3. **Tickets in the backtest are chosen for highest joint probability**, because without prices there is no expected value to rank by. Live tickets are chosen by expected value.
4. **The noise settings of the simulation were tuned on sampled games from both test seasons.** Model coefficients are strictly walk-forward (fitted on earlier seasons only), but these few spread settings are not, so calibration figures are a little flattering. The 2026-27 season to date was not used for tuning and will be the first clean check.
5. **Which players were listed for a game comes from that game's box score** (who dressed or was listed inactive). Their status, minutes and everything else come from before tip-off.

## Where each model stands

| Part | Result | Verdict |
|---|---|---|
| Leg probabilities | Legs called 70-80% hit 77.4% (78,814 legs). Legs called 80-90% hit 86.6%. Every market within 3 points at the 70%+ end | Good, slightly cautious |
| Game legs | Moneyline, spread and total probabilities within 1 point of actual in every bucket | Good |
| Game simulation spread | Actual margin fell inside the simulated 10-90% band 79.4% of the time, totals 79.6% (target 80%) | Good |
| Blowouts | Predicted 45.7% of games, actual 47.0%. Overtime predicted 4.6%, actual 4.6% | Good |
| Team projection | Margin error 11.14 points. Ratings alone: 11.18. Rest, style, referees and absences add almost nothing | Weak edge over a plain rating |
| Minutes | Error 5.05 minutes against 5.06 for a simple recent-average. Better when a rotation player is out, worse in ordinary games | No better than the baseline overall |
| Minutes percentiles | 10th percentile beaten 89.1% (target 90%), 90th exceeded 10.0% (target 10%) | Good |
| Ticket joint probability | 4-leg: modelled 69.7%, hit 72.8%. 6-leg: modelled 55.5%, hit 60.6%. Multiplying legs would have said 62.4% and 47.1% | Too low by 3 to 5 points |
| Teammate correlations | Two top scorers' points: simulated -0.13, historical +0.02. Guard assists with centre points: simulated +0.02, historical +0.15 | Understated |
| Double-doubles | Under-forecast by 4 to 7 points between 20% and 60% | Weak |
| Triple-doubles | Forecast 0.46%, actual 0.88% | Poor: do not bet |

## Validation asked for in each step

### Step 3: minutes (last season, 2025-26)

| Games | Player-games | Error, model | Error, baseline | Beat 10th pct | Beat 50th | Beat 90th |
|---|---|---|---|---|---|---|
| All | 24,955 | 5.03 | 5.05 | 89.0% | 51.0% | 9.6% |
| Normal (no rotation player out, no blowout) | 9,658 | 5.09 | 4.90 | 90.8% | 59.2% | 13.0% |
| A rotation player out | 5,876 | 5.38 | 5.54 | 87.5% | 44.6% | 7.3% |
| Blowouts | 12,364 | 4.95 | 5.07 | 87.5% | 45.5% | 7.6% |

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

**Blowout rule:** in flagged games, legs that clear 70% inside blowout simulations hit 86.2%; legs that do not hit 72.7% (1,127 legs). This rule earns its place.

### Step 6: simulation

- Calibration by market and bucket: tables below.
- Speed: a 10-game slate at 10,000 simulations per game takes 118 seconds on 4 cores, of which about 50 seconds is building features and fitting. The backtest takes 2.2 seconds per game per core at 2,000 simulations, most of it building and ranking tickets.

### Step 8: by situation (legs at 70%+)

| Situation | Legs | Forecast | Actual |
|---|---|---|---|
| Blowout-flagged games | 27,834 | 84.5% | 85.7% |
| Other games | 195,771 | 84.7% | 86.3% |
| First 20 games | 55,648 | 84.7% | 86.9% |
| Games 21-55 | 95,067 | 84.8% | 86.5% |
| Games 56-72 | 45,203 | 84.6% | 86.6% |
| Final weeks (73+) | 27,687 | 84.6% | 83.3% |
| Team has a rotation player out | 66,446 | 84.6% | 83.3% |

The two weak spots are the final weeks (resting and tanking) and games with a rotation player out. Both are over-forecast by about 1.3 points while everything else is under-forecast.

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
| 2025 | all games | 24167 | 5.065 | 5.079 | 0.892 | 0.518 | 0.104 |
| 2025 | normal (no rotation player out, no blowout) | 9007 | 5.035 | 4.805 | 0.910 | 0.594 | 0.131 |
| 2025 | a rotation player out | 6952 | 5.496 | 5.722 | 0.876 | 0.478 | 0.098 |
| 2025 | blowouts | 11543 | 5.012 | 5.137 | 0.877 | 0.459 | 0.083 |
| 2026 | all games | 24955 | 5.027 | 5.049 | 0.890 | 0.510 | 0.096 |
| 2026 | normal (no rotation player out, no blowout) | 9658 | 5.090 | 4.895 | 0.908 | 0.592 | 0.130 |
| 2026 | a rotation player out | 5876 | 5.379 | 5.537 | 0.875 | 0.446 | 0.073 |
| 2026 | blowouts | 12364 | 4.954 | 5.074 | 0.875 | 0.455 | 0.076 |
| both | all games | 49122 | 5.046 | 5.064 | 0.891 | 0.514 | 0.100 |
| both | normal (no rotation player out, no blowout) | 18665 | 5.064 | 4.851 | 0.909 | 0.593 | 0.131 |
| both | a rotation player out | 12828 | 5.442 | 5.637 | 0.876 | 0.463 | 0.086 |
| both | blowouts | 23907 | 4.982 | 5.105 | 0.876 | 0.457 | 0.079 |

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


**Player legs, season 2025** (1,023,500 legs on the calibration grid)

| bucket | legs | forecast | actual | gap | note |
|---|---|---|---|---|---|
| 0-10% | 476636 | 0.026 | 0.025 | -0.001 |  |
| 10-20% | 123989 | 0.146 | 0.149 | 0.003 |  |
| 20-30% | 85595 | 0.248 | 0.252 | 0.005 |  |
| 30-40% | 68625 | 0.348 | 0.360 | 0.012 |  |
| 40-50% | 59578 | 0.449 | 0.462 | 0.014 |  |
| 50-60% | 52006 | 0.549 | 0.571 | 0.022 |  |
| 60-70% | 45050 | 0.649 | 0.672 | 0.023 |  |
| 70-80% | 38448 | 0.749 | 0.777 | 0.028 |  |
| 80-90% | 34939 | 0.850 | 0.867 | 0.017 |  |
| 90-100% | 38634 | 0.950 | 0.954 | 0.005 |  |

**Player legs, season 2026** (1,049,904 legs on the calibration grid)

| bucket | legs | forecast | actual | gap | note |
|---|---|---|---|---|---|
| 0-10% | 487551 | 0.026 | 0.024 | -0.002 |  |
| 10-20% | 129866 | 0.146 | 0.140 | -0.006 |  |
| 20-30% | 89289 | 0.247 | 0.244 | -0.004 |  |
| 30-40% | 70290 | 0.349 | 0.348 | -0.000 |  |
| 40-50% | 60372 | 0.449 | 0.458 | 0.010 |  |
| 50-60% | 53970 | 0.549 | 0.562 | 0.013 |  |
| 60-70% | 46982 | 0.649 | 0.668 | 0.020 |  |
| 70-80% | 40366 | 0.749 | 0.771 | 0.022 |  |
| 80-90% | 35996 | 0.850 | 0.866 | 0.016 |  |
| 90-100% | 35222 | 0.948 | 0.952 | 0.004 |  |

**Player legs, season both** (2,073,404 legs on the calibration grid)

| bucket | legs | forecast | actual | gap | note |
|---|---|---|---|---|---|
| 0-10% | 964187 | 0.026 | 0.024 | -0.001 |  |
| 10-20% | 253855 | 0.146 | 0.144 | -0.002 |  |
| 20-30% | 174884 | 0.248 | 0.248 | 0.000 |  |
| 30-40% | 138915 | 0.348 | 0.354 | 0.005 |  |
| 40-50% | 119950 | 0.449 | 0.460 | 0.012 |  |
| 50-60% | 105976 | 0.549 | 0.566 | 0.017 |  |
| 60-70% | 92032 | 0.649 | 0.670 | 0.021 |  |
| 70-80% | 78814 | 0.749 | 0.774 | 0.025 |  |
| 80-90% | 70935 | 0.850 | 0.866 | 0.016 |  |
| 90-100% | 73856 | 0.949 | 0.953 | 0.004 |  |

**Legs the model calls 70% or better, by market**

| market | legs at 70%+ | forecast | actual | gap | note |
|---|---|---|---|---|---|
| ast | 25402 | 0.852 | 0.862 | 0.010 |  |
| blk | 1912 | 0.775 | 0.763 | -0.012 |  |
| fg3m | 22592 | 0.808 | 0.837 | 0.029 |  |
| pa | 39315 | 0.859 | 0.882 | 0.022 |  |
| pr | 49460 | 0.864 | 0.874 | 0.010 |  |
| pra | 38593 | 0.857 | 0.871 | 0.014 |  |
| pts | 22716 | 0.841 | 0.860 | 0.020 |  |
| reb | 18964 | 0.833 | 0.843 | 0.010 |  |
| stl | 4651 | 0.752 | 0.751 | -0.001 |  |

**Calibration by market**

| market | all legs | mean abs gap by bucket | 70-80% bucket legs | 70-80% forecast | 70-80% actual |
|---|---|---|---|---|---|
| ast | 225370 | 0.006 | 8382 | 0.750 | 0.765 |
| blk | 135222 | 0.009 | 1359 | 0.744 | 0.728 |
| fg3m | 225370 | 0.016 | 11314 | 0.749 | 0.787 |
| pa | 270444 | 0.016 | 11943 | 0.750 | 0.788 |
| pr | 270444 | 0.011 | 14055 | 0.750 | 0.774 |
| pra | 315518 | 0.015 | 11770 | 0.750 | 0.774 |
| pts | 270444 | 0.015 | 8313 | 0.749 | 0.779 |
| reb | 225370 | 0.015 | 7697 | 0.748 | 0.761 |
| stl | 135222 | 0.006 | 3981 | 0.738 | 0.741 |

**Combo markets only (PRA, P+R, P+A), counted from joint results**

| bucket | legs | forecast | actual | gap | note |
|---|---|---|---|---|---|
| 0-10% | 383873 | 0.025 | 0.023 | -0.002 |  |
| 10-20% | 95247 | 0.146 | 0.143 | -0.003 |  |
| 20-30% | 66996 | 0.248 | 0.251 | 0.004 |  |
| 30-40% | 54303 | 0.349 | 0.359 | 0.010 |  |
| 40-50% | 46857 | 0.449 | 0.466 | 0.018 |  |
| 50-60% | 42295 | 0.549 | 0.574 | 0.025 |  |
| 60-70% | 39467 | 0.650 | 0.675 | 0.025 |  |
| 70-80% | 37768 | 0.750 | 0.779 | 0.029 |  |
| 80-90% | 39470 | 0.851 | 0.867 | 0.016 |  |
| 90-100% | 50130 | 0.951 | 0.955 | 0.004 |  |

**Double-doubles** (32,205 player-games with 20+ projected minutes)

| bucket | legs | forecast | actual | gap | note |
|---|---|---|---|---|---|
| 0-10% | 21976 | 0.031 | 0.037 | 0.006 |  |
| 10-20% | 4804 | 0.142 | 0.164 | 0.021 |  |
| 20-30% | 2222 | 0.245 | 0.297 | 0.052 |  |
| 30-40% | 1343 | 0.345 | 0.389 | 0.044 |  |
| 40-50% | 834 | 0.446 | 0.507 | 0.061 |  |
| 50-60% | 510 | 0.547 | 0.614 | 0.067 |  |
| 60-70% | 311 | 0.646 | 0.672 | 0.026 |  |
| 70-80% | 136 | 0.738 | 0.699 | -0.040 | (too small to trust) |
| 80-90% | 62 | 0.843 | 0.855 | 0.012 | (too small to trust) |
| 90-100% | 7 | 0.928 | 0.714 | -0.213 | (too small to trust) |

**Triple-doubles**: forecast 0.46%, actual 0.88% over 32,205 player-games; players given 10%+: forecast 22.8%, actual 34.2% (275 cases).

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
| double_double | 2025 | 109 | 0.760 | 0.743 | -0.017 | 0.760 | (too small to trust) |
| double_double | 2026 | 86 | 0.777 | 0.733 | -0.044 | 0.777 | (too small to trust) |
| double_double | both | 195 | 0.768 | 0.738 | -0.029 | 0.767 | (too small to trust) |
| game_script | 2025 | 1231 | 0.644 | 0.673 | 0.029 | 0.575 |  |
| game_script | 2026 | 1231 | 0.656 | 0.690 | 0.034 | 0.583 |  |
| game_script | both | 2462 | 0.650 | 0.681 | 0.031 | 0.579 |  |
| props_4 | 2025 | 1231 | 0.695 | 0.725 | 0.030 | 0.624 |  |
| props_4 | 2026 | 1231 | 0.698 | 0.731 | 0.033 | 0.625 |  |
| props_4 | both | 2462 | 0.697 | 0.728 | 0.032 | 0.624 |  |
| props_6 | 2025 | 1231 | 0.554 | 0.595 | 0.041 | 0.470 |  |
| props_6 | 2026 | 1231 | 0.556 | 0.617 | 0.061 | 0.472 |  |
| props_6 | both | 2462 | 0.555 | 0.606 | 0.051 | 0.471 |  |

**70%+ legs by situation**

| 70%+ legs in | legs | forecast | actual | gap | note |
|---|---|---|---|---|---|
| blowout-flagged games | 27834 | 0.845 | 0.857 | 0.011 |  |
| other games | 195771 | 0.847 | 0.863 | 0.016 |  |
| early season (first 20 games) | 55648 | 0.847 | 0.869 | 0.022 |  |
| mid-season (21-55) | 95067 | 0.848 | 0.865 | 0.017 |  |
| after the All-Star break (56-72) | 45203 | 0.846 | 0.866 | 0.020 |  |
| final weeks (73+) | 27687 | 0.846 | 0.833 | -0.013 |  |
| starters | 195173 | 0.855 | 0.870 | 0.015 |  |
| bench | 28432 | 0.791 | 0.808 | 0.017 |  |
| team has a rotation player out | 66446 | 0.846 | 0.833 | -0.014 |  |

Blowout rule: in flagged games, 70%+ legs that also clear 70% inside blowout simulations hit 86.2% (26,707 legs); those that do not hit 72.7% (1,127 legs).

**Shooting gate**

| 70%+ scoring legs | legs | forecast | actual | gap |
|---|---|---|---|---|
| pass the shooting gate | 137246 | 0.853 | 0.870 | 0.017 |
| fail the shooting gate | 35430 | 0.842 | 0.862 | 0.020 |

**Simulated against historical correlation** (historical = average product of standardised surprises)

| pair | cases | simulated correlation | historical correlation |
|---|---|---|---|
| guard assists with centre points | 4468 | 0.023 | 0.154 |
| top scorer's points with game total | 4924 | 0.210 | 0.228 |
| two top scorers' points | 4924 | -0.129 | 0.017 |

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