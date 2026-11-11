# NBA module audit

Audit date: 11 November 2026 (2026-27 season, about three weeks in). Repo: `GodseyePredictions/godseye`, `main` at `3840b43`. No model code was written.

## Read this first

1. **There is no NBA code in this repo.** Not on `main`, `game-markets`, `app-preview-build` or `nfl-model-and-odds-math`. The seven-module NBA algo needs to be added before it can be assessed.
2. **The NFL player-prop algo is not in this repo either.** The repo holds the NFL game-market model and the website. The touchdown and prop picks arrive as an exported HTML page that `scripts/import-console.py` unpacks. Whatever produces that export lives somewhere else.
3. **`stats.nba.com` and `cdn.nba.com` could not be reached from this cloud session.** `stats.nba.com` timed out on every call and `cdn.nba.com` returned 403. That is the only free source for tracking, hustle, matchup, play-type and defender-distance data, so those rows below are **not verified**. I did not disguise the requests as a browser to get round the block.
4. **The Odds API could not be tested: no key is available to this session.** The host answers (`401 MISSING_KEY`). Everything in the odds row is from its published documentation, not from a live call. The most important open question is whether it carries **bet365** NBA player props and alternate lines for your region.
5. **Three of your engineering rules do not match the NFL code as it stands.** The NFL Python has no tests, no config file (thresholds are constants at the top of each script) and no bet log. "Mirror the NFL module" and "tests for every module, one config file, log everything" pull in different directions. Section A3 proposes how to settle it.

---

## Part A: Repo

### A1. How the NFL algo is organised

**Two halves that barely touch.**

| Half | Where | What it is |
|---|---|---|
| Website | `src/`, `public/`, `scripts/` | Next.js 16 site. `/` is marketing, `/app` is the console. |
| Model | `model/` | Flat folder of Python scripts, run by hand in order. No package, no `__init__.py`, no CLI. |

**Model files (1,745 lines of Python)**

| File | Lines | Job |
|---|---|---|
| `fetch_data.py` | 33 | Downloads nflverse files: `games.csv`, players, play-by-play, injuries, snap counts, FTN charting. |
| `features.py` | 128 | Play-by-play to `data/cache/team_games.csv`, `qb_games.csv`, `skill_games.csv`. |
| `matchups.py` | 167 | Unit-level tables (run direction, target depth, pressure) and `personnel.csv` (starters ruled Out or Doubtful). |
| `nfl_model.py` | 60 | Elo-style team rating in points. |
| `backtest.py` | 106 | Tunes the Elo model to 2014, scores it from 2015 against the closing spread. |
| `team_metrics.py` | 279 | Opponent-adjusted possession and penalty ratings, walk-forward from 2024. |
| `game_markets.py` | 972 | The main model: ratings, ridge fundamentals, market blend, seven-check pick gate, 4/6/8-leg tickets, interception model, leg correlations, hybrid SGP pricing, scorecard. |

**Data flow**

```
nflverse (GitHub) -> fetch_data.py -> data/pbp, injuries, snap_counts   (not committed)
                  -> features.py, matchups.py -> data/cache/*.csv       (committed)
                  -> game_markets.py -> output/game_markets.json        (committed)
console export (HTML, built elsewhere) -> scripts/import-console.py -> public/console/data.js
game_markets.py also reads public/console/data.js for TD probabilities, weather and injury flags
website reads output/*.json and public/console/data.js
```

**Config.** None. Each script carries its own constants (`SAFE_MIN_P = 0.65`, `ALT_OFFSETS`, `MIN_DOGS`, `TEST_FROM`, the `Params` dataclass in `nfl_model.py`).

**Tests.** `npm test` runs two TypeScript files with Node's built-in runner: `src/lib/odds.test.ts` and `src/lib/bets.test.ts`. There are **no Python tests**.

**How a slate gets run.** By hand: `fetch_data.py`, then `features.py`, `matchups.py`, `game_markets.py`, then import the console export, then commit the outputs. Re-run after injury designations post. No scheduler, no runner script.

**How a slate gets graded.** Two separate things, neither a pick log:
- *Model scorecard*: `game_markets.py` re-scores itself walk-forward on 2020 onward each run and writes the result into the output JSON.
- *Bet tracking*: `src/lib/bets.ts` stores bets in the visitor's browser and the user marks them won or lost by hand. It has a `closingOdds` field (singles only) and `closingLineValue()` in `odds.ts`.

Nothing in the repo writes a timestamped record of projection, price taken, closing line and result. Rule 9 has no existing home.

