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
