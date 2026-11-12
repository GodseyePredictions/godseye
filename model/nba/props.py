"""Player stat models: a per-minute rate for every stat, built as baseline, then form, then tonight.

Each stat's rate is  baseline x exp(sum of adjustments).  Every adjustment is one fitted coefficient
times one input, so the list of adjustments printed with a projection is exactly how it was built.
Coefficients are fitted on earlier seasons only. Factor groups can be switched off in config.

What is in, by group (see docs/nba_audit.md for why the rest is missing):
  form               last-5 volume per minute against the opponents faced; last-5 shooting, capped small
  teammate_inout     with/without splits from inout.py
  opp_shot_profile   opponent's allowed rim rate, three rate, free-throw rate and accuracy by zone
  opp_position       what the opponent allows per minute to guards / forwards / centres
  rim_protection     opponent's block rate and rim attempts allowed (one combined input, for blocks and twos)
  situational        home/away (capped), back-to-back, season phase
  referee            crew foul tendency, for free throws
What is out because no reachable source has it: pick-and-roll coverage, zone frequency, play types,
individual defender matchup, shot contests, off-ball movement and screens, double teams, touches,
drives, potential assists, rebound chances, deflections.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.linear_model import PoissonRegressor

from nba.config import CONFIG

VOLUME = ["fg2a", "fg3a", "fta", "reb", "ast", "stl", "blk"]
MAKES = {"fg2m": ("fg2a", "p2"), "fg3m": ("fg3a", "p3")}
GROUPS = {
    "form": ["form_{s}", "form_shoot_{s}"],
    "teammate_inout": ["io_{s}"],
    "opp_shot_profile": ["x_rimvol", "x_3vol", "x_fta", "x_rimpct", "x_midpct", "x_p3", "x_miss", "x_tov"],
    "opp_position": ["pos_{s}"],
    "rim_protection": ["x_blk"],
    "situational": ["home_c", "b2b", "early", "post_asb", "final_weeks"],
    "referee": ["ref_pf"],
}
FEATS = {
    "fg2a": ["form_fg2a", "io_fga", "x_rimvol", "pos_fga", "home_c", "b2b", "early", "post_asb", "final_weeks"],
    "fg3a": ["form_fg3a", "io_fg3a", "x_3vol", "pos_fg3a", "home_c", "b2b", "early", "post_asb", "final_weeks"],
    "fta": ["form_fta", "io_fta", "x_fta", "pos_fta", "ref_pf", "home_c", "b2b"],
    "reb": ["form_reb", "io_reb", "x_miss", "pos_reb", "home_c", "b2b"],
    "ast": ["form_ast", "io_ast", "pos_ast", "home_c", "b2b"],
    "stl": ["form_stl", "x_tov", "pos_stl", "home_c", "b2b"],
    "blk": ["form_blk", "x_blk", "pos_blk", "home_c", "b2b"],
    "fg2m": ["form_shoot_fg2m", "x_rimpct", "x_midpct", "x_blk", "home_c", "b2b", "early", "post_asb", "final_weeks"],
    "fg3m": ["form_shoot_fg3m", "x_p3", "home_c", "b2b", "early", "post_asb", "final_weeks"],
}
NUISANCE = ["pace_c"]
LABEL = {"form": "last-5 form", "teammate_inout": "teammate in/out", "opp_shot_profile": "opponent shot profile",
         "opp_position": "opponent vs position", "rim_protection": "rim protection", "situational": "situation",
         "referee": "referee crew"}


def _g(feat):
    if feat.startswith("form"): return "form"
    if feat.startswith("io_"): return "teammate_inout"
    if feat.startswith("pos_"): return "opp_position"
    if feat == "x_blk": return "rim_protection"
    if feat.startswith("x_"): return "opp_shot_profile"
    if feat == "ref_pf": return "referee"
    return "situational"


def design(P: pd.DataFrame, T: pd.DataFrame, L: pd.DataFrame, C: pd.DataFrame, G: pd.DataFrame, cfg=CONFIG) -> pd.DataFrame:
    """Baselines and tonight's inputs for every player row. C = game_sim.clash(...), G = game table."""
    D = P.copy()
    w = cfg["last_season_weight"] * D.get("prev_w", pd.Series(1.0, index=D.index))
    lg = L.set_index("date_et").reindex(D.date_et)
    lg.index = D.index
    grp = D.grp.to_numpy()
    def lg_pos(stat):
        num = np.select([grp == "G", grp == "F"], [lg[f"lg_G_{stat}"], lg[f"lg_F_{stat}"]], lg[f"lg_C_{stat}"])
        den = np.select([grp == "G", grp == "F"], [lg["lg_G_min"], lg["lg_F_min"]], lg["lg_C_min"])
        r = num / np.where(den > 0, den, np.nan)
        return np.where(np.isfinite(r), r, np.nanmean(r) if np.isfinite(np.nanmean(r)) else 0.0)
    D["s_fg2a"], D["prev_fg2a"], D["l5_fg2a"] = D.s_fga - D.s_fg3a, D.prev_fga - D.prev_fg3a, D.l5_fga - D.l5_fg3a
    D["s_fg2m"], D["prev_fg2m"], D["l5_fg2m"] = D.s_fgm - D.s_fg3m, D.prev_fgm - D.prev_fg3m, D.l5_fgm - D.l5_fg3m
    mins = D.s_min + w * D.prev_min
    pri = {"fg2a": lg_pos("fga") - lg_pos("fg3a"), "fg3a": lg_pos("fg3a"), "fta": lg_pos("fta"), "reb": lg_pos("reb"),
           "ast": lg_pos("ast"), "stl": lg_pos("stl"), "blk": lg_pos("blk")}
    km = cfg["rate_prior_minutes"]
    kmap = {"fg2a": "fga", "fg3a": "fg3a", "fta": "fta", "reb": "reb", "ast": "ast", "stl": "stl", "blk": "blk"}
    fringe = np.where(D.base_min.fillna(0) < 15, 0.8, 1.0)        # low-minute players use the ball less than their position average
    for s in VOLUME:
        k = km[kmap[s]]
        D["b_" + s] = (D["s_" + s] + w * D["prev_" + s] + k * pri[s] * (fringe if s in ("fg2a", "fg3a", "fta", "ast") else 1.0)) / (mins + k)
    oshare = ((D.s_oreb + w * D.prev_oreb + 15 * np.where(grp == "C", 0.3, np.where(grp == "F", 0.22, 0.14))) /
              (D.s_reb + w * D.prev_reb + 15))
    D["oreb_share"] = oshare.clip(0.03, 0.6)
    ka = cfg["eff_prior_attempts"]
    lg2 = ((lg.lg_fgm - lg.lg_fg3m) / (lg.lg_fga - lg.lg_fg3a).replace(0, np.nan)).fillna(0.54).to_numpy()
    lg3 = (lg.lg_fg3m / lg.lg_fg3a.replace(0, np.nan)).fillna(0.36).to_numpy()
    lgft = (lg.lg_ftm / lg.lg_fta.replace(0, np.nan)).fillna(0.78).to_numpy()
    lgrim = (lg.lg_rim_m / lg.lg_rim_a.replace(0, np.nan)).fillna(0.64).to_numpy()
    lgmid = (lg.lg_mid_m / lg.lg_mid_a.replace(0, np.nan)).fillna(0.43).to_numpy()
    D["b_p2"] = (D.s_fg2m + w * D.prev_fg2m + ka["p2"] * lg2) / (D.s_fg2a + w * D.prev_fg2a + ka["p2"])
    D["b_p3"] = (D.s_fg3m + w * D.prev_fg3m + ka["p3"] * (lg3 - 0.02)) / (D.s_fg3a + w * D.prev_fg3a + ka["p3"])
    D["b_ft"] = (D.s_ftm + w * D.prev_ftm + ka["ft"] * lgft) / (D.s_fta + w * D.prev_fta + ka["ft"])
    rim_a, mid_a = D.s_rim_a + w * D.prev_rim_a, D.s_mid_a + w * D.prev_mid_a
    D["rim_share2"] = ((rim_a + 20 * 0.55) / (rim_a + mid_a + 20)).clip(0.05, 0.98)
    c3 = D.s_c3_a + w * D.prev_c3_a
    D["c3_share"] = (c3 + 10 * 0.25) / (D.s_fg3a + w * D.prev_fg3a + 10)
    D["base_sample_min"] = mins.round(0)

    # ---- form: last five against what those opponents allow
    pc = cfg["form_pseudo"]
    l5m = D.l5_min.fillna(0)
    for s in VOLUME:
        D["form_" + s] = np.log((D["l5_" + s].fillna(0) + pc[s]) / (l5m * D["b_" + s] + pc[s]))
    D["form_shoot_fg2m"] = np.log((D.l5_fg2m.fillna(0) + 25 * D.b_p2) / (D.l5_fg2a.fillna(0) * D.b_p2 + 25 * D.b_p2))
    D["form_shoot_fg3m"] = np.log((D.l5_fg3m.fillna(0) + 25 * D.b_p3) / (D.l5_fg3a.fillna(0) * D.b_p3 + 25 * D.b_p3))

    # ---- opponent
    c = C.set_index(["game_id", "team_id"]).reindex(pd.MultiIndex.from_arrays([D.game_id, D.team_id]))
    def ln(a, b):
        return np.log(np.clip(c[a].to_numpy() / c[b].to_numpy(), 0.6, 1.6))
    rs = D.rim_share2.to_numpy()
    D["x_rimvol"] = np.nan_to_num(rs * ln("opp_o_rim_share", "opp_lg_rim_share"))
    D["x_3vol"] = np.nan_to_num(ln("opp_o_r3", "opp_lg_r3"))
    D["x_fta"] = np.nan_to_num(ln("opp_o_fta_pp", "opp_lg_fta_pp"))
    D["x_rimpct"] = np.nan_to_num(rs * ln("opp_o_rim_pct", "opp_lg_rim_pct"))
    D["x_midpct"] = np.nan_to_num((1 - rs) * ln("opp_o_mid_pct", "opp_lg_mid_pct"))
    D["x_p3"] = np.nan_to_num(ln("opp_o_p3", "opp_lg_p3"))
    D["x_tov"] = np.nan_to_num(ln("opp_o_tov_pp", "opp_lg_tov_pp")) * 0  # replaced below with the opponent's own turnover rate
    t = T.set_index(["game_id", "team_id"])
    oi = pd.MultiIndex.from_arrays([D.game_id, D.opp_id])
    o = t.reindex(oi)
    kpos = cfg["opp_pos_prior_games"]
    for s in ("fga", "fg3a", "fta", "reb", "ast", "stl", "blk"):
        num = np.select([grp == "G", grp == "F"], [o[f"al_G_{s}"], o[f"al_F_{s}"]], o[f"al_C_{s}"]) + \
              0.5 * np.select([grp == "G", grp == "F"], [o[f"pal_G_{s}"], o[f"pal_F_{s}"]], o[f"pal_C_{s}"])
        den = np.select([grp == "G", grp == "F"], [o["al_G_min"], o["al_F_min"]], o["al_C_min"]) + \
              0.5 * np.select([grp == "G", grp == "F"], [o["pal_G_min"], o["pal_F_min"]], o["pal_C_min"])
        lgr = lg_pos(s)
        prior_min = kpos * 80.0
        D["pos_" + s] = np.log(np.clip((num + prior_min * lgr) / (den + prior_min) / np.where(lgr > 0, lgr, 1), 0.6, 1.6))
    # opponent's own offence: turnovers (for steals), missed shots (for rebounds), rim attempts and blocks suffered
    def orate(num, den, lgnum, lgden, k=12):
        n_ = o["ts_" + num].to_numpy() + 0.4 * o["tp_" + num].to_numpy()
        d_ = (o["ts_" + den].to_numpy() + 0.4 * o["tp_" + den].to_numpy())
        l_ = (lg["lg_" + lgnum] / lg["lg_" + lgden].replace(0, np.nan)).to_numpy()
        l_ = np.where(np.isfinite(l_), l_, np.nanmean(l_))
        per = 95.0                                          # about one game of possessions or shot attempts
        return np.log(np.clip((n_ + k * per * l_) / (d_ + k * per) / l_, 0.6, 1.6))
    D["x_tov"] = np.nan_to_num(orate("tov", "poss", "tov", "poss"))
    D["opp_games"] = o.ts_n.to_numpy()
    miss = np.log(np.clip((1 - (o.ts_fgm + 0.4 * o.tp_fgm + 500 * 0.47) / (o.ts_fga + 0.4 * o.tp_fga + 500)) / 0.53, 0.8, 1.25))
    D["x_miss"] = np.nan_to_num(miss.to_numpy())
    D["x_blk"] = np.nan_to_num(orate("rim_a", "fga", "rim_a", "fga")) + np.nan_to_num(orate("o_blk", "fga", "blk", "fga"))

    # ---- situation
    D["home_c"] = D.is_home - 0.5
    gno = D.game_no.fillna(40)
    D["early"], D["post_asb"], D["final_weeks"] = (gno <= 20).astype(int), ((gno > 55) & (gno <= 72)).astype(int), (gno > 72).astype(int)
    g = G.set_index("game_id")
    D["ref_pf"] = g.ref_pf.reindex(D.game_id).fillna(0).to_numpy() / 5.0
    D["pace_c"] = np.log(g.r_pace.reindex(D.game_id).fillna(100).to_numpy() / 100.0)
    D["io_fg2a"] = D.io_fga
    # fourth-quarter usage in the player's own games: shots per second in the fourth relative to the whole game
    kq = cfg["q4_usage_prior_fga"]
    q4r = ((D.s_q4_fga + w * D.prev_q4_fga + kq * 0.24) / (D.s_fga + w * D.prev_fga + kq)) / \
          ((D.s_sec_q4 + w * D.prev_sec_q4 + 60 * 200 * 0.24) / ((D.s_min + w * D.prev_min) * 60 + 60 * 200))
    D["q4_usage_ratio"] = q4r.clip(0.7, 1.5).fillna(1.0)
    return D


