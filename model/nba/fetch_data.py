"""Pull every source the audit marked strong or usable, cache the raw responses, load the tables.

Usage (from model/):
  python3 -m nba.fetch_data history 2023-10-24 2026-04-12   # scoreboards + game summaries
  python3 -m nba.fetch_data build                           # raw cache -> SQLite tables
Every pull is resumable: responses already in data/raw are not asked for again.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

from common.http import FetchError, get
from nba import espn
from nba.config import CONFIG
from nba.store import RAW, connect, upsert

SB = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={}"
SM = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={}"
ESPN_GAP = CONFIG["min_interval"]["site.api.espn.com"]


def scoreboard(day: str, max_age=None) -> dict:
    return json.loads(get(SB.format(day.replace("-", "")), RAW, min_interval=ESPN_GAP, max_age=max_age)[0])


def summary(game_id: str, max_age=None, tag: str = "") -> tuple[dict, str]:
    body, at = get(SM.format(game_id), RAW, min_interval=ESPN_GAP, max_age=max_age, tag=tag)
    return json.loads(body), at


def schedule_rows(sb: dict) -> list[dict]:
    rows = []
    for e in sb.get("events", []):
        if e["season"]["type"] != 2:      # regular season only (includes cup group games)
            continue
        c = e["competitions"][0]
        side = {x["homeAway"]: x["team"] for x in c["competitors"]}
        tip = datetime.fromisoformat(e["date"].replace("Z", "+00:00"))
        rows.append({"game_id": e["id"], "season": e["season"]["year"],
                     "date_et": (tip - timedelta(hours=5)).date().isoformat(), "tip_utc": tip.isoformat(timespec="seconds"),
                     "home_id": side["home"]["id"], "away_id": side["away"]["id"], "home": side["home"]["abbreviation"],
                     "away": side["away"]["abbreviation"], "venue": (c.get("venue") or {}).get("fullName"),
                     "neutral": int(bool(c.get("neutralSite"))),
                     "_completed": bool(e["status"]["type"].get("completed"))})
    return rows


def days(first: str, last: str):
    d = date.fromisoformat(first)
    while d <= date.fromisoformat(last):
        yield d.isoformat()
        d += timedelta(days=1)


def load_game(con, game_id: str, max_age=None) -> bool:
    try:
        s, _ = summary(game_id, max_age=max_age)
    except FetchError as e:
        print(f"  summary {game_id}: {e}")
        return False
    p = espn.parse_summary(s, CONFIG)
    if not p:
        return False
    posted = p["game"]["date_et"] + "T%02d:00:00+00:00" % CONFIG["officials_posted_utc_hour"]
    for o in p["officials"]:
        o["known_at"] = min(posted, p["game"]["tip_utc"])
    upsert(con, "games", [p["game"]])
    upsert(con, "player_games", p["players"])
    upsert(con, "officials", p["officials"])
    upsert(con, "starters", p["starters"])
    return True


def pull_range(con, first: str, last: str, fresh_days: int = 0) -> dict:
    """Schedules for every day in range, summaries for finished games. Days within `fresh_days`
    of today are asked for again; older days come from the cache."""
    today = datetime.now(timezone.utc).date()
    have = {r[0] for r in con.execute("SELECT game_id FROM games")}
    n_sched = n_new = 0
    for day in days(first, last):
        recent = (today - date.fromisoformat(day)).days <= fresh_days
        try:
            rows = schedule_rows(scoreboard(day, max_age=600 if recent else None))
        except FetchError as e:
            print(f"  scoreboard {day}: {e}")
            continue
        done = [r for r in rows if r.pop("_completed")]
        n_sched += upsert(con, "schedule", rows)
        todo = [r["game_id"] for r in done if r["game_id"] not in have]
        with ThreadPoolExecutor(6) as ex:                 # fetch in parallel, load in order
            list(ex.map(lambda g: _quiet(g), todo))
        n_new += sum(load_game(con, g) for g in todo)
    return {"schedule_rows": n_sched, "new_games": n_new}


def _quiet(game_id):
    try:
        summary(game_id)
    except FetchError:
        pass


if __name__ == "__main__":
    con = connect()
    if sys.argv[1] == "history":
        print(pull_range(con, sys.argv[2], sys.argv[3]))
    elif sys.argv[1] == "build":
        for a, b in (("2023-10-24", "2024-04-14"), ("2024-10-22", "2025-04-13"), ("2025-10-21", "2026-04-12"),
                     ("2026-10-20", (datetime.now(timezone.utc).date() + timedelta(days=2)).isoformat())):
            print(a, b, pull_range(con, a, b, fresh_days=3))
