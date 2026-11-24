# Ledger vs. new ATTD model: 2026 Weeks 1–9 head-to-head

Source: `ledger/NFL-Algo-Complete-Ledger.md`. All 339 ATD prices across 10 builds matched a player-game.
The new model was rebuilt week by week with **no look-ahead**: the xTD play model, team model and boosted model are refit each week on prior games only.
Grades are "as shipped" (standing rule 5).

## Shipped ATD legs, pooled (W1, W3, W4, W5, W6, W8, W9 TNF): n = 223
| | avg price | actual hit | log loss (lower = better) |
|---|---|---|---|
| Ledger engine (as shipped) | 38.0% | 40.8% | 0.6521 |
| New model, same legs | 40.2% | 40.8% | **0.6456** |
New model better by 0.0065, but the 95% bootstrap CI runs from −0.026 to +0.036, so it is **not a significant difference on 223 legs**.

## By build
| build | n | hit | ledger p | new p | ledger LL | new LL |
|---|---|---|---|---|---|---|
| v1.3 shipped (W1) | 25 | 64.0% | 43.5% | 38.5% | 0.756 | 0.746 |
| v1.7 shipped (W3) | 41 | 34.1% | 37.2% | 39.0% | 0.584 | 0.585 |
| v1.8 replay (W3) | 42 | 35.7% | 43.8% | 38.3% | 0.600 | 0.563 |
| v1.8/1.9 shipped (W4) | 40 | 40.0% | 37.2% | 42.0% | 0.617 | 0.678 |
| v1.9b shipped (W5) | 37 | 45.9% | 35.2% | 38.0% | 0.738 | 0.672 |
| v1.9e shipped (W6) | 43 | 25.6% | 38.3% | 41.6% | 0.595 | 0.611 |
| v1.9f shipped (W8) | 31 | 48.4% | 40.9% | 43.1% | 0.687 | 0.646 |
| v1.9g shipped (W9 TNF) | 6 | 33.3% | 25.0% | 31.6% | 0.625 | 0.513 |
The new model wins 5 of 8 shipped/replay comparisons. Its losses were W4 (Smith-Njigba 56%, St. Brown 58%, no TD) and W6.

## Where the two disagreed by 10+ points (shipped legs)
| case | legs | actual | ledger said | new said | closer |
|---|---|---|---|---|---|
| new model higher | 49 | **55.1%** | 35.8% | 50.9% | new model |
| new model lower | 25 | 40.0% | 43.3% | 27.1% | ledger |
The "new lower" group is mostly committee/backup backs and non-star QBs (Monangai, Allgeier, Montgomery, Shough).
The opportunity-share model rates them low, and they cashed more often than it expected. That's the goal-line-back exception the
ledger added in v1.9g; worth watching with more weeks.

## By position (shipped legs)
| pos | n | hit | ledger p | new p |
|---|---|---|---|---|
| RB | 123 | 48.8% | 41.4% | 44.0% |
| WR | 69 | 27.5% | 33.9% | 36.7% |
| TE | 22 | 40.9% | 31.9% | 34.0% |
| QB | 9 | 33.3% | 37.2% | 31.1% |
**Both engines overpriced the WRs that were picked.** On the full slate the new model's WRs are calibrated, so this is a selection effect: the WRs
that get onto a ticket are the ones whose price runs hottest. Recommendation: require a bigger edge on WR legs (or keep the
ledger's ×0.82 WR haircut) when picking from the board.

## New model's own weekly top-16 board (full slate, no picks involved)
| week | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| hits / 16 | 11 | 10 | 10 | 8 | 13 | 8 | 7 | 11 |
| expected | 7.8 | 8.8 | 8.4 | 9.2 | 9.1 | 9.4 | 9.2 | 9.1 |
78/128 = 61% vs 71 expected. On the full 2026 slate (2,983 player-games) calibration holds; the 60%+ bin hit 76.5% vs 66.8% priced.

## Rules carried forward from the ledger into the new build
- Questionable = singles only. Return from absence (missed 2+ of the team's last 4 games) = singles only. Both are kept out of parlays automatically.
- Roster and injury refresh is built into every run (weekly roster status + official injury report); re-run at inactives.
- ATDs stay their own ticket. Grading is as shipped.
- Early exits are already priced: the model trains on everyone who took one snap, so a player who leaves early counts as a miss in its base rates.
