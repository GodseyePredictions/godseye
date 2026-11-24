"""Game-environment context: stadium/roof/surface, weather, kickoff slot, travel & time zones.

Historical weather comes from the NFL game-day weather string in play-by-play (recorded at kickoff).
Upcoming games use the US National Weather Service hourly forecast at kickoff (api.weather.gov).
Indoor (dome / closed roof) games get weather category "indoor" and neutral temp/wind.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .data import DATA_DIR

ET = ZoneInfo("America/New_York")

# stadium_id -> (lat, lon, IANA tz)
STADIUMS = {
    "ATL97": (33.7554, -84.4008, "America/New_York"), "BAL00": (39.2780, -76.6227, "America/New_York"),
    "BOS00": (42.0909, -71.2643, "America/New_York"), "BUF00": (42.7738, -78.7870, "America/New_York"),
    "CAR00": (35.2258, -80.8528, "America/New_York"), "CHI98": (41.8623, -87.6167, "America/Chicago"),
    "CIN00": (39.0955, -84.5161, "America/New_York"), "CLE00": (41.5061, -81.6995, "America/New_York"),
    "DAL00": (32.7473, -97.0945, "America/Chicago"), "DEN00": (39.7439, -105.0201, "America/Denver"),
    "DET00": (42.3400, -83.0456, "America/Detroit"), "GNB00": (44.5013, -88.0622, "America/Chicago"),
    "HOU00": (29.6847, -95.4107, "America/Chicago"), "IND00": (39.7601, -86.1639, "America/Indiana/Indianapolis"),
    "JAX00": (30.3239, -81.6373, "America/New_York"), "KAN00": (39.0489, -94.4839, "America/Chicago"),
    "LAX01": (33.9535, -118.3392, "America/Los_Angeles"), "MIA00": (25.9580, -80.2389, "America/New_York"),
    "MIN01": (44.9737, -93.2581, "America/Chicago"), "NAS00": (36.1665, -86.7713, "America/Chicago"),
    "NOR00": (29.9511, -90.0812, "America/Chicago"), "NYC01": (40.8135, -74.0745, "America/New_York"),
    "PHI00": (39.9008, -75.1675, "America/New_York"), "PHO00": (33.5276, -112.2626, "America/Phoenix"),
    "PIT00": (40.4468, -80.0158, "America/New_York"), "SEA00": (47.5952, -122.3316, "America/Los_Angeles"),
    "SFO01": (37.4030, -121.9700, "America/Los_Angeles"), "TAM00": (27.9759, -82.5033, "America/New_York"),
    "VEG00": (36.0909, -115.1833, "America/Los_Angeles"), "WAS00": (38.9078, -76.8645, "America/New_York"),
    # international
    "LON00": (51.5560, -0.2796, "Europe/London"), "LON01": (51.5560, -0.2796, "Europe/London"),
    "LON02": (51.6043, -0.0664, "Europe/London"), "FRA00": (50.0686, 8.6455, "Europe/Berlin"),
    "GER00": (48.2188, 11.6247, "Europe/Berlin"), "MUN01": (48.2188, 11.6247, "Europe/Berlin"),
    "MEX00": (19.3029, -99.1505, "America/Mexico_City"), "MAD01": (40.4531, -3.6883, "Europe/Madrid"),
    "MEL00": (-37.8200, 144.9834, "Australia/Melbourne"), "PAR00": (48.9244, 2.3601, "Europe/Paris"),
    "RIO00": (-22.9121, -43.2302, "America/Sao_Paulo"), "SAO00": (-23.5453, -46.4742, "America/Sao_Paulo"),
}
INTL = {"LON00", "LON01", "LON02", "FRA00", "GER00", "MUN01", "MEX00", "MAD01", "MEL00", "PAR00", "RIO00", "SAO00"}
TURF = {"fieldturf", "matrixturf", "sportturf", "astroturf", "a_turf", "turf"}
WX_CATS = ["indoor", "clear", "cloudy", "rain", "snow", "fog"]


def _hav_miles(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def wx_category(text: str | None, indoor: bool, pop: float | None = None) -> str:
    if indoor:
        return "indoor"
    t = (text or "").lower()
    chance = any(w in t for w in ("chance", "slight", "isolated", "scattered")) and (pop is None or pop < 50)
    if re.search(r"snow|flurr|sleet|blizzard|wintry", t) and not chance:
        return "snow"
    if re.search(r"rain|shower|drizzle|storm|thunder", t) and not chance:
        return "rain"
    if "fog" in t or "haze" in t:
        return "fog"
    if re.search(r"cloud|overcast|gray|grey", t):
        return "cloudy"
    if re.search(r"sun|clear|fair|nice|beautiful", t):
        return "clear"
    return "cloudy" if chance else "clear"


def _parse_wind(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return np.nan
    m = re.findall(r"\d+", str(x))
    return float(max(map(int, m))) if m else np.nan


# --------------------------------------------------------------------------------------------
def game_context(schedules: pd.DataFrame, pbp: pd.DataFrame, forecasts: dict | None = None) -> pd.DataFrame:
    """One row per (game_id, team) with environment, slot and travel features."""
    s = schedules.copy()
    # roof/surface: fill unknown (future) from the stadium's most recent known values
    s = s.sort_values(["season", "week"])
    for c in ("roof", "surface"):
        s[c] = s[c].replace("", np.nan)
        s[c] = s.groupby("stadium_id")[c].transform(lambda x: x.ffill().bfill())
    wx = pbp.drop_duplicates("game_id").set_index("game_id")[["weather", "temp", "wind"]]
    s = s.join(wx, on="game_id", rsuffix="_pbp")

    # home stadium per team-season = most common venue for its true home games
    hs = s[s.location == "Home"].groupby(["season", "home_team"]).stadium_id \
        .agg(lambda x: x.mode().iloc[0]).rename("home_stadium")
    rows = []
    forecasts = forecasts or {}
    for g in s.itertuples(index=False):
        sid = g.stadium_id if g.stadium_id in STADIUMS else None
        indoor = str(g.roof) in ("dome", "closed")
        fc = forecasts.get(g.game_id)
        if fc is not None and not indoor:
            cat = wx_category(fc["short"], indoor, fc.get("pop"))
            temp, wind = fc["temp"], fc["wind"]
        else:
            cat = wx_category(g.weather if isinstance(g.weather, str) else None, indoor)
            wtxt = g.weather if isinstance(g.weather, str) else ""
            mt, mw = re.search(r"Temp:\s*(-?\d+)", wtxt), re.search(r"Wind:[^\d]*(\d+)", wtxt)
            temp = g.temp if not pd.isna(g.temp) else (g.temp_pbp if not pd.isna(g.temp_pbp)
                                                       else (float(mt.group(1)) if mt else np.nan))
            wind = g.wind if not pd.isna(g.wind) else (_parse_wind(g.wind_pbp) if not pd.isna(g.wind_pbp)
                                                       else (float(mw.group(1)) if mw else np.nan))
            if not isinstance(g.weather, str) and pd.isna(temp) and not indoor:
                cat = "unknown"
        if indoor:
            temp, wind = 70.0, 0.0
        try:
            hh, mm = map(int, str(g.gametime).split(":"))
        except ValueError:
            hh, mm = 13, 0
        kick_et = datetime.fromisoformat(str(g.gameday)).replace(hour=hh, minute=mm, tzinfo=ET)
        et_hour = hh + mm / 60
        if g.weekday == "Sunday":
            slot = "early" if et_hour < 14.5 else ("late" if et_hour < 19 else "night")
            if et_hour < 11:
                slot = "intl_morning"
        else:
            slot = "night" if et_hour >= 19 else "other_day"
        for side in ("home", "away"):
            team = getattr(g, f"{side}_team")
            opp = g.away_team if side == "home" else g.home_team
            home_sid = hs.get((g.season, team))
            if home_sid not in STADIUMS:
                home_sid = sid
            venue = STADIUMS.get(sid or home_sid)
            home_loc = STADIUMS.get(home_sid)
            if venue and home_loc:
                miles = _hav_miles(home_loc[:2], venue[:2])
                home_tz, venue_tz = ZoneInfo(home_loc[2]), ZoneInfo(venue[2])
                tz_shift = (kick_et.astimezone(venue_tz).utcoffset() - kick_et.astimezone(home_tz).utcoffset()) \
                    .total_seconds() / 3600
                body = kick_et.astimezone(home_tz)
                body_hour = body.hour + body.minute / 60
            else:
                miles, tz_shift, body_hour = np.nan, np.nan, et_hour
            rest = getattr(g, f"{side}_rest")
            rows.append({
                "game_id": g.game_id, "team": team,
                "is_indoor": int(indoor), "is_turf": int(str(g.surface).lower() in TURF),
                "roof_type": str(g.roof), "wx_cat": cat, "temp": temp, "wind": wind,
                "wx_bad": int(cat in ("rain", "snow")), "cold": int((temp if not pd.isna(temp) else 60) <= 35),
                "windy": int((wind if not pd.isna(wind) else 0) >= 15),
                "slot": slot, "kick_et_hour": et_hour, "weekday": g.weekday,
                "is_intl": int(sid in INTL if sid else 0), "div_game": g.div_game,
                "travel_miles": 0.0 if side == "home" and sid == home_sid else miles,
                "tz_shift": tz_shift if side == "away" or sid != home_sid else 0.0,
                "body_clock_hour": body_hour,
                "early_body_clock": int(body_hour < 11.5),
                "rest_days": rest, "short_week": int(rest <= 5) if not pd.isna(rest) else 0,
                "post_bye": int(rest >= 10) if not pd.isna(rest) else 0,
            })
    c = pd.DataFrame(rows)
    c["slot_code"] = c.slot.map({"early": 0, "late": 1, "night": 2, "other_day": 3, "intl_morning": 4})
    c["wx_code"] = c.wx_cat.map({k: i for i, k in enumerate(WX_CATS)}).fillna(-1)
    return c


# --------------------------------------------------------------------------------------------
def fetch_forecasts(schedules: pd.DataFrame, season: int, week: int) -> dict:
    """NWS hourly forecast at kickoff for each outdoor US game in the given week. Cached per week."""
    cache = DATA_DIR / f"forecast_{season}_wk{week}.json"
    games = schedules[(schedules.season == season) & (schedules.week == week) & schedules.home_score.isna()]
    out = json.loads(cache.read_text()) if cache.exists() else {}
    ua = "attd-model (personal research)"

    def get(url):
        r = subprocess.run(["curl", "-sS", "-m", "25", "-A", ua, url], capture_output=True, text=True)
        return json.loads(r.stdout)

    for g in games.itertuples(index=False):
        if str(g.roof) in ("dome", "closed") or g.stadium_id in INTL or g.stadium_id not in STADIUMS:
            continue
        lat, lon, _ = STADIUMS[g.stadium_id]
        try:
            hh, mm = map(int, str(g.gametime).split(":"))
            kick = datetime.fromisoformat(str(g.gameday)).replace(hour=hh, minute=mm, tzinfo=ET)
            pt = get(f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}")
            periods = get(pt["properties"]["forecastHourly"])["properties"]["periods"]
            best = min(periods, key=lambda p: abs(datetime.fromisoformat(p["startTime"]) - kick))
            if abs(datetime.fromisoformat(best["startTime"]) - kick) > timedelta(hours=2):
                continue  # kickoff beyond the forecast horizon
            out[g.game_id] = {"short": best["shortForecast"], "temp": float(best["temperature"]),
                              "wind": _parse_wind(best["windSpeed"]),
                              "pop": (best.get("probabilityOfPrecipitation") or {}).get("value"),
                              "fetched": datetime.now(ET).isoformat(timespec="minutes")}
        except Exception as e:  # noqa: BLE001
            print(f"  [weather] {g.game_id}: forecast unavailable ({e.__class__.__name__})")
    cache.write_text(json.dumps(out, indent=1))
    return out


# --------------------------------------------------------------------------------------------
def player_context_splits(df: pd.DataFrame, k: float = 10.0) -> pd.DataFrame:
    """Shrunk player splits: how a player's scoring (0.5*TD + 0.5*xTD per game) in THIS game's context
    compares to his overall rate, using only prior games.  k = pseudo-games of shrinkage toward 1.0."""
    df = df.sort_values(["season", "week", "game_id"]).copy()
    df["_score"] = 0.5 * df.td + 0.5 * df.xtd           # NaN for future rows
    df["_s0"] = df._score.fillna(0)
    df["_n0"] = df._score.notna().astype(float)
    g = df.groupby("player_id")
    tot_s = g._s0.cumsum() - df._s0
    tot_n = g._n0.cumsum() - df._n0
    rate = (tot_s + 0.15 * 4) / (tot_n + 4)              # overall prior rate, lightly regularized
    df["home_away"] = df.is_home
    df["home_x_slot"] = df.is_home.astype(str) + "_" + df.slot.astype(str)
    df["home_x_roof"] = df.is_home.astype(str) + "_" + df.is_indoor.astype(str)
    df["home_x_surface"] = df.is_home.astype(str) + "_" + df.is_turf.astype(str)
    df["home_x_wx"] = df.is_home.astype(str) + "_" + df.wx_bad.astype(str)
    out = {}
    for c in ["home_away", "is_indoor", "is_turf", "slot", "wx_bad", "cold",
              "home_x_slot", "home_x_roof", "home_x_surface", "home_x_wx"]:
        gc = df.groupby(["player_id", c])
        cs = gc._s0.cumsum() - df._s0
        cn = gc._n0.cumsum() - df._n0
        out[f"split_{c}"] = ((cs + k * rate) / (cn + k)) / rate
        out[f"split_{c}_n"] = cn
    res = pd.DataFrame(out, index=df.index)
    return res.reindex(df.index)
