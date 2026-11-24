"""Leakage-safe player-game feature construction.

Every feature for game g uses only information from games strictly before g (shift-then-EWMA),
plus pre-game information (Vegas lines, home/away, who is active). Upcoming games are appended as
pseudo-rows with empty outcomes so the exact same code path produces features for prediction.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import SKILL_POS
from .xtd import prep_plays

POS_GROUP = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE"}

PLAYER_STATS = ["carries", "rush_rz", "rush_i10", "rush_i5", "rush_xtd", "rush_td",
                "targets", "tgt_rz", "tgt_i10", "ez_tgt", "rec_xtd", "rec_td",
                "xtd", "td", "yds", "deep_tgt", "short_tgt", "air_yds", "yac"]
SHARE_STATS = ["carries", "rush_rz", "rush_i10", "rush_i5", "rush_xtd",
               "targets", "tgt_rz", "tgt_i10", "ez_tgt", "rec_xtd", "xtd", "td",
               "deep_tgt", "short_tgt", "air_yds"]
HL_SHORT, HL_LONG = 3.0, 10.0


# --------------------------------------------------------------------------------------------
# Per-game aggregation
# --------------------------------------------------------------------------------------------
def player_game_stats(rushes: pd.DataFrame, targets: pd.DataFrame, pbp: pd.DataFrame) -> pd.DataFrame:
    key = ["game_id", "season", "week", "posteam", "player_id"]
    r = rushes.assign(
        carries=1, rush_rz=(rushes.yardline_100 <= 20).astype(int),
        rush_i10=(rushes.yardline_100 <= 10).astype(int), rush_i5=(rushes.yardline_100 <= 5).astype(int),
        rush_xtd=rushes.xtd, rush_td=rushes.y, yds=rushes.yards_gained.fillna(0),
    ).groupby(key)[["carries", "rush_rz", "rush_i10", "rush_i5", "rush_xtd", "rush_td", "yds"]].sum()
    t = targets.assign(
        targets=1, tgt_rz=(targets.yardline_100 <= 20).astype(int),
        tgt_i10=(targets.yardline_100 <= 10).astype(int), ez_tgt=targets.ez_target,
        rec_xtd=targets.xtd, rec_td=targets.y,
        yds=np.where(targets.complete_pass == 1, targets.yards_gained.fillna(0), 0),
        deep_tgt=(targets.air_yards >= 20).astype(int), short_tgt=(targets.air_yards <= 5).astype(int),
        air_yds=targets.air_yards.clip(lower=0),
        yac=np.where(targets.complete_pass == 1, targets.yards_after_catch.fillna(0), 0),
    ).groupby(key)[["targets", "tgt_rz", "tgt_i10", "ez_tgt", "rec_xtd", "rec_td", "yds", "deep_tgt",
                    "short_tgt", "air_yds", "yac"]].sum()
    s = r.add(t, fill_value=0).fillna(0).reset_index()

    # Label: any offensive TD credited to the player (rush, rec, or offensive fumble recovery)
    tdp = pbp[(pbp.touchdown == 1) & (pbp.td_team == pbp.posteam) & pbp.td_player_id.notna()
              & pbp.play_type.isin(["run", "pass"]) & (pbp.two_point_attempt != 1)]
    tdc = tdp.groupby(["game_id", "td_player_id"]).size().rename("td").reset_index() \
        .rename(columns={"td_player_id": "player_id"})
    s = s.merge(tdc, on=["game_id", "player_id"], how="left")
    s["td"] = s.td.fillna(0)
    s["xtd"] = s.rush_xtd + s.rec_xtd
    return s


def team_game_table(pbp: pd.DataFrame, rushes, targets, schedules: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, team) incl. upcoming games from the schedule."""
    p = pbp[pbp.play_type.isin(["run", "pass"]) & (pbp.two_point_attempt != 1)]
    offtd = p[(p.touchdown == 1) & (p.td_team == p.posteam)]
    g = p.groupby(["game_id", "posteam"]).agg(plays=("play_type", "size"),
                                                drives=("fixed_drive", "nunique")).reset_index()
    tds = offtd.groupby(["game_id", "posteam"]).agg(team_td=("touchdown", "size"),
                                                     team_rush_td=("rush", "sum")).reset_index()
    rx = rushes.groupby(["game_id", "posteam"]).xtd.sum().rename("team_rush_xtd").reset_index()
    tx = targets.groupby(["game_id", "posteam"]).xtd.sum().rename("team_rec_xtd").reset_index()
    for d in (tds, rx, tx):
        g = g.merge(d, on=["game_id", "posteam"], how="left")
    g = g.fillna({"team_td": 0, "team_rush_td": 0, "team_rush_xtd": 0, "team_rec_xtd": 0})
    g["team_pass_td"] = g.team_td - g.team_rush_td
    g["team_xtd"] = g.team_rush_xtd + g.team_rec_xtd
    g = g.rename(columns={"posteam": "team"})

    # schedule -> two rows per game with Vegas-implied team totals
    s = schedules[["game_id", "season", "week", "gameday", "home_team", "away_team",
                   "spread_line", "total_line", "home_score", "away_score"]].copy()
    home = s.assign(team=s.home_team, opp=s.away_team, is_home=1,
                    spread=s.spread_line, pts=s.home_score)
    away = s.assign(team=s.away_team, opp=s.home_team, is_home=0,
                    spread=-s.spread_line, pts=s.away_score)
    tg = pd.concat([home, away], ignore_index=True)
    tg["implied"] = (tg.total_line + tg.spread) / 2.0
    tg = tg[["game_id", "season", "week", "gameday", "team", "opp", "is_home", "spread",
             "total_line", "implied", "pts"]]
    tg = tg.merge(g, on=["game_id", "team"], how="left")
    tg["played"] = tg.plays.notna()
    return tg


