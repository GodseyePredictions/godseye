# God's Eye — permanent factor checklist (ATD **and** props)

Set by the user on Nov 8 2026. **Every ATD and props build considers every factor below. No exceptions, no opt-outs.**
In code this is `DEFAULT_GROUPS = list(FEATURE_GROUPS)` (`attd/model.py`) for ATD and `PROP_GROUPS = list(FEATURE_GROUPS)`
(`attd/week.py`) for props, so a new factor group is automatically included everywhere once it's added to `FEATURE_GROUPS`.
Every pick's intel sheet must show the factors that apply to it.

| # | Factor | How it enters the model | Feature group |
|---|---|---|---|
| 1 | **Where the match is**: stadium, international, travel distance | stadium coordinates, miles traveled, international flag | `travel_rest`, `game_time` |
| 2 | **Time zones / body clock** | time-zone shift, kickoff hour on the team's home clock, early-body-clock flag | `travel_rest` |
| 3 | **Kickoff slot**: early (1pm ET), afternoon (4pm), night (SNF/MNF/TNF), international morning | slot code, ET kickoff hour, weekday | `game_time` |
| 4 | **Turf vs grass, indoor vs outdoor** | surface, roof | `stadium_weather` |
| 5 | **Weather**: sun / cloud / rain / snow / fog, temp, wind (indoor = neutral) | NWS kickoff-hour forecast; recorded weather for history | `stadium_weather` |
| 6 | **Home vs away** + player's home/away × roof/surface/slot/weather splits | home flag; shrunk player splits | base + `player_splits` |
| 7 | **Rest**: short week, off a bye | rest days | `travel_rest` |
| 8 | **OC play-calling**: pass rate over expected (all / red zone / inside 10), WR-TE-RB target split, deep / short / middle / screen, play-action, RPO, motion, shotgun, pace, QB designed runs | rolling team (or coordinator) tendencies | `off_playcalling_oc` |
| 9 | **DC scheme**: blitz rate, pass rushers, box counts, PROE faced, deep / YAC / aDOT allowed, TDs allowed by position, red-zone TD% allowed | rolling defense (or coordinator) tendencies | `def_scheme_dc` |
| 10 | **WR vs corners & safeties** | active CB + S coverage ratings (pass breakups + 2×INT per game), unit availability, yards/target, catch rate and explosive plays allowed to WRs, role × matchup interactions | `defender_personnel`, `unit_matchups` |
| 11 | **RB: O-line vs D-line / linebackers** | own RB yards/carry, stuff rate, sack & pressure rate allowed vs opponent's YPC allowed, stuffs forced, sacks, active DL + LB front ratings (sacks + ½ QB hits + TFL), run-lane interaction | `unit_matchups`, `defender_personnel` |
| 12 | **TE vs linebackers & safeties** | active LB + S coverage ratings, yards/target and catch rate allowed to TEs | `defender_personnel`, `unit_matchups` |
| 13 | **Who they're against**: the named defenders | defenders projected to play (active roster − Out/Doubtful − personnel.csv), with their recent production, listed on every intel sheet | `defender_personnel` |
| 14 | **Injuries, both sides**: opponent defenders out (snap-weighted DL/LB/DB), own offensive line out | official injury report + personnel.csv | `def_injuries`, `own_ol_injuries` |
| 15 | **Player route profile**: deep / short target share, air yards, YAC | rolling player profile | `player_route_profile` |
| 16 | Market anchor: Vegas implied team total & spread | team-TD Poisson layer | base |

## Standing rules carried from the ledger
1. Rosters and injuries are refreshed before every build. Official inactives are applied ~90 minutes before kickoff, then re-run.
2. bet365 milestones only: yards from 20+ in 10s, carries 10/15/20/25, pass yards by 25 from 150, attempts by 5, receptions from 1+.
3. Props SGPs never contain TD legs; ATDs are their own ticket.
4. Picks come from the engine only: no analyst or media picks. The user's own reads go into `data/personnel.csv` and are logged.
5. Grading is as shipped: no retroactive swaps. Every graded week produces an algorithm change.
6. Check every named player is on the roster of the team being discussed.
7. Questionable players and players returning from a 2+ game absence are singles only.
8. One player per team on ATD parlays (teammates split TDs). Cross-game props combos: ≤2 legs per game, ≤1 per team.

