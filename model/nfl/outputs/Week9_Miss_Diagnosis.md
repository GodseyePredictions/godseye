# Week 9 — why the misses missed (metrics not met)

Source: nflverse play-by-play (all Sunday games), ESPN drive log (SNF). Model inputs compared with what happened.

## 1. Team touchdown volume (the model's anchor) fell short
| Team | Model off. TDs | Actual | Who scored |
|---|---|---|---|
| NYJ | 2.0 | 0 | — (lost 35-12, 61% pass) |
| MIA | 2.3 | 0 | — |
| ARI | 1.6 | 0 | — |
| DET | 3.1 | 1 | Gibbs |
| CHI (SNF) | 3.3 | 2 | Odunze (9-yd pass), Burden (56-yd pass); 3rd TD was a pick-six |
| LA | 2.9 | 2 | Corum, Nacua |
| IND | 2.7 | 2 | McGowan, Dulin (backups) |
| LV | 2.3 | 2 | Cousins, Bowers |
| SEA | 2.5 | 2 | Barner x2 |
Seven of the thirteen ATD misses came from offenses that scored 0–1 touchdowns.

## 2. Red-zone share did not convert (volume was fine)
| Player | Carries (exp) | RZ touches / team | Inside-10 carries | Team TDs went to |
|---|---|---|---|---|
| Kyren Williams | 15 (15) | 4/12 | 2 | Corum run, Nacua pass |
| Chuba Hubbard | 16 (16) | 3/8 | 0 | three passes (Tremble, Waller, McMillan) |
| Ollie Gordon II | 16 (14) | 4/5 | 0 | nobody |
| Woody Marks | 18 (13) | 5/10 | 0 | five passes |
| Omarion Hampton | 13 (11) | 3/8 | 2 | two passes |
| Jonathan Taylor | 13 (17) | 4/7 | 2 | McGowan, Dulin |
| D'Andre Swift (SNF) | 12 | 3 RZ carries (from the 13, 14, 8); Ahmed took a carry from the 9 | 1 | Odunze, Burden |
Backs got their touches; the red-zone play-calling went to the air far more than the OC tendencies suggested (CAR 3/3, HOU 5/5, SEA 2/2 TDs by pass).

## 3. Game script collapsed volume
Braelon Allen 8 carries (exp 15), NYJ trailing 35-12; Jeanty 6 carries (exp 11) and −5 receiving yards on screens, LV down 38-17; Love 29 attempts (line 30) and Kraft 3 targets (exp 6) with GB up 45-27 and running the clock; Penix 162 yards on 31 attempts (5.2 per attempt vs ~7 expected: efficiency, not volume).

## 4. Usage the pregame model could not see
Emanuel Wilson 0 carries (expected 16) on a 50% run day for Seattle; Ladd McConkey 0 targets (expected 4) on 68 Chargers plays; Jameson Williams 2 targets (expected 6). These are role/injury events, not variance, and they each killed a leg. Confirm against the Monday injury report.

## 5. Receivers' red-zone shares are thin by nature
Smith-Njigba 0 of Seattle's 5 red-zone targets (Barner got both TDs); Olave 0 of 10 despite 12 targets and 98 yards; Michael Wilson 3/10 with 1 end-zone target on a 0-TD offense; Kittle 1/13 as SF's 4 TDs went to McCaffrey x2, Purdy, Watkins. A 25–30% red-zone target share is one or two looks a game; the model prices that correctly (44% hit vs 49% expected on all ATDs) but it is not ticket material.