# --------------------------------------------------------------------------------------------
# Rolling helpers
# --------------------------------------------------------------------------------------------
def _shift_ewm(df: pd.DataFrame, by: str, cols: list[str], hl: float, suffix: str) -> pd.DataFrame:
    shifted = df.groupby(by, sort=False)[cols].shift(1).astype(float)
    shifted[by] = df[by].values
    out = shifted.groupby(by, sort=False)[cols].ewm(halflife=hl, ignore_na=True).mean()
    out = out.reset_index(level=0, drop=True).sort_index()
    return out.reindex(df.index).add_suffix(suffix)


def team_features(tg: pd.DataFrame) -> pd.DataFrame:
    tg = tg.sort_values(["season", "week"]).reset_index(drop=True)
    off_cols = ["team_td", "team_rush_td", "team_pass_td", "team_xtd", "team_rush_xtd", "team_rec_xtd",
                "plays", "pts"]
    played = tg[tg.played | tg.pts.isna()]  # completed games + future games
    o = _shift_ewm(played, "team", off_cols, 6.0, "_ewm")
    tgf = played.join(o)

    # Defense: what each opponent ALLOWS. Build a defense-keyed frame and roll it.
    d = played[["game_id", "season", "week", "opp"] + off_cols].rename(columns={"opp": "def_team"})
    d = d.sort_values(["season", "week"]).reset_index(drop=True)
    dr = _shift_ewm(d, "def_team", off_cols, 6.0, "_allowed_ewm")
    d = d[["game_id", "def_team"]].join(dr)
    tgf = tgf.merge(d, left_on=["game_id", "opp"], right_on=["game_id", "def_team"], how="left") \
        .drop(columns="def_team")
    # Fill missing Vegas line with rolling-points-based estimate
    fallback = 0.5 * tgf.pts_ewm.fillna(22) + 0.5 * tgf.pts_allowed_ewm.fillna(22)
    tgf["implied_filled"] = tgf.implied.fillna(fallback)
    tgf["spread"] = tgf.spread.fillna(0)
    tgf["total_line"] = tgf.total_line.fillna(tgf.implied_filled * 2)
    return tgf