@dataclass
class RateModel:
    coefs: dict = field(default_factory=dict)        # stat -> {feature: coefficient}
    groups_on: dict = field(default_factory=dict)
    cfg: dict = None

    def adjust(self, D: pd.DataFrame, stat: str) -> tuple[np.ndarray, dict]:
        """Total log-adjustment for a stat (capped) and the contribution of each factor group."""
        cap_v, cap_s = self.cfg["form_cap_volume"], self.cfg["form_cap_shooting"]
        parts = {}
        for f, b in self.coefs[stat].items():
            if f in NUISANCE or f.startswith("_"):
                continue
            grp = _g(f)
            if not self.groups_on.get(grp, True):
                continue
            v = b * D[f].to_numpy(float)
            if f.startswith("form_shoot"):
                v = np.clip(v, -cap_s, cap_s)
            elif f.startswith("form_"):
                v = np.clip(v, -cap_v, cap_v)
            elif f == "home_c":
                v = np.clip(v, -self.cfg["home_away_cap"], self.cfg["home_away_cap"])
            parts[grp] = parts.get(grp, 0) + v
        tot = sum(parts.values()) if parts else np.zeros(len(D))
        lim = np.log1p(self.cfg["max_total_adjustment"])
        return np.clip(tot, -lim, lim), parts


