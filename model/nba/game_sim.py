"""Game script engine. Runs before any player projection.

Part A  team projection: opponent-adjusted ratings (ridge, recent games weighted more, last season as the
        starting point), then a fitted regression that adds rest, travel, home court, who is missing tonight,
        style clash and the referee crew. Reported next to the market number and the blend of the two.
Part B  simulation: every game is played N times in eight six-minute segments. Each segment draws possessions,
        turnovers, shot attempts by type, makes and free throws for both teams, so the score is built from the
        same events the player simulation later hands out to players.
Part C  blowout states and probabilities, read straight off the simulated games.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV

from nba.config import CONFIG

SEG = 8
MARGIN_X = ["r_margin", "home", "d_b2b", "d_3in4", "d_trip", "d_rest", "d_missing", "d_tz"]
TOTAL_X = ["r_total", "r_pace", "s_b2b", "s_missing", "s_3pa", "s_orb", "s_tov", "s_fta", "ref_pts", "ref_pf"]


# ------------------------------------------------------------------ Part A: ratings
def ratings(T: pd.DataFrame, cfg=CONFIG) -> pd.DataFrame:
    """Pre-game offence, defence and pace ratings for both teams of every game (home rows of T order).
    Each date is rated from games that ended before that date."""
    t = T.sort_values("tip")
    home = t[t.side_home == 1].drop_duplicates("game_id").set_index("game_id")
    away = t[t.side_home == 0].drop_duplicates("game_id").set_index("game_id")
    g = pd.DataFrame({"season": home.season, "date": home.date_et, "h": home.team_id, "a": away.team_id.reindex(home.index),
                      "pending": home.pending, "neutral": (home.is_home == 0.5).astype(float),
                      "ppp_h": home.team_pts / home.poss, "ppp_a": home.opp_pts / home.poss,
                      "pace": home.poss / home.reg_min * 48}).dropna(subset=["a"])
    teams = sorted(set(g.h) | set(g.a))
    ix = {x: i for i, x in enumerate(teams)}
    n = len(teams)
    hl, lam, carry = cfg["rating_half_life_games"] * 2.2, cfg["rating_ridge"], cfg["season_carry"]
    out = []
    prior = np.zeros(3 * n)
    for season, gs in g.groupby("season", sort=True):
        done = gs[gs.pending == 0]
        dn = pd.to_datetime(done.date).to_numpy()
        hi, ai = done.h.map(ix).to_numpy(), done.a.map(ix).to_numpy()
        m = len(done)
        Xo = np.zeros((2 * m, 2 * n + 1)); yo = np.zeros(2 * m)
        r = np.arange(m)
        Xo[r, hi] = 1; Xo[r, n + ai] = -1; Xo[r, 2 * n] = 0.5 * (1 - done.neutral.to_numpy()); yo[:m] = done.ppp_h
        Xo[m + r, ai] = 1; Xo[m + r, n + hi] = -1; Xo[m + r, 2 * n] = -0.5 * (1 - done.neutral.to_numpy()); yo[m:] = done.ppp_a
        Xp = np.zeros((m, n)); Xp[r, hi] = 1; Xp[r, ai] = 1; yp = done.pace.to_numpy()
        last = prior.copy()
        for day, today in gs.groupby("date", sort=True):
            d0 = np.datetime64(day)
            k = dn < d0
            if k.sum() >= 10:
                age = (d0 - dn[k]).astype("timedelta64[D]").astype(float)
                w = 0.5 ** (age / hl)
                mu = np.average(np.r_[yo[:m][k], yo[m:][k]], weights=np.r_[w, w])
                A = np.r_[Xo[:m][k], Xo[m:][k]]; ww = np.r_[w, w]
                p0 = np.r_[prior[:2 * n], cfg["home_court_prior"] / 100.0]
                reg = np.eye(2 * n + 1) * lam; reg[-1, -1] = lam * 20
                AtW = A.T * ww
                sol = p0 + np.linalg.solve(AtW @ A + reg, AtW @ (np.r_[yo[:m][k], yo[m:][k]] - mu - A @ p0))
                mp = np.average(yp[k], weights=w)
                Ap = Xp[k]
                ApW = Ap.T * w
                pace = prior[2 * n:] + np.linalg.solve(ApW @ Ap + np.eye(n) * lam, ApW @ (yp[k] - mp - Ap @ prior[2 * n:]))
                last = np.r_[sol[:2 * n], pace]
                hca = sol[-1]
            else:
                sol = np.r_[prior[:2 * n], cfg["home_court_prior"] / 100.0]
                mu = np.average(yo[:m][k].tolist() + yo[m:][k].tolist() + [1.14] * 20)
                mp, pace, hca = 100.0, prior[2 * n:], cfg["home_court_prior"] / 100.0
            for gid, row in today.iterrows():
                h, a = ix[row.h], ix[row.a]
                side = 0.5 * (1 - row.neutral) * hca
                out.append({"game_id": gid, "r_ppp_h": mu + sol[h] - sol[n + a] + side, "r_ppp_a": mu + sol[a] - sol[n + h] - side,
                            "r_pace": mp + pace[h] + pace[a], "home_id": row.h, "away_id": row.a, "neutral": row.neutral})
        prior = last * carry
    return pd.DataFrame(out)


def _rate(num, den, pnum, pden, lg, k):
    """Season-to-date rate with last season, then the league, as the prior (k games' worth of weight)."""
    prior = np.where(pden > 0, pnum / np.maximum(pden, 1e-9), lg)
    wt = np.where(pden > 0, pden / 82.0, 60.0) * k      # a typical game's worth of the denominator, times k games
    return (num + prior * wt) / (den + wt)


def team_style(T: pd.DataFrame, L: pd.DataFrame, cfg=CONFIG) -> pd.DataFrame:
    """Per-possession tendencies for and against, for each team before each game."""
    k = cfg["style_prior_games"]
    lg = L.set_index("date_et").reindex(T.date_et)
    def L_(a, b):
        return (lg["lg_" + a] / lg["lg_" + b].replace(0, np.nan)).to_numpy()
    S = pd.DataFrame({"game_id": T.game_id.to_numpy(), "team_id": T.team_id.to_numpy(), "opp_id": T.opp_id.to_numpy()})
    def both(name, num, den, lgv):
        lgv = np.nan_to_num(lgv, nan=np.nanmean(lgv) if np.isfinite(np.nanmean(lgv)) else 0.0)
        S[name] = _rate(T["ts_" + num].to_numpy(), T["ts_" + den].to_numpy(), T["tp_" + num].to_numpy(), T["tp_" + den].to_numpy(), lgv, k)
        S["o_" + name] = _rate(T["ts_o_" + num].to_numpy(), T["ts_" + den].to_numpy() if den == "poss" else T["ts_o_" + den].to_numpy(),
                               T["tp_o_" + num].to_numpy(), T["tp_" + den].to_numpy() if den == "poss" else T["tp_o_" + den].to_numpy(), lgv, k)
        S["lg_" + name] = lgv
    both("tov_pp", "tov", "poss", L_("tov", "poss"))
    both("fta_pp", "fta", "poss", L_("fta", "poss"))
    both("fga_pp", "fga", "poss", L_("fga", "poss"))
    both("r3", "fg3a", "fga", L_("fg3a", "fga"))
    both("ft_pct", "ftm", "fta", L_("ftm", "fta"))
    both("p3", "fg3m", "fg3a", L_("fg3m", "fg3a"))
    both("ast_fgm", "ast", "fgm", L_("ast", "fgm"))
    both("rim_share", "rim_a", "fga", L_("rim_a", "fga"))
    both("c3_share", "c3_a", "fg3a", L_("c3_a", "fg3a"))
    both("rim_pct", "rim_m", "rim_a", L_("rim_m", "rim_a"))
    both("mid_pct", "mid_m", "mid_a", L_("mid_m", "mid_a"))
    fg2m, fg2a = lg.lg_fgm - lg.lg_fg3m, lg.lg_fga - lg.lg_fg3a
    lg2 = (fg2m / fg2a.replace(0, np.nan)).to_numpy(); lg2 = np.nan_to_num(lg2, nan=np.nanmean(lg2))
    for pre, name in (("", "p2"), ("o_", "o_p2")):
        S[name] = _rate((T[f"ts_{pre}fgm"] - T[f"ts_{pre}fg3m"]).to_numpy(), (T[f"ts_{pre}fga"] - T[f"ts_{pre}fg3a"]).to_numpy(),
                        (T[f"tp_{pre}fgm"] - T[f"tp_{pre}fg3m"]).to_numpy(), (T[f"tp_{pre}fga"] - T[f"tp_{pre}fg3a"]).to_numpy(), lg2, k)
    S["lg_p2"] = lg2
    # rebounds, steals and blocks as shares of the chances that produce them
    lgo = (lg.lg_oreb / (lg.lg_oreb + lg.lg_dreb).replace(0, np.nan)).to_numpy(); lgo = np.nan_to_num(lgo, nan=np.nanmean(lgo))
    S["orb"] = _rate(T.ts_oreb.to_numpy(), (T.ts_oreb + T.ts_o_dreb).to_numpy(), T.tp_oreb.to_numpy(), (T.tp_oreb + T.tp_o_dreb).to_numpy(), lgo, k)
    S["o_orb"] = _rate(T.ts_o_oreb.to_numpy(), (T.ts_o_oreb + T.ts_dreb).to_numpy(), T.tp_o_oreb.to_numpy(), (T.tp_o_oreb + T.tp_dreb).to_numpy(), lgo, k)
    S["lg_orb"] = lgo
    lgs = (lg.lg_stl / lg.lg_tov.replace(0, np.nan)).to_numpy(); lgs = np.nan_to_num(lgs, nan=np.nanmean(lgs))
    S["stl_tov"] = _rate(T.ts_stl.to_numpy(), T.ts_o_tov.to_numpy(), T.tp_stl.to_numpy(), T.tp_o_tov.to_numpy(), lgs, k)
    S["lg_stl_tov"] = lgs
    lgb = (lg.lg_blk / fg2a.replace(0, np.nan)).to_numpy(); lgb = np.nan_to_num(lgb, nan=np.nanmean(lgb))
    S["blk_fg2a"] = _rate(T.ts_blk.to_numpy(), (T.ts_o_fga - T.ts_o_fg3a).to_numpy(), T.tp_blk.to_numpy(), (T.tp_o_fga - T.tp_o_fg3a).to_numpy(), lgb, k)
    S["o_blk_fg2a"] = _rate(T.ts_o_blk.to_numpy(), (T.ts_fga - T.ts_fg3a).to_numpy(), T.tp_o_blk.to_numpy(), (T.tp_fga - T.tp_fg3a).to_numpy(), lgb, k)
    S["lg_blk_fg2a"] = lgb
    return S


def clash(S: pd.DataFrame) -> pd.DataFrame:
    """Tonight's expected tendencies for each team: its own offence against this opponent's defence."""
    o = S.set_index(["game_id", "team_id"])
    opp = o.reindex(pd.MultiIndex.from_arrays([S.game_id, S.opp_id]))
    C = S[["game_id", "team_id", "opp_id"]].copy()
    for n in ("tov_pp", "fta_pp", "fga_pp", "r3", "p3", "p2", "ast_fgm", "rim_share", "c3_share", "rim_pct", "mid_pct"):
        lgv = S["lg_" + n].to_numpy() if "lg_" + n in S else S[n].mean()
        C[n] = S[n].to_numpy() * opp["o_" + n].to_numpy() / lgv
    C["ft_pct"] = S.ft_pct.to_numpy()
    C["orb"] = S.orb.to_numpy() * opp.o_orb.to_numpy() / S.lg_orb.to_numpy()
    C["stl_tov"] = S.stl_tov.to_numpy()
    C["blk_fg2a"] = S.blk_fg2a.to_numpy() * opp.o_blk_fg2a.to_numpy() / S.lg_blk_fg2a.to_numpy()
    for n in ("o_rim_share", "o_c3_share", "o_rim_pct", "o_mid_pct", "o_p3", "o_r3", "o_fta_pp", "o_tov_pp", "o_blk_fg2a",
              "lg_rim_share", "lg_c3_share", "lg_rim_pct", "lg_mid_pct", "lg_p3", "lg_r3", "lg_fta_pp", "lg_tov_pp", "lg_blk_fg2a",
              "o_orb", "lg_orb"):
        C["opp_" + n] = opp[n].to_numpy()
    return C


def missing_value(P: pd.DataFrame, cfg=CONFIG) -> pd.DataFrame:
    """Value of the rotation players expected out for each team, minus what the team has been missing
    lately (which its ratings already contain). Value = baseline minutes x game score per minute."""
    w = cfg["last_season_weight"]
    def tot(c):
        return P["s_" + c] + w * P["prev_" + c]
    gs = (tot("pts") + 0.4 * tot("fgm") - 0.7 * tot("fga") - 0.4 * (tot("fta") - tot("ftm")) + 0.7 * tot("oreb") + 0.3 * tot("dreb")
          + tot("stl") + 0.7 * tot("ast") + 0.7 * tot("blk") - 0.4 * tot("pf") - tot("tov")) / (tot("min") + 200)
    val = (P.base_min.fillna(0) * gs).where((P.exp_out == 1) & (P.base_min >= cfg["rotation_min"]) & (P.last_team == P.team_id), 0.0)
    v = P.assign(v=val).groupby(["game_id", "team_id"]).agg(v=("v", "sum"), tip=("tip", "first")).reset_index().sort_values("tip")
    v["baked"] = v.groupby("team_id").v.transform(lambda x: x.shift(1).rolling(cfg["missing_window_games"], min_periods=1).mean()).fillna(0)
    v["missing"] = v.v - v.baked
    return v[["game_id", "team_id", "missing", "v"]]


def referee_index(officials: pd.DataFrame, T: pd.DataFrame, cfg=CONFIG) -> pd.DataFrame:
    """For each game, the crew's earlier games: points and fouls per game relative to the league, shrunk."""
    g = T[T.side_home == 1].drop_duplicates("game_id")[["game_id", "tip", "known", "pending", "team_pts", "opp_pts", "pf", "o_pf"]]
    g = g.assign(pts=g.team_pts + g.opp_pts, fouls=g.pf + g.o_pf)
    from nba.features import _asof
    done = g[g.pending == 0].sort_values("known")
    # league averages as they stood before each game (never the whole-sample average, which would see the future)
    lg = pd.DataFrame({"known": done.known, "lp": done.pts.cumsum(), "lf": done.fouls.cumsum(), "ln": np.arange(1, len(done) + 1)})
    o = officials.merge(g, on="game_id", how="inner").sort_values("tip")
    od = o[o.pending == 0].sort_values("known").assign(n=1)
    cum = od.groupby("name")[["pts", "fouls", "n"]].cumsum()
    state = pd.DataFrame({"name": od.name, "known": od.known, "cp": cum.pts, "cf": cum.fouls, "cn": cum.n})
    m = _asof(o[["game_id", "name", "tip"]], state, "name").fillna(0)
    m = _asof(m, lg, None)
    k = cfg["ref_prior_games"]
    lg_pts = (m.lp / m.ln).fillna(0)
    lg_pf = (m.lf / m.ln).fillna(0)
    m["rp"], m["rf"] = (m.cp - m.cn * lg_pts) / (m.cn + k), (m.cf - m.cn * lg_pf) / (m.cn + k)
    return m.groupby("game_id").agg(ref_pts=("rp", "mean"), ref_pf=("rf", "mean"), ref_n=("cn", "mean")).reset_index()


def game_table(P, T, L, officials, cfg=CONFIG) -> pd.DataFrame:
    """One row per game with every pre-game input and (for finished games) the result."""
    R = ratings(T, cfg)
    S = team_style(T, L, cfg)
    mv = missing_value(P, cfg).set_index(["game_id", "team_id"])
    rf = referee_index(officials, T, cfg).set_index("game_id") if officials is not None and len(officials) else None
    t = T.set_index(["game_id", "team_id"])
    s = S.set_index(["game_id", "team_id"])
    G = R.copy()
    hi = pd.MultiIndex.from_arrays([G.game_id, G.home_id]); ai = pd.MultiIndex.from_arrays([G.game_id, G.away_id])
    th, ta, sh, sa = t.reindex(hi), t.reindex(ai), s.reindex(hi), s.reindex(ai)
    poss = G.r_pace
    G["r_margin"] = (G.r_ppp_h - G.r_ppp_a) * poss
    G["r_total"] = (G.r_ppp_h + G.r_ppp_a) * poss
    G["home"] = 1 - G.neutral
    f = lambda x: np.nan_to_num(x.to_numpy(float))
    G["d_b2b"], G["s_b2b"] = f(th.b2b) - f(ta.b2b), f(th.b2b) + f(ta.b2b)
    G["d_3in4"] = f(th.three_in_four) - f(ta.three_in_four)
    G["d_trip"] = (f(th.travel_miles) - f(ta.travel_miles)) / 1000
    G["d_rest"] = np.clip(f(th.rest_days), 0, 4) - np.clip(f(ta.rest_days), 0, 4)
    G["d_tz"] = np.abs(f(th.tz_change)) - np.abs(f(ta.tz_change))
    mh, ma = f(mv.missing.reindex(hi)), f(mv.missing.reindex(ai))
    G["d_missing"], G["s_missing"] = mh - ma, mh + ma
    G["s_3pa"] = f(sh.r3) + f(sa.r3) + f(sh.o_r3) + f(sa.o_r3) - 4 * f(sh.lg_r3)
    G["s_orb"] = f(sh.orb) + f(sa.orb) - 2 * f(sh.lg_orb)
    G["s_tov"] = f(sh.tov_pp) + f(sa.tov_pp) + f(sh.o_tov_pp) + f(sa.o_tov_pp) - 4 * f(sh.lg_tov_pp)
    G["s_fta"] = f(sh.fta_pp) + f(sa.fta_pp) + f(sh.o_fta_pp) + f(sa.o_fta_pp) - 4 * f(sh.lg_fta_pp)
    if rf is not None:
        G = G.merge(rf, on="game_id", how="left")
    for c in ("ref_pts", "ref_pf", "ref_n"):
        G[c] = G.get(c, pd.Series(0.0, index=G.index)).fillna(0.0)
    G["season"], G["tip"], G["date_et"], G["pending"] = th.season.to_numpy(), th.tip.to_numpy(), th.date_et.to_numpy(), th.pending.to_numpy()
    G["home"], G["home_abbr"], G["away_abbr"] = G.home, th.team.to_numpy(), ta.team.to_numpy()
    G["margin"], G["total"] = th.margin.to_numpy(), (th.team_pts + th.opp_pts).to_numpy()
    G["poss"], G["periods"] = th.poss.to_numpy(), th.periods.to_numpy()
    G["q4_entry"], G["max_lead"], G["max_deficit"] = th.q4_entry.to_numpy(), th.max_lead_2h.to_numpy(), th.max_deficit_2h.to_numpy()
    G["close_last5"] = th.close_last5.to_numpy()
    G["game_no"] = np.minimum(f(th.game_no), f(ta.game_no))
    return G


@dataclass
class TeamModel:
    margin: object = None
    total: object = None
    pace_bias: float = 0.0
    resid_sd_margin: float = 12.5
    resid_sd_total: float = 18.0
    drop: tuple = ()

    def predict(self, G: pd.DataFrame) -> pd.DataFrame:
        out = G[["game_id"]].copy()
        Xm, Xt = G[MARGIN_X].to_numpy(float).copy(), G[TOTAL_X].to_numpy(float).copy()
        for c in self.drop:
            if c in MARGIN_X: Xm[:, MARGIN_X.index(c)] = 0
            if c in TOTAL_X: Xt[:, TOTAL_X.index(c)] = 0
        out["model_margin"] = self.margin.predict(Xm)
        out["model_total"] = self.total.predict(Xt)
        out["model_poss"] = G.r_pace.to_numpy() + self.pace_bias
        return out


def fit_team_model(G: pd.DataFrame, drop: tuple = ()) -> TeamModel:
    d = G[(G.pending == 0) & G.margin.notna() & (G.game_no >= 5)]
    Xm, Xt = d[MARGIN_X].to_numpy(float).copy(), d[TOTAL_X].to_numpy(float).copy()
    for c in drop:
        if c in MARGIN_X: Xm[:, MARGIN_X.index(c)] = 0
        if c in TOTAL_X: Xt[:, TOTAL_X.index(c)] = 0
    alphas = [1, 10, 100, 1000]
    m = RidgeCV(alphas=alphas).fit(Xm, d.margin)
    t = RidgeCV(alphas=alphas).fit(Xt, d.total)
    M = TeamModel(margin=m, total=t, drop=drop)
    M.pace_bias = float((d.poss / (48 + 5 * (d.periods - 4)) * 48 - d.r_pace).mean())
    M.resid_sd_margin = float((d.margin - m.predict(Xm)).std())
    M.resid_sd_total = float((d.total - t.predict(Xt)).std())
    return M


def blend(pred: pd.DataFrame, market: pd.DataFrame | None, game_no, cfg=CONFIG) -> pd.DataFrame:
    """Our number, the market number, and the blend. Market spread is the home line (negative = home favoured).
    With no market line the blend is our number and says so."""
    out = pred.copy()
    out["market_margin"], out["market_total"] = np.nan, np.nan
    if market is not None and len(market):
        mk = market.sort_values("known_at").drop_duplicates("game_id", keep="last").set_index("game_id")
        out["market_margin"] = -mk.spread_home.reindex(out.game_id).to_numpy(float)
        out["market_total"] = mk.total.reindex(out.game_id).to_numpy(float)
    w = np.where(np.asarray(game_no) < cfg["market_weight_switch_games"], cfg["market_weight_early"], cfg["market_weight_late"])
    out["market_weight"] = np.where(out.market_margin.notna(), w, 0.0)
    out["blend_margin"] = np.where(out.market_margin.notna(), w * out.market_margin + (1 - w) * out.model_margin, out.model_margin)
    out["blend_total"] = np.where(out.market_total.notna(), w * out.market_total + (1 - w) * out.model_total, out.model_total)
    return out


# ------------------------------------------------------------------ Part B: simulation
@dataclass
class GameSims:
    game_id: str
    home_id: str
    away_id: str
    pts_q: np.ndarray          # (N, 2, 4) points by quarter, home then away
    final: np.ndarray          # (N, 2) final score including overtime
    ot: np.ndarray             # (N,) overtime periods
    poss: np.ndarray           # (N,) possessions per team, whole game
    box: dict                  # team totals per simulation, each (N, 2): fg2a fg2m fg3a fg3m fta ftm tov oreb
    q4_entry: np.ndarray       # (N,) home margin entering the fourth
    mid_q4: np.ndarray         # (N,) home margin with six minutes left
    max_lead_2h: np.ndarray    # (N, 2) biggest second-half lead seen at the checkpoints, home and away
    luck: np.ndarray           # (N, 2) each team's shooting multiplier in that game
    meta: dict = field(default_factory=dict)

    @property
    def margin(self):
        return self.final[:, 0] - self.final[:, 1]

    @property
    def total(self):
        return self.final.sum(1)

    def blowout(self, cfg=CONFIG):
        """+1 home blowout, -1 away blowout, 0 neither, per simulation."""
        h = (self.q4_entry >= cfg["blowout_q4_lead"]) | (self.max_lead_2h[:, 0] >= cfg["blowout_2h_checkpoint_lead"])
        a = (self.q4_entry <= -cfg["blowout_q4_lead"]) | (self.max_lead_2h[:, 1] >= cfg["blowout_2h_checkpoint_lead"])
        return np.where(h & ~a, 1, np.where(a & ~h, -1, np.where(h & a, np.sign(self.margin), 0))).astype(int)

    def close(self, cfg=CONFIG):
        return (np.abs(self.mid_q4) <= cfg["close_mid_q4_margin"]) & (np.abs(self.margin) <= 12) | (self.ot > 0)

    def save(self, path):
        np.savez_compressed(path, pts_q=self.pts_q, final=self.final, ot=self.ot, poss=self.poss, q4_entry=self.q4_entry,
                            mid_q4=self.mid_q4, max_lead_2h=self.max_lead_2h, luck=self.luck,
                            **{"box_" + k: v for k, v in self.box.items()})


def _solve_eff(c_home: dict, c_away: dict, tgt_h: float, tgt_a: float):
    """Scale each team's two- and three-point accuracy so its expected points per possession hits the target."""
    out = []
    for c, tgt in ((c_home, tgt_h), (c_away, tgt_a)):
        shots = c["fga_pp"] * ((1 - c["r3"]) * 2 * c["p2"] + c["r3"] * 3 * c["p3"])
        f = (tgt - c["fta_pp"] * c["ft_pct"]) / shots
        out.append(float(np.clip(f, 0.7, 1.4)))
    return out


def simulate(game_id, home_id, away_id, c_home: dict, c_away: dict, exp_poss: float, exp_margin: float, exp_total: float,
             n: int, seed: int, cfg=CONFIG) -> GameSims:
    rng = np.random.default_rng(seed)
    # Leading teams ease off and trailing teams close: each segment pulls the margin back by `rubber_band`.
    # The starting edge is scaled up so the expected final margin is still the projected one.
    rb = cfg["rubber_band"]
    phi = 1 - rb
    edge = exp_margin * (SEG * rb / (1 - phi ** SEG) if rb > 0 else 1.0)
    reg_total = exp_total - cfg["ot_total_allowance"]
    ppp_h = (reg_total + edge) / 2 / exp_poss
    ppp_a = (reg_total - edge) / 2 / exp_poss
    seg_pts_each = exp_total / 2 / SEG
    fh, fa = _solve_eff(c_home, c_away, ppp_h, ppp_a)
    C = [c_home, c_away]; F = [fh, fa]
    game_poss = rng.normal(exp_poss, cfg["sim_poss_sd"], n)
    luck = np.exp(rng.normal(0, cfg["sim_eff_sd"], (n, 2)) - cfg["sim_eff_sd"] ** 2 / 2)
    keys = ("fg2a", "fg2m", "fg3a", "fg3m", "fta", "ftm", "tov")
    box = {k: np.zeros((n, 2), int) for k in keys}
    seg_pts = np.zeros((n, 2, SEG), int)
    poss_tot = np.zeros(n)

    def play(poss, mult, t):
        p = np.maximum(poss, 1)
        mult = 1.0 if mult is None else mult
        tov = rng.binomial(p, np.clip(C[t]["tov_pp"], 0.02, 0.3))
        fga = np.maximum(np.rint(p * C[t]["fga_pp"] + rng.normal(0, 0.8, n)).astype(int), 0)
        fg3a = rng.binomial(fga, np.clip(C[t]["r3"], 0.05, 0.7))
        fg2a = fga - fg3a
        fg2m = rng.binomial(fg2a, np.clip(C[t]["p2"] * F[t] * luck[:, t] * mult, 0.05, 0.9))
        fg3m = rng.binomial(fg3a, np.clip(C[t]["p3"] * F[t] * luck[:, t] * mult, 0.03, 0.8))
        fta = rng.poisson(p * C[t]["fta_pp"])
        ftm = rng.binomial(fta, np.clip(C[t]["ft_pct"], 0.4, 0.95))
        for k, v in zip(keys, (fg2a, fg2m, fg3a, fg3m, fta, ftm, tov)):
            box[k][:, t] += v
        return 2 * fg2m + 3 * fg3m + ftm

    for s in range(SEG):
        poss = np.rint(game_poss / SEG + rng.normal(0, cfg["sim_segment_poss_sd"], n)).astype(int)
        poss_tot += poss
        lead = seg_pts[:, 0, :s].sum(1) - seg_pts[:, 1, :s].sum(1)          # home margin so far
        for t in (0, 1):
            pull = 1 - (rb / 2) * (lead if t == 0 else -lead) / seg_pts_each
            seg_pts[:, t, s] = play(poss, pull, t)
    cum = seg_pts.cumsum(2)
    final = cum[:, :, -1].copy()
    # one- and two-point games go to overtime more often than chance (late fouling, playing for the tie)
    gap = final[:, 0] - final[:, 1]
    pull_ot = (np.abs(gap) <= 2) & (gap != 0) & (rng.random(n) < cfg["ot_pull_prob"])
    for t, behind in ((0, gap < 0), (1, gap > 0)):
        add = np.where(pull_ot & behind, np.abs(gap), 0)
        final[:, t] += add; seg_pts[:, t, -1] += add
        box["ftm"][:, t] += add; box["fta"][:, t] += add
    cum = seg_pts.cumsum(2)
    ot = np.zeros(n, int)
    for _ in range(3):
        tied = final[:, 0] == final[:, 1]
        if not tied.any():
            break
        poss = np.rint(game_poss / SEG * (5 / 6) + rng.normal(0, cfg["sim_segment_poss_sd"], n)).astype(int)
        snap = {k: v.copy() for k, v in box.items()}
        add = [play(poss, None, 0), play(poss, None, 1)]
        for k in keys:                                  # only tied games keep their overtime events
            box[k] = np.where(tied[:, None], box[k], snap[k])
        final[:, 0] += np.where(tied, add[0], 0); final[:, 1] += np.where(tied, add[1], 0)
        poss_tot += np.where(tied, poss, 0)
        ot += tied
    still = final[:, 0] == final[:, 1]
    if still.any():
        w = rng.random(n) < 0.5
        final[:, 0] += np.where(still & w, 1, 0); final[:, 1] += np.where(still & ~w, 1, 0)
        box["ftm"][:, 0] += np.where(still & w, 1, 0); box["ftm"][:, 1] += np.where(still & ~w, 1, 0)
        box["fta"][:, 0] += np.where(still & w, 1, 0); box["fta"][:, 1] += np.where(still & ~w, 1, 0)
    # events that follow from the shots: rebounds from misses, steals from turnovers, blocks from twos, assists from makes
    for k in ("oreb", "dreb", "stl", "blk", "ast"):
        box[k] = np.zeros((n, 2), int)
    for t in (0, 1):
        o = 1 - t
        miss = box["fg2a"][:, t] - box["fg2m"][:, t] + box["fg3a"][:, t] - box["fg3m"][:, t]
        ft_miss = np.rint(cfg["ft_miss_rebound_share"] * (box["fta"][:, t] - box["ftm"][:, t])).astype(int)
        chances = rng.binomial(miss + ft_miss, cfg["credited_rebound_share"])     # the rest go out of bounds or to "team"
        box["oreb"][:, t] = rng.binomial(chances, np.clip(C[t]["orb"], 0.05, 0.5))
        box["dreb"][:, o] = chances - box["oreb"][:, t]
        box["stl"][:, o] = rng.binomial(box["tov"][:, t], np.clip(C[o]["stl_tov"], 0.2, 0.8))
        box["blk"][:, o] = np.minimum(rng.binomial(box["fg2a"][:, t], np.clip(C[o]["blk_fg2a"], 0.01, 0.25)),
                                      box["fg2a"][:, t] - box["fg2m"][:, t])
        box["ast"][:, t] = rng.binomial(box["fg2m"][:, t] + box["fg3m"][:, t], np.clip(C[t]["ast_fgm"], 0.3, 0.85))
    pts_q = seg_pts.reshape(n, 2, 4, 2).sum(3)
    diff = cum[:, 0, :] - cum[:, 1, :]                    # home margin after each segment
    checks = np.c_[diff[:, 3], diff[:, 4], diff[:, 5], diff[:, 6], final[:, 0] - final[:, 1]]
    return GameSims(game_id, home_id, away_id, pts_q, final, ot, poss_tot, box, diff[:, 5], diff[:, 6],
                    np.c_[checks.max(1), (-checks).max(1)], luck,
                    {"exp_poss": exp_poss, "exp_margin": exp_margin, "exp_total": exp_total, "eff_scale": [fh, fa], "seed": seed})


# ------------------------------------------------------------------ game legs
def game_leg_prob(sims: GameSims, market: str, line: float = 0.0, side: str = "home") -> float:
    """Model probability of a game leg, by counting simulated games. Spread line is the team's line
    (home -4.5 wins when home wins by 5+). Pushes count as half."""
    if market == "ml":
        return float((sims.margin > 0).mean() if side == "home" else (sims.margin < 0).mean())
    if market == "spread":
        m = sims.margin if side == "home" else -sims.margin
        return float(((m + line) > 0).mean() + 0.5 * ((m + line) == 0).mean())
    if market == "total":
        t = sims.total
        return float((t > line).mean() + 0.5 * (t == line).mean()) if side == "over" else float((t < line).mean() + 0.5 * (t == line).mean())
    raise ValueError(market)


def leg_hits(sims: GameSims, market: str, line: float, side: str) -> np.ndarray:
    """Per-simulation outcome of a game leg (True/False), for joint probabilities."""
    if market == "ml":
        return sims.margin > 0 if side == "home" else sims.margin < 0
    if market == "spread":
        return ((sims.margin if side == "home" else -sims.margin) + line) > 0
    return sims.total > line if side == "over" else sims.total < line
