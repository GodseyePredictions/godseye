"""Three-layer ATTD model.

Layer 1  Team TD rates.  Poisson GLMs for a team's offensive RUSHING TDs and PASSING TDs, anchored on the
         Vegas implied team total and adjusted by rolling offensive/defensive xTD form.
Layer 2  Structural player model.  lambda_player = lambda_team_rush * rush_share + lambda_team_pass * rec_share,
         shares renormalized across active teammates, times a shrunk finishing factor.
         P(ATTD) = 1 - exp(-lambda).
Layer 3  Gradient boosting (LightGBM) on ~60 features *including* the structural lambda.  (A held-out
         isotonic step was tested and hurt out-of-sample log loss, so it is optional.)
"""
from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import PoissonRegressor
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

TEAM_FEATS = ["implied_filled", "spread", "total_line", "is_home",
              "team_xtd_ewm", "team_td_ewm", "team_xtd_allowed_ewm", "team_td_allowed_ewm"]
TEAM_RUSH_FEATS = TEAM_FEATS + ["team_rush_xtd_ewm", "team_rush_td_ewm", "team_rush_xtd_allowed_ewm",
                                "team_rush_td_allowed_ewm"]
TEAM_PASS_FEATS = TEAM_FEATS + ["team_rec_xtd_ewm", "team_pass_td_ewm", "team_rec_xtd_allowed_ewm",
                                "team_pass_td_allowed_ewm"]

BASE_FEATS = [
    "pos_code", "lam_struct", "p_struct", "lam_team_rush", "lam_team_pass",
    "rush_share", "rec_share", "share_norm", "share_raw", "vacated", "rank_in_team", "rank_in_pos",
    "pos_group_share_sum", "finish_adj", "finish_ratio", "career_xtd_pg",
    "offense_pct_e3", "offense_pct_lag1", "sh_xtd_lag1", "sh_carries_lag1", "sh_targets_lag1",
    "carries_e3", "rush_rz_e3", "rush_i10_e3", "rush_i5_e3", "targets_e3", "tgt_rz_e3", "tgt_i10_e3",
    "ez_tgt_e3", "rush_xtd_e3", "rec_xtd_e3", "xtd_e3", "td_e3", "yds_e3", "xtd_e10", "td_e10",
    "sh_carries_e3", "sh_rush_rz_e3", "sh_rush_i10_e3", "sh_rush_i5_e3", "sh_targets_e3",
    "sh_tgt_rz_e3", "sh_tgt_i10_e3", "sh_ez_tgt_e3",
    "n_prev", "n_prev_season", "age", "years_exp", "draft_number",
    "implied_filled", "spread", "total_line", "is_home",
    "team_xtd_ewm", "team_xtd_allowed_ewm", "team_rush_xtd_allowed_ewm", "team_rec_xtd_allowed_ewm",
    "week",
]