# --------------------------------------------------------------------------------------------
# Main builder
# --------------------------------------------------------------------------------------------
def build_player_games(pbp, rosters, snaps, schedules, xtd_model, future: pd.DataFrame | None = None):
    """Return (player_game feature frame, team-game frame).

    future: optional frame [game_id, season, week, team, player_id, position, name] of projected actives
            for games not yet played.
    """
    qb_ids = set(rosters.loc[rosters.position == "QB", "gsis_id"].dropna())
    rushes, targets = prep_plays(pbp, qb_ids)
    rushes, targets = xtd_model.score(rushes, targets)
    stats = player_game_stats(rushes, targets, pbp)

    # ---- player-game base from snap counts (includes players with 0 touches) ----
    from .data import id_map
    m = id_map(rosters)
    sn = snaps[snaps.offense_snaps > 0].merge(m, left_on="pfr_player_id", right_on="pfr_id", how="inner")
    team_snaps = snaps.groupby(["game_id", "team"]).offense_snaps.max().rename("team_snaps")
    sn = sn.join(team_snaps, on=["game_id", "team"])
    sn = sn[["game_id", "season", "week", "team", "gsis_id", "offense_snaps", "offense_pct"]] \
        .rename(columns={"gsis_id": "player_id"}).drop_duplicates(["game_id", "player_id"])

    base = stats.rename(columns={"posteam": "team"}).merge(
        sn, on=["game_id", "season", "week", "team", "player_id"], how="outer")
    for c in PLAYER_STATS:
        base[c] = base[c].fillna(0)

    # position / name from rosters (latest record per player)
    pos = rosters.dropna(subset=["gsis_id"]).sort_values(["season", "week"]) \
        .drop_duplicates("gsis_id", keep="last")[["gsis_id", "position", "full_name", "birth_date",
                                                   "rookie_year", "draft_number"]] \
        .rename(columns={"gsis_id": "player_id", "full_name": "name"})
    base = base.merge(pos, on="player_id", how="left")
    base = base[base.position.isin(SKILL_POS)]
    base["is_future"] = False

    if future is not None and len(future):
        f = future.copy()
        f["is_future"] = True
        for c in PLAYER_STATS:
            f[c] = np.nan
        f = f.merge(pos.drop(columns=["position", "name"]), on="player_id", how="left")
        base = pd.concat([base, f], ignore_index=True)

    base["pos_group"] = base.position.map(POS_GROUP)

    # ---- per-game shares (player stat / team stat in that game) ----
    team_tot = base[~base.is_future].groupby(["game_id", "team"])[SHARE_STATS].sum()
    team_tot = team_tot.add_prefix("tm_")
    base = base.join(team_tot, on=["game_id", "team"])
    for c in SHARE_STATS:
        den = base[f"tm_{c}"]
        base[f"sh_{c}"] = np.where(den > 0, base[c] / den.replace(0, np.nan), np.nan)
    base = base.drop(columns=[f"tm_{c}" for c in SHARE_STATS])

    # ---- rolling player features ----
    base = base.sort_values(["season", "week", "game_id"]).reset_index(drop=True)
    roll_cols = PLAYER_STATS + [f"sh_{c}" for c in SHARE_STATS] + ["offense_pct"]
    s = _shift_ewm(base, "player_id", roll_cols, HL_SHORT, "_e3")
    l = _shift_ewm(base, "player_id", ["td", "xtd", "sh_xtd", "sh_td", "rush_xtd", "rec_xtd",
                                       "sh_rush_xtd", "sh_rec_xtd"], HL_LONG, "_e10")
    lag = base.groupby("player_id", sort=False)[["offense_pct", "sh_xtd", "sh_carries", "sh_targets"]] \
        .shift(1).add_suffix("_lag1")
    base = pd.concat([base, s, l, lag], axis=1)
    base["n_prev"] = base.groupby("player_id").cumcount()
    base["n_prev_season"] = base.groupby(["player_id", "season"]).cumcount()
    # career TD rate per expected TD (finishing skill), heavily shrunk
    cum_td = base.groupby("player_id").td.transform(lambda x: x.shift(1).fillna(0).cumsum())
    cum_xtd = base.groupby("player_id").xtd.transform(lambda x: x.shift(1).fillna(0).cumsum())
    base["finish_ratio"] = (cum_td + 3.0) / (cum_xtd + 3.0)
    base["career_xtd_pg"] = cum_xtd / base.n_prev.replace(0, np.nan)
    base["age"] = (pd.to_datetime(base.season.astype(str) + "-10-01")
                   - pd.to_datetime(base.birth_date, errors="coerce")).dt.days / 365.25
    base["years_exp"] = base.season - pd.to_numeric(base.rookie_year, errors="coerce")
    base["draft_number"] = pd.to_numeric(base.draft_number, errors="coerce").fillna(300)
    return base, rushes, targets