## Evidence
Walk-forward tests (2023–26) and a 2025–26 holdout: no factor group individually clears noise. The Vegas total and each
player's opportunity share carry most of the signal. Including every group costs about 0.0002 log loss, so considering
everything is free. Results: `outputs/factor_walkforward.csv`, `outputs/backtest_report.md`.

## Algorithm SGP (God's Eye "SGP" tab), added Nov 8 2026
One SGP per game, built from the best floor-band leg (70–88%, target 78%) per slot, all distinct players, no TD legs:
QB: pass yards **or** passing TDs · RB rush: rush yards · WR, TE, RB receiving: receptions **or** receiving yards.
"Best" = the highest-probability in-band rung after the role, sanity, Questionable and return gates. If a slot has
nothing qualifying, it's skipped and refilled with the next-best leg from those markets (labelled "fill for …").
Each slot lists runner-up alternatives. The joint price uses the measured leg correlations (`models/leg_correlations.json`).
Code: `algo_sgp()` in `attd/tickets.py`.

## Added Nov 8 2026 (Week 9 QB changes)
9. **Backup QB rule:** when a team's starting QB is Out (official report or personnel.csv), the depth-chart backup is pulled
   into the pool and projected to start, so no game is modelled without a quarterback. He is singles-only until he has
   recent starts. Logged on the platform's "This week's personnel" panel (`outputs/personnel_log_*.json`).
10. **ATD ticket styles:** Chalk (highest p, ≤1 per team), Balanced (no position over half the legs, always a WR),
    Air (WR/TE/QB only, capped at 8 legs). Caps apply at every ticket length so tickets nest.
11. **Platform transparency:** every build publishes user overrides, backup starters, the singles-only list with reasons,
    and official Out/Doubtful to the God's Eye page; the factor list and these rules are on its "Model & rules" tab.

12. **Return-from-absence (decided Nov 9 2026, Jacobs + Jordan Mason cases):** a player is singles-only while he has fewer
    than 2 games played since his last missed team game. After two full games back, his role is priced by the model
    (snap/share EWMAs), not by a flag. Replaces "missed 2+ of the team's last 4".

### Pending the user's decision (do not change without it)
- Explicit backup-QB downgrade factor for receivers (needs a backtest first).

## Week 9 report-card changes (Nov 9 2026) — PENDING BACKTEST, nothing ships until it clears
Failure modes observed (64 tickets, 18 cashed): 7 of 13 ATD misses on offenses scoring 0–1 TD; red-zone TDs went
through the air far above season OC rates (CAR 3/3, HOU 5/5, SEA 2/2); three legs died on roles the pregame features
could not see (E. Wilson 0 carries, McConkey 0 targets, J. Williams 2 targets); volume legs died in blowouts
(Allen 8 carries, Love 29 att); 7 perfect-props tickets died on one TD leg.

| Fix | New metrics | Where |
|---|---|---|
| 1 Team scenario | `team_td_sd` (season SD of weekly off. TDs), `team_zero_rate`, `abs_spread`, `dog_by_7`, `trail_pass_oc` (pass rate when down 10+), `lead_run_oc` | `FEATURE_GROUPS["team_scenario"]` |
| 2 Red-zone recency | 3-game EWMA of red-zone / inside-10 pass rate, RZ TD rate, RZ target split by position (`*_oc3`), `rz_pass_trend`, `rz_tgt_rank`, `rz_tgt_top2_share` | `FEATURE_GROUPS["rz_recency"]` |
| 3 Role freshness | `carry_share_jump`, `target_share_jump`, `snap_trend`, `fresh_role` (share moved >15 pts or snaps >20 pts last game, or <3 games this season) → singles only on tickets | `FEATURE_GROUPS["role_freshness"]`, `pick_rungs`, ATD pools |
| 4 Floor-game sanity | `<stat>_min` (worst game this season), `<stat>_loss` (average in losses), `trail_car_rate`, `trail_tgt_rate` → a floor leg must clear its line in the worst game or in losses | `PROP_FEATS`, `pick_rungs` |
| 5 Ticket rules | props parlays never carry TD legs (all-position ladders off by default); WR/TE anytime TDs are singles only; ATD tickets draw from RB/QB | `crossgame.build_ladders`, `atd_slip.ticket_sets`, `week.py` |