def fit(D: pd.DataFrame, cfg=CONFIG, groups_on: dict | None = None, alpha: float = 2e-3) -> RateModel:
    """Poisson fits of actual counts against baseline x minutes, on played rows of earlier seasons."""
    groups_on = dict(cfg["factor_groups_on"]) if groups_on is None else groups_on
    d = D[(D.played == 1) & (D["min"] >= 10)].copy()
    d["fg2a"], d["fg2m"] = d.fga - d.fg3a, d.fgm - d.fg3m
    M = RateModel(groups_on=groups_on, cfg=cfg)
    for stat, feats in FEATS.items():
        use = [f for f in feats if groups_on.get(_g(f), True)] + NUISANCE
        if stat in MAKES:
            att, pct = MAKES[stat]
            expo = d[att] * d["b_" + pct]
            use = [f for f in use if f not in NUISANCE]
        else:
            expo = d["min"] * d["b_" + stat]
        ok = expo > 0.05
        y = (d[stat][ok] / expo[ok]).clip(0, 20)
        if not use:                                   # every group switched off: baseline with a level correction only
            M.coefs[stat] = {"_intercept": float(np.log(np.average(y, weights=expo[ok])))}
            continue
        reg = PoissonRegressor(alpha=alpha, max_iter=300).fit(d.loc[ok, use].fillna(0), y, sample_weight=expo[ok])
        M.coefs[stat] = dict(zip(use, reg.coef_))
        M.coefs[stat]["_intercept"] = float(reg.intercept_)
    return M


