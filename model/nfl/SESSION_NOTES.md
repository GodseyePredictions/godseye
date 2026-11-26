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
- Nov 24 2026 (scheduled build): Croskey-Merritt set ACT again on the Week 12 roster rows after the download reset him to RES. He played 28 snaps in Week 11 and ESPN lists him Active. Daniel Jones shows CUT for IND and is off ESPN's Colts roster, so that one is real and was left alone.
- Nov 24 2026: the owner said in this session that scheduled NFL builds (Tue/Thu/Sat) may merge to main and publish on their own when the site check and tests pass. Stop-and-report conditions in the task still apply.
- Nov 24 2026 (owner): the published site is the app preview (home page, branding, white slips). Every NFL publish goes: `python run.py site`, `npm run nfl:site`, tests, `node scripts/build-preview.mjs <out.html>`, then publish that file to the app preview artifact. Merge the latest main first so the NBA side is current. Every set slip in the console is a white ticket (`.ticket`), and SGP ladders are drawn as set slips, never as bare buttons.
- Nov 25 2026 (owner read, relayed by the master session): "no Adams no Nacua, done for season. Myles Garrett back and Micah Parsons back." Checked against ESPN at 21:00 UTC: Adams and Nacua on injured reserve (already RES in the roster data); Garrett active and starting for LA (already ACT); Parsons on Green Bay's active roster, listed questionable, while nflverse still had him RES, so he was set ACT on the Week 12 rows. Parsons has no 2026 snaps, so the defensive-personnel features (snap-weighted absences) do not change with his return; the model has no way yet to credit a star defender coming back.
- Nov 25 2026 (owner read, this session): "Kyren is still RB1 for Rams." ESPN's Rams depth chart lists Kyren Williams first (then Corum, Rivers). The displaced-back hold came from one game (Week 10: Rivers 15 carries, Williams 12). Williams added to data/ticket_overrides.txt; the displaced-back hold in attd/early.py now skips names in that file. Clear the file after the game.
- Nov 26 2026: Kyren Williams cleared from data/ticket_overrides.txt after GB @ LA (final LA 26, GB 13).