Validation plan: ATD walk-forward 2024–26 old vs new feature set (log loss + bootstrap CI); team zero-TD calibration by
λ bucket; weekly chalk-4 ticket hit rate vs stated probability under old and new; props 2025–26 holdout old vs new
features per market (log loss + floor-band calibration). Results: `outputs/fix_backtest.json`.

### Backtest verdicts (Nov 9 2026) — what shipped from the Week 9 fixes
- New feature groups (team_scenario, rz_recency, role_freshness): **no out-of-sample gain** for ATD (−0.05e-3 log loss, CI −0.6..+0.5)
  or props. Kept on as intel per the all-factors rule; not credited as an improvement.
- Team zero-TD: model **over**-predicts shutouts (λ 2.5–3: 6.7% predicted vs 2.7% actual). Fix 1 is a card note, not a model change.
- Ticket structure: weekly chalk 4-leg 2025–26 hit 21.4% vs 19% stated (n=28). Tickets were calibrated; Week 9 was variance.
- `fresh_role` gate: no signal for ATDs (reverted). Real for volume props (pass att −15 pts, carries −5, rush yds −4): kept for
  carries / rush yds / pass att only.
- Floor-game gate (worst game or average in losses clears the line): failing legs under-hit 4–10 pts on carries, rush yds, pass att;
  no effect on receiving. Kept for volume markets only.
- Ticket rules (Fix 5): props parlays carry no TD legs; WR/TE anytime TDs singles only. Judgment rules from the ledger + Week 9, not backtested.

## Script-first SGPs (added Week 10, 2026-11-09)
Per game the script is read first (`attd/script_sgp.py: game_script`): spread/favourite, total tier, PROE, pass rate when
trailing 10+ / run rate when leading 10+, red-zone pass trend (OC last 3), pace, weather, O-line vs front run lane,
secondary softness vs WRs/TEs. Every candidate leg gets a script fit (−1..+1) with reasons; legs are ranked by
logit(p) + fit weight, legs the script argues against (fit ≤ −0.3) are dropped when ≥14 others remain, and tickets are
built greedily with copula-joint probability: nested 4/6/8/10-leg props ladders (no TD legs, Fix 5), plus two hybrids
(1 anytime TD + 4 props; 2 anytime TDs + 4 props; ATDs are ticket-eligible RB/QB only, p ≥ 0.30). ≤2 legs per player,
≤3 per market. Shipped on the Game SGPs tab ("Script SGPs") and `outputs/Script_SGP_Slip_<S>_Wk<W>.pdf`
(`attd/script_sgp_pdf.render`). The old one-leg-per-position SGP is kept below it as "Slot SGPs".

### Closed gap (logged Nov 9 2026, fixed Nov 10 2026)
Late defensive and OL outs that arrive via ESPN's pregame report or user reads (`data/personnel.csv`) now feed
`def_out_*` / `def_starters_out` / `own_ol_out`: `scheme.personnel_injuries` turns each OUT/INACTIVE/IR/TRADED row into
a synthetic injury-report row (roster name match within the team; OUT/INACTIVE for the game week of `as_of`, IR/TRADED
carried to season end) and `add_environment` concatenates it with the official file before `injury_table`. Names must
match the nflverse roster spelling (e.g. "Michael Danna", not "Mike Danna"); unmatched rows are silently skipped.


## Tempo & discipline factor group (added Nov 10 2026, user request)
`tempo_penalty` in `FEATURE_GROUPS` (`attd/scheme.py: tempo_penalty_tables / rolling_tempo`, team-keyed EWMA, half-life 5):
- **Penalties:** offensive penalties per play and yards (`off_pen_rate_tp`, `off_pen_yds_tp`); the opponent defence's
  penalties per play and yards (`def_pen_rate_tpd`, `def_pen_yds_tpd`); `pen_edge` = their flags minus ours.