def deviance(M: RateModel, D: pd.DataFrame) -> dict:
    """Out-of-sample Poisson deviance per stat (lower is better), on played rows."""
    d = D[(D.played == 1) & (D["min"] >= 10)].copy()
    d["fg2a"], d["fg2m"] = d.fga - d.fg3a, d.fgm - d.fg3m
    out = {}
    for stat in FEATS:
        if stat in MAKES:
            att, pct = MAKES[stat]
            expo = d[att] * d["b_" + pct]
            nuis = 0.0
        else:
            expo = d["min"] * d["b_" + stat]
            nuis = M.coefs[stat].get("pace_c", 0) * d.pace_c
        adj, _ = M.adjust(d, stat)
        mu = np.maximum(expo * np.exp(M.coefs[stat]["_intercept"] + adj + nuis), 1e-6)
        y = d[stat].to_numpy(float)
        dev = 2 * (np.where(y > 0, y * np.log(np.maximum(y, 1e-9) / mu), 0) - (y - mu))
        out[stat] = float(np.mean(dev))
    return out


def apply(M: RateModel, D: pd.DataFrame, cfg=CONFIG) -> pd.DataFrame:
    """Tonight's rates per minute, itemised adjustments, expected shooting and the shooting gate."""
    R = D.copy()
    items = [[] for _ in range(len(R))]
    for stat in VOLUME + ["fg2m", "fg3m"]:
        adj, parts = M.adjust(R, stat)
        inter = M.coefs[stat]["_intercept"]
        if stat in MAKES:
            base = R["b_" + MAKES[stat][1]]
            R["p2" if stat == "fg2m" else "p3"] = (base * np.exp(inter + adj)).clip(0.05, 0.85)
        else:
            R["r_" + stat] = R["b_" + stat] * np.exp(inter + adj)
        R["adj_" + stat] = adj
        for grp, v in parts.items():
            for i in np.where(np.abs(v) >= 0.01)[0]:
                items[i].append((stat, grp, float(v[i])))
    R["pft"] = R.b_ft
    R["r_oreb"], R["r_dreb"] = R.r_reb * R.oreb_share, R.r_reb * (1 - R.oreb_share)
    R["items"] = items
    fga_b = R.b_fg2a + R.b_fg3a
    fga_t = R.r_fg2a + R.r_fg3a
    R["base_fg_pct"] = (R.b_fg2a * R.b_p2 + R.b_fg3a * R.b_p3) / fga_b.replace(0, np.nan)
    R["exp_fg_pct"] = (R.r_fg2a * R.p2 + R.r_fg3a * R.p3) / fga_t.replace(0, np.nan)
    R["base_3p_pct"], R["exp_3p_pct"] = R.b_p3, R.p3
    R["gate_pts"] = (R.exp_fg_pct >= R.base_fg_pct + cfg["shooting_gate_fg_margin"]).astype(int)
    R["gate_fg3m"] = ((R.exp_3p_pct >= R.base_3p_pct + cfg["shooting_gate_3p_margin"]) &
                      (R.r_fg3a >= R.b_fg3a * (1 + cfg["shooting_gate_3pa_margin"]))).astype(int)
    l5 = (R.l5_fga / R.l5_min.replace(0, np.nan)) / (R.s_fga / R.s_min.replace(0, np.nan))
    R["role_shift"] = ((l5 - 1).abs() >= cfg["role_shift_usage"]) & (R.s_n >= 10) & (R.l5_n >= 3)
    return R


def explain(row, stat_names=None) -> list[str]:
    """The itemised adjustments of one player as plain lines, biggest first."""
    names = {"fg2a": "two-point attempts", "fg3a": "three-point attempts", "fta": "free-throw attempts", "reb": "rebounds",
             "ast": "assists", "stl": "steals", "blk": "blocks", "fg2m": "two-point accuracy", "fg3m": "three-point accuracy"}
    out = []
    for stat, grp, v in sorted(row["items"], key=lambda x: -abs(x[2])):
        n = {"form": f"last {int(row.l5_n or 0)} games", "opp_position": f"opponent's {int(row.get('opp_games', 0) or 0)} games this season plus last season",
             "opp_shot_profile": f"opponent's {int(row.get('opp_games', 0) or 0)} games this season plus last season",
             "teammate_inout": "see in/out note"}.get(grp, "")
        out.append(f"{names[stat]} {np.expm1(v):+.0%} from {LABEL[grp]}" + (f" ({n})" if n else ""))
    return out
