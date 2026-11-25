"""League constants the sim needs, measured from the store as of a date: nothing here is typed in.

Period shares of scoring, how shot, goal, hit and block rates move with the score, empty-net scoring,
how often a tied game is settled in overtime, assists per goal, and home ice.
"""
import numpy as np
import pandas as pd


def fit(games: pd.DataFrame, team_game: pd.DataFrame, score: pd.DataFrame, tgs: pd.DataFrame, pgs_totals: dict | None = None,
        season: int | None = None, goal_prior_xg: float = 600.0) -> dict:
    """All inputs are rows known before the date being priced. `score` is team_game_score."""
    k = {}
    en = team_game.en_gf.sum()
    p = np.array([games.h1.sum() + games.a1.sum(), games.h2.sum() + games.a2.sum(), games.h3.sum() + games.a3.sum() - en], float)
    k["period_share"] = (p / p.sum()).tolist()
    ev = score[score.scope == "ev5"].groupby("lead")[["toi", "sog_f", "hits_f", "blk_f", "xgf", "cf"]].sum()
    al = score[score.scope == "all"].groupby("lead")[["toi", "sog_f", "hits_f", "blk_f", "xgf", "cf"]].sum()
    rate = lambda d, c: (d[c] / d.toi) / (d.at[0, c] / d.at[0, "toi"])
    k["se_goals"] = rate(ev, "xgf").reindex(range(-2, 3)).tolist()       # index 0 = down two or more ... 4 = up two or more
    k["se_sog"] = rate(ev, "sog_f").reindex(range(-2, 3)).tolist()
    k["se_hits"] = rate(al, "hits_f").reindex(range(-2, 3)).tolist()
    k["se_blk"] = rate(al, "blk_f").reindex(range(-2, 3)).tolist()
    w = al.toi / al.toi.sum()
    for name in ("se_goals", "se_sog", "se_hits", "se_blk"):             # centre on 1.00 over a typical game
        v = np.array(k[name]); src = ev if name in ("se_goals", "se_sog") else al
        k[name] = (v / float((v * (src.toi / src.toi.sum()).to_numpy()).sum())).tolist()
    k["en_g60"] = float(en / max(team_game.en_sec.sum(), 1) * 3600)
    tied = games[games.decided != "REG"]
    k["ot_decided"] = float((tied.decided == "OT").mean()) if len(tied) else 0.68
    k["tie_rate"] = float(len(tied) / len(games))
    reg_h = games.h1 + games.h2 + games.h3
    reg_a = games.a1 + games.a2 + games.a3
    k["home_ice"] = float(np.sqrt(reg_h.sum() / reg_a.sum()))
    t = tgs.groupby("strength")[["toi", "gf", "xgf", "sog_f"]].sum()
    n_tg = tgs[["game_id", "team"]].drop_duplicates().shape[0]
    k["pp_sec_pg"] = float(t.at["pp", "toi"] / n_tg)
    k["goals_per_xg"] = {s: float(t.at[s, "gf"] / t.at[s, "xgf"]) for s in ("ev5", "pp", "pk")}
    k["sog60"] = {s: float(t.at[s, "sog_f"] / t.at[s, "toi"] * 3600) for s in ("ev5", "pp", "pk")}
    k["xg60"] = {s: float(t.at[s, "xgf"] / t.at[s, "toi"] * 3600) for s in ("ev5", "pp", "pk")}
    sh = team_game.groupby("is_home").sog.sum()
    k["home_sog"] = float(np.sqrt(sh.get(1, 1) / max(sh.get(0, 1), 1)))
    cur = tgs[tgs.season == season] if season is not None else tgs.iloc[:0]
    k["season_goal_factor"] = float((cur.gf.sum() + goal_prior_xg) / (cur.xgf.sum() + goal_prior_xg)) if len(cur) else 1.0
    if pgs_totals:
        k["a1_per_goal"] = pgs_totals["a1"] / pgs_totals["g"]
        k["a2_given_a1"] = pgs_totals["a2"] / pgs_totals["a1"]
    else:
        k["a1_per_goal"], k["a2_given_a1"] = 0.935, 0.803
    return k