- **Drive stalls after 3rd down:** share of failed 3rd downs that end the drive (`stall3_rate_tp`), punts and field
  goals per drive after a failed 3rd down (`punt_after3_pd_tp`, `fg_after3_pd_tp`), overall punt / FG rates, 3rd-down
  conversion for and against, and what this defence forces (`stall3_forced_tpd`, `punts_forced_tpd`).
- **Possession & volume:** plays and drives per game, time of possession, seconds per play (pace), the same allowed by
  the opponent; `exp_plays` and `exp_top_sec` blend our offence with their defence.
- **Time on field per offensive player:** `exp_snaps = exp_plays × snap share`, `exp_time_on_field = exp_top × snap
  share`; shipped in every pick's intel ("Tempo & discipline" line) and used by the props models.
- **Game script:** profile notes flag penalty-prone / disciplined offences, flag-happy defences, 3rd-down stalls,
  FG-settling, and expected plays / possession per team; leg fit rewards volume legs in high-play scripts, penalises
  TD legs where drives settle for FGs or own penalties push the offence back.
**Backtest verdict (Nov 10 2026, walk-forward, scratch `tempo_backtest.py`):**
- ATD, 2024–26 folds, 17,128 player-games: log loss 0.38456 → 0.38449 (gain +0.00007, bootstrap 95% CI −0.00048 to
  +0.00060). Neutral: the group neither helps nor hurts ATD probabilities. It stays in `FEATURE_GROUPS` (standing rule:
  every factor considered on every build) and ships as intel and script-fit.
- Props (2025–26 holdout, old vs new feature list): carries 0.17907 → 0.17826 (better), rush yards 0.21565 → 0.21595
  (slightly worse), receptions 0.24165 → 0.24132 (better). Floor-rung calibration unchanged (≈0.79 predicted at the
  floor both ways). Receiving yards, pass attempts, pass yards and pass TDs were not reached: both backtest jobs hit the
  container's background time limit under load. Verdict: neutral-to-small-positive on volume markets; keep in the props
  feature list. Re-run the four missing markets with `python run.py backtest` on a quiet container.
- Where the group earns its keep is the game script: expected plays / possession per team, 3rd-down stalls and FG
  settling, and per-player expected snaps and time on field now steer leg fit and every pick's "Tempo & discipline"
  intel line.

## Kick-off window pack and Sunday rules (added Nov 15 2026, Week 10)
- **Window pack** (`attd/early.py: build_window`, PDFs in `attd/window_pdf.py`, site section `renderEarly`): for the next
  kick-off window with 3+ games, the site's Algorithm picks page leads with (1) window-only ATD 4/6/8/10 tickets,
  (2) each game's script-first props ladder (4/6/8), (3) master slips: every game's top 4 / 6 / 8 props on one slip,
  priced as the product of the game tickets, with the expected number of game tickets cashing.
- **ESPN sweep** (`attd/espn_news.py: sweep`): run before every build. Players ESPN rules Out / IR ahead of the official
  file are appended to `data/personnel.csv` with the nflverse roster spelling. Week 10 caught Kenneth Walker III,
  David Montgomery and Will Mallory, all still Questionable on the Friday report.
- **Interim ticket rules from the Week 9 Monday grade** (eligibility rules, not probability changes; no backtest yet):
  1. Backup-QB offences (`early.backup_qb_teams`: backup_qb on the personnel log, or a QB with >= 25% of the team's
     season attempts ruled out this week) stay off ATD parlays, and their passing / receiving legs stay off script SGPs
     (`build_script_sgps(hold_pass=...)`). Rushing legs stay. Players remain on the board as singles.
  2. A back under 7 carries a game (EWMA) is an ATD single, not a parlay leg (inherited roles, e.g. Emmett Johnson
     when Walker was ruled out).
  3. Window ATD tickets take no leg under 20%; a ticket size is skipped if the pool runs dry.
  The proper fix (a QB-quality feature that reprices teammates, with a backtest) is still pending.

