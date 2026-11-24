"""Sync kick-off times and totals from ESPN's scoreboard into data/schedules.csv (nflverse lags on flexed games and
late line moves). Run after every download."""
from __future__ import annotations

import json
import urllib.request
from zoneinfo import ZoneInfo

import pandas as pd

from .data import DATA_DIR

FIX = {"WSH": "WAS", "LAR": "LA"}


def sync(season, week, dates):
    s = pd.read_csv(DATA_DIR / "schedules.csv"); ch = []
    for d in dates:
        req = urllib.request.Request(f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={d}", headers={"User-Agent": "Mozilla/5.0"})
        for e in json.loads(urllib.request.urlopen(req, timeout=30).read())["events"]:
            c = e["competitions"][0]; t = {x["homeAway"]: FIX.get(x["team"]["abbreviation"], x["team"]["abbreviation"]) for x in c["competitors"]}
            m = (s.season == season) & (s.week == week) & (s.home_team == t["home"]) & (s.away_team == t["away"])
            if not m.any() or e["status"]["type"]["state"] != "pre":
                continue
            et = pd.Timestamp(e["date"]).tz_convert(ZoneInfo("America/New_York"))
            new = {"gametime": et.strftime("%H:%M"), "gameday": et.strftime("%Y-%m-%d")}
            o = (c.get("odds") or [{}])[0]
            if o.get("overUnder"): new["total_line"] = float(o["overUnder"])
            for k, v in new.items():
                old = s.loc[m, k].iloc[0]
                if str(old) != str(v) and not (k == "total_line" and abs(float(old) - float(v)) < 0.01):
                    ch.append(f"{t['away']}@{t['home']} {k}: {old} -> {v}"); s.loc[m, k] = v
    s.to_csv(DATA_DIR / "schedules.csv", index=False)
    return ch
