# NBA data health report

Generated 2026-11-11T19:36:07+00:00 from `model/nba/data/nba.sqlite`.

## Rows and date coverage

| table | rows | first | last |
|---|---|---|---|
| games | 3,854 | 2023-10-24 | 2026-11-10 |
| schedule | 3,900 | 2023-10-24 | 2026-11-14 |
| player_games | 101,649 | 2023-10-25 | 2026-11-11 |
| officials | 11,505 | 2023-10-24 | 2026-11-10 |
| starters | 38,540 | 2023-10-24 | 2026-11-11 |
| injury_reports | 288,967 | 2023-10-24 | 2026-11-11 |
| ref_assignments | 30 | 2026-11-11 | 2026-11-11 |
| market_lines | 10 | 2026-11-11 | 2026-11-11 |
| odds | 0 |  |  |
| availability | 882 | 2026-11-11 | 2026-11-11 |
| pbp_snapshots | 522 | 2026-11-10 | 2026-11-10 |
| nba_runs | 3 | 2026-11-11 | 2026-11-11 |
| nba_projections | 655 | 2026-11-11 | 2026-11-11 |
| nba_legs | 0 |  |  |
| nba_tickets | 0 |  |  |
| nba_game_cards | 21 | 2026-11-11 | 2026-11-11 |
| nba_report_cards | 0 |  |  |
| nba_status_changes | 0 |  |  |

## Games by season

| season | finished games loaded | on the schedule | first | last |
|---|---|---|---|---|
| 2023-24 | 1,232 | 1,234 | 2023-10-24 | 2024-04-14 |
| 2024-25 | 1,231 | 1,239 | 2024-10-22 | 2025-04-13 |
| 2025-26 | 1,231 | 1,239 | 2025-10-21 | 2026-04-12 |
| 2026-27 | 160 | 188 | 2026-10-20 | 2026-11-10 |

## Missing fields

| check | result |
|---|---|
| Box-score lines | 101,649 (82,738 with minutes, 18,911 did not play) |
| Played lines with no position | 0 |
| Played lines with no seconds-by-quarter (no play-by-play) | 0 |
| Rebuilt minutes vs box-score minutes | mean gap 0.25 min; 0.08% of lines off by more than 2 |
| Shots with a zone vs box-score attempts | 687,585 of 686,346 (100.18%) |
| Games with no officials listed | 19 of 3,854 |
| Games with fewer than 3 officials | 0 |
| Injury reports loaded | 2,074 reports, 288,967 rows |
| Injury rows whose player name found no exact match | 3,712 of 278,508 (1.33%) |
| Game dates with at least one injury report | 99.8% |
| Games with a market spread and total | 10 (ESPN keeps these only on the day; none exist for past seasons) |
| Player prop and alternate-line prices | 0 rows (no odds key and no bet365 sheet loaded yet) |
| Closing prices captured | 0 |
| Starters | espn_box: 3,854 games. Known only once a game starts: no pre-tip source |
| Names waiting in the review file | 32 (player: 32) |

## Not ingested, and why

| Data | Reason |
|---|---|
| Tracking, hustle, matchup, play-type, defender distance | `stats.nba.com` does not answer from this cloud environment (audit, Part B) |
| Confirmed starters before tip-off | No reachable free source. ESPN lists starters only after tip |
| Historical prop prices, alternate lines, closing prices | No Odds API key; ESPN drops old lines |
| Basketball Reference pages | Not needed: box scores, play-by-play and officials all come from ESPN with history. Kept out to respect its crawl limits |
| Minutes restrictions for past seasons | The official report does not publish them; ESPN's notes exist only for today |
| Player age | Not in any source pulled. The minutes model uses each player's own history instead |

pbpstats possession-level totals (team, opponent, player, lineup) are snapshotted daily into `pbp_snapshots` but the models do not read them yet: they cannot be re-pulled for past dates fast enough to backtest.
