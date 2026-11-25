"""NHL API: schedule, play-by-play, shift charts, officials and scratches, TOI by strength, rosters.

Hosts: api-web.nhle.com (schedule, gamecenter, rosters) and api.nhle.com/stats/rest (shift charts and the
league's own even-strength / power-play / shorthanded ice time). Fetching and parsing are kept apart: every
`parse_*` takes the decoded JSON and returns plain rows, so the tests run on saved responses with no network.

What the NHL API does not have: an injury feed. Injured-reserve players come from Daily Faceoff's line pages
(ingest/dailyfaceoff.py) and a game's scratches from the gamecenter right-rail here.
"""
import json
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

from common.http import FetchError, get

WEB = "https://api-web.nhle.com/v1"
STATS = "https://api.nhle.com/stats/rest/en"
PERIOD_SEC = 1200
SHOT_TYPES = {"shot-on-goal", "missed-shot", "blocked-shot", "goal"}
FINAL_STATES = {"OFF", "FINAL"}


def _json(url, root, cfg, max_age=None, tag=""):
    host = url.split("/")[2]
    body, _ = get(url, root, min_interval=cfg["sources"]["min_interval"].get(host, 0.5),
                  retries=cfg["sources"]["retries"], max_age=max_age, tag=tag)
    return json.loads(body)


def mmss(s: str) -> int:
    m, sec = s.split(":")
    return int(m) * 60 + int(sec)


# ------------------------------------------------------------------ schedule
def parse_schedule_week(doc: dict, game_types=(2,)) -> list[dict]:
    rows = []
    for day in doc.get("gameWeek", []):
        for g in day.get("games", []):
            if g.get("gameType") not in game_types:
                continue
            off = g.get("venueUTCOffset") or "+00:00"
            sign = -1 if off.startswith("-") else 1
            hh, mm = off.lstrip("+-").split(":")
            rows.append({"game_id": g["id"], "season": g["season"] // 10000, "game_type": g["gameType"], "date_et": day["date"],
                         "start_utc": g["startTimeUTC"], "home": g["homeTeam"]["abbrev"], "away": g["awayTeam"]["abbrev"],
                         "home_id": g["homeTeam"]["id"], "away_id": g["awayTeam"]["id"], "venue": g.get("venue", {}).get("default"),
                         "venue_utc_offset": sign * (int(hh) + int(mm) / 60), "neutral": int(bool(g.get("neutralSite"))),
                         "state": g.get("gameState")})
    return rows


def season_schedule(season: int, root, cfg, current: bool = False) -> list[dict]:
    """Every game of one season (season = the year it starts), walked a week at a time."""
    max_age = cfg["sources"]["schedule_max_age_sec"] if current else None
    first = _json(f"{WEB}/schedule/{season}-10-15", root, cfg, max_age)
    day, end = first["regularSeasonStartDate"], first["regularSeasonEndDate"]
    rows, seen = [], set()
    today = datetime.now(timezone.utc).date()
    while day <= end:
        live = current and abs((date.fromisoformat(day) - today).days) <= 8     # this week's game states change by the hour
        doc = _json(f"{WEB}/schedule/{day}", root, cfg, cfg["sources"]["live_week_max_age_sec"] if live else max_age)
        for r in parse_schedule_week(doc, tuple(cfg["seasons"]["game_types"])):
            if r["game_id"] not in seen and r["season"] == season:
                seen.add(r["game_id"]); rows.append(r)
        nxt = doc.get("nextStartDate")
        if not nxt or nxt <= day:
            break
        day = nxt
    return rows


# ------------------------------------------------------------------ one game
def game_max_age(date_et: str, cfg, today: date | None = None):
    """Old games never change; the last two days may still be corrected, so they are re-read."""
    today = today or datetime.now(timezone.utc).date()
    return cfg["sources"]["recent_game_max_age_sec"] if date.fromisoformat(date_et) >= today - timedelta(days=2) else None


def fetch_game(game_id: int, date_et: str, root, cfg) -> dict:
    """Raw play-by-play, right-rail (officials, scratches) and shift chart for one finished game."""
    age = game_max_age(date_et, cfg)
    out = {"pbp": _json(f"{WEB}/gamecenter/{game_id}/play-by-play", root, cfg, age)}
    try:
        out["rail"] = _json(f"{WEB}/gamecenter/{game_id}/right-rail", root, cfg, age)
    except FetchError:
        out["rail"] = {}
    try:
        url = f"{STATS}/shiftcharts?cayenneExp=gameId={game_id}"
        out["shifts"] = _json(url, root, cfg, age)
        if not out["shifts"].get("data"):             # the league sometimes posts a shift chart late: ask again, once a day
            out["shifts"] = _json(url, root, cfg, cfg["sources"]["empty_shifts_retry_sec"])
    except FetchError:
        out["shifts"] = {"data": []}
    return out