**Odds ingestion.** None. NFL closing lines come from nflverse `games.csv`. The README lists live odds as not built.

**Worth knowing.** The NFL model's own README says it does not beat the closing line, and its tickets are "fair-price references, not proven edges".

### A2. Existing NBA code

**None found.** The only mentions of NBA in the repo are a sport dropdown option in `ConsoleApp.tsx` and "NBA is next" on the marketing page.

| Module you described | In repo? | Verdict |
|---|---|---|
| Player prop projection | No | Cannot assess |
| Minutes projection | No | Cannot assess |
| SGP correlation engine (Monte Carlo) | No | Cannot assess |
| Backtesting harness | No | Cannot assess |
| Stat-specific models | No | Cannot assess |
| Data pipeline (the-odds-api + NBA Stats API) | No | Cannot assess |
| Daily runner | No | Cannot assess |

Please add it (a branch, a folder, or a second repo) and I will do the keep / refactor / replace pass.

One thing to check when you do: if the old data pipeline calls `stats.nba.com` directly, it will fail from any cloud host the way it failed here.

### A3. Proposed layout

NFL files stay exactly where they are. Nothing is moved or edited.

```
model/
  (existing NFL scripts, untouched)
  common/                 new, sport-neutral; NBA uses it first, NFL can adopt later
    odds_math.py          Python port of src/lib/odds.ts (decimal, implied, fair, EV, Kelly, CLV)
    odds_feed.py          the-odds-api client + pasted-CSV reader; returns only rungs the book offers
    tickets.py            leg selection and SGP assembly under config rules
    joint.py              correlated-leg joint probability (lifted from game_markets.py's copula idea)
    ledger.py             append-only timestamped log: projection, probability, price, close, result
    grading.py            settle legs and tickets from box scores, compute CLV
  nba/
    config.py             the single config file: 70% floor, blowout cutoffs, shrinkage, caps
    fetch_data.py         same name and role as the NFL one
    features.py
    availability.py       official injury report + starters, with timestamps (rule 2)
    game_sim.py           game-level simulation, runs first (rule 6)
    minutes.py
    props.py              per-stat distributions with itemised adjustments (rule 10)
    sgp.py
    backtest.py
    run_slate.py          daily runner
    data/  cache/  output/
    tests/                pytest, one test file per module
docs/
  nba_audit.md
```

**What can genuinely be shared today:** only ideas, not importable code. The odds maths exists in TypeScript and again, partly, inside `game_markets.py`. The ticket builder (`ladder`) and joint-probability code are buried in the 972-line NFL script. Odds ingestion, logging and grading do not exist.

**Decisions I need from you**

| Question | My recommendation |
|---|---|
| NFL has no Python tests or config file. Mirror that, or follow your written rules? | Follow the written rules (pytest, one config file). Mirror NFL only in naming, flat scripts, `data/cache/output` folders and walk-forward scoring. |
| Shared code: copy into `model/common/` and leave NFL alone, or refactor NFL to import it? | Copy and leave NFL alone for now. Refactoring NFL breaks "do not change NFL code". |
| Where does the ledger live? | A committed CSV or SQLite file under `model/nba/output/`, since there is no database yet. |

---

## Part B: Data

### How each source behaved from this session

| Source | Result of real calls | Auth | Rate limit seen |
|---|---|---|---|
| `site.api.espn.com` | 200 on every call, 0.2 to 0.4 s | None | No limit headers; responses cached about 9 s. Undocumented API, can change without notice. |
| `api.pbpstats.com` | 200; fast for small calls, 5 to 21 s for league-wide tables | None | No limit headers. One-person project; slow calls suggest keeping volume low. |
| `www.basketball-reference.com` | 200 on six pages | None | `robots.txt` sets crawl-delay 3 s. Site policy is roughly 20 requests a minute, with temporary bans above that. |
| `official.nba.com` | 200 with a named client; 403 to curl's default client string | None | None seen |
| `ak-static.cms.nba.com` (injury PDFs) | 200 for correct file names | None | None seen |
| `stats.nba.com` | **Timed out (25 to 30 s) on every call** | None, but filters by client and network | Not measurable |
| `cdn.nba.com` | **403 Access Denied** on every call | None | Not measurable |
| `api.the-odds-api.com` | **401 MISSING_KEY** | API key | Not measurable |

### B1. Box scores and play-by-play: available, verified

