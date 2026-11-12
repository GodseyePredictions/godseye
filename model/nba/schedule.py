"""Schedule features: rest days, back-to-backs, three games in four nights, travel and time zones.

Arena coordinates are a hand-entered table (the sources give city and state only), keyed by the
ESPN team abbreviation. A game at a neutral site has no travel figure rather than a wrong one.
"""
import math
from datetime import date

import pandas as pd

from nba.config import CONFIG

# team: (latitude, longitude, hours from UTC in winter)
ARENAS = {
    "ATL": (33.757, -84.396, -5), "BOS": (42.366, -71.062, -5), "BKN": (40.683, -73.975, -5),
    "CHA": (35.225, -80.839, -5), "CHI": (41.881, -87.674, -6), "CLE": (41.497, -81.688, -5),
    "DAL": (32.790, -96.810, -6), "DEN": (39.749, -105.008, -7), "DET": (42.341, -83.055, -5),
    "GS": (37.768, -122.388, -8), "HOU": (29.751, -95.362, -6), "IND": (39.764, -86.156, -5),
    "LAC": (33.945, -118.343, -8), "LAL": (34.043, -118.267, -8), "MEM": (35.138, -90.051, -6),
    "MIA": (25.781, -80.187, -5), "MIL": (43.045, -87.917, -6), "MIN": (44.979, -93.276, -6),
    "NO": (29.949, -90.082, -6), "NY": (40.751, -73.994, -5), "OKC": (35.463, -97.515, -6),
    "ORL": (28.539, -81.384, -5), "PHI": (39.901, -75.172, -5), "PHX": (33.446, -112.071, -7),
    "POR": (45.532, -122.667, -8), "SAC": (38.580, -121.500, -8), "SA": (29.427, -98.438, -6),
    "TOR": (43.643, -79.379, -5), "UTAH": (40.768, -111.901, -7), "WSH": (38.898, -77.021, -5),
}


def miles(a, b) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def team_schedule_features(schedule: pd.DataFrame, cfg=CONFIG) -> pd.DataFrame:
    """One row per team per game. Uses only the schedule (dates and places), which is published
    before the season, so nothing here can leak a result."""
    s = schedule.sort_values("tip_utc")
    rows = []
    for home_side in (True, False):
        t = s.assign(team=s.home if home_side else s.away, team_id=s.home_id if home_side else s.away_id,
                     opp_id=s.away_id if home_side else s.home_id, is_home=int(home_side), site=s.home)
        rows.append(t[["game_id", "season", "date_et", "tip_utc", "team", "team_id", "opp_id", "is_home", "site", "neutral"]])
    t = pd.concat(rows).sort_values(["team_id", "tip_utc"]).reset_index(drop=True)
    out = []
    for _, g in t.groupby(["team_id", "season"], sort=False):
        dates = [date.fromisoformat(d) for d in g.date_et]
        prev_site, prev_date = None, None
        for i, r in enumerate(g.itertuples()):
            d = dates[i]
            rest = (d - prev_date).days - 1 if prev_date else None
            n4 = sum(1 for x in dates[:i + 1] if (d - x).days < cfg["three_in_four_days"])
            here = None if r.neutral else ARENAS.get(r.site)
            was = ARENAS.get(prev_site) if prev_site else ARENAS.get(r.team)
            if prev_date and (d - prev_date).days > 4:      # long gap: assume the team went home in between
                was = ARENAS.get(r.team)
            travel = miles(was, here) if here and was else None
            tz = (here[2] - was[2]) if here and was else None
            out.append({"game_id": r.game_id, "team_id": r.team_id, "opp_id": r.opp_id, "is_home": r.is_home,
                        "rest_days": rest, "b2b": int(rest == 0) if rest is not None else 0,
                        "three_in_four": int(n4 >= 3), "travel_miles": travel, "tz_change": tz,
                        "game_no": i + 1})
            prev_site, prev_date = (None if r.neutral else r.site), d
    return pd.DataFrame(out)
