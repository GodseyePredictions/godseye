# NBA storage schema

Everything the NBA module produces is written to SQLite (`model/nba/data/nba.sqlite`) and, for the latest slate, to `model/nba/output/nba_slate.json`. This page documents the tables the Godseye site will read for public track records and per-user pick tracking. Table definitions live in `model/nba/ledger.py` (ledger) and `model/nba/store.py` (data).

Conventions:

- All times are UTC, ISO 8601.
- Player, team and game ids are ESPN ids (the module's canonical ids).
- Prices are American odds. Probabilities are 0 to 1.
- A milestone rung is stored as an over line half a point lower: "20+ points" is `market=pts, side=over, line=19.5`.
- The ledger is append-only. A re-run adds rows under a new `run_id`; it never rewrites an earlier run.

## How the tables link

```
nba_runs 1 ── * nba_game_cards
         1 ── * nba_projections
         1 ── * nba_legs ── (leg_ids) ── nba_tickets
games / player_games  ── results used for grading
odds                  ── prices, including the closing price (is_close = 1)
nba_report_cards      ── one per slate date
```

## Ledger tables (what the site reads)

### nba_runs
One row each time the pipeline runs.

| column | meaning |
|---|---|
| run_id | Key for everything produced by this run |
| run_at | When it ran |
| kind | `slate` (whole slate) or `game` (single-game re-run) |
| slate_date | Eastern date of the games |
| n_sims | Simulations per game |

### nba_game_cards
The game script card, written before any prop.

| column | meaning |
|---|---|
| run_id, game_id | Key |
| matchup | For example `CLE @ NY` |
| card_json | Pace, margin and total (ours, market, blend), win probability, blowout and close-game probability, the three most likely scripts, blowout warning, starters' expected fourth-quarter minutes, blowout exposure per player |
| card_text | The printed card including tickets and risk notes |

### nba_projections
One row per projected player per run.

| column | meaning |
|---|---|
| run_id, game_id, player_id | Key |
| name, team_id | Display |
| status | `confirmed_in`, `questionable`, `doubtful`, `out`, `unknown` at run time |
| role, role_change | `starter`, `sixth man`, `rotation`, `fringe`; reason text when the role has changed |
| p_play | Chance he takes the floor |
| min_mean, min_p10, min_p50, min_p90 | Minutes distribution, if he plays |
| pts, reb, ast, fg3m, stl, blk | Mean of each stat across the simulations, if he plays |
| exp_fg_pct, base_fg_pct, exp_3p_pct, base_3p_pct | Expected shooting tonight against his own baseline |
| gate_pts, gate_fg3m | Shooting gate, 1 = pass |
| blowout_exposure | Share of points+rebounds+assists lost in blowout simulations |
| adjustments | JSON list: every adjustment that moved a rate from baseline, with sample sizes |
| inout_notes | Teammate in/out effects and how each was estimated |
| act_min, act_pts, act_reb, act_ast, act_fg3m, act_stl, act_blk, graded_at | Filled by nightly grading |

### nba_legs
Every rung or line the book offered, with the model's view.

| column | meaning |
|---|---|
| run_id, leg_id | Key. `leg_id` = `game|market|player|side|line` and is stable across runs |
| kind | `prop`, `dd` (double-double or triple-double) or `game` |
| player_id, team_id, label | `label` is the bet365-style wording shown on slips |
| market | `pts reb ast fg3m stl blk pra pr pa dd td ml spread total` |
| line, side | `side` is `over`, `under`, `yes` or `team` |
| model_prob | Counted from the simulations |
| p_blowout, p_close | The same probability inside blowout and close-game simulations |
| book, price, price_seen_at | The price taken into account and when it was seen |
| closing_price | Last price before tip-off, filled at grading |
| gate_ok, sgp_eligible, why_not | Whether the leg may go on a same-game parlay, and the rule that stopped it if not |
| reason | One line from the itemised adjustments |
| actual, result, graded_at | `result` is `won`, `lost`, `push` or `void` (player did not play) |

### nba_tickets

| column | meaning |
|---|---|
| ticket_id | Key |
| run_id, game_id | Which run and game |
| type | `props_4`, `props_6`, `game_script`, `double_double` |
| leg_ids | JSON list of `leg_id` |
| slip_json | JSON list in the site's existing `Leg` shape (`description`, `odds`, `game`) from `src/lib/bets.ts`, so the tracker can import it as a bet |
| joint_prob | Share of simulated games in which every leg hits |
| book_price, price_is_estimate | `price_is_estimate = 1` means the product of leg prices, not bet365's own same-game price |
| fair_price, ev | Model fair price and expected value per unit staked |
| status | `proposed`, `placed`, `superseded` |
| placed_at, stake, locked | Set when the ticket is marked placed. A locked ticket is never changed, only graded |
| result, graded_at, miss_causes | `miss_causes` is a JSON list of cause tags for the legs that lost |

Cause tags: `minutes miss`, `blowout`, `injury in game`, `shooting variance`, `model error`.

### nba_report_cards
One row per slate date: `card_json` (legs hit and missed, calibration to date by market and ticket type, closing line value, alerts) and `card_text`.

### nba_status_changes
One row per availability change seen between runs: who, from and to status, and `projections_changed` (JSON list of the projections that moved because of it).

## Data tables (inputs)

| table | one row per | key columns |
|---|---|---|
| games | finished game | scores by quarter, biggest second-half lead, close-game flag, `known_at` = when the game ended |
| schedule | scheduled game | date, tip time, teams, venue, neutral flag |
| player_games | player per game | box score, shots by zone, seconds by quarter, starter flag, did-not-play reason |
| officials | official per game | name |
| injury_reports | player per official report | `report_utc` (the timestamp), status, reason, matched `player_id` or null |
| availability | player per gate run | status, minutes restriction, games since return, `known_at` |
| starters | starter per game | `source`, `known_at` (ESPN lists starters only once a game starts) |
| ref_assignments | official per game day | from official.nba.com, captured daily |
| market_lines | game per snapshot | spread, total, moneylines from ESPN (DraftKings) |
| odds | price per snapshot | `source` (`the-odds-api` or `csv`), `book`, market, player, side, line, price, `is_close` |
| pbp_snapshots | entity per day | pbpstats possession-level totals, stored for later use |

Every input table has a time column (`known_at` or `report_utc`). Model code reads them only through a point-in-time view that returns rows known before a given moment.

## For the site

- **Public track record:** `nba_tickets` where `status = 'placed'` joined to `nba_legs` on `leg_ids`, plus `nba_report_cards` for calibration to date.
- **Per-user pick tracking:** import `nba_tickets.slip_json` into the existing bet tracker (`Bet.legs`), with `joint_prob` as `modelChance` and `book_price` as `price`.
- **Tonight's slate without SQL:** `model/nba/output/nba_slate.json` holds the latest run: cards, projections, tickets, singles, availability and status changes.
