"""Turn a raw ESPN game summary into rows: game, player box lines, officials, starters, market line.

Play-by-play adds what the box score lacks: shots by zone for each player, seconds played in each
quarter (rebuilt from substitutions), fourth-quarter shots, and the lead through the second half.
"""
import math
from datetime import datetime, timedelta, timezone

HOOP_X = 25.0  # ESPN shot coordinates are in feet with the basket at x=25, y=0


def _clock(s: str) -> float:
    if ":" in s:
        m, sec = s.split(":")
        return int(m) * 60 + float(sec)
    return float(s)


def _plen(p: int) -> int:
    return 720 if p <= 4 else 300


def zone(x, y, pts3: bool, cfg) -> str | None:
    if x is None or y is None or abs(x) > 100 or abs(y) > 100:
        return None
    if pts3:
        return "c3" if y <= cfg["corner3_max_y"] else "ab3"
    return "rim" if math.hypot(x - HOOP_X, y) <= cfg["rim_max_ft"] else "mid"


def period_seconds(plays: list, team_of: dict, box_sec: dict) -> dict:
    """Seconds on the floor per player per period, from substitutions.

    A player is on the floor at the start of a period if his first appearance in it is anything
    other than being substituted in. If that leaves a team short of five, the gap is filled with
    the players whose box-score minutes are furthest above what has been found for them.
    """
    periods = sorted({p["period"]["number"] for p in plays})
    out = {pid: {} for pid in team_of}
    short = []
    for per in periods:
        ev = [p for p in plays if p["period"]["number"] == per]
        seen, start, order = set(), {}, []
        for p in ev:
            ids = [a["athlete"]["id"] for a in p.get("participants", []) if (a.get("athlete") or {}).get("id")]
            if p["type"]["text"] == "Substitution" and len(ids) == 2:
                i, o = ids
                if o not in seen and o in team_of:
                    seen.add(o); start.setdefault(team_of[o], []).append(o)
                seen.add(i)
            else:
                for a in ids:
                    if a not in seen and a in team_of:
                        seen.add(a); start.setdefault(team_of[a], []).append(a)
        length = _plen(per)
        on = {t: set(v[:5]) for t, v in start.items()}
        since = {a: length for v in on.values() for a in v}
        acc = {}
        for p in ev:
            if p["type"]["text"] != "Substitution":
                continue
            ids = [a["athlete"]["id"] for a in p.get("participants", []) if (a.get("athlete") or {}).get("id")]
            if len(ids) != 2 or ids[0] not in team_of:
                continue
            i, o = ids
            t, now = team_of[i], _clock(p["clock"]["displayValue"])
            if o in on.get(t, ()):
                on[t].discard(o); acc[o] = acc.get(o, 0) + since.pop(o, now) - now
            on.setdefault(t, set()).add(i); since[i] = now
        for a, s in since.items():
            acc[a] = acc.get(a, 0) + s
        for a, s in acc.items():
            out[a][per] = max(0.0, s)
        for t in set(team_of.values()):
            n = len(start.get(t, [])[:5])
            if n < 5:
                short.append((per, t, 5 - n))
    for per, t, need in short:  # fill gaps with the biggest unexplained box-score minutes
        cands = sorted(((box_sec.get(a, 0) - sum(out[a].values()), a) for a in team_of
                        if team_of[a] == t and per not in out[a]), reverse=True)
        for gap, a in cands[:need]:
            if gap > _plen(per) * 0.5:
                out[a][per] = float(_plen(per))
    return out