def parse_pbp(doc: dict) -> dict:
    """Flatten a play-by-play document. Shootout attempts are dropped: they are not goals, shots or saves.

    Times are seconds from the opening face-off. `seconds` is the length of the game that was played
    (3,600 plus any overtime)."""
    home, away = doc["homeTeam"], doc["awayTeam"]
    team_of = {home["id"]: home["abbrev"], away["id"]: away["abbrev"]}
    roster = {r["playerId"]: {"team": team_of.get(r["teamId"]), "pos": r.get("positionCode"),
                              "name": f"{r['firstName']['default']} {r['lastName']['default']}"} for r in doc.get("rosterSpots", [])}
    events, ot_len, shootout = [], 0, False
    for e in doc.get("plays", []):
        pd_ = e.get("periodDescriptor", {})
        if pd_.get("periodType") == "SO":
            shootout = True
            continue
        per = pd_.get("number", 1)
        t = mmss(e.get("timeInPeriod", "00:00"))
        if per > 3:
            ot_len = max(ot_len, t + (per - 4) * PERIOD_SEC)
        d = e.get("details", {})
        kind = e.get("typeDescKey")
        ev = {"sec": (per - 1) * PERIOD_SEC + t, "period": per, "type": kind, "code": e.get("situationCode"),
              "team": team_of.get(d.get("eventOwnerTeamId"))}
        if kind in SHOT_TYPES:
            shooter = d.get("shootingPlayerId") or d.get("scoringPlayerId")
            ev.update(shooter=shooter, goalie=d.get("goalieInNetId"), blocker=d.get("blockingPlayerId"),
                      a1=d.get("assist1PlayerId"), a2=d.get("assist2PlayerId"))
            if shooter in roster:                     # a blocked shot's "owner" is not always the shooter's side
                ev["team"] = roster[shooter]["team"]
        elif kind == "hit":
            ev.update(hitter=d.get("hittingPlayerId"))
            if d.get("hittingPlayerId") in roster:
                ev["team"] = roster[d["hittingPlayerId"]]["team"]
        elif kind == "penalty":
            by = d.get("committedByPlayerId") or d.get("servedByPlayerId")
            ev.update(by=d.get("committedByPlayerId"), drawn=d.get("drawnByPlayerId"), pen_type=d.get("typeCode"),
                      desc=d.get("descKey"), minutes=d.get("duration") or 0)
            if by in roster:
                ev["team"] = roster[by]["team"]
        events.append(ev)
    last = doc.get("periodDescriptor", {}).get("periodType", "REG")
    return {"game_id": doc["id"], "season": doc["season"] // 10000, "date_et": doc["gameDate"], "start_utc": doc["startTimeUTC"],
            "state": doc.get("gameState"), "home": home["abbrev"], "away": away["abbrev"],
            "home_goals": home.get("score", 0), "away_goals": away.get("score", 0),
            "venue": doc.get("venue", {}).get("default"), "decided": "SO" if shootout or last == "SO" else ("OT" if last == "OT" else "REG"),
            "seconds": 3 * PERIOD_SEC + ot_len, "roster": roster, "events": events}


def parse_shifts(doc: dict, seconds: int) -> list[tuple[int, int, int]]:
    """(player_id, start, end) in game seconds, end exclusive. Goal rows in the feed (typeCode 505) are skipped."""
    out = []
    for s in doc.get("data", []):
        if s.get("typeCode") != 517 or not s.get("startTime") or not s.get("endTime"):
            continue
        base = (s["period"] - 1) * PERIOD_SEC
        a, b = base + mmss(s["startTime"]), base + mmss(s["endTime"])
        if a < seconds and b > a:
            out.append((s["playerId"], a, min(b, seconds)))
    return out


def parse_rail(doc: dict, pbp: dict) -> tuple[list[dict], list[dict]]:
    """Officials and scratches for one game."""
    info = doc.get("gameInfo") or {}
    name = lambda o: (o.get("fullName") or o).get("default")     # both shapes have been served
    offs = [{"game_id": pbp["game_id"], "name": name(o), "role": role}
            for key, role in (("referees", "referee"), ("linesmen", "linesperson"))
            for o in info.get(key, []) if name(o)]
    scr = [{"game_id": pbp["game_id"], "team": pbp[side], "player_id": p["id"],
            "name": f"{p['firstName']['default']} {p['lastName']['default']}"}
           for key, side in (("homeTeam", "home"), ("awayTeam", "away")) for p in (info.get(key) or {}).get("scratches", [])]
    return offs, scr


