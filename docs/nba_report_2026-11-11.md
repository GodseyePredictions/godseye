# NBA report card: Wednesday 11 November 2026

First graded slate. 10 games, tickets issued at 6:00 pm ET on DraftKings ladder prices (read through ESPN). Nothing was marked as placed, so this is a paper result.

## Grade: B for the picks, D for the pricing, C+ overall

| Part | Result | Grade |
|---|---|---|
| Ticket legs | 76 of 83 hit (91.6%). The model said 77.5%; DraftKings' prices implied 82.1% | A |
| 4-leg tickets | 7 of 10 cashed | A |
| 6-leg tickets | 5 of 10 cashed | A |
| 8-leg tickets | 6 of 10 cashed | A |
| Multi-game slips | 0 of 2 (10 of 12 legs, 13 of 15 legs) | C |
| Probabilities | Too low everywhere. Legs called 77% hit 86%; DraftKings had them at 86% | D |
| "Negative value" flag | Put on 26 of 30 tickets; 16 of those cashed | F |
| Star players | Six named stars projected 29 to 31 minutes and played 32 to 36 | D |
| Game calls | Winner right in 8 of 10; margin error 9.4 points against the market's 9.3 | B |

One night is a small sample. 18 of 30 tickets cashing against about 7.5 expected is partly luck: the same tickets would cash far fewer times on an average night.

## What cashed

| Game | 4-leg | 6-leg | 8-leg |
|---|---|---|---|
| WSH @ IND | Won (+107) | Won (+222) | Won (+374) |
| CLE @ NY | Won (+141) | Won (+289) | Won (+367) |
| DEN @ MEM | Won (−119) | Won (+143) | Won (+180) |
| BKN @ NO | Won (+123) | Won (+233) | Won (+343) |
| ORL @ UTAH | Won (+164) | Won (+287) | Won (+478) |
| BOS @ TOR | Won (+305) | Lost, 5 of 6 | Lost, 7 of 8 |
| LAL @ MIL | Won (+212) | Lost, 5 of 6 | Lost, 7 of 8 |
| SA @ CHI | Lost, 2 of 4 | Lost, 4 of 6 | Won (+226) |
| GS @ HOU | Lost, 3 of 4 | Lost, 5 of 6 | Lost, 7 of 8 |
| OKC @ POR | Lost, 3 of 4 | Lost, 4 of 6 | Lost, 6 of 8 |

Prices are the leg prices multiplied together. DraftKings' real same-game price would have been lower, so the return below is an upper bound.

| Ticket type | Tickets | Cashed | Units won at 1 unit each |
|---|---|---|---|
| 4-leg | 10 | 7 | +8.4 |
| 6-leg | 10 | 5 | +6.7 |
| 8-leg | 10 | 6 | +15.7 |
| Multi-game | 2 | 0 | −2.0 |
| All | 32 | 18 | +28.8 |

## The seven legs that missed

| Leg | Model | Needed | Got | Why |
|---|---|---|---|---|
| Immanuel Quickley 5+ assists | 72% | 5 | 4 | One short |
| Stephon Castle 4+ assists | 82% | 4 | 3 | One short |
| Stephon Castle 4+ rebounds | 74% | 4 | 1 | Model error |
| Kyle Kuzma 3+ rebounds | 83% | 3 | 1 | Blowout: lost minutes |
| Tari Eason 4+ rebounds | 73% | 4 | 3 | One short |
| Shai Gilgeous-Alexander 4+ assists | 77% | 4 | 2 | Model error |
| Kenrich Williams 3+ rebounds | 80% | 3 | 2 | One short |

All seven were rebounds or assists. No points leg and no threes leg on a ticket missed.

## What the night showed

1. **The model was too cautious, and the book was right.** Across all 3,318 priced player legs, the model's forecasts were more wrong than DraftKings' prices (error score 0.1364 against 0.1345, lower is better). In every probability band the result landed on DraftKings' number, not the model's.
2. **So the "negative value" label was backwards.** The tickets it flagged returned +28.1 units; the four it did not flag returned +2.7.
3. **Starters were under-projected**: 27.9 minutes projected against 29.1 played, and 14.6 points against 15.4.

## Adjustments made

| Change | Why |
|---|---|
| A benched player (coach's decision) no longer counts as "out" | Healthy scratches were being treated as absent, then as "returning" the next night, which pulled minutes off starters |
| A player out all season no longer triggers redistribution | His last-season minutes were being handed to teammates a second time |
| Last season counts 60% less for a player who changed teams | Anthony Davis and Trae Young were projected on their old roles |
| Established starters give up less when a team's listed minutes exceed 240 | The squeeze was hitting everyone equally |
| "Negative value" label replaced by a neutral note | It was wrong on 16 of 26 tickets |

## Not fixed

- **Top stars still project 4 to 5 minutes low on some teams.** Re-running last night with the adjusted model moved Jalen Brunson from 28.9 to 29.7 minutes (he played 35) and Anthony Davis from 28.2 to 29.2 (he played 34). Across the 61 players projected for 27 or more minutes, the gap closed from 1.05 minutes to 0.63. The remaining cause, checked on Washington, is that the model expects too many bench players to get on the floor (about 12; 9 played).
- **Model probabilities remain below the book's.** Until they are calibrated against prices over more slates, the model's view of value should not be trusted over DraftKings'.
