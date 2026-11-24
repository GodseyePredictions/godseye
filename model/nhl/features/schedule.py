"""Schedule spots: rest, back-to-backs, three-in-four, travel and time zones, for every team in every game.

Built from the schedule alone, which is public months ahead, so nothing here can leak a result.
Travel is great-circle distance between the home rinks of consecutive games (a neutral-site game is
placed at the listed home team's rink, and flagged).
"""
import math
from datetime import date

import pandas as pd


def km(a: dict, b: dict, radius: float) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def build(schedule: pd.DataFrame, teams: list[dict], cfg) -> pd.DataFrame:
    """One row per (game, team): rest_days, b2b, three_in_four, games_last_7, travel_km, km_last_7,
    tz_shift (hours east is positive), and the same for the opponent as rest_diff."""
    c = cfg["schedule"]
    where = {t["abbrev"]: t for t in teams}
    rows = []
    s = schedule.sort_values(["start_utc", "game_id"])
    long = pd.concat([s.assign(team=s.home, opp=s.away, is_home=1), s.assign(team=s.away, opp=s.home, is_home=0)])
    for (team, season), g in long.sort_values("start_utc").groupby(["team", "season"]):
        days, kms, prev = [], [], None
        for r in g.itertuples():
            d = date.fromisoformat(r.date_et)
            here = where.get(r.home)
            rest = (d - prev["d"]).days if prev else None
            start = prev["at"] if prev else where.get(team)
            dist = km(start, here, c["earth_radius_km"]) if start and here else None
            shift = (r.venue_utc_offset - prev["off"]) if prev and r.venue_utc_offset is not None and prev["off"] is not None else 0.0
            days.append(d); kms.append(dist or 0.0)
            in4 = sum(1 for x in days if (d - x).days < c["three_in_four_days"])
            in7 = [i for i, x in enumerate(days) if (d - x).days < 7]
            rows.append({"game_id": r.game_id, "team": team, "opp": r.opp, "is_home": r.is_home, "season": season,
                         "date_et": r.date_et, "rest_days": rest, "b2b": int(rest is not None and rest <= c["b2b_days"]),
                         "three_in_four": int(in4 >= 3), "games_last_7": len(in7) - 1,
                         "travel_km": None if dist is None else round(dist, 1), "km_last_7": round(sum(kms[i] for i in in7), 1),
                         "tz_shift": shift, "neutral": int(r.neutral)})
            prev = {"d": d, "at": here, "off": r.venue_utc_offset}
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    opp = out[["game_id", "team", "rest_days", "b2b"]].rename(columns={"team": "opp", "rest_days": "opp_rest_days", "b2b": "opp_b2b"})
    out = out.merge(opp, on=["game_id", "opp"], how="left")
    out["rest_diff"] = out.rest_days - out.opp_rest_days
    return out.sort_values(["date_et", "game_id", "is_home"]).reset_index(drop=True)
