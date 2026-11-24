"""Player-prop milestone model (bet365 ladders).

One model per market learns the full outcome distribution with a "stacked threshold" design: every
player-game is repeated once per rung k with label 1{X >= k}, and the rung enters as a feature under a
monotone-decreasing constraint.  That yields P(X >= k) for every rung, coherent across rungs (never
increasing in k), with whatever skew / zero-inflation the data shows (no normal assumption).

Labels are official box-score lines (nflverse stats_player_week = what books settle on).
Every row is a player who took at least one offensive snap, so early exits count as misses in training.
"""
from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd

from .features import _shift_ewm

PROP_STATS = ["carries", "rush_yds", "rec", "tgt", "rec_yds", "pass_att", "pass_cmp", "pass_yds", "pass_td"]

# market -> eligible positions, training grid, bet365 ladder
MARKETS = {
    "carries":  dict(pos=["RB", "QB"], grid=list(range(4, 31, 2)) + [15, 25], ladder=[10, 15, 20, 25],
                     label="carries"),
    "rush_yds": dict(pos=["RB", "QB"], grid=list(range(10, 201, 10)), ladder=list(range(20, 151, 10)),
                     label="rush yds"),
    "rec":      dict(pos=["WR", "TE", "RB"], grid=list(range(1, 13)), ladder=list(range(1, 11)),
                     label="receptions"),
    "rec_yds":  dict(pos=["WR", "TE", "RB"], grid=list(range(10, 201, 10)), ladder=list(range(20, 151, 10)),
                     label="rec yds"),
    "pass_att": dict(pos=["QB"], grid=list(range(15, 51, 5)), ladder=list(range(20, 46, 5)),
                     label="pass att"),
    "pass_yds": dict(pos=["QB"], grid=list(range(100, 426, 25)), ladder=list(range(150, 351, 25)),
                     label="pass yds"),
    "pass_td":  dict(pos=["QB"], grid=[1, 2, 3, 4], ladder=[1, 2, 3], label="pass TDs"),
}
YARDAGE = {"rush_yds", "rec_yds", "pass_yds"}

PARAMS = dict(objective="binary", n_estimators=400, learning_rate=0.05, num_leaves=31, min_child_samples=300,
              subsample=0.7, subsample_freq=1, colsample_bytree=0.7, reg_lambda=5.0, verbose=-1)


# --------------------------------------------------------------------------------------------
def qb_starters(pbp: pd.DataFrame) -> pd.DataFrame:
    """The QB who took the team's first dropback = pre-game knowable starter (keeps early exits in)."""
    p = pbp[pbp.passer_player_id.notna() & (pbp.two_point_attempt != 1)].sort_values(["game_id", "play_id"])
    return p.drop_duplicates(["game_id", "posteam"])[["game_id", "posteam", "passer_player_id"]] \
        .rename(columns={"posteam": "team", "passer_player_id": "player_id"}).assign(is_starter=1)


