# NBA minutes rebuild and rebound test (19 November 2026)

## What was wrong

The linear minutes model was barely better than a plain baseline (season, last 10, last 5 blended) and worse than the baseline for projected starters. The earlier note that "players who played 34+ minutes were projected 5 short" was mostly a selection effect: conditional on the projection, the model was not biased low. The real problems were error size and role: players who actually started were projected 0.8 to 2.2 minutes low and bench players high, because the model did not use the most recent game or who else was available.

## What changed

A boosted model of minutes given the player plays (`model/nba/minutes.py`, config `minutes_boosted`). New inputs, all from games before tip plus tonight's availability:

- minutes in the last game and the last three games, and whether he started them
- minutes this season when starting and when coming off the bench
- his rank in minutes among the teammates available tonight
- the minutes and number of usual starters ruled out tonight

The 240-minute reconciliation before simulation is switched off for this model (it made projections worse); each simulated game is still brought to 240.

## Out-of-sample results

Models fitted on earlier seasons only. Average miss in minutes, players who played:

| Season | Player-games | Baseline | Old model | New model |
|---|---|---|---|---|
| 2025-26 | 26,323 | 5.00 | 4.93 | 4.52 |
| 2026-27 to date | 4,871 | 5.23 | 5.23 | 4.53 |

Players projected 34+ minutes: the old model said 36.7 and they played 33.1; the new model says 35.1 and they played 34.8.

Full simulation on the same 206 games of 2025-26 (every sixth game, 2,000 simulations each):

| Measure | Old | New |
|---|---|---|
| Minutes, average miss | 5.15 | 4.83 |
| Points, average miss | 4.75 | 4.68 |
| Rebounds, average miss | 1.92 | 1.90 |
| Assists, average miss | 1.41 | 1.40 |
| Threes, average miss | 0.94 | 0.94 |
| Points legs, Brier score | 0.0895 | 0.0880 |
| Rebounds legs, Brier score | 0.1046 | 0.1032 |
| Assists legs, Brier score | 0.0928 | 0.0916 |
| Threes legs, Brier score | 0.1225 | 0.1216 |

Lower is better in every row. Legs the model calls 70% or better still hit at their forecast rate (84% forecast, 84% hit for points).

Still open: simulated minutes for players with a 30+ baseline average about 0.9 above what they play.

## Rebounds: tested, not shipped

An opportunity-based rebound model was tested: own and opponent miss rates, shot volume, offensive and defensive rebounding rates, three-point rate, the rebounding load of teammates available and ruled out, and separate offensive-rebound history. Out of sample the gain over the current per-minute model was too small to matter (Poisson deviance from 1.168 to 1.166 in 2025-26, and from 1.173 to 1.164 on 4,173 player-games this season; average miss unchanged at 1.74 and 1.72 rebounds). Nearly all the predictive weight stayed on the player's own rebound rate. It was not added.

Rebound accuracy does improve through minutes. What box scores cannot supply is rebound chances and box-out data; that needs a tracking-data source.
