# God's Eye Predictions (ATTD engine): instructions for Claude

- **Read `FACTORS.md` before any ATD or props work.** Every factor listed there is considered on every build; never drop
  a factor group or switch to a reduced feature set. New factors are added to `FEATURE_GROUPS` (`attd/model.py`).
- **Picks come from the model only.** No media, expert picks or pick sites. User reads go into `data/personnel.csv`.
- **Every pick ships with intel**: the role numbers, matchup (named defenders), environment, OC/DC tendencies and a risk line.
- **Weekly flow:**
  1. `python run.py download --season S`
  2. `python run.py project --season S --week W` (ATD)
  3. `python run.py card --season S --week W` (props + tickets)
  4. ATD and props slip PDFs, plus the script-first SGP PDF (`attd.script_sgp_pdf.render`)
  5. `python run.py site --season S --week W`, then republish the God's Eye artifact
     ([private artifact link, not committed])
- **After games:** `python run.py grade-card` (graded as shipped), then log the algorithm change.
- **Ledger of past slips:** `ledger/NFL-Algo-Complete-Ledger.md`.
- **Between builds:** `python run.py refresh --season S --week W` re-pulls injuries/rosters/lines/forecasts, diffs against
  the last snapshot (`data/watch_snapshots/`), logs to `data/news_log.jsonl`, writes `outputs/watch_<S>_wk<W>.md` and
  names shipped legs touched. Single-game ATD slip: `attd.game_atd_pdf.render(S, W, game_id, out)`.
- **Before every build:** `attd.espn_news.sweep(S, W, [dates], write=True)` (check names against the roster first), then project/card.
- **Kick-off window pack** (e.g. Sunday early games): `attd.early.build_window`, `attd.window_pdf.render_atd / render_master`,
  per-game PDF via `attd.script_sgp_pdf.render(S, W, window_games, ...)`. The site shows it automatically for the next window.
- **After every download:** `attd.espn_lines.sync(S, W, [dates])` (kick-off flexes and totals), then the ESPN injury sweep.
- **Full slate with matchups:** `attd.full_slate.build` + `attd.full_slate_pdf.render`; games listed in
  `data/matchup_read_games.txt` as `game_id,consensus` get the agreed slips on the site. Locked releases go in `outputs/official/`.
- **ESPN game-day roster caveat (learned Nov 22 2026):** the `inactive` flag from `espn_news.gameday` can carry over from a player's previous missed game. Evans and Hockenson showed inactive while the injury report had cleared them and the user confirmed both active. Cross-check any flagged skill player against the ESPN summary injury list (removed from the list = cleared) before logging him OUT.
- Nov 23 2026: Jacory Croskey-Merritt (WAS) set ACT in data/roster_2026.parquet by hand for Week 11. ESPN depth chart lists him RB1, off IR, DraftKings posted lines; nflverse roster still had RES. A re-download overwrites this.
