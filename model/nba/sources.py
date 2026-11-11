"""Smaller pulls: referee assignments, ESPN injury notes, ESPN market lines, pbpstats snapshots."""
import html
import json
import re
from datetime import datetime, timezone

from common.http import FetchError, get
from nba.config import CONFIG
from nba.store import RAW, upsert

GAP = CONFIG["min_interval"]


def referee_assignments(max_age=900) -> list[dict]:
    """Tonight's crews from official.nba.com. The page shows today only, so it is captured every day."""
    body, at = get("https://official.nba.com/referee-assignments/", RAW, min_interval=GAP["official.nba.com"],
                   max_age=max_age, tag=datetime.now(timezone.utc).strftime("%Y%m%d"))
    t = body.decode("utf8", "ignore")
    m = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December) (\d{1,2}), (20\d\d)", t)
    if not m:
        return []
    day = datetime.strptime(" ".join(m.groups()), "%B %d %Y").date().isoformat()
    nba = t.split("G League")[0] if "G League" in t else t
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", nba, flags=re.S):
        cells = [html.unescape(re.sub("<[^>]+>", "", c)).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S)]
        if len(cells) >= 4 and "@" in cells[0]:
            for role, name in zip(("crew_chief", "referee", "umpire"), cells[1:4]):
                name = re.sub(r"\s*\(#\d+\)", "", name).strip()
                if name:
                    rows.append({"date_et": day, "matchup": cells[0], "name": name, "role": role, "known_at": at})
    return rows


def espn_injury_notes(idmap, max_age=600) -> dict:
    """player_id -> latest ESPN note (free text). Used only to spot stated minutes restrictions."""
    body, _ = get("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries", RAW,
                  min_interval=GAP["site.api.espn.com"], max_age=max_age, tag=datetime.now(timezone.utc).strftime("%Y%m%d%H"))
    out = {}
    for t in json.loads(body).get("injuries", []):
        tid = idmap.team(t.get("displayName", ""), "espn_injuries")
        for i in t.get("injuries", []):
            pid = idmap.player(i["athlete"]["displayName"], [tid] if tid else None, "espn_injuries")
            if pid:
                out[pid] = " ".join(x for x in (i.get("shortComment"), i.get("longComment")) if x)
    return out


def espn_market_line(summary: dict, game_id: str, known_at: str) -> dict | None:
    """Spread, total and moneyline that ESPN shows before a game (DraftKings). ESPN drops these
    once a game is old, so they only exist for games captured on the day."""
    pc = summary.get("pickcenter") or []
    if not pc:
        return None
    p = pc[0]
    if p.get("spread") is None and p.get("overUnder") is None:
        return None
    return {"game_id": game_id, "known_at": known_at, "provider": "espn:" + (p.get("provider") or {}).get("name", "?"),
            "spread_home": p.get("spread"), "total": p.get("overUnder"),
            "ml_home": (p.get("homeTeamOdds") or {}).get("moneyLine"), "ml_away": (p.get("awayTeamOdds") or {}).get("moneyLine")}


def pbpstats_snapshot(con, season: str, to_date: str) -> int:
    """Possession-level team and player totals up to `to_date`, kept as dated snapshots.
    Stored for later use; the models do not read these yet (see docs/nba_data_health.md)."""
    con.execute("CREATE TABLE IF NOT EXISTS pbp_snapshots (snapshot_date TEXT, kind TEXT, entity_id TEXT, name TEXT, "
                "team TEXT, data TEXT, known_at TEXT, PRIMARY KEY (snapshot_date, kind, entity_id))")
    n = 0
    for kind in ("Team", "Opponent", "Player", "Lineup"):
        url = (f"https://api.pbpstats.com/get-totals/nba?Season={season}&SeasonType=Regular%20Season&Type={kind}"
               f"&ToDate={to_date}")
        try:
            body, at = get(url, RAW, min_interval=GAP["api.pbpstats.com"], timeout=90)
        except FetchError as e:
            print(f"  pbpstats {kind}: {e}")
            continue
        rows = [{"snapshot_date": to_date, "kind": kind, "entity_id": str(r.get("EntityId")), "name": r.get("Name"),
                 "team": r.get("TeamAbbreviation"), "data": json.dumps(r), "known_at": at}
                for r in json.loads(body).get("multi_row_table_data", [])]
        n += upsert(con, "pbp_snapshots", rows)
    return n
