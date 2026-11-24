# NFL Algo — Complete Ledger (2026, Weeks 1–9)

**What this is.** Every slip, SGP and anytime-TD ticket the model shipped during the 2026 season, graded against official nflverse stat lines, with the report-card findings and the algorithm change that followed each one. Built from the saved slate files (`slate_week*.json`, `game_*.json`) so every number here is what was on the card before kickoff; nothing is re-picked after the fact. Weeks 1–2 and the pre-engine single-game packs exist only as rendered PDFs (image pages, no text layer); their results are summarized from the report cards of the time.

**How to read a card.** *Model* is the engine's probability for the leg; *Fair* is the break-even American price (play only when the book posts longer). SGP prices come from a Gaussian-copula Monte Carlo (same-game legs correlated; cross-game legs independent). Floor band = 70–88% legs chosen near 78%; aggressive band = 55–68% near 62%; mid = 62–74%. *Tier* shows how the 4 / 6 / 8-leg tickets nest. *2026 x/y pre-game* is the player's hit rate on that exact rung before the game (added to cards from Week 6). Q = Questionable at build time (singles only from v1.8). Early exits count as misses.

**Bet365 conventions baked in.** Milestone ladders, not over/unders: rush and receiving yards from 20+ in 10s, carries 10/15/20/25, pass yards by 25 from 150, attempts by 5, receptions from 1+. Props SGPs never carry TD legs; ATDs are a separate ticket. Staking rule throughout: quarter-Kelly, play above fair only.


## Engine evolution

| Version | Date | What changed | Why |
|---|---|---|---|
| v1.0–1.3 | Sept 10–13 | Projections = recent form × season × defense-allowed × environment; bet365 ladders; first full-slate 4/6-leg SGPs + separate ATD slip; cross-game combos 4/6/8/10/12; per-game intel | Week 1 build (TB@CIN pack → full Sept 13 slate) |
| v1.4–1.5 | Sept 14–16 | Roster-status gate (EXE/RES/PUP/SUS/NON/RET/CUT) and injury Out/Doubtful gate | Josh Jacobs appeared on the ATD slip while on the exempt list |
| v1.6c | Sept 26 | OC/DC scheme priors for all 32 teams blended with measured team tendencies; value band 70–88% near 78%; role floor (no 1+ reception legs on 2-catch players); two-pass distinct-player build; market cap 2; one RB volume leg per team (backfield pie); props SGPs 4/6/8 | Week 1 report card: 13/13 SGPs missed on edge rungs (59% vs 60% on legs — calibrated but no margin) |
| v1.7 | Sept 27 | Week 3 slate shipped on this build; aggressive (55–68%) variant added for Week 4 | — |
| v1.8 | Oct 4 | Empirical-Bayes projections: current season weighted by games vs the player's prior full-season rate (K=6), recent-form tilt capped ±15%, SD widened for small samples; game-script layer (implied points vs baseline, blowout haircuts); Questionable = singles only; role-confidence gate (2+ games, RB 8 touches/g, WR/TE 4 tgt/g, QB 20 att/g) | Week 3 report card: 69% vs 78%. Root cause was a code bug — "season baseline" had collapsed to the mean of 2–3 current games. Leakage-free replay of Week 3 on v1.8: 79% vs 76%, SGP4 7/14 |
| v1.9 | Oct 4–11 | ATD v2 opportunity model native: λ = team implied TDs (from total/spread) × player red-zone share (inside-20 touches, inside-10 carries, end-zone targets, TD share; shrunk K=6) × opponent RZ-TD-rate and position TD-allowed. "Nothing in here is who scored recently." | Week 3 ATD board under the recency model; v2 back-test W1–2 top-20 hit 75% vs 55% |
| v1.9b/c | Oct 11 | Packaging fix (coordinators.csv lost from zips); pbp name-collision fix (Bi./Br. Robinson both read as B.Robinson — the ATD model had been reading zero 2026 red-zone work for both) | Bijan 39% → 50% once fixed |
| v1.9d | Oct 15 | Environment-split multiplier capped ±15%; 2026-rate sanity gate on every rung (≥60% of a counting rung, 65% of a yardage rung); backfield-trend term (last-2 vs season touches, clamped, ^0.75) | Hampton 2+ receptions priced 79% on a 1.0-catch season (env ×1.33 + OC prior); Hampton losing touches to Mitchell unseen by the ±15% tilt |
| v1.9e | Oct 15–18 | WR/TE opportunity weights (end-zone targets 35%, inside-10 15%); personnel-aware defence regression when 2+ starting DBs are out; per-game all-position slips (QB+RB+WR+TE prop + ATD); official inactives via personnel file; bench list for displaced starters | JSN priced at a 16% share while owning 60% of Seattle's end-zone targets (RB weights applied to a WR) |
| v1.9f | Oct 18 | Calibration layer fitted on 708 shipped legs (W3–5): SD inflation rush yds ×1.25, rec yds ×1.20 (TE ×1.30), RB receptions ×1.30, WR/TE receptions ×1.10, carries ×1.10, attempts ×0.90; probability offsets at half the observed gap; any 50+ yds / 4+ receptions rung needs a ≥60% 2026 hit rate; no 1+ reception legs on 4-catch players | Week 5 report card: centre right (65% vs 65% on the full candidate list), spread wrong — every rung above the first over-priced on skill yardage, attempts under-priced. **Out-of-sample test:** Week 6 v1.9f build (made pre-kick, not shipped) went 86% vs 76% with SGP4 6/11 against the shipped v1.9e's 73% and 2/11 |
| v1.9g | Nov 5 | Return-from-absence gate (missed 2+ of last 4 team games, or partial return last week → singles only, no teammate "he's back" boost); 2.5% early-exit haircut per leg; 2%-per-team wipeout factor on every ticket; ATD position calibration (WR ×0.82, RB ×1.05) and team-total convexity (λ × (team TDs/2.5)^0.35); goal-line exception so a low-volume back can be priced for TD; weather applied by hand as personnel multipliers (not yet automated) | Week 8: Lamar (1 snap) and Mayfield (7 snaps) left in their first games back — nine floor legs gone; WR TD picks 26% vs 34% priced over six weeks; low-team-total TD picks over-priced by 9 points. Week 8 replay on v1.9g: 63% → 71% |

**Week 9 TNF result (first v1.9g card):** JAX 33, BAL 10 — floor 4-leg (+129 → +215 rain version), floor 6-leg (+204 / +310), ATD 4-leg (+332), ATD 6-leg (+534), the all-position slip (+352) and the Rodriguez ATD single (fair +131) all cashed; the 8-leg died on Henry's TD and the 'realistic' 4 on Strange's third catch.

**Still open (as of Nov 7):** automated weather join (wind/precip rules at build time); chalk ATD triple 1/3 in three straight graded weeks (ticket-level cap, not a model change); aggressive-band +1-rung reception legs 46% vs 62%; combo builder concentrates on one leg (diversify by team, not just game); pace and routes/snap participation data; skewed (non-normal) distributions for yardage.


## Scorecard by week (recomputed from the saved cards against official stat lines)

| Build | Legs | Actual | Expected | SGP4 | SGP6 | SGP8 |
|---|---|---|---|---|---|---|
| Week 1 (v1.3) | 40/71 | 56% | 61% | 1/15 | 0/15 | 0/15 |
| Week 3 shipped (v1.7) | 74/108 | 69% | 78% | 4/14 | 1/14 | 0/14 |
| Week 3 v1.8 replay | 85/107 | 79% | 76% | 7/14 | 7/14 | 4/14 |
| Week 4 floor | 72/102 | 71% | 77% | 3/14 | 2/14 | 1/14 |
| Week 4 aggressive | 59/104 | 57% | 63% | 3/14 | 1/14 | 0/14 |
| Week 5 floor | 71/98 | 72% | 76% | 4/13 | 4/13 | 1/13 |
| Week 5 aggressive | 55/101 | 54% | 61% | 2/13 | 0/13 | 0/13 |
| Week 6 shipped (v1.9e) | 61/84 | 73% | 77% | 2/11 | 1/11 | 1/11 |
| Week 6 v1.9f (pre-kick, unshipped) | 69/80 | 86% | 77% | 6/11 | 6/11 | 1/11 |
| Week 6 aggressive | 50/85 | 59% | 63% | 3/11 | 1/11 | 0/11 |
| Week 8 early (v1.9f) | 40/63 | 63% | 77% | 1/8 | 1/8 | 1/8 |
| Week 8 aggressive | 34/64 | 53% | 62% | 1/8 | 1/8 | 1/8 |
| Week 8 v1.9g replay | 44/62 | 71% | 77% | 2/8 | 1/8 | 1/8 |

Floor-band production builds only (W3 shipped, W4, W5, W6 shipped, W8): the engine's centre is right and its spread was wrong until v1.9f; v1.9f's one blind test (W6 pre-kick) was its best week, and its one shipped week (W8) was hit by early exits the model did not price — which is what v1.9g addresses.


## Week 1 — Sunday Sept 13 2026 (first full slate)

*Engine v1.3.* First full-slate build: 4-leg and 6-leg props SGPs per game, separate ATD slip, cross-game combos. Legs were chosen at the edge of the line (≈55–65%), which is what the Week 1 report card found: calibrated on legs (the saved file re-grades at 56% vs 61%; the Week 1 card reported 59% vs 60%) but the posted SGP slips did not cash — the saved file shows one 4-leg card (BAL@IND) clearing on the exact legs stored, while the 13 slips actually placed from the pack all missed; the ATD slip went 7/8 (Higgins the miss — the request to swap him for Chase Brown after the fact was declined for ledger integrity). Full rendered packs: NFL-Sept13-Full-Slate-Pack.pdf, NFL-Sept13-Cross-Combos.pdf, Full-Slate-ATD-Slip.pdf; report cards: Week1-Report-Card.pdf, Week1-Combo-Report-Card.pdf, Week1-ATD-Report-Card.pdf.


### ARI@LAC — final 26-14
*O/U None · indoor · turf*

**Injury report (as built):** ARI DEF · Garrett Williams (CB) — Out · Achilles; ARI OFF · Isaiah Adams (G) — Out · Knee · DNP; ARI DEF · Dadrion Taylor-Demerson (S) — Out · Ribs · DNP; ARI OFF · Jeremiyah Love (RB) — Questionable · Ankle; LAC DEF · Deane Leonard (CB) — Out · Abdomen · DNP; LAC DEF · Tuli Tuipulotu (DE) — Questionable · Hip

**Defensive leaks:** LAC D leaks passing interceptions to QBs: x1.43 league; ARI D leaks rushing yards to RBs: x1.16 league (worsening x1.20 last 4); ARI D leaks receiving yards to RBs: x1.08 league (worsening x1.69 last 4)

**Coordinators:** LAC OC Mike McDaniel — NEW (pass_rb prior, SD widened) · LAC DC Chris O'Leary — NEW (unit trends less reliable) · ARI OC Nathaniel Hackett — NEW (run_heavy prior, SD widened) · ARI DC Nick Rallis

**Props SGP** — 4-leg 20.0% · fair +399 ✗ · 6-leg 7.1% · fair +1304 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Justin Herbert o0.5 INT o0.5 | 70% | -231 | ✓ 1 INT | `4-leg core`
| 2 | Ladd McConkey 3+ receptions | 66% | -192 | ✓ 5 | `4-leg core`
| 3 | Omarion Hampton 50+ rush yds | 61% | -157 | ✗ 43 | `4-leg core`
| 4 | Omarion Hampton 14+ carries | 59% | -144 | ✗ 12 | `4-leg core`
| 5 | Justin Herbert 200+ pass yds | 55% | -123 | ✓ 209 | `+6`
| 6 | Ladd McConkey 40+ rec yds | 53% | -112 | ✓ 82 | `+6`

Legs 4/6 (expected 3.6)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Omarion Hampton (LAC RB) | 44% | +127 | ✓ TD |  |
| Ladd McConkey (LAC WR) | 34% | +193 | ✓ TD |  |

TD double (Omarion Hampton + Ladd McConkey): 19.2% · fair +419 **CASHED**


### ATL@PIT — final 13-20
*O/U None · outdoor · grass*

**Injury report (as built):** ATL OFF · Tua Tagovailoa (QB) — Out · Oblique · DNP; ATL OFF · Michael Penix Jr. (QB) — Out · Knee; ATL DEF · Billy Bowman Jr. (CB) — Out · Achilles; ATL OFF · Cameron Williams (T) — Out · Ankle · DNP; ATL DEF · Za'Darius Smith (DE) — Questionable · Shoulder; ATL OFF · Jake Matthews (T) — nan · DNP; PIT DEF · Joey Porter Jr. (CB) — Questionable · Back

**Defensive leaks:** PIT D leaks passing interceptions to QBs: x1.34 league (worsening x1.06 last 4); PIT D leaks receptions to TEs: x1.20 league (worsening x1.08 last 4); ATL D leaks passing interceptions to QBs: x1.17 league (worsening x1.82 last 4); ATL D leaks receptions to RBs: x1.13 league

**Coordinators:** PIT OC Brian Angelichio — NEW (pass_te prior, SD widened) · PIT DC Patrick Graham — NEW (unit trends less reliable) · ATL OC Tommy Rees — NEW (run_heavy prior, SD widened) · ATL DC Jeff Ulbrich

**Props SGP** — 4-leg 26.8% · fair +273 ✗ · 6-leg —  · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Bijan Robinson 16+ carries | 65% | -187 | ✓ 21 | `4-leg core`
| 2 | Bijan Robinson 80+ rush yds | 61% | -158 | ✓ 83 | `4-leg core`
| 3 | DK Metcalf 50+ rec yds | 53% | -115 | ✗ 40 | `4-leg core`

Legs 2/3 (expected 1.8)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Bijan Robinson (ATL RB) | 51% | -105 | ✓ TD |  |
| DK Metcalf (PIT WR) | 29% | +248 | ✗ no TD |  |

TD double (Bijan Robinson + DK Metcalf): 16.7% · fair +498 ✗


### BAL@IND — final 41-23
*O/U None · outdoor · turf*

**Injury report (as built):** BAL DEF · Nnamdi Madubuike (DT) — Out · Neck; BAL DEF · Teddye Buchanan (LB) — Out · Knee; BAL OFF · Devontez Walker (WR) — Questionable · Groin; BAL DEF · Calais Campbell (DE) — nan · DNP; IND DEF · Austin Ajiake (LB) — Questionable · Hamstring · DNP; IND DEF · DeForest Buckner (DT) — nan · DNP

**Defensive leaks:** IND D leaks passing interceptions to QBs: x1.26 league; IND D leaks receiving yards to TEs: x1.22 league (worsening x1.15 last 4); BAL D leaks receiving yards to RBs: x1.30 league (worsening x1.15 last 4); BAL D leaks receptions to RBs: x1.21 league (worsening x1.33 last 4)

**Coordinators:** IND OC Jim Bob Cooter — continuity: data rules · IND DC Lou Anarumo · BAL OC Declan Doyle — NEW (pass_wr prior, SD widened) · BAL DC Anthony Weaver — NEW (unit trends less reliable)

**Props SGP** — 4-leg 25.2% · fair +297 **CASHED** · 6-leg 10.3% · fair +875 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Derrick Henry 80+ rush yds | 77% | -342 | ✓ 144 | `4-leg core`
| 2 | Jonathan Taylor 18+ carries | 66% | -197 | ✓ 19 | `4-leg core`
| 3 | Jonathan Taylor 60+ rush yds | 59% | -145 | ✓ 98 | `4-leg core`
| 4 | Derrick Henry 18+ carries | 59% | -144 | ✓ 24 | `4-leg core`
| 5 | Lamar Jackson o0.5 INT o0.5 | 56% | -128 | ✗ 0 INT | `+6`
| 6 | Zay Flowers 80+ rec yds | 54% | -118 | ✓ 150 | `+6`

Legs 5/6 (expected 3.7)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Derrick Henry (BAL RB) | 70% | -233 | ✓ TD |  |
| Jonathan Taylor (IND RB) | 50% | +102 | ✓ TD |  |

TD double (Derrick Henry + Jonathan Taylor): 36.7% · fair +172 **CASHED**


### BUF@HOU — final 36-31
*O/U None · outdoor · turf*

**Injury report (as built):** BUF OFF · Ty Johnson (RB) — Questionable · Hamstring; BUF DEF · Jordan Hancock (CB) — Questionable · Quadricep; BUF DEF · T.J. Sanders (DE) — Questionable · Knee; HOU DEF · Will Anderson Jr. (DE) — nan · DNP; HOU DEF · Kayden McDonald (DT) — nan · DNP

**Defensive leaks:** HOU D leaks passing interceptions to QBs: x1.55 league; BUF D leaks passing interceptions to QBs: x1.17 league; BUF D leaks receptions to RBs: x1.10 league

**Coordinators:** HOU OC Nick Caley — continuity: data rules · HOU DC Matt Burke · BUF OC Pete Carmichael Jr. — NEW (balanced prior, SD widened) · BUF DC Jim Leonhard — NEW (unit trends less reliable)

**Props SGP** — 4-leg 15.2% · fair +557 ✗ · 6-leg 9.4% · fair +959 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Josh Allen 25+ pass att | 66% | -190 | ✓ 29 | `4-leg core`
| 2 | DJ Moore 30+ rec yds | 59% | -146 | ✓ 100 | `4-leg core`
| 3 | James Cook 80+ rush yds | 59% | -147 | ✗ 57 | `4-leg core`
| 4 | Nico Collins 70+ rec yds | 57% | -136 | ✓ 75 | `4-leg core`
| 5 | C.J. Stroud 200+ pass yds | 57% | -133 | ✓ 274 | `+6`
| 6 | Josh Allen o0.5 INT o0.5 | 55% | -123 | ✗ 0 INT | `+6`

Legs 4/6 (expected 3.5)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| James Cook (BUF RB) | 59% | -143 | ✗ no TD |  |
| David Montgomery (HOU RB) | 44% | +130 | ✓ TD |  |

TD double (James Cook + David Montgomery): 27.8% · fair +259 ✗


### CHI@CAR — final 59-37
*O/U None · outdoor · grass*

**Injury report (as built):** CAR DEF · Patrick Jones II (LB) — Out · Back · DNP; CHI DEF · Xavier Woods (S) — Questionable · Groin; CHI OFF · Tyson Bagent (QB) — Questionable · Back · DNP; CHI OFF · Rome Odunze (WR) — Questionable · Calf; CHI OFF · Ozzy Trapilo (T) — Questionable · Knee

**Defensive leaks:** CAR D leaks rushing yards to RBs: x1.34 league; CAR D leaks carries to RBs: x1.19 league (worsening x1.08 last 4); CHI D leaks passing interceptions to QBs: x1.43 league (worsening x1.25 last 4); CHI D leaks rushing yards to RBs: x1.18 league

**Coordinators:** CAR OC Brad Idzik — continuity: data rules · CAR DC Ejiro Evero · CHI OC Press Taylor — NEW (pass_wr prior, SD widened) · CHI DC Dennis Allen

**Props SGP** — 4-leg 25.4% · fair +293 ✗ · 6-leg 11.1% · fair +799 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Caleb Williams 30+ pass att | 79% | -377 | ✗ 29 | `4-leg core`
| 2 | Rome Odunze 40+ rec yds | 61% | -158 | ✓ 52 | `4-leg core`
| 3 | Tetairoa McMillan 3+ receptions | 60% | -149 | ✓ 5 | `4-leg core`
| 4 | Bryce Young 25+ pass att | 58% | -139 | ✓ 37 | `4-leg core`
| 5 | Tetairoa McMillan 40+ rec yds | 58% | -137 | ✓ 75 | `+6`
| 6 | D'Andre Swift 14+ carries | 57% | -130 | ✓ 18 | `+6`

Legs 5/6 (expected 3.7)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| D'Andre Swift (CHI RB) | 56% | -125 | ✓ TD |  |
| Chuba Hubbard (CAR RB) | 33% | +206 | ✓ TD |  |

TD double (D'Andre Swift + Chuba Hubbard): 20.2% · fair +396 **CASHED**


### CLE@JAX — final 10-34
*O/U None · outdoor · grass*

**Injury report (as built):** CLE OFF · Teven Jenkins (G) — Out · Back · DNP; CLE OFF · Parker Brailsford (C) — Questionable · Thumb; JAX OFF · LeQuint Allen Jr. (RB) — Questionable · Hip; JAX OFF · Anton Harrison (T) — nan · DNP

**Defensive leaks:** JAX D leaks passing interceptions to QBs: x1.17 league (worsening x2.12 last 4); JAX D leaks receptions to RBs: x1.17 league (worsening x1.11 last 4)

**Coordinators:** JAX OC Grant Udinski — continuity: data rules · JAX DC Anthony Campanile · CLE OC Travis Switzer — NEW (run_heavy prior, SD widened) · CLE DC Mike Rutenberg — NEW (unit trends less reliable)

**Props SGP** — 4-leg 26.1% · fair +283 ✗ · 6-leg —  · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Brian Thomas Jr. 40+ rec yds | 62% | -162 | ✓ 40 | `4-leg core`
| 2 | Travis Hunter 40+ rec yds | 59% | -144 | ✗ 8 | `4-leg core`
| 3 | Trevor Lawrence 30+ pass att | 57% | -132 | ✗ 23 | `4-leg core`
| 4 | Trevor Lawrence 250+ pass yds | 56% | -127 | ✗ 245 | `4-leg core`
| 5 | Brian Thomas Jr. 3+ receptions | 56% | -127 | ✓ 3 | `+6`

Legs 2/5 (expected 2.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Brian Thomas Jr. (JAX WR) | 24% | +320 | ✗ no TD |  |

### DAL@NYG — final 20-28
*O/U None · outdoor · turf*

**Injury report (as built):** DAL OFF · Malik Davis (RB) — Out · Hip; DAL OFF · Luke Schoonmaker (TE) — nan · DNP; NYG OFF · Malik Nabers (WR) — Questionable · Knee

**Defensive leaks:** NYG D leaks rushing yards to RBs: x1.20 league; NYG D leaks receptions to RBs: x1.08 league; DAL D leaks receiving yards to RBs: x1.28 league; DAL D leaks receiving yards to WRs: x1.14 league

**Coordinators:** NYG OC Matt Nagy — NEW (pass_wr prior, SD widened) · NYG DC Dennard Wilson — NEW (unit trends less reliable) · DAL OC Klayton Adams — continuity: data rules · DAL DC Christian Parker — NEW (unit trends less reliable)

**Props SGP** — 4-leg 14.3% · fair +601 ✗ · 6-leg 6.2% · fair +1520 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Javonte Williams 60+ rush yds | 63% | -168 | ✗ 41 | `4-leg core`
| 2 | Javonte Williams 14+ carries | 62% | -160 | ✗ 12 | `4-leg core`
| 3 | Dak Prescott 225+ pass yds | 59% | -141 | ✗ 175 | `4-leg core`
| 4 | Malik Nabers 70+ rec yds | 57% | -134 | ✗ 69 | `4-leg core`
| 5 | Dak Prescott 30+ pass att | 57% | -134 | ✓ 34 | `+6`
| 6 | CeeDee Lamb 70+ rec yds | 57% | -134 | ✗ 44 | `+6`

Legs 1/6 (expected 3.5)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Malik Nabers (NYG WR) | 48% | +108 | ✗ no TD |  |
| Javonte Williams (DAL RB) | 46% | +120 | ✓ TD |  |

TD double (Malik Nabers + Javonte Williams): 24.1% · fair +315 ✗


### DEN@KC — final 10-31
*O/U None · outdoor · grass*

**Injury report (as built):** KC DEF · Chamarri Conner (S) — nan · DNP; KC OFF · Josh Simmons (T) — nan · DNP

**Defensive leaks:** KC D leaks receiving yards to TEs: x1.12 league; DEN D leaks attempts to QBs: x1.09 league

**Coordinators:** KC OC Eric Bieniemy — NEW (pass_wr prior, SD widened) · KC DC Steve Spagnuolo · DEN OC Davis Webb — NEW (balanced prior, SD widened) · DEN DC Vance Joseph

**Props SGP** — 4-leg 43.6% · fair +130 ✗ · 6-leg —  · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Jaylen Waddle 3+ receptions | 66% | -191 | ✗ 1 | `4-leg core`
| 2 | Jaylen Waddle 40+ rec yds | 56% | -127 | ✗ 2 | `4-leg core`

Legs 0/2 (expected 1.2)


### GB@MIN — final 22-39
*O/U None · indoor · turf*

**Injury report (as built):** GB DEF · Warren Brinson (DT) — Out · Calf · DNP; GB OFF · Aaron Banks (G) — Questionable · Knee; GB OFF · Zach Bako-Bewele (T) — Questionable · Knee; GB DEF · Ty'Ron Hopper (LB) — Questionable · Achilles; MIN OFF · Christian Darrisaw (T) — nan · DNP

**Defensive leaks:** MIN D leaks passing interceptions to QBs: x1.34 league; GB D leaks receptions to RBs: x1.14 league

**Coordinators:** MIN OC Wes Phillips — continuity: data rules · MIN DC Brian Flores · GB OC Adam Stenavich — continuity: data rules · GB DC Jonathan Gannon — NEW (unit trends less reliable)

**Props SGP** — 4-leg 21.3% · fair +368 ✗ · 6-leg —  · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Justin Jefferson 4+ receptions | 65% | -186 | ✓ 8 | `4-leg core`
| 2 | Jayden Reed 30+ rec yds | 61% | -154 | ✗ 20 | `4-leg core`
| 3 | Jordan Addison 30+ rec yds | 56% | -129 | ✗ 0 | `4-leg core`
| 4 | Justin Jefferson 50+ rec yds | 52% | -110 | ✓ 92 | `4-leg core`

Legs 2/4 (expected 2.3)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Jordan Addison (MIN WR) | 26% | +292 | ✗ no TD |  |
| Justin Jefferson (MIN WR) | 15% | +562 | ✓ TD |  |

TD double (Jordan Addison + Justin Jefferson): 6.3% · fair +1490 ✗


### MIA@LV — final 13-27
*O/U None · indoor · grass*

**Injury report (as built):** LV OFF · Brock Bowers (TE) — Out · Knee · DNP

**Defensive leaks:** MIA D leaks receptions to TEs: x1.18 league (worsening x1.07 last 4); MIA D leaks receiving yards to TEs: x1.17 league

**Coordinators:** LV OC Andrew Janocko — NEW (run_heavy prior, SD widened) · LV DC Rob Leonard — NEW (unit trends less reliable) · MIA OC Bobby Slowik — NEW (pass_wr prior, SD widened) · MIA DC Sean Duggan — NEW (unit trends less reliable)

**Props SGP** — 4-leg 16.3% · fair +514 ✗ · 6-leg —  · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Ashton Jeanty 60+ rush yds | 59% | -143 | ✓ 102 | `4-leg core`
| 2 | De'Von Achane 14+ carries | 57% | -133 | ✗ 11 | `4-leg core`
| 3 | De'Von Achane 70+ rush yds | 56% | -125 | ✗ 36 | `4-leg core`
| 4 | Ashton Jeanty 18+ carries | 52% | -109 | ✓ 23 | `4-leg core`

Legs 2/4 (expected 2.2)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| De'Von Achane (MIA RB) | 40% | +152 | ✗ no TD |  |
| Ashton Jeanty (LV RB) | 38% | +167 | ✓ TD |  |

TD double (De'Von Achane + Ashton Jeanty): 17.0% · fair +488 ✗


### NE@SEA — final 10-13
*O/U None · outdoor · turf*

**Injury report (as built):** NE OFF · Ben Brown (C) — Out · Knee · DNP; NE OFF · TreVeyon Henderson (RB) — Out · Ankle · DNP; SEA DEF · Ty Okada (S) — Out · Hamstring · DNP; SEA OFF · Tory Horton (WR) — Questionable · Hamstring; SEA DEF · Nick Emmanwori (S) — Questionable · Ankle

**Defensive leaks:** SEA D leaks passing interceptions to QBs: x1.30 league; SEA D leaks receptions to RBs: x1.13 league (worsening x1.26 last 4)

**Coordinators:** SEA OC Brian Fleury — NEW (run_heavy prior, SD widened) · SEA DC Aden Durde · NE OC Josh McDaniels — continuity: data rules · NE DC Zak Kuhr — NEW (unit trends less reliable)

**Props SGP** — 4-leg — ✗ · 6-leg —  · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Hunter Henry 50+ rec yds | 55% | -123 | ✗ 26 | `4-leg core`

Legs 0/1 (expected 0.6)


### NO@DET — final 30-31
*O/U None · indoor · turf*

**Injury report (as built):** DET DEF · Christian Izien (S) — Questionable · Groin; NO DEF · Cameron Jordan (LB) — Out · Hamstring; NO OFF · Audric Estimé (RB) — Out · Thigh · DNP; NO OFF · Oscar Delp (TE) — Out · Hamstring · DNP; NO OFF · Alvin Kamara (RB) — Questionable · Knee

**Defensive leaks:** DET D leaks passing interceptions to QBs: x1.22 league; DET D leaks receiving yards to WRs: x1.18 league; NO D leaks rushing yards to RBs: x1.12 league; NO D leaks carries to RBs: x1.11 league

**Coordinators:** DET OC Drew Petzing — NEW (pass_te prior, SD widened) · DET DC Kelvin Sheppard · NO OC Doug Nussmeier — continuity: data rules · NO DC Brandon Staley

**Props SGP** — 4-leg 20.1% · fair +396 ✗ · 6-leg 11.4% · fair +780 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Jared Goff 35+ pass att | 67% | -204 | ✓ 39 | `4-leg core`
| 2 | Jared Goff 275+ pass yds | 67% | -202 | ✗ 206 | `4-leg core`
| 3 | Jahmyr Gibbs 12+ carries | 66% | -190 | ✓ 29 | `4-leg core`
| 4 | Amon-Ra St. Brown 80+ rec yds | 60% | -147 | ✗ 67 | `4-leg core`
| 5 | Jahmyr Gibbs 30+ rec yds | 57% | -132 | ✓ 30 | `+6`
| 6 | Amon-Ra St. Brown 7+ receptions | 54% | -119 | ✓ 10 | `+6`

Legs 4/6 (expected 3.7)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Jahmyr Gibbs (DET RB) | 64% | -179 | ✓ TD |  |
| Amon-Ra St. Brown (DET WR) | 41% | +144 | ✓ TD |  |

TD double (Jahmyr Gibbs + Amon-Ra St. Brown): 30.7% · fair +226 **CASHED**


### NYJ@TEN — final 23-10
*O/U None · outdoor · grass*

**Injury report (as built):** NYJ OFF · Kene Nwangwu (RB) — Doubtful · Back · DNP; NYJ DEF · D'Angelo Ponds (CB) — Doubtful · Calf; NYJ OFF · Tim Patrick (WR) — Out · Groin · DNP; NYJ DEF · Joseph Ossai (DE) — Out · Foot · DNP; TEN DEF · Cedric Gray (LB) — Out · Concussion · DNP

**Defensive leaks:** NYJ D leaks carries to RBs: x1.14 league; NYJ D leaks rushing yards to RBs: x1.10 league

**Coordinators:** TEN OC Brian Daboll — NEW (pass_wr prior, SD widened) · TEN DC Gus Bradley — NEW (unit trends less reliable) · NYJ OC Frank Reich — NEW (balanced prior, SD widened) · NYJ DC Brian Duker — NEW (unit trends less reliable)

**Props SGP** — 4-leg 16.2% · fair +518 ✗ · 6-leg 8.7% · fair +1045 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Garrett Wilson 5+ receptions | 64% | -180 | ✓ 6 | `4-leg core`
| 2 | Garrett Wilson 50+ rec yds | 63% | -167 | ✓ 79 | `4-leg core`
| 3 | Breece Hall 40+ rush yds | 61% | -158 | ✓ 102 | `4-leg core`
| 4 | Breece Hall 20+ rec yds | 57% | -131 | ✗ 16 | `4-leg core`
| 5 | Calvin Ridley 30+ rec yds | 56% | -128 | – DNP | `+6`
| 6 | Cam Ward 30+ pass att | 55% | -120 | ✓ 32 | `+6`

Legs 4/5 (expected 3.6)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Garrett Wilson (NYJ WR) | 43% | +133 | ✗ no TD |  |
| Breece Hall (NYJ RB) | 26% | +279 | ✓ TD |  |

TD double (Garrett Wilson + Breece Hall): 15.2% · fair +560 ✗


### TB@CIN — final 27-33
*O/U None · outdoor · turf*

**Injury report (as built):** CIN DEF · Shemar Stewart (DE) — Doubtful · Knee · DNP; CIN DEF · Dexter Lawrence (DT) — nan · DNP; CIN OFF · Ja'Marr Chase (WR) — nan · DNP; TB OFF · Justin Skule (T) — Doubtful · Oblique; TB OFF · Sean Tucker (RB) — Doubtful · Hamstring; TB OFF · Jalen McMillan (WR) — Doubtful · Knee; TB DEF · Christian Rozeboom (LB) — Questionable · Foot

**Defensive leaks:** CIN D leaks receiving yards to TEs: x1.44 league; CIN D leaks receptions to TEs: x1.29 league; TB D leaks receiving yards to RBs: x1.41 league; TB D leaks receiving yards to TEs: x1.19 league (worsening x1.34 last 4)

**Coordinators:** CIN OC Dan Pitcher — continuity: data rules · CIN DC Al Golden · TB OC Zac Robinson — NEW (pass_wr prior, SD widened) · TB DC Todd Bowles

**Props SGP** — 4-leg 20.7% · fair +383 ✗ · 6-leg 11.2% · fair +794 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Baker Mayfield o0.5 INT o0.5 | 68% | -218 | ✗ 0 INT | `4-leg core`
| 2 | Chase Brown 20+ rec yds | 66% | -196 | ✓ 22 | `4-leg core`
| 3 | Chase Brown 12+ carries | 66% | -192 | ✓ 16 | `4-leg core`
| 4 | Ja'Marr Chase 8+ receptions | 63% | -168 | ✗ 2 | `4-leg core`
| 5 | Ja'Marr Chase 90+ rec yds | 58% | -141 | ✗ 12 | `+6`
| 6 | Tee Higgins 60+ rec yds | 54% | -119 | ✗ 59 | `+6`

Legs 2/6 (expected 3.8)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Chase Brown (CIN RB) | 64% | -176 | ✓ TD |  |
| Tee Higgins (CIN WR) | 58% | -137 | ✗ no TD |  |

TD double (Chase Brown + Tee Higgins): 41.5% · fair +141 ✗


### WAS@PHI — final 22-24
*O/U None · outdoor · grass*

**Injury report (as built):** PHI DEF · Jonathan Greenard (LB) — Out · Pectoral; PHI OFF · Eli Stowers (TE) — Questionable · Hamstring

**Defensive leaks:** WAS D leaks rushing yards to RBs: x1.21 league (worsening x1.12 last 4); WAS D leaks carries to RBs: x1.10 league (worsening x1.06 last 4)

**Coordinators:** PHI OC Sean Mannion — NEW (run_heavy prior, SD widened) · PHI DC Vic Fangio · WAS OC David Blough — NEW (balanced prior, SD widened) · WAS DC Daronte Jones — NEW (unit trends less reliable)

**Props SGP** — 4-leg 12.1% · fair +726 ✗ · 6-leg —  · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Dallas Goedert 3+ receptions | 60% | -153 | ✓ 4 | `4-leg core`
| 2 | Saquon Barkley 20+ carries | 59% | -144 | ✗ 15 | `4-leg core`
| 3 | Terry McLaurin 50+ rec yds | 57% | -134 | ✗ 14 | `4-leg core`
| 4 | Saquon Barkley 80+ rush yds | 54% | -115 | ✓ 83 | `4-leg core`
| 5 | Dallas Goedert 30+ rec yds | 53% | -112 | ✓ 77 | `+6`

Legs 3/5 (expected 2.8)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Saquon Barkley (PHI RB) | 46% | +116 | ✗ no TD |  |
| Dallas Goedert (PHI TE) | 38% | +161 | ✓ TD |  |

TD double (Saquon Barkley + Dallas Goedert): 22.3% · fair +348 ✗


### Cross-game combos — Week 1 — Sunday Sept 13 2026 (first full slate)

**4-leg** — 29.4% · fair +240 — 2/4 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | CHI@CAR | Caleb Williams 30+ pass att | 79% | ✗ 29 |
| 2 | BAL@IND | Derrick Henry 80+ rush yds | 77% | ✓ 144 |
| 3 | ARI@LAC | Justin Herbert o0.5 INT o0.5 | 70% | ✓ 1 INT |
| 4 | TB@CIN | Baker Mayfield o0.5 INT o0.5 | 68% | ✗ 0 INT |

**6-leg** — 14.9% · fair +570 — 3/6 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | CHI@CAR | Caleb Williams 30+ pass att | 79% | ✗ 29 |
| 2 | BAL@IND | Derrick Henry 80+ rush yds | 77% | ✓ 144 |
| 3 | ARI@LAC | Justin Herbert o0.5 INT o0.5 | 70% | ✓ 1 INT |
| 4 | TB@CIN | Baker Mayfield o0.5 INT o0.5 | 68% | ✗ 0 INT |
| 5 | NO@DET | Jared Goff 35+ pass att | 67% | ✓ 39 |
| 6 | NO@DET | Jared Goff 275+ pass yds | 67% | ✗ 206 |

**8-leg** — 7.1% · fair +1306 — 5/8 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | CHI@CAR | Caleb Williams 30+ pass att | 79% | ✗ 29 |
| 2 | BAL@IND | Derrick Henry 80+ rush yds | 77% | ✓ 144 |
| 3 | ARI@LAC | Justin Herbert o0.5 INT o0.5 | 70% | ✓ 1 INT |
| 4 | TB@CIN | Baker Mayfield o0.5 INT o0.5 | 68% | ✗ 0 INT |
| 5 | NO@DET | Jared Goff 35+ pass att | 67% | ✓ 39 |
| 6 | NO@DET | Jared Goff 275+ pass yds | 67% | ✗ 206 |
| 7 | BAL@IND | Jonathan Taylor 18+ carries | 66% | ✓ 19 |
| 8 | TB@CIN | Chase Brown 20+ rec yds | 66% | ✓ 22 |

**10-leg** — 3.4% · fair +2846 — 7/10 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | CHI@CAR | Caleb Williams 30+ pass att | 79% | ✗ 29 |
| 2 | BAL@IND | Derrick Henry 80+ rush yds | 77% | ✓ 144 |
| 3 | ARI@LAC | Justin Herbert o0.5 INT o0.5 | 70% | ✓ 1 INT |
| 4 | TB@CIN | Baker Mayfield o0.5 INT o0.5 | 68% | ✗ 0 INT |
| 5 | NO@DET | Jared Goff 35+ pass att | 67% | ✓ 39 |
| 6 | NO@DET | Jared Goff 275+ pass yds | 67% | ✗ 206 |
| 7 | BAL@IND | Jonathan Taylor 18+ carries | 66% | ✓ 19 |
| 8 | TB@CIN | Chase Brown 20+ rec yds | 66% | ✓ 22 |
| 9 | ARI@LAC | Ladd McConkey 3+ receptions | 66% | ✓ 5 |
| 10 | BUF@HOU | Josh Allen 25+ pass att | 66% | ✓ 29 |

**12-leg** — 1.4% · fair +7079 — 9/12 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | CHI@CAR | Caleb Williams 30+ pass att | 79% | ✗ 29 |
| 2 | BAL@IND | Derrick Henry 80+ rush yds | 77% | ✓ 144 |
| 3 | ARI@LAC | Justin Herbert o0.5 INT o0.5 | 70% | ✓ 1 INT |
| 4 | TB@CIN | Baker Mayfield o0.5 INT o0.5 | 68% | ✗ 0 INT |
| 5 | NO@DET | Jared Goff 35+ pass att | 67% | ✓ 39 |
| 6 | NO@DET | Jared Goff 275+ pass yds | 67% | ✗ 206 |
| 7 | BAL@IND | Jonathan Taylor 18+ carries | 66% | ✓ 19 |
| 8 | TB@CIN | Chase Brown 20+ rec yds | 66% | ✓ 22 |
| 9 | ARI@LAC | Ladd McConkey 3+ receptions | 66% | ✓ 5 |
| 10 | BUF@HOU | Josh Allen 25+ pass att | 66% | ✓ 29 |
| 11 | ATL@PIT | Bijan Robinson 16+ carries | 65% | ✓ 21 |
| 12 | GB@MIN | Justin Jefferson 4+ receptions | 65% | ✓ 8 |


### ATD board (top 12) — Week 1 — Sunday Sept 13 2026 (first full slate)

| # | Game | Player | Model | Fair | Result |
|---|---|---|---|---|---|
| 1 | BAL@IND | Derrick Henry (RB) | 70% | -233 | ✓ TD |
| 2 | NO@DET | Jahmyr Gibbs (RB) | 64% | -179 | ✓ TD |
| 3 | TB@CIN | Chase Brown (RB) | 64% | -176 | ✓ TD |
| 4 | BUF@HOU | James Cook (RB) | 59% | -143 | ✗ no TD |
| 5 | TB@CIN | Tee Higgins (WR) | 58% | -137 | ✗ no TD |
| 6 | CHI@CAR | D'Andre Swift (RB) | 56% | -125 | ✓ TD |
| 7 | ATL@PIT | Bijan Robinson (RB) | 51% | -105 | ✓ TD |
| 8 | BAL@IND | Jonathan Taylor (RB) | 50% | +102 | ✓ TD |
| 9 | TB@CIN | Ja'Marr Chase (WR) | 49% | +103 | ✗ no TD |
| 10 | DAL@NYG | Malik Nabers (WR) | 48% | +108 | ✗ no TD |
| 11 | WAS@PHI | Saquon Barkley (RB) | 46% | +116 | ✗ no TD |
| 12 | DAL@NYG | Javonte Williams (RB) | 46% | +120 | ✓ TD |

Board: top-16 7/12 · top-8 6/8 · chalk triple 3/3


### Scorecard — Week 1 — Sunday Sept 13 2026 (first full slate)

**Legs 40/71 = 56% actual vs 61% expected · SGP4 1/15 · SGP6 0/15 · SGP8 0/15**

| Game | Final | Legs | SGP4 | SGP6 | SGP8 |
|---|---|---|---|---|---|
| BAL@IND | 41-23 | 5/6 | ✓ | ✗ | ✗ |
| CHI@CAR | 59-37 | 5/6 | ✗ | ✗ | ✗ |
| ARI@LAC | 26-14 | 4/6 | ✗ | ✗ | ✗ |
| BUF@HOU | 36-31 | 4/6 | ✗ | ✗ | ✗ |
| NO@DET | 30-31 | 4/6 | ✗ | ✗ | ✗ |
| NYJ@TEN | 23-10 | 4/5 | ✗ | ✗ | ✗ |
| WAS@PHI | 22-24 | 3/5 | ✗ | ✗ | ✗ |
| ATL@PIT | 13-20 | 2/3 | ✗ | ✗ | ✗ |
| CLE@JAX | 10-34 | 2/5 | ✗ | ✗ | ✗ |
| GB@MIN | 22-39 | 2/4 | ✗ | ✗ | ✗ |
| MIA@LV | 13-27 | 2/4 | ✗ | ✗ | ✗ |
| TB@CIN | 27-33 | 2/6 | ✗ | ✗ | ✗ |
| DAL@NYG | 20-28 | 1/6 | ✗ | ✗ | ✗ |
| DEN@KC | 10-31 | 0/2 | ✗ | ✗ | ✗ |
| NE@SEA | 10-13 | 0/1 | ✗ | ✗ | ✗ |


## Week 2 — Sunday Sept 20 2026 (PDF only)

*Engine v1.5.* Shipped as NFL-Week2-Full-Slate-Pack.pdf, NFL-Week2-Cross-Combos.pdf, NFL-Week2-ATD-Slip.pdf and NFL-Week2-Superstar-Board.pdf (a "semi-aggressive, near-the-line" board of stars only, built at the user's request). The slate JSON for this week was not retained in any engine snapshot, so legs are not reproduced here; the ATD board was the last built on the recency model before v2. Single-game cards that week: DEN-KC-MNF-Model-Pack.pdf (Walker vs Harvey TD debate; Walker card + final board), MNF-Walker-Card-and-Final-Board.pdf.


## Week 3 — Sunday Sept 27 2026 (shipped v1.7)

*Engine v1.7.* Shipped build. Report card (Week3-Report-Card.pdf): 69% vs 78% expected, SGP4 4/14, SGP6 1/14, SGP8 0/14; the 80–85% band hit 52%. Root cause was the season-baseline bug fixed in v1.8. ATD v2's chalk triple (Henry · McCaffrey · Gibbs) cashed at +274 and the board top-8 went 6/8. One thin-role leg (Jadarian Price 10+ carries) killed all five combos.


### CAR@CLE — final 18-21
*O/U 42.5 · spread -1.5 · outdoor · grass · 13:00 ET*

**Injury report (as built):** CAR DEF · Nick Scott (S) — Out · Rib · DNP; CAR DEF · Devin Lloyd (LB) — Out · Calf · DNP; CAR DEF · Claudin Cherelus (LB) — Out · Shoulder · DNP; CAR OFF · Xavier Legette (WR) — Questionable · Knee; CAR OFF · Jalen Coker (WR) — Questionable · Ankle; CLE OFF · Teven Jenkins (G) — Out · Back · DNP; CLE DEF · Grant Delpit (S) — Questionable · Shoulder; CLE DEF · Tyson Campbell (CB) — Questionable · Ankle

**Defensive leaks:** CAR D leaks rushing yards to RBs: x1.37 (worsening x1.34 L4); CAR D leaks carries to RBs: x1.19 (worsening x1.06 L4)

**Coordinators:** CAR OC Brad Idzik — continuity · measured pass 63% | DC Ejiro Evero (two_high_shell) · CLE OC Travis Switzer — NEW (run_heavy) · measured pass 54% | DC Mike Rutenberg (multiple)

**Props SGP** — 4-leg 38.5% · fair +160 **CASHED** · 6-leg 26.0% · fair +285 ✗ · 8-leg 20.9% · fair +379 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Darren Waller 2+ receptions | 78% | -353 | ✓ 5 | `4-leg core`
| 2 | Chuba Hubbard 20+ rush yds | 77% | -340 | ✓ 82 | `4-leg core`
| 3 | Denzel Boston 2+ receptions | 79% | -377 | ✓ 2 | `4-leg core`
| 4 | Bryce Young 175+ pass yds | 76% | -308 | ✓ 291 | `4-leg core`
| 5 | Quinshon Judkins 20+ rush yds | 75% | -306 | ✓ 70 | `+6`
| 6 | Jalen Coker 50+ rec yds (Q) | 75% | -299 | ✗ 18 | `+6`
| 7 | Tetairoa McMillan 50+ rec yds | 71% | -247 | ✗ 17 | `+8`
| 8 | Bryce Young 25+ pass att | 84% | -543 | ✓ 48 | `+8`

Legs 6/8 (expected 6.2)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Quinshon Judkins (CLE RB) | 41% | +142 | ✗ no TD | share 20% · team 2.3 TD · RZ-D 0.99 · pos-D 1.16 |
| Chuba Hubbard (CAR RB) | 35% | +187 | ✗ no TD | share 18% · team 2.46 TD · RZ-D 1.01 · pos-D 0.95 |
| Tetairoa McMillan (CAR WR) | 28% | +258 | ✗ no TD | share 12% · team 2.46 TD · RZ-D 1.01 · pos-D 1.12 |

TD double (Quinshon Judkins + Chuba Hubbard): 16.4% · fair +510 ✗


### CIN@PIT — final 27-30
*O/U 42.5 · spread -3.5 · outdoor · grass · 13:00 ET*

**Injury report (as built):** CIN DEF · B.J. Hill (DT) — Doubtful · Achilles · DNP; CIN OFF · Andrei Iosivas (WR) — Out · Thumb · DNP; CIN DEF · Dexter Lawrence (DT) — nan · DNP; PIT OFF · Rico Dowdle (RB) — Out · Toe · DNP; PIT OFF · Gennings Dunker (G) — Out · Knee · DNP; PIT DEF · Jamel Dean (CB) — Questionable · Ankle; PIT OFF · Michael Pittman (WR) — Questionable · Foot; PIT OFF · Jaylen Warren (RB) — Questionable · Shoulder

**Defensive leaks:** PIT D leaks passing interceptions to QBs: x1.39 (worsening x1.54 L4); PIT D leaks receptions to TEs: x1.16; PIT D leaks receiving yards to TEs: x1.15; CIN D leaks receiving yards to TEs: x1.47 (worsening x1.30 L4)

**Coordinators:** CIN OC Dan Pitcher — continuity · measured pass 57% | DC Al Golden (disguise_zone) · PIT OC Brian Angelichio — NEW (pass_te) · measured pass 65% | DC Patrick Graham (multiple)

**Props SGP** — 4-leg 41.4% · fair +141 ✗ · 6-leg 29.5% · fair +238 ✗ · 8-leg 23.5% · fair +325 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Jaylen Warren 20+ rush yds (Q) | 78% | -359 | ✓ 127 | `4-leg core`
| 2 | Chase Brown 3+ receptions | 78% | -360 | ✗ 2 | `4-leg core`
| 3 | Michael Pittman 2+ receptions (Q) | 78% | -347 | ✓ 2 | `4-leg core`
| 4 | Mike Gesicki 30+ rec yds | 78% | -347 | ✓ 37 | `4-leg core`
| 5 | Aaron Rodgers 200+ pass yds | 76% | -313 | ✓ 292 | `+6`
| 6 | Tee Higgins 50+ rec yds | 76% | -309 | ✓ 90 | `+6`
| 7 | Joe Burrow 30+ pass att | 72% | -263 | ✓ 37 | `+8`
| 8 | Aaron Rodgers 35+ pass att | 81% | -423 | ✗ 34 | `+8`

Legs 6/8 (expected 6.2)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Chase Brown (CIN RB) | 33% | +206 | ✗ no TD | share 21% · team 2.58 TD · RZ-D 0.9 · pos-D 0.77 |
| Jaylen Warren (PIT RB) | 32% | +209 | ✗ no TD | share 16% · team 2.18 TD · RZ-D 1.02 · pos-D 1.13 |
| Ja'Marr Chase (CIN WR) | 31% | +227 | ✓ TD | share 15% · team 2.58 TD · RZ-D 0.9 · pos-D 1.0 |

TD double (Chase Brown + Jaylen Warren): 12.4% · fair +706 ✗


### HOU@IND — final 17-19
*O/U 42.5 · spread -1.5 · outdoor · turf · 13:00 ET*

**Injury report (as built):** HOU DEF · Jadeveon Clowney (DE) — Out · Knee · DNP; HOU DEF · M.J. Stewart (S) — Out · Knee; HOU OFF · Nico Collins (WR) — Out · Hamstring · DNP; HOU DEF · Jacob Hummel (LB) — Out · Groin · DNP; HOU OFF · Ed Ingram (G) — Out · Groin · DNP; HOU OFF · Trent Brown (T) — Questionable · Knee; HOU OFF · Dalton Schultz (TE) — nan · DNP; HOU DEF · Logan Hall (DE) — nan · DNP

**Defensive leaks:** IND D leaks receiving yards to TEs: x1.25 (worsening x1.28 L4); IND D leaks passing interceptions to QBs: x1.19; IND D leaks receptions to TEs: x1.17 (worsening x1.24 L4); HOU D leaks passing interceptions to QBs: x1.47

**Coordinators:** HOU OC Nick Caley — continuity · measured pass 65% | DC Matt Burke (four_man_rush) · IND OC Jim Bob Cooter — continuity · measured pass 54% | DC Lou Anarumo (disguise_zone)

**Props SGP** — 4-leg 41.3% · fair +142 ✗ · 6-leg 33.4% · fair +200 ✗ · 8-leg 27.0% · fair +271 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Jonathan Taylor 2+ receptions | 78% | -349 | ✓ 2 | `4-leg core`
| 2 | Josh Downs 3+ receptions | 78% | -362 | ✓ 5 | `4-leg core`
| 3 | Dalton Schultz 50+ rec yds | 78% | -363 | ✗ 30 | `4-leg core`
| 4 | David Montgomery 20+ rush yds | 77% | -334 | ✓ 33 | `4-leg core`
| 5 | C.J. Stroud 200+ pass yds | 82% | -440 | ✗ 167 | `+6`
| 6 | Daniel Jones 20+ pass att | 84% | -543 | ✓ 36 | `+6`
| 7 | Josh Downs 30+ rec yds | 76% | -325 | ✓ 77 | `+8`
| 8 | C.J. Stroud 30+ pass att | 82% | -472 | ✗ 27 | `+8`

Legs 5/8 (expected 6.4)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Jonathan Taylor (IND RB) | 45% | +121 | ✗ no TD | share 28% · team 2.3 TD · RZ-D 1.01 · pos-D 0.92 |
| David Montgomery (HOU RB) | 39% | +159 | ✗ no TD | share 19% · team 2.46 TD · RZ-D 0.98 · pos-D 1.04 |
| Woody Marks (HOU RB) | 29% | +240 | ✓ TD | share 14% · team 2.46 TD · RZ-D 0.98 · pos-D 1.04 |

TD double (Jonathan Taylor + David Montgomery): 19.7% · fair +409 ✗


### KC@MIA — final 24-10
*O/U 45.5 · spread -10.0 · outdoor · grass · 13:00 ET*

**Injury report (as built):** KC DEF · Chamarri Conner (S) — Doubtful · Knee; KC OFF · Josh Simmons (T) — Out · Back · DNP; MIA OFF · Jaylen Wright (RB) — Doubtful · Stinger · DNP; MIA DEF · Rob Beal Jr. (DE) — Out · Hamstring · DNP; MIA OFF · Caleb Douglas (WR) — Out · Ankle · DNP; MIA OFF · Ryan Miller (WR) — Questionable · Hip; MIA DEF · Julius Brents (CB) — Questionable · Knee

**Defensive leaks:** MIA D leaks receiving yards to TEs: x1.17; MIA D leaks receptions to TEs: x1.17; MIA D leaks receiving yards to RBs: x1.10 (worsening x1.27 L4); KC D leaks receiving yards to TEs: x1.10

**Coordinators:** KC OC Eric Bieniemy — NEW (pass_wr) · measured pass 52% | DC Steve Spagnuolo (blitz_heavy) · MIA OC Bobby Slowik — NEW (pass_wr) · measured pass 52% | DC Sean Duggan (multiple)

**Props SGP** — 4-leg 46.3% · fair +116 ✗ · 6-leg 30.7% · fair +226 ✗ · 8-leg 22.3% · fair +349 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Kenneth Walker III 2+ receptions | 78% | -350 | ✓ 2 | `4-leg core`
| 2 | Travis Kelce 40+ rec yds | 77% | -326 | ✓ 59 | `4-leg core`
| 3 | De'Von Achane 2+ receptions | 80% | -393 | ✗ 0 | `4-leg core`
| 4 | Rashee Rice 30+ rec yds | 76% | -320 | ✓ 88 | `4-leg core`
| 5 | Patrick Mahomes 200+ pass yds | 81% | -415 | ✓ 246 | `+6`
| 6 | Kenneth Walker III 100+ rush yds | 79% | -373 | ✗ 70 | `+6`
| 7 | Patrick Mahomes 30+ pass att | 82% | -445 | ✗ 24 | `+8`
| 8 | De'Von Achane 50+ rush yds | 72% | -258 | ✗ 17 | `+8`

Legs 4/8 (expected 6.2)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Kenneth Walker III (KC RB) | 47% | +113 | ✓ TD | share 17% · team 3.11 TD · RZ-D 1.15 · pos-D 1.1 |
| Rashee Rice (KC WR) | 39% | +156 | ✗ no TD | share 14% · team 3.11 TD · RZ-D 1.15 · pos-D 1.03 |
| De'Von Achane (MIA RB) | 33% | +201 | ✗ no TD | share 23% · team 1.99 TD · RZ-D 0.95 · pos-D 0.92 |

TD double (Kenneth Walker III + Rashee Rice): 22.9% · fair +336 ✗


### LAC@BUF — final 16-24
*O/U 49.5 · spread +7.0 · outdoor · turf · 13:00 ET*

**Injury report (as built):** BUF DEF · Jordan Hancock (CB) — Out · Hamstring · DNP; BUF DEF · T.J. Sanders (DE) — Out · Illness · DNP; BUF OFF · DJ Moore (WR) — Questionable · Shoulder; BUF DEF · Ed Oliver (DT) — Questionable · Hip; BUF OFF · Keon Coleman (WR) — Questionable · Ankle; BUF OFF · Ar'maj Reed-Adams (G) — Questionable · Elbow; BUF DEF · Terrel Bernard (LB) — nan · DNP; LAC DEF · Dalvin Tomlinson (DT) — Out · Hamstring · DNP

**Defensive leaks:** BUF D leaks receiving yards to RBs: x1.12 (worsening x1.30 L4); BUF D leaks passing interceptions to QBs: x1.11; BUF D leaks receptions to RBs: x1.11 (worsening x1.17 L4); LAC D leaks passing interceptions to QBs: x1.39

**Coordinators:** LAC OC Mike McDaniel — NEW (pass_rb) · measured pass 50% | DC Chris O'Leary (two_high_shell) · BUF OC Pete Carmichael Jr. — NEW (balanced) · measured pass 51% | DC Jim Leonhard (disguise_zone)

**Props SGP** — 4-leg 42.4% · fair +136 ✗ · 6-leg 33.7% · fair +197 ✗ · 8-leg 21.6% · fair +362 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Justin Herbert o0.5 INT o0.5 | 77% | -333 | ✓ 1 INT | `4-leg core`
| 2 | Keon Coleman 2+ receptions (Q) | 79% | -385 | ✗ 1 | `4-leg core`
| 3 | Dalton Kincaid 50+ rec yds | 76% | -325 | ✗ 38 | `4-leg core`
| 4 | Tre Harris 20+ rec yds | 74% | -292 | ✓ 76 | `4-leg core`
| 5 | Josh Allen 200+ pass yds | 74% | -289 | ✓ 204 | `+6`
| 6 | Khalil Shakir 2+ receptions | 82% | -452 | ✗ 1 | `+6`
| 7 | James Cook 10+ carries | 82% | -467 | ✓ 24 | `+8`
| 8 | Omarion Hampton 60+ rush yds | 73% | -269 | ✗ 56 | `+8`

Legs 4/8 (expected 6.2)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Omarion Hampton (LAC RB) | 42% | +139 | ✗ no TD | share 18% · team 2.38 TD · RZ-D 1.08 · pos-D 1.22 |
| Josh Allen (BUF QB) | 40% | +151 | ✓ TD | share 17% · team 3.16 TD · RZ-D 0.81 · pos-D 1.02 |
| James Cook (BUF RB) | 40% | +152 | ✓ TD | share 20% · team 3.16 TD · RZ-D 0.81 · pos-D 0.89 |

TD double (Omarion Hampton + Josh Allen): 18.8% · fair +431 ✗


### NE@JAX — final 6-35
*O/U 46.5 · spread +3.0 · outdoor · grass · 13:00 ET*

**Injury report (as built):** JAX DEF · Albert Regis (DT) — Doubtful · Elbow; NE DEF · Dre'Mont Jones (LB) — Out · Shoulder · DNP; NE DEF · Brenden Schooler (S) — Out · Back; NE DEF · Quintayvious Hutchins (LB) — Out · Knee · DNP; NE DEF · Craig Woodson (S) — Questionable · Shoulder; NE OFF · Eli Raridon (TE) — Questionable · Thigh · DNP

**Defensive leaks:** JAX D leaks passing interceptions to QBs: x1.19 (worsening x1.20 L4); JAX D leaks receiving yards to RBs: x1.19 (worsening x1.19 L4); JAX D leaks receptions to RBs: x1.17

**Coordinators:** NE OC Josh McDaniels — continuity · measured pass 48% | DC Zak Kuhr (multiple) · JAX OC Grant Udinski — continuity · measured pass 48% | DC Anthony Campanile (pressure)

**Props SGP** — 4-leg 39.9% · fair +151 ✗ · 6-leg 29.9% · fair +234 ✗ · 8-leg 22.3% · fair +348 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Jakobi Meyers 20+ rec yds | 78% | -359 | ✓ 64 | `4-leg core`
| 2 | Brenton Strange 2+ receptions | 78% | -349 | ✓ 3 | `4-leg core`
| 3 | Brian Thomas Jr. 20+ rec yds | 79% | -370 | ✗ 8 | `4-leg core`
| 4 | Chris Rodriguez Jr. 20+ rush yds | 77% | -332 | ✓ 37 | `4-leg core`
| 5 | Rhamondre Stevenson 30+ rush yds | 77% | -331 | ✗ 22 | `+6`
| 6 | Trevor Lawrence 200+ pass yds | 81% | -428 | ✗ 182 | `+6`
| 7 | Drake Maye 25+ pass att | 81% | -431 | ✓ 25 | `+8`
| 8 | Parker Washington 4+ receptions | 73% | -271 | ✗ 3 | `+8`

Legs 4/8 (expected 6.2)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Chris Rodriguez Jr. (JAX RB) | 30% | +232 | ✓ TD | share 16% · team 2.77 TD · RZ-D 1.0 · pos-D 0.8 |
| Rhamondre Stevenson (NE RB) | 29% | +244 | ✗ no TD | share 17% · team 2.44 TD · RZ-D 0.96 · pos-D 0.86 |
| TreVeyon Henderson (NE RB) | 26% | +282 | ✗ no TD | share 15% · team 2.44 TD · RZ-D 0.96 · pos-D 0.86 |

TD double (Chris Rodriguez Jr. + Rhamondre Stevenson): 10.5% · fair +854 ✗


### NYJ@DET — final 24-31
*O/U 48.5 · spread +6.5 · indoor · turf · 13:00 ET*

**Injury report (as built):** DET OFF · Ben Bartch (G) — Out · Foot · DNP; DET DEF · Thomas Harper (S) — Out · Ankle · DNP; NYJ OFF · Kene Nwangwu (RB) — Doubtful · Back · DNP; NYJ DEF · Minkah Fitzpatrick (S) — Out · Groin · DNP; NYJ DEF · Francisco Mauigoa (LB) — Out · Quadricep · DNP; NYJ OFF · Mason Taylor (TE) — Out · Thumb · DNP; NYJ DEF · Joseph Ossai (DE) — Questionable · Foot; NYJ OFF · Adonai Mitchell (WR) — Questionable · Finger

**Defensive leaks:** DET D leaks passing interceptions to QBs: x1.23 (worsening x1.16 L4); DET D leaks receiving yards to WRs: x1.20 (worsening x1.26 L4); DET D leaks receptions to WRs: x1.13 (worsening x1.16 L4); NYJ D leaks carries to RBs: x1.11

**Coordinators:** NYJ OC Frank Reich — NEW (balanced) · measured pass 50% | DC Brian Duker (multiple) · DET OC Drew Petzing — NEW (pass_te) · measured pass 59% | DC Kelvin Sheppard (pressure)

**Props SGP** — 4-leg 44.0% · fair +128 **CASHED** · 6-leg 33.8% · fair +196 ✗ · 8-leg 18.6% · fair +437 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Sam LaPorta 30+ rec yds | 78% | -349 | ✓ 44 | `4-leg core`
| 2 | Jameson Williams 2+ receptions | 77% | -342 | ✓ 4 | `4-leg core`
| 3 | Geno Smith 20+ pass att | 77% | -332 | ✓ 37 | `4-leg core`
| 4 | Garrett Wilson 40+ rec yds | 76% | -323 | ✓ 107 | `4-leg core`
| 5 | Jared Goff 250+ pass yds | 76% | -316 | ✓ 269 | `+6`
| 6 | Amon-Ra St. Brown 7+ receptions | 75% | -303 | ✗ 4 | `+6`
| 7 | Jahmyr Gibbs 40+ rush yds | 75% | -296 | ✓ 99 | `+8`
| 8 | Breece Hall 40+ rush yds | 75% | -293 | ✗ 32 | `+8`

Legs 6/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Jahmyr Gibbs (DET RB) | 63% | -172 | ✓ TD | share 22% · team 3.08 TD · RZ-D 1.16 · pos-D 1.37 |
| Amon-Ra St. Brown (DET WR) | 45% | +121 | ✓ TD | share 18% · team 3.08 TD · RZ-D 1.16 · pos-D 1.03 |
| Breece Hall (NYJ RB) | 35% | +189 | ✗ no TD | share 18% · team 2.35 TD · RZ-D 1.08 · pos-D 0.95 |

TD double (Jahmyr Gibbs + Amon-Ra St. Brown): 33.1% · fair +202 **CASHED**


### SEA@WAS — final 31-33
*O/U 40.5 · spread -7.5 · outdoor · grass · 13:00 ET*

**Injury report (as built):** SEA DEF · Julian Love (S) — Out · Calf · DNP; SEA DEF · Ty Okada (S) — Out · Hamstring · DNP; SEA DEF · Brandon Pili (DT) — Questionable · Concussion; WAS DEF · Frankie Luvu (LB) — Out · Groin · DNP; WAS OFF · Sam Cosmi (G) — Out · Concussion · DNP; WAS DEF · Nick Cross (S) — Out · Illness · DNP; WAS OFF · Chig Okonkwo (TE) — Out · Hamstring · DNP; WAS OFF · Jayden Daniels (QB) — Out · Elbow · DNP

**Defensive leaks:** WAS D leaks rushing yards to RBs: x1.18; WAS D leaks carries to RBs: x1.08; SEA D leaks passing interceptions to QBs: x1.39 (worsening x2.06 L4); SEA D leaks receptions to RBs: x1.15 (worsening x1.24 L4)

**Coordinators:** SEA OC Brian Fleury — NEW (run_heavy) · measured pass 45% | DC Aden Durde (four_man_rush) · WAS OC David Blough — NEW (balanced) · measured pass 52% | DC Daronte Jones (zone_cover3)

**Props SGP** — 4-leg 37.4% · fair +168 ✗ · 6-leg 29.0% · fair +245 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Jadarian Price 10+ carries | 78% | -355 | ✗ 5 | `4-leg core`
| 2 | Jacory Croskey-Merritt 10+ carries | 77% | -339 | ✓ 19 | `4-leg core`
| 3 | Stefon Diggs 3+ receptions | 76% | -318 | ✓ 4 | `4-leg core`
| 4 | Antonio Williams 20+ rec yds | 76% | -315 | ✗ 15 | `4-leg core`
| 5 | Rachaad White 2+ receptions | 82% | -452 | ✗ 1 | `+6`
| 6 | Jaxon Smith-Njigba 100+ rec yds | 82% | -456 | ✓ 128 | `+6`

Legs 3/6 (expected 4.7)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Jaxon Smith-Njigba (SEA WR) | 39% | +158 | ✓ TD | share 16% · team 2.69 TD · RZ-D 1.14 · pos-D 1.09 |
| Emanuel Wilson (SEA RB) | 20% | +390 | ✗ no TD | share 7% · team 2.69 TD · RZ-D 1.14 · pos-D 1.1 |

TD double (Jaxon Smith-Njigba + Emanuel Wilson): 11.3% · fair +787 ✗


### TEN@NYG — final 7-12
*O/U 37.5 · spread +2.5 · outdoor · turf · 13:00 ET*

**Injury report (as built):** NYG DEF · Brian Burns (LB) — Questionable · Ankle · DNP; NYG DEF · Deonte Banks (CB) — Questionable · Calf; NYG DEF · Tyler Nubin (S) — Questionable · Calf; NYG OFF · Jaxson Dart (QB) — nan · DNP; TEN DEF · Cordale Flott (CB) — Questionable · Quadricep; TEN OFF · Tyjae Spears (RB) — Questionable · Ankle

**Defensive leaks:** NYG D leaks rushing yards to RBs: x1.20

**Coordinators:** TEN OC Brian Daboll — NEW (pass_wr) · measured pass 55% | DC Gus Bradley (zone_cover3) · NYG OC Matt Nagy — NEW (pass_wr) · measured pass 51% | DC Dennard Wilson (pressure)

**Props SGP** — 4-leg 38.0% · fair +163 ✗ · 6-leg 24.6% · fair +306 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Calvin Ridley 20+ rec yds | 77% | -327 | ✗ 0 | `4-leg core`
| 2 | Tony Pollard 10+ carries | 76% | -325 | ✓ 17 | `4-leg core`
| 3 | Malik Nabers 2+ receptions | 80% | -399 | ✓ 5 | `4-leg core`
| 4 | Wan'Dale Robinson 3+ receptions | 76% | -315 | ✓ 7 | `4-leg core`
| 5 | Elic Ayomanor 20+ rec yds | 75% | -305 | ✗ 11 | `+6`
| 6 | Cam Skattebo 60+ rush yds | 72% | -251 | ✓ 60 | `+6`

Legs 4/6 (expected 4.6)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Cam Skattebo (NYG RB) | 38% | +167 | ✗ no TD | share 17% · team 2.24 TD · RZ-D 1.15 · pos-D 1.13 |
| Malik Nabers (NYG WR) | 32% | +212 | ✗ no TD | share 14% · team 2.24 TD · RZ-D 1.15 · pos-D 1.12 |
| Tony Pollard (TEN RB) | 32% | +213 | ✗ no TD | share 16% · team 1.96 TD · RZ-D 1.14 · pos-D 1.16 |

TD double (Cam Skattebo + Malik Nabers): 16.1% · fair +521 ✗


### ARI@SF — final 30-36
*O/U 47.5 · spread +7.5 · outdoor · grass · 16:05 ET*

**Injury report (as built):** ARI DEF · Dadrion Taylor-Demerson (S) — Out · Back · DNP; ARI DEF · Roy Lopez (DT) — Questionable · Groin; ARI DEF · Max Melton (CB) — Questionable · Toe; SF OFF · Demarcus Robinson (WR) — Out · Ankle · DNP; SF DEF · Nick Bosa (DE) — Out · Knee · DNP; SF DEF · James Thompson Jr. (DT) — Out · Ankle · DNP; SF DEF · Romello Height (DE) — Out · Hand · DNP; SF OFF · Mike Evans (WR) — Questionable · Hip

**Defensive leaks:** SF D leaks receptions to RBs: x1.21; SF D leaks receiving yards to RBs: x1.15; ARI D leaks rushing yards to RBs: x1.15

**Coordinators:** ARI OC Nathaniel Hackett — NEW (run_heavy) · measured pass 56% | DC Nick Rallis (blitz_heavy) · SF OC Klay Kubiak — continuity · measured pass 50% | DC Raheem Morris (zone_cover3)

**Props SGP** — 4-leg 41.0% · fair +144 ✗ · 6-leg 27.0% · fair +270 ✗ · 8-leg 19.9% · fair +404 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Tyler Allgeier 20+ rush yds | 78% | -348 | ✗ -1 | `4-leg core`
| 2 | Trey McBride 7+ receptions | 78% | -346 | ✓ 9 | `4-leg core`
| 3 | Mike Evans 3+ receptions (Q) | 79% | -371 | ✓ 3 | `4-leg core`
| 4 | Brock Purdy 25+ pass att | 77% | -333 | ✓ 27 | `4-leg core`
| 5 | Christian McCaffrey 10+ carries | 77% | -331 | ✓ 15 | `+6`
| 6 | George Kittle 40+ rec yds | 77% | -329 | ✓ 82 | `+6`
| 7 | Jacoby Brissett 20+ pass att | 76% | -320 | ✓ 52 | `+8`
| 8 | Trey McBride 50+ rec yds | 75% | -295 | ✓ 75 | `+8`

Legs 7/8 (expected 6.2)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Christian McCaffrey (SF RB) | 64% | -182 | ✓ TD | share 27% · team 3.08 TD · RZ-D 1.11 · pos-D 1.16 |
| George Kittle (SF TE) | 39% | +159 | ✓ TD | share 12% · team 3.08 TD · RZ-D 1.11 · pos-D 1.21 |
| Trey McBride (ARI TE) | 38% | +167 | ✗ no TD | share 20% · team 2.24 TD · RZ-D 0.93 · pos-D 1.09 |

TD double (Christian McCaffrey + George Kittle): 29.2% · fair +242 **CASHED**


### MIN@TB — final 23-16
*O/U 42.5 · spread -1.5 · outdoor · grass · 16:05 ET*

**Injury report (as built):** MIN OFF · Nick Samac (C) — Out · Knee · DNP; MIN OFF · Brett Thorson (P) — Out · Hamstring · DNP; MIN OFF · Christian Darrisaw (T) — nan · DNP; TB DEF · Rueben Bain Jr. (LB) — Out · Groin · DNP; TB DEF · Josiah Trotter (LB) — Out · Shoulder

**Defensive leaks:** TB D leaks receiving yards to RBs: x1.41; TB D leaks receiving yards to TEs: x1.22 (worsening x1.35 L4); TB D leaks receptions to RBs: x1.17 (worsening x1.42 L4); MIN D leaks passing interceptions to QBs: x1.35 (worsening x1.06 L4)

**Coordinators:** MIN OC Wes Phillips — continuity · measured pass 42% | DC Brian Flores (blitz_man) · TB OC Zac Robinson — NEW (pass_wr) · measured pass 58% | DC Todd Bowles (blitz_heavy)

**Props SGP** — 4-leg 40.4% · fair +147 **CASHED** · 6-leg 29.4% · fair +240 ✗ · 8-leg 23.7% · fair +322 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Bucky Irving 40+ rush yds | 78% | -364 | ✓ 46 | `4-leg core`
| 2 | Chris Godwin Jr. 2+ receptions | 78% | -362 | ✓ 3 | `4-leg core`
| 3 | Emeka Egbuka 2+ receptions | 78% | -365 | ✓ 5 | `4-leg core`
| 4 | Aaron Jones 15+ carries | 78% | -365 | ✓ 17 | `4-leg core`
| 5 | Cade Otton 20+ rec yds | 79% | -382 | ✓ 56 | `+6`
| 6 | T.J. Hockenson 20+ rec yds | 79% | -382 | ✗ 11 | `+6`
| 7 | Baker Mayfield 175+ pass yds | 75% | -300 | ✓ 217 | `+8`
| 8 | Baker Mayfield 25+ pass att | 83% | -482 | ✓ 34 | `+8`

Legs 7/8 (expected 6.3)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Justin Jefferson (MIN WR) | 32% | +212 | ✗ no TD | share 16% · team 2.46 TD · RZ-D 1.04 · pos-D 0.94 |
| Aaron Jones (MIN RB) | 30% | +230 | ✗ no TD | share 15% · team 2.46 TD · RZ-D 1.04 · pos-D 0.95 |
| Jordan Addison (MIN WR) | 24% | +324 | ✓ TD | share 11% · team 2.46 TD · RZ-D 1.04 · pos-D 0.94 |

TD double (Justin Jefferson + Aaron Jones): 13.5% · fair +642 ✗


### BAL@DAL — final 34-31
*O/U 53.5 · spread -3.0 · outdoor · turf · 16:25 ET*

**Injury report (as built):** BAL OFF · Ronnie Stanley (T) — Out · Toe · DNP; BAL OFF · Zay Flowers (WR) — Questionable · Hamstring; DAL DEF · Malik Hooker (S) — Out · Forearm · DNP; DAL DEF · P.J. Locke (S) — Out · Foot · DNP; DAL DEF · Cobie Durant (CB) — Out · Hamstring · DNP; DAL DEF · DeMarvion Overshown (LB) — Out · Hamstring · DNP

**Defensive leaks:** DAL D leaks receiving yards to RBs: x1.27; DAL D leaks receiving yards to WRs: x1.13; DAL D leaks passing yards to QBs: x1.09; BAL D leaks receiving yards to RBs: x1.27

**Coordinators:** BAL OC Declan Doyle — NEW (pass_wr) · measured pass 49% | DC Anthony Weaver (pressure) · DAL OC Klayton Adams — continuity · measured pass 62% | DC Christian Parker (two_high_shell)

**Props SGP** — 4-leg 46.7% · fair +114 ✗ · 6-leg 33.4% · fair +200 ✗ · 8-leg 25.2% · fair +296 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Javonte Williams 2+ receptions | 78% | -362 | ✓ 2 | `4-leg core`
| 2 | Ryan Flournoy 3+ receptions | 78% | -345 | ✗ 2 | `4-leg core`
| 3 | Lamar Jackson 20+ rush yds | 77% | -328 | ✓ 50 | `4-leg core`
| 4 | Dak Prescott 175+ pass yds | 80% | -392 | ✓ 276 | `4-leg core`
| 5 | Derrick Henry 100+ rush yds | 82% | -441 | ✗ 89 | `+6`
| 6 | Zay Flowers 100+ rec yds (Q) | 82% | -464 | ✗ 84 | `+6`
| 7 | CeeDee Lamb 60+ rec yds | 73% | -269 | ✓ 112 | `+8`
| 8 | Lamar Jackson 175+ pass yds | 82% | -447 | ✓ 186 | `+8`

Legs 5/8 (expected 6.3)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Derrick Henry (BAL RB) | 66% | -195 | ✓ TD | share 29% · team 3.16 TD · RZ-D 1.15 · pos-D 1.1 |
| Javonte Williams (DAL RB) | 42% | +138 | ✓ TD | share 20% · team 2.83 TD · RZ-D 0.92 · pos-D 1.01 |
| Lamar Jackson (BAL QB) | 33% | +204 | ✗ no TD | share 8% · team 3.16 TD · RZ-D 1.15 · pos-D 1.54 |

TD double (Derrick Henry + Javonte Williams): 30.0% · fair +233 **CASHED**


### LV@NO — final 35-27
*O/U 43.5 · spread +3.5 · indoor · turf · 16:25 ET*

**Injury report (as built):** LV DEF · Treydan Stukes (S) — Out · Concussion · DNP; LV DEF · Kwity Paye (DE) — Questionable · Illness; LV OFF · Aidan O'Connell (QB) — Questionable · Not injury related - personal matter · DNP; LV OFF · Brock Bowers (TE) — Questionable · Knee · DNP; NO OFF · Barion Brown (WR) — Out · Hamstring · DNP; NO DEF · Christen Miller (DT) — Out · Toe · DNP; NO DEF · Martin Emerson (CB) — Questionable · Shoulder

**Defensive leaks:** NO D leaks rushing yards to RBs: x1.13 (worsening x1.11 L4); NO D leaks carries to RBs: x1.11

**Coordinators:** LV OC Andrew Janocko — NEW (run_heavy) · measured pass 47% | DC Rob Leonard (four_man_rush) · NO OC Doug Nussmeier — continuity · measured pass 63% | DC Brandon Staley (two_high_shell)

**Props SGP** — 4-leg 46.7% · fair +114 **CASHED** · 6-leg 30.1% · fair +232 **CASHED** · 8-leg 21.7% · fair +360 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Juwan Johnson 3+ receptions | 78% | -349 | ✓ 8 | `4-leg core`
| 2 | Tre Tucker 2+ receptions | 77% | -342 | ✓ 4 | `4-leg core`
| 3 | Devaughn Vele 30+ rec yds | 76% | -326 | ✓ 39 | `4-leg core`
| 4 | Tyler Shough 40+ pass att | 80% | -409 | ✓ 42 | `4-leg core`
| 5 | Travis Etienne 20+ rush yds | 81% | -416 | ✓ 57 | `+6`
| 6 | Kirk Cousins 20+ pass att | 74% | -285 | ✓ 33 | `+6`
| 7 | Ashton Jeanty 20+ carries | 83% | -492 | ✗ 19 | `+8`
| 8 | Chris Olave 100+ rec yds | 72% | -258 | ✓ 107 | `+8`

Legs 7/8 (expected 6.2)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Ashton Jeanty (LV RB) | 43% | +131 | ✗ no TD | share 26% · team 2.24 TD · RZ-D 0.95 · pos-D 1.01 |
| Tyler Shough (NO QB) | 38% | +160 | ✗ no TD | share 13% · team 2.63 TD · RZ-D 1.02 · pos-D 1.41 |
| Alvin Kamara (NO RB) | 36% | +177 | ✗ no TD | share 16% · team 2.63 TD · RZ-D 1.02 · pos-D 1.04 |

TD double (Ashton Jeanty + Tyler Shough): 18.8% · fair +432 ✗


### LA@DEN — final 26-30
*O/U 43.5 · spread -2.5 · outdoor · grass · 20:20 ET*

**Injury report (as built):** DEN OFF · Jonah Coleman (RB) — Out · Ankle · DNP; DEN OFF · Marvin Mims Jr. (WR) — Questionable · Foot; LA OFF · Puka Nacua (WR) — Doubtful · Hip · DNP; LA DEF · Kamren Kinchens (S) — Doubtful · Hamstring · DNP; LA OFF · Colby Parkinson (TE) — Questionable · Knee · DNP; LA DEF · Aaron Donald (DT) — nan · DNP; LA DEF · Byron Young (LB) — nan · DNP

**Defensive leaks:** LA D leaks passing interceptions to QBs: x1.23 (worsening x1.16 L4); LA D leaks receptions to TEs: x1.11; LA D leaks receiving yards to RBs: x1.09

**Coordinators:** LA OC Nathan Scheelhaase — NEW (pass_wr) · measured pass 51% | DC Chris Shula (four_man_rush) · DEN OC Davis Webb — NEW (balanced) · measured pass 58% | DC Vance Joseph (pressure)

**Props SGP** — 4-leg 43.3% · fair +131 ✗ · 6-leg 28.4% · fair +252 ✗ · 8-leg 19.3% · fair +419 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Jaylen Waddle 3+ receptions | 78% | -361 | ✗ 2 | `4-leg core`
| 2 | Blake Corum 50+ rush yds | 78% | -346 | ✗ 15 | `4-leg core`
| 3 | Matthew Stafford o0.5 INT o0.5 | 77% | -331 | ✓ 2 INT | `4-leg core`
| 4 | Courtland Sutton 2+ receptions | 76% | -326 | ✓ 3 | `4-leg core`
| 5 | J.K. Dobbins 40+ rush yds | 74% | -289 | ✓ 49 | `+6`
| 6 | Bo Nix 25+ pass att | 83% | -474 | ✓ 34 | `+6`
| 7 | Davante Adams 70+ rec yds | 70% | -236 | ✓ 137 | `+8`
| 8 | Matthew Stafford 25+ pass att | 76% | -311 | ✓ 55 | `+8`

Legs 6/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Kyren Williams (LA RB) | 42% | +139 | ✗ no TD | share 24% · team 2.58 TD · RZ-D 0.76 · pos-D 1.01 |
| Davante Adams (LA WR) | 28% | +262 | ✗ no TD | share 20% · team 2.58 TD · RZ-D 0.76 · pos-D 0.71 |
| Courtland Sutton (DEN WR) | 26% | +283 | ✗ no TD | share 14% · team 2.3 TD · RZ-D 0.84 · pos-D 1.03 |

TD double (Kyren Williams + Davante Adams): 15.5% · fair +547 ✗


### Cross-game combos — Week 3 — Sunday Sept 27 2026 (shipped v1.7)

**4-leg** — 37.3% · fair +168 — 3/4 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | SEA@WAS | Jadarian Price 10+ carries | 78% | ✗ 5 |
| 2 | CAR@CLE | Darren Waller 2+ receptions | 78% | ✓ 5 |
| 3 | NE@JAX | Jakobi Meyers 20+ rec yds | 78% | ✓ 64 |
| 4 | CIN@PIT | Jaylen Warren 20+ rush yds | 78% | ✓ 127 |

**6-leg** — 22.7% · fair +340 — 5/6 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | SEA@WAS | Jadarian Price 10+ carries | 78% | ✗ 5 |
| 2 | CAR@CLE | Darren Waller 2+ receptions | 78% | ✓ 5 |
| 3 | NE@JAX | Jakobi Meyers 20+ rec yds | 78% | ✓ 64 |
| 4 | CIN@PIT | Jaylen Warren 20+ rush yds | 78% | ✓ 127 |
| 5 | KC@MIA | Kenneth Walker III 2+ receptions | 78% | ✓ 2 |
| 6 | NYJ@DET | Sam LaPorta 30+ rec yds | 78% | ✓ 44 |

**8-leg** — 13.8% · fair +624 — 6/8 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | SEA@WAS | Jadarian Price 10+ carries | 78% | ✗ 5 |
| 2 | CAR@CLE | Darren Waller 2+ receptions | 78% | ✓ 5 |
| 3 | NE@JAX | Jakobi Meyers 20+ rec yds | 78% | ✓ 64 |
| 4 | CIN@PIT | Jaylen Warren 20+ rush yds | 78% | ✓ 127 |
| 5 | KC@MIA | Kenneth Walker III 2+ receptions | 78% | ✓ 2 |
| 6 | NYJ@DET | Sam LaPorta 30+ rec yds | 78% | ✓ 44 |
| 7 | ARI@SF | Tyler Allgeier 20+ rush yds | 78% | ✗ -1 |
| 8 | MIN@TB | Aaron Jones 15+ carries | 78% | ✓ 17 |

**10-leg** — 8.6% · fair +1059 — 6/10 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | SEA@WAS | Jadarian Price 10+ carries | 78% | ✗ 5 |
| 2 | CAR@CLE | Darren Waller 2+ receptions | 78% | ✓ 5 |
| 3 | NE@JAX | Jakobi Meyers 20+ rec yds | 78% | ✓ 64 |
| 4 | CIN@PIT | Jaylen Warren 20+ rush yds | 78% | ✓ 127 |
| 5 | KC@MIA | Kenneth Walker III 2+ receptions | 78% | ✓ 2 |
| 6 | CIN@PIT | Chase Brown 3+ receptions | 78% | ✗ 2 |
| 7 | NYJ@DET | Sam LaPorta 30+ rec yds | 78% | ✓ 44 |
| 8 | ARI@SF | Tyler Allgeier 20+ rush yds | 78% | ✗ -1 |
| 9 | HOU@IND | Dalton Schultz 50+ rec yds | 78% | ✗ 30 |
| 10 | MIN@TB | Bucky Irving 40+ rush yds | 78% | ✓ 46 |

**12-leg** — 5.2% · fair +1830 — 6/12 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | SEA@WAS | Jadarian Price 10+ carries | 78% | ✗ 5 |
| 2 | CAR@CLE | Darren Waller 2+ receptions | 78% | ✓ 5 |
| 3 | NE@JAX | Jakobi Meyers 20+ rec yds | 78% | ✓ 64 |
| 4 | CIN@PIT | Jaylen Warren 20+ rush yds | 78% | ✓ 127 |
| 5 | KC@MIA | Kenneth Walker III 2+ receptions | 78% | ✓ 2 |
| 6 | CIN@PIT | Chase Brown 3+ receptions | 78% | ✗ 2 |
| 7 | LA@DEN | Jaylen Waddle 3+ receptions | 78% | ✗ 2 |
| 8 | NYJ@DET | Sam LaPorta 30+ rec yds | 78% | ✓ 44 |
| 9 | ARI@SF | Tyler Allgeier 20+ rush yds | 78% | ✗ -1 |
| 10 | HOU@IND | Dalton Schultz 50+ rec yds | 78% | ✗ 30 |
| 11 | MIN@TB | Bucky Irving 40+ rush yds | 78% | ✓ 46 |
| 12 | LA@DEN | Blake Corum 50+ rush yds | 78% | ✗ 15 |


### ATD board (top 16) — Week 3 — Sunday Sept 27 2026 (shipped v1.7)

| # | Game | Player | Model | Fair | Result |
|---|---|---|---|---|---|
| 1 | BAL@DAL | Derrick Henry (RB) | 66% | -195 | ✓ TD |
| 2 | ARI@SF | Christian McCaffrey (RB) | 64% | -182 | ✓ TD |
| 3 | NYJ@DET | Jahmyr Gibbs (RB) | 63% | -172 | ✓ TD |
| 4 | KC@MIA | Kenneth Walker III (RB) | 47% | +113 | ✓ TD |
| 5 | HOU@IND | Jonathan Taylor (RB) | 45% | +121 | ✗ no TD |
| 6 | NYJ@DET | Amon-Ra St. Brown (WR) | 45% | +121 | ✓ TD |
| 7 | LV@NO | Ashton Jeanty (RB) | 43% | +131 | ✗ no TD |
| 8 | BAL@DAL | Javonte Williams (RB) | 42% | +138 | ✓ TD |
| 9 | LAC@BUF | Omarion Hampton (RB) | 42% | +139 | ✗ no TD |
| 10 | LA@DEN | Kyren Williams (RB) | 42% | +139 | ✗ no TD |
| 11 | CAR@CLE | Quinshon Judkins (RB) | 41% | +142 | ✗ no TD |
| 12 | LAC@BUF | Josh Allen (QB) | 40% | +151 | ✓ TD |
| 13 | LAC@BUF | James Cook (RB) | 40% | +152 | ✓ TD |
| 14 | KC@MIA | Rashee Rice (WR) | 39% | +156 | ✗ no TD |
| 15 | SEA@WAS | Jaxon Smith-Njigba (WR) | 39% | +158 | ✓ TD |
| 16 | HOU@IND | David Montgomery (RB) | 39% | +159 | ✗ no TD |

Board: top-16 9/16 · top-8 6/8 · chalk triple 3/3


### Scorecard — Week 3 — Sunday Sept 27 2026 (shipped v1.7)

**Legs 74/108 = 69% actual vs 78% expected · SGP4 4/14 · SGP6 1/14 · SGP8 0/14**

| Game | Final | Legs | SGP4 | SGP6 | SGP8 |
|---|---|---|---|---|---|
| ARI@SF | 30-36 | 7/8 | ✗ | ✗ | ✗ |
| MIN@TB | 23-16 | 7/8 | ✓ | ✗ | ✗ |
| LV@NO | 35-27 | 7/8 | ✓ | ✓ | ✗ |
| CAR@CLE | 18-21 | 6/8 | ✓ | ✗ | ✗ |
| CIN@PIT | 27-30 | 6/8 | ✗ | ✗ | ✗ |
| NYJ@DET | 24-31 | 6/8 | ✓ | ✗ | ✗ |
| LA@DEN | 26-30 | 6/8 | ✗ | ✗ | ✗ |
| HOU@IND | 17-19 | 5/8 | ✗ | ✗ | ✗ |
| BAL@DAL | 34-31 | 5/8 | ✗ | ✗ | ✗ |
| KC@MIA | 24-10 | 4/8 | ✗ | ✗ | ✗ |
| LAC@BUF | 16-24 | 4/8 | ✗ | ✗ | ✗ |
| NE@JAX | 6-35 | 4/8 | ✗ | ✗ | ✗ |
| TEN@NYG | 7-12 | 4/6 | ✗ | ✗ | ✗ |
| SEA@WAS | 31-33 | 3/6 | ✗ | ✗ | ✗ |


## Week 3 — v1.8 replay (data through Week 2 only; not shipped)

*Engine v1.8 replay.* Leakage-free replay of the same games on the fixed engine, run after the grading. 79% vs 76%, SGP4 7/14, SGP6 7/14, SGP8 4/14. Caveat recorded at the time: the fixes were designed knowing the misses — Week 4 forward was the real exam.


### CAR@CLE — final 18-21
*O/U 41.5 · spread -2.5 · outdoor · grass · 13:00 ET*

**Injury report (as built):** CAR DEF · Nick Scott (S) — Out · Rib · DNP; CAR DEF · Devin Lloyd (LB) — Out · Calf · DNP; CAR DEF · Claudin Cherelus (LB) — Out · Shoulder · DNP; CAR OFF · Xavier Legette (WR) — Questionable · Knee; CAR OFF · Jalen Coker (WR) — Questionable · Ankle; CLE OFF · Teven Jenkins (G) — Out · Back · DNP; CLE DEF · Grant Delpit (S) — Questionable · Shoulder; CLE DEF · Tyson Campbell (CB) — Questionable · Ankle

**Defensive leaks:** CAR D leaks rushing yards to RBs: x1.37 (worsening x1.34 L4); CAR D leaks carries to RBs: x1.19 (worsening x1.06 L4)

**Coordinators:** CAR OC Brad Idzik — continuity · measured pass 65% | DC Ejiro Evero (two_high_shell) · CLE OC Travis Switzer — NEW (run_heavy) · measured pass 53% | DC Mike Rutenberg (multiple)

**Props SGP** — 4-leg 38.4% · fair +160 **CASHED** · 6-leg 27.4% · fair +265 **CASHED** · 8-leg 20.5% · fair +388 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Harold Fannin Jr. 3+ receptions | 78% | -353 | ✓ 7 | `4-leg core`
| 2 | Quinshon Judkins 15+ carries | 77% | -343 | ✓ 18 | `4-leg core`
| 3 | Chuba Hubbard 20+ rush yds | 77% | -343 | ✓ 82 | `4-leg core`
| 4 | Tetairoa McMillan 2+ receptions | 80% | -390 | ✓ 2 | `4-leg core`
| 5 | Bryce Young 20+ pass att | 81% | -427 | ✓ 48 | `+6`
| 6 | Deshaun Watson 20+ pass att | 75% | -298 | ✓ 30 | `+6`
| 7 | Denzel Boston 30+ rec yds | 75% | -299 | ✓ 41 | `+8`
| 8 | KC Concepcion 20+ rec yds | 74% | -287 | ✗ 9 | `+8`

Legs 7/8 (expected 6.2)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Chuba Hubbard (CAR RB) | 38% | +160 | ✗ no TD |  |
| Harold Fannin Jr. (CLE TE) | 36% | +175 | ✓ TD |  |
| Denzel Boston (CLE WR) | 34% | +194 | ✗ no TD |  |

TD double (Chuba Hubbard + Harold Fannin Jr.): 16.0% · fair +525 ✗


### CIN@PIT — final 27-30
*O/U 42.5 · spread -3.5 · outdoor · grass · 13:00 ET*

**Injury report (as built):** CIN DEF · B.J. Hill (DT) — Doubtful · Achilles · DNP; CIN OFF · Andrei Iosivas (WR) — Out · Thumb · DNP; CIN DEF · Dexter Lawrence (DT) — nan · DNP; PIT OFF · Rico Dowdle (RB) — Out · Toe · DNP; PIT OFF · Gennings Dunker (G) — Out · Knee · DNP; PIT DEF · Jamel Dean (CB) — Questionable · Ankle; PIT OFF · Michael Pittman (WR) — Questionable · Foot; PIT OFF · Jaylen Warren (RB) — Questionable · Shoulder

**Defensive leaks:** PIT D leaks passing interceptions to QBs: x1.39 (worsening x1.54 L4); PIT D leaks receptions to TEs: x1.16; PIT D leaks receiving yards to TEs: x1.15; CIN D leaks receiving yards to TEs: x1.47 (worsening x1.30 L4)

**Coordinators:** CIN OC Dan Pitcher — continuity · measured pass 60% | DC Al Golden (disguise_zone) · PIT OC Brian Angelichio — NEW (pass_te) · measured pass 64% | DC Patrick Graham (multiple)

**Props SGP** — 4-leg 48.6% · fair +106 **CASHED** · 6-leg 35.1% · fair +185 **CASHED** · 8-leg 24.4% · fair +310 **CASHED**

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Joe Burrow 25+ pass att | 78% | -363 | ✓ 37 | `4-leg core`
| 2 | Aaron Rodgers 30+ pass att | 79% | -384 | ✓ 34 | `4-leg core`
| 3 | DK Metcalf 2+ receptions | 80% | -409 | ✓ 3 | `4-leg core`
| 4 | Chase Brown 2+ receptions | 81% | -419 | ✓ 2 | `4-leg core`
| 5 | Pat Freiermuth 20+ rec yds | 75% | -294 | ✓ 30 | `+6`
| 6 | Ja'Marr Chase 40+ rec yds | 73% | -273 | ✓ 98 | `+6`
| 7 | Chase Brown 10+ carries | 81% | -428 | ✓ 13 | `+8`
| 8 | Aaron Rodgers 200+ pass yds | 72% | -262 | ✓ 292 | `+8`

Legs 8/8 (expected 6.2)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Chase Brown (CIN RB) | 55% | -120 | ✗ no TD |  |
| Ja'Marr Chase (CIN WR) | 49% | +104 | ✓ TD |  |
| Tee Higgins (CIN WR) | 44% | +128 | ✓ TD |  |

TD double (Chase Brown + Ja'Marr Chase): 31.4% · fair +219 ✗


### HOU@IND — final 17-19
*O/U 41.5 · spread -1.5 · outdoor · turf · 13:00 ET*

**Injury report (as built):** HOU DEF · Jadeveon Clowney (DE) — Out · Knee · DNP; HOU DEF · M.J. Stewart (S) — Out · Knee; HOU OFF · Nico Collins (WR) — Out · Hamstring · DNP; HOU DEF · Jacob Hummel (LB) — Out · Groin · DNP; HOU OFF · Ed Ingram (G) — Out · Groin · DNP; HOU OFF · Trent Brown (T) — Questionable · Knee; HOU OFF · Dalton Schultz (TE) — nan · DNP; HOU DEF · Logan Hall (DE) — nan · DNP

**Defensive leaks:** IND D leaks receiving yards to TEs: x1.25 (worsening x1.28 L4); IND D leaks passing interceptions to QBs: x1.19; IND D leaks receptions to TEs: x1.17 (worsening x1.24 L4); HOU D leaks passing interceptions to QBs: x1.47

**Coordinators:** HOU OC Nick Caley — continuity · measured pass 63% | DC Matt Burke (four_man_rush) · IND OC Jim Bob Cooter — continuity · measured pass 54% | DC Lou Anarumo (disguise_zone)

**Props SGP** — 4-leg 40.0% · fair +150 ✗ · 6-leg 27.4% · fair +265 ✗ · 8-leg 18.1% · fair +454 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Woody Marks 20+ rush yds | 78% | -355 | ✗ 15 | `4-leg core`
| 2 | C.J. Stroud 30+ pass att | 78% | -356 | ✗ 27 | `4-leg core`
| 3 | Jared Wayne 2+ receptions | 78% | -360 | ✗ 1 | `4-leg core`
| 4 | Josh Downs 2+ receptions | 79% | -366 | ✓ 5 | `4-leg core`
| 5 | Dalton Schultz 40+ rec yds | 73% | -276 | ✗ 30 | `+6`
| 6 | Daniel Jones 20+ pass att | 72% | -256 | ✓ 36 | `+6`
| 7 | Jonathan Taylor 40+ rush yds | 71% | -249 | ✓ 68 | `+8`
| 8 | C.J. Stroud 200+ pass yds | 78% | -362 | ✗ 167 | `+8`

Legs 3/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Jonathan Taylor (IND RB) | 58% | -138 | ✗ no TD |  |
| David Montgomery (HOU RB) | 51% | -105 | ✗ no TD |  |
| Tyler Warren (IND TE) | 25% | +300 | ✗ no TD |  |

TD double (Jonathan Taylor + David Montgomery): 32.0% · fair +213 ✗


### KC@MIA — final 24-10
*O/U 45.5 · spread -10.0 · outdoor · grass · 13:00 ET*

**Injury report (as built):** KC DEF · Chamarri Conner (S) — Doubtful · Knee; KC OFF · Josh Simmons (T) — Out · Back · DNP; MIA OFF · Jaylen Wright (RB) — Doubtful · Stinger · DNP; MIA DEF · Rob Beal Jr. (DE) — Out · Hamstring · DNP; MIA OFF · Caleb Douglas (WR) — Out · Ankle · DNP; MIA OFF · Ryan Miller (WR) — Questionable · Hip; MIA DEF · Julius Brents (CB) — Questionable · Knee

**Defensive leaks:** MIA D leaks receiving yards to TEs: x1.17; MIA D leaks receptions to TEs: x1.17; MIA D leaks receiving yards to RBs: x1.09 (worsening x1.27 L4); KC D leaks receiving yards to TEs: x1.10

**Coordinators:** KC OC Eric Bieniemy — NEW (pass_wr) · measured pass 52% | DC Steve Spagnuolo (blitz_heavy) · MIA OC Bobby Slowik — NEW (pass_wr) · measured pass 52% | DC Sean Duggan (multiple)

**Props SGP** — 4-leg 35.2% · fair +184 ✗ · 6-leg 23.5% · fair +326 ✗ · 8-leg 18.1% · fair +453 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Xavier Worthy 2+ receptions | 78% | -348 | ✓ 2 | `4-leg core`
| 2 | Travis Kelce 3+ receptions | 78% | -349 | ✗ 2 | `4-leg core`
| 3 | Rashee Rice 30+ rec yds | 74% | -279 | ✓ 88 | `4-leg core`
| 4 | Kenneth Walker III 70+ rush yds | 73% | -271 | ✓ 70 | `4-leg core`
| 5 | Patrick Mahomes 30+ pass att | 72% | -261 | ✗ 24 | `+6`
| 6 | De'Von Achane 50+ rush yds | 72% | -255 | ✗ 17 | `+6`
| 7 | Travis Kelce 30+ rec yds | 73% | -275 | ✓ 59 | `+8`
| 8 | Patrick Mahomes 200+ pass yds | 70% | -236 | ✓ 246 | `+8`

Legs 5/8 (expected 5.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Kenneth Walker III (KC RB) | 42% | +140 | ✓ TD |  |
| De'Von Achane (MIA RB) | 40% | +151 | ✗ no TD |  |
| Rashee Rice (KC WR) | 35% | +187 | ✗ no TD |  |

TD double (Kenneth Walker III + De'Von Achane): 18.8% · fair +433 ✗


### LAC@BUF — final 16-24
*O/U 50.5 · spread +7.0 · outdoor · grass · 13:00 ET*

**Injury report (as built):** BUF DEF · Jordan Hancock (CB) — Out · Hamstring · DNP; BUF DEF · T.J. Sanders (DE) — Out · Illness · DNP; BUF OFF · DJ Moore (WR) — Questionable · Shoulder; BUF DEF · Ed Oliver (DT) — Questionable · Hip; BUF OFF · Keon Coleman (WR) — Questionable · Ankle; BUF OFF · Ar'maj Reed-Adams (G) — Questionable · Elbow; BUF DEF · Terrel Bernard (LB) — nan · DNP; LAC DEF · Dalvin Tomlinson (DT) — Out · Hamstring · DNP

**Defensive leaks:** BUF D leaks receiving yards to RBs: x1.11 (worsening x1.30 L4); BUF D leaks passing interceptions to QBs: x1.11; BUF D leaks receptions to RBs: x1.11 (worsening x1.17 L4); LAC D leaks passing interceptions to QBs: x1.39

**Coordinators:** LAC OC Mike McDaniel — NEW (pass_rb) · measured pass 52% | DC Chris O'Leary (two_high_shell) · BUF OC Pete Carmichael Jr. — NEW (balanced) · measured pass 49% | DC Jim Leonhard (disguise_zone)

**Props SGP** — 4-leg 39.0% · fair +156 **CASHED** · 6-leg 28.0% · fair +257 **CASHED** · 8-leg 21.6% · fair +363 **CASHED**

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Ladd McConkey 2+ receptions | 79% | -378 | ✓ 4 | `4-leg core`
| 2 | Omarion Hampton 10+ carries | 79% | -385 | ✓ 15 | `4-leg core`
| 3 | James Cook 10+ carries | 76% | -312 | ✓ 24 | `4-leg core`
| 4 | Quentin Johnston 2+ receptions | 75% | -306 | ✓ 3 | `4-leg core`
| 5 | Justin Herbert 20+ pass att | 75% | -303 | ✓ 34 | `+6`
| 6 | Ladd McConkey 20+ rec yds | 73% | -275 | ✓ 66 | `+6`
| 7 | Quentin Johnston 20+ rec yds | 73% | -270 | ✓ 40 | `+8`
| 8 | Justin Herbert 150+ pass yds | 72% | -253 | ✓ 226 | `+8`

Legs 8/8 (expected 6.0)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Josh Allen (BUF QB) | 62% | -167 | ✓ TD |  |
| James Cook (BUF RB) | 59% | -142 | ✓ TD |  |
| Omarion Hampton (LAC RB) | 49% | +106 | ✗ no TD |  |

TD double (Josh Allen + James Cook): 41.2% · fair +143 **CASHED**


### NE@JAX — final 6-35
*O/U 46.5 · spread +3.0 · outdoor · grass · 13:00 ET*

**Injury report (as built):** JAX DEF · Albert Regis (DT) — Doubtful · Elbow; NE DEF · Dre'Mont Jones (LB) — Out · Shoulder · DNP; NE DEF · Brenden Schooler (S) — Out · Back; NE DEF · Quintayvious Hutchins (LB) — Out · Knee · DNP; NE DEF · Craig Woodson (S) — Questionable · Shoulder; NE OFF · Eli Raridon (TE) — Questionable · Thigh · DNP

**Defensive leaks:** JAX D leaks passing interceptions to QBs: x1.19 (worsening x1.20 L4); JAX D leaks receiving yards to RBs: x1.19 (worsening x1.19 L4); JAX D leaks receptions to RBs: x1.17

**Coordinators:** NE OC Josh McDaniels — continuity · measured pass 50% | DC Zak Kuhr (multiple) · JAX OC Grant Udinski — continuity · measured pass 49% | DC Anthony Campanile (pressure)

**Props SGP** — 4-leg 40.1% · fair +149 ✗ · 6-leg 26.3% · fair +280 ✗ · 8-leg 21.1% · fair +373 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Rhamondre Stevenson 20+ rush yds | 77% | -331 | ✓ 22 | `4-leg core`
| 2 | Brian Thomas Jr. 2+ receptions | 77% | -327 | ✗ 1 | `4-leg core`
| 3 | Drake Maye 200+ pass yds | 80% | -402 | ✗ 199 | `4-leg core`
| 4 | Parker Washington 20+ rec yds | 74% | -292 | ✓ 40 | `4-leg core`
| 5 | DeMario Douglas 2+ receptions | 72% | -259 | ✗ 1 | `+6`
| 6 | Trevor Lawrence 200+ pass yds | 70% | -236 | ✗ 182 | `+6`
| 7 | Drake Maye o0.5 INT o0.5 | 74% | -287 | ✓ 2 INT | `+8`
| 8 | Brian Thomas Jr. 30+ rec yds | 74% | -278 | ✗ 8 | `+8`

Legs 3/8 (expected 6.0)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Rhamondre Stevenson (NE RB) | 48% | +108 | ✗ no TD |  |
| Bhayshul Tuten (JAX RB) | 41% | +143 | ✓ TD |  |
| Trevor Lawrence (JAX QB) | 38% | +164 | ✗ no TD |  |

TD double (Rhamondre Stevenson + Bhayshul Tuten): 22.0% · fair +355 ✗


### NYJ@DET — final 24-31
*O/U 49.5 · spread +7.0 · indoor · turf · 13:00 ET*

**Injury report (as built):** DET OFF · Ben Bartch (G) — Out · Foot · DNP; DET DEF · Thomas Harper (S) — Out · Ankle · DNP; NYJ OFF · Kene Nwangwu (RB) — Doubtful · Back · DNP; NYJ DEF · Minkah Fitzpatrick (S) — Out · Groin · DNP; NYJ DEF · Francisco Mauigoa (LB) — Out · Quadricep · DNP; NYJ OFF · Mason Taylor (TE) — Out · Thumb · DNP; NYJ DEF · Joseph Ossai (DE) — Questionable · Foot; NYJ OFF · Adonai Mitchell (WR) — Questionable · Finger

**Defensive leaks:** DET D leaks passing interceptions to QBs: x1.23 (worsening x1.16 L4); DET D leaks receiving yards to WRs: x1.20 (worsening x1.26 L4); DET D leaks receptions to WRs: x1.13 (worsening x1.16 L4); NYJ D leaks carries to RBs: x1.11

**Coordinators:** NYJ OC Frank Reich — NEW (balanced) · measured pass 55% | DC Brian Duker (multiple) · DET OC Drew Petzing — NEW (pass_te) · measured pass 57% | DC Kelvin Sheppard (pressure)

**Props SGP** — 4-leg 39.7% · fair +152 **CASHED** · 6-leg 27.5% · fair +264 **CASHED** · 8-leg 20.1% · fair +398 **CASHED**

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Jared Goff 25+ pass att | 78% | -355 | ✓ 32 | `4-leg core`
| 2 | Breece Hall 10+ carries | 78% | -354 | ✓ 13 | `4-leg core`
| 3 | Jahmyr Gibbs 10+ carries | 78% | -357 | ✓ 20 | `4-leg core`
| 4 | Jameson Williams 1+ receptions | 78% | -346 | ✓ 4 | `4-leg core`
| 5 | Geno Smith 150+ pass yds | 78% | -344 | ✓ 321 | `+6`
| 6 | Sam LaPorta 20+ rec yds | 76% | -320 | ✓ 44 | `+6`
| 7 | Amon-Ra St. Brown 4+ receptions | 75% | -304 | ✓ 4 | `+8`
| 8 | Garrett Wilson 40+ rec yds | 74% | -284 | ✓ 107 | `+8`

Legs 8/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Jahmyr Gibbs (DET RB) | 61% | -156 | ✓ TD |  |
| Amon-Ra St. Brown (DET WR) | 55% | -120 | ✓ TD |  |
| Garrett Wilson (NYJ WR) | 39% | +154 | ✓ TD |  |

TD double (Jahmyr Gibbs + Amon-Ra St. Brown): 37.9% · fair +164 **CASHED**


### SEA@WAS — final 31-33
*O/U 40.5 · spread -8.5 · outdoor · grass · 13:00 ET*

**Injury report (as built):** SEA DEF · Julian Love (S) — Out · Calf · DNP; SEA DEF · Ty Okada (S) — Out · Hamstring · DNP; SEA DEF · Brandon Pili (DT) — Questionable · Concussion; WAS DEF · Frankie Luvu (LB) — Out · Groin · DNP; WAS OFF · Sam Cosmi (G) — Out · Concussion · DNP; WAS DEF · Nick Cross (S) — Out · Illness · DNP; WAS OFF · Chig Okonkwo (TE) — Out · Hamstring · DNP; WAS OFF · Jayden Daniels (QB) — Out · Elbow · DNP

**Defensive leaks:** WAS D leaks rushing yards to RBs: x1.18; WAS D leaks carries to RBs: x1.08; SEA D leaks passing interceptions to QBs: x1.39 (worsening x2.06 L4); SEA D leaks receptions to RBs: x1.15 (worsening x1.24 L4)

**Coordinators:** SEA OC Brian Fleury — NEW (run_heavy) · measured pass 55% | DC Aden Durde (four_man_rush) · WAS OC David Blough — NEW (balanced) · measured pass 51% | DC Daronte Jones (zone_cover3)

**Props SGP** — 4-leg 37.7% · fair +165 ✗ · 6-leg —  · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Stefon Diggs 2+ receptions | 78% | -347 | ✓ 4 | `4-leg core`
| 2 | Jaxon Smith-Njigba 6+ receptions | 80% | -404 | ✓ 10 | `4-leg core`
| 3 | Jadarian Price 40+ rush yds | 74% | -285 | ✗ 15 | `4-leg core`
| 4 | Terry McLaurin 30+ rec yds | 71% | -247 | ✓ 77 | `4-leg core`
| 5 | Jaxon Smith-Njigba 90+ rec yds | 72% | -263 | ✓ 128 | `+6`

Legs 4/5 (expected 3.8)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Jaxon Smith-Njigba (SEA WR) | 52% | -109 | ✓ TD |  |
| Jacory Croskey-Merritt (WAS RB) | 41% | +145 | ✗ no TD |  |
| Stefon Diggs (WAS WR) | 36% | +179 | ✗ no TD |  |

TD double (Jaxon Smith-Njigba + Jacory Croskey-Merritt): 23.5% · fair +326 ✗


### TEN@NYG — final 7-12
*O/U 37.5 · spread +2.5 · outdoor · turf · 13:00 ET*

**Injury report (as built):** NYG DEF · Brian Burns (LB) — Questionable · Ankle · DNP; NYG DEF · Deonte Banks (CB) — Questionable · Calf; NYG DEF · Tyler Nubin (S) — Questionable · Calf; NYG OFF · Jaxson Dart (QB) — nan · DNP; TEN DEF · Cordale Flott (CB) — Questionable · Quadricep; TEN OFF · Tyjae Spears (RB) — Questionable · Ankle

**Defensive leaks:** NYG D leaks rushing yards to RBs: x1.20

**Coordinators:** TEN OC Brian Daboll — NEW (pass_wr) · measured pass 58% | DC Gus Bradley (zone_cover3) · NYG OC Matt Nagy — NEW (pass_wr) · measured pass 48% | DC Dennard Wilson (pressure)

**Props SGP** — 4-leg 41.3% · fair +142 **CASHED** · 6-leg 25.5% · fair +293 **CASHED** · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Malik Nabers 4+ receptions | 78% | -353 | ✓ 5 | `4-leg core`
| 2 | Cam Ward 20+ pass att | 78% | -347 | ✓ 36 | `4-leg core`
| 3 | Tony Pollard 10+ carries | 79% | -374 | ✓ 17 | `4-leg core`
| 4 | Isaiah Likely 2+ receptions | 77% | -333 | ✓ 2 | `4-leg core`
| 5 | Carnell Tate 20+ rec yds | 76% | -311 | ✓ 58 | `+6`
| 6 | Cam Skattebo 50+ rush yds | 74% | -289 | ✓ 60 | `+6`
| 7 | Malachi Fields 20+ rec yds | 73% | -269 | ✗ 19 | `+8`

Legs 6/7 (expected 5.3)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Cam Skattebo (NYG RB) | 58% | -140 | ✗ no TD |  |
| Malik Nabers (NYG WR) | 29% | +244 | ✗ no TD |  |
| Cam Ward (TEN QB) | 27% | +266 | ✗ no TD |  |

TD double (Cam Skattebo + Malik Nabers): 21.0% · fair +377 ✗


### ARI@SF — final 30-36
*O/U 48.5 · spread +7.5 · outdoor · grass · 16:05 ET*

**Injury report (as built):** ARI DEF · Dadrion Taylor-Demerson (S) — Out · Back · DNP; ARI DEF · Roy Lopez (DT) — Questionable · Groin; ARI DEF · Max Melton (CB) — Questionable · Toe; SF OFF · Demarcus Robinson (WR) — Out · Ankle · DNP; SF DEF · Nick Bosa (DE) — Out · Knee · DNP; SF DEF · James Thompson Jr. (DT) — Out · Ankle · DNP; SF DEF · Romello Height (DE) — Out · Hand · DNP; SF OFF · Mike Evans (WR) — Questionable · Hip

**Defensive leaks:** SF D leaks receptions to RBs: x1.21; SF D leaks receiving yards to RBs: x1.14; ARI D leaks rushing yards to RBs: x1.15

**Coordinators:** ARI OC Nathaniel Hackett — NEW (run_heavy) · measured pass 60% | DC Nick Rallis (blitz_heavy) · SF OC Klay Kubiak — continuity · measured pass 51% | DC Raheem Morris (zone_cover3)

**Props SGP** — 4-leg 44.0% · fair +127 ✗ · 6-leg 24.5% · fair +308 ✗ · 8-leg 16.1% · fair +522 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Christian McCaffrey 4+ receptions | 78% | -348 | ✓ 4 | `4-leg core`
| 2 | Deebo Samuel Sr. 2+ receptions | 77% | -343 | ✗ 0 | `4-leg core`
| 3 | Jeremiyah Love 20+ rush yds | 76% | -325 | ✓ 90 | `4-leg core`
| 4 | Brock Purdy 175+ pass yds | 74% | -278 | ✓ 297 | `4-leg core`
| 5 | Kaelon Black 30+ rush yds | 73% | -268 | ✗ 17 | `+6`
| 6 | George Kittle 40+ rec yds | 72% | -263 | ✓ 82 | `+6`
| 7 | Jacoby Brissett 20+ pass att | 72% | -260 | ✓ 52 | `+8`
| 8 | Trey McBride 50+ rec yds | 72% | -252 | ✓ 75 | `+8`

Legs 6/8 (expected 5.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Christian McCaffrey (SF RB) | 56% | -130 | ✓ TD |  |
| Trey McBride (ARI TE) | 45% | +124 | ✗ no TD |  |
| George Kittle (SF TE) | 42% | +141 | ✓ TD |  |

TD double (Christian McCaffrey + Trey McBride): 27.5% · fair +264 ✗


### MIN@TB — final 23-16
*O/U 42.5 · spread -1.5 · outdoor · grass · 16:05 ET*

**Injury report (as built):** MIN OFF · Nick Samac (C) — Out · Knee · DNP; MIN OFF · Brett Thorson (P) — Out · Hamstring · DNP; MIN OFF · Christian Darrisaw (T) — nan · DNP; TB DEF · Rueben Bain Jr. (LB) — Out · Groin · DNP; TB DEF · Josiah Trotter (LB) — Out · Shoulder

**Defensive leaks:** TB D leaks receiving yards to RBs: x1.41; TB D leaks receiving yards to TEs: x1.22 (worsening x1.35 L4); TB D leaks receptions to RBs: x1.17 (worsening x1.42 L4); MIN D leaks passing interceptions to QBs: x1.35 (worsening x1.06 L4)

**Coordinators:** MIN OC Wes Phillips — continuity · measured pass 46% | DC Brian Flores (blitz_man) · TB OC Zac Robinson — NEW (pass_wr) · measured pass 60% | DC Todd Bowles (blitz_heavy)

**Props SGP** — 4-leg 36.9% · fair +171 ✗ · 6-leg 26.2% · fair +282 ✗ · 8-leg 19.9% · fair +401 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Bucky Irving 30+ rush yds | 78% | -349 | ✓ 46 | `4-leg core`
| 2 | Baker Mayfield 25+ pass att | 78% | -347 | ✓ 34 | `4-leg core`
| 3 | Aaron Jones 40+ rush yds | 77% | -341 | ✓ 58 | `4-leg core`
| 4 | T.J. Hockenson 20+ rec yds | 76% | -324 | ✗ 11 | `4-leg core`
| 5 | Chris Godwin Jr. 2+ receptions | 76% | -323 | ✓ 3 | `+6`
| 6 | Emeka Egbuka 2+ receptions | 76% | -313 | ✓ 5 | `+6`
| 7 | Cade Otton 20+ rec yds | 75% | -302 | ✓ 56 | `+8`
| 8 | Baker Mayfield 175+ pass yds | 72% | -252 | ✓ 217 | `+8`

Legs 7/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Aaron Jones (MIN RB) | 30% | +228 | ✗ no TD |  |
| Justin Jefferson (MIN WR) | 27% | +265 | ✗ no TD |  |
| Bucky Irving (TB RB) | 26% | +279 | ✗ no TD |  |

TD double (Aaron Jones + Justin Jefferson): 11.9% · fair +740 ✗


### BAL@DAL — final 34-31
*O/U 53.5 · spread -3.0 · outdoor · grass · 16:25 ET*

**Injury report (as built):** BAL OFF · Ronnie Stanley (T) — Out · Toe · DNP; BAL OFF · Zay Flowers (WR) — Questionable · Hamstring; DAL DEF · Malik Hooker (S) — Out · Forearm · DNP; DAL DEF · P.J. Locke (S) — Out · Foot · DNP; DAL DEF · Cobie Durant (CB) — Out · Hamstring · DNP; DAL DEF · DeMarvion Overshown (LB) — Out · Hamstring · DNP

**Defensive leaks:** DAL D leaks receiving yards to RBs: x1.27; DAL D leaks receiving yards to WRs: x1.13; DAL D leaks passing yards to QBs: x1.09; BAL D leaks receiving yards to RBs: x1.27

**Coordinators:** BAL OC Declan Doyle — NEW (pass_wr) · measured pass 44% | DC Anthony Weaver (pressure) · DAL OC Klayton Adams — continuity · measured pass 60% | DC Christian Parker (two_high_shell)

**Props SGP** — 4-leg 47.6% · fair +110 **CASHED** · 6-leg 30.8% · fair +225 **CASHED** · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | CeeDee Lamb 5+ receptions | 77% | -327 | ✓ 7 | `4-leg core`
| 2 | Dak Prescott 25+ pass att | 80% | -388 | ✓ 40 | `4-leg core`
| 3 | George Pickens 20+ rec yds | 74% | -277 | ✓ 82 | `4-leg core`
| 4 | Derrick Henry 10+ carries | 84% | -504 | ✓ 26 | `4-leg core`
| 5 | Mark Andrews 2+ receptions | 71% | -250 | ✓ 3 | `+6`
| 6 | CeeDee Lamb 50+ rec yds | 74% | -283 | ✓ 112 | `+6`
| 7 | Dak Prescott 175+ pass yds | 73% | -268 | ✓ 276 | `+8`

Legs 7/7 (expected 5.3)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Derrick Henry (BAL RB) | 70% | -236 | ✓ TD |  |
| Javonte Williams (DAL RB) | 38% | +162 | ✓ TD |  |
| CeeDee Lamb (DAL WR) | 36% | +182 | ✗ no TD |  |

TD double (Derrick Henry + Javonte Williams): 28.8% · fair +248 **CASHED**


### LV@NO — final 35-27
*O/U 43.5 · spread +3.5 · indoor · turf · 16:25 ET*

**Injury report (as built):** LV DEF · Treydan Stukes (S) — Out · Concussion · DNP; LV DEF · Kwity Paye (DE) — Questionable · Illness; LV OFF · Aidan O'Connell (QB) — Questionable · Not injury related - personal matter · DNP; LV OFF · Brock Bowers (TE) — Questionable · Knee · DNP; NO OFF · Barion Brown (WR) — Out · Hamstring · DNP; NO DEF · Christen Miller (DT) — Out · Toe · DNP; NO DEF · Martin Emerson (CB) — Questionable · Shoulder

**Defensive leaks:** NO D leaks rushing yards to RBs: x1.13 (worsening x1.11 L4); NO D leaks carries to RBs: x1.11

**Coordinators:** LV OC Andrew Janocko — NEW (run_heavy) · measured pass 50% | DC Rob Leonard (four_man_rush) · NO OC Doug Nussmeier — continuity · measured pass 62% | DC Brandon Staley (two_high_shell)

**Props SGP** — 4-leg 38.4% · fair +160 **CASHED** · 6-leg 27.2% · fair +268 **CASHED** · 8-leg 19.7% · fair +407 **CASHED**

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Tre Tucker 20+ rec yds | 78% | -354 | ✓ 43 | `4-leg core`
| 2 | Juwan Johnson 20+ rec yds | 78% | -344 | ✓ 53 | `4-leg core`
| 3 | Chris Olave 6+ receptions | 77% | -340 | ✓ 9 | `4-leg core`
| 4 | Travis Etienne 30+ rush yds | 77% | -335 | ✓ 57 | `4-leg core`
| 5 | Ashton Jeanty 2+ receptions | 75% | -297 | ✓ 3 | `+6`
| 6 | Tyler Shough 175+ pass yds | 74% | -278 | ✓ 255 | `+6`
| 7 | Ashton Jeanty 15+ carries | 81% | -433 | ✓ 19 | `+8`
| 8 | Tyler Shough 35+ pass att | 72% | -260 | ✓ 42 | `+8`

Legs 8/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Ashton Jeanty (LV RB) | 46% | +117 | ✗ no TD |  |
| Chris Olave (NO WR) | 44% | +125 | ✗ no TD |  |
| Travis Etienne (NO RB) | 44% | +130 | ✗ no TD |  |

TD double (Ashton Jeanty + Chris Olave): 22.7% · fair +340 ✗


### LA@DEN — final 26-30
*O/U 43.5 · spread +1.5 · outdoor · grass · 20:20 ET*

**Injury report (as built):** DEN OFF · Jonah Coleman (RB) — Out · Ankle · DNP; DEN OFF · Marvin Mims Jr. (WR) — Questionable · Foot; LA OFF · Puka Nacua (WR) — Doubtful · Hip · DNP; LA DEF · Kamren Kinchens (S) — Doubtful · Hamstring · DNP; LA OFF · Colby Parkinson (TE) — Questionable · Knee · DNP; LA DEF · Aaron Donald (DT) — nan · DNP; LA DEF · Byron Young (LB) — nan · DNP

**Defensive leaks:** LA D leaks passing interceptions to QBs: x1.23 (worsening x1.16 L4); LA D leaks receptions to TEs: x1.11; LA D leaks receiving yards to RBs: x1.09

**Coordinators:** LA OC Nathan Scheelhaase — NEW (pass_wr) · measured pass 59% | DC Chris Shula (four_man_rush) · DEN OC Davis Webb — NEW (balanced) · measured pass 58% | DC Vance Joseph (pressure)

**Props SGP** — 4-leg 38.4% · fair +161 ✗ · 6-leg 27.6% · fair +262 ✗ · 8-leg 20.2% · fair +395 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Kyren Williams 10+ carries | 79% | -371 | ✓ 15 | `4-leg core`
| 2 | Jaylen Waddle 3+ receptions | 77% | -339 | ✗ 2 | `4-leg core`
| 3 | J.K. Dobbins 50+ rush yds | 76% | -323 | ✗ 49 | `4-leg core`
| 4 | Davante Adams 4+ receptions | 80% | -394 | ✓ 7 | `4-leg core`
| 5 | Bo Nix 30+ pass att | 76% | -312 | ✓ 34 | `+6`
| 6 | Matthew Stafford 25+ pass att | 81% | -434 | ✓ 55 | `+6`
| 7 | Courtland Sutton 30+ rec yds | 70% | -239 | ✓ 46 | `+8`
| 8 | Bo Nix 200+ pass yds | 75% | -305 | ✗ 186 | `+8`

Legs 5/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Davante Adams (LA WR) | 55% | -123 | ✗ no TD |  |
| Kyren Williams (LA RB) | 47% | +112 | ✗ no TD |  |
| Courtland Sutton (DEN WR) | 31% | +225 | ✗ no TD |  |

TD double (Davante Adams + Kyren Williams): 30.7% · fair +226 ✗


### Cross-game combos — Week 3 — v1.8 replay (data through Week 2 only; not shipped)

**4-leg** — 38.1% · fair +163 — 3/4 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | NYJ@DET | Jared Goff 25+ pass att | 78% | ✓ 32 |
| 2 | NYJ@DET | Breece Hall 10+ carries | 78% | ✓ 13 |
| 3 | HOU@IND | Woody Marks 20+ rush yds | 78% | ✗ 15 |
| 4 | LV@NO | Tre Tucker 20+ rec yds | 78% | ✓ 43 |

**6-leg** — 22.2% · fair +350 — 4/6 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | NYJ@DET | Jared Goff 25+ pass att | 78% | ✓ 32 |
| 2 | NYJ@DET | Breece Hall 10+ carries | 78% | ✓ 13 |
| 3 | HOU@IND | Woody Marks 20+ rush yds | 78% | ✗ 15 |
| 4 | LV@NO | Tre Tucker 20+ rec yds | 78% | ✓ 43 |
| 5 | HOU@IND | C.J. Stroud 30+ pass att | 78% | ✗ 27 |
| 6 | CAR@CLE | Harold Fannin Jr. 3+ receptions | 78% | ✓ 7 |

**8-leg** — 13.6% · fair +638 — 6/8 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | NYJ@DET | Jared Goff 25+ pass att | 78% | ✓ 32 |
| 2 | NYJ@DET | Breece Hall 10+ carries | 78% | ✓ 13 |
| 3 | HOU@IND | Woody Marks 20+ rush yds | 78% | ✗ 15 |
| 4 | LV@NO | Tre Tucker 20+ rec yds | 78% | ✓ 43 |
| 5 | HOU@IND | C.J. Stroud 30+ pass att | 78% | ✗ 27 |
| 6 | CAR@CLE | Harold Fannin Jr. 3+ receptions | 78% | ✓ 7 |
| 7 | TEN@NYG | Malik Nabers 4+ receptions | 78% | ✓ 5 |
| 8 | MIN@TB | Bucky Irving 30+ rush yds | 78% | ✓ 46 |

**10-leg** — 8.1% · fair +1136 — 8/10 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | NYJ@DET | Jared Goff 25+ pass att | 78% | ✓ 32 |
| 2 | NYJ@DET | Breece Hall 10+ carries | 78% | ✓ 13 |
| 3 | HOU@IND | Woody Marks 20+ rush yds | 78% | ✗ 15 |
| 4 | LV@NO | Tre Tucker 20+ rec yds | 78% | ✓ 43 |
| 5 | HOU@IND | C.J. Stroud 30+ pass att | 78% | ✗ 27 |
| 6 | CAR@CLE | Harold Fannin Jr. 3+ receptions | 78% | ✓ 7 |
| 7 | TEN@NYG | Malik Nabers 4+ receptions | 78% | ✓ 5 |
| 8 | KC@MIA | Xavier Worthy 2+ receptions | 78% | ✓ 2 |
| 9 | MIN@TB | Bucky Irving 30+ rush yds | 78% | ✓ 46 |
| 10 | CIN@PIT | Joe Burrow 25+ pass att | 78% | ✓ 37 |

**12-leg** — 5.5% · fair +1721 — 9/12 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | NYJ@DET | Jared Goff 25+ pass att | 78% | ✓ 32 |
| 2 | NYJ@DET | Breece Hall 10+ carries | 78% | ✓ 13 |
| 3 | HOU@IND | Woody Marks 20+ rush yds | 78% | ✗ 15 |
| 4 | LV@NO | Tre Tucker 20+ rec yds | 78% | ✓ 43 |
| 5 | HOU@IND | C.J. Stroud 30+ pass att | 78% | ✗ 27 |
| 6 | CAR@CLE | Harold Fannin Jr. 3+ receptions | 78% | ✓ 7 |
| 7 | TEN@NYG | Malik Nabers 4+ receptions | 78% | ✓ 5 |
| 8 | KC@MIA | Xavier Worthy 2+ receptions | 78% | ✓ 2 |
| 9 | KC@MIA | Travis Kelce 3+ receptions | 78% | ✗ 2 |
| 10 | MIN@TB | Bucky Irving 30+ rush yds | 78% | ✓ 46 |
| 11 | CIN@PIT | Joe Burrow 25+ pass att | 78% | ✓ 37 |
| 12 | TEN@NYG | Cam Ward 20+ pass att | 78% | ✓ 36 |


### ATD board (top 16) — Week 3 — v1.8 replay (data through Week 2 only; not shipped)

| # | Game | Player | Model | Fair | Result |
|---|---|---|---|---|---|
| 1 | BAL@DAL | Derrick Henry (RB) | 70% | -236 | ✓ TD |
| 2 | LAC@BUF | Josh Allen (QB) | 62% | -167 | ✓ TD |
| 3 | NYJ@DET | Jahmyr Gibbs (RB) | 61% | -156 | ✓ TD |
| 4 | LAC@BUF | James Cook (RB) | 59% | -142 | ✓ TD |
| 5 | TEN@NYG | Cam Skattebo (RB) | 58% | -140 | ✗ no TD |
| 6 | HOU@IND | Jonathan Taylor (RB) | 58% | -138 | ✗ no TD |
| 7 | ARI@SF | Christian McCaffrey (RB) | 56% | -130 | ✓ TD |
| 8 | LA@DEN | Davante Adams (WR) | 55% | -123 | ✗ no TD |
| 9 | NYJ@DET | Amon-Ra St. Brown (WR) | 55% | -120 | ✓ TD |
| 10 | CIN@PIT | Chase Brown (RB) | 55% | -120 | ✗ no TD |
| 11 | SEA@WAS | Jaxon Smith-Njigba (WR) | 52% | -109 | ✓ TD |
| 12 | HOU@IND | David Montgomery (RB) | 51% | -105 | ✗ no TD |
| 13 | CIN@PIT | Ja'Marr Chase (WR) | 49% | +104 | ✓ TD |
| 14 | LAC@BUF | Omarion Hampton (RB) | 49% | +106 | ✗ no TD |
| 15 | NE@JAX | Rhamondre Stevenson (RB) | 48% | +108 | ✗ no TD |
| 16 | LA@DEN | Kyren Williams (RB) | 47% | +112 | ✗ no TD |

Board: top-16 8/16 · top-8 5/8 · chalk triple 3/3


### Scorecard — Week 3 — v1.8 replay (data through Week 2 only; not shipped)

**Legs 85/107 = 79% actual vs 76% expected · SGP4 7/14 · SGP6 7/14 · SGP8 4/14**

| Game | Final | Legs | SGP4 | SGP6 | SGP8 |
|---|---|---|---|---|---|
| CIN@PIT | 27-30 | 8/8 | ✓ | ✓ | ✓ |
| LAC@BUF | 16-24 | 8/8 | ✓ | ✓ | ✓ |
| NYJ@DET | 24-31 | 8/8 | ✓ | ✓ | ✓ |
| LV@NO | 35-27 | 8/8 | ✓ | ✓ | ✓ |
| CAR@CLE | 18-21 | 7/8 | ✓ | ✓ | ✗ |
| MIN@TB | 23-16 | 7/8 | ✗ | ✗ | ✗ |
| BAL@DAL | 34-31 | 7/7 | ✓ | ✓ | ✗ |
| TEN@NYG | 7-12 | 6/7 | ✓ | ✓ | ✗ |
| ARI@SF | 30-36 | 6/8 | ✗ | ✗ | ✗ |
| KC@MIA | 24-10 | 5/8 | ✗ | ✗ | ✗ |
| LA@DEN | 26-30 | 5/8 | ✗ | ✗ | ✗ |
| SEA@WAS | 31-33 | 4/5 | ✗ | ✗ | ✗ |
| HOU@IND | 17-19 | 3/8 | ✗ | ✗ | ✗ |
| NE@JAX | 6-35 | 3/8 | ✗ | ✗ | ✗ |


## Week 4 — Sunday Oct 4 2026 (floor, v1.8/v1.9)

*Engine v1.8 + ATD v2.* First week on the empirical-Bayes projections and the ATD v2 opportunity model. Also shipped: an aggressive variant (below), an afternoon-window rebuild (NFL-Week4-Afternoon-SGPs.pdf, NFL-Week4-Afternoon-Safe-Combo.pdf), IND-WAS-London-Slip-Pack.pdf (Downs as WR1 with McLaurin out), DET-CAR-SNF-Pack.pdf and ATL-NO-MNF-Pack.pdf. ATD v2 notes from the week: Gibbs, Henry and McCaffrey all scored.


### IND@WAS — final 30-13
*O/U 46.5 · spread -4.5 · outdoor · grass · 09:30 ET*

**Injury report (as built):** IND OFF · Keenan Allen (WR) — Questionable · Not injury related - resting player · DNP; IND OFF · Ashton Dulin (WR) — Questionable · Ankle; WAS OFF · Sam Cosmi (G) — Out · Concussion · DNP; WAS OFF · Rachaad White (RB) — Out · Shoulder · DNP; WAS DEF · Nick Cross (S) — Out · Illness · DNP; WAS OFF · Jayden Daniels (QB) — Out · Elbow; WAS OFF · Terry McLaurin (WR) — Questionable · Hamstring; WAS DEF · Percy Butler (S) — Questionable · Concussion

**Defensive leaks:** WAS D leaks rushing yards to RBs: x1.16; IND D leaks receiving yards to TEs: x1.23 (worsening x1.06 L4); IND D leaks receptions to TEs: x1.16 (worsening x1.11 L4); IND D leaks passing interceptions to QBs: x1.16

**Coordinators:** IND OC Jim Bob Cooter — continuity · measured pass 54% | DC Lou Anarumo (disguise_zone) · WAS OC David Blough — NEW (balanced) · measured pass 51% | DC Daronte Jones (zone_cover3)

**Props SGP** — 4-leg 36.5% · fair +174 ✗ · 6-leg 26.6% · fair +276 ✗ · 8-leg 21.4% · fair +367 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Jacory Croskey-Merritt 20+ rush yds | 76% | -316 | ✗ 15 | `4-leg core`
| 2 | Stefon Diggs 3+ receptions | 75% | -306 | ✓ 5 | `4-leg core`
| 3 | Daniel Jones 150+ pass yds | 75% | -293 | ✗ 143 | `4-leg core`
| 4 | Jonathan Taylor 15+ carries | 82% | -468 | ✓ 20 | `4-leg core`
| 5 | Josh Downs 3+ receptions | 83% | -486 | ✓ 3 | `+6`
| 6 | Stefon Diggs 20+ rec yds | 74% | -283 | ✓ 35 | `+6`
| 7 | Josh Downs 30+ rec yds | 73% | -269 | ✗ 16 | `+8`
| 8 | Daniel Jones 20+ pass att | 85% | -564 | ✓ 34 | `+8`

Legs 5/8 (expected 6.2)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Jonathan Taylor (IND RB) | 61% | -156 | ✓ TD | share 28% · team 2.86 TD · RZ-D 1.16 · pos-D 1.08 |
| Tyler Warren (IND TE) | 45% | +124 | ✗ no TD | share 13% · team 2.86 TD · RZ-D 1.16 · pos-D 1.49 |
| Jacory Croskey-Merritt (WAS RB) | 28% | +255 | ✗ no TD | share 14% · team 2.35 TD · RZ-D 0.99 · pos-D 1.05 |

TD double (Jonathan Taylor + Tyler Warren): 31.7% · fair +215 ✗


### ARI@NYG — final 24-36
*O/U 44.5 · spread -2.5 · outdoor · turf · 13:00 ET*

**Injury report (as built):** ARI DEF · Dadrion Taylor-Demerson (S) — Out · Back · DNP; ARI DEF · Josh Sweat (LB) — Questionable · Not injury related - resting player; NYG OFF · John Michael Schmitz (C) — nan · DNP

**Defensive leaks:** NYG D leaks rushing yards to RBs: x1.19; ARI D leaks rushing yards to RBs: x1.15

**Coordinators:** ARI OC Nathaniel Hackett — NEW (run_heavy) · measured pass 60% | DC Nick Rallis (blitz_heavy) · NYG OC Matt Nagy — NEW (pass_wr) · measured pass 48% | DC Dennard Wilson (pressure)

**Props SGP** — 4-leg 38.0% · fair +163 ✗ · 6-leg 24.5% · fair +308 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Cam Skattebo 50+ rush yds | 78% | -347 | ✓ 58 | `4-leg core`
| 2 | Malik Nabers 4+ receptions | 77% | -341 | ✓ 6 | `4-leg core`
| 3 | Isaiah Likely 2+ receptions | 77% | -330 | ✓ 7 | `4-leg core`
| 4 | Trey McBride 60+ rec yds | 77% | -331 | ✗ 31 | `4-leg core`
| 5 | Jacoby Brissett 25+ pass att | 75% | -302 | ✓ 35 | `+6`
| 6 | Jeremiyah Love 30+ rush yds | 75% | -294 | ✓ 63 | `+6`
| 7 | Michael Wilson 20+ rec yds | 73% | -265 | ✓ 95 | `+8`

Legs 6/7 (expected 5.3)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Cam Skattebo (NYG RB) | 43% | +133 | ✗ no TD | share 19% · team 2.35 TD · RZ-D 1.14 · pos-D 1.17 |
| Trey McBride (ARI TE) | 35% | +187 | ✗ no TD | share 19% · team 2.63 TD · RZ-D 1.11 · pos-D 0.83 |
| Tyler Allgeier (ARI RB) | 35% | +188 | ✓ TD | share 14% · team 2.63 TD · RZ-D 1.11 · pos-D 1.14 |

TD double (Cam Skattebo + Trey McBride): 17.1% · fair +484 ✗


### DAL@HOU — final 34-30
*O/U 48.5 · spread +3.0 · indoor · turf · 13:00 ET*

**Injury report (as built):** DAL DEF · Cobie Durant (CB) — Out · Hamstring · DNP; DAL DEF · DeMarvion Overshown (LB) — Out · Hamstring · DNP; HOU DEF · M.J. Stewart (S) — Out · Knee · DNP; HOU DEF · Azeez Al-Shaair (LB) — Out · Groin · DNP; HOU DEF · Jadeveon Clowney (DE) — Questionable · Knee · DNP; HOU DEF · Jake Hansen (LB) — Questionable · Calf; HOU DEF · Logan Hall (DE) — Questionable · Knee; HOU OFF · Ed Ingram (G) — Questionable · Groin

**Defensive leaks:** HOU D leaks passing interceptions to QBs: x1.46; DAL D leaks receiving yards to RBs: x1.24; DAL D leaks receiving yards to WRs: x1.12; DAL D leaks passing yards to QBs: x1.08

**Coordinators:** DAL OC Klayton Adams — continuity · measured pass 60% | DC Christian Parker (two_high_shell) · HOU OC Nick Caley — continuity · measured pass 63% | DC Matt Burke (four_man_rush)

**Props SGP** — 4-leg 42.3% · fair +136 ✗ · 6-leg 29.1% · fair +244 ✗ · 8-leg 20.8% · fair +382 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | CeeDee Lamb 4+ receptions | 78% | -349 | ✓ 17 | `4-leg core`
| 2 | C.J. Stroud 225+ pass yds | 78% | -346 | ✓ 347 | `4-leg core`
| 3 | George Pickens 3+ receptions | 79% | -382 | ✗ 2 | `4-leg core`
| 4 | Woody Marks 20+ rush yds | 80% | -397 | ✓ 22 | `4-leg core`
| 5 | Javonte Williams 10+ carries | 81% | -427 | ✓ 19 | `+6`
| 6 | Dak Prescott 25+ pass att | 75% | -297 | ✓ 45 | `+6`
| 7 | Dalton Schultz 30+ rec yds | 75% | -293 | ✗ 9 | `+8`
| 8 | Xavier Hutchinson 20+ rec yds | 73% | -275 | ✓ 46 | `+8`

Legs 6/8 (expected 6.2)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| David Montgomery (HOU RB) | 49% | +104 | ✗ no TD | share 19% · team 2.88 TD · RZ-D 1.15 · pos-D 1.14 |
| Woody Marks (HOU RB) | 42% | +137 | ✓ TD | share 16% · team 2.88 TD · RZ-D 1.15 · pos-D 1.14 |
| Javonte Williams (DAL RB) | 37% | +170 | ✓ TD | share 20% · team 2.55 TD · RZ-D 0.98 · pos-D 0.91 |

TD double (David Montgomery + Woody Marks): 25.3% · fair +295 ✗


### GB@TB — final 17-14
*O/U 38.5 · spread -3.0 · outdoor · grass · 13:00 ET*

**Injury report (as built):** GB OFF · Aaron Banks (G) — Out · Knee · DNP; GB OFF · Jacob Monk (C) — Out · Quadricep · DNP; GB DEF · Warren Brinson (DT) — Out · Calf · DNP; GB DEF · Anthony Campbell (DT) — Out · Ankle · DNP; GB DEF · Edgerrin Cooper (LB) — Questionable · Shoulder; GB OFF · Jager Burton (C) — Questionable · Groin; TB OFF · Baker Mayfield (QB) — Out · Thumb · DNP; TB OFF · Ko Kieft (TE) — Out · Elbow · DNP

**Defensive leaks:** TB D leaks receiving yards to RBs: x1.40; TB D leaks receiving yards to TEs: x1.19; TB D leaks receptions to RBs: x1.17 (worsening x1.29 L4); GB D leaks receptions to RBs: x1.10

**Coordinators:** GB OC Adam Stenavich — continuity · measured pass 72% | DC Jonathan Gannon (two_high_shell) · TB OC Zac Robinson — NEW (pass_wr) · measured pass 60% | DC Todd Bowles (blitz_heavy)

**Props SGP** — 4-leg 39.1% · fair +156 **CASHED** · 6-leg 28.7% · fair +249 **CASHED** · 8-leg 18.1% · fair +454 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Cade Otton 20+ rec yds | 78% | -352 | ✓ 37 | `4-leg core`
| 2 | Bucky Irving 10+ carries | 78% | -347 | ✓ 16 | `4-leg core`
| 3 | Tucker Kraft 20+ rec yds | 78% | -345 | ✓ 42 | `4-leg core`
| 4 | Emeka Egbuka 2+ receptions | 77% | -342 | ✓ 2 | `4-leg core`
| 5 | Ted Hurst III 1+ receptions | 79% | -386 | ✓ 2 | `+6`
| 6 | Jordan Love 25+ pass att | 74% | -279 | ✓ 30 | `+6`
| 7 | MarShawn Lloyd 20+ rush yds | 71% | -250 | ✗ 13 | `+8`
| 8 | Jordan Love 175+ pass yds | 73% | -274 | ✓ 197 | `+8`

Legs 7/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Bucky Irving (TB RB) | 27% | +266 | ✗ no TD | share 15% · team 1.99 TD · RZ-D 1.09 · pos-D 1.02 |
| Christian Watson (GB WR) | 27% | +275 | ✗ no TD | share 14% · team 2.32 TD · RZ-D 1.04 · pos-D 0.95 |
| Emeka Egbuka (TB WR) | 22% | +348 | ✗ no TD | share 11% · team 1.99 TD · RZ-D 1.09 · pos-D 1.09 |

TD double (Bucky Irving + Christian Watson): 8.9% · fair +1024 ✗


### JAX@CIN — final 22-17
*O/U 51.5 · spread +2.5 · outdoor · turf · 13:00 ET*

**Injury report (as built):** CIN DEF · Kyle Dugger (S) — Out · Quadricep · DNP; CIN OFF · Colbie Young (WR) — Out · Knee · DNP; CIN DEF · B.J. Hill (DT) — Questionable · Achilles; CIN OFF · Dalton Risner (G) — Questionable · Knee; CIN DEF · Bryan Cook (S) — Questionable · Ankle; CIN DEF · Swayze Bozeman (LB) — Questionable · Groin · DNP; CIN DEF · Dexter Lawrence (DT) — nan · DNP; JAX DEF · Montaric Brown (CB) — Questionable · Hamstring

**Defensive leaks:** CIN D leaks receiving yards to TEs: x1.48 (worsening x1.29 L4); CIN D leaks receptions to TEs: x1.30 (worsening x1.14 L4); CIN D leaks receiving yards to RBs: x1.19 (worsening x1.26 L4); JAX D leaks passing interceptions to QBs: x1.23 (worsening x1.54 L4)

**Coordinators:** JAX OC Grant Udinski — continuity · measured pass 49% | DC Anthony Campanile (pressure) · CIN OC Dan Pitcher — continuity · measured pass 60% | DC Al Golden (disguise_zone)

**Props SGP** — 4-leg 47.2% · fair +112 ✗ · 6-leg 34.6% · fair +189 ✗ · 8-leg 18.0% · fair +455 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Brian Thomas Jr. 20+ rec yds | 78% | -349 | ✗ 17 | `4-leg core`
| 2 | Tee Higgins 50+ rec yds | 78% | -345 | ✓ 157 | `4-leg core`
| 3 | Trevor Lawrence 25+ pass att | 79% | -367 | ✗ 23 | `4-leg core`
| 4 | Parker Washington 2+ receptions | 79% | -383 | ✗ 1 | `4-leg core`
| 5 | Joe Burrow 200+ pass yds | 76% | -322 | ✓ 428 | `+6`
| 6 | Ja'Marr Chase 6+ receptions | 75% | -302 | ✗ 3 | `+6`
| 7 | Chase Brown 50+ rush yds | 73% | -272 | ✗ 10 | `+8`
| 8 | Bhayshul Tuten 20+ rush yds | 72% | -258 | ✓ 73 | `+8`

Legs 3/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Chase Brown (CIN RB) | 39% | +155 | ✗ no TD | share 20% · team 3.02 TD · RZ-D 0.9 · pos-D 0.85 |
| Ja'Marr Chase (CIN WR) | 34% | +192 | ✗ no TD | share 16% · team 3.02 TD · RZ-D 0.9 · pos-D 0.92 |
| Tee Higgins (CIN WR) | 28% | +252 | ✗ no TD | share 13% · team 3.02 TD · RZ-D 0.9 · pos-D 0.92 |

TD double (Chase Brown + Ja'Marr Chase): 17.7% · fair +466 ✗


### LA@PHI — final 24-20
*O/U 42.5 · spread -3.5 · outdoor · grass · 13:00 ET*

**Injury report (as built):** LA DEF · Aaron Donald (DT) — Out · Back · DNP; LA DEF · Jaylen Watson (CB) — Out · Shoulder · DNP; LA OFF · Terrance Ferguson (TE) — Out · Ankle · DNP; LA OFF · Colby Parkinson (TE) — Questionable · Knee · DNP; LA DEF · Josaiah Stewart (LB) — Questionable · Groin · DNP; LA OFF · Tyler Higbee (TE) — nan · DNP; LA OFF · Alaric Jackson (T) — nan · DNP; PHI OFF · Dallas Goedert (TE) — Out · Knee · DNP

**Defensive leaks:** LA D leaks passing interceptions to QBs: x1.23 (worsening x1.16 L4); LA D leaks receiving yards to RBs: x1.12; LA D leaks receptions to TEs: x1.08

**Coordinators:** LA OC Nathan Scheelhaase — NEW (pass_wr) · measured pass 59% | DC Chris Shula (four_man_rush) · PHI OC Sean Mannion — NEW (run_heavy) · measured pass 54% | DC Vic Fangio (two_high_shell)

**Props SGP** — 4-leg 38.5% · fair +160 **CASHED** · 6-leg 28.6% · fair +249 ✗ · 8-leg 20.8% · fair +381 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Kyren Williams 40+ rush yds | 78% | -363 | ✓ 80 | `4-leg core`
| 2 | Matthew Stafford 25+ pass att | 77% | -338 | ✓ 51 | `4-leg core`
| 3 | Davante Adams 4+ receptions | 77% | -338 | ✓ 4 | `4-leg core`
| 4 | Tyler Higbee 2+ receptions | 74% | -280 | ✓ 5 | `4-leg core`
| 5 | Jalen Hurts 20+ rush yds | 72% | -263 | ✗ 18 | `+6`
| 6 | Saquon Barkley 10+ carries | 88% | -704 | ✗ 2 | `+6`
| 7 | Matthew Stafford 175+ pass yds | 71% | -245 | ✓ 317 | `+8`
| 8 | Davante Adams 50+ rec yds | 71% | -242 | ✗ 32 | `+8`

Legs 5/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Kyren Williams (LA RB) | 45% | +124 | ✓ TD | share 23% · team 2.58 TD · RZ-D 0.95 · pos-D 1.02 |
| Davante Adams (LA WR) | 32% | +210 | ✗ no TD | share 20% · team 2.58 TD · RZ-D 0.95 · pos-D 0.78 |
| Saquon Barkley (PHI RB) | 28% | +262 | ✗ no TD | share 21% · team 2.18 TD · RZ-D 0.88 · pos-D 0.76 |

TD double (Kyren Williams + Davante Adams): 18.6% · fair +436 ✗


### NE@BUF — final 29-26
*O/U 49.5 · spread +7.0 · outdoor · turf · 13:00 ET*

**Injury report (as built):** BUF DEF · T.J. Sanders (DE) — Doubtful · Illness; BUF DEF · Christian Benford (CB) — Questionable · Toe · DNP; BUF OFF · Ray Davis (RB) — Questionable · Hamstring; BUF DEF · Sam Franklin Jr. (S) — nan · DNP; BUF DEF · Terrel Bernard (LB) — nan · DNP; NE DEF · Christian Barmore (DT) — Out · Shoulder · DNP; NE DEF · Brenden Schooler (S) — Out · Back; NE DEF · Christian Gonzalez (CB) — Out · Shoulder · DNP

**Defensive leaks:** BUF D leaks passing interceptions to QBs: x1.12; BUF D leaks receptions to RBs: x1.11 (worsening x1.07 L4); BUF D leaks receiving yards to RBs: x1.09

**Coordinators:** NE OC Josh McDaniels — continuity · measured pass 50% | DC Zak Kuhr (multiple) · BUF OC Pete Carmichael Jr. — NEW (balanced) · measured pass 49% | DC Jim Leonhard (disguise_zone)

**Props SGP** — 4-leg 46.5% · fair +115 ✗ · 6-leg 24.3% · fair +312 ✗ · 8-leg 17.5% · fair +471 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | DJ Moore 2+ receptions | 78% | -356 | ✗ 1 | `4-leg core`
| 2 | Dalton Kincaid 2+ receptions | 79% | -372 | ✗ 1 | `4-leg core`
| 3 | Drake Maye 20+ pass att | 79% | -372 | ✓ 37 | `4-leg core`
| 4 | Josh Allen 20+ pass att | 75% | -306 | ✓ 33 | `4-leg core`
| 5 | James Cook 50+ rush yds | 74% | -285 | ✓ 75 | `+6`
| 6 | Rhamondre Stevenson 20+ rush yds | 71% | -246 | ✓ 47 | `+6`
| 7 | Mack Hollins 20+ rec yds | 70% | -235 | ✓ 53 | `+8`
| 8 | Drake Maye 150+ pass yds | 81% | -419 | ✓ 269 | `+8`

Legs 6/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| James Cook (BUF RB) | 43% | +134 | ✓ TD | share 20% · team 3.16 TD · RZ-D 1.07 · pos-D 0.85 |
| Rhamondre Stevenson (NE RB) | 40% | +148 | ✓ TD | share 17% · team 2.38 TD · RZ-D 1.04 · pos-D 1.22 |
| TreVeyon Henderson (NE RB) | 36% | +174 | ✗ no TD | share 15% · team 2.38 TD · RZ-D 1.04 · pos-D 1.22 |

TD double (James Cook + Rhamondre Stevenson): 19.5% · fair +412 **CASHED**


### NYJ@CHI — final 12-23
*O/U 43.5 · spread +3.5 · outdoor · grass · 13:00 ET*

**Injury report (as built):** CHI DEF · Cam Lewis (S) — Doubtful · Hip · DNP; CHI OFF · Braxton Jones (T) — Out · Knee · DNP; CHI DEF · Kyler Gordon (CB) — Out · Calf; CHI DEF · Noah Sewell (LB) — Out · Achilles; CHI OFF · Caleb Williams (QB) — Out · Hamstring · DNP; CHI DEF · Shemar Turner (DE) — Out · Knee; NYJ OFF · Dylan Parham (G) — Out · Knee · DNP; NYJ OFF · Breece Hall (RB) — Out · Quadricep · DNP

**Defensive leaks:** CHI D leaks passing interceptions to QBs: x1.43; CHI D leaks rushing yards to RBs: x1.17; NYJ D leaks carries to RBs: x1.11

**Coordinators:** NYJ OC Frank Reich — NEW (balanced) · measured pass 55% | DC Brian Duker (multiple) · CHI OC Press Taylor — NEW (pass_wr) · measured pass 48% | DC Dennis Allen (blitz_man)

**Props SGP** — 4-leg 40.9% · fair +144 ✗ · 6-leg 23.3% · fair +330 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Kalif Raymond 20+ rec yds | 77% | -329 | ✗ 6 | `4-leg core`
| 2 | Geno Smith 150+ pass yds | 77% | -328 | ✗ 119 | `4-leg core`
| 3 | Garrett Wilson 50+ rec yds | 75% | -302 | ✗ 27 | `4-leg core`
| 4 | Luther Burden III 3+ receptions | 72% | -263 | ✓ 4 | `4-leg core`
| 5 | D'Andre Swift 50+ rush yds | 72% | -258 | ✓ 58 | `+6`
| 6 | Rome Odunze 2+ receptions | 72% | -255 | ✓ 6 | `+6`
| 7 | Geno Smith 20+ pass att | 80% | -393 | ✗ 15 | `+8`

Legs 3/7 (expected 5.2)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| D'Andre Swift (CHI RB) | 54% | -117 | ✗ no TD | share 19% · team 2.63 TD · RZ-D 1.17 · pos-D 1.43 |
| Kyle Monangai (CHI RB) | 39% | +156 | ✓ TD | share 12% · team 2.63 TD · RZ-D 1.17 · pos-D 1.43 |
| Garrett Wilson (NYJ WR) | 28% | +262 | ✗ no TD | share 12% · team 2.24 TD · RZ-D 0.99 · pos-D 1.17 |

TD double (D'Andre Swift + Kyle Monangai): 25.6% · fair +290 ✗


### TEN@BAL — final 18-24
*O/U 42.5 · spread +11.5 · outdoor · grass · 13:00 ET*

**Injury report (as built):** BAL OFF · Ethan Pocic (C) — Out · Knee · DNP; BAL DEF · Trey Hendrickson (LB) — Out · Finger · DNP; BAL OFF · Jovaughn Gwyn (C) — Out · Ankle · DNP; BAL OFF · Chris Moore (WR) — Questionable · Ankle; BAL OFF · Ronnie Stanley (T) — Questionable · Toe · DNP; BAL OFF · Zay Flowers (WR) — Questionable · Hamstring; TEN OFF · Tyjae Spears (RB) — Questionable · Ankle; TEN DEF · Kevin Winston Jr. (S) — Questionable · Shoulder · DNP

**Defensive leaks:** BAL D leaks receiving yards to RBs: x1.23; BAL D leaks receptions to RBs: x1.20; BAL D leaks receiving yards to WRs: x1.16

**Coordinators:** TEN OC Brian Daboll — NEW (pass_wr) · measured pass 58% | DC Gus Bradley (zone_cover3) · BAL OC Declan Doyle — NEW (pass_wr) · measured pass 44% | DC Anthony Weaver (pressure)

**Props SGP** — 4-leg 45.6% · fair +119 ✗ · 6-leg 25.1% · fair +299 ✗ · 8-leg 16.6% · fair +502 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Mark Andrews 2+ receptions | 78% | -360 | ✓ 5 | `4-leg core`
| 2 | Cam Ward 20+ pass att | 79% | -378 | ✓ 31 | `4-leg core`
| 3 | Wan'Dale Robinson 20+ rec yds | 76% | -315 | ✗ 19 | `4-leg core`
| 4 | Carnell Tate 20+ rec yds | 76% | -313 | ✓ 145 | `4-leg core`
| 5 | Tony Pollard 30+ rush yds | 72% | -256 | ✓ 48 | `+6`
| 6 | Lamar Jackson 150+ pass yds | 71% | -249 | ✓ 222 | `+6`
| 7 | Derrick Henry 80+ rush yds | 71% | -248 | ✗ 73 | `+8`
| 8 | Wan'Dale Robinson 4+ receptions | 76% | -314 | ✗ 3 | `+8`

Legs 5/8 (expected 6.0)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Derrick Henry (BAL RB) | 65% | -184 | ✓ TD | share 29% · team 3.02 TD · RZ-D 1.12 · pos-D 1.11 |
| Mark Andrews (BAL TE) | 30% | +236 | ✓ TD | share 11% · team 3.02 TD · RZ-D 1.12 · pos-D 1.05 |
| Tony Pollard (TEN RB) | 24% | +326 | ✓ TD | share 16% · team 1.74 TD · RZ-D 0.91 · pos-D 1.02 |

TD double (Derrick Henry + Mark Andrews): 23.2% · fair +331 **CASHED**


### MIA@MIN — final 10-15
*O/U 38.5 · spread +10.0 · indoor · turf · 16:05 ET*

**Injury report (as built):** MIA DEF · Rob Beal Jr. (LB) — Out · Hamstring · DNP; MIA DEF · Storm Duck (CB) — Out · Knee; MIA OFF · Caleb Douglas (WR) — Out · Ankle · DNP; MIN OFF · Justin Jefferson (WR) — Out · Ankle · DNP; MIN DEF · Charles Demmings (CB) — Out · Hamstring · DNP; MIN OFF · Brett Thorson (P) — Out · Hamstring · DNP; MIN OFF · Christian Darrisaw (T) — nan · DNP

**Defensive leaks:** MIN D leaks passing interceptions to QBs: x1.39 (worsening x1.37 L4); MIA D leaks receiving yards to TEs: x1.19 (worsening x1.13 L4); MIA D leaks receptions to TEs: x1.16

**Coordinators:** MIA OC Bobby Slowik — NEW (pass_wr) · measured pass 52% | DC Sean Duggan (multiple) · MIN OC Wes Phillips — continuity · measured pass 46% | DC Brian Flores (blitz_man)

**Props SGP** — 4-leg 44.7% · fair +124 ✗ · 6-leg —  · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | T.J. Hockenson 2+ receptions | 78% | -354 | ✓ 13 | `4-leg core`
| 2 | Aaron Jones 10+ carries | 76% | -325 | ✓ 20 | `4-leg core`
| 3 | Malik Washington 2+ receptions | 74% | -279 | ✓ 5 | `4-leg core`

Legs 3/3 (expected 2.3)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Aaron Jones (MIN RB) | 40% | +153 | ✗ no TD | share 15% · team 2.72 TD · RZ-D 1.14 · pos-D 1.14 |
| Jordan Addison (MIN WR) | 28% | +251 | ✗ no TD | share 12% · team 2.72 TD · RZ-D 1.14 · pos-D 1.0 |
| T.J. Hockenson (MIN TE) | 21% | +369 | ✗ no TD | share 7% · team 2.72 TD · RZ-D 1.14 · pos-D 1.1 |

TD double (Aaron Jones + Jordan Addison): 15.2% · fair +556 ✗


### DEN@SF — final 14-24
*O/U 48.5 · spread +3.0 · outdoor · grass · 16:25 ET*

**Injury report (as built):** DEN DEF · Dondrea Tillman (LB) — Out · Hamstring · DNP; SF DEF · Nick Bosa (DE) — Out · Knee · DNP; SF DEF · Mykel Williams (DE) — Out · Knee; SF DEF · James Thompson Jr. (DT) — Out · Ankle · DNP; SF OFF · Mike Evans (WR) — Questionable · Ribs; SF DEF · Dre Greenlaw (LB) — Questionable · Quadricep; SF DEF · Keion White (DE) — Questionable · Hamstring; SF DEF · Jaden Dugger (LB) — Questionable · Shoulder

**Defensive leaks:** SF D leaks receptions to RBs: x1.23 (worsening x1.09 L4); SF D leaks receiving yards to RBs: x1.14; DEN D leaks passing interceptions to QBs: x1.12 (worsening x1.70 L4); DEN D leaks attempts to QBs: x1.09

**Coordinators:** DEN OC Davis Webb — NEW (balanced) · measured pass 58% | DC Vance Joseph (pressure) · SF OC Klay Kubiak — continuity · measured pass 51% | DC Raheem Morris (zone_cover3)

**Props SGP** — 4-leg 37.3% · fair +168 ✗ · 6-leg 26.8% · fair +273 ✗ · 8-leg 21.8% · fair +360 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Christian McCaffrey 4+ receptions | 79% | -382 | ✗ 3 | `4-leg core`
| 2 | George Kittle 4+ receptions | 76% | -320 | ✓ 4 | `4-leg core`
| 3 | Kaelon Black 20+ rush yds | 76% | -316 | ✗ 13 | `4-leg core`
| 4 | Bo Nix 150+ pass yds | 76% | -311 | ✓ 214 | `4-leg core`
| 5 | Courtland Sutton 20+ rec yds | 75% | -302 | ✗ 4 | `+6`
| 6 | Deebo Samuel Sr. 20+ rec yds | 74% | -291 | ✓ 26 | `+6`
| 7 | Brock Purdy 25+ pass att | 82% | -456 | ✓ 30 | `+8`
| 8 | J.K. Dobbins 10+ carries | 85% | -569 | ✓ 11 | `+8`

Legs 5/8 (expected 6.2)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Christian McCaffrey (SF RB) | 49% | +103 | ✓ TD | share 27% · team 2.88 TD · RZ-D 0.73 · pos-D 0.99 |
| J.K. Dobbins (DEN RB) | 31% | +222 | ✗ no TD | share 15% · team 2.55 TD · RZ-D 0.94 · pos-D 0.99 |
| RJ Harvey (DEN RB) | 30% | +229 | ✗ no TD | share 15% · team 2.55 TD · RZ-D 0.94 · pos-D 0.99 |

TD double (Christian McCaffrey + J.K. Dobbins): 17.3% · fair +478 ✗


### KC@LV — final 30-27
*O/U 47.5 · spread -4.5 · indoor · grass · 16:25 ET*

**Injury report (as built):** KC OFF · Josh Simmons (T) — Out · Back · DNP; LV OFF · Jackson Powers-Johnson (G) — Out · Groin · DNP; LV OFF · Aidan O'Connell (QB) — Questionable · Not injury related - personal matter · DNP

**Defensive leaks:** KC D leaks receiving yards to TEs: x1.10

**Coordinators:** KC OC Eric Bieniemy — NEW (pass_wr) · measured pass 52% | DC Steve Spagnuolo (blitz_heavy) · LV OC Andrew Janocko — NEW (run_heavy) · measured pass 50% | DC Rob Leonard (four_man_rush)

**Props SGP** — 4-leg 44.3% · fair +126 ✗ · 6-leg 34.3% · fair +192 ✗ · 8-leg 24.6% · fair +307 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Patrick Mahomes 200+ pass yds | 78% | -355 | ✓ 225 | `4-leg core`
| 2 | Travis Kelce 30+ rec yds | 78% | -346 | ✗ 15 | `4-leg core`
| 3 | Kirk Cousins 20+ pass att | 77% | -331 | ✓ 52 | `4-leg core`
| 4 | Ashton Jeanty 3+ receptions | 77% | -328 | ✓ 6 | `4-leg core`
| 5 | Xavier Worthy 2+ receptions | 76% | -324 | ✓ 4 | `+6`
| 6 | Rashee Rice 40+ rec yds | 76% | -316 | – DNP | `+6`
| 7 | Kenneth Walker III 15+ carries | 83% | -479 | ✓ 22 | `+8`
| 8 | Patrick Mahomes 30+ pass att | 76% | -324 | ✓ 30 | `+8`

Legs 6/7 (expected 6.2)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Kenneth Walker III (KC RB) | 45% | +124 | ✓ TD | share 20% · team 2.91 TD · RZ-D 1.04 · pos-D 1.02 |
| Ashton Jeanty (LV RB) | 43% | +135 | ✗ no TD | share 25% · team 2.41 TD · RZ-D 0.94 · pos-D 0.93 |
| Rashee Rice (KC WR) | 32% | +212 | – DNP | share 14% · team 2.91 TD · RZ-D 1.04 · pos-D 0.95 |

TD double (Kenneth Walker III + Ashton Jeanty): 21.3% · fair +369 ✗


### LAC@SEA — final 23-30
*O/U 42.5 · spread +7.0 · outdoor · turf · 16:25 ET*

**Injury report (as built):** LAC DEF · Dalvin Tomlinson (DT) — Out · Hamstring · DNP; LAC OFF · Kayode Awosika (G) — Out · Fibula · DNP; LAC OFF · Charlie Kolar (TE) — Out · Forearm; LAC OFF · Brenen Thompson (WR) — Out · Quadricep · DNP; LAC DEF · Donte Jackson (CB) — Questionable · Concussion; LAC DEF · Derwin James (S) — Questionable · Hamstring; LAC DEF · Elijah Molden (S) — Questionable · Hamstring; LAC OFF · Trey Lance (QB) — Questionable · Groin

**Defensive leaks:** SEA D leaks passing interceptions to QBs: x1.35 (worsening x1.41 L4); SEA D leaks receptions to RBs: x1.13; SEA D leaks receiving yards to RBs: x1.09; LAC D leaks passing interceptions to QBs: x1.43

**Coordinators:** LAC OC Mike McDaniel — NEW (pass_rb) · measured pass 52% | DC Chris O'Leary (two_high_shell) · SEA OC Brian Fleury — NEW (run_heavy) · measured pass 55% | DC Aden Durde (four_man_rush)

**Props SGP** — 4-leg 36.2% · fair +176 ✗ · 6-leg 24.7% · fair +305 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Justin Herbert 20+ pass att | 77% | -330 | ✓ 31 | `4-leg core`
| 2 | Jaxon Smith-Njigba 5+ receptions | 76% | -326 | ✓ 5 | `4-leg core`
| 3 | Quentin Johnston 2+ receptions | 76% | -317 | ✗ 1 | `4-leg core`
| 4 | Omarion Hampton 10+ carries | 76% | -310 | ✗ 9 | `4-leg core`
| 5 | Jaxon Smith-Njigba 60+ rec yds | 74% | -284 | ✓ 76 | `+6`
| 6 | Quentin Johnston 20+ rec yds | 70% | -235 | ✓ 44 | `+6`

Legs 4/6 (expected 4.5)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Jaxon Smith-Njigba (SEA WR) | 30% | +234 | ✗ no TD | share 16% · team 2.77 TD · RZ-D 0.84 · pos-D 0.86 |
| Omarion Hampton (LAC RB) | 23% | +327 | ✓ TD | share 20% · team 1.99 TD · RZ-D 0.88 · pos-D 0.73 |

TD double (Jaxon Smith-Njigba + Omarion Hampton): 8.6% · fair +1065 ✗


### DET@CAR — final 26-32
*O/U 51.5 · spread -3.5 · outdoor · grass · 20:20 ET*

**Injury report (as built):** CAR OFF · Damien Lewis (G) — Out · Elbow · DNP; CAR OFF · Xavier Legette (WR) — Out · Knee · DNP; CAR OFF · Jalen Coker (WR) — Questionable · Quadricep; CAR DEF · Cam Jackson (DT) — Questionable · Knee; CAR OFF · Monroe Freeling (T) — Questionable · Concussion; CAR DEF · Lee Hunter (DT) — Questionable · Foot; DET OFF · Ben Bartch (G) — Out · Foot · DNP; DET DEF · D.J. Reed (CB) — Questionable · Rib

**Defensive leaks:** CAR D leaks rushing yards to RBs: x1.36 (worsening x1.12 L4); CAR D leaks carries to RBs: x1.18; DET D leaks passing interceptions to QBs: x1.19; DET D leaks receiving yards to WRs: x1.19 (worsening x1.10 L4)

**Coordinators:** DET OC Drew Petzing — NEW (pass_te) · measured pass 57% | DC Kelvin Sheppard (pressure) · CAR OC Brad Idzik — continuity · measured pass 65% | DC Ejiro Evero (two_high_shell)

**Props SGP** — 4-leg 40.7% · fair +146 **CASHED** · 6-leg 26.0% · fair +284 **CASHED** · 8-leg 18.4% · fair +443 **CASHED**

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Chuba Hubbard 40+ rush yds | 78% | -345 | ✓ 122 | `4-leg core`
| 2 | Jared Goff 200+ pass yds | 79% | -369 | ✓ 412 | `4-leg core`
| 3 | Tetairoa McMillan 3+ receptions | 77% | -337 | ✓ 14 | `4-leg core`
| 4 | Jameson Williams 2+ receptions | 77% | -335 | ✓ 6 | `4-leg core`
| 5 | Bryce Young 150+ pass yds | 76% | -325 | ✓ 329 | `+6`
| 6 | Jahmyr Gibbs 15+ carries | 76% | -322 | ✓ 15 | `+6`
| 7 | Sam LaPorta 40+ rec yds | 72% | -259 | ✓ 84 | `+8`
| 8 | Amon-Ra St. Brown 40+ rec yds | 71% | -241 | ✓ 75 | `+8`

Legs 8/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Jahmyr Gibbs (DET RB) | 56% | -126 | ✓ TD | share 23% · team 3.08 TD · RZ-D 1.0 · pos-D 1.14 |
| Chuba Hubbard (CAR RB) | 38% | +162 | ✓ TD | share 18% · team 2.69 TD · RZ-D 1.09 · pos-D 0.93 |
| Amon-Ra St. Brown (DET WR) | 38% | +165 | ✗ no TD | share 18% · team 3.08 TD · RZ-D 1.0 · pos-D 0.86 |

TD double (Jahmyr Gibbs + Chuba Hubbard): 23.4% · fair +327 **CASHED**


### Cross-game combos — Week 4 — Sunday Oct 4 2026 (floor, v1.8/v1.9)

**4-leg** — 37.2% · fair +169 — 3/4 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | MIA@MIN | T.J. Hockenson 2+ receptions | 78% | ✓ 13 |
| 2 | KC@LV | Patrick Mahomes 200+ pass yds | 78% | ✓ 225 |
| 3 | NE@BUF | DJ Moore 2+ receptions | 78% | ✗ 1 |
| 4 | GB@TB | Cade Otton 20+ rec yds | 78% | ✓ 37 |

**6-leg** — 22.8% · fair +338 — 4/6 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | MIA@MIN | T.J. Hockenson 2+ receptions | 78% | ✓ 13 |
| 2 | KC@LV | Patrick Mahomes 200+ pass yds | 78% | ✓ 225 |
| 3 | NE@BUF | DJ Moore 2+ receptions | 78% | ✗ 1 |
| 4 | GB@TB | Cade Otton 20+ rec yds | 78% | ✓ 37 |
| 5 | JAX@CIN | Brian Thomas Jr. 20+ rec yds | 78% | ✗ 17 |
| 6 | LA@PHI | Kyren Williams 40+ rush yds | 78% | ✓ 80 |

**8-leg** — 13.7% · fair +631 — 6/8 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | MIA@MIN | T.J. Hockenson 2+ receptions | 78% | ✓ 13 |
| 2 | KC@LV | Patrick Mahomes 200+ pass yds | 78% | ✓ 225 |
| 3 | NE@BUF | DJ Moore 2+ receptions | 78% | ✗ 1 |
| 4 | GB@TB | Cade Otton 20+ rec yds | 78% | ✓ 37 |
| 5 | JAX@CIN | Brian Thomas Jr. 20+ rec yds | 78% | ✗ 17 |
| 6 | LA@PHI | Kyren Williams 40+ rush yds | 78% | ✓ 80 |
| 7 | DAL@HOU | C.J. Stroud 225+ pass yds | 78% | ✓ 347 |
| 8 | ARI@NYG | Cam Skattebo 50+ rush yds | 78% | ✓ 58 |

**10-leg** — 7.9% · fair +1163 — 8/10 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | MIA@MIN | T.J. Hockenson 2+ receptions | 78% | ✓ 13 |
| 2 | KC@LV | Patrick Mahomes 200+ pass yds | 78% | ✓ 225 |
| 3 | NE@BUF | DJ Moore 2+ receptions | 78% | ✗ 1 |
| 4 | GB@TB | Cade Otton 20+ rec yds | 78% | ✓ 37 |
| 5 | TEN@BAL | Mark Andrews 2+ receptions | 78% | ✓ 5 |
| 6 | JAX@CIN | Brian Thomas Jr. 20+ rec yds | 78% | ✗ 17 |
| 7 | LA@PHI | Kyren Williams 40+ rush yds | 78% | ✓ 80 |
| 8 | DAL@HOU | C.J. Stroud 225+ pass yds | 78% | ✓ 347 |
| 9 | ARI@NYG | Cam Skattebo 50+ rush yds | 78% | ✓ 58 |
| 10 | GB@TB | Bucky Irving 10+ carries | 78% | ✓ 16 |

**12-leg** — 5.3% · fair +1781 — 9/12 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | MIA@MIN | T.J. Hockenson 2+ receptions | 78% | ✓ 13 |
| 2 | KC@LV | Patrick Mahomes 200+ pass yds | 78% | ✓ 225 |
| 3 | NE@BUF | DJ Moore 2+ receptions | 78% | ✗ 1 |
| 4 | GB@TB | Cade Otton 20+ rec yds | 78% | ✓ 37 |
| 5 | TEN@BAL | Mark Andrews 2+ receptions | 78% | ✓ 5 |
| 6 | JAX@CIN | Brian Thomas Jr. 20+ rec yds | 78% | ✗ 17 |
| 7 | DAL@HOU | CeeDee Lamb 4+ receptions | 78% | ✓ 17 |
| 8 | LA@PHI | Kyren Williams 40+ rush yds | 78% | ✓ 80 |
| 9 | DAL@HOU | C.J. Stroud 225+ pass yds | 78% | ✓ 347 |
| 10 | ARI@NYG | Cam Skattebo 50+ rush yds | 78% | ✓ 58 |
| 11 | GB@TB | Bucky Irving 10+ carries | 78% | ✓ 16 |
| 12 | KC@LV | Travis Kelce 30+ rec yds | 78% | ✗ 15 |


### ATD board (top 16) — Week 4 — Sunday Oct 4 2026 (floor, v1.8/v1.9)

| # | Game | Player | Model | Fair | Result |
|---|---|---|---|---|---|
| 1 | TEN@BAL | Derrick Henry (RB) | 65% | -184 | ✓ TD |
| 2 | IND@WAS | Jonathan Taylor (RB) | 61% | -156 | ✓ TD |
| 3 | DET@CAR | Jahmyr Gibbs (RB) | 56% | -126 | ✓ TD |
| 4 | NYJ@CHI | D'Andre Swift (RB) | 54% | -117 | ✗ no TD |
| 5 | DEN@SF | Christian McCaffrey (RB) | 49% | +103 | ✓ TD |
| 6 | DAL@HOU | David Montgomery (RB) | 49% | +104 | ✗ no TD |
| 7 | IND@WAS | Tyler Warren (TE) | 45% | +124 | ✗ no TD |
| 8 | LA@PHI | Kyren Williams (RB) | 45% | +124 | ✓ TD |
| 9 | KC@LV | Kenneth Walker III (RB) | 45% | +124 | ✓ TD |
| 10 | ARI@NYG | Cam Skattebo (RB) | 43% | +133 | ✗ no TD |
| 11 | NE@BUF | James Cook (RB) | 43% | +134 | ✓ TD |
| 12 | KC@LV | Ashton Jeanty (RB) | 43% | +135 | ✗ no TD |
| 13 | DAL@HOU | Woody Marks (RB) | 42% | +137 | ✓ TD |
| 14 | NE@BUF | Rhamondre Stevenson (RB) | 40% | +148 | ✓ TD |
| 15 | MIA@MIN | Aaron Jones (RB) | 40% | +153 | ✗ no TD |
| 16 | JAX@CIN | Chase Brown (RB) | 39% | +155 | ✗ no TD |

Board: top-16 9/16 · top-8 5/8 · chalk triple 3/3

**2+ TD board (singles only):** Derrick Henry 28% (+257) · Jonathan Taylor 24% (+314) · Jahmyr Gibbs 20% (+408) · D'Andre Swift 18% (+450) · Christian McCaffrey 15% (+576) · David Montgomery 15% (+581)


### Scorecard — Week 4 — Sunday Oct 4 2026 (floor, v1.8/v1.9)

**Legs 72/102 = 71% actual vs 77% expected · SGP4 3/14 · SGP6 2/14 · SGP8 1/14**

| Game | Final | Legs | SGP4 | SGP6 | SGP8 |
|---|---|---|---|---|---|
| DET@CAR | 26-32 | 8/8 | ✓ | ✓ | ✓ |
| GB@TB | 17-14 | 7/8 | ✓ | ✓ | ✗ |
| ARI@NYG | 24-36 | 6/7 | ✗ | ✗ | ✗ |
| DAL@HOU | 34-30 | 6/8 | ✗ | ✗ | ✗ |
| NE@BUF | 29-26 | 6/8 | ✗ | ✗ | ✗ |
| KC@LV | 30-27 | 6/7 | ✗ | ✗ | ✗ |
| IND@WAS | 30-13 | 5/8 | ✗ | ✗ | ✗ |
| LA@PHI | 24-20 | 5/8 | ✓ | ✗ | ✗ |
| TEN@BAL | 18-24 | 5/8 | ✗ | ✗ | ✗ |
| DEN@SF | 14-24 | 5/8 | ✗ | ✗ | ✗ |
| LAC@SEA | 23-30 | 4/6 | ✗ | ✗ | ✗ |
| JAX@CIN | 22-17 | 3/8 | ✗ | ✗ | ✗ |
| NYJ@CHI | 12-23 | 3/7 | ✗ | ✗ | ✗ |
| MIA@MIN | 10-15 | 3/3 | ✗ | ✗ | ✗ |


## Week 4 — aggressive band (55–68%)

*Engine v1.8.* "A true full slate with higher milestones" — same engine, legs one to two rungs higher.


### IND@WAS — final 30-13
*O/U 46.5 · spread -4.5 · outdoor · grass · 09:30 ET*

**Injury report (as built):** IND OFF · Keenan Allen (WR) — Questionable · Not injury related - resting player · DNP; IND OFF · Ashton Dulin (WR) — Questionable · Ankle; WAS OFF · Sam Cosmi (G) — Out · Concussion · DNP; WAS OFF · Rachaad White (RB) — Out · Shoulder · DNP; WAS DEF · Nick Cross (S) — Out · Illness · DNP; WAS OFF · Jayden Daniels (QB) — Out · Elbow; WAS OFF · Terry McLaurin (WR) — Questionable · Hamstring; WAS DEF · Percy Butler (S) — Questionable · Concussion

**Defensive leaks:** WAS D leaks rushing yards to RBs: x1.16; IND D leaks receiving yards to TEs: x1.23 (worsening x1.06 L4); IND D leaks receptions to TEs: x1.16 (worsening x1.11 L4); IND D leaks passing interceptions to QBs: x1.16

**Coordinators:** IND OC Jim Bob Cooter — continuity · measured pass 54% | DC Lou Anarumo (disguise_zone) · WAS OC David Blough — NEW (balanced) · measured pass 51% | DC Daronte Jones (zone_cover3)

**Props SGP** — 4-leg 15.0% · fair +567 ✗ · 6-leg 7.6% · fair +1219 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Daniel Jones 175+ pass yds | 63% | -169 | ✗ 143 | `4-leg core`
| 2 | Stefon Diggs 40+ rec yds | 61% | -154 | ✗ 35 | `4-leg core`
| 3 | Josh Downs 40+ rec yds | 61% | -154 | ✗ 16 | `4-leg core`
| 4 | Jonathan Taylor 70+ rush yds | 58% | -137 | ✓ 95 | `4-leg core`
| 5 | Jacory Croskey-Merritt 40+ rush yds | 58% | -136 | ✗ 15 | `+6`
| 6 | Stefon Diggs 4+ receptions | 65% | -185 | ✓ 5 | `+6`
| 7 | Daniel Jones o0.5 INT o0.5 | 65% | -185 | ✓ 1 INT | `+8`

Legs 3/7 (expected 4.3)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Jonathan Taylor (IND RB) | 61% | -156 | ✓ TD | share 28% · team 2.86 TD · RZ-D 1.16 · pos-D 1.08 |
| Tyler Warren (IND TE) | 45% | +124 | ✗ no TD | share 13% · team 2.86 TD · RZ-D 1.16 · pos-D 1.49 |
| Jacory Croskey-Merritt (WAS RB) | 28% | +255 | ✗ no TD | share 14% · team 2.35 TD · RZ-D 0.99 · pos-D 1.05 |

TD double (Jonathan Taylor + Tyler Warren): 31.7% · fair +215 ✗


### ARI@NYG — final 24-36
*O/U 44.5 · spread -2.5 · outdoor · turf · 13:00 ET*

**Injury report (as built):** ARI DEF · Dadrion Taylor-Demerson (S) — Out · Back · DNP; ARI DEF · Josh Sweat (LB) — Questionable · Not injury related - resting player; NYG OFF · John Michael Schmitz (C) — nan · DNP

**Defensive leaks:** NYG D leaks rushing yards to RBs: x1.19; ARI D leaks rushing yards to RBs: x1.15

**Coordinators:** ARI OC Nathaniel Hackett — NEW (run_heavy) · measured pass 60% | DC Nick Rallis (blitz_heavy) · NYG OC Matt Nagy — NEW (pass_wr) · measured pass 48% | DC Dennard Wilson (pressure)

**Props SGP** — 4-leg 18.8% · fair +432 **CASHED** · 6-leg 10.1% · fair +891 ✗ · 8-leg 5.3% · fair +1785 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Jacoby Brissett 150+ pass yds | 62% | -165 | ✓ 166 | `4-leg core`
| 2 | Malachi Fields 30+ rec yds | 61% | -159 | ✓ 52 | `4-leg core`
| 3 | Isaiah Likely 3+ receptions | 63% | -170 | ✓ 7 | `4-leg core`
| 4 | Jeremiyah Love 50+ rush yds | 61% | -157 | ✓ 63 | `4-leg core`
| 5 | Kendrick Bourne 3+ receptions | 61% | -156 | – DNP | `+6`
| 6 | Michael Wilson 40+ rec yds | 61% | -154 | ✓ 95 | `+6`
| 7 | Cam Skattebo 70+ rush yds | 60% | -147 | ✗ 58 | `+8`
| 8 | Jameis Winston o0.5 INT o0.5 | 57% | -132 | ✓ 2 INT | `+8`

Legs 6/7 (expected 4.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Cam Skattebo (NYG RB) | 43% | +133 | ✗ no TD | share 19% · team 2.35 TD · RZ-D 1.14 · pos-D 1.17 |
| Trey McBride (ARI TE) | 35% | +187 | ✗ no TD | share 19% · team 2.63 TD · RZ-D 1.11 · pos-D 0.83 |
| Tyler Allgeier (ARI RB) | 35% | +188 | ✓ TD | share 14% · team 2.63 TD · RZ-D 1.11 · pos-D 1.14 |

TD double (Cam Skattebo + Trey McBride): 17.1% · fair +484 ✗


### DAL@HOU — final 34-30
*O/U 48.5 · spread +3.0 · indoor · turf · 13:00 ET*

**Injury report (as built):** DAL DEF · Cobie Durant (CB) — Out · Hamstring · DNP; DAL DEF · DeMarvion Overshown (LB) — Out · Hamstring · DNP; HOU DEF · M.J. Stewart (S) — Out · Knee · DNP; HOU DEF · Azeez Al-Shaair (LB) — Out · Groin · DNP; HOU DEF · Jadeveon Clowney (DE) — Questionable · Knee · DNP; HOU DEF · Jake Hansen (LB) — Questionable · Calf; HOU DEF · Logan Hall (DE) — Questionable · Knee; HOU OFF · Ed Ingram (G) — Questionable · Groin

**Defensive leaks:** HOU D leaks passing interceptions to QBs: x1.46; DAL D leaks receiving yards to RBs: x1.24; DAL D leaks receiving yards to WRs: x1.12; DAL D leaks passing yards to QBs: x1.08

**Coordinators:** DAL OC Klayton Adams — continuity · measured pass 60% | DC Christian Parker (two_high_shell) · HOU OC Nick Caley — continuity · measured pass 63% | DC Matt Burke (four_man_rush)

**Props SGP** — 4-leg 18.5% · fair +441 **CASHED** · 6-leg 8.9% · fair +1027 **CASHED** · 8-leg 5.1% · fair +1841 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | George Pickens 50+ rec yds | 62% | -165 | ✓ 75 | `4-leg core`
| 2 | CeeDee Lamb 5+ receptions | 62% | -161 | ✓ 17 | `4-leg core`
| 3 | David Montgomery 10+ carries | 61% | -159 | ✓ 10 | `4-leg core`
| 4 | Xavier Hutchinson 30+ rec yds | 61% | -157 | ✓ 46 | `4-leg core`
| 5 | Javonte Williams 50+ rush yds | 63% | -171 | ✓ 62 | `+6`
| 6 | Dak Prescott 200+ pass yds | 60% | -153 | ✓ 335 | `+6`
| 7 | C.J. Stroud 35+ pass att | 58% | -140 | ✗ 31 | `+8`
| 8 | Dalton Schultz 5+ receptions | 58% | -137 | ✗ 2 | `+8`

Legs 6/8 (expected 4.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| David Montgomery (HOU RB) | 49% | +104 | ✗ no TD | share 19% · team 2.88 TD · RZ-D 1.15 · pos-D 1.14 |
| Woody Marks (HOU RB) | 42% | +137 | ✓ TD | share 16% · team 2.88 TD · RZ-D 1.15 · pos-D 1.14 |
| Javonte Williams (DAL RB) | 37% | +170 | ✓ TD | share 20% · team 2.55 TD · RZ-D 0.98 · pos-D 0.91 |

TD double (David Montgomery + Woody Marks): 25.3% · fair +295 ✗


### GB@TB — final 17-14
*O/U 38.5 · spread -3.0 · outdoor · grass · 13:00 ET*

**Injury report (as built):** GB OFF · Aaron Banks (G) — Out · Knee · DNP; GB OFF · Jacob Monk (C) — Out · Quadricep · DNP; GB DEF · Warren Brinson (DT) — Out · Calf · DNP; GB DEF · Anthony Campbell (DT) — Out · Ankle · DNP; GB DEF · Edgerrin Cooper (LB) — Questionable · Shoulder; GB OFF · Jager Burton (C) — Questionable · Groin; TB OFF · Baker Mayfield (QB) — Out · Thumb · DNP; TB OFF · Ko Kieft (TE) — Out · Elbow · DNP

**Defensive leaks:** TB D leaks receiving yards to RBs: x1.40; TB D leaks receiving yards to TEs: x1.19; TB D leaks receptions to RBs: x1.17 (worsening x1.29 L4); GB D leaks receptions to RBs: x1.10

**Coordinators:** GB OC Adam Stenavich — continuity · measured pass 72% | DC Jonathan Gannon (two_high_shell) · TB OC Zac Robinson — NEW (pass_wr) · measured pass 60% | DC Todd Bowles (blitz_heavy)

**Props SGP** — 4-leg 18.3% · fair +447 ✗ · 6-leg 10.1% · fair +887 ✗ · 8-leg 5.7% · fair +1653 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Emeka Egbuka 30+ rec yds | 62% | -166 | ✗ 13 | `4-leg core`
| 2 | Chris Godwin Jr. 3+ receptions | 63% | -168 | ✓ 6 | `4-leg core`
| 3 | MarShawn Lloyd 30+ rush yds | 61% | -154 | ✗ 13 | `4-leg core`
| 4 | Tucker Kraft 40+ rec yds | 60% | -152 | ✓ 42 | `4-leg core`
| 5 | Jordan Love 200+ pass yds | 64% | -180 | ✗ 197 | `+6`
| 6 | Christian Watson 4+ receptions | 59% | -145 | ✗ 3 | `+6`
| 7 | Bucky Irving 40+ rush yds | 66% | -191 | ✓ 61 | `+8`
| 8 | Jordan Love 30+ pass att | 57% | -135 | ✓ 30 | `+8`

Legs 4/8 (expected 4.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Bucky Irving (TB RB) | 27% | +266 | ✗ no TD | share 15% · team 1.99 TD · RZ-D 1.09 · pos-D 1.02 |
| Christian Watson (GB WR) | 27% | +275 | ✗ no TD | share 14% · team 2.32 TD · RZ-D 1.04 · pos-D 0.95 |
| Emeka Egbuka (TB WR) | 22% | +348 | ✗ no TD | share 11% · team 1.99 TD · RZ-D 1.09 · pos-D 1.09 |

TD double (Bucky Irving + Christian Watson): 8.9% · fair +1024 ✗


### JAX@CIN — final 22-17
*O/U 51.5 · spread +2.5 · outdoor · turf · 13:00 ET*

**Injury report (as built):** CIN DEF · Kyle Dugger (S) — Out · Quadricep · DNP; CIN OFF · Colbie Young (WR) — Out · Knee · DNP; CIN DEF · B.J. Hill (DT) — Questionable · Achilles; CIN OFF · Dalton Risner (G) — Questionable · Knee; CIN DEF · Bryan Cook (S) — Questionable · Ankle; CIN DEF · Swayze Bozeman (LB) — Questionable · Groin · DNP; CIN DEF · Dexter Lawrence (DT) — nan · DNP; JAX DEF · Montaric Brown (CB) — Questionable · Hamstring

**Defensive leaks:** CIN D leaks receiving yards to TEs: x1.48 (worsening x1.29 L4); CIN D leaks receptions to TEs: x1.30 (worsening x1.14 L4); CIN D leaks receiving yards to RBs: x1.19 (worsening x1.26 L4); JAX D leaks passing interceptions to QBs: x1.23 (worsening x1.54 L4)

**Coordinators:** JAX OC Grant Udinski — continuity · measured pass 49% | DC Anthony Campanile (pressure) · CIN OC Dan Pitcher — continuity · measured pass 60% | DC Al Golden (disguise_zone)

**Props SGP** — 4-leg 19.1% · fair +423 ✗ · 6-leg 9.2% · fair +985 ✗ · 8-leg 5.8% · fair +1638 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Chase Brown 60+ rush yds | 62% | -159 | ✗ 10 | `4-leg core`
| 2 | Mike Gesicki 3+ receptions | 63% | -169 | ✓ 3 | `4-leg core`
| 3 | Parker Washington 40+ rec yds | 61% | -158 | ✗ 7 | `4-leg core`
| 4 | Jakobi Meyers 40+ rec yds | 63% | -170 | ✗ 33 | `4-leg core`
| 5 | Trevor Lawrence o0.5 INT o0.5 | 60% | -153 | ✗ 0 INT | `+6`
| 6 | Bhayshul Tuten 30+ rush yds | 59% | -146 | ✓ 73 | `+6`
| 7 | Tee Higgins 5+ receptions | 65% | -184 | ✓ 11 | `+8`
| 8 | Joe Burrow 250+ pass yds | 57% | -132 | ✓ 428 | `+8`

Legs 4/8 (expected 4.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Chase Brown (CIN RB) | 39% | +155 | ✗ no TD | share 20% · team 3.02 TD · RZ-D 0.9 · pos-D 0.85 |
| Ja'Marr Chase (CIN WR) | 34% | +192 | ✗ no TD | share 16% · team 3.02 TD · RZ-D 0.9 · pos-D 0.92 |
| Tee Higgins (CIN WR) | 28% | +252 | ✗ no TD | share 13% · team 3.02 TD · RZ-D 0.9 · pos-D 0.92 |

TD double (Chase Brown + Ja'Marr Chase): 17.7% · fair +466 ✗


### LA@PHI — final 24-20
*O/U 42.5 · spread -3.5 · outdoor · grass · 13:00 ET*

**Injury report (as built):** LA DEF · Aaron Donald (DT) — Out · Back · DNP; LA DEF · Jaylen Watson (CB) — Out · Shoulder · DNP; LA OFF · Terrance Ferguson (TE) — Out · Ankle · DNP; LA OFF · Colby Parkinson (TE) — Questionable · Knee · DNP; LA DEF · Josaiah Stewart (LB) — Questionable · Groin · DNP; LA OFF · Tyler Higbee (TE) — nan · DNP; LA OFF · Alaric Jackson (T) — nan · DNP; PHI OFF · Dallas Goedert (TE) — Out · Knee · DNP

**Defensive leaks:** LA D leaks passing interceptions to QBs: x1.23 (worsening x1.16 L4); LA D leaks receiving yards to RBs: x1.12; LA D leaks receptions to TEs: x1.08

**Coordinators:** LA OC Nathan Scheelhaase — NEW (pass_wr) · measured pass 59% | DC Chris Shula (four_man_rush) · PHI OC Sean Mannion — NEW (run_heavy) · measured pass 54% | DC Vic Fangio (two_high_shell)

**Props SGP** — 4-leg 24.8% · fair +304 ✗ · 6-leg 9.7% · fair +926 ✗ · 8-leg 7.2% · fair +1291 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Tyler Higbee 3+ receptions | 62% | -164 | ✓ 5 | `4-leg core`
| 2 | Matthew Stafford 30+ pass att | 62% | -160 | ✓ 51 | `4-leg core`
| 3 | Davante Adams 5+ receptions | 63% | -172 | ✗ 4 | `4-leg core`
| 4 | Jalen Hurts 30+ rush yds | 61% | -155 | ✗ 18 | `4-leg core`
| 5 | Blake Corum 30+ rush yds | 64% | -177 | ✗ 14 | `+6`
| 6 | Dontayvion Wicks 20+ rec yds | 66% | -193 | ✗ 18 | `+6`
| 7 | Matthew Stafford o0.5 INT o0.5 | 65% | -183 | ✓ 2 INT | `+8`
| 8 | Davante Adams 70+ rec yds | 58% | -141 | ✗ 32 | `+8`

Legs 3/8 (expected 5.0)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Kyren Williams (LA RB) | 45% | +124 | ✓ TD | share 23% · team 2.58 TD · RZ-D 0.95 · pos-D 1.02 |
| Davante Adams (LA WR) | 32% | +210 | ✗ no TD | share 20% · team 2.58 TD · RZ-D 0.95 · pos-D 0.78 |
| Saquon Barkley (PHI RB) | 28% | +262 | ✗ no TD | share 21% · team 2.18 TD · RZ-D 0.88 · pos-D 0.76 |

TD double (Kyren Williams + Davante Adams): 18.6% · fair +436 ✗


### NE@BUF — final 29-26
*O/U 49.5 · spread +7.0 · outdoor · turf · 13:00 ET*

**Injury report (as built):** BUF DEF · T.J. Sanders (DE) — Doubtful · Illness; BUF DEF · Christian Benford (CB) — Questionable · Toe · DNP; BUF OFF · Ray Davis (RB) — Questionable · Hamstring; BUF DEF · Sam Franklin Jr. (S) — nan · DNP; BUF DEF · Terrel Bernard (LB) — nan · DNP; NE DEF · Christian Barmore (DT) — Out · Shoulder · DNP; NE DEF · Brenden Schooler (S) — Out · Back; NE DEF · Christian Gonzalez (CB) — Out · Shoulder · DNP

**Defensive leaks:** BUF D leaks passing interceptions to QBs: x1.12; BUF D leaks receptions to RBs: x1.11 (worsening x1.07 L4); BUF D leaks receiving yards to RBs: x1.09

**Coordinators:** NE OC Josh McDaniels — continuity · measured pass 50% | DC Zak Kuhr (multiple) · BUF OC Pete Carmichael Jr. — NEW (balanced) · measured pass 49% | DC Jim Leonhard (disguise_zone)

**Props SGP** — 4-leg 15.3% · fair +554 ✗ · 6-leg 8.3% · fair +1105 ✗ · 8-leg 5.6% · fair +1679 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | TreVeyon Henderson 30+ rush yds | 62% | -165 | ✓ 42 | `4-leg core`
| 2 | Josh Allen 30+ rush yds | 60% | -152 | ✗ 4 | `4-leg core`
| 3 | Khalil Shakir 20+ rec yds | 64% | -179 | ✓ 82 | `4-leg core`
| 4 | Mack Hollins 30+ rec yds | 60% | -148 | ✓ 53 | `4-leg core`
| 5 | DJ Moore 3+ receptions | 65% | -185 | ✗ 1 | `+6`
| 6 | James Cook 15+ carries | 66% | -196 | ✗ 12 | `+6`
| 7 | Dalton Kincaid 3+ receptions | 66% | -197 | ✗ 1 | `+8`
| 8 | Drake Maye 175+ pass yds | 68% | -212 | ✓ 269 | `+8`

Legs 4/8 (expected 5.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| James Cook (BUF RB) | 43% | +134 | ✓ TD | share 20% · team 3.16 TD · RZ-D 1.07 · pos-D 0.85 |
| Rhamondre Stevenson (NE RB) | 40% | +148 | ✓ TD | share 17% · team 2.38 TD · RZ-D 1.04 · pos-D 1.22 |
| TreVeyon Henderson (NE RB) | 36% | +174 | ✗ no TD | share 15% · team 2.38 TD · RZ-D 1.04 · pos-D 1.22 |

TD double (James Cook + Rhamondre Stevenson): 19.5% · fair +412 **CASHED**


### NYJ@CHI — final 12-23
*O/U 43.5 · spread +3.5 · outdoor · grass · 13:00 ET*

**Injury report (as built):** CHI DEF · Cam Lewis (S) — Doubtful · Hip · DNP; CHI OFF · Braxton Jones (T) — Out · Knee · DNP; CHI DEF · Kyler Gordon (CB) — Out · Calf; CHI DEF · Noah Sewell (LB) — Out · Achilles; CHI OFF · Caleb Williams (QB) — Out · Hamstring · DNP; CHI DEF · Shemar Turner (DE) — Out · Knee; NYJ OFF · Dylan Parham (G) — Out · Knee · DNP; NYJ OFF · Breece Hall (RB) — Out · Quadricep · DNP

**Defensive leaks:** CHI D leaks passing interceptions to QBs: x1.43; CHI D leaks rushing yards to RBs: x1.17; NYJ D leaks carries to RBs: x1.11

**Coordinators:** NYJ OC Frank Reich — NEW (balanced) · measured pass 55% | DC Brian Duker (multiple) · CHI OC Press Taylor — NEW (pass_wr) · measured pass 48% | DC Dennis Allen (blitz_man)

**Props SGP** — 4-leg 15.9% · fair +528 ✗ · 6-leg 9.8% · fair +916 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Luther Burden III 40+ rec yds | 62% | -166 | ✓ 63 | `4-leg core`
| 2 | Kyle Monangai 30+ rush yds | 61% | -156 | ✓ 146 | `4-leg core`
| 3 | Garrett Wilson 6+ receptions | 60% | -153 | ✗ 3 | `4-leg core`
| 4 | Kalif Raymond 4+ receptions | 60% | -150 | ✗ 2 | `4-leg core`
| 5 | Rome Odunze 30+ rec yds | 59% | -146 | ✓ 94 | `+6`
| 6 | Geno Smith 25+ pass att | 65% | -189 | ✗ 15 | `+6`
| 7 | Geno Smith 200+ pass yds | 58% | -136 | ✗ 119 | `+8`

Legs 3/7 (expected 4.3)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| D'Andre Swift (CHI RB) | 54% | -117 | ✗ no TD | share 19% · team 2.63 TD · RZ-D 1.17 · pos-D 1.43 |
| Kyle Monangai (CHI RB) | 39% | +156 | ✓ TD | share 12% · team 2.63 TD · RZ-D 1.17 · pos-D 1.43 |
| Garrett Wilson (NYJ WR) | 28% | +262 | ✗ no TD | share 12% · team 2.24 TD · RZ-D 0.99 · pos-D 1.17 |

TD double (D'Andre Swift + Kyle Monangai): 25.6% · fair +290 ✗


### TEN@BAL — final 18-24
*O/U 42.5 · spread +11.5 · outdoor · grass · 13:00 ET*

**Injury report (as built):** BAL OFF · Ethan Pocic (C) — Out · Knee · DNP; BAL DEF · Trey Hendrickson (LB) — Out · Finger · DNP; BAL OFF · Jovaughn Gwyn (C) — Out · Ankle · DNP; BAL OFF · Chris Moore (WR) — Questionable · Ankle; BAL OFF · Ronnie Stanley (T) — Questionable · Toe · DNP; BAL OFF · Zay Flowers (WR) — Questionable · Hamstring; TEN OFF · Tyjae Spears (RB) — Questionable · Ankle; TEN DEF · Kevin Winston Jr. (S) — Questionable · Shoulder · DNP

**Defensive leaks:** BAL D leaks receiving yards to RBs: x1.23; BAL D leaks receptions to RBs: x1.20; BAL D leaks receiving yards to WRs: x1.16

**Coordinators:** TEN OC Brian Daboll — NEW (pass_wr) · measured pass 58% | DC Gus Bradley (zone_cover3) · BAL OC Declan Doyle — NEW (pass_wr) · measured pass 44% | DC Anthony Weaver (pressure)

**Props SGP** — 4-leg 26.2% · fair +282 ✗ · 6-leg 16.5% · fair +508 ✗ · 8-leg 5.0% · fair +1900 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Wan'Dale Robinson 40+ rec yds | 62% | -164 | ✗ 19 | `4-leg core`
| 2 | Carnell Tate 4+ receptions | 62% | -165 | ✓ 9 | `4-leg core`
| 3 | Cam Ward 150+ pass yds | 63% | -169 | ✓ 222 | `4-leg core`
| 4 | Mark Andrews 3+ receptions | 65% | -183 | ✓ 5 | `4-leg core`
| 5 | Lamar Jackson 20+ pass att | 59% | -145 | ✓ 20 | `+6`
| 6 | Rashod Bateman 20+ rec yds | 65% | -187 | ✓ 46 | `+6`
| 7 | Derrick Henry 100+ rush yds | 58% | -138 | ✗ 73 | `+8`
| 8 | Tony Pollard 50+ rush yds | 57% | -131 | ✗ 48 | `+8`

Legs 5/8 (expected 4.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Derrick Henry (BAL RB) | 65% | -184 | ✓ TD | share 29% · team 3.02 TD · RZ-D 1.12 · pos-D 1.11 |
| Mark Andrews (BAL TE) | 30% | +236 | ✓ TD | share 11% · team 3.02 TD · RZ-D 1.12 · pos-D 1.05 |
| Tony Pollard (TEN RB) | 24% | +326 | ✓ TD | share 16% · team 1.74 TD · RZ-D 0.91 · pos-D 1.02 |

TD double (Derrick Henry + Mark Andrews): 23.2% · fair +331 **CASHED**


### MIA@MIN — final 10-15
*O/U 38.5 · spread +10.0 · indoor · turf · 16:05 ET*

**Injury report (as built):** MIA DEF · Rob Beal Jr. (LB) — Out · Hamstring · DNP; MIA DEF · Storm Duck (CB) — Out · Knee; MIA OFF · Caleb Douglas (WR) — Out · Ankle · DNP; MIN OFF · Justin Jefferson (WR) — Out · Ankle · DNP; MIN DEF · Charles Demmings (CB) — Out · Hamstring · DNP; MIN OFF · Brett Thorson (P) — Out · Hamstring · DNP; MIN OFF · Christian Darrisaw (T) — nan · DNP

**Defensive leaks:** MIN D leaks passing interceptions to QBs: x1.39 (worsening x1.37 L4); MIA D leaks receiving yards to TEs: x1.19 (worsening x1.13 L4); MIA D leaks receptions to TEs: x1.16

**Coordinators:** MIA OC Bobby Slowik — NEW (pass_wr) · measured pass 52% | DC Sean Duggan (multiple) · MIN OC Wes Phillips — continuity · measured pass 46% | DC Brian Flores (blitz_man)

**Props SGP** — 4-leg 16.7% · fair +498 **CASHED** · 6-leg —  · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | T.J. Hockenson 3+ receptions | 62% | -163 | ✓ 13 | `4-leg core`
| 2 | Malik Washington 20+ rec yds | 63% | -167 | ✓ 67 | `4-leg core`
| 3 | Aaron Jones 50+ rush yds | 63% | -169 | ✓ 94 | `4-leg core`
| 4 | Jordan Addison 30+ rec yds | 60% | -148 | ✓ 52 | `4-leg core`
| 5 | Malik Washington 3+ receptions | 59% | -143 | ✓ 5 | `+6`

Legs 5/5 (expected 3.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Aaron Jones (MIN RB) | 40% | +153 | ✗ no TD | share 15% · team 2.72 TD · RZ-D 1.14 · pos-D 1.14 |
| Jordan Addison (MIN WR) | 28% | +251 | ✗ no TD | share 12% · team 2.72 TD · RZ-D 1.14 · pos-D 1.0 |
| T.J. Hockenson (MIN TE) | 21% | +369 | ✗ no TD | share 7% · team 2.72 TD · RZ-D 1.14 · pos-D 1.1 |

TD double (Aaron Jones + Jordan Addison): 15.2% · fair +556 ✗


### DEN@SF — final 14-24
*O/U 48.5 · spread +3.0 · outdoor · grass · 16:25 ET*

**Injury report (as built):** DEN DEF · Dondrea Tillman (LB) — Out · Hamstring · DNP; SF DEF · Nick Bosa (DE) — Out · Knee · DNP; SF DEF · Mykel Williams (DE) — Out · Knee; SF DEF · James Thompson Jr. (DT) — Out · Ankle · DNP; SF OFF · Mike Evans (WR) — Questionable · Ribs; SF DEF · Dre Greenlaw (LB) — Questionable · Quadricep; SF DEF · Keion White (DE) — Questionable · Hamstring; SF DEF · Jaden Dugger (LB) — Questionable · Shoulder

**Defensive leaks:** SF D leaks receptions to RBs: x1.23 (worsening x1.09 L4); SF D leaks receiving yards to RBs: x1.14; DEN D leaks passing interceptions to QBs: x1.12 (worsening x1.70 L4); DEN D leaks attempts to QBs: x1.09

**Coordinators:** DEN OC Davis Webb — NEW (balanced) · measured pass 58% | DC Vance Joseph (pressure) · SF OC Klay Kubiak — continuity · measured pass 51% | DC Raheem Morris (zone_cover3)

**Props SGP** — 4-leg 30.6% · fair +227 ✗ · 6-leg 13.4% · fair +644 ✗ · 8-leg 5.3% · fair +1784 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | George Kittle 60+ rec yds | 62% | -164 | ✓ 70 | `4-leg core`
| 2 | Deebo Samuel Sr. 30+ rec yds | 62% | -165 | ✗ 26 | `4-leg core`
| 3 | Brock Purdy 225+ pass yds | 62% | -167 | ✗ 218 | `4-leg core`
| 4 | Christian McCaffrey 5+ receptions | 64% | -175 | ✗ 3 | `4-leg core`
| 5 | Jaylen Waddle 3+ receptions | 64% | -180 | ✓ 5 | `+6`
| 6 | J.K. Dobbins 60+ rush yds | 59% | -144 | ✗ 40 | `+6`
| 7 | Bo Nix o0.5 INT o0.5 | 57% | -134 | ✗ 0 INT | `+8`
| 8 | Kaelon Black 40+ rush yds | 56% | -127 | ✗ 13 | `+8`

Legs 2/8 (expected 4.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Christian McCaffrey (SF RB) | 49% | +103 | ✓ TD | share 27% · team 2.88 TD · RZ-D 0.73 · pos-D 0.99 |
| J.K. Dobbins (DEN RB) | 31% | +222 | ✗ no TD | share 15% · team 2.55 TD · RZ-D 0.94 · pos-D 0.99 |
| RJ Harvey (DEN RB) | 30% | +229 | ✗ no TD | share 15% · team 2.55 TD · RZ-D 0.94 · pos-D 0.99 |

TD double (Christian McCaffrey + J.K. Dobbins): 17.3% · fair +478 ✗


### KC@LV — final 30-27
*O/U 47.5 · spread -4.5 · indoor · grass · 16:25 ET*

**Injury report (as built):** KC OFF · Josh Simmons (T) — Out · Back · DNP; LV OFF · Jackson Powers-Johnson (G) — Out · Groin · DNP; LV OFF · Aidan O'Connell (QB) — Questionable · Not injury related - personal matter · DNP

**Defensive leaks:** KC D leaks receiving yards to TEs: x1.10

**Coordinators:** KC OC Eric Bieniemy — NEW (pass_wr) · measured pass 52% | DC Steve Spagnuolo (blitz_heavy) · LV OC Andrew Janocko — NEW (run_heavy) · measured pass 50% | DC Rob Leonard (four_man_rush)

**Props SGP** — 4-leg 23.2% · fair +331 ✗ · 6-leg 13.8% · fair +623 ✗ · 8-leg 5.6% · fair +1674 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Kirk Cousins 150+ pass yds | 62% | -164 | ✓ 365 | `4-leg core`
| 2 | Xavier Worthy 3+ receptions | 62% | -165 | ✓ 4 | `4-leg core`
| 3 | Rashee Rice 60+ rec yds | 62% | -161 | – DNP | `4-leg core`
| 4 | Tre Tucker 4+ receptions | 60% | -153 | ✓ 4 | `4-leg core`
| 5 | Travis Kelce 50+ rec yds | 60% | -148 | ✗ 15 | `+6`
| 6 | Patrick Mahomes o0.5 INT o0.5 | 57% | -133 | ✗ 0 INT | `+6`
| 7 | Ashton Jeanty 20+ carries | 67% | -205 | ✗ 15 | `+8`
| 8 | Kenneth Walker III 100+ rush yds | 56% | -128 | ✓ 177 | `+8`

Legs 4/7 (expected 4.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Kenneth Walker III (KC RB) | 45% | +124 | ✓ TD | share 20% · team 2.91 TD · RZ-D 1.04 · pos-D 1.02 |
| Ashton Jeanty (LV RB) | 43% | +135 | ✗ no TD | share 25% · team 2.41 TD · RZ-D 0.94 · pos-D 0.93 |
| Rashee Rice (KC WR) | 32% | +212 | – DNP | share 14% · team 2.91 TD · RZ-D 1.04 · pos-D 0.95 |

TD double (Kenneth Walker III + Ashton Jeanty): 21.3% · fair +369 ✗


### LAC@SEA — final 23-30
*O/U 42.5 · spread +7.0 · outdoor · turf · 16:25 ET*

**Injury report (as built):** LAC DEF · Dalvin Tomlinson (DT) — Out · Hamstring · DNP; LAC OFF · Kayode Awosika (G) — Out · Fibula · DNP; LAC OFF · Charlie Kolar (TE) — Out · Forearm; LAC OFF · Brenen Thompson (WR) — Out · Quadricep · DNP; LAC DEF · Donte Jackson (CB) — Questionable · Concussion; LAC DEF · Derwin James (S) — Questionable · Hamstring; LAC DEF · Elijah Molden (S) — Questionable · Hamstring; LAC OFF · Trey Lance (QB) — Questionable · Groin

**Defensive leaks:** SEA D leaks passing interceptions to QBs: x1.35 (worsening x1.41 L4); SEA D leaks receptions to RBs: x1.13; SEA D leaks receiving yards to RBs: x1.09; LAC D leaks passing interceptions to QBs: x1.43

**Coordinators:** LAC OC Mike McDaniel — NEW (pass_rb) · measured pass 52% | DC Chris O'Leary (two_high_shell) · SEA OC Brian Fleury — NEW (run_heavy) · measured pass 55% | DC Aden Durde (four_man_rush)

**Props SGP** — 4-leg 17.6% · fair +467 ✗ · 6-leg 11.3% · fair +782 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Quentin Johnston 30+ rec yds | 62% | -165 | ✓ 44 | `4-leg core`
| 2 | Jaxon Smith-Njigba 6+ receptions | 62% | -166 | ✗ 5 | `4-leg core`
| 3 | Justin Herbert 25+ pass att | 61% | -158 | ✓ 31 | `4-leg core`
| 4 | Omarion Hampton 50+ rush yds | 65% | -182 | ✗ 45 | `4-leg core`
| 5 | Tre Harris 20+ rec yds | 66% | -189 | ✓ 60 | `+6`
| 6 | Quentin Johnston 3+ receptions | 63% | -167 | ✗ 1 | `+6`
| 7 | Justin Herbert o0.5 INT o0.5 | 65% | -184 | ✓ 2 INT | `+8`

Legs 4/7 (expected 4.4)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Jaxon Smith-Njigba (SEA WR) | 30% | +234 | ✗ no TD | share 16% · team 2.77 TD · RZ-D 0.84 · pos-D 0.86 |
| Omarion Hampton (LAC RB) | 23% | +327 | ✓ TD | share 20% · team 1.99 TD · RZ-D 0.88 · pos-D 0.73 |

TD double (Jaxon Smith-Njigba + Omarion Hampton): 8.6% · fair +1065 ✗


### DET@CAR — final 26-32
*O/U 51.5 · spread -3.5 · outdoor · grass · 20:20 ET*

**Injury report (as built):** CAR OFF · Damien Lewis (G) — Out · Elbow · DNP; CAR OFF · Xavier Legette (WR) — Out · Knee · DNP; CAR OFF · Jalen Coker (WR) — Questionable · Quadricep; CAR DEF · Cam Jackson (DT) — Questionable · Knee; CAR OFF · Monroe Freeling (T) — Questionable · Concussion; CAR DEF · Lee Hunter (DT) — Questionable · Foot; DET OFF · Ben Bartch (G) — Out · Foot · DNP; DET DEF · D.J. Reed (CB) — Questionable · Rib

**Defensive leaks:** CAR D leaks rushing yards to RBs: x1.36 (worsening x1.12 L4); CAR D leaks carries to RBs: x1.18; DET D leaks passing interceptions to QBs: x1.19; DET D leaks receiving yards to WRs: x1.19 (worsening x1.10 L4)

**Coordinators:** DET OC Drew Petzing — NEW (pass_te) · measured pass 57% | DC Kelvin Sheppard (pressure) · CAR OC Brad Idzik — continuity · measured pass 65% | DC Ejiro Evero (two_high_shell)

**Props SGP** — 4-leg 17.4% · fair +473 ✗ · 6-leg 10.0% · fair +905 ✗ · 8-leg 6.2% · fair +1511 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Bryce Young o0.5 INT o0.5 | 62% | -165 | ✗ 0 INT | `4-leg core`
| 2 | Sam LaPorta 50+ rec yds | 62% | -160 | ✓ 84 | `4-leg core`
| 3 | Tetairoa McMillan 50+ rec yds | 61% | -158 | ✓ 192 | `4-leg core`
| 4 | Jahmyr Gibbs 60+ rush yds | 60% | -151 | ✗ 46 | `4-leg core`
| 5 | Chuba Hubbard 50+ rush yds | 65% | -189 | ✓ 122 | `+6`
| 6 | Jared Goff 30+ pass att | 65% | -189 | ✓ 52 | `+6`
| 7 | Jameson Williams 3+ receptions | 66% | -197 | ✓ 6 | `+8`
| 8 | Darren Waller 3+ receptions | 57% | -134 | ✓ 3 | `+8`

Legs 6/8 (expected 5.0)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Jahmyr Gibbs (DET RB) | 56% | -126 | ✓ TD | share 23% · team 3.08 TD · RZ-D 1.0 · pos-D 1.14 |
| Chuba Hubbard (CAR RB) | 38% | +162 | ✓ TD | share 18% · team 2.69 TD · RZ-D 1.09 · pos-D 0.93 |
| Amon-Ra St. Brown (DET WR) | 38% | +165 | ✗ no TD | share 18% · team 3.08 TD · RZ-D 1.0 · pos-D 0.86 |

TD double (Jahmyr Gibbs + Chuba Hubbard): 23.4% · fair +327 **CASHED**


### Cross-game combos — Week 4 — aggressive band (55–68%)

**4-leg** — 15.0% · fair +568 — 3/4 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | TEN@BAL | Wan'Dale Robinson 40+ rec yds | 62% | ✗ 19 |
| 2 | LA@PHI | Tyler Higbee 3+ receptions | 62% | ✓ 5 |
| 3 | DEN@SF | George Kittle 60+ rec yds | 62% | ✓ 70 |
| 4 | MIA@MIN | T.J. Hockenson 3+ receptions | 62% | ✓ 13 |

**6-leg** — 5.9% · fair +1609 — 5/6 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | TEN@BAL | Wan'Dale Robinson 40+ rec yds | 62% | ✗ 19 |
| 2 | LA@PHI | Tyler Higbee 3+ receptions | 62% | ✓ 5 |
| 3 | DEN@SF | George Kittle 60+ rec yds | 62% | ✓ 70 |
| 4 | MIA@MIN | T.J. Hockenson 3+ receptions | 62% | ✓ 13 |
| 5 | KC@LV | Kirk Cousins 150+ pass yds | 62% | ✓ 365 |
| 6 | NE@BUF | TreVeyon Henderson 30+ rush yds | 62% | ✓ 42 |

**8-leg** — 2.3% · fair +4311 — 6/8 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | TEN@BAL | Wan'Dale Robinson 40+ rec yds | 62% | ✗ 19 |
| 2 | LA@PHI | Tyler Higbee 3+ receptions | 62% | ✓ 5 |
| 3 | DEN@SF | George Kittle 60+ rec yds | 62% | ✓ 70 |
| 4 | MIA@MIN | T.J. Hockenson 3+ receptions | 62% | ✓ 13 |
| 5 | KC@LV | Kirk Cousins 150+ pass yds | 62% | ✓ 365 |
| 6 | NE@BUF | TreVeyon Henderson 30+ rush yds | 62% | ✓ 42 |
| 7 | ARI@NYG | Jacoby Brissett 150+ pass yds | 62% | ✓ 166 |
| 8 | DET@CAR | Bryce Young o0.5 INT o0.5 | 62% | ✗ 0 INT |

**10-leg** — 1.1% · fair +9334 — 8/10 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | TEN@BAL | Wan'Dale Robinson 40+ rec yds | 62% | ✗ 19 |
| 2 | LA@PHI | Tyler Higbee 3+ receptions | 62% | ✓ 5 |
| 3 | DEN@SF | George Kittle 60+ rec yds | 62% | ✓ 70 |
| 4 | MIA@MIN | T.J. Hockenson 3+ receptions | 62% | ✓ 13 |
| 5 | TEN@BAL | Carnell Tate 4+ receptions | 62% | ✓ 9 |
| 6 | KC@LV | Kirk Cousins 150+ pass yds | 62% | ✓ 365 |
| 7 | LAC@SEA | Quentin Johnston 30+ rec yds | 62% | ✓ 44 |
| 8 | NE@BUF | TreVeyon Henderson 30+ rush yds | 62% | ✓ 42 |
| 9 | ARI@NYG | Jacoby Brissett 150+ pass yds | 62% | ✓ 166 |
| 10 | DET@CAR | Bryce Young o0.5 INT o0.5 | 62% | ✗ 0 INT |

**12-leg** — 0.4% · fair +25740 — 10/12 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | TEN@BAL | Wan'Dale Robinson 40+ rec yds | 62% | ✗ 19 |
| 2 | LA@PHI | Tyler Higbee 3+ receptions | 62% | ✓ 5 |
| 3 | DEN@SF | George Kittle 60+ rec yds | 62% | ✓ 70 |
| 4 | MIA@MIN | T.J. Hockenson 3+ receptions | 62% | ✓ 13 |
| 5 | TEN@BAL | Carnell Tate 4+ receptions | 62% | ✓ 9 |
| 6 | KC@LV | Kirk Cousins 150+ pass yds | 62% | ✓ 365 |
| 7 | LAC@SEA | Quentin Johnston 30+ rec yds | 62% | ✓ 44 |
| 8 | NE@BUF | TreVeyon Henderson 30+ rush yds | 62% | ✓ 42 |
| 9 | DAL@HOU | George Pickens 50+ rec yds | 62% | ✓ 75 |
| 10 | ARI@NYG | Jacoby Brissett 150+ pass yds | 62% | ✓ 166 |
| 11 | KC@LV | Xavier Worthy 3+ receptions | 62% | ✓ 4 |
| 12 | DET@CAR | Bryce Young o0.5 INT o0.5 | 62% | ✗ 0 INT |


### ATD board (top 16) — Week 4 — aggressive band (55–68%)

| # | Game | Player | Model | Fair | Result |
|---|---|---|---|---|---|
| 1 | TEN@BAL | Derrick Henry (RB) | 65% | -184 | ✓ TD |
| 2 | IND@WAS | Jonathan Taylor (RB) | 61% | -156 | ✓ TD |
| 3 | DET@CAR | Jahmyr Gibbs (RB) | 56% | -126 | ✓ TD |
| 4 | NYJ@CHI | D'Andre Swift (RB) | 54% | -117 | ✗ no TD |
| 5 | DEN@SF | Christian McCaffrey (RB) | 49% | +103 | ✓ TD |
| 6 | DAL@HOU | David Montgomery (RB) | 49% | +104 | ✗ no TD |
| 7 | IND@WAS | Tyler Warren (TE) | 45% | +124 | ✗ no TD |
| 8 | LA@PHI | Kyren Williams (RB) | 45% | +124 | ✓ TD |
| 9 | KC@LV | Kenneth Walker III (RB) | 45% | +124 | ✓ TD |
| 10 | ARI@NYG | Cam Skattebo (RB) | 43% | +133 | ✗ no TD |
| 11 | NE@BUF | James Cook (RB) | 43% | +134 | ✓ TD |
| 12 | KC@LV | Ashton Jeanty (RB) | 43% | +135 | ✗ no TD |
| 13 | DAL@HOU | Woody Marks (RB) | 42% | +137 | ✓ TD |
| 14 | NE@BUF | Rhamondre Stevenson (RB) | 40% | +148 | ✓ TD |
| 15 | MIA@MIN | Aaron Jones (RB) | 40% | +153 | ✗ no TD |
| 16 | JAX@CIN | Chase Brown (RB) | 39% | +155 | ✗ no TD |

Board: top-16 9/16 · top-8 5/8 · chalk triple 3/3

**2+ TD board (singles only):** Derrick Henry 28% (+257) · Jonathan Taylor 24% (+314) · Jahmyr Gibbs 20% (+408) · D'Andre Swift 18% (+450) · Christian McCaffrey 15% (+576) · David Montgomery 15% (+581)


### Scorecard — Week 4 — aggressive band (55–68%)

**Legs 59/104 = 57% actual vs 63% expected · SGP4 3/14 · SGP6 1/14 · SGP8 0/14**

| Game | Final | Legs | SGP4 | SGP6 | SGP8 |
|---|---|---|---|---|---|
| ARI@NYG | 24-36 | 6/7 | ✓ | ✗ | ✗ |
| DAL@HOU | 34-30 | 6/8 | ✓ | ✓ | ✗ |
| DET@CAR | 26-32 | 6/8 | ✗ | ✗ | ✗ |
| TEN@BAL | 18-24 | 5/8 | ✗ | ✗ | ✗ |
| MIA@MIN | 10-15 | 5/5 | ✓ | ✗ | ✗ |
| GB@TB | 17-14 | 4/8 | ✗ | ✗ | ✗ |
| JAX@CIN | 22-17 | 4/8 | ✗ | ✗ | ✗ |
| NE@BUF | 29-26 | 4/8 | ✗ | ✗ | ✗ |
| KC@LV | 30-27 | 4/7 | ✗ | ✗ | ✗ |
| LAC@SEA | 23-30 | 4/7 | ✗ | ✗ | ✗ |
| IND@WAS | 30-13 | 3/7 | ✗ | ✗ | ✗ |
| LA@PHI | 24-20 | 3/8 | ✗ | ✗ | ✗ |
| NYJ@CHI | 12-23 | 3/7 | ✗ | ✗ | ✗ |
| DEN@SF | 14-24 | 2/8 | ✗ | ✗ | ✗ |


## Week 5 — Sunday Oct 11 2026 (floor, v1.9b)

*Engine v1.9b.* Morning build with Friday designations. Report card (Week5-Report-Card.pdf): 72% vs 76%, SGP4 4/13, SGP6 4/13 (expected 3.6), SGP8 1/13. DET@ARI went 8/8 and all three SGPs cashed. All five cross-game combos died on one leg (Herbert 150+ → 121). Receiving yards 61% vs 75%, TE legs 65%, rush yards 65% — the same markets as Week 3, which led to the 708-leg calibration study and v1.9f.


### PHI@JAX — final 17-19
*O/U 41.5 · spread +7.5 · outdoor · grass · 09:30 ET*

**Injury report (as built):** JAX DEF · Eric Murray (S) — Doubtful · Concussion; JAX DEF · Jaylon Jones (CB) — Out · Hamstring; PHI OFF · Saquon Barkley (RB) — Out · Hamstring · DNP; PHI DEF · Marcus Epps (S) — Out · Groin · DNP; PHI OFF · Marquise Brown (WR) — Out · Ankle · DNP; PHI OFF · DeVonta Smith (WR) — Out · Hamstring · DNP; PHI OFF · Drew Kendall (C) — Out · Knee · DNP; PHI DEF · Jonathan Greenard (LB) — Questionable · Ankle · DNP

**Defensive leaks:** JAX D leaks passing interceptions to QBs: x1.27 (worsening x1.86 L4); JAX D leaks receiving yards to RBs: x1.21 (worsening x1.31 L4); JAX D leaks receptions to RBs: x1.21 (worsening x1.37 L4)

**Coordinators:** PHI OC Sean Mannion — NEW (run_heavy) · measured pass 53% | DC Vic Fangio (two_high_shell) · JAX OC Grant Udinski — continuity · measured pass 48% | DC Anthony Campanile (pressure)

**Props SGP** — 4-leg 42.0% · fair +138 ✗ · 6-leg 28.4% · fair +252 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Jakobi Meyers 3+ receptions | 78% | -346 | ✗ 2 | `4-leg core`
| 2 | Bhayshul Tuten 20+ rush yds | 77% | -328 | ✓ 72 | `4-leg core`
| 3 | Makai Lemon 1+ receptions | 81% | -434 | ✓ 5 | `4-leg core`
| 4 | Trevor Lawrence 20+ pass att | 82% | -458 | ✓ 39 | `4-leg core`
| 5 | Parker Washington 20+ rec yds | 74% | -277 | ✓ 124 | `+6`
| 6 | Brenton Strange 20+ rec yds | 72% | -255 | ✓ 68 | `+6`
| 7 | Trevor Lawrence 175+ pass yds | 70% | -237 | ✓ 331 | `+8`

Legs 6/7 (expected 5.3)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Trevor Lawrence (JAX QB) | 33% | +203 | ✗ no TD | share 9% · team 2.74 TD · RZ-D 0.97 · pos-D 1.71 |
| Jalen Hurts (PHI QB) | 32% | +211 | ✗ no TD | share 18% · team 1.9 TD · RZ-D 0.89 · pos-D 1.22 |
| Bhayshul Tuten (JAX RB) | 26% | +277 | ✗ no TD | share 11% · team 2.74 TD · RZ-D 0.97 · pos-D 1.04 |

TD double (Trevor Lawrence + Jalen Hurts): 12.5% · fair +702 ✗


### CHI@GB — final 7-31
*O/U 47.5 · spread -1.5 · outdoor · grass · 13:00 ET*

**Injury report (as built):** CHI OFF · Kyle Monangai (RB) — Out · Thumb · DNP; CHI DEF · Keyshaun Elliott (LB) — Out · Quadricep · DNP; CHI DEF · Kyler Gordon (CB) — Questionable · Calf; CHI DEF · Noah Sewell (LB) — Questionable · Achilles; CHI OFF · Caleb Williams (QB) — Questionable · Hamstring; CHI DEF · Shemar Turner (DE) — Questionable · Knee; GB OFF · Aaron Banks (G) — Doubtful · Knee; GB OFF · Jacob Monk (C) — Doubtful · Quadricep

**Defensive leaks:** GB D leaks receptions to RBs: x1.08; CHI D leaks passing interceptions to QBs: x1.39; CHI D leaks rushing yards to RBs: x1.16

**Coordinators:** CHI OC Press Taylor — NEW (pass_wr) · measured pass 45% | DC Dennis Allen (blitz_man) · GB OC Adam Stenavich — continuity · measured pass 68% | DC Jonathan Gannon (two_high_shell)

**Props SGP** — 4-leg 44.7% · fair +124 **CASHED** · 6-leg 25.9% · fair +286 **CASHED** · 8-leg 18.0% · fair +456 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Rome Odunze 2+ receptions | 78% | -350 | ✓ 3 | `4-leg core`
| 2 | Luther Burden III 3+ receptions | 78% | -365 | ✓ 4 | `4-leg core`
| 3 | Jordan Love 175+ pass yds | 77% | -343 | ✓ 367 | `4-leg core`
| 4 | Tucker Kraft 20+ rec yds | 76% | -318 | ✓ 64 | `4-leg core`
| 5 | Christian Watson 30+ rec yds | 75% | -296 | ✓ 143 | `+6`
| 6 | MarShawn Lloyd 20+ rush yds | 72% | -258 | ✓ 31 | `+6`
| 7 | D'Andre Swift 60+ rush yds | 71% | -241 | ✗ 43 | `+8`
| 8 | Jordan Love 25+ pass att | 82% | -471 | ✓ 31 | `+8`

Legs 7/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| D'Andre Swift (CHI RB) | 43% | +133 | ✓ TD | share 19% · team 2.74 TD · RZ-D 1.1 · pos-D 1.04 |
| Christian Watson (GB WR) | 31% | +219 | ✓ TD | share 13% · team 2.58 TD · RZ-D 0.97 · pos-D 1.16 |
| Rome Odunze (CHI WR) | 26% | +291 | ✗ no TD | share 10% · team 2.74 TD · RZ-D 1.1 · pos-D 1.06 |

TD double (D'Andre Swift + Christian Watson): 15.5% · fair +546 **CASHED**


### CIN@MIA — final 31-24
*O/U 44.5 · spread -7.0 · outdoor · grass · 13:00 ET*

**Injury report (as built):** CIN DEF · Kyle Dugger (S) — Out · Quadricep · DNP; CIN OFF · Tee Higgins (WR) — Questionable · Groin; CIN OFF · Ja'Marr Chase (WR) — Questionable · Concussion; CIN DEF · Bryan Cook (S) — Questionable · Ankle; CIN DEF · Swayze Bozeman (LB) — Questionable · Groin; CIN OFF · Colbie Young (WR) — Questionable · Knee; CIN DEF · B.J. Hill (DT) — nan · DNP; CIN DEF · Dexter Lawrence (DT) — nan · DNP

**Defensive leaks:** MIA D leaks receiving yards to TEs: x1.22 (worsening x1.58 L4); MIA D leaks receptions to TEs: x1.20 (worsening x1.23 L4); MIA D leaks receiving yards to RBs: x1.08; CIN D leaks receiving yards to TEs: x1.49 (worsening x1.64 L4)

**Coordinators:** CIN OC Dan Pitcher — continuity · measured pass 65% | DC Al Golden (disguise_zone) · MIA OC Bobby Slowik — NEW (pass_wr) · measured pass 52% | DC Sean Duggan (multiple)

**Props SGP** — 4-leg 44.1% · fair +127 ✗ · 6-leg 33.3% · fair +200 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Mike Gesicki 2+ receptions | 78% | -349 | ✗ 1 | `4-leg core`
| 2 | Chase Brown 3+ receptions | 76% | -317 | ✓ 3 | `4-leg core`
| 3 | Joe Burrow 30+ pass att | 82% | -440 | ✓ 32 | `4-leg core`
| 4 | Greg Dulcich 30+ rec yds | 72% | -260 | ✓ 37 | `4-leg core`
| 5 | Mike Gesicki 20+ rec yds | 73% | -268 | ✗ 4 | `+6`
| 6 | Joe Burrow 225+ pass yds | 72% | -256 | ✗ 190 | `+6`
| 7 | Chase Brown 50+ rush yds | 71% | -240 | ✗ 39 | `+8`

Legs 3/7 (expected 5.2)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Chase Brown (CIN RB) | 48% | +109 | ✗ no TD | share 20% · team 2.88 TD · RZ-D 1.1 · pos-D 1.1 |
| Ollie Gordon II (MIA RB) | 26% | +280 | ✓ TD | share 13% · team 2.1 TD · RZ-D 1.0 · pos-D 1.1 |
| Mike Gesicki (CIN TE) | 26% | +291 | ✓ TD | share 9% · team 2.88 TD · RZ-D 1.1 · pos-D 1.08 |

TD double (Chase Brown + Ollie Gordon II): 14.5% · fair +591 ✗


### CLE@NYJ — final 12-17
*O/U 38.5 · spread +2.5 · outdoor · turf · 13:00 ET*

**Injury report (as built):** CLE OFF · Tylan Wallace (WR) — Out · Knee · DNP; CLE OFF · Teven Jenkins (G) — Out · Back · DNP; CLE DEF · Kalia Davis (DT) — Out · Quadricep · DNP; CLE DEF · Mike Hall Jr. (DT) — Out · Ankle · DNP; CLE DEF · Mason Graham (DT) — Out · Knee · DNP; CLE OFF · Dillon Gabriel (QB) — Out · Back; CLE OFF · Carsen Ryan (TE) — Out · Calf · DNP; NYJ OFF · Dylan Parham (G) — Out · Knee · DNP

**Defensive leaks:** NYJ D leaks carries to RBs: x1.14 (worsening x1.25 L4); NYJ D leaks rushing yards to RBs: x1.11 (worsening x1.30 L4)

**Coordinators:** CLE OC Travis Switzer — NEW (run_heavy) · measured pass 53% | DC Mike Rutenberg (multiple) · NYJ OC Frank Reich — NEW (balanced) · measured pass 54% | DC Brian Duker (multiple)

**Props SGP** — 4-leg 39.2% · fair +155 ✗ · 6-leg 27.9% · fair +258 ✗ · 8-leg 22.3% · fair +348 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Denzel Boston 2+ receptions | 78% | -356 | ✓ 3 | `4-leg core`
| 2 | Garrett Wilson 3+ receptions | 78% | -344 | ✓ 7 | `4-leg core`
| 3 | Harold Fannin Jr. 20+ rec yds | 79% | -372 | ✗ 4 | `4-leg core`
| 4 | Quinshon Judkins 30+ rush yds | 77% | -333 | ✓ 44 | `4-leg core`
| 5 | Deshaun Watson 20+ pass att | 76% | -316 | ✓ 33 | `+6`
| 6 | KC Concepcion 20+ rec yds | 74% | -280 | ✗ 5 | `+6`
| 7 | Geno Smith 20+ pass att | 82% | -467 | ✓ 30 | `+8`
| 8 | Geno Smith 175+ pass yds | 73% | -267 | ✓ 182 | `+8`

Legs 6/8 (expected 6.2)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Quinshon Judkins (CLE RB) | 49% | +102 | ✗ no TD | share 22% · team 2.02 TD · RZ-D 1.11 · pos-D 1.42 |
| Garrett Wilson (NYJ WR) | 27% | +276 | ✓ TD | share 12% · team 2.3 TD · RZ-D 1.01 · pos-D 1.11 |
| Harold Fannin Jr. (CLE TE) | 26% | +288 | ✗ no TD | share 14% · team 2.02 TD · RZ-D 1.11 · pos-D 1.03 |

TD double (Quinshon Judkins + Garrett Wilson): 15.1% · fair +564 ✗


### HOU@TEN — final 26-3
*O/U 37.5 · spread -6.5 · outdoor · grass · 13:00 ET*

**Injury report (as built):** HOU OFF · Tank Dell (WR) — Out · Knee · DNP; HOU DEF · M.J. Stewart (S) — Questionable · Knee; HOU OFF · Braden Smith (T) — Questionable · Foot; HOU OFF · Ed Ingram (G) — Questionable · Illness; HOU OFF · Blake Fisher (T) — Questionable · Illness; HOU OFF · Aireontae Ersery (T) — Questionable · Illness · DNP; HOU DEF · Kayden McDonald (DT) — Questionable · Ankle; HOU DEF · Jadeveon Clowney (DE) — nan · DNP

**Defensive leaks:** HOU D leaks passing interceptions to QBs: x1.42

**Coordinators:** HOU OC Nick Caley — continuity · measured pass 63% | DC Matt Burke (four_man_rush) · TEN OC Brian Daboll — NEW (pass_wr) · measured pass 57% | DC Gus Bradley (zone_cover3)

**Props SGP** — 4-leg 45.4% · fair +120 **CASHED** · 6-leg 28.6% · fair +250 **CASHED** · 8-leg 18.0% · fair +455 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Dalton Schultz 20+ rec yds | 78% | -358 | ✓ 30 | `4-leg core`
| 2 | Nico Collins 5+ receptions | 78% | -361 | ✓ 5 | `4-leg core`
| 3 | Wan'Dale Robinson 3+ receptions | 79% | -374 | ✓ 6 | `4-leg core`
| 4 | Cam Ward 25+ pass att | 76% | -318 | ✓ 36 | `4-leg core`
| 5 | Tony Pollard 30+ rush yds | 75% | -294 | ✓ 52 | `+6`
| 6 | C.J. Stroud 150+ pass yds | 74% | -287 | ✓ 261 | `+6`
| 7 | David Montgomery 40+ rush yds | 72% | -256 | ✗ 11 | `+8`
| 8 | Cam Ward 150+ pass yds | 76% | -313 | ✓ 170 | `+8`

Legs 7/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| David Montgomery (HOU RB) | 42% | +138 | ✗ no TD | share 19% · team 2.46 TD · RZ-D 1.14 · pos-D 1.1 |
| Nico Collins (HOU WR) | 40% | +150 | ✗ no TD | share 18% · team 2.46 TD · RZ-D 1.14 · pos-D 1.08 |
| Woody Marks (HOU RB) | 37% | +168 | ✗ no TD | share 16% · team 2.46 TD · RZ-D 1.14 · pos-D 1.1 |

TD double (David Montgomery + Nico Collins): 21.3% · fair +369 ✗


### IND@PIT — final 22-34
*O/U 41.5 · spread +3.0 · outdoor · grass · 13:00 ET*

**Injury report (as built):** IND DEF · Arden Key (DE) — Out · Hamstring · DNP; IND OFF · Ashton Dulin (WR) — Out · Hamstring · DNP; IND OFF · Will Mallory (TE) — Out · Thumb; IND DEF · Jaylon Carlies (LB) — Out · Ribs · DNP; IND OFF · Keenan Allen (WR) — Questionable · Not injury related - resting player; IND DEF · Charvarius Ward (CB) — Questionable · Not injury related - resting player; IND OFF · Darius Slayton (WR) — Questionable · Knee; IND DEF · DeForest Buckner (DT) — nan · DNP

**Defensive leaks:** PIT D leaks passing interceptions to QBs: x1.35; PIT D leaks receptions to TEs: x1.14; PIT D leaks receiving yards to TEs: x1.12; IND D leaks receiving yards to TEs: x1.20

**Coordinators:** IND OC Jim Bob Cooter — continuity · measured pass 54% | DC Lou Anarumo (disguise_zone) · PIT OC Brian Angelichio — NEW (pass_te) · measured pass 64% | DC Patrick Graham (multiple)

**Props SGP** — 4-leg 38.4% · fair +160 ✗ · 6-leg 27.8% · fair +260 ✗ · 8-leg 19.1% · fair +424 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | DK Metcalf 20+ rec yds | 77% | -327 | ✗ 12 | `4-leg core`
| 2 | Daniel Jones 20+ pass att | 80% | -407 | ✓ 44 | `4-leg core`
| 3 | Jaylen Warren 30+ rush yds | 75% | -297 | ✓ 101 | `4-leg core`
| 4 | Josh Downs 20+ rec yds | 74% | -287 | ✓ 47 | `4-leg core`
| 5 | Aaron Rodgers 35+ pass att | 74% | -286 | ✗ 31 | `+6`
| 6 | Pat Freiermuth 2+ receptions | 82% | -462 | ✓ 5 | `+6`
| 7 | Tyler Warren 3+ receptions | 84% | -523 | ✓ 7 | `+8`
| 8 | Jonathan Taylor 40+ rush yds | 71% | -244 | ✓ 45 | `+8`

Legs 6/8 (expected 6.2)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Jonathan Taylor (IND RB) | 38% | +163 | ✗ no TD | share 29% · team 2.16 TD · RZ-D 0.92 · pos-D 0.8 |
| Jaylen Warren (PIT RB) | 30% | +234 | ✓ TD | share 14% · team 2.49 TD · RZ-D 0.96 · pos-D 1.01 |
| Tyler Warren (IND TE) | 27% | +270 | ✓ TD | share 13% · team 2.16 TD · RZ-D 0.92 · pos-D 1.19 |

TD double (Jonathan Taylor + Jaylen Warren): 13.2% · fair +657 ✗


### LV@NE — final 17-45
*O/U 45.5 · spread +3.5 · outdoor · turf · 13:00 ET*

**Injury report (as built):** LV OFF · Jalen Nailor (WR) — Out · Concussion · DNP; LV OFF · Dont'e Thornton Jr. (WR) — Out · Hamstring; LV OFF · Trey Zuhn III (C) — Out · Knee · DNP; LV OFF · Ashton Jeanty (RB) — Questionable · Ankle · DNP; NE OFF · Mack Hollins (WR) — Out · Calf · DNP; NE DEF · Carlton Davis III (CB) — Out · Neck · DNP; NE OFF · Reggie Gilliam (FB) — Out · Ankle · DNP; NE DEF · Christian Gonzalez (CB) — Out · Shoulder · DNP

**Coordinators:** LV OC Andrew Janocko — NEW (run_heavy) · measured pass 55% | DC Rob Leonard (four_man_rush) · NE OC Josh McDaniels — continuity · measured pass 51% | DC Zak Kuhr (multiple)

**Props SGP** — 4-leg 38.8% · fair +158 ✗ · 6-leg 26.1% · fair +283 ✗ · 8-leg 21.0% · fair +375 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Romeo Doubs 30+ rec yds | 79% | -367 | ✗ 16 | `4-leg core`
| 2 | TreVeyon Henderson 30+ rush yds | 76% | -326 | ✗ 22 | `4-leg core`
| 3 | Tre Tucker 2+ receptions | 75% | -306 | ✓ 4 | `4-leg core`
| 4 | Brock Bowers 50+ rec yds | 74% | -293 | ✓ 110 | `4-leg core`
| 5 | Drake Maye 200+ pass yds | 72% | -260 | ✓ 374 | `+6`
| 6 | Kirk Cousins 20+ pass att | 72% | -252 | ✓ 28 | `+6`
| 7 | Romeo Doubs 2+ receptions | 84% | -514 | ✗ 1 | `+8`
| 8 | Drake Maye o0.5 INT o0.5 | 71% | -244 | ✗ 0 INT | `+8`

Legs 4/8 (expected 6.0)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Brock Bowers (LV TE) | 35% | +186 | ✓ TD | share 20% · team 2.35 TD · RZ-D 1.07 · pos-D 0.89 |
| TreVeyon Henderson (NE RB) | 34% | +191 | ✗ no TD | share 14% · team 2.74 TD · RZ-D 1.05 · pos-D 1.04 |
| Romeo Doubs (NE WR) | 29% | +240 | ✗ no TD | share 13% · team 2.74 TD · RZ-D 1.05 · pos-D 0.98 |

TD double (Brock Bowers + TreVeyon Henderson): 13.9% · fair +618 ✗


### MIN@NO — final 23-13
*O/U 41.5 · spread -1.5 · indoor · turf · 13:00 ET*

**Injury report (as built):** MIN OFF · Christian Darrisaw (T) — Out · Concussion · DNP; MIN DEF · Charles Demmings (CB) — Out · Hamstring; MIN OFF · Brian O'Neill (T) — Questionable · Knee; MIN OFF · Justin Jefferson (WR) — Questionable · Ankle; MIN OFF · Jordan Addison (WR) — Questionable · Hamstring; MIN OFF · Michael Jurgens (C) — Questionable · Elbow; MIN OFF · Ben Yurosek (TE) — Questionable · Ankle; NO DEF · Kaden Elliss (LB) — Out · Calf · DNP

**Defensive leaks:** NO D leaks rushing yards to RBs: x1.16 (worsening x1.19 L4); NO D leaks carries to RBs: x1.12; MIN D leaks passing interceptions to QBs: x1.35 (worsening x1.06 L4)

**Coordinators:** MIN OC Wes Phillips — continuity · measured pass 49% | DC Brian Flores (blitz_man) · NO OC Doug Nussmeier — continuity · measured pass 65% | DC Brandon Staley (two_high_shell)

**Props SGP** — 4-leg 41.7% · fair +140 ✗ · 6-leg 33.9% · fair +195 ✗ · 8-leg 23.9% · fair +319 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Devaughn Vele 2+ receptions | 79% | -377 | ✓ 4 | `4-leg core`
| 2 | Aaron Jones 40+ rush yds | 77% | -333 | ✓ 113 | `4-leg core`
| 3 | Tyler Shough 175+ pass yds | 77% | -330 | ✗ 96 | `4-leg core`
| 4 | T.J. Hockenson 2+ receptions | 80% | -410 | ✗ 1 | `4-leg core`
| 5 | Chris Olave 70+ rec yds | 76% | -308 | ✗ 46 | `+6`
| 6 | Juwan Johnson 20+ rec yds | 81% | -433 | ✗ 16 | `+6`
| 7 | Kyler Murray 25+ pass att | 70% | -237 | ✓ 30 | `+8`
| 8 | Tyler Shough 35+ pass att | 75% | -307 | ✗ 25 | `+8`

Legs 3/8 (expected 6.2)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Aaron Jones (MIN RB) | 34% | +195 | ✓ TD | share 16% · team 2.41 TD · RZ-D 0.97 · pos-D 1.12 |

### NYG@WAS — final 27-27
*O/U 41.5 · spread +3.5 · outdoor · grass · 13:00 ET*

**Injury report (as built):** NYG DEF · Jason Pinnock (S) — Out · Concussion · DNP; NYG DEF · Chauncey Golston (DE) — Out · Neck · DNP; WAS OFF · Stefon Diggs (WR) — Out · Hamstring · DNP; WAS OFF · Marcus Mariota (QB) — Out · Knee · DNP; WAS DEF · Charles Omenihu (DE) — Out · Groin · DNP; WAS DEF · Nick Cross (S) — Out · Illness; WAS DEF · Percy Butler (S) — Out · Hamstring · DNP; WAS DEF · Tyler Owens (S) — Out · Hamstring · DNP

**Defensive leaks:** WAS D leaks rushing yards to RBs: x1.17; NYG D leaks rushing yards to RBs: x1.19

**Coordinators:** NYG OC Matt Nagy — NEW (pass_wr) · measured pass 48% | DC Dennard Wilson (pressure) · WAS OC David Blough — NEW (balanced) · measured pass 54% | DC Daronte Jones (zone_cover3)

**Props SGP** — 4-leg 41.0% · fair +144 **CASHED** · 6-leg 24.2% · fair +314 **CASHED** · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Cam Skattebo 30+ rush yds | 78% | -361 | ✓ 59 | `4-leg core`
| 2 | Jacory Croskey-Merritt 20+ rush yds | 77% | -340 | ✓ 82 | `4-leg core`
| 3 | Malik Nabers 5+ receptions | 79% | -371 | ✓ 11 | `4-leg core`
| 4 | Isaiah Likely 2+ receptions | 81% | -418 | ✓ 11 | `4-leg core`
| 5 | Jayden Daniels 20+ pass att | 71% | -250 | ✓ 25 | `+6`
| 6 | Antonio Williams 20+ rec yds | 70% | -236 | ✓ 31 | `+6`
| 7 | Isaiah Likely 20+ rec yds | 74% | -289 | ✓ 94 | `+8`

Legs 7/7 (expected 5.3)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Cam Skattebo (NYG RB) | 38% | +160 | ✗ no TD | share 19% · team 2.13 TD · RZ-D 1.18 · pos-D 1.1 |
| Jacory Croskey-Merritt (WAS RB) | 34% | +190 | ✓ TD | share 14% · team 2.52 TD · RZ-D 1.11 · pos-D 1.12 |
| Rachaad White (WAS RB) | 33% | +206 | ✗ no TD | share 13% · team 2.52 TD · RZ-D 1.11 · pos-D 1.12 |

TD double (Cam Skattebo + Jacory Croskey-Merritt): 15.2% · fair +558 ✗


### DEN@LAC — final 23-17
*O/U 41.5 · spread -3.5 · indoor · turf · 16:05 ET*

**Injury report (as built):** DEN DEF · Pat Surtain II (CB) — Out · Ankle · DNP; DEN DEF · Riley Moss (CB) — Out · Ribs · DNP; DEN OFF · Pat Bryant (WR) — nan · DNP; LAC OFF · Trey Lance (QB) — Doubtful · Groin; LAC DEF · Donte Jackson (CB) — Out · Hamstring · DNP; LAC DEF · Derwin James (S) — Out · Hamstring · DNP; LAC OFF · Kayode Awosika (G) — Out · Fibula · DNP; LAC OFF · Trevor Penning (G) — Out · Concussion · DNP

**Defensive leaks:** LAC D leaks passing interceptions to QBs: x1.42 (worsening x1.33 L4); DEN D leaks attempts to QBs: x1.09 (worsening x1.08 L4); DEN D leaks passing interceptions to QBs: x1.09 (worsening x1.31 L4)

**Coordinators:** DEN OC Davis Webb — NEW (balanced) · measured pass 60% | DC Vance Joseph (pressure) · LAC OC Mike McDaniel — NEW (pass_rb) · measured pass 52% | DC Chris O'Leary (two_high_shell)

**Props SGP** — 4-leg 38.6% · fair +159 ✗ · 6-leg 25.7% · fair +289 ✗ · 8-leg 19.3% · fair +418 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Justin Herbert 150+ pass yds | 78% | -350 | ✗ 121 | `4-leg core`
| 2 | Courtland Sutton 2+ receptions | 77% | -337 | ✓ 2 | `4-leg core`
| 3 | RJ Harvey 3+ receptions | 79% | -379 | ✗ 0 | `4-leg core`
| 4 | Omarion Hampton 40+ rush yds | 73% | -265 | ✗ 33 | `4-leg core`
| 5 | J.K. Dobbins 10+ carries | 72% | -256 | ✓ 18 | `+6`
| 6 | Bo Nix 25+ pass att | 86% | -635 | ✓ 27 | `+6`
| 7 | Justin Herbert o0.5 INT o0.5 | 77% | -329 | ✓ 1 INT | `+8`
| 8 | Courtland Sutton 20+ rec yds | 72% | -260 | ✗ 18 | `+8`

Legs 4/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Omarion Hampton (LAC RB) | 32% | +217 | ✗ no TD | share 21% · team 2.13 TD · RZ-D 0.74 · pos-D 0.99 |
| J.K. Dobbins (DEN RB) | 28% | +257 | ✓ TD | share 15% · team 2.52 TD · RZ-D 0.85 · pos-D 0.93 |
| RJ Harvey (DEN RB) | 26% | +277 | ✗ no TD | share 14% · team 2.52 TD · RZ-D 0.85 · pos-D 0.93 |

TD double (Omarion Hampton + J.K. Dobbins): 10.6% · fair +847 ✗


### DET@ARI — final 45-21
*O/U 54.5 · spread -5.5 · indoor · grass · 16:25 ET*

**Injury report (as built):** ARI DEF · Andrew Wingard (S) — Out · Knee · DNP; ARI OFF · Isaiah Adams (G) — Out · Ankle · DNP; ARI DEF · Walter Nolen (DT) — Questionable · Calf; ARI DEF · Karson Sharar (LB) — Questionable · Hamstring; DET DEF · Rock Ya-Sin (CB) — Out · Hamstring · DNP; DET OFF · Ben Bartch (G) — Out · Foot · DNP; DET OFF · Cade Mays (C) — Out · Wrist; DET DEF · Brian Branch (S) — Out · Achilles

**Defensive leaks:** ARI D leaks rushing yards to RBs: x1.14; ARI D leaks receiving yards to TEs: x1.08; DET D leaks receiving yards to WRs: x1.20; DET D leaks passing interceptions to QBs: x1.16

**Coordinators:** DET OC Drew Petzing — NEW (pass_te) · measured pass 62% | DC Kelvin Sheppard (pressure) · ARI OC Nathaniel Hackett — NEW (run_heavy) · measured pass 59% | DC Nick Rallis (blitz_heavy)

**Props SGP** — 4-leg 45.0% · fair +122 **CASHED** · 6-leg 28.1% · fair +256 **CASHED** · 8-leg 18.5% · fair +441 **CASHED**

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Trey McBride 6+ receptions | 78% | -344 | ✓ 9 | `4-leg core`
| 2 | Sam LaPorta 4+ receptions | 78% | -345 | ✓ 5 | `4-leg core`
| 3 | Jacoby Brissett 200+ pass yds | 76% | -323 | ✓ 292 | `4-leg core`
| 4 | Michael Wilson 30+ rec yds | 76% | -318 | ✓ 30 | `4-leg core`
| 5 | Jared Goff 30+ pass att | 81% | -422 | ✓ 30 | `+6`
| 6 | Jeremiyah Love 10+ carries | 75% | -300 | ✓ 12 | `+6`
| 7 | Amon-Ra St. Brown 40+ rec yds | 74% | -290 | ✓ 69 | `+8`
| 8 | Jahmyr Gibbs 30+ rush yds | 74% | -281 | ✓ 151 | `+8`

Legs 8/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Jahmyr Gibbs (DET RB) | 61% | -158 | ✓ TD | share 24% · team 3.36 TD · RZ-D 1.13 · pos-D 1.12 |
| Amon-Ra St. Brown (DET WR) | 50% | +102 | ✗ no TD | share 18% · team 3.36 TD · RZ-D 1.13 · pos-D 1.08 |
| Trey McBride (ARI TE) | 47% | +113 | ✓ TD | share 18% · team 2.74 TD · RZ-D 1.09 · pos-D 1.24 |

TD double (Jahmyr Gibbs + Amon-Ra St. Brown): 35.0% · fair +186 ✗


### SF@SEA — final 32-29
*O/U 46.5 · spread +3.0 · outdoor · turf · 16:25 ET*

**Injury report (as built):** SEA DEF · Chazz Surratt (LB) — Out · Calf · DNP; SEA OFF · Zach Charbonnet (RB) — Out · Knee; SEA DEF · Julian Neal (CB) — Out · Hamstring · DNP; SEA OFF · Irvin Charles (WR) — Questionable · Knee; SEA OFF · George Holani (RB) — Questionable · Ribs; SF OFF · Kyle Juszczyk (FB) — Out · Knee · DNP; SF DEF · Nick Bosa (DE) — Out · Knee · DNP; SF DEF · Marques Sigle (S) — Out · Ankle · DNP

**Defensive leaks:** SEA D leaks passing interceptions to QBs: x1.39; SEA D leaks receptions to RBs: x1.15 (worsening x1.09 L4); SEA D leaks receiving yards to RBs: x1.10; SF D leaks receptions to RBs: x1.28 (worsening x1.66 L4)

**Coordinators:** SF OC Klay Kubiak — continuity · measured pass 50% | DC Raheem Morris (zone_cover3) · SEA OC Brian Fleury — NEW (run_heavy) · measured pass 51% | DC Aden Durde (four_man_rush)

**Props SGP** — 4-leg 40.4% · fair +147 ✗ · 6-leg 28.1% · fair +256 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Christian McCaffrey 10+ carries | 78% | -361 | ✓ 11 | `4-leg core`
| 2 | Deebo Samuel Sr. 3+ receptions | 78% | -365 | ✗ 2 | `4-leg core`
| 3 | Brock Purdy 175+ pass yds | 76% | -319 | ✓ 189 | `4-leg core`
| 4 | Jaxon Smith-Njigba 5+ receptions | 81% | -430 | ✓ 5 | `4-leg core`
| 5 | Mike Evans 20+ rec yds | 74% | -284 | ✓ 113 | `+6`
| 6 | George Kittle 30+ rec yds | 72% | -257 | ✗ 24 | `+6`
| 7 | Brock Purdy 25+ pass att | 74% | -287 | ✓ 29 | `+8`

Legs 5/7 (expected 5.3)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Christian McCaffrey (SF RB) | 39% | +157 | ✓ TD | share 28% · team 2.44 TD · RZ-D 0.91 · pos-D 0.77 |
| Jaxon Smith-Njigba (SEA WR) | 35% | +189 | ✓ TD | share 16% · team 2.77 TD · RZ-D 0.95 · pos-D 0.98 |
| Mike Evans (SF WR) | 25% | +307 | ✓ TD | share 14% · team 2.44 TD · RZ-D 0.91 · pos-D 0.9 |

TD double (Christian McCaffrey + Jaxon Smith-Njigba): 15.5% · fair +546 **CASHED**


### BAL@ATL — final 30-23
*O/U 43.5 · spread +3.0 · indoor · turf · 20:20 ET*

**Injury report (as built):** ATL DEF · Yasir Abdullah (LB) — Out · Hamstring · DNP; ATL OFF · Jake Matthews (T) — Questionable · Groin; ATL DEF · Za'Darius Smith (DE) — Questionable · Concussion; ATL DEF · Samson Ebukam (DE) — Questionable · Hamstring; ATL DEF · Divine Deablo (LB) — Questionable · Hamstring; BAL DEF · Trey Hendrickson (LB) — Out · Finger · DNP; BAL OFF · Lamar Jackson (QB) — Out · Ankle · DNP; BAL OFF · Cam Jurgens (C) — Out · Concussion · DNP

**Defensive leaks:** ATL D leaks receptions to RBs: x1.15 (worsening x1.09 L4); ATL D leaks receptions to WRs: x1.09 (worsening x1.27 L4); ATL D leaks passing interceptions to QBs: x1.09; BAL D leaks receiving yards to RBs: x1.20

**Coordinators:** BAL OC Declan Doyle — NEW (pass_wr) · measured pass 45% | DC Anthony Weaver (pressure) · ATL OC Tommy Rees — NEW (run_heavy) · measured pass 42% | DC Jeff Ulbrich (blitz_heavy)

**Props SGP** — 4-leg 36.2% · fair +176 ✗ · 6-leg 24.8% · fair +303 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Brian Robinson 20+ rush yds | 78% | -349 | ✗ 16 | `4-leg core`
| 2 | Bijan Robinson 2+ receptions | 79% | -372 | ✓ 4 | `4-leg core`
| 3 | Derrick Henry 90+ rush yds | 76% | -308 | ✓ 102 | `4-leg core`
| 4 | Michael Penix Jr. 150+ pass yds | 72% | -260 | ✓ 240 | `4-leg core`
| 5 | Drake London 60+ rec yds | 71% | -247 | ✓ 118 | `+6`
| 6 | Drake London 5+ receptions | 71% | -242 | ✓ 7 | `+6`

Legs 5/6 (expected 4.5)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Derrick Henry (BAL RB) | 46% | +120 | ✓ TD | share 30% · team 2.27 TD · RZ-D 0.91 · pos-D 0.93 |
| Bijan Robinson (ATL RB) | 39% | +156 | ✗ no TD | share 20% · team 2.6 TD · RZ-D 0.9 · pos-D 1.01 |
| Drake London (ATL WR) | 30% | +238 | ✗ no TD | share 14% · team 2.6 TD · RZ-D 0.9 · pos-D 1.0 |

TD double (Derrick Henry + Bijan Robinson): 20.0% · fair +401 ✗


### Cross-game combos — Week 5 — Sunday Oct 11 2026 (floor, v1.9b)

**4-leg** — 37.1% · fair +169 — 3/4 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | CLE@NYJ | Denzel Boston 2+ receptions | 78% | ✓ 3 |
| 2 | HOU@TEN | Dalton Schultz 20+ rec yds | 78% | ✓ 30 |
| 3 | CHI@GB | Rome Odunze 2+ receptions | 78% | ✓ 3 |
| 4 | DEN@LAC | Justin Herbert 150+ pass yds | 78% | ✗ 121 |

**6-leg** — 22.9% · fair +336 — 5/6 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | CLE@NYJ | Denzel Boston 2+ receptions | 78% | ✓ 3 |
| 2 | HOU@TEN | Dalton Schultz 20+ rec yds | 78% | ✓ 30 |
| 3 | CHI@GB | Rome Odunze 2+ receptions | 78% | ✓ 3 |
| 4 | DEN@LAC | Justin Herbert 150+ pass yds | 78% | ✗ 121 |
| 5 | NYG@WAS | Cam Skattebo 30+ rush yds | 78% | ✓ 59 |
| 6 | SF@SEA | Christian McCaffrey 10+ carries | 78% | ✓ 11 |

**8-leg** — 13.9% · fair +618 — 5/8 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | CLE@NYJ | Denzel Boston 2+ receptions | 78% | ✓ 3 |
| 2 | HOU@TEN | Dalton Schultz 20+ rec yds | 78% | ✓ 30 |
| 3 | CHI@GB | Rome Odunze 2+ receptions | 78% | ✓ 3 |
| 4 | DEN@LAC | Justin Herbert 150+ pass yds | 78% | ✗ 121 |
| 5 | NYG@WAS | Cam Skattebo 30+ rush yds | 78% | ✓ 59 |
| 6 | SF@SEA | Christian McCaffrey 10+ carries | 78% | ✓ 11 |
| 7 | BAL@ATL | Brian Robinson 20+ rush yds | 78% | ✗ 16 |
| 8 | LV@NE | Romeo Doubs 30+ rec yds | 79% | ✗ 16 |

**10-leg** — 8.6% · fair +1064 — 6/10 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | CLE@NYJ | Denzel Boston 2+ receptions | 78% | ✓ 3 |
| 2 | HOU@TEN | Dalton Schultz 20+ rec yds | 78% | ✓ 30 |
| 3 | CHI@GB | Rome Odunze 2+ receptions | 78% | ✓ 3 |
| 4 | CIN@MIA | Mike Gesicki 2+ receptions | 78% | ✗ 1 |
| 5 | DEN@LAC | Justin Herbert 150+ pass yds | 78% | ✗ 121 |
| 6 | NYG@WAS | Cam Skattebo 30+ rush yds | 78% | ✓ 59 |
| 7 | SF@SEA | Christian McCaffrey 10+ carries | 78% | ✓ 11 |
| 8 | BAL@ATL | Brian Robinson 20+ rush yds | 78% | ✗ 16 |
| 9 | LV@NE | Romeo Doubs 30+ rec yds | 79% | ✗ 16 |
| 10 | CHI@GB | Jordan Love 175+ pass yds | 77% | ✓ 367 |

**12-leg** — 5.7% · fair +1656 — 8/12 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | CLE@NYJ | Denzel Boston 2+ receptions | 78% | ✓ 3 |
| 2 | HOU@TEN | Dalton Schultz 20+ rec yds | 78% | ✓ 30 |
| 3 | CHI@GB | Rome Odunze 2+ receptions | 78% | ✓ 3 |
| 4 | CIN@MIA | Mike Gesicki 2+ receptions | 78% | ✗ 1 |
| 5 | DEN@LAC | Justin Herbert 150+ pass yds | 78% | ✗ 121 |
| 6 | HOU@TEN | Nico Collins 5+ receptions | 78% | ✓ 5 |
| 7 | NYG@WAS | Cam Skattebo 30+ rush yds | 78% | ✓ 59 |
| 8 | SF@SEA | Christian McCaffrey 10+ carries | 78% | ✓ 11 |
| 9 | BAL@ATL | Brian Robinson 20+ rush yds | 78% | ✗ 16 |
| 10 | LV@NE | Romeo Doubs 30+ rec yds | 79% | ✗ 16 |
| 11 | CHI@GB | Jordan Love 175+ pass yds | 77% | ✓ 367 |
| 12 | NYG@WAS | Jacory Croskey-Merritt 20+ rush yds | 77% | ✓ 82 |


### ATD board (top 16) — Week 5 — Sunday Oct 11 2026 (floor, v1.9b)

| # | Game | Player | Model | Fair | Result |
|---|---|---|---|---|---|
| 1 | DET@ARI | Jahmyr Gibbs (RB) | 61% | -158 | ✓ TD |
| 2 | DET@ARI | Amon-Ra St. Brown (WR) | 50% | +102 | ✗ no TD |
| 3 | CLE@NYJ | Quinshon Judkins (RB) | 49% | +102 | ✗ no TD |
| 4 | CIN@MIA | Chase Brown (RB) | 48% | +109 | ✗ no TD |
| 5 | DET@ARI | Trey McBride (TE) | 47% | +113 | ✓ TD |
| 6 | BAL@ATL | Derrick Henry (RB) | 46% | +120 | ✓ TD |
| 7 | CHI@GB | D'Andre Swift (RB) | 43% | +133 | ✓ TD |
| 8 | HOU@TEN | David Montgomery (RB) | 42% | +138 | ✗ no TD |
| 9 | DET@ARI | Sam LaPorta (TE) | 40% | +149 | ✓ TD |
| 10 | HOU@TEN | Nico Collins (WR) | 40% | +150 | ✗ no TD |
| 11 | BAL@ATL | Bijan Robinson (RB) | 39% | +156 | ✗ no TD |
| 12 | SF@SEA | Christian McCaffrey (RB) | 39% | +157 | ✓ TD |
| 13 | NYG@WAS | Cam Skattebo (RB) | 38% | +160 | ✗ no TD |
| 14 | IND@PIT | Jonathan Taylor (RB) | 38% | +163 | ✗ no TD |
| 15 | HOU@TEN | Woody Marks (RB) | 37% | +168 | ✗ no TD |
| 16 | LV@NE | Brock Bowers (TE) | 35% | +186 | ✓ TD |

Board: top-16 7/16 · top-8 4/8 · chalk triple 1/3

**2+ TD board (singles only):** Jahmyr Gibbs 24% (+307) · Amon-Ra St. Brown 15% (+566) · Quinshon Judkins 15% (+570) · Chase Brown 14% (+623) · Trey McBride 13% (+651) · Derrick Henry 12% (+705)


### Scorecard — Week 5 — Sunday Oct 11 2026 (floor, v1.9b)

**Legs 71/98 = 72% actual vs 76% expected · SGP4 4/13 · SGP6 4/13 · SGP8 1/13**

| Game | Final | Legs | SGP4 | SGP6 | SGP8 |
|---|---|---|---|---|---|
| DET@ARI | 45-21 | 8/8 | ✓ | ✓ | ✓ |
| CHI@GB | 7-31 | 7/8 | ✓ | ✓ | ✗ |
| HOU@TEN | 26-3 | 7/8 | ✓ | ✓ | ✗ |
| NYG@WAS | 27-27 | 7/7 | ✓ | ✓ | ✗ |
| PHI@JAX | 17-19 | 6/7 | ✗ | ✗ | ✗ |
| CLE@NYJ | 12-17 | 6/8 | ✗ | ✗ | ✗ |
| IND@PIT | 22-34 | 6/8 | ✗ | ✗ | ✗ |
| SF@SEA | 32-29 | 5/7 | ✗ | ✗ | ✗ |
| BAL@ATL | 30-23 | 5/6 | ✗ | ✗ | ✗ |
| LV@NE | 17-45 | 4/8 | ✗ | ✗ | ✗ |
| DEN@LAC | 23-17 | 4/8 | ✗ | ✗ | ✗ |
| CIN@MIA | 31-24 | 3/7 | ✗ | ✗ | ✗ |
| MIN@NO | 23-13 | 3/8 | ✗ | ✗ | ✗ |


## Week 5 — aggressive band

*Engine v1.9b.* 54% vs 61% expected; reception rungs one step up were the weak point (41% vs 61%).


### PHI@JAX — final 17-19
*O/U 41.5 · spread +7.5 · outdoor · grass · 09:30 ET*

**Injury report (as built):** JAX DEF · Eric Murray (S) — Doubtful · Concussion; JAX DEF · Jaylon Jones (CB) — Out · Hamstring; PHI OFF · Saquon Barkley (RB) — Out · Hamstring · DNP; PHI DEF · Marcus Epps (S) — Out · Groin · DNP; PHI OFF · Marquise Brown (WR) — Out · Ankle · DNP; PHI OFF · DeVonta Smith (WR) — Out · Hamstring · DNP; PHI OFF · Drew Kendall (C) — Out · Knee · DNP; PHI DEF · Jonathan Greenard (LB) — Questionable · Ankle · DNP

**Defensive leaks:** JAX D leaks passing interceptions to QBs: x1.27 (worsening x1.86 L4); JAX D leaks receiving yards to RBs: x1.21 (worsening x1.31 L4); JAX D leaks receptions to RBs: x1.21 (worsening x1.37 L4)

**Coordinators:** PHI OC Sean Mannion — NEW (run_heavy) · measured pass 53% | DC Vic Fangio (two_high_shell) · JAX OC Grant Udinski — continuity · measured pass 48% | DC Anthony Campanile (pressure)

**Props SGP** — 4-leg 20.6% · fair +386 **CASHED** · 6-leg 11.3% · fair +787 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Makai Lemon 20+ rec yds | 63% | -168 | ✓ 43 | `4-leg core`
| 2 | Jalen Hurts 20+ pass att | 61% | -157 | ✓ 40 | `4-leg core`
| 3 | Bhayshul Tuten 30+ rush yds | 64% | -180 | ✓ 72 | `4-leg core`
| 4 | Parker Washington 30+ rec yds | 65% | -183 | ✓ 124 | `4-leg core`
| 5 | Brenton Strange 3+ receptions | 65% | -184 | ✓ 7 | `+6`
| 6 | Jakobi Meyers 4+ receptions | 59% | -145 | ✗ 2 | `+6`
| 7 | Trevor Lawrence 25+ pass att | 59% | -143 | ✓ 39 | `+8`

Legs 6/7 (expected 4.4)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Trevor Lawrence (JAX QB) | 33% | +203 | ✗ no TD | share 9% · team 2.74 TD · RZ-D 0.97 · pos-D 1.71 |
| Jalen Hurts (PHI QB) | 32% | +211 | ✗ no TD | share 18% · team 1.9 TD · RZ-D 0.89 · pos-D 1.22 |
| Bhayshul Tuten (JAX RB) | 26% | +277 | ✗ no TD | share 11% · team 2.74 TD · RZ-D 0.97 · pos-D 1.04 |

TD double (Trevor Lawrence + Jalen Hurts): 12.5% · fair +702 ✗


### CHI@GB — final 7-31
*O/U 47.5 · spread -1.5 · outdoor · grass · 13:00 ET*

**Injury report (as built):** CHI OFF · Kyle Monangai (RB) — Out · Thumb · DNP; CHI DEF · Keyshaun Elliott (LB) — Out · Quadricep · DNP; CHI DEF · Kyler Gordon (CB) — Questionable · Calf; CHI DEF · Noah Sewell (LB) — Questionable · Achilles; CHI OFF · Caleb Williams (QB) — Questionable · Hamstring; CHI DEF · Shemar Turner (DE) — Questionable · Knee; GB OFF · Aaron Banks (G) — Doubtful · Knee; GB OFF · Jacob Monk (C) — Doubtful · Quadricep

**Defensive leaks:** GB D leaks receptions to RBs: x1.08; CHI D leaks passing interceptions to QBs: x1.39; CHI D leaks rushing yards to RBs: x1.16

**Coordinators:** CHI OC Press Taylor — NEW (pass_wr) · measured pass 45% | DC Dennis Allen (blitz_man) · GB OC Adam Stenavich — continuity · measured pass 68% | DC Jonathan Gannon (two_high_shell)

**Props SGP** — 4-leg 16.6% · fair +502 ✗ · 6-leg 9.9% · fair +908 ✗ · 8-leg 5.5% · fair +1722 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | D'Andre Swift 70+ rush yds | 61% | -158 | ✗ 43 | `4-leg core`
| 2 | Rome Odunze 40+ rec yds | 61% | -155 | ✓ 40 | `4-leg core`
| 3 | Luther Burden III 4+ receptions | 63% | -173 | ✓ 4 | `4-leg core`
| 4 | Colston Loveland 3+ receptions | 61% | -154 | ✗ 2 | `4-leg core`
| 5 | Kalif Raymond 30+ rec yds | 64% | -176 | ✗ 6 | `+6`
| 6 | MarShawn Lloyd 30+ rush yds | 60% | -150 | ✓ 31 | `+6`
| 7 | Jordan Love 30+ pass att | 66% | -198 | ✓ 31 | `+8`
| 8 | Jordan Love 225+ pass yds | 57% | -132 | ✓ 367 | `+8`

Legs 5/8 (expected 4.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| D'Andre Swift (CHI RB) | 43% | +133 | ✓ TD | share 19% · team 2.74 TD · RZ-D 1.1 · pos-D 1.04 |
| Christian Watson (GB WR) | 31% | +219 | ✓ TD | share 13% · team 2.58 TD · RZ-D 0.97 · pos-D 1.16 |
| Rome Odunze (CHI WR) | 26% | +291 | ✗ no TD | share 10% · team 2.74 TD · RZ-D 1.1 · pos-D 1.06 |

TD double (D'Andre Swift + Christian Watson): 15.5% · fair +546 **CASHED**


### CIN@MIA — final 31-24
*O/U 44.5 · spread -7.0 · outdoor · grass · 13:00 ET*

**Injury report (as built):** CIN DEF · Kyle Dugger (S) — Out · Quadricep · DNP; CIN OFF · Tee Higgins (WR) — Questionable · Groin; CIN OFF · Ja'Marr Chase (WR) — Questionable · Concussion; CIN DEF · Bryan Cook (S) — Questionable · Ankle; CIN DEF · Swayze Bozeman (LB) — Questionable · Groin; CIN OFF · Colbie Young (WR) — Questionable · Knee; CIN DEF · B.J. Hill (DT) — nan · DNP; CIN DEF · Dexter Lawrence (DT) — nan · DNP

**Defensive leaks:** MIA D leaks receiving yards to TEs: x1.22 (worsening x1.58 L4); MIA D leaks receptions to TEs: x1.20 (worsening x1.23 L4); MIA D leaks receiving yards to RBs: x1.08; CIN D leaks receiving yards to TEs: x1.49 (worsening x1.64 L4)

**Coordinators:** CIN OC Dan Pitcher — continuity · measured pass 65% | DC Al Golden (disguise_zone) · MIA OC Bobby Slowik — NEW (pass_wr) · measured pass 52% | DC Sean Duggan (multiple)

**Props SGP** — 4-leg 24.8% · fair +303 ✗ · 6-leg 18.4% · fair +443 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Joe Burrow 250+ pass yds | 62% | -161 | ✗ 190 | `4-leg core`
| 2 | Dohnte Meyers 30+ rec yds | 62% | -161 | ✗ 12 | `4-leg core`
| 3 | Mike Gesicki 3+ receptions | 62% | -166 | ✗ 1 | `4-leg core`
| 4 | Greg Dulcich 40+ rec yds | 62% | -160 | ✗ 37 | `4-leg core`
| 5 | Chase Brown 4+ receptions | 63% | -169 | ✗ 3 | `+6`
| 6 | Joe Burrow 35+ pass att | 66% | -190 | ✗ 32 | `+6`
| 7 | Chase Brown 15+ carries | 66% | -191 | ✗ 13 | `+8`

Legs 0/7 (expected 4.4)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Chase Brown (CIN RB) | 48% | +109 | ✗ no TD | share 20% · team 2.88 TD · RZ-D 1.1 · pos-D 1.1 |
| Ollie Gordon II (MIA RB) | 26% | +280 | ✓ TD | share 13% · team 2.1 TD · RZ-D 1.0 · pos-D 1.1 |
| Mike Gesicki (CIN TE) | 26% | +291 | ✓ TD | share 9% · team 2.88 TD · RZ-D 1.1 · pos-D 1.08 |

TD double (Chase Brown + Ollie Gordon II): 14.5% · fair +591 ✗


### CLE@NYJ — final 12-17
*O/U 38.5 · spread +2.5 · outdoor · turf · 13:00 ET*

**Injury report (as built):** CLE OFF · Tylan Wallace (WR) — Out · Knee · DNP; CLE OFF · Teven Jenkins (G) — Out · Back · DNP; CLE DEF · Kalia Davis (DT) — Out · Quadricep · DNP; CLE DEF · Mike Hall Jr. (DT) — Out · Ankle · DNP; CLE DEF · Mason Graham (DT) — Out · Knee · DNP; CLE OFF · Dillon Gabriel (QB) — Out · Back; CLE OFF · Carsen Ryan (TE) — Out · Calf · DNP; NYJ OFF · Dylan Parham (G) — Out · Knee · DNP

**Defensive leaks:** NYJ D leaks carries to RBs: x1.14 (worsening x1.25 L4); NYJ D leaks rushing yards to RBs: x1.11 (worsening x1.30 L4)

**Coordinators:** CLE OC Travis Switzer — NEW (run_heavy) · measured pass 53% | DC Mike Rutenberg (multiple) · NYJ OC Frank Reich — NEW (balanced) · measured pass 54% | DC Brian Duker (multiple)

**Props SGP** — 4-leg 23.4% · fair +327 ✗ · 6-leg 11.8% · fair +749 ✗ · 8-leg 7.2% · fair +1286 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Geno Smith 200+ pass yds | 62% | -162 | ✗ 182 | `4-leg core`
| 2 | Denzel Boston 50+ rec yds | 62% | -165 | ✗ 46 | `4-leg core`
| 3 | Garrett Wilson 40+ rec yds | 64% | -177 | ✓ 104 | `4-leg core`
| 4 | KC Concepcion 4+ receptions | 60% | -148 | ✗ 1 | `4-leg core`
| 5 | Deshaun Watson 150+ pass yds | 65% | -184 | ✓ 155 | `+6`
| 6 | Quinshon Judkins 15+ carries | 67% | -201 | ✗ 14 | `+6`
| 7 | Kenyon Sadiq 3+ receptions | 55% | -123 | ✗ 2 | `+8`
| 8 | Deshaun Watson 25+ pass att | 56% | -125 | ✓ 33 | `+8`

Legs 3/8 (expected 4.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Quinshon Judkins (CLE RB) | 49% | +102 | ✗ no TD | share 22% · team 2.02 TD · RZ-D 1.11 · pos-D 1.42 |
| Garrett Wilson (NYJ WR) | 27% | +276 | ✓ TD | share 12% · team 2.3 TD · RZ-D 1.01 · pos-D 1.11 |
| Harold Fannin Jr. (CLE TE) | 26% | +288 | ✗ no TD | share 14% · team 2.02 TD · RZ-D 1.11 · pos-D 1.03 |

TD double (Quinshon Judkins + Garrett Wilson): 15.1% · fair +564 ✗


### HOU@TEN — final 26-3
*O/U 37.5 · spread -6.5 · outdoor · grass · 13:00 ET*

**Injury report (as built):** HOU OFF · Tank Dell (WR) — Out · Knee · DNP; HOU DEF · M.J. Stewart (S) — Questionable · Knee; HOU OFF · Braden Smith (T) — Questionable · Foot; HOU OFF · Ed Ingram (G) — Questionable · Illness; HOU OFF · Blake Fisher (T) — Questionable · Illness; HOU OFF · Aireontae Ersery (T) — Questionable · Illness · DNP; HOU DEF · Kayden McDonald (DT) — Questionable · Ankle; HOU DEF · Jadeveon Clowney (DE) — nan · DNP

**Defensive leaks:** HOU D leaks passing interceptions to QBs: x1.42

**Coordinators:** HOU OC Nick Caley — continuity · measured pass 63% | DC Matt Burke (four_man_rush) · TEN OC Brian Daboll — NEW (pass_wr) · measured pass 57% | DC Gus Bradley (zone_cover3)

**Props SGP** — 4-leg 23.9% · fair +319 ✗ · 6-leg 11.1% · fair +803 ✗ · 8-leg 5.1% · fair +1863 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | C.J. Stroud 175+ pass yds | 62% | -160 | ✓ 261 | `4-leg core`
| 2 | Cam Ward 175+ pass yds | 63% | -170 | ✗ 170 | `4-leg core`
| 3 | Wan'Dale Robinson 30+ rec yds | 61% | -155 | ✓ 53 | `4-leg core`
| 4 | Nico Collins 70+ rec yds | 64% | -175 | ✗ 56 | `4-leg core`
| 5 | Tony Pollard 50+ rush yds | 58% | -138 | ✓ 52 | `+6`
| 6 | Dalton Schultz 4+ receptions | 67% | -205 | ✗ 3 | `+6`
| 7 | David Montgomery 50+ rush yds | 56% | -130 | ✗ 11 | `+8`
| 8 | Cam Ward 30+ pass att | 60% | -153 | ✓ 36 | `+8`

Legs 4/8 (expected 4.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| David Montgomery (HOU RB) | 42% | +138 | ✗ no TD | share 19% · team 2.46 TD · RZ-D 1.14 · pos-D 1.1 |
| Nico Collins (HOU WR) | 40% | +150 | ✗ no TD | share 18% · team 2.46 TD · RZ-D 1.14 · pos-D 1.08 |
| Woody Marks (HOU RB) | 37% | +168 | ✗ no TD | share 16% · team 2.46 TD · RZ-D 1.14 · pos-D 1.1 |

TD double (David Montgomery + Nico Collins): 21.3% · fair +369 ✗


### IND@PIT — final 22-34
*O/U 41.5 · spread +3.0 · outdoor · grass · 13:00 ET*

**Injury report (as built):** IND DEF · Arden Key (DE) — Out · Hamstring · DNP; IND OFF · Ashton Dulin (WR) — Out · Hamstring · DNP; IND OFF · Will Mallory (TE) — Out · Thumb; IND DEF · Jaylon Carlies (LB) — Out · Ribs · DNP; IND OFF · Keenan Allen (WR) — Questionable · Not injury related - resting player; IND DEF · Charvarius Ward (CB) — Questionable · Not injury related - resting player; IND OFF · Darius Slayton (WR) — Questionable · Knee; IND DEF · DeForest Buckner (DT) — nan · DNP

**Defensive leaks:** PIT D leaks passing interceptions to QBs: x1.35; PIT D leaks receptions to TEs: x1.14; PIT D leaks receiving yards to TEs: x1.12; IND D leaks receiving yards to TEs: x1.20

**Coordinators:** IND OC Jim Bob Cooter — continuity · measured pass 54% | DC Lou Anarumo (disguise_zone) · PIT OC Brian Angelichio — NEW (pass_te) · measured pass 64% | DC Patrick Graham (multiple)

**Props SGP** — 4-leg 24.0% · fair +317 ✗ · 6-leg 7.5% · fair +1237 ✗ · 8-leg 4.8% · fair +1993 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Pat Freiermuth 30+ rec yds | 62% | -164 | ✓ 44 | `4-leg core`
| 2 | DK Metcalf 40+ rec yds | 62% | -161 | ✗ 12 | `4-leg core`
| 3 | Aaron Rodgers 250+ pass yds | 60% | -152 | ✗ 235 | `4-leg core`
| 4 | Daniel Jones 25+ pass att | 60% | -152 | ✓ 44 | `4-leg core`
| 5 | Jaylen Warren 50+ rush yds | 58% | -139 | ✓ 101 | `+6`
| 6 | Jonathan Taylor 60+ rush yds | 56% | -129 | ✗ 45 | `+6`
| 7 | Tyler Warren 4+ receptions | 68% | -212 | ✓ 7 | `+8`
| 8 | Daniel Jones 150+ pass yds | 60% | -150 | ✓ 267 | `+8`

Legs 5/8 (expected 4.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Jonathan Taylor (IND RB) | 38% | +163 | ✗ no TD | share 29% · team 2.16 TD · RZ-D 0.92 · pos-D 0.8 |
| Jaylen Warren (PIT RB) | 30% | +234 | ✓ TD | share 14% · team 2.49 TD · RZ-D 0.96 · pos-D 1.01 |
| Tyler Warren (IND TE) | 27% | +270 | ✓ TD | share 13% · team 2.16 TD · RZ-D 0.92 · pos-D 1.19 |

TD double (Jonathan Taylor + Jaylen Warren): 13.2% · fair +657 ✗


### LV@NE — final 17-45
*O/U 45.5 · spread +3.5 · outdoor · turf · 13:00 ET*

**Injury report (as built):** LV OFF · Jalen Nailor (WR) — Out · Concussion · DNP; LV OFF · Dont'e Thornton Jr. (WR) — Out · Hamstring; LV OFF · Trey Zuhn III (C) — Out · Knee · DNP; LV OFF · Ashton Jeanty (RB) — Questionable · Ankle · DNP; NE OFF · Mack Hollins (WR) — Out · Calf · DNP; NE DEF · Carlton Davis III (CB) — Out · Neck · DNP; NE OFF · Reggie Gilliam (FB) — Out · Ankle · DNP; NE DEF · Christian Gonzalez (CB) — Out · Shoulder · DNP

**Coordinators:** LV OC Andrew Janocko — NEW (run_heavy) · measured pass 55% | DC Rob Leonard (four_man_rush) · NE OC Josh McDaniels — continuity · measured pass 51% | DC Zak Kuhr (multiple)

**Props SGP** — 4-leg 23.5% · fair +326 ✗ · 6-leg 10.5% · fair +851 ✗ · 8-leg 7.7% · fair +1206 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | TreVeyon Henderson 50+ rush yds | 62% | -163 | ✗ 22 | `4-leg core`
| 2 | Brock Bowers 6+ receptions | 61% | -158 | ✓ 8 | `4-leg core`
| 3 | Tre Tucker 40+ rec yds | 60% | -148 | ✓ 41 | `4-leg core`
| 4 | Kirk Cousins 175+ pass yds | 59% | -145 | ✓ 243 | `4-leg core`
| 5 | DeMario Douglas 20+ rec yds | 67% | -204 | ✓ 65 | `+6`
| 6 | Drake Maye 225+ pass yds | 55% | -124 | ✓ 374 | `+6`
| 7 | Tre Tucker 3+ receptions | 59% | -144 | ✓ 4 | `+8`
| 8 | Kirk Cousins 25+ pass att | 57% | -133 | ✓ 28 | `+8`

Legs 7/8 (expected 4.8)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Brock Bowers (LV TE) | 35% | +186 | ✓ TD | share 20% · team 2.35 TD · RZ-D 1.07 · pos-D 0.89 |
| TreVeyon Henderson (NE RB) | 34% | +191 | ✗ no TD | share 14% · team 2.74 TD · RZ-D 1.05 · pos-D 1.04 |
| Romeo Doubs (NE WR) | 29% | +240 | ✗ no TD | share 13% · team 2.74 TD · RZ-D 1.05 · pos-D 0.98 |

TD double (Brock Bowers + TreVeyon Henderson): 13.9% · fair +618 ✗


### MIN@NO — final 23-13
*O/U 41.5 · spread -1.5 · indoor · turf · 13:00 ET*

**Injury report (as built):** MIN OFF · Christian Darrisaw (T) — Out · Concussion · DNP; MIN DEF · Charles Demmings (CB) — Out · Hamstring; MIN OFF · Brian O'Neill (T) — Questionable · Knee; MIN OFF · Justin Jefferson (WR) — Questionable · Ankle; MIN OFF · Jordan Addison (WR) — Questionable · Hamstring; MIN OFF · Michael Jurgens (C) — Questionable · Elbow; MIN OFF · Ben Yurosek (TE) — Questionable · Ankle; NO DEF · Kaden Elliss (LB) — Out · Calf · DNP

**Defensive leaks:** NO D leaks rushing yards to RBs: x1.16 (worsening x1.19 L4); NO D leaks carries to RBs: x1.12; MIN D leaks passing interceptions to QBs: x1.35 (worsening x1.06 L4)

**Coordinators:** MIN OC Wes Phillips — continuity · measured pass 49% | DC Brian Flores (blitz_man) · NO OC Doug Nussmeier — continuity · measured pass 65% | DC Brandon Staley (two_high_shell)

**Props SGP** — 4-leg 23.2% · fair +332 ✗ · 6-leg 12.9% · fair +674 ✗ · 8-leg 8.7% · fair +1045 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | T.J. Hockenson 30+ rec yds | 62% | -165 | ✗ 7 | `4-leg core`
| 2 | Tyler Shough 40+ pass att | 62% | -166 | ✗ 25 | `4-leg core`
| 3 | Kyler Murray o0.5 INT o0.5 | 61% | -159 | ✗ 0 INT | `4-leg core`
| 4 | Devaughn Vele 3+ receptions | 64% | -179 | ✓ 4 | `4-leg core`
| 5 | Aaron Jones 50+ rush yds | 66% | -190 | ✓ 113 | `+6`
| 6 | Chris Olave 90+ rec yds | 57% | -132 | ✗ 46 | `+6`
| 7 | Tyler Shough o0.5 INT o0.5 | 61% | -156 | ✓ 2 INT | `+8`
| 8 | Chris Olave 8+ receptions | 57% | -130 | ✗ 4 | `+8`

Legs 3/8 (expected 4.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Aaron Jones (MIN RB) | 34% | +195 | ✓ TD | share 16% · team 2.41 TD · RZ-D 0.97 · pos-D 1.12 |

### NYG@WAS — final 27-27
*O/U 41.5 · spread +3.5 · outdoor · grass · 13:00 ET*

**Injury report (as built):** NYG DEF · Jason Pinnock (S) — Out · Concussion · DNP; NYG DEF · Chauncey Golston (DE) — Out · Neck · DNP; WAS OFF · Stefon Diggs (WR) — Out · Hamstring · DNP; WAS OFF · Marcus Mariota (QB) — Out · Knee · DNP; WAS DEF · Charles Omenihu (DE) — Out · Groin · DNP; WAS DEF · Nick Cross (S) — Out · Illness; WAS DEF · Percy Butler (S) — Out · Hamstring · DNP; WAS DEF · Tyler Owens (S) — Out · Hamstring · DNP

**Defensive leaks:** WAS D leaks rushing yards to RBs: x1.17; NYG D leaks rushing yards to RBs: x1.19

**Coordinators:** NYG OC Matt Nagy — NEW (pass_wr) · measured pass 48% | DC Dennard Wilson (pressure) · WAS OC David Blough — NEW (balanced) · measured pass 54% | DC Daronte Jones (zone_cover3)

**Props SGP** — 4-leg 18.8% · fair +432 **CASHED** · 6-leg 11.1% · fair +801 ✗ · 8-leg 6.5% · fair +1448 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Antonio Williams 3+ receptions | 62% | -162 | ✓ 3 | `4-leg core`
| 2 | Jayden Daniels 40+ rush yds | 62% | -160 | ✓ 103 | `4-leg core`
| 3 | Malik Nabers 60+ rec yds | 61% | -154 | ✓ 121 | `4-leg core`
| 4 | Isaiah Likely 30+ rec yds | 64% | -174 | ✓ 94 | `4-leg core`
| 5 | Jameis Winston o0.5 INT o0.5 | 65% | -183 | ✗ 0 INT | `+6`
| 6 | Jacory Croskey-Merritt 30+ rush yds | 66% | -195 | ✓ 82 | `+6`
| 7 | Jayden Daniels 150+ pass yds | 60% | -151 | ✓ 199 | `+8`
| 8 | Jameis Winston 20+ pass att | 59% | -145 | ✓ 54 | `+8`

Legs 7/8 (expected 5.0)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Cam Skattebo (NYG RB) | 38% | +160 | ✗ no TD | share 19% · team 2.13 TD · RZ-D 1.18 · pos-D 1.1 |
| Jacory Croskey-Merritt (WAS RB) | 34% | +190 | ✓ TD | share 14% · team 2.52 TD · RZ-D 1.11 · pos-D 1.12 |
| Rachaad White (WAS RB) | 33% | +206 | ✗ no TD | share 13% · team 2.52 TD · RZ-D 1.11 · pos-D 1.12 |

TD double (Cam Skattebo + Jacory Croskey-Merritt): 15.2% · fair +558 ✗


### DEN@LAC — final 23-17
*O/U 41.5 · spread -3.5 · indoor · turf · 16:05 ET*

**Injury report (as built):** DEN DEF · Pat Surtain II (CB) — Out · Ankle · DNP; DEN DEF · Riley Moss (CB) — Out · Ribs · DNP; DEN OFF · Pat Bryant (WR) — nan · DNP; LAC OFF · Trey Lance (QB) — Doubtful · Groin; LAC DEF · Donte Jackson (CB) — Out · Hamstring · DNP; LAC DEF · Derwin James (S) — Out · Hamstring · DNP; LAC OFF · Kayode Awosika (G) — Out · Fibula · DNP; LAC OFF · Trevor Penning (G) — Out · Concussion · DNP

**Defensive leaks:** LAC D leaks passing interceptions to QBs: x1.42 (worsening x1.33 L4); DEN D leaks attempts to QBs: x1.09 (worsening x1.08 L4); DEN D leaks passing interceptions to QBs: x1.09 (worsening x1.31 L4)

**Coordinators:** DEN OC Davis Webb — NEW (balanced) · measured pass 60% | DC Vance Joseph (pressure) · LAC OC Mike McDaniel — NEW (pass_rb) · measured pass 52% | DC Chris O'Leary (two_high_shell)

**Props SGP** — 4-leg 25.1% · fair +299 ✗ · 6-leg 15.0% · fair +568 ✗ · 8-leg 5.4% · fair +1760 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Jaylen Waddle 20+ rec yds | 62% | -164 | ✗ 19 | `4-leg core`
| 2 | Courtland Sutton 3+ receptions | 62% | -165 | ✗ 2 | `4-leg core`
| 3 | Bo Nix 150+ pass yds | 62% | -166 | ✗ 123 | `4-leg core`
| 4 | Omarion Hampton 50+ rush yds | 62% | -161 | ✗ 33 | `4-leg core`
| 5 | Justin Herbert 30+ rush yds | 60% | -152 | ✓ 54 | `+6`
| 6 | RJ Harvey 5+ receptions | 58% | -136 | ✗ 0 | `+6`
| 7 | Oronde Gadsden II 30+ rec yds | 56% | -130 | ✗ 0 | `+8`
| 8 | Justin Herbert 30+ pass att | 58% | -137 | ✗ 24 | `+8`

Legs 1/8 (expected 4.8)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Omarion Hampton (LAC RB) | 32% | +217 | ✗ no TD | share 21% · team 2.13 TD · RZ-D 0.74 · pos-D 0.99 |
| J.K. Dobbins (DEN RB) | 28% | +257 | ✓ TD | share 15% · team 2.52 TD · RZ-D 0.85 · pos-D 0.93 |
| RJ Harvey (DEN RB) | 26% | +277 | ✗ no TD | share 14% · team 2.52 TD · RZ-D 0.85 · pos-D 0.93 |

TD double (Omarion Hampton + J.K. Dobbins): 10.6% · fair +847 ✗


### DET@ARI — final 45-21
*O/U 54.5 · spread -5.5 · indoor · grass · 16:25 ET*

**Injury report (as built):** ARI DEF · Andrew Wingard (S) — Out · Knee · DNP; ARI OFF · Isaiah Adams (G) — Out · Ankle · DNP; ARI DEF · Walter Nolen (DT) — Questionable · Calf; ARI DEF · Karson Sharar (LB) — Questionable · Hamstring; DET DEF · Rock Ya-Sin (CB) — Out · Hamstring · DNP; DET OFF · Ben Bartch (G) — Out · Foot · DNP; DET OFF · Cade Mays (C) — Out · Wrist; DET DEF · Brian Branch (S) — Out · Achilles

**Defensive leaks:** ARI D leaks rushing yards to RBs: x1.14; ARI D leaks receiving yards to TEs: x1.08; DET D leaks receiving yards to WRs: x1.20; DET D leaks passing interceptions to QBs: x1.16

**Coordinators:** DET OC Drew Petzing — NEW (pass_te) · measured pass 62% | DC Kelvin Sheppard (pressure) · ARI OC Nathaniel Hackett — NEW (run_heavy) · measured pass 59% | DC Nick Rallis (blitz_heavy)

**Props SGP** — 4-leg 18.9% · fair +428 ✗ · 6-leg 11.4% · fair +778 ✗ · 8-leg 6.6% · fair +1410 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Michael Wilson 5+ receptions | 62% | -164 | ✗ 4 | `4-leg core`
| 2 | Sam LaPorta 5+ receptions | 62% | -161 | ✓ 5 | `4-leg core`
| 3 | Jeremiyah Love 50+ rush yds | 62% | -166 | ✗ 22 | `4-leg core`
| 4 | Amon-Ra St. Brown 60+ rec yds | 61% | -159 | ✓ 69 | `4-leg core`
| 5 | Jared Goff 35+ pass att | 63% | -168 | ✗ 30 | `+6`
| 6 | Kendrick Bourne 20+ rec yds | 61% | -157 | ✓ 70 | `+6`
| 7 | Jacoby Brissett o0.5 INT o0.5 | 64% | -177 | ✓ 1 INT | `+8`
| 8 | Jahmyr Gibbs 15+ carries | 66% | -195 | ✓ 25 | `+8`

Legs 5/8 (expected 5.0)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Jahmyr Gibbs (DET RB) | 61% | -158 | ✓ TD | share 24% · team 3.36 TD · RZ-D 1.13 · pos-D 1.12 |
| Amon-Ra St. Brown (DET WR) | 50% | +102 | ✗ no TD | share 18% · team 3.36 TD · RZ-D 1.13 · pos-D 1.08 |
| Trey McBride (ARI TE) | 47% | +113 | ✓ TD | share 18% · team 2.74 TD · RZ-D 1.09 · pos-D 1.24 |

TD double (Jahmyr Gibbs + Amon-Ra St. Brown): 35.0% · fair +186 ✗


### SF@SEA — final 32-29
*O/U 46.5 · spread +3.0 · outdoor · turf · 16:25 ET*

**Injury report (as built):** SEA DEF · Chazz Surratt (LB) — Out · Calf · DNP; SEA OFF · Zach Charbonnet (RB) — Out · Knee; SEA DEF · Julian Neal (CB) — Out · Hamstring · DNP; SEA OFF · Irvin Charles (WR) — Questionable · Knee; SEA OFF · George Holani (RB) — Questionable · Ribs; SF OFF · Kyle Juszczyk (FB) — Out · Knee · DNP; SF DEF · Nick Bosa (DE) — Out · Knee · DNP; SF DEF · Marques Sigle (S) — Out · Ankle · DNP

**Defensive leaks:** SEA D leaks passing interceptions to QBs: x1.39; SEA D leaks receptions to RBs: x1.15 (worsening x1.09 L4); SEA D leaks receiving yards to RBs: x1.10; SF D leaks receptions to RBs: x1.28 (worsening x1.66 L4)

**Coordinators:** SF OC Klay Kubiak — continuity · measured pass 50% | DC Raheem Morris (zone_cover3) · SEA OC Brian Fleury — NEW (run_heavy) · measured pass 51% | DC Aden Durde (four_man_rush)

**Props SGP** — 4-leg 16.6% · fair +502 ✗ · 6-leg 8.9% · fair +1022 ✗ · 8-leg 5.2% · fair +1829 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Jaxon Smith-Njigba 80+ rec yds | 62% | -166 | ✓ 102 | `4-leg core`
| 2 | Deebo Samuel Sr. 4+ receptions | 61% | -159 | ✗ 2 | `4-leg core`
| 3 | Kaelon Black 30+ rush yds | 63% | -168 | ✗ 16 | `4-leg core`
| 4 | George Kittle 40+ rec yds | 61% | -155 | ✗ 24 | `4-leg core`
| 5 | Brock Purdy 200+ pass yds | 64% | -179 | ✗ 189 | `+6`
| 6 | Emanuel Wilson 30+ rush yds | 59% | -143 | ✓ 61 | `+6`
| 7 | Christian McCaffrey 5+ receptions | 58% | -139 | ✗ 3 | `+8`
| 8 | Sam Darnold 150+ pass yds | 57% | -131 | ✓ 195 | `+8`

Legs 3/8 (expected 4.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Christian McCaffrey (SF RB) | 39% | +157 | ✓ TD | share 28% · team 2.44 TD · RZ-D 0.91 · pos-D 0.77 |
| Jaxon Smith-Njigba (SEA WR) | 35% | +189 | ✓ TD | share 16% · team 2.77 TD · RZ-D 0.95 · pos-D 0.98 |
| Mike Evans (SF WR) | 25% | +307 | ✓ TD | share 14% · team 2.44 TD · RZ-D 0.91 · pos-D 0.9 |

TD double (Christian McCaffrey + Jaxon Smith-Njigba): 15.5% · fair +546 **CASHED**


### BAL@ATL — final 30-23
*O/U 43.5 · spread +3.0 · indoor · turf · 20:20 ET*

**Injury report (as built):** ATL DEF · Yasir Abdullah (LB) — Out · Hamstring · DNP; ATL OFF · Jake Matthews (T) — Questionable · Groin; ATL DEF · Za'Darius Smith (DE) — Questionable · Concussion; ATL DEF · Samson Ebukam (DE) — Questionable · Hamstring; ATL DEF · Divine Deablo (LB) — Questionable · Hamstring; BAL DEF · Trey Hendrickson (LB) — Out · Finger · DNP; BAL OFF · Lamar Jackson (QB) — Out · Ankle · DNP; BAL OFF · Cam Jurgens (C) — Out · Concussion · DNP

**Defensive leaks:** ATL D leaks receptions to RBs: x1.15 (worsening x1.09 L4); ATL D leaks receptions to WRs: x1.09 (worsening x1.27 L4); ATL D leaks passing interceptions to QBs: x1.09; BAL D leaks receiving yards to RBs: x1.20

**Coordinators:** BAL OC Declan Doyle — NEW (pass_wr) · measured pass 45% | DC Anthony Weaver (pressure) · ATL OC Tommy Rees — NEW (run_heavy) · measured pass 42% | DC Jeff Ulbrich (blitz_heavy)

**Props SGP** — 4-leg 16.4% · fair +511 ✗ · 6-leg 9.5% · fair +954 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Michael Penix Jr. 20+ pass att | 61% | -159 | ✓ 32 | `4-leg core`
| 2 | Bijan Robinson 100+ rush yds | 61% | -159 | ✗ 86 | `4-leg core`
| 3 | Derrick Henry 20+ carries | 64% | -181 | ✓ 24 | `4-leg core`
| 4 | Drake London 6+ receptions | 59% | -144 | ✓ 7 | `4-leg core`
| 5 | Bijan Robinson 30+ rec yds | 59% | -143 | ✓ 32 | `+6`
| 6 | Drake London 80+ rec yds | 59% | -142 | ✓ 118 | `+6`
| 7 | Michael Penix Jr. 200+ pass yds | 58% | -136 | ✓ 240 | `+8`

Legs 6/7 (expected 4.2)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Derrick Henry (BAL RB) | 46% | +120 | ✓ TD | share 30% · team 2.27 TD · RZ-D 0.91 · pos-D 0.93 |
| Bijan Robinson (ATL RB) | 39% | +156 | ✗ no TD | share 20% · team 2.6 TD · RZ-D 0.9 · pos-D 1.01 |
| Drake London (ATL WR) | 30% | +238 | ✗ no TD | share 14% · team 2.6 TD · RZ-D 0.9 · pos-D 1.0 |

TD double (Derrick Henry + Bijan Robinson): 20.0% · fair +401 ✗


### Cross-game combos — Week 5 — aggressive band

**4-leg** — 15.0% · fair +568 — 1/4 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | IND@PIT | Pat Freiermuth 30+ rec yds | 62% | ✓ 44 |
| 2 | DEN@LAC | Jaylen Waddle 20+ rec yds | 62% | ✗ 19 |
| 3 | DET@ARI | Michael Wilson 5+ receptions | 62% | ✗ 4 |
| 4 | LV@NE | TreVeyon Henderson 50+ rush yds | 62% | ✗ 22 |

**6-leg** — 5.8% · fair +1636 — 2/6 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | IND@PIT | Pat Freiermuth 30+ rec yds | 62% | ✓ 44 |
| 2 | DEN@LAC | Jaylen Waddle 20+ rec yds | 62% | ✗ 19 |
| 3 | DET@ARI | Michael Wilson 5+ receptions | 62% | ✗ 4 |
| 4 | LV@NE | TreVeyon Henderson 50+ rush yds | 62% | ✗ 22 |
| 5 | CLE@NYJ | Geno Smith 200+ pass yds | 62% | ✗ 182 |
| 6 | NYG@WAS | Antonio Williams 3+ receptions | 62% | ✓ 3 |

**8-leg** — 2.2% · fair +4431 — 2/8 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | IND@PIT | Pat Freiermuth 30+ rec yds | 62% | ✓ 44 |
| 2 | DEN@LAC | Jaylen Waddle 20+ rec yds | 62% | ✗ 19 |
| 3 | DET@ARI | Michael Wilson 5+ receptions | 62% | ✗ 4 |
| 4 | LV@NE | TreVeyon Henderson 50+ rush yds | 62% | ✗ 22 |
| 5 | CLE@NYJ | Geno Smith 200+ pass yds | 62% | ✗ 182 |
| 6 | NYG@WAS | Antonio Williams 3+ receptions | 62% | ✓ 3 |
| 7 | MIN@NO | Tyler Shough 40+ pass att | 62% | ✗ 25 |
| 8 | CIN@MIA | Joe Burrow 250+ pass yds | 62% | ✗ 190 |

**10-leg** — 1.0% · fair +9506 — 2/10 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | IND@PIT | Pat Freiermuth 30+ rec yds | 62% | ✓ 44 |
| 2 | DEN@LAC | Jaylen Waddle 20+ rec yds | 62% | ✗ 19 |
| 3 | DET@ARI | Michael Wilson 5+ receptions | 62% | ✗ 4 |
| 4 | LV@NE | TreVeyon Henderson 50+ rush yds | 62% | ✗ 22 |
| 5 | MIN@NO | T.J. Hockenson 30+ rec yds | 62% | ✗ 7 |
| 6 | CLE@NYJ | Geno Smith 200+ pass yds | 62% | ✗ 182 |
| 7 | NYG@WAS | Antonio Williams 3+ receptions | 62% | ✓ 3 |
| 8 | MIN@NO | Tyler Shough 40+ pass att | 62% | ✗ 25 |
| 9 | DEN@LAC | Courtland Sutton 3+ receptions | 62% | ✗ 2 |
| 10 | CIN@MIA | Joe Burrow 250+ pass yds | 62% | ✗ 190 |

**12-leg** — 0.4% · fair +22473 — 3/12 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | IND@PIT | Pat Freiermuth 30+ rec yds | 62% | ✓ 44 |
| 2 | DEN@LAC | Jaylen Waddle 20+ rec yds | 62% | ✗ 19 |
| 3 | DET@ARI | Michael Wilson 5+ receptions | 62% | ✗ 4 |
| 4 | LV@NE | TreVeyon Henderson 50+ rush yds | 62% | ✗ 22 |
| 5 | MIN@NO | T.J. Hockenson 30+ rec yds | 62% | ✗ 7 |
| 6 | CLE@NYJ | Geno Smith 200+ pass yds | 62% | ✗ 182 |
| 7 | NYG@WAS | Antonio Williams 3+ receptions | 62% | ✓ 3 |
| 8 | MIN@NO | Tyler Shough 40+ pass att | 62% | ✗ 25 |
| 9 | CLE@NYJ | Denzel Boston 50+ rec yds | 62% | ✗ 46 |
| 10 | DEN@LAC | Courtland Sutton 3+ receptions | 62% | ✗ 2 |
| 11 | CIN@MIA | Joe Burrow 250+ pass yds | 62% | ✗ 190 |
| 12 | DET@ARI | Sam LaPorta 5+ receptions | 62% | ✓ 5 |


### ATD board (top 16) — Week 5 — aggressive band

| # | Game | Player | Model | Fair | Result |
|---|---|---|---|---|---|
| 1 | DET@ARI | Jahmyr Gibbs (RB) | 61% | -158 | ✓ TD |
| 2 | DET@ARI | Amon-Ra St. Brown (WR) | 50% | +102 | ✗ no TD |
| 3 | CLE@NYJ | Quinshon Judkins (RB) | 49% | +102 | ✗ no TD |
| 4 | CIN@MIA | Chase Brown (RB) | 48% | +109 | ✗ no TD |
| 5 | DET@ARI | Trey McBride (TE) | 47% | +113 | ✓ TD |
| 6 | BAL@ATL | Derrick Henry (RB) | 46% | +120 | ✓ TD |
| 7 | CHI@GB | D'Andre Swift (RB) | 43% | +133 | ✓ TD |
| 8 | HOU@TEN | David Montgomery (RB) | 42% | +138 | ✗ no TD |
| 9 | DET@ARI | Sam LaPorta (TE) | 40% | +149 | ✓ TD |
| 10 | HOU@TEN | Nico Collins (WR) | 40% | +150 | ✗ no TD |
| 11 | BAL@ATL | Bijan Robinson (RB) | 39% | +156 | ✗ no TD |
| 12 | SF@SEA | Christian McCaffrey (RB) | 39% | +157 | ✓ TD |
| 13 | NYG@WAS | Cam Skattebo (RB) | 38% | +160 | ✗ no TD |
| 14 | IND@PIT | Jonathan Taylor (RB) | 38% | +163 | ✗ no TD |
| 15 | HOU@TEN | Woody Marks (RB) | 37% | +168 | ✗ no TD |
| 16 | LV@NE | Brock Bowers (TE) | 35% | +186 | ✓ TD |

Board: top-16 7/16 · top-8 4/8 · chalk triple 1/3

**2+ TD board (singles only):** Jahmyr Gibbs 24% (+307) · Amon-Ra St. Brown 15% (+566) · Quinshon Judkins 15% (+570) · Chase Brown 14% (+623) · Trey McBride 13% (+651) · Derrick Henry 12% (+705)


### Scorecard — Week 5 — aggressive band

**Legs 55/101 = 54% actual vs 61% expected · SGP4 2/13 · SGP6 0/13 · SGP8 0/13**

| Game | Final | Legs | SGP4 | SGP6 | SGP8 |
|---|---|---|---|---|---|
| LV@NE | 17-45 | 7/8 | ✗ | ✗ | ✗ |
| NYG@WAS | 27-27 | 7/8 | ✓ | ✗ | ✗ |
| PHI@JAX | 17-19 | 6/7 | ✓ | ✗ | ✗ |
| BAL@ATL | 30-23 | 6/7 | ✗ | ✗ | ✗ |
| CHI@GB | 7-31 | 5/8 | ✗ | ✗ | ✗ |
| IND@PIT | 22-34 | 5/8 | ✗ | ✗ | ✗ |
| DET@ARI | 45-21 | 5/8 | ✗ | ✗ | ✗ |
| HOU@TEN | 26-3 | 4/8 | ✗ | ✗ | ✗ |
| CLE@NYJ | 12-17 | 3/8 | ✗ | ✗ | ✗ |
| MIN@NO | 23-13 | 3/8 | ✗ | ✗ | ✗ |
| SF@SEA | 32-29 | 3/8 | ✗ | ✗ | ✗ |
| DEN@LAC | 23-17 | 1/8 | ✗ | ✗ | ✗ |
| CIN@MIA | 31-24 | 0/7 | ✗ | ✗ | ✗ |


## Week 5 — Afternoon rebuild (DET@ARI, BAL@ATL, DEN@LAC, SF@SEA) at final inactives

*Engine v1.9c (name-collision fix shipped inside this run). Built ~12:45 PT with official inactives: Marvin Harrison Jr. scratched (trade), McConkey active-but-limited (pulled from tickets after the user flagged it), Hampton losing touches to Mitchell (user catch → Hampton 30+ replaced 40+; the 30+ cashed at 33 yards, the 40+ would not have). Rendered: NFL-Week5-Afternoon-Update.pdf, NFL-Week5-Afternoon-Position-Slips.pdf.*


### DET@ARI — final 45-21

**FLOOR** — 4-leg 44.9% · fair +123 **CASHED** · 6-leg 29.5% · fair +239 **CASHED**

| # | Leg | Model | Result |
|---|---|---|---|
| 1 | Amon-Ra St. Brown 5+ receptions | 78% | ✓ 6 |
| 2 | Kendrick Bourne 1+ receptions | 77% | ✓ 5 |
| 3 | Jacoby Brissett 200+ pass yds | 79% | ✓ 292 |
| 4 | Jared Goff 250+ pass yds | 76% | ✓ 271 |
| 5 | Sam LaPorta 40+ rec yds | 76% | ✓ 88 |
| 6 | Jeremiyah Love 10+ carries | 76% | ✓ 12 |
| 7 | Michael Wilson 40+ rec yds | 74% | ✗ 30 |
| 8 | Jahmyr Gibbs 30+ rush yds | 74% | ✓ 151 |

**AGGRESSIVE** — 4-leg 19.1% · fair +422 ✗ · 6-leg 12.7% · fair +689 ✗

| # | Leg | Model | Result |
|---|---|---|---|
| 1 | Jahmyr Gibbs 30+ rec yds | 61% | ✓ 56 |
| 2 | Jeremiyah Love 50+ rush yds | 63% | ✗ 22 |
| 3 | Trey McBride 60+ rec yds | 61% | ✓ 66 |
| 4 | Jared Goff 35+ pass att | 64% | ✗ 30 |
| 5 | Amon-Ra St. Brown 7+ receptions | 60% | ✗ 6 |
| 6 | Jacoby Brissett o0.5 INT o0.5 | 64% | ✓ 1 INT |
| 7 | Sam LaPorta 5+ receptions | 64% | ✓ 5 |
| 8 | Jared Goff 275+ pass yds | 64% | ✗ 271 |

**ATD:** Jahmyr Gibbs 62% (-162) ✓ · Trey McBride 53% (-113) ✓ · Amon-Ra St. Brown 50% (-101) ✗ · Sam LaPorta 41% (+146) ✓ · Michael Wilson 38% (+166) ✗


### BAL@ATL — final 30-23

**FLOOR** — 4-leg 35.6% · fair +181 ✗ · 6-leg 23.5% · fair +326 ✗

| # | Leg | Model | Result |
|---|---|---|---|
| 1 | Brian Robinson 20+ rush yds | 78% | ✗ 16 |
| 2 | Bijan Robinson 2+ receptions | 79% | ✓ 4 |
| 3 | Michael Penix Jr. 150+ pass yds | 72% | ✓ 240 |
| 4 | Drake London 60+ rec yds | 71% | ✓ 118 |
| 5 | Derrick Henry 20+ carries | 71% | ✓ 24 |
| 6 | Drake London 5+ receptions | 71% | ✓ 7 |

**AGGRESSIVE** — 4-leg 15.5% · fair +544 ✗ · 6-leg 9.4% · fair +961 ✗

| # | Leg | Model | Result |
|---|---|---|---|
| 1 | Michael Penix Jr. 20+ pass att | 61% | ✓ 32 |
| 2 | Bijan Robinson 100+ rush yds | 61% | ✗ 86 |
| 3 | Drake London 6+ receptions | 59% | ✓ 7 |
| 4 | Bijan Robinson 30+ rec yds | 59% | ✓ 32 |
| 5 | Drake London 80+ rec yds | 59% | ✓ 118 |
| 6 | Michael Penix Jr. 200+ pass yds | 58% | ✓ 240 |

**ATD:** Bijan Robinson 50% (+100) ✗ · Derrick Henry 48% (+111) ✓ · Drake London 30% (+238) ✗ · Brian Robinson 24% (+308) ✗


### DEN@LAC — final 23-17

**FLOOR** — 4-leg 45.3% · fair +121 ✗ · 6-leg 24.0% · fair +316 ✗

| # | Leg | Model | Result |
|---|---|---|---|
| 1 | Justin Herbert 25+ pass att | 78% | ✗ 24 |
| 2 | Bo Nix 30+ pass att | 78% | ✗ 27 |
| 3 | Courtland Sutton 2+ receptions | 80% | ✓ 2 |
| 4 | Oronde Gadsden II 2+ receptions | 76% | ✗ 0 |
| 5 | Omarion Hampton 30+ rush yds | 73% | ✓ 33 |
| 6 | J.K. Dobbins 10+ carries | 73% | ✓ 18 |
| 7 | Justin Herbert 20+ rush yds | 76% | ✓ 54 |
| 8 | Courtland Sutton 20+ rec yds | 74% | ✗ 18 |

**AGGRESSIVE** — 4-leg 16.6% · fair +503 ✗ · 6-leg 11.4% · fair +780 ✗

| # | Leg | Model | Result |
|---|---|---|---|
| 1 | Oronde Gadsden II 30+ rec yds | 62% | ✗ 0 |
| 2 | Omarion Hampton 50+ rush yds | 62% | ✗ 33 |
| 3 | RJ Harvey 5+ receptions | 61% | ✗ 0 |
| 4 | Justin Herbert 30+ rush yds | 64% | ✓ 54 |
| 5 | Jaylen Waddle 3+ receptions | 59% | ✗ 2 |
| 6 | Courtland Sutton 30+ rec yds | 65% | ✗ 18 |
| 7 | Bo Nix 35+ pass att | 57% | ✗ 27 |
| 8 | Justin Herbert 200+ pass yds | 59% | ✗ 121 |

**ATD:** Omarion Hampton 34% (+195) ✗ · J.K. Dobbins 29% (+242) ✓ · RJ Harvey 28% (+261) ✗ · Courtland Sutton 27% (+268) ✓ · Bo Nix 23% (+337) ✗


### SF@SEA — final 32-29

**FLOOR** — 4-leg 39.9% · fair +151 ✗ · 6-leg 26.7% · fair +274 ✗

| # | Leg | Model | Result |
|---|---|---|---|
| 1 | Brock Purdy 175+ pass yds | 78% | ✓ 189 |
| 2 | Deebo Samuel Sr. 30+ rec yds | 78% | ✗ 21 |
| 3 | Christian McCaffrey 10+ carries | 78% | ✓ 11 |
| 4 | George Kittle 3+ receptions | 76% | ✓ 5 |
| 5 | Mike Evans 20+ rec yds | 75% | ✓ 113 |
| 6 | Jaxon Smith-Njigba 6+ receptions | 71% | ✗ 5 |
| 7 | Brock Purdy 25+ pass att | 77% | ✓ 29 |

**AGGRESSIVE** — 4-leg 17.2% · fair +480 ✗ · 6-leg 8.4% · fair +1094 ✗

| # | Leg | Model | Result |
|---|---|---|---|
| 1 | George Kittle 40+ rec yds | 62% | ✗ 24 |
| 2 | Kaelon Black 30+ rush yds | 63% | ✗ 16 |
| 3 | Deebo Samuel Sr. 4+ receptions | 63% | ✗ 2 |
| 4 | Christian McCaffrey 5+ receptions | 60% | ✗ 3 |
| 5 | Sam Darnold 150+ pass yds | 59% | ✓ 195 |
| 6 | Emanuel Wilson 30+ rush yds | 59% | ✓ 61 |
| 7 | Brock Purdy 200+ pass yds | 66% | ✗ 189 |
| 8 | Mike Evans 40+ rec yds | 57% | ✓ 113 |

**ATD:** Christian McCaffrey 39% (+157) ✓ · Jaxon Smith-Njigba 35% (+183) ✓ · Mike Evans 25% (+306) ✓ · AJ Barner 24% (+311) ✗ · George Kittle 24% (+319) ✗


### Week 5 afternoon — all-position slips (first use of the format)

**DEN@LAC slip5** — 18.1% · fair +451 ✗: Justin Herbert 25+ pass att ✗(24) · Omarion Hampton 30+ rush yds ✓(33) · Courtland Sutton 2+ receptions ✓(2) · Oronde Gadsden II 2+ receptions ✗(0) · Omarion Hampton ANYTIME TD ✗(no TD)

**DEN@LAC slip8** — 6.0% · fair +1566 ✗: Justin Herbert 25+ pass att ✗(24) · Omarion Hampton 30+ rush yds ✓(33) · Courtland Sutton 2+ receptions ✓(2) · Oronde Gadsden II 2+ receptions ✗(0) · J.K. Dobbins 10+ carries ✓(18) · Bo Nix 30+ pass att ✗(27) · Omarion Hampton ANYTIME TD ✗(no TD) · J.K. Dobbins ANYTIME TD ✓(TD)

**DET@ARI slip5** — 36.6% · fair +173 **CASHED**: Jared Goff 250+ pass yds ✓(271) · Jahmyr Gibbs 2+ receptions ✓(5) · Amon-Ra St. Brown 5+ receptions ✓(6) · Sam LaPorta 40+ rec yds ✓(88) · Jahmyr Gibbs ANYTIME TD ✓(TD)

**DET@ARI slip8** — 16.2% · fair +517 ✗: Jared Goff 250+ pass yds ✓(271) · Jahmyr Gibbs 2+ receptions ✓(5) · Amon-Ra St. Brown 5+ receptions ✓(6) · Sam LaPorta 40+ rec yds ✓(88) · Jeremiyah Love 10+ carries ✓(12) · Michael Wilson 40+ rec yds ✗(30) · Jahmyr Gibbs ANYTIME TD ✓(TD) · Trey McBride ANYTIME TD ✓(TD)

**SF@SEA slip5** — 22.3% · fair +349 ✗: Brock Purdy 175+ pass yds ✓(189) · Christian McCaffrey 10+ carries ✓(11) · Deebo Samuel Sr. 30+ rec yds ✗(21) · George Kittle 3+ receptions ✓(5) · Christian McCaffrey ANYTIME TD ✓(TD)

**SF@SEA slip8** — 8.0% · fair +1144 ✗: Brock Purdy 175+ pass yds ✓(189) · Christian McCaffrey 10+ carries ✓(11) · Deebo Samuel Sr. 30+ rec yds ✗(21) · George Kittle 3+ receptions ✓(5) · Mike Evans 20+ rec yds ✓(113) · Jaxon Smith-Njigba 6+ receptions ✗(5) · Christian McCaffrey ANYTIME TD ✓(TD) · Jaxon Smith-Njigba ANYTIME TD ✓(TD)

**BAL@ATL slip5** — 27.3% · fair +266 ✗: Michael Penix Jr. 150+ pass yds ✓(240) · Brian Robinson 20+ rush yds ✗(16) · Drake London 60+ rec yds ✓(118) · Bijan Robinson ANYTIME TD ✗(no TD)

**BAL@ATL slip8** — 14.5% · fair +590 ✗: Michael Penix Jr. 150+ pass yds ✓(240) · Brian Robinson 20+ rush yds ✗(16) · Drake London 60+ rec yds ✓(118) · Bijan Robinson 2+ receptions ✓(4) · Bijan Robinson ANYTIME TD ✗(no TD) · Derrick Henry ANYTIME TD ✓(TD)


### Week 5 afternoon — cross-combo (floor, max 2 legs/game)

**4-leg** — 40.7% · fair +146 — 1/4: Brock Purdy 175+ pass yds ✓ · Deebo Samuel Sr. 30+ rec yds ✗ · Justin Herbert 25+ pass att ✗ · Bo Nix 30+ pass att ✗

**6-leg** — 24.3% · fair +312 — 2/6: Brock Purdy 175+ pass yds ✓ · Deebo Samuel Sr. 30+ rec yds ✗ · Justin Herbert 25+ pass att ✗ · Bo Nix 30+ pass att ✗ · Brian Robinson 20+ rush yds ✗ · Amon-Ra St. Brown 5+ receptions ✓

**8-leg** — 15.2% · fair +556 — 4/8: Brock Purdy 175+ pass yds ✓ · Deebo Samuel Sr. 30+ rec yds ✗ · Justin Herbert 25+ pass att ✗ · Bo Nix 30+ pass att ✗ · Brian Robinson 20+ rush yds ✗ · Amon-Ra St. Brown 5+ receptions ✓ · Kendrick Bourne 1+ receptions ✓ · Bijan Robinson 80+ rush yds ✓


## Week 5 TNF — TB @ DAL (Oct 8 2026) — final TB 24, DAL 16

*Engine v1.9 + hand-applied personnel at inactives (Mayfield OUT → Daniels; Winfield Jr. and Morrison OUT; surprise scratch Joey Porter Jr. + Cobie Durant; Tyler Smith activated). Rendered: TB-DAL-TNF-Week5-Pack.pdf.*

**Floor 8** — 6/8: Dak 30+ att ✓(42) · Javonte 50+ rush yds ✗(45) · Pickens 40+ rec yds ✓(130) · Egbuka 30+ rec yds ✓(38) | +6: Dak 225+ ✓(316) · Irving 2+ rec ✓(2) | +8: Javonte 2+ rec ✓(2) · Godwin 4+ rec ✗(3). 4-leg ✗ on Javonte.
**Dallas air stack (5)** — 2/5: Dak 2+ pass TDs ✗(1) · Lamb 60+ ✗(9) · Lamb 5+ rec ✗(2) · Pickens 3+ rec ✓(9) · Ferguson 2+ rec ✓(3).
**Tampa chase stack (5)** — 3/5: Egbuka 4+ rec ✓(6) · Egbuka 40+ ✗(38) · Godwin 4+ rec ✗(3) · Daniels 175+ ✓(189) · Irving 2+ rec ✓(2).
**Aggressive 6** — 1/6. **User's slip, critiqued and rebuilt** (Lamb 60+ · Javonte 50+ · Javonte ATD · Ferguson 2+) — 2/4.
**ATD:** Javonte 50% ✓ · Lamb 33% ✗ · Egbuka 34% ✓ · Irving 32% ✓ · Pickens 31% ✓. The two "fades" (Irving, Pickens) both scored — logged as a model-side error in the Week 5 report card: a fade on red-zone share ignores that a flipped game script makes every Tampa touchdown available.


## Week 6 — Sunday Oct 18 2026 (shipped floor, v1.9e)

*Engine v1.9e.* Shipped with official inactives (Hurts OUT → McKee; Barkley/Shipley OUT → Pierce; Mayfield OUT → Daniels; Lamar OUT → Huntley; Breece Hall OUT → Braelon Allen; Caleb Williams active; Rice, Tre Harris, Theo Johnson OUT). London game skipped (kicked off). Report card (Weeks6-8-Report-Card.pdf): 73% vs 76%, SGP4 2/11 — BUF@LV 8/8 with all three SGPs cashed. The v1.9f build of this same slate (next section) is the model's out-of-sample exam.


### BAL@CLE — final 10-13
*O/U 39.5 · spread -3.0 · outdoor · grass · 13:00 ET*

**Personnel:** BAL: Lamar OUT — Huntley 2nd start; Jurgens, Hibner OUT. CLE: Watson starts (Gabriel IR); Sampson OUT; Judkins Q — singles only.

**Injury report (as built):** BAL OFF · Lamar Jackson (QB) — Out · Ankle · DNP; BAL DEF · Broderick Washington (DE) — Out · Ankle · DNP; BAL OFF · Cam Jurgens (C) — Out · Concussion; BAL OFF · Matthew Hibner (TE) — Out · Hand · DNP; BAL OFF · Andrew Vorhees (G) — Questionable · Foot; BAL OFF · Emery Jones Jr. (G) — Questionable · Ankle; BAL OFF · Ja'Kobi Lane (WR) — Questionable · Wrist; BAL DEF · Calais Campbell (DT) — nan · DNP

**Defensive leaks:** BAL D leaks receiving yards to RBs: x1.20; BAL D leaks receptions to RBs: x1.18; BAL D leaks receiving yards to WRs: x1.17 (worsening x1.23 L4)

**Coordinators:** BAL OC Declan Doyle — NEW (pass_wr) · measured pass 46% | DC Anthony Weaver (pressure) · CLE OC Travis Switzer — NEW (run_heavy) · measured pass 54% | DC Mike Rutenberg (multiple)

**Props SGP** — 4-leg 37.8% · fair +165 ✗ · 6-leg 28.0% · fair +258 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Derrick Henry 70+ rush yds | 77% | -328 | ✗ 58 | `4-leg core` · 2026 4/5 pre-game
| 2 | Denzel Boston 2+ receptions | 80% | -397 | ✗ 1 | `4-leg core` · 2026 5/5 pre-game
| 3 | Mark Andrews 2+ receptions | 76% | -318 | ✗ 1 | `4-leg core` · 2026 5/5 pre-game
| 4 | Zay Flowers 40+ rec yds | 76% | -315 | ✓ 66 | `4-leg core` · 2026 4/4 pre-game
| 5 | Deshaun Watson 25+ pass att | 74% | -289 | ✓ 26 | `+6` · 2026 4/5 pre-game
| 6 | Harold Fannin Jr. 20+ rec yds | 74% | -290 | ✗ 9 | `+6` · 2026 4/5 pre-game
| 7 | Deshaun Watson 150+ pass yds | 70% | -236 | ✓ 164 | `+8` · 2026 4/5 pre-game

Legs 3/7 (expected 5.3)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Derrick Henry (BAL RB) | 50% | -102 | ✗ no TD | share 30% · team 2.38 TD · RZ-D 0.99 · pos-D 0.91 |
| Denzel Boston (CLE WR) | 28% | +257 | ✗ no TD | share 17% · team 2.04 TD · RZ-D 0.89 · pos-D 0.98 |
| Mark Andrews (BAL TE) | 24% | +308 | ✗ no TD | share 15% · team 2.38 TD · RZ-D 0.99 · pos-D 0.9 |
| Harold Fannin Jr. (CLE TE) | 21% | +376 | ✗ no TD | share 14% · team 2.04 TD · RZ-D 0.89 · pos-D 0.85 |

TD double (Derrick Henry + Denzel Boston): 16.1% · fair +521 ✗

**All-position slip** — 24.9% · fair +302 ✗: Deshaun Watson 25+ pass att ✓(26) · Derrick Henry 70+ rush yds ✗(58) · Denzel Boston 2+ receptions ✗(1) · Mark Andrews 2+ receptions ✗(1) · Derrick Henry ANYTIME TD ✗(no TD)

**All-position 8-leg** — 8.2% · fair +1116 ✗: Deshaun Watson 25+ pass att ✓(26) · Derrick Henry 70+ rush yds ✗(58) · Denzel Boston 2+ receptions ✗(1) · Mark Andrews 2+ receptions ✗(1) · Zay Flowers 40+ rec yds ✓(66) · Harold Fannin Jr. 20+ rec yds ✗(9) · Derrick Henry ANYTIME TD ✗(no TD) · Denzel Boston ANYTIME TD ✗(no TD)


### CAR@PHI — final 25-14
*O/U 39.5 · spread -3.0 · outdoor · grass · 13:00 ET*

**Personnel:** PHI: Hurts OUT (calf clot) — Tanner McKee starts. Barkley, Shipley OUT, Bigsby IR — Dameon Pierce backfield. Dickerson (G), Calcaterra (TE), Carter II (S), Bennett (CB) OUT. CAR: Dillon OUT, Freeling doubtful; Etienne, Moton Q.

**Injury report (as built):** CAR OFF · Monroe Freeling (T) — Doubtful · Knee; CAR OFF · AJ Dillon (RB) — Out · Ankle · DNP; CAR OFF · Taylor Moton (T) — Questionable · Lung; CAR DEF · Tershawn Wharton (DT) — Questionable · Neck; CAR OFF · Damien Lewis (G) — Questionable · Elbow; CAR DEF · Jaelan Phillips (LB) — Questionable · Hamstring; CAR OFF · Trevor Etienne (RB) — Questionable · Ankle; PHI DEF · A.J. Epenesa (LB) — Doubtful · Back · DNP

**Defensive leaks:** CAR D leaks rushing yards to RBs: x1.34; CAR D leaks carries to RBs: x1.17; CAR D leaks receiving yards to TEs: x1.08 (worsening x1.26 L4)

**Coordinators:** CAR OC Brad Idzik — continuity · measured pass 63% | DC Ejiro Evero (two_high_shell) · PHI OC Sean Mannion — NEW (run_heavy) · measured pass 56% | DC Vic Fangio (two_high_shell)

**Props SGP** — 4-leg 47.2% · fair +112 ✗ · 6-leg 28.4% · fair +252 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Chuba Hubbard 2+ receptions | 78% | -352 | ✗ 1 | `4-leg core` · 2026 3/4 pre-game
| 2 | Tetairoa McMillan 3+ receptions | 77% | -343 | ✓ 6 | `4-leg core` · 2026 3/4 pre-game
| 3 | Darren Waller 20+ rec yds | 74% | -279 | ✗ 0 | `4-leg core` · 2026 4/4 pre-game
| 4 | Bryce Young 175+ pass yds | 73% | -275 | ✓ 281 | `4-leg core` · 2026 4/4 pre-game
| 5 | DeVonta Smith 20+ rec yds | 72% | -256 | ✓ 75 | `+6` · 2026 3/3 pre-game
| 6 | Chuba Hubbard 10+ carries | 84% | -516 | ✓ 28 | `+6` · 2026 4/4 pre-game
| 7 | Bryce Young 25+ pass att | 86% | -614 | ✓ 39 | `+8` · 2026 4/4 pre-game

Legs 5/7 (expected 5.4)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Chuba Hubbard (CAR RB) | 38% | +160 | ✓ TD | share 19% · team 2.38 TD · RZ-D 0.94 · pos-D 1.01 |
| Dallas Goedert (PHI TE) | 29% | +246 | ✗ no TD | share 14% · team 2.04 TD · RZ-D 0.98 · pos-D 1.08 |
| Tetairoa McMillan (CAR WR) | 27% | +266 | ✗ no TD | share 16% · team 2.38 TD · RZ-D 0.94 · pos-D 0.88 |
| DeVonta Smith (PHI WR) | 25% | +294 | ✓ TD | share 16% · team 2.04 TD · RZ-D 0.98 · pos-D 0.85 |

TD double (Chuba Hubbard + Dallas Goedert): 13.0% · fair +670 ✗

**All-position slip** — 23.4% · fair +326 ✗: Bryce Young 175+ pass yds ✓(281) · Chuba Hubbard 2+ receptions ✗(1) · Tetairoa McMillan 3+ receptions ✓(6) · Darren Waller 20+ rec yds ✗(0) · Chuba Hubbard ANYTIME TD ✓(TD)

**All-position 8-leg** — 7.8% · fair +1186 ✗: Bryce Young 175+ pass yds ✓(281) · Chuba Hubbard 2+ receptions ✗(1) · Tetairoa McMillan 3+ receptions ✓(6) · Darren Waller 20+ rec yds ✗(0) · DeVonta Smith 20+ rec yds ✓(75) · Chuba Hubbard ANYTIME TD ✓(TD) · Dallas Goedert ANYTIME TD ✗(no TD)


### CHI@ATL — final 31-23
*O/U 51.5 · spread -1.5 · indoor · turf · 13:00 ET*

**Personnel:** CHI: Caleb Williams ACTIVE (hamstring) per club; Monangai OUT — Swift; T.J. Edwards, Odeyingbo OUT; Gordon, Stevenson Q. ATL: C.J. Henderson OUT; Z. Smith Q.

**Injury report (as built):** ATL DEF · C.J. Henderson (CB) — Out · Groin · DNP; ATL DEF · Za'Darius Smith (DE) — Questionable · Neck; CHI DEF · T.J. Edwards (LB) — Out · Hamstring · DNP; CHI DEF · Dayo Odeyingbo (DE) — Out · Quadricep · DNP; CHI OFF · Kyle Monangai (RB) — Out · Thumb · DNP; CHI DEF · Keyshaun Elliott (LB) — Out · Quadricep · DNP; CHI DEF · Kyler Gordon (CB) — Questionable · Calf; CHI DEF · Tyrique Stevenson (CB) — Questionable · Hip

**Defensive leaks:** ATL D leaks receptions to RBs: x1.14 (worsening x1.11 L4); ATL D leaks receptions to WRs: x1.10 (worsening x1.27 L4); CHI D leaks passing interceptions to QBs: x1.35; CHI D leaks rushing yards to RBs: x1.15

**Coordinators:** CHI OC Press Taylor — NEW (pass_wr) · measured pass 48% | DC Dennis Allen (blitz_man) · ATL OC Tommy Rees — NEW (run_heavy) · measured pass 45% | DC Jeff Ulbrich (blitz_heavy)

**Props SGP** — 4-leg 38.2% · fair +162 ✗ · 6-leg 23.2% · fair +331 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | D'Andre Swift 15+ carries | 80% | -393 | ✓ 16 | `4-leg core` · 2026 4/5 pre-game
| 2 | Bijan Robinson 2+ receptions | 75% | -305 | ✓ 2 | `4-leg core` · 2026 4/5 pre-game
| 3 | Drake London 5+ receptions | 74% | -292 | ✗ 4 | `4-leg core` · 2026 3/5 pre-game
| 4 | Rome Odunze 40+ rec yds | 74% | -293 | ✗ 39 | `4-leg core` · 2026 5/5 pre-game
| 5 | Luther Burden III 30+ rec yds | 74% | -283 | ✓ 95 | `+6` · 2026 5/5 pre-game
| 6 | Brian Robinson 30+ rush yds | 74% | -282 | ✗ 1 | `+6` · 2026 4/5 pre-game
| 7 | Michael Penix Jr. 175+ pass yds | 73% | -273 | ✓ 225 | `+8` · 2026 3/3 pre-game

Legs 4/7 (expected 5.2)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Bijan Robinson (ATL RB) | 50% | +102 | ✗ no TD | share 28% · team 2.8 TD · RZ-D 0.97 · pos-D 0.94 |
| D'Andre Swift (CHI RB) | 48% | +107 | ✓ TD | share 19% · team 2.97 TD · RZ-D 0.93 · pos-D 0.94 |
| Drake London (ATL WR) | 44% | +130 | ✗ no TD | share 18% · team 2.8 TD · RZ-D 0.97 · pos-D 1.18 |
| Rome Odunze (CHI WR) | 41% | +144 | ✗ no TD | share 14% · team 2.97 TD · RZ-D 0.93 · pos-D 1.11 |

TD double (Bijan Robinson + D'Andre Swift): 26.1% · fair +283 ✗

**All-position slip** — 22.6% · fair +342 ✗: Michael Penix Jr. 175+ pass yds ✓(225) · D'Andre Swift 15+ carries ✓(16) · Drake London 5+ receptions ✗(4) · Colston Loveland 2+ receptions ✓(6) · Bijan Robinson ANYTIME TD ✗(no TD)

**All-position 8-leg** — 10.7% · fair +837 ✗: Michael Penix Jr. 175+ pass yds ✓(225) · D'Andre Swift 15+ carries ✓(16) · Drake London 5+ receptions ✗(4) · Colston Loveland 2+ receptions ✓(6) · Brian Robinson 30+ rush yds ✗(1) · Rome Odunze 40+ rec yds ✗(39) · Bijan Robinson ANYTIME TD ✗(no TD) · D'Andre Swift ANYTIME TD ✓(TD)


### NO@NYG — final 34-27
*O/U 46.5 · spread -1.5 · outdoor · turf · 13:00 ET*

**Personnel:** NYG: Theo Johnson (TE), Nubin (S), Hood (CB) OUT; A. Thomas, Eluemunor Q. NO: Elliss, Jennings (LBs) OUT; Kamara, Olave Q — singles only.

**Injury report (as built):** NO DEF · Kaden Elliss (LB) — Out · Calf · DNP; NO DEF · Anfernee Jennings (LB) — Out · Knee · DNP; NO OFF · Zach Wood (LS) — Questionable · Calf; NO OFF · Alvin Kamara (RB) — Questionable · Back; NO DEF · Nathan Shepherd (DT) — Questionable · Illness; NO OFF · Chris Olave (WR) — Questionable · Illness; NO DEF · Lorenzo Styles Jr. (CB) — Questionable · Knee; NYG OFF · Theo Johnson (TE) — Out · Neck · DNP

**Defensive leaks:** NYG D leaks rushing yards to RBs: x1.19; NO D leaks rushing yards to RBs: x1.17 (worsening x1.30 L4); NO D leaks carries to RBs: x1.12 (worsening x1.12 L4)

**Coordinators:** NO OC Doug Nussmeier — continuity · measured pass 64% | DC Brandon Staley (two_high_shell) · NYG OC Matt Nagy — NEW (pass_wr) · measured pass 53% | DC Dennard Wilson (pressure)

**Props SGP** — 4-leg 47.3% · fair +111 ✗ · 6-leg 24.5% · fair +309 ✗ · 8-leg 16.7% · fair +498 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Tyler Shough 25+ pass att | 78% | -345 | ✓ 30 | `4-leg core` · 2026 5/5 pre-game
| 2 | Devaughn Vele 4+ receptions | 78% | -345 | ✗ 3 | `4-leg core` · 2026 4/5 pre-game
| 3 | Cam Skattebo 40+ rush yds | 79% | -373 | – DNP | `4-leg core` · 2026 4/5 pre-game
| 4 | Juwan Johnson 4+ receptions | 79% | -378 | ✗ 0 | `4-leg core` · 2026 4/5 pre-game
| 5 | Isaiah Likely 20+ rec yds | 73% | -272 | ✓ 99 | `+6` · 2026 4/5 pre-game
| 6 | Kendre Miller 20+ rush yds | 72% | -257 | ✓ 70 | `+6` · 2026 2/4 pre-game
| 7 | Malik Nabers 40+ rec yds | 71% | -243 | ✓ 165 | `+8` · 2026 3/5 pre-game
| 8 | Tyler Shough 250+ pass yds | 70% | -238 | ✗ 144 | `+8` · 2026 4/5 pre-game

Legs 4/7 (expected 6.0)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Malik Nabers (NYG WR) | 44% | +125 | ✗ no TD | share 21% · team 2.52 TD · RZ-D 0.96 · pos-D 1.06 |
| Cam Skattebo (NYG RB) | 40% | +151 | – DNP | share 17% · team 2.52 TD · RZ-D 0.96 · pos-D 1.12 |
| Tyler Shough (NO QB) | 30% | +232 | ✓ TD | share 11% · team 2.69 TD · RZ-D 1.06 · pos-D 1.2 |
| Devaughn Vele (NO WR) | 29% | +240 | ✗ no TD | share 12% · team 2.69 TD · RZ-D 1.06 · pos-D 1.04 |

TD double (Malik Nabers + Cam Skattebo): 22.2% · fair +351 ✗

**All-position slip** — 24.6% · fair +307 ✗: Tyler Shough 25+ pass att ✓(30) · Cam Skattebo 40+ rush yds –(DNP) · Devaughn Vele 4+ receptions ✗(3) · Juwan Johnson 4+ receptions ✗(0) · Malik Nabers ANYTIME TD ✗(no TD)

**All-position 8-leg** — 9.1% · fair +994 ✗: Tyler Shough 25+ pass att ✓(30) · Cam Skattebo 40+ rush yds –(DNP) · Devaughn Vele 4+ receptions ✗(3) · Juwan Johnson 4+ receptions ✗(0) · Kendre Miller 20+ rush yds ✓(70) · Malik Nabers 40+ rec yds ✓(165) · Malik Nabers ANYTIME TD ✗(no TD) · Cam Skattebo ANYTIME TD –(DNP)


### NYJ@NE — final 19-26
*O/U 43.5 · spread +7.5 · outdoor · turf · 13:00 ET*

**Personnel:** NYJ: Breece Hall OUT — Braelon Allen backfield; A. Mitchell OUT. NE: Carlton Davis III + Prunty (CBs) OUT; A.J. Brown activated off IR (no 2026 sample — not in pool); Henderson Q.

**Injury report (as built):** NE DEF · Carlton Davis III (CB) — Out · Neck · DNP; NE DEF · Karon Prunty (CB) — Out · Hamstring · DNP; NE OFF · A.J. Brown (WR) — Questionable · Ankle; NE DEF · Christian Elliss (LB) — Questionable · Chest; NE OFF · Marcus Bryant (T) — Questionable · Ankle; NE OFF · Will Campbell (T) — Questionable · Knee; NE DEF · Craig Woodson (S) — Questionable · Shoulder; NE OFF · TreVeyon Henderson (RB) — Questionable · Ankle

**Defensive leaks:** NYJ D leaks carries to RBs: x1.13 (worsening x1.25 L4); NYJ D leaks rushing yards to RBs: x1.10 (worsening x1.29 L4)

**Coordinators:** NYJ OC Frank Reich — NEW (balanced) · measured pass 53% | DC Brian Duker (multiple) · NE OC Josh McDaniels — continuity · measured pass 51% | DC Zak Kuhr (multiple)

**Props SGP** — 4-leg 42.6% · fair +135 ✗ · 6-leg 26.7% · fair +275 ✗ · 8-leg 19.3% · fair +418 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Drake Maye 20+ pass att | 78% | -359 | ✓ 32 | `4-leg core` · 2026 5/5 pre-game
| 2 | Geno Smith 175+ pass yds | 77% | -335 | ✓ 252 | `4-leg core` · 2026 4/5 pre-game
| 3 | Romeo Doubs 20+ rec yds | 76% | -324 | ✓ 42 | `4-leg core` · 2026 3/5 pre-game
| 4 | Garrett Wilson 50+ rec yds | 74% | -278 | ✗ 44 | `4-leg core` · 2026 4/5 pre-game
| 5 | Rhamondre Stevenson 10+ carries | 71% | -247 | ✓ 14 | `+6` · 2026 3/5 pre-game
| 6 | Geno Smith 20+ pass att | 80% | -391 | ✓ 30 | `+6` · 2026 4/5 pre-game
| 7 | Drake Maye 175+ pass yds | 73% | -274 | ✓ 235 | `+8` · 2026 5/5 pre-game
| 8 | Garrett Wilson 5+ receptions | 70% | -235 | ✗ 4 | `+8` · 2026 4/5 pre-game

Legs 6/8 (expected 6.0)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Rhamondre Stevenson (NE RB) | 54% | -117 | ✗ no TD | share 18% · team 2.86 TD · RZ-D 1.09 · pos-D 1.38 |
| Romeo Doubs (NE WR) | 37% | +171 | ✓ TD | share 15% · team 2.86 TD · RZ-D 1.09 · pos-D 1.01 |
| Garrett Wilson (NYJ WR) | 30% | +238 | ✗ no TD | share 13% · team 2.02 TD · RZ-D 1.04 · pos-D 1.05 |
| Braelon Allen (NYJ RB) | 25% | +297 | ✗ no TD | share 11% · team 2.02 TD · RZ-D 1.04 · pos-D 0.92 |

TD double (Rhamondre Stevenson + Romeo Doubs): 24.4% · fair +310 ✗

**All-position slip** — 29.7% · fair +237 ✗: Drake Maye 20+ pass att ✓(32) · Rhamondre Stevenson 10+ carries ✓(14) · Romeo Doubs 20+ rec yds ✓(42) · Rhamondre Stevenson ANYTIME TD ✗(no TD)

**All-position 8-leg** — 12.3% · fair +715 ✗: Drake Maye 20+ pass att ✓(32) · Rhamondre Stevenson 10+ carries ✓(14) · Romeo Doubs 20+ rec yds ✓(42) · Garrett Wilson 50+ rec yds ✗(44) · Geno Smith 175+ pass yds ✓(252) · Rhamondre Stevenson ANYTIME TD ✗(no TD) · Romeo Doubs ANYTIME TD ✓(TD)


### PIT@TB — final 26-19
*O/U 38.5 · spread -1.5 · outdoor · grass · 13:00 ET*

**Personnel:** TB: Mayfield OUT — Jalon Daniels 3rd start. Winfield Jr. (S) OUT, Morrison (CB) doubtful. PIT: DeShon Elliott (S), Roman Wilson, Skowronek OUT; Ramsey, Dean, Dowdle, Freiermuth Q (singles only).

**Injury report (as built):** PIT DEF · DeShon Elliott (S) — Out · Knee; PIT OFF · Ben Skowronek (WR) — Out · Calf · DNP; PIT OFF · Roman Wilson (WR) — Out · Finger · DNP; PIT DEF · Jalen Ramsey (CB) — Questionable · Wrist; PIT DEF · Jamel Dean (CB) — Questionable · Ankle; PIT OFF · Rico Dowdle (RB) — Questionable · Toe; PIT OFF · Pat Freiermuth (TE) — Questionable · Calf; PIT DEF · Keeanu Benton (DT) — Questionable · Ankle

**Defensive leaks:** TB D leaks receiving yards to RBs: x1.38; TB D leaks receiving yards to TEs: x1.18; TB D leaks receptions to RBs: x1.15; PIT D leaks passing interceptions to QBs: x1.32

**Coordinators:** PIT OC Brian Angelichio — NEW (pass_te) · measured pass 63% | DC Patrick Graham (multiple) · TB OC Zac Robinson — NEW (pass_wr) · measured pass 53% | DC Todd Bowles (blitz_heavy)

**Props SGP** — 4-leg 38.9% · fair +157 ✗ · 6-leg 28.3% · fair +254 ✗ · 8-leg 17.4% · fair +473 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Emeka Egbuka 2+ receptions | 78% | -357 | ✓ 7 | `4-leg core` · 2026 5/5 pre-game
| 2 | Chris Godwin Jr. 2+ receptions | 77% | -341 | ✓ 4 | `4-leg core` · 2026 5/5 pre-game
| 3 | Bucky Irving 40+ rush yds | 77% | -331 | ✓ 46 | `4-leg core` · 2026 5/5 pre-game
| 4 | Cade Otton 20+ rec yds | 76% | -325 | ✗ 4 | `4-leg core` · 2026 5/5 pre-game
| 5 | Aaron Rodgers 30+ pass att | 80% | -397 | ✓ 49 | `+6` · 2026 5/5 pre-game
| 6 | Jaylen Warren 20+ rec yds | 74% | -277 | ✓ 28 | `+6` · 2026 5/5 pre-game
| 7 | Jaylen Warren 10+ carries | 71% | -249 | ✓ 14 | `+8` · 2026 5/5 pre-game
| 8 | Aaron Rodgers 225+ pass yds | 71% | -242 | ✓ 253 | `+8` · 2026 3/5 pre-game

Legs 7/8 (expected 6.0)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Jaylen Warren (PIT RB) | 28% | +251 | ✗ no TD | share 15% · team 2.24 TD · RZ-D 1.04 · pos-D 0.94 |
| Bucky Irving (TB RB) | 27% | +275 | ✗ no TD | share 18% · team 2.07 TD · RZ-D 0.93 · pos-D 0.85 |
| DK Metcalf (PIT WR) | 26% | +279 | ✗ no TD | share 14% · team 2.24 TD · RZ-D 1.04 · pos-D 0.97 |
| Emeka Egbuka (TB WR) | 25% | +303 | ✓ TD | share 16% · team 2.07 TD · RZ-D 0.93 · pos-D 0.99 |

TD double (Jaylen Warren + Bucky Irving): 9.3% · fair +980 ✗

**All-position slip** — 14.5% · fair +587 ✗: Aaron Rodgers 30+ pass att ✓(49) · Bucky Irving 40+ rush yds ✓(46) · Emeka Egbuka 2+ receptions ✓(7) · Cade Otton 20+ rec yds ✗(4) · Jaylen Warren ANYTIME TD ✗(no TD)

**All-position 8-leg** — 5.3% · fair +1778 ✗: Aaron Rodgers 30+ pass att ✓(49) · Bucky Irving 40+ rush yds ✓(46) · Emeka Egbuka 2+ receptions ✓(7) · Cade Otton 20+ rec yds ✗(4) · Jaylen Warren 2+ receptions ✓(2) · DK Metcalf 30+ rec yds ✓(93) · Jaylen Warren ANYTIME TD ✗(no TD) · Bucky Irving ANYTIME TD ✗(no TD)


### TEN@IND — final 26-20
*O/U 43.5 · spread +6.5 · indoor · turf · 13:00 ET*

**Personnel:** TEN: Winston Jr. (S) OUT; Spears Q. IND: Dulin OUT; Tyler Warren Q — singles only.

**Injury report (as built):** IND OFF · Ashton Dulin (WR) — Out · Hamstring · DNP; IND DEF · Jaylon Carlies (LB) — Out · Ribs · DNP; IND OFF · Tyler Warren (TE) — Questionable · Groin; IND DEF · DeForest Buckner (DT) — nan · DNP; TEN DEF · Jordan Elliott (DT) — Out · Not injury related - personal matter · DNP; TEN DEF · Kevin Winston Jr. (S) — Out · Quadricep · DNP; TEN DEF · Joshua Williams (CB) — Questionable · Pectoral; TEN OFF · Tyjae Spears (RB) — Questionable · Knee

**Defensive leaks:** IND D leaks receiving yards to TEs: x1.19; IND D leaks receptions to TEs: x1.14; IND D leaks passing interceptions to QBs: x1.14

**Coordinators:** TEN OC Brian Daboll — NEW (pass_wr) · measured pass 59% | DC Gus Bradley (zone_cover3) · IND OC Jim Bob Cooter — continuity · measured pass 56% | DC Lou Anarumo (disguise_zone)

**Props SGP** — 4-leg 37.7% · fair +165 ✗ · 6-leg 26.3% · fair +280 ✗ · 8-leg 18.3% · fair +446 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Josh Downs 3+ receptions | 78% | -345 | ✓ 4 | `4-leg core` · 2026 4/5 pre-game
| 2 | Tony Pollard 40+ rush yds | 78% | -344 | ✓ 76 | `4-leg core` · 2026 4/5 pre-game
| 3 | Wan'Dale Robinson 5+ receptions | 79% | -385 | ✗ 3 | `4-leg core` · 2026 3/5 pre-game
| 4 | Jonathan Taylor 15+ carries | 76% | -324 | ✓ 21 | `4-leg core` · 2026 5/5 pre-game
| 5 | Daniel Jones 175+ pass yds | 76% | -314 | ✓ 269 | `+6` · 2026 3/5 pre-game
| 6 | Keenan Allen 30+ rec yds | 75% | -300 | ✓ 82 | `+6` · 2026 3/4 pre-game
| 7 | Cam Ward 175+ pass yds | 74% | -278 | ✗ 102 | `+8` · 2026 3/5 pre-game
| 8 | Carnell Tate 20+ rec yds | 71% | -243 | ✓ 70 | `+8` · 2026 4/5 pre-game

Legs 6/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Jonathan Taylor (IND RB) | 59% | -144 | ✓ TD | share 29% · team 2.8 TD · RZ-D 1.12 · pos-D 1.07 |
| Keenan Allen (IND WR) | 35% | +187 | ✗ no TD | share 13% · team 2.8 TD · RZ-D 1.12 · pos-D 1.08 |
| Tony Pollard (TEN RB) | 34% | +193 | ✗ no TD | share 19% · team 2.07 TD · RZ-D 0.97 · pos-D 1.04 |
| Wan'Dale Robinson (TEN WR) | 24% | +324 | ✗ no TD | share 13% · team 2.07 TD · RZ-D 0.97 · pos-D 1.01 |

TD double (Jonathan Taylor + Keenan Allen): 24.8% · fair +303 ✗

**All-position slip** — 35.1% · fair +185 **CASHED**: Daniel Jones 175+ pass yds ✓(269) · Tony Pollard 40+ rush yds ✓(76) · Josh Downs 3+ receptions ✓(4) · Jonathan Taylor ANYTIME TD ✓(TD)

**All-position 8-leg** — 12.8% · fair +683 ✗: Daniel Jones 175+ pass yds ✓(269) · Tony Pollard 40+ rush yds ✓(76) · Josh Downs 3+ receptions ✓(4) · Jonathan Taylor 15+ carries ✓(21) · Wan'Dale Robinson 5+ receptions ✗(3) · Jonathan Taylor ANYTIME TD ✓(TD) · Keenan Allen ANYTIME TD ✗(no TD)


### ARI@LA — final 18-16
*O/U 51.5 · spread +12.5 · indoor · turf · 16:05 ET*

**Personnel:** ARI: Jeremiyah Love OUT — Allgeier backfield; Wingard, W. Williams OUT; Budda Baker Q. LA: Curl, McDuffie Q. Dome.

**Injury report (as built):** ARI DEF · Andrew Wingard (S) — Out · Knee · DNP; ARI OFF · Jeremiyah Love (RB) — Out · Ankle · DNP; ARI DEF · Wydett Williams Jr. (S) — Out · Concussion · DNP; ARI DEF · Budda Baker (S) — Questionable · Not injury related - resting player · DNP; ARI OFF · Blake Gillikin (P) — Questionable · Back; ARI DEF · Zaven Collins (LB) — Questionable · Hip · DNP; ARI DEF · Kitan Crawford (S) — Questionable · Ankle; LA DEF · Kam Curl (S) — Questionable · Ankle · DNP

**Defensive leaks:** LA D leaks passing interceptions to QBs: x1.21; LA D leaks receiving yards to RBs: x1.15 (worsening x1.56 L4); ARI D leaks rushing yards to RBs: x1.16; ARI D leaks receiving yards to TEs: x1.10 (worsening x1.49 L4)

**Coordinators:** ARI OC Nathaniel Hackett — NEW (run_heavy) · measured pass 62% | DC Nick Rallis (blitz_heavy) · LA OC Nathan Scheelhaase — NEW (pass_wr) · measured pass 63% | DC Chris Shula (four_man_rush)

**Props SGP** — 4-leg 44.5% · fair +125 ✗ · 6-leg 27.1% · fair +269 ✗ · 8-leg 18.6% · fair +439 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Matthew Stafford 35+ pass att | 78% | -359 | ✗ 33 | `4-leg core` · 2026 3/5 pre-game
| 2 | Kyren Williams 2+ receptions | 79% | -367 | ✓ 3 | `4-leg core` · 2026 5/5 pre-game
| 3 | Michael Wilson 2+ receptions | 76% | -325 | ✓ 4 | `4-leg core` · 2026 5/5 pre-game
| 4 | Jacoby Brissett 150+ pass yds | 76% | -321 | ✓ 218 | `4-leg core` · 2026 4/5 pre-game
| 5 | Tyler Allgeier 20+ rush yds | 75% | -304 | ✓ 38 | `+6` · 2026 2/5 pre-game
| 6 | Trey McBride 50+ rec yds | 74% | -287 | ✓ 53 | `+6` · 2026 3/5 pre-game
| 7 | Puka Nacua 80+ rec yds | 74% | -283 | ✓ 80 | `+8` · 2026 2/3 pre-game
| 8 | Kyren Williams 15+ carries | 76% | -314 | ✗ 10 | `+8` · 2026 3/5 pre-game

Legs 6/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Kyren Williams (LA RB) | 70% | -229 | ✗ no TD | share 25% · team 3.58 TD · RZ-D 1.15 · pos-D 1.14 |
| Davante Adams (LA WR) | 66% | -199 | ✗ no TD | share 26% · team 3.58 TD · RZ-D 1.15 · pos-D 1.11 |
| Puka Nacua (LA WR) | 44% | +127 | ✗ no TD | share 14% · team 3.58 TD · RZ-D 1.15 · pos-D 1.11 |
| Trey McBride (ARI TE) | 34% | +190 | ✗ no TD | share 19% · team 2.18 TD · RZ-D 0.91 · pos-D 0.95 |

TD double (Kyren Williams + Davante Adams): 50.4% · fair -101 ✗

**All-position slip** — 34.0% · fair +194 ✗: Matthew Stafford 35+ pass att ✗(33) · Kyren Williams 2+ receptions ✓(3) · Michael Wilson 2+ receptions ✓(4) · Trey McBride 50+ rec yds ✓(53) · Kyren Williams ANYTIME TD ✗(no TD)

**All-position 8-leg** — 18.8% · fair +433 ✗: Matthew Stafford 35+ pass att ✗(33) · Kyren Williams 2+ receptions ✓(3) · Michael Wilson 2+ receptions ✓(4) · Trey McBride 50+ rec yds ✓(53) · Tyler Allgeier 20+ rush yds ✓(38) · Puka Nacua 80+ rec yds ✓(80) · Kyren Williams ANYTIME TD ✗(no TD) · Davante Adams ANYTIME TD ✗(no TD)


### BUF@LV — final 33-30
*O/U 53.5 · spread -5.5 · indoor · grass · 16:25 ET*

**Personnel:** BUF: DJ Moore, Palmer Q — singles only; Oliver Q. LV: Thornton (WR), Runyon (TE), Hemingway OUT. Dome.

**Injury report (as built):** BUF OFF · DJ Moore (WR) — Questionable · Shoulder; BUF DEF · Ed Oliver (DE) — Questionable · Knee; BUF OFF · Josh Palmer (WR) — Questionable · Shoulder; BUF DEF · Dee Alford (CB) — Questionable · Ankle; BUF DEF · T.J. Sanders (DE) — Questionable · Shoulder; LV DEF · Tonka Hemingway (DT) — Out · Concussion · DNP; LV OFF · Carter Runyon (TE) — Out · Foot; LV OFF · Dont'e Thornton Jr. (WR) — Out · Hamstring

**Defensive leaks:** BUF D leaks receiving yards to RBs: x1.13 (worsening x1.09 L4); BUF D leaks receptions to RBs: x1.12 (worsening x1.12 L4); BUF D leaks passing interceptions to QBs: x1.10

**Coordinators:** BUF OC Pete Carmichael Jr. — NEW (balanced) · measured pass 48% | DC Jim Leonhard (disguise_zone) · LV OC Andrew Janocko — NEW (run_heavy) · measured pass 57% | DC Rob Leonard (four_man_rush)

**Props SGP** — 4-leg 39.9% · fair +151 **CASHED** · 6-leg 33.2% · fair +201 **CASHED** · 8-leg 23.7% · fair +323 **CASHED**

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Tre Tucker 30+ rec yds | 78% | -351 | ✓ 97 | `4-leg core` · 2026 4/5 pre-game
| 2 | Brock Bowers 40+ rec yds | 77% | -338 | ✓ 70 | `4-leg core` · 2026 3/3 pre-game
| 3 | Josh Allen 20+ pass att | 77% | -339 | ✓ 33 | `4-leg core` · 2026 4/5 pre-game
| 4 | James Cook 15+ carries | 76% | -322 | ✓ 22 | `4-leg core` · 2026 3/5 pre-game
| 5 | Kirk Cousins 25+ pass att | 80% | -411 | ✓ 41 | `+6` · 2026 5/5 pre-game
| 6 | Ashton Jeanty 3+ receptions | 81% | -425 | ✓ 4 | `+6` · 2026 5/5 pre-game
| 7 | Khalil Shakir 3+ receptions | 72% | -262 | ✓ 4 | `+8` · 2026 4/5 pre-game
| 8 | Josh Allen 150+ pass yds | 80% | -389 | ✓ 255 | `+8` · 2026 5/5 pre-game

Legs 8/8 (expected 6.2)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Josh Allen (BUF QB) | 59% | -144 | ✗ no TD | share 18% · team 3.3 TD · RZ-D 1.06 · pos-D 1.41 |
| Ashton Jeanty (LV RB) | 56% | -126 | ✓ TD | share 25% · team 2.69 TD · RZ-D 1.11 · pos-D 1.22 |
| James Cook (BUF RB) | 53% | -111 | ✓ TD | share 22% · team 3.3 TD · RZ-D 1.06 · pos-D 1.04 |
| Brock Bowers (LV TE) | 42% | +138 | ✗ no TD | share 24% · team 2.69 TD · RZ-D 1.11 · pos-D 0.82 |

TD double (Josh Allen + Ashton Jeanty): 35.1% · fair +185 ✗

**All-position slip** — 28.5% · fair +251 ✗: Josh Allen 20+ pass att ✓(33) · James Cook 15+ carries ✓(22) · Tre Tucker 30+ rec yds ✓(97) · Brock Bowers 40+ rec yds ✓(70) · Josh Allen ANYTIME TD ✗(no TD)

**All-position 8-leg** — 15.5% · fair +544 ✗: Josh Allen 20+ pass att ✓(33) · James Cook 15+ carries ✓(22) · Tre Tucker 30+ rec yds ✓(97) · Brock Bowers 40+ rec yds ✓(70) · Ashton Jeanty 3+ receptions ✓(4) · Khalil Shakir 3+ receptions ✓(4) · Josh Allen ANYTIME TD ✗(no TD) · Ashton Jeanty ANYTIME TD ✓(TD)


### LAC@KC — final 6-22
*O/U 41.5 · spread +7.5 · outdoor · grass · 16:25 ET*

**Personnel:** LAC: Tre Harris OUT; Derwin James, D. Jackson, Alt, Awosika OUT; Shelley doubtful; KLS Q. KC: Rashee Rice OUT; Simmons (T) OUT; Sneed Q.

**Injury report (as built):** KC OFF · Rashee Rice (WR) — Out · Hamstring · DNP; KC OFF · Josh Simmons (T) — Out · Back; KC DEF · L'Jarius Sneed (CB) — Questionable · Knee; LAC DEF · Rodney Shelley (CB) — Doubtful · Hamstring · DNP; LAC DEF · Donte Jackson (CB) — Out · Hamstring · DNP; LAC DEF · Derwin James (S) — Out · Hamstring · DNP; LAC OFF · Kayode Awosika (G) — Out · Fibula · DNP; LAC OFF · Joe Alt (T) — Out · Neck · DNP

**Defensive leaks:** KC D leaks receiving yards to TEs: x1.17 (worsening x2.09 L4); KC D leaks receptions to TEs: x1.11 (worsening x1.81 L4); LAC D leaks passing interceptions to QBs: x1.39

**Coordinators:** LAC OC Mike McDaniel — NEW (pass_rb) · measured pass 49% | DC Chris O'Leary (two_high_shell) · KC OC Eric Bieniemy — NEW (pass_wr) · measured pass 52% | DC Steve Spagnuolo (blitz_heavy)

**Props SGP** — 4-leg 43.3% · fair +131 ✗ · 6-leg 29.0% · fair +245 ✗ · 8-leg 17.2% · fair +482 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Omarion Hampton 20+ rush yds | 78% | -364 | ✗ 18 | `4-leg core` · 2026 5/5 pre-game
| 2 | Patrick Mahomes 200+ pass yds | 78% | -347 | ✓ 272 | `4-leg core` · 2026 3/4 pre-game
| 3 | Quentin Johnston 2+ receptions | 80% | -389 | ✗ 1 | `4-leg core` · 2026 2/4 pre-game
| 4 | Travis Kelce 3+ receptions | 80% | -406 | ✓ 4 | `4-leg core` · 2026 2/4 pre-game
| 5 | Ladd McConkey 20+ rec yds | 73% | -273 | ✗ 17 | `+6` · 2026 3/4 pre-game
| 6 | Xavier Worthy 20+ rec yds | 72% | -255 | ✓ 73 | `+6` · 2026 3/4 pre-game
| 7 | Justin Herbert 20+ pass att | 71% | -247 | ✓ 37 | `+8` · 2026 5/5 pre-game
| 8 | Kenneth Walker III 60+ rush yds | 71% | -245 | ✓ 128 | `+8` · 2026 4/4 pre-game

Legs 5/8 (expected 6.0)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Kenneth Walker III (KC RB) | 42% | +137 | ✓ TD | share 21% · team 2.74 TD · RZ-D 0.9 · pos-D 0.96 |
| Omarion Hampton (LAC RB) | 28% | +254 | ✗ no TD | share 21% · team 1.9 TD · RZ-D 0.92 · pos-D 0.9 |
| Xavier Worthy (KC WR) | 24% | +310 | ✗ no TD | share 10% · team 2.74 TD · RZ-D 0.9 · pos-D 0.95 |
| Travis Kelce (KC TE) | 22% | +344 | ✗ no TD | share 9% · team 2.74 TD · RZ-D 0.9 · pos-D 0.91 |

TD double (Kenneth Walker III + Omarion Hampton): 13.8% · fair +624 ✗

**All-position slip** — 22.7% · fair +342 ✗: Patrick Mahomes 200+ pass yds ✓(272) · Omarion Hampton 20+ rush yds ✗(18) · Quentin Johnston 2+ receptions ✗(1) · Travis Kelce 3+ receptions ✓(4) · Kenneth Walker III ANYTIME TD ✓(TD)

**All-position 8-leg** — 6.9% · fair +1347 ✗: Patrick Mahomes 200+ pass yds ✓(272) · Omarion Hampton 20+ rush yds ✗(18) · Quentin Johnston 2+ receptions ✗(1) · Travis Kelce 3+ receptions ✓(4) · Kenneth Walker III 60+ rush yds ✓(128) · Ladd McConkey 20+ rec yds ✗(17) · Kenneth Walker III ANYTIME TD ✓(TD) · Omarion Hampton ANYTIME TD ✗(no TD)


### DAL@GB — final 13-23
*O/U 53.5 · spread +1.5 · outdoor · grass · 20:20 ET*

**Personnel:** DAL: Durant (CB), Shelton (T) OUT; Porter Jr., Overshown Q. GB: Hargrave (DT), St-Juste (CB), Skyy Moore OUT; Banks, Monk Q. Outdoor grass, night.

**Injury report (as built):** DAL DEF · Cobie Durant (CB) — Out · Hamstring · DNP; DAL OFF · Drew Shelton (T) — Out · Hamstring · DNP; DAL DEF · DeMarvion Overshown (LB) — Questionable · Hamstring; DAL DEF · Ameer Speed (CB) — Questionable · Knee; DAL DEF · Joey Porter Jr. (CB) — Questionable · Ankle; DAL DEF · LT Overton (DT) — Questionable · Foot · DNP; DAL DEF · Von Miller (LB) — nan · DNP; GB DEF · Jordon Riley (DE) — Doubtful · Achilles

**Defensive leaks:** GB D leaks receptions to RBs: x1.11; GB D leaks passing interceptions to QBs: x1.10 (worsening x2.60 L4); DAL D leaks receiving yards to RBs: x1.21; DAL D leaks receiving yards to WRs: x1.13 (worsening x1.11 L4)

**Coordinators:** DAL OC Klayton Adams — continuity · measured pass 64% | DC Christian Parker (two_high_shell) · GB OC Adam Stenavich — continuity · measured pass 65% | DC Jonathan Gannon (two_high_shell)

**Props SGP** — 4-leg 45.1% · fair +122 **CASHED** · 6-leg 28.7% · fair +248 ✗ · 8-leg 19.4% · fair +415 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Jordan Love 225+ pass yds | 78% | -351 | ✓ 276 | `4-leg core` · 2026 3/5 pre-game
| 2 | Javonte Williams 2+ receptions | 78% | -361 | ✓ 2 | `4-leg core` · 2026 5/5 pre-game
| 3 | George Pickens 30+ rec yds | 78% | -344 | ✓ 73 | `4-leg core` · 2026 4/5 pre-game
| 4 | Matthew Golden 30+ rec yds | 77% | -341 | ✓ 104 | `4-leg core` · 2026 4/5 pre-game
| 5 | MarShawn Lloyd 20+ rush yds | 75% | -306 | ✗ 10 | `+6` · 2026 3/5 pre-game
| 6 | CeeDee Lamb 6+ receptions | 75% | -295 | ✓ 9 | `+6` · 2026 3/5 pre-game
| 7 | Dak Prescott 175+ pass yds | 74% | -277 | ✓ 258 | `+8` · 2026 5/5 pre-game
| 8 | Javonte Williams 30+ rush yds | 78% | -346 | ✓ 41 | `+8` · 2026 5/5 pre-game

Legs 7/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Javonte Williams (DAL RB) | 51% | -105 | ✓ TD | share 23% · team 2.91 TD · RZ-D 1.05 · pos-D 1.03 |
| Christian Watson (GB WR) | 49% | +104 | ✗ no TD | share 17% · team 3.08 TD · RZ-D 1.1 · pos-D 1.22 |
| George Pickens (DAL WR) | 39% | +157 | ✗ no TD | share 16% · team 2.91 TD · RZ-D 1.05 · pos-D 1.02 |
| MarShawn Lloyd (GB RB) | 38% | +162 | ✗ no TD | share 13% · team 3.08 TD · RZ-D 1.1 · pos-D 1.1 |

TD double (Javonte Williams + Christian Watson): 27.2% · fair +267 ✗

**All-position slip** — 28.8% · fair +248 **CASHED**: Jordan Love 225+ pass yds ✓(276) · Javonte Williams 2+ receptions ✓(2) · George Pickens 30+ rec yds ✓(73) · Tucker Kraft 3+ receptions ✓(5) · Javonte Williams ANYTIME TD ✓(TD)

**All-position 8-leg** — 13.5% · fair +641 ✗: Jordan Love 225+ pass yds ✓(276) · Javonte Williams 2+ receptions ✓(2) · George Pickens 30+ rec yds ✓(73) · Tucker Kraft 3+ receptions ✓(5) · MarShawn Lloyd 20+ rush yds ✗(10) · Matthew Golden 30+ rec yds ✓(104) · Javonte Williams ANYTIME TD ✓(TD) · Christian Watson ANYTIME TD ✗(no TD)


### Cross-game combos — Week 6 — Sunday Oct 18 2026 (shipped floor, v1.9e)

**4-leg** — 37.4% · fair +167 — 2/4 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | PIT@TB | Emeka Egbuka 2+ receptions | 78% | ✓ 7 |
| 2 | CAR@PHI | Chuba Hubbard 2+ receptions | 78% | ✗ 1 |
| 3 | NYJ@NE | Drake Maye 20+ pass att | 78% | ✓ 32 |
| 4 | ARI@LA | Matthew Stafford 35+ pass att | 78% | ✗ 33 |

**6-leg** — 22.8% · fair +339 — 4/6 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | PIT@TB | Emeka Egbuka 2+ receptions | 78% | ✓ 7 |
| 2 | CAR@PHI | Chuba Hubbard 2+ receptions | 78% | ✗ 1 |
| 3 | NYJ@NE | Drake Maye 20+ pass att | 78% | ✓ 32 |
| 4 | ARI@LA | Matthew Stafford 35+ pass att | 78% | ✗ 33 |
| 5 | BUF@LV | Tre Tucker 30+ rec yds | 78% | ✓ 97 |
| 6 | DAL@GB | Jordan Love 225+ pass yds | 78% | ✓ 276 |

**8-leg** — 14.0% · fair +613 — 5/8 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | PIT@TB | Emeka Egbuka 2+ receptions | 78% | ✓ 7 |
| 2 | CAR@PHI | Chuba Hubbard 2+ receptions | 78% | ✗ 1 |
| 3 | NYJ@NE | Drake Maye 20+ pass att | 78% | ✓ 32 |
| 4 | ARI@LA | Matthew Stafford 35+ pass att | 78% | ✗ 33 |
| 5 | BUF@LV | Tre Tucker 30+ rec yds | 78% | ✓ 97 |
| 6 | DAL@GB | Jordan Love 225+ pass yds | 78% | ✓ 276 |
| 7 | LAC@KC | Omarion Hampton 20+ rush yds | 78% | ✗ 18 |
| 8 | LAC@KC | Patrick Mahomes 200+ pass yds | 78% | ✓ 272 |

**10-leg** — 8.8% · fair +1041 — 7/10 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | PIT@TB | Emeka Egbuka 2+ receptions | 78% | ✓ 7 |
| 2 | CAR@PHI | Chuba Hubbard 2+ receptions | 78% | ✗ 1 |
| 3 | NYJ@NE | Drake Maye 20+ pass att | 78% | ✓ 32 |
| 4 | ARI@LA | Matthew Stafford 35+ pass att | 78% | ✗ 33 |
| 5 | BUF@LV | Tre Tucker 30+ rec yds | 78% | ✓ 97 |
| 6 | DAL@GB | Jordan Love 225+ pass yds | 78% | ✓ 276 |
| 7 | DAL@GB | Javonte Williams 2+ receptions | 78% | ✓ 2 |
| 8 | LAC@KC | Omarion Hampton 20+ rush yds | 78% | ✗ 18 |
| 9 | LAC@KC | Patrick Mahomes 200+ pass yds | 78% | ✓ 272 |
| 10 | TEN@IND | Josh Downs 30+ rec yds | 78% | ✓ 40 |

**12-leg** — 5.3% · fair +1770 — 9/12 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | PIT@TB | Emeka Egbuka 2+ receptions | 78% | ✓ 7 |
| 2 | CAR@PHI | Chuba Hubbard 2+ receptions | 78% | ✗ 1 |
| 3 | NYJ@NE | Drake Maye 20+ pass att | 78% | ✓ 32 |
| 4 | ARI@LA | Matthew Stafford 35+ pass att | 78% | ✗ 33 |
| 5 | BUF@LV | Tre Tucker 30+ rec yds | 78% | ✓ 97 |
| 6 | DAL@GB | Jordan Love 225+ pass yds | 78% | ✓ 276 |
| 7 | DAL@GB | Javonte Williams 2+ receptions | 78% | ✓ 2 |
| 8 | LAC@KC | Omarion Hampton 20+ rush yds | 78% | ✗ 18 |
| 9 | LAC@KC | Patrick Mahomes 200+ pass yds | 78% | ✓ 272 |
| 10 | TEN@IND | Josh Downs 3+ receptions | 78% | ✓ 4 |
| 11 | TEN@IND | Tony Pollard 40+ rush yds | 78% | ✓ 76 |
| 12 | NO@NYG | Tyler Shough 25+ pass att | 78% | ✓ 30 |


### ATD board (top 16) — Week 6 — Sunday Oct 18 2026 (shipped floor, v1.9e)

| # | Game | Player | Model | Fair | Result |
|---|---|---|---|---|---|
| 1 | ARI@LA | Kyren Williams (RB) | 70% | -229 | ✗ no TD |
| 2 | ARI@LA | Davante Adams (WR) | 66% | -199 | ✗ no TD |
| 3 | TEN@IND | Jonathan Taylor (RB) | 59% | -144 | ✓ TD |
| 4 | BUF@LV | Josh Allen (QB) | 59% | -144 | ✗ no TD |
| 5 | BUF@LV | Ashton Jeanty (RB) | 56% | -126 | ✓ TD |
| 6 | NYJ@NE | Rhamondre Stevenson (RB) | 54% | -117 | ✗ no TD |
| 7 | BUF@LV | James Cook (RB) | 53% | -111 | ✓ TD |
| 8 | DAL@GB | Javonte Williams (RB) | 51% | -105 | ✓ TD |
| 9 | BAL@CLE | Derrick Henry (RB) | 50% | -102 | ✗ no TD |
| 10 | CHI@ATL | Bijan Robinson (RB) | 50% | +102 | ✗ no TD |
| 11 | DAL@GB | Christian Watson (WR) | 49% | +104 | ✗ no TD |
| 12 | CHI@ATL | D'Andre Swift (RB) | 48% | +107 | ✓ TD |
| 13 | NO@NYG | Malik Nabers (WR) | 44% | +125 | ✗ no TD |
| 14 | ARI@LA | Puka Nacua (WR) | 44% | +127 | ✗ no TD |
| 15 | CHI@ATL | Drake London (WR) | 44% | +130 | ✗ no TD |
| 16 | LAC@KC | Kenneth Walker III (RB) | 42% | +137 | ✓ TD |

Board: top-16 6/16 · top-8 4/8 · chalk triple 1/3

**2+ TD board (singles only):** Kyren Williams 33% (+200) · Davante Adams 30% (+235) · Jonathan Taylor 22% (+346) · Josh Allen 22% (+347) · Ashton Jeanty 20% (+406) · Rhamondre Stevenson 18% (+448)


### Scorecard — Week 6 — Sunday Oct 18 2026 (shipped floor, v1.9e)

**Legs 61/84 = 73% actual vs 77% expected · SGP4 2/11 · SGP6 1/11 · SGP8 1/11**

| Game | Final | Legs | SGP4 | SGP6 | SGP8 |
|---|---|---|---|---|---|
| BUF@LV | 33-30 | 8/8 | ✓ | ✓ | ✓ |
| PIT@TB | 26-19 | 7/8 | ✗ | ✗ | ✗ |
| DAL@GB | 13-23 | 7/8 | ✓ | ✗ | ✗ |
| NYJ@NE | 19-26 | 6/8 | ✗ | ✗ | ✗ |
| TEN@IND | 26-20 | 6/8 | ✗ | ✗ | ✗ |
| ARI@LA | 18-16 | 6/8 | ✗ | ✗ | ✗ |
| CAR@PHI | 25-14 | 5/7 | ✗ | ✗ | ✗ |
| LAC@KC | 6-22 | 5/8 | ✗ | ✗ | ✗ |
| CHI@ATL | 31-23 | 4/7 | ✗ | ✗ | ✗ |
| NO@NYG | 34-27 | 4/7 | ✗ | ✗ | ✗ |
| BAL@CLE | 10-13 | 3/7 | ✗ | ✗ | ✗ |


## Week 6 — v1.9f build (made pre-kick the same morning; not shipped)

*Engine v1.9f.* **The out-of-sample test of the calibration layer.** Same games, same inputs, built before kickoff after the Week 5 report card: same players one rung lower, no thin TE yardage legs. 86% vs 76%, SGP4 6/11, SGP6 6/11, 4-leg cross-combo cashed. This is why v1.9f became the production engine from Week 8.


### BAL@CLE — final 10-13
*O/U 39.5 · spread -3.0 · outdoor · grass · 13:00 ET*

**Personnel:** BAL: Lamar OUT — Huntley 2nd start; Jurgens, Hibner OUT. CLE: Watson starts (Gabriel IR); Sampson OUT; Judkins Q — singles only.

**Injury report (as built):** BAL OFF · Lamar Jackson (QB) — Out · Ankle · DNP; BAL DEF · Broderick Washington (DE) — Out · Ankle · DNP; BAL OFF · Cam Jurgens (C) — Out · Concussion; BAL OFF · Matthew Hibner (TE) — Out · Hand · DNP; BAL OFF · Andrew Vorhees (G) — Questionable · Foot; BAL OFF · Emery Jones Jr. (G) — Questionable · Ankle; BAL OFF · Ja'Kobi Lane (WR) — Questionable · Wrist; BAL DEF · Calais Campbell (DT) — nan · DNP

**Defensive leaks:** BAL D leaks receiving yards to RBs: x1.20; BAL D leaks receptions to RBs: x1.18; BAL D leaks receiving yards to WRs: x1.17 (worsening x1.23 L4)

**Coordinators:** BAL OC Declan Doyle — NEW (pass_wr) · measured pass 46% | DC Anthony Weaver (pressure) · CLE OC Travis Switzer — NEW (run_heavy) · measured pass 54% | DC Mike Rutenberg (multiple)

**Props SGP** — 4-leg 46.6% · fair +115 ✗ · 6-leg 31.4% · fair +218 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Zay Flowers 3+ receptions | 78% | -351 | ✓ 6 | `4-leg core` · 2026 4/4 pre-game
| 2 | Deshaun Watson 25+ pass att | 80% | -390 | ✓ 26 | `4-leg core` · 2026 4/5 pre-game
| 3 | Harold Fannin Jr. 2+ receptions | 80% | -409 | ✗ 1 | `4-leg core` · 2026 4/5 pre-game
| 4 | Denzel Boston 30+ rec yds | 74% | -287 | ✗ 15 | `4-leg core` · 2026 5/5 pre-game
| 5 | Derrick Henry 15+ carries | 82% | -461 | ✓ 17 | `+6` · 2026 5/5 pre-game
| 6 | Zay Flowers 30+ rec yds | 74% | -285 | ✓ 66 | `+6` · 2026 4/4 pre-game
| 7 | Deshaun Watson 150+ pass yds | 70% | -236 | ✓ 164 | `+8` · 2026 4/5 pre-game

Legs 5/7 (expected 5.4)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Derrick Henry (BAL RB) | 50% | -102 | ✗ no TD | share 30% · team 2.38 TD · RZ-D 0.99 · pos-D 0.91 |
| Denzel Boston (CLE WR) | 28% | +257 | ✗ no TD | share 17% · team 2.04 TD · RZ-D 0.89 · pos-D 0.98 |
| Mark Andrews (BAL TE) | 24% | +308 | ✗ no TD | share 15% · team 2.38 TD · RZ-D 0.99 · pos-D 0.9 |
| Harold Fannin Jr. (CLE TE) | 21% | +376 | ✗ no TD | share 14% · team 2.04 TD · RZ-D 0.89 · pos-D 0.85 |

TD double (Derrick Henry + Denzel Boston): 16.1% · fair +521 ✗

**All-position slip** — 28.1% · fair +255 ✗: Deshaun Watson 25+ pass att ✓(26) · Derrick Henry 15+ carries ✓(17) · Zay Flowers 3+ receptions ✓(6) · Harold Fannin Jr. 2+ receptions ✗(1) · Derrick Henry ANYTIME TD ✗(no TD)

**All-position 8-leg** — 9.9% · fair +906 ✗: Deshaun Watson 25+ pass att ✓(26) · Derrick Henry 15+ carries ✓(17) · Zay Flowers 3+ receptions ✓(6) · Harold Fannin Jr. 2+ receptions ✗(1) · Denzel Boston 30+ rec yds ✗(15) · Derrick Henry ANYTIME TD ✗(no TD) · Denzel Boston ANYTIME TD ✗(no TD)


### CAR@PHI — final 25-14
*O/U 39.5 · spread -3.0 · outdoor · grass · 13:00 ET*

**Personnel:** PHI: Hurts OUT (calf clot) — Tanner McKee starts. Barkley, Shipley OUT, Bigsby IR — Dameon Pierce backfield. Dickerson (G), Calcaterra (TE), Carter II (S), Bennett (CB) OUT. CAR: Dillon OUT, Freeling doubtful; Etienne, Moton Q.

**Injury report (as built):** CAR OFF · Monroe Freeling (T) — Doubtful · Knee; CAR OFF · AJ Dillon (RB) — Out · Ankle · DNP; CAR OFF · Taylor Moton (T) — Questionable · Lung; CAR DEF · Tershawn Wharton (DT) — Questionable · Neck; CAR OFF · Damien Lewis (G) — Questionable · Elbow; CAR DEF · Jaelan Phillips (LB) — Questionable · Hamstring; CAR OFF · Trevor Etienne (RB) — Questionable · Ankle; PHI DEF · A.J. Epenesa (LB) — Doubtful · Back · DNP

**Defensive leaks:** CAR D leaks rushing yards to RBs: x1.34; CAR D leaks carries to RBs: x1.17; CAR D leaks receiving yards to TEs: x1.08 (worsening x1.26 L4)

**Coordinators:** CAR OC Brad Idzik — continuity · measured pass 63% | DC Ejiro Evero (two_high_shell) · PHI OC Sean Mannion — NEW (run_heavy) · measured pass 56% | DC Vic Fangio (two_high_shell)

**Props SGP** — 4-leg 38.3% · fair +161 ✗ · 6-leg 28.3% · fair +254 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Chuba Hubbard 10+ carries | 78% | -365 | ✓ 28 | `4-leg core` · 2026 4/4 pre-game
| 2 | Darren Waller 2+ receptions | 77% | -333 | ✗ 0 | `4-leg core` · 2026 4/4 pre-game
| 3 | Jalen Coker 2+ receptions | 76% | -326 | ✓ 6 | `4-leg core` · 2026 3/3 pre-game
| 4 | Bryce Young 30+ pass att | 74% | -286 | ✓ 39 | `4-leg core` · 2026 4/4 pre-game
| 5 | Tetairoa McMillan 30+ rec yds | 73% | -273 | ✓ 86 | `+6` · 2026 3/4 pre-game
| 6 | Bryce Young 175+ pass yds | 73% | -275 | ✓ 281 | `+6` · 2026 4/4 pre-game
| 7 | Jalen Coker 20+ rec yds | 71% | -242 | ✓ 97 | `+8` · 2026 2/3 pre-game

Legs 6/7 (expected 5.2)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Chuba Hubbard (CAR RB) | 38% | +160 | ✓ TD | share 19% · team 2.38 TD · RZ-D 0.94 · pos-D 1.01 |
| Dallas Goedert (PHI TE) | 29% | +246 | ✗ no TD | share 14% · team 2.04 TD · RZ-D 0.98 · pos-D 1.08 |
| Tetairoa McMillan (CAR WR) | 27% | +266 | ✗ no TD | share 16% · team 2.38 TD · RZ-D 0.94 · pos-D 0.88 |
| DeVonta Smith (PHI WR) | 25% | +294 | ✓ TD | share 16% · team 2.04 TD · RZ-D 0.98 · pos-D 0.85 |

TD double (Chuba Hubbard + Dallas Goedert): 13.0% · fair +670 ✗

**All-position slip** — 21.5% · fair +366 ✗: Bryce Young 30+ pass att ✓(39) · Chuba Hubbard 10+ carries ✓(28) · Jalen Coker 2+ receptions ✓(6) · Darren Waller 2+ receptions ✗(0) · Chuba Hubbard ANYTIME TD ✓(TD)

**All-position 8-leg** — 7.7% · fair +1196 ✗: Bryce Young 30+ pass att ✓(39) · Chuba Hubbard 10+ carries ✓(28) · Jalen Coker 2+ receptions ✓(6) · Darren Waller 2+ receptions ✗(0) · Tetairoa McMillan 30+ rec yds ✓(86) · Chuba Hubbard ANYTIME TD ✓(TD) · Dallas Goedert ANYTIME TD ✗(no TD)


### CHI@ATL — final 31-23
*O/U 51.5 · spread -1.5 · indoor · turf · 13:00 ET*

**Personnel:** CHI: Caleb Williams ACTIVE (hamstring) per club; Monangai OUT — Swift; T.J. Edwards, Odeyingbo OUT; Gordon, Stevenson Q. ATL: C.J. Henderson OUT; Z. Smith Q.

**Injury report (as built):** ATL DEF · C.J. Henderson (CB) — Out · Groin · DNP; ATL DEF · Za'Darius Smith (DE) — Questionable · Neck; CHI DEF · T.J. Edwards (LB) — Out · Hamstring · DNP; CHI DEF · Dayo Odeyingbo (DE) — Out · Quadricep · DNP; CHI OFF · Kyle Monangai (RB) — Out · Thumb · DNP; CHI DEF · Keyshaun Elliott (LB) — Out · Quadricep · DNP; CHI DEF · Kyler Gordon (CB) — Questionable · Calf; CHI DEF · Tyrique Stevenson (CB) — Questionable · Hip

**Defensive leaks:** ATL D leaks receptions to RBs: x1.14 (worsening x1.11 L4); ATL D leaks receptions to WRs: x1.10 (worsening x1.27 L4); CHI D leaks passing interceptions to QBs: x1.35; CHI D leaks rushing yards to RBs: x1.15

**Coordinators:** CHI OC Press Taylor — NEW (pass_wr) · measured pass 48% | DC Dennis Allen (blitz_man) · ATL OC Tommy Rees — NEW (run_heavy) · measured pass 45% | DC Jeff Ulbrich (blitz_heavy)

**Props SGP** — 4-leg 36.2% · fair +176 **CASHED** · 6-leg 23.2% · fair +330 **CASHED** · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Rome Odunze 2+ receptions | 78% | -351 | ✓ 3 | `4-leg core` · 2026 5/5 pre-game
| 2 | Colston Loveland 1+ receptions | 78% | -361 | ✓ 6 | `4-leg core` · 2026 4/5 pre-game
| 3 | D'Andre Swift 15+ carries | 74% | -292 | ✓ 16 | `4-leg core` · 2026 4/5 pre-game
| 4 | Bijan Robinson 60+ rush yds | 74% | -283 | ✓ 61 | `4-leg core` · 2026 5/5 pre-game
| 5 | Luther Burden III 20+ rec yds | 74% | -282 | ✓ 95 | `+6` · 2026 5/5 pre-game
| 6 | Drake London 50+ rec yds | 74% | -278 | ✓ 62 | `+6` · 2026 4/5 pre-game
| 7 | Michael Penix Jr. 175+ pass yds | 73% | -273 | ✓ 225 | `+8` · 2026 3/3 pre-game

Legs 7/7 (expected 5.3)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Bijan Robinson (ATL RB) | 50% | +102 | ✗ no TD | share 28% · team 2.8 TD · RZ-D 0.97 · pos-D 0.94 |
| D'Andre Swift (CHI RB) | 48% | +107 | ✓ TD | share 19% · team 2.97 TD · RZ-D 0.93 · pos-D 0.94 |
| Drake London (ATL WR) | 44% | +130 | ✗ no TD | share 18% · team 2.8 TD · RZ-D 0.97 · pos-D 1.18 |
| Rome Odunze (CHI WR) | 41% | +144 | ✗ no TD | share 14% · team 2.97 TD · RZ-D 0.93 · pos-D 1.11 |

TD double (Bijan Robinson + D'Andre Swift): 26.1% · fair +283 ✗

**All-position slip** — 21.7% · fair +361 ✗: Michael Penix Jr. 175+ pass yds ✓(225) · D'Andre Swift 15+ carries ✓(16) · Rome Odunze 2+ receptions ✓(3) · Colston Loveland 1+ receptions ✓(6) · Bijan Robinson ANYTIME TD ✗(no TD)

**All-position 8-leg** — 10.9% · fair +813 ✗: Michael Penix Jr. 175+ pass yds ✓(225) · D'Andre Swift 15+ carries ✓(16) · Rome Odunze 2+ receptions ✓(3) · Colston Loveland 1+ receptions ✓(6) · Bijan Robinson 60+ rush yds ✓(61) · Luther Burden III 20+ rec yds ✓(95) · Bijan Robinson ANYTIME TD ✗(no TD) · D'Andre Swift ANYTIME TD ✓(TD)


### NO@NYG — final 34-27
*O/U 46.5 · spread -1.5 · outdoor · turf · 13:00 ET*

**Personnel:** NYG: Theo Johnson (TE), Nubin (S), Hood (CB) OUT; A. Thomas, Eluemunor Q. NO: Elliss, Jennings (LBs) OUT; Kamara, Olave Q — singles only.

**Injury report (as built):** NO DEF · Kaden Elliss (LB) — Out · Calf · DNP; NO DEF · Anfernee Jennings (LB) — Out · Knee · DNP; NO OFF · Zach Wood (LS) — Questionable · Calf; NO OFF · Alvin Kamara (RB) — Questionable · Back; NO DEF · Nathan Shepherd (DT) — Questionable · Illness; NO OFF · Chris Olave (WR) — Questionable · Illness; NO DEF · Lorenzo Styles Jr. (CB) — Questionable · Knee; NYG OFF · Theo Johnson (TE) — Out · Neck · DNP

**Defensive leaks:** NYG D leaks rushing yards to RBs: x1.19; NO D leaks rushing yards to RBs: x1.17 (worsening x1.30 L4); NO D leaks carries to RBs: x1.12 (worsening x1.12 L4)

**Coordinators:** NO OC Doug Nussmeier — continuity · measured pass 64% | DC Brandon Staley (two_high_shell) · NYG OC Matt Nagy — NEW (pass_wr) · measured pass 53% | DC Dennard Wilson (pressure)

**Props SGP** — 4-leg 41.4% · fair +141 ✗ · 6-leg 28.1% · fair +255 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Cam Skattebo 10+ carries | 78% | -362 | – DNP | `4-leg core` · 2026 5/5 pre-game
| 2 | Juwan Johnson 30+ rec yds | 77% | -327 | ✗ 0 | `4-leg core` · 2026 4/5 pre-game
| 3 | Malik Nabers 4+ receptions | 75% | -306 | ✓ 12 | `4-leg core` · 2026 4/5 pre-game
| 4 | Tyler Shough 25+ pass att | 83% | -487 | ✓ 30 | `4-leg core` · 2026 5/5 pre-game
| 5 | Devaughn Vele 4+ receptions | 72% | -262 | ✗ 3 | `+6` · 2026 4/5 pre-game
| 6 | Malik Nabers 20+ rec yds | 73% | -275 | ✓ 165 | `+6` · 2026 4/5 pre-game
| 7 | Tyler Shough 250+ pass yds | 70% | -238 | ✗ 144 | `+8` · 2026 4/5 pre-game

Legs 3/6 (expected 5.3)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Malik Nabers (NYG WR) | 44% | +125 | ✗ no TD | share 21% · team 2.52 TD · RZ-D 0.96 · pos-D 1.06 |
| Cam Skattebo (NYG RB) | 40% | +151 | – DNP | share 17% · team 2.52 TD · RZ-D 0.96 · pos-D 1.12 |
| Tyler Shough (NO QB) | 30% | +232 | ✓ TD | share 11% · team 2.69 TD · RZ-D 1.06 · pos-D 1.2 |
| Devaughn Vele (NO WR) | 29% | +240 | ✗ no TD | share 12% · team 2.69 TD · RZ-D 1.06 · pos-D 1.04 |

TD double (Malik Nabers + Cam Skattebo): 22.2% · fair +351 ✗

**All-position slip** — 23.7% · fair +323 ✗: Tyler Shough 25+ pass att ✓(30) · Cam Skattebo 10+ carries –(DNP) · Malik Nabers 4+ receptions ✓(12) · Juwan Johnson 30+ rec yds ✗(0) · Malik Nabers ANYTIME TD ✗(no TD)

**All-position 8-leg** — 12.0% · fair +731 ✗: Tyler Shough 25+ pass att ✓(30) · Cam Skattebo 10+ carries –(DNP) · Malik Nabers 4+ receptions ✓(12) · Juwan Johnson 30+ rec yds ✗(0) · Devaughn Vele 4+ receptions ✗(3) · Malik Nabers ANYTIME TD ✗(no TD) · Cam Skattebo ANYTIME TD –(DNP)


### NYJ@NE — final 19-26
*O/U 43.5 · spread +7.5 · outdoor · turf · 13:00 ET*

**Personnel:** NYJ: Breece Hall OUT — Braelon Allen backfield; A. Mitchell OUT. NE: Carlton Davis III + Prunty (CBs) OUT; A.J. Brown activated off IR (no 2026 sample — not in pool); Henderson Q.

**Injury report (as built):** NE DEF · Carlton Davis III (CB) — Out · Neck · DNP; NE DEF · Karon Prunty (CB) — Out · Hamstring · DNP; NE OFF · A.J. Brown (WR) — Questionable · Ankle; NE DEF · Christian Elliss (LB) — Questionable · Chest; NE OFF · Marcus Bryant (T) — Questionable · Ankle; NE OFF · Will Campbell (T) — Questionable · Knee; NE DEF · Craig Woodson (S) — Questionable · Shoulder; NE OFF · TreVeyon Henderson (RB) — Questionable · Ankle

**Defensive leaks:** NYJ D leaks carries to RBs: x1.13 (worsening x1.25 L4); NYJ D leaks rushing yards to RBs: x1.10 (worsening x1.29 L4)

**Coordinators:** NYJ OC Frank Reich — NEW (balanced) · measured pass 53% | DC Brian Duker (multiple) · NE OC Josh McDaniels — continuity · measured pass 51% | DC Zak Kuhr (multiple)

**Props SGP** — 4-leg 34.0% · fair +194 **CASHED** · 6-leg 26.2% · fair +282 **CASHED** · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Geno Smith 175+ pass yds | 77% | -335 | ✓ 252 | `4-leg core` · 2026 4/5 pre-game
| 2 | Garrett Wilson 4+ receptions | 75% | -305 | ✓ 4 | `4-leg core` · 2026 4/5 pre-game
| 3 | Drake Maye 175+ pass yds | 73% | -274 | ✓ 235 | `4-leg core` · 2026 5/5 pre-game
| 4 | Rhamondre Stevenson 30+ rush yds | 70% | -235 | ✓ 36 | `4-leg core` · 2026 4/5 pre-game
| 5 | Garrett Wilson 40+ rec yds | 74% | -280 | ✓ 44 | `+6` · 2026 4/5 pre-game
| 6 | Drake Maye 20+ pass att | 84% | -513 | ✓ 32 | `+6` · 2026 5/5 pre-game
| 7 | Geno Smith 20+ pass att | 85% | -573 | ✓ 30 | `+8` · 2026 4/5 pre-game

Legs 7/7 (expected 5.4)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Rhamondre Stevenson (NE RB) | 54% | -117 | ✗ no TD | share 18% · team 2.86 TD · RZ-D 1.09 · pos-D 1.38 |
| Romeo Doubs (NE WR) | 37% | +171 | ✓ TD | share 15% · team 2.86 TD · RZ-D 1.09 · pos-D 1.01 |
| Garrett Wilson (NYJ WR) | 30% | +238 | ✗ no TD | share 13% · team 2.02 TD · RZ-D 1.04 · pos-D 1.05 |
| Braelon Allen (NYJ RB) | 25% | +297 | ✗ no TD | share 11% · team 2.02 TD · RZ-D 1.04 · pos-D 0.92 |

TD double (Rhamondre Stevenson + Romeo Doubs): 24.4% · fair +310 ✗

**All-position slip** — 29.3% · fair +242 ✗: Geno Smith 175+ pass yds ✓(252) · Rhamondre Stevenson 30+ rush yds ✓(36) · Garrett Wilson 4+ receptions ✓(4) · Rhamondre Stevenson ANYTIME TD ✗(no TD)

**All-position 8-leg** — 13.1% · fair +662 ✗: Geno Smith 175+ pass yds ✓(252) · Rhamondre Stevenson 30+ rush yds ✓(36) · Garrett Wilson 4+ receptions ✓(4) · Drake Maye 175+ pass yds ✓(235) · Rhamondre Stevenson ANYTIME TD ✗(no TD) · Romeo Doubs ANYTIME TD ✓(TD)


### PIT@TB — final 26-19
*O/U 38.5 · spread -1.5 · outdoor · grass · 13:00 ET*

**Personnel:** TB: Mayfield OUT — Jalon Daniels 3rd start. Winfield Jr. (S) OUT, Morrison (CB) doubtful. PIT: DeShon Elliott (S), Roman Wilson, Skowronek OUT; Ramsey, Dean, Dowdle, Freiermuth Q (singles only).

**Injury report (as built):** PIT DEF · DeShon Elliott (S) — Out · Knee; PIT OFF · Ben Skowronek (WR) — Out · Calf · DNP; PIT OFF · Roman Wilson (WR) — Out · Finger · DNP; PIT DEF · Jalen Ramsey (CB) — Questionable · Wrist; PIT DEF · Jamel Dean (CB) — Questionable · Ankle; PIT OFF · Rico Dowdle (RB) — Questionable · Toe; PIT OFF · Pat Freiermuth (TE) — Questionable · Calf; PIT DEF · Keeanu Benton (DT) — Questionable · Ankle

**Defensive leaks:** TB D leaks receiving yards to RBs: x1.38; TB D leaks receiving yards to TEs: x1.18; TB D leaks receptions to RBs: x1.15; PIT D leaks passing interceptions to QBs: x1.32

**Coordinators:** PIT OC Brian Angelichio — NEW (pass_te) · measured pass 63% | DC Patrick Graham (multiple) · TB OC Zac Robinson — NEW (pass_wr) · measured pass 53% | DC Todd Bowles (blitz_heavy)

**Props SGP** — 4-leg 33.0% · fair +203 **CASHED** · 6-leg 21.1% · fair +375 **CASHED** · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Germie Bernard 1+ receptions | 78% | -364 | ✓ 11 | `4-leg core` · 2026 4/4 pre-game
| 2 | Ted Hurst III 1+ receptions | 75% | -305 | ✓ 3 | `4-leg core` · 2026 4/4 pre-game
| 3 | Jaylen Warren 20+ rush yds | 74% | -283 | ✓ 50 | `4-leg core` · 2026 5/5 pre-game
| 4 | Bucky Irving 30+ rush yds | 73% | -269 | ✓ 46 | `4-leg core` · 2026 5/5 pre-game
| 5 | Aaron Rodgers 225+ pass yds | 71% | -242 | ✓ 253 | `+6` · 2026 3/5 pre-game
| 6 | DK Metcalf 20+ rec yds | 70% | -237 | ✓ 93 | `+6` · 2026 4/5 pre-game
| 7 | Aaron Rodgers 30+ pass att | 85% | -584 | ✓ 49 | `+8` · 2026 5/5 pre-game

Legs 7/7 (expected 5.3)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Jaylen Warren (PIT RB) | 28% | +251 | ✗ no TD | share 15% · team 2.24 TD · RZ-D 1.04 · pos-D 0.94 |
| Bucky Irving (TB RB) | 27% | +275 | ✗ no TD | share 18% · team 2.07 TD · RZ-D 0.93 · pos-D 0.85 |
| DK Metcalf (PIT WR) | 26% | +279 | ✗ no TD | share 14% · team 2.24 TD · RZ-D 1.04 · pos-D 0.97 |
| Emeka Egbuka (TB WR) | 25% | +303 | ✓ TD | share 16% · team 2.07 TD · RZ-D 0.93 · pos-D 0.99 |

TD double (Jaylen Warren + Bucky Irving): 9.3% · fair +980 ✗

**All-position slip** — 14.0% · fair +615 ✗: Aaron Rodgers 225+ pass yds ✓(253) · Jaylen Warren 20+ rush yds ✓(50) · Germie Bernard 1+ receptions ✓(11) · Cade Otton 3+ receptions ✗(1) · Jaylen Warren ANYTIME TD ✗(no TD)

**All-position 8-leg** — 4.4% · fair +2194 ✗: Aaron Rodgers 225+ pass yds ✓(253) · Jaylen Warren 20+ rush yds ✓(50) · Germie Bernard 1+ receptions ✓(11) · Cade Otton 3+ receptions ✗(1) · Bucky Irving 30+ rush yds ✓(46) · DK Metcalf 20+ rec yds ✓(93) · Jaylen Warren ANYTIME TD ✗(no TD) · Bucky Irving ANYTIME TD ✗(no TD)


### TEN@IND — final 26-20
*O/U 43.5 · spread +6.5 · indoor · turf · 13:00 ET*

**Personnel:** TEN: Winston Jr. (S) OUT; Spears Q. IND: Dulin OUT; Tyler Warren Q — singles only.

**Injury report (as built):** IND OFF · Ashton Dulin (WR) — Out · Hamstring · DNP; IND DEF · Jaylon Carlies (LB) — Out · Ribs · DNP; IND OFF · Tyler Warren (TE) — Questionable · Groin; IND DEF · DeForest Buckner (DT) — nan · DNP; TEN DEF · Jordan Elliott (DT) — Out · Not injury related - personal matter · DNP; TEN DEF · Kevin Winston Jr. (S) — Out · Quadricep · DNP; TEN DEF · Joshua Williams (CB) — Questionable · Pectoral; TEN OFF · Tyjae Spears (RB) — Questionable · Knee

**Defensive leaks:** IND D leaks receiving yards to TEs: x1.19; IND D leaks receptions to TEs: x1.14; IND D leaks passing interceptions to QBs: x1.14

**Coordinators:** TEN OC Brian Daboll — NEW (pass_wr) · measured pass 59% | DC Gus Bradley (zone_cover3) · IND OC Jim Bob Cooter — continuity · measured pass 56% | DC Lou Anarumo (disguise_zone)

**Props SGP** — 4-leg 45.7% · fair +119 ✗ · 6-leg 30.7% · fair +226 ✗ · 8-leg 18.8% · fair +431 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Cam Ward 30+ pass att | 78% | -346 | ✗ 22 | `4-leg core` · 2026 4/5 pre-game
| 2 | Josh Downs 20+ rec yds | 79% | -374 | ✓ 40 | `4-leg core` · 2026 4/5 pre-game
| 3 | Keenan Allen 20+ rec yds | 77% | -338 | ✓ 82 | `4-leg core` · 2026 3/4 pre-game
| 4 | Daniel Jones 175+ pass yds | 76% | -314 | ✓ 269 | `4-leg core` · 2026 3/5 pre-game
| 5 | Tony Pollard 10+ carries | 82% | -444 | ✓ 19 | `+6` · 2026 4/5 pre-game
| 6 | Wan'Dale Robinson 5+ receptions | 74% | -288 | ✗ 3 | `+6` · 2026 3/5 pre-game
| 7 | Carnell Tate 2+ receptions | 74% | -286 | ✓ 6 | `+8` · 2026 4/5 pre-game
| 8 | Jonathan Taylor 15+ carries | 71% | -249 | ✓ 21 | `+8` · 2026 5/5 pre-game

Legs 6/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Jonathan Taylor (IND RB) | 59% | -144 | ✓ TD | share 29% · team 2.8 TD · RZ-D 1.12 · pos-D 1.07 |
| Keenan Allen (IND WR) | 35% | +187 | ✗ no TD | share 13% · team 2.8 TD · RZ-D 1.12 · pos-D 1.08 |
| Tony Pollard (TEN RB) | 34% | +193 | ✗ no TD | share 19% · team 2.07 TD · RZ-D 0.97 · pos-D 1.04 |
| Wan'Dale Robinson (TEN WR) | 24% | +324 | ✗ no TD | share 13% · team 2.07 TD · RZ-D 0.97 · pos-D 1.01 |

TD double (Jonathan Taylor + Keenan Allen): 24.8% · fair +303 ✗

**All-position slip** — 34.1% · fair +193 ✗: Cam Ward 30+ pass att ✗(22) · Tony Pollard 10+ carries ✓(19) · Josh Downs 20+ rec yds ✓(40) · Jonathan Taylor ANYTIME TD ✓(TD)

**All-position 8-leg** — 12.8% · fair +684 ✗: Cam Ward 30+ pass att ✗(22) · Tony Pollard 10+ carries ✓(19) · Josh Downs 20+ rec yds ✓(40) · Jonathan Taylor 15+ carries ✓(21) · Keenan Allen 20+ rec yds ✓(82) · Jonathan Taylor ANYTIME TD ✓(TD) · Keenan Allen ANYTIME TD ✗(no TD)


### ARI@LA — final 18-16
*O/U 51.5 · spread +12.5 · indoor · turf · 16:05 ET*

**Personnel:** ARI: Jeremiyah Love OUT — Allgeier backfield; Wingard, W. Williams OUT; Budda Baker Q. LA: Curl, McDuffie Q. Dome.

**Injury report (as built):** ARI DEF · Andrew Wingard (S) — Out · Knee · DNP; ARI OFF · Jeremiyah Love (RB) — Out · Ankle · DNP; ARI DEF · Wydett Williams Jr. (S) — Out · Concussion · DNP; ARI DEF · Budda Baker (S) — Questionable · Not injury related - resting player · DNP; ARI OFF · Blake Gillikin (P) — Questionable · Back; ARI DEF · Zaven Collins (LB) — Questionable · Hip · DNP; ARI DEF · Kitan Crawford (S) — Questionable · Ankle; LA DEF · Kam Curl (S) — Questionable · Ankle · DNP

**Defensive leaks:** LA D leaks passing interceptions to QBs: x1.21; LA D leaks receiving yards to RBs: x1.15 (worsening x1.56 L4); ARI D leaks rushing yards to RBs: x1.16; ARI D leaks receiving yards to TEs: x1.10 (worsening x1.49 L4)

**Coordinators:** ARI OC Nathaniel Hackett — NEW (run_heavy) · measured pass 62% | DC Nick Rallis (blitz_heavy) · LA OC Nathan Scheelhaase — NEW (pass_wr) · measured pass 63% | DC Chris Shula (four_man_rush)

**Props SGP** — 4-leg 42.6% · fair +135 ✗ · 6-leg 27.2% · fair +267 ✗ · 8-leg 20.6% · fair +385 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Trey McBride 7+ receptions | 77% | -335 | ✓ 7 | `4-leg core` · 2026 5/5 pre-game
| 2 | Kendrick Bourne 1+ receptions | 77% | -330 | ✓ 5 | `4-leg core` · 2026 4/4 pre-game
| 3 | Jacoby Brissett 150+ pass yds | 76% | -321 | ✓ 218 | `4-leg core` · 2026 4/5 pre-game
| 4 | Kyren Williams 60+ rush yds | 73% | -267 | ✗ 50 | `4-leg core` · 2026 3/5 pre-game
| 5 | Matthew Stafford 35+ pass att | 84% | -512 | ✗ 33 | `+6` · 2026 3/5 pre-game
| 6 | Davante Adams 30+ rec yds | 71% | -248 | ✓ 39 | `+6` · 2026 4/5 pre-game
| 7 | Puka Nacua 70+ rec yds | 70% | -236 | ✓ 80 | `+8` · 2026 3/3 pre-game
| 8 | Jacoby Brissett 30+ pass att | 80% | -401 | ✓ 35 | `+8` · 2026 4/5 pre-game

Legs 6/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Kyren Williams (LA RB) | 70% | -229 | ✗ no TD | share 25% · team 3.58 TD · RZ-D 1.15 · pos-D 1.14 |
| Davante Adams (LA WR) | 66% | -199 | ✗ no TD | share 26% · team 3.58 TD · RZ-D 1.15 · pos-D 1.11 |
| Puka Nacua (LA WR) | 44% | +127 | ✗ no TD | share 14% · team 3.58 TD · RZ-D 1.15 · pos-D 1.11 |
| Trey McBride (ARI TE) | 34% | +190 | ✗ no TD | share 19% · team 2.18 TD · RZ-D 0.91 · pos-D 0.95 |

TD double (Kyren Williams + Davante Adams): 50.4% · fair -101 ✗

**All-position slip** — 32.9% · fair +204 ✗: Jacoby Brissett 150+ pass yds ✓(218) · Kyren Williams 60+ rush yds ✗(50) · Kendrick Bourne 1+ receptions ✓(5) · Trey McBride 7+ receptions ✓(7) · Kyren Williams ANYTIME TD ✗(no TD)

**All-position 8-leg** — 19.6% · fair +410 ✗: Jacoby Brissett 150+ pass yds ✓(218) · Kyren Williams 60+ rush yds ✗(50) · Kendrick Bourne 1+ receptions ✓(5) · Trey McBride 7+ receptions ✓(7) · Davante Adams 30+ rec yds ✓(39) · Matthew Stafford 35+ pass att ✗(33) · Kyren Williams ANYTIME TD ✗(no TD) · Davante Adams ANYTIME TD ✗(no TD)


### BUF@LV — final 33-30
*O/U 53.5 · spread -5.5 · indoor · grass · 16:25 ET*

**Personnel:** BUF: DJ Moore, Palmer Q — singles only; Oliver Q. LV: Thornton (WR), Runyon (TE), Hemingway OUT. Dome.

**Injury report (as built):** BUF OFF · DJ Moore (WR) — Questionable · Shoulder; BUF DEF · Ed Oliver (DE) — Questionable · Knee; BUF OFF · Josh Palmer (WR) — Questionable · Shoulder; BUF DEF · Dee Alford (CB) — Questionable · Ankle; BUF DEF · T.J. Sanders (DE) — Questionable · Shoulder; LV DEF · Tonka Hemingway (DT) — Out · Concussion · DNP; LV OFF · Carter Runyon (TE) — Out · Foot; LV OFF · Dont'e Thornton Jr. (WR) — Out · Hamstring

**Defensive leaks:** BUF D leaks receiving yards to RBs: x1.13 (worsening x1.09 L4); BUF D leaks receptions to RBs: x1.12 (worsening x1.12 L4); BUF D leaks passing interceptions to QBs: x1.10

**Coordinators:** BUF OC Pete Carmichael Jr. — NEW (balanced) · measured pass 48% | DC Jim Leonhard (disguise_zone) · LV OC Andrew Janocko — NEW (run_heavy) · measured pass 57% | DC Rob Leonard (four_man_rush)

**Props SGP** — 4-leg 46.2% · fair +117 **CASHED** · 6-leg 28.0% · fair +258 **CASHED** · 8-leg 17.0% · fair +489 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Tre Tucker 20+ rec yds | 78% | -356 | ✓ 97 | `4-leg core` · 2026 5/5 pre-game
| 2 | Brock Bowers 4+ receptions | 78% | -352 | ✓ 4 | `4-leg core` · 2026 3/3 pre-game
| 3 | Khalil Shakir 2+ receptions | 78% | -352 | ✓ 4 | `4-leg core` · 2026 4/5 pre-game
| 4 | Josh Allen 150+ pass yds | 80% | -389 | ✓ 255 | `4-leg core` · 2026 5/5 pre-game
| 5 | Kirk Cousins 30+ pass att | 73% | -264 | ✓ 41 | `+6` · 2026 3/5 pre-game
| 6 | James Cook 60+ rush yds | 72% | -264 | ✓ 95 | `+6` · 2026 4/5 pre-game
| 7 | Ashton Jeanty 40+ rush yds | 70% | -237 | ✗ 22 | `+8` · 2026 4/5 pre-game
| 8 | Khalil Shakir 20+ rec yds | 76% | -313 | ✓ 34 | `+8` · 2026 4/5 pre-game

Legs 7/8 (expected 6.0)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Josh Allen (BUF QB) | 59% | -144 | ✗ no TD | share 18% · team 3.3 TD · RZ-D 1.06 · pos-D 1.41 |
| Ashton Jeanty (LV RB) | 56% | -126 | ✓ TD | share 25% · team 2.69 TD · RZ-D 1.11 · pos-D 1.22 |
| James Cook (BUF RB) | 53% | -111 | ✓ TD | share 22% · team 3.3 TD · RZ-D 1.06 · pos-D 1.04 |
| Brock Bowers (LV TE) | 42% | +138 | ✗ no TD | share 24% · team 2.69 TD · RZ-D 1.11 · pos-D 0.82 |

TD double (Josh Allen + Ashton Jeanty): 35.1% · fair +185 ✗

**All-position slip** — 31.1% · fair +222 ✗: Josh Allen 150+ pass yds ✓(255) · Ashton Jeanty 1+ receptions ✓(4) · Tre Tucker 20+ rec yds ✓(97) · Brock Bowers 4+ receptions ✓(4) · Josh Allen ANYTIME TD ✗(no TD)

**All-position 8-leg** — 15.3% · fair +554 ✗: Josh Allen 150+ pass yds ✓(255) · Ashton Jeanty 1+ receptions ✓(4) · Tre Tucker 20+ rec yds ✓(97) · Brock Bowers 4+ receptions ✓(4) · James Cook 60+ rush yds ✓(95) · Khalil Shakir 20+ rec yds ✓(34) · Josh Allen ANYTIME TD ✗(no TD) · Ashton Jeanty ANYTIME TD ✓(TD)


### LAC@KC — final 6-22
*O/U 41.5 · spread +7.5 · outdoor · grass · 16:25 ET*

**Personnel:** LAC: Tre Harris OUT; Derwin James, D. Jackson, Alt, Awosika OUT; Shelley doubtful; KLS Q. KC: Rashee Rice OUT; Simmons (T) OUT; Sneed Q.

**Injury report (as built):** KC OFF · Rashee Rice (WR) — Out · Hamstring · DNP; KC OFF · Josh Simmons (T) — Out · Back; KC DEF · L'Jarius Sneed (CB) — Questionable · Knee; LAC DEF · Rodney Shelley (CB) — Doubtful · Hamstring · DNP; LAC DEF · Donte Jackson (CB) — Out · Hamstring · DNP; LAC DEF · Derwin James (S) — Out · Hamstring · DNP; LAC OFF · Kayode Awosika (G) — Out · Fibula · DNP; LAC OFF · Joe Alt (T) — Out · Neck · DNP

**Defensive leaks:** KC D leaks receiving yards to TEs: x1.17 (worsening x2.09 L4); KC D leaks receptions to TEs: x1.11 (worsening x1.81 L4); LAC D leaks passing interceptions to QBs: x1.39

**Coordinators:** LAC OC Mike McDaniel — NEW (pass_rb) · measured pass 49% | DC Chris O'Leary (two_high_shell) · KC OC Eric Bieniemy — NEW (pass_wr) · measured pass 52% | DC Steve Spagnuolo (blitz_heavy)

**Props SGP** — 4-leg 45.1% · fair +122 **CASHED** · 6-leg 25.4% · fair +293 **CASHED** · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Patrick Mahomes 200+ pass yds | 78% | -347 | ✓ 272 | `4-leg core` · 2026 3/4 pre-game
| 2 | Xavier Worthy 2+ receptions | 77% | -340 | ✓ 7 | `4-leg core` · 2026 4/4 pre-game
| 3 | Ladd McConkey 1+ receptions | 80% | -394 | ✓ 1 | `4-leg core` · 2026 3/4 pre-game
| 4 | Justin Herbert 20+ pass att | 76% | -321 | ✓ 37 | `4-leg core` · 2026 5/5 pre-game
| 5 | Travis Kelce 20+ rec yds | 73% | -275 | ✓ 53 | `+6` · 2026 3/4 pre-game
| 6 | Kenneth Walker III 40+ rush yds | 71% | -247 | ✓ 128 | `+6` · 2026 4/4 pre-game
| 7 | Quentin Johnston 20+ rec yds | 71% | -243 | ✓ 57 | `+8` · 2026 2/4 pre-game

Legs 7/7 (expected 5.3)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Kenneth Walker III (KC RB) | 42% | +137 | ✓ TD | share 21% · team 2.74 TD · RZ-D 0.9 · pos-D 0.96 |
| Omarion Hampton (LAC RB) | 28% | +254 | ✗ no TD | share 21% · team 1.9 TD · RZ-D 0.92 · pos-D 0.9 |
| Xavier Worthy (KC WR) | 24% | +310 | ✗ no TD | share 10% · team 2.74 TD · RZ-D 0.9 · pos-D 0.95 |
| Travis Kelce (KC TE) | 22% | +344 | ✗ no TD | share 9% · team 2.74 TD · RZ-D 0.9 · pos-D 0.91 |

TD double (Kenneth Walker III + Omarion Hampton): 13.8% · fair +624 ✗

**All-position slip** — 21.4% · fair +368 **CASHED**: Patrick Mahomes 200+ pass yds ✓(272) · Kenneth Walker III 40+ rush yds ✓(128) · Xavier Worthy 2+ receptions ✓(7) · Travis Kelce 3+ receptions ✓(4) · Kenneth Walker III ANYTIME TD ✓(TD)

**All-position 8-leg** — 6.7% · fair +1384 ✗: Patrick Mahomes 200+ pass yds ✓(272) · Kenneth Walker III 40+ rush yds ✓(128) · Xavier Worthy 2+ receptions ✓(7) · Travis Kelce 3+ receptions ✓(4) · Quentin Johnston 20+ rec yds ✓(57) · Justin Herbert 20+ pass att ✓(37) · Kenneth Walker III ANYTIME TD ✓(TD) · Omarion Hampton ANYTIME TD ✗(no TD)


### DAL@GB — final 13-23
*O/U 53.5 · spread +1.5 · outdoor · grass · 20:20 ET*

**Personnel:** DAL: Durant (CB), Shelton (T) OUT; Porter Jr., Overshown Q. GB: Hargrave (DT), St-Juste (CB), Skyy Moore OUT; Banks, Monk Q. Outdoor grass, night.

**Injury report (as built):** DAL DEF · Cobie Durant (CB) — Out · Hamstring · DNP; DAL OFF · Drew Shelton (T) — Out · Hamstring · DNP; DAL DEF · DeMarvion Overshown (LB) — Questionable · Hamstring; DAL DEF · Ameer Speed (CB) — Questionable · Knee; DAL DEF · Joey Porter Jr. (CB) — Questionable · Ankle; DAL DEF · LT Overton (DT) — Questionable · Foot · DNP; DAL DEF · Von Miller (LB) — nan · DNP; GB DEF · Jordon Riley (DE) — Doubtful · Achilles

**Defensive leaks:** GB D leaks receptions to RBs: x1.11; GB D leaks passing interceptions to QBs: x1.10 (worsening x2.60 L4); DAL D leaks receiving yards to RBs: x1.21; DAL D leaks receiving yards to WRs: x1.13 (worsening x1.11 L4)

**Coordinators:** DAL OC Klayton Adams — continuity · measured pass 64% | DC Christian Parker (two_high_shell) · GB OC Adam Stenavich — continuity · measured pass 65% | DC Jonathan Gannon (two_high_shell)

**Props SGP** — 4-leg 45.4% · fair +120 **CASHED** · 6-leg 27.8% · fair +260 **CASHED** · 8-leg 22.0% · fair +354 **CASHED**

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Tucker Kraft 3+ receptions | 78% | -353 | ✓ 5 | `4-leg core` · 2026 4/5 pre-game
| 2 | Jordan Love 225+ pass yds | 78% | -351 | ✓ 276 | `4-leg core` · 2026 3/5 pre-game
| 3 | Matthew Golden 2+ receptions | 78% | -351 | ✓ 6 | `4-leg core` · 2026 5/5 pre-game
| 4 | Javonte Williams 20+ rush yds | 76% | -309 | ✓ 41 | `4-leg core` · 2026 5/5 pre-game
| 5 | George Pickens 20+ rec yds | 76% | -309 | ✓ 73 | `+6` · 2026 5/5 pre-game
| 6 | CeeDee Lamb 40+ rec yds | 74% | -283 | ✓ 70 | `+6` · 2026 4/5 pre-game
| 7 | Dak Prescott 175+ pass yds | 74% | -277 | ✓ 258 | `+8` · 2026 5/5 pre-game
| 8 | Jordan Love 30+ pass att | 81% | -432 | ✓ 41 | `+8` · 2026 4/5 pre-game

Legs 8/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Javonte Williams (DAL RB) | 51% | -105 | ✓ TD | share 23% · team 2.91 TD · RZ-D 1.05 · pos-D 1.03 |
| Christian Watson (GB WR) | 49% | +104 | ✗ no TD | share 17% · team 3.08 TD · RZ-D 1.1 · pos-D 1.22 |
| George Pickens (DAL WR) | 39% | +157 | ✗ no TD | share 16% · team 2.91 TD · RZ-D 1.05 · pos-D 1.02 |
| MarShawn Lloyd (GB RB) | 38% | +162 | ✗ no TD | share 13% · team 3.08 TD · RZ-D 1.1 · pos-D 1.1 |

TD double (Javonte Williams + Christian Watson): 27.2% · fair +267 ✗

**All-position slip** — 27.0% · fair +271 **CASHED**: Jordan Love 225+ pass yds ✓(276) · Javonte Williams 20+ rush yds ✓(41) · Matthew Golden 2+ receptions ✓(6) · Tucker Kraft 3+ receptions ✓(5) · Javonte Williams ANYTIME TD ✓(TD)

**All-position 8-leg** — 12.7% · fair +685 ✗: Jordan Love 225+ pass yds ✓(276) · Javonte Williams 20+ rush yds ✓(41) · Matthew Golden 2+ receptions ✓(6) · Tucker Kraft 3+ receptions ✓(5) · George Pickens 20+ rec yds ✓(73) · Dak Prescott 175+ pass yds ✓(258) · Javonte Williams ANYTIME TD ✓(TD) · Christian Watson ANYTIME TD ✗(no TD)


### Cross-game combos — Week 6 — v1.9f build (made pre-kick the same morning; not shipped)

**4-leg** — 42.8% · fair +134 — 4/4 **CASHED**
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | BUF@LV | Tre Tucker 20+ rec yds | 78% | ✓ 97 |
| 2 | BUF@LV | Brock Bowers 4+ receptions | 78% | ✓ 4 |
| 3 | DAL@GB | Tucker Kraft 3+ receptions | 78% | ✓ 5 |
| 4 | DAL@GB | Jordan Love 225+ pass yds | 78% | ✓ 276 |

**6-leg** — 25.8% · fair +288 — 4/6 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | BUF@LV | Tre Tucker 20+ rec yds | 78% | ✓ 97 |
| 2 | BUF@LV | Brock Bowers 4+ receptions | 78% | ✓ 4 |
| 3 | DAL@GB | Tucker Kraft 3+ receptions | 78% | ✓ 5 |
| 4 | DAL@GB | Jordan Love 225+ pass yds | 78% | ✓ 276 |
| 5 | NO@NYG | Cam Skattebo 10+ carries | 78% | – DNP |
| 6 | TEN@IND | Cam Ward 30+ pass att | 78% | ✗ 22 |

**8-leg** — 15.9% · fair +528 — 6/8 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | BUF@LV | Tre Tucker 20+ rec yds | 78% | ✓ 97 |
| 2 | BUF@LV | Brock Bowers 4+ receptions | 78% | ✓ 4 |
| 3 | DAL@GB | Tucker Kraft 3+ receptions | 78% | ✓ 5 |
| 4 | DAL@GB | Jordan Love 225+ pass yds | 78% | ✓ 276 |
| 5 | NO@NYG | Cam Skattebo 10+ carries | 78% | – DNP |
| 6 | TEN@IND | Cam Ward 30+ pass att | 78% | ✗ 22 |
| 7 | LAC@KC | Patrick Mahomes 200+ pass yds | 78% | ✓ 272 |
| 8 | CAR@PHI | Chuba Hubbard 10+ carries | 78% | ✓ 28 |

**10-leg** — 9.7% · fair +927 — 8/10 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | BUF@LV | Tre Tucker 20+ rec yds | 78% | ✓ 97 |
| 2 | BUF@LV | Brock Bowers 4+ receptions | 78% | ✓ 4 |
| 3 | DAL@GB | Tucker Kraft 3+ receptions | 78% | ✓ 5 |
| 4 | CHI@ATL | Rome Odunze 2+ receptions | 78% | ✓ 3 |
| 5 | DAL@GB | Jordan Love 225+ pass yds | 78% | ✓ 276 |
| 6 | NO@NYG | Cam Skattebo 10+ carries | 78% | – DNP |
| 7 | TEN@IND | Cam Ward 30+ pass att | 78% | ✗ 22 |
| 8 | LAC@KC | Patrick Mahomes 200+ pass yds | 78% | ✓ 272 |
| 9 | CAR@PHI | Chuba Hubbard 10+ carries | 78% | ✓ 28 |
| 10 | TEN@IND | Josh Downs 20+ rec yds | 79% | ✓ 40 |

**12-leg** — 6.0% · fair +1568 — 10/12 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | BUF@LV | Tre Tucker 20+ rec yds | 78% | ✓ 97 |
| 2 | BUF@LV | Brock Bowers 4+ receptions | 78% | ✓ 4 |
| 3 | DAL@GB | Tucker Kraft 3+ receptions | 78% | ✓ 5 |
| 4 | CHI@ATL | Rome Odunze 2+ receptions | 78% | ✓ 3 |
| 5 | BAL@CLE | Zay Flowers 3+ receptions | 78% | ✓ 6 |
| 6 | DAL@GB | Jordan Love 225+ pass yds | 78% | ✓ 276 |
| 7 | NO@NYG | Cam Skattebo 10+ carries | 78% | – DNP |
| 8 | TEN@IND | Cam Ward 30+ pass att | 78% | ✗ 22 |
| 9 | LAC@KC | Patrick Mahomes 200+ pass yds | 78% | ✓ 272 |
| 10 | CAR@PHI | Chuba Hubbard 10+ carries | 78% | ✓ 28 |
| 11 | TEN@IND | Josh Downs 20+ rec yds | 79% | ✓ 40 |
| 12 | NYJ@NE | Geno Smith 175+ pass yds | 77% | ✓ 252 |


### ATD board (top 16) — Week 6 — v1.9f build (made pre-kick the same morning; not shipped)

| # | Game | Player | Model | Fair | Result |
|---|---|---|---|---|---|
| 1 | ARI@LA | Kyren Williams (RB) | 70% | -229 | ✗ no TD |
| 2 | ARI@LA | Davante Adams (WR) | 66% | -199 | ✗ no TD |
| 3 | TEN@IND | Jonathan Taylor (RB) | 59% | -144 | ✓ TD |
| 4 | BUF@LV | Josh Allen (QB) | 59% | -144 | ✗ no TD |
| 5 | BUF@LV | Ashton Jeanty (RB) | 56% | -126 | ✓ TD |
| 6 | NYJ@NE | Rhamondre Stevenson (RB) | 54% | -117 | ✗ no TD |
| 7 | BUF@LV | James Cook (RB) | 53% | -111 | ✓ TD |
| 8 | DAL@GB | Javonte Williams (RB) | 51% | -105 | ✓ TD |
| 9 | BAL@CLE | Derrick Henry (RB) | 50% | -102 | ✗ no TD |
| 10 | CHI@ATL | Bijan Robinson (RB) | 50% | +102 | ✗ no TD |
| 11 | DAL@GB | Christian Watson (WR) | 49% | +104 | ✗ no TD |
| 12 | CHI@ATL | D'Andre Swift (RB) | 48% | +107 | ✓ TD |
| 13 | NO@NYG | Malik Nabers (WR) | 44% | +125 | ✗ no TD |
| 14 | ARI@LA | Puka Nacua (WR) | 44% | +127 | ✗ no TD |
| 15 | CHI@ATL | Drake London (WR) | 44% | +130 | ✗ no TD |
| 16 | LAC@KC | Kenneth Walker III (RB) | 42% | +137 | ✓ TD |

Board: top-16 6/16 · top-8 4/8 · chalk triple 1/3

**2+ TD board (singles only):** Kyren Williams 33% (+200) · Davante Adams 30% (+235) · Jonathan Taylor 22% (+346) · Josh Allen 22% (+347) · Ashton Jeanty 20% (+406) · Rhamondre Stevenson 18% (+448)


### Scorecard — Week 6 — v1.9f build (made pre-kick the same morning; not shipped)

**Legs 69/80 = 86% actual vs 77% expected · SGP4 6/11 · SGP6 6/11 · SGP8 1/11**

| Game | Final | Legs | SGP4 | SGP6 | SGP8 |
|---|---|---|---|---|---|
| DAL@GB | 13-23 | 8/8 | ✓ | ✓ | ✓ |
| CHI@ATL | 31-23 | 7/7 | ✓ | ✓ | ✗ |
| NYJ@NE | 19-26 | 7/7 | ✓ | ✓ | ✗ |
| PIT@TB | 26-19 | 7/7 | ✓ | ✓ | ✗ |
| BUF@LV | 33-30 | 7/8 | ✓ | ✓ | ✗ |
| LAC@KC | 6-22 | 7/7 | ✓ | ✓ | ✗ |
| CAR@PHI | 25-14 | 6/7 | ✗ | ✗ | ✗ |
| TEN@IND | 26-20 | 6/8 | ✗ | ✗ | ✗ |
| ARI@LA | 18-16 | 6/8 | ✗ | ✗ | ✗ |
| BAL@CLE | 10-13 | 5/7 | ✗ | ✗ | ✗ |
| NO@NYG | 34-27 | 3/6 | ✗ | ✗ | ✗ |


## Week 6 — aggressive band (shipped)

*Engine v1.9e.* 59% vs 61% expected; SGP4 3/11 (expected 2.2); TEN@IND and LAC@KC all-position slips cashed.


### BAL@CLE — final 10-13
*O/U 39.5 · spread -3.0 · outdoor · grass · 13:00 ET*

**Personnel:** BAL: Lamar OUT — Huntley 2nd start; Jurgens, Hibner OUT. CLE: Watson starts (Gabriel IR); Sampson OUT; Judkins Q — singles only.

**Injury report (as built):** BAL OFF · Lamar Jackson (QB) — Out · Ankle · DNP; BAL DEF · Broderick Washington (DE) — Out · Ankle · DNP; BAL OFF · Cam Jurgens (C) — Out · Concussion; BAL OFF · Matthew Hibner (TE) — Out · Hand · DNP; BAL OFF · Andrew Vorhees (G) — Questionable · Foot; BAL OFF · Emery Jones Jr. (G) — Questionable · Ankle; BAL OFF · Ja'Kobi Lane (WR) — Questionable · Wrist; BAL DEF · Calais Campbell (DT) — nan · DNP

**Defensive leaks:** BAL D leaks receiving yards to RBs: x1.20; BAL D leaks receptions to RBs: x1.18; BAL D leaks receiving yards to WRs: x1.17 (worsening x1.23 L4)

**Coordinators:** BAL OC Declan Doyle — NEW (pass_wr) · measured pass 46% | DC Anthony Weaver (pressure) · CLE OC Travis Switzer — NEW (run_heavy) · measured pass 54% | DC Mike Rutenberg (multiple)

**Props SGP** — 4-leg 19.0% · fair +426 ✗ · 6-leg 9.0% · fair +1010 ✗ · 8-leg 5.4% · fair +1752 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Harold Fannin Jr. 30+ rec yds | 62% | -167 | ✗ 9 | `4-leg core` · 2026 2/5 pre-game
| 2 | Tyler Huntley 20+ pass att | 61% | -159 | ✓ 31 | `4-leg core` · 2026 1/2 pre-game
| 3 | Derrick Henry 90+ rush yds | 61% | -158 | ✗ 58 | `4-leg core` · 2026 2/5 pre-game
| 4 | KC Concepcion 30+ rec yds | 64% | -175 | ✓ 37 | `4-leg core` · 2026 2/5 pre-game
| 5 | Mark Andrews 3+ receptions | 60% | -149 | ✗ 1 | `+6` · 2026 5/5 pre-game
| 6 | Deshaun Watson 20+ rush yds | 65% | -187 | ✓ 29 | `+6` · 2026 5/5 pre-game
| 7 | Harold Fannin Jr. 4+ receptions | 60% | -151 | ✗ 1 | `+8` · 2026 2/5 pre-game
| 8 | Deshaun Watson 175+ pass yds | 55% | -124 | ✗ 164 | `+8` · 2026 3/5 pre-game

Legs 3/8 (expected 4.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Derrick Henry (BAL RB) | 50% | -102 | ✗ no TD | share 30% · team 2.38 TD · RZ-D 0.99 · pos-D 0.91 |
| Denzel Boston (CLE WR) | 28% | +257 | ✗ no TD | share 17% · team 2.04 TD · RZ-D 0.89 · pos-D 0.98 |
| Mark Andrews (BAL TE) | 24% | +308 | ✗ no TD | share 15% · team 2.38 TD · RZ-D 0.99 · pos-D 0.9 |
| Harold Fannin Jr. (CLE TE) | 21% | +376 | ✗ no TD | share 14% · team 2.04 TD · RZ-D 0.89 · pos-D 0.85 |

TD double (Derrick Henry + Denzel Boston): 16.1% · fair +521 ✗

**All-position slip** — 13.2% · fair +656 ✗: Tyler Huntley 20+ pass att ✓(31) · Derrick Henry 90+ rush yds ✗(58) · KC Concepcion 30+ rec yds ✓(37) · Harold Fannin Jr. 30+ rec yds ✗(9) · Derrick Henry ANYTIME TD ✗(no TD)

**All-position 8-leg** — 3.8% · fair +2559 ✗: Tyler Huntley 20+ pass att ✓(31) · Derrick Henry 90+ rush yds ✗(58) · KC Concepcion 30+ rec yds ✓(37) · Harold Fannin Jr. 30+ rec yds ✗(9) · Mark Andrews 3+ receptions ✗(1) · Deshaun Watson 20+ rush yds ✓(29) · Derrick Henry ANYTIME TD ✗(no TD) · Denzel Boston ANYTIME TD ✗(no TD)


### CAR@PHI — final 25-14
*O/U 39.5 · spread -3.0 · outdoor · grass · 13:00 ET*

**Personnel:** PHI: Hurts OUT (calf clot) — Tanner McKee starts. Barkley, Shipley OUT, Bigsby IR — Dameon Pierce backfield. Dickerson (G), Calcaterra (TE), Carter II (S), Bennett (CB) OUT. CAR: Dillon OUT, Freeling doubtful; Etienne, Moton Q.

**Injury report (as built):** CAR OFF · Monroe Freeling (T) — Doubtful · Knee; CAR OFF · AJ Dillon (RB) — Out · Ankle · DNP; CAR OFF · Taylor Moton (T) — Questionable · Lung; CAR DEF · Tershawn Wharton (DT) — Questionable · Neck; CAR OFF · Damien Lewis (G) — Questionable · Elbow; CAR DEF · Jaelan Phillips (LB) — Questionable · Hamstring; CAR OFF · Trevor Etienne (RB) — Questionable · Ankle; PHI DEF · A.J. Epenesa (LB) — Doubtful · Back · DNP

**Defensive leaks:** CAR D leaks rushing yards to RBs: x1.34; CAR D leaks carries to RBs: x1.17; CAR D leaks receiving yards to TEs: x1.08 (worsening x1.26 L4)

**Coordinators:** CAR OC Brad Idzik — continuity · measured pass 63% | DC Ejiro Evero (two_high_shell) · PHI OC Sean Mannion — NEW (run_heavy) · measured pass 56% | DC Vic Fangio (two_high_shell)

**Props SGP** — 4-leg 22.3% · fair +349 ✗ · 6-leg 10.1% · fair +890 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Tetairoa McMillan 60+ rec yds | 61% | -155 | ✓ 86 | `4-leg core` · 2026 3/4 pre-game
| 2 | Dontayvion Wicks 20+ rec yds | 63% | -173 | ✓ 24 | `4-leg core` · 2026 4/5 pre-game
| 3 | Bryce Young o0.5 INT o0.5 | 60% | -152 | ✗ 0 INT | `4-leg core` · 2026 2/4 pre-game
| 4 | Chuba Hubbard 3+ receptions | 60% | -147 | ✗ 1 | `4-leg core` · 2026 2/4 pre-game
| 5 | DeVonta Smith 4+ receptions | 59% | -142 | ✓ 7 | `+6` · 2026 2/3 pre-game
| 6 | Chuba Hubbard 60+ rush yds | 59% | -145 | ✓ 120 | `+6` · 2026 2/4 pre-game
| 7 | Bryce Young 225+ pass yds | 56% | -125 | ✓ 281 | `+8` · 2026 4/4 pre-game

Legs 5/7 (expected 4.2)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Chuba Hubbard (CAR RB) | 38% | +160 | ✓ TD | share 19% · team 2.38 TD · RZ-D 0.94 · pos-D 1.01 |
| Dallas Goedert (PHI TE) | 29% | +246 | ✗ no TD | share 14% · team 2.04 TD · RZ-D 0.98 · pos-D 1.08 |
| Tetairoa McMillan (CAR WR) | 27% | +266 | ✗ no TD | share 16% · team 2.38 TD · RZ-D 0.94 · pos-D 0.88 |
| DeVonta Smith (PHI WR) | 25% | +294 | ✓ TD | share 16% · team 2.04 TD · RZ-D 0.98 · pos-D 0.85 |

TD double (Chuba Hubbard + Dallas Goedert): 13.0% · fair +670 ✗

**All-position slip** — 14.7% · fair +581 ✗: Bryce Young 225+ pass yds ✓(281) · Chuba Hubbard 3+ receptions ✗(1) · Tetairoa McMillan 60+ rec yds ✓(86) · Darren Waller 30+ rec yds ✗(0) · Chuba Hubbard ANYTIME TD ✓(TD)

**All-position 8-leg** — 4.7% · fair +2016 ✗: Bryce Young 225+ pass yds ✓(281) · Chuba Hubbard 3+ receptions ✗(1) · Tetairoa McMillan 60+ rec yds ✓(86) · Darren Waller 30+ rec yds ✗(0) · DeVonta Smith 4+ receptions ✓(7) · Chuba Hubbard ANYTIME TD ✓(TD) · Dallas Goedert ANYTIME TD ✗(no TD)


### CHI@ATL — final 31-23
*O/U 51.5 · spread -1.5 · indoor · turf · 13:00 ET*

**Personnel:** CHI: Caleb Williams ACTIVE (hamstring) per club; Monangai OUT — Swift; T.J. Edwards, Odeyingbo OUT; Gordon, Stevenson Q. ATL: C.J. Henderson OUT; Z. Smith Q.

**Injury report (as built):** ATL DEF · C.J. Henderson (CB) — Out · Groin · DNP; ATL DEF · Za'Darius Smith (DE) — Questionable · Neck; CHI DEF · T.J. Edwards (LB) — Out · Hamstring · DNP; CHI DEF · Dayo Odeyingbo (DE) — Out · Quadricep · DNP; CHI OFF · Kyle Monangai (RB) — Out · Thumb · DNP; CHI DEF · Keyshaun Elliott (LB) — Out · Quadricep · DNP; CHI DEF · Kyler Gordon (CB) — Questionable · Calf; CHI DEF · Tyrique Stevenson (CB) — Questionable · Hip

**Defensive leaks:** ATL D leaks receptions to RBs: x1.14 (worsening x1.11 L4); ATL D leaks receptions to WRs: x1.10 (worsening x1.27 L4); CHI D leaks passing interceptions to QBs: x1.35; CHI D leaks rushing yards to RBs: x1.15

**Coordinators:** CHI OC Press Taylor — NEW (pass_wr) · measured pass 48% | DC Dennis Allen (blitz_man) · ATL OC Tommy Rees — NEW (run_heavy) · measured pass 45% | DC Jeff Ulbrich (blitz_heavy)

**Props SGP** — 4-leg 19.6% · fair +410 ✗ · 6-leg 9.5% · fair +949 ✗ · 8-leg 6.3% · fair +1475 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Kalif Raymond 20+ rec yds | 62% | -164 | ✗ 18 | `4-leg core` · 2026 3/5 pre-game
| 2 | Bijan Robinson 3+ receptions | 63% | -168 | ✗ 2 | `4-leg core` · 2026 3/5 pre-game
| 3 | Tyson Bagent o0.5 INT o0.5 | 63% | -169 | – DNP | `4-leg core` · 2026 2/3 pre-game
| 4 | D'Andre Swift 60+ rush yds | 61% | -157 | ✗ 44 | `4-leg core` · 2026 2/5 pre-game
| 5 | Drake London 6+ receptions | 63% | -171 | ✗ 4 | `+6` · 2026 2/5 pre-game
| 6 | Brian Robinson 40+ rush yds | 61% | -156 | ✗ 1 | `+6` · 2026 3/5 pre-game
| 7 | Michael Penix Jr. 200+ pass yds | 64% | -176 | ✓ 225 | `+8` · 2026 3/3 pre-game
| 8 | Luther Burden III 40+ rec yds | 64% | -178 | ✓ 95 | `+8` · 2026 4/5 pre-game

Legs 2/7 (expected 5.0)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Bijan Robinson (ATL RB) | 50% | +102 | ✗ no TD | share 28% · team 2.8 TD · RZ-D 0.97 · pos-D 0.94 |
| D'Andre Swift (CHI RB) | 48% | +107 | ✓ TD | share 19% · team 2.97 TD · RZ-D 0.93 · pos-D 0.94 |
| Drake London (ATL WR) | 44% | +130 | ✗ no TD | share 18% · team 2.8 TD · RZ-D 0.97 · pos-D 1.18 |
| Rome Odunze (CHI WR) | 41% | +144 | ✗ no TD | share 14% · team 2.97 TD · RZ-D 0.93 · pos-D 1.11 |

TD double (Bijan Robinson + D'Andre Swift): 26.1% · fair +283 ✗

**All-position slip** — 15.2% · fair +560 ✗: Michael Penix Jr. 200+ pass yds ✓(225) · Bijan Robinson 3+ receptions ✗(2) · Kalif Raymond 20+ rec yds ✗(18) · Colston Loveland 3+ receptions ✓(6) · Bijan Robinson ANYTIME TD ✗(no TD)

**All-position 8-leg** — 5.7% · fair +1647 ✗: Michael Penix Jr. 200+ pass yds ✓(225) · Bijan Robinson 3+ receptions ✗(2) · Kalif Raymond 20+ rec yds ✗(18) · Colston Loveland 3+ receptions ✓(6) · D'Andre Swift 60+ rush yds ✗(44) · Luther Burden III 40+ rec yds ✓(95) · Bijan Robinson ANYTIME TD ✗(no TD) · D'Andre Swift ANYTIME TD ✓(TD)


### NO@NYG — final 34-27
*O/U 46.5 · spread -1.5 · outdoor · turf · 13:00 ET*

**Personnel:** NYG: Theo Johnson (TE), Nubin (S), Hood (CB) OUT; A. Thomas, Eluemunor Q. NO: Elliss, Jennings (LBs) OUT; Kamara, Olave Q — singles only.

**Injury report (as built):** NO DEF · Kaden Elliss (LB) — Out · Calf · DNP; NO DEF · Anfernee Jennings (LB) — Out · Knee · DNP; NO OFF · Zach Wood (LS) — Questionable · Calf; NO OFF · Alvin Kamara (RB) — Questionable · Back; NO DEF · Nathan Shepherd (DT) — Questionable · Illness; NO OFF · Chris Olave (WR) — Questionable · Illness; NO DEF · Lorenzo Styles Jr. (CB) — Questionable · Knee; NYG OFF · Theo Johnson (TE) — Out · Neck · DNP

**Defensive leaks:** NYG D leaks rushing yards to RBs: x1.19; NO D leaks rushing yards to RBs: x1.17 (worsening x1.30 L4); NO D leaks carries to RBs: x1.12 (worsening x1.12 L4)

**Coordinators:** NO OC Doug Nussmeier — continuity · measured pass 64% | DC Brandon Staley (two_high_shell) · NYG OC Matt Nagy — NEW (pass_wr) · measured pass 53% | DC Dennard Wilson (pressure)

**Props SGP** — 4-leg 19.1% · fair +424 ✗ · 6-leg 11.6% · fair +760 ✗ · 8-leg 4.9% · fair +1925 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Devaughn Vele 5+ receptions | 62% | -163 | ✗ 3 | `4-leg core` · 2026 3/5 pre-game
| 2 | Jameis Winston 20+ pass att | 62% | -165 | ✓ 26 | `4-leg core` · 2026 4/4 pre-game
| 3 | Cam Skattebo 15+ carries | 62% | -166 | – DNP | `4-leg core` · 2026 3/5 pre-game
| 4 | Tyler Shough 275+ pass yds | 61% | -158 | ✗ 144 | `4-leg core` · 2026 2/5 pre-game
| 5 | Juwan Johnson 5+ receptions | 61% | -157 | ✗ 0 | `+6` · 2026 2/5 pre-game
| 6 | Isaiah Likely 30+ rec yds | 64% | -174 | ✓ 99 | `+6` · 2026 4/5 pre-game
| 7 | Malik Nabers 60+ rec yds | 58% | -136 | ✓ 165 | `+8` · 2026 3/5 pre-game
| 8 | Kendre Miller 30+ rush yds | 57% | -130 | ✓ 70 | `+8` · 2026 2/4 pre-game

Legs 4/7 (expected 4.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Malik Nabers (NYG WR) | 44% | +125 | ✗ no TD | share 21% · team 2.52 TD · RZ-D 0.96 · pos-D 1.06 |
| Cam Skattebo (NYG RB) | 40% | +151 | – DNP | share 17% · team 2.52 TD · RZ-D 0.96 · pos-D 1.12 |
| Tyler Shough (NO QB) | 30% | +232 | ✓ TD | share 11% · team 2.69 TD · RZ-D 1.06 · pos-D 1.2 |
| Devaughn Vele (NO WR) | 29% | +240 | ✗ no TD | share 12% · team 2.69 TD · RZ-D 1.06 · pos-D 1.04 |

TD double (Malik Nabers + Cam Skattebo): 22.2% · fair +351 ✗

**All-position slip** — 12.1% · fair +728 ✗: Jameis Winston 20+ pass att ✓(26) · Cam Skattebo 15+ carries –(DNP) · Devaughn Vele 5+ receptions ✗(3) · Juwan Johnson 5+ receptions ✗(0) · Malik Nabers ANYTIME TD ✗(no TD)

**All-position 8-leg** — 3.9% · fair +2465 ✗: Jameis Winston 20+ pass att ✓(26) · Cam Skattebo 15+ carries –(DNP) · Devaughn Vele 5+ receptions ✗(3) · Juwan Johnson 5+ receptions ✗(0) · Kendre Miller 30+ rush yds ✓(70) · Malik Nabers 60+ rec yds ✓(165) · Malik Nabers ANYTIME TD ✗(no TD) · Cam Skattebo ANYTIME TD –(DNP)


### NYJ@NE — final 19-26
*O/U 43.5 · spread +7.5 · outdoor · turf · 13:00 ET*

**Personnel:** NYJ: Breece Hall OUT — Braelon Allen backfield; A. Mitchell OUT. NE: Carlton Davis III + Prunty (CBs) OUT; A.J. Brown activated off IR (no 2026 sample — not in pool); Henderson Q.

**Injury report (as built):** NE DEF · Carlton Davis III (CB) — Out · Neck · DNP; NE DEF · Karon Prunty (CB) — Out · Hamstring · DNP; NE OFF · A.J. Brown (WR) — Questionable · Ankle; NE DEF · Christian Elliss (LB) — Questionable · Chest; NE OFF · Marcus Bryant (T) — Questionable · Ankle; NE OFF · Will Campbell (T) — Questionable · Knee; NE DEF · Craig Woodson (S) — Questionable · Shoulder; NE OFF · TreVeyon Henderson (RB) — Questionable · Ankle

**Defensive leaks:** NYJ D leaks carries to RBs: x1.13 (worsening x1.25 L4); NYJ D leaks rushing yards to RBs: x1.10 (worsening x1.29 L4)

**Coordinators:** NYJ OC Frank Reich — NEW (balanced) · measured pass 53% | DC Brian Duker (multiple) · NE OC Josh McDaniels — continuity · measured pass 51% | DC Zak Kuhr (multiple)

**Props SGP** — 4-leg 21.9% · fair +356 ✗ · 6-leg 8.8% · fair +1034 ✗ · 8-leg 5.1% · fair +1872 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Garrett Wilson 60+ rec yds | 64% | -174 | ✗ 44 | `4-leg core` · 2026 3/5 pre-game
| 2 | Geno Smith 25+ pass att | 64% | -180 | ✓ 30 | `4-leg core` · 2026 3/5 pre-game
| 3 | Drake Maye o0.5 INT o0.5 | 60% | -148 | ✗ 0 INT | `4-leg core` · 2026 4/5 pre-game
| 4 | Rhamondre Stevenson 50+ rush yds | 59% | -143 | ✗ 36 | `4-leg core` · 2026 2/5 pre-game
| 5 | Romeo Doubs 30+ rec yds | 66% | -192 | ✓ 42 | `+6` · 2026 3/5 pre-game
| 6 | Braelon Allen 30+ rush yds | 56% | -129 | ✓ 78 | `+6` · 2026 3/5 pre-game
| 7 | Drake Maye 200+ pass yds | 59% | -144 | ✓ 235 | `+8` · 2026 3/5 pre-game
| 8 | Garrett Wilson 6+ receptions | 58% | -137 | ✗ 4 | `+8` · 2026 3/5 pre-game

Legs 4/8 (expected 4.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Rhamondre Stevenson (NE RB) | 54% | -117 | ✗ no TD | share 18% · team 2.86 TD · RZ-D 1.09 · pos-D 1.38 |
| Romeo Doubs (NE WR) | 37% | +171 | ✓ TD | share 15% · team 2.86 TD · RZ-D 1.09 · pos-D 1.01 |
| Garrett Wilson (NYJ WR) | 30% | +238 | ✗ no TD | share 13% · team 2.02 TD · RZ-D 1.04 · pos-D 1.05 |
| Braelon Allen (NYJ RB) | 25% | +297 | ✗ no TD | share 11% · team 2.02 TD · RZ-D 1.04 · pos-D 0.92 |

TD double (Rhamondre Stevenson + Romeo Doubs): 24.4% · fair +310 ✗

**All-position slip** — 20.3% · fair +393 ✗: Geno Smith 25+ pass att ✓(30) · Rhamondre Stevenson 50+ rush yds ✗(36) · Garrett Wilson 60+ rec yds ✗(44) · Rhamondre Stevenson ANYTIME TD ✗(no TD)

**All-position 8-leg** — 5.3% · fair +1796 ✗: Geno Smith 25+ pass att ✓(30) · Rhamondre Stevenson 50+ rush yds ✗(36) · Garrett Wilson 60+ rec yds ✗(44) · Braelon Allen 30+ rush yds ✓(78) · Romeo Doubs 30+ rec yds ✓(42) · Rhamondre Stevenson ANYTIME TD ✗(no TD) · Romeo Doubs ANYTIME TD ✓(TD)


### PIT@TB — final 26-19
*O/U 38.5 · spread -1.5 · outdoor · grass · 13:00 ET*

**Personnel:** TB: Mayfield OUT — Jalon Daniels 3rd start. Winfield Jr. (S) OUT, Morrison (CB) doubtful. PIT: DeShon Elliott (S), Roman Wilson, Skowronek OUT; Ramsey, Dean, Dowdle, Freiermuth Q (singles only).

**Injury report (as built):** PIT DEF · DeShon Elliott (S) — Out · Knee; PIT OFF · Ben Skowronek (WR) — Out · Calf · DNP; PIT OFF · Roman Wilson (WR) — Out · Finger · DNP; PIT DEF · Jalen Ramsey (CB) — Questionable · Wrist; PIT DEF · Jamel Dean (CB) — Questionable · Ankle; PIT OFF · Rico Dowdle (RB) — Questionable · Toe; PIT OFF · Pat Freiermuth (TE) — Questionable · Calf; PIT DEF · Keeanu Benton (DT) — Questionable · Ankle

**Defensive leaks:** TB D leaks receiving yards to RBs: x1.38; TB D leaks receiving yards to TEs: x1.18; TB D leaks receptions to RBs: x1.15; PIT D leaks passing interceptions to QBs: x1.32

**Coordinators:** PIT OC Brian Angelichio — NEW (pass_te) · measured pass 63% | DC Patrick Graham (multiple) · TB OC Zac Robinson — NEW (pass_wr) · measured pass 53% | DC Todd Bowles (blitz_heavy)

**Props SGP** — 4-leg 16.9% · fair +493 **CASHED** · 6-leg 10.2% · fair +882 **CASHED** · 8-leg 5.6% · fair +1674 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Jaylen Warren 50+ rush yds | 62% | -164 | ✓ 50 | `4-leg core` · 2026 3/5 pre-game
| 2 | Emeka Egbuka 3+ receptions | 62% | -167 | ✓ 7 | `4-leg core` · 2026 4/5 pre-game
| 3 | Aaron Rodgers 35+ pass att | 61% | -159 | ✓ 49 | `4-leg core` · 2026 3/5 pre-game
| 4 | DK Metcalf 40+ rec yds | 63% | -168 | ✓ 93 | `4-leg core` · 2026 2/5 pre-game
| 5 | Germie Bernard 30+ rec yds | 61% | -157 | ✓ 87 | `+6` · 2026 2/4 pre-game
| 6 | Jalon Daniels 20+ pass att | 60% | -151 | ✓ 43 | `+6` · 2026 2/3 pre-game
| 7 | Cade Otton 4+ receptions | 60% | -150 | ✗ 1 | `+8` · 2026 2/5 pre-game
| 8 | Bucky Irving 15+ carries | 64% | -180 | ✓ 19 | `+8` · 2026 4/5 pre-game

Legs 7/8 (expected 4.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Jaylen Warren (PIT RB) | 28% | +251 | ✗ no TD | share 15% · team 2.24 TD · RZ-D 1.04 · pos-D 0.94 |
| Bucky Irving (TB RB) | 27% | +275 | ✗ no TD | share 18% · team 2.07 TD · RZ-D 0.93 · pos-D 0.85 |
| DK Metcalf (PIT WR) | 26% | +279 | ✗ no TD | share 14% · team 2.24 TD · RZ-D 1.04 · pos-D 0.97 |
| Emeka Egbuka (TB WR) | 25% | +303 | ✓ TD | share 16% · team 2.07 TD · RZ-D 0.93 · pos-D 0.99 |

TD double (Jaylen Warren + Bucky Irving): 9.3% · fair +980 ✗

**All-position slip** — 8.5% · fair +1079 ✗: Aaron Rodgers 35+ pass att ✓(49) · Jaylen Warren 50+ rush yds ✓(50) · Emeka Egbuka 3+ receptions ✓(7) · Cade Otton 4+ receptions ✗(1) · Jaylen Warren ANYTIME TD ✗(no TD)

**All-position 8-leg** — 2.6% · fair +3737 ✗: Aaron Rodgers 35+ pass att ✓(49) · Jaylen Warren 50+ rush yds ✓(50) · Emeka Egbuka 3+ receptions ✓(7) · Cade Otton 4+ receptions ✗(1) · Bucky Irving 15+ carries ✓(19) · DK Metcalf 40+ rec yds ✓(93) · Jaylen Warren ANYTIME TD ✗(no TD) · Bucky Irving ANYTIME TD ✗(no TD)


### TEN@IND — final 26-20
*O/U 43.5 · spread +6.5 · indoor · turf · 13:00 ET*

**Personnel:** TEN: Winston Jr. (S) OUT; Spears Q. IND: Dulin OUT; Tyler Warren Q — singles only.

**Injury report (as built):** IND OFF · Ashton Dulin (WR) — Out · Hamstring · DNP; IND DEF · Jaylon Carlies (LB) — Out · Ribs · DNP; IND OFF · Tyler Warren (TE) — Questionable · Groin; IND DEF · DeForest Buckner (DT) — nan · DNP; TEN DEF · Jordan Elliott (DT) — Out · Not injury related - personal matter · DNP; TEN DEF · Kevin Winston Jr. (S) — Out · Quadricep · DNP; TEN DEF · Joshua Williams (CB) — Questionable · Pectoral; TEN OFF · Tyjae Spears (RB) — Questionable · Knee

**Defensive leaks:** IND D leaks receiving yards to TEs: x1.19; IND D leaks receptions to TEs: x1.14; IND D leaks passing interceptions to QBs: x1.14

**Coordinators:** TEN OC Brian Daboll — NEW (pass_wr) · measured pass 59% | DC Gus Bradley (zone_cover3) · IND OC Jim Bob Cooter — continuity · measured pass 56% | DC Lou Anarumo (disguise_zone)

**Props SGP** — 4-leg 16.6% · fair +504 **CASHED** · 6-leg 8.5% · fair +1072 ✗ · 8-leg 5.1% · fair +1853 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Jonathan Taylor 70+ rush yds | 62% | -164 | ✓ 94 | `4-leg core` · 2026 3/5 pre-game
| 2 | Daniel Jones 200+ pass yds | 62% | -167 | ✓ 269 | `4-leg core` · 2026 3/5 pre-game
| 3 | Keenan Allen 40+ rec yds | 61% | -159 | ✓ 82 | `4-leg core` · 2026 2/4 pre-game
| 4 | Tony Pollard 60+ rush yds | 61% | -158 | ✓ 76 | `4-leg core` · 2026 2/5 pre-game
| 5 | Wan'Dale Robinson 50+ rec yds | 63% | -168 | ✗ 22 | `+6` · 2026 2/5 pre-game
| 6 | Cam Ward 200+ pass yds | 60% | -151 | ✗ 102 | `+6` · 2026 1/5 pre-game
| 7 | Josh Downs 4+ receptions | 59% | -145 | ✓ 4 | `+8` · 2026 2/5 pre-game
| 8 | Carnell Tate 5+ receptions | 55% | -123 | ✓ 6 | `+8` · 2026 2/5 pre-game

Legs 6/8 (expected 4.8)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Jonathan Taylor (IND RB) | 59% | -144 | ✓ TD | share 29% · team 2.8 TD · RZ-D 1.12 · pos-D 1.07 |
| Keenan Allen (IND WR) | 35% | +187 | ✗ no TD | share 13% · team 2.8 TD · RZ-D 1.12 · pos-D 1.08 |
| Tony Pollard (TEN RB) | 34% | +193 | ✗ no TD | share 19% · team 2.07 TD · RZ-D 0.97 · pos-D 1.04 |
| Wan'Dale Robinson (TEN WR) | 24% | +324 | ✗ no TD | share 13% · team 2.07 TD · RZ-D 0.97 · pos-D 1.01 |

TD double (Jonathan Taylor + Keenan Allen): 24.8% · fair +303 ✗

**All-position slip** — 19.0% · fair +426 **CASHED**: Daniel Jones 200+ pass yds ✓(269) · Jonathan Taylor 70+ rush yds ✓(94) · Keenan Allen 40+ rec yds ✓(82) · Jonathan Taylor ANYTIME TD ✓(TD)

**All-position 8-leg** — 6.1% · fair +1541 ✗: Daniel Jones 200+ pass yds ✓(269) · Jonathan Taylor 70+ rush yds ✓(94) · Keenan Allen 40+ rec yds ✓(82) · Tony Pollard 60+ rush yds ✓(76) · Wan'Dale Robinson 50+ rec yds ✗(22) · Jonathan Taylor ANYTIME TD ✓(TD) · Keenan Allen ANYTIME TD ✗(no TD)


### ARI@LA — final 18-16
*O/U 51.5 · spread +12.5 · indoor · turf · 16:05 ET*

**Personnel:** ARI: Jeremiyah Love OUT — Allgeier backfield; Wingard, W. Williams OUT; Budda Baker Q. LA: Curl, McDuffie Q. Dome.

**Injury report (as built):** ARI DEF · Andrew Wingard (S) — Out · Knee · DNP; ARI OFF · Jeremiyah Love (RB) — Out · Ankle · DNP; ARI DEF · Wydett Williams Jr. (S) — Out · Concussion · DNP; ARI DEF · Budda Baker (S) — Questionable · Not injury related - resting player · DNP; ARI OFF · Blake Gillikin (P) — Questionable · Back; ARI DEF · Zaven Collins (LB) — Questionable · Hip · DNP; ARI DEF · Kitan Crawford (S) — Questionable · Ankle; LA DEF · Kam Curl (S) — Questionable · Ankle · DNP

**Defensive leaks:** LA D leaks passing interceptions to QBs: x1.21; LA D leaks receiving yards to RBs: x1.15 (worsening x1.56 L4); ARI D leaks rushing yards to RBs: x1.16; ARI D leaks receiving yards to TEs: x1.10 (worsening x1.49 L4)

**Coordinators:** ARI OC Nathaniel Hackett — NEW (run_heavy) · measured pass 62% | DC Nick Rallis (blitz_heavy) · LA OC Nathan Scheelhaase — NEW (pass_wr) · measured pass 63% | DC Chris Shula (four_man_rush)

**Props SGP** — 4-leg 17.2% · fair +482 ✗ · 6-leg 9.6% · fair +937 ✗ · 8-leg 5.8% · fair +1620 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Michael Wilson 40+ rec yds | 62% | -164 | ✗ 32 | `4-leg core` · 2026 3/5 pre-game
| 2 | Kendrick Bourne 3+ receptions | 62% | -160 | ✓ 5 | `4-leg core` · 2026 2/4 pre-game
| 3 | Tyler Allgeier 30+ rush yds | 63% | -167 | ✓ 38 | `4-leg core` · 2026 2/5 pre-game
| 4 | Matthew Stafford 300+ pass yds | 63% | -168 | ✗ 222 | `4-leg core` · 2026 4/5 pre-game
| 5 | Jacoby Brissett o0.5 INT o0.5 | 61% | -155 | ✓ 1 INT | `+6` · 2026 3/5 pre-game
| 6 | Kyren Williams 80+ rush yds | 61% | -154 | ✗ 50 | `+6` · 2026 3/5 pre-game
| 7 | Davante Adams 60+ rec yds | 60% | -152 | ✗ 39 | `+8` · 2026 2/5 pre-game
| 8 | Tyler Higbee 3+ receptions | 60% | -150 | ✓ 4 | `+8` · 2026 3/4 pre-game

Legs 4/8 (expected 4.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Kyren Williams (LA RB) | 70% | -229 | ✗ no TD | share 25% · team 3.58 TD · RZ-D 1.15 · pos-D 1.14 |
| Davante Adams (LA WR) | 66% | -199 | ✗ no TD | share 26% · team 3.58 TD · RZ-D 1.15 · pos-D 1.11 |
| Puka Nacua (LA WR) | 44% | +127 | ✗ no TD | share 14% · team 3.58 TD · RZ-D 1.15 · pos-D 1.11 |
| Trey McBride (ARI TE) | 34% | +190 | ✗ no TD | share 19% · team 2.18 TD · RZ-D 0.91 · pos-D 0.95 |

TD double (Kyren Williams + Davante Adams): 50.4% · fair -101 ✗

**All-position slip** — 16.0% · fair +524 ✗: Matthew Stafford 300+ pass yds ✗(222) · Tyler Allgeier 30+ rush yds ✓(38) · Michael Wilson 40+ rec yds ✗(32) · Tyler Higbee 3+ receptions ✓(4) · Kyren Williams ANYTIME TD ✗(no TD)

**All-position 8-leg** — 6.8% · fair +1361 ✗: Matthew Stafford 300+ pass yds ✗(222) · Tyler Allgeier 30+ rush yds ✓(38) · Michael Wilson 40+ rec yds ✗(32) · Tyler Higbee 3+ receptions ✓(4) · Kyren Williams 80+ rush yds ✗(50) · Kendrick Bourne 3+ receptions ✓(5) · Kyren Williams ANYTIME TD ✗(no TD) · Davante Adams ANYTIME TD ✗(no TD)


### BUF@LV — final 33-30
*O/U 53.5 · spread -5.5 · indoor · grass · 16:25 ET*

**Personnel:** BUF: DJ Moore, Palmer Q — singles only; Oliver Q. LV: Thornton (WR), Runyon (TE), Hemingway OUT. Dome.

**Injury report (as built):** BUF OFF · DJ Moore (WR) — Questionable · Shoulder; BUF DEF · Ed Oliver (DE) — Questionable · Knee; BUF OFF · Josh Palmer (WR) — Questionable · Shoulder; BUF DEF · Dee Alford (CB) — Questionable · Ankle; BUF DEF · T.J. Sanders (DE) — Questionable · Shoulder; LV DEF · Tonka Hemingway (DT) — Out · Concussion · DNP; LV OFF · Carter Runyon (TE) — Out · Foot; LV OFF · Dont'e Thornton Jr. (WR) — Out · Hamstring

**Defensive leaks:** BUF D leaks receiving yards to RBs: x1.13 (worsening x1.09 L4); BUF D leaks receptions to RBs: x1.12 (worsening x1.12 L4); BUF D leaks passing interceptions to QBs: x1.10

**Coordinators:** BUF OC Pete Carmichael Jr. — NEW (balanced) · measured pass 48% | DC Jim Leonhard (disguise_zone) · LV OC Andrew Janocko — NEW (run_heavy) · measured pass 57% | DC Rob Leonard (four_man_rush)

**Props SGP** — 4-leg 16.9% · fair +493 ✗ · 6-leg 9.8% · fair +925 ✗ · 8-leg 6.0% · fair +1560 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | James Cook 100+ rush yds | 61% | -156 | ✗ 95 | `4-leg core` · 2026 3/5 pre-game
| 2 | Tre Tucker 4+ receptions | 63% | -171 | ✓ 5 | `4-leg core` · 2026 4/5 pre-game
| 3 | Brock Bowers 60+ rec yds | 61% | -156 | ✓ 70 | `4-leg core` · 2026 3/3 pre-game
| 4 | Ashton Jeanty 60+ rush yds | 63% | -172 | ✗ 22 | `4-leg core` · 2026 1/5 pre-game
| 5 | Michael Mayer 4+ receptions | 60% | -150 | ✓ 7 | `+6` · 2026 2/5 pre-game
| 6 | Josh Allen o0.5 INT o0.5 | 59% | -146 | ✗ 0 INT | `+6` · 2026 3/5 pre-game
| 7 | Khalil Shakir 50+ rec yds | 58% | -138 | ✗ 34 | `+8` · 2026 3/5 pre-game
| 8 | Kirk Cousins 30+ pass att | 68% | -210 | ✓ 41 | `+8` · 2026 3/5 pre-game

Legs 4/8 (expected 4.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Josh Allen (BUF QB) | 59% | -144 | ✗ no TD | share 18% · team 3.3 TD · RZ-D 1.06 · pos-D 1.41 |
| Ashton Jeanty (LV RB) | 56% | -126 | ✓ TD | share 25% · team 2.69 TD · RZ-D 1.11 · pos-D 1.22 |
| James Cook (BUF RB) | 53% | -111 | ✓ TD | share 22% · team 3.3 TD · RZ-D 1.06 · pos-D 1.04 |
| Brock Bowers (LV TE) | 42% | +138 | ✗ no TD | share 24% · team 2.69 TD · RZ-D 1.11 · pos-D 0.82 |

TD double (Josh Allen + Ashton Jeanty): 35.1% · fair +185 ✗

**All-position slip** — 17.0% · fair +490 ✗: Josh Allen 40+ rush yds ✗(1) · James Cook 100+ rush yds ✗(95) · Tre Tucker 4+ receptions ✓(5) · Brock Bowers 60+ rec yds ✓(70) · Josh Allen ANYTIME TD ✗(no TD)

**All-position 8-leg** — 6.7% · fair +1404 ✗: Josh Allen 40+ rush yds ✗(1) · James Cook 100+ rush yds ✗(95) · Tre Tucker 4+ receptions ✓(5) · Brock Bowers 60+ rec yds ✓(70) · Ashton Jeanty 30+ rec yds ✓(36) · Khalil Shakir 4+ receptions ✓(4) · Josh Allen ANYTIME TD ✗(no TD) · Ashton Jeanty ANYTIME TD ✓(TD)


### LAC@KC — final 6-22
*O/U 41.5 · spread +7.5 · outdoor · grass · 16:25 ET*

**Personnel:** LAC: Tre Harris OUT; Derwin James, D. Jackson, Alt, Awosika OUT; Shelley doubtful; KLS Q. KC: Rashee Rice OUT; Simmons (T) OUT; Sneed Q.

**Injury report (as built):** KC OFF · Rashee Rice (WR) — Out · Hamstring · DNP; KC OFF · Josh Simmons (T) — Out · Back; KC DEF · L'Jarius Sneed (CB) — Questionable · Knee; LAC DEF · Rodney Shelley (CB) — Doubtful · Hamstring · DNP; LAC DEF · Donte Jackson (CB) — Out · Hamstring · DNP; LAC DEF · Derwin James (S) — Out · Hamstring · DNP; LAC OFF · Kayode Awosika (G) — Out · Fibula · DNP; LAC OFF · Joe Alt (T) — Out · Neck · DNP

**Defensive leaks:** KC D leaks receiving yards to TEs: x1.17 (worsening x2.09 L4); KC D leaks receptions to TEs: x1.11 (worsening x1.81 L4); LAC D leaks passing interceptions to QBs: x1.39

**Coordinators:** LAC OC Mike McDaniel — NEW (pass_rb) · measured pass 49% | DC Chris O'Leary (two_high_shell) · KC OC Eric Bieniemy — NEW (pass_wr) · measured pass 52% | DC Steve Spagnuolo (blitz_heavy)

**Props SGP** — 4-leg 21.3% · fair +370 **CASHED** · 6-leg 12.5% · fair +700 ✗ · 8-leg 6.3% · fair +1477 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Quentin Johnston 40+ rec yds | 62% | -162 | ✓ 57 | `4-leg core` · 2026 2/4 pre-game
| 2 | Justin Herbert o0.5 INT o0.5 | 62% | -165 | ✓ 1 INT | `4-leg core` · 2026 5/5 pre-game
| 3 | Patrick Mahomes o0.5 INT o0.5 | 61% | -159 | ✓ 1 INT | `4-leg core` · 2026 2/4 pre-game
| 4 | Travis Kelce 50+ rec yds | 61% | -158 | ✓ 53 | `4-leg core` · 2026 3/4 pre-game
| 5 | Ladd McConkey 3+ receptions | 61% | -158 | ✗ 1 | `+6` · 2026 3/4 pre-game
| 6 | Kenneth Walker III 15+ carries | 66% | -195 | ✓ 19 | `+6` · 2026 4/4 pre-game
| 7 | Omarion Hampton 40+ rush yds | 57% | -132 | ✗ 18 | `+8` · 2026 4/5 pre-game
| 8 | Patrick Mahomes 30+ pass att | 64% | -175 | ✓ 30 | `+8` · 2026 2/4 pre-game

Legs 6/8 (expected 4.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Kenneth Walker III (KC RB) | 42% | +137 | ✓ TD | share 21% · team 2.74 TD · RZ-D 0.9 · pos-D 0.96 |
| Omarion Hampton (LAC RB) | 28% | +254 | ✗ no TD | share 21% · team 1.9 TD · RZ-D 0.92 · pos-D 0.9 |
| Xavier Worthy (KC WR) | 24% | +310 | ✗ no TD | share 10% · team 2.74 TD · RZ-D 0.9 · pos-D 0.95 |
| Travis Kelce (KC TE) | 22% | +344 | ✗ no TD | share 9% · team 2.74 TD · RZ-D 0.9 · pos-D 0.91 |

TD double (Kenneth Walker III + Omarion Hampton): 13.8% · fair +624 ✗

**All-position slip** — 12.2% · fair +717 **CASHED**: Patrick Mahomes 30+ pass att ✓(30) · Kenneth Walker III 15+ carries ✓(19) · Quentin Johnston 40+ rec yds ✓(57) · Travis Kelce 50+ rec yds ✓(53) · Kenneth Walker III ANYTIME TD ✓(TD)

**All-position 8-leg** — 3.3% · fair +2906 ✗: Patrick Mahomes 30+ pass att ✓(30) · Kenneth Walker III 15+ carries ✓(19) · Quentin Johnston 40+ rec yds ✓(57) · Travis Kelce 50+ rec yds ✓(53) · Omarion Hampton 40+ rush yds ✗(18) · Ladd McConkey 3+ receptions ✗(1) · Kenneth Walker III ANYTIME TD ✓(TD) · Omarion Hampton ANYTIME TD ✗(no TD)


### DAL@GB — final 13-23
*O/U 53.5 · spread +1.5 · outdoor · grass · 20:20 ET*

**Personnel:** DAL: Durant (CB), Shelton (T) OUT; Porter Jr., Overshown Q. GB: Hargrave (DT), St-Juste (CB), Skyy Moore OUT; Banks, Monk Q. Outdoor grass, night.

**Injury report (as built):** DAL DEF · Cobie Durant (CB) — Out · Hamstring · DNP; DAL OFF · Drew Shelton (T) — Out · Hamstring · DNP; DAL DEF · DeMarvion Overshown (LB) — Questionable · Hamstring; DAL DEF · Ameer Speed (CB) — Questionable · Knee; DAL DEF · Joey Porter Jr. (CB) — Questionable · Ankle; DAL DEF · LT Overton (DT) — Questionable · Foot · DNP; DAL DEF · Von Miller (LB) — nan · DNP; GB DEF · Jordon Riley (DE) — Doubtful · Achilles

**Defensive leaks:** GB D leaks receptions to RBs: x1.11; GB D leaks passing interceptions to QBs: x1.10 (worsening x2.60 L4); DAL D leaks receiving yards to RBs: x1.21; DAL D leaks receiving yards to WRs: x1.13 (worsening x1.11 L4)

**Coordinators:** DAL OC Klayton Adams — continuity · measured pass 64% | DC Christian Parker (two_high_shell) · GB OC Adam Stenavich — continuity · measured pass 65% | DC Jonathan Gannon (two_high_shell)

**Props SGP** — 4-leg 25.4% · fair +294 ✗ · 6-leg 14.0% · fair +616 ✗ · 8-leg 8.8% · fair +1031 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Dak Prescott 200+ pass yds | 62% | -161 | ✓ 258 | `4-leg core` · 2026 4/5 pre-game
| 2 | CeeDee Lamb 70+ rec yds | 62% | -166 | ✓ 70 | `4-leg core` · 2026 3/5 pre-game
| 3 | George Pickens 50+ rec yds | 61% | -157 | ✓ 73 | `4-leg core` · 2026 3/5 pre-game
| 4 | MarShawn Lloyd 30+ rush yds | 64% | -176 | ✗ 10 | `4-leg core` · 2026 2/5 pre-game
| 5 | Javonte Williams 3+ receptions | 60% | -151 | ✗ 2 | `+6` · 2026 3/5 pre-game
| 6 | Christian Watson 4+ receptions | 65% | -183 | ✗ 3 | `+6` · 2026 4/5 pre-game
| 7 | Jordan Love 275+ pass yds | 58% | -139 | ✓ 276 | `+8` · 2026 3/5 pre-game
| 8 | Dak Prescott 30+ pass att | 64% | -180 | ✓ 54 | `+8` · 2026 5/5 pre-game

Legs 5/8 (expected 5.0)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Javonte Williams (DAL RB) | 51% | -105 | ✓ TD | share 23% · team 2.91 TD · RZ-D 1.05 · pos-D 1.03 |
| Christian Watson (GB WR) | 49% | +104 | ✗ no TD | share 17% · team 3.08 TD · RZ-D 1.1 · pos-D 1.22 |
| George Pickens (DAL WR) | 39% | +157 | ✗ no TD | share 16% · team 2.91 TD · RZ-D 1.05 · pos-D 1.02 |
| MarShawn Lloyd (GB RB) | 38% | +162 | ✗ no TD | share 13% · team 3.08 TD · RZ-D 1.1 · pos-D 1.1 |

TD double (Javonte Williams + Christian Watson): 27.2% · fair +267 ✗

**All-position slip** — 12.7% · fair +685 ✗: Dak Prescott 200+ pass yds ✓(258) · MarShawn Lloyd 30+ rush yds ✗(10) · CeeDee Lamb 70+ rec yds ✓(70) · Tucker Kraft 40+ rec yds ✗(37) · Javonte Williams ANYTIME TD ✓(TD)

**All-position 8-leg** — 7.1% · fair +1316 ✗: Dak Prescott 200+ pass yds ✓(258) · MarShawn Lloyd 30+ rush yds ✗(10) · CeeDee Lamb 70+ rec yds ✓(70) · Tucker Kraft 40+ rec yds ✗(37) · Javonte Williams 3+ receptions ✗(2) · George Pickens 4+ receptions ✓(6) · Javonte Williams ANYTIME TD ✓(TD) · Christian Watson ANYTIME TD ✗(no TD)


### Cross-game combos — Week 6 — aggressive band (shipped)

**4-leg** — 15.0% · fair +568 — 2/4 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | NO@NYG | Devaughn Vele 5+ receptions | 62% | ✗ 3 |
| 2 | PIT@TB | Jaylen Warren 50+ rush yds | 62% | ✓ 50 |
| 3 | LAC@KC | Quentin Johnston 40+ rec yds | 62% | ✓ 57 |
| 4 | CHI@ATL | Kalif Raymond 20+ rec yds | 62% | ✗ 18 |

**6-leg** — 5.9% · fair +1587 — 4/6 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | NO@NYG | Devaughn Vele 5+ receptions | 62% | ✗ 3 |
| 2 | PIT@TB | Jaylen Warren 50+ rush yds | 62% | ✓ 50 |
| 3 | LAC@KC | Quentin Johnston 40+ rec yds | 62% | ✓ 57 |
| 4 | CHI@ATL | Kalif Raymond 20+ rec yds | 62% | ✗ 18 |
| 5 | TEN@IND | Jonathan Taylor 70+ rush yds | 62% | ✓ 94 |
| 6 | NO@NYG | Jameis Winston 20+ pass att | 62% | ✓ 26 |

**8-leg** — 2.6% · fair +3723 — 6/8 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | NO@NYG | Devaughn Vele 5+ receptions | 62% | ✗ 3 |
| 2 | PIT@TB | Jaylen Warren 50+ rush yds | 62% | ✓ 50 |
| 3 | LAC@KC | Quentin Johnston 40+ rec yds | 62% | ✓ 57 |
| 4 | CHI@ATL | Kalif Raymond 20+ rec yds | 62% | ✗ 18 |
| 5 | TEN@IND | Jonathan Taylor 70+ rush yds | 62% | ✓ 94 |
| 6 | NO@NYG | Jameis Winston 20+ pass att | 62% | ✓ 26 |
| 7 | LAC@KC | Justin Herbert o0.5 INT o0.5 | 62% | ✓ 1 INT |
| 8 | DAL@GB | Dak Prescott 200+ pass yds | 62% | ✓ 258 |

**10-leg** — 0.9% · fair +10538 — 7/10 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | NO@NYG | Devaughn Vele 5+ receptions | 62% | ✗ 3 |
| 2 | PIT@TB | Jaylen Warren 50+ rush yds | 62% | ✓ 50 |
| 3 | LAC@KC | Quentin Johnston 40+ rec yds | 62% | ✓ 57 |
| 4 | CHI@ATL | Kalif Raymond 20+ rec yds | 62% | ✗ 18 |
| 5 | TEN@IND | Jonathan Taylor 70+ rush yds | 62% | ✓ 94 |
| 6 | NO@NYG | Jameis Winston 20+ pass att | 62% | ✓ 26 |
| 7 | ARI@LA | Michael Wilson 40+ rec yds | 62% | ✗ 32 |
| 8 | LAC@KC | Justin Herbert o0.5 INT o0.5 | 62% | ✓ 1 INT |
| 9 | DAL@GB | Dak Prescott 200+ pass yds | 62% | ✓ 258 |
| 10 | TEN@IND | Daniel Jones 200+ pass yds | 62% | ✓ 269 |

**12-leg** — 0.4% · fair +22271 — 9/12 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | NO@NYG | Devaughn Vele 5+ receptions | 62% | ✗ 3 |
| 2 | PIT@TB | Jaylen Warren 50+ rush yds | 62% | ✓ 50 |
| 3 | LAC@KC | Quentin Johnston 40+ rec yds | 62% | ✓ 57 |
| 4 | CHI@ATL | Kalif Raymond 20+ rec yds | 62% | ✗ 18 |
| 5 | TEN@IND | Jonathan Taylor 70+ rush yds | 62% | ✓ 94 |
| 6 | NO@NYG | Jameis Winston 20+ pass att | 62% | ✓ 26 |
| 7 | ARI@LA | Michael Wilson 40+ rec yds | 62% | ✗ 32 |
| 8 | LAC@KC | Justin Herbert o0.5 INT o0.5 | 62% | ✓ 1 INT |
| 9 | DAL@GB | Dak Prescott 200+ pass yds | 62% | ✓ 258 |
| 10 | DAL@GB | CeeDee Lamb 70+ rec yds | 62% | ✓ 70 |
| 11 | TEN@IND | Daniel Jones 200+ pass yds | 62% | ✓ 269 |
| 12 | PIT@TB | Emeka Egbuka 3+ receptions | 62% | ✓ 7 |


### ATD board (top 16) — Week 6 — aggressive band (shipped)

| # | Game | Player | Model | Fair | Result |
|---|---|---|---|---|---|
| 1 | ARI@LA | Kyren Williams (RB) | 70% | -229 | ✗ no TD |
| 2 | ARI@LA | Davante Adams (WR) | 66% | -199 | ✗ no TD |
| 3 | TEN@IND | Jonathan Taylor (RB) | 59% | -144 | ✓ TD |
| 4 | BUF@LV | Josh Allen (QB) | 59% | -144 | ✗ no TD |
| 5 | BUF@LV | Ashton Jeanty (RB) | 56% | -126 | ✓ TD |
| 6 | NYJ@NE | Rhamondre Stevenson (RB) | 54% | -117 | ✗ no TD |
| 7 | BUF@LV | James Cook (RB) | 53% | -111 | ✓ TD |
| 8 | DAL@GB | Javonte Williams (RB) | 51% | -105 | ✓ TD |
| 9 | BAL@CLE | Derrick Henry (RB) | 50% | -102 | ✗ no TD |
| 10 | CHI@ATL | Bijan Robinson (RB) | 50% | +102 | ✗ no TD |
| 11 | DAL@GB | Christian Watson (WR) | 49% | +104 | ✗ no TD |
| 12 | CHI@ATL | D'Andre Swift (RB) | 48% | +107 | ✓ TD |
| 13 | NO@NYG | Malik Nabers (WR) | 44% | +125 | ✗ no TD |
| 14 | ARI@LA | Puka Nacua (WR) | 44% | +127 | ✗ no TD |
| 15 | CHI@ATL | Drake London (WR) | 44% | +130 | ✗ no TD |
| 16 | LAC@KC | Kenneth Walker III (RB) | 42% | +137 | ✓ TD |

Board: top-16 6/16 · top-8 4/8 · chalk triple 1/3

**2+ TD board (singles only):** Kyren Williams 33% (+200) · Davante Adams 30% (+235) · Jonathan Taylor 22% (+346) · Josh Allen 22% (+347) · Ashton Jeanty 20% (+406) · Rhamondre Stevenson 18% (+448)


### Scorecard — Week 6 — aggressive band (shipped)

**Legs 50/85 = 59% actual vs 63% expected · SGP4 3/11 · SGP6 1/11 · SGP8 0/11**

| Game | Final | Legs | SGP4 | SGP6 | SGP8 |
|---|---|---|---|---|---|
| PIT@TB | 26-19 | 7/8 | ✓ | ✓ | ✗ |
| TEN@IND | 26-20 | 6/8 | ✓ | ✗ | ✗ |
| LAC@KC | 6-22 | 6/8 | ✓ | ✗ | ✗ |
| CAR@PHI | 25-14 | 5/7 | ✗ | ✗ | ✗ |
| DAL@GB | 13-23 | 5/8 | ✗ | ✗ | ✗ |
| NO@NYG | 34-27 | 4/7 | ✗ | ✗ | ✗ |
| NYJ@NE | 19-26 | 4/8 | ✗ | ✗ | ✗ |
| ARI@LA | 18-16 | 4/8 | ✗ | ✗ | ✗ |
| BUF@LV | 33-30 | 4/8 | ✗ | ✗ | ✗ |
| BAL@CLE | 10-13 | 3/8 | ✗ | ✗ | ✗ |
| CHI@ATL | 31-23 | 2/7 | ✗ | ✗ | ✗ |


## Week 6 TNF — SEA @ DEN (Oct 15 2026)

*Engine v1.9d/e (first live run of the rung gate, backfield trend, env cap and WR/TE weighting) · O/U 40.5 · spread -2.5 · Empower Field at Mile High · outdoor/grass · final 14-17*

**Personnel:** DEN OUT: Pat Surtain II (CB1, ankle), Talanoa Hufanga (S, ankle). Riley Moss (CB) QUESTIONABLE — ribs, limited all week, expected to play hurt. Pat Bryant (WR) and Jonah Coleman (RB) on IR; Jonathan Cooper (EDGE) suspended. Powers, B. Jones, Sai'vion Jones cleared. SEA OUT: Drake Thomas (LB, ankle) and Chazz Surratt (LB, calf) — Tyrice Knight steps in; Charbonnet still out. JSN (ankle) full participant, no status — plays. Holani, Stephens cleared. Darnold starts (Lock limited, forearm). Weather: clear-ish, 12C at sunset falling toward 1C by the 4th quarter, 30% rain chance, altitude.

**What the engine did with it:** SEA WRs x1.08 (no Surtain; Moss hurt), SEA TE x1.12 (Hufanga out — the safety covers the tight end; DEN has allowed 63 yds/g to TEs this year). Darnold pass yds x1.06. DEN TE/RB receiving x1.06 (two SEA linebackers out). Cold-night x0.97 on passing yardage. ENGINE FIX v1.9e shipped on this run: the ATD model weighted inside-10 carries at 35% for every position, which priced JSN — 60% of Seattle's end-zone targets and 41% of its touchdowns — at a 16% opportunity share. WR/TE now weight end-zone targets at 35%: JSN 24% -> 33%. And with two starting DBs out, Denver's season TD-defence factors are regressed halfway to league average instead of being taken at face value.

**The read:** Lowest total of the week (40.5), Seattle a short road favourite: Denver implied 2.1 TDs, Seattle 2.4. The props edge is volume: Nix 25+ attempts is 5/5 this year, Dobbins has become the Denver backfield (17-11-18 carries), JSN averages 117 yards with 4/5 games over 90. The TD edge is JSN — 7 of Seattle's 17 touchdowns, 11 of its 21 red-zone targets, 6 of 10 end-zone targets — now the top of the board at 33%. Barner is Seattle's second red-zone target (5 RZ targets, 2 end-zone) but projects 2.7 catches and 30 yards; his legs live in the aggressive band, not the floor.

**ATD note:** JSN 33% (+200) is the only TD on the slate with a case. The book will post him near +120, which is still shorter than the model — no edge as a single, but he is the right TD leg inside a slip, where the copula credits his 90+ yards. Barner 21% (+385): two end-zone targets this year, 6 TDs in 2025; a +400 single is fair, not value. Sutton 32% is a weighting artefact to watch — half of Denver's end-zone targets, one TD.

**Slip note:** No TE leg qualifies for the floor: Barner projects 2.7 receptions (2.4/g this year), under the engine's 2.8 role floor; his 2+ receptions prices at 68% and 20+ yards at 64% — aggressive-band singles, and the better swap for Waddle 4+ rec (57%) in the aggressive 6-leg if you want him on a ticket. Harvey 2+ rec: 0 catches last week as Dobbins took 18 carries — first leg to drop. Dobbins 40+ is prior-heavy; 10+ carries (86%) is the sturdier version.

**FLOOR SGP** — 4-leg 44.1% · fair +127 **CASHED** · 6-leg 30.0% · fair +233 **CASHED** · 8-leg 20.7% · fair +384 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | RJ Harvey 2+ receptions | 78% | -353 | ✓ 3 | `4-leg core`
| 2 | Courtland Sutton 2+ receptions | 79% | -367 | ✓ 2 | `4-leg core`
| 3 | Bo Nix 25+ pass att | 80% | -414 | ✓ 27 | `4-leg core`
| 4 | J.K. Dobbins 40+ rush yds | 81% | -429 | ✓ 41 | `4-leg core`
| 5 | Emanuel Wilson 20+ rush yds | 75% | -296 | ✓ 52 | `+6`
| 6 | Jaylen Waddle 20+ rec yds | 73% | -273 | ✓ 24 | `+6`
| 7 | Jaxon Smith-Njigba 90+ rec yds | 73% | -270 | ✓ 134 | `+8`
| 8 | Bo Nix 150+ pass yds | 74% | -278 | ✗ 107 | `+8`

Legs 7/8

**AGGRESSIVE SGP** — 4-leg 18.5% · fair +439 ✗ · 6-leg 11.0% · fair +811 ✗ · 8-leg 5.3% · fair +1777 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Sam Darnold 150+ pass yds | 62% | -164 | ✓ 278 | `4-leg core`
| 2 | Bo Nix 30+ pass att | 62% | -162 | ✗ 27 | `4-leg core`
| 3 | Emanuel Wilson 10+ carries | 62% | -160 | ✓ 14 | `4-leg core`
| 4 | Courtland Sutton 30+ rec yds | 61% | -155 | ✗ 19 | `4-leg core`
| 5 | Jaxon Smith-Njigba 100+ rec yds | 64% | -178 | ✓ 134 | `+6`
| 6 | Jaylen Waddle 4+ receptions | 57% | -135 | ✓ 4 | `+6`
| 7 | RJ Harvey 3+ receptions | 67% | -204 | ✓ 3 | `+8`
| 8 | J.K. Dobbins 60+ rush yds | 56% | -128 | ✗ 41 | `+8`

Legs 5/8

**Anytime TD**

| Player | Model | Fair | 2+ TDs | Result | Decomposition |
|---|---|---|---|---|---|
| Jaxon Smith-Njigba (SEA WR) | 33% | +200 | 6% (+1481) | ✗ no TD | share 21% · team 2.41 TD · RZ-D 0.88 · pos-D 0.86 |
| Courtland Sutton (DEN WR) | 32% | +214 | 6% (+1653) | ✗ no TD | share 20% · team 2.13 TD · RZ-D 0.94 · pos-D 0.93 |
| J.K. Dobbins (DEN RB) | 26% | +291 | 4% (+2678) | ✓ TD | share 17% · team 2.13 TD · RZ-D 0.94 · pos-D 0.78 |
| Emanuel Wilson (SEA RB) | 25% | +307 | 3% (+2925) | ✗ no TD | share 12% · team 2.41 TD · RZ-D 0.88 · pos-D 1.0 |
| RJ Harvey (DEN RB) | 21% | +373 | 2% (+4043) | ✓ TD | share 14% · team 2.13 TD · RZ-D 0.94 · pos-D 0.78 |
| AJ Barner (SEA TE) | 21% | +385 | 2% (+4268) | ✗ no TD | share 10% · team 2.41 TD · RZ-D 0.88 · pos-D 0.98 |
| Jaylen Waddle (DEN WR) | 18% | +462 | 2% (+5826) | ✗ no TD | share 10% · team 2.13 TD · RZ-D 0.94 · pos-D 0.93 |

TD double: 12.4% · fair +704 · triple: 5.2% · fair +1815

**All-position slip** — 21.9% · fair +357 ✗: Bo Nix 25+ pass att ✓(27) · RJ Harvey 2+ receptions ✓(3) · Courtland Sutton 2+ receptions ✓(2) · Jaxon Smith-Njigba ANYTIME TD ✗(no TD)

**All-position 8-leg** — 7.9% · fair +1161 ✗: Bo Nix 25+ pass att ✓(27) · RJ Harvey 2+ receptions ✓(3) · Courtland Sutton 2+ receptions ✓(2) · J.K. Dobbins 40+ rush yds ✓(41) · Jaylen Waddle 20+ rec yds ✓(24) · Jaxon Smith-Njigba ANYTIME TD ✗(no TD) · Courtland Sutton ANYTIME TD ✗(no TD)

*Gated (not eligible for tickets):* Jadarian Price (SEA) OUT, George Holani (SEA) role, Cooper Kupp (SEA) role, Tory Horton (SEA) role, Eric Saubert (SEA) role, Jonah Coleman (DEN) OUT, Pat Bryant (DEN) OUT, Troy Franklin (DEN) role, Evan Engram (DEN) role, Nate Adkins (DEN) role

*Grade: floor 7/8 — 4-leg ✓ (+127) and 6-leg ✓ (+233) cashed; aggressive 5/8; all-position 5-leg 3/4 (JSN ATD missed, Dobbins and Harvey scored). The user's JSN 'TD menace' call exposed the WR weighting bug (fixed in v1.9e) even though JSN did not score that night; Barner's 'big day' did not arrive (3-20).*


## Week 6 SNF — DAL @ GB (Oct 18 2026)

*Engine v1.9f (first SNF card on the calibration layer) · O/U 53.5 · spread +1.5 · Lambeau Field · outdoor/grass · final 13-23*

**Personnel:** DAL INACTIVE: DeMarvion Overshown (LB), Cobie Durant (CB), Alijah Clark (S), Drew Shelton (T), Emari Demercado (RB), James Houston, Camden Brown. Joey Porter Jr. (Q all week) is ACTIVE; Ameer Speed, LT Overton active. GB INACTIVE: Aaron Banks (LG), Benjamin St-Juste (CB), Burton, Jennings; Javon Hargrave (DT) and Skyy Moore out — four active DTs. Brandon Cisse ACTIVE on a hip, starting opposite Nixon. Jacob Monk back as a backup; Savion Williams makes his debut (returns). Josh Jacobs remains on the exempt list — Lloyd / Kaleb Johnson committee. Lambeau: clear, 15C at kick cooling to ~8C, no wind issue.

**What the engine did with it:** First SNF card on v1.9f: calibration layer live (rush yds SD x1.25, rec yds x1.20 / TE x1.30, RB receptions x1.30; attempts tightened x0.90) plus the high-rung gate — which is why Lamb sits at 40+ not 60+, Javonte at 20+ rush, Pickens at 20+. Personnel: GB passing x1.04 (Durant + Clark out, Porter on a Q week), GB RB/TE receiving x1.03 (Overshown out); DAL passing x1.03 (St-Juste out, Cisse hurt), DAL rushing x1.04 (Hargrave out, thin DT rotation); Love x0.98 for the LG swap. Both defences' TD factors regressed 30% toward average for the DB absences.

**The read:** Highest total on the Sunday card (53.5), pick 'em at Lambeau. Both quarterbacks are volume machines — Love 37 attempts and 282 yards a game, Dak 38 and 276 — and the game-script layer barely touches either side at a 1.5 spread. The TD board is the story: Javonte has six rushing scores in five games on a 23% red-zone share and Green Bay is down Hargrave inside; Christian Watson has six receiving touchdowns and draws a Dallas secondary missing Durant and Clark. Lloyd at 38% is the committee back in a 3.1-TD offence — the price, not the player.

**ATD note:** Javonte 52% (-111) and Watson 49% (+104) are both chalk you can hold at plus money; the double prices at 27.9%, fair +258. Pickens 39% / Lamb 38% / Lloyd 38% are the second tier — Lloyd only at +200 or longer given the committee. Kraft and Ferguson (25-27%) are singles at +300 or better, not ticket legs.

**Slip note:** All-position 5-leg is Love 30+ att · Javonte 20+ rush · Golden 2+ rec · Kraft 3+ rec · Javonte ATD at 28.1%, fair +256. Dak 175+ at 71% looks cheap — he has cleared it 5/5 and 275+ 4/5 — but the model docks him for outdoor-grass splits and Green Bay's pass defence; the aggressive band carries him at 200+ (59%). Lamb's floor leg is 40+ (4/5), not the 60+ he had last week before the 9-yard game.

**FLOOR SGP** — 4-leg 46.2% · fair +116 **CASHED** · 6-leg 27.6% · fair +262 **CASHED** · 8-leg 20.6% · fair +386 **CASHED**

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Matthew Golden 2+ receptions | 78% | -344 | ✓ 6 | `4-leg core`
| 2 | Tucker Kraft 3+ receptions | 79% | -377 | ✓ 5 | `4-leg core`
| 3 | Jordan Love 30+ pass att | 80% | -401 | ✓ 41 | `4-leg core`
| 4 | Javonte Williams 20+ rush yds | 75% | -302 | ✓ 41 | `4-leg core`
| 5 | George Pickens 20+ rec yds | 75% | -297 | ✓ 73 | `+6`
| 6 | CeeDee Lamb 40+ rec yds | 73% | -270 | ✓ 70 | `+6`
| 7 | Dak Prescott 175+ pass yds | 71% | -249 | ✓ 258 | `+8`
| 8 | Jordan Love 225+ pass yds | 75% | -299 | ✓ 276 | `+8`

Legs 8/8

**AGGRESSIVE SGP** — 4-leg 24.7% · fair +305 ✗ · 6-leg 10.6% · fair +840 ✗ · 8-leg 5.3% · fair +1796 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | George Pickens 40+ rec yds | 62% | -162 | ✓ 73 | `4-leg core`
| 2 | Matthew Golden 40+ rec yds | 62% | -162 | ✓ 104 | `4-leg core`
| 3 | Tucker Kraft 4+ receptions | 64% | -177 | ✓ 5 | `4-leg core`
| 4 | Christian Watson 4+ receptions | 60% | -148 | ✗ 3 | `4-leg core`
| 5 | MarShawn Lloyd 20+ rush yds | 64% | -182 | ✗ 10 | `+6`
| 6 | Dak Prescott 200+ pass yds | 59% | -145 | ✓ 258 | `+6`
| 7 | Jordan Love 35+ pass att | 59% | -143 | ✓ 41 | `+8`
| 8 | Javonte Williams 40+ rush yds | 56% | -125 | ✓ 41 | `+8`

Legs 6/8

**Anytime TD**

| Player | Model | Fair | 2+ TDs | Result | Decomposition |
|---|---|---|---|---|---|
| Javonte Williams (DAL RB) | 52% | -111 | 17% (+483) | ✓ TD | share 23% · team 2.91 TD · RZ-D 1.05 · pos-D 1.03 |
| Christian Watson (GB WR) | 49% | +104 | 15% (+584) | ✗ no TD | share 17% · team 3.08 TD · RZ-D 1.1 · pos-D 1.22 |
| George Pickens (DAL WR) | 39% | +157 | 9% (+1033) | ✗ no TD | share 16% · team 2.91 TD · RZ-D 1.05 · pos-D 1.02 |
| MarShawn Lloyd (GB RB) | 38% | +162 | 8% (+1087) | ✗ no TD | share 13% · team 3.08 TD · RZ-D 1.1 · pos-D 1.1 |
| CeeDee Lamb (DAL WR) | 38% | +165 | 8% (+1109) | ✗ no TD | share 16% · team 2.91 TD · RZ-D 1.05 · pos-D 1.02 |
| Matthew Golden (GB WR) | 28% | +256 | 4% (+2191) | ✓ TD | share 8% · team 3.08 TD · RZ-D 1.1 · pos-D 1.22 |
| Tucker Kraft (GB TE) | 27% | +270 | 4% (+2385) | ✗ no TD | share 10% · team 3.08 TD · RZ-D 1.1 · pos-D 0.93 |
| Jake Ferguson (DAL TE) | 25% | +297 | 4% (+2770) | ✗ no TD | share 10% · team 2.91 TD · RZ-D 1.05 · pos-D 0.93 |

TD double: 27.9% · fair +258 · triple: 14.5% · fair +589

**All-position slip** — 28.1% · fair +256 **CASHED**: Jordan Love 30+ pass att ✓(41) · Javonte Williams 20+ rush yds ✓(41) · Matthew Golden 2+ receptions ✓(6) · Tucker Kraft 3+ receptions ✓(5) · Javonte Williams ANYTIME TD ✓(TD)

**All-position 8-leg** — 12.8% · fair +683 ✗: Jordan Love 30+ pass att ✓(41) · Javonte Williams 20+ rush yds ✓(41) · Matthew Golden 2+ receptions ✓(6) · Tucker Kraft 3+ receptions ✓(5) · George Pickens 20+ rec yds ✓(73) · Dak Prescott 175+ pass yds ✓(258) · Javonte Williams ANYTIME TD ✓(TD) · Christian Watson ANYTIME TD ✗(no TD)

*Gated (not eligible for tickets):* Tyler Goodson (DAL) role, Emari Demercado (DAL) OUT, KaVontae Turpin (DAL) role, Brevyn Spann-Ford (DAL) role, Kaleb Johnson (GB) role, Chris Brooks (GB) OUT, Skyy Moore (GB) OUT, Bo Melton (GB) role, Jonnu Smith (GB) role

*Grade: floor 8/8 — 4-leg ✓ (+116), 6-leg ✓ (+262), 8-leg ✓ (+386); all-position 5-leg ✓ 5/5 (+256); aggressive 6/8. ATD: Javonte ✓ (52%), Golden ✓ (28%); Watson, Pickens, Lamb, Lloyd, Kraft, Ferguson ✗. User's five-man ATD (Lamb · Williams · Watson · Golden · Pickens) went 2/5 — the model's recommended drop (Golden) scored and its chalk (Watson) did not. Model had the five at 3.7% / +2576 and the Golden-less four at 8.4% / +1085; 2+ TD singles offered: Javonte 17% (+483), Watson 15% (+584) — neither hit.*


## Week 8 — Sunday Nov 1 2026, early window (shipped floor, v1.9f)

*Engine v1.9f.* Eight 10am-PT games (clocks went back). Built on Friday designations with Lamar and Mayfield expected back (both were given a 'QB returns' boost to their receivers — the error v1.9g corrects). Report card: 63% vs 76%, SGP4 1/8 (TEN@CIN 8/8, all three SGPs cashed). Nine of 23 floor misses were players who left early: Lamar (1 snap, thumb → IR), Mayfield (7 snaps), Jeanty (6 touches), Tre Tucker (1 target), plus their dependent receivers. ATD board top-16 went 10/16 — the best board week on record — while the chalk triple went 1/3 again. ATD slip gained an RB / WR / TE page this week.


### ARI@DAL — final 33-30
*O/U 54.5 · spread +7.0 · indoor · turf · 13:00 ET*

**Personnel:** DAL: Pickens Q (shoulder) — singles only; Turpin OUT; Kenny Clark, Bullard (DTs) Q; Locke (S) Q; Winters (LB) OUT. ARI: Nolen (DT) OUT; Melton (CB), Wingard (S), Froholdt (C) Q; Conner + Benson on IR — Allgeier/Knight split. Roof.

**Injury report (as built):** ARI OFF · Jon Gaines II (G) — Out · Ankle · DNP; ARI DEF · Walter Nolen (DT) — Out · Ankle · DNP; ARI OFF · Hjalte Froholdt (C) — Questionable · Knee · DNP; ARI DEF · Andrew Wingard (S) — Questionable · Knee; ARI DEF · Max Melton (CB) — Questionable · Knee; DAL OFF · KaVontae Turpin (WR) — Out · Ribs · DNP; DAL DEF · Dee Winters (LB) — Out · Calf · DNP; DAL DEF · Jonathan Bullard (DT) — Questionable · Calf

**Defensive leaks:** DAL D leaks receiving yards to RBs: x1.20; DAL D leaks receiving yards to WRs: x1.13; DAL D leaks passing yards to QBs: x1.08; ARI D leaks rushing yards to RBs: x1.15

**Coordinators:** ARI OC Nathaniel Hackett — NEW (run_heavy) · measured pass 61% | DC Nick Rallis (blitz_heavy) · DAL OC Klayton Adams — continuity · measured pass 63% | DC Christian Parker (two_high_shell)

**Props SGP** — 4-leg 45.2% · fair +121 ✗ · 6-leg 30.3% · fair +230 ✗ · 8-leg 25.0% · fair +301 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Trey McBride 8+ receptions | 78% | -356 | ✗ 7 | `4-leg core` · 2026 5/7 pre-game
| 2 | Jacoby Brissett 175+ pass yds | 79% | -368 | ✗ 119 | `4-leg core` · 2026 5/7 pre-game
| 3 | Michael Wilson 2+ receptions | 76% | -325 | ✓ 8 | `4-leg core` · 2026 7/7 pre-game
| 4 | Dak Prescott 35+ pass att | 76% | -309 | ✗ 29 | `4-leg core` · 2026 4/7 pre-game
| 5 | CeeDee Lamb 50+ rec yds | 75% | -294 | ✓ 58 | `+6` · 2026 5/7 pre-game
| 6 | Javonte Williams 15+ carries | 82% | -441 | ✓ 24 | `+6` · 2026 3/7 pre-game
| 7 | Jacoby Brissett 35+ pass att | 76% | -323 | ✗ 23 | `+8` · 2026 6/7 pre-game
| 8 | Trey McBride 40+ rec yds | 74% | -288 | ✓ 72 | `+8` · 2026 6/7 pre-game

Legs 4/8 (expected 6.2)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Javonte Williams (DAL RB) | 65% | -187 | ✗ no TD | share 24% · team 3.44 TD · RZ-D 1.14 · pos-D 1.16 |
| CeeDee Lamb (DAL WR) | 52% | -109 | ✗ no TD | share 18% · team 3.44 TD · RZ-D 1.14 · pos-D 1.07 |
| Michael Wilson (ARI WR) | 40% | +150 | ✓ TD | share 14% · team 2.66 TD · RZ-D 1.16 · pos-D 1.3 |
| Trey McBride (ARI TE) | 38% | +166 | ✓ TD | share 19% · team 2.66 TD · RZ-D 1.16 · pos-D 0.86 |

TD double (Javonte Williams + CeeDee Lamb): 38.5% · fair +160 ✗

**All-position slip** — 34.8% · fair +187 ✗: Jacoby Brissett 175+ pass yds ✗(119) · Javonte Williams 15+ carries ✓(24) · Michael Wilson 2+ receptions ✓(8) · Trey McBride 8+ receptions ✗(7) · Javonte Williams ANYTIME TD ✗(no TD)

**All-position 8-leg** — 17.5% · fair +470 ✗: Jacoby Brissett 175+ pass yds ✗(119) · Javonte Williams 15+ carries ✓(24) · Michael Wilson 2+ receptions ✓(8) · Trey McBride 8+ receptions ✗(7) · CeeDee Lamb 50+ rec yds ✓(58) · Dak Prescott 35+ pass att ✗(29) · Javonte Williams ANYTIME TD ✗(no TD) · CeeDee Lamb ANYTIME TD ✗(no TD)


### ATL@TB — final 0-16
*O/U 43.5 · spread +2.5 · outdoor · grass · 13:00 ET*

**Personnel:** TB: Egbuka OUT — Godwin / Tez Johnson / Otton absorb 8 tgt/g; Mayfield back under centre (11 att in a run-heavy Wk 7); Gainwell Q; Goedeke (T) Q. ATL: Brian Robinson OUT — Bijan's goal-line competition gone; Zaccheaus Q; Bowman + Terrell (CBs) Q; Lindstrom DNP Wed.

**Injury report (as built):** ATL OFF · Brian Robinson (RB) — Out · Hamstring · DNP; ATL DEF · Samson Ebukam (DE) — Questionable · Hamstring; ATL OFF · Olamide Zaccheaus (WR) — Questionable · Shoulder; ATL DEF · Charles Snowden (DE) — Questionable · Back; ATL DEF · Divine Deablo (LB) — Questionable · Forearm; ATL DEF · Billy Bowman Jr. (CB) — Questionable · Hamstring; ATL OFF · Beaux Collins (WR) — Questionable · Hip; ATL OFF · Cameron Williams (T) — Questionable · Ankle

**Defensive leaks:** TB D leaks receiving yards to RBs: x1.37; TB D leaks receiving yards to TEs: x1.18; TB D leaks receptions to RBs: x1.16; ATL D leaks receptions to RBs: x1.16 (worsening x1.15 L4)

**Coordinators:** ATL OC Tommy Rees — NEW (run_heavy) · measured pass 49% | DC Jeff Ulbrich (blitz_heavy) · TB OC Zac Robinson — NEW (pass_wr) · measured pass 49% | DC Todd Bowles (blitz_heavy)

**Props SGP** — 4-leg 39.5% · fair +153 ✗ · 6-leg 25.5% · fair +292 ✗ · 8-leg 20.9% · fair +379 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Baker Mayfield 150+ pass yds | 78% | -358 | ✗ 0 | `4-leg core` · 2026 3/4 pre-game
| 2 | Bijan Robinson 15+ carries | 78% | -360 | ✓ 19 | `4-leg core` · 2026 6/7 pre-game
| 3 | Cade Otton 2+ receptions | 80% | -393 | – DNP | `4-leg core` · 2026 5/7 pre-game
| 4 | Bucky Irving 40+ rush yds | 76% | -319 | ✓ 170 | `4-leg core` · 2026 7/7 pre-game
| 5 | Drake London 3+ receptions | 75% | -294 | ✗ 1 | `+6` · 2026 6/7 pre-game
| 6 | Chris Godwin Jr. 20+ rec yds | 72% | -262 | ✗ 0 | `+6` · 2026 7/7 pre-game
| 7 | Michael Penix Jr. 20+ pass att | 86% | -613 | ✓ 24 | `+8` · 2026 5/5 pre-game
| 8 | Baker Mayfield 25+ pass att | 75% | -296 | ✗ 3 | `+8` · 2026 3/4 pre-game

Legs 3/7 (expected 6.2)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Bijan Robinson (ATL RB) | 49% | +103 | ✗ no TD | share 26% · team 2.3 TD · RZ-D 1.05 · pos-D 0.9 |
| Bucky Irving (TB RB) | 47% | +111 | ✓ TD | share 20% · team 2.58 TD · RZ-D 0.98 · pos-D 1.02 |
| Drake London (ATL WR) | 37% | +169 | ✗ no TD | share 19% · team 2.3 TD · RZ-D 1.05 · pos-D 0.95 |

TD double (Bijan Robinson + Bucky Irving): 25.6% · fair +291 ✗

**All-position slip** — 25.2% · fair +296 ✗: Baker Mayfield 150+ pass yds ✗(0) · Bijan Robinson 15+ carries ✓(19) · Drake London 3+ receptions ✗(1) · Cade Otton 2+ receptions –(DNP) · Bijan Robinson ANYTIME TD ✗(no TD)

**All-position 8-leg** — 11.6% · fair +763 ✗: Baker Mayfield 150+ pass yds ✗(0) · Bijan Robinson 15+ carries ✓(19) · Drake London 3+ receptions ✗(1) · Cade Otton 2+ receptions –(DNP) · Bucky Irving 40+ rush yds ✓(170) · Chris Godwin Jr. 20+ rec yds ✗(0) · Bijan Robinson ANYTIME TD ✗(no TD) · Bucky Irving ANYTIME TD ✓(TD)


### BAL@BUF — final 10-36
*O/U 54.5 · spread +3.0 · outdoor · turf · 13:00 ET*

**Personnel:** BAL: Lamar Jackson off the report — expected to start (Rapoport). Hawkins (S) OUT; T.J. Tampa (CB), Randall (RB) Q; Stanley, Campbell DNP (vet rest). BUF: Kincaid (TE, chest) Q, DJ Moore (WR) Q, Alford (CB) Q, Gaines (DT) Q, Spencer Brown (T) Q — all singles only until inactives. Highest total of the window (54.5).

**Injury report (as built):** BAL DEF · Jaylinn Hawkins (S) — Out · Knee · DNP; BAL OFF · Olaivavega Ioane (G) — Out · Knee; BAL DEF · T.J. Tampa (CB) — Questionable · Knee; BAL OFF · Adam Randall (RB) — Questionable · Neck; BAL DEF · Calais Campbell (DT) — nan · DNP; BAL OFF · Ronnie Stanley (T) — nan · DNP; BUF OFF · Tyrell Shavers (WR) — Out · Knee; BUF OFF · DJ Moore (WR) — Questionable · Shoulder

**Defensive leaks:** BUF D leaks receiving yards to RBs: x1.12 (worsening x1.72 L4); BUF D leaks receptions to RBs: x1.12 (worsening x1.57 L4); BUF D leaks passing interceptions to QBs: x1.11; BAL D leaks receiving yards to WRs: x1.17 (worsening x1.05 L4)

**Coordinators:** BAL OC Declan Doyle — NEW (pass_wr) · measured pass 49% | DC Anthony Weaver (pressure) · BUF OC Pete Carmichael Jr. — NEW (balanced) · measured pass 49% | DC Jim Leonhard (disguise_zone)

**Props SGP** — 4-leg 35.2% · fair +184 ✗ · 6-leg 21.8% · fair +359 ✗ · 8-leg 16.2% · fair +518 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Keon Coleman 2+ receptions | 78% | -344 | ✗ 1 | `4-leg core` · 2026 3/6 pre-game
| 2 | Zay Flowers 5+ receptions | 77% | -338 | ✗ 0 | `4-leg core` · 2026 6/6 pre-game
| 3 | James Cook 50+ rush yds | 75% | -300 | ✓ 80 | `4-leg core` · 2026 6/6 pre-game
| 4 | Josh Allen 200+ pass yds | 73% | -268 | ✓ 289 | `4-leg core` · 2026 6/6 pre-game
| 5 | Lamar Jackson 175+ pass yds | 73% | -266 | ✗ 0 | `+6` · 2026 4/4 pre-game
| 6 | Derrick Henry 50+ rush yds | 72% | -259 | ✓ 53 | `+6` · 2026 6/7 pre-game
| 7 | Keon Coleman 20+ rec yds | 74% | -290 | ✗ 4 | `+8` · 2026 4/6 pre-game
| 8 | Josh Allen 25+ pass att | 71% | -249 | ✓ 34 | `+8` · 2026 5/6 pre-game

Legs 4/8 (expected 5.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Derrick Henry (BAL RB) | 64% | -181 | ✓ TD | share 31% · team 2.88 TD · RZ-D 1.08 · pos-D 1.21 |
| James Cook (BUF RB) | 51% | -105 | ✓ TD | share 22% · team 3.22 TD · RZ-D 0.96 · pos-D 0.99 |
| Josh Allen (BUF QB) | 48% | +111 | ✓ TD | share 18% · team 3.22 TD · RZ-D 0.96 · pos-D 1.11 |
| Keon Coleman (BUF WR) | 33% | +205 | ✗ no TD | share 13% · team 3.22 TD · RZ-D 0.96 · pos-D 0.99 |

TD double (Derrick Henry + James Cook): 35.1% · fair +185 **CASHED**

**All-position slip** — 25.4% · fair +294 ✗: Josh Allen 200+ pass yds ✓(289) · James Cook 50+ rush yds ✓(80) · Keon Coleman 2+ receptions ✗(1) · Mark Andrews 2+ receptions ✓(3) · Derrick Henry ANYTIME TD ✓(TD)

**All-position 8-leg** — 12.1% · fair +724 ✗: Josh Allen 200+ pass yds ✓(289) · James Cook 50+ rush yds ✓(80) · Keon Coleman 2+ receptions ✗(1) · Mark Andrews 2+ receptions ✓(3) · Derrick Henry 50+ rush yds ✓(53) · Zay Flowers 70+ rec yds ✗(0) · Derrick Henry ANYTIME TD ✓(TD) · James Cook ANYTIME TD ✓(TD)


### CLE@PIT — final 6-27
*O/U 38.5 · spread +3.5 · outdoor · grass · 13:00 ET*

**Personnel:** PIT: Echols + Slaughter (CBs) OUT — Cleveland passing x1.06; Pittman IR; Skowronek Q. CLE: Howard (T), Harden (CB), D. Thomas (S) Q; Judkins back (17 carries Wk 7). Lowest total of the window (38.5).

**Injury report (as built):** CLE OFF · Tytus Howard (T) — Questionable · Concussion · DNP; CLE DEF · Daniel Thomas (S) — Questionable · Ankle; CLE DEF · Myles Harden (CB) — Questionable · Hamstring; PIT DEF · Brandin Echols (CB) — Out · Hamstring · DNP; PIT DEF · Doneiko Slaughter (CB) — Out · Hamstring · DNP; PIT OFF · Ben Skowronek (WR) — Questionable · Calf

**Defensive leaks:** PIT D leaks passing interceptions to QBs: x1.36 (worsening x1.05 L4); PIT D leaks receptions to TEs: x1.12; PIT D leaks receiving yards to TEs: x1.10

**Coordinators:** CLE OC Travis Switzer — NEW (run_heavy) · measured pass 53% | DC Mike Rutenberg (multiple) · PIT OC Brian Angelichio — NEW (pass_te) · measured pass 62% | DC Patrick Graham (multiple)

**Props SGP** — 4-leg 42.5% · fair +135 ✗ · 6-leg 25.9% · fair +286 ✗ · 8-leg 19.0% · fair +426 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | DK Metcalf 2+ receptions | 78% | -351 | ✗ 1 | `4-leg core` · 2026 7/7 pre-game
| 2 | Quinshon Judkins 20+ rush yds | 77% | -334 | ✓ 25 | `4-leg core` · 2026 6/6 pre-game
| 3 | Deshaun Watson 150+ pass yds | 79% | -381 | ✓ 324 | `4-leg core` · 2026 6/7 pre-game
| 4 | Aaron Rodgers 30+ pass att | 80% | -409 | ✗ 25 | `4-leg core` · 2026 7/7 pre-game
| 5 | Denzel Boston 2+ receptions | 75% | -301 | ✓ 6 | `+6` · 2026 6/7 pre-game
| 6 | Jaylen Warren 20+ rush yds | 74% | -290 | ✓ 143 | `+6` · 2026 7/7 pre-game
| 7 | Denzel Boston 20+ rec yds | 74% | -277 | ✓ 37 | `+8` · 2026 6/7 pre-game
| 8 | Deshaun Watson 25+ pass att | 73% | -272 | ✓ 39 | `+8` · 2026 6/7 pre-game

Legs 6/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Quinshon Judkins (CLE RB) | 33% | +205 | ✗ no TD | share 25% · team 1.96 TD · RZ-D 0.93 · pos-D 0.86 |
| Denzel Boston (CLE WR) | 31% | +218 | ✗ no TD | share 20% · team 1.96 TD · RZ-D 0.93 · pos-D 0.99 |
| DK Metcalf (PIT WR) | 31% | +227 | ✗ no TD | share 15% · team 2.35 TD · RZ-D 0.98 · pos-D 1.07 |
| Rico Dowdle (PIT RB) | 30% | +235 | ✓ TD | share 16% · team 2.35 TD · RZ-D 0.98 · pos-D 0.95 |

TD double (Quinshon Judkins + Denzel Boston): 14.1% · fair +608 ✗

**All-position slip** — 17.9% · fair +460 ✗: Deshaun Watson 150+ pass yds ✓(324) · Quinshon Judkins 20+ rush yds ✓(25) · DK Metcalf 2+ receptions ✗(1) · Harold Fannin Jr. 3+ receptions ✓(10) · Quinshon Judkins ANYTIME TD ✗(no TD)

**All-position 8-leg** — 7.2% · fair +1295 ✗: Deshaun Watson 150+ pass yds ✓(324) · Quinshon Judkins 20+ rush yds ✓(25) · DK Metcalf 2+ receptions ✗(1) · Harold Fannin Jr. 3+ receptions ✓(10) · Jaylen Warren 20+ rush yds ✓(143) · Denzel Boston 20+ rec yds ✓(37) · Quinshon Judkins ANYTIME TD ✗(no TD) · Denzel Boston ANYTIME TD ✗(no TD)


### IND@JAX — final 7-42
*O/U 46.5 · spread +10.0 · outdoor · grass · 13:00 ET*

**Personnel:** IND: Alec Pierce IR, Gould OUT; Walley (CB) OUT; Ogletree Q. JAX: Antonio Johnson (S) OUT; Meyers Q — singles only. IND -10.

**Injury report (as built):** IND OFF · Anthony Gould (WR) — Out · Concussion; IND DEF · Justin Walley (CB) — Out · Knee · DNP; IND OFF · Andrew Ogletree (TE) — Questionable · Knee · DNP; IND DEF · Bryce Boettcher (LB) — Questionable · Groin · DNP; JAX DEF · Antonio Johnson (S) — Out · Ankle · DNP; JAX OFF · Jakobi Meyers (WR) — Questionable · Hamstring · DNP

**Defensive leaks:** JAX D leaks passing interceptions to QBs: x1.25; JAX D leaks receptions to RBs: x1.18; JAX D leaks receiving yards to RBs: x1.17; IND D leaks receiving yards to TEs: x1.16

**Coordinators:** IND OC Jim Bob Cooter — continuity · measured pass 55% | DC Lou Anarumo (disguise_zone) · JAX OC Grant Udinski — continuity · measured pass 52% | DC Anthony Campanile (pressure)

**Props SGP** — 4-leg 36.7% · fair +173 ✗ · 6-leg 28.1% · fair +256 ✗ · 8-leg 20.9% · fair +379 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Parker Washington 2+ receptions | 78% | -348 | ✗ 1 | `4-leg core` · 2026 5/6 pre-game
| 2 | Brenton Strange 3+ receptions | 76% | -325 | ✗ 2 | `4-leg core` · 2026 4/6 pre-game
| 3 | Bhayshul Tuten 20+ rush yds | 76% | -316 | ✓ 104 | `4-leg core` · 2026 6/6 pre-game
| 4 | Daniel Jones 25+ pass att | 75% | -301 | ✓ 28 | `4-leg core` · 2026 6/7 pre-game
| 5 | Jonathan Taylor 10+ carries | 81% | -432 | ✗ 8 | `+6` · 2026 7/7 pre-game
| 6 | Trevor Lawrence 200+ pass yds | 83% | -479 | ✓ 210 | `+6` · 2026 4/6 pre-game
| 7 | Parker Washington 20+ rec yds | 76% | -320 | ✗ 16 | `+8` · 2026 5/6 pre-game
| 8 | Brenton Strange 20+ rec yds | 71% | -245 | ✓ 55 | `+8` · 2026 5/6 pre-game

Legs 4/8 (expected 6.2)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Jonathan Taylor (IND RB) | 40% | +153 | ✗ no TD | share 30% · team 2.04 TD · RZ-D 0.91 · pos-D 0.84 |
| Bhayshul Tuten (JAX RB) | 32% | +211 | ✓ TD | share 12% · team 3.16 TD · RZ-D 0.97 · pos-D 0.99 |
| Parker Washington (JAX WR) | 30% | +234 | ✗ no TD | share 12% · team 3.16 TD · RZ-D 0.97 · pos-D 0.99 |
| Tyler Warren (IND TE) | 26% | +279 | ✗ no TD | share 14% · team 2.04 TD · RZ-D 0.91 · pos-D 1.07 |

TD double (Jonathan Taylor + Bhayshul Tuten): 14.7% · fair +580 ✗

**All-position slip** — 18.3% · fair +447 ✗: Daniel Jones 25+ pass att ✓(28) · Bhayshul Tuten 20+ rush yds ✓(104) · Parker Washington 2+ receptions ✗(1) · Brenton Strange 3+ receptions ✗(2) · Jonathan Taylor ANYTIME TD ✗(no TD)

**All-position 8-leg** — 8.0% · fair +1144 ✗: Daniel Jones 25+ pass att ✓(28) · Bhayshul Tuten 20+ rush yds ✓(104) · Parker Washington 2+ receptions ✗(1) · Brenton Strange 3+ receptions ✗(2) · Jonathan Taylor 10+ carries ✗(8) · Trevor Lawrence 200+ pass yds ✓(210) · Jonathan Taylor ANYTIME TD ✗(no TD) · Bhayshul Tuten ANYTIME TD ✓(TD)


### LV@NYJ — final 38-33
*O/U 46.5 · spread +1.5 · outdoor · turf · 13:00 ET*

**Personnel:** NYJ: Breece Hall Q (quad) — Braelon Allen 17/24/17 carries the last three weeks regardless; Sweat (DT), Ossai (DE), Mitchell (T) OUT, Bailey doubtful. LV: Cousins starts; Bech Q; Runyon OUT.

**Injury report (as built):** LV DEF · Patrick Johnson (DE) — Out · Stinger · DNP; LV OFF · Carter Runyon (TE) — Out · Foot; LV OFF · Jackson Powers-Johnson (G) — Questionable · Back; LV OFF · Jack Bech (WR) — Questionable · Forearm; NYJ DEF · David Bailey (DE) — Doubtful · Groin · DNP; NYJ DEF · Joseph Ossai (DE) — Out · Ankle · DNP; NYJ OFF · Max Mitchell (T) — Out · Concussion · DNP; NYJ DEF · T'Vondre Sweat (DT) — Out · Knee · DNP

**Defensive leaks:** NYJ D leaks carries to RBs: x1.14 (worsening x1.07 L4); NYJ D leaks rushing yards to RBs: x1.11; LV D leaks rushing yards to RBs: x1.08 (worsening x1.41 L4)

**Coordinators:** LV OC Andrew Janocko — NEW (run_heavy) · measured pass 60% | DC Rob Leonard (four_man_rush) · NYJ OC Frank Reich — NEW (balanced) · measured pass 54% | DC Brian Duker (multiple)

**Props SGP** — 4-leg 40.9% · fair +144 ✗ · 6-leg 30.6% · fair +227 ✗ · 8-leg 22.3% · fair +348 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Mason Taylor 2+ receptions | 78% | -362 | ✓ 3 | `4-leg core` · 2026 4/4 pre-game
| 2 | Ashton Jeanty 10+ carries | 78% | -365 | ✗ 2 | `4-leg core` · 2026 6/7 pre-game
| 3 | Kirk Cousins 200+ pass yds | 77% | -332 | ✓ 247 | `4-leg core` · 2026 6/7 pre-game
| 4 | Geno Smith 30+ pass att | 76% | -326 | ✓ 32 | `4-leg core` · 2026 5/7 pre-game
| 5 | Tre Tucker 2+ receptions | 80% | -405 | ✗ 0 | `+6` · 2026 7/7 pre-game
| 6 | Garrett Wilson 30+ rec yds | 74% | -291 | ✓ 83 | `+6` · 2026 5/7 pre-game
| 7 | Brock Bowers 60+ rec yds | 74% | -280 | ✓ 92 | `+8` · 2026 5/5 pre-game
| 8 | Geno Smith 225+ pass yds | 72% | -254 | ✓ 290 | `+8` · 2026 4/7 pre-game

Legs 6/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Ashton Jeanty (LV RB) | 53% | -114 | ✗ no TD | share 26% · team 2.52 TD · RZ-D 1.08 · pos-D 1.22 |
| Brock Bowers (LV TE) | 43% | +134 | ✓ TD | share 21% · team 2.52 TD · RZ-D 1.08 · pos-D 1.0 |
| Garrett Wilson (NYJ WR) | 33% | +201 | ✗ no TD | share 13% · team 2.69 TD · RZ-D 1.1 · pos-D 1.07 |
| Braelon Allen (NYJ RB) | 32% | +213 | ✓ TD | share 12% · team 2.69 TD · RZ-D 1.1 · pos-D 1.06 |

TD double (Ashton Jeanty + Brock Bowers): 27.4% · fair +264 ✗

**All-position slip** — 27.8% · fair +260 ✗: Kirk Cousins 200+ pass yds ✓(247) · Ashton Jeanty 10+ carries ✗(2) · Tre Tucker 2+ receptions ✗(0) · Mason Taylor 2+ receptions ✓(3) · Ashton Jeanty ANYTIME TD ✗(no TD)

**All-position 8-leg** — 13.3% · fair +652 ✗: Kirk Cousins 200+ pass yds ✓(247) · Ashton Jeanty 10+ carries ✗(2) · Tre Tucker 2+ receptions ✗(0) · Mason Taylor 2+ receptions ✓(3) · Garrett Wilson 30+ rec yds ✓(83) · Brock Bowers 60+ rec yds ✓(92) · Ashton Jeanty ANYTIME TD ✗(no TD) · Brock Bowers ANYTIME TD ✓(TD)


### MIN@DET — final 15-19
*O/U 46.5 · spread +3.0 · indoor · turf · 13:00 ET*

**Personnel:** DET: Kerby Joseph (S) OUT, McCreary (CB) Q — Minnesota passing x1.06. Pacheco IR — Gibbs 29 carries last week. MIN: Kyler Murray starts; Darrisaw (LT) DNP Wed. Dome.

**Injury report (as built):** DET DEF · Kerby Joseph (S) — Out · Knee; DET DEF · Roger McCreary (CB) — Questionable · Foot; MIN DEF · Jay Ward (S) — Questionable · Knee; MIN OFF · Christian Darrisaw (T) — nan · DNP

**Defensive leaks:** DET D leaks receiving yards to WRs: x1.19; DET D leaks passing interceptions to QBs: x1.18 (worsening x1.21 L4); DET D leaks receptions to WRs: x1.15 (worsening x1.06 L4); MIN D leaks passing interceptions to QBs: x1.40 (worsening x1.54 L4)

**Coordinators:** MIN OC Wes Phillips — continuity · measured pass 48% | DC Brian Flores (blitz_man) · DET OC Drew Petzing — NEW (pass_te) · measured pass 58% | DC Kelvin Sheppard (pressure)

**Props SGP** — 4-leg 43.6% · fair +130 ✗ · 6-leg 28.3% · fair +253 ✗ · 8-leg 16.0% · fair +524 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | T.J. Hockenson 2+ receptions | 78% | -344 | ✓ 4 | `4-leg core` · 2026 5/6 pre-game
| 2 | Kyler Murray 175+ pass yds | 76% | -314 | ✓ 210 | `4-leg core` · 2026 2/5 pre-game
| 3 | Jared Goff 225+ pass yds | 76% | -310 | ✗ 176 | `4-leg core` · 2026 5/6 pre-game
| 4 | Jordan Addison 2+ receptions | 75% | -306 | ✓ 3 | `4-leg core` · 2026 4/5 pre-game
| 5 | Jahmyr Gibbs 30+ rush yds | 73% | -273 | ✓ 153 | `+6` · 2026 6/6 pre-game
| 6 | Justin Jefferson 40+ rec yds | 73% | -272 | ✗ 33 | `+6` · 2026 4/6 pre-game
| 7 | Amon-Ra St. Brown 30+ rec yds | 73% | -271 | ✓ 46 | `+8` · 2026 5/6 pre-game
| 8 | Aaron Jones 10+ carries | 71% | -243 | ✗ 5 | `+8` · 2026 5/6 pre-game

Legs 5/8 (expected 5.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Justin Jefferson (MIN WR) | 44% | +129 | ✓ TD | share 21% · team 2.44 TD · RZ-D 1.05 · pos-D 1.11 |
| Jahmyr Gibbs (DET RB) | 40% | +148 | ✓ TD | share 24% · team 2.77 TD · RZ-D 0.68 · pos-D 0.87 |
| Aaron Jones (MIN RB) | 32% | +210 | ✗ no TD | share 17% · team 2.44 TD · RZ-D 1.05 · pos-D 0.96 |
| Jordan Addison (MIN WR) | 32% | +215 | ✗ no TD | share 14% · team 2.44 TD · RZ-D 1.05 · pos-D 1.11 |

TD double (Justin Jefferson + Jahmyr Gibbs): 19.8% · fair +405 **CASHED**

**All-position slip** — 23.1% · fair +332 **CASHED**: Kyler Murray 175+ pass yds ✓(210) · Jahmyr Gibbs 30+ rush yds ✓(153) · Jordan Addison 2+ receptions ✓(3) · T.J. Hockenson 2+ receptions ✓(4) · Justin Jefferson ANYTIME TD ✓(TD)

**All-position 8-leg** — 8.8% · fair +1036 ✗: Kyler Murray 175+ pass yds ✓(210) · Jahmyr Gibbs 30+ rush yds ✓(153) · Jordan Addison 2+ receptions ✓(3) · T.J. Hockenson 2+ receptions ✓(4) · Aaron Jones 10+ carries ✗(5) · Justin Jefferson 40+ rec yds ✗(33) · Justin Jefferson ANYTIME TD ✓(TD) · Jahmyr Gibbs ANYTIME TD ✓(TD)


### TEN@CIN — final 36-43
*O/U 45.5 · spread +12.5 · outdoor · turf · 13:00 ET*

**Personnel:** TEN: Carnell Tate (WR1 by targets) OUT, Tyjae Spears OUT, Ridley Q, Franklin-Myers (DE) Q. CIN: Dugger (S) OUT; Allen/Hill/Lawrence (DTs) DNP Wed, no tag. CIN -12.5 — blowout haircut on TEN rushing and CIN passing applied.

**Injury report (as built):** CIN DEF · Kyle Dugger (S) — Out · Quadricep · DNP; CIN DEF · Joe Giles-Harris (LB) — Questionable · Calf; CIN DEF · Jonathan Allen (DT) — nan · DNP; CIN DEF · B.J. Hill (DT) — nan · DNP; CIN DEF · Dexter Lawrence (DT) — nan · DNP; TEN OFF · Tommy Townsend (P) — Out · Knee · DNP; TEN OFF · Tyjae Spears (RB) — Out · Knee · DNP; TEN OFF · Carnell Tate (WR) — Out · Shoulder · DNP

**Defensive leaks:** CIN D leaks receiving yards to TEs: x1.46; CIN D leaks receptions to TEs: x1.28; CIN D leaks passing interceptions to QBs: x1.15 (worsening x1.88 L4)

**Coordinators:** TEN OC Brian Daboll — NEW (pass_wr) · measured pass 56% | DC Gus Bradley (zone_cover3) · CIN OC Dan Pitcher — continuity · measured pass 62% | DC Al Golden (disguise_zone)

**Props SGP** — 4-leg 39.5% · fair +153 **CASHED** · 6-leg 27.8% · fair +260 **CASHED** · 8-leg 18.4% · fair +444 **CASHED**

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Joe Burrow 200+ pass yds | 78% | -354 | ✓ 462 | `4-leg core` · 2026 5/6 pre-game
| 2 | Ja'Marr Chase 4+ receptions | 78% | -344 | ✓ 11 | `4-leg core` · 2026 4/6 pre-game
| 3 | Chase Brown 20+ rush yds | 77% | -337 | ✓ 55 | `4-leg core` · 2026 5/6 pre-game
| 4 | Wan'Dale Robinson 3+ receptions | 79% | -382 | ✓ 6 | `4-leg core` · 2026 6/7 pre-game
| 5 | Tee Higgins 50+ rec yds | 75% | -297 | ✓ 155 | `+6` · 2026 5/6 pre-game
| 6 | Cam Ward 25+ pass att | 73% | -272 | ✓ 40 | `+6` · 2026 5/7 pre-game
| 7 | Tony Pollard 40+ rush yds | 72% | -255 | ✓ 117 | `+8` · 2026 6/7 pre-game
| 8 | Joe Burrow 30+ pass att | 76% | -316 | ✓ 48 | `+8` · 2026 6/6 pre-game

Legs 8/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Chase Brown (CIN RB) | 50% | -101 | ✗ no TD | share 20% · team 3.25 TD · RZ-D 1.12 · pos-D 1.09 |
| Ja'Marr Chase (CIN WR) | 48% | +107 | ✓ TD | share 18% · team 3.25 TD · RZ-D 1.12 · pos-D 1.04 |
| Tony Pollard (TEN RB) | 44% | +128 | ✓ TD | share 22% · team 1.85 TD · RZ-D 0.98 · pos-D 1.05 |
| Tee Higgins (CIN WR) | 39% | +156 | ✓ TD | share 14% · team 3.25 TD · RZ-D 1.12 · pos-D 1.04 |

TD double (Chase Brown + Ja'Marr Chase): 28.9% · fair +246 ✗

**All-position slip** — 30.5% · fair +228 ✗: Joe Burrow 200+ pass yds ✓(462) · Chase Brown 20+ rush yds ✓(55) · Ja'Marr Chase 4+ receptions ✓(11) · Chase Brown ANYTIME TD ✗(no TD)

**All-position 8-leg** — 13.9% · fair +620 ✗: Joe Burrow 200+ pass yds ✓(462) · Chase Brown 20+ rush yds ✓(55) · Ja'Marr Chase 4+ receptions ✓(11) · Tony Pollard 40+ rush yds ✓(117) · Wan'Dale Robinson 3+ receptions ✓(6) · Chase Brown ANYTIME TD ✗(no TD) · Ja'Marr Chase ANYTIME TD ✓(TD)


### Cross-game combos — Week 8 — Sunday Nov 1 2026, early window (shipped floor, v1.9f)

**4-leg** — 37.2% · fair +169 — 1/4 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | TEN@CIN | Joe Burrow 200+ pass yds | 78% | ✓ 462 |
| 2 | ARI@DAL | Trey McBride 8+ receptions | 78% | ✗ 7 |
| 3 | ATL@TB | Baker Mayfield 150+ pass yds | 78% | ✗ 0 |
| 4 | CLE@PIT | DK Metcalf 2+ receptions | 78% | ✗ 1 |

**6-leg** — 23.3% · fair +329 — 2/6 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | TEN@CIN | Joe Burrow 200+ pass yds | 78% | ✓ 462 |
| 2 | ARI@DAL | Trey McBride 8+ receptions | 78% | ✗ 7 |
| 3 | ATL@TB | Baker Mayfield 150+ pass yds | 78% | ✗ 0 |
| 4 | CLE@PIT | DK Metcalf 2+ receptions | 78% | ✗ 1 |
| 5 | ATL@TB | Bijan Robinson 15+ carries | 78% | ✓ 19 |
| 6 | LV@NYJ | Ashton Jeanty 10+ carries | 78% | ✗ 2 |

**8-leg** — 13.7% · fair +632 — 4/8 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | TEN@CIN | Joe Burrow 200+ pass yds | 78% | ✓ 462 |
| 2 | ARI@DAL | Trey McBride 8+ receptions | 78% | ✗ 7 |
| 3 | ATL@TB | Baker Mayfield 150+ pass yds | 78% | ✗ 0 |
| 4 | CLE@PIT | DK Metcalf 2+ receptions | 78% | ✗ 1 |
| 5 | ATL@TB | Bijan Robinson 15+ carries | 78% | ✓ 19 |
| 6 | LV@NYJ | Ashton Jeanty 10+ carries | 78% | ✗ 2 |
| 7 | TEN@CIN | Chase Brown 20+ rush yds | 77% | ✓ 55 |
| 8 | CLE@PIT | Quinshon Judkins 20+ rush yds | 77% | ✓ 25 |

**10-leg** — 8.9% · fair +1025 — 4/10 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | TEN@CIN | Joe Burrow 200+ pass yds | 78% | ✓ 462 |
| 2 | ARI@DAL | Trey McBride 8+ receptions | 78% | ✗ 7 |
| 3 | ATL@TB | Baker Mayfield 150+ pass yds | 78% | ✗ 0 |
| 4 | CLE@PIT | DK Metcalf 2+ receptions | 78% | ✗ 1 |
| 5 | ATL@TB | Bijan Robinson 15+ carries | 78% | ✓ 19 |
| 6 | IND@JAX | Parker Washington 2+ receptions | 78% | ✗ 1 |
| 7 | LV@NYJ | Ashton Jeanty 10+ carries | 78% | ✗ 2 |
| 8 | ARI@DAL | Jacoby Brissett 175+ pass yds | 79% | ✗ 119 |
| 9 | TEN@CIN | Chase Brown 20+ rush yds | 77% | ✓ 55 |
| 10 | CLE@PIT | Quinshon Judkins 20+ rush yds | 77% | ✓ 25 |

**12-leg** — 5.3% · fair +1791 — 6/12 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | TEN@CIN | Joe Burrow 200+ pass yds | 78% | ✓ 462 |
| 2 | ARI@DAL | Trey McBride 8+ receptions | 78% | ✗ 7 |
| 3 | ATL@TB | Baker Mayfield 150+ pass yds | 78% | ✗ 0 |
| 4 | CLE@PIT | DK Metcalf 2+ receptions | 78% | ✗ 1 |
| 5 | ATL@TB | Bijan Robinson 15+ carries | 78% | ✓ 19 |
| 6 | IND@JAX | Parker Washington 2+ receptions | 78% | ✗ 1 |
| 7 | LV@NYJ | Mason Taylor 2+ receptions | 78% | ✓ 3 |
| 8 | LV@NYJ | Ashton Jeanty 10+ carries | 78% | ✗ 2 |
| 9 | ARI@DAL | Jacoby Brissett 175+ pass yds | 79% | ✗ 119 |
| 10 | TEN@CIN | Chase Brown 20+ rush yds | 77% | ✓ 55 |
| 11 | CLE@PIT | Quinshon Judkins 20+ rush yds | 77% | ✓ 25 |
| 12 | IND@JAX | Bhayshul Tuten 20+ rush yds | 76% | ✓ 104 |


### ATD board (top 16) — Week 8 — Sunday Nov 1 2026, early window (shipped floor, v1.9f)

| # | Game | Player | Model | Fair | Result |
|---|---|---|---|---|---|
| 1 | ARI@DAL | Javonte Williams (RB) | 65% | -187 | ✗ no TD |
| 2 | BAL@BUF | Derrick Henry (RB) | 64% | -181 | ✓ TD |
| 3 | LV@NYJ | Ashton Jeanty (RB) | 53% | -114 | ✗ no TD |
| 4 | ARI@DAL | CeeDee Lamb (WR) | 52% | -109 | ✗ no TD |
| 5 | BAL@BUF | James Cook (RB) | 51% | -105 | ✓ TD |
| 6 | TEN@CIN | Chase Brown (RB) | 50% | -101 | ✗ no TD |
| 7 | ATL@TB | Bijan Robinson (RB) | 49% | +103 | ✗ no TD |
| 8 | TEN@CIN | Ja'Marr Chase (WR) | 48% | +107 | ✓ TD |
| 9 | BAL@BUF | Josh Allen (QB) | 48% | +111 | ✓ TD |
| 10 | ATL@TB | Bucky Irving (RB) | 47% | +111 | ✓ TD |
| 11 | TEN@CIN | Tony Pollard (RB) | 44% | +128 | ✓ TD |
| 12 | MIN@DET | Justin Jefferson (WR) | 44% | +129 | ✓ TD |
| 13 | LV@NYJ | Brock Bowers (TE) | 43% | +134 | ✓ TD |
| 14 | MIN@DET | Jahmyr Gibbs (RB) | 40% | +148 | ✓ TD |
| 15 | ARI@DAL | Michael Wilson (WR) | 40% | +150 | ✓ TD |
| 16 | IND@JAX | Jonathan Taylor (RB) | 40% | +153 | ✗ no TD |

Board: top-16 10/16 · top-8 3/8 · chalk triple 1/3

**2+ TD board (singles only):** Javonte Williams 28% (+251) · Derrick Henry 28% (+262) · Ashton Jeanty 18% (+462) · CeeDee Lamb 17% (+491) · James Cook 16% (+519) · Chase Brown 16% (+547)


### Scorecard — Week 8 — Sunday Nov 1 2026, early window (shipped floor, v1.9f)

**Legs 40/63 = 63% actual vs 77% expected · SGP4 1/8 · SGP6 1/8 · SGP8 1/8**

| Game | Final | Legs | SGP4 | SGP6 | SGP8 |
|---|---|---|---|---|---|
| TEN@CIN | 36-43 | 8/8 | ✓ | ✓ | ✓ |
| CLE@PIT | 6-27 | 6/8 | ✗ | ✗ | ✗ |
| LV@NYJ | 38-33 | 6/8 | ✗ | ✗ | ✗ |
| MIN@DET | 15-19 | 5/8 | ✗ | ✗ | ✗ |
| ARI@DAL | 33-30 | 4/8 | ✗ | ✗ | ✗ |
| BAL@BUF | 10-36 | 4/8 | ✗ | ✗ | ✗ |
| IND@JAX | 7-42 | 4/8 | ✗ | ✗ | ✗ |
| ATL@TB | 0-16 | 3/7 | ✗ | ✗ | ✗ |


## Week 8 — aggressive band (shipped)

*Engine v1.9f.* 53% vs 62% expected; TEN@CIN 8/8.


### ARI@DAL — final 33-30
*O/U 54.5 · spread +7.0 · indoor · turf · 13:00 ET*

**Personnel:** DAL: Pickens Q (shoulder) — singles only; Turpin OUT; Kenny Clark, Bullard (DTs) Q; Locke (S) Q; Winters (LB) OUT. ARI: Nolen (DT) OUT; Melton (CB), Wingard (S), Froholdt (C) Q; Conner + Benson on IR — Allgeier/Knight split. Roof.

**Injury report (as built):** ARI OFF · Jon Gaines II (G) — Out · Ankle · DNP; ARI DEF · Walter Nolen (DT) — Out · Ankle · DNP; ARI OFF · Hjalte Froholdt (C) — Questionable · Knee · DNP; ARI DEF · Andrew Wingard (S) — Questionable · Knee; ARI DEF · Max Melton (CB) — Questionable · Knee; DAL OFF · KaVontae Turpin (WR) — Out · Ribs · DNP; DAL DEF · Dee Winters (LB) — Out · Calf · DNP; DAL DEF · Jonathan Bullard (DT) — Questionable · Calf

**Defensive leaks:** DAL D leaks receiving yards to RBs: x1.20; DAL D leaks receiving yards to WRs: x1.13; DAL D leaks passing yards to QBs: x1.08; ARI D leaks rushing yards to RBs: x1.15

**Coordinators:** ARI OC Nathaniel Hackett — NEW (run_heavy) · measured pass 61% | DC Nick Rallis (blitz_heavy) · DAL OC Klayton Adams — continuity · measured pass 63% | DC Christian Parker (two_high_shell)

**Props SGP** — 4-leg 17.0% · fair +490 ✗ · 6-leg 9.7% · fair +929 ✗ · 8-leg 7.3% · fair +1266 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Tyler Allgeier 10+ carries | 62% | -163 | ✓ 11 | `4-leg core` · 2026 2/7 pre-game
| 2 | Michael Wilson 4+ receptions | 62% | -167 | ✓ 8 | `4-leg core` · 2026 6/7 pre-game
| 3 | Kendrick Bourne 30+ rec yds | 61% | -159 | ✗ 29 | `4-leg core` · 2026 3/6 pre-game
| 4 | CeeDee Lamb 70+ rec yds | 64% | -174 | ✗ 58 | `4-leg core` · 2026 5/7 pre-game
| 5 | Jacoby Brissett 225+ pass yds | 59% | -143 | ✗ 119 | `+6` · 2026 4/7 pre-game
| 6 | Dak Prescott 300+ pass yds | 58% | -139 | ✗ 195 | `+6` · 2026 2/7 pre-game
| 7 | CeeDee Lamb 5+ receptions | 68% | -211 | ✓ 7 | `+8` · 2026 6/7 pre-game
| 8 | Jacoby Brissett o0.5 INT o0.5 | 56% | -126 | ✓ 1 INT | `+8` · 2026 4/7 pre-game

Legs 4/8 (expected 4.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Javonte Williams (DAL RB) | 65% | -187 | ✗ no TD | share 24% · team 3.44 TD · RZ-D 1.14 · pos-D 1.16 |
| CeeDee Lamb (DAL WR) | 52% | -109 | ✗ no TD | share 18% · team 3.44 TD · RZ-D 1.14 · pos-D 1.07 |
| Michael Wilson (ARI WR) | 40% | +150 | ✓ TD | share 14% · team 2.66 TD · RZ-D 1.16 · pos-D 1.3 |
| Trey McBride (ARI TE) | 38% | +166 | ✓ TD | share 19% · team 2.66 TD · RZ-D 1.16 · pos-D 0.86 |

TD double (Javonte Williams + CeeDee Lamb): 38.5% · fair +160 ✗

**All-position slip** — 16.8% · fair +494 ✗: Jacoby Brissett 225+ pass yds ✗(119) · Tyler Allgeier 10+ carries ✓(11) · Michael Wilson 4+ receptions ✓(8) · Javonte Williams ANYTIME TD ✗(no TD)

**All-position 8-leg** — 7.1% · fair +1299 ✗: Jacoby Brissett 225+ pass yds ✗(119) · Tyler Allgeier 10+ carries ✓(11) · Michael Wilson 4+ receptions ✓(8) · Kendrick Bourne 30+ rec yds ✗(29) · Dak Prescott 300+ pass yds ✗(195) · Javonte Williams ANYTIME TD ✗(no TD) · CeeDee Lamb ANYTIME TD ✗(no TD)


### ATL@TB — final 0-16
*O/U 43.5 · spread +2.5 · outdoor · grass · 13:00 ET*

**Personnel:** TB: Egbuka OUT — Godwin / Tez Johnson / Otton absorb 8 tgt/g; Mayfield back under centre (11 att in a run-heavy Wk 7); Gainwell Q; Goedeke (T) Q. ATL: Brian Robinson OUT — Bijan's goal-line competition gone; Zaccheaus Q; Bowman + Terrell (CBs) Q; Lindstrom DNP Wed.

**Injury report (as built):** ATL OFF · Brian Robinson (RB) — Out · Hamstring · DNP; ATL DEF · Samson Ebukam (DE) — Questionable · Hamstring; ATL OFF · Olamide Zaccheaus (WR) — Questionable · Shoulder; ATL DEF · Charles Snowden (DE) — Questionable · Back; ATL DEF · Divine Deablo (LB) — Questionable · Forearm; ATL DEF · Billy Bowman Jr. (CB) — Questionable · Hamstring; ATL OFF · Beaux Collins (WR) — Questionable · Hip; ATL OFF · Cameron Williams (T) — Questionable · Ankle

**Defensive leaks:** TB D leaks receiving yards to RBs: x1.37; TB D leaks receiving yards to TEs: x1.18; TB D leaks receptions to RBs: x1.16; ATL D leaks receptions to RBs: x1.16 (worsening x1.15 L4)

**Coordinators:** ATL OC Tommy Rees — NEW (run_heavy) · measured pass 49% | DC Jeff Ulbrich (blitz_heavy) · TB OC Zac Robinson — NEW (pass_wr) · measured pass 49% | DC Todd Bowles (blitz_heavy)

**Props SGP** — 4-leg 25.0% · fair +300 ✗ · 6-leg 16.4% · fair +511 ✗ · 8-leg 5.9% · fair +1594 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Bucky Irving 1+ receptions | 62% | -165 | ✗ 0 | `4-leg core` · 2026 6/7 pre-game
| 2 | Chris Godwin Jr. 30+ rec yds | 63% | -170 | ✗ 0 | `4-leg core` · 2026 5/7 pre-game
| 3 | Bijan Robinson 20+ rec yds | 63% | -170 | ✗ 0 | `4-leg core` · 2026 3/7 pre-game
| 4 | Drake London 4+ receptions | 65% | -184 | ✗ 1 | `4-leg core` · 2026 6/7 pre-game
| 5 | Michael Penix Jr. 25+ pass att | 65% | -185 | ✗ 24 | `+6` · 2026 4/5 pre-game
| 6 | Baker Mayfield 200+ pass yds | 59% | -143 | ✗ 0 | `+6` · 2026 2/4 pre-game
| 7 | Bucky Irving 20+ carries | 59% | -143 | ✓ 27 | `+8` · 2026 2/7 pre-game
| 8 | Bijan Robinson 70+ rush yds | 65% | -189 | ✓ 76 | `+8` · 2026 5/7 pre-game

Legs 2/8 (expected 5.0)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Bijan Robinson (ATL RB) | 49% | +103 | ✗ no TD | share 26% · team 2.3 TD · RZ-D 1.05 · pos-D 0.9 |
| Bucky Irving (TB RB) | 47% | +111 | ✓ TD | share 20% · team 2.58 TD · RZ-D 0.98 · pos-D 1.02 |
| Drake London (ATL WR) | 37% | +169 | ✗ no TD | share 19% · team 2.3 TD · RZ-D 1.05 · pos-D 0.95 |

TD double (Bijan Robinson + Bucky Irving): 25.6% · fair +291 ✗

**All-position slip** — 16.3% · fair +514 ✗: Michael Penix Jr. 25+ pass att ✗(24) · Bucky Irving 1+ receptions ✗(0) · Chris Godwin Jr. 30+ rec yds ✗(0) · Cade Otton 20+ rec yds –(DNP) · Bijan Robinson ANYTIME TD ✗(no TD)

**All-position 8-leg** — 6.9% · fair +1352 ✗: Michael Penix Jr. 25+ pass att ✗(24) · Bucky Irving 1+ receptions ✗(0) · Chris Godwin Jr. 30+ rec yds ✗(0) · Cade Otton 20+ rec yds –(DNP) · Bijan Robinson 70+ rush yds ✓(76) · Drake London 4+ receptions ✗(1) · Bijan Robinson ANYTIME TD ✗(no TD) · Bucky Irving ANYTIME TD ✓(TD)


### BAL@BUF — final 10-36
*O/U 54.5 · spread +3.0 · outdoor · turf · 13:00 ET*

**Personnel:** BAL: Lamar Jackson off the report — expected to start (Rapoport). Hawkins (S) OUT; T.J. Tampa (CB), Randall (RB) Q; Stanley, Campbell DNP (vet rest). BUF: Kincaid (TE, chest) Q, DJ Moore (WR) Q, Alford (CB) Q, Gaines (DT) Q, Spencer Brown (T) Q — all singles only until inactives. Highest total of the window (54.5).

**Injury report (as built):** BAL DEF · Jaylinn Hawkins (S) — Out · Knee · DNP; BAL OFF · Olaivavega Ioane (G) — Out · Knee; BAL DEF · T.J. Tampa (CB) — Questionable · Knee; BAL OFF · Adam Randall (RB) — Questionable · Neck; BAL DEF · Calais Campbell (DT) — nan · DNP; BAL OFF · Ronnie Stanley (T) — nan · DNP; BUF OFF · Tyrell Shavers (WR) — Out · Knee; BUF OFF · DJ Moore (WR) — Questionable · Shoulder

**Defensive leaks:** BUF D leaks receiving yards to RBs: x1.12 (worsening x1.72 L4); BUF D leaks receptions to RBs: x1.12 (worsening x1.57 L4); BUF D leaks passing interceptions to QBs: x1.11; BAL D leaks receiving yards to WRs: x1.17 (worsening x1.05 L4)

**Coordinators:** BAL OC Declan Doyle — NEW (pass_wr) · measured pass 49% | DC Anthony Weaver (pressure) · BUF OC Pete Carmichael Jr. — NEW (balanced) · measured pass 49% | DC Jim Leonhard (disguise_zone)

**Props SGP** — 4-leg 23.3% · fair +330 ✗ · 6-leg 16.1% · fair +520 ✗ · 8-leg 5.9% · fair +1598 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Lamar Jackson 20+ pass att | 63% | -169 | ✗ 1 | `4-leg core` · 2026 4/4 pre-game
| 2 | Ja'Kobi Lane 3+ receptions | 64% | -176 | ✗ 1 | `4-leg core` · 2026 2/3 pre-game
| 3 | Khalil Shakir 30+ rec yds | 60% | -152 | ✓ 64 | `4-leg core` · 2026 5/6 pre-game
| 4 | Josh Allen 225+ pass yds | 60% | -150 | ✓ 289 | `4-leg core` · 2026 4/6 pre-game
| 5 | Keon Coleman 3+ receptions | 64% | -179 | ✗ 1 | `+6` · 2026 3/6 pre-game
| 6 | Zay Flowers 80+ rec yds | 64% | -180 | ✗ 0 | `+6` · 2026 4/6 pre-game
| 7 | James Cook 80+ rush yds | 57% | -133 | ✓ 80 | `+8` · 2026 4/6 pre-game
| 8 | Derrick Henry 60+ rush yds | 67% | -203 | ✗ 53 | `+8` · 2026 5/7 pre-game

Legs 3/8 (expected 5.0)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Derrick Henry (BAL RB) | 64% | -181 | ✓ TD | share 31% · team 2.88 TD · RZ-D 1.08 · pos-D 1.21 |
| James Cook (BUF RB) | 51% | -105 | ✓ TD | share 22% · team 3.22 TD · RZ-D 0.96 · pos-D 0.99 |
| Josh Allen (BUF QB) | 48% | +111 | ✓ TD | share 18% · team 3.22 TD · RZ-D 0.96 · pos-D 1.11 |
| Keon Coleman (BUF WR) | 33% | +205 | ✗ no TD | share 13% · team 3.22 TD · RZ-D 0.96 · pos-D 0.99 |

TD double (Derrick Henry + James Cook): 35.1% · fair +185 **CASHED**

**All-position slip** — 18.1% · fair +454 ✗: Lamar Jackson 20+ pass att ✗(1) · James Cook 80+ rush yds ✓(80) · Ja'Kobi Lane 3+ receptions ✗(1) · Mark Andrews 3+ receptions ✓(3) · Derrick Henry ANYTIME TD ✓(TD)

**All-position 8-leg** — 6.1% · fair +1550 ✗: Lamar Jackson 20+ pass att ✗(1) · James Cook 80+ rush yds ✓(80) · Ja'Kobi Lane 3+ receptions ✗(1) · Mark Andrews 3+ receptions ✓(3) · Derrick Henry 60+ rush yds ✗(53) · Khalil Shakir 30+ rec yds ✓(64) · Derrick Henry ANYTIME TD ✓(TD) · James Cook ANYTIME TD ✓(TD)


### CLE@PIT — final 6-27
*O/U 38.5 · spread +3.5 · outdoor · grass · 13:00 ET*

**Personnel:** PIT: Echols + Slaughter (CBs) OUT — Cleveland passing x1.06; Pittman IR; Skowronek Q. CLE: Howard (T), Harden (CB), D. Thomas (S) Q; Judkins back (17 carries Wk 7). Lowest total of the window (38.5).

**Injury report (as built):** CLE OFF · Tytus Howard (T) — Questionable · Concussion · DNP; CLE DEF · Daniel Thomas (S) — Questionable · Ankle; CLE DEF · Myles Harden (CB) — Questionable · Hamstring; PIT DEF · Brandin Echols (CB) — Out · Hamstring · DNP; PIT DEF · Doneiko Slaughter (CB) — Out · Hamstring · DNP; PIT OFF · Ben Skowronek (WR) — Questionable · Calf

**Defensive leaks:** PIT D leaks passing interceptions to QBs: x1.36 (worsening x1.05 L4); PIT D leaks receptions to TEs: x1.12; PIT D leaks receiving yards to TEs: x1.10

**Coordinators:** CLE OC Travis Switzer — NEW (run_heavy) · measured pass 53% | DC Mike Rutenberg (multiple) · PIT OC Brian Angelichio — NEW (pass_te) · measured pass 62% | DC Patrick Graham (multiple)

**Props SGP** — 4-leg 14.8% · fair +575 ✗ · 6-leg 7.9% · fair +1164 ✗ · 8-leg 5.3% · fair +1770 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Jaylen Warren 40+ rush yds | 62% | -161 | ✓ 143 | `4-leg core` · 2026 7/7 pre-game
| 2 | Aaron Rodgers 35+ pass att | 61% | -157 | ✗ 25 | `4-leg core` · 2026 4/7 pre-game
| 3 | KC Concepcion 4+ receptions | 61% | -155 | ✗ 3 | `4-leg core` · 2026 5/7 pre-game
| 4 | Quinshon Judkins 40+ rush yds | 61% | -154 | ✗ 25 | `4-leg core` · 2026 4/6 pre-game
| 5 | Denzel Boston 40+ rec yds | 60% | -152 | ✗ 37 | `+6` · 2026 5/7 pre-game
| 6 | DK Metcalf 30+ rec yds | 60% | -151 | ✗ 4 | `+6` · 2026 5/7 pre-game
| 7 | Germie Bernard 3+ receptions | 59% | -143 | ✓ 5 | `+8` · 2026 4/6 pre-game
| 8 | Deshaun Watson 175+ pass yds | 66% | -196 | ✓ 324 | `+8` · 2026 4/7 pre-game

Legs 3/8 (expected 4.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Quinshon Judkins (CLE RB) | 33% | +205 | ✗ no TD | share 25% · team 1.96 TD · RZ-D 0.93 · pos-D 0.86 |
| Denzel Boston (CLE WR) | 31% | +218 | ✗ no TD | share 20% · team 1.96 TD · RZ-D 0.93 · pos-D 0.99 |
| DK Metcalf (PIT WR) | 31% | +227 | ✗ no TD | share 15% · team 2.35 TD · RZ-D 0.98 · pos-D 1.07 |
| Rico Dowdle (PIT RB) | 30% | +235 | ✓ TD | share 16% · team 2.35 TD · RZ-D 0.98 · pos-D 0.95 |

TD double (Quinshon Judkins + Denzel Boston): 14.1% · fair +608 ✗

**All-position slip** — 8.8% · fair +1041 ✗: Aaron Rodgers 35+ pass att ✗(25) · Jaylen Warren 40+ rush yds ✓(143) · KC Concepcion 4+ receptions ✗(3) · Harold Fannin Jr. 30+ rec yds ✓(154) · Quinshon Judkins ANYTIME TD ✗(no TD)

**All-position 8-leg** — 3.4% · fair +2821 ✗: Aaron Rodgers 35+ pass att ✗(25) · Jaylen Warren 40+ rush yds ✓(143) · KC Concepcion 4+ receptions ✗(3) · Harold Fannin Jr. 30+ rec yds ✓(154) · Quinshon Judkins 40+ rush yds ✗(25) · Denzel Boston 40+ rec yds ✗(37) · Quinshon Judkins ANYTIME TD ✗(no TD) · Denzel Boston ANYTIME TD ✗(no TD)


### IND@JAX — final 7-42
*O/U 46.5 · spread +10.0 · outdoor · grass · 13:00 ET*

**Personnel:** IND: Alec Pierce IR, Gould OUT; Walley (CB) OUT; Ogletree Q. JAX: Antonio Johnson (S) OUT; Meyers Q — singles only. IND -10.

**Injury report (as built):** IND OFF · Anthony Gould (WR) — Out · Concussion; IND DEF · Justin Walley (CB) — Out · Knee · DNP; IND OFF · Andrew Ogletree (TE) — Questionable · Knee · DNP; IND DEF · Bryce Boettcher (LB) — Questionable · Groin · DNP; JAX DEF · Antonio Johnson (S) — Out · Ankle · DNP; JAX OFF · Jakobi Meyers (WR) — Questionable · Hamstring · DNP

**Defensive leaks:** JAX D leaks passing interceptions to QBs: x1.25; JAX D leaks receptions to RBs: x1.18; JAX D leaks receiving yards to RBs: x1.17; IND D leaks receiving yards to TEs: x1.16

**Coordinators:** IND OC Jim Bob Cooter — continuity · measured pass 55% | DC Lou Anarumo (disguise_zone) · JAX OC Grant Udinski — continuity · measured pass 52% | DC Anthony Campanile (pressure)

**Props SGP** — 4-leg 17.9% · fair +457 ✗ · 6-leg 8.4% · fair +1097 ✗ · 8-leg 5.8% · fair +1640 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Parker Washington 40+ rec yds | 63% | -167 | ✗ 16 | `4-leg core` · 2026 5/6 pre-game
| 2 | Brenton Strange 30+ rec yds | 61% | -159 | ✓ 55 | `4-leg core` · 2026 4/6 pre-game
| 3 | Bhayshul Tuten 10+ carries | 64% | -176 | ✓ 16 | `4-leg core` · 2026 6/6 pre-game
| 4 | Daniel Jones o0.5 INT o0.5 | 64% | -179 | ✓ 2 INT | `4-leg core` · 2026 6/7 pre-game
| 5 | Keenan Allen 4+ receptions | 57% | -131 | ✓ 7 | `+6` · 2026 4/6 pre-game
| 6 | Jonathan Taylor 40+ rush yds | 55% | -124 | ✗ 23 | `+6` · 2026 7/7 pre-game
| 7 | Parker Washington 3+ receptions | 65% | -182 | ✗ 1 | `+8` · 2026 5/6 pre-game
| 8 | Daniel Jones 150+ pass yds | 67% | -201 | ✗ 144 | `+8` · 2026 5/7 pre-game

Legs 4/8 (expected 5.0)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Jonathan Taylor (IND RB) | 40% | +153 | ✗ no TD | share 30% · team 2.04 TD · RZ-D 0.91 · pos-D 0.84 |
| Bhayshul Tuten (JAX RB) | 32% | +211 | ✓ TD | share 12% · team 3.16 TD · RZ-D 0.97 · pos-D 0.99 |
| Parker Washington (JAX WR) | 30% | +234 | ✗ no TD | share 12% · team 3.16 TD · RZ-D 0.97 · pos-D 0.99 |
| Tyler Warren (IND TE) | 26% | +279 | ✗ no TD | share 14% · team 2.04 TD · RZ-D 0.91 · pos-D 1.07 |

TD double (Jonathan Taylor + Bhayshul Tuten): 14.7% · fair +580 ✗

**All-position slip** — 10.0% · fair +898 ✗: Daniel Jones 150+ pass yds ✗(144) · Bhayshul Tuten 10+ carries ✓(16) · Parker Washington 40+ rec yds ✗(16) · Brenton Strange 30+ rec yds ✓(55) · Jonathan Taylor ANYTIME TD ✗(no TD)

**All-position 8-leg** — 3.2% · fair +3006 ✗: Daniel Jones 150+ pass yds ✗(144) · Bhayshul Tuten 10+ carries ✓(16) · Parker Washington 40+ rec yds ✗(16) · Brenton Strange 30+ rec yds ✓(55) · Jonathan Taylor 40+ rush yds ✗(23) · Keenan Allen 4+ receptions ✓(7) · Jonathan Taylor ANYTIME TD ✗(no TD) · Bhayshul Tuten ANYTIME TD ✓(TD)


### LV@NYJ — final 38-33
*O/U 46.5 · spread +1.5 · outdoor · turf · 13:00 ET*

**Personnel:** NYJ: Breece Hall Q (quad) — Braelon Allen 17/24/17 carries the last three weeks regardless; Sweat (DT), Ossai (DE), Mitchell (T) OUT, Bailey doubtful. LV: Cousins starts; Bech Q; Runyon OUT.

**Injury report (as built):** LV DEF · Patrick Johnson (DE) — Out · Stinger · DNP; LV OFF · Carter Runyon (TE) — Out · Foot; LV OFF · Jackson Powers-Johnson (G) — Questionable · Back; LV OFF · Jack Bech (WR) — Questionable · Forearm; NYJ DEF · David Bailey (DE) — Doubtful · Groin · DNP; NYJ DEF · Joseph Ossai (DE) — Out · Ankle · DNP; NYJ OFF · Max Mitchell (T) — Out · Concussion · DNP; NYJ DEF · T'Vondre Sweat (DT) — Out · Knee · DNP

**Defensive leaks:** NYJ D leaks carries to RBs: x1.14 (worsening x1.07 L4); NYJ D leaks rushing yards to RBs: x1.11; LV D leaks rushing yards to RBs: x1.08 (worsening x1.41 L4)

**Coordinators:** LV OC Andrew Janocko — NEW (run_heavy) · measured pass 60% | DC Rob Leonard (four_man_rush) · NYJ OC Frank Reich — NEW (balanced) · measured pass 54% | DC Brian Duker (multiple)

**Props SGP** — 4-leg 16.8% · fair +497 ✗ · 6-leg 11.1% · fair +804 ✗ · 8-leg 5.3% · fair +1800 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Braelon Allen 10+ carries | 61% | -159 | ✓ 21 | `4-leg core` · 2026 5/7 pre-game
| 2 | Tre Tucker 40+ rec yds | 63% | -171 | ✗ 0 | `4-leg core` · 2026 6/7 pre-game
| 3 | Geno Smith 250+ pass yds | 61% | -155 | ✓ 290 | `4-leg core` · 2026 3/7 pre-game
| 4 | Adonai Mitchell 2+ receptions | 64% | -174 | ✓ 7 | `4-leg core` · 2026 2/3 pre-game
| 5 | Brock Bowers 80+ rec yds | 60% | -151 | ✓ 92 | `+6` · 2026 3/5 pre-game
| 6 | Michael Mayer 3+ receptions | 60% | -148 | ✓ 5 | `+6` · 2026 6/7 pre-game
| 7 | Ashton Jeanty 30+ rush yds | 59% | -146 | ✗ 9 | `+8` · 2026 4/7 pre-game
| 8 | Kirk Cousins 250+ pass yds | 59% | -144 | ✗ 247 | `+8` · 2026 4/7 pre-game

Legs 5/8 (expected 4.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Ashton Jeanty (LV RB) | 53% | -114 | ✗ no TD | share 26% · team 2.52 TD · RZ-D 1.08 · pos-D 1.22 |
| Brock Bowers (LV TE) | 43% | +134 | ✓ TD | share 21% · team 2.52 TD · RZ-D 1.08 · pos-D 1.0 |
| Garrett Wilson (NYJ WR) | 33% | +201 | ✗ no TD | share 13% · team 2.69 TD · RZ-D 1.1 · pos-D 1.07 |
| Braelon Allen (NYJ RB) | 32% | +213 | ✓ TD | share 12% · team 2.69 TD · RZ-D 1.1 · pos-D 1.06 |

TD double (Ashton Jeanty + Brock Bowers): 27.4% · fair +264 ✗

**All-position slip** — 12.7% · fair +685 ✗: Geno Smith 250+ pass yds ✓(290) · Braelon Allen 10+ carries ✓(21) · Tre Tucker 40+ rec yds ✗(0) · Brock Bowers 80+ rec yds ✓(92) · Ashton Jeanty ANYTIME TD ✗(no TD)

**All-position 8-leg** — 4.9% · fair +1948 ✗: Geno Smith 250+ pass yds ✓(290) · Braelon Allen 10+ carries ✓(21) · Tre Tucker 40+ rec yds ✗(0) · Brock Bowers 80+ rec yds ✓(92) · Ashton Jeanty 30+ rush yds ✗(9) · Adonai Mitchell 2+ receptions ✓(7) · Ashton Jeanty ANYTIME TD ✗(no TD) · Brock Bowers ANYTIME TD ✓(TD)


### MIN@DET — final 15-19
*O/U 46.5 · spread +3.0 · indoor · turf · 13:00 ET*

**Personnel:** DET: Kerby Joseph (S) OUT, McCreary (CB) Q — Minnesota passing x1.06. Pacheco IR — Gibbs 29 carries last week. MIN: Kyler Murray starts; Darrisaw (LT) DNP Wed. Dome.

**Injury report (as built):** DET DEF · Kerby Joseph (S) — Out · Knee; DET DEF · Roger McCreary (CB) — Questionable · Foot; MIN DEF · Jay Ward (S) — Questionable · Knee; MIN OFF · Christian Darrisaw (T) — nan · DNP

**Defensive leaks:** DET D leaks receiving yards to WRs: x1.19; DET D leaks passing interceptions to QBs: x1.18 (worsening x1.21 L4); DET D leaks receptions to WRs: x1.15 (worsening x1.06 L4); MIN D leaks passing interceptions to QBs: x1.40 (worsening x1.54 L4)

**Coordinators:** MIN OC Wes Phillips — continuity · measured pass 48% | DC Brian Flores (blitz_man) · DET OC Drew Petzing — NEW (pass_te) · measured pass 58% | DC Kelvin Sheppard (pressure)

**Props SGP** — 4-leg 17.2% · fair +483 ✗ · 6-leg 10.7% · fair +833 ✗ · 8-leg 5.5% · fair +1708 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Aaron Jones 40+ rush yds | 62% | -164 | ✗ 22 | `4-leg core` · 2026 5/6 pre-game
| 2 | Jared Goff 250+ pass yds | 62% | -162 | ✗ 176 | `4-leg core` · 2026 5/6 pre-game
| 3 | Kyler Murray 200+ pass yds | 63% | -169 | ✓ 210 | `4-leg core` · 2026 2/5 pre-game
| 4 | T.J. Hockenson 20+ rec yds | 63% | -169 | ✓ 58 | `4-leg core` · 2026 4/6 pre-game
| 5 | Jameson Williams 3+ receptions | 61% | -156 | ✓ 4 | `+6` · 2026 4/6 pre-game
| 6 | Jordan Addison 30+ rec yds | 63% | -172 | ✓ 66 | `+6` · 2026 2/5 pre-game
| 7 | Jahmyr Gibbs 3+ receptions | 60% | -150 | ✗ 2 | `+8` · 2026 6/6 pre-game
| 8 | Kyler Murray 20+ rush yds | 59% | -143 | ✓ 35 | `+8` · 2026 2/5 pre-game

Legs 5/8 (expected 4.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Justin Jefferson (MIN WR) | 44% | +129 | ✓ TD | share 21% · team 2.44 TD · RZ-D 1.05 · pos-D 1.11 |
| Jahmyr Gibbs (DET RB) | 40% | +148 | ✓ TD | share 24% · team 2.77 TD · RZ-D 0.68 · pos-D 0.87 |
| Aaron Jones (MIN RB) | 32% | +210 | ✗ no TD | share 17% · team 2.44 TD · RZ-D 1.05 · pos-D 0.96 |
| Jordan Addison (MIN WR) | 32% | +215 | ✗ no TD | share 14% · team 2.44 TD · RZ-D 1.05 · pos-D 1.11 |

TD double (Justin Jefferson + Jahmyr Gibbs): 19.8% · fair +405 **CASHED**

**All-position slip** — 12.3% · fair +714 ✗: Jared Goff 250+ pass yds ✗(176) · Aaron Jones 40+ rush yds ✗(22) · Jameson Williams 3+ receptions ✓(4) · T.J. Hockenson 20+ rec yds ✓(58) · Justin Jefferson ANYTIME TD ✓(TD)

**All-position 8-leg** — 5.1% · fair +1857 ✗: Jared Goff 250+ pass yds ✗(176) · Aaron Jones 40+ rush yds ✗(22) · Jameson Williams 3+ receptions ✓(4) · T.J. Hockenson 20+ rec yds ✓(58) · Jahmyr Gibbs 3+ receptions ✗(2) · Jordan Addison 30+ rec yds ✓(66) · Justin Jefferson ANYTIME TD ✓(TD) · Jahmyr Gibbs ANYTIME TD ✓(TD)


### TEN@CIN — final 36-43
*O/U 45.5 · spread +12.5 · outdoor · turf · 13:00 ET*

**Personnel:** TEN: Carnell Tate (WR1 by targets) OUT, Tyjae Spears OUT, Ridley Q, Franklin-Myers (DE) Q. CIN: Dugger (S) OUT; Allen/Hill/Lawrence (DTs) DNP Wed, no tag. CIN -12.5 — blowout haircut on TEN rushing and CIN passing applied.

**Injury report (as built):** CIN DEF · Kyle Dugger (S) — Out · Quadricep · DNP; CIN DEF · Joe Giles-Harris (LB) — Questionable · Calf; CIN DEF · Jonathan Allen (DT) — nan · DNP; CIN DEF · B.J. Hill (DT) — nan · DNP; CIN DEF · Dexter Lawrence (DT) — nan · DNP; TEN OFF · Tommy Townsend (P) — Out · Knee · DNP; TEN OFF · Tyjae Spears (RB) — Out · Knee · DNP; TEN OFF · Carnell Tate (WR) — Out · Shoulder · DNP

**Defensive leaks:** CIN D leaks receiving yards to TEs: x1.46; CIN D leaks receptions to TEs: x1.28; CIN D leaks passing interceptions to QBs: x1.15 (worsening x1.88 L4)

**Coordinators:** TEN OC Brian Daboll — NEW (pass_wr) · measured pass 56% | DC Gus Bradley (zone_cover3) · CIN OC Dan Pitcher — continuity · measured pass 62% | DC Al Golden (disguise_zone)

**Props SGP** — 4-leg 23.5% · fair +325 **CASHED** · 6-leg 12.3% · fair +711 **CASHED** · 8-leg 5.3% · fair +1792 **CASHED**

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Chase Brown 2+ receptions | 62% | -164 | ✓ 8 | `4-leg core` · 2026 6/6 pre-game
| 2 | Wan'Dale Robinson 30+ rec yds | 61% | -155 | ✓ 57 | `4-leg core` · 2026 3/7 pre-game
| 3 | Ja'Marr Chase 60+ rec yds | 61% | -154 | ✓ 141 | `4-leg core` · 2026 4/6 pre-game
| 4 | Joe Burrow 250+ pass yds | 59% | -142 | ✓ 462 | `4-leg core` · 2026 4/6 pre-game
| 5 | Tony Pollard 50+ rush yds | 66% | -194 | ✓ 117 | `+6` · 2026 5/7 pre-game
| 6 | Cam Ward 150+ pass yds | 67% | -205 | ✓ 304 | `+6` · 2026 5/7 pre-game
| 7 | Chase Brown 40+ rush yds | 59% | -144 | ✓ 55 | `+8` · 2026 3/6 pre-game
| 8 | Joe Burrow 35+ pass att | 55% | -124 | ✓ 48 | `+8` · 2026 3/6 pre-game

Legs 8/8 (expected 4.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Chase Brown (CIN RB) | 50% | -101 | ✗ no TD | share 20% · team 3.25 TD · RZ-D 1.12 · pos-D 1.09 |
| Ja'Marr Chase (CIN WR) | 48% | +107 | ✓ TD | share 18% · team 3.25 TD · RZ-D 1.12 · pos-D 1.04 |
| Tony Pollard (TEN RB) | 44% | +128 | ✓ TD | share 22% · team 1.85 TD · RZ-D 0.98 · pos-D 1.05 |
| Tee Higgins (CIN WR) | 39% | +156 | ✓ TD | share 14% · team 3.25 TD · RZ-D 1.12 · pos-D 1.04 |

TD double (Chase Brown + Ja'Marr Chase): 28.9% · fair +246 ✗

**All-position slip** — 18.8% · fair +432 ✗: Joe Burrow 250+ pass yds ✓(462) · Chase Brown 2+ receptions ✓(8) · Wan'Dale Robinson 30+ rec yds ✓(57) · Chase Brown ANYTIME TD ✗(no TD)

**All-position 8-leg** — 8.0% · fair +1150 ✗: Joe Burrow 250+ pass yds ✓(462) · Chase Brown 2+ receptions ✓(8) · Wan'Dale Robinson 30+ rec yds ✓(57) · Tony Pollard 50+ rush yds ✓(117) · Ja'Marr Chase 60+ rec yds ✓(141) · Chase Brown ANYTIME TD ✗(no TD) · Ja'Marr Chase ANYTIME TD ✓(TD)


### Cross-game combos — Week 8 — aggressive band (shipped)

**4-leg** — 15.8% · fair +534 — 2/4 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | ARI@DAL | Tyler Allgeier 10+ carries | 62% | ✓ 11 |
| 2 | TEN@CIN | Chase Brown 2+ receptions | 62% | ✓ 8 |
| 3 | MIN@DET | Aaron Jones 40+ rush yds | 62% | ✗ 22 |
| 4 | MIN@DET | Jared Goff 250+ pass yds | 62% | ✗ 176 |

**6-leg** — 6.0% · fair +1566 — 3/6 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | ARI@DAL | Tyler Allgeier 10+ carries | 62% | ✓ 11 |
| 2 | TEN@CIN | Chase Brown 2+ receptions | 62% | ✓ 8 |
| 3 | MIN@DET | Aaron Jones 40+ rush yds | 62% | ✗ 22 |
| 4 | MIN@DET | Jared Goff 250+ pass yds | 62% | ✗ 176 |
| 5 | ATL@TB | Bucky Irving 1+ receptions | 62% | ✗ 0 |
| 6 | CLE@PIT | Jaylen Warren 40+ rush yds | 62% | ✓ 143 |

**8-leg** — 2.0% · fair +4819 — 3/8 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | ARI@DAL | Tyler Allgeier 10+ carries | 62% | ✓ 11 |
| 2 | TEN@CIN | Chase Brown 2+ receptions | 62% | ✓ 8 |
| 3 | MIN@DET | Aaron Jones 40+ rush yds | 62% | ✗ 22 |
| 4 | MIN@DET | Jared Goff 250+ pass yds | 62% | ✗ 176 |
| 5 | ATL@TB | Bucky Irving 1+ receptions | 62% | ✗ 0 |
| 6 | CLE@PIT | Jaylen Warren 40+ rush yds | 62% | ✓ 143 |
| 7 | IND@JAX | Parker Washington 40+ rec yds | 63% | ✗ 16 |
| 8 | ARI@DAL | Kendrick Bourne 30+ rec yds | 61% | ✗ 29 |

**10-leg** — 0.9% · fair +10550 — 6/10 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | ARI@DAL | Tyler Allgeier 10+ carries | 62% | ✓ 11 |
| 2 | TEN@CIN | Chase Brown 2+ receptions | 62% | ✓ 8 |
| 3 | MIN@DET | Aaron Jones 40+ rush yds | 62% | ✗ 22 |
| 4 | MIN@DET | Jared Goff 250+ pass yds | 62% | ✗ 176 |
| 5 | ATL@TB | Bucky Irving 1+ receptions | 62% | ✗ 0 |
| 6 | CLE@PIT | Jaylen Warren 40+ rush yds | 62% | ✓ 143 |
| 7 | ARI@DAL | Michael Wilson 4+ receptions | 62% | ✓ 8 |
| 8 | IND@JAX | Parker Washington 40+ rec yds | 63% | ✗ 16 |
| 9 | IND@JAX | Brenton Strange 30+ rec yds | 61% | ✓ 55 |
| 10 | LV@NYJ | Braelon Allen 10+ carries | 61% | ✓ 21 |

**12-leg** — 0.3% · fair +32473 — 6/12 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | ARI@DAL | Tyler Allgeier 10+ carries | 62% | ✓ 11 |
| 2 | TEN@CIN | Chase Brown 2+ receptions | 62% | ✓ 8 |
| 3 | MIN@DET | Aaron Jones 40+ rush yds | 62% | ✗ 22 |
| 4 | MIN@DET | Jared Goff 250+ pass yds | 62% | ✗ 176 |
| 5 | ATL@TB | Bucky Irving 1+ receptions | 62% | ✗ 0 |
| 6 | CLE@PIT | Jaylen Warren 40+ rush yds | 62% | ✓ 143 |
| 7 | ARI@DAL | Michael Wilson 4+ receptions | 62% | ✓ 8 |
| 8 | IND@JAX | Parker Washington 40+ rec yds | 63% | ✗ 16 |
| 9 | IND@JAX | Brenton Strange 30+ rec yds | 61% | ✓ 55 |
| 10 | LV@NYJ | Braelon Allen 10+ carries | 61% | ✓ 21 |
| 11 | BAL@BUF | Lamar Jackson 20+ pass att | 63% | ✗ 1 |
| 12 | CLE@PIT | Aaron Rodgers 35+ pass att | 61% | ✗ 25 |


### ATD board (top 16) — Week 8 — aggressive band (shipped)

| # | Game | Player | Model | Fair | Result |
|---|---|---|---|---|---|
| 1 | ARI@DAL | Javonte Williams (RB) | 65% | -187 | ✗ no TD |
| 2 | BAL@BUF | Derrick Henry (RB) | 64% | -181 | ✓ TD |
| 3 | LV@NYJ | Ashton Jeanty (RB) | 53% | -114 | ✗ no TD |
| 4 | ARI@DAL | CeeDee Lamb (WR) | 52% | -109 | ✗ no TD |
| 5 | BAL@BUF | James Cook (RB) | 51% | -105 | ✓ TD |
| 6 | TEN@CIN | Chase Brown (RB) | 50% | -101 | ✗ no TD |
| 7 | ATL@TB | Bijan Robinson (RB) | 49% | +103 | ✗ no TD |
| 8 | TEN@CIN | Ja'Marr Chase (WR) | 48% | +107 | ✓ TD |
| 9 | BAL@BUF | Josh Allen (QB) | 48% | +111 | ✓ TD |
| 10 | ATL@TB | Bucky Irving (RB) | 47% | +111 | ✓ TD |
| 11 | TEN@CIN | Tony Pollard (RB) | 44% | +128 | ✓ TD |
| 12 | MIN@DET | Justin Jefferson (WR) | 44% | +129 | ✓ TD |
| 13 | LV@NYJ | Brock Bowers (TE) | 43% | +134 | ✓ TD |
| 14 | MIN@DET | Jahmyr Gibbs (RB) | 40% | +148 | ✓ TD |
| 15 | ARI@DAL | Michael Wilson (WR) | 40% | +150 | ✓ TD |
| 16 | IND@JAX | Jonathan Taylor (RB) | 40% | +153 | ✗ no TD |

Board: top-16 10/16 · top-8 3/8 · chalk triple 1/3

**2+ TD board (singles only):** Javonte Williams 28% (+251) · Derrick Henry 28% (+262) · Ashton Jeanty 18% (+462) · CeeDee Lamb 17% (+491) · James Cook 16% (+519) · Chase Brown 16% (+547)


### Scorecard — Week 8 — aggressive band (shipped)

**Legs 34/64 = 53% actual vs 62% expected · SGP4 1/8 · SGP6 1/8 · SGP8 1/8**

| Game | Final | Legs | SGP4 | SGP6 | SGP8 |
|---|---|---|---|---|---|
| TEN@CIN | 36-43 | 8/8 | ✓ | ✓ | ✓ |
| LV@NYJ | 38-33 | 5/8 | ✗ | ✗ | ✗ |
| MIN@DET | 15-19 | 5/8 | ✗ | ✗ | ✗ |
| ARI@DAL | 33-30 | 4/8 | ✗ | ✗ | ✗ |
| IND@JAX | 7-42 | 4/8 | ✗ | ✗ | ✗ |
| BAL@BUF | 10-36 | 3/8 | ✗ | ✗ | ✗ |
| CLE@PIT | 6-27 | 3/8 | ✗ | ✗ | ✗ |
| ATL@TB | 0-16 | 2/8 | ✗ | ✗ | ✗ |


## Week 8 — v1.9g replay (data through Week 7; built Nov 5 after grading)

*Engine v1.9g replay.* In-sample check of the v1.9g changes (return gate catches Lamar; exit-risk haircut; ATD calibration): 71% vs 77% against the shipped 63%; SGP4 2/8; ATD top-16 11/16. Mayfield's partial-return pattern was then added to the gate (he played 11 attempts the week before), so this replay understates the production rule.


### ARI@DAL — final 33-30
*O/U 54.5 · spread +7.0 · indoor · grass · 13:00 ET*

**Personnel:** DAL: Pickens Q (shoulder) — singles only; Turpin OUT; Kenny Clark, Bullard (DTs) Q; Locke (S) Q; Winters (LB) OUT. ARI: Nolen (DT) OUT; Melton (CB), Wingard (S), Froholdt (C) Q; Conner + Benson on IR — Allgeier/Knight split. Roof.

**Injury report (as built):** ARI OFF · Jon Gaines II (G) — Out · Ankle · DNP; ARI DEF · Walter Nolen (DT) — Out · Ankle · DNP; ARI OFF · Hjalte Froholdt (C) — Questionable · Knee · DNP; ARI DEF · Andrew Wingard (S) — Questionable · Knee; ARI DEF · Max Melton (CB) — Questionable · Knee; DAL OFF · KaVontae Turpin (WR) — Out · Ribs · DNP; DAL DEF · Dee Winters (LB) — Out · Calf · DNP; DAL DEF · Jonathan Bullard (DT) — Questionable · Calf

**Defensive leaks:** DAL D leaks receiving yards to RBs: x1.20; DAL D leaks receiving yards to WRs: x1.13 (worsening x1.15 L4); DAL D leaks passing yards to QBs: x1.08; ARI D leaks rushing yards to RBs: x1.15

**Coordinators:** ARI OC Nathaniel Hackett — NEW (run_heavy) · measured pass 61% | DC Nick Rallis (blitz_heavy) · DAL OC Klayton Adams — continuity · measured pass 60% | DC Christian Parker (two_high_shell)

**Props SGP** — 4-leg 33.6% · fair +197 **CASHED** · 6-leg 24.3% · fair +311 ✗ · 8-leg 17.0% · fair +488 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | CeeDee Lamb 4+ receptions | 76% | -324 | ✓ 7 | `4-leg core` · 2026 6/7 pre-game
| 2 | Michael Wilson 2+ receptions | 75% | -300 | ✓ 8 | `4-leg core` · 2026 7/7 pre-game
| 3 | Javonte Williams 40+ rush yds | 73% | -276 | ✓ 56 | `4-leg core` · 2026 6/7 pre-game
| 4 | Trey McBride 30+ rec yds | 72% | -256 | ✓ 72 | `4-leg core` · 2026 7/7 pre-game
| 5 | Jacoby Brissett 35+ pass att | 84% | -537 | ✗ 23 | `+6` · 2026 6/7 pre-game
| 6 | Dak Prescott 35+ pass att | 71% | -241 | ✗ 29 | `+6` · 2026 4/7 pre-game
| 7 | CeeDee Lamb 50+ rec yds | 71% | -248 | ✓ 58 | `+8` · 2026 5/7 pre-game
| 8 | Dak Prescott 250+ pass yds | 70% | -234 | ✗ 195 | `+8` · 2026 5/7 pre-game

Legs 5/8 (expected 5.9)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Javonte Williams (DAL RB) | 70% | -239 | ✗ no TD | share 24% · team 3.44 TD · RZ-D 1.12 · pos-D 1.13 |
| CeeDee Lamb (DAL WR) | 49% | +104 | ✗ no TD | share 18% · team 3.44 TD · RZ-D 1.12 · pos-D 1.06 |
| Tyler Allgeier (ARI RB) | 42% | +140 | ✓ TD | share 14% · team 2.66 TD · RZ-D 1.15 · pos-D 1.15 |
| Trey McBride (ARI TE) | 39% | +157 | ✓ TD | share 19% · team 2.66 TD · RZ-D 1.15 · pos-D 0.89 |

TD double (Javonte Williams + CeeDee Lamb): 38.0% · fair +163 ✗

**All-position slip** — 30.2% · fair +232 ✗: Jacoby Brissett 35+ pass att ✗(23) · Javonte Williams 40+ rush yds ✓(56) · CeeDee Lamb 4+ receptions ✓(7) · Trey McBride 7+ receptions ✓(7) · Javonte Williams ANYTIME TD ✗(no TD)

**All-position 8-leg** — 16.9% · fair +494 ✗: Jacoby Brissett 35+ pass att ✗(23) · Javonte Williams 40+ rush yds ✓(56) · CeeDee Lamb 4+ receptions ✓(7) · Trey McBride 7+ receptions ✓(7) · Dak Prescott 35+ pass att ✗(29) · Javonte Williams ANYTIME TD ✗(no TD) · CeeDee Lamb ANYTIME TD ✗(no TD)


### ATL@TB — final 0-16
*O/U 42.5 · spread +2.5 · outdoor · grass · 13:00 ET*

**Personnel:** TB: Egbuka OUT — Godwin / Tez Johnson / Otton absorb 8 tgt/g; Mayfield back under centre (11 att in a run-heavy Wk 7); Gainwell Q; Goedeke (T) Q. ATL: Brian Robinson OUT — Bijan's goal-line competition gone; Zaccheaus Q; Bowman + Terrell (CBs) Q; Lindstrom DNP Wed.

**Injury report (as built):** ATL OFF · Brian Robinson (RB) — Out · Hamstring · DNP; ATL DEF · Samson Ebukam (DE) — Questionable · Hamstring; ATL OFF · Olamide Zaccheaus (WR) — Questionable · Shoulder; ATL DEF · Charles Snowden (DE) — Questionable · Back; ATL DEF · Divine Deablo (LB) — Questionable · Forearm; ATL DEF · Billy Bowman Jr. (CB) — Questionable · Hamstring; ATL OFF · Beaux Collins (WR) — Questionable · Hip; ATL OFF · Cameron Williams (T) — Questionable · Ankle

**Defensive leaks:** TB D leaks receiving yards to RBs: x1.37; TB D leaks receiving yards to TEs: x1.18; TB D leaks receptions to RBs: x1.16; ATL D leaks receptions to RBs: x1.16 (worsening x1.32 L4)

**Coordinators:** ATL OC Tommy Rees — NEW (run_heavy) · measured pass 49% | DC Jeff Ulbrich (blitz_heavy) · TB OC Zac Robinson — NEW (pass_wr) · measured pass 44% | DC Todd Bowles (blitz_heavy)

**Props SGP** — 4-leg 43.5% · fair +130 ✗ · 6-leg 23.8% · fair +320 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Chris Godwin Jr. 3+ receptions | 78% | -354 | ✗ 0 | `4-leg core` · 2026 7/7 pre-game
| 2 | Baker Mayfield 20+ pass att | 79% | -383 | ✗ 3 | `4-leg core` · 2026 3/4 pre-game
| 3 | Cade Otton 2+ receptions | 76% | -320 | – DNP | `4-leg core` · 2026 5/7 pre-game
| 4 | Bijan Robinson 15+ carries | 76% | -311 | ✓ 19 | `4-leg core` · 2026 6/7 pre-game
| 5 | Bucky Irving 40+ rush yds | 75% | -296 | ✓ 170 | `+6` · 2026 7/7 pre-game
| 6 | Drake London 20+ rec yds | 74% | -286 | ✗ 8 | `+6` · 2026 7/7 pre-game
| 7 | Michael Penix Jr. 20+ pass att | 83% | -485 | ✓ 24 | `+8` · 2026 5/5 pre-game

Legs 3/6 (expected 5.4)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Bucky Irving (TB RB) | 51% | -105 | ✓ TD | share 21% · team 2.52 TD · RZ-D 0.96 · pos-D 1.02 |
| Bijan Robinson (ATL RB) | 48% | +108 | ✗ no TD | share 26% · team 2.24 TD · RZ-D 1.03 · pos-D 0.88 |
| Drake London (ATL WR) | 29% | +247 | ✗ no TD | share 18% · team 2.24 TD · RZ-D 1.03 · pos-D 0.93 |

TD double (Bucky Irving + Bijan Robinson): 25.8% · fair +287 ✗

**All-position slip** — 26.8% · fair +273 ✗: Baker Mayfield 20+ pass att ✗(3) · Bijan Robinson 15+ carries ✓(19) · Chris Godwin Jr. 3+ receptions ✗(0) · Cade Otton 2+ receptions –(DNP) · Bucky Irving ANYTIME TD ✓(TD)

**All-position 8-leg** — 11.3% · fair +786 ✗: Baker Mayfield 20+ pass att ✗(3) · Bijan Robinson 15+ carries ✓(19) · Chris Godwin Jr. 3+ receptions ✗(0) · Cade Otton 2+ receptions –(DNP) · Bucky Irving 40+ rush yds ✓(170) · Drake London 20+ rec yds ✗(8) · Bucky Irving ANYTIME TD ✓(TD) · Bijan Robinson ANYTIME TD ✗(no TD)


### BAL@BUF — final 10-36
*O/U 54.5 · spread +3.0 · outdoor · grass · 13:00 ET*

**Personnel:** BAL: Lamar Jackson off the report — expected to start (Rapoport). Hawkins (S) OUT; T.J. Tampa (CB), Randall (RB) Q; Stanley, Campbell DNP (vet rest). BUF: Kincaid (TE, chest) Q, DJ Moore (WR) Q, Alford (CB) Q, Gaines (DT) Q, Spencer Brown (T) Q — all singles only until inactives. Highest total of the window (54.5).

**Injury report (as built):** BAL DEF · Jaylinn Hawkins (S) — Out · Knee · DNP; BAL OFF · Olaivavega Ioane (G) — Out · Knee; BAL DEF · T.J. Tampa (CB) — Questionable · Knee; BAL OFF · Adam Randall (RB) — Questionable · Neck; BAL DEF · Calais Campbell (DT) — nan · DNP; BAL OFF · Ronnie Stanley (T) — nan · DNP; BUF OFF · Tyrell Shavers (WR) — Out · Knee; BUF OFF · DJ Moore (WR) — Questionable · Shoulder

**Defensive leaks:** BUF D leaks receptions to RBs: x1.13 (worsening x1.26 L4); BUF D leaks receiving yards to RBs: x1.12 (worsening x1.40 L4); BUF D leaks passing interceptions to QBs: x1.11; BAL D leaks receiving yards to WRs: x1.18 (worsening x1.10 L4)

**Coordinators:** BAL OC Declan Doyle — NEW (pass_wr) · measured pass 50% | DC Anthony Weaver (pressure) · BUF OC Pete Carmichael Jr. — NEW (balanced) · measured pass 49% | DC Jim Leonhard (disguise_zone)

**Props SGP** — 4-leg 39.7% · fair +152 ✗ · 6-leg 23.7% · fair +322 ✗ · 8-leg 17.9% · fair +459 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Mark Andrews 2+ receptions | 77% | -339 | ✓ 3 | `4-leg core` · 2026 6/7 pre-game
| 2 | Zay Flowers 5+ receptions | 79% | -378 | ✗ 0 | `4-leg core` · 2026 6/6 pre-game
| 3 | Josh Allen 150+ pass yds | 80% | -396 | ✓ 289 | `4-leg core` · 2026 6/6 pre-game
| 4 | James Cook 15+ carries | 76% | -308 | ✓ 21 | `4-leg core` · 2026 4/6 pre-game
| 5 | Derrick Henry 30+ rush yds | 74% | -288 | ✓ 53 | `+6` · 2026 7/7 pre-game
| 6 | Keon Coleman 20+ rec yds | 73% | -272 | ✗ 4 | `+6` · 2026 4/6 pre-game
| 7 | Josh Allen 20+ pass att | 82% | -456 | ✓ 34 | `+8` · 2026 5/6 pre-game
| 8 | Zay Flowers 60+ rec yds | 71% | -247 | ✗ 0 | `+8` · 2026 5/6 pre-game

Legs 5/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Derrick Henry (BAL RB) | 68% | -215 | ✓ TD | share 31% · team 2.88 TD · RZ-D 1.06 · pos-D 1.2 |
| James Cook (BUF RB) | 56% | -129 | ✓ TD | share 22% · team 3.22 TD · RZ-D 0.97 · pos-D 1.0 |
| Josh Allen (BUF QB) | 53% | -114 | ✓ TD | share 19% · team 3.22 TD · RZ-D 0.97 · pos-D 1.18 |
| Mark Andrews (BAL TE) | 30% | +231 | ✗ no TD | share 14% · team 2.88 TD · RZ-D 1.06 · pos-D 0.79 |

TD double (Derrick Henry + James Cook): 39.1% · fair +156 **CASHED**

**All-position slip** — 30.8% · fair +225 ✗: Josh Allen 150+ pass yds ✓(289) · James Cook 15+ carries ✓(21) · Zay Flowers 5+ receptions ✗(0) · Mark Andrews 2+ receptions ✓(3) · Derrick Henry ANYTIME TD ✓(TD)

**All-position 8-leg** — 15.0% · fair +566 ✗: Josh Allen 150+ pass yds ✓(289) · James Cook 15+ carries ✓(21) · Zay Flowers 5+ receptions ✗(0) · Mark Andrews 2+ receptions ✓(3) · Derrick Henry 30+ rush yds ✓(53) · Keon Coleman 20+ rec yds ✗(4) · Derrick Henry ANYTIME TD ✓(TD) · James Cook ANYTIME TD ✓(TD)


### CLE@PIT — final 6-27
*O/U 38.5 · spread +3.5 · outdoor · grass · 13:00 ET*

**Personnel:** PIT: Echols + Slaughter (CBs) OUT — Cleveland passing x1.06; Pittman IR; Skowronek Q. CLE: Howard (T), Harden (CB), D. Thomas (S) Q; Judkins back (17 carries Wk 7). Lowest total of the window (38.5).

**Injury report (as built):** CLE OFF · Tytus Howard (T) — Questionable · Concussion · DNP; CLE DEF · Daniel Thomas (S) — Questionable · Ankle; CLE DEF · Myles Harden (CB) — Questionable · Hamstring; PIT DEF · Brandin Echols (CB) — Out · Hamstring · DNP; PIT DEF · Doneiko Slaughter (CB) — Out · Hamstring · DNP; PIT OFF · Ben Skowronek (WR) — Questionable · Calf

**Defensive leaks:** PIT D leaks passing interceptions to QBs: x1.36 (worsening x1.05 L4); PIT D leaks receptions to TEs: x1.12; PIT D leaks receiving yards to TEs: x1.10

**Coordinators:** CLE OC Travis Switzer — NEW (run_heavy) · measured pass 56% | DC Mike Rutenberg (multiple) · PIT OC Brian Angelichio — NEW (pass_te) · measured pass 60% | DC Patrick Graham (multiple)

**Props SGP** — 4-leg 38.0% · fair +163 ✗ · 6-leg 23.6% · fair +324 ✗ · 8-leg 17.3% · fair +476 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Deshaun Watson 150+ pass yds | 78% | -362 | ✓ 324 | `4-leg core` · 2026 6/7 pre-game
| 2 | Aaron Rodgers 175+ pass yds | 77% | -337 | ✗ 172 | `4-leg core` · 2026 7/7 pre-game
| 3 | Quinshon Judkins 10+ carries | 79% | -386 | ✓ 11 | `4-leg core` · 2026 6/6 pre-game
| 4 | KC Concepcion 2+ receptions | 76% | -316 | ✓ 3 | `4-leg core` · 2026 6/7 pre-game
| 5 | DK Metcalf 2+ receptions | 75% | -300 | ✗ 1 | `+6` · 2026 7/7 pre-game
| 6 | Jaylen Warren 20+ rush yds | 72% | -263 | ✓ 143 | `+6` · 2026 7/7 pre-game
| 7 | Denzel Boston 20+ rec yds | 71% | -248 | ✓ 37 | `+8` · 2026 6/7 pre-game
| 8 | Deshaun Watson 25+ pass att | 73% | -271 | ✓ 39 | `+8` · 2026 6/7 pre-game

Legs 6/8 (expected 6.0)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Rico Dowdle (PIT RB) | 33% | +204 | ✓ TD | share 17% · team 2.35 TD · RZ-D 0.98 · pos-D 0.97 |
| Quinshon Judkins (CLE RB) | 31% | +221 | ✗ no TD | share 25% · team 1.96 TD · RZ-D 0.91 · pos-D 0.85 |
| Jaylen Warren (PIT RB) | 30% | +232 | ✓ TD | share 15% · team 2.35 TD · RZ-D 0.98 · pos-D 0.97 |
| Denzel Boston (CLE WR) | 27% | +269 | ✗ no TD | share 23% · team 1.96 TD · RZ-D 0.91 · pos-D 0.98 |

TD double (Rico Dowdle + Quinshon Judkins): 11.5% · fair +766 ✗

**All-position slip** — 14.8% · fair +576 **CASHED**: Deshaun Watson 150+ pass yds ✓(324) · Quinshon Judkins 10+ carries ✓(11) · KC Concepcion 2+ receptions ✓(3) · Harold Fannin Jr. 3+ receptions ✓(10) · Rico Dowdle ANYTIME TD ✓(TD)

**All-position 8-leg** — 6.0% · fair +1569 ✗: Deshaun Watson 150+ pass yds ✓(324) · Quinshon Judkins 10+ carries ✓(11) · KC Concepcion 2+ receptions ✓(3) · Harold Fannin Jr. 3+ receptions ✓(10) · Jaylen Warren 20+ rush yds ✓(143) · Denzel Boston 20+ rec yds ✓(37) · Rico Dowdle ANYTIME TD ✓(TD) · Quinshon Judkins ANYTIME TD ✗(no TD)


### IND@JAX — final 7-42
*O/U 45.5 · spread +10.0 · outdoor · grass · 13:00 ET*

**Personnel:** IND: Alec Pierce IR, Gould OUT; Walley (CB) OUT; Ogletree Q. JAX: Antonio Johnson (S) OUT; Meyers Q — singles only. IND -10.

**Injury report (as built):** IND OFF · Anthony Gould (WR) — Out · Concussion; IND DEF · Justin Walley (CB) — Out · Knee · DNP; IND OFF · Andrew Ogletree (TE) — Questionable · Knee · DNP; IND DEF · Bryce Boettcher (LB) — Questionable · Groin · DNP; JAX DEF · Antonio Johnson (S) — Out · Ankle · DNP; JAX OFF · Jakobi Meyers (WR) — Questionable · Hamstring · DNP

**Defensive leaks:** JAX D leaks passing interceptions to QBs: x1.25 (worsening x1.14 L4); JAX D leaks receptions to RBs: x1.18 (worsening x1.13 L4); JAX D leaks receiving yards to RBs: x1.17; IND D leaks receiving yards to TEs: x1.16

**Coordinators:** IND OC Jim Bob Cooter — continuity · measured pass 54% | DC Lou Anarumo (disguise_zone) · JAX OC Grant Udinski — continuity · measured pass 50% | DC Anthony Campanile (pressure)

**Props SGP** — 4-leg 45.9% · fair +118 ✗ · 6-leg 25.6% · fair +291 ✗ · 8-leg 18.6% · fair +437 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Trevor Lawrence 225+ pass yds | 78% | -351 | ✗ 210 | `4-leg core` · 2026 4/6 pre-game
| 2 | Brenton Strange 3+ receptions | 78% | -362 | ✗ 2 | `4-leg core` · 2026 4/6 pre-game
| 3 | Parker Washington 2+ receptions | 79% | -366 | ✗ 1 | `4-leg core` · 2026 5/6 pre-game
| 4 | Jonathan Taylor 10+ carries | 79% | -380 | ✗ 8 | `4-leg core` · 2026 7/7 pre-game
| 5 | Bhayshul Tuten 20+ rush yds | 77% | -331 | ✓ 104 | `+6` · 2026 6/6 pre-game
| 6 | Daniel Jones 25+ pass att | 73% | -273 | ✓ 28 | `+6` · 2026 6/7 pre-game
| 7 | Brenton Strange 20+ rec yds | 72% | -258 | ✓ 55 | `+8` · 2026 5/6 pre-game
| 8 | Parker Washington 30+ rec yds | 71% | -245 | ✗ 16 | `+8` · 2026 5/6 pre-game

Legs 3/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Bhayshul Tuten (JAX RB) | 39% | +157 | ✓ TD | share 13% · team 3.11 TD · RZ-D 0.98 · pos-D 1.04 |
| Jonathan Taylor (IND RB) | 37% | +168 | ✗ no TD | share 31% · team 1.99 TD · RZ-D 0.91 · pos-D 0.83 |
| Parker Washington (JAX WR) | 26% | +285 | ✗ no TD | share 11% · team 3.11 TD · RZ-D 0.98 · pos-D 1.0 |
| Trevor Lawrence (JAX QB) | 21% | +377 | ✗ no TD | share 8% · team 3.11 TD · RZ-D 0.98 · pos-D 0.91 |

TD double (Bhayshul Tuten + Jonathan Taylor): 16.0% · fair +526 ✗

**All-position slip** — 22.4% · fair +347 ✗: Trevor Lawrence 225+ pass yds ✗(210) · Jonathan Taylor 10+ carries ✗(8) · Parker Washington 2+ receptions ✗(1) · Brenton Strange 3+ receptions ✗(2) · Bhayshul Tuten ANYTIME TD ✓(TD)

**All-position 8-leg** — 8.2% · fair +1112 ✗: Trevor Lawrence 225+ pass yds ✗(210) · Jonathan Taylor 10+ carries ✗(8) · Parker Washington 2+ receptions ✗(1) · Brenton Strange 3+ receptions ✗(2) · Bhayshul Tuten 20+ rush yds ✓(104) · Daniel Jones 25+ pass att ✓(28) · Bhayshul Tuten ANYTIME TD ✓(TD) · Jonathan Taylor ANYTIME TD ✗(no TD)


### LV@NYJ — final 38-33
*O/U 46.5 · spread +1.5 · outdoor · grass · 13:00 ET*

**Personnel:** NYJ: Breece Hall Q (quad) — Braelon Allen 17/24/17 carries the last three weeks regardless; Sweat (DT), Ossai (DE), Mitchell (T) OUT, Bailey doubtful. LV: Cousins starts; Bech Q; Runyon OUT.

**Injury report (as built):** LV DEF · Patrick Johnson (DE) — Out · Stinger · DNP; LV OFF · Carter Runyon (TE) — Out · Foot; LV OFF · Jackson Powers-Johnson (G) — Questionable · Back; LV OFF · Jack Bech (WR) — Questionable · Forearm; NYJ DEF · David Bailey (DE) — Doubtful · Groin · DNP; NYJ DEF · Joseph Ossai (DE) — Out · Ankle · DNP; NYJ OFF · Max Mitchell (T) — Out · Concussion · DNP; NYJ DEF · T'Vondre Sweat (DT) — Out · Knee · DNP

**Defensive leaks:** NYJ D leaks carries to RBs: x1.14 (worsening x1.29 L4); NYJ D leaks rushing yards to RBs: x1.11 (worsening x1.22 L4)

**Coordinators:** LV OC Andrew Janocko — NEW (run_heavy) · measured pass 59% | DC Rob Leonard (four_man_rush) · NYJ OC Frank Reich — NEW (balanced) · measured pass 54% | DC Brian Duker (multiple)

**Props SGP** — 4-leg 41.9% · fair +138 ✗ · 6-leg 25.2% · fair +296 ✗ · 8-leg 19.3% · fair +419 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Geno Smith 25+ pass att | 79% | -373 | ✓ 32 | `4-leg core` · 2026 5/7 pre-game
| 2 | Garrett Wilson 3+ receptions | 76% | -326 | ✓ 6 | `4-leg core` · 2026 6/7 pre-game
| 3 | Tre Tucker 2+ receptions | 76% | -326 | ✗ 0 | `4-leg core` · 2026 7/7 pre-game
| 4 | Kirk Cousins 25+ pass att | 76% | -313 | ✓ 26 | `4-leg core` · 2026 7/7 pre-game
| 5 | Brock Bowers 50+ rec yds | 72% | -263 | ✓ 92 | `+6` · 2026 5/5 pre-game
| 6 | Braelon Allen 10+ carries | 72% | -259 | ✓ 21 | `+6` · 2026 5/7 pre-game
| 7 | Kirk Cousins 175+ pass yds | 76% | -312 | ✓ 247 | `+8` · 2026 6/7 pre-game
| 8 | Geno Smith 175+ pass yds | 73% | -276 | ✓ 290 | `+8` · 2026 6/7 pre-game

Legs 7/8 (expected 6.0)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Ashton Jeanty (LV RB) | 50% | -102 | ✗ no TD | share 23% · team 2.52 TD · RZ-D 1.09 · pos-D 1.2 |
| Brock Bowers (LV TE) | 46% | +115 | ✓ TD | share 22% · team 2.52 TD · RZ-D 1.09 · pos-D 1.05 |
| Braelon Allen (NYJ RB) | 36% | +177 | ✓ TD | share 13% · team 2.69 TD · RZ-D 1.07 · pos-D 1.06 |
| Garrett Wilson (NYJ WR) | 34% | +196 | ✗ no TD | share 16% · team 2.69 TD · RZ-D 1.07 · pos-D 1.09 |

TD double (Ashton Jeanty + Brock Bowers): 27.5% · fair +263 ✗

**All-position slip** — 20.2% · fair +396 ✗: Geno Smith 25+ pass att ✓(32) · Braelon Allen 10+ carries ✓(21) · Garrett Wilson 3+ receptions ✓(6) · Mason Taylor 2+ receptions ✓(3) · Ashton Jeanty ANYTIME TD ✗(no TD)

**All-position 8-leg** — 10.4% · fair +864 ✗: Geno Smith 25+ pass att ✓(32) · Braelon Allen 10+ carries ✓(21) · Garrett Wilson 3+ receptions ✓(6) · Mason Taylor 2+ receptions ✓(3) · Tre Tucker 20+ rec yds ✗(0) · Brock Bowers 50+ rec yds ✓(92) · Ashton Jeanty ANYTIME TD ✗(no TD) · Brock Bowers ANYTIME TD ✓(TD)


### MIN@DET — final 15-19
*O/U 46.5 · spread +3.0 · indoor · grass · 13:00 ET*

**Personnel:** DET: Kerby Joseph (S) OUT, McCreary (CB) Q — Minnesota passing x1.06. Pacheco IR — Gibbs 29 carries last week. MIN: Kyler Murray starts; Darrisaw (LT) DNP Wed. Dome.

**Injury report (as built):** DET DEF · Kerby Joseph (S) — Out · Knee; DET DEF · Roger McCreary (CB) — Questionable · Foot; MIN DEF · Jay Ward (S) — Questionable · Knee; MIN OFF · Christian Darrisaw (T) — nan · DNP

**Defensive leaks:** DET D leaks receiving yards to WRs: x1.19 (worsening x1.07 L4); DET D leaks passing interceptions to QBs: x1.18; DET D leaks receptions to WRs: x1.15 (worsening x1.19 L4); MIN D leaks passing interceptions to QBs: x1.40

**Coordinators:** MIN OC Wes Phillips — continuity · measured pass 49% | DC Brian Flores (blitz_man) · DET OC Drew Petzing — NEW (pass_te) · measured pass 55% | DC Kelvin Sheppard (pressure)

**Props SGP** — 4-leg 36.6% · fair +173 ✗ · 6-leg 26.1% · fair +283 ✗ · 8-leg 16.4% · fair +512 ✗

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Jared Goff 200+ pass yds | 78% | -357 | ✗ 176 | `4-leg core` · 2026 6/6 pre-game
| 2 | Kyler Murray 150+ pass yds | 80% | -402 | ✓ 210 | `4-leg core` · 2026 4/5 pre-game
| 3 | Aaron Jones 20+ rush yds | 76% | -314 | ✓ 22 | `4-leg core` · 2026 6/6 pre-game
| 4 | Jordan Addison 20+ rec yds | 76% | -308 | ✓ 66 | `4-leg core` · 2026 4/5 pre-game
| 5 | T.J. Hockenson 2+ receptions | 75% | -299 | ✓ 4 | `+6` · 2026 5/6 pre-game
| 6 | Amon-Ra St. Brown 20+ rec yds | 74% | -286 | ✓ 46 | `+6` · 2026 5/6 pre-game
| 7 | Jameson Williams 2+ receptions | 73% | -273 | ✓ 4 | `+8` · 2026 6/6 pre-game
| 8 | Jahmyr Gibbs 30+ rush yds | 72% | -251 | ✓ 153 | `+8` · 2026 6/6 pre-game

Legs 7/8 (expected 6.0)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Jahmyr Gibbs (DET RB) | 44% | +126 | ✓ TD | share 25% · team 2.77 TD · RZ-D 0.68 · pos-D 0.88 |
| Justin Jefferson (MIN WR) | 39% | +157 | ✓ TD | share 22% · team 2.44 TD · RZ-D 1.06 · pos-D 1.11 |
| Jordan Mason (MIN RB) | 33% | +205 | ✗ no TD | share 16% · team 2.44 TD · RZ-D 1.06 · pos-D 0.94 |
| T.J. Hockenson (MIN TE) | 32% | +211 | ✓ TD | share 12% · team 2.44 TD · RZ-D 1.06 · pos-D 1.26 |

TD double (Jahmyr Gibbs + Justin Jefferson): 18.6% · fair +437 **CASHED**

**All-position slip** — 19.0% · fair +427 ✗: Jared Goff 200+ pass yds ✗(176) · Aaron Jones 20+ rush yds ✓(22) · Jordan Addison 20+ rec yds ✓(66) · T.J. Hockenson 2+ receptions ✓(4) · Jahmyr Gibbs ANYTIME TD ✓(TD)

**All-position 8-leg** — 8.2% · fair +1126 ✗: Jared Goff 200+ pass yds ✗(176) · Aaron Jones 20+ rush yds ✓(22) · Jordan Addison 20+ rec yds ✓(66) · T.J. Hockenson 2+ receptions ✓(4) · Jahmyr Gibbs 30+ rush yds ✓(153) · Amon-Ra St. Brown 20+ rec yds ✓(46) · Jahmyr Gibbs ANYTIME TD ✓(TD) · Justin Jefferson ANYTIME TD ✓(TD)


### TEN@CIN — final 36-43
*O/U 45.5 · spread +13.5 · outdoor · grass · 13:00 ET*

**Personnel:** TEN: Carnell Tate (WR1 by targets) OUT, Tyjae Spears OUT, Ridley Q, Franklin-Myers (DE) Q. CIN: Dugger (S) OUT; Allen/Hill/Lawrence (DTs) DNP Wed, no tag. CIN -12.5 — blowout haircut on TEN rushing and CIN passing applied.

**Injury report (as built):** CIN DEF · Kyle Dugger (S) — Out · Quadricep · DNP; CIN DEF · Joe Giles-Harris (LB) — Questionable · Calf; CIN DEF · Jonathan Allen (DT) — nan · DNP; CIN DEF · B.J. Hill (DT) — nan · DNP; CIN DEF · Dexter Lawrence (DT) — nan · DNP; TEN OFF · Tommy Townsend (P) — Out · Knee · DNP; TEN OFF · Tyjae Spears (RB) — Out · Knee · DNP; TEN OFF · Carnell Tate (WR) — Out · Shoulder · DNP

**Defensive leaks:** CIN D leaks receiving yards to TEs: x1.46; CIN D leaks receptions to TEs: x1.28; CIN D leaks passing interceptions to QBs: x1.15 (worsening x1.25 L4)

**Coordinators:** TEN OC Brian Daboll — NEW (pass_wr) · measured pass 57% | DC Gus Bradley (zone_cover3) · CIN OC Dan Pitcher — continuity · measured pass 64% | DC Al Golden (disguise_zone)

**Props SGP** — 4-leg 37.7% · fair +165 **CASHED** · 6-leg 22.6% · fair +342 **CASHED** · 8-leg 17.4% · fair +475 **CASHED**

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Wan'Dale Robinson 3+ receptions | 78% | -353 | ✓ 6 | `4-leg core` · 2026 6/7 pre-game
| 2 | Joe Burrow 200+ pass yds | 77% | -339 | ✓ 462 | `4-leg core` · 2026 5/6 pre-game
| 3 | Chase Brown 20+ rush yds | 76% | -322 | ✓ 55 | `4-leg core` · 2026 5/6 pre-game
| 4 | Cam Ward 25+ pass att | 75% | -306 | ✓ 40 | `4-leg core` · 2026 5/7 pre-game
| 5 | Ja'Marr Chase 4+ receptions | 74% | -284 | ✓ 11 | `+6` · 2026 4/6 pre-game
| 6 | Tony Pollard 15+ carries | 74% | -284 | ✓ 21 | `+6` · 2026 4/7 pre-game
| 7 | Tee Higgins 50+ rec yds | 73% | -266 | ✓ 155 | `+8` · 2026 5/6 pre-game
| 8 | Joe Burrow 30+ pass att | 79% | -374 | ✓ 48 | `+8` · 2026 6/6 pre-game

Legs 8/8 (expected 6.1)

**Anytime TD (separate ticket)**

| Player | Model | Fair | Result | Decomposition |
|---|---|---|---|---|
| Chase Brown (CIN RB) | 54% | -117 | ✗ no TD | share 19% · team 3.3 TD · RZ-D 1.14 · pos-D 1.06 |
| Ja'Marr Chase (CIN WR) | 47% | +112 | ✓ TD | share 18% · team 3.3 TD · RZ-D 1.14 · pos-D 1.09 |
| Tony Pollard (TEN RB) | 43% | +134 | ✓ TD | share 23% · team 1.79 TD · RZ-D 0.99 · pos-D 1.07 |
| Tee Higgins (CIN WR) | 40% | +153 | ✓ TD | share 14% · team 3.3 TD · RZ-D 1.14 · pos-D 1.09 |

TD double (Chase Brown + Ja'Marr Chase): 29.6% · fair +238 ✗

**All-position slip** — 29.8% · fair +236 ✗: Joe Burrow 200+ pass yds ✓(462) · Chase Brown 20+ rush yds ✓(55) · Wan'Dale Robinson 3+ receptions ✓(6) · Chase Brown ANYTIME TD ✗(no TD)

**All-position 8-leg** — 13.5% · fair +641 ✗: Joe Burrow 200+ pass yds ✓(462) · Chase Brown 20+ rush yds ✓(55) · Wan'Dale Robinson 3+ receptions ✓(6) · Tony Pollard 15+ carries ✓(21) · Ja'Marr Chase 4+ receptions ✓(11) · Chase Brown ANYTIME TD ✗(no TD) · Ja'Marr Chase ANYTIME TD ✓(TD)


### Cross-game combos — Week 8 — v1.9g replay (data through Week 7; built Nov 5 after grading)

**4-leg** — 34.2% · fair +192 — 1/4 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | ATL@TB | Chris Godwin Jr. 3+ receptions | 78% | ✗ 0 |
| 2 | MIN@DET | Jared Goff 200+ pass yds | 78% | ✗ 176 |
| 3 | TEN@CIN | Wan'Dale Robinson 3+ receptions | 78% | ✓ 6 |
| 4 | IND@JAX | Trevor Lawrence 225+ pass yds | 78% | ✗ 210 |

**6-leg** — 20.9% · fair +379 — 3/6 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | ATL@TB | Chris Godwin Jr. 3+ receptions | 78% | ✗ 0 |
| 2 | MIN@DET | Jared Goff 200+ pass yds | 78% | ✗ 176 |
| 3 | TEN@CIN | Wan'Dale Robinson 3+ receptions | 78% | ✓ 6 |
| 4 | IND@JAX | Trevor Lawrence 225+ pass yds | 78% | ✗ 210 |
| 5 | LV@NYJ | Geno Smith 25+ pass att | 79% | ✓ 32 |
| 6 | TEN@CIN | Joe Burrow 30+ pass att | 79% | ✓ 48 |

**8-leg** — 12.9% · fair +674 — 4/8 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | ATL@TB | Chris Godwin Jr. 3+ receptions | 78% | ✗ 0 |
| 2 | MIN@DET | Jared Goff 200+ pass yds | 78% | ✗ 176 |
| 3 | TEN@CIN | Wan'Dale Robinson 3+ receptions | 78% | ✓ 6 |
| 4 | IND@JAX | Trevor Lawrence 225+ pass yds | 78% | ✗ 210 |
| 5 | LV@NYJ | Geno Smith 25+ pass att | 79% | ✓ 32 |
| 6 | TEN@CIN | Joe Burrow 30+ pass att | 79% | ✓ 48 |
| 7 | IND@JAX | Jonathan Taylor 10+ carries | 79% | ✗ 8 |
| 8 | CLE@PIT | Quinshon Judkins 10+ carries | 79% | ✓ 11 |

**10-leg** — 8.8% · fair +1042 — 5/10 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | ATL@TB | Chris Godwin Jr. 3+ receptions | 78% | ✗ 0 |
| 2 | MIN@DET | Jared Goff 200+ pass yds | 78% | ✗ 176 |
| 3 | TEN@CIN | Wan'Dale Robinson 3+ receptions | 78% | ✓ 6 |
| 4 | IND@JAX | Trevor Lawrence 225+ pass yds | 78% | ✗ 210 |
| 5 | IND@JAX | Brenton Strange 3+ receptions | 78% | ✗ 2 |
| 6 | CLE@PIT | Deshaun Watson 150+ pass yds | 78% | ✓ 324 |
| 7 | LV@NYJ | Geno Smith 25+ pass att | 79% | ✓ 32 |
| 8 | TEN@CIN | Joe Burrow 30+ pass att | 79% | ✓ 48 |
| 9 | ATL@TB | Baker Mayfield 20+ pass att | 79% | ✗ 3 |
| 10 | CLE@PIT | Quinshon Judkins 10+ carries | 79% | ✓ 11 |

**12-leg** — 5.0% · fair +1906 — 7/12 ✗
| # | Game | Leg | Model | Result |
|---|---|---|---|---|
| 1 | ATL@TB | Chris Godwin Jr. 3+ receptions | 78% | ✗ 0 |
| 2 | MIN@DET | Jared Goff 200+ pass yds | 78% | ✗ 176 |
| 3 | TEN@CIN | Wan'Dale Robinson 3+ receptions | 78% | ✓ 6 |
| 4 | IND@JAX | Trevor Lawrence 225+ pass yds | 78% | ✗ 210 |
| 5 | IND@JAX | Brenton Strange 3+ receptions | 78% | ✗ 2 |
| 6 | CLE@PIT | Deshaun Watson 150+ pass yds | 78% | ✓ 324 |
| 7 | LV@NYJ | Geno Smith 25+ pass att | 79% | ✓ 32 |
| 8 | BAL@BUF | Mark Andrews 2+ receptions | 77% | ✓ 3 |
| 9 | TEN@CIN | Joe Burrow 200+ pass yds | 77% | ✓ 462 |
| 10 | ATL@TB | Baker Mayfield 20+ pass att | 79% | ✗ 3 |
| 11 | CLE@PIT | Quinshon Judkins 10+ carries | 79% | ✓ 11 |
| 12 | MIN@DET | Aaron Jones 20+ rush yds | 76% | ✓ 22 |


### ATD board (top 16) — Week 8 — v1.9g replay (data through Week 7; built Nov 5 after grading)

| # | Game | Player | Model | Fair | Result |
|---|---|---|---|---|---|
| 1 | ARI@DAL | Javonte Williams (RB) | 70% | -239 | ✗ no TD |
| 2 | BAL@BUF | Derrick Henry (RB) | 68% | -215 | ✓ TD |
| 3 | BAL@BUF | James Cook (RB) | 56% | -129 | ✓ TD |
| 4 | TEN@CIN | Chase Brown (RB) | 54% | -117 | ✗ no TD |
| 5 | BAL@BUF | Josh Allen (QB) | 53% | -114 | ✓ TD |
| 6 | ATL@TB | Bucky Irving (RB) | 51% | -105 | ✓ TD |
| 7 | LV@NYJ | Ashton Jeanty (RB) | 50% | -102 | ✗ no TD |
| 8 | ARI@DAL | CeeDee Lamb (WR) | 49% | +104 | ✗ no TD |
| 9 | ATL@TB | Bijan Robinson (RB) | 48% | +108 | ✗ no TD |
| 10 | TEN@CIN | Ja'Marr Chase (WR) | 47% | +112 | ✓ TD |
| 11 | LV@NYJ | Brock Bowers (TE) | 46% | +115 | ✓ TD |
| 12 | MIN@DET | Jahmyr Gibbs (RB) | 44% | +126 | ✓ TD |
| 13 | TEN@CIN | Tony Pollard (RB) | 43% | +134 | ✓ TD |
| 14 | ARI@DAL | Tyler Allgeier (RB) | 42% | +140 | ✓ TD |
| 15 | TEN@CIN | Tee Higgins (WR) | 40% | +153 | ✓ TD |
| 16 | ARI@DAL | Trey McBride (TE) | 39% | +157 | ✓ TD |

Board: top-16 11/16 · top-8 4/8 · chalk triple 2/3

**2+ TD board (singles only):** Javonte Williams 34% (+190) · Derrick Henry 32% (+214) · James Cook 20% (+396) · Chase Brown 18% (+447) · Josh Allen 18% (+462) · Bucky Irving 16% (+518)


### Scorecard — Week 8 — v1.9g replay (data through Week 7; built Nov 5 after grading)

**Legs 44/62 = 71% actual vs 77% expected · SGP4 2/8 · SGP6 1/8 · SGP8 1/8**

| Game | Final | Legs | SGP4 | SGP6 | SGP8 |
|---|---|---|---|---|---|
| TEN@CIN | 36-43 | 8/8 | ✓ | ✓ | ✓ |
| LV@NYJ | 38-33 | 7/8 | ✗ | ✗ | ✗ |
| MIN@DET | 15-19 | 7/8 | ✗ | ✗ | ✗ |
| CLE@PIT | 6-27 | 6/8 | ✗ | ✗ | ✗ |
| ARI@DAL | 33-30 | 5/8 | ✓ | ✗ | ✗ |
| BAL@BUF | 10-36 | 5/8 | ✗ | ✗ | ✗ |
| ATL@TB | 0-16 | 3/6 | ✗ | ✗ | ✗ |
| IND@JAX | 7-42 | 3/8 | ✗ | ✗ | ✗ |


## Week 9 TNF — JAX @ BAL (Nov 5 2026)

*Engine v1.9g (first card on the return gate, exit-risk pricing and ATD position calibration; Fagnano debut, Tuten/Meyers limited, rain) · O/U 39.5 · spread -9.5 · M&T Bank Stadium · outdoor/grass · final 33-10*

**Personnel:** BAL INACTIVE: Nate Wiggins (CB1, stinger), Jaylinn Hawkins (S), Elijah Sarratt (WR), Emery Jones Jr. (G), Aeneas Peebles (DL). Lamar Jackson to IR (thumb surgery, hurt on the first snap in Buffalo); Tyler Huntley OUT (toe). Joe Fagnano — undrafted rookie from UConn — makes his first NFL start; Austin Reed is the backup, Kedon Slovis the emergency QB; Jacoby Brissett was acquired Wednesday and will not play. Jake Moody elevated at kicker. JAX INACTIVE: CJ Williams (WR), Alijah Huzzie (CB), Cam'Ron Silmon-Craig (S), Wesley Williams (DL). Bhayshul Tuten (RB1) and Travon Walker ACTIVE after Q weeks. Brian Thomas Jr. (7 targets in five games) fails the role gate; Travis Hunter has no 2026 sample. Outdoor grass.

**What the engine did with it:** First card on v1.9g. Fagnano has no NFL sample, so no Ravens QB legs exist, and BAL pass-catchers carry x0.78 (role) and x0.80 (TD). JAX passing x1.06 with Wiggins and Hawkins out; Baltimore's TD-defence factors regressed 40% toward average. JAX -9.5 at a 39.5 total: Jacksonville implied 24.5 points / 2.7 TDs, Baltimore 15 / 1.7 — which is why Henry is 30% not 50% despite a 31% red-zone share. New this week: every leg carries a 2.5% early-exit haircut and each ticket a 2%-per-team wipeout factor (Lamar and Mayfield both left inside ten snaps last Sunday and took nine floor legs with them); ATD lambdas are position-calibrated (WR x0.82, RB x1.05) and convex in team total; a player in his first game back from a 2-game absence is singles-only.

**The read:** The engine refuses to build a Baltimore story: a rookie making his debut behind a line that just lost its franchise QB on snap one, implied for 15 points. Everything with weight is Jacksonville's passing volume — Lawrence 28.7 attempts projected, 25+ hit 5/7 — spread across Washington, Meyers and Strange, none of whom has a dominant share (Washington 2026 targets 6-12-5-3-9-11-2). That is why the floor pool is six legs, not eight, and why the 8-leg does not exist tonight. Henry 10+ carries at 65% is the one Ravens leg with a case: a run-first plan by necessity, against a backfield trend (34 carries in his last two games) the engine will not ignore.

**ATD note:** No ATD clears 31%. Tuten 31% (+222) now that he is active, Henry 30% (+231), Meyers 28% (+256) — every one a 'take only at fair or longer'. Tuten + Henry double 10.7%, fair +834. Jacksonville's red-zone work is spread across four players and Baltimore is implied for 15 points; there is no chalk in this game.

**Slip note:** All-position 4-leg (no RB prop qualifies in the floor band): Lawrence 25+ att · Meyers 20+ rec yds · Strange 2+ rec · Tuten ATD — 22.1%, fair +352. Floor 4-leg 43.8% (+129), 6-leg 32.9% (+204). Size small: a 39.5 total with a debut quarterback is exactly the game the early-exit pricing was built for.

**FLOOR SGP** — 4-leg 43.8% · fair +129 **CASHED** · 6-leg 32.9% · fair +204 **CASHED** · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Jakobi Meyers 20+ rec yds | 79% | -367 | ✓ 65 | `4-leg core`
| 2 | Brenton Strange 2+ receptions | 80% | -393 | ✓ 2 | `4-leg core`
| 3 | Zay Flowers 2+ receptions | 76% | -314 | ✓ 3 | `4-leg core`
| 4 | Trevor Lawrence 25+ pass att | 76% | -310 | ✓ 26 | `4-leg core`
| 5 | Parker Washington 20+ rec yds | 72% | -251 | ✓ 61 | `+6`
| 6 | Trevor Lawrence 200+ pass yds | 74% | -278 | ✓ 242 | `+6`

Legs 6/6

**AGGRESSIVE SGP** — 4-leg 18.1% · fair +451 ✗ · 6-leg 7.7% · fair +1193 ✗ · 8-leg — 

| # | Leg | Model | Fair | Result | Tier |
|---|---|---|---|---|---|
| 1 | Parker Washington 3+ receptions | 62% | -162 | ✗ 2 | `4-leg core`
| 2 | Zay Flowers 30+ rec yds | 61% | -155 | ✗ 6 | `4-leg core`
| 3 | Derrick Henry 10+ carries | 65% | -184 | ✓ 17 | `4-leg core`
| 4 | Jakobi Meyers 40+ rec yds | 59% | -145 | ✓ 65 | `4-leg core`
| 5 | Bhayshul Tuten 30+ rush yds | 59% | -142 | ✗ 29 | `+6`
| 6 | Trevor Lawrence 225+ pass yds | 58% | -137 | ✓ 242 | `+6`
| 7 | Brenton Strange 3+ receptions | 67% | -205 | ✗ 2 | `+8`

Legs 3/7

**Anytime TD**

| Player | Model | Fair | 2+ TDs | Result | Decomposition |
|---|---|---|---|---|---|
| Bhayshul Tuten (JAX RB) | 31% | +222 | 5% (+1745) | ✓ TD | share 13% · team 2.74 TD · RZ-D 0.98 · pos-D 1.0 |
| Derrick Henry (BAL RB) | 30% | +231 | 5% (+1863) | ✗ no TD | share 31% · team 1.68 TD · RZ-D 0.91 · pos-D 0.83 |
| Jakobi Meyers (JAX WR) | 28% | +256 | 4% (+2178) | ✗ no TD | share 14% · team 2.74 TD · RZ-D 0.98 · pos-D 1.0 |
| Parker Washington (JAX WR) | 23% | +329 | 3% (+3285) | ✓ TD | share 11% · team 2.74 TD · RZ-D 0.98 · pos-D 1.0 |
| Trevor Lawrence (JAX QB) | 22% | +359 | 3% (+3787) | ✗ no TD | share 8% · team 2.74 TD · RZ-D 0.98 · pos-D 1.13 |
| Brenton Strange (JAX TE) | 16% | +508 | 1% (+6885) | ✗ no TD | share 6% · team 2.74 TD · RZ-D 0.98 · pos-D 0.96 |

TD double: 10.7% · fair +834 · triple: 4.9% · fair +1946

**All-position slip** — 22.1% · fair +352 **CASHED**: Trevor Lawrence 25+ pass att ✓(26) · Jakobi Meyers 20+ rec yds ✓(65) · Brenton Strange 2+ receptions ✓(2) · Bhayshul Tuten ANYTIME TD ✓(TD)

**All-position 8-leg** — 7.5% · fair +1237 ✗: Trevor Lawrence 25+ pass att ✓(26) · Jakobi Meyers 20+ rec yds ✓(65) · Brenton Strange 2+ receptions ✓(2) · Zay Flowers 2+ receptions ✓(3) · Bhayshul Tuten ANYTIME TD ✓(TD) · Derrick Henry ANYTIME TD ✗(no TD)

*Gated (not eligible for tickets):* Chris Rodriguez Jr. (JAX) role, Ameer Abdullah (JAX) role, Brian Thomas Jr. (JAX) role, Josh Cameron (JAX) role, Nate Boerkircher (JAX) role, Tyler Huntley (BAL) OUT, Justice Hill (BAL) role, Rasheen Ali (BAL) role, Rashod Bateman (BAL) role, Ja'Kobi Lane (BAL) role, Devontez Walker (BAL) RETURN, Josh Cuevas (BAL) role

*Pre-kick ticket set as finally given (rain version, built on receptions / attempts / carries / lowest pass-yards rung): **Floor 4** Strange 2+ rec · Flowers 2+ rec · Lawrence 175+ · Henry 10+ car — 31.7% / +215; **Floor 6** + Washington 2+ rec · Lawrence 25+ att — 24.4% / +310. **ATD ladder** 4: Strange 2+ · Lawrence 175+ · Henry 10+ car · Rodriguez ATD — 23.1% / +332; 6: + Flowers 2+ · Washington 2+ — 15.8% / +534; 8: + Lawrence 25+ att · Henry ATD — 7.1% / +1313; 10: + Strange 20+ · Flowers 20+ — 5.1% / +1876. **Realistic** 4: Strange 3+ · Flowers 3+ · Henry 10+ car · Lawrence 200+ — 21.3% / +368. **Single:** Rodriguez ATD 43% (fair +131) — the goal-line-back exception (7 of Jacksonville's 13 inside-the-10 carries) added to the engine during this build. Grades for these hand-assembled tickets are in the table below.*

| Ticket | Legs | Result |
|---|---|---|
| **Floor 4 (+215)** | Brenton Strange 2+ receptions ✓(2) · Zay Flowers 2+ receptions ✓(3) · Trevor Lawrence 175+ pass yds ✓(242) · Derrick Henry 10+ carries ✓(17) | **CASHED** 4/4 |
| **Floor 6 (+310)** | Brenton Strange 2+ receptions ✓(2) · Zay Flowers 2+ receptions ✓(3) · Trevor Lawrence 175+ pass yds ✓(242) · Derrick Henry 10+ carries ✓(17) · Parker Washington 2+ receptions ✓(2) · Trevor Lawrence 25+ pass att ✓(26) | **CASHED** 6/6 |
| **ATD 4 (+332)** | Brenton Strange 2+ receptions ✓(2) · Trevor Lawrence 175+ pass yds ✓(242) · Derrick Henry 10+ carries ✓(17) · Chris Rodriguez Jr. ANYTIME TD ✓(TD) | **CASHED** 4/4 |
| **ATD 6 (+534)** | Brenton Strange 2+ receptions ✓(2) · Trevor Lawrence 175+ pass yds ✓(242) · Derrick Henry 10+ carries ✓(17) · Chris Rodriguez Jr. ANYTIME TD ✓(TD) · Zay Flowers 2+ receptions ✓(3) · Parker Washington 2+ receptions ✓(2) | **CASHED** 6/6 |
| **ATD 8 (+1313)** | Brenton Strange 2+ receptions ✓(2) · Trevor Lawrence 175+ pass yds ✓(242) · Derrick Henry 10+ carries ✓(17) · Chris Rodriguez Jr. ANYTIME TD ✓(TD) · Zay Flowers 2+ receptions ✓(3) · Parker Washington 2+ receptions ✓(2) · Trevor Lawrence 25+ pass att ✓(26) · Derrick Henry ANYTIME TD ✗(no TD) | ✗ 7/8 |
| **Realistic 4 (+368)** | Brenton Strange 3+ receptions ✗(2) · Zay Flowers 3+ receptions ✓(3) · Derrick Henry 10+ carries ✓(17) · Trevor Lawrence 200+ pass yds ✓(242) | ✗ 3/4 |
| **Rodriguez ATD single (fair +131)** | Chris Rodriguez Jr. ANYTIME TD ✓(TD) | **CASHED** 1/1 |


## Pre-engine and single-game packs that exist only as PDFs

Week 1 era (Sept 10–14): TB-CIN-Model-Slip-Pack.pdf / -v2-Milestones (the first card, where bet365's milestone format was adopted), Melbourne-Full-Slip-Pack.pdf and Rams-vs-49ers-Melbourne-Combo-Pack.pdf (LA vs SF in Melbourne), SEA-vs-NE-Slip-Pack.pdf, Slip-01…06 PNGs (the six Week 1 Giants-game slips: props safety 4-leg, props core 6-leg, ATD ground chalk, ATD air-raid value, combo funnel 4-leg, combo both-backfields 6-leg — the user's final 10-leg at +1900 with three ATDs is in the chat record; Lamb and Javonte scored, Nabers did not).
Week 2 era: TNF-Lions-Bills-Pack.pdf and TNF-RedZone-Play-Calling-Report.pdf (coordinator red-zone tendencies), DEN-KC-MNF-Model-Pack.pdf, MNF-Walker-Card-and-Final-Board.pdf, NFL-Week2-Superstar-Board.pdf.
Week 3 era: NYG-LA-SGP-Variants.pdf and NYG-LA-ATD-Variants.pdf (Nacua out → in; Garrett out; Donald in), colour-coded tiers introduced here.
Week 4 era: IND-WAS-London-Slip-Pack.pdf, NFL-Week4-Afternoon-SGPs.pdf, NFL-Week4-Afternoon-Safe-Combo.pdf, DET-CAR-SNF-Pack.pdf (McMillan · Hubbard · St. Brown · Waller · Gibbs ATD discussion), ATL-NO-MNF-Pack.pdf (Saints passing stack; lost by one yard the night before).

## Report cards (PDF)

Week1-Report-Card.pdf · Week1-Combo-Report-Card.pdf · Week1-ATD-Report-Card.pdf · Week3-Report-Card.pdf (17 pages, v1.8 root cause + replay) · Week5-Report-Card.pdf (18 pages, 708-leg calibration → v1.9f) · Weeks6-8-Report-Card.pdf (23 pages, v1.9f out-of-sample exam, early-exit finding → v1.9g).

## Standing rules the user set (so the next build honours them)

1. Rosters and injuries refreshed before every build; official inactives applied ~90 minutes before kick; re-run and re-issue when they change.
2. Bet365 milestones only (yards from 20+, carries by 5, pass yards by 25 from 150, attempts by 5, receptions from 1+); no over/under lines.
3. Props SGPs never contain TD legs; ATDs are their own ticket; every pack carries 4/6/8-leg props, an aggressive variant, cross-game combos (4/6/8/10/12), a full-slate ATD slip, and all-position slips.
4. Picks come from the engine — no analyst/media picks; when the user's own read (Hampton–Mitchell, JSN, Barner, Meyers' hamstring, rain) changes a number, it goes through the engine as a personnel multiplier, is logged, and if it exposes a bug the bug is fixed before the next card.
5. Grades are "as shipped": no retroactive swaps (Higgins → Chase Brown declined, Week 1). Every graded week produces an algorithm change, documented in the report card.
6. Before pricing any manually named player, check he is on the roster of the team being discussed (Mike Evans is a 49er; Rachaad White is a Commander; Kenneth Walker is a Chief).