def add_prop_features(df: pd.DataFrame, official: pd.DataFrame, pbp: pd.DataFrame) -> pd.DataFrame:
    df = df.drop(columns=[c for c in PROP_STATS if c in df.columns]).merge(
        official[["game_id", "player_id"] + PROP_STATS], on=["game_id", "player_id"], how="left")
    played = ~df.is_future
    for c in PROP_STATS:  # played a snap but no box-score row = zeros
        df.loc[played, c] = df.loc[played, c].fillna(0)
    df = df.sort_values(["season", "week", "game_id"]).reset_index(drop=True)

    e3 = _shift_ewm(df, "player_id", PROP_STATS, 3.0, "_p3")
    e10 = _shift_ewm(df, "player_id", PROP_STATS, 10.0, "_p10")
    sh = df.groupby("player_id", sort=False)[PROP_STATS].shift(1).astype(float)
    sh["player_id"] = df.player_id.values
    sd = sh.groupby("player_id", sort=False)[PROP_STATS].ewm(halflife=8.0, ignore_na=True).std() \
        .reset_index(level=0, drop=True).sort_index().reindex(df.index).add_suffix("_psd")
    lag = df.groupby("player_id", sort=False)[PROP_STATS].shift(1).add_suffix("_lag1")
    # season-to-date average (the ledger's empirical-Bayes "current season" input)
    filled = df[PROP_STATS].fillna(0).assign(player_id=df.player_id, season=df.season)
    cs = filled.groupby(["player_id", "season"], sort=False)[PROP_STATS].cumsum()
    std_ = pd.DataFrame({f"{c}_std": (cs[c] - filled[c]) / df.n_prev_season.replace(0, np.nan)
                         for c in PROP_STATS}, index=df.index)
    df = pd.concat([df, e3, e10, sd, lag, std_], axis=1)

    # team volume (rolling) and opponent allowed by position group
    tm = df[~df.is_future].groupby(["game_id", "team"])[["carries", "pass_att", "tgt", "rush_yds", "pass_yds"]] \
        .sum().add_prefix("tm_").reset_index()
    sk = df[["game_id", "season", "week", "team", "opp"]].drop_duplicates(["game_id", "team"])
    tmv = sk.merge(tm, on=["game_id", "team"], how="left").sort_values(["season", "week"]).reset_index(drop=True)
    tcols = [c for c in tmv.columns if c.startswith("tm_")]
    tmv = pd.concat([tmv[["game_id", "team"]], _shift_ewm(tmv, "team", tcols, 5.0, "_ewm")], axis=1)
    df = df.merge(tmv, on=["game_id", "team"], how="left")

    al = df[~df.is_future].groupby(["game_id", "opp", "pos_group"])[["carries", "rush_yds", "rec", "rec_yds",
                                                                     "tgt", "pass_att", "pass_yds"]].sum()
    al = al.unstack("pos_group")
    al.columns = [f"alw_{s}_{p}" for s, p in al.columns]
    al = al.reset_index().rename(columns={"opp": "def_team"})
    skd = sk.rename(columns={"team": "def_team"})[["game_id", "season", "week", "def_team"]]
    alv = skd.merge(al, on=["game_id", "def_team"], how="left").sort_values(["season", "week"]) \
        .reset_index(drop=True)
    acols = [c for c in alv.columns if c.startswith("alw_")]
    alv = pd.concat([alv[["game_id", "def_team"]], _shift_ewm(alv, "def_team", acols, 6.0, "_ewm")], axis=1)
    df = df.merge(alv.rename(columns={"def_team": "opp"}), on=["game_id", "opp"], how="left")
    # this player's position-specific allowed numbers
    for s in ["carries", "rush_yds", "rec", "rec_yds", "tgt", "pass_att", "pass_yds"]:
        cols = {p: f"alw_{s}_{p}_ewm" for p in ["QB", "RB", "WR", "TE"]}
        df[f"opp_alw_{s}"] = np.select([df.pos_group == p for p in cols],
                                       [df[c] if c in df else np.nan for c in cols.values()], np.nan)

    # Fix 4 (Week 9): floor-game and script-conditional volume, season-to-date (shifted)
    scores = pbp.groupby("game_id").agg(home_team=("home_team", "first"), away_team=("away_team", "first"),
                                        hs=("home_score", "max"), as_=("away_score", "max")).reset_index()
    res = pd.concat([scores.assign(team=scores.home_team, won=(scores.hs > scores.as_).astype(int)),
                     scores.assign(team=scores.away_team, won=(scores.as_ > scores.hs).astype(int))])[["game_id", "team", "won"]]
    df = df.merge(res, on=["game_id", "team"], how="left")
    g = df.groupby(["player_id", "season"], sort=False)
    for c in PROP_STATS:
        df[f"{c}_min"] = g[c].transform(lambda x: x.shift(1).expanding(min_periods=1).min())
        lossv = df[c].where(df.won == 0)
        df[f"{c}_loss"] = lossv.groupby([df.player_id, df.season], sort=False).transform(
            lambda x: x.shift(1).expanding(min_periods=1).mean())
    # carries / targets when the team trailed by 10+ (share of team), rolling
    tr = pbp[pbp.play_type.isin(["run", "pass"]) & (pbp.score_differential <= -10)]
    tc = tr[tr.rusher_player_id.notna()].groupby(["game_id", "rusher_player_id"]).size().rename("trail_car").reset_index() \
        .rename(columns={"rusher_player_id": "player_id"})
    tt = tr[tr.receiver_player_id.notna()].groupby(["game_id", "receiver_player_id"]).size().rename("trail_tgt").reset_index() \
        .rename(columns={"receiver_player_id": "player_id"})
    df = df.merge(tc, on=["game_id", "player_id"], how="left").merge(tt, on=["game_id", "player_id"], how="left")
    df[["trail_car", "trail_tgt"]] = df[["trail_car", "trail_tgt"]].fillna(0)
    tr_team = tr.groupby(["game_id", "posteam"]).size().rename("trail_plays").reset_index().rename(columns={"posteam": "team"})
    df = df.merge(tr_team, on=["game_id", "team"], how="left"); df["trail_plays"] = df.trail_plays.fillna(0)
    df = df.sort_values(["season", "week", "game_id"]).reset_index(drop=True)
    tp = _shift_ewm(df, "player_id", ["trail_car", "trail_tgt", "trail_plays"], 6.0, "_e")
    df = pd.concat([df, tp], axis=1)
    df["trail_car_rate"] = df.trail_car_e / df.trail_plays_e.replace(0, np.nan)
    df["trail_tgt_rate"] = df.trail_tgt_e / df.trail_plays_e.replace(0, np.nan)
    st = qb_starters(pbp)
    df = df.merge(st, on=["game_id", "team", "player_id"], how="left")
    df["is_starter"] = df.is_starter.fillna(0)
    return df


