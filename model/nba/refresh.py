"""Refresh commands.

  python3 -m nba.refresh daily                 # everything: results, schedule, reports, referees, odds, snapshots
  python3 -m nba.refresh gameday               # only what changes late: injuries, starters, odds, closing prices
  python3 -m nba.refresh injuries-history      # official injury reports for every past game date (resumable)
  python3 -m nba.refresh csv path/to/sheet.csv GAME_ID    # load a pasted bet365 sheet for one game
"""
import json
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd

from common import odds_feed
from common.http import FetchError
from nba import fetch_data, injuries, sources
from nba.config import CONFIG, odds_api_key
from nba.ids import IdMap, TEAMS
from nba.store import RAW, connect, upsert


def idmap(con) -> IdMap:
    return IdMap(pd.read_sql("SELECT player_id, name, team_id FROM player_games ORDER BY known_at", con),
                 pd.read_sql("SELECT * FROM schedule", con))


def team_name(abbr: str) -> str:
    return TEAMS[abbr][0]


def load_injury_report(con, ids: IdMap, moment_utc: datetime) -> int:
    got = injuries.fetch_latest_before(moment_utc)
    if not got:
        return 0
    body, when = got
    rows = injuries.resolve_ids(injuries.parse_report(injuries.pdf_text(body), when), ids)
    return upsert(con, "injury_reports", rows)


def injuries_history(con) -> dict:
    """For every past game, the last official report at least `lead` minutes before its tip."""
    ids = idmap(con)
    lead = timedelta(minutes=CONFIG["injury_report_lead_min"])
    tips = pd.read_sql("SELECT DISTINCT tip_utc FROM games ORDER BY tip_utc", con).tip_utc
    slots = sorted({injuries.report_time_before(datetime.fromisoformat(t) - lead) for t in tips})
    have = set(pd.read_sql("SELECT DISTINCT report_utc FROM injury_reports", con).report_utc)
    n = miss = 0
    for s in slots:
        if s.astimezone(timezone.utc).isoformat(timespec="seconds") in have:
            continue
        got = injuries.fetch_report(s)
        if not got:
            miss += 1
            continue
        n += upsert(con, "injury_reports", injuries.resolve_ids(injuries.parse_report(injuries.pdf_text(got[0]), s), ids))
    new = ids.write_review()
    return {"slots": len(slots), "rows_loaded": n, "slots_without_report": miss, "names_sent_to_review": new}


def todays_games(con, days_ahead: int = 1) -> pd.DataFrame:
    now = datetime.now(timezone.utc)
    a, b = (now - timedelta(hours=6)).isoformat(), (now + timedelta(days=days_ahead)).isoformat()
    return pd.read_sql("SELECT * FROM schedule WHERE tip_utc BETWEEN ? AND ? ORDER BY tip_utc", con, params=[a, b])


def pull_odds(con, ids: IdMap, games: pd.DataFrame) -> dict:
    key = odds_api_key()
    if not key:
        # no Odds API key: DraftKings ladders through ESPN's odds API (points, rebounds, assists, threes)
        n, problems = 0, []
        for g in games.itertuples():
            try:
                rows, bad = sources.espn_draftkings_props(g.game_id, ids.names)
                con.execute("DELETE FROM odds WHERE game_id=? AND source='espn-core' AND known_at=?", [g.game_id, rows[0]["known_at"] if rows else ""])
                n += upsert(con, "odds", rows)
                problems += bad
            except FetchError as e:
                problems.append(f"{g.game_id}: {e}")
        return {"status": "ok: DraftKings via ESPN (ODDS_API_KEY is not set)", "rows": n, "problems": problems}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M")
    n, problems = 0, []
    try:
        events = odds_feed.api_events(key, RAW)
    except FetchError as e:
        return {"status": f"failed: {e}"}
    for ev in events:
        try:
            data, at = odds_feed.api_event_odds(key, ev["id"], RAW, odds_feed.all_api_markets(), CONFIG["odds_regions"],
                                                None, stamp)
        except FetchError as e:
            problems.append(str(e)); continue
        rows, bad = odds_feed.resolve(odds_feed.rows_from_api(data, at, CONFIG["odds_book"]), ids)
        problems += bad
        n += upsert(con, "odds", rows)
    return {"status": "ok", "rows": n, "problems": problems[:20], "events": len(events)}


def load_csv(con, path: str, game_id: str) -> dict:
    ids = idmap(con)
    g = pd.read_sql("SELECT * FROM schedule WHERE game_id=?", con, params=[game_id])
    if g.empty:
        return {"loaded": 0, "rejected": [f"game {game_id} is not on the schedule"]}
    rows, bad = odds_feed.read_csv(open(path).read())
    rows, bad2 = odds_feed.resolve(rows, ids, game_id, [g.home_id[0], g.away_id[0]])
    ids.write_review()
    return {"loaded": upsert(con, "odds", rows), "rejected": bad + bad2}


def gameday(con) -> dict:
    """Late-changing data only. Safe to run every few minutes."""
    ids = idmap(con)
    games = todays_games(con)
    out = {"games": len(games)}
    out["injury_rows"] = load_injury_report(con, ids, datetime.now(timezone.utc))
    starters = lines = closed = 0
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for g in games.itertuples():
        try:
            s, at = fetch_data.summary(g.game_id, max_age=120, tag=now[:16])
        except FetchError:
            continue
        line = sources.espn_market_line(s, g.game_id, at)
        if line and g.tip_utc > now:
            lines += upsert(con, "market_lines", [line])
        for tb in s.get("boxscore", {}).get("players", []):       # ESPN lists starters once the game begins
            for a in tb["statistics"][0]["athletes"]:
                if a.get("starter"):
                    starters += upsert(con, "starters", [{"game_id": g.game_id, "team_id": tb["team"]["id"],
                                                         "player_id": a["athlete"]["id"], "source": "espn_live", "known_at": at}])
        if g.tip_utc <= now:
            closed += odds_feed.mark_closing(con, g.game_id, g.tip_utc)
    out.update(starters=starters, market_lines=lines, closing_prices_marked=closed, odds=pull_odds(con, ids, games))
    try:
        out["referee_rows"] = upsert(con, "ref_assignments", sources.referee_assignments())
    except FetchError as e:
        out["referee_rows"] = f"failed: {e}"
    out["names_sent_to_review"] = ids.write_review()
    return out


def daily(con) -> dict:
    today = datetime.now(timezone.utc).date()
    out = {"results": fetch_data.pull_range(con, (today - timedelta(days=4)).isoformat(),
                                            (today + timedelta(days=3)).isoformat(), fresh_days=5)}
    out["gameday"] = gameday(con)
    season = f"{today.year if today.month >= 9 else today.year - 1}-{str((today.year if today.month >= 9 else today.year - 1) + 1)[2:]}"
    out["pbpstats_rows"] = sources.pbpstats_snapshot(con, season, (today - timedelta(days=1)).isoformat())
    return out


if __name__ == "__main__":
    con = connect()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "daily"
    res = {"daily": lambda: daily(con), "gameday": lambda: gameday(con), "injuries-history": lambda: injuries_history(con),
           "csv": lambda: load_csv(con, sys.argv[2], sys.argv[3])}[cmd]()
    print(json.dumps(res, indent=2, default=str))