# ------------------------------------------------------------------ league TOI by strength
def parse_toi(doc: dict) -> list[dict]:
    return [{"game_id": r["gameId"], "player_id": r["playerId"], "team": r.get("teamAbbrev"), "date_et": r["gameDate"],
             "ev": r.get("evTimeOnIce") or 0, "pp": r.get("ppTimeOnIce") or 0, "sh": r.get("shTimeOnIce") or 0,
             "total": r.get("timeOnIce") or 0} for r in doc.get("data", [])]


def toi_by_strength(date_et: str, root, cfg) -> list[dict]:
    """Every skater's EV / PP / SH seconds for the games of one day, as the league counts them.
    The stats API serves at most 100 rows a call, so the day is read a page at a time, in a fixed order:
    without the sort, pages overlap and rows go missing."""
    order = quote('[{"property":"gameId","direction":"ASC"},{"property":"playerId","direction":"ASC"}]')
    q = quote(f'gameDate>="{date_et}" and gameDate<="{date_et} 23:59:59" and gameTypeId=2')
    rows, start = [], 0
    while True:
        doc = _json(f"{STATS}/skater/timeonice?isAggregate=false&isGame=true&start={start}&limit=100&sort={order}&cayenneExp={q}",
                    root, cfg, game_max_age(date_et, cfg))
        page = parse_toi(doc)
        rows += page
        start += 100
        if not page or start >= doc.get("total", 0):
            return rows


# ------------------------------------------------------------------ rosters
def parse_roster(doc: dict, team: str) -> list[dict]:
    return [{"player_id": p["id"], "name": f"{p['firstName']['default']} {p['lastName']['default']}",
             "pos": p.get("positionCode"), "team": team}
            for grp in ("forwards", "defensemen", "goalies") for p in doc.get(grp, [])]


def roster(team: str, root, cfg) -> list[dict]:
    return parse_roster(_json(f"{WEB}/roster/{team}/current", root, cfg, cfg["sources"]["schedule_max_age_sec"]), team)


# ------------------------------------------------------------------ the league's betting partner (game lines only)
def parse_partner_odds(doc: dict, known_at: str) -> list[dict]:
    """Moneyline, 60-minute three-way, puck line and total from the partner book the NHL shows (odds rows)."""
    book = ((doc.get("bettingPartner") or {}).get("name") or "partner").lower()
    rows = []
    for g in doc.get("games", []):
        for side in ("homeTeam", "awayTeam"):
            team = g[side]["abbrev"]
            for o in g[side].get("odds", []):
                kind, q, price = o.get("description"), (o.get("qualifier") or "").strip(), o.get("value")
                if price is None:
                    continue
                base = {"known_at": known_at, "source": "nhl-partner", "book": book, "game_id": g["gameId"], "player_id": None,
                        "price": float(price), "is_close": 0}
                if kind == "MONEY_LINE_2_WAY":
                    rows.append({**base, "market": "ml", "player_name": team, "side": "team", "line": 0.0})
                elif kind == "MONEY_LINE_3_WAY":
                    if q.lower() == "draw":
                        if side == "homeTeam":
                            rows.append({**base, "market": "ml3", "player_name": "Draw", "side": "draw", "line": 0.0})
                    else:
                        rows.append({**base, "market": "ml3", "player_name": team, "side": "team", "line": 0.0})
                elif kind == "PUCK_LINE" and q:
                    rows.append({**base, "market": "spread", "player_name": team, "side": "team", "line": float(q)})
                elif kind == "OVER_UNDER" and q[:1] in ("O", "U"):
                    rows.append({**base, "market": "total", "player_name": "", "side": "over" if q[0] == "O" else "under", "line": float(q[1:])})
    return rows


def partner_odds(root, cfg) -> list[dict]:
    """The partner feed only serves the current odds date; callers keep the games they want by id."""
    from datetime import datetime as _dt, timezone as _tz
    url = f"{WEB}/partner-game/{cfg['sources']['partner_country']}/now"
    host = url.split("/")[2]
    body, at = get(url, root, min_interval=cfg["sources"]["min_interval"].get(host, 0.5), retries=cfg["sources"]["retries"],
                   max_age=cfg["sources"]["gameday_max_age_sec"], tag=_dt.now(_tz.utc).strftime("%Y%m%dT%H") )
    return parse_partner_odds(json.loads(body), at)