FEATURE_GROUPS = {
    "stadium_weather": ["is_indoor", "is_turf", "wx_code", "temp", "wind", "wx_bad", "cold", "windy"],
    "game_time": ["slot_code", "kick_et_hour", "is_intl", "div_game"],
    "travel_rest": ["travel_miles", "tz_shift", "body_clock_hour", "early_body_clock", "rest_days",
                    "short_week", "post_bye"],
    "player_splits": [f"split_{c}" for c in ["home_away", "is_indoor", "is_turf", "slot", "wx_bad", "cold",
                                             "home_x_slot", "home_x_roof", "home_x_surface", "home_x_wx"]],
    "def_injuries": ["def_out_DL", "def_out_LB", "def_out_DB", "def_out_total", "def_starters_out"],
    "own_ol_injuries": ["own_ol_out"],
    "def_scheme_dc": [f"{c}_dc" for c in ["blitz_rate", "rushers", "box_run", "light_box", "heavy_box",
                                          "proe_faced", "deep_rate_allowed", "deep_td_allowed", "yac_allowed",
                                          "adot_allowed", "td_allowed_WR", "td_allowed_TE", "td_allowed_RB",
                                          "td_allowed_QB", "rz_td_rate_allowed"]] + ["mx_pos_td_allowed", "mx_deep"],
    "off_playcalling_oc": [f"{c}_oc" for c in ["proe", "rz_pass", "gl_pass", "rz_proe", "deep_rate",
                                               "short_rate", "middle_rate", "adot", "yac_pc", "shotgun",
                                               "no_huddle", "pa_rate", "screen_rate", "rpo_rate", "motion_rate",
                                               "qb_design_run", "qb_rz_run", "tgt_WR", "tgt_TE", "tgt_RB",
                                               "rztgt_WR", "rztgt_TE", "rztgt_RB", "rz_td_rate"]]
                          + ["mx_pos_tgt_pref"],
    "unit_matchups": [f"{c}_oc" for c in ["ol_rb_ypc", "ol_stuff_rate", "ol_sack_rate", "ol_pressure_rate",
                                          "explosive_rate"]]
                     + [f"{c}_dc" for c in ["dl_rb_ypc_allowed", "dl_stuff_forced", "dl_sack_rate", "dl_pressure_rate",
                                            "explosive_allowed", "ypt_allowed_WR", "ypt_allowed_TE", "ypt_allowed_RB",
                                            "cr_allowed_WR", "cr_allowed_TE", "cr_allowed_RB"]]
                     + ["mx_ypt_allowed", "mx_cr_allowed", "mx_tgt_x_ypt", "mx_run_lane", "mx_stuff", "mx_rush_x_lane",
                        "mx_pass_pro"],
    "defender_personnel": [f"def_{u}_{m}" for u in ("CB", "S", "LB", "DL") for m in ("cov", "front", "avail")]
                          + ["def_secondary_cov", "def_front_splash", "mx_cov_index"],
    "tempo_penalty": ["off_pen_rate_tp", "off_pen_yds_tp", "def_pen_rate_tpd", "def_pen_yds_tpd", "pen_edge",
                      "third_conv_tp", "third_conv_allowed_tpd", "punt_after3_pd_tp", "fg_after3_pd_tp", "stall3_rate_tp",
                      "stall3_forced_tpd", "stall_edge", "punt_rate_tp", "fg_rate_tp", "plays_tp", "plays_allowed_tpd",
                      "drives_tp", "top_sec_tp", "top_allowed_tpd", "sec_per_play_tp", "opp_sec_per_play_tp",
                      "exp_plays", "exp_top_sec", "exp_snaps", "exp_time_on_field"],
    "team_scenario": ["team_td_sd", "team_zero_rate", "abs_spread", "dog_by_7", "trail_pass_oc", "lead_run_oc"],
    "rz_recency": ["rz_pass_oc3", "gl_pass_oc3", "rz_td_rate_oc3", "rztgt_WR_oc3", "rztgt_TE_oc3", "rztgt_RB_oc3",
                   "rz_pass_trend", "rz_tgt_rank", "rz_tgt_top2_share"],
    "role_freshness": ["carry_share_jump", "target_share_jump", "snap_trend", "fresh_role"],
    "player_route_profile": ["sh_deep_tgt_e3", "sh_short_tgt_e3", "sh_air_yds_e3", "deep_tgt_e3",
                             "short_tgt_e3", "air_yds_e3", "yac_e3"],
}
# Production default = ALL factor groups (user standing rule, see FACTORS.md).  Walk-forward tests show no single
# group clears noise and switching all on costs ~0.0002 log loss, so nothing is lost by always considering them.
DEFAULT_GROUPS = list(FEATURE_GROUPS)   # standing rule (FACTORS.md): every factor group is always considered
GBM_FEATS = BASE_FEATS + [f for g in FEATURE_GROUPS.values() for f in g]          # everything (ablation)


def feats_for(groups):
    if groups in (None, "default"):
        groups = DEFAULT_GROUPS
    elif groups == "all":
        groups = list(FEATURE_GROUPS)
    elif groups == "none":
        groups = []
    return BASE_FEATS + [f for g in groups for f in FEATURE_GROUPS[g]]

