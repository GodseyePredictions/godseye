"""Data health report: rows per table, date coverage, missing fields. Writes docs/nba_data_health.md.

Usage (from model/):  python3 -m nba.health
"""
import pandas as pd

from nba import ledger
from nba.ids import REVIEW
from nba.store import HERE, connect

DOC = HERE.parent.parent / "docs" / "nba_data_health.md"
DATES = {"games": "date_et", "schedule": "date_et", "player_games": "known_at", "officials": "known_at", "starters": "known_at",
         "injury_reports": "report_utc", "ref_assignments": "date_et", "market_lines": "known_at", "odds": "known_at",
         "availability": "known_at", "pbp_snapshots": "snapshot_date", "nba_runs": "run_at",
         "nba_projections": "run_at", "nba_legs": "run_at", "nba_tickets": "run_at", "nba_game_cards": "run_at",
         "nba_report_cards": "slate_date", "nba_status_changes": "seen_at"}


def main():
    con = connect()
    ledger.init(con)
    have = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    L = ["# NBA data health report", "", f"Generated {ledger.now()} from `model/nba/data/nba.sqlite`.", "",
         "## Rows and date coverage", "", "| table | rows | first | last |", "|---|---|---|---|"]
    for t, d in DATES.items():
        if t not in have:
            L.append(f"| {t} | not created yet | | |")
            continue
        n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        a, b = con.execute(f"SELECT MIN({d}), MAX({d}) FROM {t}").fetchone() if d and n else ("", "")
        L.append(f"| {t} | {n:,} | {str(a)[:10]} | {str(b)[:10]} |")
    g = pd.read_sql("SELECT season, COUNT(*) games, MIN(date_et) first, MAX(date_et) last FROM games GROUP BY season", con)
    s = pd.read_sql("SELECT season, COUNT(*) scheduled FROM schedule GROUP BY season", con)
    g = g.merge(s, on="season")
    L += ["", "## Games by season", "", "| season | finished games loaded | on the schedule | first | last |", "|---|---|---|---|---|"]
    L += [f"| {r.season - 1}-{str(r.season)[2:]} | {r.games:,} | {r.scheduled:,} | {r.first} | {r.last} |" for r in g.itertuples()]
    pg = pd.read_sql("SELECT * FROM player_games", con)
    played = pg[pg["min"] > 0]
    L += ["", "## Missing fields", "", "| check | result |", "|---|---|"]
    L.append(f"| Box-score lines | {len(pg):,} ({len(played):,} with minutes, {len(pg) - len(played):,} did not play) |")
    L.append(f"| Played lines with no position | {played.pos.isna().sum():,} |")
    L.append(f"| Played lines with no seconds-by-quarter (no play-by-play) | {played.sec_q4.isna().sum():,} |")
    sec = played.dropna(subset=["sec_q4"])
    tot = (sec.sec_q1 + sec.sec_q2 + sec.sec_q3 + sec.sec_q4 + sec.sec_ot) / 60
    L.append(f"| Rebuilt minutes vs box-score minutes | mean gap {abs(tot - sec['min']).mean():.2f} min; {(abs(tot - sec['min']) > 2).mean():.2%} of lines off by more than 2 |")
    z = played.rim_a + played.mid_a + played.c3_a + played.ab3_a
    L.append(f"| Shots with a zone vs box-score attempts | {z.sum():,} of {played.fga.sum():,} ({z.sum() / played.fga.sum():.2%}) |")
    gm = pd.read_sql("SELECT * FROM games", con)
    off = pd.read_sql("SELECT game_id, COUNT(*) n FROM officials GROUP BY game_id", con)
    L.append(f"| Games with no officials listed | {len(gm) - len(off):,} of {len(gm):,} |")
    L.append(f"| Games with fewer than 3 officials | {(off.n < 3).sum():,} |")
    inj = pd.read_sql("SELECT report_utc, game_date, player_name, player_id, status FROM injury_reports", con)
    named = inj[inj.player_name != ""]
    L.append(f"| Injury reports loaded | {inj.report_utc.nunique():,} reports, {len(inj):,} rows |")
    L.append(f"| Injury rows whose player name found no exact match | {named.player_id.isna().sum():,} of {len(named):,} ({named.player_id.isna().mean():.2%}) |")
    dates = set(gm.date_et)
    cov = len(dates & set(inj.game_date)) / len(dates)
    L.append(f"| Game dates with at least one injury report | {cov:.1%} |")
    ml = pd.read_sql("SELECT COUNT(DISTINCT game_id) n FROM market_lines", con).n[0]
    L.append(f"| Games with a market spread and total | {ml:,} (ESPN keeps these only on the day; none exist for past seasons) |")
    od = pd.read_sql("SELECT COUNT(*) n FROM odds", con).n[0]
    L.append(f"| Player prop and alternate-line prices | {od:,} rows" + (" (no odds key and no bet365 sheet loaded yet)" if od == 0 else "") + " |")
    L.append(f"| Closing prices captured | {pd.read_sql('SELECT COUNT(*) n FROM odds WHERE is_close=1', con).n[0]:,} |")
    st = pd.read_sql("SELECT source, COUNT(DISTINCT game_id) n FROM starters GROUP BY source", con)
    L.append(f"| Starters | {'; '.join(f'{r.source}: {r.n:,} games' for r in st.itertuples())}. Known only once a game starts: no pre-tip source |")
    if REVIEW.exists():
        rv = pd.read_csv(REVIEW)
        L.append(f"| Names waiting in the review file | {len(rv):,} ({', '.join(f'{k}: {v}' for k, v in rv.kind.value_counts().items())}) |")
    L += ["", "## Not ingested, and why", "",
          "| Data | Reason |", "|---|---|",
          "| Tracking, hustle, matchup, play-type, defender distance | `stats.nba.com` does not answer from this cloud environment (audit, Part B) |",
          "| Confirmed starters before tip-off | No reachable free source. ESPN lists starters only after tip |",
          "| Historical prop prices, alternate lines, closing prices | No Odds API key; ESPN drops old lines |",
          "| Basketball Reference pages | Not needed: box scores, play-by-play and officials all come from ESPN with history. Kept out to respect its crawl limits |",
          "| Minutes restrictions for past seasons | The official report does not publish them; ESPN's notes exist only for today |",
          "| Player age | Not in any source pulled. The minutes model uses each player's own history instead |",
          "", "pbpstats possession-level totals (team, opponent, player, lineup) are snapshotted daily into `pbp_snapshots` "
          "but the models do not read them yet: they cannot be re-pulled for past dates fast enough to backtest."]
    DOC.write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