def parse_summary(s: dict, cfg: dict) -> dict | None:
    comp = s["header"]["competitions"][0]
    if not comp["status"]["type"].get("completed"):
        return None
    gid = s["header"]["id"]
    side = {c["homeAway"]: c for c in comp["competitors"]}
    h, a = side["home"], side["away"]
    tip = datetime.fromisoformat(comp["date"].replace("Z", "+00:00"))
    plays = s.get("plays") or []
    wall = [p["wallclock"] for p in plays if p.get("wallclock")]
    ended = max(wall) if wall else (tip + timedelta(hours=3)).isoformat()
    ended = datetime.fromisoformat(ended.replace("Z", "+00:00")).astimezone(timezone.utc)
    if ended <= tip:
        ended = tip + timedelta(hours=3)
    known = ended.isoformat(timespec="seconds")
    hq = [int(float(l.get("displayValue") or 0)) for l in h.get("linescores", [])]
    aq = [int(float(l.get("displayValue") or 0)) for l in a.get("linescores", [])]
    if len(hq) < 4 or len(aq) < 4:
        return None
    year = s["header"]["season"]["year"]

    players, team_of, box_sec = [], {}, {}
    for tb in s["boxscore"].get("players", []):
        tid = tb["team"]["id"]
        st = tb["statistics"][0]
        ix = {l: i for i, l in enumerate(st["labels"])}
        for at in st["athletes"]:
            v = at.get("stats") or []
            dnp = bool(at.get("didNotPlay")) or not v
            def num(k, part=None):
                if dnp or k not in ix:
                    return 0
                x = v[ix[k]]
                if part is not None:
                    x = x.split("-")[part] if "-" in x else 0
                try:
                    return float(x)
                except (TypeError, ValueError):
                    return 0
            pid = at["athlete"].get("id")
            if not pid:
                continue
            team_of[pid] = tid
            box_sec[pid] = num("MIN") * 60
            players.append({
                "game_id": gid, "team_id": tid, "player_id": pid, "name": at["athlete"].get("displayName"),
                "pos": (at["athlete"].get("position") or {}).get("abbreviation"), "starter": int(bool(at.get("starter"))),
                "dnp": int(dnp), "reason": at.get("reason") if dnp else None, "min": num("MIN"), "pts": num("PTS"),
                "reb": num("REB"), "oreb": num("OREB"), "dreb": num("DREB"), "ast": num("AST"), "stl": num("STL"),
                "blk": num("BLK"), "tov": num("TO"), "pf": num("PF"), "fgm": num("FG", 0), "fga": num("FG", 1),
                "fg3m": num("3PT", 0), "fg3a": num("3PT", 1), "ftm": num("FT", 0), "fta": num("FT", 1),
                "rim_a": 0, "rim_m": 0, "mid_a": 0, "mid_m": 0, "c3_a": 0, "c3_m": 0, "ab3_a": 0, "ab3_m": 0,
                "sec_q1": None, "sec_q2": None, "sec_q3": None, "sec_q4": None, "sec_ot": None,
                "q4_fga": 0, "q4_pts": 0, "known_at": known})
    if not players:
        return None
    by_id = {p["player_id"]: p for p in players}

    lead_h = lead_a = 0
    close5 = 0
    for p in plays:
        per = p["period"]["number"]
        hs, as_ = p.get("homeScore"), p.get("awayScore")
        if hs is not None and as_ is not None and per in (3, 4):
            lead_h, lead_a = max(lead_h, hs - as_), max(lead_a, as_ - hs)
            if per == 4 and _clock(p["clock"]["displayValue"]) <= 300 and abs(hs - as_) <= cfg["close_margin"]:
                close5 = 1
        if p.get("shootingPlay") and p.get("participants") and "Free Throw" not in p["type"]["text"]:
            pid = (p["participants"][0].get("athlete") or {}).get("id")
            row = by_id.get(pid)
            pa = p.get("pointsAttempted") or (3 if "three point" in p.get("text", "").lower() else 2)
            c = p.get("coordinate") or {}
            z = zone(c.get("x"), c.get("y"), pa == 3, cfg)
            if row is not None:
                made = int(bool(p.get("scoringPlay")))
                if z:
                    row[z + "_a"] += 1; row[z + "_m"] += made
                if per == 4:
                    row["q4_fga"] += 1; row["q4_pts"] += made * pa
    if plays:
        secs = period_seconds(plays, team_of, box_sec)
        for pid, d in secs.items():
            r = by_id[pid]
            if r["dnp"]:
                continue
            for q in (1, 2, 3, 4):
                r[f"sec_q{q}"] = d.get(q, 0.0)
            r["sec_ot"] = sum(v for k, v in d.items() if k > 4)

    game = {"game_id": gid, "season": year, "date_et": (tip - timedelta(hours=5)).date().isoformat(),
            "tip_utc": tip.isoformat(timespec="seconds"), "known_at": known,
            "home_id": h["team"]["id"], "away_id": a["team"]["id"], "home": h["team"]["abbreviation"],
            "away": a["team"]["abbreviation"], "venue": (s.get("gameInfo", {}).get("venue") or {}).get("fullName"),
            "neutral": int(bool(comp.get("neutralSite"))), "completed": 1,
            "home_pts": int(h["score"]), "away_pts": int(a["score"]), "periods": len(hq),
            "hq1": hq[0], "hq2": hq[1], "hq3": hq[2], "hq4": hq[3], "aq1": aq[0], "aq2": aq[1], "aq3": aq[2], "aq4": aq[3],
            "max_lead_2h_home": lead_h, "max_lead_2h_away": lead_a, "close_last5": close5}
    officials = [{"game_id": gid, "name": o.get("displayName"), "known_at": game["tip_utc"]}
                 for o in s.get("gameInfo", {}).get("officials", []) if o.get("displayName")]
    starters = [{"game_id": gid, "team_id": p["team_id"], "player_id": p["player_id"], "source": "espn_box",
                 "known_at": game["tip_utc"]} for p in players if p["starter"]]
    return {"game": game, "players": players, "officials": officials, "starters": starters}