GBM_PARAMS = dict(objective="binary", n_estimators=1200, learning_rate=0.01, num_leaves=15,
                  min_child_samples=300, subsample=0.8, subsample_freq=1, colsample_bytree=0.7,
                  reg_lambda=5.0, verbose=-1)


class TeamModel:
    def fit(self, tg: pd.DataFrame):
        d = tg[tg.played & tg.team_xtd_ewm.notna() & tg.team_xtd_allowed_ewm.notna()]
        self.rush = PoissonRegressor(alpha=1e-3, max_iter=500).fit(d[TEAM_RUSH_FEATS], d.team_rush_td)
        self.pas = PoissonRegressor(alpha=1e-3, max_iter=500).fit(d[TEAM_PASS_FEATS], d.team_pass_td)
        # Over-dispersion & same-game correlation of team TD counts (used by the parlay simulator)
        mu = self.rush.predict(d[TEAM_RUSH_FEATS]) + self.pas.predict(d[TEAM_PASS_FEATS])
        y = d.team_td.values
        self.team_disp = float(max(0.0, (np.mean((y - mu) ** 2) - np.mean(mu)) / np.mean(mu ** 2)))
        r = pd.DataFrame({"game_id": d.game_id.values, "res": (y - mu) / np.sqrt(mu)})
        r["k"] = r.groupby("game_id").cumcount()
        w = r.pivot(index="game_id", columns="k", values="res").dropna()
        self.game_corr = float(np.corrcoef(w[0], w[1])[0, 1]) if len(w) > 50 else 0.0
        return self

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        X = df[TEAM_RUSH_FEATS].copy()
        fill = {c: X[c].median() for c in X.columns}
        df = df.copy()
        df["lam_team_rush"] = self.rush.predict(df[TEAM_RUSH_FEATS].fillna(fill))
        fill = {c: df[c].median() for c in TEAM_PASS_FEATS}
        df["lam_team_pass"] = self.pas.predict(df[TEAM_PASS_FEATS].fillna(fill))
        return df


def add_structural(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["lam_struct"] = (df.lam_team_rush * df.rush_share + df.lam_team_pass * df.rec_share) * df.finish_adj
    df["p_struct"] = 1.0 - np.exp(-df.lam_struct)
    return df


class ATTDModel:
    def __init__(self, params=None, feats=None):
        self.params = params or GBM_PARAMS
        self.feats = feats or feats_for("default")

    def fit(self, train: pd.DataFrame, calib: pd.DataFrame | None = None):
        train = train[train.label.notna()]
        self.gbm = lgb.LGBMClassifier(**self.params)
        self.gbm.fit(train[self.feats], train.label)
        self.iso = None
        if calib is not None and len(calib):
            raw = self.gbm.predict_proba(calib[self.feats])[:, 1]
            self.iso = IsotonicRegression(out_of_bounds="clip", y_min=1e-4, y_max=0.95).fit(raw, calib.label)
        return self

    def predict(self, df):
        raw = self.gbm.predict_proba(df[self.feats])[:, 1]
        if self.iso is None:
            return raw
        # light blend with raw keeps the isotonic step function from being too blocky
        return 0.7 * self.iso.predict(raw) + 0.3 * raw


# --------------------------------------------------------------------------------------------
def metrics(y, p, label):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return {"model": label, "n": len(y), "log_loss": log_loss(y, p), "brier": brier_score_loss(y, p),
            "auc": roc_auc_score(y, p), "mean_pred": float(np.mean(p)), "actual_rate": float(np.mean(y))}


def calibration_table(y, p, bins=(0, .05, .10, .15, .20, .25, .30, .35, .40, .50, .60, 1.0)):
    d = pd.DataFrame({"y": y, "p": p})
    d["bin"] = pd.cut(d.p, bins)
    return d.groupby("bin", observed=True).agg(n=("y", "size"), pred=("p", "mean"), actual=("y", "mean"))