PROP_FEATS = (
    [f"{c}_{s}" for c in PROP_STATS for s in ("p3", "p10", "psd", "lag1", "std")]   # _min/_loss/trail_* are gate columns only (backtest: no gain)
    + ["tm_carries_ewm", "tm_pass_att_ewm", "tm_tgt_ewm", "tm_rush_yds_ewm", "tm_pass_yds_ewm"]
    + [f"opp_alw_{s}" for s in ["carries", "rush_yds", "rec", "rec_yds", "tgt", "pass_att", "pass_yds"]]
    + ["pos_code", "offense_pct_e3", "offense_pct_lag1", "n_prev", "n_prev_season", "age", "years_exp",
       "draft_number", "implied_filled", "spread", "total_line", "is_home", "plays_ewm",
       "rush_share", "rec_share", "sh_carries_e3", "sh_targets_e3", "sh_air_yds_e3", "sh_deep_tgt_e3",
       "sh_short_tgt_e3", "yac_e3", "air_yds_e3", "rank_in_pos", "vacated", "team_xtd_ewm"]
)


def prop_feature_list(df, extra_groups):
    from .model import FEATURE_GROUPS
    f = [c for c in PROP_FEATS if c in df.columns]
    for g in extra_groups:
        f += [c for c in FEATURE_GROUPS[g] if c in df.columns]
    return list(dict.fromkeys(f))


def _stack(d: pd.DataFrame, market: str, grid) -> pd.DataFrame:
    k = np.asarray(grid, float)
    out = d.loc[d.index.repeat(len(k))].copy()
    out["k"] = np.tile(k, len(d))
    base = out[f"{market}_p10"].fillna(out[f"{market}_p3"]).fillna(0)
    out["k_rel"] = out.k / (base + 1.0)
    out["k_minus"] = out.k - out[f"{market}_p3"].fillna(base)
    out["k_z"] = out.k_minus / (out[f"{market}_psd"].fillna(base * 0.5) + 1.0)
    if market in d.columns:
        out["y"] = (out[market] >= out.k).astype(float)
    return out


def eligible(df: pd.DataFrame, market: str) -> pd.Series:
    m = df.pos_group.isin(MARKETS[market]["pos"])
    if market.startswith("pass"):
        m &= df.is_starter == 1
    elif market in ("carries", "rush_yds"):
        m &= (df.pos_group == "RB") | ((df.pos_group == "QB") & (df.is_starter == 1))
    return m


def _logit(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


class PropModel:
    """Stacked-threshold GBM + out-of-fold Platt calibration (a + b*logit p), per market."""

    def __init__(self, market, feats, params=None, calibrate=True, n_oof=3):
        self.market, self.feats, self.params = market, feats, params or PARAMS
        self.calibrate, self.n_oof, self.cal = calibrate, n_oof, None

    def fit(self, train: pd.DataFrame):
        if self.calibrate:
            from sklearn.linear_model import LogisticRegression
            seasons = sorted(train.season.unique())[-self.n_oof:]
            P, Y = [], []
            for s in seasons:
                inner = PropModel(self.market, self.feats, self.params, calibrate=False)._fit(train[train.season != s])
                d = train[(train.season == s) & eligible(train, self.market) & train[self.market].notna()]
                C = inner.curve(d)
                P.append(C.p.values); Y.append((C[self.market] >= C.k).values.astype(float))
            P, Y = np.concatenate(P), np.concatenate(Y)
            self.cal = LogisticRegression(C=100.0).fit(_logit(P)[:, None], Y)
        return self._fit(train)

    def _fit(self, train: pd.DataFrame):
        spec = MARKETS[self.market]
        d = train[eligible(train, self.market) & train[self.market].notna()]
        S = _stack(d, self.market, spec["grid"])
        cols = self.feats + ["k", "k_rel", "k_minus", "k_z"]
        mono = [0] * len(self.feats) + [-1, -1, -1, -1]
        self.m = lgb.LGBMClassifier(**self.params, monotone_constraints=mono,
                                    monotone_constraints_method="advanced")
        self.m.fit(S[cols], S.y)
        self.cols = cols
        return self

    def curve(self, d: pd.DataFrame, ladder=None) -> pd.DataFrame:
        """Return long frame: one row per (player-game, rung) with p = P(X >= rung)."""
        ladder = ladder or MARKETS[self.market]["ladder"]
        S = _stack(d, self.market, ladder)
        S["p_raw"] = self.m.predict_proba(S[self.cols])[:, 1]
        S["p"] = S.p_raw if self.cal is None else self.cal.predict_proba(_logit(S.p_raw.values)[:, None])[:, 1]
        # enforce monotone in k within each player-game (guard against residual noise)
        S["p"] = S.groupby(level=0).p.cummin()
        S["market"] = self.market
        return S

    def mean(self, d):
        """E[X] ~ sum_k P(X >= k) * dk over the training grid (for residual correlation)."""
        g = MARKETS[self.market]["grid"]
        g = sorted(set(g))
        S = self.curve(d, g)
        steps = np.diff([0] + g)
        S["w"] = np.tile(steps, len(d))
        return (S.p * S.w).groupby(level=0).sum()