## Week 10 report card fixes (Nov 16 2026)
Graded as shipped: `outputs/internal/graded_2026_wk10_sunday.json`, report `outputs/internal/Report_Card_2026_Wk10_Sunday.pdf`.
Props legs 78.3% vs 79.2% priced (83 legs). ATD legs: RB/QB 10 of 20 (9.6 expected), WR/TE 3 of 12 (4.7 expected).
10 of 59 tickets cashed vs 13.3 expected.
1. **Backup-QB haircut (model change, `pipeline.backup_qb_haircut`, applied in `project` and `week.build_week`).**
   Out of sample 2025-26, weeks 4+, starter under 25% of team season attempts, teammates priced >= 20%:
   WR/TE 28.6% priced vs 17.3% actual (n=133, se 3.2); RB 38.3% vs 31.2% (n=96); RB priced >= 30%: 44.9% vs 29.2% (n=65).
   Regular starters: within 1 point. Logit shift WR/TE -0.5, RB -0.3 (shrunk from -0.65 / -0.31). `p_attd_raw` keeps
   the unshifted number. Re-estimate when the sample doubles.
2. **Backup-QB detection (`early.backup_qb_teams`)** now also uses the starter-share rule the haircut was measured on:
   the expected starter (available QB with most attempts over the team's last two games) has under 25% of season
   attempts. Catches starters on injured reserve (Baltimore Week 10) that the weekly report never lists.
3. **Removed** the third ATD fallback tier (backs on backup-QB offences as fill legs: 0 for 3 in Week 10).
   In a single-game slip a backup-QB lead back may still be the TD leg at his haircut price; pass-catchers may not.
4. **Hybrid TD leg ranking** uses the play-at probability (model minus cushion: RB 3 pts, QB/TE 4, WR 6).
5. **Shipped snapshot** (`outputs/shipped/`) now includes the window pack and script slips.
6. **Tested, rejected:** per-position top-end recalibration. Fit on 2025, test 2026: log loss 0.3927 raw vs 0.3933
   adjusted; 5-fold gain +0.00004 (CI -0.0008 to +0.0010). Not applied.
7. **Open:** blowout scripts (four more in Week 10) still unmodelled; backup-QB props pricing untested.

## Week 10 MNF grade and fixes (Nov 19 2026)
LAC 23, BAL 20. ATD legs 2 of 2 (Henry at haircut 43%, Hampton 32%); props 3 of 8; all four slips lost.
Cause: every prop leg was a Charger and five rode Herbert's volume; LAC led and ran (Herbert 18 att, Hampton 22 carries).
1. **One-script cap** (`script_sgp._greedy(cap_pass=True)`): legs in PASS_MK (rec, rec_yds, pass_att, pass_yds, pass_td)
   from one team are at most half the ticket at every length.
2. **Minimum sample:** script-SGP prop legs need `season_n >= 4`.
3. **Returning players re-enter the pool** (`pipeline.projected_actives`): active-roster players with season snaps but
   none in the 4-game lookback, listed on this week's report as Full/Limited and not Out/Doubtful, are projected and
   flagged returning (singles only). Montgomery (Wk 11), Etienne (Wk 10).
4. **Single-game pack** (`window_pdf.build_game_pack / render_game_pack`): props 4/6/8, lotto (`script_sgp.build_lotto`:
   10 safest rungs, 80-97%), ATD choose 2/3/4, ATD + props 6 and 8-leg.

## EXPERIMENTAL: matchup reads (Nov 19 2026, user test; NOT in the default build or on the site)
`attd/matchup.py`. For each candidate prop leg: how the same role slot (QB, RB1/RB2 by carries, WR1-3 and TE1 by
targets) has done against this defence this season = share that cleared the line. Used only via
`window_pdf.build_game_pack(use_reads=True)`: shifts script fit by 1.5 x (read - model), drops a leg when the read
trails the model by 25+ points, or when under 60% of that role cleared it and the model is 15+ points higher.
Probabilities are never changed. Evidence against promoting it: 2023-26 test (1,420 team-games per position) shows
passing-side positional splits lose ~80-85% of their gap the next game and TDs-allowed-by-position has zero
carry-over; run defence keeps ~40%. First live test: Week 11 TNF IND @ HOU
(`outputs/TNF_Slips_2026_Wk11_IND_HOU_matchup_reads.pdf` vs the default `TNF_Slips_2026_Wk11_IND_HOU.pdf`). Grade both.
- **Aggressive SGP** (`script_sgp.build_aggressive`, `window_pdf.render_aggressive`, Nov 19 2026): 6 and 8-leg from
  each player's line nearest 62% (band 50-72%), season hit rate >= 40%, standard caps. With reads on, the read ranks
  (fit weight 1.2) but does not veto. Separate slip; the standard slips keep the 70-88% floor band.
- **Nov 19 2026, user decision:** matchup reads switched ON for 2026_11_IND_HOU only (`data/matchup_read_games.txt`;
  site script slips, lotto, Aggressive SGP, official PDF `Official_Slips_2026_Wk11_TNF_IND_HOU.pdf`). The model-only
  build `TNF_Slips_2026_Wk11_IND_HOU.pdf` is kept for the A/B grade. Reads stay OFF for every other game until graded.
- **Per-player ticket override** (`data/ticket_overrides.txt`, `early.apply_overrides`, Nov 19 2026): lifts the
  returning / fresh-role flags for named players so they compete on the normal probability and hit-rate thresholds.
  First use: David Montgomery, Wk 11 TNF (user instruction). Clear the file after the game.
- **Single-TD slips** now pick the scorer (top three candidates) whose finished 6-leg is most likely after his position
  cushion, instead of always taking the top-ranked candidate.
- **Locked official releases** live in `outputs/official/` (read-only PDF + JSON of every ticket as shipped, with a
  SHA-256 of the PDF). Grade from the JSON; never rebuild over a locked file. First: `OFFICIAL_2026_Wk11_TNF_IND_HOU`.

## Week 11 TNF grade (Nov 20 2026): HOU 26, IND 3
Locked official set (matchup reads on): 0 of 13 tickets, props legs 12/22 (76% priced), ATD 1/4. Model-only comparison,
same inactives: 0 of 8 tickets, props legs 12/18. Reads: no gain in first live test (dropped Stroud 200+ correctly;
dropped Stroud 2+ TD and Warren 20+ yds wrongly; Taylor 30+ rush, the 9-of-9 read, missed). Reads remain experimental,
`data/matchup_read_games.txt` game is finished; do not add games without a user decision. Override file cleared.
Root cause: half of each ticket sat on a 12.5-point underdog whose offence had lost 32% of its targets
(Warren 3+ rec on 10 of 13 tickets, 1 catch). Right: Collins (TD, 3+ rec, 40+ yds), Montgomery role (26-107, 3 rec).
Proposed, NOT applied (await user): heavy-underdog offence limit (backtest first); changed-offence flag;
confirmed-lead-back exemption from the hit-rate gate; matchup reads off for official slips.

## Nov 21 2026: the four TNF fixes, after backtesting (user: "apply all 4 and backtest the underdog rule")
Scratch scripts `dog_bt.py`, `dog_bt2.py`. Two of the four proposals failed their backtests and were NOT applied as proposed.
1. **Heavy-underdog cap: REJECTED, replaced by a ranking nudge.** Model floor legs (70-88%), 2026 walk-forward,
   n=2,783: on 10+ point underdogs they hit 79.8% vs 77.6% priced (n=84). Model-free 2021-26 (floor line = hardest line
   cleared in 75%+ of prior games, n=22,008): receiving legs on heavy underdogs (10+ dog, implied < 17.5) hit 73.7% vs
   73.9% for everyone else (n=691, se 1.7); rushing -1.9 (se 3.9); QB attempts -6.3 (se 6.5), the opposite of the
   proposed "attempt legs only". What does show: a gradient on implied team total. Model legs on teams implied < 17.5
   hit 1.0 pt under price while other buckets ran 2.2-4.8 over; model-free 68.1% (implied < 15) and 71.3% (15-17.5)
   vs 73-76% above. Applied: `leg_fit` -0.15 with "low implied team total" (ranking only, no cap, no probability change).
2. **Changed-offence flag: REJECTED.** Teams missing 25%+ of their last-three-game targets: remaining pass-catchers'
   floor receiving legs hit 75.2% vs 73.8% otherwise (n=1,672 vs 12,880; diff +1.5, se 1.1). No penalty exists; the
   Colts were one game. Not applied.
3. **Replacement lead back: APPLIED** (`early.lead_replacements`, `apply_role_flags` -> `lead_repl` on the ladders,
   `tickets.pick_rungs`). When the lead back (30+ carries over the team's last three games) is out, the replacement
   went from 6.5 carries / 27.7 yds to 12.2 / 51.2 (n=167); 80% cleared 20 yds, 67% cleared 30, 65% had 10+ carries;
   their own floor rushing lines hit 92% (n=37) vs 73% for other backs. His carries / rush-yards legs now skip the
   fresh-role gate, the season hit-rate gate and the worst-game gate. The returning-player singles rule (user's)
   still applies on top.
4. **Matchup reads: OFF** for official slips (`data/matchup_read_games.txt` emptied). Code kept as experimental.

## Full-slate comparison and agreed slips (Nov 21 2026, user request)
- `attd/defense_report.py`: every defence by position, season to date, rank 1 = best.
- `attd/full_slate.py` / `full_slate_pdf.py`: per game the algorithm slip, the matchup-steered slip and the **agreed
  (consensus) slip**: a leg must be priced by the model and cleared by >= 60% of that role vs this defence
  (`matchup.apply(mode="consensus")`); the read vetoes, never promotes, except rushing legs where run defence moves the
  ranking. Falls back to the algorithm slip per ticket size when too few legs are agreed (`matchup.build_game`).
- Site: `data/matchup_read_games.txt` lines `game_id,consensus` (Week 11 Sunday + MNF). Algorithm picks page and Game
  SGPs tab both use `build_game`, so they always match.
- ATD ticket order (`early.build_window`): backs vs a bottom-ten run defence +0.20 logit, vs a top-eight -0.20. Order
  only. Evidence: 0.79 vs 0.64 rushing TDs next game, soft vs stingy thirds, 2023-26.
- One-script cap relaxes when nothing else is left (one offence held out) so every game gets a ticket.
- `attd/espn_lines.sync(S, W, dates)`: run after every download; nflverse lags flexed kick-offs and totals.
- **ATD versions and hedges** (`attd/atd_versions.py`, `atd_versions_pdf.py`, Nov 22 2026, user request): ground, air,
  mixed, matchup-weighted and favourites tickets (4 and 6-leg, one per team) plus hedges (air cover for the ground
  ticket, round robins by 3s and 2s with the simulated hit distribution, either-scorer pairs, shootout doubles).
  Matchup index is order-only: backs = own OL yards/carry, opposing front yards/carry and stuff rate, run-defence rank,
  goal-line share; pass-catchers = expected dropbacks, opposing sack rate, yards/target allowed, end-zone share.
  WR/TE context 2026: 56% of rushing+receiving TDs go to WR/TE; priced 30-40% they hit 37.1% vs 34.2% priced (n=159),
  priced 40%+ they hit 41.6% vs 46.0% (n=89). Regenerate with the inactives rebuild.

- **User read, Nov 22 2026 (Wk11 MIN@SF):** the backup-QB haircut treats Kirk Cousins as a new passer for MIN. He ran this offence 2018-23 and Jefferson scored in 41-56% of games with him (2021-23 data). Open item: exempt a "new" QB who has prior seasons of starts with the same team/receivers from the haircut. Priced by hand that night: Jefferson 26% -> 36%, Jones 27% -> 34%. Grade to see which number was closer.

- **Market over/under test (first run Wk11 MNF, Nov 23 2026):** DraftKings player lines are available from the ESPN core API (`.../odds/100/propBets`, lines only, no prices). Compared each line with the model's interpolated P(over). Result logged in `outputs/internal/market_test_2026_wk11_MNF_*`. Model medians sat below the market on most receiving lines; a market line for a player missing from the model (Croskey-Merritt) exposed a stale role. Grade the 8-leg test slip and the line-by-line sides before adopting anything.