| | ESPN | pbpstats | Basketball Reference |
|---|---|---|---|
| Box score fields | MIN, PTS, FG, 3PT, FT, REB, AST, TO, STL, BLK, OREB, DREB, PF, +/-, starter flag, DNP reason | 231 fields per player: possessions, shots by zone, assisted/unassisted, putbacks, usage, on-court ratings, foul and turnover types | Basic, advanced (usage, rebound %, assist %, ratings, BPM), by quarter and half |
| Play-by-play | 454 plays in the sample game: type, text, clock, period, score, player ids, shot coordinates, substitutions, wall-clock time | Possession-level, built from NBA play-by-play | Full play-by-play page |
| History | 2003-04 game returned plays with coordinates (no wall-clock that far back) | 2000-01 returned 441 players | Decades |
| Game-day timing | Live during games, final at the buzzer | Last night's games were present this morning | Next day |

Reliability: three independent sources agree on basics, so cross-checking is cheap. pbpstats game ids are NBA ids; ESPN uses its own, so an id map is needed.

### B2. Player tracking (touches, passes, potential assists, drives, catch-and-shoot vs pull-up): NOT VERIFIED

Only free source is `stats.nba.com` (`leaguedashptstats`, `playerdashptshots`). Unreachable here. From prior knowledge, not confirmed today: available from 2013-14, filterable by date range and per game, posted the morning after.

Verified partial substitute: ESPN play types label each shot ("Pullup Jump Shot", "Driving Layup Shot", "Step Back Jump Shot", "Cutting Layup Shot"), and pbpstats gives assisted vs unassisted by zone. Neither gives touches, passes or potential assists.

### B3. Hustle stats (contested shots, deflections, screen assists, box-outs, loose balls): NOT VERIFIED

`stats.nba.com` only (`leaguehustlestatsplayer`, `hustlestatsboxscore`). From prior knowledge: from 2016-17, per game. No substitute found in any reachable source.

### B4. Matchup data (who guarded whom, partial possessions, points and FG% allowed): NOT VERIFIED

`stats.nba.com` only (`leagueseasonmatchups`, `boxscorematchupsv3`). From prior knowledge: from 2017-18, per game. Known to be noisy: assignments are inferred by tracking, switches split possessions, and single-game samples are tiny.

### B5. Play-type data (P&R handler, roll man, isolation, spot-up, off-screen, handoff, post-up, transition): NOT VERIFIED

`stats.nba.com` only (`synergyplaytypes`). From prior knowledge: from 2015-16, offence and defence, frequency and points per possession.

**Point-in-time problem, if that memory is right:** this feed is season-to-date totals with no date filter and no per-game rows. Past seasons can only be pulled as end-of-season numbers, which leaks future games into any backtest (rule 7). The fix is to snapshot it every day from now on and treat prior seasons as unusable for backtesting, or use them only as a previous-season prior.

### B6. Shot data: location and type verified; defender distance NOT VERIFIED

Verified:
- ESPN: every shot has x, y, shot type, shooter, points attempted, back to at least 2003-04.
- pbpstats `get-shots`: per shot, distance, value, made, assisted and by whom, blocked and by whom, putback, both five-man lineups on the floor, score margin, seconds into the possession, how the possession started, and a `shot_quality` estimate.
- Basketball Reference has a shot chart page per game.

Not verified: nearest-defender distance. That lives on `stats.nba.com` shot dashboards as bucketed season aggregates (0-2, 2-4, 4-6, 6+ feet) per player. From prior knowledge, per-shot defender distance has not been public since 2016.

### B7. Lineup and on/off data: available, verified

pbpstats:
- `get-totals?Type=Lineup`: five-man units, 228 fields.
- `get-wowy-stats`: with-or-without-you splits per team.
- `get-on-off`: on, off, difference, minutes on and off.
- `get-totals` accepts `FromDate` and `ToDate`. **This makes point-in-time on/off possible**: ask for a season up to yesterday and nothing later.
- `get-game-logs`: per-game rows per player.
- Shots carry both lineup ids, so with/without rates can also be rebuilt from raw shots.

History back to 2000-01. League-wide calls took up to 21 s, so cache hard.

### B8. Official injury report and confirmed starters

**Injury report: available, verified, official, timestamped.**
- `official.nba.com/nba-injury-report-2026-27-season/` links every report as a PDF.
- This season the reports are published **every 15 minutes** (49 files listed by noon today). The timestamp is in the file name and on the page header.
- Fields: game date, tip time (ET), matchup, team, player, status (Out, Doubtful, Questionable, Probable, Available), reason. Teams that have not filed show "NOT YET SUBMITTED".
- Archive verified by direct download: January 2020, November 2021, 2023, 2024 and 2025 all returned files. File naming changed (hourly `_05PM` up to 2025-26, `_05_00PM` now).
- Reliability: it is a PDF with wrapped multi-line cells, so it needs a careful parser with tests. Late scratches after the last report are not captured.

