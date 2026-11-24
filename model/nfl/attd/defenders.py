"""Who they're against: defender-level ratings rolled into unit strength for the defenders who actually play.

Per defender (from play-by-play, keyed on gsis id):
  coverage splash = pass breakups + 2 x interceptions        (CB, S)
  front splash    = sacks + 0.5 x QB hits + tackles for loss  (DL, LB)
EWMA per game (shifted, no look-ahead) x the defender's typical snap share.

Unit index for a game = sum over that unit's ACTIVE defenders (played that game in history; for an upcoming game:
on the active roster, not ruled Out/Doubtful, not in personnel.csv), plus unit availability = active snap share /
the unit's normal snap share.  Also returns the named defenders for the intel sheets.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import data as D
from .features import _shift_ewm

UNIT = {"CB": "CB", "DB": "CB", "S": "S", "FS": "S", "SS": "S", "LB": "LB", "ILB": "LB", "OLB": "LB", "MLB": "LB",
        "DL": "DL", "DT": "DL", "DE": "DL", "NT": "DL"}
UNIT_N = {"CB": 3, "S": 2, "LB": 2, "DL": 4}   # normal starters per unit (snap-share denominator)
DEF_PBP_COLS = ["pass_defense_1_player_id", "pass_defense_2_player_id", "interception_player_id", "sack_player_id",
                "half_sack_1_player_id", "half_sack_2_player_id", "qb_hit_1_player_id", "qb_hit_2_player_id",
                "tackle_for_loss_1_player_id", "tackle_for_loss_2_player_id"]


def _nkey(s):
    return (s.fillna("").str.lower().str.replace(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", regex=True)
            .str.replace(r"[^a-z]", "", regex=True))


def defender_games(seasons, rosters, snaps) -> pd.DataFrame:
    """One row per defender-game with gsis id, unit, snap share and splash stats."""
    pbp = D._read_many("pbp", seasons, ["game_id", "season_type"] + DEF_PBP_COLS)
    pbp = pbp[pbp.season_type.isin(["REG", "POST"])]
    def cnt(cols, w=1.0):
        s = pd.concat([pbp[["game_id", c]].rename(columns={c: "pid"}) for c in cols]).dropna()
        return s.groupby(["game_id", "pid"]).size() * w
    stats = pd.concat({
        "pd": cnt(["pass_defense_1_player_id", "pass_defense_2_player_id"]),
        "int": cnt(["interception_player_id"]),
        "sack": cnt(["sack_player_id"]).add(cnt(["half_sack_1_player_id", "half_sack_2_player_id"], 0.5), fill_value=0),
        "qbh": cnt(["qb_hit_1_player_id", "qb_hit_2_player_id"]),
        "tfl": cnt(["tackle_for_loss_1_player_id", "tackle_for_loss_2_player_id"]),
    }, axis=1).fillna(0).reset_index().rename(columns={"level_1": "pid"})

    sn = snaps[(snaps.defense_snaps > 0) & snaps.position.isin(UNIT)].copy()
    sn["unit"] = sn.position.map(UNIT)
    ro = rosters.dropna(subset=["gsis_id"])[["season", "team", "full_name", "gsis_id"]].drop_duplicates()
    ro["nk"] = _nkey(ro.full_name)
    ro = ro.drop_duplicates(["season", "team", "nk"])
    sn["nk"] = _nkey(sn.player)
    sn = sn.merge(ro[["season", "team", "nk", "gsis_id"]], on=["season", "team", "nk"], how="left")
    sn = sn.merge(stats, left_on=["game_id", "gsis_id"], right_on=["game_id", "pid"], how="left").drop(columns="pid")
    for c in ["pd", "int", "sack", "qbh", "tfl"]:
        sn[c] = sn[c].fillna(0)
    sn["cov"] = sn["pd"] + 2 * sn["int"]
    sn["front"] = sn.sack + 0.5 * sn.qbh + sn.tfl
    sn["pkey"] = sn.gsis_id.fillna(sn.team + ":" + sn.player)
    return sn[["game_id", "season", "week", "team", "player", "pkey", "unit", "defense_pct", "cov", "front",
               "pd", "int", "sack", "tfl"]]


def unit_indices(dg: pd.DataFrame, upcoming: pd.DataFrame | None = None):
    """dg: defender-games. upcoming: rows [game_id, season, week, team, pkey] of projected active defenders.
    Returns (unit index per (game_id, def team), named defenders for upcoming games)."""
    dg = dg.copy()
    dg["is_future"] = False
    if upcoming is not None and len(upcoming):
        last = dg.sort_values(["season", "week"]).drop_duplicates("pkey", keep="last").set_index("pkey")
        u = upcoming.copy()
        u["player"] = u.pkey.map(last.player)
        u["unit"] = u.pkey.map(last.unit)
        u["is_future"] = True
        dg = pd.concat([dg, u.dropna(subset=["unit"])], ignore_index=True)
    dg = dg.sort_values(["season", "week", "game_id"]).reset_index(drop=True)
    r = _shift_ewm(dg, "pkey", ["cov", "front", "defense_pct", "pd", "int", "sack", "tfl"], 6.0, "_e")
    dg = pd.concat([dg, r], axis=1)
    dg["games_played"] = dg.groupby("pkey").cumcount()
    w = dg.defense_pct_e.fillna(0.5)
    dg["cov_w"] = dg.cov_e.fillna(0) * 1.0
    dg["front_w"] = dg.front_e.fillna(0) * 1.0
    dg["snap_w"] = w
    g = dg.groupby(["game_id", "team", "unit"]).agg(cov=("cov_w", "sum"), front=("front_w", "sum"),
                                                     snaps=("snap_w", lambda x: x.nlargest(6).sum()))
    g = g.unstack("unit")
    out = pd.DataFrame(index=g.index)
    for u in ("CB", "S", "LB", "DL"):
        out[f"def_{u}_cov"] = g[("cov", u)] if ("cov", u) in g else np.nan
        out[f"def_{u}_front"] = g[("front", u)] if ("front", u) in g else np.nan
        out[f"def_{u}_avail"] = (g[("snaps", u)] / UNIT_N[u]).clip(upper=1.5) if ("snaps", u) in g else np.nan
    out["def_secondary_cov"] = out[["def_CB_cov", "def_S_cov"]].sum(axis=1)
    out["def_front_splash"] = out[["def_DL_front", "def_LB_front"]].sum(axis=1)
    out = out.reset_index().rename(columns={"team": "def_team"})
    names = None
    if upcoming is not None:
        f = dg[dg.is_future].copy()
        f = f.sort_values("defense_pct_e", ascending=False)
        names = f.groupby(["game_id", "team", "unit"]).head(UNIT_N.get("DL", 4))[
            ["game_id", "team", "unit", "player", "defense_pct_e", "pd_e", "int_e", "sack_e", "tfl_e", "games_played"]]
    return out, names


def projected_defenders(season, week, sched, rosters, snaps, injuries, dg) -> pd.DataFrame:
    """Defenders expected to play in each unplayed game of the week."""
    games = sched[(sched.season == season) & (sched.week == week) & sched.home_score.isna()]
    teams = pd.concat([games[["game_id", "home_team"]].rename(columns={"home_team": "team"}),
                       games[["game_id", "away_team"]].rename(columns={"away_team": "team"})])
    cur = dg[dg.season == season]
    recent_weeks = cur.groupby("team").week.apply(lambda x: sorted(x.unique())[-4:])
    rows = []
    for t, wks in recent_weeks.items():
        q = cur[(cur.team == t) & cur.week.isin(wks)]
        rows.append(q.drop_duplicates("pkey")[["team", "pkey", "player"]])
    act = pd.concat(rows) if rows else pd.DataFrame(columns=["team", "pkey", "player"])
    inj = injuries[(injuries.season == season) & (injuries.week == week) &
                   injuries.report_status.isin(["Out", "Doubtful"])]
    out_ids = set(inj.gsis_id)
    act = act[~act.pkey.isin(out_ids)]
    pf = D.DATA_DIR / "personnel.csv"
    if pf.exists():
        P = pd.read_csv(pf)
        P = P[P.status.str.upper().isin(["OUT", "INACTIVE", "TRADED", "IR"])]
        act = act[~_nkey(act.player).isin(set(_nkey(P.name)))]
    # roster status gate (IR / reserve this week)
    r = rosters[(rosters.season == season)]
    wk = week if (r.week == week).any() else r.week.max()
    inactive = set(r[(r.week == wk) & (r.status != "ACT")].gsis_id)
    act = act[~act.pkey.isin(inactive)]
    act = act.merge(teams, on="team")
    act["season"], act["week"] = season, week
    return act[["game_id", "season", "week", "team", "pkey"]]
