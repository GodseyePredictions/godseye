"""ESPN public-API injury sweep: finds players ESPN lists Out / Doubtful / IR (and, once posted, game-day inactives)
that the nflverse injury file does not already rule out. Prints them and can append them to data/personnel.csv."""
from __future__ import annotations

import json
import urllib.request
from datetime import date

import pandas as pd

from .data import DATA_DIR

import re

FIX = {"WSH": "WAS", "LAR": "LA"}
_nk = lambda x: re.sub(r"(jr|sr|ii|iii|iv)$", "", re.sub(r"[^a-z]", "", str(x).lower()))  # noqa: E731
UA = {"User-Agent": "Mozilla/5.0"}


def _get(u):
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read())


def sweep(season, week, dates, write=False):
    inj = pd.read_parquet(DATA_DIR / f"inj_{season}.parquet"); inj = inj[inj.week == week]
    known = {(r.team, _nk(r.full_name)) for r in inj.itertuples() if str(r.report_status) in ("Out", "Doubtful")}
    ro = pd.read_parquet(DATA_DIR / f"roster_{season}.parquet"); ro = ro[ro.week == ro.week.max()]
    rost = {(r.team, _nk(r.full_name)): (r.position, r.status) for r in ro.itertuples()}
    pf = DATA_DIR / "personnel.csv"; P = pd.read_csv(pf)
    have = {(r.team, _nk(r.name)) for r in P.itertuples(index=False) if str(r.as_of) >= str(date.today() - pd.Timedelta(days=6))}
    rows, quest = [], []
    for d in dates:
        sb = _get(f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={d}")
        for e in sb["events"]:
            if e["status"]["type"]["state"] != "pre":
                continue
            s = _get(f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={e['id']}")
            for t in s.get("injuries", []):
                team = FIX.get(t["team"]["abbreviation"], t["team"]["abbreviation"])
                for x in t.get("injuries", []):
                    nm = x["athlete"]["displayName"]; st = x.get("status", ""); pos = x["athlete"].get("position", {}).get("abbreviation", "")
                    det = (x.get("details") or {}); typ = det.get("type", "")
                    key = (team, _nk(nm))
                    if st in ("Out", "Injured Reserve", "Doubtful", "Suspension", "Inactive"):
                        if key in known or key in have:
                            continue
                        if key in rost and rost[key][1] != "ACT":
                            continue          # already off the active roster in nflverse
                        rows.append((nm, team, "OUT", f"ESPN {st} ({pos}{', ' + typ if typ else ''}), swept {date.today()}", str(date.today())))
                    elif st == "Questionable" and pos in ("QB", "RB", "WR", "TE"):
                        quest.append((team, nm, pos, typ))
    out = pd.DataFrame(rows, columns=["name", "team", "status", "note", "as_of"])
    if write and len(out):
        pd.concat([P, out], ignore_index=True).to_csv(pf, index=False)
    return out, pd.DataFrame(quest, columns=["team", "name", "pos", "type"])


def gameday(dates, kick_hours=None):
    """Official game-day rosters from ESPN's core API: inactives (didNotPlay) and listed starters per team."""
    out = []
    for d in dates:
        sb = _get(f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={d}")
        for e in sb["events"]:
            if e["status"]["type"]["state"] != "pre":
                continue
            if kick_hours and int(e["date"][11:13]) not in kick_hours:
                continue
            for c in e["competitions"][0]["competitors"]:
                team = FIX.get(c["team"]["abbreviation"], c["team"]["abbreviation"])
                r = _get(f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events/{e['id']}/competitions/{e['id']}/competitors/{c['id']}/roster?limit=200")
                for x in r.get("entries", []):
                    if not (x.get("didNotPlay") or x.get("starter")):
                        continue
                    pos = ""
                    try:
                        a = _get(x["athlete"]["$ref"].replace("http://", "https://")); name = a.get("fullName") or a.get("displayName"); pos = a.get("position", {}).get("abbreviation", "")
                    except Exception:  # noqa: BLE001
                        name = x.get("displayName")
                    out.append({"game": e["shortName"], "team": team, "name": name, "pos": pos,
                                "inactive": bool(x.get("didNotPlay")), "starter": bool(x.get("starter"))})
    return pd.DataFrame(out)