ESPN `injuries` is a usable cross-check (93 entries, each with a timestamp, status, body part and expected return date) but it is not the official source.

**Confirmed starters before tip: weak.**
- ESPN's pre-game summary had **no players and no officials** for tonight's game. Starters only appear in the box score once the game starts (5 of 14 flagged in last night's game).
- The NBA's own daily lineups feed is on `stats.nba.com`: not reachable, not verified.
- So from here there is no verified free source of confirmed starters ahead of tip-off. Rule 2 can be met for availability (injury report) but not yet for "confirmed starter".

### B9. Schedule: available, verified

ESPN team schedule returned 80 games with date-time (UTC), venue name, city and state, home/away. Rest days and back-to-backs are simple to derive. Travel distance and time zones need a small static table of 30 arenas with coordinates and zones; ESPN gives city and state only. Neutral-site and cup games are flagged.

### B10. Referee assignments and crew tendencies: available, verified

- Assignments: `official.nba.com/referee-assignments/` lists tonight's crew chief, referee, umpire and alternate per game. It is posted on game day (from prior knowledge about 9 am ET). The page shows today only, so it must be captured daily.
- History: ESPN's summary lists the three officials for each finished game, back to at least 2003-04. Basketball Reference box scores also list them.
- Tendencies: Basketball Reference's referee register has games, fouls, free throw attempts and points per game, each relative to league average, split home and visitor. For point-in-time use, rebuild these from ESPN box scores by date rather than scraping season totals.

### B11. Odds: NOT VERIFIED (no API key)

Live result: `401 MISSING_KEY`. The following is from The Odds API's documentation as I know it, and needs confirming with a real key:

| Item | Documented position (unverified) |
|---|---|
| Game lines | `h2h`, `spreads`, `totals`, `alternate_spreads`, `alternate_totals` |
| Player props | points, rebounds, assists, threes, steals, blocks, PRA, P+R, P+A, double-double, triple-double |
| Milestone rungs | `_alternate` versions of the prop markets |
| How props are fetched | One event at a time; cost scales with markets times regions |
| Free tier | About 500 credits a month. A full slate of props for one book would use that in a day or two. |
| Historical and closing prices | Paid plans only. Game lines from 2020, player props from about May 2023, as timed snapshots. |
| **bet365** | **Uncertain.** I recall an Australian bet365 feed and patchy or no coverage elsewhere. This must be checked first, because rule 5 depends on real bet365 rungs. |

Verified free fallback for game lines only: ESPN's summary carries DraftKings spread, total and moneyline per game (not bet365, no props, no reliable history).

The key cannot be put in a request header by this platform's secure credential store because The Odds API takes it as a URL parameter. To test, add it as an environment variable named `ODDS_API_KEY` in the cloud environment settings and start a new session. Do not paste it into chat.

---

## Part C: Thesis coverage

Quality reflects what I could verify. "Unverified" means the source is `stats.nba.com`.

| Factor | Best free source | Quality | Proxy if not direct | Paid source that does it properly |
|---|---|---|---|---|
| Player health, minutes restrictions, return ramp | Official NBA injury report (status); ESPN injuries (body part, return date); box score minutes | Usable for status. None for stated restrictions | Minutes in first games back vs pre-injury baseline, by injury type and games missed | Sportradar or SportsDataIO injury feeds; Rotowire for beat-writer restriction notes |
| Teammate in or out | pbpstats WOWY, on/off, lineups, date-filtered | Strong | Not needed | Cleaning the Glass (garbage time removed) |
| Home vs away | Any box score source | Strong | Not needed | None needed |
| Season phase, rest, back-to-backs, 4th-quarter usage | ESPN schedule and play-by-play; pbpstats possessions | Strong for rest and phase. Usable for 4th-quarter usage | Arena table for travel and time zones; 4th-quarter usage rebuilt from play-by-play | None needed |
| Defensive scheme: zone vs man frequency | None | None | Opponent's allowed 3-point rate, corner-three rate and assisted rate, from pbpstats | Synergy Sports; Second Spectrum |
| Pick-and-roll coverage: drop, switch, blitz, hedge | None | None | NBA play-type defence vs handler and roll man (unverified); opponent rim vs pull-up shot mix allowed | Second Spectrum; Synergy |
| Individual defender matchup | NBA matchup data (unverified) | Weak | Defender-position-level rates allowed; who shared the floor from pbpstats lineups | BBall Index matchup data; Second Spectrum |
| Shot contests and altered shots | NBA hustle contested shots and defender-distance buckets (unverified) | Weak | Block rate and opponent accuracy at rim by defender on floor, from pbpstats | Second Spectrum |
| Off-ball movement and screens | NBA hustle screen assists, play-type off-screen and handoff (unverified) | Weak | Assisted share and catch-and-shoot share of a player's shots | Second Spectrum; Synergy |
| FG% and 3P% vs each scheme and matchup | None for scheme; NBA matchup FG% (unverified) | None for scheme. Weak for matchup | Opponent-allowed accuracy by zone and shot type, shrunk hard | Synergy |
| Double teams vs single coverage | None | None | Team assist rate and teammate catch-and-shoot volume when the star is on the floor | Second Spectrum |
| Rebound, steal and block opportunity | pbpstats: missed shots by zone while on floor, rebound % by shot type, bad-pass vs lost-ball steals, blocks by zone. NBA rebound chances (unverified) | Usable | Opportunities = opponent misses, live-ball turnovers and rim attempts while on floor | NBA tracking via Sportradar or Second Spectrum |
| Pace and blowout risk | pbpstats possessions per game, seconds per possession; ESPN win-probability series; ESPN DraftKings spread | Strong | Not needed | The Odds API paid history for closing spreads |
| Referee effect | official.nba.com assignments; ESPN officials per game; Basketball Reference register | Usable | Not needed. Expect a small effect, mostly on fouls and free throws | None needed |

---

## Part D: Recommendation

**The three factors with the weakest free data**

| # | Factor | Free data | Is a paid feed worth it? |
|---|---|---|---|
| 1 | Zone vs man frequency | None | **No.** Synergy and Second Spectrum sell to teams and media, not at retail prices. Zone is a small share of NBA possessions. Use opponent shot-profile proxies. |
| 2 | Pick-and-roll coverage type | None | **No, not now.** Same vendors, same access problem. NBA play-type defence gets part of the way if it can be reached and snapshotted daily. Revisit only if backtests show points and assists props for ball handlers are the weak spot. |
| 3 | Double teams vs single coverage | None | **No.** Only exists in Second Spectrum. It affects a handful of stars; teammate catch-and-shoot volume is an adequate proxy. |

**Where money or effort would actually pay off**

1. **Odds history.** A paid Odds API plan (or another vendor if it lacks bet365) is the one purchase I would make. Without historical prop prices and closing lines there is no honest backtest and rule 9 cannot be met. Confirm bet365 coverage before paying.
2. **Access to `stats.nba.com`.** No purchase needed, but the fetch has to run from somewhere the NBA does not block, most likely your own computer, and write files the cloud job reads. Until that is tested, tracking, hustle, matchup and play-type data should be treated as unavailable.
3. **Confirmed starters.** If the NBA daily lineups feed cannot be reached, a paid lineup feed (SportsDataIO or Rotowire) is the only way to satisfy rule 2 for starters.

**What stops the build right now**

| Blocker | What I need |
|---|---|
| No NBA code to assess | Add the seven modules to the repo or a branch |
| Odds unverified | `ODDS_API_KEY` set in the environment, then a new session |
| `stats.nba.com` unreachable | Your call: test from your own computer, or build without those five data types |
| NFL has no tests, config or ledger | Your call on the three decisions in A3 |

## Appendix: calls made

All on 11 November 2026, one request per line unless noted.

| Host | Endpoints called |
|---|---|
| ESPN | `scoreboard` (10 Nov 2026, 11 Nov 2026, 5 Nov 2003), `summary` (final game, scheduled game, 2003 game), `injuries`, `teams/2/schedule` |
| pbpstats | `get-games` (2025-26, 2026-27), `get-totals` (Player, Lineup, Opponent, 2000-01, date-filtered), `get-wowy-stats`, `get-on-off`, `get-game-stats`, `get-game-logs`, `get-shots`, `get-possessions` (422, wrong parameters) |
| Basketball Reference | `robots.txt`, box score, play-by-play, shot chart, plus-minus, referee register |
| official.nba.com | referee assignments, injury report index |
| ak-static.cms.nba.com | Seven injury report PDFs from 2020 to today |
| stats.nba.com | `scoreboardv2`, `leaguedashptstats` (both timed out) |
| cdn.nba.com | live scoreboard, league schedule (both 403) |
| the-odds-api | `/v4/sports`, `/v4/sports/basketball_nba/events` (both 401) |
