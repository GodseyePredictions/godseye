"""Team rates by strength state, as of a date.

For every team and strength (ev5, evo, pp, pk, and all): per-60 rates for goals, expected goals, shot
attempts, shots on goal, high-danger shots, hits and blocks, for and against. Each rate is the spec's
blend, 60% season and 40% last 10 games. Early in a season the "season" part is topped up with last
season's rate until the team has played `season_carry_games`. Penalties drawn and taken per 60 and
power-play time per game sit on the "all" row. `*_idx` is the blended rate over the league's.
"""
import pandas as pd

from nhl.store import STRENGTHS

COUNTS = ["gf", "ga", "xgf", "xga", "cf", "ca", "ff", "fa", "sog_f", "sog_a", "hdf", "hda", "hits_f", "hits_a", "blk_f", "blk_a",
          "pen_taken", "pen_drawn"]


def _with_all(tgs: pd.DataFrame) -> pd.DataFrame:
    keys = ["game_id", "team", "season", "date_et", "known_at", "is_home"]
    total = tgs.groupby(keys, as_index=False)[["toi"] + COUNTS].sum().assign(strength="all")
    return pd.concat([tgs[keys + ["strength", "toi"] + COUNTS], total], ignore_index=True)


def build(tgs: pd.DataFrame, season: int, cfg) -> pd.DataFrame:
    """tgs: team_game_strength rows known before the date being priced. season: the season being priced."""
    c = cfg["rates"]
    d = _with_all(tgs)
    cur, prev = d[d.season == season], d[d.season == season - 1]
    order = cur.drop_duplicates(["team", "game_id"]).sort_values("known_at")
    recent_ids = order.groupby("team").tail(c["recent_games"])[["team", "game_id"]]
    rec = cur.merge(recent_ids, on=["team", "game_id"])
    key = ["team", "strength"]
    S = cur.groupby(key)[["toi"] + COUNTS].sum()
    R = rec.groupby(key)[["toi"] + COUNTS].sum().reindex(S.index).fillna(0)
    Pv = prev.groupby(key)[["toi"] + COUNTS].sum().reindex(S.index)
    gp = cur.groupby("team").game_id.nunique()
    out = pd.DataFrame(index=S.index)
    out["gp"] = gp.reindex(S.index.get_level_values("team")).to_numpy()
    out["gp_recent"] = rec.groupby("team").game_id.nunique().reindex(S.index.get_level_values("team")).fillna(0).to_numpy()
    out["toi_pg"] = S.toi / out.gp
    lg_cur = cur.groupby("strength")[["toi"] + COUNTS].sum()
    carry_games = (c["season_carry_games"] - out.gp).clip(lower=0)
    carry_toi = carry_games * out.toi_pg                                # seconds of last season mixed in
    for col in COUNTS:
        lg_rate = (lg_cur[col] / lg_cur.toi * 3600).reindex(S.index.get_level_values("strength")).to_numpy()
        prior = (Pv[col] / Pv.toi * 3600).fillna(pd.Series(lg_rate, index=S.index))   # a team with no last season: the league
        season_rate = (S[col] + prior * carry_toi / 3600) / (S.toi + carry_toi) * 3600
        recent_rate = (R[col] / R.toi * 3600).where(R.toi > 0, season_rate)
        out[f"{col}60_season"] = season_rate
        out[f"{col}60_recent"] = recent_rate
        out[f"{col}60"] = c["team_weight_season"] * season_rate + c["team_weight_recent"] * recent_rate
        out[f"{col}60_idx"] = out[f"{col}60"] / lg_rate
    out["xgf_pct"] = out.xgf60 / (out.xgf60 + out.xga60)
    return out.reset_index().assign(season=season)


def strengths() -> tuple:
    return STRENGTHS + ("all",)