def priors_for_new_players(df: pd.DataFrame) -> pd.Series:
    """Average realized share of players in their first-ever observed game, by position group."""
    first = df[(df.n_prev == 0) & ~df.is_future]
    return first.groupby("pos_group")[["sh_xtd", "sh_td", "sh_rush_xtd", "sh_rec_xtd", "offense_pct"]] \
        .mean().fillna(0.0)


def _renorm(df, col, keep=0.85):
    """Renormalize a share among active teammates; `keep` of any vacated share is redistributed."""
    tot = df.groupby(["game_id", "team"])[col].transform("sum")
    over = df[col] / tot.clip(lower=1.0)
    under = df[col] * (1.0 + keep * (1.0 - tot) / tot.clip(lower=1e-6))
    return np.where(tot >= 1.0, over, under), tot


def finalize(base: pd.DataFrame, tgf: pd.DataFrame, priors: pd.DataFrame) -> pd.DataFrame:
    df = base.merge(
        tgf.drop(columns=["season", "week", "team_td", "team_rush_td", "team_pass_td", "team_xtd",
                          "team_rush_xtd", "team_rec_xtd", "plays", "drives", "pts", "played"]),
        on=["game_id", "team"], how="inner")

    # fill brand-new players with position priors
    for c, pc in [("sh_xtd_e3", "sh_xtd"), ("sh_xtd_e10", "sh_xtd"), ("sh_td_e3", "sh_td"),
                  ("sh_td_e10", "sh_td"), ("offense_pct_e3", "offense_pct"),
                  ("sh_rush_xtd_e3", "sh_rush_xtd"), ("sh_rush_xtd_e10", "sh_rush_xtd"),
                  ("sh_rec_xtd_e3", "sh_rec_xtd"), ("sh_rec_xtd_e10", "sh_rec_xtd")]:
        df[c] = df[c].fillna(df.pos_group.map(priors[pc]))

    # Opportunity-share blends. Expected-TD share stabilizes far faster than realized TD share.
    df["rush_share_raw"] = (0.6 * df.sh_rush_xtd_e3 + 0.4 * df.sh_rush_xtd_e10).clip(lower=0.0005)
    df["rec_share_raw"] = (0.6 * df.sh_rec_xtd_e3 + 0.4 * df.sh_rec_xtd_e10).clip(lower=0.0005)
    df["share_raw"] = (0.45 * df.sh_xtd_e3 + 0.30 * df.sh_xtd_e10 + 0.10 * df.sh_td_e3
                       + 0.15 * df.sh_td_e10.fillna(df.sh_xtd_e10)).clip(lower=0.002)
    # Renormalize among players actually active this game -> vacated opportunity (injuries,
    # inactives, trades) flows to teammates who are playing.
    df["rush_share"], df["rush_share_sum"] = _renorm(df, "rush_share_raw")
    df["rec_share"], df["rec_share_sum"] = _renorm(df, "rec_share_raw")
    df["share_norm"], df["share_active_sum"] = _renorm(df, "share_raw")
    df["vacated"] = (1.0 - df.share_active_sum).clip(lower=0)
    grp = df.groupby(["game_id", "team"])
    df["rank_in_team"] = grp.share_raw.rank(ascending=False)
    df["pos_group_share_sum"] = df.groupby(["game_id", "team", "pos_group"]).share_raw.transform("sum")
    df["rank_in_pos"] = df.groupby(["game_id", "team", "pos_group"]).share_raw.rank(ascending=False)
    # Shrunk finishing skill: sqrt dampens; clipped to avoid chasing TD luck
    df["finish_adj"] = np.sqrt(df.finish_ratio).clip(0.8, 1.25)

    df["pos_code"] = df.pos_group.map({"QB": 0, "RB": 1, "WR": 2, "TE": 3})
    df["label"] = (df.td >= 1).astype(float)
    df.loc[df.is_future, "label"] = np.nan
    return df
