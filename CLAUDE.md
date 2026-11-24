# Godseye Predictions

## NBA module: standing rules

These rules apply to every session that touches the NBA player-prop module. The module is being built separately first and will be added to Godseye alongside the existing NFL algo.

### Goal

Project full probability distributions for NBA player props and build bet365 same-game parlays (SGPs) from them.

### Markets

- **Player:** points, rebounds, assists, 3-pointers made, steals, blocks, Points+Rebounds+Assists, Points+Rebounds, Points+Assists, double-double, triple-double.
- **Game:** moneyline, spread, alternative spread, game total, alternative total.

### Standing rules (carried over from the NFL algo)

1. **Algo only.** Picks come from this system's own output. No expert, media or consensus picks. Web lookups are allowed only for official injury reports, confirmed starters and rosters.
2. **No verified availability, no leg.** A player without a confirmed status for tonight cannot appear on a ticket.
3. **Floor rungs for SGPs.** Every SGP leg must have model probability of 70% or higher. Edge rungs (lower probability, positive expected value) are for straight singles only.
4. **Ticket structure per game:** one 4-leg and one 6-leg props-only SGP. Players from both teams are eligible; take the best legs regardless of side. Double-double and triple-double legs go on their own ticket and are never mixed into the props SGPs.
5. **Book format.** Support both bet365 over/under lines and bet365 milestone ladders (for example 20+, 25+, 30+ points). Only use rungs the book actually offers, read from the odds feed or a pasted CSV. Never assume a rung exists.
6. **Game script first.** No player prop is projected until the game-level simulation has run for that game. Blowout risk is assessed before any leg is considered.
7. **Point-in-time discipline.** Every feature uses only information available before tip-off. No leakage from the game being predicted.
8. **Shrink small samples.** Any split (home/away, versus a defender, last 5 games) is blended toward the player's baseline in proportion to sample size, and the sample size is shown next to the number.
9. **Log everything with a timestamp:** projection, probability, price taken, closing line, result.
10. **Explain every number.** Each projection carries an itemised list of the adjustments that moved it from baseline.

### Engineering rules

- Mirror the folder layout, naming and test style of the existing NFL module.
- Python for all modelling code.
- All thresholds (70% floor, blowout cutoffs, shrinkage strengths, caps) live in one config file. Nothing hard-coded.
- Write tests for every module. Do not change or break NFL code.
- If a data source cannot supply something a prompt asks for, stop and tell the user. Do not invent a substitute silently.

### Amendments (11 November 2026, from the owner)

- **Ticket sizes:** 4-leg, 6-leg and 8-leg props SGPs per game (rule 4 said 4 and 6).
- **Props tickets use four markets:** points, rebounds, assists, 3-pointers made. The other markets stay modelled but are not used on props tickets.
- **Multi-game slips:** 4 or 5 legs from each of 3 games (12 or 15 props), chosen by the algorithm's own joint probabilities. Every leg still needs 70%.
- **Book:** bet365 or DraftKings. DraftKings milestone ladders are read from ESPN's odds API. Rule 5 still holds: only rungs the book lists, and a rung is used only when it fits the player's over/under line.
- **Site:** landing page at `/`, NFL at `/nfl`, NBA at `/nba`.

### Amendments (19 November 2026)

- **4-leg slips use four different players.** 6-leg and 8-leg slips may still carry two legs on one player.
- **Rebound legs need 75%.** Every other market keeps the 70% floor.
- **Calibration from graded slates.** Each market's probabilities are shifted by what graded legs show, shrunk by sample size and capped (`model/nba/calibrate.py`). The ledger keeps the raw probability beside the calibrated one. All three settings live in `model/nba/config.py`.

### Amendments (20 November 2026, from the owner)

- **Never post results on the site.** No graded slips, records, units or "what cashed" on GodsEye (site or artifact). Grading still runs and is logged; results are reported to the owner in chat or as a private file only. Config: `site_show_results` stays False.
- **The all-games slip is made on request only**, delivered as a PDF, and is not shown on the site.
- **Leg floor is 75% in every market** (rule 3 said 70%). Slip legs the model called 70 to 74% hit 71% over six graded nights.
- **Rebound legs:** at most one per slip, and none on a 4-leg slip.
- **Slips per game:** a 4-leg, a second 4-leg on four different players, and a 6-leg. The 8-leg is dropped.

### Amendments (24 November 2026, from the owner)

- **Cashed slips showcase.** Winning algorithm slips are listed on a "Cashed slips" tab (site and artifact), each with an example stake and what it would have returned. This is the one exception to "never post results": the full tracker stays private (`site_show_results` False). The page always states how many slips were issued and how many lost, that stakes are examples and not bets placed, and what the same stakes on every slip would have netted. Config: `site_show_cashed`, `cashed_long_price`, `cashed_stake_long`, `cashed_stake_short`.
